#!/usr/bin/env python3
"""Browser proof for Task 019 result exploration and candidate comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
CHECKER_VIEW = json.loads(
    (ROOT / "tests/fixtures/node-k001-checker-analysis-view.json").read_text(
        encoding="utf-8"
    )
)
CUBE_VIEW = json.loads(
    (ROOT / "tests/fixtures/node-k001-cube-analysis-view.json").read_text(
        encoding="utf-8"
    )
)


def install_adapter(context: BrowserContext, submissions: list[dict]) -> None:
    views = {
        CHECKER_VIEW["analysis_key"]: CHECKER_VIEW,
        CUBE_VIEW["analysis_key"]: CUBE_VIEW,
    }

    def route_request(route: Route) -> None:
        if route.request.url.endswith("/__bs_local_analysis/submit"):
            payload = route.request.post_data_json
            submissions.append(payload)
            view = CHECKER_VIEW if payload["decision"] == "checker" else CUBE_VIEW
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "analysis_key": view["analysis_key"],
                        "status": "complete",
                        "cache_hit": True,
                    }
                ),
            )
            return
        if "/__bs_local_analysis/status/" in route.request.url:
            key = route.request.url.rsplit("/", 1)[-1]
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "analysis_key": key,
                        "status": "complete",
                        "analysis_view": views[key],
                    }
                ),
            )
            return
        route.continue_()

    context.route("**/__bs_local_analysis/**", route_request)


def capture_errors(page: Page, page_errors: list[str], console_errors: list[str]) -> None:
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )


def wait_for_fixture(page: Page) -> None:
    page.wait_for_function(
        """() => {
          const hosts = [...document.querySelectorAll('[data-bs-analysis-results]')];
          return hosts.length >= 8 && hosts.every((host) => host.children.length > 0);
        }"""
    )


def fixture_snapshot(page: Page) -> dict:
    checker = page.locator(
        '[data-analysis-id="sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"]'
    )
    cube = page.locator('[data-analysis-id="cube-ui-demo"]')
    return {
        "checker_candidates": checker.locator(
            "[data-bs-analysis-candidate-id]"
        ).count(),
        "checker_recommended": checker.locator(
            ".bs-analysis-results-recommended-badge"
        ).all_text_contents(),
        "checker_board": checker.locator(
            ".bs-analysis-results-board-image"
        ).get_attribute("src"),
        "cube_pressed": cube.locator(
            '.bs-analysis-results-choice[aria-pressed="true"]'
        ).get_attribute("data-bs-analysis-result-choice"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8872")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    page_errors: list[str] = []
    console_errors: list[str] = []
    submissions: list[dict] = []
    responsive: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        install_adapter(context, submissions)
        page = context.new_page()
        capture_errors(page, page_errors, console_errors)

        response = page.goto(
            args.base_url + "/analyze/results-fixture.html",
            wait_until="networkidle",
        )
        assert response and response.ok
        wait_for_fixture(page)

        node_checker = page.locator(
            '[data-analysis-id="sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"]'
        )
        candidates = node_checker.locator("[data-bs-analysis-candidate-id]")
        assert candidates.count() == 8
        assert node_checker.locator(
            ".bs-analysis-results-recommended-badge"
        ).count() == 1
        assert "engine recommended" in node_checker.locator(
            ".bs-analysis-results-recommended-badge"
        ).inner_text().lower()
        assert node_checker.locator(".bs-analysis-results-board-image").get_attribute(
            "src"
        ).endswith("/node-k001/checker/candidate-1.svg")

        # Pointer selection reaches every returned checker candidate.
        selected_ids: list[str] = []
        for index in range(candidates.count()):
            summary = candidates.nth(index).locator(":scope > summary")
            summary.click()
            candidate_id = candidates.nth(index).get_attribute(
                "data-bs-analysis-candidate-id"
            )
            assert summary.get_attribute("aria-current") == "true"
            selected_ids.append(candidate_id)
        assert len(set(selected_ids)) == 8
        assert node_checker.locator(
            ".bs-analysis-results-comparison-table"
        ).count() == 1

        # Original/result toggle and reset retain the explicit recommendation.
        node_checker.get_by_role("button", name="Reset to recommended").click()
        assert candidates.nth(0).locator(":scope > summary").get_attribute(
            "aria-current"
        ) == "true"
        node_checker.get_by_role("button", name="Original", exact=True).click()
        assert node_checker.locator(".bs-analysis-results-board-image").get_attribute(
            "src"
        ).endswith("/node-k001/checker/starting.svg")
        node_checker.get_by_role("button", name="Movement + result").click()
        assert node_checker.locator(".bs-analysis-results-board-image").get_attribute(
            "src"
        ).endswith("/node-k001/checker/candidate-1.svg")

        # Arrow navigation updates selection and focus without closing disclosure.
        first_summary = candidates.nth(0).locator(":scope > summary")
        first_summary.focus()
        page.keyboard.press("ArrowDown")
        assert candidates.nth(1).locator(":scope > summary").get_attribute(
            "aria-current"
        ) == "true"
        assert candidates.nth(1).locator(":scope > summary").evaluate(
            "element => element === document.activeElement"
        )

        # A separately supplied result board is distinct from the original board.
        synthetic_checker = page.locator('[data-analysis-id="checker-ui-demo"]')
        assert synthetic_checker.get_by_role("button", name="Result", exact=True).get_attribute(
            "aria-pressed"
        ) == "true"
        result_src = synthetic_checker.locator(
            ".bs-analysis-results-board-image"
        ).get_attribute("src")
        synthetic_checker.get_by_role("button", name="Original", exact=True).click()
        original_src = synthetic_checker.locator(
            ".bs-analysis-results-board-image"
        ).get_attribute("src")
        assert result_src != original_src
        synthetic_checker.get_by_role("button", name="Result", exact=True).click()

        # Missing values and a prepared bar entry remain readable and fail closed.
        synthetic_candidates = synthetic_checker.locator(
            "[data-bs-analysis-candidate-id]"
        )
        synthetic_candidates.nth(2).locator(":scope > summary").click()
        facts = synthetic_checker.locator(".bs-analysis-results-preview-facts")
        assert "bar to point 24" in facts.inner_text()
        assert "no resulting board was inferred" in facts.inner_text().lower()
        assert "Not supplied" in synthetic_candidates.nth(2).inner_text()
        assert synthetic_checker.locator(
            ".bs-analysis-results-board-image"
        ).get_attribute("src") == original_src

        # Cube selection uses the same factual recommended-vs-selected workspace.
        synthetic_cube = page.locator('[data-analysis-id="cube-ui-demo"]')
        assert "recommended action" in synthetic_cube.inner_text().lower()
        synthetic_cube.get_by_role("button", name="Roll / No double", exact=False).click()
        assert synthetic_cube.locator(
            ".bs-analysis-results-comparison-table"
        ).count() == 1
        assert "selected action" in synthetic_cube.inner_text().lower()
        synthetic_cube.get_by_role("button", name="Reset to recommended").click()
        assert synthetic_cube.locator(
            ".bs-analysis-results-comparison-table"
        ).count() == 0

        assert page.locator(".bs-analysis-results-error[role=alert]").count() == 2
        page.reload(wait_until="networkidle")
        wait_for_fixture(page)
        first_render = fixture_snapshot(page)
        page.reload(wait_until="networkidle")
        wait_for_fixture(page)
        assert fixture_snapshot(page) == first_render
        context.close()

        # Analyzer request -> fixture result -> explorer -> editor -> resubmit.
        analyzer_context = browser.new_context(viewport={"width": 1280, "height": 900})
        install_adapter(analyzer_context, submissions)
        analyzer = analyzer_context.new_page()
        capture_errors(analyzer, page_errors, console_errors)
        analyzer.goto(args.base_url + "/analyze/", wait_until="networkidle")
        analyzer.get_by_role("button", name="Analyze this position").click()
        analyzer.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        live_results = analyzer.locator("[data-bs-analyzer-results]")
        assert live_results.locator("[data-bs-result-explorer=checker]").count() == 1
        assert live_results.get_by_role("img", name="Original analyzed position").count() == 1
        assert "No candidate board was inferred" in live_results.inner_text()
        live_candidates = live_results.locator("[data-bs-analysis-candidate-id]")
        live_candidates.nth(0).locator(":scope > summary").focus()
        analyzer.keyboard.press("End")
        assert live_candidates.nth(-1).locator(":scope > summary").get_attribute(
            "aria-current"
        ) == "true"
        live_results.get_by_role("button", name="Edit original position").click()
        assert analyzer.locator("[data-bs-analyzer-form]").evaluate(
            "form => form.contains(document.activeElement)"
        )
        analyzer.get_by_role("button", name="Flip view").click()
        assert analyzer.locator("[data-bs-live-analyzer]").get_attribute(
            "data-bs-analyzer-state"
        ) == "edited"
        analyzer.get_by_role("button", name="Analyze this position").click()
        analyzer.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        analyzer.check('input[name="decision"][value="cube"]')
        analyzer.get_by_role("button", name="Analyze this position").click()
        analyzer.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        assert live_results.locator("[data-bs-result-explorer=cube]").count() == 1
        assert "recommended action" in live_results.inner_text().lower()
        analyzer_context.close()

        # Touch selection and required responsive widths.
        touch_context = browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
        )
        touch = touch_context.new_page()
        capture_errors(touch, page_errors, console_errors)
        touch.goto(args.base_url + "/analyze/results-fixture.html", wait_until="networkidle")
        wait_for_fixture(touch)
        touch_checker = touch.locator('[data-analysis-id="checker-ui-demo"]')
        touch_checker.locator("[data-bs-analysis-candidate-id]").nth(1).locator(
            ":scope > summary"
        ).tap()
        assert touch_checker.locator(
            "[data-bs-analysis-candidate-id]"
        ).nth(1).locator(":scope > summary").get_attribute("aria-current") == "true"
        touch_context.close()

        for width, height in ((1440, 1000), (768, 1024), (390, 844), (320, 700)):
            width_context = browser.new_context(viewport={"width": width, "height": height})
            width_page = width_context.new_page()
            capture_errors(width_page, page_errors, console_errors)
            width_page.goto(
                args.base_url + "/analyze/results-fixture.html", wait_until="networkidle"
            )
            wait_for_fixture(width_page)
            dimensions = width_page.evaluate(
                "({client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
            )
            assert dimensions["scroll"] <= dimensions["client"]
            explorer = width_page.locator("[data-bs-result-explorer=checker]").first
            box = explorer.bounding_box()
            assert box and box["width"] <= width + 0.5
            responsive.append(
                {
                    "width": width,
                    "client_width": dimensions["client"],
                    "scroll_width": dimensions["scroll"],
                    "explorer_width": round(box["width"], 2),
                }
            )
            width_context.close()
        browser.close()

    assert not page_errors, page_errors
    assert not console_errors, console_errors
    proof = {
        "schema_version": "analyzer-task-019-result-explorer-browser-proof-v1",
        "status": "PASS",
        "checker_candidates": 8,
        "recommended_identification": "PASS",
        "candidate_selection": "PASS",
        "original_board": "PASS",
        "prepared_movement_and_result_board": "PASS",
        "separate_result_board": "PASS",
        "bar_movement_fact": "PASS",
        "missing_preview_fail_closed": "PASS",
        "comparison_deltas": "PASS",
        "cube_exploration": "PASS",
        "editor_result_round_trip": "PASS",
        "pointer": "PASS",
        "touch": "PASS",
        "keyboard": "PASS",
        "accessibility_state": "PASS",
        "malformed_fail_closed": "PASS",
        "deterministic_repeated_render": "PASS",
        "responsive": responsive,
        "page_errors": page_errors,
        "console_errors": console_errors,
        "submissions": submissions,
        "engine_execution_count": 0,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
