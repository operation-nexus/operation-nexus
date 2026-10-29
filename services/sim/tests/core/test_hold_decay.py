"""NX-489 (ECONOMY EC-9a, GAMEPLAY §9, Q-TD-102, Q-TD-126): a broken victory hold decays.

A break keeps the progress P (`Campaign.hold_ticks`); P drains at `decay_slow_rate` for the slow
stage, then at `decay_fast_rate`, and resets at 0 (`VictoryHoldReset{DECAYED}`) or when the Static
owns a broken-hold node at full defense hp (`REPAIRED`, with `reset_on_repair`); a re-held hold
resumes from what is left. The rates and switches come through the loader (`shipped_config`); only
the slow stage and the hold length are shrunk to a few ticks so a run is short.

Worked example used below (the shipped rates 0.25 and 1.0, a slow stage S of 4 ticks, a hold broken
at P = 6): the loss after t broken ticks is floor(0.25 x min(t, 4) + 1.0 x max(0, t - 4)), so
t = 1..3 lose 0 (P 6), t = 4 loses 1 (P 5, the stage boundary), t = 5..8 lose 2..5 (P 4..1) and
t = 9 loses 6: P reaches 0 and the hold resets.
"""

from collections.abc import Mapping
from fractions import Fraction
from typing import Any

import msgpack
import pytest
from test_campaign import CONFIG, RC, end, hold_seven, new_world, of, own, pause, resume, run
from test_launch import new_world as director_world
from test_launch import scores, window
from test_victory_hold import WEST, at_risk, director_rules

import nexus.core.campaign as campaign_mod
from nexus.contracts.gen.common.enums import NodeOwner
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.victory_hold_broken import VictoryHoldBroken
from nexus.contracts.gen.events.victory_hold_reset import VictoryHoldReset
from nexus.contracts.gen.events.victory_hold_started import VictoryHoldStarted
from nexus.core.fog import side_view
from nexus.core.rules import CampaignRules
from nexus.core.step import step
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import start_campaign
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
SEVEN = ("cross-n", "cross-s", "fob-n-e", "fob-n-w", "fob-s-e", "fob-s-w", "west-airbase")
P_BY_T = {1: 6, 2: 6, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}  # the worked example above
_LOADED = ("hold_decay", "decay_slow_rate", "decay_fast_rate", "reset_on_repair")


def decay_world(
    keys: Mapping[str, object] | None = None, *, hold: int = 50, slow: int = 4
) -> World:
    """strait-1 with `keys` (dotted balance keys) through the loader, the hold `hold` ticks long
    and the slow stage `slow` ticks; every defense hp at 0 (test_campaign's world)."""
    rc = shipped_config(keys).rules.campaign if keys else RC
    assert rc is not None
    loaded = {k: getattr(rc, k) for k in _LOADED}
    return new_world(victory_hold_ticks=hold, decay_slow_ticks=slow, **loaded)


def hold_events(events: list[Event]) -> list[Any]:
    kinds = (VictoryHoldStarted, VictoryHoldBroken, VictoryHoldReset)
    return [e for e in events if isinstance(e, kinds)]


def broken(w: World, held: int, *lost: str) -> VictoryHoldBroken:
    """Hold seven nodes for `held` running ticks, then lose `lost` (default fob-s-e): the break."""
    hold_seven(w)
    run(w, held)
    own(w, "ENEMY", *(lost or ("fob-s-e",)))
    (e,) = hold_events(run(w))
    assert isinstance(e, VictoryHoldBroken)
    return e


def regain(w: World) -> Any:
    own(w, "COALITION", *SEVEN)
    (e,) = hold_events(run(w))
    return e


# --- the curve ------------------------------------------------------------------------------------


def test_a_break_keeps_the_progress_out_of_the_running_hold() -> None:
    w = decay_world()
    e = broken(w, 6)
    assert (e.node_id, e.progress_ticks) == ("fob-s-e", 6)
    c = w.campaign
    assert (c.hold_ticks, c.hold_nodes, c.hold_broken_nodes, c.hold_broken_ticks) == (
        6,
        (),
        SEVEN,
        0,
    )


@pytest.mark.parametrize(("t", "p"), sorted(P_BY_T.items()))
def test_the_progress_follows_the_two_stage_curve_and_a_re_hold_resumes_from_it(
    t: int, p: int
) -> None:
    w = decay_world()
    broken(w, 6)
    assert hold_events(run(w, t)) == []  # no per-tick decay event, no reset before 0
    assert w.viewer_units() == 0  # decay runs with nobody playing (EC-9a Clock)
    started = regain(w)
    assert isinstance(started, VictoryHoldStarted) and started.progress_ticks == p
    assert w.campaign.hold_ticks == p + 1  # the resume tick credits one more


def test_the_progress_reaching_zero_resets_the_hold() -> None:
    w = decay_world()
    broken(w, 6)
    assert hold_events(run(w, 8)) == []
    (reset,) = hold_events(run(w))  # t = 9
    assert isinstance(reset, VictoryHoldReset)
    assert (reset.reason, reset.node_id, reset.tick) == ("DECAYED", None, 16)  # 6 + 1 + 9
    c = w.campaign
    assert (c.hold_ticks, c.hold_broken_ticks, c.hold_broken_nodes) == (0, 0, ())
    assert hold_events(run(w, 5)) == []  # once
    fresh = regain(w)
    assert isinstance(fresh, VictoryHoldStarted) and fresh.progress_ticks == 0


def test_the_loss_is_exact_where_a_float_would_drift() -> None:
    # 0.29 x 100 is 28.999999999999996 in binary floating point; the exact loss is 29
    rate = {"campaign.victory.decay_slow_rate": 0.29, "campaign.victory.decay_fast_rate": 0.29}
    w = decay_world(rate, slow=100)
    broken(w, 30)
    run(w, 100)
    started = regain(w)
    assert isinstance(started, VictoryHoldStarted) and started.progress_ticks == 1  # 30 - 29


def test_a_resumed_hold_ends_at_the_tick_its_progress_reaches_the_hold() -> None:
    w = decay_world()
    broken(w, 6)  # running ticks 1..6 held, the break on 7
    run(w, 6)  # t = 6: P = 3
    started = regain(w)  # running tick 14
    assert isinstance(started, VictoryHoldStarted)
    assert (started.progress_ticks, started.ends_at_tick) == (3, 60)  # 14 + 50 - (3 + 1)
    events = run(w, 46)
    (ended,) = of(events, CampaignEnded)
    assert (ended.result, ended.end_tick) == ("VICTORY", 60)


def test_a_second_break_restarts_the_slow_stage() -> None:
    w = decay_world()
    broken(w, 6)
    run(w, 6)  # P = 3
    regain(w)  # P 4
    run(w)  # P 5
    own(w, "ENEMY", "fob-s-e")
    (again,) = hold_events(run(w))
    assert isinstance(again, VictoryHoldBroken) and again.progress_ticks == 5
    run(w, 3)  # t = 3 of the new break: still the slow stage, nothing lost
    started = regain(w)
    assert isinstance(started, VictoryHoldStarted) and started.progress_ticks == 5


# --- reset by repair (R1) -------------------------------------------------------------------------


def full(w: World, *nodes: str) -> None:
    assert w.rules is not None and w.rules.defense is not None
    for n in nodes:
        w.defense_hp[n] = w.rules.defense.max_hp[n]


def test_a_broken_hold_node_the_static_repairs_to_full_resets_it_lowest_id_first() -> None:
    w = decay_world()
    e = broken(w, 6, "fob-s-e", "fob-n-e")
    assert e.node_id == "fob-n-e"
    run(w, 2)
    full(w, "fob-s-e", "fob-n-e")
    (reset,) = hold_events(run(w))
    assert isinstance(reset, VictoryHoldReset) and (reset.reason, reset.node_id) == (
        "REPAIRED",
        "fob-n-e",
    )
    assert (w.campaign.hold_ticks, w.campaign.hold_broken_nodes) == (0, ())


def test_the_repair_names_the_one_node_at_full() -> None:
    w = decay_world()
    broken(w, 6, "fob-s-e", "fob-n-e")
    full(w, "fob-s-e")
    (reset,) = hold_events(run(w))
    assert isinstance(reset, VictoryHoldReset) and reset.node_id == "fob-s-e"


def test_no_repair_reset_for_a_node_short_of_full_or_still_the_coalitions() -> None:
    w = decay_world()
    broken(w, 6)
    full(w, "west-airbase", "fob-n-e")  # broken-hold nodes, still the coalition's
    assert w.rules is not None and w.rules.defense is not None
    w.defense_hp["fob-s-e"] = w.rules.defense.max_hp["fob-s-e"] - 1
    assert hold_events(run(w, 2)) == []


def test_with_reset_on_repair_off_only_the_decay_ends_it() -> None:
    w = decay_world({"campaign.victory.reset_on_repair": False})
    broken(w, 6)
    full(w, "fob-s-e")
    assert hold_events(run(w, 8)) == []
    (reset,) = hold_events(run(w))
    assert isinstance(reset, VictoryHoldReset) and reset.reason == "DECAYED"


def test_on_the_tick_both_hold_the_decay_is_the_reason() -> None:
    w = decay_world()
    broken(w, 6)
    run(w, 8)
    full(w, "fob-s-e")
    (reset,) = hold_events(run(w))
    assert isinstance(reset, VictoryHoldReset) and (reset.reason, reset.node_id) == (
        "DECAYED",
        None,
    )


# --- the clock: running ticks only ----------------------------------------------------------------


def test_no_decay_while_paused() -> None:
    w = decay_world()
    broken(w, 6)
    run(w, 2)
    step(w, [pause(w)])
    assert hold_events(run(w, 30)) == []
    assert w.campaign.hold_broken_ticks == 2
    step(w, [resume(w)])  # this running tick is t = 3
    run(w, 3)  # t = 6: P = 3
    started = regain(w)
    assert isinstance(started, VictoryHoldStarted) and started.progress_ticks == 3


def test_no_decay_once_the_campaign_has_ended() -> None:
    w = decay_world()
    broken(w, 6)
    run(w, 2)
    step(w, [end(w)])
    assert hold_events(run(w, 30)) == []
    c = w.campaign
    assert (c.hold_ticks, c.hold_broken_ticks, c.hold_broken_nodes) == (6, 2, SEVEN)


# --- a decaying hold is not the running hold ------------------------------------------------------


def test_a_decaying_hold_is_not_in_the_enemy_view() -> None:
    w = decay_world()
    broken(w, 6)
    run(w)
    assert w.campaign.hold_broken_nodes == SEVEN
    assert side_view(w, "ENEMY").hold == frozenset()


def decaying(w: World, *nodes: str) -> World:
    c = w.campaign
    c.running_ticks = c.tick = 2
    c.hold_ticks, c.hold_broken_ticks, c.hold_broken_nodes = 1, 1, tuple(sorted(nodes))
    return w


def test_a_decaying_hold_gets_no_multiplier_hold_response_or_sitrep() -> None:
    rules = director_rules(**{"director.score.victory_hold_mult": 2.0})
    assert scores(decaying(director_world(), *WEST), rules) == scores(director_world(), rules)
    # FS-10: a running hold's second capture operation launches outside ALPHA's max_ops
    # (test_victory_hold); a decaying hold gets none of it and no HOLD_AT_RISK
    w = decaying(director_world(), *WEST)
    assert at_risk(window(w, "ALPHA", 80, rules)) == []
    assert at_risk(window(w, "ALPHA", 80, rules)) == []
    offensives = {j.key.split(":")[2] for j in w.boards["ENEMY"].values() if "OFFENSIVE" in j.key}
    assert offensives == {"west-airbase"}  # no second one on fob-n-w past max_ops


# --- hold_break: reset is the rule before NX-489 --------------------------------------------------


def _track_hold_before_nx489(
    world: World, rc: CampaignRules, holding: bool, out: list[Event]
) -> None:
    """`nexus.core.campaign._track_hold` as of 417a66c (`campaign.py:192-216`), the oracle. The
    one change: its events set `progress_ticks` 0, the field the old schema did not have."""
    c = world.campaign
    was = c.hold_nodes
    c.hold_ticks = c.hold_ticks + 1 if holding else 0
    c.hold_nodes = (
        tuple(n for n in rc.strategic if world.owner.get(n) == "COALITION") if holding else ()
    )
    if c.hold_ticks == 1:
        out.append(
            VictoryHoldStarted.model_construct(
                kind="VictoryHoldStarted", tick=c.tick + 1, event_seq=world.next_event_seq(),
                campaign_id=c.id, node_ids=list(c.hold_nodes),
                ends_at_tick=c.running_ticks + rc.victory_hold_ticks - 1, progress_ticks=0,
            )
        )  # fmt: skip
    elif was and not holding:
        out.append(
            VictoryHoldBroken.model_construct(
                kind="VictoryHoldBroken", tick=c.tick + 1, event_seq=world.next_event_seq(),
                campaign_id=c.id, node_id=next(n for n in was if world.owner.get(n) != "COALITION"),
                progress_ticks=0,
            )
        )  # fmt: skip


# tick -> (side, nodes) taken before that tick: breaks, a re-hold, a double loss, a slow regain
SCRIPT: dict[int, tuple[NodeOwner, tuple[str, ...]]] = {
    0: ("COALITION", SEVEN),
    4: ("ENEMY", ("fob-s-e",)),
    6: ("COALITION", ("fob-s-e",)),
    9: ("ENEMY", ("fob-n-e", "fob-s-w")),
    11: ("COALITION", ("fob-n-e",)),
    14: ("COALITION", ("fob-s-w",)),
    18: ("ENEMY", ("cross-n",)),
    19: ("COALITION", ("cross-n",)),
}


def scripted(w: World) -> list[tuple[str, list[dict[str, Any]]]]:
    trace = []
    for tick in range(40):
        if tick in SCRIPT:
            side, nodes = SCRIPT[tick]
            own(w, side, *nodes)
        trace.append((state_hash(w), [e.model_dump() for e in run(w)]))
    return trace


def test_hold_break_reset_reproduces_the_old_rule_tick_for_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reset_world() -> World:
        return decay_world({"campaign.victory.hold_break": "reset"}, hold=8)

    now = scripted(reset_world())
    monkeypatch.setattr(campaign_mod, "_track_hold", _track_hold_before_nx489)
    before = scripted(reset_world())
    assert now == before
    kinds = [e["kind"] for _, events in now for e in events if "Hold" in e["kind"]]
    assert kinds == ["VictoryHoldStarted", "VictoryHoldBroken"] * 3 + ["VictoryHoldStarted"]
    assert any(e["kind"] == "CampaignEnded" for _, events in now for e in events)


def test_the_default_decay_differs_from_the_old_rule_on_the_same_script() -> None:
    kinds = [
        (e["kind"], e.get("progress_ticks"))
        for _, events in scripted(decay_world(hold=8))
        for e in events
        if "Hold" in e["kind"]
    ]
    assert kinds[:4] == [
        ("VictoryHoldStarted", 0),
        ("VictoryHoldBroken", 4),  # running ticks 1..4 held
        ("VictoryHoldStarted", 4),  # resumed: two slow-stage ticks lost nothing
        ("VictoryHoldBroken", 7),
    ]


# --- the loader -----------------------------------------------------------------------------------


def test_the_shipped_keys_reach_the_rules() -> None:
    assert RC.hold_decay is True and RC.reset_on_repair is True
    assert RC.decay_slow_ticks == 6_000  # 10 game minutes at 10 Hz
    assert (RC.decay_slow_rate, RC.decay_fast_rate) == (Fraction(1, 4), Fraction(1))


@pytest.mark.parametrize(
    "keys",
    [
        {"campaign.victory.decay_fast_rate": 0.2},  # below the slow rate 0.25
        {"campaign.victory.decay_fast_rate": 0},  # never reaches 0
        {"campaign.victory.decay_slow_rate": -0.1},
        {"campaign.victory.decay_slow_min": -1},
    ],
)
def test_the_loader_refuses_a_curve_that_never_empties_or_speeds_down(
    keys: dict[str, object],
) -> None:
    with pytest.raises(ConfigError):
        shipped_config(keys)


def test_equal_rates_load() -> None:
    rc = shipped_config({"campaign.victory.decay_fast_rate": 0.25}).rules.campaign
    assert rc is not None and rc.decay_fast_rate == rc.decay_slow_rate


# --- snapshot and determinism (SIM-CORE, ADR-0002) ------------------------------------------------


def shipped_decaying() -> World:
    """The shipped rules (Director and campaign), a hold broken after 700 ticks, 50 ticks into
    its slow stage."""
    w = start_campaign(CAMPAIGN_ID, 7, CONFIG)
    hold_seven(w)
    for _ in range(700):
        step(w, [])
    own(w, "ENEMY", "fob-s-e")
    for _ in range(51):
        step(w, [])
    c = w.campaign
    assert (c.hold_ticks, c.hold_broken_ticks, c.hold_broken_nodes) == (700, 50, SEVEN)
    return w


def test_save_and_load_mid_decay_replays_the_same_run() -> None:
    def go(w: World) -> tuple[str, list[dict[str, Any]]]:
        events = [e.model_dump() for _ in range(1_300) for e in step(w, [])]
        return state_hash(w), events

    a = shipped_decaying()
    b = load(save(a))
    b.rules = a.rules  # a snapshot holds no rules (SC-9)
    assert state_hash(b) == state_hash(a)
    assert (b.campaign.hold_broken_ticks, b.campaign.hold_broken_nodes) == (50, SEVEN)
    first = go(a)
    assert go(b) == first
    assert go(shipped_decaying()) == first  # and a fresh run from the seed


def test_the_decay_state_is_in_the_hash() -> None:
    w = shipped_decaying()
    before = state_hash(w)
    w.campaign.hold_broken_ticks += 1
    assert state_hash(w) != before
    w.campaign.hold_broken_ticks -= 1
    w.campaign.hold_broken_nodes = SEVEN[1:]
    assert state_hash(w) != before


def refused(w: World, match: str, **campaign: object) -> None:
    raw = msgpack.unpackb(save(w), raw=False)
    raw["campaign"].update(campaign)
    with pytest.raises(ValueError, match=match):
        load(msgpack.packb(raw, use_bin_type=True))


def test_the_loader_refuses_an_inconsistent_hold() -> None:
    w = decay_world()
    broken(w, 6)
    run(w, 2)
    assert load(save(w)).campaign.hold_broken_nodes == SEVEN  # the valid one loads
    refused(w, "campaign", hold_broken_nodes=[])  # progress with no hold
    refused(w, "campaign", hold_nodes=list(SEVEN))  # running and decaying at once
    refused(w, "campaign", hold_ticks=0)  # a decaying hold with nothing kept
    refused(w, "campaign", hold_broken_ticks=w.campaign.running_ticks)  # more ticks than ran
    refused(w, "hold_broken_nodes", hold_broken_nodes=["west-airbase", "cross-n"])
    fresh = decay_world()
    run(fresh, 3)
    refused(fresh, "campaign", hold_broken_ticks=1)  # broken ticks with no broken hold


def test_a_format_36_snapshot_is_refused() -> None:
    raw = msgpack.unpackb(save(decay_world()), raw=False)
    raw["v"] = 36
    with pytest.raises(ValueError, match="unsupported snapshot format version 36"):
        load(msgpack.packb(raw, use_bin_type=True))
