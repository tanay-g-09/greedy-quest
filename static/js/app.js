/* ============================================================
   GREEDY QUEST -- app.js
   Wires up DOM controls on the game page. Only runs where the
   expected elements exist, so it's harmless on other pages.
   ============================================================ */

(function () {
  "use strict";

  const canvas = document.getElementById("board-canvas");
  if (!canvas || typeof GQ === "undefined") return; // not the game page

  GQ.init(canvas);

  function $(id) { return document.getElementById(id); }

  function currentSelection() {
    const levelVal = $("level-select").value;
    const difficulty = $("difficulty-select").value;
    return {
      difficulty,
      levelId: levelVal ? parseInt(levelVal, 10) : null,
    };
  }

  async function loadNewMap() {
    const sel = currentSelection();
    localStorage.removeItem("greedyQuestComparison");
    await GQ.newGame(sel.difficulty, sel.levelId);
  }

  // ---- setup panel ----
  $("btn-new-map").addEventListener("click", loadNewMap);
  $("btn-play-again").addEventListener("click", loadNewMap);

  $("level-select").addEventListener("change", () => {
    $("difficulty-select").disabled = !!$("level-select").value;
  });

  // ---- HUD actions ----
  $("btn-reset-position").addEventListener("click", () => GQ.resetPosition());

  let paused = false;
  $("btn-pause").addEventListener("click", () => {
    paused = !paused;
    $("btn-pause").textContent = paused ? "Resume" : "Pause";
  });

  // ---- keyboard movement ----
  const KEY_DIRS = {
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
    w: "up", s: "down", a: "left", d: "right",
    W: "up", S: "down", A: "left", D: "right",
  };
  window.addEventListener("keydown", (e) => {
    if (paused) return;
    const dir = KEY_DIRS[e.key];
    if (!dir) return;
    // don't hijack typing in selects/inputs
    const tag = (document.activeElement && document.activeElement.tagName) || "";
    if (tag === "SELECT" || tag === "INPUT") return;
    e.preventDefault();
    GQ.movePlayer(dir);
  });

  // ---- mobile dpad ----
  document.querySelectorAll(".dpad button").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (paused) return;
      GQ.movePlayer(btn.dataset.dir);
    });
  });

  // ---- AI controls ----
  $("btn-ai-solve").addEventListener("click", () => GQ_AI.solve());
  $("btn-watch-ai").addEventListener("click", () => GQ_AI.watch());
  $("btn-step").addEventListener("click", async () => {
    if (!GQ_AI.state.trace) {
      await GQ_AI.solve({ silent: true }); // fetches trace, leaves index at -1
    }
    GQ_AI.stepForward(); // advances to 0 on first call, or forward otherwise
  });
  $("btn-play-pause-ai").addEventListener("click", () => GQ_AI.togglePlayPause());
  $("btn-reset-ai").addEventListener("click", () => { GQ_AI.reset(); GQ.render(); });

  document.querySelectorAll(".speed-row button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".speed-row button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      GQ_AI.setSpeed(btn.dataset.speed);
    });
  });

  $("toggle-heuristics").addEventListener("change", () => GQ.render());
  $("toggle-numbers").addEventListener("change", () => GQ.render());

  // ---- educational panel ----
  $("edu-toggle").addEventListener("click", () => {
    $("edu-panel").classList.toggle("open");
  });

  // ---- initial load: honor ?level= / ?watch= query params ----
  const params = new URLSearchParams(window.location.search);
  const initialLevel = params.get("level");
  const initialWatch = params.get("watch");

  (async function boot() {
    if (initialLevel) {
      $("level-select").value = initialLevel;
      $("difficulty-select").disabled = true;
      await GQ.newGame(null, parseInt(initialLevel, 10));
    } else {
      await GQ.newGame("easy", null);
    }
    if (initialWatch) {
      GQ_AI.watch();
    }
  })();
})();
