"""The Threat Director's operations: candidates, scoring and selection (THREAT-DIRECTOR §4 steps 3,
4 and 6, TD-2, TD-5; Q-TD-4, Q-TD-6, Q-SIM-78, Q-SIM-81; NX-156).

Pure and side-agnostic: it takes a side's `SideView`, that side's `DirectorState` and `Own`, the few
facts about the side's own units and facilities that no view holds (its convoys, its damaged
air-defense sites, its radars, how many units it has live), and never the `World`. Nothing here
draws from the RNG but `rank`, which draws from the stream it is given, nothing reads a clock.

**Candidates (step 3).** For each catalog operation enabled at the tier, in id order, each target
(NODE: node ids, SECTOR: sector ids, RADAR: the Static radars' base ids, CONVOYS: one, id "") in id
order, is a candidate when every precondition holds, every job's selector resolves to something
(TD-2: a selector that resolves to nothing drops the operation) and, for a node on the other side,
its kind has a `score.target_value`. A live operation (jobs on the board) is not posted again
for the same target, except CONVOYS, whose candidate is only the convoys not yet escorted.

**Score (step 4).** `priority x target value x weakness x memory x proximity`, exact Fractions:
- target value: `score.target_value.<node kind>` for a node of the other side,
  `score.own_node_value` for a node the side holds, else 1;
- weakness: `score.weakness_min` at full defense HP rising linearly to `score.weakness_max` at
  none, from the node's HP in the view over its maximum; 1 for anything but a node of the other
  side;
- memory: the operation's counter in events c, `1 + k c` for RAISE, `1 / (1 + k c)` for LOWER, k
  being `director.memory.factor` (the per-sector counters read the target's sector);
- TD-5, `track_age`: `1 + f s` (f is `score.stale_factor`) for a SECTOR, `s` being 0 with a
  current track there, `age / fade` of the oldest last-known track (at most 1), and 1 with no
  track of any kind;
- proximity: `score.provocation_proximity` for a target in `last_provocation_sector` while the CP
  ceiling is one of `score.proximity_tiers` (Q-TD-4).
Then noise: one `director` draw per candidate in enumeration order, `r` in [-1000, 1000], moves the
score by `noise_scale x r / 1000` of itself. Order for selection: score descending, operation id,
target id.

**Selection (step 6).** Greedy in that order within the window budget and the unit caps: an
operation is taken if its cost is left and its units fit `max_spawns_per_window` and the room below
`max_live_units.<tier>`; an escort operation shrinks to the convoys that fit (at least one); at
most one effect operation (a radar blink) a window. A tier runs at most `director.max_ops.<tier>`
operations with jobs at a time (§3), counting those still on the board; the routine ones, those
enabled at Pattern of Life, do not count (Q-SIM-84).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import NamedTuple

from nexus.contracts.gen.common.enums import ThreatTier, UnitKind
from nexus.core.director import TIERS
from nexus.core.fog import SideView
from nexus.core.logistics import deploy_pool, nearest_by_air
from nexus.core.rng import PcgStream
from nexus.core.rules import CP_SCALE, DirectorRules, JobTemplate, OperationRules, Rules, sector_at
from nexus.core.tasking import ring_crossed
from nexus.core.tasking_gen import fits
from nexus.core.world import DirectorState, Vec2

# A draw is r in [-NOISE_STEPS, NOISE_STEPS], so the span is 2 * steps + 1. Fixed with the RNG
# stream: it sets the draw resolution and a change reshuffles every seeded decision (not a tunable).
NOISE_STEPS = 1000
_FOE = {"COALITION": "ENEMY", "ENEMY": "COALITION"}
_EACH_CONVOY = "each_convoy"
_GARRISON = "GARRISON"  # the target of the garrison upkeep operation (Q-SIM-85)
LIVE_PREFIX = "op:"  # a Director job's dedupe key is `op:<operation>:<target>:<job index>[:<unit>]`


class Where(NamedTuple):
    """What a job is aimed at: a node, one of the side's own units (an escort job), or a point
    (a Recon scout, Q-SIM-87) with `origin`, the base its scout is raised at."""

    node: str | None
    entity: int | None = None
    pos: Vec2 | None = None
    origin: str | None = None


@dataclass(frozen=True, slots=True)
class Own:
    """What the side knows of itself that its `SideView` does not hold. `convoys` are the side's
    moving carriers that follow no one and have no escort job yet, in id order, as (id, node it
    stands at or left last); `damaged_ad` the bases with an air-defense site below full HP;
    `radars` the bases with a radar site that is not Disabled; `live_units` its mobile units;
    `homed` the kinds of its live Director units homed at each base, in id order (Q-SIM-85), and
    `margin` each of its finite-stock bases' stock less the starvation floor (negative below it)."""

    convoys: tuple[tuple[int, str], ...] = ()
    damaged_ad: frozenset[str] = frozenset()
    radars: frozenset[str] = frozenset()
    live_units: int = 0
    homed: Mapping[str, tuple[UnitKind, ...]] = field(default_factory=dict)
    margin: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Candidate:
    """An operation aimed at `target`; `wheres[i]` is where job `i` of its template is posted (one
    job each, `slots` units each). `score` is set by `rank`."""

    op: OperationRules
    target: str
    sector: str | None
    wheres: tuple[tuple[Where, ...], ...]
    score: Fraction = Fraction(0)

    @property
    def units(self) -> int:
        return sum(j.slots * len(w) for j, w in zip(self.op.jobs, self.wheres, strict=True))


def bases(view: SideView, rules: Rules) -> list[str]:
    """The nodes the side owns now that count as its bases: not a bridge, not a sanctuary."""
    return [
        n for n in sorted(view.nodes)
        if view.owners.get(n) == view.side and rules.node_kind.get(n) not in rules.uncapturable
    ]  # fmt: skip


def _nearest(view: SideView, to: str, nodes: list[str]) -> str | None:
    """The node nearest `to` by straight line, ties by id."""
    x, y = view.nodes[to]
    best = min(
        ((math.hypot(view.nodes[n][0] - x, view.nodes[n][1] - y), n) for n in nodes), default=None
    )
    return None if best is None else best[1]


def launch_base(view: SideView, rules: Rules, own: Own, kind: UnitKind, pos: Vec2) -> str:
    """Where a new aircraft of `kind` for a job at `pos` is raised (GP-7): the base
    `logistics.plan_deploy` picks for it, from the view's owners and `Own.margin` (the stock
    over the floor of the side's finite-stock bases) through the same `deploy_pool` and
    `nearest_by_air`; else the side's rear source."""
    pool = deploy_pool(rules, kind, view.side, view.owners, own.margin)
    return nearest_by_air(rules, pool, pos.x, pos.y) or rules.supply.rear[view.side]


def _grid(rules: Rules, sector: str, step: int) -> list[tuple[int, int]]:
    """The centres of the `step`-m grid cells whose centre lies in the sector, in (x, y) order."""
    poly = dict(rules.sectors)[sector]
    x1, y1 = max(p[0] for p in poly), max(p[1] for p in poly)
    return [
        (x, y)
        for x in range(step // 2, x1 + 1, step)
        for y in range(step // 2, y1 + 1, step)
        if sector_at(rules, x, y) == sector
    ]


def span(v: float, reach: float, step: int) -> range:
    """The grid-cell centres (`step // 2 + k step`) within `reach` of the coordinate `v`."""
    half = step // 2
    lo, hi = math.ceil((v - reach - half) / step), math.floor((v + reach - half) / step)
    return range(half + lo * step, half + hi * step + 1, step)


def cell_key(x: float, y: float) -> str:
    """A grid cell's key in `DirectorState.looked`: its centre in metres, `x:y`."""
    return f"{round(x)}:{round(y)}"


def _picture(
    view: SideView, rules: Rules, dr: DirectorRules, cells: list[tuple[int, int]],
    looked: Mapping[str, int], now: int,
) -> dict[tuple[int, int], Fraction]:  # fmt: skip
    """TD-5 and FOW-6a per cell, the freshest of two readings (1 is unseen, 0 fresh): the track
    reading is 1 with no track of any kind within `director.recon.loiter_radius_m` of its centre,
    else the age share (`age / fade`, at most 1) of the freshest one, 0 for a current track; the
    look reading (Q-SIM-87) is 1 for a cell no sensor of the side covered within
    `director.recon.memory_s`, else the time since it last did over that time. The Static's own
    view and memory alone."""
    fade, reach = rules.track_fade_ticks, dr.recon_loiter_radius_m
    stale = dict.fromkeys(cells, Fraction(1))
    for t in (*view.tracks.values(), *view.last_known.values()):
        share = Fraction(0) if t.age is None else Fraction(min(t.age, fade), fade)
        for x in span(t.pos.x, reach, dr.recon_grid_m):
            for y in span(t.pos.y, reach, dr.recon_grid_m):
                if share < stale.get((x, y), 0) and math.hypot(x - t.pos.x, y - t.pos.y) <= reach:
                    stale[x, y] = share
    memory = dr.recon_memory_ticks
    for c in cells:
        if (seen := looked.get(cell_key(*c))) is not None:
            stale[c] = min(stale[c], Fraction(min(now - seen, memory), memory))
    return stale


def _sortie_fits(
    view: SideView, rules: Rules, dr: DirectorRules, kind: UnitKind, start: Vec2, spot: Vec2
) -> bool:
    """A scout of `kind` raised at `start` can fly to `spot`, loiter there and land at the nearest
    landing base of the side's with the bingo reserve left (`Rules.fuel_s`, one fuel second per
    world second); else it would turn for home mid-loiter and the job could not finish."""
    homes = [view.nodes[n] for n in rules.landing_nodes if view.owners.get(n) == view.side]
    back = min((math.hypot(spot.x - x, spot.y - y) for x, y in homes), default=math.inf)
    flight = (math.hypot(spot.x - start.x, spot.y - start.y) + back) / rules.speed_mps[kind]
    loiter = dr.recon_loiter_ticks * rules.world_dt
    return flight + loiter + rules.bingo_reserve_frac * rules.fuel_s[kind] <= rules.fuel_s[kind]


def recon_point(
    view: SideView, rules: Rules, own: Own, sector: str, kind: UnitKind,
    looked: Mapping[str, int], now: int,
) -> tuple[Vec2, str] | None:  # fmt: skip
    """Q-SIM-87: the point of `sector` a scout of `kind` loiters at and the base it is raised at,
    or None (the sector is skipped this window). The stalest cell first (`_picture`: tracks and
    looks), ties by (x, y); the first whose route from its launch base crosses no discovered
    coalition air-defense ring that was not last seen Disabled, which stays clear of every such
    ring by the loiter radius, and which the scout can fly to, loiter at and return from
    (`_sortie_fits`). Only the view and `Own` are read (TD-2)."""
    dr = rules.director
    if dr is None:
        return None
    cells = _grid(rules, sector, dr.recon_grid_m)
    stale = _picture(view, rules, dr, cells, looked, now)
    order = sorted(cells, key=lambda c: (-stale[c], c))
    for x, y in order:
        spot = Vec2(x, y)
        origin = launch_base(view, rules, own, kind, spot)
        start = Vec2(*rules.roads.pos[origin])
        clear = not ring_crossed(view.markers.values(), start, (x, y), dr.recon_loiter_radius_m)
        if clear and _sortie_fits(view, rules, dr, kind, start, spot):
            return spot, origin
    return None


def _resolve(
    job: JobTemplate, c_target: str, state: DirectorState, view: SideView, rules: Rules, own: Own,
    now: int,
) -> tuple[Where, ...]:  # fmt: skip
    """A selector against the side's view (TD-2); empty when it resolves to nothing."""
    at = job.at
    if at == _EACH_CONVOY:
        return tuple(Where(None, i) for i, _ in own.convoys)
    if at in ("target", "target_defenses"):
        return (Where(c_target),)
    if at == "nearest_own_base":
        near = _nearest(view, c_target, bases(view, rules))
        return () if near is None else (Where(near),)
    spot = recon_point(
        view, rules, own, c_target, job.unit_kinds[0], state.looked, now
    )  # sector_point
    return () if spot is None else (Where(None, None, *spot),)


def _frontline(view: SideView, rules: Rules, node: str, hops: int) -> bool:
    """Some node within `hops` road hops (`director.frontline_hops`) has another owner."""
    owner, seen, ring = view.owners.get(node), {node}, [node]
    for _ in range(hops):
        ring = sorted({n for m in ring for n, _ in rules.roads.neighbours(m)} - seen)
        if any(view.owners.get(n) != owner for n in ring):
            return True
        seen.update(ring)
    return False


def _holds(
    pre: str, node: str, state: DirectorState, view: SideView, rules: Rules, own: Own, now: int
) -> bool:
    match pre:
        case "target_owner_is_coalition":  # the other side's, whichever the Director's
            return view.owners.get(node) == _FOE[view.side]
        case "target_in_enemy_view":
            return node in view.nodes
        case "target_capturable":
            return rules.node_kind.get(node) not in rules.uncapturable
        case "target_is_frontline":
            return rules.director is not None and _frontline(
                view, rules, node, rules.director.frontline_hops
            )
        case "target_recently_lost":
            lost = state.lost.get(node)
            dr = rules.director
            return lost is not None and dr is not None and now - lost < dr.retake_ticks
        case "target_has_damaged_air_defense":
            return node in own.damaged_ad
        case "target_radar_operational":
            return node in own.radars
        case "has_unescorted_convoy":
            return bool(own.convoys)
    raise ValueError(f"unknown precondition {pre!r}")


def _targets(op: OperationRules, view: SideView, rules: Rules, own: Own) -> list[str]:
    match op.target:
        case "NODE":
            return sorted(view.nodes)
        case "SECTOR":
            return [s for s, _ in rules.sectors]
        case "RADAR":
            return sorted(own.radars)
        case "GARRISON":  # a base below its quota (Q-SIM-85, = _GARRISON; a match needs a literal)
            return [
                n for n in bases(view, rules)
                if len(own.homed.get(n, ())) < rules.garrison_quota.get(n, 0)
            ]  # fmt: skip
    return [""]  # CONVOYS


def _sector_of(op: OperationRules, target: str, view: SideView, rules: Rules) -> str | None:
    if op.target == "SECTOR":
        return target
    if op.target in ("NODE", "RADAR"):
        return sector_at(rules, *view.nodes[target])
    return None


def live_pairs(keys: list[str]) -> frozenset[tuple[str, str]]:
    """(operation, target) of every Director job key on the board."""
    return frozenset(
        (parts[1], parts[2])
        for k in keys if k.startswith(LIVE_PREFIX) and len(parts := k.split(":")) >= 4
    )  # fmt: skip


def has_capture(op: OperationRules) -> bool:
    return any(j.kind == "CAPTURE" for j in op.jobs)


def candidates(
    state: DirectorState, view: SideView, rules: Rules, own: Own, now: int,
    live: frozenset[tuple[str, str]], *, capture: bool | None = None,
) -> list[Candidate]:  # fmt: skip
    """Step 3, in (operation id, target id) order; `now` is the running tick. `capture` True
    considers only the operations with a CAPTURE job whatever their tier (the Pattern of Life
    capture slot, Q-SIM-85), False drops them (the night cap is spent), None the tier's own."""
    dr = rules.director
    if dr is None:
        raise ValueError("candidates need the Director rules")
    out: list[Candidate] = []
    for op in dr.operations:
        if (capture is not True and state.tier not in op.tiers) or (
            capture is not None and has_capture(op) != capture
        ):
            continue
        for target in _targets(op, view, rules, own):
            if (op.target != "CONVOYS" and (op.id, target) in live) or not _eligible(
                op, target, state, view, rules, own, now
            ):
                continue
            wheres = tuple(_resolve(j, target, state, view, rules, own, now) for j in op.jobs)
            if all(wheres):
                sector = _sector_of(op, target, view, rules)
                chosen = _garrison(op, target, rules, dr, own) if op.target == _GARRISON else op
                out.append(Candidate(chosen, target, sector, wheres))
    return out


def _garrison(
    op: OperationRules, base: str, rules: Rules, dr: DirectorRules, own: Own
) -> OperationRules:
    """The garrison operation sized and filled for its base: `director.garrison.replace_per_window`
    units (at most the shortfall), each of the kind the base is then shortest of from
    `director.garrison.kinds` for its node kind (round-robin: fewest first, ties by list order);
    the cost is the catalog's per unit."""
    kinds = dr.garrison_kinds[rules.node_kind[base]]
    have = own.homed.get(base, ())
    count = min(dr.replace_per_window, rules.garrison_quota[base] - len(have))
    picked: list[UnitKind] = []
    for _ in range(count):
        picked.append(min(kinds, key=lambda k: (have.count(k), kinds.index(k))))
        have = (*have, picked[-1])
    job = replace(op.jobs[0], unit_kinds=tuple(picked), slots=count)
    return replace(op, cost=op.cost * count, jobs=(job,))


def _eligible(
    op: OperationRules, target: str, state: DirectorState, view: SideView, rules: Rules,
    own: Own, now: int,
) -> bool:  # fmt: skip
    dr = rules.director
    if dr is None:
        return False
    if not all(_holds(p, target, state, view, rules, own, now) for p in op.preconditions):
        return False
    if op.target == "NODE" and view.owners.get(target) == _FOE[view.side]:
        return rules.node_kind.get(target) in dr.target_value  # a kind with no value is no target
    return True


def staleness(view: SideView, rules: Rules, dr: DirectorRules) -> dict[str, Fraction]:
    """TD-5, per sector: 0 with a current track in it, else `age / fade` of the oldest last-known
    track in it (below 1: they fade at 1), 1 with none."""
    fade = rules.track_fade_ticks
    cur = {s for t in view.tracks.values() if (s := sector_at(rules, t.pos.x, t.pos.y))}
    old: dict[str, int] = {}
    for t in view.last_known.values():
        s = sector_at(rules, t.pos.x, t.pos.y)
        if s is not None and t.age is not None:
            old[s] = max(old.get(s, 0), t.age)
    return {
        s: Fraction(0)
        if s in cur
        else Fraction(min(old[s], fade), fade)
        if s in old
        else Fraction(1)
        for s, _ in rules.sectors
    }


def _memory(
    op: OperationRules, state: DirectorState, sector: str | None, dr: DirectorRules
) -> Fraction:
    if op.memory is None:
        return Fraction(1)
    counter, effect = op.memory
    counts: Mapping[str, int] = {}
    if counter == "convoy_attacks":
        raw = state.convoy_attacks
    elif counter == "radar_strikes":
        raw = state.radar_strikes
    else:
        counts = state.node_losses if counter == "node_losses_by_sector" else state.recon_losses
        raw = counts.get(sector or "", 0)
    m = 1 + dr.memory_factor * Fraction(raw, CP_SCALE)
    return m if effect == "RAISE" else 1 / m


def _node_factors(c: Candidate, view: SideView, rules: Rules, dr: DirectorRules) -> Fraction:
    """Target value x weakness for a node of the other side; `score.own_node_value` for a node the
    side holds; 1 for any other target."""
    node = c.target
    if c.op.target != "NODE":
        return Fraction(1)
    if view.owners.get(node) == view.side:
        return dr.own_node_value
    if view.owners.get(node) != _FOE[view.side]:
        return Fraction(1)
    value = dr.target_value[rules.node_kind[node]]
    top = rules.defense.max_hp.get(node, 0) if rules.defense else 0
    if top <= 0:
        return value
    hp = min(top, max(0, view.defense_hp.get(node, top)))
    return value * (dr.weakness_min + (dr.weakness_max - dr.weakness_min) * (1 - Fraction(hp, top)))


def rank(
    cands: list[Candidate], state: DirectorState, view: SideView, rules: Rules, rng: PcgStream
) -> list[Candidate]:
    """Step 4: score every candidate (one `director` draw each, in enumeration order) and return
    them best first."""
    dr = rules.director
    if dr is None:
        raise ValueError("rank needs the Director rules")
    stale = staleness(view, rules, dr) if any(c.op.track_age for c in cands) else {}
    near = TIERS[state.ceiling] in dr.proximity_tiers and state.last_provocation_sector is not None
    scored = []
    for c in cands:
        s = c.op.priority * _node_factors(c, view, rules, dr) * _memory(c.op, state, c.sector, dr)
        if c.op.track_age:
            s *= 1 + dr.stale_factor * stale.get(c.target, Fraction(1))
        if near and c.sector == state.last_provocation_sector:
            s *= dr.proximity
        draw = rng.randbelow(2 * NOISE_STEPS + 1) - NOISE_STEPS
        scored.append(replace(c, score=s * (1 + dr.noise * Fraction(draw, NOISE_STEPS))))
    return sorted(scored, key=lambda c: (-c.score, c.op.id, c.target))


def _fit(c: Candidate, room: int, least: int) -> Candidate | None:
    """`c` with its units within `room`: an each-convoy job keeps the first convoys that fit
    (at least `least`, `director.escort_min_convoys`), anything else must fit whole."""
    if c.units <= room:
        return c
    steps = list(zip(c.op.jobs, c.wheres, strict=True))
    fixed = sum(j.slots * len(w) for j, w in steps if j.at != _EACH_CONVOY)
    per = sum(j.slots for j, _ in steps if j.at == _EACH_CONVOY)
    keep = (room - fixed) // per if per else 0
    if keep < least:
        return None
    return replace(c, wheres=tuple(w[:keep] if j.at == _EACH_CONVOY else w for j, w in steps))


def select(
    ranked: list[Candidate], dr: DirectorRules, budget: int, spawn_room: int, live_room: int,
    live: frozenset[tuple[str, str]], max_ops: int | None, routine: frozenset[str] = frozenset(),
) -> list[Candidate]:  # fmt: skip
    """Step 6 (module docstring). `live_room` is `max_live_units.<tier>` less the live units."""
    chosen: list[Candidate] = []
    running = set(live)
    blinks = 0
    for c in ranked:
        if c.op.cost > budget or (c.op.effect and blinks >= dr.blink_max):
            continue  # at most `decoy_blink.max_per_window` radars blink per window (Q-SIM-82)
        pair = (c.op.id, c.target)
        new = bool(c.op.jobs) and pair not in running
        counted = {p for p in running if p[0] not in routine}
        if new and c.op.id not in routine and max_ops is not None and len(counted) >= max_ops:
            continue
        fitted = _fit(c, min(spawn_room, live_room), dr.escort_min_convoys)
        if fitted is None:
            continue
        chosen.append(fitted)
        blinks += bool(c.op.effect)
        budget -= c.op.cost
        spawn_room -= fitted.units
        live_room -= fitted.units
        if new:
            running.add(pair)
    return chosen


def routine_ops(dr: DirectorRules) -> frozenset[str]:
    """Operations enabled at Pattern of Life are routine: `director.max_ops.<tier>` skips them."""
    return frozenset(o.id for o in dr.operations if "PATTERN_OF_LIFE" in o.tiers)


def max_ops(tier: ThreatTier, dr: DirectorRules) -> int | None:
    """§3: a tier runs at most `director.max_ops.<tier>` operations at a time, None for no cap
    (the budget bounds it). Pattern of Life has no key: all its operations are routine, which
    never count (STRUCT)."""
    return dr.max_ops.get(tier)


def patrol_via(view: SideView, rules: Rules, base: str) -> str | None:
    """Where a patrol from `base` turns (Q-SIM-85, Q-SIM-86): the road neighbour (a base, not a
    bridge or sanctuary, and not one the other side holds) on the shortest way to the nearest node
    within `director.frontline_hops` hops that the side does not hold (the `_frontline` ring
    search; ties by node id), neutral or not; with no front in reach, the nearest such neighbour
    by straight line. A patrolling unit never captures (`nexus.core.capture`). None for a base
    with no such road."""
    dr = rules.director
    first = [
        n for n, _ in rules.roads.neighbours(base)
        if view.owners.get(n) != _FOE[view.side]
        and rules.node_kind.get(n) not in rules.uncapturable
    ]  # fmt: skip
    if dr is None or not first:
        return None
    best: tuple[int, str] | None = None
    for n in first:
        seen, ring = {base, n}, [n]
        for depth in range(1, dr.frontline_hops + 1):
            if any(view.owners.get(m) != view.side for m in ring):
                best = min(best or (depth, n), (depth, n))
                break
            ring = sorted({m for r in ring for m, _ in rules.roads.neighbours(r)} - seen)
            seen.update(ring)
    return best[1] if best else _nearest(view, base, sorted(first))


def garrison_cost(dr: DirectorRules) -> int:
    """Budget points of one replacement garrison unit: the cost of the GARRISON operation, 0 when
    the catalog has none."""
    return next((o.cost for o in dr.operations if o.target == _GARRISON), 0)


def convoy_bases(view: SideView, rules: Rules, own: Own) -> list[str]:
    """The Static bases with an upkeep shortfall (Q-SIM-85), largest first, ties by node id: the
    cost of a base's missing garrison units less its margin over the floor (so a base below its
    floor counts the floor less its stock too, Q-SIM-86), above zero."""
    dr = rules.director
    if dr is None:
        return []
    unit, short = garrison_cost(dr), dict[str, int]()
    for n in bases(view, rules):
        missing = rules.garrison_quota.get(n, 0) - len(own.homed.get(n, ()))
        short[n] = missing * unit - own.margin.get(n, 0)
    return sorted((n for n, s in short.items() if s > 0), key=lambda n: (-short[n], n))


def _garrison_problem(rules: Rules, kind: UnitKind, node: str) -> str | None:
    """Why a garrison of `kind` cannot live at `node`: it cannot stage, it is not raised there (the
    theater's `spawns`), or it is an aircraft at a node that is no landing base (Q-SIM-86: a unit
    must spawn at its home node and rest there)."""
    domain = rules.domain[kind]
    if not fits(rules, kind, "STAGE"):
        return "cannot stage"
    if node not in rules.supply.spawns.get(domain, ()):
        return "is not raised"
    if domain == "AIR" and node not in rules.landing_nodes:
        return "cannot land"
    return None


def misfits(rules: Rules) -> list[str]:
    """Catalog problems that need the kernel rules: a unit kind that cannot do its job kind, a
    garrison or convoy kind that cannot do its job."""
    dr = rules.director
    out = [
        f"{op.id}: {kind} cannot take a {job.kind} job"
        for op in (dr.operations if dr else ())
        for job in op.jobs
        for kind in dict.fromkeys(job.unit_kinds)
        if not fits(rules, kind, job.kind)
    ]
    if dr is None:
        return out
    for node in sorted(rules.garrison_quota):
        kinds = dr.garrison_kinds.get(rules.node_kind[node], ())
        if not kinds:
            out.append(f"director.garrison.kinds has none for {node} ({rules.node_kind[node]})")
        out += [
            f"director.garrison.kinds: {k} {why} at {node}"
            for k in dict.fromkeys(kinds)
            if (why := _garrison_problem(rules, k, node))
        ]
    if rules.garrison_quota and not any(o.target == _GARRISON for o in dr.operations):
        out.append("a theater garrison_quota needs a GARRISON operation in the catalog")
    if not fits(rules, dr.convoy_kind, "RESUPPLY"):
        out.append(f"director.pol.convoy_kind: {dr.convoy_kind} cannot take a RESUPPLY job")
    return out
