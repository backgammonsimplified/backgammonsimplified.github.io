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

assert.match(checkerView.analysis_key, live.ANALYSIS_KEY);
assert.equal(live.LOOKUP_ROOT, "/__bs_local_analysis/lookup/");

function fakeSurface() {
  const label = { textContent: "" };
  const detail = { textContent: "" };
  const key = { textContent: "", hidden: true };
  const results = { replaceChildren() {} };
  return {
    dataset: {},
    querySelector(selector) {
      return {
        "[data-bs-analyzer-state-label]": label,
        "[data-bs-analyzer-state-detail]": detail,
        "[data-bs-analyzer-key]": key,
        "[data-bs-analyzer-results]": results
      }[selector];
    }
  };
}

(async function () {
  const surface = fakeSurface();
  const states = [];
  const payloads = [
    { ok: true, status: "queued" },
    { ok: true, status: "running" },
    { ok: true, status: "complete", analysis_view: checkerView }
  ];
  live.setState(surface, "queued", "queued");
  await live.pollUntilComplete(surface, checkerView.analysis_key, {
    pollInterval: 1,
    fetchJson: async function () {
      states.push(surface.dataset.bsAnalyzerState);
      return payloads.shift();
    },
    renderNodeAnalysisView: function (_target, value) {
      assert.equal(value.analysis_key, checkerView.analysis_key);
    }
  });
  assert.deepEqual(states, ["queued", "queued", "running"]);
  assert.equal(surface.dataset.bsAnalyzerState, "complete");

  const lookupSurface = fakeSurface();
  const lookupStates = [];
  await live.loadAnalysisKey(lookupSurface, checkerView.analysis_key, {
    pollInterval: 1,
    fetchJson: async function () {
      lookupStates.push(lookupSurface.dataset.bsAnalyzerState);
      return { ok: true, status: "complete", analysis_view: checkerView };
    },
    renderNodeAnalysisView: function () {}
  });
  assert.deepEqual(lookupStates, ["looking-up", "already-complete"]);
  assert.equal(lookupSurface.dataset.bsAnalyzerState, "complete");

  console.log("interactive Analyzer server lifecycle and shared-viewer mapping passed");
})().catch(function (error) {
  console.error(error);
  process.exitCode = 1;
});
