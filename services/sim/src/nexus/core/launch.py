"""The Director's operations in the world: pick, pay, spawn, post (THREAT-DIRECTOR §4 steps 5-8,
TD-2, Q-TD-8, Q-TD-12, Q-SIM-81; NX-156). Where `nexus.core.operations` decides from a view, this
module touches the world, in the `director` slot right after `nexus.core.director.decide`.

Each window: the Retake clocks are pruned; `Own` is read; candidates are ranked with the `director`
stream and selected within `DirectorState.budget` and the unit caps; each selected operation is
launched in selection order:
- **Pay.** "The budget is the stock" (Q-TD-12): the operation's cost is debited from the surplus of
  the side's finite-stock bases (above their starvation floors), the base its first unit spawned at
  first, then the rest in id order, one `SupplyConsumed{SPAWN}` per base. Units cost nothing more
  (no loadout charge), so the sum of costs never exceeds the real surplus.
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

from fractions import Fraction

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core import operations as ops
from nexus.core.fog import SideView
from nexus.core.logistics import plan_deploy
from nexus.core.rng import RngStream
from nexus.core.rules import DirectorRules, JobTemplate, Rules, sector_at
from nexus.core.tasking import post_job, take
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import DirectorState, Entity, Vec2, World, consumed

_DIRECTOR = "ENEMY_DIRECTOR"
# Defensive counter -> the adaptation it announces (ThreatAdaptation.category).
_ADAPTATION = {"convoy_attacks": "CONVOY_ESCORT", "radar_strikes": "IADS_REINFORCED"}
_MOVERS = ("AIR", "GROUND")


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
    for e in world.entities():
        if e.side != side:
            continue
        live += rules.domain[e.kind] in _MOVERS
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
    return ops.Own(tuple(convoys), frozenset(damaged), frozenset(radars), live)


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
    _resume(world, side, state, now)
    _retire_idle(world, side, state, dr, now, out)
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()])
    cands = ops.candidates(state, view, rules, own, now, live)
    ranked = ops.rank(cands, state, view, rules, world.rng.stream(RngStream.DIRECTOR))
    chosen = ops.select(
        ranked, dr, state.budget, dr.max_spawns_per_window,
        dr.max_live_units[state.tier] - own.live_units, live,
        ops.alpha_max_ops(state.tier, dr), ops.routine_ops(dr),
    )  # fmt: skip
    for c in chosen:
        _launch(world, rules, side, view, state, c, out)


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
    first, spawned = _post_and_spawn(world, rules, side, c, out)
    _pay(world, rules, side, c.op.cost * spawned // max(1, c.units), first, out)
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
    world: World, rules: Rules, side: Side, c: ops.Candidate, out: list[Event]
) -> tuple[str | None, int]:
    """Post the jobs in order and give each its units; returns the first spawned unit's base and
    how many were spawned. A slot goes to an idle live unit of its kind first (the lowest id),
    which is neither spawned nor paid for (Q-SIM-84)."""
    dr = rules.director
    if dr is None:
        return None, 0
    spare = _spare(world, side)
    spawned = 0
    first: str | None = None
    prev: int | None = None  # the job the next step waits for
    for idx, (job, wheres) in enumerate(zip(c.op.jobs, c.wheres, strict=True)):
        last = prev
        for w in wheres:
            tail = "" if w.entity is None else f":{w.entity}"
            spec = JobSpec(
                job.kind, f"{ops.LIVE_PREFIX}{c.op.id}:{c.target}:{idx}{tail}", job.slots,
                dr.job_urgency_milli, node=w.node, depends_on=prev, entity=w.entity,
            )  # fmt: skip
            posted = post_job(world, side, spec, out)
            last = posted.id
            for n in range(job.slots):
                kind = job.unit_kinds[n % len(job.unit_kinds)]
                if spare.get(kind):
                    take(world, spare[kind].pop(0), posted, out)
                    continue
                unit, base = _spawn(
                    world, rules, side, kind, _near(world, rules, side, job, w), out
                )
                first, spawned = first or base, spawned + 1
                take(world, unit, posted, out)
        prev = last
    return first, spawned


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


def _retire_idle(
    world: World, side: Side, state: DirectorState, dr: DirectorRules, now: int, out: list[Event]
) -> None:
    """A Director unit with no job and no path for `director.idle_retire_s` is removed, no refund
    (Q-SIM-84); it is reported as `UnitDespawned{RETIRED}`, not a loss (no memory, stats or crew).
    `state.idle` holds the tick each was first seen idle. A carrier with cargo is kept, so
    stock + cargo + consumed stays exact."""
    idle = {str(e.id) for es in _spare(world, side).values() for e in es if not e.cargo}
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
    world: World, rules: Rules, side: Side, kind: str, near: str, out: list[Event]
) -> tuple[Entity, str]:
    """One Director unit at `plan_deploy`'s base for a job at `near`, else the rear source."""
    deploy = plan_deploy(world, rules, side, kind, near)  # type: ignore[arg-type]  # a UnitKind
    node = deploy[0] if deploy else rules.supply.rear[side]
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
