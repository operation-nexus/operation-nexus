"""NX-410: a repair crew's road to a bridge's repair stop enters no node the other side holds
(Q-SIM-125, the supply runs' rule since NX-407 / Q-SIM-122; neutral ground stays passable), and
the REPAIR_BRIDGE job is not posted when no live carrier has such a road.

strait-1: bridge-n carries fob-n-w ~ cross-n, bridge-s fob-s-w ~ cross-s; east-airbase (ENEMY)
joins cross-n and cross-s. From cross-s the short road to bridge-n's banks runs through it.
"""

import dataclasses
from itertools import pairwise

import test_tasking as tt
from hypothesis import given, settings
from hypothesis import strategies as st
from test_bridge_repair import _jobs
from test_bridges import NORTH, SOUTH, cut

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import bridges, tasking
from nexus.core.logistics import approach
from nexus.core.roads import Road, RoadGraph
from nexus.core.step import step
from nexus.core.world import Vec2, World, state_hash

RULES = tt.RULES
TRUCK: UnitKind = "LOGI_TRUCK"
FOE = "east-airbase"
WEST = ["cross-s", "fob-s-w", "west-airbase", "fob-n-w", NORTH]  # bridge-n's stop round the west


def _crew_at_cross_s(w: World) -> None:
    """The only coalition carrier, at neutral cross-s (fob-s-w's crews are elsewhere)."""
    tt.put(w, TRUCK, "cross-s")


def test_no_repair_job_is_posted_when_the_only_road_crosses_enemy_ground() -> None:
    """Both bridges down: from cross-s, bridge-n's banks lie only past east-airbase, so its job is
    not posted; bridge-s's bank is cross-s itself, so that one is."""
    w = tt.new_world()
    cut(w, NORTH, SOUTH)
    _crew_at_cross_s(w)
    tt.board_pass(w)
    assert [j.node for j in _jobs(w, "REPAIR_BRIDGE")] == [SOUTH]


def test_a_neutral_node_on_the_road_stays_passable() -> None:
    """east-airbase neutral: the crew's road through it is allowed, and bridge-n's job posts."""
    w = tt.new_world()
    w.owner[FOE] = "NEUTRAL"
    cut(w, NORTH, SOUTH)
    _crew_at_cross_s(w)
    tt.board_pass(w)
    assert [j.node for j in _jobs(w, "REPAIR_BRIDGE")] == [NORTH, SOUTH]
    assert approach(w, RULES, "cross-s", NORTH, side="COALITION") == [
        "cross-s", FOE, "cross-n", NORTH,
    ]  # fmt: skip


def test_a_claimed_crew_routes_round_enemy_ground_when_an_alternative_exists() -> None:
    """Only bridge-n down: the old nearer bank (cross-n, past east-airbase) is refused, so the
    crew drives round by the west to fob-n-w."""
    w = tt.new_world()
    cut(w, NORTH)
    assert approach(w, RULES, "cross-s", NORTH, side=None) == ["cross-s", FOE, "cross-n", NORTH]
    crew = tt.put(w, TRUCK, "cross-s")
    job = tt.post(w, "COALITION", "REPAIR_BRIDGE", NORTH, "repair")
    assert tasking._feasible(w, RULES, {}, crew, job) == "ok"
    tasking.claim(w, crew, job, [])
    tasking._dispatch(w, RULES, {}, crew, job)
    assert crew.path == WEST


def test_a_crew_is_not_sent_when_its_only_road_crosses_enemy_ground() -> None:
    w = tt.new_world()
    cut(w, NORTH, SOUTH)
    crew = tt.put(w, TRUCK, "cross-s")
    job = tt.post(w, "COALITION", "REPAIR_BRIDGE", NORTH, "repair")
    assert tasking._feasible(w, RULES, {}, crew, job) == "no"


def test_a_crew_rerouted_by_a_cut_never_drives_through_enemy_ground() -> None:
    """`bridges.reroute` on a small graph (on strait-1 a cut that turns a crew back also cuts it
    off from its bank): s - y - t is the road, y a bridge, s - e - t the detour; the crew on s -> t
    heads for bridge x's stop past bank t. y falls: with e enemy-held it stops at s; with e
    neutral it takes the detour."""
    pos = {"s": (0, 0), "y": (500, 0), "t": (1000, 0), "e": (500, 1000), "x": (1500, 0),
           "u": (2000, 0)}  # fmt: skip
    roads = RoadGraph(
        pos, [Road("s", "t", 1.0, "y"), Road("s", "e", 1.0), Road("e", "t", 1.0),
              Road("t", "u", 1.0, "x")],
    )  # fmt: skip
    rules = dataclasses.replace(RULES, roads=roads)
    cases = (
        ("ENEMY", "NEUTRAL", ["s"]),
        ("NEUTRAL", "NEUTRAL", ["s", "e", "t", "x"]),
        ("NEUTRAL", "ENEMY", ["s"]),
    )  # the last: the bank itself is enemy-held, not exempt
    for owner, bank, path in cases:  # fmt: skip
        w = tt.new_world()
        w.owner["e"] = owner  # type: ignore[assignment]  # a str literal; the dict holds NodeOwner
        w.owner["t"] = bank  # type: ignore[assignment]  # as above
        crew = tt.put(w, TRUCK, "haven")
        job = tt.post(w, "COALITION", "REPAIR_BRIDGE", NORTH, "repair")
        tasking.claim(w, crew, job, [])
        crew.pos, crew.last_node, crew.path = Vec2(200.0, 0.0), "s", ["t", "x"]
        w.bridge_down = {"x", "y"}
        bridges.reroute(w, rules)
        assert crew.path == path, (owner, bank)


@settings(max_examples=60, deadline=None)
@given(
    owners=st.lists(st.sampled_from(["COALITION", "ENEMY", "NEUTRAL"]), min_size=5, max_size=5),
    down=st.sets(st.sampled_from([NORTH, SOUTH]), min_size=1),
)
def test_a_repair_approach_never_enters_an_enemy_held_node(
    owners: list[str], down: set[str]
) -> None:
    w = tt.new_world()
    nodes = ["cross-n", "cross-s", FOE, "fob-n-w", "fob-s-w"]
    for node, owner in zip(nodes, owners, strict=True):
        w.owner[node] = owner  # type: ignore[assignment]  # sampled str; the dict holds NodeOwner
    cut(w, *sorted(down))
    for start in sorted(n for n in RULES.roads.pos if n not in RULES.roads.spans):
        for bridge in sorted(down):
            route = approach(w, RULES, start, bridge, side="COALITION")
            if route is None:
                continue
            assert all(w.owner.get(n) != "ENEMY" for n in route[1:-1]), (start, bridge)
            assert not {RULES.roads.edge(a, b).bridge for a, b in pairwise(route[:-1])} & down


def test_the_crew_detour_world_is_deterministic() -> None:
    def play() -> tuple[str, list[Event]]:
        w = tt.new_world(seed=7)
        cut(w, NORTH)
        tt.put(w, TRUCK, "cross-s")
        tt.put(w, TRUCK, "fob-s-w")
        events: list[Event] = []
        for _ in range(4 * tt.EVERY):
            events += step(w, [])
        return state_hash(w), events

    assert play() == play()
