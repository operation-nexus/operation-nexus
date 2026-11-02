"""NX-412 part 2 (ECONOMY EC-4, EC-5, EC-6, EC-10 step 3, EC-15): home bases, upkeep, grounding.

Runs on the shipped strait-1 config with both sides limited and `economy.upkeep` 5 for
GARRISON_INFANTRY and STRIKE_FIGHTER (every other kind 0). Coalition nodes: haven (20 km, 120 km,
its source, paid from the pool), west-airbase (90 km, 120 km), fob-n-w (130 km, 60 km), fob-s-w
(130 km, 180 km); cross-n (230 km, 60 km) is a neutral FOB. Expected values are worked by hand.
"""

import dataclasses
from typing import Any

import msgpack
import pytest
from fixture_pre_5b import pre_5b_config
from hypothesis import given
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID, cid, join
from test_rebase import rebase
from test_tasking import post

from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core import economy, upkeep
from nexus.core.bridges import blocked
from nexus.core.capture import _flip, _Presence
from nexus.core.launch import _spare, _spawn
from nexus.core.roads import RoadGraph, shortest_path
from nexus.core.step import step
from nexus.core.tasking import claim
from nexus.core.tasking_gen import is_idle
from nexus.core.world import (
    SIDES,
    Campaign,
    CaptureBar,
    Entity,
    Vec2,
    World,
    load,
    save,
    state_hash,
)
from nexus.runtime.campaign_config import CampaignConfig, start_campaign

LIMITED = {"economy.unlimited.COALITION": False, "economy.unlimited.ENEMY": False}
PAID = {
    "economy.upkeep.GARRISON_INFANTRY": 5, "economy.upkeep.STRIKE_FIGHTER": 5,
    # every window (NX-426): the payment-order tests below charge every unit each window
    "economy.upkeep_period.GARRISON_INFANTRY": 1, "economy.upkeep_period.STRIKE_FIGHTER": 1,
    "economy.cost_parity": False,  # STRIKE_FIGHTER pays, its mirror does not (NX-494)
}  # fmt: skip
CONFIG = pre_5b_config({**LIMITED, **PAID})
RULES = CONFIG.rules
WINDOW = 600  # economy.window_s 60 game s at 10 Hz
INF: UnitKind = "GARRISON_INFANTRY"
JET: UnitKind = "STRIKE_FIGHTER"


def new_world(seed: int = 12345, config: CampaignConfig = CONFIG) -> World:
    return start_campaign(CAMPAIGN_ID, seed, config)


# Infantry at 500 m/s so a drive home fits in a short test (positions and roads as shipped).
FAST = dataclasses.replace(
    CONFIG,
    rules=dataclasses.replace(RULES, speed_mps={**RULES.speed_mps, "GARRISON_INFANTRY": 500.0}),
)


def put(
    w: World, kind: UnitKind, node: str, *, owner: OwnerKind = "COMMANDER", ordered: int = 0,
    home: str | None = None,
) -> Entity:  # fmt: skip
    """A unit standing at `node` (an aircraft LANDED, full), homed at `home` (default `node`)."""
    side: Side = "ENEMY" if kind.startswith("ENEMY_") else "COALITION"
    commander = cid(w._next_entity_id) if owner == "COMMANDER" else None
    e = w.spawn(kind, side, owner, Vec2(*RULES.roads.pos[node]), commander_id=commander)
    e.last_node, e.home_base, e.ordered = node, home or node, ordered
    if RULES.domain[kind] == "AIR":
        e.state, e.fuel = "LANDED", RULES.fuel_s[kind]
    return e


def window(w: World) -> list[Event]:
    """Income, the clip and upkeep, as the tick that crosses the window boundary runs them."""
    w.campaign.running_ticks = WINDOW - 1
    w.campaign.tick = max(w.campaign.tick, WINDOW - 1)
    out: list[Event] = []
    economy.window(w, out)
    upkeep.upkeep(w, out)
    return out


def rows(out: list[Event]) -> list[tuple[Any, ...]]:
    """The upkeep events: (kind, entity, home) or (SupplyConsumed, node, amount)."""
    got: list[tuple[Any, ...]] = []
    for e in out:
        if e.kind in ("UnitGrounded", "UnitUngrounded"):
            got.append((e.kind, e.entity_id, e.node_id))
        elif e.kind == "SupplyConsumed" and e.cause == "UPKEEP":
            got.append((e.kind, e.node_id, e.amount))
    return got


def parked(e: Entity) -> tuple[object, ...]:
    """(state, last node, path, grounded) read afresh (mypy keeps what a test assigned)."""
    return e.state, e.last_node, e.path, e.grounded


def run(w: World, ticks: int) -> list[Event]:
    return [ev for _ in range(ticks) for ev in step(w, [])]


# --- EC-6 payment order and EC-4 who pays ---------------------------------------------------------


def test_viewer_units_pay_first_then_the_most_recent_order_then_id() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 10  # two payments of 5
    ai = put(w, INF, "fob-n-w", owner="AI_GARRISON", ordered=9)  # AI: last, however recent
    old = put(w, INF, "fob-n-w", ordered=3)  # idle longest: grounds before the newer viewers
    new_a = put(w, INF, "fob-n-w", ordered=7)
    new_b = put(w, INF, "fob-n-w", ordered=7)  # same tick: the lower id pays first
    out = window(w)
    assert rows(out) == [
        ("UnitGrounded", old.id, "fob-n-w"),
        ("UnitGrounded", ai.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 10),
    ]
    assert (new_a.grounded, new_b.grounded, old.grounded, ai.grounded) == (False, False, True, True)
    assert w.stock["fob-n-w"] == 0


def busy(w: World, e: Entity, key: str) -> Entity:
    """`e` holding a claim on its own DEFEND job at its home (NX-428)."""
    claim(w, e, post(w, "COALITION", "DEFEND", str(e.home_base), key), [])
    return e


def test_viewer_before_ai_stays_outermost_over_a_job() -> None:
    # Q-TD-23 kept (Q-TD-49): an AI job holder still grounds before an idle viewer unit
    w = new_world()
    w.stock["fob-n-w"] = 5
    holder = busy(w, put(w, INF, "fob-n-w", owner="AI_GARRISON", ordered=9), "h")
    idle = put(w, INF, "fob-n-w", ordered=0)
    assert rows(window(w)) == [
        ("UnitGrounded", holder.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 5),
    ]
    assert (holder.grounded, idle.grounded) == (True, False)


@pytest.mark.parametrize("owner", ["COMMANDER", "AI_GARRISON"])
def test_an_idle_unit_grounds_before_a_job_holder_of_its_class_at_the_same_home(
    owner: OwnerKind,
) -> None:  # fmt: skip
    # Q-TD-43: the idle unit's more recent order does not save it from a job holder's claim
    w = new_world()
    w.stock["fob-n-w"] = 5
    holder = busy(w, put(w, INF, "fob-n-w", owner=owner, ordered=0), "h")
    idle = put(w, INF, "fob-n-w", owner=owner, ordered=9)
    assert rows(window(w)) == [
        ("UnitGrounded", idle.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 5),
    ]
    assert (holder.grounded, holder.job_id is not None, idle.grounded) == (False, True, True)


def test_job_holders_ground_only_when_the_holders_ahead_take_the_stock() -> None:
    # every viewer unit at the home holds a job: recency, then id, decides among them
    w = new_world()
    w.stock["fob-n-w"] = 10  # two payments of 5
    old = busy(w, put(w, INF, "fob-n-w", ordered=3), "old")
    new_a = busy(w, put(w, INF, "fob-n-w", ordered=7), "a")
    new_b = busy(w, put(w, INF, "fob-n-w", ordered=7), "b")  # same tick: the lower id pays first
    already = put(w, INF, "fob-n-w", ordered=10)
    already.grounded = True  # grounded last window: idle, so it pays after every viewer holder
    assert rows(window(w)) == [
        ("UnitGrounded", old.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 10),
    ]
    assert (new_a.grounded, new_b.grounded, old.grounded, already.grounded) == (
        False, False, True, True)  # fmt: skip


def test_a_viewer_following_an_order_pays_before_an_idle_viewer_at_the_same_home() -> None:
    # Q-TD-49c: an explicit order under way (here a HOLD still travelling to its node) is busy
    w = new_world()
    w.stock["fob-n-w"] = 5
    ordered = put(w, INF, "fob-n-w", ordered=0)
    ordered.order, ordered.order_node, ordered.held_since = "HOLD", "fob-s-w", 0
    ordered.path = ["fob-s-w"]
    idle = put(w, INF, "fob-n-w", ordered=9)
    assert rows(window(w)) == [
        ("UnitGrounded", idle.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 5),
    ]
    assert (ordered.grounded, ordered.order, idle.grounded) == (False, "HOLD", True)


def test_a_unit_parked_on_hold_at_home_is_idle() -> None:
    # Q-TD-49c: a HOLD has no end of its own, so once parked the unit is idle at home and the
    # most recent order decides, not the HOLD
    w = new_world()
    w.stock["fob-n-w"] = 5
    parked = put(w, INF, "fob-n-w", ordered=0)
    parked.order, parked.order_node, parked.held_since = "HOLD", "fob-n-w", 0
    idle = put(w, INF, "fob-n-w", ordered=9)
    assert rows(window(w)) == [
        ("UnitGrounded", parked.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 5),
    ]
    assert (parked.grounded, idle.grounded) == (True, False)


def test_an_idle_unit_at_another_home_does_not_spare_a_job_holder() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    holder = busy(w, put(w, INF, "fob-n-w"), "h")
    idle = put(w, INF, "fob-s-w")  # fob-s-w holds 500 of its own
    assert rows(window(w)) == [
        ("UnitGrounded", holder.id, "fob-n-w"),
        ("SupplyConsumed", "fob-s-w", 5),
    ]
    assert not idle.grounded


_BASES = ("fob-n-w", "fob-s-w", "west-airbase")
HELD = st.tuples(
    st.sampled_from(("job", "order", "idle")), st.booleans(), st.integers(0, 5),
    st.sampled_from(_BASES),
)  # fmt: skip


def _held_window(units: list[Any], stock: dict[str, int]) -> tuple[World, set[int], str]:
    """The world after one window, the ids that were busy (a job or an order) going in, and its
    state hash."""
    w = new_world()
    w.stock.update(stock)
    for i, (work, viewer, ordered, home) in enumerate(units):
        e = put(w, INF, home, owner="COMMANDER" if viewer else "AI_GARRISON", ordered=ordered)
        if work == "job":
            busy(w, e, str(i))
        elif work == "order":  # a HOLD still on its way (a parked HOLD is idle, Q-TD-49c)
            e.order, e.order_node, e.held_since, e.path = "HOLD", home, 0, [home]
    held = {e.id for e in w.entities() if e.job_id is not None or (e.order and e.path)}
    window(w)
    return w, held, state_hash(w)


@given(units=st.lists(HELD, max_size=8), stock=st.fixed_dictionaries(
    {b: st.integers(0, 25) for b in _BASES}))  # fmt: skip
def test_a_busy_unit_grounds_only_when_its_home_grounds_every_idle_unit_of_its_class(
    units: list[Any], stock: dict[str, int],
) -> None:  # fmt: skip
    """Every charged unit here is INF at the same 5 (the start world homes nothing at these bases).
    The property needs equal costs: with mixed costs a costly busy unit may ground while a cheaper
    idle one pays from what is left (Q-TD-49 (b))."""
    w, held, digest = _held_window(units, stock)
    er = RULES.economy
    assert er is not None
    charged = [e for e in w.entities() if er.upkeep.get(e.kind, 0) and e.home_base in _BASES]
    assert {er.upkeep[e.kind] for e in charged} <= {5}
    idle_paid = {
        (e.home_base, e.owner_kind) for e in charged if e.id not in held and not e.grounded
    }
    assert not [
        e.id for e in charged
        if e.id in held and e.grounded and (e.home_base, e.owner_kind) in idle_paid
    ]  # fmt: skip
    assert _held_window(units, stock)[2] == digest  # same world, same hash


def test_a_base_pays_from_its_stock_and_the_source_from_the_pool() -> None:
    w = new_world()
    pool = w.pool["COALITION"]
    put(w, INF, "fob-n-w")
    put(w, INF, "haven")
    put(w, "LOGI_TRUCK", "fob-n-w")  # upkeep 0: free, no debit
    out = window(w)
    assert rows(out) == [
        ("SupplyConsumed", "fob-n-w", 5),
        ("SupplyConsumed", "haven", 5),
    ]
    assert (w.stock["fob-n-w"], w.pool["COALITION"]) == (495, pool - 5)


def test_a_home_pays_only_the_full_amount_and_a_lost_home_never_pays() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 4
    short = put(w, INF, "fob-n-w")
    lost = put(w, INF, "west-airbase")
    w.owner["west-airbase"] = "ENEMY"  # not re-homed yet: the enemy's stock never pays for it
    assert rows(window(w)) == [
        ("UnitGrounded", short.id, "fob-n-w"),
        ("UnitGrounded", lost.id, "west-airbase"),
    ]
    assert (w.stock["fob-n-w"], w.stock["west-airbase"]) == (4, 1000)


def test_a_grounded_unit_ungrounds_at_the_first_window_its_home_pays() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    assert rows(window(w)) == [("UnitGrounded", e.id, "fob-n-w")]
    assert rows(window(w)) == []  # still short: no second event
    w.stock["fob-n-w"] = 7
    assert rows(window(w)) == [
        ("UnitUngrounded", e.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 5),
    ]
    assert (e.grounded, w.stock["fob-n-w"]) == (False, 2)
    assert is_idle(RULES, e, "COALITION")  # the board may task it again


# --- EC-6 what grounded means --------------------------------------------------------------------


def test_a_grounded_aircraft_flies_home_lands_and_stays() -> None:
    w = new_world()
    w.stock["west-airbase"] = 0
    jet = put(w, JET, "west-airbase")
    jet.state, jet.last_node, jet.path = "ON_STATION", None, []
    jet.pos = jet.orbit = Vec2(150_000.0, 120_000.0)
    window(w)
    assert (jet.grounded, jet.state, jet.path) == (True, "RTB", ["west-airbase"])
    run(w, 1500)  # 60 km home, and on past the next window (still unpaid)
    assert parked(jet) == ("LANDED", "west-airbase", [], True)
    assert jet.job_id is None and jet.order is None


def test_a_grounded_ground_unit_drives_home_and_parks() -> None:
    w = new_world(config=FAST)
    w.stock["fob-n-w"] = 0
    inf = put(w, INF, "cross-n", home="fob-n-w")  # out at a neutral node: no home change there
    window(w)
    assert inf.grounded and inf.path[-1] == "fob-n-w"
    run(w, 1000)  # about 100 km of road at 300 m a tick, and on past the next window
    assert (inf.last_node, inf.path, inf.home_base, inf.grounded) == (
        "fob-n-w",
        [],
        "fob-n-w",
        True,
    )
    assert not is_idle(RULES, inf, "COALITION")


def test_a_grounded_ground_unit_with_no_road_home_only_finishes_its_leg() -> None:
    w = new_world(config=FAST)
    w.stock["fob-n-w"] = 0
    for bridge in ("bridge-n", "bridge-s"):  # both crossings down: no road back west
        w.bridge_hp[bridge] = 0
        w.bridge_down.add(bridge)
    assert shortest_path(RULES.roads, "cross-n", "fob-n-w", blocked=blocked(w)) is None
    inf = put(w, INF, "cross-n", home="fob-n-w")
    route = shortest_path(RULES.roads, "cross-n", "static-hq", blocked=blocked(w))
    assert route is not None and len(route) > 2
    inf.path = list(route)  # off east on an order it is about to drop
    step(w, [])
    leg = inf.path[0]
    assert len(inf.path) > 1 and inf.last_node == "cross-n"  # mid-leg, more legs after
    window(w)
    assert inf.grounded and inf.path == [leg]  # the current leg only, not on to static-hq


def test_grounding_drops_the_claim_order_and_leader_and_refuses_new_work() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d")
    claim(w, e, job, [])
    out = window(w)
    assert [ev.kind for ev in out if ev.kind in ("JobReleased", "UnitGrounded")] == [
        "JobReleased",
        "UnitGrounded",
    ]
    assert (e.job_id, e.order, e.follow_id, e.id in job.claims) == (None, None, None, False)
    assert not is_idle(RULES, e, "COALITION")  # the board gives it no job
    director = put(w, "ENEMY_ARMOR", "fob-n-e", owner="ENEMY_DIRECTOR")
    director.grounded = True
    assert director not in _spare(w, "ENEMY").get("ENEMY_ARMOR", [])  # nor does the Director


def test_upkeep_runs_before_the_director_window_in_the_same_tick() -> None:
    """EC-10: a Director unit idle past `director.idle_retire_s` (600 game s) is retired at the
    window, unless upkeep grounded it first in that tick: a grounded unit is not the Director's
    to retire, reuse or recall (`launch._spare`)."""
    config = pre_5b_config(
        {**LIMITED, "economy.upkeep.ENEMY_ARMOR": 5, "economy.upkeep_period.ENEMY_ARMOR": 1}
    )
    w = new_world(config=config)
    w.stock["fob-n-e"] = 0  # its home cannot pay
    armor = put(w, "ENEMY_ARMOR", "fob-n-e", owner="ENEMY_DIRECTOR")  # no garrison `home`
    w.director["ENEMY"].idle[str(armor.id)] = 1  # idle since running tick 1
    w.campaign.tick = w.campaign.running_ticks = 6599  # the next tick is a window of both
    out = step(w, [])
    mine = [ev.kind for ev in out if getattr(ev, "entity_id", None) == armor.id]
    assert mine == ["UnitGrounded"]  # not UnitDespawned{RETIRED}
    assert w.find(armor.id) is armor and armor.grounded


def grounded_jet(w: World) -> Entity:
    """A viewer jet grounded at a dry west-airbase (stock 0)."""
    w.stock["west-airbase"] = 0
    jet = put(w, JET, "west-airbase")
    window(w)
    assert jet.grounded
    return jet


def send(w: World, e: Entity, node: str) -> list[Event]:
    return step(w, [rebase(e, node).model_copy(update={"target_tick": w.campaign.tick + 1})])


def rejected(out: list[Event]) -> list[str]:
    return [ev.reason for ev in out if isinstance(ev, CommandRejected)]


def test_a_grounded_jet_rebases_to_a_base_that_pays_it_and_ungrounds_at_the_next_window() -> None:
    """NX-435 (Q-TD-51 U3): the jet flies west-airbase -> haven still grounded, holding; landing
    makes haven its home (EC-5), and the next window charges it there (the pool) and ungrounds."""
    w = new_world()
    jet = grounded_jet(w)
    assert rejected(send(w, jet, "haven")) == []
    assert (jet.path, jet.order, jet.grounded) == (["haven"], "HOLD", True)
    assert state_hash(load(save(w))) == state_hash(w)  # a grounded unit on a HOLD saves and loads
    out: list[Event] = []
    for _ in range(10**5):  # bounded: a jet that never lands fails, never hangs
        if not jet.path and jet.state == "LANDED":
            break
        out += step(w, [])
    else:
        raise AssertionError("the jet never landed at haven")
    out += step(w, [])  # `logistics` homes it on the tick it stands landed
    assert (jet.last_node, jet.home_base, jet.grounded) == ("haven", "haven", True)
    assert [r for r in rows(out) if r[0] != "SupplyConsumed"] == []  # no window ungrounded it yet
    pool = w.pool["COALITION"]
    for _ in range(10**5):  # bounded: a jet that never ungrounds fails, never hangs
        if not jet.grounded:
            break
        out = step(w, [])
    else:
        raise AssertionError("no window ungrounded the jet")
    assert rows(out) == [("UnitUngrounded", jet.id, "haven"), ("SupplyConsumed", "haven", 5)]
    assert w.campaign.running_ticks % WINDOW == 0  # at a window
    income = [ev.amount for ev in out if ev.kind == "SupplyProduced"]
    assert w.pool["COALITION"] == pool + sum(income) - 5  # the jet's upkeep, from haven's pool


def test_a_grounded_unit_may_not_rebase_to_a_base_that_cannot_pay_it() -> None:
    w = new_world()
    jet = grounded_jet(w)
    w.pool["COALITION"] = 4  # one short of the jet's upkeep of 5
    assert rejected(send(w, jet, "haven")) == ["UNIT_GROUNDED"]
    w.stock["fob-n-w"] = 0
    inf = put(w, INF, "fob-n-w")
    window(w)
    assert inf.grounded
    assert rejected(send(w, inf, "west-airbase")) == ["UNIT_GROUNDED"]  # dry (stock 0)
    assert rejected(send(w, inf, "fob-n-w")) == ["UNIT_GROUNDED"]  # its own dry home
    assert (jet.path, jet.order, inf.path, inf.order) == ([], None, [], None)
    w.pool["COALITION"] = 5  # exactly its upkeep
    assert rejected(send(w, jet, "haven")) == []
    assert jet.path == ["haven"]


@given(stock=st.integers(0, 12))
def test_a_grounded_unit_rebases_exactly_when_the_target_holds_its_upkeep(stock: int) -> None:
    w = new_world()
    w.stock["fob-n-w"], w.stock["west-airbase"] = 0, stock
    inf = put(w, INF, "fob-n-w")
    window(w)
    accepted = rejected(send(w, inf, "west-airbase")) == []
    assert accepted == (stock >= 5)  # the infantry's upkeep
    assert (inf.order, inf.grounded, w.stock["west-airbase"]) == (
        "HOLD" if accepted else None, True, stock,  # the check moves no stock
    )  # fmt: skip


def test_a_grounded_unit_rebase_checks_the_node_before_the_pay() -> None:
    """The node checks come first, so a bad node keeps its own reason."""
    w = new_world()
    jet = grounded_jet(w)
    assert rejected(send(w, jet, "nowhere")) == ["NODE_UNKNOWN"]
    assert rejected(send(w, jet, "east-airbase")) == ["NODE_NOT_FRIENDLY"]
    assert rejected(send(w, jet, "fob-n-w")) == ["NODE_INVALID_FOR_UNIT"]


def test_a_paying_unit_still_rebases_to_a_dry_base() -> None:
    w = new_world()
    w.stock["west-airbase"] = 0
    jet = put(w, JET, "haven")
    assert rejected(send(w, jet, "west-airbase")) == []
    assert (jet.path, jet.order, jet.grounded) == (["west-airbase"], "HOLD", False)


def test_a_grounded_unit_takes_no_other_order() -> None:
    w = new_world()
    jet = grounded_jet(w)
    cmd = join(1, "STRIKE", "fob-n-w", issuer={"commander_id": jet.commander_id})
    out = step(w, [cmd.model_copy(update={"target_tick": w.campaign.tick + 1})])
    assert rejected(out) == ["UNIT_IN_SORTIE"]
    assert (jet.path, jet.order, jet.grounded) == ([], None, True)


def test_a_grounded_unit_under_rebase_ungrounds_on_the_way_when_its_old_home_pays() -> None:
    """Still charged at its old home while it travels (EC-6): a restock there ungrounds it at the
    next window, and it drives on to the REBASE target with its HOLD (infantry at shipped speed:
    the 72 km drive outlasts a window)."""
    w = new_world()
    w.stock["fob-n-w"], w.stock["west-airbase"] = 0, 5
    inf = put(w, INF, "fob-n-w")
    window(w)
    assert rejected(send(w, inf, "west-airbase")) == []
    w.stock["fob-n-w"] = 10
    out: list[Event] = []
    while inf.grounded:
        out = step(w, [])
        assert w.campaign.running_ticks < 10**5
    assert rows(out) == [("UnitUngrounded", inf.id, "fob-n-w"), ("SupplyConsumed", "fob-n-w", 5)]
    assert (inf.path[-1], inf.order, inf.home_base) == ("west-airbase", "HOLD", "fob-n-w")


def test_a_grounded_rebase_keeps_its_target_when_the_old_home_falls() -> None:
    """`rehome` sends a grounded unit to its new home, but not one travelling under a REBASE; one
    parked on its HOLD (no path left) is sent as before."""
    w = new_world(config=FAST)
    w.stock["fob-s-w"] = 0
    inf = put(w, INF, "fob-s-w")
    parked_ = put(w, INF, "fob-s-w")
    window(w)
    assert rejected(send(w, inf, "haven")) == []
    parked_.order = "HOLD"  # arrived on a grounded REBASE, still grounded
    w.owner["fob-s-w"] = "ENEMY"
    upkeep.rehome(w, "fob-s-w")
    # from fob-s-w (130, 180): west-airbase 72.1 km, fob-n-w 120 km, haven 124 km
    assert (inf.home_base, inf.path[-1], inf.grounded) == ("west-airbase", "haven", True)
    assert (parked_.home_base, parked_.path[-1], parked_.grounded) == (
        "west-airbase", "west-airbase", True,
    )  # fmt: skip


def test_a_grounded_rebase_is_deterministic() -> None:
    def play() -> tuple[str, list[str]]:
        w = new_world()
        jet = grounded_jet(w)
        kinds = [str(ev.kind) for ev in send(w, jet, "haven") + run(w, 2 * WINDOW)]
        return state_hash(w), kinds

    first = play()
    assert "UnitUngrounded" in first[1]
    assert play() == first


def test_a_grounded_unit_still_returns_fire() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    window(w)
    armor = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(130_500.0, 60_000.0))
    armor.last_node = "fob-n-w"
    fired = [ev for ev in run(w, 50) if isinstance(ev, WeaponFired) and ev.shooter_id == e.id]
    assert e.grounded and fired and fired[0].target_id == armor.id


# --- EC-5 home bases -----------------------------------------------------------------------------


def test_spawn_landing_and_parking_set_the_home() -> None:
    w = new_world()
    (spawned,) = [ev for ev in step(w, [join(1, "STRIKE", "fob-n-w")]) if ev.kind == "UnitSpawned"]
    jet = w.get(spawned.entity_id)
    assert spawned.node_id == "west-airbase"  # forward-deployed (GP-7)
    assert jet.home_base == "west-airbase"  # where it spawned
    run(w, 600)
    assert jet.home_base == "west-airbase"  # 600 ticks later: still its spawn base
    w2 = new_world(config=FAST)
    inf = put(w2, INF, "cross-n", home="haven")
    inf.path = ["fob-n-w"]  # drives back over the road and parks at the friendly FOB
    for _ in range(1000):
        step(w2, [])
        if not inf.path:  # parked this tick; the board may send it on from the next pass
            break
    assert (inf.last_node, inf.home_base) == ("fob-n-w", "fob-n-w")


def test_director_spawns_and_the_start_garrison_are_homed_where_they_stand() -> None:
    w = new_world()
    garrison = [e for e in w.entities() if e.owner_kind == "ENEMY_DIRECTOR"]
    assert garrison and all(e.home_base == e.last_node == e.home for e in garrison)
    unit, node = _spawn(w, RULES, "ENEMY", "ENEMY_ARMOR", "fob-n-e", [], at="static-hq")
    assert (node, unit.home_base) == ("static-hq", "static-hq")


def test_the_order_tick_is_the_spawn_then_the_latest_rebase() -> None:
    w = new_world()
    run(w, 10)
    (spawned,) = [
        ev
        for ev in step(w, [join(1, "LOGI", target_tick=11, hold=True)])
        if ev.kind == "UnitSpawned"
    ]
    truck = w.get(spawned.entity_id)
    assert truck.ordered == 10  # running ticks when its JOIN applied (before the tick's clock)
    run(w, 5)
    cmd = rebase(truck, "west-airbase").model_copy(update={"target_tick": w.campaign.tick + 1})
    step(w, [cmd])
    assert (truck.order, truck.ordered) == ("HOLD", 16)


def test_units_re_home_to_the_nearest_host_when_their_home_falls() -> None:
    w = new_world()
    # equidistant from haven (20 km) and west-airbase (90 km): the lower node id wins the tie
    jet = put(w, JET, "fob-n-w")
    jet.state, jet.last_node, jet.path = "ON_STATION", None, []
    jet.pos = jet.orbit = Vec2(55_000.0, 120_000.0)
    inf = put(w, INF, "fob-n-w")  # nearest base by straight line: west-airbase (72.1 km)
    near = {s: _Presence() for s in SIDES}
    w.capture["fob-n-w"] = CaptureBar("ENEMY", 1)
    assert RULES.capture is not None
    _flip(w, RULES, RULES.capture, "fob-n-w", "ENEMY", near, [])
    assert (jet.home_base, inf.home_base) == ("haven", "west-airbase")
    # fob-s-w is 120 km from fob-n-w, west-airbase sqrt(40^2 + 60^2) = 72.1 km
    assert inf.path[-1] == "west-airbase" or inf.path == []  # escaped toward the nearest base


def test_a_grounded_unit_heads_for_its_new_home_after_a_loss() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    inf = put(w, INF, "cross-n", home="fob-n-w")
    window(w)
    w.owner["fob-n-w"] = "ENEMY"
    upkeep.rehome(w, "fob-n-w")
    # from cross-n (230, 60): west-airbase 152.3 km, fob-s-w 156.2 km, haven 210.6 km
    assert (inf.home_base, inf.path[-1]) == ("west-airbase", "west-airbase")


# --- EC-15 and the rollout: no-op defaults ------------------------------------------------------


def test_an_unlimited_side_pays_nothing() -> None:
    unlimited_coalition = {
        **PAID,
        "economy.unlimited.COALITION": True,
        "economy.unlimited.ENEMY": False,
    }
    w = start_campaign(CAMPAIGN_ID, 1, pre_5b_config(unlimited_coalition))
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    assert rows(window(w)) == []  # the coalition is unlimited: no upkeep, never grounded
    assert (e.grounded, w.stock["fob-n-w"]) == (False, 0)


def test_zero_upkeep_changes_nothing() -> None:
    w = start_campaign(CAMPAIGN_ID, 1, pre_5b_config(LIMITED))  # shipped upkeep: all 0
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    before = (dict(w.stock), dict(w.pool))
    assert rows(window(w)) == []
    assert not e.grounded
    assert w.stock == before[0]


# --- snapshots and determinism -------------------------------------------------------------------


def test_home_and_grounded_survive_a_snapshot_and_bad_ones_are_refused() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w", ordered=0)
    window(w)
    back = load(save(w))
    assert (back.get(e.id).home_base, back.get(e.id).grounded) == ("fob-n-w", True)
    assert state_hash(back) == state_hash(w)
    for field_, value, match in (
        ("home_base", "nowhere", "home_base"),
        ("home_base", None, "grounded"),
        ("order", "GOTO", "grounded"),  # no order but a REBASE hold (NX-435)
        ("ordered", 10**6, "ordered"),
        ("ordered", -1, "ordered"),  # a running tick: never negative
        ("grounded", 1, "grounded"),  # a bool, not a truthy int
    ):
        raw = msgpack.unpackb(save(w), raw=False)
        (rec,) = [r for r in raw["entities"] if r["id"] == e.id]
        rec[field_] = value
        with pytest.raises(ValueError, match=match):
            load(msgpack.packb(raw, use_bin_type=True))


def test_same_seed_and_commands_give_the_same_hash_through_windows_with_a_mid_window_save() -> None:
    # a jet costs more than the coalition's income (50 a window); the Static garrison pays 2 each.
    # The EC-11 load check would refuse such a jet: its viewer count is 0 here (load only)
    config = pre_5b_config(
        {**LIMITED, "economy.upkeep.STRIKE_FIGHTER": 60, "economy.upkeep.ENEMY_ARMOR": 2,
         "economy.upkeep_period.STRIKE_FIGHTER": 1, "economy.upkeep_period.ENEMY_ARMOR": 1,
         "economy.floor_viewer_units": 0,
         "economy.cost_parity": False}  # the jet alone pays (NX-494)
    )  # fmt: skip

    def scenario(snapshot_at: int | None = None) -> tuple[str, list[dict[str, Any]]]:
        w = new_world(7, config)
        w.pool["COALITION"] = 0  # the sanctuary cannot pay: a fresh viewer jet grounds
        events: list[dict[str, Any]] = []
        for tick in range(1, 2 * WINDOW + 1):
            commands = [join(1, "STRIKE", target_tick=tick, hold=True)] if tick == 100 else []
            events += [e.model_dump() for e in step(w, commands)]
            if tick == snapshot_at:
                rules, w = w.rules, load(save(w))
                w.rules = rules
        return state_hash(w), events

    first = scenario()
    grounded = [(e["tick"], e["node_id"]) for e in first[1] if e["kind"] == "UnitGrounded"]
    assert grounded == [(600, "haven")]
    assert any(e["kind"] == "SupplyConsumed" and e["cause"] == "UPKEEP" for e in first[1])
    assert scenario() == first
    assert scenario(snapshot_at=650) == first


# --- EC-3 and EC-4: a mirrored world pays mirrored upkeep (property) ---------------------------

_HOMES = ("a", "b", "c")
UNIT = st.tuples(st.booleans(), st.integers(0, 5), st.sampled_from(_HOMES))  # viewer, ordered, home


def _mirror_world(stock: dict[str, int]) -> World:
    """Coalition bases c-a.. and ENEMY bases e-a.., each side's source, every unit pays 3."""
    er = RULES.economy
    assert er is not None
    rules = dataclasses.replace(
        RULES,
        supply=dataclasses.replace(RULES.supply, rear={"COALITION": "c-rear", "ENEMY": "e-rear"}),
        # positions: a Static base's shortfall sitrep asks whether it is seen (NX-436)
        roads=RoadGraph({f"{p}-{h}": (0, 0) for p in ("c", "e") for h in _HOMES}, ()),
        economy=dataclasses.replace(
            er, upkeep={INF: 3, "ENEMY_ARMOR": 3}, upkeep_period={INF: 1, "ENEMY_ARMOR": 1}
        ),
    )
    w = World.new(Campaign(CAMPAIGN_ID, 1, "cfg-test"), rules)
    sides: tuple[tuple[str, Side], ...] = (("c", "COALITION"), ("e", "ENEMY"))
    w.owner = {f"{p}-{h}": s for p, s in sides for h in _HOMES}
    w.stock = {f"{p}-{h}": n for p in ("c", "e") for h, n in stock.items()}
    w.pool = {"COALITION": 0, "ENEMY": 0}
    return w


@given(units=st.lists(UNIT, max_size=10), stock=st.fixed_dictionaries(
    {h: st.integers(0, 12) for h in _HOMES}))  # fmt: skip
def test_mirrored_sides_pay_and_ground_the_same(units: list[Any], stock: dict[str, int]) -> None:
    w = _mirror_world(stock)
    pairs = []
    for viewer, ordered, home in units:  # created in turn, so ids keep the same order per side
        made = []
        for side, kind, prefix in (("COALITION", INF, "c"), ("ENEMY", "ENEMY_ARMOR", "e")):
            owner: OwnerKind = "COMMANDER" if viewer else (
                "AI_GARRISON" if side == "COALITION" else "ENEMY_DIRECTOR")  # fmt: skip
            e = w.spawn(kind, side, owner, Vec2(0.0, 0.0))  # type: ignore[arg-type]
            e.home_base, e.ordered = f"{prefix}-{home}", ordered
            made.append(e)
        pairs.append(made)
    total = sum(w.stock.values())
    out = window(w)
    for c, e in pairs:
        assert c.grounded == e.grounded
    for h in _HOMES:
        assert w.stock[f"c-{h}"] == w.stock[f"e-{h}"] >= 0
    paid = sum(ev.amount for ev in out if ev.kind == "SupplyConsumed")
    assert total - sum(w.stock.values()) == paid  # every unit debited is reported, exactly
    assert paid == 3 * sum(not c.grounded for pair in pairs for c in pair)


# --- NX-426: the upkeep period (Q-TD-41, Q-TD-52 D1) ---------------------------------------------
# GARRISON_INFANTRY pays its 5 every 4 windows: in the window whose index (running ticks / the
# window length, from 1) plus its id is a multiple of 4, and every window while grounded.
EVERY_4 = pre_5b_config({**LIMITED, **PAID, "economy.upkeep_period.GARRISON_INFANTRY": 4})


def window_at(w: World, index: int) -> list[Event]:
    """Economy window number `index` (from 1): `window` at that window's boundary."""
    w.campaign.running_ticks = index * WINDOW - 1
    w.campaign.tick = max(w.campaign.tick, index * WINDOW - 1)
    out: list[Event] = []
    economy.window(w, out)
    upkeep.upkeep(w, out)
    return out


def test_a_unit_with_period_4_pays_once_every_4_windows_on_its_staggered_window() -> None:
    w = new_world(config=EVERY_4)
    w.stock["fob-n-w"] = 100
    e = put(w, INF, "fob-n-w")
    due = [i for i in range(1, 13) if rows(window_at(w, i))]
    assert due == [i for i in range(1, 13) if (i + e.id) % 4 == 0] and len(due) == 3
    assert w.stock["fob-n-w"] == 100 - 3 * 5


def test_units_with_consecutive_ids_spread_their_payments_across_windows() -> None:
    w = new_world(config=EVERY_4)
    w.stock["fob-n-w"] = 100
    units = [put(w, INF, "fob-n-w") for _ in range(4)]
    for i in range(1, 5):
        assert rows(window_at(w, i)) == [("SupplyConsumed", "fob-n-w", 5)]  # one of four a window
    assert w.stock["fob-n-w"] == 100 - 4 * 5 and not any(u.grounded for u in units)


def test_a_grounded_unit_retries_every_window_then_returns_to_its_stagger() -> None:
    w = new_world(config=EVERY_4)
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    first = next(i for i in range(1, 5) if (i + e.id) % 4 == 0)
    assert rows(window_at(w, first)) == [("UnitGrounded", e.id, "fob-n-w")]
    w.stock["fob-n-w"] = 7
    assert rows(window_at(w, first + 1)) == [  # not its due window: the retry pays
        ("UnitUngrounded", e.id, "fob-n-w"),
        ("SupplyConsumed", "fob-n-w", 5),
    ]
    for i in range(first + 2, first + 4):  # back to its stagger: not charged again until due
        assert rows(window_at(w, i)) == []
    assert rows(window_at(w, first + 4)) == [("UnitGrounded", e.id, "fob-n-w")]  # 2 left < 5


def test_the_stagger_follows_running_ticks_so_a_pause_does_not_shift_it() -> None:
    # paused for 1.5 windows: campaign.tick runs 900 ahead of running_ticks, the stagger does not
    w = new_world(config=EVERY_4)
    w.stock["fob-n-w"] = 100
    e = put(w, INF, "fob-n-w")
    due = []
    for i in range(1, 9):
        w.campaign.running_ticks = i * WINDOW - 1
        w.campaign.tick = w.campaign.running_ticks + 900
        out: list[Event] = []
        upkeep.upkeep(w, out)
        if rows(out):
            due.append(i)
    assert due == [i for i in range(1, 9) if (i + e.id) % 4 == 0] and len(due) == 2


def test_a_grounded_unit_still_short_is_charged_again_without_a_second_event() -> None:
    w = new_world(config=EVERY_4)
    w.stock["fob-n-w"] = 0
    e = put(w, INF, "fob-n-w")
    first = next(i for i in range(1, 5) if (i + e.id) % 4 == 0)
    window_at(w, first)
    w.stock["fob-n-w"] = 4  # short of 5 every window: it stays grounded, nothing is debited
    for i in range(first + 1, first + 5):
        assert rows(window_at(w, i)) == [] and e.grounded
    assert w.stock["fob-n-w"] == 4


def test_owed_is_the_per_window_average_rounded_up_once_per_side() -> None:
    w = new_world(config=EVERY_4)
    assert upkeep.owed(w, "COALITION") == 0
    put(w, INF, "fob-n-w")
    assert upkeep.owed(w, "COALITION") == 2  # ceil(5/4)
    put(w, INF, "fob-n-w")
    put(w, INF, "fob-s-w")
    assert upkeep.owed(w, "COALITION") == 4  # ceil(15/4): one rounding, not 3 x ceil(5/4)
    put(w, JET, "west-airbase")  # period 1: 5 a window
    assert upkeep.owed(w, "COALITION") == 9  # ceil(15/4 + 5)
    put(w, "ENEMY_ARMOR", "fob-n-e", owner="ENEMY_DIRECTOR")  # upkeep 0
    assert upkeep.owed(w, "ENEMY") == 0


@given(count=st.integers(1, 12), period=st.integers(1, 6), start=st.integers(1, 30))
def test_with_enough_stock_each_unit_pays_exactly_once_per_period(
    count: int, period: int, start: int
) -> None:
    config = pre_5b_config({**LIMITED, **PAID, "economy.upkeep_period.GARRISON_INFANTRY": period})
    w = new_world(config=config)
    w.stock["fob-n-w"] = 5 * count
    units = [put(w, INF, "fob-n-w") for _ in range(count)]
    paid = 0
    for i in range(start, start + period):
        amount = sum(ev.amount for ev in window_at(w, i) if ev.kind == "SupplyConsumed")
        assert amount == 5 * sum((i + u.id) % period == 0 for u in units)
        paid += amount
    assert paid == 5 * count and w.stock["fob-n-w"] == 0
    assert not any(u.grounded for u in units)


def test_staggered_upkeep_is_deterministic_through_a_mid_window_save() -> None:
    # the jet (60, every 3 windows) costs more than the empty sanctuary holds: it grounds at its
    # due window and retries every window after; the Static garrison pays 2 every 3 windows.
    # The EC-11 load check would refuse such a jet: its viewer count is 0 here (load only)
    config = pre_5b_config({
        **LIMITED, "economy.upkeep.STRIKE_FIGHTER": 60, "economy.upkeep.ENEMY_ARMOR": 2,
        "economy.upkeep_period.STRIKE_FIGHTER": 3, "economy.upkeep_period.ENEMY_ARMOR": 3,
        "economy.floor_viewer_units": 0,
        "economy.cost_parity": False,  # the jet alone pays (NX-494)
    })  # fmt: skip

    def scenario(snapshot_at: int | None = None) -> tuple[str, list[dict[str, Any]]]:
        w = new_world(7, config)
        w.pool["COALITION"] = 0
        events: list[dict[str, Any]] = []
        for tick in range(1, 3 * WINDOW + 1):
            commands = [join(1, "STRIKE", target_tick=tick, hold=True)] if tick == 100 else []
            events += [e.model_dump() for e in step(w, commands)]
            if tick == snapshot_at:
                rules, w = w.rules, load(save(w))
                w.rules = rules
        return state_hash(w), events

    first = scenario()
    assert [e["kind"] for e in first[1]].count("UnitGrounded") == 1
    assert any(e["kind"] == "SupplyConsumed" and e["cause"] == "UPKEEP" for e in first[1])
    assert scenario() == first
    assert scenario(snapshot_at=1250) == first
