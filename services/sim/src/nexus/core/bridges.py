"""Bridges: hp, STRUCTURE fire on a bridge, the cut road, `BridgeDestroyed`, truck field repair and
`BridgeRepaired` (NX-373 parts 1a and 2; STATE-MACHINES §4.3 B-1 and B-2, GAMEPLAY §5, COMBAT CB-10,
Q-GD-11, Q-SIM-101, Q-SIM-105..107; the collapse NX-400, Q-SIM-112; who fires NX-408, Q-SIM-124).

`World.bridge_hp` holds every BRIDGE node's whole hp in id order, starting at `logistics.bridge_hp`;
`World.bridge_down` the bridges that reached 0. A down bridge stays down until it is repaired to
full, so the set, not the hp, is what cuts the road.

- **Who fires (Q-SIM-105, Q-SIM-124):** only a unit holding a claim on a STRIKE job (its own
  `job_id` on its side's board) whose node is the bridge, with a STRUCTURE weapon, the bridge in
  range, hp left and not down (a bridge under repair is never struck again, the Q-SIM-112
  constraint), after unit targets (CB-1 unchanged) and before the automatic node fallback, which
  never picks a bridge (it takes only enemy-owned nodes with defense hp; a bridge is NEUTRAL and
  has none). A direct GOTO order to a bridge (`Entity.order_node`) is a hold that defends it, never
  a strike: the holder engages units by CB-1 and never fires on the span (Q-SIM-124 amends
  Q-SIM-112).
- **Hits:** `damage` takes the weapon's full `damage` (armor 0, Q-CBT-22), never below 0; a shot
  landing on a bridge already at 0 fizzles (`combat`). At 0 the bridge goes down and
  `BridgeDestroyed{node_id, by_id, lost_ids}` names the shooter, once per down cycle.
- **Collapse (Q-SIM-112):** that hit then destroys, in id order and before the reroute, every
  GROUND unit of either side on the bridge's edge (not standing on an end node) within
  `logistics.bridge_collapse_radius_m` of the cut point, measured along the edge: `lose_unit` with
  the shooter as killer, no assists and cause BRIDGE_COLLAPSE (cargo lost, CB-8 crew roll), and a
  victim of the other side counts for the Static as a kill by that shooter
  (`provocation.suffered_hit`, no new weight). Aircraft are not affected.
- **Roads (B-1):** every path planner passes `blocked(world)` to `roads.shortest_path`, so a down
  bridge's edge is in no path computed after the tick it fell.
- **Paths already set (NX-373 part 1b, Q-SIM-108):** the hit that brings a bridge down calls
  `reroute`: every GROUND unit with a path, in id order, whose remaining road (its position, then
  its path) crosses a down bridge's cut point (the bridge node's position projected on the edge)
  replans from the last node before the crossing (a coalition patrol through held nodes only, as
  `tasking._patrol_route`; a supply run, a RESUPPLY claimant or a loaded truck on a GOTO order to
  its path's last node, of either side, around nodes the other side holds, as
  `logistics.supply_route`, Q-SIM-122), or
  stops there with no route. A unit on the cut edge at or past the
  cut point and beyond the collapse radius carries on; aircraft are not affected.

- **Repair (NX-373 part 2, Q-GD-11):** a bridge is not a road endpoint: a truck repairs it at its
  *stop*, the bridge's position projected on its road (`RoadGraph.stops`, the cut point), reached
  along the half of the edge from a bank (a path ending in the bridge's id, `step._waypoint`), its
  `last_node` staying the bank. Each carrier of either side parked there (no path, not Disabled)
  adds `Supply.bridge_repair_milli` thousandths of an hp per running tick, from
  `logistics.bridge_hp / (bridge_repair_time_s x truck_bridge_repair_mult)` per world second; the
  thousandths carry in `World.bridge_repair`, which a truck leaving keeps. Capped at the maximum
  (B-2), no cargo cost, not while paused. At full the carry is 0, and a down bridge is up again (its
  edge returns) with `BridgeRepaired{node_id, by_id}` naming the lowest-id carrier parked there; a
  damaged bridge that was never down emits nothing. The repair also starts that bridge's
  STRIKE_BRIDGE cooldown (`provocation.bridge_repaired`, NX-401). No regeneration and no
  starvation drain (a bridge has no stock). Deterministic: integer state, no RNG of its own.
"""

from collections.abc import Mapping
from itertools import pairwise

from nexus.contracts.gen.common.enums import NodeOwner, Side
from nexus.contracts.gen.events.bridge_destroyed import BridgeDestroyed
from nexus.contracts.gen.events.bridge_repaired import BridgeRepaired
from nexus.contracts.gen.events.event import Event
from nexus.core.defense import MILLI_HP
from nexus.core.provocation import bridge_repaired, suffered_hit
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules, WeaponRules
from nexus.core.world import Entity, Vec2, World, at_stop, lose_unit


def blocked(world: World) -> frozenset[str]:
    """The bridges whose road edge is cut (`roads.shortest_path`'s `blocked`)."""
    return frozenset(world.bridge_down)


def target(world: World, rules: Rules, w: WeaponRules, shooter: Entity) -> tuple[str, float] | None:
    """The bridge `shooter` fires `w` at, with the squared distance: its STRIKE job's node, when
    that is a bridge with hp left, not down, within `range_m` (Q-SIM-105); else None. A GOTO order
    to a bridge never fires on it (Q-SIM-124)."""
    job = None if shooter.job_id is None else world.boards[shooter.side].get(shooter.job_id)
    node = job.node if job is not None and job.kind == "STRIKE" else None
    if node is None or not world.bridge_hp.get(node) or node in world.bridge_down:
        return None
    x, y = rules.roads.pos[node]
    d2 = (shooter.pos.x - x) ** 2 + (shooter.pos.y - y) ** 2
    return (node, d2) if d2 <= w.range_m**2 else None


def damage(
    world: World, rules: Rules, node: str, amount: int, by_id: int, out: list[Event]
) -> None:
    """Remove `amount` hp, not below 0; at 0 the bridge goes down, announces it once, destroys the
    ground units on it (`collapsing`) and reroutes the units whose road crosses it (`reroute`)."""
    world.bridge_hp[node] = max(0, world.bridge_hp[node] - amount)
    if world.bridge_hp[node] or node in world.bridge_down:
        return
    world.bridge_down.add(node)
    lost, shooter = collapsing(world, rules, node), world.find(by_id)
    out.append(
        BridgeDestroyed.model_construct(
            kind="BridgeDestroyed",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            node_id=node,
            by_id=by_id,
            lost_ids=[e.id for e in lost],
        )
    )
    for e in lost:
        was = e.damage_state
        lose_unit(world, e, out, killer_id=by_id, cause="BRIDGE_COLLAPSE")
        if shooter is not None and shooter.side != e.side:
            suffered_hit(world, shooter, e, was)  # a kill as any other (Q-SIM-112)
    reroute(world, rules)


def collapsing(world: World, rules: Rules, node: str) -> list[Entity]:
    """The GROUND units, in id order, on the road edge `node` carries (off its end nodes) within
    `logistics.bridge_collapse_radius_m` of the cut point, measured along the edge (Q-SIM-112)."""
    radius, pos = rules.supply.bridge_collapse_m, rules.roads.pos
    lost = []
    for e in world.entities():
        last = e.last_node
        if rules.domain[e.kind] != "GROUND" or last is None or e.pos == Vec2(*pos[last]):
            continue
        found = rules.roads.edge_at(last, e.pos.x, e.pos.y)
        if found is None or found[1].bridge != node:
            continue
        (ax, ay), (bx, by), (cx, cy) = pos[last], pos[found[0]], pos[node]
        along = (e.pos.x - cx) * (bx - ax) + (e.pos.y - cy) * (by - ay)  # x the edge length
        if abs(along) <= radius * found[1].length_m:
            lost.append(e)
    return lost


def not_held(world: World, rules: Rules, side: Side) -> frozenset[str]:
    """The nodes `side` does not hold: a coalition patrol's road `avoid` (Q-SIM-94)."""
    return frozenset(n for n in rules.roads.pos if world.owner.get(n) != side)


def enemy_held(world: World, rules: Rules, side: Side) -> frozenset[str]:
    """The nodes the other side holds: a supply run's road `avoid`, either side's
    (`logistics.supply_route`, Q-SIM-122); neutral ground stays passable."""
    return held_by_other(rules, world.owner, side)


def held_by_other(rules: Rules, owners: Mapping[str, NodeOwner], side: Side) -> frozenset[str]:
    """`enemy_held` from an owner table (the world's, or a `SideView`'s, FOW-10)."""
    other = "ENEMY" if side == "COALITION" else "COALITION"
    return frozenset(n for n in rules.roads.pos if owners.get(n) == other)


def crosses(world: World, rules: Rules, frm: str, to: str, pos: Vec2) -> bool:
    """True when a unit at `pos` on the road `frm` -> `to`, driving toward `to`, has a down
    bridge's cut point still ahead of it: the edge's bridge is down and `pos` projects onto the
    edge short of the bridge node's position. At or past the cut point: False (it carries on)."""
    bridge = rules.roads.edge(frm, to).bridge
    if bridge not in world.bridge_down or rules.roads.stops.get(bridge) == (pos.x, pos.y):
        return False  # intact, or standing on the cut point (its repair stop)
    (ax, ay), (bx, by), (cx, cy) = (rules.roads.pos[n] for n in (frm, to, bridge))
    dx, dy = bx - ax, by - ay
    return (pos.x - ax) * dx + (pos.y - ay) * dy < (cx - ax) * dx + (cy - ay) * dy


def reroute(world: World, rules: Rules) -> None:
    """Replan every GROUND unit, in id order, whose remaining road crosses a down bridge
    (Q-SIM-108): its current leg toward the cut point turns back to the node it came from; a later
    hop over a cut edge keeps the path up to the node before it. From that node it takes
    `roads.shortest_path` (with `blocked`) to its last path node, or stops there with none. A
    coalition patrol replans through held nodes only; a supply run (a RESUPPLY claimant, or a
    loaded truck on a GOTO order to that last node) enters no node the other side holds, that
    node exempt
    (`enemy_held`, Q-SIM-122); an empty capture-run truck takes any road. A path to a bridge's
    repair stop is planned to the bank before it, the stop kept after a new route."""
    cut = blocked(world)
    for e in world.entities():
        path = [n for n in e.path if isinstance(n, str)]
        stop = path.pop() if path and path[-1] in rules.roads.spans else None
        if rules.domain[e.kind] != "GROUND" or not path or e.last_node is None:
            continue
        origin = e.last_node  # where the current leg began
        at_node = e.pos == Vec2(*rules.roads.pos[origin])
        if path[0] == origin and not at_node:  # turning back: the leg began at the far end
            found = rules.roads.edge_at(origin, e.pos.x, e.pos.y)
            if found is None:  # off its road: ground units stay on their segment, so never
                continue
            origin = found[0]
        seq = [origin, *path[1:]] if path[0] == origin else [origin, *path]
        job = None if e.job_id is None else world.boards[e.side].get(e.job_id)
        held = job is not None and job.kind == "PATROL" and job.via is None  # coalition patrol
        avoid = not_held(world, rules, e.side) if held else frozenset()
        goto_run = e.order == "GOTO" and bool(e.cargo) and seq[-1] == e.order_node
        supply = job.kind == "RESUPPLY" if job is not None else goto_run
        if supply:  # a supply run (Q-SIM-122): around enemy-held nodes, its destination exempt
            avoid = enemy_held(world, rules, e.side) - {seq[-1]}
        for k, (a, b) in enumerate(pairwise(seq)):
            if rules.roads.edge(a, b).bridge in cut and (k or crosses(world, rules, a, b, e.pos)):
                route = shortest_path(rules.roads, a, seq[-1], blocked=cut, avoid=avoid)
                e.path = [*seq[1:k], *(route or [a]), *([stop] if route and stop else [])]
                break


def repair(world: World, out: list[Event]) -> None:
    """One running tick of truck field repair (module docstring)."""
    rules = world.rules
    if world.frozen or rules is None or not rules.supply.bridge_repair_milli:
        return
    parked: dict[str, list[int]] = {}
    for e in world.entities():  # id order: each list starts with its lowest id
        if e.kind in rules.supply.carriers and not e.path and e.damage_state != "DISABLED":
            node = at_stop(rules, e)
            if node in world.bridge_hp:
                parked.setdefault(str(node), []).append(e.id)
    for node, ids in sorted(parked.items()):
        top = rules.supply.bridge_hp[node]
        if world.bridge_hp[node] == top:
            continue
        carry = world.bridge_repair[node] + len(ids) * rules.supply.bridge_repair_milli
        gain, world.bridge_repair[node] = divmod(carry, MILLI_HP)
        world.bridge_hp[node] = min(top, world.bridge_hp[node] + gain)
        if world.bridge_hp[node] < top:
            continue
        world.bridge_repair[node] = 0
        if node in world.bridge_down:
            world.bridge_down.discard(node)
            out.append(
                BridgeRepaired.model_construct(
                    kind="BridgeRepaired",
                    tick=world.campaign.tick + 1,
                    event_seq=world.next_event_seq(),
                    campaign_id=world.campaign.id,
                    node_id=node,
                    by_id=ids[0],
                )
            )
            bridge_repaired(world, node)  # its STRIKE_BRIDGE cooldown starts (NX-401)


def validate(world: World, rules: Rules) -> None:
    """Check a restored world's bridge state against the rules (a snapshot carries none): exactly
    the theater's bridges, 0 <= hp <= max, 0 hp means down, a down bridge is below full, and a
    repair carry is below one hp and 0 at full."""
    top = rules.supply.bridge_hp
    if list(world.bridge_hp) != list(top) or list(world.bridge_repair) != list(top):
        raise ValueError("bridge_hp or bridge_repair does not name the theater's bridges")
    for node, hp in world.bridge_hp.items():
        down, carry = node in world.bridge_down, world.bridge_repair[node]
        if hp > top[node] or (hp == 0 and not down) or (down and hp == top[node]):
            raise ValueError(f"bridge {node}: hp above its maximum, or hp and down disagree")
        if carry >= MILLI_HP or (carry and hp == top[node]):
            raise ValueError(f"bridge {node}: repair carry of a whole hp, or one at full hp")
