"""Q-TD-141: a retiring unit returns to the nearest base its side owns before it is removed
(THREAT-DIRECTOR §7a 143a-143e for Director units, GAMEPLAY 111a for coalition AI trucks).

strait-1 roads used here: cross-n (neutral) is one leg from fob-n-e (Static, 63 km) and one from
fob-n-w (coalition, over bridge-n, 100 km); east-airbase is the Static's landing base nearest
cross-n (100 km, static-hq 162 km). Arrival is set by hand (the unit is put on the node it drove
to, path done) except in the determinism test, which flies a jet home with real `step`s.
"""

import dataclasses

from hypothesis import given, settings
from hypothesis import strategies as st
from test_launch import DR, RULES, new_world, skip, unit, window
from test_logistics_cadence import ON, WINDOW, at
from test_tasking import AI, put
from test_tasking import new_world as board_world

from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.core.economy import guard_room
from nexus.core.step import step
from nexus.core.tasking import claim, post_job
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import Entity, Vec2, World, load, save, state_hash

FAST = dataclasses.replace(
    RULES, director=dataclasses.replace(DR, idle_retire_ticks=DR.window_ticks)
)  # due one window after it is first seen idle, so real `step`s reach it quickly
ENEMY_BASES = ("fob-n-e", "fob-s-e", "east-airbase", "static-hq", "static-rear")
COALITION_BASES = ("haven", "west-airbase", "fob-n-w", "fob-s-w")


def retired(events: list[Event]) -> list[int]:
    return [e.entity_id for e in events if isinstance(e, UnitDespawned) and e.reason == "RETIRED"]


def arrive(w: World, e: Entity, node: str) -> None:
    """The unit has driven or flown to `node` and stopped (an aircraft lands there)."""
    e.pos, e.last_node, e.path = Vec2(*RULES.roads.pos[node]), node, []
    if RULES.domain[e.kind] == "AIR":
        e.state = "LANDED"


def due(w: World) -> list[Event]:
    """Two Director windows a retirement apart: the first starts the idle clock, the second finds
    the unit due."""
    window(w, "PATTERN_OF_LIFE", 0)
    skip(w, DR.idle_retire_ticks)
    return window(w, "PATTERN_OF_LIFE", 0)


def next_window(w: World) -> list[Event]:
    skip(w, DR.window_ticks)
    return window(w, "PATTERN_OF_LIFE", 0)


# --- Director units (THREAT-DIRECTOR §7a 143a-143e) ----------------------------------------------


def test_a_due_ground_unit_out_in_the_open_drives_home_and_retires_only_on_arrival() -> None:
    w = new_world()
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    assert retired(due(w)) == []  # 143a: not removed in the open
    assert w.find(armor.id) is armor and armor.path[-1] == "fob-n-e"
    assert retired(next_window(w)) == []  # still driving: not removed
    assert str(armor.id) in w.director["ENEMY"].idle  # its return is remembered
    arrive(w, armor, "fob-n-e")
    assert retired(next_window(w)) == [armor.id]
    assert w.find(armor.id) is None and w.director["ENEMY"].idle == {}


def test_a_due_aircraft_on_station_flies_rtb_and_retires_once_landed() -> None:
    w = new_world()
    jet = unit(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    jet.state = "ON_STATION"  # orbiting over cross-n after its job
    assert retired(due(w)) == []
    assert (jet.state, jet.path) == ("RTB", ["east-airbase"])
    arrive(w, jet, "east-airbase")
    assert retired(next_window(w)) == [jet.id]


def test_a_due_unit_already_at_a_base_its_side_owns_is_removed_at_once() -> None:
    w = new_world()
    jet = unit(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "east-airbase")  # LANDED
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    assert sorted(retired(due(w))) == sorted([jet.id, armor.id])  # 143b


def test_a_returning_unit_is_live_and_a_job_ends_its_return() -> None:
    w = new_world()
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    room = guard_room(w, "ENEMY")
    due(w)
    assert armor.path and guard_room(w, "ENEMY") == room  # 143c: it still counts
    spec = JobSpec("DEFEND", "op:test:fob-n-e:0", 1, DR.job_urgency_milli, node="fob-n-e")
    claim(w, armor, post_job(w, "ENEMY", spec, []), [])  # a later operation reuses it
    arrive(w, armor, "fob-n-e")
    assert retired(next_window(w)) == []  # its return ended: not retired on arrival
    assert str(armor.id) not in w.director["ENEMY"].idle


def test_a_returning_unit_killed_on_the_way_is_no_retirement() -> None:
    w = new_world()
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    due(w)
    w.remove(armor.id)  # destroyed on the road (combat reports it; not this test's concern)
    assert retired(next_window(w)) == [] and w.director["ENEMY"].idle == {}


def test_a_due_unit_with_no_base_to_reach_stays_and_is_tried_each_window() -> None:
    w = new_world()
    for node in ENEMY_BASES:
        w.owner[node] = "COALITION"
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    first = w.campaign.running_ticks + 1
    assert retired(due(w)) == []
    assert armor.path == [] and w.find(armor.id) is armor  # 143d: it stays
    assert retired(next_window(w)) == [] and armor.path == []
    assert w.director["ENEMY"].idle == {str(armor.id): first}  # still due
    w.owner["fob-n-e"] = "ENEMY"  # a base to go to again
    assert retired(next_window(w)) == []
    assert armor.path[-1] == "fob-n-e"  # tried again at the next window


def off_node(w: World, node: str, toward: str, metres: float) -> Entity:
    """Director armor whose `last_node` is `node`, stopped `metres` along the road to `toward`."""
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", node)
    (ax, ay), (bx, by) = RULES.roads.pos[node], RULES.roads.pos[toward]
    k = metres / ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    armor.pos = Vec2(ax + (bx - ax) * k, ay + (by - ay) * k)
    return armor


def test_a_due_aircraft_airborne_over_its_base_is_not_removed_and_flies_rtb() -> None:
    """`last_node` is its own airbase, but it is in the air 5 km off it: not at a base (143a)."""
    w = new_world()
    jet = unit(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "east-airbase")
    x, y = RULES.roads.pos["east-airbase"]
    jet.state, jet.pos = "ON_STATION", Vec2(x - 5_000.0, y)
    assert retired(due(w)) == [] and w.find(jet.id) is jet
    assert (jet.state, jet.path) == ("RTB", ["east-airbase"])


def test_a_due_ground_unit_stopped_off_its_own_base_node_drives_onto_it_then_retires() -> None:
    """`last_node` is fob-n-e (Static) but it stands 1 km down the road: not at a base, and
    `go_home` sends it back onto the node instead of leaving it there for good."""
    w = new_world()
    armor = off_node(w, "fob-n-e", "cross-n", 1_000.0)
    assert retired(due(w)) == [] and w.find(armor.id) is armor
    assert armor.path == ["fob-n-e"]
    arrive(w, armor, "fob-n-e")
    assert retired(next_window(w)) == [armor.id]


def test_a_moving_returner_keeps_its_entry_from_exactly_due_but_not_a_tick_before() -> None:
    w = new_world()
    now = w.campaign.running_ticks + 1  # the tick the hand-run window counts as `now`
    exact = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    early = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    for e in (exact, early):
        e.path = ["fob-n-e"]  # driving, no job: free but not idle
    s = w.director["ENEMY"]
    s.idle = {
        str(exact.id): now - DR.idle_retire_ticks,
        str(early.id): now - DR.idle_retire_ticks + 1,
    }
    assert retired(window(w, "PATTERN_OF_LIFE", 0)) == []
    assert s.idle == {str(exact.id): now - DR.idle_retire_ticks}  # due: its return is kept


def test_a_return_survives_a_snapshot_and_retires_at_the_first_window_there() -> None:
    w = new_world(3, FAST)
    armor = off_node(w, "fob-n-e", "cross-n", 1_000.0)
    for _ in range(3 * DR.window_ticks):  # due at the second window: sent home
        step(w, [])
        if armor.path:
            break
    w = load(save(w))
    w.rules = FAST  # static config: a snapshot carries none (recovery re-attaches it)
    armor = w.get(armor.id)
    assert armor.path == ["fob-n-e"] and str(armor.id) in w.director["ENEMY"].idle
    arrived: int | None = None
    events: list[Event] = []
    for _ in range(3 * DR.window_ticks):
        events += step(w, [])
        if arrived is None and w.find(armor.id) is not None and not armor.path:
            arrived = w.campaign.tick
    assert arrived is not None
    (gone,) = [e for e in events if isinstance(e, UnitDespawned)]
    assert (gone.entity_id, gone.reason) == (armor.id, "RETIRED")
    assert gone.tick == (arrived // DR.window_ticks + 1) * DR.window_ticks  # the next window


NODES = sorted(n for n, kind in RULES.node_kind.items() if kind != "BRIDGE")


@settings(max_examples=40, deadline=None)
@given(st.sampled_from(NODES), st.sets(st.sampled_from(ENEMY_BASES)))
def test_a_due_unit_is_removed_only_at_an_own_base_and_returns_only_to_one(
    node: str, lost: set[str]
) -> None:
    w = new_world()
    for base in sorted(lost):
        w.owner[base] = "COALITION"
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", node)
    gone = retired(due(w))
    if gone:
        assert gone == [armor.id] and w.owner.get(node) == "ENEMY"
    else:
        assert w.owner.get(node) != "ENEMY" and w.find(armor.id) is armor
        assert not armor.path or w.owner.get(str(armor.path[-1])) == "ENEMY"


def test_the_return_path_is_deterministic() -> None:
    """Same seed, same setup -> same events and state hash, through a real flight home: a jet
    10 km west of east-airbase, due after one window, flies RTB, lands and retires."""

    def run() -> tuple[str, list[Event], int]:
        w = new_world(7, FAST)
        jet = unit(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "east-airbase")
        x, y = RULES.roads.pos["east-airbase"]
        jet.pos, jet.state, jet.last_node = Vec2(x - 10_000.0, y), "ON_STATION", None
        events: list[Event] = []
        states: set[str | None] = set()
        for _ in range(4 * DR.window_ticks):
            events += step(w, [])
            states.add(jet.state)
        assert "RTB" in states and retired(events) == [jet.id]  # it flew home, then retired
        return state_hash(w), events, jet.id

    assert run() == run()


# --- coalition AI trucks (GAMEPLAY 111a) ---------------------------------------------------------


def truck_due(w: World) -> list[Event]:
    at(w, WINDOW)
    return at(w, WINDOW + DR.idle_retire_ticks)


def test_a_due_ai_truck_out_in_the_open_drives_home_and_retires_only_on_arrival() -> None:
    w = board_world(rules=ON)
    truck = put(w, "LOGI_TRUCK", "cross-n", AI)
    assert retired(truck_due(w)) == []
    assert truck.path[-1] == "fob-n-w"
    arrive(w, truck, "fob-n-w")
    assert retired(at(w, WINDOW + DR.idle_retire_ticks + WINDOW)) == [truck.id]
    assert w.director["COALITION"].idle == {}


def test_an_ai_truck_driving_home_keeps_its_idle_entry() -> None:
    w = board_world(rules=ON)
    truck = put(w, "LOGI_TRUCK", "cross-n", AI)
    truck_due(w)
    assert retired(at(w, WINDOW + DR.idle_retire_ticks + WINDOW)) == [] and truck.path
    assert str(truck.id) in w.director["COALITION"].idle  # still on its way: the return is kept


def test_a_due_ai_truck_with_no_base_to_reach_stays_and_is_tried_each_window() -> None:
    w = board_world(rules=ON)
    for node in COALITION_BASES:
        w.owner[node] = "ENEMY"
    truck = put(w, "LOGI_TRUCK", "cross-n", AI)
    assert retired(truck_due(w)) == [] and truck.path == []
    later = WINDOW + DR.idle_retire_ticks + WINDOW
    assert retired(at(w, later)) == [] and truck.path == []
    w.owner["fob-n-w"] = "COALITION"
    assert retired(at(w, later + WINDOW)) == [] and truck.path[-1] == "fob-n-w"
