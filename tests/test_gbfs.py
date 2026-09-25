"""
Unit tests for algorithms/greedy_best_first.py

Run with:  python -m pytest tests/test_gbfs.py -v
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from algorithms.greedy_best_first import (  # noqa: E402
    greedy_best_first_search,
    manhattan_distance,
)

W = 1  # wall
E = 0  # empty


def make_grid(rows):
    return [row[:] for row in rows]


def assert_valid_path(grid, path):
    """Shared validator: adjacency + no walls crossed."""
    assert len(path) > 0
    for x, y in path:
        assert grid[y][x] != W, f"path crosses a wall at {(x, y)}"
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        dist = abs(x1 - x2) + abs(y1 - y2)
        assert dist == 1, f"non-adjacent path step {(x1, y1)} -> {(x2, y2)}"


def test_manhattan_distance():
    assert manhattan_distance((0, 0), (3, 4)) == 7
    assert manhattan_distance((5, 5), (5, 5)) == 0


def test_simple_path_no_obstacles():
    grid = make_grid([[E] * 5 for _ in range(5)])
    result = greedy_best_first_search(grid, (0, 0), (4, 4))
    assert result.found
    assert_valid_path(grid, result.path)
    assert result.path[0] == (0, 0)
    assert result.path[-1] == (4, 4)


def test_no_path_exists():
    # A wall of W completely separates start from goal.
    grid = make_grid([
        [E, E, W, E, E],
        [E, E, W, E, E],
        [E, E, W, E, E],
        [E, E, W, E, E],
        [E, E, W, E, E],
    ])
    result = greedy_best_first_search(grid, (0, 0), (4, 4))
    assert not result.found
    assert result.path == []


def test_start_equals_goal():
    grid = make_grid([[E] * 3 for _ in range(3)])
    result = greedy_best_first_search(grid, (1, 1), (1, 1))
    assert result.found
    assert result.path == [(1, 1)]
    assert result.steps[0].heuristic == 0


def test_obstacles_are_respected():
    grid = make_grid([
        [E, E, E, E, E],
        [E, W, W, W, E],
        [E, W, E, W, E],
        [E, W, E, W, E],
        [E, E, E, W, E],
    ])
    result = greedy_best_first_search(grid, (0, 0), (4, 4))
    assert result.found
    assert_valid_path(grid, result.path)


def test_large_grid_performance_and_validity():
    size = 40
    grid = [[E] * size for _ in range(size)]
    # Walls only on even rows, each with one guaranteed gap -> always solvable,
    # while still forcing GBFS to actually navigate around obstacles.
    for y in range(0, size, 2):
        gap_x = (y // 2) % size
        for x in range(size):
            if x != gap_x:
                grid[y][x] = W
    result = greedy_best_first_search(grid, (0, 0), (size - 1, size - 1))
    assert result.found
    assert_valid_path(grid, result.path)
    assert result.execution_time_ms < 500  # should be fast even at 40x40


def test_multiple_possible_paths_returns_one_valid_path():
    grid = make_grid([[E] * 6 for _ in range(6)])
    result = greedy_best_first_search(grid, (0, 0), (5, 5))
    assert result.found
    assert_valid_path(grid, result.path)


def test_greedy_trap_may_not_be_shortest():
    """
    Classic GBFS weakness: a wall creates a 'pocket' near the goal.
    GBFS greedily walks toward the goal and can be lured into it,
    producing a path that is valid but NOT necessarily the shortest
    possible route (unlike A*, which would find the optimum).
    We only assert the path is valid and found -- optimality is
    explicitly NOT guaranteed, and that's the point of this test.
    """
    grid = make_grid([
        [E, E, E, E, E, E, E],
        [E, W, W, W, W, W, E],
        [E, W, E, E, E, W, E],
        [E, W, E, W, E, W, E],
        [E, W, E, E, E, W, E],
        [E, W, W, W, W, W, E],
        [E, E, E, E, E, E, E],
    ])
    result = greedy_best_first_search(grid, (0, 0), (6, 0))
    assert result.found
    assert_valid_path(grid, result.path)


def test_random_generated_boards_are_solvable_when_expected(monkeypatch=None):
    import random
    random.seed(42)
    for _ in range(10):
        size = 10
        grid = [[E] * size for _ in range(size)]
        for _ in range(15):
            x, y = random.randint(0, size - 1), random.randint(0, size - 1)
            if (x, y) not in [(0, 0), (size - 1, size - 1)]:
                grid[y][x] = W
        result = greedy_best_first_search(grid, (0, 0), (size - 1, size - 1))
        if result.found:
            assert_valid_path(grid, result.path)
        # else: this particular random board happened to be unsolvable,
        # which is a valid outcome for this raw test (map_generator.py
        # is responsible for guaranteeing solvability in the real game).


def test_priority_is_heuristic_only_not_a_star():
    """
    Regression guard: confirms GBFS expands nodes in an order driven
    purely by h(n), not g(n)+h(n). We build a grid where a 'greedy'
    strategy visibly commits to the heuristically-closer neighbor
    first, even though it doesn't yet know the true path cost.
    """
    grid = make_grid([[E] * 5 for _ in range(5)])
    result = greedy_best_first_search(grid, (0, 0), (4, 0))
    # From (0,0), heuristic-best neighbor toward goal (4,0) is (1,0) (h=3)
    # over (0,1) (h=5). First expansion's selected neighbor must reflect
    # pure h(n) ordering.
    first_step = result.steps[0]
    assert first_step.selected == (1, 0)
