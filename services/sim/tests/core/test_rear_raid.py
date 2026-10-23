"""NX-399 (Q-SIM-111): a deep raid on the Static's rear is accepted, a capture run there is not.

Runs on the shipped strait-1 config as test_order_hold does. `static-rear` is the Static's
uncapturable rear source (kind SANCTUARY) joined by road to `static-hq`; `haven` is the
coalition's own sanctuary.
"""

import pytest
from test_join import cid, join
from test_tasking import RULES, new_world, put

from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core.step import step
from nexus.core.world import Vec2, World, state_hash

REAR, HQ = "static-rear", "static-hq"


def reasons(events: list[Event]) -> list[str]:
    return [e.reason for e in events if isinstance(e, CommandRejected)]


@pytest.mark.parametrize("node", [REAR, "bridge-n"])
def test_a_logi_run_to_a_node_that_can_never_be_captured_is_rejected(node: str) -> None:
    w = new_world()
    events = step(w, [join(1, "LOGI", node)])
    assert reasons(events) == ["NODE_INVALID_FOR_UNIT"]
    assert not any(isinstance(e, UnitSpawned) for e in events)
    assert not [e for e in w.entities() if e.commander_id]


@pytest.mark.parametrize("node", ["haven", "fob-n-w", HQ])
def test_a_logi_run_to_the_sides_own_sanctuary_or_a_base_is_unchanged(node: str) -> None:
    w = new_world()
    events = step(w, [join(1, "LOGI", node)])
    assert reasons(events) == [] and any(isinstance(e, UnitSpawned) for e in events)


def test_the_kind_list_decides_not_the_node_id() -> None:
    import dataclasses

    w = new_world()
    w.rules = dataclasses.replace(RULES, uncapturable=frozenset())  # SANCTUARY capturable again
    assert reasons(step(w, [join(1, "LOGI", REAR)])) == []


def test_a_strike_order_to_the_rear_is_accepted_as_a_raid_order() -> None:
    w = new_world()
    events = step(w, [join(1, "STRIKE", REAR)])
    assert reasons(events) == []
    (jet,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert (jet.order, jet.order_node) == ("GOTO", REAR) and jet.path == [REAR]


def _raid() -> tuple[World, int, int | None]:
    """A jet holding over the rear (as NX-398 leaves one that arrived) and a Static convoy on the
    rear-HQ road 500 m from it; steps to the jet's first shot. Returns the world, the jet's id
    and the target of that shot (None if it never fired)."""
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", REAR)
    jet.order, jet.order_node = "GOTO", REAR
    jet.state, jet.orbit = "ON_STATION", Vec2(*RULES.roads.pos[REAR])
    (rx, ry), (hx, hy) = RULES.roads.pos[REAR], RULES.roads.pos[HQ]
    d = ((hx - rx) ** 2 + (hy - ry) ** 2) ** 0.5
    at = Vec2(rx + (hx - rx) * 500 / d, ry + (hy - ry) * 500 / d)
    convoy = w.spawn("ENEMY_CONVOY", "ENEMY", "AI_GARRISON", at)
    for _ in range(600):
        for e in step(w, []):
            if isinstance(e, WeaponFired) and e.shooter_id == jet.id:
                assert e.target_id == convoy.id
                return w, jet.id, e.target_id
    return w, jet.id, None


def test_the_raider_holds_near_the_rear_and_engages_a_static_convoy() -> None:
    w, jet_id, target = _raid()
    assert target is not None
    jet = w.get(jet_id)
    assert (jet.order, jet.order_node) == ("GOTO", REAR)  # still holding when it fired


def test_a_raid_is_deterministic() -> None:
    a, _, _ = _raid()
    b, _, _ = _raid()
    assert state_hash(a) == state_hash(b)
