"""Static per-campaign rules the kernel reads (SIM-CORE §4, SC-2; NX-121).

Read-only data built once from the loaded config: never world state, so it is not in snapshots
or `state_hash` (the campaign's `config_hash` covers it). It takes contract types only, so the
kernel stays free of `nexus.runtime`; the runtime loads the files and builds the road graph.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from nexus.contracts.gen.common.enums import Domain, NodeOwner, Role, Side, UnitKind
from nexus.contracts.gen.config.balance import Air, Fow, Logistics, Sim, Slots
from nexus.contracts.gen.config.roles import Roles
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.core.roads import RoadGraph

_LANDING_KINDS = ("AIRBASE", "SANCTUARY")  # aircraft land only here (Q-SIM-38, NX-368)
_SIDES: tuple[Side, ...] = ("COALITION", "ENEMY")
# Recon units paint targets (CONFIG-AND-CONTENT §7.3, FOG-OF-WAR Q-FOW-6). shortcut: named here
# until the unit catalog lists capabilities; then it becomes a catalog field.
_PAINTERS: tuple[UnitKind, ...] = ("RECON_UAV", "ENEMY_RECON_UAV")
# Kinds that haul cargo (GAMEPLAY §5). shortcut: named here until the unit catalog gets its `cargo`
# field (CONFIG-AND-CONTENT §7.3); the amount is the one global `logistics.truck_cargo`.
_CARRIERS: tuple[UnitKind, ...] = ("LOGI_TRUCK", "ENEMY_CONVOY")
_MILLI = 1000  # a truck's unload progress is counted in thousandths of a stock unit


@dataclass(frozen=True, slots=True)
class Supply:
    """Logistics rules (NX-123, GAMEPLAY §5). The default is a theater with no stock nodes and no
    carriers, for hand-built rules in tests."""

    rear: Mapping[Side, str] = field(default_factory=dict)  # each side's SANCTUARY: infinite source
    # Node -> its starting owner. Interim "friendly" test: node ownership becomes world state with
    # capture (NX-125), which must replace this.
    start_owner: Mapping[str, NodeOwner] = field(default_factory=dict)
    max_stock: Mapping[str, int] = field(default_factory=dict)  # finite-stock nodes only
    starve_floor: Mapping[str, int] = field(default_factory=dict)  # ceil(starve_threshold x max)
    carriers: frozenset[UnitKind] = frozenset()
    truck_cargo: int = 0  # logistics.truck_cargo
    unload_milli: int = 0  # logistics.unload_rate x world_dt, in thousandths per tick


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
    # Side -> the AIRBASE and SANCTUARY nodes it may land at, by id. From the theater's start
    # owners: node ownership becomes world state with capture (NX-125), which must replace this.
    landing_bases: Mapping[Side, tuple[str, ...]]
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


def world_dt(sim: Sim) -> float:
    """`1 / tick_hz x time_scale` in exact decimals, then one rounding (6x at 10 Hz is 0.6)."""
    return float(Fraction(repr(sim.time_scale)) / sim.tick_hz)


def _role_kind(roles: Roles) -> Mapping[Role, UnitKind]:
    """Every role `content/roles.yaml` maps; NAVY joins in P3 (Q-GD-8)."""
    return {"STRIKE": roles.STRIKE, "RECON": roles.RECON, "LOGI": roles.LOGI}


def _landing_bases(theater: TheaterConfig) -> Mapping[Side, tuple[str, ...]]:
    nodes = sorted(theater.nodes, key=lambda n: n.id)
    return {
        side: tuple(n.id for n in nodes if n.kind in _LANDING_KINDS and n.start_owner == side)
        for side in _SIDES
    }


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
    if unload_milli < 1:
        raise ValueError("logistics.unload_rate x world_dt is below 0.001 stock per tick")
    return Supply(
        rear={side: sanctuaries[side] for side in _SIDES},
        start_owner={n.id: n.start_owner for n in theater.nodes},
        max_stock=max_stock,
        starve_floor={k: math.ceil(logistics.starve_threshold * v) for k, v in max_stock.items()},
        carriers=frozenset(_CARRIERS),
        truck_cargo=logistics.truck_cargo,
        unload_milli=unload_milli,
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
    respawn_delay_ticks: int,
    track_fade_ticks: int,
    sigint_refresh_ticks: int,
    mask_cell_m: float,
    masking: Mapping[tuple[int, int], frozenset[str]],
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
        landing_bases=_landing_bases(theater),
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
        supply=_supply(theater, logistics, world_dt(sim)),
    )
