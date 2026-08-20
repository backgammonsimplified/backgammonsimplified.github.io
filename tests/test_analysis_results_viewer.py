import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "site" / "data" / "analyzer-analysis-results-fixtures.json"
RETAINED_PATH = ROOT / "site" / "data" / "analyzer-retained-checker-preview.json"
CANONICAL_PATH = ROOT / "site" / "data" / "analyzer-canonical-checker-preview.json"
PAGE_PATH = ROOT / "site" / "analyze" / "results-fixture.qmd"
PUBLICATION_PATH = ROOT / "site" / "_publication.yml"
QUARTO_PATH = ROOT / "site" / "_quarto.yml"
SCRIPTS_PATH = ROOT / "site" / "includes" / "bs-scripts.html"
VIEWER_PATH = ROOT / "site" / "assets" / "bs-analysis-results.js"
VIEWER_CSS_PATH = ROOT / "site" / "assets" / "bs-analysis-results.css"
R_RENDERER_PATH = ROOT / "scripts" / "render_real_checker_assets.R"


class AnalysisResultsViewerContractTests(unittest.TestCase):
    def test_synthetic_failure_fixture_remains_explicit(self):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "bs-analysis-results-viewer-fixture-v1")
        self.assertEqual(payload["fixture_status"]["kind"], "synthetic")
        self.assertTrue(payload["analyses"]["checker-ui-demo"]["fixture"])
        self.assertTrue(payload["analyses"]["cube-ui-demo"]["fixture"])

    def test_retained_checker_preview_uses_real_analysis_and_move_boards(self):
        payload = json.loads(RETAINED_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["fixture_status"]["kind"], "retained-analysis")
        checker = payload["analyses"]["retained-checker-preview"]
        self.assertEqual(checker["context"]["dice"], "3-1")
        self.assertEqual([item["move"] for item in checker["candidates"]], [
            "8/4",
            "13/10 11/10",
            "13/10 8/7",
        ])
        self.assertEqual([item["actual_ply"] for item in checker["candidates"]], [4, 4, 4])
        self.assertEqual(checker["candidates"][0]["difference_from_best"], 0.0)
        for candidate in checker["candidates"]:
            self.assertIn("move_board", candidate)
            self.assertIn("checker-sage-gnu-disagreement-001", candidate["move_board"]["image"])
            self.assertIn("starting position", candidate["move_board"]["alt"])

    def test_canonical_checker_preview_uses_verified_parquet_materialization(self):
        payload = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["fixture_status"]["kind"], "canonical-analysis")
        package = payload["materialization"]["package"]
        self.assertEqual(
            package["package_id"],
            "canonical-analysis-reference-2c828e118b6cf22f",
        )
        self.assertEqual(
            package["manifest_sha256"],
            "effa2a8bc273be03222d8193c090f96ef3415224af228f0e45678b8e7ec498a7",
        )
        self.assertEqual(package["conformance_status"], "verified-canonical-v1")

        decision_id = (
            "b909630c811a0214b8156e068b88ebeb9a064a56bfec3ae5af8c6afe45278d07"
        )
        checker = payload["analyses"][decision_id]

        self.assertEqual(
            checker["canonical_context"]["logical_position_id"],
            "c3aeb102842104c01efb857fbcd5c3f45d0cd3859b65f28d6fae3c7a470c2e3b",
        )
        self.assertEqual(checker["context"]["dice"], "3-1")
        self.assertEqual(checker["metadata"]["played_move"], "13/12 11/8")
        self.assertEqual(checker["metadata"]["recommendation"], "8/4")

        self.assertEqual(
            [item["move"] for item in checker["candidates"]],
            ["8/4", "13/10 11/10", "13/10 8/7", "8/7 6/3", "13/12 11/8"],
        )
        self.assertEqual(
            [item["value"]["value"] for item in checker["candidates"]],
            [-1.615, -1.617, -1.619, -1.625, -1.643],
        )
        self.assertTrue(
            all(item["difference_from_best"] is None for item in checker["candidates"])
        )
        self.assertEqual(
            [item["native_equity_loss_display"] for item in checker["candidates"]],
            [None, -0.002, -0.004, -0.01, -0.028],
        )
        self.assertEqual(
            checker["candidates"][0]["probabilities"],
            {
                "win": 0.162,
                "win_gammon_or_better": 0.0,
                "win_backgammon": 0.0,
                "lose": 0.838,
                "lose_gammon_or_worse": 0.677,
                "lose_backgammon": 0.052,
            },
        )

    def test_checker_and_cube_cover_degraded_states(self):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        checker = payload["analyses"]["checker-ui-demo"]
        cube = payload["analyses"]["cube-ui-demo"]
        self.assertIsNone(checker["candidates"][2]["result_board"])
        self.assertIsNone(checker["candidates"][1]["probabilities"]["win_gammon_or_better"])
        self.assertFalse(cube["actions"][3]["supported"])
        self.assertIn("malformed-ui-demo", payload["analyses"])

    def test_outcome_presentation_is_one_stacked_bar(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("exclusiveOutcomeSegments", script)
        self.assertIn("outcomeSummaryItems", script)
        self.assertIn("bs-analysis-results-outcome-bar", script)
        self.assertIn("bs-analysis-results-outcome-segment", script)
        self.assertIn("Gammon and backgammon breakdown not supplied", script)
        self.assertIn(".bs-analysis-results-outcome-bar", css)
        self.assertIn("display: flex;", css)
        self.assertIn("bs-analysis-results-outcome-summary-item--", script)
        self.assertIn(".bs-analysis-results-outcome-summary-item--win", css)
        self.assertIn(".bs-analysis-results-outcome-summary-item--lose", css)
        self.assertIn("#237a3b", css)
        self.assertIn("#b23b3b", css)
        self.assertNotIn("bs-analysis-results-probability-track", script)
        self.assertNotIn("bs-analysis-results-probability-track", css)

    def test_checker_keeps_open_bars_and_board_is_beside_moves(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn('element("details", "bs-analysis-results-candidate")', script)
        self.assertIn('element("summary", "bs-analysis-results-candidate-summary")', script)
        self.assertIn('"Equity"', script)
        self.assertIn('"vs best"', script)
        self.assertIn("details.open = true", script)
        self.assertNotIn("other.open = false", script)
        self.assertIn("candidate.move_board || originalBoard", script)
        self.assertNotIn("candidate.result_board", script)
        self.assertIn("shell.append(boardSection, analysisSection)", script)
        self.assertIn("article.append(header, presentation.element)", script)
        self.assertIn(".bs-analysis-results-shell", css)
        self.assertIn("grid-template-columns: minmax(18rem, 0.9fr) minmax(28rem, 1.1fr);", css)

    def test_checker_active_selection_is_separate_from_disclosure(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("setActiveCheckerCandidate", script)
        self.assertIn('summary.addEventListener("click"', script)
        self.assertIn('summary.setAttribute("aria-current"', script)
        self.assertIn('details.classList.toggle("is-active", active)', script)
        self.assertIn("selected.details.open = true", script)
        self.assertNotIn("details.open = false", script)
        self.assertNotIn('details.addEventListener("toggle"', script)
        self.assertIn(".bs-analysis-results-candidate.is-active", css)
        self.assertIn("bs-analysis-results-candidate-selected", script)

    def test_checker_sticky_surface_keeps_top_and_selected_decisions(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")

        self.assertIn("bs-analysis-results-checker-decision", script)
        self.assertIn("bs-analysis-results-checker-summary", script)
        self.assertIn('checkerMoveCard(topCandidate, "Top move", "top")', script)
        self.assertIn(
            'checkerMoveCard(selectedCandidate, "Selected move", "selected")',
            script,
        )
        self.assertIn("showCheckerDecision(decision, topCandidate, candidate)", script)
        self.assertIn("selectedCandidate.id === topCandidate.id", script)
        self.assertIn("candidate.move_board || originalBoard", script)

        sticky_block = css.split(
            ".bs-analysis-results-checker-decision {", 1
        )[1].split("}", 1)[0]
        self.assertIn("position: sticky;", sticky_block)
        self.assertIn("top: var(--bs-analysis-results-sticky-top", sticky_block)
        self.assertIn("max-height:", sticky_block)
        self.assertIn("overflow-y: auto;", sticky_block)

    def test_checker_probability_comparison_is_semantic_and_complete(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")

        self.assertIn("PROBABILITY_COMPARISON_ROWS", script)
        for label in (
            "Win",
            "Win gammon or better",
            "Win backgammon",
            "Lose",
            "Lose gammon or worse",
            "Lose backgammon",
        ):
            self.assertIn(f'"{label}"', script)
        self.assertIn('element("table", "bs-analysis-results-comparison-table")', script)
        self.assertIn('element("thead", "")', script)
        self.assertIn('element("tbody", "")', script)
        self.assertIn('label.scope = "row"', script)
        self.assertIn('topHeader.scope = "col"', script)
        self.assertIn('selectedHeader.scope = "col"', script)
        self.assertIn("selected - top", script)
        self.assertIn('difference === null ? null', script)
        self.assertIn('return "Not supplied"', script)

    def test_checker_responsive_css_contains_component_overflow(self):
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")

        self.assertIn("max-width: 100%;", css)
        self.assertIn("overflow-x: clip;", css)
        self.assertIn("table-layout: fixed;", css)
        self.assertIn("@media (max-width: 700px)", css)
        narrow = css.split("@media (max-width: 700px)", 1)[1]
        self.assertIn(
            "grid-template-columns: minmax(6.75rem, 34vw) minmax(0, 1fr);",
            narrow,
        )
        self.assertIn(".bs-analysis-results-comparison-table", narrow)

    def test_presentation_api_is_shared_with_lessons(self):
        viewer = VIEWER_PATH.read_text(encoding="utf-8")
        lesson = (ROOT / "site" / "assets" / "bs-lesson-analysis.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function renderPresentation(host, model, options)", viewer)
        self.assertIn("sharedAnalysis().renderPresentation", lesson)
        self.assertIn("checkerViewModel", lesson)
        self.assertIn("cubeViewModel", lesson)
        self.assertNotIn("candidateMetricRows", lesson)
        self.assertNotIn("analysisRows", lesson)
        self.assertNotIn("formatProbability", lesson)

    def test_r_renderer_uses_current_structured_backgammonboard_api(self):
        renderer = R_RENDERER_PATH.read_text(encoding="utf-8")
        self.assertIn("structured_moves_from_fixture_notation", renderer)
        self.assertIn("board_moves(", renderer)
        self.assertIn('board_colors("bs")', renderer)
        self.assertIn('board_style("bs")', renderer)
        self.assertIn('perspective = "decision_maker"', renderer)
        self.assertIn('light_player = "near_player"', renderer)
        retired_preset = "b" + "ms"
        self.assertNotIn(f'board_colors("{retired_preset}")', renderer)
        self.assertNotIn(f'board_style("{retired_preset}")', renderer)
        self.assertNotIn("moves = candidate$move", renderer)
        self.assertNotIn("show_information", renderer)
        self.assertNotIn("brand_text", renderer)

    def test_cube_action_controls_use_compact_result_rows(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("bs-analysis-results-choice-primary", script)
        self.assertIn("bs-analysis-results-choice-secondary", script)
        self.assertIn("bs-analysis-results-choice-value", script)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto;", css)
        self.assertIn("border-bottom: 1px solid var(--bs-border);", css)

    def test_fixture_route_is_registered_non_indexable(self):
        publication = PUBLICATION_PATH.read_text(encoding="utf-8")
        route = "/analyze/results-fixture.html:"
        self.assertIn(route, publication)
        route_block = publication.split(route, 1)[1].split("\n      /", 1)[0]
        self.assertIn("status: fixture", route_block)
        page = PAGE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("published: true", page)
        self.assertIn("DEVELOPMENT PREVIEW", page)
        self.assertIn("analyzer-canonical-checker-preview.json", page)
        self.assertIn("analyzer-canonical-cube-preview.json", page)
        self.assertIn("Canonical Parquet checker regression result", page)
        self.assertIn("Canonical Parquet cube regression result", page)

    def test_viewer_assets_are_registered(self):
        quarto = QUARTO_PATH.read_text(encoding="utf-8")
        scripts = SCRIPTS_PATH.read_text(encoding="utf-8")
        self.assertIn("data/analyzer-analysis-results-fixtures.json", quarto)
        self.assertIn("data/analyzer-retained-checker-preview.json", quarto)
        self.assertIn("data/analyzer-canonical-checker-preview.json", quarto)
        self.assertIn("data/analyzer-canonical-cube-preview.json", quarto)
        self.assertIn("assets/bs-analysis-results.css", quarto)
        self.assertIn('/assets/bs-analysis-results.js', scripts)
        self.assertLess(
            scripts.index("bs-analysis-results.js"),
            scripts.index("bs-lesson-analysis.js"),
        )


if __name__ == "__main__":
    unittest.main()
