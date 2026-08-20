const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const live = require("../site/assets/bs-analyzer-live.js");
const viewer = require("../site/assets/bs-analysis-results.js");
const root = path.resolve(__dirname, "..");

const checker = live.normalizeInput({
  gnuid: " 4HPwATDgc/ABMA:cAnqAAAAAAAE ",
  decision: "checker",
  die1: "4",
  die2: "2"
});
assert.deepEqual(checker, {
  gnuid: "4HPwATDgc/ABMA:cAnqAAAAAAAE",
  decision: "checker",
  dice: [4, 2],
  engine: "gnu",
  analysis_setting: "1ply"
});

assert.deepEqual(
  live.normalizeInput({
    gnuid: "4HPwATDgc/ABMA:cAngAAAAAAAE",
    decision: "cube",
    die1: "not-used",
    die2: "not-used"
  }).dice,
  null
);
assert.throws(
  () => live.normalizeInput({ gnuid: "4HPwATDgc/ABMA", decision: "cube" }),
  /complete GNU Position ID and Match ID/
);
assert.throws(
  () =>
    live.normalizeInput({
      gnuid: "4HPwATDgc/ABMA:cAnqAAAAAAAE",
      decision: "checker",
      die1: "0",
      die2: "7"
    }),
  /two dice values/
);

const checkerView = JSON.parse(
  fs.readFileSync(
    path.join(root, "tests/fixtures/node-k001-checker-analysis-view.json"),
    "utf8"
  )
);
const cubeView = JSON.parse(
  fs.readFileSync(
    path.join(root, "tests/fixtures/node-k001-cube-analysis-view.json"),
    "utf8"
  )
);
const checkerModel = viewer.analysisModelFromNodeView(checkerView);
const cubeModel = viewer.analysisModelFromNodeView(cubeView);

assert.equal(checkerModel.fixture, false);
assert.equal(checkerModel.source_schema, viewer.NODE_ANALYSIS_VIEW_SCHEMA);
assert.equal(checkerModel.analysis_kind, "checker");
assert.equal(checkerModel.original_board, null);
assert.equal(checkerModel.candidates.length, checkerView.checker.candidates.length);
assert.equal(checkerModel.candidates[0].move, checkerView.checker.candidates[0].notation);
assert.equal(checkerModel.metadata.parser, "gnu-text-parser-v1");
assert.equal(cubeModel.analysis_kind, "cube");
assert.equal(cubeModel.actions.length, cubeView.cube.actions.length);
assert.equal(cubeModel.actions[0].label, cubeView.cube.actions[0].label);
assert.equal(cubeModel.context.dice, null);

assert.throws(
  () => viewer.analysisModelFromNodeView({ schema_version: "invented-view-v1" }),
  /Unsupported Node analysis-view schema/
);

console.log("interactive Analyzer normalization and shared-viewer mapping passed");
