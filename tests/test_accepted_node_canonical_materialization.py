from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.analysis import analysis_view_materializer as materializer
from scripts.analysis import materialize_accepted_node_pair as pair


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "evidence" / "analyzer-k001" / "task-008"
CONFIG_PATH = ROOT / "scripts" / "analysis" / "node-k001-canonical-materialization.json"
CHECKER_READ_SET = EVIDENCE_ROOT / "checker-read-set.json"
CUBE_READ_SET = EVIDENCE_ROOT / "cube-read-set.json"
EVIDENCE_PATH = EVIDENCE_ROOT / "materialization-evidence.json"
ANALYSIS_VIEW = ROOT / "site" / "data" / "analyzer-node-k001-lesson-preview.json"

CHECKER_ID = "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"
CUBE_ID = "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"
EXCLUDED_ID = "sha256-ba87405bf38017214424d71b1e3d1299ed323101db8893f2aa430054167a6414"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AcceptedNodeCanonicalMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.checker_read_set = json.loads(CHECKER_READ_SET.read_text(encoding="utf-8"))
        cls.cube_read_set = json.loads(CUBE_READ_SET.read_text(encoding="utf-8"))
        cls.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        cls.analysis_view = json.loads(ANALYSIS_VIEW.read_text(encoding="utf-8"))

    def test_exact_package_and_manifest_authorities_are_frozen(self):
        authorities = self.evidence["authority"]
        self.assertEqual(
            authorities["checker"]["package_id"],
            "1a38c5a48214a4ea156d1896b8ea09bcdce75880077fabb2fc516c5685ff259c",
        )
        self.assertEqual(
            authorities["checker"]["manifest_sha256"],
            "bcd84099792e5679dd997ea4aa85f0d3ee217f5df79b2adc989b5938c6d2988e",
        )
        self.assertEqual(
            authorities["cube"]["package_id"],
            "bde4011fa40a384168a49529db7192e039a15252d4a2ab481c7b2fecfa98806b",
        )
        self.assertEqual(
            authorities["cube"]["manifest_sha256"],
            "dbe6bcb41ac8ecdb52ffa33a72cc97bc47fae9c0f9bc67a9bc8559c197c2d11a",
        )
        self.assertEqual(
            authorities["checker"]["committed_marker"]["manifest_sha256"],
            authorities["checker"]["manifest_sha256"],
        )
        self.assertEqual(
            authorities["cube"]["committed_marker"]["manifest_sha256"],
            authorities["cube"]["manifest_sha256"],
        )

    def test_selected_canonical_ids_and_explicit_null_result_positions(self):
        selected = self.evidence["selected"]
        self.assertEqual(selected["checker"]["analysis_id"], CHECKER_ID)
        self.assertEqual(
            selected["checker"]["decision_id"],
            "8e8e9519d238e20fdbb550ec871f3a6a8fb915fe0091353e1ad20e73cb21acb3",
        )
        self.assertEqual(len(selected["checker"]["candidate_ids"]), 8)
        self.assertEqual(len(selected["checker"]["evaluation_ids"]), 8)
        self.assertEqual(selected["checker"]["result_position_ids"], [None] * 8)
        self.assertEqual(selected["cube"]["analysis_id"], CUBE_ID)
        self.assertEqual(
            selected["cube"]["cube_occurrence_id"],
            "215747e8305eff4e89325822fda7c967d2a242154194ff7a1b4b8ea6f34c5005",
        )
        self.assertEqual(len(selected["cube"]["cube_action_ids"]), 3)

        checker = self.checker_read_set["analyses"][0]
        self.assertTrue(
            all(row["structured_movements"] == [] for row in checker["checker_candidates"])
        )
        self.assertTrue(
            all(row["resulting_position_id"] is None for row in checker["checker_candidates"])
        )

    def test_excluded_package_a_cube_is_rejected_and_absent(self):
        excluded = self.evidence["excluded_package_a_cube"]
        self.assertEqual(excluded["source_record_id"], EXCLUDED_ID)
        self.assertEqual(excluded["disposition"], "rejected-before-materialization")
        self.assertEqual(len(excluded["cube_action_ids"]), 3)
        self.assertNotIn(EXCLUDED_ID, ANALYSIS_VIEW.read_text(encoding="utf-8"))
        self.assertEqual(set(self.analysis_view["analyses"]), {CHECKER_ID, CUBE_ID})

    def test_read_sets_reproduce_checked_in_pair_byte_for_byte(self):
        checker_document = materializer.materialize_document(self.checker_read_set)
        cube_document = materializer.materialize_document(self.cube_read_set)
        combined = pair.combine_documents(
            checker_document,
            cube_document,
            checker_analysis_id=CHECKER_ID,
            cube_analysis_id=CUBE_ID,
            config_sha256=hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            materializer.stable_json_bytes(combined),
            ANALYSIS_VIEW.read_bytes(),
        )
        outputs = self.evidence["outputs"]
        self.assertEqual(outputs["checker_read_set_sha256"], sha256(CHECKER_READ_SET))
        self.assertEqual(outputs["cube_read_set_sha256"], sha256(CUBE_READ_SET))
        self.assertEqual(outputs["golden_pair_analysis_view_sha256"], sha256(ANALYSIS_VIEW))

    def test_full_provenance_survives_materializer_round_trip(self):
        for read_set, analysis_id in (
            (self.checker_read_set, CHECKER_ID),
            (self.cube_read_set, CUBE_ID),
        ):
            source = read_set["analyses"][0]["canonical_provenance"]
            output = self.analysis_view["analyses"][analysis_id]["canonical_context"][
                "provenance"
            ]
            self.assertEqual(source, output)
            self.assertEqual(source["settings"]["invocation_identity"], "gnubg-cli-command-file-windows-v1")
            self.assertEqual(source["settings"]["parser_identity"], "gnu-text-parser-v1")
            self.assertEqual(
                source["producer"]["analysis_producer_identity"]["producer_identity_sha256"],
                "b785713f755b9059dd7187ff07aec7a47372ccb393f7bd026a60acf7550f1cbf",
            )

    def test_query_hashes_bind_to_the_checked_in_duckdb_queries(self):
        queries = self.evidence["query_evidence"]
        expected = {
            "checker_selection_sql_sha256": pair.CHECKER_SELECTION_SQL,
            "checker_evaluations_sql_sha256": pair.CHECKER_EVALUATIONS_SQL,
            "cube_selection_sql_sha256": pair.CUBE_SELECTION_SQL,
            "cube_actions_sql_sha256": pair.CUBE_ACTIONS_SQL,
            "excluded_selection_sql_sha256": pair.EXCLUDED_SELECTION_SQL,
            "excluded_actions_sql_sha256": pair.EXCLUDED_ACTIONS_SQL,
        }
        for key, sql in expected.items():
            self.assertEqual(queries[key], hashlib.sha256(sql.encode("utf-8")).hexdigest())

    def test_lessons_consume_canonical_pair_through_shared_viewer(self):
        cube_lesson = (ROOT / "site/learn/cube/what-the-cube-is-asking.qmd").read_text()
        checker_lesson = (
            ROOT / "site/learn/cube/why-is-25-percent-the-basic-take-point.qmd"
        ).read_text()
        for lesson in (cube_lesson, checker_lesson):
            self.assertIn('/data/analyzer-node-k001-lesson-preview.json', lesson)
        lesson_adapter = (ROOT / "site/assets/bs-lesson-analysis.js").read_text()
        self.assertIn("sharedAnalysis().renderPresentation", lesson_adapter)
        self.assertNotIn("Parquet", lesson_adapter)


if __name__ == "__main__":
    unittest.main()
