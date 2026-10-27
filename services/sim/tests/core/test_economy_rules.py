"""NX-412 part 3 (ECONOMY EC-7, EC-8, EC-13, EC-14; Q-TD-33): the director budget, the live-unit
guard and the one spawn rule, behind the temporary switch `economy.legacy_rules`.

Runs on the shipped strait-1 config with `economy.legacy_rules` false (flipped through the shipped
profile). Expected numbers are worked by hand from the shipped values: spend_frac
pattern_of_life 0.007, alpha 0.02, bravo 0.0534; source_spend_frac 0.005; upkeep_reserve_windows 2;
cadence_windows 10; the Static's bases start with 1,500 stock above their starvation floors
(east-airbase 500, static-hq 500, fob-n-e 250, fob-s-e 250); a limited Static's pool starts at its
storage, 8,000 (2,000 + HQ 2,000 + AIRBASE 2,000 + 2 FOB 1,000); the coalition's at 6,000; a
STRIKE_FIGHTER's loadout costs 20; OFFENSIVE costs 60 (6 units), RECON 2.
"""

import dataclasses
from fractions import Fraction
from typing import Any

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID, join

from nexus.contracts.gen.common.enums import ThreatTier, UnitKind
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.core import operations as ops
from nexus.core.director import budget, rear_share
from nexus.core.fog import side_view
from nexus.core.launch import _capture_slot, _convoys, _post_and_spawn, _Purse, _routine
from nexus.core.launch import run as launch
from nexus.core.rules import JobTemplate, OperationRules, Rules
from nexus.core.step import step
from nexus.core.world import Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config

# forward staging (NX-416) out of reach, so these tests see EC-13 alone; test_staging.py covers it
NEW: dict[str, object] = {"economy.legacy_rules": False, "director.staging.direct_s": 1e6}
LIMITED: dict[str, object] = {
    "economy.unlimited.COALITION": False,
    "economy.unlimited.ENEMY": False,
}
STATIC_BASES = ("east-airbase", "fob-n-e", "fob-s-e", "static-hq")


def config(overrides: dict[str, object]) -> CampaignConfig:
    """The shipped config with `overrides`, the campaign layer off and no opening Static garrison
    (as test_launch), so a window launches only what the test sets up."""
    c = shipped_config(overrides)
    return dataclasses.replace(c, rules=dataclasses.replace(c.rules, campaign=None))


NEW_UNLIMITED = config(NEW)
NEW_LIMITED = config({**NEW, **LIMITED})
LEGACY_LIMITED = config(LIMITED)


def world(c: CampaignConfig, seed: int = 1, *, garrison: bool = False) -> World:
    rules = c.rules if garrison else dataclasses.replace(c.rules, garrison_quota={})
    return start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(c, rules=rules))


def at_floor(w: World) -> None:
    for n in STATIC_BASES:
        assert w.rules is not None
        w.stock[n] = w.rules.supply.starve_floor[n]


def the_budget(w: World, tier: ThreatTier = "ALPHA", *, upkeep: int = 0) -> int:
    assert w.rules is not None
    s = w.director["ENEMY"]
    s.tier = tier
    return budget(s, side_view(w, "ENEMY"), w.rules, w.stock, w.pool.get("ENEMY", 0), upkeep)


def operations(w: World, spend: int, tier: ThreatTier = "ALPHA") -> list[Event]:
    """One window of operations at `tier` with `spend` budget points."""
    assert w.rules is not None
    s = w.director["ENEMY"]
    s.tier, s.budget = tier, spend
    out: list[Event] = []
    launch(w, "ENEMY", side_view(w, "ENEMY"), w.rules, out)
    return out


def spawns(out: list[Event]) -> list[str]:
    return [e.node_id for e in out if e.kind == "UnitSpawned"]


def debits(out: list[Event]) -> list[tuple[str, int]]:
    return [(e.node_id, e.amount) for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN"]


# --- EC-7: the budget formula ---------------------------------------------------------------------


@pytest.mark.parametrize(("tier", "want"), [("PATTERN_OF_LIFE", 10), ("ALPHA", 30), ("BRAVO", 80)])
def test_the_base_term_is_the_tier_share_of_the_surplus(tier: ThreatTier, want: int) -> None:
    # unlimited Static: no pool, so the rear term is 0; floor(1500 x 0.007) = 10, x 0.02 = 30,
    # x 0.0534 = 80 (80.1 floored)
    assert the_budget(world(NEW_UNLIMITED), tier) == want


def test_the_rear_term_adds_a_share_of_the_pool() -> None:
    w = world(NEW_LIMITED)
    assert w.pool["ENEMY"] == 8000
    assert the_budget(w) == 30 + 40  # floor(8000 x 0.005) = 40
    w.pool["ENEMY"] = 199
    assert the_budget(w) == 30  # floor(0.995) = 0


def test_the_reserve_keeps_back_two_windows_of_upkeep_and_the_budget_never_goes_below_0() -> None:
    w = world(NEW_UNLIMITED)
    assert the_budget(w, upkeep=7) == 30 - 14
    assert the_budget(w, upkeep=15) == 0  # 30 - 30
    assert the_budget(w, upkeep=100) == 0  # never negative


def test_with_every_fraction_at_1_the_budget_is_surplus_plus_pool() -> None:
    ones = {f"director.spend_frac.{t}": 1.0 for t in ("pattern_of_life", "alpha", "bravo")}
    c = config({**NEW, **LIMITED, **ones, "director.source_spend_frac": 1.0})
    w = world(c)
    w.pool["ENEMY"] = 300
    assert the_budget(w) == 1500 + 300


def test_the_cadence_floor_buys_the_cheapest_operation_after_cadence_windows_with_the_hq() -> None:
    # 1 upkeep a window: a reserve of 2 takes the rear share back to 0 without the floor
    w = world(NEW_LIMITED)
    at_floor(w)  # surplus 0
    w.pool["ENEMY"] = 400  # rear share floor(400 x 0.005) = 2
    s = w.director["ENEMY"]
    s.windows, s.last_operation = 9, 0
    assert the_budget(w, upkeep=1) == 0  # 9 windows since: no floor yet
    s.windows = 10
    assert the_budget(w, upkeep=1) == 2  # RECON (2), the cheapest ALPHA operation, rear share 2
    s.last_operation = 1
    assert the_budget(w, upkeep=1) == 0  # an operation 9 windows ago
    s.last_operation = 0
    w.owner["static-hq"] = "COALITION"
    assert the_budget(w, upkeep=1) == 0  # no HQ held: no floor
    w.owner["static-hq"] = "ENEMY"
    w.pool["ENEMY"] = 200  # rear share 1: the pool covers RECON, this window cannot (NX-434)
    assert the_budget(w, upkeep=1) == 0


def posted(w: World) -> list[tuple[str, str]]:
    """(operation, target) of the Director's operations on the Static's board."""
    return sorted(ops.live_pairs([j.key for j in w.boards["ENEMY"].values()]))


def floor_window(w: World, windows: int, spend: int = 30) -> list[tuple[str, str]]:
    """One ALPHA window `windows` windows after the last launch (window 0) with `spend` points."""
    w.director["ENEMY"].windows = windows
    operations(w, spend)
    return posted(w)


# with 30 points and no floor the ALPHA window buys PROBE (15) and three RECON (2) (seed 1)
CHEAP = [("PROBE", "fob-n-w"), ("RECON", "centre"), ("RECON", "north"), ("RECON", "south")]


def test_the_cadence_floor_buys_a_capture_operation_over_cheaper_ones() -> None:
    # Q-TD-42: the floor lifts the budget to OFFENSIVE (60, the one capture operation with a
    # target: RETAKE has no recently lost base) and launches it first, not PROBE or RECON
    w = world(NEW_UNLIMITED)
    assert floor_window(w, 10) == [("OFFENSIVE", "west-airbase")]
    assert w.director["ENEMY"].budget == 60 and w.director["ENEMY"].last_operation == 10
    assert floor_window(world(NEW_UNLIMITED), 9) == CHEAP  # not due: unchanged
    assert world(NEW_UNLIMITED).director["ENEMY"].budget == 0


CAPTURE_OPS = ("OFFENSIVE", "RETAKE")


def cheap_windows(w: World, first: int, last: int) -> None:
    """Windows `first`..`last`, each buying cheap operations (30 points, ALPHA) and none that
    captures; the board is cleared before each, as if the last window's operations had ended."""
    for k in range(first, last + 1):
        w.boards["ENEMY"].clear()
        pairs = floor_window(w, k)
        assert pairs and not [p for p in pairs if p[0] in CAPTURE_OPS], (k, pairs)
        assert w.director["ENEMY"].budget == 30, k  # no lift


def test_cheap_operations_every_window_do_not_hold_off_the_capture_floor() -> None:
    # Q-TD-54 (J0-J4 review §2): the Static launched cheap operations every window and the floor,
    # counted from any operation, never came due. It counts from the last capture operation:
    # nine windows of PROBE and RECON leave it at window 0, so window 10 forces OFFENSIVE
    w = world(NEW_UNLIMITED)
    cheap_windows(w, 1, 9)
    assert w.director["ENEMY"].last_operation == 0  # cheap launches do not stamp
    w.boards["ENEMY"].clear()
    assert floor_window(w, 10) == [("OFFENSIVE", "west-airbase")]
    assert w.director["ENEMY"].last_operation == 10  # a capture launch does
    cheap_windows(w, 11, 19)  # counted from window 10: not due before window 20
    assert w.director["ENEMY"].last_operation == 10
    w.boards["ENEMY"].clear()
    assert floor_window(w, 20) == [("OFFENSIVE", "west-airbase")]


def test_with_no_capture_target_the_cheapest_operation_floor_also_counts_from_capture() -> None:
    # Q-TD-54, one clock (NX-439): with the night cap spent no capture operation is a candidate,
    # so window 10 buys cheap operations; they do not reset the floor, which stays due and keeps
    # the next window's budget at the cheapest operation (RECON, 2) the rear share (2) pays
    w = world(NEW_LIMITED)
    s = w.director["ENEMY"]
    s.last_flip = 1  # the night cap is spent: no capture operation
    pairs = floor_window(w, 10)
    assert pairs and not [p for p in pairs if p[0] in CAPTURE_OPS]
    assert s.last_operation == 0
    at_floor(w)  # surplus 0
    w.pool["ENEMY"] = 400  # rear share floor(400 x 0.005) = 2, all of it the reserve's
    s.windows = 11
    assert the_budget(w, upkeep=1) == 2


def test_without_a_capture_target_the_floor_keeps_the_cheapest_operation_rule() -> None:
    def capped(windows: int) -> tuple[list[tuple[str, str]], int]:
        w = world(NEW_UNLIMITED)
        w.director["ENEMY"].last_flip = 1  # the night cap is spent: no capture operation
        return floor_window(w, windows), w.director["ENEMY"].budget

    assert capped(10) == capped(9)
    assert capped(10)[1] == 30 and capped(10)[0][0][0] == "PROBE"
    w = world(NEW_UNLIMITED)
    w.owner["static-hq"] = "COALITION"  # no HQ held: the floor does not apply
    assert ("OFFENSIVE", "west-airbase") not in floor_window(w, 10)
    assert w.director["ENEMY"].budget == 30


def cheapest_window(free: int, pool: int, windows: int = 10) -> tuple[int, list[Event], World]:
    """NX-434: an ALPHA window of a limited Static with no capture candidate (the night cap
    spent), `free` surplus at east-airbase only, `pool` in its rear pool and 1 upkeep a window
    (a reserve of 2): the budget `decide` sets (`the_budget`), then that window's operations."""
    w = world(NEW_LIMITED)
    at_floor(w)
    w.stock["east-airbase"] += free
    w.pool["ENEMY"] = pool
    s = w.director["ENEMY"]
    s.last_flip, s.windows = 1, windows
    spend = the_budget(w, upkeep=1)
    return spend, operations(w, spend), w


def test_the_cheapest_operation_floor_the_rear_account_pays_is_paid_at_the_source() -> None:
    # NX-434: no base surplus, pool 400 (rear share 2, all of it the reserve's): the floor lifts
    # the budget to RECON (2), the rear account is 2, and RECON spawns and pays at the source
    spend, out, w = cheapest_window(0, 400)
    assert spend == 2 and debits(out) == [("static-rear", 2)] and spawns(out) == ["static-rear"]
    assert w.pool["ENEMY"] == 398
    assert cheapest_window(0, 400, windows=9)[:2] == (0, [])  # not due: nothing


def test_the_cheapest_operation_floor_counts_no_pool_money_the_window_cannot_spend() -> None:
    # NX-434: no base surplus, pool 200 (rear share 1): the pool covers RECON (2) but the window's
    # rear account cannot, so the floor lifts nothing and the window is the one without it
    # (before NX-434 it counted surplus + pool, lifted the budget to 2 and RECON could not pay)
    due, not_due = cheapest_window(0, 200), cheapest_window(0, 200, windows=9)
    assert due[0] == not_due[0] == 0
    assert debits(due[1]) == debits(not_due[1]) == [] and spawns(due[1]) == []
    assert due[2].pool["ENEMY"] == 200
    assert due[2].director["ENEMY"].budget == 0  # `launch.run`'s floor agrees: no lift there


def test_a_failed_capture_lead_is_undone_to_the_cheapest_operation_lift() -> None:
    # NX-434, Q-TD-48 (6): surplus 59 (east-airbase 50, fob-n-e 9) plus a rear account of 1 (pool
    # 200) passes OFFENSIVE's 60, but no node can pay it, so the lead's lift is undone. The undo
    # goes back to the cheapest-operation lift (budget and base account 2), not to the split's
    # base account of 1, so RECON (2) is still paid at east-airbase
    w = world(NEW_LIMITED)
    at_floor(w)
    w.stock["east-airbase"] += 50
    w.stock["fob-n-e"] += 9
    w.pool["ENEMY"] = 200
    w.director["ENEMY"].windows = 10
    spend = the_budget(w, upkeep=1)  # floor(59 x 0.02) + 1 - 2 = 0, the floor's RECON: 2
    assert spend == 2
    out = operations(w, spend)
    assert debits(out) == [("east-airbase", 2)]
    assert [p[0] for p in posted(w)] == ["RECON"]
    assert w.director["ENEMY"].budget == 2


def test_with_base_surplus_the_cheapest_operation_floor_lifts_the_base_account() -> None:
    # NX-434: surplus 50 at east-airbase (enough to deploy at), pool 200 (rear share 1). The
    # budget is 2 (RECON) as before NX-434; the base account is lifted to 2 like the capture
    # floor's, not left at 2 - 1, so RECON pays at the base instead of nowhere
    spend, out, _ = cheapest_window(50, 200)
    assert spend == 2 and debits(out) == [("east-airbase", 2)]
    assert cheapest_window(50, 200, windows=9)[0] == 0  # 1 + 1 - 2: not due, no floor
    w = world(NEW_LIMITED)  # 1,500 surplus, pool 8,000: the formula's 70 is above the floor
    w.director["ENEMY"].windows = 10
    assert the_budget(w) == 70


@given(
    free=st.one_of(st.just([0, 0, 0, 0]), st.lists(st.integers(0, 120), min_size=4, max_size=4)),
    pool=st.integers(0, 3000),
    upkeep=st.integers(0, 40),
    tier=st.sampled_from(["ALPHA", "BRAVO"]),
)
@settings(max_examples=40, deadline=None)
def test_the_cheapest_operation_floor_counts_only_what_the_window_can_pay(
    free: list[int], pool: int, upkeep: int, tier: ThreatTier
) -> None:
    # NX-434: a lift never exceeds base surplus + the rear share; with no base surplus, a lift
    # is paid at the source (no capture candidate: the night cap is spent)
    w = world(NEW_LIMITED)
    assert w.rules is not None and w.rules.director is not None
    at_floor(w)
    for n, f in zip(STATIC_BASES, free, strict=True):
        w.stock[n] += f
    w.pool["ENEMY"] = pool
    s = w.director["ENEMY"]
    s.last_flip, s.windows = 1, 9
    unlifted = the_budget(w, tier, upkeep=upkeep)
    s.windows = 10
    lifted = the_budget(w, tier, upkeep=upkeep)
    assert unlifted <= lifted <= max(unlifted, sum(free) + rear_share(w.rules.director, pool))
    if lifted > unlifted and sum(free) == 0:
        out = operations(w, lifted, tier)
        assert [n for n, _ in debits(out)] == ["static-rear"], (lifted, debits(out))


def surplus_world(free: int) -> World:
    """An unlimited Static (no pool) whose only surplus is `free` at east-airbase."""
    w = world(NEW_UNLIMITED)
    at_floor(w)
    w.stock["east-airbase"] += free
    return w


def test_a_capture_operation_surplus_and_pool_cannot_pay_is_not_forced() -> None:
    # Q-TD-34 (1): affordable means surplus + pool, and this Static has no pool. 59 is below
    # OFFENSIVE (60) and RETAKE has no target, so the window is the one without the floor
    w = surplus_world(59)
    assert floor_window(w, 10, spend=10) == floor_window(surplus_world(59), 9, spend=10)
    assert w.director["ENEMY"].budget == 10
    w = surplus_world(60)  # exactly OFFENSIVE: forced and paid there
    assert floor_window(w, 10, spend=10) == [("OFFENSIVE", "west-airbase")]
    assert w.rules is not None
    assert w.stock["east-airbase"] == w.rules.supply.starve_floor["east-airbase"]


def test_pool_money_the_window_cannot_spend_promotes_no_capture_operation() -> None:
    # Q-TD-48 (5): no base surplus and a 2000 pool (rear account floor(2000 x 0.005) = 10).
    # OFFENSIVE (60) is within surplus + pool but not payable this window, so the floor must
    # not promote it over what the rear account can buy: the window is the one without it
    def limited() -> World:
        w = world(NEW_LIMITED)
        at_floor(w)
        w.pool["ENEMY"] = 2000
        return w

    w = limited()
    assert floor_window(w, 10, spend=10) == floor_window(limited(), 9, spend=10)
    assert w.director["ENEMY"].budget == 10
    # with staging on, a wrongly promoted OFFENSIVE would be staged (it holds its cost and waits)
    # instead of failing to pay, so only the cap keeps it out
    w = world(config({"economy.legacy_rules": False, **LIMITED}))
    at_floor(w)
    w.pool["ENEMY"] = 2000
    floor_window(w, 10, spend=10)
    assert w.director["ENEMY"].staged == []
    assert w.director["ENEMY"].budget == 10


def test_the_rear_account_counts_toward_the_capture_floor() -> None:
    # Q-TD-48 (5), NX-434 (`_floor_cap`, shared by both floors): no base surplus, pool 6000 at
    # `source_spend_frac` 0.01, a rear account of 60 with a 60 budget: OFFENSIVE (ranked last at
    # priority 0.01) is forced and paid at the source; without the floor the window buys the
    # better-ranked cheap operations
    def rear_only() -> World:
        frac = {"director.source_spend_frac": 0.01, "director.op_priority.OFFENSIVE": 0.01}
        w = world(config({**NEW, **LIMITED, **frac}))
        at_floor(w)
        w.pool["ENEMY"] = 6000
        return w

    w = rear_only()
    assert floor_window(w, 10, spend=60) == [("OFFENSIVE", "west-airbase")]
    assert w.pool["ENEMY"] == 6000 - 60
    assert ("OFFENSIVE", "west-airbase") not in floor_window(rear_only(), 9, spend=60)


def test_a_promoted_capture_operation_that_cannot_pay_crowds_out_nothing() -> None:
    # Q-TD-48 (6), from CodeRabbit on #411: base surplus 50 at east-airbase plus a rear account of
    # 10 (pool 2000) passes the floor's 60, but OFFENSIVE pays at one node, and neither the base
    # (50) nor the rear account (10) can pay 60, so the window is the one without the floor
    def limited(free: int) -> World:
        w = world(NEW_LIMITED)
        at_floor(w)
        w.stock["east-airbase"] += free
        w.pool["ENEMY"] = 2000
        return w

    w = limited(50)  # 30 points: without the floor the window buys three RECON at the source
    assert floor_window(w, 10, spend=30) == floor_window(limited(50), 9, spend=30) != []
    assert w.director["ENEMY"].budget == 30
    w = limited(60)  # the base can pay all 60: the base account is lifted to it, not 60 - 10
    assert floor_window(w, 10, spend=10) == [("OFFENSIVE", "west-airbase")]


def test_legacy_rules_have_no_capture_floor() -> None:
    assert floor_window(world(LEGACY_LIMITED), 10) == floor_window(world(LEGACY_LIMITED), 0)


def test_the_floor_buys_the_cheapest_capture_operation_retake_over_offensive() -> None:
    # west-airbase lost at tick 1 gives RETAKE (50) a target next to OFFENSIVE (60)
    w = world(NEW_UNLIMITED)
    w.director["ENEMY"].lost["west-airbase"] = 1
    assert floor_window(w, 10) == [("RETAKE", "west-airbase")]
    assert w.director["ENEMY"].budget == 50


def test_the_floors_capture_operation_goes_before_better_ranked_cheaper_ones() -> None:
    # OFFENSIVE's priority at 0.01 ranks it below PROBE and RECON, which would spend 15 + 2s of
    # the lifted 60 first and leave OFFENSIVE unpaid; the floor selects it first
    w = world(config({**NEW, "director.op_priority.OFFENSIVE": 0.01}))
    assert floor_window(w, 10) == [("OFFENSIVE", "west-airbase")]


COUNTED = ("OFFENSIVE", "RETAKE", "PROBE")  # the ALPHA operations `max_ops` counts here


def test_the_floors_capture_operation_takes_one_slot_past_max_ops_never_two() -> None:
    # Q-TD-57 (NX-441): ALPHA runs one non-routine operation at a time (`max_ops.alpha` 1). With
    # the window-10 OFFENSIVE still on the board the floor due at window 20 runs a second one
    # (cap + 1); with both still on the board the floor due at window 30 lifts nothing
    w = world(NEW_UNLIMITED)
    assert floor_window(w, 10) == [("OFFENSIVE", "west-airbase")]
    pairs = floor_window(w, 20)
    assert w.director["ENEMY"].budget == 60
    two = [("OFFENSIVE", "fob-n-w"), ("OFFENSIVE", "west-airbase")]
    assert [p for p in pairs if p[0] in COUNTED] == two
    pairs = floor_window(w, 30)
    assert w.director["ENEMY"].budget == 30  # not lifted to 60
    assert [p for p in pairs if p[0] in COUNTED] == two
    assert w.director["ENEMY"].last_operation == 20


def test_a_probe_holding_alphas_one_slot_does_not_block_the_floor() -> None:
    # Q-TD-57 (NX-441): window 9 (floor not due) buys PROBE, which holds `max_ops.alpha` 1; the
    # floor due at window 10 still launches OFFENSIVE. Window 20, PROBE and OFFENSIVE still on the
    # board (cap + 1), it does not stack a third
    w = world(NEW_UNLIMITED)
    assert floor_window(w, 9) == CHEAP
    pairs = floor_window(w, 10)
    assert w.director["ENEMY"].budget == 60 and w.director["ENEMY"].last_operation == 10
    held = [("OFFENSIVE", "west-airbase"), ("PROBE", "fob-n-w")]
    assert [p for p in pairs if p[0] in COUNTED] == held
    pairs = floor_window(w, 20)
    assert w.director["ENEMY"].budget == 30 and w.director["ENEMY"].last_operation == 10
    assert [p for p in pairs if p[0] in COUNTED] == held


def test_with_the_floor_not_due_max_ops_holds_as_before() -> None:
    # PROBE holds ALPHA's one slot; window 9, the floor not due, with 100 points: OFFENSIVE (60)
    # is paid for but `max_ops.alpha` keeps it out
    w = world(NEW_UNLIMITED)
    assert floor_window(w, 9) == CHEAP
    pairs = floor_window(w, 9, spend=100)
    assert [p for p in pairs if p[0] in COUNTED] == [("PROBE", "fob-n-w")]
    assert w.director["ENEMY"].last_operation == 0


def test_only_the_floors_capture_operation_gets_the_extra_slot() -> None:
    # Q-TD-57: ALPHA's slot empty, the floor due, 100 points and spawn room for more than
    # OFFENSIVE's 6 units: OFFENSIVE takes the slot and PROBE (15) is not given the floor's one
    w = world(config({**NEW, "director.max_spawns_per_window": 20}))
    pairs = floor_window(w, 10, spend=100)
    assert [p for p in pairs if p[0] in COUNTED] == [("OFFENSIVE", "west-airbase")]


@given(
    gaps=st.lists(st.integers(1, 12), min_size=1, max_size=6),
    spends=st.lists(st.integers(0, 120), min_size=6, max_size=6),
    seed=st.integers(1, 50),
)
@settings(max_examples=25, deadline=None)
def test_the_floor_runs_at_most_one_operation_past_max_ops(
    gaps: list[int], spends: list[int], seed: int
) -> None:
    # Q-TD-57: ALPHA windows that never end an operation; the operations `max_ops` counts never
    # exceed cap + 1, and past the cap only when a capture operation is among them
    w = world(NEW_UNLIMITED, seed)
    assert w.rules is not None and w.rules.director is not None
    cap = w.rules.director.max_ops["ALPHA"]
    assert cap is not None
    routine = _routine(w.rules.director)
    windows = 0
    for gap, spend in zip(gaps, spends, strict=False):
        windows += gap
        counted = [p for p in floor_window(w, windows, spend) if p[0] not in routine]
        assert len(counted) <= cap + 1
        assert len(counted) <= cap or any(p[0] in CAPTURE_OPS for p in counted)


@given(
    windows=st.integers(8, 12),
    free=st.lists(st.integers(0, 300), min_size=4, max_size=4),
    pool=st.integers(0, 3000),
    tier=st.sampled_from(["ALPHA", "BRAVO"]),
)
@settings(max_examples=25, deadline=None)
def test_the_floor_never_lifts_the_budget_past_surplus_plus_pool(
    windows: int, free: list[int], pool: int, tier: ThreatTier
) -> None:
    w = world(NEW_LIMITED)
    at_floor(w)
    for n, f in zip(STATIC_BASES, free, strict=True):
        w.stock[n] += f
    w.pool["ENEMY"] = pool
    s = w.director["ENEMY"]
    s.windows = windows
    spend = the_budget(w, tier)
    out = operations(w, spend, tier)
    assert s.budget <= sum(free) + pool
    assert sum(a for _, a in debits(out)) <= s.budget
    # Q-TD-54: the floor's clock moves only when a capture operation posts (staging is off here)
    assert (s.last_operation == windows) == any(p[0] in CAPTURE_OPS for p in posted(w))


def test_legacy_rules_keep_the_tier_budget_and_ignore_the_pool() -> None:
    w = world(LEGACY_LIMITED)
    assert the_budget(w, "BRAVO", upkeep=100) == 80  # min(director.budget.bravo, 1500)
    at_floor(w)
    assert the_budget(w, "BRAVO") == 0  # the rear pool adds nothing (Q-TD-5)


@pytest.mark.parametrize(
    ("period", "armors", "budget"),
    [
        (1, 1, 9),  # owed 3 a window: 15 - 2 x 3
        (20, 1, 13),  # NX-426: owed ceil(3/20) = 1: 15 - 2 x 1
        (4, 2, 11),  # owed ceil(3/4 + 3/4) = 2, one rounding for the side: 15 - 2 x 2
    ],
)
def test_the_window_sets_the_budget_from_the_pool_and_the_owed_upkeep(
    period: int, armors: int, budget: int
) -> None:
    w = world(config({
        **NEW, **LIMITED, "economy.upkeep.ENEMY_ARMOR": 3,
        "economy.upkeep_period.ENEMY_ARMOR": period,
    }))  # fmt: skip
    at_floor(w)  # surplus 0
    w.pool["ENEMY"] = 2940
    assert w.rules is not None
    for _ in range(armors):
        pos = Vec2(*w.rules.roads.pos["fob-n-e"])
        armor = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", pos)
        armor.last_node = armor.home_base = "fob-n-e"
    w.campaign.tick = w.campaign.running_ticks = 599
    step(w, [])  # the economy window, then the decision window, in one tick (EC-10)
    # income 30 + FOB 5 + FOB 5 + AIRBASE 10 + HQ 10 = 60: pool 3000 (upkeep is paid at fob-n-e);
    # PATTERN_OF_LIFE: 0 + floor(3000 x 0.005) - 2 x owed (upkeep.owed, the per-window average)
    assert w.director["ENEMY"].budget == budget


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"director.spend_frac.alpha": 0.001}, "pattern_of_life <= alpha <= bravo"),
        ({"director.spend_frac.bravo": 0.01}, "pattern_of_life <= alpha <= bravo"),
    ],
)
def test_the_loader_requires_ordered_tier_fractions(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        shipped_config(overrides)


def test_the_cost_envelope_follows_the_rules_in_force() -> None:
    small = {
        "director.spend_frac.pattern_of_life": 0.001,
        "director.spend_frac.alpha": 0.002,
        "director.spend_frac.bravo": 0.004,
    }
    shipped_config(small)  # legacy rules: the envelope is still the largest tier budget (80)
    # storage with every node held: 2000 + 2 AIRBASE 2000 + HQ 2000 + 6 FOB 1000 = 14000;
    # floor(0.004 x 14000) = 56 < OFFENSIVE's 60
    with pytest.raises(ConfigError, match=r"OFFENSIVE: cost 60 is above .*14000 \(56\)"):
        shipped_config({**NEW, **small})
    shipped_config(NEW)  # floor(0.0534 x 14000) = 747: the shipped catalog fits


# --- EC-13: one spawn rule, Director --------------------------------------------------------------


def test_an_operation_draws_its_cost_once_at_the_base_where_all_its_units_spawn() -> None:
    w = world(NEW_UNLIMITED)
    before = dict(w.stock)
    out = operations(w, 60)
    assert spawns(out) == ["east-airbase"] * 6  # a landing base: the jets spawn there too
    assert debits(out) == [("east-airbase", 60)]
    assert w.stock["east-airbase"] == before["east-airbase"] - 60
    assert all(w.stock[n] == before[n] for n in STATIC_BASES if n != "east-airbase")


def test_an_unlimited_static_spends_one_account_at_bases_and_its_source() -> None:
    w = world(NEW_UNLIMITED)
    assert w.rules is not None and w.rules.director is not None
    purse = _Purse.of(70, None, w.rules.director)
    assert purse == _Purse(70, 0, one=True)  # no pool: no rear share, the whole budget
    out: list[Event] = []
    for _ in range(2):  # 40 at static-hq (a base pays), then 40 more no longer fit the 30 left
        _post_and_spawn(w, w.rules, "ENEMY", one_unit_op(40), out, lambda n: 40 * n, purse)
    assert debits(out) == [("static-hq", 40)] and purse.base == 30
    at_floor(w)  # no base can pay: the source, on the same account, debits no stock
    _post_and_spawn(w, w.rules, "ENEMY", one_unit_op(30), out, lambda n: 30 * n, purse)
    _post_and_spawn(w, w.rules, "ENEMY", one_unit_op(1), out, lambda n: n, purse)
    assert spawns(out) == ["static-hq", "static-rear"] and purse.base == 0
    assert debits(out) == [("static-hq", 40)]  # the 1 no longer fits: dropped


def test_rear_pool_money_buys_only_units_that_spawn_at_the_source() -> None:
    w = world(NEW_LIMITED)
    out = operations(w, 60)  # rear account floor(8000 x 0.005) = 40, base account 20
    assert debits(out) == [] and spawns(out) == []  # OFFENSIVE (60) fits neither: dropped
    assert w.pool["ENEMY"] == 8000 and w.stock["east-airbase"] == 1000
    w = world(NEW_LIMITED)
    out = operations(w, 100)  # base account 60: the bases pay it, the pool pays nothing
    assert debits(out) == [("east-airbase", 60)] and w.pool["ENEMY"] == 8000


def one_unit_op(cost: int, *kinds: UnitKind) -> ops.Candidate:
    """A STAGE operation at static-hq, one unit of each kind (ENEMY_ARMOR by default), costing
    `cost` (a hand-built catalog entry)."""
    job = JobTemplate("STAGE", "target", kinds or ("ENEMY_ARMOR",), len(kinds or (1,)))
    op = OperationRules("TEST", "NODE", (), cost, frozenset({"ALPHA"}), (job,), None, Fraction(1))
    return ops.Candidate(op, "static-hq", None, ((ops.Where("static-hq"),),))


def test_each_account_pays_only_its_own_spawns() -> None:
    w = world(NEW_LIMITED)
    assert w.rules is not None
    purse = _Purse(70, 40)
    out: list[Event] = []
    for _ in range(3):
        _post_and_spawn(w, w.rules, "ENEMY", one_unit_op(40), out, lambda n: 40 * n, purse)
    # 40 of the base account at static-hq; the next 40 no longer fits it (30 left) and goes to
    # the source on the rear account (40); the third fits neither and is dropped
    assert debits(out) == [("static-hq", 40), ("static-rear", 40)]
    assert (purse.base, purse.rear) == (30, 0) and w.pool["ENEMY"] == 8000 - 40


def test_the_rear_account_is_never_more_than_the_budget() -> None:
    dr = NEW_LIMITED.rules.director
    assert dr is not None
    assert _Purse.of(100, 8000, dr) == _Purse(60, 40)
    assert _Purse.of(20, 8000, dr) == _Purse(0, 20)  # the reserve took the budget below 40


def thin(overrides: dict[str, object] | None = None) -> tuple[World, Rules]:
    """A limited Static whose bases each hold 29 above their floor (116 in all, none enough to
    deploy at: `logistics.forward_deploy_min_surplus` is 50), with the shipped garrison quotas
    and no opening garrison, at Pattern of Life."""
    w = world(config({**NEW, **LIMITED, **(overrides or {})}), garrison=True)
    for e in list(w.entities()):
        if e.home is not None:
            w.remove(e.id)
    assert w.rules is not None
    for n in STATIC_BASES:
        w.stock[n] = w.rules.supply.starve_floor[n] + 29
    w.director["ENEMY"].tier = "PATTERN_OF_LIFE"
    return w, w.rules


def test_the_capture_slot_spawns_at_the_source_only_on_the_rear_account() -> None:
    for rear, want in ((40, []), (60, [("static-rear", 60)])):
        w, rules = thin()
        assert rules.director is not None
        w.campaign.running_ticks = rules.director.offensive_ticks  # the slot is due
        purse, out = _Purse(0, rear), list[Event]()
        _capture_slot(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"],
                      rules.director, w.campaign.running_ticks + 1, out, purse)  # fmt: skip
        # a capture operation costs 50 or 60, more than any base can pay: the source or nothing
        assert debits(out) == want and purse.rear == rear - sum(a for _, a in want)


def test_an_unlimited_capture_slot_spawns_at_its_source_on_the_real_surplus() -> None:
    w, rules = thin({"economy.unlimited.ENEMY": True})
    assert rules.director is not None and "ENEMY" not in w.pool
    w.campaign.running_ticks = rules.director.offensive_ticks
    purse, out = _Purse.of(0, None, rules.director), list[Event]()
    _capture_slot(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"],
                  rules.director, w.campaign.running_ticks + 1, out, purse)  # fmt: skip
    # one account, the real surplus (116): the capture operation spawns at the source, unpaid
    assert set(spawns(out)) == {"static-rear"} and debits(out) == []


def test_a_pol_convoy_at_the_source_spends_the_windows_rear_account() -> None:
    w, rules = thin({"director.pol.convoy_cost": 30})
    assert rules.director is not None
    purse, out = _Purse(0, 40), list[Event]()
    _convoys(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], rules.director,
             out, purse)  # fmt: skip
    assert debits(out) == [("static-rear", 30)] and purse.rear == 10


def test_the_paying_base_must_host_every_kind_of_the_operation() -> None:
    c = NEW_LIMITED
    sup = c.rules.supply
    no_ground = {**sup.spawns, "GROUND": sup.spawns["GROUND"] - {"east-airbase"}}
    pair = one_unit_op(30, "ENEMY_STRIKE_FIGHTER", "ENEMY_ARMOR")
    for spawns_, want in ((sup.spawns, "east-airbase"), (no_ground, "static-rear")):
        rules = dataclasses.replace(c.rules, supply=dataclasses.replace(sup, spawns=spawns_))
        w = world(dataclasses.replace(c, rules=rules))
        out: list[Event] = []
        _post_and_spawn(w, rules, "ENEMY", pair, out, lambda n: 15 * n, _Purse(40, 40))
        # the jet picks east-airbase; without a ground spawn there the armor cannot come along
        assert spawns(out) == [want, want] and debits(out) == [(want, 30)]


def test_no_stock_means_no_spawn_and_nothing_posted() -> None:
    w = world(NEW_LIMITED)
    assert w.rules is not None
    at_floor(w)
    w.pool["ENEMY"] = 59
    out: list[Event] = []
    _post_and_spawn(w, w.rules, "ENEMY", one_unit_op(60), out, lambda n: 60 * n, _Purse(60, 60))
    assert [e for e in out if e.kind in ("UnitSpawned", "JobCreated", "SupplyConsumed")] == []
    assert w.pool["ENEMY"] == 59
    w.pool["ENEMY"] = 60  # exactly the cost: it launches at the source
    _post_and_spawn(w, w.rules, "ENEMY", one_unit_op(60), out, lambda n: 60 * n, _Purse(60, 60))
    assert debits(out) == [("static-rear", 60)] and w.pool["ENEMY"] == 0
    w = world(NEW_UNLIMITED)
    at_floor(w)
    out = operations(w, 60)  # an unlimited pool never runs out (EC-15): the source, unpaid
    assert spawns(out) == ["static-rear"] * 6 and debits(out) == []


def test_a_capture_launch_stamps_the_window_of_the_last_operation() -> None:
    w = world(NEW_UNLIMITED)
    w.director["ENEMY"].windows = 7
    operations(w, 60)
    assert ("OFFENSIVE", "west-airbase") in posted(w)
    assert w.director["ENEMY"].last_operation == 7
    w = world(NEW_LIMITED)
    w.director["ENEMY"].windows = 8
    at_floor(w)
    out = operations(w, 40)  # all on the rear account (40): launched, but none captures
    assert {n for n, _ in debits(out)} == {"static-rear"}
    assert not [p for p in posted(w) if p[0] in CAPTURE_OPS]
    assert w.director["ENEMY"].last_operation == 0  # Q-TD-54: no stamp


@pytest.mark.parametrize("pool", [8000, 2000])
def test_thin_bases_push_operations_to_the_source_and_the_pool_pays_its_share_a_window(
    pool: int,
) -> None:
    c = shipped_config({**NEW, **LIMITED, "director.tier.start": "BRAVO"})
    w = start_campaign(CAMPAIGN_ID, 3, c)
    assert w.rules is not None
    windows = rear_spawns = 0
    while windows < 6:
        for n in STATIC_BASES:  # well stocked by count, thin above the floor
            w.stock[n] = w.rules.supply.starve_floor[n] + 55
        w.pool["ENEMY"] = pool
        out = step(w, [])
        if w.campaign.running_ticks % 600 == 0:
            windows += 1
            # the pool at the decision window is at most `pool` + one window's income (60):
            # 8000 -> rear account 40; 2000 -> 10 (BRAVO's budget is 11 + the rear account)
            drawn = sum(a for n, a in debits(out) if n == "static-rear")
            assert drawn <= (min(8000, pool + 60) * 5) // 1000
            rear_spawns += drawn > 0
    assert rear_spawns > 0 if pool == 8000 else True  # the fallback to the source happened


def test_legacy_rules_still_split_the_cost_over_the_bases_and_never_touch_the_pool() -> None:
    w = world(LEGACY_LIMITED)
    out = operations(w, 60)
    assert sum(a for _, a in debits(out)) == 60 and w.pool["ENEMY"] == 8000
    assert {n for n, _ in debits(out)} <= set(STATIC_BASES)


def garrison_world(c: CampaignConfig) -> World:
    """Only GARRISON_UPKEEP in the catalog, the shipped quotas, no opening garrison."""
    dr = c.rules.director
    assert dr is not None
    rules = dataclasses.replace(
        c.rules,
        director=dataclasses.replace(
            dr, operations=tuple(o for o in dr.operations if o.id == "GARRISON_UPKEEP")
        ),
    )
    w = start_campaign(CAMPAIGN_ID, 1, dataclasses.replace(c, rules=rules))
    for e in list(w.entities()):
        if e.home is not None:
            w.remove(e.id)
    return w


def test_a_garrison_replacement_pays_at_its_own_base_never_the_source() -> None:
    w = garrison_world(NEW_LIMITED)
    at_floor(w)
    w.stock["static-hq"] += 8  # GARRISON_UPKEEP's 8, only here
    out = operations(w, 80)
    assert debits(out) == [("static-hq", 8)] and spawns(out) == ["static-hq"]
    assert w.pool["ENEMY"] == 8000  # a fixed base never falls back to the source


# --- EC-13: one spawn rule, JOIN ------------------------------------------------------------------


def coalition(overrides: dict[str, object]) -> World:
    c = shipped_config(overrides)
    rules = dataclasses.replace(c.rules, campaign=None, tasking=None)
    return start_campaign(CAMPAIGN_ID, 1, dataclasses.replace(c, rules=rules))


def test_a_viewer_sanctuary_spawn_is_free_with_the_switch_on() -> None:
    w = coalition({**NEW, **LIMITED})
    out = step(w, [join(1, "STRIKE", hold=True)])
    assert spawns(out) == ["haven"] and debits(out) == [] and w.pool["COALITION"] == 6000


def test_a_viewer_sanctuary_spawn_draws_its_loadout_from_the_pool_with_the_switch_off() -> None:
    w = coalition({**NEW, **LIMITED, "economy.free_viewer_spawn": False})
    out = step(w, [join(1, "STRIKE", hold=True)])
    assert spawns(out) == ["haven"] and debits(out) == [("haven", 20)]
    assert w.pool["COALITION"] == 6000 - 20


def test_a_viewer_join_the_pool_cannot_pay_is_refused_no_stock() -> None:
    w = coalition({**NEW, **LIMITED, "economy.free_viewer_spawn": False})
    w.pool["COALITION"] = 19
    out = step(w, [join(1, "STRIKE", hold=True)])
    assert [e.reason for e in out if isinstance(e, CommandRejected)] == ["NO_STOCK"]
    assert spawns(out) == [] and w.pool["COALITION"] == 19


def test_legacy_rules_keep_sanctuary_spawns_free_whatever_the_switch() -> None:
    w = coalition({**LIMITED, "economy.free_viewer_spawn": False})
    w.pool["COALITION"] = 0
    out = step(w, [join(1, "STRIKE", hold=True)])
    assert spawns(out) == ["haven"] and debits(out) == []


def test_an_unlimited_coalition_spawns_with_the_switch_off_and_pays_nothing() -> None:
    w = coalition({**NEW, "economy.free_viewer_spawn": False})
    out = step(w, [join(1, "STRIKE", hold=True)])
    assert spawns(out) == ["haven"] and debits(out) == []


# --- EC-8: the performance guard ------------------------------------------------------------------


def test_a_join_at_the_guard_waits_in_the_reserve_queue() -> None:
    w = coalition({**NEW, "sim.max_live_units_per_side": 1})
    assert w.rules is not None  # no coalition mover live yet (facilities are STATIC)
    movers = [e for e in w.entities() if w.rules.domain[e.kind] != "STATIC"]
    assert [e for e in movers if e.side == "COALITION"] == []
    out = step(w, [join(1, "STRIKE", hold=True), join(2, "STRIKE", hold=True)])
    assert spawns(out) == ["haven"]  # the viewer cap is 500, the guard 1
    assert [e.kind for e in out if e.kind == "ReserveQueueJoined"] == ["ReserveQueueJoined"]
    legacy = coalition({"sim.max_live_units_per_side": 1})  # read only with legacy rules off
    assert spawns(step(legacy, [join(1, "STRIKE", hold=True), join(2, "STRIKE", hold=True)])) == [
        "haven",
        "haven",
    ]


def test_the_guard_bounds_the_directors_new_units() -> None:
    w = world(config({**NEW, "sim.max_live_units_per_side": 3}))
    assert 0 < len(spawns(operations(w, 80, "BRAVO"))) <= 3  # the guard's room, not BRAVO's cap
    w = world(config({**NEW, "sim.max_live_units_per_side": 3}))
    for _ in range(3):
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    assert spawns(operations(w, 80, "BRAVO")) == []  # no room at all
    w = world(config({"sim.max_live_units_per_side": 3}))  # legacy rules: the guard is not read
    assert len(spawns(operations(w, 80, "BRAVO"))) > 3


def refusals(out: list[Event]) -> list[tuple[str, str, int, int]]:
    return [(e.side, e.reason, e.operations, e.units) for e in out if e.kind == "SpawnRefused"]


def test_a_director_operation_stopped_by_the_guard_is_counted() -> None:
    # NX-412 part 5a (EC-8, Q-TD-34 (5)): no room at all, so every operation the budget allows is
    # refused by the guard, in one event for the window
    w = world(config({**NEW, "sim.max_live_units_per_side": 3}))
    for _ in range(3):
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    [(side, reason, n, units)] = refusals(operations(w, 80, "BRAVO"))
    assert (side, reason) == ("ENEMY", "GUARD") and n >= 1 and units >= 1


def test_no_refusal_while_the_guard_has_room() -> None:
    out = operations(world(NEW_UNLIMITED), 80, "BRAVO")  # the shipped guard, 1000
    assert spawns(out) and refusals(out) == []
    out = operations(world(config({**NEW, "sim.max_live_units_per_side": 3})), 0, "BRAVO")
    assert refusals(out) == []  # no budget: the budget, not the guard, stops everything
    c = config({**NEW, "sim.max_live_units_per_side": 3})
    assert c.rules.director is not None  # the loader refuses 0: set it on the rules
    dr = dataclasses.replace(c.rules.director, max_spawns_per_window=0)
    w = world(dataclasses.replace(c, rules=dataclasses.replace(c.rules, director=dr)))
    for _ in range(3):
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    out = operations(w, 80, "BRAVO")
    assert refusals(out) == [] and spawns(out) == []  # anti-spam stops them first: not counted


def test_the_legacy_tier_cap_refusal_is_counted_as_tier_cap() -> None:
    w = world(config({}))  # legacy rules: director.max_live_units.bravo binds, not the guard
    assert w.rules is not None and w.rules.director is not None
    for _ in range(w.rules.director.max_live_units["BRAVO"]):
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    [(side, reason, n, _)] = refusals(operations(w, 80, "BRAVO"))
    assert (side, reason) == ("ENEMY", "TIER_CAP") and n >= 1
    assert refusals(operations(world(config({})), 80, "BRAVO")) == []  # room left: none


def test_a_pol_convoy_stopped_by_the_guard_is_counted() -> None:
    for cap, want in ((1, [("ENEMY", "GUARD", 1, 1)]), (1000, [])):
        w, rules = thin({"director.pol.convoy_cost": 30, "sim.max_live_units_per_side": cap})
        assert rules.director is not None and rules.director.convoy_slots == 1
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))  # the guard's one mover
        out: list[Event] = []
        _convoys(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], rules.director,
                 out, _Purse(0, 40))  # fmt: skip
        assert refusals(out) == want
        assert bool(debits(out)) == (cap == 1000)  # refused: nothing spawned or paid
    w, rules = thin({"director.pol.convoy_cost": 30, "sim.max_live_units_per_side": 1})
    assert rules.director is not None
    w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    out = list[Event]()
    no_spawns = dataclasses.replace(rules.director, max_spawns_per_window=0)
    _convoys(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], no_spawns,
             out, _Purse(0, 40))  # fmt: skip
    assert refusals(out) == [] and debits(out) == []  # anti-spam stopped it first: not counted


def test_a_capture_slot_stopped_by_the_guard_is_counted() -> None:
    for cap in (1, 1000):
        w, rules = thin({"sim.max_live_units_per_side": cap})
        assert rules.director is not None
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))  # the guard's one mover
        w.campaign.running_ticks = rules.director.offensive_ticks  # the slot is due
        out = list[Event]()
        _capture_slot(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"],
                      rules.director, w.campaign.running_ticks + 1, out, _Purse(0, 60))  # fmt: skip
        if cap == 1:  # the rear account could pay, the guard says no: counted, nothing paid
            assert [r[:2] for r in refusals(out)] == [("ENEMY", "GUARD")] and debits(out) == []
        else:
            assert refusals(out) == [] and [n for n, _ in debits(out)] == ["static-rear"]


# --- determinism, save and load, the mirror -------------------------------------------------------


def run(w: World, ticks: int, commands: dict[int, list[Any]] | None = None) -> list[Event]:
    out: list[Event] = []
    for _ in range(ticks):
        tick = w.campaign.tick + 1
        batch = [c.model_copy(update={"target_tick": tick}) for c in (commands or {}).get(tick, [])]
        out += step(w, batch)
    return out


JOINS = {1: [join(1, "STRIKE", "fob-n-w"), join(2, "RECON", hold=True)], 700: [join(3, "STRIKE")]}


@pytest.mark.parametrize(
    "overrides",
    [
        NEW,
        {**NEW, **LIMITED, "economy.free_viewer_spawn": False},
        {**NEW, "sim.max_live_units_per_side": 24},  # 22 Static movers open: SpawnRefused
    ],
    ids=["unlimited", "limited-switch-off", "guard-binding"],
)
def test_legacy_off_runs_deterministically(overrides: dict[str, object]) -> None:
    def once() -> tuple[str, list[dict[str, Any]]]:
        w = start_campaign(CAMPAIGN_ID, 99, shipped_config(overrides))
        events = run(w, 1300, JOINS)
        return state_hash(w), [e.model_dump() for e in events]

    first = once()
    assert any(e["kind"] == "UnitSpawned" and e["owner_kind"] == "ENEMY_DIRECTOR" for e in first[1])
    refused = any(e["kind"] == "SpawnRefused" for e in first[1])
    assert refused == ("sim.max_live_units_per_side" in overrides)
    assert once() == first


def test_the_cheapest_operation_floor_runs_deterministically() -> None:
    # NX-434: the floor's RECON paid at the source, twice from seed 1
    def once() -> tuple[str, list[dict[str, Any]]]:
        _, out, w = cheapest_window(0, 400)
        return state_hash(w), [e.model_dump() for e in out]

    first = once()
    assert any(e["kind"] == "UnitSpawned" for e in first[1])
    assert once() == first


def test_the_capture_clock_runs_deterministically() -> None:
    # Q-TD-54: nine windows of cheap operations, then the floor's OFFENSIVE, twice from seed 1
    def once() -> tuple[str, list[tuple[str, str]]]:
        w = world(NEW_UNLIMITED)
        cheap_windows(w, 1, 9)
        w.boards["ENEMY"].clear()
        floor_window(w, 10)
        return state_hash(w), posted(w)

    first = once()
    assert first[1] == [("OFFENSIVE", "west-airbase")]
    assert once() == first


def test_the_floor_past_max_ops_runs_deterministically() -> None:
    # Q-TD-57: PROBE holds ALPHA's one slot, then the floor's OFFENSIVE launches past it, twice
    def once() -> tuple[str, list[tuple[str, str]]]:
        w = world(NEW_UNLIMITED)
        floor_window(w, 9)
        floor_window(w, 10)
        return state_hash(w), posted(w)

    first = once()
    assert ("OFFENSIVE", "west-airbase") in first[1] and ("PROBE", "fob-n-w") in first[1]
    assert once() == first


def test_the_capture_floor_runs_deterministically() -> None:
    # ALPHA's budget is 30 (1,500 x 0.02), below every capture operation, and the capture slot
    # runs only at Pattern of Life: a CAPTURE job here comes from the cadence floor (Q-TD-42)
    c = shipped_config({**NEW, "director.cadence_windows": 1, "director.tier.start": "ALPHA"})

    def run_once() -> tuple[str, list[dict[str, Any]]]:
        w = start_campaign(CAMPAIGN_ID, 99, c)
        events = run(w, 1300)
        return state_hash(w), [e.model_dump() for e in events]

    first = run_once()
    assert any(e["kind"] == "JobCreated" and e["job_kind"] == "CAPTURE" for e in first[1])
    assert run_once() == first


def test_save_and_load_mid_window_resume_identically() -> None:
    c = shipped_config({**NEW, **LIMITED, "economy.free_viewer_spawn": False})
    w = start_campaign(CAMPAIGN_ID, 5, c)
    run(w, 900, JOINS)  # one director window run, the next half way
    assert w.director["ENEMY"].windows == 1
    copy = load(save(w))
    copy.rules = c.rules
    assert state_hash(copy) == state_hash(w)
    assert [e.model_dump() for e in run(copy, 700)] == [e.model_dump() for e in run(w, 700)]
    assert state_hash(copy) == state_hash(w)


def test_a_snapshot_with_an_operation_after_the_windows_run_is_refused() -> None:
    w = start_campaign(CAMPAIGN_ID, 5, NEW_LIMITED)
    raw = msgpack.unpackb(save(w), raw=False, strict_map_key=False)
    raw["director"]["ENEMY"]["last_operation"] = 1  # no window has run
    with pytest.raises(ValueError, match="an operation launched after the windows run"):
        load(msgpack.packb(raw, use_bin_type=True))


_MIRROR: tuple[tuple[UnitKind, UnitKind], ...] = (
    ("STRIKE_FIGHTER", "ENEMY_STRIKE_FIGHTER"),
    ("RECON_UAV", "ENEMY_RECON_UAV"),
)


@given(pair=st.sampled_from(_MIRROR), pool=st.integers(0, 40))
@settings(max_examples=40, deadline=None)
def test_with_the_switch_off_mirrored_source_spawns_cost_the_same(
    pair: tuple[UnitKind, UnitKind], pool: int
) -> None:
    """EC-13 parity: a coalition viewer's sanctuary spawn and a Static spawn at its source, of the
    mirrored kind at the same cost, draw the same from the same pool or both refuse."""
    w = world(config({**NEW, **LIMITED, "economy.free_viewer_spawn": False}))
    rules: Rules = w.rules  # type: ignore[assignment]
    at_floor(w)  # no Static base can pay: the Static spawns at its source
    w.pool = {"COALITION": pool, "ENEMY": pool}
    role = "STRIKE" if pair[0] == "STRIKE_FIGHTER" else "RECON"
    joined = step(w, [join(1, role, hold=True)])
    cost = rules.supply.loadout_cost[pair[1]]
    out: list[Event] = []
    paid = _post_and_spawn(w, rules, "ENEMY", one_unit_op(cost, pair[1]), out, lambda n: cost * n)
    assert rules.supply.loadout_cost[pair[0]] == cost
    assert (spawns(joined) == ["haven"]) == (paid == 1) == (pool >= cost)
    assert w.pool["COALITION"] == w.pool["ENEMY"]
    assert [a for _, a in debits(joined)] == [a for _, a in debits(out)]
