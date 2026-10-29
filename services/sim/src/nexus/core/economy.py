"""Force economy, part 1: source pools, income and storage (NX-412; ECONOMY EC-1, EC-2, EC-3,
EC-10 steps 1-2, EC-15).

Each side's source (its SANCTUARY, `Supply.rear`) holds a finite whole-unit pool in
`World.pool`, unless the side runs in unlimited mode (`economy.unlimited.<side>`): a side absent
from `World.pool` has the infinite source of before NX-412, so the snapshot names the mode, and
a restore refuses pools that do not match the rules' limited sides (`validate`).
Every `economy.window_s` running ticks, before the director window in the same tick (EC-10):

1. Income: the pool gains `income.floor` plus `income.per_node.<kind>` for each node the side
   owns (`World.owner`) with no capture bar on it (`World.capture`: not contested), capped at
   storage; `SupplyProduced{side, amount}`, none for 0.
2. Clip: storage is `storage.floor` plus `storage.per_node.<kind>` for each node the side owns;
   stock above it (a lost node lowered the cap) is removed as `SupplyConsumed{STORAGE_LOST}` at
   the source, never silently. `World.storage` keeps the cap the clip used.

The pool pays for what the source pays today: truck loads (`logistics.load`). A pool that
cannot pay loads less, or nothing, as an empty base does. Free spawns at the sanctuary stay free
(EC-13 is a later part). Deterministic: sides in Side order, nodes in id order, no RNG.
"""

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.supply_produced import SupplyProduced
from nexus.core.rules import EconomyRules, Rules
from nexus.core.world import World, consumed

MOVERS = ("AIR", "GROUND")  # the domains the EC-8 guard and the Director's live units count


def _held(world: World, rules: Rules, er: EconomyRules, side: Side) -> list[str]:
    """The nodes `side` owns that earn or store (a kind with an `income.per_node` entry)."""
    return [
        n for n, kind in rules.node_kind.items()
        if kind in er.income_per_node and world.owner.get(n) == side
    ]  # fmt: skip


def storage_cap(world: World, rules: Rules, er: EconomyRules, side: Side) -> int:
    """EC-2: `storage.floor` plus each held node's `storage.per_node`."""
    held = _held(world, rules, er, side)
    return er.storage_floor + sum(er.storage_per_node[rules.node_kind[n]] for n in held)


def income(world: World, rules: Rules, er: EconomyRules, side: Side) -> int:
    """EC-1: `income.floor` plus each held node with no capture bar's `income.per_node`."""
    held = _held(world, rules, er, side)
    return er.income_floor + sum(
        er.income_per_node[rules.node_kind[n]] for n in held if n not in world.capture
    )


def start(world: World) -> None:
    """Campaign setup: each limited side's pool starts full, at its storage cap."""
    rules = world.rules
    er = rules.economy if rules else None
    if rules is None or er is None:
        return
    for side in er.limited:
        world.storage[side] = world.pool[side] = storage_cap(world, rules, er, side)


def validate(world: World, rules: Rules) -> None:
    """Check a restored world's source pools against the campaign rules (a snapshot carries
    none); raises ValueError. Each limited side has a pool and no other side does, so a save made
    under other `economy.unlimited.<side>` values never restores into a side with no pool."""
    er = rules.economy
    limited = set(er.limited) if er else set()
    if set(world.pool) != limited:
        raise ValueError(
            f"economy: the snapshot's source pools {sorted(world.pool)} do not match the rules' "
            f"limited sides {sorted(limited)}"
        )


def due(world: World) -> tuple[Rules, EconomyRules] | None:
    """The rules when this tick is an economy window (every `window_ticks`-th running tick); None
    otherwise, without economy rules, or while frozen (SC-11)."""
    rules = world.rules
    er = rules.economy if rules else None
    if world.frozen or rules is None or er is None:
        return None
    return None if (world.campaign.running_ticks + 1) % er.window_ticks else (rules, er)


def window(world: World, out: list[Event]) -> None:
    """EC-10 steps 1-2 at an economy window (`due`); upkeep (step 3) is `nexus.core.upkeep`."""
    if (ready := due(world)) is None:
        return
    rules, er = ready
    for side in sorted(world.pool):
        cap = storage_cap(world, rules, er, side)
        gain = max(0, min(income(world, rules, er, side), cap - world.pool[side]))
        world.pool[side] += gain
        world.storage[side] = cap
        if gain:
            out.append(
                SupplyProduced.model_construct(
                    kind="SupplyProduced", tick=world.campaign.tick + 1,
                    event_seq=world.next_event_seq(), campaign_id=world.campaign.id,
                    side=side, amount=gain,
                )
            )  # fmt: skip
        lost = world.pool[side] - cap
        if lost > 0:
            world.pool[side] = cap
            out.append(consumed(world, rules.supply.rear[side], lost, "STORAGE_LOST"))


def pool_side(world: World, node: str) -> Side | None:
    """The side whose finite source pool `node` is, or None (a base, or an infinite source)."""
    rules = world.rules
    if rules is None:
        return None
    return next((s for s in sorted(world.pool) if rules.supply.rear[s] == node), None)


def source_stock(world: World, node: str) -> int | None:
    """What a source can load: a base's stock, a limited source's pool; None when infinite."""
    if node in world.stock:
        return world.stock[node]
    side = pool_side(world, node)
    return None if side is None else world.pool[side]


def guard_room(world: World, side: Side) -> int | None:
    """EC-8 (NX-412 part 3): how many more movers (AIR and GROUND units) `side` may have live
    under `sim.max_live_units_per_side`; None under `economy.legacy_rules`, which has no guard."""
    rules = world.rules
    er = rules.economy if rules else None
    if rules is None or er is None or er.legacy:
        return None
    live = sum(e.side == side and rules.domain[e.kind] in MOVERS for e in world.entities())
    return er.max_live_per_side - live
