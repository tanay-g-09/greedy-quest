/* ============================================================
   GREEDY QUEST -- game.js
   Human play state: board fetch/render, movement, HUD, timer,
   pause/resume, treasure-found overlay.
   ============================================================ */

window.GQ = (function () {
  "use strict";

  // Buttons that must not run while the game is paused. New map / Reset
  // stay enabled on purpose: they start a fresh attempt, which clears the
  // pause.
  const AI_BUTTON_IDS = [
    "btn-ai-solve", "btn-watch-ai", "btn-step", "btn-play-pause-ai", "btn-reset-ai",
  ];

  const state = {
    board: null,
    playerPos: null,
    moves: 0,
    distance: null,
    difficulty: "easy",
    levelId: null,
    levelName: null,
    finished: false,
    paused: false,
    pausedAtClient: null,   // Date.now() at the moment the player paused
    pauseToken: 0,          // bumped on every pause/resume/new game to ignore stale replies
    clientStart: null,      // Date.now() - time already played (shifted on resume)
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

  // ---------------------------------------------------------------
  // Timer
  // ---------------------------------------------------------------

  function startTimer() {
    stopTimer();
    state.clientStart = Date.now();
    state.timerHandle = setInterval(() => {
      // The interval keeps firing while paused; it just must not advance
      // the display. (Not checking this was the original pause bug.)
      if (state.finished || state.paused) return;
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
    const end = state.paused && state.pausedAtClient ? state.pausedAtClient : Date.now();
    return (end - state.clientStart) / 1000;
  }

  // ---------------------------------------------------------------
  // Pause / resume
  // ---------------------------------------------------------------

  function applyPausedUi() {
    const paused = state.paused;
    const pauseBtn = $("btn-pause");
    pauseBtn.textContent = paused ? "Resume" : "Pause";
    pauseBtn.setAttribute("aria-pressed", String(paused));
    pauseBtn.disabled = state.finished;      // nothing to pause once the treasure is found
    $("pause-overlay").classList.toggle("visible", paused);
    AI_BUTTON_IDS.forEach((id) => { $(id).disabled = paused; });
  }

  /** Forget any pause (used when a new attempt starts). */
  function clearPause() {
    state.paused = false;
    state.pausedAtClient = null;
    state.pauseToken += 1;
  }

  async function setPaused(wantPaused) {
    if (state.finished || !state.board || state.paused === wantPaused) return;

    // Update the UI and the local clock immediately so the pause feels
    // instant, then reconcile with the server's authoritative clock.
    const now = Date.now();
    state.paused = wantPaused;
    if (wantPaused) {
      state.pausedAtClient = now;
      $("stat-time").textContent = formatTime(elapsedSeconds());  // show the exact frozen value
      if (window.GQ_AI) window.GQ_AI.onGamePaused();
    } else {
      state.clientStart += now - state.pausedAtClient;
      state.pausedAtClient = null;
      if (window.GQ_AI) window.GQ_AI.onGameResumed();
    }
    applyPausedUi();
    if (wantPaused) $("btn-resume").focus();
    else state.canvas.focus();

    const token = ++state.pauseToken;
    try {
      const data = await api(wantPaused ? "/api/game/pause" : "/api/game/resume", {
        method: "POST",
      });
      // Ignore the reply if the player has since toggled again or started a new game.
      if (token !== state.pauseToken || state.finished) return;
      const anchor = wantPaused ? state.pausedAtClient : Date.now();
      state.clientStart = anchor - data.elapsed_seconds * 1000;
      $("stat-time").textContent = formatTime(data.elapsed_seconds);
      updateScoreDisplay(data.score);
    } catch (e) {
      /* Server unreachable: the local clock is still correct, keep going. */
    }
  }

  function togglePause() {
    return setPaused(!state.paused);
  }

  // ---------------------------------------------------------------
  // Rendering / HUD
  // ---------------------------------------------------------------

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

  // ---------------------------------------------------------------
  // Game lifecycle
  // ---------------------------------------------------------------

  /** Shared by newGame() and resetPosition(): a fresh attempt on the server's board. */
  function startFreshAttempt(data) {
    applyStateResponse(data);
    clearPause();
    if (window.GQ_AI) window.GQ_AI.reset();
    $("treasure-overlay").classList.remove("visible");
    $("stat-time").textContent = formatTime(0);
    startTimer();
    applyPausedUi();
    render();
  }

  async function newGame(difficulty, levelId, seed) {
    const payload = {};
    if (levelId) payload.level_id = levelId;
    else payload.difficulty = difficulty;
    if (seed != null) payload.seed = seed;

    const data = await api("/api/game/new", { method: "POST", body: JSON.stringify(payload) });
    startFreshAttempt(data);
  }

  async function resetPosition() {
    const data = await api("/api/game/reset", { method: "POST" });
    startFreshAttempt(data);
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
    if (state.finished || state.paused) return;
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
    applyPausedUi();   // disables the Pause button
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

  function init(canvas) {
    state.canvas = canvas;
  }

  return {
    state, init, newGame, movePlayer, resetPosition, render,
    updateHud, elapsedSeconds, api, $,
    setPaused, togglePause,
  };
})();
