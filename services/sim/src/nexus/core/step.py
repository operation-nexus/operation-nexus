"""The kernel step and its fixed system order (SIM-CORE SC-1, SC-6, SC-7, SC-13, SC-14).

`step` is SC-1's `step(state, commands, rng)` with the RNG inside the world (`world.rng`, Q-SIM-32).
It mutates the world in place and returns the tick's events; `state_hash` cadence is the runtime's.
"""

from collections.abc import Callable, Mapping, Sequence

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.core.world import World

TICK_DT = 0.1  # game seconds per tick (SC-2)

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
            out.append(
                CommandRejected.model_construct(
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
            )
        else:
            handler(world, command, out)


def director(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Director and AI orders: NX-155."""


def movement(
    world: World, c: Sequence[Command], h: Mapping[str, Handler], out: list[Event]
) -> None:
    """Movement: NX-121."""


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
    world: World, commands: Sequence[Command], handlers: Mapping[str, Handler] = HANDLERS
) -> list[Event]:
    """Compute tick `world.campaign.tick + 1`, then advance the tick by 1; returns its events.

    `commands` are exactly those whose `target_tick` is the tick being computed (the runtime
    guarantees it); any other `target_tick` is a caller bug and raises ValueError.
    """
    tick = world.campaign.tick + 1
    wrong = [c.arrival_seq for c in commands if c.target_tick != tick]
    if wrong:
        raise ValueError(f"commands {wrong} do not target tick {tick}")
    events: list[Event] = []
    for _, system in SYSTEMS:
        system(world, commands, handlers, events)
    world.campaign.tick = tick
    return events
