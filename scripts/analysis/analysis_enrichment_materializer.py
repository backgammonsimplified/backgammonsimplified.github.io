#!/usr/bin/env python3
"""Materialize verified candidate previews and frozen HADD sidecars.

The input is an explicitly selected, already-completed Node analysis view plus
project-owned ordered movement facts.  This process never runs an analysis
engine, parses raw GNU output, ranks candidates, or executes in the browser.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.analysis import hadd_sidecar
    from scripts.analysis import materialize_node_analysis as node_materializer
except ModuleNotFoundError:  # Direct execution from scripts/analysis.
    import hadd_sidecar
    import materialize_node_analysis as node_materializer


CONFIG_SCHEMA = "bs-analyzer-analysis-enrichment-materialization-v1"
RENDER_SCHEMA = "bs-analyzer-analysis-enrichment-render-v1"
RECEIPT_SCHEMA = "bs-analyzer-candidate-preview-receipt-v1"
HADD_REQUEST_SCHEMA = "explainer-hadd-sidecar-generation-request-v1"
BOARD_COMMIT = "e3a989788758d30a0be065490d29ec48a88a05c0"
CALCULATOR_COMMIT = "a385a963ed01a6eac083dae7a1b246b1c150b3eb"
EXPLAINER_COMMIT = "58522bb078ecda273a11476c60f1875a2255b285"
EXPLAINER_PACKAGE_IDENTITY = (
    "f40ba9417896383a94e48012843eb0f45e177430e746cd01080f8243c5751424"
)
COMPLETE_GNUID = __import__("re").compile(
    r"^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$"
)


class EnrichmentError(ValueError):
    """Accepted facts cannot be enriched without guessing."""


def stable_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise EnrichmentError(f"Output is not stable finite JSON: {error}") from error


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EnrichmentError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise EnrichmentError(f"{path} must be an array")
    return value


def require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnrichmentError(f"{path} must be a non-empty string")
    return value


def output_paths(config: dict[str, Any], root: Path) -> dict[str, Path]:
    output = require_object(config.get("output"), "config.output")
    required = (
        "analysis_view",
        "assets",
        "hadd_sidecar",
        "hadd_generation_request",
        "materialization_receipt",
    )
    return {
        key: node_materializer.resolve_path(output.get(key), root, f"config.output.{key}")
        for key in required
    }


def validate_step(value: Any, expected_order: int, path: str) -> dict[str, Any]:
    step = require_object(value, path)
    if set(step) != {"order", "from", "to", "die"}:
        raise EnrichmentError(f"{path} has an unexpected structured movement schema")
    if step["order"] != expected_order:
        raise EnrichmentError(f"{path}.order must be consecutive from one")
    for key, special in (("from", "bar"), ("to", "off")):
        point = step[key]
        if isinstance(point, bool) or not (
            (isinstance(point, int) and 1 <= point <= 24) or point == special
        ):
            raise EnrichmentError(f"{path}.{key} must be point 1..24 or {special}")
    die = step["die"]
    if die is not None and (
        isinstance(die, bool) or not isinstance(die, int) or die not in range(1, 7)
    ):
        raise EnrichmentError(f"{path}.die must be null or 1..6")
    return copy.deepcopy(step)


def enrichment_index(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    materialization = require_object(config.get("analysis_enrichment"), "config.analysis_enrichment")
    if materialization.get("schema_version") != CONFIG_SCHEMA:
        raise EnrichmentError("Unsupported analysis enrichment schema")
    authority = require_object(materialization.get("authority"), "config.analysis_enrichment.authority")
    if authority != {
        "backgammonboard_commit": BOARD_COMMIT,
        "backgammoncalculator_commit": CALCULATOR_COMMIT,
        "explainer_commit": EXPLAINER_COMMIT,
        "explainer_package_identity_sha256": EXPLAINER_PACKAGE_IDENTITY,
    }:
        raise EnrichmentError("Configured semantic authority identities differ")
    rows = require_list(materialization.get("checker_analyses"), "config.analysis_enrichment.checker_analyses")
    result: dict[str, dict[str, Any]] = {}
    for analysis_index, raw in enumerate(rows):
        path = f"config.analysis_enrichment.checker_analyses[{analysis_index}]"
        row = require_object(raw, path)
        analysis_id = require_text(row.get("analysis_id"), f"{path}.analysis_id")
        if analysis_id in result:
            raise EnrichmentError(f"Duplicate enrichment analysis identity: {analysis_id}")
        candidates: dict[str, dict[str, Any]] = {}
        for candidate_index, candidate_raw in enumerate(require_list(row.get("candidates"), f"{path}.candidates")):
            candidate_path = f"{path}.candidates[{candidate_index}]"
            candidate = require_object(candidate_raw, candidate_path)
            candidate_id = require_text(candidate.get("candidate_id"), f"{candidate_path}.candidate_id")
            if candidate_id in candidates:
                raise EnrichmentError(f"Duplicate enrichment candidate identity: {candidate_id}")
            movements = [
                validate_step(value, index + 1, f"{candidate_path}.movement_steps[{index}]")
                for index, value in enumerate(require_list(candidate.get("movement_steps"), f"{candidate_path}.movement_steps"))
            ]
            if not movements:
                raise EnrichmentError(f"{candidate_path}.movement_steps must not be empty")
            candidates[candidate_id] = {
                "candidate_id": candidate_id,
                "candidate_concept_id": require_text(
                    candidate.get("candidate_concept_id"),
                    f"{candidate_path}.candidate_concept_id",
                ),
                "source_notation": require_text(
                    candidate.get("source_notation"),
                    f"{candidate_path}.source_notation",
                ),
                "movement_steps": movements,
            }
        result[analysis_id] = {"analysis_id": analysis_id, "candidates": candidates}
    return result


def prepare_base(config: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if config.get("schema_version") != node_materializer.CONFIG_SCHEMA:
        raise EnrichmentError("The completed-result selection must use the accepted Node authoring schema")
    document, manifest, _ = node_materializer.build_document(config, root)
    index = enrichment_index(config)
    selected = {entry["analysis_id"]: entry for entry in manifest["analyses"]}
    render_analyses: list[dict[str, Any]] = []
    for analysis_id, enrichment in index.items():
        if analysis_id not in selected or analysis_id not in document["analyses"]:
            raise EnrichmentError(f"Enrichment refers to an unselected analysis: {analysis_id}")
        selection = selected[analysis_id]
        if selection["kind"] != "checker":
            raise EnrichmentError("Checker preview enrichment cannot be attached to cube analysis")
        source = node_materializer.load_json(Path(selection["artifact"]))
        source_by_id = {
            candidate["id"]: candidate for candidate in source["checker"]["candidates"]
        }
        if len(source_by_id) != len(source["checker"]["candidates"]):
            raise EnrichmentError("Completed result contains duplicate candidate IDs")
        prepared_rows = []
        for candidate_id, facts in enrichment["candidates"].items():
            source_candidate = source_by_id.get(candidate_id)
            if source_candidate is None:
                raise EnrichmentError(f"Structured movement refers to unknown candidate: {candidate_id}")
            if source_candidate.get("notation") != facts["source_notation"]:
                raise EnrichmentError(f"Candidate notation identity differs: {candidate_id}")
            projected = next(
                candidate
                for candidate in document["analyses"][analysis_id]["candidates"]
                if candidate["id"] == candidate_id
            )
            prepared_rows.append(
                {
                    **facts,
                    "display_rank": projected["display_rank"],
                }
            )
        model = document["analyses"][analysis_id]
        recommendation = source.get("recommendation", {})
        recommended_id = recommendation.get("id")
        if recommended_id is None:
            matches = [
                candidate_id
                for candidate_id, candidate in source_by_id.items()
                if candidate.get("notation") == recommendation.get("notation")
            ]
            recommended_id = matches[0] if len(matches) == 1 else None
        if recommended_id not in source_by_id:
            raise EnrichmentError("Completed result recommendation identity is unavailable")
        model["recommended_id"] = recommended_id
        model["canonical_context"] = {
            "canonical_decision_id": analysis_id,
            "source_occurrence": {"occurrence_id": analysis_id},
            "source_factual_result_identity": {
                "analysis_key": analysis_id,
                "artifact_sha256": selection["artifact_sha256"],
            },
        }
        for candidate in model["candidates"]:
            candidate["move_board"] = None
            candidate["result_board"] = None
            candidate["resulting_position_id"] = None
            candidate["structured_movements"] = []
            candidate["preview"] = {
                "status": "unavailable",
                "kind": None,
                "movement_steps": [],
                "resulting_position_id": None,
                "message": (
                    "Accepted structured movement/result facts were not supplied; "
                    "no movement or resulting board was guessed."
                ),
            }
        render_analyses.append(
            {
                "analysis_id": analysis_id,
                "artifact": selection["artifact"],
                "artifact_sha256": selection["artifact_sha256"],
                "asset_subdir": selection["asset_subdir"],
                "candidates": sorted(
                    prepared_rows,
                    key=lambda item: (item["display_rank"], item["candidate_id"]),
                ),
            }
        )
    render_manifest = {
        "schema_version": RENDER_SCHEMA,
        "engine_execution_count": 0,
        "authority": {
            "board_commit": BOARD_COMMIT,
            "calculator_commit": CALCULATOR_COMMIT,
        },
        "analyses": render_analyses,
    }
    return document, render_manifest


def run_renderer(manifest: dict[str, Any], root: Path, stage: Path) -> dict[str, Any]:
    receipt_path = stage / "candidate-preview-receipt.json"
    payload = copy.deepcopy(manifest)
    payload["output_root"] = str(stage / "assets")
    payload["receipt_path"] = str(receipt_path)
    manifest_path = stage / "render-manifest.json"
    manifest_path.write_bytes(stable_bytes(payload))
    environment = dict(os.environ)
    default_library = root / ".r-library"
    inherited = environment.get("R_LIBS_USER")
    if default_library.is_dir():
        environment["R_LIBS_USER"] = (
            str(default_library)
            if not inherited
            else os.pathsep.join((str(default_library), inherited))
        )
    executable = environment.get("RSCRIPT_BIN", "Rscript")
    try:
        subprocess.run(
            [
                executable,
                "--vanilla",
                str(root / "scripts/analysis/render_analysis_enrichment_assets.R"),
                str(manifest_path),
            ],
            cwd=root,
            env=environment,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise EnrichmentError(f"Candidate preview renderer failed: {error}") from error
    return node_materializer.load_json(receipt_path)


def validate_receipt(
    receipt: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise EnrichmentError("Candidate preview receipt schema differs")
    if receipt.get("engine_execution_count") != 0 or receipt.get("deterministic") is not True:
        raise EnrichmentError("Candidate preview receipt changed the zero-engine deterministic boundary")
    authority = require_object(receipt.get("authority"), "receipt.authority")
    if authority.get("board_commit") != BOARD_COMMIT or authority.get("calculator_commit") != CALCULATOR_COMMIT:
        raise EnrichmentError("Candidate preview receipt authority differs")
    expected_analyses = {item["analysis_id"]: item for item in manifest["analyses"]}
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for analysis_index, raw in enumerate(require_list(receipt.get("analyses"), "receipt.analyses")):
        analysis = require_object(raw, f"receipt.analyses[{analysis_index}]")
        analysis_id = require_text(analysis.get("analysis_id"), "receipt.analysis_id")
        expected = expected_analyses.get(analysis_id)
        if expected is None or analysis.get("artifact_sha256") != expected["artifact_sha256"]:
            raise EnrichmentError("Candidate receipt source factual result identity differs")
        expected_candidates = {item["candidate_id"]: item for item in expected["candidates"]}
        for candidate_index, candidate_raw in enumerate(require_list(analysis.get("candidates"), "receipt.candidates")):
            candidate = require_object(candidate_raw, f"receipt.candidates[{candidate_index}]")
            candidate_id = require_text(candidate.get("candidate_id"), "receipt.candidate_id")
            key = (analysis_id, candidate_id)
            if key in found or candidate_id not in expected_candidates:
                raise EnrichmentError("Candidate receipt identity is duplicate or unknown")
            expected_candidate = expected_candidates[candidate_id]
            if (
                candidate.get("candidate_concept_id") != expected_candidate["candidate_concept_id"]
                or candidate.get("source_notation") != expected_candidate["source_notation"]
                or candidate.get("movement_steps") != expected_candidate["movement_steps"]
            ):
                raise EnrichmentError("Candidate receipt changed accepted source/movement identity")
            result_id = candidate.get("resulting_position_id")
            identity = require_object(candidate.get("resulting_position_identity"), "receipt.resulting_position_identity")
            hadd_position = require_object(candidate.get("hadd_position"), "receipt.hadd_position")
            if (
                not isinstance(result_id, str)
                or COMPLETE_GNUID.fullmatch(result_id) is None
                or identity.get("format") != "complete_gnuid"
                or identity.get("complete_gnuid") != result_id
                or hadd_position.get("position_id") != result_id
                or hadd_position.get("perspective") != "player_on_roll"
            ):
                raise EnrichmentError("Candidate resulting-position identity/perspective differs")
            board = require_object(candidate.get("resulting_board_state"), "receipt.resulting_board_state")
            players = require_object(board.get("players"), "receipt.resulting_board_state.players")
            for player in ("player_0", "player_1"):
                state = require_object(players.get(player), f"receipt.players.{player}")
                points = require_list(state.get("points"), f"receipt.players.{player}.points")
                if len(points) != 24 or sum(points) + state.get("bar", -1) + state.get("off", -1) != 15:
                    raise EnrichmentError("Prepared resulting board violates checker totals")
            found[key] = candidate
    expected_keys = {
        (analysis["analysis_id"], candidate["candidate_id"])
        for analysis in manifest["analyses"]
        for candidate in analysis["candidates"]
    }
    if set(found) != expected_keys:
        raise EnrichmentError("Candidate preview receipt has partial or ambiguous coverage")
    return found


def attach_previews(
    document: dict[str, Any],
    receipt_index: dict[tuple[str, str], dict[str, Any]],
    config: dict[str, Any],
) -> None:
    public_root = require_text(config["output"].get("public_asset_root"), "config.output.public_asset_root").rstrip("/")
    selection_by_id = {
        item["analysis_id"]: item for item in config["analyses"]
    }
    for analysis_id, model in document["analyses"].items():
        selection = selection_by_id[analysis_id]
        subdir = selection["asset_subdir"]
        for candidate in model.get("candidates", []):
            receipt = receipt_index.get((analysis_id, candidate["id"]))
            if receipt is None:
                continue
            movement = f"{public_root}/{subdir}/{receipt['movement_asset_file']}"
            result = f"{public_root}/{subdir}/{receipt['result_asset_file']}"
            candidate.update(
                {
                    "candidate_concept_id": receipt["candidate_concept_id"],
                    "structured_movements": copy.deepcopy(receipt["movement_steps"]),
                    "resulting_position_id": receipt["resulting_position_id"],
                    "move_board": {
                        "image": movement,
                        "alt": f"Verified movement overlay for {candidate['move']}.",
                    },
                    "result_board": {
                        "image": result,
                        "alt": f"Verified resulting board after {candidate['move']}.",
                    },
                    "movement_effects": copy.deepcopy(receipt["applied_effects"]),
                    "resulting_board_state": copy.deepcopy(receipt["resulting_board_state"]),
                    "preview": {
                        "status": "available",
                        "kind": "prepared-movement-and-result",
                        "movement_steps": copy.deepcopy(receipt["movement_steps"]),
                        "movement_effects": copy.deepcopy(receipt["applied_effects"]),
                        "resulting_position_id": receipt["resulting_position_id"],
                        "perspective": copy.deepcopy(receipt["perspective"]),
                        "message": (
                            "Ordered movement, movement overlay, complete resulting GNUID, "
                            "and resulting board were prepared and cross-verified at build time."
                        ),
                    },
                }
            )


def hadd_request(
    document: dict[str, Any],
    receipt_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    positions: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    ab_requests: list[dict[str, str]] = []
    for analysis_id, analysis in sorted(document["analyses"].items()):
        if analysis.get("analysis_kind") != "checker":
            continue
        rows = analysis.get("candidates", [])
        if not rows or any((analysis_id, row["id"]) not in receipt_index for row in rows):
            return None
        recommended_id = analysis.get("recommended_id")
        if recommended_id not in {row["id"] for row in rows}:
            raise EnrichmentError("Completed result recommendation identity is unavailable")
        for row in rows:
            receipt = receipt_index[(analysis_id, row["id"])]
            position = copy.deepcopy(receipt["hadd_position"])
            position_id = position["position_id"]
            if position_id in positions and positions[position_id] != position:
                raise EnrichmentError("Duplicate resulting position identity is ambiguous")
            positions[position_id] = position
            candidates.append(
                {
                    "decision_id": analysis_id,
                    "candidate_id": row["id"],
                    "candidate_concept_id": receipt["candidate_concept_id"],
                    "result_position_id": position_id,
                    "source_occurrence_id": analysis_id,
                }
            )
            if row["id"] != recommended_id:
                ab_requests.append(
                    {
                        "decision_id": analysis_id,
                        "candidate_a_id": row["id"],
                        "candidate_b_id": recommended_id,
                    }
                )
    if not candidates:
        return None
    return {
        "schema_version": HADD_REQUEST_SCHEMA,
        "positions": [positions[key] for key in sorted(positions)],
        "candidates": sorted(candidates, key=lambda item: (item["decision_id"], item["candidate_id"])),
        "ab_requests": sorted(
            ab_requests,
            key=lambda item: (
                item["decision_id"],
                item["candidate_a_id"],
                item["candidate_b_id"],
            ),
        ),
    }


def verify_explainer(explainer: Path) -> None:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=explainer,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise EnrichmentError(f"Unable to verify frozen Explainer checkout: {error}") from error
    if head != EXPLAINER_COMMIT:
        raise EnrichmentError("Frozen Explainer checkout head differs")
    manifest = node_materializer.load_json(
        explainer
        / "artifacts/development/explainer-k002-compact-hadd-integration-contract-v1/manifest.json"
    )
    if manifest.get("package_identity_sha256") != EXPLAINER_PACKAGE_IDENTITY:
        raise EnrichmentError("Frozen Explainer integration package identity differs")


def produce_hadd(
    request: dict[str, Any],
    explainer: Path,
    destination: Path,
    root: Path,
) -> dict[str, Any]:
    verify_explainer(explainer)
    request_path = destination.parent / "hadd-generation-request.json"
    request_path.write_bytes(stable_bytes(request))
    environment = dict(os.environ)
    source_path = str(explainer / "src")
    environment["PYTHONPATH"] = (
        source_path
        if not environment.get("PYTHONPATH")
        else os.pathsep.join((source_path, environment["PYTHONPATH"]))
    )
    command = [
        sys.executable,
        str(explainer / "scripts/produce_hadd_sidecar.py"),
        "--model-bundle",
        str(explainer / "artifacts/development/explainer-k002-hadd-compact-runtime/model"),
        "--contract",
        str(explainer / "config/integration/explainer-k002-compact-hadd-integration-contract-v1.json"),
        "--request",
        str(request_path),
        "--output",
        str(destination),
    ]
    try:
        subprocess.run(command, cwd=explainer, env=environment, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise EnrichmentError(f"Frozen HADD sidecar production failed: {error}") from error
    try:
        sidecar = hadd_sidecar.load_sidecar(destination)
        hadd_sidecar.validate_sidecar(sidecar)
    except hadd_sidecar.HaddSidecarError as error:
        raise EnrichmentError(f"Generated sidecar failed the Task 020 validator: {error}") from error
    return sidecar


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in {"render-manifest.json", "candidate-preview-receipt.json"}
    }


def materialize(
    config: dict[str, Any],
    root: Path,
    explainer: Path,
    *,
    verify_repeat: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    document, render_manifest = prepare_base(config, root)
    temporary_root = Path(tempfile.mkdtemp(prefix="analyzer-enrichment-", dir=root / "task-work"))
    stage = temporary_root / "first"
    stage.mkdir(parents=True)
    receipt = run_renderer(render_manifest, root, stage)
    receipt_index = validate_receipt(receipt, render_manifest)
    if verify_repeat:
        repeated_stage = temporary_root / "second"
        repeated_stage.mkdir(parents=True)
        repeated_receipt = run_renderer(render_manifest, root, repeated_stage)
        validate_receipt(repeated_receipt, render_manifest)
        if stable_bytes(receipt) != stable_bytes(repeated_receipt):
            raise EnrichmentError("Repeated candidate preparation changed semantic content")
        if tree_hashes(stage / "assets") != tree_hashes(repeated_stage / "assets"):
            raise EnrichmentError("Repeated candidate preparation changed board assets")
    attach_previews(document, receipt_index, config)
    request = hadd_request(document, receipt_index)
    if request is None:
        document = hadd_sidecar.unavailable(document, "missing_required_resulting_position_fact")
        sidecar: dict[str, Any] = {}
    else:
        sidecar_path = stage / "generated-hadd-sidecar.json"
        sidecar = produce_hadd(request, explainer, sidecar_path, root)
        document = hadd_sidecar.attach_sidecar(document, sidecar)
        if verify_repeat:
            repeated_sidecar_path = stage / "generated-hadd-sidecar-repeat.json"
            repeated_sidecar = produce_hadd(request, explainer, repeated_sidecar_path, root)
            if stable_bytes(sidecar) != stable_bytes(repeated_sidecar):
                raise EnrichmentError("Repeated frozen HADD generation changed semantic content")
        document["hadd_materialization"] = {
            "status": "available",
            "source_factual_results": [
                {
                    "analysis_key": analysis["analysis_id"],
                    "artifact_sha256": analysis["artifact_sha256"],
                }
                for analysis in render_manifest["analyses"]
            ],
            "explainer_commit": EXPLAINER_COMMIT,
            "immutable_integration_package_identity_sha256": EXPLAINER_PACKAGE_IDENTITY,
            "sidecar_package_identity_sha256": sidecar["package_identity_sha256"],
            "model_identity_sha256": sidecar["model"]["source_model_identity_sha256"],
            "runtime_identity": sidecar["model"]["runtime_id"],
            "feature_set_identity": sidecar["feature_system"]["feature_set_identity"],
            "feature_order_identity_sha256": sidecar["feature_system"]["ordered_feature_ids_sha256"],
            "position_perspective": sidecar["target"]["position_perspective"],
            "generation_provenance": {
                "producer": sidecar["generation"]["producer_version"],
                "explainer_artifacts_read_only": True,
                "engine_execution_count": 0,
                "new_training_refits": 0,
            },
        }
    document["analysis_enrichment"] = {
        "schema_version": CONFIG_SCHEMA,
        "status": "available",
        "candidate_preview_receipt_sha256": sha256_bytes(stable_bytes(receipt)),
        "board_commit": BOARD_COMMIT,
        "calculator_commit": CALCULATOR_COMMIT,
        "engine_execution_count": 0,
        "public_deployment": False,
        "calculated_cubeful": "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED",
    }
    remapped: dict[str, Any] = {}
    selections = {item["analysis_id"]: item for item in config["analyses"]}
    for analysis_id, analysis in document["analyses"].items():
        display_id = selections.get(analysis_id, {}).get("display_id", analysis_id)
        display_id = require_text(display_id, f"config.analyses[{analysis_id}].display_id")
        if display_id in remapped:
            raise EnrichmentError(f"Duplicate presentation analysis identity: {display_id}")
        analysis["id"] = display_id
        remapped[display_id] = analysis
    document["analyses"] = {key: remapped[key] for key in sorted(remapped)}
    return document, receipt, request or {}, stage


def promote_assets(stage_assets: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}.", dir=destination.parent) as name:
        backup = Path(name) / "previous"
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(stage_assets, destination)
        except Exception:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--explainer-repo", type=Path, required=True)
    parser.add_argument("--verify-repeat", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    stage: Path | None = None
    try:
        config = node_materializer.load_json(args.config.resolve())
        paths = output_paths(config, root)
        document, receipt, request, stage = materialize(
            config,
            root,
            args.explainer_repo.resolve(),
            verify_repeat=args.verify_repeat,
        )
        sidecar_path = stage / "generated-hadd-sidecar.json"
        promote_assets(stage / "assets", paths["assets"])
        node_materializer.write_atomic(paths["analysis_view"], stable_bytes(document))
        node_materializer.write_atomic(paths["materialization_receipt"], stable_bytes(receipt))
        node_materializer.write_atomic(paths["hadd_generation_request"], stable_bytes(request))
        if sidecar_path.is_file():
            node_materializer.write_atomic(paths["hadd_sidecar"], sidecar_path.read_bytes())
    except (EnrichmentError, node_materializer.AuthoringError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        if stage is not None:
            shutil.rmtree(stage.parent, ignore_errors=True)
    print(f"PASS: materialized Analyzer enrichment: {paths['analysis_view']}")
    print(f"PASS: candidate previews and resulting boards: {paths['assets']}")
    print(f"PASS: frozen HADD sidecar: {paths['hadd_sidecar']}")
    print("ENGINE EXECUTION COUNT: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
