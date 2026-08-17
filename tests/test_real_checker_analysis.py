import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "real-analysis" / "checker-sage-gnu-disagreement-001"
PROJECTION_PATH = ROOT / "site" / "data" / "checker-sage-gnu-disagreement-001.json"
ASSET_DIR = ROOT / "site" / "assets" / "positions" / "real-analysis" / "checker-sage-gnu-disagreement-001"
LESSON = ROOT / "site" / "learn" / "cube" / "why-is-25-percent-the-basic-take-point.qmd"

SPEC = importlib.util.spec_from_file_location(
    "project_real_checker_fixture",
    ROOT / "scripts" / "project_real_checker_fixture.py",
)
ADAPTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ADAPTER)


class RealCheckerAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        cls.fixture = cls.projection["checker_cases"]["checker-sage-gnu-disagreement-001"]
        cls.view = json.loads((FIXTURE_DIR / "analyzer-view.json").read_text(encoding="utf-8"))
        cls.analysis = json.loads((FIXTURE_DIR / "analysis.json").read_text(encoding="utf-8"))

    def test_checked_in_projection_is_adapter_output(self):
        self.assertEqual(ADAPTER.build_projection(FIXTURE_DIR), self.projection)
        self.assertEqual(self.projection["fixture_status"]["kind"], "retained-analysis")

    def test_identities_are_preserved_on_fixture_and_candidates(self):
        identity = (
            self.fixture["position_id"],
            self.fixture["state_hash"],
            self.fixture["analysis_id"],
        )
        self.assertEqual(identity, (
            self.view["position_id"],
            self.view["state_hash"],
            self.view["analysis_id"],
        ))
        for candidate in self.fixture["candidates"]:
            self.assertEqual(
                (candidate["position_id"], candidate["state_hash"], candidate["analysis_id"]),
                identity,
            )

    def test_top_three_map_move_rank_value_loss_and_probabilities(self):
        analysis_by_rank = {candidate["rank"]: candidate for candidate in self.analysis["candidates"]}
        self.assertEqual([candidate["label"] for candidate in self.fixture["candidates"]], [
            "8/4",
            "13/10 11/10",
            "13/10 8/7",
        ])
        for projected, viewed in zip(self.fixture["candidates"], self.view["candidates"][:3]):
            authoritative = analysis_by_rank[viewed["rank"]]
            self.assertEqual(projected["rank"], viewed["rank"])
            self.assertEqual(projected["move"], viewed["move"])
            self.assertEqual(projected["equity"], viewed["equity"])
            self.assertEqual(
                projected["equity_loss"],
                0.0 if viewed["difference_from_best"] is None else abs(viewed["difference_from_best"]),
            )
            self.assertEqual(projected["winning_probabilities"], authoritative["probabilities"])
            self.assertIsNone(projected["explanation"])
            self.assertTrue(projected["missing_value_state"]["explanation"])

    def test_every_mapped_svg_exists_and_parses(self):
        ADAPTER.validate_asset_contract(self.projection, ASSET_DIR)
        names = [self.fixture["initial"]["image"]]
        names.extend(candidate["image"] for candidate in self.fixture["candidates"])
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            root = ElementTree.parse(ASSET_DIR / name).getroot()
            self.assertTrue(root.tag.endswith("svg"), name)

    def test_missing_asset_fails_explicitly(self):
        malformed = copy.deepcopy(self.projection)
        fixture = next(iter(malformed["checker_cases"].values()))
        fixture["candidates"][1]["image"] = "does-not-exist.svg"
        with self.assertRaisesRegex(FileNotFoundError, "Missing checker SVG asset"):
            ADAPTER.validate_asset_contract(malformed, ASSET_DIR)

    def test_malformed_source_fixture_fails(self):
        documents = {
            name: json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
            for name in ADAPTER.EXPECTED_SCHEMAS
        }
        documents["analyzer-view.json"]["analysis_id"] = "wrong-analysis-id"

        def in_memory_load(path):
            return documents[path.name]

        with mock.patch.object(ADAPTER, "load_json", side_effect=in_memory_load):
            with self.assertRaisesRegex(ValueError, "analysis_id"):
                ADAPTER.build_projection(FIXTURE_DIR)

    def test_lesson_loads_golden_projection_and_browser_does_not_apply_moves(self):
        source = LESSON.read_text(encoding="utf-8")
        self.assertIn(
            'data-bs-analysis-src="/data/analyzer-node-k001-lesson-preview.json"',
            source,
        )
        self.assertIn(
            'data-bs-analysis-id="sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"',
            source,
        )
        browser = (ROOT / "site" / "assets" / "bs-lesson-analysis.js").read_text(encoding="utf-8")
        shared = (ROOT / "site" / "assets" / "bs-analysis-results.js").read_text(encoding="utf-8")
        self.assertNotIn("board_moves", browser)
        self.assertNotIn("apply_board_moves", browser)
        self.assertIn("move_board", browser)
        self.assertIn("assetUrl(fixtures.asset_root, candidate.image)", browser)
        self.assertIn("candidate.move_board || originalBoard", shared)
        self.assertIn("sharedAnalysis().renderPresentation", browser)


if __name__ == "__main__":
    unittest.main()
