"""Logistics: where a truck loads and what it does on arrival (NX-123 part 1; GAMEPLAY §5, GP-7,
Q-GP-24, Q-SIM-48..50).

Stock is whole units in `World.stock` (finite nodes only; a SANCTUARY is infinite by rule). A truck
loads at its source when it spawns and unloads at its destination in the `logistics` system. All
counts are integers, so stock plus cargo is conserved exactly: a unit leaves a source's stock at
the same moment it becomes a truck's cargo, and leaves the cargo as it joins a node's stock. The
unload rate is counted in thousandths of a unit per tick (`Supply.unload_milli`), carried on the
truck as `Entity.unload_milli` so no fraction is ever lost to rounding.

"Friendly" is the node's theater `start_owner` for now: ownership becomes world state with capture
(NX-125), which must replace `friendly`. Routes avoid no bridge until combat can destroy one
(NX-124). The `logistics` system is deterministic: entities in id order, candidate nodes in id
order, ties on distance by node id.
"""

from itertools import pairwise
from typing import NamedTuple

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Entity, World

_NO_BLOCKED = frozenset[str]()  # no bridge is destroyed until combat (NX-124)


class Run(NamedTuple):
    """A truck's start: where it loads, how many units, and the road route to its destination."""

    source: str
    cargo: int
    route: list[str]


def friendly(rules: Rules, side: Side, node: str) -> bool:
    return rules.supply.start_owner.get(node) == side


def _route(rules: Rules, a: str, b: str) -> list[str] | None:
    return shortest_path(rules.roads, a, b, blocked=_NO_BLOCKED)


def _length(rules: Rules, route: list[str]) -> float:
    """Metres along a node route."""
    return sum(rules.roads.edge(a, b).length_m for a, b in pairwise(route))


def _nearest(rules: Rules, start: str, candidates: list[str]) -> tuple[str, list[str]] | None:
    """The candidate with the shortest road route from `start` (ties by node id), and that route."""
    best: tuple[float, str, list[str]] | None = None
    for node in sorted(candidates):
        route = _route(rules, start, node)
        if route is None:
            continue
        length = _length(rules, route)
        if best is None or length < best[0]:  # sorted ids: the first of a tie is the lowest id
            best = (length, node, route)
    return None if best is None else (best[1], best[2])


def plan_run(world: World, rules: Rules, side: Side, dest: str) -> Run | None:
    """A cargo truck of `side` sent to `dest` (GAMEPLAY §5 Q-GP-24; None: no road route).

    A friendly `dest` that can hold stock gets cargo from the friendly node (never `dest`) with
    stock above its starvation floor that is nearest `dest` by road (route metres, ties by node
    id): `min(truck_cargo, surplus)`. With no such node the side's rear source loads a full
    `truck_cargo`. Any other `dest` (neutral, enemy, infinite or unable to hold stock) is a
    capture run: it loads nothing and spawns at the rear source.
    """
    sup = rules.supply
    rear = sup.rear[side]
    if friendly(rules, side, dest) and sup.max_stock.get(dest, 0) > 0:
        sources = [
            n for n in sup.max_stock
            if n != dest and friendly(rules, side, n) and _surplus(world, rules, n) > 0
        ]  # fmt: skip
        best = _nearest(rules, dest, sources)  # roads are two-way, so dest -> source measures it
        if best is not None:
            source = best[0]
            route = _route(rules, source, dest)
            cargo = min(sup.truck_cargo, _surplus(world, rules, source))
            return None if route is None else Run(source, cargo, route)
        cargo = sup.truck_cargo
    else:
        cargo = 0
    route = _route(rules, rear, dest)
    return None if route is None else Run(rear, cargo, route)


def _surplus(world: World, rules: Rules, node: str) -> int:
    return world.stock.get(node, 0) - rules.supply.starve_floor[node]


def load(world: World, run: Run) -> None:
    """Debit the source for the cargo; a SANCTUARY (not in `stock`) is infinite."""
    if run.source in world.stock:
        world.stock[run.source] -= run.cargo


def logistics(world: World, out: list[Event]) -> None:
    """A truck standing at the end of its path unloads, or drives on (GAMEPLAY §5, Q-SIM-50).

    Paused (SC-11): nothing unloads. At a friendly node it moves `unload_rate x world_dt` units
    into the node's stock per tick, up to the node's maximum; when the node is full it keeps the
    rest, parked. At a node no longer friendly it drives to the nearest friendly base (a node with
    a stock maximum) with room, else to the nearest friendly base, else stays put. The truck is
    never retired here (GP-5 retire is NX-324). A stop ends when the cargo is gone, the node is
    full or the truck drives off; it emits one `SupplyDelivered` for the units unloaded, none for 0.
    """
    rules = world.rules
    if world.campaign.clock_paused or rules is None:
        return
    for e in world.entities():
        if e.cargo and not e.path and e.last_node is not None:
            if friendly(rules, e.side, e.last_node):
                _unload(world, rules, e, e.last_node, out)
            else:
                _divert(world, rules, e, e.last_node, out)


def _unload(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> None:
    sup = rules.supply
    room = sup.max_stock.get(node, 0) - world.stock.get(node, 0)
    if e.cargo is None or room <= 0:
        return
    whole, e.unload_milli = divmod(e.unload_milli + sup.unload_milli, 1000)
    moved = min(whole, e.cargo, room)
    world.stock[node] = world.stock.get(node, 0) + moved
    e.cargo -= moved
    e.delivered += moved
    if e.cargo == 0:
        e.unload_milli = 0
    if e.cargo == 0 or moved == room:
        _end_stop(world, e, node, out)


def _end_stop(world: World, e: Entity, node: str, out: list[Event]) -> None:
    """Report the stop's delivery (none for 0 units) and reset its count; unload_milli carries."""
    if e.delivered:
        out.append(
            SupplyDelivered.model_construct(
                kind="SupplyDelivered",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                node_id=node,
                amount=e.delivered,
                carrier_id=e.id,
                commander_id=e.commander_id,
            )
        )
    e.delivered = 0


def _divert(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> None:
    # shortcut: a truck with no reachable friendly base re-plans every tick; cache it once roads
    # or ownership can change (bridges NX-124, capture NX-125) if it shows in the tick budget.
    sup = rules.supply
    bases = [n for n, top in sup.max_stock.items() if top > 0 and friendly(rules, e.side, n)]
    with_room = [n for n in bases if world.stock.get(n, 0) < sup.max_stock[n]]
    best = _nearest(rules, node, with_room) or _nearest(rules, node, bases)
    if best is not None:
        _end_stop(world, e, node, out)  # a stop cut short by the node turning hostile
        e.path = list(best[1])
