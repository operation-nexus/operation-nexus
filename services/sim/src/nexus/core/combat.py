"""Combat: targeting, shots, hit rolls, damage, damage states, destruction and wrecks (NX-124
part 1; COMBAT CB-1..CB-7, CB-9, SIM-CORE SC-5, SC-11, SC-13).

The `combat` slot, each running tick (not while frozen, SC-11), in this order:

1. Timers count down one running tick: every weapon's `reload`, every wreck's `wreck_left`.
2. **New shots (CB-1, CB-2).** Entities in id order; a Disabled entity does not fire. For each
   weapon with a round left and no reload, in the unit's loadout (catalog) order, the target is the
   highest priority valid one: a contact its side tracks now (never a last-known track or a blob,
   Q-FOW-4; never a Disabled facility) whose domain the weapon targets, for an AIR target in one
   of the weapon's `bands`, within `range_m` (real positions); priority `threat` descending, then
   distance, then id. Firing spends a round, starts the reload and stores a `Shot` landing
   `ceil(distance / (speed x world_dt))` ticks later, a gun on the fire tick.
   **Structures (CB-10, Q-SIM-71):** a weapon whose `targets` include STRUCTURE with no valid unit
   target in range (units always come first) fires at the defense HP of the nearest node, ties by
   id, that the enemy owns and whose HP is above 0, within `range_m` of the node's position (nodes
   are always known, FOW-10, so no track is needed).
3. **Impacts (CB-3, CB-4).** Shots due, in `(impact_tick, id)` order. A shot fizzles, with no RNG
   draw, when the shooter or target is gone, the shooter's side no longer tracks the target, or the
   target left the weapon's range or bands, or became a Disabled facility (Q-FOW-16). Otherwise
   `Pk = min(pk_cap, base_pk x track x range x evasion x masking)` and one draw on the `combat`
   stream decides the hit. A shot at a node's defenses fizzles when its shooter is gone, the node
   changed hands or is already at 0 hp, or it is out of range; else its Pk has track `track`,
   evasion
   1.0 and no masking (Q-CBT-22).
4. **Damage (CB-5, CB-6, CB-9).** A hit removes `floor(damage x (1 - armor))` hp, at least 1, with
   `armor` an exact decimal (0 for a structure: `damage` hp off the node's defenses, floored at the
   idle floor, `nexus.core.defense`). The damage state follows hp against the kind's thresholds
   (`UnitRules.cuts`). A facility (STATIC) floors at the Disabled threshold, never Destroyed; any
   other unit at 0 hp is removed with `UnitDestroyed{killer_id = the shooter, assist_ids}`, and so
   is an aircraft that is not LANDED the moment it becomes Disabled (Q-SIM-66; that hit emits
   `UnitDestroyed` alone, no state change). Any other unit that becomes Disabled is a wreck: it
   stops, stays targetable and is removed after `combat.disabled_timeout_s` with
   `UnitDespawned{WRECKED}` (CB-7). Its commander's respawn delay starts at that removal (COMBAT
   §5.5), or at once on a destruction. Every hit on a non-facility is kept in `Entity.hits` for
   `combat.assist_window_s`; the shooters still inside the window, minus the killer, are the
   `assist_ids` (CB-5a). A shot already in flight still lands after its shooter becomes Disabled.
5. Wrecks whose countdown reached 0 are removed, in id order.

Pending shots and every timer are on the campaign clock (running ticks), so a pause freezes them.
Deterministic: integer state, exact armor decimals, entities and shots in id or `(impact_tick, id)`
order, no RNG except the one `combat` draw per non-fizzled impact.
Targeting uses one `UniformGrid` per side and threat level (SC-10), searched in growing radii.
"""

import math
from bisect import insort

from nexus.contracts.gen.common.enums import AltBand, Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.munitions_depleted import MunitionsDepleted
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.contracts.gen.events.weapon_impact import WeaponImpact
from nexus.core.defense import damage as damage_defense
from nexus.core.defense import floor as defense_floor
from nexus.core.fog import LOW_BANDS, in_masking_region, is_off_facility
from nexus.core.logistics import go_home
from nexus.core.rearm import stop_problem
from nexus.core.rng import RngStream
from nexus.core.rules import CombatRules, Rules, WeaponRules
from nexus.core.spatial import UniformGrid
from nexus.core.world import (
    _ZERO,
    Entity,
    Shot,
    World,
    drop_claim,
    end_rearm,
    lose_unit,
    roll_crew,
    set_damage_state,
)

_DISABLED = "DISABLED"
_AIR, _GROUND, _STATIC = "AIR", "GROUND", "STATIC"
# Targeting grids: the cell size and the query padding change speed only, never a result.
_CELL_M = 4000.0
_SLACK_M = 1.0
_MAX_ASSISTS = 32  # UnitDestroyed.assist_ids maxItems
_STRUCTURE = "STRUCTURE"


def resolve(world: World, out: list[Event]) -> None:
    rules = world.rules
    if world.frozen or rules is None or rules.combat is None:
        return
    cr, now = rules.combat, world.campaign.running_ticks + 1  # the running tick being computed
    for e in world.entities():
        if any(e.reload):
            e.reload = [max(0, r - 1) for r in e.reload]
        if e.wreck_left is not None:
            e.wreck_left -= 1
    for marker_id in [i for i, m in world.crew_markers.items() if m.expires <= now]:
        del world.crew_markers[marker_id]
    _fire(world, rules, cr, now, out)
    _land(world, rules, cr, now, out)
    _remove_wrecks(world, out)


def _d2(a: Entity, b: Entity) -> float:
    return (a.pos.x - b.pos.x) ** 2 + (a.pos.y - b.pos.y) ** 2


def _fire(world: World, rules: Rules, cr: CombatRules, now: int, out: list[Event]) -> None:
    levels: dict[Side, list[_Level]] = {}  # built on a side's first ready shooter
    # nodes held at their idle floor (nothing to take); no hp changes while shots are fired
    pinned = frozenset(
        n for n, hp in world.defense_hp.items() if hp <= defense_floor(world, rules, n)
    )
    for e in world.entities():
        if e.damage_state == _DISABLED or not e.ammo:
            continue
        ready = [
            i for i, (a, r) in enumerate(zip(e.ammo, e.reload, strict=True)) if a > 0 and not r
        ]
        if not ready:
            continue
        if e.side not in levels:
            levels[e.side] = _target_levels(world, rules, cr, e.side)
        loadout = cr.loadout(e.kind, e.variant)
        for i in ready:
            w = loadout[i]
            pick: tuple[Entity | str, float] | None = _pick(rules, w, e, levels[e.side])
            if pick is None and _STRUCTURE in w.targets:
                pick = _pick_node(world, rules, w, e, pinned)
            if pick is not None:
                _shoot(world, rules, e, i, w, pick, now, out)


type _Level = list[tuple[str, AltBand | None, UniformGrid]]  # one threat level, by class


def _target_levels(world: World, rules: Rules, cr: CombatRules, side: Side) -> list[_Level]:
    """The valid targets of `side`'s shooters (CB-1: enemies it tracks now, not a Disabled
    facility), highest threat level first; within a level one grid per (domain, altitude band),
    the two things a weapon filters on besides range. Nothing moves or dies while shots are fired,
    so they stay valid for the whole pass."""
    groups: dict[tuple[int, str, AltBand | None], list[Entity]] = {}
    for i, c in world.contacts[side].items():
        t = world.find(i)
        if c.age is None and t is not None and t.side != side and not is_off_facility(rules, t):
            key = (cr.units[t.kind].threat, rules.domain[t.kind], t.alt_band)
            groups.setdefault(key, []).append(t)
    levels: dict[int, _Level] = {}
    for (threat, domain, band), members in groups.items():
        grid = UniformGrid(_CELL_M)
        grid.rebuild(members)
        levels.setdefault(threat, []).append((domain, band, grid))
    return [levels[threat] for threat in sorted(levels, reverse=True)]


def _pick(
    rules: Rules, w: WeaponRules, shooter: Entity, levels: list[_Level]
) -> tuple[Entity, float] | None:
    """The best valid target for `w` (CB-1): the highest threat level with any valid target in
    range, and there the nearest by squared distance, ties by id. Each level is searched in
    growing radii, so a crowd far away is never looked at when a target is near. The grids only
    narrow the search: every candidate is checked with the exact `_d2` and range tests."""
    range2 = w.range_m**2
    for level in levels:
        grids = [
            g
            for domain, band, g in level
            if domain in w.targets and (domain != _AIR or band in w.bands)
        ]
        radius = _CELL_M
        while grids:
            last = radius >= w.range_m
            limit2 = range2 if last else radius * radius
            best: tuple[float, int, Entity] | None = None
            for grid in grids:
                for t in grid.within(shooter.pos, min(radius, w.range_m) + _SLACK_M):
                    d2 = _d2(shooter, t)
                    if d2 <= limit2 and (best is None or (d2, t.id) < best[:2]):
                        best = (d2, t.id, t)
            if best is not None:
                return best[2], best[0]
            if last:
                break
            radius *= 2
    return None


def _pick_node(
    world: World, rules: Rules, w: WeaponRules, shooter: Entity, pinned: frozenset[str]
) -> tuple[str, float] | None:
    """The nearest enemy-owned node with defense HP in range, ties by node id (CB-10). Never the
    Static's rear source (it cannot be captured and the Static has no defeat) nor a node held at
    its idle floor (the coalition sanctuary at 1 hp while nobody plays)."""
    best: tuple[float, str] | None = None
    rear = rules.supply.rear["ENEMY"]  # the Static's rear source: no win effect (Q-SIM-64)
    for node, hp in world.defense_hp.items():  # id order
        if (
            hp
            and node not in pinned
            and node != rear
            and world.owner[node] not in (shooter.side, "NEUTRAL")
        ):
            x, y = rules.roads.pos[node]
            d2 = (shooter.pos.x - x) ** 2 + (shooter.pos.y - y) ** 2
            if d2 <= w.range_m**2 and (best is None or d2 < best[0]):
                best = (d2, node)
    return None if best is None else (best[1], best[0])


def _shoot(
    world: World,
    rules: Rules,
    shooter: Entity,
    i: int,
    w: WeaponRules,
    pick: tuple[Entity | str, float],
    now: int,
    out: list[Event],
) -> None:
    target, d2 = pick
    node = target if isinstance(target, str) else None
    target_id = None if isinstance(target, str) else target.id
    shooter.ammo[i] -= 1
    shooter.reload[i] = w.reload_ticks
    delay = 0 if w.speed_mps is None else math.ceil(math.sqrt(d2) / (w.speed_mps * rules.world_dt))
    shot = Shot(world.next_shot_id(), shooter.id, target_id, w.id, now + delay, node)
    insort(world.shots, shot, key=lambda s: (s.impact_tick, s.id))
    out.append(
        WeaponFired.model_construct(
            kind="WeaponFired",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            shooter_id=shooter.id,
            target_id=target_id,
            target_node_id=node,
            weapon=w.id,
            impact_tick=shot.impact_tick,
        )
    )
    if w.speed_mps is not None:
        _depleted(world, rules, shooter, out)


def _depleted(world: World, rules: Rules, e: Entity, out: list[Event]) -> None:
    """After a non-gun round: `MunitionsDepleted` when no non-gun round is left (CB-11)."""
    if rules.combat is None:
        return
    left = [
        (a, w.speed_mps is None)
        for a, w in zip(e.ammo, rules.combat.loadout(e.kind, e.variant), strict=True)
    ]
    if any(a and not gun for a, gun in left):
        return
    out.append(
        MunitionsDepleted.model_construct(
            kind="MunitionsDepleted",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            entity_id=e.id,
            guns_only=any(a for a, _ in left),
        )
    )
    go_home(world, rules, e)  # auto-RTB, once, as the last missile or bomb is spent (§5.6)


def _land(world: World, rules: Rules, cr: CombatRules, now: int, out: list[Event]) -> None:
    due = sum(s.impact_tick <= now for s in world.shots)  # the list is in impact order
    landing, world.shots = world.shots[:due], world.shots[due:]
    for shot in landing:
        shooter = world.find(shot.shooter)
        target = None if shot.target is None else world.find(shot.target)
        w = cr.weapons[shot.weapon_id]
        if shot.node is not None:
            pk = None if shooter is None else _pk_node(world, rules, cr, shooter, shot.node, w)
        else:
            pk = (
                None
                if shooter is None or target is None
                else _pk(world, rules, cr, shooter, target, w)
            )
        hit = pk is not None and world.rng.stream(RngStream.COMBAT).random() < pk
        out.append(
            WeaponImpact.model_construct(
                kind="WeaponImpact",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                shooter_id=shot.shooter,
                target_id=shot.target,
                target_node_id=shot.node,
                weapon=shot.weapon_id,
                hit=hit,
            )
        )
        if hit and shot.node is not None:
            damage_defense(world, rules, shot.node, w.damage, out)  # armor 0 (Q-CBT-22)
        elif hit and shooter is not None and target is not None:
            _hit(world, rules, cr, shooter, target, w, out)


def _pk_node(
    world: World, rules: Rules, cr: CombatRules, shooter: Entity, node: str, w: WeaponRules
) -> float | None:
    """The hit probability on a node's defenses, or None for a fizzle (CB-3, CB-10): a structure
    is always known (FOW-10), has evasion 1.0 and is never masked (Q-CBT-22)."""
    x, y = rules.roads.pos[node]
    d2 = (shooter.pos.x - x) ** 2 + (shooter.pos.y - y) ** 2
    if (
        world.defense_hp[node] <= defense_floor(world, rules, node)
        or world.owner[node] in (shooter.side, "NEUTRAL")
        or d2 > w.range_m**2
    ):
        return None
    return min(cr.pk_cap, w.base_pk * cr.track_mult * _range_factor(cr, math.sqrt(d2), w.range_m))


def _pk(
    world: World, rules: Rules, cr: CombatRules, shooter: Entity, target: Entity, w: WeaponRules
) -> float | None:
    """The hit probability (CB-4), or None for a fizzle (CB-3): no draw is made for it."""
    track = world.contacts[shooter.side].get(target.id)
    domain = rules.domain[target.kind]
    d2 = _d2(shooter, target)
    if (
        track is None
        or track.age is not None
        or is_off_facility(rules, target)
        or d2 > w.range_m**2
        or domain not in w.targets
        or (domain == _AIR and target.alt_band not in w.bands)
    ):
        return None
    masked = (domain == _AIR and target.alt_band in LOW_BANDS) or (
        domain == _GROUND and in_masking_region(rules, target.pos)
    )
    return min(
        cr.pk_cap,
        w.base_pk
        * (cr.painted_mult if track.painted else cr.track_mult)
        * _range_factor(cr, math.sqrt(d2), w.range_m)
        * cr.units[target.kind].evasion
        * (cr.masked_mult if masked else 1.0),
    )


def _range_factor(cr: CombatRules, dist: float, range_m: float) -> float:
    """1.0 up to `full_pk_frac` of the range, then linear down to `min_mult` at the range."""
    full = cr.full_pk_frac * range_m
    if dist <= full:
        return 1.0
    return 1.0 - (1.0 - cr.min_mult) * (dist - full) / (range_m - full)


def _hit(
    world: World,
    rules: Rules,
    cr: CombatRules,
    shooter: Entity,
    target: Entity,
    w: WeaponRules,
    out: list[Event],
) -> None:
    stats = cr.units[target.kind]
    facility = rules.domain[target.kind] == _STATIC
    hp = target.hp - max(1, math.floor(w.damage * (1 - stats.armor)))
    if facility:
        hp = max(hp, stats.floor)  # never Destroyed (CB-9)
    else:
        now = world.campaign.running_ticks + 1
        recent = [h for h in target.hits if now - h[1] <= cr.assist_window_ticks]
        if hp <= 0:
            _destroy(world, target, shooter, recent, out)
            return
        target.hits = [*recent, [shooter.id, now]]
    target.hp = hp
    state = stats.state(hp)
    if state == target.damage_state:
        return
    if state == _DISABLED and not facility and target.state not in (None, "LANDED"):
        _destroy(world, target, shooter, target.hits, out)  # airborne: it cannot stay up
        return
    set_damage_state(world, target, state, out)
    if state == "MISSION_KILL":
        go_home(world, rules, target)  # auto-RTB, once, as it reaches Mission-kill (COMBAT §5.6)
    if state == _DISABLED and not facility:
        target.wreck_left, target.path, target.vel = cr.disabled_timeout_ticks, [], _ZERO
        roll_crew(world, target, out)  # the first of Disabled or Destroyed (CB-8)


def _destroy(
    world: World, target: Entity, killer: Entity, hits: list[list[int]], out: list[Event]
) -> None:
    """Remove a destroyed unit: the killer is the shooter of the last hit, the assists every other
    distinct shooter in `hits` (still inside the assist window), sorted, at most 32 (CB-5a)."""
    assists = sorted({h[0] for h in hits} - {killer.id})[:_MAX_ASSISTS]
    lose_unit(world, target, out, killer_id=killer.id, assist_ids=assists)


def _remove_wrecks(world: World, out: list[Event]) -> None:
    for e in [e for e in world.entities() if e.wreck_left == 0]:
        end_rearm(world, e, out)
        drop_claim(world, e, out)
        world.remove(e.id)
        if e.commander_id is not None:
            world.record_loss(e.commander_id)
        out.append(
            UnitDespawned.model_construct(
                kind="UnitDespawned",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                entity_id=e.id,
                reason="WRECKED",
            )
        )


def validate(world: World, rules: Rules) -> None:
    """Check a restored world's combat state against the campaign rules (a snapshot carries none);
    raises ValueError naming the entity or shot. Without combat rules there is nothing to check."""
    cr = rules.combat
    if cr is None:
        return
    for e in world.entities():
        _validate_entity(world, rules, cr, e)
    now = world.campaign.running_ticks
    for s in world.shots:
        shooter = world.find(s.shooter)
        target = None if s.target is None else world.find(s.target)
        if s.node is not None and s.node not in world.defense_hp:
            raise ValueError(f"shot {s.id}: node {s.node} has no defenses")
        if s.weapon_id not in cr.weapons or s.impact_tick <= now:
            raise ValueError(f"shot {s.id}: unknown weapon {s.weapon_id!r} or already due")
        if shooter is not None and cr.weapons[s.weapon_id] not in cr.loadout(
            shooter.kind, shooter.variant
        ):
            raise ValueError(f"shot {s.id}: shooter {s.shooter} does not carry {s.weapon_id}")
        if shooter is not None and target is not None and shooter.side == target.side:
            raise ValueError(f"shot {s.id}: shooter and target are on one side")


def _validate_entity(world: World, rules: Rules, cr: CombatRules, e: Entity) -> None:
    stats = cr.units.get(e.kind)
    if stats is None:
        raise ValueError(f"entity {e.id}: kind {e.kind} is not in the catalog")
    loadout = cr.loadout(e.kind, e.variant)
    facility = rules.domain[e.kind] == _STATIC
    problem = (
        "hp above the kind's maximum" if e.hp > stats.hp
        else "damage_state does not match hp" if e.damage_state != stats.state(e.hp)
        else "altitude band does not match the kind" if e.alt_band != stats.alt_band
        else "ammo or reload does not match the loadout"
        if len(e.ammo) != len(loadout) or len(e.reload) != len(loadout)
        or any(a > w.ammo for a, w in zip(e.ammo, loadout, strict=True))
        or any(r > w.reload_ticks for r, w in zip(e.reload, loadout, strict=True))
        else "a Disabled unit needs a wreck timer within combat.disabled_timeout_s, a facility or "
        "any other unit none"
        if (e.wreck_left is None) != (facility or e.damage_state != _DISABLED)
        or (e.wreck_left or 0) > cr.disabled_timeout_ticks
        else "repair_debt not below the repair price denominator"
        if e.repair_debt >= (rules.supply.facility_hp_per_stock if facility else stats.hp)
        else "an airborne aircraft cannot be Disabled"
        if e.damage_state == _DISABLED and e.state not in (None, "LANDED")
        else "hits on a facility, or from the future"
        if e.hits and (facility or e.hits[-1][1] > world.campaign.running_ticks)
        else "last_node or a path waypoint is not a theater node"
        if (e.last_node is not None and e.last_node not in rules.node_kind)
        or any(isinstance(p, str) and p not in rules.node_kind for p in e.path)
        else stop_problem(world, rules, cr, e)
    )  # fmt: skip
    if problem:
        raise ValueError(f"entity {e.id} ({e.kind}): {problem}")
