"""NX-123 part 1: node stock, truck source choice, unload and divert (GAMEPLAY §5, GP-7;
Q-GP-24, Q-SIM-48..50).

Shipped strait-1 numbers: a truck loads `truck_cargo` 100 and unloads 1.0 stock per world s, which
is 0.6 per tick (`sim.time_scale` 6), so 600 thousandths a tick; `starve_threshold` 0.25 puts the
floor at 500 on west-airbase (max 2000) and 250 on a FOB (max 1000). West-airbase starts at 1000,
each FOB at 500; the sanctuaries `haven` and `static-rear` are infinite.
"""

import dataclasses
import os
import subprocess
import sys
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID, join

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.logistics import friendly, plan_run
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.world import Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config, start_campaign

CONFIG = load_campaign_config()
RULES = CONFIG.rules
POS = RULES.roads.pos


def new_world(rules: Rules = RULES) -> World:
    w = start_campaign(CAMPAIGN_ID, 12345, dataclasses.replace(CONFIG, rules=rules))
    return w


def send(w: World, command: JoinCommand) -> list[Event]:
    """Step `w` one tick with `command` aimed at it."""
    return step(w, [command.model_copy(update={"target_tick": w.campaign.tick + 1})])


def truck_for(w: World, n: int, node: str | None, role: str = "LOGI") -> Entity:
    """JOIN commander `n` and return the new unit."""
    before = {e.id for e in w.entities()}
    send(w, join(n, role, node))
    (unit,) = (e for e in w.entities() if e.id not in before)
    return unit


def parked(
    w: World, node: str, cargo: int, side: Side = "COALITION", kind: Any = "LOGI_TRUCK"
) -> Entity:
    """A truck standing at the end of its path at `node`."""
    e = w.spawn(kind, side, "AI_GARRISON", Vec2(*POS[node]), hp=None)
    e.last_node, e.cargo = node, cargo
    return e


def total(w: World) -> int:
    return sum(w.stock.values()) + sum(e.cargo or 0 for e in w.entities())


def test_start_campaign_loads_theater_stock_and_no_sanctuary_stock() -> None:
    w = new_world()
    assert w.stock["west-airbase"] == 1000 and w.stock["fob-n-e"] == 500
    assert w.stock["bridge-n"] == 0 and w.stock["static-hq"] == 1000
    assert "haven" not in w.stock and "static-rear" not in w.stock  # infinite by rule


def test_truck_loads_at_the_nearest_friendly_node_with_surplus() -> None:
    w = new_world()
    t = truck_for(w, 1, "fob-n-w")
    # west-airbase (1000, floor 500) is the nearest source by road; it spawns there and loads.
    assert (t.cargo, w.stock["west-airbase"]) == (100, 900)
    assert w.stock["fob-s-w"] == 500  # untouched
    spawned = step(new_world(), [join(2, "LOGI", "fob-n-w")])
    (ev,) = [e for e in spawned if isinstance(e, UnitSpawned)]
    assert (ev.node_id, ev.unit_kind, ev.loadout) == ("west-airbase", "LOGI_TRUCK", "FULL")
    # It already moved a tick (SC-13) from west-airbase, toward fob-n-w: 25 m/s x 0.6 s.
    assert t.last_node == "west-airbase" and t.path == ["fob-n-w"]
    assert t.pos.x > 90_000.0 and t.pos.y < 120_000.0


def test_cargo_is_the_surplus_and_a_source_never_drops_below_its_floor() -> None:
    w = new_world()
    w.stock["west-airbase"] = 520  # floor 500: surplus 20
    t = truck_for(w, 1, "fob-n-w")
    assert (t.cargo, w.stock["west-airbase"]) == (20, 500)


def test_a_source_at_its_floor_is_skipped() -> None:
    w = new_world()
    w.stock["west-airbase"] = 500  # surplus 0: not a source
    t = truck_for(w, 1, "fob-n-w")
    assert t.last_node == "fob-s-w" and t.cargo == 100  # the other friendly node with surplus
    assert (w.stock["fob-s-w"], w.stock["west-airbase"]) == (400, 500)


def test_equally_near_sources_tie_by_node_id() -> None:
    w = new_world()  # fob-n-w and fob-s-w are mirror images, both 250 over their floor
    assert truck_for(w, 1, "west-airbase").last_node == "fob-n-w"
    w2 = new_world()
    w2.stock["fob-n-w"] = 250  # at its floor
    assert truck_for(w2, 1, "west-airbase").last_node == "fob-s-w"


def test_destination_is_never_its_own_source_and_the_sanctuary_is_last_resort() -> None:
    w = new_world()
    for n in ("fob-n-w", "fob-s-w"):
        w.stock[n] = 250  # at the floor
    # Only west-airbase has surplus and it is the destination: haven loads a full truck.
    before = total(w)
    t = truck_for(w, 1, "west-airbase")
    assert (t.last_node, t.cargo, w.stock["west-airbase"]) == ("haven", 100, 1000)
    assert total(w) == before + 100  # loaded at an infinite source


def test_neutral_enemy_and_null_targets_carry_nothing_from_the_sanctuary() -> None:
    for n, node in enumerate(["cross-n", "static-hq", None], start=1):
        w = new_world()
        t = truck_for(w, n, node)
        assert (t.last_node, t.cargo) == ("haven", 0), node
        assert w.stock["west-airbase"] == 1000


def test_non_trucks_forward_deploy_and_carry_no_cargo() -> None:
    w = new_world()
    for n, role in enumerate(["STRIKE", "RECON"], start=1):
        u = truck_for(w, n, "west-airbase", role)
        assert (u.last_node, u.cargo) == ("west-airbase", None)
    assert w.stock["west-airbase"] == 1000 - 20 - 5  # each paid its loadout_cost


def test_enemy_convoy_loads_from_the_static_nodes_and_the_rear_source() -> None:
    w = new_world()
    run = plan_run(w, RULES, "ENEMY", "static-hq")
    # east-airbase (70 km) is nearer static-hq than either FOB (120 km), and is over its floor.
    assert run and (run.source, run.cargo, run.route) == (
        "east-airbase",
        100,
        ["east-airbase", "static-hq"],
    )
    for n in ("fob-n-e", "fob-s-e", "static-hq", "east-airbase"):
        w.stock[n] = RULES.supply.starve_floor[n]
    rear = plan_run(w, RULES, "ENEMY", "fob-n-e")
    assert rear and (rear.source, rear.cargo) == ("static-rear", 100)
    assert rear.route == ["static-rear", "static-hq", "fob-n-e"]
    assert friendly(w, "ENEMY", "static-hq") and not friendly(w, "COALITION", "static-hq")


def test_a_truck_unloads_at_the_rate_and_parks_empty() -> None:
    w = new_world()
    e = parked(w, "fob-n-w", 5)
    for _ in range(5):  # 600 thousandths a tick: 3000 thousandths = 3 whole units
        step(w, [])
    assert (e.cargo, w.stock["fob-n-w"], e.unload_milli) == (2, 503, 0)
    for _ in range(4):
        step(w, [])
    assert (e.cargo, w.stock["fob-n-w"], e.unload_milli) == (0, 505, 0)
    assert e.id in {x.id for x in w.entities()} and e.path == []  # parked, not retired


def deliveries(w: World, ticks: int) -> list[tuple[int, str, int, int]]:
    """(tick, node, amount, carrier) of every SupplyDelivered in `ticks` more ticks."""
    return [
        (ev.tick, ev.node_id, ev.amount, ev.carrier_id)
        for _ in range(ticks)
        for ev in step(w, [])
        if isinstance(ev, SupplyDelivered)
    ]


def test_a_stop_ending_with_empty_cargo_reports_one_delivery() -> None:
    w = new_world()
    e = parked(w, "fob-n-w", 5)
    assert deliveries(w, 20) == [(9, "fob-n-w", 5, e.id)]
    assert e.delivered == 0


def test_a_stop_ending_at_the_nodes_maximum_reports_what_fit() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 998
    e = parked(w, "fob-n-w", 100)
    assert deliveries(w, 30) == [(4, "fob-n-w", 2, e.id)]  # then it sits parked, silent
    assert (e.cargo, e.delivered) == (98, 0)


def test_a_stop_cut_short_by_a_lost_destination_reports_what_was_unloaded() -> None:
    w = new_world()
    e = parked(w, "static-hq", 50)
    e.delivered = 3  # it had unloaded 3 units before the node stopped being friendly
    (event,) = [ev for ev in step(w, []) if isinstance(ev, SupplyDelivered)]
    assert (event.node_id, event.amount, event.carrier_id) == ("static-hq", 3, e.id)
    assert event.commander_id == e.commander_id and e.delivered == 0 and e.path


def test_no_delivery_event_when_nothing_was_delivered() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 1000  # full on arrival
    parked(w, "fob-n-w", 10)
    parked(w, "static-hq", 10)  # drives off having unloaded nothing
    assert deliveries(w, 10) == []


def test_a_mid_stop_delivery_count_survives_a_snapshot() -> None:
    w = new_world()
    e = parked(w, "fob-n-w", 100)
    for _ in range(3):
        step(w, [])
    assert e.delivered == 1
    again = load(save(w))
    assert again.get(e.id).delivered == 1 and state_hash(again) == state_hash(w)
    e.delivered = 0
    assert state_hash(again) != state_hash(w)


def test_an_enemy_convoy_unloads_at_an_enemy_node_by_the_same_rules() -> None:
    w = new_world()
    e = parked(w, "static-hq", 4, "ENEMY", "ENEMY_CONVOY")
    for _ in range(7):
        step(w, [])
    assert (e.cargo, w.stock["static-hq"]) == (0, 1004)


def test_unloading_stops_at_the_nodes_maximum_and_the_truck_keeps_the_rest() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 998  # max 1000
    e = parked(w, "fob-n-w", 100)
    for _ in range(20):
        step(w, [])
    assert (w.stock["fob-n-w"], e.cargo, e.path) == (1000, 98, [])  # no divert: it is friendly


def test_paused_campaign_unloads_nothing() -> None:
    w = new_world()
    e = parked(w, "fob-n-w", 50)
    w.campaign.clock_paused = True
    for _ in range(10):
        step(w, [])
    assert (e.cargo, e.unload_milli, w.stock["fob-n-w"]) == (50, 0, 500)


def test_a_lost_destination_diverts_to_the_nearest_friendly_base_with_room() -> None:
    w = new_world()
    e = parked(w, "static-hq", 50)  # the coalition truck stands at an enemy node
    step(w, [])
    # fob-n-w and fob-s-w are equally near by road; the id order picks the north one.
    assert e.path[-1] == "fob-n-w" and e.path[0] == "static-hq"
    w.stock["fob-n-w"] = 1000  # full: not a candidate while another base has room
    e.path = []
    step(w, [])
    assert e.path[-1] == "fob-s-w"
    for _ in range(100_000):  # it drives there and unloads
        step(w, [])
        if e.cargo == 0:
            break
    assert (e.cargo, e.last_node, w.stock["fob-s-w"]) == (0, "fob-s-w", 550)


def test_a_lost_destination_with_no_room_anywhere_drives_to_the_nearest_friendly_base() -> None:
    w = new_world()
    for n, top in RULES.supply.max_stock.items():
        if friendly(w, "COALITION", n):
            w.stock[n] = top
    e = parked(w, "static-hq", 50)
    step(w, [])
    assert e.path[-1] == "fob-n-w"  # parked there later holding its cargo
    e.path, e.last_node, e.pos = [], "fob-n-w", Vec2(*POS["fob-n-w"])
    for _ in range(10):
        step(w, [])
    assert (e.cargo, e.path) == (50, [])


def test_a_lost_destination_with_no_friendly_base_stays_put() -> None:
    owners = {n: "ENEMY" if o == "COALITION" else o for n, o in RULES.supply.start_owner.items()}
    rules = dataclasses.replace(RULES, supply=dataclasses.replace(RULES.supply, start_owner=owners))
    w = new_world(rules)
    e = parked(w, "static-hq", 50)
    for _ in range(5):
        step(w, [])
    assert (e.cargo, e.path, e.last_node) == (50, [], "static-hq")


def fast_rules() -> Rules:
    """Trucks 200x faster so a hypothesis run sees arrivals and unloads in a few steps."""
    fast = {k: v * 200 for k, v in RULES.speed_mps.items()}
    return dataclasses.replace(RULES, speed_mps=fast)


ACTION = st.one_of(
    st.tuples(st.just("join"), st.sampled_from(sorted(POS))),
    st.tuples(st.just("steps"), st.integers(1, 40)),
    st.tuples(st.just("remove"), st.integers(0, 5)),
)


@given(st.lists(ACTION, max_size=30))
def test_stock_plus_cargo_is_conserved_exactly(actions: list[tuple[str, Any]]) -> None:
    """Total stock and cargo changes only by cargo loaded at an infinite source and by cargo lost
    with a removed truck (a debit from a finite source is a cargo gain, so the total is steady)."""
    w, n = new_world(fast_rules()), 0
    expected = total(w)
    rear = set(RULES.supply.rear.values())
    for kind, arg in actions:
        if kind == "join":
            n += 1
            for ev in send(w, join(n, "LOGI", arg)):
                if isinstance(ev, UnitSpawned) and ev.node_id in rear:
                    expected += w.get(ev.entity_id).cargo or 0  # no leg ends in its spawn tick
        elif kind == "steps":
            for _ in range(arg):
                step(w, [])
        else:
            loaded = [e for e in w.entities() if e.cargo]
            if loaded:
                gone = loaded[arg % len(loaded)]
                expected -= gone.cargo or 0
                w.remove(gone.id)
        assert total(w) == expected
        assert all(0 <= s <= RULES.supply.max_stock[k] for k, s in w.stock.items())


def stocked_world() -> World:
    w = new_world()
    truck_for(w, 1, "fob-n-w")
    truck_for(w, 2, "static-hq")
    parked(w, "fob-s-w", 7).unload_milli = 450
    for _ in range(50):
        step(w, [])
    return w


def test_snapshot_round_trips_and_the_hash_covers_stock_and_cargo() -> None:
    w = stocked_world()
    h = state_hash(w)
    again = load(save(w))
    assert state_hash(again) == h and again.stock == w.stock
    cargo = next(e for e in w.entities() if e.cargo)
    cargo.cargo = (cargo.cargo or 0) + 1
    assert state_hash(w) != h
    cargo.cargo -= 1
    w.stock["fob-n-w"] += 1
    assert state_hash(w) != h
    w.stock["fob-n-w"] -= 1
    assert state_hash(w) == h


def test_load_refuses_a_bad_stock_map() -> None:
    import msgpack

    raw = msgpack.unpackb(save(stocked_world()), raw=False)
    raw["stock"]["fob-n-w"] = -1
    with pytest.raises(ValueError, match="stock"):
        load(msgpack.packb(raw, use_bin_type=True))
    raw["stock"]["fob-n-w"] = 5
    raw["entities"][-1]["unload_milli"] = 1000
    with pytest.raises(ValueError, match="unload_milli"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_a_version_9_snapshot_is_refused() -> None:
    import msgpack

    raw = msgpack.unpackb(save(new_world()), raw=False)
    raw["v"] = 9
    with pytest.raises(ValueError, match="unsupported snapshot format version 9"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_make_rules_refuses_a_start_stock_above_its_kinds_maximum() -> None:
    from nexus.core.rules import make_rules

    small = CONFIG.balance.logistics.node_max_stock.model_copy(update={"FOB": 400})
    logistics = CONFIG.balance.logistics.model_copy(update={"node_max_stock": small})
    with pytest.raises(ValueError, match="fob-n-e"):
        make_rules(
            CONFIG.balance.sim, CONFIG.catalog.units, RULES.roads, roles=CONFIG.catalog.roles.roles,
            theater=CONFIG.theater, slots=CONFIG.balance.slots, air=CONFIG.balance.air,
            fow=CONFIG.balance.fow, logistics=logistics, capture=CONFIG.balance.capture,
            respawn_delay_ticks=0,
            track_fade_ticks=1, sigint_refresh_ticks=1, mask_cell_m=1000.0, masking={},
        )  # fmt: skip


def test_make_rules_refuses_an_unload_rate_below_a_thousandth_per_tick() -> None:
    from nexus.core.rules import make_rules

    logistics = CONFIG.balance.logistics.model_copy(update={"unload_rate": 0.0001})
    with pytest.raises(ValueError, match=r"below 0\.001 per tick"):
        make_rules(
            CONFIG.balance.sim, CONFIG.catalog.units, RULES.roads, roles=CONFIG.catalog.roles.roles,
            theater=CONFIG.theater, slots=CONFIG.balance.slots, air=CONFIG.balance.air,
            fow=CONFIG.balance.fow, logistics=logistics, capture=CONFIG.balance.capture,
            respawn_delay_ticks=0,
            track_fade_ticks=1, sigint_refresh_ticks=1, mask_cell_m=1000.0, masking={},
        )  # fmt: skip


def run_scenario() -> World:
    w = new_world(fast_rules())
    for n, node in enumerate(["fob-n-w", "west-airbase", "fob-s-w", "cross-n"], start=1):
        send(w, join(n, "LOGI", node))
    for _ in range(300):
        step(w, [])
    return w


def test_two_runs_hash_alike_and_across_hash_seeds() -> None:
    assert state_hash(run_scenario()) == state_hash(run_scenario())
    child = (
        "import sys; sys.path.insert(0, sys.argv[1]); from test_logistics import run_scenario\n"
        "from nexus.core.world import state_hash; print(state_hash(run_scenario()))"
    )

    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", child, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert run("1") == run("2") == state_hash(run_scenario())
