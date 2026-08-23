#!/usr/bin/env python3
"""Serve the rendered Analyze page with a loopback-only Node coordinator.

This is a local-development adapter, not a production API. It only coordinates
the accepted backgammon-node CLI for GNU 1-ply checker/cube requests and serves
the resulting normalized Node analysis view. The CLI may run locally or through
a fixed operator-configured server command. Node owns request identity,
deduplication, execution, parsing, status, result, and analysis-view semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
from urllib.parse import unquote, urlsplit


LOCAL_AUTHORITY = "loopback-development-adapter"
SERVER_CONFIG_SCHEMA = "b" + "ms-analyzer-server-transport-v1"
SUBMISSION_SCHEMA = "b" + "ms-analysis-submission-v2"
NODE_VIEW_SCHEMA = "b" + "ms-node-analysis-view-v0"
MAX_REQUEST_BYTES = 2_048
ANALYSIS_KEY = re.compile(r"^sha256-[0-9a-f]{64}$")
GNU_ID = re.compile(r"^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$")
SAFE_REMOTE_VALUE = re.compile(r"^[A-Za-z0-9_./:=@,+-]+$")
SAFE_DISPLAY_VALUE = re.compile(r"^[A-Za-z0-9 _./:=@,+><-]{1,160}$")
TERMINAL_FAILURES = {
    "cancelled",
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
    if set(value) != {
        "schema_version",
        "engine",
        "decision_type",
        "analysis_setting",
        "position",
        "dice",
    }:
        raise AdapterError("malformed_request", "The analysis request has unsupported fields.")
    if value.get("schema_version") != SUBMISSION_SCHEMA:
        raise AdapterError("malformed_request", "The analysis request schema is unsupported.")
    if value.get("engine") != "gnu" or value.get("analysis_setting") != "1ply":
        raise AdapterError(
            "unsupported_capability",
            "This local product slice supports only GNU at 1-ply.",
            422,
        )
    position = value.get("position")
    if not isinstance(position, dict) or set(position) != {"format", "id"}:
        raise AdapterError("malformed_request", "The position must be a complete GNUID.")
    gnuid = position.get("id")
    if (
        position.get("format") != "gnuid"
        or not isinstance(gnuid, str)
        or GNU_ID.fullmatch(gnuid) is None
    ):
        raise AdapterError(
            "malformed_request",
            "Enter a complete GNU Position ID and Match ID separated by a colon.",
        )
    decision = value.get("decision_type")
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
        "position": {"format": "gnuid", "id": gnuid},
        "dice": dice if decision == "checker" else None,
    }


def safe_remote_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or SAFE_REMOTE_VALUE.fullmatch(value) is None:
        raise AdapterError("transport_configuration", f"The server {label} is not safely bounded.", 500)
    return value


def safe_remote_path(value: Any, label: str) -> str:
    path = safe_remote_value(value, label)
    parsed = PurePosixPath(path)
    if not parsed.is_absolute() or ".." in parsed.parts:
        raise AdapterError("transport_configuration", f"The server {label} must be absolute.", 500)
    return path.rstrip("/") or "/"


def safe_command(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise AdapterError("transport_configuration", f"The server {label} is missing.", 500)
    return [safe_remote_value(token, label) for token in value]


def safe_display_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or SAFE_DISPLAY_VALUE.fullmatch(value) is None:
        raise AdapterError(
            "transport_configuration", f"The server {label} is not safely bounded.", 500
        )
    return value


class RemoteCommandTransport:
    """Run fixed, shell-token-safe commands through an operator-owned control route."""

    def __init__(self, control_command: list[str]) -> None:
        self.control_command = safe_command(control_command, "control command")

    def run(
        self,
        arguments: list[str],
        input_bytes: bytes | None = None,
        timeout: float = 120.0,
    ) -> subprocess.CompletedProcess[bytes]:
        bounded = [safe_remote_value(token, "command argument") for token in arguments]
        try:
            return subprocess.run(
                [*self.control_command, *bounded],
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdapterError(
                "node_unavailable", "The accepted server Node capability is unavailable.", 503
            ) from error

    def popen(self, arguments: list[str]) -> subprocess.Popen[bytes]:
        bounded = [safe_remote_value(token, "command argument") for token in arguments]
        try:
            return subprocess.Popen(
                [*self.control_command, *bounded],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise AdapterError(
                "node_unavailable", "The accepted server Node capability is unavailable.", 503
            ) from error


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
        attempts = {
            path.parent.name
            for pattern in ("attempt-*/native-execution.json", "attempt-*/engine-result.json")
            for path in record_root.glob(pattern)
        }
        return len(attempts)

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
            result_record = self.public_root / key / "result.json"
            try:
                view, digest = self._materialize_view(key)
            except AdapterError as error:
                if error.code == "result_pending":
                    response["status"] = "running"
                    return response
                raise
            response["analysis_view"] = view
            response["analysis_view_sha256"] = digest
            response["result_sha256"] = hashlib.sha256(result_record.read_bytes()).hexdigest()
        return response

    def lookup(self, key: str) -> dict[str, Any]:
        response = self.status(key)
        response["lookup_disposition"] = (
            "already_complete" if response.get("status") == "complete" else "status_found"
        )
        return response


class ServerNodeCoordinator:
    """Coordinate accepted Node CLI state through a bounded remote command route."""

    def __init__(self, config: dict[str, Any], timeout_seconds: float = 120.0) -> None:
        if config.get("schema_version") != SERVER_CONFIG_SCHEMA:
            raise AdapterError(
                "transport_configuration", "The server transport schema is unsupported.", 500
            )
        self.transport = RemoteCommandTransport(config.get("control_command"))
        self.node_command = safe_command(config.get("node_command"), "Node command")
        self.worker_observer_command = safe_command(
            config.get("worker_observer_command"), "worker observer command"
        )
        self.runtime_root = safe_remote_path(config.get("runtime_root"), "runtime root")
        self.public_root = safe_remote_path(config.get("public_root"), "public root")
        self.view_root = safe_remote_path(config.get("view_root"), "analysis-view root")
        self.profile_manifest = safe_remote_path(
            config.get("profile_manifest"), "profile manifest"
        )
        if config.get("gnu_producer") != "engine-kit":
            raise AdapterError(
                "transport_configuration", "The server GNU producer must be engine-kit.", 500
            )
        self.public_url_root = safe_remote_value(
            config.get("public_url_root", "/analysis/task-016"), "public URL root"
        )
        self.timeout_seconds = timeout_seconds
        self.worker_start_delay = float(config.get("worker_start_delay_seconds", 0.2))
        if not 0 <= self.worker_start_delay <= 2:
            raise AdapterError(
                "transport_configuration", "The worker start delay is out of bounds.", 500
            )
        self.transport_disposition = safe_display_value(
            config.get("transport_disposition") or "operator-configured server command",
            "transport disposition",
        )
        self.node_authority = safe_remote_value(
            config.get("node_authority"), "Node authority"
        )
        raw_sources = config.get("lookup_sources", [])
        if not isinstance(raw_sources, list) or len(raw_sources) > 4:
            raise AdapterError(
                "transport_configuration", "The server lookup source list is invalid.", 500
            )
        self.lookup_sources = [
            {
                "runtime_root": safe_remote_path(source.get("runtime_root"), "lookup runtime root"),
                "public_root": safe_remote_path(source.get("public_root"), "lookup public root"),
                "disposition": "accepted_completed",
            }
            for source in raw_sources
            if isinstance(source, dict)
        ]
        if len(self.lookup_sources) != len(raw_sources):
            raise AdapterError(
                "transport_configuration", "A server lookup source is malformed.", 500
            )
        self._worker_threads: list[threading.Thread] = []
        self._worker_failures: list[str] = []
        self._lifecycle_events: dict[str, list[str]] = {}
        self._delivered_running: set[str] = set()
        self._lifecycle_lock = threading.Lock()

    @classmethod
    def from_config(cls, path: Path, timeout_seconds: float = 120.0) -> "ServerNodeCoordinator":
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AdapterError(
                "transport_configuration", "The server transport configuration is unreadable.", 500
            ) from error
        if not isinstance(config, dict):
            raise AdapterError(
                "transport_configuration", "The server transport configuration is malformed.", 500
            )
        return cls(config, timeout_seconds=timeout_seconds)

    @property
    def common_args(self) -> list[str]:
        return [
            "--runtime-root",
            self.runtime_root,
            "--public-root",
            self.public_root,
            "--public-url-root",
            self.public_url_root,
            "--profile-manifest",
            self.profile_manifest,
            "--gnu-producer",
            "engine-kit",
        ]

    @staticmethod
    def _path(root: str, *parts: str) -> str:
        return str(PurePosixPath(root, *parts))

    def _node(
        self,
        arguments: list[str],
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        completed = self.transport.run(
            [*self.node_command, *arguments],
            input_bytes=input_text.encode("utf-8") if input_text is not None else None,
            timeout=timeout or self.timeout_seconds,
        )
        lines = [line.strip() for line in completed.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
        try:
            payload = json.loads(lines[-1]) if lines else None
        except json.JSONDecodeError as error:
            raise AdapterError(
                "node_unavailable", "The accepted server Node capability returned unreadable output.", 502
            ) from error
        if not isinstance(payload, dict):
            raise AdapterError(
                "node_unavailable", "The accepted server Node capability returned no result.", 502
            )
        if completed.returncode != 0 or payload.get("ok") is False:
            error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
            raise AdapterError(
                str(error.get("code") or "node_failure"),
                str(error.get("message") or "The accepted server Node capability rejected the request."),
                422 if completed.returncode == 2 else 502,
            )
        return payload

    def _read(self, path: str, timeout: float = 30.0) -> bytes | None:
        completed = self.transport.run(["/bin/cat", safe_remote_path(path, "read path")], timeout=timeout)
        if completed.returncode == 0:
            return completed.stdout
        if completed.returncode == 255:
            raise AdapterError(
                "node_unavailable", "The accepted server Node capability is unavailable.", 503
            )
        return None

    @staticmethod
    def _json_bytes(value: bytes | None, message: str) -> dict[str, Any]:
        try:
            payload = json.loads(value) if value is not None else None
        except json.JSONDecodeError as error:
            raise AdapterError("adapter_io_error", message, 502) from error
        if not isinstance(payload, dict):
            raise AdapterError("adapter_io_error", message, 502)
        return payload

    def health(self) -> dict[str, Any]:
        report = self._node(["health", *self.common_args], timeout=30)
        if not report.get("ok"):
            raise AdapterError(
                "node_unavailable", "The accepted server Node health check failed.", 503
            )
        return report

    def package_identity(self) -> dict[str, str]:
        return {"authority": self.node_authority}

    def _record_lifecycle(self, key: str, status: Any) -> None:
        if status not in {"queued", "running", "complete", *TERMINAL_FAILURES}:
            return
        with self._lifecycle_lock:
            events = self._lifecycle_events.setdefault(key, [])
            if not events or events[-1] != status:
                events.append(status)

    def _take_observed_running(self, key: str) -> bool:
        with self._lifecycle_lock:
            if key in self._delivered_running:
                return False
            if "running" not in self._lifecycle_events.get(key, []):
                return False
            self._delivered_running.add(key)
            return True

    def _run_worker(self, key: str) -> None:
        try:
            if self.worker_start_delay:
                time.sleep(self.worker_start_delay)
            observer = Path(__file__).with_name("analyzer_server_worker_observer.py").read_bytes()
            process = self.transport.popen(
                [
                    *self.worker_observer_command,
                    key,
                    self.runtime_root,
                    self.public_root,
                    self.public_url_root,
                    self.profile_manifest,
                    str(self.timeout_seconds),
                ]
            )
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(observer)
            process.stdin.close()
            for line in process.stdout:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._record_lifecycle(key, payload.get("node_status"))
            if process.wait() != 0:
                self._worker_failures.append("worker_failure")
        except AdapterError as error:
            self._worker_failures.append(error.code)
        except OSError:
            self._worker_failures.append("worker_observer_unavailable")

    def _launch_worker(self, key: str) -> None:
        thread = threading.Thread(
            target=self._run_worker,
            args=(key,),
            name="bs-server-node-worker-once",
            daemon=True,
        )
        self._worker_threads.append(thread)
        thread.start()

    def submit(self, value: Any) -> dict[str, Any]:
        request = normalize_product_request(value)
        outcome = self._node(
            ["submit", "-", "--mode", "live", *self.common_args],
            input_text=json.dumps(request, sort_keys=True, separators=(",", ":")),
            timeout=30,
        )
        key = outcome.get("analysis_key")
        if not isinstance(key, str) or ANALYSIS_KEY.fullmatch(key) is None:
            raise AdapterError(
                "node_unavailable", "The accepted server Node returned an invalid analysis key.", 502
            )
        if outcome.get("status") == "queued" and not outcome.get("cache_hit"):
            self._record_lifecycle(key, "queued")
            self._launch_worker(key)
        return {
            "ok": True,
            "adapter_authority": LOCAL_AUTHORITY,
            "analysis_key": key,
            "status": outcome.get("status"),
            "cache_hit": bool(outcome.get("cache_hit")),
        }

    def _source(self, key: str) -> tuple[dict[str, str], bytes]:
        sources = [
            {
                "runtime_root": self.runtime_root,
                "public_root": self.public_root,
                "disposition": "task_runtime",
            },
            *self.lookup_sources,
        ]
        for source in sources:
            status_path = self._path(source["public_root"], key, "status.json")
            status_bytes = self._read(status_path)
            if status_bytes is not None:
                return source, status_bytes
        raise AdapterError("unknown_analysis", "No server Node analysis has this key.", 404)

    def _attempt_count(self, runtime_root: str, key: str) -> int:
        record_root = self._path(runtime_root, "records", key)
        attempts: set[str] = set()
        for filename in ("engine-result.json", "native-execution.json"):
            completed = self.transport.run(
                [
                    "/usr/bin/find",
                    record_root,
                    "-mindepth",
                    "2",
                    "-maxdepth",
                    "2",
                    "-name",
                    filename,
                    "-print",
                ],
                timeout=30,
            )
            if completed.returncode not in {0, 1}:
                raise AdapterError(
                    "node_unavailable", "The server Node attempt record is unavailable.", 503
                )
            for line in completed.stdout.decode("utf-8", "replace").splitlines():
                attempts.add(PurePosixPath(line).parent.name)
        return len(attempts)

    def _materialize_view(
        self, source: dict[str, str], key: str
    ) -> tuple[dict[str, Any], str]:
        output = self._path(self.view_root, f"{key}.json")
        view_bytes = self._read(output)
        if view_bytes is None:
            created = self.transport.run(["/bin/mkdir", "-p", self.view_root], timeout=30)
            if created.returncode != 0:
                raise AdapterError(
                    "adapter_io_error", "The server Node analysis view cannot be finalized.", 502
                )
            request_record = self._path(
                source["runtime_root"], "queue", "done", f"{key}.json"
            )
            result_record = self._path(source["public_root"], key, "result.json")
            self._node(
                [
                    "analysis-view",
                    "--request-record",
                    request_record,
                    "--result-record",
                    result_record,
                    "--output",
                    output,
                ],
                timeout=30,
            )
            view_bytes = self._read(output)
        payload = self._json_bytes(view_bytes, "The server Node analysis view is malformed.")
        if payload.get("schema_version") != NODE_VIEW_SCHEMA or payload.get("analysis_key") != key:
            raise AdapterError(
                "adapter_io_error", "The server Node analysis view is malformed.", 502
            )
        assert view_bytes is not None
        return payload, hashlib.sha256(view_bytes).hexdigest()

    def status(self, key: str) -> dict[str, Any]:
        if ANALYSIS_KEY.fullmatch(key) is None:
            raise AdapterError("malformed_request", "The analysis key is invalid.")
        source, status_bytes = self._source(key)
        status = self._json_bytes(status_bytes, "The server Node status is malformed.")
        response: dict[str, Any] = {
            "ok": True,
            "adapter_authority": LOCAL_AUTHORITY,
            "analysis_key": key,
            "status": status.get("status"),
            "cache_hit": bool(status.get("cache_hit")),
            "engine_execution_count": self._attempt_count(source["runtime_root"], key),
            "server_source": source["disposition"],
        }
        if status.get("status") in TERMINAL_FAILURES:
            response["error"] = status.get("error")
        if status.get("status") == "complete" and self._take_observed_running(key):
            response["status"] = "running"
            response["status_observation"] = "observed_from_node_public_lifecycle"
            return response
        if status.get("status") == "complete":
            result_bytes = self._read(self._path(source["public_root"], key, "result.json"))
            if result_bytes is None:
                response["status"] = "running"
                return response
            view, digest = self._materialize_view(source, key)
            response["analysis_view"] = view
            response["analysis_view_sha256"] = digest
            response["result_sha256"] = hashlib.sha256(result_bytes).hexdigest()
        return response

    def lookup(self, key: str) -> dict[str, Any]:
        response = self.status(key)
        response["lookup_disposition"] = (
            "already_complete" if response.get("status") == "complete" else "status_found"
        )
        return response


class AnalyzerHandler(SimpleHTTPRequestHandler):
    server_version = "BMSAnalyzerLocal/1"

    def __init__(
        self,
        *args: Any,
        directory: str,
        coordinator: NodeCoordinator | ServerNodeCoordinator,
        **kwargs: Any,
    ):
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
        if length < 1 or length > MAX_REQUEST_BYTES:
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
        lookup_prefix = "/__bs_local_analysis/lookup/"
        if path.startswith(lookup_prefix):
            try:
                self._json(self.coordinator.lookup(path[len(lookup_prefix) :]))
            except AdapterError as error:
                self._error(error)
            return
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
    parser.add_argument(
        "--server-config",
        type=Path,
        help="operator-local JSON for a fixed development-only server command transport",
    )
    parser.add_argument("--node-timeout", type=float, default=120.0)
    args = parser.parse_args()
    if args.port < 1 or args.port > 65_535:
        parser.error("--port must be from 1 to 65535")
    repo_root = Path(__file__).resolve().parents[1]
    static_root = (args.static_root or repo_root / "site" / "_site").resolve()
    if not (static_root / "analyze" / "index.html").is_file():
        parser.error("render site/analyze/index.qmd before starting the local adapter")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.server_config:
        coordinator: NodeCoordinator | ServerNodeCoordinator = ServerNodeCoordinator.from_config(
            args.server_config.resolve(), timeout_seconds=args.node_timeout
        )
    else:
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
    print("BS Analyzer loopback development preview", flush=True)
    print(f"URL: http://{args.host}:{args.port}/analyze/", flush=True)
    if isinstance(coordinator, ServerNodeCoordinator):
        print(f"Node authority: {identity['authority']}", flush=True)
        print(f"Transport: {coordinator.transport_disposition}", flush=True)
    else:
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
