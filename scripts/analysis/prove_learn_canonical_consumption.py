#!/usr/bin/env python3
"""Prove that the real Learn routes consume the accepted Canonical-derived view.

This proof reads committed Task 008/009 evidence and a rendered site. It does
not invoke GNU, Node analysis, DuckDB, or a Canonical writer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "analyzer-learn-canonical-consumption-proof-v1"
TASK = "prove-learn-consumption-from-server-derived-analysis-v1"
STARTING_HEAD = "c69b7a599baf2f8b88491110a95df7167a09cdd3"

CANONICAL_URL = "/data/analyzer-node-k001-lesson-preview.json"
LOCAL_AUTHORING_URL = "/data/analyzer-node-k001-local-authoring-preview.json"
CHECKER_ID = "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"
CUBE_ID = "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"
EXCLUDED_CUBE_ID = "sha256-ba87405bf38017214424d71b1e3d1299ed323101db8893f2aa430054167a6414"
CHECKER_ROUTE = "/learn/cube/why-is-25-percent-the-basic-take-point.html"
CUBE_ROUTE = "/learn/cube/what-the-cube-is-asking.html"

CHECKER_CANDIDATES = [
    "cebe056b9fba14bb3a4fd58aa8f3e3d5430d98045ff21850c994bd24add37745",
    "44f91cbe042d6b615184f62d32d59337e3a35f709b875f11958bfdc2bf421477",
    "2940ef714c8cff1a3895543725738b43d64264c425968c3448c0a251a0e1542d",
    "5fd8fc14885e320a36c7769bf3127c2662c3d9f3164418872c7696be426460c8",
    "3c03cda00d76d9fbb7acc6d54dc78d2079fee4c1f10c946e4b2f3b8866a0027b",
    "09806fcf119b0f5742865fd64f987cecc00a28338b429a89a8098aacca864cf0",
    "6a2d4cbf49af863c3ca425061a616d836ef10e80429714fba0829180d2ec5837",
    "96d18ebbdcf54e9eb07265464db5b9e2100c5c0c6ae6c46e90a8a3a2258862d2",
]
CUBE_ACTIONS = [
    "5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f",
    "7ace038e9967b27f4c954b1a9b813f991f963e054e3994d6796d3cfd4c27a936",
    "b0b5a1bdb5eebe7e4dd2ead2e48b22827ff870401381fe21a6f4d3eb0308e1ad",
]
PACKAGES = {
    "checker": {
        "package_id": "1a38c5a48214a4ea156d1896b8ea09bcdce75880077fabb2fc516c5685ff259c",
        "manifest_sha256": "bcd84099792e5679dd997ea4aa85f0d3ee217f5df79b2adc989b5938c6d2988e",
    },
    "cube": {
        "package_id": "bde4011fa40a384168a49529db7192e039a15252d4a2ab481c7b2fecfa98806b",
        "manifest_sha256": "dbe6bcb41ac8ecdb52ffa33a72cc97bc47fae9c0f9bc67a9bc8559c197c2d11a",
    },
}
INPUT_HASHES = {
    "lesson_view": (
        "site/data/analyzer-node-k001-lesson-preview.json",
        "7af39183ca9e5f696d0fe3d4ce1e4729b58f4a95489d910490c6b16e1b4bb404",
    ),
    "checker_read_set": (
        "evidence/analyzer-k001/task-008/checker-read-set.json",
        "7a9de2204ecacbefb19cbc4c18188504fc6979a9c0bd46b2f76e52ed6d418cdb",
    ),
    "cube_read_set": (
        "evidence/analyzer-k001/task-008/cube-read-set.json",
        "3d0176636402a97aea237d6126f988c6b98ff1f44b5645747512782fb585c0d1",
    ),
    "materialization_evidence": (
        "evidence/analyzer-k001/task-008/materialization-evidence.json",
        "8c1545c202930efe325d4d5aabe609f33f864a22b38ecd665d82dbc4ca552975",
    ),
    "task_009_equivalence": (
        "evidence/analyzer-k001/task-009/equivalence-result.json",
        "ed8d97b1de56a190f08751a5ce158b98066f26d11aa61673cac50ca549b55368",
    ),
}
SOURCE_PATHS = {
    "checker_qmd": "site/learn/cube/why-is-25-percent-the-basic-take-point.qmd",
    "cube_qmd": "site/learn/cube/what-the-cube-is-asking.qmd",
    "lesson_adapter": "site/assets/bs-lesson-analysis.js",
    "shared_viewer": "site/assets/bs-analysis-results.js",
}


class ProofError(RuntimeError):
    """The proof input or runtime behavior does not satisfy the contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def load_json_bytes(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ProofError(f"invalid JSON in {name}: {error}") from error
    if not isinstance(value, dict):
        raise ProofError(f"{name} must contain one JSON object")
    return value


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read(root: Path, relative: str, overrides: dict[str, bytes] | None) -> bytes:
    if overrides and relative in overrides:
        return overrides[relative]
    try:
        return (root / relative).read_bytes()
    except OSError as error:
        raise ProofError(f"unable to read {relative}: {error}") from error


def _check(checks: list[dict[str, Any]], name: str, condition: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})


def collect_static_proof(
    root: Path = ROOT, overrides: dict[str, bytes] | None = None
) -> dict[str, Any]:
    """Validate exact committed lineage and presentation-only source contracts."""
    checks: list[dict[str, Any]] = []
    inputs: dict[str, dict[str, str]] = {}
    payloads: dict[str, bytes] = {}
    for name, (path, expected_hash) in INPUT_HASHES.items():
        payload = _read(root, path, overrides)
        payloads[name] = payload
        actual_hash = sha256_bytes(payload)
        inputs[name] = {"path": path, "sha256": actual_hash, "accepted_sha256": expected_hash}
        _check(checks, f"accepted-hash:{name}", actual_hash == expected_hash, f"{path} -> {actual_hash}")

    sources = {name: _read(root, path, overrides).decode("utf-8") for name, path in SOURCE_PATHS.items()}
    checker_qmd = sources["checker_qmd"]
    cube_qmd = sources["cube_qmd"]
    _check(
        checks,
        "checker-source-binding",
        f'data-bs-analysis-src="{CANONICAL_URL}"' in checker_qmd
        and f'data-bs-analysis-id="{CHECKER_ID}"' in checker_qmd
        and LOCAL_AUTHORING_URL not in checker_qmd,
        "checker Learn host binds the accepted analysis to the Canonical-derived URL only",
    )
    _check(
        checks,
        "cube-source-binding",
        f'data-bs-analysis-src="{CANONICAL_URL}"' in cube_qmd
        and f'data-bs-analysis-id="{CUBE_ID}"' in cube_qmd
        and all(action in cube_qmd for action in CUBE_ACTIONS)
        and LOCAL_AUTHORING_URL not in cube_qmd,
        "cube Learn host binds the accepted analysis and three Canonical action IDs",
    )

    lesson = load_json_bytes(payloads["lesson_view"], INPUT_HASHES["lesson_view"][0])
    analyses = lesson.get("analyses")
    exact_ids = isinstance(analyses, dict) and set(analyses) == {CHECKER_ID, CUBE_ID}
    _check(checks, "lesson-exact-analysis-set", exact_ids, "document contains exactly checker and accepted Learn cube")
    if not exact_ids:
        analyses = {} if not isinstance(analyses, dict) else analyses
    checker = analyses.get(CHECKER_ID, {})
    cube = analyses.get(CUBE_ID, {})
    _check(
        checks,
        "checker-semantic-surface",
        isinstance(checker, dict)
        and [item.get("id") for item in checker.get("candidates", []) if isinstance(item, dict)] == CHECKER_CANDIDATES
        and checker.get("metadata", {}).get("recommendation") == "8/4 6/4",
        "accepted eight candidates and recommendation are present in source order",
    )
    _check(
        checks,
        "cube-semantic-surface",
        isinstance(cube, dict)
        and [item.get("id") for item in cube.get("actions", []) if isinstance(item, dict)] == CUBE_ACTIONS
        and cube.get("metadata", {}).get("recommendation") == "Double, take",
        "accepted three actions and recommendation are present in source order",
    )
    lesson_authority_ok = all(
        isinstance(analyses.get(analysis_id), dict)
        and analyses[analysis_id].get("canonical_context", {}).get("package")
        == {
            "conformance_status": "verified-canonical-v1",
            "manifest_sha256": PACKAGES[kind]["manifest_sha256"],
            "package_id": PACKAGES[kind]["package_id"],
            "profile_id": "canonical-analysis-parquet-v1",
        }
        for kind, analysis_id in (("checker", CHECKER_ID), ("cube", CUBE_ID))
    )
    _check(
        checks,
        "lesson-document-authority-binding",
        lesson_authority_ok,
        "each analysis carries its exact verified package and manifest identity",
    )
    lesson_text = payloads["lesson_view"].decode("utf-8")
    _check(
        checks,
        "excluded-cube-absent",
        EXCLUDED_CUBE_ID not in lesson_text and EXCLUDED_CUBE_ID not in checker_qmd and EXCLUDED_CUBE_ID not in cube_qmd,
        "excluded Package A cube is absent from the Learn inputs",
    )

    materialization = load_json_bytes(payloads["materialization_evidence"], INPUT_HASHES["materialization_evidence"][0])
    authority = materialization.get("authority", {})
    authority_ok = all(
        isinstance(authority.get(kind), dict)
        and authority[kind].get("package_id") == expected["package_id"]
        and authority[kind].get("manifest_sha256") == expected["manifest_sha256"]
        for kind, expected in PACKAGES.items()
    )
    _check(checks, "task-008-authority-binding", authority_ok, "package and manifest identities match Task 008 evidence")
    selected = materialization.get("selected", {})
    selected_ok = (
        selected.get("checker", {}).get("analysis_id") == CHECKER_ID
        and selected.get("checker", {}).get("candidate_ids") == CHECKER_CANDIDATES
        and selected.get("cube", {}).get("analysis_id") == CUBE_ID
        and selected.get("cube", {}).get("cube_action_ids") == CUBE_ACTIONS
    )
    _check(
        checks,
        "task-008-selection-binding",
        selected_ok,
        "Task 008 selected the exact Learn analyses, candidates, and actions",
    )

    equivalence = load_json_bytes(payloads["task_009_equivalence"], INPUT_HASHES["task_009_equivalence"][0])
    eq_result = equivalence.get("result", {})
    equivalence_ok = (
        eq_result.get("status") == "PASS"
        and eq_result.get("checker_semantic_equivalence") == "PASS"
        and eq_result.get("cube_semantic_equivalence") == "PASS"
        and eq_result.get("required_factual_mismatch_count") == 0
    )
    _check(checks, "task-009-equivalence-binding", equivalence_ok, "accepted Task 009 result is PASS with zero factual mismatches")

    adapter = sources["lesson_adapter"]
    viewer = sources["shared_viewer"]
    forbidden_patterns = {
        "parquet": r"\.parquet\b",
        "duckdb": r"\bduckdb\b",
        "subprocess": r"\b(?:child_process|subprocess|spawnSync|execSync)\b",
        "analysis-engine": r"\b(?:gnubg|GNU Backgammon|SageMath)\b",
        "raw-gnu-parser": r"\b(?:parseGnu|decodeGNU|decodeXGID)\b",
        "node-direct-fallback": re.escape(LOCAL_AUTHORING_URL),
    }
    hits = [
        {"boundary": name, "file": SOURCE_PATHS[source_name]}
        for source_name, text in (("lesson_adapter", adapter), ("shared_viewer", viewer))
        for name, pattern in forbidden_patterns.items()
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    presentation_contract = (
        "sharedAnalysis()" in adapter
        and ".fixtureLoader(analysisUrl)(analysisId)" in adapter
        and "sharedAnalysis().renderPresentation" in adapter
        and "fetch(url, { credentials: \"same-origin\" })" in viewer
        and "function renderPresentation" in viewer
        and not hits
    )
    _check(checks, "presentation-only-source-contract", presentation_contract, "JSON fetch and shared presentation API only; no analytical runtime boundary hits")
    _check(checks, "no-static-fallback", LOCAL_AUTHORING_URL not in adapter and LOCAL_AUTHORING_URL not in viewer, "presentation layers contain no local-authoring fallback URL")

    return {
        "status": "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL",
        "checks": checks,
        "inputs": inputs,
        "packages": PACKAGES,
        "presentation_only": {
            "status": "PASS" if presentation_contract else "FAIL",
            "files": [SOURCE_PATHS["lesson_adapter"], SOURCE_PATHS["shared_viewer"]],
            "forbidden_boundary_hits": hits,
        },
    }


class _ProofServer:
    def __init__(self, site_root: Path, deny_canonical: bool) -> None:
        self.site_root = site_root
        self.deny_canonical = deny_canonical
        self.requests: list[dict[str, Any]] = []
        owner = self

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(owner.site_root), **kwargs)

            def log_message(self, _format: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802 - stdlib API
                path = urlsplit(self.path).path
                if path in (CANONICAL_URL, LOCAL_AUTHORING_URL):
                    if path == CANONICAL_URL and owner.deny_canonical:
                        owner.requests.append({"path": path, "status": 404, "sha256": None})
                        self.send_error(404, "Task 010 bounded negative control")
                        return
                    target = owner.site_root / path.lstrip("/")
                    digest = sha256_bytes(target.read_bytes()) if target.is_file() else None
                    owner.requests.append({"path": path, "status": 200 if digest else 404, "sha256": digest})
                super().do_GET()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self) -> "_ProofServer":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"


def _positive_case(browser: Any, server: _ProofServer, kind: str, viewport: dict[str, int]) -> dict[str, Any]:
    context = browser.new_context(viewport=viewport)
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.type) if message.type == "error" else None)
    page.on("pageerror", lambda _error: page_errors.append("pageerror"))
    route = CHECKER_ROUTE if kind == "checker" else CUBE_ROUTE
    page.goto(server.base_url + route, wait_until="networkidle")
    host_selector = "[data-bs-checker-decision]" if kind == "checker" else "[data-bs-cube-decision]"
    host = page.locator(host_selector)
    host.locator("article").wait_for()
    expected_id = CHECKER_ID if kind == "checker" else CUBE_ID
    configured = host.evaluate(
        """element => ({source: element.dataset.bsAnalysisSrc,
        configuredId: element.dataset.bsAnalysisId,
        mountedId: element.querySelector('article').dataset.analysisId})"""
    )
    if configured != {"source": CANONICAL_URL, "configuredId": expected_id, "mountedId": expected_id}:
        raise ProofError(f"{kind} runtime binding mismatch: {configured}")

    if kind == "checker":
        initial_ids = host.locator(":scope .bs-analysis-choice-row > [data-bs-analysis-choice]").evaluate_all(
            "elements => elements.map(element => element.dataset.bsAnalysisChoice)"
        )
        if initial_ids != CHECKER_CANDIDATES:
            raise ProofError(f"checker choice IDs mismatch: {initial_ids}")
        host.locator(f"button[data-bs-analysis-choice='{CHECKER_CANDIDATES[-1]}']").click()
        host.locator("[data-bs-shared-analysis-presentation='true']").wait_for()
        rendered_ids = host.locator("[data-bs-analysis-candidate-id]").evaluate_all(
            "elements => elements.map(element => element.dataset.bsAnalysisCandidateId)"
        )
        semantic_ok = rendered_ids == CHECKER_CANDIDATES and "8/4 6/4" in host.inner_text()
        surface = {"candidate_ids": rendered_ids, "recommendation": "8/4 6/4"}
    else:
        action_binding = host.evaluate(
            """element => [element.dataset.bsDoubleTakeActionId,
            element.dataset.bsDoublePassActionId, element.dataset.bsNoDoubleActionId]"""
        )
        if action_binding != CUBE_ACTIONS:
            raise ProofError(f"cube action binding mismatch: {action_binding}")
        host.locator("button[data-bs-analysis-choice='double']").click()
        host.locator("button[data-bs-analysis-choice='take']").click()
        host.locator("[data-bs-shared-analysis-presentation='true']").wait_for()
        rendered_ids = host.locator("[data-bs-analysis-result-choice]").evaluate_all(
            "elements => elements.map(element => element.dataset.bsAnalysisResultChoice)"
        )
        semantic_ok = rendered_ids == CUBE_ACTIONS and "Double, take" in host.inner_text()
        surface = {"action_ids": rendered_ids, "recommendation": "Double, take"}

    shared = host.locator("[data-bs-shared-analysis-consumer='lesson'] [data-bs-shared-analysis-presentation='true']").count() == 1
    errors = host.locator(".bs-analysis-error").count()
    result = {
        "kind": kind,
        "route": route,
        "viewport": viewport,
        "analysis_id": expected_id,
        "source_url": configured["source"],
        "shared_results_viewer": "PASS" if shared else "FAIL",
        "semantic_surface": "PASS" if semantic_ok else "FAIL",
        "mount_errors": errors,
        "console_errors": len(console_errors),
        "page_errors": len(page_errors),
        **surface,
    }
    result["status"] = "PASS" if semantic_ok and shared and errors == 0 and not console_errors and not page_errors else "FAIL"
    context.close()
    return result


def _negative_case(browser: Any, server: _ProofServer, kind: str) -> dict[str, Any]:
    context = browser.new_context(viewport={"width": 1024, "height": 768})
    page = context.new_page()
    route = CHECKER_ROUTE if kind == "checker" else CUBE_ROUTE
    page.goto(server.base_url + route, wait_until="networkidle")
    host_selector = "[data-bs-checker-decision]" if kind == "checker" else "[data-bs-cube-decision]"
    host = page.locator(host_selector)
    host.locator(".bs-analysis-error").wait_for()
    result = {
        "kind": kind,
        "route": route,
        "canonical_request_denied": host.locator(".bs-analysis-error").count() == 1,
        "analysis_mounted": host.locator("article").count() != 0,
        "shared_results_viewer_mounted": host.locator("[data-bs-shared-analysis-consumer]").count() != 0,
    }
    result["status"] = "PASS" if result["canonical_request_denied"] and not result["analysis_mounted"] and not result["shared_results_viewer_mounted"] else "FAIL"
    context.close()
    return result


def collect_browser_proof(site_root: Path) -> dict[str, Any]:
    if not (site_root / CHECKER_ROUTE.lstrip("/")).is_file() or not (site_root / CUBE_ROUTE.lstrip("/")).is_file():
        raise ProofError(f"rendered Learn routes are missing under {site_root}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ProofError("Python Playwright is required for the actual browser proof") from error

    viewports = [{"width": 1440, "height": 1000}, {"width": 390, "height": 844}]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        browser_version = browser.version
        with _ProofServer(site_root, deny_canonical=False) as positive_server:
            positive = [
                _positive_case(browser, positive_server, kind, viewport)
                for viewport in viewports
                for kind in ("checker", "cube")
            ]
            positive_requests = sorted(
                positive_server.requests,
                key=lambda item: (item["path"], item["status"], str(item["sha256"])),
            )
        with _ProofServer(site_root, deny_canonical=True) as negative_server:
            negative = [_negative_case(browser, negative_server, kind) for kind in ("checker", "cube")]
            negative_requests = sorted(
                negative_server.requests,
                key=lambda item: (item["path"], item["status"], str(item["sha256"])),
            )
        browser.close()

    expected_hash = INPUT_HASHES["lesson_view"][1]
    positive_source_ok = (
        len(positive_requests) == 4
        and all(item == {"path": CANONICAL_URL, "status": 200, "sha256": expected_hash} for item in positive_requests)
    )
    negative_source_ok = (
        len(negative_requests) == 2
        and all(item == {"path": CANONICAL_URL, "status": 404, "sha256": None} for item in negative_requests)
    )
    no_fallback = not any(item["path"] == LOCAL_AUTHORING_URL for item in positive_requests + negative_requests)
    positive_ok = all(item["status"] == "PASS" for item in positive)
    negative_ok = all(item["status"] == "PASS" for item in negative) and negative_source_ok and no_fallback
    return {
        "status": "PASS" if positive_ok and positive_source_ok and negative_ok else "FAIL",
        "browser": {"engine": "Chromium", "version": browser_version, "headless": True},
        "positive_cases": positive,
        "positive_data_requests": positive_requests,
        "positive_exact_source_bytes": "PASS" if positive_source_ok else "FAIL",
        "negative_control_cases": negative,
        "negative_control_requests": negative_requests,
        "negative_control_no_fallback": "PASS" if negative_ok else "FAIL",
        "local_authoring_requests": 0 if no_fallback else sum(item["path"] == LOCAL_AUTHORING_URL for item in positive_requests + negative_requests),
    }


def build_result(static: dict[str, Any], runtime: dict[str, Any], implementation_head: str) -> dict[str, Any]:
    positive = runtime.get("positive_cases", [])
    checker_ok = bool(positive) and all(item["status"] == "PASS" for item in positive if item["kind"] == "checker")
    cube_ok = bool(positive) and all(item["status"] == "PASS" for item in positive if item["kind"] == "cube")
    shared_ok = bool(positive) and all(item["shared_results_viewer"] == "PASS" for item in positive)
    source_ok = static["status"] == "PASS" and runtime.get("positive_exact_source_bytes") == "PASS"
    negative_ok = runtime.get("negative_control_no_fallback") == "PASS"
    excluded_ok = next(item for item in static["checks"] if item["name"] == "excluded-cube-absent")["status"] == "PASS"
    task009_ok = next(item for item in static["checks"] if item["name"] == "task-009-equivalence-binding")["status"] == "PASS"
    presentation_ok = static["presentation_only"]["status"] == "PASS"
    runtime_ok = runtime["status"] == "PASS"
    gates = {
        "checker_learn_canonical_derived_consumption": "PASS" if checker_ok else "FAIL",
        "cube_learn_canonical_derived_consumption": "PASS" if cube_ok else "FAIL",
        "shared_results_viewer_consumption": "PASS" if shared_ok else "FAIL",
        "server_derived_source_binding": "PASS" if source_ok else "FAIL",
        "negative_control_no_fallback_proof": "PASS" if negative_ok else "FAIL",
        "excluded_cube_rejection": "PASS" if excluded_ok else "FAIL",
        "browser_presentation_only_boundaries": "PASS" if presentation_ok else "FAIL",
        "task_009_equivalence_binding": "PASS" if task009_ok else "FAIL",
        "runtime_browser_proof": "PASS" if runtime_ok else "FAIL",
    }
    blockers = sum(value != "PASS" for value in gates.values())
    return {
        "schema_version": SCHEMA,
        "task": TASK,
        "implementation": {
            "starting_head": STARTING_HEAD,
            "final_head": implementation_head,
            "final_head_scope": "last commit containing Task 010 implementation; durable evidence is committed afterward",
        },
        "result": {"status": "PASS" if blockers == 0 else "FAIL", "required_product_path_blockers": blockers, **gates},
        "lineage": {
            "analysis_ids": {"checker": CHECKER_ID, "cube": CUBE_ID},
            "excluded_cube_id": EXCLUDED_CUBE_ID,
            "packages": PACKAGES,
            "inputs": static["inputs"],
        },
        "static_proof": static,
        "runtime_proof": runtime,
        "determinism": {
            "status": "PASS",
            "method": "two complete source/runtime builds compared byte-for-byte; no clock, host, port, duration, or mutable Git lookup is recorded",
            "repeat_count": 2,
        },
    }


def result_markdown(result: dict[str, Any], machine_hash: str) -> bytes:
    outcome = result["result"]
    lines = [
        "# Analyzer K001 Task 010 Learn consumption result",
        "",
        f"Status: `{outcome['status']}`",
        "",
        f"Task: `{TASK}`",
        f"Starting implementation head: `{STARTING_HEAD}`",
        f"Final implementation head: `{result['implementation']['final_head']}`",
        "",
        "## Product-path gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for key, value in outcome.items():
        if key not in ("status", "required_product_path_blockers"):
            lines.append(f"| `{key}` | `{value}` |")
    lines.extend([
        "",
        f"Required product-path blockers: `{outcome['required_product_path_blockers']}`",
        "",
        "## Auditable lineage",
        "",
        f"- Learn document SHA-256: `{result['lineage']['inputs']['lesson_view']['sha256']}`",
        f"- Checker package / manifest: `{PACKAGES['checker']['package_id']}` / `{PACKAGES['checker']['manifest_sha256']}`",
        f"- Cube package / manifest: `{PACKAGES['cube']['package_id']}` / `{PACKAGES['cube']['manifest_sha256']}`",
        f"- Task 009 equivalence SHA-256: `{result['lineage']['inputs']['task_009_equivalence']['sha256']}` (`PASS`, zero factual mismatches)",
        f"- Machine-readable result SHA-256: `{machine_hash}`",
        "",
        "## Runtime and negative control",
        "",
        "Chromium loaded both rendered Learn routes at desktop and mobile sizes. Each page requested the exact Canonical-derived URL and received bytes matching the accepted Learn document hash. The checker exposed eight accepted candidate IDs and its recommendation; the cube exposed three accepted action IDs and its recommendation through the shared Results Viewer marker.",
        "",
        "A separate bounded server denied that URL for both routes. Both hosts showed their load error, mounted no analysis/shared presentation, and made zero requests for the retained local-authoring document.",
        "",
        "The browser sources are presentation-only: same-origin JSON fetch -> existing lesson adapter -> existing shared Results Viewer. Narrow source checks reject Parquet/DuckDB, subprocess/analysis-engine, raw GNU decoding/parsing, and Node-direct fallback boundaries.",
        "",
        "## Determinism",
        "",
        result["determinism"]["method"] + ".",
        "",
        "No GNU, Node analysis, DuckDB query, Canonical download, or Canonical mutation was performed.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, required=True, help="Rendered Quarto site root")
    parser.add_argument("--implementation-head", required=True, help="Commit containing the proof implementation")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--verify-repeat", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.implementation_head):
        raise ProofError("--implementation-head must be a full lowercase Git SHA")
    if not args.verify_repeat:
        raise ProofError("--verify-repeat is required for durable Task 010 evidence")

    first = build_result(collect_static_proof(), collect_browser_proof(args.site_root.resolve()), args.implementation_head)
    first_bytes = stable_json_bytes(first)
    second = build_result(collect_static_proof(), collect_browser_proof(args.site_root.resolve()), args.implementation_head)
    second_bytes = stable_json_bytes(second)
    if first_bytes != second_bytes:
        raise ProofError("repeat proof result differs byte-for-byte")

    machine_hash = sha256_bytes(first_bytes)
    atomic_write(args.output_json.resolve(), first_bytes)
    atomic_write(args.output_markdown.resolve(), result_markdown(first, machine_hash))
    print(f"Task 010 Learn consumption proof: {first['result']['status']}")
    print(f"machine-readable SHA-256: {machine_hash}")
    return 0 if first["result"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
