"""Human-led AI wingmen (GAMEPLAY §1b items 239-255, NX-511; Q-GP-50, Q-GP-51; Q-DEV-46).

1. **Spawn** (`on_claim`, called by `tasking.claim`, so a board pass and a parameterless JOIN
   alike): a COMMANDER-owned coalition armed aircraft of a kind the AI garrison may fly
   (`TaskingRules.wingmen_kinds`) that claims a STRIKE job while LANDED on a coalition landing
   base, whose commander sent a chat command within `tasking.wingmen_lead_active_min`
   (`World.last_command`) and has no wingmen cooldown, gets k AI_GARRISON wingmen of its kind at
   that base: k is the largest number within `fade(wingmen_max)`, the faded theater cap
   `fade(wingmen_max_live)` less the live wingmen, the EC-8 guard and what the base can pay in
   whole `logistics.loadout_cost` above its starvation floor (EC-13; never free). Each follows the
   lead (FOLLOW order) and holds no claim. A refused or short flight is silent (item 255.6).
2. **Each running tick** (`run`, the `director` slot before the board): a wingman sent home for
   its own reason (RTB, or no longer following the lead) leaves the flight for good; the flight
   ends when the lead is gone or Disabled or no longer holds the claim. At the end a lost wingman
   (destroyed or Disabled) with no impact, or no wingman ever airborne, starts the commander's
   `tasking.wingmen_cooldown_min`; the rest go home (`logistics.go_home`). A wingman out of a
   flight is removed on landing at a coalition landing base, `UnitDespawned{RETIRED}`. No refund.
3. **Impact** (`note_hit` from `combat`, `on_done` from `tasking`): a hit by any member, or the
   job DONE (TESTING-STRATEGY A2's striker test).

Deterministic: integers, leads in id order, ids from `World.spawn`, no RNG. Nothing is read or
written without a flight, a wingman going home or a qualifying claim, so a world with no viewer
unit is untouched (item 249).
"""

from bisect import insort

from nexus.contracts.gen.common.enums import OwnerKind, Side
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.economy import guard_room, source_stock
from nexus.core.logistics import at_own_base, go_home, pay_spawn
from nexus.core.rules import Rules, TaskingRules
from nexus.core.world import Entity, Flight, Job, UnitState, Vec2, World, on_node

_SIDE: Side = "COALITION"
_AI: OwnerKind = "AI_GARRISON"
_DISABLED = "DISABLED"
_LANDED: UnitState = "LANDED"


def fade(cap: int, viewers: int, quiet_ref: int) -> int:
    """⌈cap x (q - min(v, q)) / q⌉ in integers (item 241)."""
    return -(-cap * (quiet_ref - min(viewers, quiet_ref)) // quiet_ref)


def _tasking(world: World) -> tuple[Rules, TaskingRules] | None:
    rules = world.rules
    if rules is None or rules.tasking is None or rules.capture is None:
        return None
    return rules, rules.tasking


def _live(world: World, ids: list[int]) -> list[Entity]:
    return [e for i in ids if (e := world.find(i)) is not None]


def _qualifies(world: World, rules: Rules, tr: TaskingRules, lead: Entity, job: Job) -> bool:
    """Item 240: a viewer's landed armed aircraft on a STRIKE claim, its commander active and not
    cooling down."""
    cid = lead.commander_id
    if cid is None or job.kind != "STRIKE" or lead.side != _SIDE or lead.owner_kind != "COMMANDER":
        return False
    last = world.last_command.get(cid)
    now = world.campaign.running_ticks
    return (
        lead.kind in tr.wingmen_kinds and rules.domain[lead.kind] == "AIR" and any(lead.ammo)
        and lead.state == _LANDED and lead.last_node in world.landing_bases(_SIDE)
        and on_node(rules, lead)
        and last is not None and now - last < tr.wingmen_lead_active_ticks
        and world.wingmen_cooldown.get(cid, 0) <= now + 1
    )  # fmt: skip


def _affordable(world: World, rules: Rules, lead: Entity, node: str, want: int) -> int:
    """Whole loadouts the node can pay above its starvation floor (EC-13, GP-7), at most `want`."""
    cost = rules.supply.loadout_cost.get(lead.kind, 0)
    have = source_stock(world, node)  # None: an infinite source
    if cost <= 0 or have is None:
        return want
    return min(want, max(0, have - rules.supply.starve_floor.get(node, 0)) // cost)


def on_claim(world: World, lead: Entity, job: Job, out: list[Event]) -> None:
    """Spawn `lead`'s flight for its new claim on `job` (module docstring, 1)."""
    found = _tasking(world)
    if found is None or not found[1].wingmen_max:
        return
    rules, tr = found
    if lead.id in world.flights:
        _end(world, rules, tr, lead.id)  # one flight per claim (item 240)
    if rules.capture is None or not _qualifies(world, rules, tr, lead, job):
        return
    node = str(lead.last_node)
    v, q = world.viewer_units(), rules.capture.quiet_ref
    live = sum(len(_live(world, f.wingmen)) for f in world.flights.values())
    live += len(_live(world, world.wingmen_home))
    want = min(fade(tr.wingmen_max, v, q), fade(tr.wingmen_max_live, v, q) - live)
    k = _affordable(world, rules, lead, node, min(want, guard_room(world, _SIDE)))
    if k <= 0:
        return
    cost = rules.supply.loadout_cost.get(lead.kind, 0)
    ids = []
    for _ in range(k):
        w = world.spawn(lead.kind, _SIDE, _AI, Vec2(*rules.roads.pos[node]))
        w.last_node = w.home_base = node  # its base pays its upkeep (EC-5)
        w.state, w.fuel = _LANDED, rules.fuel_s[w.kind]
        w.order, w.follow_id = "FOLLOW", lead.id
        pay_spawn(world, node, cost, out)
        out.append(
            UnitSpawned.model_construct(
                kind="UnitSpawned", tick=world.campaign.tick + 1, event_seq=world.next_event_seq(),
                campaign_id=world.campaign.id, entity_id=w.id, unit_kind=w.kind, side=_SIDE,
                owner_kind=_AI, commander_id=None, callsign=None, node_id=node, loadout="FULL",
            )
        )  # fmt: skip
        ids.append(w.id)
    world.flights[lead.id] = Flight(job.id, str(lead.commander_id), ids)


def run(world: World, out: list[Event]) -> None:
    """The per-tick pass (module docstring, 2)."""
    if world.frozen or not (world.flights or world.wingmen_home):
        return
    found = _tasking(world)
    if found is None:
        return
    rules, tr = found
    for lead_id in sorted(world.flights):
        flight = world.flights[lead_id]
        for w in _live(world, flight.wingmen):
            if w.damage_state == _DISABLED:
                continue
            flight.flown |= w.state != _LANDED
            if w.follow_id != lead_id or w.state == "RTB":  # sent home: out for good (item 245)
                flight.wingmen.remove(w.id)
                _send_home(world, rules, w)
        lead = world.find(lead_id)
        job = world.boards[_SIDE].get(flight.job)
        if (
            lead is None
            or lead.damage_state == _DISABLED
            or job is None
            or lead_id not in job.claims
        ):
            _end(world, rules, tr, lead_id)
    _retire(world, rules, out)


def _end(world: World, rules: Rules, tr: TaskingRules, lead_id: int) -> None:
    """The flight ends (item 245); the cooldown (item 248)."""
    flight = world.flights.pop(lead_id)
    alive = [w for w in _live(world, flight.wingmen) if w.damage_state != _DISABLED]
    lost = len(alive) < len(flight.wingmen)
    if not flight.impact and (lost or not flight.flown) and tr.wingmen_cooldown_ticks:
        until = world.campaign.running_ticks + 1 + tr.wingmen_cooldown_ticks
        world.wingmen_cooldown[flight.commander] = until
    for w in alive:
        _send_home(world, rules, w)


def _send_home(world: World, rules: Rules, w: Entity) -> None:
    go_home(world, rules, w)  # stops following; airborne, RTB to the nearest landing base
    insort(world.wingmen_home, w.id)


def _retire(world: World, rules: Rules, out: list[Event]) -> None:
    """A wingman out of a flight is removed on landing at a base of its side (Q-TD-141)."""
    keep = []
    for w in _live(world, world.wingmen_home):
        if w.damage_state == _DISABLED:
            continue  # a wreck: removed as one (CB-7)
        if not at_own_base(world, rules, w):
            keep.append(w.id)
            continue
        world.remove(w.id)
        out.append(
            UnitDespawned.model_construct(
                kind="UnitDespawned", tick=world.campaign.tick + 1,
                event_seq=world.next_event_seq(), campaign_id=world.campaign.id,
                entity_id=w.id, reason="RETIRED",
            )
        )  # fmt: skip
    world.wingmen_home = keep


def prune(world: World) -> None:
    """At each board pass (`tasking.run`): drop chat-command ticks past the active-lead window
    and cooldowns that ended (item 240)."""
    found = _tasking(world)
    if found is None:
        return
    window, ran = found[1].wingmen_lead_active_ticks, world.campaign.running_ticks
    if world.last_command:
        world.last_command = {c: t for c, t in world.last_command.items() if ran - t < window}
    if world.wingmen_cooldown:
        world.wingmen_cooldown = {c: u for c, u in world.wingmen_cooldown.items() if u > ran + 1}


def lead_job(world: World, e: Entity) -> Job | None:
    """The STRIKE job of the lead whose flight `e` flies in (item 244), else None."""
    flight = None if e.follow_id is None else world.flights.get(e.follow_id)
    if flight is None or e.id not in flight.wingmen:
        return None
    return world.boards[e.side].get(flight.job)


def note_hit(world: World, shooter_id: int) -> None:
    """A hit by a flight member (lead or wingman) is the flight's impact (item 248)."""
    for lead_id, flight in world.flights.items():
        if shooter_id == lead_id or shooter_id in flight.wingmen:
            flight.impact = True


def on_done(world: World, job_id: int) -> None:
    """A DONE job is impact for the flights that fly it (item 248)."""
    for flight in world.flights.values():
        if flight.job == job_id:
            flight.impact = True
