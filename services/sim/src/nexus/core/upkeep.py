"""Force economy, part 2: home bases, upkeep and grounding (NX-412; ECONOMY EC-4, EC-5, EC-6,
EC-10 step 3, EC-15).

Home base (EC-5, `Entity.home_base`): the node a unit spawned at (set by each spawn), then the
friendly node it last landed or parked at (the `logistics` system, by the rearm-stop rule
`rearm.station`). When the node is lost (`rehome`, from the capture flip), the home becomes the
nearest friendly node that can host the unit's domain (a landing base for an aircraft, any base but
a BRIDGE for a ground unit), by straight line from the unit, ties by node id.

Upkeep (EC-4, `upkeep`, at an economy window after income and the clip, before the Threat
Director): each live unit of a side not in unlimited mode pays `economy.upkeep.<kind>` whole stock
units from its home, in the EC-6 payment order: viewer (COMMANDER) units before AI units, then the
most recent order or spawn (`Entity.ordered`) first, then entity id. A home pays from
`World.stock`, or from the side's pool when it is the side's source, and only when it holds the
full amount and its side still owns it. The total each home paid is one `SupplyConsumed{UPKEEP}`
per window, in node id order. A kind with upkeep 0 always pays; a kind with no key (a facility)
and a unit with no home (only hand-built worlds; every spawn sets one) are not charged.

Grounded (EC-6): a unit whose home cannot pay is grounded, never deleted (`UnitGrounded`): it drops
its job claim, order and leader, an aircraft flies home and lands, a ground unit drives home and
parks; the board and the Director give it no job (`tasking_gen.is_idle`, `launch._spare`) and
REBASE refuses it (`UNIT_GROUNDED`). It still returns fire. It ungrounds (`UnitUngrounded`) at the
first window its home pays. shortcut: the spawn reply's "haul to <base>" warning (EC-6) is not
built: the sim has no spawn-reply path yet (the gateway's chat replies, NX-190); the events carry
what it needs.

Deterministic: entities in the sorted payment order, homes in id order, integers, no RNG; nothing
while paused (`economy.due`).
"""

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_grounded import UnitGrounded
from nexus.contracts.gen.events.unit_ungrounded import UnitUngrounded
from nexus.core.bridges import blocked
from nexus.core.economy import due
from nexus.core.logistics import friendly_bases, nearest_base, road_start
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.world import Entity, World, consumed, drop_claim, on_node


def rehome(world: World, node: str) -> None:
    """EC-5: each unit homed at `node`, which its side just lost, re-homes to the nearest friendly
    node that can host it; a grounded one heads there. With none (a side's sanctuary is never
    lost, so not in practice) it keeps the lost home, which cannot pay."""
    rules = world.rules
    if rules is None:
        return
    for e in world.entities():
        if e.home_base != node or world.owner.get(node) == e.side:
            continue
        air = rules.domain[e.kind] == "AIR"
        hosts = world.landing_bases(e.side) if air else tuple(friendly_bases(world, rules, e.side))
        if hosts:
            e.home_base = nearest_base(e, rules, hosts)[1]
            if e.grounded:
                _send_home(world, rules, e)


def upkeep(world: World, out: list[Event]) -> None:
    """EC-10 step 3 at an economy window (module docstring)."""
    if (ready := due(world)) is None:
        return
    rules, er = ready
    units = sorted(
        (e for e in world.entities()
         if e.side in er.limited and e.home_base is not None and e.kind in er.upkeep),
        key=lambda e: (e.owner_kind != "COMMANDER", -e.ordered, e.id),
    )  # fmt: skip
    paid: dict[str, int] = {}
    for e in units:
        home, cost = str(e.home_base), er.upkeep[e.kind]
        purse = _purse(world, rules, e, home)
        pays = cost == 0 or (purse is not None and purse >= cost)
        if pays and cost:
            _debit(world, rules, e, home, cost)
            paid[home] = paid.get(home, 0) + cost
        if pays and e.grounded:
            e.grounded = False
            out.append(_event(world, UnitUngrounded, "UnitUngrounded", e, home))
        elif not pays and not e.grounded:
            _ground(world, rules, e, out)
    for home in sorted(paid):
        out.append(consumed(world, home, paid[home], "UPKEEP"))


def owed(world: World, side: Side) -> int:
    """What `side`'s live units owe in upkeep per window, as `upkeep` charges it; 0 for a side in
    unlimited mode (EC-15). The EC-7 reserve reads it."""
    er = world.rules.economy if world.rules else None
    if er is None or side not in er.limited:
        return 0
    return sum(
        er.upkeep.get(e.kind, 0)
        for e in world.entities()
        if e.side == side and e.home_base is not None
    )


def _purse(world: World, rules: Rules, e: Entity, home: str) -> int | None:
    """What `home` can pay for `e`: the side's pool at its source, else the node's stock; None
    when the side no longer owns it or it holds no finite stock."""
    if world.owner.get(home) != e.side:
        return None
    if home == rules.supply.rear[e.side]:
        return world.pool[e.side]
    return world.stock.get(home)


def _debit(world: World, rules: Rules, e: Entity, home: str, cost: int) -> None:
    if home == rules.supply.rear[e.side]:
        world.pool[e.side] -= cost
    else:
        world.stock[home] -= cost


def _ground(world: World, rules: Rules, e: Entity, out: list[Event]) -> None:
    """EC-6: drop the claim, order and leader, head home; `UnitGrounded`."""
    drop_claim(world, e, out)
    e.order = e.order_node = e.held_since = e.follow_id = e.pickup = None
    e.grounded = True
    _send_home(world, rules, e)
    out.append(_event(world, UnitGrounded, "UnitGrounded", e, str(e.home_base)))


def _send_home(world: World, rules: Rules, e: Entity) -> None:
    """An aircraft flies to its home (RTB when airborne) and lands there; a ground unit takes the
    road route there from the node it heads for or stands at (`road_start`) and parks; with no
    route it only finishes its current leg (as an evicted claimant does, `tasking.claim`), never
    driving on to the target it dropped. A unit already there, or a facility, stays."""
    home = str(e.home_base)
    domain = rules.domain[e.kind]
    if domain == "AIR":
        if e.state == "LANDED" and e.last_node == home and not e.path:
            return
        e.path, e.orbit = [home], None
        if e.state in ("EN_ROUTE", "ON_STATION"):
            e.state = "RTB"
    elif domain == "GROUND":
        if not e.path and e.last_node == home and on_node(rules, e):
            return
        start = road_start(rules, e)
        route = (
            None
            if start is None
            else shortest_path(rules.roads, start, home, blocked=blocked(world))
        )
        e.path = list(route) if route is not None else e.path[:1]


def _event(
    world: World,
    model: type[UnitGrounded] | type[UnitUngrounded],
    kind: str,
    e: Entity,
    home: str,
) -> Event:
    return model.model_construct(
        kind=kind, tick=world.campaign.tick + 1, event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id, entity_id=e.id, node_id=home,
    )  # fmt: skip
