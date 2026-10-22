"""The Director's operations in the world: pick, pay, spawn, post (THREAT-DIRECTOR §4 steps 5-8,
TD-2, Q-TD-8, Q-TD-12, Q-SIM-81; NX-156). Where `nexus.core.operations` decides from a view, this
module touches the world, in the `director` slot right after `nexus.core.director.decide`.

Each window: the Retake clocks are pruned; `Own` is read; candidates are ranked with the `director`
stream and selected within `DirectorState.budget` and the unit caps; each selected operation is
launched in selection order:
- **Pay.** "The budget is the stock" (Q-TD-12): the operation's cost is debited from the surplus of
  the side's finite-stock bases (above their starvation floors), the base its first unit spawned at
  first, then the rest in id order, one `SupplyConsumed{SPAWN}` per base. Units cost nothing more
  (no loadout charge). The window's budget is a plan: an operation whose cost the real surplus
  cannot pay at launch (earlier ones loaded carriers from it) is skipped whole, never part-paid.
- **Spawn (Q-TD-8).** One unit per slot, kinds in turn, owned by the ENEMY_DIRECTOR, full of fuel
  and rounds, at `plan_deploy`'s base for the unit's job (GP-7: the nearest base with surplus,
  else the rear source), planned on the stock before the debit.
- **Jobs.** Each template job is posted by `post_job` on the side's board, in order, the key
  `op:<operation>:<target>:<job index>[:<convoy>]`, each depending on the job posted just before
  it (the last of the previous step); its units claim it at once (`tasking.take`).
- **Effect.** EMISSION_BLINK turns the radar at the target base dark for `decoy_blink.dark_s`
  (`DirectorState.dark` holds when it resumes), then it may not blink again for `cooldown_s`
  (`blink_ready`); at most one radar blinks per window (Q-SIM-82).
- **INTEL (step 5).** An operation whose RAISE counter is a defensive one (`convoy_attacks`,
  `radar_strikes`) and above zero announces `ThreatAdaptation UP` for that category, once, at the
  sector level; when the counter has decayed below one event it announces `DOWN`.
"""

import itertools
import math
from collections.abc import Callable
from fractions import Fraction

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core import operations as ops
from nexus.core.director import night_capped, surplus
from nexus.core.fog import SideView, is_off_facility
from nexus.core.logistics import plan_deploy
from nexus.core.rng import RngStream
from nexus.core.roads import shortest_path
from nexus.core.rules import DirectorRules, JobTemplate, OperationRules, Rules, sector_at
from nexus.core.tasking import post_job, take
from nexus.core.tasking_gen import JobSpec, fits
from nexus.core.world import DirectorState, Entity, Job, Vec2, World, consumed

_DIRECTOR = "ENEMY_DIRECTOR"
# Defensive counter -> the adaptation it announces (ThreatAdaptation.category).
_ADAPTATION = {"convoy_attacks": "CONVOY_ESCORT", "radar_strikes": "IADS_REINFORCED"}
_MOVERS = ("AIR", "GROUND")
_PATROL_OP, _CONVOY_OP = "POL_PATROL", "POL_CONVOY"  # the `op:` ids of the Pattern of Life jobs


def _routine(dr: DirectorRules) -> frozenset[str]:
    """Operations ALPHA's one-at-a-time rule skips: the catalog's routine ones and the Pattern of
    Life patrols and convoys, which are no catalog entries."""
    return ops.routine_ops(dr) | {_PATROL_OP, _CONVOY_OP}


def _own(world: World, rules: Rules, side: Side) -> ops.Own:
    dr = rules.director
    share = dr.reinforce_above if dr is not None else Fraction(0)
    state, now = world.director[side], world.campaign.running_ticks + 1
    escorted = {j.entity for j in world.boards[side].values() if j.kind == "ESCORT_CONVOY"}
    cr = rules.combat
    convoys: list[tuple[int, str]] = []
    damaged: set[str] = set()
    radars: set[str] = set()
    live = 0
    homed: dict[str, list[UnitKind]] = {}
    for e in world.entities():
        if e.side != side:
            continue
        live += rules.domain[e.kind] in _MOVERS
        if e.home is not None and e.owner_kind == _DIRECTOR:
            homed.setdefault(e.home, []).append(e.kind)
        if (
            e.kind in rules.supply.carriers
            and e.path
            and e.follow_id is None
            and e.id not in escorted
        ):
            if e.damage_state != "DISABLED":
                convoys.append((e.id, e.last_node or rules.supply.rear[side]))
        elif e.base_id is not None and e.kind == "AIR_DEFENSE_SITE":
            top = cr.units[e.kind].hp if cr is not None else 0
            if top and Fraction(top - e.hp, top) > share:
                damaged.add(e.base_id)
        elif e.base_id is not None and e.kind == "RADAR_SITE" and e.damage_state != "DISABLED":
            if state.blink_ready.get(e.base_id, 0) <= now and e.base_id not in state.dark:
                radars.add(e.base_id)  # not dark, not cooling down (Q-SIM-82)
    free = {
        n: world.stock[n] - floor
        for n, floor in rules.supply.starve_floor.items()
        if world.owner.get(n) == side and n in world.stock
    }
    return ops.Own(
        tuple(convoys), frozenset(damaged), frozenset(radars), live,
        {n: tuple(k) for n, k in homed.items()}, free,
    )  # fmt: skip


def look(world: World, rules: Rules, side: Side, state: DirectorState, now: int) -> None:
    """Recon memory (Q-SIM-87): every cell of the `director.recon.grid_m` grid within the sensor
    radius of one of the side's emitting units now is marked looked at, `now`; marks older than
    `director.recon.memory_s` are dropped first (their staleness is 1, as no mark). Units in id
    order, cells ascending, so the result does not depend on any iteration order."""
    dr = rules.director
    if dr is None:
        return
    step, width, height = dr.recon_grid_m, *rules.bounds_m
    state.looked = {k: t for k, t in state.looked.items() if now - t < dr.recon_memory_ticks}
    for e in world.entities():
        radius = rules.sensor_radius(e.kind, e.damage_state)
        if e.side != side or radius <= 0 or e.emitting is False or is_off_facility(rules, e):
            continue
        for x in ops.span(e.pos.x, radius, step):
            for y in ops.span(e.pos.y, radius, step):
                if (
                    0 < x <= width
                    and 0 < y <= height
                    and math.hypot(x - e.pos.x, y - e.pos.y) <= radius
                ):
                    state.looked[ops.cell_key(x, y)] = now


def run(world: World, side: Side, view: SideView, rules: Rules, out: list[Event]) -> None:
    """One window's operations for `side` (module docstring); `decide` has set the budget."""
    dr = rules.director
    if dr is None or rules.tasking is None:  # no board: no operations
        return
    state, now = world.director[side], world.campaign.running_ticks + 1
    for node in sorted(state.lost):
        if view.owners.get(node) == side or now - state.lost[node] >= dr.retake_ticks:
            del state.lost[node]
    _announce_down(world, side, state, dr, out)
    look(world, rules, side, state, now)
    _resume(world, side, state, now)
    _retire_idle(world, rules, side, state, dr, now, out)
    _recall(world, rules, side)
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()])
    capped = world.viewer_units() == 0 and night_capped(state, dr, now)  # no capture operations
    cands = ops.candidates(state, view, rules, own, now, live, capture=False if capped else None)
    ranked = ops.rank(cands, state, view, rules, world.rng.stream(RngStream.DIRECTOR))
    chosen = ops.select(
        ranked, dr, state.budget, dr.max_spawns_per_window,
        dr.max_live_units[state.tier] - own.live_units, live,
        ops.alpha_max_ops(state.tier, dr), _routine(dr),
    )  # fmt: skip
    for c in chosen:
        _launch(world, rules, side, view, state, c, out)
    _pattern_of_life(world, rules, side, view, state, capped, now, out)


def _pattern_of_life(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState, capped: bool,
    now: int, out: list[Event],
) -> None:  # fmt: skip
    """The periodic Pattern of Life work (Q-SIM-85), each on its own timer in `DirectorState`: the
    patrols, the supply convoys, and at Pattern of Life the capture operations, which wait for the
    night-progress cap and are paid from the real surplus, not the window's budget."""
    dr = rules.director
    if dr is None:
        return
    if now - state.last_patrol >= dr.patrol_ticks:
        state.last_patrol = now
        _patrols(world, rules, side, view, dr, out)
    if now - state.last_convoy >= dr.convoy_ticks:
        state.last_convoy = now
        _convoys(world, rules, side, view, state, dr, out)
    if (
        state.tier == "PATTERN_OF_LIFE"
        and not capped
        and now - state.last_offensive >= dr.offensive_ticks
    ):
        _capture_slot(world, rules, side, view, state, dr, now, out)


def _capture_slot(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    dr: DirectorRules, now: int, out: list[Event],
) -> None:  # fmt: skip
    """Up to `director.pol.offensives_per_period` capture operations, whatever their tier, ranked
    and selected as usual against the real surplus and the Pattern of Life unit room."""
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()])
    cands = ops.candidates(state, view, rules, own, now, live, capture=True)
    if not cands:
        return
    ranked = ops.rank(cands, state, view, rules, world.rng.stream(RngStream.DIRECTOR))
    chosen = ops.select(
        ranked, dr, surplus(view, rules, world.stock), dr.max_spawns_per_window,
        dr.max_live_units[state.tier] - own.live_units, live, None, _routine(dr),
    )  # fmt: skip
    if chosen:
        state.last_offensive = now
    for c in chosen[: dr.offensives_per_period]:
        _launch(world, rules, side, view, state, c, out)


def _patrols(
    world: World, rules: Rules, side: Side, view: SideView, dr: DirectorRules, out: list[Event]
) -> None:
    """Per Static base, idle ground garrison units homed there (lowest ids first) take patrol jobs
    of `director.pol.patrol_slots` units until `director.pol.patrols_per_base` are out: each
    drives to the road node toward the front, then home (Q-SIM-85, Q-SIM-86)."""
    keys = {j.key for j in world.boards[side].values()}
    idle: dict[str, list[Entity]] = {}
    for e in sorted((e for es in _spare(world, side).values() for e in es), key=lambda e: e.id):
        if e.home is not None and fits(rules, e.kind, "PATROL"):
            idle.setdefault(e.home, []).append(e)
    for base in ops.bases(view, rules):
        via, prefix = ops.patrol_via(view, rules, base), f"{ops.LIVE_PREFIX}{_PATROL_OP}:{base}:"
        if via is None:
            continue
        out_now = sum(k.startswith(prefix) for k in keys)
        crews = idle.get(base, [])
        for _ in range(max(0, dr.patrols_per_base - out_now)):
            crew, crews = crews[: dr.patrol_slots], crews[dr.patrol_slots :]
            if not crew:
                break
            key = next(k for n in itertools.count() if (k := f"{prefix}{n}") not in keys)
            keys.add(key)
            spec = JobSpec("PATROL", key, dr.patrol_slots, dr.job_urgency_milli, node=base, via=via)
            job = post_job(world, side, spec, out)
            for unit in crew:
                take(world, unit, job, out)


def _convoys(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    dr: DirectorRules, out: list[Event],
) -> None:  # fmt: skip
    """Up to `director.pol.convoys_per_period` RESUPPLY jobs, to the bases with the largest upkeep
    shortfall (one each), taken by an idle carrier of `director.pol.convoy_kind` or a new one,
    within the unit caps; a new carrier costs `director.pol.convoy_cost` from the surplus
    (Q-SIM-85)."""
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()])
    room = min(dr.max_spawns_per_window, dr.max_live_units[state.tier] - own.live_units)
    op = OperationRules(
        _CONVOY_OP, "NODE", (), dr.convoy_cost, frozenset(),
        (JobTemplate("RESUPPLY", "target", (dr.convoy_kind,), 1),), None, Fraction(0),
    )  # fmt: skip
    for base in ops.convoy_bases(view, rules, own)[: dr.convoys_per_period]:
        if (_CONVOY_OP, base) in live or room < 1 or surplus(view, rules, world.stock) < op.cost:
            continue
        cand = ops.Candidate(op, base, None, ((ops.Where(base),),))
        room -= _post_and_spawn(world, rules, side, cand, out, lambda n: op.cost * n) or 0


def _launch(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    c: ops.Candidate, out: list[Event],
) -> None:  # fmt: skip
    dr = rules.director
    if dr is None:
        return
    if c.op.effect is not None:
        _blink(world, side, state, c.target, now=world.campaign.running_ticks + 1, dr=dr)
        return
    paid = _post_and_spawn(world, rules, side, c, out, lambda n: c.op.cost * n // max(1, c.units))
    if paid is None:  # it could not pay: nothing was posted, so nothing to announce
        return
    _announce_up(world, side, view, state, dr, c, out)


def _resume(world: World, side: Side, state: DirectorState, now: int) -> None:
    """Radars whose dark time is over emit again (Q-SIM-82)."""
    for base in sorted(state.dark):
        if state.dark[base] <= now:
            del state.dark[base]
            for e in world.entities():
                if e.side == side and e.kind == "RADAR_SITE" and e.base_id == base:
                    e.emitting = True


def _blink(
    world: World, side: Side, state: DirectorState, base: str, *, now: int, dr: DirectorRules | None
) -> None:
    """DecoyBlink (FOW-11, Q-SIM-82): the base's radar goes dark for `decoy_blink.dark_s` and may
    not blink again for `cooldown_s` after it went dark."""
    if dr is None:
        return
    for e in world.entities():
        if (
            e.side == side
            and e.kind == "RADAR_SITE"
            and e.base_id == base
            and e.emitting is not None
        ):
            e.emitting = False
    state.dark[base] = now + dr.dark_ticks
    state.blink_ready[base] = now + dr.blink_cooldown_ticks


def _post_and_spawn(
    world: World, rules: Rules, side: Side, c: ops.Candidate, out: list[Event],
    cost: Callable[[int], int],
) -> int | None:  # fmt: skip
    """Post the jobs in order, pay `cost(spawned)` and give each job its units; returns how many
    were spawned, or None when the real surplus now cannot pay for them and nothing was posted:
    the window's budget is only a plan, because the operations launched before this one load
    carriers from the same surplus (`_payable`). A slot goes to an idle live unit of its kind
    first (the lowest id), which is neither spawned nor paid for (Q-SIM-84). Units take their
    jobs only after the payment, because a carrier at its source loads on taking a job, and
    loading first could leave too little surplus to pay."""
    dr = rules.director
    if dr is None:
        return 0
    garrison = c.op.target == "GARRISON"
    spare = {} if garrison else _reusable(world, side)  # a garrison replacement is always new
    if _payable(world, rules, side) < cost(_new_units(c, spare)):
        return None
    spawned = 0
    first: str | None = None
    prev: int | None = None  # the job the next step waits for
    given: list[tuple[Entity, Job]] = []
    for idx, (job, wheres) in enumerate(zip(c.op.jobs, c.wheres, strict=True)):
        last = prev
        for w in wheres:
            tail = "" if w.entity is None else f":{w.entity}"
            spec = JobSpec(
                job.kind, f"{ops.LIVE_PREFIX}{c.op.id}:{c.target}:{idx}{tail}", job.slots,
                dr.job_urgency_milli, node=w.node, depends_on=prev, entity=w.entity, pos=w.pos,
            )  # fmt: skip
            posted = post_job(world, side, spec, out)
            last = posted.id
            for n in range(job.slots):
                kind = job.unit_kinds[n % len(job.unit_kinds)]
                idle = [u for u in spare.get(kind, []) if w.origin in (None, u.last_node)]
                if idle:  # a scout for a point must rest at the base its route was checked from
                    spare[kind].remove(idle[0])
                    given.append((idle[0], posted))
                    continue
                unit, base = _spawn(
                    world, rules, side, kind, _near(world, rules, side, job, w), out,
                    at=c.target if garrison else w.origin,
                )  # fmt: skip
                first, spawned = first or base, spawned + 1
                if garrison:
                    unit.home = c.target
                given.append((unit, posted))
        prev = last
    _pay(world, rules, side, cost(spawned), first, out)
    for unit, posted in given:
        take(world, unit, posted, out)
    return spawned


def _new_units(c: ops.Candidate, spare: dict[str, list[Entity]]) -> int:
    """How many units `_post_and_spawn` will spawn for `c`: its slots less those an idle unit fills
    (the same matching, on a copy of `spare`)."""
    left = {k: list(v) for k, v in spare.items()}
    new = 0
    for job, wheres in zip(c.op.jobs, c.wheres, strict=True):
        for w in wheres:
            for n in range(job.slots):
                kind = job.unit_kinds[n % len(job.unit_kinds)]
                idle = [u for u in left.get(kind, []) if w.origin in (None, u.last_node)]
                if idle:
                    left[kind].remove(idle[0])
                else:
                    new += 1
    return new


def _spare(world: World, side: Side) -> dict[str, list[Entity]]:
    """The side's idle Director units by kind, lowest id first: no job, order or path, not
    Disabled and not homebound, so the board would let them take a job."""
    out: dict[str, list[Entity]] = {}
    for e in world.entities():
        if (
            e.side == side and e.owner_kind == _DIRECTOR and e.job_id is None and e.order is None
            and not e.path and e.damage_state != "DISABLED" and e.state != "RTB"
        ):  # fmt: skip
            out.setdefault(e.kind, []).append(e)
    return out


def _within_quota(world: World, rules: Rules, side: Side) -> set[int]:
    """The Director units that count toward their home base's garrison quota: the lowest ids homed
    at a base the side still holds, up to `garrison_quota` (Q-SIM-85)."""
    count: dict[str, int] = {}
    kept: set[int] = set()
    for e in world.entities():
        if e.side == side and e.owner_kind == _DIRECTOR and e.home is not None:
            n = count.get(e.home, 0)
            if world.owner.get(e.home) == side and n < rules.garrison_quota.get(e.home, 0):
                kept.add(e.id)
            count[e.home] = n + 1
    return kept


def _away(rules: Rules, e: Entity) -> bool:
    """A garrison unit is away from its home when it rests at another node or, an aircraft, orbits
    somewhere else."""
    if e.home is None:
        return False
    home = Vec2(*rules.roads.pos[e.home])
    return e.last_node != e.home or (e.state == "ON_STATION" and e.orbit not in (None, home))


def _recall(world: World, rules: Rules, side: Side) -> None:
    """An idle garrison unit away from its home base, while the side holds it, is sent home
    (Q-SIM-86): a ground unit by the road from the node it stands on, an aircraft straight."""
    for es in _spare(world, side).values():
        for e in es:
            if e.home is None or world.owner.get(e.home) != side or not _away(rules, e):
                continue
            if rules.domain[e.kind] == "AIR":
                e.path = [e.home]
            elif e.last_node is not None and e.pos == Vec2(*rules.roads.pos[e.last_node]):
                route = shortest_path(rules.roads, e.last_node, e.home, blocked=frozenset())
                e.path = [] if route is None else [*route]


def _reusable(world: World, side: Side) -> dict[str, list[Entity]]:
    """`_spare` without the garrison units: an operation never takes one (Q-SIM-85)."""
    return {
        kind: free for kind, es in _spare(world, side).items()
        if (free := [e for e in es if e.home is None])
    }  # fmt: skip


def _retire_idle(
    world: World,
    rules: Rules,
    side: Side,
    state: DirectorState,
    dr: DirectorRules,
    now: int,
    out: list[Event],
) -> None:
    """A Director unit with no job and no path for `director.idle_retire_s` is removed, no refund
    (Q-SIM-84); it is reported as `UnitDespawned{RETIRED}`, not a loss (no memory, stats or crew).
    `state.idle` holds the tick each was first seen idle. A carrier with cargo is kept, so
    stock + cargo + consumed stays exact. Only a unit above its home base's garrison quota (the
    highest ids) is retired: a garrison sitting at its base is never churned (Q-SIM-85)."""
    kept = _within_quota(world, rules, side)
    idle = {
        str(e.id) for es in _spare(world, side).values() for e in es
        if not e.cargo and e.id not in kept
    }  # fmt: skip
    for key in sorted(state.idle, key=int):
        if key not in idle:
            del state.idle[key]
    for key in sorted(idle, key=int):
        since = state.idle.setdefault(key, now)
        if now - since >= dr.idle_retire_ticks and (e := world.find(int(key))) is not None:
            del state.idle[key]
            world.remove(e.id)
            out.append(
                UnitDespawned.model_construct(
                    kind="UnitDespawned", tick=world.campaign.tick + 1,
                    event_seq=world.next_event_seq(), campaign_id=world.campaign.id,
                    entity_id=e.id, reason="RETIRED",
                )
            )  # fmt: skip


def _near(world: World, rules: Rules, side: Side, job: JobTemplate, w: ops.Where) -> str:
    """The node a unit for this job should spawn near: the job's node, or the convoy's."""
    if w.node is not None:
        return w.node
    convoy = world.find(w.entity or 0)
    return (convoy.last_node if convoy else None) or rules.supply.rear[side]


def _spawn(
    world: World, rules: Rules, side: Side, kind: str, near: str, out: list[Event], *,
    at: str | None = None,
) -> tuple[Entity, str]:  # fmt: skip
    """One Director unit at `plan_deploy`'s base for a job at `near`, else the rear source; at
    `at` instead when given (a garrison replacement is raised at its own base, Q-SIM-85)."""
    deploy = None if at else plan_deploy(world, rules, side, kind, near)  # type: ignore[arg-type]
    node = at or (deploy[0] if deploy else rules.supply.rear[side])
    unit = world.spawn(kind, side, _DIRECTOR, Vec2(*rules.roads.pos[node]))  # type: ignore[arg-type]
    unit.last_node = node
    if kind in rules.supply.carriers:
        unit.cargo = 0
    if rules.domain[unit.kind] == "AIR":
        unit.state, unit.fuel = "LANDED", rules.fuel_s[unit.kind]
    out.append(
        UnitSpawned.model_construct(
            kind="UnitSpawned", tick=world.campaign.tick + 1, event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id, entity_id=unit.id, unit_kind=unit.kind, side=side,
            owner_kind=_DIRECTOR, commander_id=None, callsign=None, node_id=node, loadout="FULL",
        )
    )  # fmt: skip
    return unit, node


def _payable(world: World, rules: Rules, side: Side) -> int:
    """What `_pay` can debit now: the stock above the floor of the side's finite-stock bases."""
    return sum(
        max(0, world.stock[n] - floor)
        for n, floor in rules.supply.starve_floor.items()
        if world.owner.get(n) == side and n in world.stock
    )


def _pay(
    world: World, rules: Rules, side: Side, cost: int, prefer: str | None, out: list[Event]
) -> None:
    """Debit `cost` from the surplus of the side's finite-stock bases (module docstring)."""
    order = sorted(rules.supply.starve_floor, key=lambda n: (n != prefer, n))
    for node in order:
        if cost <= 0:
            break
        if world.owner.get(node) != side or node not in world.stock:
            continue
        take_ = min(cost, max(0, world.stock[node] - rules.supply.starve_floor[node]))
        if take_:
            world.stock[node] -= take_
            out.append(consumed(world, node, take_, "SPAWN"))
            cost -= take_
    if cost > 0:
        raise ValueError(f"the Director's budget exceeded the stock by {cost}")


def _adaptation(
    world: World, side: Side, category: str, sector: str, direction: str, out: list[Event]
) -> None:
    out.append(
        ThreatAdaptation.model_construct(
            kind="ThreatAdaptation", tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(), campaign_id=world.campaign.id, side=side,
            category=category, sector_id=sector, direction=direction,
        )
    )  # fmt: skip


def _announce_up(
    world: World, side: Side, view: SideView, state: DirectorState, dr: DirectorRules,
    c: ops.Candidate, out: list[Event],
) -> None:  # fmt: skip
    memory = c.op.memory
    if memory is None or memory[1] != "RAISE" or memory[0] not in _ADAPTATION:
        return
    category = _ADAPTATION[memory[0]]
    if getattr(state, memory[0]) <= dr.up_above or category in state.adapted:
        return
    sector = c.sector
    if sector is None:  # CONVOYS: where the first escorted convoy is
        w = c.wheres[0][0]
        convoy = world.find(w.entity or 0)
        sector = (
            sector_at(world.rules, convoy.pos.x, convoy.pos.y) if convoy and world.rules else None
        )
    if sector is not None:
        state.adapted[category] = sector
        _adaptation(world, side, category, sector, "UP", out)


def _announce_down(
    world: World, side: Side, state: DirectorState, dr: DirectorRules, out: list[Event]
) -> None:
    for counter, category in _ADAPTATION.items():
        sector = state.adapted.get(category)
        if sector is not None and getattr(state, counter) < dr.down_below:
            del state.adapted[category]
            _adaptation(world, side, category, sector, "DOWN", out)
