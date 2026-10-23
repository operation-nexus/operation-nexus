"""NX-157: the Threat Director's Pattern of Life (THREAT-DIRECTOR §5, §5a, §7a; Q-SIM-85, TD-1,
TD-2, Q-TD-11, Q-GP-44, Q-SIM-84).

Runs on the shipped strait-1 config with the campaign layer off. Shipped numbers: garrison quotas
east-airbase 6, fob-n-e 4, fob-s-e 4, static-hq 8; GARRISON_UPKEEP costs 8; patrols every 1,800
game s, supply convoys every 3,600, one capture operation every 21,600; the night cap is one
Static flip per 6 game hours with no viewer unit. The long run is simulated once and shared.
"""

import dataclasses
import functools
import itertools
from fractions import Fraction
from typing import Any

import msgpack
import pytest
from test_launch import (
    DR,
    enemy_units,
    run_clock,
    skip,
    unit,
)
from test_launch import RULES as BARE
from test_launch import new_world as bare_world
from test_launch import window as bare_window

from nexus.contracts.gen.common.enums import Side, ThreatTier, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import operations as ops
from nexus.core.director import night_capped
from nexus.core.fog import side_view
from nexus.core.launch import _own
from nexus.core.provocation import validate
from nexus.core.rules import CAPTURE_FULL, CP_SCALE, Rules, TaskingRules
from nexus.core.step import step
from nexus.core.tasking_gen import generate
from nexus.core.world import CaptureBar, Entity, World, load, save, state_hash

QUOTA = {"east-airbase": 6, "fob-n-e": 4, "fob-s-e": 4, "static-hq": 8}
RULES = dataclasses.replace(BARE, garrison_quota=QUOTA)  # the shipped quotas (test_launch has none)


def new_world(seed: int = 1, rules: Rules = RULES, *, opening: bool = False) -> World:
    """The shipped campaign start; its opening garrison (Q-SIM-86) only with `opening`, as most of
    these tests fill, send or lose a garrison themselves."""
    w = bare_world(seed, rules)
    return w if opening else empty_garrison(w)


def window(
    w: World, tier: ThreatTier = "ALPHA", budget: int = 80, rules: Rules = RULES
) -> list[Event]:
    return bare_window(w, tier, budget, rules)


def with_director(**changes: Any) -> Rules:
    return dataclasses.replace(RULES, director=dataclasses.replace(DR, **changes))


def empty_garrison(w: World) -> World:
    """`w` without its opening garrison, for a test about filling or sending one."""
    for e in list(w.entities()):
        if e.home is not None:
            w.remove(e.id)
    return w


GARRISON_ONLY = with_director(
    operations=tuple(o for o in DR.operations if o.id == "GARRISON_UPKEEP"),
)


def homed(w: World) -> dict[str, list[Entity]]:
    out: dict[str, list[Entity]] = {}
    for e in w.entities():
        if e.home is not None:
            out.setdefault(e.home, []).append(e)
    return out


def live_ops(w: World) -> set[tuple[str, str]]:
    return set(ops.live_pairs([j.key for j in w.boards["ENEMY"].values()]))


def viewer(w: World) -> Entity:
    return unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "haven")


# --- the long overnight run (shared) -------------------------------------------------------------

# The 6-game-hour night (216,000 ticks, ~65 s) with its two long periods divided by 12, so the
# run is 1.5 game hours: a capture operation every 30 game minutes, the night cap 30 game minutes.
# The real periods (6 h) are pinned by the golden-rules checks below, not simulated here.
COMPRESS = 12
NIGHT_RULES = with_director(
    offensive_ticks=DR.offensive_ticks // COMPRESS, night_cap_ticks=DR.night_cap_ticks // COMPRESS
)
OVERNIGHT_TICKS = 40_000


def look_staleness(w: World, rules: Rules) -> Fraction:
    """The Static's mean staleness over the theater's recon cells: 1 for a cell no sensor covered
    within `director.recon.memory_s`, else the time since over that time (0 fresh)."""
    dr, now = rules.director, w.campaign.running_ticks + 1
    assert dr is not None
    width, height = rules.bounds_m
    cells = int(width // dr.recon_grid_m) * int(height // dr.recon_grid_m)
    seen = w.director["ENEMY"].looked
    fresh = sum(1 - Fraction(now - t, dr.recon_memory_ticks) for t in seen.values())
    return Fraction(1) - Fraction(fresh) / cells


@functools.cache
def overnight() -> dict[str, Any]:
    """1.5 game hours with the long periods compressed, 0 viewers, no commands; stats are taken
    every decision window."""
    w = new_world(7, NIGHT_RULES)
    s = w.director["ENEMY"]
    cap = DR.max_live_units["PATTERN_OF_LIFE"]
    stats: dict[str, Any] = {
        "tier_changes": 0, "peak_prov": 0, "over_quota": [], "over_cap": [], "idle_homed": [],
        "td2": [], "at_36000": {}, "captured": [], "kinds": set(),
        "scouts": set(), "scout_losses": 0, "stale": [], "points": set(),
    }  # fmt: skip
    for i in range(OVERNIGHT_TICKS):
        for e in step(w, []):
            stats["kinds"].add(e.kind)
            if e.kind == "UnitSpawned" and e.unit_kind == "ENEMY_RECON_UAV":
                stats["scouts"].add(e.entity_id)
            stats["scout_losses"] += e.kind == "UnitDestroyed" and e.entity_id in stats["scouts"]
            if e.kind == "ThreatTierChanged":
                stats["tier_changes"] += 1
            if e.kind == "NodeCaptured":
                stats["captured"].append((w.campaign.tick, e.from_, e.to))
        if (i + 1) % DR.window_ticks:
            continue
        stats["peak_prov"] = max(stats["peak_prov"], s.provocation, s.prov_level)
        by_base = homed(w)
        stats["over_quota"] += [b for b, u in by_base.items() if len(u) > QUOTA.get(b, 0)]
        stats["over_cap"] += [len(enemy_units(w))] if len(enemy_units(w)) > cap else []
        stats["idle_homed"] += [k for k in s.idle if (u := w.find(int(k))) and u.home]
        view = side_view(w, "ENEMY")
        stats["stale"].append(look_staleness(w, NIGHT_RULES))
        stats["points"] |= {
            (j.pos.x, j.pos.y)
            for j in w.boards["ENEMY"].values()
            if j.pos is not None and j.key.startswith("op:RECON")
        }
        stats["td2"] += [
            j.key
            for j in w.boards["ENEMY"].values()
            if (j.node is not None and j.node not in view.nodes)
            or (j.via is not None and j.via not in view.nodes)
        ]
        if i + 1 == 36_000:
            stats["at_36000"] = {b: [u.kind for u in us] for b, us in by_base.items()}
    stats["world"] = w
    return stats


def test_overnight_with_no_viewers_there_is_no_escalation_and_at_most_a_node_per_cap() -> None:
    run = overnight()
    assert run["tier_changes"] == 0 and run["peak_prov"] == 0  # criterion 1: no escalation
    lost = [t for t, frm, to in run["captured"] if frm == "COALITION" and to == "ENEMY"]
    flips = [t for t, _, to in run["captured"] if to == "ENEMY"]
    cap = NIGHT_RULES.director.night_cap_ticks  # type: ignore[union-attr]  # the config has one
    assert all(b - a >= cap for a, b in itertools.pairwise(flips))  # one flip per cap
    assert all(b - a >= cap for a, b in itertools.pairwise(lost))  # one node lost per 6 game h
    # the capture slot fired in its period (every 21,600 game s / 12) and did not escalate
    assert run["world"].director["ENEMY"].last_offensive >= DR.offensive_ticks // COMPRESS
    assert run["world"].director["ENEMY"].tier == "PATTERN_OF_LIFE"


def test_recon_losses_and_stock_burn_fall_well_below_nx_157s_and_the_picture_stays_fresh() -> None:
    """Q-SIM-87 against NX-157's 0-viewer run (about 14 scouts lost and 70 stock burnt per game
    hour; mean look staleness 0.29 over 6 hours, by the same rule from the sensors' coverage)."""
    run = overnight()
    hours = OVERNIGHT_TICKS / 36_000
    recon = next(o for o in DR.operations if o.id == "RECON")
    burn = len(run["scouts"]) * recon.cost  # a scout reused from an idle unit costs nothing
    assert run["scout_losses"] / hours <= 14 / 4
    assert burn / hours <= 70 / 2  # 18 an hour in this run, which starts with its opening scouts
    assert len(run["scouts"]) > 0  # it still scouts
    assert len(run["points"]) >= 8  # and to many places (NX-157's run: 3 nodes)
    assert sum(run["stale"]) / len(run["stale"]) <= 0.25  # 0.17 here; NX-157's run: 0.29


def test_upkeep_fills_each_base_to_its_quota_in_turn_and_never_beyond() -> None:
    run = overnight()
    assert run["over_quota"] == []
    assert {b: len(k) for b, k in run["at_36000"].items()} == QUOTA
    for base in ("fob-n-e", "fob-s-e", "static-hq"):  # FOBs and the HQ: armor
        assert set(run["at_36000"][base]) == {"ENEMY_ARMOR"}
    airbase = run["at_36000"]["east-airbase"]  # the two kinds in turn, 3 + 3
    assert (airbase.count("ENEMY_FIGHTER"), airbase.count("ENEMY_ARMOR")) == (3, 3)


def test_no_unit_leak_over_a_long_run_and_the_td2_view_holds() -> None:
    run = overnight()
    assert run["over_cap"] == []  # never above max_live_units.pattern_of_life
    assert run["idle_homed"] == []  # a garrison unit at its base is never on the retirement clock
    assert run["td2"] == []  # every job node and patrol turn is a node the Static's view holds
    w: World = run["world"]
    assert len(enemy_units(w)) <= DR.max_live_units["PATTERN_OF_LIFE"]


def test_stock_plus_cargo_plus_consumed_stays_exact_with_upkeep_and_convoys() -> None:
    w = new_world(2, GARRISON_ONLY)
    for node in QUOTA:  # every Static base at its floor: only the rear source can fill a convoy
        w.stock[node] = RULES.supply.starve_floor[node]

    def total() -> int:
        return sum(w.stock.values()) + sum(e.cargo or 0 for e in w.entities())

    start, spent, convoys = total(), 0, 0
    for _ in range(DR.convoy_ticks + 4 * DR.window_ticks):
        for e in step(w, []):
            spent += e.amount if e.kind == "SupplyConsumed" else 0
            convoys += e.kind == "UnitSpawned" and e.unit_kind == DR.convoy_kind
    # nothing is created but cargo loaded at an infinite source, and every unit it holds counts
    gained = total() + spent - start
    assert convoys >= 1 and 0 <= gained <= convoys * RULES.supply.truck_cargo
    assert all(0 <= s <= RULES.supply.max_stock[n] for n, s in w.stock.items())


# --- garrison upkeep and retirement (Q-SIM-85 (2), (3)) ------------------------------------------


def test_a_lost_garrison_unit_is_replaced_once_and_paid_from_surplus() -> None:
    w = new_world(1, GARRISON_ONLY)
    for _ in range(4):  # one replacement a window per short base: four windows fill nothing yet
        out = window(w, "PATTERN_OF_LIFE", 8, GARRISON_ONLY)
        assert len([e for e in out if e.kind == "UnitSpawned"]) == 1  # the budget pays one
        run_clock(w, 120)  # the unit stages at its base
    spawned = [e for e in homed(w).values()]
    assert sum(len(u) for u in spawned) == 4
    before = sum(w.stock.values())
    out = window(w, "PATTERN_OF_LIFE", 8, GARRISON_ONLY)
    paid = [e.amount for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN"]
    assert paid == [8] and sum(w.stock.values()) == before - 8  # the catalog cost, from stock


def test_a_base_at_quota_is_no_candidate_and_a_loss_makes_it_one_again() -> None:
    w = new_world()
    for base, n in QUOTA.items():
        for _ in range(n):
            unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", base).home = base
    own = _own(w, RULES, "ENEMY")
    view = side_view(w, "ENEMY")
    w.director["ENEMY"].tier = "PATTERN_OF_LIFE"
    live = frozenset[tuple[str, str]]()

    def short() -> list[str]:
        cands = ops.candidates(w.director["ENEMY"], view, RULES, _own(w, RULES, "ENEMY"), 1, live)
        return [c.target for c in cands if c.op.id == "GARRISON_UPKEEP"]

    assert own.homed["fob-n-e"] == ("ENEMY_ARMOR",) * 4 and short() == []
    w.remove(homed(w)["fob-n-e"][0].id)
    assert short() == ["fob-n-e"]


def test_retirement_takes_only_units_above_the_quota_highest_id_first() -> None:
    w = new_world()
    garrison = [unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e") for _ in range(6)]
    for e in garrison:
        e.home = "fob-n-e"
    stray = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")  # no home: as before
    window(w, "PATTERN_OF_LIFE", 0)
    assert w.director["ENEMY"].idle.keys() == {str(e.id) for e in garrison[4:]} | {str(stray.id)}
    skip(w, DR.idle_retire_ticks)
    out = window(w, "PATTERN_OF_LIFE", 0)
    gone = {e.entity_id for e in out if e.kind == "UnitDespawned"}
    assert gone == {garrison[4].id, garrison[5].id, stray.id}  # the two above the quota of 4
    assert [e.id for e in homed(w)["fob-n-e"]] == [e.id for e in garrison[:4]]


def test_a_lost_base_has_no_quota_so_its_idle_garrison_retires() -> None:
    w = new_world()
    keep = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    keep.home = "fob-n-e"
    w.owner["fob-n-e"] = "COALITION"
    window(w, "PATTERN_OF_LIFE", 0)
    skip(w, DR.idle_retire_ticks)
    out = window(w, "PATTERN_OF_LIFE", 0)
    assert [e.entity_id for e in out if e.kind == "UnitDespawned"] == [keep.id]


def test_a_garrison_unit_never_takes_a_job_from_the_board_by_itself() -> None:
    w = new_world()
    stay = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    stay.home = "fob-n-e"
    from nexus.core.tasking import post_job
    from nexus.core.tasking_gen import JobSpec

    post_job(w, "ENEMY", JobSpec("STAGE", "op:X:east-airbase:0", 2, 1000, node="east-airbase"), [])
    run_clock(w, 2 * RULES.tasking.reeval_every_ticks)  # type: ignore[union-attr]
    assert stay.job_id is None and not stay.path


# --- patrols (Q-SIM-85 (4)) ----------------------------------------------------------------------


def test_the_patrol_turns_at_the_node_toward_the_front_neutral_or_not_never_the_enemys() -> None:
    w = new_world()
    view = side_view(w, "ENEMY")
    via = {b: ops.patrol_via(view, RULES, b) for b in QUOTA}
    assert via == {  # the neutral bridgeheads are the front; the HQ, behind it, goes to the airbase
        "east-airbase": "cross-n", "fob-n-e": "cross-n", "fob-s-e": "cross-s",
        "static-hq": "east-airbase",
    }  # fmt: skip
    w.owner["cross-n"] = "COALITION"  # a node the other side holds is never a turning point
    assert ops.patrol_via(side_view(w, "ENEMY"), RULES, "fob-n-e") == "static-hq"


def test_an_idle_garrison_unit_drives_out_and_home_on_the_patrol_period_and_the_job_is_done() -> (
    None
):
    w = new_world(1, GARRISON_ONLY)
    u = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    u.home = "fob-n-e"
    s = w.director["ENEMY"]
    skip(w, DR.patrol_ticks - 2)
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    assert not w.boards["ENEMY"] and s.last_patrol == 0  # not due: one tick early
    skip(w, 1)
    out = window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "PATROL"]
    assert (job.key, job.node, job.via, s.last_patrol) == (
        "op:POL_PATROL:fob-n-e:0", "fob-n-e", "cross-n", DR.patrol_ticks,
    )  # fmt: skip
    assert u.job_id == job.id and u.path[-1] == "fob-n-e" and "cross-n" in u.path
    assert any(e.kind == "JobCreated" and e.job_kind == "PATROL" for e in out)
    seen: set[str | None] = set()
    done: list[Event] = []
    for _ in range(40_000):
        for e in step(w, []):
            if e.kind == "JobDone" and e.job_id == job.id:
                done.append(e)
        seen.add(u.last_node)
        assert "cross-n" not in w.capture  # a patrolling unit never captures the node it turns at
        if done:
            break
    assert done and "cross-n" in seen  # it reached the turning node and came home
    assert w.owner["cross-n"] == "NEUTRAL" and w.director["ENEMY"].last_flip == 0
    assert u.last_node == "fob-n-e" and not u.path and u.job_id is None
    assert [e.entity_id for e in done[0].participants] == [u.id]
    assert u.home == "fob-n-e"


def test_a_base_whose_only_idle_unit_is_an_aircraft_or_none_posts_no_patrol() -> None:
    w = new_world(1, GARRISON_ONLY)
    jet = unit(w, "ENEMY_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "east-airbase")
    jet.home = "east-airbase"
    skip(w, DR.patrol_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    assert [j for j in w.boards["ENEMY"].values() if j.kind == "PATROL"] == []


# --- convoys (Q-SIM-85 (5)) ----------------------------------------------------------------------


def test_the_convoy_runs_to_the_base_with_the_largest_upkeep_shortfall_and_only_then() -> None:
    w = new_world(1, GARRISON_ONLY)
    s = w.director["ENEMY"]
    view = side_view(w, "ENEMY")
    assert ops.convoy_bases(view, RULES, _own(w, RULES, "ENEMY")) == []  # all stocked: none short
    w.stock["fob-n-e"] = RULES.supply.starve_floor["fob-n-e"]  # no surplus: 4 x 8 short
    w.stock["fob-s-e"] = RULES.supply.starve_floor["fob-s-e"] + 10  # 4 x 8 - 10 short
    assert ops.convoy_bases(view, RULES, _own(w, RULES, "ENEMY")) == ["fob-n-e", "fob-s-e"]
    skip(w, DR.convoy_ticks - 2)
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    assert not any(j.kind == "RESUPPLY" for j in w.boards["ENEMY"].values())  # one tick early
    skip(w, 1)
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"]
    assert (job.key, job.node, s.last_convoy) == (
        "op:POL_CONVOY:fob-n-e:0",
        "fob-n-e",
        DR.convoy_ticks,
    )
    (truck,) = [e for e in enemy_units(w) if e.kind == DR.convoy_kind]
    assert truck.job_id == job.id
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)  # not posted twice
    assert len([j for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"]) == 1


# --- night progress (Q-SIM-85 (6)) ---------------------------------------------------------------


def test_the_cap_is_spent_for_one_over_cap_hours_counted_from_the_last_flip() -> None:
    s = new_world().director["ENEMY"]
    assert not night_capped(s, DR, 5)
    s.last_flip = 100
    assert night_capped(s, DR, 100 + DR.night_cap_ticks - 1)
    assert not night_capped(s, DR, 100 + DR.night_cap_ticks)
    assert DR.night_cap_ticks == 216_000  # 1 / (1/6) game hours at 10 ticks a game second


def flip_ready(w: World, *nodes: str) -> None:
    for n in nodes:
        unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", n)
        w.capture[n] = CaptureBar("ENEMY", CAPTURE_FULL - 1)


def test_with_no_viewer_the_second_flip_waits_a_night_cap_and_the_bar_holds_just_short() -> None:
    w = new_world()
    flip_ready(w, "cross-n", "cross-s")
    step(w, [])
    assert (w.owner["cross-n"], w.owner["cross-s"]) == ("ENEMY", "NEUTRAL")
    assert w.director["ENEMY"].last_flip == 1
    for _ in range(20):
        step(w, [])
    assert w.owner["cross-s"] == "NEUTRAL" and w.capture["cross-s"].progress == CAPTURE_FULL - 1
    skip(w, DR.night_cap_ticks)
    step(w, [])
    assert dict(w.owner)["cross-s"] == "ENEMY"  # the cap is over: it flips
    assert w.director["ENEMY"].last_flip == w.campaign.running_ticks


def test_with_a_viewer_unit_there_is_no_hold_but_the_flip_still_starts_the_cap_clock() -> None:
    w = new_world()
    v = viewer(w)
    flip_ready(w, "cross-n", "cross-s")
    step(w, [])
    assert (w.owner["cross-n"], w.owner["cross-s"]) == ("ENEMY", "ENEMY")  # nothing held
    assert w.director["ENEMY"].last_flip == 1 and w.director["ENEMY"].held == {}
    w.remove(v.id)  # the viewer leaves: the clock the flip started now holds the next one
    w.owner["cross-n"] = w.owner["cross-s"] = "NEUTRAL"
    flip_ready(w, "cross-n")
    step(w, [])
    assert w.owner["cross-n"] == "NEUTRAL" and "cross-n" in w.director["ENEMY"].held


def test_a_bar_held_by_the_cap_stays_held_when_a_viewer_arrives_and_frees_one_at_a_time() -> None:
    w = new_world()
    w.director["ENEMY"].last_flip = 1  # the cap is spent
    flip_ready(w, "cross-n", "cross-s")
    step(w, [])
    held = dict(w.director["ENEMY"].held)
    assert sorted(held) == ["cross-n", "cross-s"] and w.owner["cross-n"] == "NEUTRAL"
    viewer(w)  # a viewer joins: nobody sees the held bases fall at once
    for _ in range(30):
        step(w, [])
    assert (w.owner["cross-n"], w.owner["cross-s"]) == ("NEUTRAL", "NEUTRAL")
    assert w.capture["cross-n"].progress == CAPTURE_FULL - 1 and w.director["ENEMY"].held == held
    skip(w, DR.night_cap_ticks)  # the cap frees: one flips, the other waits a full cap again
    step(w, [])
    assert (w.owner["cross-n"], w.owner["cross-s"]) == ("ENEMY", "NEUTRAL")
    assert sorted(w.director["ENEMY"].held) == ["cross-s"]
    for _ in range(30):
        step(w, [])
    assert w.owner["cross-s"] == "NEUTRAL"


def test_a_held_bar_leaves_the_set_when_it_is_drained_and_survives_a_snapshot() -> None:
    w = new_world()
    w.director["ENEMY"].last_flip = 1
    flip_ready(w, "cross-n")
    step(w, [])
    assert sorted(w.director["ENEMY"].held) == ["cross-n"]
    again = load(save(w))
    again.rules = RULES
    assert again.director["ENEMY"].held == w.director["ENEMY"].held
    assert state_hash(again) == state_hash(w)
    for e in [e for e in w.entities() if e.last_node == "cross-n"]:
        w.remove(e.id)  # its capturers are gone ...
    w.capture["cross-n"].progress -= 10  # ... and coalition units drained it: not at the flip
    step(w, [])
    assert w.director["ENEMY"].held == {}


def test_the_director_launches_no_capture_operation_while_the_cap_is_spent() -> None:
    rules = with_director(
        max_spawns_per_window=30, max_live_units={t: 90 for t in DR.max_live_units},
        noise=DR.noise * 0,
    )  # fmt: skip

    def launched(capped: bool) -> set[str]:
        w = new_world(1, rules)
        if capped:
            w.director["ENEMY"].last_flip = 1
        window(w, "BRAVO", 300, rules)
        return {op for op, _ in live_ops(w)}

    assert "OFFENSIVE" in launched(False)
    assert launched(True) & {"OFFENSIVE", "RETAKE"} == set()
    assert launched(True)  # everything else still runs


def test_the_pol_capture_slot_launches_one_on_its_period_from_real_surplus() -> None:
    w = new_world()
    s = w.director["ENEMY"]
    skip(w, DR.offensive_ticks - 2)
    window(w, "PATTERN_OF_LIFE", 0)
    assert s.last_offensive == 0 and not any(p[0] == "OFFENSIVE" for p in live_ops(w))
    skip(w, 1)
    before = sum(w.stock.values())
    window(w, "PATTERN_OF_LIFE", 0)  # a zero window budget: the slot is outside it
    caps = {p for p in live_ops(w) if p[0] in ("OFFENSIVE", "RETAKE")}
    assert len(caps) == 1 and s.last_offensive == DR.offensive_ticks
    assert sum(w.stock.values()) < before  # paid from the stock
    window(w, "PATTERN_OF_LIFE", 0)
    assert {p for p in live_ops(w) if p[0] in ("OFFENSIVE", "RETAKE")} == caps  # not a second one


def test_the_pol_capture_slot_waits_while_the_cap_is_spent_and_is_pol_only() -> None:
    w = new_world()
    w.director["ENEMY"].last_flip = 1
    skip(w, DR.offensive_ticks - 1)  # the period is over, the cap (from tick 1) is not
    window(w, "PATTERN_OF_LIFE", 0)
    assert w.director["ENEMY"].last_offensive == 0
    assert not {p for p in live_ops(w) if p[0] in ("OFFENSIVE", "RETAKE")}
    w2 = new_world()
    skip(w2, DR.offensive_ticks)
    window(w2, "ALPHA", 0)  # at ALPHA the slot is not used: the tier's own operations apply
    assert w2.director["ENEMY"].last_offensive == 0


# --- acceptance: 0 to 1 viewer, staging seen by scouts only within coverage ---------------------


def test_one_viewer_arriving_changes_nothing_until_that_operator_provokes() -> None:
    w = new_world(opening=True)  # the shipped config: the idle-viewer strike gate (Q-SIM-92) holds
    viewer(w)
    s = w.director["ENEMY"]
    events = run_clock(w, 24 * DR.window_ticks)
    assert [e for e in events if e.kind == "ThreatTierChanged"] == []
    assert (s.tier, s.prov_level, s.provocation) == ("PATTERN_OF_LIFE", 0, 0)
    for _ in range(14 * 1):  # then provocation: the tier steps once the dwell is spent
        s.pending += 15 * CP_SCALE
        run_clock(w, DR.window_ticks)
    assert s.tier == "ALPHA"


def test_staging_is_visible_to_a_scout_only_inside_its_sensor_coverage() -> None:
    w = new_world()
    armor = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "east-airbase")
    radius = RULES.sensor_radius_m["RECON_UAV"]
    far = unit(w, "RECON_UAV", "COALITION", "COMMANDER", "haven")
    near = unit(w, "RECON_UAV", "COALITION", "COMMANDER", "west-airbase")
    x, y = RULES.roads.pos["east-airbase"]
    near.pos = dataclasses.replace(near.pos, x=x - 0.5 * radius, y=y)
    far.pos = dataclasses.replace(far.pos, x=x - 3 * radius, y=y)
    for _ in range(RULES.track_every_ticks + 2):
        step(w, [])
    assert armor.id in w.contacts["COALITION"]  # the near scout holds it
    near.pos = dataclasses.replace(near.pos, x=x - 3 * radius)
    w.contacts["COALITION"].clear()
    for _ in range(RULES.track_every_ticks + 2):
        step(w, [])
    assert armor.id not in w.contacts["COALITION"]  # no scout in range: not visible


# --- time, snapshot, determinism -----------------------------------------------------------------


def test_the_pol_timers_are_game_time_and_a_pause_freezes_them() -> None:
    w = new_world()
    u = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    u.home = "fob-n-e"
    run_clock(w, DR.patrol_ticks - 3 * DR.window_ticks)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    ticks = w.campaign.running_ticks
    run_clock(w, 2 * DR.patrol_ticks)  # long past the period in wall ticks
    assert w.campaign.running_ticks == ticks and w.director["ENEMY"].last_patrol == 0
    assert not any(j.kind == "PATROL" for j in w.boards["ENEMY"].values())
    w.campaign.clock_paused, w.campaign.pause_reason = False, None
    run_clock(w, 3 * DR.window_ticks + 5)
    assert w.director["ENEMY"].last_patrol == DR.patrol_ticks


@functools.cache
def _pol_snapshot() -> bytes:
    w = new_world(3, opening=True)
    run_clock(w, DR.patrol_ticks - 400)
    assert homed(w)  # garrison units exist: the patrol window has something to send
    return save(w)


def pol_world() -> World:
    """A world 400 ticks before the first patrol window, restored from one shared run."""
    w = load(_pol_snapshot())
    w.rules = RULES
    return w


def test_a_restored_world_runs_the_same_events_with_the_pol_state_and_format_20_is_refused() -> (
    None
):
    w = pol_world()
    again = load(save(w))
    again.rules = RULES
    assert state_hash(again) == state_hash(w)
    live, restored = run_clock(w, 3 * DR.window_ticks), run_clock(again, 3 * DR.window_ticks)
    assert any(e.kind == "JobCreated" and e.job_kind == "PATROL" for e in live)
    assert [e.model_dump(by_alias=True) for e in live] == [
        e.model_dump(by_alias=True) for e in restored
    ]
    assert state_hash(again) == state_hash(w)
    assert again.director["ENEMY"].last_patrol == DR.patrol_ticks
    raw = msgpack.unpackb(save(w), raw=False)
    raw["v"] = 20
    with pytest.raises(ValueError, match="unsupported snapshot format version 20"):
        load(msgpack.packb(raw, use_bin_type=True))


def _entity(raw: dict[str, Any], **changes: object) -> None:
    next(e for e in raw["entities"] if e["home"] is not None).update(changes)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw["director"]["ENEMY"].update(last_patrol=10**9),
        lambda raw: raw["director"]["ENEMY"].update(last_flip=10**9),
        lambda raw: raw["director"]["ENEMY"].update(last_convoy=7),  # no window sets that
        lambda raw: raw["director"]["ENEMY"].update(held={"nowhere": 5}),
        lambda raw: raw["director"]["ENEMY"].update(held={"cross-n": 10**9}),
        lambda raw: _entity(raw, home="nowhere"),
        lambda raw: _entity(raw, owner_kind="AI_GARRISON"),
        lambda raw: raw["boards"]["ENEMY"][0].update(via="static-hq"),  # a via on a non-patrol
    ],
)
def test_a_corrupt_pol_state_is_refused(mutate: Any) -> None:
    w = pol_world()
    run_clock(w, 2 * DR.window_ticks)
    raw = msgpack.unpackb(save(w), raw=False)
    mutate(raw)
    with pytest.raises(ValueError):
        validate(load(msgpack.packb(raw, use_bin_type=True)), RULES)


def test_pol_needs_the_director_rules_and_the_kernel_stays_generic() -> None:
    """The catalog names the upkeep operation; the kernel names no operation id but its own jobs."""
    import inspect

    from nexus.core import launch, operations

    assert "GARRISON_UPKEEP" not in inspect.getsource(launch) + inspect.getsource(operations)
    plain: Rules = dataclasses.replace(RULES, garrison_quota={})
    w = new_world(1, plain)
    run_clock(w, 2 * DR.window_ticks)
    assert homed(w) == {}  # no quota: no upkeep


def test_a_window_with_every_pol_timer_due_at_a_thousand_entities_is_fast() -> None:
    import time

    w = new_world()
    for i in range(1000):
        side, owner = ("COALITION", "COMMANDER") if i % 2 else ("ENEMY", "ENEMY_DIRECTOR")
        kind: UnitKind = "STRIKE_FIGHTER" if side == "COALITION" else "ENEMY_ARMOR"
        e = unit(w, kind, side, owner, "west-airbase" if side == "COALITION" else "fob-n-e")
        if side == "ENEMY" and i % 4 == 0:
            e.home = "fob-n-e"
    skip(w, DR.offensive_ticks - 1)  # patrol, convoy and capture timers all due
    view = side_view(w, "ENEMY")
    start = time.perf_counter()
    for _ in range(3):
        for t in ("last_patrol", "last_convoy", "last_offensive"):
            setattr(w.director["ENEMY"], t, 0)
        window(w, "PATTERN_OF_LIFE", 80)
        view = side_view(w, "ENEMY")
    assert (time.perf_counter() - start) / 3 < 0.5
    assert view.side == "ENEMY"


def test_td2_the_pattern_of_life_decisions_read_the_view_and_own_only() -> None:
    """`patrol_via`, `convoy_bases` and the garrison kind live in `nexus.core.operations`, which
    never names `World` or an entity accessor; what they need beyond the view is `Own`."""
    import ast
    from pathlib import Path

    import nexus.core.operations as module

    tree = ast.parse(Path(module.__file__).read_text())
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"World", "Entity"} and not attrs & {"entities", "find", "stock"}


# --- garrison defence, no board offense at Pattern of Life, the keys (Q-SIM-85) -------------------


def test_a_garrison_unit_defends_its_own_base_and_no_other_job_from_the_board() -> None:
    w = new_world()
    mine = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    mine.home = "fob-n-e"
    other = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-s-e")
    other.home = "fob-s-e"
    w.capture["fob-n-e"] = CaptureBar("COALITION", CAPTURE_FULL // 2)  # a bar on its own base
    run_clock(w, RULES.tasking.reeval_every_ticks)  # type: ignore[union-attr]  # one board pass
    job = w.boards["ENEMY"][mine.job_id or -1]
    assert (job.kind, job.node) == ("DEFEND", "fob-n-e")  # its own base
    assert other.job_id is None  # another base's garrison is not drawn to it


def test_an_operation_never_takes_a_garrison_unit() -> None:
    w = new_world()
    keep = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    keep.home = "fob-n-e"
    free = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")  # no home: reusable
    rules = with_director(
        max_spawns_per_window=20, max_live_units={t: 90 for t in DR.max_live_units}
    )
    window(w, "BRAVO", 300, rules)
    assert keep.job_id is None and not keep.path
    assert free.job_id is not None  # the unhomed unit fills a slot first, as before


def marked_world() -> World:
    """The Static has discovered the coalition's SAM site at west-airbase: a strike target."""
    from nexus.core.world import FacilityMarker, Vec2

    w = new_world()
    pos = Vec2(*RULES.roads.pos["west-airbase"])
    w.defense_hp["west-airbase"] = 100
    unit(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "east-airbase")  # can staff it
    w.markers["ENEMY"][99] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", pos, True, 1, 40000, "HEALTHY"
    )
    return w


def tasking_rules() -> TaskingRules:
    assert RULES.tasking is not None
    return RULES.tasking


def strike_keys(w: World, rules: Rules = RULES, side: Side = "ENEMY") -> list[str]:
    assert rules.tasking is not None
    specs = generate(w, rules, rules.tasking, side, side_view(w, side))
    return [s.key for s in specs if s.kind == "STRIKE"]


def test_the_static_board_posts_no_strike_at_pattern_of_life_and_does_from_alpha() -> None:
    w = marked_world()
    assert tasking_rules().static_offense_min_tier == "ALPHA"
    assert strike_keys(w) == []  # tier Pattern of Life
    w.director["ENEMY"].tier = "ALPHA"
    assert strike_keys(w) == ["strike:west-airbase"]


def test_a_lowered_gate_lets_the_static_board_strike_at_pattern_of_life() -> None:
    tasking = dataclasses.replace(tasking_rules(), static_offense_min_tier="PATTERN_OF_LIFE")
    open_rules = dataclasses.replace(RULES, tasking=tasking)
    assert strike_keys(marked_world(), open_rules) == ["strike:west-airbase"]


def test_the_coalition_board_is_not_gated_by_the_static_tier() -> None:
    w = marked_world()
    w.markers["COALITION"][98] = w.markers["ENEMY"][99]  # a site it has found, on its own node
    w.owner["west-airbase"] = "ENEMY"  # so it is the foe's: a strike target for the coalition
    w.defense_hp["west-airbase"] = 100
    assert w.director["ENEMY"].tier == "PATTERN_OF_LIFE"
    assert strike_keys(w, RULES, "COALITION") == ["strike:west-airbase"]


def test_the_capture_chain_still_strikes_at_pattern_of_life() -> None:
    w = new_world()
    skip(w, DR.offensive_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0)
    kinds = {j.kind for j in w.boards["ENEMY"].values()}
    assert {"STAGE", "STRIKE", "CAPTURE"} <= kinds  # the Director's own operation, not the board's
    assert all(j.key.startswith("op:") for j in w.boards["ENEMY"].values() if j.kind == "STRIKE")


def test_replace_per_window_buys_that_many_units_in_kind_turn_at_most_the_shortfall() -> None:
    rules = with_director(
        garrison_kinds={**DR.garrison_kinds, "AIRBASE": ("ENEMY_FIGHTER", "ENEMY_ARMOR")},
        replace_per_window=3,
        max_spawns_per_window=12,
        operations=GARRISON_ONLY.director.operations,  # type: ignore[union-attr]
    )
    w = new_world(1, rules)
    out = window(w, "PATTERN_OF_LIFE", 200, rules)
    by_base: dict[str, list[str]] = {}
    for e in out:
        if e.kind == "UnitSpawned":
            by_base.setdefault(e.node_id, []).append(e.unit_kind)
    assert by_base["east-airbase"] == ["ENEMY_FIGHTER", "ENEMY_ARMOR", "ENEMY_FIGHTER"]
    assert len(by_base["fob-n-e"]) == 3 and 3 * 8 * 4 >= sum(
        e.amount for e in out if e.kind == "SupplyConsumed"
    )  # the catalog cost per unit
    for base, n in QUOTA.items():  # never beyond the shortfall
        assert len(homed(w)[base]) == min(3, n)


def test_patrols_per_base_sends_that_many_idle_units_each_on_its_own_job() -> None:
    rules = with_director(
        patrols_per_base=2,
        operations=GARRISON_ONLY.director.operations,  # type: ignore[union-attr]
    )
    w = new_world(1, rules)
    us = [unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e") for _ in range(3)]
    for u in us:
        u.home = "fob-n-e"
    skip(w, DR.patrol_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0, rules)
    keys = sorted(j.key for j in w.boards["ENEMY"].values() if j.kind == "PATROL")
    assert keys == ["op:POL_PATROL:fob-n-e:0", "op:POL_PATROL:fob-n-e:1"]
    assert [u.job_id is not None for u in us] == [True, True, False]  # the lowest ids go


def test_convoys_per_period_and_convoy_cost_are_keys() -> None:
    rules = with_director(
        convoys_per_period=2,
        convoy_cost=7,
        operations=GARRISON_ONLY.director.operations,  # type: ignore[union-attr]
    )
    w = new_world(1, rules)
    for n in ("fob-n-e", "fob-s-e", "static-hq"):
        w.stock[n] = RULES.supply.starve_floor[n]
    before = sum(w.stock.values())
    skip(w, DR.convoy_ticks - 1)
    out = window(w, "PATTERN_OF_LIFE", 0, rules)
    jobs = sorted(j.key for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY")
    assert jobs == ["op:POL_CONVOY:fob-n-e:0", "op:POL_CONVOY:static-hq:0"]  # 64, then 32 (id)
    spent = sum(e.amount for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN")
    cargo = sum(e.cargo or 0 for e in w.entities())  # the two trucks loaded at a finite base
    assert spent == 2 * 7  # a new carrier each
    assert sum(w.stock.values()) + cargo == before - spent


def test_convoy_slots_is_the_units_one_pol_convoy_job_takes() -> None:
    """NX-388, Q-DEV-21: the shipped 1 is the old single-truck convoy; 2 posts a 2-slot job."""
    for slots in (1, 2):
        rules = with_director(
            convoy_slots=slots,
            operations=GARRISON_ONLY.director.operations,  # type: ignore[union-attr]
        )
        w = new_world(1, rules)
        w.stock["fob-n-e"] = RULES.supply.starve_floor["fob-n-e"]
        skip(w, DR.convoy_ticks - 1)
        window(w, "PATTERN_OF_LIFE", 0, rules)
        (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"]
        assert job.slots == slots


def test_a_convoy_needs_room_for_all_its_slots() -> None:
    """A 3-slot job spawns 3 units, so it waits for room for 3 (spawn window and live caps)."""
    ops_ = GARRISON_ONLY.director.operations  # type: ignore[union-attr]
    for room, spawned in ((1, 0), (3, 3)):
        rules = with_director(
            convoy_slots=3, max_spawns_per_window=room, operations=ops_,
            max_live_units={t: 90 for t in DR.max_live_units},
        )  # fmt: skip
        w = new_world(1, rules)
        w.stock["fob-n-e"] = RULES.supply.starve_floor["fob-n-e"]
        before = len(list(w.entities()))
        skip(w, DR.convoy_ticks - 1)
        window(w, "PATTERN_OF_LIFE", 0, rules)
        assert len(list(w.entities())) - before == spawned


def test_a_snapshot_with_a_pattern_of_life_ceiling_restores() -> None:
    """`director.tier.alpha_enter_cp` > 0 holds the ceiling at 0; the load check allows it."""
    rules = with_director(alpha_enter_cp=20 * CP_SCALE)
    w = new_world(1, rules)
    for _ in range(DR.window_ticks):  # one real decision window
        step(w, [])
    state = w.director["ENEMY"]
    assert state.windows >= 1 and state.ceiling == 0
    again = load(save(w))
    again.rules = rules
    assert again.director["ENEMY"].ceiling == 0 and state_hash(again) == state_hash(w)


def test_a_paid_convoy_is_paid_before_its_carrier_loads_so_it_never_overdraws() -> None:
    sup = RULES.supply
    cost = sup.forward_deploy_min_surplus  # the only surplus is the spawn base's, exactly the cost
    rules = with_director(convoy_cost=cost, operations=GARRISON_ONLY.director.operations)  # type: ignore[union-attr]
    w = new_world(1, rules)
    for n in sup.starve_floor:
        w.stock[n] = sup.starve_floor[n]
    w.stock["east-airbase"] += cost  # the carrier spawns here and would load this surplus first
    w.stock["fob-n-e"] -= 50  # short, so a convoy is due
    before = sum(w.stock.values())
    skip(w, DR.convoy_ticks - 1)
    out = window(w, "PATTERN_OF_LIFE", 0, rules)  # paying after loading would raise here
    spent = sum(e.amount for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN")
    cargo = sum(e.cargo or 0 for e in w.entities())
    assert spent == cost
    assert sum(w.stock.values()) + cargo == before - spent


def test_offensives_per_period_launches_that_many_capture_operations() -> None:
    rules = with_director(
        offensives_per_period=2, max_spawns_per_window=30,
        max_live_units={t: 90 for t in DR.max_live_units},
    )  # fmt: skip
    w = new_world(1, rules)
    skip(w, DR.offensive_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0, rules)
    caps = {p for p in live_ops(w) if p[0] in ("OFFENSIVE", "RETAKE")}
    assert len(caps) == 2


# --- Q-SIM-86: the economy, the opening garrison, going home, the patrol slots -------------------


def test_a_convoy_refills_a_base_below_its_floor_even_with_a_full_garrison() -> None:
    w = new_world(1, opening=True)
    w.stock["east-airbase"] = 0  # below the floor: the shortfall is the floor less the stock
    view = side_view(w, "ENEMY")
    own = _own(w, RULES, "ENEMY")
    assert own.margin["east-airbase"] == -RULES.supply.starve_floor["east-airbase"]
    assert ops.convoy_bases(view, RULES, own) == ["east-airbase"]
    skip(w, DR.convoy_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"]
    assert job.key == "op:POL_CONVOY:east-airbase:0"
    for _ in range(30_000):
        step(w, [])
        if w.stock["east-airbase"]:
            break
    assert w.stock["east-airbase"] > 0  # the convoy arrived and unloaded


def test_a_base_at_its_floor_with_a_full_garrison_needs_no_convoy() -> None:
    w = new_world(1, opening=True)
    for n in QUOTA:
        w.stock[n] = RULES.supply.starve_floor[n]
    assert ops.convoy_bases(side_view(w, "ENEMY"), RULES, _own(w, RULES, "ENEMY")) == []


def test_the_loader_refuses_a_garrison_kind_that_cannot_rest_at_its_base_kind() -> None:
    assert ops.misfits(RULES) == []
    air_at_hq = with_director(garrison_kinds={**DR.garrison_kinds, "HQ": ("ENEMY_FIGHTER",)})
    assert any("cannot land at static-hq" in m for m in ops.misfits(air_at_hq))
    armor_at_nowhere = dataclasses.replace(RULES, garrison_quota={"bridge-n": 1})
    assert any("bridge-n" in m for m in ops.misfits(armor_at_nowhere))


def test_static_bases_start_at_quota_free_homed_and_the_same_every_time() -> None:
    w, bare = new_world(1, opening=True), new_world(1)
    assert {b: len(u) for b, u in homed(w).items()} == QUOTA
    assert [e.kind for e in homed(w)["east-airbase"]] == ["ENEMY_FIGHTER", "ENEMY_ARMOR"] * 3
    assert {e.kind for e in homed(w)["static-hq"] + homed(w)["fob-n-e"]} == {"ENEMY_ARMOR"}
    assert all(e.state == "LANDED" for e in homed(w)["east-airbase"] if e.kind == "ENEMY_FIGHTER")
    assert w.stock == bare.stock  # free: no stock debited, no event
    assert all(
        e.owner_kind == "ENEMY_DIRECTOR" and e.last_node == e.home for e in w.entities() if e.home
    )
    ids = [e.id for b in sorted(QUOTA) for e in homed(w)[b]]
    assert ids == sorted(ids)  # in node id order
    assert state_hash(new_world(1, opening=True)) == state_hash(w)
    assert own_homed(w) == QUOTA


def own_homed(w: World) -> dict[str, int]:
    return {b: len(k) for b, k in _own(w, RULES, "ENEMY").homed.items()}


def test_an_idle_garrison_unit_away_from_its_held_home_is_sent_home() -> None:
    w = new_world(1, GARRISON_ONLY)
    away = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    away.home = "fob-n-e"
    jet = unit(w, "ENEMY_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", "static-rear")
    jet.home = "east-airbase"
    lost = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    lost.home = "fob-s-e"
    w.owner["fob-s-e"] = "COALITION"  # its home fell: nothing to go home to
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    assert away.path[-1] == "fob-n-e" and jet.path == ["east-airbase"] and lost.path == []
    for _ in range(40_000):
        step(w, [])
        if away.last_node == "fob-n-e" and not away.path:
            break
    assert away.last_node == "fob-n-e" and not away.path


def test_a_patrol_whose_turning_node_is_lost_still_ends_with_the_unit_home() -> None:
    w = new_world(1, GARRISON_ONLY)
    u = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    u.home = "fob-n-e"
    skip(w, DR.patrol_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "PATROL"]
    w.owner[job.via or ""] = "COALITION"  # the node it turns at falls to the coalition
    for _ in range(40_000):
        step(w, [])
        if u.job_id is None and not u.path:
            break
    assert u.job_id is None and u.last_node == "fob-n-e" and not u.path


def test_a_patrol_that_fails_on_a_lost_home_drops_its_route_and_never_captures() -> None:
    w = new_world(1, GARRISON_ONLY)
    u = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    u.home = "fob-n-e"
    skip(w, DR.patrol_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0, GARRISON_ONLY)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "PATROL"]
    while u.last_node != job.via:  # out at the turning node, about to head home
        step(w, [])
    w.owner["fob-n-e"] = "COALITION"  # its home falls while it is away: the patrol fails
    for _ in range(20_000):
        step(w, [])
        assert u.job_id is None or u.job_id == job.id
        if u.job_id is None:
            assert not u.path or u.path[-1] != "fob-n-e"  # no stale route to the lost base
        for node, bar in w.capture.items():
            assert bar.side != "ENEMY", node  # a failed patrol never starts a capture


def test_a_unit_that_is_no_patrol_does_capture_where_it_stands() -> None:
    """The control for the patrol test: the same neutral node, a unit with no job."""
    w = new_world()
    unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    step(w, [])
    assert w.capture["cross-n"].side == "ENEMY"


def test_a_garrison_unit_never_captures_where_it_stands() -> None:
    """A garrison only defends (Q-SIM-86): the same neutral node as the control, a homed unit."""
    w = new_world()
    u = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "cross-n")
    u.home = "fob-n-e"
    step(w, [])
    assert "cross-n" not in w.capture


def test_patrol_slots_is_the_crew_of_one_patrol_job() -> None:
    rules = with_director(patrol_slots=2, operations=GARRISON_ONLY.director.operations)  # type: ignore[union-attr]
    w = new_world(1, rules)
    us = [unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e") for _ in range(3)]
    for u in us:
        u.home = "fob-n-e"
    skip(w, DR.patrol_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0, rules)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.kind == "PATROL"]
    assert job.slots == 2 and sorted(job.claims) == [us[0].id, us[1].id]
    assert us[2].job_id is None
