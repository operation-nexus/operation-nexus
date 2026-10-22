"""NX-125: capture with contest and decay, live node ownership and what a flip does (GAMEPLAY §8,
§9; STATE-MACHINES §4.2 N-1..N-5; FOG-OF-WAR FOW-10, FOW-13; Q-SIM-56, Q-SIM-57).

Shipped strait-1 numbers: `capture.radius_m` 2000, `time_s` 120, exponent 0.5, `quiet_floor` 0.6
(`quiet_ref` 50), `min_time_s` 30, `logi_weight` 0.5, garrison x3, empty x0.5, decay 1/120 of the
bar per world s; 0.6 world s per tick, so one tick adds `round(1e8 x 0.6 / time)` millionths of a
percent and decays 500,000. cross-n is a NEUTRAL FOB with no facility; fob-n-e is an ENEMY FOB with
one (ad-fob-n-e); static-rear and the bridges can never be captured.
"""

import dataclasses
import math
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nexus.contracts.gen.common.enums import NodeOwner, Side, UnitKind
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core.fog import side_view
from nexus.core.logistics import friendly, plan_deploy
from nexus.core.rules import CAPTURE_FULL
from nexus.core.step import step
from nexus.core.world import CaptureBar, Contact, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config, start_campaign

RULES = dataclasses.replace(  # NX-374: board off; no opening garrison (Q-SIM-86)
    load_campaign_config().rules, tasking=None, garrison_quota={}
)
CONFIG = dataclasses.replace(load_campaign_config(), rules=RULES)
POS = RULES.roads.pos
CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
NEUTRAL_FOB = "cross-n"
ENEMY_FOB = "fob-n-e"
INFANTRY: UnitKind = "GARRISON_INFANTRY"  # armed, coalition
ARMOR: UnitKind = "ENEMY_ARMOR"  # armed, enemy
TRUCK: UnitKind = "LOGI_TRUCK"  # unarmed, coalition
CONVOY: UnitKind = "ENEMY_CONVOY"  # unarmed, enemy
DECAY = 500_000
NEAR = FULL_MINUS_1 = CAPTURE_FULL - 1


def cid(n: int) -> str:
    return f"0192f0c1-7a2b-7c3d-8e4f-{n:012d}"


def new_world() -> World:
    """A strait-1 campaign with every node's defenses down: these tests are about the capture bar;
    the defense HP gate is tested in `test_defense.py`."""
    w = start_campaign(CAMPAIGN_ID, 12345, CONFIG)
    w.defense_hp = dict.fromkeys(w.defense_hp, 0)
    return w


def put(
    w: World,
    kind: UnitKind,
    side: Side,
    node: str,
    *,
    n: int | None = None,
    dx: float = 0.0,
    state: Any = None,
) -> Entity:
    """A unit standing at `node` (`dx` metres east); `n` makes it a commander's."""
    e = w.spawn(
        kind,
        side,
        "AI_GARRISON" if n is None else "COMMANDER",
        Vec2(POS[node][0] + dx, POS[node][1]),
        commander_id=None if n is None else cid(n),
    )
    e.last_node = node
    if state:
        e.state, e.fuel = state, RULES.fuel_s[kind]
    return e


def run(w: World, ticks: int = 1) -> list[Event]:
    events: list[Event] = []
    for _ in range(ticks):
        events += step(w, [])
    return events


def progress(w: World, node: str = NEUTRAL_FOB) -> int:
    return w.capture[node].progress if node in w.capture else 0


def gain(w: World, node: str = NEUTRAL_FOB) -> int:
    """What one more tick adds to the bar of `node`."""
    before = progress(w, node)
    run(w)
    return progress(w, node) - before


def per_tick(time_s: float) -> int:
    return round(CAPTURE_FULL * 0.6 / time_s)


def of[T: Event](events: list[Event], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


# --- the table rows -------------------------------------------------------------------------


def test_live_owners_start_from_the_theater_and_the_sanctuaries_are_never_capture_targets() -> None:
    w = new_world()
    assert w.owner == RULES.supply.start_owner and w.owner["cross-n"] == "NEUTRAL"
    for node in ("static-rear", "haven", "bridge-n", "bridge-s"):
        side: Side = "COALITION" if node in ("haven", "bridge-n", "bridge-s") else "ENEMY"
        other: Side = "ENEMY" if side == "COALITION" else "COALITION"
        before = w.owner[node]
        put(w, TRUCK if other == "COALITION" else CONVOY, other, node)
        put(w, INFANTRY if other == "COALITION" else ARMOR, other, node)
        run(w, 400)
        assert (w.owner[node], node in w.capture) == (before, False)


def test_a_capture_starts_once_and_fills_at_the_quiet_stream_rate() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    events = run(w)
    (started,) = of(events, CaptureStarted)
    assert (started.node_id, started.side, started.tick) == (NEUTRAL_FOB, "COALITION", 1)
    # v = 0: quiet_mult 0.6, one capturer: 120 x 0.6 = 72 world s.
    assert w.capture[NEUTRAL_FOB] == CaptureBar("COALITION", per_tick(72.0))
    assert per_tick(72.0) == 833_333
    assert of(run(w), CaptureStarted) == []  # not again while it fills


def test_the_flip_lands_on_the_first_tick_the_bar_reaches_full_and_never_twice() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    run(w, 120)
    assert w.owner[NEUTRAL_FOB] == "NEUTRAL" and progress(w) == 120 * 833_333 < CAPTURE_FULL
    events = run(w)  # tick 121: 121 x 833,333 = 100,833,293 >= 1e8
    (captured,) = of(events, NodeCaptured)
    assert (captured.from_, captured.to, captured.tick) == ("NEUTRAL", "COALITION", 121)
    assert captured.participant_commander_ids == []  # an AI unit has no commander
    assert w.owner[NEUTRAL_FOB] == "COALITION" and NEUTRAL_FOB not in w.capture
    assert w.lost == {}  # taking a neutral node loses nobody anything
    assert of(run(w, 50), NodeCaptured) == []  # an owner is never a capturer


@pytest.mark.parametrize(
    ("units", "time_s"),
    [
        ([INFANTRY] * 4, 72.0 / 2),  # diminishing returns: n ** 0.5
        ([INFANTRY, TRUCK], 72.0 / 1.5**0.5),  # a logistics unit counts as half (Q-SM-7)
        ([INFANTRY] * 16, 30.0),  # 72 / 4 = 18 s, floored at min_time_s
    ],
)
def test_rate_scales_with_weighted_units_and_is_floored(
    units: list[UnitKind], time_s: float
) -> None:
    w = new_world()
    for kind in units:
        put(w, kind, "COALITION", NEUTRAL_FOB)
    run(w)
    assert progress(w) == per_tick(time_s)


def test_the_quiet_multiplier_is_linear_in_viewer_units_and_for_the_coalition_only() -> None:
    w = new_world()
    for i in range(25):  # 25 live commander units far from any node: v = 25, quiet 0.8
        put(w, INFANTRY, "COALITION", "haven", n=100 + i)
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    assert gain(w) == per_tick(96.0)
    w2 = new_world()
    for i in range(60):  # above quiet_ref: 1.0
        put(w2, INFANTRY, "COALITION", "haven", n=100 + i)
    put(w2, INFANTRY, "COALITION", NEUTRAL_FOB)
    assert gain(w2) == per_tick(120.0)
    w3 = new_world()  # v = 0 but the enemy has no quiet-stream bonus (Q-SIM-26)
    put(w3, ARMOR, "ENEMY", NEUTRAL_FOB)
    assert gain(w3) == per_tick(120.0)


def test_a_unit_outside_the_radius_does_not_count_and_the_edge_does() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB, dx=2000.5)
    run(w)
    assert NEUTRAL_FOB not in w.capture
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB, dx=2000.0)
    run(w)
    assert NEUTRAL_FOB in w.capture


def test_air_never_captures_and_facilities_never_count() -> None:
    w = new_world()
    flying = put(w, "STRIKE_FIGHTER", "COALITION", NEUTRAL_FOB, state="EN_ROUTE")
    flying.path = [Vec2(0.0, 0.0)]
    put(w, "STRIKE_FIGHTER", "COALITION", NEUTRAL_FOB, state="LANDED")
    run(w, 5)
    assert NEUTRAL_FOB not in w.capture and w.owner[NEUTRAL_FOB] == "NEUTRAL"
    # A facility on the attacker's side near the node adds no capturer.
    site = put(w, "AIR_DEFENSE_SITE", "COALITION", NEUTRAL_FOB)
    site.base_id = "west-airbase"
    run(w, 5)
    assert NEUTRAL_FOB not in w.capture


def test_decay_empties_the_bar_and_keeps_the_owner() -> None:
    w = new_world()
    w.capture[NEUTRAL_FOB] = CaptureBar("COALITION", 1_200_000)
    assert [gain(w) for _ in range(2)] == [-DECAY, -DECAY]
    run(w)
    assert NEUTRAL_FOB not in w.capture and w.owner[NEUTRAL_FOB] == "NEUTRAL"
    w.capture[ENEMY_FOB] = CaptureBar("COALITION", 700_000)
    run(w, 2)
    assert ENEMY_FOB not in w.capture and w.owner[ENEMY_FOB] == "ENEMY"


def test_a_capturer_returning_stops_the_decay_and_the_bar_fills_again() -> None:
    w = new_world()
    w.capture[NEUTRAL_FOB] = CaptureBar("COALITION", 5_000_000)
    run(w, 2)
    assert progress(w) == 4_000_000
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    assert gain(w) == per_tick(72.0)


def test_an_opposing_combat_unit_makes_the_bar_decay_not_freeze() -> None:
    """Owner, 2026-10-21, Q-SIM-23: a contested bar drains at the abandoned rate."""
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    run(w, 3)
    start = progress(w)
    armor = put(w, ARMOR, "ENEMY", NEUTRAL_FOB)
    assert [gain(w) for _ in range(2)] == [-DECAY, -DECAY]
    assert of(run(w), NodeCaptured) == [] and progress(w) == start - 3 * DECAY
    w.remove(armor.id)  # the opposing side is gone, the attacker remains: Capturing again
    assert gain(w) == per_tick(72.0)


def test_an_armed_side_facing_only_unarmed_units_starts_its_own_bar_once_theirs_is_gone() -> None:
    w = new_world()
    w.capture[NEUTRAL_FOB] = CaptureBar("COALITION", 1_200_000)
    put(w, TRUCK, "COALITION", NEUTRAL_FOB)  # an unarmed capturer cannot block the node for ever
    put(w, ARMOR, "ENEMY", NEUTRAL_FOB)
    run(w, 3)
    assert NEUTRAL_FOB not in w.capture
    events = run(w)
    assert w.capture[NEUTRAL_FOB].side == "ENEMY" and len(of(events, CaptureStarted)) == 1


def test_sixty_infantry_against_an_empty_base_never_flip_faster_than_min_time() -> None:
    w = new_world()
    for _ in range(60):
        put(w, INFANTRY, "COALITION", ENEMY_FOB)
    # 72 / sqrt(60) = 9.3 s, x0.5 empty = 4.6 s: the 30 s floor applies after the modifier.
    ticks = 0
    while not of(run(w), NodeCaptured):
        ticks += 1
        assert ticks < 500
    assert progress(w, ENEMY_FOB) == 0 and ticks + 1 == math.ceil(CAPTURE_FULL / per_tick(30.0))


def test_attackers_gone_while_the_defender_holds_the_bar_drains() -> None:
    w = new_world()
    w.capture[ENEMY_FOB] = CaptureBar("COALITION", 3_000_000)
    put(w, ARMOR, "ENEMY", ENEMY_FOB)  # a combat-capable defender, no attacker in radius
    assert [gain(w, ENEMY_FOB) for _ in range(2)] == [-DECAY, -DECAY]


def test_a_defender_who_can_contest_keeps_an_owned_node_from_starting_a_bar() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    put(w, ARMOR, "ENEMY", ENEMY_FOB)
    run(w, 5)
    assert ENEMY_FOB not in w.capture  # contested before it began: nothing starts


def test_two_sides_at_a_neutral_node_follow_the_table() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    put(w, ARMOR, "ENEMY", NEUTRAL_FOB)
    run(w, 5)
    assert NEUTRAL_FOB not in w.capture  # both blocked: neither starts
    w2 = new_world()
    put(w2, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w2, CONVOY, "ENEMY", NEUTRAL_FOB)
    run(w2, 5)
    assert NEUTRAL_FOB not in w2.capture  # two free sides, equal weight: neither starts
    w3 = new_world()
    put(w3, INFANTRY, "COALITION", NEUTRAL_FOB)
    put(w3, CONVOY, "ENEMY", NEUTRAL_FOB)  # the convoy cannot block: the infantry fills the bar
    run(w3, 2)
    assert w3.capture[NEUTRAL_FOB].side == "COALITION"


def test_unarmed_sides_at_a_neutral_node_the_heavier_starts_the_bar() -> None:
    w = new_world()  # two trucks (1.0) against one truck (0.5)
    put(w, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w, CONVOY, "ENEMY", NEUTRAL_FOB)
    assert len(of(run(w), CaptureStarted)) == 1 and w.capture[NEUTRAL_FOB].side == "COALITION"
    w2 = new_world()  # two trucks (1.0) against three convoys (1.5): the other side wins
    put(w2, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w2, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w2, CONVOY, "ENEMY", NEUTRAL_FOB)
    put(w2, CONVOY, "ENEMY", NEUTRAL_FOB)
    put(w2, CONVOY, "ENEMY", NEUTRAL_FOB)
    run(w2)
    assert w2.capture[NEUTRAL_FOB].side == "ENEMY"  # 1.5 beats 1.0


def test_a_started_unarmed_bar_fills_while_the_other_side_stays() -> None:
    w = new_world()
    put(w, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w, TRUCK, "COALITION", NEUTRAL_FOB)
    put(w, CONVOY, "ENEMY", NEUTRAL_FOB)
    run(w)
    first = progress(w)
    assert first > 0 and gain(w) > 0 and w.capture[NEUTRAL_FOB].side == "COALITION"
    assert len(of(run(w, 400), NodeCaptured)) == 1 and w.owner[NEUTRAL_FOB] == "COALITION"


def test_a_bar_of_one_side_drains_before_the_other_side_starts() -> None:
    w = new_world()
    w.capture[NEUTRAL_FOB] = CaptureBar("COALITION", 1_000_000)
    put(w, ARMOR, "ENEMY", NEUTRAL_FOB)
    run(w, 2)
    assert NEUTRAL_FOB not in w.capture  # the coalition bar drained to 0 and was removed
    run(w)
    assert w.capture[NEUTRAL_FOB].side == "ENEMY"


def test_empty_and_garrison_modifiers_apply_at_an_owned_node_only() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    # No enemy unit here (its facility does not count, Q-GP-38): x0.5, 36 s.
    assert gain(w, ENEMY_FOB) == per_tick(36.0)
    garrisoned = new_world()
    put(garrisoned, INFANTRY, "COALITION", ENEMY_FOB)
    put(garrisoned, CONVOY, "ENEMY", ENEMY_FOB)  # unarmed: cannot contest
    assert gain(garrisoned, ENEMY_FOB) == per_tick(216.0)
    parked = new_world()
    put(parked, INFANTRY, "COALITION", ENEMY_FOB)
    put(parked, "ENEMY_FIGHTER", "ENEMY", ENEMY_FOB, state="LANDED")
    assert gain(parked, ENEMY_FOB) == per_tick(216.0)
    assert gain(w, ENEMY_FOB) == per_tick(36.0)  # the neutral node uses neither (above: 72)


def test_n5_a_defender_that_cannot_contest_slows_capture_and_one_that_can_stops_it() -> None:
    empty, garrisoned, armed = new_world(), new_world(), new_world()
    for w in (empty, garrisoned, armed):
        put(w, INFANTRY, "COALITION", ENEMY_FOB)
    put(garrisoned, CONVOY, "ENEMY", ENEMY_FOB)
    put(armed, ARMOR, "ENEMY", ENEMY_FOB)
    rates = [gain(w, ENEMY_FOB) for w in (empty, garrisoned, armed)]
    assert rates[0] > rates[1] > rates[2] == 0


def test_a_disabled_defender_does_not_contest_and_counts_for_the_garrison() -> None:
    # Q-ALN-33: a wreck cannot contest, so it applies the garrison multiplier (x3), like an
    # unarmed unit, instead of freezing the bar as a healthy ARMOR does (NX-124).
    wreck_w, convoy_w = new_world(), new_world()
    for w in (wreck_w, convoy_w):
        put(w, INFANTRY, "COALITION", ENEMY_FOB)
    wreck = put(wreck_w, ARMOR, "ENEMY", ENEMY_FOB)
    wreck.hp, wreck.damage_state, wreck.wreck_left = 5, "DISABLED", 10_000
    put(convoy_w, CONVOY, "ENEMY", ENEMY_FOB)
    assert gain(wreck_w, ENEMY_FOB) == gain(convoy_w, ENEMY_FOB) > 0


def test_a_disabled_unit_cannot_escape_a_flipped_base() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    wreck = put(w, ARMOR, "ENEMY", ENEMY_FOB)  # its base is about to flip
    wreck.hp, wreck.damage_state, wreck.wreck_left = 5, "DISABLED", 10_000
    healthy = put(w, CONVOY, "ENEMY", ENEMY_FOB)
    w.capture[ENEMY_FOB] = CaptureBar("COALITION", CAPTURE_FULL - 1)
    events = run(w)
    lost = {e.entity_id for e in of(events, UnitDestroyed)}
    assert lost == {wreck.id} and w.get(healthy.id).path  # the wreck dies; the convoy drives off


def test_the_garrison_must_be_at_the_base() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    put(w, CONVOY, "ENEMY", ENEMY_FOB, dx=2001.0)  # just outside: the base is empty
    assert gain(w, ENEMY_FOB) == per_tick(36.0)


def test_pause_freezes_capture() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    run(w, 3)
    before = state_hash(w)
    w.campaign.clock_paused = True
    ticks = w.campaign.tick
    run(w, 10)
    assert progress(w) == 3 * 833_333 and w.campaign.tick == ticks + 10
    w.campaign.clock_paused = False
    assert before != state_hash(w)  # only the tick moved
    assert gain(w) == 833_333


# --- the flip --------------------------------------------------------------------------------


def about_to_flip(w: World, node: str, side: Side) -> None:
    w.capture[node] = CaptureBar(side, NEAR)


def test_a_flip_switches_the_nodes_facilities_keeping_damage_and_keeps_the_stock() -> None:
    w = new_world()
    site = next(e for e in w.entities() if e.base_id == ENEMY_FOB)
    site.hp = 77
    stock = w.stock[ENEMY_FOB]
    about_to_flip(w, ENEMY_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    (captured,) = of(run(w), NodeCaptured)
    assert (captured.from_, captured.to) == ("ENEMY", "COALITION")
    assert w.lost == {ENEMY_FOB: 1}  # the Static lost it on running tick 1 (counterattack window)
    assert (site.side, site.hp, site.owner_kind) == ("COALITION", 77, "AI_GARRISON")
    other = next(e for e in w.entities() if e.base_id == "fob-s-e")
    assert other.side == "ENEMY"  # another base's facility is untouched
    assert w.stock[ENEMY_FOB] == stock  # the stock belongs to the base (Q-SIM-56)


def test_participants_are_the_capturing_commanders_sorted_and_deduplicated() -> None:
    w = new_world()
    about_to_flip(w, NEUTRAL_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB, n=3)
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB, n=1)
    put(w, TRUCK, "COALITION", NEUTRAL_FOB, n=3)
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)  # an AI unit has no commander
    far = put(w, INFANTRY, "COALITION", NEUTRAL_FOB, n=9, dx=5000.0)
    (captured,) = of(run(w), NodeCaptured)
    assert captured.participant_commander_ids == [cid(1), cid(3)] and far.id in {
        e.id for e in w.entities()
    }


def test_ground_units_of_the_loser_take_the_road_to_the_nearest_friendly_base_cargo_aboard() -> (
    None
):
    w = new_world()
    convoy = put(w, CONVOY, "ENEMY", ENEMY_FOB)
    convoy.cargo = 50
    about_to_flip(w, ENEMY_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    events = run(w)
    assert of(events, UnitDestroyed) == [] and convoy.cargo == 50
    # static-hq (a friendly base) is the nearest by road; the unit leaves from where it stands.
    assert convoy.path == [ENEMY_FOB, "static-hq"]


def test_a_unit_on_the_road_continues_to_the_node_it_is_heading_for() -> None:
    w = new_world()
    convoy = put(w, CONVOY, "ENEMY", ENEMY_FOB, dx=1000.0)
    convoy.path = ["static-hq"]
    about_to_flip(w, ENEMY_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    run(w)
    assert convoy.path[0] == "static-hq" and convoy.last_node == ENEMY_FOB


def test_an_unloading_truck_ends_its_stop_when_it_leaves_the_flipped_node() -> None:
    w = new_world()
    convoy = put(w, CONVOY, "ENEMY", ENEMY_FOB)
    convoy.cargo, convoy.delivered = 50, 4
    about_to_flip(w, ENEMY_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    events = run(w)
    assert [(e.node_id, e.amount) for e in of(events, SupplyDelivered)] == [(ENEMY_FOB, 4)]
    assert convoy.delivered == 0


def lose_all_other_bases(w: World, side: Side, keep: str) -> None:
    for node, owner in list(w.owner.items()):
        if owner == side and node != keep:
            w.owner[node] = "NEUTRAL"


def test_ground_units_with_no_road_to_a_friendly_base_are_lost_with_a_respawn_delay() -> None:
    w = new_world()
    about_to_flip(w, "fob-n-w", "ENEMY")
    lose_all_other_bases(w, "COALITION", "fob-n-w")
    mine = put(w, TRUCK, "COALITION", "fob-n-w", n=7)
    put(w, ARMOR, "ENEMY", "fob-n-w")
    events = run(w)
    (captured, destroyed) = [e for e in events if isinstance(e, NodeCaptured | UnitDestroyed)]
    assert isinstance(captured, NodeCaptured) and isinstance(destroyed, UnitDestroyed)
    assert (destroyed.entity_id, destroyed.killer_id, destroyed.assist_ids, destroyed.side) == (
        mine.id,
        None,
        [],
        "COALITION",
    )
    assert mine.id not in {e.id for e in w.entities()}
    assert w.respawn_left[cid(7)] == RULES.respawn_delay_ticks - 1  # lifecycle counted one down


def test_a_landed_aircraft_with_fuel_takes_off_rtb_to_the_nearest_base_it_still_owns() -> None:
    w = new_world()
    about_to_flip(w, "west-airbase", "ENEMY")
    jet = put(w, "STRIKE_FIGHTER", "COALITION", "west-airbase", state="LANDED")
    put(w, ARMOR, "ENEMY", "west-airbase")
    put(w, INFANTRY, "COALITION", "haven", n=9)  # someone plays: no idle floor on west-airbase
    assert of(run(w), UnitDestroyed) == []
    assert (jet.state, jet.path) == ("RTB", ["haven"])
    assert w.landing_bases("COALITION") == ("haven",)


def test_an_aircraft_that_cannot_reach_a_base_is_lost() -> None:
    w = new_world()
    about_to_flip(w, "west-airbase", "ENEMY")
    short = put(w, "STRIKE_FIGHTER", "COALITION", "west-airbase", n=2, state="LANDED")
    short.fuel = 1.0  # haven is 70 km away: 280 s at 250 m/s
    put(w, ARMOR, "ENEMY", "west-airbase")
    put(w, INFANTRY, "COALITION", "haven", n=9)  # someone plays: no idle floor
    (destroyed,) = of(run(w), UnitDestroyed)
    assert destroyed.entity_id == short.id and cid(2) in w.respawn_left
    w2 = new_world()
    about_to_flip(w2, "west-airbase", "ENEMY")
    w2.owner["haven"] = "ENEMY"  # not reachable by rule in play; no base left
    stuck = put(w2, "STRIKE_FIGHTER", "COALITION", "west-airbase", state="LANDED")
    put(w2, ARMOR, "ENEMY", "west-airbase")
    put(w2, INFANTRY, "COALITION", "haven", n=9)  # someone plays: no idle floor
    assert [e.entity_id for e in of(run(w2), UnitDestroyed)] == [stuck.id]


def test_an_rtb_aircraft_whose_base_was_captured_retargets_at_once() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "COALITION", "west-airbase", dx=60_000.0, state="RTB")
    jet.path, jet.vel, jet.fuel = ["west-airbase"], Vec2(-250.0, 0.0), 300.0  # just enough for it
    w.owner["west-airbase"] = "ENEMY"  # flipped (the capture slot comes after movement)
    run(w)
    assert (jet.state, jet.path) == ("RTB", ["haven"])
    w.owner["haven"] = "ENEMY"  # no base left: it flies on to the one it had
    jet.path = ["haven"]
    run(w)
    assert jet.path == ["haven"]


def test_an_airborne_aircraft_over_the_node_is_not_at_the_base() -> None:
    w = new_world()
    about_to_flip(w, "west-airbase", "ENEMY")
    jet = put(w, "STRIKE_FIGHTER", "COALITION", "west-airbase", state="ON_STATION")
    put(w, INFANTRY, "COALITION", "haven", n=9)  # someone plays: no idle floor
    jet.orbit = jet.pos
    put(w, ARMOR, "ENEMY", "west-airbase")
    assert of(run(w), UnitDestroyed) == [] and jet.state != "RTB"


def test_a_flip_from_neutral_resolves_no_units() -> None:
    w = new_world()
    about_to_flip(w, NEUTRAL_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    stray = put(w, CONVOY, "ENEMY", NEUTRAL_FOB)
    assert of(run(w), UnitDestroyed) == [] and stray.path == []


# --- live ownership elsewhere ----------------------------------------------------------------


def test_logistics_sources_and_diverts_follow_the_live_owner() -> None:
    w = new_world()
    assert not friendly(w, "COALITION", NEUTRAL_FOB)
    w.owner[NEUTRAL_FOB] = "COALITION"
    assert friendly(w, "COALITION", NEUTRAL_FOB)
    truck = put(w, TRUCK, "COALITION", NEUTRAL_FOB)
    truck.cargo = 10
    run(w, 40)  # it is a friendly node now: it unloads rather than drives off
    assert (truck.path, w.stock[NEUTRAL_FOB]) == ([], 10) and truck.cargo == 0
    w.owner[NEUTRAL_FOB] = "ENEMY"
    again = put(w, TRUCK, "COALITION", NEUTRAL_FOB)
    again.cargo = 10
    run(w)
    assert (
        again.path and again.path[0] == NEUTRAL_FOB
    )  # a hostile node: it drives to a friendly base


def test_a_captured_airbase_is_a_landing_base_and_a_forward_deploy_site() -> None:
    w = new_world()
    assert w.landing_bases("COALITION") == ("haven", "west-airbase")
    w.owner["east-airbase"] = "COALITION"
    assert w.landing_bases("COALITION") == ("east-airbase", "haven", "west-airbase")
    assert w.landing_bases("ENEMY") == ("static-rear",)
    assert plan_deploy(w, RULES, "COALITION", "STRIKE_FIGHTER", "static-hq") == (
        "east-airbase",
        ["static-hq"],
    )
    jet = put(w, "STRIKE_FIGHTER", "COALITION", "east-airbase", state="LANDED")
    jet.fuel = 100.0
    run(w, 5)
    assert jet.fuel > 100.0 and w.stock["east-airbase"] < 1000  # it refuels at the captured base
    far = put(w, "STRIKE_FIGHTER", "COALITION", "static-hq", state="ON_STATION")
    far.orbit, far.fuel = far.pos, 100.0
    run(w)
    assert (far.state, far.path) == ("RTB", ["east-airbase"])  # bingo: the nearest base it owns


# --- fog -------------------------------------------------------------------------------------


def test_side_view_carries_a_copy_of_every_nodes_owner() -> None:
    w = new_world()
    view = side_view(w, "COALITION")
    assert dict(view.owners) == w.owner
    w.owner[NEUTRAL_FOB] = "ENEMY"
    assert (
        view.owners[NEUTRAL_FOB] == "NEUTRAL"
        and side_view(w, "ENEMY").owners[NEUTRAL_FOB] == "ENEMY"
    )


def test_a_flip_moves_the_facilitys_contact_and_marker_between_sides() -> None:
    w = new_world()
    site = next(e for e in w.entities() if e.base_id == ENEMY_FOB)
    w.contacts["COALITION"][site.id] = Contact(site.kind, site.pos, site.vel)
    w.markers["COALITION"][site.id] = dataclasses.replace(side_marker(site), confirmed_tick=0)
    about_to_flip(w, ENEMY_FOB, "COALITION")
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    run(w)
    assert site.id not in w.contacts["COALITION"] and site.id not in w.markers["COALITION"]
    lost = w.markers["ENEMY"][site.id]  # the enemy keeps the site it lost, as of the flip tick
    assert (lost.kind, lost.variant, lost.pos, lost.confirmed_tick) == (
        site.kind,
        site.variant,
        site.pos,
        1,
    )
    assert list(w.markers["ENEMY"]) == sorted(w.markers["ENEMY"])
    reloaded = load(save(w))  # the views stay valid for the loader (enemy markers of own-side...)
    assert reloaded.markers["ENEMY"] == w.markers["ENEMY"]


def side_marker(site: Entity) -> Any:
    from nexus.core.world import FacilityMarker

    return FacilityMarker(
        site.kind, site.variant, site.pos, site.emitting, 0, None, site.damage_state
    )


# --- properties, snapshot, determinism ---------------------------------------------------------

NODES = sorted(n for n in POS if n not in ("bridge-n", "bridge-s"))
UNIT = st.tuples(
    st.sampled_from([INFANTRY, TRUCK, ARMOR, CONVOY]), st.sampled_from(NODES), st.booleans()
)
ACTIONS = st.one_of(
    st.tuples(st.just("put"), UNIT),
    st.tuples(st.just("bar"), st.sampled_from(NODES), st.sampled_from(["COALITION", "ENEMY"]),
              st.integers(CAPTURE_FULL - 3_000_000, CAPTURE_FULL - 1)),
    st.tuples(st.just("drop"), st.integers(0, 40)),
    st.tuples(st.just("steps"), st.integers(1, 30)),
)  # fmt: skip


def apply(w: World, action: tuple[Any, ...]) -> int:
    """Run one action; returns how many flips it saw."""
    kind, flips = action[0], 0
    if kind == "put":
        unit, node, _ = action[1]
        put(w, unit, "ENEMY" if unit in (ARMOR, CONVOY) else "COALITION", node)
    elif kind == "bar":
        _, node, side, amount = action
        if w.owner[node] != side and RULES.node_kind[node] != "SANCTUARY":
            w.capture[node] = CaptureBar(side, amount)
    elif kind == "drop":
        ids = [e.id for e in w.entities() if e.base_id is None]
        if ids:
            w.remove(ids[action[1] % len(ids)])
    else:
        for _ in range(action[1]):
            flips += check_one_tick(w)
    return flips


def check_one_tick(w: World) -> int:
    """One step. N-1: a node flips at most once, and exactly the nodes with a `NodeCaptured`
    changed owner. N-2: every bar stays inside (0, 100 %). N-4: the sanctuaries never move."""
    before = dict(w.owner)
    flipped = [(e.node_id, e.from_, e.to) for e in of(run(w), NodeCaptured)]
    assert len({node for node, _, _ in flipped}) == len(flipped)
    assert {n for n in w.owner if w.owner[n] != before[n]} == {node for node, _, _ in flipped}
    assert all(before[node] == frm and w.owner[node] == to for node, frm, to in flipped)
    for node, bar in w.capture.items():
        assert 0 < bar.progress < CAPTURE_FULL and bar.side != w.owner[node]
    assert (w.owner["haven"], w.owner["static-rear"]) == ("COALITION", "ENEMY")
    assert "haven" not in w.capture and "static-rear" not in w.capture
    return len(flipped)


@given(st.lists(ACTIONS, max_size=25))
@settings(max_examples=80, deadline=None)
def test_property_no_double_flip_and_progress_stays_in_range(actions: list[Any]) -> None:
    w = new_world()
    for action in actions:
        apply(w, action)


def test_the_property_generator_reaches_flips() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    apply(w, ("bar", NEUTRAL_FOB, "COALITION", CAPTURE_FULL - 1))
    assert apply(w, ("steps", 1)) == 1


def test_progress_is_monotonic_while_uncontested_capture_continues() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    seen = []
    for _ in range(120):
        run(w)
        seen.append(progress(w))
    assert seen == sorted(seen) and len(set(seen)) == len(seen) and seen[-1] < CAPTURE_FULL


def mid_capture() -> World:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB, n=1)
    put(w, CONVOY, "ENEMY", ENEMY_FOB)
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    run(w, 40)
    return w


def test_snapshot_round_trip_mid_capture_continues_identically() -> None:
    w = mid_capture()
    assert w.capture and any(b.progress for b in w.capture.values())
    restored = load(save(w))
    assert (restored.owner, restored.capture) == (w.owner, w.capture)
    assert state_hash(restored) == state_hash(w)
    restored.rules = w.rules
    for _ in range(100):
        assert [e.model_dump() for e in run(w)] == [e.model_dump() for e in run(restored)]
    assert state_hash(restored) == state_hash(w)


def test_two_runs_of_the_same_scenario_hash_equal() -> None:
    def scenario() -> tuple[str, list[dict[str, Any]]]:
        w = mid_capture()
        events = run(w, 400)
        return state_hash(w), [e.model_dump() for e in events]

    assert scenario() == scenario()


def test_capture_rules_follow_the_balance_keys() -> None:
    cap = RULES.capture
    assert cap is not None and (cap.radius_m, cap.time_s, cap.decay_micro) == (2000.0, 120.0, DECAY)
    assert math.isclose(CONFIG.balance.capture.decay_per_s, 1 / 120)
    owners: dict[str, NodeOwner] = new_world().owner
    assert owners["haven"] == "COALITION" and owners["static-rear"] == "ENEMY"
