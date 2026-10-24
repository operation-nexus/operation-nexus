"""Static per-campaign rules the kernel reads (SIM-CORE §4, SC-2; NX-121).

Read-only data built once from the loaded config: never world state, so it is not in snapshots
or `state_hash` (the campaign's `config_hash` covers it). It takes contract types only, so the
kernel stays free of `nexus.runtime`; the runtime loads the files and builds the road graph.
"""

import math
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal, cast

from nexus.contracts.gen.common.enums import (
    AltBand,
    DamageState,
    Domain,
    JobKind,
    NodeKind,
    NodeOwner,
    Role,
    Side,
    ThreatTier,
    UnitKind,
)
from nexus.contracts.gen.config.balance import (
    Air,
    Capture,
    Director,
    Fow,
    IdleFloor,
    Logistics,
    Sim,
    Slots,
    Tasking,
)
from nexus.contracts.gen.config.balance import Campaign as CampaignBalance
from nexus.contracts.gen.config.balance import Combat as CombatBalance
from nexus.contracts.gen.config.roles import Roles
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.contracts.gen.config.weapons import Weapon
from nexus.core.geometry import in_polygon
from nexus.core.roads import RoadGraph

CAPTURE_FULL = 100_000_000  # a full capture bar, in millionths of a percent (NX-125)
CP_SCALE = 1_000_000  # coalition power and provocation are whole millionths of a point (NX-155)

_SIDES: tuple[Side, ...] = ("COALITION", "ENEMY")
# Recon units paint targets (CONFIG-AND-CONTENT §7.3, FOG-OF-WAR Q-FOW-6). shortcut: named here
# until the unit catalog lists capabilities; then it becomes a catalog field.
_PAINTERS: tuple[UnitKind, ...] = ("RECON_UAV", "ENEMY_RECON_UAV")
# Kinds that haul cargo (GAMEPLAY §5). shortcut: named here until the unit catalog gets its `cargo`
# field (CONFIG-AND-CONTENT §7.3); the amount is the one global `logistics.truck_cargo`.
_CARRIERS: tuple[UnitKind, ...] = ("LOGI_TRUCK", "ENEMY_CONVOY")
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
    # ceil(logistics.stock_target_frac x max): the forward stock target (Q-SIM-100, NX-389)
    stock_target: Mapping[str, int] = field(default_factory=dict)
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
    # logistics.ammo_loadout_share: of a loadout_cost, what a kind with ammo and fuel pays for ammo
    ammo_loadout_share: Fraction = Fraction(1, 2)
    # Domain -> the theater `spawns` nodes that take that domain (GP-7, Q-SIM-54).
    spawns: Mapping[Domain, frozenset[str]] = field(default_factory=dict)
    # BRIDGE node -> its max hp, `logistics.bridge_hp`, in id order (NX-373; empty: hand-built).
    bridge_hp: Mapping[str, int] = field(default_factory=dict)
    # `logistics.bridge_collapse_radius_m` (Q-SIM-112): how far along the cut edge a bridge's fall
    # destroys GROUND units (0 in hand-built rules: only a unit exactly at the cut point).
    bridge_collapse_m: float = 0.0
    # logistics.bridge_hp / (bridge_repair_time_s x truck_bridge_repair_mult) x world_dt, in
    # thousandths of an hp per tick per carrier parked at a bridge's stop (NX-373 part 2).
    bridge_repair_milli: int = 0


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
    min_progress: int  # capture.min_progress_per_tick, millionths of a percent of the bar
    requires_defenses_down: bool  # a bar starts only at 0 defense hp (Q-GD-18)
    air_weight: float | None  # capture.air_weight when capture.air_counts, else None (N-3)
    quiet_sides: frozenset[Side]  # the sides the quiet-stream multiplier applies to (Q-SIM-26)


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
    idle_floor: bool  # campaign.idle_floor.enabled (Q-GP-44)
    sanctuary_min_hp: int  # campaign.idle_floor.sanctuary_min_hp


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
    enemy_hq: str  # its capture by the coalition wins, when `hq_capture`
    hq_capture: bool  # campaign.victory.hq_capture
    objective_pick: str  # campaign.objective_pick: "uniform", the only value so far
    # Objective candidates by id (never SANCTUARY, BRIDGE or the enemy HQ; Q-SM-11) -> the ids of
    # their road neighbours that can have an owner (not BRIDGE): a candidate with a neighbour of
    # another owner is on the frontline.
    candidates: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class TaskingRules:
    """Tasking Board rules (NX-374, GAMEPLAY §1b, Q-SIM-73): durations in running ticks, the
    priorities and the aging rate exact (Fractions) so a ranking and a tie are exact, and the
    urgencies in thousandths. `slots` holds the fixed slot counts; a resupply job is sized from
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
    scout_post_interval_ticks: int  # at most one new generated scout job per board this often
    capture_max_restarts: int  # fresh CAPTURE expiries while the claimants are still driving
    scout_open_max: int  # the most generated scout jobs a board holds at once (NX-156)
    station_m: Mapping[
        str, float
    ]  # follow_station_m: escort, column, overwatch, wingman (Q-SIM-76)
    threat_memory_ticks: int  # how long an attacker of a group stays a group threat
    leash_m: float  # the farthest an escort leaves station to engage
    static_offense_min_tier: ThreatTier  # the lowest tier at which the Static's board posts strikes
    follow_hold_slack: float  # a stopped leader's followers hold within this many stations of it
    overfill_factor: int  # with every job full, a job takes units up to this times its slots
    overfill_point_jobs: bool  # tasking.overfill_point_jobs: a Recon point job overfills too
    join_excluded_jobs: frozenset[JobKind]  # tasking.join_excluded_jobs: a bare JOIN never takes
    scout_blob_runs: int  # SIGINT refreshes a blob must stay in a cell before a scout is posted
    scout_urgency_milli: Mapping[str, int]  # by blob size S / M / L, in thousandths
    strike_urgency_per_threat_milli: int  # urgency a facility's `threat` point adds, thousandths
    strike_max_scaled_slots: (
        int  # extra strike slots for idle armed viewer units, at most (Q-SIM-92)
    )
    strike_idle_targets_max: int  # strike jobs on known defended foe nodes at once (Q-SIM-92)
    strike_idle_targets_min_tier: ThreatTier  # the lowest Static tier at which they are posted
    patrol_max_nodes: int  # coalition front-line nodes with a patrol job at once (Q-SIM-94)
    patrol_orbit_m: float  # an aircraft patrol circles its node this far out (Q-SIM-94)
    patrol_dwell_ticks: int  # a coalition patrol is done this long after it is on station
    order_dwell_ticks: int  # an armed unit holds its GOTO node at most this long (Q-SIM-110)
    stock_urgency_milli: int  # a stocking resupply job's urgency (Q-SIM-100, NX-389)
    stock_front_bonus_milli: int  # added to it on a front-line base
    ai_jobs: frozenset[JobKind]  # tasking.ai_jobs: an AI garrison unit takes these by itself
    ai_excluded_jobs: frozenset[JobKind]  # tasking.ai_excluded_jobs: and never these (Q-GP-45)
    human_displaces_ai: bool  # tasking.human_displaces_ai: a viewer's unit bumps an AI claimant
    escort_repair_crews: bool  # tasking.escort_repair_crews: escort each repair truck (Q-SIM-118)


@dataclass(frozen=True, slots=True)
class Weights:
    """Provocation per action, in millionths of a point (Q-SIM-78, Q-TD-11)."""

    destroyed: int
    damaged: int
    recon_destroyed: int
    recon_damaged: int
    convoy_hit: int
    facility_damaged: int
    facility_disabled: int
    captured: int
    scout_in_rear: int
    redemption_support: int
    redemption_cosmetic: int


@dataclass(frozen=True, slots=True)
class JobTemplate:
    """One job of an operation (`content/operations.yaml`, CONFIG-AND-CONTENT §8a): `at` is a
    selector (`nexus.core.operations`), `slots` units are bought, taking `unit_kinds` in turn."""

    kind: JobKind
    at: str
    unit_kinds: tuple[UnitKind, ...]
    slots: int


@dataclass(frozen=True, slots=True)
class OperationRules:
    """One catalog operation with its `director.op_priority` (exact). `jobs` or `effect`, not both.
    `memory` is the threat-memory counter that moves its score, and how."""

    id: str
    target: str
    preconditions: tuple[str, ...]
    cost: int
    tiers: frozenset[ThreatTier]
    jobs: tuple[JobTemplate, ...]
    effect: str | None
    priority: Fraction
    memory: tuple[str, str] | None = None  # (counter, RAISE or LOWER), THREAT-DIRECTOR §2
    track_age: bool = False  # TD-5: the score rises with the staleness of the sector's picture


@dataclass(frozen=True, slots=True)
class DirectorRules:
    """Threat Director (NX-155, NX-156, THREAT-DIRECTOR §2-§5a). Coalition power and provocation are
    whole millionths of a point and the tick counts are game ticks, so every threshold, EMA step and
    decay is exact integer arithmetic (floor division) and a snapshot restores them bit for bit.
    `decay` is the per-window multiplier `num / den` of the provocation half-life, `memory_decay`
    that of the threat-memory half-life; `ema` the per-window EMA step. Scoring (§4 step 4) is
    exact Fractions: `target_value` by node kind, `weakness_max`, `proximity` and `noise`.
    `operations` are the catalog in id order; `retake_ticks` how long a lost node can be retaken."""

    window_ticks: int
    cp_value: Mapping[UnitKind, int]  # a kind not listed counts 0
    ema: tuple[int, int]
    alpha_enter_cp: int
    bravo_enter_cp: int
    exit_ratio: Fraction
    min_dwell_ticks: int
    start_tier: ThreatTier  # director.tier.start: the tier a campaign starts in
    max_step: int  # director.tier.max_step: tier steps one move takes (Q-TD-1: 1)
    escalate: int
    bravo: int
    decay: tuple[int, int]
    weights: Weights
    ai_shooter_mult: Fraction  # director.provocation.ai_shooter_mult: x a hit by no player's unit
    budget: Mapping[ThreatTier, int]
    max_spawns_per_window: int
    max_live_units: Mapping[ThreatTier, int]
    operations: tuple[OperationRules, ...]
    target_value: Mapping[NodeKind, Fraction]
    weakness_max: Fraction
    proximity: Fraction
    noise: Fraction
    memory_decay: tuple[int, int]
    retake_ticks: int
    dark_ticks: int  # how long a blinking radar is dark (Q-SIM-82)
    blink_cooldown_ticks: int  # before the same radar may blink again
    bridge_cooldown_ticks: int  # after BridgeRepaired, before STRIKE_BRIDGE aims at it (Q-SIM-121)
    max_ops: Mapping[ThreatTier, int | None]  # ALPHA, BRAVO: non-routine ops at once
    proximity_tiers: frozenset[ThreatTier]  # CP ceilings at which `proximity` applies
    scout_in_rear_max: int  # scout-in-rear notes one window adds
    idle_retire_ticks: int  # a Director unit with no job this long is retired (Q-SIM-84)
    blink_max: int  # radars that start a blink in one window
    up_above: int  # millionths of an event: a ThreatAdaptation goes UP above it
    reinforce_above: Fraction  # share of a site's HP missing above which ReinforceIADS fires
    escort_min_convoys: int  # the fewest convoys an escort operation is cut to
    frontline_hops: int  # road hops that define the front
    memory_factor: Fraction  # k in 1 + k c, 1 / (1 + k c)
    own_node_value: Fraction  # target value of a node the side already holds
    weakness_min: Fraction  # weakness multiplier at full defenses
    stale_factor: Fraction  # coefficient of the Recon staleness term
    job_urgency_milli: int  # urgency of an operation's jobs, thousandths
    down_below: int  # millionths of an event: a ThreatAdaptation goes DOWN below it
    memory_weights: Mapping[
        str, int
    ]  # millionths of an event per convoy/radar hit, scout/node lost
    # Pattern of Life (Q-SIM-85, NX-157). `garrison_kinds`: the kinds that fill a base's garrison,
    # by node kind, round-robin; the periods are game ticks on the campaign clock; `night_cap_ticks`
    # is 1 / `campaign.night_progress_cap_nodes_per_h` game hours.
    garrison_kinds: Mapping[NodeKind, tuple[UnitKind, ...]]
    patrol_ticks: int
    convoy_ticks: int
    offensive_ticks: int
    night_cap_ticks: int
    convoy_kind: UnitKind  # the carrier of a Pattern of Life convoy
    replace_per_window: int  # garrison units a short base buys in one window
    patrols_per_base: int
    patrol_slots: int  # units one patrol job takes
    convoy_slots: int  # units one Pattern of Life convoy job takes
    convoys_per_period: int
    offensives_per_period: int
    capture_slot_tiers: frozenset[ThreatTier]  # director.pol.capture_slot_tiers (Q-SIM-85)
    convoy_cost: int  # budget points of one Pattern of Life convoy
    # Recon (NX-379, Q-SIM-87): a scout loiters `recon_loiter_ticks` within `recon_loiter_radius_m`
    # of its point, picked from a grid of `recon_grid_m` over the sector.
    recon_loiter_ticks: int
    recon_loiter_radius_m: float
    recon_grid_m: int
    recon_memory_ticks: int  # how long a cell a sensor covered counts as looked at
    # Scout intercepts (Q-SIM-96, NX-382): a coalition scout tracked inside `intercept_radius_m` of
    # a Static-held node for `intercept_reaction_ticks` (`intercept_pol_linger_ticks` at Pattern of
    # Life) draws an interceptor; a garrison fighter takes one within `intercept_leash_m` of its
    # home; the job ends once the scout was untracked `intercept_lost_ticks`.
    intercept_radius_m: float
    intercept_leash_m: float
    intercept_reaction_ticks: int
    intercept_pol_linger_ticks: int
    intercept_lost_ticks: int


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
    min_damage: int  # combat.min_damage: the least hp a hit takes, however heavy the armor
    facility_indestructible: bool  # combat.facility_indestructible: the CB-9 hp floor

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
    # capture.uncapturable_node_kinds: never captured, no defenses, not a base (empty: hand-built).
    uncapturable: frozenset[NodeKind] = frozenset()
    masked_bands: frozenset[AltBand] = frozenset()  # fow.masked_alt_bands (empty: hand-built)
    capture: CaptureRules | None = None
    campaign: CampaignRules | None = None  # NX-126; None leaves the campaign layer off
    combat: CombatRules | None = None  # NX-124; None leaves combat off
    defense: DefenseRules | None = None  # NX-124 part 3; None: nodes have no defense HP
    tasking: TaskingRules | None = None  # NX-374; None leaves the Tasking Boards off
    director: DirectorRules | None = None  # NX-155; None leaves the Threat Director off
    # Static base id -> `garrison_quota` of the theater (Q-SIM-85): the live Director units kept
    # homed there.
    garrison_quota: Mapping[str, int] = field(default_factory=dict)
    # Sector id -> polygon (id order), from the theater (NX-155): where a provocation happened;
    # `sector_at` finds a point's sector.
    sectors: tuple[tuple[str, tuple[tuple[int, int], ...]], ...] = ()
    # slots.rebase_order (Q-SIM-90): the order a rebased unit is left with; the default is for
    # hand-built rules, the shipped value comes from `balance/default.yaml`.
    rebase_order: Literal["HOLD"] = "HOLD"

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
    scout_post_interval_ticks: int,
    threat_memory_ticks: int,
    patrol_dwell_ticks: int,
    order_dwell_ticks: int,
) -> TaskingRules:
    """The tick counts are `cfg`'s game-time keys already converted by the config loader. Raises
    ValueError when the stocking urgency rounds to 0 thousandths, or a front-line stocking job
    could reach 1000 thousandths (1.0), the least a starving or damaged base's job has
    (Q-SIM-100: those always rank first). Checked on the stored thousandths, after rounding."""
    stock_urgency = round(Fraction(repr(cfg.stock_urgency)) * 1000)
    front_bonus = round(Fraction(repr(cfg.stock_front_bonus)) * 1000)
    if stock_urgency < 1 or front_bonus < 0 or stock_urgency + front_bonus >= 1000:
        raise ValueError(
            "tasking.stock_urgency must be at least 0.001 and tasking.stock_urgency + "
            "tasking.stock_front_bonus must stay below 1.0, in whole thousandths"
        )
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
        scout_open_max=cfg.scout_open_max,
        capture_max_restarts=cfg.capture_max_restarts,
        scout_post_interval_ticks=scout_post_interval_ticks,
        station_m=cfg.follow_station_m.model_dump(),
        threat_memory_ticks=threat_memory_ticks,
        leash_m=cfg.escort_leash_m,
        static_offense_min_tier=cfg.static_offense_min_tier,
        follow_hold_slack=cfg.follow_hold_slack,
        overfill_factor=cfg.overfill_factor,
        overfill_point_jobs=cfg.overfill_point_jobs,
        join_excluded_jobs=frozenset(cfg.join_excluded_jobs),
        scout_blob_runs=cfg.scout_blob_runs,
        scout_urgency_milli={
            k[0].upper(): round(Fraction(repr(v)) * 1000) for k, v in cfg.scout_urgency
        },
        strike_urgency_per_threat_milli=round(Fraction(repr(cfg.strike_urgency_per_threat)) * 1000),
        strike_max_scaled_slots=cfg.strike_max_scaled_slots,
        strike_idle_targets_max=cfg.strike_idle_targets_max,
        strike_idle_targets_min_tier=cfg.strike_idle_targets_min_tier,
        patrol_max_nodes=cfg.patrol_max_nodes,
        patrol_orbit_m=cfg.patrol_orbit_m,
        patrol_dwell_ticks=patrol_dwell_ticks,
        order_dwell_ticks=order_dwell_ticks,
        stock_urgency_milli=stock_urgency,
        stock_front_bonus_milli=front_bonus,
        ai_jobs=frozenset(cfg.ai_jobs),
        ai_excluded_jobs=frozenset(cfg.ai_excluded_jobs),
        human_displaces_ai=cfg.human_displaces_ai,
        escort_repair_crews=cfg.escort_repair_crews,
    )


_Q = 2**40  # the provocation decay multiplier's denominator
# The reduced half-life : window ratio p / q may have neither part above this: the bisection below
# raises numbers to the power p, which stays under a millisecond or so up to 256 (shipped: 15 / 1).
DECAY_RATIO_MAX = 256  # a bound on the bisection's cost, not a game rule: it rejects a config


def _decay(half_life_ticks: int, window_ticks: int) -> tuple[int, int]:
    """`2 ** -(window / half_life)` as `m / _Q`: `m` is the largest integer with
    `(m / _Q) ** p * 2 ** q <= 1`, for `p / q = half_life / window` in lowest terms. An exact
    integer bisection, no float."""
    ratio = Fraction(half_life_ticks, window_ticks)
    p, q = ratio.numerator, ratio.denominator
    if max(p, q) > DECAY_RATIO_MAX:
        raise ValueError(
            f"half-life : window is {p} / {q}; neither part may exceed {DECAY_RATIO_MAX}"
        )
    lo, hi = 0, _Q
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid**p * 2**q <= _Q**p:
            lo = mid
        else:
            hi = mid - 1
    return lo, _Q


def _micro(value: float) -> int:
    return round(Fraction(repr(value)) * CP_SCALE)


def director_rules(
    cfg: Director,
    units: Iterable[UnitConfig],
    *,
    window_ticks: int,
    ema_ticks: int,
    half_life_ticks: int,
    min_dwell_ticks: int,
    memory_half_life_ticks: int,
    retake_ticks: int,
    dark_ticks: int,
    blink_cooldown_ticks: int,
    bridge_cooldown_ticks: int,
    idle_retire_ticks: int,
    operations: Iterable[OperationRules],
    patrol_ticks: int,
    convoy_ticks: int,
    offensive_ticks: int,
    night_cap_ticks: int,
    recon_loiter_ticks: int,
    recon_memory_ticks: int,
    intercept_reaction_ticks: int,
    intercept_pol_linger_ticks: int,
    intercept_lost_ticks: int,
) -> DirectorRules:
    """The tick counts are `cfg`'s game-time keys already converted by the config loader;
    `operations` is the validated catalog (`nexus.runtime.operations`). Raises ValueError for a
    coalition-side kind without a `cp.unit_value` (the threshold order is checked by
    `load_balance`)."""
    values = {cast(UnitKind, k): _micro(v) for k, v in cfg.cp.unit_value}
    missing = sorted(u.kind for u in units if u.side == "COALITION" and u.kind not in values)
    if missing:
        raise ValueError(f"director.cp.unit_value has no value for the coalition kinds {missing}")
    pv = cfg.provocation
    w, r = pv.weights, pv.weights.redemption
    return DirectorRules(
        window_ticks=window_ticks,
        cp_value=values,
        ema=(min(window_ticks, ema_ticks), ema_ticks),
        alpha_enter_cp=_micro(cfg.tier.alpha_enter_cp),
        bravo_enter_cp=_micro(cfg.tier.bravo_enter_cp),
        exit_ratio=Fraction(repr(cfg.tier.exit_ratio)),
        min_dwell_ticks=min_dwell_ticks,
        start_tier=cfg.tier.start,
        max_step=cfg.tier.max_step,
        escalate=_micro(pv.escalate_threshold),
        bravo=_micro(pv.bravo_threshold),
        decay=_decay(half_life_ticks, window_ticks),
        weights=Weights(
            _micro(w.unit_destroyed), _micro(w.unit_damaged),
            _micro(w.recon_destroyed), _micro(w.recon_damaged), _micro(w.convoy_hit),
            _micro(w.facility_damaged), _micro(w.facility_disabled), _micro(w.base_captured),
            _micro(w.scout_in_rear), _micro(r.support), _micro(r.cosmetic),
        ),
        ai_shooter_mult=Fraction(repr(pv.ai_shooter_mult)),
        budget={"PATTERN_OF_LIFE": cfg.budget.pattern_of_life, "ALPHA": cfg.budget.alpha,
                "BRAVO": cfg.budget.bravo},
        max_spawns_per_window=cfg.max_spawns_per_window,
        max_live_units={"PATTERN_OF_LIFE": cfg.max_live_units.pattern_of_life,
                        "ALPHA": cfg.max_live_units.alpha, "BRAVO": cfg.max_live_units.bravo},
        operations=tuple(sorted(operations, key=lambda o: o.id)),
        target_value={cast(NodeKind, k): Fraction(repr(v)) for k, v in cfg.score.target_value},
        weakness_max=Fraction(repr(cfg.score.weakness_max)),
        proximity=Fraction(repr(cfg.score.provocation_proximity)),
        noise=Fraction(repr(cfg.noise_scale)),
        memory_decay=_decay(memory_half_life_ticks, window_ticks),
        retake_ticks=retake_ticks,
        dark_ticks=dark_ticks,
        blink_cooldown_ticks=blink_cooldown_ticks,
        bridge_cooldown_ticks=bridge_cooldown_ticks,
        max_ops={
            "ALPHA": cfg.max_ops.alpha,
            "BRAVO": cfg.max_ops.bravo,
        },
        proximity_tiers=frozenset(cfg.score.proximity_tiers),
        scout_in_rear_max=pv.scout_in_rear_max_per_window,
        idle_retire_ticks=idle_retire_ticks,
        blink_max=cfg.decoy_blink.max_per_window,
        up_above=_micro(cfg.adaptation_up_above),
        reinforce_above=Fraction(repr(cfg.reinforce_damage_above)),
        escort_min_convoys=cfg.escort_min_convoys,
        frontline_hops=cfg.frontline_hops,
        memory_factor=Fraction(repr(cfg.memory.factor)),
        own_node_value=Fraction(repr(cfg.score.own_node_value)),
        weakness_min=Fraction(repr(cfg.score.weakness_min)),
        stale_factor=Fraction(repr(cfg.score.stale_factor)),
        job_urgency_milli=round(Fraction(repr(cfg.job_urgency)) * 1000),
        down_below=_micro(cfg.adaptation_down_below),
        memory_weights={k: _micro(v) for k, v in cfg.memory.weights},
        garrison_kinds={
            cast(NodeKind, k): tuple(cast(UnitKind, u) for u in v) for k, v in cfg.garrison.kinds
        },
        patrol_ticks=patrol_ticks,
        convoy_ticks=convoy_ticks,
        offensive_ticks=offensive_ticks,
        night_cap_ticks=night_cap_ticks,
        convoy_kind=cfg.pol.convoy_kind,
        replace_per_window=cfg.garrison.replace_per_window,
        patrols_per_base=cfg.pol.patrols_per_base,
        patrol_slots=cfg.pol.patrol_slots,
        convoy_slots=cfg.pol.convoy_slots,
        convoys_per_period=cfg.pol.convoys_per_period,
        offensives_per_period=cfg.pol.offensives_per_period,
        capture_slot_tiers=frozenset(cfg.pol.capture_slot_tiers),
        convoy_cost=cfg.pol.convoy_cost,
        recon_loiter_ticks=recon_loiter_ticks,
        recon_loiter_radius_m=cfg.recon.loiter_radius_m,
        recon_grid_m=cfg.recon.grid_m,
        recon_memory_ticks=recon_memory_ticks,
        intercept_radius_m=cfg.intercept.radius_m,
        intercept_leash_m=cfg.intercept.leash_m,
        intercept_reaction_ticks=intercept_reaction_ticks,
        intercept_pol_linger_ticks=intercept_pol_linger_ticks,
        intercept_lost_ticks=intercept_lost_ticks,
    )  # fmt: skip


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
        capture.empty_base_mult, decay_micro, capture.min_progress_per_tick,
        capture.requires_defenses_down, capture.air_weight if capture.air_counts else None,
        frozenset(capture.quiet_sides),
    )  # fmt: skip


def _defense(
    theater: TheaterConfig, capture: Capture, logistics: Logistics, sim: Sim, idle: IdleFloor
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
        ticks_per_min=60 * sim.tick_hz,  # 60: seconds per minute, a unit conversion
        sanctuary_repair_milli=repair_milli,
        forward_airbase=theater.forward_airbase,
        idle_floor=idle.enabled,
        sanctuary_min_hp=idle.sanctuary_min_hp,
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
    truck_s = logistics.bridge_repair_time_s * logistics.truck_bridge_repair_mult
    bridge_milli = round(logistics.bridge_hp * dt * _MILLI / truck_s)
    if bridge_milli < 1:
        raise ValueError("a truck's bridge repair rate x world_dt is below 0.001 hp per tick")
    return Supply(
        rear={side: sanctuaries[side] for side in _SIDES},
        start_owner={n.id: n.start_owner for n in theater.nodes},
        max_stock=max_stock,
        starve_floor={k: math.ceil(logistics.starve_threshold * v) for k, v in max_stock.items()},
        stock_target={k: math.ceil(logistics.stock_target_frac * v) for k, v in max_stock.items()},
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
        ammo_loadout_share=Fraction(repr(logistics.ammo_loadout_share)),
        spawns={d: frozenset(s.node for s in theater.spawns if d in s.domains) for d in _DOMAINS},
        bridge_hp={
            n.id: logistics.bridge_hp
            for n in sorted(theater.nodes, key=lambda n: n.id)
            if n.kind == "BRIDGE"
        },
        bridge_collapse_m=logistics.bridge_collapse_radius_m,
        bridge_repair_milli=bridge_milli,
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
    uncapturable: Collection[NodeKind],
) -> CampaignRules:
    """The tick counts are `cfg`'s game-time keys already converted by the config loader."""
    kind = {n.id: n.kind for n in theater.nodes}
    ownable = {n for n, k in kind.items() if k != "BRIDGE"}
    skip = {n for n, k in kind.items() if k in uncapturable} | {theater.enemy_hq}
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
        strategic=tuple(sorted(n for n, k in kind.items() if k in cfg.strategic_node_kinds)),
        enemy_hq=theater.enemy_hq,
        hq_capture=cfg.victory.hq_capture,
        objective_pick=cfg.objective_pick,
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
        min_damage=cfg.min_damage,
        facility_indestructible=cfg.facility_indestructible,
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
    idle_floor: IdleFloor,
    respawn_delay_ticks: int,
    track_fade_ticks: int,
    sigint_refresh_ticks: int,
    mask_cell_m: float,
    masking: Mapping[tuple[int, int], frozenset[str]],
    campaign: CampaignRules | None = None,
    combat: CombatRules | None = None,
    tasking: TaskingRules | None = None,
    director: DirectorRules | None = None,
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
        landing_nodes=tuple(
            sorted(n.id for n in theater.nodes if n.kind in air.landing_node_kinds)
        ),
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
        uncapturable=frozenset(capture.uncapturable_node_kinds),
        masked_bands=frozenset(fow.masked_alt_bands),
        capture=_capture(capture, world_dt(sim)),
        campaign=campaign,
        combat=combat,
        defense=_defense(theater, capture, logistics, sim, idle_floor),
        tasking=tasking,
        director=director,
        garrison_quota={n.id: n.garrison_quota for n in theater.nodes if n.garrison_quota},
        sectors=tuple(
            (s.id, tuple((x, y) for x, y in s.polygon))
            for s in sorted(theater.sectors, key=lambda s: s.id)
        ),
        rebase_order=slots.rebase_order,
    )


def sector_at(rules: Rules, x: float, y: float) -> str | None:
    """The first sector, by id, whose polygon holds the point (an edge counts as inside); None when
    outside every one (`nexus.core.geometry`)."""
    for sector, poly in rules.sectors:
        if in_polygon(x, y, poly):
            return sector
    return None
