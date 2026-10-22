"""Node capture: live ownership, the capture bar, the flip and what it does (NX-125; GAMEPLAY §8,
STATE-MACHINES §4.2, Q-SIM-56, Q-SIM-57).

`World.owner` is each node's live owner and `World.capture` its bar: the side filling it and the
progress as an integer of millionths of a percent (`CAPTURE_FULL` = 100 %), so the flip threshold
and the decay are exact and a snapshot restores them bit for bit. Each tick's gain is
`round(CAPTURE_FULL x world_dt / time)`, at least 1, where
`time = max(min_time_s, time_s x quiet_mult(v) / n^exponent x garrison modifier)`, so `min_time_s`
is the only cap on how fast a crowd can flip a base (Q-GP-4).

Who counts (by position within `capture.radius_m` of the node): GROUND units are capturers, a
logistics unit (`Supply.carriers`) weighing `logi_weight`; air never counts (N-3) and facilities
never contest or garrison (Q-GP-38). A ground unit whose catalog has weapons and that is not
Disabled is combat-capable: on the side opposing a capturer it contests the bar: the bar then
drains. A defender that cannot contest (an unarmed or Disabled ground unit, or an aircraft LANDED
at the base) applies `garrison_mult` instead; an owner with no unit there applies
`empty_base_mult`; a NEUTRAL node uses neither.
The quiet-stream `quiet_mult` applies to the coalition only (Q-SIM-26) and `v` is the live
viewer units, as JOIN counts them (`World.viewer_units`).

A side `S` that is not the owner and has capturers is free when the other side has no combat-capable
unit there. A node with no bar starts one for the only free side (`CaptureStarted`); with two free
sides (a neutral node, both sides unarmed) the side with the larger capture weight starts it and an
exact tie starts nothing (Q-SIM-59). A bar fills while its side is free and
drains by `decay_per_s` x `world_dt` otherwise: abandoned, or contested by a combat-capable unit
(owner, 2026-10-21, Q-SIM-23); at 0 it is removed and the node keeps its owner. At `CAPTURE_FULL`
the node flips in this tick (N-1: one bar, one test per node per tick): `NodeCaptured`, the node's
facilities switch side keeping their damage (Q-GP-25, `fog.hand_over`), and the previous owner's
mobile units within the radius escape or are lost (Q-SM-10): a ground unit takes the road route to
the nearest friendly base, an aircraft LANDED there takes off RTB to the nearest base it owns if its
fuel reaches it; any other is removed with `UnitDestroyed` and, for a commander's unit, its respawn
delay and, once per unit, its crew roll (COMBAT CB-8: a wreck rolled when it became Disabled); a
Disabled wreck cannot escape.
Stock stays with the node. A SANCTUARY or BRIDGE node is never captured (N-4).

Defense HP (NX-124 part 3, `nexus.core.defense`, Q-GD-18): a bar cannot start on a node whose
defense HP is above 0. A bar already running is not stopped by a later repair: it fills or decays
by the rules above (the gate says "can't begin", GAMEPLAY §8), and the flip sets the HP to 0 for the
new owner. Idle floor (Q-GP-28, Q-GP-44): with no live viewer unit, the theater's `forward_airbase`
while the coalition owns it is skipped, so its bar neither starts, fills nor decays.

Night progress (Q-SIM-85, Q-SIM-86, NX-157): every Static flip stamps `DirectorState.last_flip`.
With no live viewer unit, the Static may flip a node only if none flipped in the last
`1 / campaign.night_progress_cap_nodes_per_h` game hours (`director.night_capped`); until then its
bar holds one step short of the flip (the node is in `DirectorState.held`), and the Director
launches no capture operation (`nexus.core.launch`). A held bar stays held until the cap frees,
even when a viewer arrives, so a new viewer does not see held bases fall at once; coalition units
contest it as any bar, and it leaves `held` when it is gone or drained. A garrison unit (one
with a home base) and a unit on a PATROL job never count as capturers (they still contest and
garrison): a garrison only defends (Q-SIM-86), so a patrol turns at a neutral node, or a failed
one stands there, without flipping it.

Runs after `logistics` in the `logistics_capture` slot (SC-13) and not while paused (SC-11).
Deterministic: nodes in id order, entities in id order, no RNG.
shortcut: a scan of every entity per capturable node; use the SC-10 grid if nodes x entities shows
in the tick budget.
"""

import math
from dataclasses import dataclass, field

from nexus.contracts.gen.common.enums import NodeKind, NodeOwner, Side
from nexus.contracts.gen.events.capture_started import CaptureStarted
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.core.defense import reset
from nexus.core.director import night_capped
from nexus.core.fog import hand_over
from nexus.core.logistics import friendly_bases, nearest
from nexus.core.provocation import captured
from nexus.core.rules import CAPTURE_FULL, CaptureRules, Rules
from nexus.core.world import SIDES, CaptureBar, Entity, World, end_stop, lose_unit

_UNCAPTURABLE: tuple[NodeKind, ...] = ("SANCTUARY", "BRIDGE")
_OTHER: dict[Side, Side] = {"COALITION": "ENEMY", "ENEMY": "COALITION"}
_AIR, _GROUND = "AIR", "GROUND"
_DISABLED = "DISABLED"


@dataclass(slots=True)
class _Presence:
    """One side's units near one node."""

    weight: float = 0.0  # capturers: 1 per ground unit, `logi_weight` per logistics unit
    armed: int = 0  # combat-capable ground units: they contest
    garrison: int = 0  # units that are there but cannot contest: unarmed ground, LANDED air
    commanders: set[str] = field(default_factory=set)  # of the capturers


type _Nodes = dict[str, dict[Side, _Presence]]


def capture(world: World, out: list[Event]) -> None:
    rules = world.rules
    if world.frozen or rules is None or rules.capture is None:
        return
    cap = rules.capture
    nodes = [n for n, kind in rules.node_kind.items() if kind not in _UNCAPTURABLE]
    _prune_held(world)
    near = _presence(world, rules, cap, nodes)
    viewers = world.viewer_units()
    quiet = _quiet(cap, viewers)
    idle_node = rules.defense.forward_airbase if viewers == 0 and rules.defense else None
    for node in nodes:  # id order
        if node == idle_node and world.owner[node] == "COALITION":
            continue  # the idle floor
        _tick_node(world, rules, cap, node, near[node], quiet, viewers == 0, out)


def _prune_held(world: World) -> None:
    """A node leaves `held` when its bar is gone, is not the Static's or has been drained."""
    held = world.director["ENEMY"].held
    for node in sorted(held):
        bar = world.capture.get(node)
        if bar is None or bar.side != "ENEMY" or bar.progress < CAPTURE_FULL - 1:
            del held[node]


def _patrolling(world: World, e: Entity) -> bool:
    """A garrison unit or a patrol: no capture weight."""
    if e.home is not None:
        return True
    job = world.boards[e.side].get(e.job_id) if e.job_id is not None else None
    return job is not None and job.kind == "PATROL"


def _presence(world: World, rules: Rules, cap: CaptureRules, nodes: list[str]) -> _Nodes:
    near: _Nodes = {n: {s: _Presence() for s in SIDES} for n in nodes}
    r2 = cap.radius_m**2
    for e in world.entities():
        domain = rules.domain[e.kind]
        if domain == _AIR and e.state != "LANDED":
            continue  # airborne: never counts (N-3); LANDED air only garrisons
        if domain not in (_AIR, _GROUND):
            continue  # facilities never contest or garrison (Q-GP-38)
        capturing = not _patrolling(world, e)
        for n in nodes:
            x, y = rules.roads.pos[n]
            if (e.pos.x - x) ** 2 + (e.pos.y - y) ** 2 <= r2:
                _tally(near[n][e.side], e, domain, rules, cap, capturing=capturing)
    return near


def _tally(
    p: _Presence, e: Entity, domain: str, rules: Rules, cap: CaptureRules, *, capturing: bool
) -> None:
    if domain == _AIR:
        p.garrison += 1
        return
    if capturing:
        p.weight += cap.logi_weight if e.kind in rules.supply.carriers else 1.0
        if e.commander_id is not None:
            p.commanders.add(e.commander_id)
    if e.kind in rules.armed and e.damage_state != _DISABLED:  # a wreck cannot contest (Q-ALN-33)
        p.armed += 1
    else:
        p.garrison += 1


def _quiet(cap: CaptureRules, viewers: int) -> float:
    """`quiet_mult(v)`: `quiet_floor` at 0 viewer units, linear to 1.0 at `quiet_ref`."""
    share = min(viewers, cap.quiet_ref) / cap.quiet_ref
    return cap.quiet_floor + (1.0 - cap.quiet_floor) * share


def _tick_node(
    world: World,
    rules: Rules,
    cap: CaptureRules,
    node: str,
    near: dict[Side, _Presence],
    quiet: float,
    humanless: bool,
    out: list[Event],
) -> None:
    owner = world.owner[node]
    capturers = [s for s in SIDES if s != owner and near[s].weight > 0]
    free = [s for s in capturers if not near[_OTHER[s]].armed]
    bar = world.capture.get(node)
    if bar is None:
        if world.defense_hp.get(node):
            return  # the defenses are up: no bar (Q-GD-18)
        starter = _starter(near, free)
        if starter is None:
            return
        bar = world.capture[node] = CaptureBar(starter, 0)
        out.append(_started(world, node, bar.side))
    elif bar.side not in free:  # abandoned, or contested: it drains alike (Q-SIM-23)
        _decay(world, cap, node, bar)
        return
    base = _base_time(cap, near[bar.side].weight, quiet if bar.side == "COALITION" else 1.0)
    time = max(cap.min_time_s, base * _modifier(cap, owner, near))
    bar.progress += max(cap.min_progress, round(CAPTURE_FULL * rules.world_dt / time))
    if bar.progress >= CAPTURE_FULL:
        if _night_hold(world, rules, node, bar, humanless):
            bar.progress = CAPTURE_FULL - 1  # the night cap holds the flip back
            return
        _flip(world, rules, cap, node, bar.side, near, out)


def _night_hold(world: World, rules: Rules, node: str, bar: CaptureBar, humanless: bool) -> bool:
    """Whether the night cap holds back this Static flip (a held node stays held, Q-SIM-86); a flip
    that goes ahead stamps the cap clock, with or without viewers."""
    dr, static = rules.director, world.director["ENEMY"]
    if dr is None or bar.side != "ENEMY":
        return False
    now = world.campaign.running_ticks + 1
    if night_capped(static, dr, now) and (humanless or node in static.held):
        static.held.setdefault(node, now)
        return True
    static.last_flip = now
    static.held.pop(node, None)
    return False


def _starter(near: dict[Side, _Presence], free: list[Side]) -> Side | None:
    """The side that starts a bar: the only free side, else the heavier one (Q-SIM-59). The weights
    are the float sums the rate uses, built in entity id order, so the comparison is deterministic;
    for the shipped weights (1 and 0.5) they are exact, so a tie is a real tie."""
    if len(free) == 1:
        return free[0]
    if len(free) == 2 and near[free[0]].weight != near[free[1]].weight:
        return max(free, key=lambda s: near[s].weight)
    return None


def _base_time(cap: CaptureRules, n: float, quiet: float) -> float:
    return cap.time_s * quiet / float(n**cap.exponent)


def _modifier(cap: CaptureRules, owner: NodeOwner, near: dict[Side, _Presence]) -> float:
    """The garrison (x `garrison_mult`) or empty-base modifier; none at a NEUTRAL node. A
    combat-capable defender never gets here: the bar drains."""
    if owner == "NEUTRAL":
        return 1.0
    return cap.garrison_mult if near[owner].garrison else cap.empty_base_mult


def _decay(world: World, cap: CaptureRules, node: str, bar: CaptureBar) -> None:
    bar.progress -= cap.decay_micro
    if bar.progress <= 0:
        del world.capture[node]


def _started(world: World, node: str, side: Side) -> CaptureStarted:
    return CaptureStarted.model_construct(
        kind="CaptureStarted",
        tick=world.campaign.tick + 1,
        event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id,
        node_id=node,
        side=side,
    )


def _flip(
    world: World,
    rules: Rules,
    cap: CaptureRules,
    node: str,
    to: Side,
    near: dict[Side, _Presence],
    out: list[Event],
) -> None:
    before = world.owner[node]
    world.owner[node] = to
    if before != "NEUTRAL":  # a node lost to the other side opens the counterattack window
        world.lost[node] = world.campaign.running_ticks + 1
    del world.capture[node]
    reset(world, node)
    out.append(
        NodeCaptured.model_construct(
            kind="NodeCaptured",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            node_id=node,
            from_=before,
            to=to,
            participant_commander_ids=sorted(near[to].commanders),
        )
    )
    captured(world, node, before, to, len(near[to].commanders))  # the Static's provocation
    _switch_facilities(world, node, to)
    if before != "NEUTRAL":
        _resolve_units(world, rules, cap, node, before, out)


def _switch_facilities(world: World, node: str, to: Side) -> None:
    """The base's facilities change side and keep everything else (Q-GP-25), FOW-13."""
    for e in world.entities():
        if e.base_id == node and e.side != to:
            loser, e.side = e.side, to
            hand_over(world, e, loser)


def _resolve_units(
    world: World, rules: Rules, cap: CaptureRules, node: str, loser: Side, out: list[Event]
) -> None:
    """The loser's mobile units near the node escape or are lost, in id order (Q-SM-10)."""
    x, y = rules.roads.pos[node]
    lost: list[Entity] = []
    for e in world.entities():
        domain = rules.domain[e.kind]
        parked_air = domain == _AIR and e.state == "LANDED"
        mobile = domain == _GROUND or parked_air
        if e.side != loser or e.base_id is not None or not mobile:
            continue
        if (e.pos.x - x) ** 2 + (e.pos.y - y) ** 2 > cap.radius_m**2:
            continue
        escaped = e.damage_state != _DISABLED and (  # a wreck cannot move
            _escape_air(world, rules, e)
            if parked_air
            else _escape_ground(world, rules, e, node, out)
        )
        if not escaped:
            lost.append(e)
    for e in lost:
        lose_unit(world, e, out)


def _escape_ground(world: World, rules: Rules, e: Entity, node: str, out: list[Event]) -> bool:
    """Re-path to the nearest friendly base by road, from the node the unit is heading for (or
    standing at); False when there is none. A truck keeps its cargo and ends its unloading stop."""
    start = e.path[0] if e.path else e.last_node
    best = None
    if isinstance(start, str):
        best = nearest(rules, start, friendly_bases(world, rules, e.side))
    if best is None:
        return False
    if e.delivered:
        end_stop(world, e, node, out)
    e.path = list(best[1])
    return True


def _escape_air(world: World, rules: Rules, e: Entity) -> bool:
    """Take off RTB to the nearest base the side owns when the fuel reaches it, ties by node id."""
    if e.fuel is None:
        raise ValueError(f"aircraft {e.id} has no fuel")
    reach = min(
        ((math.hypot(x - e.pos.x, y - e.pos.y), n)
         for n in world.landing_bases(e.side) for x, y in [rules.roads.pos[n]]),
        default=None,
    )  # fmt: skip
    if reach is None or e.fuel < reach[0] / rules.speed(e.kind, e.damage_state):
        return False
    e.state, e.path, e.orbit = "RTB", [reach[1]], None
    return True
