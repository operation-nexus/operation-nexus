"""NX-373 part 1a: bridge hp, STRUCTURE fire on a bridge, the cut road and `BridgeDestroyed`
(STATE-MACHINES §4.3 B-1 and B-2, GAMEPLAY §5, COMBAT CB-10, Q-SIM-105..107).

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
from test_combat import ARMOR, JET, RULES, new_world, of, put, run, sure, track

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
        bridges.damage(w, SOUTH, 200, 7, out)
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


# --- hp bounds (B-2 for damage; repair is part 2) ---------------------------------------------


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.sampled_from(BRIDGES), st.integers(0, 400)), max_size=30))
def test_hp_stays_within_zero_and_max_and_down_means_it_reached_zero(
    hits: list[tuple[str, int]],
) -> None:
    w = new_world()
    out: list[Event] = []
    for node, amount in hits:
        bridges.damage(w, node, amount, 1, out)
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
