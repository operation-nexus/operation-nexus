"""NX-373 parts 1a and 1b: bridge hp, STRUCTURE fire on a bridge, the cut road, `BridgeDestroyed`
and the reroute of paths already set (STATE-MACHINES §4.3 B-1 and B-2, GAMEPLAY §5, COMBAT CB-10,
Q-SIM-105..108).

Shipped strait-1 numbers: bridge-n (200 km, 60 km) carries fob-n-w~cross-n and bridge-s (200 km,
180 km) fob-s-w~cross-s; `logistics.bridge_hp` 300; AG_LIGHT does 50 damage at 10 km, 300 m/s
(0.6 world s per tick, so 9 km is a 50-tick flight). Combat worlds are built by hand with the board
off (`test_combat`): a STRIKE claim is set by hand on the side's board.
"""

import dataclasses
from collections.abc import Callable
from itertools import pairwise

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_combat import ARMOR, CONFIG, JET, RULES, TRUCK, new_world, of, put, run, sure, track

from nexus.contracts.gen.commands.join import NodeTarget
from nexus.contracts.gen.common.enums import JobKind
from nexus.contracts.gen.events.bridge_destroyed import BridgeDestroyed
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core import bridges, follow, handlers, launch, tasking
from nexus.core.combat import _pick_node
from nexus.core.combat import validate as combat_validate
from nexus.core.logistics import nearest, plan_run
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Claim, Entity, Job, Vec2, World, load, save, state_hash

POS = RULES.roads.pos
NORTH, SOUTH = "bridge-n", "bridge-s"
BRIDGES = (NORTH, SOUTH)
MAX_HP = 300
BANKS = [n for n, k in RULES.node_kind.items() if k != "BRIDGE"]
SURE = sure("AG_LIGHT")


def strike(w: World, e: Entity, node: str, kind: JobKind = "STRIKE") -> Job:
    """`e` holds a claim on a job of `kind` at `node` on its side's board."""
    job = Job(w.next_job_id(), kind, f"strike:{node}", 2, 1000, 0, node=node)
    job.claims[e.id] = Claim(0, active=True)
    w.boards[e.side][job.id] = job
    e.job_id = job.id
    return job


def jet_at(w: World, node: str = NORTH, dx: float = 0.0) -> Entity:
    x, y = POS[node]
    return put(w, JET, "COALITION", x + dx, y, cmd=1)


def bridge_shots(events: list[Event]) -> list[WeaponFired]:
    return [e for e in of(events, WeaponFired) if e.target_node_id in BRIDGES]


def cut(w: World, *nodes: str) -> None:
    for n in nodes:
        w.bridge_hp[n] = 0
        w.bridge_down.add(n)


def bridges_on(path: list[str]) -> set[str | None]:
    return {RULES.roads.edge(a, b).bridge for a, b in pairwise(path)}


# --- state ------------------------------------------------------------------------------------


def test_every_bridge_starts_full_and_is_not_a_capture_defense() -> None:
    w = new_world()
    assert w.bridge_hp == {NORTH: MAX_HP, SOUTH: MAX_HP} and w.bridge_down == set()
    assert NORTH not in w.defense_hp and SOUTH not in w.defense_hp


# --- who fires (Q-SIM-105) --------------------------------------------------------------------


def test_a_strike_claimant_on_the_bridge_shoots_it() -> None:
    w = new_world(SURE)
    jet = jet_at(w)
    strike(w, jet, NORTH)
    events = run(w)
    (fired,) = of(events, WeaponFired)
    assert (fired.shooter_id, fired.target_id, fired.target_node_id) == (jet.id, None, NORTH)
    (impact,) = of(events, WeaponImpact)
    assert impact.hit and impact.target_node_id == NORTH
    assert w.bridge_hp[NORTH] == MAX_HP - 50 and w.bridge_hp[SOUTH] == MAX_HP
    assert of(events, BridgeDestroyed) == [] and w.bridge_down == set()


@pytest.mark.parametrize(
    "claim",
    [
        None,  # no job at all
        ("STRIKE", "fob-n-e"),  # a strike on another node
        ("SCOUT", NORTH),  # a job on the bridge that is not a strike
    ],
)
def test_a_unit_without_a_strike_claim_on_the_bridge_never_shoots_it(
    claim: tuple[JobKind, str] | None,
) -> None:
    w = new_world(SURE)
    jet = jet_at(w)
    if claim is not None:
        strike(w, jet, claim[1], claim[0])
    assert of(run(w, 30), WeaponFired) == [] and w.bridge_hp[NORTH] == MAX_HP


def test_the_automatic_fallback_never_picks_a_bridge() -> None:
    w = new_world(SURE)
    jet = jet_at(w)
    combat = SURE.combat
    assert combat is not None
    weapon = combat.weapons["AG_LIGHT"]
    for node in BRIDGES:
        x, y = POS[node]
        jet.pos = Vec2(x, y)
        assert _pick_node(w, SURE, weapon, jet, frozenset()) is None


def test_units_come_first_and_the_bridge_must_be_in_range() -> None:
    w = new_world(SURE)
    jet = jet_at(w)
    strike(w, jet, NORTH)
    armor = put(w, ARMOR, "ENEMY", POS[NORTH][0] + 2_000, POS[NORTH][1])
    track(w, jet, armor)
    (fired,) = of(run(w), WeaponFired)
    assert fired.target_id == armor.id and w.bridge_hp[NORTH] == MAX_HP
    far = new_world(SURE)
    strike(far, jet_at(far, dx=10_001), NORTH)  # AG_LIGHT reaches 10 km
    assert of(run(far, 30), WeaponFired) == []


# --- destruction ------------------------------------------------------------------------------


def test_the_hit_that_takes_it_to_zero_destroys_it_once_and_names_the_shooter() -> None:
    w = new_world(SURE)
    jet = jet_at(w)
    strike(w, jet, NORTH)
    w.bridge_hp[NORTH] = 50
    events = run(w, 60)  # long enough for more reloads: no shot at a bridge with no hp
    (down,) = of(events, BridgeDestroyed)
    assert (down.node_id, down.by_id) == (NORTH, jet.id)
    assert len(bridge_shots(events)) == 1
    assert w.bridge_hp[NORTH] == 0 and w.bridge_down == {NORTH}


def test_a_hit_landing_at_zero_hp_fizzles() -> None:
    w = new_world(SURE)
    first, second = jet_at(w), jet_at(w)
    strike(w, first, NORTH)
    strike(w, second, NORTH)
    w.bridge_hp[NORTH] = 50
    events = run(w)
    assert [s.shooter_id for s in bridge_shots(events)] == [first.id, second.id]
    assert [(i.shooter_id, i.hit) for i in of(events, WeaponImpact)] == [
        (first.id, True),
        (second.id, False),
    ]
    assert [d.by_id for d in of(events, BridgeDestroyed)] == [first.id]
    assert w.bridge_hp[NORTH] == 0


def test_damage_never_goes_below_zero_and_announces_once() -> None:
    w = new_world()
    out: list[Event] = []
    for _ in range(3):
        bridges.damage(w, RULES, SOUTH, 200, 7, out)
    assert w.bridge_hp[SOUTH] == 0 and [e.by_id for e in of(out, BridgeDestroyed)] == [7]


def test_bridge_fire_is_deterministic() -> None:
    def once() -> tuple[str, list[str]]:
        w = new_world(RULES)  # the shipped Pk: hits and misses come from the combat stream
        for dx in (0.0, 3_000.0, 9_000.0):
            strike(w, jet_at(w, dx=dx), NORTH)
        events = run(w, 200)
        return state_hash(w), [e.model_dump_json() for e in events]

    a, b = once(), once()
    assert a == b and any("BridgeDestroyed" in e or "WeaponImpact" in e for e in a[1])


# --- the STRIKE verdict -----------------------------------------------------------------------


def test_a_strike_on_a_bridge_is_done_only_once_the_bridge_is_down() -> None:
    import test_tasking as tt

    w = tt.new_world()
    jet = tt.put(w, JET, "west-airbase")
    job = tt.post(w, "COALITION", "STRIKE", NORTH, "b", slots=1)
    tasking.claim(w, jet, job, [])
    jet.path, jet.state = [NORTH], "EN_ROUTE"
    first = tt.board_pass(w)
    assert of(first, JobDone) == [] and job.id in w.boards["COALITION"]
    w.bridge_hp[NORTH] = 100
    assert of(tt.board_pass(w), JobDone) == []  # damaged, not down
    cut(w, NORTH)
    (done,) = of(tt.board_pass(w), JobDone)
    assert done.job_id == job.id and job.id not in w.boards["COALITION"]


# --- the cut road (B-1) -----------------------------------------------------------------------


def test_after_the_cut_a_route_between_the_banks_avoids_the_edge() -> None:
    w = new_world()
    assert NORTH in bridges_on(nearest(w, RULES, "fob-n-w", ["cross-n"])[1])  # type: ignore[index]
    cut(w, NORTH)
    found = nearest(w, RULES, "fob-n-w", ["cross-n"])
    assert found is not None and found[1][0] == "fob-n-w" and found[1][-1] == "cross-n"
    assert bridges_on(found[1]) == {None, SOUTH}
    cut(w, SOUTH)
    assert nearest(w, RULES, "fob-n-w", ["cross-n"]) is None
    assert plan_run(w, RULES, "COALITION", "cross-n") is None


def _planner_paths(w: World, rules: Rules, a: str, b: str) -> list[list[str] | None]:
    """The route every planner finds from `a` to `b` (None: none), each through its own code."""
    out: list[list[str] | None] = []
    found = nearest(w, rules, a, [b])  # logistics, capture escape, rebase
    out.append(None if found is None else found[1])
    out.append(tasking._road(w, rules, {}, a, b))  # the board
    unit = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(*POS[a]))
    unit.last_node = unit.home = a
    if follow._approach(w, rules, unit, Vec2(*POS[b])):  # an escort's greedy leg toward a threat
        out.append([a, *(str(p) for p in unit.path)])
    unit.path = []
    patrol = Job(w.next_job_id(), "PATROL", f"patrol:{b}", 1, 1000, 0, node=b)
    out.append(tasking._patrol_route(w, rules, {}, unit, patrol))  # a patrol through held nodes
    follow._drive(w, rules, unit, b)  # a follower
    out.append([str(p) for p in unit.path] or None)
    unit.path, unit.home = [], b
    launch._recall(w, rules, "ENEMY")  # a garrison unit sent home
    out.append([str(p) for p in unit.path] or None)
    w.remove(unit.id)
    return out


@settings(max_examples=40, deadline=None)
@given(
    down=st.sets(st.sampled_from(BRIDGES)),
    pair=st.tuples(st.sampled_from(BANKS), st.sampled_from(BANKS)).filter(lambda p: p[0] != p[1]),
)
def test_no_planner_routes_over_a_cut_bridge(down: set[str], pair: tuple[str, str]) -> None:
    w = new_world()
    w.owner = {n: "ENEMY" for n in w.owner}  # recall and patrol need nodes their side holds
    cut(w, *sorted(down))
    a, b = pair
    paths = _planner_paths(w, RULES, a, b)
    for path in paths:
        assert path is None or not (bridges_on([str(p) for p in path]) & down)
    if not down:
        assert all(p is not None for p in paths)  # every bank node is reachable (TH-3)


def test_an_escort_never_approaches_a_threat_over_a_cut_bridge() -> None:
    w = new_world()
    escort = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(*POS["fob-n-w"]))
    escort.last_node = "fob-n-w"
    past = Vec2(POS["cross-n"][0] + 1_000, POS["cross-n"][1])  # a threat beyond the north bridge
    assert follow._approach(w, RULES, escort, past) and escort.path == ["cross-n"]
    escort.path = []
    cut(w, NORTH)
    moved = follow._approach(w, RULES, escort, past)
    assert not moved or NORTH not in bridges_on(["fob-n-w", *(str(p) for p in escort.path)])


def test_a_join_route_avoids_a_cut_bridge() -> None:
    no_deploy = dataclasses.replace(
        RULES, supply=dataclasses.replace(RULES.supply, spawns={})
    )  # no forward deploy: the JOIN leaves the sanctuary by road
    w = new_world(no_deploy)
    target = NodeTarget(node_id="cross-n")
    plan = handlers._route(w, target=target, kind="GARRISON_INFANTRY", rules=no_deploy)
    assert not isinstance(plan, str) and NORTH in bridges_on([str(p) for p in plan.path])
    cut(w, NORTH)
    plan = handlers._route(w, target=target, kind="GARRISON_INFANTRY", rules=no_deploy)
    assert not isinstance(plan, str) and bridges_on([str(p) for p in plan.path]) == {None, SOUTH}
    cut(w, SOUTH)
    assert handlers._route(w, target=target, kind="GARRISON_INFANTRY", rules=no_deploy) == (
        "NODE_INVALID_FOR_UNIT"
    )


# --- paths already set (part 1b, Q-SIM-108) ---------------------------------------------------


def truck(w: World, x: float, y: float, last: str, path: list[str]) -> Entity:
    """A coalition truck at (x, y) that last reached `last`, driving `path`."""
    e = put(w, TRUCK, "COALITION", x, y)
    e.last_node, e.path = last, [*path]
    return e


def fall(w: World, *nodes: str) -> list[Event]:
    """Bring each bridge down with one hit (the reroute runs from `damage`)."""
    out: list[Event] = []
    for n in nodes:
        bridges.damage(w, RULES, n, MAX_HP, 1, out)
    return out


def test_a_truck_short_of_the_cut_turns_back_and_takes_the_other_bridge() -> None:
    w = new_world()
    e = truck(w, 150_000, 60_000, "fob-n-w", ["cross-n", "fob-n-e"])
    fall(w, NORTH)
    path = [str(p) for p in e.path]
    assert path[0] == "fob-n-w" and path[-1] == "fob-n-e"
    assert bridges_on(path) == {None, SOUTH}
    run(w, 3)
    assert e.pos.x < 150_000 and e.pos.y == 60_000  # it drives back toward fob-n-w


def test_a_truck_at_or_past_the_cut_carries_on() -> None:
    w = new_world()
    past = truck(w, 210_000, 60_000, "fob-n-w", ["cross-n", "fob-n-e"])
    at = truck(w, *POS[NORTH], "fob-n-w", ["cross-n"])
    hp = at.hp
    fall(w, NORTH)
    assert past.path == ["cross-n", "fob-n-e"] and at.path == ["cross-n"]
    assert at.hp == hp  # no damage to a unit on the falling bridge


def test_with_both_bridges_down_a_truck_stops_at_its_bank_node() -> None:
    w = new_world()
    e = truck(w, 150_000, 60_000, "fob-n-w", ["cross-n", "fob-n-e"])
    fall(w, SOUTH, NORTH)
    assert e.path == ["fob-n-w"]


def test_a_truck_turned_back_over_the_cut_heads_for_its_own_bank() -> None:
    w = new_world()  # it left fob-n-w, crossed, and was turned back toward it: east of the cut
    e = truck(w, 210_000, 60_000, "fob-n-w", ["fob-n-w", "west-airbase"])
    fall(w, NORTH)
    path = [str(p) for p in e.path]
    assert path[0] == "cross-n" and path[-1] == "west-airbase" and NORTH not in bridges_on(path)


def test_a_later_hop_over_the_cut_replans_from_the_node_before_it() -> None:
    w = new_world()
    x = (POS["west-airbase"][0] + POS["fob-n-w"][0]) / 2
    y = (POS["west-airbase"][1] + POS["fob-n-w"][1]) / 2
    e = truck(w, x, y, "west-airbase", ["fob-n-w", "cross-n", "fob-n-e"])
    other = truck(w, x, y, "west-airbase", ["fob-n-w"])  # its road crosses no bridge
    fall(w, NORTH)
    rest = shortest_path(RULES.roads, "fob-n-w", "fob-n-e", blocked=frozenset({NORTH}))
    assert rest is not None and e.path == rest  # the prefix up to fob-n-w, then the new route
    assert other.path == ["fob-n-w"]
    w2 = new_world()
    e2 = truck(w2, x, y, "west-airbase", ["fob-n-w", "cross-n", "fob-n-e"])
    cut(w2, NORTH, SOUTH)
    bridges.reroute(w2, RULES)
    assert e2.path == ["fob-n-w"]  # no route: it stops at the node before the cut
    fall(w, SOUTH)  # the south falls later: the new route stops short of it
    assert e.path == ["fob-n-w", "west-airbase", "fob-s-w"]


def test_a_later_hop_is_cut_wherever_the_unit_stands() -> None:
    w = new_world()  # west of the cut, yet its road comes back west over it from the east bank
    tour = ["west-airbase", "fob-s-w", "cross-s", "east-airbase", "cross-n", "fob-n-w"]
    e = truck(w, 50_000, 120_000, "haven", tour)
    fall(w, NORTH)
    path = [str(p) for p in e.path]
    assert path[:5] == tour[:5] and path[-1] == "fob-n-w" and NORTH not in bridges_on(path)


def test_a_unit_at_a_node_bound_over_the_cut_replans_from_it() -> None:
    w = new_world()
    e = truck(w, *POS["fob-n-w"], "fob-n-w", ["fob-n-w", "cross-n"])
    fall(w, NORTH)
    assert e.path[0] == "fob-n-w" and NORTH not in bridges_on([str(p) for p in e.path])
    assert e.path[-1] == "cross-n"


def test_a_coalition_patrol_replans_through_held_nodes_only() -> None:
    board_on = dataclasses.replace(CONFIG.rules, campaign=None, track_every_ticks=10**9)
    w = new_world(board_on)
    for n in ("cross-n", "cross-s"):
        w.owner[n] = "COALITION"
    e = put(w, ARMOR, "COALITION", 150_000, 60_000, cmd=1)
    e.last_node, e.path = "fob-n-w", ["cross-n"]
    job = Job(w.next_job_id(), "PATROL", "patrol:cross-n", 2, 1000, 0, node="cross-n")
    job.claims[e.id] = Claim(0, active=True)
    w.boards["COALITION"][job.id] = job
    e.job_id = job.id
    bridges.damage(w, board_on, NORTH, MAX_HP, 1, [])
    assert e.path == ["fob-n-w"]  # the only way round runs through east-airbase (ENEMY)
    for _ in range(2_000):  # 20 km back to fob-n-w at the armor's speed, and on
        run(w)
        assert {e.last_node, *map(str, e.path)} <= {
            n for n, o in w.owner.items() if o == "COALITION"
        }
        assert e.path or e.pos == Vec2(*POS[str(e.last_node)])  # never stranded mid-road
    assert e.last_node == "fob-n-w"


def _patrol_unit(x: float, last: str, path: list[str]) -> tuple[World, Entity]:
    w = new_world(dataclasses.replace(CONFIG.rules, campaign=None, track_every_ticks=10**9))
    for n in ("cross-n", "cross-s"):
        w.owner[n] = "COALITION"
    e = put(w, ARMOR, "COALITION", x, 60_000, cmd=1)
    e.last_node, e.path = last, [*path]
    job = Job(w.next_job_id(), "PATROL", "patrol:cross-n", 2, 1000, 0, node="cross-n")
    job.claims[e.id] = Claim(0, active=True)
    w.boards["COALITION"][job.id] = job
    e.job_id = job.id
    return w, e


def test_a_patrol_lost_mid_edge_sends_the_unit_back_to_the_node_it_left_not_to_stand() -> None:
    """Q-SIM-109: its node falls while a ground unit is on the road: it is never stranded there."""
    w, e = _patrol_unit(150_000, "fob-n-w", ["cross-n"])
    w.owner["cross-n"] = "ENEMY"
    held = {n for n, o in w.owner.items() if o == "COALITION"}
    back = False
    for _ in range(2_000):
        run(w)
        assert {e.last_node, *map(str, e.path)} <= held  # never enters the lost node
        back |= e.pos == Vec2(*POS["fob-n-w"])
    assert back  # it reached a node, where the board can task it again


def test_a_patrol_lost_mid_edge_with_no_held_end_stops_the_unit_rather_than_enter_one() -> None:
    w, e = _patrol_unit(150_000, "fob-n-w", ["cross-n"])
    w.owner["fob-n-w"] = w.owner["cross-n"] = "ENEMY"
    run(w)
    assert e.job_id is None and not e.path and e.pos == Vec2(150_000, 60_000)


def _abandon(w: World, e: Entity) -> None:
    """Fail the unit's patrol the way `_end` does, with the route ending at the job's node."""
    tasking._abandon_patrol(w, RULES, e, w.boards["COALITION"][e.job_id or 0])


def test_a_patrol_lost_mid_edge_with_the_node_behind_lost_goes_on_to_the_node_ahead() -> None:
    w, e = _patrol_unit(150_000, "fob-n-w", ["cross-n"])
    w.owner["fob-n-w"] = "ENEMY"
    _abandon(w, e)
    assert e.path == ["cross-n"]


def test_a_patrol_lost_mid_edge_with_both_ends_held_goes_back_to_the_node_it_left() -> None:
    w, e = _patrol_unit(150_000, "fob-n-w", ["cross-n"])
    w.owner["fob-n-w"] = "COALITION"
    _abandon(w, e)
    assert e.path == ["fob-n-w"]


def test_a_failed_patrol_aircraft_is_not_sent_to_the_node_it_left() -> None:
    w, e = _patrol_unit(150_000, "fob-n-w", ["cross-n"])
    jet = put(w, JET, "COALITION", 150_000, 60_000, cmd=2)
    jet.last_node, jet.path, jet.state, jet.job_id = "fob-n-w", ["cross-n"], "EN_ROUTE", e.job_id
    w.owner["fob-n-w"] = "COALITION"
    for n in ("west-airbase", "haven"):
        w.owner[n] = (
            "ENEMY"  # no landing base: go_home leaves the route, which ends at the job node
        )
    _abandon(w, jet)
    assert jet.path == []


def test_a_patrol_lost_while_the_unit_stands_on_a_node_stops_it_there() -> None:
    w, e = _patrol_unit(120_000, "cross-s", ["cross-n"])
    e.pos = Vec2(*POS["cross-s"])
    w.owner["cross-n"] = "ENEMY"
    run(w)
    assert e.job_id is None and not e.path and e.pos == Vec2(*POS["cross-s"])


def test_a_mid_edge_patrol_failure_replays_identically() -> None:
    def hashes() -> list[str]:
        w, _ = _patrol_unit(150_000, "fob-n-w", ["cross-n"])
        w.owner["cross-n"] = "ENEMY"
        out = []
        for _ in range(300):
            run(w)
            out.append(state_hash(w))
        return out

    assert hashes() == hashes() and len(set(hashes())) > 1


def test_only_a_patrol_keeps_to_held_nodes() -> None:
    w = new_world()
    e = truck(w, 150_000, 60_000, "fob-n-w", ["cross-n", "fob-n-e"])
    strike(w, e, "fob-n-e")  # any other job, `via` unset too: the plain road search
    fall(w, NORTH)
    assert e.path[-1] == "fob-n-e" and SOUTH in bridges_on([str(p) for p in e.path])


def test_a_static_patrol_drops_its_via_and_takes_the_plain_route_home() -> None:
    w = new_world()
    e = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(150_000, 60_000))
    e.last_node, e.path = "fob-n-w", ["cross-n", "east-airbase"]  # back from its turn at fob-n-w
    job = Job(w.next_job_id(), "PATROL", "patrol:east-airbase", 1, 1000, 0, node="east-airbase")
    job.via = "fob-n-w"
    job.claims[e.id] = Claim(0, active=True)
    w.boards["ENEMY"][job.id] = job
    e.job_id = job.id
    fall(w, NORTH)
    path = [str(p) for p in e.path]
    assert path[0] == "fob-n-w" and path[-1] == "east-airbase"
    assert bridges_on(path) == {None, SOUTH}  # through coalition nodes: no held-only avoid


def test_aircraft_paths_are_never_rerouted() -> None:
    w = new_world()
    jet = jet_at(w, "fob-n-w")
    jet.state, jet.path, jet.last_node = "EN_ROUTE", ["cross-n"], "fob-n-w"
    fall(w, NORTH)
    assert jet.path == ["cross-n"]


def test_a_follower_on_the_near_bank_never_routes_over_the_cut() -> None:
    w = new_world()
    f = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(150_000, 60_000))
    f.last_node, f.path = "fob-n-w", ["cross-n"]
    assert follow._ends(w, RULES, f) == ["cross-n", "fob-n-w"]
    cut(w, NORTH)
    assert follow._ends(w, RULES, f) == ["fob-n-w"]
    assert follow._drive(w, RULES, f, "fob-n-e")
    assert f.path[0] == "fob-n-w" and NORTH not in bridges_on([str(p) for p in f.path])
    f.path = ["fob-n-w"]  # turned back: the end ahead is found by position
    assert follow._ends(w, RULES, f) == ["fob-n-w"]
    f.pos = Vec2(210_000, 60_000)  # the far bank: it may not drive back over
    assert follow._ends(w, RULES, f) == ["cross-n"]
    assert not follow._approach(w, RULES, f, Vec2(*POS["west-airbase"]))  # fob-n-w is across


def test_a_bridge_falling_in_combat_reroutes_deterministically() -> None:
    def once() -> tuple[str, list[str], list[str | Vec2]]:
        w = new_world(SURE)
        jet = jet_at(w)
        strike(w, jet, NORTH)
        w.bridge_hp[NORTH] = 50
        e = truck(w, 150_000, 60_000, "fob-n-w", ["cross-n", "fob-n-e"])
        events = run(w, 3)
        return state_hash(w), [x.model_dump_json() for x in events], [*e.path]

    a, b = once(), once()
    assert a == b and any("BridgeDestroyed" in x for x in a[1])
    assert a[2][0] == "fob-n-w" and NORTH not in bridges_on([str(p) for p in a[2]])


EDGES = sorted(
    {tuple(sorted((a, nb))) for a in RULES.roads.pos for nb, _ in RULES.roads.neighbours(a)}
)


def _crosses_a_cut(w: World, e: Entity) -> bool:
    """Geometry only: does the polyline pos -> path pass a down bridge's position, starting short
    of it (a unit standing exactly on it may carry on)?"""
    points = [(e.pos.x, e.pos.y), *(POS[str(p)] for p in e.path)]
    for bridge in w.bridge_down:
        cx, cy = POS[bridge]
        for (px, py), (qx, qy) in pairwise(points):
            dx, dy = qx - px, qy - py
            length2 = dx * dx + dy * dy
            if length2 == 0 or (px, py) == (cx, cy):
                continue
            along = ((cx - px) * dx + (cy - py) * dy) / length2
            if 0 < along <= 1 and abs(dx * (cy - py) - dy * (cx - px)) <= 1e-6 * length2:
                return True
    return False


@settings(max_examples=60, deadline=None)
@given(
    units=st.lists(
        st.tuples(
            st.sampled_from(EDGES),
            st.floats(0, 1),
            st.booleans(),
            st.sampled_from(BANKS),
            st.booleans(),
        ),
        min_size=1,
        max_size=6,
    ),
    down=st.lists(st.sampled_from(BRIDGES), min_size=1, max_size=2, unique=True),
)
def test_after_a_fall_no_ground_path_crosses_a_cut_bridge(
    units: list[tuple[tuple[str, str], float, bool, str, bool]], down: list[str]
) -> None:
    w = new_world()
    for (a, b), s, flip, dest, turned in units:
        a, b = (b, a) if flip else (a, b)
        (ax, ay), (bx, by) = POS[a], POS[b]
        x, y = ax + s * (bx - ax), ay + s * (by - ay)
        if turned and 0 < s < 1:  # left b, turned back toward it: heading for b from a's side
            route = shortest_path(RULES.roads, b, dest, blocked=frozenset())
            truck(w, x, y, b, route or [b])
        else:
            route = shortest_path(RULES.roads, b, dest, blocked=frozenset())
            truck(w, x, y, a, [b, *(route or [b])[1:]])
    paths = {e.id: [*e.path] for e in w.entities()}
    fall(w, *down)
    for e in w.entities():
        if e.kind == TRUCK:
            assert not _crosses_a_cut(w, e), (e.pos, paths[e.id], e.path)
            assert e.path, "a rerouted unit always keeps its stop node"


# --- hp bounds (B-2 for damage; repair is part 2) ---------------------------------------------


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.sampled_from(BRIDGES), st.integers(0, 400)), max_size=30))
def test_hp_stays_within_zero_and_max_and_down_means_it_reached_zero(
    hits: list[tuple[str, int]],
) -> None:
    w = new_world()
    out: list[Event] = []
    for node, amount in hits:
        bridges.damage(w, RULES, node, amount, 1, out)
        assert 0 <= w.bridge_hp[node] <= MAX_HP
    spent = {n: sum(a for m, a in hits if m == n) for n in BRIDGES}
    assert w.bridge_down == {n for n in BRIDGES if spent[n] >= MAX_HP}
    assert sorted(e.node_id for e in of(out, BridgeDestroyed)) == sorted(w.bridge_down)
    bridges.validate(w, RULES)


# --- snapshot and restore ---------------------------------------------------------------------


def test_a_down_bridge_and_a_shot_in_flight_survive_a_snapshot() -> None:
    w = new_world(SURE)
    intact = state_hash(w)
    cut(w, SOUTH)
    strike(w, jet_at(w, dx=9_000), NORTH)
    run(w)  # a 50-tick flight: the shot is still pending
    assert [s.node for s in w.shots] == [NORTH]
    assert state_hash(w) != intact
    again = load(save(w))
    assert (again.bridge_hp, again.bridge_down) == (w.bridge_hp, w.bridge_down)
    bridges.validate(again, SURE)
    combat_validate(again, SURE)
    assert state_hash(again) == state_hash(w)
    again.rules = SURE
    assert [e.model_dump_json() for e in run(again, 60)] == [
        e.model_dump_json() for e in run(w, 60)
    ]


@pytest.mark.parametrize(
    "bad",
    [
        lambda w: w.bridge_hp.__setitem__(NORTH, MAX_HP + 1),  # above the maximum
        lambda w: w.bridge_hp.__setitem__(NORTH, 0),  # 0 hp but not down
        lambda w: w.bridge_down.add(NORTH),  # down at full hp
        lambda w: w.bridge_hp.pop(SOUTH),  # a bridge missing
        lambda w: w.bridge_hp.__setitem__("fob-n-w", 5),  # not a bridge
    ],
)
def test_restore_refuses_bridge_state_that_does_not_fit_the_rules(
    bad: Callable[[World], object],
) -> None:
    w = new_world()
    bad(w)
    again = load(save(w))
    with pytest.raises(ValueError, match="bridge"):
        bridges.validate(again, RULES)


@pytest.mark.parametrize(
    "bad",
    [
        lambda w: w.bridge_hp.__setitem__(NORTH, -1),
        lambda w: w.bridge_down.add("fob-n-w"),  # down, yet not a bridge
        lambda w: w.bridge_hp.__setitem__("nowhere", 5),  # not a node
    ],
)
def test_load_refuses_malformed_bridge_state(bad: Callable[[World], object]) -> None:
    w = new_world()
    bad(w)
    with pytest.raises(ValueError, match="bridge"):
        load(save(w))
