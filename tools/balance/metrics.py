"""Run metrics read from the event stream and the world (NX-031 part 1; TESTING-STRATEGY §3.5).

`Collector.feed(events)` after every tick, `observe(world)` after every step, `sample(world)` every
`sample_ticks`. It only measures; `report.py` holds the targets and the pass/fail rules. Nothing
here is invented: a number with no data behind it is `None` or an empty list, never a default.

Not measurable yet, and not produced: the kill-share Gini by rank (no ranks until PROGRESSION) and
the adversarial targets A5 and A6 (part 2, NX-321).
"""

from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from nexus.contracts.gen.events.event import Event
from nexus.core.campaign import momentum
from nexus.core.world import World

_ENEMY, _COALITION = "ENEMY", "COALITION"  # Side values


class Collector:
    def __init__(
        self,
        world: World,
        newbies: frozenset[str],
        *,
        tick_hz: int,
        sample_ticks: int,
        a3_ticks: int,
    ) -> None:
        rules = world.rules
        if rules is None or rules.campaign is None:
            raise ValueError("the harness needs a world with campaign rules")
        self._world_rules = rules
        self._strategic = frozenset(rules.campaign.strategic)
        self._sanctuary = rules.sanctuary
        self.tick_hz, self.sample_ticks, self.a3_ticks = tick_hz, sample_ticks, a3_ticks
        self.newbies = newbies
        # entity id -> (unit kind, side), from the setup (garrison, facilities) and UnitSpawned
        self.entity = {e.id: (e.kind, e.side) for e in world.entities()}
        self.commander_of: dict[int, str] = {
            e.id: e.commander_id for e in world.entities() if e.commander_id
        }
        self.join_tick: dict[str, int] = {}
        self.impact_tick: dict[str, int] = {}
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

    def note_join(self, commander: str, tick: int) -> None:
        """A JOIN was sent: the first one is the start of a newbie's time-to-first-impact."""
        self.join_tick.setdefault(commander, tick)

    def feed(self, events: Iterable[Event]) -> None:
        for event in events:
            handler = self._on.get(event.kind)
            if handler:
                handler(event)

    def observe(self, world: World) -> None:
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

    # --- event handlers ---------------------------------------------------------------------
    def _spawned(self, e: Any) -> None:
        self.entity[e.entity_id] = (e.unit_kind, e.side)
        if e.commander_id:
            self.commander_of[e.entity_id] = e.commander_id

    def _credit(self, commander: str | None, tick: int) -> None:
        if commander is not None and commander in self.newbies and commander in self.join_tick:
            self.impact_tick.setdefault(commander, tick)

    def _impact(self, e: Any) -> None:
        if e.hit:
            self._credit(self.commander_of.get(e.shooter_id), e.tick)

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
            self._credit(self.commander_of.get(e.killer_id), e.tick)

    def _delivered(self, e: Any) -> None:
        self._credit(e.commander_id, e.tick)

    def _captured(self, e: Any) -> None:
        for commander in e.participant_commander_ids:
            self._credit(commander, e.tick)
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
        total_kills = sum(self.kills.values())
        return {
            "outcome": self._outcome(end_tick),
            "momentum": {
                "sample_every_s": self.sample_ticks / s,
                "samples": self.momentum,
            },
            "newbie": {
                "joined": len(joined),
                "ttfi_s": sorted(
                    (self.impact_tick[c] - self.join_tick[c]) / s
                    for c in joined
                    if c in self.impact_tick
                ),
                "no_impact_observed_s": sorted(
                    (end_tick - self.join_tick[c]) / s for c in joined if c not in self.impact_tick
                ),
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
            "starvation": {
                "any_node_minutes": self.starved_any * self.sample_ticks / s / 60,
                "node_minutes": self.starved_nodes * self.sample_ticks / s / 60,
            },
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
