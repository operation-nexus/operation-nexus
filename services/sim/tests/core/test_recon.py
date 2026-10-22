"""NX-379: Static recon that explores instead of feeding the air defenses (Q-SIM-87; THREAT-DIRECTOR
TD-2, TD-5, §5a; FOG-OF-WAR FOW-6a; GAMEPLAY §1b TB-2).

Runs on the shipped strait-1 config with the campaign layer off. Shipped numbers: RECON costs 2,
the scout loiters 600 game s within 5,000 m of its point, the candidate grid is 10,000 m. A sector
is 400 km x 80 km, so the grid holds up to 40 x 8 cells in it.
"""

import dataclasses
import math
import time
from fractions import Fraction

import pytest
from test_launch import (
    DR,
    RULES,
    clear_coalition_defenses,
    new_world,
    run_clock,
    skip,
    unit,
    window,
)
from test_launch import candidates as launch_candidates

from nexus.contracts.gen.common.enums import UnitKind
from nexus.core import operations as ops
from nexus.core.fog import side_view
from nexus.core.launch import _own, look
from nexus.core.logistics import plan_deploy
from nexus.core.provocation import validate
from nexus.core.rules import Rules
from nexus.core.world import Contact, FacilityMarker, Vec2, World, load, save, state_hash

RECON = tuple(o for o in DR.operations if o.id == "RECON")
RECON_ONLY: Rules = dataclasses.replace(
    RULES, director=dataclasses.replace(DR, operations=RECON, noise=Fraction(0))
)
FAR: Rules = dataclasses.replace(
    RULES, fuel_s={**RULES.fuel_s, "ENEMY_RECON_UAV": 1e9}
)  # no range limit
RADIUS = DR.recon_loiter_radius_m
LOITER = DR.recon_loiter_ticks
UAV: UnitKind = "ENEMY_RECON_UAV"


def marker(w: World, key: int, x: float, y: float, ring: int, state: str = "HEALTHY") -> None:
    """A coalition air-defense site the Static has discovered (FOW-13), last seen in `state`."""
    w.markers["ENEMY"][key] = FacilityMarker(
        "AIR_DEFENSE_SITE",
        None,
        Vec2(x, y),
        True,
        0,
        ring,
        state,  # type: ignore[arg-type]
    )


def point(w: World, sector: str, rules: Rules = RULES) -> tuple[Vec2, str] | None:
    view = side_view(w, "ENEMY")
    looked, now = w.director["ENEMY"].looked, w.campaign.running_ticks + 1
    return ops.recon_point(view, rules, _own(w, rules, "ENEMY"), sector, UAV, looked, now)


def clearance(start: Vec2, goal: Vec2, centre: Vec2) -> float:
    """Least distance from `centre` to the segment, by sampling it (independent of the code)."""
    steps = 2000
    return min(
        math.hypot(
            start.x + (goal.x - start.x) * k / steps - centre.x,
            start.y + (goal.y - start.y) * k / steps - centre.y,
        )
        for k in range(steps + 1)
    )


def recon_wheres(w: World) -> dict[str, tuple[ops.Where, ...]]:
    return {
        c.target: c.wheres[0] for c in launch_candidates(w, "PATTERN_OF_LIFE") if c.op.id == "RECON"
    }


def ring_field(w: World) -> None:
    """Four rings across the northern sector, 100 km apart, that together cover it."""
    for n, x in enumerate((50_000, 150_000, 250_000, 350_000)):
        marker(w, 9001 + n, x, 40_000, 75_000)


# --- the point ------------------------------------------------------------------------------------


def test_with_nothing_known_the_point_is_the_first_stale_cell_and_deterministic() -> None:
    w = new_world()
    got = point(w, "north", FAR)
    assert got is not None
    spot, origin = got
    assert (spot.x, spot.y) == (5_000, 5_000)  # every cell is missing (1): the tie goes by (x, y)
    assert origin == "east-airbase"  # the nearest Static base that spawns aircraft
    assert point(new_world(), "north", FAR) == got  # no draw: another world gives the same


def test_the_stalest_cell_wins_a_fresh_track_makes_its_area_fresh() -> None:
    w = new_world()
    view = side_view(w, "ENEMY")
    fade = RULES.track_fade_ticks
    # a current track at the first cell and a track lost half a fade ago at the second
    tracks = {1: Contact("STRIKE_FIGHTER", Vec2(5_000, 5_000), Vec2(0, 0), None)}
    old = {2: Contact("STRIKE_FIGHTER", Vec2(5_000, 15_000), Vec2(0, 0), fade // 2)}
    seen = dataclasses.replace(view, tracks=tracks, last_known=old)
    spot, _ = ops.recon_point(seen, FAR, _own(w, FAR, "ENEMY"), "north", UAV, {}, 1) or (None, "")
    assert spot is not None and (spot.x, spot.y) == (
        5_000,
        25_000,
    )  # the first cell with no track at all
    # the area of a track older than every missing one never beats a missing cell; with every
    # cell tracked the oldest wins
    every = {
        i: Contact(
            "STRIKE_FIGHTER",
            Vec2(x, y),
            Vec2(0, 0),
            fade // 2 if (x, y) == (45_000, 25_000) else None,
        )
        for i, (x, y) in enumerate(ops._grid(RULES, "north", DR.recon_grid_m))
    }
    full = dataclasses.replace(view, tracks=every, last_known={})
    spot, _ = ops.recon_point(full, FAR, _own(w, FAR, "ENEMY"), "north", UAV, {}, 1) or (None, "")
    assert spot is not None and (spot.x, spot.y) == (45_000, 25_000)


def test_a_point_the_scout_could_not_loiter_at_and_return_from_is_never_picked() -> None:
    w = new_world()
    spot, _ = point(w, "north") or (Vec2(0, 0), "")
    assert (spot.x, spot.y) != (5_000, 5_000)  # the stalest cell is out of range (305 km out)
    speed, fuel = RULES.speed_mps[UAV], RULES.fuel_s[UAV]
    start = Vec2(*RULES.roads.pos["east-airbase"])
    out = math.hypot(spot.x - start.x, spot.y - start.y)
    back = math.hypot(spot.x - start.x, spot.y - start.y)  # at most: it can land where it started
    loiter = LOITER * RULES.world_dt  # one fuel second per world second
    assert (out + back) / speed + loiter + RULES.bingo_reserve_frac * fuel <= fuel
    # the cell the picker refused is beyond that budget by plain arithmetic
    far = Vec2(5_000, 5_000)
    trip = 2 * math.hypot(far.x - start.x, far.y - start.y) / speed
    assert trip + loiter + RULES.bingo_reserve_frac * fuel > fuel


def test_no_route_crosses_a_known_active_ring_and_a_disabled_one_is_ignored() -> None:
    w = new_world()
    for n, (x, y) in enumerate([(60_000, 40_000), (150_000, 20_000), (310_000, 30_000)]):
        marker(w, 9001 + n, x, y, 45_000)
    marker(w, 9100, 5_000, 5_000, 30_000, "DISABLED")  # the stalest cell: last seen Disabled
    hit = 0
    for sector in ("north", "centre", "south"):
        got = point(w, sector)
        assert got is not None
        spot, origin = got
        start = Vec2(*RULES.roads.pos[origin])
        for m in (m for k, m in w.markers["ENEMY"].items() if m.state != "DISABLED"):
            assert m.ring_m is not None
            assert clearance(start, spot, m.pos) > m.ring_m + RADIUS
            hit += 1
    assert hit == 9
    free = new_world()
    marker(free, 9100, 5_000, 5_000, 30_000, "DISABLED")
    assert point(free, "north") == point(new_world(), "north")  # a Disabled site blocks nothing


def test_a_sector_covered_by_rings_is_skipped_and_the_others_are_not() -> None:
    w = new_world()
    ring_field(w)
    got = recon_wheres(w)
    assert "north" not in got and {"centre", "south"} <= set(got)
    assert point(w, "north") is None
    for where in got.values():  # the surviving scouts fly to a point, not a node
        assert where[0].node is None and where[0].pos is not None and where[0].origin


def test_the_point_and_route_come_from_the_view_not_from_the_true_coalition() -> None:
    quiet, busy = new_world(), new_world()
    # hidden state differs: coalition air defenses the Static has never seen, on the quiet world's
    # chosen point and across its routes
    spot, _ = point(quiet, "north") or (Vec2(0, 0), "")
    for n, (x, y) in enumerate([(spot.x, spot.y), (spot.x + 20_000, spot.y), (100_000, 20_000)]):
        site = unit(busy, "AIR_DEFENSE_SITE", "COALITION", "AI_GARRISON", "west-airbase")
        site.pos = Vec2(x, y)
        site.base_id = "west-airbase"
        assert n >= 0
    assert side_view(quiet, "ENEMY").markers == side_view(busy, "ENEMY").markers == {}
    for sector in ("north", "centre", "south"):
        assert point(busy, sector) == point(quiet, sector)
    assert recon_wheres(busy) == recon_wheres(quiet)
    marker(busy, 9001, spot.x, spot.y, 8_000)  # once it is discovered, the point moves
    assert point(busy, "north") != point(quiet, "north")


def test_the_spawn_base_is_where_the_route_was_checked_from() -> None:
    w = new_world()
    wheres = recon_wheres(w)
    events = window(w, "PATTERN_OF_LIFE", 2, RECON_ONLY)
    spawned = [e for e in events if e.kind == "UnitSpawned"]
    job = next(j for j in w.boards["ENEMY"].values() if j.kind == "SCOUT")
    got = wheres[job.key.split(":")[2]][0]
    assert len(spawned) == 1 and spawned[0].node_id == got.origin
    assert job.node is None and job.blob is None and job.pos == got.pos
    assert job.key.startswith("op:RECON:")


# --- cost -----------------------------------------------------------------------------------------


def test_recon_costs_two_and_is_paid_from_the_stock() -> None:
    w = new_world()
    before = sum(w.stock.values())
    events = window(w, "PATTERN_OF_LIFE", 2, RECON_ONLY)
    paid = sum(e.amount for e in events if e.kind == "SupplyConsumed")
    assert paid == 2 == before - sum(w.stock.values())
    assert len([e for e in events if e.kind == "UnitSpawned"]) == 1
    w = new_world()
    assert not [e for e in window(w, "PATTERN_OF_LIFE", 1, RECON_ONLY) if e.kind == "UnitSpawned"]


# --- loiter ---------------------------------------------------------------------------------------


def launched(seed: int = 1) -> tuple[World, int]:
    w = new_world(seed, RECON_ONLY)
    clear_coalition_defenses(w)  # nothing shoots the scout down: this is about its loiter
    window(w, "PATTERN_OF_LIFE", 2, RECON_ONLY)
    job = next(j for j in w.boards["ENEMY"].values() if j.kind == "SCOUT")
    return w, job.id


def test_the_scout_loiters_in_the_radius_for_loiter_s_then_the_job_is_done_and_it_goes_home() -> (
    None
):
    w, job_id = launched()
    job = w.boards["ENEMY"][job_id]
    scout = w.find(next(iter(job.claims)))
    assert scout is not None and job.pos is not None
    centre, seen, done, spans = job.pos, [], None, []
    for _ in range(40_000):
        for e in run_clock(w, 1):
            if e.kind == "JobDone" and e.job_id == job_id:
                done = w.campaign.running_ticks
        if done:
            break
        if job.arrived is not None:
            seen.append(math.hypot(scout.pos.x - centre.x, scout.pos.y - centre.y))
            spans.append((scout.pos.x, scout.pos.y))
    assert done is not None and job.arrived is not None
    assert LOITER <= done - job.arrived <= LOITER + 2 * RECON_ONLY.tasking.reeval_every_ticks  # type: ignore[union-attr]
    orbit = RECON_ONLY.min_speed_mps[UAV] * RECON_ONLY.orbit_period_s / math.tau
    assert max(seen) <= RADIUS + 2 * orbit  # within the radius, plus the orbit it turns in
    assert len(set(spans)) > 100 and max(seen) > 0.5 * RADIUS  # it moves around the point
    assert str(scout.state) == "RTB" and scout.job_id is None  # then home
    for _ in range(15_000):  # the flight home takes about 8,000 ticks
        run_clock(w, 1)
        if str(scout.state) == "LANDED":  # looked at every tick: the next launch reuses it at once
            break
    assert str(scout.state) == "LANDED" and scout.last_node == "east-airbase"


def test_a_lost_scout_fails_the_job_as_before_and_counts_as_a_loss() -> None:
    w, job_id = launched()
    job = w.boards["ENEMY"][job_id]
    scout = w.find(next(iter(job.claims)))
    assert scout is not None
    w.remove(scout.id)  # shot down on the way
    run_clock(w, 2 * RECON_ONLY.tasking.reeval_every_ticks)  # type: ignore[union-attr]
    left = w.boards["ENEMY"].get(job_id)
    assert left is None or (left.arrived is None and not left.claims)  # never loitered, never done


def test_live_and_restored_worlds_agree_with_a_loitering_scout() -> None:
    w, job_id = launched()
    while w.boards["ENEMY"][job_id].arrived is None:
        run_clock(w, 10)
    run_clock(w, 200)  # mid-loiter, with a corner leg flown
    again = load(save(w))
    again.rules = RECON_ONLY
    assert state_hash(again) == state_hash(w)
    live, restored = run_clock(w, 6500), run_clock(again, 6500)
    assert [e.model_dump(by_alias=True) for e in live] == [
        e.model_dump(by_alias=True) for e in restored
    ]
    assert state_hash(again) == state_hash(w)
    assert any(e.kind == "JobDone" for e in live)  # the loiter ended in the compared span


def test_two_runs_of_the_same_seed_are_identical() -> None:
    def run() -> tuple[list[object], str]:
        w, _ = launched(3)
        events = run_clock(w, 15_000)
        return [e.model_dump(by_alias=True) for e in events], state_hash(w)

    first = run()
    assert first == run() and first[0]


def test_a_snapshot_of_the_old_format_is_refused_and_a_malformed_point_job_too() -> None:
    import msgpack

    w, job_id = launched()
    run_clock(w, 5)
    raw = msgpack.unpackb(save(w), raw=False)
    raw["v"] = 21
    with pytest.raises(ValueError, match="unsupported snapshot format version 21"):
        load(msgpack.packb(raw, use_bin_type=True))
    raw = msgpack.unpackb(save(w), raw=False)
    jobs = raw["boards"]["ENEMY"]
    scout = next(j for j in jobs if j["id"] == job_id)
    scout["pos"] = None
    with pytest.raises(ValueError, match="targets a node or a blob"):
        load(msgpack.packb(raw, use_bin_type=True))
    scout["pos"], scout["arrived"] = [0, 0], 10**9
    with pytest.raises(ValueError, match="loiters"):
        load(msgpack.packb(raw, use_bin_type=True))


# --- speed ----------------------------------------------------------------------------------------


def test_recon_points_for_every_sector_at_a_thousand_tracks_are_fast() -> None:
    w = new_world()
    for n in range(10):
        marker(w, 9001 + n, 30_000 + 37_000 * n, 20_000 + 21_000 * (n % 9), 30_000)
    view = side_view(w, "ENEMY")
    seen = {
        i: Contact(
            "STRIKE_FIGHTER",
            Vec2(397 * i % 400_000, 241 * i % 240_000),
            Vec2(0, 0),
            None if i % 2 else i,
        )
        for i in range(1000)
    }
    busy = dataclasses.replace(
        view,
        tracks={i: c for i, c in seen.items() if c.age is None},
        last_known={i: c for i, c in seen.items() if c.age is not None},
    )
    own = _own(w, RULES, "ENEMY")
    start = time.perf_counter()
    for _ in range(5):
        for sector in ("north", "centre", "south"):
            ops.recon_point(busy, RULES, own, sector, UAV, {}, 1)
    per_window = (time.perf_counter() - start) / 5
    assert per_window < 0.1, per_window  # the existing 1,000-entity window allows 0.5 s in all


# --- visit memory (Q-SIM-87) ------------------------------------------------------------------


def look_at(w: World, x: float, y: float) -> None:
    """A Static scout sits at (x, y) for one decision window."""
    scout = unit(w, UAV, "ENEMY", "ENEMY_DIRECTOR", "east-airbase")
    scout.pos = Vec2(x, y)
    look(w, RULES, "ENEMY", w.director["ENEMY"], w.campaign.running_ticks + 1)
    w.remove(scout.id)


def test_what_a_sensor_covered_is_remembered_with_or_without_tracks() -> None:
    w = new_world()
    clear_coalition_defenses(w)
    for e in list(w.entities()):
        if e.side == "ENEMY":
            w.remove(e.id)  # no Static sensor: nothing is looked at
    skip(w, 100)
    look(w, RULES, "ENEMY", w.director["ENEMY"], 101)
    assert w.director["ENEMY"].looked == {}
    look_at(w, 55_000, 45_000)
    looked = w.director["ENEMY"].looked
    radius = RULES.sensor_radius(UAV, "HEALTHY")
    assert looked  # the scout saw cells in which there is no track
    for key, tick in looked.items():
        x, y = (int(p) for p in key.split(":"))
        assert tick == 101 and x % 10_000 == 5_000 and y % 10_000 == 5_000
        assert math.hypot(x - 55_000, y - 45_000) <= radius
    assert "55000:45000" in looked and "45000:45000" in looked  # within the radius of the scout
    assert not [k for k in ("5000:5000", "395000:235000") if k in looked]


def test_a_mark_older_than_memory_s_is_dropped() -> None:
    w = new_world()
    w.director["ENEMY"].looked = {"5000:5000": 1}
    look(w, RULES, "ENEMY", w.director["ENEMY"], 1 + DR.recon_memory_ticks)
    assert "5000:5000" not in w.director["ENEMY"].looked  # staleness 1 again, as no mark
    w.director["ENEMY"].looked = {"5000:5000": 2}
    look(w, RULES, "ENEMY", w.director["ENEMY"], 1 + DR.recon_memory_ticks)
    assert w.director["ENEMY"].looked["5000:5000"] == 2


def test_a_looked_cell_is_not_picked_again_so_the_scouts_visit_distinct_cells() -> None:
    w = new_world()
    clear_coalition_defenses(w)
    picked, repeated = [], []
    for _ in range(8):
        skip(w, DR.window_ticks)
        spot, _ = point(w, "north", FAR) or (Vec2(0, 0), "")
        picked.append((spot.x, spot.y))
        look_at(w, spot.x, spot.y)
        again = ops.recon_point(
            side_view(w, "ENEMY"), FAR, _own(w, FAR, "ENEMY"), "north", UAV, {}, 1
        )  # without the memory the same cell is picked again
        repeated.append(again[0] if again else None)
    assert len(set(picked)) == 8
    assert len(set(repeated)) == 1


def test_looks_and_tracks_combine_the_fresher_wins_and_staleness_rises_with_time() -> None:
    w = new_world()
    view = side_view(w, "ENEMY")
    cells = [(5_000, 5_000), (15_000, 5_000)]
    fade = RULES.track_fade_ticks
    far_track = {1: Contact("STRIKE_FIGHTER", Vec2(5_000, 5_000), Vec2(0, 0), fade // 2)}
    seen = dataclasses.replace(view, tracks={}, last_known=far_track)
    half = DR.recon_memory_ticks // 2
    looked = {"5000:5000": 1, "15000:5000": 1 + half}
    got = ops._picture(seen, FAR, DR, cells, looked, 1 + half)
    assert got[5_000, 5_000] == Fraction(1, 2)  # the look (half the memory ago) ties the track
    assert got[15_000, 5_000] == 0  # looked at this very tick
    assert ops._picture(seen, FAR, DR, cells, {}, 1 + half)[5_000, 5_000] == Fraction(1, 2)
    assert ops._picture(seen, FAR, DR, cells, {"5000:5000": 1 + half}, 1 + half)[5_000, 5_000] == 0


def test_live_and_restored_worlds_agree_with_a_recon_memory_and_a_bad_cell_is_refused() -> None:
    import msgpack

    w, _ = launched()
    run_clock(w, 2 * DR.window_ticks + 5)
    assert w.director["ENEMY"].looked
    again = load(save(w))
    again.rules = RECON_ONLY
    assert again.director["ENEMY"].looked == w.director["ENEMY"].looked
    assert state_hash(again) == state_hash(w)
    live, restored = run_clock(w, 3 * DR.window_ticks), run_clock(again, 3 * DR.window_ticks)
    assert [e.model_dump(by_alias=True) for e in live] == [
        e.model_dump(by_alias=True) for e in restored
    ]
    assert state_hash(again) == state_hash(w)
    for bad in ({"5001:5000": 1}, {"5000:5000": 10**9}, {"x:5000": 1}, {"5000:245000": 1}):
        raw = msgpack.unpackb(save(w), raw=False)
        raw["director"]["ENEMY"]["looked"] = bad
        with pytest.raises(ValueError):
            restored_bad = load(msgpack.packb(raw, use_bin_type=True))
            validate(restored_bad, RECON_ONLY)


def test_recording_a_thousand_entities_looks_is_fast_and_repeatable() -> None:
    w = new_world()
    for i in range(1000):
        e = unit(w, UAV, "ENEMY", "ENEMY_DIRECTOR", "east-airbase")
        e.pos = Vec2(397 * i % 400_000, 241 * i % 240_000)
    s = w.director["ENEMY"]
    start = time.perf_counter()
    for n in range(5):
        look(w, RULES, "ENEMY", s, 1 + n)
    per_window = (time.perf_counter() - start) / 5
    assert per_window < 0.25, per_window
    first = dict(s.looked)
    s.looked = {}
    look(w, RULES, "ENEMY", s, 5)  # from scratch, the same marks
    assert s.looked == first and list(s.looked) == sorted(
        s.looked, key=lambda k: list(first).index(k)
    )


# --- one scout per point job, ring abort, validation, launch base (QA round) --------------------


def test_a_point_scout_job_never_takes_a_second_scout_even_when_every_job_is_full() -> None:
    w = new_world(1, RECON_ONLY)
    clear_coalition_defenses(w)
    window(w, "PATTERN_OF_LIFE", 6, RECON_ONLY)  # three RECON operations, one scout each
    spare = [unit(w, UAV, "ENEMY", "ENEMY_DIRECTOR", "east-airbase") for _ in range(3)]
    jobs = [j for j in w.boards["ENEMY"].values() if j.kind == "SCOUT"]
    assert len(jobs) == 3 and all(len(j.claims) == j.slots == 1 for j in jobs)
    for _ in range(400):  # eight board passes: the idle scouts look for a job each time
        run_clock(w, 1)
        for j in w.boards["ENEMY"].values():
            assert len(j.claims) <= j.slots
    assert all(u.job_id is None for u in spare)  # they stayed idle, burning nothing


def test_a_ring_that_now_covers_the_point_ends_the_job_and_the_scout_goes_home() -> None:
    w, job_id = launched()
    job = w.boards["ENEMY"][job_id]
    scout = w.find(next(iter(job.claims)))
    assert scout is not None and job.pos is not None
    while job.arrived is None:
        run_clock(w, 10)
    done = False
    marker(w, 9001, job.pos.x + 3_000, job.pos.y, 4_000)  # a site found 3 km away, ring 4 km
    for _ in range(3 * RECON_ONLY.tasking.reeval_every_ticks):  # type: ignore[union-attr]
        done |= any(e.kind == "JobDone" and e.job_id == job_id for e in run_clock(w, 1))
    assert done and job_id not in w.boards["ENEMY"]
    assert str(scout.state) == "RTB" and scout.job_id is None
    # a ring that is farther than ring + loiter radius, or that was last seen Disabled, does not
    w2, job2 = launched()
    j2 = w2.boards["ENEMY"][job2]
    assert j2.pos is not None
    marker(w2, 9001, j2.pos.x + 4_000 + RADIUS + 1_000, j2.pos.y, 4_000)
    marker(w2, 9002, j2.pos.x, j2.pos.y, 30_000, "DISABLED")
    run_clock(w2, 3 * RECON_ONLY.tasking.reeval_every_ticks)  # type: ignore[union-attr]
    assert job2 in w2.boards["ENEMY"]


def test_a_point_job_outside_the_theater_is_refused() -> None:
    import msgpack

    w, job_id = launched()
    run_clock(w, 5)
    raw = msgpack.unpackb(save(w), raw=False)
    scout = next(j for j in raw["boards"]["ENEMY"] if j["id"] == job_id)
    scout["pos"] = [500_000_000, 5_000_000]  # mm: x = 500 km, the theater is 400 km wide
    with pytest.raises(ValueError, match="outside the theater"):
        validate(load(msgpack.packb(raw, use_bin_type=True)), RECON_ONLY)


def test_launch_base_is_the_base_plan_deploy_picks_for_every_node_and_stock_level() -> None:
    w = new_world()
    own_rules = RULES
    for floor_east in (False, True):  # the nearest airbase with and without surplus
        if floor_east:
            w.stock["east-airbase"] = RULES.supply.starve_floor["east-airbase"]
        view = side_view(w, "ENEMY")
        own = _own(w, own_rules, "ENEMY")
        for node, (x, y) in sorted(RULES.roads.pos.items()):
            if node == RULES.supply.rear["ENEMY"]:
                continue  # a JOIN to its own sanctuary spawns there: no choice to compare
            planned = plan_deploy(w, RULES, "ENEMY", UAV, node)
            expect = planned[0] if planned else RULES.supply.rear["ENEMY"]
            assert ops.launch_base(view, RULES, own, UAV, Vec2(x, y)) == expect, (node, floor_east)
