"""NX-124 part 2: crew survival, downed-crew markers and the damaged slowdown (COMBAT CB-6, CB-8;
GAMEPLAY §6a; Q-SIM-68, Q-SIM-65).

Shipped numbers: survival chance 0.75 aircraft, 0.60 ENEMY_ARMOR, 0.50 GARRISON_INFANTRY, 0.70
LOGI_TRUCK and ENEMY_CONVOY; a marker lasts 10 game minutes (6,000 running ticks);
`damaged_speed_mult` 0.75 (a STRIKE_FIGHTER flies 250 m/s, stalls at 100). One roll is exactly one
draw on the `combat` stream, made at the first of Disabled or Destroyed.
"""

import dataclasses
from typing import Any

import pytest
from test_capture import about_to_flip, lose_all_other_bases
from test_capture import new_world as capture_world
from test_capture import put as put_at
from test_combat import (
    ARMOR,
    COMBAT,
    CONVOY,
    ENEMY_JET,
    INFANTRY,
    JET,
    RADAR,
    RULES,
    TRUCK,
    new_world,
    of,
    put,
    run,
)

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.crew_downed import CrewDowned
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core.combat import _hit
from nexus.core.rng import RngStream, SimRng
from nexus.core.rules import Rules
from nexus.core.world import Entity, Vec2, World, load, lose_unit, roll_crew, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config

UAV: UnitKind = "RECON_UAV"
RULES_CAMPAIGN = load_campaign_config().rules


def surviving(p: float) -> Rules:
    """Rules where every crew survives with chance `p`."""
    units = {
        k: dataclasses.replace(u, crew_survival=p if u.crew else 0.0)
        for k, u in COMBAT.units.items()
    }
    return dataclasses.replace(RULES, combat=dataclasses.replace(COMBAT, units=units))


def combat_state(w: World) -> dict[str, str]:
    return w.rng.to_state()[RngStream.COMBAT.value]


def after_draws(seed: int, n: int) -> dict[str, str]:
    ref = SimRng(seed)
    for _ in range(n):
        ref.stream(RngStream.COMBAT).random()
    return ref.to_state()[RngStream.COMBAT.value]


# --- the roll ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "side", "chance"),
    [
        (JET, "COALITION", 0.75), (ENEMY_JET, "ENEMY", 0.75), (ARMOR, "ENEMY", 0.60),
        (INFANTRY, "COALITION", 0.50), (TRUCK, "COALITION", 0.70), (CONVOY, "ENEMY", 0.70),
    ],
)  # fmt: skip
def test_the_survival_rate_over_many_seeds_matches_the_kinds_chance(
    kind: UnitKind, side: Any, chance: float
) -> None:
    n, downed = 3000, 0
    for seed in range(n):
        w = new_world(RULES, seed)
        out: list[Event] = []
        roll_crew(w, put(w, kind, side, 0), out)
        downed += len(of(out, CrewDowned))
    assert downed / n == pytest.approx(chance, abs=0.035)  # 5 sigma at n = 3000


@pytest.mark.parametrize("kind", [UAV, RADAR, "AIR_DEFENSE_SITE"])
def test_a_unit_with_no_crew_draws_nothing(kind: UnitKind) -> None:
    w = new_world()
    roll_crew(w, put(w, kind, "COALITION" if kind != "AIR_DEFENSE_SITE" else "ENEMY", 0), [])
    assert w.rng.to_state() == SimRng(12345).to_state()


def test_a_crewed_unit_draws_exactly_once_and_below_the_chance_is_downed() -> None:
    for p, downed in ((1.0, True), (0.0, False)):
        w = new_world(surviving(p))
        out: list[Event] = []
        jet = put(w, JET, "COALITION", 1_234.6, 99.4)
        roll_crew(w, jet, out)
        assert combat_state(w) == after_draws(12345, 1)
        assert len(of(out, CrewDowned)) == (1 if downed else 0)
        if downed:
            (event,) = of(out, CrewDowned)
            assert (event.marker_id, event.entity_id, event.side) == (1, jet.id, "COALITION")
            assert (event.pos.x_m, event.pos.y_m) == (1_235, 99)
            assert w.crew_markers[1].pos == jet.pos
        else:
            assert w.crew_markers == {}


# --- the marker --------------------------------------------------------------------------------


def test_a_downed_crew_marker_lasts_ten_game_minutes_and_a_pause_freezes_it() -> None:
    w = new_world(surviving(1.0))
    roll_crew(w, put(w, JET, "COALITION", 0), [])
    roll_crew(w, put(w, ARMOR, "ENEMY", 5_000), [])
    assert sorted(w.crew_markers) == [1, 2] and w._next_marker_id == 3
    run(w, 3_000)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    assert run(w, 500) == [] and len(w.crew_markers) == 2  # frozen, not aged
    w.campaign.clock_paused, w.campaign.pause_reason = False, None
    run(w, 3_000)  # made for running tick 1, it is on the map through tick 6,000
    assert len(w.crew_markers) == 2
    run(w, 1)
    assert w.crew_markers == {}  # removed on running tick 6,001


# --- once per unit, on every loss path ---------------------------------------------------------


def test_a_wreck_rolled_when_it_became_disabled_and_not_again_when_it_dies() -> None:
    w = new_world(surviving(0.5))
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000)  # LANDED: a Disabled one is a wreck
    jet.hp = 12
    gun = dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=5)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, shooter, jet, gun, out)
    assert jet.damage_state == "DISABLED" and combat_state(w) == after_draws(12345, 1)
    _hit(w, RULES, COMBAT, shooter, jet, dataclasses.replace(gun, damage=50), out)
    assert w.find(jet.id) is None and combat_state(w) == after_draws(12345, 1)  # no second roll


def test_a_wreck_removed_by_its_timeout_draws_nothing_more() -> None:
    w = new_world(surviving(0.5))
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000)
    jet.hp = 12
    _hit(
        w, RULES, COMBAT, shooter, jet, dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=5), []
    )
    run(w, 6_000)
    assert w.find(jet.id) is None and combat_state(w) == after_draws(12345, 1)


def test_a_direct_kill_an_airborne_disable_and_a_fuel_crash_each_roll_once() -> None:
    gun = dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=100)
    w = new_world(surviving(1.0))  # a killing blow from full hp
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    truck = put(w, TRUCK, "COALITION", 1_000)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, shooter, truck, gun, out)
    assert [type(e) for e in out] == [UnitDestroyed, CrewDowned]
    assert combat_state(w) == after_draws(12345, 1)
    air = put(w, JET, "COALITION", 2_000)  # airborne, hit to Disabled: destroyed at once
    air.state, air.fuel, air.hp = "EN_ROUTE", 3_000.0, 16
    out = []
    _hit(w, RULES, COMBAT, shooter, air, dataclasses.replace(gun, damage=10), out)
    assert [type(e) for e in out] == [UnitDestroyed, CrewDowned]
    assert combat_state(w) == after_draws(12345, 2)
    dry = put(w, JET, "COALITION", 3_000)  # out of fuel after this tick's move
    dry.state, dry.fuel, dry.path = "EN_ROUTE", 0.3, [Vec2(90_000.0, 0.0)]
    events = run(w)
    assert [type(e) for e in events if isinstance(e, UnitDestroyed | CrewDowned)] == [
        UnitDestroyed,
        CrewDowned,
    ]
    assert combat_state(w) == after_draws(12345, 3) and sorted(w.crew_markers) == [1, 2, 3]


def test_a_unit_lost_at_a_flipped_base_rolls_its_crew() -> None:
    for p, expected in ((1.0, 1), (0.0, 0)):
        w = capture_world()
        w.rules = dataclasses.replace(RULES_CAMPAIGN, combat=surviving(p).combat)
        about_to_flip(w, "fob-n-w", "ENEMY")
        lose_all_other_bases(w, "COALITION", "fob-n-w")
        mine = put_at(w, TRUCK, "COALITION", "fob-n-w", n=7)
        put_at(w, ARMOR, "ENEMY", "fob-n-w")
        events = run(w)
        assert [e.entity_id for e in of(events, UnitDestroyed)] == [mine.id]
        assert len(of(events, CrewDowned)) == expected


def test_lose_unit_rolls_a_never_disabled_unit_and_skips_a_disabled_one() -> None:
    w = new_world(surviving(1.0))
    fresh = put(w, TRUCK, "COALITION", 0)
    wreck = put(w, TRUCK, "COALITION", 10)
    wreck.hp, wreck.damage_state = 5, "DISABLED"
    out: list[Event] = []
    lose_unit(w, fresh, out)
    lose_unit(w, wreck, out)
    assert [e.entity_id for e in of(out, CrewDowned)] == [fresh.id]


# --- snapshot ----------------------------------------------------------------------------------


def test_markers_round_trip_in_the_snapshot_and_the_hash_covers_them() -> None:
    w = new_world(surviving(1.0))
    roll_crew(w, put(w, JET, "COALITION", 7.25, 8.5), [])
    run(w, 10)
    h = state_hash(w)
    again = load(save(w))
    again.rules = w.rules
    assert again.crew_markers == w.crew_markers and state_hash(again) == h
    marker = w.crew_markers[1]
    for name, value in (("expires", marker.expires + 1), ("pos", Vec2(7.0, 8.5))):
        before = getattr(marker, name)
        setattr(marker, name, value)
        assert state_hash(w) != h, name
        setattr(marker, name, before)
    w._next_marker_id += 1
    assert state_hash(w) != h


def test_load_refuses_a_bad_marker() -> None:
    import msgpack

    w = new_world(surviving(1.0))
    roll_crew(w, put(w, JET, "COALITION", 0), [])
    raw = msgpack.unpackb(save(w), raw=False)
    marker = raw["crew_markers"][0]
    for field, value in (("id", 2), ("expires", 0), ("entity_id", 99), ("side", "NEUTRAL")):
        bad = dict(marker, **{field: value})
        with pytest.raises(ValueError, match=r"crew|marker"):
            load(msgpack.packb(dict(raw, crew_markers=[bad]), use_bin_type=True))


# --- the damaged slowdown ----------------------------------------------------------------------


def fly(w: World, e: Entity, ticks: int = 1) -> float:
    start = e.pos.x
    run(w, ticks)
    return e.pos.x - start


def test_a_damaged_aircraft_flies_at_three_quarters_speed() -> None:
    w = new_world()
    healthy, damaged = put(w, JET, "COALITION", 0, 0), put(w, JET, "COALITION", 0, 5_000)
    for e in (healthy, damaged):
        e.state, e.fuel, e.path = "EN_ROUTE", 3_000.0, [Vec2(900_000.0, e.pos.y)]
    damaged.hp, damaged.damage_state = 60, "DAMAGED"
    assert fly(w, healthy, 10) == pytest.approx(250.0 * 0.6 * 10)
    assert damaged.pos.x == pytest.approx(187.5 * 0.6 * 10) and damaged.state == "EN_ROUTE"


def test_the_damaged_speed_never_drops_below_the_stall_speed() -> None:
    slow = dataclasses.replace(RULES, combat=dataclasses.replace(COMBAT, damaged_speed_mult=0.3))
    w = new_world(slow)
    e = put(w, JET, "COALITION", 0)
    e.state, e.fuel, e.path = "EN_ROUTE", 3_000.0, [Vec2(900_000.0, 0.0)]
    e.hp, e.damage_state = 60, "DAMAGED"
    assert fly(w, e, 10) == pytest.approx(100.0 * 0.6 * 10)  # 75 m/s clamped up to 100


def test_a_damaged_ground_unit_drives_at_three_quarters_speed() -> None:
    w = new_world()
    ok, bad = put(w, ARMOR, "ENEMY", 130_000, 60_000), put(w, ARMOR, "ENEMY", 130_000, 60_000)
    for e in (ok, bad):
        e.last_node, e.path = "fob-n-w", ["cross-n"]
    bad.hp, bad.damage_state = 140, "DAMAGED"  # 200 hp: below 70 % is 140
    run(w, 10)
    assert ok.pos.x - 130_000 == pytest.approx(20.0 * 0.6 * 10)
    assert bad.pos.x - 130_000 == pytest.approx(20.0 * 0.75 * 0.6 * 10)


def test_bingo_uses_the_damaged_speed() -> None:
    w = new_world()
    ok, bad = put(w, JET, "COALITION", 60_000, 120_000), put(w, JET, "COALITION", 60_000, 120_000)
    for e in (ok, bad):
        e.state, e.path = "EN_ROUTE", [Vec2(60_000.0, 20_000.0)]
        e.fuel = 540.0 + 30_000.0 / 250.0 + 1.0  # the reserve + the flight home at 250 m/s + 1 s
    bad.hp, bad.damage_state = 60, "DAMAGED"
    run(w, 1)
    assert ok.state == "EN_ROUTE" and bad.state == "RTB"  # the slower flight needs more fuel
