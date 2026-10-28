"""NX-483: a CAPTURE job does not expire while one of its claimants is within the capture radius of
its node and the side's bar there is live (GAMEPLAY §1b, `tasking._capturing`). Both boards: the
Static's `op:` CAPTURE and the coalition's `retake:`. The hold ends with the bar (it flips, or it
drains to 0), spends no restart and keeps no state, and a bar that may stand still for good
(`capture.stalled`, the idle floor and the last base) holds nothing.

strait-1 (the `test_tasking` scene): `cross-n` starts NEUTRAL, with no defenses; `west-airbase` is
the coalition's forward airbase.
"""

from dataclasses import replace

import pytest
from test_join import cid, join
from test_retake import COALITION_START, retakes, scene
from test_tasking import AI, RULES, TR, board_pass, new_world, of, post, put

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.core.rules import CAPTURE_FULL, CaptureRules
from nexus.core.step import step
from nexus.core.tasking import claim
from nexus.core.world import CaptureBar, Job, Vec2, World, load, save, state_hash

_cap = RULES.capture
if _cap is None:
    raise AssertionError("the shipped config has capture rules")
CAP: CaptureRules = _cap
NODE = "cross-n"


def spent(w: World, job: Job) -> None:
    """The job's expiry is due at the next board pass and it has no restart left."""
    job.expires, job.restarts = w.campaign.running_ticks + 1, TR.capture_max_restarts


def static_capture(w: World, node: str = NODE, at: str = NODE) -> tuple[Job, int]:
    """An `op:capture` job on `node` claimed by a Director armor standing at `at`."""
    job = post(w, "ENEMY", "CAPTURE", node, "capture", slots=1)
    armor = put(w, "ENEMY_ARMOR", at, owner="ENEMY_DIRECTOR")
    claim(w, armor, job, [])
    return job, armor.id


def ended(events: list[Event], job: Job) -> list[str]:
    return [e.kind for e in events if isinstance(e, JobDone | JobExpired) and e.job_id == job.id]


def drive(w: World, side: Side, job: Job, ticks: int) -> list[Event]:
    """Real ticks until the job leaves the side's board (or `ticks` pass)."""
    out: list[Event] = []
    for _ in range(ticks):
        out += step(w, [])
        if job.id not in w.boards[side]:
            break
    return out


# --- the hold ------------------------------------------------------------------------------------


def test_a_static_capture_due_mid_bar_is_kept_and_done_on_the_flip() -> None:
    w = new_world()
    job, armor = static_capture(w)
    while w.capture.get(NODE) is None:  # the bar starts under the standing armor
        step(w, [])
    spent(w, job)
    out = drive(w, "ENEMY", job, 20 * TR.reeval_every_ticks)
    assert w.owner[NODE] == "ENEMY"
    assert ended(out, job) == ["JobDone"]  # used to be JobExpired, with the node flipped anyway
    (done,) = [e for e in of(out, JobDone) if e.job_id == job.id]
    assert [p.entity_id for p in done.participants] == [armor]
    assert job.restarts == TR.capture_max_restarts  # the hold spent no restart


def test_a_retake_due_mid_bar_is_kept_and_done_on_the_flip() -> None:
    """The NX-475 QA case: the expiry passes right after the bar starts, restarts used up."""
    w = scene("fob-n-w")
    while not retakes(w):
        step(w, [])
    (job,) = retakes(w)
    step(w, [join(1, "LOGI", target_tick=w.campaign.tick + 1)])
    (truck,) = [e for e in w.entities() if e.commander_id == cid(1)]
    while w.capture.get("fob-n-w") is None:
        step(w, [])
    spent(w, job)
    out = drive(w, "COALITION", job, 30_000)
    assert w.owner["fob-n-w"] == "COALITION"
    assert ended(out, job) == ["JobDone"]
    (done,) = [e for e in of(out, JobDone) if e.job_id == job.id]
    assert [p.entity_id for p in done.participants] == [truck.id]


@pytest.mark.parametrize(
    ("at", "bar", "kept"),
    [
        (NODE, "ENEMY", True),  # on the node, its side's bar: held
        ("cross-s", "ENEMY", False),  # its claimant is elsewhere
        (NODE, "COALITION", False),  # the bar is the other side's
        (NODE, None, False),  # no bar
    ],
)
def test_only_a_claimant_in_the_radius_of_its_sides_live_bar_holds_the_expiry(
    at: str, bar: Side | None, kept: bool
) -> None:
    w = new_world()
    job, _ = static_capture(w, at=at)
    if bar is not None:
        w.capture[NODE] = CaptureBar(bar, CAPTURE_FULL // 2)
    spent(w, job)
    out = board_pass(w)
    assert (job.id in w.boards["ENEMY"]) is kept
    assert ended(out, job) == ([] if kept else ["JobExpired"])


def test_the_radius_is_the_capture_radius() -> None:
    w = new_world()
    job, armor = static_capture(w)
    w.capture[NODE] = CaptureBar("ENEMY", CAPTURE_FULL // 2)
    x, y = RULES.roads.pos[NODE]
    radius = CAP.radius_m
    w.get(armor).pos = Vec2(x + radius, y)  # on the edge: it counts for the bar, so it holds
    spent(w, job)
    board_pass(w)
    assert job.id in w.boards["ENEMY"]
    w.get(armor).pos = Vec2(x + radius + 1, y)
    spent(w, job)
    assert ended(board_pass(w), job) == ["JobExpired"]


def test_a_contested_bar_drains_and_the_job_then_expires() -> None:
    """A coalition infantry contests the bar: it drains to 0 and the hold ends with it."""
    w = new_world()
    job, _ = static_capture(w)
    w.capture[NODE] = CaptureBar("ENEMY", 5 * CAP.decay_micro)
    put(w, "GARRISON_INFANTRY", NODE, owner=AI)
    spent(w, job)
    out = drive(w, "ENEMY", job, 4 * TR.reeval_every_ticks)
    assert NODE not in w.capture and w.owner[NODE] == "NEUTRAL"
    assert ended(out, job) == ["JobExpired"]


@pytest.mark.parametrize(
    ("viewer", "floor", "kept"),
    [
        (False, True, False),  # the idle floor: the bar neither fills nor decays
        (True, True, True),  # a live viewer unit: the bar is live
        (False, False, True),  # `campaign.idle_floor.enabled` off: the bar is live
    ],
)
def test_the_idle_floor_on_the_forward_airbase_holds_nothing(
    viewer: bool, floor: bool, kept: bool
) -> None:
    """A Static bar on the coalition's forward airbase at no live viewer unit neither fills nor
    decays, so it would hold the job for good (`capture.stalled`)."""
    assert RULES.defense is not None and RULES.defense.forward_airbase == "west-airbase"
    w = new_world(rules=replace(RULES, defense=replace(RULES.defense, idle_floor=floor)))
    job, _ = static_capture(w, "west-airbase", "west-airbase")
    w.capture["west-airbase"] = CaptureBar("ENEMY", CAPTURE_FULL // 2)
    if viewer:
        put(w, "LOGI_TRUCK", "haven")  # a COMMANDER-owned unit
    assert w.viewer_units() == int(viewer)
    spent(w, job)
    out = board_pass(w)
    assert (job.id in w.boards["ENEMY"]) is kept
    assert ended(out, job) == ([] if kept else ["JobExpired"])


@pytest.mark.parametrize(
    ("lost", "node", "kept"),
    [
        (("west-airbase", "fob-s-w"), "fob-n-w", False),  # fob-n-w is its last base
        ((), "fob-n-w", True),  # other strategic nodes held: the bar is live
        (COALITION_START, NODE, True),  # it holds none, and the node is not its own
    ],
)
def test_the_coalitions_last_base_holds_nothing(
    lost: tuple[str, ...], node: str, kept: bool
) -> None:
    """Q-TD-103: on the only strategic node the coalition holds a Static bar under a Static
    capturer neither starts nor fills, so it would hold the job for good; with another strategic
    node held, or on a node the coalition does not hold, the bar is live and holds it."""
    w = scene(*lost)
    job, _ = static_capture(w, node, node)
    w.capture[node] = CaptureBar("ENEMY", CAPTURE_FULL // 2)
    spent(w, job)
    out = board_pass(w)
    assert (job.id in w.boards["ENEMY"]) is kept
    assert ended(out, job) == ([] if kept else ["JobExpired"])


def test_a_night_held_bar_holds_nothing() -> None:
    """A Static bar the night cap holds one step short of the flip (`DirectorState.held`) waits
    for a release that each Static flip elsewhere moves on, so its job expires as before NX-483.
    Nodes run in id order: `cross-n` flips first and stamps the cap, then `cross-s` stays held."""
    w = new_world()
    job, _ = static_capture(w, "cross-s", "cross-s")
    st = w.director["ENEMY"]
    w.capture["cross-s"] = CaptureBar("ENEMY", CAPTURE_FULL - 1)
    st.held["cross-s"] = w.campaign.running_ticks
    put(w, "ENEMY_ARMOR", NODE, owner="ENEMY_DIRECTOR")  # a Static capture elsewhere
    w.capture[NODE] = CaptureBar("ENEMY", CAPTURE_FULL - 1)
    assert st.last_flip == 0  # the cap is free for one flip
    spent(w, job)
    out = drive(w, "ENEMY", job, TR.reeval_every_ticks)
    assert w.owner[NODE] == "ENEMY" and st.last_flip > 0  # the flip elsewhere
    assert "cross-s" in st.held and w.owner["cross-s"] == "NEUTRAL"
    assert ended(out, job) == ["JobExpired"]


# --- determinism ---------------------------------------------------------------------------------


def _run(snapshot_at: int | None = None) -> tuple[str, list[str]]:
    w = new_world()
    job, _ = static_capture(w)
    events: list[Event] = []
    while w.capture.get(NODE) is None:
        events += step(w, [])
    spent(w, job)
    if snapshot_at is not None:
        for _ in range(snapshot_at):  # into the hold: past the due pass
            events += step(w, [])
        copy = load(save(w))
        copy.rules = w.rules
        assert state_hash(copy) == state_hash(w)
        w = copy
    events += drive(w, "ENEMY", job, 20 * TR.reeval_every_ticks)
    assert w.owner[NODE] == "ENEMY"
    return state_hash(w), [e.model_dump_json() for e in events]


def test_the_hold_is_deterministic_and_survives_save_and_load() -> None:
    first = _run()
    assert first == _run()
    assert _run(snapshot_at=TR.reeval_every_ticks + 1) == first
