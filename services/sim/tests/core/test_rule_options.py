"""NX-388 part 2 (Q-CFG-16, Q-DEV-21): small fixed rules become balance options whose defaults
keep today's behaviour, and five keys become hot-reloadable. Part 2b: the Director's starting tier,
tier step, AI shooter provocation and capture-slot tiers, the AI garrison's job sets, a viewer
displacing an AI claimant, and the order a rebase leaves.

Each option: the shipped value is the old rule, a non-default value set through the loader reaches
`Rules`, the kernel follows it (expected values worked out by hand from the shipped numbers, see
`test_capture.py`), and the loader refuses a bad value. Hot reload: no reload path is built yet
(CONFIG-AND-CONTENT §5), so "re-read live" is shown by swapping `World.rules` mid-run, which is
what a reload that rebuilds `Rules` does: the next use reads the new value.
"""

import dataclasses
from fractions import Fraction
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
from test_combat import COMBAT, CONVOY, JET, sure, track
from test_combat import INFANTRY as GRUNT
from test_combat import RULES as COMBAT_RULES
from test_combat import new_world as combat_world
from test_combat import put as combat_put
from test_combat import run as fight_run
from test_director import DR, MICRO, valid_after, view
from test_director import RULES as DIRECTOR_RULES
from test_launch import skip
from test_pol import live_ops, with_director
from test_pol import new_world as pol_world
from test_pol import window as pol_window
from test_tasking import AI, PATROL_TR, TR, board_pass, kinds, post, pw
from test_tasking import RULES as TASK_RULES
from test_tasking import new_world as task_world
from test_tasking import put as task_put

from nexus.contracts.gen.common.enums import JobKind, ThreatTier
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core import combat as combat_mod
from nexus.core.combat import _hit
from nexus.core.defense import damage
from nexus.core.director import decide, night_capped
from nexus.core.fog import _marker, side_view
from nexus.core.provocation import suffered_defense_hit
from nexus.core.provocation import validate as director_validate
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking_gen import _strike
from nexus.core.world import (
    CaptureBar,
    Contact,
    DirectorState,
    Vec2,
    World,
    roll_crew,
    state_hash,
)
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


# --- part 2b: defaults, the loader ---------------------------------------------------------------


def test_the_part_2b_defaults_are_the_old_fixed_rules() -> None:
    r = shipped_config({}).rules
    assert r.director and r.tasking
    assert (r.director.start_tier, r.director.max_step) == ("PATTERN_OF_LIFE", 1)
    assert r.director.ai_shooter_mult == 0
    assert r.director.capture_slot_tiers == {"PATTERN_OF_LIFE"}
    assert r.tasking.ai_jobs == {"DEFEND", "RESUPPLY", "SCOUT"}
    assert r.tasking.ai_excluded_jobs == {"ESCORT_CONVOY", "PATROL"}
    assert r.tasking.human_displaces_ai is True and r.rebase_order == "HOLD"


def test_non_default_part_2b_options_reach_the_rules() -> None:
    r = rules_of(
        director__tier__start="BRAVO",
        director__tier__max_step=2,
        director__provocation__ai_shooter_mult=0.5,
        director__pol__capture_slot_tiers=["ALPHA", "BRAVO"],
        tasking__ai_jobs=["DEFEND", "STRIKE"],
        tasking__ai_excluded_jobs=[],
        tasking__human_displaces_ai=False,
    )
    assert r.director and r.tasking
    assert (r.director.start_tier, r.director.max_step) == ("BRAVO", 2)
    assert r.director.ai_shooter_mult == Fraction(1, 2)
    assert r.director.capture_slot_tiers == {"ALPHA", "BRAVO"}
    assert r.tasking.ai_jobs == {"DEFEND", "STRIKE"} and r.tasking.ai_excluded_jobs == set()
    assert r.tasking.human_displaces_ai is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("director.tier.start", "CHARLIE"),
        ("director.tier.max_step", 0),
        ("director.tier.max_step", 3),
        ("director.provocation.ai_shooter_mult", -0.5),
        ("director.pol.capture_slot_tiers", ["CHARLIE"]),
        ("tasking.ai_jobs", ["REPAIR_BRIDGE"]),
        ("tasking.ai_jobs", ["DEFEND", "PATROL"]),  # also in ai_excluded_jobs
        ("tasking.ai_jobs", ["DEFEND", "INTERCEPT"]),  # INTERCEPT has its own rule
        ("tasking.ai_excluded_jobs", ["INTERCEPT"]),
        ("tasking.human_displaces_ai", "maybe"),
        ("slots.rebase_order", "GOTO"),  # GOTO never ends for a truck with cargo aboard
    ],
)
def test_the_loader_rejects_a_bad_part_2b_option(key: str, value: object) -> None:
    with pytest.raises(ConfigError):
        shipped_config({key: value})


# --- director.tier.start ------------------------------------------------------------------------

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"


def test_a_campaign_starts_the_director_in_the_start_tier_and_it_settles_after_a_dwell() -> None:
    shipped = start_campaign(CAMPAIGN_ID, 1, shipped_config({}))
    assert shipped.director["ENEMY"].tier == "PATTERN_OF_LIFE"
    config = shipped_config({"director.tier.start": "ALPHA"})
    w = start_campaign(CAMPAIGN_ID, 1, config)
    assert w.director["ENEMY"] == DirectorState(tier="ALPHA")  # dwell 0, the usual levels
    assert w.director["COALITION"] == DirectorState()  # no Director runs for it
    director_validate(w, config.rules)
    # No provocation and no CP: min(level 0, ceiling ALPHA) is PATTERN_OF_LIFE, reached once the
    # 10-window dwell is spent, like a move from any tier.
    state, path = w.director["ENEMY"], []
    for _ in range(11):
        decide(state, view(), config.rules, {})
        path.append(state.tier)
    assert path == ["ALPHA"] * 9 + ["PATTERN_OF_LIFE"] * 2


def test_a_restore_measures_reachable_tiers_from_the_start_tier() -> None:
    w = valid_after(0)
    w.director["ENEMY"].tier = "ALPHA"
    with pytest.raises(ValueError, match="could not have reached"):
        director_validate(w, DIRECTOR_RULES)
    alpha = dataclasses.replace(DR, start_tier="ALPHA")
    director_validate(w, dataclasses.replace(DIRECTOR_RULES, director=alpha))


# --- director.tier.max_step ---------------------------------------------------------------------


def director_rules(**changes: Any) -> Rules:
    return dataclasses.replace(DIRECTOR_RULES, director=dataclasses.replace(DR, **changes))


@pytest.mark.parametrize(
    ("fighters", "max_step", "tier"),
    [(10, 1, "ALPHA"), (10, 2, "BRAVO"), (0, 2, "ALPHA")],
)
def test_the_tier_moves_up_to_max_step_steps_after_the_dwell(
    fighters: int, max_step: int, tier: str
) -> None:
    # CP 100 (10 fighters x 10) lifts the ceiling to BRAVO by window 5 (100 x (1 - 0.8^5) = 67 >
    # 60); provocation 100 a window is above BRAVO's 40. At the 10th window the dwell is spent.
    # No fighters: the ceiling stays ALPHA, so a 2-step move still stops there.
    rules = director_rules(max_step=max_step)
    state, path = DirectorState(), []
    for _ in range(10):
        state.pending += 100 * MICRO
        decide(state, view(["STRIKE_FIGHTER"] * fighters), rules, {})
        path.append(state.tier)
    assert path == ["PATTERN_OF_LIFE"] * 9 + [tier]


@pytest.mark.parametrize(("max_step", "ok"), [(1, False), (2, True)])
def test_a_restore_allows_a_tier_max_step_moves_could_reach(max_step: int, ok: bool) -> None:
    w = valid_after(10)  # one dwell: one move
    w.director["ENEMY"].tier, w.director["ENEMY"].budget = "BRAVO", DR.budget["BRAVO"]
    rules = director_rules(max_step=max_step)
    if ok:
        director_validate(w, rules)
    else:
        with pytest.raises(ValueError, match="could not have reached"):
            director_validate(w, rules)


# --- director.provocation.ai_shooter_mult --------------------------------------------------------


def test_an_ai_shooters_weight_is_floored_to_whole_millionths() -> None:
    from types import SimpleNamespace
    from typing import cast

    from nexus.core.provocation import _by
    from nexus.core.world import Entity

    dr = dataclasses.replace(DR, ai_shooter_mult=Fraction(1, 3))
    ai = cast(Entity, SimpleNamespace(owner_kind="AI_GARRISON"))  # _by reads only owner_kind
    assert _by(dr, ai, 1_000_001) == 333_333  # 333,333.67 floors; rounding would give 333,334
    assert _by(dr, ai, 2) == 0


@pytest.mark.parametrize(
    ("cmd", "mult", "points"),
    [(None, Fraction(0), 0), (None, Fraction(1, 2), 2_500_000), (None, Fraction(3), 15 * MICRO),
     (7, Fraction(1, 2), 5 * MICRO)],
)  # fmt: skip
def test_an_ai_kill_provokes_by_ai_shooter_mult_and_a_players_kill_in_full(
    cmd: int | None, mult: Fraction, points: int
) -> None:
    w = with_rules(combat_world(sure("SMALL_ARMS", damage=80)), director={"ai_shooter_mult": mult})
    shooter = combat_put(w, GRUNT, "COALITION", 0, cmd=cmd)
    convoy = combat_put(w, CONVOY, "ENEMY", 500)  # 80 hp: one hit kills, 5 points in full
    track(w, shooter, convoy)
    fight_run(w)
    assert w.find(convoy.id) is None and w.director["ENEMY"].pending == points
    assert w.director["ENEMY"].last_provocation_sector == ("north" if points else None)


@pytest.mark.parametrize(("mult", "points"), [(Fraction(0), 0), (Fraction(1, 2), 1_500_000)])
def test_an_ai_hit_on_a_static_bases_defenses_provokes_by_ai_shooter_mult(
    mult: Fraction, points: int
) -> None:
    w = with_rules(combat_world(), director={"ai_shooter_mult": mult})
    suffered_defense_hit(w, combat_put(w, GRUNT, "COALITION", 0), "fob-n-e")  # 3 points in full
    assert w.director["ENEMY"].pending == points


# --- director.pol.capture_slot_tiers -------------------------------------------------------------


@pytest.mark.parametrize(
    ("tiers", "tier", "runs"),
    [
        (frozenset({"PATTERN_OF_LIFE"}), "ALPHA", False),
        (frozenset({"ALPHA"}), "ALPHA", True),
        (frozenset({"ALPHA"}), "PATTERN_OF_LIFE", False),
        (frozenset(), "PATTERN_OF_LIFE", False),
    ],
)
def test_the_capture_slot_runs_only_at_the_capture_slot_tiers(
    tiers: frozenset[ThreatTier], tier: ThreatTier, runs: bool
) -> None:
    rules = with_director(capture_slot_tiers=tiers)
    w = pol_world(1, rules)
    skip(w, DR.offensive_ticks - 1)
    pol_window(w, tier, 0, rules)  # a zero window budget: only the slot can launch one
    assert (w.director["ENEMY"].last_offensive == DR.offensive_ticks) is runs
    assert len({p for p in live_ops(w) if p[0] in ("OFFENSIVE", "RETAKE")}) == runs


# --- tasking.ai_jobs / ai_excluded_jobs ----------------------------------------------------------


def task_rules(**changes: Any) -> Rules:
    return dataclasses.replace(TASK_RULES, tasking=dataclasses.replace(TR, **changes))


@pytest.mark.parametrize(
    ("ai_jobs", "takes"),
    [
        (frozenset({"DEFEND", "RESUPPLY", "SCOUT"}), "DEFEND"),
        (frozenset({"RESUPPLY", "SCOUT"}), None),  # a defend is no longer the garrison's own
        (frozenset({"RESUPPLY", "SCOUT", "STRIKE"}), "STRIKE"),  # a strike no human started
    ],
)
def test_the_ai_garrison_takes_the_ai_jobs_by_itself(
    ai_jobs: frozenset[JobKind], takes: str | None
) -> None:
    w = task_world(1, task_rules(ai_jobs=ai_jobs))
    jobs = {
        "STRIKE": post(w, "COALITION", "STRIKE", "east-airbase", "s"),
        "DEFEND": post(w, "COALITION", "DEFEND", "fob-n-w", "d"),
    }
    jet = task_put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    board_pass(w)
    assert jet.job_id == (jobs[takes].id if takes else None)


@pytest.mark.parametrize(
    ("excluded", "joins"),
    [(frozenset({"ESCORT_CONVOY", "PATROL"}), False), (frozenset({"ESCORT_CONVOY"}), True)],
)
def test_the_ai_garrison_joins_a_viewers_patrol_only_when_it_is_not_excluded(
    excluded: frozenset[JobKind], joins: bool
) -> None:
    w = pw(dataclasses.replace(PATROL_TR, ai_excluded_jobs=excluded))
    grunt = task_put(w, "GARRISON_INFANTRY", "west-airbase")
    ai = task_put(w, "GARRISON_INFANTRY", "west-airbase", AI)  # after the viewer's claim
    board_pass(w)
    assert grunt.job_id is not None and w.boards["COALITION"][grunt.job_id].kind == "PATROL"
    assert ai.job_id == (grunt.job_id if joins else None)


# --- tasking.human_displaces_ai ------------------------------------------------------------------


@pytest.mark.parametrize("displaces", [True, False])
def test_a_viewer_bumps_the_highest_id_ai_claimant_only_with_human_displaces_ai(
    displaces: bool,
) -> None:
    w = task_world(1, task_rules(human_displaces_ai=displaces))
    job = post(w, "COALITION", "DEFEND", "fob-n-w", "d")  # 2 slots, the only job
    ai1 = task_put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    ai2 = task_put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    board_pass(w)
    human = task_put(w, "GARRISON_INFANTRY", "west-airbase")
    events = board_pass(w)
    if displaces:
        assert kinds(events) == ["JobReleased", "JobClaimed"] and ai2.job_id is None
        assert set(job.claims) == {ai1.id, human.id}
    else:  # every job is full for it too: it overfills (2 x 2 slots) and nobody is released
        assert kinds(events) == ["JobClaimed"] and ai2.job_id == job.id
        assert set(job.claims) == {ai1.id, ai2.id, human.id}


# --- determinism with every part 2b option flipped -----------------------------------------------


def test_a_campaign_with_every_part_2b_option_flipped_is_deterministic() -> None:
    config = shipped_config(
        {
            "director.tier.start": "ALPHA",
            "director.tier.max_step": 2,
            "director.provocation.ai_shooter_mult": 1.0,
            "director.pol.capture_slot_tiers": ["PATTERN_OF_LIFE", "ALPHA", "BRAVO"],
            "tasking.ai_jobs": ["DEFEND", "RESUPPLY", "SCOUT", "STRIKE"],
            "tasking.ai_excluded_jobs": [],
            "tasking.human_displaces_ai": False,
        }
    )

    def scenario() -> tuple[str, list[dict[str, Any]]]:
        w = start_campaign(CAMPAIGN_ID, 3, config)
        events = [e.model_dump() for _ in range(6_600) for e in step(w, [])]  # 11 windows
        return state_hash(w), events

    first = scenario()
    assert any(e["kind"] == "ThreatTierChanged" for e in first[1])  # ALPHA settles in the span
    assert scenario() == first
