"""NX-373 part 2: truck field repair of bridges, `BridgeRepaired`, the REPAIR_BRIDGE job and the
TB-8 dependency of a cut-off resupply on it (STATE-MACHINES §4.3 B-2, GAMEPLAY §1b TB-8 and §5,
Q-GD-11, Q-SIM-101, Q-SIM-112's constraint).

Shipped strait-1 numbers: bridge-n (200 km, 60 km) carries fob-n-w (130 km) ~ cross-n (230 km) at
y 60 km, so its repair stop is (200 km, 60 km); `logistics.bridge_hp` 300,
`bridge_repair_time_s` 600 x `truck_bridge_repair_mult` 5 = 3000 world s for one truck, and
`sim.time_scale` 6 at 10 Hz is 0.6 world s per tick: 5000 ticks for one truck, 2500 for two.
"""

import dataclasses
from collections.abc import Callable

import pytest
import test_tasking as tt
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter
from test_bridges import MAX_HP, NORTH, SOUTH, SURE, bridges_on, cut, jet_at, ordered, strike
from test_combat import JET, RULES, TRUCK, new_world, of, put, run

from nexus.contracts.gen.commands.rebase import RebaseCommand
from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.bridge_destroyed import BridgeDestroyed
from nexus.contracts.gen.events.bridge_repaired import BridgeRepaired
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_claimed import JobClaimed
from nexus.contracts.gen.events.job_created import JobCreated
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.contracts.gen.events.job_failed import JobFailed
from nexus.contracts.gen.events.job_released import JobReleased
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core import bridges, capture, handlers, tasking
from nexus.core.logistics import go_home, nearest, plan_run
from nexus.core.roads import Road, RoadGraph
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import Entity, Job, Vec2, World, at_stop, load, save, state_hash
from nexus.runtime.golden import shipped_config

STOP = Vec2(200_000.0, 60_000.0)  # bridge-n projected on fob-n-w~cross-n
ONE_TRUCK_TICKS = 5000  # 3000 world s / 0.6 world s per tick
EVENTS: TypeAdapter[Event] = TypeAdapter(Event)


def parked(w: World, n: int = 1, side: Side = "COALITION") -> list[Entity]:
    """`n` trucks parked at bridge-n's repair stop, having come from fob-n-w."""
    out = []
    for _ in range(n):
        e = put(w, TRUCK, side, STOP.x, STOP.y)
        e.last_node = "fob-n-w"
        out.append(e)
    return out


def down(w: World, node: str = NORTH, hp: int = 0) -> None:
    cut(w, node)
    w.bridge_hp[node] = hp


# --- the rate (B-2, Q-GD-11) ------------------------------------------------------------------


def test_the_stop_is_the_bridge_projected_on_its_road() -> None:
    assert RULES.roads.stops[NORTH] == (STOP.x, STOP.y)
    assert RULES.roads.spans[NORTH] == ("cross-n", "fob-n-w")
    assert RULES.supply.bridge_repair_milli == 60  # 300 hp / 3000 s x 0.6 s, in thousandths


@pytest.mark.parametrize(("trucks", "ticks"), [(1, ONE_TRUCK_TICKS), (2, ONE_TRUCK_TICKS // 2)])
def test_trucks_repair_a_down_bridge_in_the_worked_time(trucks: int, ticks: int) -> None:
    w = new_world()
    down(w)
    first = parked(w, trucks)[0]
    events = run(w, ticks - 1)
    assert w.bridge_hp[NORTH] == MAX_HP - 1 and w.bridge_down == {NORTH}
    assert of(events, BridgeRepaired) == []
    events = run(w)
    (up,) = of(events, BridgeRepaired)
    assert (up.node_id, up.by_id) == (NORTH, first.id)
    assert EVENTS.validate_python(up.model_dump()) == up
    assert w.bridge_hp[NORTH] == MAX_HP and w.bridge_down == set() and w.bridge_repair[NORTH] == 0
    assert of(run(w, 50), BridgeRepaired) == []  # once per down cycle


def test_the_edge_returns_once_repaired() -> None:
    w = new_world()
    down(w, hp=MAX_HP - 1)
    route = nearest(w, RULES, "fob-n-w", ["cross-n"])
    assert route is not None and NORTH not in bridges_on(route[1])
    parked(w)
    run(w, 17)  # 17 x 60 = 1020 thousandths: the last hp
    assert w.bridge_down == set()
    route = nearest(w, RULES, "fob-n-w", ["cross-n"])
    assert route is not None and route[1] == ["fob-n-w", "cross-n"]


def test_a_truck_leaving_mid_repair_keeps_the_bridge_down_and_the_carry() -> None:
    w = new_world()
    down(w)
    (truck,) = parked(w)
    run(w, 1001)  # 60 060 thousandths
    assert (w.bridge_hp[NORTH], w.bridge_repair[NORTH]) == (60, 60)
    truck.path = ["fob-n-w"]
    run(w, 200)
    assert (w.bridge_hp[NORTH], w.bridge_repair[NORTH]) == (60, 60)
    assert w.bridge_down == {NORTH}


def test_a_damaged_bridge_that_never_fell_repairs_to_full_silently() -> None:
    w = new_world()
    w.bridge_hp[NORTH] = MAX_HP - 10
    parked(w)
    events = run(w, 200)
    assert w.bridge_hp[NORTH] == MAX_HP and w.bridge_repair[NORTH] == 0
    assert of(events, BridgeRepaired) == [] and w.bridge_down == set()


@pytest.mark.parametrize(
    "spoil",
    [
        lambda w, e: setattr(e, "damage_state", "DISABLED"),
        lambda w, e: setattr(w.campaign, "clock_paused", True),
        lambda w, e: setattr(e, "pos", Vec2(STOP.x - 1, STOP.y)),  # not at the stop
        lambda w, e: setattr(e, "kind", "ENEMY_ARMOR"),  # not a carrier
    ],
)
def test_no_repair_without_a_carrier_parked_at_the_stop(
    spoil: Callable[[World, Entity], object],
) -> None:
    w = new_world()
    down(w)
    (truck,) = parked(w)
    spoil(w, truck)
    run(w, 100)
    assert (w.bridge_hp[NORTH], w.bridge_repair[NORTH]) == (0, 0)


def test_either_side_repairs() -> None:
    w = new_world()
    down(w, hp=MAX_HP - 1)
    put_convoy = put(w, "ENEMY_CONVOY", "ENEMY", STOP.x, STOP.y)
    put_convoy.last_node = "cross-n"
    (up,) = of(run(w, 17), BridgeRepaired)
    assert up.by_id == put_convoy.id


def test_a_truck_drives_out_to_the_stop_and_keeps_its_bank() -> None:
    w = new_world()
    down(w, hp=MAX_HP - 1)
    truck = put(w, TRUCK, "COALITION", 199_000, 60_000)
    truck.last_node, truck.path = "fob-n-w", [NORTH]
    run(w, 200)  # 1 km at the truck's speed, then 17 ticks of repair
    assert truck.pos == STOP and truck.last_node == "fob-n-w" and truck.path == []
    assert w.bridge_down == set()


def test_a_loaded_truck_at_the_stop_unloads_nothing_into_its_bank() -> None:
    w = new_world()
    down(w)
    (truck,) = parked(w)
    truck.cargo = 50
    stock = dict(w.stock)
    run(w, 100)
    assert truck.cargo == 50 and w.stock == stock


# --- B-2 property -----------------------------------------------------------------------------

OPS = st.lists(
    st.one_of(
        st.tuples(st.just("hit"), st.integers(0, 400)),
        st.tuples(st.just("park"), st.integers(0, 3)),
        st.tuples(st.just("tick"), st.integers(1, 300)),
    ),
    max_size=25,
)


@settings(max_examples=60, deadline=None)
@given(OPS)
def test_repair_keeps_hp_within_zero_and_max_and_no_carry_at_full(
    ops: list[tuple[str, int]],
) -> None:
    w = new_world()
    out: list[Event] = []
    for op, n in ops:
        if op == "hit":
            bridges.damage(w, RULES, NORTH, n, 1, out)  # a fall destroys the parked trucks
        elif op == "park":
            for e in [e for e in w.entities() if e.kind == TRUCK]:
                w.remove(e.id)
            parked(w, n)
        else:
            for _ in range(n):
                bridges.repair(w, out)
        hp = w.bridge_hp[NORTH]
        assert 0 <= hp <= MAX_HP and 0 <= w.bridge_repair[NORTH] < 1000
        assert hp < MAX_HP or w.bridge_repair[NORTH] == 0
        assert (hp == 0) <= (NORTH in w.bridge_down)
        bridges.validate(w, RULES)
    downs, ups = of(out, BridgeDestroyed), of(out, BridgeRepaired)
    assert len(ups) in (len(downs), len(downs) - 1)  # each repair closes the fall before it


# --- determinism and snapshots ----------------------------------------------------------------


def test_repair_is_deterministic() -> None:
    def once() -> tuple[str, list[str]]:
        w = new_world()
        down(w, hp=250)
        truck = put(w, TRUCK, "COALITION", 198_000, 60_000)
        truck.last_node, truck.path = "fob-n-w", [NORTH]
        parked(w)
        events = run(w, 1200)
        return state_hash(w), [e.model_dump_json() for e in events]

    a, b = once(), once()
    assert a == b and sum("BridgeRepaired" in e for e in a[1]) == 1


def test_a_repair_carry_survives_a_snapshot() -> None:
    w = new_world()
    down(w)
    parked(w, 2)
    run(w, 7)  # 840 thousandths: no whole hp yet
    assert (w.bridge_hp[NORTH], w.bridge_repair[NORTH]) == (0, 840)
    again = load(save(w))
    bridges.validate(again, RULES)
    assert again.bridge_repair == w.bridge_repair and state_hash(again) == state_hash(w)
    again.rules = RULES
    assert [e.model_dump_json() for e in run(again, 3000)] == [
        e.model_dump_json() for e in run(w, 3000)
    ]
    assert state_hash(again) == state_hash(w)


@pytest.mark.parametrize(
    "bad",
    [
        lambda w: w.bridge_repair.__setitem__(NORTH, 1000),  # a whole hp in the carry
        lambda w: w.bridge_repair.__setitem__(SOUTH, 5),  # a carry at full hp
        lambda w: w.bridge_repair.pop(SOUTH),  # a bridge missing
    ],
)
def test_restore_refuses_a_bad_repair_carry(bad: Callable[[World], object]) -> None:
    w = new_world()
    down(w, hp=10)
    bad(w)
    again = load(save(w))
    with pytest.raises(ValueError, match="bridge"):
        bridges.validate(again, RULES)


# --- reroute with a path to a stop ------------------------------------------------------------


def test_a_reroute_keeps_a_path_to_a_stop_working() -> None:
    w = new_world()
    down(w)  # bridge-n under repair
    over = put(w, TRUCK, "COALITION", 150_000, 180_000)  # bound for the stop over bridge-s
    over.last_node, over.path = "fob-s-w", ["cross-s", "east-airbase", "cross-n", NORTH]
    clear = put(w, TRUCK, "COALITION", 110_000, 90_000)  # its road crosses no bridge
    clear.last_node, clear.path = "west-airbase", ["fob-n-w", NORTH]
    bridges.damage(w, RULES, SOUTH, MAX_HP, 1, [])
    assert over.path == ["fob-s-w"]  # no road left to the far bank: it stops at its own
    assert clear.path == ["fob-n-w", NORTH]
    run(w, 3)  # and both still drive


# --- Q-SIM-112: no re-strike of a bridge under repair -----------------------------------------


@pytest.mark.parametrize("by", ["strike", "order"])
def test_a_down_bridge_under_repair_is_never_struck_again(by: str) -> None:
    w = new_world(SURE)
    jet = jet_at(w)
    if by == "strike":
        strike(w, jet, NORTH)
    else:
        ordered(jet, NORTH)
    down(w, hp=100)  # down, part repaired
    assert of(run(w, 30), WeaponFired) == [] and w.bridge_hp[NORTH] == 100
    w.bridge_down.clear()  # the same hp, not down: it is a target again
    shots = of(run(w, 30), WeaponFired)
    assert shots and {s.target_node_id for s in shots} == {NORTH}


def test_a_goto_hold_on_a_bridge_ends_when_it_falls_and_never_resumes() -> None:
    w = tt.new_world()
    jet = tt.put(w, JET, "west-airbase")
    jet.pos, jet.last_node, jet.state = Vec2(*RULES.roads.pos[NORTH]), NORTH, "ON_STATION"
    ordered(jet, NORTH)
    tt.board_pass(w)
    assert jet.held_since in range(1, w.campaign.running_ticks + 1)  # armed, holding the bridge
    cut(w, NORTH)
    tt.board_pass(w)
    assert (jet.order, jet.order_node, jet.held_since) == (None, None, None)
    w.bridge_hp[NORTH] = MAX_HP - 1  # repaired back to just short of full
    rules = w.rules
    assert rules is not None and rules.combat is not None
    assert bridges.target(w, rules, rules.combat.weapons["AG_LIGHT"], jet) is None


def test_a_goto_under_way_to_a_down_bridge_ends_before_it_arrives() -> None:
    """Q-SIM-115: the order ends at the next pass even under way, so a unit that arrives after
    the repair never fires on the bridge it was sent to."""
    w = tt.new_world()
    jet = tt.put(w, JET, "west-airbase")
    ordered(jet, NORTH)
    jet.path = [NORTH]  # under way
    cut(w, NORTH)
    tt.board_pass(w)
    assert (jet.order, jet.order_node) == (None, None)


def test_a_truck_on_the_road_out_to_a_stop_escapes_when_its_bank_is_captured() -> None:
    """Capture escape starts from the bank (`road_start`), not the bridge id, which is no road
    vertex: before, the truck found no route home and was lost."""
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.pos, truck.path = Vec2(131_000, 60_000), [NORTH]  # 1 km out, inside the capture radius
    w.owner["fob-n-w"] = "ENEMY"
    out: list[Event] = []
    assert RULES.capture is not None
    capture._resolve_units(w, RULES, RULES.capture, "fob-n-w", "COALITION", out)
    assert w.find(truck.id) is truck and truck.path and NORTH not in truck.path


# --- the REPAIR_BRIDGE job and TB-8 -----------------------------------------------------------


def _jobs(w: World, kind: str, side: str = "COALITION") -> list[Job]:
    return [j for j in w.boards[side].values() if j.kind == kind]  # type: ignore[index]


def test_the_coalition_board_posts_a_repair_job_for_each_down_bridge_and_a_truck_takes_it() -> None:
    w = tt.new_world()
    w.bridge_hp[SOUTH] = MAX_HP - 50  # damaged, not down: no job
    down(w, hp=MAX_HP - 1)
    truck = tt.put(w, TRUCK, "fob-n-w", cargo=0)
    events = tt.board_pass(w)
    (job,) = _jobs(w, "REPAIR_BRIDGE")
    (created,) = [e for e in of(events, JobCreated) if e.job_kind == "REPAIR_BRIDGE"]
    assert (created.side, created.node_id, job.key) == (
        "COALITION",
        NORTH,
        "repair_bridge:bridge-n",
    )
    assert _jobs(w, "REPAIR_BRIDGE", "ENEMY") == []  # the Static never undoes its own cuts
    assert [c.entity_id for c in of(events, JobClaimed) if c.job_id == job.id] == [truck.id]
    assert truck.path == ["fob-n-w", NORTH]
    truck.pos, truck.path = Vec2(199_000, 60_000), [NORTH]  # the 70 km drive, done
    events = []
    for _ in range(400):  # the last 1 km, 17 ticks of repair, then the next pass
        events += step(w, [])
        if job.id not in w.boards["COALITION"]:
            break
    (up,) = of(events, BridgeRepaired)
    (done,) = [d for d in of(events, JobDone) if d.job_id == job.id]
    assert up.by_id == truck.id and [p.entity_id for p in done.participants] == [truck.id]
    assert truck.job_id is None and truck.path == ["fob-n-w"]  # back to its bank


def test_no_repair_job_without_a_carrier_that_can_reach_a_bank() -> None:
    w = tt.new_world()
    down(w)
    assert _jobs(w, "REPAIR_BRIDGE") == [] and of(tt.board_pass(w), JobCreated) == []
    wreck = tt.put(w, TRUCK, "fob-n-w")
    wreck.damage_state = "DISABLED"
    tt.board_pass(w)
    assert _jobs(w, "REPAIR_BRIDGE") == []
    cut(w, SOUTH)  # a truck on the far side reaches cross-n, a bank of each bridge
    tt.put(w, TRUCK, "east-airbase", owner="AI_GARRISON")
    w.owner["east-airbase"] = "COALITION"
    tt.board_pass(w)
    assert sorted(j.node or "" for j in _jobs(w, "REPAIR_BRIDGE")) == [NORTH, SOUTH]


def test_the_generator_posts_only_what_the_executor_can_route() -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.order = "HOLD"  # busy: the generator still counts it, the board does not assign it
    tt.board_pass(w)
    (job,) = _jobs(w, "REPAIR_BRIDGE")
    assert not job.claims
    truck.order = None
    rules = w.rules
    assert rules is not None
    assert tasking._feasible(w, rules, {}, truck, job) == "ok"


def _cut_off(w: World) -> Entity:
    """cross-n is the coalition's and starving, both bridges are down, a truck is at fob-n-w."""
    w.owner["cross-n"] = "COALITION"
    w.stock["cross-n"] = 0
    cut(w, NORTH, SOUTH)
    assert plan_run(w, RULES, "COALITION", "cross-n") is None
    return tt.put(w, TRUCK, "fob-n-w")


def test_a_cut_off_resupply_waits_for_the_repair_and_opens_when_it_is_done() -> None:
    w = tt.new_world()
    _cut_off(w)
    events = tt.board_pass(w)
    (repair,) = [j for j in _jobs(w, "REPAIR_BRIDGE") if j.node == NORTH]
    # the first cut bridge on the intact route haven -> west-airbase -> fob-n-w -> cross-n
    (resupply,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    assert resupply.depends_on == repair.id and not resupply.claims
    (created,) = [e for e in of(events, JobCreated) if e.job_id == resupply.id]
    assert created.depends_on_job_id == repair.id
    w.bridge_hp[NORTH], w.bridge_down = MAX_HP, {SOUTH}  # repaired
    events = tt.board_pass(w)
    assert [d.job_id for d in of(events, JobDone)] == [repair.id]
    assert resupply.depends_on is None and resupply.id in w.boards["COALITION"]


def test_an_open_resupply_gains_the_dependency_by_being_posted_again() -> None:
    w = tt.new_world()
    w.owner["cross-n"], w.stock["cross-n"] = "COALITION", 0
    tt.board_pass(w)
    (old,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    assert old.depends_on is None
    cut(w, NORTH, SOUTH)
    tt.put(w, TRUCK, "fob-n-w")
    events = tt.board_pass(w)
    assert old.id in [e.job_id for e in of(events, JobExpired)]
    (new,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    repair = {j.node: j.id for j in _jobs(w, "REPAIR_BRIDGE")}
    assert new.id != old.id and new.depends_on == repair[NORTH]


def test_a_cut_off_resupply_fails_when_its_repair_job_expires() -> None:
    w = tt.new_world()
    truck = _cut_off(w)
    tt.board_pass(w)
    (repair,) = [j for j in _jobs(w, "REPAIR_BRIDGE") if j.node == NORTH]
    (resupply,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    assert resupply.depends_on == repair.id
    truck.damage_state = "DISABLED"  # no carrier left: the repair job is no longer generated
    events = tt.board_pass(w)
    assert repair.id in [e.job_id for e in of(events, JobExpired)]
    assert resupply.id in [e.job_id for e in of(events, JobFailed)]


def test_the_static_board_never_posts_a_repair_job() -> None:
    w = tt.new_world()
    down(w)
    convoy = tt.put(w, "ENEMY_CONVOY", "cross-n", owner="AI_GARRISON")
    assert convoy.side == "ENEMY"
    tt.board_pass(w)
    assert _jobs(w, "REPAIR_BRIDGE", "ENEMY") == []


def test_a_repair_job_survives_a_snapshot() -> None:
    w = tt.new_world()
    down(w)
    tt.put(w, TRUCK, "fob-n-w")
    for _ in range(tt.EVERY):
        step(w, [])
    assert _jobs(w, "REPAIR_BRIDGE")
    again = load(save(w))
    assert state_hash(again) == state_hash(w)


def test_repair_never_passes_the_maximum() -> None:
    fast = dataclasses.replace(
        RULES, supply=dataclasses.replace(RULES.supply, bridge_repair_milli=700_000)
    )  # 700 hp a tick
    w = new_world(fast)
    down(w, hp=10)
    parked(w)
    assert len(of(run(w), BridgeRepaired)) == 1
    assert w.bridge_hp[NORTH] == MAX_HP and w.bridge_repair[NORTH] == 0


def test_a_reroute_keeps_the_stop_at_the_end_of_a_new_route() -> None:
    w = new_world()
    w.bridge_hp[NORTH] = MAX_HP - 10  # damaged, so its road is open
    e = put(w, TRUCK, "COALITION", 150_000, 180_000)
    e.last_node, e.path = "fob-s-w", ["cross-s", "east-airbase", "cross-n", NORTH]
    bridges.damage(w, RULES, SOUTH, MAX_HP, 1, [])
    assert e.path == ["fob-s-w", "west-airbase", "fob-n-w", "cross-n", NORTH]


def test_dataclass_rules_without_a_repair_rate_repair_nothing() -> None:
    off = dataclasses.replace(
        RULES, supply=dataclasses.replace(RULES.supply, bridge_repair_milli=0)
    )
    w = new_world(off)
    down(w)
    parked(w)
    run(w, 50)
    assert w.bridge_hp[NORTH] == 0


def test_a_truck_at_the_stop_is_never_on_the_near_side_of_the_cut() -> None:
    """The stop is the cut point: a truck there turning back is past it from either end, whatever
    the float rounding of the projection on a diagonal road (`crosses`)."""
    w = new_world()
    for a, b, c in [
        ((0, 0), (1000, 777), (333, 259)),
        ((328_057, 152_266), (34_355, 158_754), (324_547, 152_331)),  # rounds short from a
    ]:
        roads = RoadGraph({"a": a, "b": b, "c": c}, [Road("a", "b", 1.0, "c")])
        rules = dataclasses.replace(RULES, roads=roads)
        w.bridge_down = {"c"}
        stop = Vec2(*roads.stops["c"])
        assert not bridges.crosses(w, rules, "a", "b", stop)
        assert not bridges.crosses(w, rules, "b", "a", stop)


def test_a_claimant_repairing_at_the_stop_keeps_its_claim_past_the_lease() -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    tt.board_pass(w)
    (job,) = _jobs(w, "REPAIR_BRIDGE")
    truck.pos, truck.path = STOP, []  # parked at the stop, 300 hp to go
    events: list[Event] = []
    for _ in range(tt.LEASE // tt.EVERY + 2):
        events += tt.board_pass(w)
    assert of(events, JobReleased) == [] and truck.id in job.claims


# --- QA round: TB-8 on a claimed job, the loader, the event tick ------------------------------


def test_a_claimed_resupply_keeps_its_job_and_claims_when_its_node_is_cut_off() -> None:
    w = tt.new_world()
    w.owner["cross-n"], w.stock["cross-n"] = "COALITION", 0
    tt.board_pass(w)
    (job,) = [j for j in _jobs(w, "RESUPPLY") if j.node == "cross-n"]
    hauler = tt.put(w, TRUCK, "fob-n-w", cargo=100)
    tasking.claim(w, hauler, job, [])
    hauler.path = ["cross-n"]  # under way: progress, so the lease holds
    cut(w, NORTH, SOUTH)
    tt.put(w, TRUCK, "fob-n-w")
    events = tt.board_pass(w)
    assert job.id in w.boards["COALITION"] and job.depends_on is None
    assert hauler.id in job.claims and hauler.job_id == job.id
    ended = [e.job_id for e in of(events, JobExpired)] + [e.job_id for e in of(events, JobFailed)]
    assert job.id not in ended


def test_the_loader_refuses_a_truck_repair_rate_below_a_thousandth_hp_a_tick() -> None:
    with pytest.raises(ValueError, match=r"bridge repair rate x world_dt is below 0\.001 hp"):
        shipped_config({"logistics.bridge_repair_time_s": 1e9})


def test_bridge_repaired_is_stamped_with_the_tick_being_computed() -> None:
    w = new_world()
    down(w, hp=MAX_HP - 1)
    parked(w)
    events = run(w, 16)
    assert of(events, BridgeRepaired) == []
    (up,) = of(run(w), BridgeRepaired)
    assert up.tick == w.campaign.tick == 17


# --- a truck parked at a stop given a new route -----------------------------------------------


@pytest.mark.parametrize("start", ["parked", "driving"])
def test_a_rebase_from_the_stop_drives_back_along_the_road_through_its_bank(start: str) -> None:
    w = tt.new_world()
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.pos = STOP if start == "parked" else Vec2(190_000, 60_000)
    truck.path = [] if start == "parked" else [NORTH]
    cmd = RebaseCommand.model_validate({
        "kind": "REBASE", "source": "CHAT", "issuer": {"commander_id": truck.commander_id},
        "target_tick": w.campaign.tick + 1, "arrival_seq": 1, "correlation_id": "r1",
        "node_id": "west-airbase",
    })  # fmt: skip
    step(w, [cmd])
    assert truck.path == ["fob-n-w", "west-airbase"]
    for _ in range(4000):  # 60-70 km at the truck's speed: it stays on the y = 60 km road
        step(w, [])
        if truck.pos == Vec2(*RULES.roads.pos["fob-n-w"]):
            break
        assert truck.pos.y == 60_000 and 130_000 < truck.pos.x <= STOP.x
    assert truck.last_node == "fob-n-w" and truck.path[-1] == "west-airbase"


def test_sent_home_from_the_stop_a_truck_drives_back_to_its_bank_first() -> None:
    w = new_world()
    (truck,) = parked(w)
    go_home(w, RULES, truck)
    assert truck.path and truck.path[0] == "fob-n-w"  # fob-n-w is a friendly base: it goes there


# --- escorting a repair crew (Q-SIM-118) ------------------------------------------------------


def _crew(rules: Rules | None = None) -> tuple[World, Entity, Job]:
    """A down bridge-n, a truck claiming its repair job; the next pass may post its escort."""
    w = tt.new_world() if rules is None else tt.new_world(rules=rules)
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    tt.board_pass(w)
    (repair,) = _jobs(w, "REPAIR_BRIDGE")
    assert truck.id in repair.claims
    return w, truck, repair


def _escort(w: World) -> Job | None:
    found = _jobs(w, "ESCORT_CONVOY")
    return found[0] if found else None


def test_a_repair_crew_gets_an_escort_job_with_no_threat() -> None:
    w, truck, _ = _crew()
    assert not w.contacts["COALITION"] and not w.markers["COALITION"]  # nothing threatens it
    events = tt.board_pass(w)
    job = _escort(w)
    assert job is not None and (job.key, job.entity, job.node) == (
        f"escort:{truck.id}",
        truck.id,
        NORTH,
    )
    (created,) = [e for e in of(events, JobCreated) if e.job_id == job.id]
    assert created.entity_id == truck.id and created.node_id == NORTH
    truck.pos, truck.path = STOP, []  # parked at the stop: no path left, yet the job stays
    tt.board_pass(w)
    assert job.id in w.boards["COALITION"]


def test_no_crew_escort_with_the_option_off() -> None:
    tr = dataclasses.replace(tt.TR, escort_repair_crews=False)
    w, _, _ = _crew(dataclasses.replace(tt.RULES, tasking=tr))
    tt.board_pass(w)
    assert _escort(w) is None


def _escorted(owner: str = "COMMANDER") -> tuple[World, Entity, Job, Entity]:
    w, truck, _ = _crew()
    jet = tt.put(w, JET, "west-airbase", owner=owner)  # type: ignore[arg-type]
    tt.board_pass(w)
    job = _escort(w)
    assert job is not None
    return w, truck, job, jet


def test_a_viewer_jet_takes_the_crew_escort_as_a_follow_order() -> None:
    _w, truck, job, jet = _escorted()
    assert jet.id in job.claims and jet.follow_id == truck.id


def test_the_ai_garrison_never_takes_a_crew_escort() -> None:
    _w, _, job, jet = _escorted("AI_GARRISON")
    assert not job.claims and jet.follow_id is None


def test_the_crew_escort_is_done_when_the_bridge_is_repaired() -> None:
    w, _truck, job, jet = _escorted()
    tt.board_pass(w)  # the follow order makes the claim active
    w.bridge_hp[NORTH], w.bridge_down = MAX_HP, set()
    events = tt.board_pass(w)
    (done,) = [d for d in of(events, JobDone) if d.job_id == job.id]
    assert [p.entity_id for p in done.participants] == [jet.id] and jet.follow_id is None


def test_the_crew_escort_fails_when_the_truck_is_lost() -> None:
    w, truck, job, _ = _escorted()
    w.remove(truck.id)
    assert job.id in [e.job_id for e in of(tt.board_pass(w), JobFailed)]


def test_the_crew_escort_expires_when_the_truck_drops_the_repair() -> None:
    w, truck, job, _ = _escorted()
    truck.order = "HOLD"  # a human order wins: the repair claim is released
    assert job.id in [e.job_id for e in of(tt.board_pass(w), JobExpired)]


def repairing(w: World, truck: Entity) -> Job:
    """`truck` holds a claim on bridge-n's repair job (it may be anywhere)."""
    spec = JobSpec("REPAIR_BRIDGE", f"repair_bridge:{NORTH}", 2, 1000, node=NORTH)
    job = tasking.post_job(w, "COALITION", spec, [])
    tasking.claim(w, truck, job, [])
    return job


def test_a_ground_follower_holds_station_at_the_stop() -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.pos = STOP
    repairing(w, truck)  # else the board sends it home from the stop
    near = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    near.pos = Vec2(199_600, 60_000)  # within twice the 500 m escort station
    far = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    far.pos = Vec2(197_000, 60_000)
    for f in (near, far):
        f.order, f.follow_id = "FOLLOW", truck.id
    for _ in range(1000):  # 3 m a tick: 2 km in about 670
        step(w, [])
        for f in (near, far):
            assert f.pos.y == 60_000 and 196_999 < f.pos.x <= STOP.x  # never drives off
    assert near.pos == Vec2(199_600, 60_000)  # it held where it was
    assert STOP.x - far.pos.x <= 1_000  # it closed up to twice the station
    held = far.pos
    step(w, [])
    assert far.pos == held  # and holds there
    assert truck.follow_id is None and far.last_node == "fob-n-w"


def test_a_ground_follower_follows_a_truck_out_to_the_stop() -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.pos, truck.path = Vec2(194_000, 60_000), [NORTH]
    f = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    f.pos, f.order, f.follow_id = Vec2(193_000, 60_000), "FOLLOW", truck.id
    step(w, [])
    assert f.path == [NORTH]  # straight on along the bridge's road, not back to fob-n-w


def test_a_crew_escort_replays_identically() -> None:
    def once() -> tuple[str, list[str]]:
        w, _truck, _, _ = _escorted()
        events = []
        for _ in range(3 * tt.EVERY):
            events += step(w, [])
        return state_hash(w), [e.model_dump_json() for e in events]

    a, b = once(), once()
    assert a == b


def test_a_crew_escort_targets_the_truck_not_its_bridge() -> None:
    w, truck, job, _ = _escorted()
    assert tasking._waypoint(w, job) == truck.pos
    rules = w.rules
    assert rules is not None
    assert handlers._route_job(w, job, JET, rules) == "NODE_INVALID_FOR_UNIT"  # JOIN never takes it


def test_a_threatened_trucks_escort_becomes_its_crew_escort() -> None:
    w, truck, _ = _crew()
    spec = JobSpec("ESCORT_CONVOY", f"escort:{truck.id}", 2, 1000, entity=truck.id)
    job = tasking.post_job(w, "COALITION", spec, [])  # as a threatened route posts it
    assert job.node is None
    tt.board_pass(w)
    assert job.node == NORTH  # it now ends with the repair, not on arrival
    truck.pos, truck.path = STOP, []
    tt.board_pass(w)
    assert job.id in w.boards["COALITION"]


def test_a_crew_escort_survives_a_snapshot() -> None:
    w = tt.new_world()
    down(w)
    tt.put(w, TRUCK, "fob-n-w")
    for _ in range(2 * tt.EVERY):
        step(w, [])
    assert _escort(w) is not None
    assert state_hash(load(save(w))) == state_hash(w)


def test_a_follower_out_on_the_bridge_road_turns_back_when_its_leader_does() -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")  # parked at its bank
    f = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    f.pos, f.path, f.order, f.follow_id = Vec2(195_000, 60_000), [NORTH], "FOLLOW", truck.id
    step(w, [])
    assert f.path == ["fob-n-w"] and f.pos.x < 195_000


def test_a_follower_ahead_of_a_truck_bound_for_the_stop_paces_it() -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.pos, truck.path = Vec2(190_000, 60_000), [NORTH]
    f = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    # 600 m ahead, past its 500 m escort station: it slows to keep it (`follow._mult`)
    f.pos, f.path, f.order, f.follow_id = Vec2(190_600, 60_000), [NORTH], "FOLLOW", truck.id
    for _ in range(20):
        step(w, [])
    assert f.path == [NORTH] and 190_600 <= f.pos.x < STOP.x


# --- QA round 3: nobody is stranded at a stop ---------------------------------------------------


def test_a_truck_still_on_the_way_when_the_repair_ends_turns_back_and_is_never_stranded() -> None:
    w = tt.new_world()
    down(w, hp=MAX_HP - 1)
    early, late = tt.put(w, TRUCK, "fob-n-w"), tt.put(w, TRUCK, "fob-n-w")
    tt.board_pass(w)
    (job,) = _jobs(w, "REPAIR_BRIDGE")
    assert sorted(job.claims) == [early.id, late.id]
    early.pos, early.path = STOP, []  # parked: it finishes the last hp
    late.pos, late.path = Vec2(190_000, 60_000), [NORTH]  # 10 km short of the stop
    rules = w.rules
    assert rules is not None
    for _ in range(5000):
        step(w, [])
        assert at_stop(rules, late) is None or late.job_id is not None
        if job.id not in w.boards["COALITION"] and late.path:
            assert NORTH not in late.path  # it lost the stop when the job ended
    assert w.bridge_down == set() and late.job_id is None
    assert late.pos.x < STOP.x and at_stop(rules, early) is None


def test_an_evicted_ai_truck_on_its_way_to_the_stop_turns_back() -> None:
    w = tt.new_world()
    down(w)
    ai = tt.put(w, TRUCK, "fob-n-w", owner="AI_GARRISON")
    ai.pos, ai.path = Vec2(195_000, 60_000), [NORTH]
    spec = JobSpec("REPAIR_BRIDGE", f"repair_bridge:{NORTH}", 1, 1000, node=NORTH)
    job = tasking.post_job(w, "COALITION", spec, [])
    tasking.claim(w, ai, job, [])
    human = tt.put(w, TRUCK, "fob-n-w")
    tasking.claim(w, human, job, [])  # the slot is full: the AI truck is displaced
    assert ai.job_id is None and ai.path == ["fob-n-w"]


@pytest.mark.parametrize("on_the_way", [False, True])
def test_the_board_sends_a_jobless_ground_unit_home_from_a_stop(on_the_way: bool) -> None:
    w = tt.new_world()
    down(w)
    truck = tt.put(w, TRUCK, "fob-n-w")
    truck.pos, truck.path = (Vec2(195_000, 60_000), [NORTH]) if on_the_way else (STOP, [])
    jet = tt.put(w, JET, "west-airbase")
    jet.state, jet.path = "EN_ROUTE", [NORTH]  # an aircraft bound for the bridge keeps its path
    follower = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    follower.pos, follower.order, follower.follow_id = STOP, "FOLLOW", truck.id  # follow's call
    w.campaign.running_ticks = tt.EVERY - 1
    tasking.run(w, [])
    assert truck.path[0] == "fob-n-w" and NORTH not in truck.path
    assert jet.path == [NORTH] or jet.job_id is not None
    assert follower.pos == STOP and follower.path == []  # left to `follow`


def test_a_follower_on_the_stop_never_crosses_the_down_bridge() -> None:
    w = tt.new_world()
    down(w)
    lead = tt.put(w, TRUCK, "cross-n")
    f = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    f.pos, f.order, f.follow_id = STOP, "FOLLOW", lead.id
    for _ in range(300):
        step(w, [])
        assert f.pos.x <= STOP.x and f.pos.y == 60_000, (f.pos, f.path)


def test_the_crew_escort_fails_when_the_truck_is_disabled() -> None:
    w, truck, job, _ = _escorted()
    tt.board_pass(w)
    truck.damage_state = "DISABLED"
    events = []
    for _ in range(2 * tt.EVERY):
        events += step(w, [])
    assert job.id in [e.job_id for e in of(events, JobFailed)]
    assert job.id not in [e.job_id for e in of(events, JobExpired)]


def test_go_home_is_unchanged_for_a_unit_stopped_mid_road_by_a_friendly_base() -> None:
    w = tt.new_world()
    u = tt.put(w, "GARRISON_INFANTRY", "fob-n-w")
    u.pos = Vec2(150_000, 60_000)  # stopped on the road toward cross-n, no path
    go_home(w, RULES, u)
    assert u.path == []  # its last node is a friendly base: as before NX-373 part 2
    u.path = ["cross-n"]
    go_home(w, RULES, u)
    assert u.path[0] == "cross-n" and u.path[-1] != "cross-n"  # finishes its leg, then home
