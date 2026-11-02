"""Forward staging, the pure parts (THREAT-DIRECTOR §4a FS-1, FS-2, FS-6; Q-TD-36, Q-TD-37;
NX-416). `nexus.core.launch` stages, holds, launches and re-stages,
`nexus.core.logistics.stock_targets` raises the staging base's stock target.

Road travel time is `roads.travel_ticks` for the operation's capture kinds (the slowest one), on
the side's public road picture: bridges down in its view (`SideView.bridge_down`) are cut, no node
is avoided (a capture run may cross any node, GAMEPLAY §5). No route counts as never arriving.
Nodes are taken in id order and ties broken by id; nothing draws from the RNG.
"""

import math

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.core.fog import SideView
from nexus.core.roads import travel_ticks
from nexus.core.rules import OperationRules, Rules
from nexus.core.world import DirectorState, World


def pairs(state: DirectorState) -> frozenset[tuple[str, str]]:
    """(operation, target) of every staged operation: not posted again, counted by `max_ops`."""
    return frozenset((s.op, s.target) for s in state.staged)


def capture_kinds(op: OperationRules) -> tuple[UnitKind, ...]:
    """The unit kinds of the operation's CAPTURE jobs, in template order, each once."""
    return tuple(dict.fromkeys(k for j in op.jobs if j.kind == "CAPTURE" for k in j.unit_kinds))


def _ticks(rules: Rules, view: SideView, kinds: tuple[UnitKind, ...], a: str, b: str) -> float:
    """The slowest of `kinds`' road travel ticks from `a` to `b`; infinite with no route."""
    worst = 0.0
    for k in kinds:
        t = travel_ticks(
            rules.roads, a, b, rules.speed_mps[k], rules.world_dt, blocked=view.bridge_down
        )
        if t is None:
            return math.inf
        worst = max(worst, t)
    return worst


def far(rules: Rules, view: SideView, op: OperationRules, target: str) -> bool:
    """FS-1: an operation with a CAPTURE job on a node whose road travel time from the side's rear
    source exceeds `director.staging.direct_s`."""
    dr, kinds = rules.director, capture_kinds(op)
    if dr is None or op.target != "NODE" or not kinds:
        return False
    rear = rules.supply.rear[view.side]
    return _ticks(rules, view, kinds, rear, target) > dr.staging_direct_ticks


def hosts(world: World, rules: Rules, side: Side, node: str, op: OperationRules) -> bool:
    """FS-2, FS-6: `node` can be the operation's staging base now: the side holds it, it is no
    BRIDGE, it holds stock (a `logistics.node_max_stock` above 0), no capture bar is on it, and it
    is a theater `spawns` node for every capture kind's domain (ECONOMY EC-5)."""
    sup = rules.supply
    return (
        world.owner.get(node) == side
        and rules.node_kind.get(node) != "BRIDGE"
        and sup.max_stock.get(node, 0) > 0
        and node not in world.capture
        and all(node in sup.spawns.get(rules.domain[k], ()) for k in capture_kinds(op))
    )


def base_for(
    world: World, rules: Rules, side: Side, view: SideView, op: OperationRules, target: str
) -> str | None:
    """FS-2: the node that `hosts` the operation with the shortest road travel time to `target`,
    ties by id; None when none is strictly nearer than the rear source."""
    kinds, rear = capture_kinds(op), rules.supply.rear[side]
    best: tuple[float, str] = (_ticks(rules, view, kinds, rear, target), "")  # "" is the rear
    for node in sorted(rules.supply.max_stock):
        if node != rear and hosts(world, rules, side, node, op):
            best = min(best, (_ticks(rules, view, kinds, node, target), node))
    return best[1] or None
