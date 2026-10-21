"""Rearm stops: fuel, ammo and repair at a friendly base (NX-124 part 2; GAMEPLAY §5, §5b,
Q-SIM-51, Q-SIM-53, Q-SIM-68, STATE-MACHINES §4.1 Landed / Rearming).

`restock`, called by the `logistics` system for every entity that is not unloading cargo, runs one
tick of a unit's stop. Where it stops (`_station`): an aircraft LANDED with no path at a landing
base of its side; a GROUND unit with no path standing on a friendly base node (any node but a
BRIDGE); a facility at its own base while the base is friendly and has no capture bar (not
contested). A Disabled non-facility is a wreck and never restocks (CB-7). A kind with no
`loadout_cost` (the cargo kinds) is skipped.

Three lines are bought in this order, all from the base's stock (a SANCTUARY is infinite: the same
rates, no debit), each in exact integers:

- **Fuel** (aircraft). Up to `rearm_rate x world_dt` stock-thousandths a tick (`Supply.rearm_milli`,
  shared with ammo). A full tank costs `loadout_cost` for a kind with no ammo and half of it for a
  kind with ammo; only the missing fuel is paid for. Below the starvation floor it fills to
  `starved_loadout.fuel_frac` of `fuel_s`.
- **Ammo.** A full load costs the other half (all of it for a kind with no fuel; a facility pays
  `facility_rearm_cost`). The ammo share is the average over the weapons of each one's missing share
  (rounds missing / its full load, Q-SIM-69), so a round costs `price / (n x its full load)`, guns
  included. Rounds refill in loadout order with whatever the budget affords, carried as
  `Entity.ammo_credit` until a round is whole. A starved base (GAMEPLAY §5,
  `starved_loadout.secondary_ammo` 0) refills only guns (`projectile_speed_mps` null). A Disabled
  facility restocks nothing until repaired.
- **Repair.** `logistics.repair_rate.<node kind>` hp per world second (`Supply.repair_milli`,
  thousandths of an hp a tick, carried as `Entity.repair_milli`). A unit pays `loadout_cost x` the
  share of its max hp repaired, a facility 1 stock per `logistics.facility_repair_hp_per_stock` hp;
  the price is an exact fraction `num/den` of stock per hp, owed in `Entity.repair_debt`
  (units of 1/den stock-thousandths). A starved base still repairs.

Every stock-thousandth drawn is added to `Entity.rearm_milli`; a whole stock unit leaves the node as
it reaches 1000 and is counted in `rearm_spent`, so units debited = thousandths bought / 1000 and
`SupplyConsumed{REARM}` (fuel and ammo) and `SupplyConsumed{REPAIR}` (hp), one each per stop when it
ends (everything wanted is bought, the unit leaves, or the base stalls); repair has its own carries
`repair_owed` and `repair_spent`. A base never sells beyond its stock. When something is still
wanted and nothing could be bought, `RearmStalled` is emitted once. The damage state follows hp:
each repair step that changes it emits `UnitDamageStateChanged`, and the step that reaches max hp
`UnitRepaired{by_id: None, node_id}`.
Deterministic: integers except fuel, entities in id order (the caller), no RNG.
"""

import math
from dataclasses import dataclass

from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.rearm_stalled import RearmStalled
from nexus.contracts.gen.events.unit_repaired import UnitRepaired
from nexus.core.rules import CombatRules, Rules
from nexus.core.world import Entity, Vec2, World, end_rearm, set_damage_state

_MILLI = 1000
_EPS = 1e-6  # float noise in a fuel-to-milli conversion; below any real milli-unit of stock
_DISABLED = "DISABLED"
_STATIC, _AIR, _GROUND = "STATIC", "AIR", "GROUND"


@dataclass(slots=True)
class _Buy:
    """One entity's purchases this tick. `room` is the stock-thousandths the node can still pay
    (None: infinite); `budget` what is left of the per-tick fuel and ammo rate."""

    room: int | None
    budget: int
    drawn: int = 0  # stock-thousandths bought for fuel and rounds
    repair_drawn: int = 0  # stock-thousandths bought for repair
    moved: bool = False  # anything bought or restored
    unmet: bool = False  # something is still wanted

    def afford(self, n: int) -> int:
        return n if self.room is None else min(n, self.room)

    def draw(self, n: int, *, repair: bool = False) -> None:
        if repair:
            self.repair_drawn += n
        else:
            self.drawn += n
        if self.room is not None:
            self.room -= n


def _station(world: World, rules: Rules, e: Entity) -> str | None:
    """The base node where `e` is stopped to restock, or None."""
    if e.path:  # moving (a facility never has a path)
        return None
    domain = rules.domain[e.kind]
    if domain == _STATIC:
        node = e.base_id
        return (
            node if node and world.owner.get(node) == e.side and node not in world.capture else None
        )
    node = e.last_node
    if node is None or world.owner.get(node) != e.side:
        return None
    if domain == _AIR:
        return node if e.state == "LANDED" and node in rules.landing_nodes else None
    on_it = domain == _GROUND and e.pos == Vec2(*rules.roads.pos[node])
    return node if on_it and rules.node_kind.get(node) != "BRIDGE" else None


def ammo_price(rules: Rules, e: Entity) -> int:
    """A full load of rounds in stock-thousandths: a facility pays `facility_rearm_cost`; a unit
    half its `loadout_cost` if it also has a tank, else all of it; 0 for an unarmed kind."""
    cr, sup = rules.combat, rules.supply
    if cr is None or not cr.loadout(e.kind, e.variant):
        return 0
    if rules.domain[e.kind] == _STATIC:
        return _MILLI * sup.facility_rearm_cost
    whole = _MILLI * sup.loadout_cost.get(e.kind, 0)
    return whole // 2 if e.kind in rules.fuel_s else whole


def restock(world: World, rules: Rules, e: Entity, out: list[Event]) -> None:
    """One running tick of `e`'s stop at a base (module docstring); ends it if `e` is not at one."""
    sup, cr = rules.supply, rules.combat
    node = _station(world, rules, e)
    facility = rules.domain[e.kind] == _STATIC
    cost = sup.loadout_cost.get(e.kind, 0)
    if node is None or (e.damage_state == _DISABLED and not facility):
        return end_rearm(world, e, out)
    finite = node in world.stock
    starved = finite and world.stock[node] < sup.starve_floor[node]
    room = max(0, world.stock[node] * _MILLI - e.rearm_milli - e.repair_owed) if finite else None
    b = _Buy(room, sup.rearm_milli)
    price = ammo_price(rules, e)
    if cost and not facility:  # a kind with no loadout cost (a truck) has nothing to refuel or arm
        _buy_fuel(rules, e, _MILLI * cost - price, starved, b)
    if price and cr is not None and e.damage_state != _DISABLED:
        _buy_ammo(cr, e, price, starved, b)
    if cr is not None:
        _repair(world, rules, cr, e, node, cost, b, out)
    if finite:
        paid, e.rearm_milli = divmod(e.rearm_milli + b.drawn, _MILLI)
        fixed, e.repair_owed = divmod(e.repair_owed + b.repair_drawn, _MILLI)
        world.stock[node] -= paid + fixed
        e.rearm_spent += paid
        e.repair_spent += fixed
    if not b.unmet:
        return end_rearm(world, e, out)
    if b.moved:
        e.stalled = False
    else:
        _stall(world, e, node, out)


def _buy_fuel(rules: Rules, e: Entity, price: int, starved: bool, b: _Buy) -> None:
    """Fuel up to the tank (or the starved cap); `price` is a full tank in stock-thousandths."""
    if e.fuel is None:
        return
    full = rules.fuel_s[e.kind]
    cap = rules.supply.starved_fuel_frac * full if starved else full
    if e.fuel >= cap:
        return
    # shortcut: the stop's node is `last_node` when it ends; an aircraft that takes off and reaches
    # another node in one tick would report there (nodes are km apart, a tick moves < 200 m).
    need = math.ceil((cap - e.fuel) * price / full - _EPS)
    if need <= 0:  # what is missing is float noise: full
        e.fuel = cap
        return
    pay = b.afford(min(b.budget, need))
    if pay > 0:
        b.draw(pay)
        b.budget -= pay
        b.moved = True
        e.fuel = cap if pay == need else e.fuel + pay * full / price
    b.unmet |= e.fuel < cap


def _buy_ammo(cr: CombatRules, e: Entity, price: int, starved: bool, b: _Buy) -> None:
    """Rounds in loadout order. `price` is the whole load in stock-thousandths, split equally
    between the n weapons, so a round of a weapon with `full` rounds costs `price / (n x full)`.
    With `big` the lcm of the full loads, `ammo_credit` counts stock-thousandths x n x big and
    that round costs `price x big / full` of it: whole numbers throughout."""
    loadout = cr.loadout(e.kind, e.variant)
    n, big = len(loadout), math.lcm(*(w.ammo for w in loadout))
    unit = [price * big // w.ammo for w in loadout]  # credit per round of each weapon
    todo = [
        i for i, w in enumerate(loadout)
        if e.ammo[i] < w.ammo and not (starved and w.speed_mps is not None)
    ]  # fmt: skip
    short = sum((loadout[i].ammo - e.ammo[i]) * unit[i] for i in todo) - e.ammo_credit
    if not todo:
        return
    buy = b.afford(min(b.budget, max(0, -(-short // (n * big)))))
    e.ammo_credit += buy * n * big
    b.draw(buy)
    b.budget -= buy
    b.moved |= buy > 0
    for i in todo:
        take = min(loadout[i].ammo - e.ammo[i], e.ammo_credit // unit[i])
        e.ammo[i] += take
        e.ammo_credit -= take * unit[i]
        b.moved |= take > 0
    b.unmet |= any(e.ammo[i] < loadout[i].ammo for i in todo)


def _repair(
    world: World, rules: Rules, cr: CombatRules, e: Entity, node: str, cost: int, b: _Buy,
    out: list[Event],
) -> None:  # fmt: skip
    """Hp at the base's repair rate; see the module docstring for the price."""
    stats = cr.units[e.kind]
    missing = stats.hp - e.hp
    rate = rules.supply.repair_milli.get(rules.node_kind.get(node, "BRIDGE"), 0)
    if missing <= 0 or rate <= 0:
        return
    num, den = (
        (1, rules.supply.facility_hp_per_stock) if rules.domain[e.kind] == _STATIC
        else (cost, stats.hp)
    )  # fmt: skip
    m = min(rate, missing * _MILLI - e.repair_milli)  # thousandths of an hp this tick
    paying = b.room is not None and num > 0  # a SANCTUARY, or a kind with no cost, is free
    if paying and b.room is not None:  # a finite base: it can pay only so much
        m = min(m, ((b.room + 1) * den - 1 - e.repair_debt) // num)
    if m > 0:
        if paying:
            whole, e.repair_debt = divmod(e.repair_debt + num * m, den)
            b.draw(whole, repair=True)
        gained, e.repair_milli = divmod(e.repair_milli + m, _MILLI)
        b.moved = True
        if gained:
            e.hp += gained
            _repaired(world, cr, e, node, out)
    b.unmet |= e.hp < stats.hp


def _repaired(world: World, cr: CombatRules, e: Entity, node: str, out: list[Event]) -> None:
    stats = cr.units[e.kind]
    state = stats.state(e.hp)
    if state != e.damage_state:
        set_damage_state(world, e, state, out)
    if e.hp == stats.hp:
        out.append(
            UnitRepaired.model_construct(
                kind="UnitRepaired",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                entity_id=e.id,
                by_id=None,
                node_id=node,
            )
        )


def _stall(world: World, e: Entity, node: str, out: list[Event]) -> None:
    was_stalled = e.stalled
    end_rearm(world, e, out)
    e.stalled = True
    if not was_stalled:
        out.append(
            RearmStalled.model_construct(
                kind="RearmStalled",
                tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id,
                entity_id=e.id,
                node_id=node,
            )
        )


def stop_problem(world: World, rules: Rules, cr: CombatRules, e: Entity) -> str | None:
    """What is wrong with `e`'s rearm state in a restored world, or None. Spend counters and the
    stall flag are flushed by the next `restock`, and `capture` runs after it in the same tick, so
    they may sit on an entity whose stop just ended (a bar over its base, a flipped base); they
    need only a node to report on. Repair progress exists only below max hp; the ammo credit stays
    under what one more round would need (below `n x lcm` once every round is back, else below
    the dearest round)."""
    if (e.rearm_spent or e.repair_spent or e.stalled) and (e.base_id or e.last_node) is None:
        return "rearm spend or stall with no node to report it at"
    if e.repair_milli and e.hp >= cr.units[e.kind].hp:
        return "repair progress at full hp"
    loadout = cr.loadout(e.kind, e.variant)
    price = ammo_price(rules, e)
    if not loadout or not price:
        return "an ammo credit without ammo to buy" if e.ammo_credit else None
    n, big = len(loadout), math.lcm(*(w.ammo for w in loadout))
    full = all(a == w.ammo for a, w in zip(e.ammo, loadout, strict=True))
    bound = n * big if full else max(n * big, price * big // min(w.ammo for w in loadout))
    return "ammo_credit above what the loadout can owe" if e.ammo_credit >= bound else None
