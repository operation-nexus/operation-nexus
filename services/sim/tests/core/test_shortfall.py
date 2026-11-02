"""NX-436 (ECONOMY EC-6a, Q-TD-51 U5, Q-TD-64, FOW-13): upkeep shortfall sitreps.

Runs on the shipped strait-1 config with both sides limited and `economy.upkeep` 5, every window,
for GARRISON_INFANTRY, STRIKE_FIGHTER and ENEMY_ARMOR. The coalition base is fob-n-w; the Static
base is fob-n-e, which starts with four AI ENEMY_ARMOR (ids 16-19) homed there and its air
defense site (id 7). Expected values
are worked by hand: a unit costs 5, so a base holding 0 grounds every unit charged there and one
holding 5 x n pays n of them.
"""

from typing import Any

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID
from test_upkeep import put

from nexus.contracts.gen.events.event import Event
from nexus.core import economy, logistics, upkeep
from nexus.core.world import Contact, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.golden import shipped_config

WINDOW = 600  # economy.window_s 60 game s at 10 Hz
BASE, STATIC = "fob-n-w", "fob-n-e"
STATIC_ARMOR = (16, 17, 18, 19)  # strait-1's garrison at fob-n-e (module docstring)
STATIC_SITE = 7  # fob-n-e's air defense site
KEYS = {
    "economy.unlimited.COALITION": False, "economy.unlimited.ENEMY": False,
    **{f"economy.upkeep.{k}": 5 for k in ("GARRISON_INFANTRY", "STRIKE_FIGHTER", "ENEMY_ARMOR")},
    **{f"economy.upkeep_period.{k}": 1
       for k in ("GARRISON_INFANTRY", "STRIKE_FIGHTER", "ENEMY_ARMOR")},
    "economy.cost_parity": False,  # STRIKE_FIGHTER pays, its mirror does not (NX-494)
}  # fmt: skip


def config(quiet: int = 0) -> CampaignConfig:
    return shipped_config({**KEYS, "economy.shortfall_quiet_windows": quiet})


CONFIG = config()


def new_world(cfg: CampaignConfig = CONFIG) -> World:
    return start_campaign(CAMPAIGN_ID, 12345, cfg)


def window(w: World, k: int) -> list[Event]:
    """Economy window `k` (from 1): income, the clip and upkeep, as its boundary tick runs them."""
    w.campaign.running_ticks = k * WINDOW - 1
    w.campaign.tick = max(w.campaign.tick, k * WINDOW - 1)
    out: list[Event] = []
    economy.window(w, out)
    upkeep.upkeep(w, out)
    return out


def charge(w: World, k: int) -> list[Event]:
    """Upkeep alone at window `k` (no income), for a source paid from the pool."""
    w.campaign.running_ticks = w.campaign.tick = k * WINDOW - 1
    out: list[Event] = []
    upkeep.upkeep(w, out)
    return out


def sitreps(out: list[Event]) -> list[tuple[Any, ...]]:
    return [
        (e.side, e.node_id, e.status, e.grounded, list(e.credit_ids))
        for e in out
        if e.kind == "SupplyShortfall"
    ]


def started(n: int, node: str = BASE, side: str = "COALITION") -> tuple[Any, ...]:
    return (side, node, "STARTED", n, [])


def ended(credit: list[int], node: str = BASE, side: str = "COALITION") -> tuple[Any, ...]:
    return (side, node, "ENDED", 0, credit)


def truck(w: World, node: str, cargo: int) -> Entity:
    e = put(w, "LOGI_TRUCK", node)
    e.cargo = cargo
    return e


def unload(w: World) -> None:
    """Run the logistics system until every truck has unloaded (no window in between)."""
    for _ in range(10_000):
        if not any(e.cargo for e in w.entities()):
            return
        logistics.logistics(w, [])
    raise AssertionError("trucks did not unload")


def see(w: World, entity_id: int) -> None:
    """The coalition tracks `entity_id` now (a Tier 2 contact, FOW-5)."""
    e = w.find(entity_id)
    assert e is not None
    w.contacts["COALITION"][entity_id] = Contact(e.kind, e.pos, Vec2(0.0, 0.0))


# --- one sitrep per episode, never per unit ------------------------------------------------------


def test_many_units_grounding_at_once_make_one_sitrep_per_episode() -> None:
    w = new_world()
    w.stock[BASE] = 0
    units = [put(w, "GARRISON_INFANTRY", BASE) for _ in range(3)]
    out = window(w, 1)
    assert [e.kind for e in out].count("UnitGrounded") == 3
    assert sitreps(out) == [started(3)]  # one line, the count, never per unit
    put(w, "GARRISON_INFANTRY", BASE)  # a fourth grounds into the open episode
    out = window(w, 2)
    assert [e.kind for e in out].count("UnitGrounded") == 1
    assert sitreps(out) == []
    assert all(u.grounded for u in units)


def test_an_episode_without_a_grounded_unit_says_nothing() -> None:
    w = new_world()
    w.stock[BASE] = 15
    put(w, "GARRISON_INFANTRY", BASE)
    assert sitreps(window(w, 1)) == []
    assert w.shortfall["COALITION"] == {}


# --- the payoff names the haulers ----------------------------------------------------------------


def test_the_payoff_credits_the_haulers_who_delivered_during_the_episode_ascending() -> None:
    w = new_world()
    w.stock[BASE] = 0
    early = truck(w, BASE, 1)  # delivers before the episode: not credited
    unload(w)
    w.stock[BASE] = 0
    put(w, "GARRISON_INFANTRY", BASE)
    put(w, "GARRISON_INFANTRY", BASE)
    assert sitreps(window(w, 1)) == [started(2)]
    low, high = truck(w, BASE, 4), truck(w, BASE, 6)  # 10: both units pay again
    elsewhere = truck(w, "fob-s-w", 3)  # another base: not credited
    unload(w)
    out = window(w, 2)
    assert [e.kind for e in out].count("UnitUngrounded") == 2
    assert sitreps(out) == [ended([low.id, high.id])]
    assert early.id not in (low.id, high.id) and elsewhere.id > high.id
    w.stock[BASE] = 10
    assert sitreps(window(w, 3)) == []  # closed once


def test_the_payoff_names_at_most_the_32_lowest_haulers() -> None:
    w = new_world()
    w.stock[BASE] = 0
    put(w, "GARRISON_INFANTRY", BASE)
    window(w, 1)
    trucks = [truck(w, BASE, 1) for _ in range(33)]
    unload(w)
    [(_, _, status, _, credit)] = sitreps(window(w, 2))
    assert status == "ENDED"
    assert credit == [t.id for t in trucks[:32]]  # trucks spawn in id order


def test_the_credits_ascend_by_id_not_by_delivery_order() -> None:
    w = new_world()
    w.stock[BASE] = 0
    put(w, "GARRISON_INFANTRY", BASE)
    window(w, 1)
    low = truck(w, BASE, 0)  # empty for now: it delivers second
    high = truck(w, BASE, 3)
    unload(w)
    low.cargo = 3
    unload(w)
    assert sitreps(window(w, 2)) == [ended([low.id, high.id])]


def test_a_truck_that_has_not_unloaded_a_whole_unit_is_not_credited() -> None:
    w = new_world()
    w.stock[BASE] = 0
    put(w, "GARRISON_INFANTRY", BASE)
    window(w, 1)
    t = truck(w, BASE, 3)
    logistics.logistics(w, [])  # one tick: 0.6 of a unit (logistics.unload_rate), none whole
    assert (w.stock[BASE], t.cargo) == (0, 3)
    w.remove(t.id)
    w.stock[BASE] = 5  # paid from elsewhere
    assert sitreps(window(w, 2)) == [ended([])]


def test_a_hauler_is_credited_once_over_two_stops() -> None:
    w = new_world()
    w.stock[BASE] = 0
    put(w, "GARRISON_INFANTRY", BASE)
    window(w, 1)
    t = truck(w, BASE, 2)
    unload(w)
    t.cargo = 3
    unload(w)
    assert sitreps(window(w, 2)) == [ended([t.id])]


def test_an_episode_closed_by_a_loss_not_a_payment_ends_silently() -> None:
    w = new_world()
    w.stock[BASE] = 0
    u = put(w, "GARRISON_INFANTRY", BASE)
    window(w, 1)
    w.remove(u.id)  # destroyed while grounded: nobody was paid back
    out = window(w, 2)
    assert sitreps(out) == []
    assert w.shortfall["COALITION"] == {} and w.shortfall_end["COALITION"] == {BASE: 2 * WINDOW}


def test_a_source_paid_from_the_pool_ends_with_no_haulers() -> None:
    w = new_world()
    u = put(w, "GARRISON_INFANTRY", "haven")
    w.pool["COALITION"] = 0
    assert sitreps(charge(w, 1)) == [started(1, "haven")]
    w.pool["COALITION"] = 5  # the pool pays it: no truck delivered
    assert sitreps(charge(w, 2)) == [ended([], "haven")]
    assert not u.grounded


# --- a Static base only while the coalition sees it ----------------------------------------------


def test_no_static_shortfall_sitrep_for_an_unseen_base() -> None:
    w = new_world()
    w.stock[STATIC] = 0
    out = window(w, 1)
    assert [e.entity_id for e in out if e.kind == "UnitGrounded"] == list(STATIC_ARMOR)
    assert sitreps(out) == []
    assert w.shortfall["ENEMY"][STATIC].status == "PENDING"
    w.stock[STATIC] = 20
    assert sitreps(window(w, 2)) == []  # never announced: no payoff either


def test_a_seen_static_base_is_announced_with_no_credits() -> None:
    w = new_world()
    w.stock[STATIC] = 0
    see(w, STATIC_ARMOR[0])
    assert sitreps(window(w, 1)) == [started(1, STATIC, "ENEMY")]  # one of four is tracked
    convoy = put(w, "ENEMY_CONVOY", STATIC)
    convoy.cargo = 20
    unload(w)
    assert w.shortfall["ENEMY"][STATIC].haulers == [convoy.id]
    assert sitreps(window(w, 2)) == [ended([], STATIC, "ENEMY")]  # Static haulers stay hidden


def test_a_static_base_spotted_mid_episode_is_announced_then_once() -> None:
    w = new_world()
    w.stock[STATIC] = 0
    assert sitreps(window(w, 1)) == []
    see(w, STATIC_ARMOR[2])
    assert sitreps(window(w, 2)) == [started(1, STATIC, "ENEMY")]
    assert sitreps(window(w, 3)) == []


def test_a_static_count_names_only_the_grounded_units_the_coalition_tracks() -> None:
    w = new_world()
    w.stock[STATIC] = 0
    see(w, STATIC_ARMOR[1])
    see(w, STATIC_ARMOR[3])
    assert sitreps(window(w, 1)) == [started(2, STATIC, "ENEMY")]  # 4 grounded, 2 tracked


def test_a_static_base_seen_by_its_site_alone_reports_no_count() -> None:
    w = new_world()
    w.stock[STATIC] = 0
    see(w, STATIC_SITE)  # the base is seen, none of its grounded armor is
    assert sitreps(window(w, 1)) == [started(0, STATIC, "ENEMY")]


def test_an_unheard_static_episode_starts_no_quiet_gap() -> None:
    w = new_world(config(quiet=30))
    w.stock[STATIC] = 0
    assert sitreps(window(w, 1)) == []  # unseen: PENDING
    w.stock[STATIC] = 20
    assert sitreps(window(w, 2)) == []  # closed unheard
    assert w.shortfall_end["ENEMY"] == {}
    w.stock[STATIC] = 0
    see(w, STATIC_ARMOR[0])
    assert sitreps(window(w, 3)) == [started(1, STATIC, "ENEMY")]  # within 30 windows: announced


def test_a_static_payoff_needs_the_base_seen_when_it_ends() -> None:
    w = new_world()
    w.stock[STATIC] = 0
    see(w, STATIC_ARMOR[0])
    window(w, 1)
    w.contacts["COALITION"].clear()  # lost sight of it
    w.stock[STATIC] = 20
    assert sitreps(window(w, 2)) == []
    assert w.shortfall["ENEMY"] == {}


# --- rate limit when the shortfall turns chronic -------------------------------------------------


def test_an_episode_soon_after_the_last_is_muted_until_the_base_has_been_quiet() -> None:
    w = new_world(config(quiet=2))
    u = put(w, "GARRISON_INFANTRY", BASE)
    w.stock[BASE] = 0
    assert sitreps(window(w, 1)) == [started(1)]
    w.stock[BASE] = 5
    assert sitreps(window(w, 2)) == [ended([])]  # ended at window 2
    w.stock[BASE] = 0
    assert sitreps(window(w, 3)) == []  # 1 window after: muted
    assert w.shortfall["COALITION"][BASE].status == "MUTED"
    w.stock[BASE] = 5
    assert sitreps(window(w, 4)) == []  # a muted episode has no payoff; ended at window 4
    w.stock[BASE] = 0
    assert sitreps(window(w, 6)) == []  # 2 windows after window 4: still muted
    w.stock[BASE] = 5
    window(w, 7)  # ends at window 7
    w.stock[BASE] = 0
    assert sitreps(window(w, 10)) == [started(1)]  # 3 windows after: announced again
    assert u.grounded


def test_quiet_zero_announces_every_episode() -> None:
    w = new_world()
    put(w, "GARRISON_INFANTRY", BASE)
    got = []
    for k, stock in enumerate((0, 5, 0, 5), start=1):
        w.stock[BASE] = stock
        got += sitreps(window(w, k))
    assert got == [started(1), ended([]), started(1), ended([])]


def test_the_shipped_quiet_gap_is_read_from_the_config() -> None:
    shipped, seven = shipped_config({}).rules.economy, config(quiet=7).rules.economy
    assert shipped is not None and shipped.shortfall_quiet_windows == 30  # balance/default.yaml
    assert seven is not None and seven.shortfall_quiet_windows == 7


# --- snapshot, determinism, property --------------------------------------------------------------


def _mid_episode() -> tuple[World, Entity]:
    w = new_world()
    w.stock[BASE] = 0
    put(w, "GARRISON_INFANTRY", BASE)
    window(w, 1)
    t = truck(w, BASE, 2)
    unload(w)
    return w, t


def test_save_and_load_mid_episode_keeps_its_status_and_haulers() -> None:
    w, t = _mid_episode()
    copy = load(save(w))
    assert copy.shortfall == w.shortfall and state_hash(copy) == state_hash(w)
    copy.rules = w.rules
    w.stock[BASE] = copy.stock[BASE] = 5
    assert sitreps(window(copy, 2)) == sitreps(window(w, 2)) == [ended([t.id])]
    assert state_hash(copy) == state_hash(w)
    assert copy.shortfall_end == {"COALITION": {BASE: 2 * WINDOW}, "ENEMY": {}}


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d["shortfall"]["COALITION"][BASE].update(status="LOUD"), "status"),
        (lambda d: d["shortfall"]["COALITION"][BASE].update(haulers=[9, 3]), "ascend"),
        (lambda d: d["shortfall"]["COALITION"][BASE].update(haulers=[10**6]), "ascend"),
        (lambda d: d["shortfall"]["COALITION"].update(atlantis=d["shortfall"]["COALITION"][BASE]),
         "not a node"),
        (lambda d: d["shortfall_end"]["ENEMY"].update({STATIC: 10**9}), "after the snapshot"),
        (lambda d: d["shortfall"].pop("ENEMY"), "exactly the keys"),
        (lambda d: d["shortfall"].update(ENEMY=[]), "must be a map"),
        (lambda d: d["shortfall"]["COALITION"][BASE].update(haulers={"3": 1}), "must be a list"),
    ],
)  # fmt: skip
def test_load_refuses_a_bad_shortfall(edit: Any, message: str) -> None:
    w, _ = _mid_episode()
    data = msgpack.unpackb(save(w), raw=False)
    edit(data)
    with pytest.raises(ValueError, match=message):
        load(msgpack.packb(data, use_bin_type=True))


def test_pending_and_muted_episodes_survive_save_and_load() -> None:
    w = new_world(config(quiet=5))
    u = put(w, "GARRISON_INFANTRY", BASE)
    w.stock[BASE], w.stock[STATIC] = 0, 0  # the Static base unseen: PENDING
    window(w, 1)
    w.stock[BASE] = 5
    window(w, 2)  # the coalition episode ends, heard
    w.stock[BASE] = 0
    window(w, 3)  # a new one inside the gap: MUTED
    status = {s: {n: f.status for n, f in w.shortfall[s].items()} for s in ("COALITION", "ENEMY")}
    assert status == {"COALITION": {BASE: "MUTED"}, "ENEMY": {STATIC: "PENDING"}}
    copy = load(save(w))
    copy.rules = w.rules
    assert copy.shortfall == w.shortfall and copy.shortfall_end == w.shortfall_end
    see(copy, STATIC_ARMOR[0])
    see(w, STATIC_ARMOR[0])
    assert sitreps(window(copy, 4)) == sitreps(window(w, 4)) == [started(1, STATIC, "ENEMY")]
    assert state_hash(copy) == state_hash(w) and u.grounded


def _scenario() -> tuple[list[tuple[Any, ...]], str]:
    w = new_world()
    see(w, STATIC_ARMOR[1])
    got: list[tuple[Any, ...]] = []
    for k, (own, static) in enumerate(((0, 0), (0, 0), (20, 0), (0, 20), (5, 20)), start=1):
        w.stock[BASE], w.stock[STATIC] = own, static
        if k == 2:
            truck(w, BASE, 3)
            unload(w)
        put(w, "GARRISON_INFANTRY", BASE)
        got += sitreps(window(w, k))
    return got, state_hash(w)


def test_same_inputs_give_the_same_sitreps_and_state() -> None:
    first = _scenario()
    assert first == _scenario()
    # worked by hand: A=32 grounds (k1); the truck (33) hauls 3 (k2: still short, B grounds too);
    # 20 pays A, B, C (k3); 0 grounds A-D while the Static base's 20 pays its four (k4); 5 pays
    # one of five (k5: the episode runs on)
    assert first[0] == [
        started(1),
        started(1, STATIC, "ENEMY"),  # four grounded, one tracked
        ended([33]),
        ended([], STATIC, "ENEMY"),
        started(4),
    ]


@settings(max_examples=40, deadline=None)
@given(st.lists(st.sampled_from((0, 5, 10)), min_size=1, max_size=12))
def test_every_started_has_at_most_one_matching_end(stocks: list[int]) -> None:
    w = new_world()
    put(w, "GARRISON_INFANTRY", BASE)
    put(w, "GARRISON_INFANTRY", BASE)
    statuses = []
    for k, stock in enumerate(stocks, start=1):
        w.stock[BASE] = stock
        statuses += [s[2] for s in sitreps(window(w, k)) if s[1] == BASE]
    # alternating, starting with STARTED: one start per episode, at most one end each
    assert statuses == ["STARTED", "ENDED"] * (len(statuses) // 2) + ["STARTED"] * (
        len(statuses) % 2
    )
    open_now = BASE in w.shortfall["COALITION"]
    assert open_now == any(e.grounded for e in w.entities() if e.home_base == BASE)
