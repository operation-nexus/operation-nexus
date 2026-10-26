"""NX-440: a STRIKE claimant fires at its node's defenses before units there, with
`combat.strike_structure_first` (COMBAT CB-10, Q-TD-55; extends the bridge exception, Q-SIM-105).
Off (the default) is the old rule: units always come first, so a SAM site at the node takes every
round (docs/review/ENTERTAINMENT-sweep-J0-J4-2026-10-26.md §2).

Worlds are built by hand with the board off (`test_combat`); the key is flipped through the shipped
config, then hits are made sure. Shipped numbers: FOB defense HP 300; AG_LIGHT 4 rounds of 50 damage
at 10 km, so two jets (8 rounds, 400) can take a FOB down, and a jet's AA_LIGHT never targets one.
"""

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_bridges import strike
from test_combat import ARMOR, ENEMY_JET, JET, new_world, of, put, run, track, with_weapon

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core.rules import Rules
from nexus.core.world import Entity, World, state_hash
from nexus.runtime.golden import shipped_config

SITE: UnitKind = "AIR_DEFENSE_SITE"
TARGET = {"COALITION": "fob-n-e", "ENEMY": "fob-n-w"}  # a FOB the other side owns
MAX_HP = 300


def rules(on: bool) -> Rules:
    """The shipped rules with the key set, board and sensing off, AG_LIGHT always hitting."""
    shipped = shipped_config({"combat.strike_structure_first": on}).rules
    base = dataclasses.replace(shipped, campaign=None, tasking=None, track_every_ticks=10**9)
    sure = with_weapon(base, "AG_LIGHT", base_pk=1.0)
    assert sure.combat is not None and sure.combat.strike_structure_first is on
    return dataclasses.replace(sure, combat=dataclasses.replace(sure.combat, pk_cap=1.0))


def scene(on: bool, side: Side = "COALITION", jets: int = 2) -> tuple[World, list[Entity], str]:
    """`jets` of `side`'s strike jets over the other side's FOB, a tracked SAM site and armor of
    the other side there; nothing claims anything yet."""
    w = new_world(rules(on))
    node = TARGET[side]
    pos = w.rules.roads.pos[node]  # type: ignore[union-attr]  # rules are set above
    other: Side = "ENEMY" if side == "COALITION" else "COALITION"
    assert w.owner[node] == other and w.defense_hp[node] == MAX_HP
    shooters = [
        put(w, JET if side == "COALITION" else ENEMY_JET, side, pos[0] + 500 * i, pos[1], cmd=i + 1)
        for i in range(jets)
    ]
    for t in (put(w, SITE, other, pos[0] + 1_000, pos[1]), put(w, ARMOR, other, *pos)):
        track(w, shooters[0], t)
    return w, shooters, node


def node_shots(events: list[Event]) -> list[WeaponFired]:
    return [f for f in of(events, WeaponFired) if f.target_node_id is not None]


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])  # ECONOMY EC-3: no owner-kind check
def test_with_the_key_a_strike_package_brings_the_defenses_down_past_a_sam_site(
    side: Side,
) -> None:
    w, jets, node = scene(True, side)
    for jet in jets:
        strike(w, jet, node)
    events = run(w, 120)
    shots = of(events, WeaponFired)
    assert [f.target_node_id for f in shots if f.weapon == "AG_LIGHT"][:6] == [node] * 6
    assert all(f.target_id is None for f in shots[:6])  # no unit took a round first
    assert {f.weapon for f in node_shots(events)} == {"AG_LIGHT"}  # AA_LIGHT has no STRUCTURE
    assert w.defense_hp[node] == 0
    assert [d.node_id for d in of(events, NodeDefensesDown)] == [node]


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])
def test_without_the_key_units_come_first_and_the_defenses_hold(side: Side) -> None:
    w, jets, node = scene(False, side)
    for jet in jets:
        strike(w, jet, node)
    events = run(w, 120)
    assert of(events, WeaponFired) and node_shots(events) == []
    assert w.defense_hp[node] == MAX_HP and of(events, NodeDefensesDown) == []


@pytest.mark.parametrize(
    "claim",
    [
        None,  # no job
        ("SCOUT", "fob-n-e"),  # a job on the node that is not a strike
        ("STRIKE", "static-hq"),  # a strike on another node, out of range
    ],
)
def test_only_a_strike_claim_on_this_node_fires_at_it_before_units(
    claim: tuple[str, str] | None,
) -> None:
    w, (jet,), node = scene(True, jets=1)
    if claim is not None:
        strike(w, jet, claim[1], claim[0])  # type: ignore[arg-type]  # a JobKind literal
    first = of(run(w), WeaponFired)
    assert [f.target_node_id for f in first] == [None] and w.defense_hp[node] == MAX_HP


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])
def test_a_strike_claim_on_its_own_node_never_fires_at_it(side: Side) -> None:
    """Over its own side's FOB with a claim on it, the jet takes the enemy units there instead."""
    w, (jet,), node = scene(True, side, jets=1)
    w.owner[node] = side
    strike(w, jet, node)
    mine = [f for f in of(run(w, 60), WeaponFired) if f.shooter_id == jet.id]
    assert mine and all(f.target_id is not None for f in mine)  # (the armor shells the FOB)


@pytest.mark.parametrize("armor", [False, True])
def test_a_strike_claim_on_a_bridge_keeps_the_old_order(armor: bool) -> None:
    """A bridge has no defense HP, so the key leaves it to `bridges.target` (Q-SIM-105): units
    first, then the span (bridge-n at 200 km, 60 km; `logistics.bridge_hp` 300, AG_LIGHT 50)."""
    w = new_world(rules(True))
    x, y = w.rules.roads.pos["bridge-n"]  # type: ignore[union-attr]
    jet = put(w, JET, "COALITION", x, y, cmd=1)
    strike(w, jet, "bridge-n")
    foe = put(w, ARMOR, "ENEMY", x + 2_000, y) if armor else None
    if foe is not None:
        track(w, jet, foe)
    (first,) = [f for f in of(run(w), WeaponFired) if f.weapon == "AG_LIGHT"]
    if foe is not None:
        assert (first.target_id, first.target_node_id) == (foe.id, None)
        assert w.bridge_hp["bridge-n"] == 300
    else:
        assert (first.target_id, first.target_node_id) == (None, "bridge-n")
        assert w.bridge_hp["bridge-n"] == 250


def test_strike_first_fire_is_deterministic() -> None:
    def once() -> tuple[str, list[str]]:
        w, jets, node = scene(True)
        w.rules = shipped_rules_on()  # the shipped Pk: hits and misses come from the combat stream
        for jet in jets:
            strike(w, jet, node)
        events = run(w, 200)
        return state_hash(w), [e.model_dump_json() for e in events]

    a, b = once(), once()
    assert a == b and any('"WeaponImpact"' in e and '"fob-n-e"' in e for e in a[1])


def shipped_rules_on() -> Rules:
    shipped = shipped_config({"combat.strike_structure_first": True}).rules
    return dataclasses.replace(shipped, campaign=None, tasking=None, track_every_ticks=10**9)


@settings(max_examples=30, deadline=None)
@given(
    on=st.booleans(),
    dxs=st.lists(st.integers(-12_000, 12_000), min_size=1, max_size=3),
    armor_dx=st.integers(-12_000, 12_000),
)
def test_a_claim_changes_fire_only_with_the_key(on: bool, dxs: list[int], armor_dx: int) -> None:
    """Off: holding STRIKE claims changes no event (the old rule). On: every claimant's first
    AG_LIGHT shot, fired while its node is in range, is at the node."""

    def play(claims: bool) -> tuple[list[Event], list[int]]:
        w = new_world(rules(on))
        node = TARGET["COALITION"]
        x, y = w.rules.roads.pos[node]  # type: ignore[union-attr]
        jets = [put(w, JET, "COALITION", x + dx, y, cmd=i + 1) for i, dx in enumerate(dxs)]
        armor = put(w, ARMOR, "ENEMY", x + armor_dx, y)
        for jet in jets:
            track(w, jet, armor)
            if claims:
                strike(w, jet, node)
        return run(w, 30), [j.id for j in jets]

    events, ids = play(True)
    if not on:
        assert [e.model_dump() for e in events] == [e.model_dump() for e in play(False)[0]]
        return
    for jet_id, dx in zip(ids, dxs, strict=True):
        first = [f for f in of(events, WeaponFired) if f.shooter_id == jet_id]
        if abs(dx) <= 10_000:  # in AG_LIGHT range of the node: it fires at once, at the node
            assert first[0].target_node_id == TARGET["COALITION"]
