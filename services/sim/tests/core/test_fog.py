"""NX-150 part 1: Tier 2 tracks, last-known tracks, spotted and the visibility predicate
(FOG-OF-WAR FOW-1, FOW-4..6a, FOW-9, FOW-10, FOW-12, §3; SIM-CORE SC-4, SC-9, SC-10, SC-11).

Hand rules below: passes every 5 ticks, last-known tracks fade after 10 running ticks. A coalition
RADAR_SITE senses 1000 m; an ENEMY_ARMOR senses 200 m and has stealth 0.5; nothing else senses.
"""

import os
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
from nexus.core.world import Campaign, Contact, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config

SHIPPED = load_campaign_config().rules
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


def brute(w: World, side: Side, rules: Rules = RULES) -> list[int]:
    """O(n^2) oracle: every enemy within some sensor's radius x the target's stealth."""
    sensors = [s for s in w.entities() if s.side == side and rules.sensor_radius_m[s.kind] > 0]
    return [
        t.id
        for t in w.entities()
        if t.side != side
        and any(
            (t.pos.x - s.pos.x) ** 2 + (t.pos.y - s.pos.y) ** 2
            <= (rules.sensor_radius_m[s.kind] * rules.stealth[t.kind]) ** 2
            for s in sensors
        )
    ]


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
        put(w, kind, side, float(x), float(y))
    return w


def test_sc10_smoke_1000_entities() -> None:
    w = big_world()
    start = time.perf_counter()
    run_to(w, 5)
    elapsed_ms = (time.perf_counter() - start) * 1000  # reported only, never asserted (§5)
    for side in ("COALITION", "ENEMY"):
        assert list(w.contacts[side]) == brute(w, side, SHIPPED)
    print(f"5 ticks incl. one sensing pass at 1,000 entities: {elapsed_ms:.1f} ms")


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
    assert run("1") == run("2") == state_hash(w)
