"""A landed aircraft is a GROUND target (Q-MV-14, NX-450; COMBAT CB-1, CB-3, CB-7).

Owner, 2026-10-27 (#412): a grounded aircraft takes damage from air-to-ground bombs and from ground
fire; a SAM, or any weapon that targets only AIR, can neither target nor hit it.
"""

import dataclasses

from test_combat import COMBAT, JET, RULES, airborne, new_world, of, pk_of, put, run, sure, track
from test_tasking import new_world as campaign_world
from test_tasking import put as put_at

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core.follow import _Ctx, _find_threats, _own_reach
from nexus.core.rules import Rules
from nexus.core.world import Contact, Entity, Vec2, World, state_hash

ADS: UnitKind = (
    "AIR_DEFENSE_SITE"  # AAA_GUN (NOE, LOW) and SAM (LOW, MED, HIGH); MED is a jet's band
)
ENEMY_JET: UnitKind = "ENEMY_STRIKE_FIGHTER"  # AG_LIGHT (GROUND) and AA_LIGHT (AIR, LOW and MED)
INFANTRY: UnitKind = "GARRISON_INFANTRY"  # SMALL_ARMS: GROUND only, a gun, 1,500 m


def certain(weapon_id: str) -> Rules:
    """`sure(weapon_id)` with every jet's evasion 1.0: a shot in the full-Pk range always hits."""
    rules = sure(weapon_id)
    assert rules.combat is not None
    units = {
        k: dataclasses.replace(u, evasion=1.0) if k in (JET, ENEMY_JET) else u
        for k, u in rules.combat.units.items()
    }
    return dataclasses.replace(rules, combat=dataclasses.replace(rules.combat, units=units))


def sam_scene(rules: Rules | None = None) -> tuple[World, Entity, Entity]:
    """An enemy SAM site and a coalition jet parked 5 km from it, tracked."""
    w = new_world() if rules is None else new_world(rules)
    site = put(w, ADS, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 5_000, cmd=1)  # LANDED, MED band
    track(w, site, jet)
    return w, site, jet


def test_a_sam_site_in_range_never_fires_at_a_parked_jet() -> None:
    w, site, jet = sam_scene()
    assert jet.state == "LANDED" and jet.alt_band == "MED"  # the band it would be shot in
    assert of(run(w, 40), WeaponFired) == []  # 24 s: more than a SAM reload (15 s)
    assert jet.hp == 100 and site.ammo == [400, 8]


def test_an_airborne_jet_is_a_normal_air_target_again() -> None:
    w, site, jet = sam_scene()
    assert of(run(w, 3), WeaponFired) == []
    airborne(jet)
    fired = of(run(w), WeaponFired)
    assert [(f.shooter_id, f.target_id, f.weapon) for f in fired] == [(site.id, jet.id, "SAM")]


def test_an_air_to_ground_weapon_fires_at_a_parked_jet_and_damages_it() -> None:
    w = new_world(certain("AG_LIGHT"))
    bomber = put(w, ENEMY_JET, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 2_000, cmd=1)
    track(w, bomber, jet)
    fired = of(run(w), WeaponFired)
    # AG_LIGHT only: the strike fighter's AA_LIGHT is an AIR weapon and the jet is on the ground.
    assert [(f.target_id, f.weapon) for f in fired] == [(jet.id, "AG_LIGHT")]
    # 2,000 m at 300 m/s is 6.67 s, 11.1 ticks of 0.6 s: impact on running tick 1 + 12.
    (impact,) = of(run(w, 12), WeaponImpact)
    assert (impact.target_id, impact.hit) == (jet.id, True)
    assert jet.hp == 50  # 100 hp, AG_LIGHT damage 50, strike fighter armor 0.0 (content)


def test_a_ground_units_gun_hits_a_parked_jet() -> None:
    w = new_world(certain("SMALL_ARMS"))
    infantry = put(w, INFANTRY, "COALITION", 0)
    jet = put(w, ENEMY_JET, "ENEMY", 500)  # LANDED; full Pk up to 750 m
    track(w, infantry, jet)
    events = run(w)
    assert [(f.target_id, f.weapon) for f in of(events, WeaponFired)] == [(jet.id, "SMALL_ARMS")]
    (impact,) = of(events, WeaponImpact)
    assert impact.hit is True and jet.hp == 92  # SMALL_ARMS damage 8, armor 0.0 (content)
    # Airborne it is out of SMALL_ARMS' reach: a GROUND-only weapon.
    airborne(jet)
    assert of(run(w, 10), WeaponFired) == []


def test_a_sam_shot_in_flight_fizzles_when_its_target_lands() -> None:
    w, _site, jet = sam_scene(certain("SAM"))
    airborne(jet)
    (fired,) = of(run(w), WeaponFired)
    assert fired.weapon == "SAM" and fired.impact_tick > 2
    jet.state = "LANDED"  # it lands while the missile flies
    before = w.rng.to_state()
    impacts = of(run(w, fired.impact_tick - 1), WeaponImpact)
    assert [(i.target_id, i.hit) for i in impacts] == [(jet.id, False)]
    assert w.rng.to_state() == before and jet.hp == 100  # CB-3: a fizzle draws nothing


def test_a_bomb_in_flight_fizzles_when_its_target_takes_off() -> None:
    w = new_world(certain("AG_LIGHT"))
    bomber = put(w, ENEMY_JET, "ENEMY", 0)
    bomber.ammo[1] = 0  # no AA_LIGHT: only the bomb can touch the jet once it is airborne
    jet = put(w, JET, "COALITION", 2_000, cmd=1)
    track(w, bomber, jet)
    (fired,) = of(run(w), WeaponFired)
    airborne(jet)  # it leaves the ground while the bomb falls
    before = w.rng.to_state()
    impacts = of(run(w, fired.impact_tick - 1), WeaponImpact)
    assert [(i.target_id, i.weapon, i.hit) for i in impacts] == [(jet.id, "AG_LIGHT", False)]
    assert w.rng.to_state() == before and jet.hp == 100  # CB-3: a fizzle draws nothing


def test_an_escort_reaches_a_parked_jet_only_with_a_ground_weapon() -> None:
    w = new_world()
    fighter = put(w, "ENEMY_FIGHTER", "ENEMY", 0)  # AA_MISSILE: AIR only, 30 km
    infantry = put(w, INFANTRY, "ENEMY", 0)
    jet = put(w, JET, "COALITION", 1_000, cmd=1)
    assert w.rules is not None
    assert (_own_reach(w.rules, fighter, jet), _own_reach(w.rules, infantry, jet)) == (0.0, 1500.0)
    airborne(jet)
    assert (_own_reach(w.rules, fighter, jet), _own_reach(w.rules, infantry, jet)) == (
        30000.0,
        0.0,
    )


def test_a_parked_group_member_is_threatened_by_ground_weapons_not_by_air_only_ones() -> None:
    """Escort threats (`follow._find_threats`) use the same target class as combat."""
    w = campaign_world()
    jet = put_at(w, JET, "west-airbase")  # LANDED
    w.contacts["COALITION"] = {}
    foes: tuple[tuple[UnitKind, float], ...] = (
        ("ENEMY_ARMOR", 3_000.0),
        ("ENEMY_FIGHTER", 10_000.0),
    )
    for kind, dx in foes:
        foe = w.spawn(kind, "ENEMY", "ENEMY_DIRECTOR", Vec2(jet.pos.x + dx, jet.pos.y))
        w.contacts["COALITION"][foe.id] = Contact(kind, foe.pos, Vec2(0, 0))
    rules = w.rules
    assert rules is not None

    def threats() -> list[UnitKind]:
        return [t.kind for t in _find_threats(_Ctx(w, rules), "COALITION", [jet])]

    assert threats() == ["ENEMY_ARMOR"]  # AG_CANNON reaches 4 km; AA_MISSILE cannot hit it
    airborne(jet)
    assert threats() == ["ENEMY_FIGHTER"]  # airborne: AA_MISSILE (30 km), not the GROUND gun


def test_landed_and_airborne_targets_replay_identically() -> None:
    """Same seed, same scene, same landing and takeoff ticks: same events and state hash."""

    def play() -> tuple[list[dict[str, object]], str]:
        w = new_world(seed=4242)
        site = put(w, ADS, "ENEMY", 0)
        bomber = put(w, ENEMY_JET, "ENEMY", -1_000)
        infantry = put(w, INFANTRY, "ENEMY", 4_000)
        jets = [put(w, JET, "COALITION", x, cmd=i) for i, x in enumerate((3_000, 4_500, 6_000), 1)]
        for watcher in (site, bomber, infantry):
            for jet in jets:
                track(w, watcher, jet)
        events = run(w, 5)
        airborne(jets[0])
        events += run(w, 20)
        jets[0].state = "LANDED"
        airborne(jets[2])
        events += run(w, 40)
        return [e.model_dump() for e in events], state_hash(w)

    first, second = play(), play()
    assert first == second
    assert any(e["kind"] == "WeaponFired" for e in first[0])


# --- Q-MV-18: a parked aircraft does not evade; GROUND masking -----------------------------------


def test_a_landed_jet_has_no_evasion_factor() -> None:
    """Q-MV-18: Pk on a parked jet is the ground-target Pk with evasion 1.0, not the kind's 0.7."""
    w = new_world()
    armor = put(w, "ENEMY_ARMOR", "ENEMY", 0)  # AG_CANNON: base_pk 0.6, 4 km
    jet = put(w, JET, "COALITION", 1_000, cmd=1)  # 25% of the range: range factor 1.0
    track(w, armor, jet)
    cannon = COMBAT.weapons["AG_CANNON"]
    assert COMBAT.units[JET].evasion == 0.7  # content: what a flying jet would get
    assert pk_of(w, armor, jet, cannon) == 0.6  # base_pk x track 1.0 x range 1.0, nothing else


def test_a_landed_jet_in_a_masking_region_takes_the_masked_multiplier_airborne_at_med_not() -> None:
    """strait-1's northern-hills covers x 150-260 km, y 0-35 km: ground there is masked (x0.5),
    a MED aircraft is not (`fow.masked_alt_bands` is NOE and LOW)."""
    units = {**COMBAT.units, JET: dataclasses.replace(COMBAT.units[JET], evasion=1.0)}
    w = new_world(dataclasses.replace(RULES, combat=dataclasses.replace(COMBAT, units=units)))
    shooter = put(w, ENEMY_JET, "ENEMY", 200_000, 10_000)
    jet = put(w, JET, "COALITION", 201_000, 10_000, cmd=1)  # LANDED, MED band
    track(w, shooter, jet)
    both = dataclasses.replace(
        COMBAT.weapons["AG_LIGHT"], targets=frozenset({"GROUND", "AIR"}), bands=frozenset({"MED"})
    )
    assert w.rules is not None and w.rules.combat is not None
    assert pk_of(w, shooter, jet, both, w.rules.combat) == 0.7 * 0.5  # base_pk x masked_mult
    airborne(jet)
    assert pk_of(w, shooter, jet, both, w.rules.combat) == 0.7  # MED: never masked


# --- Q-MV-19: a landed aircraft fires no AIR weapon --------------------------------------------


def test_a_parked_fighter_does_not_fire_at_an_aircraft_overhead_until_airborne() -> None:
    w = new_world()
    fighter = put(w, "ENEMY_FIGHTER", "ENEMY", 0)  # AA_MISSILE only; LANDED
    jet = airborne(put(w, JET, "COALITION", 2_000, cmd=1))
    track(w, fighter, jet)
    assert of(run(w, 5), WeaponFired) == []
    airborne(fighter)
    fired = of(run(w), WeaponFired)
    assert [(f.shooter_id, f.target_id, f.weapon) for f in fired] == [
        (fighter.id, jet.id, "AA_MISSILE")
    ]


def test_a_parked_strike_jet_bombs_a_ground_unit_but_its_air_gun_stays_silent() -> None:
    w = new_world()
    striker = put(w, ENEMY_JET, "ENEMY", 0)  # AG_LIGHT and AA_LIGHT; LANDED
    armor = put(w, INFANTRY, "COALITION", 2_000)
    jet = airborne(put(w, JET, "COALITION", 2_000, 500, cmd=1))  # in AA_LIGHT's reach and band
    track(w, striker, armor)
    track(w, striker, jet)
    fired = of(run(w), WeaponFired)
    assert [(f.target_id, f.weapon) for f in fired if f.shooter_id == striker.id] == [
        (armor.id, "AG_LIGHT")
    ]
