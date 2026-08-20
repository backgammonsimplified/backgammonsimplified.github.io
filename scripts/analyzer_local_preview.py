#!/usr/bin/env python3
"""Serve the rendered Analyze page with a loopback-only Node coordinator.

This is a local-development adapter, not a production API. It only coordinates
the accepted backgammon-node CLI for GNU 1-ply checker/cube requests and serves
the resulting normalized Node analysis view. Node owns request identity,
deduplication, execution, parsing, status, result, and analysis-view semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from typing import Any
from urllib.parse import unquote, urlsplit


LOCAL_AUTHORITY = "local-development-only"
SUBMISSION_SCHEMA = "b" + "ms-analysis-submission-v2"
NODE_VIEW_SCHEMA = "b" + "ms-node-analysis-view-v0"
ANALYSIS_KEY = re.compile(r"^sha256-[0-9a-f]{64}$")
GNU_ID = re.compile(r"^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$")
TERMINAL_FAILURES = {
    "failed",
    "timed_out",
    "unsupported",
    "malformed_request",
    "configuration_mismatch",
}


class AdapterError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdapterError("adapter_io_error", "Local Node output is unavailable.", 500) from error
    if not isinstance(value, dict):
        raise AdapterError("adapter_io_error", "Local Node output is malformed.", 500)
    return value


def normalize_product_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdapterError("malformed_request", "The analysis request must be a JSON object.")
    if value.get("engine") != "gnu" or value.get("analysis_setting") != "1ply":
        raise AdapterError(
            "unsupported_capability",
            "This local product slice supports only GNU at 1-ply.",
            422,
        )
    gnuid = value.get("gnuid")
    if not isinstance(gnuid, str) or GNU_ID.fullmatch(gnuid.strip()) is None:
        raise AdapterError(
            "malformed_request",
            "Enter a complete GNU Position ID and Match ID separated by a colon.",
        )
    decision = value.get("decision")
    if decision not in {"checker", "cube"}:
        raise AdapterError("malformed_request", "Choose a checker or cube decision.")
    dice = value.get("dice")
    if decision == "checker":
        if (
            not isinstance(dice, list)
            or len(dice) != 2
            or any(
                isinstance(die, bool) or not isinstance(die, int) or die < 1 or die > 6
                for die in dice
            )
        ):
            raise AdapterError(
                "malformed_request",
                "Checker analysis requires two dice values from 1 to 6.",
            )
    elif dice is not None:
        raise AdapterError("malformed_request", "Cube analysis requires dice to be absent.")
    return {
        "schema_version": SUBMISSION_SCHEMA,
        "engine": "gnu",
        "decision_type": decision,
        "analysis_setting": "1ply",
        "position": {"format": "gnuid", "id": gnuid.strip()},
        "dice": dice if decision == "checker" else None,
    }


class NodeCoordinator:
    def __init__(
        self,
        work_root: Path,
        node_command: list[str] | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.work_root = Path(work_root).resolve()
        self.runtime_root = self.work_root / "runtime"
        self.public_root = self.work_root / "public"
        self.view_root = self.work_root / "analysis-view"
        self.node_command = node_command or [sys.executable, "-m", "backgammon_node.cli"]
        self.timeout_seconds = timeout_seconds
        self._worker_threads: list[threading.Thread] = []
        self._worker_failures: list[str] = []

    @property
    def common_args(self) -> list[str]:
        return [
            "--runtime-root",
            str(self.runtime_root),
            "--public-root",
            str(self.public_root),
            "--public-url-root",
            "/analysis/local",
        ]

    def _node(
        self,
        arguments: list[str],
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                [*self.node_command, *arguments],
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout or self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdapterError(
                "node_unavailable", "The accepted local Node capability is unavailable.", 503
            ) from error
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        try:
            payload = json.loads(lines[-1]) if lines else None
        except json.JSONDecodeError as error:
            raise AdapterError(
                "node_unavailable", "The accepted local Node capability returned unreadable output.", 502
            ) from error
        if not isinstance(payload, dict):
            raise AdapterError(
                "node_unavailable", "The accepted local Node capability returned no result.", 502
            )
        if completed.returncode != 0 or payload.get("ok") is False:
            error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
            raise AdapterError(
                str(error.get("code") or "node_failure"),
                str(error.get("message") or "The accepted local Node capability rejected the request."),
                422 if completed.returncode == 2 else 502,
            )
        return payload

    def health(self) -> dict[str, Any]:
        # Node's --require-live gate also requires Sage, which this GNU-only
        # product slice intentionally does not expose. The GNU producer itself
        # validates its exact executable/resources before every live execution.
        report = self._node(["health", *self.common_args], timeout=30)
        if not report.get("ok"):
            raise AdapterError(
                "node_unavailable", "The accepted local Node capability failed its live health check.", 503
            )
        return report

    def package_identity(self) -> dict[str, str]:
        try:
            return {
                "backgammon-node": importlib.metadata.version("backgammon-node"),
                "backgammon-engine-kit": importlib.metadata.version("backgammon-engine-kit"),
            }
        except importlib.metadata.PackageNotFoundError as error:
            raise AdapterError(
                "node_unavailable", "The accepted Node packages are not installed.", 503
            ) from error

    def _run_worker(self) -> None:
        try:
            self._node(
                [
                    "worker",
                    *self.common_args,
                    "--once",
                    "--timeout",
                    str(self.timeout_seconds),
                ],
                timeout=self.timeout_seconds + 15,
            )
        except AdapterError as error:
            self._worker_failures.append(error.code)

    def _launch_worker(self) -> None:
        thread = threading.Thread(target=self._run_worker, name="bs-node-worker-once", daemon=True)
        self._worker_threads.append(thread)
        thread.start()

    def submit(self, value: Any) -> dict[str, Any]:
        request = normalize_product_request(value)
        outcome = self._node(
            ["submit", "-", "--mode", "live", *self.common_args],
            input_text=json.dumps(request, sort_keys=True, separators=(",", ":")),
            timeout=30,
        )
        if outcome.get("status") == "queued" and not outcome.get("cache_hit"):
            self._launch_worker()
        return {
            "ok": True,
            "adapter_authority": LOCAL_AUTHORITY,
            "analysis_key": outcome.get("analysis_key"),
            "status": outcome.get("status"),
            "cache_hit": bool(outcome.get("cache_hit")),
        }

    def _attempt_count(self, key: str) -> int:
        record_root = self.runtime_root / "records" / key
        return len(list(record_root.glob("attempt-*/native-execution.json")))

    def _materialize_view(self, key: str) -> tuple[dict[str, Any], str]:
        output = self.view_root / f"{key}.json"
        if not output.is_file():
            request_record = self.runtime_root / "queue" / "done" / f"{key}.json"
            result_record = self.public_root / key / "result.json"
            if not request_record.is_file() or not result_record.is_file():
                raise AdapterError(
                    "result_pending", "The completed Node record is still being finalized.", 409
                )
            output.parent.mkdir(parents=True, exist_ok=True)
            self._node(
                [
                    "analysis-view",
                    "--request-record",
                    str(request_record),
                    "--result-record",
                    str(result_record),
                    "--output",
                    str(output),
                ],
                timeout=30,
            )
        payload = load_json(output)
        if payload.get("schema_version") != NODE_VIEW_SCHEMA or payload.get("analysis_key") != key:
            raise AdapterError("adapter_io_error", "The Node analysis view is malformed.", 500)
        return payload, hashlib.sha256(output.read_bytes()).hexdigest()

    def status(self, key: str) -> dict[str, Any]:
        if ANALYSIS_KEY.fullmatch(key) is None:
            raise AdapterError("malformed_request", "The analysis key is invalid.")
        status_path = self.public_root / key / "status.json"
        if not status_path.is_file():
            raise AdapterError("unknown_analysis", "No local Node analysis has this key.", 404)
        status = load_json(status_path)
        response: dict[str, Any] = {
            "ok": True,
            "adapter_authority": LOCAL_AUTHORITY,
            "analysis_key": key,
            "status": status.get("status"),
            "cache_hit": bool(status.get("cache_hit")),
            "engine_execution_count": self._attempt_count(key),
        }
        if status.get("status") in TERMINAL_FAILURES:
            response["error"] = status.get("error")
        if status.get("status") == "complete":
            try:
                view, digest = self._materialize_view(key)
            except AdapterError as error:
                if error.code == "result_pending":
                    response["status"] = "running"
                    return response
                raise
            response["analysis_view"] = view
            response["analysis_view_sha256"] = digest
        return response


class AnalyzerHandler(SimpleHTTPRequestHandler):
    server_version = "BMSAnalyzerLocal/1"

    def __init__(self, *args: Any, directory: str, coordinator: NodeCoordinator, **kwargs: Any):
        self.coordinator = coordinator
        super().__init__(*args, directory=directory, **kwargs)

    def _json(self, value: dict[str, Any], status: int = 200) -> None:
        payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, error: AdapterError) -> None:
        self._json(
            {"ok": False, "error": {"code": error.code, "message": str(error)}},
            error.status,
        )

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._error(AdapterError("local_only", "This adapter accepts loopback requests only.", 403))
            return
        if urlsplit(self.path).path != "/__bs_local_analysis/submit":
            self._error(AdapterError("not_found", "Unknown local adapter route.", 404))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 1 or length > 16_384:
            self._error(AdapterError("malformed_request", "The request body size is invalid."))
            return
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            self._json(self.coordinator.submit(value), HTTPStatus.ACCEPTED)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(AdapterError("malformed_request", "The request body must be valid JSON."))
        except AdapterError as error:
            self._error(error)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        path = unquote(urlsplit(self.path).path)
        prefix = "/__bs_local_analysis/status/"
        if path.startswith(prefix):
            try:
                self._json(self.coordinator.status(path[len(prefix) :]))
            except AdapterError as error:
                self._error(error)
            return
        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        # Deliberately log only the standard method/path/status line. Request
        # bodies, engine output, and private Node paths never enter server logs.
        super().log_message(format, *args)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "::1"))
    parser.add_argument("--static-root", type=Path)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--node-timeout", type=float, default=120.0)
    args = parser.parse_args()
    if args.port < 1 or args.port > 65_535:
        parser.error("--port must be from 1 to 65535")
    repo_root = Path(__file__).resolve().parents[1]
    static_root = (args.static_root or repo_root / "site" / "_site").resolve()
    if not (static_root / "analyze" / "index.html").is_file():
        parser.error("render site/analyze/index.qmd before starting the local adapter")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.work_root:
        work_root = args.work_root.resolve()
        work_root.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="bs-analyzer-node-")
        work_root = Path(temporary.name)
    coordinator = NodeCoordinator(work_root, timeout_seconds=args.node_timeout)
    identity = coordinator.package_identity()
    coordinator.health()

    def handler(*handler_args: Any, **handler_kwargs: Any) -> AnalyzerHandler:
        return AnalyzerHandler(
            *handler_args,
            directory=str(static_root),
            coordinator=coordinator,
            **handler_kwargs,
        )

    server = ThreadingHTTPServer((args.host, args.port), handler)
    print("BS Analyzer local-development-only preview", flush=True)
    print(f"URL: http://{args.host}:{args.port}/analyze/", flush=True)
    print(
        "Node packages: "
        f"backgammon-node {identity['backgammon-node']}; "
        f"backgammon-engine-kit {identity['backgammon-engine-kit']}",
        flush=True,
    )
    print("Boundary: loopback; GNU + 1ply; no production routing", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if temporary is not None:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
