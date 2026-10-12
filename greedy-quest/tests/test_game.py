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


# ---------------------------------------------------------------------
# Pause / resume
#
# These use a fake clock so they are deterministic and instant. Note that
# GameState.started_at's default factory captured the real time.time at
# import, so each test sets started_at explicitly from the fake clock.
# ---------------------------------------------------------------------

import game.game_state as game_state_module  # noqa: E402


def make_timed_state(monkeypatch, start_time=1000.0):
    clock = [start_time]
    monkeypatch.setattr(game_state_module.time, "time", lambda: clock[0])
    state = GameState.new(Board.empty(5, 5, (0, 0), (4, 4)), "easy")
    state.started_at = clock[0]
    return state, clock


def test_pause_freezes_elapsed_time(monkeypatch):
    state, clock = make_timed_state(monkeypatch)
    clock[0] = 1010.0
    assert state.elapsed_seconds() == 10.0

    assert state.pause() is True
    clock[0] = 1500.0  # a long time passes while paused
    assert state.elapsed_seconds() == 10.0


def test_resume_excludes_paused_time(monkeypatch):
    state, clock = make_timed_state(monkeypatch)
    clock[0] = 1010.0
    state.pause()
    clock[0] = 1500.0
    assert state.resume() is True
    assert state.elapsed_seconds() == 10.0  # right after resume, still 10s
    clock[0] = 1505.0
    assert state.elapsed_seconds() == 15.0  # only 5 more real seconds counted


def test_multiple_pauses_accumulate_correctly(monkeypatch):
    state, clock = make_timed_state(monkeypatch)
    clock[0] = 1004.0; state.pause()      # played 4s
    clock[0] = 1100.0; state.resume()     # paused 96s
    clock[0] = 1106.0; state.pause()      # played 6 more (10 total)
    clock[0] = 9999.0; state.resume()     # paused a very long time
    clock[0] = 10001.0
    assert state.elapsed_seconds() == 12.0


def test_score_does_not_decay_while_paused(monkeypatch):
    state, clock = make_timed_state(monkeypatch)
    clock[0] = 1010.0
    state.pause()
    score_at_pause = state.compute_score()
    clock[0] = 5000.0
    assert state.compute_score() == score_at_pause


def test_moves_rejected_while_paused_then_allowed_after_resume(monkeypatch):
    state, _clock = make_timed_state(monkeypatch)
    state.pause()
    result = state.move("right")
    assert result["success"] is False
    assert result["reason"] == "game_paused"
    assert state.player_pos == (0, 0)
    assert state.moves == 0

    state.resume()
    assert state.move("right")["success"] is True
    assert state.player_pos == (1, 0)


def test_pause_and_resume_are_idempotent(monkeypatch):
    state, _clock = make_timed_state(monkeypatch)
    assert state.resume() is False        # not paused yet
    assert state.pause() is True
    assert state.pause() is False         # already paused
    assert state.paused is True
    assert state.resume() is True
    assert state.resume() is False
    assert state.paused is False


def test_cannot_pause_a_finished_game(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(game_state_module.time, "time", lambda: clock[0])
    state = GameState.new(Board.empty(2, 1, (0, 0), (1, 0)), "easy")
    state.started_at = 1000.0
    clock[0] = 1007.0
    state.move("right")  # reaches goal, finishes at t=1007
    assert state.finished is True

    assert state.pause() is False
    assert state.paused is False
    clock[0] = 2000.0
    assert state.elapsed_seconds() == 7.0  # finish time is untouched


def test_paused_state_survives_serialization_round_trip(monkeypatch):
    state, clock = make_timed_state(monkeypatch)
    clock[0] = 1010.0
    state.pause()
    restored = GameState.from_dict(state.to_dict())
    assert restored.paused is True
    assert restored.paused_at == state.paused_at
    clock[0] = 3000.0
    assert restored.elapsed_seconds() == 10.0
