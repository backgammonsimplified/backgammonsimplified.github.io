(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.BMSPositionEditor = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // Factual codec provenance: backgammonsimplified/backgammoncalculator
  // @a385a963ed01a6eac083dae7a1b246b1c150b3eb, R/position_identifiers.R.
  // That accepted project implementation records the GNUID/XGID bit-field
  // concepts adapted from MIT-licensed bglab in GNUID_XGID_ATTRIBUTION.md and
  // THIRD_PARTY_NOTICES.md. This browser port implements only complete GNUID.
  const BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const COMPLETE_GNUID = /^[A-Za-z0-9+/]{14}:[A-Za-z0-9+/]{12}$/;
  const PLAYERS = ["player_0", "player_1"];
  const POINTS = Array.from({ length: 24 }, function (_value, index) {
    return "point_" + (index + 1);
  });
  const STARTING_GNUID = "4HPwATDgc/ABMA:cAnqAAAAAAAE";

  function editorError(message, rule) {
    const error = new Error(message);
    error.rule = rule;
    return error;
  }

  function otherPlayer(player) {
    return player === "player_0" ? "player_1" : "player_0";
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function base64ToBits(identifier) {
    const values = Array.from(identifier, function (character) {
      return BASE64.indexOf(character);
    });
    if (values.some(function (value) { return value < 0; })) {
      throw editorError("The GNUID contains a character outside the GNU Base64 alphabet.", "base64_alphabet");
    }
    const bytes = [];
    const groups = Math.floor(values.length / 4);
    for (let groupIndex = 0; groupIndex < groups; groupIndex += 1) {
      const start = groupIndex * 4;
      const group = values.slice(start, start + 4);
      bytes.push(
        group[0] * 4 + Math.floor(group[1] / 16),
        (group[1] % 16) * 16 + Math.floor(group[2] / 4),
        (group[2] % 4) * 64 + group[3]
      );
    }
    const remainder = values.length % 4;
    if (remainder === 2) {
      const final = values.slice(-2);
      bytes.push(final[0] * 4 + Math.floor(final[1] / 16));
    } else if (remainder !== 0) {
      throw editorError("The GNUID has an unsupported Base64 length.", "base64_length");
    }
    const bits = [];
    bytes.forEach(function (byte) {
      for (let shift = 0; shift < 8; shift += 1) bits.push((byte >> shift) & 1);
    });
    return bits;
  }

  function bitsToBase64(bits) {
    if (bits.length % 8 !== 0 || bits.some(function (bit) { return bit !== 0 && bit !== 1; })) {
      throw editorError("The editor could not encode the GNUID bit data.", "bit_encoding");
    }
    const bytes = [];
    for (let start = 0; start < bits.length; start += 8) {
      let byte = 0;
      for (let shift = 0; shift < 8; shift += 1) byte += bits[start + shift] * (2 ** shift);
      bytes.push(byte);
    }
    const values = [];
    const groups = Math.floor(bytes.length / 3);
    for (let groupIndex = 0; groupIndex < groups; groupIndex += 1) {
      const start = groupIndex * 3;
      const group = bytes.slice(start, start + 3);
      values.push(
        Math.floor(group[0] / 4),
        (group[0] % 4) * 16 + Math.floor(group[1] / 16),
        (group[1] % 16) * 4 + Math.floor(group[2] / 64),
        group[2] % 64
      );
    }
    const remainder = bytes.length % 3;
    if (remainder === 1) {
      const final = bytes[bytes.length - 1];
      values.push(Math.floor(final / 4), (final % 4) * 16);
    } else if (remainder === 2) {
      const final = bytes.slice(-2);
      values.push(
        Math.floor(final[0] / 4),
        (final[0] % 4) * 16 + Math.floor(final[1] / 16),
        (final[1] % 16) * 4
      );
    }
    return values.map(function (value) { return BASE64[value]; }).join("");
  }

  function readInteger(bits, start, width) {
    let value = 0;
    for (let shift = 0; shift < width; shift += 1) value += bits[start + shift] * (2 ** shift);
    return value;
  }

  function writeInteger(bits, start, width, value) {
    for (let shift = 0; shift < width; shift += 1) bits[start + shift] = (value >> shift) & 1;
  }

  function emptyPlayer() {
    return { points: Array(24).fill(0), bar: 0, off: 15 };
  }

  function clearState(base) {
    const source = base || startingState();
    return Object.assign(clone(source), {
      players: { player_0: emptyPlayer(), player_1: emptyPlayer() }
    });
  }

  function validatePositionId(positionId) {
    if (!/^[A-Za-z0-9+/]{14}$/.test(positionId)) {
      throw editorError("The Position ID must contain 14 GNU Base64 characters.", "position_id_format");
    }
    if (BASE64.indexOf(positionId[13]) % 16 !== 0) {
      throw editorError("The Position ID has non-zero padding bits.", "position_id_padding");
    }
  }

  function validateMatchId(matchId) {
    if (!/^[A-Za-z0-9+/]{12}$/.test(matchId)) {
      throw editorError("The Match ID must contain 12 GNU Base64 characters.", "match_id_format");
    }
  }

  function decodePositionId(positionId, diceOwner) {
    validatePositionId(positionId);
    const bits = base64ToBits(positionId);
    if (bits.length !== 80) throw editorError("The Position ID did not decode to 80 bits.", "position_id_length");
    const rows = [Array(25).fill(0), Array(25).fill(0)];
    let cursor = 0;
    for (let row = 0; row < 2; row += 1) {
      for (let slot = 0; slot < 25; slot += 1) {
        while (cursor < bits.length && bits[cursor] === 1) {
          rows[row][slot] += 1;
          cursor += 1;
        }
        if (cursor >= bits.length) throw editorError("The Position ID has a malformed checker sequence.", "unary_separator");
        cursor += 1;
      }
    }
    if (bits.slice(cursor).some(function (bit) { return bit !== 0; })) {
      throw editorError("The Position ID has non-zero trailing bits.", "position_id_trailing_bits");
    }
    if (rows.some(function (row) { return row.reduce(function (sum, count) { return sum + count; }, 0) > 15; })) {
      throw editorError("The Position ID assigns more than 15 checkers to a player.", "checker_total");
    }
    const stable = {};
    stable[diceOwner] = rows[1];
    stable[otherPlayer(diceOwner)] = rows[0];
    const players = {};
    PLAYERS.forEach(function (player) {
      const ownPoints = stable[player].slice(0, 24);
      const points = player === "player_0" ? ownPoints.reverse() : ownPoints;
      const bar = stable[player][24];
      players[player] = {
        points: points,
        bar: bar,
        off: 15 - points.reduce(function (sum, count) { return sum + count; }, 0) - bar
      };
    });
    for (let point = 0; point < 24; point += 1) {
      if (players.player_0.points[point] && players.player_1.points[point]) {
        throw editorError("Both players cannot occupy point " + (point + 1) + ".", "point_overlap");
      }
    }
    return players;
  }

  function decodeMatchId(matchId) {
    validateMatchId(matchId);
    const bits = base64ToBits(matchId);
    if (bits.length !== 72) throw editorError("The Match ID did not decode to 72 bits.", "match_id_length");
    const cubeOwnerCode = readInteger(bits, 4, 2);
    const cubeOwners = { 0: "player_0", 1: "player_1", 3: "centered" };
    const gameStateCode = readInteger(bits, 8, 3);
    const dice = [readInteger(bits, 15, 3), readInteger(bits, 18, 3)];
    if (!cubeOwners[cubeOwnerCode]) throw editorError("The Match ID uses a reserved cube-owner code.", "cube_owner_code");
    if (bits.slice(67).some(function (bit) { return bit !== 0; })) throw editorError("The Match ID uses reserved bits.", "reserved_bits");
    if (dice.some(function (die) { return die > 6; }) || ((dice[0] === 0) !== (dice[1] === 0))) {
      throw editorError("The Match ID contains invalid dice.", "dice_pair");
    }
    if (gameStateCode > 1) throw editorError("Only active or not-started games can be edited.", "game_state");
    if (readInteger(bits, 13, 2) !== 0) throw editorError("Resignation states are not supported by this editor.", "resignation");
    const diceOwner = readInteger(bits, 6, 1) === 0 ? "player_0" : "player_1";
    const turnOwner = readInteger(bits, 11, 1) === 0 ? "player_0" : "player_1";
    const doubleOffered = readInteger(bits, 12, 1) === 1;
    if (doubleOffered) throw editorError("Pending-double identifiers are not analysis editor inputs.", "pending_double");
    if (diceOwner !== turnOwner) throw editorError("The Match ID has inconsistent turn ownership.", "turn_owner");
    return {
      turn: { dice_owner: diceOwner, turn_owner: turnOwner, dice: dice[0] === 0 ? [] : dice },
      cube: { exponent: readInteger(bits, 0, 4), owner: cubeOwners[cubeOwnerCode] },
      score: { player_0: readInteger(bits, 36, 15), player_1: readInteger(bits, 51, 15) },
      match: {
        length: readInteger(bits, 21, 15),
        crawford: readInteger(bits, 7, 1) === 1,
        jacoby: readInteger(bits, 66, 1) === 0,
        game_state_code: gameStateCode
      }
    };
  }

  function decodeGnuid(identifier) {
    const gnuid = String(identifier || "").trim();
    if (!COMPLETE_GNUID.test(gnuid)) {
      throw editorError("Enter a complete 14-character Position ID and 12-character Match ID separated by a colon.", "complete_gnuid_format");
    }
    const parts = gnuid.split(":");
    const decodedMatch = decodeMatchId(parts[1]);
    const state = {
      schema_version: "b" + "ms-position-editor-state-v1",
      players: decodePositionId(parts[0], decodedMatch.turn.dice_owner),
      turn: decodedMatch.turn,
      cube: decodedMatch.cube,
      score: decodedMatch.score,
      match: decodedMatch.match,
      decision: decodedMatch.turn.dice.length === 2 ? "checker" : "cube",
      view_flipped: false
    };
    const errors = validateState(state, { requireDecision: true });
    if (errors.length) throw editorError(errors[0], "invalid_identifier_state");
    return state;
  }

  function validateState(state, options) {
    const errors = [];
    if (!state || !state.players) return ["The editor state is missing its checker records."];
    PLAYERS.forEach(function (player) {
      const record = state.players[player];
      if (!record || !Array.isArray(record.points) || record.points.length !== 24) {
        errors.push((player === "player_0" ? "Copper" : "Navy") + " must have 24 point counts.");
        return;
      }
      const counts = record.points.concat([record.bar, record.off]);
      if (counts.some(function (count) { return !Number.isInteger(count) || count < 0 || count > 15; })) {
        errors.push((player === "player_0" ? "Copper" : "Navy") + " checker counts must be whole numbers from 0 to 15.");
      }
      const total = counts.reduce(function (sum, count) { return sum + count; }, 0);
      if (total !== 15) errors.push((player === "player_0" ? "Copper" : "Navy") + " must have exactly 15 checkers; currently " + total + ".");
    });
    if (state.players.player_0 && state.players.player_1 && Array.isArray(state.players.player_0.points) && Array.isArray(state.players.player_1.points)) {
      for (let point = 0; point < 24; point += 1) {
        if (state.players.player_0.points[point] > 0 && state.players.player_1.points[point] > 0) {
          errors.push("Point " + (point + 1) + " contains both checker colours.");
        }
      }
    }
    if (!state.turn || !PLAYERS.includes(state.turn.dice_owner)) errors.push("Choose which player is on roll.");
    if (!state.cube || !Number.isInteger(state.cube.exponent) || state.cube.exponent < 0 || state.cube.exponent > 15) errors.push("Cube value must be a power of two from 1 through 32768.");
    if (!state.cube || !["centered", "player_0", "player_1"].includes(state.cube.owner)) errors.push("Choose centered, Copper-owned, or Navy-owned cube state.");
    const matchLength = state.match && state.match.length;
    const scores = state.score || {};
    if (!Number.isInteger(matchLength) || matchLength < 0 || matchLength > 32767) errors.push("Match length must be a whole number from 0 through 32767.");
    if (!Number.isInteger(scores.player_0) || scores.player_0 < 0 || scores.player_0 > 32767 || !Number.isInteger(scores.player_1) || scores.player_1 < 0 || scores.player_1 > 32767) {
      errors.push("Both scores must be whole numbers from 0 through 32767.");
    } else if (Number.isInteger(matchLength) && matchLength > 0 && (scores.player_0 >= matchLength || scores.player_1 >= matchLength)) {
      errors.push("In an active match, both scores must be below the match length.");
    }
    if (matchLength === 0 && state.match && state.match.crawford) errors.push("Crawford cannot be enabled in unlimited play.");
    if (matchLength > 0 && state.match && state.match.jacoby) errors.push("Jacoby applies only to unlimited play.");
    if (state.match && state.match.crawford && Number.isInteger(matchLength) && matchLength > 0) {
      const oneAway = [scores.player_0, scores.player_1].filter(function (score) { return score === matchLength - 1; }).length;
      if (oneAway !== 1) errors.push("Crawford requires exactly one player to be one point from the match.");
      if (state.cube.exponent !== 0 || state.cube.owner !== "centered") errors.push("A Crawford game requires a centered 1-cube.");
    }
    if (!state.match || ![0, 1].includes(state.match.game_state_code)) errors.push("The active game state is invalid.");
    if (options && options.requireDecision) {
      if (!state.decision || !["checker", "cube"].includes(state.decision)) errors.push("Choose a checker or cube decision.");
      if (state.decision === "checker") {
        if (!state.turn || !Array.isArray(state.turn.dice) || state.turn.dice.length !== 2 || state.turn.dice.some(function (die) { return !Number.isInteger(die) || die < 1 || die > 6; })) {
          errors.push("Checker analysis requires two dice values from 1 to 6.");
        }
      }
    }
    return Array.from(new Set(errors));
  }

  function encodePositionId(state) {
    const ownRows = {
      player_0: state.players.player_0.points.slice().reverse().concat([state.players.player_0.bar]),
      player_1: state.players.player_1.points.slice().concat([state.players.player_1.bar])
    };
    const diceOwner = state.turn.dice_owner;
    const rows = [ownRows[otherPlayer(diceOwner)], ownRows[diceOwner]];
    let bits = [];
    rows.forEach(function (row) {
      row.forEach(function (count) {
        bits = bits.concat(Array(count).fill(1), [0]);
      });
    });
    if (bits.length > 80) throw editorError("This checker state exceeds GNU Position ID capacity.", "position_capacity");
    bits = bits.concat(Array(80 - bits.length).fill(0));
    return bitsToBase64(bits);
  }

  function encodeMatchId(state) {
    const bits = Array(72).fill(0);
    const ownerCodes = { player_0: 0, player_1: 1, centered: 3 };
    const dice = state.decision === "checker" ? state.turn.dice.slice().sort(function (a, b) { return b - a; }) : [0, 0];
    [
      [0, 4, state.cube.exponent],
      [4, 2, ownerCodes[state.cube.owner]],
      [6, 1, state.turn.dice_owner === "player_0" ? 0 : 1],
      [7, 1, state.match.crawford ? 1 : 0],
      [8, 3, state.match.game_state_code],
      [11, 1, state.turn.dice_owner === "player_0" ? 0 : 1],
      [12, 1, 0], [13, 2, 0],
      [15, 3, dice[0]], [18, 3, dice[1]],
      [21, 15, state.match.length],
      [36, 15, state.score.player_0], [51, 15, state.score.player_1],
      [66, 1, state.match.jacoby ? 0 : 1], [67, 5, 0]
    ].forEach(function (field) { writeInteger(bits, field[0], field[1], field[2]); });
    return bitsToBase64(bits);
  }

  function encodeGnuid(state) {
    const errors = validateState(state, { requireDecision: true });
    if (errors.length) throw editorError(errors[0], "invalid_editor_state");
    return encodePositionId(state) + ":" + encodeMatchId(state);
  }

  function serializeRequest(state) {
    const gnuid = encodeGnuid(state);
    return {
      schema_version: "b" + "ms-analysis-submission-v2",
      engine: "gnu",
      decision_type: state.decision,
      analysis_setting: "1ply",
      position: { format: "gnuid", id: gnuid },
      dice: state.decision === "checker" ? state.turn.dice.slice() : null
    };
  }

  function serializeAdapterRequest(state) {
    const request = serializeRequest(state);
    return {
      gnuid: request.position.id,
      decision: request.decision_type,
      dice: request.dice,
      engine: request.engine,
      analysis_setting: request.analysis_setting
    };
  }

  function startingState() {
    return decodeGnuid(STARTING_GNUID);
  }

  function pointPlacement(point) {
    if (point >= 13 && point <= 18) return { row: 1, column: point - 12, edge: "top" };
    if (point >= 19) return { row: 1, column: point - 11, edge: "top" };
    if (point >= 7) return { row: 2, column: 13 - point, edge: "bottom" };
    return { row: 2, column: 14 - point, edge: "bottom" };
  }

  function playerLabel(player) {
    return player === "player_0" ? "Copper" : "Navy";
  }

  function describeSlot(slot) {
    if (slot.indexOf("point_") === 0) return "point " + slot.slice(6);
    const parts = slot.split(":");
    return playerLabel(parts[1]) + " " + (parts[0] === "bar" ? "bar" : "off tray");
  }

  function slotRecord(state, slot) {
    if (slot.indexOf("point_") === 0) {
      const index = Number(slot.slice(6)) - 1;
      return {
        get: function (player) { return state.players[player].points[index]; },
        set: function (player, value) { state.players[player].points[index] = value; }
      };
    }
    const parts = slot.split(":");
    return {
      owner: parts[1],
      get: function (player) { return player === parts[1] ? state.players[player][parts[0]] : 0; },
      set: function (player, value) { if (player === parts[1]) state.players[player][parts[0]] = value; }
    };
  }

  function moveCheckerState(state, player, from, to) {
    if (!PLAYERS.includes(player)) throw editorError("Choose Copper or Navy before editing checkers.", "checker_player");
    const source = slotRecord(state, from);
    const destination = slotRecord(state, to);
    if (source.get(player) < 1) throw editorError("The source does not contain that checker.", "checker_source");
    if (from === to) throw editorError("Choose a different checker destination.", "checker_destination");
    if (destination.owner && destination.owner !== player) throw editorError("A checker cannot use the other player's bar or off tray.", "checker_owner");
    if (to.indexOf("point_") === 0 && destination.get(otherPlayer(player)) > 0) throw editorError("Both checker colours cannot occupy one point.", "point_overlap");
    source.set(player, source.get(player) - 1);
    destination.set(player, destination.get(player) + 1);
    return state;
  }

  function createController(surface, options) {
    const form = surface.closest("[data-bs-live-analyzer]").querySelector("[data-bs-analyzer-form]");
    // Quarto annotates full-page raw HTML containers with its publication grid
    // classes. The editor owns an independent responsive grid inside that page.
    surface.classList.remove("page-columns", "page-full");
    form.classList.remove("page-columns", "page-full");
    const board = surface.querySelector("[data-bs-editor-board]");
    const errorsHost = surface.querySelector("[data-bs-editor-errors]");
    const announcement = surface.querySelector("[data-bs-editor-announcement]");
    const identifierOutput = surface.querySelector("[data-bs-editor-identifier-output]");
    const gnuidInput = form.querySelector('[name="gnuid"]');
    const undoButton = surface.querySelector("[data-bs-editor-action=undo]");
    let state = (options && options.state) ? clone(options.state) : startingState();
    let history = [];
    let selected = null;
    let drag = null;

    function announce(message) {
      if (announcement) announcement.textContent = message;
    }

    function snapshot() {
      return clone(state);
    }

    function setControl(selector, value) {
      const element = form.querySelector(selector);
      if (element) element.value = String(value);
    }

    function checkerCount(slot, player) {
      return slotRecord(state, slot).get(player);
    }

    function slotAria(slot) {
      if (slot.indexOf("point_") === 0) {
        return describeSlot(slot) + ", " + checkerCount(slot, "player_0") + " Copper and " + checkerCount(slot, "player_1") + " Navy checkers";
      }
      const owner = slotRecord(state, slot).owner;
      return describeSlot(slot) + ", " + checkerCount(slot, owner) + " checkers";
    }

    function select(player, slot) {
      if (checkerCount(slot, player) < 1) return;
      selected = { player: player, slot: slot };
      renderBoard();
      announce(playerLabel(player) + " checker selected on " + describeSlot(slot) + ". Choose a destination, or use Remove selected.");
    }

    function canMove(player, from, to) {
      if (!from || !to || from === to) return "Choose a different destination.";
      const source = slotRecord(state, from);
      const destination = slotRecord(state, to);
      if (source.get(player) < 1) return "The selected checker is no longer available.";
      if (destination.owner && destination.owner !== player) return playerLabel(player) + " cannot use the other player's " + to.split(":")[0] + ".";
      if (to.indexOf("point_") === 0 && destination.get(otherPlayer(player)) > 0) return describeSlot(to) + " is occupied by " + playerLabel(otherPlayer(player)) + ".";
      return null;
    }

    function move(player, from, to, message) {
      const reason = canMove(player, from, to);
      if (reason) { announce(reason); return false; }
      history.push(snapshot());
      if (history.length > 100) history.shift();
      moveCheckerState(state, player, from, to);
      selected = null;
      sync();
      announce(message || playerLabel(player) + " moved from " + describeSlot(from) + " to " + describeSlot(to) + ".");
      return true;
    }

    function activePlacementPlayer() {
      const checked = surface.querySelector('[name="placement-side"]:checked');
      return checked ? checked.value : "player_0";
    }

    function activateDestination(slot) {
      if (selected) return move(selected.player, selected.slot, slot);
      const player = activePlacementPlayer();
      return move(player, "off:" + player, slot, playerLabel(player) + " checker placed on " + describeSlot(slot) + ".");
    }

    function makeChecker(slot, player, index, count, edge) {
      const checker = document.createElement("button");
      checker.type = "button";
      checker.className = "bs-editor-checker bs-editor-checker--" + player;
      checker.dataset.player = player;
      checker.dataset.sourceSlot = slot;
      checker.style.setProperty("--stack-index", String(index));
      checker.style.setProperty("--stack-total", String(Math.min(count, 5)));
      checker.dataset.edge = edge;
      checker.setAttribute("aria-label", playerLabel(player) + " checker on " + describeSlot(slot) + (count > 5 && index === 4 ? ", stack of " + count : ""));
      if (count > 5 && index === 4) checker.textContent = String(count);
      if (selected && selected.player === player && selected.slot === slot && index === Math.min(count, 5) - 1) checker.classList.add("is-selected");
      checker.addEventListener("click", function (event) { event.stopPropagation(); select(player, slot); });
      checker.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); event.stopPropagation(); select(player, slot); }
        if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); event.stopPropagation(); move(player, slot, "off:" + player); }
      });
      checker.addEventListener("pointerdown", beginPointer);
      return checker;
    }

    function appendStack(element, slot, edge) {
      PLAYERS.forEach(function (player) {
        const count = checkerCount(slot, player);
        for (let index = 0; index < Math.min(count, 5); index += 1) element.appendChild(makeChecker(slot, player, index, count, edge));
      });
    }

    function makeSlot(slot, point, placement) {
      const element = document.createElement("div");
      element.className = "bs-editor-slot bs-editor-slot--" + placement.edge + (point ? " bs-editor-point bs-editor-point--" + (point % 2 ? "copper" : "ivory") : " bs-editor-bar");
      element.dataset.slot = slot;
      element.tabIndex = 0;
      element.setAttribute("role", "button");
      element.setAttribute("aria-label", slotAria(slot));
      element.style.gridRow = String(placement.row);
      element.style.gridColumn = String(placement.column);
      element.addEventListener("click", function () { activateDestination(slot); });
      element.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activateDestination(slot); }
      });
      if (point) {
        const label = document.createElement("span");
        label.className = "bs-editor-point-label";
        label.textContent = String(point);
        element.appendChild(label);
      } else {
        const label = document.createElement("span");
        label.className = "bs-editor-bar-label";
        label.textContent = placement.edge === "top" ? "Navy bar" : "Copper bar";
        element.appendChild(label);
      }
      appendStack(element, slot, placement.edge);
      return element;
    }

    function renderOff(slot, element, edge) {
      element.replaceChildren();
      element.dataset.slot = slot;
      element.tabIndex = 0;
      element.setAttribute("role", "button");
      element.setAttribute("aria-label", slotAria(slot));
      element.onclick = function () { activateDestination(slot); };
      element.onkeydown = function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activateDestination(slot); }
      };
      const title = document.createElement("span");
      title.className = "bs-editor-off-label";
      title.textContent = describeSlot(slot);
      element.appendChild(title);
      appendStack(element, slot, edge);
    }

    function renderBoard() {
      board.replaceChildren();
      for (let point = 1; point <= 24; point += 1) {
        const visualPoint = state.view_flipped ? 25 - point : point;
        board.appendChild(makeSlot("point_" + point, point, pointPlacement(visualPoint)));
      }
      board.appendChild(makeSlot("bar:player_1", null, state.view_flipped ? { row: 2, column: 7, edge: "bottom" } : { row: 1, column: 7, edge: "top" }));
      board.appendChild(makeSlot("bar:player_0", null, state.view_flipped ? { row: 1, column: 7, edge: "top" } : { row: 2, column: 7, edge: "bottom" }));
      renderOff("off:player_1", surface.querySelector("[data-bs-editor-off=player_1]"), "top");
      renderOff("off:player_0", surface.querySelector("[data-bs-editor-off=player_0]"), "bottom");
    }

    function renderValidation() {
      const errors = validateState(state, { requireDecision: true });
      errorsHost.replaceChildren();
      if (errors.length) {
        const heading = document.createElement("strong");
        heading.textContent = "Fix before analysis";
        const list = document.createElement("ul");
        errors.forEach(function (message) { const item = document.createElement("li"); item.textContent = message; list.appendChild(item); });
        errorsHost.append(heading, list);
        errorsHost.hidden = false;
        gnuidInput.value = "";
        gnuidInput.setAttribute("aria-invalid", "true");
        identifierOutput.value = "Position is not serializable yet.";
      } else {
        errorsHost.hidden = true;
        gnuidInput.removeAttribute("aria-invalid");
        const gnuid = encodeGnuid(state);
        gnuidInput.value = gnuid;
        identifierOutput.value = gnuid;
      }
      return errors;
    }

    function syncControls() {
      const onRoll = form.querySelector('[name="on_roll"][value="' + state.turn.dice_owner + '"]');
      if (onRoll) onRoll.checked = true;
      const decision = form.querySelector('[name="decision"][value="' + state.decision + '"]');
      if (decision) decision.checked = true;
      setControl('[name="die1"]', state.turn.dice[0] || "");
      setControl('[name="die2"]', state.turn.dice[1] || "");
      setControl('[name="cube_value"]', 2 ** state.cube.exponent);
      setControl('[name="cube_owner"]', state.cube.owner);
      setControl('[name="match_length"]', state.match.length);
      setControl('[name="score_player_0"]', state.score.player_0);
      setControl('[name="score_player_1"]', state.score.player_1);
      const crawford = form.querySelector('[name="crawford"]');
      const jacoby = form.querySelector('[name="jacoby"]');
      crawford.checked = Boolean(state.match.crawford);
      crawford.disabled = state.match.length === 0;
      jacoby.checked = Boolean(state.match.jacoby);
      jacoby.disabled = state.match.length > 0;
      const diceGroup = form.querySelector("[data-bs-checker-dice]");
      if (diceGroup) diceGroup.hidden = state.decision !== "checker";
      form.querySelectorAll("[data-bs-checker-die]").forEach(function (input) {
        input.disabled = state.decision !== "checker";
        input.required = state.decision === "checker";
      });
      surface.querySelector("[data-bs-editor-turn-summary]").textContent = playerLabel(state.turn.dice_owner) + " on roll";
      surface.querySelector("[data-bs-editor-total=player_0]").textContent = String(state.players.player_0.points.reduce(function (sum, count) { return sum + count; }, state.players.player_0.bar + state.players.player_0.off));
      surface.querySelector("[data-bs-editor-total=player_1]").textContent = String(state.players.player_1.points.reduce(function (sum, count) { return sum + count; }, state.players.player_1.bar + state.players.player_1.off));
      undoButton.disabled = history.length === 0;
    }

    function sync() {
      syncControls();
      renderBoard();
      renderValidation();
    }

    function notifyChange() {
      if (typeof CustomEvent === "function") {
        surface.dispatchEvent(
          new CustomEvent("bs-position-editor-change", {
            bubbles: true,
            detail: { gnuid: gnuidInput.value || null }
          })
        );
      }
    }

    function update(mutator, message) {
      history.push(snapshot());
      if (history.length > 100) history.shift();
      mutator(state);
      selected = null;
      sync();
      notifyChange();
      announce(message);
    }

    function beginPointer(event) {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const checker = event.currentTarget;
      drag = {
        pointerId: event.pointerId,
        player: checker.dataset.player,
        slot: checker.dataset.sourceSlot,
        x: event.clientX,
        y: event.clientY,
        active: false,
        origin: checker,
        ghost: null
      };
      checker.setPointerCapture && checker.setPointerCapture(event.pointerId);
      window.addEventListener("pointermove", pointerMove, { passive: false });
      window.addEventListener("pointerup", pointerEnd, { once: true });
      window.addEventListener("pointercancel", pointerCancel, { once: true });
    }

    function destinationAt(x, y) {
      const element = document.elementFromPoint(x, y);
      return element && element.closest ? element.closest("[data-slot]") : null;
    }

    function clearDropState() {
      surface.querySelectorAll(".is-drop-target,.is-drop-invalid").forEach(function (element) { element.classList.remove("is-drop-target", "is-drop-invalid"); });
    }

    function pointerMove(event) {
      if (!drag || event.pointerId !== drag.pointerId) return;
      if (!drag.active && Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 7) return;
      event.preventDefault();
      if (!drag.active) {
        drag.active = true;
        drag.ghost = drag.origin.cloneNode(true);
        drag.ghost.classList.add("bs-editor-drag-ghost");
        drag.ghost.removeAttribute("style");
        document.body.appendChild(drag.ghost);
        drag.origin.classList.add("is-drag-origin");
      }
      drag.ghost.style.left = event.clientX + "px";
      drag.ghost.style.top = event.clientY + "px";
      clearDropState();
      const destination = destinationAt(event.clientX, event.clientY);
      if (destination) destination.classList.add(canMove(drag.player, drag.slot, destination.dataset.slot) ? "is-drop-invalid" : "is-drop-target");
    }

    function cleanPointer() {
      if (!drag) return;
      if (drag.ghost) drag.ghost.remove();
      if (drag.origin) drag.origin.classList.remove("is-drag-origin");
      clearDropState();
      window.removeEventListener("pointermove", pointerMove);
    }

    function pointerEnd(event) {
      if (!drag || event.pointerId !== drag.pointerId) return;
      const current = drag;
      const destination = current.active ? destinationAt(event.clientX, event.clientY) : null;
      cleanPointer();
      drag = null;
      if (current.active) {
        if (destination) move(current.player, current.slot, destination.dataset.slot);
        else announce("Drag cancelled. Drop on a point, bar, or off tray.");
      }
    }

    function pointerCancel() {
      cleanPointer();
      drag = null;
      announce("Drag cancelled.");
    }

    form.addEventListener("change", function (event) {
      const target = event.target;
      if (!target || !target.name) return;
      if (target.name === "decision") update(function (value) { value.decision = target.value; }, target.value === "checker" ? "Checker decision selected." : "Cube decision selected; request dice will be null.");
      if (target.name === "on_roll") update(function (value) { value.turn.dice_owner = target.value; value.turn.turn_owner = target.value; }, playerLabel(target.value) + " is now on roll.");
      if (target.name === "die1" || target.name === "die2") update(function (value) {
        const die1 = Number(form.elements.die1.value); const die2 = Number(form.elements.die2.value);
        value.turn.dice = die1 && die2 ? [die1, die2] : [];
      }, "Checker dice updated.");
      if (target.name === "cube_value") update(function (value) { value.cube.exponent = Math.log2(Number(target.value)); }, "Cube value updated.");
      if (target.name === "cube_owner") update(function (value) { value.cube.owner = target.value; }, "Cube ownership updated.");
      if (target.name === "match_length") update(function (value) {
        value.match.length = Number(target.value);
        if (value.match.length === 0) value.match.crawford = false;
        else value.match.jacoby = false;
      }, Number(target.value) === 0 ? "Unlimited play selected." : target.value + "-point match selected.");
      if (target.name === "score_player_0" || target.name === "score_player_1") update(function (value) { value.score[target.name.replace("score_", "")] = Number(target.value); }, "Score updated.");
      if (target.name === "crawford") update(function (value) { value.match.crawford = target.checked; }, target.checked ? "Crawford enabled." : "Crawford disabled.");
      if (target.name === "jacoby") update(function (value) { value.match.jacoby = target.checked; }, target.checked ? "Jacoby enabled." : "Jacoby disabled.");
    });

    surface.querySelectorAll("[data-bs-editor-action]").forEach(function (button) {
      button.addEventListener("click", function () {
        const action = button.dataset.bsEditorAction;
        if (action === "start") update(function () { state = startingState(); }, "Standard starting position restored.");
        if (action === "clear") update(function () { state = clearState(state); }, "Board cleared; all checkers moved to their off trays.");
        if (action === "flip") update(function (value) { value.view_flipped = !value.view_flipped; }, "Board view flipped. Factual point numbers are unchanged.");
        if (action === "undo") {
          const previous = history.pop();
          if (previous) { state = previous; selected = null; sync(); notifyChange(); announce("Last editor change undone."); }
        }
        if (action === "remove") {
          if (selected) move(selected.player, selected.slot, "off:" + selected.player, "Selected checker moved to its off tray.");
          else announce("Select a checker before choosing Remove selected.");
        }
        if (action === "import") {
          const input = surface.querySelector("[data-bs-editor-import]");
          try {
            const imported = decodeGnuid(input.value);
            history.push(snapshot());
            imported.view_flipped = state.view_flipped;
            state = imported;
            selected = null;
            input.removeAttribute("aria-invalid");
            sync();
            notifyChange();
            announce("Complete GNUID imported into the editor.");
          } catch (error) {
            announce("Could not import GNUID: " + error.message);
            input.setAttribute("aria-invalid", "true");
          }
        }
        if (action === "copy") {
          if (!gnuidInput.value) { announce("Fix the editor errors before copying a GNUID."); return; }
          const copied = function () { announce("Complete GNUID copied."); };
          if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(gnuidInput.value).then(copied, function () { identifierOutput.select(); document.execCommand("copy"); copied(); });
          else { identifierOutput.select(); document.execCommand("copy"); copied(); }
        }
      });
    });

    sync();
    announce("Interactive position editor ready. Choose a checker, then choose its destination.");
    return {
      getState: function () { return snapshot(); },
      setState: function (value) { state = clone(value); selected = null; sync(); notifyChange(); },
      move: move,
      select: select,
      serializeGnuid: function () { return encodeGnuid(state); },
      serializeRequest: function () { return serializeRequest(state); },
      undo: function () { const previous = history.pop(); if (previous) { state = previous; sync(); notifyChange(); } }
    };
  }

  function mountAll() {
    document.querySelectorAll("[data-bs-position-editor]").forEach(function (surface) {
      if (!surface.bsPositionEditor) surface.bsPositionEditor = createController(surface);
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountAll, { once: true });
    else mountAll();
  }

  return {
    BASE64: BASE64,
    COMPLETE_GNUID: COMPLETE_GNUID,
    STARTING_GNUID: STARTING_GNUID,
    base64ToBits: base64ToBits,
    bitsToBase64: bitsToBase64,
    clearState: clearState,
    createController: createController,
    decodeGnuid: decodeGnuid,
    encodeGnuid: encodeGnuid,
    mountAll: mountAll,
    moveCheckerState: moveCheckerState,
    serializeAdapterRequest: serializeAdapterRequest,
    serializeRequest: serializeRequest,
    startingState: startingState,
    validateState: validateState
  };
});
