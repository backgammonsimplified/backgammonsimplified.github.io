import hashlib
import json
import re
import unittest
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
FIXTURE_PATH = SITE / "data" / "lesson-analysis-svg-mvp.json"
GOLDEN_PATH = SITE / "data" / "analyzer-node-k001-lesson-preview.json"
ASSET_ROOT = (
    SITE
    / "assets"
    / "positions"
    / "lesson-analysis-svg-mvp"
    / "opening-fixture"
)
CUBE_LESSON = SITE / "learn" / "cube" / "what-the-cube-is-asking.qmd"
CHECKER_LESSON = (
    SITE
    / "learn"
    / "cube"
    / "why-is-25-percent-the-basic-take-point.qmd"
)


class LessonAnalysisFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        cls.cube_source = CUBE_LESSON.read_text(encoding="utf-8")
        cls.checker_source = CHECKER_LESSON.read_text(encoding="utf-8")

    def test_fixture_contract_and_explicit_status(self):
        self.assertEqual(
            self.data["schema_version"],
            "bs-lesson-analysis-fixture-v1",
        )
        self.assertEqual(self.data["fixture_status"]["kind"], "fixture-only")
        message = self.data["fixture_status"]["message"].casefold()
        self.assertIn("test fixtures", message)
        self.assertIn("not verified engine output", message)

    def test_cube_fixture_supports_all_requested_answer_shapes(self):
        cube_cases = self.data["cube_cases"]
        self.assertEqual(
            cube_cases["cube-roll"]["correct_first_action"],
            "roll",
        )
        self.assertEqual(
            cube_cases["cube-double-take"]["actions"]["double"]["responder"][
                "correct_response"
            ],
            "take",
        )
        self.assertEqual(
            cube_cases["cube-double-pass"]["actions"]["double"]["responder"][
                "correct_response"
            ],
            "pass",
        )

    def test_every_referenced_svg_exists_and_parses(self):
        names = set()
        for cube in self.data["cube_cases"].values():
            names.add(cube["initial"]["image"])
            responder = cube["actions"]["double"].get("responder")
            if responder:
                names.add(responder["image"])
        for checker in self.data["checker_cases"].values():
            names.add(checker["initial"]["image"])
            names.update(candidate["image"] for candidate in checker["candidates"])

        self.assertEqual(
            names,
            {
                "starting.svg",
                "responder-flipped.svg",
                "candidate-1.svg",
                "candidate-2.svg",
                "candidate-3.svg",
            },
        )
        for name in names:
            path = ASSET_ROOT / name
            self.assertTrue(path.is_file(), name)
            root = ElementTree.parse(path).getroot()
            self.assertTrue(root.tag.endswith("svg"), name)

    def test_shared_start_is_one_asset_used_by_both_component_types(self):
        cube_start = self.data["cube_cases"]["cube-double-take"]["initial"][
            "image"
        ]
        checker_start = self.data["checker_cases"][
            "checker-three-candidates"
        ]["initial"]["image"]
        self.assertEqual(cube_start, checker_start)
        starts = list(ASSET_ROOT.rglob("starting.svg"))
        self.assertEqual(starts, [ASSET_ROOT / "starting.svg"])

    def test_real_lessons_reference_exact_golden_analysis_keys(self):
        self.assertIn(
            'data-bs-analysis-src="/data/analyzer-node-k001-lesson-preview.json"',
            self.cube_source,
        )
        self.assertIn(
            'data-bs-analysis-src="/data/analyzer-node-k001-lesson-preview.json"',
            self.checker_source,
        )
        self.assertEqual(
            self.cube_source.count("data-bs-cube-decision"),
            1,
        )
        self.assertEqual(
            self.checker_source.count("data-bs-checker-decision"),
            1,
        )
        self.assertIn(
            "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d",
            self.checker_source,
        )
        self.assertIn(
            "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01",
            self.cube_source,
        )
        self.assertNotIn("<svg", self.cube_source.casefold())
        self.assertNotIn("<svg", self.checker_source.casefold())

    def test_golden_checker_preserves_source_candidates_and_prepared_assets(self):
        checker = self.golden["analyses"][
            "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"
        ]
        self.assertEqual(checker["metadata"]["recommendation"], "8/4 6/4")
        self.assertEqual(len(checker["candidates"]), 8)
        self.assertEqual(
            [candidate["source_order"] for candidate in checker["candidates"]],
            list(range(1, 9)),
        )
        self.assertEqual(
            [candidate["id"] for candidate in checker["candidates"]],
            [f"gnu-move-{rank}" for rank in range(1, 9)],
        )
        for rank, candidate in enumerate(checker["candidates"], start=1):
            expected = f"/assets/positions/node-k001/checker/candidate-{rank}.svg"
            self.assertEqual(candidate["move_board"]["image"], expected)
            self.assertTrue((SITE / expected.removeprefix("/")).is_file())

    def test_golden_cube_preserves_source_actions_equities_and_probabilities(self):
        cube = self.golden["analyses"][
            "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"
        ]
        self.assertEqual(cube["metadata"]["recommendation"], "Double, take")
        self.assertEqual(
            [(action["id"], action["value"]["value"]) for action in cube["actions"]],
            [
                ("double-take", 0.998032),
                ("double-pass", 1.0),
                ("no-double", 0.637873),
            ],
        )
        self.assertEqual(
            cube["probabilities"],
            {
                "win": 0.749996,
                "win_gammon_or_better": 0.0,
                "win_backgammon": 0.0,
                "lose": 0.250004,
                "lose_gammon_or_worse": 0.0,
                "lose_backgammon": 0.0,
            },
        )
        self.assertTrue(all(action["probabilities"] is None for action in cube["actions"]))

    def test_qmd_hosts_do_not_hard_code_component_ids(self):
        for source in (self.cube_source, self.checker_source):
            host_blocks = re.findall(
                r"<div\s+.*?data-bs-(?:cube|checker)-decision.*?</div>",
                source,
                flags=re.DOTALL,
            )
            self.assertTrue(host_blocks)
            for block in host_blocks:
                self.assertNotRegex(block, r'(?:^|\s)id="')

    def test_script_is_loaded_before_continuous_lesson_loader(self):
        scripts = (SITE / "includes" / "bs-scripts.html").read_text(
            encoding="utf-8"
        )
        analysis_index = scripts.index("bs-lesson-analysis.js")
        shared_index = scripts.index("bs-analysis-results.js")
        scroll_index = scripts.index("bs-learn-scroll.js")
        self.assertLess(shared_index, analysis_index)
        self.assertLess(analysis_index, scroll_index)
        implementation = (
            SITE / "assets" / "bs-lesson-analysis.js"
        ).read_text(encoding="utf-8")
        self.assertIn("window.BSLearn.mountLesson", implementation)
        self.assertIn("mount(rootElement)", implementation)
        self.assertIn("dataset.bsAnalysisMounted", implementation)

    def test_svg_reuse_cannot_duplicate_inline_ids(self):
        implementation = (
            SITE / "assets" / "bs-lesson-analysis.js"
        ).read_text(encoding="utf-8")
        self.assertIn("sharedAnalysis().renderBoard", implementation)
        self.assertNotIn('document.createElement("img")', implementation)
        self.assertNotIn("fetchSvg", implementation)
        start_hash = hashlib.sha256(
            (ASSET_ROOT / "starting.svg").read_bytes()
        ).hexdigest()
        self.assertEqual(len(start_hash), 64)

    def test_missing_optional_values_are_retained(self):
        candidate = self.data["checker_cases"]["checker-three-candidates"][
            "candidates"
        ][2]
        self.assertIsNone(candidate["winning_probabilities"]["win_gammon"])
        self.assertIsNone(candidate["winning_probabilities"]["lose_gammon"])

    def test_resource_contract_copies_dynamic_assets(self):
        config = (SITE / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn('"assets/positions/**"', config)
        self.assertIn("data/lesson-analysis-svg-mvp.json", config)
        self.assertIn("data/checker-sage-gnu-disagreement-001.json", config)
        self.assertIn("data/analyzer-node-k001-lesson-preview.json", config)
        self.assertIn("assets/bs-lesson-analysis.css", config)
        provenance = ASSET_ROOT / "PROVENANCE.txt"
        self.assertTrue(provenance.is_file())
        self.assertFalse((ASSET_ROOT / "PROVENANCE.md").exists())

    def test_lesson_is_a_thin_adapter_to_shared_presentation(self):
        implementation = (
            SITE / "assets" / "bs-lesson-analysis.js"
        ).read_text(encoding="utf-8")
        shared = (SITE / "assets" / "bs-analysis-results.js").read_text(
            encoding="utf-8"
        )
        lesson_css = (SITE / "assets" / "bs-lesson-analysis.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("checkerViewModel", implementation)
        self.assertIn("cubeViewModel", implementation)
        self.assertIn("sharedAnalysis().renderPresentation", implementation)
        self.assertIn(".fixtureLoader(analysisUrl)(analysisId)", implementation)
        self.assertIn("mountAcceptedChecker", implementation)
        self.assertIn("mountAcceptedCube", implementation)
        self.assertNotIn("candidateMetricRows", implementation)
        self.assertNotIn("analysisRows", implementation)
        self.assertNotIn(".bs-analysis-position-image", lesson_css)
        self.assertNotIn(".bs-analysis-metrics", lesson_css)
        self.assertIn("function outcomePanel", shared)
        self.assertIn("function renderChecker", shared)
        self.assertIn("function renderCube", shared)

    def test_real_lesson_flow_remains_owned_by_the_adapter(self):
        implementation = (
            SITE / "assets" / "bs-lesson-analysis.js"
        ).read_text(encoding="utf-8")
        self.assertIn('choiceButton(candidate.move, candidate.id)', implementation)
        self.assertIn('choiceButton("Double", "double")', implementation)
        self.assertIn('choiceButton("Take", "take")', implementation)
        self.assertIn("revealAcceptedAnalysis", implementation)
        self.assertIn("data-bs-lesson-prompt", self.checker_source)
        self.assertIn("data-bs-lesson-prompt", self.cube_source)

    def test_direct_browser_path_does_not_transform_or_calculate_analysis(self):
        implementation = (
            SITE / "assets" / "bs-lesson-analysis.js"
        ).read_text(encoding="utf-8")
        direct_path = implementation.split(
            "function acceptedAnalysisChoice", 1
        )[1].split("function mountCube", 1)[0]
        self.assertIn("payload.analysis", implementation)
        for forbidden in (
            "Parquet",
            "DuckDB",
            "GNUID",
            "Position ID",
            "decode",
            "applyMove",
            "parseMove",
            "difference_from_best",
            "equity_loss",
        ):
            self.assertNotIn(forbidden, direct_path)


if __name__ == "__main__":
    unittest.main()
