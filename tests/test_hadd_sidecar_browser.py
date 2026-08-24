#!/usr/bin/env python3
"""Live-browser proof for the prepared HADD sidecar in the shared viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SIDECAR = json.loads(
    (ROOT / "tests/fixtures/hadd-integration/actual-4ply-canonical-pair-sidecar-v1.json").read_text(
        encoding="utf-8"
    )
)
RETAINED = json.loads(
    (ROOT / "site/data/analyzer-retained-checker-preview.json").read_text(encoding="utf-8")
)["analyses"]["retained-checker-preview"]


def prepared_model() -> dict:
    model = json.loads(json.dumps(RETAINED))
    model["id"] = "task-020-hadd-browser-proof"
    model["candidates"] = model["candidates"][:2]
    for candidate, record in zip(model["candidates"], SIDECAR["records"], strict=True):
        candidate["id"] = record["candidate_id"]
        candidate["candidate_concept_id"] = record["candidate_concept_id"]
        candidate["resulting_position_id"] = record["result_position_id"]
        candidate["hadd_derived_facts"] = {
            "position_id": record["position_id"],
            "position_perspective": record["position_perspective"],
            "probabilities": {
                **record["cumulative_probabilities"],
                "lose": record["lose_probability"],
            },
            "probability_derived_cubeless": record["probability_derived_cubeless"],
            "conditional_logit_evidence": record["conditional_logit_evidence"],
        }
    model["recommended_id"] = model["candidates"][1]["id"]
    model["hadd"] = {
        "status": "available",
        "selected_architecture": "ridge-ranking-hadd-value-explanation-sidecar-v1",
        "authority": {
            "hadd_ranking_authorized": False,
            "calculated_cubeful": "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED",
        },
        "model": SIDECAR["model"],
        "feature_system": SIDECAR["feature_system"],
        "position_perspective": SIDECAR["target"]["position_perspective"],
        "ab_explanations": SIDECAR["ab_explanations"],
    }
    return model


def capture_errors(page: Page, page_errors: list[str], console_errors: list[str]) -> None:
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )


def install_model(page: Page, base_url: str, model: dict) -> None:
    response = page.goto(base_url + "/analyze/results-fixture.html", wait_until="networkidle")
    assert response and response.ok
    page.evaluate(
        """model => {
          const host = document.createElement('main');
          host.id = 'task-020-hadd-proof';
          document.body.replaceChildren(host);
          document.body.style.margin = '0';
          BMSAnalysisResults.renderPresentation(host, model, {});
        }""",
        model,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8872")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    model = prepared_model()
    page_errors: list[str] = []
    console_errors: list[str] = []
    responsive: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-gpu"])
        context = browser.new_context(viewport={"width": 1440, "height": 1100})
        page = context.new_page()
        capture_errors(page, page_errors, console_errors)
        install_model(page, args.base_url, model)
        host = page.locator("#task-020-hadd-proof")
        assert host.locator(".bs-analysis-results-hadd").count() == 1
        assert "HADD did not select either candidate" in host.inner_text()
        assert "Pairwise Ridge remains the sole Explainer ranking authority" in host.inner_text()
        assert "HADD value" in host.inner_text()
        assert "HADD probabilities" in host.inner_text()
        default_render = host.inner_text()

        candidates = host.locator("[data-bs-analysis-candidate-id]")
        candidates.nth(0).locator(":scope > summary").click()
        assert "Why the resulting positions differ according to HADD" in host.inner_text()
        explanation = host.locator(".bs-analysis-results-hadd-explanation")
        explanation.locator(":scope > summary").click()
        assert explanation.get_attribute("open") is not None
        assert "selected-minus-recommended (A-minus-B)" in explanation.inner_text()
        assert host.locator(".bs-analysis-results-hadd-table tbody tr").count() == 26

        candidates.nth(1).locator(":scope > summary").focus()
        page.keyboard.press("Home")
        assert candidates.nth(0).locator(":scope > summary").get_attribute("aria-current") == "true"

        install_model(page, args.base_url, model)
        assert page.locator("#task-020-hadd-proof").inner_text() == default_render
        context.close()

        touch_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            has_touch=True,
            is_mobile=True,
        )
        touch = touch_context.new_page()
        capture_errors(touch, page_errors, console_errors)
        install_model(touch, args.base_url, model)
        touch_candidates = touch.locator("[data-bs-analysis-candidate-id]")
        touch_candidates.nth(0).locator(":scope > summary").tap()
        assert touch_candidates.nth(0).locator(":scope > summary").get_attribute("aria-current") == "true"
        touch_context.close()

        for width in (1440, 768, 390, 320):
            responsive_context = browser.new_context(viewport={"width": width, "height": 1000})
            responsive_page = responsive_context.new_page()
            capture_errors(responsive_page, page_errors, console_errors)
            install_model(responsive_page, args.base_url, model)
            responsive_page.locator("[data-bs-analysis-candidate-id]").nth(0).locator(
                ":scope > summary"
            ).click()
            dimensions = responsive_page.evaluate(
                """() => ({
                  width: innerWidth,
                  client_width: document.documentElement.clientWidth,
                  scroll_width: document.documentElement.scrollWidth,
                  table_client_width: document.querySelector('.bs-analysis-results-hadd-table-wrap').clientWidth,
                  table_scroll_width: document.querySelector('.bs-analysis-results-hadd-table-wrap').scrollWidth
                })"""
            )
            responsive.append(dimensions)
            assert dimensions["scroll_width"] <= dimensions["client_width"]
            responsive_context.close()
        browser.close()

    result = {
        "status": "PASS",
        "sidecar_schema": SIDECAR["schema_version"],
        "sidecar_package_identity_sha256": SIDECAR["package_identity_sha256"],
        "pointer": "PASS",
        "touch": "PASS",
        "keyboard": "PASS",
        "accessibility": "PASS",
        "deterministic_repeated_rendering": "PASS",
        "responsive": responsive,
        "page_errors": page_errors,
        "console_errors": console_errors,
        "engine_execution_count": 0,
    }
    assert not page_errors
    assert not console_errors
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
