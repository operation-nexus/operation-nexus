"""NX-416: forward staging for the Static (THREAT-DIRECTOR §4a FS-1..FS-8; Q-TD-36..Q-TD-38).

Runs on the shipped strait-1 config with `economy.legacy_rules` false (flipped through the shipped
profile), the campaign layer off and no opening garrison (as test_economy_rules). Shipped numbers:
`director.staging.direct_s` 1500 game s (15,000 ticks), `max_wait_windows` 90, `max_staged` 2;
OFFENSIVE costs 60 (STAGE 2 armor, STRIKE 2 jets, CAPTURE 2 armor: 10 a unit, so 40 for the
armor at an FOB and 20 for the jets at their own spawn node), PROBE 15; an FOB holds at
most 1,000 stock with a starvation floor of 250; ENEMY_ARMOR drives 20 m/s (world), 12 m a tick.
Road travel for ENEMY_ARMOR (`roads.travel_ticks`, every bridge up): static-rear to fob-n-w
285 km, 23,750 ticks (39.6 game min, past direct_s); to fob-n-w from fob-n-e about 163 km, from
east-airbase 200 km; west-airbase is equally far from fob-n-e and fob-s-e (a tie, by id).
"""

import dataclasses

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import launch as launch_mod
from nexus.core import operations as ops
from nexus.core import staging as stg
from nexus.core.bridges import enemy_held
from nexus.core.fog import side_view
from nexus.core.launch import _convoys, _launch, _own, _Purse, _staged_shares
from nexus.core.launch import run as launch
from nexus.core.logistics import _base_share, stock_targets
from nexus.core.provocation import validate
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking_gen import _resupply
from nexus.core.world import CaptureBar, Contact, Staged, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.golden import shipped_config

NEW: dict[str, object] = {"economy.legacy_rules": False}
STATIC_BASES = ("east-airbase", "fob-n-e", "fob-s-e", "static-hq")


def config(overrides: dict[str, object] | None = None) -> CampaignConfig:
    c = shipped_config({**NEW, **(overrides or {})})
    return dataclasses.replace(c, rules=dataclasses.replace(c.rules, campaign=None))


SHIPPED = config()


def world(c: CampaignConfig = SHIPPED, seed: int = 1) -> World:
    rules = dataclasses.replace(c.rules, garrison_quota={})
    return start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(c, rules=rules))


def at_floor(w: World, *nodes: str) -> None:
    assert w.rules is not None
    for n in nodes or STATIC_BASES:
        w.stock[n] = w.rules.supply.starve_floor[n]


def offensive(w: World, target: str) -> ops.Candidate:
    assert w.rules is not None
    s = w.director["ENEMY"]
    c = ops.candidate(
        "OFFENSIVE", target, s, side_view(w, "ENEMY"), w.rules, _own(w, w.rules, "ENEMY"),
        w.campaign.running_ticks + 1,
    )  # fmt: skip
    assert c is not None
    return c


def fire(w: World, c: ops.Candidate, budget: int = 60) -> list[Event]:
    """`launch._launch` of `c` with a window purse of `budget` (unlimited Static: one account)."""
    assert w.rules is not None and w.rules.director is not None
    out: list[Event] = []
    purse = _Purse.of(budget, w.pool.get("ENEMY"), w.rules.director)
    _launch(w, w.rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], c, out, purse)
    return out


def window(w: World, budget: int = 60, tier: str = "ALPHA") -> list[Event]:
    """One window of operations (`launch.run`) with `budget` points."""
    assert w.rules is not None
    s = w.director["ENEMY"]
    s.tier, s.budget = tier, budget  # type: ignore[assignment]
    s.windows += 1
    out: list[Event] = []
    launch(w, "ENEMY", side_view(w, "ENEMY"), w.rules, out)
    return out


def staging_events(out: list[Event]) -> list[tuple[str, str, str | None]]:
    return [
        (e.sector_id, e.direction, e.node_id)
        for e in out
        if e.kind == "ThreatAdaptation" and e.category == "STAGING"
    ]


def debits(out: list[Event]) -> list[tuple[str, int]]:
    return [(e.node_id, e.amount) for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN"]


def spawns(out: list[Event]) -> list[tuple[str, str]]:
    return [(e.unit_kind, e.node_id) for e in out if e.kind == "UnitSpawned"]


# --- the keys (FS-8) ------------------------------------------------------------------------------


def test_the_loader_reads_the_staging_keys_as_ticks_and_counts() -> None:
    dr = SHIPPED.rules.director
    assert dr is not None
    assert (dr.staging_direct_ticks, dr.staging_max_wait_windows, dr.staging_max_staged) == (
        15_000, 90, 2,
    )  # fmt: skip
    other = config(
        {
            "director.staging.direct_s": 600.5,
            "director.staging.max_wait_windows": 3,
            "director.staging.max_staged": 1,
        }
    ).rules.director
    assert other is not None
    assert (other.staging_direct_ticks, other.staging_max_wait_windows) == (6005, 3)
    assert other.staging_max_staged == 1


# --- FS-1: when to stage --------------------------------------------------------------------------


def test_only_a_capture_operation_past_direct_s_is_staged() -> None:
    w = world()
    rules, view = SHIPPED.rules, side_view(w, "ENEMY")
    dr = rules.director
    assert dr is not None
    probe = next(o for o in dr.operations if o.id == "PROBE")
    offense = offensive(w, "fob-n-w").op
    assert stg.far(rules, view, offense, "fob-n-w")  # 23,750 ticks > 15,000
    assert not stg.far(rules, view, probe, "fob-n-w")  # no CAPTURE job
    near = config({"director.staging.direct_s": 2400}).rules  # 24,000 ticks: not past it
    assert not stg.far(near, view, offense, "fob-n-w")
    exact = config({"director.staging.direct_s": 2375}).rules  # 23,750: equal is not past
    assert not stg.far(exact, view, offense, "fob-n-w")
    assert stg.far(config({"director.staging.direct_s": 2374.9}).rules, view, offense, "fob-n-w")


def test_a_near_target_spawns_as_ec_13_says_and_nothing_is_staged() -> None:
    w = world(config({"director.staging.direct_s": 3600}))
    out = fire(w, offensive(w, "fob-n-w"))
    assert staging_events(out) == [] and w.director["ENEMY"].staged == []
    assert debits(out) == [("east-airbase", 60)]  # EC-13: plan_deploy's base for the jets


def test_legacy_rules_never_stage() -> None:
    legacy = shipped_config({})  # the shipped default: economy.legacy_rules true
    w = world(dataclasses.replace(legacy, rules=dataclasses.replace(legacy.rules, campaign=None)))
    at_floor(w, "fob-n-e")
    out: list[Event] = []
    assert w.rules is not None
    s = w.director["ENEMY"]
    _launch(w, w.rules, "ENEMY", side_view(w, "ENEMY"), s, offensive(w, "fob-n-w"), out, None)
    assert staging_events(out) == [] and s.staged == []
    assert sum(a for _, a in debits(out)) == 60  # paid from the surplus as before


# --- FS-2: the base -------------------------------------------------------------------------------


def test_the_base_is_the_nearest_host_by_road_and_ties_go_by_id() -> None:
    w = world()
    rules, view = SHIPPED.rules, side_view(w, "ENEMY")
    op = offensive(w, "fob-n-w").op
    assert stg.base_for(w, rules, "ENEMY", view, op, "fob-n-w") == "fob-n-e"
    assert stg.base_for(w, rules, "ENEMY", view, op, "fob-s-w") == "fob-s-e"
    assert stg.base_for(w, rules, "ENEMY", view, op, "west-airbase") == "fob-n-e"  # tie: by id
    w.owner["fob-n-e"] = "COALITION"
    assert stg.base_for(w, rules, "ENEMY", view, op, "west-airbase") == "fob-s-e"
    assert stg.base_for(w, rules, "ENEMY", view, op, "fob-n-w") == "east-airbase"


def test_a_contested_base_is_no_host_and_none_nearer_than_the_rear_is_no_staging() -> None:
    w = world()
    rules, view = SHIPPED.rules, side_view(w, "ENEMY")
    op = offensive(w, "fob-n-w").op
    w.capture["fob-n-e"] = CaptureBar("COALITION", 1)
    assert not stg.hosts(w, rules, "ENEMY", "fob-n-e", op)
    assert stg.base_for(w, rules, "ENEMY", view, op, "fob-n-w") == "east-airbase"
    w.capture.clear()
    for n in ("east-airbase", "fob-n-e", "static-hq"):  # fob-s-e is 307 km off, the rear 285
        w.owner[n] = "NEUTRAL"
    assert stg.hosts(w, rules, "ENEMY", "fob-s-e", op)
    assert stg.base_for(w, rules, "ENEMY", view, op, "fob-n-w") is None


# --- FS-3, FS-4, FS-5: stage, stock, launch -------------------------------------------------------


def test_staging_announces_the_sector_only_and_waits_when_the_base_cannot_pay() -> None:
    w = world()
    at_floor(w)
    out = fire(w, offensive(w, "fob-n-w"))
    assert staging_events(out) == [("north", "UP", None)]  # FOW-13: never the base
    assert debits(out) == [] and spawns(out) == []
    assert w.director["ENEMY"].staged == [Staged("OFFENSIVE", "fob-n-w", "fob-n-e", 0)]


def test_the_base_target_is_raised_so_a_resupply_job_and_the_convoy_go_there() -> None:
    c = config({"logistics.stock_target_frac": 0.28})  # target 280, floor 250 on an FOB
    w = world(c)
    assert w.rules is not None and w.rules.tasking is not None
    at_floor(w)
    w.stock["fob-n-e"] = 280  # at its own target, 30 over the floor: it cannot pay its 40
    view = side_view(w, "ENEMY")
    before = [
        j.key
        for j in _resupply(
            w, w.rules, w.rules.tasking, "ENEMY", view, enemy_held(w, w.rules, "ENEMY")
        )
    ]
    assert "resupply:fob-n-e" not in before
    fire(w, offensive(w, "fob-n-w"))
    # FS-3 (Q-TD-38): only the 4 armor that spawn at the FOB, 4 x 10 of the 60, not the jets' 20
    assert stock_targets(w, w.rules)["fob-n-e"] == 250 + 40
    assert stock_targets(w, w.rules)["fob-s-e"] == 280  # elsewhere unchanged
    jobs = {
        j.key: j
        for j in _resupply(
            w, w.rules, w.rules.tasking, "ENEMY", view, enemy_held(w, w.rules, "ENEMY")
        )
    }
    assert jobs["resupply:fob-n-e"].slots == 1  # fills 10 to the raised target
    out: list[Event] = []
    assert w.rules.director is not None
    _convoys(w, w.rules, "ENEMY", view, w.director["ENEMY"], w.rules.director, out, None)
    assert [j.node for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"] == ["fob-n-e"]


LIMITED = config({"economy.unlimited.ENEMY": False})
# A pool of 4,000 gives a window's rear account floor(4000 x 0.005) = 20, the jets' share; with a
# budget of 60 the base account is the other 40, the armor's share.
POOL = 4000


def test_a_staged_operation_launches_once_it_can_pay_and_each_spawn_node_pays_its_units() -> None:
    w = world(LIMITED)
    at_floor(w)
    w.pool["ENEMY"] = POOL
    fire(w, offensive(w, "fob-n-w"))
    out = window(w)
    assert debits(out) == [] and len(w.director["ENEMY"].staged) == 1  # still short
    w.stock["fob-n-e"] = 250 + 40  # a convoy delivered the armor's share
    out = window(w)
    # FS-4 (Q-TD-38): 4 armor x 10 at the FOB, 2 jets x 10 from the pool at their spawn node
    assert debits(out) == [("fob-n-e", 40), ("static-rear", 20)]
    assert w.stock["fob-n-e"] == 250 and w.pool["ENEMY"] == POOL - 20
    assert [n for k, n in spawns(out) if k == "ENEMY_ARMOR"] == ["fob-n-e"] * 4
    jets = {n for k, n in spawns(out) if k != "ENEMY_ARMOR"}
    # an FOB hosts no aircraft: they spawn by plan_deploy, here the rear (east-airbase is at floor)
    assert jets == {"static-rear"}
    assert w.director["ENEMY"].staged == []
    assert {j.key for j in w.boards["ENEMY"].values()} >= {"op:OFFENSIVE:fob-n-w:2"}


def test_a_staged_operation_waits_while_its_base_can_pay_but_the_rear_cannot_pay_the_jets() -> None:
    w = world(LIMITED)
    at_floor(w)  # east-airbase at its floor: plan_deploy sends the jets to the rear
    w.pool["ENEMY"] = POOL - 1000  # a rear account of 15: short of the jets' 20
    w.stock["fob-n-e"] = 250 + 40  # the base can pay its armor's share
    out = fire(w, offensive(w, "fob-n-w"))
    assert staging_events(out) == [("north", "UP", None)] and debits(out) == []
    out = window(w)
    assert debits(out) == [] and spawns(out) == [] and len(w.director["ENEMY"].staged) == 1
    w.pool["ENEMY"] = POOL
    out = window(w)
    assert debits(out) == [("fob-n-e", 40), ("static-rear", 20)]
    assert w.director["ENEMY"].staged == []


def jets_at_east_airbase(pool: int) -> World:
    """LIMITED, staged at fob-n-e, which can pay its armor's 40; plan_deploy puts the jets at
    east-airbase (past forward_deploy_min_surplus), whose stock could pay their 20."""
    w = world(LIMITED)
    at_floor(w)
    w.pool["ENEMY"] = pool
    w.stock["east-airbase"] += 60
    w.stock["fob-n-e"] += 40
    fire(w, offensive(w, "fob-n-w"), budget=0)
    assert len(w.director["ENEMY"].staged) == 1
    return w


def test_jets_whose_deploy_base_cannot_pay_spawn_and_pay_at_the_rear() -> None:
    w = jets_at_east_airbase(POOL)
    # budget 60: base account 40, all the armor's; the rear account 20 and the pool pay the jets
    out = window(w)
    assert debits(out) == [("fob-n-e", 40), ("static-rear", 20)]  # Q-TD-39
    assert {n for k, n in spawns(out) if k != "ENEMY_ARMOR"} == {"static-rear"}
    assert [n for k, n in spawns(out) if k == "ENEMY_ARMOR"] == ["fob-n-e"] * 4
    assert w.pool["ENEMY"] == POOL - 20 and w.director["ENEMY"].staged == []


def test_jets_wait_when_neither_their_deploy_base_nor_the_rear_can_pay() -> None:
    w = jets_at_east_airbase(POOL - 1000)  # a rear account of 15: short of the jets' 20
    out = window(w)
    assert debits(out) == [] and spawns(out) == [] and len(w.director["ENEMY"].staged) == 1


def test_jets_spawn_and_pay_at_their_deploy_base_when_it_can_pay() -> None:
    w = jets_at_east_airbase(POOL)
    assert w.rules is not None
    c, purse = offensive(w, "fob-n-w"), _Purse(60, 20)  # base account 60: the armor's 40 + jets' 20
    staged = _staged_shares(w, w.rules, "ENEMY", c, {}, lambda n: 10 * n, purse, "fob-n-e")
    assert staged is not None
    shares, spots = staged
    assert shares == {"fob-n-e": 40, "east-airbase": 20}
    assert sorted(spots) == ["east-airbase"] * 2 + ["fob-n-e"] * 4


def test_a_reused_idle_unit_is_neither_spawned_nor_paid_and_the_jets_still_fall_back() -> None:
    w = jets_at_east_airbase(POOL)
    assert w.rules is not None
    idle = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(*w.rules.roads.pos["fob-n-e"]))
    idle.last_node = "fob-n-e"
    out = window(w)
    # 5 new units of the 6 at 60 x n // 6: 3 armor 30 at the FOB (base account 40 leaves 10), the
    # jets' 20 from the rear account (Q-TD-39); the idle armor takes the first STAGE slot
    assert debits(out) == [("fob-n-e", 30), ("static-rear", 20)]
    assert [n for k, n in spawns(out) if k == "ENEMY_ARMOR"] == ["fob-n-e"] * 3
    assert {n for k, n in spawns(out) if k != "ENEMY_ARMOR"} == {"static-rear"}
    assert idle.job_id is not None and w.director["ENEMY"].staged == []


def test_moved_units_join_the_rear_share_counted_last(monkeypatch: pytest.MonkeyPatch) -> None:
    w = world()
    assert w.rules is not None
    at_floor(w)
    w.stock["fob-n-e"] += 100
    real = launch_mod._staged_spot

    def spot(world: World, rules: Rules, side: Side, kind: UnitKind, near: str, at: str) -> str:
        # the jets' deploy node: an id after "static-rear", with no stock, so it cannot pay
        air = rules.domain[kind] == "AIR"
        return "zz-base" if air else real(world, rules, side, kind, near, at)

    monkeypatch.setattr(launch_mod, "_staged_spot", spot)
    c = offensive(w, "fob-n-w")
    staged = _staged_shares(
        w, w.rules, "ENEMY", c, {}, lambda n: 65 * n // 6, _Purse(1000, 0, one=True), "fob-n-e"
    )
    assert staged is not None
    shares, spots = staged
    # floor(65 x 4 / 6) = 43 at the base, the moved jets' 65 - 43 = 22 at the rear, after it
    assert shares == {"fob-n-e": 43, "static-rear": 22} and sum(shares.values()) == 65
    assert sorted(spots) == ["fob-n-e"] * 4 + ["static-rear"] * 2


def test_one_account_short_of_both_shares_waits_as_the_rear_draws_it_too() -> None:
    w = world()
    assert w.rules is not None
    at_floor(w)
    w.stock["east-airbase"] += 60  # past forward_deploy_min_surplus: plan_deploy puts the jets here
    w.stock["fob-n-e"] += 40  # each base can pay its own share
    out = fire(w, offensive(w, "fob-n-w"), budget=50)  # one account of 50: short of 40 + 20
    assert debits(out) == [] and len(w.director["ENEMY"].staged) == 1
    # unlimited (EC-15): the rear fallback draws the same one account, so it is short there too
    out = window(w, budget=50)
    assert debits(out) == [] and spawns(out) == [] and len(w.director["ENEMY"].staged) == 1
    out = window(w, budget=60)
    assert debits(out) == [("fob-n-e", 40), ("east-airbase", 20)]
    assert {n for k, n in spawns(out) if k != "ENEMY_ARMOR"} == {"east-airbase"}


def test_the_base_share_comes_first_and_matches_the_stock_target_with_an_uneven_cost() -> None:
    w = world()
    assert w.rules is not None
    at_floor(w)
    w.stock["east-airbase"] += 100
    w.stock["fob-n-e"] += 100
    c = offensive(w, "fob-n-w")
    staged = _staged_shares(
        w, w.rules, "ENEMY", c, {}, lambda n: 65 * n // 6, _Purse(1000, 0, one=True), "fob-n-e"
    )
    assert staged is not None
    shares = staged[0]
    # base first: floor(65 x 4 / 6) = 43, the rest 65 - 43 = 22 (by id first it would be 44 + 21)
    assert shares == {"fob-n-e": 43, "east-airbase": 22}
    assert _base_share(w.rules, dataclasses.replace(c.op, cost=65), "fob-n-e") == 43


def test_a_staged_operation_holds_its_budget_share_and_a_max_ops_slot() -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    out = window(w, budget=160)  # 60 held, 100 left, but ALPHA runs one operation at a time
    keys = [j.key for j in w.boards["ENEMY"].values()]
    routine = ops.routine_ops(SHIPPED.rules.director)  # type: ignore[arg-type]
    assert not [k for k in keys if k.split(":")[1] not in routine], keys
    assert debits(out) == [] and len(w.director["ENEMY"].staged) == 1  # none staged on top


def test_a_staged_operation_holds_its_budget_share_with_no_max_ops_cap() -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    window(w, budget=70, tier="BRAVO")  # BRAVO has no max_ops cap; 60 held leaves 10
    dr = SHIPPED.rules.director
    assert dr is not None
    cost = {o.id: o.cost for o in dr.operations}
    posted = {j.key.split(":")[1] for j in w.boards["ENEMY"].values()}
    assert posted and all(cost[op] <= 10 for op in posted), posted


def test_the_wait_runs_out_then_ec_13_launches_it_where_it_can_pay() -> None:
    w = world()
    at_floor(w, "fob-n-e", "fob-s-e", "static-hq")  # east-airbase keeps its 500 surplus
    w.stock["east-airbase"] = w.rules.supply.starve_floor["east-airbase"]  # type: ignore[union-attr]
    fire(w, offensive(w, "fob-n-w"))
    s = w.director["ENEMY"]
    s.windows = 89  # the next window is the 90th since staging started at 0
    w.stock["east-airbase"] += 200
    out = window(w)
    assert debits(out) == [("east-airbase", 60)] and s.staged == []
    assert staging_events(out) == []


def test_the_wait_runs_out_and_with_nothing_to_pay_it_is_dropped() -> None:
    c = config({"economy.unlimited.ENEMY": False})
    w = world(c)
    at_floor(w)
    w.pool["ENEMY"] = 0  # the rear cannot pay either
    fire(w, offensive(w, "fob-n-w"))
    s = w.director["ENEMY"]
    out = window(w, budget=0)  # no budget either, so nothing new is selected
    assert len(s.staged) == 1  # waiting, not yet late
    s.windows = 89
    out = window(w, budget=0)
    assert s.staged == [] and debits(out) == [] and spawns(out) == []
    assert not [j for j in w.boards["ENEMY"].values() if j.key.startswith("op:OFFENSIVE")]


def test_at_most_max_staged_operations_wait_and_the_next_spawns_as_ec_13_says() -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    fire(w, offensive(w, "fob-s-w"))
    out = fire(w, offensive(w, "west-airbase"))
    s = w.director["ENEMY"]
    assert [(x.target, x.base) for x in s.staged] == [
        ("fob-n-w", "fob-n-e"),
        ("fob-s-w", "fob-s-e"),
    ]
    # not staged: EC-13 sends it to the source (unlimited: it pays nothing, so no debit event)
    assert staging_events(out) == [] and {n for _, n in spawns(out)} == {"static-rear"}


# --- FS-6: losing the base ------------------------------------------------------------------------


@pytest.mark.parametrize("how", ["captured", "contested"])
def test_losing_the_base_restages_at_the_next_one_and_keeps_the_wait(how: str) -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    if how == "captured":
        w.owner["fob-n-e"] = "COALITION"
    else:
        w.capture["fob-n-e"] = CaptureBar("COALITION", 1)
    out = window(w)
    assert w.director["ENEMY"].staged == [Staged("OFFENSIVE", "fob-n-w", "east-airbase", 0)]
    assert staging_events(out) == []  # FS-5 (Q-TD-38): the coalition tracks nothing there
    assert debits(out) == []


@pytest.mark.parametrize("what", ["facility", "unit", "disabled", "coalition"])
@pytest.mark.parametrize("tracked", [True, False])
def test_a_restage_is_announced_only_when_the_coalition_tracks_a_static_unit_at_the_new_base(
    what: str, tracked: bool
) -> None:
    w = world()
    assert w.rules is not None
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    w.owner["fob-n-e"] = "COALITION"  # it re-stages at east-airbase
    spot = Vec2(*w.rules.roads.pos["east-airbase"])
    watcher: Side = "COALITION"
    if what in ("facility", "disabled"):  # a site of east-airbase, off the node: by its base_id
        seen = next(e for e in w.entities() if e.base_id == "east-airbase")
        seen.pos = Vec2(spot.x + 500, spot.y)
        if what == "disabled":  # not live: a Disabled site does not count
            seen.damage_state = "DISABLED"
    elif what == "unit":  # a Director unit standing on the node
        seen = w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", spot)
    else:  # a coalition unit on the node, tracked by the Static: not a Static unit
        seen, watcher = w.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", spot), "ENEMY"
    hq = next(e for e in w.entities() if e.base_id == "static-hq")
    w.contacts["COALITION"][hq.id] = Contact(hq.kind, hq.pos, Vec2(0, 0))  # tracked, elsewhere
    # tracked now, or only a last-known track (FOW-6a), which does not count
    w.contacts[watcher][seen.id] = Contact(seen.kind, seen.pos, Vec2(0, 0), None if tracked else 5)
    out = window(w)
    assert w.director["ENEMY"].staged == [Staged("OFFENSIVE", "fob-n-w", "east-airbase", 0)]
    announced = tracked and what in ("facility", "unit")
    assert staging_events(out) == ([("centre", "UP", None)] if announced else [])


def test_with_no_base_left_it_falls_back_at_once() -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    for n in STATIC_BASES:  # every base contested: none can stage, the STAGE job still resolves
        w.capture[n] = CaptureBar("COALITION", 1)
    out = window(w)
    assert w.director["ENEMY"].staged == [] and {n for _, n in spawns(out)} == {"static-rear"}
    assert "op:OFFENSIVE:fob-n-w:2" in {j.key for j in w.boards["ENEMY"].values()}


def test_a_target_no_longer_held_by_the_coalition_is_dropped() -> None:
    w = world()
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    w.owner["fob-n-w"] = "ENEMY"
    window(w)
    assert w.director["ENEMY"].staged == []
    assert not [j for j in w.boards["ENEMY"].values() if j.key.startswith("op:OFFENSIVE:fob-n-w")]


# --- FS-7: state, snapshot, determinism -----------------------------------------------------------


def run(w: World, ticks: int) -> list[dict[str, object]]:
    return [e.model_dump() for _ in range(ticks) for e in step(w, [])]


def staged_world(seed: int = 4) -> World:
    c = shipped_config({**NEW, "director.tier.start": "ALPHA"})
    w = start_campaign(CAMPAIGN_ID, seed, c)
    at_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    assert w.director["ENEMY"].staged
    return w


def test_save_and_load_while_staged_resume_identically() -> None:
    w = staged_world()
    copy = load(save(w))
    copy.rules = w.rules
    assert state_hash(copy) == state_hash(w) and copy.director == w.director
    assert w.rules is not None
    validate(copy, w.rules)
    assert run(copy, 1300) == run(w, 1300)
    assert state_hash(copy) == state_hash(w)


def test_a_staged_run_is_deterministic() -> None:
    def once() -> tuple[str, list[dict[str, object]]]:
        w = staged_world()
        return state_hash(w), run(w, 1300)

    assert once() == once()


def raw_of(w: World) -> dict[str, object]:
    return msgpack.unpackb(save(w), raw=False, strict_map_key=False)  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    ("entry", "match"),
    [
        (
            {"op": "OFFENSIVE", "target": "fob-n-w", "base": "fob-n-e", "since": 5},
            "after the windows",
        ),
        ({"op": "OFFENSIVE", "target": "fob-n-w", "base": "fob-n-e"}, "exactly the keys"),
        ({"op": "OFFENSIVE", "target": 3, "base": "fob-n-e", "since": 0}, "staged target"),
    ],
)
def test_a_corrupt_staged_entry_is_refused(entry: dict[str, object], match: str) -> None:
    raw = raw_of(world())
    raw["director"]["ENEMY"]["staged"] = [entry]  # type: ignore[index]
    with pytest.raises(ValueError, match=match):
        load(msgpack.packb(raw, use_bin_type=True))


def test_staged_entries_out_of_order_or_twice_are_refused() -> None:
    w = world()
    w.director["ENEMY"].windows = 1
    raw = raw_of(w)
    a = {"op": "RETAKE", "target": "fob-n-w", "base": "fob-n-e", "since": 0}
    b = {"op": "OFFENSIVE", "target": "fob-n-w", "base": "fob-n-e", "since": 0}
    for entries in ([a, b], [b, b]):
        raw["director"]["ENEMY"]["staged"] = entries  # type: ignore[index]
        with pytest.raises(ValueError, match="ascending"):
            load(msgpack.packb(raw, use_bin_type=True))


def test_validate_refuses_a_staged_operation_that_is_no_catalog_capture_or_at_no_node() -> None:
    assert SHIPPED.rules is not None
    for bad in (Staged("PROBE", "fob-n-w", "fob-n-e", 0), Staged("OFFENSIVE", "x", "fob-n-e", 0)):
        w = world()
        w.director["ENEMY"].staged = [bad]
        with pytest.raises(ValueError, match="staged operation"):
            validate(w, SHIPPED.rules)


@settings(max_examples=25, deadline=None)
@given(
    lost=st.lists(st.sampled_from(STATIC_BASES), unique=True, max_size=4),
    stock=st.lists(st.integers(0, 400), min_size=4, max_size=4),
    windows=st.integers(1, 3),
)
def test_staged_count_and_bases_hold_after_every_window(
    lost: list[str], stock: list[int], windows: int
) -> None:
    """Invariant: after a window at most `max_staged` operations are staged, each at a base the
    Static holds with no capture bar, and the stock never goes below a floor."""
    w = world()
    at_floor(w)
    for target in ("fob-n-w", "fob-s-w", "west-airbase"):
        fire(w, offensive(w, target))
    assert w.rules is not None
    for n, extra in zip(STATIC_BASES, stock, strict=True):
        w.stock[n] = w.rules.supply.starve_floor[n] + extra
    for n in lost:
        w.owner[n] = "COALITION"
    for _ in range(windows):
        window(w, budget=200)
        s = w.director["ENEMY"]
        assert len(s.staged) <= SHIPPED.rules.director.staging_max_staged  # type: ignore[union-attr]
        for x in s.staged:
            assert w.owner[x.base] == "ENEMY" and x.base not in w.capture
        held = [n for n in STATIC_BASES if w.owner[n] == "ENEMY"]
        assert all(w.stock[n] >= w.rules.supply.starve_floor[n] for n in held)
