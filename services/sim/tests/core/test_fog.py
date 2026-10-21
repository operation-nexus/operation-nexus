"""NX-150: Tier 2 tracks, last-known tracks, spotted and the visibility predicate (part 1);
terrain masking, emitters, passive sensors and facility markers (part 2)
(FOG-OF-WAR FOW-1, FOW-4..6a, FOW-9..13, Q-FOW-3, §3; SIM-CORE SC-4, SC-9, SC-10, SC-11).

Hand rules below: passes every 5 ticks, last-known tracks fade after 10 running ticks. A coalition
RADAR_SITE senses 1000 m; an ENEMY_ARMOR senses 200 m and has stealth 0.5; nothing else senses,
nothing listens passively and nothing is masked unless a test says so.
"""

import os
import statistics
import subprocess
import sys
import time
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.core.fog import side_view, spotted, tracked_by, visible
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.world import (
    Campaign,
    Contact,
    Entity,
    FacilityMarker,
    Vec2,
    World,
    load,
    save,
    state_hash,
)
from nexus.runtime.campaign_config import load_campaign_config

# The campaign layer is off: these tests are about sensing, not objectives (NX-126).
SHIPPED = replace(load_campaign_config().rules, campaign=None)
RADAR: UnitKind = "RADAR_SITE"
TRUCK: UnitKind = "LOGI_TRUCK"
ARMOR: UnitKind = "ENEMY_ARMOR"
CONVOY: UnitKind = "ENEMY_CONVOY"
RULES = replace(
    SHIPPED,
    sensor_radius_m={k: 0.0 for k in SHIPPED.speed_mps} | {RADAR: 1000.0, ARMOR: 200.0},
    stealth={k: 1.0 for k in SHIPPED.speed_mps} | {ARMOR: 0.5},
    track_every_ticks=5,
    track_fade_ticks=10,
    passive_range_m={k: 0.0 for k in SHIPPED.speed_mps},
    masking={},
)


def world(rules: Rules = RULES) -> World:
    return World.new(Campaign("0192f3a4-5b6c-7d8e-9f01-23456789abcd", 7, "cfg-test"), rules)


def put(w: World, kind: UnitKind, side: Side, x: float, y: float = 0.0) -> Entity:
    return w.spawn(kind, side, "AI_GARRISON", Vec2(x, y), hp=None)


def run_to(w: World, tick: int) -> None:
    while w.campaign.tick < tick:
        step(w, [])


def test_tracked_exactly_inside_radius_times_stealth() -> None:
    w = world()
    put(w, RADAR, "COALITION", 0.0)
    inside = [put(w, ARMOR, "ENEMY", 500.0), put(w, CONVOY, "ENEMY", 0.0, -1000.0)]
    outside = [put(w, ARMOR, "ENEMY", 500.01), put(w, CONVOY, "ENEMY", 600.0, 800.01)]
    run_to(w, 4)
    assert w.contacts == {"COALITION": {}, "ENEMY": {}}  # tick 4 is not due (FOW-5)
    run_to(w, 5)
    assert [i for i in w.contacts["COALITION"]] == [e.id for e in inside]
    assert not any(tracked_by(w, "COALITION", e.id) for e in outside)
    assert w.contacts["ENEMY"] == {}  # the armor's 200 m reaches no coalition unit


def test_detection_draws_no_rng() -> None:
    w = world()
    put(w, RADAR, "COALITION", 0.0)
    put(w, ARMOR, "ENEMY", 100.0)
    before = w.rng.to_state()
    run_to(w, 50)
    assert tracked_by(w, "COALITION", 2)
    assert w.rng.to_state() == before  # Q-FOW-2: no detection roll


@pytest.mark.parametrize("how", ["flies_out", "destroyed_unseen"])
def test_last_known_track_is_frozen_ages_and_fades_whatever_happened(how: str) -> None:
    w = world()
    put(w, RADAR, "COALITION", 0.0)
    jet = put(w, "ENEMY_FIGHTER", "ENEMY", 100.0, 50.0)  # 250 m/s east: 150 m per tick
    jet.path, jet.state, jet.fuel = [Vec2(100_000.0, 50.0)], "EN_ROUTE", 3600.0
    run_to(w, 5)
    seen = Contact("ENEMY_FIGHTER", Vec2(850, 50), Vec2(250, 0))
    assert w.contacts["COALITION"] == {jet.id: seen}
    if how == "destroyed_unseen":
        w.remove(jet.id)  # a hidden death or despawn (FOW-6a)
    run_to(w, 9)  # flying on, it left the 1000 m radius on tick 7
    assert tracked_by(w, "COALITION", jet.id)  # the last computed view holds (Q-FOW-6)
    run_to(w, 10)
    assert w.contacts["COALITION"] == {jet.id: replace(seen, age=0)}  # frozen at the tick-5 pass
    assert not tracked_by(w, "COALITION", jet.id)
    run_to(w, 19)
    assert w.contacts["COALITION"][jet.id].age == 9
    run_to(w, 20)
    assert w.contacts["COALITION"] == {}  # dropped after 10 running ticks, not earlier


def test_retracked_contact_leaves_last_known() -> None:
    w = world()
    put(w, RADAR, "COALITION", 0.0)
    armor = put(w, ARMOR, "ENEMY", 100.0)
    run_to(w, 5)
    armor.pos = Vec2(5000.0, 0.0)
    run_to(w, 10)
    armor.pos = Vec2(200.0, 0.0)
    run_to(w, 15)
    assert w.contacts["COALITION"] == {armor.id: Contact(ARMOR, Vec2(200, 0), Vec2(0, 0))}


def test_facilities_leave_no_last_known_track() -> None:
    """FOW-13: a lost facility is dropped, in both views; markers come with part 2. Each side's
    recon UAV (1000 m sensor, 60 m/s east: 36 m per tick) passes an enemy facility; an enemy
    convoy beside the coalition's path shows that units do leave a last-known track."""
    radii: dict[UnitKind, float] = {
        "RECON_UAV": 1e3,
        "ENEMY_RECON_UAV": 1e3,
        RADAR: 0.0,
        ARMOR: 0.0,
    }
    w = world(replace(RULES, sensor_radius_m={**RULES.sensor_radius_m, **radii}))
    for kind, side, y in (("RECON_UAV", "COALITION", 0.0), ("ENEMY_RECON_UAV", "ENEMY", 9e3)):
        uav = put(w, kind, side, 0.0, y)  # type: ignore[arg-type]  # literals above
        uav.path, uav.state, uav.fuel = [Vec2(100_000.0, y)], "EN_ROUTE", 14400.0
    site = put(w, "AIR_DEFENSE_SITE", "ENEMY", 500.0)
    radar = put(w, RADAR, "COALITION", 500.0, 9e3)
    convoy = put(w, CONVOY, "ENEMY", 300.0)
    run_to(w, 5)
    assert tracked_by(w, "COALITION", site.id) and tracked_by(w, "ENEMY", radar.id)
    run_to(w, 45)  # both UAVs are 1,120 m past their facility
    assert list(side_view(w, "COALITION").last_known) == [convoy.id]
    assert side_view(w, "ENEMY").last_known == {} == side_view(w, "ENEMY").tracks


def test_enemy_view_and_spotted_use_the_same_rules() -> None:
    w = world()
    truck = put(w, TRUCK, "COALITION", 0.0)
    armor = put(w, ARMOR, "ENEMY", 200.0)  # the armor senses 200 m: the truck is on the edge
    radar = put(w, RADAR, "COALITION", 50_000.0)
    run_to(w, 5)
    assert (spotted(w, truck), spotted(w, radar), spotted(w, armor)) == (True, False, False)
    view = side_view(w, "ENEMY")
    assert (list(view.tracks), view.last_known) == ([truck.id], {})
    truck.pos = Vec2(-1.0, 0.0)
    run_to(w, 9)
    assert spotted(w, truck)  # until the next pass
    run_to(w, 10)
    assert not spotted(w, truck)
    view = side_view(w, "ENEMY")
    assert (view.tracks, list(view.last_known)) == ({}, [truck.id])
    assert view.last_known[truck.id] == Contact(TRUCK, Vec2(0, 0), Vec2(0, 0), 0)
    assert view.nodes == SHIPPED.roads.pos  # FOW-10: every node's position
    view.last_known[truck.id].age = 99  # a copy: the world is untouched
    run_to(w, 20)
    assert side_view(w, "ENEMY").last_known == {}  # faded in the enemy view too (FOW-6a)


def test_pause_freezes_age_and_passes() -> None:
    w = world()
    put(w, RADAR, "COALITION", 0.0)
    armor = put(w, ARMOR, "ENEMY", 100.0)
    late = put(w, CONVOY, "ENEMY", 9000.0)
    run_to(w, 5)
    armor.pos = Vec2(5000.0, 0.0)
    run_to(w, 12)
    assert w.contacts["COALITION"][armor.id].age == 2
    w.campaign.clock_paused = True
    late.pos = Vec2(10.0, 0.0)  # moved into range while paused: not tracked while paused
    run_to(w, 40)
    assert w.contacts["COALITION"] == {armor.id: Contact(ARMOR, Vec2(100, 0), Vec2(0, 0), 2)}
    w.campaign.clock_paused = False
    run_to(w, 45)
    assert w.contacts["COALITION"][armor.id].age == 7  # FOW-9: 2 + 5 running ticks
    assert tracked_by(w, "COALITION", late.id)


def test_restore_between_passes_replays_to_the_same_hash() -> None:
    w = world()
    put(w, RADAR, "COALITION", 0.0)
    armor = put(w, ARMOR, "ENEMY", 100.0)
    put(w, TRUCK, "COALITION", 150.0)
    run_to(w, 5)
    armor.pos = Vec2(5000.0, 0.0)
    run_to(w, 7)  # between the passes at 5 and 10 (Q-FOW-6)
    restored = load(save(w))
    restored.rules = RULES
    assert state_hash(restored) == state_hash(w)
    run_to(w, 33)
    run_to(restored, 33)
    assert state_hash(restored) == state_hash(w)
    assert restored.contacts == w.contacts


def _cell_regions(rules: Rules, e: Entity) -> frozenset[str]:
    cell = (int(e.pos.x // rules.mask_cell_m), int(e.pos.y // rules.mask_cell_m))
    return rules.masking.get(cell, frozenset())


def brute(w: World, side: Side, rules: Rules = RULES) -> list[int]:
    """O(n^2) oracle: every enemy within some live sensor's radius x the target's stealth, unless
    it is a GROUND unit in a masking region the sensor is not in."""
    sensors = [
        s
        for s in w.entities()
        if s.side == side and rules.sensor_radius_m[s.kind] > 0 and s.emitting is not False
    ]

    def sees(s: Entity, t: Entity) -> bool:
        reach = rules.sensor_radius_m[s.kind] * rules.stealth[t.kind]
        hidden = rules.domain[t.kind] == "GROUND" and bool(_cell_regions(rules, t))
        hidden = hidden and not (_cell_regions(rules, t) & _cell_regions(rules, s))
        return (t.pos.x - s.pos.x) ** 2 + (t.pos.y - s.pos.y) ** 2 <= reach**2 and not hidden

    return [t.id for t in w.entities() if t.side != side and any(sees(s, t) for s in sensors)]


def brute_discovered(w: World, side: Side, rules: Rules) -> list[int]:
    """Oracle for one pass from no markers: tracked enemy facilities and emitting enemy sites
    inside a live passive sensor's range (FOW-13)."""
    ears = [s for s in w.entities() if s.side == side and rules.passive_range_m[s.kind] > 0]
    heard = {
        t.id
        for t in w.entities()
        if t.side != side
        and t.emitting
        and any(
            (t.pos.x - s.pos.x) ** 2 + (t.pos.y - s.pos.y) ** 2
            <= rules.passive_range_m[s.kind] ** 2
            for s in ears
            if s.emitting is not False
        )
    }
    static = {i for i in brute(w, side, rules) if rules.domain[w.get(i).kind] == "STATIC"}
    return sorted(heard | static)


_UNITS: list[tuple[UnitKind, Side]] = [
    (RADAR, "COALITION"),
    (TRUCK, "COALITION"),
    (ARMOR, "ENEMY"),
    (CONVOY, "ENEMY"),
]
_XY = st.integers(-3000, 3000).map(float) | st.floats(-3000, 3000)


@given(st.lists(st.tuples(st.sampled_from(_UNITS), _XY, _XY), max_size=40))
def test_no_entity_outside_coverage_passes_the_visibility_predicate(
    units: list[tuple[tuple[UnitKind, Side], float, float]],
) -> None:
    w = world()
    for (kind, side), x, y in units:
        put(w, kind, side, x, y)
    run_to(w, 5)
    for side in ("COALITION", "ENEMY"):
        assert [i for i in w.contacts[side]] == brute(w, side)
    for e in w.entities():
        if visible(w, "COALITION", e):
            assert e.side == "COALITION" or e.id in brute(w, "COALITION")  # FOW-1


def big_world() -> World:
    """1,000 entities over strait-1 with the shipped sensor radii (SC-10)."""
    w = World.new(Campaign("c", 1, "cfg"), SHIPPED)
    kinds: list[tuple[UnitKind, Side]] = [
        (TRUCK, "COALITION"), ("GARRISON_INFANTRY", "COALITION"), (RADAR, "COALITION"),
        (ARMOR, "ENEMY"), (CONVOY, "ENEMY"), ("AIR_DEFENSE_SITE", "ENEMY"),
    ]  # fmt: skip
    for i in range(1000):
        kind, side = kinds[i % len(kinds)]
        x, y = (i * 7919) % 400_000, (i * 104_729) % 240_000  # spread by two primes
        e = put(w, kind, side, float(x), float(y))
        e.emitting = True if SHIPPED.domain[kind] == "STATIC" else None  # every site emits
    return w


def test_sc10_smoke_1000_entities() -> None:
    w = big_world()
    start = time.perf_counter()
    run_to(w, 5)
    elapsed_ms = (time.perf_counter() - start) * 1000  # reported only, never asserted (§5)
    for side in ("COALITION", "ENEMY"):
        assert list(w.contacts[side]) == brute(w, side, SHIPPED)
        assert list(w.markers[side]) == brute_discovered(w, side, SHIPPED)
    # strait-1's masking regions hold armor, so the masking path runs (the dense coalition sensors
    # here include some inside each region; the hand test above shows it hiding).
    assert any(_cell_regions(SHIPPED, t) for t in w.entities() if t.kind == ARMOR)
    print(f"5 ticks incl. one sensing pass at 1,000 entities: {elapsed_ms:.1f} ms")


def test_sc10_step_time_1000_entities() -> None:
    """Per-tick `step` time over 50 ticks, 10 of them Tier 2 passes; nothing moves in
    `big_world`, so sensing dominates. Printed only, never asserted (§5)."""
    w = big_world()
    ms = []
    for _ in range(50):
        start = time.perf_counter()
        step(w, [])
        ms.append((time.perf_counter() - start) * 1000)
    assert w.contacts["COALITION"] and w.contacts["ENEMY"]
    p99 = statistics.quantiles(ms, n=100, method="inclusive")[98]
    print(f"step at 1,000 entities, 50 ticks: mean {statistics.fmean(ms):.2f} ms, p99 {p99:.2f} ms")


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_fog import big_world, run_to\n"
    "from nexus.core.world import state_hash\nw = big_world(); run_to(w, 30); print(state_hash(w))"
)


def test_sensing_hash_is_hash_seed_independent() -> None:
    """Cross-process smoke test of a run that tracks something. Contact ids are ints, whose hashes
    do not depend on PYTHONHASHSEED, so this guards against a later str-keyed set or dict in
    sensing, not against anything the int-keyed code can do today."""

    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    w = big_world()
    run_to(w, 30)
    assert w.contacts["COALITION"] and w.contacts["ENEMY"]  # the run does track something
    assert w.markers["COALITION"] and w.markers["ENEMY"]  # and discovers sites (FOW-13)
    assert run("1") == run("2") == state_hash(w)


# --- NX-150 part 2: terrain masking (Q-FOW-3) ---

HILLS: frozenset[str] = frozenset({"hills"})
# Cells of 1 km: "hills" covers x 0-3 km, "valley" x 5-6 km, both y 0-1 km. The radar reaches
# 10 km x the armor's stealth 0.5 = 5 km.
MASKED = replace(
    RULES,
    sensor_radius_m={**RULES.sensor_radius_m, RADAR: 10_000.0},
    mask_cell_m=1000.0,
    masking={(0, 0): HILLS, (1, 0): HILLS, (2, 0): HILLS, (5, 0): frozenset({"valley"})},
)


@pytest.mark.parametrize(
    ("radar_x", "tracks_armor"),
    [(2500.0, True), (5500.0, False), (4500.0, False)],  # same region, another region, none
)
def test_ground_unit_in_masking_region_hidden_from_sensors_outside_it(
    radar_x: float, tracks_armor: bool
) -> None:
    w = world(MASKED)
    put(w, RADAR, "COALITION", radar_x, 500.0)
    armor = put(w, ARMOR, "ENEMY", 500.0, 500.0)
    site = put(w, "AIR_DEFENSE_SITE", "ENEMY", 600.0, 500.0)  # STATIC: never masked
    outside = put(w, ARMOR, "ENEMY", 3500.0, 500.0)  # in no region
    run_to(w, 5)
    assert tracked_by(w, "COALITION", armor.id) is tracks_armor
    assert tracked_by(w, "COALITION", site.id) and tracked_by(w, "COALITION", outside.id)


# --- NX-150 part 2: emitters, passive sensors, facility markers (FOW-11, FOW-13) ---

UAV: UnitKind = "RECON_UAV"
SAM: UnitKind = "AIR_DEFENSE_SITE"
LISTENING = replace(RULES, passive_range_m={**RULES.passive_range_m, UAV: 5000.0, RADAR: 3000.0})


def site(w: World, side: Side, x: float, emitting: bool | None, kind: UnitKind = SAM) -> Entity:
    e = put(w, kind, side, x)
    e.base_id, e.variant, e.emitting = "fob-n-e", "SAM" if kind == SAM else None, emitting
    return e


def parked_uav(w: World, x: float) -> Entity:
    uav = put(w, UAV, "COALITION", x)
    uav.state, uav.fuel = "LANDED", 100.0  # no path: it stays put
    return uav


@pytest.mark.parametrize("ear", ["uav", "radar"])
def test_emitting_site_in_passive_range_is_discovered_dark_one_never(ear: str) -> None:
    w = world(LISTENING)
    if ear == "uav":
        parked_uav(w, 0.0)  # passive 5000 m, no active sensor
        reach = 5000.0
    else:
        put(w, RADAR, "COALITION", 0.0, 0.0)  # passive 3000 m; active 1000 m
        reach = 3000.0
    emitting = site(w, "ENEMY", reach, True)  # exactly at the edge
    dark = site(w, "ENEMY", -reach / 2, False)
    silent = site(w, "ENEMY", reach / 2, None)  # SHORT_RANGE: never emits
    beyond = site(w, "ENEMY", reach + 0.01, True)
    before = w.rng.to_state()
    run_to(w, 5)
    pos = Vec2(reach, 0.0)
    assert w.markers["COALITION"] == {emitting.id: FacilityMarker(SAM, "SAM", pos, True, 5)}
    assert not any(tracked_by(w, "COALITION", e.id) for e in (emitting, dark, silent, beyond))
    assert w.rng.to_state() == before  # no RNG draw
    view = side_view(w, "COALITION")
    assert (list(view.markers), view.tracks) == ([emitting.id], {})  # FOW-13 in the view
    assert not visible(w, "COALITION", dark) and w.markers["ENEMY"] == {}


def test_only_facilities_are_heard() -> None:
    """FOW-11: only STATIC sites emit; a non-facility flagged emitting (say, from a snapshot) is
    neither heard nor marked."""
    w = world(LISTENING)
    parked_uav(w, 0.0)
    convoy = put(w, CONVOY, "ENEMY", 1000.0)
    convoy.emitting = True
    run_to(w, 5)
    assert w.markers["COALITION"] == {}


def test_dark_site_gives_no_coverage_and_hears_nothing() -> None:
    w = world(LISTENING)
    radar = site(w, "ENEMY", 0.0, False, RADAR)  # active 1000 m, passive 3000 m, but dark
    truck = put(w, TRUCK, "COALITION", 500.0)
    ours = site(w, "COALITION", 2000.0, True)
    run_to(w, 5)
    assert not spotted(w, truck) and w.contacts["ENEMY"] == {} and w.markers["ENEMY"] == {}
    radar.emitting = True  # back on: covers and hears again
    run_to(w, 10)
    assert spotted(w, truck) and list(w.markers["ENEMY"]) == [ours.id]


def test_marker_never_fades_and_keeps_unobserved_details() -> None:
    """FOW-13: a site the side no longer observes keeps its marker with the old values and
    confirmed_tick, past the track fade and past its removal; observing it again refreshes."""
    w = world(LISTENING)
    radar = put(w, RADAR, "COALITION", 0.0)
    sam = site(w, "ENEMY", 500.0, True)
    run_to(w, 5)
    first = FacilityMarker(SAM, "SAM", Vec2(500, 0), True, 5)
    assert w.markers["COALITION"] == {sam.id: first} and tracked_by(w, "COALITION", sam.id)
    radar.pos = Vec2(-10_000.0, 0.0)  # out of active and passive range
    sam.emitting = False  # an unsensed change (DecoyBlink later)
    run_to(w, 50)  # well past track_fade_ticks
    assert w.markers["COALITION"] == {sam.id: first}
    assert w.contacts["COALITION"] == {}  # the facility contact itself is gone (FOW-13)
    radar.pos = Vec2(0.0, 0.0)
    run_to(w, 55)
    assert w.markers["COALITION"] == {sam.id: replace(first, emitting=False, confirmed_tick=55)}
    radar.pos = Vec2(-10_000.0, 0.0)
    w.remove(sam.id)  # a hidden destruction
    run_to(w, 80)
    assert w.markers["COALITION"][sam.id].confirmed_tick == 55


def test_undiscovered_facility_is_in_no_view() -> None:
    w = world(LISTENING)
    put(w, RADAR, "COALITION", 0.0)
    far = site(w, "ENEMY", 50_000.0, True, RADAR)  # the enemy radar can't reach us either
    run_to(w, 20)
    for side in ("COALITION", "ENEMY"):
        view = side_view(w, side)
        assert (view.tracks, view.last_known, view.markers) == ({}, {}, {})
    assert not visible(w, "COALITION", far)


def test_pause_freezes_discovery_and_markers_round_trip() -> None:
    w = world(LISTENING)
    parked_uav(w, 0.0)
    sam = site(w, "ENEMY", 9000.0, True)
    run_to(w, 5)
    w.campaign.clock_paused = True
    sam.pos = Vec2(1000.0, 0.0)  # moved into passive range while paused (a test stand-in)
    run_to(w, 30)
    assert w.markers["COALITION"] == {}  # FOW-9: no pass while paused
    w.campaign.clock_paused = False
    run_to(w, 32)  # between passes
    restored = load(save(w))
    restored.rules = LISTENING
    run_to(w, 40)
    run_to(restored, 40)
    # Discovered at the first pass after resuming (35), refreshed on every pass since.
    assert w.markers["COALITION"] == {sam.id: FacilityMarker(SAM, "SAM", Vec2(1000, 0), True, 40)}
    assert state_hash(restored) == state_hash(w)
