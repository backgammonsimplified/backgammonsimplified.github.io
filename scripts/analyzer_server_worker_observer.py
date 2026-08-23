#!/usr/bin/env python3
"""Run one accepted Node worker and stream its public lifecycle states.

This development-proof helper is sent over the approved control route on
stdin. It owns no queue, engine, parser, cache, cancellation, or result logic;
the accepted backgammon-node CLI remains the worker and publication authority.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time


def emit(value: dict) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def main() -> int:
    if len(sys.argv) != 7:
        emit({"ok": False, "error": "invalid-observer-arguments"})
        return 2
    key, runtime_root, public_root, public_url_root, profile_manifest, timeout = sys.argv[1:]
    status_path = Path(public_root, key, "status.json")
    command = [
        sys.executable,
        "-m",
        "backgammon_node.cli",
        "worker",
        "--runtime-root",
        runtime_root,
        "--public-root",
        public_root,
        "--public-url-root",
        public_url_root,
        "--profile-manifest",
        profile_manifest,
        "--gnu-producer",
        "engine-kit",
        "--once",
        "--timeout",
        timeout,
    ]
    worker = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    previous = None
    while worker.poll() is None:
        try:
            status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            status = None
        if status and status != previous:
            emit({"node_status": status})
            previous = status
        time.sleep(0.01)
    stdout, _ = worker.communicate()
    try:
        status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
    except (OSError, json.JSONDecodeError):
        status = None
    if status and status != previous:
        emit({"node_status": status})
    if worker.returncode != 0:
        emit({"ok": False, "worker_returncode": worker.returncode})
        return worker.returncode
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        outcome = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError:
        outcome = {}
    emit({"ok": True, "worker_status": outcome.get("status")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
