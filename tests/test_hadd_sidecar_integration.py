from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.analysis import hadd_sidecar


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "hadd-integration"
SIDECAR_PATH = FIXTURE_ROOT / "actual-4ply-canonical-pair-sidecar-v1.json"
REQUEST_PATH = FIXTURE_ROOT / "actual-4ply-canonical-pair-request-v1.json"


def factual_document(request: dict) -> dict:
    decision_id = request["ab_requests"][0]["decision_id"]
    return {
        "schema_version": "bs-analysis-results-viewer-fixture-v1",
        "fixture_status": {
            "kind": "canonical-analysis",
            "label": "Canonical factual join fixture",
            "message": "Only stable factual identities participate in this integration fixture.",
        },
        "analyses": {
            decision_id: {
                "analysis_kind": "checker",
                "canonical_context": {"canonical_decision_id": decision_id},
                "candidates": [
                    {
                        "id": item["candidate_id"],
                        "candidate_concept_id": item["candidate_concept_id"],
                        "resulting_position_id": item["result_position_id"],
                    }
                    for item in request["candidates"]
                ],
            }
        },
    }


def refresh_package_identity(sidecar: dict) -> None:
    payload = {key: value for key, value in sidecar.items() if key != "package_identity_sha256"}
    sidecar["package_identity_sha256"] = hashlib.sha256(
        hadd_sidecar._stable_compact(payload)
    ).hexdigest()


class HaddSidecarIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sidecar = hadd_sidecar.load_sidecar(SIDECAR_PATH)
        cls.request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.factual = factual_document(cls.request)

    def test_accepted_immutable_fixture_identity_and_complete_validation(self) -> None:
        self.assertEqual(
            hashlib.sha256(SIDECAR_PATH.read_bytes()).hexdigest(),
            "67208900e9be8448465d886b564ed75b314bee0fbe41c1c474c861a9c3334ffb",
        )
        self.assertIs(hadd_sidecar.validate_sidecar(self.sidecar), self.sidecar)
        self.assertEqual(
            self.sidecar["package_identity_sha256"],
            "2d8c3475ee377fc826879a83d80b13017e01f931794d965c1a3cc178b0a8a720",
        )

    def test_exact_stable_joins_attach_probabilities_value_and_explanation(self) -> None:
        output = hadd_sidecar.attach_sidecar(self.factual, self.sidecar)
        self.assertEqual(output["hadd_integration"]["status"], "available")
        analysis = next(iter(output["analyses"].values()))
        self.assertFalse(analysis["hadd"]["authority"]["hadd_ranking_authorized"])
        self.assertEqual(
            analysis["hadd"]["authority"]["calculated_cubeful"],
            "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED",
        )
        first = analysis["candidates"][0]["hadd_derived_facts"]
        self.assertAlmostEqual(first["probabilities"]["win"], 0.9220429863994463)
        self.assertAlmostEqual(first["probability_derived_cubeless"], 1.1361007237092626)
        self.assertEqual(len(first["conditional_logit_evidence"]["feature_contributions"]), 351)
        self.assertEqual(analysis["hadd"]["ab_explanations"][0]["difference_order"], "A-minus-B")

    def test_probability_hierarchy_value_and_a_minus_b_reconstruction(self) -> None:
        for record in self.sidecar["records"]:
            probabilities = record["cumulative_probabilities"]
            self.assertLessEqual(probabilities["win_backgammon"], probabilities["win_gammon_or_better"])
            self.assertLessEqual(probabilities["win_gammon_or_better"], probabilities["win"])
            self.assertLessEqual(probabilities["lose_backgammon"], probabilities["lose_gammon_or_worse"])
            self.assertLessEqual(probabilities["lose_gammon_or_worse"], record["lose_probability"])
            expected = (
                2 * probabilities["win"] - 1
                + probabilities["win_gammon_or_better"] + probabilities["win_backgammon"]
                - probabilities["lose_gammon_or_worse"] - probabilities["lose_backgammon"]
            )
            self.assertAlmostEqual(expected, record["probability_derived_cubeless"], places=12)
        explanation = self.sidecar["ab_explanations"][0]
        reconstructed = [
            math.fsum(row["conditional_logit_contributions"][head] for row in explanation["per_feature_conditional_logit_difference"])
            for head in range(5)
        ]
        for actual, expected in zip(reconstructed, explanation["conditional_logit_difference"]):
            self.assertLessEqual(abs(actual - expected), 1e-12)

    def test_exactly_unchanged_features_cancel_on_all_five_heads(self) -> None:
        rows = self.sidecar["ab_explanations"][0]["per_feature_conditional_logit_difference"]
        unchanged = [row for row in rows if row["conditional_logit_contributions"] == [0.0] * 5]
        self.assertGreater(len(unchanged), 0)
        self.assertEqual(unchanged[0]["feature_id"], "player_point_01_checkers")
        self.assertTrue(all(value == 0.0 for row in unchanged for value in row["conditional_logit_contributions"]))

    def test_wrong_duplicate_or_ambiguous_factual_ids_fail_closed_without_mutation(self) -> None:
        cases = []
        wrong = copy.deepcopy(self.factual)
        next(iter(wrong["analyses"].values()))["candidates"][0]["resulting_position_id"] = "wrong"
        cases.append(wrong)
        duplicate = copy.deepcopy(self.factual)
        candidates = next(iter(duplicate["analyses"].values()))["candidates"]
        candidates.append(copy.deepcopy(candidates[0]))
        cases.append(duplicate)
        partial = copy.deepcopy(self.factual)
        next(iter(partial["analyses"].values()))["candidates"].pop()
        cases.append(partial)
        for factual in cases:
            with self.subTest(factual=factual):
                with self.assertRaises(hadd_sidecar.HaddSidecarError):
                    hadd_sidecar.attach_sidecar(factual, self.sidecar)
                self.assertNotIn("hadd_integration", factual)

    def test_incompatible_exact_identities_fail_closed(self) -> None:
        mutations = [
            ("schema_version", "future"),
            ("selected_architecture", "other"),
        ]
        for key, value in mutations:
            malformed = copy.deepcopy(self.sidecar)
            malformed[key] = value
            with self.subTest(key=key), self.assertRaises(hadd_sidecar.HaddSidecarError):
                hadd_sidecar.validate_sidecar(malformed)
        for section, key in [
            ("model", "source_model_identity_sha256"),
            ("feature_system", "feature_registry_sha256"),
            ("feature_system", "ordered_feature_ids_sha256"),
            ("target", "position_perspective"),
            ("integration_contract", "descriptor_sha256"),
        ]:
            malformed = copy.deepcopy(self.sidecar)
            malformed[section][key] = "wrong"
            with self.subTest(section=section, key=key), self.assertRaises(hadd_sidecar.HaddSidecarError):
                hadd_sidecar.validate_sidecar(malformed)

    def test_invalid_probability_and_contribution_semantics_fail_closed(self) -> None:
        malformed = copy.deepcopy(self.sidecar)
        malformed["records"][0]["cumulative_probabilities"]["win_backgammon"] = 0.99
        refresh_package_identity(malformed)
        with self.assertRaisesRegex(hadd_sidecar.HaddSidecarError, "probability_hierarchy"):
            hadd_sidecar.validate_sidecar(malformed)
        malformed = copy.deepcopy(self.sidecar)
        malformed["ab_explanations"][0]["per_feature_conditional_logit_difference"][0][
            "conditional_logit_contributions"
        ][0] = 0.01
        refresh_package_identity(malformed)
        with self.assertRaisesRegex(hadd_sidecar.HaddSidecarError, "reconstruction_mismatch"):
            hadd_sidecar.validate_sidecar(malformed)

    def test_duplicate_json_keys_and_malformed_or_missing_files_are_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"schema_version":"one","schema_version":"two"}', encoding="utf-8")
            with self.assertRaisesRegex(hadd_sidecar.HaddSidecarError, "duplicate_json_key"):
                hadd_sidecar.load_sidecar(duplicate)
            with self.assertRaisesRegex(hadd_sidecar.HaddSidecarError, "missing_or_malformed"):
                hadd_sidecar.load_sidecar(root / "missing.json")

    def test_unavailable_disposition_preserves_all_factual_content(self) -> None:
        output = hadd_sidecar.unavailable(self.factual, "wrong_model")
        self.assertEqual(output["hadd_integration"]["status"], "unavailable")
        self.assertFalse(output["hadd_integration"]["fabricated_content"])
        self.assertEqual(output["analyses"], self.factual["analyses"])
        self.assertNotIn("hadd_integration", self.factual)

    def test_cli_missing_sidecar_keeps_factual_analyzer_usable(self) -> None:
        read_set = ROOT / "tests/fixtures/analyzer-analysis-view-read-set-v1.json"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "view.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/analysis/analysis_view_materializer.py"),
                    str(read_set),
                    "--hadd-sidecar",
                    str(Path(temporary) / "missing-sidecar.json"),
                    "--prepare-exploration",
                    "--verify-repeat",
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["hadd_integration"]["status"], "unavailable")
            self.assertFalse(result["hadd_integration"]["fabricated_content"])
            self.assertEqual(len(result["analyses"]), 2)


if __name__ == "__main__":
    unittest.main()
