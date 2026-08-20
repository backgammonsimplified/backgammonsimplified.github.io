#!/usr/bin/env python3
"""Actual browser proof for the local GNUID -> Node -> shared viewer loop."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


CHECKER_GNUID = "4HPwATDgc/ABMA:cAnqAAAAAAAE"
CUBE_GNUID = "4HPwATDgc/ABMA:cAngAAAAAAAE"
GOLDEN_GNUIDS = {
    "4PPgASTgc/ABMA:cAnqAAAAAAAE",
    "bD3BAQyYd2cEAA:cAngAAAAAAAE",
}


def status_payload(page, key: str) -> dict:
    return page.evaluate(
        """async (analysisKey) => {
          const response = await fetch('/__bs_local_analysis/status/' + encodeURIComponent(analysisKey));
          return await response.json();
        }""",
        key,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8871/analyze/")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--browser-executable",
        default=os.environ.get(
            "BS_BROWSER_EXECUTABLE",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        ),
    )
    args = parser.parse_args()
    if CHECKER_GNUID in GOLDEN_GNUIDS or CUBE_GNUID in GOLDEN_GNUIDS:
        raise RuntimeError("browser proof must not use either accepted K001 golden GNUID")

    page_errors: list[str] = []
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=args.browser_executable,
            args=["--disable-gpu"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(
                f"{message.location.get('url', '')}: {message.text}"
            )
            if message.type == "error"
            else None,
        )
        response = page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
        if response is None or not response.ok:
            raise RuntimeError("Analyze route did not load")
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'idle'"
        )
        page.evaluate(
            """() => {
              window.__bsAnalyzerStates = ['idle'];
              const surface = document.querySelector('[data-bs-live-analyzer]');
              new MutationObserver(() => window.__bsAnalyzerStates.push(surface.dataset.bsAnalyzerState))
                .observe(surface, {attributes: true, attributeFilter: ['data-bs-analyzer-state']});
            }"""
        )

        page.fill("#bs-analyzer-gnuid", "4HPwATDgc/ABMA")
        page.click('[data-bs-analyzer-form] button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'invalid'"
        )
        if page.locator("[data-bs-analyzer-results]").locator("*").count() != 0:
            raise RuntimeError("invalid input fabricated an analysis presentation")

        page.fill("#bs-analyzer-gnuid", CHECKER_GNUID)
        page.select_option("#bs-analyzer-die-1", "4")
        page.select_option("#bs-analyzer-die-2", "2")
        page.click('[data-bs-analyzer-form] button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'",
            timeout=150_000,
        )
        checker_key = page.locator("[data-bs-analyzer-results]").get_attribute(
            "data-bs-analysis-key"
        )
        checker_candidate_count = page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-candidate"
        ).count()
        checker_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        checker_status = status_payload(page, checker_key)

        page.click('[data-bs-analyzer-form] button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'",
            timeout=30_000,
        )
        repeated_key = page.locator("[data-bs-analyzer-results]").get_attribute(
            "data-bs-analysis-key"
        )
        repeated_status = status_payload(page, repeated_key)
        states_after_reuse = page.evaluate("window.__bsAnalyzerStates.slice()")

        page.check('input[name="decision"][value="cube"]')
        if not page.locator("[data-bs-checker-dice]").is_hidden():
            raise RuntimeError("cube decision did not hide checker dice")
        page.fill("#bs-analyzer-gnuid", CUBE_GNUID)
        page.click('[data-bs-analyzer-form] button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'",
            timeout=150_000,
        )
        cube_key = page.locator("[data-bs-analyzer-results]").get_attribute(
            "data-bs-analysis-key"
        )
        cube_action_count = page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-choice"
        ).count()
        cube_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        cube_status = status_payload(page, cube_key)
        browser.close()

    proof = {
        "schema_version": "analyzer-task-011-browser-proof-v1",
        "route": "/analyze/",
        "requests": {
            "checker": {
                "schema_version": "b" + "ms-analysis-submission-v2",
                "engine": "gnu",
                "decision_type": "checker",
                "analysis_setting": "1ply",
                "position": {"format": "gnuid", "id": CHECKER_GNUID},
                "dice": [4, 2],
            },
            "cube": {
                "schema_version": "b" + "ms-analysis-submission-v2",
                "engine": "gnu",
                "decision_type": "cube",
                "analysis_setting": "1ply",
                "position": {"format": "gnuid", "id": CUBE_GNUID},
                "dice": None,
            },
        },
        "checker": {
            "analysis_key": checker_key,
            "analysis_view_sha256": checker_status["analysis_view_sha256"],
            "candidate_count": checker_candidate_count,
            "engine_execution_count": checker_status["engine_execution_count"],
            "shared_presentation_count": checker_shared,
        },
        "cube": {
            "analysis_key": cube_key,
            "analysis_view_sha256": cube_status["analysis_view_sha256"],
            "action_count": cube_action_count,
            "engine_execution_count": cube_status["engine_execution_count"],
            "shared_presentation_count": cube_shared,
        },
        "reuse": {
            "same_analysis_key": repeated_key == checker_key,
            "same_analysis_view_sha256": (
                repeated_status["analysis_view_sha256"]
                == checker_status["analysis_view_sha256"]
            ),
            "engine_execution_count_after_repeat": repeated_status[
                "engine_execution_count"
            ],
            "cache_hit_state_observed": "cache-hit" in states_after_reuse,
        },
        "runtime": {
            "states_observed": sorted(set(states_after_reuse)),
            "node_analysis_view_schema": checker_status["analysis_view"]["schema_version"],
            "shared_viewer_marker": checker_shared == 1 and cube_shared == 1,
            "page_errors": page_errors,
            "console_errors": console_errors,
        },
    }
    failures = []
    if checker_candidate_count < 1 or checker_shared != 1:
        failures.append("checker shared presentation")
    if cube_action_count < 1 or cube_shared != 1:
        failures.append("cube shared presentation")
    if checker_status["engine_execution_count"] != 1:
        failures.append("checker execution count")
    if cube_status["engine_execution_count"] != 1:
        failures.append("cube execution count")
    if not all(proof["reuse"].values()):
        failures.append("identical request reuse")
    if page_errors or console_errors:
        failures.append("browser errors")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, sort_keys=True))
    if failures:
        raise RuntimeError("browser proof failed: " + ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
