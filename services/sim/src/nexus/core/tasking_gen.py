"""Tasking Board job generation (GAMEPLAY §1b, TB-4, TB-9; NX-374).

`generate` returns the jobs one side's board should hold now, as `JobSpec`s. TB-9: it reads only
that side's `SideView` (FOG-OF-WAR FOW-4, FOW-8) plus the side's own state: its nodes' stock, its
facilities, the capture bars on its nodes, and the node defense hp, which is node state that
combat uses without a track (COMBAT CB-10, FOW-10). The objective is the coalition's. No spec
refers to an entity id, so a job names a node, or a SIGINT blob with its cell centre.

- **Resupply** (`resupply:<node>`): a node the side owns, with stock, below its starvation floor or
  with damaged facilities (Q-GP-47). Urgency: the larger of the stock deficit share (floor - stock)
  / floor and the facilities' missing hp share, on top of 1.0. A node below its forward stock
  target (`Supply.stock_target`, Q-SIM-100, NX-389) gets one too (stocking), urgency
  `tasking.stock_urgency` plus `tasking.stock_front_bonus` on the front line (`_on_front`, the
  patrol rule), below 1.0; when both apply the higher urgency wins. Slots: one per
  `resupply_stock_per_slot` of missing stock (max stock - stock, rounded up; for a stocking-only
  job, target - stock), 1 to `resupply_slots_max`.
- **Defend** (`defend:<node>`): a node the side owns that can be captured and is threatened: the
  other side's capture bar is on it, or a tracked enemy GROUND unit is within
  `tasking.defend_radius_m` of it (Q-SIM-74). Urgency: 1.0 + the larger of the bar's share and
  `1 - d / radius` for the nearest tracked enemy at distance `d` (0 at the radius, 1 at the base),
  capped at `urgency_max`.
- **Strike** (`strike:<node>`): an enemy-held node whose defense hp is above 0 that is the active
  objective (coalition only, urgency at the cap), or holds a discovered facility marker whose
  last-known state is not Disabled (urgency 1.0 + its kind's `threat` / 100, capped).
  Q-SIM-92: each strike job gets one extra slot per idle armed viewer unit (up to
  `tasking.strike_max_scaled_slots`); with idle ones left and none of the above open, the
  `tasking.strike_idle_targets_max` foe-held nodes with defense hp nearest a node of the side's
  (ties by id) get a job, urgency 1.0, once the Static's tier is at least
  `tasking.strike_idle_targets_min_tier`.
- **Assist objective** (`assist:<node>`, coalition only): the active objective's node, urgency at
  the cap (the objective flag). It ends with the objective.
- **Scout** (`scout:<cell>`): each SIGINT blob in the side's view (a group it senses but cannot
  track) whose cell is not cooling down after a scout job ended, however
  (`tasking.scout_cooldown_min`), at most
  `tasking.scout_open_max` of them at once.
  Urgency by size bucket: S 1.0, M 1.5, L 2.0 (capped).
- **Escort convoy** (`escort:<truck id>`, Q-GP-29, Q-GP-47): a carrier of the side that has a road
  path and follows no one (a column is covered by its lead truck's job), whose route (its position
  through the nodes of its path) passes within a detected threat: the ring of a discovered
  air-defense site last seen not Disabled, or within `tasking.defend_radius_m` of a currently
  tracked enemy (last-known tracks and unseen emitters do not count). Urgency 1.0. Taking it is a
  follow order on the truck; it ends when the truck arrives.
- **Patrol** (`patrol:<node>`, coalition only, Q-SIM-94, NX-382): a front-line node: held by the
  side, not a sanctuary or bridge, with a road neighbour the side does not hold. At most
  `tasking.patrol_max_nodes`, those nearest a node the other side holds first (exact squared
  straight-line distance, as the idle strike targets are ordered by distance; ties by node id), and
  only while a viewer's armed or recon unit of the side is idle. Urgency 1.0.

- **Intercept** (`intercept:<entity>`, the Static's only, Q-SIM-96, NX-382): a coalition painter
  aircraft the side's view currently tracks (a last-known track does not count) inside
  `director.intercept.radius_m` of a node the side holds, kept tracked there at every board pass for
  `director.intercept.reaction_s` (`pol_linger_s` at Pattern of Life), counted from the first pass
  that saw it (`World.intercept_seen`, set by `nexus.core.tasking`). It carries the track's
  position. Urgency 1.0.

A kind is generated only while the side can staff it: a live unit of the side fits it, or, for
the coalition, a viewer can JOIN as a role that fits. A scout is posted for a cell only once a
blob has been in it for 2 consecutive SIGINT refreshes (`World.blob_runs`), so a blob crossing
cells posts nothing.

`GENERATED` lists the key prefixes the board owns: an unclaimed job with one of them that is not
generated again is dropped (its condition ended). A job posted by anything else (the director, a
GM) is not.
"""

import math
from collections.abc import Iterator, Mapping
from fractions import Fraction
from itertools import pairwise
from typing import NamedTuple

from nexus.contracts.gen.common.enums import JobKind, NodeOwner, Side, UnitKind
from nexus.core.director import TIERS
from nexus.core.fog import SideView
from nexus.core.logistics import facility_damage
from nexus.core.rules import CAPTURE_FULL, Rules, TaskingRules
from nexus.core.world import Contact, Entity, Vec2, World

POST_GATE = (
    "post-gate"  # a `World.cooldown` key (cells are digits): no new scout job until its tick
)
GENERATED = (
    "resupply:",
    "defend:",
    "strike:",
    "assist:",
    "scout:",
    "escort:",
    "patrol:",
    "intercept:",
)
_GROUND, _AIR = "GROUND", "AIR"
_JOB_KINDS: tuple[JobKind, ...] = (
    "RESUPPLY", "SCOUT", "DEFEND", "STRIKE", "ASSIST_OBJECTIVE", "ESCORT_CONVOY", "PATROL",
    "INTERCEPT",
)  # fmt: skip
_STATIC: Side = "ENEMY"
_FOE: dict[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}


class JobSpec(NamedTuple):
    """A job to post (`tasking.post_job`): `urgency` in thousandths; `objective` makes the job end
    with that objective instead of expiring."""

    kind: JobKind
    key: str
    slots: int
    urgency: int
    node: str | None = None
    blob: str | None = None
    pos: Vec2 | None = None
    objective: int | None = None
    depends_on: int | None = None
    entity: int | None = None  # an escort job: the truck; an intercept job: the scout
    via: str | None = None  # a patrol job: the node it drives out to before it goes home


def fits(rules: Rules, kind: UnitKind, job_kind: JobKind) -> bool:
    """Whether a unit kind can do a job kind (the role(s) that fit, GAMEPLAY §1b), from what the
    kind can do: carriers resupply, painters (recon) scout, armed aircraft strike, armed aircraft
    and ground units defend, any ground unit (a capturer) assists an objective, armed or recon
    aircraft escort (strike and recon units, GAMEPLAY §1b). The Director's jobs (NX-156): any
    aircraft or ground unit that is not a carrier stages, a ground one captures (NX-157). A patrol
    (the Director's, and the coalition board's, Q-SIM-94) takes an armed or recon unit of either
    domain."""
    domain = rules.domain[kind]
    match job_kind:
        case "RESUPPLY":
            return kind in rules.supply.carriers
        case _ if kind in rules.supply.carriers:
            return False  # a carrier only hauls; capture runs are direct orders
        case "SCOUT":
            return kind in rules.painters
        case "STRIKE":
            return domain == _AIR and kind in rules.armed
        case "DEFEND":
            return domain in (_AIR, _GROUND) and kind in rules.armed
        case "ASSIST_OBJECTIVE":
            return domain == _GROUND
        case "ESCORT_CONVOY":
            return domain == _AIR and (kind in rules.armed or kind in rules.painters)
        case "STAGE":
            return domain in (_AIR, _GROUND)
        case "PATROL":
            return domain in (_AIR, _GROUND) and (kind in rules.armed or kind in rules.painters)
        case "CAPTURE":
            return domain == _GROUND
        case "INTERCEPT":
            return domain == _AIR and kind in rules.armed  # `can_hit` asks the loaded weapons
    return False


def can_hit(rules: Rules, e: Entity, target: UnitKind) -> bool:
    """`e` holds a round of a weapon that reaches `target`'s domain and (an aircraft) its default
    altitude band, as the escort's `_own_reach` reads the shooter's own state."""
    cr = rules.combat
    if cr is None:
        return False
    domain, band = rules.domain[target], cr.units[target].alt_band
    return any(
        rounds > 0 and domain in w.targets and (domain != _AIR or band in w.bands)
        for w, rounds in zip(cr.loadout(e.kind, e.variant), e.ammo, strict=True)
    )


def held_within(
    nodes: Mapping[str, tuple[float, float]], owners: Mapping[str, NodeOwner], side: Side,
    x: float, y: float, reach: float,
) -> bool:  # fmt: skip
    """The point is within `reach` of a node `side` holds."""
    return any(
        owners.get(n) == side and math.hypot(px - x, py - y) <= reach
        for n, (px, py) in nodes.items()
    )


def watched(world: World, rules: Rules, view: SideView) -> dict[int, Contact]:
    """The coalition painter aircraft `view` tracks now inside `director.intercept.radius_m` of a
    node its side holds, by id (Q-SIM-96). A wreck is not hunted: the unit must still exist and not
    be Disabled, a liveness read of the truth (as the job's DONE reads it) because a destroyed or
    Disabled scout's contact stays tracked until sensing drops it."""
    dr = rules.director
    if dr is None:
        return {}
    return {
        i: c for i, c in sorted(view.tracks.items())
        if (e := world.find(i)) is not None and e.damage_state != "DISABLED"
        and c.kind in rules.painters and rules.domain[c.kind] == _AIR
        and held_within(view.nodes, view.owners, view.side, c.pos.x, c.pos.y, dr.intercept_radius_m)
    }  # fmt: skip


def is_idle(rules: Rules, e: Entity, side: Side) -> bool:
    """Whether the board may give `e` a job: no job, no explicit order (a HOLD keeps it off), no
    route, not Disabled, not returning to base (TB-2)."""
    return (
        e.side == side and e.job_id is None and e.order is None and not e.path
        and e.damage_state != "DISABLED" and e.state != "RTB"
        and rules.domain[e.kind] in (_AIR, _GROUND)
    )  # fmt: skip


def _idle_strikers(world: World, rules: Rules, side: Side) -> int:
    """Idle viewer-owned units of the side that could strike now: they fit a STRIKE job and still
    hold ammo (Q-SIM-92)."""
    return sum(
        e.owner_kind == "COMMANDER"
        and is_idle(rules, e, side)
        and any(e.ammo)
        and fits(rules, e.kind, "STRIKE")
        for e in world.entities()
    )


def _idle_patrollers(world: World, rules: Rules, side: Side) -> bool:
    """Whether a viewer-owned unit of the side that fits a patrol is idle (Q-SIM-94)."""
    return any(
        e.owner_kind == "COMMANDER" and is_idle(rules, e, side) and fits(rules, e.kind, "PATROL")
        for e in world.entities()
    )


def _able(world: World, rules: Rules, side: Side) -> set[JobKind]:
    """Job kinds the side can staff: a live unit of it fits, or, for the coalition, a viewer can
    JOIN as a role that fits (a parameterless JOIN takes its job at once, Q-GP-23)."""
    kinds = {e.kind for e in world.entities() if e.side == side and e.damage_state != "DISABLED"}
    if side == "COALITION":
        kinds |= set(rules.role_kind.values())
    return {j for j in _JOB_KINDS if any(fits(rules, k, j) for k in kinds)}


def _urgency(tr: TaskingRules, share: Fraction) -> int:
    # Q-GP-20: an urgency runs from 1.0 (1000 thousandths) by `share` (0..1) up to the tunable
    # `urgency_max`; the 1.0 floor and the unit-width share are the definition of the multiplier.
    return min(tr.urgency_max_milli, 1000 + math.floor(share * 1000))


def generate(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> list[JobSpec]:
    able = _able(world, rules, side)
    specs = [
        *_resupply(world, rules, tr, side, view),
        *_defend(world, rules, tr, side, view),
        *(_strike(world, rules, tr, side, view) if _offense_open(world, tr, side) else ()),
        *_assist(world, tr, side),
        *_scout(tr, view, world, side),
        *_escort(world, rules, tr, side, view),
        *_patrol(world, rules, tr, side, view),
        *_intercept(world, rules, tr, side, view),
    ]
    return _cap_scouts([s for s in specs if s.kind in able], world, tr, side)


def _offense_open(world: World, tr: TaskingRules, side: Side) -> bool:
    """The Static's board posts the strikes it generates only from `tasking.static_offense_min_tier`
    up (Q-SIM-85: no offensives from the board at Pattern of Life); the Director's own operations
    post their jobs themselves, and the coalition's board is not gated."""
    if side != _STATIC:
        return True
    return TIERS.index(world.director[side].tier) >= TIERS.index(tr.static_offense_min_tier)


def _idle_targets_open(world: World, tr: TaskingRules) -> bool:
    """Idle-viewer strikes (Q-SIM-92) wait for the Static's tier to reach
    `tasking.strike_idle_targets_min_tier`, so a lone new viewer provokes nothing (Q-SIM-86)."""
    tier = world.director[_STATIC].tier
    return TIERS.index(tier) >= TIERS.index(tr.strike_idle_targets_min_tier)


def _cap_scouts(specs: list[JobSpec], world: World, tr: TaskingRules, side: Side) -> list[JobSpec]:
    """At most `tasking.scout_open_max` generated scout jobs on the board: those already claimed
    stay, then those already posted, then at most one new one per `tasking.scout_post_interval_min`
    (the highest urgency, ties by key; the blob jobs of moving
    units would otherwise flood a board, NX-156). An unclaimed one left out expires as no longer
    generated."""
    posted = {
        j.key: bool(j.claims) for j in world.boards[side].values() if j.key.startswith("scout:")
    }
    claimed = {k for k, c in posted.items() if c}
    # claimed first, then those already posted (no churn), then the highest urgency, then key
    rest = sorted(
        (s for s in specs if s.kind == "SCOUT" and s.key not in claimed),
        key=lambda s: (s.key not in posted, -s.urgency, s.key),
    )
    keep = set(claimed)
    gated = world.cooldown[side].get(POST_GATE, 0) > world.campaign.running_ticks + 1
    for s in rest:
        if len(keep) >= tr.scout_open_max:
            break
        if s.key in posted:
            keep.add(s.key)
        elif not gated:  # one new scout job per board per interval (Q-DEV-21)
            keep.add(s.key)
            gated = True
    return [s for s in specs if s.kind != "SCOUT" or s.key in keep]


def _resupply(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    sup, damage = rules.supply, facility_damage(world, rules, side)
    for node in sorted(sup.max_stock):
        top, stock, floor = sup.max_stock[node], world.stock.get(node, 0), sup.starve_floor[node]
        if top <= 0 or view.owners.get(node) != side:
            continue
        starved = Fraction(floor - stock, floor) if stock < floor else Fraction(0)
        missing_hp, max_hp = damage.get(node, (0, 1))
        need = max(starved, Fraction(missing_hp, max_hp))
        stocking = 0  # below the forward stock target (Q-SIM-100): the stocking urgency
        if stock < sup.stock_target[node]:
            front = tr.stock_front_bonus_milli if _on_front(rules, view, side, node) else 0
            stocking = tr.stock_urgency_milli + front
        if need or stocking:
            fill = top if need else sup.stock_target[node]  # stocking fills up to the target only
            slots = -(-(fill - stock) // tr.resupply_stock_per_slot)
            yield JobSpec(
                "RESUPPLY", f"resupply:{node}", min(tr.resupply_slots_max, max(1, slots)),
                max(_urgency(tr, need) if need else 0, stocking), node=node,
            )  # fmt: skip


def _defend(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    reach = tr.defend_radius_m
    for node, (x, y) in sorted(view.nodes.items()):
        if view.owners.get(node) != side or rules.node_kind[node] in rules.uncapturable:
            continue
        bar = world.capture.get(node)  # a bar on an owned node is always the other side's
        share = Fraction(bar.progress, CAPTURE_FULL) if bar is not None else Fraction(0)
        nearest = min(  # the closest tracked enemy ground unit within the radius
            (
                math.hypot(c.pos.x - x, c.pos.y - y)
                for c in view.tracks.values()
                if rules.domain[c.kind] == _GROUND
            ),
            default=math.inf,
        )
        if nearest <= reach:
            share = max(share, Fraction(1) - Fraction(nearest) / Fraction(reach))
        if share or nearest <= reach:
            yield JobSpec(
                "DEFEND", f"defend:{node}", tr.slots["DEFEND"], _urgency(tr, share), node=node
            )


def _strike(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    foe, free = _FOE[side], _idle_strikers(world, rules, side)
    slots = tr.slots["STRIKE"] + min(tr.strike_max_scaled_slots, free)  # Q-SIM-92
    targets: dict[str, JobSpec] = {}
    rear = rules.supply.rear["ENEMY"]  # never struck: combat never fires at it (Q-SIM-64, NX-396)
    o = world.objective if side == "COALITION" else None
    if (
        o is not None and o.node_id != rear
        and view.owners.get(o.node_id) == foe and view.defense_hp.get(o.node_id, 0)
    ):  # fmt: skip
        targets[o.node_id] = JobSpec(
            "STRIKE", f"strike:{o.node_id}", slots, tr.urgency_max_milli, node=o.node_id,
            objective=o.id,
        )  # fmt: skip
    at = {(float(x), float(y)): n for n, (x, y) in view.nodes.items()}
    threats: dict[str, int] = {}  # node -> the highest `threat` of its discovered sites
    for _, m in sorted(view.markers.items()):
        node = at.get((m.pos.x, m.pos.y))
        if (
            node is None or node == rear or view.owners.get(node) != foe
            or m.state == "DISABLED" or not view.defense_hp.get(node, 0)
        ):  # fmt: skip
            continue
        threat = rules.combat.units[m.kind].threat if rules.combat else 0
        threats[node] = max(threats.get(node, 0), threat)
    for node, threat in sorted(threats.items()):
        if node not in targets:
            urgency = min(tr.urgency_max_milli, 1000 + tr.strike_urgency_per_threat_milli * threat)
            targets[node] = JobSpec("STRIKE", f"strike:{node}", slots, urgency, node=node)
    if free and not targets and _idle_targets_open(world, tr):  # known defended foe nodes
        mine = [p for n, p in sorted(view.nodes.items()) if view.owners.get(n) == side]
        near = sorted(
            (min((math.hypot(x - mx, y - my) for mx, my in mine), default=math.inf), n)
            for n, (x, y) in view.nodes.items()
            if n != rear and view.owners.get(n) == foe and view.defense_hp.get(n, 0)
        )
        for _, n in near[: tr.strike_idle_targets_max]:
            targets[n] = JobSpec("STRIKE", f"strike:{n}", slots, 1000, node=n)
    for node in sorted(targets):
        yield targets[node]


def _assist(world: World, tr: TaskingRules, side: Side) -> Iterator[JobSpec]:
    o = world.objective
    if o is not None and side == "COALITION":
        yield JobSpec(
            "ASSIST_OBJECTIVE", f"assist:{o.node_id}", tr.slots["ASSIST_OBJECTIVE"],
            tr.urgency_max_milli, node=o.node_id, objective=o.id,
        )  # fmt: skip


def _scout(tr: TaskingRules, view: SideView, world: World, side: Side) -> Iterator[JobSpec]:
    now, cooling, runs = (
        world.campaign.running_ticks + 1,
        world.cooldown[side],
        world.blob_runs[side],
    )
    for b in view.blobs:
        cell = b.id.split("-")[1]  # the refresh tick changes, the cell is the dedupe key
        if runs.get(cell, 0) < tr.scout_blob_runs or cooling.get(cell, 0) > now:
            continue  # not there for `scout_blob_runs` refreshes yet, or scouted lately (Q-SIM-75)
        urgency = min(tr.urgency_max_milli, tr.scout_urgency_milli[b.size])
        yield JobSpec("SCOUT", f"scout:{cell}", tr.slots["SCOUT"], urgency, blob=b.id, pos=b.pos)


def _patrol(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    if side != "COALITION" or not _idle_patrollers(world, rules, side):
        return
    foe = [p for n, p in view.nodes.items() if view.owners.get(n) == _FOE[side]]
    front = sorted(
        (min(((x - fx) ** 2 + (y - fy) ** 2 for fx, fy in foe), default=math.inf), n)
        for n, (x, y) in view.nodes.items()
        if _on_front(rules, view, side, n)
    )
    for _, n in front[: tr.patrol_max_nodes]:
        yield JobSpec("PATROL", f"patrol:{n}", tr.slots["PATROL"], 1000, node=n)


def _on_front(rules: Rules, view: SideView, side: Side, n: str) -> bool:
    """A front-line node (Q-SIM-94): held by the side, capturable (not a sanctuary or bridge), with
    a road neighbour the side does not hold. Patrols and the stocking bonus share it."""
    return (
        view.owners.get(n) == side
        and rules.node_kind[n] not in rules.uncapturable
        and any(view.owners.get(m) != side for m, _ in rules.roads.neighbours(n))
    )


def _intercept(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    dr = rules.director
    if side != _STATIC or dr is None:
        return
    pol = world.director[side].tier == "PATTERN_OF_LIFE"
    wait = dr.intercept_pol_linger_ticks if pol else dr.intercept_reaction_ticks
    now = world.campaign.running_ticks + 1
    for i, c in watched(world, rules, view).items():
        if i in world.intercept_seen and now - world.intercept_seen[i] >= wait:
            yield JobSpec(
                "INTERCEPT", f"intercept:{i}", tr.slots["INTERCEPT"], 1000, pos=c.pos, entity=i
            )


type _Segment = tuple[float, float, float, float, float]  # ax, ay, dx, dy, dx^2 + dy^2


def _segments(route: list[tuple[float, float]]) -> list[_Segment]:
    return [(ax, ay, bx - ax, by - ay, (bx - ax) ** 2 + (by - ay) ** 2)
            for (ax, ay), (bx, by) in pairwise(route)]  # fmt: skip


def _near_route(segs: list[_Segment], x: float, y: float, reach: float) -> bool:
    """The polyline passes within `reach` of the point."""
    r2 = reach * reach
    for ax, ay, dx, dy, length2 in segs:
        k = 0.0 if length2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
        ex, ey = ax + k * dx - x, ay + k * dy - y
        if ex * ex + ey * ey <= r2:
            return True
    return False


def _escort(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    rings = [(m.pos, m.ring_m) for _, m in sorted(view.markers.items())
             if m.ring_m is not None and m.state != "DISABLED"]  # fmt: skip
    reach = tr.defend_radius_m
    cells: dict[tuple[int, int], list[tuple[float, float]]] = {}  # tracked enemies, bucketed
    for c in view.tracks.values():
        cells.setdefault((math.floor(c.pos.x / reach), math.floor(c.pos.y / reach)), []).append(
            (c.pos.x, c.pos.y)
        )
    seen: dict[tuple[float, float, tuple[str, ...]], bool] = {}
    for e in world.entities():
        if (
            e.side != side or e.kind not in rules.supply.carriers or not e.path
            or e.follow_id is not None or e.damage_state == "DISABLED"
        ):  # fmt: skip
            continue
        key = (e.pos.x, e.pos.y, tuple(map(str, e.path)))  # a convoy's trucks share one answer
        if key not in seen:
            route = [(e.pos.x, e.pos.y), *(rules.roads.pos[str(p)] for p in e.path)]
            xs, ys = [x for x, _ in route], [y for _, y in route]
            box = (min(xs), min(ys), max(xs), max(ys))  # a point farther than its reach is out
            segs = _segments(route)
            seen[key] = any(
                _in_box(box, p.x, p.y, ring) and _near_route(segs, p.x, p.y, ring)
                for p, ring in rings
            ) or any(_near_route(segs, x, y, reach) for x, y in _tracks_in_box(cells, box, reach))
        threatened = seen[key]
        if threatened:
            yield JobSpec(
                "ESCORT_CONVOY", f"escort:{e.id}", tr.slots["ESCORT_CONVOY"], 1000, entity=e.id
            )


def _in_box(box: tuple[float, float, float, float], x: float, y: float, reach: float) -> bool:
    """The point is within `reach` of the box (a necessary condition for being within `reach` of
    anything inside it, so a cheap reject)."""
    return box[0] - reach <= x <= box[2] + reach and box[1] - reach <= y <= box[3] + reach


def _tracks_in_box(
    cells: dict[tuple[int, int], list[tuple[float, float]]],
    box: tuple[float, float, float, float],
    reach: float,
) -> Iterator[tuple[float, float]]:
    """The bucketed points within `reach` of the box (cells are `reach` wide)."""
    x0, y0 = math.floor((box[0] - reach) / reach), math.floor((box[1] - reach) / reach)
    x1, y1 = math.floor((box[2] + reach) / reach), math.floor((box[3] + reach) / reach)
    if (x1 - x0 + 1) * (y1 - y0 + 1) > len(cells):  # a long route: scan the occupied cells
        keys = [k for k in cells if x0 <= k[0] <= x1 and y0 <= k[1] <= y1]
    else:
        keys = [
            (kx, ky) for kx in range(x0, x1 + 1) for ky in range(y0, y1 + 1) if (kx, ky) in cells
        ]
    for key in keys:
        for x, y in cells[key]:
            if _in_box(box, x, y, reach):
                yield x, y
