import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "real-analysis" / "checker-sage-gnu-disagreement-001"
OUTPUT_PATH = ROOT / "site" / "data" / "analyzer-retained-checker-preview.json"
ASSET_DIR = ROOT / "site" / "assets" / "positions" / "real-analysis" / "checker-sage-gnu-disagreement-001"
RENDER_WRAPPER = ROOT / "scripts" / "analysis" / "render-retained-checker-preview.sh"
R_REQUIREMENTS = ROOT / "scripts" / "analysis" / "requirements.R"
SETUP_SCRIPT = ROOT / "scripts" / "setup" / "setup.sh"
R_RENDERER = ROOT / "scripts" / "render_real_checker_assets.R"

SPEC = importlib.util.spec_from_file_location(
    "project_retained_checker_preview",
    ROOT / "scripts" / "analysis" / "project_retained_checker_preview.py",
)
PROJECTOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PROJECTOR)


class AnalyzerRetainedCheckerPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checked_in = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        cls.checker = cls.checked_in["analyses"]["retained-checker-preview"]

    def test_checked_in_preview_is_deterministic_projector_output(self):
        self.assertEqual(PROJECTOR.build_projection(FIXTURE_DIR), self.checked_in)

    def test_top_three_real_candidates_map_exact_values(self):
        self.assertEqual(
            [(item["display_rank"], item["move"], item["value"]["value"], item["difference_from_best"])
             for item in self.checker["candidates"]],
            [
                (1, "8/4", -1.615, 0.0),
                (2, "13/10 11/10", -1.617, -0.002),
                (3, "13/10 8/7", -1.619, -0.004),
            ],
        )

    def test_same_starting_position_and_candidate_overlay_assets_are_explicit(self):
        self.assertTrue(self.checker["original_board"]["image"].endswith("/starting.svg"))
        for candidate in self.checker["candidates"]:
            self.assertIn("move_board", candidate)
            self.assertIn("starting position", candidate["move_board"]["alt"])
            image_name = Path(candidate["move_board"]["image"]).name
            self.assertTrue((ASSET_DIR / image_name).is_file(), image_name)

    def test_played_move_and_recommendation_remain_distinct(self):
        metadata = self.checker["metadata"]
        self.assertEqual(metadata["played_move"], "13/12 11/8")
        self.assertEqual(metadata["recommendation"], "8/4")
        self.assertNotEqual(metadata["played_move"], metadata["recommendation"])

    def test_supported_setup_provisions_analyzer_r_dependencies(self):
        requirements = R_REQUIREMENTS.read_text(encoding="utf-8")
        setup = SETUP_SCRIPT.read_text(encoding="utf-8")
        for package in ("jsonlite", "ggplot2", "ggforce", "ggiraph", "patchwork", "scales"):
            self.assertIn(package, requirements)
        self.assertIn("scripts/analysis/requirements.R", setup)
        self.assertIn("install-r-dependencies.R", setup)

    def test_render_wrapper_installs_current_local_renderer_packages_without_devtools(self):
        wrapper = RENDER_WRAPPER.read_text(encoding="utf-8")
        renderer = R_RENDERER.read_text(encoding="utf-8")
        self.assertIn("CMD INSTALL", wrapper)
        self.assertIn('"${BACKGAMMONBOARD_REPO}"', wrapper)
        self.assertIn('"${BACKGAMMONCALCULATOR_REPO}"', wrapper)
        self.assertNotIn("devtools", wrapper)
        self.assertNotIn("devtools", renderer)
        self.assertIn('board_colors("bs")', renderer)
        self.assertIn('board_style("bs")', renderer)
        self.assertIn("board_moves(", renderer)

    def test_renderer_derives_starting_xgid_from_retained_gnuid(self):
        renderer = R_RENDERER.read_text(encoding="utf-8")
        self.assertIn("source$gnu_position_id", renderer)
        self.assertIn("source$gnu_match_id", renderer)
        self.assertIn("backgammoncalculator::gnuid_to_xgid", renderer)
        self.assertNotIn('starting_xgid <- "XGID=', renderer)
        self.assertIn("backgammoncalculator commit", renderer)
        self.assertIn("derived XGID", renderer)

    def test_renderer_maps_fixture_decision_player_from_factual_on_roll_identity(self):
        renderer = R_RENDERER.read_text(encoding="utf-8")
        self.assertIn("decision_player <- position$on_roll", renderer)
        self.assertIn("position$score[[position$on_roll]]", renderer)
        self.assertNotIn('identical(position$on_roll, "player_1")', renderer)


if __name__ == "__main__":
    unittest.main()
