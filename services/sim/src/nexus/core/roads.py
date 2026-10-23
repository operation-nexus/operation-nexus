"""Road graph and A* for ground movement (SIM-CORE §4 Edge, GAMEPLAY §5; NX-120).

Pure and deterministic: built from plain data (the runtime turns a loaded theater into `Road`s),
adjacency is held in node-id order, and heap entries carry explicit `(f, g, node_id)` keys, so no
result depends on dict, set or hash order. Travel cost is `length_m / speed_mult` (GAMEPLAY §5);
`length_m` is the straight line between the endpoints. A destroyed bridge removes its edge until
repaired (Q-GD-11): pass its node id in `blocked`.
"""

import heapq
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

ROAD = "ROAD"


@dataclass(frozen=True, slots=True)
class Road:
    """One ROAD edge as plain data; `bridge` is the BRIDGE node it crosses, if any."""

    a: str
    b: str
    speed_mult: float
    bridge: str | None = None


@dataclass(frozen=True, slots=True)
class Edge:
    id: str  # EdgeId `<a>~<b>~<layer>`, node ids sorted (CONTRACTS §3.2)
    length_m: float
    speed_mult: float
    bridge: str | None


def edge_id(a: str, b: str, layer: str = ROAD) -> str:
    lo, hi = sorted((a, b))
    return f"{lo}~{hi}~{layer}"


class RoadGraph:
    """Node positions (integer metres) and ROAD edges with adjacency sorted by neighbour id."""

    __slots__ = ("_adj", "_max_speed_mult", "pos")

    def __init__(self, pos: Mapping[str, tuple[int, int]], roads: Iterable[Road]) -> None:
        self.pos = dict(sorted(pos.items()))
        adj: dict[str, list[tuple[str, Edge]]] = {n: [] for n in self.pos}
        seen: set[str] = set()
        fastest = 1.0  # only scales the heuristic; with no edges no path needs it
        for r in roads:
            if r.a not in self.pos or r.b not in self.pos:
                raise ValueError(f"road {r.a}~{r.b} has an unknown endpoint")
            (ax, ay), (bx, by) = self.pos[r.a], self.pos[r.b]
            edge = Edge(edge_id(r.a, r.b), math.hypot(bx - ax, by - ay), r.speed_mult, r.bridge)
            if r.a == r.b or edge.id in seen:
                raise ValueError(f"self-loop or duplicate road {edge.id}")
            seen.add(edge.id)
            fastest = r.speed_mult if len(seen) == 1 else max(fastest, r.speed_mult)
            adj[r.a].append((r.b, edge))
            adj[r.b].append((r.a, edge))
        self._adj = {n: tuple(sorted(out, key=lambda t: t[0])) for n, out in adj.items()}
        self._max_speed_mult = fastest

    def neighbours(self, node: str) -> tuple[tuple[str, Edge], ...]:
        return self._adj[node]

    def edge(self, a: str, b: str) -> Edge:
        """The ROAD edge between two adjacent nodes; ValueError if there is none."""
        for nxt, edge in self._adj.get(a, ()):
            if nxt == b:
                return edge
        raise ValueError(f"no road between {a!r} and {b!r}")

    def edge_at(self, last: str, x: float, y: float) -> tuple[str, Edge] | None:
        """The neighbour of `last` and the edge to it whose segment holds the point (x, y): the
        road a unit that left `last` is on, so it can turn back (NX-374, followers)."""
        lx, ly = self.pos[last]
        for nxt, edge in self._adj[last]:
            dx, dy = self.pos[nxt][0] - lx, self.pos[nxt][1] - ly
            along = (x - lx) * dx + (y - ly) * dy  # 1e-6: relative collinearity epsilon below
            if (
                abs(dx * (y - ly) - dy * (x - lx)) <= 1e-6 * edge.length_m
                and 0 <= along <= edge.length_m**2
            ):
                return nxt, edge
        return None

    def speed_mult_at(self, last: str, heading: str, x: float, y: float) -> float:
        """`speed_mult` of the road a unit at (x, y) is on, having left `last` for `heading`; when
        `heading` is `last` it is turning back and the road is found by position (`edge_at`)."""
        if heading != last:
            return self.edge(last, heading).speed_mult
        found = self.edge_at(last, x, y)
        return 1.0 if found is None else found[1].speed_mult

    def heuristic(self, node: str, goal: str) -> float:
        """Straight line / fastest speed_mult: never above the true cost, so A* stays optimal."""
        (x, y), (gx, gy) = self.pos[node], self.pos[goal]
        return math.hypot(gx - x, gy - y) / self._max_speed_mult


def shortest_path(
    graph: RoadGraph,
    start: str,
    goal: str,
    *,
    blocked: frozenset[str],
    avoid: frozenset[str] = frozenset(),
) -> list[str] | None:
    """Cheapest node path from `start` to `goal` avoiding edges whose bridge is in `blocked` and
    never entering a node of `avoid` (the start is exempt; a goal in `avoid` is unreachable).

    Ties break by f, then g, then node id. A stale heap entry is skipped rather than using a closed
    set, so a float-rounding inconsistency in the heuristic re-expands a node instead of losing it.
    """
    for node in (start, goal):
        if node not in graph.pos:
            raise ValueError(f"unknown node {node!r}")
    best = {start: 0.0}
    came_from: dict[str, str] = {}
    heap = [(graph.heuristic(start, goal), 0.0, start)]
    while heap:
        _, g, node = heapq.heappop(heap)
        if g > best[node]:
            continue
        if node == goal:
            path = [goal]
            while path[-1] != start:
                path.append(came_from[path[-1]])
            return path[::-1]
        for nxt, edge in graph.neighbours(node):
            if edge.bridge in blocked or nxt in avoid:
                continue
            cost = g + edge.length_m / edge.speed_mult
            if cost < best.get(nxt, math.inf):
                best[nxt] = cost
                came_from[nxt] = node
                heapq.heappush(heap, (cost + graph.heuristic(nxt, goal), cost, nxt))
    return None
