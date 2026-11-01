"""NX-471: a captured base's facilities change hands Disabled and repair slowly (GAMEPLAY §8
"Facilities at a captured base", COMBAT CB-9, Q-TD-78 (a), Q-TD-135).

Worlds are strait-1 through the shipped config with the keys flipped through the config
(`shipped_config`), and a capture is forced as `test_capture.py` forces one: a bar one step short of
full, defenses 0. Shipped numbers: `ad-fob-n-e` and `ad-fob-n-w` are 150-hp sites at FOBs (repair
rate 0.5, 300 thousandths of an hp a tick); `ad-east` and `radar-east` are at east-airbase (rate
1.0, 600 a tick). The floor is 14 hp and the restore line 53 (`combat.facility_restore_frac`). At
S = 92 (65 x S and 130 x S ticks) the floor to the restore line takes 5,980 ticks at an airbase
and 11,960 at a FOB; then 162 and 324 ticks to full hp.
"""

import dataclasses
import hashlib
from collections.abc import Callable
from typing import Any

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_capture import (
    ARMOR,
    CAMPAIGN_ID,
    INFANTRY,
    NEUTRAL_FOB,
    about_to_flip,
    of,
    put,
    run,
)
from test_combat import track

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.rearm_stalled import RearmStalled
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.unit_damage_state_changed import UnitDamageStateChanged
from nexus.contracts.gen.events.unit_repaired import UnitRepaired
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core import combat as combat_mod
from nexus.core.tasking import ring_crossed
from nexus.core.world import CaptureBar, Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import start_campaign
from nexus.runtime.golden import shipped_config

FOB, WEST_FOB, AIRBASE = "fob-n-e", "fob-n-w", "east-airbase"
SITE: UnitKind = "AIR_DEFENSE_SITE"
RADAR: UnitKind = "RADAR_SITE"
FLOOR, LINE, FULL = 14, 53, 150
FAST = {"capture.seized_repair_slowdown": 20}  # keeps the long runs short; the rule is the same


def world(**keys: Any) -> World:
    """strait-1 through the shipped config with `keys` (`capture__seized_repair_slowdown=20`)
    overridden; the board is off and there is no opening garrison, every defense is down."""
    cfg = shipped_config({k.replace("__", "."): v for k, v in keys.items()})
    rules = dataclasses.replace(cfg.rules, tasking=None, garrison_quota={})
    w = start_campaign(CAMPAIGN_ID, 12345, dataclasses.replace(cfg, rules=rules))
    w.defense_hp = dict.fromkeys(w.defense_hp, 0)
    return w


def fast(**keys: Any) -> World:
    return world(capture__seized_repair_slowdown=20, **keys)


def site_at(w: World, node: str, kind: UnitKind = SITE) -> Entity:
    return next(e for e in w.entities() if e.base_id == node and e.kind == kind)


def take(w: World, node: str, side: Any) -> list[Event]:
    """`side` captures `node` in the next tick (the loser's units there are moved out of the way
    first, as a real counterattack has to contest them off)."""
    for e in w.entities():
        if e.side != side and e.base_id is None and e.last_node == node:
            e.pos, e.last_node = Vec2(0.0, 0.0), None
    about_to_flip(w, node, side)
    put(w, INFANTRY if side == "COALITION" else ARMOR, side, node)
    return run(w)


def until(w: World, done: Any, limit: int) -> list[Event]:
    """Run until `done()`; the events of those ticks. Fails after `limit` ticks."""
    events: list[Event] = []
    for _ in range(limit):
        if done():
            return events
        events += run(w)
    raise AssertionError(f"not done after {limit} ticks")


def now(e: Entity) -> tuple[int, str, int | None]:
    """(hp, damage state, seized carry): widened, so an earlier assert does not narrow the next."""
    return e.hp, e.damage_state, e.seized_carry


def damage_changes(events: list[Event], *ids: int) -> list[tuple[int, str, str]]:
    return [
        (e.entity_id, e.from_, e.to)
        for e in of(events, UnitDamageStateChanged)
        if not ids or e.entity_id in ids
    ]


# --- the flip disables ------------------------------------------------------------------------


def test_a_flip_leaves_the_site_at_its_floor_disabled_and_seized_in_the_flip_tick() -> None:
    w = world()
    site = site_at(w, FOB)
    assert (site.hp, site.damage_state, site.seized_carry) == (FULL, "HEALTHY", None)
    site.repair_milli, site.repair_debt = 400, 3
    events = take(w, FOB, "COALITION")
    assert [type(e) for e in events if isinstance(e, NodeCaptured | UnitDamageStateChanged)] == [
        NodeCaptured,
        UnitDamageStateChanged,
    ]
    assert damage_changes(events) == [(site.id, "HEALTHY", "DISABLED")]
    assert (site.side, site.hp, site.damage_state) == ("COALITION", FLOOR, "DISABLED")
    assert (site.seized_carry, site.repair_milli, site.repair_debt) == (0, 0, 0)


def test_a_site_already_disabled_drops_to_the_floor_with_no_state_event() -> None:
    w = world()
    site = site_at(w, FOB)
    site.hp, site.damage_state = 30, "DISABLED"  # struck, not yet back
    events = take(w, FOB, "COALITION")
    assert (site.hp, site.damage_state, site.seized_carry) == (FLOOR, "DISABLED", 0)
    assert damage_changes(events) == []


def test_a_site_below_its_floor_keeps_its_hp() -> None:
    w = world(combat__facility_indestructible=False)
    site = site_at(w, FOB)
    site.hp, site.damage_state = 10, "DISABLED"
    take(w, FOB, "COALITION")
    assert (site.hp, site.damage_state, site.seized_carry) == (10, "DISABLED", 0)


def test_an_airbase_seizes_all_its_facilities_with_their_events_in_id_order() -> None:
    w = world()
    ids = sorted(e.id for e in w.entities() if e.base_id == AIRBASE)
    assert len(ids) == 2  # radar-east and ad-east
    events = take(w, AIRBASE, "COALITION")
    assert [c[0] for c in damage_changes(events)] == ids
    for i in ids:
        e = w.find(i)
        assert e is not None
        assert (e.side, e.hp, e.damage_state, e.seized_carry) == ("COALITION", FLOOR, "DISABLED", 0)


def test_a_neutral_base_flip_emits_nothing_more_than_today() -> None:
    kinds: dict[bool, list[str]] = {}
    for on in (True, False):
        w = world(capture__facilities_disabled=on)
        kinds[on] = [e.kind for e in take(w, NEUTRAL_FOB, "COALITION")]
    assert kinds[True] == kinds[False] and "UnitDamageStateChanged" not in kinds[True]


def test_the_flip_adds_only_the_state_event_to_the_switch_off_stream() -> None:
    # No provocation or other event rides on the flip (GAMEPLAY §8, EC-3): the streams differ by
    # the Disabled events alone.
    on = take(world(capture__facilities_disabled=True), AIRBASE, "COALITION")
    off = take(world(capture__facilities_disabled=False), AIRBASE, "COALITION")
    assert [e.kind for e in on if e.kind != "UnitDamageStateChanged"] == [e.kind for e in off]
    assert len(on) == len(off) + 2


@settings(max_examples=12, deadline=None)
@given(hp=st.integers(1, FULL), debt=st.integers(0, 9), milli=st.integers(0, 999))
def test_the_flip_never_raises_hp_and_a_seized_site_stays_below_its_line(
    hp: int, debt: int, milli: int
) -> None:
    w = world()
    site = site_at(w, FOB)
    assert w.rules is not None and w.rules.combat is not None
    stats = w.rules.combat.units[SITE]
    site.hp, site.damage_state = hp, stats.state(hp)
    site.repair_debt, site.repair_milli = debt, milli
    take(w, FOB, "COALITION")
    assert site.hp <= hp and site.hp < stats.restore and site.damage_state == "DISABLED"
    assert (site.seized_carry, site.repair_debt, site.repair_milli) == (0, 0, 0)
    combat_mod.validate(w, w.rules)


# --- Disabled does nothing --------------------------------------------------------------------


def hang(w: World, site: Entity) -> Callable[..., list[WeaponFired]]:
    """A low enemy fighter hangs 3 km from `site` (inside its 4 km gun), known to the site's side
    and kept fuelled. The returned function runs `ticks` and gives the shots `site` fired in them
    (stopping at the first with `until_fire`)."""
    assert w.rules is not None
    jet = put(w, "ENEMY_FIGHTER", "ENEMY", site.base_id or FOB, dx=3_000.0, state="ON_STATION")
    jet.alt_band = "LOW"
    fuel = w.rules.fuel_s[jet.kind]

    def go(ticks: int = 1, *, until_fire: bool = False) -> list[WeaponFired]:
        fired: list[WeaponFired] = []
        for _ in range(ticks):
            jet.pos, jet.fuel = Vec2(site.pos.x + 3_000.0, site.pos.y), fuel
            track(w, site, jet)
            fired += [f for f in of(run(w), WeaponFired) if f.shooter_id == site.id]
            if fired and until_fire:
                break
        return fired

    return go


def test_a_seized_site_fires_at_nothing_until_it_is_back_on_line() -> None:
    w = fast()
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    go = hang(w, site)  # in range, tracked and ready: Disabled does nothing
    while site.damage_state == "DISABLED":
        assert go() == []
        assert w.campaign.tick < 6_000
    assert site.hp == LINE
    assert go(10, until_fire=True)  # back on line: it fires within a few ticks


def sees(w: World, spotted: Entity) -> bool:
    return spotted.id in w.contacts["COALITION"]


def test_a_seized_radar_adds_no_coverage_until_it_is_back_on_line() -> None:
    for disabled in (False, True):  # the control: without the rule the radar works at once
        w = fast(capture__facilities_disabled=disabled)
        radar = site_at(w, AIRBASE, RADAR)
        take(w, AIRBASE, "COALITION")
        armor = put(w, ARMOR, "ENEMY", AIRBASE, dx=-30_000.0)  # inside 120 km x its 0.5 stealth
        run(w, 60)
        assert sees(w, armor) is (not disabled)
    marker = w.markers["ENEMY"][radar.id]  # and the loser's marker of it reads Disabled, silent
    assert (marker.state, marker.emitting) == ("DISABLED", False)
    assert radar.damage_state == "DISABLED"
    until(w, lambda: radar.damage_state != "DISABLED", 3_000)
    run(w, 60)
    assert sees(w, armor)


def test_the_losers_marker_reads_disabled_and_its_ring_no_longer_locks_it_out() -> None:
    results = {}
    for on in (True, False):
        w = world(capture__facilities_disabled=on)
        site = site_at(w, FOB)
        take(w, FOB, "COALITION")
        marker = w.markers["ENEMY"][site.id]
        start, goal = Vec2(site.pos.x - 20_000, site.pos.y), (site.pos.x + 20_000, site.pos.y)
        results[on] = (marker.state, ring_crossed(w.markers["ENEMY"].values(), start, goal))
    assert results[True] == (
        "DISABLED",
        False,
    )  # the Director's TD-2 and the board's TB-2 read this
    assert results[False] == ("HEALTHY", True)  # today's lockout (Q-TD-78)


def test_a_shot_in_flight_at_the_site_at_the_flip_fizzles_without_a_combat_draw() -> None:
    w = world()
    site = site_at(w, FOB)
    jet = put(w, "STRIKE_FIGHTER", "COALITION", FOB, dx=3_000.0, state="ON_STATION")
    track(w, jet, site)
    for _ in range(30):
        if any(s.target == site.id for s in w.shots):
            break
        jet.pos, jet.fuel = Vec2(site.pos.x + 3_000.0, site.pos.y), 1e6
        run(w)
    shot = next((s for s in w.shots if s.target == site.id), None)
    assert shot is not None, "the setup must put a shot in flight at the site"
    take(w, FOB, "COALITION")
    jet.pos = Vec2(site.pos.x + 3_000.0, site.pos.y)
    before = w.rng.to_state()
    while any(s.id == shot.id for s in w.shots):
        run(w)
        assert w.campaign.tick < 400
    assert w.rng.to_state() == before and site.hp == FLOOR


# --- repair with supply -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("node", "to_line", "to_full"), [(AIRBASE, 5_980, 162), (FOB, 11_960, 324)]
)
def test_the_slow_repair_takes_exactly_the_derived_ticks(
    node: str, to_line: int, to_full: int
) -> None:
    w = world()
    site = site_at(w, node)
    take(w, node, "COALITION")
    start = w.stock[node]
    events = run(w, to_line - 1)
    assert site.hp < LINE and site.damage_state == "DISABLED" and site.seized_carry is not None
    events += run(w)  # tick `to_line`: the 53rd hp, and the site is on line again
    assert now(site) == (LINE, "DAMAGED", None)
    assert damage_changes(events, site.id) == [(site.id, "DISABLED", "DAMAGED")]
    if node == FOB:  # one site here: 3.9 stock to the line, drawn in whole units
        assert start - w.stock[node] == 3
    events += run(w, to_full - 1)
    assert site.hp < FULL and of(events, UnitRepaired) == []
    events += run(w)  # tick `to_full` after the line: full hp and UnitRepaired
    assert site.hp == FULL and site.id in [r.entity_id for r in of(events, UnitRepaired)]
    if node == FOB:
        spent = sum(e.amount for e in of(events, SupplyConsumed) if e.cause == "REPAIR")
        assert spent == start - w.stock[node] == 13  # 13.6 to full; the 0.6 is the stop's flush


def test_with_no_slowdown_the_seized_repair_takes_the_struck_sites_65_ticks() -> None:
    w = world(capture__seized_repair_slowdown=1)
    site = site_at(w, AIRBASE)
    take(w, AIRBASE, "COALITION")
    assert site.seized_carry == 0
    run(w, 64)
    assert site.hp < LINE and site.seized_carry == 0
    run(w)
    assert now(site) == (LINE, "DAMAGED", None)  # 39 hp at 0.6 a tick: 65 ticks, 6.5 game s


def test_the_carry_makes_a_fractional_rate_exact() -> None:
    w = world(capture__seized_repair_slowdown=7)  # 300 / 7 is not whole: the carry holds the rest
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    run(w, 7)
    assert (site.repair_milli, site.seized_carry) == (300, 0)  # 7 ticks x 300 / 7, nothing lost
    run(w, 3)
    assert (site.repair_milli, site.seized_carry) == (428, 4)  # 3 x 300 = 900 = 128 x 7 + 4
    assert 0 <= (site.seized_carry or 0) < 7


def test_a_slowed_tick_that_earns_no_whole_thousandth_still_moves_the_carry() -> None:
    w = world(capture__seized_repair_slowdown=600)  # a FOB's 300 a tick: 0, 1, 0, 1 thousandths
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    events = run(w, 1_001)
    # 1,001 x 300 / 600 = 500 whole thousandths, carry 300; without the carry move it stays at 0
    assert (site.hp, site.repair_milli, site.seized_carry) == (FLOOR, 500, 300)
    assert of(events, RearmStalled) == []  # a progress tick is not a stall
    run(w, 1)
    assert (site.repair_milli, site.seized_carry) == (501, 0)


# --- no supply, no repair ----------------------------------------------------------------------


@pytest.mark.parametrize("slow", [92, 600])  # 600: the slowed ticks that earn 0 thousandths
def test_a_starved_seized_site_makes_no_progress_and_a_delivery_restarts_it(slow: int) -> None:
    w = world(capture__seized_repair_slowdown=slow)
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    w.stock[FOB] = 0
    stalls = of(run(w, 30), RearmStalled)  # the first thousandths owed settle in these ticks
    frozen = (site.hp, site.repair_milli, site.repair_debt, site.seized_carry)
    stalls += of(run(w, 1_000), RearmStalled)
    assert (site.hp, site.repair_milli, site.repair_debt, site.seized_carry) == frozen
    assert len(stalls) == 1 and site.damage_state == "DISABLED"
    if slow == 600:  # an unpaid slowed tick leaves the carry where it was (it would sit at 300)
        assert site.seized_carry == 0
    w.stock[FOB] = 100  # a delivery
    run(w, 10)
    assert site.repair_milli > frozen[1] or site.hp > frozen[0]
    assert site.seized_carry is not None


def test_a_capture_bar_pauses_the_repair() -> None:
    w = world()
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    run(w, 50)
    w.capture[FOB] = CaptureBar("ENEMY", 5_000_000)  # a counterattack under way
    frozen = (site.hp, site.repair_milli, site.repair_debt, site.seized_carry)
    run(w, 1)
    assert FOB in w.capture
    assert (site.hp, site.repair_milli, site.repair_debt, site.seized_carry) == frozen
    del w.capture[FOB]
    run(w, 5)
    assert (site.hp, site.repair_milli) != frozen[:2] and site.seized_carry is not None


# --- retaken mid-repair ------------------------------------------------------------------------


def test_a_retake_mid_repair_and_a_third_flip_seize_the_site_afresh() -> None:
    w = fast()
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    until(w, lambda: site.hp >= 40, 3_000)
    assert site.damage_state == "DISABLED" and site.seized_carry is not None
    for side in ("ENEMY", "COALITION"):
        events = take(w, FOB, side)
        assert (site.side, site.hp, site.damage_state, site.seized_carry) == (
            side,
            FLOOR,
            "DISABLED",
            0,
        )
        assert damage_changes(events) == []  # still Disabled: no event
        run(w, 100)
        assert site.hp > FLOOR and site.seized_carry is not None  # and it repairs again, slowly
        until(w, lambda: site.hp >= 30, 3_000)


# --- parity -----------------------------------------------------------------------------------


def test_a_static_capture_of_a_coalition_base_mirrors_a_coalition_capture_of_a_static_one() -> None:
    def seize(node: str, side: Any) -> tuple[Any, ...]:
        w = fast()
        site = site_at(w, node)
        events = take(w, node, side) + run(w, 600)
        mine = ("NodeCaptured", "UnitDamageStateChanged", "UnitRepaired", "RearmStalled")
        shape = [
            (e.kind, getattr(e, "from_", None), getattr(e, "to", None), getattr(e, "amount", None))
            for e in events
            if e.kind in mine or (e.kind == "SupplyConsumed" and e.cause == "REPAIR")
        ]  # not the economy (a Static base earns supply a coalition one does not)
        return (shape, site.hp, site.damage_state, site.seized_carry, site.repair_milli,
                site.repair_debt, w.stock[node])  # fmt: skip

    coalition = seize(FOB, "COALITION")
    static = seize(WEST_FOB, "ENEMY")
    swap = {"COALITION": "ENEMY", "ENEMY": "COALITION"}
    mirrored = [(k, swap.get(a, a), swap.get(b, b), n) for k, a, b, n in static[0]]
    assert mirrored == coalition[0] and static[1:6] == coalition[1:6]
    assert static[6] == coalition[6]  # both bases start with 500 stock


# --- the switch off is today -------------------------------------------------------------------


def test_with_the_switch_off_a_flip_keeps_damage_and_a_healthy_site_fires_for_its_new_owner() -> (
    None
):
    w = world(capture__facilities_disabled=False)
    site = site_at(w, FOB)
    site.hp, site.damage_state = 77, "DAMAGED"
    events = take(w, FOB, "COALITION")
    assert (site.side, site.hp, site.damage_state, site.seized_carry) == (
        "COALITION",
        77,
        "DAMAGED",
        None,
    )
    assert damage_changes(events) == []
    w = world(capture__facilities_disabled=False)
    healthy = site_at(w, FOB)
    take(w, FOB, "COALITION")
    assert healthy.seized_carry is None and healthy.damage_state == "HEALTHY"
    assert hang(w, healthy)(10, until_fire=True)  # a healthy site fires for its new owner


def legacy_run(**keys: Any) -> str:
    """A capture, a retake, a second capture and 300 ticks of repair under the default keys, as
    the events' hash. Uses only what exists before NX-471, so the pinned value was produced by the
    code before it."""
    w = world(**keys)
    events: list[Event] = []
    site = site_at(w, FOB)
    site.hp, site.damage_state = 90, "DAMAGED"
    for side in ("COALITION", "ENEMY", "COALITION"):
        events += take(w, FOB, side)
        events += run(w, 120)
    events += run(w, 300)
    text = "\n".join(e.model_dump_json() for e in events)
    return hashlib.blake2b(text.encode(), digest_size=16).hexdigest() + f":{len(events)}"


LEGACY_EVENTS = "3f8d901c5822e5a6813516567d6c36f2:25"  # made at d9984b2, before NX-471


def test_a_scripted_capture_and_retake_run_with_the_switch_off_is_the_code_before_nx_471() -> None:
    assert legacy_run(capture__facilities_disabled=False) == LEGACY_EVENTS


# --- determinism and snapshots -----------------------------------------------------------------


def seize_retake_and_repair() -> tuple[str, str]:
    w = fast()
    site = site_at(w, FOB)
    events = take(w, FOB, "COALITION") + run(w, 200)
    events += take(w, FOB, "ENEMY") + run(w, 100)
    events += take(w, FOB, "COALITION")
    events += until(w, lambda: site.seized_carry is None, 4_000) + run(w, 50)
    text = "\n".join(e.model_dump_json() for e in events)
    return hashlib.blake2b(text.encode(), digest_size=16).hexdigest(), state_hash(w)


def test_seize_repair_retake_and_back_on_line_is_deterministic() -> None:
    assert seize_retake_and_repair() == seize_retake_and_repair()


def test_a_snapshot_taken_mid_repair_round_trips_to_the_same_run() -> None:
    w = fast()
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    run(w, 333)
    assert site.seized_carry is not None and site.hp > FLOOR
    again = load(save(w))
    again.rules = w.rules
    combat_mod.validate(again, w.rules)  # type: ignore[arg-type]
    assert state_hash(again) == state_hash(w)
    assert run(again, 200) == run(w, 200) and state_hash(again) == state_hash(w)
    carry = w.find(site.id).seized_carry  # type: ignore[union-attr]
    h = state_hash(w)
    site.seized_carry = (carry or 0) + 1
    assert state_hash(w) != h  # the carry is in the hash


def restored(w: World, mutate: Any) -> None:
    """Round-trips `w` through the loader with `mutate(raw entity dicts)`, then validates."""
    raw = msgpack.unpackb(save(w), raw=False)
    mutate(raw["entities"])
    loaded = load(msgpack.packb(raw, use_bin_type=True))
    loaded.rules = w.rules
    combat_mod.validate(loaded, w.rules)  # type: ignore[arg-type]


def test_restore_refuses_a_bad_seized_carry_and_the_old_format() -> None:
    w = fast()
    site = site_at(w, FOB)
    take(w, FOB, "COALITION")
    run(w, 20)

    def set_carry(value: Any, state: str | None = None, hp: int | None = None) -> Any:
        def mutate(entities: list[dict[str, Any]]) -> None:
            for d in entities:
                if d["id"] == site.id:
                    d["seized_carry"] = value
                    d["damage_state"] = state or d["damage_state"]
                    d["hp"] = d["hp"] if hp is None else hp

        return mutate

    restored(w, set_carry(site.seized_carry))
    with pytest.raises(ValueError, match="seized_carry"):
        restored(w, set_carry(20))  # at S (20) or above
    with pytest.raises(ValueError, match="seized_carry"):
        restored(w, set_carry(-1))
    with pytest.raises(ValueError, match="seized_carry"):
        restored(w, set_carry(0, "HEALTHY", FULL))  # not Disabled
    unit = next(e for e in w.entities() if e.kind == INFANTRY or e.base_id is None)
    with pytest.raises(ValueError, match="seized_carry"):
        restored(w, lambda es: [d.update(seized_carry=0) for d in es if d["id"] == unit.id])
    off = fast(capture__facilities_disabled=False)
    off_site = site_at(off, FOB)
    off_site.seized_carry = 0  # a switch-off world holds no seized site
    off_site.hp, off_site.damage_state = FLOOR, "DISABLED"
    with pytest.raises(ValueError, match="seized_carry"):
        combat_mod.validate(off, off.rules)  # type: ignore[arg-type]
    raw = msgpack.unpackb(save(w), raw=False)
    raw["v"] = 38
    with pytest.raises(ValueError, match="unsupported snapshot format version 38"):
        load(msgpack.packb(raw, use_bin_type=True))
