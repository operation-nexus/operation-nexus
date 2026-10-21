"""Command handlers and the kernel's handler table (SIM-CORE SC-6, SC-7, SC-14; AGENTS.md rule 6a).

A handler applies one command in the `apply_commands` slot: it mutates the world and appends its
events. An invalid command becomes a `CommandRejected`, never an exception (SC-7); a missing
`World.rules` is a setup bug and raises.
"""

from collections.abc import Callable, Mapping

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.join import FollowTarget, NodeTarget
from nexus.contracts.gen.common.enums import OwnerKind, RejectReason, Side, UnitKind
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.reserve_queue_joined import ReserveQueueJoined
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Vec2, World

type Handler = Callable[[World, Command, list[Event]], None]

_COMMANDER: OwnerKind = "COMMANDER"
_COALITION: Side = "COALITION"  # every chat commander plays the coalition
_NO_BLOCKED = frozenset[str]()  # no bridge is destroyed until combat (NX-124)


def reject(world: World, command: Command, reason: RejectReason) -> CommandRejected:
    return CommandRejected.model_construct(
        kind="CommandRejected",
        tick=world.campaign.tick + 1,
        event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id,
        arrival_seq=command.arrival_seq,
        command_kind=command.kind,
        reason=reason,
        # Staff, system and advisor issuers map to None when their commands land.
        commander_id=command.issuer.commander_id,
    )


def join(world: World, command: Command, out: list[Event]) -> None:
    """JOIN (STATE-MACHINES §4.1, §4.4): spawn the commander's unit, or queue it (GP-3, Q-ALN-26).

    A valid JOIN queues while paused, at the cap, or behind a non-empty queue (strict FIFO, U-4);
    otherwise it spawns at once. Interim until NX-123: every unit spawns at the coalition's
    SANCTUARY with a FULL loadout and no stock is debited (forward deploy, GP-7, joins with
    logistics). No callsign reaches the kernel yet, so the unit's callsign is None. An aircraft
    spawns LANDED with full fuel and takes off in `movement` when it has a path (NX-368).
    """
    rules = _rules(world)
    plan = _plan(world, command, rules)
    if isinstance(plan, str):
        out.append(reject(world, command, plan))
    elif (
        world.campaign.clock_paused
        or world.reserve_queue
        or _viewer_units(world) >= rules.max_viewer_units
    ):
        _enqueue(world, command, rules, out)
    else:
        _spawn(world, command, *plan, rules, out)


def serve_reserve_queue(world: World, out: list[Event], *, drop: bool = False) -> None:
    """Pop the queue head while a viewer slot is free (§4.1 Reserve row); the caller skips paused
    ticks. Each entry is checked again as a fresh JOIN: one no longer valid is rejected with that
    check's reason and the next entry is served.

    `drop` (a running tombstoned tick, SC-8): the entries this pass would serve first are
    rejected with `INTERNAL_ERROR` unplanned, one per free slot and at least the head, so a queued
    JOIN that crashed the tick cannot crash its replay. At least one: the slot the crashed tick
    freed may have come from one of its commands, which the tombstone drops.
    shortcut: an invalid entry ahead of the crasher uses up a dropped place although serving would
    have skipped it; the crasher then fails a later tick, which drops it in turn (each crash
    counts toward the SC-8 limit). Fine while invalid-at-serve entries are rare (lost routes).
    """
    rules = _rules(world)
    free = rules.max_viewer_units - _viewer_units(world)
    if drop:
        free = max(free, 1)
    while world.reserve_queue and free > 0:
        command = world.reserve_queue.pop(0)
        plan = "INTERNAL_ERROR" if drop else _plan(world, command, rules)
        if isinstance(plan, str):
            out.append(reject(world, command, plan))
            if drop:
                free -= 1  # a dropped entry takes the place it would have been served in
            continue
        _spawn(world, command, *plan, rules, out)
        free -= 1


def _rules(world: World) -> Rules:
    if world.rules is None:
        raise ValueError("JOIN needs the world's rules")
    return world.rules


def _viewer_units(world: World) -> int:
    """Live COMMANDER-owned units; AUTO units are COMMANDER-owned too, so they count (Q-ALN-9).
    shortcut: a scan of every entity; keep a count if the SC-10 benchmark shows it in budget."""
    return sum(e.owner_kind == _COMMANDER for e in world.entities())


def _enqueue(world: World, command: Command, rules: Rules, out: list[Event]) -> None:
    """Append, or replace the commander's own entry in place (U-4: one each, position kept)."""
    commander = command.issuer.commander_id
    queue = world.reserve_queue
    position = next((i for i, c in enumerate(queue, 1) if c.issuer.commander_id == commander), 0)
    if position:
        queue[position - 1] = command
    elif len(queue) >= rules.reserve_queue_max:
        out.append(reject(world, command, "RESERVE_QUEUE_FULL"))
        return
    else:
        queue.append(command)
        position = len(queue)
    out.append(
        ReserveQueueJoined.model_construct(
            kind="ReserveQueueJoined",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            commander_id=commander,
            position=position,
        )
    )


def _spawn(
    world: World, command: Command, kind: UnitKind, path: list[str], rules: Rules, out: list[Event]
) -> None:
    node = rules.sanctuary
    unit = world.spawn(
        kind,
        _COALITION,
        _COMMANDER,
        Vec2(*rules.roads.pos[node]),
        commander_id=command.issuer.commander_id,
        hp=None,
    )
    unit.last_node, unit.path = node, list(path)
    if rules.domain[kind] == "AIR":  # on the ground, full; with a path it takes off (NX-368)
        unit.state, unit.fuel = "LANDED", rules.fuel_s[kind]
    out.append(
        UnitSpawned.model_construct(
            kind="UnitSpawned",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            entity_id=unit.id,
            unit_kind=kind,
            side=_COALITION,
            owner_kind=_COMMANDER,
            commander_id=unit.commander_id,
            callsign=None,
            node_id=node,
            loadout="FULL",
        )
    )


def _plan(
    world: World, command: Command, rules: Rules
) -> tuple[UnitKind, list[str]] | RejectReason:
    """The unit kind and path for a JOIN, or why it is rejected (checked in this order)."""
    commander = command.issuer.commander_id
    # shortcut: a scan of every entity per JOIN; index live units per commander if the SC-10
    # benchmark (500 viewer units) shows JOIN bursts over budget.
    live = sum(e.commander_id == commander for e in world.entities())
    if live and world.campaign.clock_paused:
        return "CAMPAIGN_PAUSED"  # only a JOIN with no live unit may queue while paused (SC-11)
    if command.hold and command.target is not None:
        return "INVALID_PAYLOAD"  # hold only with target null (CONTRACTS §5.2)
    kind = rules.role_kind.get(command.role)
    if kind is None:
        return "ROLE_UNKNOWN"  # NAVY until P3
    if live >= rules.max_live_per_commander:
        return "UNIT_IN_SORTIE"  # retarget or switch at base needs unit states (GP-1)
    if commander in world.respawn_left:
        return "RESPAWN_COOLDOWN"
    path = _path(command.target, kind, rules)
    return path if isinstance(path, str) else (kind, path)


def _path(
    target: NodeTarget | FollowTarget | None, kind: UnitKind, rules: Rules
) -> list[str] | RejectReason:
    """No target (hold, or auto-task once the board exists, NX-155): no path; Holding."""
    if target is None:
        return []
    if isinstance(target, FollowTarget):
        return "FOLLOW_TARGET_INVALID"  # every follow, until follow (Q-GP-31) lands
    if target.node_id not in rules.roads.pos:
        return "NODE_UNKNOWN"
    domain = rules.domain[kind]
    if domain == "AIR":
        return [target.node_id]
    if domain != "GROUND":
        return "NODE_INVALID_FOR_UNIT"  # SEA joins with the naval graph (P3); STATIC never moves
    route = shortest_path(rules.roads, rules.sanctuary, target.node_id, blocked=_NO_BLOCKED)
    return "NODE_INVALID_FOR_UNIT" if route is None else route


HANDLERS: Mapping[str, Handler] = {"JOIN": join}
