"""NX-500 (ECONOMY EC-7 "Surplus reference"; Q-TD-125 owner (a), Q-TD-132 (A)): the Director's
surplus is stock above R(n) = max(ceil(`director.surplus_ref_frac` x `node_max_stock`), the
starvation floor), fixed at load in `Supply.surplus_ref`; every other floor reader stays on the
floor.

Expected numbers are worked by hand from the shipped strait-1 values: `node_max_stock` AIRBASE
and HQ 2,000, FOB 1,000, BRIDGE 0; `starve_threshold` 0.25 (floors 500 and 250); the Static's
bases start at 1,000 (east-airbase, static-hq) and 500 (fob-n-e, fob-s-e); `spend_frac.alpha`
0.02. Every config goes through `shipped_config` overrides, so the loader's key path is the one
under test, not a hand-built rules object.
"""

import dataclasses
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID

from nexus.contracts.gen.events.event import Event
from nexus.core.director import budget, surplus
from nexus.core.fog import side_view
from nexus.core.launch import _capture_slot, _convoys, _floor_cap, _Purse, _surplus_purse
from nexus.core.logistics import keeps
from nexus.core.rearm import is_starved
from nexus.core.step import step
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config

STATIC_BASES = ("east-airbase", "fob-n-e", "fob-s-e", "static-hq")
DEFAULT = shipped_config({})
LOW_FLOOR = shipped_config({"logistics.starve_threshold": 0.05})
# R at strait-1 by hand: AIRBASE and HQ ceil(0.25 x 2000), FOB ceil(0.25 x 1000), BRIDGE 0
STRAIT_1_R = {
    "west-airbase": 500, "east-airbase": 500, "static-hq": 500,
    "fob-n-w": 250, "fob-s-w": 250, "cross-n": 250, "cross-s": 250, "fob-n-e": 250, "fob-s-e": 250,
    "bridge-n": 0, "bridge-s": 0,
}  # fmt: skip


def world(c: CampaignConfig, seed: int = 1) -> World:
    return start_campaign(CAMPAIGN_ID, seed, c)


def static_surplus(w: World, stock: dict[str, int] | None = None) -> int:
    assert w.rules is not None
    return surplus(side_view(w, "ENEMY"), w.rules, w.stock if stock is None else stock)


def alpha_budget(w: World) -> int:
    assert w.rules is not None
    s = w.director["ENEMY"]
    s.tier = "ALPHA"
    return budget(s, side_view(w, "ENEMY"), w.rules, w.stock, 0, 0)  # no pool, no upkeep


# --- the reference at the default -------------------------------------------------------------


def test_at_the_default_the_reference_is_the_floor_at_every_strait_1_node() -> None:
    sup = DEFAULT.rules.supply
    assert dict(sup.surplus_ref) == STRAIT_1_R
    assert dict(sup.surplus_ref) == dict(sup.starve_floor)
    assert static_surplus(world(DEFAULT)) == 1500  # 500 + 500 + 250 + 250, the spend_frac basis


def test_at_the_default_the_surplus_is_the_stock_above_the_floor_for_any_stock() -> None:
    floors = DEFAULT.rules.supply.starve_floor
    w = world(DEFAULT)

    @given(st.dictionaries(st.sampled_from(sorted(floors)), st.integers(0, 2000)))
    def check(stock: dict[str, int]) -> None:
        old = sum(max(0, stock.get(n, 0) - floors[n]) for n in STATIC_BASES)
        assert static_surplus(w, stock) == old

    check()


# --- a lower floor changes logistics only (Q-TD-125) ------------------------------------------


def test_a_lower_floor_leaves_the_surplus_and_the_budget_where_they_were() -> None:
    sup = LOW_FLOOR.rules.supply
    assert sup.starve_floor["east-airbase"] == 100 and sup.starve_floor["fob-n-e"] == 50
    assert dict(sup.surplus_ref) == STRAIT_1_R  # max(500, 100), max(250, 50)
    low, base = world(LOW_FLOOR), world(DEFAULT)
    assert static_surplus(low) == static_surplus(base) == 1500
    assert alpha_budget(low) == alpha_budget(base) == 30  # floor(1500 x 0.02)


def test_before_nx_500_the_same_lower_floor_made_the_static_richer() -> None:
    # the pre-change rule, the surplus above the floor: 900 + 900 + 450 + 450 = 2,700 at 0.05
    low = world(LOW_FLOOR)
    assert low.rules is not None
    old_sup = dataclasses.replace(low.rules.supply, surplus_ref=low.rules.supply.starve_floor)
    low.rules = dataclasses.replace(low.rules, supply=old_sup)
    assert static_surplus(low) == 2700
    assert alpha_budget(low) == 54  # floor(2700 x 0.02), against 30 with the reference


def test_a_lower_floor_leaves_the_cadence_cap_and_the_surplus_purses_unchanged() -> None:
    def spends(c: CampaignConfig) -> tuple[int, Any]:
        w = world(c)
        assert w.rules is not None
        view, purse = side_view(w, "ENEMY"), _Purse(0, 7, False)
        return _floor_cap(w, w.rules, view, purse), _surplus_purse(view, w.rules, w, purse)

    assert spends(LOW_FLOOR) == spends(DEFAULT) == (1500 + 7, _Purse(1500, 7, False))


def test_a_lower_floor_still_moves_starved_and_keep() -> None:
    low, base = world(LOW_FLOOR), world(DEFAULT)
    for w in (low, base):
        w.stock["east-airbase"] = 300
    assert low.rules is not None and base.rules is not None
    assert not is_starved(low, low.rules, "east-airbase")  # 300 >= 100
    assert is_starved(base, base.rules, "east-airbase")  # 300 < 500
    # a run to a base starving under both floors: every source keeps its floor, not the reference
    for w in (low, base):
        w.stock["east-airbase"] = 40
    assert keeps(low, low.rules, "ENEMY", "east-airbase")["fob-n-e"] == 50
    assert keeps(base, base.rules, "ENEMY", "east-airbase")["fob-n-e"] == 250


# --- the max, and a raised reference ----------------------------------------------------------


def test_a_floor_raised_above_the_reference_shrinks_the_surplus() -> None:
    high = shipped_config({"logistics.starve_threshold": 0.4})
    sup = high.rules.supply
    assert sup.surplus_ref["east-airbase"] == 800 and sup.surplus_ref["fob-n-e"] == 400
    assert static_surplus(world(high)) == 600  # 200 + 200 + 100 + 100: what the bases can pay


def test_a_raised_reference_lowers_the_surplus() -> None:
    raised = shipped_config({"director.surplus_ref_frac": 0.4})
    sup = raised.rules.supply
    assert sup.starve_floor["east-airbase"] == 500  # the floor does not move
    assert sup.surplus_ref["east-airbase"] == 800 and sup.surplus_ref["fob-n-e"] == 400
    w = world(raised)
    assert static_surplus(w) == 600
    assert alpha_budget(w) == 12  # floor(600 x 0.02)


def test_a_lost_base_stops_counting() -> None:
    w = world(LOW_FLOOR)
    w.owner["fob-n-e"] = "COALITION"
    assert static_surplus(w) == 1250  # 500 + 500 + 250


# --- loader -----------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_the_loader_refuses_a_reference_outside_0_to_1(bad: float) -> None:
    with pytest.raises(ConfigError, match="surplus_ref_frac"):
        shipped_config({"director.surplus_ref_frac": bad})


def test_the_bounds_0_and_1() -> None:
    zero = shipped_config({"director.surplus_ref_frac": 0.0}).rules.supply
    assert dict(zero.surplus_ref) == STRAIT_1_R  # max(0, floor): the floor
    full = shipped_config({"director.surplus_ref_frac": 1.0}).rules.supply
    assert full.surplus_ref["static-hq"] == 2000 and full.surplus_ref["bridge-n"] == 0


def test_the_reference_is_exact_decimal_arithmetic() -> None:
    # 0.28 x 1100 is 308 exactly, but 308.00000000000006 in floats, whose ceil is 309
    c = shipped_config({"director.surplus_ref_frac": 0.28, "logistics.node_max_stock.FOB": 1100})
    sup = c.rules.supply
    assert sup.starve_floor["fob-n-e"] == 275  # ceil(0.25 x 1100), below the reference
    assert sup.surplus_ref["fob-n-e"] == 308
    assert sup.surplus_ref["east-airbase"] == 560  # 0.28 x 2000


def test_a_part_unit_reference_rounds_up() -> None:
    sup = shipped_config({"director.surplus_ref_frac": 0.3333}).rules.supply
    assert sup.surplus_ref["east-airbase"] == 667  # 666.6
    assert sup.surplus_ref["fob-n-e"] == 334  # 333.3


# --- the convoy gate and the capture slot read the reference ------------------------------------


def at_reference(overrides: dict[str, object], *, old_rule: bool) -> World:
    """A Static at threshold 0.05 (floors 100 and 50) with static-hq, fob-n-e and fob-s-e at their
    reference (500, 250, 250) and east-airbase at 140: 40 + 400 + 200 + 200 = 840 above the floor,
    0 above R. No opening garrison, and east-airbase's 40 above its floor is less than its
    missing garrison's cost, so it is short (a convoy base). With `old_rule` the reference is
    swapped back to the floor, the rule before NX-500."""
    c = shipped_config({"logistics.starve_threshold": 0.05, **overrides})
    w = world(c)
    for e in list(w.entities()):
        if e.home is not None:
            w.remove(e.id)
    assert w.rules is not None
    sup = w.rules.supply
    for n in STATIC_BASES:
        w.stock[n] = sup.surplus_ref[n]
    w.stock["east-airbase"] = 140
    if old_rule:
        old_sup = dataclasses.replace(sup, surplus_ref=sup.starve_floor)
        w.rules = dataclasses.replace(w.rules, supply=old_sup)
    w.director["ENEMY"].tier = "PATTERN_OF_LIFE"
    return w


def convoy_jobs(old_rule: bool) -> list[str]:
    w = at_reference({"director.pol.convoy_cost": 30}, old_rule=old_rule)
    assert w.rules is not None and w.rules.director is not None
    out: list[Event] = []
    _convoys(w, w.rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], w.rules.director,
             out, _Purse(0, 40))  # fmt: skip
    return [e.job_kind for e in out if e.kind == "JobCreated"]


def test_a_convoy_costing_more_than_the_surplus_above_the_reference_is_not_sent() -> None:
    # 30 <= 840 above the floor, but 30 > 0 above R: the gate sends no convoy, though the
    # window's rear account (40) could pay the carrier at the source; the old rule sent one
    assert convoy_jobs(old_rule=False) == []
    assert convoy_jobs(old_rule=True) == ["RESUPPLY"]


def capture_slot_selects(old_rule: bool) -> bool:
    w = at_reference({}, old_rule=old_rule)
    assert w.rules is not None and w.rules.director is not None
    state = w.director["ENEMY"]
    w.campaign.running_ticks = now = w.rules.director.offensive_ticks  # the slot is due
    _capture_slot(w, w.rules, "ENEMY", side_view(w, "ENEMY"), state, w.rules.director, now,
                  [], _Purse(0, 0))  # fmt: skip
    return state.last_offensive == now


def test_the_capture_slot_selects_against_the_surplus_above_the_reference() -> None:
    # a capture operation costs 50 or 60: within 840 above the floor, not within 0 above R
    assert not capture_slot_selects(old_rule=False)
    assert capture_slot_selects(old_rule=True)


# --- determinism, snapshot ----------------------------------------------------------------------


def run(w: World, ticks: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for _ in range(ticks):
        out += [e.model_dump() for e in step(w, [])]
    return out


def test_a_run_with_the_reference_above_the_floor_is_deterministic() -> None:
    def once() -> tuple[str, list[dict[str, Any]]]:
        w = world(LOW_FLOOR, seed=7)
        events = run(w, 1300)  # two director windows and a bit
        return state_hash(w), events

    first = once()
    assert first[1]
    assert once() == first


def test_save_and_load_resume_identically_with_the_reference() -> None:
    w = world(LOW_FLOOR, seed=7)
    run(w, 900)
    copy = load(save(w))
    copy.rules = w.rules
    assert state_hash(copy) == state_hash(w)
    assert run(copy, 700) == run(w, 700)
    assert state_hash(copy) == state_hash(w)
