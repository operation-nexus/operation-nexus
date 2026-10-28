"""NX-472: `combat.facility_restore_frac`, the hp fraction a Disabled facility is repaired back to
before it is on line again (COMBAT CB-9, Q-TD-86). The shipped 0.35 is the Mission-kill line (the
NX-461 rule, covered in `test_rearm.py` and `test_sead.py`); here the key is set through the shipped
config loader to 0.8 and to its minimum, `damage_state.disabled_below` 0.10.

AIR_DEFENSE_SITE, 150 hp: Disabled below 15, Mission-kill below 53, Damaged below 105. Restore lines
worked by hand: ceil(0.35 x 150) = 53, ceil(0.8 x 150) = 120, ceil(0.10 x 150) = 15. West-airbase
repairs 0.6 hp a tick, so hp climbs one at a time and every line is hit exactly.
"""

import dataclasses

import pytest
from test_forward_deploy_refuel import WEST, run
from test_logistics import RULES, new_world
from test_rearm import changes, facility, state

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core.combat import validate
from nexus.core.rules import Rules
from nexus.core.world import Entity, World, load, save, state_hash
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config

SITE: UnitKind = "AIR_DEFENSE_SITE"


def rules_at(frac: float) -> Rules:
    """RULES (the logistics test set-up) with the combat rules the loader builds for `frac`."""
    return dataclasses.replace(
        RULES, combat=shipped_config({"combat.facility_restore_frac": frac}).rules.combat
    )


def disabled_site(rules: Rules) -> tuple[World, Entity]:
    w = new_world(rules)
    site = facility(w, WEST, SITE)
    site.hp, site.damage_state = 14, "DISABLED"  # the facility floor
    return w, site


def repair_to(w: World, site: Entity, hp: int) -> list[Event]:
    events: list[Event] = []
    for _ in range(400):  # bounded: a stalled repair fails the assert instead of hanging
        if site.hp >= hp:
            break
        events += run(w, 1)
    assert site.hp == hp
    return events


@pytest.mark.parametrize(("frac", "line"), [(0.35, 53), (0.8, 120), (0.10, 15), (1.0, 150)])
def test_the_loader_turns_the_key_into_a_restore_line_in_whole_hp(frac: float, line: int) -> None:
    combat = rules_at(frac).combat
    assert combat is not None and combat.units[SITE].restore == line


def test_the_shipped_restore_line_is_the_mission_kill_line_for_every_kind() -> None:
    combat = shipped_config({}).rules.combat
    assert combat is not None
    assert all(u.restore == u.cuts[1] for u in combat.units.values())


def test_at_0_8_a_site_stays_off_past_the_mission_kill_line_and_returns_at_120() -> None:
    w, site = disabled_site(rules_at(0.8))
    events = repair_to(w, site, 119)  # far past 53, where the shipped rule would bring it back
    assert state(site) == "DISABLED" and changes(events) == []
    events = repair_to(w, site, 120)
    assert state(site) == "HEALTHY" and changes(events) == [("DISABLED", "HEALTHY")]


def test_at_the_minimum_a_site_is_back_as_soon_as_it_leaves_disabled() -> None:
    w, site = disabled_site(rules_at(0.10))
    events = repair_to(w, site, 15)
    assert state(site) == "MISSION_KILL" and changes(events) == [("DISABLED", "MISSION_KILL")]


def test_a_hit_does_not_bring_a_site_out_early_at_0_8() -> None:
    rules = rules_at(0.8)
    assert rules.combat is not None
    stats = rules.combat.units[SITE]
    assert stats.state_after(119, "DISABLED", True) == "DISABLED"
    assert stats.state_after(119, "DISABLED", False) == "HEALTHY"  # a non-facility: hp only
    assert stats.state_after(52, "MISSION_KILL", True) == "MISSION_KILL"  # not Disabled before


@pytest.mark.parametrize(("frac", "ok"), [(0.8, True), (0.35, False)])
def test_the_restore_check_follows_the_key(frac: float, ok: bool) -> None:
    rules = rules_at(frac)
    w, site = disabled_site(rules)
    site.hp = 100  # Disabled at 100 hp: below the 0.8 line (120), above the shipped one (53)
    if ok:
        validate(w, rules)
    else:
        with pytest.raises(ValueError, match="damage_state does not match hp"):
            validate(w, rules)


def test_a_snapshot_mid_restore_at_0_8_continues_identically() -> None:
    rules = rules_at(0.8)
    w, site = disabled_site(rules)
    repair_to(w, site, 80)  # Disabled, between the shipped line and the 0.8 line
    h = state_hash(w)
    again = load(save(w))
    again.rules = rules
    validate(again, rules)
    assert state_hash(again) == h
    assert run(again, 80) == run(w, 80) and state_hash(again) == state_hash(w)
    assert site.hp == 128 and state(site) == "HEALTHY"  # 80 + 80 x 0.6, past 120


@pytest.mark.parametrize("frac", [0.09, 0.0, 1.01])
def test_the_loader_refuses_a_line_below_disabled_or_above_full_hp(frac: float) -> None:
    with pytest.raises(ConfigError):
        shipped_config({"combat.facility_restore_frac": frac})
