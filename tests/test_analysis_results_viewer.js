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
const retained = JSON.parse(
  fs.readFileSync(
    path.join(root, "site/data/analyzer-retained-checker-preview.json"),
    "utf8"
  )
);
const golden = JSON.parse(
  fs.readFileSync(
    path.join(root, "site/data/analyzer-node-k001-lesson-preview.json"),
    "utf8"
  )
);
const haddSidecar = JSON.parse(
  fs.readFileSync(
    path.join(
      root,
      "tests/fixtures/hadd-integration/actual-4ply-canonical-pair-sidecar-v1.json"
    ),
    "utf8"
  )
);

class FakeElement {
  constructor(tagName) {
    this.tagName = String(tagName).toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.className = "";
    this._textContent = "";
    this.open = false;
    this.hidden = false;
    this.listeners = {};
    this.classList = {
      add: (className) => {
        const classes = new Set(this.className.split(/\s+/).filter(Boolean));
        classes.add(className);
        this.className = Array.from(classes).join(" ");
      },
      toggle: (className, enabled) => {
        const classes = new Set(this.className.split(/\s+/).filter(Boolean));
        enabled ? classes.add(className) : classes.delete(className);
        this.className = Array.from(classes).join(" ");
      },
      contains: (className) =>
        this.className.split(/\s+/).filter(Boolean).includes(className)
    };
  }

  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this._textContent = String(value);
    this.children = [];
  }

  append(...children) {
    children.forEach((child) => this.appendChild(child));
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  replaceChildren(...children) {
    this._textContent = "";
    this.children = [];
    this.append(...children);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return this.attributes[name];
  }

  addEventListener(name, listener) {
    this.listeners[name] = this.listeners[name] || [];
    this.listeners[name].push(listener);
  }

  querySelector(selector) {
    if (selector === ":scope > summary") {
      return this.children.find((child) => child.tagName === "SUMMARY") || null;
    }
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const matches = [];
    const attributeMatch = selector.match(/^\[data-([a-z0-9-]+)\]$/);
    const classMatch = selector.match(/^\.([a-zA-Z0-9_-]+)$/);
    const datasetKey = attributeMatch
      ? attributeMatch[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())
      : null;
    function visit(node) {
      node.children.forEach((child) => {
        if (
          (datasetKey && child.dataset[datasetKey] !== undefined) ||
          (classMatch && child.classList.contains(classMatch[1])) ||
          (!datasetKey && !classMatch && child.tagName === selector.toUpperCase())
        ) {
          matches.push(child);
        }
        visit(child);
      });
    }
    visit(this);
    return matches;
  }
}

function findByClass(rootElement, className) {
  if (rootElement.classList.contains(className)) return rootElement;
  for (const child of rootElement.children) {
    const found = findByClass(child, className);
    if (found) return found;
  }
  return null;
}

assert.equal(viewer.validateFixtureDocument(fixtures), fixtures);
assert.equal(viewer.validateFixtureDocument(retained), retained);
assert.equal(viewer.validateFixtureDocument(golden), golden);
assert.equal(retained.fixture_status.kind, "retained-analysis");

const canonical = JSON.parse(JSON.stringify(retained));
canonical.fixture_status = {
  kind: "canonical-analysis",
  label: "Canonical Parquet analysis",
  message: "Values come from verified Canonical Analysis Parquet v1."
};
assert.equal(viewer.validateFixtureDocument(canonical), canonical);

const retainedChecker = viewer.analysisFromDocument(
  retained,
  "retained-checker-preview"
).analysis;
const goldenChecker = viewer.analysisFromDocument(
  golden,
  "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"
).analysis;
const goldenCube = viewer.analysisFromDocument(
  golden,
  "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"
).analysis;
assert.equal(goldenChecker.candidates.length, 8);
assert.equal(goldenChecker.candidates[0].move, "8/4 6/4");
assert.equal(goldenCube.metadata.recommendation, "Double, take");
assert.match(goldenCube.responder_board.image, /node-k001\/cube\/responder\.svg$/);
assert.deepEqual(
  goldenCube.actions.map((action) => action.id),
  [
    "5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f",
    "7ace038e9967b27f4c954b1a9b813f991f963e054e3994d6796d3cfd4c27a936",
    "b0b5a1bdb5eebe7e4dd2ead2e48b22827ff870401381fe21a6f4d3eb0308e1ad"
  ]
);
assert.equal(retainedChecker.analysis_kind, "checker");
assert.equal(retainedChecker.candidates.length, 3);
assert.equal(retainedChecker.candidates[0].move, "8/4");
assert.equal(retainedChecker.candidates[0].actual_ply, 4);
assert.equal(retainedChecker.candidates[0].value.value, -1.615);
assert.equal(retainedChecker.candidates[0].difference_from_best, 0.0);
assert.equal(retainedChecker.candidates[1].difference_from_best, -0.002);
assert.match(
  retainedChecker.candidates[0].move_board.image,
  /checker-sage-gnu-disagreement-001\/candidate-1-/
);
assert.match(
  retainedChecker.original_board.image,
  /checker-sage-gnu-disagreement-001\/starting\.svg$/
);

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
  viewer.outcomeSummaryItems(retainedChecker.candidates[0].probabilities),
  [
    ["Win", 0.162, "win"],
    ["Gammon", 0.0, "win"],
    ["Backgammon", 0.0, "win"],
    ["Lose gammon", 0.677, "lose"],
    ["Lose backgammon", 0.052, "lose"]
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

const comparisonRows = viewer.probabilityComparisonRows(
  {
    win: 0.42,
    win_gammon_or_better: 0.12,
    win_backgammon: 0.02,
    lose: 0.58,
    lose_gammon_or_worse: 0.18,
    lose_backgammon: 0.03
  },
  {
    win: 0.37,
    win_gammon_or_better: 0.15,
    win_backgammon: null,
    lose: 0.63,
    lose_gammon_or_worse: 0.15,
    lose_backgammon: 0.04
  }
);
assert.deepEqual(
  comparisonRows.map((row) => row.label),
  [
    "Win",
    "Win gammon or better",
    "Win backgammon",
    "Lose",
    "Lose gammon or worse",
    "Lose backgammon"
  ]
);
assert.equal(comparisonRows[0].topDisplay, "42%");
assert.equal(comparisonRows[0].selectedDisplay, "37%");
assert.equal(comparisonRows[0].differenceDisplay, "-5%");
assert.equal(comparisonRows[1].differenceDisplay, "+3%");
assert.equal(comparisonRows[2].selectedDisplay, "Not supplied");
assert.equal(comparisonRows[2].differenceDisplay, null);

global.document = {
  createElement(tagName) {
    return new FakeElement(tagName);
  }
};

const checkerHost = new FakeElement("div");
const checkerControls = viewer.renderPresentation(checkerHost, retainedChecker, {});
const checkerDecision = findByClass(
  checkerHost,
  "bs-analysis-results-checker-decision"
);
assert.ok(checkerDecision, "checker presentation has a sticky decision structure");
assert.ok(findByClass(checkerDecision, "bs-analysis-results-decision-card--top"));
assert.ok(findByClass(checkerDecision, "bs-analysis-results-outcome-bar"));
assert.equal(
  findByClass(checkerDecision, "bs-analysis-results-decision-move").textContent,
  retainedChecker.candidates[0].move
);
assert.equal(findByClass(checkerDecision, "bs-analysis-results-comparison-table"), null);
assert.ok(findByClass(checkerHost, "bs-analysis-results-recommended-badge"));
assert.match(
  findByClass(checkerHost, "bs-analysis-results-preview-facts").textContent,
  /verified combined movement\/result board/
);

const candidateDetails = checkerHost.querySelectorAll(
  "[data-bs-analysis-candidate-id]"
);
assert.equal(candidateDetails[0].open, true);
candidateDetails[1].open = true;
assert.equal(checkerControls.activate(retainedChecker.candidates[1].id), true);
assert.equal(candidateDetails[0].open, true, "selecting keeps the top details open");
assert.equal(candidateDetails[1].open, true, "selecting keeps another details open");
assert.equal(
  findByClass(checkerHost, "bs-analysis-results-board-image").src,
  retainedChecker.candidates[1].move_board.image
);
assert.equal(
  findByClass(checkerDecision, "bs-analysis-results-decision-card--top")
    .textContent.includes(retainedChecker.candidates[0].move),
  true,
  "the top move remains the baseline"
);
assert.ok(findByClass(checkerDecision, "bs-analysis-results-decision-card--selected"));
assert.ok(
  findByClass(checkerDecision, "bs-analysis-results-decision-card--selected")
    .querySelector(".bs-analysis-results-outcome-bar")
);
const comparisonTable = findByClass(
  checkerDecision,
  "bs-analysis-results-comparison-table"
);
assert.ok(comparisonTable);
assert.match(comparisonTable.textContent, /Recommended/);
assert.match(comparisonTable.textContent, /Selected/);

assert.equal(checkerControls.setPreviewMode("original"), true);
assert.equal(checkerControls.getPreviewMode(), "original");
assert.equal(
  findByClass(checkerHost, "bs-analysis-results-board-image").src,
  retainedChecker.original_board.image
);
assert.equal(checkerControls.setPreviewMode("movement"), true);

assert.equal(checkerControls.activate(retainedChecker.candidates[0].id), true);
assert.equal(findByClass(checkerDecision, "bs-analysis-results-comparison-table"), null);

const haddChecker = JSON.parse(JSON.stringify(retainedChecker));
haddChecker.candidates = haddChecker.candidates.slice(0, 2);
haddChecker.candidates.forEach((candidate, index) => {
  const record = haddSidecar.records[index];
  candidate.id = record.candidate_id;
  candidate.candidate_concept_id = record.candidate_concept_id;
  candidate.resulting_position_id = record.result_position_id;
  candidate.hadd_derived_facts = {
    position_id: record.position_id,
    position_perspective: record.position_perspective,
    probabilities: {
      ...record.cumulative_probabilities,
      lose: record.lose_probability
    },
    probability_derived_cubeless: record.probability_derived_cubeless,
    conditional_logit_evidence: record.conditional_logit_evidence
  };
});
haddChecker.recommended_id = haddChecker.candidates[1].id;
haddChecker.hadd = {
  status: "available",
  selected_architecture: "ridge-ranking-hadd-value-explanation-sidecar-v1",
  position_perspective: "normalized_static_post_move_next_player_on_roll",
  authority: {
    hadd_ranking_authorized: false,
    calculated_cubeful: "CUBEFUL_CALCULATION_AUTHORITY_BLOCKED"
  },
  model: haddSidecar.model,
  feature_system: haddSidecar.feature_system,
  ab_explanations: haddSidecar.ab_explanations
};
assert.equal(viewer.usablePreparedHadd(haddChecker), haddChecker.hadd);
const haddHost = new FakeElement("div");
const haddControls = viewer.renderPresentation(haddHost, haddChecker, {});
assert.ok(findByClass(haddHost, "bs-analysis-results-hadd"));
assert.match(haddHost.textContent, /HADD derived resulting-position facts/);
assert.match(haddHost.textContent, /Pairwise Ridge remains the sole Explainer ranking authority/);
assert.match(haddHost.textContent, /HADD did not select either candidate/);
assert.match(haddHost.textContent, /model-derived resulting-position probabilities/);
assert.equal(haddControls.activate(haddChecker.candidates[0].id), true);
assert.match(haddHost.textContent, /selected-minus-recommended \(A-minus-B\)/);
assert.match(haddHost.textContent, /nonlinear outputs/);
assert.ok(findByClass(haddHost, "bs-analysis-results-hadd-table"));
assert.match(haddHost.textContent, /q_win/);
assert.match(haddHost.textContent, /opponent point 01 checkers/);

const incompatibleHadd = JSON.parse(JSON.stringify(haddChecker));
incompatibleHadd.hadd.position_perspective = "wrong";
const incompatibleHost = new FakeElement("div");
viewer.renderPresentation(incompatibleHost, incompatibleHadd, {});
assert.equal(findByClass(incompatibleHost, "bs-analysis-results-hadd"), null);
assert.ok(findByClass(incompatibleHost, "bs-analysis-results-decision-card--top"));

const cubeHost = new FakeElement("div");
const cubeControls = viewer.renderPresentation(cubeHost, cube, {});
assert.equal(findByClass(cubeHost, "bs-analysis-results-checker-decision"), null);
assert.equal(findByClass(cubeHost, "bs-analysis-results-comparison-table"), null);
assert.equal(cubeControls.activate("roll"), true);
assert.ok(findByClass(cubeHost, "bs-analysis-results-comparison-table"));
assert.match(cubeHost.textContent, /Recommended action/);
assert.match(cubeHost.textContent, /Selected action/);
assert.equal(cubeControls.reset(), true);
assert.equal(findByClass(cubeHost, "bs-analysis-results-comparison-table"), null);

const syntheticCheckerHost = new FakeElement("div");
const syntheticCheckerControls = viewer.renderPresentation(
  syntheticCheckerHost,
  checker,
  {}
);
assert.equal(syntheticCheckerControls.getPreviewMode(), "result");
assert.equal(
  findByClass(syntheticCheckerHost, "bs-analysis-results-board-image").src,
  checker.candidates[0].result_board.image
);

const goldenCheckerHost = new FakeElement("div");
const goldenCheckerControls = viewer.renderPresentation(
  goldenCheckerHost,
  goldenChecker,
  { initialActiveId: "96d18ebbdcf54e9eb07265464db5b9e2100c5c0c6ae6c46e90a8a3a2258862d2" }
);
assert.equal(
  goldenCheckerHost.querySelectorAll("[data-bs-analysis-candidate-id]").length,
  8
);
assert.equal(
  goldenCheckerControls.activate(
    "44f91cbe042d6b615184f62d32d59337e3a35f709b875f11958bfdc2bf421477"
  ),
  true
);
assert.match(
  findByClass(goldenCheckerHost, "bs-analysis-results-board-image").src,
  /node-k001\/checker\/candidate-2\.svg$/
);
assert.ok(
  findByClass(goldenCheckerHost, "bs-analysis-results-comparison-table"),
  "the golden checker retains the Task 005 comparison"
);

const goldenCubeHost = new FakeElement("div");
viewer.renderPresentation(goldenCubeHost, goldenCube, {
  boardOverride: goldenCube.responder_board,
  initialActiveId: "5134e196c229cf5b7b36ce230fe26eedbb75ab8e1851010d6316008c233cfa0f"
});
assert.equal(
  goldenCubeHost.querySelectorAll("[data-bs-analysis-result-choice]").length,
  3
);
assert.equal(
  findByClass(goldenCubeHost, "bs-analysis-results-checker-decision"),
  null
);
assert.equal(findByClass(goldenCubeHost, "bs-analysis-results-comparison-table"), null);
assert.match(goldenCubeHost.textContent, /Recommended action/);
assert.match(
  findByClass(goldenCubeHost, "bs-analysis-results-board-image").src,
  /node-k001\/cube\/responder\.svg$/
);

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
