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


def verify_package(root: Path, expected_manifest_sha256: str) -> dict[str, Any]:
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
    decision_id: str,
    *,
    actual_ply: int | None,
    presentation_sidecar: Path,
    presentation_analysis_id: str,
    expected_gnu_position_id: str,
) -> dict[str, Any]:
    verified = verify_package(package_root, expected_manifest_sha256)
    root: Path = verified["root"]
    presentation = load_presentation(presentation_sidecar, presentation_analysis_id)

    module = require_duckdb()
    with module.connect(database=":memory:") as connection:
        for table in REQUIRED_TABLES:
            connection.read_parquet(str(root / f"{table}.parquet")).create_view(table)

        decisions = fetch_dicts(
            connection,
            """
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
            WHERE d.decision_id = ?
            """,
            (decision_id,),
        )
        if len(decisions) != 1:
            raise CanonicalReadSetError(
                f"Expected exactly one Canonical decision {decision_id!r}; "
                f"found {len(decisions)}"
            )
        decision = decisions[0]
        if decision["occurrence_kind"] != "checker_decision":
            raise CanonicalReadSetError(f"Decision {decision_id} is not a checker decision")

        observed_gnu_position_id = (
            decision["gnu_position_id_native"] or decision["gnu_position_id"]
        )
        if observed_gnu_position_id != expected_gnu_position_id:
            raise CanonicalReadSetError(
                "Presentation position identity mismatch: "
                f"expected GNU {expected_gnu_position_id}, got {observed_gnu_position_id}"
            )

        evaluations = fetch_dicts(
            connection,
            """
            SELECT
                c.candidate_id,
                c.move_raw,
                c.move_normalized,
                c.is_played,
                c.result_position_id,
                c.reconstruction_status,
                e.evaluation_id,
                e.engine,
                e.engine_version,
                e.analysis_profile_id,
                e.actual_ply,
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
                e.cubeless_money_equity_derived,
                e.cubeless_money_equity_derivation_version
            FROM candidates c
            JOIN evaluations e USING (candidate_id)
            WHERE c.decision_id = ?
            ORDER BY e.native_rank NULLS LAST, c.candidate_id, e.evaluation_id
            """,
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
    sidecar_candidates = {
        row["move"]: row
        for row in presentation.get("candidates", [])
        if isinstance(row, dict) and isinstance(row.get("move"), str)
    }

    checker_candidates = []
    checker_evaluations = []
    for row in selected_rows:
        rank = int(row["native_rank"])
        sidecar = sidecar_candidates.get(row["move_raw"], {})
        move_board = sidecar.get("move_board")
        if move_board is not None and not isinstance(move_board, dict):
            raise CanonicalReadSetError(
                f"Presentation move board for {row['move_raw']!r} is malformed"
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
                    None
                    if row["native_equity_loss_display"] is None
                    else "Source-native displayed equity loss: "
                    f"{row['native_equity_loss_display']:+.3f}; not relabeled "
                    "as canonical difference-from-best."
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
    return {
        "schema_version": READ_SET_SCHEMA,
        "package": {
            "package_id": verified["package_id"],
            "profile_id": manifest.get("candidate_version") or manifest["contract_version"],
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
                    "parser": "canonical-parquet-readset-v1",
                    "source_hash": source_hash,
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
                ],
                "limitations": [
                    "Canonical native_equity_loss_display is preserved separately and is not reinterpreted as difference-from-best.",
                    "Structured checker movement rows are not present in this Canonical package; existing verified movement-overlay SVGs are reused for matching displayed moves.",
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--decision-id", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--actual-ply", type=int)
    parser.add_argument("--presentation-sidecar", type=Path, required=True)
    parser.add_argument("--presentation-analysis-id", required=True)
    parser.add_argument("--expected-gnu-position-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = build_checker_read_set(
            args.package_root,
            args.expected_manifest_sha256,
            args.decision_id,
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
