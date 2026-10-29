"""NX-475: the coalition retake job (GAMEPLAY §1b; Q-TD-94 (b), Q-TD-99, Q-TD-100, Q-TD-101).

A `retake:<node>` CAPTURE job on the coalition board: a strategic node the coalition held at
campaign start and does not hold now, posted once its defenses are down, one at a time, the node
nearest a coalition-held node first. A viewer's truck takes it from the board or with a bare
`!join logi`; it ranks below a starving base's resupply and above a stocking one. The Static's
board and its CAPTURE jobs are unchanged. Scenes reuse `test_tasking` (strait-1, board passes by
hand) with the campaign rules on (the strategic nodes) and timed objectives off.

strait-1: the coalition starts with `west-airbase` (90 km, 120 km), `fob-n-w` (130, 60),
`fob-s-w` (130, 180) and the haven (20, 120); `cross-n`/`cross-s` start NEUTRAL, the east ENEMY.
"""

import dataclasses
from typing import Any

import msgpack
import pytest
from fixture_pre_5b import pre_5b_config
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import cid, join
from test_tasking import (
    AI,
    CONFIG,
    EVERY,
    RULES,
    board_pass,
    jobs,
    new_world,
    of,
    post,
    put,
    see,
)

from nexus.contracts.gen.common.enums import NodeOwner, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_created import JobCreated
from nexus.contracts.gen.events.job_done import JobDone
from nexus.core import tasking_gen
from nexus.core.capture import _switch_facilities
from nexus.core.logistics import plan_run
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking import _now, idle_diagnosis, priority, rank
from nexus.core.tasking_gen import fits_job
from nexus.core.world import Blob, Job, Vec2, World, load, save, state_hash

_CAMPAIGN = CONFIG.rules.campaign
assert _CAMPAIGN is not None
RET_RULES: Rules = dataclasses.replace(
    RULES, campaign=dataclasses.replace(_CAMPAIGN, objectives_on=False)
)
STOCK_RET_RULES: Rules = dataclasses.replace(RET_RULES, supply=CONFIG.rules.supply)


def _keep(minutes: float) -> Rules:
    """RET_RULES with `tasking.retake_keep_min` set through the shipped config and its loader."""
    tr = pre_5b_config({"tasking.retake_keep_min": minutes}).rules.tasking
    assert tr is not None
    return dataclasses.replace(RET_RULES, tasking=dataclasses.replace(tr, patrol_max_nodes=0))


KEEP_0, KEEP_5 = _keep(0), _keep(5)
COALITION_START = ("fob-n-w", "fob-s-w", "west-airbase")


def lose(w: World, *nodes: str, to: NodeOwner = "ENEMY", hp: int = 0) -> None:
    """The coalition lost `nodes` (their facilities change side) and their defenses are at `hp`."""
    for n in nodes:
        w.owner[n] = to
        w.defense_hp[n] = hp
        if to != "NEUTRAL":
            _switch_facilities(w, n, to)


def retakes(w: World, side: Any = "COALITION") -> list[Job]:
    return [j for j in jobs(w, side) if j.key.startswith("retake:")]


def scene(*lost: str, rules: Rules = RET_RULES) -> World:
    w = new_world(rules=rules)
    lose(w, *lost)
    return w


# --- posting ------------------------------------------------------------------------------------


def test_the_job_waits_for_the_nodes_defenses_to_be_down() -> None:
    w = new_world(rules=RET_RULES)
    lose(w, "fob-n-w", hp=150)
    board_pass(w)
    assert retakes(w) == []  # defenses up: the strike comes first
    w.defense_hp["fob-n-w"] = 1
    board_pass(w)
    assert retakes(w) == []
    w.defense_hp["fob-n-w"] = 0
    board_pass(w)
    (job,) = retakes(w)
    assert (job.kind, job.key, job.node, job.slots, job.urgency) == (
        "CAPTURE", "retake:fob-n-w", "fob-n-w", 1, 1000,
    )  # fmt: skip


def test_only_a_strategic_node_held_at_start_and_lost_now_is_eligible_with_no_window() -> None:
    w = new_world(rules=RET_RULES)
    for n in ("cross-n", "fob-n-e", "east-airbase"):  # never the coalition's at start
        w.defense_hp[n] = 0
    w.owner["cross-n"] = "ENEMY"
    board_pass(w)
    assert retakes(w) == []  # nothing the coalition started with is lost
    lose(w, "fob-s-w", to="NEUTRAL")  # not held now, though nobody holds it
    assert w.lost == {}  # no recent-loss memory: eligibility has no time window (Q-TD-101)
    w.campaign.running_ticks += 100 * RET_RULES.tasking.expire_ticks  # type: ignore[union-attr]
    board_pass(w)
    assert [j.node for j in retakes(w)] == ["fob-s-w"]


def test_the_static_board_never_posts_a_retake() -> None:
    w = new_world(rules=RET_RULES)
    lose(w, "fob-n-e", "east-airbase", to="COALITION")  # the Static lost its own start nodes
    put(w, "ENEMY_CONVOY", "static-hq", AI)
    board_pass(w)
    assert retakes(w, "ENEMY") == [] and retakes(w) == []


def test_one_job_at_a_time_the_node_nearest_a_held_node_first() -> None:
    w = scene("west-airbase", "fob-n-w")  # held: fob-s-w and the haven
    board_pass(w)
    # west-airbase: 70 km from the haven; fob-n-w: 120 km from fob-s-w, 125 km from the haven
    assert [j.node for j in retakes(w)] == ["west-airbase"]
    w.owner["west-airbase"] = "COALITION"  # retaken (by anyone): the next one is posted
    board_pass(w)
    assert [j.node for j in retakes(w)] == ["fob-n-w"]


def test_ties_go_to_the_lower_node_id() -> None:
    w = scene("fob-n-w", "fob-s-w")  # both 72.1 km from west-airbase
    board_pass(w)
    assert [j.node for j in retakes(w)] == ["fob-n-w"]


def test_the_live_job_is_kept_and_a_claimed_one_blocks_any_other() -> None:
    w = scene("fob-n-w")
    board_pass(w)
    (first,) = retakes(w)
    lose(w, "west-airbase")  # now nearer the haven than fob-n-w is to anything held
    board_pass(w)
    assert retakes(w) == [first]  # the live job stays: no churn
    truck = put(w, "LOGI_TRUCK", "haven")
    w.defense_hp["west-airbase"] = 0
    board_pass(w)
    assert truck.id in first.claims
    w.defense_hp["fob-n-w"] = 50  # no longer eligible, but claimed: it runs out, nothing else
    board_pass(w)
    assert retakes(w) == [first]


def test_an_unclaimed_job_that_stops_qualifying_hands_over_to_the_next() -> None:
    w = scene("fob-n-w", "fob-s-w", rules=KEEP_0)  # no keep: withdrawn at the first pass
    board_pass(w)
    assert [j.node for j in retakes(w)] == ["fob-n-w"]
    w.defense_hp["fob-n-w"] = 50  # the Static repaired it
    board_pass(w)
    assert [j.node for j in retakes(w)] == ["fob-s-w"]


def test_no_job_on_a_node_no_capture_run_can_reach(monkeypatch: pytest.MonkeyPatch) -> None:
    """strait-1 has no start node a road cut can isolate, so the road answer is stubbed: the
    generator asks `plan_run` (the bare JOIN's own capture-run plan) and skips a None."""
    w = scene("west-airbase", "fob-n-w")
    monkeypatch.setattr(
        tasking_gen, "plan_run",  # the name the generator calls
        lambda world, rules, side, dest, **kw: None if dest == "west-airbase"
        else plan_run(world, rules, side, dest, **kw),
    )  # fmt: skip
    board_pass(w)
    assert [j.node for j in retakes(w)] == ["fob-n-w"]  # the nearer one cannot be reached


@settings(max_examples=40, deadline=None)
@given(
    lost=st.sets(st.sampled_from(COALITION_START)),
    up=st.sets(st.sampled_from(COALITION_START)),
    neutral=st.booleans(),
)
def test_property_at_most_one_retake_on_an_eligible_node(
    lost: set[str], up: set[str], neutral: bool
) -> None:
    """Invariant: after any pass the coalition board holds at most one retake job, and it names a
    start node the coalition does not hold, at 0 defense hp; with one eligible, there is one."""
    w = new_world(rules=RET_RULES)
    for n in sorted(lost):
        lose(w, n, to="NEUTRAL" if neutral else "ENEMY", hp=100 if n in up else 0)
    board_pass(w)
    eligible = {n for n in lost if n not in up}
    found = retakes(w)
    assert len(found) == (1 if eligible else 0)
    assert all(j.node in eligible for j in found)


# --- ranking (Q-TD-100) -------------------------------------------------------------------------


def _order(w: World) -> list[str]:
    tr = RET_RULES.tasking
    assert tr is not None
    return [
        j.kind
        for j in rank(tr, jobs(w), _now(w), None, side="COALITION")
        if j.kind in ("RESUPPLY", "CAPTURE")
    ]


def test_a_starving_bases_resupply_outranks_the_retake_and_a_truck_takes_it() -> None:
    w = scene("fob-n-w")
    w.stock["fob-s-w"] = 200  # below its floor of 250: starving
    truck = put(w, "LOGI_TRUCK", "haven")
    board_pass(w)
    assert _order(w) == ["RESUPPLY", "CAPTURE"]
    (claimed,) = [j for j in jobs(w) if truck.id in j.claims]
    assert claimed.kind == "RESUPPLY" and claimed.node == "fob-s-w"


def test_a_waiting_retake_never_ages_past_a_fresh_starving_resupply() -> None:
    """QA's NX-475 case: posted 8 game minutes before `fob-s-w` starves (240 of a 250 floor, urgency
    1040, 52.0 points); with TB-3 aging the retake would score 45 + 8 = 53 and take the truck."""
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    tr = RET_RULES.tasking
    assert tr is not None
    w.campaign.running_ticks += 8 * tr.ticks_per_min  # inside the 15-min expiry
    w.stock["fob-s-w"] = 240
    truck = put(w, "LOGI_TRUCK", "haven")
    board_pass(w)
    assert retakes(w) == [job] and priority(tr, job, _now(w), side="COALITION") == 45  # no aging
    assert _order(w) == ["RESUPPLY", "CAPTURE"]
    (claimed,) = [j for j in jobs(w) if truck.id in j.claims]
    assert claimed.key == "resupply:fob-s-w"


def test_the_retake_outranks_a_stocking_resupply_and_a_truck_takes_it() -> None:
    w = scene("fob-n-w", rules=STOCK_RET_RULES)
    w.stock.update({"west-airbase": 1600, "fob-s-w": 700})  # fob-s-w below target, not starving
    truck = put(w, "LOGI_TRUCK", "haven")
    board_pass(w)
    (stocking,) = [j for j in jobs(w) if j.kind == "RESUPPLY"]
    assert stocking.node == "fob-s-w" and stocking.urgency < 1000
    assert _order(w) == ["CAPTURE", "RESUPPLY"]
    (claimed,) = [j for j in jobs(w) if truck.id in j.claims]
    assert claimed.key == "retake:fob-n-w"


# --- who takes it -------------------------------------------------------------------------------


def test_a_viewer_truck_on_the_board_takes_it_and_drives_a_capture_run() -> None:
    w = scene("fob-n-w")
    truck = put(w, "LOGI_TRUCK", "haven")
    garrison = put(w, "LOGI_TRUCK", "haven", AI)
    board_pass(w)
    (job,) = retakes(w)
    assert list(job.claims) == [truck.id] and truck.job_id == job.id
    assert truck.path[-1] == "fob-n-w" and not truck.cargo
    assert garrison.job_id is None  # the AI garrison never retakes (it never initiates offense)


def test_idle_diagnosis_sees_the_retake_an_idle_viewer_truck_would_take() -> None:
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    w.boards["COALITION"] = {job.id: job}  # only the retake (the SEAD strike there is dropped)
    truck = put(w, "LOGI_TRUCK", "haven")
    assert idle_diagnosis(w, truck) == ("next_pass", job)  # the harness's label: taken next pass
    garrison = put(w, "LOGI_TRUCK", "haven", AI)
    assert idle_diagnosis(w, garrison) == ("no_job", None)


def test_a_bare_join_logi_takes_the_retake() -> None:
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    step(w, [join(1, "LOGI")])
    (truck,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert truck.job_id == job.id and list(job.claims) == [truck.id]
    assert truck.last_node == "haven" and truck.cargo == 0  # a capture run from the rear
    assert truck.path[-1] == "fob-n-w"


def test_a_bare_join_logi_prefers_a_starving_bases_resupply() -> None:
    w = scene("fob-n-w")
    w.stock["fob-s-w"] = 200
    board_pass(w)
    step(w, [join(1, "LOGI")])
    (truck,) = [e for e in w.entities() if e.commander_id == cid(1)]
    job = w.boards["COALITION"][truck.job_id or 0]
    assert (job.kind, job.node) == ("RESUPPLY", "fob-s-w")


def test_other_units_do_not_fit_a_retake_and_trucks_do_not_fit_the_directors_capture() -> None:
    others: tuple[UnitKind, ...] = ("STRIKE_FIGHTER", "RECON_UAV")
    for kind in others:
        assert not fits_job(RET_RULES, kind, "CAPTURE", "retake:fob-n-w")
    assert fits_job(RET_RULES, "LOGI_TRUCK", "CAPTURE", "retake:fob-n-w")
    trucks: tuple[UnitKind, ...] = ("LOGI_TRUCK", "ENEMY_CONVOY")
    for kind in trucks:
        assert not fits_job(RET_RULES, kind, "CAPTURE", "op:capture")  # unchanged (Q-TD-14)


def test_the_static_side_is_unchanged_an_idle_convoy_never_takes_an_op_capture() -> None:
    w = new_world(rules=RET_RULES)
    lose(w, "fob-n-w")
    convoy = put(w, "ENEMY_CONVOY", "static-hq", AI)
    op = post(w, "ENEMY", "CAPTURE", "cross-n", "cap", slots=1)
    board_pass(w)
    assert convoy.job_id is None and op.claims == {}
    assert retakes(w, "ENEMY") == []


# --- end to end, determinism, snapshots ----------------------------------------------------------


def _drive(w: World, ticks: int) -> list[Event]:
    out: list[Event] = []
    for _ in range(ticks):
        out += step(w, [])
        if w.owner["fob-n-w"] == "COALITION":
            break
    return out


def _run(snapshot_at: int | None = None) -> tuple[str, list[str]]:
    w = scene("fob-n-w")
    events: list[Event] = []
    while not retakes(w):  # real ticks: the first board pass posts the job
        events += step(w, [])
    events += step(w, [join(1, "LOGI", target_tick=w.campaign.tick + 1)])  # taken at spawn
    if snapshot_at is not None:
        events += _drive(w, snapshot_at)
        copy = load(save(w))
        copy.rules = w.rules
        assert state_hash(copy) == state_hash(w)
        w = copy
    events += _drive(w, 30_000)
    assert w.owner["fob-n-w"] == "COALITION"
    return state_hash(w), [e.model_dump_json() for e in events]


def test_a_truck_retakes_the_node_and_the_job_is_done_with_it() -> None:
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    step(w, [join(1, "LOGI")])
    (truck,) = [e for e in w.entities() if e.commander_id == cid(1)]
    out = _drive(w, 30_000)
    assert w.owner["fob-n-w"] == "COALITION"
    out += step(w, [])  # finish the tick's board pass if the flip came between passes
    for _ in range(RET_RULES.tasking.reeval_every_ticks):  # type: ignore[union-attr]
        if job.id not in w.boards["COALITION"]:
            break
        out += step(w, [])
    (done,) = [e for e in of(out, JobDone) if e.job_id == job.id]
    assert [p.entity_id for p in done.participants] == [truck.id]
    assert retakes(w) == []  # nothing else lost


def test_the_retake_run_is_deterministic_and_survives_save_and_load() -> None:
    first = _run()
    assert first == _run()
    assert _run(snapshot_at=200) == first


def _reload(w: World, edit: Any) -> None:
    w.campaign.tick = w.campaign.running_ticks
    raw = msgpack.unpackb(save(w), raw=False, strict_map_key=False)
    edit(raw["boards"])
    load(msgpack.packb(raw, use_bin_type=True))


def test_a_snapshot_keeps_the_retake_on_the_coalition_board_only() -> None:
    w = scene("fob-n-w")
    board_pass(w)
    _reload(w, lambda b: None)  # valid as it is

    def mine(b: Any) -> Any:
        return next(j for j in b["COALITION"] if j["key"].startswith("retake:"))

    def moved(b: Any) -> None:
        b["ENEMY"].append(b["COALITION"].pop(b["COALITION"].index(mine(b))))

    with pytest.raises(ValueError, match="coalition board's"):
        _reload(w, moved)
    with pytest.raises(ValueError, match="does not name its kind"):
        _reload(w, lambda b: mine(b).update(key="retake:fob-s-w"))
    with pytest.raises(ValueError, match="only CAPTURE"):
        _reload(w, lambda b: mine(b).update(kind="STRIKE"))
    with pytest.raises(ValueError, match="only CAPTURE"):
        _reload(w, lambda b: mine(b).update(key="op:capture"))  # a coalition CAPTURE is a retake


# --- the keep after the defenses come back (Q-TD-121, NX-484) -----------------------------------
# `tasking.retake_keep_min`: shipped 30 game minutes, 18,000 ticks at 10 Hz; KEEP_5 is 3,000;
# KEEP_0 is no keep. An unclaimed retake never TB-1 expires (Q-TD-121 revised): only withdrawal.


def pass_at(w: World, tick: int) -> list[Event]:
    """One board pass at running tick `tick` (a multiple of the board cadence)."""
    assert tick % EVERY == 0 and tick > w.campaign.running_ticks
    w.campaign.running_ticks = tick - 1
    return board_pass(w)


def restocked(rules: Rules = RET_RULES) -> tuple[World, Job, int]:
    """A posted, unclaimed retake job on fob-n-w whose defenses the Static rebuilt; the pass that
    first saw them up (its keep clock) is returned."""
    w = scene("fob-n-w", rules=rules)
    board_pass(w)
    (job,) = retakes(w)
    w.defense_hp["fob-n-w"] = 50
    board_pass(w)
    assert job.lost == w.campaign.running_ticks  # the clock: the pass just run
    return w, job, job.lost


def ended(out: list[Event], job: Job) -> list[str]:
    return [e.kind for e in out if getattr(e, "job_id", 0) == job.id]


def test_the_loader_reads_the_keep_from_the_shipped_config() -> None:
    assert RET_RULES.tasking is not None and KEEP_5.tasking is not None
    assert RET_RULES.tasking.retake_keep_ticks == 18_000  # 30 game min x 60 s x 10 Hz
    assert KEEP_5.tasking.retake_keep_ticks == 3_000
    assert KEEP_0.tasking is not None and KEEP_0.tasking.retake_keep_ticks == 0


def test_an_unclaimed_job_survives_restored_defenses_inside_the_keep() -> None:
    w, job, up = restocked()  # shipped: 30 min
    out = pass_at(w, up + 10 * 600)  # 10 game min later, inside the job's 15-min expiry too
    assert retakes(w) == [job] and not of(out, JobCreated)


def test_the_job_is_withdrawn_once_the_keep_has_passed() -> None:
    w, job, up = restocked(KEEP_5)
    pass_at(w, up + 3_000 - EVERY)
    assert retakes(w) == [job]  # the last pass inside the keep
    out = pass_at(w, up + 3_000)
    assert retakes(w) == [] and ended(out, job) == ["JobExpired"]


def test_defenses_down_again_inside_the_keep_continue_the_same_job_with_a_fresh_clock() -> None:
    w, job, up = restocked(KEEP_5)
    w.defense_hp["fob-n-w"] = 0  # struck down again at 2.5 min
    out = pass_at(w, up + 1_500)
    assert retakes(w) == [job] and job.lost is None and not of(out, JobCreated)
    w.defense_hp["fob-n-w"] = 80  # rebuilt again at 4 min: a new clock starts there
    out += pass_at(w, up + 2_400)
    assert job.lost == up + 2_400
    out += pass_at(w, up + 5_000)  # 8.3 min after the first restock, 4.3 after the second
    assert retakes(w) == [job] and not of(out, JobCreated)
    pass_at(w, up + 2_400 + 3_000)
    assert retakes(w) == []


def test_a_keep_of_zero_withdraws_at_once_and_keeps_no_clock() -> None:
    w = scene("fob-n-w", rules=KEEP_0)
    board_pass(w)
    (job,) = retakes(w)
    w.defense_hp["fob-n-w"] = 50
    out = board_pass(w)
    assert retakes(w) == [] and job.lost is None and ended(out, job) == ["JobExpired"]


EXPIRE = 9_000  # tasking.expire_min 15 game min at 10 Hz


def test_an_unclaimed_retake_at_zero_defenses_never_expires() -> None:
    """Q-TD-121 revised: one job id per lost node while it qualifies, past 2 x `expire_min`."""
    w = scene("fob-n-w", rules=KEEP_0)  # no keep: the exemption alone
    board_pass(w)
    (job,) = retakes(w)
    out: list[Event] = []
    for t in range(job.created + 1_500, job.created + 2 * EXPIRE + 1, 1_500):
        out += pass_at(w, t)
    assert retakes(w) == [job] and ended(out, job) == []
    assert not [e for e in of(out, JobCreated) if e.job_kind == "CAPTURE"]


def test_a_kept_job_outlives_the_expiry_when_the_keep_is_longer() -> None:
    w, job, up = restocked()  # shipped keep 30 min, expiry 15
    pass_at(w, job.created + EXPIRE)
    pass_at(w, up + 18_000 - EVERY)
    assert retakes(w) == [job]
    out = pass_at(w, up + 18_000)
    assert retakes(w) == [] and ended(out, job) == ["JobExpired"]


def test_other_generated_jobs_still_expire_unclaimed() -> None:
    """A scout job nobody takes still expires beside the exempt retake (a coalition resupply job
    no longer does since Q-SIM-131, NX-492: `test_logistics_cadence`)."""
    w = scene("fob-n-w")
    see(w, "COALITION", Blob("3-7", Vec2(75e3, 5e3), "S"))
    put(w, "RECON_UAV", "west-airbase").path = ["east-airbase"]  # busy: never idle
    board_pass(w)
    (old,) = [j for j in jobs(w) if j.key == "scout:7"]
    pass_at(w, old.created + EXPIRE - EVERY)
    assert old.id in w.boards["COALITION"]
    out = pass_at(w, old.created + EXPIRE)
    assert ended(out, old) == ["JobExpired"] and len(retakes(w)) == 1  # TB-1; the retake stays


def test_a_claim_starts_the_retakes_capture_clock() -> None:
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    pass_at(w, job.created + 2 * EXPIRE)  # long past its posting expiry, still posted
    truck = put(w, "LOGI_TRUCK", "haven")
    board_pass(w)
    assert truck.id in job.claims and job.expires == w.campaign.running_ticks + EXPIRE


def test_an_overfill_claim_does_not_restart_the_capture_clock() -> None:
    """Only the first claim starts the clock: a second viewer truck that overfills the one-slot job
    (`tasking.overfill_factor`, no other job fits it) leaves `expires` as it was."""
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    first = put(w, "LOGI_TRUCK", "haven")
    board_pass(w)
    assert list(job.claims) == [first.id]
    clock = job.expires
    second = put(w, "LOGI_TRUCK", "haven")
    board_pass(w)
    assert list(job.claims) == [first.id, second.id] and job.expires == clock


def test_a_hot_reload_through_keep_zero_leaves_no_stale_clock() -> None:
    """Keep 30, defenses up (clock), down again, reload to keep 0 for a pass, back to 30: the next
    return of the defenses starts a fresh keep, not the stale one."""
    w, job, up = restocked()
    w.defense_hp["fob-n-w"] = 0
    assert w.rules is not None
    w.rules = dataclasses.replace(w.rules, tasking=KEEP_0.tasking)
    pass_at(w, up + 1_000)
    assert retakes(w) == [job] and job.lost is None
    w.rules = dataclasses.replace(w.rules, tasking=RET_RULES.tasking)
    pass_at(w, up + 20_000)  # past the old clock's keep (18,000)
    w.defense_hp["fob-n-w"] = 50
    pass_at(w, up + 20_050)
    assert retakes(w) == [job] and job.lost == up + 20_050


def test_a_claimed_retake_still_expires_by_the_capture_rules() -> None:
    """The exemption is for an unclaimed job: a claimant standing at the node with no live bar
    (board passes only, so no capture run starts) ends the job at its CAPTURE clock."""
    w = scene("fob-n-w")
    board_pass(w)
    (job,) = retakes(w)
    truck = put(w, "LOGI_TRUCK", "fob-n-w")
    board_pass(w)
    assert truck.id in job.claims and job.expires is not None
    truck.path = []  # standing on the node (its one-node leg driven)
    pass_at(w, job.expires - EVERY)
    assert job.claims[truck.id].active  # arrived: progress, so the lease holds
    assert job.id in w.boards["COALITION"]
    out = pass_at(w, job.expires)
    assert ended(out, job) == ["JobExpired"]


def test_recapture_withdraws_at_once_inside_the_keep() -> None:
    w, _, _ = restocked()
    w.owner["fob-n-w"] = "COALITION"  # held again, defenses up (no capture run: by anyone)
    board_pass(w)
    assert retakes(w) == []


def test_a_lost_road_withdraws_at_once_inside_the_keep(monkeypatch: pytest.MonkeyPatch) -> None:
    w, _, _ = restocked()
    monkeypatch.setattr(tasking_gen, "plan_run", lambda *a, **kw: None)  # no capture run reaches
    board_pass(w)
    assert retakes(w) == []


def test_no_truck_role_withdraws_at_once_inside_the_keep() -> None:
    w, _, _ = restocked()
    assert w.rules is not None
    roles = {r: k for r, k in w.rules.role_kind.items() if k not in w.rules.supply.carriers}
    w.rules = dataclasses.replace(w.rules, role_kind=roles)
    board_pass(w)
    assert retakes(w) == []


def test_a_snapshot_mid_keep_keeps_the_clock_and_rejects_a_bad_one() -> None:
    w, job, up = restocked(KEEP_5)
    w.campaign.tick = w.campaign.running_ticks  # board passes by hand move only the running clock
    copy = load(save(w))
    copy.rules = w.rules
    assert state_hash(copy) == state_hash(w) and retakes(copy)[0].lost == up
    for world in (w, copy):
        pass_at(world, up + 3_000 - EVERY)
        assert [j.id for j in retakes(world)] == [job.id]
        pass_at(world, up + 3_000)
        assert retakes(world) == []
    w2, _, _ = restocked(KEEP_5)

    def mine(b: Any) -> Any:
        return next(j for j in b["COALITION"] if j["key"].startswith("retake:"))

    with pytest.raises(ValueError, match="at a past tick"):
        _reload(w2, lambda b: mine(b).update(lost=10**9))
    with pytest.raises(ValueError, match="loses its scout"):  # no other coalition job has one
        _reload(w2, lambda b: next(j for j in b["COALITION"] if j is not mine(b)).update(lost=1))


def _keep_run(snapshot_at: int | None = None) -> tuple[str, list[str]]:
    """Real ticks: the job is posted, the defenses come back, fall again, come back, and the keep
    runs out (KEEP_5: 3,000 ticks)."""
    w = scene("fob-n-w", rules=KEEP_5)
    events: list[Event] = []
    while not retakes(w):
        events += step(w, [])
    script = {500: 50, 1_500: 0, 2_000: 80}  # ticks after the posting: fob-n-w's defense hp
    for i in range(6_000):
        w.defense_hp["fob-n-w"] = script.get(i, w.defense_hp["fob-n-w"])
        if i == snapshot_at:
            copy = load(save(w))
            copy.rules = w.rules
            assert state_hash(copy) == state_hash(w)
            w = copy
        events += step(w, [])
    created = [e for e in of(events, JobCreated) if e.job_kind == "CAPTURE"]
    assert len(created) == 1 and retakes(w) == []  # one job through the dip, then withdrawn
    return state_hash(w), [e.model_dump_json() for e in events]


def test_the_keep_is_deterministic_and_survives_save_and_load() -> None:
    first = _keep_run()
    assert first == _keep_run()
    assert _keep_run(snapshot_at=2_500) == first  # mid-keep: the clock is in the snapshot
