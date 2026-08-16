from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis import analysis_view_materializer as materializer


FIXTURE = ROOT / "tests" / "fixtures" / "analyzer-analysis-view-read-set-v1.json"


class AnalysisViewMaterializerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.read_set = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_output_is_byte_deterministic_and_sorted_by_canonical_identity(self) -> None:
        first = materializer.stable_json_bytes(
            materializer.materialize_document(copy.deepcopy(self.read_set))
        )
        reversed_input = copy.deepcopy(self.read_set)
        reversed_input["analyses"].reverse()
        reversed_input["analyses"][1]["checker_candidates"].reverse()
        reversed_input["analyses"][1]["checker_evaluations"].reverse()
        second = materializer.stable_json_bytes(
            materializer.materialize_document(reversed_input)
        )
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(
            list(payload["analyses"]),
            ["synthetic-checker-decision-001", "synthetic-cube-decision-001"],
        )

    def test_checker_preserves_occurrence_position_depth_values_and_source_order(self) -> None:
        output = materializer.materialize_document(self.read_set)
        checker = output["analyses"]["synthetic-checker-decision-001"]
        canonical = checker["canonical_context"]
        self.assertEqual(canonical["logical_position_id"], "synthetic-logical-position-001")
        self.assertEqual(
            canonical["source_occurrence"]["occurrence_id"], "synthetic-occurrence-001"
        )
        self.assertNotEqual(
            canonical["logical_position_id"], canonical["source_occurrence"]["occurrence_id"]
        )
        self.assertEqual(canonical["requested_analysis"]["requested_ply"], 4)
        self.assertEqual(
            [row["id"] for row in checker["candidates"]],
            [
                "synthetic-checker-candidate-001",
                "synthetic-checker-candidate-002",
                "synthetic-checker-candidate-003",
            ],
        )
        self.assertEqual([row["actual_ply"] for row in checker["candidates"]], [4, 2, None])
        first = checker["candidates"][0]
        self.assertEqual(first["value"], {"label": "Equity", "value": -1.615})
        self.assertEqual(first["values"]["native"]["semantics"], "GNU Cubeful equity")
        self.assertEqual(first["values"]["normalized"]["value"], -0.8075)
        self.assertEqual(first["resulting_position_id"], "synthetic-result-position-001")
        self.assertEqual(len(first["evaluations"]), 1)
        self.assertIsNone(checker["candidates"][2]["move_board"])

    def test_cube_occurrence_is_distinct_from_complete_actions(self) -> None:
        cube = materializer.materialize_document(self.read_set)["analyses"][
            "synthetic-cube-decision-001"
        ]
        self.assertEqual(cube["cube_occurrence"]["observed_action_normalized"], "roll")
        self.assertEqual(
            [row["normalized_action"] for row in cube["actions"]],
            ["roll", "double_take", "double_pass", "beaver"],
        )
        self.assertFalse(cube["actions"][-1]["supported"])
        self.assertIsNone(cube["actions"][-1]["value"]["value"])
        self.assertTrue(all(row["actual_ply"] is None for row in cube["actions"]))

    def test_missing_is_not_reinterpreted_as_null(self) -> None:
        malformed = copy.deepcopy(self.read_set)
        del malformed["analyses"][0]["checker_evaluations"][0]["actual_ply"]
        with self.assertRaisesRegex(materializer.MaterializationError, "explicit null"):
            materializer.materialize_document(malformed)

    def test_orphan_evaluation_and_unsupported_schema_fail_closed(self) -> None:
        malformed = copy.deepcopy(self.read_set)
        malformed["analyses"][0]["checker_evaluations"][0]["candidate_id"] = "missing"
        with self.assertRaisesRegex(materializer.MaterializationError, "unknown candidate"):
            materializer.materialize_document(malformed)
        malformed = copy.deepcopy(self.read_set)
        malformed["schema_version"] = "future"
        with self.assertRaisesRegex(materializer.MaterializationError, "Unsupported"):
            materializer.materialize_document(malformed)

    def test_verified_package_requires_manifest_identity(self) -> None:
        malformed = copy.deepcopy(self.read_set)
        malformed["package"]["conformance_status"] = "verified-canonical-v1"
        with self.assertRaisesRegex(materializer.MaterializationError, "manifest SHA-256"):
            materializer.materialize_document(malformed)

    def test_cli_repeat_verification_writes_stable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "analysis-view.json"
            command = [
                sys.executable,
                str(ROOT / "scripts" / "analysis" / "analysis_view_materializer.py"),
                str(FIXTURE),
                "--output",
                str(output),
                "--verify-repeat",
            ]
            first = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_hash = hashlib.sha256(output.read_bytes()).hexdigest()
            second = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first_hash, hashlib.sha256(output.read_bytes()).hexdigest())

    def test_duplicate_json_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"schema_version":"one","schema_version":"two"}\n', encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError, "Duplicate JSON key"):
                materializer.load_json(path)


if __name__ == "__main__":
    unittest.main()
