"""Run metrics read from the event stream and the world (NX-031 part 1; TESTING-STRATEGY §3.5).

`Collector.feed(events)` after every tick, `observe(world)` after every step, `sample(world)` every
`sample_ticks`, `sample_idle(world)` every `idle_sample_ticks`, `check_impact(world)` every
`impact_check_ticks`. It only measures; `report.py` holds the targets and the pass/fail rules.
Nothing here is invented: a number with no data behind it is `None` or an empty list, never
a default.

Not measurable yet, and not produced: the kill-share Gini by rank (no ranks until PROGRESSION) and
the adversarial targets A5 and A6 (part 2, NX-321).
"""

import itertools
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Final

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.events.event import Event
from nexus.core.campaign import momentum
from nexus.core.director import TIERS
from nexus.core.fog import side_view
from nexus.core.launch import NO_CAPTURE, no_capture_reason
from nexus.core.roads import shortest_path, travel_ticks
from nexus.core.rules import Rules
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
SIDES: Final[tuple[Side, ...]] = ("COALITION", "ENEMY")
# ECONOMY §4 "Harness report" (NX-412 part 5a): per side, per game hour (index = (tick - 1) // an
# hour's ticks): income (`SupplyProduced`), upkeep paid (`SupplyConsumed{UPKEEP}`) and groundings
# (`UnitGrounded`); `pool` and `grounded` (live grounded units) are read at the first sample of
# each new hour, `pool` None for a side in unlimited mode (no pool, EC-15).
ECON_SERIES = ("income", "upkeep", "groundings")
# The Pattern of Life job ids of `nexus.core.launch` (`_PATROL_OP`, `_CONVOY_OP`): routine work,
# not Director operations, so the operation counts leave them out (they stay in `by_id`).
# R11 (ENTERTAINMENT-upkeep Q2): a shortfall episode "follows enemy action" on its home's supply
# when the action came this many game minutes or fewer before the episode's first window.
ACTION_MINUTES: Final = 30
# R10: a coalition pool under 1/POOL_LOW_DIV of its storage cap (integer test) for more than
# POOL_LOW_MINUTES game minutes in a row.
POOL_LOW_DIV: Final = 10
POOL_LOW_MINUTES: Final = 30
ROUTINE_JOBS = frozenset({"POL_PATROL", "POL_CONVOY"})
OFFENSIVE = "OFFENSIVE"
RETAKE = "RETAKE"
FUNNEL_STEPS = ("strike_fired", "defenses_down", "capture_started", "captured")
CAPTURE_OPS = (OFFENSIVE, RETAKE)  # the operations with a STRIKE then a CAPTURE step (funnel)


def _add(series: list[int], index: int, n: int) -> None:
    series.extend([0] * (index + 1 - len(series)))
    series[index] += n


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
        # Q-TEST-11 inputs (steamroll.py). Ownership follows `NodeCaptured` from the setup's owners;
        # a pressure event is a Static capture start on a coalition node, a coalition
        # `NodeDefensesDown`, or a coalition node lost. The victory hold is derived (no event
        # names it): a run of the coalition holding `victory_node_frac` of the strategic nodes.
        self._owner = dict(world.owner)
        self.pressure_ticks: list[int] = []
        # The hold follows the sim's own `VictoryHoldStarted` / `VictoryHoldBroken` (ECONOMY EC-9;
        # one at setup arrives on tick 1). `holds`: per hold its start, end, whether it broke and
        # the Static operations launched during it.
        self.holds_broken = 0
        self.hold_start: int | None = None
        self.holds: list[dict[str, Any]] = []
        self.hour_ticks = 3600 * tick_hz
        self._source_side = {node: side for side, node in sorted(rules.supply.rear.items())}
        self.econ: dict[str, dict[str, list[int]]] = {
            s: {k: [] for k in ECON_SERIES} for s in SIDES
        }
        self.hourly: list[dict[str, dict[str, int | None]]] = []  # pool, grounded per side
        self.refused: dict[str, list[int]] = {}  # SpawnRefused operations per hour, by reason
        self.refused_units: Counter[str] = Counter()
        self.adapted: dict[str, list[int]] = {}  # ThreatAdaptation sitreps per hour, by category
        self._prev_state: dict[int, str] = {}  # armed viewer unit -> "job", "busy" or idle reason
        self.grounded_from: Counter[str] = Counter()  # newly grounded, by the previous state
        self.exposure: Counter[str] = Counter()  # units seen again after a sample in that state
        self._windows = world.director[_ENEMY].windows
        self.budget: list[int] = []  # the Static's planned window budgets, summed per hour
        self.budget_windows: list[int] = []  # its decision windows per hour
        self.spent: dict[str, list[int]] = {"base": [], "source": []}  # its SPAWN debits per hour
        # NX-452: per Static decision window, "launched" (a capture operation posted its jobs)
        # or the first reason none did (`nexus.core.launch.no_capture_reason`, NO_CAPTURE order)
        self.no_capture: Counter[str] = Counter()
        self._new_jobs: list[int] = []  # Static jobs created this tick (JobCreated)
        self.ops: list[tuple[int, str, str, bool]] = []  # (tick, operation, target, on coalition)
        self.ops_unseen = 0  # a created job already gone from the board when `observe` read it
        # D5 inputs (review ENTERTAINMENT-runs-F-G-H §8). `funnel`: per OFFENSIVE / RETAKE launch,
        # which steps its target saw afterwards; `_latest` maps a target to its newest launch.
        self.funnel: list[dict[str, Any]] = []
        self._latest: dict[str, dict[str, Any]] = {}
        self.tier0 = self.tier
        self.tier_log: list[tuple[int, str]] = []  # (tick, new tier) of the Static, in order
        self._debits = 0  # Static SPAWN debits since the last `observe`
        self.spawn_by_op: Counter[str] = Counter()
        self.spawn_shared = 0  # debits of a tick with several launches (not attributable)
        self.spawn_unattributed = 0  # debits of a tick with no launch seen
        self.army_peak = 0  # the most live armed coalition units in one sample
        self.static_units: list[int] = []  # live armed Static units, per `sample`
        self.static_stock: list[int] = []  # Static-held finite-stock bases' stock, per `sample`
        self.static_start_stock = self._static_stock(world)
        # Rare-shortfall metrics (NX-437; ENTERTAINMENT-upkeep Q2 R1-R4, R8, R10, R11). Read from
        # the world at each economy window (a tick where `running_ticks` crosses a multiple of
        # `economy.window_ticks`); counts only, never a commander id (ECONOMY §4, privacy).
        er = rules.economy
        self._wticks = er.window_ticks if er else 0
        self._widx = world.campaign.running_ticks // self._wticks if self._wticks else 0
        self.windows = 0
        self.unit_windows = {s: [0, 0] for s in SIDES}  # armed units, grounded ones, summed
        self.windows_viewer_grounded = 0  # R2
        self._open: dict[str, int] = {}  # home -> index in `episodes` of its running episode
        self.episodes: list[dict[str, Any]] = []  # R3: home, start tick, windows, R11 flag
        self.sitreps: Counter[str] = Counter()  # SupplyShortfall by "<side> <status>" (NX-436)
        self._grounded_cmdrs: set[str] = set()  # R4, kept inside; only the counts leave
        self._cmdrs: set[str] = set(self.commander_of.values())
        self._pool_low = 0  # R10: running low windows
        self.pool_low_stretches: list[int] = []  # closed qualifying stretches, in windows
        self._carriers: set[int] = {
            i
            for i, (k, sd) in self.entity.items()
            if k in rules.supply.carriers and sd == _COALITION
        }
        self._dest: dict[int, str] = {}  # a loaded coalition carrier -> the node it drives to
        self._action: dict[str, int] = {}  # node -> tick of the last enemy action on its supply
        self._bridge_cut: dict[str, int] = {}  # bridge node -> tick of its last BridgeDestroyed
        self._road_bridges: dict[str, frozenset[str]] = {}
        self._on: dict[str, Callable[[Any], None]] = {
            "UnitSpawned": self._spawned,
            "WeaponFired": self._fired,
            "WeaponImpact": self._impact,
            "UnitDestroyed": self._destroyed,
            "SupplyDelivered": self._delivered,
            "NodeCaptured": self._captured,
            "CaptureStarted": self._capture_started,
            "NodeDefensesDown": self._defenses_down,
            "ThreatTierChanged": self._tier,
            "CampaignEnded": self._end,
            "VictoryHoldStarted": self._hold_started,
            "VictoryHoldBroken": self._hold_broken,
            "SupplyProduced": self._produced,
            "SupplyConsumed": self._consumed,
            "UnitGrounded": self._grounded,
            "SpawnRefused": self._refused,
            "ThreatAdaptation": self._adapted,
            "SupplyShortfall": self._shortfall_sitrep,
            "JobCreated": self._job_created,
            "BridgeDestroyed": self._bridge_destroyed,
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
        for eid in sorted(self._carriers):  # where a loaded convoy is bound (R11 needs it at death)
            c = world.find(eid)
            if c is None:
                self._carriers.discard(eid)
            elif c.cargo and c.path and isinstance(c.path[-1], str):
                self._dest[eid] = c.path[-1]
            else:
                self._dest.pop(eid, None)  # unloaded or parked: no longer a convoy under way
        if self._wticks and world.campaign.running_ticks // self._wticks > self._widx:
            self._widx = world.campaign.running_ticks // self._wticks
            self._economy_window(world)
        captured = self._launches(world)
        state = world.director[_ENEMY]
        if state.windows != self._windows:  # a Static decision window ran this tick
            self._windows = state.windows
            self._window_capture(world, captured)
            hour = self._hour(world.campaign.tick)
            _add(self.budget, hour, state.budget)
            _add(self.budget_windows, hour, 1)
        hp = world.defense_hp[self._sanctuary]
        self.sanctuary_min = min(self.sanctuary_min, hp)
        if world.campaign.tick <= self.a3_ticks:
            self.sanctuary_min_window = min(self.sanctuary_min_window, hp)

    def _economy_window(self, world: World) -> None:
        """One economy window has run (upkeep included): R1/R8 unit shares, R2, R3/R11 episodes
        and R10 pool stretches. Counted in windows (ints); a window stands for `window_ticks`."""
        rules, tick = self._world_rules, world.campaign.tick
        self.windows += 1
        viewer_grounded = False
        homes: set[str] = set()
        for e in world.entities():
            if e.side == _COALITION and e.grounded and e.home_base:
                homes.add(e.home_base)  # R3 counts every grounded coalition unit, AI included
            if e.kind not in rules.armed or e.damage_state == "DISABLED":
                continue
            if e.side == _COALITION and e.owner_kind == "COMMANDER":
                self.unit_windows[_COALITION][0] += 1
                self.unit_windows[_COALITION][1] += e.grounded
                viewer_grounded |= e.grounded
            elif e.side == _ENEMY and e.owner_kind != "COMMANDER":
                self.unit_windows[_ENEMY][0] += 1
                self.unit_windows[_ENEMY][1] += e.grounded
        self.windows_viewer_grounded += viewer_grounded
        for home in sorted(homes):
            if home in self._open:
                self.episodes[self._open[home]]["windows"] += 1
            else:
                self._open[home] = len(self.episodes)
                after = self._after_action(home, tick)
                self.episodes.append(
                    {"home": home, "start": tick, "windows": 1, "after_action": after}
                )
        for home in sorted(set(self._open) - homes):
            del self._open[home]  # the episode ended: a window with nothing grounded at the home
        pool, cap = world.pool.get(_COALITION), world.storage.get(_COALITION)
        if pool is not None and cap is not None and pool * POOL_LOW_DIV < cap:
            self._pool_low += 1
        else:
            self._close_pool_stretch()

    def _long_stretch(self, windows: int) -> bool:
        return windows * self._wticks > POOL_LOW_MINUTES * 60 * self.tick_hz

    def _close_pool_stretch(self) -> None:
        if self._long_stretch(self._pool_low):
            self.pool_low_stretches.append(self._pool_low)
        self._pool_low = 0

    def _after_action(self, home: str, tick: int) -> bool:
        """R11: enemy action on `home`'s supply at most `ACTION_MINUTES` before `tick`: a loaded
        convoy bound for it killed by a Static unit, a bridge on its road from the coalition's
        source cut, or a Static capture started at it."""
        if home not in self._road_bridges:
            rules = self._world_rules
            path = shortest_path(
                rules.roads, rules.supply.rear[_COALITION], home, blocked=frozenset()
            )
            self._road_bridges[home] = frozenset(
                b
                for a, c in itertools.pairwise(path or [])
                if (b := rules.roads.edge(a, c).bridge) is not None
            )
        seen = [
            self._action.get(home),
            *(self._bridge_cut.get(b) for b in self._road_bridges[home]),
        ]
        limit = ACTION_MINUTES * 60 * self.tick_hz
        return any(t is not None and tick - t <= limit for t in seen)

    def sample(self, world: World) -> None:
        """Momentum and supply starvation, once per `sample_ticks` (a game minute by default)."""
        self.momentum.append(momentum(world).momentum_pct)
        rules = self._world_rules
        self.static_units.append(
            sum(
                e.side == _ENEMY and e.kind in rules.armed and e.damage_state != "DISABLED"
                for e in world.entities()
            )
        )
        self.static_stock.append(self._static_stock(world))
        self.army_peak = max(
            self.army_peak,
            sum(
                e.side == _COALITION and e.kind in rules.armed and e.damage_state != "DISABLED"
                for e in world.entities()
            ),
        )
        if world.campaign.tick // self.hour_ticks > len(self.hourly):  # first sample of an hour
            self.hourly.append(
                {
                    s: {
                        "pool": world.pool.get(s),
                        "grounded": sum(e.side == s and e.grounded for e in world.entities()),
                    }
                    for s in SIDES
                }
            )
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
        reasons = {e.id: idle_reason(world, e) for e in armed if is_idle(rules, e, _COALITION)}
        self.idle_shares.append(len(reasons) / len(armed))
        self.idle_reasons.update(reasons.values())
        self._grounding_by_state(armed, reasons)

    def _grounding_by_state(self, armed: list[Any], reasons: Mapping[int, str]) -> None:
        """Review ask (econ checkpoint §4.2): who upkeep grounds. Each armed viewer unit's state
        at the last sample ("job", "busy": an order, route or RTB, else its idle reason, so "full"
        is idle with only full jobs); a unit grounded now and not then counts for that state."""
        for e in armed:
            if e.id in self._prev_state:
                self.exposure[self._prev_state[e.id]] += 1
                if e.grounded:
                    self.grounded_from[self._prev_state[e.id]] += 1
        self._prev_state = {
            e.id: "job" if e.job_id is not None else reasons.get(e.id, "busy")
            for e in armed
            if not e.grounded
        }

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

    def _static_stock(self, world: World) -> int:
        return sum(
            world.stock.get(n, 0)
            for n in sorted(self._world_rules.supply.max_stock)
            if world.owner.get(n) == _ENEMY
        )

    def _hour(self, tick: int) -> int:
        return max(0, tick - 1) // self.hour_ticks

    def _window_capture(self, world: World, captured: bool) -> None:
        """NX-452: count the decision window that just ran as launched, or by why it launched
        no capture operation; the kernel helper only reads the world."""
        rules = self._world_rules
        if captured:
            self.no_capture["launched"] += 1
        elif rules.director is not None:
            view = side_view(world, _ENEMY)
            now = world.campaign.running_ticks  # the window's running tick, after its step
            self.no_capture[no_capture_reason(world, _ENEMY, view, rules, now)] += 1

    def _launches(self, world: World) -> bool:
        """The Static's operation launches this tick: its new jobs whose key is
        `op:<operation>:<target>:0...` (the first job of an operation), one per (operation,
        target). A catalog operation (not `ROUTINE_JOBS`) in a running hold counts for it. True
        when a capture operation (`CAPTURE_OPS`) launched."""
        board, tick = world.boards[_ENEMY], world.campaign.tick
        launched: set[tuple[str, str]] = set()
        for jid in self._new_jobs:
            job = board.get(jid)
            if job is None:
                self.ops_unseen += 1
                continue
            parts = job.key.split(":")
            if parts[0] == "op" and len(parts) >= 4 and parts[3] == "0":
                launched.add((parts[1], parts[2]))
        self._new_jobs = []
        debits, self._debits = self._debits, 0
        if debits and len(launched) == 1:
            self.spawn_by_op[next(iter(launched))[0]] += debits
        elif launched:
            self.spawn_shared += debits
        else:
            self.spawn_unattributed += debits
        for op, target in sorted(launched):
            self.ops.append((tick, op, target, self._owner.get(target) == _COALITION))
            if op in CAPTURE_OPS:
                step: dict[str, Any] = {"tick": tick, "op": op, "target": target}
                step.update(dict.fromkeys(FUNNEL_STEPS, False))
                self.funnel.append(step)
                self._latest[target] = step
            if op not in ROUTINE_JOBS and self.hold_start is not None and self.holds:
                self.holds[-1]["ops"] += 1
        return any(op in CAPTURE_OPS for op, _ in launched)

    def _side_of(self, node: str) -> str | None:
        return self._source_side.get(node) or self._owner.get(node)

    # --- event handlers ---------------------------------------------------------------------
    def _spawned(self, e: Any) -> None:
        self.entity[e.entity_id] = (e.unit_kind, e.side)
        if e.side == _COALITION and e.unit_kind in self._world_rules.supply.carriers:
            self._carriers.add(e.entity_id)
        if e.commander_id:
            self.commander_of[e.entity_id] = e.commander_id
            self._cmdrs.add(e.commander_id)
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
        dest = self._dest.pop(e.entity_id, None)
        killer_side = self.entity.get(e.killer_id, (None, None))[1]
        if dest and e.side == _COALITION and killer_side == _ENEMY:
            self._action[dest] = e.tick  # R11: a loaded convoy lost on its way to `dest`
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

    def _fired(self, e: Any) -> None:
        """A Static shot at a node's defenses: the newest capture operation on it got its strike."""
        step = self._latest.get(e.target_node_id) if e.target_node_id else None
        if step and self.entity.get(e.shooter_id, (None, None))[1] == _ENEMY:
            step["strike_fired"] = True

    def _captured(self, e: Any) -> None:
        if (step := self._latest.pop(e.node_id, None)) and e.to == _ENEMY:
            step["captured"] = True
        for commander in e.participant_commander_ids:
            self._credit(commander, e.tick, "capture")
        if e.from_ == _COALITION and e.to != _COALITION:
            self.pressure_ticks.append(e.tick)
            if e.node_id in self._strategic:
                self.nodes_lost.append((e.tick, e.node_id))
        self._owner[e.node_id] = e.to

    def _hold_started(self, e: Any) -> None:
        self.hold_start = e.tick
        self.holds.append({"start": e.tick, "end": None, "broken": False, "ops": 0})

    def _hold_broken(self, e: Any) -> None:
        self.holds_broken += 1
        self.hold_start = None
        if self.holds:
            self.holds[-1].update(end=e.tick, broken=True)

    def _produced(self, e: Any) -> None:
        _add(self.econ[e.side]["income"], self._hour(e.tick), e.amount)

    def _consumed(self, e: Any) -> None:
        side = self._side_of(e.node_id)
        if e.cause == "UPKEEP" and side in self.econ:
            _add(self.econ[side]["upkeep"], self._hour(e.tick), e.amount)
        elif e.cause == "SPAWN" and side == _ENEMY:
            account = "source" if e.node_id in self._source_side else "base"
            self._debits += e.amount
            _add(self.spent[account], self._hour(e.tick), e.amount)

    def _bridge_destroyed(self, e: Any) -> None:
        self._bridge_cut[e.node_id] = e.tick

    def _grounded(self, e: Any) -> None:
        if cmdr := self.commander_of.get(e.entity_id):
            self._grounded_cmdrs.add(cmdr)
        side = self.entity.get(e.entity_id, (None, None))[1]
        if side in self.econ:
            _add(self.econ[side]["groundings"], self._hour(e.tick), 1)

    def _refused(self, e: Any) -> None:
        _add(self.refused.setdefault(e.reason, []), self._hour(e.tick), e.operations)
        self.refused_units[e.reason] += e.units

    def _adapted(self, e: Any) -> None:
        if e.side == _ENEMY:
            _add(self.adapted.setdefault(e.category, []), self._hour(e.tick), 1)

    def _shortfall_sitrep(self, e: Any) -> None:
        self.sitreps[f"{e.side} {e.status}"] += 1

    def _job_created(self, e: Any) -> None:
        if e.side == _ENEMY:
            self._new_jobs.append(e.job_id)

    def _capture_started(self, e: Any) -> None:
        if e.side == _ENEMY:
            self._action[e.node_id] = e.tick  # R11: the home contested
        if e.side == _ENEMY and self._owner.get(e.node_id) == _COALITION:
            self.pressure_ticks.append(e.tick)
            if step := self._latest.get(e.node_id):
                step["capture_started"] = True

    def _defenses_down(self, e: Any) -> None:
        if e.owner == _COALITION:
            self.pressure_ticks.append(e.tick)
            if step := self._latest.get(e.node_id):
                step["defenses_down"] = True

    def _tier(self, e: Any) -> None:
        if e.side != _ENEMY:
            return
        self.dwell[self.tier] += e.tick - self.tier_since
        self.tier, self.tier_since = e.to, e.tick
        self.tier_log.append((e.tick, e.to))
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
            "steamroll": {
                "pressure_ticks": self.pressure_ticks,
                "hold_start": self.hold_start,
                "holds_broken": self.holds_broken,
                "sample_ticks": self.sample_ticks,
                "static": {
                    "units": self.static_units,
                    "stock": self.static_stock,
                    "start_stock": self.static_start_stock,
                },
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
            "economy": self._economy(),
        }

    def _economy(self) -> dict[str, Any]:
        """ECONOMY §4 "Harness report" inputs (NX-412 part 5a); per-hour lists are indexed by game
        hour and may be shorter than the run where nothing happened late."""
        return {
            "sides": self.econ,
            "hourly": self.hourly,
            "refused": {"operations_per_hour": self.refused, "units": dict(self.refused_units)},
            "adapted": dict(sorted(self.adapted.items())),  # STAGING: forward staging (NX-416)
            "grounded_from": dict(sorted(self.grounded_from.items())),
            "exposure": dict(sorted(self.exposure.items())),
            "budget": {"sum": self.budget, "windows": self.budget_windows, "spent": self.spent},
            "ops": [list(o) for o in self.ops],
            "ops_unseen": self.ops_unseen,
            "holds": [{**h, "pressure": self._pressure_in(h)} for h in self.holds],
            "funnel": self.funnel,
            "no_capture": {k: self.no_capture[k] for k in ("launched", *NO_CAPTURE)},
            "tiers": {"start": self.tier0, "changes": [list(c) for c in self.tier_log]},
            "spawn_by_op": {
                "ops": dict(sorted(self.spawn_by_op.items())),
                "shared": self.spawn_shared,
                "unattributed": self.spawn_unattributed,
            },
            "army_peak": self.army_peak,
            "shortfall": self._shortfall(),
        }

    def _shortfall(self) -> dict[str, Any]:
        """Raw counts for R1-R4, R8, R10, R11 (the report forms the shares). An episode or a pool
        stretch still running at the end counts, with the windows so far."""
        low = [self._pool_low] if self._long_stretch(self._pool_low) else []
        stretches = [*self.pool_low_stretches, *low]
        return {
            "window_ticks": self._wticks,
            "windows": self.windows,
            "unit_windows": {
                s: {"units": u, "grounded": g} for s, (u, g) in self.unit_windows.items()
            },
            "windows_viewer_grounded": self.windows_viewer_grounded,
            "episodes": [dict(x) for x in self.episodes],
            "sitreps": dict(sorted(self.sitreps.items())),
            "viewers": len(self._cmdrs),
            "viewers_grounded": len(self._grounded_cmdrs),
            "pool_low": {
                "stretches": len(stretches),
                "minutes": sum(stretches) * self._wticks / self.tick_hz / 60,
            },
        }

    def _pressure_in(self, hold: dict[str, Any]) -> int:
        """Pressure events from a hold's start to its end, both ticks counted."""
        end = hold["end"]
        return sum(hold["start"] <= t and (end is None or t <= end) for t in self.pressure_ticks)

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


def travel_table(rules: Rules, tick_hz: int) -> list[dict[str, Any]]:
    """Review ask (econ checkpoint §4.1, S1 and S2): for each victory-relevant (strategic) node and
    each unit kind a Static capture job buys, the shortest road travel time from the Static's rear
    source, against `campaign.victory_hold_min`. Pure: the theater's road graph with every bridge
    up and no node avoided, the kind's top (Healthy) speed and each road's `speed_mult`; staging,
    spawning, fuel and combat are left out, so a real arrival is later. Times are game minutes
    (campaign clock: world time / `sim.time_scale`). A node no road reaches has `minutes` None."""
    rc, dr = rules.campaign, rules.director
    rear = rules.supply.rear.get(_ENEMY)
    if rc is None or dr is None or rear is None:
        return []
    kinds = sorted(
        {k for op in dr.operations for j in op.jobs if j.kind == "CAPTURE" for k in j.unit_kinds}
    )
    hold_min = rc.victory_hold_ticks / tick_hz / 60
    rows = []
    for node in rc.strategic:
        path = shortest_path(rules.roads, rear, node, blocked=frozenset())
        for kind in kinds:
            ticks = travel_ticks(
                rules.roads, rear, node, rules.speed_mps[kind], rules.world_dt, blocked=frozenset()
            )  # the kernel's own rule (THREAT-DIRECTOR FS-1)
            minutes = None if ticks is None else ticks / tick_hz / 60
            rows.append(
                {
                    "node": node,
                    "kind": kind,
                    "road_km": None if path is None else _path_km(rules, path),
                    "minutes": minutes,
                    "hold_min": hold_min,
                    "within_hold": None if ticks is None else ticks <= rc.victory_hold_ticks,
                }
            )
    return rows


def _path_km(rules: Rules, path: list[str]) -> float:
    return sum(rules.roads.edge(a, b).length_m for a, b in itertools.pairwise(path)) / 1000
