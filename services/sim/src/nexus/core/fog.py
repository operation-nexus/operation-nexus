"""Fog of war, Tier 2 tracks (FOG-OF-WAR FOW-1, FOW-4..6a, FOW-9, FOW-10, FOW-12; NX-150).

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

Not here yet (NX-150 part 2): terrain masking (Q-FOW-3), Tier 1 SIGINT blobs, emitters, passive
sensors and facility discovery (FOW-11, FOW-13), the painted flag (Q-FOW-6), node owners in the
view (world state with capture, NX-125).
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from nexus.contracts.gen.common.enums import Side
from nexus.core.rules import Rules
from nexus.core.spatial import UniformGrid
from nexus.core.world import Contact, Entity, World

_STATIC = "STATIC"
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


def _detect(world: World, rules: Rules, grid: UniformGrid, side: Side) -> list[int]:
    """Ids of enemy entities inside any of `side`'s sensors, ascending (a pure function)."""
    grid.rebuild(e for e in world.entities() if e.side != side)  # targets only
    found: set[int] = set()  # membership only; the result is sorted
    for s in world.entities():
        radius = rules.sensor_radius_m[s.kind]
        if s.side != side or radius <= 0:
            continue
        for i in grid.query_radius(s.pos, radius):
            if i in found:
                continue
            t = world.get(i)
            reach = radius * rules.stealth[t.kind]
            if (t.pos.x - s.pos.x) ** 2 + (t.pos.y - s.pos.y) ** 2 <= reach * reach:
                found.add(i)
    return sorted(found)


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


def side_view(world: World, side: Side) -> SideView:
    if world.rules is None:
        raise ValueError("side_view needs the world's rules")
    known = world.contacts[side]
    return SideView(
        side,
        {i: replace(c) for i, c in known.items() if c.age is None},
        {i: replace(c) for i, c in known.items() if c.age is not None},
        dict(world.rules.roads.pos),
    )
