"""NX-407: a supply run enters no node the other side holds (Q-SIM-122; neutral ground is
passable), so a cut bridge holds the
resupply behind its repair (TB-8, Q-SIM-117) instead of sending trucks through the Static's
airbase; a unit going home or escaping still drives through enemy ground when that is its only road.

strait-1: bridge-n carries fob-n-w ~ cross-n, bridge-s fob-s-w ~ cross-s; with bridge-n down the
only road west of cross-n runs cross-n -> east-airbase (ENEMY) -> cross-s -> fob-s-w.
"""

from itertools import pairwise

import test_tasking as tt
from hypothesis import given, settings
from hypothesis import strategies as st
from test_bridge_repair import _jobs
from test_bridges import NORTH, SOUTH, cut
from test_follow import follow_join
from test_join import cid

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import bridges, capture, logistics, tasking
from nexus.core.bridges import blocked
from nexus.core.logistics import go_home, plan_run, supply_route
from nexus.core.roads import shortest_path
from nexus.core.step import step
from nexus.core.world import Entity, Vec2, World, state_hash

RULES = tt.RULES
TRUCK: UnitKind = "LOGI_TRUCK"
FOE = "east-airbase"


def _held_cross_n(w: World) -> None:
    """cross-n is the coalition's and empty; cross-s stays NEUTRAL, east-airbase the Static's."""
    w.owner["cross-n"], w.stock["cross-n"] = "COALITION", 0


def _interior(route: list[str]) -> list[str]:
    return route[1:-1]


def test_after_the_cut_a_truck_for_cross_n_never_routes_through_the_airbase() -> None:
    w = tt.new_world()
    _held_cross_n(w)
    cut(w, NORTH)
    detour = shortest_path(RULES.roads, "cross-n", "fob-s-w", blocked=blocked(w))
    assert detour is not None and FOE in detour  # the road the old planner took
    assert plan_run(w, RULES, "COALITION", "cross-n") is None
    truck = tt.put(w, TRUCK, "fob-n-w")
    tt.board_pass(w)
    (repair,) = [j for j in _jobs(w, "REPAIR_BRIDGE") if j.node == NORTH]
    (resupply,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    assert resupply.depends_on == repair.id and not resupply.claims  # TB-8: waits on the repair
    assert FOE not in truck.path
    w.bridge_hp[NORTH], w.bridge_down = 300, set()  # repaired: the run goes over bridge-n
    run = plan_run(w, RULES, "COALITION", "cross-n")
    assert run is not None and FOE not in run.route and run.route[-2:] == ["fob-n-w", "cross-n"]


def test_a_claimed_truck_never_reroutes_through_the_airbase_when_the_bridge_falls() -> None:
    w = tt.new_world()
    _held_cross_n(w)
    tt.board_pass(w)
    (job,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    hauler = tt.put(w, TRUCK, "fob-n-w", cargo=100)
    tasking.claim(w, hauler, job, [])
    hauler.pos, hauler.path = Vec2(150_000.0, 60_000.0), ["cross-n"]  # short of the cut
    joined = tt.put(w, TRUCK, "fob-n-w", cargo=100)  # a `!join logi cross-n`: a GOTO, no job
    joined.order, joined.order_node = "GOTO", "cross-n"
    joined.pos, joined.path = Vec2(150_000.0, 60_000.0), ["cross-n"]
    bridges.damage(w, RULES, NORTH, 300, 1, [])
    assert hauler.path == ["fob-n-w"] and joined.path == ["fob-n-w"]  # back to its bank, no detour


def test_a_supply_route_allows_its_ends_but_not_the_enemy_nodes_between() -> None:
    """The start and the destination are exempt; enemy-held nodes between are not."""
    w = tt.new_world()
    assert supply_route(w, RULES, "COALITION", "cross-n", "fob-n-w") == ["cross-n", "fob-n-w"]
    w.owner["cross-n"] = "ENEMY"
    assert supply_route(w, RULES, "COALITION", "fob-n-e", "fob-n-w") is None  # past cross-n
    w.owner["fob-n-w"] = "ENEMY"  # a destination lost on the way: still reached, then diverted
    assert supply_route(w, RULES, "COALITION", "west-airbase", "fob-n-w") == [
        "west-airbase",
        "fob-n-w",
    ]


def test_with_no_cut_every_resupply_route_is_unchanged() -> None:
    w = tt.new_world()
    for dest in sorted(RULES.supply.max_stock):
        for side in ("COALITION", "ENEMY"):
            run = plan_run(w, RULES, side, dest)
            if run is not None:
                assert run.route == shortest_path(
                    RULES.roads, run.source, dest, blocked=frozenset()
                ), (side, dest)


def test_the_static_s_supply_runs_avoid_coalition_held_nodes_too() -> None:
    w = tt.new_world()
    w.owner["cross-n"], w.stock["cross-n"] = "ENEMY", 0
    w.owner[FOE] = w.owner["fob-n-e"] = "COALITION"  # every road to cross-n passes one of these
    assert shortest_path(RULES.roads, "fob-s-e", "cross-n", blocked=frozenset()) is not None
    assert plan_run(w, RULES, "ENEMY", "cross-n") is None


def test_a_supply_run_passes_through_a_neutral_crossing() -> None:
    """fob-n-e taken and empty, no cut: its run from fob-n-w crosses neutral cross-n (Q-SIM-122:
    only enemy-held nodes are avoided; avoiding neutral ones would leave it unsuppliable)."""
    w = tt.new_world()
    w.owner["fob-n-e"], w.stock["fob-n-e"] = "COALITION", 0
    assert w.owner["cross-n"] == "NEUTRAL"
    run = plan_run(w, RULES, "COALITION", "fob-n-e")
    assert run is not None and run.route == ["fob-n-w", "cross-n", "fob-n-e"]
    assert supply_route(w, RULES, "COALITION", "fob-n-w", "fob-n-e") == run.route


def _ground_unit_at_fob_n_e(w: World) -> Entity:
    """A coalition truck at fob-n-e (the Static's), bridge-n down: its only road home runs through
    the Static's airbase."""
    cut(w, NORTH)
    return tt.put(w, TRUCK, "fob-n-e", cargo=10)


def test_go_home_still_drives_through_enemy_ground_when_it_is_the_only_road() -> None:
    w = tt.new_world()
    e = _ground_unit_at_fob_n_e(w)
    e.order = "GOTO"
    go_home(w, RULES, e)
    path = [str(p) for p in e.path]
    assert FOE in path and path[-1] == "fob-s-w"


def test_a_capture_escape_still_drives_through_enemy_ground_when_it_is_the_only_road() -> None:
    w = tt.new_world()
    e = _ground_unit_at_fob_n_e(w)
    assert capture._escape_ground(w, RULES, e, "fob-n-e", [])
    path = [str(p) for p in e.path]
    assert FOE in path and path[-1] == "fob-s-w"


@settings(max_examples=60, deadline=None)
@given(
    owners=st.lists(st.sampled_from(["COALITION", "ENEMY", "NEUTRAL"]), min_size=4, max_size=4),
    down=st.sets(st.sampled_from([NORTH, SOUTH])),
)
def test_a_supply_run_never_enters_an_enemy_held_node(owners: list[str], down: set[str]) -> None:
    w = tt.new_world()
    for node, owner in zip(["cross-n", "cross-s", FOE, "fob-n-e"], owners, strict=True):
        w.owner[node] = owner  # type: ignore[assignment]
    cut(w, *sorted(down))
    sides: tuple[tuple[Side, Side], ...] = (("COALITION", "ENEMY"), ("ENEMY", "COALITION"))
    for side, other in sides:
        for dest in sorted(RULES.supply.max_stock):
            run = plan_run(w, RULES, side, dest)
            if run is None or w.owner.get(dest) != side or not RULES.supply.max_stock[dest]:
                continue  # a capture run may cross any node
            assert all(w.owner.get(n) != other for n in _interior(run.route)), (side, dest)
            assert not {RULES.roads.edge(a, b).bridge for a, b in pairwise(run.route)} & down


def test_the_cut_off_resupply_world_is_deterministic() -> None:
    def play() -> tuple[str, list[Event]]:
        w = tt.new_world(seed=7)
        _held_cross_n(w)
        cut(w, NORTH)
        tt.put(w, TRUCK, "fob-n-w")
        tt.put(w, TRUCK, "west-airbase")
        events: list[Event] = []
        for _ in range(4 * tt.EVERY):
            events += step(w, [])
        return state_hash(w), events

    assert play() == play()


def test_neither_resupply_leg_of_a_board_truck_crosses_enemy_ground() -> None:
    """A truck at neutral cross-s with bridge-s down reaches fob-n-w (and its source, west-airbase)
    only past east-airbase and cross-n: infeasible loaded (the run) and empty (the pickup leg)."""
    w = tt.new_world()
    cut(w, SOUTH)
    job = tt.post(w, "COALITION", "RESUPPLY", "fob-n-w", "supply")
    loaded, empty = tt.put(w, TRUCK, "cross-s", cargo=10), tt.put(w, TRUCK, "cross-s")
    assert shortest_path(RULES.roads, "cross-s", "fob-n-w", blocked=blocked(w)) is not None
    assert tasking._feasible(w, RULES, {}, loaded, job) == "no"
    assert tasking._feasible(w, RULES, {}, empty, job) == "no"
    w.owner[FOE] = "COALITION"  # the airbase taken: both legs open over the neutral crossings
    assert tasking._feasible(w, RULES, {}, loaded, job) == "ok"
    assert tasking._feasible(w, RULES, {}, empty, job) == "ok"


def test_a_resupply_reached_only_through_enemy_ground_waits_on_no_repair() -> None:
    """fob-n-e held, cross-n and static-hq the Static's: even repaired, no held road reaches it, so
    the job depends on no repair and no truck takes it (it expires as an unserved job does)."""
    w = tt.new_world()
    w.owner["fob-n-e"], w.stock["fob-n-e"], w.owner["cross-n"] = "COALITION", 0, "ENEMY"
    cut(w, NORTH)
    tt.put(w, TRUCK, "fob-n-w")
    tt.board_pass(w)
    assert [j.node for j in _jobs(w, "REPAIR_BRIDGE")] == [NORTH]
    (resupply,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "fob-n-e"]
    assert resupply.depends_on is None and not resupply.claims


def _goto_truck(w: World, frm: str, to: str, x: float, y: float, cargo: int | None) -> Entity:
    """A truck on a `!join logi <to>` GOTO order, on the road `frm` -> `to` at (x, y)."""
    e = tt.put(w, TRUCK, frm, cargo=cargo)
    e.order, e.order_node, e.pos, e.path = "GOTO", to, Vec2(x, y), [to]
    return e


def _events_of(events: list[Event], unit_id: int) -> list[Event]:
    return [ev for ev in events if unit_id in ev.model_dump().values()]


def _held_at_cross_s() -> tuple[World, Entity]:
    """QA's repro (Q-SIM-126): a loaded GOTO truck on cross-s -> fob-s-w short of the cut, then
    bridge-s falls; it turns back to neutral cross-s, whose only other roads run to the Static's
    fob-s-e and east-airbase."""
    w = tt.new_world()
    truck = _goto_truck(w, "cross-s", "fob-s-w", 220_000.0, 180_000.0, cargo=100)
    bridges.damage(w, RULES, SOUTH, 300, 1, [])
    assert truck.path == ["cross-s"]
    for _ in range(1000):
        step(w, [])
        if not truck.path:
            break
    assert truck.last_node == "cross-s" and truck.pos == Vec2(*RULES.roads.pos["cross-s"])
    return w, truck


def test_a_supply_truck_on_neutral_ground_never_diverts_through_enemy_ground() -> None:
    """It holds with its cargo, emitting nothing, through logistics ticks and board passes (the
    `logistics` slot and the board, without capture: in play its own bar takes cross-s)."""
    w, truck = _held_at_cross_s()
    events: list[Event] = []
    for _ in range(3):
        for _ in range(5):
            logistics.logistics(w, events)
        events += tt.board_pass(w)
        assert truck.path == [] and truck.cargo == 100 and truck.order == "GOTO"
    assert truck.last_node == "cross-s" and not _events_of(events, truck.id)


def test_in_play_the_held_truck_takes_cross_s_and_unloads_there() -> None:
    w, truck = _held_at_cross_s()
    for _ in range(2 * tt.EVERY):
        step(w, [])
        assert FOE not in truck.path
    assert w.owner["cross-s"] == "COALITION" and truck.last_node == "cross-s"
    assert w.stock["cross-s"] > 0 and (truck.cargo or 0) < 100


def test_a_holding_supply_truck_leaves_once_the_road_reopens() -> None:
    w, truck = _held_at_cross_s()
    step(w, [])
    assert truck.path == []
    w.bridge_hp[SOUTH], w.bridge_down = 300, set()  # repaired
    step(w, [])
    assert truck.path == ["cross-s", "fob-s-w"] and truck.cargo == 100


def test_a_truck_on_a_node_the_other_side_took_still_flees_by_any_road() -> None:
    """Escape case (Q-SIM-126): a loaded GOTO truck standing on fob-n-e, the Static's, with
    bridge-n down: its only road to a friendly base runs through east-airbase."""
    w = tt.new_world()
    truck = _ground_unit_at_fob_n_e(w)
    truck.order, truck.order_node = "GOTO", "fob-n-e"
    logistics.logistics(w, [])
    assert FOE in truck.path and truck.path[-1] == "fob-s-w"


def test_a_follower_truck_keeps_the_old_source_pick_where_a_supply_run_is_refused() -> None:
    """GAMEPLAY §1b Q-GP-31: a `!join logi <callsign>` truck loads at the source `plan_run` picks
    for its leader's destination by any road; here the supply run itself is refused."""
    w = tt.new_world()
    _held_cross_n(w)
    cut(w, NORTH)
    assert plan_run(w, RULES, "COALITION", "cross-n") is None  # every road passes the airbase
    lead = tt.put(w, TRUCK, "fob-s-w", cargo=100)
    lead.path = ["cross-s", FOE, "cross-n"]
    events = step(w, [follow_join(1, "LOGI", lead.id)])
    assert not [ev for ev in events if ev.kind == "CommandRejected"]
    (col,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert col.follow_id == lead.id and col.cargo and col.last_node == "fob-s-w"


def test_dispatch_sends_an_empty_truck_to_its_source_around_enemy_ground() -> None:
    """The pickup leg (`tasking._dispatch`): the empty truck at cross-n loads at cross-s, the only
    source with surplus for fob-n-e; the short road (200 km) passes east-airbase, the Static's, so
    it takes the long one round the west (344 km)."""
    w = tt.new_world()
    w.owner["fob-n-e"], w.stock["fob-n-e"] = "COALITION", 0
    w.owner["cross-n"] = w.owner["cross-s"] = "COALITION"
    for n in ("west-airbase", "fob-n-w", "fob-s-w", "cross-n"):
        w.stock[n] = RULES.supply.starve_floor[n]
    w.stock["cross-s"] = RULES.supply.starve_floor["cross-s"] + 200
    job = tt.post(w, "COALITION", "RESUPPLY", "fob-n-e", "supply")
    truck = tt.put(w, TRUCK, "cross-n")
    assert shortest_path(RULES.roads, "cross-n", "cross-s", blocked=frozenset()) == [
        "cross-n", FOE, "cross-s",
    ]  # fmt: skip
    tasking._dispatch(w, RULES, {}, truck, job)
    assert truck.pickup == "cross-s"
    assert truck.path == ["cross-n", "fob-n-w", "west-airbase", "fob-s-w", "cross-s"]


def test_an_empty_capture_run_truck_reroutes_by_any_road() -> None:
    """An empty GOTO truck (a capture run to cross-n) turned back by the cut takes the only road
    left, through east-airbase: only a supply run avoids enemy ground."""
    w = tt.new_world()
    truck = _goto_truck(w, "fob-n-w", "cross-n", 150_000.0, 60_000.0, cargo=None)
    bridges.damage(w, RULES, NORTH, 300, 1, [])
    assert truck.path[0] == "fob-n-w" and FOE in truck.path and truck.path[-1] == "cross-n"


def test_a_rerouted_supply_run_still_reaches_its_lost_destination() -> None:
    """The destination is exempt from the avoid (`reroute`): cross-n lost on the way, east-airbase
    neutral, bridge-n falls: the loaded GOTO truck drives round by the south to cross-n."""
    w = tt.new_world()
    w.owner["cross-n"], w.owner[FOE] = "ENEMY", "NEUTRAL"
    truck = _goto_truck(w, "fob-n-w", "cross-n", 150_000.0, 60_000.0, cargo=100)
    bridges.damage(w, RULES, NORTH, 300, 1, [])
    assert truck.path == ["fob-n-w", "west-airbase", "fob-s-w", "cross-s", FOE, "cross-n"]


def test_a_loaded_truck_going_home_reroutes_by_any_road() -> None:
    """A loaded truck whose GOTO named fob-n-e but whose path now runs home to west-airbase is no
    supply run (its path does not end at `order_node`): turned back to cross-n by the cut, it
    takes the only road left, through east-airbase."""
    w = tt.new_world()
    truck = _goto_truck(w, "cross-n", "fob-n-e", 220_000.0, 60_000.0, cargo=100)
    truck.path = ["fob-n-w", "west-airbase"]
    bridges.damage(w, RULES, NORTH, 300, 1, [])
    assert truck.path[0] == "cross-n" and FOE in truck.path and truck.path[-1] == "west-airbase"


def test_a_held_claimant_whose_lease_lapses_still_never_crosses_enemy_ground() -> None:
    """QA round 2: a RESUPPLY claimant holding at neutral cross-s loses its claim after the lease;
    jobless and loaded, it must keep holding, not divert through east-airbase (Q-SIM-126)."""
    w = tt.new_world()
    w.stock["fob-s-w"] = 0
    tt.board_pass(w)
    (job,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "fob-s-w"]
    truck = tt.put(w, "LOGI_TRUCK", "cross-s", cargo=100)
    tasking.claim(w, truck, job, [])
    truck.pos, truck.path = Vec2(220_000.0, 180_000.0), ["fob-s-w"]
    rules = w.rules
    assert rules is not None
    bridges.damage(w, rules, SOUTH, 300, 1, [])
    tt.board_pass(w)
    repair = _jobs(w, "REPAIR_BRIDGE")
    for r in repair:  # fill the repair slots so the board has no other job for the truck
        for _ in range(r.slots - len(r.claims)):
            blocker = tt.put(w, "LOGI_TRUCK", "haven")
            tasking.claim(w, blocker, r, [])
            blocker.path = []
    released = False
    for _ in range(3_000):
        w.capture.pop("cross-s", None)  # a contested node: it never falls to the truck
        w.owner["cross-s"] = "NEUTRAL"
        for r in repair:
            for c in r.claims.values():
                c.at = tasking._now(w)
        step(w, [])
        assert "east-airbase" not in truck.path
        released = released or truck.job_id is None
    assert released and truck.cargo == 100  # the lease lapsed and it still held with its cargo
