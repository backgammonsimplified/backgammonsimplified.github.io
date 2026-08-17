#!/usr/bin/env python3
"""Deterministically materialize Analyzer semantic read sets for the Results Viewer.

This module deliberately starts after the Canonical Parquet query boundary.  The
physical Parquet-to-read-set adapter cannot be frozen until the exact Corpus
package is published and inspected.  Keeping the semantic read set explicit lets
the Analyzer materialization and validation rules be exercised without guessing
physical Canonical V1 column names.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


READ_SET_SCHEMA = "analyzer-analysis-view-read-set-v1"
VIEWER_SCHEMA = "bs-analysis-results-viewer-fixture-v1"
SUPPORTED_DECISION_KINDS = {"checker", "cube"}


class MaterializationError(ValueError):
    """Raised when an input cannot be materialized without inventing semantics."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise MaterializationError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as error:
        raise MaterializationError(f"Unable to read JSON input {path}: {error}") from error
    if not isinstance(value, dict):
        raise MaterializationError(f"{path} must contain one JSON object")
    return value


def stable_json_bytes(value: object) -> bytes:
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
        raise MaterializationError(f"Output is not stable JSON: {error}") from error


def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MaterializationError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise MaterializationError(f"{path} must be an array")
    return value


def require_keys(value: dict[str, Any], keys: tuple[str, ...], path: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise MaterializationError(
            f"{path} is missing required key(s): {', '.join(missing)}; "
            "use explicit null for known unavailable values"
        )


def require_identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MaterializationError(f"{path} must be a non-empty string")
    return value


def require_optional_number(value: Any, path: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaterializationError(f"{path} must be a number or explicit null")
    return value


def require_optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MaterializationError(f"{path} must be an integer or explicit null")
    return value


def require_optional_text(value: Any, path: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise MaterializationError(f"{path} must be text or explicit null")
    return value


def require_movement_point(value: Any, path: str) -> int | str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise MaterializationError(f"{path} must be an integer or non-empty point label")
    if isinstance(value, str) and not value.strip():
        raise MaterializationError(f"{path} must not be empty")
    return value


def format_score(score: dict[str, Any]) -> str:
    require_keys(score, ("player", "opponent", "match_length"), "context.score")
    values = (score["player"], score["opponent"], score["match_length"])
    if any(isinstance(item, bool) or not isinstance(item, int) for item in values):
        raise MaterializationError("context.score fields must be integers")
    return f"{score['player']}-{score['opponent']} to {score['match_length']}"


def format_cube(cube: dict[str, Any]) -> str:
    require_keys(cube, ("value", "owner"), "context.cube")
    if isinstance(cube["value"], bool) or not isinstance(cube["value"], int):
        raise MaterializationError("context.cube.value must be an integer")
    return f"{cube['value']}, {require_identifier(cube['owner'], 'context.cube.owner')}"


def map_probabilities(value: Any, path: str) -> dict[str, Any] | None:
    if value is None:
        return None
    source = require_object(value, path)
    keys = (
        "win",
        "win_gammon_or_better",
        "win_backgammon",
        "lose",
        "lose_gammon_or_worse",
        "lose_backgammon",
    )
    require_keys(source, keys, path)
    return {
        key: require_optional_number(source[key], f"{path}.{key}") for key in keys
    }


def map_value(value: Any, path: str) -> dict[str, Any]:
    source = require_object(value, path)
    require_keys(source, ("label", "value", "semantics"), path)
    return {
        "label": require_identifier(source["label"], f"{path}.label"),
        "value": require_optional_number(source["value"], f"{path}.value"),
        "semantics": require_identifier(source["semantics"], f"{path}.semantics"),
    }


def map_board(value: Any, path: str) -> dict[str, str] | None:
    if value is None:
        return None
    board = require_object(value, path)
    require_keys(board, ("image", "alt"), path)
    return {
        "image": require_identifier(board["image"], f"{path}.image"),
        "alt": require_identifier(board["alt"], f"{path}.alt"),
    }


def validate_common_analysis(source: dict[str, Any], path: str) -> None:
    require_keys(
        source,
        (
            "canonical_decision_id",
            "decision_kind",
            "logical_position_id",
            "source_occurrence",
            "context",
            "requested_analysis",
            "provenance",
            "presentation",
            "position",
            "warnings",
            "limitations",
        ),
        path,
    )
    require_identifier(source["canonical_decision_id"], f"{path}.canonical_decision_id")
    if source["decision_kind"] not in SUPPORTED_DECISION_KINDS:
        raise MaterializationError(f"{path}.decision_kind is unsupported")
    require_identifier(source["logical_position_id"], f"{path}.logical_position_id")

    occurrence = require_object(source["source_occurrence"], f"{path}.source_occurrence")
    require_keys(
        occurrence,
        ("occurrence_id", "source_id", "source_record_id", "match_id", "game_id", "line_number"),
        f"{path}.source_occurrence",
    )
    for key in ("occurrence_id", "source_id"):
        require_identifier(occurrence[key], f"{path}.source_occurrence.{key}")
    for key in ("source_record_id", "match_id", "game_id"):
        require_optional_text(occurrence[key], f"{path}.source_occurrence.{key}")
    require_optional_integer(occurrence["line_number"], f"{path}.source_occurrence.line_number")

    context = require_object(source["context"], f"{path}.context")
    require_keys(context, ("score", "cube", "dice", "decision", "player_on_roll"), f"{path}.context")
    format_score(require_object(context["score"], f"{path}.context.score"))
    format_cube(require_object(context["cube"], f"{path}.context.cube"))
    dice = context["dice"]
    if dice is not None:
        dice_values = require_list(dice, f"{path}.context.dice")
        if any(isinstance(item, bool) or not isinstance(item, int) for item in dice_values):
            raise MaterializationError(f"{path}.context.dice must contain integers or be null")
    require_identifier(context["decision"], f"{path}.context.decision")
    require_identifier(context["player_on_roll"], f"{path}.context.player_on_roll")

    requested = require_object(source["requested_analysis"], f"{path}.requested_analysis")
    require_keys(requested, ("requested_ply", "cubeful", "profile_id"), f"{path}.requested_analysis")
    require_optional_integer(requested["requested_ply"], f"{path}.requested_analysis.requested_ply")
    if requested["cubeful"] is not None and not isinstance(requested["cubeful"], bool):
        raise MaterializationError(f"{path}.requested_analysis.cubeful must be boolean or null")
    require_identifier(requested["profile_id"], f"{path}.requested_analysis.profile_id")

    provenance = require_object(source["provenance"], f"{path}.provenance")
    require_keys(
        provenance,
        ("engine", "engine_version", "source_family", "parser", "source_hash"),
        f"{path}.provenance",
    )
    for key in ("engine", "source_family", "parser", "source_hash"):
        require_identifier(provenance[key], f"{path}.provenance.{key}")
    require_optional_text(provenance["engine_version"], f"{path}.provenance.engine_version")

    presentation = require_object(source["presentation"], f"{path}.presentation")
    require_keys(presentation, ("title", "subtitle", "fixture", "played_move", "recommendation"), f"{path}.presentation")
    require_identifier(presentation["title"], f"{path}.presentation.title")
    require_identifier(presentation["subtitle"], f"{path}.presentation.subtitle")
    if presentation["fixture"] is not True:
        raise MaterializationError(
            f"{path}.presentation.fixture must be true until the production viewer contract is published"
        )
    require_optional_text(presentation["played_move"], f"{path}.presentation.played_move")
    require_optional_text(presentation["recommendation"], f"{path}.presentation.recommendation")

    position = require_object(source["position"], f"{path}.position")
    require_keys(position, ("position_id", "original_board"), f"{path}.position")
    if position["position_id"] != source["logical_position_id"]:
        raise MaterializationError(f"{path} logical and displayed position identities differ")
    map_board(position["original_board"], f"{path}.position.original_board")
    for key in ("warnings", "limitations"):
        values = require_list(source[key], f"{path}.{key}")
        for index, value in enumerate(values):
            require_identifier(value, f"{path}.{key}[{index}]")


def map_evaluation(source: dict[str, Any], path: str) -> dict[str, Any]:
    require_keys(
        source,
        (
            "evaluation_id",
            "candidate_id",
            "source_order",
            "selected_for_display",
            "evaluation_type",
            "actual_ply",
            "native_value",
            "normalized_value",
            "display_value_source",
            "difference_from_best",
            "probabilities",
        ),
        path,
    )
    display_source = source["display_value_source"]
    if display_source not in {"native", "normalized"}:
        raise MaterializationError(f"{path}.display_value_source must be native or normalized")
    source_order = require_optional_integer(source["source_order"], f"{path}.source_order")
    if source_order is None or source_order < 1:
        raise MaterializationError(f"{path}.source_order must be a positive integer")
    if not isinstance(source["selected_for_display"], bool):
        raise MaterializationError(f"{path}.selected_for_display must be boolean")
    return {
        "actual_ply": require_optional_integer(source["actual_ply"], f"{path}.actual_ply"),
        "candidate_id": require_identifier(source["candidate_id"], f"{path}.candidate_id"),
        "difference_from_best": require_optional_number(
            source["difference_from_best"], f"{path}.difference_from_best"
        ),
        "native_equity_loss_display": require_optional_number(
            source.get("native_equity_loss_display"),
            f"{path}.native_equity_loss_display",
        ),
        "display_value_source": display_source,
        "evaluation_id": require_identifier(source["evaluation_id"], f"{path}.evaluation_id"),
        "evaluation_type": require_identifier(source["evaluation_type"], f"{path}.evaluation_type"),
        "native_value": map_value(source["native_value"], f"{path}.native_value"),
        "normalized_value": map_value(source["normalized_value"], f"{path}.normalized_value"),
        "probabilities": map_probabilities(source["probabilities"], f"{path}.probabilities"),
        "selected_for_display": source["selected_for_display"],
        "source_order": source_order,
    }


def map_checker(source: dict[str, Any], path: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    require_keys(source, ("checker_candidates", "checker_evaluations", "probabilities"), path)
    candidate_rows = require_list(source["checker_candidates"], f"{path}.checker_candidates")
    evaluation_rows = require_list(source["checker_evaluations"], f"{path}.checker_evaluations")
    if not candidate_rows:
        raise MaterializationError(f"{path}.checker_candidates must not be empty")

    candidates_by_id: dict[str, dict[str, Any]] = {}
    candidate_orders: set[int] = set()
    for index, item in enumerate(candidate_rows):
        item_path = f"{path}.checker_candidates[{index}]"
        candidate = require_object(item, item_path)
        require_keys(
            candidate,
            (
                "candidate_id",
                "source_order",
                "display_rank",
                "native_move",
                "normalized_move",
                "structured_movements",
                "resulting_position_id",
                "move_board",
                "supported",
                "details",
            ),
            item_path,
        )
        candidate_id = require_identifier(candidate["candidate_id"], f"{item_path}.candidate_id")
        if candidate_id in candidates_by_id:
            raise MaterializationError(f"Duplicate checker candidate ID: {candidate_id}")
        order = require_optional_integer(candidate["source_order"], f"{item_path}.source_order")
        rank = require_optional_integer(candidate["display_rank"], f"{item_path}.display_rank")
        if order is None or order < 1 or order in candidate_orders:
            raise MaterializationError(f"{item_path}.source_order must be unique and positive")
        if rank is not None and rank < 1:
            raise MaterializationError(f"{item_path}.display_rank must be positive or null")
        candidate_orders.add(order)
        movements = require_list(candidate["structured_movements"], f"{item_path}.structured_movements")
        mapped_movements = []
        movement_orders: set[int] = set()
        for movement_index, movement_value in enumerate(movements):
            movement_path = f"{item_path}.structured_movements[{movement_index}]"
            movement = require_object(movement_value, movement_path)
            require_keys(movement, ("order", "from", "to", "die"), movement_path)
            movement_order = require_optional_integer(movement["order"], f"{movement_path}.order")
            if movement_order is None or movement_order < 1 or movement_order in movement_orders:
                raise MaterializationError(f"{movement_path}.order must be unique and positive")
            movement_orders.add(movement_order)
            mapped_movements.append(
                {
                    "die": require_optional_integer(movement["die"], f"{movement_path}.die"),
                    "from": require_movement_point(movement["from"], f"{movement_path}.from"),
                    "order": movement_order,
                    "to": require_movement_point(movement["to"], f"{movement_path}.to"),
                }
            )
        if not isinstance(candidate["supported"], bool):
            raise MaterializationError(f"{item_path}.supported must be boolean")
        candidates_by_id[candidate_id] = {
            "details": require_optional_text(candidate["details"], f"{item_path}.details"),
            "display_rank": rank,
            "id": candidate_id,
            "move": require_identifier(candidate["native_move"], f"{item_path}.native_move"),
            "move_board": map_board(candidate["move_board"], f"{item_path}.move_board"),
            "normalized_move": require_optional_text(candidate["normalized_move"], f"{item_path}.normalized_move"),
            "resulting_position_id": require_optional_text(
                candidate["resulting_position_id"], f"{item_path}.resulting_position_id"
            ),
            "source_order": order,
            "structured_movements": sorted(mapped_movements, key=lambda item: item["order"]),
            "supported": candidate["supported"],
        }

    evaluations_by_candidate: dict[str, list[dict[str, Any]]] = {
        candidate_id: [] for candidate_id in candidates_by_id
    }
    evaluation_ids: set[str] = set()
    for index, item in enumerate(evaluation_rows):
        item_path = f"{path}.checker_evaluations[{index}]"
        evaluation = map_evaluation(require_object(item, item_path), item_path)
        if evaluation["evaluation_id"] in evaluation_ids:
            raise MaterializationError(f"Duplicate evaluation ID: {evaluation['evaluation_id']}")
        evaluation_ids.add(evaluation["evaluation_id"])
        if evaluation["candidate_id"] not in evaluations_by_candidate:
            raise MaterializationError(
                f"{item_path} refers to unknown candidate {evaluation['candidate_id']}"
            )
        evaluations_by_candidate[evaluation["candidate_id"]].append(evaluation)

    output: list[dict[str, Any]] = []
    for candidate_id, candidate in sorted(
        candidates_by_id.items(), key=lambda item: (item[1]["source_order"], item[0])
    ):
        evaluations = sorted(
            evaluations_by_candidate[candidate_id],
            key=lambda item: (item["source_order"], item["evaluation_id"]),
        )
        selected = [item for item in evaluations if item["selected_for_display"]]
        if len(selected) != 1:
            raise MaterializationError(
                f"Candidate {candidate_id} must have exactly one selected display evaluation"
            )
        display = selected[0]
        displayed_value = display[
            "native_value" if display["display_value_source"] == "native" else "normalized_value"
        ]
        output.append(
            {
                **candidate,
                "actual_ply": display["actual_ply"],
                "difference_from_best": display["difference_from_best"],
                "native_equity_loss_display": display["native_equity_loss_display"],
                "evaluation": display["evaluation_type"],
                "evaluations": evaluations,
                "probabilities": display["probabilities"],
                "value": {"label": displayed_value["label"], "value": displayed_value["value"]},
                "values": {
                    "native": display["native_value"],
                    "normalized": display["normalized_value"],
                },
            }
        )
    return output, map_probabilities(source["probabilities"], f"{path}.probabilities")


def map_cube(source: dict[str, Any], path: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any]]:
    require_keys(source, ("cube_occurrence", "cube_actions", "probabilities"), path)
    occurrence = require_object(source["cube_occurrence"], f"{path}.cube_occurrence")
    require_keys(
        occurrence,
        ("cube_occurrence_id", "observed_action_native", "observed_action_normalized"),
        f"{path}.cube_occurrence",
    )
    mapped_occurrence = {
        "cube_occurrence_id": require_identifier(
            occurrence["cube_occurrence_id"], f"{path}.cube_occurrence.cube_occurrence_id"
        ),
        "observed_action_native": require_optional_text(
            occurrence["observed_action_native"], f"{path}.cube_occurrence.observed_action_native"
        ),
        "observed_action_normalized": require_optional_text(
            occurrence["observed_action_normalized"], f"{path}.cube_occurrence.observed_action_normalized"
        ),
        "recommendation_native": require_optional_text(
            occurrence.get("recommendation_native"),
            f"{path}.cube_occurrence.recommendation_native",
        ),
        "recommendation_normalized": require_optional_text(
            occurrence.get("recommendation_normalized"),
            f"{path}.cube_occurrence.recommendation_normalized",
        ),
        "block_analysis_ply": require_optional_integer(
            occurrence.get("block_analysis_ply"),
            f"{path}.cube_occurrence.block_analysis_ply",
        ),
        "requested_cube_ply": require_optional_integer(
            occurrence.get("requested_cube_ply"),
            f"{path}.cube_occurrence.requested_cube_ply",
        ),
    }
    rows = require_list(source["cube_actions"], f"{path}.cube_actions")
    if not rows:
        raise MaterializationError(f"{path}.cube_actions must not be empty")
    actions: list[dict[str, Any]] = []
    ids: set[str] = set()
    orders: set[int] = set()
    for index, item in enumerate(rows):
        item_path = f"{path}.cube_actions[{index}]"
        action = require_object(item, item_path)
        require_keys(
            action,
            (
                "action_id",
                "source_order",
                "label",
                "native_action",
                "normalized_action",
                "supported",
                "actual_ply",
                "native_value",
                "normalized_value",
                "display_value_source",
                "probabilities",
                "details",
            ),
            item_path,
        )
        action_id = require_identifier(action["action_id"], f"{item_path}.action_id")
        order = require_optional_integer(action["source_order"], f"{item_path}.source_order")
        if action_id in ids or order is None or order < 1 or order in orders:
            raise MaterializationError(f"{item_path} action identity/order is duplicate or invalid")
        ids.add(action_id)
        orders.add(order)
        if not isinstance(action["supported"], bool):
            raise MaterializationError(f"{item_path}.supported must be boolean")
        display_source = action["display_value_source"]
        if display_source not in {"native", "normalized"}:
            raise MaterializationError(f"{item_path}.display_value_source must be native or normalized")
        native = map_value(action["native_value"], f"{item_path}.native_value")
        normalized = map_value(action["normalized_value"], f"{item_path}.normalized_value")
        display = native if display_source == "native" else normalized
        actions.append(
            {
                "actual_ply": require_optional_integer(action["actual_ply"], f"{item_path}.actual_ply"),
                "details": require_optional_text(action["details"], f"{item_path}.details"),
                "id": action_id,
                "label": require_identifier(action["label"], f"{item_path}.label"),
                "native_action": require_identifier(action["native_action"], f"{item_path}.native_action"),
                "native_difference": require_optional_number(
                    action.get("native_difference"),
                    f"{item_path}.native_difference",
                ),
                "normalized_action": require_identifier(
                    action["normalized_action"], f"{item_path}.normalized_action"
                ),
                "probabilities": map_probabilities(action["probabilities"], f"{item_path}.probabilities"),
                "source_order": order,
                "supported": action["supported"],
                "value": {"label": display["label"], "value": display["value"]},
                "values": {"native": native, "normalized": normalized},
            }
        )
    return (
        sorted(actions, key=lambda item: (item["source_order"], item["id"])),
        map_probabilities(source["probabilities"], f"{path}.probabilities"),
        mapped_occurrence,
    )


def materialize_analysis(source: dict[str, Any], package: dict[str, Any], path: str) -> dict[str, Any]:
    validate_common_analysis(source, path)
    decision_id = source["canonical_decision_id"]
    context = source["context"]
    occurrence = source["source_occurrence"]
    requested = source["requested_analysis"]
    provenance = source["provenance"]
    presentation = source["presentation"]
    original_board = map_board(source["position"]["original_board"], f"{path}.position.original_board")
    assert original_board is not None

    analysis: dict[str, Any] = {
        "analysis_kind": source["decision_kind"],
        "canonical_context": {
            "logical_position_id": source["logical_position_id"],
            "package": package,
            "requested_analysis": requested,
            "source_occurrence": occurrence,
            "state": context,
        },
        "context": {
            "cube": format_cube(context["cube"]),
            "decision": context["decision"],
            "dice": None if context["dice"] is None else "-".join(str(item) for item in context["dice"]),
            "score": format_score(context["score"]),
        },
        "fixture": True,
        "id": decision_id,
        "limitations": source["limitations"],
        "metadata": {
            "analysis_settings": {
                "effective": "Row-local actual depth is retained on each evaluation/action",
                "requested": (
                    f"Requested {requested['requested_ply']}-ply"
                    if requested["requested_ply"] is not None
                    else "Requested ply not supplied"
                ),
            },
            "engine": provenance["engine"],
            "engine_version": provenance["engine_version"],
            "parser": provenance["parser"],
            "played_move": presentation["played_move"],
            "provenance": (
                f"package {package['package_id']}; occurrence {occurrence['occurrence_id']}; "
                f"source hash {provenance['source_hash']}"
            ),
            "recommendation": presentation["recommendation"],
            "source_family": provenance["source_family"],
        },
        "original_board": original_board,
        "subtitle": presentation["subtitle"],
        "title": presentation["title"],
        "warnings": source["warnings"],
    }
    if source["decision_kind"] == "checker":
        candidates, probabilities = map_checker(source, path)
        analysis["candidates"] = candidates
        analysis["probabilities"] = probabilities
    else:
        actions, probabilities, cube_occurrence = map_cube(source, path)
        analysis["actions"] = actions
        analysis["cube_occurrence"] = cube_occurrence
        analysis["probabilities"] = probabilities
    return analysis


def validate_package(package: Any) -> dict[str, Any]:
    value = require_object(package, "package")
    require_keys(
        value,
        ("package_id", "profile_id", "manifest_sha256", "conformance_status"),
        "package",
    )
    for key in ("package_id", "profile_id", "conformance_status"):
        require_identifier(value[key], f"package.{key}")
    require_optional_text(value["manifest_sha256"], "package.manifest_sha256")
    if value["conformance_status"] not in {"synthetic-minimal", "verified-canonical-v1"}:
        raise MaterializationError("package.conformance_status is unsupported")
    if value["conformance_status"] == "verified-canonical-v1" and value["manifest_sha256"] is None:
        raise MaterializationError("Verified Canonical V1 input requires a manifest SHA-256")
    return {
        "conformance_status": value["conformance_status"],
        "manifest_sha256": value["manifest_sha256"],
        "package_id": value["package_id"],
        "profile_id": value["profile_id"],
    }


def materialize_document(read_set: dict[str, Any]) -> dict[str, Any]:
    require_keys(read_set, ("schema_version", "package", "fixture_status", "analyses"), "read_set")
    if read_set["schema_version"] != READ_SET_SCHEMA:
        raise MaterializationError(f"Unsupported read-set schema: {read_set['schema_version']!r}")
    package = validate_package(read_set["package"])
    fixture_status = require_object(read_set["fixture_status"], "fixture_status")
    require_keys(fixture_status, ("kind", "label", "message"), "fixture_status")
    if fixture_status["kind"] not in {
        "synthetic",
        "retained-analysis",
        "canonical-analysis",
    }:
        raise MaterializationError(
            "fixture_status.kind is not compatible with the current viewer"
        )
    for key in ("label", "message"):
        require_identifier(fixture_status[key], f"fixture_status.{key}")
    rows = require_list(read_set["analyses"], "analyses")
    if not rows:
        raise MaterializationError("analyses must not be empty")
    analyses: dict[str, Any] = {}
    for index, item in enumerate(rows):
        path = f"analyses[{index}]"
        source = require_object(item, path)
        analysis = materialize_analysis(source, package, path)
        if analysis["id"] in analyses:
            raise MaterializationError(f"Duplicate canonical decision ID: {analysis['id']}")
        analyses[analysis["id"]] = analysis
    return {
        "analyses": {key: analyses[key] for key in sorted(analyses)},
        "fixture_status": {
            "kind": fixture_status["kind"],
            "label": fixture_status["label"],
            "message": fixture_status["message"],
        },
        "materialization": {
            "contract": READ_SET_SCHEMA,
            "deterministic_order": "canonical decision ID; source order; stable identity",
            "package": package,
        },
        "schema_version": VIEWER_SCHEMA,
    }


def materialize_subset(read_set: dict[str, Any], decision_ids: list[str]) -> dict[str, Any]:
    selected = set(decision_ids)
    subset = dict(read_set)
    subset["analyses"] = [
        item for item in require_list(read_set.get("analyses"), "analyses")
        if isinstance(item, dict) and item.get("canonical_decision_id") in selected
    ]
    if len(subset["analyses"]) != len(selected):
        found = {item.get("canonical_decision_id") for item in subset["analyses"]}
        raise MaterializationError(f"Unknown canonical decision ID(s): {sorted(selected - found)}")
    return materialize_document(subset)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("read_set", type=Path, help="semantic Analyzer read-set JSON")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--decision-id", action="append", default=[])
    parser.add_argument("--verify-repeat", action="store_true")
    args = parser.parse_args()
    try:
        read_set = load_json(args.read_set.resolve())
        result = (
            materialize_subset(read_set, args.decision_id)
            if args.decision_id
            else materialize_document(read_set)
        )
        payload = stable_json_bytes(result)
        if args.verify_repeat:
            repeated = stable_json_bytes(
                materialize_subset(read_set, args.decision_id)
                if args.decision_id
                else materialize_document(read_set)
            )
            if payload != repeated:
                raise MaterializationError("Repeat materialization was not byte-identical")
        write_atomic(args.output.resolve(), payload)
    except MaterializationError as error:
        print(f"ERROR: {error}", file=__import__("sys").stderr)
        return 1
    print(f"PASS: wrote deterministic analysis-view JSON: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
