from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "site/assets/bs-analysis-results.js"
LIVE = ROOT / "site/assets/bs-analyzer-live.js"
MATERIALIZER = ROOT / "scripts/analysis/analysis_view_materializer.py"
ANALYZER_PAGE = ROOT / "site/analyze/index.qmd"
FIXTURE_PAGE = ROOT / "site/analyze/results-fixture.qmd"
EVIDENCE = ROOT / "evidence/analyzer-k001/task-019/result-explorer-browser-result.json"


class ResultExplorerContractTests(unittest.TestCase):
    def test_shared_viewer_owns_one_checker_and_cube_explorer(self) -> None:
        viewer = VIEWER.read_text(encoding="utf-8")
        page = ANALYZER_PAGE.read_text(encoding="utf-8")

        self.assertIn("bsResultExplorer", viewer)
        self.assertIn("recommendedCheckerCandidate", viewer)
        self.assertIn("recommendedCubeAction", viewer)
        self.assertIn("Reset to recommended", viewer)
        self.assertIn("Edit original position", viewer)
        self.assertIn("bs-analysis-results.js", (ROOT / "site/includes/bs-scripts.html").read_text(encoding="utf-8"))
        self.assertNotIn("data-bs-analyzer-result-renderer", page)

    def test_browser_does_not_create_backgammon_semantics(self) -> None:
        viewer = VIEWER.read_text(encoding="utf-8")
        live = LIVE.read_text(encoding="utf-8")

        for forbidden in (
            "board_moves",
            "apply_board_moves",
            "generateLegal",
            "legalMoves",
            "parseCheckerNotation",
            "parseGnu",
            "resultingPositionFrom",
        ):
            self.assertNotIn(forbidden, viewer)
            self.assertNotIn(forbidden, live)
        self.assertIn("No candidate board was inferred", viewer)
        self.assertIn("originalBoardSnapshot", live)
        self.assertIn('render: function () { return snapshot.cloneNode(true); }', live)

    def test_materializer_prepares_comparisons_and_preview_disposition(self) -> None:
        source = MATERIALIZER.read_text(encoding="utf-8")

        self.assertIn("prepare_checker_exploration", source)
        self.assertIn("prepare_cube_exploration", source)
        self.assertIn("probability_differences", source)
        self.assertIn('"prepared-movement-and-result"', source)
        self.assertIn("consumers must not infer a resulting board", source)

    def test_current_node_fixtures_remain_fail_closed_for_candidate_boards(self) -> None:
        checker = json.loads(
            (ROOT / "tests/fixtures/node-k001-checker-analysis-view.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(
            all(candidate.get("movement_steps") is None for candidate in checker["checker"]["candidates"])
        )
        self.assertTrue(
            all(candidate["resulting_position_id"] is None for candidate in checker["checker"]["candidates"])
        )

    def test_fixture_route_covers_prepared_result_and_failure_states(self) -> None:
        page = FIXTURE_PAGE.read_text(encoding="utf-8")
        self.assertIn('data-analysis-id="checker-ui-demo"', page)
        self.assertIn('data-analysis-id="cube-ui-demo"', page)
        self.assertIn('data-analysis-id="malformed-ui-demo"', page)

    def test_browser_evidence_is_complete_and_engine_free(self) -> None:
        proof = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(proof["engine_execution_count"], 0)
        self.assertEqual(proof["page_errors"], [])
        self.assertEqual(proof["console_errors"], [])
        self.assertEqual([row["width"] for row in proof["responsive"]], [1440, 768, 390, 320])
        self.assertTrue(all(row["scroll_width"] <= row["client_width"] for row in proof["responsive"]))


if __name__ == "__main__":
    unittest.main()
