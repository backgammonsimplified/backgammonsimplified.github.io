#!/usr/bin/env python3
"""Materialize one explicit Canonical cube occurrence into the Analyzer read set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.canonical_parquet_readset import (
    CanonicalReadSetError,
    fetch_dicts,
    load_presentation,
    require_duckdb,
    stable_json_bytes,
    verify_package,
)


CUBE_SELECTION_SQL = """
            SELECT
                co.cube_occurrence_id,
                co.source_occurrence_id,
                co.game_id,
                co.position_id,
                co.block_analysis_ply,
                co.requested_cube_ply,
                co.cubeless_equity_native,
                co.cubeless_money_equity_native,
                co.native_probabilities_json,
                co.native_probabilities_lexical_json,
                co.recommendation_native,
                co.recommendation_class,
                co.observed_action_native,
                co.observed_action_class,
                co.observed_action_explicit,
                co.cube_value_displayed,

                so.dataset_id,
                so.occurrence_kind,
                so.source_family,
                so.historical_pipeline_selected,
                so.logical_opportunity_id,
                so.source_path,
                so.source_sha256,
                so.raw_block_sha256,
                so.parser_status,
                so.parser_warnings_json,
                so.source_schema_version,
                so.source_start_line,
                so.source_end_line,
                so.source_record_id,
                so.source_line,
                so.gnu_id_native,
                so.gnu_position_id_native,
                so.gnu_match_id_native,

                g.source_match_id,

                oc.play_regime,
                oc.match_length,
                oc.player_on_roll_score,
                oc.opponent_score,
                oc.cube_value,
                oc.cube_owner_relative,
                oc.crawford,
                oc.post_crawford,
                oc.jacoby,
                oc.cube_offer_pending,
                oc.perspective AS context_perspective,

                p.gnu_position_id,
                p.perspective AS position_perspective,
                p.position_encoding_version

            FROM cube_occurrences co
            JOIN source_occurrences so
              USING (source_occurrence_id)
            JOIN occurrence_contexts oc
              USING (source_occurrence_id)
            JOIN positions p
              ON p.position_id = co.position_id
            LEFT JOIN games g
              ON g.game_id = co.game_id
            WHERE so.source_record_id = ?
              AND so.occurrence_kind = 'cube_analysis'
            """

CUBE_ACTIONS_SQL = """
            SELECT
                cube_action_id,
                source_occurrence_id,
                native_rank,
                action_native,
                action_class,
                native_equity,
                native_difference,
                row_local_actual_ply,
                block_analysis_ply,
                requested_cube_ply,
                raw_source_line
            FROM cube_actions
            WHERE cube_occurrence_id = ?
            ORDER BY native_rank NULLS LAST, cube_action_id
            """


REQUIRED_TABLES = (
    "positions",
    "games",
    "source_occurrences",
    "occurrence_contexts",
    "cube_occurrences",
    "cube_actions",
)


def build_cube_read_set(
    package_root: Path,
    expected_manifest_sha256: str,
    analysis_id: str,
    *,
    expected_package_id: str | None = None,
    expected_record_ids: set[str] | None = None,
    presentation_sidecar: Path,
    presentation_analysis_id: str,
) -> dict[str, Any]:
    verified = verify_package(
        package_root,
        expected_manifest_sha256,
        expected_package_id=expected_package_id,
        expected_record_ids=expected_record_ids,
    )
    root: Path = verified["root"]
    presentation = load_presentation(presentation_sidecar, presentation_analysis_id)
    if presentation_analysis_id != analysis_id:
        raise CanonicalReadSetError(
            "Presentation analysis identity does not match accepted cube identity"
        )

    for table in REQUIRED_TABLES:
        if table not in verified["table_files"]:
            raise CanonicalReadSetError(f"Canonical package is missing {table}")

    module = require_duckdb()
    with module.connect(database=":memory:") as connection:
        for table in REQUIRED_TABLES:
            connection.read_parquet(
                [str(path) for path in verified["table_files"][table]],
                union_by_name=True,
            ).create_view(table)

        rows = fetch_dicts(
            connection,
            CUBE_SELECTION_SQL,
            (analysis_id,),
        )

        if len(rows) != 1:
            raise CanonicalReadSetError(
                f"Expected one cube row for accepted analysis {analysis_id!r}; "
                f"found {len(rows)}"
            )

        occurrence = rows[0]
        cube_occurrence_id = occurrence["cube_occurrence_id"]
        if occurrence["source_record_id"] != analysis_id:
            raise CanonicalReadSetError("Selected cube row lost accepted source identity")
        if occurrence["gnu_position_id_native"] != occurrence["gnu_position_id"]:
            raise CanonicalReadSetError(
                "Source-native and Canonical GNU Position IDs disagree"
            )
        if not occurrence["source_sha256"]:
            raise CanonicalReadSetError(
                "Selected source occurrence lacks source_sha256"
            )
        authoring = presentation.get("local_authoring")
        source_request = authoring.get("source_request") if isinstance(authoring, dict) else None
        sidecar_position = (
            source_request.get("position") if isinstance(source_request, dict) else None
        )
        if not isinstance(sidecar_position, dict) or sidecar_position.get("id") != occurrence["gnu_id_native"]:
            raise CanonicalReadSetError(
                "Presentation GNU identity does not match the accepted Canonical cube row"
            )

        actions = fetch_dicts(
            connection,
            CUBE_ACTIONS_SQL,
            (cube_occurrence_id,),
        )

    if len(actions) < 2:
        raise CanonicalReadSetError(
            "Selected cube occurrence has fewer than two actions"
        )

    cube_actions: list[dict[str, Any]] = []
    for row in actions:
        rank = row["native_rank"]
        if rank is None or rank < 1:
            raise CanonicalReadSetError(
                f"Cube action {row['cube_action_id']} lacks a positive native rank"
            )
        if not row["action_native"] or not row["action_class"]:
            raise CanonicalReadSetError(
                f"Cube action {row['cube_action_id']} lacks action identity"
            )

        details = [
            f"Source-native rank: {rank}",
            (
                "Row-local actual ply: not supplied"
                if row["row_local_actual_ply"] is None
                else f"Row-local actual ply: {row['row_local_actual_ply']}"
            ),
            f"Block analysis ply: {row['block_analysis_ply']}",
            f"Requested cube ply: {row['requested_cube_ply']}",
        ]
        if row["native_difference"] is not None:
            details.append(
                "Source-native difference: "
                f"{row['native_difference']:+.3f}"
            )

        cube_actions.append(
            {
                "action_id": row["cube_action_id"],
                "source_order": int(rank),
                "label": row["action_native"],
                "native_action": row["action_native"],
                "normalized_action": row["action_class"],
                "supported": True,
                "actual_ply": row["row_local_actual_ply"],
                "native_value": {
                    "label": "Equity",
                    "value": row["native_equity"],
                    "semantics": "Source-native cube action equity",
                },
                "normalized_value": {
                    "label": "Normalized value",
                    "value": None,
                    "semantics": (
                        "No normalized cube action value supplied by "
                        "Canonical Analysis Parquet v1"
                    ),
                },
                "display_value_source": "native",
                "probabilities": None,
                "details": "; ".join(details),
                "native_difference": row["native_difference"],
            }
        )

    manifest = verified["manifest"]
    source_identity = manifest.get("source_identity", {})
    source_settings = source_identity.get("settings", {})
    match_id = occurrence["source_match_id"] or occurrence["gnu_match_id_native"]
    try:
        native_probabilities = json.loads(occurrence["native_probabilities_json"])
        parser_warnings = json.loads(occurrence["parser_warnings_json"])
    except (TypeError, json.JSONDecodeError) as error:
        raise CanonicalReadSetError("Canonical cube JSON fields are malformed") from error
    probability_keys = {
        "win",
        "win_gammon",
        "win_backgammon",
        "lose",
        "lose_gammon",
        "lose_backgammon",
    }
    if not isinstance(native_probabilities, dict) or set(native_probabilities) != probability_keys:
        raise CanonicalReadSetError("Canonical cube probabilities have an unexpected shape")
    if not isinstance(parser_warnings, list) or not all(
        isinstance(item, str) for item in parser_warnings
    ):
        raise CanonicalReadSetError("Canonical cube parser warnings are malformed")
    probabilities = {
        "win": native_probabilities["win"],
        "win_gammon_or_better": native_probabilities["win_gammon"],
        "win_backgammon": native_probabilities["win_backgammon"],
        "lose": native_probabilities["lose"],
        "lose_gammon_or_worse": native_probabilities["lose_gammon"],
        "lose_backgammon": native_probabilities["lose_backgammon"],
    }
    original_board = presentation.get("original_board")
    responder_board = presentation.get("responder_board")
    if not isinstance(original_board, dict) or not original_board.get("image"):
        raise CanonicalReadSetError("Presentation sidecar lacks the exact cube board asset")
    if not isinstance(responder_board, dict) or not responder_board.get("image"):
        raise CanonicalReadSetError("Presentation sidecar lacks the prepared responder board")

    return {
        "schema_version": "analyzer-analysis-view-read-set-v1",
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
                "Cube values are materialized from the verified frozen "
                "Canonical Analysis Parquet v1 reference package."
            ),
        },
        "analyses": [
            {
                "analysis_id": analysis_id,
                "canonical_decision_id": cube_occurrence_id,
                "decision_kind": "cube",
                "logical_position_id": occurrence["position_id"],
                "source_occurrence": {
                    "occurrence_id": occurrence["source_occurrence_id"],
                    "source_id": occurrence["dataset_id"],
                    "source_record_id": occurrence["source_record_id"],
                    "match_id": match_id,
                    "game_id": occurrence["game_id"],
                    "line_number": occurrence["source_line"],
                    "source_start_line": occurrence["source_start_line"],
                    "source_end_line": occurrence["source_end_line"],
                    "logical_opportunity_id": occurrence["logical_opportunity_id"],
                    "historical_pipeline_selected": occurrence[
                        "historical_pipeline_selected"
                    ],
                    "gnu_position_id_native": occurrence["gnu_position_id_native"],
                    "gnu_match_id_native": occurrence["gnu_match_id_native"],
                    "source_path": occurrence["source_path"],
                },
                "context": {
                    "score": {
                        "player": occurrence["player_on_roll_score"],
                        "opponent": occurrence["opponent_score"],
                        "match_length": occurrence["match_length"],
                    },
                    "cube": {
                        "value": occurrence["cube_value"],
                        "owner": occurrence["cube_owner_relative"],
                    },
                    "dice": None,
                    "decision": "Cube decision",
                    "player_on_roll": occurrence["context_perspective"],
                },
                "requested_analysis": {
                    "requested_ply": occurrence["requested_cube_ply"],
                    "cubeful": None,
                    "profile_id": "canonical-analysis-parquet-v1",
                },
                "provenance": {
                    "engine": source_identity.get("engine", {}).get("name", "gnu"),
                    "engine_version": source_identity.get("engine", {}).get("version"),
                    "source_family": occurrence["source_family"],
                    "parser": source_settings.get("parser_identity") or "unknown",
                    "source_hash": occurrence["source_sha256"],
                },
                "canonical_provenance": {
                    "adapter": "canonical-parquet-cube-readset-v1",
                    "source": {
                        "dataset_id": occurrence["dataset_id"],
                        "source_path": occurrence["source_path"],
                        "source_record_id": occurrence["source_record_id"],
                        "raw_block_sha256": occurrence["raw_block_sha256"],
                        "parser_status": occurrence["parser_status"],
                        "parser_warnings_json": occurrence["parser_warnings_json"],
                        "source_schema_version": occurrence["source_schema_version"],
                        "gnu_id_native": occurrence["gnu_id_native"],
                        "gnu_position_id_native": occurrence["gnu_position_id_native"],
                        "gnu_match_id_native": occurrence["gnu_match_id_native"],
                    },
                    "producer": source_identity.get("producer"),
                    "settings": source_settings,
                    "source_manifests": source_identity.get("source_manifests"),
                    "writer": manifest.get("writer"),
                },
                "presentation": {
                    "title": "Canonical Parquet cube analysis",
                    "subtitle": (
                        "Real cube occurrence and analytical action rows "
                        "from Canonical Analysis Parquet v1"
                    ),
                    "fixture": True,
                    "played_move": None,
                    "recommendation": occurrence["recommendation_native"],
                },
                "position": {
                    "position_id": occurrence["position_id"],
                    "gnu_position_id": occurrence["gnu_position_id"],
                    "original_board": {
                        "image": original_board["image"],
                        "alt": original_board["alt"],
                    },
                },
                "responder_board": responder_board,
                "cube_occurrence": {
                    "cube_occurrence_id": cube_occurrence_id,
                    "observed_action_native": occurrence["observed_action_native"],
                    "observed_action_normalized": occurrence[
                        "observed_action_class"
                    ],
                    "recommendation_native": occurrence["recommendation_native"],
                    "recommendation_normalized": occurrence[
                        "recommendation_class"
                    ],
                    "block_analysis_ply": occurrence["block_analysis_ply"],
                    "requested_cube_ply": occurrence["requested_cube_ply"],
                },
                "cube_actions": cube_actions,
                "probabilities": probabilities,
                "warnings": [
                    (
                        "Cube occurrence and all displayed action equities come "
                        "from the verified Canonical Parquet package."
                    ),
                    *parser_warnings,
                ],
                "limitations": [
                    (
                        "Row-local actual ply is absent for these cube action "
                        f"rows; requested and block analysis ply remain {occurrence['requested_cube_ply']}."
                    ),
                    (
                        "Source-native cube action differences are preserved "
                        "separately and are not reinterpreted."
                    ),
                    (
                        "No normalized cube action equity is supplied by "
                        "Canonical Analysis Parquet v1."
                    ),
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--expected-package-id")
    parser.add_argument("--expected-record-id", action="append", default=[])
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--presentation-sidecar", type=Path, required=True)
    parser.add_argument("--presentation-analysis-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = build_cube_read_set(
            args.package_root,
            args.expected_manifest_sha256,
            args.analysis_id,
            expected_package_id=args.expected_package_id,
            expected_record_ids=(set(args.expected_record_id) or None),
            presentation_sidecar=args.presentation_sidecar,
            presentation_analysis_id=args.presentation_analysis_id,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(stable_json_bytes(payload))
    except (CanonicalReadSetError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        "PASS: wrote Canonical cube semantic read set: "
        f"{args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
