"""The kernel step and its fixed system order (SIM-CORE SC-1, SC-6, SC-7, SC-13, SC-14).

`step` is SC-1's `step(state, commands, rng)` with the RNG inside the world (`world.rng`, Q-SIM-32).
It mutates the world in place and returns the tick's events; `state_hash` cadence is the runtime's.
"""

import math
from collections.abc import Callable, Mapping, Sequence

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.core.fog import sense
from nexus.core.handlers import HANDLERS as HANDLERS
from nexus.core.handlers import Handler as Handler
from nexus.core.handlers import reject, serve_reserve_queue
from nexus.core.rules import Rules
from nexus.core.world import Entity, UnitState, Vec2, World

TICK_DT = 0.1  # game seconds per tick (SC-2)
_STOPPED = Vec2(0.0, 0.0)
_GROUND = "GROUND"
_AIR = "AIR"
_LANDED: UnitState = "LANDED"
_EN_ROUTE: UnitState = "EN_ROUTE"
_ON_STATION: UnitState = "ON_STATION"
_RTB: UnitState = "RTB"

type System = Callable[[World, Sequence[Command], Mapping[str, Handler], list[Event]], None]


def apply_commands(
    world: World, commands: Sequence[Command], handlers: Mapping[str, Handler], out: list[Event]
) -> None:
    """Apply in `(target_tick, arrival_seq)` order (SC-6); an unhandled kind is rejected (SC-7)."""
    for command in sorted(commands, key=lambda c: (c.target_tick, c.arrival_seq)):
        handler = handlers.get(command.kind)
        if handler is None:
            out.append(reject(world, command, "INTERNAL_ERROR"))
        else:
            handler(world, command, out)


def director(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Director and AI orders: NX-155."""


def movement(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Each unit with a path moves `WORLD_DT` world seconds along it, in id order (SC-2, SC-4).

    AIR flies straight at `speed_mps`; GROUND follows road edges at `speed_mps x speed_mult`
    (GAMEPLAY §5). Time left after reaching a waypoint carries on to the next one in the same tick.
    Aircraft also take off, burn fuel, check bingo, orbit, land and crash here (`_fly`, NX-368).
    Paused (SC-11): nothing moves or burns. A path is followed as given; JOIN assigns one (NX-122).
    """
    if world.campaign.clock_paused:
        return
    rules, lost = world.rules, []
    for e in world.entities():
        if rules is None:  # nothing may move: only parked, stateless or LANDED units
            if e.path or e.state not in (None, _LANDED):
                raise ValueError(f"entity {e.id} moves but the world has no rules")
            e.vel = _STOPPED
        elif rules.domain[e.kind] == _AIR:
            if not _fly(e, rules):
                lost.append(e)
        elif e.path:
            _move(e, rules)
        else:
            e.vel = _STOPPED
    for e in lost:  # removed after the loop, in id order
        _crash(world, e, out)


def _fly(e: Entity, rules: Rules) -> bool:
    """One tick of an aircraft (STATE-MACHINES §4.1, NX-368); False when it ran out of fuel.

    A LANDED aircraft with no path stays put. Otherwise, unless RTB, the bingo check first, so a
    LANDED aircraft ordered off at bingo, or ordered to the base it stands on, stays landed
    without burning. Then it burns `WORLD_DT` of fuel (a constant burn per world second, a whole
    tick even on the takeoff and landing ticks) and flies its path at top speed, or orbits when it
    has none. A path ending at a landing base of its side ends LANDED; any other ends ON_STATION,
    orbiting the point it reached. Only then is fuel 0 a crash: landing on that tick wins.
    """
    if e.state is None:
        raise ValueError(f"aircraft {e.id} has no state")
    landed = e.state == _LANDED
    if landed and not e.path:
        e.vel = _STOPPED
        return True
    if e.state != _RTB:
        _check_bingo(e, rules)
    if landed and e.path == [e.last_node] and _on_own_base(e, rules):
        e.state, e.path, e.vel = _LANDED, [], _STOPPED  # its own base, or bingo: no takeoff
        return True
    e.fuel = max(0.0, _fuel(e) - rules.world_dt)
    if not e.path:
        if e.orbit is None:
            _start_orbit(e, rules, None)
        else:
            _orbit(e, e.orbit, rules)
    else:
        if e.state != _RTB:
            e.state = _EN_ROUTE  # takeoff, or a new order leaves the station
        e.orbit = None
        leg = _move(e, rules)
        if not e.path:
            if _on_own_base(e, rules):
                e.state, e.vel = _LANDED, _STOPPED
            else:
                _start_orbit(e, rules, leg)
    return e.state == _LANDED or e.fuel > 0.0  # else a flameout (owner, 2026-10-21)


def _on_own_base(e: Entity, rules: Rules) -> bool:
    """On a landing base of its side: an AIRBASE or SANCTUARY node (Q-SIM-38)."""
    node = e.last_node
    if node is None or node not in rules.landing_bases[e.side]:
        return False
    return e.pos == Vec2(*rules.roads.pos[node])


def _crash(world: World, e: Entity, out: list[Event]) -> None:
    """Out of fuel: the aircraft is lost like a shoot-down and its owner's respawn delay starts
    (owner, 2026-10-21). The wreck and the crew-survival roll join with combat (NX-124)."""
    world.remove(e.id)
    if e.commander_id is not None:
        world.record_loss(e.commander_id)
    out.append(
        UnitDestroyed.model_construct(
            kind="UnitDestroyed",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            entity_id=e.id,
            killer_id=None,
            assist_ids=[],
            side=e.side,
        )
    )


def _fuel(e: Entity) -> float:
    if e.fuel is None:
        raise ValueError(f"aircraft {e.id} has no fuel")
    return e.fuel


def _check_bingo(e: Entity, rules: Rules) -> None:
    """Bingo: fuel <= the flight time at top speed to the nearest base it may land at (ties by
    node id) + `bingo_reserve_frac` x full fuel. Then it heads there, RTB. No base: it flies on."""
    bases = rules.landing_bases[e.side]
    if not bases:
        return
    dist, base = min(
        (math.hypot(x - e.pos.x, y - e.pos.y), n) for n in bases for x, y in [rules.roads.pos[n]]
    )
    reserve = rules.bingo_reserve_frac * rules.fuel_s[e.kind]
    if _fuel(e) <= dist / rules.speed_mps[e.kind] + reserve:
        e.state, e.path, e.orbit = _RTB, [base], None


def _orbit_radius(e: Entity, rules: Rules) -> tuple[float, float]:
    """(min speed, radius): one lap at `min_speed_mps` takes `air.orbit_period_s`."""
    speed = rules.min_speed_mps[e.kind]
    return speed, speed * rules.orbit_period_s / math.tau


def _start_orbit(e: Entity, rules: Rules, heading: tuple[float, float] | None) -> None:
    """Circle through the point reached, entered along `heading` (east when the last leg had no
    length), the angle increasing: clockwise on the map, where y grows south. The centre is
    clamped so the circle stays in bounds. shortcut: when the clamp moves it (a point within one
    radius of the map edge), the next tick snaps onto the circle; no strait-1 node is that close
    to an edge. Upgrade to a curved entry if Vec2 waypoints near the edge become common."""
    hx, hy = heading or (1.0, 0.0)
    speed, r = _orbit_radius(e, rules)
    w, h = rules.bounds_m
    cx = min(max(e.pos.x - hy * r, r), w - r)
    cy = min(max(e.pos.y + hx * r, r), h - r)
    e.state, e.orbit, e.vel = _ON_STATION, Vec2(cx, cy), Vec2(hx * speed, hy * speed)


def _orbit(e: Entity, centre: Vec2, rules: Rules) -> None:
    speed, r = _orbit_radius(e, rules)
    turn = math.tau * rules.world_dt / rules.orbit_period_s
    theta = math.atan2(e.pos.y - centre.y, e.pos.x - centre.x) + turn
    cos, sin = math.cos(theta), math.sin(theta)
    e.pos = Vec2(centre.x + r * cos, centre.y + r * sin)
    e.vel = Vec2(-speed * sin, speed * cos)


def _waypoint(e: Entity, rules: Rules) -> tuple[Vec2, float]:
    """The next waypoint and the speed to it in m/s (world)."""
    wp, speed = e.path[0], rules.speed_mps[e.kind]
    if rules.domain[e.kind] == _GROUND:
        if not isinstance(wp, str) or e.last_node is None:
            raise ValueError(f"ground entity {e.id} must move node to node on the road graph")
        speed *= rules.roads.edge(e.last_node, wp).speed_mult
    if isinstance(wp, str):
        x, y = rules.roads.pos[wp]
        return Vec2(x, y), speed
    return wp, speed


def _move(e: Entity, rules: Rules) -> tuple[float, float] | None:
    """Returns the unit heading of the last leg finished this tick, if any had a length."""
    left = rules.world_dt  # world seconds still to spend this tick
    leg = None
    while e.path:
        if e.path[0] == e.last_node and e.pos == Vec2(*rules.roads.pos[e.last_node]):
            e.path.pop(0)  # already there: a route from `shortest_path` starts at its own node
            continue
        target, speed = _waypoint(e, rules)
        dx, dy = target.x - e.pos.x, target.y - e.pos.y
        dist, reach = math.hypot(dx, dy), speed * left
        if dist > reach:
            if reach > 0.0:
                k = reach / dist
                e.pos = Vec2(e.pos.x + dx * k, e.pos.y + dy * k)
            break
        if dist > 0.0:  # so speed > 0
            left -= dist / speed
            leg = (dx / dist, dy / dist)
        _arrive(e, target)  # snap exactly: no drift at nodes
    e.vel = _velocity(e, rules)
    return leg


def _arrive(e: Entity, target: Vec2) -> None:
    e.pos = target
    wp = e.path.pop(0)
    if isinstance(wp, str):
        e.last_node = wp


def _velocity(e: Entity, rules: Rules) -> Vec2:
    """Heading to the next waypoint at the current speed; zero once the path is done."""
    if not e.path:
        return _STOPPED
    target, speed = _waypoint(e, rules)
    dx, dy = target.x - e.pos.x, target.y - e.pos.y
    dist = math.hypot(dx, dy)
    return Vec2(dx / dist * speed, dy / dist * speed) if dist and speed > 0.0 else _STOPPED


def sensing(world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]) -> None:
    """Tier 2 tracks and last-known tracks on due ticks (FOW-5, FOW-6a): `nexus.core.fog`."""
    sense(world)


def combat(world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]) -> None:
    """Combat resolution: NX-124."""


def logistics_capture(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Logistics and capture: NX-123 (logistics), NX-125 (capture)."""


def objectives(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Objectives: NX-126."""


def lifecycle(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Respawn delays count down one running tick (GP-2, SC-11), then the reserve queue fills free
    viewer slots FIFO (GP-3); despawn and retire: NX-324. Nothing happens while paused.

    In commander-id order; an entry reaching 0 is deleted, so the commander may JOIN next tick.
    A unit served from the queue starts moving next tick (`movement` ran before this slot).
    """
    _lifecycle(world, out, drop=False)


def _lifecycle_tombstoned(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """`lifecycle` on a tombstoned tick (SC-8): the queue entries it would serve are dropped."""
    _lifecycle(world, out, drop=True)


def _lifecycle(world: World, out: list[Event], *, drop: bool) -> None:
    if world.campaign.clock_paused:
        return
    world.respawn_left = {k: left - 1 for k, left in sorted(world.respawn_left.items()) if left > 1}
    if world.reserve_queue:
        serve_reserve_queue(world, out, drop=drop)


SYSTEMS: tuple[tuple[str, System], ...] = (
    ("apply_commands", apply_commands),
    ("director", director),
    ("movement", movement),
    ("sensing", sensing),
    ("combat", combat),
    ("logistics_capture", logistics_capture),
    ("objectives", objectives),
    ("lifecycle", lifecycle),
)


def step(
    world: World,
    commands: Sequence[Command],
    handlers: Mapping[str, Handler] = HANDLERS,
    dropped: Sequence[Command] | None = None,
) -> list[Event]:
    """Compute tick `world.campaign.tick + 1`, then advance the tick by 1; returns its events.

    `commands` are exactly those whose `target_tick` is the tick being computed (the runtime
    guarantees it); any other `target_tick` is a caller bug and raises ValueError. `dropped` are
    the commands of a tombstoned tick (SC-8): none is applied; each becomes a
    `CommandRejected{INTERNAL_ERROR}` in arrival_seq order, ahead of the systems' events. Any
    `dropped`, even empty, marks the tick tombstoned: `lifecycle` then drops the reserve-queue
    entries it would serve, also as `CommandRejected{INTERNAL_ERROR}`, in queue order.
    """
    tick = world.campaign.tick + 1
    tombstoned = dropped is not None
    dropped = dropped or ()
    wrong = [c.arrival_seq for c in (*commands, *dropped) if c.target_tick != tick]
    if wrong:
        raise ValueError(f"commands {wrong} do not target tick {tick}")
    in_order = sorted(dropped, key=lambda c: c.arrival_seq)
    events: list[Event] = [reject(world, c, "INTERNAL_ERROR") for c in in_order]
    for _, system in SYSTEMS:
        if tombstoned and system is lifecycle:
            system = _lifecycle_tombstoned
        system(world, commands, handlers, events)
    world.campaign.tick = tick
    return events
