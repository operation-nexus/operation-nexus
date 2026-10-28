"""The Director's operations in the world: pick, pay, spawn, post (THREAT-DIRECTOR §4 steps 5-8,
TD-2, Q-TD-8, Q-TD-12, Q-SIM-81; NX-156). Where `nexus.core.operations` decides from a view, this
module touches the world, in the `director` slot right after `nexus.core.director.decide`.

Each window: the Retake clocks are pruned; `Own` is read; candidates are ranked with the `director`
stream and selected within `DirectorState.budget` and the unit caps; each selected operation is
launched in selection order:
- **Pay.** "The budget is the stock" (Q-TD-12): under `economy.legacy_rules` the operation's cost
  is debited from the surplus of the side's finite-stock bases (above their starvation floors), the
  base its first unit spawned at first, then the rest in id order, one `SupplyConsumed{SPAWN}` per
  base. Otherwise (ECONOMY EC-13, NX-412 part 3) it is drawn once, at the one node where all its
  new units spawn (`_paying_node`), from one of the window's two accounts (`_Purse`): the base
  `plan_deploy` picks for its first unit (a garrison replacement's own base, a scout's checked
  origin) when that base's surplus pays it and it fits the base account; else the source when
  the rear account (`director.rear_share`) and the pool cover it; else it is dropped this window.
  A side in unlimited mode has no pool (EC-15) and one account, the whole budget, for base and
  source spawns alike; its source is never debited. The capture slot
  and the Pattern of Life convoys use the real surplus as their base account and share the
  window's rear account, so the pool pays at most `rear_share` a window. Units
  cost nothing more (no loadout charge). The window's budget is a plan: an operation whose cost
  cannot be paid at launch (earlier ones loaded carriers from the same stock) is skipped whole,
  never part-paid.
- **Spawn (Q-TD-8).** One unit per slot, kinds in turn, owned by the ENEMY_DIRECTOR, full of fuel
  and rounds, at `plan_deploy`'s base for the unit's job (GP-7: the nearest base with surplus,
  else the rear source), planned on the stock before the debit.
- **Jobs.** Each template job is posted by `post_job` on the side's board, in order, the key
  `op:<operation>:<target>:<job index>[:<convoy>]`, each depending on the job posted just before
  it (the last of the previous step); its units claim it at once (`tasking.take`).
- **Room.** The units must fit `max_spawns_per_window` and the live room: below
  `director.max_live_units.<tier>` under `economy.legacy_rules`, else below the EC-8 guard
  `sim.max_live_units_per_side` (`economy.guard_room`). A capture operation that posts jobs
  stamps `DirectorState.last_operation` (the EC-7 cadence floor, Q-TD-54); others do not. When
  the floor is due, the cheapest capture operation with a target that base surplus plus the
  window's rear account pays (`_floor_cap`) lifts the budget and the base account to at least
  its cost (`_lift`) and is selected and launched first (`_floor_capture`, Q-TD-42, Q-TD-48),
  even with `max_ops` full: it may run while `max_ops` are running, not `max_ops + 1`
  (Q-TD-57); if it cannot pay, the lift is undone and the window selects as without it; one
  the window's other caps would skip lifts nothing. The cheapest-operation floor
  (`director.cadence_floor`, no capture target needed) counts the same payable money and lifts
  the base account to its cost the same way, before the capture floor (NX-434). The floor is
  not due while an operation is staged (`director.cadence_due`), and each window `_review`
  keeps, launches or drops one stamps `last_operation` (a staged operation is always a capture
  one), so it counts from the drop.
  Operations the budget and `max_spawns_per_window` allow but the live room does not are counted
  in one `SpawnRefused` per selection (EC-8, `GUARD` or `TIER_CAP`; NX-412 part 5a).
- **Effect.** EMISSION_BLINK turns the radar at the target base dark for `decoy_blink.dark_s`
  (`DirectorState.dark` holds when it resumes), then it may not blink again for `cooldown_s`
  (`blink_ready`); at most one radar blinks per window (Q-SIM-82).
- **INTEL (step 5).** An operation whose RAISE counter is a defensive one (`convoy_attacks`,
  `radar_strikes`) and above zero announces `ThreatAdaptation UP` for that category, once, at the
  sector level; when the counter has decayed below one event it announces `DOWN`. A capture
  operation (Offensive, Retake) launched on a node of the running victory hold announces
  `ThreatAdaptation{HOLD_AT_RISK, node_id}`, once per launch, the sitrep "NULL moves on <node>,
  the hold is at risk" (ECONOMY EC-9, Q-TD-19; NX-412 part 4).
- **Forward staging (THREAT-DIRECTOR §4a, NX-416; legacy rules off).** A capture operation
  farther than `director.staging.direct_s` by road from the rear waits at its staging base
  (`nexus.core.staging`) until every node it spawns at can pay its own units, units whose
  deploy base cannot pay spawning at the source instead (`_stage`, `_review`, `_staged_shares`;
  Q-TD-38, Q-TD-39), announced as `ThreatAdaptation{STAGING}` in the base's
  sector (a re-stage only when the coalition tracks a unit at the new base, `seen_at`); it holds
  its budget share and a `max_ops` slot while it waits, and falls back by EC-13 after
  `max_wait_windows` or is dropped; while the night cap is spent it does not launch and is
  dropped where it would fall back (NX-480). Each massing sitrep is closed once in its sector (FS-9,
  Q-TD-47, NX-431; `Staged.sector`, `_close`): `STAGING_LAUNCHED` on a launch from the base,
  `STAGING_DISPERSED` on any other end or a re-stage it no longer names (`_restage`).
- **Victory-hold response (Q-TD-46, NX-430; legacy rules off).** While a coalition victory hold
  runs, a capture operation on one of its nodes never waits at a staging base (`_stage`
  launches it from the base when that pays now, with no massing sitrep, else by EC-13, the
  rear if needed), one already staged waits no longer (`_review`: it launches at its base or
  by EC-13, or is dropped), and it is outside `director.max_ops.<tier>`: neither capped nor
  counted (`select`'s `hold`). The budget, the spawn and live rooms and the one-per-target rule
  still apply; its launch announces `HOLD_AT_RISK` as above and nothing new. When the hold
  ends, a running one counts against the cap again (accepted for now; the sweep measures it).
- **Diagnostic (NX-452).** `no_capture_reason` says, for the balance harness, why a window
  launched no capture operation, from `run`'s own predicates; the sim never calls it.
"""

import itertools
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.spawn_refused import SpawnRefused
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core import operations as ops
from nexus.core import staging as stg
from nexus.core.bridges import blocked
from nexus.core.director import (
    cadence_due,
    cadence_floor,
    night_capped,
    night_spacing,
    rear_share,
    surplus,
)
from nexus.core.economy import MOVERS, guard_room
from nexus.core.fog import SideView, is_off_facility, seen_at
from nexus.core.logistics import pay_spawn, plan_deploy, plan_run, stock_targets
from nexus.core.rng import RngStream
from nexus.core.roads import shortest_path
from nexus.core.rules import (
    DirectorRules,
    JobTemplate,
    OperationRules,
    Rules,
    legacy_rules,
    sector_at,
)
from nexus.core.tasking import post_job, take
from nexus.core.tasking_gen import JobSpec, fits
from nexus.core.world import DirectorState, Entity, Job, Staged, Vec2, World, consumed

_DIRECTOR = "ENEMY_DIRECTOR"
# Defensive counter -> the adaptation it announces (ThreatAdaptation.category).
_ADAPTATION = {"convoy_attacks": "CONVOY_ESCORT", "radar_strikes": "IADS_REINFORCED"}
_PATROL_OP, _CONVOY_OP = "POL_PATROL", "POL_CONVOY"  # the `op:` ids of the Pattern of Life jobs
_LAUNCHED, _DISPERSED = "STAGING_LAUNCHED", "STAGING_DISPERSED"  # a massing's payoff (Q-TD-47)


@dataclass(slots=True)
class _Purse:
    """EC-7 (legacy rules off): the window's two accounts. `base` pays for units that spawn at a
    base (the budget less the rear share: the bases' spend share less the reserve, lifted by the
    cadence floor), `rear` (`director.rear_share`, at most the budget) for units that spawn at
    the source, so the pool pays at most its small share a window. A side in unlimited mode
    (EC-15: no pool, which never runs out) has `one` account, `base`, the whole budget, for
    spawns at bases and at the source alike."""

    base: int
    rear: int
    one: bool = False

    @classmethod
    def of(cls, budget: int, pool: int | None, dr: DirectorRules) -> "_Purse":
        if pool is None:
            return cls(budget, 0, one=True)
        rear = min(budget, rear_share(dr, pool))
        return cls(budget - rear, rear)

    def room(self, at_source: bool) -> int:
        return self.rear if at_source and not self.one else self.base

    def spend(self, at_source: bool, cost: int) -> None:
        if at_source and not self.one:
            self.rear -= cost
        else:
            self.base -= cost


def _live_room(world: World, rules: Rules, side: Side, state: DirectorState, own: ops.Own) -> int:
    """Live units the side may still add: the EC-8 guard, or under `economy.legacy_rules` the
    room below `director.max_live_units.<tier>`."""
    guard, dr = guard_room(world, side), rules.director
    if guard is not None:
        return guard
    return 0 if dr is None else dr.max_live_units[state.tier] - own.live_units


def _note_refused(world: World, side: Side, refused: list[int], out: list[Event]) -> None:
    """EC-8 (NX-412 part 5a): one `SpawnRefused` for the operations the live cap stopped in one
    selection; `GUARD` when the guard applies, else the legacy tier cap. None for no refusal."""
    if not refused:
        return
    out.append(
        SpawnRefused.model_construct(
            kind="SpawnRefused", tick=world.campaign.tick + 1, event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id, side=side,
            reason="TIER_CAP" if guard_room(world, side) is None else "GUARD",
            operations=len(refused), units=sum(refused),
        )
    )  # fmt: skip


def _routine(dr: DirectorRules) -> frozenset[str]:
    """Operations the `director.max_ops.<tier>` caps skip: the catalog's routine ones and the
    Pattern of Life patrols and convoys, which are no catalog entries."""
    return ops.routine_ops(dr) | {_PATROL_OP, _CONVOY_OP}


def _night_capped(
    world: World, rules: Rules, state: DirectorState, dr: DirectorRules, now: int
) -> bool:
    """The night cap bars capture operations at the faded spacing for the live viewer units
    (Q-TD-93); without capture rules there is no fade: it holds at no live viewer unit only."""
    viewers = world.viewer_units()
    if rules.capture is None:
        return viewers == 0 and night_capped(state, dr, now, dr.night_cap_ticks)
    return night_capped(state, dr, now, night_spacing(dr, viewers, rules.capture.quiet_ref))


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
        live += rules.domain[e.kind] in MOVERS
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
    jobs = world.boards[side].values()  # the bridges its live STRIKE jobs name (NX-401)
    struck = frozenset(j.node for j in jobs if j.kind == "STRIKE" and j.node in world.bridge_hp)
    return ops.Own(
        tuple(convoys), frozenset(damaged), frozenset(radars), live,
        {n: tuple(k) for n, k in homed.items()}, free, struck,
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
    pool = world.pool.get(side)  # unchanged since `decide` set the budget; None: unlimited
    purse = None if legacy_rules(rules) else _Purse.of(state.budget, pool, dr)
    if purse is not None:  # the cheapest-operation floor lifts the base account too (NX-434)
        cheapest = cadence_floor(state, view, rules, _floor_cap(world, rules, view, purse))
        _lift(purse, state, cheapest)
    capped = _night_capped(world, rules, state, dr, now)  # no capture operations, staged too
    held = _review(world, rules, side, view, state, out, purse, capped)
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()]) | stg.pairs(state)
    cands = ops.candidates(state, view, rules, own, now, live, capture=False if capped else None)
    ranked = ops.rank(cands, state, view, rules, world.rng.stream(RngStream.DIRECTOR))
    room, most = _live_room(world, rules, side, state, own), ops.max_ops(state.tier, dr)
    hold = frozenset() if purse is None else view.hold  # outside `max_ops` (Q-TD-46)

    def fits(c: ops.Candidate) -> bool:  # `select`'s caps on `c` as the floor's lead, cost given
        return bool(ops.select(
            [c], dr, c.op.cost, dr.max_spawns_per_window, room, live, most, _routine(dr),
            over=c, hold=hold,
        ))  # fmt: skip

    lead = None if purse is None else _floor_capture(world, rules, view, state, ranked, purse, fits)
    unlifted = (purse.base, state.budget) if purse is not None else (0, state.budget)
    if purse is not None and lead is not None:  # no staged operation, so `held` is 0
        _lift(purse, state, lead.op.cost)
        ranked = [lead, *(c for c in ranked if c is not lead)]

    def pick(cands: list[ops.Candidate], refused: list[int]) -> list[ops.Candidate]:
        return ops.select(
            cands, dr, state.budget - held, dr.max_spawns_per_window, room, live, most,
            _routine(dr), refused, over=lead, hold=hold,
        )  # fmt: skip

    refused: list[int] = []
    chosen = pick(ranked, refused)
    if purse is not None and lead is not None and chosen[:1] == [lead]:
        chosen = chosen[1:]
        if not _launch(world, rules, side, view, state, lead, out, purse):
            # it could not pay after all (Q-TD-48 (6)): the floor lifts nothing, so the window
            # buys what it would have without the lead
            purse.base, state.budget = unlifted
            refused = []
            chosen = pick([c for c in ranked if c is not lead], refused)
    _note_refused(world, side, refused, out)
    for c in chosen:
        _launch(world, rules, side, view, state, c, out, purse)
    _pattern_of_life(world, rules, side, view, state, capped, now, out, purse)


def _floor_capture(
    world: World, rules: Rules, view: SideView, state: DirectorState, ranked: list[ops.Candidate],
    purse: _Purse, fits: Callable[[ops.Candidate], bool],
) -> ops.Candidate | None:  # fmt: skip
    """ECONOMY EC-7, Q-TD-42 (legacy rules off): when the cadence floor is due, the best-ranked
    target of the cheapest capture operation (`ops.has_capture`) among the window's candidates
    (its tier, the night cap) that the window can actually pay and the window's caps allow
    (`fits`: the spawn and live rooms, `max_ops` with one slot over, Q-TD-57); None leaves the
    floor at the cheapest operation (`director.cadence_floor`). Payable is `_floor_cap`, base
    surplus plus this window's rear account, not surplus + pool (Q-TD-48 (5)): the lift goes to
    the base account, so pool money beyond the rear share would promote an operation that cannot
    pay and crowd out cheaper ones the rear account could."""
    if not cadence_due(state, view, rules):
        return None
    cap = _floor_cap(world, rules, view, purse)
    caps = [c for c in ranked if ops.has_capture(c.op) and c.op.cost <= cap and fits(c)]
    least = min((c.op.cost for c in caps), default=None)
    return next((c for c in caps if c.op.cost == least), None)


def _floor_cap(world: World, rules: Rules, view: SideView, purse: _Purse) -> int:
    """EC-7, Q-TD-48 (5): what a cadence floor counts as affordable this window, base surplus
    plus the window's rear account (an unlimited side's one account adds nothing), never the
    whole pool; both floors use it (NX-434)."""
    return surplus(view, rules, world.stock) + (0 if purse.one else purse.rear)


def _lift(purse: _Purse, state: DirectorState, cost: int) -> None:
    """A cadence floor's lift: the budget and the base account to at least `cost`, so the base
    account alone can pay it at a base; the rear account is unchanged (Q-TD-48, NX-434)."""
    purse.base = max(purse.base, cost)
    state.budget = max(state.budget, cost)


# NX-452: why a window launched no capture operation, in priority order (`no_capture_reason`)
NO_CAPTURE = (
    "staged", "night_cap", "tier", "no_target", "targets_busy", "budget", "floor_not_due",
    "max_ops", "other",
)  # fmt: skip


def no_capture_reason(world: World, side: Side, view: SideView, rules: Rules, now: int) -> str:
    """NX-452, a harness diagnostic, never called by the sim: why the decision window that ran at
    running tick `now` launched no capture operation (Offensive, Retake), for a caller that knows
    it launched none. It reads the world after the window and changes nothing: no state, no
    event, no RNG draw (no `rank`). The first that holds, in `run`'s own check order, with its
    predicates: `staged` (an operation waits at a staging base: `_review` runs first, it holds
    budget and a `max_ops` slot and the floor is not due); `night_cap` (`night_capped` at the
    faded spacing for the live viewer units, none from `quiet_ref` on: no capture candidates);
    `tier` (no capture operation is enabled at the tier, e.g. Pattern of Life);
    `no_target` (no capture candidate, `ops.candidates`, even with no
    operation live); `targets_busy` (there are some, but a running or staged capture operation
    already covers each: the same call with the live pairs); then the
    cheapest candidate against the money, the window's budget or, with the floor due
    (`cadence_due`, legacy rules off), what the floor counts (`_floor_cap`): `budget` (more than
    either), `floor_not_due` (more than the budget but the floor would count it, were it due);
    `max_ops` (`ops.select` takes an affordable one only with no `max_ops` cap, one over for the
    floor's lead as `_floor_capture` allows it: the floor due and its cost within `_floor_cap`);
    `other` (the spawn or live room, money the window's better-ranked operations
    spent first, or a payment that failed at launch). Read after the window, money that window
    already spent counts as spent."""
    dr = rules.director
    if dr is None:
        raise ValueError("no_capture_reason needs the Director rules")
    state = world.director[side]
    if state.staged:
        return "staged"
    if _night_capped(world, rules, state, dr, now):
        return "night_cap"
    if not any(ops.has_capture(o) and state.tier in o.tiers for o in dr.operations):
        return "tier"
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()]) | stg.pairs(state)

    def capture(pairs: frozenset[tuple[str, str]]) -> list[ops.Candidate]:
        return [
            c for c in ops.candidates(state, view, rules, own, now, pairs) if ops.has_capture(c.op)
        ]

    if not capture(frozenset()):
        return "no_target"
    if not (caps := capture(live)):
        return "targets_busy"
    purse = None if legacy_rules(rules) else _Purse.of(state.budget, world.pool.get(side), dr)
    cap = None if purse is None else _floor_cap(world, rules, view, purse)
    floor = cap is not None and cadence_due(state, view, rules)
    money = max(state.budget, cap) if floor and cap is not None else state.budget
    cheapest = min(c.op.cost for c in caps)
    if cheapest > money:
        return "floor_not_due" if cap is not None and cheapest <= cap else "budget"
    room, hold = (
        _live_room(world, rules, side, state, own),
        view.hold if purse is not None else frozenset(),
    )

    def taken(c: ops.Candidate, most: int | None) -> bool:
        return bool(ops.select(
            [c], dr, c.op.cost, dr.max_spawns_per_window, room, live, most, _routine(dr),
            over=c if floor and cap is not None and c.op.cost <= cap else None, hold=hold,
        ))  # fmt: skip

    paid = [c for c in caps if c.op.cost <= money]
    capped = not any(taken(c, ops.max_ops(state.tier, dr)) for c in paid)
    return "max_ops" if capped and any(taken(c, None) for c in paid) else "other"


def _pattern_of_life(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState, capped: bool,
    now: int, out: list[Event], purse: _Purse | None = None,
) -> None:  # fmt: skip
    """The periodic Pattern of Life work (Q-SIM-85), each on its own timer in `DirectorState`: the
    patrols, the supply convoys, and at the `director.pol.capture_slot_tiers` (Pattern of Life by
    default) the capture operations, which wait for the night-progress cap and are paid from the
    real surplus, not the window's budget. With legacy rules off a convoy or capture operation
    that spawns at the source still spends the window's rear account (`purse`)."""
    dr = rules.director
    if dr is None:
        return
    if now - state.last_patrol >= dr.patrol_ticks:
        state.last_patrol = now
        _patrols(world, rules, side, view, dr, out)
    if now - state.last_convoy >= dr.convoy_ticks:
        state.last_convoy = now
        _convoys(world, rules, side, view, state, dr, out, purse)
    if (
        state.tier in dr.capture_slot_tiers
        and not capped
        and now - state.last_offensive >= dr.offensive_ticks
    ):
        _capture_slot(world, rules, side, view, state, dr, now, out, purse)


def _capture_slot(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    dr: DirectorRules, now: int, out: list[Event], purse: _Purse | None,
) -> None:  # fmt: skip
    """Up to `director.pol.offensives_per_period` capture operations, whatever their tier, ranked
    and selected as usual against the real surplus and the Pattern of Life unit room."""
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()]) | stg.pairs(state)
    cands = ops.candidates(state, view, rules, own, now, live, capture=True)
    if not cands:
        return
    ranked = ops.rank(cands, state, view, rules, world.rng.stream(RngStream.DIRECTOR))
    refused: list[int] = []
    chosen = ops.select(
        ranked, dr, surplus(view, rules, world.stock), dr.max_spawns_per_window,
        _live_room(world, rules, side, state, own), live, None, _routine(dr), refused,
    )  # fmt: skip
    _note_refused(world, side, refused, out)
    if chosen:
        state.last_offensive = now
    spend = _surplus_purse(view, rules, world, purse)
    for c in chosen[: dr.offensives_per_period]:
        _launch(world, rules, side, view, state, c, out, spend)
    _keep_rear(purse, spend)


def _patrols(
    world: World, rules: Rules, side: Side, view: SideView, dr: DirectorRules, out: list[Event]
) -> None:
    """Per Static base, idle ground garrison units homed there (lowest ids first) take patrol jobs
    of `director.pol.patrol_slots` units until `director.pol.patrols_per_base` are out: each
    drives to the road node toward the front, then home (Q-SIM-85, Q-SIM-86)."""
    keys = {j.key for j in world.boards[side].values()}
    idle: dict[str, list[Entity]] = {}
    for e in sorted((e for es in _spare(world, side).values() for e in es), key=lambda e: e.id):
        if (
            e.home is not None
            and rules.domain[e.kind] == "GROUND"
            and fits(rules, e.kind, "PATROL")
        ):
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
    dr: DirectorRules, out: list[Event], purse: _Purse | None,
) -> None:  # fmt: skip
    """Up to `director.pol.convoys_per_period` RESUPPLY jobs, to the bases with the largest upkeep
    shortfall (one each), taken by an idle carrier of `director.pol.convoy_kind` or a new one,
    within the unit caps; a new carrier costs `director.pol.convoy_cost` from the surplus
    (Q-SIM-85), and only when a truck has a route there (`plan_run`, around enemy-held nodes;
    NX-413). A staging base below its raised stock target goes first (THREAT-DIRECTOR FS-3)."""
    own = _own(world, rules, side)
    live = ops.live_pairs([j.key for j in world.boards[side].values()])
    spawns, live_room = dr.max_spawns_per_window, _live_room(world, rules, side, state, own)
    refused: list[int] = []
    op = OperationRules(
        _CONVOY_OP, "NODE", (), dr.convoy_cost, frozenset(),
        (JobTemplate("RESUPPLY", "target", (dr.convoy_kind,), dr.convoy_slots),), None, Fraction(0),
    )  # fmt: skip
    targets = stock_targets(world, rules)  # a staging base below its raised target first (FS-3)
    first = [s.base for s in state.staged if world.stock.get(s.base, 0) < targets.get(s.base, 0)]
    for base in [*dict.fromkeys([*first, *ops.convoy_bases(view, rules, own)])][
        : dr.convoys_per_period
    ]:
        if (_CONVOY_OP, base) in live or surplus(view, rules, world.stock) < op.cost:
            continue
        if plan_run(world, rules, side, base) is None:  # no truck could reach it (NX-413)
            continue
        if min(spawns, live_room) < dr.convoy_slots:  # the job spawns up to `convoy_slots` units
            if spawns >= dr.convoy_slots:  # the live cap, not anti-spam, stopped it (EC-8)
                refused.append(dr.convoy_slots)
            continue
        cand = ops.Candidate(op, base, None, ((ops.Where(base),),))
        spend = _surplus_purse(view, rules, world, purse)
        made = _post_and_spawn(world, rules, side, cand, out, lambda n: op.cost * n, spend) or 0
        spawns, live_room = spawns - made, live_room - made
        _keep_rear(purse, spend)
    _note_refused(world, side, refused, out)


def _surplus_purse(
    view: SideView, rules: Rules, world: World, purse: _Purse | None
) -> _Purse | None:
    """The accounts of a spend from the real base surplus (a convoy, the capture slot): the
    surplus for base spawns, what is left of the window's rear account for source spawns."""
    if purse is None:
        return None
    return _Purse(surplus(view, rules, world.stock), purse.rear, purse.one)


def _keep_rear(purse: _Purse | None, spend: _Purse | None) -> None:
    if purse is not None and spend is not None:
        purse.rear = spend.rear


def _launch(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    c: ops.Candidate, out: list[Event], purse: _Purse | None = None, at: str | None = None,
    stage: bool = True,
) -> bool:  # fmt: skip
    """Launch `c`; True when it posted its jobs or was staged. `at` is a staged operation's base,
    where the units it hosts spawn and pay (FS-4); `stage` False never stages it (a staged one
    falling back)."""
    dr = rules.director
    if dr is None:
        return False
    if c.op.effect is not None:
        _blink(world, side, state, c.target, now=world.campaign.running_ticks + 1, dr=dr)
        return True
    if at is None and stage and _stage(world, rules, side, view, state, c, out, purse):
        return True
    paid = _post_and_spawn(
        world, rules, side, c, out, lambda n: c.op.cost * n // max(1, c.units), purse, at
    )
    if paid is None:  # it could not pay: nothing was posted, so nothing to announce
        return False
    if ops.has_capture(c.op):  # the EC-7 floor counts from capture operations only (Q-TD-54)
        state.last_operation = state.windows
    _announce_up(world, side, view, state, dr, c, out)
    if c.target in view.hold and c.sector is not None and ops.has_capture(c.op):
        _adaptation(world, side, "HOLD_AT_RISK", c.sector, "UP", out, node=c.target)
    return True


def _stage(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    c: ops.Candidate, out: list[Event], purse: _Purse | None,
) -> bool:  # fmt: skip
    """FS-1, FS-2, FS-4, FS-5 (legacy rules off, `purse` set): a far capture operation is staged
    at its base: `STAGING` is announced in the base's sector, and it launches at once when every
    node it spawns at can pay its own units (then `STAGING_LAUNCHED` there, FS-9), else waits in
    `DirectorState.staged` with that sector open. False when it
    is not staged (near, no nearer base, or `director.staging.max_staged` waiting): it spawns as
    EC-13 says. Aimed at a node of the running victory hold (Q-TD-46, FS-10) it never waits and
    says nothing: True when it launched at once from the base, else False (EC-13, the rear if
    needed)."""
    dr = rules.director
    if purse is None or dr is None:
        return False
    hold = c.target in view.hold
    if not hold and len(state.staged) >= dr.staging_max_staged:
        return False
    base = stg.base_for(world, rules, side, view, c.op, c.target)
    if base is None or not stg.far(rules, view, c.op, c.target):
        return False
    if hold:  # the hold response: from the base if it pays now, no massing sitrep (Q-TD-64)
        return _launch(world, rules, side, view, state, c, out, purse, at=base)
    staged = Staged(c.op.id, c.target, base, state.windows, _sector(rules, base))
    if staged.sector is not None:
        _adaptation(world, side, "STAGING", staged.sector, "UP", out)
    if _launch(world, rules, side, view, state, c, out, purse, at=base):
        _close(world, side, staged, _LAUNCHED, out)
    else:
        state.staged.append(staged)
        state.staged.sort(key=lambda s: (s.op, s.target))
    return True


def _review(
    world: World, rules: Rules, side: Side, view: SideView, state: DirectorState,
    out: list[Event], purse: _Purse | None, capped: bool,
) -> int:  # fmt: skip
    """FS-4, FS-6, each window before the selection, in (op, target) order: a staged operation no
    longer a candidate (`ops.candidate`) is dropped; one whose base the side lost or that has a
    capture bar re-stages at the next base by FS-2 (its wait kept; `_restage`),
    or falls back; it launches when every spawn node can pay its share; after
    `director.staging.max_wait_windows`, or at once when its target is in the running victory hold
    (Q-TD-46), it launches by EC-13 from wherever `_paying_node` finds the stock, else is
    dropped. While the night cap is spent (`capped`, §5, NX-480) a staged operation does not
    launch: it keeps waiting, its wait still running, and is dropped where it would fall back.
    FS-9 (Q-TD-47): a launch at the base closes its massing as
    `STAGING_LAUNCHED`, a drop or a fallback launch as `STAGING_DISPERSED`. Returns the budget the
    staged operations spent or still hold this window."""
    dr = rules.director
    if purse is None or dr is None or not state.staged:
        return 0
    now, held, keep = world.campaign.running_ticks + 1, 0, []
    for s in list(state.staged):
        c = ops.candidate(s.op, s.target, state, view, rules, _own(world, rules, side), now)
        if c is None:
            _close(world, side, s, _DISPERSED, out)
            continue
        base: str | None = s.base
        if not stg.hosts(world, rules, side, s.base, c.op):
            base = stg.base_for(world, rules, side, view, c.op, s.target)
            if base is not None:
                _restage(world, rules, side, s, base, out)
        # one aimed into the running victory hold waits no longer (Q-TD-46, NX-430)
        late = state.windows - s.since >= dr.staging_max_wait_windows or s.target in view.hold
        go = (world, rules, side, view, state, c, out, purse)
        # the night cap bars it (§5, NX-480): a staged operation is always a capture one (FS-1)
        if not capped and base is not None and _launch(*go, at=base):
            _close(world, side, s, _LAUNCHED, out)
            held += c.op.cost
        elif not capped and (base is None or late) and _launch(*go, stage=False):
            _close(world, side, s, _DISPERSED, out)  # it went in from elsewhere, not the base
            held += c.op.cost
        elif base is not None and not late:
            keep.append(s)
            held += c.op.cost
        else:
            _close(world, side, s, _DISPERSED, out)
    state.staged = keep
    state.last_operation = state.windows  # kept, launched or dropped this window (Q-TD-42)
    return held


def _sector(rules: Rules, node: str) -> str | None:
    return sector_at(rules, *rules.roads.pos[node])


def _close(world: World, side: Side, s: Staged, category: str, out: list[Event]) -> None:
    """Q-TD-47: the open "massing" sitrep of `s`, if any, is closed once, in the sector it named:
    `_LAUNCHED` ("NULL assault launching from <sector>") or `_DISPERSED` ("massing disperses")."""
    if s.sector is not None:
        _adaptation(world, side, category, s.sector, "UP", out)
        s.sector = None


def _restage(
    world: World, rules: Rules, side: Side, s: Staged, base: str, out: list[Event]
) -> None:
    """FS-5, FS-6 on a re-stage at `base` (Q-TD-38, Q-TD-47): "NULL forces are massing in
    <sector>", the new base's sector only, when the coalition tracks a Static unit there
    (`fog.seen_at`) and no massing sitrep is open for that sector; an open one for another sector,
    or one the coalition can no longer see, is closed as dispersed first."""
    sector = _sector(rules, base) if seen_at(world, rules, side, base) else None
    if sector != s.sector:
        _close(world, side, s, _DISPERSED, out)
        if sector is not None:
            _adaptation(world, side, "STAGING", sector, "UP", out)
            s.sector = sector
    s.base = base


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
    cost: Callable[[int], int], purse: _Purse | None = None, at: str | None = None,
) -> int | None:  # fmt: skip
    """Post the jobs in order, pay `cost(spawned)` and give each job its units; returns how many
    were spawned, or None when the real surplus now cannot pay for them and nothing was posted:
    the window's budget is only a plan, because the operations launched before this one load
    carriers from the same surplus (`_payable`). A slot goes to an idle live unit of its kind
    first (the lowest id), which is neither spawned nor paid for (Q-SIM-84). Units take their
    jobs only after the payment, because a carrier at its source loads on taking a job, and
    loading first could leave too little surplus to pay. With `economy.legacy_rules` off the
    cost is drawn once at `_paying_node`, where every new unit spawns (EC-13); with `at`, a staged
    operation's base (FS-4, Q-TD-38), each unit spawns where `_staged_shares` planned it and each
    spawn node pays its own units' share."""
    dr = rules.director
    if dr is None:
        return 0
    garrison = c.op.target == "GARRISON"
    spare = {} if garrison else _reusable(world, side)  # a garrison replacement is always new
    legacy, need = legacy_rules(rules), cost(len(_new_slots(c, spare)))
    node, shares = None, None
    spots: Iterator[str] = iter(())  # where a staged operation's new units spawn, in slot order
    if legacy:
        if _payable(world, rules, side) < need:
            return None
    elif at is not None:
        if (staged := _staged_shares(world, rules, side, c, spare, cost, purse, at)) is None:
            return None
        shares, spots = staged[0], iter(staged[1])
    elif (node := _paying_node(world, rules, side, c, need, purse)) is None:
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
                near = _near(world, rules, side, job, w)
                spot = node or (c.target if garrison else w.origin)
                if at is not None:
                    spot = next(spots)  # as `_staged_shares` planned and priced it
                unit, base = _spawn(world, rules, side, kind, near, out, at=spot)
                first, spawned = first or base, spawned + 1
                if garrison:
                    unit.home = c.target
                given.append((unit, posted))
        prev = last
    if next(spots, None) is not None:
        raise ValueError("a staged spawn left planned spots: the plan and the spawn drifted")
    if legacy:
        _pay(world, rules, side, cost(spawned), first, out)
    else:
        if node is not None:
            shares = {node: cost(spawned)}
        for paying, share in (shares or {}).items():
            pay_spawn(world, paying, share, out)
            if purse is not None:
                purse.spend(paying == rules.supply.rear[side], share)
    for unit, posted in given:
        take(world, unit, posted, out)
    return spawned


def _staged_spot(world: World, rules: Rules, side: Side, kind: UnitKind, near: str, at: str) -> str:
    """FS-4: where a new unit of an operation staged at `at` spawns: `at` when it hosts the kind's
    domain, else as EC-13 says (`plan_deploy`'s base for its job, else the rear source)."""
    if at in rules.supply.spawns.get(rules.domain[kind], ()):
        return at
    deploy = plan_deploy(world, rules, side, kind, near)
    return deploy[0] if deploy else rules.supply.rear[side]


def _staged_shares(
    world: World, rules: Rules, side: Side, c: ops.Candidate, spare: dict[str, list[Entity]],
    cost: Callable[[int], int], purse: _Purse | None, at: str,
) -> tuple[dict[str, int], list[str]] | None:  # fmt: skip
    """FS-4 (Q-TD-38, Q-TD-39): what each spawn node of `c`, staged at `at`, pays for its own new
    units and where each new unit spawns (in `_new_slots` order), or None while the base or the
    source cannot pay. A node's share is the cost of the units counted up to and including it
    less the cost of those before it, the base first, then the other bases by id, the source
    last, so the shares add up to `cost(new units)` and the base's is `cost(its units)` (FS-3). A
    base pays from its surplus and the base account, the source from the pool and the rear
    account, as `_paying_node` checks one node; a deploy base that cannot pay sends its units to
    the source, as `_paying_node` does."""
    slots = [
        _staged_spot(world, rules, side, kind, _near(world, rules, side, job, w), at)
        for kind, job, w in _new_slots(c, spare)
    ]
    count: dict[str, int] = {}
    for spot in slots:
        count[spot] = count.get(spot, 0) + 1
    rear, sup, pool = rules.supply.rear[side], rules.supply, world.pool.get(side)
    room = None if purse is None else _Purse(purse.base, purse.rear, purse.one)
    shares: dict[str, int] = {}
    moved: set[str] = set()
    units = 0
    for node in [*sorted(set(count) - {rear}, key=lambda n: (n != at, n)), rear]:
        n = count.get(node, 0) + (sum(count[m] for m in sorted(moved)) if node == rear else 0)
        if n == 0:
            continue
        share = cost(units + n) - cost(units)
        if node == rear:
            ok = pool is None or pool >= share
        else:
            ok = world.stock.get(node, 0) - sup.starve_floor.get(node, 0) >= share
        if room is not None:
            ok = ok and share <= room.room(node == rear)
        if share > 0 and not ok:
            if node in (at, rear):
                return None
            moved.add(node)  # Q-TD-39: its units spawn at the source and pay their share there
            continue
        if room is not None:
            room.spend(node == rear, share)
        units += n
        shares[node] = share
    return shares, [rear if s in moved else s for s in slots]


def _paying_node(
    world: World, rules: Rules, side: Side, c: ops.Candidate, cost: int, purse: _Purse | None
) -> str | None:
    """EC-13: the node that pays `cost` and where every new unit of `c` spawns (module
    docstring), or None to drop it this window. A fixed origin (a garrison replacement's base, a
    scout's checked base) has no fallback to the source. Otherwise the base is `plan_deploy`'s
    for the operation's first aircraft kind (a landing base), else its first kind, and must be a
    `spawns` node for every kind's domain."""
    rear, sup = rules.supply.rear[side], rules.supply
    job, w = c.op.jobs[0], c.wheres[0][0]
    fixed = c.target if c.op.target == "GARRISON" else w.origin
    node = fixed or rear
    if not fixed:
        kinds = [k for j in c.op.jobs for k in j.unit_kinds]
        probe = next((k for k in kinds if rules.domain[k] == "AIR"), kinds[0])
        deploy = plan_deploy(world, rules, side, probe, _near(world, rules, side, job, w))
        if deploy and all(deploy[0] in sup.spawns.get(rules.domain[k], ()) for k in kinds):
            node = deploy[0]
    if node != rear:
        surplus_ = world.stock.get(node, 0) - sup.starve_floor.get(node, 0)
        if cost <= 0 or (surplus_ >= cost and (purse is None or cost <= purse.room(False))):
            return node
        if fixed:
            return None
    pool = world.pool.get(side)  # None: an infinite source (unlimited mode)
    paid = (purse is None or cost <= purse.room(True)) and (pool is None or pool >= cost)
    return rear if cost <= 0 or paid else None


def _new_slots(
    c: ops.Candidate, spare: dict[str, list[Entity]]
) -> list[tuple[UnitKind, JobTemplate, ops.Where]]:
    """The slots `_post_and_spawn` will spawn a new unit for, in its order: `c`'s slots less those
    an idle unit fills (the same matching, on a copy of `spare`)."""
    left = {k: list(v) for k, v in spare.items()}
    new: list[tuple[UnitKind, JobTemplate, ops.Where]] = []
    for job, wheres in zip(c.op.jobs, c.wheres, strict=True):
        for w in wheres:
            for n in range(job.slots):
                kind = job.unit_kinds[n % len(job.unit_kinds)]
                idle = [u for u in left.get(kind, []) if w.origin in (None, u.last_node)]
                if idle:
                    left[kind].remove(idle[0])
                else:
                    new.append((kind, job, w))
    return new


def _spare(world: World, side: Side) -> dict[str, list[Entity]]:
    """The side's idle Director units by kind, lowest id first: no job, order or path, not
    Disabled, not homebound and not grounded (ECONOMY EC-6), so the board would let them take a
    job."""
    out: dict[str, list[Entity]] = {}
    for e in world.entities():
        if (
            e.side == side and e.owner_kind == _DIRECTOR and e.job_id is None and e.order is None
            and not e.path and e.damage_state != "DISABLED" and e.state != "RTB" and not e.grounded
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
                route = shortest_path(rules.roads, e.last_node, e.home, blocked=blocked(world))
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
    unit.last_node = unit.home_base = node  # its spawn node pays its upkeep (ECONOMY EC-5)
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
    world: World, side: Side, category: str, sector: str, direction: str, out: list[Event],
    node: str | None = None,
) -> None:  # fmt: skip
    out.append(
        ThreatAdaptation.model_construct(
            kind="ThreatAdaptation", tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(), campaign_id=world.campaign.id, side=side,
            category=category, sector_id=sector, direction=direction, node_id=node, credit_ids=[],
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
