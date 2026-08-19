import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "analysis" / "node-k001-regression-authoring.json"
GOLDEN_PATH = ROOT / "site" / "data" / "analyzer-node-k001-local-authoring-preview.json"

SPEC = importlib.util.spec_from_file_location(
    "materialize_node_analysis",
    ROOT / "scripts" / "analysis" / "materialize_node_analysis.py",
)
AUTHORING = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(AUTHORING)


def without_local_authoring(document):
    result = copy.deepcopy(document)
    result.pop("local_authoring", None)
    for analysis in result["analyses"].values():
        analysis.pop("local_authoring", None)
    return result


class NodeAnalysisAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = AUTHORING.load_json(CONFIG_PATH)
        cls.document, cls.manifest, cls.paths = AUTHORING.build_document(
            cls.config, ROOT
        )

    def test_checker_and_cube_regress_to_the_accepted_projection(self):
        accepted = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            without_local_authoring(self.document),
            without_local_authoring(accepted),
        )

    def test_source_identity_and_provenance_are_retained_verbatim(self):
        for selection in self.config["analyses"]:
            source = json.loads((ROOT / selection["artifact"]).read_text(encoding="utf-8"))
            projected = self.document["analyses"][selection["analysis_id"]]
            identity = projected["local_authoring"]
            self.assertEqual(identity["analysis_key"], source["analysis_key"])
            self.assertEqual(identity["source_schema"], source["schema_version"])
            self.assertEqual(identity["source_request"], source["source_request"])
            self.assertEqual(
                identity["producer_provenance"], source["producer_provenance"]
            )
            self.assertRegex(identity["artifact_sha256"], r"^[0-9a-f]{64}$")

    def test_repeat_projection_is_byte_identical(self):
        repeated, repeated_manifest, repeated_paths = AUTHORING.build_document(
            self.config, ROOT
        )
        self.assertEqual(
            AUTHORING.stable_bytes(self.document), AUTHORING.stable_bytes(repeated)
        )
        self.assertEqual(self.manifest, repeated_manifest)
        self.assertEqual(self.paths, repeated_paths)

    def test_wrong_or_ambiguous_selection_fails_closed(self):
        wrong = copy.deepcopy(self.config)
        wrong["analyses"][0]["analysis_id"] = "sha256-wrong"
        with self.assertRaisesRegex(AUTHORING.AuthoringError, "identity"):
            AUTHORING.build_document(wrong, ROOT)

        with tempfile.TemporaryDirectory() as name:
            source = json.loads(
                (ROOT / self.config["analyses"][0]["artifact"]).read_text(
                    encoding="utf-8"
                )
            )
            source["checker"]["candidates"][1]["source_order"] = 1
            malformed = Path(name) / "ambiguous.json"
            malformed.write_text(json.dumps(source), encoding="utf-8")
            ambiguous = copy.deepcopy(self.config)
            ambiguous["analyses"][0]["artifact"] = str(malformed)
            with self.assertRaisesRegex(AUTHORING.AuthoringError, "duplicate/invalid"):
                AUTHORING.build_document(ambiguous, ROOT)

    def test_local_authority_cannot_be_promoted_by_config(self):
        promoted = copy.deepcopy(self.config)
        promoted["authority"] = "canonical"
        with self.assertRaisesRegex(AUTHORING.AuthoringError, "local-development-only"):
            AUTHORING.build_document(promoted, ROOT)
        promoted = copy.deepcopy(self.config)
        promoted["fixture_status"]["kind"] = "canonical-analysis"
        with self.assertRaisesRegex(AUTHORING.AuthoringError, "not Canonical"):
            AUTHORING.build_document(promoted, ROOT)

    def test_local_authoring_does_not_rebind_canonical_lessons(self):
        self.assertEqual(
            AUTHORING.apply_learn_bindings(
                self.config, ROOT, set(self.document["analyses"])
            ),
            [],
        )
        self.assertEqual(self.config["learn_bindings"], [])

    def test_render_manifest_uses_only_selected_completed_artifacts(self):
        self.assertEqual(self.manifest["authority"], "local-development-only")
        self.assertEqual(
            [row["kind"] for row in self.manifest["analyses"]],
            ["checker", "cube"],
        )
        renderer = (
            ROOT / "scripts" / "analysis" / "render_node_analysis_assets.R"
        ).read_text(encoding="utf-8")
        self.assertIn("backgammonboard", renderer)
        self.assertIn("board_moves", renderer)
        self.assertNotIn("gnubg", renderer.casefold())


if __name__ == "__main__":
    unittest.main()
