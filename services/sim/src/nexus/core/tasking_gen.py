"""Tasking Board job generation (GAMEPLAY §1b, TB-4, TB-9; NX-374).

`generate` returns the jobs one side's board should hold now, as `JobSpec`s. TB-9: it reads only
that side's `SideView` (FOG-OF-WAR FOW-4, FOW-8) plus the side's own state: its nodes' stock, its
facilities, the capture bars on its nodes, and the node defense hp, which is node state that
combat uses without a track (COMBAT CB-10, FOW-10). The objective is the coalition's. No spec
refers to an entity id, so a job names a node, or a SIGINT blob with its cell centre.

- **Resupply** (`resupply:<node>`): a node the side owns, with stock, below its starvation floor or
  with damaged facilities (Q-GP-47). Urgency: the larger of the stock deficit share (floor - stock)
  / floor and the facilities' missing hp share, on top of 1.0. Slots: one per
  `resupply_stock_per_slot` of missing stock (max stock - stock, rounded up), 1 to
  `resupply_slots_max`.
- **Defend** (`defend:<node>`): a node the side owns that can be captured and is threatened: the
  other side's capture bar is on it, or a tracked enemy GROUND unit is within
  `tasking.defend_radius_m` of it (Q-SIM-74). Urgency: 1.0 + the larger of the bar's share and
  `1 - d / radius` for the nearest tracked enemy at distance `d` (0 at the radius, 1 at the base),
  capped at `urgency_max`.
- **Strike** (`strike:<node>`): an enemy-held node whose defense hp is above 0 that is the active
  objective (coalition only, urgency at the cap), or holds a discovered facility marker whose
  last-known state is not Disabled (urgency 1.0 + its kind's `threat` / 100, capped).
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

A kind is generated only while the side can staff it: a live unit of the side fits it, or, for
the coalition, a viewer can JOIN as a role that fits. A scout is posted for a cell only once a
blob has been in it for 2 consecutive SIGINT refreshes (`World.blob_runs`), so a blob crossing
cells posts nothing.

`GENERATED` lists the key prefixes the board owns: an unclaimed job with one of them that is not
generated again is dropped (its condition ended). A job posted by anything else (the director, a
GM) is not.
"""

import math
from collections.abc import Iterator
from fractions import Fraction
from itertools import pairwise
from typing import NamedTuple

from nexus.contracts.gen.common.enums import JobKind, Side, UnitKind
from nexus.core.director import TIERS
from nexus.core.fog import SideView
from nexus.core.rules import CAPTURE_FULL, Rules, TaskingRules
from nexus.core.world import Vec2, World

POST_GATE = (
    "post-gate"  # a `World.cooldown` key (cells are digits): no new scout job until its tick
)
GENERATED = ("resupply:", "defend:", "strike:", "assist:", "scout:", "escort:")
_GROUND, _AIR = "GROUND", "AIR"
_UNDEFENDED = ("SANCTUARY", "BRIDGE")  # never captured (N-4, NX-373)
_BLOB_RUN = 2  # consecutive SIGINT refreshes a blob must stay in a cell before a scout is posted
_BLOB_URGENCY = {"S": 1000, "M": 1500, "L": 2000}  # thousandths: the size bucket spans 1.0 to 2.0
_JOB_KINDS: tuple[JobKind, ...] = (
    "RESUPPLY", "SCOUT", "DEFEND", "STRIKE", "ASSIST_OBJECTIVE", "ESCORT_CONVOY",
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
    entity: int | None = None  # an escort job: the truck
    via: str | None = None  # a patrol job: the node it drives out to before it goes home


def fits(rules: Rules, kind: UnitKind, job_kind: JobKind) -> bool:
    """Whether a unit kind can do a job kind (the role(s) that fit, GAMEPLAY §1b), from what the
    kind can do: carriers resupply, painters (recon) scout, armed aircraft strike, armed aircraft
    and ground units defend, any ground unit (a capturer) assists an objective, armed or recon
    aircraft escort (strike and recon units, GAMEPLAY §1b). The Director's jobs (NX-156): any
    aircraft or ground unit that is not a carrier stages, a ground one captures or patrols
    (NX-157)."""
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
        case "CAPTURE" | "PATROL":
            return domain == _GROUND
    return False


def _able(world: World, rules: Rules, side: Side) -> set[JobKind]:
    """Job kinds the side can staff: a live unit of it fits, or, for the coalition, a viewer can
    JOIN as a role that fits (a parameterless JOIN takes its job at once, Q-GP-23)."""
    kinds = {e.kind for e in world.entities() if e.side == side and e.damage_state != "DISABLED"}
    if side == "COALITION":
        kinds |= set(rules.role_kind.values())
    return {j for j in _JOB_KINDS if any(fits(rules, k, j) for k in kinds)}


def _urgency(tr: TaskingRules, share: Fraction) -> int:
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
    ]
    return _cap_scouts([s for s in specs if s.kind in able], world, tr, side)


def _offense_open(world: World, tr: TaskingRules, side: Side) -> bool:
    """The Static's board posts the strikes it generates only from `tasking.static_offense_min_tier`
    up (Q-SIM-85: no offensives from the board at Pattern of Life); the Director's own operations
    post their jobs themselves, and the coalition's board is not gated."""
    if side != _STATIC:
        return True
    return TIERS.index(world.director[side].tier) >= TIERS.index(tr.static_offense_min_tier)


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


def _facility_damage(world: World, rules: Rules, side: Side) -> dict[str, tuple[int, int]]:
    """Base -> (missing hp, max hp) over the side's facilities there (the side's own state)."""
    cr = rules.combat
    totals: dict[str, list[int]] = {}
    for e in world.entities():
        if cr is not None and e.side == side and e.base_id is not None:
            top = cr.units[e.kind].hp
            t = totals.setdefault(e.base_id, [0, 0])
            t[0] += top - e.hp
            t[1] += top
    return {n: (t[0], t[1]) for n, t in totals.items()}


def _resupply(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    sup, damage = rules.supply, _facility_damage(world, rules, side)
    for node in sorted(sup.max_stock):
        top, stock, floor = sup.max_stock[node], world.stock.get(node, 0), sup.starve_floor[node]
        if top <= 0 or view.owners.get(node) != side:
            continue
        starved = Fraction(floor - stock, floor) if stock < floor else Fraction(0)
        missing_hp, max_hp = damage.get(node, (0, 1))
        need = max(starved, Fraction(missing_hp, max_hp))
        if need:
            slots = -(-(top - stock) // tr.resupply_stock_per_slot)
            yield JobSpec(
                "RESUPPLY", f"resupply:{node}", min(tr.resupply_slots_max, max(1, slots)),
                _urgency(tr, need), node=node,
            )  # fmt: skip


def _defend(
    world: World, rules: Rules, tr: TaskingRules, side: Side, view: SideView
) -> Iterator[JobSpec]:
    reach = tr.defend_radius_m
    for node, (x, y) in sorted(view.nodes.items()):
        if view.owners.get(node) != side or rules.node_kind[node] in _UNDEFENDED:
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
    foe, slots = _FOE[side], tr.slots["STRIKE"]
    targets: dict[str, JobSpec] = {}
    o = world.objective if side == "COALITION" else None
    if o is not None and view.owners.get(o.node_id) == foe and view.defense_hp.get(o.node_id, 0):
        targets[o.node_id] = JobSpec(
            "STRIKE", f"strike:{o.node_id}", slots, tr.urgency_max_milli, node=o.node_id,
            objective=o.id,
        )  # fmt: skip
    at = {(float(x), float(y)): n for n, (x, y) in view.nodes.items()}
    threats: dict[str, int] = {}  # node -> the highest `threat` of its discovered sites
    for _, m in sorted(view.markers.items()):
        node = at.get((m.pos.x, m.pos.y))
        if (
            node is None or view.owners.get(node) != foe
            or m.state == "DISABLED" or not view.defense_hp.get(node, 0)
        ):  # fmt: skip
            continue
        threat = rules.combat.units[m.kind].threat if rules.combat else 0
        threats[node] = max(threats.get(node, 0), min(threat, 100))
    for node, threat in sorted(threats.items()):
        if node not in targets:
            urgency = min(tr.urgency_max_milli, 1000 + 10 * threat)
            targets[node] = JobSpec("STRIKE", f"strike:{node}", slots, urgency, node=node)
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
        if runs.get(cell, 0) < _BLOB_RUN or cooling.get(cell, 0) > now:
            continue  # not there for 2 refreshes yet, or scouted lately (Q-SIM-75)
        urgency = min(tr.urgency_max_milli, _BLOB_URGENCY[b.size])
        yield JobSpec("SCOUT", f"scout:{cell}", tr.slots["SCOUT"], urgency, blob=b.id, pos=b.pos)


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
