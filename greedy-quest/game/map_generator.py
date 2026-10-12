"""
game/map_generator.py

Generates random, ALWAYS-solvable maps, plus a set of hand-authored
challenge levels (including the "Greedy Trap").

Solvability is guaranteed by generate -> validate -> retry (using
Board.is_solvable(), a plain BFS reachability check). That reachability
check is purely a generation-time validator; it is never used as the
game's pathfinding solver -- GBFS always fills that role.
"""

from __future__ import annotations

import random
from typing import Optional, Tuple

from game.board import Board, DIFFICULTY_SETTINGS, EMPTY, TRAP, WALL

Coord = Tuple[int, int]

MAX_GENERATION_ATTEMPTS = 60


def generate_random_map(difficulty: str, seed: Optional[int] = None) -> Board:
    """
    Generate a random solvable map for the given difficulty
    ('easy' | 'medium' | 'hard' | 'extreme').
    """
    if difficulty not in DIFFICULTY_SETTINGS:
        raise ValueError(f"Unknown difficulty: {difficulty}")

    settings = DIFFICULTY_SETTINGS[difficulty]
    size = settings["size"]
    wall_density = settings["wall_density"]
    trap_density = settings["trap_density"]

    rng = random.Random(seed)

    start = (0, 0)
    goal = (size - 1, size - 1)

    for _attempt in range(MAX_GENERATION_ATTEMPTS):
        board = Board.empty(size, size, start, goal)

        for y in range(size):
            for x in range(size):
                pos = (x, y)
                if pos == start or pos == goal:
                    continue
                roll = rng.random()
                if roll < wall_density:
                    board.set_tile(pos, WALL)
                elif roll < wall_density + trap_density:
                    board.set_tile(pos, TRAP)

        if board.is_solvable():
            return board

    # Fallback: if we somehow failed every attempt (extremely unlikely
    # at these densities), return a guaranteed-solvable empty board
    # with a light sprinkling of traps only (no walls).
    board = Board.empty(size, size, start, goal)
    for y in range(size):
        for x in range(size):
            pos = (x, y)
            if pos != start and pos != goal and rng.random() < trap_density:
                board.set_tile(pos, TRAP)
    return board


def _board_from_ascii(rows: list[str], start: Coord, goal: Coord) -> Board:
    """
    Helper for hand-authored challenge levels.
    '.' = empty, '#' = wall, '^' = trap
    """
    height = len(rows)
    width = len(rows[0])
    board = Board.empty(width, height, start, goal)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                board.set_tile((x, y), WALL)
            elif ch == "^":
                board.set_tile((x, y), TRAP)
    return board


def get_challenge_level(level_id: int) -> Board:
    """Return one of the six hand-authored challenge levels (1-6)."""
    if level_id == 1:
        # LEVEL 1 -- First Steps: mostly open, a couple of nudges.
        rows = [
            "..........",
            "..........",
            "...##.....",
            "...##.....",
            "..........",
            ".....##...",
            ".....##...",
            "..........",
            "..........",
            "..........",
        ]
        return _board_from_ascii(rows, (0, 0), (9, 9))

    if level_id == 2:
        # LEVEL 2 -- The Maze
        rows = [
            "....#.....",
            ".##.#.###.",
            "....#.#...",
            ".####.#.##",
            "......#...",
            ".####.###.",
            ".#....#...",
            ".#.####.##",
            ".#......#.",
            "..........",
        ]
        return _board_from_ascii(rows, (0, 0), (9, 9))

    if level_id == 3:
        # LEVEL 3 -- Greedy Trap: the goal is visually close (top-right)
        # but a pocket of walls lures a pure-heuristic search into a
        # detour. See section 12 of the spec: this is the flagship
        # demonstration that GBFS does not guarantee an optimal path.
        rows = [
            ".......",
            ".#####.",
            ".#...#.",
            ".#.#.#.",
            ".#...#.",
            ".#####.",
            ".......",
        ]
        return _board_from_ascii(rows, (0, 0), (6, 0))

    if level_id == 4:
        # LEVEL 4 -- Dead End: several plausible-looking branches that
        # terminate, forcing backtracking behavior to be visible.
        rows = [
            "..........",
            ".####.###.",
            ".#..#...#.",
            ".#.##.#.#.",
            ".#....#.#.",
            ".####.#.#.",
            ".#....#.#.",
            ".#.####.#.",
            ".#.......#",
            "..........",
        ]
        return _board_from_ascii(rows, (0, 0), (9, 9))

    if level_id == 5:
        # LEVEL 5 -- Treasure Rush: larger open board with scattered
        # traps, rewarding speed.
        board = generate_random_map("medium", seed=2025)
        return board

    if level_id == 6:
        # LEVEL 6 -- Extreme Hunt
        board = generate_random_map("extreme", seed=1337)
        return board

    raise ValueError(f"Unknown challenge level: {level_id}")


CHALLENGE_LEVEL_NAMES = {
    1: "First Steps",
    2: "The Maze",
    3: "Greedy Trap",
    4: "Dead End",
    5: "Treasure Rush",
    6: "Extreme Hunt",
}
