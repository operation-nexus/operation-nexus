"""Static per-campaign rules the kernel reads (SIM-CORE §4, SC-2; NX-121).

Read-only data built once from the loaded config: never world state, so it is not in snapshots
or `state_hash` (the campaign's `config_hash` covers it). It takes contract types only, so the
kernel stays free of `nexus.runtime`; the runtime loads the files and builds the road graph.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from nexus.contracts.gen.common.enums import Domain, UnitKind
from nexus.contracts.gen.config.balance import Sim
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.core.roads import RoadGraph


@dataclass(frozen=True, slots=True)
class Rules:
    world_dt: float  # world seconds per tick: TICK_DT x sim.time_scale (SC-2)
    speed_mps: Mapping[UnitKind, float]  # m/s of world time
    domain: Mapping[UnitKind, Domain]
    roads: RoadGraph


def world_dt(sim: Sim) -> float:
    """`1 / tick_hz x time_scale` in exact decimals, then one rounding (6x at 10 Hz is 0.6)."""
    return float(Fraction(repr(sim.time_scale)) / sim.tick_hz)


def make_rules(sim: Sim, units: Iterable[UnitConfig], roads: RoadGraph) -> Rules:
    units = tuple(units)
    return Rules(
        world_dt=world_dt(sim),
        speed_mps={u.kind: u.speed_mps for u in units},
        domain={u.kind: u.domain for u in units},
        roads=roads,
    )
