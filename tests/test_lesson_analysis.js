const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const analysis = require("../site/assets/bs-lesson-analysis.js");
const shared = require("../site/assets/bs-analysis-results.js");

const root = path.resolve(__dirname, "..");
const fixtures = JSON.parse(
  fs.readFileSync(
    path.join(root, "site/data/lesson-analysis-svg-mvp.json"),
    "utf8"
  )
);
const realFixtures = JSON.parse(
  fs.readFileSync(
    path.join(root, "site/data/checker-sage-gnu-disagreement-001.json"),
    "utf8"
  )
);

assert.equal(
  analysis.validateFixtureDocument(fixtures),
  fixtures,
  "the checked-in fixture document is accepted"
);
assert.equal(analysis.validateFixtureDocument(realFixtures), realFixtures);

const doubleTake = fixtures.cube_cases["cube-double-take"];
const rollReview = analysis.cubeDecisionState(doubleTake, "roll");
assert.equal(rollReview.actionAccepted, false);
assert.equal(rollReview.responder, null);
assert.equal(rollReview.actionData.analysis.recommendation, "Double");

const doubleChoice = analysis.cubeDecisionState(doubleTake, "double");
assert.equal(doubleChoice.actionAccepted, true);
assert.equal(doubleChoice.responder.correct_response, "take");
assert.equal(doubleChoice.actionData.analysis.recommendation, "Double");

const passReview = analysis.cubeDecisionState(doubleTake, "double", "pass");
assert.equal(passReview.responseAccepted, false);
assert.equal(passReview.responseData.analysis.recommendation, "Take");

const takeAnswer = analysis.cubeDecisionState(doubleTake, "double", "take");
assert.equal(takeAnswer.responseAccepted, true);
assert.equal(takeAnswer.responseData.analysis.recommendation, "Take");

const rollFixture = fixtures.cube_cases["cube-roll"];
assert.equal(
  analysis.cubeDecisionState(rollFixture, "roll").actionAccepted,
  true,
  "the component supports Roll as the accepted first action"
);
assert.equal(
  analysis.cubeDecisionState(rollFixture, "double").responder,
  null,
  "a rejected Double does not invent a responder decision"
);

const doublePass = fixtures.cube_cases["cube-double-pass"];
assert.equal(
  analysis.cubeDecisionState(doublePass, "double", "pass").responseAccepted,
  true,
  "the component supports Pass as the accepted cube response"
);
assert.equal(
  analysis.cubeDecisionState(doublePass, "double", "take").responseAccepted,
  false
);

assert.throws(
  () => analysis.cubeDecisionState(doubleTake, "beaver"),
  /Double or Roll/
);

const realChecker =
  realFixtures.checker_cases["checker-sage-gnu-disagreement-001"];
const realCandidate = analysis.checkerCandidateState(
  realChecker,
  "candidate-1"
);
assert.equal(realCandidate.label, "8/4");
assert.equal(realCandidate.rank, 1);
assert.equal(realCandidate.equity, -1.615);
assert.equal(realCandidate.equity_loss, 0);
assert.equal(realCandidate.winning_probabilities.lose_gammon, 0.677);
assert.equal(realCandidate.explanation, null);
assert.equal(
  analysis.checkerCandidateIdentityMatches(realChecker, realCandidate),
  true
);
assert.equal(
  analysis.checkerCandidateIdentityMatches(realChecker, {
    ...realCandidate,
    analysis_id: "wrong"
  }),
  false
);
assert.throws(
  () => analysis.cubeDecisionState(doubleTake, "double", "beaver"),
  /Pass or Take/
);

const checker = fixtures.checker_cases["checker-three-candidates"];
const candidate1 = analysis.checkerCandidateState(checker, "candidate-1");
const candidate2 = analysis.checkerCandidateState(checker, "candidate-2");
const candidate3 = analysis.checkerCandidateState(checker, "candidate-3");
assert.equal(candidate1.image, "candidate-1.svg");
assert.equal(candidate2.equity_loss, 0);
assert.equal(candidate3.winning_probabilities.win_gammon, null);
assert.throws(
  () => analysis.checkerCandidateState(checker, "candidate-4"),
  /does not define/
);

const checkerModel = analysis.checkerViewModel(checker, fixtures);
assert.equal(checkerModel.analysis_kind, "checker");
assert.equal(checkerModel.candidates.length, 3);
assert.equal(checkerModel.candidates[1].value.value, 0.093);
assert.equal(checkerModel.candidates[1].difference_from_best, -0);
assert.equal(checkerModel.candidates[2].probabilities.win_gammon_or_better, null);
assert.match(checkerModel.candidates[0].move_board.image, /candidate-1\.svg$/);
assert.equal(shared.validateAnalysisModel(checkerModel), checkerModel);

const retainedCheckerModel = analysis.checkerViewModel(realChecker, realFixtures);
assert.equal(retainedCheckerModel.candidates[0].move, "8/4");
assert.equal(retainedCheckerModel.candidates[1].difference_from_best, -0.002);
assert.equal(
  retainedCheckerModel.candidates[0].probabilities.lose_gammon_or_worse,
  0.677
);
assert.match(
  retainedCheckerModel.candidates[0].move_board.alt,
  /starting position with checker movement overlay/
);
assert.equal(shared.validateAnalysisModel(retainedCheckerModel), retainedCheckerModel);

const cubeModel = analysis.cubeViewModel(
  doubleTake.actions.double.analysis,
  doubleTake.initial,
  doubleTake,
  fixtures,
  "first-double"
);
assert.equal(cubeModel.analysis_kind, "cube");
assert.deepEqual(
  cubeModel.actions.map((action) => action.id),
  ["roll", "double_take"]
);
assert.equal(cubeModel.probabilities.lose, 0.37);
assert.equal(cubeModel.probabilities.win_gammon_or_better, 0.14);
assert.equal(analysis.matchingActionId(cubeModel, "double"), "double_take");
assert.equal(shared.validateAnalysisModel(cubeModel), cubeModel);

assert.deepEqual(analysis.lessonProbabilities({ win: 0.58 }), {
  win: 0.58,
  win_gammon_or_better: undefined,
  win_backgammon: undefined,
  lose: 0.42000000000000004,
  lose_gammon_or_worse: undefined,
  lose_backgammon: undefined
});

assert.equal(
  analysis.assetUrl(fixtures.asset_root, fixtures.cube_cases["cube-roll"].initial.image),
  "/assets/positions/lesson-analysis-svg-mvp/opening-fixture/starting.svg"
);
assert.throws(
  () => analysis.assetUrl(fixtures.asset_root, "../outside.svg"),
  /unsafe/
);

analysis.resetInstanceCounter();
const instanceIds = [
  analysis.nextInstanceId("cube", "cube-double-take"),
  analysis.nextInstanceId("cube", "cube-double-take"),
  analysis.nextInstanceId("checker", "checker-three-candidates")
];
assert.equal(new Set(instanceIds).size, instanceIds.length);
assert.match(instanceIds[0], /^bs-analysis-cube-cube-double-take-1$/);
assert.match(instanceIds[2], /^bs-analysis-checker-checker-three-candidates-3$/);

console.log("lesson analysis fixture logic passed");
