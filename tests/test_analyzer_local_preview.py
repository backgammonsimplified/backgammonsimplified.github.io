import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "analyzer_local_preview.py"
SPEC = importlib.util.spec_from_file_location("analyzer_local_preview", MODULE_PATH)
assert SPEC and SPEC.loader
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)

NON_GOLDEN = "4HPwATDgc/ABMA:cAnqAAAAAAAE"


def server_config():
    return {
        "schema_version": ADAPTER.SERVER_CONFIG_SCHEMA,
        "control_command": ["ssh", "neotame", "ssh", "mannitol"],
        "node_command": [
            "env",
            "PYTHONPATH=/srv/backgammon-node/src",
            "nice",
            "-n",
            "10",
            "/srv/node-venv/bin/python",
            "-m",
            "backgammon_node.cli",
        ],
        "worker_observer_command": [
            "env",
            "PYTHONPATH=/srv/backgammon-node/src",
            "nice",
            "-n",
            "10",
            "/srv/node-venv/bin/python",
            "-",
        ],
        "runtime_root": "/srv/task-016/private",
        "public_root": "/srv/task-016/public",
        "view_root": "/srv/task-016/views",
        "profile_manifest": "/srv/node-venv/share/analysis-profiles-v1.json",
        "gnu_producer": "engine-kit",
        "node_authority": "left-brain@" + "a" * 40,
        "transport_disposition": "approved development server route",
        "lookup_sources": [
            {
                "runtime_root": "/srv/task-012/private",
                "public_root": "/srv/task-012/public",
            }
        ],
    }


def subprocess_result(returncode, stdout):
    return ADAPTER.subprocess.CompletedProcess([], returncode, stdout.encode("utf-8"), b"")


class AnalyzerLocalPreviewTests(unittest.TestCase):
    def test_normalizes_fixed_gnu_checker_and_cube_requests(self):
        checker = ADAPTER.normalize_product_request(
            {
                "gnuid": NON_GOLDEN,
                "decision": "checker",
                "dice": [4, 2],
                "engine": "gnu",
                "analysis_setting": "1ply",
            }
        )
        self.assertEqual(checker["schema_version"], "b" + "ms-analysis-submission-v2")
        self.assertEqual(checker["position"], {"format": "gnuid", "id": NON_GOLDEN})
        self.assertEqual(checker["dice"], [4, 2])
        cube = ADAPTER.normalize_product_request(
            {
                "gnuid": "4HPwATDgc/ABMA:cAngAAAAAAAE",
                "decision": "cube",
                "dice": None,
                "engine": "gnu",
                "analysis_setting": "1ply",
            }
        )
        self.assertIsNone(cube["dice"])

    def test_rejects_incomplete_gnuid_checker_dice_and_cube_dice(self):
        invalid = [
            {
                "gnuid": "4HPwATDgc/ABMA",
                "decision": "cube",
                "dice": None,
                "engine": "gnu",
                "analysis_setting": "1ply",
            },
            {
                "gnuid": NON_GOLDEN,
                "decision": "checker",
                "dice": [0, 7],
                "engine": "gnu",
                "analysis_setting": "1ply",
            },
            {
                "gnuid": NON_GOLDEN,
                "decision": "cube",
                "dice": [4, 2],
                "engine": "gnu",
                "analysis_setting": "1ply",
            },
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ADAPTER.AdapterError):
                ADAPTER.normalize_product_request(request)

    def test_submit_consumes_node_cache_disposition(self):
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = ADAPTER.NodeCoordinator(Path(temporary), ["fake-node"])
            request = {
                "gnuid": NON_GOLDEN,
                "decision": "checker",
                "dice": [4, 2],
                "engine": "gnu",
                "analysis_setting": "1ply",
            }
            key = "sha256-" + "1" * 64
            with mock.patch.object(
                coordinator,
                "_node",
                side_effect=[
                    {"analysis_key": key, "status": "queued", "cache_hit": False},
                    {"analysis_key": key, "status": "complete", "cache_hit": True},
                ],
            ), mock.patch.object(coordinator, "_launch_worker") as launch:
                first = coordinator.submit(request)
                second = coordinator.submit(request)
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            launch.assert_called_once_with()

    def test_complete_status_materializes_existing_node_view(self):
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = ADAPTER.NodeCoordinator(Path(temporary), ["fake-node"])
            key = "sha256-" + "2" * 64
            public = coordinator.public_root / key
            public.mkdir(parents=True)
            (public / "status.json").write_text(
                json.dumps({"analysis_key": key, "status": "complete", "cache_hit": False}),
                encoding="utf-8",
            )
            done = coordinator.runtime_root / "queue" / "done"
            done.mkdir(parents=True)
            (done / f"{key}.json").write_text("{}", encoding="utf-8")
            (public / "result.json").write_text("{}", encoding="utf-8")
            attempt = coordinator.runtime_root / "records" / key / "attempt-1"
            attempt.mkdir(parents=True)
            (attempt / "engine-result.json").write_text("{}", encoding="utf-8")

            def fake_node(arguments, input_text=None, timeout=None):
                output = Path(arguments[arguments.index("--output") + 1])
                output.write_text(
                    json.dumps(
                        {
                            "schema_version": ADAPTER.NODE_VIEW_SCHEMA,
                            "analysis_key": key,
                            "analysis_kind": "cube",
                        },
                        separators=(",", ":"),
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return {"ok": True}

            with mock.patch.object(coordinator, "_node", side_effect=fake_node):
                response = coordinator.status(key)
            self.assertEqual(response["status"], "complete")
            self.assertEqual(response["analysis_view"]["analysis_key"], key)
            self.assertRegex(response["analysis_view_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(response["engine_execution_count"], 1)
            self.assertRegex(response["result_sha256"], r"^[0-9a-f]{64}$")

    def test_server_submit_keeps_browser_request_on_stdin(self):
        coordinator = ADAPTER.ServerNodeCoordinator(server_config())
        key = "sha256-" + "4" * 64
        completed = subprocess_result(
            0,
            json.dumps({"analysis_key": key, "status": "queued", "cache_hit": False})
            + "\n",
        )
        request = {
            "gnuid": NON_GOLDEN,
            "decision": "checker",
            "dice": [3, 1],
            "engine": "gnu",
            "analysis_setting": "1ply",
        }
        with mock.patch.object(coordinator.transport, "run", return_value=completed) as run, mock.patch.object(
            coordinator, "_launch_worker"
        ) as launch:
            response = coordinator.submit(request)
        arguments = run.call_args.args[0]
        input_bytes = run.call_args.kwargs["input_bytes"]
        self.assertNotIn(NON_GOLDEN, " ".join(arguments))
        self.assertIn(NON_GOLDEN, input_bytes.decode("utf-8"))
        self.assertEqual(response["status"], "queued")
        launch.assert_called_once_with(key)

    def test_server_lookup_reads_accepted_source_and_uses_node_view(self):
        coordinator = ADAPTER.ServerNodeCoordinator(server_config())
        key = "sha256-" + "5" * 64
        status = json.dumps({"analysis_key": key, "status": "complete", "cache_hit": False})
        result = json.dumps({"analysis_key": key, "analysis": {"status": "complete"}}) + "\n"
        view = json.dumps(
            {
                "schema_version": ADAPTER.NODE_VIEW_SCHEMA,
                "analysis_key": key,
                "analysis_kind": "checker",
            },
            separators=(",", ":"),
        ) + "\n"
        materialized = {"value": False}

        def fake_run(arguments, input_bytes=None, timeout=120):
            command = " ".join(arguments)
            if arguments[0] == "/bin/cat":
                path = arguments[1]
                if "/task-016/public/" in path:
                    return subprocess_result(1, "")
                if path.endswith("status.json"):
                    return subprocess_result(0, status)
                if path.endswith("result.json"):
                    return subprocess_result(0, result)
                if path.endswith(f"views/{key}.json") and materialized["value"]:
                    return subprocess_result(0, view)
                return subprocess_result(1, "")
            if arguments[0] == "/usr/bin/find":
                if "engine-result.json" in arguments:
                    return subprocess_result(
                        0, f"/srv/task-012/private/records/{key}/attempt-1/engine-result.json\n"
                    )
                return subprocess_result(0, "")
            if arguments[:2] == ["/bin/mkdir", "-p"]:
                return subprocess_result(0, "")
            if "analysis-view" in arguments:
                materialized["value"] = True
                return subprocess_result(0, json.dumps({"ok": True, "analysis_key": key}) + "\n")
            raise AssertionError(f"unexpected server command: {command}")

        with mock.patch.object(coordinator.transport, "run", side_effect=fake_run):
            response = coordinator.lookup(key)
        self.assertEqual(response["status"], "complete")
        self.assertEqual(response["server_source"], "accepted_completed")
        self.assertEqual(response["lookup_disposition"], "already_complete")
        self.assertEqual(response["engine_execution_count"], 1)
        self.assertEqual(response["analysis_view"]["analysis_key"], key)
        self.assertNotIn("runtime_root", response)
        self.assertNotIn("public_root", response)

    def test_server_transport_rejects_shell_text_and_relative_paths(self):
        unsafe_command = server_config()
        unsafe_command["control_command"] = ["ssh", "mannitol;uname"]
        with self.assertRaises(ADAPTER.AdapterError):
            ADAPTER.ServerNodeCoordinator(unsafe_command)
        unsafe_path = server_config()
        unsafe_path["runtime_root"] = "relative/runtime"
        with self.assertRaises(ADAPTER.AdapterError):
            ADAPTER.ServerNodeCoordinator(unsafe_path)
        unsafe_label = server_config()
        unsafe_label["transport_disposition"] = "route\nsecret"
        with self.assertRaises(ADAPTER.AdapterError):
            ADAPTER.ServerNodeCoordinator(unsafe_label)

    def test_server_running_display_requires_observed_node_lifecycle(self):
        coordinator = ADAPTER.ServerNodeCoordinator(server_config())
        key = "sha256-" + "6" * 64
        self.assertFalse(coordinator._take_observed_running(key))
        coordinator._record_lifecycle(key, "running")
        self.assertTrue(coordinator._take_observed_running(key))
        self.assertFalse(coordinator._take_observed_running(key))

    def test_failed_status_is_visible_without_fabricated_view(self):
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = ADAPTER.NodeCoordinator(Path(temporary), ["fake-node"])
            key = "sha256-" + "3" * 64
            public = coordinator.public_root / key
            public.mkdir(parents=True)
            error = {"code": "engine_failure", "message": "Engine analysis failed."}
            (public / "status.json").write_text(
                json.dumps({"analysis_key": key, "status": "failed", "error": error}),
                encoding="utf-8",
            )
            response = coordinator.status(key)
            self.assertEqual(response["status"], "failed")
            self.assertEqual(response["error"], error)
            self.assertNotIn("analysis_view", response)

    def test_adapter_is_loopback_and_shared_viewer_only(self):
        adapter = MODULE_PATH.read_text(encoding="utf-8")
        observer = (ROOT / "scripts" / "analyzer_server_worker_observer.py").read_text(
            encoding="utf-8"
        )
        page_script = (ROOT / "site" / "assets" / "bs-analyzer-live.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('default="127.0.0.1"', adapter)
        self.assertIn("renderNodeAnalysisView", page_script)
        self.assertNotIn("createElement(\"table\")", page_script)
        self.assertNotIn("gnubg", page_script.lower())
        self.assertNotIn("ssh", page_script.lower())
        self.assertIn('"backgammon_node.cli"', observer)
        self.assertNotIn("from backgammon_node", observer)


if __name__ == "__main__":
    unittest.main()
