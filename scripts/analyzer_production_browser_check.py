#!/usr/bin/env python3
"""Browser proof for the production Analyzer protocol using an in-page gateway double."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "tests" / "fixtures" / "node-k001-checker-analysis-view.json"

HTML = """
<!doctype html>
<html><body>
<main data-test-analyzer>
  <form data-bs-analyzer-form novalidate>
    <input id="bs-analyzer-gnuid" name="gnuid">
    <label><input type="radio" name="decision" value="checker" checked>Checker</label>
    <label><input type="radio" name="decision" value="cube">Cube</label>
    <fieldset data-bs-checker-dice>
      <select name="die1" data-bs-checker-die><option value="4">4</option></select>
      <select name="die2" data-bs-checker-die><option value="2">2</option></select>
    </fieldset>
    <button type="submit" disabled>Analyze</button>
  </form>
  <section>
    <span data-bs-analyzer-state-label></span>
    <p data-bs-analyzer-state-detail></p>
    <code data-bs-analyzer-key hidden></code>
  </section>
  <div data-bs-analyzer-results></div>
</main>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--browser-executable",
        default=os.environ.get("BS_BROWSER_EXECUTABLE", "/usr/bin/chromium"),
    )
    args = parser.parse_args()
    view = json.loads(VIEW.read_text(encoding="utf-8"))
    page_errors: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        launch_options = {"headless": True, "args": ["--disable-gpu"]}
        if args.browser_executable and Path(args.browser_executable).is_file():
            launch_options["executable_path"] = args.browser_executable
        browser = playwright.chromium.launch(**launch_options)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.set_content(HTML)
        page.add_script_tag(path=str(ROOT / "site" / "assets" / "bs-analysis-results.js"))
        page.add_script_tag(path=str(ROOT / "site" / "assets" / "bs-analyzer-live.js"))
        page.evaluate(
            """(analysisView) => {
              const live = window.BMSAnalyzerLive;
              const key = analysisView.analysis_key;
              window.__proof = {
                submissions: 0,
                submittedRequests: [],
                states: [],
                keys: [],
                statusSequence: []
              };
              const transport = {
                kind: 'production-https-double',
                async submit(request) {
                  window.__proof.submissions += 1;
                  window.__proof.submittedRequests.push(request);
                  const repeat = window.__proof.submissions > 1;
                  window.__proof.statusSequence = repeat
                    ? ['complete']
                    : ['queued', 'running', 'complete'];
                  window.__proof.keys.push(key);
                  return {
                    schema_version: live.SUBMIT_RESPONSE_SCHEMA,
                    analysis_key: key,
                    status: repeat ? 'complete' : 'queued',
                    cache_hit: repeat
                  };
                },
                async status(analysisKey) {
                  const status = window.__proof.statusSequence.shift() || 'complete';
                  return {
                    schema_version: live.STATUS_RESPONSE_SCHEMA,
                    analysis_key: analysisKey,
                    status: status,
                    cache_hit: window.__proof.submissions > 1
                  };
                },
                async lookup(analysisKey) {
                  window.__proof.statusSequence = ['complete'];
                  return {
                    schema_version: live.STATUS_RESPONSE_SCHEMA,
                    analysis_key: analysisKey,
                    status: 'complete',
                    cache_hit: true
                  };
                },
                async result(analysisKey) {
                  return {
                    schema_version: live.RESULT_RESPONSE_SCHEMA,
                    analysis_key: analysisKey,
                    status: 'complete',
                    analysis_view: analysisView
                  };
                }
              };
              const surface = document.querySelector('[data-test-analyzer]');
              new MutationObserver(() => window.__proof.states.push(surface.dataset.bsAnalyzerState))
                .observe(surface, {attributes: true, attributeFilter: ['data-bs-analyzer-state']});
              window.__controller = live.mount(surface, {
                transport: transport,
                pollInterval: 1
              });
            }""",
            view,
        )
        page.wait_for_function(
            "document.querySelector('[data-test-analyzer]').dataset.bsAnalyzerState === 'idle'"
        )

        page.fill("#bs-analyzer-gnuid", "4HPwATDgc/ABMA")
        page.click('button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-test-analyzer]').dataset.bsAnalyzerState === 'invalid'"
        )
        invalid_submissions = page.evaluate("window.__proof.submissions")

        page.fill("#bs-analyzer-gnuid", "4HPwATDgc/ABMA:cAnqAAAAAAAE")
        page.click('button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-test-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        first_states = page.evaluate("window.__proof.states.slice()")
        first_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        first_candidates = page.locator(
            "[data-bs-analyzer-results] .bs-analysis-results-candidate"
        ).count()

        repeat_start = len(first_states)
        page.click('button[type="submit"]')
        page.wait_for_function(
            "document.querySelector('[data-test-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        repeat_states = page.evaluate(f"window.__proof.states.slice({repeat_start})")
        repeat_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()

        page.evaluate(
            "(analysisKey) => window.__controller.lookup(analysisKey)",
            view["analysis_key"],
        )
        page.wait_for_function(
            "document.querySelector('[data-test-analyzer]').dataset.bsAnalyzerState === 'complete'"
        )
        lookup_shared = page.locator(
            "[data-bs-analyzer-results] [data-bs-shared-analysis-presentation]"
        ).count()
        submitted_requests = page.evaluate("window.__proof.submittedRequests")
        keys = page.evaluate("window.__proof.keys")

        public_errors: list[str] = []
        public_console_errors: list[str] = []
        public_api_requests: list[str] = []
        public_page = browser.new_page(viewport={"width": 1440, "height": 1000})
        public_page.on("pageerror", lambda error: public_errors.append(str(error)))
        public_page.on(
            "console",
            lambda message: public_console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        public_page.on(
            "request",
            lambda request: public_api_requests.append(request.url)
            if "/v1/analyzer/" in request.url or "/__bs_local_analysis/" in request.url
            else None,
        )

        rendered_root = (ROOT / "site" / "_site").resolve()

        def fulfill_rendered(route):
            relative = unquote(urlsplit(route.request.url).path).lstrip("/")
            if not relative or relative.endswith("/"):
                relative += "index.html"
            target = (rendered_root / relative).resolve()
            if not target.is_relative_to(rendered_root) or not target.is_file():
                route.fulfill(status=404, body="not found")
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            route.fulfill(status=200, body=target.read_bytes(), content_type=content_type)

        public_page.route("https://backgammonsimplified.github.io/**", fulfill_rendered)
        response = public_page.goto(
            "https://backgammonsimplified.github.io/analyze/",
            wait_until="domcontentloaded",
        )
        if response is None or not response.ok:
            raise RuntimeError("rendered public Analyzer route did not load")
        public_page.wait_for_function(
            "document.querySelector('[data-bs-live-analyzer]').dataset.bsAnalyzerState === 'unavailable'"
        )
        public_button_disabled = public_page.locator(
            '[data-bs-analyzer-form] button[type="submit"]'
        ).is_disabled()
        browser.close()

    proof = {
        "schema_version": "analyzer-task-017-production-browser-double-v1",
        "transport": "bounded production HTTPS protocol double",
        "invalid_input": {
            "submissions": invalid_submissions,
        },
        "first_request": {
            "states": first_states,
            "shared_presentation_count": first_shared,
            "candidate_count": first_candidates,
        },
        "repeat_request": {
            "states": repeat_states,
            "shared_presentation_count": repeat_shared,
        },
        "existing_lookup": {
            "shared_presentation_count": lookup_shared,
        },
        "requests": submitted_requests,
        "keys": keys,
        "page_errors": page_errors,
        "console_errors": console_errors,
        "rendered_public_gate": {
            "state": "unavailable",
            "submit_disabled": public_button_disabled,
            "api_requests": public_api_requests,
            "page_errors": public_errors,
            "console_errors": public_console_errors,
        },
    }
    failures = []
    if invalid_submissions != 0:
        failures.append("invalid input reached transport")
    if not {"queued", "running", "complete"}.issubset(first_states):
        failures.append("lifecycle states")
    if first_shared != 1 or first_candidates < 1 or repeat_shared != 1 or lookup_shared != 1:
        failures.append("shared Results Viewer")
    if proof["keys"] != [view["analysis_key"], view["analysis_key"]]:
        failures.append("duplicate key reuse")
    if "cache-hit" not in repeat_states:
        failures.append("cache-hit state")
    if page_errors or console_errors:
        failures.append("browser errors")
    if (
        not public_button_disabled
        or public_api_requests
        or public_errors
        or public_console_errors
    ):
        failures.append("rendered public fail-closed gate")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, sort_keys=True))
    if failures:
        raise RuntimeError("production browser proof failed: " + ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
