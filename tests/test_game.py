"""
Unit tests for game/game_state.py

Run with: python -m pytest tests/test_game.py -v
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.board import Board, WALL, TRAP  # noqa: E402
from game.game_state import GameState  # noqa: E402


def make_simple_board():
    # 3x3 open board, start top-left, goal bottom-right
    board = Board.empty(3, 3, (0, 0), (2, 2))
    return board


def test_new_game_starts_at_start_position():
    state = GameState.new(make_simple_board(), "easy")
    assert state.player_pos == (0, 0)
    assert state.moves == 0
    assert not state.finished


def test_valid_move_updates_position_and_move_count():
    state = GameState.new(make_simple_board(), "easy")
    result = state.move("right")
    assert result["success"] is True
    assert state.player_pos == (1, 0)
    assert state.moves == 1


def test_move_into_wall_is_rejected():
    board = make_simple_board()
    board.set_tile((1, 0), WALL)
    state = GameState.new(board, "easy")
    result = state.move("right")
    assert result["success"] is False
    assert result["reason"] == "blocked_by_wall"
    assert state.player_pos == (0, 0)  # unchanged
    assert state.moves == 0


def test_move_out_of_bounds_is_rejected():
    state = GameState.new(make_simple_board(), "easy")
    result = state.move("up")  # already at y=0
    assert result["success"] is False
    assert result["reason"] == "out_of_bounds"


def test_reaching_goal_finishes_game():
    board = Board.empty(2, 1, (0, 0), (1, 0))
    state = GameState.new(board, "easy")
    result = state.move("right")
    assert result["reached_goal"] is True
    assert state.finished is True


def test_moving_after_finish_is_rejected():
    board = Board.empty(2, 1, (0, 0), (1, 0))
    state = GameState.new(board, "easy")
    state.move("right")
    result = state.move("left")
    assert result["success"] is False
    assert result["reason"] == "game_already_finished"


def test_trap_is_tracked_and_reduces_score():
    board = Board.empty(3, 1, (0, 0), (2, 0))
    board.set_tile((1, 0), TRAP)
    state = GameState.new(board, "easy")
    baseline_state = GameState.new(board, "easy")

    result = state.move("right")  # steps on trap
    assert result["hit_trap"] is True
    assert state.traps_hit == 1

    baseline_state.moves = state.moves  # equalize moves for fair comparison
    assert state.compute_score() <= baseline_state.compute_score()


def test_score_never_goes_negative():
    state = GameState.new(make_simple_board(), "easy")
    state.moves = 100000
    assert state.compute_score() == 0


def test_invalid_direction_rejected_without_crashing():
    state = GameState.new(make_simple_board(), "easy")
    result = state.move("diagonal")
    assert result["success"] is False
    assert result["reason"] == "invalid_direction"


def test_serialization_round_trip():
    state = GameState.new(make_simple_board(), "medium")
    state.move("right")
    data = state.to_dict()
    restored = GameState.from_dict(data)
    assert restored.player_pos == state.player_pos
    assert restored.moves == state.moves
    assert restored.difficulty == state.difficulty
