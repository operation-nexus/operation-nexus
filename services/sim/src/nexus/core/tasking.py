"""The Tasking Board: jobs, leases, assignment and outcomes for both sides (GAMEPLAY §1b, TB-1 to
TB-10; STATE-MACHINES §4.1 Holding; SIM-CORE SC-5, SC-11, SC-13; NX-374, Q-SIM-73).

`World.boards[side]` holds a side's live jobs (`nexus.core.world.Job`); a job that reaches DONE,
FAILED or EXPIRED leaves the board in that pass and its event is the durable record (TB-10). `run`
is the `director` slot (SC-13), before `movement`. Every `tasking.reeval_every_ticks` running ticks
(TB-6: the pass at running tick `now = running_ticks + 1` is due when it divides `now`), and never
while frozen (SC-11), for each side in COALITION, ENEMY order:

1. **Order completion.** A GOTO order ends when its unit has no path, no cargo and no capture bar of
   its side filling where it stands (it arrived, its unloading stop or capture run ended); a HOLD
   never ends. An order keeps the board off the unit (TB-7).
2. **Settle.** A claim is released (`JobReleased`) when its unit is lost, Disabled, sent home (RTB)
   or given an explicit order (a human order wins, TB-7). A unit with a path, or arrived, has made
   progress: its claim becomes ACTIVE and its lease clock restarts; with none for
   `tasking.claim_lease_s` the claim is released and the job is OPEN again (TB-1). Then the outcome:
   - RESUPPLY: DONE when a claimant stands at the node with its cargo gone (the delivery stop
     ended); FAILED when the side lost the node. DEFEND: FAILED likewise; DONE when a claimant
     stands at the node and the threat is gone (no bar of the other side, and the side tracks no
     enemy GROUND unit within `tasking.defend_radius_m`)). STRIKE: DONE when the node's
     defense hp is 0 or the side owns it. SCOUT: DONE when a claimant has arrived at the blob's
     cell (or the node). ASSIST_OBJECTIVE and an objective's STRIKE also end with the objective
     (`on_objective`). STAGE (the Director's, NX-156): go to the base and hold; DONE when every
     current claimant is there and every slot is claimed or the expiry has passed (the job that
     depends on it opens then), FAILED with no claimant left or when the side lost the base.
     CAPTURE (the Director's): go to the node and stay, the capture run itself being
     `nexus.core.capture`; DONE when the node is the side's, EXPIRED at its expiry even with
     claimants (a claimant still driving gets a fresh clock, at most
     `tasking.capture_max_restarts` times).
     PATROL (the Director's, NX-157): drive out to `Job.via` and then home to the base; DONE when a
     claimant is back at the base, FAILED with no claimant left or when the side lost the base.
     PATROL (the coalition's, Q-SIM-94): hold the node (an aircraft circles it); DONE
     `tasking.patrol_dwell_s` after the first claimant is on station, FAILED when the node or a
     node on a claimant's route is no longer the side's.
     INTERCEPT (the Static's, Q-SIM-96, NX-382): each pass its claimants fly to the scout's
     last-known track position; DONE when the scout is destroyed or Disabled (a participant
     needed, else EXPIRED), EXPIRED when the side has not tracked it for
     `director.intercept.lost_s` (`Job.lost`: when it was first found untracked) or its last track
     is no longer within `director.intercept.radius_m` of a node the side holds.
   - DONE needs a participant (a live ACTIVE claimant), else EXPIRED, unless another job waits for
     it (the Director's chains, NX-156): its goal was met, so the next step must not fail with it.
     A job with no claim expires `tasking.expire_min` after posting (an objective's job: with the
     objective); one waiting for another does not expire.
   - A job that depends on an ended one (TB-8) loses the dependency when it was DONE, else FAILS.
     When it loses it, its expiry clock restarts and its claimants (units that took it at spawn,
     `take`, and waited with their lease held) set off.
3. **Generate** (`nexus.core.tasking_gen`, from the side's `SideView`, TB-9) and post by dedupe key
   (`post_job`, TB-4; later also the director's entry). An unclaimed generated job that is no
   longer generated expires.
4. **Assign** (TB-2, TB-5, TB-7). Each idle unit of the side (aircraft or ground, not Disabled, no
   path, not RTB, no job, no explicit order), in id order, takes the first job in rank order that
   fits it (`fits`), has no open dependency, may be taken by it, has a free slot (when every
   fitting job is full: any) and is feasible. Rank: `tasking.priority.<kind>` x urgency +
   `priority_aging_per_min` x game minutes waited, an exact Fraction, highest first; runs of equal
   priority are ordered by one `tasking` draw each, in job id order, then by id. Feasible: a
   GROUND unit has a road route (an empty truck on a resupply job reloads at a source first);
   an aircraft reaches the target and a landing base of its side with the bingo reserve left,
   its straight route crosses no discovered, not-Disabled enemy air-defense ring unless the
   target is that site's base (`crosses_ring`, also applied to a parameterless JOIN), and a strike
   job needs a round. A carrier (truck, convoy) fits resupply jobs only. An
   aircraft that fails only for fuel or rounds takes a refuel step instead: it flies to the
   nearest landing base with stock, where `logistics` restocks it, and tries again next pass. A
   claim sets the path: a GROUND unit by road, an aircraft straight.

Before each Static pass `World.intercept_seen` is brought up to date (`_watch`: the first pass a
coalition scout was tracked inside a held node's radius, dropped when it is not).

A non-garrison unit may displace an AI garrison claimant (Q-TD-11; `tasking.human_displaces_ai`).
An AI garrison unit takes the `tasking.ai_jobs` (DEFEND, RESUPPLY, SCOUT) freely, never the
`tasking.ai_excluded_jobs` (ESCORT_CONVOY, PATROL), and any other job only once a COMMANDER-owned
unit holds a claim on it (it never initiates offense). A parameterless JOIN takes the best job at
once (`joinable_jobs`, ties by id). For `tasking.counterattack_window_min` after its side loses a
node (`World.lost`) the garrison may also take strike and assist-objective jobs against it
(Q-GD-31).
Deterministic: integers and Fractions, jobs and units in id order, one RNG stream.
"""

import math
from collections.abc import Iterable, Sequence
from fractions import Fraction
from typing import Any, Literal

from nexus.contracts.gen.common.enums import JobKind, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_claimed import JobClaimed
from nexus.contracts.gen.events.job_created import JobCreated
from nexus.contracts.gen.events.job_done import JobDone, Participant
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.contracts.gen.events.job_failed import JobFailed
from nexus.core.fog import SideView, side_view
from nexus.core.logistics import Run, go_home, keeps, load, nearest_base, plan_run
from nexus.core.rng import PcgStream, RngStream
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules, TaskingRules
from nexus.core.tasking_gen import (
    GENERATED,
    POST_GATE,
    JobSpec,
    can_hit,
    fits,
    generate,
    held_within,
    is_idle,
    watched,
)
from nexus.core.world import (
    SIDES,
    Claim,
    Entity,
    FacilityMarker,
    Job,
    Vec2,
    World,
    release_claim,
)

type Outcome = Literal["DONE", "FAILED", "EXPIRED"]
type Verdict = Literal["ok", "refuel", "no"]
type Routes = dict[tuple[str, str], list[str] | None]
_AIR, _GROUND = "AIR", "GROUND"
_INTERCEPT: JobKind = "INTERCEPT"  # the Static board's hunt of a scout (Q-SIM-96, NX-382)
_PATROL: JobKind = "PATROL"  # the Director's (NX-157), and the coalition board's (NX-382)
_COALITION: Side = "COALITION"
_STATIC: Side = "ENEMY"
_AI, _HUMAN = "AI_GARRISON", "COMMANDER"
_NO_BLOCKED = frozenset[str]()  # no bridge is destroyed until NX-373
_MAX_PARTICIPANTS = 64  # JobDone.participants maxItems
_TIE_DRAW = 1 << 32  # width of the tie-break draw; it only orders equals, not a tunable


def _now(world: World) -> int:
    """The running tick being computed, on the campaign clock."""
    return world.campaign.running_ticks + 1


def _base(world: World) -> dict[str, Any]:
    return {
        "tick": world.campaign.tick + 1,
        "event_seq": world.next_event_seq(),
        "campaign_id": world.campaign.id,
    }


def priority(tr: TaskingRules, job: Job, now: int) -> Fraction:
    """`tasking.priority.<kind>` x urgency, plus linear aging per game minute waited (TB-3)."""
    waited = Fraction(now - job.created, tr.ticks_per_min)
    # 1000: `Job.urgency` is in thousandths of a multiplier (a fixed-point scale)
    return tr.priority[job.kind] * Fraction(job.urgency, 1000) + tr.aging_per_min * waited


def rank(tr: TaskingRules, jobs: Sequence[Job], now: int, tie: PcgStream | None) -> list[Job]:
    """Best first: priority descending, then job id. With `tie`, each run of equal priority is
    ordered by one draw per job (in id order) before the id (TB-5); without, by id alone."""
    scored = sorted(((priority(tr, j, now), j) for j in jobs), key=lambda pj: (-pj[0], pj[1].id))
    out: list[Job] = []
    i = 0
    while i < len(scored):
        j = i
        while j < len(scored) and scored[j][0] == scored[i][0]:
            j += 1
        run = [job for _, job in scored[i:j]]
        if tie is not None and len(run) > 1:
            draws = {job.id: tie.randbelow(_TIE_DRAW) for job in run}
            run.sort(key=lambda job: (draws[job.id], job.id))
        out += run
        i = j
    return out


def post_job(world: World, side: Side, spec: JobSpec, out: list[Event]) -> Job:
    """Post a job to `side`'s board, or update the live job with the same dedupe key instead of
    adding a second one (TB-4: slots and urgency follow the new spec, the posting time and expiry
    stay). The one entry for the generator and, later, the director's operation templates."""
    tr = _rules(world)[1]
    board = world.boards[side]
    job = next((j for j in board.values() if j.key == spec.key), None)
    if job is not None:
        job.slots, job.urgency = spec.slots, spec.urgency
        if spec.blob is not None:
            job.blob, job.pos = spec.blob, spec.pos
        if spec.objective is not None:  # e.g. a marker strike that became the objective
            job.objective, job.expires = spec.objective, None
        return job
    now = _now(world)
    job = Job(
        world.next_job_id(), spec.kind, spec.key, spec.slots, spec.urgency, now, spec.node,
        spec.blob, spec.pos, None if spec.objective is not None else now + tr.expire_ticks,
        spec.depends_on, spec.objective, spec.entity, via=spec.via,
    )  # fmt: skip
    board[job.id] = job
    out.append(
        JobCreated.model_construct(
            kind="JobCreated",
            **_base(world),
            job_id=job.id,
            side=side,
            job_kind=job.kind,
            node_id=job.node,
            blob_id=job.blob,
            entity_id=job.entity,
            slots=job.slots,
            depends_on_job_id=job.depends_on,
        )
    )
    return job


def _rules(world: World) -> tuple[Rules, TaskingRules]:
    if world.rules is None or world.rules.tasking is None:
        raise ValueError("the Tasking Board needs the world's rules with tasking rules")
    return world.rules, world.rules.tasking


def _is_ai(world: World, entity_id: int) -> bool:
    e = world.find(entity_id)
    return e is not None and e.owner_kind == _AI


def _full(world: World, job: Job, *, ai: bool) -> bool:
    """No free slot for a unit (`ai`: an AI garrison unit). Any other unit does not count the
    garrison's claims while `tasking.human_displaces_ai`: it displaces one (`claim`)."""
    if ai or not _rules(world)[1].human_displaces_ai:
        return len(job.claims) >= job.slots
    humans = 0
    for i in job.claims:
        humans += not _is_ai(world, i)
        if humans >= job.slots:
            return True
    return False


def _overfill(tr: TaskingRules, job: Job) -> int:
    """The claims a job takes when every job is full: `tasking.overfill_factor` times its slots,
    but a Recon scout's point job never doubles unless `tasking.overfill_point_jobs` (a second scout
    would only burn fuel and rearm, NX-379)."""
    return (
        job.slots
        if _is_point(job) and not tr.overfill_point_jobs
        else tr.overfill_factor * job.slots
    )


def _open(tr: TaskingRules, world: World, pool: list[Job], *, ai: bool) -> list[Job]:
    """The jobs a unit may take, in rank order: those with a free slot, else (every one full) those
    not yet at `overfill_factor` times their slots; beyond that the unit waits for the next pass."""
    free = [j for j in pool if not _full(world, j, ai=ai)]
    return free or [j for j in pool if len(j.claims) < _overfill(tr, j)]


def _may_take(world: World, tr: TaskingRules, e: Entity, job: Job) -> bool:
    """An AI garrison unit never initiates offense: outside its own jobs it joins only a job a
    COMMANDER-owned unit already holds (GAMEPLAY §1b, Q-GD-26), or a strike or assist-objective
    job against a node its side lost within `tasking.counterattack_window_min` (Q-GD-31)."""
    if job.kind == _INTERCEPT:  # the garrison's own call: a round that can hit the scout
        track = world.contacts[e.side].get(job.entity or 0)
        return track is not None and world.rules is not None and can_hit(world.rules, e, track.kind)
    if job.kind in tr.ai_excluded_jobs:
        return e.owner_kind != _AI  # escorting, patrolling: the players' call (Q-GP-45, Q-SIM-94)
    if e.owner_kind != _AI or job.kind in tr.ai_jobs:
        return True
    lost = world.lost.get(job.node or "")
    owner = world.owner.get(job.node or "")
    if lost is not None and _now(world) - lost < tr.counterattack_window_ticks:
        if owner not in (e.side, "NEUTRAL"):
            return True
    return any((c := world.find(i)) is not None and c.owner_kind == _HUMAN for i in job.claims)


def take(world: World, e: Entity, job: Job, out: list[Event]) -> None:
    """A unit the Director has just spawned takes `job` at once (NX-156, Q-SIM-81): it claims it
    and, when no earlier job holds it back, sets off if the job is feasible for it (a job still
    waiting is held by its claimants' leases, and they set off when it opens)."""
    claim(world, e, job, out)
    if job.depends_on is None:
        _launch(world, e, job)


def _launch(world: World, e: Entity, job: Job) -> None:
    rules = _rules(world)[0]
    routes: Routes = {}
    if _feasible(world, rules, routes, e, job) == "ok":
        _dispatch(world, rules, routes, e, job)


def claim(world: World, e: Entity, job: Job, out: list[Event]) -> None:
    """`e` takes a slot of `job` (JobClaimed; the lease starts). A job whose slots are full gives
    one to a non-garrison unit (while `tasking.human_displaces_ai`) by releasing its AI garrison
    claimant with the highest entity id (Q-TD-11), which stops where it is (an aircraft orbits; a
    ground unit finishes its road leg); a job full of humans is overfilled, which only happens when
    every job is full. Claims are kept in
    entity-id order, as a snapshot restores them, so a restored world emits the same events."""
    if e.owner_kind != _AI and len(job.claims) >= job.slots and not _full(world, job, ai=False):
        evicted = max(i for i in job.claims if _is_ai(world, i))
        release_claim(world, job, evicted, out)
        if (v := world.find(evicted)) is not None:
            v.path = (
                v.path[:1]
                if v.path and world.rules and world.rules.domain[v.kind] == _GROUND
                else []
            )
    job.claims[e.id] = Claim(_now(world))
    job.claims = dict(sorted(job.claims.items()))
    e.job_id = job.id
    out.append(
        JobClaimed.model_construct(kind="JobClaimed", **_base(world), job_id=job.id, entity_id=e.id)
    )


def joinable_jobs(world: World, kind: UnitKind) -> list[Job]:
    """The coalition jobs a new `kind` unit may take on a parameterless JOIN (Q-GP-23), best first:
    it fits the kind, has no open dependency and a free slot (every one full: up to the overfill
    cap), by priority then job id. The caller plans the first it can route and that an aircraft's
    route danger allows (`crosses_ring`); a new unit is full of fuel and rounds."""
    if world.rules is None or world.rules.tasking is None:
        return []  # the boards are off
    rules, tr = world.rules, world.rules.tasking
    jobs = [
        j for j in world.boards["COALITION"].values()
        if j.depends_on is None and j.kind not in tr.join_excluded_jobs
        and fits(rules, kind, j.kind)
    ]  # fmt: skip
    return rank(tr, _open(tr, world, jobs, ai=False), _now(world), None)


def run(world: World, out: list[Event]) -> None:
    """The `director` slot (module docstring)."""
    if world.frozen or world.rules is None or world.rules.tasking is None:
        return
    rules, tr = world.rules, world.rules.tasking
    now = _now(world)
    _guard_patrols(world, out)
    if now % tr.reeval_every_ticks:
        return
    world.lost = {n: t for n, t in world.lost.items() if now - t < tr.counterattack_window_ticks}
    for side in SIDES:
        world.cooldown[side] = {c: u for c, u in world.cooldown[side].items() if u > now}
    for e in world.entities():
        if e.order == "GOTO" and not e.path and not e.cargo and not _capturing(world, rules, e):
            e.order = None  # arrived (a truck: its stop ended, any capture run done)
    routes: Routes = {}  # road routes found this pass, shared by every unit
    for side in SIDES:
        _settle(world, rules, tr, side, now, routes, out)
        view = side_view(world, side)
        if side == _STATIC:
            _watch(world, rules, view, now)
        specs = generate(world, rules, tr, side, view)
        before = {j.key for j in world.boards[side].values()}
        for spec in specs:
            post_job(world, side, spec, out)
        if any(
            j.key.startswith("scout:") and j.key not in before for j in world.boards[side].values()
        ):
            world.cooldown[side][POST_GATE] = now + tr.scout_post_interval_ticks
        wanted = {s.key for s in specs}
        for job in list(world.boards[side].values()):
            if job.key.startswith(GENERATED) and job.key not in wanted and not job.claims:
                _end(world, side, job, "EXPIRED", out)  # its condition ended
        if side == _COALITION:
            _preempt_patrols(world, rules, tr, now, routes, out)
        _assign(world, rules, tr, side, now, routes, out)


def _watch(world: World, rules: Rules, view: SideView, now: int) -> None:
    """The intercept clock (Q-SIM-96): a scout watched now keeps the pass it was first watched
    (consecutive passes), any other starts at `now`; one that is not watched loses its entry."""
    seen = world.intercept_seen
    world.intercept_seen = {i: seen.get(i, now) for i in watched(world, rules, view)}


def _capturing(world: World, rules: Rules, e: Entity) -> bool:
    """A ground unit standing where its side's capture bar is filling: its capture run goes on."""
    bar = world.capture.get(e.last_node or "")
    return rules.domain[e.kind] == _GROUND and bar is not None and bar.side == e.side


def on_objective(world: World, objective_id: int, completed: bool, out: list[Event]) -> None:
    """The objective resolved (`nexus.core.campaign`): its jobs end, DONE if it was completed and
    a claimant made progress, else EXPIRED."""
    for side in SIDES:
        for job in list(world.boards[side].values()):
            if job.objective == objective_id and job.id in world.boards[side]:
                done = completed and _participants(world, job)
                _end(world, side, job, "DONE" if done else "EXPIRED", out)


def _arrived(e: Entity, job: Job) -> bool:
    """At the job's target with nothing left to fly or drive: a node job when `last_node` is the
    node; a blob job when the aircraft is orbiting at the end of its path."""
    if e.path:
        return False
    return e.last_node == job.node if job.node is not None else e.state == "ON_STATION"


def _settle(
    world: World, rules: Rules, tr: TaskingRules, side: Side, now: int, routes: Routes,
    out: list[Event],
) -> None:  # fmt: skip
    board = world.boards[side]
    for job in list(board.values()):
        if job.id not in board:
            continue  # ended by a dependency cascade
        for entity_id, c in list(job.claims.items()):
            e = world.find(entity_id)
            if e is not None and e.pickup is not None and not e.path and e.last_node == e.pickup:
                if not _load_at_source(
                    world, rules, routes, e, job
                ):  # the reload step reached its source
                    release_claim(world, job, entity_id, out)  # ... and found nothing to load
                    continue
            if e is None or e.damage_state == "DISABLED" or e.state == "RTB" or e.order is not None:
                release_claim(world, job, entity_id, out)  # lost, sent home, or a human order wins
            elif job.kind == "ESCORT_CONVOY":  # the progress is the follow order itself
                if e.follow_id != job.entity:
                    release_claim(
                        world, job, entity_id, out
                    )  # the truck is gone, or it re-attached
                else:
                    c.at, c.active = now, True
            elif e.path or _arrived(e, job):
                c.at, c.active = now, True
            elif job.depends_on is not None:
                c.at = now  # waiting for the job before it (a unit that took it at spawn)
            elif now - c.at >= tr.claim_lease_ticks:
                release_claim(world, job, entity_id, out)  # no progress for the whole lease
        if (
            job.kind == "CAPTURE"
            and job.expires is not None
            and now >= job.expires
            and job.restarts < tr.capture_max_restarts
            and any((e := world.find(i)) is not None and e.path for i in job.claims)
        ):  # units still driving get a fresh clock, at most `capture_max_restarts` times
            job.expires, job.restarts = now + tr.expire_ticks, job.restarts + 1
        if job.kind == _INTERCEPT:
            _chase(world, side, job, out)
        if _is_point(job):
            _loiter(world, rules, tr, job, now)
        elif _is_station_patrol(side, job):
            _dwell(world, rules, tr, job, now)
        outcome = _outcome(world, rules, tr, side, job, now)
        if outcome is not None:
            _end(world, side, job, outcome, out)


def _in_leash(rules: Rules, e: Entity, pos: Vec2) -> bool:
    """`pos` is within `director.intercept.leash_m` of the garrison unit's home (a unit without a
    home has no leash)."""
    dr = rules.director
    if e.home is None:
        return True
    hx, hy = rules.roads.pos[e.home]
    return dr is not None and math.hypot(pos.x - hx, pos.y - hy) <= dr.intercept_leash_m


def _chase(world: World, side: Side, job: Job, out: list[Event]) -> None:
    """Q-SIM-96: the job's position follows the side's track of the scout (last-known once lost,
    never the scout's true position, FOW), and each claimant flies to it. A garrison claimant
    whose scout's track passes its leash is released and stops; the recall takes it home."""
    c = world.contacts[side].get(job.entity or 0)
    if c is not None:
        job.pos = c.pos
    if c is not None and c.age is None:
        job.lost = None
    elif job.lost is None:  # first found untracked: the track's age says since when
        job.lost = _now(world) - (0 if c is None else c.age or 0)
    if c is None:
        return
    for i in list(job.claims):
        if (e := world.find(i)) is None:
            continue
        if world.rules is not None and not _in_leash(world.rules, e, c.pos):
            release_claim(world, job, i, out)
            e.path = []
        else:
            e.path = [c.pos]


def _escaped(world: World, rules: Rules, side: Side, job: Job) -> bool:
    """The scout was untracked for `director.intercept.lost_s`, or its last track is not within
    `director.intercept.radius_m` of a node the side holds."""
    dr = rules.director
    if dr is None or job.pos is None:
        return True
    lost = job.lost is not None and _now(world) - job.lost >= dr.intercept_lost_ticks
    return lost or not held_within(
        rules.roads.pos, world.owner, side, job.pos.x, job.pos.y, dr.intercept_radius_m
    )


def _present(world: World, job: Job, *, delivered: bool = False) -> bool:
    """A live claimant has arrived (with its cargo gone, for a delivery)."""
    return any(
        (e := world.find(i)) is not None and _arrived(e, job) and not (delivered and e.cargo)
        for i in job.claims
    )


def _staged(world: World, job: Job) -> bool:
    """Every current claimant has arrived and either every slot is claimed or the job's expiry has
    passed (a unit lost on the way must not hold the job for ever, Q-SIM-84)."""
    mine = [world.find(i) for i in job.claims]
    full = len(mine) >= job.slots or (job.expires is not None and _now(world) >= job.expires)
    return full and all(e is not None and _arrived(e, job) for e in mine)


def _menaced(world: World, rules: Rules, tr: TaskingRules, side: Side, node: str) -> bool:
    """The other side's bar is on the node, or the side tracks an enemy ground unit within
    `tasking.defend_radius_m` of it (what the side knows, as when the job was posted)."""
    bar = world.capture.get(node)
    if bar is not None and bar.side != side:
        return True
    x, y = rules.roads.pos[node]
    return any(
        c.age is None and rules.domain[c.kind] == _GROUND
        and math.hypot(c.pos.x - x, c.pos.y - y) <= tr.defend_radius_m
        for c in world.contacts[side].values()
    )  # fmt: skip


def _verdict(world: World, rules: Rules, tr: TaskingRules, side: Side, job: Job) -> Outcome | None:
    node = job.node
    lost = node is not None and world.owner.get(node) != side
    match job.kind:
        case "RESUPPLY":
            if lost:
                return "FAILED"
            return "DONE" if _present(world, job, delivered=True) else None
        case "DEFEND":
            if lost:
                return "FAILED"
            held = node is not None and _present(world, job)
            return "DONE" if held and not _menaced(world, rules, tr, side, str(node)) else None
        case "STRIKE":
            fallen = node is not None and (not lost or not world.defense_hp.get(node, 0))
            return "DONE" if fallen else None
        case "SCOUT":
            if _is_point(job):  # done when the loiter ends or a ring covers it (NX-379)
                over = _loiter_over(rules, job, _now(world)) or _ring_over(world, rules, side, job)
                return "DONE" if over else None
            return "DONE" if _present(world, job) else None
        case "STAGE":
            if lost or not job.claims:  # no unit left to hold the base
                return "FAILED"
            return "DONE" if _staged(world, job) else None
        case "CAPTURE":
            return "DONE" if node is not None and world.owner.get(node) == side else None
        case "PATROL" if _is_station_patrol(side, job):
            return _station_verdict(world, tr, job)
        case "PATROL":  # = _PATROL; a match needs a literal
            if lost or not job.claims:  # no unit left to drive, or the base is gone
                return "FAILED"
            return "DONE" if _present(world, job) else None  # home again
        case "INTERCEPT":
            scout = world.find(job.entity or 0)  # a kill is seen by those who made it
            if scout is None or scout.damage_state == "DISABLED":
                return "DONE"
            return "EXPIRED" if _escaped(world, rules, side, job) else None
        case "ESCORT_CONVOY":
            truck = world.find(job.entity or 0)
            if truck is None or truck.damage_state == "DISABLED":
                return "FAILED" if job.claims else "EXPIRED"
            return None if truck.path else "DONE"  # it arrived (no participant: EXPIRED)
    return None  # ASSIST_OBJECTIVE ends with its objective


def _outcome(
    world: World, rules: Rules, tr: TaskingRules, side: Side, job: Job, now: int
) -> Outcome | None:
    verdict = _verdict(world, rules, tr, side, job)
    waited_on = any(j.depends_on == job.id for j in world.boards[side].values())
    if verdict == "DONE" and not _participants(world, job) and not waited_on:
        verdict = "EXPIRED"  # nobody to credit (a job another waits for is DONE: its goal is met)
    # A job waiting for another does not expire (the one before it ends or fails it, TB-8); a
    # capture run ends at its expiry even with claimants (NX-156).
    held = job.depends_on is not None or (job.claims and job.kind != "CAPTURE")
    if verdict is None and not held and job.expires is not None and now >= job.expires:
        verdict = "EXPIRED"
    return verdict


def _participants(world: World, job: Job) -> list[Entity]:
    return [
        e for i, c in sorted(job.claims.items()) if c.active and (e := world.find(i)) is not None
    ]


def _end(world: World, side: Side, job: Job, outcome: Outcome, out: list[Event]) -> None:
    """Remove the job, free its claimants and emit its outcome; jobs that depend on it lose the
    dependency (DONE) or fail with it (TB-8)."""
    board = world.boards[side]
    people = _participants(world, job)[:_MAX_PARTICIPANTS]
    for i in job.claims:
        if (e := world.find(i)) is not None:
            if outcome == "FAILED" and job.kind == _PATROL and world.rules is not None:
                _abandon_patrol(world, world.rules, e, job)
            if outcome == "DONE" and _is_point(job) and world.rules is not None:
                go_home(world, world.rules, e)  # the loiter is over (NX-379)
            if job.kind == _INTERCEPT:
                e.path = []  # it stops where it is, not at a dead scout's last position
            e.job_id = e.pickup = None
            if e.order != "FOLLOW":
                e.follow_id = None  # an escort claim ends with its follow order
    if job.blob is not None and world.rules and world.rules.tasking:  # any outcome (Q-DEV-21)
        until = _now(world) + world.rules.tasking.scout_cooldown_ticks
        # The cell is not posted again yet; blob ids are `<refresh_tick>-<cell>` (Q-SIM-47).
        world.cooldown[side][job.blob.split("-")[-1]] = until
    del board[job.id]
    base = {**_base(world), "job_id": job.id}
    if outcome == "DONE":
        done = [
            Participant(entity_id=e.id, commander_id=e.commander_id, auto=False) for e in people
        ]
        out.append(JobDone.model_construct(kind="JobDone", **base, participants=done))
    elif outcome == "FAILED":
        out.append(JobFailed.model_construct(kind="JobFailed", **base))
    else:
        out.append(JobExpired.model_construct(kind="JobExpired", **base))
    for dep in [j for j in board.values() if j.depends_on == job.id]:
        if outcome == "DONE":
            dep.depends_on = None
            if dep.expires is not None and world.rules and world.rules.tasking:
                dep.expires = _now(world) + world.rules.tasking.expire_ticks
            for i in dep.claims:
                if (e := world.find(i)) is not None:
                    _launch(world, e, dep)
        else:
            _end(world, side, dep, "FAILED", out)


def _is_point(job: Job) -> bool:
    """A Recon scout job at a point of a sector (NX-379): no node, no blob, a position."""
    return job.kind == "SCOUT" and job.node is None and job.blob is None


def _loiter_over(rules: Rules, job: Job, now: int) -> bool:
    dr = rules.director
    return job.arrived is not None and (dr is None or now - job.arrived >= dr.recon_loiter_ticks)


def _ring_over(world: World, rules: Rules, side: Side, job: Job) -> bool:
    """A discovered air-defense ring that was not last seen Disabled now covers the job's point,
    with the loiter radius of clearance (Q-SIM-87): the scout ends the job and goes home."""
    dr = rules.director
    if dr is None or job.pos is None:
        return False
    return ring_crossed(
        world.markers[side].values(), job.pos, (job.pos.x, job.pos.y), dr.recon_loiter_radius_m
    )


def _loiter(world: World, rules: Rules, tr: TaskingRules, job: Job, now: int) -> None:
    """Q-SIM-87: the loiter starts when a claimant arrives at the point and lasts
    `director.recon.loiter_s`. Meanwhile each claimant with no path flies to the next corner of
    the square of `director.recon.loiter_radius_m` around the point (corners E, S, W, N; the
    one after the corner nearest its position, ties first), so it stays within the radius. The
    job is DONE when the loiter ends (`_verdict`); with no claimant the loiter restarts."""
    dr = rules.director
    if dr is None or job.pos is None:
        return
    if not job.claims:
        job.arrived = None
        return
    if job.arrived is None:
        if not _present(world, job):
            return
        job.arrived = now
    if _loiter_over(rules, job, now):
        return
    for i in job.claims:
        e = world.find(i)
        if e is not None and not e.path and e.state == "ON_STATION":
            e.path = [_corner(rules, job.pos, e.pos, dr.recon_loiter_radius_m)]


def _corner(rules: Rules, centre: Vec2, at: Vec2, radius: float) -> Vec2:
    """The loiter corner after the one nearest `at`, kept inside the theater."""
    w, h = rules.bounds_m
    corners = [
        Vec2(min(max(centre.x + dx, 0.0), w), min(max(centre.y + dy, 0.0), h))
        for dx, dy in ((radius, 0.0), (0.0, radius), (-radius, 0.0), (0.0, -radius))
    ]
    near = min(
        range(len(corners)), key=lambda k: (math.hypot(corners[k].x - at.x, corners[k].y - at.y), k)
    )
    return corners[(near + 1) % len(corners)]


def _is_station_patrol(side: Side, job: Job) -> bool:
    """A coalition patrol (Q-SIM-94, NX-382) holds at its node; the Director's goes out and back."""
    return job.kind == _PATROL and side == _COALITION


def _station_verdict(world: World, tr: TaskingRules, job: Job) -> Outcome | None:
    """DONE after `tasking.patrol_dwell_s` on station (a lost node fails it in `_guard_patrols`)."""
    held = job.arrived is not None and _now(world) - job.arrived >= tr.patrol_dwell_ticks
    return "DONE" if held else None


def _patrol_exposed(world: World, side: Side, job: Job) -> bool:
    """A claimed coalition patrol whose node, or a node on a claimant's path, the side no longer
    holds: it must never enter one (Q-SIM-94)."""
    return any(
        isinstance(n, str) and world.owner.get(n) != side
        for i in job.claims
        if (e := world.find(i)) is not None
        for n in [job.node, *e.path]
    )


def _guard_patrols(world: World, out: list[Event]) -> None:
    """Every tick, before movement: a coalition patrol whose node or route lost its side's hold
    FAILS now and its units stop or go home (`_abandon_patrol`), so none enters a lost node. Only
    claimed patrols are looked at."""
    for job in list(world.boards[_COALITION].values()):
        if job.kind == _PATROL and job.claims and _patrol_exposed(world, _COALITION, job):
            _end(world, _COALITION, job, "FAILED", out)


def _preempt_patrols(
    world: World, rules: Rules, tr: TaskingRules, now: int, routes: Routes, out: list[Event]
) -> None:
    """A patrol never holds a unit a better job needs (GAMEPLAY §1b): in unit id order, a patrol
    claimant is released when an open job of higher priority has a free slot and the unit fits it,
    may take it and finds it feasible (the assignment's own checks, so it does not drop the patrol
    only to be refused). `_assign` then gives it a job. A claimant is a viewer's unit, or a
    garrison unit when `tasking.ai_excluded_jobs` allows patrols (by default it never takes one),
    with no `home` (the Director's units only), so `_board_may_give` always holds for it and is
    not asked.

    shortcut: `_feasible` routes a ground unit only from the node it stands on, so a ground
    patrol is preempted once it stands on a node (an aircraft any time); the wait is bounded by
    its transit. Upgrade: route from the unit's next path node."""
    board = world.boards[_COALITION]
    claimants = sorted(
        (i, job) for job in board.values() if job.kind == _PATROL for i in job.claims
    )
    for i, job in claimants:
        e = world.find(i)
        if e is None:
            continue
        mine = priority(tr, job, now)
        if any(
            j.kind != _PATROL and j.depends_on is None and priority(tr, j, now) > mine
            and not _full(world, j, ai=False)
            and fits(rules, e.kind, j.kind) and _may_take(world, tr, e, j)
            and _feasible(world, rules, routes, e, j) == "ok"
            for j in board.values()
        ):  # fmt: skip
            release_claim(world, job, i, out)
            e.path = []


def _dwell(world: World, rules: Rules, tr: TaskingRules, job: Job, now: int) -> None:
    """Q-SIM-94: the dwell starts when a claimant is on station at the node. A patrolling aircraft
    flies to the next corner of the square of `tasking.patrol_orbit_m` around the node (the
    scout loiter's corners, `_corner`), so it stays within that distance. With no claimant the
    dwell restarts."""
    if not job.claims or job.node is None:
        job.arrived = None
        return
    if job.arrived is None:
        if not _present(world, job):
            return
        job.arrived = now
    centre = Vec2(*rules.roads.pos[job.node])
    for i in job.claims:
        e = world.find(i)
        if e is not None and not e.path and e.state == "ON_STATION":
            e.path = [_corner(rules, centre, e.pos, tr.patrol_orbit_m)]


def _abandon_patrol(world: World, rules: Rules, e: Entity, job: Job) -> None:
    """A failed patrol's unit drops its route: home to the nearest friendly base, or it stands
    when no route avoids the other side's nodes (it retires once idle, Q-SIM-84), so it never
    drives on into a lost base (Q-SIM-86)."""
    go_home(world, rules, e)
    held = {world.owner.get(n) for n in e.path if isinstance(n, str)} - {None, e.side}
    if e.path and (e.path[-1] == job.node or held):
        e.path = []


def _board_may_give(rules: Rules, e: Entity, job: Job) -> bool:
    """A PATROL on the Static's board is the Director's alone (the coalition board posts its own,
    Q-SIM-94), and a garrison unit (`Entity.home`) stays at its base: the board gives it only a
    DEFEND of that base, or an INTERCEPT of a scout within `director.intercept.leash_m` of it, the
    one exception (Q-SIM-96); the Director sends it elsewhere (Q-SIM-85)."""
    if job.kind == _PATROL and e.side != _COALITION:
        return False
    if e.home is None:
        return True
    if job.kind == _INTERCEPT:
        return job.pos is not None and _in_leash(rules, e, job.pos)
    return job.kind == "DEFEND" and job.node == e.home


def _assign(
    world: World, rules: Rules, tr: TaskingRules, side: Side, now: int, routes: Routes,
    out: list[Event],
) -> None:  # fmt: skip
    jobs = list(world.boards[side].values())
    if not jobs:
        return
    idle = sorted((e for e in world.entities() if is_idle(rules, e, side)), key=lambda e: e.id)
    if not idle:
        return
    ranked = rank(tr, jobs, now, world.rng.stream(RngStream.TASKING))
    for e in idle:
        pool = [
            j for j in ranked
            if j.depends_on is None and _board_may_give(rules, e, j)
            and fits(rules, e.kind, j.kind) and _may_take(world, tr, e, j)
        ]  # fmt: skip
        for job in _open(tr, world, pool, ai=e.owner_kind == _AI):
            verdict = _feasible(world, rules, routes, e, job)
            if verdict == "no":
                continue
            if verdict == "ok":
                claim(world, e, job, out)
                _dispatch(world, rules, routes, e, job)
            else:
                _refuel(world, rules, e)
            break


def idle_reason(world: World, e: Entity) -> str:
    """Why an idle unit holds no job: `no_job` (nothing it may take is on the board), `full` (only
    full ones), or the reason the first job it may take is refused: `ring`, `ammo`, `refuel` (a
    rearm step would fix it, so it is refuelling now) or `reach_fuel` (a full tank would not
    reach either); else `other`. A read-only diagnostic for the balance harness (Q-SIM-92): it
    applies `_assign`'s own pool, `_open` and `_feasible`, but never ranks (that draws from the
    tasking stream)."""
    rules, tr = _rules(world)
    pool = [
        j for j in world.boards[e.side].values()
        if j.depends_on is None and _board_may_give(rules, e, j)
        and fits(rules, e.kind, j.kind) and _may_take(world, tr, e, j)
    ]  # fmt: skip
    if not pool:
        return "no_job"
    jobs = _open(tr, world, pool, ai=e.owner_kind == _AI)
    if not jobs:
        return "full"
    verdicts = [(j, _feasible(world, rules, {}, e, j)) for j in jobs]
    if any(v == "ok" for _, v in verdicts):
        return "other"  # it takes one at the next pass
    job, verdict = verdicts[0]
    if rules.domain[e.kind] != _AIR or not world.landing_bases(e.side) or e.fuel is None:
        return "other"
    if crosses_ring(world, rules, e.side, e.pos, job):
        return "ring"
    if job.kind == "STRIKE" and not any(e.ammo):
        return "ammo"
    return "refuel" if verdict == "refuel" else "reach_fuel"


def _waypoint(world: World, job: Job) -> str | Vec2:
    """Where the job is: its node, the blob's cell centre, or the escorted truck now."""
    escorted = job.kind == "ESCORT_CONVOY" and job.entity is not None  # an intercept: its track
    truck = world.find(job.entity or 0) if escorted else None
    target = job.node if job.node is not None else truck.pos if truck else job.pos
    if target is None:
        raise ValueError(f"job {job.id} has no target")
    return target


def _road(rules: Rules, routes: Routes, a: str, b: str) -> list[str] | None:
    """The road route `a` to `b`, found once per pass (roads and blocked bridges do not change
    inside one)."""
    if (a, b) not in routes:
        routes[a, b] = shortest_path(rules.roads, a, b, blocked=_NO_BLOCKED)
    return routes[a, b]


def _route(rules: Rules, routes: Routes, e: Entity, job: Job) -> list[str] | None:
    """A ground unit's road route from the node it stands on, or None (not on a node, no road)."""
    if e.last_node is None or job.node is None or e.pos != Vec2(*rules.roads.pos[e.last_node]):
        return None
    return _road(rules, routes, e.last_node, job.node)


def _patrol_route(
    world: World, rules: Rules, routes: Routes, e: Entity, job: Job
) -> list[str] | None:
    """A patrol's road route: out to `job.via`, then home to the job's node (NX-157); the leg
    shared by both is the node it turns at, listed once. A coalition patrol has no `via`: its route
    runs to its node through nodes its side holds only (Q-SIM-94)."""
    if e.last_node is None or job.node is None:
        return None
    if e.pos != Vec2(*rules.roads.pos[e.last_node]):
        return None
    if job.via is None:
        avoid = frozenset(n for n in rules.roads.pos if world.owner.get(n) != e.side)
        return shortest_path(rules.roads, e.last_node, job.node, blocked=_NO_BLOCKED, avoid=avoid)
    out = _road(rules, routes, e.last_node, job.via)
    home = _road(rules, routes, job.via, job.node)
    return None if out is None or home is None else [*out, *home[1:]]


def _reaches(
    world: World, rules: Rules, e: Entity, job: Job, bases: tuple[str, ...], fuel: float
) -> bool:
    """Out to the target and on to the nearest landing base with the bingo reserve left (NX-368)."""
    return reaches(rules, e, _waypoint(world, job), bases, fuel)


def reaches(rules: Rules, e: Entity, goal: str | Vec2, bases: tuple[str, ...], fuel: float) -> bool:
    """`e` can fly to `goal` and on to the nearest of `bases` with the bingo reserve left; a goal
    that is itself a base (a rebase, Q-SIM-90) leaves nothing to fly on."""
    x, y = rules.roads.pos[goal] if isinstance(goal, str) else (goal.x, goal.y)
    back = min(math.hypot(bx - x, by - y) for b in bases for bx, by in [rules.roads.pos[b]])
    out = math.hypot(x - e.pos.x, y - e.pos.y)
    reserve = rules.bingo_reserve_frac * rules.fuel_s[e.kind]
    return fuel > (out + back) / rules.speed(e.kind, e.damage_state) + reserve


def _feasible(world: World, rules: Rules, routes: Routes, e: Entity, job: Job) -> Verdict:
    """TB-2. `refuel`: it fails now, but a full tank and load (a rearm step) would do."""
    if rules.domain[e.kind] == _GROUND:
        if job.kind == "RESUPPLY" and not e.cargo:
            return "ok" if _reload_plan(world, rules, routes, e, job) is not None else "no"
        if job.kind == _PATROL:
            return "no" if _patrol_route(world, rules, routes, e, job) is None else "ok"
        return "no" if _route(rules, routes, e, job) is None else "ok"
    bases = world.landing_bases(e.side)
    if not bases or e.fuel is None or crosses_ring(world, rules, e.side, e.pos, job):
        return "no"
    armed = job.kind != "STRIKE" or any(e.ammo)
    if armed and _reaches(world, rules, e, job, bases, e.fuel):
        return "ok"
    return "refuel" if _reaches(world, rules, e, job, bases, rules.fuel_s[e.kind]) else "no"


def _dispatch(world: World, rules: Rules, routes: Routes, e: Entity, job: Job) -> None:
    if job.kind == "ESCORT_CONVOY":  # taking it is a follow order on the truck (Q-GP-29)
        e.follow_id, e.path = job.entity, []
        return
    if rules.domain[e.kind] == _AIR:
        e.path = [_waypoint(world, job)]
        return
    if job.kind == "RESUPPLY" and not e.cargo:  # reload first (Q-SIM-74)
        run = _reload_plan(world, rules, routes, e, job)
        if run is None:
            return
        if run.source == e.last_node:
            _load(world, e, run.source, job.node)
        else:
            e.pickup = run.source
            e.path = [*(_road(rules, routes, str(e.last_node), run.source) or [])]
            return
    route = (
        _patrol_route(world, rules, routes, e, job)
        if job.kind == _PATROL
        else _route(rules, routes, e, job)
    )
    e.path = [] if route is None else [*route]


def _reload_plan(world: World, rules: Rules, routes: Routes, e: Entity, job: Job) -> Run | None:
    """Where an empty truck loads for a resupply job: the JOIN source rule (`plan_run`: the nearest
    friendly base with surplus to the destination, never the destination, the sanctuary last),
    provided there is something to carry and the truck can drive there."""
    if e.last_node is None or job.node is None:
        return None
    run = plan_run(world, rules, e.side, job.node)
    if run is None or run.cargo <= 0:
        return None
    return run if _road(rules, routes, e.last_node, run.source) is not None else None


def crosses_ring(world: World, rules: Rules, side: Side, start: Vec2, job: Job) -> bool:
    """TB-2 route danger: the straight line from `start` to the target passes within the
    engagement ring of an enemy site the side has discovered and last saw not Disabled, unless
    the target is that site's own base."""
    if job.kind == "ESCORT_CONVOY":
        return False  # the convoy is where the threat is: a direct order, as a follow is
    goal = _waypoint(world, job)
    gx, gy = rules.roads.pos[goal] if isinstance(goal, str) else (goal.x, goal.y)
    others = (m for m in world.markers[side].values() if (m.pos.x, m.pos.y) != (gx, gy))
    orbit = rules.tasking.patrol_orbit_m if job.kind == _PATROL and rules.tasking else 0.0
    return ring_crossed(others, start, (gx, gy), orbit)  # a patrol's orbit needs clearance too


def ring_crossed(
    markers: Iterable[FacilityMarker], start: Vec2, goal: tuple[float, float], margin: float = 0.0
) -> bool:
    """The straight line from `start` to `goal` passes within an engagement ring (plus `margin`, m)
    of one of the markers whose site has a ring and was last seen not Disabled. Pure: the Director
    asks it of the Static's discovered markers (TD-2) as the board does of the side's (TB-2)."""
    gx, gy = goal
    dx, dy = gx - start.x, gy - start.y
    length2 = dx * dx + dy * dy
    for m in markers:
        if m.ring_m is None or m.state == "DISABLED":
            continue
        k = (
            0.0
            if length2 == 0
            else max(0.0, min(1.0, ((m.pos.x - start.x) * dx + (m.pos.y - start.y) * dy) / length2))
        )
        if math.hypot(start.x + k * dx - m.pos.x, start.y + k * dy - m.pos.y) <= m.ring_m + margin:
            return True
    return False


def _load(world: World, e: Entity, source: str, dest: str | None) -> None:
    """Load as a spawn does: `min(truck_cargo, spare)` leaves the source's stock (the sanctuary
    is infinite), so stock plus cargo is conserved. The source keeps its floor, or its stock target
    on a stocking run to `dest` (`keeps`, Q-SIM-102). The stocking rule is derived again here from
    `dest`'s state now, not when the job was taken, so a destination lost or starved mid-trip
    loads under the floor rule (as `plan_run` would plan it now)."""
    rules = world.rules
    if rules is None:
        return
    sup = rules.supply
    keep = (
        keeps(world, rules, e.side, dest)
        if dest is not None and sup.max_stock.get(dest, 0) > 0
        else sup.starve_floor
    )
    surplus = world.stock[source] - keep[source] if source in world.stock else None
    cargo = sup.truck_cargo if surplus is None else max(0, min(sup.truck_cargo, surplus))
    load(world, Run(source, cargo, []))
    e.cargo = cargo


def _load_at_source(world: World, rules: Rules, routes: Routes, e: Entity, job: Job) -> bool:
    """The truck reached its source: load and head for the destination. False: nothing to carry,
    or no road on (the truck keeps no path then)."""
    source = e.pickup or ""
    e.pickup = None
    if world.owner.get(source) == e.side:
        _load(world, e, source, job.node)
    route = _route(rules, routes, e, job) if e.cargo else None
    e.path = [] if route is None else [*route]
    return route is not None


def _refuel(world: World, rules: Rules, e: Entity) -> None:
    """The rearm/refuel step (GAMEPLAY §1b, Q-GD-17): head for the nearest landing base of the
    side that has stock, unless already landed at one (`logistics` restocks it there)."""
    bases = tuple(b for b in world.landing_bases(e.side) if b not in world.stock or world.stock[b])
    if bases and not (e.state == "LANDED" and e.last_node in bases):
        e.path, e.orbit = [nearest_base(e, rules, bases)[1]], None
