#!/usr/bin/env python3
"""Headless product proof for accepted server lookup, submission, and reuse."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


EXISTING_TASK_012_KEY = (
    "sha256-a7b55f2d72d95d769c7c7428198242c3bfbd16ca92e596a51fce0aa72d7b9782"
)
MISSING_GNUID = "PAAAICMAAAAAAA:cAngAAAAAAAE"
GOLDEN_GNUIDS = {
    "4PPgASTgc/ABMA:cAnqAAAAAAAE",
    "bD3BAQyYd2cEAA:cAngAAAAAAAE",
}


def endpoint_payload(page: Page, endpoint: str) -> dict:
    return page.evaluate(
        """async (url) => {
          const response = await fetch(url, {credentials: 'same-origin'});
          return await response.json();
        }""",
        endpoint,
    )


def wait_complete(page: Page, timeout: int) -> None:
    page.wait_for_function(
        "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'complete'",
        timeout=timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8871/analyze/")
    parser.add_argument("--existing-key", default=EXISTING_TASK_012_KEY)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--browser-executable",
        default=os.environ.get("BS_BROWSER_EXECUTABLE", "/usr/bin/chromium"),
    )
    args = parser.parse_args()
    if MISSING_GNUID in GOLDEN_GNUIDS:
        raise RuntimeError("server browser proof must not use an accepted K001 golden GNUID")

    page_errors: list[str] = []
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=args.browser_executable,
            args=["--disable-gpu"],
        )

        lookup_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        lookup_page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = lookup_page.goto(
            args.url + "?analysis_key=" + args.existing_key,
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        if response is None or not response.ok:
            raise RuntimeError("Analyze lookup route did not load")
        wait_complete(lookup_page, 60_000)
        existing_lookup = endpoint_payload(
            lookup_page,
            "/__bs_local_analysis/lookup/" + args.existing_key,
        )
        existing_shared = lookup_page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        existing_candidates = lookup_page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-candidate"
        ).count()

        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        response = page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
        if response is None or not response.ok:
            raise RuntimeError("Analyze submission route did not load")
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

        submission_requests: list[str] = []
        page.on(
            "request",
            lambda request: submission_requests.append(request.url)
            if "/__bs_local_analysis/submit" in request.url
            else None,
        )
        page.fill("#bs-analyzer-gnuid", "4HPwATDgc/ABMA")
        page.click('[data-bs-analyzer-form] button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'invalid'"
        )
        failure_state = page.locator("[data-bs-live-analyzer]").get_attribute(
            "data-bs-analyzer-state"
        )
        failure_presentations = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        failure_submissions = len(submission_requests)

        page.check('input[name="decision"][value="cube"]')
        page.fill("#bs-analyzer-gnuid", MISSING_GNUID)
        page.click('[data-bs-analyzer-form] button[type="submit"]')
        wait_complete(page, 180_000)
        first_states = page.evaluate("window.__bsAnalyzerStates.slice()")
        new_key = page.locator("[data-bs-analyzer-results]").get_attribute(
            "data-bs-analysis-key"
        )
        first_status = endpoint_payload(
            page, "/__bs_local_analysis/status/" + new_key
        )
        first_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        first_actions = page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-choice"
        ).count()

        repeat_start = len(first_states)
        page.click('[data-bs-analyzer-form] button[type="submit"]')
        wait_complete(page, 60_000)
        all_states = page.evaluate("window.__bsAnalyzerStates.slice()")
        repeat_states = all_states[repeat_start:]
        repeat_key = page.locator("[data-bs-analyzer-results]").get_attribute(
            "data-bs-analysis-key"
        )
        repeat_status = endpoint_payload(
            page, "/__bs_local_analysis/status/" + repeat_key
        )
        repeat_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        browser.close()

    proof = {
        "schema_version": "analyzer-task-016-server-browser-proof-v1",
        "route": "/analyze/",
        "existing_lookup": {
            "analysis_key": args.existing_key,
            "lookup_disposition": existing_lookup.get("lookup_disposition"),
            "server_source": existing_lookup.get("server_source"),
            "status": existing_lookup.get("status"),
            "analysis_view_sha256": existing_lookup.get("analysis_view_sha256"),
            "result_sha256": existing_lookup.get("result_sha256"),
            "historical_engine_execution_count": existing_lookup.get(
                "engine_execution_count"
            ),
            "candidate_count": existing_candidates,
            "shared_presentation_count": existing_shared,
        },
        "missing_request": {
            "schema_version": "b" + "ms-analysis-submission-v2",
            "engine": "gnu",
            "decision_type": "cube",
            "analysis_setting": "1ply",
            "position": {"format": "gnuid", "id": MISSING_GNUID},
            "dice": None,
        },
        "first_execution": {
            "analysis_key": new_key,
            "status": first_status.get("status"),
            "engine_execution_count": first_status.get("engine_execution_count"),
            "analysis_view_sha256": first_status.get("analysis_view_sha256"),
            "result_sha256": first_status.get("result_sha256"),
            "states_observed": first_states,
            "action_count": first_actions,
            "shared_presentation_count": first_shared,
        },
        "repeat": {
            "analysis_key": repeat_key,
            "same_analysis_key": repeat_key == new_key,
            "engine_execution_count": repeat_status.get("engine_execution_count"),
            "same_analysis_view_sha256": repeat_status.get("analysis_view_sha256")
            == first_status.get("analysis_view_sha256"),
            "same_result_sha256": repeat_status.get("result_sha256")
            == first_status.get("result_sha256"),
            "states_observed": repeat_states,
            "cache_hit_state_observed": "cache-hit" in repeat_states,
            "shared_presentation_count": repeat_shared,
        },
        "failure": {
            "state": failure_state,
            "submission_count": failure_submissions,
            "shared_presentation_count": failure_presentations,
        },
        "runtime": {
            "page_errors": page_errors,
            "console_errors": console_errors,
        },
    }
    failures = []
    if existing_lookup.get("status") != "complete" or existing_shared != 1:
        failures.append("accepted existing lookup")
    if first_status.get("status") != "complete":
        failures.append("missing request completion")
    if first_status.get("engine_execution_count") != 1:
        failures.append("first native execution count")
    if not {"queued", "running", "complete"}.issubset(first_states):
        failures.append("queued/running/complete display")
    if first_shared != 1 or first_actions < 1:
        failures.append("shared Results Viewer")
    if repeat_key != new_key or repeat_status.get("engine_execution_count") != 1:
        failures.append("repeat execution reuse")
    if not proof["repeat"]["same_analysis_view_sha256"] or not proof["repeat"][
        "same_result_sha256"
    ]:
        failures.append("repeat factual identity")
    if "cache-hit" not in repeat_states or repeat_shared != 1:
        failures.append("repeat disposition/viewer")
    if failure_state != "invalid" or failure_submissions != 0 or failure_presentations != 0:
        failures.append("fail-closed invalid input")
    if page_errors or console_errors:
        failures.append("browser errors")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, sort_keys=True))
    if failures:
        raise RuntimeError("server browser proof failed: " + ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
