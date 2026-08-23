const assert = require("node:assert/strict");
const editor = require("../site/assets/bs-position-editor.js");

function copy(value) {
  return JSON.parse(JSON.stringify(value));
}

const start = editor.startingState();
assert.equal(editor.encodeGnuid(start), editor.STARTING_GNUID);
assert.deepEqual(start.players.player_0.points, [2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 3, 0, 5, 0, 0, 0, 0, 0]);
assert.deepEqual(start.players.player_1.points, [0, 0, 0, 0, 0, 5, 0, 3, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]);
assert.equal(start.players.player_0.off, 0);
assert.equal(start.players.player_1.off, 0);

const cleared = editor.clearState(start);
assert.ok(cleared.players.player_0.points.every((count) => count === 0));
assert.ok(cleared.players.player_1.points.every((count) => count === 0));
assert.equal(cleared.players.player_0.off, 15);
assert.equal(cleared.players.player_1.off, 15);
assert.deepEqual(editor.validateState(cleared, { requireDecision: true }), []);

const moved = copy(start);
editor.moveCheckerState(moved, "player_0", "point_1", "point_2");
assert.equal(moved.players.player_0.points[0], 1);
assert.equal(moved.players.player_0.points[1], 1);
editor.moveCheckerState(moved, "player_0", "point_2", "bar:player_0");
assert.equal(moved.players.player_0.bar, 1);
editor.moveCheckerState(moved, "player_0", "bar:player_0", "off:player_0");
assert.equal(moved.players.player_0.off, 1);
assert.deepEqual(editor.validateState(moved, { requireDecision: true }), []);

const placed = editor.clearState(start);
editor.moveCheckerState(placed, "player_0", "off:player_0", "point_4");
editor.moveCheckerState(placed, "player_1", "off:player_1", "point_21");
assert.equal(placed.players.player_0.points[3], 1);
assert.equal(placed.players.player_1.points[20], 1);
assert.equal(placed.players.player_0.off, 14);
assert.equal(placed.players.player_1.off, 14);
assert.throws(() => editor.moveCheckerState(placed, "player_1", "point_21", "point_4"), /Both checker colours/);
assert.throws(() => editor.moveCheckerState(placed, "player_0", "point_4", "bar:player_1"), /other player's bar/);
editor.moveCheckerState(placed, "player_1", "point_21", "bar:player_1");
assert.equal(placed.players.player_1.bar, 1);
editor.moveCheckerState(placed, "player_1", "bar:player_1", "off:player_1");
assert.equal(placed.players.player_1.off, 15);

const checkerRequest = editor.serializeRequest(start);
assert.deepEqual(checkerRequest, {
  schema_version: "b" + "ms-analysis-submission-v2",
  engine: "gnu",
  decision_type: "checker",
  analysis_setting: "1ply",
  position: { format: "gnuid", id: editor.STARTING_GNUID },
  dice: [4, 2]
});
assert.deepEqual(editor.serializeRequest(copy(start)), checkerRequest);
assert.deepEqual(editor.serializeAdapterRequest(start), {
  gnuid: editor.STARTING_GNUID,
  decision: "checker",
  dice: [4, 2],
  engine: "gnu",
  analysis_setting: "1ply"
});

const cube = copy(start);
cube.decision = "cube";
const cubeRequest = editor.serializeRequest(cube);
assert.equal(cubeRequest.decision_type, "cube");
assert.equal(cubeRequest.dice, null);
assert.equal(cubeRequest.position.id, "4HPwATDgc/ABMA:cAngAAAAAAAE");
assert.deepEqual(editor.decodeGnuid(cubeRequest.position.id).turn.dice, []);

const regressionVectors = [
  "4HPwATDgc/ABMA:8IhuACAACAAE",
  "ewMAAD4gAAAAAA:AQGqAAAAAAAE",
  "ewMAAD4gAAAAAA:EQGqAAAAAAAE",
  "ewMAAD4gAAAAAA:UQmqAAAAAAAE",
  "PAAAICMAAAAAAA:cAngAAAAAAAE"
];
for (const gnuid of regressionVectors) {
  const decoded = editor.decodeGnuid(gnuid);
  assert.equal(editor.encodeGnuid(decoded), gnuid, gnuid);
  assert.deepEqual(editor.decodeGnuid(editor.encodeGnuid(decoded)), decoded, gnuid);
}

const rollChanged = copy(start);
rollChanged.turn.dice_owner = "player_0";
rollChanged.turn.turn_owner = "player_0";
const rollIdentifier = editor.encodeGnuid(rollChanged);
assert.notEqual(rollIdentifier, editor.STARTING_GNUID);
assert.equal(editor.decodeGnuid(rollIdentifier).turn.dice_owner, "player_0");

const matchChanged = copy(start);
matchChanged.match.length = 5;
matchChanged.score.player_0 = 2;
matchChanged.score.player_1 = 3;
matchChanged.cube = { exponent: 2, owner: "player_1" };
const matchIdentifier = editor.encodeGnuid(matchChanged);
const matchRoundTrip = editor.decodeGnuid(matchIdentifier);
assert.deepEqual(matchRoundTrip.score, matchChanged.score);
assert.equal(matchRoundTrip.match.length, 5);
assert.deepEqual(matchRoundTrip.cube, matchChanged.cube);

const invalidTotal = copy(start);
invalidTotal.players.player_0.off = 1;
assert.match(editor.validateState(invalidTotal, { requireDecision: true }).join(" "), /exactly 15/);

const invalidOverlap = copy(start);
invalidOverlap.players.player_1.points[0] = 1;
invalidOverlap.players.player_1.points[5] -= 1;
assert.match(editor.validateState(invalidOverlap, { requireDecision: true }).join(" "), /Point 1 contains both/);

const invalidDice = copy(start);
invalidDice.turn.dice = [0, 7];
assert.match(editor.validateState(invalidDice, { requireDecision: true }).join(" "), /two dice values/);
assert.throws(() => editor.encodeGnuid(invalidDice), /Checker analysis requires/);

const invalidScore = copy(start);
invalidScore.score.player_0 = 7;
assert.match(editor.validateState(invalidScore, { requireDecision: true }).join(" "), /below the match length/);

const invalidCrawford = copy(start);
invalidCrawford.match.crawford = true;
invalidCrawford.cube = { exponent: 1, owner: "player_0" };
assert.match(editor.validateState(invalidCrawford, { requireDecision: true }).join(" "), /Crawford requires/);
assert.match(editor.validateState(invalidCrawford, { requireDecision: true }).join(" "), /centered 1-cube/);

const invalidJacoby = copy(start);
invalidJacoby.match.jacoby = true;
assert.match(editor.validateState(invalidJacoby, { requireDecision: true }).join(" "), /unlimited play/);

const money = copy(start);
money.match.length = 0;
money.match.jacoby = true;
money.score = { player_0: 12, player_1: 9 };
assert.deepEqual(editor.validateState(money, { requireDecision: true }), []);
assert.equal(editor.decodeGnuid(editor.encodeGnuid(money)).match.jacoby, true);

for (const identifier of ["", "4HPwATDgc/ABMA", "XGID=-b----E-C---eE---c-e----B-:0:0:1:53:1:2:1:3:10", "4HPwATDgc/ABMB:cAnqAAAAAAAE"]) {
  assert.throws(() => editor.decodeGnuid(identifier));
}

console.log("interactive position editor state, GNUID, validation, and request contracts passed");
