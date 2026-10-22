"""Fog of war: Tier 1 SIGINT, Tier 2 tracks, painting, facility discovery (FOG-OF-WAR; NX-150).

`sense` is the SC-13 `sensing` system. On ticks where `tick % fow.track_every_ticks == 0` it
computes, per side, the enemy entities inside any of that side's sensors: `sensor.radius_m` (x
`damaged_sensor_mult` at Damaged or worse, CB-6) x the target's `stealth`, no RNG (Q-FOW-2), via
SC-10 grids, one per sensor range class. The result is `World.contacts` (world state): a tracked
contact holds the target's kind, position and velocity at that pass; one no longer tracked keeps
those frozen and becomes a last-known track that ages every running tick and is dropped after
`fow.track_fade_s`, whether or not the entity still exists (FOW-6a); a facility (STATIC) that is no
longer tracked is dropped, as facilities never leave last-known tracks (FOW-13). Re-tracking a
contact makes it a tracked contact again. Nothing runs while paused (FOW-9). Between passes
everything reads the last computed view (Q-FOW-6). Both sides use the same code (FOW-4).

Terrain masking (Q-FOW-3): a GROUND target, or an aircraft at the NOE or LOW altitude band
(`Entity.alt_band`, NX-124 part 3), in a cell of `Rules.masking` is tracked only by a sensor
standing in one of that cell's regions; STATIC targets are never masked (COMBAT §5.3).

Emitters and discovery (FOW-11, FOW-13): `Entity.emitting` is None for a kind that never emits,
True while emitting, False while dark; a dark site senses nothing, and neither does a Disabled
facility (it neither senses, emits nor listens until repaired, GAMEPLAY §5b; it is still tracked
and discovered like any site). On each pass a side observes
an enemy facility it tracks, or an emitting one within `sensor.passive_range_m` of one of its
passive sensors; observing it writes its permanent `FacilityMarker` with the site's kind, variant,
position, emitting flag, engagement ring (`ring_m`: its longest AIR weapon range for its variant,
m, or None) and damage state as of this tick. An unobserved site's marker keeps its old values.

Painting (Q-FOW-6): on each pass, a contact is `painted` when a recon unit of the side
(`Rules.painters`) tracks it with its own sensor within `fow.paint_range_m`. A last-known track is
never painted.

SIGINT (Tier 1, FOW-2, Q-FOW-7): after every `fow.sigint_refresh_s` of running world time (counted
in `World.sigint_age`, frozen while paused, FOW-9) each side's blobs are rebuilt from scratch: the
moving enemy mobile units it does not track that are within `fow.sigint_range_mult` x the sensor
radius of one of its non-dark radar sites, counted per square cell of `fow.sigint_cell_m`. Cell
`(cx, cy) = (floor(x / cell), floor(y / cell))`, clamped into the theater bounds (which the cell
divides, `make_rules`), has index `cy * (w / cell) + cx`; a blob is drawn at the cell's centre with
id `<refresh_tick>-<cell_index>` and a size bucket (`fow.sigint_size_m_min`, `_l_min`), so it
carries no entity id, exact count or exact position, and building it draws no RNG.

Base flips (`hand_over`, NX-125, FOW-13): the facility is now its new side's own, so that side drops
its contact and marker of it; the side that lost the base keeps a marker with the site as of the
flip tick, so it never needs a last-known track (facilities have none). The view carries every
node's live owner (FOW-10).

Not here yet: the `TargetPainted{recon_id, target_id, until_tick}` event with combat (NX-124),
`until_tick` being the next Tier 2 pass; emitting mobile units in blobs (Q-FOW-7 "moving or
emitting") once a mobile emitter exists.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace

from nexus.contracts.gen.common.enums import DamageState, NodeOwner, Side, UnitKind
from nexus.core.rules import Rules
from nexus.core.spatial import UniformGrid
from nexus.core.world import _ZERO, Blob, BlobSize, Contact, Entity, FacilityMarker, Vec2, World

_STATIC = "STATIC"
_STATES: tuple[DamageState, ...] = ("HEALTHY", "DAMAGED")  # a radius is the same at worse states
_GROUND, _AIR = "GROUND", "AIR"
LOW_BANDS = ("NOE", "LOW")  # the altitude bands terrain masks (Q-FOW-3, COMBAT §5.2)
_NOWHERE: frozenset[str] = frozenset()
_ENEMY_OF: Mapping[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}
_RADAR: UnitKind = "RADAR_SITE"
# A sensor range class spans radii up to this many times its smallest one. On three 1,000-entity
# layouts (NX-372) 4 was fastest or tied against 1 and 2 (more grid rebuilds) and well ahead of one
# class for all (3-8 km sensors scanning 60 km cells: ~15 ms a pass with two facing ground lines).
_CLASS_SPAN = 4.0


def sense(world: World) -> None:
    rules = world.rules
    if rules is None or world.frozen:
        return
    _age(world, rules)
    if not (world.campaign.tick + 1) % rules.track_every_ticks:
        _track(world, rules)
    world.sigint_age += 1
    if world.sigint_age >= rules.sigint_refresh_ticks:
        world.sigint_age = 0
        for side in _ENEMY_OF:
            world.blobs[side] = _sigint(world, rules, side)
            old = world.blob_runs[side]  # a blob staying in its cell lengthens its run
            cells = [b.id.split("-")[1] for b in world.blobs[side]]
            world.blob_runs[side] = {c: old.get(c, 0) + 1 for c in cells}


def _age(world: World, rules: Rules) -> None:
    """Last-known tracks gain a running tick and drop at `fow.track_fade_s` (FOW-6a)."""
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


def _track(world: World, rules: Rules) -> None:
    """One Tier 2 pass for both sides: tracks, painting and discovery."""
    cells = _class_cells(rules)
    for side in _ENEMY_OF:
        tracked, painted = _detect(world, rules, cells, side) if cells else ([], set())
        world.contacts[side] = _merge(world, rules, world.contacts[side], tracked, painted)
        _discover(world, rules, side, tracked)


def _class_cells(rules: Rules) -> dict[float, float]:
    """Effective sensor radius (healthy and damaged, CB-6) -> grid cell of its range class: radii
    ascending, a class spans up to
    `_CLASS_SPAN` x its smallest radius, and its cell is its largest radius / 2 (SC-10)."""
    cells: dict[float, float] = {}
    group: list[float] = []
    radii = {rules.sensor_radius(k, state) for k in rules.sensor_radius_m for state in _STATES}
    for r in [*sorted(r for r in radii if r > 0), math.inf]:
        if group and r > _CLASS_SPAN * group[0]:  # inf closes the last class
            cells |= dict.fromkeys(group, group[-1] / 2)
            group = []
        group.append(r)
    return cells


def _detect(
    world: World, rules: Rules, cells: Mapping[float, float], side: Side
) -> tuple[list[int], set[int]]:
    """Ids of enemy entities inside any of `side`'s sensors, ascending, and the subset one of its
    painters tracks within `fow.paint_range_m` (a pure function).

    One target grid per range class (NX-372). Painters paint first, then every sensor (longest
    first) tracks; a target leaves the grids once painted or tracked, so later scans see only the
    rest. Both results are unions, so neither order changes them."""
    sensors = sorted(
        (
            (s, r, _regions(rules, s.pos))
            for s in world.entities()
            if s.side == side
            and (r := rules.sensor_radius(s.kind, s.damage_state)) > 0
            and s.emitting is not False  # dark: no coverage (FOW-11)
            and not is_off_facility(rules, s)
        ),
        key=lambda sensor: -sensor[1],
    )
    targets = [e for e in world.entities() if e.side != side]
    grids: dict[float, UniformGrid] = {}
    found: set[int] = set()  # membership only; the result is sorted

    def grid(radius: float) -> UniformGrid:
        cell = cells[radius]
        if (g := grids.get(cell)) is None:
            g = grids[cell] = UniformGrid(cell)
            g.rebuild(t for t in targets if t.id not in found)
        return g

    def scan(
        sensor: Entity, radius: float, here: frozenset[str], limit2: float, out: set[int]
    ) -> None:
        # The old pass's exact arithmetic (NX-372): grid filter at `radius`, then `_dist2`.
        for t in grid(radius).within(sensor.pos, radius):
            d2 = _dist2(t.pos, sensor.pos)
            reach = radius * rules.stealth[t.kind]
            if d2 <= reach * reach and d2 <= limit2 and not _masked(rules, t, here):
                out.add(t.id)
                found.add(t.id)
                for g in grids.values():
                    g.remove(t)

    painted: set[int] = set()
    for s, r, here in sensors:
        if s.kind in rules.painters:  # its own track within paint range (Q-FOW-6)
            scan(s, r, here, rules.paint_range_m**2, painted)
    for s, r, here in sensors:
        scan(s, r, here, math.inf, found)
    return sorted(found), painted


def _dist2(a: Vec2, b: Vec2) -> float:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _regions(rules: Rules, pos: Vec2) -> frozenset[str]:
    """The masking regions covering `pos` (Q-FOW-3)."""
    cell = (int(pos.x // rules.mask_cell_m), int(pos.y // rules.mask_cell_m))
    return rules.masking.get(cell, _NOWHERE)


def in_masking_region(rules: Rules, pos: Vec2) -> bool:
    """`pos` is inside a theater masking region (Q-FOW-3); combat's masking factor uses it too."""
    return bool(_regions(rules, pos))


def is_off_facility(rules: Rules, e: Entity) -> bool:
    """A Disabled facility does nothing until repaired (GAMEPLAY §5b): it senses, emits and listens
    for no one, fires on no one, and is not a valid target (COMBAT CB-1)."""
    return e.damage_state == "DISABLED" and rules.domain[e.kind] == _STATIC


def _masked(rules: Rules, target: Entity, sensor_regions: frozenset[str]) -> bool:
    """A GROUND target, or an aircraft at a low band, in a masking region, seen by a sensor in none
    of its regions."""
    domain = rules.domain[target.kind]
    if domain != _GROUND and not (domain == _AIR and target.alt_band in LOW_BANDS):
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
        if e.side != side
        and e.emitting
        and rules.domain[e.kind] == _STATIC
        and not is_off_facility(rules, e)
    ]
    if not emitters:
        return []
    ears = [
        (s.pos, r * r)
        for s in world.entities()
        if s.side == side
        and (r := rules.passive_range_m[s.kind]) > 0
        and s.emitting is not False
        and not is_off_facility(rules, s)
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
        markers[i] = _marker(rules, e, tick)
    world.markers[side] = dict(sorted(markers.items()))


def _ring_m(rules: Rules, e: Entity) -> int | None:
    """A facility's engagement ring: its longest AIR weapon range for its variant, or None."""
    if rules.combat is None:
        return None
    ranges = [w.range_m for w in rules.combat.loadout(e.kind, e.variant) if _AIR in w.targets]
    return round(max(ranges)) if ranges else None


def _marker(rules: Rules, e: Entity, tick: int) -> FacilityMarker:
    return FacilityMarker(
        e.kind, e.variant, e.pos, _emitting(rules, e), tick, _ring_m(rules, e), e.damage_state
    )


def _emitting(rules: Rules, e: Entity) -> bool | None:
    """The marker's `emitting`: a Disabled emitter does not emit, so False (Q-SIM-66)."""
    return False if e.emitting and is_off_facility(rules, e) else e.emitting


def hand_over(world: World, facility: Entity, loser: Side) -> None:
    """A facility just switched from `loser` to `facility.side` with its base (FOW-13, Q-GP-25).
    The new side drops its contact and marker of it; `loser` gets a marker with the site's state
    as of this tick. Call after the side is set."""
    world.contacts[facility.side].pop(facility.id, None)
    world.markers[facility.side].pop(facility.id, None)
    world.contacts[loser].pop(facility.id, None)
    markers = world.markers[loser]
    tick = world.campaign.tick + 1
    markers[facility.id] = (
        FacilityMarker(
            facility.kind, facility.variant, facility.pos, facility.emitting, tick, None,
            facility.damage_state,
        )
        if world.rules is None
        else _marker(world.rules, facility, tick)
    )  # fmt: skip
    world.markers[loser] = dict(sorted(markers.items()))


def _sigint(world: World, rules: Rules, side: Side) -> tuple[Blob, ...]:
    """`side`'s Tier 1 blobs, by cell index (Q-FOW-7, FOW-11: a dark radar adds no range).
    shortcut: units x radar sites, no grid; radar sites are the few pre-placed facilities. Use the
    grid if a theater's radar sites reach the hundreds (SC-10 smoke test)."""
    radars = [
        (s.pos, (rules.sensor_radius(s.kind, s.damage_state) * rules.sigint_range_mult) ** 2)
        for s in world.entities()
        if s.side == side
        and s.kind == _RADAR
        and s.emitting is not False
        and not is_off_facility(rules, s)
    ]
    if not radars:
        return ()
    cell = rules.sigint_cell_m
    cols, rows = (max(1, math.ceil(b / cell)) for b in rules.bounds_m)
    counts: dict[int, int] = {}
    for e in world.entities():
        if (
            e.side == side
            or e.vel == _ZERO  # parked or silent: no blob
            or rules.domain[e.kind] == _STATIC  # facilities never form blobs
            or tracked_by(world, side, e.id)  # outside the side's sensors only
            or not any(_dist2(e.pos, p) <= r2 for p, r2 in radars)
        ):
            continue
        cx = min(max(math.floor(e.pos.x / cell), 0), cols - 1)
        cy = min(max(math.floor(e.pos.y / cell), 0), rows - 1)
        k = cy * cols + cx
        counts[k] = counts.get(k, 0) + 1
    tick = world.campaign.tick + 1  # the refresh tick being computed
    return tuple(
        Blob(
            f"{tick}-{k}", Vec2((k % cols + 0.5) * cell, (k // cols + 0.5) * cell), _size(rules, n)
        )
        for k, n in sorted(counts.items())
    )


def _size(rules: Rules, n: int) -> BlobSize:
    return "S" if n < rules.sigint_size_m_min else "M" if n < rules.sigint_size_l_min else "L"


def _merge(
    world: World, rules: Rules, old: dict[int, Contact], tracked: list[int], painted: set[int]
) -> dict[int, Contact]:
    now = {
        i: Contact(e.kind, e.pos, e.vel, None, i in painted)
        for i in tracked
        for e in [world.get(i)]
    }
    for i, c in old.items():
        if i not in now:
            if c.age is None and rules.domain[c.kind] == _STATIC:
                continue  # facilities never leave last-known tracks; markers do (FOW-13, part 2)
            if c.age is None:
                c.age, c.painted = 0, False  # coverage lost: a last-known track (FOW-6a)
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
    owners: Mapping[str, NodeOwner]  # every node's live owner (FOW-10, NX-125)
    markers: Mapping[int, FacilityMarker]  # discovered enemy facilities (FOW-13)
    blobs: tuple[Blob, ...]  # Tier 1 SIGINT blobs from the last refresh, by cell index
    defense_hp: Mapping[str, int]  # every defended node's hp: public node state (FOW-10, CB-10)


def side_view(world: World, side: Side) -> SideView:
    if world.rules is None:
        raise ValueError("side_view needs the world's rules")
    known = world.contacts[side]
    return SideView(
        side,
        {i: replace(c) for i, c in known.items() if c.age is None},
        {i: replace(c) for i, c in known.items() if c.age is not None},
        dict(world.rules.roads.pos),
        dict(world.owner),
        {i: replace(m) for i, m in world.markers[side].items()},
        world.blobs[side],  # immutable
        dict(world.defense_hp),
    )
