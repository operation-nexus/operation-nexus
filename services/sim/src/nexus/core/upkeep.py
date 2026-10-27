"""Force economy, part 2: home bases, upkeep and grounding (NX-412, NX-426, NX-428; ECONOMY EC-4,
EC-5, EC-6, EC-10 step 3, EC-15).

Home base (EC-5, `Entity.home_base`): the node a unit spawned at (set by each spawn), then the
friendly node it last landed or parked at (the `logistics` system, by the rearm-stop rule
`rearm.station`). When the node is lost (`rehome`, from the capture flip), the home becomes the
nearest friendly node that can host the unit's domain (a landing base for an aircraft, any base but
a BRIDGE for a ground unit), by straight line from the unit, ties by node id.

Upkeep (EC-4, `upkeep`, at an economy window after income and the clip, before the Threat
Director): each live unit of a side not in unlimited mode pays `economy.upkeep.<kind>` whole stock
units from its home once every `economy.upkeep_period.<kind>` windows (NX-426, Q-TD-41, Q-TD-52
D1): in the window whose index (running ticks over the window length, the first window 1) plus its
entity id is a multiple of the period, so a kind's payments spread across windows by id, and every
window while it is grounded (a retry, back to its stagger once paid). The units charged this
window pay in the EC-6 payment order: viewer (COMMANDER) units before AI units (Q-TD-23);
within each class busy units before the rest (Q-TD-43, Q-TD-49, Q-TD-49c), busy meaning it holds
a claimed job (`Entity.job_id`) or follows an explicit order (`Entity.order`) that is under way: a
HOLD counts only while the unit travels, so a unit parked on HOLD is idle (`_busy`); then the most
recent order or spawn (`Entity.ordered`) first; then entity id. Each home pays from its own
purse, so a busy unit is grounded only when the units ahead of it at its home have used what the
home holds. A home pays from `World.stock`, or from the
side's pool when it is the side's source, and only when it holds the full amount and its side
still owns it. The total each home paid is one `SupplyConsumed{UPKEEP}` per window, in node id
order. A kind with upkeep 0 always pays; a kind with no key (a facility) and a unit with no home
(only hand-built worlds; every spawn sets one) are not charged.

Grounded (EC-6): a unit whose home cannot pay is grounded, never deleted (`UnitGrounded`): it drops
its job claim, order and leader, an aircraft flies home and lands, a ground unit drives home and
parks; the board and the Director give it no job (`tasking_gen.is_idle`, `launch._spare`). Its
one way out is REBASE (NX-435, Q-TD-51 U3) to a base that would pay it now (`pays_at`); REBASE to
any other base refuses it (`UNIT_GROUNDED`). The rebased unit stays grounded and takes the REBASE
hold; landing at the new base makes it its home (EC-5), so the next window charges it there (a
grounded unit is charged every window). It still returns fire. It ungrounds (`UnitUngrounded`) at
the first window its home pays. shortcut: the spawn reply's "haul to <base>" warning (EC-6) is not
built: the sim has no spawn-reply path yet (the gateway's chat replies, NX-190); the events carry
what it needs.

Shortfall sitreps (EC-6a, NX-436, Q-TD-51 U5, Q-TD-64; `_sitreps`, after the payments): a
shortfall episode of a side at a base is the run of consecutive windows in which at least one unit
of that side homed there is grounded (the NX-437 harness's episode, GLOSSARY). It is announced
once, never per unit, as `SupplyShortfall{STARTED, grounded}` ("<BASE> OUT OF SUPPLY: n flights
grounded. Haul to <BASE>"); for an ENEMY base n counts only the grounded units the coalition
spots (`fog.spotted`), 0 when it sees the base but none of them. When it closes because the
base paid a grounded unit again this window (a `UnitUngrounded` there), an announced episode
gets one `SupplyShortfall{ENDED}` crediting the carriers that unloaded into the base's stock
during it (`Shortfall.haulers`, set by `logistics`; the 32 lowest ids, COALITION only);
one that closes otherwise (its units destroyed or rehomed) ends silently.
An ENEMY base's episode is announced at the first window the coalition sees the
base (`fog.seen_at`) and closed with a payoff only if it sees it then too (FOW-13). Rate limit: an
episode starting `economy.shortfall_quiet_windows` windows or fewer after the base's last heard
one (announced or muted) ended (`World.shortfall_end`) is never announced (MUTED), so a chronic
shortfall stays quiet; an episode never announced because the base was unseen starts no gap.

Deterministic: entities in the sorted payment order, homes in id order, integers, no RNG; nothing
while paused (`economy.due`).
"""

import math

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.supply_shortfall import SupplyShortfall
from nexus.contracts.gen.events.unit_grounded import UnitGrounded
from nexus.contracts.gen.events.unit_ungrounded import UnitUngrounded
from nexus.core.bridges import blocked
from nexus.core.economy import due
from nexus.core.fog import seen_at, spotted
from nexus.core.logistics import friendly_bases, nearest_base, road_start
from nexus.core.roads import shortest_path
from nexus.core.rules import EconomyRules, Rules
from nexus.core.world import (
    SIDES,
    Entity,
    Shortfall,
    World,
    consumed,
    drop_claim,
    on_node,
)

_MAX_CREDITS = 32  # SupplyShortfall.credit_ids maxItems
_VIEWERS: Side = "COALITION"  # the side whose sensors gate a shortfall sitrep (FOW-13)


def rehome(world: World, node: str) -> None:
    """EC-5: each unit homed at `node`, which its side just lost, re-homes to the nearest friendly
    node that can host it; a grounded one heads there, unless it travels under a REBASE (an order
    with a path, NX-435), which keeps its target. With none (a side's sanctuary is never
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
            if e.grounded and not (e.order is not None and e.path):
                _send_home(world, rules, e)


def _busy(e: Entity) -> bool:
    """EC-6 (Q-TD-43, Q-TD-49c): a claimed job, or an explicit order under way. A HOLD counts only
    while the unit still travels to its node: a unit parked on HOLD is idle at home (a HOLD has no
    end of its own)."""
    return e.job_id is not None or (e.order is not None and (e.order != "HOLD" or bool(e.path)))


def upkeep(world: World, out: list[Event]) -> None:
    """EC-10 step 3 at an economy window (module docstring)."""
    if (ready := due(world)) is None:
        return
    rules, er = ready
    index = (world.campaign.running_ticks + 1) // er.window_ticks  # this window's, from 1
    units = sorted(
        (e for e in world.entities()
         if e.side in er.limited and e.home_base is not None and e.kind in er.upkeep
         and (e.grounded or (index + e.id) % er.upkeep_period[e.kind] == 0)),
        key=lambda e: (e.owner_kind != "COMMANDER", not _busy(e), -e.ordered, e.id),
    )  # fmt: skip
    paid: dict[str, int] = {}
    freed: set[tuple[Side, str]] = set()  # (side, home) that paid a grounded unit this window
    for e in units:
        home, cost = str(e.home_base), er.upkeep[e.kind]
        pays = _covers(world, rules, e, home, cost)
        if pays and cost:
            _debit(world, rules, e, home, cost)
            paid[home] = paid.get(home, 0) + cost
        if pays and e.grounded:
            e.grounded = False
            freed.add((e.side, home))
            out.append(_event(world, UnitUngrounded, "UnitUngrounded", e, home))
        elif not pays and not e.grounded:
            _ground(world, rules, e, out)
    for home in sorted(paid):
        out.append(consumed(world, home, paid[home], "UPKEEP"))
    _sitreps(world, rules, er, freed, out)


def _sitreps(
    world: World, rules: Rules, er: EconomyRules, freed: set[tuple[Side, str]], out: list[Event]
) -> None:
    """EC-6a (module docstring): close the episodes whose base grounds nobody now, then open and
    announce, sides in Side order, bases in id order."""
    now = world.campaign.running_ticks + 1
    grounded: dict[tuple[Side, str], int] = {}  # what the coalition may hear of: (side, base) -> n
    for e in world.entities():
        if e.grounded and e.home_base is not None:
            key = (e.side, e.home_base)  # an ENEMY unit counts only while spotted (FOW-13)
            grounded[key] = grounded.get(key, 0) + (e.side == _VIEWERS or spotted(world, e))
    for side in SIDES:
        episodes = world.shortfall[side]
        for node in sorted(n for n in episodes if (side, n) not in grounded):
            closed = episodes.pop(node)
            if closed.status != "PENDING":  # an unheard episode starts no quiet gap
                world.shortfall_end[side][node] = now
            if (closed.status == "ANNOUNCED" and (side, node) in freed
                    and _shown(world, rules, side, node)):  # fmt: skip
                credit = closed.haulers[:_MAX_CREDITS] if side == _VIEWERS else []
                out.append(_shortfall(world, side, node, "ENDED", 0, credit))
    for (side, node), n in sorted(grounded.items()):
        episode = world.shortfall[side].get(node)
        if episode is None:
            last = world.shortfall_end[side].get(node)
            quiet = last is not None and now - last <= er.shortfall_quiet_windows * er.window_ticks
            episode = world.shortfall[side][node] = Shortfall("MUTED" if quiet else "PENDING")
        if episode.status == "PENDING" and _shown(world, rules, side, node):
            episode.status = "ANNOUNCED"
            out.append(_shortfall(world, side, node, "STARTED", n, []))


def _shown(world: World, rules: Rules, side: Side, node: str) -> bool:
    """FOW-13: the coalition hears of its own bases, and of a Static base only while it sees it."""
    return side == _VIEWERS or seen_at(world, rules, side, node)


def _shortfall(
    world: World, side: Side, node: str, status: str, grounded: int, credit: list[int]
) -> Event:
    return SupplyShortfall.model_construct(
        kind="SupplyShortfall", tick=world.campaign.tick + 1, event_seq=world.next_event_seq(),
        campaign_id=world.campaign.id, side=side, node_id=node, status=status, grounded=grounded,
        credit_ids=credit,
    )  # fmt: skip


def owed(world: World, side: Side) -> int:
    """What `side`'s live units owe in upkeep per window on average (Q-TD-52 D1): the exact sum
    of each charged unit's `upkeep / upkeep_period` (`EconomyRules.rate`), rounded up once, so it
    never under-reserves and over-reserves by less than 1; 0 for a side in unlimited mode
    (EC-15). The EC-7 reserve reads it."""
    er = world.rules.economy if world.rules else None
    if er is None or side not in er.limited:
        return 0
    return math.ceil(
        sum(
            er.rate(e.kind) for e in world.entities()
            if e.side == side and e.home_base is not None and e.kind in er.upkeep
        )
    )  # fmt: skip


def pays_at(world: World, rules: Rules, e: Entity, node: str) -> bool:
    """NX-435 (Q-TD-51 U3): would `node` pay grounded `e`'s upkeep now, read as one payment:
    upkeep 0, or `node` is the side's and holds the full `economy.upkeep.<kind>` (`_purse`).
    Nothing is reserved: units due there before it are not deducted. REBASE reads it for a
    grounded unit's target; only a charged kind of a limited side grounds (`upkeep`), so `e`'s
    kind has a key. Pure."""
    return rules.economy is None or _covers(world, rules, e, node, rules.economy.upkeep[e.kind])


def _covers(world: World, rules: Rules, e: Entity, node: str, cost: int) -> bool:
    purse = _purse(world, rules, e, node)
    return cost == 0 or (purse is not None and purse >= cost)


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
