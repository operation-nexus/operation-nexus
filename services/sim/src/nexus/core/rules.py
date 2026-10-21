"""Static per-campaign rules the kernel reads (SIM-CORE §4, SC-2; NX-121).

Read-only data built once from the loaded config: never world state, so it is not in snapshots
or `state_hash` (the campaign's `config_hash` covers it). It takes contract types only, so the
kernel stays free of `nexus.runtime`; the runtime loads the files and builds the road graph.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from nexus.contracts.gen.common.enums import Domain, Role, Side, UnitKind
from nexus.contracts.gen.config.balance import Air, Fow, Sim, Slots
from nexus.contracts.gen.config.roles import Roles
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.core.roads import RoadGraph

_LANDING_KINDS = ("AIRBASE", "SANCTUARY")  # aircraft land only here (Q-SIM-38, NX-368)
_SIDES: tuple[Side, ...] = ("COALITION", "ENEMY")


@dataclass(frozen=True, slots=True)
class Rules:
    world_dt: float  # world seconds per tick: TICK_DT x sim.time_scale (SC-2)
    speed_mps: Mapping[UnitKind, float]  # m/s of world time; a top speed (Q-SIM-38)
    domain: Mapping[UnitKind, Domain]
    roads: RoadGraph
    role_kind: Mapping[Role, UnitKind]  # content/roles.yaml; a missing role is not playable yet
    sanctuary: str  # the coalition's SANCTUARY node: every JOIN spawns here until NX-123 (GP-7)
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
    respawn_delay_ticks: int,
    track_fade_ticks: int,
) -> Rules:
    """`respawn_delay_ticks` and `track_fade_ticks` are `slots.respawn_delay_s` and
    `fow.track_fade_s` already converted by the config loader."""
    units = tuple(units)
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
    )
