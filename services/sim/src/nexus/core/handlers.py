"""Command handlers and the kernel's handler table (SIM-CORE SC-6, SC-7, SC-14; AGENTS.md rule 6a).

A handler applies one command in the `apply_commands` slot: it mutates the world and appends its
events. An invalid command becomes a `CommandRejected`, never an exception (SC-7); a missing
`World.rules` is a setup bug and raises.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import NamedTuple

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.join import FollowTarget, JoinCommand, NodeTarget
from nexus.contracts.gen.commands.rebase import RebaseCommand
from nexus.contracts.gen.commands.staff_campaign_end import StaffCampaignEndCommand
from nexus.contracts.gen.commands.staff_campaign_pause import StaffCampaignPauseCommand
from nexus.contracts.gen.commands.staff_campaign_resume import StaffCampaignResumeCommand
from nexus.contracts.gen.commands.sys_queue_timeout import SysQueueTimeoutCommand
from nexus.contracts.gen.commands.sys_set_callsign import SysSetCallsignCommand
from nexus.contracts.gen.common.enums import (
    OwnerKind,
    QueueLeaveReason,
    RejectReason,
    Side,
    UnitKind,
)
from nexus.contracts.gen.events.callsign_changed import CallsignChanged
from nexus.contracts.gen.events.campaign_clock_paused import CampaignClockPaused
from nexus.contracts.gen.events.campaign_clock_resumed import CampaignClockResumed
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.reserve_queue_joined import ReserveQueueJoined
from nexus.contracts.gen.events.reserve_queue_left import ReserveQueueLeft
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.bridges import blocked
from nexus.core.campaign import end_campaign
from nexus.core.follow import can_follow
from nexus.core.logistics import (
    Run,
    friendly_bases,
    load,
    nearest,
    pay_loadout,
    plan_deploy,
    plan_run,
)
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.tasking import claim, crosses_ring, joinable_jobs, reaches
from nexus.core.world import Entity, Job, Order, Vec2, World, end_stop, release_claim

type Handler = Callable[[World, Command, list[Event]], None]


class _Plan(NamedTuple):
    """A valid JOIN: the unit kind, where it loads and spawns (`source`), the `cargo` it carries
    (None for a kind that carries none) and its road path or flight waypoints."""

    kind: UnitKind
    source: str
    cargo: int | None
    path: Sequence[str | Vec2]
    job: int | None = None  # the Tasking Board job a parameterless JOIN takes (Q-GP-23)
    follow: int | None = None  # the unit a follow JOIN keeps station on (Q-GP-31)


_COMMANDER: OwnerKind = "COMMANDER"
_COALITION: Side = "COALITION"  # every chat commander plays the coalition


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
        commander_id=(
            command.issuer.commander_id
            if isinstance(command, JoinCommand | RebaseCommand)
            else None
        ),
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


def rebase(world: World, command: Command, out: list[Event]) -> None:
    """REBASE (GAMEPLAY §3, Q-SIM-90): move the commander's live unit to a friendly base.

    Rejected, in this order: `CAMPAIGN_PAUSED` (Q-ALN-2), `NO_ACTIVE_UNIT` (no live, non-Disabled
    unit), `NODE_UNKNOWN`, `NODE_NOT_FRIENDLY`, `NODE_INVALID_FOR_UNIT` (an aircraft needs a landing
    base, a ground unit a base it has a road route to), `OUT_OF_REACH` (an aircraft that cannot fly
    there with its bingo reserve, `tasking.reaches`). An accepted rebase is an explicit order
    (TB-7): it releases the unit's board job, ends a follow, cuts a truck's unloading stop, and sets
    the order `slots.rebase_order` (HOLD, its only value, Q-CFG-16), so the unit takes no board job
    on the way or at the base until its commander's next order. Arrival, landing, refuelling and
    rearming are the ordinary `movement` and `logistics` systems.
    """
    if not isinstance(command, RebaseCommand):
        raise TypeError(f"REBASE handler got {command.kind}")
    rules = _rules(world)
    if world.campaign.clock_paused:
        out.append(reject(world, command, "CAMPAIGN_PAUSED"))  # Q-ALN-2: no change while paused
        return
    unit = next(
        (
            e for e in world.entities()
            if e.commander_id == command.issuer.commander_id and e.damage_state != "DISABLED"
        ),
        None,
    )  # fmt: skip
    if unit is None:
        out.append(reject(world, command, "NO_ACTIVE_UNIT"))
        return
    path = _rebase_path(world, rules, unit, command.node_id)
    if isinstance(path, str):
        out.append(reject(world, command, path))
        return
    if unit.job_id is not None:
        release_claim(world, world.boards[unit.side][unit.job_id], unit.id, out)
    if unit.delivered and unit.last_node is not None:
        end_stop(world, unit, unit.last_node, out)  # leaving cuts the unloading stop
    unit.path, unit.order, unit.follow_id = path, rules.rebase_order, None
    unit.held_since = unit.order_node = None  # a new order ends a GOTO and its hold (Q-SIM-110)


def _rebase_path(
    world: World, rules: Rules, unit: Entity, node: str
) -> list[str | Vec2] | RejectReason:
    """The path of a valid rebase, or why it is rejected (see `rebase`). Pure."""
    if node not in rules.roads.pos:
        return "NODE_UNKNOWN"
    if world.owner.get(node) != _COALITION:
        return "NODE_NOT_FRIENDLY"
    domain = rules.domain[unit.kind]
    if domain == "AIR":
        bases = world.landing_bases(_COALITION)
        if node not in bases:
            return "NODE_INVALID_FOR_UNIT"
        fuel = unit.fuel if unit.fuel is not None else 0.0
        return [node] if reaches(rules, unit, node, bases, fuel) else "OUT_OF_REACH"
    if domain != "GROUND" or node not in friendly_bases(world, rules, _COALITION):
        return "NODE_INVALID_FOR_UNIT"
    start = unit.path[0] if unit.path else unit.last_node  # a unit mid-road finishes its leg
    if not isinstance(start, str):
        return "NODE_INVALID_FOR_UNIT"
    if not unit.path and unit.pos == Vec2(*rules.roads.pos[node]):
        return []  # already there; a unit stopped on the road is routed to the node it left
    best = nearest(world, rules, start, [node])
    return "NODE_INVALID_FOR_UNIT" if best is None else list(best[1])


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
        _left(
            world,
            command.issuer.commander_id,
            "REJECTED" if isinstance(plan, str) else "SLOT_FREED",
            out,
        )
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
        _left(world, commander, "REPLACED", out)  # Joined below re-adds it: Joined/Left stay 1:1
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


def _left(world: World, commander: str, reason: QueueLeaveReason, out: list[Event]) -> None:
    """The one place an entry's exit becomes an event (NX-371): every exit emits exactly one."""
    out.append(
        ReserveQueueLeft.model_construct(
            kind="ReserveQueueLeft",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            commander_id=commander,
            reason=reason,
        )
    )


def queue_timeout(world: World, command: Command, out: list[Event]) -> None:
    """SYS_QUEUE_TIMEOUT (GAMEPLAY RQ-1, NX-371): remove the commander's queue entry and emit
    `ReserveQueueLeft{TIMEOUT}`. The runtime decides the entry is idle (wall-clock time) and logs
    this command, so replays reproduce it. Allowed while paused. A commander no longer queued
    (served or replaced meanwhile) is ignored: the command raced the queue, nothing to report.
    """
    if not isinstance(command, SysQueueTimeoutCommand):
        raise TypeError(f"SYS_QUEUE_TIMEOUT handler got {command.kind}")
    queue = world.reserve_queue
    for i, entry in enumerate(queue):
        if entry.issuer.commander_id == command.commander_id:
            del queue[i]
            _left(world, command.commander_id, "TIMEOUT", out)
            return


def _spawn(world: World, command: JoinCommand, plan: _Plan, rules: Rules, out: list[Event]) -> None:
    kind, node, cargo, path, job, follow = plan
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
    unit.order, unit.follow_id = _order(command), follow
    if unit.order == "GOTO" and isinstance(command.target, NodeTarget):
        unit.order_node = command.target.node_id  # where an armed unit holds (Q-SIM-110)
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
    """The explicit order a JOIN gives (GAMEPLAY §1b): `hold` waits, a node goes there, a unit is
    followed; none (auto-tasking) leaves the board in charge."""
    if isinstance(command.target, FollowTarget):
        return "FOLLOW"
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
    if isinstance(command.target, FollowTarget) and not can_follow(
        world, rules, kind, command.target.follow_entity_id, None
    ):
        return "FOLLOW_TARGET_INVALID"  # unknown, other side, Disabled, or no station to keep
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
        return _follow_plan(world, rules, kind, target.follow_entity_id, cargo)
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
    route = shortest_path(rules.roads, rules.sanctuary, target.node_id, blocked=blocked(world))
    return "NODE_INVALID_FOR_UNIT" if route is None else _Plan(kind, rules.sanctuary, None, route)


def _follow_plan(
    world: World, rules: Rules, kind: UnitKind, leader_id: int, cargo: int | None
) -> _Plan | RejectReason:
    """A follower spawns at the sanctuary and steers to its station (`nexus.core.follow`); a truck
    spawns at the source `plan_run` picks for the leader's destination and loads there (the
    `!join logi` source rule, Q-GP-31), so it can unload at the column's destination."""
    if cargo is None:
        return _Plan(kind, rules.sanctuary, None, [], follow=leader_id)
    leader = world.get(leader_id)
    dest = leader.path[-1] if leader.path else leader.last_node
    run = plan_run(world, rules, _COALITION, dest) if isinstance(dest, str) else None
    if run is None:
        return "NODE_INVALID_FOR_UNIT"
    return _Plan(kind, run.source, run.cargo, [], follow=leader_id)


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
    "REBASE": rebase,
    "SYS_SET_CALLSIGN": set_callsign,
    "SYS_QUEUE_TIMEOUT": queue_timeout,
    "STAFF_CAMPAIGN_PAUSE": staff_campaign_pause,
    "STAFF_CAMPAIGN_RESUME": staff_campaign_resume,
    "STAFF_CAMPAIGN_END": staff_campaign_end,
}
