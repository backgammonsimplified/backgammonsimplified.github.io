#!/usr/bin/env python3
"""Browser proof for Task 021 enriched accepted analysis lifecycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = json.loads(
    (ROOT / "site/data/analyzer-task-021-enrichment.json").read_text(encoding="utf-8")
)
MODEL = DOCUMENT["analyses"]["task-021-enriched-checker"]


def capture_errors(page: Page, page_errors: list[str], console_errors: list[str]) -> None:
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )


def wait_for_enriched(page: Page) -> None:
    page.wait_for_function(
        """() => {
          const host = document.querySelector('[data-analysis-id="task-021-enriched-checker"]');
          return host && host.querySelectorAll('[data-bs-analysis-candidate-id]').length === 8;
        }"""
    )


def install_model(page: Page, base_url: str, model: dict, host_id: str) -> None:
    response = page.goto(base_url + "/analyze/results-fixture.html", wait_until="networkidle")
    assert response and response.ok
    page.evaluate(
        """([model, hostId]) => {
          const host = document.createElement('main');
          host.id = hostId;
          document.body.replaceChildren(host);
          document.body.style.margin = '0';
          BMSAnalysisResults.renderPresentation(host, model, {});
        }""",
        [model, host_id],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8872")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    page_errors: list[str] = []
    console_errors: list[str] = []
    responsive: list[dict] = []
    selected_ids: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        capture_errors(page, page_errors, console_errors)
        response = page.goto(
            args.base_url + "/analyze/results-fixture.html", wait_until="networkidle"
        )
        assert response and response.ok
        wait_for_enriched(page)
        host = page.locator('[data-analysis-id="task-021-enriched-checker"]')
        candidates = host.locator("[data-bs-analysis-candidate-id]")
        assert candidates.count() == 8
        assert host.locator(".bs-analysis-results-recommended-badge").count() == 1
        assert "engine recommended" in host.inner_text().lower()
        assert host.locator(".bs-analysis-results-hadd").count() == 1
        assert "HADD did not select either candidate" in host.inner_text()
        assert host.locator(".bs-analysis-results-board-image").get_attribute("src").endswith(
            "candidate-1-movement.svg"
        )
        default_text = host.inner_text()

        for index in range(candidates.count()):
            summary = candidates.nth(index).locator(":scope > summary")
            summary.click()
            selected_ids.append(candidates.nth(index).get_attribute("data-bs-analysis-candidate-id"))
            assert summary.get_attribute("aria-current") == "true"
            assert "Complete GNUID" not in host.inner_text() or host.locator(
                ".bs-analysis-results-preview-facts code"
            ).count() == 1
        assert len(set(selected_ids)) == 8
        assert host.locator(".bs-analysis-results-comparison-table").count() >= 1
        assert "Selected-minus-recommended HADD value difference" in host.inner_text()

        # Original, movement, and result assets remain distinct modes.
        host.get_by_role("button", name="Reset to recommended").click()
        movement_src = host.locator(".bs-analysis-results-board-image").get_attribute("src")
        host.get_by_role("button", name="Original", exact=True).click()
        original_src = host.locator(".bs-analysis-results-board-image").get_attribute("src")
        host.get_by_role("button", name="Movement overlay", exact=True).click()
        assert host.locator(".bs-analysis-results-board-image").get_attribute("src") == movement_src
        host.get_by_role("button", name="Result", exact=True).click()
        result_src = host.locator(".bs-analysis-results-board-image").get_attribute("src")
        assert len({original_src, movement_src, result_src}) == 3

        # Keyboard selection and disclosure preserve focus and exact explanation language.
        first_summary = candidates.nth(0).locator(":scope > summary")
        first_summary.focus()
        page.keyboard.press("End")
        assert candidates.nth(7).locator(":scope > summary").get_attribute("aria-current") == "true"
        explanation = host.locator(".bs-analysis-results-hadd-explanation")
        assert explanation.count() == 1
        explanation.locator(":scope > summary").click()
        assert "exact conditional-logit contribution difference" in explanation.inner_text()
        assert "Unchanged features cancel to exact zero" in explanation.inner_text()
        assert host.locator(".bs-analysis-results-choice-status[aria-live=polite]").count() == 1

        page.reload(wait_until="networkidle")
        wait_for_enriched(page)
        assert page.locator('[data-analysis-id="task-021-enriched-checker"]').inner_text() == default_text
        context.close()

        # Touch candidate and result-board controls.
        touch_context = browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
        )
        touch = touch_context.new_page()
        capture_errors(touch, page_errors, console_errors)
        touch.goto(args.base_url + "/analyze/results-fixture.html", wait_until="networkidle")
        wait_for_enriched(touch)
        touch_host = touch.locator('[data-analysis-id="task-021-enriched-checker"]')
        touch_host.locator("[data-bs-analysis-candidate-id]").nth(1).locator(
            ":scope > summary"
        ).tap()
        touch_host.get_by_role("button", name="Result", exact=True).tap()
        assert touch_host.locator(".bs-analysis-results-board-image").get_attribute("src").endswith(
            "candidate-2-result.svg"
        )
        touch_context.close()

        # Missing preview, missing HADD, and malformed HADD retain native facts.
        missing_preview = json.loads(json.dumps(MODEL))
        missing_preview["candidates"][0]["move_board"] = None
        missing_preview["candidates"][0]["result_board"] = None
        missing_preview["candidates"][0]["preview"] = {
            "status": "unavailable",
            "message": "No accepted preview facts; no board was guessed.",
            "movement_steps": [],
        }
        variant_context = browser.new_context(viewport={"width": 900, "height": 900})
        page = variant_context.new_page()
        capture_errors(page, page_errors, console_errors)
        install_model(page, args.base_url, missing_preview, "missing-preview")
        assert "no board was guessed" in page.locator("#missing-preview").inner_text().lower()
        variant_context.close()

        missing_hadd = json.loads(json.dumps(MODEL))
        missing_hadd.pop("hadd", None)
        for candidate in missing_hadd["candidates"]:
            candidate.pop("hadd_derived_facts", None)
        variant_context = browser.new_context(viewport={"width": 900, "height": 900})
        page = variant_context.new_page()
        capture_errors(page, page_errors, console_errors)
        install_model(page, args.base_url, missing_hadd, "missing-hadd")
        assert page.locator("#missing-hadd .bs-analysis-results-hadd").count() == 0
        assert page.locator("#missing-hadd [data-bs-analysis-candidate-id]").count() == 8
        variant_context.close()

        malformed_hadd = json.loads(json.dumps(MODEL))
        malformed_hadd["candidates"][0]["hadd_derived_facts"]["position_id"] = "wrong"
        variant_context = browser.new_context(viewport={"width": 900, "height": 900})
        page = variant_context.new_page()
        capture_errors(page, page_errors, console_errors)
        install_model(page, args.base_url, malformed_hadd, "malformed-hadd")
        assert page.locator("#malformed-hadd .bs-analysis-results-hadd").count() == 0
        assert page.locator("#malformed-hadd [data-bs-analysis-candidate-id]").count() == 8
        variant_context.close()

        for width in (1440, 768, 390, 320):
            responsive_context = browser.new_context(viewport={"width": width, "height": 1000})
            responsive_page = responsive_context.new_page()
            capture_errors(responsive_page, page_errors, console_errors)
            install_model(responsive_page, args.base_url, MODEL, f"responsive-{width}")
            responsive_page.locator("[data-bs-analysis-candidate-id]").nth(1).locator(
                ":scope > summary"
            ).click()
            dimensions = responsive_page.evaluate(
                """() => ({
                  width: innerWidth,
                  client_width: document.documentElement.clientWidth,
                  scroll_width: document.documentElement.scrollWidth
                })"""
            )
            responsive.append(dimensions)
            assert dimensions["scroll_width"] <= dimensions["client_width"]
            responsive_context.close()
        browser.close()

    assert not page_errors, page_errors
    assert not console_errors, console_errors
    result = {
        "status": "PASS",
        "source_analysis_key": MODEL["canonical_context"]["canonical_decision_id"],
        "candidate_count": 8,
        "selected_candidate_ids": selected_ids,
        "candidate_preview_modes": ["original", "movement", "result"],
        "hadd_sidecar_package_identity_sha256": DOCUMENT["hadd_integration"][
            "sidecar_package_identity_sha256"
        ],
        "pointer": "PASS",
        "touch": "PASS",
        "keyboard": "PASS",
        "accessibility": "PASS",
        "missing_preview": "PASS",
        "missing_hadd": "PASS",
        "malformed_hadd": "PASS",
        "deterministic_rerendering": "PASS",
        "responsive": responsive,
        "page_errors": page_errors,
        "console_errors": console_errors,
        "engine_execution_count": 0,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
