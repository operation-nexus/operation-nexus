"""NX-466 (ECONOMY EC-9b, GAMEPLAY §9, Q-TD-84 (b), Q-TD-134): a running victory hold pauses under
the other side's pressure.

A node of the running hold is pressured when the Static has a capture bar on it (CAPTURE_BAR), it
is in `World.defense_down` (DEFENSES_DOWN), or a live, non-Disabled claimant of the Static's
CAPTURE job on it is within `tasking.defend_radius_m` (CAPTURE_OP). A pressured running tick gains
nothing and counts in `Campaign.hold_paused_ticks`; the start tick always gains 1. The switch comes
through the loader (`shipped_config`); the hold is shrunk to a few ticks only where a test needs a
short one. The Tasking Board is off (`run_tasking` is a no-op) so a hand-posted CAPTURE job and its
claim stay as posted; `tasking` stays in the rules because the radius is read from it.
"""

import dataclasses
from collections.abc import Iterator, Mapping
from typing import Any

import msgpack
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from test_campaign import CONFIG, cid, hold_seven, new_world, of, own, pause, resume, run
from test_victory_hold import SEVEN

import nexus.core.defense as defense
import nexus.core.step as step_mod
from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.victory_hold_broken import VictoryHoldBroken
from nexus.contracts.gen.events.victory_hold_paused import VictoryHoldPaused
from nexus.contracts.gen.events.victory_hold_resumed import VictoryHoldResumed
from nexus.contracts.gen.events.victory_hold_started import VictoryHoldStarted
from nexus.core.campaign import pressure
from nexus.core.fog import side_view
from nexus.core.rules import CAPTURE_FULL
from nexus.core.step import step
from nexus.core.world import CaptureBar, Claim, Entity, Job, Vec2, World, load, save, state_hash
from nexus.runtime.golden import shipped_config

HOLD = 500
NODE = "fob-s-w"  # a coalition start node: the CAPTURE_OP target
KINDS = (VictoryHoldStarted, VictoryHoldBroken, VictoryHoldPaused, VictoryHoldResumed)
assert CONFIG.rules.tasking is not None
REACH = CONFIG.rules.tasking.defend_radius_m  # 10 km at the shipped config
SWITCH = "campaign.victory.pause_on_pressure"


@pytest.fixture(autouse=True)
def _board_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(step_mod, "run_tasking", lambda world, out: None)


def pause_world(
    keys: Mapping[str, object] | None = None, *, hold: int = HOLD, **limits: Any
) -> World:
    """strait-1 whose campaign rules are the shipped ones with `keys` through the loader, the hold
    `hold` ticks long, every defense hp 0 (test_campaign's world) and the tasking rules in."""
    rc = shipped_config(keys or {}).rules.campaign
    assert rc is not None
    w = new_world(
        victory_hold_ticks=hold,
        hold_decay=rc.hold_decay,
        pause_on_pressure=rc.pause_on_pressure,
        **limits,
    )
    assert w.rules is not None
    w.rules = dataclasses.replace(w.rules, tasking=CONFIG.rules.tasking)
    return w


def started_hold(w: World, ticks: int = 3) -> VictoryHoldStarted:
    """Hold seven nodes; run `ticks` running ticks (the first emits `VictoryHoldStarted`)."""
    hold_seven(w)
    (started,) = of(run(w, ticks), VictoryHoldStarted)
    return started


def hold_events(events: list[Event]) -> list[Any]:
    return [e for e in events if isinstance(e, KINDS)]


def bar(w: World, node: str, side: Side = "ENEMY", progress: int = CAPTURE_FULL // 10) -> None:
    w.capture[node] = CaptureBar(side, progress)


def hp_max(w: World, node: str) -> int:
    assert w.rules is not None and w.rules.defense is not None
    return w.rules.defense.max_hp[node]


def knock_down(w: World, node: str) -> None:
    """A hit from full to 0: `NodeDefensesDown`, and the node enters `defense_down`."""
    assert w.rules is not None
    w.defense_hp[node] = hp_max(w, node)
    defense.damage(w, w.rules, node, hp_max(w, node), [])
    assert node in w.defense_down


def capture_job(
    w: World, claimant: Entity, node: str = NODE, key: str = "op:OFFENSIVE:fob-s-w:2"
) -> Job:
    """A Static CAPTURE job on `node` claimed by `claimant`, as an OFFENSIVE's capture step is."""
    job = Job(w.next_job_id(), "CAPTURE", key, 1, 1000, 0, node=node)
    job.claims[claimant.id] = Claim(0)
    w.boards["ENEMY"][job.id] = job
    return job


def enemy_at(w: World, node: str, dx: float, n: int = 1, side: Side = "ENEMY") -> Entity:
    """A ground unit `dx` metres east of `node`, past the capture radius (so it starts no bar)."""
    assert w.rules is not None
    x, y = w.rules.roads.pos[node]
    kind: UnitKind = "ENEMY_ARMOR" if side == "ENEMY" else "GARRISON_INFANTRY"
    return w.spawn(kind, side, "COMMANDER", Vec2(x + dx, y), commander_id=cid(n))


# --- pause and resume, one test per condition -----------------------------------------------------


def test_a_capture_bar_pauses_the_hold_and_it_resumes_when_the_bar_drains() -> None:
    w = pause_world()
    started = started_hold(w)
    assert (w.campaign.hold_ticks, w.campaign.hold_paused_ticks) == (3, 0)
    bar(w, "fob-s-e")
    (paused,) = of(run(w), VictoryHoldPaused)
    assert (paused.node_id, paused.reason, paused.progress_ticks) == ("fob-s-e", "CAPTURE_BAR", 3)
    assert w.campaign.hold_paused_ticks == 1  # the pause tick sets it to 1
    n = 1
    while True:  # the bar drains with no capturer: no event, no flip
        events = run(w)
        if "fob-s-e" not in w.capture:
            break  # drained on this tick: the first free one
        assert hold_events(events) == [] and w.campaign.hold_ticks == 3  # flat while the bar lives
        n += 1
        assert w.campaign.hold_paused_ticks == n
    (resumed,) = of(events, VictoryHoldResumed)
    assert (w.campaign.hold_ticks, w.campaign.hold_paused_ticks) == (4, 0)
    assert resumed.progress_ticks == 4
    assert resumed.ends_at_tick == w.campaign.running_ticks + HOLD - 4
    assert resumed.ends_at_tick == started.ends_at_tick + n  # later by exactly the paused ticks
    assert w.campaign.hold_broken_ticks == 0  # a pause is not a decay


@pytest.mark.parametrize("node", ["fob-s-e", "west-airbase"])
def test_a_night_held_bar_and_an_idle_floor_bar_pause_the_hold(node: str) -> None:
    """`fob-s-e`: a bar the night cap holds one step short of the flip (`DirectorState.held`).
    `west-airbase`: the forward airbase, whose bar the idle floor freezes at 0 viewer units."""
    w = pause_world()
    started_hold(w)
    assert w.viewer_units() == 0
    if node == "west-airbase":
        bar(w, node)
    else:
        bar(w, node, progress=CAPTURE_FULL - 1)
        w.director["ENEMY"].held[node] = w.campaign.running_ticks
    run(w, 60)  # the bar neither drains nor flips
    assert node in w.capture
    assert (w.campaign.hold_ticks, w.campaign.hold_paused_ticks) == (3, 60)


def test_defenses_down_pauses_until_the_node_is_rebuilt_to_full() -> None:
    w = pause_world()
    started_hold(w)
    assert w.rules is not None
    knock_down(w, "cross-n")
    (paused,) = of(run(w), VictoryHoldPaused)
    assert (paused.node_id, paused.reason) == ("cross-n", "DEFENSES_DOWN")
    defense.heal(w, w.rules, "cross-n", 1, [])  # 1 hp is not full: still down
    run(w, 5)
    assert (w.campaign.hold_ticks, w.campaign.hold_paused_ticks) == (3, 6)
    defense.heal(w, w.rules, "cross-n", hp_max(w, "cross-n"), [])  # NodeDefensesRestored
    assert "cross-n" not in w.defense_down
    (resumed,) = of(run(w), VictoryHoldResumed)
    assert resumed.progress_ticks == 4 and w.campaign.hold_paused_ticks == 0


def test_a_node_the_coalition_just_captured_at_0_hp_does_not_pause_the_hold() -> None:
    w = pause_world()
    started_hold(w)
    assert w.defense_hp["fob-s-e"] == 0 and "fob-s-e" not in w.defense_down  # hold_seven's flip
    assert hold_events(run(w, 5)) == [] and w.campaign.hold_ticks == 8


def test_a_starvation_drain_to_0_pauses_the_hold() -> None:
    w = pause_world()
    started_hold(w)
    assert w.rules is not None and w.rules.defense is not None
    node = "cross-s"
    w.defense_hp[node] = 1
    w.stock[node] = 0  # a finite-stock node below its floor loses hp each minute
    seen: list[VictoryHoldPaused] = []
    for _ in range(w.rules.defense.ticks_per_min * 3):
        seen += of(run(w), VictoryHoldPaused)
        if seen:
            break
    assert node in w.defense_down, "the drain never took the node to 0"
    assert [(p.node_id, p.reason) for p in seen] == [(node, "DEFENSES_DOWN")]


def test_a_capture_force_pauses_the_hold_at_the_defend_radius_and_not_a_metre_outside() -> None:
    w = pause_world()
    started_hold(w)
    unit = enemy_at(w, NODE, REACH + 1)
    capture_job(w, unit)  # its STRIKE step may still be open (TB-8): the claim exists from launch
    assert pressure(w, NODE, "COALITION") is None
    assert hold_events(run(w, 2)) == [] and w.campaign.hold_paused_ticks == 0
    unit.pos = Vec2(unit.pos.x - 1, unit.pos.y)  # exactly at the radius: <= counts
    assert pressure(w, NODE, "COALITION") == "CAPTURE_OP"
    (paused,) = of(run(w), VictoryHoldPaused)
    assert (paused.node_id, paused.reason) == (NODE, "CAPTURE_OP")


def test_the_capture_op_pause_ends_when_the_claimant_leaves_is_disabled_or_is_lost() -> None:
    for how in ("leaves", "disabled", "lost"):
        w = pause_world()
        started_hold(w)
        unit = enemy_at(w, NODE, REACH)
        job = capture_job(w, unit)
        (paused,) = of(run(w), VictoryHoldPaused)
        assert paused.reason == "CAPTURE_OP", how
        if how == "leaves":
            unit.pos = Vec2(unit.pos.x + 1, unit.pos.y)
        elif how == "disabled":
            unit.damage_state = "DISABLED"
        else:
            w.remove(unit.id)
            del job.claims[unit.id]
        (resumed,) = of(run(w), VictoryHoldResumed)
        assert resumed.progress_ticks == 4, how


def test_other_steps_staged_operations_and_the_coalition_s_own_units_do_not_pause_it() -> None:
    w = pause_world()
    started_hold(w)
    strike = enemy_at(w, NODE, 100, n=1)  # a claimant of the same operation's STRIKE job
    job = capture_job(w, strike, key="op:OFFENSIVE:fob-s-w:1")
    job.kind = "STRIKE"
    enemy_at(w, NODE, 100, n=2)  # a staged operation has no job, so no claim: just a unit
    mine = capture_job(w, enemy_at(w, NODE, 100, n=3, side="COALITION"))
    w.boards["COALITION"][mine.id] = w.boards["ENEMY"].pop(mine.id)  # not the Static's board
    assert pressure(w, NODE, "COALITION") is None
    assert hold_events(run(w, 3)) == []


# --- events, start tick, no victory, clock --------------------------------------------------------


def test_one_pause_event_names_the_lowest_pressured_node_and_the_first_reason() -> None:
    w = pause_world()
    started_hold(w)
    bar(w, "west-airbase")
    knock_down(w, "cross-s")  # the lowest id of the pressured nodes, DEFENSES_DOWN
    bar(w, "cross-s")  # a bar on it too: CAPTURE_BAR is first in the order
    (paused,) = of(run(w), VictoryHoldPaused)
    assert (paused.node_id, paused.reason) == ("cross-s", "CAPTURE_BAR")
    del w.capture["cross-s"]  # the node and the reason change mid-pause: nothing is emitted
    assert w.rules is not None
    defense.heal(w, w.rules, "cross-s", hp_max(w, "cross-s"), [])
    assert hold_events(run(w, 3)) == [] and w.campaign.hold_paused_ticks == 4
    del w.capture["west-airbase"]
    assert len(of(run(w), VictoryHoldResumed)) == 1  # one Resumed per pause
    assert hold_events(run(w, 3)) == [] and w.campaign.hold_paused_ticks == 0


def test_the_start_tick_gains_1_under_pressure_and_the_pause_comes_next_tick() -> None:
    w = pause_world()
    hold_seven(w)
    bar(w, "cross-n")
    events = run(w)
    (started,) = of(events, VictoryHoldStarted)
    assert of(events, VictoryHoldPaused) == [] and w.campaign.hold_ticks == 1
    assert started.ends_at_tick == 1 + HOLD - 1 and started.progress_ticks == 0
    (paused,) = of(run(w), VictoryHoldPaused)
    assert paused.progress_ticks == 1


def test_a_hold_resumed_from_decay_under_pressure_gains_1_and_pauses_next_tick() -> None:
    w = pause_world()
    started_hold(w, 6)
    own(w, "ENEMY", "fob-s-e")
    (broken,) = of(run(w), VictoryHoldBroken)
    assert broken.progress_ticks == 6
    own(w, "COALITION", "fob-s-e")
    bar(w, "cross-n")
    events = run(w)
    (restarted,) = of(events, VictoryHoldStarted)
    assert (restarted.progress_ticks, w.campaign.hold_ticks) == (6, 7)
    assert of(events, VictoryHoldPaused) == []
    assert len(of(run(w), VictoryHoldPaused)) == 1 and w.campaign.hold_ticks == 7


def test_no_victory_while_paused_and_the_first_free_tick_resumes_then_wins() -> None:
    w = pause_world(hold=10)
    started_hold(w, 9)  # progress 9 of 10
    bar(w, "cross-n", progress=CAPTURE_FULL - 1)
    w.director["ENEMY"].held["cross-n"] = 0
    assert of(run(w, 50), CampaignEnded) == [] and w.campaign.hold_ticks == 9
    del w.capture["cross-n"]
    events = run(w)
    kinds = [type(e) for e in events if isinstance(e, (VictoryHoldResumed, CampaignEnded))]
    assert kinds == [VictoryHoldResumed, CampaignEnded]
    ended = of(events, CampaignEnded)[0]
    assert (
        ended.result == "VICTORY"
        and of(events, VictoryHoldResumed)[0].ends_at_tick == ended.end_tick
    )


def test_an_hq_capture_during_a_pause_still_wins_at_once() -> None:
    w = pause_world()
    started_hold(w)
    bar(w, "cross-n")
    run(w, 2)
    assert w.rules is not None and w.rules.campaign is not None
    own(w, "COALITION", w.rules.campaign.enemy_hq)
    (ended,) = of(run(w), CampaignEnded)
    assert (ended.result, w.campaign.hold_paused_ticks) == ("VICTORY", 3)


def test_the_hold_and_the_clock_a_sim_pause_changes_nothing_and_the_campaign_clock_runs() -> None:
    w = pause_world(time_limit_ticks=40)
    started_hold(w)
    bar(w, "cross-n", progress=CAPTURE_FULL - 1)
    w.director["ENEMY"].held["cross-n"] = 0
    run(w, 2)
    before = (w.campaign.hold_ticks, w.campaign.hold_paused_ticks, w.campaign.running_ticks)
    events = step(w, [pause(w)])
    events += run(w, 5)
    assert hold_events(events) == []
    assert (w.campaign.hold_ticks, w.campaign.hold_paused_ticks, w.campaign.running_ticks) == before
    step(w, [resume(w)])
    assert w.campaign.hold_paused_ticks == before[1] + 1  # the pause goes on through a running tick
    ended = of(run(w, 40), CampaignEnded)  # the time limit runs through a hold pause
    assert [e.result for e in ended] == ["TIME_LIMIT"]


def test_a_paused_hold_stays_in_the_directors_view() -> None:
    w = pause_world()
    started_hold(w)
    bar(w, "cross-n")
    run(w, 3)
    assert w.campaign.hold_paused_ticks == 3
    assert side_view(w, "ENEMY").hold == frozenset(SEVEN) == frozenset(w.campaign.hold_nodes)


# --- with EC-9a -----------------------------------------------------------------------------------


@pytest.mark.parametrize("break_mode", ["decay", "reset"])
def test_a_break_during_a_pause_goes_to_ec9a_with_the_frozen_progress(break_mode: str) -> None:
    w = pause_world({"campaign.victory.hold_break": break_mode})
    started_hold(w, 5)
    bar(w, "cross-n")
    run(w, 4)
    assert (w.campaign.hold_ticks, w.campaign.hold_broken_ticks) == (
        5,
        0,
    )  # neither gains nor decays
    own(w, "ENEMY", "fob-s-e")  # the share falls below the fraction while paused
    events = run(w)
    (broken,) = of(events, VictoryHoldBroken)
    assert of(events, VictoryHoldResumed) == [] and w.campaign.hold_paused_ticks == 0
    assert broken.progress_ticks == (5 if break_mode == "decay" else 0)
    assert w.campaign.hold_ticks == broken.progress_ticks
    run(w, 2)
    assert w.campaign.hold_broken_ticks == (
        2 if break_mode == "decay" else 0
    )  # from the slow stage
    own(w, "COALITION", "fob-s-e")  # re-held: starts unpaused, even with the bar still there
    events = run(w)
    assert len(of(events, VictoryHoldStarted)) == 1 and of(events, VictoryHoldPaused) == []
    assert w.campaign.hold_paused_ticks == 0


# --- the switch is today --------------------------------------------------------------------------


def scripted(w: World, *, pressured: bool) -> list[dict[str, Any]]:
    """With `pressured`, all three conditions on hold nodes in turn, then a break: hold events."""
    started_hold(w, 1)
    events: list[Event] = []
    if pressured:
        bar(w, "cross-n")
    events += run(w, 3)
    if pressured:
        knock_down(w, "cross-s")
        capture_job(w, enemy_at(w, NODE, REACH))
    events += run(w, 3)
    w.capture.clear()
    w.defense_down.clear()
    own(w, "ENEMY", "fob-s-e")
    events += run(w, 2)
    # event_seq is left out: the injected `knock_down` spent one that the free run did not
    return [e.model_dump(exclude={"event_seq"}) for e in hold_events(events)]


def test_with_the_switch_off_the_hold_runs_as_before_nx_466() -> None:
    off = pause_world({SWITCH: False})
    assert off.rules is not None and off.rules.campaign is not None
    assert off.rules.campaign.pause_on_pressure is False  # through the loader
    free = pause_world()
    got, today = scripted(off, pressured=True), scripted(free, pressured=False)
    assert [e["kind"] for e in got] == ["VictoryHoldBroken"]  # no Paused, no Resumed
    assert got == today  # the same events, tick for tick, as a run with no pressure at all
    assert off.campaign.hold_paused_ticks == 0
    assert off.campaign.hold_ticks == free.campaign.hold_ticks == 7  # +1 per running tick, kept
    on = pause_world()  # and the same pressure with the switch on does pause it
    assert VictoryHoldPaused in {type(e) for e in scripted_all(on)}


def scripted_all(w: World) -> list[Event]:
    started_hold(w, 1)
    bar(w, "cross-n")
    return run(w, 3)


# --- the pressure check, by parity ----------------------------------------------------------------


def test_the_pressure_check_mirrors_for_an_enemy_held_node() -> None:
    w = pause_world()
    node = "fob-n-e"
    assert w.owner[node] == "ENEMY"
    assert pressure(w, node, "ENEMY") is None
    bar(w, node, "COALITION")
    assert pressure(w, node, "ENEMY") == "CAPTURE_BAR"
    assert pressure(w, node, "COALITION") is None  # a bar of its own side is not pressure
    del w.capture[node]
    knock_down(w, node)
    assert pressure(w, node, "ENEMY") == "DEFENSES_DOWN"
    w.defense_down.clear()
    unit = enemy_at(w, node, REACH, side="COALITION")
    job = capture_job(w, unit, node, key=f"retake:{node}")
    w.boards["COALITION"][job.id] = w.boards["ENEMY"].pop(job.id)  # the coalition's retake job
    assert pressure(w, node, "ENEMY") == "CAPTURE_OP"
    assert pressure(w, node, "COALITION") is None


# --- determinism, snapshots ----------------------------------------------------------------------


def script(w: World) -> Iterator[list[Event]]:
    """A pause, a resume, a break during a pause and a re-hold."""
    hold_seven(w)
    yield run(w, 3)
    bar(w, "cross-n")
    yield run(w, 4)
    del w.capture["cross-n"]
    yield run(w, 2)
    knock_down(w, "cross-s")
    yield run(w, 2)
    own(w, "ENEMY", "fob-s-e")
    yield run(w, 3)
    own(w, "COALITION", "fob-s-e")
    yield run(w, 3)


def test_a_run_with_a_pause_a_resume_a_break_and_a_re_hold_is_deterministic() -> None:
    def once() -> tuple[str, list[Event]]:
        w = pause_world()
        events = [e for batch in script(w) for e in batch]
        return state_hash(w), events

    (h1, e1), (h2, e2) = once(), once()
    assert h1 == h2 and e1 == e2
    kinds = [type(e).__name__ for e in e1 if isinstance(e, KINDS)]
    assert kinds == [
        "VictoryHoldStarted", "VictoryHoldPaused", "VictoryHoldResumed", "VictoryHoldPaused",
        "VictoryHoldBroken", "VictoryHoldStarted", "VictoryHoldPaused",
    ]  # fmt: skip


def test_a_snapshot_taken_mid_pause_round_trips_to_the_same_run() -> None:
    w = pause_world()
    started_hold(w)
    bar(w, "cross-n", progress=CAPTURE_FULL - 1)
    w.director["ENEMY"].held["cross-n"] = w.campaign.running_ticks
    run(w, 4)
    assert w.campaign.hold_paused_ticks == 4
    copy = load(save(w))
    copy.rules = w.rules  # a snapshot holds no rules (SC-9)
    assert copy.campaign.hold_paused_ticks == 4 and state_hash(copy) == state_hash(w)
    for world in (w, copy):
        del world.capture["cross-n"]
        world.director["ENEMY"].held.clear()
    assert run(w, 3) == run(copy, 3)
    assert state_hash(w) == state_hash(copy)
    assert of(run(w), VictoryHoldPaused) == []  # the resume is behind both


def test_bad_hold_paused_ticks_and_old_formats_are_refused() -> None:
    w = pause_world()
    started_hold(w)
    bar(w, "cross-n")
    run(w, 2)
    raw = msgpack.unpackb(save(w), raw=False)

    def refuse(change: dict[str, Any], match: str, top: dict[str, Any] | None = None) -> None:
        bad = {**raw, **(top or {}), "campaign": {**raw["campaign"], **change}}
        with pytest.raises(ValueError, match=match):
            load(msgpack.packb(bad, use_bin_type=True))

    refuse({"hold_paused_ticks": -1}, "hold_paused_ticks")
    refuse({"hold_paused_ticks": True}, "hold_paused_ticks")
    refuse({"hold_paused_ticks": 10_000}, "campaign")  # more than the clock ran
    no_hold = {"hold_paused_ticks": 2, "hold_nodes": [], "hold_ticks": 0}
    refuse(no_hold, "campaign")  # paused with no running hold
    decaying = {"hold_nodes": [], "hold_broken_nodes": list(SEVEN[1:]), "hold_broken_ticks": 1}
    refuse(decaying, "campaign")  # paused while decaying
    refuse({}, "unsupported snapshot format", {"v": 37})


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.booleans(), min_size=1, max_size=25))
def test_progress_counts_exactly_the_unpressured_ticks(pressured: list[bool]) -> None:
    """After the start tick, each tick gains 1 unpressured and counts as paused when pressured;
    Paused and Resumed alternate, starting with Paused."""
    w = pause_world()
    hold_seven(w)
    run(w)  # the start tick: progress 1
    events: list[Event] = []
    for p in pressured:
        if p:
            bar(w, "cross-n")
        else:
            w.capture.pop("cross-n", None)
        events += run(w)
        assert w.campaign.hold_ticks + w.campaign.hold_paused_ticks <= w.campaign.running_ticks
    assert w.campaign.hold_ticks == 1 + pressured.count(False)
    pauses = [type(e) for e in events if isinstance(e, (VictoryHoldPaused, VictoryHoldResumed))]
    assert pauses == [VictoryHoldPaused, VictoryHoldResumed] * (len(pauses) // 2) + (
        [VictoryHoldPaused] if len(pauses) % 2 else []
    )
    assert bool(w.campaign.hold_paused_ticks) == bool(pauses and pauses[-1] is VictoryHoldPaused)
