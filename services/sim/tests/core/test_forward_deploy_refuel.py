"""NX-123 part 2: forward deploy and refuel at bases (GAMEPLAY GP-7, §5; Q-SIM-49, Q-SIM-51,
Q-SIM-53, Q-SIM-54; SIM-CORE §4 Logistics).

Shipped strait-1 numbers: a STRIKE_FIGHTER has `fuel_s` 3600 and `loadout_cost` 20, half for a full
tank and half for a full load of rounds (Q-SIM-68); refuelling buys `rearm_rate` 0.5 stock per
world s, which at 0.6 world s a tick is 300 thousandths of a unit a tick, or 108 s of fuel (300 x
3600 / 10000). The jets here keep a full load, so only the tank is bought. West-airbase (max 2000,
floor 500) starts at 1000; `forward_deploy_min_surplus` is 50. Its AIR and GROUND spawns are
`haven`, `west-airbase` and the three friendly FOB spawns (GROUND only).
"""

import dataclasses
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID, cid, join
from test_logistics import CONFIG, POS, RULES, new_world, send, total

from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.rearm_stalled import RearmStalled
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.logistics import pay_loadout, plan_deploy
from nexus.core.roads import Road, RoadGraph
from nexus.core.rules import Rules, Supply
from nexus.core.step import step
from nexus.core.world import Campaign, Entity, Vec2, World, load, save, state_hash

FULL = 3600.0
WEST = "west-airbase"


def aircraft(
    w: World, node: str, fuel: float, side: Any = "COALITION", kind: Any = "STRIKE_FIGHTER"
) -> Entity:
    """An AI aircraft standing LANDED at `node`."""
    e = w.spawn(kind, side, "AI_GARRISON", Vec2(*POS[node]))
    e.last_node, e.state, e.fuel = node, "LANDED", fuel
    return e


def run(w: World, ticks: int) -> list[Event]:
    return [ev for _ in range(ticks) for ev in step(w, [])]


def consumed(events: list[Event]) -> list[tuple[str, int, str]]:
    return [(e.node_id, e.amount, e.cause) for e in events if isinstance(e, SupplyConsumed)]


def stalled(events: list[Event]) -> list[tuple[int, str]]:
    return [(e.entity_id, e.node_id) for e in events if isinstance(e, RearmStalled)]


def with_supply(rules: Rules = RULES, **fields: Any) -> Rules:
    return dataclasses.replace(rules, supply=dataclasses.replace(rules.supply, **fields))


# --- forward deploy ---------------------------------------------------------------------------


def test_an_aircraft_forward_deploys_and_pays_its_loadout_from_the_base() -> None:
    w = new_world()
    events = send(w, join(1, "STRIKE", "fob-n-w"))
    (spawn,) = [e for e in events if isinstance(e, UnitSpawned)]
    assert (spawn.node_id, spawn.loadout) == (WEST, "FULL")
    assert consumed(events) == [(WEST, 20, "SPAWN")] and w.stock[WEST] == 980
    unit = w.get(spawn.entity_id)
    assert (unit.state, unit.path, unit.last_node) == (
        "EN_ROUTE",
        ["fob-n-w"],
        WEST,
    )  # took off at once
    assert unit.fuel == FULL - RULES.world_dt  # a full tank, one tick burnt


def test_a_unit_that_cannot_forward_deploy_leaves_the_sanctuary_free() -> None:
    w = new_world()
    w.stock[WEST] = 549  # surplus 49: below forward_deploy_min_surplus 50
    events = send(w, join(1, "STRIKE", "fob-n-w"))
    (spawn,) = [e for e in events if isinstance(e, UnitSpawned)]
    assert spawn.node_id == "haven" and consumed(events) == [] and w.stock[WEST] == 549


def test_a_base_at_floor_plus_margin_qualifies() -> None:
    w = new_world()
    w.stock[WEST] = 550
    events = send(w, join(1, "RECON", "fob-n-w"))
    assert consumed(events) == [(WEST, 5, "SPAWN")] and w.stock[WEST] == 545


def test_a_spawn_never_takes_a_base_below_its_floor() -> None:
    rules = with_supply(forward_deploy_min_surplus=10)  # the loadout (20) is the bigger need
    for stock, node, left in ((519, "haven", 519), (520, WEST, 500)):
        w = new_world(rules)
        w.stock[WEST] = stock
        (spawn,) = [e for e in send(w, join(1, "STRIKE", "fob-n-w")) if isinstance(e, UnitSpawned)]
        assert (spawn.node_id, w.stock[WEST]) == (node, left)


def test_only_spawn_list_nodes_for_the_domain_qualify() -> None:
    # fob-n-w has stock over its floor but is a GROUND-only spawn: an aircraft never deploys there.
    w = new_world()
    w.stock[WEST] = 500
    (spawn,) = [e for e in send(w, join(1, "STRIKE", "fob-n-w")) if isinstance(e, UnitSpawned)]
    assert spawn.node_id == "haven" and w.stock["fob-n-w"] == 500
    # A node absent from the spawn list never qualifies, whatever it holds.
    rules = with_supply(spawns={**RULES.supply.spawns, "AIR": frozenset({"haven"})})
    w2 = new_world(rules)
    (spawn2,) = [e for e in send(w2, join(1, "STRIKE", "fob-n-w")) if isinstance(e, UnitSpawned)]
    assert spawn2.node_id == "haven"


def test_the_side_must_own_the_node() -> None:
    assert plan_deploy(new_world(), RULES, "COALITION", "STRIKE_FIGHTER", "east-airbase") == (
        WEST,
        ["east-airbase"],
    )
    owners = {**RULES.supply.start_owner, WEST: "ENEMY"}
    w = new_world(with_supply(start_owner=owners))
    assert plan_deploy(w, w.rules or RULES, "COALITION", "STRIKE_FIGHTER", "fob-n-w") is None


def test_ground_units_deploy_to_the_nearest_base_by_road_and_take_its_route() -> None:
    rules = dataclasses.replace(RULES, role_kind={**RULES.role_kind, "STRIKE": "GARRISON_INFANTRY"})
    w = new_world(rules)
    events = send(w, join(1, "STRIKE", "cross-n"))
    (spawn,) = [e for e in events if isinstance(e, UnitSpawned)]
    assert spawn.node_id == "fob-n-w" and consumed(events) == [("fob-n-w", 5, "SPAWN")]
    unit = w.get(spawn.entity_id)
    assert unit.path == ["cross-n"] and w.stock["fob-n-w"] == 495  # one tick along the road


def test_a_target_with_no_road_from_any_base_is_rejected() -> None:
    rules = dataclasses.replace(RULES, role_kind={**RULES.role_kind, "STRIKE": "GARRISON_INFANTRY"})
    w = new_world(rules)
    (rejected,) = send(w, join(1, "STRIKE", "bridge-n"))  # bridge nodes have no road of their own
    assert getattr(rejected, "reason", None) == "NODE_INVALID_FOR_UNIT"


def toy_world() -> World:
    """Sanctuary s0, bases a and b, target t. `a` is the nearest base to `t` by straight line (2 km)
    but its road goes round through `b`; `b` is 14 km away with a direct road."""
    pos = {"s0": (0, 0), "a": (8000, 0), "b": (0, 10000), "t": (10000, 0)}
    roads = RoadGraph(pos, [Road("s0", "a", 1.0), Road("a", "b", 1.0), Road("b", "t", 1.0)])
    supply = Supply(
        rear={"COALITION": "s0", "ENEMY": "s0"},
        start_owner={"s0": "COALITION", "a": "COALITION", "b": "COALITION", "t": "NEUTRAL"},
        max_stock={"a": 1000, "b": 1000, "t": 1000},
        starve_floor={"a": 100, "b": 100, "t": 100},
        loadout_cost={"STRIKE_FIGHTER": 20, "GARRISON_INFANTRY": 5},
        forward_deploy_min_surplus=50,
        spawns={"AIR": frozenset({"s0", "a", "b"}), "GROUND": frozenset({"s0", "a", "b"})},
    )
    rules = dataclasses.replace(
        RULES,
        roads=roads,
        sanctuary="s0",
        supply=supply,
        defense=None,  # the toy graph is not the theater's
        landing_nodes=("a", "b", "s0"),
        role_kind={**RULES.role_kind, "RECON": "GARRISON_INFANTRY"},
    )
    w = World.new(Campaign(CAMPAIGN_ID, 1, "cfg-toy"), rules)
    w.stock.update({"a": 500, "b": 500, "t": 500})
    return w


def test_air_picks_the_nearest_by_straight_line_and_ground_by_road() -> None:
    w = toy_world()
    assert w.rules and plan_deploy(w, w.rules, "COALITION", "STRIKE_FIGHTER", "t") == ("a", ["t"])
    assert plan_deploy(w, w.rules, "COALITION", "GARRISON_INFANTRY", "t") == (
        "b",
        ["b", "t"],
    )  # a is 2 km away in a line but 27 km by road; b is 14 km by road


def test_equally_near_bases_tie_by_node_id() -> None:
    w = toy_world()
    w.stock["a"] = w.stock["b"] = 500
    rules = w.rules
    assert rules is not None
    spaced = dict(rules.roads.pos)
    spaced["a"], spaced["b"] = (0, 6000), (0, -6000)  # both 6 km from t's new place
    spaced["t"] = (0, 0)
    tie = dataclasses.replace(
        rules, roads=RoadGraph(spaced, [Road("a", "t", 1.0), Road("b", "t", 1.0)])
    )
    assert plan_deploy(w, tie, "COALITION", "STRIKE_FIGHTER", "t") == ("a", ["t"])
    assert plan_deploy(w, tie, "COALITION", "GARRISON_INFANTRY", "t") == ("a", ["a", "t"])
    w.stock["a"] = 100  # a at its floor: out
    assert plan_deploy(w, tie, "COALITION", "STRIKE_FIGHTER", "t") == ("b", ["t"])


def test_hold_and_null_targets_spawn_at_the_sanctuary_with_no_debit() -> None:
    for command in (join(1, "STRIKE", None), join(2, "STRIKE", None, hold=True)):
        w = new_world()
        events = send(w, command)
        (spawn,) = [e for e in events if isinstance(e, UnitSpawned)]
        assert spawn.node_id == "haven" and consumed(events) == []
        assert w.stock[WEST] == 1000


def test_the_static_deploys_by_the_same_function() -> None:
    w = new_world()
    assert plan_deploy(w, RULES, "ENEMY", "ENEMY_FIGHTER", "fob-n-w") == (
        "east-airbase",
        ["fob-n-w"],
    )
    out: list[Event] = []
    pay_loadout(w, RULES, "ENEMY_FIGHTER", "east-airbase", out)
    assert consumed(out) == [("east-airbase", 20, "SPAWN")] and w.stock["east-airbase"] == 980
    pay_loadout(w, RULES, "ENEMY_FIGHTER", "static-rear", out)  # the rear source is infinite
    assert len(out) == 1
    w.stock["east-airbase"] = 549
    assert plan_deploy(w, RULES, "ENEMY", "ENEMY_FIGHTER", "fob-n-w") is None  # sanctuary instead


def test_a_queued_join_is_planned_again_when_it_is_served() -> None:
    rules = dataclasses.replace(RULES, max_viewer_units=1)
    for stock, node, left in ((1000, WEST, 980), (540, "haven", 540)):
        w = new_world(rules)
        send(w, join(1, "STRIKE", "fob-n-w"))
        send(w, join(2, "STRIKE", "fob-n-w"))  # the cap is reached: queued, nothing debited
        assert len(w.reserve_queue) == 1 and w.stock[WEST] == 980
        w.stock[WEST] = stock  # the base changes while the JOIN waits
        w.remove(next(e.id for e in w.entities() if e.commander_id == cid(1)))
        spawned = [e for e in run(w, 1) if isinstance(e, UnitSpawned)]
        assert [s.node_id for s in spawned] == [node] and w.stock[WEST] == left


# --- refuel -----------------------------------------------------------------------------------


def test_a_full_tank_costs_half_a_loadout_at_the_rearm_rate() -> None:
    w = new_world()
    e = aircraft(w, WEST, 0.0)
    events = run(w, 33)  # 33 x 300 = 9 900 of the 10 000 thousandths
    assert (e.fuel, w.stock[WEST], e.rearm_milli) == (33 * 108.0, 1000 - 9, 900) and not events
    events = run(w, 1)  # the last 100 fill the tank and end the stop
    assert (e.fuel, w.stock[WEST], e.rearm_milli) == (FULL, 990, 0)
    assert consumed(events) == [(WEST, 10, "REARM")] and stalled(events) == []
    assert run(w, 5) == [] and e.fuel == FULL  # never overfills


def test_a_partial_refill_pays_for_the_missing_share_only() -> None:
    w = new_world()
    e = aircraft(w, WEST, FULL / 2)
    events = run(w, 40)
    assert (e.fuel, w.stock[WEST]) == (FULL, 995)
    assert consumed(events) == [(WEST, 5, "REARM")]


def test_fuel_never_exceeds_the_tank_and_each_kind_pays_its_own_cost() -> None:
    w = new_world()
    uav = aircraft(w, WEST, 14_400.0 - 1.0, kind="RECON_UAV")  # one second short of 14 400 s
    events = run(w, 3)
    # 1 s of 14 400 costs 5 x 1000 / 14 400 = 0.35 thousandths, bought as 1: under one unit.
    assert uav.fuel == 14_400.0 and consumed(events) == []
    assert (uav.rearm_milli, w.stock[WEST]) == (1, 1000)


def test_below_the_starvation_floor_it_fills_only_to_half_a_tank() -> None:
    w = new_world()
    w.stock[WEST] = 400  # floor 500
    e = aircraft(w, WEST, 0.0)
    events = run(w, 100)
    assert (e.fuel, w.stock[WEST]) == (FULL / 2, 395)
    assert consumed(events) == [(WEST, 5, "REARM")] and stalled(events) == []
    w.stock[WEST] = 600  # a delivery lifts it over the floor: the rest of the tank is sold
    events = run(w, 100)
    assert e.fuel == FULL and w.stock[WEST] == 595 and consumed(events) == [(WEST, 5, "REARM")]


def test_an_empty_base_stalls_once_and_resumes_after_a_delivery() -> None:
    w = new_world()
    w.stock[WEST] = 0
    e = aircraft(w, WEST, 100.0)
    events = run(w, 10)
    assert stalled(events) == [(e.id, WEST)] and consumed(events) == [] and e.fuel == 100.0
    w.stock[WEST] = 3  # a truck unloads 3 units
    events = run(w, 30)  # 10 ticks of 300 spend them, the next tick stalls again
    assert e.fuel == pytest.approx(100.0 + 3 * 360.0) and w.stock[WEST] == 0
    assert consumed(events) == [(WEST, 3, "REARM")] and stalled(events) == [(e.id, WEST)]
    assert run(w, 10) == []  # still stalled: nothing more is said


def test_the_sanctuary_refuels_free_at_the_same_rate() -> None:
    w = new_world()
    e = aircraft(w, "haven", 0.0)
    before = dict(w.stock)
    events = run(w, 33)
    assert e.fuel == 33 * 108.0 and events == []
    assert [type(x) for x in run(w, 1)] == [] and e.fuel == FULL and w.stock == before


def test_an_enemy_aircraft_refuels_at_its_own_base_only() -> None:
    w = new_world()
    enemy = aircraft(w, "east-airbase", 0.0, "ENEMY", "ENEMY_FIGHTER")
    lost = aircraft(w, WEST, 0.0, "ENEMY", "ENEMY_FIGHTER")  # a node the side does not own
    run(w, 10)
    assert enemy.fuel == 10 * 108.0 and lost.fuel == 0.0


def test_a_paused_campaign_refuels_nothing() -> None:
    w = new_world()
    e = aircraft(w, WEST, 0.0)
    w.campaign.clock_paused = True
    assert run(w, 20) == [] and (e.fuel, e.rearm_milli, w.stock[WEST]) == (0.0, 0, 1000)


def test_taking_off_ends_the_stop_and_a_refuelled_aircraft_can_go() -> None:
    w = new_world()
    e = aircraft(w, WEST, 0.0)
    e.path = ["fob-n-w"]  # ordered off empty: bingo keeps it on the ground
    run(w, 3)
    assert (e.state, e.path, e.last_node) == ("LANDED", [], WEST) and e.fuel == 3 * 108.0
    run(w, 17)  # 20 ticks bought: 2160 s, above bingo (540 s at its own base)
    spent = 6
    assert e.fuel == 20 * 108.0 and w.stock[WEST] == 1000 - spent and e.rearm_spent == spent
    e.path = ["fob-n-w"]
    events = run(w, 1)
    assert e.state == "EN_ROUTE" and consumed(events) == [(WEST, spent, "REARM")]
    assert run(w, 5) == [] and e.rearm_spent == 0 and w.stock[WEST] == 1000 - spent


def test_kinds_with_no_loadout_cost_are_skipped() -> None:
    w = new_world(with_supply(loadout_cost={**RULES.supply.loadout_cost, "STRIKE_FIGHTER": 0}))
    e = aircraft(w, WEST, 0.0)
    assert run(w, 5) == [] and e.fuel == 0.0 and w.stock[WEST] == 1000


# --- conservation, snapshots, determinism -----------------------------------------------------

ROLES = ("STRIKE", "RECON", "LOGI")
ACTION = st.one_of(
    st.tuples(st.just("join"), st.sampled_from(ROLES), st.sampled_from([*sorted(POS), None])),
    st.tuples(st.just("steps"), st.integers(1, 60), st.just(None)),
    st.tuples(st.just("drain"), st.integers(0, 5), st.just(None)),
    st.tuples(st.just("stock"), st.integers(0, 3), st.integers(0, 600)),
)


def accounted(w: World, spent: int) -> int:
    """Stock + cargo + everything paid out: events already told, and refuel stops still open."""
    return total(w) + spent + sum(e.rearm_spent + e.repair_spent for e in w.entities())


@given(st.lists(ACTION, max_size=25))
def test_stock_cargo_and_consumption_balance_exactly(actions: list[tuple[str, Any, Any]]) -> None:
    fast = {k: v * 200 for k, v in RULES.speed_mps.items()}
    w, n, spent = new_world(dataclasses.replace(RULES, speed_mps=fast)), 0, 0
    expected, rear = accounted(w, 0), set(RULES.supply.rear.values())
    bases = ("west-airbase", "fob-n-w", "fob-s-w", "static-hq")

    def tell(events: list[Event]) -> None:
        nonlocal spent, expected
        spent += sum(amount for _, amount, _ in consumed(events))
        for ev in events:
            if isinstance(ev, UnitSpawned) and ev.node_id in rear:
                expected += w.get(ev.entity_id).cargo or 0

    for kind, a, b in actions:
        if kind == "join":
            n += 1
            tell(send(w, join(n, a, b)))
        elif kind == "steps":
            tell(run(w, a))
        elif kind == "drain":  # an idle aircraft lands short of fuel
            air = [e for e in w.entities() if e.state == "LANDED" and not e.path]
            if air:
                air[a % len(air)].fuel = 10.0
        else:  # a delivery or a loss changes a base's stock from outside the module
            node = bases[a]
            expected += b - w.stock[node]
            w.stock[node] = b
        assert accounted(w, spent) == expected
        assert all(0 <= s <= RULES.supply.max_stock[k] for k, s in w.stock.items())


def midway() -> World:
    """A coalition aircraft part-way through paying for fuel, and an enemy one stalled."""
    w = new_world()
    mid = aircraft(w, WEST, 3000.0)
    w.stock["east-airbase"] = 0
    dry = aircraft(w, "east-airbase", 10.0, "ENEMY", "ENEMY_FIGHTER")
    run(w, 5)  # 1500 thousandths bought: 1 unit debited, 500 owed
    assert (mid.rearm_spent, mid.rearm_milli, dry.stalled) == (1, 500, True)
    return w


def test_snapshot_round_trips_mid_refuel_and_the_hash_covers_it() -> None:
    w = midway()
    run(w, 3)
    h = state_hash(w)
    again = load(save(w))
    again.rules = RULES
    assert state_hash(again) == h
    assert run(again, 40) == run(w, 40) and state_hash(again) == state_hash(w)
    w = midway()
    e = next(x for x in w.entities() if x.rearm_spent)
    for name, value in (("rearm_milli", 7), ("rearm_spent", 9), ("stalled", True)):
        before, h = getattr(e, name), state_hash(w)
        setattr(e, name, value)
        assert state_hash(w) != h, name
        setattr(e, name, before)


def test_load_refuses_bad_refuel_progress_and_version_10() -> None:
    import msgpack

    raw = msgpack.unpackb(save(midway()), raw=False)
    air = next(e for e in raw["entities"] if e["state"] is not None)
    air["rearm_milli"] = 1000
    with pytest.raises(ValueError, match="rearm_milli"):
        load(msgpack.packb(raw, use_bin_type=True))
    air["rearm_milli"] = 0
    raw["v"] = 10
    with pytest.raises(ValueError, match="unsupported snapshot format version 10"):
        load(msgpack.packb(raw, use_bin_type=True))


def scenario() -> World:
    w = new_world()
    for n, (role, node) in enumerate(
        [("STRIKE", "fob-n-w"), ("RECON", "west-airbase"), ("LOGI", "fob-s-w"), ("STRIKE", None)],
        start=1,
    ):
        send(w, join(n, role, node))
    aircraft(w, WEST, 0.0)
    w.stock["east-airbase"] = 0
    aircraft(w, "east-airbase", 0.0, "ENEMY", "ENEMY_FIGHTER")
    run(w, 400)
    return w


def test_two_runs_hash_alike_and_across_hash_seeds() -> None:
    import os
    import subprocess
    import sys

    assert state_hash(scenario()) == state_hash(scenario())
    child = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from test_forward_deploy_refuel import scenario\n"
        "from nexus.core.world import state_hash; print(state_hash(scenario()))"
    )

    def hashed(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", child, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert hashed("1") == hashed("2") == state_hash(scenario())


def test_the_loaded_config_prices_every_spawnable_kind() -> None:
    assert RULES.supply.loadout_cost == {
        "STRIKE_FIGHTER": 20, "ENEMY_FIGHTER": 20, "ENEMY_STRIKE_FIGHTER": 20,
        "RECON_UAV": 5, "ENEMY_RECON_UAV": 5, "ENEMY_ARMOR": 15, "GARRISON_INFANTRY": 5,
        "LOGI_TRUCK": 0, "ENEMY_CONVOY": 0,
    }  # fmt: skip
    assert CONFIG.balance.logistics.starved_loadout.fuel_frac == 0.5


def test_an_air_spawn_entry_on_an_hq_is_no_candidate_and_nothing_refuels_there() -> None:
    # static-hq is an AIR spawn of the Static with stock over its floor, but not a landing base.
    w = new_world()
    assert RULES.supply.spawns["AIR"] >= {"static-hq"} and "static-hq" not in RULES.landing_nodes
    assert plan_deploy(w, RULES, "ENEMY", "ENEMY_FIGHTER", "fob-n-w") == (
        "east-airbase",
        ["fob-n-w"],
    )
    w.stock["east-airbase"] = 549  # no airbase qualifies: the HQ must not take over
    assert plan_deploy(w, RULES, "ENEMY", "ENEMY_FIGHTER", "fob-n-w") is None
    # An aircraft constructed on the HQ and on a friendly FOB buys nothing.
    hq = aircraft(w, "static-hq", 0.0, "ENEMY", "ENEMY_FIGHTER")
    fob = aircraft(w, "fob-n-w", 0.0)
    assert run(w, 10) == [] and (hq.fuel, fob.fuel) == (0.0, 0.0)
    assert (w.stock["static-hq"], w.stock["fob-n-w"]) == (1000, 500)


def test_a_hair_short_of_full_snaps_to_full_instead_of_stalling() -> None:
    w = new_world()
    e = aircraft(w, WEST, FULL - 1e-7)
    events = run(w, 5)
    assert (e.fuel, e.stalled, w.stock[WEST], e.rearm_milli) == (FULL, False, 1000, 0)
    assert stalled(events) == [] and consumed(events) == []
    w.stock[WEST] = 0
    assert run(w, 5) == []  # full stays full at an empty base


def test_a_refuel_that_crosses_the_floor_mid_stop_is_capped_at_half_a_tank() -> None:
    w = new_world()
    w.stock[WEST] = 502  # floor 500: the third unit bought takes it under
    e = aircraft(w, WEST, 0.0)
    events = run(w, 100)
    assert (e.fuel, w.stock[WEST]) == (FULL / 2, 497)
    assert consumed(events) == [(WEST, 5, "REARM")] and stalled(events) == []


def test_a_join_to_its_own_sanctuary_spawns_there_free() -> None:
    w = new_world()
    events = send(w, join(1, "STRIKE", "haven"))
    (spawn,) = [e for e in events if isinstance(e, UnitSpawned)]
    assert spawn.node_id == "haven" and consumed(events) == [] and w.stock[WEST] == 1000
    assert plan_deploy(w, RULES, "ENEMY", "ENEMY_FIGHTER", "static-rear") is None
