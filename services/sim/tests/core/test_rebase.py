"""NX-158: the REBASE handler (Q-SIM-90; GAMEPLAY §1b, §3; CONTRACTS §5.2).

Runs on the shipped strait-1 config with the board on: haven (20 km, 120 km) and west-airbase
(90 km, 120 km) are the coalition's landing bases, fob-n-w (130 km, 60 km) its FOB, east-airbase
the Static's. A rebased unit gets the HOLD order, so the board leaves it alone until a next order.
"""

import copy
import os
import subprocess
import sys

import pytest
from test_tasking import EVERY, RULES, new_world, post, put

from nexus.contracts.gen.commands.rebase import RebaseCommand
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_released import JobReleased
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.core.step import step
from nexus.core.tasking import claim
from nexus.core.world import Entity, Vec2, World, load, save, state_hash

WEST = "west-airbase"


def rebase(unit: Entity, node: str) -> RebaseCommand:
    return RebaseCommand.model_validate(
        {
            "kind": "REBASE",
            "source": "CHAT",
            "issuer": {"commander_id": unit.commander_id},
            "target_tick": 1,
            "arrival_seq": 1,
            "correlation_id": "r1",
            "node_id": node,
        }
    )


def send(w: World, unit: Entity, node: str) -> list[Event]:
    cmd = rebase(unit, node).model_copy(update={"target_tick": w.campaign.tick + 1})
    return step(w, [cmd])


def run(w: World, ticks: int) -> list[Event]:
    return [ev for _ in range(ticks) for ev in step(w, [])]


def drive(w: World, unit: Entity, limit: int = 40_000) -> list[Event]:
    """Step until `unit` has no path left; the events of those ticks."""
    events: list[Event] = []
    for _ in range(limit):
        if not unit.path:
            return events
        events += step(w, [])
    raise AssertionError("the unit never arrived")


def reasons(events: list[Event]) -> list[str]:
    return [e.reason for e in events if isinstance(e, CommandRejected)]


def ground(w: World, node: str) -> Entity:
    e = w.spawn("GARRISON_INFANTRY", "COALITION", "COMMANDER", Vec2(*RULES.roads.pos[node]),
                commander_id=f"0192f0c1-7a2b-7c3d-8e4f-{w._next_entity_id:012d}")  # fmt: skip
    e.last_node = node
    return e


# --- rejections ---------------------------------------------------------------------------------


def test_no_active_unit() -> None:
    w = new_world()
    ghost = put(w, "STRIKE_FIGHTER", "haven")
    w.remove(ghost.id)
    assert reasons(send(w, ghost, WEST)) == ["NO_ACTIVE_UNIT"]


def test_a_disabled_unit_is_not_active() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "haven")
    jet.damage_state = "DISABLED"
    assert reasons(send(w, jet, WEST)) == ["NO_ACTIVE_UNIT"]


@pytest.mark.parametrize(
    ("kind", "node", "reason"),
    [
        ("STRIKE_FIGHTER", "no-such-node", "NODE_UNKNOWN"),
        ("STRIKE_FIGHTER", "east-airbase", "NODE_NOT_FRIENDLY"),
        ("STRIKE_FIGHTER", "bridge-n", "NODE_NOT_FRIENDLY"),  # neutral
        ("STRIKE_FIGHTER", "fob-n-w", "NODE_INVALID_FOR_UNIT"),  # an aircraft needs a landing base
        ("LOGI_TRUCK", "cross-n", "NODE_NOT_FRIENDLY"),
    ],
)
def test_rejections(kind: str, node: str, reason: str) -> None:
    w = new_world()
    unit = put(w, kind, "haven" if kind == "STRIKE_FIGHTER" else WEST)  # type: ignore[arg-type]
    assert reasons(send(w, unit, node)) == [reason]
    assert (unit.order, unit.path) == (None, [])


def test_a_ground_unit_cannot_rebase_to_a_bridge() -> None:
    w = new_world()
    w.owner["bridge-n"] = "COALITION"
    unit = put(w, "LOGI_TRUCK", WEST)
    assert reasons(send(w, unit, "bridge-n")) == ["NODE_INVALID_FOR_UNIT"]


def test_out_of_reach_for_fuel_and_the_edge_of_it() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "haven")
    jet.fuel = 1.0
    assert reasons(send(w, jet, WEST)) == ["OUT_OF_REACH"]
    assert (jet.order, jet.path) == (None, [])
    # 70 km at the jet's speed plus the bingo reserve: enough fuel is accepted.
    jet.fuel = RULES.fuel_s["STRIKE_FIGHTER"]
    assert reasons(send(w, jet, WEST)) == [] and jet.path == [WEST]


# --- movement, arrival, restock -----------------------------------------------------------------


def test_an_aircraft_lands_refuels_and_rearms_from_the_new_base_with_exact_stock() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "haven")
    full_fuel, full_ammo = jet.fuel, list(jet.ammo)
    jet.fuel, jet.ammo = 2000.0, [0] * len(jet.ammo)
    w.stock[WEST] = 1000
    events = send(w, jet, WEST)
    assert (jet.order, jet.path, jet.job_id) == ("HOLD", [WEST], None)
    events += run(w, 4000)
    assert (jet.state, jet.last_node, jet.path, jet.order) == ("LANDED", WEST, [], "HOLD")
    assert jet.fuel == full_fuel and jet.ammo == full_ammo
    # the stop's one report equals the debit from this base's stock; haven is infinite
    rearm = [e.amount for e in events if isinstance(e, SupplyConsumed) and e.cause == "REARM"]
    assert len(rearm) == 1 and rearm[0] > 0 and w.stock[WEST] == 1000 - rearm[0]


def test_a_ground_unit_rebases_by_road_and_holds() -> None:
    w = new_world()
    unit = ground(w, WEST)
    send(w, unit, "fob-n-w")
    assert unit.path == ["fob-n-w"] and unit.order == "HOLD"
    drive(w, unit)
    assert (unit.last_node, unit.path) == ("fob-n-w", [])
    assert unit.pos == Vec2(*RULES.roads.pos["fob-n-w"])
    assert unit.order == "HOLD"


def test_a_ground_unit_already_there_just_holds() -> None:
    w = new_world()
    unit = ground(w, WEST)
    assert reasons(send(w, unit, WEST)) == [] and (unit.path, unit.order) == ([], "HOLD")


def test_a_truck_keeps_its_cargo_on_the_way_and_stock_is_conserved() -> None:
    w = new_world()
    truck = put(w, "LOGI_TRUCK", WEST, cargo=100)
    total = sum(w.stock.values()) + 100
    events = send(w, truck, "fob-n-w")
    events += run(w, 50)
    assert truck.cargo == 100 and truck.path  # still driving, nothing dropped
    events += drive(w, truck)
    events += run(w, 400)  # the ordinary unloading stop at the new base
    assert truck.last_node == "fob-n-w" and truck.order == "HOLD"
    gone = sum(e.amount for e in events if isinstance(e, SupplyConsumed))  # garrison spawns
    assert sum(w.stock.values()) + (truck.cargo or 0) + gone == total


# --- orders -------------------------------------------------------------------------------------


def test_a_rebase_releases_a_held_job_and_ends_a_follow() -> None:
    w = new_world()
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d")
    jet = put(w, "STRIKE_FIGHTER", "haven")
    claim(w, jet, job, [])
    events = send(w, jet, WEST)
    assert [(e.job_id, e.entity_id) for e in events if isinstance(e, JobReleased)] == [
        (job.id, jet.id)
    ]
    assert jet.job_id is None and job.claims == {}
    leader = put(w, "STRIKE_FIGHTER", "haven")
    tail = put(w, "RECON_UAV", "haven")
    tail.order, tail.follow_id = "FOLLOW", leader.id
    send(w, tail, WEST)
    assert tail.follow_id is None and tail.order == "HOLD"
    assert load(save(w)).get(tail.id).order == "HOLD"  # a consistent world still restores


def test_after_arrival_the_unit_takes_no_board_job_until_its_next_order() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "haven")
    send(w, jet, WEST)
    run(w, 4000)
    assert jet.state == "LANDED" and jet.last_node == WEST
    post(w, "COALITION", "DEFEND", "fob-n-w", "d")
    run(w, 3 * EVERY)
    assert jet.job_id is None and jet.path == []
    jet.order = None  # a next order (`!target`, NX-192 era) ends the hold; no handler yet clears it
    run(w, 2 * EVERY)
    assert jet.job_id is not None


def test_a_paused_campaign_rejects_a_rebase_and_changes_nothing() -> None:
    w = new_world()
    unit = ground(w, WEST)
    w.campaign.clock_paused = True
    unit_before, stock_before = copy.deepcopy(unit), dict(w.stock)
    assert reasons(send(w, unit, "fob-n-w")) == ["CAMPAIGN_PAUSED"]
    assert unit == unit_before and w.stock == stock_before


def test_a_unit_stopped_on_the_road_is_routed_back_to_the_node_it_left() -> None:
    w = new_world()
    unit = ground(w, WEST)
    unit.path = ["fob-n-w"]
    run(w, 300)
    unit.path = []  # stopped between nodes
    assert unit.pos != Vec2(*RULES.roads.pos[WEST])
    assert reasons(send(w, unit, WEST)) == [] and unit.path
    drive(w, unit)
    assert (unit.last_node, unit.pos) == (WEST, Vec2(*RULES.roads.pos[WEST]))
    assert unit.order == "HOLD"


# --- snapshot and determinism ---------------------------------------------------------------------


def scenario() -> World:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "haven")
    jet.fuel = 2500.0
    unit = ground(w, WEST)
    send(w, unit, "fob-n-w")
    step(w, [rebase(jet, WEST).model_copy(update={"target_tick": w.campaign.tick + 1})])
    run(w, 400)
    return w


def test_live_and_restored_worlds_agree_mid_rebase() -> None:
    live = scenario()
    assert any(e.path for e in live.entities())
    again = load(save(live))
    again.rules = live.rules
    assert state_hash(again) == state_hash(live)
    run(live, 300)
    run(again, 300)
    assert state_hash(again) == state_hash(live)


def test_runs_hash_alike_across_hash_seeds() -> None:
    assert state_hash(scenario()) == state_hash(scenario())
    child = (
        "import sys; sys.path.insert(0, sys.argv[1]); from test_rebase import scenario\n"
        "from nexus.core.world import state_hash; print(state_hash(scenario()))"
    )

    def hashed(seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        argv = [sys.executable, "-c", child, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert hashed("1") == hashed("2") == state_hash(scenario())
