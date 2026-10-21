"""NX-120: road graph and A* (GAMEPLAY §5 cost = length / speed_mult; SIM-CORE §4 Edge)."""

import math
from itertools import pairwise

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.core.roads import Road, RoadGraph, edge_id, shortest_path

NONE: frozenset[str] = frozenset()
# A 3-4-5 triangle: a-b and b-c are 5 m each, a-c is 6 m.
TRIANGLE = {"a": (0, 0), "b": (3, 4), "c": (6, 0)}


def triangle(ac_speed_mult: float) -> RoadGraph:
    roads = [Road("a", "b", 1.0, "br"), Road("b", "c", 1.0), Road("c", "a", ac_speed_mult)]
    return RoadGraph(TRIANGLE, roads)


def test_cost_is_length_over_speed_mult() -> None:
    # a-c direct costs 6 / 0.5 = 12 > 10 via b; at 2.0 it costs 3 < 10.
    assert shortest_path(triangle(0.5), "a", "c", blocked=NONE) == ["a", "b", "c"]
    assert shortest_path(triangle(2.0), "a", "c", blocked=NONE) == ["a", "c"]


def test_blocked_bridge_removes_its_edge() -> None:
    assert shortest_path(triangle(0.5), "a", "c", blocked=frozenset({"br"})) == ["a", "c"]
    assert shortest_path(triangle(0.5), "a", "b", blocked=frozenset({"br"})) == ["a", "c", "b"]


def test_unreachable_trivial_and_unknown() -> None:
    graph = RoadGraph({"a": (0, 0), "b": (1, 0), "z": (9, 9)}, [Road("a", "b", 1.0, "br")])
    assert shortest_path(graph, "a", "z", blocked=NONE) is None
    assert shortest_path(graph, "a", "b", blocked=frozenset({"br"})) is None
    assert shortest_path(graph, "a", "a", blocked=NONE) == ["a"]
    with pytest.raises(ValueError, match="unknown node 'q'"):
        shortest_path(graph, "a", "q", blocked=NONE)


def test_equal_cost_tie_breaks_on_node_id() -> None:
    square = {"a": (0, 0), "n": (0, 10), "m": (10, 0), "z": (10, 10)}
    roads = [Road("a", "n", 1.0), Road("n", "z", 1.0), Road("a", "m", 1.0), Road("m", "z", 1.0)]
    assert shortest_path(RoadGraph(square, roads), "a", "z", blocked=NONE) == ["a", "m", "z"]


def test_edge_id_sorts_nodes_and_duplicates_fail() -> None:
    assert edge_id("west", "east") == "east~west~ROAD"
    for roads in ([Road("a", "b", 1.0), Road("b", "a", 2.0)], [Road("a", "a", 1.0)]):
        with pytest.raises(ValueError, match="self-loop or duplicate road"):
            RoadGraph(TRIANGLE, roads)
    with pytest.raises(ValueError, match="road a~q has an unknown endpoint"):
        RoadGraph(TRIANGLE, [Road("a", "q", 1.0)])


def dijkstra(costs: dict[tuple[str, str], float], nodes: list[str], start: str) -> dict[str, float]:
    """Reference distances: plain O(n^2) Dijkstra over an undirected cost table."""
    dist = {n: math.inf for n in nodes}
    dist[start] = 0.0
    todo = set(nodes)
    while todo:
        u = min(todo, key=lambda n: (dist[n], n))
        todo.remove(u)
        for (x, y), c in costs.items():
            for p, q in ((x, y), (y, x)):
                if p == u and dist[u] + c < dist[q]:
                    dist[q] = dist[u] + c
    return dist


graphs = st.integers(2, 7).flatmap(
    lambda n: st.tuples(
        st.lists(st.tuples(st.integers(0, 1000), st.integers(0, 1000)), min_size=n, max_size=n),
        st.dictionaries(
            st.tuples(st.integers(0, n - 1), st.integers(0, n - 1)).filter(lambda p: p[0] < p[1]),
            st.tuples(st.floats(0.1, 10.0), st.booleans()),
        ),
        st.integers(0, n - 1),
        st.integers(0, n - 1),
    )
)


@given(graphs)
def test_a_star_matches_dijkstra(
    case: tuple[list[tuple[int, int]], dict[tuple[int, int], tuple[float, bool]], int, int],
) -> None:
    points, edges, s, g = case
    pos = {f"n{i}": p for i, p in enumerate(points)}
    roads = [Road(f"n{i}", f"n{j}", m, f"br{i}-{j}") for (i, j), (m, _) in sorted(edges.items())]
    blocked = frozenset(f"br{i}-{j}" for (i, j), (_, cut) in edges.items() if cut)
    open_costs = {
        (r.a, r.b): math.dist(pos[r.a], pos[r.b]) / r.speed_mult
        for r in roads
        if r.bridge not in blocked
    }
    expected = dijkstra(open_costs, sorted(pos), f"n{s}")[f"n{g}"]

    path = shortest_path(RoadGraph(pos, roads), f"n{s}", f"n{g}", blocked=blocked)

    if path is None:
        assert expected == math.inf
        return
    assert (path[0], path[-1]) == (f"n{s}", f"n{g}")
    steps = [open_costs.get((p, q), open_costs.get((q, p))) for p, q in pairwise(path)]
    assert None not in steps  # every hop is an open edge
    assert math.isclose(sum(c for c in steps if c is not None), expected, abs_tol=1e-9)
