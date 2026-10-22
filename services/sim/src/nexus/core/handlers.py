"""Command handlers and the kernel's handler table (SIM-CORE SC-6, SC-7, SC-14; AGENTS.md rule 6a).

A handler applies one command in the `apply_commands` slot: it mutates the world and appends its
events. An invalid command becomes a `CommandRejected`, never an exception (SC-7); a missing
`World.rules` is a setup bug and raises.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.join import FollowTarget, JoinCommand, NodeTarget
from nexus.contracts.gen.commands.staff_campaign_end import StaffCampaignEndCommand
from nexus.contracts.gen.commands.staff_campaign_pause import StaffCampaignPauseCommand
from nexus.contracts.gen.commands.staff_campaign_resume import StaffCampaignResumeCommand
from nexus.contracts.gen.commands.sys_set_callsign import SysSetCallsignCommand
from nexus.contracts.gen.common.enums import OwnerKind, RejectReason, Side, UnitKind
from nexus.contracts.gen.events.callsign_changed import CallsignChanged
from nexus.contracts.gen.events.campaign_clock_paused import CampaignClockPaused
from nexus.contracts.gen.events.campaign_clock_resumed import CampaignClockResumed
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.reserve_queue_joined import ReserveQueueJoined
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.campaign import end_campaign
from nexus.core.logistics import Run, load, pay_loadout, plan_deploy, plan_run
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.tasking import claim, crosses_ring, joinable_jobs
from nexus.core.world import Job, Order, Vec2, World

type Handler = Callable[[World, Command, list[Event]], None]


class _Plan(NamedTuple):
    """A valid JOIN: the unit kind, where it loads and spawns (`source`), the `cargo` it carries
    (None for a kind that carries none) and its road path or flight waypoints."""

    kind: UnitKind
    source: str
    cargo: int | None
    path: Sequence[str | Vec2]
    job: int | None = None  # the Tasking Board job a parameterless JOIN takes (Q-GP-23)


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
        # Staff, system and advisor issuers have no commander.
        commander_id=command.issuer.commander_id if isinstance(command, JoinCommand) else None,
    )


def join(world: World, command: Command, out: list[Event]) -> None:
    """JOIN (STATE-MACHINES §4.1, §4.4): spawn the commander's unit, or queue it (GP-3, Q-ALN-26).

    A valid JOIN queues while paused, at the cap, or behind a non-empty queue (strict FIFO, U-4);
    otherwise it spawns at once. A cargo truck spawns at its source and loads there (NX-123,
    `nexus.core.logistics.plan_run`, GP-7). Any other unit with a node target forward-deploys
    (`plan_deploy`) and pays its loadout from that base; else it spawns at the coalition's
    SANCTUARY, free. Always with a FULL loadout (Q-SIM-53). The unit takes the commander's callsign
    when identity has set one, else None (`set_callsign`, NX-370). An aircraft spawns LANDED with
    full fuel and takes off in `movement` when it has a path (NX-368).
    """
    if not isinstance(command, JoinCommand):
        raise TypeError(f"JOIN handler got {command.kind}")
    rules = _rules(world)
    plan = _plan(world, command, rules)
    if isinstance(plan, str):
        out.append(reject(world, command, plan))
    elif (
        world.campaign.clock_paused
        or world.reserve_queue
        or world.viewer_units() >= rules.max_viewer_units
    ):
        _enqueue(world, command, rules, out)
    else:
        _spawn(world, command, plan, rules, out)


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
    free = rules.max_viewer_units - world.viewer_units()
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
        _spawn(world, command, plan, rules, out)
        free -= 1


def _rules(world: World) -> Rules:
    if world.rules is None:
        raise ValueError("JOIN needs the world's rules")
    return world.rules


def _enqueue(world: World, command: JoinCommand, rules: Rules, out: list[Event]) -> None:
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


def _spawn(world: World, command: JoinCommand, plan: _Plan, rules: Rules, out: list[Event]) -> None:
    kind, node, cargo, path, job = plan
    unit = world.spawn(
        kind,
        _COALITION,
        _COMMANDER,
        Vec2(*rules.roads.pos[node]),
        commander_id=command.issuer.commander_id,
        callsign=world.callsigns.get(command.issuer.commander_id),
        hp=None,
    )
    unit.last_node, unit.path, unit.cargo = node, list(path), cargo
    unit.order = _order(command)
    if cargo:  # the plan and the spawn are one step of one tick: the stock is as planned
        load(world, Run(node, cargo, []))
    pay_loadout(world, rules, kind, node, out)
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
            callsign=unit.callsign,
            node_id=node,
            loadout="FULL",
        )
    )
    if job is not None:  # a parameterless JOIN takes its job at once (Q-GP-23)
        claim(world, unit, world.boards[_COALITION][job], out)


def _order(command: JoinCommand) -> Order | None:
    """The explicit order a JOIN gives (GAMEPLAY §1b): `hold` waits, a node goes there; neither
    (auto-tasking) leaves the board in charge."""
    return "HOLD" if command.hold else "GOTO" if command.target is not None else None


def _plan(world: World, command: JoinCommand, rules: Rules) -> _Plan | RejectReason:
    """The plan for a JOIN, or why it is rejected (checked in this order). Pure: no stock moves."""
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
    if command.target is None and not command.hold:
        for job in joinable_jobs(world, kind):
            plan = _route_job(world, job, kind, rules)
            if isinstance(plan, str):
                continue
            start = Vec2(*rules.roads.pos[plan.source])
            if rules.domain[kind] == "AIR" and crosses_ring(world, rules, _COALITION, start, job):
                continue  # route danger applies to a new aircraft as to a board assignment (TB-2)
            return plan._replace(job=job.id)
    return _route(world, target=command.target, kind=kind, rules=rules)


def _route_job(world: World, job: Job, kind: UnitKind, rules: Rules) -> _Plan | RejectReason:
    """The plan for a unit taking `job`: its node as an ordinary JOIN target, or, for a blob
    (scout), straight from the sanctuary to the blob's cell. A rejection means no plan."""
    if job.node is not None:
        return _route(world, target=NodeTarget(node_id=job.node), kind=kind, rules=rules)
    if job.pos is None or rules.domain[kind] != "AIR":
        return "NODE_INVALID_FOR_UNIT"
    return _Plan(kind, rules.sanctuary, None, [job.pos])


def _route(
    world: World, *, target: NodeTarget | FollowTarget | None, kind: UnitKind, rules: Rules
) -> _Plan | RejectReason:
    """No target (hold, or auto-task once the board exists, NX-155): no path; Holding at the
    sanctuary, a truck empty. A truck to a node plans its load and route (`plan_run`); any other
    unit forward-deploys when a base qualifies (`plan_deploy`), else leaves the sanctuary."""
    cargo = 0 if kind in rules.supply.carriers else None
    if target is None:
        return _Plan(kind, rules.sanctuary, cargo, [])
    if isinstance(target, FollowTarget):
        return "FOLLOW_TARGET_INVALID"  # every follow, until follow (Q-GP-31) lands
    if target.node_id not in rules.roads.pos:
        return "NODE_UNKNOWN"
    domain = rules.domain[kind]
    if domain not in ("AIR", "GROUND"):
        return "NODE_INVALID_FOR_UNIT"  # SEA joins with the naval graph (P3); STATIC never moves
    if cargo is not None:
        run = plan_run(world, rules, _COALITION, target.node_id)
        return "NODE_INVALID_FOR_UNIT" if run is None else _Plan(kind, *run)
    deploy = plan_deploy(world, rules, _COALITION, kind, target.node_id)
    if deploy is not None:
        return _Plan(kind, deploy[0], None, deploy[1])
    if domain == "AIR":
        return _Plan(kind, rules.sanctuary, None, [target.node_id])
    route = shortest_path(rules.roads, rules.sanctuary, target.node_id, blocked=_NO_BLOCKED)
    return "NODE_INVALID_FOR_UNIT" if route is None else _Plan(kind, rules.sanctuary, None, route)


def set_callsign(world: World, command: Command, out: list[Event]) -> None:
    """SYS_SET_CALLSIGN (CONTRACTS §5.2, Q-SIM-39): store the commander's callsign, copy it onto
    the commander's live units and emit `CallsignChanged`. The schema checks the callsign's
    pattern. Allowed while paused (Q-ALN-36). `COMMANDER_UNKNOWN` is never emitted: the kernel
    keeps no commander registry, so identity owns that check (a JOIN does not check it either).
    The map grows with each commander; FORGET (later) removes the entry.
    """
    if not isinstance(command, SysSetCallsignCommand):
        raise TypeError(f"SYS_SET_CALLSIGN handler got {command.kind}")
    world.callsigns[command.commander_id] = command.callsign
    for e in world.entities():
        if e.commander_id == command.commander_id:
            e.callsign = command.callsign
    out.append(
        CallsignChanged.model_construct(
            kind="CallsignChanged",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            commander_id=command.commander_id,
            callsign=command.callsign,
            callsign_kind=command.callsign_kind,
        )
    )


def staff_campaign_pause(world: World, command: Command, out: list[Event]) -> None:
    """STAFF_CAMPAIGN_PAUSE (STATE-MACHINES §4.4, Q-ALN-3, Q-ALN-31): stop the campaign clock and
    keep the reason. Checked in this order: a `sub_reason` with a category other than STAFF is
    `INVALID_PAYLOAD`; a STAFF command with a blank note is `REASON_REQUIRED` (SYSTEM may send
    none); a pause while paused is `ALREADY_PAUSED`. Who may pause is enforced outside the kernel
    (ADMIN-RBAC). The note is for the audit trail and is not in the event.
    """
    if not isinstance(command, StaffCampaignPauseCommand):
        raise TypeError(f"STAFF_CAMPAIGN_PAUSE handler got {command.kind}")
    c = world.campaign
    if command.sub_reason is not None and command.reason_category != "STAFF":
        out.append(reject(world, command, "INVALID_PAYLOAD"))
    elif command.source == "STAFF" and not (command.note and command.note.strip()):
        out.append(reject(world, command, "REASON_REQUIRED"))
    elif c.clock_paused:
        out.append(reject(world, command, "ALREADY_PAUSED"))
    else:
        c.clock_paused, c.pause_reason, c.pause_sub_reason = (
            True, command.reason_category, command.sub_reason,
        )  # fmt: skip
        out.append(
            CampaignClockPaused.model_construct(
                kind="CampaignClockPaused",
                tick=c.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=c.id,
                reason=command.reason_category,
                sub_reason=command.sub_reason,
            )
        )


def staff_campaign_resume(world: World, command: Command, out: list[Event]) -> None:
    """STAFF_CAMPAIGN_RESUME: restart the clock; `NOT_PAUSED` when it runs. The event carries the
    reason and sub-reason of the pause it ends. Free viewer slots fill in this tick's lifecycle."""
    if not isinstance(command, StaffCampaignResumeCommand):
        raise TypeError(f"STAFF_CAMPAIGN_RESUME handler got {command.kind}")
    c = world.campaign
    if c.pause_reason is None:
        out.append(reject(world, command, "NOT_PAUSED"))
        return
    out.append(
        CampaignClockResumed.model_construct(
            kind="CampaignClockResumed",
            tick=c.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=c.id,
            reason=c.pause_reason,
            sub_reason=c.pause_sub_reason,
        )
    )
    c.clock_paused, c.pause_reason, c.pause_sub_reason = False, None, None


def staff_campaign_end(world: World, command: Command, out: list[Event]) -> None:
    """STAFF_CAMPAIGN_END (Running or Paused): `CampaignEnded{ABORTED}` (`nexus.core.campaign`)."""
    if not isinstance(command, StaffCampaignEndCommand):
        raise TypeError(f"STAFF_CAMPAIGN_END handler got {command.kind}")
    end_campaign(world, "ABORTED", out)


HANDLERS: Mapping[str, Handler] = {
    "JOIN": join,
    "SYS_SET_CALLSIGN": set_callsign,
    "STAFF_CAMPAIGN_PAUSE": staff_campaign_pause,
    "STAFF_CAMPAIGN_RESUME": staff_campaign_resume,
    "STAFF_CAMPAIGN_END": staff_campaign_end,
}
