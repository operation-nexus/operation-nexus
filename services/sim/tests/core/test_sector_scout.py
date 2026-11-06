"""NX-512: the coalition's sector scout job (GAMEPLAY §1b item 203, Q-SIM-134, Q-TEST-14).

Runs on the strait-1 config with the pre-5b fixture and the job on (`scout_sector_points` 1, the
shipped default; the fixture turns it off for the older tests). Shipped numbers: the board passes
every 50 ticks, a point is stale after 30 game min (18,000 ticks), the scout loiters 6,000 ticks
within 5,000 m, the candidate grid is 10,000 m, and a SIGINT track fades in 300 ticks.
"""

import dataclasses
import itertools
import math
import re

import msgpack
import pytest
from fixture_pre_5b import pre_5b_config
from test_join import CAMPAIGN_ID, cid

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.core import operations as ops
from nexus.core import tasking_gen as tg
from nexus.core.fog import side_view
from nexus.core.launch import _own
from nexus.core.provocation import validate
from nexus.core.rules import DirectorRules, Rules, TaskingRules, sector_at
from nexus.core.step import step
from nexus.core.tasking import Routes, _feasible, run
from nexus.core.world import (
    Contact,
    Entity,
    FacilityMarker,
    Job,
    Vec2,
    World,
    load,
    save,
    state_hash,
)
from nexus.runtime.campaign_config import start_campaign

CONFIG = pre_5b_config({"tasking.scout_sector_points": 1})
RULES: Rules = dataclasses.replace(CONFIG.rules, campaign=None, garrison_quota={})
assert RULES.tasking is not None and RULES.director is not None
TR: TaskingRules = RULES.tasking
DR: DirectorRules = RULES.director
EVERY = TR.reeval_every_ticks
STALE = TR.scout_sector_stale_ticks
RADIUS = DR.recon_loiter_radius_m
UAV: UnitKind = "RECON_UAV"
SECTORS = ("centre", "north", "south")
KEY = re.compile(r"scout:pt:(centre|north|south):0")


def new_world(seed: int = 1, rules: Rules = RULES) -> World:
    return start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(CONFIG, rules=rules))


def blind(w: World) -> World:
    """No coalition sensor (its radar and air-defense sites go), so nothing is looked at."""
    for e in list(w.entities()):
        if e.side == "COALITION" and e.base_id:
            w.remove(e.id)
    return w


def now(w: World) -> int:
    return w.campaign.running_ticks + 1


def specs(w: World, rules: Rules = RULES) -> dict[str, Vec2]:
    """The generator's sector scout specs this pass, key to point (no post gate, no board)."""
    assert rules.tasking is not None
    out = tg._sector_scouts(w, rules, rules.tasking, "COALITION", side_view(w, "COALITION"))
    got = {s.key: s.pos for s in out}
    assert all(p is not None for p in got.values())
    return {k: p for k, p in got.items() if p is not None}


def recon(w: World, sector: str, looked: dict[str, int]) -> tuple[Vec2, str] | None:
    """The Static's own rule on the coalition's view (parity, §0 item 3)."""
    view = side_view(w, "COALITION")
    return ops.recon_point(view, RULES, _own(w, RULES, "COALITION"), sector, UAV, looked, now(w))


def board_pass(w: World) -> list[Event]:
    """Advance the clock to the next due running tick and run one board pass there."""
    w.campaign.running_ticks = (w.campaign.running_ticks // EVERY + 1) * EVERY - 1
    out: list[Event] = []
    run(w, out)
    w.campaign.running_ticks += 1
    return out


def sector_jobs(w: World) -> dict[str, Job]:
    return {j.key: j for j in w.boards["COALITION"].values() if j.key.startswith("scout:pt:")}


def ring(w: World, key: int, x: float, y: float, radius: int, state: str = "HEALTHY") -> None:
    """A Static air-defense site the coalition has discovered, last seen in `state`."""
    marker = FacilityMarker("AIR_DEFENSE_SITE", None, Vec2(x, y), True, 0, radius, state)  # type: ignore[arg-type]
    w.markers["COALITION"][key] = marker


def uav(w: World, node: str = "haven") -> Entity:
    e = w.spawn(
        UAV, "COALITION", "COMMANDER", Vec2(*RULES.roads.pos[node]),
        commander_id=cid(w._next_entity_id),
    )  # fmt: skip
    e.last_node, e.state, e.fuel = node, "LANDED", RULES.fuel_s[UAV]
    return e


def look_all(w: World, sector: str, tick: int) -> None:
    for x, y in ops._grid(RULES, sector, DR.recon_grid_m):
        w.director["COALITION"].looked[ops.cell_key(x, y)] = tick


# --- the pick -------------------------------------------------------------------------------------


def test_the_pick_is_the_statics_recon_point_on_the_coalition_view() -> None:
    w = blind(new_world())
    got = specs(w)
    assert set(got) == {f"scout:pt:{s}:0" for s in SECTORS}
    for s in SECTORS:
        pick = recon(w, s, {})
        assert pick is not None and got[f"scout:pt:{s}:0"] == pick[0]
        assert sector_at(RULES, pick[0].x, pick[0].y) == s
    assert specs(blind(new_world(7))) == got  # no draw: another seed gives the same


def test_stalest_first_and_ties_by_x_then_y() -> None:
    w = blind(new_world())
    first = specs(w)["scout:pt:north:0"]
    # every cell is unseen (1): the tie went by (x, y); a cell looked at long ago (but within
    # memory) is less stale than an unseen one, so the next unseen cell wins
    w.director["COALITION"].looked[ops.cell_key(first.x, first.y)] = now(w) - STALE
    second = specs(w)["scout:pt:north:0"]
    assert second != first and (second.x, second.y) > (first.x, first.y)


def test_a_ring_on_the_point_or_route_moves_the_pick_and_a_disabled_one_does_not() -> None:
    w = blind(new_world())
    first = specs(w)["scout:pt:north:0"]
    ring(w, 9001, first.x, first.y, 8_000, "DISABLED")
    assert specs(w)["scout:pt:north:0"] == first
    ring(w, 9001, first.x, first.y, 8_000)
    moved = specs(w)["scout:pt:north:0"]
    assert moved != first
    assert math.hypot(moved.x - first.x, moved.y - first.y) > 8_000 + RADIUS


def test_the_pick_leaves_room_to_loiter_and_land_with_the_bingo_reserve() -> None:
    w = blind(new_world())
    for s in SECTORS:
        pick = recon(w, s, {})
        assert pick is not None
        spot, origin = pick
        start = Vec2(*RULES.roads.pos[origin])
        homes = [RULES.roads.pos[n] for n in RULES.landing_nodes if w.owner.get(n) == "COALITION"]
        back = min(math.hypot(spot.x - x, spot.y - y) for x, y in homes)
        flight = (math.hypot(spot.x - start.x, spot.y - start.y) + back) / RULES.speed_mps[UAV]
        loiter = DR.recon_loiter_ticks * RULES.world_dt
        fuel = RULES.fuel_s[UAV]
        assert flight + loiter + RULES.bingo_reserve_frac * fuel <= fuel


# --- the staleness gate ---------------------------------------------------------------------------


def test_nothing_stale_no_job_and_the_gate_opens_at_stale_min() -> None:
    w = blind(new_world())
    first = specs(w)["scout:pt:north:0"]
    look_all(w, "north", now(w) - STALE + 1)
    assert "scout:pt:north:0" not in specs(w)  # every cell covered 1 tick too recently
    look_all(w, "north", now(w) - STALE)
    assert specs(w)["scout:pt:north:0"] == first  # all equally stale again: the (x, y) tie


def test_a_fresher_track_within_the_loiter_radius_blocks_a_point() -> None:
    w = blind(new_world())
    first = specs(w)["scout:pt:north:0"]
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", first, Vec2(0, 0), STALE - 1)
    moved = specs(w)["scout:pt:north:0"]
    assert math.hypot(moved.x - first.x, moved.y - first.y) > RADIUS
    edge = Vec2(first.x + RADIUS, first.y)  # exactly the loiter radius away still blocks
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", edge, Vec2(0, 0), STALE - 1)
    assert specs(w).get("scout:pt:north:0") not in (None, first)
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", first, Vec2(0, 0), STALE)
    assert specs(w)["scout:pt:north:0"] == first  # as old as the gate: no longer fresher


def test_a_cell_that_ranks_stalest_but_fails_the_gate_is_walked_past() -> None:
    # A track lost longer than it takes to fade (300 ticks) reads as unseen in the picture (1, the
    # tie), so it ranks first by (x, y), but it is fresher than the gate (18,000 ticks): the board
    # posts the next stalest cell that passes, not no job (item 203: "the k-th stalest passing").
    w = blind(new_world())
    first = specs(w)["scout:pt:north:0"]
    age = RULES.track_fade_ticks + 1
    assert age < STALE
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", first, Vec2(0, 0), age)
    assert recon(w, "north", {}) == recon(blind(new_world()), "north", {})  # still ranked first
    moved = specs(w).get("scout:pt:north:0")
    assert moved is not None and math.hypot(moved.x - first.x, moved.y - first.y) > RADIUS


def test_with_a_long_fade_a_cell_seen_too_recently_is_walked_past_too() -> None:
    # With `fow.track_fade_s` above the gate (not shipped), a passing cell can read fresher than one
    # a sensor covered just inside the gate: here the only passing cell holds a track exactly as
    # old as the gate (0.25 with the fade at 4x the gate), every other cell was looked at just
    # inside it (about 0.5). The board still posts the passing cell, not no job.
    slow = dataclasses.replace(RULES, track_fade_ticks=4 * STALE)
    w = blind(new_world(rules=slow))
    first = specs(w, slow)["scout:pt:north:0"]
    look_all(w, "north", now(w) - STALE + 1)
    del w.director["COALITION"].looked[ops.cell_key(first.x, first.y)]
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", first, Vec2(0, 0), STALE)
    assert specs(w, slow).get("scout:pt:north:0") == first


# --- count and keys -------------------------------------------------------------------------------


def test_up_to_points_per_sector_spaced_twice_the_loiter_radius() -> None:
    two = dataclasses.replace(RULES, tasking=dataclasses.replace(TR, scout_sector_points=2))
    w = blind(new_world(rules=two))
    got = specs(w, two)
    assert sorted(got) == sorted(f"scout:pt:{s}:{k}" for s in SECTORS for k in (0, 1))
    for s in SECTORS:
        a, b = got[f"scout:pt:{s}:0"], got[f"scout:pt:{s}:1"]
        # with every cell as stale, the next one in (x, y) order: exactly 2x the radius is allowed
        assert math.hypot(a.x - b.x, a.y - b.y) == 2 * RADIUS == DR.recon_grid_m
    assert got["scout:pt:north:0"] == specs(blind(new_world()))["scout:pt:north:0"]


def test_points_zero_turns_the_job_off() -> None:
    off = dataclasses.replace(RULES, tasking=dataclasses.replace(TR, scout_sector_points=0))
    w = blind(new_world(rules=off))
    assert specs(w, off) == {}
    for _ in range(3):
        board_pass(w)
    assert sector_jobs(w) == {}


def test_the_static_board_posts_no_sector_scout() -> None:
    w = blind(new_world())
    assert list(tg._sector_scouts(w, RULES, TR, "ENEMY", side_view(w, "ENEMY"))) == []


# --- the job on the board -------------------------------------------------------------------------


def test_the_job_fields_and_the_scout_caps() -> None:
    w = blind(new_world())
    board_pass(w)
    jobs = sector_jobs(w)
    assert len(jobs) == 1  # one new scout job per `scout_post_interval_min`
    (job,) = jobs.values()
    assert KEY.fullmatch(job.key) and job.kind == "SCOUT"
    assert job.node is None and job.blob is None and job.pos is not None
    assert job.slots == TR.slots["SCOUT"] and job.urgency == TR.scout_sector_urgency_milli == 500
    for _ in range(4 * TR.scout_post_interval_ticks // EVERY):
        board_pass(w)
        assert len([j for j in w.boards["COALITION"].values() if j.key.startswith("scout:")]) <= (
            TR.scout_open_max
        )
    assert len(sector_jobs(w)) == 3  # one per sector by now, each its own interval apart
    created = sorted(j.created for j in sector_jobs(w).values())
    assert all(b - a >= TR.scout_post_interval_ticks for a, b in itertools.pairwise(created))


def test_an_unclaimed_job_whose_point_is_seen_is_withdrawn_and_the_sector_cools_down() -> None:
    w = blind(new_world())
    board_pass(w)
    (job,) = sector_jobs(w).values()
    sector = job.key.split(":")[2]
    assert job.pos is not None
    w.director["COALITION"].looked[ops.cell_key(job.pos.x, job.pos.y)] = now(w)
    events = board_pass(w)
    assert [e.job_id for e in events if isinstance(e, JobExpired)] == [job.id]
    until = w.cooldown["COALITION"][f"scout:pt:{sector}"]
    assert until == w.campaign.running_ticks + TR.scout_cooldown_ticks
    while w.campaign.running_ticks + EVERY < until:
        board_pass(w)
        assert f"scout:pt:{sector}:0" not in sector_jobs(w)
    for _ in range(2 * TR.scout_post_interval_ticks // EVERY):
        board_pass(w)
    assert f"scout:pt:{sector}:0" in sector_jobs(w)  # posted again after the cooldown


def test_an_unclaimed_job_under_a_newly_discovered_ring_is_withdrawn() -> None:
    w = blind(new_world())
    board_pass(w)
    (job,) = sector_jobs(w).values()
    assert job.pos is not None
    ring(w, 9001, job.pos.x + RADIUS + 1_000, job.pos.y, 1_000)  # within the loiter radius
    events = board_pass(w)
    assert job.id in [e.job_id for e in events if isinstance(e, JobExpired)]


def test_an_unclaimed_job_near_a_fresh_track_is_withdrawn() -> None:
    w = blind(new_world())
    board_pass(w)
    (job,) = sector_jobs(w).values()
    assert job.pos is not None
    near = Vec2(job.pos.x + RADIUS, job.pos.y)  # exactly the loiter radius away
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", near, Vec2(0, 0), STALE - 1)
    events = board_pass(w)
    assert job.id in [e.job_id for e in events if isinstance(e, JobExpired)]


def test_an_open_job_keeps_its_point_while_it_stays_stale() -> None:
    w = blind(new_world())
    board_pass(w)
    (job,) = sector_jobs(w).values()
    pos = job.pos
    # the picture changes so that a fresh pick would move, but the open job's point is fixed
    assert pos is not None
    w.director["COALITION"].looked[ops.cell_key(pos.x - DR.recon_grid_m, pos.y)] = 1
    board_pass(w)
    assert sector_jobs(w)[job.key] is job and job.pos == pos


def test_a_claimed_job_is_not_moved_or_withdrawn_when_its_point_is_seen() -> None:
    w = blind(new_world())
    scout = uav(w)
    board_pass(w)
    (job,) = sector_jobs(w).values()
    assert list(job.claims) == [scout.id] and scout.job_id == job.id
    pos = job.pos
    assert pos is not None
    w.director["COALITION"].looked[ops.cell_key(pos.x, pos.y)] = now(w)
    w.contacts["COALITION"][900] = Contact("ENEMY_ARMOR", pos, Vec2(0, 0), None)
    assert specs(w)[job.key] == pos  # still generated, at its own point
    board_pass(w)
    assert sector_jobs(w)[job.key] is job and job.pos == pos and list(job.claims) == [scout.id]


# --- taking it ------------------------------------------------------------------------------------


def test_a_claimant_must_have_the_fuel_to_loiter_too() -> None:
    w = blind(new_world())
    board_pass(w)
    (job,) = sector_jobs(w).values()
    assert job.pos is not None
    scout = uav(w)
    home = Vec2(*RULES.roads.pos["haven"])
    trip = 2 * math.hypot(job.pos.x - home.x, job.pos.y - home.y) / RULES.speed_mps[UAV]
    reserve = RULES.bingo_reserve_frac * RULES.fuel_s[UAV]
    loiter = DR.recon_loiter_ticks * RULES.world_dt
    point = dataclasses.replace(job, key="op:RECON:north:0", claims={})  # the Static's: no loiter
    scout.fuel = trip + reserve + loiter / 2  # enough to fly there and back, not to loiter
    assert _feasible(w, RULES, Routes(), scout, point) == "ok"
    assert _feasible(w, RULES, Routes(), scout, job) == "refuel"
    scout.fuel = trip + reserve + loiter + 1
    assert _feasible(w, RULES, Routes(), scout, job) == "ok"


def test_a_claimant_whose_route_crosses_a_known_ring_does_not_take_it() -> None:
    w = blind(new_world())
    board_pass(w)
    (job,) = sector_jobs(w).values()
    assert job.pos is not None
    scout = uav(w)
    assert _feasible(w, RULES, Routes(), scout, job) == "ok"
    home = Vec2(*RULES.roads.pos["haven"])
    mid = Vec2((home.x + job.pos.x) / 2, (home.y + job.pos.y) / 2)
    ring(w, 9001, mid.x, mid.y, 2_000)
    assert _feasible(w, RULES, Routes(), scout, job) == "no"


def test_the_scout_loiters_then_the_job_is_done_and_pays_no_new_reward() -> None:
    w = blind(new_world())
    scout = uav(w)
    board_pass(w)
    (job,) = sector_jobs(w).values()
    assert list(job.claims) == [scout.id]
    done: list[JobDone] = []
    for _ in range(60_000):
        events = step(w, [])
        done = [e for e in events if isinstance(e, JobDone) and e.job_id == job.id]
        if done:
            break
    assert done and job.arrived is not None
    assert (
        DR.recon_loiter_ticks
        <= w.campaign.running_ticks - job.arrived
        <= (DR.recon_loiter_ticks + 2 * EVERY)
    )
    assert [p.entity_id for p in done[0].participants] == [scout.id]
    # no XP or merit (Q-TEST-14, PROG-13): the outcome is the JobDone alone
    assert str(scout.state) == "RTB" and scout.job_id is None
    assert job.key not in sector_jobs(w)


# --- snapshot, hash, loader -----------------------------------------------------------------------


def scene() -> World:
    """Coalition sensors on (looked marks) and a sector scout job on the board, by the clock."""
    w = new_world()
    for _ in range(3 * EVERY + 10):
        step(w, [])
    assert w.director["COALITION"].looked and sector_jobs(w)
    return w


def test_a_restored_world_agrees_with_the_live_one_and_the_hash_covers_the_marks() -> None:
    live = scene()
    again = load(save(live))
    again.rules = RULES
    assert state_hash(again) == state_hash(live)
    assert again.director["COALITION"].looked == live.director["COALITION"].looked
    for _ in range(TR.scout_post_interval_ticks + 2 * EVERY):
        assert step(again, []) == step(live, [])
    assert state_hash(again) == state_hash(live)
    assert len(sector_jobs(live)) == 2  # the second one was posted after the restore
    marked = load(save(live))
    marked.director["COALITION"].looked["5000:5000"] = 1
    assert state_hash(marked) != state_hash(live)


def test_two_runs_with_the_same_seed_give_the_same_events_and_hash() -> None:
    def once() -> tuple[str, list[Event]]:
        w = new_world(3)
        uav(w)
        events = [e for _ in range(600) for e in step(w, [])]
        return state_hash(w), events

    assert once() == once()


def _sector(raw: dict) -> dict:  # type: ignore[type-arg]
    return next(j for j in raw["boards"]["COALITION"] if j["key"].startswith("scout:pt:"))


def test_the_loader_accepts_a_sector_scout_job() -> None:
    raw = msgpack.unpackb(save(scene()), raw=False)
    assert _sector(raw)["urgency"] == 500
    again = load(msgpack.packb(raw, use_bin_type=True))
    assert [j.key for j in again.boards["COALITION"].values() if j.key.startswith("scout:pt:")]


def _to_enemy(raw: dict) -> None:  # type: ignore[type-arg]
    job = _sector(raw)
    raw["boards"]["COALITION"].remove(job)
    raw["boards"]["ENEMY"].append(job)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda r: _sector(r).update(key="scout:pt:north", urgency=1000),
            "targets a node or a blob",
        ),
        (
            lambda r: _sector(r).update(key="scout:pt:north:01", urgency=1000),
            "targets a node or a blob",
        ),
        (lambda r: _sector(r).update(key="scout:pt::0", urgency=1000), "targets a node or a blob"),
        (
            lambda r: _sector(r).update(key="scout:pt:north:0:1", urgency=1000),
            "targets a node or a blob",
        ),
        (lambda r: _sector(r).update(key="scout:pt:north"), "job urgency must be an int >= 1000"),
        (_to_enemy, "job urgency must be an int >= 1000"),
        (lambda r: _sector(r).update(urgency=0), "job urgency must be an int >= 1,"),
        (lambda r: _sector(r).update(urgency=-5), "job urgency must be an int >= 1,"),
    ],
)
def test_the_loader_refuses_a_bad_sector_scout_job(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    raw = msgpack.unpackb(save(scene()), raw=False)
    mutate(raw)
    with pytest.raises(ValueError, match=message):
        load(msgpack.packb(raw, use_bin_type=True))


def test_an_enemy_board_sector_scout_at_urgency_one_is_still_refused() -> None:
    raw = msgpack.unpackb(save(scene()), raw=False)
    _sector(raw).update(urgency=1000)
    _to_enemy(raw)
    with pytest.raises(ValueError, match="targets a node or a blob"):
        load(msgpack.packb(raw, use_bin_type=True))


@pytest.mark.parametrize(
    "field",
    ["cp", "windows", "budget", "tier", "lost", "idle", "last_patrol"],
)
def test_validate_lets_the_coalition_carry_looked_marks_and_nothing_else(field: str) -> None:
    w = load(save(scene()))
    validate(w, RULES)  # coalition looked marks: a restore passes (NX-512)
    d = w.director["COALITION"]
    assert d.looked
    changed = {
        "cp": 1,
        "windows": 1,
        "budget": 1,
        "tier": "ALPHA",
        "lost": {"cross-n": 1},
        "idle": {"1": 1},
        "last_patrol": 1,
    }[field]
    setattr(d, field, changed)
    with pytest.raises(ValueError, match=r"director\.COALITION: a side with no Director must keep"):
        validate(w, RULES)
