"""Logistics: where a truck loads, where a unit forward-deploys, what a truck does on arrival and
how a landed aircraft refuels (NX-123; GAMEPLAY §5, GP-7, Q-GP-24, Q-SIM-48..54).

Stock is whole units in `World.stock` (finite nodes only; a SANCTUARY is infinite by rule). A truck
loads at its source when it spawns and unloads at its destination in the `logistics` system. All
counts are integers, so stock plus cargo is conserved exactly: a unit leaves a source's stock at
the same moment it becomes a truck's cargo, and leaves the cargo as it joins a node's stock. The
unload rate is counted in thousandths of a unit per tick (`Supply.unload_milli`), carried on the
truck as `Entity.unload_milli` so no fraction is ever lost to rounding. A refuelling aircraft buys
fuel at `Supply.rearm_milli` thousandths per tick and owes `Entity.rearm_milli`; a whole unit leaves
the stock as the debt reaches 1000, so every unit debited equals thousandths bought.

"Friendly" is the node's theater `start_owner` for now: ownership becomes world state with capture
(NX-125), which must replace `friendly`. Routes avoid no bridge until combat can destroy one
(NX-124). The `logistics` system is deterministic: entities in id order, candidate nodes in id
order, ties on distance by node id.
"""

import math
from itertools import pairwise
from typing import Literal, NamedTuple

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.rearm_stalled import RearmStalled
from nexus.contracts.gen.events.supply_consumed import SupplyConsumed
from nexus.contracts.gen.events.supply_delivered import SupplyDelivered
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Entity, World

_NO_BLOCKED = frozenset[str]()  # no bridge is destroyed until combat (NX-124)
_MILLI = 1000
_EPS = 1e-6  # float noise in a fuel-to-milli conversion; below any real milli-unit of stock


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
    need = max(sup.forward_deploy_min_surplus, sup.loadout_cost.get(kind, 0))
    pool = [
        n for n in sorted(sup.spawns.get(domain, ()))
        if n in world.stock and friendly(rules, side, n) and _surplus(world, rules, n) >= need
        and (domain != "AIR" or n in rules.landing_bases[side])
    ]  # fmt: skip
    if domain == "AIR":
        tx, ty = rules.roads.pos[target]
        near = min(
            ((math.hypot(x - tx, y - ty), n) for n in pool for x, y in [rules.roads.pos[n]]),
            default=None,
        )
        return None if near is None else (near[1], [target])
    best = _nearest(rules, target, pool)  # roads are two-way, so target -> base measures it
    route = None if best is None else _route(rules, best[0], target)
    return None if best is None or route is None else (best[0], list(route))


def pay_loadout(world: World, rules: Rules, kind: UnitKind, node: str, out: list[Event]) -> None:
    """Debit a spawned unit's `loadout_cost` from `node` (a SANCTUARY is infinite: no debit) and
    emit `SupplyConsumed{SPAWN}`; nothing for a cost of 0."""
    cost = rules.supply.loadout_cost.get(kind, 0)
    if node in world.stock and cost:
        world.stock[node] -= cost
        out.append(_consumed(world, node, cost, "SPAWN"))


def _consumed(
    world: World, node: str, amount: int, cause: Literal["SPAWN", "REARM"]
) -> SupplyConsumed:
    return SupplyConsumed.model_construct(
        kind="SupplyConsumed",
        tick=world.campaign.tick + 1,
        event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id,
        node_id=node,
        amount=amount,
        cause=cause,
    )


def load(world: World, run: Run) -> None:
    """Debit the source for the cargo; a SANCTUARY (not in `stock`) is infinite."""
    if run.source in world.stock:
        world.stock[run.source] -= run.cargo


def logistics(world: World, out: list[Event]) -> None:
    """A truck standing at the end of its path unloads, or drives on (GAMEPLAY §5, Q-SIM-50); a
    landed aircraft refuels (`_refuel`).

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
        elif e.state is not None:
            _refuel(world, rules, e, out)


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


def _refuel(world: World, rules: Rules, e: Entity, out: list[Event]) -> None:
    """A LANDED aircraft with no path at a landing base of its side buys fuel (Q-SIM-51/53).

    Per running tick it buys up to `rearm_rate x WORLD_DT` stock of fuel, where one stock buys
    `fuel_s / loadout_cost` world seconds, and only the missing fuel is paid for: a full refill
    costs `loadout_cost`. A finite base debits whole units as the thousandths owed reach 1000 and
    sells nothing it has not got; below its starvation floor it fills only up to
    `starved_loadout.fuel_frac` of `fuel_s`. A SANCTUARY is infinite: the same rate, no debit.
    A kind with no `loadout_cost` (or no fuel) is skipped. At 0 stock with fuel still wanted it
    emits `RearmStalled` once; a stop ends when the aircraft is filled, stalled or leaves, with
    one `SupplyConsumed{REARM}` for the units debited, none for 0. Ground units have no fuel or
    ammo modeled yet, and guns wait for munitions (NX-124).
    """
    sup, node, fuel = rules.supply, e.last_node, e.fuel
    if fuel is None:
        raise ValueError(f"aircraft {e.id} has no fuel")
    cost = sup.loadout_cost.get(e.kind, 0)
    finite = node in world.stock
    # Aircraft land only at their side's AIRBASE or SANCTUARY (Q-SIM-42), so nowhere else refuels.
    if node is None or not (
        cost and e.state == "LANDED" and not e.path and node in rules.landing_bases[e.side]
    ):
        return _end_refuel(world, e, out)
    full = rules.fuel_s[e.kind]
    starved = finite and world.stock[node] < sup.starve_floor[node]
    cap = sup.starved_fuel_frac * full if starved else full
    if fuel >= cap:
        return _end_refuel(world, e, out)
    # shortcut: the stop's node is `last_node` when it ends; an aircraft that takes off and reaches
    # another node in one tick would report there (nodes are km apart, a tick moves < 200 m).
    need = math.ceil((cap - fuel) * cost * _MILLI / full - _EPS)
    if need <= 0:  # what is missing is float noise: full, not a stall
        e.fuel = cap
        return _end_refuel(world, e, out)
    pay = min(sup.rearm_milli, need)
    if finite:
        pay = min(pay, world.stock[node] * _MILLI - e.rearm_milli)
        if pay <= 0:
            return _stall(world, e, node, out)
        whole, e.rearm_milli = divmod(e.rearm_milli + pay, _MILLI)
        world.stock[node] -= whole
        e.rearm_spent += whole
    e.stalled = False
    e.fuel = cap if pay == need else fuel + pay * full / (cost * _MILLI)
    if e.fuel >= cap:
        _end_refuel(world, e, out)


def _end_refuel(world: World, e: Entity, out: list[Event]) -> None:
    """Report the stop's spend (none for 0 units) and reset the stop; `rearm_milli` carries."""
    if e.rearm_spent and e.last_node is not None:
        out.append(_consumed(world, e.last_node, e.rearm_spent, "REARM"))
    e.rearm_spent, e.stalled = 0, False


def _stall(world: World, e: Entity, node: str, out: list[Event]) -> None:
    was_stalled = e.stalled
    _end_refuel(world, e, out)
    e.stalled = True
    if not was_stalled:
        out.append(
            RearmStalled.model_construct(
                kind="RearmStalled",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                entity_id=e.id,
                node_id=node,
            )
        )
