"""Coalition AI trucks, the logistics cadence (GAMEPLAY §5 LC-1, LC-5; NX-473, Q-TD-92).

At every economy window (`economy.due`), after upkeep and before the Threat Director (EC-10):

1. **Retire.** A coalition AI truck (an `AI_GARRISON` carrier) the board may task (`is_idle`)
   with no cargo for `director.idle_retire_s` is removed, `UnitDespawned{RETIRED}`, the Static's
   rule (Q-SIM-84); a loaded one is kept, so stock + cargo + consumed stays exact. The clock is
   the coalition's `DirectorState.idle` (an existing snapshot field the coalition never used).
2. **Spawn**, only at the windows whose running tick is a multiple of
   `logistics.ai_trucks.period_s` (`Supply.ai_truck_period_ticks`, whole windows, so no state).
   The coalition's `resupply:` jobs, best first (`tasking.rank` with no tie draw: priority, then
   job id), that were posted at least one period ago (viewers get the first pick; such a job
   does not expire unclaimed, `tasking.unexpiring`, so its age counts from its first posting,
   Q-SIM-131, NX-492) give each slot no claim holds to an idle AI truck first (the board pass
   of this tick tasks it), else to a new `LOGI` truck, while live AI trucks are fewer than
   `logistics.ai_trucks.max_live` and the EC-8 guard has room. A new truck spawns where
   `!join logi <node>` would (`plan_run`, the §1b source, the sanctuary last), loads there, pays
   its `logistics.loadout_cost` at that node (EC-13) and claims the job; a job whose run loads
   nothing gets no truck.

An AI truck is no viewer unit (`World.viewer_units` counts COMMANDER units). Deterministic: jobs
by rank then id, entities by id, integers, no RNG (LC-5).
"""

from nexus.contracts.gen.common.enums import OwnerKind, Role, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.bridges import enemy_held
from nexus.core.economy import due, guard_room, source_stock
from nexus.core.logistics import Run, load, pay_spawn, plan_run
from nexus.core.rules import Rules
from nexus.core.tasking import claim, rank
from nexus.core.tasking_gen import is_idle
from nexus.core.world import JOB_KEY_PREFIX, Entity, Job, Vec2, World, is_ai_truck

_SIDE: Side = "COALITION"
_AI: OwnerKind = "AI_GARRISON"
_ROLE: Role = "LOGI"  # the role whose kind an AI truck is: where `!join logi` would spawn it


def ai_trucks(world: World, out: list[Event]) -> None:
    """LC-1 at an economy window (module docstring)."""
    if due(world) is None or world.rules is None or world.rules.tasking is None:
        return
    rules = world.rules
    now = world.campaign.running_ticks + 1
    _retire(world, rules, now, out)
    period = rules.supply.ai_truck_period_ticks
    if period and now % period == 0:
        _spawn_for_jobs(world, rules, now, period, out)


def _trucks(world: World, rules: Rules) -> list[Entity]:
    """The coalition's AI trucks (`world.is_ai_truck`), by id."""
    return [e for e in world.entities() if is_ai_truck(rules, e)]


def _retire(world: World, rules: Rules, now: int, out: list[Event]) -> None:
    dr = rules.director
    if dr is None:
        return
    state = world.director[_SIDE]
    idle = {str(e.id) for e in _trucks(world, rules) if is_idle(rules, e, _SIDE) and not e.cargo}
    for key in sorted(state.idle, key=int):
        if key not in idle:
            del state.idle[key]
    for key in sorted(idle, key=int):
        since = state.idle.setdefault(key, now)
        if now - since >= dr.idle_retire_ticks:
            del state.idle[key]
            world.remove(int(key))
            out.append(
                UnitDespawned.model_construct(
                    kind="UnitDespawned", tick=world.campaign.tick + 1,
                    event_seq=world.next_event_seq(), campaign_id=world.campaign.id,
                    entity_id=int(key), reason="RETIRED",
                )
            )  # fmt: skip


def _spawn_for_jobs(world: World, rules: Rules, now: int, period: int, out: list[Event]) -> None:
    tr = rules.tasking
    kind = rules.role_kind.get(_ROLE)
    if tr is None or kind is None:
        return
    trucks = _trucks(world, rules)
    spare = sum(is_idle(rules, e, _SIDE) for e in trucks)
    room = min(rules.supply.ai_truck_max_live - len(trucks), guard_room(world, _SIDE))
    jobs = [
        j for j in world.boards[_SIDE].values()
        if j.key.startswith(JOB_KEY_PREFIX["RESUPPLY"]) and now - j.created >= period
    ]  # fmt: skip
    held = enemy_held(world, rules, _SIDE)
    for job in rank(tr, jobs, now, None, side=_SIDE):
        for _ in range(max(0, job.slots - len(job.claims))):
            if spare:
                spare -= 1  # an idle AI truck goes first: the board pass tasks it
                continue
            if room <= 0 or not _spawn(world, rules, kind, job, held, out):
                break
            room -= 1
        if room <= 0 and not spare:
            return


def _spawn(
    world: World, rules: Rules, kind: UnitKind, job: Job, held: frozenset[str], out: list[Event]
) -> bool:
    """One new AI truck for `job` at its run's source, loaded, paid and claiming; False when the
    run loads nothing or the source cannot pay the spawn cost on top of the cargo."""
    run = plan_run(world, rules, _SIDE, job.node or "", held=held)
    if run is None or run.cargo <= 0:
        return False
    cost = rules.supply.loadout_cost.get(kind, 0)
    have = source_stock(world, run.source)  # None: an infinite source
    floor = rules.supply.starve_floor.get(run.source, 0)
    if cost > 0 and have is not None and have - floor - run.cargo < cost:
        return False
    unit = world.spawn(kind, _SIDE, _AI, Vec2(*rules.roads.pos[run.source]))
    unit.last_node = unit.home_base = run.source  # its spawn node pays its upkeep (EC-5)
    unit.path, unit.cargo = list(run.route), run.cargo
    load(world, Run(run.source, run.cargo, []))
    pay_spawn(world, run.source, cost, out)
    out.append(
        UnitSpawned.model_construct(
            kind="UnitSpawned", tick=world.campaign.tick + 1, event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id, entity_id=unit.id, unit_kind=unit.kind, side=_SIDE,
            owner_kind=_AI, commander_id=None, callsign=None, node_id=run.source, loadout="FULL",
        )
    )  # fmt: skip
    claim(world, unit, job, out)
    return True
