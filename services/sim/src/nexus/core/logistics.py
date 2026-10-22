"""Logistics: where a truck loads, where a unit forward-deploys, what a truck does on arrival and
how a unit at a base refuels, rearms and repairs (NX-123, NX-124; GAMEPLAY §5, GP-7, Q-GP-24,
Q-SIM-48..54). The rearm stop itself is `nexus.core.rearm`.

Stock is whole units in `World.stock` (finite nodes only; a SANCTUARY is infinite by rule). A truck
loads at its source when it spawns and unloads at its destination in the `logistics` system. All
counts are integers, so stock plus cargo is conserved exactly: a unit leaves a source's stock at
the same moment it becomes a truck's cargo, and leaves the cargo as it joins a node's stock. The
unload rate is counted in thousandths of a unit per tick (`Supply.unload_milli`), carried on the
truck as `Entity.unload_milli` so no fraction is ever lost to rounding. A unit at a base buys fuel,
rounds and hp in thousandths of stock and owes `Entity.rearm_milli`; a whole unit leaves the stock
as the debt reaches 1000, so every unit debited equals thousandths bought.

"Friendly" is the node's live owner (`World.owner`, which capture changes, NX-125). Routes avoid
no bridge until combat can destroy one (NX-124 part 3). A Disabled unit neither unloads nor
restocks and keeps its cargo until it is removed as a wreck (COMBAT CB-7, GP-5); a Disabled
facility is not a wreck and repairs. The `logistics`
system is deterministic: entities in id order, candidate nodes in id order, ties on distance by
node id.
"""

import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import NamedTuple

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core.defense import rebuild
from nexus.core.rearm import restock
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Entity, World, consumed, end_stop

_NO_BLOCKED = frozenset[str]()  # no bridge is destroyed until combat part 3 (NX-124)


class Run(NamedTuple):
    """A truck's start: where it loads, how many units, and the road route to its destination."""

    source: str
    cargo: int
    route: list[str]


def friendly(world: World, side: Side, node: str) -> bool:
    return world.owner.get(node) == side


def friendly_bases(world: World, rules: Rules, side: Side) -> list[str]:
    """The nodes `side` owns now that a unit can drive to as a base (anything but a BRIDGE)."""
    return [
        n for n, kind in rules.node_kind.items() if kind != "BRIDGE" and world.owner.get(n) == side
    ]


def nearest_base(e: Entity, rules: Rules, bases: tuple[str, ...]) -> tuple[float, str]:
    """(distance, id) of the nearest of `bases` by straight line, ties by node id."""
    return min(
        (math.hypot(x - e.pos.x, y - e.pos.y), n) for n in bases for x, y in [rules.roads.pos[n]]
    )


def go_home(world: World, rules: Rules, e: Entity) -> None:
    """Auto-RTB under the `standard` stance (COMBAT §5.6), called once, on the transition that
    triggers it: the unit reaches Mission-kill, or spends its last missile or bomb. It is not a
    standing state, so a later order is respected. An airborne aircraft goes RTB to the nearest
    landing base of its side (a LANDED one stays); a GROUND unit takes the road route to the
    nearest friendly base, from the node it is heading for or standing at, unless it is at one or
    heading for one. Anything else (a facility) does nothing.
    shortcut: with no reachable base a ground unit searches once and stays put."""
    domain = rules.domain[e.kind]
    e.follow_id = None  # sent home: it stops following (an escort claim is released by its pass)
    if e.order == "FOLLOW":
        e.order = None
    if domain == "AIR":
        bases = world.landing_bases(e.side)
        if bases and e.state in ("EN_ROUTE", "ON_STATION"):
            e.state, e.path, e.orbit = "RTB", [nearest_base(e, rules, bases)[1]], None
    elif domain == "GROUND":
        homes = friendly_bases(world, rules, e.side)
        start = e.path[0] if e.path else e.last_node
        if (e.path[-1] if e.path else e.last_node) in homes or not isinstance(start, str):
            return
        best = nearest(rules, start, homes)
        if best is not None:
            e.path = list(best[1])


def _route(rules: Rules, a: str, b: str) -> list[str] | None:
    return shortest_path(rules.roads, a, b, blocked=_NO_BLOCKED)


def _length(rules: Rules, route: list[str]) -> float:
    """Metres along a node route."""
    return sum(rules.roads.edge(a, b).length_m for a, b in pairwise(route))


def nearest(rules: Rules, start: str, candidates: list[str]) -> tuple[str, list[str]] | None:
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
    if friendly(world, side, dest) and sup.max_stock.get(dest, 0) > 0:
        sources = [
            n for n in sup.max_stock
            if n != dest and friendly(world, side, n) and _surplus(world, rules, n) > 0
        ]  # fmt: skip
        best = nearest(rules, dest, sources)  # roads are two-way, so dest -> source measures it
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


def deploy_pool(
    rules: Rules, kind: UnitKind, side: Side, owners: Mapping[str, str], surplus: Mapping[str, int]
) -> list[str]:
    """The nodes a `kind` of `side` may forward-deploy at (GP-7, Q-SIM-54), by node id: the
    theater's `spawns` nodes for the kind's domain that the side owns (an AIR one must also be a
    landing base: AIRBASE or SANCTUARY, Q-SIM-42), with finite stock (a key of `surplus`, the
    stock over the starvation floor) at least `forward_deploy_min_surplus` over its floor and at
    least the kind's `loadout_cost` over it, so the debit never takes a base below its floor. The
    one rule `plan_deploy` and the Director's `launch_base` share."""
    sup, domain = rules.supply, rules.domain[kind]
    need = max(sup.forward_deploy_min_surplus, sup.loadout_cost.get(kind, 0))
    return [
        n for n in sorted(sup.spawns.get(domain, ()))
        if n in surplus and owners.get(n) == side and surplus[n] >= need
        and (domain != "AIR" or n in rules.landing_nodes)
    ]  # fmt: skip


def nearest_by_air(rules: Rules, pool: Sequence[str], x: float, y: float) -> str | None:
    """The node of `pool` nearest the point by straight line, ties by node id (an aircraft's)."""
    near = min(
        ((math.hypot(px - x, py - y), n) for n in pool for px, py in [rules.roads.pos[n]]),
        default=None,
    )
    return None if near is None else near[1]


def plan_deploy(
    world: World, rules: Rules, side: Side, kind: UnitKind, target: str
) -> tuple[str, list[str]] | None:
    """Where a `kind` of `side` joining to node `target` forward-deploys, and its path (GP-7,
    Q-SIM-54; None: the sanctuary instead). Pure: nothing is debited (`pay_loadout`).

    Candidates are the theater's `spawns` nodes for the kind's domain that the side owns (an AIR
    one must also be a landing base of the side: AIRBASE or SANCTUARY, Q-SIM-42) and that hold
    stock at least `forward_deploy_min_surplus` above their starvation floor, and at least the
    kind's `loadout_cost` above it, so the debit never takes a base below its floor. Nearest
    to `target` by straight line for AIR (path `[target]`), by road route metres for GROUND (it
    needs a route; path is that route); ties by node id.
    """
    sup, domain = rules.supply, rules.domain[kind]
    if target == sup.rear[side]:
        return None  # a JOIN to its own sanctuary spawns there, free
    pool = deploy_pool(
        rules, kind, side, world.owner,
        {n: _surplus(world, rules, n) for n in world.stock if n in rules.supply.starve_floor},
    )  # fmt: skip
    if domain == "AIR":
        near = nearest_by_air(rules, pool, *rules.roads.pos[target])
        return None if near is None else (near, [target])
    best = nearest(rules, target, pool)  # roads are two-way, so target -> base measures it
    route = None if best is None else _route(rules, best[0], target)
    return None if best is None or route is None else (best[0], list(route))


def pay_loadout(world: World, rules: Rules, kind: UnitKind, node: str, out: list[Event]) -> None:
    """Debit a spawned unit's `loadout_cost` from `node` (a SANCTUARY is infinite: no debit) and
    emit `SupplyConsumed{SPAWN}`; nothing for a cost of 0."""
    cost = rules.supply.loadout_cost.get(kind, 0)
    if node in world.stock and cost:
        world.stock[node] -= cost
        out.append(consumed(world, node, cost, "SPAWN"))


def load(world: World, run: Run) -> None:
    """Debit the source for the cargo; a SANCTUARY (not in `stock`) is infinite."""
    if run.source in world.stock:
        world.stock[run.source] -= run.cargo


def logistics(world: World, out: list[Event]) -> None:
    """A truck standing at the end of its path unloads, or drives on (GAMEPLAY §5, Q-SIM-50); any
    other unit stopped at a base restocks (`rearm.restock`).

    Paused (SC-11): nothing unloads. At a friendly node it moves `unload_rate x world_dt` units
    into the node's stock per tick, up to the node's maximum; when the node is full it keeps the
    rest, parked. At a node no longer friendly it drives to the nearest friendly base (a node with
    a stock maximum) with room, else to the nearest friendly base, else stays put. The truck is
    never retired here (GP-5 retire is NX-324). A stop ends when the cargo is gone, the node is
    full or the truck drives off; it emits one `SupplyDelivered` for the units unloaded, none for 0.
    """
    rules = world.rules
    if world.frozen or rules is None:
        return
    for e in world.entities():
        wreck = e.damage_state == "DISABLED" and rules.domain[e.kind] != "STATIC"
        if wreck and e.delivered and e.last_node is not None:  # a wreck keeps its cargo (CB-7)
            end_stop(world, e, e.last_node, out)  # report a cut stop
        if not wreck and e.cargo and not e.path and e.last_node is not None:
            if friendly(world, e.side, e.last_node):
                _unload(world, rules, e, e.last_node, out)
            else:
                _divert(world, rules, e, e.last_node, out)
        else:
            restock(world, rules, e, out)


def _unload(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> None:
    sup = rules.supply
    room = sup.max_stock.get(node, 0) - world.stock.get(node, 0)
    # whole stock units the defenses of a finite-stock node can still take
    to_build = _defense_room(world, rules, node) if sup.max_stock.get(node, 0) > 0 else 0
    if e.cargo is None or (room <= 0 and to_build <= 0):
        return
    whole, e.unload_milli = divmod(e.unload_milli + sup.unload_milli, 1000)  # 1000: milli scale
    moved = min(whole, e.cargo, room if room > 0 else to_build)
    if room > 0:
        world.stock[node] = world.stock.get(node, 0) + moved
    else:  # full stock: each unit goes straight into the defenses (Q-SIM-71)
        e.defended += moved
    e.cargo -= moved
    e.delivered += moved
    rebuild(world, rules, node, moved, out)  # defense hp, same tick (Q-SIM-71)
    if e.cargo == 0:
        e.unload_milli = 0
    full_stock = sup.max_stock.get(node, 0) - world.stock.get(node, 0) <= 0
    if e.cargo == 0 or (full_stock and _defense_room(world, rules, node) <= 0):
        end_stop(world, e, node, out)


def _defense_room(world: World, rules: Rules, node: str) -> int:
    """Whole stock units the node's defenses can still take before they are full."""
    d = rules.defense
    if d is None or node not in world.defense_hp:
        return 0
    return -(-(d.max_hp[node] - world.defense_hp[node]) // d.repair_per_stock)


def _divert(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> None:
    # shortcut: a truck with no reachable friendly base re-plans every tick; cache it once roads
    # or ownership can change (bridges NX-124) if it shows in the tick budget.
    sup = rules.supply
    bases = [n for n, top in sup.max_stock.items() if top > 0 and friendly(world, e.side, n)]
    with_room = [n for n in bases if world.stock.get(n, 0) < sup.max_stock[n]]
    best = nearest(rules, node, with_room) or nearest(rules, node, bases)
    if best is not None:
        end_stop(world, e, node, out)  # a stop cut short by the node turning hostile
        e.path = list(best[1])
