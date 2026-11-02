"""Logistics: where a truck loads, where a unit forward-deploys, what a truck does on arrival and
how a unit at a base refuels, rearms and repairs (NX-123, NX-124; GAMEPLAY §5, GP-7, Q-GP-24,
Q-SIM-48..54). The rearm stop itself is `nexus.core.rearm`.

Stock is whole units in `World.stock` (finite nodes only); a SANCTUARY is infinite, or a whole-unit
pool in `World.pool` when its side is not in unlimited mode (`nexus.core.economy`, NX-412). A truck
loads at its source when it spawns and unloads at its destination in the `logistics` system. All
counts are integers, so stock plus cargo is conserved exactly: a unit leaves a source's stock at
the same moment it becomes a truck's cargo, and leaves the cargo as it joins a node's stock. The
unload rate is counted in thousandths of a unit per tick (`Supply.unload_milli`), carried on the
truck as `Entity.unload_milli` so no fraction is ever lost to rounding. A unit at a base buys fuel,
rounds and hp in thousandths of stock and owes `Entity.rearm_milli`; a whole unit leaves the stock
as the debt reaches 1000, so every unit debited equals thousandths bought.
A truck that unloads stock into a base with an open shortfall episode of its side is
recorded as one of the episode's haulers (`Shortfall.haulers`; ECONOMY EC-6a, NX-436).

"Friendly" is the node's live owner (`World.owner`, which capture changes, NX-125). Every route
passes `bridges.blocked`, so none crosses a down bridge (NX-373); a supply run's also enters no
node the other side holds (`supply_route`, Q-SIM-122; a supply truck's divert too, Q-SIM-126),
while a unit going home, escaping or fleeing a node the other side took may drive through any
node. A Disabled unit neither unloads nor restocks and keeps its cargo until it is removed as a
wreck (COMBAT CB-7, GP-5); a Disabled facility is not a wreck and repairs. The `logistics` system
is deterministic: entities in id order, candidate nodes in id order, ties on distance by node id.
"""

import math
from bisect import insort
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import NamedTuple

from nexus.contracts.gen.common.enums import NodeOwner, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core.bridges import blocked, enemy_held, held_by_other, quickest
from nexus.core.defense import rebuild
from nexus.core.economy import pool_side, source_stock
from nexus.core.rearm import restock, station
from nexus.core.roads import shortest_path
from nexus.core.rules import OperationRules, Rules
from nexus.core.world import Entity, World, at_stop, consumed, end_stop, on_node


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
        start = road_start(rules, e)  # a bridge stop's bank, else as before
        end = e.path[-1] if e.path else e.last_node
        if (end in homes and not at_stop(rules, e)) or start is None:
            return  # home already; one parked at a bridge stop drives back to its bank
        best = nearest(world, rules, start, homes)
        if best is not None:
            e.path = list(best[1])


def road_start(rules: Rules, e: Entity) -> str | None:
    """The node a ground unit's new road route starts from: the node it heads for (it finishes its
    leg), or the bank it left when it heads for or stands at a bridge's repair stop, so it drives
    back along the road (NX-373 part 2); None off the road graph."""
    start = e.path[0] if e.path else e.last_node
    if start in rules.roads.spans:
        start = e.last_node
    return start if isinstance(start, str) else None


def _route(
    world: World, rules: Rules, a: str, b: str, avoid: frozenset[str] = frozenset()
) -> list[str] | None:
    return shortest_path(rules.roads, a, b, blocked=blocked(world), avoid=avoid)


def supply_route(
    world: World, rules: Rules, side: Side, a: str, b: str, held: frozenset[str] | None = None
) -> list[str] | None:
    """A supply run's road route from `a` to `b` (Q-SIM-122): it enters no node the other side
    holds (`bridges.enemy_held`; neutral ground is passable); `a` and `b` themselves are allowed.
    `held`: the caller's pass-wide `enemy_held` (NX-413), computed here when None."""
    return supply_path(rules, world.owner, blocked(world), side, a, b, held)


def supply_path(
    rules: Rules,
    owners: Mapping[str, NodeOwner],
    down: frozenset[str],
    side: Side,
    a: str,
    b: str,
    held: frozenset[str] | None = None,
) -> list[str] | None:
    """`supply_route` from public node state only (owners and down bridges, FOW-10), so the
    Director's view (`operations.fed_nodes`, NX-401) plans the same route the trucks drive."""
    avoid = (held_by_other(rules, owners, side) if held is None else held) - {b}
    return shortest_path(rules.roads, a, b, blocked=down, avoid=avoid)


def _length(rules: Rules, route: list[str]) -> float:
    """Metres along a node route."""
    return sum(rules.roads.edge(a, b).length_m for a, b in pairwise(route))


def nearest(
    world: World,
    rules: Rules,
    start: str,
    candidates: list[str],
    avoid: frozenset[str] = frozenset(),
) -> tuple[str, list[str]] | None:
    """The candidate with the shortest road route from `start` (ties by node id), and that route;
    no route enters a node of `avoid` (`start` exempt)."""
    best: tuple[float, str, list[str]] | None = None
    for node in sorted(candidates):
        route = _route(world, rules, start, node, avoid)
        if route is None:
            continue
        length = _length(rules, route)
        if best is None or length < best[0]:  # sorted ids: the first of a tie is the lowest id
            best = (length, node, route)
    return None if best is None else (best[1], best[2])


def approach(
    world: World, rules: Rules, start: str, bridge: str, *, avoid: frozenset[str]
) -> list[str] | None:
    """A ground unit's road path from the node `start` to `bridge`'s repair stop: the route to the
    quicker of its banks (`bridges.quickest`: route time, then metres, then node id; Q-SIM-129),
    then the bridge's id (`step._waypoint` drives it out to the stop); None with no route to
    either bank. The route enters no node of `avoid`, a bank included (`start` is exempt): a repair
    crew's is the pass-wide `bridges.enemy_held` of its side (Q-SIM-125, NX-413; neutral ground is
    passable), anyone else's empty."""
    route = quickest(rules, start, [*rules.roads.spans[bridge]], blocked(world), avoid)
    return None if route is None else [*route, bridge]


def plan_run(
    world: World,
    rules: Rules,
    side: Side,
    dest: str,
    *,
    around_enemy: bool = True,
    held: frozenset[str] | None = None,
) -> Run | None:
    """A cargo truck of `side` sent to `dest` (GAMEPLAY §5 Q-GP-24; None: no road route).

    A friendly `dest` that can hold stock gets cargo from the friendly node (never `dest`) with
    stock above what it keeps (`keeps`) that is nearest `dest` by road (route metres, ties by node
    id): `min(truck_cargo, spare)`. With no such node the side's rear source loads a full
    `truck_cargo` (at most its pool when the side is not in unlimited mode, NX-412: an empty pool
    loads nothing). Such a supply run's routes enter no node the other side holds
    (`supply_route`, Q-SIM-122), unless `around_enemy` is False (a follower's source pick, which
    drives on its leader's road, GAMEPLAY §1b Q-GP-31). Any other `dest` (neutral, enemy,
    infinite or unable to hold stock) is a capture run: it loads nothing, spawns at the rear
    source and may cross any node. `held`: the caller's pass-wide `enemy_held` (NX-413),
    computed here when None.
    """
    sup = rules.supply
    rear = sup.rear[side]
    avoid: frozenset[str] = frozenset()
    if friendly(world, side, dest) and sup.max_stock.get(dest, 0) > 0:
        keep = keeps(world, rules, side, dest)
        sources = [
            n for n in sup.max_stock
            if n != dest and friendly(world, side, n) and world.stock.get(n, 0) > keep[n]
        ]  # fmt: skip
        if around_enemy:  # every source and `dest` are held: none is avoided
            avoid = enemy_held(world, rules, side) if held is None else held
        best = nearest(world, rules, dest, sources, avoid)  # two-way roads: dest -> source
        if best is not None:
            source = best[0]
            route = _route(world, rules, source, dest, avoid)
            cargo = min(sup.truck_cargo, world.stock.get(source, 0) - keep[source])
            return None if route is None else Run(source, cargo, route)
        pool = source_stock(world, rear)  # a limited source loads what its pool holds (NX-412)
        cargo = sup.truck_cargo if pool is None else min(sup.truck_cargo, pool)
    else:
        cargo = 0
    route = _route(world, rules, rear, dest, avoid)
    return None if route is None else Run(rear, cargo, route)


def facility_damage(world: World, rules: Rules, side: Side) -> dict[str, tuple[int, int]]:
    """Base -> (missing hp, max hp) over the side's facilities there (the side's own state)."""
    cr = rules.combat
    totals: dict[str, list[int]] = {}
    for e in world.entities():
        if cr is not None and e.side == side and e.base_id is not None:
            top = cr.units[e.kind].hp
            t = totals.setdefault(e.base_id, [0, 0])
            t[0] += top - e.hp
            t[1] += top
    return {n: (t[0], t[1]) for n, t in totals.items()}


def keeps(world: World, rules: Rules, side: Side, dest: str) -> Mapping[str, int]:
    """What each source keeps on a run to the finite-stock `dest` (Q-GP-24, Q-SIM-102): on a
    stocking run (`dest` at or above its starvation floor, below its stock target, with no damaged
    facility of the side) its own stock target, so stock flows forward from the rear and never
    back and forth between bases below target; on any other run its starvation floor."""
    sup, target = rules.supply, stock_targets(world, rules)
    stock = world.stock.get(dest, 0)
    if not sup.starve_floor[dest] <= stock < target[dest]:
        return sup.starve_floor
    missing_hp = facility_damage(world, rules, side).get(dest, (0, 0))[0]
    return sup.starve_floor if missing_hp else target


def stock_targets(world: World, rules: Rules) -> Mapping[str, int]:
    """Each finite-stock node's forward stock target (Q-SIM-100): `Supply.stock_target`, raised at
    a staging base to its starvation floor plus, for every operation staged there, the cost of
    its units that spawn there (THREAT-DIRECTOR FS-3, Q-TD-38, NX-416): the template slots whose
    kind's domain the base hosts, at the operation's cost per unit (`launch._staged_shares`), at
    most the node's maximum. The rules' own map when nothing is staged."""
    sup, dr = rules.supply, rules.director
    staged = [s for side in sorted(world.director) for s in world.director[side].staged]
    if not staged or dr is None:
        return sup.stock_target
    by_id = {o.id: o for o in dr.operations}
    need: dict[str, int] = {}
    for s in staged:
        need.setdefault(s.base, sup.starve_floor.get(s.base, 0))
        if (op := by_id.get(s.op)) is not None:
            need[s.base] += _base_share(rules, op, s.base)
    out = dict(sup.stock_target)
    for node, lift in need.items():
        if node in out:
            out[node] = max(out[node], min(sup.max_stock[node], lift))
    return out


def _base_share(rules: Rules, op: OperationRules, base: str) -> int:
    """The cost of `op`'s template slots whose kind spawns at `base` (a `spawns` node for its
    domain), at `op.cost` per unit over all its slots, floored as `launch` scales a cost."""
    # An upper bound of the launch-time base share: reused idle units lower the actual draw, and a
    # CAPTURE operation with an each-convoy job (more wheres than one per job) would differ.
    kinds = [j.unit_kinds[n % len(j.unit_kinds)] for j in op.jobs for n in range(j.slots)]
    there = sum(base in rules.supply.spawns.get(rules.domain[k], ()) for k in kinds)
    return op.cost * there // max(1, len(kinds))


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
    Q-SIM-54; None: the sanctuary instead). Pure: nothing is debited (`pay_spawn`).

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
    best = nearest(world, rules, target, pool)  # roads are two-way, so target -> base measures it
    route = None if best is None else _route(world, rules, best[0], target)
    return None if best is None or route is None else (best[0], list(route))


def pay_spawn(world: World, node: str, cost: int, out: list[Event]) -> None:
    """Debit a spawn's `cost` at `node` (ECONOMY EC-13): a base's stock, or a limited side's
    source pool; an infinite source (unlimited mode) pays nothing. `SupplyConsumed{SPAWN}` at the
    node, none for 0. The caller has checked the node can pay."""
    if cost <= 0:
        return
    if node in world.stock:
        world.stock[node] -= cost
    elif (side := pool_side(world, node)) is not None:
        world.pool[side] -= cost
    else:
        return
    out.append(consumed(world, node, cost, "SPAWN"))


def load(world: World, run: Run) -> None:
    """Debit the source for the cargo: a base's stock, or a limited side's source pool
    (`nexus.core.economy`, NX-412); a SANCTUARY in unlimited mode is infinite."""
    if run.source in world.stock:
        world.stock[run.source] -= run.cargo
    elif (side := pool_side(world, run.source)) is not None:
        world.pool[side] -= run.cargo


def logistics(world: World, out: list[Event]) -> None:
    """A truck standing at the end of its path unloads, or drives on (GAMEPLAY §5, Q-SIM-50); any
    other unit stopped at a base restocks (`rearm.restock`). Any unit stopped at a friendly base
    (`rearm.station`: landed or parked) makes it its home base (`Entity.home_base`, NX-412 part 2).

    Paused (SC-11): nothing unloads. At a friendly node it moves `unload_rate x world_dt` units
    into the node's stock per tick, up to the node's maximum; when the node is full it keeps the
    rest, parked. At a node no longer friendly it drives to the nearest friendly base (a node with
    a stock maximum) with room, else to the nearest friendly base, else stays put and tries again
    next tick; a supply truck's road there avoids enemy-held nodes (`_supply_avoid`, Q-SIM-126).
    The truck is never retired here (GP-5 retire is NX-324). A stop ends when the cargo is gone,
    the node is full or the truck drives off; it emits one `SupplyDelivered` for the units
    unloaded, none for 0.
    """
    rules = world.rules
    if world.frozen or rules is None:
        return
    for e in world.entities():
        if (home := station(world, rules, e)) is not None:
            e.home_base = home  # landed or parked at a friendly base: its home (ECONOMY EC-5)
        wreck = e.damage_state == "DISABLED" and rules.domain[e.kind] != "STATIC"
        if wreck and e.delivered and e.last_node is not None:  # a wreck keeps its cargo (CB-7)
            end_stop(world, e, e.last_node, out)  # report a cut stop
        if not wreck and e.cargo and not e.path and e.last_node is not None and on_node(rules, e):
            if friendly(world, e.side, e.last_node):
                _unload(world, rules, e, e.last_node, out)
            else:
                _divert(world, rules, e, e.last_node, out)
        else:
            restock(world, rules, e, out)


def accepts(world: World, rules: Rules, node: str) -> bool:
    """Whether a truck can unload at `node` now: it has stock room, or it has finite stock and
    defenses a unit still rebuilds (Q-SIM-71). `_unload` and the board's idle pool
    (`tasking._unloading`, Q-SIM-130) share it."""
    top = rules.supply.max_stock.get(node, 0)
    return top > world.stock.get(node, 0) or (top > 0 and _defense_room(world, rules, node) > 0)


def _unload(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> None:
    if e.cargo is None or not accepts(world, rules, node):
        end_stop(world, e, node, out)  # full before its turn (another truck filled it, NX-486)
        return
    sup = rules.supply
    room = sup.max_stock.get(node, 0) - world.stock.get(node, 0)
    # whole stock units the defenses of a finite-stock node can still take
    to_build = _defense_room(world, rules, node) if sup.max_stock.get(node, 0) > 0 else 0
    whole, e.unload_milli = divmod(e.unload_milli + sup.unload_milli, 1000)  # 1000: milli scale
    moved = min(whole, e.cargo, room if room > 0 else to_build)
    if room > 0:
        world.stock[node] = world.stock.get(node, 0) + moved
        episode = world.shortfall[e.side].get(node)  # a hauler of its payoff (EC-6a, NX-436)
        if moved and episode is not None and e.id not in episode.haulers:
            insort(episode.haulers, e.id)
    else:  # full stock: each unit goes straight into the defenses (Q-SIM-71)
        e.defended += moved
    e.cargo -= moved
    e.delivered += moved
    rebuild(world, rules, node, moved, out)  # defense hp, same tick (Q-SIM-71)
    if e.cargo == 0:
        e.unload_milli = 0
    if e.cargo == 0 or not accepts(world, rules, node):
        end_stop(world, e, node, out)


def _defense_room(world: World, rules: Rules, node: str) -> int:
    """Whole stock units the node's defenses can still take before they are full."""
    d = rules.defense
    if d is None or node not in world.defense_hp:
        return 0
    return -(-(d.max_hp[node] - world.defense_hp[node]) // d.repair_per_stock)


def _divert(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> None:
    # shortcut: a truck with no reachable friendly base re-plans every tick; cache it once roads
    # or ownership can change (bridges, NX-373) if it shows in the tick budget.
    sup = rules.supply
    bases = [n for n, top in sup.max_stock.items() if top > 0 and friendly(world, e.side, n)]
    with_room = [n for n in bases if world.stock.get(n, 0) < sup.max_stock[n]]
    avoid = _supply_avoid(world, rules, e, node)
    best = nearest(world, rules, node, with_room, avoid) or nearest(
        world, rules, node, bases, avoid
    )
    if best is not None:  # none: it holds with its cargo and tries again next tick (Q-SIM-126)
        end_stop(world, e, node, out)  # a stop cut short by the node turning hostile
        e.path = list(best[1])


def _supply_avoid(world: World, rules: Rules, e: Entity, node: str) -> frozenset[str]:
    """What a loaded truck diverting from `node` must not enter (Q-SIM-126): the nodes the other
    side holds, so it never drives its cargo through enemy ground, also once a held RESUPPLY
    claimant's lease has lapsed and it has no job; a truck standing on a node the other side holds
    flees it by any road."""
    held = enemy_held(world, rules, e.side)
    return held if node not in held else frozenset()
