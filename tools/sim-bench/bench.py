# /// script
# requires-python = "==3.12.*"
# dependencies = ["numpy==2.5.4", "msgpack==1.2.3"]
# ///
"""NX-345 SIM-CORE benchmark spike. Throwaway: the real World API is NX-101/NX-104.

Measures, per SIM-CORE SC-10, Q-SIM-4, Q-SIM-17 and Q-SIM-18:
  1. p99 of `step` plus the frame build at 1,000 entities and 500 viewer units,
  2. the idle case (0 viewers, 150 AI entities),
  3. Python objects versus NumPy arrays for the movement, sensor and combat pass,
  4. bytes per game hour of the redacted coalition and the full-truth frame streams.

  uv run tools/sim-bench/bench.py                   full game hour, both arms, both scenarios
  uv run tools/sim-bench/bench.py --ticks 600       quick smoke run

The world is synthetic. Speeds come from SIM-CORE §4; every other number in KINDS and SCENARIOS
is a STAND-IN until the unit catalog exists, so the timings show cost, not balance.
"""

# Seeded PRNGs are the point (S311); asserts are the spike's checks, never run with -O (S101).
# ruff: noqa: S101, S311

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import platform
import random
import statistics
import sys
import zlib
from time import perf_counter_ns

import msgpack
import numpy as np

TICK_DT = 0.1  # SC-2
WORLD_DT = TICK_DT * 6  # sim.time_scale default 6x (SIM-CORE §4)
W, H = 400_000.0, 240_000.0  # theater ~400 x 240 km (SIM-CORE §4)
FOW_EVERY = 5  # fow.track_every_ticks, PROPOSED (FOW-5)
KEYFRAME_EVERY = 300  # a Snapshot keyframe in each recorded stream (owner, 2026-10-19)
HOUR_TICKS = 36_000
WARMUP = 100
COAL, ENEMY = 0, 1
EV_FIRE, EV_HIT, EV_MISS, EV_DEAD, EV_SPAWN = range(5)

# name, speed m/s, sensor m, weapon m, pk, damage, cooldown ticks, munition m/s (0 = gun, lands on
# the fire tick). Speeds from SIM-CORE §4; the rest are STAND-INS.
KINDS = [
    ("jet", 250.0, 40_000.0, 20_000.0, 0.5, 40, 30, 1000.0),
    ("armor", 25.0, 8_000.0, 3_000.0, 0.3, 20, 20, 0.0),
    ("radar", 0.0, 120_000.0, 0.0, 0.0, 0, 0, 0.0),
    ("sam", 0.0, 60_000.0, 40_000.0, 0.4, 40, 50, 1000.0),
]
JET, ARMOR, RADAR, SAM = range(4)
MAX_HP = 100
CELL = max(k[2] for k in KINDS) / 2  # SC-10: cell = max sensor radius / 2
NX, NY = math.ceil(W / CELL), math.ceil(H / CELL)

# (side, kind, count). STAND-IN mixes; worst = 500 viewer units (the coalition jets and armor)
# plus 500 AI entities; idle = 0 viewers and 150 AI entities (Q-SIM-17).
SCENARIOS = {
    "worst": [
        (COAL, JET, 250),
        (COAL, ARMOR, 250),
        (ENEMY, JET, 150),
        (ENEMY, ARMOR, 200),
        (COAL, RADAR, 25),
        (COAL, SAM, 50),
        (ENEMY, RADAR, 25),
        (ENEMY, SAM, 50),
    ],
    "idle": [
        (COAL, RADAR, 10),
        (COAL, SAM, 15),
        (ENEMY, RADAR, 10),
        (ENEMY, SAM, 15),
        (ENEMY, JET, 40),
        (ENEMY, ARMOR, 60),
    ],
}


class Ent:
    __slots__ = ("cd", "hp", "id", "kind", "side", "wx", "wy", "x", "y")


class ObjWorld:
    """Arm A: one Python object per entity, a dict in id order (SC-4), a uniform grid."""

    def __init__(self, comp: list[tuple[int, int, int]], seed: int) -> None:
        self.orders, self.combat_rng = random.Random(seed), random.Random(seed + 1)
        self.ents: dict[int, Ent] = {}
        self.next_id = self.next_shot = self.tick = 0
        self.shots: list[tuple[int, int, int, int, int, int]] = []
        self.tracks: list[set[int]] = [set(), set()]
        self.dead: list[Ent] = []
        for side, kind, n in comp:
            for _ in range(n):
                self.spawn(side, kind)

    def spawn(self, side: int, kind: int) -> Ent:
        e = Ent()
        e.id, e.side, e.kind, e.hp, e.cd = self.next_id, side, kind, MAX_HP, 0
        e.x, e.y = self.orders.uniform(0, W), self.orders.uniform(0, H)
        e.wx, e.wy = self.orders.uniform(0, W), self.orders.uniform(0, H)
        self.ents[e.id] = e
        self.next_id += 1
        return e

    def near(self, side: int, x: float, y: float, r: float) -> list[Ent]:
        """Entities of `side` in the cells that a circle of radius r touches."""
        grid, out = self.grid[side], list[Ent]()
        for cx in range(max(int((x - r) // CELL), 0), min(int((x + r) // CELL), NX - 1) + 1):
            for cy in range(max(int((y - r) // CELL), 0), min(int((y + r) // CELL), NY - 1) + 1):
                out.extend(grid[cx * NY + cy])
        return out

    def step(self) -> tuple[list[tuple[int, ...]], dict[str, int]]:
        t, ts, ev = self.tick, {}, []
        a = perf_counter_ns()
        for e in self.ents.values():
            s = KINDS[e.kind][1] * WORLD_DT
            if not s:
                continue
            dx, dy = e.wx - e.x, e.wy - e.y
            d = math.hypot(dx, dy)
            if d <= s:  # arrived: a new order (stands in for director/AI orders)
                e.x, e.y = e.wx, e.wy
                e.wx, e.wy = self.orders.uniform(0, W), self.orders.uniform(0, H)
            else:
                e.x += dx / d * s
                e.y += dy / d * s
        self.grid: list[list[list[Ent]]] = [[[] for _ in range(NX * NY)] for _ in (COAL, ENEMY)]
        for e in self.ents.values():
            cell = min(int(e.x // CELL), NX - 1) * NY + min(int(e.y // CELL), NY - 1)
            self.grid[e.side][cell].append(e)
        b = perf_counter_ns()
        if t % FOW_EVERY == 0:
            for side in (COAL, ENEMY):
                found: set[int] = set()
                for e in self.ents.values():
                    if e.side != side:
                        continue
                    r = KINDS[e.kind][2]
                    r2 = r * r
                    for o in self.near(1 - side, e.x, e.y, r):
                        if o.id not in found:
                            if (o.x - e.x) ** 2 + (o.y - e.y) ** 2 <= r2:
                                found.add(o.id)
                self.tracks[side] = found
        c = perf_counter_ns()
        for e in self.ents.values():  # new shots fire, then pending impacts land (SC-13)
            if e.cd > 0:
                e.cd -= 1
                continue
            k = KINDS[e.kind]
            if not k[3]:
                continue
            mine, best, bd = self.tracks[e.side], None, k[3] * k[3]
            for o in self.near(1 - e.side, e.x, e.y, k[3]):
                if o.id in mine:
                    d2 = (o.x - e.x) ** 2 + (o.y - e.y) ** 2
                    if d2 < bd or (d2 == bd and (best is None or o.id < best.id)):
                        best, bd = o, d2
            if best is None:
                continue
            e.cd = k[6]
            it = t + math.ceil(math.sqrt(bd) / k[7] / WORLD_DT) if k[7] else t
            heapq.heappush(self.shots, (it, self.next_shot, e.id, e.kind, e.side, best.id))
            self.next_shot += 1
            ev.append((EV_FIRE, e.id, best.id))
        self.land(t, ev)
        d = perf_counter_ns()
        for e in self.dead:
            del self.ents[e.id]
            ev.append((EV_DEAD, e.id))
            ev.append((EV_SPAWN, self.spawn(e.side, e.kind).id))
        self.dead = []
        ts.update(move=b - a, sense=c - b, combat=d - c, life=perf_counter_ns() - d)
        self.tick += 1
        return ev, ts

    def land(self, t: int, ev: list[tuple[int, ...]]) -> None:
        last = (-1, -1)
        while self.shots and self.shots[0][0] <= t:
            it, sid, shooter, kind, side, target = heapq.heappop(self.shots)
            assert (it, sid) > last, "shots land in (impact_tick, id) order"
            last = (it, sid)
            o = self.ents.get(target)
            # Fizzle with no draw when the target is gone or no longer tracked (Q-FOW-16).
            if o is None or o.hp <= 0 or target not in self.tracks[side]:
                ev.append((EV_MISS, shooter, target))
            elif self.combat_rng.random() < KINDS[kind][4]:
                o.hp -= KINDS[kind][5]
                ev.append((EV_HIT, shooter, target))
                if o.hp <= 0:
                    self.dead.append(o)
            else:
                ev.append((EV_MISS, shooter, target))

    def rows(self) -> list[tuple[int, int, int, int, int, int]]:
        return [(e.id, round(e.x), round(e.y), e.hp, e.kind, e.side) for e in self.ents.values()]

    def coalition_tracks(self) -> set[int]:
        return self.tracks[COAL]


class NpWorld:
    """Arm B: hot fields in NumPy arrays, one slot per entity; brute-force distance matrices."""

    def __init__(self, comp: list[tuple[int, int, int]], seed: int) -> None:
        self.orders, self.combat_rng = np.random.default_rng(seed).spawn(2)
        kind = np.array([k for _, k, n in comp for _ in range(n)], dtype=np.int64)
        self.side = np.array([s for s, _, n in comp for _ in range(n)], dtype=np.int64)
        self.kind, n = kind, len(kind)
        col = np.array(KINDS, dtype=object)
        self.step_m = col[kind, 1].astype(float) * WORLD_DT
        self.sensor2 = col[kind, 2].astype(float) ** 2
        self.weapon2 = col[kind, 3].astype(float) ** 2
        self.mspeed = col[kind, 7].astype(float)
        self.cooldown = col[kind, 6].astype(np.int64)
        self.id = np.arange(n)
        self.slot_of = {i: i for i in range(n)}
        self.next_id, self.next_shot, self.tick = n, 0, 0
        self.x, self.wx = self.orders.uniform(0, W, n), self.orders.uniform(0, W, n)
        self.y, self.wy = self.orders.uniform(0, H, n), self.orders.uniform(0, H, n)
        self.hp, self.cd = np.full(n, MAX_HP), np.zeros(n, dtype=np.int64)
        self.tracked = [np.zeros(n, bool), np.zeros(n, bool)]
        self.shots: list[tuple[int, int, int, int, int, int]] = []

    def step(self) -> tuple[list[tuple[int, ...]], dict[str, int]]:
        t, ts, ev = self.tick, {}, []
        a = perf_counter_ns()
        dx, dy = self.wx - self.x, self.wy - self.y
        d = np.hypot(dx, dy)
        mob = self.step_m > 0
        arr = mob & (d <= self.step_m)
        f = np.zeros_like(d)
        np.divide(self.step_m, d, out=f, where=mob & ~arr)
        self.x += dx * f
        self.y += dy * f
        self.x[arr], self.y[arr] = self.wx[arr], self.wy[arr]
        n = int(arr.sum())
        if n:
            self.wx[arr], self.wy[arr] = self.orders.uniform(0, W, n), self.orders.uniform(0, H, n)
        b = perf_counter_ns()
        if t % FOW_EVERY == 0:
            for s in (COAL, ENEMY):
                sens = np.flatnonzero(self.side == s)
                tgt = np.flatnonzero(self.side != s)
                dx2 = (self.x[sens, None] - self.x[tgt]) ** 2
                d2 = dx2 + (self.y[sens, None] - self.y[tgt]) ** 2
                tr = np.zeros(len(self.id), bool)
                tr[tgt[(d2 <= self.sensor2[sens, None]).any(axis=0)]] = True
                self.tracked[s] = tr
        c = perf_counter_ns()
        ready = (self.cd == 0) & (self.weapon2 > 0)
        self.cd[self.cd > 0] -= 1
        for s in (COAL, ENEMY):
            sh = np.flatnonzero(ready & (self.side == s))
            tg = np.flatnonzero(self.tracked[s])
            if not len(sh) or not len(tg):
                continue
            d2 = (self.x[sh, None] - self.x[tg]) ** 2 + (self.y[sh, None] - self.y[tg]) ** 2
            d2[d2 > self.weapon2[sh, None]] = np.inf
            # ponytail: argmin ties go to the lowest slot, not the lowest id (SC-4); fine here.
            j = d2.argmin(axis=1)
            best = d2[np.arange(len(sh)), j]
            ok = np.isfinite(best)
            shooters, targets = sh[ok], tg[j[ok]]
            self.cd[shooters] = self.cooldown[shooters]
            ms, dist = self.mspeed[shooters], np.sqrt(best[ok])
            flight = np.zeros_like(dist)
            np.divide(dist, ms * WORLD_DT, out=flight, where=ms > 0)
            impact = t + np.ceil(flight).astype(np.int64)
            for p, q, it in zip(shooters.tolist(), targets.tolist(), impact.tolist(), strict=True):
                sid, tid = int(self.id[p]), int(self.id[q])
                heapq.heappush(self.shots, (it, self.next_shot, sid, int(self.kind[p]), s, tid))
                self.next_shot += 1
                ev.append((EV_FIRE, sid, tid))
        dead = self.land(t, ev)
        e = perf_counter_ns()
        for p in dead:
            old = int(self.id[p])
            del self.slot_of[old]
            self.id[p], self.slot_of[self.next_id] = self.next_id, p
            self.x[p], self.wx[p] = self.orders.uniform(0, W, 2)
            self.y[p], self.wy[p] = self.orders.uniform(0, H, 2)
            self.hp[p], self.cd[p] = MAX_HP, 0
            self.tracked[COAL][p] = self.tracked[ENEMY][p] = False
            ev.append((EV_DEAD, old))
            ev.append((EV_SPAWN, self.next_id))
            self.next_id += 1
        ts.update(move=b - a, sense=c - b, combat=e - c, life=perf_counter_ns() - e)
        self.tick += 1
        return ev, ts

    def land(self, t: int, ev: list[tuple[int, ...]]) -> list[int]:
        dead, last = [], (-1, -1)
        while self.shots and self.shots[0][0] <= t:
            it, sid, shooter, kind, side, target = heapq.heappop(self.shots)
            assert (it, sid) > last, "shots land in (impact_tick, id) order"
            last = (it, sid)
            p = self.slot_of.get(target)
            if p is None or self.hp[p] <= 0 or not self.tracked[side][p]:
                ev.append((EV_MISS, shooter, target))
            elif self.combat_rng.random() < KINDS[kind][4]:
                self.hp[p] -= KINDS[kind][5]
                ev.append((EV_HIT, shooter, target))
                if self.hp[p] <= 0:
                    dead.append(p)
            else:
                ev.append((EV_MISS, shooter, target))
        return dead

    def rows(self) -> list[tuple[int, int, int, int, int, int]]:
        cols = (self.id, np.rint(self.x).astype(np.int64), np.rint(self.y).astype(np.int64))
        cols += (self.hp, self.kind, self.side)
        return list(zip(*(c.tolist() for c in cols), strict=True))

    def coalition_tracks(self) -> set[int]:
        return set(self.id[self.tracked[COAL]].tolist())


class Stream:
    """One recorded frame stream: a WIRE-PROTOCOL-shaped Delta every tick, changed fields only,
    positions quantized to 1 m, plus a Snapshot keyframe every KEYFRAME_EVERY ticks. Compression
    runs off the sim thread (SIM-CORE §5), so it is outside the timed region; zlib stands in for
    zstd (owner, 2026-10-19)."""

    def __init__(self) -> None:
        self.last: dict[int, tuple[int, ...]] = {}
        self.raw = self.packed = 0
        self.z = zlib.compressobj(6)

    def build(self, tick: int, rows: list[tuple[int, ...]], ev: list[tuple[int, ...]]) -> bytes:
        ups, new = [], {}
        for r in rows:
            i, prev = r[0], self.last.get(r[0])
            new[i] = r
            if prev is None:
                ups.append({"i": i, "x": r[1], "y": r[2], "h": r[3], "k": r[4], "s": r[5]})
            elif prev != r:
                u = {"i": i}
                for key, col in (("x", 1), ("y", 2), ("h", 3)):
                    if prev[col] != r[col]:
                        u[key] = r[col]
                ups.append(u)
        removes = [i for i in self.last if i not in new]
        self.last = new
        if tick % KEYFRAME_EVERY == 0:  # the Snapshot replaces that tick's Delta
            return msgpack.packb({"t": tick, "snap": rows, "e": ev})
        return msgpack.packb({"t": tick, "b": tick - 1, "u": ups, "r": removes, "e": ev})

    def store(self, frame: bytes) -> None:
        self.raw += len(frame)
        self.packed += len(self.z.compress(frame))

    def close(self) -> None:
        self.packed += len(self.z.flush())


def pct(xs: list[float], q: int) -> float:
    return statistics.quantiles(xs, n=100, method="inclusive")[q - 1] if len(xs) > 1 else xs[0]


def run(arm: str, scenario: str, ticks: int, seed: int) -> dict[str, object]:
    comp = SCENARIOS[scenario]
    w = ObjWorld(comp, seed) if arm == "objects" else NpWorld(comp, seed)
    truth, red = Stream(), Stream()
    rec: dict[str, list[float]] = {k: [] for k in ("move", "sense", "combat", "life", "frames")}
    total, sense_ticks, shots = [], [], 0
    for _ in range(ticks):
        t0 = perf_counter_ns()
        ev, ts = w.step()
        rows, tracked = w.rows(), w.coalition_tracks()
        vis_rows = [r for r in rows if r[5] == COAL or r[0] in tracked]
        # Visible now or last tick, so the coalition still sees the kill of a unit it tracked.
        vis = {r[0] for r in vis_rows} | red.last.keys()
        vis_ev = [e for e in ev if all(i in vis for i in e[1:])]
        ft, fr = truth.build(w.tick - 1, rows, ev), red.build(w.tick - 1, vis_rows, vis_ev)
        t1 = perf_counter_ns()
        truth.store(ft)
        red.store(fr)
        shots += sum(1 for e in ev if e[0] == EV_FIRE)
        if w.tick - 1 < WARMUP:
            continue
        for k, v in ts.items():
            rec[k].append(v / 1e6)
        rec["frames"].append((t1 - t0 - sum(ts.values())) / 1e6)
        total.append((t1 - t0) / 1e6)
        if (w.tick - 1) % FOW_EVERY == 0:
            sense_ticks.append((ts["move"] + ts["sense"] + ts["combat"]) / 1e6)
    truth.close()
    red.close()
    # The spike's runnable check: entity count holds, ids stay in order, nothing leaves the map,
    # and the redacted stream holds only coalition entities and coalition tracks.
    rows = w.rows()
    assert len(rows) == sum(n for _, _, n in comp)
    assert arm != "objects" or [r[0] for r in rows] == sorted(r[0] for r in rows)
    assert all(0 <= r[1] <= W and 0 <= r[2] <= H for r in rows)
    coal = {r[0] for r in rows if r[5] == COAL}
    assert set(red.last) <= coal | w.coalition_tracks()
    scale = HOUR_TICKS / ticks
    passes = [m + s + c for m, s, c in zip(rec["move"], rec["sense"], rec["combat"], strict=True)]
    return {
        "arm": arm,
        "scenario": scenario,
        "entities": len(rows),
        "ticks": ticks,
        "step_plus_frames_ms": {"p50": pct(total, 50), "p99": pct(total, 99), "max": max(total)},
        "pass_ms_p99": pct(passes, 99),
        "pass_ms_p99_sense_ticks": pct(sense_ticks, 99),
        "system_ms_p99": {k: pct(v, 99) for k, v in rec.items()},
        "shots_per_tick": shots / ticks,
        "bytes_per_game_hour": {
            "truth_raw": round(truth.raw * scale),
            "truth_zlib": round(truth.packed * scale),
            "redacted_raw": round(red.raw * scale),
            "redacted_zlib": round(red.packed * scale),
        },
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
        "numpy": np.__version__,
        "msgpack": ".".join(map(str, msgpack.version)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--ticks", type=int, default=HOUR_TICKS, help="ticks per run (36,000 = 1 h)")
    ap.add_argument("--arm", choices=["objects", "numpy", "both"], default="both")
    ap.add_argument("--scenario", choices=["worst", "idle", "both"], default="both")
    ap.add_argument("--seed", type=int, default=345)
    ap.add_argument("--out", help="also write the results as JSON to this path")
    a = ap.parse_args()
    if a.ticks <= WARMUP + 1:
        ap.error(f"--ticks must be more than {WARMUP + 1} (the first {WARMUP} are warm-up)")
    arms = ["objects", "numpy"] if a.arm == "both" else [a.arm]
    scenarios = ["worst", "idle"] if a.scenario == "both" else [a.scenario]
    out = {"host": host(), "runs": []}
    print(json.dumps(out["host"]))
    for sc in scenarios:
        for arm in arms:
            res = run(arm, sc, a.ticks, a.seed)
            out["runs"].append(res)
            print(json.dumps(res), flush=True)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
