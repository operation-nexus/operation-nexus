"""Run metrics read from the event stream and the world (NX-031 part 1; TESTING-STRATEGY §3.5).

`Collector.feed(events)` after every tick, `observe(world)` after every step, `sample(world)` every
`sample_ticks`, `sample_idle(world)` every `idle_sample_ticks`, `check_impact(world)` every
`impact_check_ticks`. It only measures; `report.py` holds the targets and the pass/fail rules.
Nothing here is invented: a number with no data behind it is `None` or an empty list, never
a default.

Not measurable yet, and not produced: the kill-share Gini by rank (no ranks until PROGRESSION) and
the adversarial targets A5 and A6 (part 2, NX-321).
"""

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Final

from nexus.contracts.gen.events.event import Event
from nexus.core.campaign import momentum
from nexus.core.director import TIERS
from nexus.core.tasking import idle_reason
from nexus.core.tasking_gen import is_idle
from nexus.core.world import World

_ENEMY: Final = "ENEMY"  # Side values
_COALITION: Final = "COALITION"
# What counts as a newbie's impact (Q-SIM-93). A kill is also a hit, and a capture also fills a bar,
# in the same tick; the earlier in this tuple wins a same-tick tie. `capture` is the NodeCaptured
# event or, between those, a ground unit inside a coalition-filled bar's radius (derived from the
# world, no event names the capturers until it flips); `scout` is a new coalition track within the
# newbie's recon unit's sensor reach (derived: no event says who tracked what); `departure`
# (Q-SIM-97) is the first tick a newbie's truck holds cargo and a path: it loaded at its source and
# set off for a delivery (no event says so; `observe` reads the truck every tick, so it is exact).
IMPACT_KINDS = ("kill", "capture", "delivery", "departure", "scout", "hit")


class Collector:
    def __init__(
        self,
        world: World,
        newbies: frozenset[str],
        *,
        tick_hz: int,
        sample_ticks: int,
        a3_ticks: int,
        idle_sample_ticks: int,
        impact_check_ticks: int,
        kinds: Mapping[str, str],
        a2_min_tier: str,
    ) -> None:
        rules = world.rules
        if rules is None or rules.campaign is None:
            raise ValueError("the harness needs a world with campaign rules")
        self._world_rules = rules
        self._strategic = frozenset(rules.campaign.strategic)
        self._sanctuary = rules.sanctuary
        self.tick_hz, self.sample_ticks, self.a3_ticks = tick_hz, sample_ticks, a3_ticks
        self.idle_sample_ticks, self.impact_check_ticks = idle_sample_ticks, impact_check_ticks
        self.kinds = kinds  # commander -> persona kind (Q-SIM-95)
        self.min_tier = TIERS.index(a2_min_tier)
        self.known_tracks = set(world.contacts[_COALITION])  # ids the coalition has ever tracked
        self.idle_shares: list[float] = []  # idle armed viewer units / all, per sample
        self.idle_reasons: Counter[str] = Counter()  # why the idle ones hold no job, summed
        self.slots_per_unit: list[float] = []  # open job slots / live viewer units, per sample
        self.jobs_per_node: list[float] = []  # open coalition jobs / theater nodes, per sample
        self.newbies = newbies
        # entity id -> (unit kind, side), from the setup (garrison, facilities) and UnitSpawned
        self.entity = {e.id: (e.kind, e.side) for e in world.entities()}
        self.commander_of: dict[int, str] = {
            e.id: e.commander_id for e in world.entities() if e.commander_id
        }
        self.trucks: set[int] = set()  # newbies' trucks not yet seen loaded and under way
        self.join_tick: dict[str, int] = {}
        self.join_tier: dict[str, int] = {}  # the Static's tier index when the newbie first joined
        self.impact: dict[str, tuple[int, str]] = {}  # commander -> (tick, kind) of first impact
        self.ended: Any = None
        self.kills: Counter[str] = Counter()
        self.player_kills: Counter[str] = Counter()  # of those, by a commander-owned killer
        self.kills_unattributed = 0  # a coalition-side UnitDestroyed whose killer is unknown
        self.nodes_lost: list[tuple[int, str]] = []
        self.tier = world.director["ENEMY"].tier
        self.tier_since = world.campaign.tick
        self.dwell: Counter[str] = Counter()
        self.tier_changes = 0
        self.momentum: list[int] = []
        self.starved_any = 0
        self.starved_nodes = 0
        self.sanctuary_min = self.sanctuary_min_window = world.defense_hp[self._sanctuary]
        self._on: dict[str, Callable[[Any], None]] = {
            "UnitSpawned": self._spawned,
            "WeaponImpact": self._impact,
            "UnitDestroyed": self._destroyed,
            "SupplyDelivered": self._delivered,
            "NodeCaptured": self._captured,
            "ThreatTierChanged": self._tier,
            "CampaignEnded": self._end,
        }

    def note_join(self, commander: str, tick: int, tier: str) -> None:
        """A JOIN was sent: the first one is the start of a newbie's time-to-first-impact, and
        `tier` (the Static's, as the newbie arrives) says whether A2 counts it (Q-SIM-93)."""
        if commander not in self.join_tick:
            self.join_tick[commander] = tick
            self.join_tier[commander] = TIERS.index(tier)

    def check_impact(self, world: World) -> None:
        """The impact kinds no event names, read from the world without changing it (Q-SIM-93):
        capture progress and a new enemy track found by a newbie's recon unit."""
        tracks = {i: c for i, c in world.contacts[_COALITION].items() if c.age is None}
        new = {i: c for i, c in sorted(tracks.items()) if i not in self.known_tracks}
        self.known_tracks.update(world.contacts[_COALITION])
        pending = {c for c in self.newbies if c in self.join_tick and c not in self.impact}
        if not pending:
            return
        rules, tick = self._world_rules, world.campaign.tick
        units = [e for e in world.entities() if e.commander_id in pending]
        for e in units:
            for c in new.values():
                reach = rules.sensor_radius(e.kind, e.damage_state) * rules.stealth[c.kind]
                if (
                    e.kind in rules.painters
                    and math.dist((e.pos.x, e.pos.y), (c.pos.x, c.pos.y)) <= reach
                ):
                    self._credit(e.commander_id, tick, "scout")
        cap = rules.capture
        if cap is None:
            return
        for node, bar in sorted(world.capture.items()):
            if bar.side != _COALITION:
                continue
            x, y = rules.roads.pos[node]
            for e in units:
                if (
                    rules.domain[e.kind] == "GROUND"
                    and math.dist((e.pos.x, e.pos.y), (x, y)) <= cap.radius_m
                ):
                    self._credit(e.commander_id, tick, "capture")

    def feed(self, events: Iterable[Event]) -> None:
        for event in events:
            handler = self._on.get(event.kind)
            if handler:
                handler(event)

    def observe(self, world: World) -> None:
        for eid in sorted(self.trucks):  # a truck leaving its source loaded (Q-SIM-97)
            e = world.find(eid)
            if e is None:
                self.trucks.discard(eid)
            elif e.cargo and e.path:
                self.trucks.discard(eid)
                self._credit(e.commander_id, world.campaign.tick, "departure")
        hp = world.defense_hp[self._sanctuary]
        self.sanctuary_min = min(self.sanctuary_min, hp)
        if world.campaign.tick <= self.a3_ticks:
            self.sanctuary_min_window = min(self.sanctuary_min_window, hp)

    def sample(self, world: World) -> None:
        """Momentum and supply starvation, once per `sample_ticks` (a game minute by default)."""
        self.momentum.append(momentum(world).momentum_pct)
        floor, stock = self._world_rules.supply.starve_floor, world.stock
        starved = sum(
            1
            for n, owner in sorted(world.owner.items())
            if owner == _COALITION and n in stock and stock[n] < floor[n]
        )
        self.starved_nodes += starved
        self.starved_any += starved > 0

    def sample_idle(self, world: World) -> None:
        """The idle armed viewer-unit share (Q-SIM-92): commander-owned units of an armed kind, not
        Disabled, with no job, order or route; and `idle_reason` for each idle one. A sample with
        no such unit is skipped."""
        rules = self._world_rules
        armed = [
            e
            for e in world.entities()
            if e.owner_kind == "COMMANDER"
            and e.kind in rules.armed
            and e.damage_state != "DISABLED"
        ]
        if not armed:
            return
        idle = [e for e in armed if is_idle(rules, e, _COALITION)]
        self.idle_shares.append(len(idle) / len(armed))
        self.idle_reasons.update(idle_reason(world, e) for e in idle)

    def sample_density(self, world: World) -> None:
        """Job density on the coalition board. An open job has an unfilled slot; its unfilled slots
        are `slots - claims`. Slots per live (not Disabled) viewer unit skips a sample with no such
        unit."""
        open_jobs = [j for j in world.boards[_COALITION].values() if len(j.claims) < j.slots]
        self.jobs_per_node.append(len(open_jobs) / len(world.owner))
        units = sum(
            e.owner_kind == "COMMANDER" and e.damage_state != "DISABLED" for e in world.entities()
        )
        if units:
            self.slots_per_unit.append(sum(j.slots - len(j.claims) for j in open_jobs) / units)

    # --- event handlers ---------------------------------------------------------------------
    def _spawned(self, e: Any) -> None:
        self.entity[e.entity_id] = (e.unit_kind, e.side)
        if e.commander_id:
            self.commander_of[e.entity_id] = e.commander_id
            if e.commander_id in self.newbies and e.unit_kind in self._world_rules.supply.carriers:
                self.trucks.add(e.entity_id)

    def _credit(self, commander: str | None, tick: int, kind: str) -> None:
        if commander is None or commander not in self.newbies or commander not in self.join_tick:
            return
        first = self.impact.get(commander)
        if first is None or (
            tick == first[0] and IMPACT_KINDS.index(kind) < IMPACT_KINDS.index(first[1])
        ):
            self.impact[commander] = (tick, kind)

    def _impact(self, e: Any) -> None:
        if e.hit:
            self._credit(self.commander_of.get(e.shooter_id), e.tick, "hit")

    def _destroyed(self, e: Any) -> None:
        if e.side != _ENEMY:
            return
        if e.killer_id is None or e.killer_id not in self.entity:
            self.kills_unattributed += 1
            return
        kind, side = self.entity[e.killer_id]
        if side == _COALITION:
            self.kills[kind] += 1
            if e.killer_id in self.commander_of:
                self.player_kills[kind] += 1
            self._credit(self.commander_of.get(e.killer_id), e.tick, "kill")

    def _delivered(self, e: Any) -> None:
        self._credit(e.commander_id, e.tick, "delivery")

    def _captured(self, e: Any) -> None:
        for commander in e.participant_commander_ids:
            self._credit(commander, e.tick, "capture")
        if e.from_ == _COALITION and e.to != _COALITION and e.node_id in self._strategic:
            self.nodes_lost.append((e.tick, e.node_id))

    def _tier(self, e: Any) -> None:
        if e.side != _ENEMY:
            return
        self.dwell[self.tier] += e.tick - self.tier_since
        self.tier, self.tier_since = e.to, e.tick
        self.tier_changes += 1

    def _end(self, e: Any) -> None:
        self.ended = e

    # --- result -----------------------------------------------------------------------------
    def result(self, end_tick: int) -> dict[str, Any]:
        """Plain JSON data. `end_tick` is the last tick run (the campaign's end or the run's)."""
        s = float(self.tick_hz)
        dwell = Counter(self.dwell)
        dwell[self.tier] += end_tick - self.tier_since
        joined = sorted(c for c in self.newbies if c in self.join_tick)
        counted = [c for c in joined if self.join_tier[c] >= self.min_tier]
        total_kills = sum(self.kills.values())
        return {
            "outcome": self._outcome(end_tick),
            "momentum": {
                "sample_every_s": self.sample_ticks / s,
                "samples": self.momentum,
            },
            "newbie": {
                "joined": len(joined),
                "joined_below_tier": len(joined) - len(counted),
                # below-tier arrivals (Pattern of Life) are reported, never judged (Q-SIM-93)
                "below_tier_ttfi_s": self._ttfi(
                    [c for c in joined if self.join_tier[c] < self.min_tier]
                ),
                **self._group(counted, end_tick),
                "by_kind": {
                    k: self._group([c for c in counted if self.kinds[c] == k], end_tick)
                    for k in sorted({self.kinds[c] for c in counted})
                },
            },
            "kills": {
                "by_kind": dict(sorted(self.kills.items())),
                "player_by_kind": dict(sorted(self.player_kills.items())),
                "total": total_kills,
                "unattributed": self.kills_unattributed,
            },
            "nodes_lost": [{"tick": t, "node": n} for t, n in self.nodes_lost],
            "nodes_lost_in_a3_window": sum(t <= self.a3_ticks for t, _ in self.nodes_lost),
            "sanctuary_hp": {
                "min": self.sanctuary_min,
                "min_in_a3_window": self.sanctuary_min_window,
            },
            "director": {
                "tier_dwell_s": {k: v / s for k, v in sorted(dwell.items())},
                "tier_changes": self.tier_changes,
            },
            "idle": {
                "sample_every_s": self.idle_sample_ticks / s,
                "samples": len(self.idle_shares),
                "share_sum": sum(self.idle_shares),
                "share_max": max(self.idle_shares, default=None),
                "reasons": dict(sorted(self.idle_reasons.items())),
            },
            "density": {
                "slots_per_unit_samples": len(self.slots_per_unit),
                "slots_per_unit_sum": sum(self.slots_per_unit),
                "jobs_per_node_samples": len(self.jobs_per_node),
                "jobs_per_node_sum": sum(self.jobs_per_node),
            },
            "starvation": {
                "any_node_minutes": self.starved_any * self.sample_ticks / s / 60,
                "node_minutes": self.starved_nodes * self.sample_ticks / s / 60,
            },
        }

    def _ttfi(self, commanders: list[str]) -> list[float]:
        return sorted(
            (self.impact[c][0] - self.join_tick[c]) / self.tick_hz
            for c in commanders
            if c in self.impact
        )

    def _group(self, commanders: list[str], end_tick: int) -> dict[str, Any]:
        """A2's inputs for these newbies: joined, time to first impact, how long the rest were
        watched without one, and the first-impact kind breakdown."""
        return {
            "joined_counted": len(commanders),
            "ttfi_s": self._ttfi(commanders),
            "no_impact_observed_s": sorted(
                (end_tick - self.join_tick[c]) / self.tick_hz
                for c in commanders
                if c not in self.impact
            ),
            "first_impact_kinds": dict(
                sorted(Counter(self.impact[c][1] for c in commanders if c in self.impact).items())
            ),
        }

    def _outcome(self, end_tick: int) -> dict[str, Any]:
        e = self.ended
        return {
            "ended": e is not None,
            "result": e.result if e else None,
            "winner": e.winner if e else None,
            "end_tick": e.end_tick if e else None,
            "length_h": e.end_tick / (3600 * self.tick_hz) if e else None,
            "nodes_held_pct": e.nodes_held_pct if e else None,
            "ticks_run": end_tick,
        }
