"""NX-430 (Q-TD-46, THREAT-DIRECTOR §4a, ECONOMY EC-9): the Static answers a coalition victory hold.

While a hold runs, a capture operation on a hold node is never staged, one
already staged waits no longer, and it is outside `director.max_ops.<tier>`: neither capped nor
counted. With no hold, staging and the cap are as before. Same set-up and shipped numbers as
test_staging (strait-1, OFFENSIVE 60, fob-n-w 23,750 armor ticks from the rear, past `direct_s`;
its staging base fob-n-e; ALPHA `max_ops` 1).
"""

import pytest
from fixture_pre_5b import pre_5b_config
from hypothesis import given, settings
from hypothesis import strategies as st
from test_campaign import hold_seven
from test_join import CAMPAIGN_ID
from test_staging import (
    LIMITED,
    POOL,
    at_floor,
    debits,
    fire,
    offensive,
    payoffs,
    spawns,
    staging_events,
    window,
    world,
)

from nexus.contracts.gen.events.event import Event
from nexus.core import operations as ops
from nexus.core.launch import _routine
from nexus.core.step import step
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import start_campaign

WEST = ("fob-n-w", "fob-s-w", "west-airbase")  # the coalition's start: OFFENSIVE's targets
COUNTED = ("OFFENSIVE", "RETAKE", "PROBE")  # the ALPHA operations `max_ops` counts


def in_hold(w: World, *nodes: str) -> World:
    """A running victory hold on `nodes` (as test_victory_hold)."""
    w.campaign.hold_ticks = 1
    w.campaign.hold_nodes = tuple(sorted(nodes))
    return w


def at_risk(out: list[Event]) -> list[str | None]:
    return [e.node_id for e in out if e.kind == "ThreatAdaptation" and e.category == "HOLD_AT_RISK"]


def posted(w: World) -> list[tuple[str, str]]:
    return sorted(ops.live_pairs([j.key for j in w.boards["ENEMY"].values()]))


def counted(w: World) -> list[tuple[str, str]]:
    return [p for p in posted(w) if p[0] in COUNTED]


# --- no staging -----------------------------------------------------------------------------------


def test_a_capture_operation_on_a_hold_node_launches_at_once_without_staging() -> None:
    plain = world()
    out = fire(plain, offensive(plain, "fob-n-w"))  # no hold: staged at fob-n-e, which pays
    assert staging_events(out) == [("north", "UP", None)]
    assert payoffs(out) == [("STAGING_LAUNCHED", "north")]
    plain_debits = debits(out)
    w = in_hold(world(), *WEST)
    out = fire(w, offensive(w, "fob-n-w"))
    # FS-10 ("from the rear if needed"): from fob-n-e, which pays now, as the plain launch, but
    # with no massing sitrep and no payoff (Q-TD-64); HOLD_AT_RISK once, as before
    assert staging_events(out) == [] and payoffs(out) == [] and w.director["ENEMY"].staged == []
    assert debits(out) == plain_debits == [("fob-n-e", 40), ("east-airbase", 20)]
    assert [n for k, n in spawns(out) if k == "ENEMY_ARMOR"] == ["fob-n-e"] * 4
    assert at_risk(out) == ["fob-n-w"]
    assert "op:OFFENSIVE:fob-n-w:2" in {j.key for j in w.boards["ENEMY"].values()}


def test_a_hold_response_whose_base_cannot_pay_goes_by_ec_13_at_once() -> None:
    w = in_hold(world(), *WEST)
    at_floor(w, "fob-n-e")  # the staging base cannot pay; east-airbase can
    out = fire(w, offensive(w, "fob-n-w"))
    assert staging_events(out) == [] and w.director["ENEMY"].staged == []
    assert debits(out) == [("east-airbase", 60)]  # EC-13: plan_deploy's base for the jets


def test_a_hold_response_launches_from_its_base_even_with_max_staged_waiting() -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    fire(w, offensive(w, "fob-s-w"))
    assert len(w.director["ENEMY"].staged) == 2  # `max_staged` waiting
    w.stock["fob-n-e"] += 40  # west-airbase's base (fob-n-e, a tie by id) pays its armor now
    in_hold(w, "west-airbase")
    out = fire(w, offensive(w, "west-airbase"))
    assert staging_events(out) == [] and payoffs(out) == []
    assert [n for k, n in spawns(out) if k == "ENEMY_ARMOR"] == ["fob-n-e"] * 4
    assert debits(out) == [("fob-n-e", 40)]  # the jets at the unlimited rear debit nothing


def test_with_no_forward_base_to_host_it_it_launches_from_the_rear() -> None:
    w = in_hold(world(LIMITED), *WEST)
    at_floor(w)  # no base can pay: no forward spawn node
    w.pool["ENEMY"] = POOL * 3  # a rear account of floor(12000 x 0.005) = 60
    out = fire(w, offensive(w, "fob-n-w"))
    assert staging_events(out) == [] and w.director["ENEMY"].staged == []
    assert debits(out) == [("static-rear", 60)]
    assert {n for _, n in spawns(out)} == {"static-rear"} and len(spawns(out)) == 6


def test_a_capture_operation_on_a_node_outside_the_hold_still_stages() -> None:
    w = in_hold(world(), "fob-s-w")
    at_floor(w)
    out = fire(w, offensive(w, "fob-n-w"))
    assert staging_events(out) == [("north", "UP", None)] and len(w.director["ENEMY"].staged) == 1


def test_a_staged_operation_on_a_node_that_enters_the_hold_waits_no_longer() -> None:
    w = world()
    at_floor(w)  # fob-n-e cannot pay: it waits
    fire(w, offensive(w, "fob-n-w"))
    assert len(w.director["ENEMY"].staged) == 1
    w.stock["east-airbase"] += 100  # EC-13 can pay at east-airbase
    out = window(w)
    assert len(w.director["ENEMY"].staged) == 1  # no hold: still waiting at its base
    in_hold(w, *WEST)
    out = window(w)
    assert w.director["ENEMY"].staged == [] and debits(out) == [("east-airbase", 60)]
    assert payoffs(out) == [("STAGING_DISPERSED", "north")]  # it did not go in from the base
    assert at_risk(out) == ["fob-n-w"]


def test_a_staged_operation_on_a_hold_node_with_nothing_to_pay_is_dropped() -> None:
    w = world(LIMITED)
    at_floor(w)
    w.pool["ENEMY"] = 0
    fire(w, offensive(w, "fob-n-w"))
    in_hold(w, *WEST)
    out = window(w, budget=0)
    assert w.director["ENEMY"].staged == [] and debits(out) == [] and spawns(out) == []
    assert payoffs(out) == [("STAGING_DISPERSED", "north")]


# --- outside max_ops ------------------------------------------------------------------------------


def probe_holds_the_slot(w: World) -> None:
    """ALPHA's one `max_ops` slot taken by a PROBE (window 1, the floor not due; 30 points buy
    PROBE 15 and three RECON, routine)."""
    window(w, budget=30)
    assert counted(w) == [("PROBE", "fob-n-w")]


def test_with_max_ops_full_the_hold_response_still_launches() -> None:
    w = in_hold(world(), *WEST)
    probe_holds_the_slot(w)
    window(w, budget=60)  # the best-ranked OFFENSIVE: west-airbase (target value 1.5)
    assert counted(w) == [("OFFENSIVE", "west-airbase"), ("PROBE", "fob-n-w")]


def test_with_no_hold_a_full_max_ops_keeps_the_offensive_out() -> None:
    w = world()
    probe_holds_the_slot(w)
    window(w, budget=60)
    assert counted(w) == [("PROBE", "fob-n-w")]


def test_a_full_max_ops_still_keeps_out_a_capture_operation_on_a_node_outside_the_hold() -> None:
    w = in_hold(world(), "fob-s-w")
    probe_holds_the_slot(w)
    window(w, budget=500)  # pays every OFFENSIVE; only the hold node's is outside the cap
    assert counted(w) == [("OFFENSIVE", "fob-s-w"), ("PROBE", "fob-n-w")]


def test_an_operation_without_a_capture_job_on_a_hold_node_still_takes_the_slot() -> None:
    w = in_hold(world(), "fob-n-w")
    probe_holds_the_slot(w)  # PROBE on fob-n-w, a hold node: no CAPTURE job, so counted
    window(w, budget=500)  # only the hold node's OFFENSIVE is outside the cap
    assert counted(w) == [("OFFENSIVE", "fob-n-w"), ("PROBE", "fob-n-w")]


def test_a_running_hold_response_does_not_take_the_slot() -> None:
    w = in_hold(world(), *WEST)
    window(w, budget=60)
    assert counted(w) == [("OFFENSIVE", "west-airbase")]
    window(w, budget=30)  # ALPHA's slot is still free for PROBE
    assert counted(w) == [("OFFENSIVE", "west-airbase"), ("PROBE", "fob-n-w")]


def test_when_the_hold_ends_a_running_hold_response_counts_again() -> None:
    w = in_hold(world(), *WEST)
    window(w, budget=60)
    w.campaign.hold_ticks, w.campaign.hold_nodes = 0, ()  # the hold is over (accepted, FS-10)
    window(w, budget=30)  # the OFFENSIVE now holds ALPHA's slot: no PROBE
    assert counted(w) == [("OFFENSIVE", "west-airbase")]


def test_the_budget_still_bounds_the_hold_response() -> None:
    w = in_hold(world(), *WEST)
    window(w, budget=59)  # OFFENSIVE costs 60
    assert not [p for p in posted(w) if p[0] == "OFFENSIVE"]


@given(
    hold=st.sets(st.sampled_from(WEST)),
    budgets=st.lists(st.integers(0, 200), min_size=1, max_size=5),
    seed=st.integers(1, 30),
)
@settings(max_examples=25, deadline=None)
def test_no_hold_node_stays_staged_and_the_cap_counts_only_the_rest(
    hold: set[str], budgets: list[int], seed: int
) -> None:
    w = world(seed=seed)
    at_floor(w)
    assert w.rules is not None and w.rules.director is not None
    cap = w.rules.director.max_ops["ALPHA"]
    assert cap is not None
    capture = {o.id for o in w.rules.director.operations if ops.has_capture(o)}
    routine = _routine(w.rules.director)
    if hold:
        in_hold(w, *hold)
    for b in budgets:
        window(w, budget=b)
        assert not [s for s in w.director["ENEMY"].staged if s.target in hold]
        rest = [
            p for p in posted(w)
            if p[0] not in routine and not (p[0] in capture and p[1] in hold)
        ]  # fmt: skip
        assert len(rest) <= cap + 1  # the floor's one over (Q-TD-57) is unchanged


# --- determinism ----------------------------------------------------------------------------------


def hold_world(seed: int = 4) -> World:
    # ALPHA from the start, spending half its surplus, so the first window can buy an OFFENSIVE
    half = {"director.spend_frac.alpha": 0.5, "director.spend_frac.bravo": 0.5}
    c = pre_5b_config({"director.tier.start": "ALPHA", **half})
    w = start_campaign(CAMPAIGN_ID, seed, c)
    hold_seven(w)
    step(w, [])
    assert w.campaign.hold_nodes  # the hold runs
    return w


def run(w: World, ticks: int) -> list[dict[str, object]]:
    return [e.model_dump() for _ in range(ticks) for e in step(w, [])]


@pytest.mark.parametrize("seed", [4, 7])
def test_a_run_during_a_hold_is_deterministic_and_survives_save_and_load(seed: int) -> None:
    def once() -> tuple[str, list[dict[str, object]]]:
        w = hold_world(seed)
        return state_hash(w), run(w, 1300)

    h, events = once()
    assert (h, events) == once()
    said = [e["category"] for e in events if e["kind"] == "ThreatAdaptation"]
    assert said == ["HOLD_AT_RISK"] * 2  # two OFFENSIVEs past ALPHA's cap of 1, never staged
    w = hold_world(seed)
    run(w, 650)
    copy = load(save(w))
    copy.rules = w.rules
    assert run(copy, 650) == run(w, 650) and state_hash(copy) == state_hash(w)
