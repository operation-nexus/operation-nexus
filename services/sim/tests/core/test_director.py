"""NX-151, NX-155: the Threat Director's view, coalition power, provocation, tiers and budget
(THREAT-DIRECTOR §2-§5a, §7; TD-1, TD-2; Q-TD-1, Q-TD-2, Q-TD-5, Q-TD-11, Q-TD-12, Q-SIM-78).

Shipped numbers (Q-SIM-78): a decision window every 600 running ticks (60 game s at 10 Hz), CP EMA
step 1/5 per window, dwell 6,000 ticks (10 windows), ALPHA from provocation 10 (exit 8), BRAVO from
40 (exit 32), BRAVO CP ceiling from 60 (exit 48), provocation half-life 15 windows. Most tests drive
`decide` with a hand-made `SideView`; the integration ones use real `step`s on the combat and
capture test scenes.
"""

import ast
import dataclasses
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import msgpack
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter
from test_capture import ENEMY_FOB, about_to_flip
from test_capture import new_world as capture_world
from test_capture import put as put_at
from test_combat import COMBAT, CONVOY, INFANTRY, RADAR, new_world, put, run, sure, track

from nexus.contracts.gen.common.enums import ThreatTier, UnitKind
from nexus.contracts.gen.events.threat_tier_changed import ThreatTierChanged
from nexus.core import director as director_mod
from nexus.core.combat import _hit
from nexus.core.director import TIERS, TierChange, decide, due, level, raw_cp, surplus
from nexus.core.fog import SideView, side_view
from nexus.core.geometry import in_polygon
from nexus.core.provocation import (
    captured,
    in_rear,
    note_redemption,
    scan_rear,
    suffered_defense_hit,
    suffered_hit,
)
from nexus.core.provocation import validate as director_validate
from nexus.core.rules import DECAY_RATIO_MAX, DirectorRules, Rules, _decay, sector_at
from nexus.core.step import step
from nexus.core.world import (
    Contact,
    DirectorState,
    Vec2,
    World,
    load,
    save,
    state_hash,
    to_canonical,
)
from nexus.runtime.campaign_config import ConfigPaths, load_campaign_config, start_campaign
from nexus.runtime.config import ConfigError, load_balance

CONFIG = load_campaign_config()
RULES = dataclasses.replace(CONFIG.rules, campaign=None, tasking=None, track_every_ticks=10**9)
_dr = RULES.director
if _dr is None:
    raise AssertionError("the shipped config has Director rules")
DR: DirectorRules = _dr
MICRO = 1_000_000
WINDOW = DR.window_ticks  # 600
DWELL_WINDOWS = DR.min_dwell_ticks // WINDOW  # 10
FIGHTER: UnitKind = "STRIKE_FIGHTER"
SCOUT: UnitKind = "RECON_UAV"
TRUCK: UnitKind = "LOGI_TRUCK"
DIRECTOR_SRC = Path(director_mod.__file__)
CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
STRAIT = dataclasses.replace(
    CONFIG,
    rules=dataclasses.replace(CONFIG.rules, campaign=None, tasking=None, garrison_quota={}),
)


def view(kinds: Sequence[UnitKind] = (), last_known: Sequence[UnitKind] = ()) -> SideView:
    """The ENEMY's view tracking one unit of each of `kinds` (ids from 1) and, as last-known tracks,
    one of each of `last_known`; the nodes keep their start owners."""
    here = Contact("RECON_UAV", Vec2(0, 0), Vec2(0, 0))
    tracks = {i: dataclasses.replace(here, kind=k) for i, k in enumerate(kinds, 1)}
    old = {i: dataclasses.replace(here, kind=k, age=3) for i, k in enumerate(last_known, 1000)}
    return SideView("ENEMY", tracks, old, {}, dict(RULES.supply.start_owner), {}, (), {})


def window(
    state: DirectorState,
    v: SideView,
    pending: int = 0,
    stock: dict[str, int] | None = None,
) -> TierChange | None:
    """One decision window with `pending` points (whole) noted since the last."""
    state.pending += pending * MICRO
    return decide(state, v, RULES, stock or {})


def tiers(n: int, kinds: list[UnitKind], pending: int) -> list[ThreatTier]:
    """The tier after each of `n` windows under constant CP input and per-window provocation."""
    state, out = DirectorState(), []
    for _ in range(n):
        window(state, view(kinds), pending)
        out.append(state.tier)
    return out


# --- coalition power (§2, Q-TD-2, Q-FOW-14) -------------------------------------------------------


def test_cp_sums_tracked_listed_kinds_and_ignores_last_known_and_unlisted() -> None:
    v = view([FIGHTER, SCOUT, TRUCK, "RADAR_SITE"], last_known=[FIGHTER, FIGHTER])
    assert raw_cp(v, DR) == (10 + 3 + 2) * MICRO  # the radar site counts 0, the old tracks too


def test_cp_ema_moves_one_fifth_of_the_way_per_window() -> None:
    state, v = DirectorState(), view([FIGHTER])  # raw 10
    window(state, v)
    assert state.cp == 2 * MICRO  # 0 + (10 - 0) / 5
    window(state, v)
    assert state.cp == 3_600_000  # 2 + (10 - 2) / 5
    window(state, view())  # nothing tracked: falls by a fifth
    assert state.cp == 2_880_000


def strait(truck_at: tuple[float, float], ticks: int) -> World:
    """The shipped strait-1 campaign (sensing on) with one commander's truck, run `ticks` ticks."""
    w = start_campaign(CAMPAIGN_ID, 5, STRAIT)
    w.spawn(TRUCK, "COALITION", "COMMANDER", Vec2(*truck_at), commander_id="c-1")
    for _ in range(ticks):
        step(w, [])
    return w


def test_an_untracked_coalition_unit_changes_nothing_but_a_tracked_one_counts() -> None:
    a, b = strait((20_000, 120_000), 2 * WINDOW + 1), strait((60_000, 100_000), 2 * WINDOW + 1)
    assert a.contacts["ENEMY"] == b.contacts["ENEMY"] == {}  # both far from every Static sensor
    assert a.director["ENEMY"].windows == 2 and a.director["ENEMY"].cp == 0
    assert (
        to_canonical(a, quantize=False)["director"] == to_canonical(b, quantize=False)["director"]
    )
    near = strait((300_000, 120_000), 5)  # the control: beside the East Airbase radar
    assert raw_cp(side_view(near, "ENEMY"), DR) == 2 * MICRO


def test_the_director_module_never_names_the_world_or_reads_an_entity() -> None:
    tree = ast.parse(DIRECTOR_SRC.read_text())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not names & {"World", "world", "Entity"}
    assert not attrs & {"entities", "find", "spawn", "contacts", "campaign", "rng"}
    assert imported & {"DirectorState"} and not imported & {"World", "Entity"}


# --- levels, hysteresis and tiers (§3, Q-TD-1) ----------------------------------------------------

ENTERS = (10 * MICRO, 40 * MICRO)
EXIT = Fraction(8, 10)


@given(st.lists(st.integers(8 * MICRO, 10 * MICRO - 1), max_size=30))
def test_a_value_inside_the_band_never_changes_the_level(values: list[int]) -> None:
    for held in (0, 1):
        for v in values:
            assert level(v, held, ENTERS, EXIT) == held
    # 8.0 is the exit value itself: the level is kept there and lost one micro-point below it
    assert level(8 * MICRO, 1, ENTERS, EXIT) == 1 and level(8 * MICRO - 1, 1, ENTERS, EXIT) == 0


def test_levels_rise_at_the_enter_value_and_can_skip() -> None:
    assert level(10 * MICRO - 1, 0, ENTERS, EXIT) == 0
    assert level(10 * MICRO, 0, ENTERS, EXIT) == 1
    assert level(40 * MICRO, 0, ENTERS, EXIT) == 2  # a jump in the level; the tier still steps
    assert level(32 * MICRO, 2, ENTERS, EXIT) == 2 and level(32 * MICRO - 1, 2, ENTERS, EXIT) == 1


def test_zero_provocation_with_high_cp_stays_pattern_of_life() -> None:
    assert set(tiers(200, [FIGHTER] * 30, 0)) == {"PATTERN_OF_LIFE"}


def test_high_provocation_with_low_cp_caps_at_alpha() -> None:
    path = tiers(200, [], 100)
    assert path[DWELL_WINDOWS - 1] == "ALPHA" and set(path[DWELL_WINDOWS - 1 :]) == {"ALPHA"}


def test_pattern_of_life_to_bravo_steps_through_alpha_with_the_dwell() -> None:
    path = tiers(40, [FIGHTER] * 10, 100)  # CP 100, provocation far above BRAVO
    assert path[: DWELL_WINDOWS - 1] == ["PATTERN_OF_LIFE"] * (DWELL_WINDOWS - 1)
    assert path[DWELL_WINDOWS - 1 : 2 * DWELL_WINDOWS - 1] == ["ALPHA"] * DWELL_WINDOWS
    assert path[2 * DWELL_WINDOWS - 1 :] == ["BRAVO"] * (40 - 2 * DWELL_WINDOWS + 1)


def test_a_tier_steps_back_down_one_dwell_at_a_time() -> None:
    state = DirectorState()
    for _ in range(2 * DWELL_WINDOWS):
        window(state, view([FIGHTER] * 10), 100)
    assert state.tier == "BRAVO"
    seen: list[ThreatTier] = []
    for _ in range(400):  # no more provocation: it decays, the CP stays
        window(state, view([FIGHTER] * 10))
        seen.append(state.tier)
    assert "ALPHA" in seen and seen[-1] == "PATTERN_OF_LIFE"  # CP alone cannot keep BRAVO up
    assert seen.index("ALPHA") < seen.index("PATTERN_OF_LIFE")  # through ALPHA, not straight down
    assert seen.index("ALPHA") >= DWELL_WINDOWS - 1  # and only after the dwell in BRAVO


@given(
    st.lists(
        st.tuples(st.integers(0, 25), st.sampled_from([0, 0, 0, 3, 40, 120])),
        min_size=1,
        max_size=150,
    )
)
def test_no_flapping_under_oscillating_cp_and_provocation(steps: list[tuple[int, int]]) -> None:
    state, last_change, before = DirectorState(), None, "PATTERN_OF_LIFE"
    for i, (fighters, pending) in enumerate(steps):
        change = window(state, view([FIGHTER] * fighters), pending)
        if change is not None:
            step_ = TIERS.index(change.after) - TIERS.index(change.before)
            assert abs(step_) == 1
            assert step_ < 0 or TIERS.index(change.after) <= min(state.prov_level, state.ceiling)
            assert (change.before, state.dwell) == (before, 0)
            assert last_change is None or i - last_change >= DWELL_WINDOWS
            last_change, before = i, change.after
        else:
            assert state.tier == before


# --- provocation: decay (§5a, Q-SIM-78) -----------------------------------------------------------


def test_provocation_decays_by_the_half_life_to_the_micro_point() -> None:
    state = DirectorState()
    window(state, view(), 40)
    assert state.provocation == 40 * MICRO  # added after the decay, so a fresh note is whole
    with localcontext() as ctx:
        ctx.prec = 60
        factor = Decimal(2) ** (Decimal(-1) / Decimal(15))  # a window is 1/15 of the half-life
        for n in (1, 5, 15, 30):
            probe = DirectorState(provocation=40 * MICRO)
            for _ in range(n):
                window(probe, view())
            expect = Decimal(40 * MICRO) * factor**n
            assert abs(Decimal(probe.provocation) - expect) <= n + 1  # one floor per window


def test_decay_is_monotone_and_reaches_zero() -> None:
    state, last = DirectorState(provocation=MICRO), MICRO
    for _ in range(2000):
        window(state, view())
        assert state.provocation <= last
        last = state.provocation
    assert state.provocation == 0


# --- provocation: who and what (§5a, Q-TD-11, Q-AI-9) ---------------------------------------------


def pending(w: World) -> int:
    return w.director["ENEMY"].pending


def test_a_player_kill_adds_five_and_an_ai_garrison_kill_adds_nothing() -> None:
    for cmd, expect in ((7, 5 * MICRO), (None, 0)):
        w = new_world(sure("SMALL_ARMS", damage=80))
        inf = put(w, INFANTRY, "COALITION", 0, cmd=cmd)
        convoy = put(w, CONVOY, "ENEMY", 500)  # 80 hp: one hit kills
        track(w, inf, convoy)
        run(w)
        assert w.find(convoy.id) is None and pending(w) == expect
        assert w.director["ENEMY"].last_provocation_sector == ("north" if cmd else None)


def test_a_player_hit_scores_by_what_was_hit() -> None:
    radar = COMBAT.units[RADAR]  # a facility floors at the Disabled threshold (CB-9)

    def hit_score(kind: UnitKind, hp: int | None = None, *, disabled: bool = False) -> int:
        w = new_world()
        shooter = put(w, INFANTRY, "COALITION", 0, cmd=3)
        target = put(w, kind, "ENEMY", 500)
        if hp is not None:
            target.hp = hp
        if disabled:
            target.damage_state = "DISABLED"
        weapon = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=50)
        was = target.damage_state
        _hit(w, RULES, COMBAT, shooter, target, weapon, [])
        suffered_hit(w, shooter, target, was)
        return pending(w)

    assert hit_score("ENEMY_ARMOR") == 1 * MICRO  # a unit hit
    assert hit_score(CONVOY) == 3 * MICRO  # a convoy hit, not 1
    assert hit_score(RADAR) == 3 * MICRO  # a facility hit that does not disable it
    assert hit_score(RADAR, radar.cuts[0] + 1) == 8 * MICRO  # the hit that brings it to Disabled
    assert hit_score(RADAR, radar.floor, disabled=True) == 3 * MICRO  # already Disabled
    assert hit_score(CONVOY, 3) == 5 * MICRO  # destroyed: 5, not also a convoy hit


def test_a_wreck_made_by_a_player_counts_as_a_kill_once() -> None:
    convoy = COMBAT.units[CONVOY]
    w = new_world()
    shooter = put(w, INFANTRY, "COALITION", 0, cmd=3)
    target = put(w, CONVOY, "ENEMY", 500)
    target.hp = convoy.cuts[0] + 3
    small = dataclasses.replace(COMBAT.weapons["SMALL_ARMS"], damage=5)
    was = target.damage_state
    _hit(w, RULES, COMBAT, shooter, target, small, [])
    suffered_hit(w, shooter, target, was)  # armor 0: hp now below the Disabled cut, a wreck
    assert target.damage_state == "DISABLED" and w.find(target.id) is not None
    assert pending(w) == 5 * MICRO
    was = target.damage_state
    _hit(w, RULES, COMBAT, shooter, target, dataclasses.replace(small, damage=500), [])
    suffered_hit(w, shooter, target, was)  # its destruction, and any hit on it: nothing more
    assert w.find(target.id) is None and pending(w) == 5 * MICRO
    ai = new_world()
    ai_shooter = put(ai, INFANTRY, "COALITION", 0)  # an AI garrison wreck-maker adds 0
    wreck = put(ai, CONVOY, "ENEMY", 500)
    wreck.hp = convoy.cuts[0] + 3
    _hit(ai, RULES, COMBAT, ai_shooter, wreck, small, [])
    suffered_hit(ai, ai_shooter, wreck, "HEALTHY")
    assert pending(ai) == 0


def test_a_player_hit_on_a_static_bases_defenses_counts_like_a_facility_hit() -> None:
    w = new_world()
    inf = put(w, INFANTRY, "COALITION", 0, cmd=3)
    suffered_defense_hit(w, inf, "west-airbase")  # the coalition's own base: nothing
    suffered_defense_hit(w, put(w, INFANTRY, "COALITION", 0), "fob-n-e")  # an AI shooter: nothing
    assert pending(w) == 0
    suffered_defense_hit(w, inf, "fob-n-e")
    assert pending(w) == 3 * MICRO and w.director["ENEMY"].last_provocation_sector == "north"


def test_a_shot_at_a_static_bases_defenses_provokes_through_combat() -> None:
    rules = sure("AG_LIGHT")
    w = new_world(rules)
    jet = put(w, FIGHTER, "COALITION", 289_000, 40_000, cmd=5)  # 1 km from fob-n-e
    w.defense_hp["fob-n-e"] = 100
    events = run(w, 10)  # the missile lands on tick 7
    assert w.defense_hp["fob-n-e"] < 100, events
    assert pending(w) >= 3 * MICRO and jet.id in {e.id for e in w.entities()}


def test_the_coalition_losing_units_never_provokes() -> None:
    w = new_world()
    shooter = put(w, INFANTRY, "COALITION", 0, cmd=1)
    truck = put(w, TRUCK, "COALITION", 500, cmd=2)
    suffered_hit(w, shooter, truck, "HEALTHY")  # the victim's side has no Director
    assert pending(w) == 0 and w.director["COALITION"] == DirectorState()


def test_a_flip_of_a_static_base_with_a_commander_adds_fifteen_in_its_sector() -> None:
    w = capture_world()
    about_to_flip(w, ENEMY_FOB, "COALITION")
    put_at(w, INFANTRY, "COALITION", ENEMY_FOB, n=4)
    step(w, [])
    assert w.owner[ENEMY_FOB] == "COALITION" and pending(w) == 15 * MICRO
    assert w.director["ENEMY"].last_provocation_sector == "north"
    ai = capture_world()
    about_to_flip(ai, ENEMY_FOB, "COALITION")
    put_at(ai, INFANTRY, "COALITION", ENEMY_FOB)  # AI garrison: no commander in radius
    step(ai, [])
    assert ai.owner[ENEMY_FOB] == "COALITION" and pending(ai) == 0


def test_only_a_static_base_flipping_to_the_coalition_counts() -> None:
    w = new_world()
    captured(w, "cross-n", "NEUTRAL", "COALITION", 1)  # a neutral node
    captured(w, "west-airbase", "COALITION", "ENEMY", 1)  # the coalition's loss
    assert pending(w) == 0


def rear_scene(x: float, *, cmd: int | None, tracked: bool = True, y: float = 120_000) -> World:
    w = new_world()
    scout = put(w, SCOUT, "COALITION", x, y, cmd=cmd)
    if tracked:
        w.contacts["ENEMY"][scout.id] = Contact(scout.kind, scout.pos, scout.vel)
    return w


def scan(w: World) -> None:
    scan_rear(w, "ENEMY", side_view(w, "ENEMY"))


def test_a_tracked_player_scout_in_the_rear_adds_two_once_per_window() -> None:
    w = rear_scene(385_000, cmd=1)  # behind the HQ
    second = put(w, SCOUT, "COALITION", 390_000, 120_000, cmd=2)
    w.contacts["ENEMY"][second.id] = Contact(second.kind, second.pos, second.vel)
    scan(w)
    assert pending(w) == 2 * MICRO  # two scouts, one note per window
    assert w.director["ENEMY"].last_provocation_sector == "centre"


@pytest.mark.parametrize(
    ("x", "cmd", "tracked"),
    [
        (385_000, 1, False),  # the Static does not sense it (TD-2, Q-FOW-15)
        (385_000, None, True),  # an AI scout
        (150_000, 1, True),  # tracked, but nearer the coalition's bases than the Static's
        (200_000, 1, True),  # along the front, on the coalition side (92 km vs 110 km)
        (210_000, 1, True),  # exactly as near fob-n-w as east-airbase (100 km each): a tie
    ],
)
def test_a_scout_that_is_unsensed_ai_or_not_in_the_rear_adds_nothing(
    x: float, cmd: int | None, tracked: bool
) -> None:
    w = rear_scene(x, cmd=cmd, tracked=tracked)
    scan(w)
    assert pending(w) == 0 and w.director["ENEMY"].last_provocation_sector is None


def test_the_rear_is_where_the_static_owns_the_nearest_base_and_moves_with_the_front() -> None:
    def in_rear_at(w: World, x: float, y: float = 120_000) -> bool:
        return in_rear(side_view(w, "ENEMY"), RULES, x, y)

    w = new_world()
    assert in_rear_at(w, 211_000)  # one km past the tie: east-airbase is 99 km, fob-n-w 100.8 km
    assert not in_rear_at(w, 210_000) and not in_rear_at(w, 200_000)
    assert not in_rear_at(w, 200_000, 110_000)  # fob-n-w is 86 km off, east-airbase 110 km
    w.owner["fob-n-w"] = "ENEMY"  # the front moves west: a flip
    assert in_rear_at(w, 200_000, 110_000)  # now fob-n-w is the Static's, fob-s-w 99 km off
    w.owner["fob-n-w"] = "COALITION"
    w.owner["east-airbase"] = "COALITION"  # and east: the Static's nearest base is farther
    assert not in_rear_at(w, 211_000)
    assert in_rear_at(w, 385_000) and not in_rear_at(w, 20_000)  # behind each side's lines
    bridge_side = new_world()
    bridge_side.owner["bridge-n"] = "ENEMY"  # a BRIDGE is never a base (Q-SIM-79)
    assert not in_rear(side_view(bridge_side, "ENEMY"), RULES, 200_000, 60_000)
    gone = new_world()
    gone.owner.update({n: "COALITION" for n in gone.owner})
    assert not in_rear(side_view(gone, "ENEMY"), RULES, 385_000, 120_000)  # no base


def test_a_last_known_scout_track_adds_nothing() -> None:
    w = rear_scene(385_000, cmd=1)
    for c in w.contacts["ENEMY"].values():
        c.age = 5
    scan(w)
    assert pending(w) == 0


def test_a_redemption_adds_its_class_weight_and_a_cosmetic_one_nothing() -> None:
    w = new_world()
    note_redemption(w, "ENEMY", "cosmetic")
    assert pending(w) == 0 and w.director["ENEMY"].last_provocation_sector is None
    note_redemption(w, "ENEMY", "support")
    assert pending(w) == 1 * MICRO


def test_the_last_provocation_sector_is_the_latest_and_ties_go_to_the_lowest_id() -> None:
    w = new_world()
    inf = put(w, INFANTRY, "COALITION", 0, 0, cmd=1)
    south = put(w, CONVOY, "ENEMY", 500, 200_000)  # south lane
    centre = put(w, CONVOY, "ENEMY", 500, 100_000)  # centre lane
    north = put(w, CONVOY, "ENEMY", 500, 1_000)  # north lane
    for target in (south, centre, south):
        suffered_hit(w, inf, target, "HEALTHY")
    state = w.director["ENEMY"]
    assert state.last_provocation_sector == "centre"  # the same tick: centre < south, either order
    w.campaign.running_ticks += 1
    suffered_hit(w, inf, north, "HEALTHY")
    assert state.last_provocation_sector == "north"  # a later tick replaces it, whatever the id


def test_sector_at_finds_the_lane_and_takes_the_lowest_id_on_an_edge() -> None:
    assert sector_at(RULES, 1_000, 79_999) == "north"
    assert sector_at(RULES, 1_000, 80_000) == "centre"  # the boundary: centre < north by id
    assert sector_at(RULES, 1_000, 239_999) == "south" and sector_at(RULES, -1, 0) is None


# --- the window (TD-1) ----------------------------------------------------------------------------


def test_a_window_runs_on_every_600th_running_tick() -> None:
    assert [due(DR, t) for t in (1, 599, 600, 601, 1200)] == [False, False, True, False, True]


def test_the_window_decides_provocation_and_budget_at_running_tick_600() -> None:
    w = new_world(sure("SMALL_ARMS", damage=80))
    inf = put(w, INFANTRY, "COALITION", 0, cmd=7)
    convoy = put(w, CONVOY, "ENEMY", 500)
    track(w, inf, convoy)
    run(w, WINDOW - 1)
    assert w.director["ENEMY"].windows == 0 and pending(w) == 5 * MICRO
    run(w)
    state = w.director["ENEMY"]
    assert (state.windows, state.provocation, state.pending) == (1, 5 * MICRO, 0)


@pytest.mark.parametrize("paused_at", [300, WINDOW - 1])  # mid-window, and one tick before it ends
def test_a_pause_freezes_every_director_field_and_resuming_finishes_the_window(
    paused_at: int,
) -> None:
    w = new_world(sure("SMALL_ARMS", damage=80))
    inf = put(w, INFANTRY, "COALITION", 0, cmd=7)
    convoy = put(w, CONVOY, "ENEMY", 500)
    track(w, inf, convoy)
    run(w, paused_at)  # with 5 points pending
    frozen = to_canonical(w, quantize=False)["director"]
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    events = run(w, 2 * WINDOW)  # two whole windows of paused ticks
    assert events == [] and to_canonical(w, quantize=False)["director"] == frozen
    w.campaign.clock_paused, w.campaign.pause_reason = False, None
    run(w, WINDOW - paused_at - 1)
    assert w.director["ENEMY"].windows == 0
    run(w)  # running tick 600 again
    assert w.director["ENEMY"].windows == 1 and w.director["ENEMY"].provocation == 5 * MICRO


def test_the_window_and_the_dwell_take_the_same_ticks_at_another_time_scale(
    tmp_path: Path,
) -> None:
    text = ConfigPaths().balance.read_text().replace("time_scale: 6.0", "time_scale: 1.0")
    (tmp_path / "balance.yaml").write_text(text)
    slow = load_campaign_config(
        dataclasses.replace(ConfigPaths(), balance=tmp_path / "balance.yaml")
    )
    assert slow.rules.world_dt != CONFIG.rules.world_dt
    assert slow.rules.director == DR  # game time: the same ticks whatever the world speed
    w = start_campaign(
        CAMPAIGN_ID,
        5,
        dataclasses.replace(
            slow,
            rules=dataclasses.replace(slow.rules, campaign=None, tasking=None, garrison_quota={}),
        ),
    )
    for _ in range(WINDOW):
        step(w, [])
    assert w.director["ENEMY"].windows == 1


# --- budget (§4 step 2, Q-TD-5, Q-TD-12) ----------------------------------------------------------


def stock_scene() -> tuple[World, dict[str, int]]:
    w = new_world()
    floors = RULES.supply.starve_floor
    stock = {n: floors[n] + extra for n, extra in
             {"fob-n-e": 2, "fob-s-e": 0, "east-airbase": 1, "static-hq": -5}.items()}  # fmt: skip
    stock["west-airbase"] = 10_000  # the coalition's stock is not the Static's
    stock["static-rear"] = 10_000  # the rear source is excluded (Q-TD-12)
    return w, stock


def test_the_budget_is_the_surplus_of_the_static_bases_when_that_is_less_than_the_tier() -> None:
    w, stock = stock_scene()
    state = DirectorState()
    window(state, side_view(w, "ENEMY"), stock=stock)
    assert state.budget == 3  # 2 + 0 + 1 + 0 (below its floor adds nothing), tier cap 10


def test_the_budget_is_the_tier_budget_when_the_stock_can_pay_and_never_more() -> None:
    w, _ = stock_scene()
    rich = {
        n: RULES.supply.max_stock[n] for n in ("fob-n-e", "fob-s-e", "east-airbase", "static-hq")
    }
    assert surplus(side_view(w, "ENEMY"), RULES, rich) >= 80
    caps: tuple[tuple[ThreatTier, int], ...] = (
        ("PATTERN_OF_LIFE", 10),
        ("ALPHA", 30),
        ("BRAVO", 80),
    )
    for tier, cap in caps:
        state = DirectorState(tier=tier, prov_level=2, ceiling=2, dwell=0)
        window(state, side_view(w, "ENEMY"), 100, stock=rich)
        assert state.budget == min(cap, surplus(side_view(w, "ENEMY"), RULES, rich))


def test_a_starved_static_has_no_budget_and_a_lost_base_stops_counting() -> None:
    w, stock = stock_scene()
    assert surplus(side_view(w, "ENEMY"), RULES, stock) == 3
    w.owner["fob-n-e"] = "COALITION"  # captured
    assert surplus(side_view(w, "ENEMY"), RULES, stock) == 1
    floors = RULES.supply.starve_floor
    assert surplus(side_view(w, "ENEMY"), RULES, dict(floors)) == 0


def test_the_budget_is_never_above_the_real_surplus() -> None:
    @given(
        st.dictionaries(st.sampled_from(sorted(RULES.supply.starve_floor)), st.integers(0, 2000))
    )
    def check(stock: dict[str, int]) -> None:
        w = new_world()
        state = DirectorState()
        window(state, side_view(w, "ENEMY"), stock=stock)
        assert state.budget <= surplus(side_view(w, "ENEMY"), RULES, stock)
        assert state.budget <= DR.budget["PATTERN_OF_LIFE"]

    check()


# --- events, snapshot, hash, determinism ----------------------------------------------------------


def test_a_tier_change_emits_threat_tier_changed_with_the_smoothed_cp() -> None:
    w = new_world()
    state = w.director["ENEMY"]
    state.pending, state.cp = 30 * MICRO, 7 * MICRO
    events = run(w, DWELL_WINDOWS * WINDOW)
    (changed,) = [e for e in events if isinstance(e, ThreatTierChanged)]
    assert (changed.side, changed.from_, changed.to) == ("ENEMY", "PATTERN_OF_LIFE", "ALPHA")
    assert changed.tick == DWELL_WINDOWS * WINDOW and 0 < changed.cp_smoothed < 7
    wire = changed.model_dump(mode="json", by_alias=True)
    assert wire["from"] == "PATTERN_OF_LIFE" and wire["side"] == "ENEMY"
    assert TypeAdapter(ThreatTierChanged).validate_python(wire).to == "ALPHA"
    assert state.tier == "ALPHA" and state.dwell == 0


def busy_state() -> World:
    w = new_world()
    w.director["ENEMY"] = DirectorState(
        cp=61 * MICRO, provocation=12_345_678, pending=3 * MICRO, tier="ALPHA", prov_level=1,
        ceiling=2, dwell=1200, windows=7, budget=9, last_provocation_sector="north",
        last_provocation_tick=5,
    )  # fmt: skip
    w.campaign.tick = w.campaign.running_ticks = 4200
    return w


def test_director_state_round_trips_and_is_in_the_hash() -> None:
    w = busy_state()
    again = load(save(w))
    assert again.director == w.director and state_hash(again) == state_hash(w)
    for field, value in (("cp", 1), ("provocation", 2), ("pending", 0), ("tier", "BRAVO"),
                         ("prov_level", 2), ("ceiling", 1), ("dwell", 0), ("windows", 6),
                         ("budget", 1), ("last_provocation_sector", "south")):  # fmt: skip
        other = busy_state()
        setattr(other.director["ENEMY"], field, value)
        assert state_hash(other) != state_hash(w), field


def test_format_18_snapshots_are_refused() -> None:
    raw = msgpack.unpackb(save(busy_state()), raw=False)
    raw["v"] = 18
    with pytest.raises(ValueError, match="unsupported snapshot format version 18"):
        load(msgpack.packb(raw, use_bin_type=True))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"tier": "CHARLIE"}, "bad tier"),
        ({"ceiling": 0}, "ceiling at least 1"),
        ({"prov_level": 3}, "0..2"),
        ({"cp": -1}, "cp must be an int"),
        ({"windows": 9999}, "after the snapshot's running ticks"),
        ({"last_provocation_sector": None}, "sector and tick go together"),
        ({"surprise": 1}, "exactly the keys"),
    ],
)
def test_a_bad_director_state_is_refused(change: dict[str, object], message: str) -> None:
    raw = msgpack.unpackb(save(busy_state()), raw=False)
    raw["director"]["ENEMY"].update(change)
    with pytest.raises(ValueError, match=message):
        load(msgpack.packb(raw, use_bin_type=True))


def kills_scene() -> World:
    """A commander's infantry kills three Static convoys within the first 40 ticks (15 points)."""
    w = new_world(sure("SMALL_ARMS", damage=80))
    inf = put(w, INFANTRY, "COALITION", 0, cmd=7)
    for i in range(3):
        track(w, inf, put(w, CONVOY, "ENEMY", 100 + 10 * i))
    return w


def scenario() -> World:
    w = kills_scene()
    run(w, 12_000)
    return w


def test_provocation_raises_alpha_after_the_dwell_and_decays_back() -> None:
    w = kills_scene()
    state, seen = w.director["ENEMY"], {}
    for tick in range(1, 12_001):
        step(w, [])
        if tick % WINDOW == 0:
            seen[tick // WINDOW] = (state.tier, state.prov_level)
    assert seen[1] == ("PATTERN_OF_LIFE", 1)  # 15 points: the level rises at once, the tier waits
    assert seen[DWELL_WINDOWS - 1][0] == "PATTERN_OF_LIFE" and seen[DWELL_WINDOWS][0] == "ALPHA"
    # the level drops below 8 at window 15 (15 x 2^(-14/15) = 7.9), the tier a dwell after ALPHA
    assert seen[15][1] == 0 and seen[19][0] == "ALPHA" and seen[20] == ("PATTERN_OF_LIFE", 0)
    assert state.last_provocation_sector == "north"


def test_the_same_run_gives_the_same_hash_in_any_hash_seed() -> None:
    child = (
        "import sys; sys.path.insert(0, sys.argv[1]); from test_director import scenario\n"
        "from nexus.core.world import state_hash; print(state_hash(scenario()))"
    )

    def run_with(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", child, os.path.dirname(__file__)]
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603  # fixed argv

    assert run_with("1") == run_with("2") == state_hash(scenario())


def test_the_rules_without_a_director_run_no_window() -> None:
    off: Rules = dataclasses.replace(RULES, director=None)
    w = new_world(off)
    run(w, 2 * WINDOW)
    assert w.director["ENEMY"] == DirectorState()


# --- restore-time validation, decay bound, geometry (NX-155 QA) -----------------------------------


def valid_after(windows: int) -> World:
    """A world whose clock has run `windows` whole windows, with a Director state to match."""
    w = new_world()
    w.campaign.tick = w.campaign.running_ticks = windows * WINDOW
    w.director["ENEMY"] = DirectorState(windows=windows, dwell=min(windows, DWELL_WINDOWS) * WINDOW)
    return w


def test_a_reachable_director_state_validates() -> None:
    w = valid_after(25)
    w.director["ENEMY"].tier = "BRAVO"  # 2 steps need 20 windows
    w.director["ENEMY"].budget = DR.budget["BRAVO"]
    w.director["ENEMY"].last_provocation_sector = "south"
    w.director["ENEMY"].last_provocation_tick = 5
    director_validate(w, RULES)
    director_validate(new_world(), RULES)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"windows": 26}, "more windows"),
        ({"dwell": WINDOW + 1}, "dwell"),  # not whole windows
        ({"dwell": 11 * WINDOW}, "dwell"),  # above the minimum dwell
        ({"tier": "BRAVO"}, "could not have reached"),  # needs 20 windows, 5 run
        ({"budget": 11}, "budget"),  # PATTERN_OF_LIFE pays 10
        ({"last_provocation_sector": "atlantis", "last_provocation_tick": 1}, "not in the theater"),
    ],
)
def test_an_unreachable_director_state_is_refused(change: dict[str, object], message: str) -> None:
    w = valid_after(5 if message != "more windows" else 25)
    for key, value in change.items():
        setattr(w.director["ENEMY"], key, value)
    if message == "more windows":
        w.campaign.tick = w.campaign.running_ticks = 25 * WINDOW - 1
        w.director["ENEMY"].dwell = 0
    with pytest.raises(ValueError, match=message):
        director_validate(w, RULES)


def test_a_side_with_no_director_must_keep_its_start_state() -> None:
    w = new_world()
    w.director["COALITION"].pending = 1
    with pytest.raises(ValueError, match=r"director.COALITION"):
        director_validate(w, RULES)


def test_dwell_stops_at_the_minimum_so_it_stays_bounded() -> None:
    state = DirectorState()
    for _ in range(500):
        window(state, view())
    assert state.dwell == DR.min_dwell_ticks and state.windows == 500


def test_the_half_life_window_ratio_is_bounded_and_the_bound_is_fast() -> None:
    assert _decay(9000, 600) == DR.decay  # 15 / 1
    started = time.perf_counter()
    m, _ = _decay(DECAY_RATIO_MAX * 600, 600)
    assert time.perf_counter() - started < 0.1 and 0 < m < 2**40
    with pytest.raises(ValueError, match="neither part may exceed"):
        _decay((DECAY_RATIO_MAX + 1) * 600, 600)
    with pytest.raises(ValueError, match="neither part may exceed"):
        _decay(600, (DECAY_RATIO_MAX + 1) * 600)


def test_a_hang_ratio_is_a_config_error(tmp_path: Path) -> None:
    text = ConfigPaths().balance.read_text().replace("half_life_s: 900", "half_life_s: 5400000")
    path = tmp_path / "balance.yaml"
    path.write_text(text)
    started = time.perf_counter()
    with pytest.raises(ConfigError, match=r"director.provocation.half_life_s"):
        load_balance(path)
    assert time.perf_counter() - started < 1.0


POLY = [(0, 0), (10, 0), (10, 10), (5, 4), (0, 10)]  # concave: a notch from the top edge


@pytest.mark.parametrize(
    ("x", "y", "inside"),
    [
        (5, 2, True), (0, 0, True), (10, 10, True), (5, 0, True), (10, 5, True),  # vertex, edges
        (5, 4, True), (5, 5, False), (2, 10, False), (-1, 5, False), (11, 5, False),  # notch
        (5, 10, False), (3, 7, False), (1, 7, True), (0, 11, False),
    ],
)  # fmt: skip
def test_in_polygon_edges_and_the_float_form_agree(x: int, y: int, inside: bool) -> None:
    assert in_polygon(x, y, POLY) is inside
    assert in_polygon(float(x), float(y), POLY) is inside  # a float is exact: same answer


@given(st.integers(-5, 15), st.integers(-5, 15))
def test_in_polygon_int_and_float_points_always_agree(x: int, y: int) -> None:
    assert in_polygon(x, y, POLY) == in_polygon(float(x), float(y), POLY)


def test_sector_at_and_the_theater_loader_share_one_implementation() -> None:
    import nexus.runtime.theater as theater_mod

    assert vars(theater_mod)["in_polygon"] is in_polygon
    for sector, poly in RULES.sectors:  # every sector corner and edge midpoint is inside it
        for (x1, y1), (x2, y2) in zip(poly, (*poly[1:], poly[0]), strict=True):
            assert sector_at(RULES, x1, y1) is not None
            assert in_polygon((x1 + x2) / 2, (y1 + y2) / 2, poly), sector
