"""
app.py

GREEDY QUEST -- Flask backend.

State model: no database (per spec section 29). Each browser gets a
session cookie holding a game_id (uuid4); the actual GameState objects
live server-side in an in-memory dict (GAME_STORE). This is the right
tradeoff for a single-process academic demo -- restarting the server
clears all games, which is fine here.

Every endpoint validates its own input and never trusts client-supplied
coordinates blindly (spec section 33).
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from flask import Flask, jsonify, render_template, request, session

from algorithms.greedy_best_first import SearchResult, greedy_best_first_search
from game.board import DIFFICULTY_SETTINGS, Board
from game.game_state import GameState, MOVE_DELTAS
from game.map_generator import (
    CHALLENGE_LEVEL_NAMES,
    generate_random_map,
    get_challenge_level,
)

app = Flask(__name__)
app.secret_key = os.environ.get("GREEDY_QUEST_SECRET_KEY", "dev-secret-change-me")

# In-memory server-side store: game_id -> {"state": GameState, "last_solve": SearchResult|None}
GAME_STORE: dict[str, dict] = {}

DIRECTION_ALIASES = {
    "up": "up", "w": "up", "arrowup": "up",
    "down": "down", "s": "down", "arrowdown": "down",
    "left": "left", "a": "left", "arrowleft": "left",
    "right": "right", "d": "right", "arrowright": "right",
}


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def _get_game_id(create_if_missing: bool = False) -> Optional[str]:
    game_id = session.get("game_id")
    if game_id is None and create_if_missing:
        game_id = str(uuid.uuid4())
        session["game_id"] = game_id
    return game_id


def _get_entry() -> Optional[dict]:
    game_id = _get_game_id()
    if game_id is None:
        return None
    return GAME_STORE.get(game_id)


def _require_entry():
    entry = _get_entry()
    if entry is None:
        return None, (jsonify({
            "error": "no_active_game",
            "message": "No active game for this session. Call /api/game/new first.",
        }), 404)
    return entry, None


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
    else:
        if difficulty not in DIFFICULTY_SETTINGS:
            return _error(f"difficulty must be one of {sorted(DIFFICULTY_SETTINGS)}")
        seed_val = None
        if seed is not None:
            try:
                seed_val = int(seed)
            except (TypeError, ValueError):
                return _error("seed must be an integer")
        board = generate_random_map(difficulty, seed=seed_val)

    game_id = _get_game_id(create_if_missing=True)
    state = GameState.new(board, difficulty)
    GAME_STORE[game_id] = {"state": state, "last_solve": None}

    response = state.to_dict()
    if level_id is not None:
        response["level_id"] = level_id
        response["level_name"] = CHALLENGE_LEVEL_NAMES[level_id]
    return jsonify(response)


@app.route("/api/game/state", methods=["GET"])
def api_game_state():
    entry, err = _require_entry()
    if err:
        return err
    return jsonify(entry["state"].to_dict())


@app.route("/api/game/move", methods=["POST"])
def api_game_move():
    entry, err = _require_entry()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    raw_direction = str(payload.get("direction", "")).lower()
    direction = DIRECTION_ALIASES.get(raw_direction)
    if direction is None:
        return _error(f"direction must be one of {sorted(set(DIRECTION_ALIASES))}")

    state: GameState = entry["state"]
    result = state.move(direction)
    result["state"] = state.to_dict()
    return jsonify(result)


@app.route("/api/game/reset", methods=["POST"])
def api_game_reset():
    """Reset the player back to start on the SAME board (same map, fresh attempt)."""
    entry, err = _require_entry()
    if err:
        return err
    old_state: GameState = entry["state"]
    new_state = GameState.new(old_state.board, old_state.difficulty)
    entry["state"] = new_state
    entry["last_solve"] = None
    return jsonify(new_state.to_dict())


# --------------------------------------------------------------------
# API: AI (GBFS)
# --------------------------------------------------------------------

@app.route("/api/ai/solve", methods=["POST"])
def api_ai_solve():
    """
    Runs the real GBFS solver on the current board and returns the full
    step-by-step trace (for 'Watch AI Think' replay) plus the final path
    and performance stats. The trace is cached server-side so /api/ai/step
    can serve individual steps without re-running the search.
    """
    entry, err = _require_entry()
    if err:
        return err

    state: GameState = entry["state"]
    board: Board = state.board

    result: SearchResult = greedy_best_first_search(
        board.walkability_grid(), board.start, board.goal
    )
    entry["last_solve"] = result
    return jsonify(result.to_dict())


@app.route("/api/ai/step", methods=["POST"])
def api_ai_step():
    """
    Returns a single step from the most recent /api/ai/solve trace, by
    index (0-based). Lets the frontend drive STEP / PLAY / PAUSE controls
    without re-sending the whole trace or re-running the search.
    """
    entry, err = _require_entry()
    if err:
        return err

    last_solve: Optional[SearchResult] = entry.get("last_solve")
    if last_solve is None:
        return _error("No solve has been run yet. Call /api/ai/solve first.", 409)

    payload = request.get_json(silent=True) or {}
    try:
        index = int(payload.get("index", 0))
    except (TypeError, ValueError):
        return _error("index must be an integer")

    total_steps = len(last_solve.steps)
    if index < 0 or index >= total_steps:
        return _error(f"index out of range (0..{total_steps - 1})")

    return jsonify({
        "step": last_solve.steps[index].to_dict(),
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
