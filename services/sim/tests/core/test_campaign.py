"""NX-126: the campaign clock, staff pause/resume/end, victory, the time limit, timed objectives and
momentum (GAMEPLAY §9; STATE-MACHINES §4.4 C-1..C-5, §4.5 O-1, O-2; SIM-CORE SC-11, SC-13, SC-15;
Q-SIM-60, Q-SIM-61, Q-SIM-62).

Shipped strait-1 numbers: eight strategic nodes: west-airbase, fob-n-w and fob-s-w (coalition),
cross-n and cross-s (neutral), fob-n-e, fob-s-e and east-airbase (enemy). Eighty percent of eight
is 6.4, so seven are needed. Tests that need a short campaign shrink the tick limits in the
campaign rules; one test reads the shipped conversions.
"""

import dataclasses
import itertools
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_join import join

import nexus.core.world as world_mod
from nexus.contracts.gen.commands.staff_campaign_end import StaffCampaignEndCommand
from nexus.contracts.gen.commands.staff_campaign_pause import StaffCampaignPauseCommand
from nexus.contracts.gen.commands.staff_campaign_resume import StaffCampaignResumeCommand
from nexus.contracts.gen.common.enums import NodeOwner, Side, UnitKind
from nexus.contracts.gen.events.campaign_clock_paused import CampaignClockPaused
from nexus.contracts.gen.events.campaign_clock_resumed import CampaignClockResumed
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.objective_announced import ObjectiveAnnounced
from nexus.contracts.gen.events.objective_resolved import ObjectiveResolved
from nexus.core.campaign import Momentum, momentum
from nexus.core.step import step
from nexus.core.world import Campaign, Entity, Objective, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config, start_campaign

CONFIG = load_campaign_config()
RULES = dataclasses.replace(CONFIG.rules, tasking=None)  # NX-374: board off
assert RULES.campaign is not None
RC = RULES.campaign
POS = RULES.roads.pos
CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
STAFF = {"staff_id": "0192f0c1-7a2b-7c3d-8e4f-0000000000a1"}
SEQ = itertools.count(1)
COALITION_NODES = ("west-airbase", "fob-n-w", "fob-s-w")
NEUTRAL_NODES = ("cross-n", "cross-s")
ENEMY_NODES = ("fob-n-e", "fob-s-e", "east-airbase")
FRONTLINE = {"fob-n-w", "fob-s-w", "cross-n", "cross-s", "fob-n-e", "fob-s-e", "east-airbase"}
INFANTRY: UnitKind = "GARRISON_INFANTRY"


def cid(n: int) -> str:
    return f"0192f0c1-7a2b-7c3d-8e4f-{n:012d}"


def new_world(*, objectives: bool = False, seed: int = 12345, **limits: Any) -> World:
    """strait-1 at tick 0; `limits` shrink the campaign rules (`time_limit_ticks`, ...)."""
    rc = dataclasses.replace(RC, objectives_on=objectives, **limits)
    rules = dataclasses.replace(RULES, campaign=rc)
    w = start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(CONFIG, rules=rules))
    w.defense_hp = dict.fromkeys(w.defense_hp, 0)  # these tests are not about defense HP
    return w


def header(w: World, kind: str, source: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "source": source,
        "issuer": STAFF if source == "STAFF" else {"system": "watchdog"},
        "target_tick": w.campaign.tick + 1,
        "arrival_seq": next(SEQ),
        "correlation_id": "t",
    }


def pause(
    w: World,
    category: str = "STAFF",
    *,
    sub: str | None = None,
    note: str | None = "raid on chat",
    source: str = "STAFF",
) -> StaffCampaignPauseCommand:
    payload = {"reason_category": category, "sub_reason": sub, "note": note}
    return StaffCampaignPauseCommand.model_validate(
        header(w, "STAFF_CAMPAIGN_PAUSE", source) | payload
    )


def resume(w: World, source: str = "STAFF") -> StaffCampaignResumeCommand:
    return StaffCampaignResumeCommand.model_validate(
        header(w, "STAFF_CAMPAIGN_RESUME", source) | {"note": None}
    )


def end(w: World) -> StaffCampaignEndCommand:
    return StaffCampaignEndCommand.model_validate(
        header(w, "STAFF_CAMPAIGN_END", "STAFF") | {"reason": "owner called it"}
    )


def run(w: World, ticks: int = 1) -> list[Event]:
    events: list[Event] = []
    for _ in range(ticks):
        events += step(w, [])
    return events


def of[T: Event](events: list[Event], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


def own(w: World, side: NodeOwner, *nodes: str) -> None:
    for node in nodes:
        w.owner[node] = side


def hold_seven(w: World) -> None:
    own(w, "COALITION", *COALITION_NODES, *NEUTRAL_NODES, "fob-n-e", "fob-s-e")


def put(w: World, node: str, n: int, side: Side = "COALITION", dx: float = 0.0) -> Entity:
    """A commander's ground unit at `node` (`dx` metres east); the commander is number `n`."""
    kind: UnitKind = INFANTRY if side == "COALITION" else "ENEMY_ARMOR"
    e = w.spawn(kind, side, "COMMANDER", Vec2(POS[node][0] + dx, POS[node][1]), commander_id=cid(n))
    e.last_node = node
    return e


# --- the clock and the staff commands -------------------------------------------------------


def test_the_clock_counts_only_running_ticks() -> None:
    w = new_world()
    run(w, 5)
    step(w, [pause(w)])  # applied on tick 6, before the systems: that tick does not run
    assert (w.campaign.tick, w.campaign.running_ticks) == (6, 5)
    run(w, 6)
    assert (w.campaign.tick, w.campaign.running_ticks) == (12, 5)  # C-1
    step(w, [resume(w)])  # the resume tick runs
    run(w, 2)
    assert (w.campaign.tick, w.campaign.running_ticks) == (15, 8)


def test_pause_and_resume_events_carry_the_reason_and_the_note_stays_out() -> None:
    w = new_world()
    (paused,) = of(step(w, [pause(w, sub="RAID")]), CampaignClockPaused)
    assert (paused.reason, paused.sub_reason, paused.tick) == ("STAFF", "RAID", 1)
    assert w.campaign.clock_paused and (w.campaign.pause_reason, w.campaign.pause_sub_reason) == (
        "STAFF",
        "RAID",
    )
    assert "raid on chat" not in str(paused.model_dump())
    (resumed,) = of(step(w, [resume(w)]), CampaignClockResumed)
    assert (resumed.reason, resumed.sub_reason) == ("STAFF", "RAID")  # those of the pause it ends
    assert (w.campaign.clock_paused, w.campaign.pause_reason, w.campaign.pause_sub_reason) == (
        False,
        None,
        None,
    )


def rejects(events: list[Event]) -> list[str]:
    return [e.reason for e in of(events, CommandRejected)]


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"category": "TECHNICAL", "sub": "RAID", "source": "SYSTEM"}, "INVALID_PAYLOAD"),
        ({"category": "CEASEFIRE", "sub": "OTHER"}, "INVALID_PAYLOAD"),
        ({"note": None}, "REASON_REQUIRED"),
        ({"note": "   "}, "REASON_REQUIRED"),
        ({"note": ""}, "REASON_REQUIRED"),
    ],
)
def test_pause_payload_validation(kwargs: dict[str, Any], reason: str) -> None:
    w = new_world()
    events = step(w, [pause(w, **kwargs)])
    assert rejects(events) == [reason] and not w.campaign.clock_paused


def test_a_system_pause_needs_no_note_and_a_staff_pause_may_have_no_sub_reason() -> None:
    w = new_world()
    step(w, [pause(w, "TECHNICAL", note=None, source="SYSTEM")])
    assert (w.campaign.clock_paused, w.campaign.pause_reason) == (True, "TECHNICAL")
    w = new_world()
    step(w, [pause(w)])
    assert (w.campaign.pause_reason, w.campaign.pause_sub_reason) == ("STAFF", None)


def test_pausing_while_paused_is_rejected_and_keeps_the_first_reason() -> None:
    w = new_world()
    step(w, [pause(w, sub="ABUSE")])
    events = step(w, [pause(w, "MAINTENANCE", note=None, source="SYSTEM")])
    assert rejects(events) == ["ALREADY_PAUSED"]
    assert (w.campaign.pause_reason, w.campaign.pause_sub_reason) == ("STAFF", "ABUSE")


def test_resuming_a_running_campaign_is_rejected() -> None:
    w = new_world()
    assert rejects(step(w, [resume(w)])) == ["NOT_PAUSED"]


def test_commands_in_one_tick_apply_in_arrival_order() -> None:
    w = new_world()
    events = step(w, [resume(w), pause(w), pause(w), resume(w)])
    assert [type(e).__name__ for e in events] == [
        "CommandRejected",  # NOT_PAUSED
        "CampaignClockPaused",
        "CommandRejected",  # ALREADY_PAUSED
        "CampaignClockResumed",
    ]
    assert rejects(events) == ["NOT_PAUSED", "ALREADY_PAUSED"]


def test_a_paused_world_rejects_a_join_from_a_commander_with_a_unit() -> None:
    """The SC-11 chat rules are untouched: only the staff commands changed."""
    w = new_world()
    put(w, "west-airbase", 1)
    step(w, [pause(w)])
    assert rejects(step(w, [join(1, "LOGI", "fob-n-w", target_tick=2)])) == ["CAMPAIGN_PAUSED"]


def test_end_aborts_freezes_the_world_and_rejects_every_later_command() -> None:
    w = new_world()
    mover = put(w, "west-airbase", 1)
    mover.path = ["fob-n-w"]  # to prove the world is frozen
    run(w, 3)
    (ended,) = of(step(w, [end(w), pause(w), end(w)]), CampaignEnded)  # later ones: C-3
    assert (ended.result, ended.winner, ended.end_tick, w.campaign.ended) == (
        "ABORTED",
        None,
        4,
        True,
    )
    at_end, running = mover.pos, w.campaign.running_ticks
    assert run(w, 20) == [] and w.campaign.tick == 24
    assert (mover.pos, w.campaign.running_ticks) == (at_end, running)  # only the tick moved
    assert rejects(step(w, [end(w), resume(w)])) == ["CAMPAIGN_NOT_RUNNING"] * 2


def test_the_commands_after_the_end_in_the_same_tick_are_rejected_not_applied() -> None:
    w = new_world()
    events = step(w, [end(w), pause(w)])
    assert [type(e).__name__ for e in events] == ["CampaignEnded", "CommandRejected"]
    assert rejects(events) == ["CAMPAIGN_NOT_RUNNING"] and not w.campaign.clock_paused


def test_a_paused_campaign_can_be_ended() -> None:
    w = new_world()
    step(w, [pause(w)])
    (ended,) = of(step(w, [end(w)]), CampaignEnded)
    assert ended.result == "ABORTED"


def test_an_ended_world_stops_every_time_driven_system() -> None:
    w = new_world()
    put(w, "cross-n", 1)
    step(w, [end(w)])
    run(w, 5)
    assert w.capture == {} and w.campaign.running_ticks == 0  # no bar started


# --- victory ----------------------------------------------------------------------------------


def test_holding_the_victory_share_for_the_hold_time_wins() -> None:
    w = new_world(victory_hold_ticks=5)
    hold_seven(w)
    assert of(run(w, 4), CampaignEnded) == [] and w.campaign.hold_ticks == 4
    (ended,) = of(run(w), CampaignEnded)
    assert (ended.result, ended.winner, ended.end_tick) == ("VICTORY", "COALITION", 5)
    assert ended.nodes_held_pct == 88  # 7 of 8, 87.5 rounded half up
    assert (ended.score.coalition, ended.score.enemy) == (87.5, 12.5)  # 100 x 35/40, 100 x 5/40
    assert run(w, 5) == []


def test_a_dip_below_the_share_resets_the_hold() -> None:
    w = new_world(victory_hold_ticks=5)
    hold_seven(w)
    run(w, 3)
    own(w, "ENEMY", "fob-s-e")  # 6 of 8 = 75 %: below 80 %
    run(w)
    assert w.campaign.hold_ticks == 0
    own(w, "COALITION", "fob-s-e")
    assert of(run(w, 4), CampaignEnded) == []  # four ticks of a new run
    assert len(of(run(w), CampaignEnded)) == 1


def test_only_strategic_nodes_count_toward_the_share() -> None:
    w = new_world(victory_hold_ticks=3)
    own(w, "COALITION", *COALITION_NODES, *NEUTRAL_NODES, "fob-n-e")  # 6 of 8
    own(w, "COALITION", "bridge-n", "bridge-s", "static-rear")  # not strategic; not the HQ
    assert of(run(w, 10), CampaignEnded) == []
    own(w, "COALITION", "fob-s-e")  # now 7
    assert len(of(run(w, 3), CampaignEnded)) == 1


def test_the_enemy_holding_the_nodes_is_not_a_coalition_loss() -> None:
    w = new_world(victory_hold_ticks=3)
    own(w, "ENEMY", *COALITION_NODES, *NEUTRAL_NODES, "fob-n-e", "fob-s-e", "east-airbase")
    assert of(run(w, 10), CampaignEnded) == [] and not w.campaign.ended


def test_capturing_the_enemy_hq_wins() -> None:
    w = new_world()
    put(w, "static-hq", 1)
    events: list[Event] = []
    while not w.campaign.ended and w.campaign.tick < 200:
        events += run(w)
    (flip,) = of(events, NodeCaptured)
    (ended,) = of(events, CampaignEnded)
    assert (flip.node_id, flip.participant_commander_ids) == ("static-hq", [cid(1)])
    assert (ended.result, ended.winner, ended.tick) == ("VICTORY", "COALITION", flip.tick)
    assert events.index(flip) < events.index(ended)  # the flip, then the end, in one tick
    assert ended.nodes_held_pct == 38  # 3 of 8, 37.5 half up


# --- the time limit ---------------------------------------------------------------------------


def test_the_time_limit_scores_the_average_node_share_exactly() -> None:
    w = new_world(time_limit_ticks=20)
    assert of(run(w, 19), CampaignEnded) == []  # C-5: not before the limit
    (ended,) = of(run(w), CampaignEnded)
    # 3 nodes of 8 each side all along: 50 x 60/160 + 50 x 3/8 = 37.5 each, an exact tie.
    assert (ended.result, ended.winner, ended.end_tick) == ("TIME_LIMIT", None, 20)
    assert (ended.score.coalition, ended.score.enemy) == (37.5, 37.5)


@pytest.mark.parametrize(("flip", "winner"), [("COALITION", "COALITION"), ("ENEMY", "ENEMY")])
def test_the_higher_score_wins_the_time_limit(flip: NodeOwner, winner: Side) -> None:
    w = new_world(time_limit_ticks=20)
    own(w, flip, "cross-n")
    (ended,) = of(run(w, 20), CampaignEnded)
    assert (ended.winner, ended.score.coalition > ended.score.enemy) == (
        winner,
        flip == "COALITION",
    )
    assert max(ended.score.coalition, ended.score.enemy) == 50.0  # 50 x 80/160 + 50 x 4/8
    assert ended.result == "TIME_LIMIT"  # the Static wins only here (Q-SIM-64)


def test_the_final_share_can_swing_a_side_that_trailed_on_average() -> None:
    w = new_world(time_limit_ticks=20)
    own(w, "ENEMY", *NEUTRAL_NODES)
    assert of(run(w, 16), CampaignEnded) == []  # coalition 3 nodes, enemy 5
    own(w, "COALITION", *NEUTRAL_NODES, "fob-n-e", "fob-s-e")  # coalition 7, enemy 1 for 4 ticks
    (ended,) = of(run(w, 4), CampaignEnded)
    # sums 48 + 28 = 76 and 80 + 4 = 84 of 160: averages 0.475 and 0.525; finals 7/8 and 1/8
    assert (ended.score.coalition, ended.score.enemy) == (67.5, 32.5)  # 23.75 + 43.75, 26.25 + 6.25
    assert ended.winner == "COALITION"


def test_a_static_lead_at_the_limit_is_a_time_limit_win_for_the_enemy() -> None:
    w = new_world(time_limit_ticks=20)
    own(w, "ENEMY", *NEUTRAL_NODES, "fob-s-w")  # 6 of 8 all along: below the victory share anyway
    (ended,) = of(run(w, 20), CampaignEnded)
    assert (ended.result, ended.winner) == ("TIME_LIMIT", "ENEMY")
    assert (ended.score.coalition, ended.score.enemy) == (25.0, 75.0)


def test_objective_points_join_the_score_and_a_tie_is_exact() -> None:
    w = new_world(time_limit_ticks=20)
    c = w.campaign
    c.running_ticks, c.tick = 19, 19
    c.held_ticks_coalition, c.held_ticks_enemy = 49, 65  # this tick adds 3 each: 52 and 68
    # 50 x 52/160 + 50 x 3/8 + 5 = 40 = 50 x 68/160 + 50 x 3/8
    c.objectives_issued = c.objectives_done = 1
    (ended,) = of(run(w), CampaignEnded)
    assert (ended.winner, ended.score.coalition, ended.score.enemy) == (None, 40.0, 40.0)


def test_a_pause_does_not_advance_the_time_limit() -> None:
    w = new_world(time_limit_ticks=10)
    run(w, 4)
    step(w, [pause(w)])
    assert of(run(w, 100), CampaignEnded) == []
    step(w, [resume(w)])
    assert of(run(w, 4), CampaignEnded) == []  # running ticks 5..9
    assert len(of(run(w), CampaignEnded)) == 1


def test_victory_comes_before_the_time_limit_on_the_same_tick() -> None:
    w = new_world(time_limit_ticks=5, victory_hold_ticks=5)
    hold_seven(w)
    (ended,) = of(run(w, 5), CampaignEnded)
    assert ended.result == "VICTORY"


def test_shipped_campaign_rules_in_ticks_and_nodes() -> None:
    assert (RC.time_limit_ticks, RC.victory_hold_ticks, RC.objective_period_ticks) == (
        2_592_000,  # 72 h x 3600 s x 10 Hz
        18_000,  # 30 min
        9_000,  # 15 min
    )
    assert RC.strategic == (*sorted((*COALITION_NODES, *NEUTRAL_NODES, *ENEMY_NODES)),)
    # never the sanctuaries, the bridges or the Static's HQ (Q-SM-11, Q-SIM-58)
    assert not {"haven", "static-rear", "bridge-n", "bridge-s", "static-hq"} & set(RC.candidates)
    assert RC.enemy_hq == "static-hq" and RC.objectives_on


# --- timed objectives -------------------------------------------------------------------------


def test_the_first_objective_is_announced_on_the_first_running_tick() -> None:
    w = new_world(objectives=True)
    (a,) = of(run(w), ObjectiveAnnounced)
    assert (a.objective_id, a.tick, a.deadline_tick) == (1, 1, 1 + RC.objective_period_ticks)
    assert w.objective == Objective(1, a.node_id, a.deadline_tick, a.node_id in COALITION_NODES)
    assert a.node_id in FRONTLINE


def test_the_pick_is_uniform_over_the_frontline_and_deterministic() -> None:
    picks = []
    for seed in range(100):
        (a,) = of(run(new_world(objectives=True, seed=seed)), ObjectiveAnnounced)
        picks.append(a.node_id)
        again = of(run(new_world(objectives=True, seed=seed)), ObjectiveAnnounced)
        assert [e.model_dump() for e in again] == [a.model_dump()]
    # west-airbase has only coalition neighbours; the sanctuaries, bridges and HQ are never picked
    assert set(picks) == FRONTLINE


def test_a_pick_draws_only_from_the_objective_stream() -> None:
    w = new_world(objectives=True)
    before = w.rng.to_state()
    run(w)
    after = w.rng.to_state()
    assert [k for k in before if before[k] != after[k]] == ["objective"]


def test_a_hold_objective_is_a_coalition_node_and_a_capture_any_other() -> None:
    kinds = {}
    for seed in range(60):
        w = new_world(objectives=True, seed=seed)
        run(w)
        assert w.objective is not None
        kinds[w.objective.node_id] = w.objective.hold
    assert kinds == {n: n in COALITION_NODES for n in FRONTLINE}


def test_with_no_frontline_nothing_is_announced_and_nothing_is_drawn() -> None:
    w = new_world(objectives=True)
    own(w, "ENEMY", *RC.candidates, "haven")  # a coalition sanctuary beside a node is a frontline
    before = w.rng.to_state()
    assert of(run(w, 5), ObjectiveAnnounced) == [] and w.rng.to_state() == before
    own(w, "COALITION", "fob-n-w")  # a frontline again: announced on the next tick
    assert len(of(run(w), ObjectiveAnnounced)) == 1


def test_off_mode_has_no_objectives_and_draws_nothing() -> None:
    w = new_world(objectives=False)
    before = w.rng.to_state()
    assert [e for e in run(w, 50) if "Objective" in type(e).__name__] == []
    assert w.objective is None and w.rng.to_state() == before


def active(w: World, node: str, *, hold: bool, deadline: int = 50) -> None:
    """Make `node` the active objective, as an announcement would."""
    w.campaign.objectives_issued = 1
    w.objective = Objective(1, node, deadline, hold)


def test_a_capture_objective_completes_when_the_coalition_captures_the_node() -> None:
    w = new_world(objectives=True, objective_period_ticks=9000)
    active(w, "cross-n", hold=False, deadline=1000)
    put(w, "cross-n", 7)
    events: list[Event] = []
    while w.objective is not None and w.objective.id == 1 and w.campaign.tick < 300:
        events += run(w)
    (flip,) = of(events, NodeCaptured)
    (done,) = of(events, ObjectiveResolved)
    assert (done.objective_id, done.outcome, done.tick) == (1, "COMPLETED", flip.tick)
    assert done.participant_commander_ids == flip.participant_commander_ids == [cid(7)]
    assert w.campaign.objectives_done == 1
    (nxt,) = of(events, ObjectiveAnnounced)  # O-1: the next one in the tick this one resolved
    assert (nxt.objective_id, nxt.tick) == (2, done.tick)
    assert events.index(done) < events.index(nxt)


def test_an_enemy_capture_does_not_complete_a_capture_objective() -> None:
    w = new_world(objectives=True)
    active(w, "cross-n", hold=False, deadline=1000)
    put(w, "cross-n", 7, "ENEMY")
    events = run(w, 300)
    assert of(events, NodeCaptured) and of(events, ObjectiveResolved) == []
    assert w.objective is not None and w.objective.id == 1


def test_an_uncaptured_objective_expires_at_the_deadline_and_the_next_follows() -> None:
    w = new_world(objectives=True, objective_period_ticks=9000)
    active(w, "cross-n", hold=False, deadline=5)
    assert of(run(w, 4), ObjectiveResolved) == []
    events = run(w)
    (done,) = of(events, ObjectiveResolved)
    assert (done.outcome, done.participant_commander_ids, done.tick) == ("EXPIRED", [], 5)
    assert w.campaign.objectives_done == 0
    (nxt,) = of(events, ObjectiveAnnounced)
    assert (nxt.objective_id, nxt.deadline_tick) == (2, 5 + 9000)


def test_a_hold_objective_completes_only_if_held_when_the_timer_ends() -> None:
    w = new_world(objectives=True)
    active(w, "fob-n-w", hold=True, deadline=5)
    put(w, "fob-n-w", 3)
    put(w, "fob-n-w", 1, dx=2000.0)  # the edge of capture.radius_m counts
    put(w, "fob-n-w", 2, dx=2001.0)  # outside
    put(w, "fob-n-w", 4, "ENEMY")  # the other side
    assert of(run(w, 4), ObjectiveResolved) == []
    (done,) = of(run(w), ObjectiveResolved)
    assert (done.outcome, done.participant_commander_ids) == ("COMPLETED", [cid(1), cid(3)])
    assert w.campaign.objectives_done == 1


def test_losing_a_hold_objective_mid_period_is_not_an_instant_fail() -> None:
    w = new_world(objectives=True)
    active(w, "fob-n-w", hold=True, deadline=8)
    run(w, 2)
    own(w, "ENEMY", "fob-n-w")
    assert of(run(w, 3), ObjectiveResolved) == []  # still active while lost (Q-SIM-61)
    own(w, "COALITION", "fob-n-w")  # retaken before the timer ends
    (done,) = of(run(w, 3), ObjectiveResolved)
    assert (done.objective_id, done.outcome, done.tick) == (1, "COMPLETED", 8)


def test_a_hold_objective_lost_at_the_deadline_expires() -> None:
    w = new_world(objectives=True)
    active(w, "fob-n-w", hold=True, deadline=4)
    own(w, "ENEMY", "fob-n-w")
    (done,) = of(run(w, 4), ObjectiveResolved)
    assert (done.outcome, w.campaign.objectives_done) == ("EXPIRED", 0)


def test_the_objective_timer_is_frozen_while_paused() -> None:
    w = new_world(objectives=True)
    active(w, "cross-n", hold=False, deadline=5)
    run(w, 2)
    step(w, [pause(w)])
    assert [e for e in run(w, 100) if "Objective" in type(e).__name__] == []  # O-2
    step(w, [resume(w)])
    assert of(run(w, 1), ObjectiveResolved) == []  # running tick 4
    assert len(of(run(w, 1), ObjectiveResolved)) == 1  # running tick 5


def test_the_objective_is_resolved_before_the_end_check_scores_it() -> None:
    w = new_world(objectives=True, time_limit_ticks=5)
    active(w, "fob-n-w", hold=True, deadline=5)
    events = run(w, 5)
    kinds = [
        type(e).__name__
        for e in events
        if "Objective" in type(e).__name__ or "Ended" in type(e).__name__
    ]
    ended = of(events, CampaignEnded)[0]
    assert kinds[-2:] == ["ObjectiveResolved", "CampaignEnded"]
    assert ended.score.coalition == 100 * 15 / 40 + 5  # 3 of 8 nodes for 5 ticks, one objective


def test_ending_a_world_with_no_campaign_rules_scores_zero_and_does_not_raise() -> None:
    for rules in (None, dataclasses.replace(RULES, campaign=None)):
        w = World.new(Campaign(CAMPAIGN_ID, 1, "cfg-test"), rules)
        (ended,) = of(step(w, [end(w)]), CampaignEnded)
        assert (ended.result, ended.winner, ended.nodes_held_pct) == ("ABORTED", None, 0)
        assert (ended.score.coalition, ended.score.enemy) == (0.0, 0.0) and w.campaign.ended


def test_an_end_expires_the_active_objective_first() -> None:
    w = new_world(objectives=True)
    active(w, "cross-n", hold=False, deadline=1000)
    events = step(w, [end(w)])
    assert [type(e).__name__ for e in events] == ["ObjectiveResolved", "CampaignEnded"]
    (done,) = of(events, ObjectiveResolved)
    assert (done.outcome, done.participant_commander_ids) == ("EXPIRED", [])
    assert w.objective is None and w.campaign.objectives_done == 0


def test_a_victory_leaves_no_active_objective_either() -> None:
    w = new_world(objectives=True, victory_hold_ticks=3)
    hold_seven(w)
    active(w, "cross-n", hold=False, deadline=1000)  # owned by the coalition: never "captured"
    events = run(w, 3)
    kinds = [type(e).__name__ for e in events if type(e) in (ObjectiveResolved, CampaignEnded)]
    assert kinds == ["ObjectiveResolved", "CampaignEnded"] and w.objective is None
    assert of(events, ObjectiveResolved)[0].outcome == "EXPIRED"


# --- momentum ---------------------------------------------------------------------------------


def test_momentum_at_the_start() -> None:
    w = new_world()
    # nodes 3/8 = 37.5 %; coalition bases hold 1000+500+500 of 2000+1000+1000 = 50 %:
    # 70 x 0.375 + 30 x 0.5 = 41.25
    assert momentum(w) == Momentum(41, 38, 50)


def test_momentum_follows_stock_and_ownership_and_rounds_halves_up() -> None:
    w = new_world()
    w.stock = {n: 0 for n in w.stock}
    assert momentum(w) == Momentum(26, 38, 0)  # 26.25
    own(w, "ENEMY", *COALITION_NODES)
    assert momentum(w) == Momentum(0, 0, 0)  # no strategic node and no finite base: supply is 0
    own(w, "COALITION", "fob-n-w")  # 1 of 8 = 12.5 %: half up is 13, not half-even 12
    w.stock["fob-n-w"] = 500  # half of its 1000
    assert momentum(w) == Momentum(24, 13, 50)  # 70 x 0.125 + 30 x 0.5 = 23.75


def test_momentum_is_clamped_and_uses_the_weights_in_the_rules() -> None:
    w = new_world()
    own(w, "COALITION", *RC.strategic)
    heavy = dataclasses.replace(
        RULES, campaign=dataclasses.replace(RC, nodes_weight=RC.nodes_weight * 2)
    )
    w.rules = heavy
    assert momentum(w).momentum_pct == 100  # 140 x 1 + 30 x fill, capped


# --- state, snapshots, determinism --------------------------------------------------------------


def scenario(seed: int) -> tuple[World, list[Event]]:
    w = new_world(
        objectives=True,
        seed=seed,
        time_limit_ticks=400,
        victory_hold_ticks=50,
        objective_period_ticks=30,
    )
    put(w, "cross-n", 1)
    events = run(w, 60)
    events += step(w, [pause(w, "MAINTENANCE", note=None, source="SYSTEM")])
    events += run(w, 10) + step(w, [resume(w, "SYSTEM")]) + run(w, 40)
    return w, events


def test_two_runs_of_a_scenario_are_identical() -> None:
    (a, ea), (b, eb) = scenario(5), scenario(5)
    assert state_hash(a) == state_hash(b)
    assert [e.model_dump() for e in ea] == [e.model_dump() for e in eb]
    assert state_hash(scenario(6)[0]) != state_hash(a)


def test_a_snapshot_mid_campaign_restores_and_continues_identically() -> None:
    w, _ = scenario(5)
    step(w, [pause(w, sub="CONTENT")])
    assert w.objective is not None and w.campaign.objectives_issued > 1
    again = load(save(w))
    again.rules = w.rules
    assert state_hash(again) == state_hash(w)
    assert again.objective == w.objective and again.campaign == w.campaign
    for _ in range(3):
        step(w, [resume(w)] if w.campaign.clock_paused else [])
        step(again, [resume(again)] if again.campaign.clock_paused else [])
    assert state_hash(again) == state_hash(w)


def test_a_snapshot_after_the_end_keeps_it_ended() -> None:
    w = new_world()
    step(w, [end(w)])
    again = load(save(w))
    assert again.campaign.ended and state_hash(again) == state_hash(w)


def test_format_12_snapshots_are_refused() -> None:
    import msgpack

    raw = msgpack.unpackb(save(new_world()), raw=False)
    raw["v"] = 12
    with pytest.raises(ValueError, match="unsupported snapshot format version 12"):
        load(msgpack.packb(raw, use_bin_type=True))
    assert world_mod.FORMAT_VERSION == 17


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.update(pause_reason="STAFF"),  # a reason while running
        lambda c: c.update(clock_paused=True),  # paused with no reason
        lambda c: c.update(clock_paused=True, pause_reason="TECHNICAL", pause_sub_reason="RAID"),
        lambda c: c.update(running_ticks=c["tick"] + 1),
        lambda c: c.update(objectives_done=1),
    ],
)
def test_inconsistent_campaign_state_is_refused_on_load(mutate: Any) -> None:
    import msgpack

    raw = msgpack.unpackb(save(new_world()), raw=False)
    mutate(raw["campaign"])
    with pytest.raises(ValueError, match="campaign"):
        load(msgpack.packb(raw, use_bin_type=True))


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("campaign", "hold_ticks", 3),  # above running_ticks (0)
        ("campaign", "held_ticks_coalition", 1),  # above nodes x running_ticks (0)
        ("campaign", "held_ticks_enemy", 1),
        ("campaign", "running_ticks", -1),
        ("campaign", "hold_ticks", -1),
        ("campaign", "held_ticks_enemy", -1),
        ("campaign", "objectives_issued", -1),
    ],
)
def test_campaign_counters_are_bounded_on_load(section: str, field: str, value: int) -> None:
    import msgpack

    raw = msgpack.unpackb(save(new_world()), raw=False)
    raw[section][field] = value
    with pytest.raises(ValueError, match=r"campaign|must be an int"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_an_ended_world_with_an_active_objective_is_refused_on_load() -> None:
    import msgpack

    w, _ = scenario(5)
    assert w.objective is not None
    raw = msgpack.unpackb(save(w), raw=False)
    raw["campaign"]["ended"] = True
    with pytest.raises(ValueError, match="ended campaign"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_an_objective_that_is_not_the_latest_or_is_past_due_is_refused_on_load() -> None:
    import msgpack

    w, _ = scenario(5)
    assert w.objective is not None
    for bad in ({"id": 99}, {"deadline": w.campaign.running_ticks}):
        raw = msgpack.unpackb(save(w), raw=False)
        raw["objective"] = {**raw["objective"], **bad}
        with pytest.raises(ValueError, match="objective"):
            load(msgpack.packb(raw, use_bin_type=True))


op_strategy = st.one_of(
    st.just(("step",)),
    st.just(("pause",)),
    st.just(("resume",)),
    st.just(("end",)),
    st.tuples(
        st.just("flip"),
        st.sampled_from([*sorted(RC.candidates), "static-hq"]),
        st.sampled_from(["COALITION", "ENEMY", "NEUTRAL"]),
    ),
)


@given(ops=st.lists(op_strategy, max_size=80), seed=st.integers(0, 2**16))
def test_property_one_end_nothing_after_and_one_active_objective(
    ops: list[tuple[Any, ...]], seed: int
) -> None:
    """C-2, C-3, O-1 and the event/state agreement over random runs."""
    w = new_world(
        objectives=True,
        seed=seed,
        time_limit_ticks=40,
        victory_hold_ticks=6,
        objective_period_ticks=7,
    )
    ends = announced = resolved = 0
    for op in ops:
        was_ended, was_frozen = w.campaign.ended, w.frozen
        commands: list[Any] = []
        if op[0] == "flip":
            w.owner[op[1]] = op[2]
        elif op[0] == "pause":
            commands = [pause(w)]
        elif op[0] == "resume":
            commands = [resume(w)]
        elif op[0] == "end":
            commands = [end(w)]
        events = step(w, commands)
        if was_ended:
            assert all(isinstance(e, CommandRejected) for e in events)
            assert rejects(events) == ["CAMPAIGN_NOT_RUNNING"] * len(commands)
        ends += len(of(events, CampaignEnded))
        announced += len(of(events, ObjectiveAnnounced))
        resolved += len(of(events, ObjectiveResolved))
        assert ends <= 1 and (ends == 1) == w.campaign.ended
        assert announced - resolved == (w.objective is not None)  # at most one active (O-1)
        if not was_frozen and not w.frozen:  # a running tick that did not end: one is active
            frontline = any(
                w.owner[m] != w.owner[n] for n, nbrs in RC.candidates.items() for m in nbrs
            )
            assert w.objective is not None or not frontline
        if w.campaign.clock_paused or was_ended:
            assert w.campaign.running_ticks <= w.campaign.tick
    assert load(save(w)).campaign == w.campaign
