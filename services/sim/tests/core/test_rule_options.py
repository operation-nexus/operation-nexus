"""NX-388 part 2 (Q-CFG-16, Q-DEV-21): small fixed rules become balance options whose defaults
keep today's behaviour, and five keys become hot-reloadable.

Each option: the shipped value is the old rule, a non-default value set through the loader reaches
`Rules`, the kernel follows it (expected values worked out by hand from the shipped numbers, see
`test_capture.py`), and the loader refuses a bad value. Hot reload: no reload path is built yet
(CONFIG-AND-CONTENT §5), so "re-read live" is shown by swapping `World.rules` mid-run, which is
what a reload that rebuilds `Rules` does: the next use reads the new value.
"""

import dataclasses
from typing import Any

import pytest
from test_capture import (
    ARMOR,
    INFANTRY,
    NEUTRAL_FOB,
    gain,
    new_world,
    of,
    per_tick,
    progress,
    put,
    run,
)
from test_combat import COMBAT, JET
from test_combat import RULES as COMBAT_RULES
from test_combat import new_world as combat_world
from test_combat import put as combat_put

from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core import combat as combat_mod
from nexus.core.combat import _hit
from nexus.core.defense import damage
from nexus.core.director import night_capped
from nexus.core.fog import _marker, side_view
from nexus.core.rules import Rules
from nexus.core.tasking_gen import _strike
from nexus.core.world import CaptureBar, Contact, Vec2, World, roll_crew, state_hash
from nexus.runtime.campaign_config import start_campaign
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config

ENEMY_FOB, FORWARD, SANCTUARY, ENEMY_HQ = "fob-n-e", "west-airbase", "haven", "static-hq"


def with_rules(w: World, **parts: dict[str, Any]) -> World:
    """`w` with `World.rules` sub-rules replaced: `capture={...}`, `defense={...}`..."""
    rules = w.rules
    assert rules is not None
    w.rules = dataclasses.replace(
        rules,
        **{name: dataclasses.replace(getattr(rules, name), **ch) for name, ch in parts.items()},
    )
    return w


def rules_of(**overrides: object) -> Rules:
    return shipped_config({k.replace("__", "."): v for k, v in overrides.items()}).rules


# --- defaults and the loader -------------------------------------------------------------------


def test_the_defaults_are_the_old_fixed_rules() -> None:
    r = shipped_config({}).rules
    assert r.capture and r.defense and r.campaign and r.combat
    assert r.capture.requires_defenses_down is True and r.capture.air_weight is None
    assert r.capture.quiet_sides == {"COALITION"}
    assert (r.defense.idle_floor, r.defense.sanctuary_min_hp) == (True, 1)
    assert (r.campaign.hq_capture, r.campaign.objective_pick) == (True, "uniform")
    assert r.combat.facility_indestructible is True


def test_non_default_options_reach_the_rules() -> None:
    r = rules_of(
        capture__requires_defenses_down=False,
        capture__air_counts=True,
        capture__air_weight=0.25,
        capture__quiet_sides=["ENEMY"],
        campaign__idle_floor__enabled=False,
        campaign__idle_floor__sanctuary_min_hp=40,
        campaign__victory__hq_capture=False,
        combat__facility_indestructible=False,
    )
    assert r.capture and r.defense and r.campaign and r.combat
    assert r.capture.requires_defenses_down is False and r.capture.air_weight == 0.25
    assert r.capture.quiet_sides == {"ENEMY"}
    assert (r.defense.idle_floor, r.defense.sanctuary_min_hp) == (False, 40)
    assert r.campaign.hq_capture is False and r.combat.facility_indestructible is False


def test_air_weight_is_read_only_when_air_counts() -> None:
    r = rules_of(capture__air_weight=3.0)
    assert r.capture is not None and r.capture.air_weight is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("campaign.idle_floor.sanctuary_min_hp", 0),
        ("campaign.idle_floor.sanctuary_min_hp", 1001),  # above capture.defense_hp.SANCTUARY
        ("campaign.idle_floor.enabled", "maybe"),
        ("campaign.victory.hq_capture", "maybe"),
        ("campaign.objective_pick", "weighted"),
        ("capture.requires_defenses_down", "maybe"),
        ("capture.air_counts", "maybe"),
        ("capture.air_weight", 0),
        ("capture.quiet_sides", ["NEUTRAL"]),
        ("combat.facility_indestructible", "maybe"),
    ],
)
def test_the_loader_rejects_a_bad_option(key: str, value: object) -> None:
    with pytest.raises(ConfigError):
        shipped_config({key: value})


# --- campaign.victory.hq_capture ---------------------------------------------------------------


@pytest.mark.parametrize(("hq_capture", "ends"), [(True, 1), (False, 0)])
def test_holding_the_enemy_hq_wins_only_with_hq_capture(hq_capture: bool, ends: int) -> None:
    w = with_rules(new_world(), campaign={"hq_capture": hq_capture})
    w.owner[ENEMY_HQ] = "COALITION"
    assert len(of(run(w), CampaignEnded)) == ends


# --- campaign.idle_floor ------------------------------------------------------------------------


@pytest.mark.parametrize(("enabled", "bar"), [(True, False), (False, True)])
def test_the_forward_airbase_freezes_with_nobody_playing_only_with_the_idle_floor(
    enabled: bool, bar: bool
) -> None:
    w = with_rules(new_world(), defense={"idle_floor": enabled})
    put(w, ARMOR, "ENEMY", FORWARD)  # no viewer unit anywhere
    run(w)
    assert (FORWARD in w.capture) is bar


@pytest.mark.parametrize(
    ("enabled", "min_hp", "left"), [(True, 1, 1), (True, 40, 40), (False, 40, 0)]
)
def test_the_sanctuary_floor_follows_the_idle_floor_keys(
    enabled: bool, min_hp: int, left: int
) -> None:
    w = with_rules(new_world(), defense={"idle_floor": enabled, "sanctuary_min_hp": min_hp})
    assert w.rules is not None
    w.defense_hp[SANCTUARY] = 1000
    out: list[Event] = []
    damage(w, w.rules, SANCTUARY, 5000, out)
    assert w.defense_hp[SANCTUARY] == left
    assert len(of(out, NodeDefensesDown)) == (left == 0)


@pytest.mark.parametrize(("enabled", "run_ticks"), [(True, 0), (False, 5)])
def test_the_defeat_clock_pauses_with_nobody_playing_only_with_the_idle_floor(
    enabled: bool, run_ticks: int
) -> None:
    w = with_rules(new_world(), defense={"idle_floor": enabled})
    w.defense_hp[SANCTUARY] = 0
    run(w, 5)
    assert w.campaign.defeat_ticks == run_ticks


# --- capture.requires_defenses_down -------------------------------------------------------------


def test_a_bar_starts_on_a_defended_node_only_without_the_defenses_down_rule() -> None:
    w = new_world()
    w.defense_hp[ENEMY_FOB] = 300
    put(w, INFANTRY, "COALITION", ENEMY_FOB)
    assert of(run(w), CaptureStarted) == [] and ENEMY_FOB not in w.capture
    w2 = with_rules(new_world(), capture={"requires_defenses_down": False})
    w2.defense_hp[ENEMY_FOB] = 300
    put(w2, INFANTRY, "COALITION", ENEMY_FOB)
    (started,) = of(run(w2), CaptureStarted)
    # 120 s x quiet 0.6 x empty base 0.5 (the site never garrisons) = 36 world s
    assert started.node_id == ENEMY_FOB and progress(w2, ENEMY_FOB) == per_tick(36.0)


# --- capture.air_counts / air_weight ------------------------------------------------------------


def flying(w: World, kind: Any = JET, side: Any = "COALITION") -> None:
    jet = put(w, kind, side, NEUTRAL_FOB, state="EN_ROUTE")
    jet.path = [Vec2(0.0, 0.0)]  # moving away: a few hundred metres in one tick, still in range


@pytest.mark.parametrize(("weight", "time_s"), [(None, None), (1.0, 72.0), (4.0, 36.0)])
def test_an_airborne_aircraft_captures_only_with_air_counts(
    weight: float | None, time_s: float | None
) -> None:
    w = with_rules(new_world(), capture={"air_weight": weight})
    flying(w)
    run(w)
    expected = None if time_s is None else CaptureBar("COALITION", per_tick(time_s))
    assert w.capture.get(NEUTRAL_FOB) == expected  # 72 s / 4 ** 0.5 = 36 s


def test_an_airborne_capturer_never_contests() -> None:
    w = with_rules(new_world(), capture={"air_weight": 1.0})
    flying(w, "ENEMY_STRIKE_FIGHTER", "ENEMY")
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)  # armed: it contests the jet, not the reverse
    run(w)
    assert w.capture[NEUTRAL_FOB] == CaptureBar("COALITION", per_tick(72.0))


# --- capture.quiet_sides ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sides", "side", "time_s"),
    [
        (frozenset({"COALITION"}), "ENEMY", 120.0),
        (frozenset({"COALITION", "ENEMY"}), "ENEMY", 72.0),
        (frozenset(), "COALITION", 120.0),
    ],
)
def test_the_quiet_multiplier_applies_to_the_quiet_sides(
    sides: frozenset[str], side: str, time_s: float
) -> None:
    w = with_rules(new_world(), capture={"quiet_sides": sides})
    put(w, INFANTRY if side == "COALITION" else ARMOR, side, NEUTRAL_FOB)  # type: ignore[arg-type]
    assert gain(w) == per_tick(time_s)


# --- combat.facility_indestructible -------------------------------------------------------------


@pytest.mark.parametrize("indestructible", [True, False])
def test_a_facility_dies_at_zero_hp_only_without_the_floor(indestructible: bool) -> None:
    cr = dataclasses.replace(COMBAT, facility_indestructible=indestructible)
    rules = dataclasses.replace(COMBAT_RULES, combat=cr)
    w = combat_world(rules)
    shooter = combat_put(w, JET, "COALITION", 0)
    site = combat_put(w, "AIR_DEFENSE_SITE", "ENEMY", 1_000)
    light = dataclasses.replace(COMBAT.weapons["SAM"], damage=20)
    heavy = dataclasses.replace(COMBAT.weapons["SAM"], damage=500)
    out: list[Event] = []
    _hit(w, rules, cr, shooter, site, light, out)
    # 150 hp, armor 0.3: floor(20 x 0.7) = 14 off; a facility keeps no hits either way
    assert site.hp == 136 and site.hits == []
    combat_mod.validate(w, rules)
    _hit(w, rules, cr, shooter, site, heavy, out)
    if indestructible:
        assert w.find(site.id) is site and site.hp == 14 and of(out, UnitDestroyed) == []
    else:
        (dead,) = of(out, UnitDestroyed)
        assert (dead.entity_id, dead.killer_id) == (site.id, shooter.id)
        assert w.find(site.id) is None


@pytest.mark.parametrize("indestructible", [True, False])
def test_a_destroyed_facility_leaves_no_marker_contact_or_strike_target(
    indestructible: bool,
) -> None:
    config = shipped_config({"combat.facility_indestructible": indestructible})
    w = start_campaign("0192f3a4-5b6c-7d8e-9f01-23456789abcd", 1, config)
    rules, tr = config.rules, config.rules.tasking
    assert rules.combat is not None and tr is not None
    (site,) = [e for e in w.entities() if e.base_id == ENEMY_FOB]
    shooter = w.spawn(JET, "COALITION", "AI_GARRISON", site.pos)
    w.markers["COALITION"][site.id] = _marker(rules, site, 0)  # the coalition has found it
    w.contacts["COALITION"][site.id] = Contact(site.kind, site.pos, site.vel, None, False)
    w.contacts["ENEMY"][shooter.id] = Contact(shooter.kind, shooter.pos, shooter.vel, None, False)

    def strikes() -> list[str]:
        return [j.key for j in _strike(w, rules, tr, "COALITION", side_view(w, "COALITION"))]

    assert strikes() == [f"strike:{ENEMY_FOB}"]  # its marker makes the FOB a strike target
    heavy = dataclasses.replace(rules.combat.weapons["SAM"], damage=500)
    _hit(w, rules, rules.combat, shooter, site, heavy, [])
    held = [site.id in w.markers[s] or site.id in w.contacts[s] for s in ("COALITION", "ENEMY")]
    assert held == ([True, False] if indestructible else [False, False])
    # a surviving site keeps its last-seen marker until it is seen again; a dead one is gone
    assert strikes() == ([f"strike:{ENEMY_FOB}"] if indestructible else [])
    assert shooter.id in w.contacts["ENEMY"]  # other contacts are kept


# --- hot reload: the five keys are read at use ---------------------------------------------------


def test_quiet_floor_and_quiet_ref_are_read_on_the_next_tick() -> None:
    w = new_world()
    put(w, INFANTRY, "COALITION", NEUTRAL_FOB)
    assert gain(w) == per_tick(72.0)
    with_rules(w, capture={"quiet_floor": 1.0})
    assert gain(w) == per_tick(120.0)
    w2 = new_world()
    for i in range(25):  # 25 viewer units: 0.8 at quiet_ref 50, 1.0 at quiet_ref 25
        put(w2, INFANTRY, "COALITION", "haven", n=100 + i)
    put(w2, INFANTRY, "COALITION", NEUTRAL_FOB)
    assert gain(w2) == per_tick(96.0)
    with_rules(w2, capture={"quiet_ref": 25})
    assert gain(w2) == per_tick(120.0)


def test_objective_period_applies_from_the_next_objective() -> None:
    w = with_rules(new_world(), campaign={"objectives_on": True})
    run(w)
    first = w.objective
    assert w.rules and w.rules.campaign and first is not None
    assert first.deadline == 1 + w.rules.campaign.objective_period_ticks
    with_rules(w, campaign={"objective_period_ticks": 50})
    assert w.objective is first and w.objective.deadline == first.deadline  # this one keeps it
    w.objective = None  # it resolved
    run(w)
    assert w.objective is not None and w.objective.deadline == w.campaign.running_ticks + 50


def test_the_night_cap_is_read_at_each_check() -> None:
    w = new_world()
    assert w.rules and w.rules.director
    static = w.director["ENEMY"]
    static.last_flip = 100
    dr = w.rules.director
    assert night_capped(static, dr, 200)
    assert not night_capped(static, dataclasses.replace(dr, night_cap_ticks=100), 200)


def test_crew_marker_min_applies_to_markers_placed_after_it() -> None:
    sure = dataclasses.replace(COMBAT.units[JET], crew_survival=1.0)
    cr = dataclasses.replace(COMBAT, units={**COMBAT.units, JET: sure})
    w = combat_world(dataclasses.replace(COMBAT_RULES, combat=cr))
    roll_crew(w, combat_put(w, JET, "COALITION", 0), [])
    with_rules(w, combat={"crew_marker_ticks": 7})
    roll_crew(w, combat_put(w, JET, "COALITION", 10), [])
    first, second = w.crew_markers.values()
    assert first.expires == 1 + cr.crew_marker_ticks and second.expires == 1 + 7


# --- determinism ---------------------------------------------------------------------------------


def test_a_run_with_every_option_flipped_is_deterministic() -> None:
    def scenario() -> tuple[str, list[dict[str, Any]]]:
        w = with_rules(
            new_world(),
            capture={
                "requires_defenses_down": False,
                "air_weight": 2.0,
                "quiet_sides": frozenset({"ENEMY"}),
            },
            defense={"idle_floor": False},
            campaign={"hq_capture": False},
        )
        w.defense_hp[ENEMY_FOB] = 300
        put(w, INFANTRY, "COALITION", ENEMY_FOB)
        put(w, ARMOR, "ENEMY", NEUTRAL_FOB)
        flying(w)
        events = run(w, 300)
        return state_hash(w), [e.model_dump() for e in events]

    assert scenario() == scenario()
