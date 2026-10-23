"""Bridges: hp, STRUCTURE fire on a bridge, the cut road and `BridgeDestroyed` (NX-373 part 1a;
STATE-MACHINES §4.3 B-1 and B-2, GAMEPLAY §5, COMBAT CB-10, Q-GD-11, Q-SIM-101, Q-SIM-105..107).

`World.bridge_hp` holds every BRIDGE node's whole hp in id order, starting at `logistics.bridge_hp`;
`World.bridge_down` the bridges that reached 0. A down bridge stays down until it is repaired to
full (repair is part 2), so the set, not the hp, is what cuts the road.

- **Who fires (Q-SIM-105):** only a unit holding a claim on a STRIKE job (its own `job_id` on its
  side's board) whose node is the bridge, with a STRUCTURE weapon, the bridge in range and hp left,
  after unit targets (CB-1 unchanged) and before the automatic node fallback, which never picks a
  bridge (it takes only enemy-owned nodes with defense hp; a bridge is NEUTRAL and has none).
- **Hits:** `damage` takes the weapon's full `damage` (armor 0, Q-CBT-22), never below 0; a shot
  landing on a bridge already at 0 fizzles (`combat`). At 0 the bridge goes down and
  `BridgeDestroyed{node_id, by_id}` names the shooter, once per down cycle.
- **Roads (B-1):** every path planner passes `blocked(world)` to `roads.shortest_path`, so a down
  bridge's edge is in no path computed after the tick it fell.

No regeneration and no starvation drain (a bridge has no stock). Deterministic: integer state, no
RNG of its own.
"""

from nexus.contracts.gen.events.bridge_destroyed import BridgeDestroyed
from nexus.contracts.gen.events.event import Event
from nexus.core.rules import Rules, WeaponRules
from nexus.core.world import Entity, World


def blocked(world: World) -> frozenset[str]:
    """The bridges whose road edge is cut (`roads.shortest_path`'s `blocked`)."""
    return frozenset(world.bridge_down)


def target(world: World, rules: Rules, w: WeaponRules, shooter: Entity) -> tuple[str, float] | None:
    """The bridge `shooter` fires `w` at, with the squared distance: its STRIKE job's node when that
    is a bridge with hp left within `range_m` (Q-SIM-105); else None."""
    job = None if shooter.job_id is None else world.boards[shooter.side].get(shooter.job_id)
    node = job.node if job is not None and job.kind == "STRIKE" else None
    if node is None or not world.bridge_hp.get(node):
        return None
    x, y = rules.roads.pos[node]
    d2 = (shooter.pos.x - x) ** 2 + (shooter.pos.y - y) ** 2
    return (node, d2) if d2 <= w.range_m**2 else None


def damage(world: World, node: str, amount: int, by_id: int, out: list[Event]) -> None:
    """Remove `amount` hp, not below 0; at 0 the bridge goes down and announces it once."""
    world.bridge_hp[node] = max(0, world.bridge_hp[node] - amount)
    if world.bridge_hp[node] or node in world.bridge_down:
        return
    world.bridge_down.add(node)
    out.append(
        BridgeDestroyed.model_construct(
            kind="BridgeDestroyed",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            node_id=node,
            by_id=by_id,
        )
    )


def validate(world: World, rules: Rules) -> None:
    """Check a restored world's bridge state against the rules (a snapshot carries none): exactly
    the theater's bridges, 0 <= hp <= max, 0 hp means down, and a down bridge is below full."""
    top = rules.supply.bridge_hp
    if list(world.bridge_hp) != list(top):
        raise ValueError("bridge_hp does not name the theater's bridges")
    for node, hp in world.bridge_hp.items():
        down = node in world.bridge_down
        if hp > top[node] or (hp == 0 and not down) or (down and hp == top[node]):
            raise ValueError(f"bridge {node}: hp above its maximum, or hp and down disagree")
