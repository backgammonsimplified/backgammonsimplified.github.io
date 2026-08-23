import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "analyzer_public_contract.py"
SPEC = importlib.util.spec_from_file_location("analyzer_public_contract", MODULE_PATH)
assert SPEC and SPEC.loader
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)

GNU_ID = "4HPwATDgc/ABMA:cAnqAAAAAAAE"
KEY = "sha256-" + "a" * 64


def request(**changes):
    value = {
        "schema_version": CONTRACT.REQUEST_SCHEMA,
        "engine": "gnu",
        "decision_type": "checker",
        "analysis_setting": "1ply",
        "position": {"format": "gnuid", "id": GNU_ID},
        "dice": [4, 2],
    }
    value.update(changes)
    return value


class AnalyzerProductionBoundaryTests(unittest.TestCase):
    def test_exact_node_compatible_request_is_accepted(self):
        body = json.dumps(request(), separators=(",", ":")).encode()
        self.assertEqual(CONTRACT.parse_request_body(body), request())
        self.assertLess(len(body), CONTRACT.MAX_REQUEST_BYTES)

    def test_unknown_command_and_path_fields_fail_closed(self):
        for change in (
            {"command": "uname -a"},
            {"path": "/srv/private"},
            {"arguments": ["--runtime-root", "/tmp"]},
            {"token": "secret"},
        ):
            with self.subTest(change=change), self.assertRaises(CONTRACT.ContractError):
                CONTRACT.normalize_request(request(**change))
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.normalize_request(
                request(position={"format": "gnuid", "id": GNU_ID, "path": "../../private"})
            )

    def test_body_schema_engine_profile_and_dice_are_bounded(self):
        invalid = [
            request(schema_version="future"),
            request(engine="sage"),
            request(analysis_setting="rollout"),
            request(decision_type="checker", dice=[True, 2]),
            request(decision_type="checker", dice=[0, 7]),
            request(decision_type="cube", dice=[4, 2]),
            request(position={"format": "xgid", "id": "XGID=-b----"}),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(CONTRACT.ContractError):
                CONTRACT.normalize_request(value)
        with self.assertRaisesRegex(CONTRACT.ContractError, "too large"):
            CONTRACT.parse_request_body(b"{" + b" " * CONTRACT.MAX_REQUEST_BYTES + b"}")

    def test_public_error_ignores_internal_text_and_unknown_codes(self):
        value = CONTRACT.public_error("bridge_failure")
        rendered = json.dumps(value)
        self.assertEqual(value["error"]["code"], "service_unavailable")
        self.assertNotRegex(rendered, r"ssh|private-node|/srv|traceback")
        known = CONTRACT.public_error("rate_limited")
        self.assertEqual(known["error"]["code"], "rate_limited")

    def test_cors_is_exact_origin_without_wildcard_or_credentials(self):
        origin = "https://backgammonsimplified.github.io"
        headers = CONTRACT.cors_headers(origin, [origin])
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin)
        self.assertEqual(headers["Vary"], "Origin")
        self.assertNotIn("Access-Control-Allow-Credentials", headers)
        self.assertNotIn("*", headers.values())
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.cors_headers("https://attacker.example", [origin])
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.cors_headers("http://backgammonsimplified.github.io", [origin])

    def test_completed_result_requires_same_node_key_and_analysis_view(self):
        view = json.loads(
            (ROOT / "tests" / "fixtures" / "node-k001-checker-analysis-view.json").read_text(
                encoding="utf-8"
            )
        )
        key = view["analysis_key"]
        result = {
            "schema_version": CONTRACT.RESULT_RESPONSE_SCHEMA,
            "analysis_key": key,
            "status": "complete",
            "analysis_view": view,
        }
        self.assertIs(CONTRACT.validate_public_result(result, key), result)
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.validate_public_result({**result, "analysis_key": KEY}, key)
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.validate_public_result({**result, "private_path": "/srv/node"}, key)
        leaking_view = {**view, "warning": "Traceback at /srv/node/private.py"}
        with self.assertRaises(CONTRACT.ContractError):
            CONTRACT.validate_public_result({**result, "analysis_view": leaking_view}, key)

    def test_static_config_is_disabled_and_contains_no_secret_surface(self):
        config_path = ROOT / "site" / "data" / "analyzer-production-gateway-v1.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(config),
            {
                "schema_version",
                "enabled",
                "gateway_origin",
                "api_base_path",
                "allowed_site_origin",
                "max_request_bytes",
            },
        )
        self.assertFalse(config["enabled"])
        self.assertIsNone(config["gateway_origin"])
        self.assertEqual(config["max_request_bytes"], CONTRACT.MAX_REQUEST_BYTES)
        self.assertNotRegex(json.dumps(config).lower(), r"token|secret|password|ssh|\.internal|\.local")

    def test_protocol_schema_rejects_additional_properties(self):
        schema = json.loads(
            (ROOT / "contracts" / "analyzer-public-api-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        definitions = schema["$defs"]
        for name in ("request", "submit_response", "status_response", "result_response", "error_response"):
            self.assertFalse(definitions[name]["additionalProperties"], name)
        self.assertEqual(
            definitions["request"]["properties"]["engine"]["const"], "gnu"
        )
        self.assertEqual(
            definitions["request"]["properties"]["analysis_setting"]["const"], "1ply"
        )

    def test_boundary_has_no_execution_storage_or_database_authority(self):
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        for forbidden in (
            "subprocess",
            "paramiko",
            "sqlite",
            "duckdb",
            "d1",
            "parquet",
            "canonical writer",
            "hashlib",
            "hexdigest",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
