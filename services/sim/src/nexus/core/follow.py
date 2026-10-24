"""Follow, escort and formation speed (GAMEPLAY §1b Q-GP-31..33, §5 Q-SIM-38; STATE-MACHINES U-10;
NX-374 part 2, NX-369; Q-SIM-76).

`steer` runs each running tick in the `director` slot, after the Tasking Board and before
`movement` (never while frozen, SC-11). A follower is an entity with `follow_id`, its direct
leader; the follow links form forests, a unit may be followed by many and may itself follow.

1. **Leaders.** A Disabled leader leaves its followers: those with the FOLLOW order take its own
   leader, else drop the order and fall back to the board; an escort-job follower just drops.
   (A leader that dies or despawns is handled in `World.remove`.) A Disabled follower follows
   no one.
2. **Threats.** An armed follower belongs to a group: the whole tree it is in. A *group threat* is
   a tracked enemy that fired at any group member within `tasking.escort_threat_memory_s` world
   seconds (`Entity.fired_by`) or whose kind's catalog weapons reach one now (its live ammo is
   hidden state, so never read). `World.group_threat` gives
   `combat` each such follower's threat ids, which it shoots before anything else (units first,
   CB-1 order among them). The follower breaks station toward the nearest threat that is within
   `tasking.escort_leash_m` of the convoy and it can hit, until in weapon range, along the road
   that passes nearest it (one leg at a time, so only nodes with a road are chosen; none leads
   closer: it keeps station). The leash is measured from the members that cannot be engaging (the
   leader and unarmed followers), so escorts cannot leapfrog one another; an escort already
   beyond it returns to station.
3. **Station**, by the domains of follower and leader (Q-GP-32, `tasking.follow_station_m`):
   - GROUND after GROUND: the road distance to the leader's destination (its last path node, else
     the node it stands at) is steered, on the shortest road route to it. A combat unit after a
     carrier keeps `escort` m ahead of it; any other follower, `column` m behind. The speed is
     the leader's plus the gap error closed in one tick, between 0 and its top speed, so it
     catches up at top speed, then matches the leader and never overshoots. A leader that stopped
     at a base (any node but a BRIDGE) draws its followers all the way in (they park, a truck
     unloads); stopped elsewhere (also at a bridge's repair stop, NX-373 part 2, where followers
     drive out along the road to the stop), followers within twice the station hold where they are.
   - AIR after GROUND: an aircraft farther than `overwatch` m flies to the leader and orbits there
     (the orbit mechanics of `movement`). A leader parked at a landing base: it lands there.
   - AIR after AIR: a wingman `wingman` m off the leader's right, moving with it, while the
     leader flies at least the follower's `min_speed_mps`; slower, it orbits within that distance.
     A leader landed: it lands too, and takes off again once the leader does.
   A follower sent home (RTB) is not steered until it lands. A ground follower after an aircraft,
   or anyone after a STATIC unit, never happens (`can_follow`).
4. **Formation speed (NX-369).** Ground followers within `tasking.escort_leash_m` of their ground
   leader and not engaging form a group with it per connected tree; the group's speed is its
   slowest member's `Rules.speed` (damage included, before the road's `speed_mult`), and
   `World.speed_cap` holds each member to it, so a convoy never outruns its slowest escort. A
   follower still catching up to its station runs at its own top speed instead (that is how a
   faster escort gets ahead), but is held to the slowest of its own followers. A straggler beyond
   the leash or an engaging escort is outside the group and neither slows it nor is slowed by it.
   Aircraft are never capped (they orbit).

Deterministic: followers and members in id order, integer/float arithmetic on world state only.
"""

import math
from collections.abc import Sequence

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.core.bridges import blocked, crosses
from nexus.core.logistics import approach
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules, TaskingRules
from nexus.core.spatial import UniformGrid
from nexus.core.world import Entity, Vec2, World, at_stop, on_node

_GROUND, _AIR, _STATIC = "GROUND", "AIR", "STATIC"
_LONG_M = 15_000.0  # a kind reaching farther than this is kept out of the track grid
_CELL_M = 8_000.0  # track grid cell


def pair_ok(rules: Rules, kind: UnitKind, leader_kind: UnitKind) -> bool:
    """A station can be kept: ground after ground, air after air or ground, never a STATIC unit
    on either side."""
    dom, lead_dom = rules.domain[kind], rules.domain[leader_kind]
    return (
        lead_dom in (_GROUND, _AIR)
        and dom in (_GROUND, _AIR)
        and (dom == _AIR or lead_dom == _GROUND)
    )


def can_follow(
    world: World, rules: Rules, kind: UnitKind, leader_id: int, follower: Entity | None
) -> bool:
    """Whether a unit of `kind` (an existing `follower`, or None for a unit about to spawn) may
    follow `leader_id`: a live, not Disabled unit of the same side it can keep station on (ground
    after ground; air after air or ground), not itself and not one that follows it (loop)."""
    leader = world.find(leader_id)
    side = "COALITION" if follower is None else follower.side
    if leader is None or leader.side != side or leader.damage_state == "DISABLED":
        return False
    if not pair_ok(rules, kind, leader.kind):
        return False
    at: Entity | None = leader
    while follower is not None and at is not None:
        if at.id == follower.id:
            return False
        at = None if at.follow_id is None else world.find(at.follow_id)
    return True


def _dist(a: Entity, b: Entity) -> float:
    return math.hypot(a.pos.x - b.pos.x, a.pos.y - b.pos.y)


def _length(start: Vec2, path: Sequence[str | Vec2], rules: Rules) -> float:
    """The length of the polyline from `start` through `path`."""
    total, x, y = 0.0, start.x, start.y
    for p in path:
        nx, ny = rules.roads.stops.get(p, rules.roads.pos[p]) if isinstance(p, str) else (p.x, p.y)
        total += math.hypot(nx - x, ny - y)
        x, y = nx, ny
    return total


def steer(world: World) -> None:
    """The follow pass (module docstring)."""
    world.speed_cap.clear()
    world.group_threat.clear()
    rules = world.rules
    if world.frozen or rules is None or rules.tasking is None:
        return
    followers = [e for e in world.entities() if e.follow_id is not None]
    if not followers:
        return
    _reattach(world, followers)
    for f in followers:  # a follow state no command can make (corrupt, hand-built): dropped
        leader = None if f.follow_id is None else world.find(f.follow_id)
        if f.follow_id is not None and (
            leader is None or leader.side != f.side or not pair_ok(rules, f.kind, leader.kind)
        ):
            f.follow_id = None
            f.order = None if f.order == "FOLLOW" else f.order
    followers = [f for f in followers if f.follow_id is not None]
    roots, groups = _groups(world, followers)
    ctx = _Ctx(world, rules)
    threats: dict[int, list[Entity]] = {}
    capped: dict[int, float] = {}  # base speed caps of the stationed followers
    formation: list[Entity] = []  # ground followers in the group of their leader
    catching: set[int] = set()  # ... of which are still catching up to their station
    for f in followers:
        leader = world.get(f.follow_id or 0)
        if f.state == "RTB" or f.damage_state == "DISABLED":
            continue
        members = groups[roots[f.id]]
        group = _group_threats(ctx, f, members, threats)
        if group:
            world.group_threat[f.id] = tuple(sorted(t.id for t in group))
        if group and _engage(world, rules, f, members, group, capped):
            continue
        if rules.domain[f.kind] == _AIR:
            _station_air(world, rules, rules.tasking, f, leader)
        elif _station_ground(world, rules, rules.tasking, f, leader, capped, catching):
            formation.append(f)
    _formation(world, rules, formation, capped, catching)


def _reattach(world: World, followers: list[Entity]) -> None:
    """Step 1: leaders that are Disabled hand their followers on (or drop them)."""
    for f in followers:
        if f.damage_state == "DISABLED":
            continue
        lid = f.follow_id
        while lid is not None and world.get(lid).damage_state == "DISABLED":
            lid = world.get(lid).follow_id if f.order == "FOLLOW" else None
        if lid != f.follow_id:
            f.follow_id = lid
            if lid is None and f.order == "FOLLOW":
                f.order = None
    for f in followers:
        if f.damage_state == "DISABLED":  # after the others read its leader
            f.follow_id = None
            if f.order == "FOLLOW":
                f.order = None


def _groups(
    world: World, followers: list[Entity]
) -> tuple[dict[int, int], dict[int, list[Entity]]]:
    """Follower id -> the id of the root of its tree (the unit at the top of its chain), and each
    root -> the members of its tree (root and followers) in id order."""
    roots: dict[int, int] = {}
    ids: dict[int, set[int]] = {}
    for f in followers:
        at = f
        while at.follow_id is not None:
            at = world.get(at.follow_id)
        roots[f.id] = at.id
        ids.setdefault(at.id, {at.id}).add(f.id)
    return roots, {r: [world.get(i) for i in sorted(m)] for r, m in ids.items()}


# --- threats and engagement ---------------------------------------------------------------------


class _Ctx:
    """Per-tick lookups for threat finding: each side's tracked enemies on a grid (the ones with
    a reach over `_LONG_M`, in practice facilities, in a list instead, so one SAM site does not
    widen every query: a partition for speed, never for the result), and the reach of a kind."""

    __slots__ = ("far", "grid", "known", "reach", "rules", "short", "world")

    def __init__(self, world: World, rules: Rules) -> None:
        self.world, self.rules = world, rules
        self.reach: dict[tuple[UnitKind, str | None], dict[tuple[str, str | None], float]] = {}
        self.known: dict[Side, dict[int, Entity]] = {}
        self.grid: dict[Side, UniformGrid] = {}
        self.far: dict[Side, list[Entity]] = {}
        self.short: dict[Side, float] = {}

    def reach_of(self, e: Entity) -> dict[tuple[str, str | None], float]:
        """The longest range of `e`'s kind (its catalog loadout, never its live ammo: hidden
        state, FOW) against each (domain, altitude band) target."""
        key = (e.kind, e.variant)
        if key not in self.reach:
            table: dict[tuple[str, str | None], float] = {}
            cr = self.rules.combat
            for w in () if cr is None else cr.loadout(e.kind, e.variant):
                for domain in w.targets:
                    for band in (w.bands or [None]) if domain == _AIR else [None]:
                        table[domain, band] = max(table.get((domain, band), 0.0), w.range_m)
            self.reach[key] = table
        return self.reach[key]

    def tracks(self, side: Side) -> dict[int, Entity]:
        if side not in self.known:
            known: dict[int, Entity] = {}
            for i, c in self.world.contacts[side].items():  # id order
                t = self.world.find(i)
                if c.age is None and t is not None and t.damage_state != "DISABLED":
                    known[i] = t
            wide = {i: max(self.reach_of(t).values(), default=0.0) for i, t in known.items()}
            near = [t for i, t in known.items() if wide[i] <= _LONG_M]
            self.known[side] = known
            self.far[side] = [t for i, t in known.items() if wide[i] > _LONG_M]
            self.short[side] = max((wide[t.id] for t in near), default=0.0)
            self.grid[side] = UniformGrid(_CELL_M)
            self.grid[side].rebuild(near)
        return self.known[side]


def _key(rules: Rules, e: Entity) -> tuple[str, str | None]:
    domain = rules.domain[e.kind]
    return domain, e.alt_band if domain == _AIR else None


def _armed(rules: Rules, e: Entity) -> bool:
    return rules.combat is not None and any(e.ammo)


def _group_threats(
    ctx: _Ctx, f: Entity, members: list[Entity], cache: dict[int, list[Entity]]
) -> list[Entity]:
    """The threats to `f`'s group if `f` is armed (empty otherwise), found once per group."""
    if not _armed(ctx.rules, f):
        return []
    root = min(m.id for m in members)  # the group's key; ids of different groups never mix
    if root not in cache:
        cache[root] = _find_threats(ctx, f.side, members)
    return cache[root]


def _find_threats(ctx: _Ctx, side: Side, members: list[Entity]) -> list[Entity]:
    """Tracked enemies that fired at a member within the memory, or whose kind's weapons reach a
    member now (module docstring, 2). Candidates come from a bounding circle of the group."""
    rules, tr = ctx.rules, ctx.rules.tasking
    known = ctx.tracks(side)
    if tr is None or not known:
        return []
    now = ctx.world.campaign.running_ticks + 1
    recent = {s for m in members for s, tick in m.fired_by if now - tick <= tr.threat_memory_ticks}
    cx = sum(m.pos.x for m in members) / len(members)
    cy = sum(m.pos.y for m in members) / len(members)
    radius = max(math.hypot(m.pos.x - cx, m.pos.y - cy) for m in members)
    near = ctx.grid[side].within(Vec2(cx, cy), radius + ctx.short[side])
    found = {t.id: t for t in (*near, *ctx.far[side])}
    found.update((i, known[i]) for i in recent if i in known)
    out = []
    for i in sorted(found):
        t = found[i]
        table = ctx.reach_of(t)
        if i in recent or any(
            (r := table.get(_key(rules, m))) is not None
            and (t.pos.x - m.pos.x) ** 2 + (t.pos.y - m.pos.y) ** 2 <= r * r
            for m in members
        ):
            out.append(t)
    return out


def _own_reach(rules: Rules, shooter: Entity, target: Entity) -> float:
    """The longest range of a loaded weapon of `shooter` (its own state) that can hit `target`."""
    cr = rules.combat
    if cr is None:
        return 0.0
    domain = rules.domain[target.kind]
    return max(
        (
            w.range_m
            for w, rounds in zip(
                cr.loadout(shooter.kind, shooter.variant), shooter.ammo, strict=True
            )
            if rounds > 0 and domain in w.targets and (domain != _AIR or target.alt_band in w.bands)
        ),
        default=0.0,
    )


def _engage(
    world: World,
    rules: Rules,
    f: Entity,
    members: list[Entity],
    threats: list[Entity],
    capped: dict[int, float],
) -> bool:
    """Break station toward the nearest threat `f` can hit (module docstring, 2); False: keep
    station (no such threat, `f` is beyond the leash of the convoy, or no road leads toward it).
    The leash is measured from the members that cannot be engaging themselves (the leader and
    unarmed followers), so escorts cannot leapfrog one another away from the convoy."""
    tr = rules.tasking
    anchors = [m for m in members if m.id != f.id and (m.follow_id is None or not _armed(rules, m))]
    if tr is None or not anchors or min(_dist(f, m) for m in anchors) > tr.leash_m:
        return False
    options = [
        (_dist(f, t), t.id, t, reach)
        for t in threats
        if min(_dist(t, m) for m in anchors) <= tr.leash_m
        and (reach := _own_reach(rules, f, t)) > 0.0
    ]
    if not options:
        return False
    d, _, t, reach = min(options, key=lambda o: (o[0], o[1]))
    if rules.domain[f.kind] == _AIR:
        f.path = [] if d <= reach else [t.pos]
    elif d <= reach:
        capped[f.id] = 0.0  # in range: it stops where it is, on its road, and fires
    else:
        return _approach(world, rules, f, t.pos)
    return True


def _seg_dist(ax: float, ay: float, bx: float, by: float, p: Vec2) -> float:
    """The distance from `p` to the segment a-b."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    k = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p.x - ax) * dx + (p.y - ay) * dy) / length2))
    return math.hypot(ax + k * dx - p.x, ay + k * dy - p.y)


def _approach(world: World, rules: Rules, f: Entity, p: Vec2) -> bool:
    """Head down the road that passes nearest `p`: the node it heads for or the one it left
    (mid-edge), or the neighbour of its node over a road no down bridge cuts (B-1). Greedy, one leg
    at a time, so only nodes with a road are ever chosen (a BRIDGE has none). False, path
    unchanged, when no leg gets closer to `p`."""
    if f.last_node is None:
        return False
    if on_node(rules, f):
        cut = blocked(world)
        options = [n for n, edge in rules.roads.neighbours(f.last_node) if edge.bridge not in cut]
    else:
        options = [n for n in _ends(world, rules, f) if isinstance(n, str)]
    best: tuple[float, str] | None = None
    for node in options:
        x, y = rules.roads.pos[node]
        cost = (_seg_dist(f.pos.x, f.pos.y, x, y, p), node)
        best = min(best or cost, cost)
    if best is None or best[0] >= math.hypot(p.x - f.pos.x, p.y - f.pos.y) - 1.0:
        return False
    f.path = [best[1]]
    return True


# --- station ------------------------------------------------------------------------------------


def _ends(world: World, rules: Rules, f: Entity) -> list[str | Vec2 | None]:
    """The nodes a ground unit may route from: the one it heads for, and mid-edge also the one it
    left (found by position when it already turned back), but never an end across a down bridge's
    cut point from it (the bank rule, Q-SIM-108)."""
    if on_node(rules, f) or f.last_node is None:
        return [f.path[0] if f.path else f.last_node]
    if at_stop(rules, f):  # on the cut point: it leaves only by its own bank (Q-SIM-114)
        return [f.last_node]
    ahead = f.path[0] if f.path and f.path[0] != f.last_node else None
    if ahead is None or ahead in rules.roads.spans:  # turned back, or out to a bridge's stop
        found = rules.roads.edge_at(f.last_node, f.pos.x, f.pos.y)
        ahead = None if found is None else found[0]
    if not isinstance(ahead, str):
        return [ahead, f.last_node]
    ends = ((ahead, f.last_node), (f.last_node, ahead))
    return [n for n, m in ends if not crosses(world, rules, m, n, f.pos)]


def _drive(world: World, rules: Rules, f: Entity, goal: str) -> bool:
    """Set `f`'s road path to `goal`; True when its path ends there. Unchanged when it already
    does, or there is no road. Mid-edge it may go on to the node it heads for or turn back to the
    one it left, whichever is the shorter way (`movement` drives a turn back). A bridge `goal` is
    its repair stop (NX-373 part 2): straight there from that bridge's road, else by
    `logistics.approach`."""
    at_node = on_node(rules, f)
    if (f.path[-1] if f.path else f.last_node) == goal and (f.path or at_node):
        return True
    if goal in rules.roads.spans and not at_node and f.last_node is not None:
        found = rules.roads.edge_at(f.last_node, f.pos.x, f.pos.y)
        if found is not None and found[1].bridge == goal:  # already on that bridge's road
            f.path = [goal]
            return True
    starts = [n for n in _ends(world, rules, f) if isinstance(n, str)]
    best: tuple[float, list[str]] | None = None
    for start in starts:
        route = (
            approach(world, rules, start, goal)  # a leader at a bridge's repair stop
            if goal in rules.roads.spans
            else shortest_path(rules.roads, start, goal, blocked=blocked(world))
        )
        if route is not None:
            x, y = rules.roads.pos[start]
            cost = math.hypot(x - f.pos.x, y - f.pos.y) + _length(Vec2(x, y), route[1:], rules)
            best = min(best or (cost, route), (cost, route), key=lambda c: c[0])
    if best is not None:
        f.path = [*best[1]]
    return best is not None


def _mult(rules: Rules, f: Entity) -> float:
    """The `speed_mult` of the road `f` is driving, 1.0 when it has no path."""
    path = f.path[1:] if f.path and f.path[0] == f.last_node and on_node(rules, f) else f.path
    if not path or f.last_node is None:
        return 1.0
    heading = rules.roads.toward(f.last_node, str(path[0]))
    return rules.roads.speed_mult_at(f.last_node, heading, f.pos.x, f.pos.y)


def _station_ground(
    world: World,
    rules: Rules,
    tr: TaskingRules,
    f: Entity,
    leader: Entity,
    capped: dict[int, float],
    catching: set[int],
) -> bool:
    """Steer a ground follower; True when it is in the group of its leader (module docstring, 3)."""
    ahead = leader.kind in rules.supply.carriers and f.kind not in rules.supply.carriers
    station = tr.station_m["escort" if ahead else "column"]
    stopped = not leader.path
    if stopped and leader.last_node is None:
        return False
    bridge = at_stop(rules, leader) if stopped else None  # parked at a bridge's repair stop
    dest = str(leader.path[-1] if leader.path else bridge or leader.last_node)
    parked = stopped and rules.node_kind.get(dest) != "BRIDGE"
    near = _dist(f, leader) <= tr.leash_m
    if stopped and not parked and _dist(f, leader) <= tr.follow_hold_slack * station:
        capped[f.id] = 0.0  # hold station where it is
        return True
    if not _drive(world, rules, f, dest):
        return False
    r_leader = _length(leader.pos, leader.path, rules)
    target = 0.0 if parked else max(r_leader - station if ahead else r_leader + station, 0.0)
    err = _length(f.pos, f.path, rules) - target
    top = rules.speed(f.kind, f.damage_state)
    want = min(max(math.hypot(leader.vel.x, leader.vel.y) + err / rules.world_dt, 0.0), top)
    if want < top:
        capped[f.id] = want / _mult(rules, f)
    else:
        catching.add(f.id)
    return near


def _station_air(world: World, rules: Rules, tr: TaskingRules, f: Entity, leader: Entity) -> None:
    """Steer an aircraft follower (module docstring, 3)."""
    bases = world.landing_bases(f.side)
    node = leader.last_node
    parked = (
        node in bases
        and not leader.path
        and leader.pos == Vec2(*rules.roads.pos[node or ""])
        and (leader.state in (None, "LANDED"))
    )
    if parked:
        f.path = [] if f.state == "LANDED" and f.last_node == node else [str(node)]
        return
    ground = rules.domain[leader.kind] == _GROUND
    speed = math.hypot(leader.vel.x, leader.vel.y)
    if not ground and speed >= rules.min_speed_mps[f.kind]:
        off = tr.station_m["wingman"]
        hx, hy = (leader.vel.x / speed, leader.vel.y / speed) if speed else (1.0, 0.0)
        f.path = [Vec2(leader.pos.x + hy * off, leader.pos.y - hx * off)]
    elif _dist(f, leader) > tr.station_m["overwatch" if ground else "wingman"]:
        f.path = [leader.pos]


# --- formation speed ----------------------------------------------------------------------------


def _formation(
    world: World,
    rules: Rules,
    members: list[Entity],
    capped: dict[int, float],
    catching: set[int],
) -> None:
    """Step 4: the slowest speed of each connected group of ground units caps them all, except the
    ones catching up; `capped` holds each follower's own station cap, the stricter one wins."""
    parent: dict[int, int] = {}

    def find(i: int) -> int:
        while parent.setdefault(i, i) != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for f in members:
        parent[find(f.id)] = find(f.follow_id or 0)
    slowest: dict[int, float] = {}
    for i in sorted(parent):
        e = world.get(i)
        root = find(i)
        slowest[root] = min(slowest.get(root, math.inf), rules.speed(e.kind, e.damage_state))
    kids: dict[int, list[int]] = {}
    for f in members:
        kids.setdefault(f.follow_id or 0, []).append(f.id)
    for i in sorted(parent):
        # A follower catching up runs free of the group, but not of its own followers: it is
        # held to the slowest of its sub-group (NX-369).
        cap = _subtree_slowest(world, rules, kids, i) if i in catching else slowest[find(i)]
        if (cap := min(cap, capped.get(i, math.inf))) < math.inf:
            world.speed_cap[i] = cap
    for i, cap in capped.items():
        world.speed_cap.setdefault(i, cap)


def _subtree_slowest(world: World, rules: Rules, kids: dict[int, list[int]], root: int) -> float:
    """The slowest speed among `root`'s followers, transitively; infinity with none."""
    slow, stack = math.inf, list(kids.get(root, ()))
    while stack:
        e = world.get(stack.pop())
        slow = min(slow, rules.speed(e.kind, e.damage_state))
        stack += kids.get(e.id, ())
    return slow if slow < math.inf else math.inf
