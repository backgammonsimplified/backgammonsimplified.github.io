from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import duckdb
except ModuleNotFoundError:
    duckdb = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis import inspect_canonical_parquet as intake


class CanonicalParquetIntakeTests(unittest.TestCase):
    @unittest.skipUnless(duckdb is not None, "duckdb dependency is unavailable")
    def write_table(self, root: Path, table: str, columns: str) -> None:
        target = root / table / "part-000.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        escaped = target.as_posix().replace("'", "''")
        with duckdb.connect(database=":memory:") as connection:
            connection.execute(f"CREATE TABLE source AS SELECT {columns}")
            connection.execute(f"COPY source TO '{escaped}' (FORMAT PARQUET)")

    def complete_package(self, root: Path) -> None:
        self.write_table(root, "positions", "'position-1' AS position_id")
        self.write_table(root, "games", "'game-1' AS game_id")
        self.write_table(
            root,
            "source_occurrences",
            "'occurrence-1' AS source_occurrence_id",
        )
        self.write_table(
            root,
            "occurrence_contexts",
            "'occurrence-1' AS source_occurrence_id",
        )
        self.write_table(root, "decisions", "'decision-1' AS decision_id")
        self.write_table(root, "candidates", "'candidate-1' AS candidate_id")
        self.write_table(
            root,
            "evaluations",
            "'evaluation-1' AS evaluation_id, 4 AS actual_ply",
        )
        self.write_table(
            root,
            "cube_occurrences",
            "'cube-occurrence-1' AS cube_occurrence_id",
        )
        self.write_table(
            root,
            "cube_actions",
            "'cube-action-1' AS cube_action_id",
        )
        self.write_table(root, "exclusions", "'excluded-source-row' AS reason")
        (root / "manifest.json").write_text(
            json.dumps({"schema_version": "test-only"}) + "\n",
            encoding="utf-8",
        )

    @unittest.skipUnless(duckdb is not None, "duckdb dependency is unavailable")
    def test_complete_logical_family_is_inspected_without_mapping_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.complete_package(root)
            report = intake.inspect_package(root)

        self.assertEqual(intake.canonical_family_gaps(report), [])
        self.assertEqual(report["manifest"]["payload"]["schema_version"], "test-only")
        self.assertEqual(report["tables"]["evaluations"]["row_count"], 1)
        self.assertEqual(report["tables"]["cube_actions"]["row_count"], 1)
        self.assertEqual(
            [column["name"] for column in report["tables"]["evaluations"]["columns"]],
            ["evaluation_id", "actual_ply"],
        )
        self.assertEqual(len(report["tables"]["positions"]["file_sha256"]), 1)

    @unittest.skipUnless(duckdb is not None, "duckdb dependency is unavailable")
    def test_missing_tables_are_reported_instead_of_synthesized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_table(root, "positions", "'position-1' AS position_id")
            report = intake.inspect_package(root)

        gaps = intake.canonical_family_gaps(report)
        self.assertIn("manifest.json", gaps)
        self.assertIn("decisions", gaps)
        self.assertIn("evaluations", gaps)
        self.assertIn("cube_occurrences", gaps)
        self.assertIn("cube_actions", gaps)
        self.assertEqual(report["tables"]["decisions"]["status"], "missing")

    @unittest.skipIf(duckdb is not None, "only applies when DuckDB is absent")
    def test_missing_duckdb_fails_closed_with_setup_message(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "DuckDB is unavailable"):
                intake.inspect_package(Path(temporary))


if __name__ == "__main__":
    unittest.main()
