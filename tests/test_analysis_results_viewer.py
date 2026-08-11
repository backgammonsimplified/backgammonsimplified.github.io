import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "site" / "data" / "analyzer-analysis-results-fixtures.json"
PAGE_PATH = ROOT / "site" / "analyze" / "results-fixture.qmd"
PUBLICATION_PATH = ROOT / "site" / "_publication.yml"
QUARTO_PATH = ROOT / "site" / "_quarto.yml"
SCRIPTS_PATH = ROOT / "site" / "includes" / "bs-scripts.html"
VIEWER_PATH = ROOT / "site" / "assets" / "bs-analysis-results.js"
VIEWER_CSS_PATH = ROOT / "site" / "assets" / "bs-analysis-results.css"


class AnalysisResultsViewerContractTests(unittest.TestCase):
    def test_fixture_document_is_explicitly_synthetic(self):
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "bs-analysis-results-viewer-fixture-v1")
        self.assertEqual(payload["fixture_status"]["kind"], "synthetic")
        self.assertTrue(payload["analyses"]["checker-ui-demo"]["fixture"])
        self.assertTrue(payload["analyses"]["cube-ui-demo"]["fixture"])

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
        self.assertIn("bs-analysis-results-outcome-summary-item--win", script)
        self.assertIn("bs-analysis-results-outcome-summary-item--lose", script)
        self.assertIn("#237a3b", css)
        self.assertIn("#b23b3b", css)
        self.assertNotIn("bs-analysis-results-probability-track", script)
        self.assertNotIn("bs-analysis-results-probability-track", css)

    def test_checker_uses_board_first_candidate_accordion(self):
        script = VIEWER_PATH.read_text(encoding="utf-8")
        css = VIEWER_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn('element("details", "bs-analysis-results-candidate")', script)
        self.assertIn('element("summary", "bs-analysis-results-candidate-summary")', script)
        self.assertIn('"Equity"', script)
        self.assertIn('"vs best"', script)
        self.assertIn("details.open = true", script)
        self.assertIn("article.append(header, boardSection, analysisSection)", script)
        self.assertIn(".bs-analysis-results-candidate-metrics", css)
        self.assertIn(".bs-analysis-results-board-section", css)

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
        self.assertIn("SYNTHETIC FIXTURE DATA", page)

    def test_viewer_assets_are_registered(self):
        quarto = QUARTO_PATH.read_text(encoding="utf-8")
        scripts = SCRIPTS_PATH.read_text(encoding="utf-8")
        self.assertIn("data/analyzer-analysis-results-fixtures.json", quarto)
        self.assertIn("assets/bs-analysis-results.css", quarto)
        self.assertIn('/assets/bs-analysis-results.js', scripts)


if __name__ == "__main__":
    unittest.main()