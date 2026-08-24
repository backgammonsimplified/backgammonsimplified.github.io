#!/usr/bin/env python3
"""Resolve accepted GNU checker notation to one legal ordered movement.

This is an Analyzer-side, non-browser preparation boundary.  It consumes only
an accepted GNU Position ID, the accepted checker dice, and normalized
candidate notation.  It does not run an engine, evaluate a position, rank a
candidate, or parse raw GNU output.

The compact notation grammar and legal-play enumeration are aligned with the
project-owned ``candidate-board-reconstruction-v1`` implementation frozen at
Explainer commit 58522bb078ecda273a11476c60f1875a2255b285.  Prepared steps are
still passed through the accepted backgammonboard movement authority and the
result is encoded/round-tripped by the accepted backgammoncalculator authority.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


PREPARER_VERSION = "analyzer-gnu-checker-movement-preparer-v1"
SOURCE_RECONSTRUCTION_VERSION = "candidate-board-reconstruction-v1"
SOURCE_EXPLAINER_COMMIT = "58522bb078ecda273a11476c60f1875a2255b285"
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
MOVE_TOKEN_RE = re.compile(
    r"^(?P<path>(?:bar|BAR|off|OFF|[0-9]+)(?:/(?:bar|BAR|off|OFF|[0-9]+)\*?)+)"
    r"(?:\((?P<count>[2-4])\))?$"
)


class MovementPreparationError(ValueError):
    """Notation cannot be resolved to exactly one legal factual play."""


@dataclass(frozen=True)
class PositionBoard:
    """GNU-relative opponent/player point arrays, each ending with the bar."""

    players: tuple[tuple[int, ...], tuple[int, ...]]

    def __post_init__(self) -> None:
        if len(self.players) != 2 or any(len(player) != 25 for player in self.players):
            raise MovementPreparationError("a GNU board requires two arrays of 25 counts")
        if any(
            not isinstance(count, int) or isinstance(count, bool) or count < 0
            for player in self.players
            for count in player
        ):
            raise MovementPreparationError("checker counts must be non-negative integers")
        if any(sum(player) > 15 for player in self.players):
            raise MovementPreparationError("a player has more than 15 checkers on board and bar")
        for point_index in range(24):
            if self.players[1][point_index] and self.players[0][23 - point_index]:
                raise MovementPreparationError("both players occupy one physical point")

    @property
    def opponent(self) -> tuple[int, ...]:
        return self.players[0]

    @property
    def player(self) -> tuple[int, ...]:
        return self.players[1]

    @property
    def borne_off(self) -> tuple[int, int]:
        return (15 - sum(self.opponent), 15 - sum(self.player))

    def receipt_value(self) -> dict[str, Any]:
        return {
            "perspective": "decision_player",
            "opponent_points_1_to_24_and_bar": list(self.opponent),
            "player_points_1_to_24_and_bar": list(self.player),
            "opponent_borne_off": self.borne_off[0],
            "player_borne_off": self.borne_off[1],
        }


@dataclass(frozen=True)
class SubMove:
    source: int
    destination: int
    die: int
    hit: bool


@dataclass(frozen=True)
class LegalMove:
    submoves: tuple[SubMove, ...]
    board: PositionBoard
    normalized_notation: str


def decode_position_id(position_id: str) -> PositionBoard:
    """Decode one canonical 14-character GNU Position ID fail-closed."""

    if (
        not isinstance(position_id, str)
        or len(position_id) != 14
        or any(character not in BASE64_ALPHABET for character in position_id)
    ):
        raise MovementPreparationError("source position is not a GNU Position ID")
    try:
        payload = base64.b64decode(position_id + "==", validate=True)
    except (ValueError, TypeError) as error:
        raise MovementPreparationError("source position is not canonical GNU base64") from error
    if len(payload) != 10:
        raise MovementPreparationError("source position decoded to an unexpected length")
    bits = [(byte >> bit) & 1 for byte in payload for bit in range(8)]
    players: list[tuple[int, ...]] = []
    cursor = 0
    for _ in range(2):
        counts: list[int] = []
        for _ in range(25):
            count = 0
            while cursor < 80 and bits[cursor] == 1:
                count += 1
                cursor += 1
            if cursor >= 80:
                raise MovementPreparationError("source Position ID ends before its separators")
            cursor += 1
            counts.append(count)
        players.append(tuple(counts))
    if any(bits[cursor:]):
        raise MovementPreparationError("source Position ID has trailing non-zero data")
    return PositionBoard((players[0], players[1]))


def encode_position_id(board: PositionBoard) -> str:
    """Encode a validated mover-relative board for deterministic test/oracle use."""

    bits: list[int] = []
    for player in board.players:
        for count in player:
            bits.extend([1] * count)
            bits.append(0)
    if len(bits) > 80:
        raise MovementPreparationError("board cannot fit in a GNU Position ID")
    bits.extend([0] * (80 - len(bits)))
    payload = bytes(
        sum(bits[byte_index * 8 + bit] << bit for bit in range(8))
        for byte_index in range(10)
    )
    return base64.b64encode(payload).decode("ascii").rstrip("=")[:14]


def normalize_notation(value: str) -> str:
    """Validate the bounded GNU point/bar/off/path/multiplier grammar."""

    if not isinstance(value, str) or not value.strip():
        raise MovementPreparationError("move notation is empty")
    tokens = value.replace(",", " ").split()
    normalized_tokens: list[str] = []
    expanded_steps = 0
    for token in tokens:
        match = MOVE_TOKEN_RE.fullmatch(token)
        if match is None:
            raise MovementPreparationError(f"unsupported move token: {token!r}")
        parts: list[str] = []
        for index, raw_part in enumerate(match.group("path").split("/")):
            hit = raw_part.endswith("*")
            raw_location = raw_part[:-1] if hit else raw_part
            lowered = raw_location.lower()
            if lowered in {"bar", "off"}:
                location = lowered
            else:
                point = int(raw_location)
                if point not in range(1, 25):
                    raise MovementPreparationError("move point is outside 1 through 24")
                location = str(point)
            if index == 0 and hit:
                raise MovementPreparationError("a source location cannot carry a hit marker")
            parts.append(location + ("*" if hit else ""))
        if parts[0] == "off" or any(part.rstrip("*") == "bar" for part in parts[1:]):
            raise MovementPreparationError("a move cannot start off or finish on the bar")
        count = int(match.group("count") or "1")
        expanded_steps += (len(parts) - 1) * count
        if expanded_steps > 4:
            raise MovementPreparationError("notation describes more than four checker steps")
        suffix = f"({count})" if count > 1 else ""
        normalized_tokens.append("/".join(parts) + suffix)
    return " ".join(normalized_tokens)


def _mutable(board: PositionBoard) -> list[list[int]]:
    return [list(board.opponent), list(board.player)]


def _freeze(board: list[list[int]]) -> PositionBoard:
    return PositionBoard((tuple(board[0]), tuple(board[1])))


def _legal_sources(board: list[list[int]], die: int) -> list[int]:
    ours, opponent = board[1], board[0]
    sources = [24] if ours[24] else [point for point in range(24) if ours[point]]
    highest = max((point for point in range(24) if ours[point]), default=-1)
    all_home = ours[24] == 0 and highest <= 5
    legal: list[int] = []
    for source in sources:
        destination = source - die
        if destination >= 0:
            if opponent[23 - destination] < 2:
                legal.append(source)
        elif all_home and (destination == -1 or source == highest):
            legal.append(source)
    return legal


def _apply_single(board: list[list[int]], source: int, die: int) -> tuple[list[list[int]], SubMove]:
    changed = [list(board[0]), list(board[1])]
    destination = source - die
    changed[1][source] -= 1
    hit = False
    if destination >= 0:
        opponent_index = 23 - destination
        if changed[0][opponent_index] == 1:
            changed[0][opponent_index] = 0
            changed[0][24] += 1
            hit = True
        changed[1][destination] += 1
    return changed, SubMove(source, destination, die, hit)


def _generate_for_order(
    board: PositionBoard, dice_order: tuple[int, ...]
) -> list[tuple[tuple[SubMove, ...], PositionBoard]]:
    results: list[tuple[tuple[SubMove, ...], PositionBoard]] = []

    def visit(current: list[list[int]], die_index: int, steps: tuple[SubMove, ...]) -> None:
        if die_index == len(dice_order):
            results.append((steps, _freeze(current)))
            return
        die = dice_order[die_index]
        sources = _legal_sources(current, die)
        if not sources:
            results.append((steps, _freeze(current)))
            return
        for source in sources:
            changed, step = _apply_single(current, source, die)
            visit(changed, die_index + 1, steps + (step,))

    visit(_mutable(board), 0, ())
    return results


def _point_name(point: int) -> str:
    if point == 25:
        return "bar"
    if point == 0:
        return "off"
    return str(point)


def _opponent_on_point(original: PositionBoard, point: int) -> bool:
    return 1 <= point <= 24 and original.opponent[24 - point] > 0


def _format_legal_move(original: PositionBoard, submoves: tuple[SubMove, ...]) -> str:
    paths = [
        [step.source + 1, max(step.destination + 1, 0)]
        for step in sorted(
            submoves, key=lambda item: (item.source, item.destination), reverse=True
        )
    ]
    active = [True] * len(paths)
    for left in range(len(paths)):
        if not active[left]:
            continue
        for right in range(left + 1, len(paths)):
            if active[right] and paths[left][-1] == paths[right][0]:
                intermediate = paths[left][-1]
                if _opponent_on_point(original, intermediate):
                    paths[left].append(paths[right][-1])
                else:
                    paths[left][-1] = paths[right][-1]
                active[right] = False
    compact = [tuple(path) for path, enabled in zip(paths, active) if enabled]
    grouped: list[tuple[tuple[int, ...], int]] = []
    for path in compact:
        for index, (existing, count) in enumerate(grouped):
            if existing == path:
                grouped[index] = (existing, count + 1)
                break
        else:
            grouped.append((path, 1))
    already_hit: set[int] = set()
    tokens: list[str] = []
    for path, count in grouped:
        pieces = [_point_name(path[0])]
        for intermediate in path[1:-1]:
            pieces.append(_point_name(intermediate) + "*")
            already_hit.add(intermediate)
        destination = path[-1]
        final = _point_name(destination)
        if _opponent_on_point(original, destination) and destination not in already_hit:
            final += "*"
            already_hit.add(destination)
        pieces.append(final)
        token = "/".join(pieces)
        if count > 1:
            token += f"({count})"
        tokens.append(token)
    return " ".join(tokens)


@lru_cache(maxsize=None)
def generate_legal_moves(board: PositionBoard, dice: tuple[int, int]) -> tuple[LegalMove, ...]:
    """Enumerate distinct legal resulting boards under standard checker rules."""

    if len(dice) != 2 or any(
        not isinstance(die, int) or isinstance(die, bool) or die not in range(1, 7)
        for die in dice
    ):
        raise MovementPreparationError("dice must contain two integers from 1 through 6")
    orders = [(dice[0],) * 4] if dice[0] == dice[1] else [dice, (dice[1], dice[0])]
    generated: list[tuple[tuple[SubMove, ...], PositionBoard]] = []
    for order in orders:
        generated.extend(_generate_for_order(board, order))
    maximum_steps = max((len(steps) for steps, _ in generated), default=0)
    generated = [(steps, result) for steps, result in generated if len(steps) == maximum_steps]
    if dice[0] != dice[1] and maximum_steps == 1:
        high = max(dice)
        if any(steps and steps[0].die == high for steps, _ in generated):
            generated = [
                (steps, result)
                for steps, result in generated
                if steps and steps[0].die == high
            ]
    distinct: dict[tuple[tuple[int, ...], tuple[int, ...]], LegalMove] = {}
    for steps, result in generated:
        notation = _format_legal_move(board, steps)
        existing = distinct.get(result.players)
        if existing is None or notation < existing.normalized_notation:
            distinct[result.players] = LegalMove(steps, result, notation)
    return tuple(
        sorted(
            distinct.values(),
            key=lambda item: (item.normalized_notation, item.board.players),
        )
    )


def prepare_movements(position_id: str, dice: tuple[int, int], notation: str) -> dict[str, Any]:
    """Return ordered atomic steps only for one unique legal notation match."""

    source = decode_position_id(position_id)
    normalized = normalize_notation(notation)
    matches = [
        move
        for move in generate_legal_moves(source, dice)
        if move.normalized_notation == normalized
    ]
    result_boards = {move.board.players for move in matches}
    if not matches:
        raise MovementPreparationError(
            "normalized notation does not match a legal play for the accepted position and dice"
        )
    if len(result_boards) != 1 or len(matches) != 1:
        raise MovementPreparationError(
            "normalized notation does not identify exactly one legal resulting board"
        )
    match = matches[0]
    steps = [
        {
            "order": order,
            "from": "bar" if step.source == 24 else step.source + 1,
            "to": "off" if step.destination < 0 else step.destination + 1,
            "die": step.die,
        }
        for order, step in enumerate(match.submoves, start=1)
    ]
    return {
        "preparer_version": PREPARER_VERSION,
        "source_reconstruction_version": SOURCE_RECONSTRUCTION_VERSION,
        "source_explainer_commit": SOURCE_EXPLAINER_COMMIT,
        "source_fact_kind": "accepted_normalized_gnu_candidate_notation",
        "normalized_notation": normalized,
        "legality_status": "unique_legal_play",
        "perspective": "decision_player_mover_relative",
        "source_board": source.receipt_value(),
        "result_board": match.board.receipt_value(),
        "movement_steps": steps,
    }
