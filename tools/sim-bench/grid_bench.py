"""NX-104 uniform-grid benchmark: per tick, `UniformGrid.rebuild` plus one `query_radius` each.

Runs in the sim project's own environment (it imports the real `nexus.core`), from the repo root:

  uv run --frozen --project services/sim python tools/sim-bench/grid_bench.py
  uv run --frozen --project services/sim python tools/sim-bench/grid_bench.py --ticks 600   # smoke

Scenarios reuse NX-345's (tools/sim-bench/bench.py): "worst" is 1,000 entities, "idle" is 150.
Entities move toward random waypoints inside the 400 x 240 km theater (SIM-CORE §4) every tick.
Speeds come from SIM-CORE §4 (jets 250 m/s, ground 25 m/s); the sensor radii, and so the cell size
(max sensor radius / 2, SC-10), are the NX-345 STAND-INS until the unit catalog exists (NX-106).
Timed: the rebuild and the queries, not the waypoint movement. The first 100 ticks are warm-up.
"""

# Seeded PRNG for the synthetic orders (S311).
# ruff: noqa: S311

import argparse
import json
import math
import os
import platform
import random
import statistics
import sys
from time import perf_counter_ns

from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.core.spatial import UniformGrid
from nexus.core.world import Campaign, Vec2, World

WORLD_DT = 0.1 * 6  # TICK_DT x sim.time_scale default (SC-2, SIM-CORE §4)
W, H = 400_000.0, 240_000.0  # theater ~400 x 240 km (SIM-CORE §4)
WARMUP = 100

# kind -> (speed m/s from SIM-CORE §4, sensor radius m: STAND-IN from NX-345 bench.py KINDS)
KINDS: dict[UnitKind, tuple[float, float]] = {
    "STRIKE_FIGHTER": (250.0, 40_000.0),
    "ENEMY_FIGHTER": (250.0, 40_000.0),
    "LOGI_TRUCK": (25.0, 8_000.0),
    "ENEMY_ARMOR": (25.0, 8_000.0),
    "RADAR_SITE": (0.0, 120_000.0),
    "AIR_DEFENSE_SITE": (0.0, 60_000.0),
}
CELL_M = max(s for _, s in KINDS.values()) / 2  # SC-10

type Mix = list[tuple[Side, OwnerKind, UnitKind, int]]
# STAND-IN mixes with NX-345's counts per side and role.
SCENARIOS: dict[str, Mix] = {
    "worst": [
        ("COALITION", "COMMANDER", "STRIKE_FIGHTER", 250),
        ("COALITION", "COMMANDER", "LOGI_TRUCK", 250),
        ("ENEMY", "ENEMY_DIRECTOR", "ENEMY_FIGHTER", 150),
        ("ENEMY", "ENEMY_DIRECTOR", "ENEMY_ARMOR", 200),
        ("COALITION", "AI_GARRISON", "RADAR_SITE", 25),
        ("COALITION", "AI_GARRISON", "AIR_DEFENSE_SITE", 50),
        ("ENEMY", "ENEMY_DIRECTOR", "RADAR_SITE", 25),
        ("ENEMY", "ENEMY_DIRECTOR", "AIR_DEFENSE_SITE", 50),
    ],
    "idle": [
        ("COALITION", "AI_GARRISON", "RADAR_SITE", 10),
        ("COALITION", "AI_GARRISON", "AIR_DEFENSE_SITE", 15),
        ("ENEMY", "ENEMY_DIRECTOR", "RADAR_SITE", 10),
        ("ENEMY", "ENEMY_DIRECTOR", "AIR_DEFENSE_SITE", 15),
        ("ENEMY", "ENEMY_DIRECTOR", "ENEMY_FIGHTER", 40),
        ("ENEMY", "ENEMY_DIRECTOR", "ENEMY_ARMOR", 60),
    ],
}


def point(rng: random.Random) -> Vec2:
    return Vec2(rng.uniform(0, W), rng.uniform(0, H))


def move(world: World, waypoints: dict[int, Vec2], rng: random.Random) -> None:
    for e in world.entities():
        step = KINDS[e.kind][0] * WORLD_DT
        if not step:
            continue
        wp = waypoints[e.id]
        dx, dy = wp.x - e.pos.x, wp.y - e.pos.y
        d = math.hypot(dx, dy)
        if d <= step:  # arrived: a new order (stands in for director/AI orders)
            e.pos, waypoints[e.id] = wp, point(rng)
        else:
            e.pos = Vec2(e.pos.x + dx / d * step, e.pos.y + dy / d * step)


def pct(xs: list[float], q: int) -> float:
    return statistics.quantiles(xs, n=100, method="inclusive")[q - 1] if len(xs) > 1 else xs[0]


def run(scenario: str, ticks: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    world = World.new(Campaign("grid-bench", seed, "stand-in"))
    for side, owner, kind, n in SCENARIOS[scenario]:
        for _ in range(n):
            world.spawn(kind, side, owner, point(rng), hp=1)
    waypoints = {e.id: point(rng) for e in world.entities()}
    grid = UniformGrid(CELL_M)
    total, rebuild, hits = [], [], 0
    for tick in range(ticks):
        move(world, waypoints, rng)
        t0 = perf_counter_ns()
        grid.rebuild(world.entities())
        t1 = perf_counter_ns()
        n = sum(len(grid.query_radius(e.pos, KINDS[e.kind][1])) for e in world.entities())
        t2 = perf_counter_ns()
        if tick >= WARMUP:
            total.append((t2 - t0) / 1e6)
            rebuild.append((t1 - t0) / 1e6)
            hits += n
    return {
        "scenario": scenario,
        "entities": len(world),
        "ticks": ticks,
        "cell_m": CELL_M,
        "rebuild_plus_queries_ms": {
            "p50": pct(total, 50),
            "p95": pct(total, 95),
            "p99": pct(total, 99),
            "max": max(total),
        },
        "rebuild_ms_p99": pct(rebuild, 99),
        "hits_per_query": hits / len(total) / len(world),
    }


def host() -> dict[str, object]:
    cpu = platform.processor()
    if os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo") as f:
            names = [ln.split(":", 1)[1].strip() for ln in f if ln.startswith("model name")]
        cpu = names[0] if names else cpu
    return {
        "platform": platform.platform(),
        "cpu": cpu,
        "cpus": os.cpu_count(),
        "python": sys.version.split()[0],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--ticks", type=int, default=36_000, help="ticks per run (36,000 = 1 h)")
    ap.add_argument("--scenario", choices=["worst", "idle", "both"], default="both")
    ap.add_argument("--seed", type=int, default=104)
    ap.add_argument("--out", help="also write the results as JSON to this path")
    a = ap.parse_args()
    if a.ticks <= WARMUP + 1:
        ap.error(f"--ticks must be more than {WARMUP + 1} (the first {WARMUP} are warm-up)")
    scenarios = ["worst", "idle"] if a.scenario == "both" else [a.scenario]
    runs: list[dict[str, object]] = []
    out = {"host": host(), "runs": runs}
    print(json.dumps(out["host"]))
    for sc in scenarios:
        runs.append(run(sc, a.ticks, a.seed))
        print(json.dumps(runs[-1]), flush=True)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
