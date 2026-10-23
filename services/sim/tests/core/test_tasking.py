"""NX-374: the Tasking Board (GAMEPLAY §1b TB-1..TB-11; SIM-CORE SC-5, SC-11, SC-13; STATE-MACHINES
§4.1 Holding; Q-SIM-73).

Runs on the shipped strait-1 config with the campaign layer off, so no objective appears unless a
test sets one: haven (20 km, 120 km) - west-airbase - fob-n-w / fob-s-w, east-airbase (310 km,
120 km) is the Static's. Shipped tasking keys: a pass every 50 running ticks, a 1,200-tick lease,
unclaimed jobs expire after 9,000 ticks, 600 ticks to a game minute. `board_pass` runs one pass at
the next due tick without moving anything, so a test sets the scene by hand; the integration tests
at the end use real `step`s.
"""

import dataclasses
import os
import statistics
import subprocess
import sys
import time
from fractions import Fraction
from typing import Any

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel, TypeAdapter
from test_join import CAMPAIGN_ID, cid, join

from nexus.contracts.gen.common.enums import JobKind, OwnerKind, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_claimed import JobClaimed
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_released import JobReleased
from nexus.core.fog import side_view
from nexus.core.rng import RngStream, SimRng
from nexus.core.rules import Rules, TaskingRules
from nexus.core.step import SYSTEMS, step
from nexus.core.tasking import (
    _end,
    _load_at_source,
    claim,
    idle_reason,
    joinable_jobs,
    on_objective,
    post_job,
    priority,
    rank,
    run,
)
from nexus.core.tasking_gen import JobSpec, fits, generate
from nexus.core.world import (
    Blob,
    CaptureBar,
    Contact,
    Entity,
    FacilityMarker,
    Job,
    Objective,
    Vec2,
    World,
    load,
    lose_unit,
    save,
    state_hash,
    to_canonical,
)
from nexus.runtime.campaign_config import load_campaign_config, start_campaign

CONFIG = load_campaign_config()
_shipped = CONFIG.rules.tasking
if _shipped is None:
    raise AssertionError("the shipped config has tasking rules")
PATROL_TR: TaskingRules = _shipped  # the shipped patrol keys: the player patrol tests use it
TR: TaskingRules = dataclasses.replace(_shipped, patrol_max_nodes=0)  # patrols off: the older tests
RULES = dataclasses.replace(  # no opening garrison
    CONFIG.rules, campaign=None, garrison_quota={}, tasking=TR
)
EVERY = TR.reeval_every_ticks
LEASE = TR.claim_lease_ticks
HUMAN: OwnerKind = "COMMANDER"
AI: OwnerKind = "AI_GARRISON"
BASE_PRIORITY = {"DEFEND": 60, "RESUPPLY": 50, "ASSIST_OBJECTIVE": 45, "STRIKE": 40, "SCOUT": 30}


def new_world(seed: int = 1, rules: Rules = RULES) -> World:
    return start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(CONFIG, rules=rules))


def put(
    w: World, kind: UnitKind, node: str, owner: OwnerKind = HUMAN, cargo: int | None = None
) -> Entity:
    """A unit standing at `node`: an aircraft LANDED with full fuel, a truck with `cargo`."""
    side: Side = "ENEMY" if kind.startswith("ENEMY_") else "COALITION"
    commander = cid(w._next_entity_id) if owner == HUMAN else None
    e = w.spawn(kind, side, owner, Vec2(*RULES.roads.pos[node]), commander_id=commander)
    e.last_node = node
    if RULES.domain[kind] == "AIR":
        e.state, e.fuel = "LANDED", RULES.fuel_s[kind]
    if cargo is not None:
        e.cargo = cargo
    return e


def board_pass(w: World) -> list[Event]:
    """Advance the clock to the next due running tick and run one board pass there."""
    w.campaign.running_ticks = (w.campaign.running_ticks // EVERY + 1) * EVERY - 1
    out: list[Event] = []
    run(w, out)
    w.campaign.running_ticks += 1  # what the `objectives` slot adds
    return out


def post(
    w: World, side: Side, kind: JobKind, node: str, key: str,
    *, slots: int = 2, urgency: int = 1000, depends_on: int | None = None,
) -> Job:  # fmt: skip
    """A job posted by something but the generator (`op:` keys are never dropped as stale)."""
    spec = JobSpec(kind, f"op:{key}", slots, urgency, node=node, depends_on=depends_on)
    return post_job(w, side, spec, [])


def kinds(events: list[Event]) -> list[str]:
    return [e.kind for e in events]


def see(w: World, side: Side, *blobs: Blob, runs: int = 2) -> None:
    """The side's SIGINT blobs, each `runs` refreshes in its cell (a scout needs 2)."""
    w.blobs[side] = blobs
    w.blob_runs[side] = {b.id.split("-")[1]: runs for b in blobs}


def state(job: Job) -> str:
    return job.state


def of[E: BaseModel](events: list[Event], cls: type[E]) -> list[E]:
    return [e for e in events if isinstance(e, cls)]


def jobs(w: World, side: Side = "COALITION") -> list[Job]:
    return list(w.boards[side].values())


def hurt_facility(w: World, base: str, hp: int) -> None:
    (site,) = [e for e in w.entities() if e.base_id == base and e.kind == "AIR_DEFENSE_SITE"]
    site.hp = hp


# --- generation ---------------------------------------------------------------------------------


def test_the_board_runs_every_fifty_running_ticks_only() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 100  # below its floor of 250
    created = []
    for _ in range(120):
        if "JobCreated" in kinds(step(w, [])):
            created.append(w.campaign.tick)
    assert created == [50]  # tick 100 re-evaluated and found the same job (TB-4)


def test_resupply_job_slots_urgency_and_dedupe() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 100  # floor 250 of max 1000
    events = board_pass(w)
    (job,) = jobs(w)
    assert kinds(events) == ["JobCreated"]
    assert (job.kind, job.key, job.node, job.slots) == (
        "RESUPPLY",
        "resupply:fob-n-w",
        "fob-n-w",
        3,
    )
    assert job.urgency == 1600  # 1.0 + the stock deficit share 150 / 250
    assert (job.created, job.expires) == (50, 50 + TR.expire_ticks)
    # The same condition updates the job; it does not add a second one (TB-4).
    w.stock["fob-n-w"] = 200
    assert board_pass(w) == []
    assert [(j.id, j.urgency) for j in jobs(w)] == [(job.id, 1200)]
    # No longer starved, so nothing is generated and the unclaimed job expires.
    w.stock["fob-n-w"] = 600
    assert kinds(board_pass(w)) == ["JobExpired"] and jobs(w) == []


def test_damaged_facilities_raise_a_resupply_job_to_their_base() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 1000  # full: nothing missing, so one slot (Q-GP-47)
    hurt_facility(w, "fob-n-w", 75)  # half of 150 hp
    board_pass(w)
    (job,) = jobs(w)
    assert (job.node, job.urgency, job.slots) == ("fob-n-w", 1500, 1)


def test_urgency_never_passes_the_cap_and_slots_follow_missing_stock() -> None:
    w = new_world()
    w.stock["west-airbase"] = 0
    board_pass(w)
    (job,) = jobs(w)
    assert (job.urgency, job.slots) == (TR.urgency_max_milli, 3)  # empty: 2.0; 2,000 missing: max 3
    w.stock["west-airbase"] = 450  # floor 500: 1.1; 1,550 missing
    board_pass(w)
    assert jobs(w)[0].urgency == 1100


def test_priority_is_base_times_urgency_plus_exact_aging() -> None:
    job = Job(1, "DEFEND", "k", 2, 1500, 0, node="west-airbase")
    assert priority(TR, job, 0) == 90
    assert priority(TR, job, 600) == 91  # one game minute (TB-3)
    assert priority(TR, job, 1) == 90 + Fraction(1, 600)


def test_an_old_low_priority_job_overtakes_a_fresh_high_one() -> None:
    old = Job(1, "SCOUT", "a", 1, 1000, 0, blob="1-1", pos=Vec2(0, 0))
    for minutes, first in ((31, 1), (29, 2)):  # the scout has waited 30 + minutes > 60, or not
        fresh = Job(2, "DEFEND", "b", 2, 1000, 600 * minutes, node="west-airbase")
        assert next(j.id for j in rank(TR, [old, fresh], 600 * minutes, None)) == first


def test_defend_needs_a_tracked_ground_threat_or_a_bar_against_the_node() -> None:
    w = new_world()
    x, y = RULES.roads.pos["fob-n-w"]
    armor = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(x + 1500, y))
    board_pass(w)
    assert jobs(w) == []  # in range but untracked: the coalition cannot see it (TB-9)

    def track(distance: float) -> None:
        armor.pos = Vec2(x + distance, y)
        w.contacts["COALITION"][armor.id] = Contact("ENEMY_ARMOR", armor.pos, Vec2(0, 0))

    track(1500)
    board_pass(w)
    (job,) = jobs(w)
    assert (job.kind, job.node, job.slots) == ("DEFEND", "fob-n-w", 2)
    assert job.urgency == 1850  # 1 + (1 - 1500 / 10000): closer is more urgent
    track(9000)
    board_pass(w)
    assert job.urgency == 1100 and [j.id for j in jobs(w)] == [job.id]
    track(12_000)  # tracked, but beyond tasking.defend_radius_m
    assert kinds(board_pass(w)) == ["JobExpired"]
    w.capture["fob-n-w"] = CaptureBar("ENEMY", 50_000_000)  # a bar of the other side, half full
    board_pass(w)
    assert jobs(w)[0].urgency == 1500
    track(2000)  # the nearer of the bar (0.5) and the enemy (0.8) sets it
    board_pass(w)
    assert jobs(w)[0].urgency == 1800


def test_strike_targets_the_enemy_held_objective_then_discovered_sites() -> None:
    w = new_world()
    w.objective = Objective(1, "east-airbase", 90_000, False)
    put(w, "GARRISON_INFANTRY", "west-airbase", AI)  # something that can staff an assist job
    board_pass(w)
    strike, assist = jobs(w)
    assert (strike.kind, strike.node, strike.slots) == ("STRIKE", "east-airbase", 2)
    assert (strike.urgency, strike.objective, strike.expires) == (2000, 1, None)
    assert (assist.kind, assist.node, assist.slots) == ("ASSIST_OBJECTIVE", "east-airbase", 4)
    assert assist.objective == 1 and assist.expires is None
    # Own-node objective: only assist (a hold); neutral-node: only assist.
    w.objective = Objective(2, "west-airbase", 90_000, True)
    board_pass(w)
    assert [j.kind for j in jobs(w)] == ["ASSIST_OBJECTIVE"] and jobs(w)[0].node == "west-airbase"
    # Discovered sites at the enemy's fob-n-e: urgency from the highest threat there (SAM site: 90).
    w.objective = None
    pos = Vec2(*RULES.roads.pos["fob-n-e"])
    w.markers["COALITION"][98] = FacilityMarker(  # a radar there too, threat 50: the SAM's 90 wins
        "RADAR_SITE", None, pos, True, 1, None, "HEALTHY"
    )
    w.markers["COALITION"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", pos, True, 1, 35_000, "HEALTHY"
    )
    board_pass(w)
    (job,) = jobs(w)
    assert (job.kind, job.node, job.urgency, job.objective) == ("STRIKE", "fob-n-e", 1900, None)
    assert job.expires is not None
    w.defense_hp["fob-n-e"] = 0  # nothing left to strike
    assert kinds(board_pass(w)) == ["JobExpired"]


def test_objective_jobs_exist_for_the_coalition_only() -> None:
    w = new_world()
    w.objective = Objective(1, "east-airbase", 90_000, False)
    board_pass(w)
    assert jobs(w, "ENEMY") == []


def test_scout_jobs_follow_sigint_blobs_by_cell() -> None:
    w = new_world()
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"), Blob("3-48", Vec2(85e3, 15e3), "L"))
    board_pass(w)
    (large,) = jobs(w)  # one new scout job per interval: the larger blob first
    assert (large.key, large.blob, large.urgency, large.slots) == ("scout:48", "3-48", 2000, 1)
    w.campaign.running_ticks += TR.scout_post_interval_ticks
    board_pass(w)
    small = next(j for j in jobs(w) if j.key == "scout:7")
    assert (small.blob, small.urgency, small.pos) == ("3-7", 1000, Vec2(75e3, 5e3))
    # The next refresh moves the blob's id, not its cell: the job follows it.
    see(w, "COALITION", Blob("93-7", Vec2(75e3, 5e3), "M"))
    events = board_pass(w)
    assert kinds(events) == ["JobExpired"]  # cell 48 is gone
    assert [(j.id, j.blob, j.urgency) for j in jobs(w)] == [(small.id, "93-7", 1500)]


def _with(**changes: Any) -> Rules:
    return dataclasses.replace(RULES, tasking=dataclasses.replace(TR, **changes))


def test_scout_blob_runs_is_how_long_a_blob_must_stay_and_a_key() -> None:
    w = new_world(rules=_with(scout_blob_runs=3))
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"), runs=2)
    board_pass(w)
    assert jobs(w) == []  # two refreshes are not enough now
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"), runs=3)
    board_pass(w)
    assert [j.key for j in jobs(w)] == ["scout:7"]


def test_scout_urgency_is_by_blob_size_and_a_key() -> None:
    w = new_world(rules=_with(scout_urgency_milli={"S": 1100, "M": 1200, "L": 1300}))
    see(w, "COALITION", Blob("3-48", Vec2(85e3, 15e3), "L"))
    board_pass(w)
    assert [j.urgency for j in jobs(w)] == [1300]  # not the shipped 2000


def test_strike_urgency_per_threat_is_a_key() -> None:
    w = new_world(rules=_with(strike_urgency_per_threat_milli=5))
    pos = Vec2(*RULES.roads.pos["fob-n-e"])
    w.markers["COALITION"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", pos, True, 1, 35_000, "HEALTHY"
    )
    board_pass(w)
    (job,) = jobs(w)
    assert (job.kind, job.urgency) == ("STRIKE", 1000 + 5 * 90)  # SAM threat 90; shipped is 1900


def _strikes(w: World, tr: TaskingRules = TR) -> list[tuple[str, int]]:
    """The strike jobs the coalition board would hold now (generated, before any unit claims)."""
    specs = generate(
        w, dataclasses.replace(RULES, tasking=tr), tr, "COALITION", side_view(w, "COALITION")
    )
    return [(s.key, s.slots) for s in specs if s.kind == "STRIKE"]


def test_idle_armed_viewer_units_add_strike_slots_up_to_the_cap() -> None:
    """Q-SIM-92: one extra slot per idle armed viewer unit, at most `strike_max_scaled_slots`."""
    w = new_world()
    pos = Vec2(*RULES.roads.pos["fob-n-e"])
    w.markers["COALITION"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", pos, True, 1, 35_000, "HEALTHY"
    )
    put(w, "STRIKE_FIGHTER", "west-airbase", AI)  # not a viewer's: not counted
    held = put(w, "STRIKE_FIGHTER", "west-airbase")
    held.order = "HOLD"  # a HOLD keeps the board off it: not idle
    dry = put(w, "STRIKE_FIGHTER", "west-airbase")
    dry.ammo = [0, 0]  # nothing to strike with
    put(w, "RECON_UAV", "west-airbase")  # unarmed
    assert _strikes(w) == [("strike:fob-n-e", TR.slots["STRIKE"])]
    for want in (1, 2, 3, 3):
        put(w, "STRIKE_FIGHTER", "west-airbase")
        assert _strikes(w) == [("strike:fob-n-e", TR.slots["STRIKE"] + want)]


def test_idle_viewers_get_strike_jobs_on_the_nearest_known_defended_foe_nodes() -> None:
    w = new_world()
    w.director["ENEMY"].tier = "ALPHA"  # the gate (below) is open
    assert _strikes(w) == []  # nobody idle: nothing posted
    put(w, "STRIKE_FIGHTER", "west-airbase")
    # fob-n-e and fob-s-e are as near a coalition node: the tie goes by node id
    assert _strikes(w) == [("strike:fob-n-e", 3), ("strike:fob-s-e", 3)]
    three = dataclasses.replace(TR, strike_idle_targets_max=3)
    assert [k for k, _ in _strikes(w, three)] == [
        "strike:east-airbase",
        "strike:fob-n-e",
        "strike:fob-s-e",
    ]
    w.defense_hp["fob-n-e"] = 0  # nothing left there: the next nearest takes its place
    assert [k for k, _ in _strikes(w, three)] == [
        "strike:east-airbase",
        "strike:fob-s-e",
        "strike:static-hq",
    ]


def test_idle_strike_targets_wait_for_the_tier_so_a_lone_viewer_provokes_nothing() -> None:
    w = new_world()
    put(w, "STRIKE_FIGHTER", "west-airbase")
    assert w.director["ENEMY"].tier == "PATTERN_OF_LIFE"
    assert _strikes(w) == []
    w.director["ENEMY"].tier = TR.strike_idle_targets_min_tier  # ALPHA
    assert [k for k, _ in _strikes(w)] == ["strike:fob-n-e", "strike:fob-s-e"]


def test_no_idle_target_is_posted_while_a_marked_target_is_open() -> None:
    w = new_world()
    put(w, "STRIKE_FIGHTER", "west-airbase")
    w.markers["COALITION"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE",
        "SAM",
        Vec2(*RULES.roads.pos["east-airbase"]),
        True,
        1,
        35_000,
        "HEALTHY",
    )
    assert [k for k, _ in _strikes(w)] == ["strike:east-airbase"]


def test_zero_strike_scaling_keys_reproduce_the_old_board() -> None:
    off = dataclasses.replace(TR, strike_max_scaled_slots=0, strike_idle_targets_max=0)
    w = new_world()
    w.director["ENEMY"].tier = "ALPHA"
    for _ in range(4):
        put(w, "STRIKE_FIGHTER", "west-airbase")
    assert _strikes(w, off) == []
    w.markers["COALITION"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(*RULES.roads.pos["fob-n-e"]), True, 1, 35_000, "HEALTHY"
    )
    board_pass(w)
    assert _strikes(w) == [("strike:fob-n-e", TR.slots["STRIKE"])]


def test_idle_reason_names_why_an_idle_jet_holds_no_job() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    assert idle_reason(w, jet) == "no_job"
    job = post(w, "COALITION", "STRIKE", "east-airbase", "s", slots=1)
    assert idle_reason(w, jet) == "other"  # it takes the job at the next pass
    jet.ammo = [0, 0]
    assert idle_reason(w, jet) == "ammo"
    jet.ammo, jet.fuel = [4, 400], 1.0
    assert idle_reason(w, jet) == "refuel"  # a full tank would reach: it is being refuelled
    jet.fuel = RULES.fuel_s["STRIKE_FIGHTER"]
    w.markers["COALITION"][50] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(200_000, 120_000), True, 1, 30_000, "HEALTHY"
    )
    assert idle_reason(w, jet) == "ring"
    del w.markers["COALITION"][50]
    for _ in range(2 * job.slots):  # the overfill limit
        claim(w, put(w, "STRIKE_FIGHTER", "west-airbase"), job, [])
    assert idle_reason(w, jet) == "full"


def test_idle_strike_jobs_are_deterministic() -> None:
    def run() -> str:
        w = new_world()
        w.director["ENEMY"].tier = "ALPHA"
        for _ in range(3):
            put(w, "STRIKE_FIGHTER", "west-airbase")
        for _ in range(4):
            board_pass(w)
        return state_hash(w)

    assert run() == run()


# --- assignment ---------------------------------------------------------------------------------


def test_an_idle_unit_takes_the_best_matching_job_and_gets_a_path() -> None:
    w = new_world()
    low = post(w, "COALITION", "DEFEND", "fob-s-w", "low")
    high = post(w, "COALITION", "DEFEND", "fob-n-w", "high", urgency=1500)
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    events = board_pass(w)
    assert kinds(events) == ["JobClaimed"] and of(events, JobClaimed)[0].job_id == high.id
    assert (unit.job_id, unit.path) == (high.id, ["west-airbase", "fob-n-w"])
    assert low.claims == {} and state(high) == "CLAIMED"


def test_slots_fill_in_unit_id_order_before_a_job_is_skipped_unless_every_job_is_full() -> None:
    w = new_world()
    first = post(w, "COALITION", "DEFEND", "fob-n-w", "first", urgency=1500, slots=3)
    second = post(w, "COALITION", "DEFEND", "fob-s-w", "second", slots=1)
    units = [put(w, "GARRISON_INFANTRY", "west-airbase") for _ in range(6)]
    board_pass(w)
    # The first three fill the best job, the fourth takes the other, the last two overfill the best.
    assert [u.job_id for u in units] == [first.id] * 3 + [second.id] + [first.id] * 2
    assert len(first.claims) == 5 and len(second.claims) == 1


def test_infeasible_jobs_are_skipped_and_a_low_aircraft_refuels_first() -> None:
    w = new_world()
    post(w, "COALITION", "STRIKE", "east-airbase", "far", urgency=1500)
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=0)
    resupply = post(w, "COALITION", "RESUPPLY", "fob-n-w", "r")
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    jet.fuel = 600.0  # 600 s: out and back to east-airbase needs about 1,760 s plus the reserve
    board_pass(w)
    assert truck.job_id == resupply.id and truck.pickup is None  # it loads where it stands (below)
    assert (
        jet.job_id is None and jet.path == []
    )  # LANDED at a base with stock: it stays and refuels
    jet.fuel, jet.ammo = RULES.fuel_s["STRIKE_FIGHTER"], [0, 0]
    board_pass(w)
    assert jet.job_id is None  # out of rounds: a strike needs one (refuel step: stay and rearm)
    jet.ammo = [3, 400]
    board_pass(w)
    assert jet.job_id is not None


def test_a_low_orbiting_aircraft_flies_to_the_nearest_base_with_stock() -> None:
    w = new_world()
    post(w, "COALITION", "STRIKE", "east-airbase", "far")
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    jet.state, jet.fuel = "ON_STATION", 700.0
    jet.pos, jet.orbit = Vec2(150_000, 120_000), Vec2(150_000, 121_000)
    board_pass(w)
    assert jet.job_id is None and jet.path == ["west-airbase"] and jet.orbit is None
    w.stock["west-airbase"] = 0  # a base with no stock cannot refuel it: haven (infinite) can
    jet.path, jet.orbit = [], Vec2(150_000, 121_000)
    board_pass(w)
    assert jet.path == ["haven"]


def test_a_ground_unit_without_a_road_route_takes_no_job() -> None:
    w = new_world()
    post(
        w, "COALITION", "ASSIST_OBJECTIVE", "bridge-n", "island"
    )  # a BRIDGE has no road of its own
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    assert kinds(board_pass(w)) == [] and unit.job_id is None


def test_the_job_must_fit_the_unit() -> None:
    assert fits(RULES, "LOGI_TRUCK", "RESUPPLY") and not fits(RULES, "LOGI_TRUCK", "DEFEND")
    for carrier in ("LOGI_TRUCK", "ENEMY_CONVOY"):  # a carrier only hauls (capture runs are orders)
        assert not any(fits(RULES, carrier, k) for k in ("ASSIST_OBJECTIVE", "STRIKE", "SCOUT"))
    assert fits(RULES, "RECON_UAV", "SCOUT") and not fits(RULES, "RECON_UAV", "STRIKE")
    assert fits(RULES, "STRIKE_FIGHTER", "STRIKE") and fits(RULES, "STRIKE_FIGHTER", "DEFEND")
    assert fits(RULES, "GARRISON_INFANTRY", "ASSIST_OBJECTIVE")
    assert not fits(RULES, "STRIKE_FIGHTER", "ASSIST_OBJECTIVE")
    assert fits(RULES, "ENEMY_CONVOY", "RESUPPLY") and fits(RULES, "ENEMY_ARMOR", "DEFEND")
    assert fits(RULES, "ENEMY_ARMOR", "ASSIST_OBJECTIVE")


def test_a_unit_with_a_job_or_an_order_is_left_alone() -> None:
    w = new_world()
    post(w, "COALITION", "DEFEND", "fob-n-w", "a", slots=5)
    held = put(w, "GARRISON_INFANTRY", "west-airbase")
    held.order = "HOLD"
    going = put(w, "GARRISON_INFANTRY", "west-airbase")
    going.order = "GOTO"
    going.path = ["fob-s-w"]
    moving = put(w, "GARRISON_INFANTRY", "west-airbase")
    moving.path = ["fob-s-w"]
    board_pass(w)
    assert [u.job_id for u in (held, going, moving)] == [None, None, None]
    going.path = []
    board_pass(w)  # arrived: the order ends (TB-7), so the board may use the unit now
    assert going.order is None and going.job_id is not None
    assert held.order == "HOLD" and held.job_id is None


def test_a_human_order_preempts_a_claim() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "a")
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert unit.job_id == job.id
    unit.order = "GOTO"  # a later `!target`, `!rebase` or `!rtb` (TB-7)
    unit.path = ["fob-s-w"]
    events = board_pass(w)
    assert kinds(events) == ["JobReleased"] and unit.job_id is None and job.claims == {}


def test_a_capture_run_keeps_its_order_until_the_bar_is_gone() -> None:
    w = new_world()
    truck = put(w, "LOGI_TRUCK", "cross-n", cargo=0)
    truck.order = "GOTO"
    w.capture["cross-n"] = CaptureBar("COALITION", 5_000_000)
    board_pass(w)
    assert truck.order == "GOTO"
    del w.capture["cross-n"]  # flipped or abandoned
    board_pass(w)
    assert truck.order is None


# --- lifecycle, leases and outcomes -------------------------------------------------------------


def test_tb1_lifecycle_open_claimed_active_done() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    truck = put(w, "LOGI_TRUCK", "fob-n-w", cargo=100)
    events = board_pass(w)
    assert kinds(events) == ["JobCreated", "JobClaimed"]
    (job,) = jobs(w)
    assert state(job) == "CLAIMED" and truck.job_id == job.id
    board_pass(w)  # it has a path (it is moving): progress
    assert state(job) == "ACTIVE" and job.claims[truck.id].at == w.campaign.running_ticks
    truck.path, truck.cargo, w.stock["fob-n-w"] = [], 0, 300  # delivered
    done = [e for e in board_pass(w) if e.kind == "JobDone"]
    assert [p.entity_id for p in done[0].participants] == [truck.id]
    assert done[0].participants[0].auto is False and done[0].participants[0].commander_id
    assert truck.job_id is None and job.id not in w.boards["COALITION"]


def test_a_claim_without_progress_is_released_after_the_lease() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "a")
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    claimed_at = job.claims[unit.id].at
    unit.path = []  # its order was lost: neither moving nor there
    while w.campaign.running_ticks + EVERY - claimed_at < LEASE:
        assert "JobReleased" not in kinds(board_pass(w))
    events = board_pass(w)
    assert kinds(events)[:2] == ["JobReleased", "JobClaimed"]  # released, then taken afresh
    assert job.claims[unit.id].at == w.campaign.running_ticks and not job.claims[unit.id].active


def test_a_lost_disabled_or_homebound_claimant_is_released() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "a", slots=3)
    a, b, c = (put(w, "GARRISON_INFANTRY", "west-airbase") for _ in range(3))
    board_pass(w)
    assert len(job.claims) == 3
    w.remove(a.id)
    b.damage_state = "DISABLED"
    c.state = "RTB"
    events = board_pass(w)
    assert kinds(events).count("JobReleased") == 3 and job.claims == {}


def test_defend_is_done_when_the_threat_is_gone_and_a_claimant_is_there() -> None:
    w = new_world()
    x, y = RULES.roads.pos["fob-n-w"]
    armor = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(x + 500, y))
    w.contacts["COALITION"][armor.id] = Contact("ENEMY_ARMOR", armor.pos, Vec2(0, 0))
    unit = put(w, "GARRISON_INFANTRY", "fob-n-w")
    board_pass(w)
    (job,) = jobs(w)
    assert unit.job_id == job.id
    unit.path = []  # it is there already
    assert board_pass(w) == []  # the threat is still there: it holds
    w.remove(armor.id)
    del w.contacts["COALITION"][armor.id]
    events = board_pass(w)
    assert "JobDone" in kinds(events) and jobs(w) == []


def test_defend_fails_when_the_node_is_lost() -> None:
    w = new_world()
    x, y = RULES.roads.pos["fob-n-w"]
    armor = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(x + 500, y))
    w.contacts["COALITION"][armor.id] = Contact("ENEMY_ARMOR", armor.pos, Vec2(0, 0))
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert unit.job_id is not None
    w.owner["fob-n-w"] = "ENEMY"
    events = board_pass(w)
    assert kinds(events)[0] == "JobFailed" and unit.job_id is None


def test_strike_is_done_when_the_defenses_fall_and_expires_without_a_striker() -> None:
    w = new_world()
    w.objective = Objective(1, "east-airbase", 90_000, False)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    strike = next(j for j in jobs(w) if j.kind == "STRIKE")
    assert jet.job_id == strike.id and jet.path == ["east-airbase"]
    board_pass(w)  # flying: ACTIVE
    w.defense_hp["east-airbase"] = 0
    events = board_pass(w)
    done = next(e for e in events if e.kind == "JobDone")
    assert done.job_id == strike.id and [p.entity_id for p in done.participants] == [jet.id]
    # The same, but nobody had made progress: nobody to credit, so EXPIRED.
    w2 = new_world()
    post(w2, "COALITION", "STRIKE", "east-airbase", "s")
    w2.defense_hp["east-airbase"] = 0
    assert kinds(board_pass(w2)) == ["JobExpired"]


def test_assist_objective_ends_with_its_objective() -> None:
    w = new_world()
    w.objective = Objective(1, "fob-s-w", 90_000, False)
    w.owner["fob-s-w"] = "ENEMY"
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    board_pass(w)  # moving: ACTIVE
    (assist,) = [j for j in jobs(w) if j.kind == "ASSIST_OBJECTIVE"]
    assert unit.job_id == assist.id
    out: list[Event] = []
    on_objective(w, 1, True, out)
    assert kinds(out) == ["JobExpired", "JobDone"]  # the strike had no striker to credit
    (done,) = of(out, JobDone)
    assert done.job_id == assist.id and done.participants[0].entity_id == unit.id
    w.objective = Objective(2, "fob-s-w", 90_000, False)
    board_pass(w)
    out = []
    on_objective(w, 2, False, out)  # expired objective: EXPIRED, claimants freed
    assert kinds(out) == ["JobExpired", "JobExpired"] and unit.job_id is None


def test_scout_is_done_when_the_aircraft_reaches_the_blob() -> None:
    w = new_world()
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    uav = put(w, "RECON_UAV", "west-airbase")
    board_pass(w)
    (job,) = jobs(w)
    assert (uav.job_id, uav.path) == (job.id, [Vec2(75e3, 5e3)])
    board_pass(w)
    uav.path, uav.state = [], "ON_STATION"
    events = board_pass(w)
    assert of(events, JobDone)[0].job_id == job.id
    assert job.id not in w.boards["COALITION"]  # (the blob is still in view: a new job follows)


def test_unclaimed_jobs_expire_but_claimed_ones_do_not() -> None:
    w = new_world()
    post(w, "COALITION", "DEFEND", "fob-n-w", "a")
    post(w, "COALITION", "DEFEND", "fob-s-w", "b")
    put(w, "GARRISON_INFANTRY", "west-airbase")  # takes one of the two equal-priority jobs
    board_pass(w)
    (claimed,) = [j.id for j in jobs(w) if j.claims]
    w.campaign.running_ticks = TR.expire_ticks + 5
    events = board_pass(w)
    assert kinds(events) == ["JobExpired"] and [j.id for j in jobs(w)] == [claimed]


def test_tb8_a_job_waits_for_its_dependency() -> None:
    w = new_world()
    first = post(w, "COALITION", "DEFEND", "fob-n-w", "a")
    second = post(w, "COALITION", "DEFEND", "fob-s-w", "b", depends_on=first.id)
    third = post(w, "COALITION", "DEFEND", "west-airbase", "c", depends_on=second.id)
    one, two = (
        put(w, "GARRISON_INFANTRY", "west-airbase"),
        put(w, "GARRISON_INFANTRY", "west-airbase"),
    )
    board_pass(w)
    assert {one.job_id, two.job_id} == {first.id} and second.claims == {} and third.claims == {}
    out: list[Event] = []
    _end(w, "COALITION", first, "DONE", out)
    assert second.depends_on is None and third.depends_on == second.id
    _end(
        w, "COALITION", second, "EXPIRED", out
    )  # a dependency that ends badly fails its dependents
    assert kinds(out) == ["JobDone", "JobExpired", "JobFailed"] and jobs(w) == []


def test_jobs_are_events_that_validate_against_the_contract() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    put(w, "LOGI_TRUCK", "fob-n-w", cargo=100)
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    events = board_pass(w)
    for e in board_pass(w) + events:
        assert TypeAdapter(Event).validate_python(e.model_dump()) == e
    assert {"JobCreated", "JobClaimed"} <= set(kinds(events))


# --- the AI garrison ----------------------------------------------------------------------------


def test_the_garrison_defends_but_never_starts_a_strike_or_an_assault() -> None:
    w = new_world()
    strike = post(w, "COALITION", "STRIKE", "east-airbase", "s")
    assist = post(w, "COALITION", "ASSIST_OBJECTIVE", "east-airbase", "a")
    defend = post(w, "COALITION", "DEFEND", "fob-n-w", "d")
    scout = post(w, "COALITION", "SCOUT", "fob-s-w", "sc")  # (a node scout: fits only recon)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    grunt = put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    board_pass(w)
    assert jet.job_id == defend.id and grunt.job_id == defend.id  # DEFEND outranks the rest anyway
    assert strike.claims == {} and assist.claims == {} and scout.claims == {}
    defend.claims.clear()
    jet.job_id = grunt.job_id = None
    jet.path = grunt.path = []  # (they stand where they were)
    for j in (defend, scout):
        del w.boards["COALITION"][j.id]
    board_pass(w)
    assert jet.job_id is None and grunt.job_id is None  # only strike and assist are left
    # Once a human has started the strike, the garrison may join it.
    pilot = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    assert pilot.job_id == strike.id
    jet2 = put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    board_pass(w)
    assert jet2.job_id == strike.id


def test_a_human_takes_the_slot_of_an_ai_garrison_unit() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d")
    ai1 = put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    ai2 = put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    board_pass(w)
    assert set(job.claims) == {ai1.id, ai2.id}
    human = put(w, "GARRISON_INFANTRY", "west-airbase")
    events = board_pass(w)
    assert kinds(events) == ["JobReleased", "JobClaimed"]
    assert of(events, JobReleased)[0].entity_id == ai2.id
    assert set(job.claims) == {ai1.id, human.id} and ai2.job_id is None
    # A second human displaces the other AI unit; a third finds only humans and overfills.
    h2, h3 = (
        put(w, "GARRISON_INFANTRY", "west-airbase"),
        put(w, "GARRISON_INFANTRY", "west-airbase"),
    )
    board_pass(w)
    assert set(job.claims) == {human.id, h2.id, h3.id}


# --- parameterless JOIN -------------------------------------------------------------------------


def test_join_with_no_target_takes_the_best_job_at_once() -> None:
    w = new_world()
    post(w, "COALITION", "DEFEND", "fob-s-w", "low")
    best = post(w, "COALITION", "DEFEND", "fob-n-w", "best", urgency=1500)
    events = step(w, [join(1, "STRIKE")])
    assert kinds(events) == ["SupplyConsumed", "UnitSpawned", "JobClaimed"]  # the loadout is paid
    assert of(events, JobClaimed)[0].job_id == best.id
    (jet,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert (jet.job_id, jet.order) == (best.id, None) and jet.path == ["fob-n-w"]
    assert jet.last_node == "west-airbase"  # forward-deployed (GP-7)
    assert set(best.claims) == {jet.id}


def test_join_logi_with_no_target_takes_the_best_resupply_job_with_cargo() -> None:
    w = new_world()
    post(w, "COALITION", "ASSIST_OBJECTIVE", "fob-s-w", "a", urgency=2000)
    resupply = post(w, "COALITION", "RESUPPLY", "fob-n-w", "r")
    events = step(w, [join(1, "LOGI")])
    (truck,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert kinds(events)[:2] == ["UnitSpawned", "SupplyConsumed"] or "JobClaimed" in kinds(events)
    assert truck.job_id == resupply.id  # a truck takes a resupply job only (Q-GP-24)
    assert truck.cargo == RULES.supply.truck_cargo and truck.path[-1] == "fob-n-w"
    assert (
        truck.last_node == "west-airbase"
    )  # the existing source rule: the nearest base with surplus


def test_join_recon_with_no_target_flies_to_a_blob() -> None:
    w = new_world()
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    board_pass(w)
    step(w, [join(1, "RECON")])
    (uav,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert uav.job_id is not None and uav.path == [Vec2(75e3, 5e3)] and uav.last_node == "haven"


def test_hold_a_node_target_or_no_job_leave_the_board_out() -> None:
    w = new_world()
    post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=9)
    step(w, [join(1, "STRIKE", hold=True), join(2, "STRIKE", "fob-s-w")])
    by = {e.commander_id: e for e in w.entities() if e.commander_id}
    assert (by[cid(1)].order, by[cid(1)].job_id, by[cid(1)].path) == ("HOLD", None, [])
    assert (by[cid(2)].order, by[cid(2)].job_id) == ("GOTO", None)
    empty = new_world()
    step(empty, [join(3, "STRIKE")])  # no job: it waits at the sanctuary, free for the board
    (jet,) = [e for e in empty.entities() if e.commander_id == cid(3)]
    assert (jet.order, jet.job_id, jet.path, jet.last_node) == (None, None, [], "haven")


def test_a_queued_join_takes_its_job_when_served() -> None:
    capped = dataclasses.replace(RULES, max_viewer_units=1)
    w = new_world(rules=capped)
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=2)
    step(w, [join(1, "STRIKE", "fob-s-w"), join(2, "STRIKE")])  # 1 fills the cap, 2 queues
    assert len(w.reserve_queue) == 1 and job.claims == {}
    (first,) = [e for e in w.entities() if e.commander_id == cid(1)]
    w.remove(first.id)
    events = step(w, [])
    assert kinds(events) == ["SupplyConsumed", "UnitSpawned", "JobClaimed"] and len(job.claims) == 1


# --- freeze, snapshot, determinism --------------------------------------------------------------


def scenario(seed: int = 5) -> World:
    """A starving base, a blob, an objective and a few units, run past several passes."""
    w = new_world(seed)
    w.stock["fob-n-w"] = 0
    w.objective = Objective(1, "east-airbase", 90_000, False)
    w.campaign.objectives_issued = 1
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"), Blob("3-9", Vec2(85e3, 5e3), "S"))
    put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    put(w, "STRIKE_FIGHTER", "west-airbase")
    put(w, "RECON_UAV", "west-airbase")
    put(w, "RECON_UAV", "west-airbase")
    for _ in range(620):
        step(w, [])
    return w


def test_a_pause_freezes_the_boards() -> None:
    w = scenario()
    while (w.campaign.running_ticks + 1) % EVERY:  # pause on a tick where a pass is due
        step(w, [])
    boards = to_canonical(w, quantize=True)["boards"]
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    w.stock["fob-s-w"] = 0  # a pass would post a resupply job for it
    running = w.campaign.running_ticks
    events = []
    for _ in range(3 * LEASE):  # three leases: nothing is posted, released or expires
        events += step(w, [])
    assert [e for e in events if e.kind.startswith("Job")] == []
    assert w.campaign.running_ticks == running
    assert to_canonical(w, quantize=True)["boards"] == boards
    w.campaign.clock_paused, w.campaign.pause_reason = False, None
    assert "JobCreated" in kinds([e for _ in range(EVERY) for e in step(w, [])])


def test_the_boards_survive_a_snapshot_and_the_run_continues_identically() -> None:
    w = scenario()
    assert w.boards["COALITION"] and any(e.job_id for e in w.entities())
    again = load(save(w))
    again.rules = RULES
    assert state_hash(again) == state_hash(w)
    for _ in range(300):
        step(w, [])
        step(again, [])
    assert state_hash(again) == state_hash(w)


def test_format_16_snapshots_are_refused() -> None:
    raw = msgpack.unpackb(save(scenario()), raw=False)
    raw["v"] = 16
    with pytest.raises(ValueError, match="unsupported snapshot format version 16"):
        load(msgpack.packb(raw, use_bin_type=True))


def _first(raw: dict, *, claimed: bool = False) -> dict:  # type: ignore[type-arg]
    board = raw["boards"]["COALITION"]
    return next(j for j in board if j["claims"] or not claimed)


def _kind(raw: dict, kind: str) -> dict:  # type: ignore[type-arg]
    return next(j for j in raw["boards"]["COALITION"] if j["kind"] == kind)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda r: (
                r.update(next_job_id=200),
                r["boards"]["COALITION"].append(dict(_first(r), id=199, claims=[])),
            ),
            "duplicate dedupe key",
        ),
        (lambda r: _first(r).update(kind="REPAIR_BRIDGE"), "job kind"),
        (lambda r: _first(r).update(node=None), "targets a node or a blob"),
        (lambda r: _first(r).update(depends_on=9999), "dependency off the board"),
        (lambda r: _first(r).update(depends_on=_first(r)["id"]), "dependency off the board"),
        (lambda r: _first(r).update(slots=0), "job slots"),
        (lambda r: _first(r).update(created=10**9), "after the snapshot"),
        (lambda r: r.update(next_job_id=1), "stay below the counter"),
        (lambda r: _first(r, claimed=True)["claims"].append([9999, 1, False]), "below the counter"),
        (
            lambda r: next(e for e in r["entities"] if e["job_id"]).update(job_id=None),
            "job_id does not",
        ),
        (lambda r: r["entities"][0].update(order="TELEPORT"), "order"),
        (lambda r: r["boards"].update(extra=[]), "boards"),
        (
            lambda r: _kind(r, "RESUPPLY").update(node="nowhere", key="resupply:nowhere"),
            "node of the theater",
        ),
        (
            lambda r: _kind(r, "SCOUT").update(blob=None, pos=None, node="fob-n-w"),
            "scout job targets a blob",
        ),
        (
            lambda r: _kind(r, "RESUPPLY").update(node=None, blob="3-7", pos=[1.0, 2.0]),
            "scout job targets a blob",
        ),
        (lambda r: _kind(r, "SCOUT").update(key="scout:99"), "does not name"),
        (lambda r: _kind(r, "RESUPPLY").update(key="defend:fob-n-w"), "does not name"),
    ],
)
def test_a_corrupt_board_is_refused(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    raw = msgpack.unpackb(save(scenario()), raw=False)
    mutate(raw)
    with pytest.raises(ValueError, match=message):
        load(msgpack.packb(raw, use_bin_type=True))


def test_same_seed_same_assignments_and_events() -> None:
    def run_once(seed: int) -> tuple[str, list[tuple[str, int | None]]]:
        w = scenario(seed)
        return state_hash(w), sorted((str(e.id), e.job_id) for e in w.entities())

    assert run_once(5) == run_once(5)


def test_ties_are_broken_by_the_tasking_stream_and_only_that_stream() -> None:
    a = Job(1, "DEFEND", "a", 2, 1000, 0, node="fob-n-w")
    b = Job(2, "DEFEND", "b", 2, 1000, 0, node="fob-s-w")
    firsts = {
        rank(TR, [a, b], 0, SimRng(seed).stream(RngStream.TASKING))[0].id for seed in range(40)
    }
    assert firsts == {1, 2}  # the draw decides
    same = [rank(TR, [a, b], 0, SimRng(7).stream(RngStream.TASKING))[0].id for _ in range(2)]
    assert same[0] == same[1]
    w = new_world()
    post(w, "COALITION", "DEFEND", "fob-n-w", "x")
    post(w, "COALITION", "DEFEND", "fob-s-w", "y")
    put(w, "GARRISON_INFANTRY", "west-airbase")
    streams = w.rng.to_state()
    board_pass(w)
    after = w.rng.to_state()
    assert after["tasking"] != streams["tasking"]
    assert {k: v for k, v in after.items() if k != "tasking"} == {
        k: v for k, v in streams.items() if k != "tasking"
    }


@given(st.permutations(range(8)))
def test_assignments_do_not_depend_on_entity_storage_order(order: list[int]) -> None:
    def assigned(shuffle: list[int] | None) -> dict[int, int | None]:
        w = new_world(3)
        for node in ("fob-n-w", "fob-s-w", "west-airbase"):
            post(w, "COALITION", "DEFEND", node, node, slots=2)
        for _ in range(8):
            put(w, "GARRISON_INFANTRY", "west-airbase")
        if shuffle is not None:
            ids = list(w._entities)
            w._entities = {
                ids[i]: w._entities[ids[i]]
                for i in [*range(len(ids) - 8), *(len(ids) - 8 + s for s in shuffle)]
            }
        board_pass(w)
        return {e.id: e.job_id for e in w.entities()}

    assert assigned(order) == assigned(None)


def test_tb9_the_board_cannot_see_what_its_side_cannot() -> None:
    w = new_world()
    see(w, "ENEMY", Blob("3-1", Vec2(300e3, 5e3), "L"))
    x, y = RULES.roads.pos["fob-n-w"]
    spy = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(x + 100, y))  # untracked
    before = generate(w, RULES, TR, "COALITION", side_view(w, "COALITION"))
    spy.pos = Vec2(x + 90_000, y + 90_000)  # hidden state moves; the coalition cannot tell
    see(w, "ENEMY")
    assert generate(w, RULES, TR, "COALITION", side_view(w, "COALITION")) == before == []
    # The enemy sees its own blob, not the coalition's.
    w.spawn(
        "ENEMY_RECON_UAV", "ENEMY", "ENEMY_DIRECTOR", Vec2(380e3, 120e3)
    )  # it can staff a scout
    see(w, "ENEMY", Blob("3-1", Vec2(300e3, 5e3), "L"))
    see(w, "COALITION", Blob("3-2", Vec2(80e3, 5e3), "S"))
    mine = generate(w, RULES, TR, "ENEMY", side_view(w, "ENEMY"))
    assert [s.blob for s in mine] == ["3-1"]


@given(
    st.lists(
        st.tuples(st.floats(0, 400_000), st.floats(0, 240_000), st.booleans(), st.booleans()),
        min_size=1,
        max_size=12,
    )
)
def test_tb9_specs_reference_only_the_views_blobs_nodes_and_sites(
    things: list[tuple[float, float, bool, bool]],
) -> None:
    w = new_world()
    ground: list[UnitKind] = ["ENEMY_ARMOR", "GARRISON_INFANTRY"]
    for x, y, enemy, tracked in things:
        e = w.spawn(
            ground[0] if enemy else ground[1],
            "ENEMY" if enemy else "COALITION",
            HUMAN if not enemy else "ENEMY_DIRECTOR",
            Vec2(x, y),
        )
        if tracked:
            seen: Side = "COALITION" if enemy else "ENEMY"
            w.contacts[seen][e.id] = Contact(e.kind, e.pos, e.vel)
    for _ in range(2):
        step(w, [])
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    for side in ("COALITION", "ENEMY"):
        view = side_view(w, side)
        for spec in generate(w, RULES, TR, side, view):
            assert spec.node is None or spec.node in view.nodes
            assert spec.blob is None or spec.blob in {b.id for b in view.blobs}
            if spec.kind == "STRIKE":
                assert view.owners[spec.node or ""] != side
            if spec.kind == "ASSIST_OBJECTIVE":
                assert side == "COALITION"


# --- cost ---------------------------------------------------------------------------------------


def test_the_board_pass_at_1000_entities_is_cheap() -> None:
    """500 idle viewer units, jobs of every kind and a full set of contacts (SC-10). Printed
    only: the p99 `step` budget (25 ms) is measured on the reference host."""
    w = new_world()
    w.objective = Objective(1, "east-airbase", 10**9, False)
    for node in ("fob-n-w", "fob-s-w", "west-airbase"):
        w.stock[node] = 0
    kinds_cycle: list[UnitKind] = ["GARRISON_INFANTRY", "STRIKE_FIGHTER", "RECON_UAV", "LOGI_TRUCK"]
    for i in range(500):
        put(w, kinds_cycle[i % 4], "west-airbase", cargo=100 if i % 4 == 3 else None)
    for i in range(500):
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(300_000 + i, 100_000 + i))
    see(w, "COALITION", *(Blob(f"3-{k}", Vec2(50e3 + k * 1e3, 5e3), "S") for k in range(8)))
    ms = []
    for _ in range(6):
        start = time.perf_counter()
        board_pass(w)
        ms.append((time.perf_counter() - start) * 1000)
        for e in w.entities():  # free everyone so each pass assigns 500 units again
            e.job_id, e.path = None, []
        for side in w.boards:
            for job in w.boards[side].values():
                job.claims.clear()
    assert w.boards["COALITION"]
    print(
        f"board pass at 1,000 entities: median {statistics.median(ms):.2f} ms, max {max(ms):.2f} ms"
    )


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_tasking import scenario\n"
    "from nexus.core.world import state_hash; print(state_hash(scenario()))"
)


def test_board_state_hash_is_hash_seed_independent() -> None:
    def run_with(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603  # fixed argv

    assert run_with("1") == run_with("2") == state_hash(scenario())


def test_the_board_runs_in_the_director_slot() -> None:
    names = [n for n, _ in SYSTEMS]
    assert names.index("director") < names.index("movement")


# --- Q-SIM-74 and Q-SIM-75 follow-ups ------------------------------------------------------------


def test_an_empty_truck_drives_to_a_source_loads_like_a_spawn_and_delivers() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0  # starved: 1 job, destination
    w.stock["west-airbase"] = 700  # surplus over its floor of 500: 200
    total = sum(w.stock.values())
    truck = put(w, "LOGI_TRUCK", "fob-s-w", cargo=0)
    board_pass(w)
    assert truck.pickup == "west-airbase" and truck.path[-1] == "west-airbase" and truck.cargo == 0
    assert sum(w.stock.values()) == total  # nothing moved yet
    truck.path, truck.last_node, truck.pos = (
        [],
        "west-airbase",
        Vec2(*RULES.roads.pos["west-airbase"]),
    )
    board_pass(w)  # it is at the source: loads min(truck_cargo, surplus) and heads for the job
    assert truck.cargo == 100 and truck.pickup is None and truck.path[-1] == "fob-n-w"
    assert w.stock["west-airbase"] == 600 and sum(w.stock.values()) + truck.cargo == total
    assert truck.job_id is not None


def test_a_truck_at_its_source_loads_at_once_and_the_sanctuary_is_last_resort() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=0)
    board_pass(w)  # west-airbase has surplus 500 (stock 1000, floor 500): loads a full 100
    assert (truck.cargo, w.stock["west-airbase"], truck.pickup) == (100, 900, None)
    assert truck.path[-1] == "fob-n-w"
    w2 = new_world()
    w2.stock["fob-n-w"] = 0
    for n in ("west-airbase", "fob-s-w"):
        w2.stock[n] = RULES.supply.starve_floor[n]  # no surplus anywhere
    t2 = put(w2, "LOGI_TRUCK", "west-airbase", cargo=0)
    board_pass(w2)
    assert t2.pickup == "haven" and t2.path[-1] == "haven"  # the sanctuary, infinite stock


def test_a_source_that_ran_dry_releases_the_truck() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    truck = put(w, "LOGI_TRUCK", "fob-s-w", cargo=0)
    board_pass(w)
    source = truck.pickup
    assert source is not None
    w.stock[source] = RULES.supply.starve_floor[source]  # drained while it drove
    truck.path, truck.last_node, truck.pos = [], source, Vec2(*RULES.roads.pos[source])
    job = jobs(w)[0]
    spare = dataclasses.replace(truck, id=999)  # the dry arrival itself, apart from the re-plan
    spare.pickup, spare.path = source, []
    assert not _load_at_source(w, RULES, {}, spare, job)
    assert spare.path == [] and spare.cargo == 0 and spare.pickup is None  # no road to deliver on
    events = board_pass(w)
    assert "JobReleased" in kinds(events) and truck.cargo == 0 and truck.pickup != source


def test_overfill_stops_at_twice_the_slots() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=2)
    units = [put(w, "GARRISON_INFANTRY", "west-airbase") for _ in range(6)]
    board_pass(w)
    assert len(job.claims) == 4 and [u.job_id for u in units[4:]] == [None, None]
    board_pass(w)
    assert len(job.claims) == 4  # the rest keep waiting
    assert joinable_jobs(w, "GARRISON_INFANTRY") == []  # a JOIN finds the job full too


def test_overfill_factor_is_a_key_not_a_constant() -> None:
    rules = dataclasses.replace(RULES, tasking=dataclasses.replace(TR, overfill_factor=3))
    w = new_world(rules=rules)
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=2)
    for _ in range(8):
        put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert len(job.claims) == 6  # three times its slots, not twice


def test_the_garrison_may_counterattack_a_node_just_lost_within_the_window() -> None:
    w = new_world()
    w.owner["fob-n-e"] = "ENEMY"
    strike = post(w, "COALITION", "STRIKE", "fob-n-e", "s")
    ai = put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    board_pass(w)
    assert ai.job_id is None  # nobody lost it: offense needs a player
    w.lost["fob-n-e"] = w.campaign.running_ticks + 1
    board_pass(w)
    assert ai.job_id == strike.id
    w.lost["fob-n-e"] = w.campaign.running_ticks - TR.counterattack_window_ticks - 1
    late = put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    board_pass(w)
    assert late.job_id is None and "fob-n-e" not in w.lost  # the window closed and was pruned
    w.lost["fob-n-e"] = w.campaign.running_ticks + 1
    wreck = put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    wreck.damage_state = "DISABLED"
    board_pass(w)
    assert wreck.job_id is None  # only units still able to fight


def test_an_aircraft_skips_a_job_whose_route_crosses_a_discovered_air_defense_ring() -> None:
    w = new_world()
    far = post(w, "COALITION", "STRIKE", "static-hq", "hq")  # 380 km east of the jet, on y = 120 km
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    ring = 30_000
    # A SAM site at (300 km, 100 km): 20 km off the line, inside its 30 km ring.
    w.markers["COALITION"][50] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(300_000, 100_000), True, 1, ring, "HEALTHY"
    )
    board_pass(w)
    assert jet.job_id is None
    w.markers["COALITION"][50].state = "DISABLED"  # last confirmed Disabled: no danger
    board_pass(w)
    assert jet.job_id == far.id
    jet.job_id, jet.path = None, []
    far.claims.clear()
    w.markers["COALITION"][50].state = "HEALTHY"
    # The target being that very site is exempt (a strike on it), and so is a route that clears it.
    w.markers["COALITION"][50] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(*RULES.roads.pos["east-airbase"]), True, 1, ring, "HEALTHY"
    )
    board_pass(w)  # the generator posts a strike on the discovered site's own base
    assert jet.job_id is not None and w.boards["COALITION"][jet.job_id].node == "east-airbase"


def test_a_scouted_cell_is_not_posted_again_during_its_cooldown() -> None:
    w = new_world()
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    uav = put(w, "RECON_UAV", "west-airbase")
    board_pass(w)
    uav.path, uav.state = [], "ON_STATION"
    board_pass(w)  # arrived: DONE, and the blob is still in view
    assert jobs(w) == [] and uav.job_id is None
    for _ in range(3):  # the cooldown is 5 game minutes = 3,000 ticks = 60 passes
        board_pass(w)
    assert jobs(w) == []
    w.campaign.running_ticks += TR.scout_cooldown_ticks
    board_pass(w)
    assert [j.key for j in jobs(w)] == ["scout:7"]


def test_a_scout_cell_whose_job_expired_is_not_reposted_during_the_cooldown() -> None:
    w = new_world()
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))  # no recon unit: nobody can take it
    put(w, "RECON_UAV", "west-airbase").damage_state = "DISABLED"
    w.cooldown["COALITION"].clear()
    put(w, "RECON_UAV", "west-airbase").path = ["east-airbase"]  # busy: never idle
    board_pass(w)
    (job,) = jobs(w)
    w.campaign.running_ticks += TR.expire_ticks  # unclaimed past its expiry
    out = board_pass(w)
    assert [e.kind for e in out if e.kind == "JobExpired"] == ["JobExpired"] and jobs(w) == []
    board_pass(w)
    assert jobs(w) == [] and job.id not in w.boards["COALITION"]  # the blob is still there
    w.campaign.running_ticks += TR.scout_cooldown_ticks
    board_pass(w)
    assert [j.key for j in jobs(w)] == ["scout:7"]


def test_strike_reads_defense_hp_from_the_view() -> None:
    w = new_world()
    assert side_view(w, "COALITION").defense_hp["east-airbase"] == 500
    w.defense_hp["east-airbase"] = 0
    assert side_view(w, "ENEMY").defense_hp["east-airbase"] == 0


def test_a_side_with_nobody_to_staff_a_kind_posts_no_jobs_of_it() -> None:
    w = new_world()
    w.stock["fob-n-e"] = 0  # the Static's base is starved, but it has no truck
    see(w, "ENEMY", Blob("3-1", Vec2(300e3, 5e3), "L"))
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    board_pass(w)
    assert jobs(w, "ENEMY") == []  # no carrier, no recon
    assert [j.kind for j in jobs(w)] == [
        "SCOUT"
    ]  # a viewer can JOIN as recon, so the coalition keeps it
    convoy = w.spawn("ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", Vec2(380e3, 120e3), vel=Vec2(0, 0))
    board_pass(w)
    assert [j.kind for j in jobs(w, "ENEMY")] == [
        "RESUPPLY"
    ]  # now it has a carrier, still no recon
    convoy.damage_state = "DISABLED"
    board_pass(w)
    assert jobs(w, "ENEMY") == []


def test_a_scout_job_waits_for_a_blob_to_stay_in_its_cell_for_two_refreshes() -> None:
    w = new_world()
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"), runs=1)
    board_pass(w)
    assert jobs(w) == []  # a blob that just arrived (or is crossing cells) posts nothing
    w.blob_runs["COALITION"]["7"] = 2  # the next refresh found it still there
    assert kinds(board_pass(w)) == ["JobCreated"]


# --- QA fixes ----------------------------------------------------------------------------------


def restored(w: World) -> World:
    again = load(save(w))
    again.rules = w.rules
    return again


def job_events(events: list[Event]) -> list[tuple[str, int, int | None]]:
    return [
        (e.kind, e.event_seq, getattr(e, "entity_id", None))
        for e in events
        if e.kind.startswith("Job")
    ]


def test_claims_stay_in_entity_id_order_so_a_restored_world_emits_the_same_events() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=3)
    a = put(w, "GARRISON_INFANTRY", "west-airbase")  # the lower id claims second
    b = put(w, "GARRISON_INFANTRY", "west-airbase")
    a.order = "HOLD"
    for _ in range(EVERY):
        step(w, [])
    assert list(job.claims) == [b.id]
    a.order = None
    for _ in range(EVERY):
        step(w, [])
    assert list(job.claims) == [a.id, b.id]
    twin = restored(w)
    for x in (w, twin):
        for i in (a.id, b.id):
            x.get(i).damage_state = "DISABLED"
    seen = []
    for x in (w, twin):
        events: list[Event] = []
        for _ in range(EVERY):
            events += step(x, [])
        seen.append(job_events(events))
    assert seen[0] == seen[1] and len(seen[0]) == 2


@settings(max_examples=8)  # each example runs a 620-tick scenario
@given(st.integers(0, 300))
def test_a_restored_world_steps_exactly_like_the_live_one(extra: int) -> None:
    w = scenario()
    for _ in range(extra):
        step(w, [])
    twin = restored(w)
    for _ in range(150):
        live, copy = step(w, []), step(twin, [])
        assert [e.model_dump() for e in live] == [e.model_dump() for e in copy]
    assert state_hash(w) == state_hash(twin)


def test_a_removed_units_claim_is_released_at_once_with_the_event() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=1)
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    out: list[Event] = []
    lose_unit(w, unit, out)
    assert [e.kind for e in out][:2] == ["JobReleased", "UnitDestroyed"] and job.claims == {}
    wreck = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert job.claims
    wreck.damage_state, wreck.wreck_left = "DISABLED", 1
    events = step(w, [])  # the wreck times out this tick
    assert "JobReleased" in kinds(events) and job.claims == {}


def test_a_new_aircraft_avoids_a_ringed_route_like_a_board_assignment() -> None:
    w = new_world()
    far = post(w, "COALITION", "STRIKE", "static-hq", "hq", urgency=1500)
    w.markers["COALITION"][50] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(300_000, 100_000), True, 1, 30_000, "HEALTHY"
    )
    assert [j.id for j in joinable_jobs(w, "STRIKE_FIGHTER")] == [far.id]
    events = step(w, [join(1, "STRIKE")])
    (jet,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert "JobClaimed" not in kinds(events) and jet.job_id is None and jet.order is None
    w.markers["COALITION"][50].state = "DISABLED"
    step(w, [join(2, "STRIKE").model_copy(update={"target_tick": w.campaign.tick + 1})])
    (jet2,) = [e for e in w.entities() if e.commander_id == cid(2)]
    assert jet2.job_id == far.id


def test_a_truck_never_takes_a_non_resupply_job_from_the_board_or_a_join() -> None:
    w = new_world()
    w.objective = Objective(1, "east-airbase", 90_000, False)
    put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    board_pass(w)
    assert {j.kind for j in jobs(w)} >= {"ASSIST_OBJECTIVE", "STRIKE"} and truck.job_id is None
    events = step(w, [join(1, "LOGI")])
    assert "JobClaimed" not in kinds(events)


def test_an_evicted_ai_unit_stops_at_once() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d", slots=1)
    ground = put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    board_pass(w)
    assert job.claims and ground.path
    ground.path = ["fob-s-w", "cross-s"]  # mid-road, two legs to go: it finishes the current one
    human = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert ground.job_id is None and ground.path == ["fob-s-w"] and human.job_id == job.id
    w2 = new_world()
    job2 = post(w2, "COALITION", "DEFEND", "fob-n-w", "d", slots=1)
    ai_jet = put(w2, "STRIKE_FIGHTER", "west-airbase", AI)
    board_pass(w2)
    assert ai_jet.path == ["fob-n-w"]
    put(w2, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w2)
    assert ai_jet.path == [] and job2.claims and ai_jet.job_id is None


def test_a_deduped_spec_that_becomes_the_objective_ends_with_it() -> None:
    w = new_world()
    pos = Vec2(*RULES.roads.pos["fob-n-e"])
    w.markers["COALITION"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", pos, True, 1, 35_000, "HEALTHY"
    )
    board_pass(w)
    (job,) = jobs(w)
    assert job.objective is None and job.expires is not None
    w.objective = Objective(1, "fob-n-e", 90_000, False)
    board_pass(w)
    assert [j.id for j in jobs(w) if j.kind == "STRIKE"] == [job.id]
    assert [(j.objective, j.expires) for j in jobs(w) if j.kind == "STRIKE"] == [(1, None)]


def test_a_unroutable_job_costs_one_search_per_node_pair() -> None:
    w = new_world()
    for i in range(6):
        post(w, "COALITION", "ASSIST_OBJECTIVE", "bridge-n", f"u{i}", slots=4)
    for _ in range(40):
        put(w, "GARRISON_INFANTRY", "west-airbase")
    start = time.perf_counter()
    board_pass(w)
    print(f"40 ground units, 6 unroutable jobs: {(time.perf_counter() - start) * 1000:.1f} ms")
    assert not [e for e in w.entities() if e.job_id]


def test_a_board_holds_at_most_scout_open_max_scout_jobs_highest_urgency_first() -> None:
    w = new_world()
    blobs = [
        Blob("3-1", Vec2(1e3, 1e3), "S"),
        Blob("3-2", Vec2(2e3, 1e3), "L"),
        Blob("3-3", Vec2(3e3, 1e3), "S"),
        Blob("3-4", Vec2(4e3, 1e3), "M"),
        Blob("3-5", Vec2(5e3, 1e3), "L"),
    ]
    see(w, "COALITION", *blobs)
    put(w, "RECON_UAV", "west-airbase")  # a board only generates what it can staff
    assert TR.scout_open_max == 3 and TR.scout_post_interval_ticks == 1200
    seen = []
    for _ in range(5):  # one new scout job per interval, whatever is in view
        board_pass(w)
        seen.append(len([j for j in jobs(w) if j.kind == "SCOUT"]))
        board_pass(w)  # a second pass inside the interval posts nothing new
        assert len([j for j in jobs(w) if j.kind == "SCOUT"]) == seen[-1]
        w.campaign.running_ticks += TR.scout_post_interval_ticks
    # urgency L 2.0, L 2.0, M 1.5 beat S 1.0; the L tie goes by key; never more than 3
    assert seen == [1, 2, 3, 3, 3]
    assert sorted(j.key for j in jobs(w) if j.kind == "SCOUT") == ["scout:2", "scout:4", "scout:5"]


# --- coalition front-line patrols (Q-SIM-94, NX-382) ---------------------------------------------
# Strait-1 at the start: fob-n-w and fob-s-w (130 km, 60 and 180 km) face the neutral crossings,
# west-airbase and the haven sanctuary do not; the Static holds fob-n-e, fob-s-e and east-airbase.
PATROL_RULES = dataclasses.replace(RULES, tasking=PATROL_TR)
CORNER_TEST_NODE = "fob-n-w"


def pw(tr: TaskingRules = PATROL_TR) -> World:
    return new_world(1, dataclasses.replace(RULES, tasking=tr))


def _patrols(w: World, tr: TaskingRules = PATROL_TR) -> list[tuple[str, int]]:
    specs = generate(
        w, dataclasses.replace(RULES, tasking=tr), tr, "COALITION", side_view(w, "COALITION")
    )
    return [(s.key, s.slots) for s in specs if s.kind == "PATROL"]


def test_front_line_nodes_are_posted_nearest_the_foe_first_and_capped() -> None:
    w = pw()
    put(w, "GARRISON_INFANTRY", "west-airbase")
    # both face the neutral crossings, as far from the Static's nodes as each other: the tie by id
    assert _patrols(w) == [("patrol:fob-n-w", 2), ("patrol:fob-s-w", 2)]
    w.owner["cross-n"] = "COALITION"  # the front moves up: cross-n is 63 km from fob-n-e ...
    w.owner["east-airbase"] = "COALITION"  # ... east-airbase 70 km from static-hq, fob-s-w 160 km
    assert [k for k, _ in _patrols(w)] == [
        "patrol:cross-n",
        "patrol:east-airbase",
        "patrol:fob-s-w",
    ]
    one = dataclasses.replace(PATROL_TR, patrol_max_nodes=1)
    assert [k for k, _ in _patrols(w, one)] == ["patrol:cross-n"]  # the cap
    off = dataclasses.replace(PATROL_TR, patrol_max_nodes=0)
    assert _patrols(w, off) == []


def test_a_sanctuary_is_never_a_front_line_node_and_a_back_node_is_not_one() -> None:
    w = pw()
    put(w, "GARRISON_INFANTRY", "west-airbase")
    w.owner["west-airbase"] = (
        "ENEMY"  # haven (a sanctuary) now has a road neighbour the Static holds
    )
    keys = [k for k, _ in _patrols(w)]
    assert "patrol:haven" not in keys and keys == ["patrol:fob-n-w", "patrol:fob-s-w"]
    w.owner["west-airbase"] = "COALITION"
    w.owner["cross-n"] = w.owner["cross-s"] = "COALITION"
    assert "patrol:west-airbase" not in [k for k, _ in _patrols(w)]  # every neighbour is ours


def test_patrols_are_posted_only_while_a_viewer_unit_that_fits_is_idle() -> None:
    w = pw()
    assert _patrols(w) == []  # nobody
    put(w, "GARRISON_INFANTRY", "west-airbase", AI)  # the garrison does not count
    put(w, "LOGI_TRUCK", "west-airbase")  # a carrier does not fit
    assert _patrols(w) == []
    held = put(w, "STRIKE_FIGHTER", "west-airbase")
    held.order = "HOLD"  # an explicit order keeps the board off the unit
    assert _patrols(w) == []
    held.order = None
    assert [k for k, _ in _patrols(w)] == ["patrol:fob-n-w", "patrol:fob-s-w"]
    recon = put(w, "RECON_UAV", "west-airbase")
    held.job_id = 99  # busy; the recon aircraft (armed or recon, either domain) is enough
    assert [k for k, _ in _patrols(w)] == ["patrol:fob-n-w", "patrol:fob-s-w"]
    recon.job_id = 99
    assert _patrols(w) == []


def test_the_ai_garrison_never_takes_a_patrol_and_a_viewer_unit_does() -> None:
    w = pw()
    grunt = put(w, "GARRISON_INFANTRY", "west-airbase")
    ai = put(w, "GARRISON_INFANTRY", "west-airbase", AI)  # after the viewer's claim, which AI joins
    board_pass(w)
    assert ai.job_id is None and grunt.job_id is not None
    job = w.boards["COALITION"][grunt.job_id]
    assert (job.kind, job.via, job.slots) == ("PATROL", None, PATROL_TR.slots["PATROL"])
    assert grunt.path[-1] == job.node  # it drives out to the node


def test_a_patrol_is_the_lowest_priority_so_a_defend_wins() -> None:
    w = pw()
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    w.owner["cross-n"] = "COALITION"
    defend = post(w, "COALITION", "DEFEND", "fob-s-w", "d")
    board_pass(w)
    assert unit.job_id == defend.id


def test_an_aircraft_skips_a_patrol_whose_orbit_reaches_a_discovered_ring() -> None:
    one = dataclasses.replace(PATROL_TR, patrol_max_nodes=1)  # only patrol:fob-n-w (130, 60 km)
    w = pw(one)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    # a SAM 33 km north of the node with a 30 km ring: outside the ring, inside ring + 5 km orbit
    w.markers["COALITION"][50] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(130_000, 27_000), True, 1, 30_000, "HEALTHY"
    )
    board_pass(w)
    assert jet.job_id is None and [j.key for j in jobs(w)] == ["patrol:fob-n-w"]
    w.markers["COALITION"][50].state = "DISABLED"  # last seen Disabled: no danger
    board_pass(w)
    assert jet.job_id is not None and jet.path == ["fob-n-w"]


def test_a_ground_patrol_never_routes_through_a_node_the_side_does_not_hold() -> None:
    one = dataclasses.replace(PATROL_TR, patrol_max_nodes=1)
    w = pw(one)
    w.owner["west-airbase"] = "ENEMY"  # the only road between the two forward bases
    unit = put(w, "GARRISON_INFANTRY", "fob-s-w")
    assert _patrols(w, one) == [("patrol:fob-n-w", 2)]
    board_pass(w)
    assert unit.job_id is None and not unit.path  # the short way is the Static's; no other is ours
    w.owner["west-airbase"] = "COALITION"
    board_pass(w)
    assert unit.path == ["fob-s-w", "west-airbase", "fob-n-w"]


@settings(max_examples=60, deadline=None)
@given(
    owners=st.lists(
        st.sampled_from(["COALITION", "ENEMY", "NEUTRAL"]),
        min_size=len(RULES.roads.pos),
        max_size=len(RULES.roads.pos),
    ),
    start=st.integers(0, len(RULES.roads.pos) - 1),
)
def test_a_coalition_patrol_never_names_a_node_the_coalition_does_not_hold(
    owners: list[str], start: int
) -> None:
    w = pw()
    for n, o in zip(sorted(RULES.roads.pos), owners, strict=True):
        w.owner[n] = o  # type: ignore[assignment]  # one of the three owners
    here = sorted(n for n in RULES.roads.pos if w.owner[n] == "COALITION")
    if not here:
        return
    unit = put(w, "GARRISON_INFANTRY", here[start % len(here)])
    jet = put(w, "STRIKE_FIGHTER", here[start % len(here)])
    board_pass(w)
    for e in (unit, jet):
        job = w.boards["COALITION"].get(e.job_id or 0)
        if job is not None and job.kind == "PATROL":
            assert job.node is not None and w.owner[job.node] == "COALITION"
            assert all(w.owner[n] == "COALITION" for n in e.path if isinstance(n, str))


def test_a_patrol_is_done_after_the_dwell_and_the_unit_returns_to_the_board() -> None:
    one = dataclasses.replace(PATROL_TR, patrol_max_nodes=1)
    w = pw(one)
    unit = put(w, "GARRISON_INFANTRY", CORNER_TEST_NODE)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    job = jobs(w)[0]
    assert unit.job_id == job.id and jet.job_id == job.id  # two slots
    unit.path.clear()  # it has arrived
    jet.path.clear()
    jet.last_node, jet.state, jet.pos = job.node, "ON_STATION", unit.pos
    board_pass(w)
    assert job.arrived is not None and job.id in w.boards["COALITION"]
    node = Vec2(*RULES.roads.pos[CORNER_TEST_NODE])
    assert [(p.x - node.x, p.y - node.y) for p in jet.path if isinstance(p, Vec2)] in (
        [(5000, 0)],
        [(0, 5000)],
        [(-5000, 0)],
        [(0, -5000)],
    )  # it circles the node at patrol_orbit_m
    w.campaign.running_ticks += PATROL_TR.patrol_dwell_ticks - 2 * EVERY
    out = board_pass(w)
    assert job.id in w.boards["COALITION"] and not of(out, JobDone)  # not yet
    w.campaign.running_ticks += 2 * EVERY
    out = board_pass(w)
    done = of(out, JobDone)
    assert [d.job_id for d in done] == [job.id]
    assert sorted(p.entity_id for p in done[0].participants) == [unit.id, jet.id]
    assert unit.job_id is None or unit.job_id != job.id  # back on the board


def test_a_patrol_fails_and_its_unit_stops_when_its_node_is_lost() -> None:
    one = dataclasses.replace(PATROL_TR, patrol_max_nodes=1)
    w = pw(one)
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert unit.path[-1] == "fob-n-w"
    w.owner["fob-n-w"] = "ENEMY"
    out = board_pass(w)
    assert [e.kind for e in out if e.kind == "JobFailed"] == ["JobFailed"]
    assert "fob-n-w" not in unit.path and unit.job_id is None


def test_a_patrol_replays_identically() -> None:
    def hashes() -> list[str]:
        w = pw()
        put(w, "GARRISON_INFANTRY", "west-airbase")
        put(w, "RECON_UAV", "west-airbase")
        out = []
        for _ in range(3):
            board_pass(w)
            out.append(state_hash(w))
        return out

    assert hashes() == hashes()


# --- patrol fix round (NX-382): preemption, the per-tick hold check, snapshot rules ---------------


def _one() -> TaskingRules:
    return dataclasses.replace(PATROL_TR, patrol_max_nodes=1)  # only patrol:fob-n-w


def test_a_patrolling_unit_switches_to_a_better_job_it_can_take() -> None:
    w = pw(_one())
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    patrol = w.boards["COALITION"][jet.job_id or 0]
    assert patrol.kind == "PATROL"
    strike = post(w, "COALITION", "STRIKE", "fob-n-e", "s")
    out = board_pass(w)
    assert jet.job_id == strike.id and jet.job_id != patrol.id
    assert [e.kind for e in out if e.kind == "JobReleased"] == ["JobReleased"]
    assert patrol.claims == {}


def test_a_ground_patrol_unit_switches_to_a_defend() -> None:
    w = pw(_one())
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert w.boards["COALITION"][unit.job_id or 0].kind == "PATROL"
    defend = post(w, "COALITION", "DEFEND", "fob-s-w", "d")
    board_pass(w)
    assert unit.job_id == defend.id


def test_a_patrol_is_kept_for_a_better_job_the_unit_cannot_take() -> None:
    w = pw(_one())
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    patrol_id = jet.job_id
    # east-airbase: a discovered ring straight across the jet's way there (TB-2 refuses it)
    post(w, "COALITION", "STRIKE", "static-hq", "hq")
    w.markers["COALITION"][50] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(300_000, 100_000), True, 1, 30_000, "HEALTHY"
    )
    out = board_pass(w)
    assert jet.job_id == patrol_id
    assert not of(out, JobReleased)  # kept, not dropped and re-claimed


def test_a_patrol_is_kept_for_a_better_job_that_is_full() -> None:
    w = pw(_one())
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    patrol_id = jet.job_id
    strike = post(w, "COALITION", "STRIKE", "fob-n-e", "s", slots=1)
    claim(w, put(w, "STRIKE_FIGHTER", "west-airbase"), strike, [])  # its one slot is taken
    out = board_pass(w)
    assert jet.job_id == patrol_id and not of(out, JobReleased)


def test_a_patrol_is_kept_for_a_job_that_is_not_better() -> None:
    low = dataclasses.replace(_one(), priority={**PATROL_TR.priority, "STRIKE": Fraction(10)})
    w = pw(low)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    patrol_id = jet.job_id
    post(w, "COALITION", "STRIKE", "fob-n-e", "s")  # open, feasible, fits: priority 10 < 15
    out = board_pass(w)
    assert jet.job_id == patrol_id and not of(out, JobReleased)


def test_a_shipped_strike_fighter_finishes_a_patrol_before_bingo() -> None:
    w = pw(_one())
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    done: list[JobDone] = []
    for _ in range(PATROL_TR.claim_lease_ticks * 10):
        done += of(step(w, []), JobDone)
        if done:
            break
        assert jet.state != "RTB"  # bingo would end the patrol early
    assert [p.entity_id for d in done for p in d.participants] == [jet.id]


def test_a_node_lost_mid_route_is_never_entered() -> None:
    w = pw(_one())
    unit = put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert unit.path == ["west-airbase", "fob-n-w"]
    (ax, ay), (bx, by) = RULES.roads.pos["west-airbase"], RULES.roads.pos["fob-n-w"]
    k = 1 - 60 / ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5  # 60 m short of the node
    unit.pos, unit.path = Vec2(ax + k * (bx - ax), ay + k * (by - ay)), ["fob-n-w"]
    w.owner["fob-n-w"] = "ENEMY"  # flips between two board passes
    node = Vec2(bx, by)
    for _ in range(30):
        step(w, [])
        assert unit.pos != node and unit.last_node != "fob-n-w"
    assert unit.job_id is None and not unit.path


def test_a_lost_route_node_fails_the_patrol_though_its_own_node_is_held() -> None:
    w = pw(_one())
    unit = put(w, "GARRISON_INFANTRY", "fob-s-w")
    board_pass(w)
    assert unit.path == ["fob-s-w", "west-airbase", "fob-n-w"]
    w.owner["west-airbase"] = "ENEMY"  # not the job's node: a node on the way
    out: list[Event] = []
    run(w, out)  # a tick that is no board pass
    assert [e.kind for e in out] == ["JobFailed"]
    assert "west-airbase" not in unit.path and unit.job_id is None


def test_the_dwell_restarts_when_no_claimant_is_left() -> None:
    w = pw(_one())
    unit = put(w, "GARRISON_INFANTRY", CORNER_TEST_NODE)
    board_pass(w)
    unit.path.clear()
    board_pass(w)
    job = jobs(w)[0]
    assert job.arrived is not None
    unit.order = "HOLD"  # a human order releases the claim
    board_pass(w)
    assert job.claims == {} and job.arrived is None


def test_a_parameterless_join_never_takes_a_patrol() -> None:
    w = pw(_one())
    put(w, "GARRISON_INFANTRY", "west-airbase")
    board_pass(w)
    assert [j.kind for j in jobs(w)] == ["PATROL"]  # open: a slot is free
    for kind in ("STRIKE_FIGHTER", "RECON_UAV", "GARRISON_INFANTRY"):
        assert joinable_jobs(w, kind) == []


def _reload(w: World, edit: Any) -> None:
    w.campaign.tick = w.campaign.running_ticks  # board_pass moves only the running clock
    raw = msgpack.unpackb(save(w), raw=False)
    edit(raw["boards"])
    load(msgpack.packb(raw, use_bin_type=True))


def test_snapshot_patrol_jobs_follow_their_board() -> None:
    w = pw(_one())
    unit = put(w, "GARRISON_INFANTRY", CORNER_TEST_NODE)
    board_pass(w)
    unit.path.clear()
    board_pass(w)  # a coalition patrol that dwells
    assert jobs(w)[0].arrived is not None
    _reload(w, lambda b: None)  # valid as it is
    post_job(w, "ENEMY", JobSpec("PATROL", "op:p", 1, 1000, node="east-airbase", via="cross-n"), [])
    w.campaign.running_ticks += 1
    _reload(w, lambda b: None)

    def coalition(b: Any) -> Any:
        return next(j for j in b["COALITION"] if j["kind"] == "PATROL")

    def enemy(b: Any) -> Any:
        return next(j for j in b["ENEMY"] if j["kind"] == "PATROL")

    bad: list[tuple[Any, str]] = [
        (lambda b: coalition(b).update(via="cross-n"), "Static's patrol"),
        (lambda b: enemy(b).update(via=None), "Static's patrol"),
        (lambda b: enemy(b).update(arrived=5), "dwells"),
        (lambda b: enemy(b).update(key="patrol:east-airbase"), "coalition board's"),
    ]
    for edit, why in bad:
        with pytest.raises(ValueError, match=why):
            _reload(w, edit)
