"""
Unit tests for game/board.py and game/map_generator.py

Run with: python -m pytest tests/test_map.py -v
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.board import Board, DIFFICULTY_SETTINGS, WALL  # noqa: E402
from game.map_generator import (  # noqa: E402
    generate_random_map,
    get_challenge_level,
    CHALLENGE_LEVEL_NAMES,
)
from algorithms.greedy_best_first import greedy_best_first_search  # noqa: E402


def test_all_difficulties_produce_correct_size_and_are_solvable():
    for difficulty, settings in DIFFICULTY_SETTINGS.items():
        board = generate_random_map(difficulty, seed=7)
        assert board.width == settings["size"]
        assert board.height == settings["size"]
        assert board.is_solvable()


def test_generated_map_start_and_goal_are_never_walls():
    for difficulty in DIFFICULTY_SETTINGS:
        board = generate_random_map(difficulty, seed=123)
        assert not board.is_wall(board.start)
        assert not board.is_wall(board.goal)


def test_generated_map_is_actually_solvable_by_gbfs():
    """
    Cross-check: every map map_generator produces must be solvable
    not just by the internal BFS validator, but by the real GBFS
    solver used in the game.
    """
    for difficulty in DIFFICULTY_SETTINGS:
        board = generate_random_map(difficulty, seed=99)
        result = greedy_best_first_search(
            board.walkability_grid(), board.start, board.goal
        )
        assert result.found, f"{difficulty} map not solvable by GBFS"


def test_repeated_generation_is_always_solvable():
    for seed in range(20):
        board = generate_random_map("hard", seed=seed)
        assert board.is_solvable()


def test_all_six_challenge_levels_load_and_are_solvable():
    assert len(CHALLENGE_LEVEL_NAMES) == 6
    for level_id in range(1, 7):
        board = get_challenge_level(level_id)
        assert board.is_solvable()
        result = greedy_best_first_search(
            board.walkability_grid(), board.start, board.goal
        )
        assert result.found


def test_unknown_difficulty_raises():
    try:
        generate_random_map("nightmare")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_board_neighbors_respect_walls_and_bounds():
    board = Board.empty(3, 3, (0, 0), (2, 2))
    board.set_tile((1, 0), WALL)
    neighbors = board.neighbors((0, 0))
    assert (1, 0) not in neighbors  # blocked by wall
    assert (0, 1) in neighbors
    # out-of-bounds neighbors never appear
    for n in board.neighbors((0, 0)):
        assert board.in_bounds(n)
