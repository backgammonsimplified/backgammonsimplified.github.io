import json
import unittest

from scripts.analysis import prove_learn_canonical_consumption as proof


class LearnCanonicalConsumptionProofTests(unittest.TestCase):
    def check_status(self, result, name):
        return next(item["status"] for item in result["checks"] if item["name"] == name)

    def test_accepted_committed_source_and_lineage_pass(self):
        result = proof.collect_static_proof()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(self.check_status(result, "checker-source-binding"), "PASS")
        self.assertEqual(self.check_status(result, "cube-source-binding"), "PASS")
        self.assertEqual(self.check_status(result, "no-static-fallback"), "PASS")
        self.assertEqual(result["presentation_only"]["forbidden_boundary_hits"], [])

    def test_local_authoring_source_substitution_fails_closed(self):
        path = proof.SOURCE_PATHS["checker_qmd"]
        original = (proof.ROOT / path).read_bytes()
        altered = original.replace(proof.CANONICAL_URL.encode(), proof.LOCAL_AUTHORING_URL.encode())
        result = proof.collect_static_proof(overrides={path: altered})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(self.check_status(result, "checker-source-binding"), "FAIL")

    def test_wrong_cube_identity_and_action_fail_closed(self):
        path = proof.SOURCE_PATHS["cube_qmd"]
        original = (proof.ROOT / path).read_bytes()
        altered = original.replace(proof.CUBE_ID.encode(), proof.EXCLUDED_CUBE_ID.encode()).replace(
            proof.CUBE_ACTIONS[0].encode(), b"0" * 64
        )
        result = proof.collect_static_proof(overrides={path: altered})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(self.check_status(result, "cube-source-binding"), "FAIL")
        self.assertEqual(self.check_status(result, "excluded-cube-absent"), "FAIL")

    def test_modified_lesson_document_fails_hash_and_semantic_surface(self):
        path = proof.INPUT_HASHES["lesson_view"][0]
        document = json.loads((proof.ROOT / path).read_text(encoding="utf-8"))
        document["analyses"][proof.CHECKER_ID]["candidates"].pop()
        result = proof.collect_static_proof(overrides={path: proof.stable_json_bytes(document)})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(self.check_status(result, "accepted-hash:lesson_view"), "FAIL")
        self.assertEqual(self.check_status(result, "checker-semantic-surface"), "FAIL")

    def test_nonpassing_task_009_fails_binding(self):
        path = proof.INPUT_HASHES["task_009_equivalence"][0]
        document = json.loads((proof.ROOT / path).read_text(encoding="utf-8"))
        document["result"]["status"] = "FAIL"
        result = proof.collect_static_proof(overrides={path: proof.stable_json_bytes(document)})
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(self.check_status(result, "accepted-hash:task_009_equivalence"), "FAIL")
        self.assertEqual(self.check_status(result, "task-009-equivalence-binding"), "FAIL")


if __name__ == "__main__":
    unittest.main()
