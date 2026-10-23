"""NX-376 real-kernel scaling bench: the real `nexus.core.step` on a real campaign world, over an
entity ladder (REALTIME-SCALING-2026-10-22 §2-§3).

Runs in the sim project's own environment, from services/sim:

  uv run --frozen python ../../tools/sim-bench/kernel_bench.py
  uv run --frozen python ../../tools/sim-bench/kernel_bench.py --ladder 150,1000 --ticks 600 \
      --scene mixed --profile --out /tmp/kernel.json

Scenes (both seeded: the same seed builds the same scene; timings naturally vary):
  convoy  QA's worst case from tests/core/test_follow.py, scaled to N entities: convoys of a leader,
          three escorts and three column trucks on the Static's road, 30% coalition infantry the
          escorts really track, 10 trucks for the board's escort work. Shipped config with the
          test's overrides (no opening garrison, patrols off).
  mixed   a campaign-like spread on the shipped config as it is (opening garrison, patrols on):
          half the entities are viewer (COMMANDER) units of several kinds, half are Static units,
          scattered along the road so both sides track each other; board passes on. Caveats: every
          unit is injected at once with no per-unit history (no fire, losses or orders yet); only
          LOGI_TRUCK gets a path (to cross-n), the other coalition units stand still; Static
          ground units path to static-hq; aircraft sit LANDED. Not a replay of a campaign.

Timed: `step(world, [])` only. NOT counted: the frame build (no overlay frame exists yet, so this
is a lower bound on the SC-10 "step + frame build" p99 < 25 ms) and the untimed settle before
the timed ticks. The settle (`--settle`, default two board-pass periods, 2 x reeval_every_ticks)
lets sensing track, fire open and the board make its first assignments of the mass-injected scene,
so the timed ticks are steady state. The first board pass is that mass arrival (much dearer than
later ones); it is reported apart as `first_board_pass_ms`. GC is left on, as in a live run.
Board-pass ticks (tasking.reeval_every_ticks) are reported apart from
plain ticks, like the test. The container is not the reference host (SC-10: the i7-8700 under
WSL2); the output carries the host block so the two can be told apart.
"""

# Seeded PRNG for the scene layout (S311).
# ruff: noqa: S311

import argparse
import cProfile
import dataclasses
import io
import json
import math
import os
import platform
import pstats
import random
import statistics
import sys
from time import perf_counter_ns
from typing import Any

from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.core.step import step
from nexus.core.world import Entity, Vec2, World
from nexus.runtime.campaign_config import load_campaign_config, start_campaign

DIRECTOR: OwnerKind = "ENEMY_DIRECTOR"
AI: OwnerKind = "AI_GARRISON"
ROAD_Y = 120_000  # the Static's road, as in test_follow.py
EAST = 310_000  # east-airbase; static-hq is 70 km on
CAMPAIGN_ID = "0192f0c1-7a2b-7c3d-8e4f-0000000003a6"
SCENES = ("convoy", "mixed")
MIXED_VIEWER_KINDS: tuple[UnitKind, ...] = (
    "LOGI_TRUCK",
    "GARRISON_INFANTRY",
    "STRIKE_FIGHTER",
    "RECON_UAV",
)
MIXED_STATIC_KINDS: tuple[UnitKind, ...] = ("ENEMY_ARMOR", "ENEMY_CONVOY", "ENEMY_FIGHTER")

CONFIG = load_campaign_config()


def _rules(scene: str) -> Any:
    if scene == "mixed":
        return CONFIG.rules
    tasking = CONFIG.rules.tasking
    assert tasking is not None  # noqa: S101  # the shipped config has tasking rules
    return dataclasses.replace(
        CONFIG.rules,
        campaign=None,
        garrison_quota={},
        tasking=dataclasses.replace(tasking, patrol_max_nodes=0),
    )


def board_every(world: World) -> int:
    tasking = world.rules.tasking if world.rules else None
    assert tasking is not None  # noqa: S101
    return tasking.reeval_every_ticks


def _spawn(
    w: World,
    kind: UnitKind,
    owner: OwnerKind,
    pos: Vec2,
    node: str,
    path: list[str | Vec2] | None = None,
) -> Entity:
    side: Side = "ENEMY" if kind.startswith("ENEMY_") else "COALITION"
    commander = (
        f"0192f0c1-7a2b-7c3d-8e4f-{w._next_entity_id:012d}" if owner == "COMMANDER" else None
    )
    e = w.spawn(kind, side, owner, pos, commander_id=commander)
    e.last_node = node
    if path:
        e.path = path
    if w.rules is not None and w.rules.domain[kind] == "AIR":
        e.state, e.fuel = "LANDED", w.rules.fuel_s[kind]
    return e


def _on_road(w: World, kind: UnitKind, x: float, y: float = ROAD_Y) -> Entity:
    return _spawn(w, kind, DIRECTOR, Vec2(EAST + x, y), "east-airbase", ["static-hq"])


def _follow(f: Entity, leader: Entity) -> None:
    f.follow_id, f.order = leader.id, "FOLLOW"


def _convoy_scene(w: World, n: int) -> None:
    for site in [e for e in w.entities() if e.kind in ("RADAR_SITE", "AIR_DEFENSE_SITE")]:
        w.remove(site.id)
    base = len(w)
    infantry = round(0.3 * n)
    trucks = 10 if n >= 100 else 0
    convoys = max(n - base - infantry - trucks, 0) // 7
    infantry = n - base - trucks - 7 * convoys  # the remainder is more infantry: exactly n
    leads = []
    for c in range(convoys):
        x = 600 * (c % 100)  # 600 m apart; past 100 convoys the next column sits 50 m to the side
        y = ROAD_Y + 50 * (c // 100)
        lead = _on_road(w, "ENEMY_CONVOY", x, y)
        leads.append(lead)
        for k in range(3):
            _follow(_on_road(w, "ENEMY_ARMOR", x + 500 - 100 * k, y), lead)
        for k in range(3):
            _follow(_on_road(w, "ENEMY_CONVOY", x - 200 - 100 * k, y), lead)
    for k in range(infantry):  # 6 km off the road: tracked (8 km optics), out of every gun's range
        foe = _spawn(w, "GARRISON_INFANTRY", AI, Vec2(EAST + 200 * (k % 350), ROAD_Y + 6_000), "")
        foe.last_node = None
        if k % 3 == 0 and k // 3 < len(leads):  # a third of the convoys were fired at lately
            leads[k // 3].fired_by = [[foe.id, w.campaign.running_ticks + 1]]
    for k in range(trucks):  # bound for the infantry's strip: the board has escort work too
        truck = w.spawn("ENEMY_CONVOY", "ENEMY", DIRECTOR, Vec2(EAST, ROAD_Y + 10 * k))
        truck.last_node, truck.path = "east-airbase", ["static-hq"]


def _mixed_scene(w: World, n: int, rng: random.Random) -> None:
    viewers = (n - len(w)) // 2
    statics = n - len(w) - viewers
    for i in range(viewers):
        kind = MIXED_VIEWER_KINDS[i % len(MIXED_VIEWER_KINDS)]
        x, y = rng.uniform(0, 60_000), ROAD_Y + rng.uniform(-8_000, 8_000)
        if w.rules is not None and w.rules.domain[kind] == "AIR":
            _spawn(w, kind, "COMMANDER", Vec2(*w.rules.roads.pos["west-airbase"]), "west-airbase")
        else:
            path: list[str | Vec2] | None = ["cross-n"] if kind == "LOGI_TRUCK" else None
            _spawn(w, kind, "COMMANDER", Vec2(EAST + x, y), "east-airbase", path)
    for i in range(statics):
        kind = MIXED_STATIC_KINDS[i % len(MIXED_STATIC_KINDS)]
        x, y = rng.uniform(0, 60_000), ROAD_Y + rng.uniform(-8_000, 8_000)
        if w.rules is not None and w.rules.domain[kind] == "AIR":
            _spawn(w, kind, DIRECTOR, Vec2(*w.rules.roads.pos["static-rear"]), "static-rear")
        else:
            _spawn(w, kind, DIRECTOR, Vec2(EAST + x, y), "east-airbase", ["static-hq"])


def build_scene(scene: str, n: int, seed: int) -> World:
    """A world of exactly `n` entities (the campaign's own facilities and garrison included)."""
    w = start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(CONFIG, rules=_rules(scene)))
    if scene == "convoy":
        _convoy_scene(w, n)
    else:
        _mixed_scene(w, n, random.Random(seed))
    if len(w) != n:
        raise ValueError(f"scene {scene!r} cannot be built at {n} entities (got {len(w)})")
    return w


def pct(xs: list[float], q: int) -> float:
    if len(xs) < 2:
        return xs[0]
    return statistics.quantiles(xs, n=100, method="inclusive")[q - 1]


def summary(ms: list[float]) -> dict[str, float]:
    if not ms:
        return {}
    return {
        "mean": statistics.mean(ms),
        "p50": pct(ms, 50),
        "p95": pct(ms, 95),
        "p99": pct(ms, 99),
        "max": max(ms),
    }


def is_board_tick(running_ticks: int, every: int) -> bool:
    """Whether the next `step` (running_ticks + 1) runs a board pass."""
    return (running_ticks + 1) % every == 0


def settle_world(w: World, settle: int | None) -> float | None:
    """Step `settle` ticks (default 2 board periods); the first board pass's ms, if one ran."""
    every = board_every(w)
    first: float | None = None
    for _ in range(2 * every if settle is None else settle):
        due = is_board_tick(w.campaign.running_ticks, every)
        t0 = perf_counter_ns()
        step(w, [])
        if due and first is None:
            first = (perf_counter_ns() - t0) / 1e6
    return first


def run_rung(
    scene: str, n: int, ticks: int, seed: int, settle: int | None = None
) -> dict[str, Any]:
    w = build_scene(scene, n, seed)
    viewers = sum(1 for e in w.entities() if e.owner_kind == "COMMANDER")
    every = board_every(w)
    first_pass = settle_world(w, settle)
    board: list[float] = []
    plain: list[float] = []
    worst, worst_tick = -1.0, 0
    began = perf_counter_ns()
    for _ in range(ticks):
        due = is_board_tick(w.campaign.running_ticks, every)
        t0 = perf_counter_ns()
        step(w, [])
        ms = (perf_counter_ns() - t0) / 1e6
        (board if due else plain).append(ms)
        if ms > worst:
            worst, worst_tick = ms, w.campaign.running_ticks
    wall_s = (perf_counter_ns() - began) / 1e9
    every_tick = board + plain
    return {
        "entities": n,
        "viewer_units": viewers,
        "entities_after": len(w),
        "tracked": sum(len(c) for c in w.contacts.values()),
        "ticks": ticks,
        "ticks_per_s": ticks / wall_s,
        "step_ms": summary(every_tick),
        "board_pass_ms": summary(board),
        "plain_ms": summary(plain),
        "first_board_pass_ms": first_pass,
        "board_pass_ticks": len(board),
        "plain_ticks": len(plain),
        "largest_tick": {"ms": worst, "tick": worst_tick},
    }


def exponent(rungs: list[dict[str, Any]]) -> float | None:
    """Least-squares slope of log(mean step ms) against log(entities)."""
    pts = [(math.log(r["entities"]), math.log(r["step_ms"]["mean"])) for r in rungs]
    if len(pts) < 2:
        return None
    mx, my = statistics.mean(p[0] for p in pts), statistics.mean(p[1] for p in pts)
    var = sum((x - mx) ** 2 for x, _ in pts)
    return sum((x - mx) * (y - my) for x, y in pts) / var if var else None


def profile_rung(
    scene: str, n: int, ticks: int, seed: int, settle: int | None = None
) -> dict[str, str]:
    w = build_scene(scene, n, seed)
    settle_world(w, settle)
    prof = cProfile.Profile()
    prof.enable()
    for _ in range(ticks):
        step(w, [])
    prof.disable()
    out = {}
    for key in ("cumulative", "tottime"):
        buf = io.StringIO()
        pstats.Stats(prof, stream=buf).strip_dirs().sort_stats(key).print_stats(15)
        out[key] = buf.getvalue().strip()
    return out


def host() -> dict[str, Any]:
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


def table(res: dict[str, Any]) -> str:
    rows = [
        f"scene {res['scene']}, seed {res['seed']}; step only, NO frame build (SC-10 lower bound)",
        f"{'entities':>8} {'viewers':>7} {'tracked':>7} {'ticks/s':>8} {'p50':>7} {'p95':>7} "
        f"{'p99':>7} {'max':>7} {'board p99':>9} {'plain p99':>9}  largest (tick)",
    ]
    for r in res["rungs"]:
        s, b, p = r["step_ms"], r["board_pass_ms"], r["plain_ms"]
        rows.append(
            f"{r['entities']:>8} {r['viewer_units']:>7} {r['tracked']:>7} {r['ticks_per_s']:>8.1f} "
            f"{s['p50']:>7.1f} {s['p95']:>7.1f} {s['p99']:>7.1f} {s['max']:>7.1f} "
            f"{b.get('p99', float('nan')):>9.1f} {p.get('p99', float('nan')):>9.1f}  "
            f"{r['largest_tick']['ms']:.1f} ms ({r['largest_tick']['tick']})"
        )
    k = res["scaling_exponent"]
    rows.append(
        "scaling exponent (log-log slope of mean step ms vs entities): "
        + (f"{k:.2f}" if k is not None else "n/a")
    )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--ladder", default="150,300,500,1000,2000", help="entity counts")
    ap.add_argument("--ticks", type=int, default=3000, help="timed ticks per rung (3000 = 5 min)")
    ap.add_argument("--scene", choices=SCENES, default="convoy")
    ap.add_argument("--seed", type=int, default=376)
    ap.add_argument("--settle", type=int, help="untimed ticks first (default 2 board periods)")
    ap.add_argument("--profile", action="store_true", help="cProfile the largest rung")
    ap.add_argument("--out", help="write the results as JSON to this path")
    a = ap.parse_args(argv)
    ladder = sorted({int(x) for x in a.ladder.split(",")})
    if a.ticks < 1 or not ladder or ladder[0] < 1:
        ap.error("--ticks and every --ladder entry must be positive")
    if a.settle is not None and a.settle < 0:
        ap.error("--settle must not be negative")
    try:
        build_scene(a.scene, ladder[0], a.seed)
    except ValueError as e:
        ap.error(f"--ladder: {e}; the {a.scene} scene has a fixed base, use a larger first rung")
    res: dict[str, Any] = {
        "host": host(),
        "scene": a.scene,
        "seed": a.seed,
        "frame_build_counted": False,
        "rungs": [],
    }
    for n in ladder:
        res["rungs"].append(run_rung(a.scene, n, a.ticks, a.seed, a.settle))
        print(f"rung {n} done", file=sys.stderr, flush=True)
    res["scaling_exponent"] = exponent(res["rungs"])
    if a.profile:
        res["profile"] = {
            "entities": ladder[-1],
            **profile_rung(a.scene, ladder[-1], a.ticks, a.seed, a.settle),
        }
    print(json.dumps(res["host"]))
    print(table(res))
    if a.profile:
        for key in ("cumulative", "tottime"):
            print(f"\nprofile, {ladder[-1]} entities, top 15 by {key}:\n{res['profile'][key]}")
    if a.out:
        with open(a.out, "w") as f:
            json.dump(res, f, indent=2)
    return res


if __name__ == "__main__":
    main()
