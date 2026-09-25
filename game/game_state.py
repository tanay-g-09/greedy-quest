"""
game/game_state.py

Tracks one active game session: the current board, player position,
move count, elapsed time, and score. This is intentionally simple and
serializable so it can live in Flask's server-side session store
(see app.py) -- no database required (per spec section 29).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

from game.board import Board, TRAP

Coord = Tuple[int, int]

MOVE_DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    # WASD aliases handled at the API layer
}

TRAP_PENALTY = 25          # points lost per trap stepped on
BASE_SCORE = 1000
POINTS_PER_MOVE = 4        # deducted per move taken
POINTS_PER_SECOND = 2      # deducted per second elapsed


@dataclass
class GameState:
    board: Board
    difficulty: str
    player_pos: Coord
    moves: int = 0
    traps_hit: int = 0
    started_at: float = field(default_factory=time.time)
    finished: bool = False
    finished_at: Optional[float] = None

    @classmethod
    def new(cls, board: Board, difficulty: str) -> "GameState":
        return cls(board=board, difficulty=difficulty, player_pos=board.start)

    def elapsed_seconds(self) -> float:
        end = self.finished_at if self.finished else time.time()
        return max(0.0, end - self.started_at)

    def distance_to_goal(self) -> int:
        gx, gy = self.board.goal
        px, py = self.player_pos
        return abs(px - gx) + abs(py - gy)

    def move(self, direction: str) -> dict:
        """
        Attempt to move the player one cell. Returns a result dict;
        never raises on an invalid move (walls / out of bounds / already
        finished) -- it just reports that the move was rejected, since
        client coordinates/input must never be trusted blindly.
        """
        if self.finished:
            return {"success": False, "reason": "game_already_finished"}

        direction = direction.lower()
        if direction not in MOVE_DELTAS:
            return {"success": False, "reason": "invalid_direction"}

        dx, dy = MOVE_DELTAS[direction]
        px, py = self.player_pos
        new_pos = (px + dx, py + dy)

        if not self.board.in_bounds(new_pos):
            return {"success": False, "reason": "out_of_bounds"}
        if self.board.is_wall(new_pos):
            return {"success": False, "reason": "blocked_by_wall"}

        self.player_pos = new_pos
        self.moves += 1

        hit_trap = False
        if self.board.is_trap(new_pos):
            hit_trap = True
            self.traps_hit += 1

        reached_goal = new_pos == self.board.goal
        if reached_goal:
            self.finished = True
            self.finished_at = time.time()

        return {
            "success": True,
            "position": list(new_pos),
            "hit_trap": hit_trap,
            "reached_goal": reached_goal,
            "moves": self.moves,
            "distance_to_goal": self.distance_to_goal(),
        }

    def compute_score(self) -> int:
        """
        Simple, explainable scoring formula (spec section 20):
        start from a base, subtract for moves/time/traps taken, floor at 0.
        This is a heuristic scoring convenience for the player, NOT
        something the AI is compared against -- the AI is scored purely
        on search statistics (nodes explored, path length, time).
        """
        score = BASE_SCORE
        score -= self.moves * POINTS_PER_MOVE
        score -= int(self.elapsed_seconds()) * POINTS_PER_SECOND
        score -= self.traps_hit * TRAP_PENALTY
        return max(0, score)

    def to_dict(self) -> dict:
        return {
            "board": self.board.to_dict(),
            "difficulty": self.difficulty,
            "player_pos": list(self.player_pos),
            "moves": self.moves,
            "traps_hit": self.traps_hit,
            "finished": self.finished,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": round(self.elapsed_seconds(), 1),
            "distance_to_goal": self.distance_to_goal(),
            "score": self.compute_score(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        state = cls(
            board=Board.from_dict(data["board"]),
            difficulty=data["difficulty"],
            player_pos=tuple(data["player_pos"]),
            moves=data["moves"],
            traps_hit=data["traps_hit"],
            finished=data["finished"],
        )
        # started_at/finished_at aren't perfectly round-tripped through
        # elapsed_seconds alone, so we store them explicitly too.
        state.started_at = data.get("started_at", state.started_at)
        state.finished_at = data.get("finished_at")
        return state
