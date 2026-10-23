"""NX-368: aircraft states, stall speed, idle orbit, bingo fuel RTB and landing (Q-SIM-38;
GAMEPLAY §5; STATE-MACHINES §4.1; SIM-CORE SC-2/9/11, §4).

Shipped strait-1 values used below: STRIKE_FIGHTER top 250 m/s, stall 100 m/s, fuel 3600 world s;
`air.bingo_reserve_frac` 0.15 (540 s); `air.orbit_period_s` 120; 0.6 world s per tick; haven
(20 km, 120 km), west-airbase (90 km, 120 km), east-airbase (310 km, 120 km).
"""

import dataclasses
import math
import os
import subprocess
import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core.roads import RoadGraph
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.world import Campaign, Entity, UnitState, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
RULES = dataclasses.replace(load_campaign_config().rules, tasking=None)  # NX-374: board off
JET: UnitKind = "STRIKE_FIGHTER"
CID = "0192f0c1-7a2b-7c3d-8e4f-000000000099"
W, H = 400_000.0, 240_000.0


def node(name: str) -> Vec2:
    return Vec2(*RULES.roads.pos[name])


def hand_rules(
    world_dt: float = 1.0, pos: dict[str, tuple[int, int]] | None = None, reserve: float = 0.1
) -> Rules:
    """A jet with top 100 m/s, stall 40 m/s, 1000 s of fuel, a 10% reserve (100 s) and a 120 s
    orbit (radius 763.9 m); a 5-tick respawn delay; the coalition lands at the given nodes."""
    pos = {"home": (0, 0)} if pos is None else pos
    bases = tuple(sorted(pos))
    return Rules(
        world_dt, {JET: 100.0}, {JET: "AIR"}, RoadGraph(pos, []), {}, "home", 1, 5, 1, 1,
        {JET: 40.0}, {JET: 1000.0}, reserve, bases, (W, H), 120.0, {}, {}, 5, 1, {}, 1000.0, {},
        0.0, frozenset(), 1.0, 1, 1.0, 3, 7,
    )  # fmt: skip


def world(rules: Rules) -> World:
    w = World.new(Campaign(CAMPAIGN_ID, 7, "cfg-test"), rules)
    for node in rules.landing_nodes:  # hand rules own nothing: the coalition lands at them
        w.owner.setdefault(node, "COALITION")
    return w


def aircraft(
    w: World, at: Vec2, *path: str | Vec2, state: UnitState = "EN_ROUTE", fuel: float = 1000.0,
    kind: UnitKind = JET, side: Side = "COALITION",
) -> Entity:  # fmt: skip
    e = w.spawn(kind, side, "COMMANDER", at, commander_id=CID, hp=100)
    e.path, e.state, e.fuel = list(path), state, fuel
    return e


def run(w: World, ticks: int) -> None:
    for _ in range(ticks):
        step(w, [])


def run_until_landed(w: World, e: Entity, limit: int) -> bool:
    for _ in range(limit):
        step(w, [])
        if e.state == "LANDED":
            return True
    return False


def join(n: int, role: str, node_id: str | None, *, hold: bool = False) -> JoinCommand:
    return JoinCommand.model_validate(
        {
            "kind": "JOIN",
            "source": "CHAT",
            "issuer": {"commander_id": f"0192f0c1-7a2b-7c3d-8e4f-{n:012d}"},
            "target_tick": 1,
            "arrival_seq": n,
            "correlation_id": f"m{n}",
            "role": role,
            "target": None if node_id is None else {"node_id": node_id},
            "hold": hold,
        }
    )


def test_join_spawns_aircraft_landed_and_one_with_a_target_takes_off() -> None:
    w = world(RULES)
    step(w, [join(1, "STRIKE", None, hold=True), join(2, "STRIKE", "east-airbase")])
    held, sortie = w.get(1), w.get(2)
    assert (held.state, held.fuel, held.pos, held.vel) == (
        "LANDED",
        3600.0,
        node("haven"),
        Vec2(0, 0),
    )
    assert (sortie.state, sortie.vel) == ("EN_ROUTE", Vec2(250.0, 0.0))  # took off on tick 1
    assert sortie.fuel == pytest.approx(3600.0 - 0.6)
    run(w, 100)
    assert (held.state, held.fuel, held.pos) == ("LANDED", 3600.0, node("haven"))  # no burn
    assert sortie.pos == Vec2(20_000 + 101 * 150.0, 120_000)


def test_bingo_worked_example() -> None:
    """Home at (0, 0); the jet starts 50 m east, flying east at 100 m/s with 1000 s of fuel.
    Before tick k it is 50 + 100(k-1) m out with 1000 - (k-1) s left; bingo needs
    1000 - (k-1) <= 0.5 + (k-1) + 100, first true for k = 451 (550 <= 550.5; k = 450 gives
    551 > 549.5). It turns on tick 451 at 45,050 m, ends the tick at 44,950 m and reaches home
    449.5 ticks later: during tick 901, with 1000 - 901 = 99 s left."""
    w = world(hand_rules())
    a = aircraft(w, Vec2(50, 0), Vec2(300_000, 0))
    run(w, 450)
    assert (a.state, a.path) == ("EN_ROUTE", [Vec2(300_000, 0)])
    run(w, 1)
    assert (a.state, a.path, a.fuel) == ("RTB", ["home"], 549.0)
    assert a.pos.x == pytest.approx(44_950.0)
    run(w, 449)  # tick 900: 50 m out
    assert a.state == "RTB" and a.pos.x == pytest.approx(50.0)
    run(w, 1)
    assert (a.state, a.pos, a.vel, a.path, a.last_node, a.fuel) == (
        "LANDED", Vec2(0, 0), Vec2(0, 0), [], "home", 99.0,
    )  # fmt: skip
    run(w, 50)
    assert (a.state, a.pos, a.fuel) == ("LANDED", Vec2(0, 0), 99.0)  # landed: no burn


def test_rtb_goes_to_the_nearest_own_airbase_or_sanctuary() -> None:
    w = world(RULES)
    # Near cross-n (230 km, 60 km): fob-n-w and east-airbase are 100 km away, west-airbase 152 km.
    coalition = aircraft(w, Vec2(230_000, 60_000), "static-hq", fuel=1.0)
    # Near west-airbase: the enemy's only landing base is east-airbase.
    enemy = aircraft(w, Vec2(95_000, 120_000), side="ENEMY", kind="ENEMY_FIGHTER", fuel=1.0)
    step(w, [])
    assert (coalition.state, coalition.path) == ("RTB", ["west-airbase"])
    assert (enemy.state, enemy.path) == ("RTB", ["east-airbase"])


def test_bingo_ties_break_by_node_id() -> None:
    w = world(hand_rules(pos={"b-base": (1000, 0), "a-base": (-1000, 0)}))
    a = aircraft(w, Vec2(0, 0), state="ON_STATION", fuel=1.0)
    step(w, [])
    assert (a.state, a.path) == ("RTB", ["a-base"])


def test_idle_aircraft_orbits_at_stall_speed_until_bingo_then_lands() -> None:
    w = world(RULES)
    # haven -> fob-n-w is 125.3 km at 150 m a tick: arrives on tick 836. An FOB is no landing base.
    step(w, [join(1, "STRIKE", "fob-n-w")])
    a = w.get(1)
    run(w, 834)
    assert (a.state, a.path) == ("EN_ROUTE", ["fob-n-w"])
    run(w, 1)
    assert (a.state, a.pos) == ("ON_STATION", node("fob-n-w"))
    entry, centre = a.pos, a.orbit
    assert centre is not None
    r = 100.0 * 120.0 / math.tau  # ~1,910 m
    for _ in range(200):  # one lap: 120 world s at 0.6 s a tick
        step(w, [])
        assert a.state == "ON_STATION"
        assert math.hypot(a.pos.x - centre.x, a.pos.y - centre.y) == pytest.approx(r)
        assert math.hypot(a.vel.x, a.vel.y) == pytest.approx(100.0)  # never below stall speed
    assert a.pos.x == pytest.approx(entry.x) and a.pos.y == pytest.approx(entry.y)
    # Fuel at arrival 3600 - 836 x 0.6 = 3098.4 s. The nearest coalition base is west-airbase,
    # 72.1 km away (288.4 s at 250 m/s), within one orbit diameter (2r / 250 m/s = 15.3 s): bingo
    # at 540 + 288.4 +- 15.3 s, so it holds the station for 3,730 to 3,790 ticks, then flies
    # 72.1 km (about 481 ticks) home.
    run(w, 3400)
    assert a.state == "ON_STATION"
    assert run_until_landed(w, a, 1000)
    assert (a.pos, a.vel, a.last_node, a.orbit) == (
        node("west-airbase"),
        Vec2(0, 0),
        "west-airbase",
        None,
    )
    # Landed with about the reserve left, plus the 108 s the landing tick refuelled (NX-123).
    assert a.fuel == pytest.approx(540.0 + 108.0, abs=5.0)


def test_a_landed_aircraft_given_a_path_takes_off() -> None:
    w = world(hand_rules())
    a = aircraft(w, Vec2(0, 0), state="LANDED")
    run(w, 3)
    assert (a.state, a.pos, a.fuel) == ("LANDED", Vec2(0, 0), 1000.0)
    a.path = [Vec2(0, 5000)]  # an order (TARGET, later items)
    step(w, [])
    assert (a.state, a.pos, a.vel, a.fuel) == ("EN_ROUTE", Vec2(0, 100), Vec2(0, 100), 999.0)


def test_pause_freezes_fuel_and_orbit() -> None:
    w = world(hand_rules())
    a = aircraft(w, Vec2(50_000, 50_000), Vec2(50_000, 51_000))
    run(w, 15)
    assert a.state == "ON_STATION"
    before = (a.pos, a.vel, a.fuel, a.orbit, a.state)
    w.campaign.clock_paused = True
    run(w, 20)
    assert (a.pos, a.vel, a.fuel, a.orbit, a.state) == before
    w.campaign.clock_paused = False
    step(w, [])
    assert a.pos != before[0] and a.fuel == 984.0


angles = st.floats(min_value=0.0, max_value=math.tau, exclude_max=True)


@given(
    x=st.floats(0, W),
    y=st.floats(0, H),
    heading=angles,
    world_dt=st.floats(min_value=0.1, max_value=60.0),
)
def test_orbit_stays_in_bounds_at_stall_speed(
    x: float, y: float, heading: float, world_dt: float
) -> None:
    w = world(hand_rules(world_dt))
    # Arrive at (x, y) along `heading` from 1 m back: that leg sets the orbit's entry.
    start = Vec2(x - math.cos(heading), y - math.sin(heading))
    a = aircraft(w, start, Vec2(x, y), fuel=1e6)  # never bingo in this test
    step(w, [])
    for _ in range(60):
        step(w, [])
        assert a.state == "ON_STATION"
        assert -1e-6 <= a.pos.x <= W + 1e-6 and -1e-6 <= a.pos.y <= H + 1e-6
        assert math.hypot(a.vel.x, a.vel.y) == pytest.approx(40.0)


def scenario(ticks: int = 60) -> World:
    """Orbiting, RTB and freshly launched aircraft at once."""
    w = world(RULES)
    aircraft(w, Vec2(100_000, 100_000), Vec2(103_000, 101_000))  # orbits from tick 22
    aircraft(w, Vec2(200_000, 150_000), "east-airbase", fuel=900.0)  # RTB from tick 1
    aircraft(w, node("haven"), "fob-s-w", state="LANDED", kind="RECON_UAV", fuel=14_400.0)
    run(w, ticks)
    return w


def test_snapshot_round_trips_mid_orbit_and_mid_rtb() -> None:
    w = scenario()
    assert [e.state for e in w.entities()] == ["ON_STATION", "RTB", "EN_ROUTE"]
    restored = load(save(w))
    restored.rules = w.rules
    assert state_hash(restored) == state_hash(w)
    for _ in range(300):
        step(w, [])
        step(restored, [])
    assert save(restored) == save(w)


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_air import scenario\n"
    "from nexus.core.world import state_hash; print(state_hash(scenario(400)))"
)


def test_air_state_hash_is_hash_seed_independent() -> None:
    def child(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert child("1") == child("2") == state_hash(scenario(400))


def test_an_aircraft_without_state_cannot_fly() -> None:
    w = world(hand_rules())
    w.spawn(JET, "COALITION", "COMMANDER", Vec2(0, 0), hp=100).path = [Vec2(10, 0)]
    with pytest.raises(ValueError, match="no state"):
        step(w, [])


def test_bingo_at_exact_equality_turns_back() -> None:
    """1000 m from home at 100 m/s is 10 s, + the 100 s reserve = 110 s: bingo at 110.0, not
    at 110.5."""
    w = world(hand_rules())
    at_bingo = aircraft(w, Vec2(1000, 0), state="ON_STATION", fuel=110.0)
    above = aircraft(w, Vec2(1000, 0), state="ON_STATION", fuel=110.5)
    step(w, [])
    assert (at_bingo.state, at_bingo.path) == ("RTB", ["home"])
    assert above.state == "ON_STATION"


def test_out_of_fuel_the_aircraft_is_lost() -> None:
    """No landing base, so no bingo: 1.5 s of fuel at 1 s a tick is 0.5 s after tick 1 and runs
    out on tick 2; the commander's 5-tick respawn delay starts (4 left after tick 2's countdown)."""
    w = world(hand_rules(pos={}))
    a = aircraft(w, Vec2(1000, 1000), Vec2(1000, 90_000), fuel=1.5)
    assert step(w, []) == [] and a.fuel == 0.5
    events = step(w, [])
    assert events == [
        UnitDestroyed(
            kind="UnitDestroyed",
            tick=2,
            event_seq=1,
            campaign_id=CAMPAIGN_ID,
            entity_id=a.id,
            killer_id=None,
            assist_ids=[],
            side="COALITION",
            cause=None,
        )
    ]
    assert (len(w), w.respawn_left) == (0, {CID: 4})  # its slot is free


def test_orbit_turns_clockwise_on_the_map() -> None:
    """Arriving heading east (+x), the centre is one radius toward +y (south): a right turn."""
    w = world(hand_rules())
    a = aircraft(w, Vec2(10_000, 10_000), Vec2(10_050, 10_000))
    step(w, [])
    assert a.state == "ON_STATION" and a.orbit is not None
    assert a.orbit.x == 10_050
    assert a.orbit.y == pytest.approx(10_000 + 40.0 * 120.0 / math.tau)


@pytest.mark.parametrize("fuel", [50.0, 0.5])  # below the 100 s reserve; under one tick's burn
def test_landed_at_bingo_given_a_path_stays_landed_without_burning(fuel: float) -> None:
    w = world(hand_rules())
    a = aircraft(w, Vec2(0, 0), Vec2(0, 5000), state="LANDED", fuel=fuel)
    a.last_node = "home"
    assert step(w, []) == []
    assert (a.state, a.pos, a.path, a.fuel, len(w)) == ("LANDED", Vec2(0, 0), [], fuel, 1)


def test_landing_on_the_tick_fuel_runs_out_lands() -> None:
    """No reserve: 50 m from home at 100 m/s with 0.5 s left is bingo; that tick burns the last
    0.5 s and reaches home, so it lands rather than crashes."""
    w = world(hand_rules(reserve=0.0))
    a = aircraft(w, Vec2(50, 0), state="ON_STATION", fuel=0.5)
    assert step(w, []) == []
    assert (a.state, a.pos, a.fuel, a.last_node, len(w)) == ("LANDED", Vec2(0, 0), 0.0, "home", 1)
    run(w, 5)
    assert (a.state, len(w)) == ("LANDED", 1)


def test_a_vec2_after_an_own_base_does_not_land() -> None:
    w = world(RULES)
    a = aircraft(w, Vec2(89_000, 120_000), "west-airbase", Vec2(90_100, 120_000), fuel=3600.0)
    run(w, 8)  # 1,100 m at 150 m a tick: arrives on tick 8
    assert (a.state, a.last_node, a.pos) == ("ON_STATION", "west-airbase", Vec2(90_100, 120_000))


def test_two_crashes_on_one_tick_come_in_id_order() -> None:
    w = world(hand_rules(pos={}))
    first = aircraft(w, Vec2(1000, 1000), Vec2(1000, 90_000), fuel=1.5)
    second = aircraft(w, Vec2(5000, 1000), fuel=1.5, state="ON_STATION")
    step(w, [])
    events = step(w, [])
    destroyed = [e for e in events if isinstance(e, UnitDestroyed)]
    assert destroyed == events
    assert [(e.entity_id, e.event_seq) for e in destroyed] == [(first.id, 1), (second.id, 2)]
    assert len(w) == 0


def test_join_to_its_own_base_stays_landed() -> None:
    w = world(RULES)
    step(w, [join(1, "STRIKE", "haven")])  # the sanctuary it spawns at
    run(w, 10)
    a = w.get(1)
    assert (a.state, a.pos, a.path, a.fuel) == ("LANDED", node("haven"), [], 3600.0)


def test_a_path_ending_at_an_own_base_lands_there() -> None:
    w = world(RULES)
    step(w, [join(1, "STRIKE", "west-airbase")])
    jet = w.get(1)
    run(w, 465)  # 70 km at 150 m a tick: arrives on tick 467
    assert jet.state == "EN_ROUTE"
    run(w, 1)
    assert (jet.state, jet.pos, jet.last_node, jet.vel, jet.orbit) == (
        "LANDED", node("west-airbase"), "west-airbase", Vec2(0, 0), None,
    )  # fmt: skip
