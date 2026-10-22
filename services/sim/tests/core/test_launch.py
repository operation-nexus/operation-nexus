"""NX-156: the Threat Director's operations (THREAT-DIRECTOR §2, §4 steps 3-8, §7; TD-1, TD-2, TD-5;
Q-TD-4, Q-TD-6, Q-TD-8, Q-TD-12, Q-SIM-78, Q-SIM-81).

Runs on the shipped strait-1 config with the campaign layer off. A window is run by hand
(`window`: the tier and budget set, then `launch.run`) unless a test needs the clock, which then
uses real `step`s. Shipped numbers: costs OFFENSIVE 60, RETAKE 50, ESCORT_CONVOYS 10, REINFORCE_IADS
15, PROBE 15, RECON 2, DECOY_BLINK 0; at most 6 new units a window; memory half-life 30 windows.
On strait-1 an OFFENSIVE does not complete by itself (Q-SIM-84):
the strike step loses jets to air defense or has too few rounds for a full base, so the chain
tests clear the coalition's air defense and weaken the target first; that is left to balance
(NX-031).
"""

import dataclasses
import random
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter

from nexus.contracts.gen.common.enums import ThreatTier, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.contracts.gen.events.job_failed import JobFailed
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.core import operations as ops
from nexus.core.director import decide
from nexus.core.fog import side_view
from nexus.core.launch import _launch, _own, _routine, _spawn
from nexus.core.launch import run as launch
from nexus.core.provocation import captured, suffered_hit
from nexus.core.rng import RngStream
from nexus.core.rules import CP_SCALE, DirectorRules, Rules
from nexus.core.step import step
from nexus.core.world import Entity, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import REPO, ConfigPaths, load_campaign_config, start_campaign

CONFIG = load_campaign_config()
# the campaign layer off and no opening garrison (Q-SIM-86): NX-156's tests start from an empty
# Static, test_pol.py puts the quotas back
RULES = dataclasses.replace(CONFIG.rules, campaign=None, garrison_quota={})
_dr = RULES.director
if _dr is None:
    raise AssertionError("the shipped config has Director rules")
DR: DirectorRules = _dr
CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
STATIC_BASES = ("east-airbase", "fob-n-e", "fob-s-e", "static-hq")
ARMOR: UnitKind = "ENEMY_ARMOR"
EVERY = RULES.tasking.reeval_every_ticks  # type: ignore[union-attr]


def new_world(seed: int = 1, rules: Rules = RULES) -> World:
    return start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(CONFIG, rules=rules))


def clear_coalition_defenses(w: World) -> None:
    """The coalition's air-defense sites would shoot a strike down: a chain test removes them."""
    for e in list(w.entities()):
        if e.side == "COALITION" and e.base_id:
            w.remove(e.id)


def window(
    w: World, tier: ThreatTier = "ALPHA", budget: int = 80, rules: Rules = RULES
) -> list[Event]:
    """One window of operations at `tier` with `budget` points."""
    s = w.director["ENEMY"]
    s.tier, s.budget = tier, budget
    out: list[Event] = []
    launch(w, "ENEMY", side_view(w, "ENEMY"), rules, out)
    return out


def candidates(w: World, tier: ThreatTier = "ALPHA") -> list[ops.Candidate]:
    w.director["ENEMY"].tier = tier
    live = ops.live_pairs([j.key for j in w.boards["ENEMY"].values()])
    return ops.candidates(
        w.director["ENEMY"], side_view(w, "ENEMY"), RULES, _own(w, RULES, "ENEMY"),
        w.campaign.running_ticks + 1, live,
    )  # fmt: skip


def ids(cands: list[ops.Candidate], op: str) -> list[str]:
    return [c.target for c in cands if c.op.id == op]


def enemy_units(w: World) -> list[Entity]:
    return [e for e in w.entities() if e.owner_kind == "ENEMY_DIRECTOR"]


def unit(w: World, kind: UnitKind, side: str, owner: str, node: str) -> Entity:
    e = w.spawn(kind, side, owner, Vec2(*RULES.roads.pos[node]))  # type: ignore[arg-type]
    e.last_node = node
    if RULES.domain[kind] == "AIR":
        e.state, e.fuel = "LANDED", RULES.fuel_s[kind]
    return e


def zero_noise(rules: Rules) -> Rules:
    return dataclasses.replace(rules, director=dataclasses.replace(DR, noise=Fraction(0)))


# --- threat memory (§2, Q-SIM-81) -----------------------------------------------------------------


def test_memory_counts_what_the_static_suffers_whoever_hits_it() -> None:
    w = new_world()
    pilot = unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "west-airbase")
    garrison = unit(w, "GARRISON_INFANTRY", "COALITION", "AI_GARRISON", "west-airbase")
    convoy = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    scout = unit(w, "ENEMY_RECON_UAV", "ENEMY", "ENEMY_DIRECTOR", "fob-s-e")
    (radar,) = [e for e in w.entities() if e.base_id == "east-airbase" and e.kind == "RADAR_SITE"]
    s = w.director["ENEMY"]
    suffered_hit(w, pilot, convoy, "HEALTHY")
    suffered_hit(w, garrison, convoy, "HEALTHY")  # an AI garrison unit counts for memory only
    suffered_hit(w, pilot, radar, "HEALTHY")
    assert (s.convoy_attacks, s.radar_strikes) == (2 * CP_SCALE, CP_SCALE)
    assert s.pending == 3 * CP_SCALE + 3 * CP_SCALE  # provocation: the pilot's two hits only
    scout.hp = 0  # destroyed: gone from the world
    w.remove(scout.id)
    suffered_hit(w, pilot, scout, "HEALTHY")
    assert s.recon_losses == {"south": CP_SCALE}
    captured(w, "fob-n-e", "ENEMY", "COALITION", 0)
    assert s.node_losses == {"north": CP_SCALE} and s.lost == {"fob-n-e": 1}
    captured(w, "fob-n-e", "COALITION", "ENEMY", 0)
    assert s.lost == {}


def test_a_hit_on_a_wreck_is_no_new_convoy_attack() -> None:
    w = new_world()
    pilot = unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "west-airbase")
    convoy = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    suffered_hit(w, pilot, convoy, "DISABLED")
    assert w.director["ENEMY"].convoy_attacks == 0


def test_threat_memory_decays_with_its_half_life() -> None:
    w = new_world()
    s = w.director["ENEMY"]
    s.convoy_attacks, s.node_losses = 4 * CP_SCALE, {"north": 8 * CP_SCALE, "south": 1}
    view = side_view(w, "ENEMY")
    for _ in range(30):  # 30 windows of 60 s = the 1,800 s half-life
        decide(s, view, RULES, w.stock)
    assert abs(s.convoy_attacks - 2 * CP_SCALE) < 100
    assert abs(s.node_losses["north"] - 4 * CP_SCALE) < 100
    assert "south" not in s.node_losses  # a counter that reaches 0 leaves the map
    for _ in range(600):
        decide(s, view, RULES, w.stock)
    assert s.convoy_attacks == 0 and s.node_losses == {}


# --- candidates (step 3, TD-2) --------------------------------------------------------------------


def test_candidates_follow_the_tier_and_the_preconditions() -> None:
    w = new_world()
    alpha = candidates(w)
    assert ids(alpha, "OFFENSIVE") == ["fob-n-w", "fob-s-w", "west-airbase"]  # no sanctuary
    assert ids(alpha, "PROBE") == ["fob-n-w", "fob-s-w"]  # the front: a neutral bridgehead beyond
    assert ids(alpha, "RECON") == ["centre", "north", "south"]
    assert ids(alpha, "DECOY_BLINK") == ["east-airbase", "static-hq"]
    assert (
        ids(alpha, "RETAKE") == ids(alpha, "ESCORT_CONVOYS") == ids(alpha, "REINFORCE_IADS") == []
    )
    routine = {c.op.id for c in candidates(w, "PATTERN_OF_LIFE")}
    assert routine == {"RECON", "DECOY_BLINK"}  # no quota here; no convoy yet, no offensive


def test_a_selector_that_resolves_to_nothing_drops_the_operation() -> None:
    w = new_world()
    for node in ("east-airbase", "fob-n-e", "fob-s-e", "static-hq"):
        w.owner[node] = "COALITION"  # the Static owns no base: no `nearest_own_base`
    assert ids(candidates(w), "OFFENSIVE") == []
    w = new_world()
    assert "OFFENSIVE" in {c.op.id for c in candidates(w)}


def test_retake_needs_a_node_lost_within_the_window() -> None:
    w = new_world()
    w.owner["fob-n-e"] = "COALITION"
    s = w.director["ENEMY"]
    s.lost["fob-n-e"] = 1
    w.campaign.running_ticks = DR.retake_ticks - 2
    assert ids(candidates(w), "RETAKE") == ["fob-n-e"]
    w.campaign.running_ticks = DR.retake_ticks + 1
    assert ids(candidates(w), "RETAKE") == []


def test_escort_candidate_is_the_unescorted_moving_convoys() -> None:
    w = new_world()
    a = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    b = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")  # parked: no path
    a.path, b.path = ["fob-n-e"], ["fob-s-e"]
    (cand,) = [c for c in candidates(w) if c.op.id == "ESCORT_CONVOYS"]
    assert [x.entity for x in cand.wheres[0]] == [a.id, b.id]
    w.director["ENEMY"].convoy_attacks = (
        3 * CP_SCALE
    )  # raided: escorts outrank the routine scouting
    window(w, "PATTERN_OF_LIFE", 30)
    escorts = {j.entity for j in w.boards["ENEMY"].values() if j.kind == "ESCORT_CONVOY"}
    assert escorts == {a.id, b.id}


# --- scoring (step 4, Q-TD-6, Q-TD-4, TD-5) -------------------------------------------------------


def scores(
    w: World, rules: Rules = RULES, tier: ThreatTier = "ALPHA"
) -> dict[tuple[str, str], Fraction]:
    cands = candidates(w, tier)
    ranked = ops.rank(
        cands, w.director["ENEMY"], side_view(w, "ENEMY"), rules, w.rng.stream(RngStream.DIRECTOR)
    )
    return {(c.op.id, c.target): c.score for c in ranked}


def test_the_score_is_priority_value_weakness_memory_and_proximity_exactly() -> None:
    quiet = zero_noise(RULES)
    w = new_world()
    base = scores(w, quiet)
    assert base["OFFENSIVE", "west-airbase"] == Fraction(3, 2)  # 1.0 x 1.5 x full defenses
    assert base["OFFENSIVE", "fob-n-w"] == 1 and base["PROBE", "fob-n-w"] == Fraction(3, 5)
    top = RULES.defense.max_hp["west-airbase"]  # type: ignore[union-attr]
    w.defense_hp["west-airbase"] = top // 2
    assert scores(w, quiet)["OFFENSIVE", "west-airbase"] == Fraction(3, 2) * Fraction(3, 2)
    w.defense_hp["west-airbase"] = 0
    assert scores(w, quiet)["OFFENSIVE", "west-airbase"] == Fraction(3, 2) * 2  # 2.0 at none
    s = w.director["ENEMY"]
    s.node_losses = {"north": CP_SCALE}  # RETAKE x (1 + 1) in the sector; none lost here yet
    s.convoy_attacks = 3 * CP_SCALE
    s.lost["fob-n-e"] = 1
    w.owner["fob-n-e"] = "COALITION"
    assert scores(w, quiet)["RETAKE", "fob-n-e"] == Fraction(6, 5) * 1 * 2


def test_recon_utility_rises_with_stale_tracks_and_falls_with_scout_losses() -> None:
    quiet = zero_noise(RULES)
    w = new_world()
    s = w.director["ENEMY"]
    blind = scores(w, quiet)["RECON", "north"]
    assert blind == Fraction(1, 2) * 2  # no track at all: staleness 1
    from nexus.core.world import Contact

    w.contacts["ENEMY"][900] = Contact("STRIKE_FIGHTER", Vec2(100e3, 20e3), Vec2(0, 0))
    assert scores(w, quiet)["RECON", "north"] == Fraction(1, 2)  # a current track: fresh
    w.contacts["ENEMY"][900].age = RULES.track_fade_ticks // 2
    assert scores(w, quiet)["RECON", "north"] == Fraction(1, 2) * Fraction(3, 2)
    s.recon_losses = {"north": 2 * CP_SCALE}
    assert scores(w, quiet)["RECON", "north"] == Fraction(1, 2) * Fraction(3, 2) / 3


def test_q_td_4_after_a_sensed_strike_in_a_sector_the_top_candidate_targets_it() -> None:
    quiet = zero_noise(RULES)
    w = new_world()
    pilot = unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "west-airbase")
    victim = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-s-e")

    def top() -> tuple[str, str]:
        table = scores(w, quiet)
        return max(table, key=lambda k: (table[k], k))

    assert top() == ("OFFENSIVE", "west-airbase")  # the airbase is worth most
    suffered_hit(w, pilot, victim, "HEALTHY")  # a sensed strike in the south
    s = w.director["ENEMY"]
    assert s.last_provocation_sector == "south" and s.ceiling == 1
    w.defense_hp["fob-s-w"] = RULES.defense.max_hp["fob-s-w"] // 2  # type: ignore[union-attr]
    assert top() == ("OFFENSIVE", "fob-s-w")
    assert scores(w, quiet)["OFFENSIVE", "fob-s-w"] == Fraction(3, 2) * Fraction(
        3, 2
    )  # x 1.5, x 1.5
    s.ceiling = 2  # the BRAVO ceiling: no proximity
    assert scores(w, quiet)["OFFENSIVE", "fob-s-w"] == Fraction(3, 2)


def test_same_seed_same_scores_and_the_order_of_the_catalog_file_changes_nothing(
    tmp_path: Path,
) -> None:
    def trace(config_ops: Path | None) -> tuple[list[object], str]:
        paths = (
            ConfigPaths()
            if config_ops is None
            else dataclasses.replace(ConfigPaths(), operations=config_ops)
        )
        cfg = load_campaign_config(paths)
        rules = dataclasses.replace(cfg.rules, campaign=None)
        w = start_campaign(CAMPAIGN_ID, 7, dataclasses.replace(cfg, rules=rules))
        got = scores(w, rules)
        events = window(w, rules=rules)
        return [sorted(got.items()), [e.model_dump(by_alias=True) for e in events]], state_hash(w)

    shuffled = yaml.safe_load((REPO / "content" / "operations.yaml").read_text(encoding="utf-8"))
    random.Random(3).shuffle(shuffled["operations"])  # noqa: S311 - a seeded test shuffle
    path = tmp_path / "ops.yaml"
    path.write_text(yaml.safe_dump(shuffled), encoding="utf-8")
    first, again, other = trace(None), trace(None), trace(path)
    assert first == again == other
    w = new_world(8)  # another seed draws other noise
    assert sorted(scores(w).items()) != first[0][0]


# --- selection, budget, spawning (steps 6-7, Q-TD-8, Q-TD-12) -------------------------------------


def surplus(w: World) -> int:
    return sum(max(0, w.stock[n] - RULES.supply.starve_floor[n]) for n in STATIC_BASES)


def test_an_operation_is_paid_once_from_the_surplus_of_the_static_bases() -> None:
    w = new_world()
    before = {n: w.stock[n] for n in STATIC_BASES}
    events = window(w, budget=60)
    spent = sum(e.amount for e in events if e.kind == "SupplyConsumed")
    assert spent == 60  # OFFENSIVE's cost, not a unit more (no loadout charge)
    assert sum(before.values()) - sum(w.stock[n] for n in STATIC_BASES) == 60
    spawned = [e for e in events if e.kind == "UnitSpawned"]
    assert len(spawned) == 6 and all(e.owner_kind == "ENEMY_DIRECTOR" for e in spawned)
    assert all(e.side == "ENEMY" for e in spawned)


def test_one_spawn_goes_to_the_nearest_qualifying_base_else_the_rear_source() -> None:
    w = new_world()
    floor = RULES.supply.starve_floor
    for n in STATIC_BASES:
        w.stock[n] = floor[n]  # every base at its floor: none qualifies
    out: list[Event] = []
    armor, node = _spawn(w, RULES, "ENEMY", ARMOR, "fob-n-w", out)
    assert node == "static-rear" and armor.last_node == "static-rear"
    w.stock["fob-n-e"] = floor["fob-n-e"] + RULES.supply.forward_deploy_min_surplus
    w.stock["fob-s-e"] = floor["fob-s-e"] + 10_000  # richer but farther from fob-n-w
    _, node = _spawn(w, RULES, "ENEMY", ARMOR, "fob-n-w", out)
    assert node == "fob-n-e"
    w.stock["fob-n-e"] = floor["fob-n-e"] + RULES.supply.forward_deploy_min_surplus - 1
    _, node = _spawn(w, RULES, "ENEMY", ARMOR, "fob-n-w", out)
    assert node == "fob-s-e"  # the next nearest that qualifies


@given(
    stocks=st.lists(st.integers(0, 1200), min_size=4, max_size=4),
    budget=st.integers(0, 80),
    tier=st.sampled_from(["PATTERN_OF_LIFE", "ALPHA", "BRAVO"]),
    seed=st.integers(0, 50),
)
@settings(max_examples=60, deadline=None)
def test_the_budget_is_never_exceeded_nor_the_real_stock_nor_a_base_taken_below_its_floor(
    stocks: list[int], budget: int, tier: ThreatTier, seed: int
) -> None:
    w = new_world(seed)
    for n, v in zip(STATIC_BASES, stocks, strict=True):
        w.stock[n] = v
    s = w.director["ENEMY"]
    s.tier = tier
    start = surplus(w)
    decide(s, side_view(w, "ENEMY"), RULES, w.stock)
    s.tier = tier
    s.budget = min(budget, s.budget)
    events = window(w, tier, s.budget)
    spent = sum(e.amount for e in events if e.kind == "SupplyConsumed")
    assert spent <= s.budget <= min(budget, start, DR.budget[tier])
    assert start - surplus(w) == spent
    floor = RULES.supply.starve_floor
    assert all(w.stock[n] >= min(v, floor[n]) for n, v in zip(STATIC_BASES, stocks, strict=True))
    assert len([e for e in events if e.kind == "UnitSpawned"]) <= DR.max_spawns_per_window
    if s.budget == 0:  # a starved Static posts nothing it cannot fund
        assert [e for e in events if e.kind in ("UnitSpawned", "JobCreated")] == []


def test_the_caps_bound_new_units_and_live_units() -> None:
    w = new_world()
    events = window(w, "BRAVO", 80)
    assert len([e for e in events if e.kind == "UnitSpawned"]) <= DR.max_spawns_per_window
    w = new_world()
    for _ in range(DR.max_live_units["ALPHA"] - 3):  # room for 3 more only
        unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    events = window(w, "ALPHA", 80)
    assert len([e for e in events if e.kind == "UnitSpawned"]) <= 3


def non_routine(w: World) -> set[tuple[str, str]]:
    routine = ops.routine_ops(DR)
    live = ops.live_pairs([j.key for j in w.boards["ENEMY"].values()])
    return {p for p in live if p[0] not in routine}


def test_alpha_runs_one_operation_at_a_time_and_a_live_one_is_not_posted_again() -> None:
    w = new_world()
    window(w, "ALPHA", 80)
    assert len(non_routine(w)) == 1
    n_jobs = len(w.boards["ENEMY"])
    window(w, "ALPHA", 80)
    assert len(non_routine(w)) == 1  # the cap holds while it is live
    assert len(w.boards["ENEMY"]) >= n_jobs
    w2 = new_world()
    window(w2, "BRAVO", 80)
    window(w2, "BRAVO", 80)
    live = [p for p in ops.live_pairs([j.key for j in w2.boards["ENEMY"].values()])]
    assert len(live) == len(set(live)) >= 2  # BRAVO adds more, never the same one twice


def test_routine_operations_do_not_count_against_the_alpha_cap() -> None:
    assert ops.routine_ops(DR) == {"RECON", "ESCORT_CONVOYS", "DECOY_BLINK", "GARRISON_UPKEEP"}
    no_garrison = dataclasses.replace(RULES, garrison_quota={})  # upkeep would take the 15 first
    w = new_world(1, no_garrison)
    for c in candidates(w):
        if c.op.id == "RECON":
            _launch(w, RULES, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], c, [])
    assert len(ops.live_pairs([j.key for j in w.boards["ENEMY"].values()])) == 3
    window(w, "ALPHA", 15, no_garrison)  # only PROBE (15) is affordable among the rest
    assert non_routine(w) == {("PROBE", "fob-n-w")} or {p[0] for p in non_routine(w)} == {"PROBE"}


def test_a_live_patrol_or_pol_convoy_does_not_take_the_alpha_slot() -> None:
    w = new_world(1, dataclasses.replace(RULES, garrison_quota={}))
    probes = [c for c in candidates(w) if c.op.id == "PROBE"]
    assert probes
    live = frozenset({("POL_PATROL", "fob-n-e"), ("POL_CONVOY", "east-airbase")})

    def pick(routine: frozenset[str]) -> list[str]:
        chosen = ops.select(probes, DR, 80, DR.max_spawns_per_window, 40, live, 1, routine)
        return [c.op.id for c in chosen]

    assert pick(_routine(DR)) == ["PROBE"]
    assert pick(ops.routine_ops(DR)) == []  # counted as operations, they would take the slot


# --- jobs (step 8, TD-2) -------------------------------------------------------------------------


def test_an_offensive_posts_its_template_in_order_and_its_units_take_the_jobs() -> None:
    w = new_world()
    (cand,) = [c for c in candidates(w) if c.op.id == "OFFENSIVE" and c.target == "fob-n-w"]
    out: list[Event] = []
    _launch(w, RULES, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], cand, out)
    jobs = list(w.boards["ENEMY"].values())
    assert [(j.kind, j.node, j.slots) for j in jobs] == [
        ("STAGE", "fob-n-e", 2), ("STRIKE", "fob-n-w", 2), ("CAPTURE", "fob-n-w", 2),
    ]  # fmt: skip
    assert [j.depends_on for j in jobs] == [None, jobs[0].id, jobs[1].id]
    assert [len(j.claims) for j in jobs] == [2, 2, 2]
    units = enemy_units(w)
    assert [u.kind for u in units] == [
        ARMOR,
        ARMOR,
        "ENEMY_STRIKE_FIGHTER",
        "ENEMY_STRIKE_FIGHTER",
        ARMOR,
        ARMOR,
    ]
    assert [u.job_id for u in units] == [j.id for j in jobs for _ in range(2)]


def test_an_offensive_stages_strikes_and_captures_on_strait_1() -> None:
    # the units cross the neutral bridgehead and flip it: the night cap (no viewers) would hold
    # the base's flip back for 6 game hours, so this run has none (the cap has its own tests)
    w = new_world(1, with_director(night_cap_ticks=1))
    clear_coalition_defenses(w)
    w.defense_hp["fob-n-w"] = 10  # two jets with a few rounds each cannot break a full base
    (cand,) = [c for c in candidates(w) if c.op.id == "OFFENSIVE" and c.target == "fob-n-w"]
    out: list[Event] = []
    _launch(w, RULES, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], cand, out)
    done: list[str] = []
    for _ in range(40_000):
        for e in step(w, []):
            if e.kind in ("JobDone", "JobFailed", "JobExpired"):
                done.append(f"{e.kind}:{e.job_id}")
        if w.owner["fob-n-w"] == "ENEMY" and "JobDone:3" in done:
            break
    assert w.owner["fob-n-w"] == "ENEMY", done
    assert {"JobDone:1", "JobDone:2", "JobDone:3"} <= set(done)  # staged, struck, captured
    assert w.defense_hp["fob-n-w"] == 0 or w.owner["fob-n-w"] == "ENEMY"


def test_each_template_posts_what_q_sim_81_lists() -> None:
    shape = {op.id: [(j.kind, j.slots, j.unit_kinds) for j in op.jobs] for op in DR.operations}
    assert shape["PROBE"] == [("STRIKE", 1, ("ENEMY_STRIKE_FIGHTER",))]
    assert shape["RECON"] == [("SCOUT", 1, ("ENEMY_RECON_UAV",))]
    assert shape["ESCORT_CONVOYS"] == [("ESCORT_CONVOY", 1, ("ENEMY_FIGHTER",))]
    assert shape["REINFORCE_IADS"] == [("RESUPPLY", 1, ("ENEMY_CONVOY",))]
    assert shape["RETAKE"] == [
        ("STRIKE", 1, ("ENEMY_STRIKE_FIGHTER",)), ("CAPTURE", 3, (ARMOR,))
    ]  # fmt: skip
    assert shape["DECOY_BLINK"] == []


def test_golden_convoy_raids_make_escorts_appear_in_the_next_window_and_drop_away() -> None:
    w = new_world()
    convoy = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    convoy.path = ["fob-n-e"]
    pilot = unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "west-airbase")
    s = w.director["ENEMY"]
    s.tier = "ALPHA"
    view = side_view(w, "ENEMY")
    out: list[Event] = []
    decide(s, view, RULES, w.stock)  # a quiet window: escorts are routine, but no INTEL line
    launch(w, "ENEMY", view, RULES, out)
    assert not [a for a in out if isinstance(a, ThreatAdaptation)]
    live = {j.id for j in w.boards["ENEMY"].values()}
    for j in list(w.boards["ENEMY"].values()):
        del w.boards["ENEMY"][j.id]  # whatever the quiet window started is done
    for e in enemy_units(w):
        if e.id != convoy.id:
            w.remove(e.id)
    assert live
    for _ in range(3):
        suffered_hit(w, pilot, convoy, "HEALTHY")  # three raids
    out = []
    decide(s, view, RULES, w.stock)
    s.tier = "ALPHA"
    launch(w, "ENEMY", view, RULES, out)
    escorts = [j for j in w.boards["ENEMY"].values() if j.kind == "ESCORT_CONVOY"]
    assert [j.entity for j in escorts] == [convoy.id]
    up = [(a.category, a.direction, a.sector_id) for a in out if isinstance(a, ThreatAdaptation)]
    assert up == [("CONVOY_ESCORT", "UP", "centre")]
    (fighter,) = [u for u in enemy_units(w) if u.kind == "ENEMY_FIGHTER"]
    assert fighter.follow_id == convoy.id  # it escorts at once
    out = []  # the counter decays: the INTEL line says the escorts are dropped
    for _ in range(120):
        decide(s, view, RULES, w.stock)
        launch(w, "ENEMY", view, RULES, out)
    down = [(a.direction, a.category) for a in out if isinstance(a, ThreatAdaptation)]
    assert down == [("DOWN", "CONVOY_ESCORT")]
    assert TypeAdapter(Event).validate_python(
        next(a for a in out if isinstance(a, ThreatAdaptation)).model_dump(by_alias=True)
    )


def test_reinforce_iads_sends_a_convoy_to_the_base_with_the_damaged_site() -> None:
    w = new_world()
    (site,) = [e for e in w.entities() if e.base_id == "fob-n-e" and e.kind == "AIR_DEFENSE_SITE"]
    site.hp -= 1
    w.director["ENEMY"].radar_strikes = CP_SCALE
    ranked = candidates(w)
    assert ids(ranked, "REINFORCE_IADS") == ["fob-n-e"]
    events = window(w, "ALPHA", 15)
    (job,) = [
        j for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY" and j.key.startswith("op:")
    ]
    assert job.node == "fob-n-e"
    (truck,) = [u for u in enemy_units(w) if u.kind == "ENEMY_CONVOY"]
    assert truck.job_id == job.id
    assert [a.category for a in events if isinstance(a, ThreatAdaptation)] == ["IADS_REINFORCED"]


def skip(w: World, ticks: int) -> None:
    """Move the clock on without stepping (the world is only set up by hand)."""
    w.campaign.tick += ticks
    w.campaign.running_ticks += ticks


def test_decoy_blink_darkens_one_radar_a_window_for_dark_s_then_cools_down() -> None:
    w = new_world()
    radars = {e.base_id: e for e in w.entities() if e.kind == "RADAR_SITE" and e.side == "ENEMY"}
    east, hq = radars["east-airbase"], radars["static-hq"]
    s = w.director["ENEMY"]
    events = window(w, "PATTERN_OF_LIFE", 0)
    assert [e for e in events if e.kind in ("JobCreated", "UnitSpawned")] == []
    dark = [r for r in (east, hq) if r.emitting is False]
    assert len(dark) == 1  # at most one radar blinks per window
    first = dark[0].base_id
    window(w, "PATTERN_OF_LIFE", 0)
    assert east.emitting is False and hq.emitting is False  # the other one blinks next
    window(w, "PATTERN_OF_LIFE", 0)
    assert set(s.dark) == {"east-airbase", "static-hq"}  # none is left to blink
    skip(w, DR.dark_ticks)  # dark_s is over: both emit again
    window(w, "PATTERN_OF_LIFE", 0)
    assert east.emitting is True and hq.emitting is True and s.dark == {}
    assert s.blink_ready[first] > w.campaign.running_ticks  # cooling down: no blink yet
    skip(w, s.blink_ready[first] - 1 - w.campaign.running_ticks)
    window(w, "PATTERN_OF_LIFE", 0)
    assert s.dark  # the cooldown is over: a radar blinks again (the noise picks which)
    skip(w, 1)  # the hand-run window stamped the tick it ran at: the clock moves past it
    again = load(save(w))
    assert (
        again.director["ENEMY"].dark == s.dark
        and again.director["ENEMY"].blink_ready == s.blink_ready
    )


def test_a_disabled_radar_is_no_blink_candidate() -> None:
    w = new_world()
    for e in w.entities():
        if e.kind == "RADAR_SITE" and e.side == "ENEMY":
            e.damage_state = "DISABLED"
    window(w, "PATTERN_OF_LIFE", 0)
    assert w.director["ENEMY"].dark == {}


def test_pattern_of_life_affords_an_escort_at_cost_10() -> None:
    w = new_world()
    convoy = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    convoy.path = ["fob-n-e"]
    w.director["ENEMY"].convoy_attacks = 3 * CP_SCALE
    window(w, "PATTERN_OF_LIFE", DR.budget["PATTERN_OF_LIFE"])
    assert [j.entity for j in w.boards["ENEMY"].values() if j.kind == "ESCORT_CONVOY"] == [
        convoy.id
    ]


def test_a_dependent_job_waits_with_its_lease_held_and_opens_when_the_one_before_is_done() -> None:
    w = new_world()
    clear_coalition_defenses(w)
    window(w, "ALPHA", 60)
    stage, strike, capture = list(w.boards["ENEMY"].values())
    lease = RULES.tasking.claim_lease_ticks  # type: ignore[union-attr]
    for _ in range(EVERY):  # the first board pass: both armor are at the staging base
        step(w, [])
    assert stage.id not in w.boards["ENEMY"] and strike.depends_on is None
    waiting = [w.get(i) for i in capture.claims]
    for _ in range(3 * lease):  # the strike is under way; the capture armor wait, unreleased
        step(w, [])
    assert capture.id in w.boards["ENEMY"] and capture.depends_on == strike.id
    assert set(capture.claims) == {e.id for e in waiting} and all(not e.path for e in waiting)
    assert all(w.get(i).path or w.get(i).state == "ON_STATION" for i in strike.claims)


def test_td2_every_job_on_the_static_board_references_only_what_its_view_holds() -> None:
    w = new_world()
    convoy = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    convoy.path = ["fob-n-e"]
    w.director["ENEMY"].convoy_attacks = 2 * CP_SCALE
    for tier in ("ALPHA", "BRAVO", "PATTERN_OF_LIFE"):
        window(w, tier, 80)
        for _ in range(20):
            step(w, [])
    view = side_view(w, "ENEMY")
    assert w.boards["ENEMY"]
    for job in w.boards["ENEMY"].values():
        assert job.node is None or job.node in view.nodes
        assert job.blob is None or job.blob in {b.id for b in view.blobs}
        e = w.find(job.entity) if job.entity is not None else None
        assert job.entity is None or (e is not None and e.side == "ENEMY")  # its own unit
    for u in enemy_units(w):
        assert u.side == "ENEMY" and u.owner_kind == "ENEMY_DIRECTOR"


# --- time, snapshot, determinism -----------------------------------------------------------------


def test_a_pause_freezes_every_director_field_and_posts_nothing() -> None:
    w = new_world()
    w.director["ENEMY"].convoy_attacks = CP_SCALE
    for _ in range(DR.window_ticks - 5):
        step(w, [])
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    before = (state_hash(w), dataclasses.asdict(w.director["ENEMY"]))
    events: list[Event] = []
    for _ in range(3 * DR.window_ticks):
        events += step(w, [])
    assert [e for e in events if e.kind in ("JobCreated", "UnitSpawned", "SupplyConsumed")] == []
    assert dataclasses.asdict(w.director["ENEMY"]) == before[1]


def run_clock(w: World, ticks: int) -> list[Event]:
    events: list[Event] = []
    for _ in range(ticks):
        events += step(w, [])
    return events


def busy_world() -> World:
    w = new_world(5)
    s = w.director["ENEMY"]
    s.tier, s.prov_level, s.dwell = "ALPHA", 1, DR.min_dwell_ticks
    s.provocation = 20 * CP_SCALE
    s.convoy_attacks, s.node_losses = 2 * CP_SCALE, {"north": CP_SCALE}
    convoy = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    convoy.path = ["fob-n-e"]
    return w


def test_a_restored_world_runs_the_same_events_as_the_live_one_and_format_20_is_refused() -> None:
    import msgpack

    w = busy_world()
    run_clock(w, 2 * DR.window_ticks + 7)
    assert w.boards["ENEMY"] and w.director["ENEMY"].adapted
    again = load(save(w))
    again.rules = RULES
    assert state_hash(again) == state_hash(w)
    live, restored = run_clock(w, 3 * DR.window_ticks), run_clock(again, 3 * DR.window_ticks)
    assert [e.model_dump(by_alias=True) for e in live] == [
        e.model_dump(by_alias=True) for e in restored
    ]
    assert state_hash(again) == state_hash(w)
    raw = msgpack.unpackb(save(w), raw=False)
    raw["v"] = 20
    with pytest.raises(ValueError, match="unsupported snapshot format version 20"):
        load(msgpack.packb(raw, use_bin_type=True))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(convoy_attacks=-1),
        lambda d: d.update(node_losses={"nowhere": 1}),
        lambda d: d.update(lost={"fob-n-e": 10**9}),
        lambda d: d.update(adapted={"CONVOY_ESCORT": "nowhere"}),
        lambda d: d.update(dark={"east-airbase": 10**9}, blink_ready={"east-airbase": 10**9}),
        lambda d: d.update(blink_ready={"east-airbase": 10**9}),
        lambda d: d.update(dark={"east-airbase": 5}),  # dark without a cooldown
        lambda d: d.update(idle={"999999": 1}),
        lambda d: d.update(idle={"12": 10**9}),
    ],
)
def test_a_corrupt_threat_memory_is_refused(mutate: Callable[[dict[str, object]], object]) -> None:
    import msgpack

    from nexus.core.provocation import validate

    w = busy_world()
    raw = msgpack.unpackb(save(w), raw=False)
    mutate(raw["director"]["ENEMY"])
    with pytest.raises(ValueError):
        restored = load(msgpack.packb(raw, use_bin_type=True))
        validate(restored, RULES)


def test_a_window_with_many_candidates_at_a_thousand_entities_is_fast() -> None:
    w = new_world()
    clear_coalition_defenses(w)
    for i in range(1000):
        side = "COALITION" if i % 2 else "ENEMY"
        kind: UnitKind = "STRIKE_FIGHTER" if side == "COALITION" else "ENEMY_CONVOY"
        owner = "COMMANDER" if side == "COALITION" else "ENEMY_DIRECTOR"
        e = unit(w, kind, side, owner, "west-airbase" if side == "COALITION" else "east-airbase")
        if side == "ENEMY":
            e.path = ["fob-n-e"]
    view = side_view(w, "ENEMY")
    s = w.director["ENEMY"]
    s.tier, s.budget = "BRAVO", 80
    start = time.perf_counter()
    for _ in range(5):
        launch(w, "ENEMY", view, RULES, [])
        s.budget = 80
    per_window = (time.perf_counter() - start) / 5
    assert per_window < 0.5, per_window


# --- idle units, STAGE, CAPTURE restarts (Q-SIM-84) ---------------------------------------------


def run_to_tick(w: World, ticks: int) -> list[Event]:
    events: list[Event] = []
    for _ in range(ticks):
        events += step(w, [])
    return events


def test_an_operation_fills_its_slots_from_idle_units_and_pays_only_for_new_ones() -> None:
    w = new_world()
    spare = [
        unit(w, "ENEMY_RECON_UAV", "ENEMY", "ENEMY_DIRECTOR", "east-airbase") for _ in range(2)
    ]
    before = sum(w.stock.values())
    events = window(w, "PATTERN_OF_LIFE", 4)  # RECON x2 (2 each) in the best two sectors
    assert [e.kind for e in events].count("UnitSpawned") == 0
    assert {u.job_id is not None for u in spare} == {True}
    assert before - sum(w.stock.values()) == 0  # nothing was bought


def test_a_director_unit_with_no_job_is_retired_after_idle_retire_s() -> None:
    w = new_world()
    idle = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    busy = unit(w, "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", "fob-n-e")
    busy.path = ["cross-n"]  # driving: not idle
    s = w.director["ENEMY"]
    window(w, "PATTERN_OF_LIFE", 0)

    def memory() -> tuple[object, ...]:
        return (
            s.convoy_attacks, s.radar_strikes, s.node_losses, s.recon_losses, s.pending,
            s.provocation,
        )  # fmt: skip

    assert s.idle == {str(idle.id): w.campaign.running_ticks + 1}
    skip(w, DR.idle_retire_ticks - 1)
    window(w, "PATTERN_OF_LIFE", 0)
    assert w.find(idle.id) is not None  # not yet
    skip(w, 1)
    before = memory()
    events = window(w, "PATTERN_OF_LIFE", 0)
    assert w.find(idle.id) is None and w.find(busy.id) is not None and s.idle == {}
    gone = [e for e in events if isinstance(e, UnitDespawned)]
    assert [(e.entity_id, e.reason) for e in gone] == [(idle.id, "RETIRED")]
    assert not [e for e in events if e.kind == "UnitDestroyed"]  # a retirement is no loss
    assert memory() == before  # threat memory and provocation are untouched


def test_an_idle_director_carrier_with_cargo_is_not_retired() -> None:
    w = new_world()
    loaded = unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq")
    loaded.cargo = 12
    window(w, "PATTERN_OF_LIFE", 0)
    skip(w, DR.idle_retire_ticks + 1)
    events = window(w, "PATTERN_OF_LIFE", 0)
    assert w.find(loaded.id) is not None and loaded.cargo == 12  # stock + cargo stays exact
    assert not [e for e in events if isinstance(e, UnitDespawned)]


@pytest.mark.parametrize(
    ("tier", "provocation", "cp"), [("BRAVO", 60, 100), ("ALPHA", 15, 0)], ids=["bravo", "alpha"]
)
def test_forced_pressure_keeps_launching_under_small_caps_because_units_are_reused_or_retired(
    tier: ThreatTier, provocation: int, cp: int
) -> None:
    """Small live-unit caps (a config key) reach the cap in a few windows, so 60 windows show what
    300 do at the shipped ones (the QA run held 22 to 32 units): a leak would stop the launches."""
    small = {"PATTERN_OF_LIFE": 10, "ALPHA": 10, "BRAVO": 14}
    rules = with_director(max_live_units=small)
    w = new_world(1, rules)
    s = w.director["ENEMY"]
    launched, retired, idle_late = [], 0, 0
    for _ in range(60):
        s.pending += provocation * CP_SCALE
        s.cp = max(s.cp, cp * CP_SCALE)
        events = run_to_tick(w, DR.window_ticks)
        launched.append(len([e for e in events if e.kind == "JobCreated" and e.side == "ENEMY"]))
        retired += len([e for e in events if isinstance(e, UnitDespawned)])
        assert len(enemy_units(w)) <= small["BRAVO"] + DR.max_spawns_per_window
        if len(launched) > 40:
            idle_late = max(
                idle_late,
                len(
                    [
                        u
                        for u in enemy_units(w)
                        if u.job_id is None and u.home is None and u.state != "RTB"
                    ]
                ),
            )  # a garrison unit sits idle at its base by design (Q-SIM-85)
    assert s.tier == tier
    if tier == "BRAVO":
        assert retired > 0  # spent units are retired, not left to fill the cap
    else:
        assert idle_late <= 4  # ALPHA reuses them: a leak would pile up 5 to 8 idle
    assert sum(launched[40:]) > 0  # still launching in the last third: nothing is leaked
    assert all(
        w.campaign.running_ticks - since < DR.idle_retire_ticks + 2 * DR.window_ticks
        for since in s.idle.values()
    )  # no unit sits idle past its retirement


def test_stage_with_a_lost_unit_is_done_when_the_rest_arrive_and_fails_with_none() -> None:
    w = new_world()
    clear_coalition_defenses(w)
    w.defense_hp["fob-n-w"] = 10
    (cand,) = [c for c in candidates(w) if c.op.id == "OFFENSIVE" and c.target == "fob-n-w"]
    _launch(w, RULES, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], cand, [])
    stage, strike, _ = list(w.boards["ENEMY"].values())
    first = w.get(min(stage.claims))
    w.remove(first.id)  # one of the two stagers is lost on the way
    stage.claims.pop(first.id)
    stage.expires = 1  # ... and the expiry has passed
    out = run_to_tick(w, RULES.tasking.reeval_every_ticks)  # type: ignore[union-attr]
    assert any(isinstance(e, JobDone) and e.job_id == stage.id for e in out)
    assert strike.depends_on is None  # the strike opens
    w2 = new_world()
    clear_coalition_defenses(w2)
    (cand2,) = [c for c in candidates(w2) if c.op.id == "OFFENSIVE" and c.target == "fob-n-w"]
    _launch(w2, RULES, "ENEMY", side_view(w2, "ENEMY"), w2.director["ENEMY"], cand2, [])
    stage2, strike2, capture2 = list(w2.boards["ENEMY"].values())
    for i in list(stage2.claims):
        w2.remove(i)
        stage2.claims.pop(i)
    out2 = run_to_tick(w2, RULES.tasking.reeval_every_ticks)  # type: ignore[union-attr]
    kinds2 = {(e.kind, e.job_id) for e in out2 if isinstance(e, JobDone | JobFailed | JobExpired)}
    assert ("JobFailed", stage2.id) in kinds2 and ("JobFailed", strike2.id) in kinds2
    assert ("JobFailed", capture2.id) in kinds2  # the chain fails with it


def test_a_capture_run_gets_at_most_capture_max_restarts_fresh_expiries() -> None:
    w = new_world()
    tr = RULES.tasking
    assert tr is not None and tr.capture_max_restarts == 3
    clear_coalition_defenses(w)
    w.owner["fob-n-e"] = "COALITION"
    w.director["ENEMY"].lost["fob-n-e"] = 1
    (cand,) = [c for c in candidates(w) if c.op.id == "RETAKE"]
    _launch(w, RULES, "ENEMY", side_view(w, "ENEMY"), w.director["ENEMY"], cand, [])
    strike, capture = list(w.boards["ENEMY"].values())
    strike.depends_on = capture.depends_on = None  # skip the strike: only the capture clock matters
    for e in enemy_units(w):
        if e.kind == ARMOR:
            e.path = ["cross-n"]  # driving for good
            e.last_node = "east-airbase"
    seen = set()
    for _ in range(6):
        capture.expires = w.campaign.running_ticks + 1
        run_to_tick(w, tr.reeval_every_ticks)
        seen.add(capture.restarts)
        if capture.id not in w.boards["ENEMY"]:
            break
    assert max(seen) == 3 and capture.id not in w.boards["ENEMY"]  # then it expired normally


def test_a_hit_on_a_disabled_radar_is_not_remembered() -> None:
    w = new_world()
    pilot = unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "west-airbase")
    (radar,) = [e for e in w.entities() if e.base_id == "east-airbase" and e.kind == "RADAR_SITE"]
    suffered_hit(w, pilot, radar, "DISABLED")
    assert w.director["ENEMY"].radar_strikes == 0
    suffered_hit(w, pilot, radar, "HEALTHY")
    assert w.director["ENEMY"].radar_strikes == CP_SCALE


def with_director(**changes: Any) -> Rules:
    return dataclasses.replace(RULES, director=dataclasses.replace(DR, **changes))


def test_every_formula_coefficient_is_a_key() -> None:
    quiet = zero_noise(RULES)
    w = new_world()
    w.director["ENEMY"].convoy_attacks = 2 * CP_SCALE
    w.director["ENEMY"].lost["fob-n-e"] = 1
    w.owner["fob-n-e"] = "COALITION"
    base = scores(w, quiet)["RETAKE", "fob-n-e"]
    k2 = with_director(noise=Fraction(0), memory_factor=Fraction(2))
    w.director["ENEMY"].node_losses = {"north": CP_SCALE}
    one = scores(w, quiet)["RETAKE", "fob-n-e"]  # 1 + 1 x 1
    assert scores(w, k2)["RETAKE", "fob-n-e"] == one * Fraction(3, 2)  # 1 + 2 x 1 over 1 + 1 x 1
    assert base == one / 2
    wk = with_director(noise=Fraction(0), weakness_min=Fraction(2), weakness_max=Fraction(4))
    assert scores(new_world(), wk)["OFFENSIVE", "west-airbase"] == Fraction(3, 2) * 2
    w2 = new_world()
    st = with_director(noise=Fraction(0), stale_factor=Fraction(3))
    assert scores(w2, st)["RECON", "north"] == Fraction(1, 2) * 4  # 1 + 3 x 1


def test_frontline_blink_adaptation_reinforce_and_escort_keys() -> None:
    w = new_world()
    w.director["ENEMY"].tier = "ALPHA"
    two = with_director(frontline_hops=2)
    cands = ops.candidates(
        w.director["ENEMY"], side_view(w, "ENEMY"), two, _own(w, two, "ENEMY"), 1, frozenset()
    )
    assert ids(cands, "PROBE") == [
        "fob-n-w",
        "fob-s-w",
        "west-airbase",
    ]  # two hops reach the bridgehead
    two_blinks = with_director(blink_max=2)
    s = w.director["ENEMY"]
    s.tier, s.budget = "PATTERN_OF_LIFE", 0
    launch(w, "ENEMY", side_view(w, "ENEMY"), two_blinks, [])
    assert len(s.dark) == 2
    # reinforce: a lightly damaged site is no trigger above a share
    w3 = new_world()
    (site,) = [e for e in w3.entities() if e.base_id == "fob-n-e" and e.kind == "AIR_DEFENSE_SITE"]
    site.hp -= 1
    assert _own(w3, RULES, "ENEMY").damaged_ad == {"fob-n-e"}
    strict = with_director(reinforce_above=Fraction(1, 2))
    assert _own(w3, strict, "ENEMY").damaged_ad == frozenset()


def test_escort_min_convoys_and_the_up_threshold_are_keys() -> None:
    w = new_world()
    for _ in range(3):
        unit(w, "ENEMY_CONVOY", "ENEMY", "ENEMY_DIRECTOR", "static-hq").path = ["fob-n-e"]
    (cand,) = [c for c in candidates(w, "PATTERN_OF_LIFE") if c.op.id == "ESCORT_CONVOYS"]
    assert cand.units == 3
    kept = ops.select([cand], DR, 10, 2, 40, frozenset(), None)  # room for 2 units: 2 convoys
    assert [len(c.wheres[0]) for c in kept] == [2]
    strict = dataclasses.replace(DR, escort_min_convoys=3)
    assert ops.select([cand], strict, 10, 2, 40, frozenset(), None) == []
    s = w.director["ENEMY"]
    s.convoy_attacks = CP_SCALE  # one event: above 0, not above 1
    s.tier, s.budget = "PATTERN_OF_LIFE", 10
    up = with_director(up_above=CP_SCALE)
    assert not [e for e in launch_events(w, up) if isinstance(e, ThreatAdaptation)]


def launch_events(w: World, rules: Rules) -> list[Event]:
    out: list[Event] = []
    launch(w, "ENEMY", side_view(w, "ENEMY"), rules, out)
    return out


def test_own_node_value_is_a_key() -> None:
    w = new_world()
    (site,) = [e for e in w.entities() if e.base_id == "fob-n-e" and e.kind == "AIR_DEFENSE_SITE"]
    site.hp -= 1
    rich = with_director(noise=Fraction(0), own_node_value=Fraction(3))
    base = scores(w, zero_noise(RULES))["REINFORCE_IADS", "fob-n-e"]
    assert base == Fraction(7, 10)  # priority x own_node_value 1
    assert scores(w, rich)["REINFORCE_IADS", "fob-n-e"] == base * 3
