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

assert.deepEqual(viewer.candidateMetrics(checker.candidates[0]), {
  equity: "+0.093",
  versusBest: "+0.000"
});
assert.deepEqual(viewer.candidateMetrics(checker.candidates[1]), {
  equity: "+0.067",
  versusBest: "-0.026"
});
assert.deepEqual(viewer.candidateMetrics(checker.candidates[2]), {
  equity: "Not supplied",
  versusBest: "Not supplied"
});

const completeOutcomes = viewer.exclusiveOutcomeSegments(
  checker.candidates[0].probabilities
);
assert.equal(completeOutcomes.status, "complete");
assert.deepEqual(
  completeOutcomes.segments.map((segment) => [segment.key, segment.value]),
  [
    ["win_backgammon", 0.01],
    ["win_gammon", 0.1],
    ["win_single", 0.47],
    ["lose_single", 0.37],
    ["lose_gammon", 0.04],
    ["lose_backgammon", 0.01]
  ]
);
assert.ok(
  Math.abs(
    completeOutcomes.segments.reduce((sum, segment) => sum + segment.value, 0) - 1
  ) < 1e-9
);

assert.deepEqual(
  viewer.outcomeSummaryItems(checker.candidates[0].probabilities),
  [
    ["Win", 0.58, "win"],
    ["Gammon", 0.11, "win"],
    ["Backgammon", 0.01, "win"],
    ["Lose gammon", 0.05, "lose"],
    ["Lose backgammon", 0.01, "lose"]
  ]
);

const partialOutcomes = viewer.exclusiveOutcomeSegments(
  checker.candidates[1].probabilities
);
assert.equal(partialOutcomes.status, "partial");
assert.deepEqual(
  partialOutcomes.segments.map((segment) => [segment.key, segment.value]),
  [["win", 0.56], ["lose", 0.44]]
);
assert.deepEqual(
  viewer.outcomeSummaryItems(checker.candidates[1].probabilities),
  [
    ["Win", 0.56, "win"],
    ["Gammon", null, "win"],
    ["Backgammon", null, "win"],
    ["Lose gammon", null, "lose"],
    ["Lose backgammon", null, "lose"]
  ]
);

assert.equal(viewer.exclusiveOutcomeSegments(null).status, "missing");
assert.equal(
  viewer.exclusiveOutcomeSegments({ win: 0.7, lose: 0.4 }).status,
  "invalid"
);
assert.equal(
  viewer.exclusiveOutcomeSegments({
    win: 0.58,
    win_gammon_or_better: 0.1,
    win_backgammon: 0.2,
    lose: 0.42,
    lose_gammon_or_worse: 0.05,
    lose_backgammon: 0.01
  }).status,
  "invalid"
);

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