"""NX-412 part 1 (ECONOMY EC-1, EC-2, EC-3, EC-10 steps 1-2, EC-15): source pools, income,
storage and unlimited mode.

Expected numbers are worked by hand from the shipped `economy` values (income floor 30, per node
AIRBASE 10, HQ 10, FOB 5; storage floor 2000, per node AIRBASE 2000, HQ 2000, FOB 1000; window
60 game s = 600 ticks) and strait-1's start owners (Static: fob-n-e, fob-s-e, east-airbase,
static-hq; coalition: west-airbase, fob-n-w, fob-s-w; the bridges and crossings neutral).
"""

import dataclasses
from typing import Any

import msgpack
import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID, join

from nexus.contracts.gen.common.enums import NodeKind, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import economy
from nexus.core.logistics import plan_run
from nexus.core.rules import EconomyRules, Rules, Supply
from nexus.core.step import step
from nexus.core.tasking import _load
from nexus.core.world import Campaign, CaptureBar, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import start_campaign
from nexus.runtime.golden import shipped_config

_UPKEEP_KINDS: tuple[UnitKind, ...] = (
    "ENEMY_ARMOR", "ENEMY_CONVOY", "ENEMY_FIGHTER", "ENEMY_RECON_UAV", "ENEMY_STRIKE_FIGHTER",
    "GARRISON_INFANTRY", "LOGI_TRUCK", "RECON_UAV", "STRIKE_FIGHTER",
)  # fmt: skip
LIMITED = shipped_config({"economy.unlimited.COALITION": False, "economy.unlimited.ENEMY": False})
WINDOW = 600  # 60 game s at 10 Hz


def limited_world(seed: int = 12345) -> World:
    return start_campaign(CAMPAIGN_ID, seed, LIMITED)


def run_window(w: World) -> list[Event]:
    """Run the economy window as the tick that crosses the boundary does."""
    w.campaign.running_ticks = WINDOW - 1
    out: list[Event] = []
    economy.window(w, out)
    return out


def kinds(out: list[Event]) -> list[tuple[Any, ...]]:
    """Each event as (kind, side, amount) or (kind, node, amount, cause)."""
    rows: list[tuple[Any, ...]] = []
    for e in out:
        d = e.model_dump()
        if d["kind"] == "SupplyProduced":
            rows.append((d["kind"], d["side"], d["amount"]))
        else:
            rows.append((d["kind"], d["node_id"], d["amount"], d["cause"]))
    return rows


def test_the_shipped_default_is_unlimited_for_both_sides_and_keeps_infinite_sources() -> None:
    w = start_campaign(CAMPAIGN_ID, 1, shipped_config({}))
    assert w.rules is not None and w.rules.economy is not None
    assert w.rules.economy.limited == ()  # Q-TD-29: temporary default until the NX-412 sweep
    assert (w.pool, w.storage) == ({}, {})  # the snapshot names the mode: no pool = unlimited
    assert run_window(w) == []
    run = plan_run(w, w.rules, "COALITION", "cross-n")
    assert run is not None and run.source == "haven"


def test_the_loader_reads_every_economy_key() -> None:
    er = LIMITED.rules.economy
    assert er == EconomyRules(
        window_ticks=WINDOW,
        limited=("COALITION", "ENEMY"),
        income_floor=30,
        income_per_node={"AIRBASE": 10, "BRIDGE": 0, "FOB": 5, "HQ": 10, "PORT": 5},
        storage_floor=2000,
        storage_per_node={"AIRBASE": 2000, "BRIDGE": 0, "FOB": 1000, "HQ": 2000, "PORT": 1000},
        upkeep=dict.fromkeys(_UPKEEP_KINDS, 0),  # NX-412 part 2: the shipped rollout 0
    )
    only_enemy = shipped_config({"economy.unlimited.ENEMY": False, "economy.window_s": 90})
    assert only_enemy.rules.economy is not None
    assert (only_enemy.rules.economy.limited, only_enemy.rules.economy.window_ticks) == (
        ("ENEMY",),
        900,
    )


def test_pools_start_full_at_the_storage_of_the_start_holdings() -> None:
    w = limited_world()
    assert w.storage == {"COALITION": 6000, "ENEMY": 8000}  # 2000+2000+1000+1000; +2000 for HQ
    assert w.pool == w.storage


def test_income_per_window_with_nodes_held_contested_and_lost() -> None:
    w = limited_world()
    w.pool = {"COALITION": 0, "ENEMY": 100}
    assert kinds(run_window(w)) == [
        ("SupplyProduced", "COALITION", 50),  # 30 + AIRBASE 10 + 2 FOB x 5
        ("SupplyProduced", "ENEMY", 60),  # 30 + AIRBASE 10 + HQ 10 + 2 FOB x 5
    ]
    assert w.pool == {"COALITION": 50, "ENEMY": 160}
    w.capture["fob-n-e"] = CaptureBar("COALITION", 5)  # contested: earns nothing, still stores
    assert kinds(run_window(w))[1] == ("SupplyProduced", "ENEMY", 55)
    assert w.storage["ENEMY"] == 8000
    del w.capture["fob-n-e"]
    w.owner["east-airbase"] = "COALITION"  # lost: it now earns for the coalition
    assert kinds(run_window(w)) == [
        ("SupplyProduced", "COALITION", 60),
        ("SupplyProduced", "ENEMY", 50),
    ]


def test_income_runs_only_on_the_window_tick_and_never_while_paused() -> None:
    w = limited_world()
    w.pool = {"COALITION": 0, "ENEMY": 0}
    w.campaign.running_ticks = WINDOW - 2
    out: list[Event] = []
    economy.window(w, out)
    assert (out, w.pool) == ([], {"COALITION": 0, "ENEMY": 0})
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    assert run_window(w) == []


def test_income_never_fills_past_storage() -> None:
    w = limited_world()
    w.pool = {"COALITION": 5990, "ENEMY": 8000}
    assert kinds(run_window(w)) == [("SupplyProduced", "COALITION", 10)]  # full: no event
    assert w.pool == {"COALITION": 6000, "ENEMY": 8000}


def test_a_lost_node_lowers_storage_and_the_clip_is_reported_as_storage_lost() -> None:
    w = limited_world()
    w.owner["east-airbase"] = "COALITION"
    out = run_window(w)
    # ENEMY cap 8000 - 2000 = 6000: its full pool loses 2000 and earns nothing (it was above it);
    # the coalition's cap rises to 8000 and its full pool takes its income, now 60.
    assert kinds(out) == [
        ("SupplyProduced", "COALITION", 60),
        ("SupplyConsumed", "static-rear", 2000, "STORAGE_LOST"),
    ]
    assert w.pool == {"COALITION": 6060, "ENEMY": 6000}
    assert w.storage == {"COALITION": 8000, "ENEMY": 6000}


def test_a_truck_loads_from_the_pool_and_an_empty_pool_loads_nothing() -> None:
    w = limited_world()
    for n in ("fob-n-w", "fob-s-w"):
        w.stock[n] = 250  # at the floor: the sanctuary is the only source for west-airbase
    w.pool["COALITION"] = 40
    first = _join(w, 1)
    assert (first.last_node, first.cargo, w.pool["COALITION"]) == ("haven", 40, 0)
    second = _join(w, 2)  # an empty pool loads nothing, as an empty base would
    assert (second.last_node, second.cargo, w.pool["COALITION"]) == ("haven", 0, 0)
    assert w.stock["west-airbase"] == 1000


def test_a_convoy_at_its_rear_source_loads_at_most_the_pool() -> None:
    w = limited_world()
    convoy = w.spawn("ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", Vec2(*_pos(w, "static-rear")))
    convoy.last_node = "static-rear"
    w.pool["ENEMY"] = 30
    _load(w, convoy, "static-rear", "east-airbase")
    assert (convoy.cargo, w.pool["ENEMY"]) == (30, 0)
    convoy.cargo = 0
    _load(w, convoy, "static-rear", "east-airbase")
    assert (convoy.cargo, w.pool["ENEMY"]) == (0, 0)
    assert plan_run(w, LIMITED.rules, "ENEMY", "east-airbase") is not None


def test_unlimited_on_one_side_leaves_it_infinite_and_the_other_side_limited() -> None:
    w = start_campaign(CAMPAIGN_ID, 1, shipped_config({"economy.unlimited.ENEMY": False}))
    assert w.pool == {"ENEMY": 8000}
    for n in ("fob-n-w", "fob-s-w"):
        w.stock[n] = 250
    truck = _join(w, 1)
    assert (truck.last_node, truck.cargo, w.pool) == ("haven", 100, {"ENEMY": 8000})
    assert [e.kind for e in run_window(w)] == []  # ENEMY full; the coalition has no pool


def test_pools_survive_a_snapshot_and_a_mismatched_snapshot_is_refused() -> None:
    w = limited_world()
    w.pool["ENEMY"] = 123
    back = load(save(w))
    assert (back.pool, back.storage) == (w.pool, w.storage)
    assert state_hash(back) == state_hash(w)
    raw = msgpack.unpackb(save(w), raw=False)
    raw["storage"] = {"ENEMY": 8000}
    with pytest.raises(ValueError, match="same sides"):
        load(msgpack.packb(raw, use_bin_type=True))
    raw = msgpack.unpackb(save(w), raw=False)
    raw["pool"]["ENEMY"] = -1
    with pytest.raises(ValueError, match="pool"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_same_seed_and_commands_give_the_same_hash_through_two_windows() -> None:
    def scenario(snapshot_at: int | None = None) -> tuple[str, list[dict[str, Any]]]:
        w = limited_world(7)
        w.pool = {"COALITION": 0, "ENEMY": 0}
        events: list[dict[str, Any]] = []
        for tick in range(1, 2 * WINDOW + 1):
            commands = [join(1, "LOGI", "west-airbase", target_tick=tick)] if tick == 700 else []
            events += [e.model_dump() for e in step(w, commands)]
            if tick == snapshot_at:
                rules, w = w.rules, load(save(w))
                w.rules = rules
        return state_hash(w), events

    first = scenario()
    produced = [e for e in first[1] if e["kind"] == "SupplyProduced"]
    assert [(e["tick"], e["side"], e["amount"]) for e in produced] == [
        (600, "COALITION", 50), (600, "ENEMY", 60), (1200, "COALITION", 50), (1200, "ENEMY", 60),
    ]  # fmt: skip
    assert scenario() == first
    assert scenario(snapshot_at=650) == first


# --- EC-3: a mirrored theater gives mirrored pools ------------------------------------------------

_KINDS: tuple[NodeKind, ...] = ("AIRBASE", "BRIDGE", "FOB", "HQ", "PORT")
_OTHER: dict[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}


def _mirrored(kinds_: list[NodeKind]) -> World:
    """Node pairs c<i> and e<i> of the same kind, each side's sanctuary, both sides limited."""
    nodes = {f"c{i}": k for i, k in enumerate(kinds_)} | {f"e{i}": k for i, k in enumerate(kinds_)}
    rules: Rules = dataclasses.replace(
        LIMITED.rules,
        node_kind=dict(sorted(nodes.items())),
        supply=Supply(rear={"COALITION": "c-rear", "ENEMY": "e-rear"}),
        defense=None,
    )
    w = World.new(Campaign(CAMPAIGN_ID, 1, "cfg-test"), rules)
    w.owner = {n: "COALITION" if n.startswith("c") else "ENEMY" for n in rules.node_kind}
    economy.start(w)
    return w


STEP = st.tuples(st.integers(0, 7), st.sampled_from(["flip", "contest", "clear", "spend"]))


@given(
    kinds_=st.lists(st.sampled_from(_KINDS), min_size=1, max_size=8),
    steps=st.lists(STEP, max_size=12),
)
def test_mirrored_sides_keep_mirrored_pools(kinds_: list[NodeKind], steps: list[Any]) -> None:
    w = _mirrored(kinds_)
    assert w.pool["COALITION"] == w.pool["ENEMY"]
    for index, action in steps:
        i = index % len(kinds_)
        pairs: tuple[tuple[Side, str, str], ...] = (
            ("COALITION", f"c{i}", f"e{i}"),
            ("ENEMY", f"e{i}", f"c{i}"),
        )
        for side, mine, theirs in pairs:
            if action == "flip":  # each side takes the other's twin node: still mirrored
                w.owner[theirs] = side
            elif action == "contest":
                w.capture[mine] = CaptureBar(_OTHER[side], 1)
            elif action == "clear":
                w.capture.pop(mine, None)
            else:
                w.pool[side] -= min(w.pool[side], 100 * (i + 1))
        out = run_window(w)
        assert w.pool["COALITION"] == w.pool["ENEMY"]
        assert w.storage["COALITION"] == w.storage["ENEMY"]
        by_side = [(e.kind, getattr(e, "amount", None)) for e in out]
        assert by_side[: len(by_side) // 2] == by_side[len(by_side) // 2 :]


def _pos(w: World, node: str) -> tuple[float, float]:
    assert w.rules is not None
    return w.rules.roads.pos[node]


def _join(w: World, n: int) -> Any:
    before = {e.id for e in w.entities()}
    step(w, [join(n, "LOGI", "west-airbase", target_tick=w.campaign.tick + 1)])
    (unit,) = (e for e in w.entities() if e.id not in before)
    return unit
