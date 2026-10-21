"""NX-124 part 2: rearm with refuel, repair at bases and auto-RTB (COMBAT CB-6, CB-11, §5.6;
GAMEPLAY §5, §5b; Q-SIM-68; STATE-MACHINES §4.1).

Shipped strait-1 numbers, `sim.time_scale` 6 (0.6 world s a tick): a stop buys up to 300 stock
thousandths a tick (`rearm_rate` 0.5) for fuel and ammo together. A STRIKE_FIGHTER (`loadout_cost`
20: 10 for a full tank of 3,600 s, 10 for a full load of 404 rounds, AG_LIGHT 4 and AA_LIGHT 400,
the second a gun) repairs 100 hp; repair is 600 thousandths of an hp a tick at an AIRBASE or HQ
(1.0 hp/s), 300 at a FOB (0.5) and 1,200 at a sanctuary (2.0, free). A unit pays `loadout_cost` x
the share of its hp repaired, a facility 1 stock per 10 hp. West-airbase (floor 500) holds 1,000.
"""

import dataclasses
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_combat import COMBAT, of
from test_forward_deploy_refuel import FULL, WEST, aircraft, consumed, run, stalled
from test_join import join
from test_logistics import POS, RULES, new_world, send, total

from nexus.contracts.gen.common.enums import DamageState, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.munitions_depleted import MunitionsDepleted
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.unit_damage_state_changed import UnitDamageStateChanged
from nexus.contracts.gen.events.unit_repaired import UnitRepaired
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.combat import _hit, validate
from nexus.core.fog import tracked_by
from nexus.core.rules import CAPTURE_FULL
from nexus.core.world import (
    CaptureBar,
    Contact,
    Entity,
    Vec2,
    World,
    load,
    lose_unit,
    save,
    state_hash,
)

JET: UnitKind = "STRIKE_FIGHTER"
ARMOR: UnitKind = "ENEMY_ARMOR"
INFANTRY: UnitKind = "GARRISON_INFANTRY"


def ground(w: World, kind: UnitKind, node: str, side: Side = "COALITION") -> Entity:
    """A unit parked on `node`."""
    e = w.spawn(kind, side, "AI_GARRISON", Vec2(*POS[node]))
    e.last_node = node
    return e


def hurt(e: Entity, hp: int) -> Entity:
    """`e` at `hp`, in the damage state that matches (a wreck is built by hand)."""
    e.hp = hp
    e.damage_state = COMBAT.units[e.kind].state(hp)
    return e


def facility(w: World, base: str, kind: UnitKind) -> Entity:
    return next(e for e in w.entities() if e.base_id == base and e.kind == kind)


def state(e: Entity) -> DamageState:
    return e.damage_state


def changes(events: list[Event]) -> list[tuple[DamageState, DamageState]]:
    return [(e.from_, e.to) for e in events if isinstance(e, UnitDamageStateChanged)]


# --- rearm: fuel and ammo ---------------------------------------------------------------------


def test_the_rearm_rate_and_repair_rates_in_thousandths_per_tick() -> None:
    assert RULES.supply.rearm_milli == 300
    assert RULES.supply.repair_milli == {
        "AIRBASE": 600, "FOB": 300, "HQ": 600, "PORT": 600, "SANCTUARY": 1200,
    }  # fmt: skip
    assert RULES.supply.facility_hp_per_stock == 10


def test_a_full_rearm_costs_half_for_the_tank_and_half_for_the_rounds() -> None:
    w = new_world()
    jet = aircraft(w, WEST, 0.0)
    jet.ammo = [0, 0]
    run(w, 34)  # the tank takes 9 900 + 100 of 34 ticks' 300s; the other 200 buy 16 gun rounds
    # Each weapon is half of the ammo share: a missile is 1.25 stock, a gun round 0.0125, so the
    # budget goes to the guns while it cannot yet cover a missile.
    assert (jet.fuel, jet.ammo) == (FULL, [0, 16])
    events = run(w, 33)  # 34 x 300 + 33 x 300 = 20 100: the last tick buys only the 200 left
    assert (jet.ammo, jet.ammo_credit, jet.rearm_milli) == ([4, 400], 0, 0)
    assert w.stock[WEST] == 1000 - 20 and consumed(events) == [(WEST, 20, "REARM")]
    assert stalled(events) == [] and run(w, 5) == []


def test_a_unit_with_ammo_and_no_fuel_pays_the_whole_cost_for_its_rounds() -> None:
    w = new_world()
    armor = ground(w, ARMOR, "static-hq", "ENEMY")  # 40 AG_CANNON rounds, loadout_cost 15
    armor.ammo = [0]
    events = run(w, 49)
    assert armor.ammo == [39] and w.stock["static-hq"] == 1000 - 14 and events == []  # one weapon
    events = run(w, 1)  # 50 x 300 = 15 000 thousandths in all
    assert armor.ammo == [40] and w.stock["static-hq"] == 985
    assert consumed(events) == [("static-hq", 15, "REARM")]


def test_rounds_are_paid_by_the_weapons_missing_share_and_a_missile_costs_more() -> None:
    w = new_world()
    jet = aircraft(w, WEST, FULL)
    jet.ammo = [0, 400]  # all 4 missiles gone: half of the ammo half, 5 of the 10 units
    events = run(w, 16)  # 16 x 300 = 4 800 thousandths: three missiles (3 x 1 250), none yet more
    assert jet.ammo == [3, 400] and jet.rearm_milli == 800 and events == []
    events = run(w, 1)  # the last 200 buy the fourth
    assert jet.ammo == [4, 400] and jet.ammo_credit == 0 and w.stock[WEST] == 995
    assert consumed(events) == [(WEST, 5, "REARM")]


def test_a_starved_base_restocks_only_guns_and_half_a_tank() -> None:
    w = new_world()
    w.stock[WEST] = 400  # floor 500
    jet = aircraft(w, WEST, 0.0)
    jet.ammo = [0, 0]
    events = run(w, 100)
    # half a tank is 5 units, the 400 gun rounds the other half of the ammo half (5 units)
    assert (jet.fuel, jet.ammo) == (FULL / 2, [0, 400])
    assert w.stock[WEST] == 400 - 10 and consumed(events) == [(WEST, 10, "REARM")]
    assert stalled(events) == []
    w.stock[WEST] = 600  # resupplied past the floor: the missiles and the rest of the tank are sold
    events = run(w, 100)
    assert (jet.fuel, jet.ammo) == (FULL, [4, 400]) and w.stock[WEST] == 590
    assert consumed(events) == [(WEST, 10, "REARM")]


def test_an_empty_base_stalls_once_and_the_sanctuary_rearms_free() -> None:
    w = new_world()
    w.stock[WEST] = 0
    jet = aircraft(w, WEST, FULL)
    jet.ammo = [0, 0]
    events = run(w, 10)
    assert stalled(events) == [(jet.id, WEST)] and consumed(events) == [] and jet.ammo == [0, 0]
    free = aircraft(w, "haven", 0.0)
    free.ammo = [0, 0]
    before = dict(w.stock)
    events = run(w, 80)
    assert (free.fuel, free.ammo) == (FULL, [4, 400]) and w.stock == before
    assert consumed(events) == [] and stalled(events) == []


def test_a_parked_ground_unit_restocks_only_on_a_friendly_base_node() -> None:
    w = new_world()
    inf = ground(w, INFANTRY, "fob-n-w")
    inf.ammo = [0]
    stray = ground(w, INFANTRY, "cross-n")  # a neutral node
    stray.ammo = [0]
    moving = ground(w, INFANTRY, "fob-n-w")
    moving.ammo, moving.path = [0], ["west-airbase"]
    run(w, 40)
    assert inf.ammo == [300] and stray.ammo == [0] and moving.ammo == [0]
    assert w.stock["fob-n-w"] == 500 - 5  # a whole loadout_cost 5 for 300 rounds


def test_a_wreck_and_a_paused_world_restock_nothing() -> None:
    w = new_world()
    wreck = ground(w, INFANTRY, "fob-n-w")
    wreck.ammo = [0]
    hurt(wreck, 5)
    assert wreck.damage_state == "DISABLED"
    wreck.wreck_left = 1000
    assert run(w, 60) == [] and wreck.ammo == [0] and wreck.hp == 5
    jet = aircraft(w, WEST, 0.0)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    assert run(w, 20) == [] and jet.fuel == 0.0 and w.stock[WEST] == 1000


# --- MunitionsDepleted ---------------------------------------------------------------------------


def test_the_last_missile_reports_munitions_depleted_with_guns_left() -> None:
    w = new_world()
    jet = aircraft(w, "east-airbase", FULL, "ENEMY", "ENEMY_STRIKE_FIGHTER")
    target = ground(w, INFANTRY, "cross-n")
    target.pos = Vec2(jet.pos.x - 3_000.0, jet.pos.y)
    w.contacts["ENEMY"][target.id] = Contact(target.kind, target.pos, target.vel, None, False)
    jet.ammo = [1, 400]  # AG_LIGHT: one left
    jet.state, jet.last_node = "EN_ROUTE", None  # airborne: a landed jet would rearm at once
    events = run(w, 1)
    (depleted,) = of(events, MunitionsDepleted)
    assert (depleted.entity_id, depleted.guns_only) == (jet.id, True) and jet.ammo[0] == 0
    assert of(run(w, 40), MunitionsDepleted) == []  # the gun firing says nothing


# --- repair ------------------------------------------------------------------------------------


def test_a_unit_pays_its_loadout_cost_by_the_hp_share_repaired_at_an_airbase() -> None:
    w = new_world()
    jet = hurt(aircraft(w, WEST, FULL), 30)  # MISSION_KILL; 70 hp short = 14 of the 20 units
    assert jet.damage_state == "MISSION_KILL"
    events = run(w, 117)  # 70 000 / 600 = 116.67 ticks
    assert changes(events) == [("MISSION_KILL", "DAMAGED"), ("DAMAGED", "HEALTHY")]
    assert (jet.hp, jet.damage_state) == (100, "HEALTHY")
    assert w.stock[WEST] == 1000 - 14 and consumed(events) == [(WEST, 14, "REPAIR")]
    (done,) = of(events, UnitRepaired)
    assert (done.entity_id, done.by_id, done.node_id) == (jet.id, None, WEST)


def test_repair_rate_and_price_follow_the_base_kind() -> None:
    w = new_world()
    inf = hurt(ground(w, INFANTRY, "fob-n-w"), 40)  # FOB 0.5 hp/s; 40 of 80 hp = 2.5 of 5
    events = run(w, 134)  # 40 000 / 300 = 133.3 ticks
    assert inf.hp == 80 and w.stock["fob-n-w"] == 500 - 2 and inf.repair_owed == 500
    assert consumed(events) == [("fob-n-w", 2, "REPAIR")] and len(of(events, UnitRepaired)) == 1
    hq = hurt(ground(w, ARMOR, "static-hq", "ENEMY"), 100)  # HQ 1.0: 100 hp of 200 = 7.5 of 15
    run(w, 167)  # 100 000 / 600 = 166.7 ticks
    assert hq.hp == 200 and w.stock["static-hq"] == 1000 - 7 and hq.repair_owed == 500


def test_the_sanctuary_repairs_free_twice_as_fast() -> None:
    w = new_world()
    jet = hurt(aircraft(w, "haven", FULL), 50)
    before = dict(w.stock)
    events = run(w, 42)  # 50 000 / 1 200 = 41.7 ticks
    assert jet.hp == 100 and w.stock == before and consumed(events) == []
    assert len(of(events, UnitRepaired)) == 1


def test_a_stalled_base_repairs_nothing_and_says_so_once() -> None:
    w = new_world()
    w.stock[WEST] = 0
    jet = hurt(aircraft(w, WEST, FULL), 50)
    events = run(w, 30)
    assert jet.hp == 50 and stalled(events) == [(jet.id, WEST)]


def test_repair_is_not_blocked_by_starvation() -> None:
    w = new_world()
    w.stock[WEST] = 400
    jet = hurt(aircraft(w, WEST, FULL), 90)
    run(w, 30)
    assert jet.hp == 100 and w.stock[WEST] == 398


def test_a_disabled_wreck_is_never_repaired_but_a_disabled_facility_is() -> None:
    w = new_world()
    wreck = hurt(aircraft(w, WEST, FULL), 5)
    wreck.wreck_left = 6000
    site = facility(w, WEST, "AIR_DEFENSE_SITE")
    site.hp, site.damage_state = 14, "DISABLED"  # the facility floor: 14 of 150
    events = run(w, 3)
    assert wreck.hp == 5 and state(wreck) == "DISABLED"
    assert site.hp > 14 and state(site) == "MISSION_KILL"  # back above the floor
    assert changes(events) == [("DISABLED", "MISSION_KILL")]


def test_a_facility_repairs_from_its_base_stock_at_a_tenth_of_an_hp_per_stock() -> None:
    w = new_world()
    site = facility(w, WEST, "AIR_DEFENSE_SITE")
    site.hp, site.damage_state = 14, "DISABLED"
    events = run(w, 227)  # 136 hp x 1 000 / 600 = 226.7 ticks
    assert (site.hp, site.damage_state) == (150, "HEALTHY")
    assert changes(events) == [
        ("DISABLED", "MISSION_KILL"), ("MISSION_KILL", "DAMAGED"), ("DAMAGED", "HEALTHY"),
    ]  # fmt: skip
    assert w.stock[WEST] == 1000 - 13 and site.repair_owed == 600  # 13.6 units
    assert consumed(events) == [(WEST, 13, "REPAIR")] and len(of(events, UnitRepaired)) == 1


def test_a_contested_base_does_not_repair_its_facilities() -> None:
    w = new_world()
    site = facility(w, WEST, "AIR_DEFENSE_SITE")
    site.hp, site.damage_state = 14, "DISABLED"
    w.capture[WEST] = CaptureBar("ENEMY", CAPTURE_FULL // 2)
    jet = hurt(aircraft(w, WEST, FULL), 50)
    run(w, 60)
    assert (site.hp, state(site)) == (14, "DISABLED") and w.stock[WEST] == 1000 - 7
    assert jet.hp == 50 + 36  # units still repair at a contested base: 36 hp cost 7.2 units
    del w.capture[WEST]
    run(w, 5)
    assert site.hp > 14


def sam(w: World) -> Entity:
    return facility(w, WEST, "AIR_DEFENSE_SITE")  # the SAM variant: AAA_GUN 400 and SAM 8


def test_a_site_fired_out_refills_from_its_base_at_the_facility_price() -> None:
    w = new_world()
    site = sam(w)
    site.ammo = [0, 0]
    events = run(w, 33)  # the SAM round is 1.25 stock: the budget buys gun rounds until it fills
    assert site.ammo[0] == 400 and site.ammo[1] < 8  # the guns first, the SAM waits
    events += run(w, 20)
    assert site.ammo == [400, 8] and w.stock[WEST] == 1000 - 10  # facility_rearm_cost 10
    assert consumed(events) == [(WEST, 10, "REARM")] and site.ammo_credit == 0


def test_a_starved_base_refills_a_sites_guns_only_and_an_empty_one_stalls() -> None:
    w = new_world()
    w.stock[WEST] = 400
    site = sam(w)
    site.ammo = [0, 0]
    events = run(w, 40)
    assert site.ammo == [400, 0] and w.stock[WEST] == 400 - 5
    assert consumed(events) == [(WEST, 5, "REARM")] and stalled(events) == []
    w.stock[WEST] = 0
    site.ammo = [0, 0]
    events = run(w, 10)
    assert stalled(events) == [(site.id, WEST)] and site.ammo == [0, 0]


def test_a_disabled_or_contested_site_does_not_restock_and_a_sanctuary_is_free() -> None:
    w = new_world()
    site = sam(w)
    site.ammo = [0, 0]
    site.hp, site.damage_state = 14, "DISABLED"
    run(w, 2)  # still under the floor's repair: Disabled does nothing
    assert site.ammo == [0, 0]
    site.hp, site.damage_state = 150, "HEALTHY"
    w.capture[WEST] = CaptureBar("ENEMY", CAPTURE_FULL // 2)
    run(w, 40)
    assert site.ammo == [0, 0]
    del w.capture[WEST]
    site.base_id = "haven"  # a sanctuary base: infinite stock
    before = dict(w.stock)
    run(w, 40)
    assert site.ammo == [400, 8] and w.stock == before


def test_a_repaired_radar_tracks_again() -> None:
    w = new_world()
    radar = facility(w, WEST, "RADAR_SITE")
    radar.hp, radar.damage_state = 14, "DISABLED"
    uav = w.spawn("ENEMY_RECON_UAV", "ENEMY", "AI_GARRISON", Vec2(170_000.0, 120_000.0))
    uav.state, uav.fuel = (
        "LANDED",
        RULES.fuel_s["ENEMY_RECON_UAV"],
    )  # 80 km: inside a Mission-kill radar's 96 km (120 x 0.8)
    run(w, 1)
    assert not tracked_by(w, "COALITION", uav.id)  # a Disabled radar senses nothing
    run(w, 10)
    assert state(radar) == "MISSION_KILL" and tracked_by(w, "COALITION", uav.id)


def test_a_paused_world_repairs_nothing() -> None:
    w = new_world()
    jet = hurt(aircraft(w, WEST, FULL), 50)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    assert run(w, 50) == [] and jet.hp == 50 and w.stock[WEST] == 1000


# --- auto-RTB (once, on the transition) --------------------------------------------------------


def flying(w: World, kind: UnitKind = JET, side: Side = "COALITION", x: float = 60_000.0) -> Entity:
    """An aircraft en route from (x, 120 km) to a far point; west-airbase is its nearest base."""
    e = aircraft(w, WEST, 3000.0, side, kind)
    e.pos, e.last_node, e.state = Vec2(x, 120_000.0), None, "EN_ROUTE"
    e.path = [Vec2(x, 20_000.0)]
    return e


def hit(w: World, target: Entity, damage: int) -> list[Event]:
    """One AAA_GUN hit of `damage` from an enemy armor at east-airbase."""
    shooter = ground(w, ARMOR, "east-airbase", "ENEMY") if target.side == "COALITION" else None
    shooter = shooter or ground(w, INFANTRY, "west-airbase")
    out: list[Event] = []
    _hit(
        w,
        RULES,
        COMBAT,
        shooter,
        target,
        dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=damage),
        out,
    )
    return out


def see(w: World, watcher_side: Side, target: Entity) -> None:
    w.contacts[watcher_side][target.id] = Contact(target.kind, target.pos, target.vel, None, False)


@pytest.mark.parametrize(("damage", "rtb"), [(70, True), (40, False)])  # 30 hp: Mission-kill
def test_an_airborne_aircraft_turns_back_when_it_reaches_mission_kill(
    damage: int, rtb: bool
) -> None:
    w = new_world()
    jet = flying(w)
    hit(w, jet, damage)
    assert (jet.state == "RTB") is rtb
    assert jet.path == (["west-airbase"] if rtb else [Vec2(60_000.0, 20_000.0)])


def test_a_later_order_is_not_overridden_after_the_rtb() -> None:
    w = new_world()
    jet = flying(w)
    hit(w, jet, 70)
    assert jet.state == "RTB"
    jet.state, jet.path = "EN_ROUTE", [Vec2(60_000.0, 20_000.0)]  # the operator's new order
    run(w, 5)
    assert jet.state == "EN_ROUTE" and jet.path == [Vec2(60_000.0, 20_000.0)]


def test_the_last_missile_sends_an_aircraft_home_once() -> None:
    w = new_world()
    jet = flying(w)
    jet.ammo = [1, 400]
    target = ground(w, INFANTRY, "cross-n", "ENEMY")
    target.pos = Vec2(63_000.0, 120_000.0)
    see(w, "COALITION", target)
    events = run(w, 1)
    assert len(of(events, MunitionsDepleted)) == 1 and jet.ammo[0] == 0
    assert (jet.state, jet.path) == ("RTB", ["west-airbase"])


def test_a_missile_only_fighter_goes_home_on_its_last_missile() -> None:
    w = new_world()
    e = flying(w, "ENEMY_FIGHTER", "ENEMY", 300_000.0)
    e.ammo = [1]
    prey = flying(w, JET, "COALITION", 310_000.0)
    see(w, "ENEMY", prey)
    run(w, 1)
    assert e.ammo == [0] and e.state == "RTB" and e.path == ["east-airbase"]


def test_a_missile_empty_aircraft_can_be_ordered_off_a_starved_base() -> None:
    w = new_world()
    w.stock[WEST] = 400  # starved: only guns restock
    jet = aircraft(w, WEST, FULL)
    jet.ammo = [0, 400]
    jet.path = ["fob-n-w"]
    run(w, 3)
    assert jet.state == "EN_ROUTE" and jet.ammo == [0, 400]  # takes off with what is left


def test_a_guns_only_unit_never_goes_home_for_ammo() -> None:
    w = new_world()
    armor = ground(w, ARMOR, "cross-n", "ENEMY")
    armor.ammo = [1]
    prey = ground(w, INFANTRY, "cross-n")
    prey.pos = Vec2(armor.pos.x + 2_000.0, armor.pos.y)
    see(w, "ENEMY", prey)
    run(w, 1)
    assert armor.ammo == [0] and armor.path == []


def test_a_mission_killed_ground_unit_drives_to_the_nearest_friendly_base_then_obeys_orders() -> (
    None
):
    w = new_world()
    armor = ground(w, ARMOR, "cross-n", "ENEMY")
    armor.hp = 100
    hit(w, armor, 80)  # 200 hp, armor 0.5: 40 dmg, 60 hp: Mission-kill (below 70)
    assert armor.damage_state == "MISSION_KILL" and armor.path == ["cross-n", "fob-n-e"]
    armor.path = ["fob-n-w"]  # a later MOVE stands
    run(w, 5)
    assert armor.path == ["fob-n-w"]
    at_base = ground(w, ARMOR, "fob-n-e", "ENEMY")
    at_base.hp = 100
    hit(w, at_base, 80)
    assert at_base.path == []  # already at a base: stays


def test_a_truck_repairs_for_free_at_a_base_and_arms_nothing() -> None:
    w = new_world()
    truck = hurt(ground(w, "LOGI_TRUCK", "west-airbase"), 10)  # loadout_cost 0
    events = run(w, 118)  # 70 hp at 600 thousandths a tick
    assert truck.hp == 80 and w.stock[WEST] == 1000 and consumed(events) == []
    assert len(of(events, UnitRepaired)) == 1


# --- conservation, snapshots, determinism ------------------------------------------------------

ROLES = ("STRIKE", "RECON", "LOGI")
ACTION = st.one_of(
    st.tuples(st.just("join"), st.sampled_from(ROLES), st.sampled_from([*sorted(POS), None])),
    st.tuples(st.just("steps"), st.integers(1, 60), st.just(None)),
    st.tuples(st.just("stock"), st.integers(0, 3), st.integers(0, 600)),
    st.tuples(st.just("hurt"), st.integers(0, 30), st.integers(1, 100)),
    st.tuples(st.just("kill"), st.integers(0, 30), st.just(None)),
)


def accounted(w: World, spent: int) -> int:
    return total(w) + spent + sum(e.rearm_spent + e.repair_spent for e in w.entities())


@given(st.lists(ACTION, max_size=25))
def test_stock_balances_exactly_with_ammo_and_repair_debits(
    actions: list[tuple[str, Any, Any]],
) -> None:
    w, n, spent = new_world(), 0, 0
    expected, rear = accounted(w, 0), set(RULES.supply.rear.values())
    bases = ("west-airbase", "fob-n-w", "fob-s-w", "static-hq")

    def tell(events: list[Event]) -> None:
        nonlocal spent, expected
        spent += sum(amount for _, amount, _ in consumed(events))
        for ev in of(events, UnitSpawned):
            if ev.node_id in rear:
                expected += w.get(ev.entity_id).cargo or 0

    for kind, a, b in actions:
        if kind == "join":
            n += 1
            tell(send(w, join(n, a, b)))
        elif kind == "steps":
            tell(run(w, a))
        elif kind == "hurt":  # damage and spend rounds on whatever stands at a base
            parked = [e for e in w.entities() if not e.path and e.damage_state != "DISABLED"]
            if parked:
                e = parked[a % len(parked)]
                hurt(e, max(b, COMBAT.units[e.kind].cuts[0]))
                e.ammo = [0 for _ in e.ammo]
        elif kind == "kill":  # lost mid-stop: shot down, a fuel crash or a capture lose_unit's all
            stopped = [e for e in w.entities() if e.rearm_spent or e.repair_spent] or list(
                w.entities()
            )
            if stopped:
                out: list[Event] = []
                lose_unit(w, stopped[a % len(stopped)], out)
                tell(out)
        else:
            node = bases[a]
            expected += b - w.stock[node]
            w.stock[node] = b
        assert accounted(w, spent) == expected
        assert all(0 <= s <= RULES.supply.max_stock[k] for k, s in w.stock.items())


def midway() -> World:
    """A jet part-way through rearming and a facility part-way through repair."""
    w = new_world()
    jet = aircraft(w, WEST, FULL)
    jet.ammo = [1, 100]
    hurt(jet, 40)
    site = facility(w, WEST, "AIR_DEFENSE_SITE")
    site.hp, site.damage_state = 14, "DISABLED"
    run(w, 7)
    assert jet.rearm_spent and jet.repair_milli
    return w


def test_snapshot_round_trips_mid_rearm_and_the_hash_covers_every_carry() -> None:
    w = midway()
    h = state_hash(w)
    again = load(save(w))
    again.rules = RULES
    assert state_hash(again) == h
    assert run(again, 60) == run(w, 60) and state_hash(again) == state_hash(w)
    w = midway()
    jet = next(e for e in w.entities() if e.kind == JET)
    for name in ("ammo_credit", "repair_milli", "repair_debt", "repair_owed", "repair_spent"):
        before, h = getattr(jet, name), state_hash(w)
        setattr(jet, name, before + 1)
        assert state_hash(w) != h, name
        setattr(jet, name, before)


def test_load_refuses_bad_rearm_progress_and_format_14() -> None:
    import msgpack

    raw = msgpack.unpackb(save(midway()), raw=False)
    air = next(e for e in raw["entities"] if e["state"] is not None)
    air["repair_milli"] = 1000
    with pytest.raises(ValueError, match="repair_milli"):
        load(msgpack.packb(raw, use_bin_type=True))
    air["repair_milli"] = 0
    air["repair_owed"] = 1000
    with pytest.raises(ValueError, match="repair_owed"):
        load(msgpack.packb(raw, use_bin_type=True))
    air["repair_owed"] = 0
    air["ammo_credit"] = -1
    with pytest.raises(ValueError, match="ammo_credit"):
        load(msgpack.packb(raw, use_bin_type=True))
    air["ammo_credit"] = 0
    raw["v"] = 14
    with pytest.raises(ValueError, match="unsupported snapshot format version 14"):
        load(msgpack.packb(raw, use_bin_type=True))


def scenario() -> World:
    w = midway()
    for k, (role, node) in enumerate([("STRIKE", "fob-n-w"), ("LOGI", "fob-s-w")], start=1):
        send(w, join(k, role, node))
    run(w, 400)
    return w


def test_two_runs_hash_alike_and_across_hash_seeds() -> None:
    import os
    import subprocess
    import sys

    assert state_hash(scenario()) == state_hash(scenario())
    child = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from test_rearm import scenario\n"
        "from nexus.core.world import state_hash; print(state_hash(scenario()))"
    )

    def hashed(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", child, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert hashed("1") == hashed("2") == state_hash(scenario())


def test_repair_spend_is_its_own_supply_consumed_cause_apart_from_rearm() -> None:
    w = new_world()
    jet = hurt(aircraft(w, WEST, 0.0), 50)  # 5 units of repair, 10 of tank
    jet.ammo = [2, 400]  # half the missiles: 2.5 units
    events = [e for e in run(w, 140) if isinstance(e, SupplyConsumed)]
    assert sorted((e.cause, e.amount) for e in events) == [("REARM", 12), ("REPAIR", 10)]


def test_a_unit_lost_mid_stop_reports_what_the_stop_cost() -> None:
    w = new_world()
    jet = hurt(aircraft(w, WEST, FULL), 50)
    jet.ammo = [0, 400]
    run(w, 30)
    assert jet.rearm_spent and jet.repair_spent
    before = (jet.rearm_spent, jet.repair_spent)
    out: list[Event] = []
    lose_unit(w, jet, out)
    assert [(e.cause, e.amount) for e in of(out, SupplyConsumed)] == [
        ("REARM", before[0]),
        ("REPAIR", before[1]),
    ]
    assert [type(e).__name__ for e in out][:2] == ["SupplyConsumed", "SupplyConsumed"]


@pytest.mark.parametrize(
    ("changes_to", "message"),
    [
        ({"last_node": None, "rearm_spent": 3}, "no node to report"),
        ({"last_node": None, "stalled": True}, "no node to report"),
        ({"repair_milli": 5}, "repair progress at full hp"),
        ({"ammo_credit": 10**12}, "ammo_credit above"),
        ({"ammo_credit": 800}, "ammo_credit above"),  # every round back: below n x lcm = 800
    ],
)
def test_a_restored_world_with_bad_rearm_state_is_refused(
    changes_to: dict[str, Any], message: str
) -> None:
    w = new_world()
    jet = aircraft(w, WEST, FULL)
    validate(w, RULES)  # a clean world passes
    for field, value in changes_to.items():
        setattr(jet, field, value)
    with pytest.raises(ValueError, match=message):
        validate(w, RULES)


def test_a_loadout_with_an_unsafe_ammo_lcm_is_refused_at_load() -> None:
    from nexus.core.rules import WeaponRules, _check_ammo_bound

    cr = COMBAT
    base = cr.weapons["AA_LIGHT"]
    primes = (97, 89, 83, 79, 73, 71, 67, 61)  # eight coprime loads: lcm about 1e15
    loadout = tuple(dataclasses.replace(base, id=f"W{i}", ammo=p) for i, p in enumerate(primes))
    bad = dataclasses.replace(cr, loadouts={(JET, None): loadout})
    with pytest.raises(ValueError, match="least common multiple"):
        _check_ammo_bound(bad, RULES.supply)
    _check_ammo_bound(cr, RULES.supply)  # the shipped loads (lcm 400) are far inside
    assert isinstance(base, WeaponRules)


def restorable(w: World) -> None:
    """The end-of-tick state saves, loads and validates (what `recovery.restore` does)."""
    again = load(save(w))
    again.rules = RULES
    validate(again, RULES)


def test_a_bar_appearing_over_a_repairing_facility_leaves_a_restorable_state() -> None:
    w = new_world()
    site = facility(w, WEST, "AIR_DEFENSE_SITE")
    site.hp, site.damage_state = 14, "DISABLED"
    for _ in range(100):
        run(w, 1)
        if site.repair_spent:
            break
    assert site.repair_spent  # mid-stop, a whole unit paid but not yet reported
    ground(w, ARMOR, WEST, "ENEMY")  # capture starts its bar after logistics ran this tick
    run(w, 1)
    assert WEST in w.capture and site.repair_spent  # the stop ended after logistics: counters wait
    restorable(w)
    run(w, 1)
    assert site.repair_spent == 0
    restorable(w)


def test_a_unit_escaping_a_flipped_base_mid_stop_leaves_a_restorable_state() -> None:
    w = new_world(dataclasses.replace(RULES, armed=frozenset()))  # nobody contests the bar
    inf = hurt(ground(w, INFANTRY, "fob-n-w"), 20)
    for _ in range(200):
        run(w, 1)
        if inf.repair_spent:
            break
    assert inf.repair_spent
    ground(w, ARMOR, "fob-n-w", "ENEMY")
    w.capture["fob-n-w"] = CaptureBar("ENEMY", CAPTURE_FULL - 1)
    run(w, 1)
    assert w.owner["fob-n-w"] == "ENEMY" and inf.path  # flipped: it drives off
    restorable(w)


@given(st.lists(ACTION, max_size=20))
def test_every_end_of_tick_state_of_real_steps_validates(
    actions: list[tuple[str, Any, Any]],
) -> None:
    w, n = new_world(), 0
    for kind, a, b in actions:
        if kind == "join":
            n += 1
            send(w, join(n, a, b))
        elif kind == "steps":
            for _ in range(min(a, 15)):
                run(w, 1)
                restorable(w)
        elif kind == "hurt":
            parked = [e for e in w.entities() if not e.path and e.damage_state != "DISABLED"]
            if parked:
                e = parked[a % len(parked)]
                hurt(e, max(b, COMBAT.units[e.kind].cuts[0]))
                e.ammo = [0 for _ in e.ammo]
        elif kind == "kill":
            live = list(w.entities())
            if live:
                lose_unit(w, live[a % len(live)], [])
        else:
            w.stock[("west-airbase", "fob-n-w", "fob-s-w", "static-hq")[a]] = b
        restorable(w)
