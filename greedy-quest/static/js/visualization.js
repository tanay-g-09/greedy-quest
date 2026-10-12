/* ============================================================
   GREEDY QUEST -- visualization.js
   Pure rendering: given a board + overlay state, draw the canvas.
   No network calls live here.
   ============================================================ */

(function () {
  "use strict";

  const MAX_CANVAS_PX = 640; // logical drawing size; CSS scales it down responsively

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  const Palette = {
    get bg() { return cssVar("--surface"); },
    get grid() { return "#1b2333"; },
    get wall() { return "#3a4257"; },
    get wallEdge() { return "#4a5470"; },
    get trap() { return cssVar("--coral"); },
    get empty() { return cssVar("--surface"); },
    get start() { return cssVar("--gold"); },
    get goal() { return cssVar("--gold"); },
    get frontier() { return cssVar("--teal"); },
    get explored() { return cssVar("--blue"); },
    get current() { return "#ffb020"; },
    get path() { return cssVar("--violet"); },
    get player() { return "#ffffff"; },
    get text() { return cssVar("--text"); },
    get textMuted() { return cssVar("--text-faint"); },
  };

  function manhattan(a, b) {
    return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
  }

  /**
   * Draw the full board with optional AI overlay state.
   *
   * @param {HTMLCanvasElement} canvas
   * @param {object} board  {width, height, tiles, start, goal}
   * @param {object} opts   {
   *   playerPos: [x,y] | null,
   *   explored: Set<"x,y"> | array,
   *   frontier: [{position, heuristic}] | [],
   *   current: [x,y] | null,
   *   path: [[x,y],...] | [],
   *   showHeuristics: bool,
   *   showNumbers: bool,
   *   stepOrder: Map<"x,y", number> | null   (for step numbers)
   * }
   */
  function drawBoard(canvas, board, opts) {
    opts = opts || {};
    const w = board.width, h = board.height;
    const cell = Math.floor(MAX_CANVAS_PX / Math.max(w, h));
    canvas.width = cell * w;
    canvas.height = cell * h;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = Palette.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const exploredSet = opts.explored instanceof Set
      ? opts.explored
      : new Set((opts.explored || []).map((p) => p[0] + "," + p[1]));

    const frontierMap = new Map(
      (opts.frontier || []).map((f) => [f.position[0] + "," + f.position[1], f.heuristic])
    );

    const pathSet = new Set((opts.path || []).map((p) => p[0] + "," + p[1]));

    // base terrain + overlays
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const px = x * cell, py = y * cell;
        const key = x + "," + y;
        const tile = board.tiles[y][x];

        let fill = Palette.empty;
        if (tile === 1) fill = Palette.wall;
        else if (tile === 2) fill = Palette.trap;

        // overlays layer on top of terrain (walls stay walls visually)
        if (tile !== 1) {
          if (pathSet.has(key)) fill = Palette.path;
          else if (exploredSet.has(key)) fill = Palette.explored;
          else if (frontierMap.has(key)) fill = Palette.frontier;
        }

        ctx.fillStyle = fill;
        ctx.fillRect(px, py, cell, cell);

        ctx.strokeStyle = Palette.grid;
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, cell - 1, cell - 1);

        if (tile === 1) {
          ctx.strokeStyle = Palette.wallEdge;
          ctx.strokeRect(px + 3, py + 3, cell - 6, cell - 6);
        }

        // heuristic numbers
        if (opts.showHeuristics && tile !== 1 && cell >= 16) {
          const hVal = manhattan([x, y], board.goal);
          ctx.fillStyle = "rgba(231,236,243,0.55)";
          ctx.font = Math.max(9, Math.floor(cell * 0.28)) + "px 'JetBrains Mono', monospace";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(String(hVal), px + cell / 2, py + cell / 2);
        }

        // step numbers (order explored)
        if (opts.showNumbers && opts.stepOrder && opts.stepOrder.has(key) && cell >= 16) {
          ctx.fillStyle = "rgba(10,14,20,0.85)";
          ctx.font = "bold " + Math.max(8, Math.floor(cell * 0.22)) + "px 'JetBrains Mono', monospace";
          ctx.textAlign = "left";
          ctx.textBaseline = "top";
          ctx.fillText(String(opts.stepOrder.get(key)), px + 2, py + 1);
        }
      }
    }

    // current node highlight ring
    if (opts.current) {
      const [cx, cy] = opts.current;
      ctx.strokeStyle = Palette.current;
      ctx.lineWidth = 3;
      ctx.strokeRect(cx * cell + 2, cy * cell + 2, cell - 4, cell - 4);
    }

    // start marker
    drawMarker(ctx, board.start, cell, Palette.start, "S");
    // goal marker
    drawMarker(ctx, board.goal, cell, Palette.goal, "G");

    // player marker (drawn last, on top)
    if (opts.playerPos) {
      const [px, py] = opts.playerPos;
      const cxp = px * cell + cell / 2;
      const cyp = py * cell + cell / 2;
      ctx.beginPath();
      ctx.arc(cxp, cyp, cell * 0.28, 0, Math.PI * 2);
      ctx.fillStyle = Palette.player;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#0a0e14";
      ctx.stroke();
    }
  }

  function drawMarker(ctx, pos, cell, color, _label) {
    const [x, y] = pos;
    const cx = x * cell + cell / 2;
    const cy = y * cell + cell / 2;
    const r = cell * 0.22;
    ctx.beginPath();
    ctx.moveTo(cx, cy - r);
    ctx.lineTo(cx + r, cy);
    ctx.lineTo(cx, cy + r);
    ctx.lineTo(cx - r, cy);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  window.GQVisualization = { drawBoard, manhattan };
})();
