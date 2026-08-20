const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const viewer = require(path.join(root, "site/assets/bs-analysis-results.js"));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "analyzer-materializer-js-"));
const output = path.join(temporary, "analysis-view.json");
const python = fs.existsSync(path.join(root, ".venv/bin/python"))
  ? path.join(root, ".venv/bin/python")
  : "python3";

try {
  const completed = childProcess.spawnSync(
    python,
    [
      path.join(root, "scripts/analysis/analysis_view_materializer.py"),
      path.join(root, "tests/fixtures/analyzer-analysis-view-read-set-v1.json"),
      "--output",
      output,
      "--verify-repeat"
    ],
    { cwd: root, encoding: "utf8" }
  );
  assert.equal(completed.status, 0, completed.stderr);
  const document = JSON.parse(fs.readFileSync(output, "utf8"));
  assert.equal(viewer.validateFixtureDocument(document), document);

  const checker = viewer.analysisFromDocument(
    document,
    "synthetic-checker-decision-001"
  ).analysis;
  assert.equal(checker.candidates.length, 3);
  assert.equal(checker.candidates[0].id, "synthetic-checker-candidate-001");
  assert.equal(checker.candidates[0].value.value, -1.615);
  assert.equal(checker.candidates[0].actual_ply, 4);
  assert.equal(checker.candidates[1].actual_ply, 2);
  assert.equal(checker.candidates[2].actual_ply, null);
  assert.equal(checker.candidates[2].move_board, null);

  const cube = viewer.analysisFromDocument(
    document,
    "synthetic-cube-decision-001"
  ).analysis;
  assert.equal(cube.cube_occurrence.observed_action_normalized, "roll");
  assert.equal(cube.actions.length, 4);
  assert.equal(cube.actions[3].supported, false);
  assert.equal(cube.actions[3].value.value, null);
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}

console.log("analysis-view materializer remains compatible with viewer v1");
