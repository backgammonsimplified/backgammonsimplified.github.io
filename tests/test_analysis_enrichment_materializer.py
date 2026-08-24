from __future__ import annotations

import copy
import hashlib
import json
import math
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.analysis import analysis_enrichment_materializer as enrichment
from scripts.analysis import checker_movement_preparer
from scripts.analysis import hadd_sidecar


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts/analysis/task-021-analysis-enrichment.json"
VIEW_PATH = ROOT / "site/data/analyzer-task-021-enrichment.json"
RECEIPT_PATH = ROOT / "evidence/analyzer-k001/task-021/analysis-enrichment-receipt.json"
REQUEST_PATH = ROOT / "evidence/analyzer-k001/task-021/generated-hadd-request.json"
SIDECAR_PATH = ROOT / "evidence/analyzer-k001/task-021/generated-hadd-sidecar.json"


class AnalysisEnrichmentMaterializerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.view = json.loads(VIEW_PATH.read_text(encoding="utf-8"))
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.sidecar = hadd_sidecar.load_sidecar(SIDECAR_PATH)
        cls.analysis = next(iter(cls.view["analyses"].values()))

    def test_exact_semantic_authorities_and_zero_engine_boundary(self) -> None:
        facts = self.view["analysis_enrichment"]
        self.assertEqual(facts["board_commit"], enrichment.BOARD_COMMIT)
        self.assertEqual(facts["calculator_commit"], enrichment.CALCULATOR_COMMIT)
        self.assertEqual(
            facts["movement_preparer_version"],
            checker_movement_preparer.PREPARER_VERSION,
        )
        self.assertEqual(
            facts["structured_movement_source"],
            "accepted_normalized_gnu_candidate_notation",
        )
        self.assertFalse(facts["configured_per_candidate_movement_facts"])
        self.assertEqual(facts["engine_execution_count"], 0)
        self.assertFalse(facts["public_deployment"])
        self.assertEqual(
            facts["calculated_cubeful"], "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED"
        )
        self.assertEqual(self.receipt["engine_execution_count"], 0)

    def test_completed_result_identity_and_all_candidate_identities_are_preserved(self) -> None:
        source = json.loads(
            (ROOT / "tests/fixtures/node-k001-checker-analysis-view.json").read_text(
                encoding="utf-8"
            )
        )
        identity = self.analysis["canonical_context"]["source_factual_result_identity"]
        self.assertEqual(identity["analysis_key"], source["analysis_key"])
        self.assertEqual(
            identity["artifact_sha256"],
            hashlib.sha256(
                (ROOT / "tests/fixtures/node-k001-checker-analysis-view.json").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            [item["id"] for item in self.analysis["candidates"]],
            [item["id"] for item in source["checker"]["candidates"]],
        )
        self.assertEqual(self.analysis["recommended_id"], "gnu-move-1")

    def test_every_candidate_has_verified_movement_result_identity_and_two_boards(self) -> None:
        result_ids = set()
        for candidate in self.analysis["candidates"]:
            with self.subTest(candidate=candidate["id"]):
                self.assertEqual(candidate["preview"]["status"], "available")
                self.assertEqual(
                    candidate["preview"]["kind"], "prepared-movement-and-result"
                )
                self.assertGreater(len(candidate["structured_movements"]), 0)
                self.assertRegex(
                    candidate["resulting_position_id"],
                    r"^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$",
                )
                self.assertTrue(candidate["move_board"]["image"].endswith("-movement.svg"))
                self.assertTrue(candidate["result_board"]["image"].endswith("-result.svg"))
                state = candidate["resulting_board_state"]["players"]
                for player in ("player_0", "player_1"):
                    self.assertEqual(
                        sum(state[player]["points"])
                        + state[player]["bar"]
                        + state[player]["off"],
                        15,
                    )
                result_ids.add(candidate["resulting_position_id"])
        self.assertEqual(len(result_ids), 8)

    def test_two_step_and_compact_move_are_atomic_without_browser_parsing(self) -> None:
        first = self.analysis["candidates"][0]
        collapsed = self.analysis["candidates"][3]
        self.assertEqual(
            first["structured_movements"],
            [
                {"order": 1, "from": 8, "to": 4, "die": 4},
                {"order": 2, "from": 6, "to": 4, "die": 2},
            ],
        )
        self.assertEqual(
            collapsed["structured_movements"],
            [
                {"order": 1, "from": 24, "to": 20, "die": 4},
                {"order": 2, "from": 20, "to": 18, "die": 2},
            ],
        )
        for candidate in self.analysis["candidates"]:
            preparation = candidate["movement_preparation"]
            self.assertEqual(preparation["legality_status"], "unique_legal_play")
            self.assertEqual(
                preparation["source_fact_kind"],
                "accepted_normalized_gnu_candidate_notation",
            )
        viewer = (ROOT / "site/assets/bs-analysis-results.js").read_text(encoding="utf-8")
        self.assertNotIn("parseCheckerNotation", viewer)
        self.assertNotIn("applyBoardMoves", viewer)

    def test_hadd_request_is_complete_exact_and_next_player_on_roll(self) -> None:
        self.assertEqual(self.request["schema_version"], enrichment.HADD_REQUEST_SCHEMA)
        self.assertEqual(len(self.request["positions"]), 8)
        self.assertEqual(len(self.request["candidates"]), 8)
        self.assertEqual(len(self.request["ab_requests"]), 7)
        for position in self.request["positions"]:
            self.assertEqual(position["perspective"], "player_on_roll")
            self.assertEqual(len(position["on_roll_points_1_to_24_and_bar"]), 25)
            self.assertEqual(len(position["opponent_points_1_to_24_and_bar"]), 25)
            self.assertEqual(
                sum(position["on_roll_points_1_to_24_and_bar"])
                + position["on_roll_borne_off"],
                15,
            )
            self.assertEqual(
                sum(position["opponent_points_1_to_24_and_bar"])
                + position["opponent_borne_off"],
                15,
            )
        self.assertTrue(
            all(
                item["source_occurrence_id"]
                == self.analysis["canonical_context"]["canonical_decision_id"]
                for item in self.request["candidates"]
            )
        )

    def test_generated_sidecar_passes_the_only_task020_validator_and_join(self) -> None:
        self.assertIs(hadd_sidecar.validate_sidecar(self.sidecar), self.sidecar)
        self.assertEqual(self.view["hadd_integration"]["status"], "available")
        self.assertEqual(
            self.sidecar["package_identity_sha256"],
            "be1c47d34adee7292ea751c49d377df8beb3ea7428dde31d7fbe8d433fb3d54c",
        )
        self.assertEqual(len(self.sidecar["records"]), 8)
        self.assertEqual(len(self.sidecar["ab_explanations"]), 7)
        self.assertTrue(
            all("hadd_derived_facts" in candidate for candidate in self.analysis["candidates"])
        )

    def test_model_feature_order_perspective_probability_and_value_are_exact(self) -> None:
        provenance = self.view["hadd_materialization"]
        self.assertEqual(provenance["explainer_commit"], enrichment.EXPLAINER_COMMIT)
        self.assertEqual(
            provenance["immutable_integration_package_identity_sha256"],
            enrichment.EXPLAINER_PACKAGE_IDENTITY,
        )
        self.assertEqual(
            provenance["model_identity_sha256"], hadd_sidecar.MODEL["source_model_identity_sha256"]
        )
        self.assertEqual(
            provenance["feature_order_identity_sha256"],
            hadd_sidecar.FEATURE_SYSTEM["ordered_feature_ids_sha256"],
        )
        self.assertEqual(
            provenance["position_perspective"], hadd_sidecar.TARGET["position_perspective"]
        )
        for record in self.sidecar["records"]:
            probabilities = record["cumulative_probabilities"]
            self.assertLessEqual(probabilities["win_backgammon"], probabilities["win_gammon_or_better"])
            self.assertLessEqual(probabilities["win_gammon_or_better"], probabilities["win"])
            self.assertLessEqual(probabilities["lose_backgammon"], probabilities["lose_gammon_or_worse"])
            self.assertLessEqual(probabilities["lose_gammon_or_worse"], record["lose_probability"])
            expected = (
                2 * probabilities["win"]
                - 1
                + probabilities["win_gammon_or_better"]
                + probabilities["win_backgammon"]
                - probabilities["lose_gammon_or_worse"]
                - probabilities["lose_backgammon"]
            )
            self.assertLessEqual(abs(expected - record["probability_derived_cubeless"]), 1e-12)

    def test_explanations_reconstruct_and_unchanged_features_cancel(self) -> None:
        unchanged = 0
        for explanation in self.sidecar["ab_explanations"]:
            reconstructed = [
                math.fsum(
                    row["conditional_logit_contributions"][head]
                    for row in explanation["per_feature_conditional_logit_difference"]
                )
                for head in range(5)
            ]
            for actual, expected in zip(
                reconstructed, explanation["conditional_logit_difference"]
            ):
                self.assertLessEqual(abs(actual - expected), 1e-12)
            unchanged += sum(
                row["conditional_logit_contributions"] == [0.0] * 5
                for row in explanation["per_feature_conditional_logit_difference"]
            )
        self.assertGreater(unchanged, 0)

    def test_config_cannot_reintroduce_per_candidate_movement_authority(self) -> None:
        cases = []
        manual = copy.deepcopy(self.config)
        manual["analysis_enrichment"]["checker_analyses"][0]["candidates"] = [
            {"candidate_id": "manual", "movement_steps": []}
        ]
        cases.append((manual, "per-candidate movement facts are not accepted"))
        empty_prefix = copy.deepcopy(self.config)
        empty_prefix["analysis_enrichment"]["checker_analyses"][0][
            "candidate_concept_id_prefix"
        ] = ""
        cases.append((empty_prefix, "non-empty string"))
        duplicate = copy.deepcopy(self.config)
        duplicate["analysis_enrichment"]["checker_analyses"].append(
            copy.deepcopy(duplicate["analysis_enrichment"]["checker_analyses"][0])
        )
        cases.append((duplicate, "Duplicate enrichment analysis"))
        for config, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                enrichment.EnrichmentError, message
            ):
                enrichment.enrichment_index(config)

    def test_unsupported_candidate_notation_leaves_preview_and_hadd_unavailable(self) -> None:
        actual = checker_movement_preparer.prepare_movements

        def fail_one(position_id, dice, notation):
            if notation == "24/20 6/4":
                raise checker_movement_preparer.MovementPreparationError("unsupported proof")
            return actual(position_id, dice, notation)

        with patch.object(
            checker_movement_preparer, "prepare_movements", side_effect=fail_one
        ):
            document, manifest = enrichment.prepare_base(self.config, ROOT)
        analysis = next(iter(document["analyses"].values()))
        self.assertEqual(analysis["candidates"][-1]["preview"]["status"], "unavailable")
        self.assertIsNone(enrichment.hadd_request(document, {}))
        self.assertEqual(len(manifest["analyses"][0]["candidates"]), 7)
        self.assertEqual(len(manifest["analyses"][0]["preparation_failures"]), 1)

    def test_retained_result_requires_no_per_candidate_authored_semantics(self) -> None:
        configured = self.config["analysis_enrichment"]["checker_analyses"][0]
        self.assertEqual(
            set(configured), {"analysis_id", "candidate_concept_id_prefix"}
        )
        config_text = CONFIG_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"movement_steps"', config_text)
        self.assertNotIn('"source_notation"', config_text)
        _, manifest = enrichment.prepare_base(self.config, ROOT)
        self.assertEqual(len(manifest["analyses"][0]["candidates"]), 8)
        self.assertEqual(manifest["analyses"][0]["preparation_failures"], [])

    def test_inconsistent_receipt_result_board_and_perspective_fail_closed(self) -> None:
        _, manifest = enrichment.prepare_base(self.config, ROOT)
        cases = []
        wrong_identity = copy.deepcopy(self.receipt)
        wrong_identity["analyses"][0]["candidates"][0]["hadd_position"]["position_id"] = "wrong"
        cases.append((wrong_identity, "identity/perspective"))
        wrong_total = copy.deepcopy(self.receipt)
        wrong_total["analyses"][0]["candidates"][0]["resulting_board_state"]["players"]["player_0"]["off"] += 1
        cases.append((wrong_total, "checker totals"))
        wrong_candidate = copy.deepcopy(self.receipt)
        wrong_candidate["analyses"][0]["candidates"][0]["candidate_id"] = "unknown"
        cases.append((wrong_candidate, "duplicate or unknown"))
        for receipt, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                enrichment.EnrichmentError, message
            ):
                enrichment.validate_receipt(receipt, manifest)

    def test_repeat_projection_and_checked_semantic_artifacts_are_byte_stable(self) -> None:
        first_document, first_manifest = enrichment.prepare_base(self.config, ROOT)
        second_document, second_manifest = enrichment.prepare_base(
            copy.deepcopy(self.config), ROOT
        )
        self.assertEqual(enrichment.stable_bytes(first_document), enrichment.stable_bytes(second_document))
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(
            self.view["analysis_enrichment"]["candidate_preview_receipt_sha256"],
            hashlib.sha256(enrichment.stable_bytes(self.receipt)).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
