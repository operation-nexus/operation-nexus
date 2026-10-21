"""Fog of war: Tier 2 tracks, facility discovery (FOG-OF-WAR FOW-1, FOW-4..6a, FOW-9..13; NX-150).

`sense` is the SC-13 `sensing` system. On ticks where `tick % fow.track_every_ticks == 0` it
computes, per side, the enemy entities inside any of that side's sensors: `sensor.radius_m` x the
target's `stealth`, no RNG (Q-FOW-2), via the SC-10 grid (cell = max sensor radius / 2). The result
is `World.contacts` (world state): a tracked contact holds the target's kind, position and velocity
at that pass; one no longer tracked keeps those frozen and becomes a last-known track that ages
every running tick and is dropped after `fow.track_fade_s`, whether or not the entity still exists
(FOW-6a); a facility (STATIC) that is no longer tracked is dropped, as facilities never leave
last-known tracks (FOW-13). Re-tracking a contact makes it a tracked contact again. Nothing runs
while paused (FOW-9). Between passes everything reads the last computed view (Q-FOW-6). Both sides
use the same code (FOW-4).

Terrain masking (Q-FOW-3): a GROUND target in a cell of `Rules.masking` is tracked only by a sensor
standing in one of that cell's regions. Aircraft join when entities carry an altitude band
(NOE/LOW, `default_alt_band`, NX-124); STATIC targets are never masked (COMBAT §5.3).

Emitters and discovery (FOW-11, FOW-13): `Entity.emitting` is None for a kind that never emits,
True while emitting, False while dark; a dark site senses nothing. On each pass a side observes
an enemy facility it tracks, or an emitting one within `sensor.passive_range_m` of one of its
passive sensors; observing it writes its permanent `FacilityMarker` with the site's kind, variant,
position and emitting flag as of this tick. An unobserved site's marker keeps its old values.

Not here yet: Tier 1 SIGINT blobs and the painted flag (NX-150 part 2b), node owners in the view
and discovery by capturing a base (capture, NX-125).
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from nexus.contracts.gen.common.enums import Side
from nexus.core.rules import Rules
from nexus.core.spatial import UniformGrid
from nexus.core.world import Contact, Entity, FacilityMarker, Vec2, World

_STATIC = "STATIC"
_GROUND = "GROUND"
_NOWHERE: frozenset[str] = frozenset()
_ENEMY_OF: Mapping[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}


def sense(world: World) -> None:
    rules = world.rules
    if rules is None or world.campaign.clock_paused:
        return
    for side, known in world.contacts.items():
        expired = False
        for c in known.values():
            if c.age is not None:
                c.age += 1
                expired |= c.age >= rules.track_fade_ticks
        if expired:
            world.contacts[side] = {
                i: c for i, c in known.items() if c.age is None or c.age < rules.track_fade_ticks
            }
    if (world.campaign.tick + 1) % rules.track_every_ticks:
        return
    cell_m = max(rules.sensor_radius_m.values(), default=0.0) / 2
    for side in _ENEMY_OF:
        tracked = _detect(world, rules, UniformGrid(cell_m), side) if cell_m > 0 else []
        world.contacts[side] = _merge(world, rules, world.contacts[side], tracked)
        _discover(world, rules, side, tracked)


def _detect(world: World, rules: Rules, grid: UniformGrid, side: Side) -> list[int]:
    """Ids of enemy entities inside any of `side`'s sensors, ascending (a pure function)."""
    grid.rebuild(e for e in world.entities() if e.side != side)  # targets only
    found: set[int] = set()  # membership only; the result is sorted
    for s in world.entities():
        radius = rules.sensor_radius_m[s.kind]
        if s.side != side or radius <= 0 or s.emitting is False:  # dark: no coverage (FOW-11)
            continue
        here = _regions(rules, s.pos)
        for i in grid.query_radius(s.pos, radius):
            if i in found:
                continue
            t = world.get(i)
            reach = radius * rules.stealth[t.kind]
            if _dist2(t.pos, s.pos) <= reach * reach and not _masked(rules, t, here):
                found.add(i)
    return sorted(found)


def _dist2(a: Vec2, b: Vec2) -> float:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _regions(rules: Rules, pos: Vec2) -> frozenset[str]:
    """The masking regions covering `pos` (Q-FOW-3)."""
    cell = (int(pos.x // rules.mask_cell_m), int(pos.y // rules.mask_cell_m))
    return rules.masking.get(cell, _NOWHERE)


def _masked(rules: Rules, target: Entity, sensor_regions: frozenset[str]) -> bool:
    """A GROUND target in a masking region, seen by a sensor in none of its regions."""
    if rules.domain[target.kind] != _GROUND:
        return False
    regions = _regions(rules, target.pos)
    return bool(regions) and regions.isdisjoint(sensor_regions)


def _heard(world: World, rules: Rules, side: Side) -> list[int]:
    """Emitting enemy sites (STATIC domain only, FOW-11) within a passive range of one of
    `side`'s live, non-dark sensors.
    shortcut: emitters x passive sensors, no grid; emitters are the few pre-placed sites. Use the
    grid if a theater's emitters or passive sensors reach the hundreds (SC-10 smoke test)."""
    emitters = [
        e
        for e in world.entities()
        if e.side != side and e.emitting and rules.domain[e.kind] == _STATIC
    ]
    if not emitters:
        return []
    ears = [
        (s.pos, r * r)
        for s in world.entities()
        if s.side == side and (r := rules.passive_range_m[s.kind]) > 0 and s.emitting is not False
    ]
    return [e.id for e in emitters if any(_dist2(e.pos, p) <= r2 for p, r2 in ears)]


def _discover(world: World, rules: Rules, side: Side, tracked: list[int]) -> None:
    """FOW-13: write the marker of every enemy facility `side` observes this pass."""
    seen = {i for i in tracked if rules.domain[world.get(i).kind] == _STATIC}
    seen.update(_heard(world, rules, side))
    if not seen:
        return
    markers, tick = world.markers[side], world.campaign.tick + 1  # the tick being computed
    for i in seen:
        e = world.get(i)
        markers[i] = FacilityMarker(e.kind, e.variant, e.pos, e.emitting, tick)
    world.markers[side] = dict(sorted(markers.items()))


def _merge(
    world: World, rules: Rules, old: dict[int, Contact], tracked: list[int]
) -> dict[int, Contact]:
    now = {i: Contact(e.kind, e.pos, e.vel) for i in tracked for e in [world.get(i)]}
    for i, c in old.items():
        if i not in now:
            if c.age is None and rules.domain[c.kind] == _STATIC:
                continue  # facilities never leave last-known tracks; markers do (FOW-13, part 2)
            if c.age is None:
                c.age = 0  # coverage lost: freeze as a last-known track (FOW-6a)
            now[i] = c
    return dict(sorted(now.items()))


def tracked_by(world: World, side: Side, entity_id: int) -> bool:
    """`side` currently tracks the entity, as of the last pass (Q-FOW-6)."""
    c = world.contacts[side].get(entity_id)
    return c is not None and c.age is None


def spotted(world: World, entity: Entity) -> bool:
    """FOW-12: any enemy sensor tracks this unit. Says nothing about what or where."""
    return tracked_by(world, _ENEMY_OF[entity.side], entity.id)


def visible(world: World, side: Side, entity: Entity) -> bool:
    """FOW-1 predicate: `side`'s own entities and the enemy ones it currently tracks. A
    last-known track is not a visible entity; it appears only in `SideView.last_known`.
    `visible(world, "COALITION", e)` decides what the public payloads may carry."""
    return entity.side == side or tracked_by(world, side, entity.id)


@dataclass(frozen=True, slots=True)
class SideView:
    """What one side knows of the enemy (FOW-4, FOW-10); `side_view(world, "ENEMY")` is the
    director's `EnemyView`. Copies, so a reader cannot change world state. Decision code takes
    this, never the `World`."""

    side: Side
    tracks: Mapping[int, Contact]
    last_known: Mapping[int, Contact]
    nodes: Mapping[str, tuple[int, int]]  # every node's position, m (FOW-10)
    markers: Mapping[int, FacilityMarker]  # discovered enemy facilities (FOW-13)


def side_view(world: World, side: Side) -> SideView:
    if world.rules is None:
        raise ValueError("side_view needs the world's rules")
    known = world.contacts[side]
    return SideView(
        side,
        {i: replace(c) for i, c in known.items() if c.age is None},
        {i: replace(c) for i, c in known.items() if c.age is not None},
        dict(world.rules.roads.pos),
        {i: replace(m) for i, m in world.markers[side].items()},
    )
