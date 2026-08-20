#!/usr/bin/env python3
"""Inspect a Canonical Analysis Parquet reference package without guessing semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    import duckdb
except ModuleNotFoundError:  # Report a bounded setup failure instead of a traceback.
    duckdb = None


LOGICAL_TABLES = (
    "positions",
    "games",
    "source_occurrences",
    "occurrence_contexts",
    "decisions",
    "candidates",
    "evaluations",
    "cube_occurrences",
    "cube_actions",
    "exclusions",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_table_files(root: Path, table: str) -> list[Path]:
    candidates: set[Path] = set()
    direct = root / f"{table}.parquet"
    if direct.is_file():
        candidates.add(direct.resolve())

    table_dir = root / table
    if table_dir.is_dir():
        candidates.update(path.resolve() for path in table_dir.rglob("*.parquet"))

    tables_dir = root / "tables"
    nested_direct = tables_dir / f"{table}.parquet"
    if nested_direct.is_file():
        candidates.add(nested_direct.resolve())
    nested_dir = tables_dir / table
    if nested_dir.is_dir():
        candidates.update(path.resolve() for path in nested_dir.rglob("*.parquet"))

    return sorted(candidates)


def manifest_candidates(root: Path) -> list[Path]:
    return [
        path
        for path in (
            root / "manifest.json",
            root / "manifest" / "manifest.json",
        )
        if path.is_file()
    ]


def relative_paths(root: Path, paths: list[Path]) -> list[str]:
    return [path.relative_to(root).as_posix() for path in paths]


def require_duckdb():
    if duckdb is None:
        raise RuntimeError(
            "DuckDB is unavailable; install scripts/analysis/requirements.txt "
            "before inspecting Canonical Parquet"
        )
    return duckdb


def inspect_relation(connection, files: list[Path]) -> dict[str, object]:
    relation = connection.read_parquet([str(path) for path in files], union_by_name=True)
    columns = [
        {"name": name, "type": str(column_type)}
        for name, column_type in zip(relation.columns, relation.types, strict=True)
    ]
    row_count = int(relation.aggregate("count(*) AS row_count").fetchone()[0])
    return {"row_count": row_count, "columns": columns}


def inspect_package(package_root: Path) -> dict[str, object]:
    root = package_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Canonical reference package is not a directory: {root}")

    manifests = manifest_candidates(root)
    if len(manifests) > 1:
        raise ValueError("Canonical reference package has more than one manifest.json candidate")

    manifest_payload = None
    if manifests:
        manifest_payload = json.loads(manifests[0].read_text(encoding="utf-8"))

    tables: dict[str, object] = {}
    duckdb_module = require_duckdb()
    with duckdb_module.connect(database=":memory:") as connection:
        for table in LOGICAL_TABLES:
            files = discover_table_files(root, table)
            if not files:
                tables[table] = {"status": "missing", "files": []}
                continue
            table_info = inspect_relation(connection, files)
            table_info.update(
                {
                    "status": "present",
                    "files": relative_paths(root, files),
                    "file_sha256": {
                        path.relative_to(root).as_posix(): sha256_file(path)
                        for path in files
                    },
                }
            )
            tables[table] = table_info

    manifest_info: dict[str, object]
    if manifests:
        manifest = manifests[0]
        manifest_info = {
            "status": "present",
            "path": manifest.relative_to(root).as_posix(),
            "sha256": sha256_file(manifest),
            "payload": manifest_payload,
        }
    else:
        manifest_info = {"status": "missing"}

    return {
        "package_root": str(root),
        "manifest": manifest_info,
        "tables": tables,
    }


def canonical_family_gaps(report: dict[str, object]) -> list[str]:
    gaps: list[str] = []
    manifest = report["manifest"]
    if manifest["status"] != "present":
        gaps.append("manifest.json")
    for table in LOGICAL_TABLES:
        table_report = report["tables"][table]
        if table_report["status"] != "present":
            gaps.append(table)
    return gaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-complete-family",
        action="store_true",
        help="fail if any canonical logical table or manifest.json is absent",
    )
    args = parser.parse_args()

    try:
        report = inspect_package(args.package_root)
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=__import__("sys").stderr)
        return 1
    gaps = canonical_family_gaps(report)
    report["canonical_family_gaps"] = gaps
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")

    if args.require_complete_family and gaps:
        print(
            "ERROR: incomplete Canonical Parquet reference family: " + ", ".join(gaps),
            file=__import__("sys").stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
