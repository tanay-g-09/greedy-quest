"""
game/board.py

The Board is the core grid data model shared by:
- map generation
- the GBFS solver (via a plain 2D walkability grid)
- the Flask API (serialized to/from JSON)

Tile values are small ints so the board serializes compactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Coord = Tuple[int, int]

# --- Tile type constants -----------------------------------------------
EMPTY = 0
WALL = 1
TRAP = 2
START = 3
GOAL = 4

TILE_NAMES = {
    EMPTY: "empty",
    WALL: "wall",
    TRAP: "trap",
    START: "start",
    GOAL: "goal",
}

DIFFICULTY_SETTINGS = {
    "easy": {"size": 10, "wall_density": 0.12, "trap_density": 0.03},
    "medium": {"size": 20, "wall_density": 0.18, "trap_density": 0.05},
    "hard": {"size": 30, "wall_density": 0.24, "trap_density": 0.06},
    "extreme": {"size": 40, "wall_density": 0.28, "trap_density": 0.08},
}


@dataclass
class Board:
    width: int
    height: int
    # tiles[y][x] -- terrain only (EMPTY / WALL / TRAP). start/goal are
    # tracked separately so a trap or wall can never accidentally sit
    # under the player's start or goal tile.
    tiles: List[List[int]] = field(default_factory=list)
    start: Coord = (0, 0)
    goal: Coord = (0, 0)

    @classmethod
    def empty(cls, width: int, height: int, start: Coord, goal: Coord) -> "Board":
        tiles = [[EMPTY for _ in range(width)] for _ in range(height)]
        return cls(width=width, height=height, tiles=tiles, start=start, goal=goal)

    def in_bounds(self, pos: Coord) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, pos: Coord) -> int:
        x, y = pos
        return self.tiles[y][x]

    def set_tile(self, pos: Coord, value: int) -> None:
        x, y = pos
        self.tiles[y][x] = value

    def is_wall(self, pos: Coord) -> bool:
        return self.in_bounds(pos) and self.tile_at(pos) == WALL

    def is_trap(self, pos: Coord) -> bool:
        return self.in_bounds(pos) and self.tile_at(pos) == TRAP

    def is_walkable(self, pos: Coord) -> bool:
        """Walls block movement. Traps, start and goal are walkable."""
        return self.in_bounds(pos) and self.tile_at(pos) != WALL

    def neighbors(self, pos: Coord) -> List[Coord]:
        x, y = pos
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in candidates if self.is_walkable(c)]

    def walkability_grid(self) -> List[List[int]]:
        """
        Returns a plain grid where 0 = walkable, 1 = wall, suitable for
        feeding directly into algorithms.greedy_best_first_search.
        Traps are intentionally walkable here -- they're a gameplay
        penalty, not a search obstacle.
        """
        return [
            [WALL if self.tiles[y][x] == WALL else EMPTY for x in range(self.width)]
            for y in range(self.height)
        ]

    def is_solvable(self) -> bool:
        """
        Internal-only reachability check used purely to validate a
        freshly generated map. This is NOT the algorithm used to solve
        the game for the player -- GBFS (algorithms/greedy_best_first.py)
        is always the actual solver exposed via the API.
        """
        from collections import deque

        if not self.is_walkable(self.start) or not self.is_walkable(self.goal):
            return False

        visited = {self.start}
        queue = deque([self.start])
        while queue:
            current = queue.popleft()
            if current == self.goal:
                return True
            for n in self.neighbors(current):
                if n not in visited:
                    visited.add(n)
                    queue.append(n)
        return False

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "tiles": self.tiles,
            "start": list(self.start),
            "goal": list(self.goal),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        return cls(
            width=data["width"],
            height=data["height"],
            tiles=data["tiles"],
            start=tuple(data["start"]),
            goal=tuple(data["goal"]),
        )
