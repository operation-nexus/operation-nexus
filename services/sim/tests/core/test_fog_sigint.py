"""NX-150 part 2b: Tier 1 SIGINT blobs and the painted flag (FOG-OF-WAR Tier 1, Tier 2, FOW-2,
FOW-4, FOW-9, FOW-11, Q-FOW-5..7, §3; SIM-CORE SC-10, SC-11).

Hand rules (on top of `test_fog.RULES`: a coalition RADAR_SITE senses 1000 m, ENEMY_ARMOR 200 m
with stealth 0.5, passes every 5 ticks): SIGINT reaches 2 x a radar's radius (2000 m), cells are
1 km on strait-1's 400 x 240 km bounds (400 columns), and blobs refresh every 10 running ticks.
Fighters fly 150 m per tick (250 m/s x 0.6 world s).
"""

import math
import os
import re
import subprocess
import sys
import time
from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_fog import (
    ARMOR,
    RADAR,
    RULES,
    SHIPPED,
    TRUCK,
    _cell_regions,
    big_world,
    brute,
    put,
    run_to,
    world,
)

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.core.fog import _class_cells, sense, side_view, tracked_by
from nexus.core.world import Blob, Contact, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config
from nexus.runtime.config import world_ticks

SIG = replace(RULES, sigint_range_mult=2.0, sigint_cell_m=1000.0, sigint_refresh_ticks=10)
FIGHTER: dict[Side, UnitKind] = {"COALITION": "STRIKE_FIGHTER", "ENEMY": "ENEMY_FIGHTER"}
PARKED: dict[Side, UnitKind] = {"COALITION": TRUCK, "ENEMY": ARMOR}
OTHER: dict[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}


def flier(w: World, side: Side, x: float, y: float) -> Entity:
    """A fighter flying east, far from its waypoint for the whole test."""
    e = put(w, FIGHTER[side], side, x, y)
    e.path, e.state, e.fuel = [Vec2(300_000.0, y)], "EN_ROUTE", 3600.0
    return e


def sigint_scene(listener: Side) -> tuple[World, Entity, Entity]:
    """`listener`'s radar at (10, 10) km and, on tick 10 (fighters 1500 m east of their start):
    3 movers in cell (10, 11), 1 in cell (10, 8), one tracked mover, one parked unit and one
    mover beyond the SIGINT reach. Returns the world, the tracked mover and the far one."""
    w = world(SIG)
    put(w, RADAR, listener, 10_000.0, 10_000.0)
    other = OTHER[listener]
    for y in (11_500.0, 11_600.0, 11_700.0):
        flier(w, other, 9_000.0, y)  # tick 10: (10.5, y) km, ~1.6 km from the radar
    flier(w, other, 8_500.0, 8_600.0)  # tick 10: (10.0, 8.6) km, 1.4 km away
    tracked = flier(w, other, 9_000.0, 10_000.0)  # tick 10: 500 m away, inside the radar
    put(w, PARKED[other], other, 11_500.0, 10_000.0)  # parked 1.5 km away: no blob
    far = flier(w, other, 9_000.0, 12_200.0)  # tick 10: 2.27 km away, beyond 2 x 1000 m
    return w, tracked, far


@pytest.mark.parametrize("listener", ["COALITION", "ENEMY"])
def test_blobs_group_moving_untracked_units_per_cell_in_both_views(listener: Side) -> None:
    """Q-FOW-7 and FOW-4: the same rule builds both sides' blobs."""
    w, tracked, _ = sigint_scene(listener)
    before = w.rng.to_state()
    run_to(w, 9)
    assert w.blobs[listener] == ()  # not due yet
    run_to(w, 10)
    assert tracked_by(w, listener, tracked.id)
    # Cell (10, 8) is index 8 x 400 + 10 = 3210, centre (10.5, 8.5) km; cell (10, 11) is 4410.
    assert w.blobs[listener] == (
        Blob("10-3210", Vec2(10_500.0, 8_500.0), "S"),
        Blob("10-4410", Vec2(10_500.0, 11_500.0), "M"),
    )
    assert w.blobs[OTHER[listener]] == ()
    assert side_view(w, listener).blobs == w.blobs[listener]
    assert w.rng.to_state() == before  # Q-FOW-5: no RNG draw


@pytest.mark.parametrize("listener", ["COALITION", "ENEMY"])
def test_parked_group_and_group_beyond_the_multiplier_make_no_blob(listener: Side) -> None:
    """FOG-OF-WAR §3, Q-FOW-7, in both views."""
    w = world(SIG)
    put(w, RADAR, listener, 10_000.0, 10_000.0)
    other = OTHER[listener]
    for x in (11_500.0, 11_600.0, 11_700.0):
        put(w, PARKED[other], other, x, 10_000.0)  # parked within reach
    for y in (12_200.0, 12_300.0):
        flier(w, other, 9_000.0, y)  # moving beyond reach
    run_to(w, 10)
    assert w.blobs == {"COALITION": (), "ENEMY": ()}


def test_dark_radar_gives_no_sigint_range() -> None:
    """FOW-11: a dark site provides no SIGINT range."""
    w, _, _ = sigint_scene("COALITION")
    next(e for e in w.entities() if e.kind == RADAR).emitting = False
    run_to(w, 10)
    assert w.blobs["COALITION"] == ()


def test_facilities_never_form_blobs() -> None:
    """Tier 1: even one flagged as moving (say, from a snapshot), sensed directly."""
    w = world(SIG)
    put(w, RADAR, "COALITION", 10_000.0, 10_000.0)
    put(w, "AIR_DEFENSE_SITE", "ENEMY", 11_500.0, 10_000.0).vel = Vec2(1.0, 0.0)
    refresh_now(w)
    assert (w.blobs["COALITION"], w.sigint_age) == ((), 0)  # refreshed, empty


def refresh_now(w: World) -> None:
    """Run `sense` once on a refresh tick (tick 1: no Tier 2 pass), velocities as set."""
    w.sigint_age = SIG.sigint_refresh_ticks - 1
    sense(w)


def test_units_on_the_east_and_north_edges_land_in_the_last_cells() -> None:
    """Cell clamp: x == w and y == h fall in the last column and row, not off the grid."""
    w = world(SIG)
    put(w, RADAR, "COALITION", 399_000.0, 239_000.0)
    put(w, ARMOR, "ENEMY", 400_000.0, 238_500.0).vel = Vec2(1.0, 0.0)  # east edge
    put(w, ARMOR, "ENEMY", 398_500.0, 240_000.0).vel = Vec2(1.0, 0.0)  # north edge
    refresh_now(w)
    # Column 399 of 400, row 238: 238 x 400 + 399; column 398, row 239 of 240: 239 x 400 + 398.
    assert w.blobs["COALITION"] == (
        Blob("1-95599", Vec2(399_500.0, 238_500.0), "S"),
        Blob("1-95998", Vec2(398_500.0, 239_500.0), "S"),
    )


def test_only_radar_sites_give_sigint_range() -> None:
    """Tier 1: a SAM site or a fighter with a sensor is no radar site."""
    sensing = replace(
        SIG,
        sensor_radius_m={
            **SIG.sensor_radius_m,
            "AIR_DEFENSE_SITE": 1000.0,
            FIGHTER["COALITION"]: 1000.0,
        },
    )
    w = world(sensing)
    put(w, "AIR_DEFENSE_SITE", "COALITION", 10_000.0, 10_000.0).emitting = True
    jet = put(w, FIGHTER["COALITION"], "COALITION", 20_000.0, 10_000.0)
    jet.state, jet.fuel = "LANDED", 100.0
    for x in (11_500.0, 21_500.0):  # 1.5 km from each: untracked, inside 2 x 1000 m
        put(w, ARMOR, "ENEMY", x, 10_000.0).vel = Vec2(1.0, 0.0)
    refresh_now(w)
    assert (w.blobs["COALITION"], w.sigint_age) == ((), 0)  # refreshed, empty


def test_refresh_replaces_the_set_and_pause_freezes_it() -> None:
    """FOW-9: no refresh while paused; the countdown resumes where it stopped."""
    w, _, far = sigint_scene("COALITION")
    run_to(w, 15)
    old = w.blobs["COALITION"]
    w.campaign.clock_paused = True
    run_to(w, 40)  # tick 20 would have refreshed
    assert (w.blobs["COALITION"], w.sigint_age) == (old, 5)
    w.campaign.clock_paused = False
    for i in [e.id for e in w.entities() if e.state == "EN_ROUTE" and e is not far]:
        w.remove(i)  # every other mover leaves the map
    far.pos, far.path = Vec2(10_000.0, 11_500.0), [Vec2(0.0, 11_500.0)]  # 1.5 km north
    run_to(w, 45)  # 5 more running ticks: the refresh is on tick 45, not 40 or 50
    # The far fighter flew 750 m west by tick 45: (9.25, 11.5) km, cell (9, 11) = 4409.
    assert w.blobs["COALITION"] == (Blob("45-4409", Vec2(9_500.0, 11_500.0), "S"),)


def test_refresh_cadence_scales_with_time_scale() -> None:
    """FOW-9: the Tier 1 refresh is world time, so 6x needs a sixth of the ticks of 1x."""
    cfg = load_campaign_config().balance

    def ticks(scale: float) -> int:
        sim = cfg.sim.model_copy(update={"time_scale": scale})
        return world_ticks(cfg.fow.sigint_refresh_s, cfg.model_copy(update={"sim": sim}))

    assert (ticks(1.0), ticks(6.0)) == (540, 90)  # PROPOSED 54 world s; exact, so no rounding
    assert SHIPPED.sigint_refresh_ticks == 90


@pytest.mark.parametrize(
    ("m_min", "l_min", "sizes"),
    [(3, 7, ["M", "L", "S"]), (2, 6, ["L", "L", "M"])],  # shipped PROPOSED, and another profile
)
def test_size_buckets_follow_the_balance_keys(m_min: int, l_min: int, sizes: list[str]) -> None:
    """`fow.sigint_size_m_min` and `fow.sigint_size_l_min` (PROPOSED 3 and 7)."""
    w = world(replace(SIG, sigint_size_m_min=m_min, sigint_size_l_min=l_min))
    put(w, RADAR, "COALITION", 10_000.0, 10_000.0)
    # On tick 10, 1.5 to 1.7 km from the radar: 2 in cell (10, 11), 6 in (10, 8), 7 in (8, 10).
    for n, x, y in ((2, 8_800.0, 11_500.0), (6, 8_800.0, 8_500.0), (7, 6_900.0, 10_000.0)):
        for k in range(n):
            flier(w, "ENEMY", x + 10 * k, y)
    run_to(w, 10)
    assert [b.id for b in w.blobs["COALITION"]] == ["10-3210", "10-4008", "10-4410"]
    assert [b.size for b in w.blobs["COALITION"]] == sizes  # 6, 7 and 2 units


_XY = st.tuples(st.floats(0.0, 30_000.0), st.floats(0.0, 30_000.0))


@settings(max_examples=50, deadline=None)
@given(st.lists(_XY, max_size=30))
def test_blob_ids_name_no_entity_and_sit_at_cell_centres(starts: list[tuple[float, float]]) -> None:
    """FOW-2, Q-FOW-5: ids are `<refresh_tick>-<cell_index>`, positions are cell centres, sizes
    are buckets, and no RNG is drawn; every eligible unit is in exactly one blob's cell."""
    w = world(SIG)
    put(w, RADAR, "COALITION", 15_000.0, 15_000.0)
    put(w, RADAR, "COALITION", 25_000.0, 5_000.0)
    for x, y in starts:
        flier(w, "ENEMY", x, y)
    before = w.rng.to_state()
    run_to(w, 10)
    assert w.rng.to_state() == before
    cells: set[int] = set()
    for b in w.blobs["COALITION"]:
        assert re.fullmatch(r"10-(0|[1-9][0-9]*)", b.id)
        cx, cy = b.pos.x / 1000 - 0.5, b.pos.y / 1000 - 0.5
        assert cx == int(cx) and cy == int(cy)  # a cell centre
        assert b.id == f"10-{int(cy) * 400 + int(cx)}"
        cells.add(int(cy) * 400 + int(cx))
    expected = {
        math.floor(e.pos.y / 1000) * 400 + math.floor(e.pos.x / 1000)
        for e in w.entities()
        if e.side == "ENEMY"
        and not tracked_by(w, "COALITION", e.id)
        and any(math.dist((e.pos.x, e.pos.y), c) <= 2000.0 for c in ((15e3, 15e3), (25e3, 5e3)))
    }
    assert cells == expected


# --- painted flag (Q-FOW-6) ---

# The recon UAV senses 3000 m (1500 m against the armor's stealth 0.5) and paints within 2000 m.
PAINT = replace(
    RULES,
    sensor_radius_m={**RULES.sensor_radius_m, "RECON_UAV": 3000.0, "ENEMY_RECON_UAV": 3000.0},
    paint_range_m=2000.0,
)


def recon(w: World, side: Side, x: float, y: float = 0.0) -> Entity:
    kind: UnitKind = "RECON_UAV" if side == "COALITION" else "ENEMY_RECON_UAV"
    e = put(w, kind, side, x, y)
    e.state, e.fuel = "LANDED", 100.0  # no path: it stays put
    return e


def test_painted_only_when_the_painter_tracks_it_within_paint_range() -> None:
    w = world(PAINT)
    recon(w, "COALITION", 0.0)
    near = put(w, ARMOR, "ENEMY", 1400.0)  # the UAV tracks it, inside 2000 m: painted
    truck = put(w, "ENEMY_CONVOY", "ENEMY", 0.0, 1900.0)  # stealth 1.0: tracked at 3000 m
    edge = put(w, "ENEMY_CONVOY", "ENEMY", 0.0, -2500.0)  # tracked, beyond paint range
    hidden = put(w, ARMOR, "ENEMY", 1800.0)  # inside paint range, beyond the UAV's 1500 m
    put(w, RADAR, "COALITION", 1800.0, 100.0)  # tracks `hidden` for the side, cannot paint
    enemy_uav = recon(w, "ENEMY", 0.0, 50_000.0)
    mine = put(w, TRUCK, "COALITION", 0.0, 51_000.0)
    run_to(w, 5)
    painted = {i for i, c in w.contacts["COALITION"].items() if c.painted}
    assert painted == {near.id, truck.id}
    assert tracked_by(w, "COALITION", edge.id) and tracked_by(w, "COALITION", hidden.id)
    assert [i for i, c in w.contacts["ENEMY"].items() if c.painted] == [mine.id]  # FOW-4
    assert side_view(w, "ENEMY").tracks[mine.id].painted
    assert enemy_uav.id not in w.contacts["COALITION"]


def test_paint_clears_with_coverage_and_is_never_on_a_last_known_track() -> None:
    w = world(PAINT)
    recon(w, "COALITION", 0.0)
    near = put(w, ARMOR, "ENEMY", 1400.0)
    out = put(w, "ENEMY_CONVOY", "ENEMY", 0.0, 2500.0)
    run_to(w, 5)
    assert w.contacts["COALITION"][near.id].painted
    assert not w.contacts["COALITION"][out.id].painted
    near.pos, out.pos = Vec2(9000.0, 0.0), Vec2(0.0, 1000.0)
    run_to(w, 9)
    assert w.contacts["COALITION"][near.id].painted  # the last pass holds (Q-FOW-6)
    run_to(w, 10)
    assert w.contacts["COALITION"][near.id] == Contact(ARMOR, Vec2(1400, 0), Vec2(0, 0), 0)
    assert w.contacts["COALITION"][out.id].painted
    restored = load(save(w))
    assert restored.contacts == w.contacts


# NX-372: range classes 200 m and {1000, 3000} m (a class spans up to 4 x its smallest radius),
# painters on both sides, and a masking region at x 0-2 km, y 0-1 km.
CLASSES = replace(PAINT, mask_cell_m=1000.0, masking={(0, 0): frozenset({"hills"}),
                                                      (1, 0): frozenset({"hills"})})  # fmt: skip
_MIXED: list[tuple[UnitKind, Side]] = [
    (RADAR, "COALITION"), (TRUCK, "COALITION"), ("RECON_UAV", "COALITION"),
    (ARMOR, "ENEMY"), ("ENEMY_CONVOY", "ENEMY"), ("ENEMY_RECON_UAV", "ENEMY"),
]  # fmt: skip
_KM = st.floats(-3000.0, 3000.0) | st.integers(-3, 3).map(lambda k: k * 1000.0)  # exact borders


def brute_painted(w: World, side: Side) -> list[int]:
    """O(n^2) oracle: enemies a painter of `side` tracks with its own sensor (its radius x the
    target's stealth, masking from its own regions) within `fow.paint_range_m`."""

    def paints(p: Entity, t: Entity) -> bool:
        radius = CLASSES.sensor_radius_m[p.kind]
        reach = radius * CLASSES.stealth[t.kind]
        dx, dy = t.pos.x - p.pos.x, t.pos.y - p.pos.y
        d2 = dx**2 + dy**2
        hidden = CLASSES.domain[t.kind] == "GROUND" and bool(_cell_regions(CLASSES, t))
        hidden = hidden and not (_cell_regions(CLASSES, t) & _cell_regions(CLASSES, p))
        # Same float arithmetic as the kernel: the grid's `*` filter, then `**` distances.
        in_grid = dx * dx + dy * dy <= radius * radius
        return in_grid and d2 <= reach * reach and d2 <= CLASSES.paint_range_m**2 and not hidden

    painters = [s for s in w.entities() if s.side == side and s.kind in CLASSES.painters]
    return [t.id for t in w.entities() if t.side != side and any(paints(p, t) for p in painters)]


def test_oracle_paints_per_painter_with_its_own_regions() -> None:
    w = world(CLASSES)
    recon(w, "COALITION", 0.0, 0.0)  # in the hills
    recon(w, "COALITION", 2500.0, 900.0)  # outside: tracks nothing hidden in the hills
    t = put(w, "ENEMY_CONVOY", "ENEMY", 1900.0, 900.0)  # in the hills, 600 m from the second
    run_to(w, 5)
    assert tracked_by(w, "COALITION", t.id)  # the first UAV tracks it, 1.9 km off: no paint
    assert brute_painted(w, "COALITION") == []
    assert not w.contacts["COALITION"][t.id].painted


def test_shipped_range_classes() -> None:
    # The healthy radii and the same x `damaged_sensor_mult` 0.8 (CB-6): two classes still.
    small = (2400.0, 3000.0, 4000.0, 5000.0, 6400.0, 8000.0)
    large = (32000.0, 40000.0, 48000.0, 60000.0, 96000.0, 120000.0)
    assert _class_cells(SHIPPED) == dict.fromkeys(small, 4000.0) | dict.fromkeys(large, 60000.0)


# Points where `dx**2 + dy**2 <= r**2` and `dx*dx + dy*dy <= r*r` disagree by one ulp (NX-372). The
# pass keeps the pre-NX-372 arithmetic: the grid keeps `dx*dx + dy*dy <= r*r` (sensor radius),
# then `_dist2` (`**`) decides against reach and paint range.
@pytest.mark.parametrize(
    ("x", "y"),
    [
        (877.1043746055911, 480.2998189128691),  # ** just over 1000 m, * on it
        (558.452538175239, 829.5364745480655),  # ** on 1000 m, * just over: the grid drops it
    ],
)
def test_track_border_keeps_the_old_float_arithmetic(x: float, y: float) -> None:
    w = world(PAINT)
    put(w, RADAR, "COALITION", 0.0)
    t = put(w, "ENEMY_CONVOY", "ENEMY", x, y)
    run_to(w, 5)
    assert not tracked_by(w, "COALITION", t.id)


@pytest.mark.parametrize(
    ("x", "y", "painted"),
    [
        (398.8845282485021, 1959.8191582704692, False),  # ** over 2000 m, * on it (QA repro)
        (1786.0470795940635, 900.0199050429482, False),  # ** over 2000 m, * on it
        (1713.6044666718396, 1031.290323721851, True),  # ** on 2000 m, * just over
    ],
)
def test_paint_border_keeps_the_old_float_arithmetic(x: float, y: float, painted: bool) -> None:
    w = world(PAINT)
    recon(w, "COALITION", 0.0)
    t = put(w, "ENEMY_CONVOY", "ENEMY", x, y)
    run_to(w, 5)
    assert tracked_by(w, "COALITION", t.id)  # inside the UAV's 3000 m
    assert w.contacts["COALITION"][t.id].painted is painted


@given(st.lists(st.tuples(st.sampled_from(_MIXED), _KM, _KM), max_size=30))
def test_tracks_and_paint_match_brute_force_across_range_classes(
    units: list[tuple[tuple[UnitKind, Side], float, float]],
) -> None:
    w = world(CLASSES)
    for (kind, side), x, y in units:
        e = put(w, kind, side, x, y)
        if kind in CLASSES.painters:
            e.state, e.fuel = "LANDED", 100.0  # stays put
    run_to(w, 5)
    for side in ("COALITION", "ENEMY"):
        assert list(w.contacts[side]) == brute(w, side, CLASSES)
        assert [i for i, c in w.contacts[side].items() if c.painted] == brute_painted(w, side)


# --- SC-10 and determinism at 1,000 entities ---


def sigint_world() -> World:
    """`test_fog.big_world` with every mobile unit moving, one tick before a refresh."""
    w = big_world()
    for e in w.entities():
        if SHIPPED.domain[e.kind] != "STATIC":
            e.vel = Vec2(1.0, 0.0)
        elif e.side == "ENEMY" and e.id % 12 == 0:
            e.kind = RADAR  # a test stand-in: half the enemy sites become radars
    w.sigint_age = SHIPPED.sigint_refresh_ticks - 1
    w.campaign.tick = 2  # tick 3 is no Tier 2 pass: only aging and SIGINT run
    return w


def test_sc10_smoke_sigint_1000_entities() -> None:
    w = sigint_world()
    start = time.perf_counter()
    sense(w)
    elapsed_ms = (time.perf_counter() - start) * 1000  # reported only, never asserted (§5)
    assert w.blobs["COALITION"] and w.blobs["ENEMY"]
    for side in ("COALITION", "ENEMY"):
        assert all(b.id.startswith("3-") for b in w.blobs[side])
    print(f"one SIGINT refresh at 1,000 entities: {elapsed_ms:.1f} ms")


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_fog_sigint import sigint_world\n"
    "from nexus.core.fog import sense\nfrom nexus.core.world import state_hash\n"
    "w = sigint_world(); sense(w); print(state_hash(w))"
)


def test_sigint_hash_is_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    w = sigint_world()
    sense(w)
    assert w.blobs["COALITION"] and w.blobs["ENEMY"]
    assert run("1") == run("2") == state_hash(w)


def test_a_disabled_radar_gives_no_sigint_range() -> None:
    """GAMEPLAY §5b: a Disabled facility does nothing, so it adds no SIGINT range (NX-124)."""
    w, _, _ = sigint_scene("COALITION")
    radar = next(e for e in w.entities() if e.kind == RADAR)
    radar.hp, radar.damage_state = 5, "DISABLED"
    run_to(w, 10)
    assert w.blobs["COALITION"] == ()
