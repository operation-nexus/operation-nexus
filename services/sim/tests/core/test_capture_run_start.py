"""NX-513: a capture run starts from a forward base (GAMEPLAY §1b item 23, §4 GP-7; Q-SIM-135).

A truck JOINed to a neutral or enemy node carries nothing; with
`logistics.capture_run_forward_start` it starts at the GP-7 ground forward-deploy base
(`plan_deploy`), else at the sanctuary.
Toy graph: sanctuary `s0`; bases `a` and `e` each 2 km from the neutral target `t` by road, `b`
14 km away, `c` 100 m away by line but on no road. Each base holds 600 over a floor of 100.
"""

import dataclasses
from typing import Any

import pytest
from test_join import CAMPAIGN_ID, cid, join
from test_logistics import RULES, send, truck_for
from test_logistics import new_world as shipped_world

from nexus.core.logistics import Run, plan_run
from nexus.core.roads import Road, RoadGraph
from nexus.core.rules import Supply
from nexus.core.step import step
from nexus.core.world import Campaign, World, state_hash
from nexus.runtime.golden import shipped_config

POS = {
    "s0": (0, 0),
    "a": (8000, 0),
    "e": (12000, 0),
    "b": (0, 10000),
    "c": (10100, 0),
    "t": (10000, 0),
}
ROADS = [Road("s0", "a", 1.0), Road("a", "t", 1.0), Road("e", "t", 1.0), Road("s0", "b", 1.0),
         Road("b", "t", 1.0)]  # fmt: skip


def toy(switch: bool = True, **supply: Any) -> World:
    base = dict(
        rear={"COALITION": "s0", "ENEMY": "s0"},
        start_owner={"s0": "COALITION", "a": "COALITION", "e": "COALITION", "b": "COALITION",
                     "c": "COALITION", "t": "NEUTRAL"},
        max_stock={n: 1000 for n in "aebct"},
        starve_floor=dict.fromkeys("aebct", 100),
        loadout_cost={"LOGI_TRUCK": 0},
        forward_deploy_min_surplus=50,
        capture_run_forward_start=switch,
        spawns={"AIR": frozenset({"s0"}), "GROUND": frozenset({"s0", "a", "e", "b", "c"})},
    )  # fmt: skip
    rules = dataclasses.replace(
        RULES,
        roads=RoadGraph(POS, ROADS),
        sanctuary="s0",
        supply=Supply(**{**base, **supply}),
        defense=None,
        landing_nodes=("s0",),
    )
    w = World.new(Campaign(CAMPAIGN_ID, 1, "cfg-toy"), rules)
    w.stock.update(dict.fromkeys("aebct", 600))
    return w


def run_of(w: World, side: Any = "COALITION", dest: str = "t") -> Run | None:
    assert w.rules is not None
    return plan_run(w, w.rules, side, dest)


def test_the_nearest_base_by_road_is_the_start_not_the_nearest_by_line() -> None:
    # c is nearest by line but unreachable; a and e tie at 2 km; b is 14 km: ties go by node id.
    assert run_of(toy()) == Run("a", 0, ["a", "t"])


def test_a_starved_base_is_skipped_by_the_surplus_margin() -> None:
    w = toy()
    w.stock["a"] = 149  # floor 100 + margin 50: one short
    assert run_of(w) == Run("e", 0, ["e", "t"])
    w.stock["a"] = 150  # exactly the margin: qualifies again
    assert run_of(w) == Run("a", 0, ["a", "t"])


def test_a_base_on_no_road_is_skipped() -> None:
    w = toy()
    for n in "aeb":
        w.stock[n] = 100  # only c has surplus, and no road leads to it
    assert run_of(w) == Run("s0", 0, ["s0", "a", "t"])  # the sanctuary, by its own road


def test_no_qualifying_base_starts_at_the_sanctuary() -> None:
    w = toy()
    for n in "aebc":
        w.stock[n] = 100
    assert run_of(w) == Run("s0", 0, ["s0", "a", "t"])


def test_a_base_the_enemy_owns_is_not_a_start() -> None:
    w = toy()
    w.owner["a"] = w.owner["e"] = "ENEMY"
    assert run_of(w) == Run("b", 0, ["b", "t"])


def test_the_switch_off_starts_every_capture_run_at_the_sanctuary() -> None:
    assert run_of(toy(switch=False)) == Run("s0", 0, ["s0", "a", "t"])


def test_the_static_keeps_its_rear_start() -> None:
    w = toy()
    w.owner["t"] = "COALITION"  # a node the Static captures; its own bases own the road
    for n in "aeb":
        w.owner[n] = "ENEMY"
        w.stock[n] = 600
    assert run_of(w, "ENEMY") == Run("s0", 0, ["s0", "a", "t"])


def test_a_follower_takes_the_leaders_start() -> None:
    w = shipped_world()
    leader = truck_for(w, 1, "cross-n")
    send(w, join(2, "LOGI", target={"follow_entity_id": leader.id}))
    (follower,) = (e for e in w.entities() if e.commander_id == cid(2))
    assert (leader.last_node, follower.last_node) == ("fob-n-w", "fob-n-w")
    assert follower.cargo == 0


def test_the_shipped_config_starts_forward_and_the_switch_reaches_it() -> None:
    for key, start in ((True, "fob-n-w"), (False, "haven")):
        w = shipped_world(dataclasses.replace(RULES, supply=dataclasses.replace(
            RULES.supply, capture_run_forward_start=key)))  # fmt: skip
        assert truck_for(w, 1, "cross-n").last_node == start
    flipped = shipped_config({"logistics.capture_run_forward_start": False}).rules
    assert shipped_config({}).rules.supply.capture_run_forward_start is True
    assert flipped.supply.capture_run_forward_start is False


def test_no_stock_moves_and_no_supply_event_on_a_forward_start() -> None:
    w = shipped_world()
    stock, pool = dict(w.stock), dict(w.pool)
    truck_for(w, 1, "cross-n")
    assert (w.stock, w.pool) == (stock, pool)


@pytest.mark.parametrize("switch", [True, False])
def test_a_capture_run_is_deterministic(switch: bool) -> None:
    def scenario() -> str:
        w = shipped_world(dataclasses.replace(RULES, supply=dataclasses.replace(
            RULES.supply, capture_run_forward_start=switch)))  # fmt: skip
        truck_for(w, 1, "cross-n")
        for _ in range(100):
            step(w, [])
        return state_hash(w)

    assert scenario() == scenario()
