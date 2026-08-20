from __future__ import annotations

import copy
import unittest

from scripts.analysis import validate_node_parquet_equivalence as equivalence


class NodeParquetEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents, cls.hashes = equivalence.load_documents()

    def build(self, documents=None):
        return equivalence.build_report_from_documents(
            copy.deepcopy(documents if documents is not None else self.documents),
            copy.deepcopy(self.hashes),
        )

    def mismatches(self, report):
        return [
            row
            for row in report["comparisons"]
            if row["classification"] == equivalence.MISMATCH
        ]

    def test_exact_accepted_pair_passes_with_all_four_classifications_available(self):
        report = self.build()
        self.assertEqual(report["result"]["status"], "PASS")
        self.assertEqual(report["result"]["checker_semantic_equivalence"], "PASS")
        self.assertEqual(report["result"]["cube_semantic_equivalence"], "PASS")
        self.assertEqual(report["result"]["required_factual_mismatch_count"], 0)
        self.assertEqual(
            report["result"]["required_provenance_identity_mapping"], "AUDITABLE"
        )
        counts = report["summary"]["classification_counts"]
        self.assertGreater(counts[equivalence.EQUAL], 0)
        self.assertGreater(counts[equivalence.NEUTRAL], 0)
        self.assertGreater(counts[equivalence.UNAVAILABLE], 0)
        self.assertEqual(counts[equivalence.MISMATCH], 0)

    def test_native_checker_equity_change_is_a_factual_mismatch(self):
        documents = copy.deepcopy(self.documents)
        documents["node_checker"]["checker"]["candidates"][0]["value"][
            "value"
        ] += 0.000001
        report = self.build(documents)
        fields = {row["field"] for row in self.mismatches(report)}
        self.assertIn("candidate[1].native_equity", fields)
        self.assertEqual(report["result"]["checker_semantic_equivalence"], "FAIL")
        self.assertGreater(report["result"]["required_factual_mismatch_count"], 0)

    def test_candidate_reordering_fails_closed(self):
        documents = copy.deepcopy(self.documents)
        candidates = documents["checker_read_set"]["analyses"][0][
            "checker_candidates"
        ]
        candidates[0], candidates[1] = candidates[1], candidates[0]
        report = self.build(documents)
        fields = {row["field"] for row in self.mismatches(report)}
        self.assertIn("candidate[1].source_order", fields)
        self.assertIn("candidate[1].native_move", fields)

    def test_missing_required_probability_fails_closed(self):
        documents = copy.deepcopy(self.documents)
        del documents["node_cube"]["probabilities"]["win"]
        report = self.build(documents)
        mismatch = next(
            row
            for row in self.mismatches(report)
            if row["field"] == "position_probabilities.win"
        )
        self.assertNotIn("value", mismatch["node_direct"])
        self.assertEqual(report["result"]["cube_semantic_equivalence"], "FAIL")

    def test_canonical_cube_depth_is_not_backfilled_from_node(self):
        documents = copy.deepcopy(self.documents)
        documents["cube_read_set"]["analyses"][0]["cube_actions"][0][
            "actual_ply"
        ] = 1
        report = self.build(documents)
        mismatch = next(
            row
            for row in self.mismatches(report)
            if row["field"] == "action[1].row_local_actual_ply"
        )
        self.assertEqual(mismatch["canonical_derived"]["value"], 1)
        self.assertIn("refuses", mismatch["reason"])

    def test_excluded_package_a_cube_substitution_fails(self):
        documents = copy.deepcopy(self.documents)
        documents["node_cube"]["analysis_key"] = equivalence.EXCLUDED_CUBE_ID
        report = self.build(documents)
        fields = {row["field"] for row in self.mismatches(report)}
        self.assertIn("accepted_analysis_identity.node", fields)
        self.assertIn("projection_analysis_identity", fields)

    def test_input_hash_and_required_provenance_tampering_fail_closed(self):
        tampered_hashes = copy.deepcopy(self.hashes)
        tampered_hashes["checker_read_set"] = "0" * 64
        report = equivalence.build_report_from_documents(
            copy.deepcopy(self.documents), tampered_hashes
        )
        fields = {row["field"] for row in self.mismatches(report)}
        self.assertIn("input_sha256.checker_read_set", fields)
        self.assertIn("checker_read_set_hash_binding", fields)

        documents = copy.deepcopy(self.documents)
        del documents["checker_read_set"]["analyses"][0]["canonical_provenance"][
            "producer"
        ]["analysis_producer_identity"]["parser"]["source_commit"]
        report = self.build(documents)
        fields = {row["field"] for row in self.mismatches(report)}
        self.assertIn("parser_commit", fields)

    def test_repeat_report_and_human_result_are_byte_identical(self):
        first = self.build()
        second = self.build()
        first_json = equivalence.stable_json_bytes(first)
        second_json = equivalence.stable_json_bytes(second)
        self.assertEqual(first_json, second_json)
        first_markdown = equivalence.human_report(
            first, equivalence.sha256_bytes(first_json)
        )
        second_markdown = equivalence.human_report(
            second, equivalence.sha256_bytes(second_json)
        )
        self.assertEqual(first_markdown, second_markdown)


if __name__ == "__main__":
    unittest.main()
