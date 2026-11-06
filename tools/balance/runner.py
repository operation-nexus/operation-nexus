"""One balance run (NX-031 part 1, Q-SIM-91): a campaign from the shipped config, stepped through
the ordinary command path (`step` with the production `HANDLERS`) while scripted viewers send JOIN
and REBASE. Every command is appended to a command log in the format tools/replay reads (before the
tick that applies it, as the runtime does), so `replay_log` rebuilds the run from the log alone.

The harness has its own seeded RNGs (profiles.schedule, personas.new_viewer); the sim's streams are
only ever used by the sim. Runs as fast as the CPU allows; nothing here reads a clock except the
wall-time stamp in `timing`.
"""

import hashlib
import heapq
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import personas as ps
import profiles
from metrics import Collector
from orders import Orders

from nexus.contracts.gen.commands.command import Command
from nexus.core.fog import side_view
from nexus.core.step import HANDLERS, step
from nexus.core.world import World, state_hash
from nexus.runtime.campaign_config import CampaignConfig, load_campaign_config, start_campaign
from nexus.runtime.command_log import CommandLogReader, CommandLogWriter, Tombstone

PROTOCOL = "0.2"  # the command log's protocol_version (same as the runtime tests)
FLUSH_TICKS = 600
AGENCY_RULES = ("retake", "capture_started", "defenses_down", "fallback")  # NX-321 pick counters


def campaign_id(profile: str, seed: int) -> str:
    """A deterministic UUIDv7-shaped campaign id per (profile, seed)."""
    h = hashlib.blake2b(f"{profile}/{seed}".encode(), digest_size=16).hexdigest()
    return f"{h[:8]}-{h[8:12]}-7{h[13:16]}-8{h[17:20]}-{h[20:32]}"


def defended_foes(world: World) -> list[str]:
    """Foe-held nodes with defense HP in the coalition's view (public state, FOW-10), sorted."""
    view = side_view(world, "COALITION")
    return [n for n, o in sorted(view.owners.items()) if o == "ENEMY" and view.defense_hp.get(n, 0)]


def capturable_foes(world: World) -> list[str]:
    """Foe-held, capturable nodes whose defense HP is 0 in the coalition's view, sorted: where a
    capture run (JOIN LOGI with a node, Q-GP-24) can start a bar. Uncapturable kinds (the rear
    SANCTUARY, BRIDGE) never count."""
    rules = world.rules
    if rules is None:
        raise ValueError("capturable_foes needs the world's rules")
    view = side_view(world, "COALITION")
    return [
        n
        for n, o in sorted(view.owners.items())
        if o == "ENEMY"
        and not view.defense_hp.get(n, 0)
        and rules.node_kind.get(n) not in rules.uncapturable
    ]


def forward_base(world: World) -> str | None:
    """The most forward (eastmost) landing base the coalition owns, the sanctuary aside."""
    rules = world.rules
    if rules is None:
        raise ValueError("forward_base needs the world's rules")
    bases = [n for n in world.landing_bases("COALITION") if n != rules.sanctuary]
    return max(bases, key=lambda n: (rules.roads.pos[n][0], n), default=None)


class _Crowd:
    """The viewers, their wake-ups and what they make of the events."""

    def __init__(
        self, sched: list[tuple[int, str]], data: profiles.Data, profile: str, seed: int, hz: int
    ):
        self.data = data
        prof = data.profiles[profile]
        self.viewers = []
        for i, (_, persona) in enumerate(sched):
            kind = ps.draw_kind(prof, seed, i)
            tactician = ps.draw_tactician(prof, seed, i, kind)
            self.viewers.append(
                ps.new_viewer(i, data.personas[persona], prof.rng_name, seed, kind, tactician)
            )
        self.window = round(prof.agency_threat_window_s * hz)  # ticks a CaptureStarted stays recent
        self.lost_at: dict[str, int] = {}  # node -> tick of its latest coalition-to-ENEMY capture
        self.threat_at: dict[str, int] = {}  # node -> tick of its latest ENEMY CaptureStarted
        self.agency_picks: Counter[str] = Counter()  # tactician picks by rule (NX-321)
        self.striker_fallbacks = 0  # striker JOINs sent without a node: no defended foe was known
        self.capturer_fallbacks = 0  # capturer JOINs sent without a node: no capturable foe known
        self.by_commander = {v.commander_id: v for v in self.viewers}
        self.by_entity: dict[int, ps.Viewer] = {}
        self.wake = [(tick, i, "arrive") for i, (tick, _) in enumerate(sched)]  # sorted: a heap
        self.seq = 1  # next arrival_seq
        self.alive = 0  # viewers with a live unit now
        self.peak = 0  # the most at once

    def commands(self, world: World, tick: int, collector: Collector) -> list[Command]:
        out: list[Command] = []
        while self.wake and self.wake[0][0] <= tick:
            _, i, action = heapq.heappop(self.wake)
            v = self.viewers[i]
            cmd: Command | None = None
            if action == "rebase" and v.status == ps.ALIVE and (node := forward_base(world)):
                cmd = ps.rebase_command(v, node, tick, self.seq)
            elif action in ("arrive", "join") and v.status == ps.IDLE:
                cmd = self._join(world, v, action, tick)
                if cmd is not None:
                    collector.note_join(v.commander_id, tick, world.director["ENEMY"].tier)
            if cmd is not None:
                out.append(cmd)
                self.seq += 1
        return out

    def _join(self, world: World, v: ps.Viewer, action: str, tick: int) -> Command | None:
        if action == "arrive" and not ps.joins_on_arrival(v):
            v.status = ps.GONE
            return None
        v.status = ps.PENDING
        node = None
        if v.tactician and (picked := self._tactician(world, v, tick)) is not None:
            node = picked
        elif v.kind == "striker":
            node = ps.pick_node(v, defended_foes(world))
            self.striker_fallbacks += node is None
        elif v.kind == "capturer":
            node = ps.pick_node(v, capturable_foes(world))
            self.capturer_fallbacks += node is None
        elif v.kind == "freelancer" and world.rules is not None:  # any node: rear, bridges, own
            node = ps.pick_node(v, sorted(world.rules.roads.pos))  # sanctuary (NX-398, Q-SIM-110)
        return ps.join_command(v, tick, self.seq, node, self.data.kind_roles)

    def _tactician(self, world: World, v: ps.Viewer, tick: int) -> str | None:
        """NX-321: the node a tactician JOINs, or None when it falls back to its kind's pick
        (counted as `fallback`). Reads only `side_view`, `rules.strategic` and the event memory."""
        rules = world.rules
        if rules is None or rules.campaign is None:
            raise ValueError("a tactician needs the world's campaign rules")
        strategic = rules.campaign.strategic  # sorted by node id
        view = side_view(world, "COALITION")
        node: str | None
        if v.kind == "capturer":  # retake the strategic node the coalition lost last
            node = ps.latest(v, [n for n in capturable_foes(world) if n in strategic], self.lost_at)
            rule = "retake"
        else:
            mine = [n for n in strategic if view.owners.get(n) == "COALITION"]
            recent = {n: t for n, t in self.threat_at.items() if tick - t <= self.window}
            node = ps.latest(v, mine, recent)
            rule = "capture_started"
            if node is None:
                bare = [n for n in mine if not view.defense_hp.get(n, 0)]
                node = v.rng.choice(bare) if bare else None
                rule = "defenses_down"
        self.agency_picks[rule if node is not None else "fallback"] += 1
        return node

    def react(self, events: list[Any], tick: int, hz: int, seen: Counter[str]) -> None:
        for e in events:
            if e.kind == "UnitSpawned":
                self._spawned(e, tick, hz)
            elif e.kind == "ReserveQueueJoined":
                seen["queued"] += 1
            elif e.kind == "CommandRejected":
                seen[f"rejected:{e.command_kind}:{e.reason}"] += 1
                self._rejected(e, tick, hz)
            elif e.kind in ("UnitDestroyed", "UnitDespawned"):
                self._gone(e, tick, hz)
            elif e.kind == "NodeCaptured" and e.from_ == "COALITION" and e.to == "ENEMY":
                self.lost_at[e.node_id] = e.tick
            elif e.kind == "CaptureStarted" and e.side == "ENEMY":
                self.threat_at[e.node_id] = e.tick

    def _spawned(self, e: Any, tick: int, hz: int) -> None:
        v = self.by_commander.get(e.commander_id)
        if v is None:
            return
        v.status, v.entity, v.attempts = ps.ALIVE, e.entity_id, 0
        self.alive += 1
        self.peak = max(self.peak, self.alive)
        self.by_entity[e.entity_id] = v
        if (at := ps.rebase_at(v, tick, hz)) is not None:
            heapq.heappush(self.wake, (at, v.index, "rebase"))

    def _rejected(self, e: Any, tick: int, hz: int) -> None:
        v = self.by_commander.get(e.commander_id)
        if v is not None and e.command_kind == "JOIN" and v.status == ps.PENDING:
            self._lost(v, tick, hz)

    def _gone(self, e: Any, tick: int, hz: int) -> None:
        v = self.by_entity.pop(e.entity_id, None)
        if v is not None and v.status == ps.ALIVE:
            self.alive -= 1
            v.entity = None
            self._lost(v, tick, hz)

    def _lost(self, v: ps.Viewer, tick: int, hz: int) -> None:
        at = ps.rejoin_at(v, tick, hz)
        v.status = ps.GONE if at is None else ps.IDLE
        if at is not None:
            heapq.heappush(self.wake, (at, v.index, "join"))


def run(
    profile: str,
    seed: int,
    hours: float,
    log_dir: Path,
    data: profiles.Data | None = None,
    config: CampaignConfig | None = None,
    on_tick: Callable[[int, float, World], bool] | None = None,
) -> dict[str, Any]:
    """Run one (profile, seed) for up to `hours` game hours (it stops at the campaign's end) and
    return its report. The command log goes to `log_dir`. `on_tick(tick, step_seconds, world)`
    (the soak tool, NX-033) is called after each completed tick; a true return stops the run."""
    data = data or profiles.load()
    config = config or load_campaign_config()
    hz = config.balance.sim.tick_hz
    ticks = round(hours * 3600 * hz)
    world = start_campaign(campaign_id(data.profiles[profile].rng_name, seed), seed, config)
    rules = config.rules
    if rules.campaign is None:
        raise ValueError("the harness needs campaign rules")
    sched = profiles.schedule(data.profiles[profile], seed, ticks, hz)
    crowd = _Crowd(sched, data, profile, seed, hz)
    newbies = frozenset(v.commander_id for v in crowd.viewers if v.persona.name == "newbie")
    collector = Collector(
        world,
        newbies,
        kinds={v.commander_id: v.kind for v in crowd.viewers},
        a2_min_tier=data.targets.a2_min_tier,
        a2_refresh_ticks=round(data.targets.a2_refresh_unseen_game_min * 60 * hz),
        tick_hz=hz,
        sample_ticks=max(1, round(data.momentum_sample_s * hz)),
        a3_ticks=round(data.targets.a3_hours * 3600 * hz),
        idle_sample_ticks=round(data.idle_sample_min * 60 * hz),
        impact_check_ticks=max(1, round(data.impact_check_s * hz)),
        starve_threshold=config.balance.logistics.starve_threshold,
    )
    orders = Orders(
        world, frozenset(v.commander_id for v in crowd.viewers if v.kind == "freelancer")
    )
    log_dir.mkdir(parents=True)
    log = CommandLogWriter(
        log_dir, campaign_id=world.campaign.id, protocol_version=PROTOCOL, next_arrival_seq=1
    )
    crash: dict[str, Any] | None = None  # set when `step` raises; the world is then not trusted
    counts: Counter[str] = Counter()  # commands sent, by kind
    seen: Counter[str] = Counter()  # queued JOINs and rejections, by reason
    started = time.perf_counter()
    try:
        for tick in range(1, ticks + 1):
            cmds = crowd.commands(world, tick, collector)
            for c in cmds:
                counts[c.kind] += 1
            if cmds:
                log.append(cmds)
            t0 = time.perf_counter()
            try:
                events = step(world, cmds, HANDLERS)
                step_s = time.perf_counter() - t0
            except Exception as e:  # noqa: BLE001  # a sim crash is a finding: record it, stop the run
                crash = {"tick": tick, "error": f"{type(e).__name__}: {e}"}
                break
            collector.feed(events)
            collector.observe(world)
            orders.feed(events)
            orders.observe(world)
            if tick % collector.sample_ticks == 0:
                collector.sample(world)
            if tick % collector.impact_check_ticks == 0:
                collector.check_impact(world)
            if tick % collector.idle_sample_ticks == 0:
                collector.sample_idle(world)
                collector.sample_density(world)
            crowd.react(events, tick, hz, seen)
            if tick % FLUSH_TICKS == 0:
                log.flush()
            stop = on_tick is not None and on_tick(tick, step_s, world)
            if stop or world.campaign.ended:
                break
    finally:
        log.close()
    wall = time.perf_counter() - started
    ran = world.campaign.tick  # a crashed tick never completes, so this is the last good one
    return {
        "profile": profile,
        "rng_profile": data.profiles[profile].rng_name,
        "seed": seed,
        "hours": hours,
        "config_hash": world.campaign.config_hash,
        "profiles_digest": data.digest,
        "campaign_id": world.campaign.id,
        "ticks_run": ran,
        "tick_hz": hz,
        "time_limit_h": rules.campaign.time_limit_ticks / (3600 * hz),
        "profile_viewers": data.profiles[profile].viewers,  # NX-510: A1 judges by crowd size
        "viewers": {
            "distinct": len(crowd.viewers),
            "peak_concurrent": crowd.peak,  # most viewers with a live unit at once
            "by_persona": dict(sorted(Counter(v.persona.name for v in crowd.viewers).items())),
            "by_kind": dict(sorted(Counter(v.kind for v in crowd.viewers).items())),
            "striker_fallbacks": crowd.striker_fallbacks,
            "capturer_fallbacks": crowd.capturer_fallbacks,
            "tacticians": sum(v.tactician for v in crowd.viewers),
            "agency_picks": {k: crowd.agency_picks[k] for k in AGENCY_RULES},
        },
        "commands": dict(sorted(counts.items())),
        "responses": dict(sorted(seen.items())),
        "metrics": collector.result(ran),
        "orders": orders.result(),
        "crash": crash,
        "harness_error": None,
        "a3_ticks": collector.a3_ticks,
        "final_state_hash": None if crash else state_hash(world),
        "final_state_hash_sans_config": None if crash else state_hash_sans_config(world),
        "timing": {"wall_s": wall, "ticks_per_s": ran / wall if wall else None},
    }


def state_hash_sans_config(world: World) -> str:
    """`state_hash` with `campaign.config_hash` blanked (restored after), so two runs of the same
    seed under different `--set` configs compare on the world alone (NX-511 overnight-0 check:
    the config hash is part of `state_hash` and differs between the arms by construction)."""
    saved = world.campaign.config_hash
    world.campaign.config_hash = ""
    try:
        return state_hash(world)
    finally:
        world.campaign.config_hash = saved


def replay_log(log_dir: Path, seed: int, profile: str, ticks: int, config: CampaignConfig) -> str:
    """The final `state_hash` of the run rebuilt from its command log alone; `profile` is the run's
    `rng_profile` (its own name unless profiles.yaml says otherwise)."""
    world = start_campaign(campaign_id(profile, seed), seed, config)
    by_tick: defaultdict[int, list[Command]] = defaultdict(list)
    for entry in CommandLogReader(log_dir):
        if not isinstance(entry, Tombstone):
            by_tick[entry.target_tick].append(entry)
    for tick in range(1, ticks + 1):
        step(world, by_tick.get(tick, []), HANDLERS)
    return state_hash(world)


def failed_run(profile: str, seed: int, hours: float, error: str) -> dict[str, Any]:
    """The stand-in for a run whose harness code raised outside `step`: empty metrics, the error
    recorded as `harness_error`, so the batch goes on and the report shows the failure."""
    return {
        "profile": profile,
        "rng_profile": None,
        "seed": seed,
        "hours": hours,
        "config_hash": None,
        "profiles_digest": None,
        "time_limit_h": None,
        "profile_viewers": None,  # unknown: the run never started
        "ticks_run": 0,
        "a3_ticks": 0,
        "viewers": {
            "distinct": 0,
            "peak_concurrent": 0,
            "by_persona": {},
            "by_kind": {},
            "striker_fallbacks": 0,
            "capturer_fallbacks": 0,
            "tacticians": 0,
            "agency_picks": dict.fromkeys(AGENCY_RULES, 0),
        },
        "commands": {},
        "responses": {},
        "orders": None,
        "crash": None,
        "harness_error": error,
        "final_state_hash": None,
        "metrics": {
            "outcome": {"ended": False, "result": None, "length_h": None, "end_tick": None},
            "momentum": {"sample_every_s": None, "samples": []},
            "newbie": {
                "joined": 0,
                "joined_below_tier": 0,
                "below_tier_ttfi_s": [],
                "below_tier_no_impact_observed_s": [],
                "joined_counted": 0,
                "ttfi_s": [],
                "no_impact_observed_s": [],
                "first_impact_kinds": {},
                "by_kind": {},
            },
            "kills": {"by_kind": {}, "player_by_kind": {}, "total": 0, "unattributed": 0},
            "steamroll": None,
            "nodes_lost": [],
            "nodes_lost_in_a3_window": 0,
            "collapse": {
                "min_strategic_held": None,
                "first_zero_strategic_tick": None,
                "first_sanctuary_zero_tick": None,
            },
            "sanctuary_hp": {"min": None, "min_in_a3_window": None},
            "director": {"tier_dwell_s": {}, "tier_changes": 0},
            "idle": {
                "sample_every_s": 0,
                "samples": 0,
                "share_sum": 0.0,
                "share_max": None,
                "reasons": {},
                "open_strike_slots_sum": 0,
            },
            "coalition_hold": {
                "zero_strategic_ticks": 0,
                "zero_strategic_min": 0.0,
                "coalition_captures": 0,
            },
            "strategic_held": {
                "nodes": 0,
                "hold_threshold": 0,
                "min_by_k": [],
                "at_or_above_min": 0.0,
                "longest_min": 0.0,
                "by_node": {},
            },
            "who_took": {},
            "escort_jobs": [],
            "income_clip": {
                s: {"due": 0, "produced": 0, "lost": 0} for s in ("COALITION", "ENEMY")
            },
            "starvation": {
                "any_node_minutes": 0.0,
                "node_minutes": 0.0,
                "fraction_floor_any_node_minutes": 0.0,
                "fraction_floor_node_minutes": 0.0,
            },
            "hauling": {
                "run_hours": 0.0,
                "resupply_jobs": {"COALITION": 0, "ENEMY": 0},
                "deliveries": {"COALITION": 0, "ENEMY": 0},
                "trucks_lost_near_sanctuary": 0,
                "resupply_job_min": {
                    "COALITION": {"starving": 0.0, "stocking": 0.0},
                    "ENEMY": {"starving": 0.0, "stocking": 0.0},
                },
            },
            "defeat_run": {
                "started": 0,
                "longest_ticks": 0,
                "longest_min": 0.0,
                "paused_ticks": 0,
                "paused_min": 0.0,
                "resets": 0,
            },
        },
        "timing": {"wall_s": 0.0, "ticks_per_s": None},
    }
