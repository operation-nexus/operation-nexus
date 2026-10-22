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
  ceiling is ALPHA (Q-TD-4).
Then noise: one `director` draw per candidate in enumeration order, `r` in [-1000, 1000], moves the
score by `noise_scale x r / 1000` of itself. Order for selection: score descending, operation id,
target id.

**Selection (step 6).** Greedy in that order within the window budget and the unit caps: an
operation is taken if its cost is left and its units fit `max_spawns_per_window` and the room below
`max_live_units.<tier>`; an escort operation shrinks to the convoys that fit (at least one); at
most one effect operation (a radar blink) a window. ALPHA runs at most `director.alpha_max_ops`
operations with jobs at a time (§3), counting those still on the board; the routine ones, those
enabled at Pattern of Life, do not count (Q-SIM-84).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import NamedTuple

from nexus.core.fog import SideView
from nexus.core.rng import PcgStream
from nexus.core.rules import CP_SCALE, DirectorRules, OperationRules, Rules, sector_at
from nexus.core.tasking_gen import fits
from nexus.core.world import DirectorState

NOISE_STEPS = 1000  # a draw is r in [-NOISE_STEPS, NOISE_STEPS], so the span is 2 * steps + 1
_FOE = {"COALITION": "ENEMY", "ENEMY": "COALITION"}
_NOT_BASES = ("BRIDGE", "SANCTUARY")
_UNCAPTURABLE = ("SANCTUARY", "BRIDGE")
_EACH_CONVOY = "each_convoy"
LIVE_PREFIX = "op:"  # a Director job's dedupe key is `op:<operation>:<target>:<job index>[:<unit>]`


class Where(NamedTuple):
    """What a job is aimed at: a node, or (an escort job) one of the side's own units."""

    node: str | None
    entity: int | None = None


@dataclass(frozen=True, slots=True)
class Own:
    """What the side knows of itself that its `SideView` does not hold. `convoys` are the side's
    moving carriers that follow no one and have no escort job yet, in id order, as (id, node it
    stands at or left last); `damaged_ad` the bases with an air-defense site below full HP;
    `radars` the bases with a radar site that is not Disabled; `live_units` its mobile units."""

    convoys: tuple[tuple[int, str], ...] = ()
    damaged_ad: frozenset[str] = frozenset()
    radars: frozenset[str] = frozenset()
    live_units: int = 0


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
        if view.owners.get(n) == view.side and rules.node_kind.get(n) not in _NOT_BASES
    ]  # fmt: skip


def _nearest(view: SideView, to: str, nodes: list[str]) -> str | None:
    """The node nearest `to` by straight line, ties by id."""
    x, y = view.nodes[to]
    best = min(
        ((math.hypot(view.nodes[n][0] - x, view.nodes[n][1] - y), n) for n in nodes), default=None
    )
    return None if best is None else best[1]


def _sector_node(view: SideView, rules: Rules, sector: str) -> str | None:
    """The sector's node that is not the side's, not a bridge or sanctuary, nearest the side's
    rear source: where a scout of the sector goes."""
    inside = [
        n for n in sorted(view.nodes)
        if view.owners.get(n) != view.side and rules.node_kind.get(n) not in _NOT_BASES
        and sector_at(rules, *view.nodes[n]) == sector
    ]  # fmt: skip
    return _nearest(view, rules.supply.rear[view.side], inside)


def _resolve(
    at: str, c_target: str, op: OperationRules, view: SideView, rules: Rules, own: Own
) -> tuple[Where, ...]:
    """A selector against the side's view (TD-2); empty when it resolves to nothing."""
    if at == _EACH_CONVOY:
        return tuple(Where(None, i) for i, _ in own.convoys)
    if at in ("target", "target_defenses"):
        return (Where(c_target),)
    if at == "nearest_own_base":
        near = _nearest(view, c_target, bases(view, rules))
    else:  # sector_node
        near = _sector_node(view, rules, c_target)
    return () if near is None else (Where(near),)


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
            return rules.node_kind.get(node) not in _UNCAPTURABLE
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


def candidates(
    state: DirectorState, view: SideView, rules: Rules, own: Own, now: int,
    live: frozenset[tuple[str, str]],
) -> list[Candidate]:  # fmt: skip
    """Step 3, in (operation id, target id) order; `now` is the running tick."""
    dr = rules.director
    if dr is None:
        raise ValueError("candidates need the Director rules")
    out: list[Candidate] = []
    for op in dr.operations:
        if state.tier not in op.tiers:
            continue
        for target in _targets(op, view, rules, own):
            if (op.target != "CONVOYS" and (op.id, target) in live) or not _eligible(
                op, target, state, view, rules, own, now
            ):
                continue
            wheres = tuple(_resolve(j.at, target, op, view, rules, own) for j in op.jobs)
            if all(wheres):
                sector = _sector_of(op, target, view, rules)
                out.append(Candidate(op, target, sector, wheres))
    return out


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
    near = state.ceiling == 1 and state.last_provocation_sector is not None
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
    """Operations enabled at Pattern of Life are routine: ALPHA's one-at-a-time rule skips them."""
    return frozenset(o.id for o in dr.operations if "PATTERN_OF_LIFE" in o.tiers)


def alpha_max_ops(tier: str, dr: DirectorRules) -> int | None:
    """§3: ALPHA runs at most `director.alpha_max_ops` operations at a time; the other tiers are
    bounded by budget."""
    return dr.alpha_max_ops if tier == "ALPHA" else None


def misfits(rules: Rules) -> list[str]:
    """Catalog problems that need the kernel rules: a unit kind that cannot do its job kind."""
    dr = rules.director
    return [
        f"{op.id}: {kind} cannot take a {job.kind} job"
        for op in (dr.operations if dr else ())
        for job in op.jobs
        for kind in dict.fromkeys(job.unit_kinds)
        if not fits(rules, kind, job.kind)
    ]
