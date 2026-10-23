"""Headless soak (NX-033 part 1, Q-TEST-9; TESTING-STRATEGY §2, SIM-CORE SC-10, SC-16).

One seeded campaign on the real kernel, driven by a crowd profile of tools/balance (its runner and
personas, not a copy), for a wall-clock budget or a game-time budget, whichever ends first. It
records per-tick step times (the worst N single ticks, for the NX-376 spike hunt), process memory
sampled every K game minutes and its slope after a warm-up, `state_hash` checkpoints at a fixed
tick interval, and the command log; then replays the log from tick 1 and checks every checkpoint.

  cd services/sim && uv run --frozen python ../../tools/soak/soak.py \\
      --profile evening-150 --minutes 45 --out /path/to/new-dir

Writes `soak.json`, `soak.md` and `logs/` (the command log) to `--out` (must not exist). Exit 0
pass, 1 fail (reasons in the report), 2 usage or config error. Timings from a shared runner are
indicative only (the reference host decides SC-10). A measurement that cannot be taken is
`null` in the JSON and "missing" in the Markdown, never a made-up value (DATA-INTEGRITY).
"""

import argparse
import heapq
import json
import math
import os
import platform
import subprocess  # git rev-parse only, fixed argv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "balance"))
import profiles
import runner

from nexus.contracts.gen.commands.command import Command
from nexus.core.step import HANDLERS, step
from nexus.core.world import World, state_hash
from nexus.runtime.campaign_config import (
    CampaignConfig,
    load_campaign_config,
    start_campaign,
)
from nexus.runtime.command_log import CommandLogReader, Tombstone

SC10_P99_MS = 25.0  # SC-10 line, reported beside the p99 and never gated here (shared runners)
BUCKET = (
    1.01  # step-time histogram: log buckets 1% wide, O(1) memory (a list would skew the RSS slope)
)
FLOOR_S = 1e-6


def read_rss_mb() -> float | None:
    """Resident set of this process in MB from /proc/self/statm, None where that does not exist."""
    try:
        pages = int(Path("/proc/self/statm").read_text().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / 1_000_000
    except (OSError, ValueError, IndexError):
        return None


def slope_per_hour(samples: list[tuple[float, float]], warmup_h: float) -> float | None:
    """Least-squares slope of (game hour, MB) after the warm-up, MB per game hour; None when fewer
    than three samples remain or they share one x (no slope can be fitted)."""
    pts = [(h, mb) for h, mb in samples if h >= warmup_h]
    if len(pts) < 3:  # fewer than three points is not a trend
        return None
    mx = sum(h for h, _ in pts) / len(pts)
    my = sum(mb for _, mb in pts) / len(pts)
    sxx = sum((h - mx) ** 2 for h, _ in pts)
    if sxx == 0:
        return None
    return sum((h - mx) * (mb - my) for h, mb in pts) / sxx


class StepStats:
    """Step-time percentiles from a 1%-bucket log histogram, and the worst N ticks."""

    def __init__(self, worst: int):
        self.n = 0
        self.max_s = 0.0
        self.buckets: Counter[int] = Counter()
        self.limit = worst
        self.heap: list[tuple[float, int, dict[str, Any]]] = []  # min-heap on step time

    def add(self, tick: int, step_s: float, context: Any) -> None:
        """Count one tick. `context()` builds the reason dict and runs only for a tick that enters
        the worst-N list."""
        self.n += 1
        self.max_s = max(self.max_s, step_s)
        self.buckets[math.floor(math.log(max(step_s, FLOOR_S) / FLOOR_S, BUCKET))] += 1
        if self.limit <= 0:
            return
        if len(self.heap) < self.limit:
            heapq.heappush(self.heap, (step_s, tick, context()))
        elif step_s > self.heap[0][0]:
            heapq.heapreplace(self.heap, (step_s, tick, context()))

    def percentile(self, q: float) -> float | None:
        """Upper edge of the bucket holding the q-quantile (within 1% of the true value), s."""
        if not self.n:
            return None
        need, seen = math.ceil(q * self.n), 0
        for b in sorted(self.buckets):
            seen += self.buckets[b]
            if seen >= need:
                return min(FLOOR_S * BUCKET ** (b + 1), self.max_s)
        return self.max_s

    def worst(self) -> list[dict[str, Any]]:
        return [
            {"tick": t, "step_ms": s * 1000, **ctx}
            for s, t, ctx in sorted(self.heap, key=lambda x: (-x[0], x[1]))
        ]


class Probe:
    """The `on_tick` hook for runner.run: records, and says stop when a budget is spent."""

    def __init__(self, args: argparse.Namespace, hz: int, board_every: int | None):
        self.hz, self.board_every = hz, board_every
        self.stats = StepStats(args.worst)
        self.deadline = time.perf_counter() + args.minutes * 60
        self.max_tick = round(args.hours * 3600 * hz)
        self.checkpoint_ticks = args.checkpoint_ticks
        self.mem_ticks = max(1, round(args.mem_every_min * 60 * hz))
        self.checkpoints: dict[int, str] = {}
        self.memory: list[tuple[float, float]] = []  # (game hour, MB)
        self.stopped_by = "campaign end"

    def __call__(self, tick: int, step_s: float, world: World) -> bool:
        def context() -> dict[str, Any]:
            # The board runs at running tick `running_ticks + 1` (before the clock advances) when
            # that divides reeval_every_ticks and the world is not frozen (tasking.py `run`);
            # after the step the clock has advanced, so the same rule reads `running_ticks`.
            board = (
                None
                if not self.board_every
                else not world.frozen and world.campaign.running_ticks % self.board_every == 0
            )
            return {
                "game_s": tick / self.hz,
                "board_pass_tick": board,
                "entities": sum(1 for _ in world.entities()),
            }

        self.stats.add(tick, step_s, context)
        if tick % self.checkpoint_ticks == 0:
            self.checkpoints[tick] = state_hash(world)
        if tick % self.mem_ticks == 0 and (mb := read_rss_mb()) is not None:
            self.memory.append((tick / self.hz / 3600, mb))
        if tick >= self.max_tick:
            self.stopped_by = "game-time budget"
        elif time.perf_counter() >= self.deadline:
            self.stopped_by = "wall-clock budget"
        else:
            return False
        return True


def replay_checkpoints(
    log_dir: Path, seed: int, profile: str, ticks: int, config: CampaignConfig, wanted: set[int]
) -> dict[int, str]:
    """state_hash at each wanted tick of the run rebuilt from its command log alone."""
    world = start_campaign(runner.campaign_id(profile, seed), seed, config)
    by_tick: defaultdict[int, list[Command]] = defaultdict(list)
    for entry in CommandLogReader(log_dir):
        if not isinstance(entry, Tombstone):
            by_tick[entry.target_tick].append(entry)
    out: dict[int, str] = {}
    for tick in range(1, ticks + 1):
        step(world, by_tick.get(tick, []), HANDLERS)
        if tick in wanted:
            out[tick] = state_hash(world)
    return out


def verdict(
    run: dict[str, Any], slope: float | None, max_growth: float, replay: dict[str, Any] | None
) -> list[str]:
    """The reasons the soak fails; empty means pass. A missing slope is reported, not a failure."""
    reasons = []
    if run["harness_error"]:
        reasons.append(f"harness error: {run['harness_error']}")
    if run["crash"]:
        reasons.append(f"sim crash at tick {run['crash']['tick']}: {run['crash']['error']}")
    if slope is not None and slope > max_growth:
        reasons.append(f"memory grows {slope:.2f} MB per game hour, over {max_growth}")
    if replay is None:
        if not (run["crash"] or run["harness_error"]):
            reasons.append("replay did not run")
    elif replay["mismatches"]:
        reasons.append(f"replay hash mismatch at ticks {replay['mismatches']}")
    return reasons


def sha() -> str | None:
    if env := os.environ.get("GITHUB_SHA"):
        return env
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def ms(seconds: float | None) -> float | None:
    return None if seconds is None else seconds * 1000


def soak(args: argparse.Namespace, data: profiles.Data, config: CampaignConfig) -> dict[str, Any]:
    hz = config.balance.sim.tick_hz
    tasking = config.rules.tasking
    probe = Probe(args, hz, tasking.reeval_every_ticks if tasking else None)
    args.out.mkdir(parents=True)
    log_dir = args.out / "logs"
    started = time.perf_counter()
    run = runner.run(args.profile, args.seed, args.hours, log_dir, data, config, on_tick=probe)
    run_s = time.perf_counter() - started
    ran = run["ticks_run"]
    replay: dict[str, Any] | None = None
    if not (run["crash"] or run["harness_error"]):
        probe.checkpoints[ran] = run["final_state_hash"]  # the last tick is a checkpoint too
        t0 = time.perf_counter()
        got = replay_checkpoints(
            log_dir, args.seed, args.profile, ran, config, set(probe.checkpoints)
        )
        bad = [t for t, h in sorted(probe.checkpoints.items()) if got.get(t) != h]
        replay = {
            "checkpoints": len(probe.checkpoints),
            "mismatches": bad,
            "wall_s": time.perf_counter() - t0,
        }
    slope = slope_per_hour(probe.memory, args.warmup_h)
    reasons = verdict(run, slope, args.max_growth_mb_per_h, replay)
    st = probe.stats
    if run["crash"]:
        stopped = f"crash: {run['crash']['error'].split(':')[0]}"
    elif run["harness_error"]:
        stopped = "harness error"
    else:
        stopped = probe.stopped_by if ran else "none"
    return {
        "pass": not reasons,
        "reasons": reasons,
        "sha": sha(),
        "config_hash": run["config_hash"],
        "profiles_digest": run["profiles_digest"],
        "profile": args.profile,
        "seed": args.seed,
        "stopped_by": stopped,
        "ticks_run": ran,
        "game_hours": ran / hz / 3600,
        "wall_s": run_s,
        "host": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpus": os.cpu_count(),
        },
        "indicative_only": "shared-runner timings are a trend, not a verdict (SC-10: ref. host)",
        "step_ms": {
            "p50": ms(st.percentile(0.5)),
            "p99": ms(st.percentile(0.99)),
            "max": ms(st.max_s) if st.n else None,
            "sc10_p99_line": SC10_P99_MS,
            "histogram_resolution": "percentiles are bucket upper edges, within 1% of the value",
        },
        "worst_ticks": st.worst(),
        "memory": {
            "source": "/proc/self/statm" if probe.memory else None,
            "samples": [{"game_h": h, "rss_mb": mb} for h, mb in probe.memory],
            "warmup_h": args.warmup_h,
            "slope_mb_per_game_h": slope,
            "gate_applied": slope is not None,
            "max_growth_mb_per_h": args.max_growth_mb_per_h,
            "max_growth_status": "PROPOSED, not a validated value",
        },
        "checkpoints": {str(t): h for t, h in sorted(probe.checkpoints.items())},
        "checkpoint_ticks": args.checkpoint_ticks,
        "replay": replay,
        "commands": run["commands"],
        "crash": run["crash"],
        "harness_error": run["harness_error"],
    }


def num(value: float | None, fmt: str = ".2f") -> str:
    return "missing" if value is None else format(value, fmt)


def markdown(r: dict[str, Any]) -> str:
    s, m, rp = r["step_ms"], r["memory"], r["replay"]
    replay = (
        "did not run"
        if rp is None
        else f"{rp['checkpoints'] - len(rp['mismatches'])}/{rp['checkpoints']} checkpoints match "
        f"({rp['wall_s']:.0f} s)"
    )
    unmeasured = r["pass"] and not m["gate_applied"]
    headline = "FAIL" if not r["pass"] else "PASS (memory not measured)" if unmeasured else "PASS"
    lines = [
        f"# Soak: {headline}",
        "",
        *(
            ["- memory gate NOT applied (needs 3+ samples after the warm-up and /proc)"]
            if not m["gate_applied"]
            else []
        ),
        *(f"- FAIL: {x}" for x in r["reasons"]),
        f"- sha `{r['sha'] or 'missing'}`, config hash `{r['config_hash']}`",
        f"- profiles digest `{r['profiles_digest']}`",
        f"- profile `{r['profile']}`, seed {r['seed']}, stopped by: {r['stopped_by']}",
        f"- {r['ticks_run']} ticks ({r['game_hours']:.2f} game h), {r['wall_s'] / 60:.1f} min wall",
        f"- step ms: p50 {num(s['p50'])}, p99 {num(s['p99'])} (SC-10 line "
        f"{s['sc10_p99_line']}), max {num(s['max'])}",
        f"- memory: slope {num(m['slope_mb_per_game_h'])} MB per game h after a "
        f"{m['warmup_h']} h warm-up "
        f"(limit {m['max_growth_mb_per_h']}, PROPOSED), {len(m['samples'])} samples",
        f"- replay: {replay}",
        f"- {r['indicative_only']}",
        "",
        "## Worst ticks",
        "",
        "| tick | game s | step ms | board pass | entities |",
        "|---|---|---|---|---|",
        *(
            f"| {w['tick']} | {w['game_s']:.1f} | {w['step_ms']:.2f} | {w['board_pass_tick']} "
            f"| {w['entities']} |"
            for w in r["worst_ticks"]
        ),
    ]
    return "\n".join(lines) + "\n"


def positive(text: str) -> float:
    value = float(text)
    if not value > 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {text}")
    return value


def whole(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {text}")
    return value


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument(
        "--profile", default="evening-150", help="a crowd profile of tools/balance/profiles.yaml"
    )
    p.add_argument("--seed", type=whole, default=1)
    p.add_argument(
        "--minutes",
        type=positive,
        default=45.0,
        help="wall-clock budget of the run phase (the replay is extra)",
    )
    p.add_argument(
        "--hours",
        type=positive,
        default=None,
        help="game-time budget (default campaign.time_limit_h)",
    )
    p.add_argument("--worst", type=int, default=20, help="how many of the slowest ticks to list")
    p.add_argument(
        "--checkpoint-ticks",
        type=whole,
        default=3600,
        help="state_hash every N ticks (3600 = 6 game min)",
    )
    p.add_argument(
        "--mem-every-min", type=positive, default=5.0, help="game minutes between RSS samples"
    )
    p.add_argument(
        "--warmup-h",
        type=float,
        default=0.5,
        help="game hours ignored before the slope fit (PROPOSED)",
    )
    p.add_argument(
        "--max-growth-mb-per-h",
        type=positive,
        default=20.0,
        help="fail above this slope; PROPOSED, not validated",
    )
    p.add_argument("--out", type=Path, required=True, help="report directory; must not exist")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    data, config = profiles.load(), load_campaign_config()
    if args.profile not in data.profiles:
        print(f"error: unknown profile {args.profile!r}", file=sys.stderr)
        return 2
    if args.out.exists():
        print(f"error: {args.out} exists", file=sys.stderr)
        return 2
    if args.hours is None:
        if config.rules.campaign is None:
            print("error: the config has no campaign rules; pass --hours", file=sys.stderr)
            return 2
        args.hours = config.rules.campaign.time_limit_ticks / (3600 * config.balance.sim.tick_hz)
    report = soak(args, data, config)
    (args.out / "soak.json").write_text(json.dumps(report, indent=2) + "\n")
    text = markdown(report)
    (args.out / "soak.md").write_text(text)
    print(text)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
