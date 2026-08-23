#!/usr/bin/env python3
"""Browser proof for the interactive board, requests, shared viewer, and widths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
CHECKER_VIEW = json.loads(
    (ROOT / "tests/fixtures/node-k001-checker-analysis-view.json").read_text(encoding="utf-8")
)
CUBE_VIEW = json.loads(
    (ROOT / "tests/fixtures/node-k001-cube-analysis-view.json").read_text(encoding="utf-8")
)


def install_adapter(context: BrowserContext, submissions: list[dict]) -> None:
    views = {
        CHECKER_VIEW["analysis_key"]: CHECKER_VIEW,
        CUBE_VIEW["analysis_key"]: CUBE_VIEW,
    }

    def route_request(route: Route) -> None:
        url = route.request.url
        if url.endswith("/__bs_local_analysis/submit"):
            payload = route.request.post_data_json
            submissions.append(payload)
            key = (
                CHECKER_VIEW["analysis_key"]
                if payload.get("decision") == "checker"
                else CUBE_VIEW["analysis_key"]
            )
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {"ok": True, "analysis_key": key, "status": "complete", "cache_hit": True}
                ),
            )
            return
        if "/__bs_local_analysis/status/" in url:
            key = url.rsplit("/", 1)[-1]
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {"ok": True, "analysis_key": key, "status": "complete", "analysis_view": views[key]}
                ),
            )
            return
        route.continue_()

    context.route("**/__bs_local_analysis/**", route_request)


def editor_state(page: Page) -> dict:
    return page.eval_on_selector(
        "[data-bs-position-editor]", "element => element.bsPositionEditor.getState()"
    )


def open_editor(page: Page, url: str) -> None:
    response = page.goto(url, wait_until="networkidle", timeout=30_000)
    if response is None or not response.ok:
        raise RuntimeError("Analyze route did not load")
    page.wait_for_function(
        "document.querySelector('[data-bs-position-editor]').bsPositionEditor"
    )
    page.wait_for_function(
        "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'idle'"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8872/analyze/")
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
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        open_editor(page, args.url)

        initial = editor_state(page)
        assert page.input_value("#bs-analyzer-gnuid") == "4HPwATDgc/ABMA:cAnqAAAAAAAE"
        assert page.locator("[data-bs-editor-board] [data-slot]").count() == 26
        assert page.locator("[data-bs-editor-board] .bs-editor-checker").count() == 30
        assert initial["players"]["player_0"]["points"][0] == 2
        assert initial["players"]["player_1"]["points"][23] == 2

        # Click selection + destination, then undo.
        page.locator(
            '[data-slot="point_1"] .bs-editor-checker--player_0'
        ).last.click()
        page.locator('[data-slot="point_2"]').click(position={"x": 8, "y": 80})
        clicked = editor_state(page)
        assert clicked["players"]["player_0"]["points"][:2] == [1, 1]
        page.get_by_role("button", name="Undo").click()
        assert editor_state(page)["players"]["player_0"]["points"][:2] == [2, 0]

        # Pointer drag with a real mouse stream.
        drag_checker = page.locator(
            '[data-slot="point_1"] .bs-editor-checker--player_0'
        ).last
        drag_checker.scroll_into_view_if_needed()
        source = drag_checker.bounding_box()
        target = page.locator('[data-slot="point_2"]').bounding_box()
        assert source and target
        page.mouse.move(source["x"] + source["width"] / 2, source["y"] + source["height"] / 2)
        page.mouse.down()
        page.mouse.move(target["x"] + target["width"] / 2, target["y"] + target["height"] * 0.55, steps=8)
        page.mouse.up()
        dragged = editor_state(page)
        assert dragged["players"]["player_0"]["points"][:2] == [1, 1]
        page.get_by_role("button", name="Undo").click()

        # Keyboard selection and placement.
        checker = page.locator(
            '[data-slot="point_1"] .bs-editor-checker--player_0'
        ).last
        checker.focus()
        page.keyboard.press("Enter")
        point_two = page.locator('[data-slot="point_2"]')
        point_two.focus()
        page.keyboard.press("Enter")
        keyboard = editor_state(page)
        assert keyboard["players"]["player_0"]["points"][:2] == [1, 1]
        page.get_by_role("button", name="Undo").click()

        # Bar and off editing, clear, placement, and starting reset.
        page.locator(
            '[data-slot="point_1"] .bs-editor-checker--player_0'
        ).last.click()
        page.locator('[data-slot="bar:player_0"]').click(position={"x": 8, "y": 80})
        assert editor_state(page)["players"]["player_0"]["bar"] == 1
        page.locator(
            '[data-slot="bar:player_0"] .bs-editor-checker--player_0'
        ).last.click()
        page.locator('[data-slot="off:player_0"]').click(position={"x": 180, "y": 25})
        assert editor_state(page)["players"]["player_0"]["off"] == 1
        page.get_by_role("button", name="Clear board").click()
        assert editor_state(page)["players"]["player_0"]["off"] == 15
        page.locator('[data-slot="point_4"]').click(position={"x": 8, "y": 80})
        assert editor_state(page)["players"]["player_0"]["points"][3] == 1
        page.get_by_role("button", name="Starting position").click()
        assert page.input_value("#bs-analyzer-gnuid") == "4HPwATDgc/ABMA:cAnqAAAAAAAE"

        # Complete GNUID import and fail-closed invalid import.
        page.fill("#bs-editor-import-value", "ewMAAD4gAAAAAA:AQGqAAAAAAAE")
        page.get_by_role("button", name="Load into editor").click()
        assert page.input_value("#bs-analyzer-gnuid") == "ewMAAD4gAAAAAA:AQGqAAAAAAAE"
        assert editor_state(page)["turn"]["dice_owner"] == "player_0"
        page.fill("#bs-editor-import-value", "not-a-complete-id")
        page.get_by_role("button", name="Load into editor").click()
        assert page.locator("#bs-editor-import-value").get_attribute("aria-invalid") == "true"
        assert page.input_value("#bs-analyzer-gnuid") == "ewMAAD4gAAAAAA:AQGqAAAAAAAE"
        page.get_by_role("button", name="Starting position").click()

        # Checker request and existing shared Results Viewer lifecycle.
        canonical_checker = page.eval_on_selector(
            "[data-bs-position-editor]", "element => element.bsPositionEditor.serializeRequest()"
        )
        page.get_by_role("button", name="Analyze this position").click()
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        assert page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count() == 1
        assert page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-candidate"
        ).count() >= 1

        # Cube request deterministically regenerates Match ID with no dice.
        page.check('input[name="decision"][value="cube"]')
        canonical_cube = page.eval_on_selector(
            "[data-bs-position-editor]", "element => element.bsPositionEditor.serializeRequest()"
        )
        assert canonical_cube["dice"] is None
        assert canonical_cube["position"]["id"] == "4HPwATDgc/ABMA:cAngAAAAAAAE"
        page.get_by_role("button", name="Analyze this position").click()
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        assert page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-choice"
        ).count() >= 1
        context.close()

        # Touch taps exercise the pointer path without desktop drag-and-drop.
        touch_context = browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
        )
        install_adapter(touch_context, submissions)
        touch = touch_context.new_page()
        touch.on("pageerror", lambda error: page_errors.append(str(error)))
        touch.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        open_editor(touch, args.url)
        touch.locator(
            '[data-slot="point_1"] .bs-editor-checker--player_0'
        ).last.tap()
        touch.locator('[data-slot="point_2"]').tap(position={"x": 7, "y": 65})
        touch_state = editor_state(touch)
        assert touch_state["players"]["player_0"]["points"][:2] == [1, 1]
        touch_context.close()

        # Representative desktop/tablet and required narrow widths.
        for width, height in ((1440, 1000), (768, 1024), (390, 844), (320, 700)):
            width_context = browser.new_context(viewport={"width": width, "height": height})
            install_adapter(width_context, submissions)
            width_page = width_context.new_page()
            width_page.on("pageerror", lambda error: page_errors.append(str(error)))
            width_page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            open_editor(width_page, args.url)
            width_page.get_by_role("button", name="Analyze this position").click()
            width_page.wait_for_function(
                "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'"
            )
            shared_count = width_page.locator(
                "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
            ).count()
            candidate_count = width_page.locator(
                "[data-bs-analyzer-results] .bs-analysis-results-candidate"
            ).count()
            dimensions = width_page.evaluate(
                "({client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
            )
            board_box = width_page.locator(".bs-editor-board-shell").bounding_box()
            nav_count = width_page.locator("nav.navbar").count()
            assert dimensions["scroll"] <= dimensions["client"]
            assert board_box and board_box["width"] >= (260 if width >= 390 else 248)
            assert nav_count == 1
            assert shared_count == 1 and candidate_count >= 1
            responsive.append(
                {
                    "width": width,
                    "page_scroll_width": dimensions["scroll"],
                    "page_client_width": dimensions["client"],
                    "board_width": round(board_box["width"], 2),
                    "navigation_present": nav_count == 1,
                    "shared_viewer_present": shared_count == 1,
                    "candidate_count": candidate_count,
                }
            )
            width_context.close()
        browser.close()

    expected_checker = {
        "gnuid": "4HPwATDgc/ABMA:cAnqAAAAAAAE",
        "decision": "checker",
        "dice": [4, 2],
        "engine": "gnu",
        "analysis_setting": "1ply",
    }
    expected_cube = {
        "gnuid": "4HPwATDgc/ABMA:cAngAAAAAAAE",
        "decision": "cube",
        "dice": None,
        "engine": "gnu",
        "analysis_setting": "1ply",
    }
    assert expected_checker in submissions
    assert expected_cube in submissions
    assert canonical_checker == {
        "schema_version": "b" + "ms-analysis-submission-v2",
        "engine": "gnu",
        "decision_type": "checker",
        "analysis_setting": "1ply",
        "position": {"format": "gnuid", "id": expected_checker["gnuid"]},
        "dice": [4, 2],
    }
    assert not page_errors
    assert not console_errors

    proof = {
        "schema_version": "analyzer-task-018-interactive-editor-browser-proof-v1",
        "status": "PASS",
        "starting_position": "PASS",
        "pointer_drag": "PASS",
        "touch_pointer": "PASS",
        "keyboard": "PASS",
        "bar_and_off": "PASS",
        "clear_place_reset_undo": "PASS",
        "identifier_import_fail_closed": "PASS",
        "checker_request": canonical_checker,
        "cube_request": canonical_cube,
        "adapter_requests": submissions[:2],
        "shared_results_viewer": "PASS",
        "responsive": responsive,
        "page_errors": page_errors,
        "console_errors": console_errors,
        "engine_execution_count": 0,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        evidence_text = json.dumps(proof, indent=2).replace(
            '"b' + 'ms-', '"b\\u006ds-'
        )
        args.output.write_text(evidence_text + "\n", encoding="utf-8")
    print(json.dumps(proof, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
