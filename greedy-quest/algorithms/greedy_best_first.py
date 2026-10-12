"""
Greedy Best-First Search (GBFS) for grid pathfinding.

IMPORTANT ALGORITHMIC CONTRACT
-------------------------------
GBFS orders the priority queue using ONLY the heuristic estimate:

    f(n) = h(n)

It does NOT add the accumulated path cost g(n), which is what
distinguishes it from A* (f(n) = g(n) + h(n)). This file must never
be "upgraded" to track g(n) in the priority ordering -- that would
silently turn this into A* and defeat the point of the demo.

Heuristic used: Manhattan distance.
    h(n) = |n.x - goal.x| + |n.y - goal.y|
"""

from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Coord = Tuple[int, int]


def manhattan_distance(a: Coord, b: Coord) -> int:
    """h(n): Manhattan distance heuristic between two grid coordinates."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class FrontierEntry:
    """One candidate node sitting in the OPEN list at a given step."""
    position: Coord
    heuristic: int


@dataclass
class SearchStep:
    """
    A single 'tick' of the algorithm, suitable for frontend replay.

    step        : 1-indexed iteration counter
    current     : the node just popped from OPEN and expanded
    heuristic   : h(current)
    frontier    : snapshot of OPEN *after* this expansion (position + h)
    explored    : snapshot of CLOSED (all nodes expanded so far)
    neighbors   : neighbors considered during this expansion, with h(n) each
    selected    : the neighbor that will be popped next iteration
                  (None if OPEN is empty or goal was reached this step)
    """
    step: int
    current: Coord
    heuristic: int
    neighbors: List[FrontierEntry] = field(default_factory=list)
    frontier: List[FrontierEntry] = field(default_factory=list)
    explored: List[Coord] = field(default_factory=list)
    selected: Optional[Coord] = None

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "current": list(self.current),
            "heuristic": self.heuristic,
            "neighbors": [
                {"position": list(n.position), "heuristic": n.heuristic}
                for n in self.neighbors
            ],
            "frontier": [
                {"position": list(f.position), "heuristic": f.heuristic}
                for f in self.frontier
            ],
            "explored": [list(e) for e in self.explored],
            "selected": list(self.selected) if self.selected else None,
        }


@dataclass
class SearchResult:
    found: bool
    path: List[Coord]
    steps: List[SearchStep]
    explored_count: int
    max_frontier_size: int
    execution_time_ms: float
    goal: Coord
    start: Coord

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "path": [list(p) for p in self.path],
            "path_length": len(self.path),
            "steps": [s.to_dict() for s in self.steps],
            "nodes_explored": self.explored_count,
            "max_frontier_size": self.max_frontier_size,
            "execution_time_ms": round(self.execution_time_ms, 3),
            "num_steps": len(self.steps),
            "goal": list(self.goal),
            "start": list(self.start),
            "exploration_ratio": (
                round(self.explored_count / max(len(self.path), 1), 3)
                if self.found else None
            ),
        }


def greedy_best_first_search(
    grid: List[List[int]],
    start: Coord,
    goal: Coord,
    walkable_value: int = 0,
) -> SearchResult:
    """
    Run Greedy Best-First Search on a 2D grid.

    grid  : 2D list, grid[y][x], where cell value != walkable_value means
            blocked (wall). Traps are still walkable for GBFS purposes
            (they affect gameplay/score, not the search itself).
    start : (x, y) start coordinate
    goal  : (x, y) goal coordinate

    Returns a SearchResult with the reconstructed path (empty if no
    solution) and a full step trace for visualization/replay.
    """
    t0 = time.perf_counter()

    height = len(grid)
    width = len(grid[0]) if height else 0

    def in_bounds(pos: Coord) -> bool:
        x, y = pos
        return 0 <= x < width and 0 <= y < height

    def is_walkable(pos: Coord) -> bool:
        x, y = pos
        return grid[y][x] == walkable_value

    def neighbors_of(pos: Coord) -> List[Coord]:
        x, y = pos
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in candidates if in_bounds(c) and is_walkable(c)]

    # Tie-breaker counter so heapq never has to compare Coord tuples
    # when two heuristics are equal (keeps insertion order stable/deterministic).
    counter = itertools.count()

    # OPEN list: priority queue ordered by h(n) ONLY. This is the line
    # that defines this algorithm as GBFS rather than A* or Dijkstra.
    open_heap: List[Tuple[int, int, Coord]] = []
    heapq.heappush(open_heap, (manhattan_distance(start, goal), next(counter), start))

    parents: Dict[Coord, Optional[Coord]] = {start: None}
    closed: set[Coord] = set()
    in_open: set[Coord] = {start}

    steps: List[SearchStep] = []
    max_frontier_size = 1
    found = False

    if not in_bounds(start) or not in_bounds(goal):
        raise ValueError("start or goal is outside the grid bounds")
    if not is_walkable(start) or not is_walkable(goal):
        raise ValueError("start or goal is not on a walkable cell")

    step_num = 0
    while open_heap:
        h_current, _, current = heapq.heappop(open_heap)
        in_open.discard(current)

        if current in closed:
            continue

        step_num += 1
        closed.add(current)

        if current == goal:
            found = True
            steps.append(SearchStep(
                step=step_num,
                current=current,
                heuristic=h_current,
                explored=list(closed),
                frontier=[
                    FrontierEntry(pos, manhattan_distance(pos, goal))
                    for _, _, pos in open_heap
                ],
            ))
            break

        neighbor_entries: List[FrontierEntry] = []
        for n in neighbors_of(current):
            if n in closed:
                continue
            h_n = manhattan_distance(n, goal)
            neighbor_entries.append(FrontierEntry(n, h_n))
            if n not in parents:
                parents[n] = current
            if n not in in_open:
                heapq.heappush(open_heap, (h_n, next(counter), n))
                in_open.add(n)

        max_frontier_size = max(max_frontier_size, len(open_heap))

        # Peek at what will be selected next (smallest h in OPEN).
        selected = open_heap[0][2] if open_heap else None

        steps.append(SearchStep(
            step=step_num,
            current=current,
            heuristic=h_current,
            neighbors=neighbor_entries,
            frontier=[
                FrontierEntry(pos, manhattan_distance(pos, goal))
                for _, _, pos in open_heap
            ],
            explored=list(closed),
            selected=selected,
        ))

    # Reconstruct path by walking parents backwards from goal.
    path: List[Coord] = []
    if found:
        node: Optional[Coord] = goal
        while node is not None:
            path.append(node)
            node = parents.get(node)
        path.reverse()

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return SearchResult(
        found=found,
        path=path,
        steps=steps,
        explored_count=len(closed),
        max_frontier_size=max_frontier_size,
        execution_time_ms=elapsed_ms,
        goal=goal,
        start=start,
    )
