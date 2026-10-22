"""NX-124 part 3: node defense HP (GAMEPLAY §8 and §9, COMBAT CB-10, Q-GD-18, Q-SIM-71, Q-TH-7,
Q-GP-28, Q-GP-44).

Shipped strait-1 numbers: max defense HP AIRBASE 500, FOB 300, HQ 800, SANCTUARY 1000; a stock unit
delivered rebuilds 2; a base below its starvation floor (FOB: 250 of 1000) loses 5 per game minute,
600 ticks, so 1 hp per 120 starved ticks; AG_LIGHT does 50 damage at 10 km, 300 m/s, 4 rounds.
Worlds are built by hand (`World.new`): contacts are set by hand, no sensing pass runs.
"""

import dataclasses
from collections.abc import Callable

import pytest
from test_combat import INFANTRY, JET, RULES, TRUCK, new_world, of, put, run, sure, track

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.node_defenses_restored import NodeDefensesRestored
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core.combat import validate as combat_validate
from nexus.core.defense import damage, rebuild, validate
from nexus.core.rules import CAPTURE_FULL
from nexus.core.world import CaptureBar, Entity, World, load, lose_unit, save, state_hash

POS = RULES.roads.pos
ENEMY_FOB, MY_FOB, NEUTRAL_FOB = "fob-n-e", "fob-n-w", "cross-n"
FORWARD, SANCTUARY = "west-airbase", "haven"
ARMOR: UnitKind = "ENEMY_ARMOR"


def at(node: str, dx: float = 0.0) -> tuple[float, float]:
    return POS[node][0] + dx, POS[node][1]


def human(w: World) -> None:
    """One live viewer unit: somebody is playing (no idle floor)."""
    put(w, INFANTRY, "COALITION", *at(MY_FOB), cmd=1)


def lines(events: list[Event]) -> list[tuple[str, str]]:
    return [
        (e.kind, e.node_id)
        for e in events
        if isinstance(e, NodeDefensesDown | NodeDefensesRestored)
    ]


# --- start state, snapshot ------------------------------------------------------------------


def test_owned_nodes_start_full_neutral_at_zero_and_a_bridge_has_none() -> None:
    w = new_world()
    assert w.defense_hp[FORWARD] == 500 and w.defense_hp[MY_FOB] == 300
    assert w.defense_hp["static-hq"] == 800 and w.defense_hp[SANCTUARY] == 1000
    assert w.defense_hp["static-rear"] == 1000 and w.defense_hp[ENEMY_FOB] == 300
    assert w.defense_hp[NEUTRAL_FOB] == 0 and "bridge-n" not in w.defense_hp
    assert list(w.defense_hp) == sorted(w.defense_hp) and set(w.defense_drain) == set(w.defense_hp)


def test_defense_state_is_in_the_snapshot_and_the_hash() -> None:
    w = new_world()
    base = state_hash(w)
    w.defense_hp[MY_FOB], w.defense_drain[MY_FOB] = 120, 77
    w.defense_hp[ENEMY_FOB] = 10
    w.defense_down.add(ENEMY_FOB)
    assert state_hash(w) != base
    again = load(save(w))
    assert (again.defense_hp, again.defense_drain, again.defense_down) == (
        w.defense_hp, w.defense_drain, w.defense_down,
    )  # fmt: skip
    again.rules = RULES
    validate(again, RULES)
    assert state_hash(again) == state_hash(w)


@pytest.mark.parametrize(
    "bad",
    [
        lambda w: w.defense_hp.__setitem__(MY_FOB, 301),  # above the maximum
        lambda w: w.defense_drain.__setitem__(MY_FOB, 600),  # carry reaches a whole minute
        lambda w: w.defense_drain.__setitem__(NEUTRAL_FOB, 3),  # a carry at 0 hp
        lambda w: w.defense_hp.__setitem__(NEUTRAL_FOB, 10),  # hp on a NEUTRAL node
        lambda w: w.defense_down.add(MY_FOB),  # down, yet at full hp
    ],
)
def test_restore_checks_defense_state_against_the_rules(bad: Callable[[World], object]) -> None:
    w = new_world()
    bad(w)
    again = load(save(w))
    again.rules = RULES
    with pytest.raises(ValueError, match="defense"):
        validate(again, RULES)


# --- capture gate (Q-GD-18) -----------------------------------------------------------------


def test_no_bar_starts_while_the_defenses_are_up_and_one_starts_at_zero() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", *at(ENEMY_FOB), cmd=1)
    assert of(run(w, 5), CaptureStarted) == [] and ENEMY_FOB not in w.capture
    w.defense_hp[ENEMY_FOB] = 0
    assert [e.node_id for e in of(run(w), CaptureStarted)] == [ENEMY_FOB]


def test_a_neutral_node_can_be_captured_at_once() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", *at(NEUTRAL_FOB), cmd=1)
    assert [e.node_id for e in of(run(w), CaptureStarted)] == [NEUTRAL_FOB]


def test_a_running_bar_is_not_stopped_by_a_repair_and_the_flip_resets_to_zero() -> None:
    """The gate says capture "can't begin" (GAMEPLAY §8): a bar already running fills on, and the
    node is 0 for its new owner whatever was rebuilt meanwhile."""
    w = new_world()
    put(w, INFANTRY, "COALITION", *at(ENEMY_FOB), cmd=1)
    w.defense_hp[ENEMY_FOB] = 0
    run(w)
    before = w.capture[ENEMY_FOB].progress
    w.defense_hp[ENEMY_FOB] = 40  # a delivery
    w.defense_down.add(ENEMY_FOB)
    run(w)
    assert w.capture[ENEMY_FOB].progress > before
    w.capture[ENEMY_FOB] = CaptureBar("COALITION", CAPTURE_FULL - 1)
    events = run(w)
    assert [e.node_id for e in of(events, NodeCaptured)] == [ENEMY_FOB]
    assert w.defense_hp[ENEMY_FOB] == 0 and w.defense_drain[ENEMY_FOB] == 0
    assert ENEMY_FOB not in w.defense_down and lines(events) == []  # NodeCaptured says it


# --- rebuild and drain (Q-SIM-71) -----------------------------------------------------------


def truck(w: World, node: str, cargo: int) -> None:
    e = put(w, TRUCK, "COALITION", *at(node))
    e.cargo, e.last_node = cargo, node


def test_each_unit_delivered_rebuilds_two_hp_in_its_tick_up_to_the_maximum() -> None:
    w = new_world()
    w.stock[MY_FOB], w.defense_hp[MY_FOB] = 500, 100
    truck(w, MY_FOB, 10)
    for _ in range(40):
        run(w)
        assert w.defense_hp[MY_FOB] == 100 + 2 * (w.stock[MY_FOB] - 500)  # exact, every tick
    assert w.stock[MY_FOB] == 510 and w.defense_hp[MY_FOB] == 120
    w2 = new_world()
    w2.stock[MY_FOB], w2.defense_hp[MY_FOB] = 500, 299
    truck(w2, MY_FOB, 5)
    run(w2, 40)
    assert w2.stock[MY_FOB] == 505 and w2.defense_hp[MY_FOB] == 300  # capped, stock still moves


def test_a_starved_base_loses_five_hp_a_minute_with_a_carry_that_pauses() -> None:
    w = new_world()
    w.stock[MY_FOB] = 0  # below the floor of 250
    run(w, 119)
    assert (w.defense_hp[MY_FOB], w.defense_drain[MY_FOB]) == (300, 595)
    run(w)
    assert (w.defense_hp[MY_FOB], w.defense_drain[MY_FOB]) == (299, 0)
    run(w, 50)
    assert w.defense_drain[MY_FOB] == 250
    w.stock[MY_FOB] = 250  # at the floor is not starved: the drain pauses, the carry stays
    run(w, 100)
    assert (w.defense_hp[MY_FOB], w.defense_drain[MY_FOB]) == (299, 250)
    w.stock[MY_FOB] = 249
    run(w, 70)  # 250 + 70 x 5 = 600: one more hp, exactly
    assert (w.defense_hp[MY_FOB], w.defense_drain[MY_FOB]) == (298, 0)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    run(w, 500)
    assert (w.defense_hp[MY_FOB], w.defense_drain[MY_FOB]) == (298, 0)  # a pause drains nothing


def test_a_whole_minute_starved_costs_five_and_a_sanctuary_never_starves() -> None:
    w = new_world()
    w.stock[MY_FOB] = 0
    run(w, 600)
    assert w.defense_hp[MY_FOB] == 295 and w.defense_hp[SANCTUARY] == 1000
    assert w.defense_hp[FORWARD] == 500  # stock 0 is not set in this world: no stock, no drain


def test_the_drain_stops_at_zero_with_one_down_event() -> None:
    w = new_world()
    w.stock[MY_FOB], w.defense_hp[MY_FOB] = 0, 2
    events = run(w, 400)
    assert w.defense_hp[MY_FOB] == 0 and w.defense_drain[MY_FOB] == 0
    assert lines(events) == [("NodeDefensesDown", MY_FOB)]
    assert MY_FOB in w.defense_down


# --- events without spam ---------------------------------------------------------------------


def test_down_once_and_restored_only_when_full_again_so_flapping_gives_one_pair() -> None:
    w = new_world()
    out: list[Event] = []
    damage(w, RULES, MY_FOB, 300, out)
    rebuild(w, RULES, MY_FOB, 1, out)  # a delivery of one unit ...
    damage(w, RULES, MY_FOB, 2, out)  # ... then a hit
    rebuild(w, RULES, MY_FOB, 3, out)
    damage(w, RULES, MY_FOB, 6, out)
    assert w.defense_hp[MY_FOB] == 0
    assert lines(out) == [("NodeDefensesDown", MY_FOB)]  # at most one Down per cycle
    rebuild(w, RULES, MY_FOB, 149, out)
    assert w.defense_hp[MY_FOB] == 298 and len(lines(out)) == 1
    rebuild(w, RULES, MY_FOB, 1, out)
    assert lines(out) == [("NodeDefensesDown", MY_FOB), ("NodeDefensesRestored", MY_FOB)]
    assert MY_FOB not in w.defense_down
    rebuild(w, RULES, MY_FOB, 5, out)
    damage(w, RULES, MY_FOB, 10, out)
    rebuild(w, RULES, MY_FOB, 5, out)  # never down: nothing as it repairs
    assert len(lines(out)) == 2
    damage(w, RULES, MY_FOB, 300, out)  # the next cycle announces again
    assert len(lines(out)) == 3


def test_a_node_that_was_never_down_announces_nothing_as_it_builds_up() -> None:
    w = new_world()
    w.owner[NEUTRAL_FOB] = "COALITION"  # just flipped: 0 hp, no flag
    out: list[Event] = []
    rebuild(w, RULES, NEUTRAL_FOB, 150, out)
    assert w.defense_hp[NEUTRAL_FOB] == 300 and out == []


def test_a_down_event_names_the_owner_and_ids_are_sequential() -> None:
    w = new_world()
    out: list[Event] = []
    damage(w, RULES, ENEMY_FOB, 1000, out)
    (down,) = of(out, NodeDefensesDown)
    assert (down.node_id, down.owner, down.tick) == (ENEMY_FOB, "ENEMY", 1)


# --- CB-10 structure fire ---------------------------------------------------------------------


def jet_near(w: World, node: str, dist: float = 5000.0) -> Entity:
    return put(w, JET, "COALITION", *at(node, -dist), cmd=2)


def test_only_structure_weapons_fire_on_defenses_and_units_come_first() -> None:
    w = new_world(sure("AG_LIGHT"))
    jet_near(w, ENEMY_FOB)
    events = run(w, 3)
    (fired,) = of(events, WeaponFired)
    assert (fired.target_id, fired.target_node_id, fired.weapon) == (None, ENEMY_FOB, "AG_LIGHT")
    # a weapon without STRUCTURE never picks a node: infantry (GROUND) and an interceptor (AIR)
    w2 = new_world()
    put(w2, INFANTRY, "COALITION", *at(ENEMY_FOB, -50.0), cmd=3)
    put(w2, "ENEMY_FIGHTER", "ENEMY", *at(MY_FOB, 100.0))
    assert of(run(w2, 20), WeaponFired) == []
    # with an enemy unit tracked in range as well, the jet shoots the unit
    w3 = new_world(sure("AG_LIGHT"))
    jet = jet_near(w3, ENEMY_FOB)
    armor = put(w3, ARMOR, "ENEMY", *at(ENEMY_FOB, -8000.0))
    track(w3, jet, armor)
    (first,) = of(run(w3), WeaponFired)
    assert (first.target_id, first.target_node_id) == (armor.id, None)


def test_a_structure_shot_hits_for_the_full_damage_and_downs_the_node() -> None:
    w = new_world(sure("AG_LIGHT"))
    w.defense_hp[ENEMY_FOB] = 90
    jet_near(w, ENEMY_FOB)
    events = run(w, 40)
    assert next((i.hit, i.target_id, i.target_node_id) for i in of(events, WeaponImpact)) == (
        True, None, ENEMY_FOB,
    )  # fmt: skip
    assert w.defense_hp[ENEMY_FOB] == 40  # 90 - 50: armor 0 (Q-CBT-22)
    events = run(w, 40)
    assert w.defense_hp[ENEMY_FOB] == 0 and lines(events) == [("NodeDefensesDown", ENEMY_FOB)]
    assert of(run(w, 40), WeaponFired) == []  # nothing left to shoot at


def test_a_structure_shot_fizzles_without_a_draw_when_the_node_changes_hands_or_is_down() -> None:
    w = new_world(sure("AG_LIGHT"))
    jet_near(w, ENEMY_FOB)
    run(w, 2)
    assert len(w.shots) == 1 and w.shots[0].node == ENEMY_FOB
    w.defense_hp[ENEMY_FOB] = 0
    before = w.rng.to_state()
    (impact,) = of(run(w, 40), WeaponImpact)
    assert impact.hit is False and w.rng.to_state() == before


def test_a_structure_is_out_of_range_beyond_the_weapon_range() -> None:
    w = new_world(sure("AG_LIGHT"))
    jet_near(w, ENEMY_FOB, dist=10_001.0)
    assert of(run(w, 10), WeaponFired) == []


def test_a_node_you_own_or_nobody_owns_is_not_a_target() -> None:
    w = new_world(sure("AG_LIGHT"))
    put(w, JET, "COALITION", *at(MY_FOB, 100.0), cmd=2)
    put(w, JET, "COALITION", *at(NEUTRAL_FOB, 100.0), cmd=3)
    assert of(run(w, 10), WeaponFired) == []


def test_mirrored_the_enemy_fires_on_a_coalition_node() -> None:
    w = new_world(sure("AG_LIGHT"))
    put(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", *at(MY_FOB, -5000.0))
    (fired,) = of(run(w, 3), WeaponFired)
    assert fired.target_node_id == MY_FOB


# --- idle floor (Q-GP-28, Q-GP-44, Q-TH-7) ----------------------------------------------------


def test_the_sanctuary_cannot_drop_below_one_while_nobody_plays() -> None:
    w = new_world()
    out: list[Event] = []
    damage(w, RULES, SANCTUARY, 10_000, out)
    assert w.defense_hp[SANCTUARY] == 1 and out == [] and not w.defense_down
    human(w)
    damage(w, RULES, SANCTUARY, 10_000, out)
    assert w.defense_hp[SANCTUARY] == 0 and lines(out) == [("NodeDefensesDown", SANCTUARY)]
    other = new_world()
    damage(other, RULES, MY_FOB, 10_000, [])  # only the sanctuary has the floor
    assert other.defense_hp[MY_FOB] == 0


def test_capture_progress_on_the_forward_airbase_freezes_with_no_humans() -> None:
    w = new_world()
    w.defense_hp[FORWARD] = 0
    put(w, ARMOR, "ENEMY", *at(FORWARD))
    assert of(run(w, 5), CaptureStarted) == [] and FORWARD not in w.capture
    human(w)
    assert [e.node_id for e in of(run(w), CaptureStarted)] == [FORWARD]
    bar = w.capture[FORWARD].progress
    w.remove(next(e.id for e in w.entities() if e.owner_kind == "COMMANDER"))  # the last one leaves
    run(w, 5)
    assert w.capture[FORWARD].progress == bar  # frozen: neither fills nor decays


def test_other_nodes_are_not_frozen_and_a_lost_forward_airbase_is_not_protected() -> None:
    w = new_world()
    w.defense_hp[ENEMY_FOB] = 0
    put(w, INFANTRY, "COALITION", *at(ENEMY_FOB))  # AI-run, no human anywhere
    assert [e.node_id for e in of(run(w), CaptureStarted)] == [ENEMY_FOB]


# --- defeat (Q-TH-7) --------------------------------------------------------------------------


def campaign_world(hold: int) -> World:
    assert RULES.campaign is None
    full = dataclasses.replace(RULES, campaign=None)
    from nexus.runtime.campaign_config import load_campaign_config

    rc = load_campaign_config().rules.campaign
    assert rc is not None
    rules = dataclasses.replace(full, campaign=dataclasses.replace(rc, defeat_hold_ticks=hold))
    w = new_world(rules)
    human(w)
    return w


def test_the_sanctuary_held_at_zero_for_the_hold_loses_the_war() -> None:
    w = campaign_world(5)
    w.defense_hp[SANCTUARY] = 0
    assert of(run(w, 4), CampaignEnded) == [] and w.campaign.defeat_ticks == 4
    (ended,) = of(run(w), CampaignEnded)
    assert (ended.result, ended.winner, ended.tick) == ("DEFEAT", "ENEMY", 5)
    assert w.campaign.ended and w.campaign.running_ticks == 5


def test_a_repair_resets_the_hold() -> None:
    w = campaign_world(5)
    w.defense_hp[SANCTUARY] = 0
    run(w, 3)
    w.defense_hp[SANCTUARY] = 1
    run(w)
    assert w.campaign.defeat_ticks == 0
    w.defense_hp[SANCTUARY] = 0
    assert of(run(w, 4), CampaignEnded) == []
    assert len(of(run(w), CampaignEnded)) == 1


def test_a_pause_does_not_count_toward_the_hold() -> None:
    w = campaign_world(5)
    w.defense_hp[SANCTUARY] = 0
    run(w, 2)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    run(w, 50)
    w.campaign.clock_paused, w.campaign.pause_reason = False, None
    assert w.campaign.defeat_ticks == 2 and of(run(w, 2), CampaignEnded) == []
    assert len(of(run(w), CampaignEnded)) == 1


def test_no_defeat_accrues_while_nobody_plays() -> None:
    w = campaign_world(3)
    w.remove(next(e.id for e in w.entities() if e.owner_kind == "COMMANDER"))
    w.defense_hp[SANCTUARY] = 0
    assert of(run(w, 20), CampaignEnded) == [] and w.campaign.defeat_ticks == 0
    human(w)
    assert of(run(w, 2), CampaignEnded) == []
    assert len(of(run(w), CampaignEnded)) == 1


def test_victory_beats_defeat_on_the_same_tick() -> None:
    w = campaign_world(1)
    w.defense_hp[SANCTUARY] = 0
    w.owner["static-hq"] = "COALITION"
    (ended,) = of(run(w), CampaignEnded)
    assert (ended.result, ended.winner) == ("VICTORY", "COALITION")


def test_the_enemy_sanctuary_at_zero_is_not_a_coalition_defeat() -> None:
    w = campaign_world(1)
    w.defense_hp["static-rear"] = 0
    assert of(run(w, 5), CampaignEnded) == []


def test_determinism_same_scenario_same_hash() -> None:
    def scenario() -> str:
        w = new_world(sure("AG_LIGHT"))
        w.stock[MY_FOB] = 0
        jet_near(w, ENEMY_FOB)
        truck(w, MY_FOB, 3)
        run(w, 300)
        return state_hash(w)

    assert scenario() == scenario()


# --- sanctuary repair by parked logistics units (Q-SIM-71) and the rear source --------------------

REAR = "static-rear"
CONVOY: UnitKind = "ENEMY_CONVOY"


def parked_truck(w: World, kind: UnitKind = TRUCK, node: str = SANCTUARY) -> Entity:
    e = put(w, kind, "COALITION" if node == SANCTUARY else "ENEMY", *at(node))
    e.last_node = node
    return e


def test_parked_trucks_rebuild_the_sanctuary_from_infinite_supply_and_two_are_twice_as_fast() -> (
    None
):
    """0.6 world s a tick x 1.0 hp/s = 600 thousandths of an hp per truck per tick, exactly."""
    one, two = new_world(), new_world()
    for w in (one, two):
        w.defense_hp[SANCTUARY] = 100
    parked_truck(one)
    parked_truck(two)
    parked_truck(two)
    run(one, 7)
    run(two, 7)
    assert (one.defense_hp[SANCTUARY], one.defense_drain[SANCTUARY]) == (104, 200)
    assert (two.defense_hp[SANCTUARY], two.defense_drain[SANCTUARY]) == (108, 400)
    assert "haven" not in one.stock  # no stock debit: the sanctuary is infinite
    assert state_hash(load(save(one))) == state_hash(one)  # the thousandths carry survives


def test_the_enemy_rear_is_repaired_by_its_convoys_by_parity() -> None:
    w = new_world()
    w.defense_hp[REAR] = 10
    parked_truck(w, CONVOY, REAR)
    run(w, 10)
    assert w.defense_hp[REAR] == 16


def test_a_disabled_moving_foreign_or_paused_truck_repairs_nothing() -> None:
    w = new_world()
    w.defense_hp[SANCTUARY] = 100
    wreck = parked_truck(w)
    wreck.damage_state, wreck.hp, wreck.wreck_left = "DISABLED", 1, 6000
    moving = parked_truck(w)
    moving.path = [FORWARD]
    away = put(w, TRUCK, "COALITION", *at(MY_FOB))
    away.last_node = MY_FOB
    foreign = put(w, CONVOY, "ENEMY", *at(SANCTUARY))
    foreign.last_node = SANCTUARY
    run(w, 20)
    assert w.defense_hp[SANCTUARY] == 100
    parked_truck(w)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    run(w, 20)
    assert w.defense_hp[SANCTUARY] == 100  # nothing while paused (SC-11)


def test_repair_stops_at_full_with_one_restored_after_one_down() -> None:
    w = new_world()
    human(w)
    out: list[Event] = []
    damage(w, RULES, SANCTUARY, 1000, out)
    parked_truck(w)
    events = run(w, 1700)
    assert w.defense_hp[SANCTUARY] == 1000 and w.defense_drain[SANCTUARY] == 0
    assert lines(out + events) == [
        ("NodeDefensesDown", SANCTUARY),
        ("NodeDefensesRestored", SANCTUARY),
    ]


def test_a_repair_that_lifts_the_sanctuary_above_zero_resets_the_defeat_hold() -> None:
    w = campaign_world(5)
    w.defense_hp[SANCTUARY] = 0
    run(w, 3)
    assert w.campaign.defeat_ticks == 3
    parked_truck(w)
    assert of(run(w, 2), CampaignEnded) == []  # 0.6 then 1.2 hp: above 0 on the second tick
    assert w.defense_hp[SANCTUARY] == 1 and w.campaign.defeat_ticks == 0


def test_the_static_rear_is_never_a_structure_target_but_the_coalition_sanctuary_is() -> None:
    w = new_world(sure("AG_LIGHT"))
    put(w, JET, "COALITION", *at(REAR, 4000.0), cmd=2)
    assert of(run(w, 5), WeaponFired) == []
    w2 = new_world(sure("AG_LIGHT"))
    put(w2, "ENEMY_STRIKE_FIGHTER", "ENEMY", *at(SANCTUARY, 5000.0))
    (fired,) = of(run(w2, 3), WeaponFired)
    assert fired.target_node_id == SANCTUARY


# --- a full-stock node takes deliveries straight into its defenses; a pinned node is no target --


def test_a_truck_at_a_full_stock_node_spends_each_unit_on_the_defenses_and_conserves_stock() -> (
    None
):
    w = new_world()
    top = RULES.supply.max_stock[MY_FOB]
    w.stock[MY_FOB], w.defense_hp[MY_FOB] = top, 100
    w.defense_down.add(MY_FOB)
    e = put(w, TRUCK, "COALITION", *at(MY_FOB))
    e.cargo, e.last_node = 10, MY_FOB
    events: list[Event] = []
    for _ in range(40):
        events += run(w)
        assert w.stock[MY_FOB] == top  # the stock never moves
    assert w.defense_hp[MY_FOB] == 120 and e.cargo == 0  # 10 units x 2 hp
    (delivered,) = of(events, SupplyDelivered)
    (spent,) = of(events, SupplyConsumed)
    assert (delivered.amount, spent.amount, spent.cause, spent.node_id) == (
        10,
        10,
        "REPAIR",
        MY_FOB,
    )
    assert events.index(delivered) < events.index(spent)  # reported together at the stop's end
    assert e.delivered == e.defended == 0
    assert load(save(w)).get(e.id).defended == 0


def test_the_stop_ends_when_the_defenses_are_full_and_the_cargo_stays_aboard() -> None:
    w = new_world()
    w.stock[MY_FOB] = RULES.supply.max_stock[MY_FOB]
    w.defense_hp[MY_FOB] = 296
    e = put(w, TRUCK, "COALITION", *at(MY_FOB))
    e.cargo, e.last_node = 10, MY_FOB
    events = run(w, 40)
    assert w.defense_hp[MY_FOB] == 300 and e.cargo == 8  # two units fill 4 hp, then it parks
    assert [(s.amount, s.cause) for s in of(events, SupplyConsumed)] == [(2, "REPAIR")]
    assert run(w, 20) == [] and e.cargo == 8  # both full: parked with its cargo as today


def test_a_node_with_room_in_stock_takes_stock_first_and_a_sanctuary_takes_no_cargo() -> None:
    w = new_world()
    w.stock[MY_FOB], w.defense_hp[MY_FOB] = 500, 100
    t = put(w, TRUCK, "COALITION", *at(MY_FOB))
    t.cargo, t.last_node = 3, MY_FOB
    events = run(w, 20)
    assert w.stock[MY_FOB] == 503 and of(events, SupplyConsumed) == []
    w2 = new_world()
    w2.defense_hp[SANCTUARY] = 10
    s = put(w2, TRUCK, "COALITION", *at(SANCTUARY))
    s.cargo, s.last_node = 5, SANCTUARY
    run(w2, 10)
    assert s.cargo == 5  # a sanctuary is rebuilt by parked trucks, not by cargo


def test_a_node_pinned_at_its_idle_floor_is_not_a_target_and_a_shot_in_flight_fizzles() -> None:
    w = new_world(sure("AG_CANNON"))
    w.defense_hp[SANCTUARY] = 1
    put(w, ARMOR, "ENEMY", *at(SANCTUARY, 1000.0))
    assert w.viewer_units() == 0 and of(run(w, 50), WeaponFired) == []
    human(w)  # somebody plays: the floor is gone and the sanctuary is a target again
    assert of(run(w, 3), WeaponFired)
    w2 = new_world(sure("AG_LIGHT"))
    w2.defense_hp[SANCTUARY] = 2
    human(w2)
    put(w2, "ENEMY_STRIKE_FIGHTER", "ENEMY", *at(SANCTUARY, 5000.0))
    run(w2, 2)
    assert len(w2.shots) == 1
    w2.remove(next(e.id for e in w2.entities() if e.owner_kind == "COMMANDER"))  # nobody plays
    w2.defense_hp[SANCTUARY] = 1
    before = w2.rng.to_state()
    (impact,) = of(run(w2, 40), WeaponImpact)
    assert impact.hit is False and w2.rng.to_state() == before and w2.defense_hp[SANCTUARY] == 1


# --- a truck lost mid-stop still reports its units ------------------------------------------------


def unloading_truck(w: World, node: str, cargo: int) -> Entity:
    """A truck at a full-stock `node` whose defenses are low, 5 ticks into its unloading stop."""
    w.stock[node], w.defense_hp[node] = RULES.supply.max_stock[node], 100
    e = put(w, TRUCK, "COALITION", *at(node))
    e.cargo, e.last_node = cargo, node
    run(w, 5)
    assert e.defended and e.delivered == e.defended
    return e


def reported(events: list[Event], e: Entity, cargo: int) -> None:
    """The stop's `SupplyDelivered` and `SupplyConsumed{REPAIR}` come before the loss, and every
    unit that left the cargo is accounted for (the stock stayed full: all went to the defenses)."""
    assert e.cargo is not None
    (delivered,) = of(events, SupplyDelivered)
    (spent,) = of(events, SupplyConsumed)
    (gone,) = of(events, UnitDestroyed)
    assert delivered.amount == spent.amount == cargo - e.cargo > 0
    assert spent.cause == "REPAIR"
    assert events.index(delivered) < events.index(spent) < events.index(gone)


def test_a_truck_killed_mid_defended_unload_reports_both_events_before_it_dies() -> None:
    w = new_world()
    e = unloading_truck(w, MY_FOB, 20)
    hp = w.defense_hp[MY_FOB]
    out: list[Event] = []
    lose_unit(w, e, out, killer_id=99)
    reported(out, e, 20)
    assert hp - 100 == 2 * (20 - (e.cargo or 0))  # 2 hp per unit spent
    assert w.stock[MY_FOB] == RULES.supply.max_stock[MY_FOB]  # conserved: stock + consumed + lost


def test_a_truck_lost_at_a_flipped_base_with_nowhere_to_go_reports_its_stop() -> None:
    w = new_world()
    for node in w.owner:
        w.owner[node] = "ENEMY"
    w.owner[MY_FOB] = "COALITION"
    e = unloading_truck(w, MY_FOB, 20)
    put(w, ARMOR, "ENEMY", *at(MY_FOB))
    w.defense_hp[MY_FOB] = 0
    w.capture[MY_FOB] = CaptureBar("ENEMY", CAPTURE_FULL - 1)
    events = run(w)
    assert [x.node_id for x in of(events, NodeCaptured)] == [MY_FOB]
    reported(events, e, 20)  # the flip zeroes the hp; the units were still spent


def test_restore_refuses_an_entity_naming_a_node_that_does_not_exist() -> None:
    w = new_world()
    e = put(w, TRUCK, "COALITION", *at(MY_FOB))
    e.last_node = "x"
    again = load(save(w))
    with pytest.raises(ValueError, match="not a theater node"):
        combat_validate(again, RULES)
