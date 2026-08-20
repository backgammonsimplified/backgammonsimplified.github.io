#!/usr/bin/env python3
"""Materialize the commissioned Node checker/Learn cube pair from Canonical Parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis import analysis_view_materializer as materializer
from scripts.analysis.canonical_parquet_cube_readset import (
    CUBE_ACTIONS_SQL,
    CUBE_SELECTION_SQL,
    build_cube_read_set,
)
from scripts.analysis.canonical_parquet_readset import (
    CHECKER_EVALUATIONS_SQL,
    CHECKER_SELECTION_SQL,
    CanonicalReadSetError,
    build_checker_read_set,
    fetch_dicts,
    require_duckdb,
    stable_json_bytes,
    verify_package,
)


CONFIG_SCHEMA = "analyzer-accepted-node-canonical-pair-v1"
EVIDENCE_SCHEMA = "analyzer-task-008-materialization-evidence-v1"
EXCLUDED_SELECTION_SQL = """
SELECT
    so.source_occurrence_id,
    so.source_record_id,
    so.logical_opportunity_id,
    so.occurrence_kind,
    co.cube_occurrence_id,
    co.position_id
FROM source_occurrences so
JOIN cube_occurrences co USING (source_occurrence_id)
WHERE so.source_record_id = ?
  AND so.occurrence_kind = 'cube_analysis'
"""
EXCLUDED_ACTIONS_SQL = """
SELECT cube_action_id
FROM cube_actions
WHERE cube_occurrence_id = ?
ORDER BY native_rank NULLS LAST, cube_action_id
"""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def query_sha256(sql: str) -> str:
    return sha256_bytes(sql.encode("utf-8"))


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise CanonicalReadSetError(f"{path} must be a non-empty string")
    return value


def require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise CanonicalReadSetError(f"{path} must be a non-empty string array")
    if len(value) != len(set(value)):
        raise CanonicalReadSetError(f"{path} contains duplicate identities")
    return value


def resolve_repo_path(value: Any, path: str) -> Path:
    candidate = Path(require_string(value, path))
    resolved = candidate if candidate.is_absolute() else ROOT / candidate
    resolved = resolved.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as error:
        raise CanonicalReadSetError(f"{path} must remain inside the repository") from error
    return resolved


def inspect_excluded_cube(
    verified: dict[str, Any], excluded_analysis_id: str
) -> dict[str, Any]:
    module = require_duckdb()
    with module.connect(database=":memory:") as connection:
        for table in ("source_occurrences", "cube_occurrences", "cube_actions"):
            connection.read_parquet(
                [str(path) for path in verified["table_files"][table]],
                union_by_name=True,
            ).create_view(table)
        rows = fetch_dicts(connection, EXCLUDED_SELECTION_SQL, (excluded_analysis_id,))
        if len(rows) != 1:
            raise CanonicalReadSetError(
                f"Expected exactly one excluded cube {excluded_analysis_id}; found {len(rows)}"
            )
        actions = fetch_dicts(
            connection,
            EXCLUDED_ACTIONS_SQL,
            (rows[0]["cube_occurrence_id"],),
        )
    if not actions:
        raise CanonicalReadSetError("Excluded Package A cube has no canonical actions")
    return {
        **rows[0],
        "cube_action_ids": [row["cube_action_id"] for row in actions],
        "disposition": "rejected-before-materialization",
    }


def combine_documents(
    checker_document: dict[str, Any],
    cube_document: dict[str, Any],
    *,
    checker_analysis_id: str,
    cube_analysis_id: str,
    config_sha256: str,
) -> dict[str, Any]:
    analyses = {**checker_document["analyses"], **cube_document["analyses"]}
    if set(analyses) != {checker_analysis_id, cube_analysis_id}:
        raise CanonicalReadSetError("Materialized pair does not contain exactly the accepted IDs")
    return {
        "analyses": {key: analyses[key] for key in sorted(analyses)},
        "fixture_status": {
            "kind": "canonical-analysis",
            "label": "Canonical Node lesson data",
            "message": (
                "Accepted Node checker and Learn cube facts materialized from "
                "verified immutable Canonical Analysis Parquet v1 packages."
            ),
        },
        "materialization": {
            "config_sha256": config_sha256,
            "contract": materializer.READ_SET_SCHEMA,
            "deterministic_order": "accepted analysis ID; canonical source order; stable identity",
            "packages": {
                "checker": checker_document["materialization"]["package"],
                "cube": cube_document["materialization"]["package"],
            },
        },
        "schema_version": materializer.VIEWER_SCHEMA,
    }


def package_evidence(verified: dict[str, Any]) -> dict[str, Any]:
    manifest = verified["manifest"]
    return {
        "package_id": verified["package_id"],
        "manifest_sha256": verified["manifest_sha256"],
        "committed_marker": verified["committed"],
        "dataset_id": manifest["dataset_id"],
        "record_ids": verified["record_ids"],
        "relation_counts": manifest["relation_counts"],
        "relation_parts": manifest["relations"],
    }


def build(config_path: Path, checker_package: Path, cube_package: Path) -> dict[str, str]:
    config_payload = config_path.read_bytes()
    config = materializer.load_json(config_path)
    if config.get("schema_version") != CONFIG_SCHEMA:
        raise CanonicalReadSetError(f"Unsupported pair config: {config.get('schema_version')!r}")
    config_sha256 = sha256_bytes(config_payload)
    presentation = resolve_repo_path(config.get("presentation_sidecar"), "presentation_sidecar")

    checker = config.get("checker")
    cube = config.get("cube")
    outputs = config.get("outputs")
    if not all(isinstance(item, dict) for item in (checker, cube, outputs)):
        raise CanonicalReadSetError("Pair config checker, cube, and outputs must be objects")
    assert isinstance(checker, dict) and isinstance(cube, dict) and isinstance(outputs, dict)

    checker_id = require_string(checker.get("analysis_id"), "checker.analysis_id")
    cube_id = require_string(cube.get("analysis_id"), "cube.analysis_id")
    excluded_ids = require_string_list(checker.get("excluded_analysis_ids"), "checker.excluded_analysis_ids")
    if checker_id == cube_id or cube_id in excluded_ids or checker_id in excluded_ids:
        raise CanonicalReadSetError("Accepted and excluded analysis identities overlap")
    checker_records = [checker_id, *excluded_ids]
    cube_records = require_string_list(cube.get("expected_record_ids"), "cube.expected_record_ids")
    if cube_records != [cube_id]:
        raise CanonicalReadSetError("Accepted cube package must contain only the accepted Learn cube")

    checker_package_id = require_string(checker.get("package_id"), "checker.package_id")
    checker_manifest_sha = require_string(
        checker.get("manifest_sha256"), "checker.manifest_sha256"
    )
    cube_package_id = require_string(cube.get("package_id"), "cube.package_id")
    cube_manifest_sha = require_string(cube.get("manifest_sha256"), "cube.manifest_sha256")

    checker_verified = verify_package(
        checker_package,
        checker_manifest_sha,
        expected_package_id=checker_package_id,
        expected_record_ids=set(checker_records),
    )
    cube_verified = verify_package(
        cube_package,
        cube_manifest_sha,
        expected_package_id=cube_package_id,
        expected_record_ids=set(cube_records),
    )
    if checker_verified["package_id"] == cube_verified["package_id"]:
        raise CanonicalReadSetError("Checker and cube package authorities must be distinct")

    checker_read_set = build_checker_read_set(
        checker_package,
        checker_manifest_sha,
        checker_id,
        expected_package_id=checker_package_id,
        expected_record_ids=set(checker_records),
        actual_ply=None,
        presentation_sidecar=presentation,
        presentation_analysis_id=checker_id,
    )
    cube_read_set = build_cube_read_set(
        cube_package,
        cube_manifest_sha,
        cube_id,
        expected_package_id=cube_package_id,
        expected_record_ids=set(cube_records),
        presentation_sidecar=presentation,
        presentation_analysis_id=cube_id,
    )
    excluded = inspect_excluded_cube(checker_verified, excluded_ids[0])

    checker_document = materializer.materialize_document(checker_read_set)
    cube_document = materializer.materialize_document(cube_read_set)
    pair_document = combine_documents(
        checker_document,
        cube_document,
        checker_analysis_id=checker_id,
        cube_analysis_id=cube_id,
        config_sha256=config_sha256,
    )

    checker_read_bytes = stable_json_bytes(checker_read_set)
    cube_read_bytes = stable_json_bytes(cube_read_set)
    checker_view_bytes = materializer.stable_json_bytes(checker_document)
    cube_view_bytes = materializer.stable_json_bytes(cube_document)
    pair_bytes = materializer.stable_json_bytes(pair_document)
    if excluded_ids[0].encode("utf-8") in pair_bytes:
        raise CanonicalReadSetError("Excluded Package A cube entered the materialized pair")
    if checker_read_set["analyses"][0]["canonical_provenance"] != (
        checker_document["analyses"][checker_id]["canonical_context"]["provenance"]
    ):
        raise CanonicalReadSetError("Checker provenance changed during materialization")
    if cube_read_set["analyses"][0]["canonical_provenance"] != (
        cube_document["analyses"][cube_id]["canonical_context"]["provenance"]
    ):
        raise CanonicalReadSetError("Cube provenance changed during materialization")

    checker_analysis = checker_read_set["analyses"][0]
    cube_analysis = cube_read_set["analyses"][0]
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "authority": {
            "checker": package_evidence(checker_verified),
            "cube": package_evidence(cube_verified),
        },
        "config_sha256": config_sha256,
        "excluded_package_a_cube": excluded,
        "outputs": {
            "checker_read_set_sha256": sha256_bytes(checker_read_bytes),
            "checker_analysis_view_sha256": sha256_bytes(checker_view_bytes),
            "cube_read_set_sha256": sha256_bytes(cube_read_bytes),
            "cube_analysis_view_sha256": sha256_bytes(cube_view_bytes),
            "golden_pair_analysis_view_sha256": sha256_bytes(pair_bytes),
        },
        "provenance_round_trip": {
            "checker": "byte-equivalent semantic object",
            "cube": "byte-equivalent semantic object",
        },
        "query_evidence": {
            "checker_selection_sql_sha256": query_sha256(CHECKER_SELECTION_SQL),
            "checker_evaluations_sql_sha256": query_sha256(CHECKER_EVALUATIONS_SQL),
            "cube_selection_sql_sha256": query_sha256(CUBE_SELECTION_SQL),
            "cube_actions_sql_sha256": query_sha256(CUBE_ACTIONS_SQL),
            "excluded_selection_sql_sha256": query_sha256(EXCLUDED_SELECTION_SQL),
            "excluded_actions_sql_sha256": query_sha256(EXCLUDED_ACTIONS_SQL),
            "engine": "DuckDB",
            "ordering": "native rank NULLS LAST, stable canonical identity",
        },
        "selected": {
            "checker": {
                "analysis_id": checker_id,
                "decision_id": checker_analysis["canonical_decision_id"],
                "source_occurrence_id": checker_analysis["source_occurrence"]["occurrence_id"],
                "logical_position_id": checker_analysis["logical_position_id"],
                "candidate_ids": [row["candidate_id"] for row in checker_analysis["checker_candidates"]],
                "evaluation_ids": [row["evaluation_id"] for row in checker_analysis["checker_evaluations"]],
                "result_position_ids": [row["resulting_position_id"] for row in checker_analysis["checker_candidates"]],
            },
            "cube": {
                "analysis_id": cube_id,
                "cube_occurrence_id": cube_analysis["cube_occurrence"]["cube_occurrence_id"],
                "source_occurrence_id": cube_analysis["source_occurrence"]["occurrence_id"],
                "logical_position_id": cube_analysis["logical_position_id"],
                "cube_action_ids": [row["action_id"] for row in cube_analysis["cube_actions"]],
            },
        },
    }

    paths = {
        key: resolve_repo_path(outputs.get(key), f"outputs.{key}")
        for key in ("checker_read_set", "cube_read_set", "analysis_view", "evidence")
    }
    materializer.write_atomic(paths["checker_read_set"], checker_read_bytes)
    materializer.write_atomic(paths["cube_read_set"], cube_read_bytes)
    materializer.write_atomic(paths["analysis_view"], pair_bytes)
    materializer.write_atomic(paths["evidence"], materializer.stable_json_bytes(evidence))
    return {
        "checker_read_set_sha256": evidence["outputs"]["checker_read_set_sha256"],
        "cube_read_set_sha256": evidence["outputs"]["cube_read_set_sha256"],
        "golden_pair_analysis_view_sha256": evidence["outputs"]["golden_pair_analysis_view_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checker-package", type=Path, required=True)
    parser.add_argument("--cube-package", type=Path, required=True)
    args = parser.parse_args()
    try:
        hashes = build(
            args.config.resolve(),
            args.checker_package.resolve(),
            args.cube_package.resolve(),
        )
    except (CanonicalReadSetError, materializer.MaterializationError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("PASS: materialized accepted Node Canonical golden pair")
    for key, value in hashes.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
