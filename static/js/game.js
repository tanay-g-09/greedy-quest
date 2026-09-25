/* ============================================================
   GREEDY QUEST -- game.js
   Human play state: board fetch/render, movement, HUD, timer,
   treasure-found overlay.
   ============================================================ */

window.GQ = (function () {
  "use strict";

  const state = {
    board: null,
    playerPos: null,
    moves: 0,
    distance: null,
    difficulty: "easy",
    levelId: null,
    levelName: null,
    finished: false,
    clientStart: null,
    timerHandle: null,
    canvas: null,
  };

  function $(id) { return document.getElementById(id); }

  async function api(path, opts) {
    opts = opts || {};
    const res = await fetch(path, Object.assign({
      headers: { "Content-Type": "application/json" },
    }, opts));
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.message || "request_failed");
      err.data = data;
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function formatTime(seconds) {
    return seconds.toFixed(1) + "s";
  }

  function startTimer() {
    stopTimer();
    state.clientStart = Date.now();
    state.timerHandle = setInterval(() => {
      if (state.finished) return;
      const elapsed = (Date.now() - state.clientStart) / 1000;
      $("stat-time").textContent = formatTime(elapsed);
    }, 100);
  }

  function stopTimer() {
    if (state.timerHandle) {
      clearInterval(state.timerHandle);
      state.timerHandle = null;
    }
  }

  function elapsedSeconds() {
    if (!state.clientStart) return 0;
    return (Date.now() - state.clientStart) / 1000;
  }

  function render() {
    if (!state.board || !state.canvas) return;
    window.GQVisualization.drawBoard(state.canvas, state.board, {
      playerPos: state.playerPos,
      explored: window.GQ_AI ? window.GQ_AI.getExplored() : [],
      frontier: window.GQ_AI ? window.GQ_AI.getFrontier() : [],
      current: window.GQ_AI ? window.GQ_AI.getCurrent() : null,
      path: window.GQ_AI ? window.GQ_AI.getPath() : [],
      showHeuristics: $("toggle-heuristics").checked,
      showNumbers: $("toggle-numbers").checked,
      stepOrder: window.GQ_AI ? window.GQ_AI.getStepOrder() : null,
    });
  }

  function updateHud() {
    $("stat-moves").textContent = String(state.moves);
    $("stat-distance").textContent = state.distance != null ? String(state.distance) : "--";
    $("difficulty-badge").textContent = state.levelName
      ? state.levelName.toLowerCase()
      : state.difficulty;
  }

  function updateScoreDisplay(score) {
    $("stat-score").textContent = String(score);
  }

  async function newGame(difficulty, levelId, seed) {
    const payload = {};
    if (levelId) payload.level_id = levelId;
    else payload.difficulty = difficulty;
    if (seed != null) payload.seed = seed;

    const data = await api("/api/game/new", { method: "POST", body: JSON.stringify(payload) });
    applyStateResponse(data);
    if (window.GQ_AI) window.GQ_AI.reset();
    $("treasure-overlay").classList.remove("visible");
    startTimer();
    render();
  }

  function applyStateResponse(data) {
    state.board = data.board;
    state.playerPos = data.player_pos;
    state.moves = data.moves;
    state.distance = data.distance_to_goal;
    state.difficulty = data.difficulty;
    state.levelId = data.level_id || null;
    state.levelName = data.level_name || null;
    state.finished = data.finished;
    updateHud();
    updateScoreDisplay(data.score);
  }

  async function movePlayer(direction) {
    if (state.finished) return;
    let result;
    try {
      result = await api("/api/game/move", {
        method: "POST",
        body: JSON.stringify({ direction }),
      });
    } catch (e) {
      return;
    }
    if (result.success) {
      state.playerPos = result.position;
      state.moves = result.moves;
      state.distance = result.distance_to_goal;
      updateHud();
      updateScoreDisplay(result.state.score);
      render();

      if (result.reached_goal) {
        finishGame(result.state);
      }
    }
  }

  function finishGame(finalState) {
    state.finished = true;
    stopTimer();
    $("stat-time").textContent = formatTime(finalState.elapsed_seconds);

    $("tc-moves").textContent = String(finalState.moves);
    $("tc-time").textContent = formatTime(finalState.elapsed_seconds);
    $("tc-path").textContent = String(finalState.moves);
    $("tc-score").textContent = String(finalState.score);
    $("treasure-overlay").classList.add("visible");

    // Save player run for the Human vs AI comparison page.
    try {
      const existing = JSON.parse(localStorage.getItem("greedyQuestComparison") || "{}");
      existing.player = {
        moves: finalState.moves,
        time: finalState.elapsed_seconds,
        score: finalState.score,
      };
      localStorage.setItem("greedyQuestComparison", JSON.stringify(existing));
    } catch (e) { /* localStorage unavailable -- non-fatal */ }
  }

  async function resetPosition() {
    const data = await api("/api/game/reset", { method: "POST" });
    applyStateResponse(data);
    if (window.GQ_AI) window.GQ_AI.reset();
    $("treasure-overlay").classList.remove("visible");
    startTimer();
    render();
  }

  function init(canvas) {
    state.canvas = canvas;
  }

  return {
    state, init, newGame, movePlayer, resetPosition, render,
    updateHud, elapsedSeconds, api, $,
  };
})();
