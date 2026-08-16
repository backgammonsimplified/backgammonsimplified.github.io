from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis import run_retrieval_workloads as workloads


FIXTURE = ROOT / "tests" / "fixtures" / "analyzer-analysis-view-read-set-v1.json"
REGISTRY = ROOT / "scripts" / "analysis" / "retrieval_workloads_v1.json"


class RetrievalWorkloadTests(unittest.TestCase):
    def test_registry_has_stable_complete_ids_and_query_hashes(self) -> None:
        registry = workloads.load_registry(REGISTRY)
        self.assertEqual(tuple(sorted(registry)), workloads.EXPECTED_IDS)
        self.assertTrue(all(len(row["query_sha256"]) == 64 for row in registry.values()))
        self.assertEqual(
            registry["AVR-007"]["query"]["operation"],
            "requested_and_row_local_actual_depths",
        )

    def test_seeded_result_selection_is_repeatable(self) -> None:
        read_set = json.loads(FIXTURE.read_text(encoding="utf-8"))
        first = workloads.seeded_results(read_set, 15001, 3)
        second = workloads.seeded_results(read_set, 15001, 3)
        self.assertEqual(first, second)
        self.assertEqual([row["sample_sequence"] for row in first], [1, 2, 3])

    def test_all_workloads_run_across_two_profiles_with_identical_query_meaning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profile_a = root / "profile-a.json"
            profile_b = root / "profile-b.json"
            shutil.copyfile(FIXTURE, profile_a)
            shutil.copyfile(FIXTURE, profile_b)
            report_path = root / "report.json"
            scratch = root / "scratch"
            command = [
                sys.executable,
                str(ROOT / "scripts" / "analysis" / "run_retrieval_workloads.py"),
                "--profile",
                f"minimal-a={profile_a}",
                "--profile",
                f"minimal-b={profile_b}",
                "--output",
                str(report_path),
                "--scratch-root",
                str(scratch),
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["workload_ids"], list(workloads.EXPECTED_IDS))
        self.assertTrue(report["query_semantics_identical_across_profiles"])
        self.assertFalse(report["environment"]["os_cold_claim"])
        self.assertEqual(len(report["profiles"]), 2)
        for profile in report["profiles"]:
            self.assertEqual(profile["driver"], "python-semantic-read-set-proof")
            self.assertEqual(profile["duckdb"]["status"], "unavailable")
            self.assertEqual(
                [row["workload_id"] for row in profile["workloads"]],
                list(workloads.EXPECTED_IDS),
            )
            by_id = {row["workload_id"]: row for row in profile["workloads"]}
            self.assertEqual(
                by_id["AVR-012"]["classification"],
                "fresh-process/filesystem-cache-state-unknown",
            )
            self.assertTrue(by_id["AVR-013"]["transfer"]["identity_preserved"])
            self.assertTrue(by_id["AVR-014"]["transfer"]["identity_preserved"])
            self.assertEqual(
                by_id["AVR-001"]["observations"]["rows_scanned"]["status"],
                "unavailable",
            )

        hashes_a = {
            row["workload_id"]: row["query_sha256"]
            for row in report["profiles"][0]["workloads"]
        }
        hashes_b = {
            row["workload_id"]: row["query_sha256"]
            for row in report["profiles"][1]["workloads"]
        }
        self.assertEqual(hashes_a, hashes_b)


if __name__ == "__main__":
    unittest.main()
