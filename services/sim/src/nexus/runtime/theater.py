"""Theater loader: strict YAML, schema, then the CONFIG-AND-CONTENT §9.2 rules (NX-120).

Checked here: the slug matches the file name, TH-1 (unique ids and names), TH-2, TH-3, TH-4, TH-5,
TH-6, TH-10 and facility variants (CONFIG-AND-CONTENT §7.3); TH-11 (TBD) is `load_model`'s.
Deferred: name moderation (TH-1, CFG-8) and TH-7 (needs the unit catalog), TH-8 (the schema
accepts no terrain file yet), sector overlap and coverage (geometry with no reader yet), TH-9
(reported, not enforced).
"""

import unicodedata
from collections import Counter
from collections.abc import Container, Iterable
from fractions import Fraction
from pathlib import Path

from nexus.contracts.gen.config.theater import Node, TheaterConfig
from nexus.core.roads import ROAD, Road, RoadGraph, shortest_path
from nexus.runtime.config import ConfigError, load_model

# PROPOSED (NX-120, owner may veto): how far a bridge may sit from the straight line of its edge.
BRIDGE_TOLERANCE_M = 1000
# PROPOSED (NX-150, owner may veto): the masking raster's cell, m (Q-FOW-3). Finer than the SC-10
# sensing grid (60 km cells on strait-1), which would blur a 35 km-wide region into 60 km.
MASK_CELL_M = 1000
_BRIDGE = "BRIDGE"
# CONFIG-AND-CONTENT §7.3: AIR_DEFENSE_SITE has short-range AAA and SAM variants; RADAR_SITE none.
# shortcut: listed here until the unit catalog lists variants (§7a); move them there then.
_VARIANTS = {"AIR_DEFENSE_SITE": frozenset({"SAM", "SHORT_RANGE"}), "RADAR_SITE": frozenset()}

type Point = tuple[int, int]


def load_theater(path: Path) -> TheaterConfig:
    """Load and validate a theater file; every problem names the file and its key path."""
    theater = load_model(path, TheaterConfig)
    problems = [] if theater.slug == path.stem else [f"slug: {theater.slug!r} is not the file name"]
    problems += _check(theater)
    if problems:
        raise ConfigError(f"{path}: {'; '.join(problems)}")
    return theater


def road_graph(theater: TheaterConfig) -> RoadGraph:
    """The kernel's plain-data road graph: ROAD edges only (sea lanes join with the navy, P3)."""
    pos = {n.id: (n.pos[0], n.pos[1]) for n in theater.nodes}
    roads = [Road(e.a, e.b, e.speed_mult, e.bridge) for e in theater.edges if e.layer == ROAD]
    return RoadGraph(pos, roads)


def masking_cells(theater: TheaterConfig) -> tuple[int, dict[tuple[int, int], frozenset[str]]]:
    """Q-FOW-3: the cell size `MASK_CELL_M` and every such cell whose centre is inside a masking
    region (edges count, integer metres) -> the ids of those regions. The cell size comes with
    the cells so a reader cannot pair them with another. Scans each region's bounding box only."""
    half, cells = MASK_CELL_M // 2, dict[tuple[int, int], frozenset[str]]()
    for m in theater.terrain.masking_regions:
        poly = [_pt(p) for p in m.polygon]
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        for i in range(min(xs) // MASK_CELL_M, max(xs) // MASK_CELL_M + 1):
            for j in range(min(ys) // MASK_CELL_M, max(ys) // MASK_CELL_M + 1):
                centre = (i * MASK_CELL_M + half, j * MASK_CELL_M + half)
                if _in_polygon(centre, poly):
                    cells[i, j] = cells.get((i, j), frozenset()) | {m.id}
    return MASK_CELL_M, cells


def _check(t: TheaterConfig) -> list[str]:
    nodes = {n.id: n for n in t.nodes}
    problems = _unique(t) + _references(t, nodes)
    problems += _edges(t, nodes) + _singletons(t, nodes) + _placement(t)
    # TH-3 walks the graph, so it needs every reference to resolve first.
    return problems or _reachable(t, nodes)


def _duplicates(values: Iterable[str], where: str) -> list[str]:
    counts = Counter(values)
    return [f"{where}: duplicate {v!r}" for v in sorted(counts) if counts[v] > 1]


def _fold(name: str) -> str:
    # shortcut: NFKC + casefold only; confusable folding (UTS #39) joins with moderation (CFG-8).
    return unicodedata.normalize("NFKC", name).casefold()


def _unique(t: TheaterConfig) -> list[str]:  # TH-1
    return (
        _duplicates((n.id for n in t.nodes), "nodes.id")
        + _duplicates((_fold(n.name) for n in t.nodes), "nodes.name")
        + _duplicates((s.id for s in t.sectors), "sectors.id")
        + _duplicates((f.id for f in t.facilities), "facilities.id")
        + _duplicates((m.id for m in t.terrain.masking_regions), "terrain.masking_regions.id")
    )


def _references(t: TheaterConfig, nodes: dict[str, Node]) -> list[str]:  # TH-2, TH-4 and refs
    sectors = {s.id for s in t.sectors}
    bridges = {k for k, n in nodes.items() if n.kind == _BRIDGE}
    refs: list[tuple[str, str, Container[str]]] = [
        (f"nodes.{i}.sector", n.sector, sectors) for i, n in enumerate(t.nodes)
    ]
    for i, e in enumerate(t.edges):
        refs += [(f"edges.{i}.a", e.a, nodes), (f"edges.{i}.b", e.b, nodes)]
        if e.bridge is not None:
            refs.append((f"edges.{i}.bridge", e.bridge, bridges))
    refs += [(f"facilities.{i}.base", f.base, nodes) for i, f in enumerate(t.facilities)]
    refs += [(f"spawns.{i}.node", s.node, nodes) for i, s in enumerate(t.spawns)]
    refs += [(k, getattr(t, k), nodes) for k in ("sanctuary", "enemy_hq", "forward_airbase")]
    return [f"{where}: unknown or wrong-kind id {v!r}" for where, v, ok in refs if v not in ok]


def _edges(t: TheaterConfig, nodes: dict[str, Node]) -> list[str]:  # TH-2, TH-4
    problems = _duplicates((f"{min(e.a, e.b)}~{max(e.a, e.b)}~{e.layer}" for e in t.edges), "edges")
    for i, e in enumerate(t.edges):
        if e.a == e.b:
            problems.append(f"edges.{i}: self-loop on {e.a!r}")
        ends, bridge = (nodes.get(e.a), nodes.get(e.b)), nodes.get(e.bridge or "")
        if bridge and ends[0] and ends[1]:
            off = _dist2_to_segment(_pt(bridge.pos), _pt(ends[0].pos), _pt(ends[1].pos))
            if off > BRIDGE_TOLERANCE_M**2:
                problems.append(f"edges.{i}.bridge: {bridge.id!r} is not on the edge")
    return problems


def _singletons(t: TheaterConfig, nodes: dict[str, Node]) -> list[str]:  # TH-5, TH-10, CFG-2
    problems = []
    for kind, owner, key in (("SANCTUARY", "COALITION", "sanctuary"), ("HQ", "ENEMY", "enemy_hq")):
        found = [n.id for n in t.nodes if n.kind == kind]
        if len(found) != 1 or nodes[found[0]].start_owner != owner or found[0] != getattr(t, key):
            problems.append(f"{key}: need exactly one {kind} node, owned by {owner}, named here")
    for i, n in enumerate(t.nodes):
        if (n.start_stock is None) != (n.kind == "SANCTUARY"):
            problems.append(f"nodes.{i}.start_stock: null (infinite) only and always on SANCTUARY")
    fwd = nodes.get(t.forward_airbase)
    if fwd and (fwd.kind, fwd.start_owner) != ("AIRBASE", "COALITION"):
        problems.append("forward_airbase: must be a COALITION AIRBASE")
    for i, f in enumerate(t.facilities):
        base = nodes.get(f.base)
        if base and base.start_owner == "NEUTRAL":
            problems.append(f"facilities.{i}.base: {f.base!r} starts NEUTRAL")
        if f.variant is not None and f.variant not in _VARIANTS[f.kind]:
            problems.append(f"facilities.{i}.variant: {f.variant!r} is not a {f.kind} variant")
    return problems


def _placement(t: TheaterConfig) -> list[str]:  # TH-6
    w, h = t.bounds_m.w, t.bounds_m.h
    points = [(f"nodes.{i}.pos", n.pos) for i, n in enumerate(t.nodes)]
    points += [(f"sectors.{i}.polygon", p) for i, s in enumerate(t.sectors) for p in s.polygon]
    masks = t.terrain.masking_regions
    points += [
        (f"terrain.masking_regions.{i}.polygon", p) for i, m in enumerate(masks) for p in m.polygon
    ]
    problems = [f"{k}: {p} is outside bounds_m" for k, p in points if p[0] > w or p[1] > h]
    sectors = {s.id: [_pt(p) for p in s.polygon] for s in t.sectors}
    for i, n in enumerate(t.nodes):
        if n.sector in sectors and not _in_polygon(_pt(n.pos), sectors[n.sector]):
            problems.append(f"nodes.{i}.pos: not inside sector {n.sector!r}")
    return problems


def _reachable(t: TheaterConfig, nodes: dict[str, Node]) -> list[str]:  # TH-3
    graph, intact = road_graph(t), frozenset[str]()
    problems = [
        f"nodes.{i}: {n.id!r} is not reachable by road from {t.sanctuary!r}"
        for i, n in enumerate(t.nodes)
        # A BRIDGE is reached through the edge that carries it (below).
        if n.kind != _BRIDGE and shortest_path(graph, t.sanctuary, n.id, blocked=intact) is None
    ]
    carried = {e.bridge for e in t.edges}
    sea = {end for e in t.edges if e.layer == "SEA_LANE" for end in (e.a, e.b)}
    for i, n in enumerate(t.nodes):
        if n.kind == _BRIDGE and n.id not in carried:
            problems.append(f"nodes.{i}: BRIDGE {n.id!r} is on no edge")
        if n.kind == "PORT" and n.id not in sea:
            problems.append(f"nodes.{i}: PORT {n.id!r} touches no SEA_LANE")
    return problems


def _pt(p: list[int]) -> Point:
    return p[0], p[1]


def _dist2_to_segment(p: Point, a: Point, b: Point) -> Fraction:
    """Exact squared distance from p to segment ab (integer inputs, no float rounding)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = Fraction((p[0] - a[0]) * dx + (p[1] - a[1]) * dy, length2) if length2 else Fraction(0)
    t = min(max(t, Fraction(0)), Fraction(1))
    return (p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2


def _in_polygon(p: Point, poly: list[Point]) -> bool:
    """Even-odd rule in exact integer arithmetic; a point on an edge counts as inside."""
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if cross == 0 and min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2):
            return True
        if (y1 > y) != (y2 > y) and (cross > 0) == (y2 > y1):
            inside = not inside
    return inside
