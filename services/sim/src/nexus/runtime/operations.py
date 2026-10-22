"""The operation catalog loader: strict YAML, schema, then the cross-file rules (NX-156).

`content/operations.yaml` (CONFIG-AND-CONTENT §8a, Q-TD-7, Q-SIM-81) is validated against
`contracts/config/operations.json` (an unknown job kind, selector or precondition, a negative or
fractional cost, a missing field are the schema's), then here against the balance profile and the
unit catalog: ids unique; a `director.op_priority` for every operation and none for another; exactly
one of `jobs` and `effect`; a cost within the envelope (at most the largest tier budget, as an
operation above it could never run); units that are ENEMY movers, bought within
`director.max_spawns_per_window`; a selector and a precondition that suit the target and the job
kind. That a unit kind fits its job kind is checked once the kernel rules exist
(`nexus.core.operations.misfits`). The result is in id order, so file order changes nothing.
"""

from fractions import Fraction
from pathlib import Path

from nexus.contracts.gen.config.balance import BalanceConfig
from nexus.contracts.gen.config.operations import Operation, OperationsConfig
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.core.rules import JobTemplate, OperationRules
from nexus.runtime.config import ConfigError, canonical_hash, load_model

# What each precondition and selector can be aimed at (the closed lists of the schema).
_PRECONDITION_TARGET = {
    "target_owner_is_coalition": "NODE",
    "target_in_enemy_view": "NODE",
    "target_capturable": "NODE",
    "target_is_frontline": "NODE",
    "target_recently_lost": "NODE",
    "target_has_damaged_air_defense": "NODE",
    "target_radar_operational": "RADAR",
    "has_unescorted_convoy": "CONVOYS",
}
_SELECTOR_TARGET = {
    "target": "NODE",
    "target_defenses": "NODE",
    "nearest_own_base": "NODE",
    "sector_node": "SECTOR",
    "each_convoy": "CONVOYS",
}
_MOVER_DOMAINS = ("AIR", "GROUND")


def load_operations(
    path: Path, balance: BalanceConfig, units: tuple[UnitConfig, ...]
) -> tuple[OperationRules, ...]:
    """Load and validate the catalog; every problem names the file."""
    cfg = load_model(path, OperationsConfig)
    priority = balance.director.op_priority
    enemy: set[str] = {u.kind for u in units if u.side == "ENEMY" and u.domain in _MOVER_DOMAINS}
    ids = [o.id for o in cfg.operations]
    problems = [f"duplicate operation {i!r}" for i in sorted(set(ids)) if ids.count(i) > 1]
    problems += [f"{i}: no director.op_priority" for i in sorted(set(ids) - set(priority))]
    problems += [
        f"director.op_priority.{i}: no such operation" for i in sorted(set(priority) - set(ids))
    ]
    for op in cfg.operations:
        problems += [f"{op.id}: {p}" for p in _problems(op, balance, enemy)]
    if problems:
        raise ConfigError(f"{path}: " + "; ".join(problems))
    return tuple(
        sorted(
            (_rules(o, Fraction(repr(priority[o.id]))) for o in cfg.operations),
            key=lambda r: r.id,
        )
    )


def _problems(op: Operation, balance: BalanceConfig, enemy: set[str]) -> list[str]:
    d = balance.director
    out = []
    if (op.jobs is None) == (op.effect is None):
        out.append("needs exactly one of jobs and effect")
    if op.effect is not None and op.target != "RADAR":
        out.append("an effect operation aims at a RADAR")
    if (
        op.memory is not None
        and op.memory.counter.endswith("_by_sector")
        and op.target
        not in (
            "NODE",
            "SECTOR",
        )
    ):
        out.append(f"memory {op.memory.counter} needs a NODE or SECTOR target (it reads a sector)")
    if op.track_age and op.target != "SECTOR":
        out.append("track_age needs a SECTOR target")
    for what, values in (("preconditions", op.preconditions), ("enabled_tiers", op.enabled_tiers)):
        if len(set(values)) != len(values):
            out.append(f"duplicate in {what}")
    if op.effect is not None and op.cost != 0:
        out.append("an effect operation has no units, so no cost")
    if op.jobs is not None and op.cost == 0:
        out.append("an operation with jobs buys units, so it costs at least 1")
    ceiling = max(d.budget.pattern_of_life, d.budget.alpha, d.budget.bravo)
    if op.cost > ceiling:
        out.append(f"cost {op.cost} is above the largest tier budget {ceiling}")
    out += [
        f"precondition {p} does not suit target {op.target}"
        for p in sorted(op.preconditions)
        if _PRECONDITION_TARGET[p] != op.target
    ]
    for n, job in enumerate(op.jobs or (), 1):
        where = f"job {n} ({job.kind})"
        if _SELECTOR_TARGET[job.at] != op.target:
            out.append(f"{where}: selector {job.at} does not suit target {op.target}")
        if (job.kind == "ESCORT_CONVOY") != (job.at == "each_convoy"):
            out.append(f"{where}: an ESCORT_CONVOY job is the one at each_convoy")
        out += [
            f"{where}: {k} is not an ENEMY air or ground kind"
            for k in dict.fromkeys(job.unit_kinds)
            if k not in enemy
        ]
    fixed = sum(j.slots for j in op.jobs or () if j.at != "each_convoy")
    if fixed > d.max_spawns_per_window:
        out.append(f"buys {fixed} units, above max_spawns_per_window {d.max_spawns_per_window}")
    return out


def _rules(op: Operation, priority: Fraction) -> OperationRules:
    return OperationRules(
        id=op.id,
        target=op.target,
        preconditions=tuple(sorted(op.preconditions)),
        cost=op.cost,
        tiers=frozenset(op.enabled_tiers),
        jobs=tuple(JobTemplate(j.kind, j.at, tuple(j.unit_kinds), j.slots) for j in op.jobs or ()),
        effect=op.effect,
        priority=priority,
        memory=None if op.memory is None else (op.memory.counter, op.memory.effect),
        track_age=bool(op.track_age),
    )


def operations_hash(ops: tuple[OperationRules, ...]) -> str:
    """The `operations` part of `config_hash`: the canonical hash of the validated catalog in id
    order, with sorted preconditions and tiers, so file order and formatting do not matter."""
    return canonical_hash(
        [
            {
                "id": o.id,
                "target": o.target,
                "preconditions": list(o.preconditions),
                "cost": o.cost,
                "tiers": sorted(o.tiers),
                "effect": o.effect,
                "memory": o.memory,
                "track_age": o.track_age,
                "jobs": [[j.kind, j.at, list(j.unit_kinds), j.slots] for j in o.jobs],
            }
            for o in ops
        ]
    )
