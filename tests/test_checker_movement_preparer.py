from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.analysis import checker_movement_preparer as preparer


def board(
    player_points: dict[int, int] | None = None,
    opponent_on_mover_points: dict[int, int] | None = None,
    *,
    player_bar: int = 0,
    opponent_bar: int = 0,
) -> preparer.PositionBoard:
    player = [0] * 25
    opponent = [0] * 25
    for point, count in (player_points or {}).items():
        player[point - 1] = count
    for mover_point, count in (opponent_on_mover_points or {}).items():
        opponent[24 - mover_point] = count
    player[24] = player_bar
    opponent[24] = opponent_bar
    return preparer.PositionBoard((tuple(opponent), tuple(player)))


def prepare(position: preparer.PositionBoard, dice: tuple[int, int], notation: str):
    position_id = preparer.encode_position_id(position)
    return preparer.prepare_movements(position_id, dice, notation)


class CheckerMovementPreparerTests(unittest.TestCase):
    def test_ordinary_two_checker_and_one_checker_two_step(self) -> None:
        ordinary = prepare(board({13: 1, 6: 1}), (5, 1), "13/8 6/5")
        self.assertEqual(
            ordinary["movement_steps"],
            [
                {"order": 1, "from": 13, "to": 8, "die": 5},
                {"order": 2, "from": 6, "to": 5, "die": 1},
            ],
        )
        chained = prepare(board({13: 1}), (5, 1), "13/7")
        self.assertEqual(
            chained["movement_steps"],
            [
                {"order": 1, "from": 13, "to": 8, "die": 5},
                {"order": 2, "from": 8, "to": 7, "die": 1},
            ],
        )

    def test_doubles_expand_to_four_ordered_atomic_steps(self) -> None:
        result = prepare(board({13: 4}), (3, 3), "13/10(4)")
        self.assertEqual(len(result["movement_steps"]), 4)
        self.assertEqual(
            [(step["from"], step["to"], step["die"]) for step in result["movement_steps"]],
            [(13, 10, 3)] * 4,
        )

    def test_hit_marker_resolves_hit_then_subsequent_board_movement(self) -> None:
        result = prepare(board({13: 1}, {8: 1}), (5, 1), "13/8*/7")
        self.assertEqual(
            result["movement_steps"],
            [
                {"order": 1, "from": 13, "to": 8, "die": 5},
                {"order": 2, "from": 8, "to": 7, "die": 1},
            ],
        )
        self.assertEqual(
            result["result_board"]["opponent_points_1_to_24_and_bar"][-1], 1
        )

    def test_bar_entry_bar_plus_board_and_stacked_outcome(self) -> None:
        bar_board = prepare(
            board({6: 1}, player_bar=1), (1, 2), "bar/24 6/4"
        )
        self.assertEqual(bar_board["movement_steps"][0]["from"], "bar")
        self.assertEqual(bar_board["movement_steps"][1]["from"], 6)

        chained = prepare(board(player_bar=1), (1, 2), "bar/22")
        self.assertEqual(
            chained["movement_steps"],
            [
                {"order": 1, "from": "bar", "to": 24, "die": 1},
                {"order": 2, "from": 24, "to": 22, "die": 2},
            ],
        )

        stacked = prepare(board({8: 1, 6: 1}), (4, 2), "8/4 6/4")
        self.assertEqual(stacked["result_board"]["player_points_1_to_24_and_bar"][3], 2)

    def test_bearoff_uses_legal_dice_and_preserves_borne_off_count(self) -> None:
        result = prepare(board({6: 1}), (6, 1), "6/off")
        self.assertEqual(result["movement_steps"][-1]["to"], "off")
        self.assertEqual(result["result_board"]["player_borne_off"], 15)

    def test_grammar_normalization_is_bounded_and_deterministic(self) -> None:
        self.assertEqual(
            preparer.normalize_notation(" BAR/23,  6/OFF "), "bar/23 6/off"
        )
        for notation in ("13//9", "off/1", "13/bar", "25/20", "13/8(5)"):
            with self.subTest(notation=notation), self.assertRaises(
                preparer.MovementPreparationError
            ):
                preparer.normalize_notation(notation)
        position = board({13: 1, 6: 1})
        first = prepare(position, (5, 1), "13/8 6/5")
        preparer.generate_legal_moves.cache_clear()
        second = prepare(position, (5, 1), "13/8 6/5")
        self.assertEqual(first, second)

    def test_illegal_and_ambiguous_notation_fail_closed(self) -> None:
        position = board({13: 1})
        with self.assertRaisesRegex(
            preparer.MovementPreparationError, "does not match a legal play"
        ):
            prepare(position, (5, 1), "13/8")

        original = preparer.generate_legal_moves(position, (5, 1))[0]
        other_board = board({12: 1})
        ambiguous = (
            preparer.LegalMove(original.submoves, original.board, "13/7"),
            preparer.LegalMove(original.submoves, other_board, "13/7"),
        )
        with patch.object(preparer, "generate_legal_moves", return_value=ambiguous):
            with self.assertRaisesRegex(
                preparer.MovementPreparationError, "exactly one legal resulting board"
            ):
                prepare(position, (5, 1), "13/7")


if __name__ == "__main__":
    unittest.main()
