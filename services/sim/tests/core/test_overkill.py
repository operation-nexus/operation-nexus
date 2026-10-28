"""NX-468: the overkill check, `combat.overkill_check` (COMBAT CB-1, Q-TD-73). A weapon skips a
target whose shots in flight already cover, in expected damage, what it has left, and takes the
next one: the strike-funnel problem (docs/review/STRIKE-FUNNEL-analysis-2026-10-27.md §3), where
both jets spent every bomb on the air-defense site and none on the node's defenses.

Worked numbers (shipped content): AG_LIGHT 50 damage, 300 m/s, reload 10 s, 4 rounds; an
AIR_DEFENSE_SITE has 150 hp, armor 0.3 (35 hp a hit) and a Disabled floor of 14 hp, so it has 136
left; a FOB's defense HP is 300. With Pk 1 four bombs (140) cover the site: two jets 9 km out fire
two each (two volleys, 17 ticks apart; a bomb at 9 km flies 50 ticks), then the node's defenses.
"""

import dataclasses

import pytest
from test_bridges import strike
from test_combat import (
    CONVOY,
    ENEMY_JET,
    JET,
    airborne,
    new_world,
    of,
    put,
    run,
    track,
    with_weapon,
)

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core.defense import floor as defense_floor
from nexus.core.rules import Rules
from nexus.core.world import Claim, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.golden import shipped_config

SITE: UnitKind = "AIR_DEFENSE_SITE"
TARGET = {"COALITION": "fob-n-e", "ENEMY": "fob-n-w"}  # a FOB the other side owns
OUT_M = 9_000  # the jets' distance from the site: in AG_LIGHT range, a 50-tick flight


def rules(on: bool, pk: float = 1.0, *, first: bool = False) -> Rules:
    """The shipped rules with the key (and `combat.strike_structure_first` = `first`) set through
    the config, board and sensing off, AG_LIGHT's Pk fixed at `pk` everywhere in range (base `pk`,
    no range fall-off: `min_mult` 1)."""
    shipped = shipped_config(
        {"combat.overkill_check": on, "combat.strike_structure_first": first}
    ).rules
    base = dataclasses.replace(shipped, campaign=None, tasking=None, track_every_ticks=10**9)
    fixed = with_weapon(base, "AG_LIGHT", base_pk=pk)
    assert fixed.combat is not None and fixed.combat.overkill_check is on
    return dataclasses.replace(
        fixed, combat=dataclasses.replace(fixed.combat, pk_cap=1.0, min_mult=1.0)
    )


def scene(
    on: bool, side: Side = "COALITION", pk: float = 1.0, *, first: bool = False
) -> tuple[World, Entity, list[Entity]]:
    """Two of `side`'s strike jets holding STRIKE claims on the other side's FOB, `OUT_M` west of
    a tracked air-defense site that stands on the node; nothing else is there."""
    w = new_world(rules(on, pk, first=first))
    node = TARGET[side]
    x, y = w.rules.roads.pos[node]  # type: ignore[union-attr]  # rules are set above
    other: Side = "ENEMY" if side == "COALITION" else "COALITION"
    site = put(w, SITE, other, x, y)
    jet_kind = JET if side == "COALITION" else ENEMY_JET
    jets = [put(w, jet_kind, side, x - OUT_M, y + 10 * i, cmd=i + 1) for i in range(2)]
    job = strike(w, jets[0], node)  # one package: both claim the job (a board key is unique)
    job.claims[jets[1].id] = Claim(0, active=True)
    jets[1].job_id = job.id
    for jet in jets:
        track(w, jet, site)
    return w, site, jets


def bombs(events: list[Event]) -> list[WeaponFired]:
    return [f for f in of(events, WeaponFired) if f.weapon == "AG_LIGHT"]


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])  # both sides alike (EC-3)
def test_once_the_site_is_covered_the_jets_bomb_the_node_defenses(side: Side) -> None:
    w, site, jets = scene(True, side)
    node = TARGET[side]
    fired = bombs(run(w, 40))  # three volleys (ticks 1, 18, 35), none landed yet
    assert [(f.shooter_id, f.target_id, f.target_node_id) for f in fired] == [
        (jets[0].id, site.id, None),
        (jets[1].id, site.id, None),
        (jets[0].id, site.id, None),
        (jets[1].id, site.id, None),  # 4 x 35 = 140 >= 136: covered
        (jets[0].id, None, node),
        (jets[1].id, None, node),
    ]


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])
def test_without_the_check_every_bomb_goes_at_the_site(side: Side) -> None:
    w, site, _ = scene(False, side)
    fired = bombs(run(w, 40))
    assert len(fired) == 6 and all(f.target_id == site.id for f in fired)


def test_the_cover_is_expected_damage_so_a_likely_miss_takes_more_rounds() -> None:
    """At Pk 0.5 a bomb counts 17.5: eight are 140, so both jets spend all four on the site."""
    w, site, _ = scene(True, pk=0.5)
    fired = bombs(run(w, 60))
    assert len(fired) == 8 and all(f.target_id == site.id for f in fired)


def test_a_shot_that_would_fizzle_releases_the_cover() -> None:
    """A shot whose shooter is gone will fizzle (CB-3), so it counts 0: with the second jet gone,
    the first jet's two bombs (70) no longer cover the site and its next bomb goes at it again;
    with both jets there the same bomb goes at the node (the first test)."""
    w, site, jets = scene(True)
    run(w, 40)  # the site is covered (4 bombs) and two bombs went at the node; none landed
    w.remove(jets[1].id)
    jets[0].reload = [0] * len(jets[0].reload)
    (fired,) = bombs(run(w))
    assert (fired.shooter_id, fired.target_id) == (jets[0].id, site.id)


def test_a_shot_out_of_its_range_counts_nothing() -> None:
    """A shot whose target is now out of its shooter's weapon range will fizzle (CB-3): its Pk is
    None and it counts 0, not its base Pk. The second jet pulls 20 km away, so its two bombs at
    the site no longer cover it, and the first jet's next bomb goes at the site again."""
    w, site, jets = scene(True)
    run(w, 40)  # the site is covered (4 bombs, two from each jet); none landed
    jets[1].pos = Vec2(site.pos.x - 20_000, site.pos.y)  # beyond AG_LIGHT's 10 km
    jets[0].reload = [0] * len(jets[0].reload)
    (fired,) = bombs(run(w))
    assert (fired.shooter_id, fired.target_id) == (jets[0].id, site.id)


def test_a_landed_miss_releases_the_cover() -> None:
    """Pk 0.6 (21 a bomb): six in flight are 126, short of 136, so all six go at the site. The
    first lands at tick 51 and misses (seed 12345); five in flight (105) no longer cover it, so at
    tick 52 both jets fire at the site again. A hit there would have left 101 hp, covered by the
    105, and both would have bombed the node."""
    w, site, jets = scene(True, pk=0.6)
    for jet in jets:  # rounds enough to see the release
        jet.ammo = [99 if a == 4 else a for a in jet.ammo]
    events = run(w, 51)
    assert [(i.tick, i.target_id, i.hit) for i in of(events, WeaponImpact)] == [
        (51, site.id, False)
    ]
    fired = bombs(events + run(w))  # tick 52 fires before its impacts land
    assert [f.tick for f in fired] == [1, 1, 18, 18, 35, 35, 52, 52]
    assert all(f.target_id == site.id for f in fired)


def test_a_covered_unit_gives_way_to_the_next_unit() -> None:
    """Units too: an ENEMY_CONVOY (80 hp, armor 0) is covered by two bombs (100), so the first
    volley takes the nearer convoy, the second the other, and the third, both covered, the node."""
    w, site, jets = scene(True)
    del w.contacts[jets[0].side][site.id]
    x, y = site.pos.x, site.pos.y
    near, far = put(w, CONVOY, "ENEMY", x - 100, y), put(w, CONVOY, "ENEMY", x, y)
    for t in (near, far):
        track(w, jets[0], t)
    fired = bombs(run(w, 40))
    assert [(f.target_id, f.target_node_id) for f in fired] == [
        (near.id, None),
        (near.id, None),
        (far.id, None),
        (far.id, None),
        (None, TARGET["COALITION"]),
        (None, TARGET["COALITION"]),
    ]


@pytest.mark.parametrize("on", [True, False])
def test_node_defenses_are_covered_too(on: bool) -> None:
    """A FOB's 300 defense HP is covered by six bombs (Pk 1, 50 each, armor 0): with no unit there
    the jets fire three volleys at it and hold the fourth (tick 52: one hit landed, 250 left, five
    in flight cover it). Off, the fourth volley goes too."""
    w, site, jets = scene(on)
    w.remove(site.id)
    for jet in jets:
        jet.ammo = [99 if a == 4 else a for a in jet.ammo]
    fired = bombs(run(w, 52))
    assert all(f.target_node_id == TARGET["COALITION"] for f in fired)
    assert len(fired) == (6 if on else 8)


@pytest.mark.parametrize("on", [True, False])
def test_a_bridge_is_covered_too(on: bool) -> None:
    """A bridge at 50 hp: one bomb in flight (Pk 1, 50) covers it, so the second jet holds."""
    w = new_world(rules(on))
    x, y = w.rules.roads.pos["bridge-n"]  # type: ignore[union-attr]
    w.bridge_hp["bridge-n"] = 50
    for i in range(2):
        strike(w, put(w, JET, "COALITION", x - OUT_M, y + 10 * i, cmd=i + 1), "bridge-n")
    fired = bombs(run(w))
    assert [f.target_node_id for f in fired] == ["bridge-n"] * (1 if on else 2)


def test_with_strike_first_covered_defenses_give_way_to_the_site() -> None:
    """`combat.strike_structure_first` on: the claimants bomb the FOB's defenses first (300 HP,
    six bombs at Pk 1). At tick 52 one hit has landed (250 left) and five are in flight (250): the
    node is covered, so strike-first falls through and both jets bomb the site."""
    w, site, jets = scene(True, first=True)
    for jet in jets:
        jet.ammo = [99 if a == 4 else a for a in jet.ammo]
    fired = bombs(run(w, 52))
    node = TARGET["COALITION"]
    assert [(f.tick, f.target_id, f.target_node_id) for f in fired] == [
        *[(t, None, node) for t in (1, 1, 18, 18, 35, 35)],
        (52, site.id, None),
        (52, site.id, None),
    ]


@pytest.mark.parametrize("on", [True, False])
def test_the_idle_floor_counts_in_what_a_node_has_left(on: bool) -> None:
    """Nobody plays (no COMMANDER unit), so the coalition sanctuary cannot go below
    `sanctuary_min_hp` 1: at 51 HP it has 50 left, which one bomb (50, Pk 1) covers, so the
    second ENEMY jet holds; counted from the raw 51 it would fire too."""
    w = new_world(rules(on))
    r = w.rules
    assert r is not None
    node = r.sanctuary
    w.defense_hp[node] = 51
    x, y = r.roads.pos[node]
    jets = [put(w, ENEMY_JET, "ENEMY", x - 2_000, y + 10 * i) for i in range(2)]
    assert w.viewer_units() == 0 and defense_floor(w, r, node) == 1
    fired = bombs(run(w))
    assert [(f.shooter_id, f.target_node_id) for f in fired] == [
        (j.id, node) for j in jets[: 1 if on else 2]
    ]


@pytest.mark.parametrize("on", [True, False])
def test_a_sam_site_holds_while_its_missiles_cover_an_airborne_jet(on: bool) -> None:
    """An airborne jet dies at Disabled, so it has 100 - 9 = 91 hp left. SAM at base Pk 0.95 on
    evasion 0.7 is Pk 0.665, 46.55 a missile: two in flight (93.1) cover it, so the site fires at
    ticks 1 and 26 and holds at 51 and 76 (a 250-tick flight at 100 m/s over 15 km, so none has
    landed). Counted to 0 hp (100) it would fire a third; off, every reload."""
    base = rules(on)
    sam = with_weapon(base, "SAM", base_pk=0.95, speed_mps=100.0)
    w = new_world(sam)
    site = put(w, SITE, "COALITION", 0)
    jet = airborne(put(w, ENEMY_JET, "ENEMY", 15_000))
    track(w, site, jet)
    fired = [f for f in of(run(w, 100), WeaponFired) if f.weapon == "SAM"]
    assert all(f.target_id == jet.id for f in fired)
    assert [f.tick for f in fired] == ([1, 26] if on else [1, 26, 51, 76])


def test_overkill_fire_survives_a_save_and_load_with_shots_in_flight() -> None:
    def once(reload: bool) -> tuple[str, list[str]]:
        w, _, _ = scene(True, pk=0.7)
        events = run(w, 20)
        assert w.shots  # bombs in flight
        if reload:
            w = load(save(w))
            w.rules = rules(True, 0.7)
        events += run(w, 100)
        return state_hash(w), [e.model_dump_json() for e in events]

    straight, reloaded = once(False), once(True)
    assert straight == reloaded
    assert any('"target_node_id":"fob-n-e"' in e for e in straight[1])
