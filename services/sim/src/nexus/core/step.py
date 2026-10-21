"""The kernel step and its fixed system order (SIM-CORE SC-1, SC-6, SC-7, SC-13, SC-14).

`step` is SC-1's `step(state, commands, rng)` with the RNG inside the world (`world.rng`, Q-SIM-32).
It mutates the world in place and returns the tick's events; `state_hash` cadence is the runtime's.
"""

import math
from collections.abc import Callable, Mapping, Sequence

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.core.rules import Rules
from nexus.core.world import Entity, Vec2, World

TICK_DT = 0.1  # game seconds per tick (SC-2)
_STOPPED = Vec2(0.0, 0.0)
_GROUND = "GROUND"

type Handler = Callable[[World, Command, list[Event]], None]
type System = Callable[[World, Sequence[Command], Mapping[str, Handler], list[Event]], None]

# Filled one command kind at a time (AGENTS.md rule 6a). JOIN needs the theater (NX-120, GAMEPLAY).
HANDLERS: Mapping[str, Handler] = {}


def apply_commands(
    world: World, commands: Sequence[Command], handlers: Mapping[str, Handler], out: list[Event]
) -> None:
    """Apply in `(target_tick, arrival_seq)` order (SC-6); an unhandled kind is rejected (SC-7)."""
    for command in sorted(commands, key=lambda c: (c.target_tick, c.arrival_seq)):
        handler = handlers.get(command.kind)
        if handler is None:
            out.append(_internal_error(world, command))
        else:
            handler(world, command, out)


def _internal_error(world: World, command: Command) -> CommandRejected:
    return CommandRejected.model_construct(
        kind="CommandRejected",
        tick=world.campaign.tick + 1,
        event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id,
        arrival_seq=command.arrival_seq,
        command_kind=command.kind,
        reason="INTERNAL_ERROR",
        # Staff, system and advisor issuers map to None when their commands land.
        commander_id=command.issuer.commander_id,
    )


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
    Paused (SC-11): nothing moves. A path is followed as given; assigning one is NX-122 / NX-126.
    """
    if world.campaign.clock_paused:
        return
    for e in world.entities():
        if not e.path:
            e.vel = _STOPPED
            continue
        if world.rules is None:
            raise ValueError(f"entity {e.id} has a path but the world has no rules")
        _move(e, world.rules)


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


def _move(e: Entity, rules: Rules) -> None:
    left = rules.world_dt  # world seconds still to spend this tick
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
        _arrive(e, target)  # snap exactly: no drift at nodes
    e.vel = _velocity(e, rules)


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
    """Sensing and fog: NX-150."""


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
    """Despawn, respawn, retire: NX-122 (respawn), NX-324 (idle retire)."""


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
    dropped: Sequence[Command] = (),
) -> list[Event]:
    """Compute tick `world.campaign.tick + 1`, then advance the tick by 1; returns its events.

    `commands` are exactly those whose `target_tick` is the tick being computed (the runtime
    guarantees it); any other `target_tick` is a caller bug and raises ValueError. `dropped` are
    the commands of a tombstoned tick (SC-8): none is applied; each becomes a
    `CommandRejected{INTERNAL_ERROR}` in arrival_seq order, ahead of the systems' events.
    """
    tick = world.campaign.tick + 1
    wrong = [c.arrival_seq for c in (*commands, *dropped) if c.target_tick != tick]
    if wrong:
        raise ValueError(f"commands {wrong} do not target tick {tick}")
    in_order = sorted(dropped, key=lambda c: c.arrival_seq)
    events: list[Event] = [_internal_error(world, c) for c in in_order]
    for _, system in SYSTEMS:
        system(world, commands, handlers, events)
    world.campaign.tick = tick
    return events
