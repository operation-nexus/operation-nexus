"""NX-412 part 4 (ECONOMY EC-9, EC-12; Q-TD-19, Q-TD-25): the contested victory hold.

The hold events follow `nexus.core.campaign`'s rule exactly (at least `victory_node_frac`, 0.8, of
strait-1's eight strategic nodes: AIRBASE, FOB, PORT), the hold's nodes enter the `EnemyView`, the
Director's capture operations on a hold node or on a coalition node that pays income get their
multipliers, and launching one on a hold node announces the owner's sitrep. Expected values are
worked out by hand from the shipped numbers (OFFENSIVE priority 1.0, PROBE 0.6, target value
AIRBASE 1.5 and FOB 1.0, full defenses: weakness 1; income AIRBASE 10, FOB 5).
"""

import dataclasses
from fractions import Fraction
from typing import Any

import msgpack
import pytest
from fixture_pre_5b import pre_5b_config
from test_campaign import CONFIG as CAMPAIGN_CONFIG
from test_campaign import hold_seven, new_world, of, own, run
from test_launch import candidates, scores, window
from test_launch import new_world as director_world

from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.contracts.gen.events.victory_hold_broken import VictoryHoldBroken
from nexus.contracts.gen.events.victory_hold_started import VictoryHoldStarted
from nexus.core import operations as ops
from nexus.core.fog import side_view
from nexus.core.rng import RngStream
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import start_campaign
from nexus.runtime.config import ConfigError

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
SEVEN = ("cross-n", "cross-s", "fob-n-e", "fob-n-w", "fob-s-e", "fob-s-w", "west-airbase")
WEST = ("fob-n-w", "fob-s-w", "west-airbase")  # the coalition's start, the OFFENSIVE targets


def holds(w: World) -> list[Any]:
    """Every hold event of the next tick."""
    events = run(w)
    return [e for e in events if isinstance(e, (VictoryHoldStarted, VictoryHoldBroken))]


# --- the events follow campaign.py's rule ---------------------------------------------------------


def test_the_hold_starts_once_and_ends_in_the_victory_with_no_break() -> None:
    w = new_world(victory_hold_ticks=5)
    assert holds(w) == []  # 3 of 8 at the start
    hold_seven(w)  # 7 of 8 = 87.5 %
    (started,) = holds(w)
    assert isinstance(started, VictoryHoldStarted)
    assert started.node_ids == list(SEVEN) and started.tick == 2
    assert started.ends_at_tick == 6  # running ticks 2..6 are the five hold ticks
    assert w.campaign.hold_nodes == SEVEN
    events = run(w, 4)
    assert [e for e in events if isinstance(e, (VictoryHoldStarted, VictoryHoldBroken))] == []
    (ended,) = of(events, CampaignEnded)
    assert (ended.result, ended.end_tick) == ("VICTORY", 6)  # on ends_at_tick


def test_a_node_lost_below_the_share_breaks_the_hold_and_names_it() -> None:
    w = new_world(victory_hold_ticks=50, hold_decay=False)  # hold_break: reset (EC-9a)
    hold_seven(w)
    run(w, 3)
    own(w, "ENEMY", "fob-s-e")  # 6 of 8 = 75 %
    (broken,) = holds(w)
    assert isinstance(broken, VictoryHoldBroken) and broken.node_id == "fob-s-e"
    assert broken.progress_ticks == 0
    assert (w.campaign.hold_ticks, w.campaign.hold_nodes) == (0, ())
    assert holds(w) == []  # once
    own(w, "COALITION", "fob-s-e")
    (again,) = holds(w)
    assert isinstance(again, VictoryHoldStarted) and again.ends_at_tick == 6 + 50 - 1
    assert again.progress_ticks == 0


def test_a_loss_above_the_share_keeps_the_hold_and_the_later_break_names_the_node_lost() -> None:
    w = new_world(victory_hold_ticks=50)
    own(w, "COALITION", *SEVEN, "east-airbase")  # 8 of 8
    holds(w)
    own(w, "ENEMY", "east-airbase")  # 7 of 8: still at least 80 %
    assert holds(w) == [] and w.campaign.hold_ticks == 2 and w.campaign.hold_nodes == SEVEN
    own(w, "ENEMY", "fob-s-w")  # 6 of 8
    (broken,) = holds(w)
    assert isinstance(broken, VictoryHoldBroken) and broken.node_id == "fob-s-w"


def test_two_nodes_lost_on_one_tick_break_it_once_naming_the_lowest_id() -> None:
    w = new_world(victory_hold_ticks=50)
    hold_seven(w)
    holds(w)
    own(w, "ENEMY", "fob-s-e", "fob-n-e")
    (broken,) = holds(w)
    assert isinstance(broken, VictoryHoldBroken) and broken.node_id == "fob-n-e"


def test_a_campaign_ending_another_way_during_the_hold_emits_no_break() -> None:
    w = new_world(victory_hold_ticks=50, time_limit_ticks=3)
    hold_seven(w)
    events = run(w, 3)
    (ended,) = of(events, CampaignEnded)
    assert ended.result == "TIME_LIMIT"
    assert len(of(events, VictoryHoldStarted)) == 1 and of(events, VictoryHoldBroken) == []


def test_the_hold_is_in_the_snapshot_and_the_hash_and_bad_values_are_refused() -> None:
    w = new_world(victory_hold_ticks=50)
    hold_seven(w)
    run(w, 2)
    assert load(save(w)).campaign.hold_nodes == SEVEN
    before = state_hash(w)
    w.campaign.hold_nodes = SEVEN[1:]
    assert state_hash(w) != before
    for bad in (["west-airbase", "cross-n"], ["cross-n", "cross-n"], "cross-n"):
        raw = msgpack.unpackb(save(w), raw=False)
        raw["campaign"]["hold_nodes"] = bad
        with pytest.raises(ValueError, match="hold_nodes"):
            load(msgpack.packb(raw, use_bin_type=True))
    raw = msgpack.unpackb(save(w), raw=False)
    raw["campaign"]["hold_ticks"] = 0  # nodes with no hold
    with pytest.raises(ValueError, match="campaign"):
        load(msgpack.packb(raw, use_bin_type=True))
    raw = msgpack.unpackb(save(w), raw=False)
    raw["campaign"]["hold_nodes"] = []  # a hold with no nodes
    with pytest.raises(ValueError, match="campaign"):
        load(msgpack.packb(raw, use_bin_type=True))


# --- EnemyView (TD-2, Q-TD-25) --------------------------------------------------------------------


def test_the_enemy_view_holds_the_running_holds_nodes() -> None:
    w = new_world(victory_hold_ticks=50)
    run(w)
    assert side_view(w, "ENEMY").hold == frozenset()
    hold_seven(w)
    run(w)
    assert side_view(w, "ENEMY").hold == frozenset(SEVEN)
    own(w, "ENEMY", "fob-s-e", "fob-n-e")
    run(w)
    assert side_view(w, "ENEMY").hold == frozenset()


# --- the multipliers (step 4, EC-9, EC-12) -------------------------------------------------------


def director_rules(**overrides: object) -> Rules:
    """The shipped config with `overrides`, set up as test_launch's RULES, with no noise."""
    rules = pre_5b_config({"director.noise_scale": 0, **overrides}).rules
    return dataclasses.replace(rules, campaign=None, garrison_quota={})


def in_hold(w: World, *nodes: str) -> World:
    w.campaign.running_ticks = w.campaign.tick = w.campaign.hold_ticks = 1
    w.campaign.hold_nodes = tuple(sorted(nodes))
    return w


def test_the_multipliers_ship_at_one_and_change_no_score() -> None:
    rules = director_rules()
    assert rules.director is not None
    assert (rules.director.victory_hold_mult, rules.director.income_node_mult) == (
        Fraction(1),
        Fraction(1),
    )
    plain = scores(director_world(), rules)
    assert scores(in_hold(director_world(), *WEST), rules) == plain
    assert plain["OFFENSIVE", "west-airbase"] == Fraction(3, 2)


@pytest.mark.parametrize("key", ["victory_hold_mult", "income_node_mult"])
def test_the_loader_refuses_a_multiplier_below_one(key: str) -> None:
    with pytest.raises(ConfigError):
        pre_5b_config({f"director.score.{key}": 0.9})  # EC-12: >= 1


def test_the_hold_multiplier_applies_to_capture_operations_on_hold_nodes_only() -> None:
    rules = director_rules(**{"director.score.victory_hold_mult": 2.0})
    got = scores(in_hold(director_world(), "west-airbase", "fob-n-w"), rules)
    assert got["OFFENSIVE", "west-airbase"] == 3  # 1.0 x 1.5 x 2
    assert got["OFFENSIVE", "fob-n-w"] == 2  # 1.0 x 1.0 x 2
    assert got["OFFENSIVE", "fob-s-w"] == 1  # not in the hold
    assert got["PROBE", "fob-n-w"] == Fraction(3, 5)  # no CAPTURE job: 0.6 x 1.0
    assert scores(director_world(), rules)["OFFENSIVE", "west-airbase"] == Fraction(3, 2)  # none
    w = in_hold(director_world(), "fob-n-e")  # a RETAKE of a lost node in the hold
    w.owner["fob-n-e"] = "COALITION"
    w.director["ENEMY"].lost["fob-n-e"] = 1
    assert scores(w, rules)["RETAKE", "fob-n-e"] == Fraction(6, 5) * 2  # 1.2 x 1.0 x 2


def test_the_income_multiplier_applies_to_capture_operations_on_income_nodes_only() -> None:
    rules = director_rules(**{"director.score.income_node_mult": 1.5})
    got = scores(director_world(), rules)
    assert got["OFFENSIVE", "west-airbase"] == Fraction(9, 4)  # 1.0 x 1.5 x 1.5
    assert got["OFFENSIVE", "fob-n-w"] == Fraction(3, 2)  # 1.0 x 1.0 x 1.5
    assert got["PROBE", "fob-n-w"] == Fraction(3, 5)  # no CAPTURE job
    no_fob = director_rules(
        **{"director.score.income_node_mult": 1.5, "economy.income.per_node.FOB": 0}
    )
    got = scores(director_world(), no_fob)
    assert got["OFFENSIVE", "fob-n-w"] == 1 and got["OFFENSIVE", "west-airbase"] == Fraction(9, 4)
    both = director_rules(
        **{"director.score.income_node_mult": 1.5, "director.score.victory_hold_mult": 2.0}
    )
    assert scores(in_hold(director_world(), *WEST), both)["OFFENSIVE", "west-airbase"] == Fraction(
        9, 2
    )  # 1.5 x 1.5 x 2


def test_the_income_multiplier_needs_a_node_of_the_other_side() -> None:
    rules = director_rules(**{"director.score.income_node_mult": 1.5})
    w = director_world()
    (offensive,) = [c for c in candidates(w) if (c.op.id, c.target) == ("OFFENSIVE", "fob-n-w")]
    neutral = dataclasses.replace(offensive, target="cross-n")  # a neutral FOB: income 5
    view, rng = side_view(w, "ENEMY"), w.rng.stream(RngStream.DIRECTOR)
    (scored,) = ops.rank([neutral], w.director["ENEMY"], view, rules, rng)
    assert scored.score == 1  # 1.0 x 1 (no target value off the other side), no income factor


# --- the sitrep (EC-9, Q-TD-19) -------------------------------------------------------------------


def at_risk(events: list[Any]) -> list[tuple[str | None, str]]:
    return [
        (e.node_id, e.sector_id)
        for e in events
        if isinstance(e, ThreatAdaptation) and e.category == "HOLD_AT_RISK"
    ]


def test_launching_a_capture_operation_on_a_hold_node_announces_the_sitrep_once() -> None:
    rules = director_rules()
    w = in_hold(director_world(), *WEST)
    first = window(w, "ALPHA", 80, rules)
    # the top candidate (score 1.5) was launched
    assert any(j.key.startswith("op:OFFENSIVE:west-airbase:") for j in w.boards["ENEMY"].values())
    assert at_risk(first) == [("west-airbase", "centre")]
    (sitrep,) = [e for e in first if isinstance(e, ThreatAdaptation)]
    assert (sitrep.side, sitrep.direction) == ("ENEMY", "UP")
    # west-airbase's is live: not launched again; the hold response (Q-TD-46) puts fob-n-w's,
    # the other hold node, outside ALPHA's max_ops, so it launches with its own one sitrep
    assert at_risk(window(w, "ALPHA", 80, rules)) == [("fob-n-w", "north")]


def test_no_sitrep_for_a_capture_operation_on_a_node_outside_the_hold() -> None:
    rules = director_rules()
    w = in_hold(director_world(), "fob-n-w")
    events = window(w, "ALPHA", 80, rules)
    assert any(j.key.startswith("op:OFFENSIVE:west-airbase:") for j in w.boards["ENEMY"].values())
    assert at_risk(events) == []
    assert at_risk(window(director_world(), "ALPHA", 80, rules)) == []  # no hold at all


def test_no_sitrep_for_an_operation_without_a_capture_job_on_a_hold_node() -> None:
    rules = director_rules()
    w = in_hold(director_world(), *WEST)
    events = window(
        w, "ALPHA", 25, rules
    )  # three RECONs (2 each), then PROBE (15); no OFFENSIVE (60)
    assert any(j.key.startswith("op:PROBE:") for j in w.boards["ENEMY"].values())
    assert at_risk(events) == []


# --- determinism (SIM-CORE, ADR-0002) -------------------------------------------------------------


def test_save_and_load_during_a_hold_replays_the_same_run() -> None:
    def held() -> World:
        w = start_campaign(CAMPAIGN_ID, 7, CAMPAIGN_CONFIG)  # shipped rules: Director and campaign
        hold_seven(w)
        for _ in range(700):  # the hold runs through a decision window (600 ticks)
            step(w, [])
        assert w.campaign.hold_ticks == 700 and w.campaign.hold_nodes == SEVEN
        return w

    def go(w: World) -> tuple[str, list[dict[str, Any]]]:
        events = [e.model_dump() for _ in range(1_300) for e in step(w, [])]
        return state_hash(w), events

    a = held()
    b = load(save(a))
    b.rules = a.rules  # a snapshot holds no rules (SC-9)
    assert state_hash(b) == state_hash(a)
    first = go(a)
    assert go(b) == first
    assert go(held()) == first  # and a fresh run from the seed
