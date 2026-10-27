"""NX-429 (Q-SIM-129): a repair crew picks its bridge's bank by route time (each road's
`length_m / speed_mult`, what the road search minimises), then route metres, then bank id, in the
job's reach test and dispatch (`logistics.approach`) and on a reroute (`bridges.reroute`) alike;
an unreachable bank is skipped.

Small graphs on strait-1's rules: bridge x carries t ~ u; the crew starts at s.
"""

import dataclasses
import math
from itertools import combinations, pairwise

import test_tasking as tt
from hypothesis import given, settings
from hypothesis import strategies as st
from test_bridges import NORTH

from nexus.core import bridges, tasking
from nexus.core.logistics import approach
from nexus.core.roads import Road, RoadGraph, route_time, shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Entity, Vec2, World, state_hash

RULES = tt.RULES
NONE: frozenset[str] = frozenset()


def _approach_rules(near_mult: float) -> Rules:
    """s - t is 1,000 m at `near_mult`; s - u is ~2,236 m at 1.0."""
    pos = {"s": (0, 0), "t": (1000, 0), "u": (1000, 2000), "x": (1000, 1000)}
    roads = RoadGraph(
        pos, [Road("s", "t", near_mult), Road("s", "u", 1.0), Road("t", "u", 1.0, "x")]
    )
    return dataclasses.replace(RULES, roads=roads)


def test_a_slow_road_to_the_near_bank_sends_the_crew_to_the_far_bank() -> None:
    """At speed_mult 1 bank t is nearer and quicker (1,000 s vs ~2,236 s); at 0.25 its road takes
    4,000 s, so the crew drives the longer, quicker road to u. This is the generator's reach test
    and the claimant's route (both `approach`)."""
    w = tt.new_world()
    assert approach(w, _approach_rules(1.0), "s", "x", avoid=NONE) == ["s", "t", "x"]
    assert approach(w, _approach_rules(0.25), "s", "x", avoid=NONE) == ["s", "u", "x"]


def test_an_unreachable_bank_is_skipped() -> None:
    """t is quicker, but entering it is refused: u; with u refused too, no route."""
    w = tt.new_world()
    rules = _approach_rules(1.0)
    assert approach(w, rules, "s", "x", avoid=frozenset({"t"})) == ["s", "u", "x"]
    assert approach(w, rules, "s", "x", avoid=frozenset({"t", "u"})) is None


def test_equal_times_break_by_metres_then_bank_id() -> None:
    """Banks a and b of bridge x, both reached in the same time. b is 1,414 m away at 1.0, a
    2,828 m at 2.0: fewer metres wins over the lower id (b). Mirrored at equal speed (same time,
    same metres): the lower id (a)."""
    w = tt.new_world()
    pos = {"s": (0, 0), "a": (2000, 2000), "b": (1000, -1000), "x": (1500, 500)}
    roads = RoadGraph(pos, [Road("s", "a", 2.0), Road("s", "b", 1.0), Road("a", "b", 1.0, "x")])
    assert route_time(roads, ["s", "a"]) == route_time(roads, ["s", "b"])  # a real time tie
    rules = dataclasses.replace(RULES, roads=roads)
    assert approach(w, rules, "s", "x", avoid=NONE) == ["s", "b", "x"]
    pos = {"s": (0, 0), "a": (1000, 1000), "b": (1000, -1000), "x": (1000, 0)}
    roads = RoadGraph(pos, [Road("s", "a", 1.0), Road("s", "b", 1.0), Road("a", "b", 1.0, "x")])
    rules = dataclasses.replace(RULES, roads=roads)
    assert approach(w, rules, "s", "x", avoid=NONE) == ["s", "a", "x"]
    assert bridges.quickest(rules, "s", ["b", "a"], NONE, NONE) == ["s", "a"]  # ends unsorted


def _reroute_rules(detour_mult: float) -> Rules:
    """s - t is the road over bridge y; s - e - t (2 x ~1,118 m at `detour_mult`) the detour to
    bank t; s - w - u (2 x ~1,414 m at 1.0) the road to bank u; bridge x carries t ~ u."""
    pos = {"s": (0, 0), "y": (500, 0), "t": (1000, 0), "e": (500, 1000), "x": (1500, 0),
           "u": (2000, 0), "w": (1000, -1000)}  # fmt: skip
    roads = RoadGraph(
        pos, [Road("s", "t", 1.0, "y"), Road("s", "e", detour_mult), Road("e", "t", detour_mult),
              Road("t", "u", 1.0, "x"), Road("s", "w", 1.0), Road("w", "u", 1.0)],
    )  # fmt: skip
    return dataclasses.replace(RULES, roads=roads)


def _rerouted(detour_mult: float) -> tuple[World, Entity]:
    """A crew on s -> t bound for bridge x's stop; bridges x and y fall and it reroutes."""
    w = tt.new_world()
    w.owner["e"] = "NEUTRAL"
    crew = tt.put(w, "LOGI_TRUCK", "haven")
    job = tt.post(w, "COALITION", "REPAIR_BRIDGE", NORTH, "repair")
    tasking.claim(w, crew, job, [])
    crew.pos, crew.last_node, crew.path = Vec2(200.0, 0.0), "s", ["t", "x"]
    w.bridge_down = {"x", "y"}
    bridges.reroute(w, _reroute_rules(detour_mult))
    return w, crew


def test_a_rerouted_crew_takes_the_quicker_bank() -> None:
    """At speed_mult 1 the detour to t (~2,236 m) beats the road to u (~2,828 m); at 0.25 it takes
    ~8,944 s, so the crew takes u."""
    assert _rerouted(1.0)[1].path == ["s", "e", "t", "x"]
    assert _rerouted(0.25)[1].path == ["s", "w", "u", "x"]


def test_the_bank_choice_is_deterministic() -> None:
    """Same inputs, same world: the reroute's state hash and the approach repeat exactly."""
    assert state_hash(_rerouted(0.25)[0]) == state_hash(_rerouted(0.25)[0])
    w = tt.new_world()
    runs = {tuple(approach(w, _approach_rules(0.25), "s", "x", avoid=NONE) or []) for _ in "ab"}
    assert runs == {("s", "u", "x")}


def test_route_time_adds_left_to_right_as_the_search_does() -> None:
    """Costs 1 + 1e16 + 1: the search's `g + cost` rounds each step (1e16 + 1 is 1e16, twice);
    compensated `sum()` would give 1e16 + 2, so a tie the search sees could break the other way."""
    pos = {"s": (0, 0), "a": (1000, 0), "b": (2000, 0), "c": (3000, 0)}
    big = 1000 / 1e16  # the speed_mult that makes a 1,000 m road cost 1e16
    graph = RoadGraph(pos, [Road("s", "a", 1000.0), Road("a", "b", big), Road("b", "c", 1000.0)])
    costs = [graph.edge(x, y).length_m / graph.edge(x, y).speed_mult for x, y in pairwise("sabc")]
    assert sum(costs) != costs[0] + costs[1] + costs[2]  # the case really differs
    assert route_time(graph, ["s", "a", "b", "c"]) == costs[0] + costs[1] + costs[2]


NODES = ("a", "b", "c", "s", "t", "u")
PAIRS = [p for p in combinations(NODES, 2) if p != ("t", "u")]  # t ~ u is bridge x's road


@settings(max_examples=200, deadline=None)
@given(
    xy=st.lists(
        st.tuples(st.integers(0, 5000), st.integers(0, 5000)), min_size=7, max_size=7, unique=True
    ),
    roads=st.dictionaries(st.sampled_from(PAIRS), st.floats(0.1, 3.0)),
    avoid=st.frozensets(st.sampled_from(["a", "b", "c", "t", "u"])),
)
def test_approach_takes_the_brute_force_quickest_bank(
    xy: list[tuple[int, int]], roads: dict[tuple[str, str], float], avoid: frozenset[str]
) -> None:
    """Random roads and speeds, bridge x down: `approach` drives the search's route to the bank
    with the lowest (time, metres, id), each key folded here edge by edge from the positions, and
    is None exactly when neither bank is reachable."""
    pos = dict(zip((*NODES, "x"), xy, strict=True))
    graph = RoadGraph(
        pos, [*(Road(a, b, m) for (a, b), m in roads.items()), Road("t", "u", 1.0, "x")]
    )
    w = tt.new_world()
    w.bridge_down = {"x"}
    keyed = []
    for bank in ("t", "u"):
        route = shortest_path(graph, "s", bank, blocked=frozenset({"x"}), avoid=avoid)
        if route is None:
            continue
        time, metres = 0.0, 0.0
        for a, b in pairwise(route):
            (ax, ay), (bx, by) = pos[a], pos[b]
            length = math.hypot(bx - ax, by - ay)
            time, metres = time + length / roads[min(a, b), max(a, b)], metres + length
        keyed.append((time, metres, bank, route))
    got = approach(w, dataclasses.replace(RULES, roads=graph), "s", "x", avoid=avoid)
    if not keyed:
        assert got is None
    else:
        assert got is not None and got[-1] == "x"
        assert got[:-1] == min(keyed, key=lambda k: k[:3])[3]
