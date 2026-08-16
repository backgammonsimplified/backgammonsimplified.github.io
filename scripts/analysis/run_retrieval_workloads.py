#!/usr/bin/env python3
"""Run the Analyzer retrieval/materializer workload registry reproducibly.

The currently executable driver consumes the explicit semantic read-set used by
the materializer.  It proves workload selection, ordering, transfer validation,
measurement envelopes, and deterministic materialization without pretending
that JSON proof runs are DuckDB/Parquet measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.analysis.analysis_view_materializer import (
        MaterializationError,
        load_json,
        materialize_document,
        materialize_subset,
        stable_json_bytes,
        validate_package,
    )
except ModuleNotFoundError:  # Direct execution from scripts/analysis.
    from analysis_view_materializer import (  # type: ignore
        MaterializationError,
        load_json,
        materialize_document,
        materialize_subset,
        stable_json_bytes,
        validate_package,
    )


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "scripts" / "analysis" / "retrieval_workloads_v1.json"
REPORT_SCHEMA = "analyzer-retrieval-workload-report-v1"
EXPECTED_IDS = tuple(f"AVR-{number:03d}" for number in range(1, 16))


class WorkloadError(ValueError):
    """Raised when workload meaning or input identity is incomplete."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unavailable(reason: str) -> dict[str, str]:
    return {"status": "unavailable", "reason": reason}


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    document = load_json(path)
    if document.get("schema_version") != "analyzer-retrieval-workload-registry-v1":
        raise WorkloadError("Unsupported workload registry schema")
    rows = document.get("workloads")
    if not isinstance(rows, list):
        raise WorkloadError("Workload registry must contain a workloads array")
    registry: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(("id", "name", "query")) - set(row):
            raise WorkloadError("Malformed workload registry row")
        workload_id = row["id"]
        if workload_id in registry:
            raise WorkloadError(f"Duplicate workload ID: {workload_id}")
        query_bytes = stable_json_bytes(row["query"])
        registry[workload_id] = {
            **row,
            "query_sha256": sha256_bytes(query_bytes),
        }
    if tuple(sorted(registry)) != EXPECTED_IDS:
        raise WorkloadError("Registry must define AVR-001 through AVR-015 exactly once")
    return registry


@dataclass(frozen=True)
class Selection:
    checker_decision_id: str
    cube_decision_id: str
    decision_id: str
    resulting_position_id: str
    actual_ply: int


def analyses(read_set: dict[str, Any]) -> list[dict[str, Any]]:
    rows = read_set.get("analyses")
    if not isinstance(rows, list):
        raise WorkloadError("Read set must contain an analyses array")
    return sorted(rows, key=lambda row: row.get("canonical_decision_id", ""))


def select_inputs(read_set: dict[str, Any]) -> Selection:
    rows = analyses(read_set)
    checkers = [row for row in rows if row.get("decision_kind") == "checker"]
    cubes = [row for row in rows if row.get("decision_kind") == "cube"]
    if not checkers or not cubes:
        raise WorkloadError("Workload proof requires at least one checker and one cube decision")
    checker = checkers[0]
    candidates = sorted(
        checker.get("checker_candidates", []),
        key=lambda row: (row.get("source_order", 0), row.get("candidate_id", "")),
    )
    resulting = next(
        (row.get("resulting_position_id") for row in candidates if row.get("resulting_position_id")),
        None,
    )
    evaluations = checker.get("checker_evaluations", [])
    actual = next(
        (row.get("actual_ply") for row in evaluations if isinstance(row.get("actual_ply"), int)),
        None,
    )
    if not resulting or actual is None:
        raise WorkloadError("Checker proof data needs a resulting position and observable actual ply")
    return Selection(
        checker_decision_id=checker["canonical_decision_id"],
        cube_decision_id=cubes[0]["canonical_decision_id"],
        decision_id=checker["canonical_decision_id"],
        resulting_position_id=resulting,
        actual_ply=actual,
    )


def decision_by_id(read_set: dict[str, Any], decision_id: str) -> list[dict[str, Any]]:
    return [row for row in analyses(read_set) if row.get("canonical_decision_id") == decision_id]


def checker_join(read_set: dict[str, Any], decision_id: str) -> list[dict[str, Any]]:
    matches = decision_by_id(read_set, decision_id)
    if len(matches) != 1 or matches[0].get("decision_kind") != "checker":
        raise WorkloadError(f"Unknown checker decision: {decision_id}")
    decision = matches[0]
    candidates = {
        row["candidate_id"]: row for row in decision["checker_candidates"]
    }
    rows = []
    for evaluation in decision["checker_evaluations"]:
        candidate = candidates.get(evaluation["candidate_id"])
        if candidate is None:
            raise WorkloadError("Checker evaluation refers to an unknown candidate")
        rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_source_order": candidate["source_order"],
                "canonical_decision_id": decision_id,
                "evaluation_id": evaluation["evaluation_id"],
                "evaluation_source_order": evaluation["source_order"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["canonical_decision_id"],
            row["candidate_source_order"],
            row["evaluation_source_order"],
            row["evaluation_id"],
        ),
    )


def sibling_candidates(read_set: dict[str, Any], decision_id: str) -> list[dict[str, Any]]:
    decision = decision_by_id(read_set, decision_id)
    if len(decision) != 1:
        raise WorkloadError(f"Unknown decision: {decision_id}")
    return sorted(
        decision[0].get("checker_candidates", []),
        key=lambda row: (row["source_order"], row["candidate_id"]),
    )


def resulting_position_lookup(read_set: dict[str, Any], position_id: str) -> list[dict[str, Any]]:
    result = []
    for decision in analyses(read_set):
        for candidate in decision.get("checker_candidates", []):
            if candidate.get("resulting_position_id") == position_id:
                result.append(
                    {
                        "candidate_id": candidate["candidate_id"],
                        "candidate_source_order": candidate["source_order"],
                        "canonical_decision_id": decision["canonical_decision_id"],
                        "resulting_position_id": position_id,
                    }
                )
    return sorted(
        result,
        key=lambda row: (
            row["canonical_decision_id"],
            row["candidate_source_order"],
            row["candidate_id"],
        ),
    )


def occurrence_context(read_set: dict[str, Any], decision_id: str) -> list[dict[str, Any]]:
    return [
        {
            "canonical_decision_id": row["canonical_decision_id"],
            "context": row["context"],
            "logical_position_id": row["logical_position_id"],
            "source_occurrence": row["source_occurrence"],
        }
        for row in decision_by_id(read_set, decision_id)
    ]


def cube_join(read_set: dict[str, Any], decision_id: str) -> list[dict[str, Any]]:
    decision = decision_by_id(read_set, decision_id)
    if len(decision) != 1 or decision[0].get("decision_kind") != "cube":
        raise WorkloadError(f"Unknown cube decision: {decision_id}")
    occurrence = decision[0]["cube_occurrence"]
    return [
        {"cube_occurrence": occurrence, "action": action}
        for action in sorted(
            decision[0]["cube_actions"],
            key=lambda row: (row["source_order"], row["action_id"]),
        )
    ]


def depth_rows(read_set: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for decision in analyses(read_set):
        requested = decision["requested_analysis"]["requested_ply"]
        for candidate in sorted(
            decision.get("checker_candidates", []),
            key=lambda row: (row["source_order"], row["candidate_id"]),
        ):
            evaluations = [
                row
                for row in decision.get("checker_evaluations", [])
                if row["candidate_id"] == candidate["candidate_id"]
            ]
            for evaluation in sorted(
                evaluations, key=lambda row: (row["source_order"], row["evaluation_id"])
            ):
                result.append(
                    {
                        "actual_ply": evaluation["actual_ply"],
                        "candidate_id": candidate["candidate_id"],
                        "candidate_source_order": candidate["source_order"],
                        "canonical_decision_id": decision["canonical_decision_id"],
                        "evaluation_id": evaluation["evaluation_id"],
                        "evaluation_source_order": evaluation["source_order"],
                        "requested_ply": requested,
                    }
                )
    return result


def seeded_results(read_set: dict[str, Any], seed: int, sample_size: int) -> list[dict[str, Any]]:
    population = []
    for decision in analyses(read_set):
        decision_id = decision["canonical_decision_id"]
        population.extend(
            {
                "canonical_decision_id": decision_id,
                "result_id": row["candidate_id"],
                "result_kind": "checker_candidate",
            }
            for row in sorted(
                decision.get("checker_candidates", []),
                key=lambda item: (item["source_order"], item["candidate_id"]),
            )
        )
        population.extend(
            {
                "canonical_decision_id": decision_id,
                "result_id": row["action_id"],
                "result_kind": "cube_action",
            }
            for row in sorted(
                decision.get("cube_actions", []),
                key=lambda item: (item["source_order"], item["action_id"]),
            )
        )
    count = min(sample_size, len(population))
    indices = random.Random(seed).sample(range(len(population)), count)
    return [{"sample_sequence": sequence + 1, **population[index]} for sequence, index in enumerate(indices)]


def execute_semantics(
    workload_id: str,
    read_set: dict[str, Any],
    selection: Selection,
    *,
    seed: int,
    sample_size: int,
    batch_repetitions: int,
) -> tuple[list[Any], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if workload_id == "AVR-001":
        result = decision_by_id(read_set, selection.decision_id)
    elif workload_id == "AVR-002":
        result = checker_join(read_set, selection.checker_decision_id)
    elif workload_id == "AVR-003":
        result = sibling_candidates(read_set, selection.checker_decision_id)
    elif workload_id == "AVR-004":
        result = resulting_position_lookup(read_set, selection.resulting_position_id)
    elif workload_id == "AVR-005":
        result = occurrence_context(read_set, selection.decision_id)
    elif workload_id == "AVR-006":
        result = cube_join(read_set, selection.cube_decision_id)
    elif workload_id == "AVR-007":
        result = depth_rows(read_set)
    elif workload_id == "AVR-008":
        result = [row for row in depth_rows(read_set) if row["actual_ply"] == selection.actual_ply]
    elif workload_id == "AVR-009":
        result = [materialize_subset(read_set, [selection.decision_id])]
    elif workload_id == "AVR-010":
        result = [materialize_document(read_set)]
    elif workload_id == "AVR-011":
        result = seeded_results(read_set, seed, sample_size)
    elif workload_id == "AVR-015":
        result = [materialize_document(read_set) for _ in range(batch_repetitions)]
        metadata["materialized_analysis_count"] = sum(
            len(item["analyses"]) for item in result
        )
    else:
        raise WorkloadError(f"{workload_id} requires its transfer/process executor")
    return result, metadata


def cpu_seconds() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


def peak_rss_bytes() -> int:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    multiplier = 1024 if sys.platform.startswith("linux") else 1
    return int(usage.ru_maxrss * multiplier)


def measure(call: Callable[[], tuple[list[Any], dict[str, Any]]]) -> tuple[list[Any], dict[str, Any]]:
    cpu_start = cpu_seconds()
    start = time.perf_counter_ns()
    rows, metadata = call()
    elapsed_ns = time.perf_counter_ns() - start
    cpu_elapsed = cpu_seconds() - cpu_start
    count = metadata.get("materialized_analysis_count", len(rows))
    return rows, {
        **metadata,
        "cpu_seconds": round(cpu_elapsed, 9),
        "latency_ms": round(elapsed_ns / 1_000_000, 6),
        "peak_rss_bytes": peak_rss_bytes(),
        "returned_count": count,
        "throughput_per_second": round(count / (elapsed_ns / 1_000_000_000), 6)
        if elapsed_ns and count
        else 0.0,
    }


def resolved_inputs(workload_id: str, selection: Selection, seed: int, sample_size: int, batch_repetitions: int) -> dict[str, Any]:
    if workload_id in {"AVR-001", "AVR-005", "AVR-009", "AVR-012", "AVR-013", "AVR-014"}:
        return {"canonical_decision_id": selection.decision_id}
    if workload_id in {"AVR-002", "AVR-003"}:
        return {"canonical_checker_decision_id": selection.checker_decision_id}
    if workload_id == "AVR-004":
        return {"resulting_position_id": selection.resulting_position_id}
    if workload_id == "AVR-006":
        return {"canonical_cube_decision_id": selection.cube_decision_id}
    if workload_id == "AVR-008":
        return {"actual_ply": selection.actual_ply}
    if workload_id == "AVR-011":
        return {"sample_size": sample_size, "seed": seed}
    if workload_id == "AVR-015":
        return {"batch_repetitions": batch_repetitions}
    return {}


def normal_observations(profile_path: Path) -> dict[str, Any]:
    return {
        "bytes_scanned": unavailable("semantic JSON driver does not expose physical scan bytes"),
        "files_touched": [str(profile_path)],
        "partitions_touched": unavailable("semantic JSON proof input is not partitioned Parquet"),
        "pruning_evidence": unavailable("no Parquet/DuckDB execution in this proof driver"),
        "row_groups_touched": unavailable("semantic JSON proof input has no Parquet row groups"),
        "rows_scanned": unavailable("Python semantic execution does not expose physical rows scanned"),
    }


def subprocess_worker(profile_path: Path, decision_id: str) -> list[Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-profile",
        str(profile_path),
        "--worker-decision-id",
        decision_id,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise WorkloadError(f"Fresh-process worker failed: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list):
        raise WorkloadError("Fresh-process worker returned malformed JSON")
    return payload


def run_one(
    workload_id: str,
    registry_row: dict[str, Any],
    profile_path: Path,
    read_set: dict[str, Any],
    selection: Selection,
    scratch_root: Path,
    *,
    seed: int,
    sample_size: int,
    batch_repetitions: int,
) -> dict[str, Any]:
    process_class = "process-warm/filesystem-cache-state-unknown"
    transfer: dict[str, Any] | None = None

    if workload_id == "AVR-012":
        process_class = "fresh-process/filesystem-cache-state-unknown"
        rows, metrics = measure(
            lambda: (
                subprocess_worker(profile_path, selection.decision_id),
                {"fresh_process": True},
            )
        )
    elif workload_id in {"AVR-013", "AVR-014"}:
        operation_root = scratch_root / workload_id.lower()
        operation_root.mkdir(parents=True, exist_ok=False)
        copied = operation_root / "copied-read-set.json"
        before_sha = sha256_file(profile_path)
        shutil.copy2(profile_path, copied)
        read_path = copied
        if workload_id == "AVR-014":
            moved = operation_root / "moved-read-set.json"
            os.replace(copied, moved)
            read_path = moved
        after_sha = sha256_file(read_path)
        transferred = load_json(read_path)
        rows, metrics = measure(
            lambda: (decision_by_id(transferred, selection.decision_id), {})
        )
        transfer = {
            "destination": str(read_path),
            "destination_sha256": after_sha,
            "identity_preserved": before_sha == after_sha,
            "operation": "copy-then-read" if workload_id == "AVR-013" else "copy-move-then-read",
            "readback_count": len(rows),
            "source_preserved": profile_path.is_file(),
            "source_sha256": before_sha,
        }
        if not transfer["identity_preserved"] or not rows:
            raise WorkloadError(f"{workload_id} transfer/readback validation failed")
    else:
        rows, metrics = measure(
            lambda: execute_semantics(
                workload_id,
                read_set,
                selection,
                seed=seed,
                sample_size=sample_size,
                batch_repetitions=batch_repetitions,
            )
        )

    result = {
        "classification": process_class,
        "input_ids_or_seed": resolved_inputs(
            workload_id, selection, seed, sample_size, batch_repetitions
        ),
        "metrics": metrics,
        "observations": normal_observations(profile_path),
        "query": registry_row["query"],
        "query_sha256": registry_row["query_sha256"],
        "result_sha256": sha256_bytes(stable_json_bytes(rows)),
        "proof_level": "synthetic-semantic-read-set-mechanics",
        "physical_parquet_execution": unavailable(
            "exact Canonical V1 package/mapping and DuckDB dependency are unavailable"
        ),
        "workload_id": workload_id,
        "workload_name": registry_row["name"],
    }
    if transfer is not None:
        result["transfer"] = transfer
        result["observations"]["files_touched"] = [str(profile_path), transfer["destination"]]
    return result


def parse_profile(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("profile must be PROFILE_ID=/path/to/read-set.json")
    profile_id, raw_path = value.split("=", 1)
    if not profile_id or not raw_path:
        raise argparse.ArgumentTypeError("profile ID and path must be non-empty")
    if re.fullmatch(r"[A-Za-z0-9._-]+", profile_id) is None:
        raise argparse.ArgumentTypeError(
            "profile ID may contain only letters, numbers, dot, underscore, and hyphen"
        )
    return profile_id, Path(raw_path).resolve()


def worker_main(profile_path: Path, decision_id: str) -> int:
    try:
        rows = decision_by_id(load_json(profile_path), decision_id)
    except (MaterializationError, WorkloadError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(rows, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--profile", action="append", type=parse_profile, default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scratch-root", type=Path)
    parser.add_argument("--workload", action="append", choices=EXPECTED_IDS, default=[])
    parser.add_argument("--seed", type=int, default=15001)
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument("--batch-repetitions", type=int, default=5)
    parser.add_argument("--worker-profile", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-decision-id", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_profile:
        if not args.worker_decision_id:
            parser.error("--worker-decision-id is required with --worker-profile")
        return worker_main(args.worker_profile.resolve(), args.worker_decision_id)
    if not args.profile or args.output is None:
        parser.error("at least one --profile and --output are required")

    try:
        registry = load_registry(args.registry.resolve())
        requested = args.workload or list(EXPECTED_IDS)
        scratch_owner = None
        if args.scratch_root:
            scratch_root = args.scratch_root.resolve()
            scratch_root.mkdir(parents=True, exist_ok=True)
        else:
            scratch_owner = tempfile.TemporaryDirectory(prefix="analyzer-avr-")
            scratch_root = Path(scratch_owner.name)
        profile_reports = []
        query_hashes: dict[str, set[str]] = {workload_id: set() for workload_id in requested}
        try:
            for profile_id, profile_path in args.profile:
                if not profile_path.is_file():
                    raise WorkloadError(f"Profile input is not a file: {profile_path}")
                read_set = load_json(profile_path)
                package = validate_package(read_set.get("package"))
                selection = select_inputs(read_set)
                profile_scratch = Path(
                    tempfile.mkdtemp(prefix=f"{profile_id}-", dir=scratch_root)
                )
                results = []
                for workload_id in requested:
                    result = run_one(
                        workload_id,
                        registry[workload_id],
                        profile_path,
                        read_set,
                        selection,
                        profile_scratch,
                        seed=args.seed,
                        sample_size=args.sample_size,
                        batch_repetitions=args.batch_repetitions,
                    )
                    results.append(result)
                    query_hashes[workload_id].add(result["query_sha256"])
                profile_reports.append(
                    {
                        "driver": "python-semantic-read-set-proof",
                        "duckdb": unavailable("duckdb==1.5.5 is not installed in this environment"),
                        "input_bytes": profile_path.stat().st_size,
                        "input_sha256": sha256_file(profile_path),
                        "package": package,
                        "profile_id": profile_id,
                        "profile_path": str(profile_path),
                        "workloads": results,
                    }
                )
        finally:
            if scratch_owner is not None:
                scratch_owner.cleanup()

        inconsistent = [
            workload_id for workload_id, hashes in query_hashes.items() if len(hashes) != 1
        ]
        if inconsistent:
            raise WorkloadError(
                "Query meaning changed between profiles for: " + ", ".join(inconsistent)
            )
        report = {
            "environment": {
                "machine": platform.machine(),
                "os_cold_claim": False,
                "platform": platform.platform(),
                "python": platform.python_version(),
            },
            "notes": [
                "Filesystem cache state is unknown; no normal run is labeled OS-cold I/O.",
                "Unavailable DuckDB/Parquet physical metrics are explicit and are not inferred from logical work.",
                "This synthetic semantic proof is not Canonical V1 package conformance or a Parquet profile comparison.",
            ],
            "profiles": profile_reports,
            "query_semantics_identical_across_profiles": True,
            "registry_id": "analyzer-retrieval-workloads-v1",
            "schema_version": REPORT_SCHEMA,
            "workload_ids": requested,
        }
        payload = stable_json_bytes(report)
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    except (MaterializationError, WorkloadError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"PASS: exercised {len(requested)} workloads across {len(args.profile)} profile(s): {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
