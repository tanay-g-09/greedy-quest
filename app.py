"""
app.py

GREEDY QUEST -- Flask backend.

State model: fully stateless across requests, which matters for
serverless hosting (e.g. Vercel), where successive requests from the
same browser are not guaranteed to land on the same process. Instead
of holding GameState objects in server memory, each session cookie
holds a small JSON descriptor:

    {difficulty, level_id, seed, player_pos, moves, traps_hit,
     started_at, finished, finished_at, solved}

The board itself is never stored anywhere -- it is regenerated
deterministically on every request from (difficulty, seed) via
generate_random_map(), or from level_id via get_challenge_level().
Both are pure functions of their inputs, so the regenerated board is
always byte-for-byte identical to the one the player started on. This
keeps the cookie tiny (well under the 4KB limit) regardless of board
size, and means any process, anywhere, can serve any request for a
session with no shared memory or external database required.

Every endpoint validates its own input and never trusts client-supplied
coordinates blindly (spec section 33).
"""

from __future__ import annotations

import os
import random
from typing import Optional

from flask import Flask, jsonify, render_template, request, session

from algorithms.greedy_best_first import greedy_best_first_search
from game.board import DIFFICULTY_SETTINGS, Board
from game.game_state import GameState
from game.map_generator import (
    CHALLENGE_LEVEL_NAMES,
    generate_random_map,
    get_challenge_level,
)

app = Flask(__name__)
app.secret_key = os.environ.get("GREEDY_QUEST_SECRET_KEY", "dev-secret-change-me")

SESSION_KEY = "game"

DIRECTION_ALIASES = {
    "up": "up", "w": "up", "arrowup": "up",
    "down": "down", "s": "down", "arrowdown": "down",
    "left": "left", "a": "left", "arrowleft": "left",
    "right": "right", "d": "right", "arrowright": "right",
}


# --------------------------------------------------------------------
# Helpers: descriptor <-> board/state reconstruction
# --------------------------------------------------------------------

def _build_board(descriptor: dict) -> Board:
    """Deterministically regenerate the board from the tiny descriptor."""
    if descriptor.get("level_id") is not None:
        return get_challenge_level(descriptor["level_id"])
    return generate_random_map(descriptor["difficulty"], seed=descriptor["seed"])


def _build_state(descriptor: dict) -> GameState:
    board = _build_board(descriptor)
    state = GameState(
        board=board,
        difficulty=descriptor["difficulty"],
        player_pos=tuple(descriptor["player_pos"]),
        moves=descriptor["moves"],
        traps_hit=descriptor["traps_hit"],
        finished=descriptor["finished"],
    )
    state.started_at = descriptor["started_at"]
    state.finished_at = descriptor["finished_at"]
    return state


def _save_descriptor(state: GameState, difficulty, level_id, seed, solved: bool) -> None:
    session[SESSION_KEY] = {
        "difficulty": difficulty,
        "level_id": level_id,
        "seed": seed,
        "player_pos": list(state.player_pos),
        "moves": state.moves,
        "traps_hit": state.traps_hit,
        "started_at": state.started_at,
        "finished": state.finished,
        "finished_at": state.finished_at,
        "solved": solved,
    }


def _get_descriptor() -> Optional[dict]:
    return session.get(SESSION_KEY)


def _require_descriptor():
    descriptor = _get_descriptor()
    if descriptor is None:
        return None, (jsonify({
            "error": "no_active_game",
            "message": "No active game for this session. Call /api/game/new first.",
        }), 404)
    return descriptor, None


def _error(message: str, status: int = 400):
    return jsonify({"error": "bad_request", "message": message}), status


# --------------------------------------------------------------------
# Page routes
# --------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/game")
def game_page():
    return render_template("game.html")


@app.route("/algorithm")
def algorithm_page():
    return render_template("algorithm.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


# --------------------------------------------------------------------
# API: game lifecycle
# --------------------------------------------------------------------

@app.route("/api/game/new", methods=["POST"])
def api_game_new():
    payload = request.get_json(silent=True) or {}
    difficulty = payload.get("difficulty", "easy")
    level_id = payload.get("level_id")
    seed = payload.get("seed")

    if level_id is not None:
        try:
            level_id = int(level_id)
        except (TypeError, ValueError):
            return _error("level_id must be an integer")
        if level_id not in CHALLENGE_LEVEL_NAMES:
            return _error(f"level_id must be one of {sorted(CHALLENGE_LEVEL_NAMES)}")
        board = get_challenge_level(level_id)
        difficulty = "challenge"
        seed_val = None
    else:
        if difficulty not in DIFFICULTY_SETTINGS:
            return _error(f"difficulty must be one of {sorted(DIFFICULTY_SETTINGS)}")
        if seed is not None:
            try:
                seed_val = int(seed)
            except (TypeError, ValueError):
                return _error("seed must be an integer")
        else:
            # Always pin a concrete seed so the board can be deterministically
            # regenerated on every future request -- this is what lets the
            # session stay stateless (see module docstring).
            seed_val = random.randint(0, 2**31 - 1)
        board = generate_random_map(difficulty, seed=seed_val)

    state = GameState.new(board, difficulty)
    _save_descriptor(state, difficulty, level_id, seed_val, solved=False)

    response = state.to_dict()
    if level_id is not None:
        response["level_id"] = level_id
        response["level_name"] = CHALLENGE_LEVEL_NAMES[level_id]
    return jsonify(response)


@app.route("/api/game/state", methods=["GET"])
def api_game_state():
    descriptor, err = _require_descriptor()
    if err:
        return err
    state = _build_state(descriptor)
    return jsonify(state.to_dict())


@app.route("/api/game/move", methods=["POST"])
def api_game_move():
    descriptor, err = _require_descriptor()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    raw_direction = str(payload.get("direction", "")).lower()
    direction = DIRECTION_ALIASES.get(raw_direction)
    if direction is None:
        return _error(f"direction must be one of {sorted(set(DIRECTION_ALIASES))}")

    state = _build_state(descriptor)
    result = state.move(direction)
    _save_descriptor(
        state, descriptor["difficulty"], descriptor["level_id"], descriptor["seed"],
        solved=descriptor["solved"],
    )
    result["state"] = state.to_dict()
    return jsonify(result)


@app.route("/api/game/reset", methods=["POST"])
def api_game_reset():
    """Reset the player back to start on the SAME board (same map, fresh attempt)."""
    descriptor, err = _require_descriptor()
    if err:
        return err
    board = _build_board(descriptor)
    new_state = GameState.new(board, descriptor["difficulty"])
    _save_descriptor(
        new_state, descriptor["difficulty"], descriptor["level_id"], descriptor["seed"],
        solved=False,
    )
    return jsonify(new_state.to_dict())


# --------------------------------------------------------------------
# API: AI (GBFS)
# --------------------------------------------------------------------

@app.route("/api/ai/solve", methods=["POST"])
def api_ai_solve():
    """
    Runs the real GBFS solver on the current board and returns the full
    step-by-step trace (for 'Watch AI Think' replay) plus the final path
    and performance stats. Nothing is cached server-side -- the board is
    deterministic from the session descriptor, and GBFS on even the
    largest (40x40) board completes in well under a second, so
    /api/ai/step below simply re-runs it rather than relying on any
    server-side cache surviving between requests.
    """
    descriptor, err = _require_descriptor()
    if err:
        return err

    board = _build_board(descriptor)
    result = greedy_best_first_search(board.walkability_grid(), board.start, board.goal)

    descriptor["solved"] = True
    session[SESSION_KEY] = descriptor
    return jsonify(result.to_dict())


@app.route("/api/ai/step", methods=["POST"])
def api_ai_step():
    """
    Returns a single step from the search trace, by index (0-based).
    The search is deterministic given the board, so it is simply
    re-run here rather than read from a cache -- see api_ai_solve().
    """
    descriptor, err = _require_descriptor()
    if err:
        return err

    if not descriptor.get("solved"):
        return _error("No solve has been run yet. Call /api/ai/solve first.", 409)

    payload = request.get_json(silent=True) or {}
    try:
        index = int(payload.get("index", 0))
    except (TypeError, ValueError):
        return _error("index must be an integer")

    board = _build_board(descriptor)
    result = greedy_best_first_search(board.walkability_grid(), board.start, board.goal)

    total_steps = len(result.steps)
    if index < 0 or index >= total_steps:
        return _error(f"index out of range (0..{total_steps - 1})")

    return jsonify({
        "step": result.steps[index].to_dict(),
        "index": index,
        "total_steps": total_steps,
        "is_last": index == total_steps - 1,
    })


# --------------------------------------------------------------------
# API: educational info
# --------------------------------------------------------------------

@app.route("/api/algorithm/info", methods=["GET"])
def api_algorithm_info():
    return jsonify({
        "name": "Greedy Best-First Search",
        "formula": "f(n) = h(n)",
        "heuristic": {
            "name": "Manhattan Distance",
            "formula": "h(n) = |x - goal_x| + |y - goal_y|",
        },
        "explanation": (
            "Greedy Best-First Search always expands the node in the OPEN "
            "list whose heuristic estimate h(n) is smallest -- i.e. the "
            "node that currently looks closest to the goal. Unlike A*, it "
            "never factors in g(n), the cost already spent reaching that "
            "node, so it can be led into detours by obstacles that block "
            "the heuristically-tempting direction."
        ),
        "guarantees_optimal_path": False,
        "guarantees_complete": True,
        "comparison": [
            {"algorithm": "BFS", "uses_heuristic": False, "uses_path_cost": True,
             "behavior": "Explores uniformly, level by level"},
            {"algorithm": "DFS", "uses_heuristic": False, "uses_path_cost": False,
             "behavior": "Goes deep down one branch before backtracking"},
            {"algorithm": "GBFS", "uses_heuristic": True, "uses_path_cost": False,
             "behavior": "Goal-directed, fast, not guaranteed optimal"},
            {"algorithm": "A*", "uses_heuristic": True, "uses_path_cost": True,
             "behavior": "Combines cost-so-far and heuristic; optimal with an admissible heuristic"},
        ],
    })


@app.route("/api/challenge/levels", methods=["GET"])
def api_challenge_levels():
    return jsonify({
        "levels": [
            {"level_id": lid, "name": name}
            for lid, name in sorted(CHALLENGE_LEVEL_NAMES.items())
        ]
    })


# --------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "not_found"}), 404


@app.errorhandler(500)
def server_error(_e):
    return jsonify({"error": "internal_server_error"}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
