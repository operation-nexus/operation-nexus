"""NX-121: kinematics (SIM-CORE SC-2/9/11, §4; GAMEPLAY §5): air straight, ground on roads."""

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.contracts.gen.common.enums import Domain, Side, UnitKind
from nexus.core.roads import Road, RoadGraph, shortest_path
from nexus.core.rules import Rules, make_rules
from nexus.core.step import step
from nexus.core.world import Campaign, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.config import game_ticks, load_balance
from nexus.runtime.theater import load_theater, road_graph
from nexus.runtime.units import load_catalog

ROOT = Path(__file__).resolve().parents[4]
CONTENT = ROOT / "content"
STRAIT_1 = load_theater(CONTENT / "theaters" / "strait-1.yaml")
ROADS = road_graph(STRAIT_1)
W, H = STRAIT_1.bounds_m.w, STRAIT_1.bounds_m.h
CATALOG = load_catalog(CONTENT / "units", CONTENT / "weapons.yaml", CONTENT / "roles.yaml")
UNITS, ROLES = CATALOG.units, CATALOG.roles.roles
BALANCE = load_balance(ROOT / "balance" / "default.yaml")
CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
JET: UnitKind = "STRIKE_FIGHTER"
TRUCK: UnitKind = "LOGI_TRUCK"
# a -(x0.5)- b -(x2.0)- c: a 300 m road east, then 400 m south.
ELL = RoadGraph(
    {"a": (0, 0), "b": (300, 0), "c": (300, 400)}, [Road("a", "b", 0.5), Road("b", "c", 2.0)]
)


def rules(world_dt: float, roads: RoadGraph = ROADS) -> Rules:
    speeds: dict[UnitKind, float] = {JET: 250.0, TRUCK: 25.0}
    domains: dict[UnitKind, Domain] = {JET: "AIR", TRUCK: "GROUND"}
    no_bases: dict[Side, tuple[str, ...]] = {"COALITION": (), "ENEMY": ()}  # never bingo
    air = ({JET: 100.0}, {JET: 1e6}, 0.0, no_bases, (W, H), 120.0)
    return Rules(
        world_dt, speeds, domains, roads, {}, "haven", 1, 0, 1, 1, *air,
        {}, {}, 5, 1, {}, 1000.0, {},  # no sensors, no masking
    )  # fmt: skip


def scaled(time_scale: float) -> Rules:
    sim = BALANCE.sim.model_copy(update={"time_scale": time_scale})
    return make_rules(
        sim,
        UNITS,
        ROADS,
        roles=ROLES,
        theater=STRAIT_1,
        slots=BALANCE.slots,
        air=BALANCE.air,
        fow=BALANCE.fow,
        respawn_delay_ticks=0,
        track_fade_ticks=1,
        mask_cell_m=1000.0,
        masking={},
    )


def test_make_rules_refuses_a_zero_mask_cell() -> None:
    with pytest.raises(ValueError, match="mask_cell_m"):
        replace_mask_cell(0.0)


def replace_mask_cell(cell_m: float) -> Rules:
    return make_rules(
        BALANCE.sim, UNITS, ROADS, roles=ROLES, theater=STRAIT_1, slots=BALANCE.slots,
        air=BALANCE.air, fow=BALANCE.fow, respawn_delay_ticks=0, track_fade_ticks=1,
        mask_cell_m=cell_m, masking={},
    )  # fmt: skip


def world(r: Rules | None) -> World:
    return World.new(Campaign(CAMPAIGN_ID, 7, "cfg-test"), r)


def jet(w: World, at: Vec2, *path: str | Vec2) -> Entity:
    e = w.spawn(JET, "COALITION", "COMMANDER", at, hp=100)
    e.path, e.state, e.fuel = list(path), "EN_ROUTE", 1e6
    return e


def truck(w: World, node: str, *path: str, at: Vec2 | None = None) -> Entity:
    """A truck at `node` (or at `at` on the edge from `node` to `path[0]`)."""
    x, y = w.rules.roads.pos[node] if w.rules else (0, 0)
    e = w.spawn(TRUCK, "COALITION", "COMMANDER", at or Vec2(x, y), hp=100)
    e.path, e.last_node = list(path), node
    return e


def test_world_dt_is_exact_from_balance() -> None:
    assert scaled(6.0).world_dt == 0.6  # 0.1 * 6.0 in floats would be 0.6000000000000001
    assert scaled(1.0).world_dt == 0.1


@pytest.mark.parametrize(("time_scale", "jet_m", "truck_m"), [(1.0, 25.0, 2.5), (6.0, 150.0, 15.0)])
def test_sc2_distance_per_tick_is_speed_times_world_dt(
    time_scale: float, jet_m: float, truck_m: float
) -> None:
    w = world(scaled(time_scale))
    a = jet(w, Vec2(1000, 1000), Vec2(9000, 1000))
    t = truck(w, "haven", "west-airbase")  # haven (20 km, 120 km) -> east, speed_mult 1.0
    step(w, [])
    assert a.pos == Vec2(1000 + jet_m, 1000)
    assert a.vel == Vec2(250.0, 0.0)
    assert t.pos == Vec2(20000 + truck_m, 120000)
    assert t.vel == Vec2(25.0, 0.0)
    # A game-time timer does not scale (SC-2, SC-12): 0.25 s is 3 ticks at any time_scale.
    sim = BALANCE.sim.model_copy(update={"time_scale": time_scale})
    assert game_ticks(0.25, BALANCE.model_copy(update={"sim": sim})) == 3


def test_ground_speed_is_scaled_by_speed_mult() -> None:
    w = world(rules(1.0, ELL))
    slow = truck(w, "a", "b")
    fast = truck(w, "b", "c")
    step(w, [])
    assert slow.pos == Vec2(12.5, 0)  # 25 m/s x 0.5 x 1 s
    assert fast.pos == Vec2(300, 50)  # 25 m/s x 2.0 x 1 s
    assert fast.vel == Vec2(0.0, 50.0)


def test_carry_over_across_a_node_in_one_tick() -> None:
    w = world(rules(1.0, ELL))
    t = truck(w, "a", "b", "c", at=Vec2(290, 0))
    step(w, [])
    # 10 m at 12.5 m/s takes 0.8 s; the last 0.2 s at 50 m/s goes 10 m down b-c.
    assert t.last_node == "b"
    assert t.path == ["c"]
    assert t.pos.x == 300.0
    assert t.pos.y == pytest.approx(10.0)
    assert t.vel == Vec2(0.0, 50.0)


def test_arrival_snaps_and_stops() -> None:
    w = world(rules(1.0, ELL))
    t = truck(w, "b", "c", at=Vec2(300, 395))
    a = jet(w, Vec2(0.1, 0.2), Vec2(100.3, 0.2), Vec2(100.3, 50.7))
    step(w, [])
    assert (t.pos, t.vel, t.path, t.last_node) == (Vec2(300, 400), Vec2(0, 0), [], "c")
    # An aircraft snaps too, then orbits at its stall speed (NX-368, tests/core/test_air.py).
    assert (a.pos, a.vel, a.path, a.state) == (Vec2(100.3, 50.7), Vec2(0, 100), [], "ON_STATION")
    step(w, [])
    assert t.pos == Vec2(300, 400)


def test_idle_units_do_not_move_and_velocity_clears() -> None:
    w = world(None)  # no rules needed while nothing has a path
    e = w.spawn(TRUCK, "COALITION", "COMMANDER", Vec2(5, 5), vel=Vec2(25, 0), hp=100)
    step(w, [])
    assert (e.pos, e.vel) == (Vec2(5, 5), Vec2(0, 0))


def test_paused_campaign_freezes_movement() -> None:
    w = world(rules(1.0, ELL))
    t = truck(w, "a", "b")
    step(w, [])
    before = (t.pos, t.vel, list(t.path))
    w.campaign.clock_paused = True
    for _ in range(5):
        step(w, [])
    assert (t.pos, t.vel, t.path) == before


def test_bad_paths_raise() -> None:
    w = world(None)
    jet(w, Vec2(0, 0), Vec2(10, 0))
    with pytest.raises(ValueError, match="no rules"):
        step(w, [])
    w = world(rules(1.0, ELL))
    truck(w, "a", "c")  # not adjacent
    with pytest.raises(ValueError, match="no road"):
        step(w, [])
    w = world(rules(1.0, ELL))
    truck(w, "a").path = [Vec2(10, 0)]  # ground units move node to node
    with pytest.raises(ValueError, match="road graph"):
        step(w, [])


def test_a_route_starting_at_the_current_node_is_followed() -> None:
    w = world(rules(1.0, ELL))
    t = truck(w, "a")
    route = shortest_path(ELL, "a", "b", blocked=frozenset())
    assert route is not None
    t.path = list(route)  # [a, b]: starts where the truck is
    step(w, [])
    assert t.last_node == "a" and t.path == ["b"] and t.vel != Vec2(0, 0)


def moved_world(ticks: int = 40) -> World:
    w = world(rules(60.0))  # 15 km per tick at 250 m/s: mid-segment after most ticks
    jet(w, Vec2(1234.5, 6789.25), Vec2(150000, 30000), "east-airbase", Vec2(5, 239000))
    truck(w, "haven", "west-airbase", "fob-s-w", "cross-s")
    truck(w, "static-hq", "fob-n-e", "cross-n", "fob-n-w")
    for _ in range(ticks):
        step(w, [])
    return w


def test_snapshot_round_trips_mid_edge() -> None:
    w = moved_world(7)
    assert all(e.path for e in w.entities())  # everyone is mid-route
    restored = load(save(w))
    restored.rules = w.rules
    assert state_hash(restored) == state_hash(w)
    for _ in range(30):
        step(w, [])
        step(restored, [])
    assert save(restored) == save(w)


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_movement import moved_world\n"
    "from nexus.core.world import state_hash; print(state_hash(moved_world()))"
)


def test_moved_state_hash_is_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert run("1") == run("2") == state_hash(moved_world())


def _off_segment(p: Vec2, a: Vec2, b: Vec2) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)
    t = min(max(t, 0.0), 1.0)
    return math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy)


def _node(name: str) -> Vec2:
    x, y = ROADS.pos[name]
    return Vec2(x, y)


def _in_bounds(p: Vec2) -> bool:
    return -1e-6 <= p.x <= W + 1e-6 and -1e-6 <= p.y <= H + 1e-6


ROAD_NODES = [n for n in sorted(ROADS.pos) if ROADS.neighbours(n)]  # bridges sit on edges


@given(
    start=st.sampled_from(ROAD_NODES),
    turns=st.lists(st.integers(min_value=0, max_value=3), min_size=1, max_size=8),
    world_dt=st.floats(min_value=60.0, max_value=3000.0),  # >= 1.5 km a tick: few ticks
)
def test_ground_units_stay_on_the_road_graph(start: str, turns: list[int], world_dt: float) -> None:
    path: list[str] = []
    here = start
    for turn in turns:  # a random walk along existing roads
        out = ROADS.neighbours(here)
        here = out[turn % len(out)][0]
        path.append(here)
    w = world(rules(world_dt))
    t = truck(w, start, *path)
    for _ in range(10_000):
        if not t.path:
            break
        step(w, [])
        assert t.last_node is not None and _in_bounds(t.pos)
        if t.path:  # on the edge from the node it last reached to the next one
            assert _off_segment(t.pos, _node(t.last_node), _node(str(t.path[0]))) < 1e-6
    assert (t.path, t.last_node, t.pos) == ([], path[-1], _node(path[-1]))


coords = st.tuples(st.floats(0, W), st.floats(0, H)).map(lambda p: Vec2(*p))


@given(
    start=coords,
    waypoints=st.lists(coords, min_size=1, max_size=6),
    world_dt=st.floats(min_value=30.0, max_value=600.0),  # >= 7.5 km a tick: few ticks
)
def test_air_units_stay_in_bounds_and_arrive(
    start: Vec2, waypoints: list[Vec2], world_dt: float
) -> None:
    w = world(rules(world_dt))
    a = jet(w, start, *waypoints)
    for _ in range(10_000):
        if not a.path:
            break
        step(w, [])
        assert _in_bounds(a.pos)
    assert (a.path, a.pos, a.state) == ([], waypoints[-1], "ON_STATION")
