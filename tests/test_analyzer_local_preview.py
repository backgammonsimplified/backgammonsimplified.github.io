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
            self.assertEqual(response["engine_execution_count"], 0)

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
        page_script = (ROOT / "site" / "assets" / "bs-analyzer-live.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('default="127.0.0.1"', adapter)
        self.assertIn("renderNodeAnalysisView", page_script)
        self.assertNotIn("createElement(\"table\")", page_script)
        self.assertNotIn("gnubg", page_script.lower())


if __name__ == "__main__":
    unittest.main()
