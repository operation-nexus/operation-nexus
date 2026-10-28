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
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import cid, join
from test_tasking import AI, CONFIG, RULES, board_pass, jobs, new_world, of, post, put

from nexus.contracts.gen.common.enums import NodeOwner, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.core import tasking_gen
from nexus.core.capture import _switch_facilities
from nexus.core.logistics import plan_run
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking import _now, idle_diagnosis, priority, rank
from nexus.core.tasking_gen import fits_job
from nexus.core.world import Job, World, load, save, state_hash

_CAMPAIGN = CONFIG.rules.campaign
assert _CAMPAIGN is not None
RET_RULES: Rules = dataclasses.replace(
    RULES, campaign=dataclasses.replace(_CAMPAIGN, objectives_on=False)
)
STOCK_RET_RULES: Rules = dataclasses.replace(RET_RULES, supply=CONFIG.rules.supply)
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
    w = scene("fob-n-w", "fob-s-w")
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
    return [j.kind for j in rank(tr, jobs(w), _now(w), None) if j.kind in ("RESUPPLY", "CAPTURE")]


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
    assert retakes(w) == [job] and priority(tr, job, _now(w)) == 45  # no aging
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
