"""NX-413, follow-ups from NX-407 QA (Q-SIM-122, Q-SIM-125).

Part 1: a supply run or a repair crew whose remaining road enters a node that has just turned
enemy replans (`bridges.reroute` with `taken`, called by the capture flip), so a truck never drives
into a node that turned enemy on its way; a supply run's destination is exempt, a crew's bank is
not. Part 3: the Static's Pattern of Life convoy is not paid for when no truck has a route to its
base. Part 4: `enemy_held` is found once per pass (`tasking.Routes`).

strait-1 (see test_supply_routes): fob-n-w ~bridge-n~ cross-n, cross-n - east-airbase - cross-s,
cross-n - fob-n-e - static-hq; a truck at (150 000, 60 000) is on fob-n-w -> cross-n, short of
bridge-n.
"""

import dataclasses

import test_tasking as tt
from test_bridges import NORTH, SOUTH, cut
from test_economy_rules import thin
from test_staging import debits

from nexus.contracts.gen.common.enums import NodeOwner, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import bridges, tasking
from nexus.core.fog import side_view
from nexus.core.launch import _convoys, _Purse
from nexus.core.roads import Road, RoadGraph
from nexus.core.rules import CAPTURE_FULL
from nexus.core.step import step
from nexus.core.world import CaptureBar, Entity, Vec2, World, state_hash

RULES = tt.RULES
TRUCK: UnitKind = "LOGI_TRUCK"
FOE = "east-airbase"
SHORT_OF_CROSS_N = Vec2(150_000.0, 60_000.0)  # on fob-n-w -> cross-n, west of bridge-n
NEAR_CROSS_N = Vec2(225_000.0, 60_000.0)  # 5 km short of cross-n, east of bridge-n
ARRIVE_TICKS = 1000  # a truck covers 15 m a tick here: the 5 km to cross-n take ~333


def _run_to(w: World, dest: str, path: list[str]) -> Entity:
    """A loaded coalition truck on a RESUPPLY job to `dest`, left fob-n-w, short of bridge-n."""
    job = tt.post(w, "COALITION", "RESUPPLY", dest, f"supply-{dest}")
    truck = tt.put(w, TRUCK, "fob-n-w", cargo=100)
    tasking.claim(w, truck, job, [])
    truck.pos, truck.path = SHORT_OF_CROSS_N, list(path)
    return truck


def _turn(w: World, node: str, owner: NodeOwner) -> None:
    w.owner[node] = owner
    bridges.reroute(w, RULES, taken=node)


def _held_fob_n_e(w: World) -> None:
    w.owner["fob-n-e"], w.stock["fob-n-e"] = "COALITION", 0


def test_a_truck_whose_next_node_turns_enemy_turns_back() -> None:
    w = tt.new_world()
    _held_fob_n_e(w)
    truck = _run_to(w, "fob-n-e", ["cross-n", "fob-n-e"])
    _turn(w, "cross-n", "ENEMY")
    assert truck.path == ["fob-n-w"]  # no road round cross-n: back to the node it came from


def test_a_truck_whose_later_node_turns_enemy_stops_short_of_it() -> None:
    """bridge-s down, the airbase neutral: the run to cross-s goes cross-n -> airbase -> cross-s;
    the airbase taken, it keeps its leg to cross-n and stops there (no other road on)."""
    w = tt.new_world()
    cut(w, SOUTH)
    w.owner[FOE], w.owner["cross-s"], w.stock["cross-s"] = "NEUTRAL", "COALITION", 0
    truck = _run_to(w, "cross-s", ["cross-n", FOE, "cross-s"])
    _turn(w, FOE, "ENEMY")
    assert truck.path == ["cross-n"]


def test_a_supply_run_still_drives_to_a_destination_that_turned_enemy() -> None:
    """Its destination is exempt (Q-SIM-122): it arrives, then diverts (Q-SIM-126)."""
    w = tt.new_world()
    w.owner["cross-n"], w.stock["cross-n"] = "COALITION", 0
    truck = _run_to(w, "cross-n", ["cross-n"])
    _turn(w, "cross-n", "ENEMY")
    assert truck.path == ["cross-n"]


def test_a_node_turning_friendly_or_an_empty_capture_run_does_not_replan() -> None:
    w = tt.new_world()
    _held_fob_n_e(w)
    truck = _run_to(w, "fob-n-e", ["cross-n", "fob-n-e"])
    _turn(w, "cross-n", "COALITION")  # its own side's now
    assert truck.path == ["cross-n", "fob-n-e"]
    raider = tt.put(w, TRUCK, "fob-n-w")  # no job, no cargo: a capture run takes any road
    raider.pos, raider.path = SHORT_OF_CROSS_N, ["cross-n", "fob-n-e"]
    _turn(w, "cross-n", "ENEMY")
    assert raider.path == ["cross-n", "fob-n-e"]
    assert truck.path == ["fob-n-w"]


def test_a_crew_whose_bank_turns_enemy_turns_back_where_a_supply_run_drives_on() -> None:
    """Both bridges down, a crew driving from the neutral airbase to cross-n, bridge-n's east bank:
    cross-n taken, the crew turns back (its bank is not exempt, Q-SIM-125; the far bank is cut off
    too); a supply run on the same leg to cross-n drives on (its destination is exempt)."""
    w = tt.new_world()
    cut(w, NORTH, SOUTH)
    w.owner[FOE], w.owner["cross-n"], w.stock["cross-n"] = "NEUTRAL", "COALITION", 0
    on_leg = Vec2(270_000.0, 90_000.0)  # halfway along airbase -> cross-n
    crew = tt.put(w, TRUCK, FOE)
    tasking.claim(w, crew, tt.post(w, "COALITION", "REPAIR_BRIDGE", NORTH, "repair"), [])
    crew.pos, crew.path = on_leg, ["cross-n", NORTH]
    run = tt.put(w, TRUCK, FOE, cargo=100)
    tasking.claim(w, run, tt.post(w, "COALITION", "RESUPPLY", "cross-n", "supply"), [])
    run.pos, run.path = on_leg, ["cross-n"]
    _turn(w, "cross-n", "ENEMY")
    assert crew.path == [FOE]
    assert run.path == ["cross-n"]


def test_a_crew_whose_bank_turns_enemy_takes_the_other_bank_when_it_can() -> None:
    """Only bridge-n down: cross-n taken, the crew replans to fob-n-w, the west bank, by the south
    road (PR #388's nearer-bank rule, for the flip trigger too)."""
    w = tt.new_world()
    cut(w, NORTH)
    w.owner[FOE] = "NEUTRAL"
    crew = tt.put(w, TRUCK, FOE)
    tasking.claim(w, crew, tt.post(w, "COALITION", "REPAIR_BRIDGE", NORTH, "repair"), [])
    crew.pos, crew.path = Vec2(270_000.0, 90_000.0), ["cross-n", NORTH]  # airbase -> cross-n
    _turn(w, "cross-n", "ENEMY")
    assert crew.path == [FOE, "cross-s", "fob-s-w", "west-airbase", "fob-n-w", NORTH]


def test_an_empty_truck_never_drives_into_a_pickup_source_that_turned_enemy() -> None:
    """On its pickup leg the source is not exempt: the leg stops and `pickup` is cleared, so the
    claim's lease frees it for a new reload plan."""
    w = tt.new_world()
    w.owner["cross-n"], w.stock["cross-n"] = "COALITION", 500
    _held_fob_n_e(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    tasking.claim(w, truck, tt.post(w, "COALITION", "RESUPPLY", "fob-n-e", "supply"), [])
    truck.pickup, truck.pos, truck.path = "cross-n", SHORT_OF_CROSS_N, ["cross-n"]
    _turn(w, "cross-n", "ENEMY")
    assert truck.path == ["fob-n-w"] and truck.pickup is None


def test_a_cut_on_the_pickup_leg_keeps_the_pickup_when_the_source_is_friendly() -> None:
    """A cut (not a capture) on the last hop to a friendly source: the truck detours and keeps
    `pickup`, so it still loads when it gets there (CodeRabbit on #391)."""
    pos = {"s": (0, 0), "y": (500, 0), "t": (1000, 0), "e": (500, 1000)}
    roads = RoadGraph(pos, [Road("s", "t", 1.0, "y"), Road("s", "e", 1.0), Road("e", "t", 1.0)])
    rules = dataclasses.replace(RULES, roads=roads)
    w = tt.new_world()
    w.owner["e"] = w.owner["t"] = "COALITION"
    truck = tt.put(w, TRUCK, "haven")
    tasking.claim(w, truck, tt.post(w, "COALITION", "RESUPPLY", "fob-n-e", "supply"), [])
    truck.pickup, truck.pos, truck.last_node, truck.path = "t", Vec2(200.0, 0.0), "s", ["t"]
    w.bridge_down = {"y"}
    bridges.reroute(w, rules)
    assert truck.path == ["s", "e", "t"] and truck.pickup == "t"


def test_a_patrol_keeps_its_road_when_a_node_on_it_turns_enemy() -> None:
    """Only supply runs and crews replan on a flip; a coalition patrol's path is unchanged."""
    w = tt.new_world()
    patrol = tt.put(w, TRUCK, "fob-n-w")
    tasking.claim(w, patrol, tt.post(w, "COALITION", "PATROL", "fob-n-e", "patrol"), [])
    patrol.pos, patrol.path = SHORT_OF_CROSS_N, ["cross-n", "fob-n-e"]
    _turn(w, "cross-n", "ENEMY")
    assert patrol.path == ["cross-n", "fob-n-e"]


def _flip_cross_n_world(seed: int = 1) -> tuple[World, Entity]:
    """The Static's armor at cross-n one step short of the flip; a run to fob-n-e 5 km short of
    cross-n (past bridge-n, outside the capture radius), a few hundred ticks out."""
    w = tt.new_world(seed=seed)
    _held_fob_n_e(w)
    truck = _run_to(w, "fob-n-e", ["cross-n", "fob-n-e"])
    truck.pos = NEAR_CROSS_N
    tt.put(w, "ENEMY_ARMOR", "cross-n")
    w.capture["cross-n"] = CaptureBar("ENEMY", CAPTURE_FULL - 1)
    return w, truck


def test_a_truck_never_drives_into_a_node_that_turned_enemy_on_its_way() -> None:
    """The acceptance (NX-413), through the real tick: the capture flip replans the truck."""
    w, truck = _flip_cross_n_world()
    events = step(w, [])
    assert [(e.node_id, e.to) for e in events if e.kind == "NodeCaptured"] == [("cross-n", "ENEMY")]
    for _ in range(ARRIVE_TICKS):
        assert truck.last_node != "cross-n" and truck.pos != Vec2(*RULES.roads.pos["cross-n"])
        step(w, [])
    assert w.find(truck.id) is truck and truck.path == ["fob-n-w"]  # alive, heading back
    assert truck.pos.x < NEAR_CROSS_N.x


def test_the_flip_replan_is_deterministic() -> None:
    def play() -> tuple[str, list[Event]]:
        w, _ = _flip_cross_n_world(seed=7)
        events: list[Event] = []
        for _ in range(2 * tt.EVERY):
            events += step(w, [])
        return state_hash(w), events

    assert play() == play()


def test_a_convoy_with_no_road_to_its_base_is_not_paid_for() -> None:
    """fob-n-e has the largest shortfall; with cross-n and static-hq the coalition's, every road
    into it passes a coalition node, so no truck could reach it: nothing spawns, nothing is paid,
    no job is posted."""
    for cut_off in (False, True):
        w, rules = thin({"director.pol.convoy_cost": 30})
        assert rules.director is not None
        w.stock["fob-n-e"] = rules.supply.starve_floor["fob-n-e"]
        w.stock["static-hq"] = rules.supply.max_stock["static-hq"]  # no shortfall of its own
        if cut_off:
            w.owner["cross-n"] = w.owner["static-hq"] = "COALITION"
        out: list[Event] = []
        _convoys(w, rules, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], rules.director,
                 out, _Purse(0, 40))  # fmt: skip
        posted = [j.node for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"]
        assert (debits(out), posted) == (
            ([], []) if cut_off else ([("static-hq", 30)], ["fob-n-e"])
        )


def test_a_pass_finds_each_side_s_enemy_held_nodes_once() -> None:
    """Part 4: the tasking pass's `Routes` keeps `enemy_held` per side; an owner change inside a
    pass cannot happen (only capture writes `World.owner`), so a new pass sees the new owner."""
    w = tt.new_world()
    routes = tasking.Routes()
    first = tasking._held(w, RULES, routes, "COALITION")
    assert first == frozenset({FOE, "fob-n-e", "fob-s-e", "static-hq", "static-rear"})
    w.owner["cross-n"] = "ENEMY"
    assert tasking._held(w, RULES, routes, "COALITION") is first  # the pass's copy
    assert "cross-n" in tasking._held(w, RULES, tasking.Routes(), "COALITION")  # the next pass
