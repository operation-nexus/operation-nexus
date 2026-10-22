"""NX-124 part 1: targeting, shots, hit rolls, damage, damage states, destruction and wrecks
(COMBAT CB-1..CB-7, CB-9, CB-12; SIM-CORE SC-5, SC-11, SC-13).

Shipped strait-1 numbers (Q-SIM-65, `sim.time_scale` 6, so 0.6 world s per tick): AG_LIGHT range
10 km, 300 m/s, reload 10 s (17 ticks), 4 rounds; SMALL_ARMS and the guns land on the fire tick;
`combat.disabled_timeout_s` 600 s is 6,000 ticks; hp thresholds 0.70 / 0.35 / 0.10. Worlds here
start empty (no facilities) and never run a sensing pass (`track_every_ticks` is huge): contacts
are set by hand, so each test decides exactly what a side tracks.
"""

import dataclasses
import os
import subprocess
import sys
from fractions import Fraction
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import cid, join

from nexus.contracts.gen.common.enums import AltBand, Side, UnitKind
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.crew_downed import CrewDowned
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_damage_state_changed import UnitDamageStateChanged
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core import combat
from nexus.core.combat import _hit, _pk, _range_factor
from nexus.core.fog import is_off_facility
from nexus.core.rng import SimRng
from nexus.core.rules import CombatRules, Rules, WeaponRules
from nexus.core.step import step
from nexus.core.world import Campaign, Contact, Entity, Shot, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import ConfigPaths, load_campaign_config
from nexus.runtime.units import load_catalog

CONFIG = load_campaign_config()
# No campaign layer, no sensing pass: these tests are about combat (NX-126, NX-150).
RULES = dataclasses.replace(
    CONFIG.rules, campaign=None, tasking=None, track_every_ticks=10**9
)  # NX-374: board off


def _combat(rules: Rules) -> CombatRules:
    assert rules.combat is not None
    return rules.combat


COMBAT = _combat(RULES)
CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
JET: UnitKind = "STRIKE_FIGHTER"
ENEMY_JET: UnitKind = "ENEMY_STRIKE_FIGHTER"
ARMOR: UnitKind = "ENEMY_ARMOR"
INFANTRY: UnitKind = "GARRISON_INFANTRY"
CONVOY: UnitKind = "ENEMY_CONVOY"
TRUCK: UnitKind = "LOGI_TRUCK"
RADAR: UnitKind = "RADAR_SITE"
_OTHER: dict[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}


def new_world(rules: Rules = RULES, seed: int = 12345) -> World:
    return World.new(Campaign(CAMPAIGN_ID, seed, "cfg-test"), rules)


def put(
    w: World, kind: UnitKind, side: Side, x: float, y: float = 0.0, *, cmd: int | None = None
) -> Entity:
    """A parked unit at (x, y) m; an aircraft stands LANDED with full fuel."""
    e = w.spawn(
        kind, side, "AI_GARRISON" if cmd is None else "COMMANDER", Vec2(x, y),
        commander_id=None if cmd is None else cid(cmd),
    )  # fmt: skip
    if w.rules is not None and w.rules.domain[kind] == "AIR":
        e.state, e.fuel = "LANDED", w.rules.fuel_s[kind]
    return e


def track(w: World, watcher: Entity, target: Entity, *, painted: bool = False) -> None:
    """`watcher`'s side tracks `target` as of now."""
    known = w.contacts[watcher.side]
    known[target.id] = Contact(target.kind, target.pos, target.vel, None, painted)
    w.contacts[watcher.side] = dict(sorted(known.items()))


def run(w: World, ticks: int = 1) -> list[Event]:
    events: list[Event] = []
    for _ in range(ticks):
        events += step(w, [])
    return events


def of[T: Event](events: list[Event], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


def with_weapon(rules: Rules, weapon_id: str, **changes: Any) -> Rules:
    """`rules` with one weapon profile changed everywhere it is listed."""
    cr = rules.combat
    assert cr is not None
    new = dataclasses.replace(cr.weapons[weapon_id], **changes)
    loadouts = {
        key: tuple(new if w.id == weapon_id else w for w in ws) for key, ws in cr.loadouts.items()
    }
    return dataclasses.replace(
        rules,
        combat=dataclasses.replace(cr, weapons={**cr.weapons, weapon_id: new}, loadouts=loadouts),
    )


def sure(weapon_id: str, **changes: Any) -> Rules:
    """Rules where `weapon_id` always hits when it can (Pk 1, no cap)."""
    rules = with_weapon(RULES, weapon_id, base_pk=1.0, **changes)
    assert rules.combat is not None
    return dataclasses.replace(rules, combat=dataclasses.replace(rules.combat, pk_cap=1.0))


# --- CB-1 targeting -----------------------------------------------------------------------------


def test_targets_by_threat_then_distance_then_id() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    near_convoy = put(w, CONVOY, "ENEMY", 1_000)  # threat 20, nearest
    radar = put(w, RADAR, "ENEMY", 3_000)  # threat 50
    far_armor = put(w, ARMOR, "ENEMY", 5_000)  # threat 60
    tied_armor = put(w, ARMOR, "ENEMY", 5_000)  # same threat and distance: the higher id loses
    for t in (near_convoy, radar, far_armor, tied_armor):
        track(w, jet, t)
    (fired,) = of(run(w), WeaponFired)
    assert (fired.shooter_id, fired.target_id, fired.weapon) == (jet.id, far_armor.id, "AG_LIGHT")
    # Equal threat: the closer one wins, whatever its id.
    w2 = new_world()
    jet2 = put(w2, JET, "COALITION", 0)
    far = put(w2, ARMOR, "ENEMY", 6_000)
    close = put(w2, ARMOR, "ENEMY", 2_000)
    for t in (far, close):
        track(w2, jet2, t)
    assert of(run(w2), WeaponFired)[0].target_id == close.id


def test_only_a_tracked_target_is_ever_shot() -> None:
    w = new_world()
    put(w, JET, "COALITION", 0)
    last_known = put(w, ARMOR, "ENEMY", 1_000)
    unseen = put(w, ARMOR, "ENEMY", 1_500)
    w.contacts["COALITION"][last_known.id] = Contact(ARMOR, last_known.pos, last_known.vel, 3)
    assert unseen.id not in w.contacts["COALITION"]
    assert of(run(w, 5), WeaponFired) == []  # a last-known track or no track: nothing to shoot


def test_a_weapon_needs_range_domain_and_band() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    out_of_range = put(w, ARMOR, "ENEMY", 10_001)  # AG_LIGHT reaches 10 km
    wrong_domain = put(w, RADAR, "ENEMY", 500)  # STATIC: AG_LIGHT can, AA_LIGHT cannot
    high = put(w, ENEMY_JET, "ENEMY", 500)
    high.alt_band = "HIGH"  # AA_LIGHT reaches LOW and MED only
    for t in (out_of_range, wrong_domain, high):
        track(w, jet, t)
    fired = of(run(w), WeaponFired)
    assert [(f.weapon, f.target_id) for f in fired] == [("AG_LIGHT", wrong_domain.id)]
    high.alt_band = "MED"
    w.contacts["COALITION"][high.id].pos = high.pos
    assert [(f.weapon, f.target_id) for f in of(run(w, 4), WeaponFired)] == [
        ("AA_LIGHT", high.id)
    ]  # now in band: the gun fires (AG_LIGHT is reloading)


def test_a_unit_fires_each_ready_weapon_once_in_catalog_order() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    ground = put(w, ARMOR, "ENEMY", 2_000)
    air = put(w, ENEMY_JET, "ENEMY", 2_000)
    track(w, jet, ground)
    track(w, jet, air)
    fired = of(run(w), WeaponFired)
    assert [(f.weapon, f.target_id) for f in fired] == [
        ("AG_LIGHT", ground.id),
        ("AA_LIGHT", air.id),
    ]
    assert jet.ammo == [3, 399] and jet.reload == [
        17,
        4,
    ]  # 10 s and 2 s at 0.6 s a tick, rounded up


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(
                [
                    ARMOR,
                    CONVOY,
                    "ENEMY_FIGHTER",
                    "ENEMY_RECON_UAV",
                    RADAR,
                    "AIR_DEFENSE_SITE",
                    ENEMY_JET,
                ]
            ),
            st.integers(-12_000, 12_000),
            st.integers(-12_000, 12_000),
            st.sampled_from(["tracked", "last_known", "unseen"]),
            st.sampled_from(["NOE", "LOW", "MED", "HIGH"]),
        ),
        max_size=8,
    )
)
def test_cb1_chosen_target_is_valid_and_best(
    scene: list[tuple[UnitKind, int, int, str, AltBand]],
) -> None:
    """The brute force reads the content files, not `Rules`: threat, domain, range, bands."""
    paths = ConfigPaths()
    catalog = load_catalog(paths.units, paths.weapons, paths.roles)
    unit = {u.kind: u for u in catalog.units}
    weapon = {wp.id: wp for wp in catalog.weapons}
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    enemies = []
    for kind, x, y, how, band in scene:
        e = put(w, kind, "ENEMY", x, y)
        if unit[kind].domain == "AIR":
            e.alt_band = band
        if how == "tracked":
            track(w, jet, e)
        elif how == "last_known":
            w.contacts["COALITION"][e.id] = Contact(kind, e.pos, e.vel, 2)
        enemies.append((e, how))
    expected = []
    for wid in unit[JET].weapons:
        wp = weapon[wid]
        valid = [
            (-unit[e.kind].threat, e.pos.x**2 + e.pos.y**2, e.id)
            for e, how in enemies
            if how == "tracked"
            and unit[e.kind].domain in wp.targets
            and (unit[e.kind].domain != "AIR" or e.alt_band in wp.bands)
            and e.pos.x**2 + e.pos.y**2 <= wp.range_m**2
        ]
        if valid:
            expected.append((wid, min(valid)[2]))
    fired = of(run(w), WeaponFired)
    assert [(f.weapon, f.target_id) for f in fired if f.shooter_id == jet.id] == expected


def brute_fire(world: World, rules: Rules, cr: CombatRules, now: int, out: list[Event]) -> None:
    """The first, grid-free targeting (a scan and sort of every tracked contact per ready
    shooter): the oracle the grid search must equal, target for target and draw for draw."""
    for e in world.entities():
        if e.damage_state == "DISABLED" or not e.ammo:
            continue
        ready = [
            i for i, (a, r) in enumerate(zip(e.ammo, e.reload, strict=True)) if a > 0 and not r
        ]
        loadout = cr.loadout(e.kind, e.variant)
        known = sorted(
            (-cr.units[t.kind].threat, combat._d2(e, t), t.id)
            for i, c in world.contacts[e.side].items()
            if c.age is None
            and (t := world.find(i)) is not None
            and t.side != e.side
            and not is_off_facility(rules, t)
        )
        for i in ready:
            w = loadout[i]
            for _, d2, tid in known:
                t = world.get(tid)
                domain = rules.domain[t.kind]
                if (
                    d2 <= w.range_m**2
                    and domain in w.targets
                    and (domain != "AIR" or t.alt_band in w.bands)
                ):
                    combat._shoot(world, rules, e, i, w, (t, d2), now, out)
                    break


# Positions on a 500 m lattice make ties; 3-4-5 offsets put targets at exactly 1,500 / 4,000 /
# 8,000 m, the weapon ranges, where the float tests decide.
_OFFSETS = [
    (0, 0), (500, 0), (0, 1500), (1500, 0), (2400, 3200), (900, 1200), (-4800, 6400), (4000, 0),
    (0, -8000), (6000, 8000), (35000, 0), (35000.5, 0), (12000, 16000),
]  # fmt: skip
_KINDS: list[UnitKind] = [
    JET, ENEMY_JET, "ENEMY_FIGHTER", ARMOR, INFANTRY, CONVOY, TRUCK, RADAR, "AIR_DEFENSE_SITE",
    "RECON_UAV",
]  # fmt: skip


@settings(max_examples=120, deadline=None)
@given(
    scene=st.lists(
        st.tuples(
            st.sampled_from(_KINDS),
            st.sampled_from(["COALITION", "ENEMY"]),
            st.sampled_from(_OFFSETS),
            st.sampled_from(["NOE", "LOW", "MED", "HIGH"]),
            st.sampled_from(["tracked", "tracked", "tracked", "unseen", "last_known"]),
            st.booleans(),
        ),
        min_size=2,
        max_size=14,
    ),
    seed=st.integers(0, 2**32),
)
def test_the_grid_search_equals_the_brute_force_scan(
    scene: list[tuple[UnitKind, Side, tuple[float, float], AltBand, str, bool]], seed: int
) -> None:
    def build() -> World:
        w = new_world(seed=seed)
        for kind, side, (x, y), band, _, off in scene:
            e = put(w, kind, side, 10_000.0 + x, 10_000.0 + y)
            if e.state is not None:
                e.alt_band = band
            if off and w.rules is not None and w.rules.domain[kind] == "STATIC":
                e.hp, e.damage_state = 14, "DISABLED"
        for s in w.entities():
            for t in w.entities():
                how = scene[t.id - 1][4]
                if s.side != t.side and how != "unseen":
                    age = 3 if how == "last_known" else None
                    w.contacts[s.side][t.id] = Contact(t.kind, t.pos, t.vel, age)
        return w

    grid, brute = build(), build()
    events_grid = run(grid, 6)
    original, combat._fire = combat._fire, brute_fire
    try:
        events_brute = run(brute, 6)
    finally:
        combat._fire = original
    assert [e.model_dump() for e in events_grid] == [e.model_dump() for e in events_brute]
    assert state_hash(grid) == state_hash(brute)  # same shots, same RNG draws, same damage


# --- CB-2, CB-3 shots and fizzles -----------------------------------------------------------------


def test_a_gun_lands_on_the_fire_tick() -> None:
    w = new_world()
    inf = put(w, INFANTRY, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 1_000)  # SMALL_ARMS reaches 1,500 m
    track(w, inf, armor)
    events = run(w)
    (fired,) = of(events, WeaponFired)
    (impact,) = of(events, WeaponImpact)
    assert fired.impact_tick == 1 and (impact.shooter_id, impact.target_id) == (inf.id, armor.id)
    assert w.shots == []


def test_a_missile_lands_after_ceil_of_distance_over_speed_over_world_dt() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 6_000)
    track(w, jet, armor)
    (fired,) = of(run(w), WeaponFired)
    # 6,000 m at 300 m/s is 20 s, 33.33 ticks of 0.6 s, so 34: the fire tick is running tick 1.
    assert fired.impact_tick == 1 + 34
    assert [(s.shooter, s.target, s.weapon_id, s.impact_tick) for s in w.shots] == [
        (jet.id, armor.id, "AG_LIGHT", 35)
    ]
    assert of(run(w, 33), WeaponImpact) == []  # ticks 2..34
    (impact,) = of(run(w), WeaponImpact)  # tick 35
    assert impact.target_id == armor.id
    assert [s.id for s in w.shots] == [
        2,
        3,
    ]  # the first shot is spent; the reloaded jet fired twice


def test_reload_and_ammo_set_the_fire_ticks() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 2_000)
    track(w, jet, armor)
    ticks = [t for t in range(1, 120) if of(run(w), WeaponFired)]
    # 10 s reload is 17 ticks (16.67 rounded up); 4 rounds, then the weapon is dry.
    assert ticks == [1, 18, 35, 52] and jet.ammo[0] == 0


def test_shots_land_in_impact_tick_then_id_order() -> None:
    w = new_world()
    a = put(w, INFANTRY, "COALITION", 0)
    b = put(w, ARMOR, "ENEMY", 100)
    w.shots = [Shot(2, a.id, b.id, "SMALL_ARMS", 1), Shot(1, a.id, b.id, "SMALL_ARMS", 1)]
    w.shots.sort(key=lambda s: (s.impact_tick, s.id))
    w._next_shot_id = 3
    track(w, a, b)
    a.ammo = [0]  # nothing new fires
    events = run(w)
    assert [(e.shooter_id, e.target_id) for e in of(events, WeaponImpact)] == [(a.id, b.id)] * 2


def test_a_fizzle_is_a_miss_with_no_rng_draw() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 6_000)
    track(w, jet, armor)
    run(w)
    before = w.rng.to_state()
    del w.contacts["COALITION"][armor.id]  # the side loses the track while the shot flies
    events = run(w, 34)
    (impact,) = of(events, WeaponImpact)
    assert impact.hit is False and w.rng.to_state() == before


@pytest.mark.parametrize("how", ["gone", "out_of_range", "shooter_gone"])
def test_a_fizzle_draws_nothing_whatever_the_reason(how: str) -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 6_000)
    track(w, jet, armor)
    run(w)
    before = w.rng.to_state()
    if how == "gone":
        w.remove(armor.id)
    elif how == "out_of_range":
        armor.pos = Vec2(10_001.0, 0.0)
    else:
        w.remove(jet.id)
    (impact,) = of(run(w, 34), WeaponImpact)
    assert impact.hit is False and w.rng.to_state() == before


def test_a_landed_shot_draws_once_on_the_combat_stream() -> None:
    w = new_world(seed=99)
    inf = put(w, INFANTRY, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 500)
    track(w, inf, armor)
    reference = SimRng(99)
    reference.stream("combat").random()
    run(w)
    assert w.rng.to_state() == reference.to_state()  # exactly one draw, on `combat` only


# --- CB-4 hit probability -----------------------------------------------------------------------


def pk_of(
    w: World, shooter: Entity, target: Entity, weapon: WeaponRules, cr: CombatRules = COMBAT
) -> float | None:
    assert w.rules is not None
    return _pk(w, w.rules, cr, shooter, target, weapon)


def test_the_worked_example_is_042() -> None:
    # COMBAT §5.2: base_pk 0.8, range 20 km, a tracked unpainted fighter (evasion 0.7) at 15 km.
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    target = put(w, JET, "COALITION", 15_000)
    track(w, shooter, target)
    weapon = dataclasses.replace(COMBAT.weapons["AA_MISSILE"], base_pk=0.8, range_m=20_000.0)
    assert pk_of(w, shooter, target, weapon) == pytest.approx(0.8 * 1.0 * 0.75 * 0.7 * 1.0)
    assert pk_of(w, shooter, target, weapon) == pytest.approx(0.42)
    track(w, shooter, target, painted=True)
    assert pk_of(w, shooter, target, weapon) == pytest.approx(0.42 * 1.25)
    target.alt_band = "LOW"  # terrain masking: x0.5
    assert pk_of(w, shooter, target, weapon) == pytest.approx(0.42 * 1.25 * 0.5)


def test_range_factor_is_full_to_half_range_then_linear_to_the_minimum() -> None:
    for frac, expected in [(0.0, 1.0), (0.25, 1.0), (0.5, 1.0), (0.75, 0.75), (1.0, 0.5)]:
        assert _range_factor(COMBAT, frac * 8_000.0, 8_000.0) == pytest.approx(expected)


def test_no_pk_beyond_range_and_the_cap_holds() -> None:
    w = new_world()
    shooter = put(w, JET, "COALITION", 0)
    target = put(w, ARMOR, "ENEMY", 10_001)
    track(w, shooter, target)
    ag = COMBAT.weapons["AG_LIGHT"]
    assert pk_of(w, shooter, target, ag) is None  # no fire beyond range_m
    target.pos = Vec2(1_000.0, 0.0)
    track(w, shooter, target, painted=True)
    sure_shot = dataclasses.replace(ag, base_pk=1.0)  # 1.0 x 1.25 x 1 x 1 x 1 would be 1.25
    assert pk_of(w, shooter, target, sure_shot) == COMBAT.pk_cap == 0.95


def test_ground_masking_uses_the_theater_regions() -> None:
    rules = dataclasses.replace(RULES, mask_cell_m=1000.0, masking={(5, 0): frozenset({"hills"})})
    w = new_world(rules)
    shooter = put(w, JET, "COALITION", 0)
    open_ground = put(w, ARMOR, "ENEMY", 1_000)
    hills = put(w, ARMOR, "ENEMY", 5_500)  # inside cell (5, 0)
    ag = COMBAT.weapons["AG_LIGHT"]
    for t in (open_ground, hills):
        track(w, shooter, t)
    near = pk_of(w, shooter, open_ground, ag, COMBAT)
    far = pk_of(w, shooter, hills, ag, COMBAT)
    assert near == pytest.approx(0.7) and far == pytest.approx(
        0.7 * 0.95 * 0.5
    )  # 5.5 km of 10: range 0.95, masked 0.5
    static = put(w, RADAR, "ENEMY", 5_600)  # STATIC targets are never masked (Q-FOW-3)
    track(w, shooter, static)
    assert pk_of(w, shooter, static, ag, COMBAT) == pytest.approx(0.7 * 0.94)  # range factor only


@settings(max_examples=80, deadline=None)
@given(
    base_pk=st.floats(0.0, 1.0),
    dist=st.floats(0.0, 40_000.0),
    painted=st.booleans(),
    band=st.sampled_from(["NOE", "LOW", "MED", "HIGH"]),
)
def test_pk_stays_between_zero_and_the_cap(
    base_pk: float, dist: float, painted: bool, band: AltBand
) -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    target = put(w, JET, "COALITION", dist)
    target.alt_band = band
    track(w, shooter, target, painted=painted)
    weapon = dataclasses.replace(
        COMBAT.weapons["AA_MISSILE"],
        base_pk=base_pk,
        range_m=40_000.0,
        bands=frozenset({"NOE", "LOW", "MED", "HIGH"}),
    )
    pk = pk_of(w, shooter, target, weapon)
    assert pk is not None and 0.0 <= pk <= COMBAT.pk_cap


# --- CB-5, CB-6 damage and states -----------------------------------------------------------------


def test_damage_floors_exactly_and_is_at_least_one() -> None:
    w = new_world()
    shooter = put(w, INFANTRY, "COALITION", 0)
    out: list[Event] = []
    armor = put(w, ARMOR, "ENEMY", 100)  # armor 0.5, hp 200
    _hit(w, RULES, COMBAT, shooter, armor, COMBAT.weapons["SMALL_ARMS"], out)
    assert armor.hp == 200 - 4  # 8 x 0.5
    odd = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=7)
    _hit(w, RULES, COMBAT, shooter, armor, odd, out)
    assert armor.hp == 196 - 3  # floor(3.5)
    ninety = dataclasses.replace(
        COMBAT,
        units={
            **COMBAT.units,
            ARMOR: dataclasses.replace(COMBAT.units[ARMOR], armor=Fraction(9, 10)),
        },
    )
    _hit(w, RULES, ninety, shooter, armor, COMBAT.weapons["SMALL_ARMS"], out)
    assert armor.hp == 193 - 1  # 0.8 floors to 0, but a hit always takes 1
    thirty = dataclasses.replace(
        COMBAT,
        units={
            **COMBAT.units,
            ARMOR: dataclasses.replace(COMBAT.units[ARMOR], armor=Fraction(3, 10)),
        },
    )
    ten = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=10)
    _hit(w, RULES, thirty, shooter, armor, ten, out)
    assert armor.hp == 192 - 7  # 10 x 0.7 is exactly 7: no float error


def test_min_damage_is_the_floor_of_a_hit_and_a_key() -> None:
    w = new_world()
    shooter = put(w, INFANTRY, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 100)
    heavy = dataclasses.replace(
        COMBAT,
        units={
            **COMBAT.units,
            ARMOR: dataclasses.replace(COMBAT.units[ARMOR], armor=Fraction(9, 10)),
        },
        min_damage=3,
    )
    _hit(w, RULES, heavy, shooter, armor, COMBAT.weapons["SMALL_ARMS"], [])  # 0.8 floors to 0
    assert armor.hp == 200 - 3


@pytest.mark.parametrize(
    ("hp", "state"),
    [(100, "HEALTHY"), (70, "HEALTHY"), (69, "DAMAGED"), (35, "DAMAGED"), (34, "MISSION_KILL"),
     (10, "MISSION_KILL"), (9, "DISABLED"), (1, "DISABLED")],
)  # fmt: skip
def test_state_thresholds_for_a_hundred_hp_unit(hp: int, state: str) -> None:
    assert COMBAT.units[JET].state(hp) == state  # below 0.70, 0.35 and 0.10 of 100


def test_thresholds_are_whole_hp_of_the_kinds_own_maximum() -> None:
    # radar: 150 hp, so DAMAGED below 105, MISSION_KILL below 52.5 (52), DISABLED below 15
    radar = COMBAT.units[RADAR]
    assert radar.cuts == (15, 53, 105)
    assert [radar.state(h) for h in (105, 104, 53, 52, 15, 14)] == [
        "HEALTHY", "DAMAGED", "DAMAGED", "MISSION_KILL", "MISSION_KILL", "DISABLED",
    ]  # fmt: skip


def test_a_hit_reports_the_state_change_once_and_only_when_it_changes() -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000)
    sam = COMBAT.weapons["SAM"]  # 70 damage
    out: list[Event] = []
    small = dataclasses.replace(sam, damage=5)
    _hit(w, RULES, COMBAT, shooter, jet, small, out)  # 95: still healthy
    assert out == []
    _hit(w, RULES, COMBAT, shooter, jet, dataclasses.replace(sam, damage=30), out)  # 65
    _hit(w, RULES, COMBAT, shooter, jet, small, out)  # 60: still damaged
    (change,) = of(out, UnitDamageStateChanged)
    assert (change.entity_id, change.from_, change.to) == (jet.id, "HEALTHY", "DAMAGED")
    assert jet.damage_state == "DAMAGED" and jet.hp == 60


def test_a_big_hit_skips_states_and_destruction_reports_the_killer() -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000, cmd=7)
    sam = COMBAT.weapons["SAM"]
    out: list[Event] = []
    _hit(w, RULES, COMBAT, shooter, jet, sam, out)  # 100 -> 30
    (change,) = of(out, UnitDamageStateChanged)
    assert (change.from_, change.to) == ("HEALTHY", "MISSION_KILL")
    out.clear()
    _hit(w, RULES, COMBAT, shooter, jet, sam, out)  # 30 -> dead
    assert of(out, UnitDamageStateChanged) == []  # destruction is UnitDestroyed alone
    (dead,) = of(out, UnitDestroyed)
    assert (dead.entity_id, dead.killer_id, dead.assist_ids, dead.side) == (
        jet.id, shooter.id, [], "COALITION",
    )  # fmt: skip
    assert w.find(jet.id) is None and w.respawn_left == {cid(7): 200}


def test_a_killing_shot_in_a_tick_emits_fire_impact_destroy_in_order() -> None:
    w = new_world(sure("SMALL_ARMS", damage=80))
    inf = put(w, INFANTRY, "COALITION", 0)
    convoy = put(w, CONVOY, "ENEMY", 500)  # 80 hp, armor 0
    track(w, inf, convoy)
    events = run(w)
    assert [type(e) for e in events if not isinstance(e, CrewDowned)] == [
        WeaponFired,
        WeaponImpact,
        UnitDestroyed,
    ]  # the crew roll is covered in test_rearm_crew.py
    assert of(events, WeaponImpact)[0].hit is True
    assert of(events, UnitDestroyed)[0].killer_id == inf.id and len(w) == 1
    assert [e.event_seq for e in events] == sorted(e.event_seq for e in events)


# --- CB-7 wrecks ----------------------------------------------------------------------------------


def disabled_truck(w: World, *, cmd: int | None = None) -> tuple[Entity, Entity]:
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    unit = put(w, TRUCK, "COALITION", 1_000, cmd=cmd)  # 80 hp
    unit.hp = 12
    _hit(
        w,
        RULES,
        COMBAT,
        shooter,
        unit,
        dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=5),
        [],
    )
    return shooter, unit


def test_a_disabled_unit_is_a_wreck_removed_after_the_timeout() -> None:
    w = new_world()
    _, truck = disabled_truck(w, cmd=3)
    assert (truck.hp, truck.damage_state, truck.wreck_left) == (7, "DISABLED", 6_000)
    events = run(w, 5_999)
    assert events == [] and w.find(truck.id) is truck and truck.wreck_left == 1
    (gone,) = of(run(w), UnitDespawned)
    assert (gone.entity_id, gone.reason) == (truck.id, "WRECKED")
    assert w.find(truck.id) is None
    assert w.respawn_left == {cid(3): 199}  # GP-2 delay 200, one counted in the removal tick


def test_a_wreck_does_not_heal_move_or_fire_and_stays_a_target() -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    armor = put(w, ARMOR, "ENEMY", 100)
    armor.hp = 12
    armor.path, armor.vel = ["west-airbase"], Vec2(10.0, 0.0)
    _hit(
        w,
        RULES,
        COMBAT,
        shooter,
        armor,
        dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=10),
        [],
    )
    assert armor.damage_state == "DISABLED" and (armor.path, armor.vel) == ([], Vec2(0, 0))
    w.remove(shooter.id)
    armor.path = ["west-airbase"]  # even if something assigns an order, it does not move
    inf = put(w, INFANTRY, "COALITION", 600)
    track(w, inf, armor)
    track(w, armor, inf)  # the wreck tracks its enemy but does not fire
    events = run(w, 3)
    assert armor.pos == Vec2(100.0, 0.0) and armor.hp == 7 and armor.damage_state == "DISABLED"
    assert {f.shooter_id for f in of(events, WeaponFired)} == {inf.id}  # a target until Destroyed


def test_movement_leaves_a_disabled_aircraft_alone_and_burns_no_fuel() -> None:
    # Combat destroys an airborne aircraft the moment it is Disabled (Q-SIM-66), so this state only
    # arises from a hand-built world; movement still must not fly it or burn its fuel.
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    jet.state, jet.path, jet.fuel = "EN_ROUTE", [Vec2(50_000.0, 0.0)], 3_000.0
    run(w, 2)
    moved = jet.pos
    assert moved.x > 0
    jet.hp, jet.damage_state, jet.wreck_left = 5, "DISABLED", 6_000
    run(w, 10)
    assert (jet.pos, jet.path, jet.vel) == (moved, [], Vec2(0, 0))
    assert jet.fuel == pytest.approx(3_000.0 - 0.6 * 2)  # the two flying ticks only


def test_a_commander_joins_again_only_after_the_wreck_is_gone_and_the_delay_ran() -> None:
    w = new_world()
    truck = put(w, TRUCK, "COALITION", 0, cmd=3)
    truck.hp, truck.damage_state, truck.wreck_left = 5, "DISABLED", 3

    def try_join() -> list[str]:
        command = join(3, "LOGI", hold=True).model_copy(update={"target_tick": w.campaign.tick + 1})
        return [r.reason for r in of(step(w, [command]), CommandRejected)]

    assert try_join() == ["UNIT_IN_SORTIE"]  # tick 1: the wreck still holds the slot
    run(w, 1)  # tick 2
    run(w, 1)  # tick 3: the wreck goes
    assert w.find(truck.id) is None and w.respawn_left == {cid(3): 199}
    run(w, 198)  # tick 201
    assert try_join() == ["RESPAWN_COOLDOWN"]  # tick 202: lost on tick 3 + the 200-tick delay
    assert try_join() == []  # tick 203
    assert any(e.commander_id == cid(3) for e in w.entities())


def test_a_disabled_truck_keeps_its_cargo_and_unloads_nothing_until_removed() -> None:
    w = new_world()
    w.stock = {"west-airbase": 1000}
    truck = put(w, TRUCK, "COALITION", 0, cmd=1)
    truck.pos, truck.last_node, truck.cargo = (
        Vec2(*RULES.roads.pos["west-airbase"]),
        "west-airbase",
        40,
    )
    healthy = put(w, TRUCK, "COALITION", 0)
    healthy.pos, healthy.last_node, healthy.cargo = truck.pos, "west-airbase", 40
    truck.hp, truck.damage_state, truck.wreck_left = 5, "DISABLED", 100
    run(w, 50)
    assert truck.cargo == 40 and healthy.cargo < 40  # the wreck keeps it; the other one unloads
    assert w.stock["west-airbase"] == 1000 + (40 - (healthy.cargo or 0))
    run(w, 50)
    assert w.find(truck.id) is None  # lost with the wreck (GP-5): never delivered
    assert w.stock["west-airbase"] == 1000 + (40 - (healthy.cargo or 0))


# --- Q-SIM-66: airborne Disabled, assists, Disabled facilities -----------------------------------


def test_a_disabled_airborne_aircraft_is_destroyed_at_once_by_its_killer() -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000, cmd=4)
    jet.state, jet.fuel, jet.hp = "EN_ROUTE", 3_000.0, 16
    out: list[Event] = []
    _hit(
        w,
        RULES,
        COMBAT,
        shooter,
        jet,
        dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=10),
        out,
    )
    # no state change: it is destroyed (Q-SIM-66); the crew roll is covered in test_rearm_crew.py
    assert [type(e) for e in out if not isinstance(e, CrewDowned)] == [UnitDestroyed]
    (dead,) = of(out, UnitDestroyed)
    assert dead.killer_id == shooter.id and w.find(jet.id) is None
    assert w.respawn_left == {cid(4): 200}


@pytest.mark.parametrize("state", ["ON_STATION", "RTB", "EN_ROUTE"])
def test_every_airborne_state_is_destroyed_on_disabled(state: Any) -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000)
    jet.state, jet.hp = state, 12
    _hit(
        w, RULES, COMBAT, shooter, jet, dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=5), []
    )
    assert w.find(jet.id) is None


def test_a_landed_aircraft_that_is_disabled_becomes_a_ground_wreck() -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000, cmd=4)  # LANDED
    jet.hp = 12
    out: list[Event] = []
    _hit(
        w,
        RULES,
        COMBAT,
        shooter,
        jet,
        dataclasses.replace(COMBAT.weapons["AAA_GUN"], damage=5),
        out,
    )
    assert [type(e) for e in out if not isinstance(e, CrewDowned)] == [UnitDamageStateChanged]
    assert (jet.damage_state, jet.wreck_left) == ("DISABLED", 6_000)
    (gone,) = of(run(w, 6_000), UnitDespawned)
    assert (gone.entity_id, gone.reason) == (jet.id, "WRECKED")


def kill_with_hits(w: World, hits: list[tuple[Entity, int]], killer: Entity) -> UnitDestroyed:
    """Land each (shooter, running tick) hit of 1 hp on a 80 hp truck, then a killing hit."""
    truck = put(w, TRUCK, "COALITION", 1_000)
    tiny = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=1)
    for shooter, tick in hits:
        w.campaign.running_ticks = tick - 1  # the hit lands on running tick `tick`
        _hit(w, RULES, COMBAT, shooter, truck, tiny, [])
    w.campaign.running_ticks = 2_000 - 1  # the kill: running tick 2,000
    out: list[Event] = []
    _hit(w, RULES, COMBAT, killer, truck, dataclasses.replace(tiny, damage=500), out)
    (dead,) = of(out, UnitDestroyed)
    return dead


def test_assists_are_the_other_distinct_shooters_inside_the_window_sorted() -> None:
    w = new_world()
    a, b, c, killer = (put(w, ENEMY_JET, "ENEMY", 0) for _ in range(4))
    # 120 s of game time is 1,200 ticks: a hit on tick 800 or later is inside for a kill on 2,000.
    dead = kill_with_hits(
        w, [(c, 900), (a, 1_500), (c, 1_600), (killer, 1_700), (b, 1_999)], killer
    )
    assert dead.killer_id == killer.id and dead.assist_ids == [a.id, b.id, c.id]


def test_a_hit_just_outside_the_window_is_not_an_assist() -> None:
    w = new_world()
    early, edge, killer = (put(w, ENEMY_JET, "ENEMY", 0) for _ in range(3))
    dead = kill_with_hits(w, [(early, 799), (edge, 800)], killer)
    assert dead.assist_ids == [edge.id]  # 2,000 - 800 = 1,200 ticks: still in; 1,201 is out


def test_the_killer_and_a_lone_shooter_have_no_assists() -> None:
    w = new_world()
    killer = put(w, ENEMY_JET, "ENEMY", 0)
    assert kill_with_hits(w, [(killer, 1_000), (killer, 1_900)], killer).assist_ids == []


def test_assists_are_capped_at_the_contract_limit() -> None:
    w = new_world()
    crowd = [put(w, ENEMY_JET, "ENEMY", 0) for _ in range(40)]
    killer = put(w, ENEMY_JET, "ENEMY", 0)
    dead = kill_with_hits(w, [(s, 1_500) for s in crowd], killer)
    assert dead.assist_ids == sorted(s.id for s in crowd)[:32]


def test_recent_hits_are_pruned_to_the_window_and_stay_oldest_first() -> None:
    w = new_world()
    shooter = put(w, ENEMY_JET, "ENEMY", 0)
    truck = put(w, TRUCK, "COALITION", 1_000)
    tiny = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=1)
    for tick in (10, 20, 1_300):
        w.campaign.running_ticks = tick - 1
        _hit(w, RULES, COMBAT, shooter, truck, tiny, [])
    assert truck.hits == [[shooter.id, 1_300]]  # 10 and 20 are 1,290+ ticks old and dropped


def test_assists_survive_a_snapshot() -> None:
    w = new_world()
    helper, killer = put(w, ENEMY_JET, "ENEMY", 0), put(w, ENEMY_JET, "ENEMY", 0)
    truck = put(w, TRUCK, "COALITION", 1_000)
    w.campaign.tick = w.campaign.running_ticks = 49
    _hit(
        w,
        RULES,
        COMBAT,
        helper,
        truck,
        dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=1),
        [],
    )
    restored = load(save(w))
    restored.rules = RULES
    out: list[Event] = []
    big = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=500)
    _hit(restored, RULES, COMBAT, restored.get(killer.id), restored.get(truck.id), big, out)
    assert of(out, UnitDestroyed)[0].assist_ids == [helper.id]


def test_a_disabled_facility_is_not_a_valid_target_and_a_shot_at_it_fizzles() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    site = put(w, "AIR_DEFENSE_SITE", "ENEMY", 3_000)
    track(w, jet, site)
    run(w)  # fires: a healthy site is a target
    assert len(w.shots) == 1
    site.hp, site.damage_state = 14, "DISABLED"
    before = w.rng.to_state()
    events = run(w, 40)
    assert [e.hit for e in of(events, WeaponImpact)] == [False] and w.rng.to_state() == before
    assert of(events, WeaponFired) == []  # and nothing new is fired at it


def test_a_disabled_facility_does_not_fire_but_a_disabled_wreck_that_is_a_unit_is_targeted() -> (
    None
):
    w = new_world()
    jet = put(w, JET, "COALITION", 1_000)
    site = put(w, "AIR_DEFENSE_SITE", "ENEMY", 0)
    track(w, site, jet)
    site.hp, site.damage_state = 14, "DISABLED"
    assert of(run(w, 5), WeaponFired) == []
    armor = put(w, ARMOR, "ENEMY", 2_000)
    armor.hp, armor.damage_state, armor.wreck_left = 5, "DISABLED", 100
    track(w, jet, armor)
    assert [f.target_id for f in of(run(w), WeaponFired)] == [armor.id]


# --- CB-9 facilities ------------------------------------------------------------------------------


@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(1, 400), min_size=1, max_size=30))
def test_a_facility_never_drops_below_the_disabled_floor_or_dies(hits: list[int]) -> None:
    w = new_world()
    shooter = put(w, JET, "COALITION", 0)
    site = put(w, "AIR_DEFENSE_SITE", "ENEMY", 1_000)
    floor = COMBAT.units["AIR_DEFENSE_SITE"].floor
    out: list[Event] = []
    for damage in hits:
        _hit(
            w,
            RULES,
            COMBAT,
            shooter,
            site,
            dataclasses.replace(COMBAT.weapons["SAM"], damage=damage),
            out,
        )
        assert w.find(site.id) is site and site.hp >= floor
    assert of(out, UnitDestroyed) == [] and site.wreck_left is None  # never a wreck either
    if site.hp < COMBAT.units["AIR_DEFENSE_SITE"].cuts[0]:
        assert site.damage_state == "DISABLED"
    assert floor == 14  # 15 hp is MISSION_KILL (not below 10 % of 150), 14 is DISABLED


def test_a_facility_at_the_floor_takes_hits_without_further_events() -> None:
    w = new_world()
    shooter = put(w, JET, "COALITION", 0)
    site = put(w, RADAR, "ENEMY", 1_000)
    out: list[Event] = []
    for _ in range(10):
        _hit(w, RULES, COMBAT, shooter, site, COMBAT.weapons["SAM"], out)
    assert (site.hp, site.damage_state) == (14, "DISABLED")
    assert [(c.from_, c.to) for c in of(out, UnitDamageStateChanged)] == [
        ("HEALTHY", "DAMAGED"), ("DAMAGED", "MISSION_KILL"), ("MISSION_KILL", "DISABLED")
    ]  # fmt: skip


# --- CB-12 parity ---------------------------------------------------------------------------------


def duel(first: Side) -> list[Event]:
    w = new_world(seed=2026)
    kinds: dict[Side, UnitKind] = {"COALITION": JET, "ENEMY": ENEMY_JET}
    a = put(w, kinds[first], first, 0)
    b = put(w, kinds[_OTHER[first]], _OTHER[first], 3_000)
    track(w, a, b)
    track(w, b, a)
    return run(w, 400)


def shape(events: list[Event]) -> list[tuple[Any, ...]]:
    """The events without the lost unit's side label, which mirrors by design."""
    return [
        tuple((k, v) for k, v in e.model_dump(by_alias=True).items() if k != "side") for e in events
    ]


def test_cb12_the_mirrored_duel_gives_the_mirrored_outcome() -> None:
    coalition_first, enemy_first = duel("COALITION"), duel("ENEMY")
    assert of(coalition_first, UnitDestroyed), "the duel should end in a kill"
    assert shape(coalition_first) == shape(enemy_first)
    kill_a, kill_b = of(coalition_first, UnitDestroyed)[0], of(enemy_first, UnitDestroyed)[0]
    assert (kill_a.side, kill_b.side) == (
        "COALITION" if kill_a.entity_id == 1 else "ENEMY",
        "ENEMY" if kill_b.entity_id == 1 else "COALITION",
    )


# --- SC-11 pause ----------------------------------------------------------------------------------


def paused(w: World, on: bool) -> None:
    c = w.campaign
    c.clock_paused, c.pause_reason = on, "STAFF" if on else None


def test_pause_freezes_shots_reloads_and_wreck_timers() -> None:
    w = new_world()
    jet = put(w, JET, "COALITION", 0)
    armor = put(w, ARMOR, "ENEMY", 6_000)
    track(w, jet, armor)
    wreck = put(w, CONVOY, "ENEMY", 20_000)
    wreck.hp, wreck.damage_state, wreck.wreck_left = 5, "DISABLED", 36
    run(w, 3)  # fired on tick 1, impact due running tick 35
    before = (list(w.shots), list(jet.reload), list(jet.ammo), wreck.wreck_left, state_hash(w))
    paused(w, on=True)
    assert run(w, 300) == []
    assert (list(w.shots), list(jet.reload), list(jet.ammo), wreck.wreck_left) == before[:4]
    paused(w, on=False)
    seen = 0
    for running in range(4, 40):  # the 4th running tick onward
        seen = running if of(run(w), WeaponImpact) else seen
    assert seen == 35  # the shot landed on its 35th running tick, the pause not counted
    assert w.find(wreck.id) is None  # and the wreck went at its 36th, 300 paused ticks later


# --- state, determinism ---------------------------------------------------------------------------


def fight() -> World:
    w = new_world(seed=7)
    a = put(w, JET, "COALITION", 0)
    b = put(w, ENEMY_JET, "ENEMY", 4_000)
    c = put(w, ARMOR, "ENEMY", 5_000)
    d = put(w, INFANTRY, "COALITION", 4_500)
    for x, y in ((a, b), (b, a), (a, c), (d, c), (c, d)):
        track(w, x, y)
    return w


def test_a_snapshot_taken_mid_fight_continues_identically() -> None:
    w = fight()
    run(w, 25)
    assert w.shots  # shots in flight are part of the snapshot
    restored = load(save(w))
    restored.rules = RULES  # static config: a snapshot carries none (recovery re-attaches it)
    assert state_hash(restored) == state_hash(w)
    assert [e.model_dump() for e in run(w, 200)] == [e.model_dump() for e in run(restored, 200)]
    assert state_hash(restored) == state_hash(w)


def test_format_13_snapshots_are_refused() -> None:
    import msgpack

    raw = msgpack.unpackb(save(fight()), raw=False)
    raw["v"] = 13
    with pytest.raises(ValueError, match="unsupported snapshot format version 13"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_the_same_seed_and_scene_give_the_same_events_and_hash() -> None:
    a, b = fight(), fight()
    assert [e.model_dump() for e in run(a, 300)] == [e.model_dump() for e in run(b, 300)]
    assert state_hash(a) == state_hash(b)
    assert fight().rng.to_state() == new_world(seed=7).rng.to_state()  # building draws nothing


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_combat import fight, run\n"
    "from nexus.core.world import state_hash\n"
    "w = fight(); run(w, 300); print(state_hash(w))"
)


def test_the_fight_hash_is_hash_seed_independent() -> None:
    def hash_in_child(seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    w = fight()
    run(w, 300)
    assert hash_in_child("1") == hash_in_child("2") == state_hash(w)
