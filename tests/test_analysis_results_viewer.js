const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const viewer = require("../site/assets/bs-analysis-results.js");
const root = path.resolve(__dirname, "..");
const fixtures = JSON.parse(
  fs.readFileSync(
    path.join(root, "site/data/analyzer-analysis-results-fixtures.json"),
    "utf8"
  )
);

assert.equal(viewer.validateFixtureDocument(fixtures), fixtures);

const checker = viewer.analysisFromDocument(fixtures, "checker-ui-demo").analysis;
assert.equal(checker.analysis_kind, "checker");
assert.equal(checker.candidates.length, 3);
assert.equal(checker.candidates[0].evaluation, "4-ply-shaped fixture");
assert.equal(checker.candidates[1].evaluation, "2-ply-shaped fixture");
assert.equal(checker.candidates[1].probabilities.win_gammon_or_better, null);
assert.equal(checker.candidates[2].result_board, null);
assert.equal(checker.candidates[2].value.value, null);

const cube = viewer.analysisFromDocument(fixtures, "cube-ui-demo").analysis;
assert.equal(cube.analysis_kind, "cube");
assert.deepEqual(
  cube.actions.slice(0, 3).map((action) => action.normalized_action),
  ["roll", "double_take", "double_pass"]
);
assert.equal(cube.actions[3].supported, false);
assert.equal(cube.context.dice, null);

assert.equal(viewer.formatNumber(0.093), "+0.093");
assert.equal(viewer.formatNumber(-0.026), "-0.026");
assert.equal(viewer.formatNumber(null), "Not supplied");
assert.equal(viewer.formatProbability(0.58), "58.0%");
assert.equal(viewer.formatProbability(null), "Not supplied");

assert.throws(
  () => viewer.analysisFromDocument(fixtures, "unknown-ui-demo"),
  /Unknown analysis fixture ID/
);
assert.throws(
  () => viewer.analysisFromDocument(fixtures, "malformed-ui-demo"),
  /Malformed analysis viewer fixture/
);
assert.throws(
  () => viewer.validateFixtureDocument({ schema_version: "other" }),
  /Unsupported/
);

console.log("analysis results viewer fixture logic passed");
