/* ============================================================
   GREEDY QUEST -- ai.js
   Runs GBFS via /api/ai/solve, then replays the returned step
   trace client-side to drive Watch AI Think / Step / Play / Pause.
   ============================================================ */

window.GQ_AI = (function () {
  "use strict";

  const SPEED_MS = { slow: 900, medium: 450, fast: 150 };

  const state = {
    trace: null,       // full SearchResult.to_dict() from /api/ai/solve
    index: -1,          // current step index into trace.steps (-1 = nothing shown)
    playing: false,
    speed: "medium",
    playHandle: null,
    resumeAfterPause: false, // was the replay playing when the game was paused?
    stepOrderFull: null, // Map "x,y" -> order, built once trace arrives
  };

  function $(id) { return document.getElementById(id); }

  function reset() {
    stopPlayback();
    state.resumeAfterPause = false;
    state.trace = null;
    state.index = -1;
    state.stepOrderFull = null;
    $("readout-current").innerHTML = '<span class="readout-empty">Run "Solve with AI" or "Watch AI think" to see live search state.</span>';
    $("readout-neighbors").innerHTML = "";
    $("step-progress").textContent = "";
    $("perf-explored").textContent = "--";
    $("perf-path").textContent = "--";
    $("perf-time").textContent = "--";
    $("perf-status").textContent = "--";
    updatePlayPauseLabel();
  }

  function stopPlayback() {
    state.playing = false;
    if (state.playHandle) {
      clearTimeout(state.playHandle);
      state.playHandle = null;
    }
    updatePlayPauseLabel();
  }

  function updatePlayPauseLabel() {
    const btn = $("btn-play-pause-ai");
    if (btn) btn.textContent = state.playing ? "Pause" : "Play";
  }

  async function solve({ silent } = {}) {
    stopPlayback();
    const data = await GQ.api("/api/ai/solve", { method: "POST", body: JSON.stringify({}) });
    state.trace = data;
    state.index = -1;

    updatePerfTable(data);
    saveAiComparison(data);

    if (!silent) {
      // "Solve with AI": jump straight to showing the final path.
      state.index = data.steps.length - 1;
      renderCurrentStep();
    }
    GQ.render();
    return data;
  }

  function updatePerfTable(data) {
    $("perf-explored").textContent = String(data.nodes_explored);
    $("perf-path").textContent = data.found ? String(data.path_length) : "--";
    $("perf-time").textContent = data.execution_time_ms.toFixed(2) + "ms";
    const statusEl = $("perf-status");
    statusEl.textContent = data.found ? "FOUND" : "NOT FOUND";
    statusEl.className = "v " + (data.found ? "found" : "not-found");
  }

  function saveAiComparison(data) {
    try {
      const existing = JSON.parse(localStorage.getItem("greedyQuestComparison") || "{}");
      existing.ai = {
        nodes_explored: data.nodes_explored,
        execution_time_ms: data.execution_time_ms,
        path_length: data.found ? data.path_length : null,
        found: data.found,
      };
      localStorage.setItem("greedyQuestComparison", JSON.stringify(existing));
    } catch (e) { /* non-fatal */ }
  }

  async function watch() {
    await solve({ silent: true });
    if (!state.trace || state.trace.steps.length === 0) return;
    state.index = 0;
    renderCurrentStep();
    play();
  }

  function play() {
    if (!state.trace) return;
    // Pressing Play after the replay finished starts it over.
    if (state.index >= state.trace.steps.length - 1) {
      state.index = 0;
      renderCurrentStep();
    }
    state.playing = true;
    updatePlayPauseLabel();
    scheduleNext();
  }

  function pause() {
    stopPlayback();
  }

  function togglePlayPause() {
    if (!state.trace) { watch(); return; }
    if (state.playing) pause();
    else play();
  }

  function scheduleNext() {
    if (!state.playing) return;
    if (state.index >= state.trace.steps.length - 1) {
      stopPlayback();
      return;
    }
    state.playHandle = setTimeout(() => {
      stepForward();
      scheduleNext();
    }, SPEED_MS[state.speed]);
  }

  function stepForward() {
    if (!state.trace) return;
    if (state.index >= state.trace.steps.length - 1) return;
    state.index += 1;
    renderCurrentStep();
  }

  /** Game paused: halt the replay but remember whether to continue it. */
  function onGamePaused() {
    state.resumeAfterPause = state.playing;
    if (state.playing) stopPlayback();
  }

  function onGameResumed() {
    if (state.resumeAfterPause && state.trace) play();
    state.resumeAfterPause = false;
  }

  function setSpeed(speed) {
    if (SPEED_MS[speed]) state.speed = speed;
  }

  function renderCurrentStep() {
    if (!state.trace || state.index < 0) return;
    const step = state.trace.steps[state.index];
    const total = state.trace.steps.length;
    const isFinal = state.index === total - 1;

    $("step-progress").textContent = `step ${step.step} of ${total}`;

    const hCurrent = step.heuristic;
    $("readout-current").innerHTML =
      `<div>current node <span class="coord">(${step.current[0]}, ${step.current[1]})</span></div>` +
      `<div>h(n) = <span class="h-value">${hCurrent}</span></div>`;

    const rows = (step.neighbors || []).map((n) => {
      const selected = step.selected && n.position[0] === step.selected[0] && n.position[1] === step.selected[1];
      return `<div class="row${selected ? " selected" : ""}">` +
        `<span class="coord">(${n.position[0]}, ${n.position[1]})</span>` +
        `<span>h = ${n.heuristic}</span></div>`;
    });
    $("readout-neighbors").innerHTML = rows.join("") ||
      (isFinal ? '<div class="row selected">goal reached</div>' : "");

    // Build step-order map lazily up to current index (for "show step numbers")
    state.stepOrderFull = new Map();
    for (let i = 0; i <= state.index; i++) {
      const s = state.trace.steps[i];
      state.stepOrderFull.set(s.current[0] + "," + s.current[1], s.step);
    }

    GQ.render();
  }

  // ---- accessors used by game.js render() ----

  function getExplored() {
    if (!state.trace || state.index < 0) return [];
    return state.trace.steps[state.index].explored || [];
  }
  function getFrontier() {
    if (!state.trace || state.index < 0) return [];
    return state.trace.steps[state.index].frontier || [];
  }
  function getCurrent() {
    if (!state.trace || state.index < 0) return null;
    return state.trace.steps[state.index].current || null;
  }
  function getPath() {
    if (!state.trace) return [];
    const isFinalStepShown = state.index === state.trace.steps.length - 1;
    return (state.trace.found && isFinalStepShown) ? state.trace.path : [];
  }
  function getStepOrder() {
    return state.stepOrderFull;
  }

  return {
    state, reset, solve, watch, play, pause, togglePlayPause,
    stepForward, setSpeed, onGamePaused, onGameResumed,
    getExplored, getFrontier, getCurrent, getPath, getStepOrder,
  };
})();
