"""Static per-campaign rules the kernel reads (SIM-CORE §4, SC-2; NX-121).

Read-only data built once from the loaded config: never world state, so it is not in snapshots
or `state_hash` (the campaign's `config_hash` covers it). It takes contract types only, so the
kernel stays free of `nexus.runtime`; the runtime loads the files and builds the road graph.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from nexus.contracts.gen.common.enums import Domain, Role, UnitKind
from nexus.contracts.gen.config.balance import Sim, Slots
from nexus.contracts.gen.config.roles import Roles
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.core.roads import RoadGraph


@dataclass(frozen=True, slots=True)
class Rules:
    world_dt: float  # world seconds per tick: TICK_DT x sim.time_scale (SC-2)
    speed_mps: Mapping[UnitKind, float]  # m/s of world time
    domain: Mapping[UnitKind, Domain]
    roads: RoadGraph
    role_kind: Mapping[Role, UnitKind]  # content/roles.yaml; a missing role is not playable yet
    sanctuary: str  # the coalition's SANCTUARY node: every JOIN spawns here until NX-123 (GP-7)
    max_live_per_commander: int  # slots.max_live_per_commander (GP-1)
    respawn_delay_ticks: int  # slots.respawn_delay_s as game ticks, rounded up (GP-2, SC-12)


def world_dt(sim: Sim) -> float:
    """`1 / tick_hz x time_scale` in exact decimals, then one rounding (6x at 10 Hz is 0.6)."""
    return float(Fraction(repr(sim.time_scale)) / sim.tick_hz)


def _role_kind(roles: Roles) -> Mapping[Role, UnitKind]:
    """Every role `content/roles.yaml` maps; NAVY joins in P3 (Q-GD-8)."""
    return {"STRIKE": roles.STRIKE, "RECON": roles.RECON, "LOGI": roles.LOGI}


def make_rules(
    sim: Sim,
    units: Iterable[UnitConfig],
    roads: RoadGraph,
    *,
    roles: Roles,
    sanctuary: str,
    slots: Slots,
    respawn_delay_ticks: int,
) -> Rules:
    """`respawn_delay_ticks` is `slots.respawn_delay_s` already converted by the config loader."""
    units = tuple(units)
    return Rules(
        world_dt=world_dt(sim),
        speed_mps={u.kind: u.speed_mps for u in units},
        domain={u.kind: u.domain for u in units},
        roads=roads,
        role_kind=_role_kind(roles),
        sanctuary=sanctuary,
        max_live_per_commander=slots.max_live_per_commander,
        respawn_delay_ticks=respawn_delay_ticks,
    )
