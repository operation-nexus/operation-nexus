"""Node defense HP: rebuild, starvation drain, the idle floor and the events (NX-124 part 3;
GAMEPLAY §8 and §9, COMBAT CB-10, Q-GD-18, Q-SIM-71, Q-TH-7).

`World.defense_hp` is each defended node's whole hp (every kind but BRIDGE, NX-373). An owned node
starts full, a NEUTRAL one at 0, and a node that changes hands is set to 0 for its new owner
(`reset`, no event: `NodeCaptured` says it). Capture cannot start on a node above 0 (`capture`).

- **Rebuild:** each whole stock unit unloaded into a node adds
  `logistics.defense_repair_hp_per_stock` up to the node's maximum, in the tick it is unloaded
  (`rebuild`, called by `logistics`).
- **Drain:** a node with finite stock below its starvation floor loses
  `logistics.starve_hp_drain_per_min` hp per game minute (`drain`, the `logistics_capture` slot
  after `logistics`). `World.defense_drain` is the carry: each starved running tick adds the
  per-minute figure and a whole minute of ticks is one lost hp per unit of it, so no fraction is
  lost. The
  carry is kept while the node is not starved (the drain pauses) and cleared at 0 hp or a flip.
- **Sanctuary repair (Q-SIM-71):** each logistics unit (`Supply.carriers`) of the owning side parked
  at its sanctuary (no path, `last_node` the sanctuary, not Disabled) rebuilds
  `capture.sanctuary_repair_hp_per_s` hp per world second there, from the sanctuary's infinite
  supply (no stock debit), so two trucks repair twice as fast. The sanctuary's `defense_drain` is
  its carry in thousandths of an hp (it never starves, so the drain does not use it); it clears at
  full hp. Not while paused.
- **Idle floor (Q-GP-44, Q-TH-7):** with no live viewer unit (`World.viewer_units() == 0`; AUTO is
  not in code yet, when it is its units will not count) the coalition sanctuary's hp
  cannot be reduced below `campaign.idle_floor.sanctuary_min_hp` (`floor`; off with
  `campaign.idle_floor.enabled` false, Q-CFG-16).
- **Events (no spam):** `NodeDefensesDown` when hp reaches 0, which puts the node in
  `World.defense_down`; `NodeDefensesRestored` only when a rebuild takes a node in that set all the
  way to full, which removes it. A node flapping around 0 gives one Down and one Restored per
  cycle; a node that was never down (NEUTRAL, or just flipped) emits nothing as it builds up. A
  flip clears the flag. Individual hits are `WeaponImpact`.

Deterministic: nodes in id order, integer state, no RNG.
"""

from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_defenses_down import NodeDefensesDown
from nexus.contracts.gen.events.node_defenses_restored import NodeDefensesRestored
from nexus.core.rules import DefenseRules, Rules
from nexus.core.world import World

MILLI_HP = 1000  # thousandths of an hp


def floor(world: World, rules: Rules, node: str) -> int:
    """The least hp `node` may be reduced to: `sanctuary_min_hp` for the coalition sanctuary while
    nobody plays and the idle floor is on."""
    d = rules.defense
    if d is None or not d.idle_floor or node != rules.sanctuary or world.viewer_units():
        return 0
    return d.sanctuary_min_hp


def _announce(world: World, node: str, down: bool, out: list[Event]) -> None:
    event = NodeDefensesDown if down else NodeDefensesRestored
    out.append(
        event.model_construct(
            kind=event.__name__,
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            node_id=node,
            owner=world.owner[node],
        )
    )


def damage(world: World, rules: Rules, node: str, amount: int, out: list[Event]) -> None:
    """Remove `amount` hp (not below `floor`); announces the drop to 0."""
    before = world.defense_hp[node]
    world.defense_hp[node] = max(before - amount, min(before, floor(world, rules, node)))
    if before and not world.defense_hp[node]:
        world.defense_drain[node] = 0
        if node not in world.defense_down:
            world.defense_down.add(node)
            _announce(world, node, True, out)


def rebuild(world: World, rules: Rules, node: str, units: int, out: list[Event]) -> None:
    """`units` whole stock units were unloaded into `node`."""
    if rules.defense is not None:
        heal(world, rules, node, units * rules.defense.repair_per_stock, out)


def heal(world: World, rules: Rules, node: str, hp: int, out: list[Event]) -> None:
    """Add `hp` to a defended node, up to its maximum; announces a rebuild to full."""
    d = rules.defense
    before = world.defense_hp.get(node)
    if d is None or before is None:
        return
    world.defense_hp[node] = min(d.max_hp[node], before + hp)
    if node in world.defense_down and world.defense_hp[node] == d.max_hp[node]:
        world.defense_down.discard(node)
        _announce(world, node, False, out)


def reset(world: World, node: str) -> None:
    """A flip: the node starts at 0 for its new owner."""
    if node in world.defense_hp:
        world.defense_hp[node] = world.defense_drain[node] = 0
        world.defense_down.discard(node)


def drain(world: World, out: list[Event]) -> None:
    """One running tick of the starvation drain."""
    rules = world.rules
    d = rules.defense if rules else None
    if world.frozen or rules is None or d is None:
        return
    _repair_sanctuaries(world, rules, d, out)
    if not d.drain_per_min:
        return
    for node, hp in world.defense_hp.items():  # id order
        if hp and node in world.stock and world.stock[node] < rules.supply.starve_floor[node]:
            carry = world.defense_drain[node] + d.drain_per_min
            lost, world.defense_drain[node] = divmod(carry, d.ticks_per_min)
            if lost:
                damage(world, rules, node, lost, out)


def _repair_sanctuaries(world: World, rules: Rules, d: DefenseRules, out: list[Event]) -> None:
    """Parked logistics units rebuild their side's sanctuary (Q-SIM-71)."""
    parked: dict[str, int] = {}
    for e in world.entities():
        node = rules.supply.rear[e.side]
        if (
            e.kind in rules.supply.carriers
            and world.owner[node] == e.side
            and not e.path
            and e.last_node == node
            and e.damage_state != "DISABLED"
        ):
            parked[node] = parked.get(node, 0) + 1
    for node in sorted(parked):
        if world.defense_hp[node] < d.max_hp[node]:
            carry = world.defense_drain[node] + parked[node] * d.sanctuary_repair_milli
            gain, world.defense_drain[node] = divmod(carry, MILLI_HP)
            heal(world, rules, node, gain, out)
            if world.defense_hp[node] == d.max_hp[node]:
                world.defense_drain[node] = 0


def validate(world: World, rules: Rules) -> None:
    """Check a restored world's defense state against the rules (a snapshot carries none)."""
    d = rules.defense
    if d is None:
        if world.defense_hp:
            raise ValueError("defense hp in a world whose rules have no defenses")
        return
    if list(world.defense_hp) != list(d.max_hp):
        raise ValueError("defense_hp does not name the rules' defended nodes")
    for node, hp in world.defense_hp.items():
        sanctuary = node in rules.supply.rear.values()  # its carry is in thousandths of an hp
        if hp > d.max_hp[node] or world.defense_drain[node] >= (
            MILLI_HP if sanctuary else d.ticks_per_min
        ):
            raise ValueError(f"defense of {node}: hp above its maximum or drain carry too large")
        if hp == 0 and world.defense_drain[node] and not sanctuary:
            raise ValueError(f"defense of {node}: a drain carry at 0 hp")
        if node in world.defense_down and hp == d.max_hp[node]:
            raise ValueError(f"defense of {node}: down but at full hp")
        if hp and world.owner[node] == "NEUTRAL":
            raise ValueError(f"defense of {node}: hp on a NEUTRAL node")
