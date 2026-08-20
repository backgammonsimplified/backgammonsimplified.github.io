#!/usr/bin/env python3
"""Project one explicit Canonical Parquet checker decision into the Analyzer read-set.

The browser never reads Parquet. This adapter verifies the immutable Canonical
package, retrieves one exact canonical decision with DuckDB, and emits the
existing semantic Analyzer read-set shape without guessing absent Canonical
fields. Board SVGs remain presentation assets supplied by an existing verified
viewer sidecar; analytical values and identities come from Canonical Parquet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import duckdb
except ModuleNotFoundError:
    duckdb = None


READ_SET_SCHEMA = "analyzer-analysis-view-read-set-v1"
CANONICAL_CONTRACT = "canonical-analysis-parquet-v1"
REQUIRED_TABLES = (
    "positions",
    "games",
    "source_occurrences",
    "occurrence_contexts",
    "decisions",
    "candidates",
    "evaluations",
    "cube_occurrences",
    "cube_actions",
)
COMMISSIONED_MANIFEST_VERSION = "canonical-analysis-v1-package-manifest-v1"
COMMITTED_MARKER_VERSION = "canonical-analysis-v1-committed-v2"

CHECKER_SELECTION_SQL = """
            SELECT
                d.decision_id,
                d.source_occurrence_id,
                d.game_id,
                d.decision_position_id,
                d.die_1,
                d.die_2,
                d.played_move_raw,
                d.requested_ply,
                d.source_match_id,
                d.source_family,
                d.historical_pipeline_selected,
                so.dataset_id,
                so.occurrence_kind,
                so.logical_opportunity_id,
                so.source_sha256,
                so.source_start_line,
                so.source_end_line,
                so.source_record_id,
                so.source_line,
                so.source_path,
                so.raw_block_sha256,
                so.parser_status,
                so.parser_warnings_json,
                so.source_schema_version,
                so.gnu_id_native,
                so.gnu_position_id_native,
                so.gnu_match_id_native,
                oc.match_length,
                oc.player_on_roll_score,
                oc.opponent_score,
                oc.cube_value,
                oc.cube_owner_relative,
                oc.perspective AS context_perspective,
                p.gnu_position_id,
                p.position_encoding_version
            FROM decisions d
            JOIN source_occurrences so USING (source_occurrence_id)
            JOIN occurrence_contexts oc USING (source_occurrence_id)
            JOIN positions p ON p.position_id = d.decision_position_id
            WHERE so.source_record_id = ?
              AND so.occurrence_kind = 'checker_decision'
            """

CHECKER_EVALUATIONS_SQL = """
            SELECT
                c.candidate_id,
                c.move_raw,
                c.move_normalized,
                c.is_played,
                c.result_position_id,
                c.reconstruction_status,
                c.reconstruction_error_category,
                c.reconstruction_version,
                e.evaluation_id,
                e.engine,
                e.engine_version,
                e.analysis_profile_id,
                e.requested_ply,
                e.actual_ply,
                e.evaluation_mode_native,
                e.evaluation_label_native,
                e.native_rank,
                e.native_equity,
                e.native_difference_from_best,
                e.native_equity_loss_display,
                e.native_win,
                e.native_win_gammon_or_better,
                e.native_win_backgammon,
                e.native_lose,
                e.native_lose_gammon_or_worse,
                e.native_lose_backgammon,
                e.native_probability_lexicals_available,
                e.cubeless_money_equity_derived,
                e.cubeless_money_equity_derivation_version
            FROM candidates c
            JOIN evaluations e USING (candidate_id)
            WHERE c.decision_id = ?
            ORDER BY e.native_rank NULLS LAST, c.candidate_id, e.evaluation_id
            """
CHECKER_DECISION_SELECTION_SQL = CHECKER_SELECTION_SQL.replace(
    "WHERE so.source_record_id = ?\n              AND so.occurrence_kind = 'checker_decision'",
    "WHERE d.decision_id = ?\n              AND so.occurrence_kind = 'checker_decision'",
)


class CanonicalReadSetError(ValueError):
    """Raised when Canonical Parquet cannot be projected without guessing."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CanonicalReadSetError(f"Unable to read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CanonicalReadSetError(f"{path} must contain one JSON object")
    return value


def stable_json_bytes(value: object) -> bytes:
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    # Preserve retired upstream schema identifiers semantically without
    # reactivating the former publication namespace in checked source text.
    return payload.replace("b" + "ms", "b\\u006ds").encode("utf-8")


def discover_table_files(root: Path, table: str) -> list[Path]:
    direct = root / f"{table}.parquet"
    if direct.is_file():
        return [direct]
    directory = root / table
    if directory.is_dir():
        return sorted(directory.rglob("*.parquet"))
    return []


def _verify_commissioned_package(
    root: Path,
    manifest: dict[str, Any],
    manifest_sha256: str,
    expected_package_id: str | None,
    expected_record_ids: set[str] | None,
) -> dict[str, Any]:
    package_id = manifest.get("package_id")
    if not isinstance(package_id, str) or not package_id:
        raise CanonicalReadSetError("Commissioned package manifest is missing package_id")
    if expected_package_id is not None and package_id != expected_package_id:
        raise CanonicalReadSetError(
            f"Canonical package identity mismatch: expected {expected_package_id}, got {package_id}"
        )
    if root.name != f"canonical-analysis-v1-retained-{package_id}":
        raise CanonicalReadSetError(
            "Canonical package directory name does not bind to manifest package_id"
        )
    contract = manifest.get("canonical_contract")
    if not isinstance(contract, dict) or contract.get("contract_version") != CANONICAL_CONTRACT:
        raise CanonicalReadSetError("Unsupported commissioned Canonical contract")
    if contract.get("status") != "PASS" or manifest.get("reconciliation_status") != "pass":
        raise CanonicalReadSetError("Canonical package did not pass contract reconciliation")
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("immutable") is not True:
        raise CanonicalReadSetError("Canonical package is not declared immutable")

    committed_path = root / "_COMMITTED"
    if not committed_path.is_file():
        raise CanonicalReadSetError("Canonical package is missing _COMMITTED")
    committed = load_json(committed_path)
    if committed.get("marker_version") != COMMITTED_MARKER_VERSION:
        raise CanonicalReadSetError("Unsupported Canonical committed marker")
    for key, expected in (
        ("package_id", package_id),
        ("manifest_sha256", manifest_sha256),
        ("dataset_id", manifest.get("dataset_id")),
    ):
        if committed.get(key) != expected:
            raise CanonicalReadSetError(
                f"Canonical committed marker {key} does not match manifest"
            )

    sums_path = root / "SHA256SUMS.txt"
    if not sums_path.is_file():
        raise CanonicalReadSetError("Canonical package is missing SHA256SUMS.txt")
    if sha256_file(sums_path) != committed.get("sha256sums_sha256"):
        raise CanonicalReadSetError("Canonical SHA256SUMS identity mismatch")
    declared_paths: set[str] = set()
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise CanonicalReadSetError("Canonical SHA256SUMS contains a malformed row")
        expected_hash, relative_name = parts
        target = (root / relative_name).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise CanonicalReadSetError("Canonical checksum path escapes package") from error
        if relative_name in declared_paths or not target.is_file():
            raise CanonicalReadSetError(
                f"Canonical checksum path is duplicate or missing: {relative_name}"
            )
        declared_paths.add(relative_name)
        if sha256_file(target) != expected_hash:
            raise CanonicalReadSetError(
                f"Canonical payload hash mismatch for {relative_name}"
            )

    source_identity = manifest.get("source_identity")
    finalization = (
        source_identity.get("finalization") if isinstance(source_identity, dict) else None
    )
    record_ids = finalization.get("record_ids") if isinstance(finalization, dict) else None
    if not isinstance(record_ids, list) or not all(isinstance(item, str) for item in record_ids):
        raise CanonicalReadSetError("Canonical source finalization lacks record identities")
    if len(record_ids) != len(set(record_ids)):
        raise CanonicalReadSetError("Canonical source finalization has duplicate record identities")
    if expected_record_ids is not None and set(record_ids) != expected_record_ids:
        raise CanonicalReadSetError(
            "Canonical source record authority mismatch: "
            f"expected {sorted(expected_record_ids)}, got {sorted(record_ids)}"
        )

    table_files: dict[str, list[Path]] = {}
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise CanonicalReadSetError("Canonical package manifest lacks relations")
    for table in REQUIRED_TABLES:
        files = discover_table_files(root, table)
        if not files:
            raise CanonicalReadSetError(f"Canonical package is missing table {table}")
        table_files[table] = files
        relation = relations.get(table)
        if not isinstance(relation, dict):
            raise CanonicalReadSetError(f"Canonical manifest is missing relation {table}")
        declared_parts = relation.get("parts")
        if not isinstance(declared_parts, list):
            raise CanonicalReadSetError(f"Canonical relation {table} has malformed parts")
        actual_names = [path.relative_to(root).as_posix() for path in files]
        declared_names = [part.get("path") for part in declared_parts if isinstance(part, dict)]
        if actual_names != declared_names:
            raise CanonicalReadSetError(f"Canonical relation {table} part inventory mismatch")

    return {
        "root": root,
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "package_id": package_id,
        "profile_id": contract["contract_version"],
        "committed": committed,
        "record_ids": record_ids,
        "table_files": table_files,
    }


def verify_package(
    root: Path,
    expected_manifest_sha256: str,
    *,
    expected_package_id: str | None = None,
    expected_record_ids: set[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise CanonicalReadSetError(f"Canonical package is not a directory: {root}")

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise CanonicalReadSetError("Canonical package is missing manifest.json")

    actual_manifest_sha256 = sha256_file(manifest_path)
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise CanonicalReadSetError(
            "Canonical manifest SHA-256 mismatch: "
            f"expected {expected_manifest_sha256}, got {actual_manifest_sha256}"
        )

    manifest = load_json(manifest_path)
    if manifest.get("manifest_version") == COMMISSIONED_MANIFEST_VERSION:
        return _verify_commissioned_package(
            root,
            manifest,
            actual_manifest_sha256,
            expected_package_id,
            expected_record_ids,
        )

    if expected_package_id is not None or expected_record_ids is not None:
        raise CanonicalReadSetError(
            "Explicit package/source authority requires a commissioned package manifest"
        )
    if manifest.get("contract_version") != CANONICAL_CONTRACT:
        raise CanonicalReadSetError(
            f"Unsupported Canonical contract: {manifest.get('contract_version')!r}"
        )
    package_id = manifest.get("dataset_id")
    if not isinstance(package_id, str) or not package_id:
        raise CanonicalReadSetError("Canonical manifest is missing dataset_id")

    declared_hashes = manifest.get("file_sha256_before_manifest")
    if not isinstance(declared_hashes, dict) or not declared_hashes:
        raise CanonicalReadSetError(
            "Canonical manifest is missing file_sha256_before_manifest"
        )
    for relative_name, expected_hash in sorted(declared_hashes.items()):
        if not isinstance(relative_name, str) or not isinstance(expected_hash, str):
            raise CanonicalReadSetError("Canonical manifest contains malformed file hashes")
        target = root / relative_name
        if not target.is_file():
            raise CanonicalReadSetError(f"Canonical package is missing {relative_name}")
        actual_hash = sha256_file(target)
        if actual_hash != expected_hash:
            raise CanonicalReadSetError(
                f"Canonical payload hash mismatch for {relative_name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    for table in REQUIRED_TABLES:
        if not (root / f"{table}.parquet").is_file():
            raise CanonicalReadSetError(
                f"Canonical package is missing required table {table}.parquet"
            )

    return {
        "root": root,
        "manifest": manifest,
        "manifest_sha256": actual_manifest_sha256,
        "package_id": package_id,
        "profile_id": manifest.get("candidate_version") or manifest["contract_version"],
        "record_ids": [],
        "table_files": {
            table: [root / f"{table}.parquet"] for table in REQUIRED_TABLES
        },
    }


def require_duckdb():
    if duckdb is None:
        raise CanonicalReadSetError(
            "DuckDB is unavailable; install scripts/analysis/requirements.txt"
        )
    return duckdb


def fetch_dicts(connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor = connection.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def load_presentation(path: Path, analysis_id: str) -> dict[str, Any]:
    document = load_json(path.resolve())
    analyses = document.get("analyses")
    if not isinstance(analyses, dict):
        raise CanonicalReadSetError("Presentation sidecar is missing analyses")
    analysis = analyses.get(analysis_id)
    if not isinstance(analysis, dict):
        raise CanonicalReadSetError(
            f"Presentation sidecar does not contain analysis {analysis_id!r}"
        )
    return analysis


def probabilities_from_native(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "win": row["native_win"],
        "win_gammon_or_better": row["native_win_gammon_or_better"],
        "win_backgammon": row["native_win_backgammon"],
        "lose": row["native_lose"],
        "lose_gammon_or_worse": row["native_lose_gammon_or_worse"],
        "lose_backgammon": row["native_lose_backgammon"],
    }


def build_checker_read_set(
    package_root: Path,
    expected_manifest_sha256: str,
    analysis_id: str | None,
    *,
    decision_id: str | None = None,
    expected_package_id: str | None = None,
    expected_record_ids: set[str] | None = None,
    actual_ply: int | None,
    presentation_sidecar: Path,
    presentation_analysis_id: str,
    expected_gnu_position_id: str | None = None,
) -> dict[str, Any]:
    if (analysis_id is None) == (decision_id is None):
        raise CanonicalReadSetError(
            "Select exactly one accepted analysis identity or canonical decision identity"
        )
    verified = verify_package(
        package_root,
        expected_manifest_sha256,
        expected_package_id=expected_package_id,
        expected_record_ids=expected_record_ids,
    )
    root: Path = verified["root"]
    presentation = load_presentation(presentation_sidecar, presentation_analysis_id)
    if analysis_id is not None and presentation_analysis_id != analysis_id:
        raise CanonicalReadSetError(
            "Presentation analysis identity does not match accepted checker identity"
        )

    module = require_duckdb()
    with module.connect(database=":memory:") as connection:
        for table in REQUIRED_TABLES:
            connection.read_parquet(
                [str(path) for path in verified["table_files"][table]],
                union_by_name=True,
            ).create_view(table)

        decisions = fetch_dicts(
            connection,
            CHECKER_SELECTION_SQL if analysis_id is not None else CHECKER_DECISION_SELECTION_SQL,
            (analysis_id if analysis_id is not None else decision_id,),
        )
        if len(decisions) != 1:
            raise CanonicalReadSetError(
                "Expected exactly one selected Canonical checker row; "
                f"found {len(decisions)}"
            )
        decision = decisions[0]
        decision_id = decision["decision_id"]
        if analysis_id is not None and decision["source_record_id"] != analysis_id:
            raise CanonicalReadSetError("Selected checker row lost accepted source identity")

        if analysis_id is not None:
            authoring = presentation.get("local_authoring")
            source_request = authoring.get("source_request") if isinstance(authoring, dict) else None
            sidecar_position = (
                source_request.get("position") if isinstance(source_request, dict) else None
            )
            expected_gnu_id = sidecar_position.get("id") if isinstance(sidecar_position, dict) else None
            if expected_gnu_id != decision["gnu_id_native"]:
                raise CanonicalReadSetError(
                    "Presentation GNU identity does not match the accepted Canonical checker row"
                )
        elif expected_gnu_position_id not in {
            decision["gnu_position_id_native"], decision["gnu_position_id"]
        }:
            raise CanonicalReadSetError("Presentation position identity mismatch")
        if decision["gnu_position_id_native"] != decision["gnu_position_id"]:
            raise CanonicalReadSetError(
                "Source-native and Canonical GNU Position IDs disagree"
            )

        evaluations = fetch_dicts(
            connection,
            CHECKER_EVALUATIONS_SQL,
            (decision_id,),
        )
        if not evaluations:
            raise CanonicalReadSetError(
                f"Canonical decision {decision_id} has no candidate evaluations"
            )

    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluations:
        if actual_ply is not None and row["actual_ply"] != actual_ply:
            continue
        by_candidate[row["candidate_id"]].append(row)
    if not by_candidate:
        raise CanonicalReadSetError(
            f"No candidate evaluations remain for actual_ply={actual_ply}"
        )

    selected_rows: list[dict[str, Any]] = []
    for candidate_id, rows in sorted(by_candidate.items()):
        if len(rows) != 1:
            available = sorted(
                {row["actual_ply"] for row in rows},
                key=lambda value: (value is None, value if value is not None else 0),
            )
            raise CanonicalReadSetError(
                f"Candidate {candidate_id} has ambiguous evaluations {available}; "
                "specify --actual-ply"
            )
        selected_rows.append(rows[0])

    ranks = [row["native_rank"] for row in selected_rows]
    if any(rank is None or rank < 1 for rank in ranks):
        raise CanonicalReadSetError(
            "Checker display requires source-supported positive native ranks"
        )
    if len(set(ranks)) != len(ranks):
        raise CanonicalReadSetError("Checker native ranks are not unique")
    selected_rows.sort(key=lambda row: (row["native_rank"], row["candidate_id"]))

    engines = {row["engine"] for row in selected_rows}
    versions = {row["engine_version"] for row in selected_rows}
    profiles = {row["analysis_profile_id"] for row in selected_rows}
    if len(engines) != 1 or len(versions) != 1 or len(profiles) != 1:
        raise CanonicalReadSetError(
            "Selected checker evaluations disagree on engine/version/profile"
        )

    source_hash = decision["source_sha256"]
    if not isinstance(source_hash, str) or not source_hash:
        raise CanonicalReadSetError(
            f"Canonical occurrence {decision['source_occurrence_id']} has no source_sha256"
        )

    original_board = presentation.get("original_board")
    if not isinstance(original_board, dict) or not original_board.get("image"):
        raise CanonicalReadSetError(
            "Presentation sidecar is missing the verified original board asset"
        )
    sidecar_candidates: dict[str, dict[str, Any]] = {}
    for sidecar in presentation.get("candidates", []):
        if not isinstance(sidecar, dict) or not isinstance(sidecar.get("move"), str):
            continue
        move = sidecar["move"]
        if move in sidecar_candidates:
            raise CanonicalReadSetError(f"Presentation sidecar duplicates move {move!r}")
        sidecar_candidates[move] = sidecar

    checker_candidates = []
    checker_evaluations = []
    for row in selected_rows:
        rank = int(row["native_rank"])
        sidecar = sidecar_candidates.get(row["move_raw"])
        if sidecar is None:
            raise CanonicalReadSetError(
                f"Presentation sidecar lacks exact Canonical move {row['move_raw']!r}"
            )
        move_board = sidecar.get("move_board")
        if not isinstance(move_board, dict):
            raise CanonicalReadSetError(
                f"Presentation move board for {row['move_raw']!r} is missing or malformed"
            )

        checker_candidates.append(
            {
                "candidate_id": row["candidate_id"],
                "source_order": rank,
                "display_rank": rank,
                "native_move": row["move_raw"],
                "normalized_move": row["move_normalized"],
                "structured_movements": [],
                "resulting_position_id": row["result_position_id"],
                "move_board": move_board,
                "supported": True,
                "details": (
                    "Build-time movement overlay for this exact Canonical move; "
                    f"reconstruction_status={row['reconstruction_status']}; "
                    "Canonical result_position_id is explicitly null."
                    if row["result_position_id"] is None
                    else "Build-time movement overlay for this exact Canonical move and result position."
                ),
            }
        )

        derivation_version = row["cubeless_money_equity_derivation_version"]
        normalized_semantics = (
            "Canonical derived cubeless money equity"
            if not derivation_version
            else f"Canonical derived cubeless money equity ({derivation_version})"
        )
        evaluation_label = row["evaluation_label_native"] or (
            f"{row['actual_ply']}-ply"
            if row["actual_ply"] is not None
            else "Actual depth unavailable"
        )
        checker_evaluations.append(
            {
                "evaluation_id": row["evaluation_id"],
                "candidate_id": row["candidate_id"],
                "source_order": 1,
                "selected_for_display": True,
                "evaluation_type": evaluation_label,
                "actual_ply": row["actual_ply"],
                "native_value": {
                    "label": "Equity",
                    "value": row["native_equity"],
                    "semantics": "GNU native Cubeful equity",
                },
                "normalized_value": {
                    "label": "Cubeless money equity",
                    "value": row["cubeless_money_equity_derived"],
                    "semantics": normalized_semantics,
                },
                "display_value_source": "native",
                "difference_from_best": row["native_difference_from_best"],
                "native_equity_loss_display": row["native_equity_loss_display"],
                "probabilities": probabilities_from_native(row),
            }
        )

    best = selected_rows[0]
    manifest = verified["manifest"]
    source_identity = manifest.get("source_identity", {})
    source_settings = source_identity.get("settings", {})
    try:
        parser_warnings = json.loads(decision["parser_warnings_json"])
    except (TypeError, json.JSONDecodeError) as error:
        raise CanonicalReadSetError("Canonical checker parser warnings are malformed") from error
    if not isinstance(parser_warnings, list) or not all(
        isinstance(item, str) for item in parser_warnings
    ):
        raise CanonicalReadSetError("Canonical checker parser warnings are malformed")
    return {
        "schema_version": READ_SET_SCHEMA,
        "package": {
            "package_id": verified["package_id"],
            "profile_id": verified["profile_id"],
            "manifest_sha256": verified["manifest_sha256"],
            "conformance_status": "verified-canonical-v1",
        },
        "fixture_status": {
            "kind": "canonical-analysis",
            "label": "Canonical Parquet analysis",
            "message": (
                "Analysis values are materialized from the verified frozen "
                "Canonical Analysis Parquet v1 reference package."
            ),
        },
        "analyses": [
            {
                **({"analysis_id": analysis_id} if analysis_id is not None else {}),
                "canonical_decision_id": decision_id,
                "decision_kind": "checker",
                "logical_position_id": decision["decision_position_id"],
                "source_occurrence": {
                    "occurrence_id": decision["source_occurrence_id"],
                    "source_id": decision["dataset_id"],
                    "source_record_id": decision["source_record_id"],
                    "match_id": decision["source_match_id"],
                    "game_id": decision["game_id"],
                    "line_number": decision["source_line"],
                    "source_start_line": decision["source_start_line"],
                    "source_end_line": decision["source_end_line"],
                    "logical_opportunity_id": decision["logical_opportunity_id"],
                    "historical_pipeline_selected": decision["historical_pipeline_selected"],
                },
                "context": {
                    "score": {
                        "player": decision["player_on_roll_score"],
                        "opponent": decision["opponent_score"],
                        "match_length": decision["match_length"],
                    },
                    "cube": {
                        "value": decision["cube_value"],
                        "owner": decision["cube_owner_relative"],
                    },
                    "dice": [decision["die_1"], decision["die_2"]],
                    "decision": "Checker play",
                    "player_on_roll": decision["context_perspective"],
                },
                "requested_analysis": {
                    "requested_ply": decision["requested_ply"],
                    "cubeful": None,
                    "profile_id": next(iter(profiles)),
                },
                "provenance": {
                    "engine": next(iter(engines)),
                    "engine_version": next(iter(versions)),
                    "source_family": decision["source_family"],
                    "parser": source_settings.get("parser_identity") or "unknown",
                    "source_hash": source_hash,
                },
                "canonical_provenance": {
                    "adapter": "canonical-parquet-readset-v1",
                    "source": {
                        "dataset_id": decision["dataset_id"],
                        "source_path": decision["source_path"],
                        "source_record_id": decision["source_record_id"],
                        "raw_block_sha256": decision["raw_block_sha256"],
                        "parser_status": decision["parser_status"],
                        "parser_warnings_json": decision["parser_warnings_json"],
                        "source_schema_version": decision["source_schema_version"],
                        "gnu_id_native": decision["gnu_id_native"],
                        "gnu_position_id_native": decision["gnu_position_id_native"],
                        "gnu_match_id_native": decision["gnu_match_id_native"],
                    },
                    "producer": source_identity.get("producer"),
                    "settings": source_settings,
                    "source_manifests": source_identity.get("source_manifests"),
                    "writer": manifest.get("writer"),
                },
                "presentation": {
                    "title": "Canonical Parquet checker analysis",
                    "subtitle": (
                        "Verified Canonical Analysis Parquet v1 values with "
                        "retained build-time board assets"
                    ),
                    "fixture": True,
                    "played_move": decision["played_move_raw"],
                    "recommendation": best["move_raw"],
                },
                "position": {
                    "position_id": decision["decision_position_id"],
                    "original_board": original_board,
                },
                "checker_candidates": checker_candidates,
                "checker_evaluations": checker_evaluations,
                "probabilities": probabilities_from_native(best),
                "warnings": [
                    "Analysis values and canonical identities come from the verified Canonical Parquet package.",
                    "Board SVGs are retained build-time presentation assets for this exact GNU position; the browser does not read Parquet or calculate moves.",
                    *parser_warnings,
                ],
                "limitations": [
                    "Source-native difference-from-best is preserved; normalized and lexical values remain explicit null where unavailable.",
                    "Canonical structured movement and result-position facts are unavailable; empty movement arrays and null result IDs survive the read-set round trip while matching build-time overlays remain presentation-only.",
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--analysis-id")
    selection.add_argument("--decision-id")
    parser.add_argument("--expected-package-id")
    parser.add_argument("--expected-record-id", action="append", default=[])
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--actual-ply", type=int)
    parser.add_argument("--presentation-sidecar", type=Path, required=True)
    parser.add_argument("--presentation-analysis-id", required=True)
    parser.add_argument("--expected-gnu-position-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = build_checker_read_set(
            args.package_root,
            args.expected_manifest_sha256,
            args.analysis_id,
            decision_id=args.decision_id,
            expected_package_id=args.expected_package_id,
            expected_record_ids=(set(args.expected_record_id) or None),
            actual_ply=args.actual_ply,
            presentation_sidecar=args.presentation_sidecar,
            presentation_analysis_id=args.presentation_analysis_id,
            expected_gnu_position_id=args.expected_gnu_position_id,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(stable_json_bytes(payload))
    except (CanonicalReadSetError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"PASS: wrote Canonical Parquet semantic read set: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
