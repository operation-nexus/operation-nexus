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
from pathlib import Path
from typing import Any

import personas as ps
import profiles
from metrics import Collector

from nexus.contracts.gen.commands.command import Command
from nexus.core.step import HANDLERS, step
from nexus.core.world import World, state_hash
from nexus.runtime.campaign_config import CampaignConfig, load_campaign_config, start_campaign
from nexus.runtime.command_log import CommandLogReader, CommandLogWriter, Tombstone

PROTOCOL = "0.2"  # the command log's protocol_version (same as the runtime tests)
SAMPLE_S = 60  # game seconds between momentum and starvation samples
FLUSH_TICKS = 600


def campaign_id(profile: str, seed: int) -> str:
    """A deterministic UUIDv7-shaped campaign id per (profile, seed)."""
    h = hashlib.blake2b(f"{profile}/{seed}".encode(), digest_size=16).hexdigest()
    return f"{h[:8]}-{h[8:12]}-7{h[13:16]}-8{h[17:20]}-{h[20:32]}"


def forward_base(world: World) -> str | None:
    """The most forward (eastmost) landing base the coalition owns, the sanctuary aside."""
    rules = world.rules
    if rules is None:
        raise ValueError("forward_base needs the world's rules")
    bases = [n for n in world.landing_bases("COALITION") if n != rules.sanctuary]
    return max(bases, key=lambda n: (rules.roads.pos[n][0], n), default=None)


class _Crowd:
    """The viewers, their wake-ups and what they make of the events."""

    def __init__(self, sched: list[tuple[int, str]], data: profiles.Data, profile: str, seed: int):
        self.data = data
        self.viewers = [
            ps.new_viewer(i, data.personas[persona], profile, seed)
            for i, (_, persona) in enumerate(sched)
        ]
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
                cmd = self._join(v, action, tick)
                if cmd is not None:
                    collector.note_join(v.commander_id, tick)
            if cmd is not None:
                out.append(cmd)
                self.seq += 1
        return out

    def _join(self, v: ps.Viewer, action: str, tick: int) -> Command | None:
        if action == "arrive" and not ps.joins_on_arrival(v):
            v.status = ps.GONE
            return None
        v.status = ps.PENDING
        return ps.join_command(v, tick, self.seq)

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
) -> dict[str, Any]:
    """Run one (profile, seed) for up to `hours` game hours (it stops at the campaign's end) and
    return its report. The command log goes to `log_dir`."""
    data = data or profiles.load()
    config = config or load_campaign_config()
    hz = config.balance.sim.tick_hz
    ticks = round(hours * 3600 * hz)
    world = start_campaign(campaign_id(profile, seed), seed, config)
    rules = config.rules
    if rules.campaign is None:
        raise ValueError("the harness needs campaign rules")
    sched = profiles.schedule(data.profiles[profile], seed, ticks, hz)
    crowd = _Crowd(sched, data, profile, seed)
    newbies = frozenset(v.commander_id for v in crowd.viewers if v.persona.name == "newbie")
    collector = Collector(
        world,
        newbies,
        tick_hz=hz,
        sample_ticks=SAMPLE_S * hz,
        a3_ticks=round(data.targets.a3_hours * 3600 * hz),
        idle_sample_ticks=round(data.idle_sample_min * 60 * hz),
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
            try:
                events = step(world, cmds, HANDLERS)
            except Exception as e:  # noqa: BLE001  # a sim crash is a finding: record it, stop the run
                crash = {"tick": tick, "error": f"{type(e).__name__}: {e}"}
                break
            collector.feed(events)
            collector.observe(world)
            if tick % collector.sample_ticks == 0:
                collector.sample(world)
            if tick % collector.idle_sample_ticks == 0:
                collector.sample_idle(world)
            crowd.react(events, tick, hz, seen)
            if tick % FLUSH_TICKS == 0:
                log.flush()
            if world.campaign.ended:
                break
    finally:
        log.close()
    wall = time.perf_counter() - started
    ran = world.campaign.tick  # a crashed tick never completes, so this is the last good one
    return {
        "profile": profile,
        "seed": seed,
        "hours": hours,
        "config_hash": world.campaign.config_hash,
        "profiles_digest": data.digest,
        "campaign_id": world.campaign.id,
        "ticks_run": ran,
        "time_limit_h": rules.campaign.time_limit_ticks / (3600 * hz),
        "viewers": {
            "distinct": len(crowd.viewers),
            "peak_concurrent": crowd.peak,  # most viewers with a live unit at once
            "by_persona": dict(sorted(Counter(v.persona.name for v in crowd.viewers).items())),
        },
        "commands": dict(sorted(counts.items())),
        "responses": dict(sorted(seen.items())),
        "metrics": collector.result(ran),
        "crash": crash,
        "harness_error": None,
        "a3_ticks": collector.a3_ticks,
        "final_state_hash": None if crash else state_hash(world),
        "timing": {"wall_s": wall, "ticks_per_s": ran / wall if wall else None},
    }


def replay_log(log_dir: Path, seed: int, profile: str, ticks: int, config: CampaignConfig) -> str:
    """The final `state_hash` of the run rebuilt from its command log alone."""
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
        "seed": seed,
        "hours": hours,
        "config_hash": None,
        "profiles_digest": None,
        "time_limit_h": None,
        "ticks_run": 0,
        "a3_ticks": 0,
        "viewers": {"distinct": 0, "peak_concurrent": 0, "by_persona": {}},
        "commands": {},
        "responses": {},
        "crash": None,
        "harness_error": error,
        "final_state_hash": None,
        "metrics": {
            "outcome": {"ended": False, "result": None, "length_h": None, "end_tick": None},
            "momentum": {"sample_every_s": SAMPLE_S, "samples": []},
            "newbie": {"joined": 0, "ttfi_s": [], "no_impact_observed_s": []},
            "kills": {"by_kind": {}, "player_by_kind": {}, "total": 0, "unattributed": 0},
            "nodes_lost": [],
            "nodes_lost_in_a3_window": 0,
            "sanctuary_hp": {"min": None, "min_in_a3_window": None},
            "director": {"tier_dwell_s": {}, "tier_changes": 0},
            "idle": {
                "sample_every_s": 0,
                "samples": 0,
                "share_sum": 0.0,
                "share_max": None,
                "reasons": {},
            },
            "starvation": {"any_node_minutes": 0.0, "node_minutes": 0.0},
        },
        "timing": {"wall_s": 0.0, "ticks_per_s": None},
    }
