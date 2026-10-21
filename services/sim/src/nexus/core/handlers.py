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
    """JOIN (STATE-MACHINES §4.1): spawn the commander's unit at the sanctuary and path it.

    Interim until NX-123: every unit spawns at the coalition's SANCTUARY with a FULL loadout and
    no stock is debited (forward deploy, GP-7, joins with logistics). The reserve queue and the
    cap (GP-3), and queueing while paused (Q-ALN-26), are NX-122 part 3: here a paused JOIN is
    rejected. No callsign reaches the kernel yet, so the unit's callsign is None.
    """
    if world.rules is None:
        raise ValueError("JOIN needs the world's rules")
    plan = _plan(world, command, world.rules)
    if isinstance(plan, str):
        out.append(reject(world, command, plan))
        return
    kind, path = plan
    node = world.rules.sanctuary
    unit = world.spawn(
        kind,
        _COALITION,
        _COMMANDER,
        Vec2(*world.rules.roads.pos[node]),
        commander_id=command.issuer.commander_id,
        hp=None,
    )
    unit.last_node, unit.path = node, list(path)
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
    if world.campaign.clock_paused:
        return "CAMPAIGN_PAUSED"
    if command.hold and command.target is not None:
        return "INVALID_PAYLOAD"  # hold only with target null (CONTRACTS §5.2)
    kind = rules.role_kind.get(command.role)
    if kind is None:
        return "ROLE_UNKNOWN"  # NAVY until P3
    commander = command.issuer.commander_id
    # shortcut: a scan of every entity per JOIN; index live units per commander if the SC-10
    # benchmark (500 viewer units) shows JOIN bursts over budget.
    live = sum(e.commander_id == commander for e in world.entities())
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
