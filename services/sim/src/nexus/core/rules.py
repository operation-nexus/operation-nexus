"""Static per-campaign rules the kernel reads (SIM-CORE §4, SC-2; NX-121).

Read-only data built once from the loaded config: never world state, so it is not in snapshots
or `state_hash` (the campaign's `config_hash` covers it). It takes contract types only, so the
kernel stays free of `nexus.runtime`; the runtime loads the files and builds the road graph.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import cast

from nexus.contracts.gen.common.enums import (
    AltBand,
    DamageState,
    Domain,
    JobKind,
    NodeKind,
    NodeOwner,
    Role,
    Side,
    UnitKind,
)
from nexus.contracts.gen.config.balance import Air, Capture, Fow, Logistics, Sim, Slots, Tasking
from nexus.contracts.gen.config.balance import Campaign as CampaignBalance
from nexus.contracts.gen.config.balance import Combat as CombatBalance
from nexus.contracts.gen.config.roles import Roles
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.contracts.gen.config.weapons import Weapon
from nexus.core.roads import RoadGraph

CAPTURE_FULL = 100_000_000  # a full capture bar, in millionths of a percent (NX-125)

_LANDING_KINDS = ("AIRBASE", "SANCTUARY")  # aircraft land only here (Q-SIM-38, NX-368)
_SIDES: tuple[Side, ...] = ("COALITION", "ENEMY")
# Recon units paint targets (CONFIG-AND-CONTENT §7.3, FOG-OF-WAR Q-FOW-6). shortcut: named here
# until the unit catalog lists capabilities; then it becomes a catalog field.
_PAINTERS: tuple[UnitKind, ...] = ("RECON_UAV", "ENEMY_RECON_UAV")
# Kinds that haul cargo (GAMEPLAY §5). shortcut: named here until the unit catalog gets its `cargo`
# field (CONFIG-AND-CONTENT §7.3); the amount is the one global `logistics.truck_cargo`.
_CARRIERS: tuple[UnitKind, ...] = ("LOGI_TRUCK", "ENEMY_CONVOY")
_STRATEGIC_KINDS = ("AIRBASE", "FOB", "PORT")  # count toward the hold fractions (Q-GP-21)
_DOMAINS: tuple[Domain, ...] = ("AIR", "GROUND", "SEA", "STATIC")
_MILLI = 1000  # a truck's unload progress is counted in thousandths of a stock unit
# A facility variant carries only these of its kind's catalog weapons (SHORT_RANGE: the gun, no
# SAM); any other variant, and none, carries them all. shortcut: named here until the unit catalog
# lists variants (CONFIG-AND-CONTENT §7a), like the emitter rule in `campaign_config`.
_VARIANT_WEAPONS: Mapping[tuple[UnitKind, str], tuple[str, ...]] = {
    ("AIR_DEFENSE_SITE", "SHORT_RANGE"): ("AAA_GUN",)
}


@dataclass(frozen=True, slots=True)
class Supply:
    """Logistics rules (NX-123, GAMEPLAY §5). The default is a theater with no stock nodes and no
    carriers, for hand-built rules in tests."""

    rear: Mapping[Side, str] = field(default_factory=dict)  # each side's SANCTUARY: infinite source
    # Node -> its starting owner; `World.owner` starts as a copy and is the live owner (NX-125).
    start_owner: Mapping[str, NodeOwner] = field(default_factory=dict)
    max_stock: Mapping[str, int] = field(default_factory=dict)  # finite-stock nodes only
    starve_floor: Mapping[str, int] = field(default_factory=dict)  # ceil(starve_threshold x max)
    carriers: frozenset[UnitKind] = frozenset()
    truck_cargo: int = 0  # logistics.truck_cargo
    unload_milli: int = 0  # logistics.unload_rate x world_dt, in thousandths per tick
    rearm_milli: int = 0  # logistics.rearm_rate x world_dt, in thousandths per tick
    loadout_cost: Mapping[UnitKind, int] = field(default_factory=dict)  # a kind with none costs 0
    forward_deploy_min_surplus: int = 0
    starved_fuel_frac: float = 1.0  # a starved base refuels up to this share of fuel_s (Q-SIM-53)
    # logistics.repair_rate x world_dt in thousandths of an hp per tick, by base kind (Q-SIM-68); a
    # kind missing here (a BRIDGE) repairs nothing. SANCTUARY is free (infinite stock).
    repair_milli: Mapping[NodeKind, int] = field(default_factory=dict)
    facility_hp_per_stock: int = 10  # logistics.facility_repair_hp_per_stock (GAMEPLAY §5b)
    facility_rearm_cost: int = 10  # logistics.facility_rearm_cost: a full reload of a facility
    # Domain -> the theater `spawns` nodes that take that domain (GP-7, Q-SIM-54).
    spawns: Mapping[Domain, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CaptureRules:
    """Capture rules (NX-125, GAMEPLAY §8): the balance `capture` keys, plus the decay as whole
    millionths of a percent per tick so a bar's progress stays an exact integer."""

    radius_m: float
    time_s: float
    exponent: float
    quiet_floor: float
    quiet_ref: int
    min_time_s: float
    logi_weight: float
    garrison_mult: float
    empty_base_mult: float
    decay_micro: int  # capture.decay_per_s x world_dt, as millionths of a percent of the bar


@dataclass(frozen=True, slots=True)
class DefenseRules:
    """Node defense HP (NX-124 part 3, GAMEPLAY §8, Q-SIM-71): whole hp, so a rebuild or drain is
    exact. `max_hp` lists the nodes that have defenses (every kind but BRIDGE, NX-373)."""

    max_hp: Mapping[str, int]  # node id -> capture.defense_hp.<kind>
    repair_per_stock: int  # logistics.defense_repair_hp_per_stock
    drain_per_min: int  # logistics.starve_hp_drain_per_min, hp per game minute
    ticks_per_min: int  # running ticks in a game minute: the drain carry's modulus
    # capture.sanctuary_repair_hp_per_s x world_dt in thousandths of an hp per tick per parked
    # logistics unit (Q-SIM-71); the sanctuary's `defense_drain` carries its thousandths.
    sanctuary_repair_milli: int
    forward_airbase: str  # the coalition AIRBASE the idle floor protects (Q-TH-2)


@dataclass(frozen=True, slots=True)
class CampaignRules:
    """Campaign rules (NX-126, GAMEPLAY §9): clock limits in whole running game ticks, the exact
    (Fraction) weights and fractions so a threshold or a tie is exact, and the theater's
    strategic nodes and objective candidates."""

    time_limit_ticks: int  # campaign.time_limit_h
    victory_hold_ticks: int  # campaign.victory_hold_min
    defeat_hold_ticks: int  # campaign.defeat.hold_min (Q-TH-7)
    objective_period_ticks: int  # campaign.objective_period_min
    objectives_on: bool  # campaign.objective_mode is timed
    victory_node_frac: Fraction
    average_weight: Fraction  # campaign.score.average_weight (Q-SIM-64)
    final_weight: Fraction  # campaign.score.final_weight
    objective_points: Fraction
    nodes_weight: Fraction  # campaign.momentum.nodes_weight (Q-SIM-60)
    supply_weight: Fraction
    strategic: tuple[str, ...]  # AIRBASE, FOB and PORT nodes, by id (Q-GP-17, Q-GP-21)
    enemy_hq: str  # its capture by the coalition wins
    # Objective candidates by id (never SANCTUARY, BRIDGE or the enemy HQ; Q-SM-11) -> the ids of
    # their road neighbours that can have an owner (not BRIDGE): a candidate with a neighbour of
    # another owner is on the frontline.
    candidates: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class TaskingRules:
    """Tasking Board rules (NX-374, GAMEPLAY §1b, Q-SIM-73): durations in running ticks, the
    priorities and the aging rate exact (Fractions) so a ranking and a tie are exact, and the
    urgency cap in thousandths. `slots` holds the fixed slot counts; a resupply job is sized from
    its missing stock (`resupply_stock_per_slot`, at most `resupply_slots_max`)."""

    reeval_every_ticks: int
    claim_lease_ticks: int
    expire_ticks: int  # an unclaimed job expires this long after it was posted
    ticks_per_min: int  # running ticks in a game minute: the aging rate's divisor
    priority: Mapping[JobKind, Fraction]
    urgency_max_milli: int
    aging_per_min: Fraction
    slots: Mapping[JobKind, int]
    resupply_stock_per_slot: int
    resupply_slots_max: int
    defend_radius_m: float
    counterattack_window_ticks: int  # how long after a loss the garrison may counterattack
    scout_cooldown_ticks: int  # how long a scouted cell is not posted again
    station_m: Mapping[
        str, float
    ]  # follow_station_m: escort, column, overwatch, wingman (Q-SIM-76)
    threat_memory_ticks: int  # how long an attacker of a group stays a group threat
    leash_m: float  # the farthest an escort leaves station to engage


@dataclass(frozen=True, slots=True)
class WeaponRules:
    """One weapon profile (COMBAT CB-1..CB-5): `reload_ticks` is `reload_s` in whole world ticks,
    rounded up (CFG-9); `speed_mps` None is a gun, which lands on the fire tick."""

    id: str
    targets: frozenset[str]
    bands: frozenset[AltBand]
    range_m: float
    speed_mps: float | None
    base_pk: float
    damage: int
    reload_ticks: int
    ammo: int


@dataclass(frozen=True, slots=True)
class UnitRules:
    """A kind's combat stats (COMBAT CB-5, CB-6, CB-9). `armor` is an exact decimal so a hit's
    damage floors exactly. `cuts` are the whole hp below which a unit is DISABLED, MISSION_KILL and
    DAMAGED: for whole hp, hp < fraction x max_hp is hp < ceil(fraction x max_hp)."""

    hp: int
    armor: Fraction
    evasion: float
    threat: int
    cuts: tuple[int, int, int]
    alt_band: AltBand | None  # AIR: the default band
    crew: int  # crew count, 0 for facilities and unmanned kinds (CB-8)
    crew_survival: float  # chance the crew is DOWNED, not LOST; 0.0 when `crew` is 0 (Q-SIM-68)

    def state(self, hp: int) -> DamageState:
        disabled, mission_kill, damaged = self.cuts
        if hp < disabled:
            return "DISABLED"
        return "MISSION_KILL" if hp < mission_kill else "DAMAGED" if hp < damaged else "HEALTHY"

    @property
    def floor(self) -> int:
        """The hp a facility never drops below: the highest hp still DISABLED, at least 1 (CB-9)."""
        return max(1, self.cuts[0] - 1)


@dataclass(frozen=True, slots=True)
class CombatRules:
    """Combat rules (NX-124, COMBAT): per-kind stats, each (kind, variant)'s weapons in catalog
    order, and the balance `combat` keys. Absent from `Rules` (hand-built tests) = combat off."""

    units: Mapping[UnitKind, UnitRules]
    weapons: Mapping[str, WeaponRules]
    loadouts: Mapping[tuple[UnitKind, str | None], tuple[WeaponRules, ...]]
    pk_cap: float
    track_mult: float
    painted_mult: float
    full_pk_frac: float
    min_mult: float
    masked_mult: float
    disabled_timeout_ticks: int  # combat.disabled_timeout_s as game ticks, rounded up (CB-7)
    assist_window_ticks: int  # combat.assist_window_s as game ticks, rounded up (CB-5a)
    crew_marker_ticks: int  # combat.crew_marker_min as game ticks, rounded up (CB-8)
    damaged_speed_mult: float  # x top speed at Damaged or worse (CB-6, Q-SIM-65)
    damaged_sensor_mult: float  # x sensor radius at Damaged or worse

    def loadout(self, kind: UnitKind, variant: str | None) -> tuple[WeaponRules, ...]:
        return self.loadouts.get((kind, variant), self.loadouts[(kind, None)])


@dataclass(frozen=True, slots=True)
class Rules:
    world_dt: float  # world seconds per tick: TICK_DT x sim.time_scale (SC-2)
    speed_mps: Mapping[UnitKind, float]  # m/s of world time; a top speed (Q-SIM-38)
    domain: Mapping[UnitKind, Domain]
    roads: RoadGraph
    role_kind: Mapping[Role, UnitKind]  # content/roles.yaml; a missing role is not playable yet
    sanctuary: str  # coalition SANCTUARY: non-truck JOINs spawn here until forward deploy (GP-7)
    max_live_per_commander: int  # slots.max_live_per_commander (GP-1)
    respawn_delay_ticks: int  # slots.respawn_delay_s as game ticks, rounded up (GP-2, SC-12)
    max_viewer_units: int  # slots.max_viewer_units: live COMMANDER units before JOINs queue (GP-3)
    reserve_queue_max: int  # slots.reserve_queue_max (GP-3)
    min_speed_mps: Mapping[UnitKind, float]  # AIR kinds: stall speed, m/s world (NX-368)
    fuel_s: Mapping[UnitKind, float]  # AIR kinds: endurance, world s (NX-368)
    bingo_reserve_frac: float  # air.bingo_reserve_frac (NX-368)
    # The AIRBASE and SANCTUARY nodes, by id: aircraft land only at those their side owns now
    # (`World.landing_bases`, NX-125).
    landing_nodes: tuple[str, ...]
    bounds_m: tuple[float, float]  # theater width, height (m)
    orbit_period_s: float  # air.orbit_period_s: world s per lap of an idle orbit (NX-368)
    sensor_radius_m: Mapping[UnitKind, float]  # sensor.radius_m, 0 = none (FOG-OF-WAR Tier 2)
    stealth: Mapping[UnitKind, float]  # x every enemy sensor's radius against this kind
    track_every_ticks: int  # fow.track_every_ticks (FOW-5)
    track_fade_ticks: int  # fow.track_fade_s as world ticks, rounded up (FOW-6a, FOW-9, SC-12)
    passive_range_m: Mapping[UnitKind, float]  # sensor.passive_range_m, 0 = none (FOW-13)
    # Q-FOW-3: the theater's masking regions rasterized to square cells of `mask_cell_m`:
    # (floor(x / mask_cell_m), floor(y / mask_cell_m)) -> the ids of the regions covering it.
    mask_cell_m: float
    masking: Mapping[tuple[int, int], frozenset[str]]
    paint_range_m: float  # fow.paint_range_m (Q-FOW-6)
    painters: frozenset[UnitKind]  # kinds that paint (recon units)
    sigint_range_mult: float  # fow.sigint_range_mult (Tier 1, Q-FOW-7)
    sigint_refresh_ticks: int  # fow.sigint_refresh_s as world ticks, rounded up (FOW-5, FOW-9)
    sigint_cell_m: float  # fow.sigint_cell_m (FOW-2); divides both theater bounds
    sigint_size_m_min: int  # fow.sigint_size_m_min: a blob of this many units reads M
    sigint_size_l_min: int  # fow.sigint_size_l_min: and of this many, L
    supply: Supply = field(default_factory=Supply)  # NX-123
    # NX-125. `node_kind` lists every theater node in id order; empty (hand-built rules) and a
    # `capture` of None leave capture off. `armed`: the kinds whose catalog has weapons.
    node_kind: Mapping[str, NodeKind] = field(default_factory=dict)
    armed: frozenset[UnitKind] = frozenset()
    capture: CaptureRules | None = None
    campaign: CampaignRules | None = None  # NX-126; None leaves the campaign layer off
    combat: CombatRules | None = None  # NX-124; None leaves combat off
    defense: DefenseRules | None = None  # NX-124 part 3; None: nodes have no defense HP
    tasking: TaskingRules | None = None  # NX-374; None leaves the Tasking Boards off

    def speed(self, kind: UnitKind, state: DamageState) -> float:
        """A unit's top speed now: x `damaged_speed_mult` at Damaged or worse, but an aircraft never
        below its stall speed `min_speed_mps` (CB-6, Q-SIM-38)."""
        top = self.speed_mps[kind]
        if self.combat is None or state == "HEALTHY":
            return top
        return max(top * self.combat.damaged_speed_mult, self.min_speed_mps.get(kind, 0.0))

    def sensor_radius(self, kind: UnitKind, state: DamageState) -> float:
        """A unit's sensor radius now: x `damaged_sensor_mult` at Damaged or worse (CB-6)."""
        radius = self.sensor_radius_m[kind]
        return (
            radius
            if self.combat is None or state == "HEALTHY"
            else radius * self.combat.damaged_sensor_mult
        )


def tasking_rules(
    cfg: Tasking,
    *,
    claim_lease_ticks: int,
    expire_ticks: int,
    ticks_per_min: int,
    counterattack_window_ticks: int,
    scout_cooldown_ticks: int,
    threat_memory_ticks: int,
) -> TaskingRules:
    """The tick counts are `cfg`'s game-time keys already converted by the config loader."""
    return TaskingRules(
        reeval_every_ticks=cfg.reeval_every_ticks,
        claim_lease_ticks=claim_lease_ticks,
        expire_ticks=expire_ticks,
        ticks_per_min=ticks_per_min,
        priority={cast(JobKind, k.upper()): Fraction(repr(v)) for k, v in cfg.priority},
        urgency_max_milli=round(Fraction(repr(cfg.urgency_max)) * 1000),
        aging_per_min=Fraction(repr(cfg.priority_aging_per_min)),
        slots={cast(JobKind, k.upper()): v for k, v in cfg.slots},
        resupply_stock_per_slot=cfg.resupply_stock_per_slot,
        resupply_slots_max=cfg.resupply_slots_max,
        defend_radius_m=cfg.defend_radius_m,
        counterattack_window_ticks=counterattack_window_ticks,
        scout_cooldown_ticks=scout_cooldown_ticks,
        station_m=cfg.follow_station_m.model_dump(),
        threat_memory_ticks=threat_memory_ticks,
        leash_m=cfg.escort_leash_m,
    )


def world_dt(sim: Sim) -> float:
    """`1 / tick_hz x time_scale` in exact decimals, then one rounding (6x at 10 Hz is 0.6)."""
    return float(Fraction(repr(sim.time_scale)) / sim.tick_hz)


def _role_kind(roles: Roles) -> Mapping[Role, UnitKind]:
    """Every role `content/roles.yaml` maps; NAVY joins in P3 (Q-GD-8)."""
    return {"STRIKE": roles.STRIKE, "RECON": roles.RECON, "LOGI": roles.LOGI}


def _capture(capture: Capture, dt: float) -> CaptureRules:
    decay_micro = round(capture.decay_per_s * dt * CAPTURE_FULL)
    if decay_micro < 1:
        raise ValueError("capture.decay_per_s x world_dt is below one millionth of a percent")
    return CaptureRules(
        capture.radius_m, capture.time_s, capture.multi_unit_exponent, capture.quiet_floor,
        capture.quiet_ref, capture.min_time_s, capture.logi_weight, capture.garrison_mult,
        capture.empty_base_mult, decay_micro,
    )  # fmt: skip


def _defense(
    theater: TheaterConfig, capture: Capture, logistics: Logistics, sim: Sim
) -> DefenseRules:
    repair_milli = round(capture.sanctuary_repair_hp_per_s * world_dt(sim) * _MILLI)
    if repair_milli < 1:
        raise ValueError("capture.sanctuary_repair_hp_per_s x world_dt is below 0.001 hp per tick")
    by_kind = capture.defense_hp.model_dump()
    return DefenseRules(
        max_hp={n.id: by_kind[n.kind] for n in sorted(theater.nodes, key=lambda n: n.id)
                if n.kind in by_kind},
        repair_per_stock=logistics.defense_repair_hp_per_stock,
        drain_per_min=logistics.starve_hp_drain_per_min,
        ticks_per_min=60 * sim.tick_hz,
        sanctuary_repair_milli=repair_milli,
        forward_airbase=theater.forward_airbase,
    )  # fmt: skip


def _supply(theater: TheaterConfig, logistics: Logistics, dt: float) -> Supply:
    """Raises ValueError when a start_stock exceeds its kind's maximum (Q-SIM-49)."""
    max_by_kind = logistics.node_max_stock.model_dump()
    stocked = [n for n in theater.nodes if n.kind != "SANCTUARY"]
    over = [n.id for n in stocked if (n.start_stock or 0) > max_by_kind[n.kind]]
    if over:
        raise ValueError(f"start_stock above logistics.node_max_stock: {over}")
    max_stock = {n.id: max_by_kind[n.kind] for n in stocked}
    sanctuaries = {n.start_owner: n.id for n in theater.nodes if n.kind == "SANCTUARY"}
    unload_milli = round(logistics.unload_rate * dt * _MILLI)
    rearm_milli = round(logistics.rearm_rate * dt * _MILLI)
    if unload_milli < 1 or rearm_milli < 1:
        raise ValueError("logistics unload_rate or rearm_rate x world_dt is below 0.001 per tick")
    rates = cast(Mapping[NodeKind, float], logistics.repair_rate.model_dump())
    repair_milli = {k: round(rate * dt * _MILLI) for k, rate in rates.items()}
    if any(rate > 0 and repair_milli[k] < 1 for k, rate in rates.items()):
        raise ValueError("logistics.repair_rate x world_dt is below 0.001 hp per tick")
    return Supply(
        rear={side: sanctuaries[side] for side in _SIDES},
        start_owner={n.id: n.start_owner for n in theater.nodes},
        max_stock=max_stock,
        starve_floor={k: math.ceil(logistics.starve_threshold * v) for k, v in max_stock.items()},
        carriers=frozenset(_CARRIERS),
        truck_cargo=logistics.truck_cargo,
        unload_milli=unload_milli,
        rearm_milli=rearm_milli,
        loadout_cost=cast(Mapping[UnitKind, int], logistics.loadout_cost.model_dump()),
        forward_deploy_min_surplus=logistics.forward_deploy_min_surplus,
        starved_fuel_frac=logistics.starved_loadout.fuel_frac,
        repair_milli=repair_milli,
        facility_hp_per_stock=logistics.facility_repair_hp_per_stock,
        facility_rearm_cost=logistics.facility_rearm_cost,
        spawns={d: frozenset(s.node for s in theater.spawns if d in s.domains) for d in _DOMAINS},
    )


def campaign_rules(
    cfg: CampaignBalance,
    theater: TheaterConfig,
    roads: RoadGraph,
    *,
    time_limit_ticks: int,
    victory_hold_ticks: int,
    defeat_hold_ticks: int,
    objective_period_ticks: int,
) -> CampaignRules:
    """The tick counts are `cfg`'s game-time keys already converted by the config loader."""
    kind = {n.id: n.kind for n in theater.nodes}
    ownable = {n for n, k in kind.items() if k != "BRIDGE"}
    skip = {n for n, k in kind.items() if k in ("SANCTUARY", "BRIDGE")} | {theater.enemy_hq}
    return CampaignRules(
        time_limit_ticks=time_limit_ticks,
        victory_hold_ticks=victory_hold_ticks,
        defeat_hold_ticks=defeat_hold_ticks,
        objective_period_ticks=objective_period_ticks,
        objectives_on=cfg.objective_mode == "timed",
        victory_node_frac=Fraction(repr(cfg.victory_node_frac)),
        average_weight=Fraction(repr(cfg.score.average_weight)),
        final_weight=Fraction(repr(cfg.score.final_weight)),
        objective_points=Fraction(repr(cfg.score.objective_points)),
        nodes_weight=Fraction(repr(cfg.momentum.nodes_weight)),
        supply_weight=Fraction(repr(cfg.momentum.supply_weight)),
        strategic=tuple(sorted(n for n, k in kind.items() if k in _STRATEGIC_KINDS)),
        enemy_hq=theater.enemy_hq,
        candidates={
            n: tuple(m for m, _ in roads.neighbours(n) if m in ownable)
            for n in sorted(kind)
            if n not in skip
        },
    )


def combat_rules(
    cfg: CombatBalance,
    units: Iterable[UnitConfig],
    weapons: Iterable[Weapon],
    *,
    dt: float,
    disabled_timeout_ticks: int,
    assist_window_ticks: int,
    crew_marker_ticks: int,
) -> CombatRules:
    """`dt` is `world_dt`; `disabled_timeout_ticks` is `cfg.disabled_timeout_s` already converted
    by the config loader (game time); likewise `assist_window_ticks` for `cfg.assist_window_s` and
    `crew_marker_ticks` for `cfg.crew_marker_min`."""
    profile = {w.id: _weapon(w, dt) for w in weapons}
    units = tuple(units)
    ds = cfg.damage_state
    cuts = tuple(
        Fraction(repr(f)) for f in (ds.disabled_below, ds.mission_kill_below, ds.damaged_below)
    )

    survival = cfg.crew_survival.model_dump()

    def stats(u: UnitConfig) -> UnitRules:
        c = cast(tuple[int, int, int], tuple(math.ceil(f * u.hp) for f in cuts))
        if u.crew and u.kind not in survival:
            raise ValueError(f"combat.crew_survival has no chance for {u.kind} (crew {u.crew})")
        return UnitRules(
            u.hp, Fraction(repr(u.armor)), u.evasion, u.threat, c, u.default_alt_band, u.crew,
            survival.get(u.kind, 0.0) if u.crew else 0.0,
        )  # fmt: skip

    loadouts: dict[tuple[UnitKind, str | None], tuple[WeaponRules, ...]] = {}
    for u in units:
        loadouts[(u.kind, None)] = tuple(profile[w] for w in u.weapons)
        for (kind, variant), only in _VARIANT_WEAPONS.items():
            if kind == u.kind:
                loadouts[(kind, variant)] = tuple(profile[w] for w in u.weapons if w in only)
    return CombatRules(
        units={u.kind: stats(u) for u in units},
        weapons=profile,
        loadouts=loadouts,
        pk_cap=cfg.pk_cap,
        track_mult=cfg.track_quality.track,
        painted_mult=cfg.track_quality.painted,
        full_pk_frac=cfg.range.full_pk_frac,
        min_mult=cfg.range.min_mult,
        masked_mult=cfg.pk_mult.terrain_masked,
        disabled_timeout_ticks=disabled_timeout_ticks,
        assist_window_ticks=assist_window_ticks,
        crew_marker_ticks=crew_marker_ticks,
        damaged_speed_mult=ds.damaged_speed_mult,
        damaged_sensor_mult=ds.damaged_sensor_mult,
    )


def _weapon(w: Weapon, dt: float) -> WeaponRules:
    reload_ticks = math.ceil(Fraction(repr(w.reload_s)) / Fraction(repr(dt)))  # exact decimals
    return WeaponRules(
        w.id, frozenset(w.targets), frozenset(w.bands), w.range_m, w.projectile_speed_mps,
        w.base_pk, w.damage, reload_ticks, w.ammo,
    )  # fmt: skip


# `Entity.ammo_credit` is a msgpack int, so it must stay far inside 64 bits (SC-9). It is below
# max(n x lcm, price x lcm / smallest load) with n <= 8 weapons, `lcm` the least common multiple of
# a loadout's full loads and `price` at most 1000 x the dearest cost in stock-thousandths; twice
# `price x lcm` under 2**62 keeps it, and every intermediate product, under 2**63. Real loads are
# tiny (400 and 8 give lcm 400); eight coprime loads of a few hundred rounds are not allowed.
_AMMO_BOUND = 2**62


def _check_ammo_bound(cr: CombatRules, supply: Supply) -> None:
    for (kind, variant), loadout in cr.loadouts.items():
        if loadout:
            price = _MILLI * max(supply.loadout_cost.get(kind, 0), supply.facility_rearm_cost)
            if 2 * price * math.lcm(*(w.ammo for w in loadout)) >= _AMMO_BOUND:
                raise ValueError(
                    f"{kind} {variant or ''}: the least common multiple of its weapons' ammo "
                    "is too large for the rearm accounting; use rounder loads"
                )


def make_rules(
    sim: Sim,
    units: Iterable[UnitConfig],
    roads: RoadGraph,
    *,
    roles: Roles,
    theater: TheaterConfig,
    slots: Slots,
    air: Air,
    fow: Fow,
    logistics: Logistics,
    capture: Capture,
    respawn_delay_ticks: int,
    track_fade_ticks: int,
    sigint_refresh_ticks: int,
    mask_cell_m: float,
    masking: Mapping[tuple[int, int], frozenset[str]],
    campaign: CampaignRules | None = None,
    combat: CombatRules | None = None,
    tasking: TaskingRules | None = None,
) -> Rules:
    """`respawn_delay_ticks`, `track_fade_ticks` and `sigint_refresh_ticks` are
    `slots.respawn_delay_s`, `fow.track_fade_s` and `fow.sigint_refresh_s` already converted by
    the config loader; `masking` is the theater's
    rasterized masking regions (`nexus.runtime.theater.masking_cells`)."""
    units = tuple(units)
    if not mask_cell_m > 0:
        raise ValueError(f"mask_cell_m must be > 0, got {mask_cell_m!r}")
    if theater.bounds_m.w % fow.sigint_cell_m or theater.bounds_m.h % fow.sigint_cell_m:
        # every SIGINT cell, so every blob centre, lies on the map (FOW-2)
        raise ValueError(f"fow.sigint_cell_m {fow.sigint_cell_m} must divide the theater bounds")
    supply = _supply(theater, logistics, world_dt(sim))
    if combat is not None:
        _check_ammo_bound(combat, supply)
    return Rules(
        world_dt=world_dt(sim),
        speed_mps={u.kind: u.speed_mps for u in units},
        domain={u.kind: u.domain for u in units},
        roads=roads,
        role_kind=_role_kind(roles),
        sanctuary=theater.sanctuary,
        max_live_per_commander=slots.max_live_per_commander,
        respawn_delay_ticks=respawn_delay_ticks,
        max_viewer_units=slots.max_viewer_units,
        reserve_queue_max=slots.reserve_queue_max,
        min_speed_mps={u.kind: u.min_speed_mps for u in units if u.min_speed_mps is not None},
        fuel_s={u.kind: u.fuel_s for u in units if u.fuel_s is not None},
        bingo_reserve_frac=air.bingo_reserve_frac,
        landing_nodes=tuple(sorted(n.id for n in theater.nodes if n.kind in _LANDING_KINDS)),
        bounds_m=(float(theater.bounds_m.w), float(theater.bounds_m.h)),
        orbit_period_s=air.orbit_period_s,
        sensor_radius_m={u.kind: u.sensor.radius_m for u in units},
        stealth={u.kind: u.stealth for u in units},
        track_every_ticks=fow.track_every_ticks,
        track_fade_ticks=track_fade_ticks,
        passive_range_m={u.kind: u.sensor.passive_range_m or 0.0 for u in units},
        mask_cell_m=mask_cell_m,
        masking=masking,
        paint_range_m=fow.paint_range_m,
        painters=frozenset(u.kind for u in units if u.kind in _PAINTERS),
        sigint_range_mult=fow.sigint_range_mult,
        sigint_refresh_ticks=sigint_refresh_ticks,
        sigint_cell_m=float(fow.sigint_cell_m),
        sigint_size_m_min=fow.sigint_size_m_min,
        sigint_size_l_min=fow.sigint_size_l_min,
        supply=supply,
        node_kind={n.id: n.kind for n in sorted(theater.nodes, key=lambda n: n.id)},
        armed=frozenset(u.kind for u in units if u.weapons),
        capture=_capture(capture, world_dt(sim)),
        campaign=campaign,
        combat=combat,
        defense=_defense(theater, capture, logistics, sim),
        tasking=tasking,
    )
