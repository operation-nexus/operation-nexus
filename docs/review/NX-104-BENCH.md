# NX-104 uniform-grid benchmark

Status: **Reference-host run done (owner, 2026-10-21): acceptance met.** · Tracker: NX-104 · Spec: SIM-CORE SC-4, SC-10, §4

## How to run it (reference host)

From the repo root under WSL2 on the Q-TEST-1 reference host (i7-8700), with `uv` installed and `make bootstrap` done:

```bash
uv run --frozen --project services/sim python tools/sim-bench/grid_bench.py --out nx-104-ref.json
```

It runs in the sim project's own locked environment, because it imports the real `nexus.core`. The default is 36,000 ticks (one game hour) per scenario; `--ticks 600` gives a quick smoke run. Close other heavy programs first, and paste the JSON into a new section below. It records the platform, CPU model and Python version.

## What it measures

- **Timed, per tick:** `UniformGrid.rebuild` over every entity, plus one `query_radius` per entity at that entity's sensor radius. Waypoint movement runs every tick but is not timed. The first 100 ticks are warm-up, and the garbage collector stays on.
- **World:** real `World.spawn` entities on the SIM-CORE §4 theater (400 × 240 km), moving toward random waypoints at the §4 speeds (jets 250 m/s, ground 25 m/s) × `WORLD_DT` (0.1 s × 6).
- **Scenarios:** the NX-345 mixes. "worst" is 1,000 entities, 500 of them viewer units; "idle" is 150 AI entities and 0 viewers (Q-SIM-17).
- **Stand-ins:** sensor radii are the NX-345 **STAND-INS** (jets 40 km, ground 8 km, radar 120 km, air defense 60 km) until the unit catalog exists (NX-106). The cell is max sensor radius / 2 (SC-10), so 60 km here, as in NX-345.
- **Compared with NX-345:** that spike's sensing pass queried only the opposing side, and only every 5 ticks (FOW-5 PROPOSED). This bench queries every entity, both sides, every tick, and sorts each result by id (SC-4). It is an upper bound for one sensing pass, not a whole `step`.

## Reference-host run (decides NX-104)

Owner's broadcast host (Q-TEST-1): Intel Core i7-8700 @ 3.20 GHz, 12 logical CPUs, WSL2 (Linux 6.18.54.1-microsoft-standard, glibc 2.43), Python 3.12.15, 2026-10-21. Command as above, default 36,000 ticks per scenario, seed 104. Raw output: [`nx-104-ref.json`](nx-104-ref.json). Times in ms.

| Scenario | rebuild + queries p50 | p95 | p99 | max | rebuild p99 | hits per query |
|---|---|---|---|---|---|---|
| worst (1,000) | 16.18 | 17.40 | 18.86 | 41.45 | 0.39 | 55.8 |
| idle (150) | 0.68 | 0.74 | 1.06 | 4.48 | 0.07 | 13.8 |

1. **NX-104 acceptance is met:** p99 18.9 ms at 1,000 entities, under the 25 ms bar.
2. **The reference host is about 1.27× slower than the cloud container** (p99 18.9 vs 14.9 ms). Container timings elsewhere in the repo should be scaled by about that much.
3. **This bench is an upper bound, not the Q-SIM-4 pass.** Every entity queries every tick here; the real sensing pass (FOG-OF-WAR, NX-150) queries only the opposing side and only every `fow.track_every_ticks` (5). Its container median at 1,000 entities is about 7–8.6 ms per pass, so about 9–11 ms on this host: at the ~10 ms Q-SIM-4 line. The Q-SIM-4 re-check therefore needs the real pass on this host, see below.
4. **The 41 ms max is one outlier in 36,000 ticks** (likely WSL scheduling or the garbage collector, which stays on). p99 is the measure; the soak (NX-033) should still watch the tail.
5. **Idle load is negligible** (1.06 ms p99 at 150 AI-only entities).

**Next reference-host measurement (owner, when convenient):** the real sensing pass at 1,000 entities, from the repo root on this host after `git pull` and `make bootstrap`:

```bash
uv run --frozen --project services/sim pytest services/sim/tests/core/test_fog.py -s -k sc10
```

It prints `5 ticks incl. one sensing pass at 1,000 entities: <ms>`. Run it a few times; if a sensing tick stays above about 10 ms, Q-SIM-4 (NumPy for hot fields) is reopened.

## Local run: container, NOT the reference host

The numbers below are indicative only and do not decide SC-10.

Cloud agent container: "Intel(R) Xeon(R) Processor" (model not reported), 4 CPUs, Linux 6.18.44, Python 3.12.3, 2026-10-21. Command as above with the default 36,000 ticks per scenario, seed 104. Times in ms.

| Scenario | rebuild + queries p50 | p95 | p99 | max | rebuild p99 | hits per query |
|---|---|---|---|---|---|---|
| worst (1,000) | 12.06 | 12.81 | 14.92 | 26.91 | 0.32 | 55.8 |
| idle (150) | 0.55 | 0.60 | 0.63 | 5.51 | 0.05 | 13.8 |

What it suggests, pending the reference run:

1. **The rebuild is cheap** (0.3 ms p99 at 1,000 entities), so incremental updates are not needed.
2. **The queries dominate.** With the 120 km stand-in radar the cell is 60 km, a 7 × 4 grid, so a radar query scans most of the map (the NX-345 finding). Real catalog ranges decide how much smaller cells help.
3. **Acceptance is met indicatively:** p99 14.9 ms at 1,000 entities is under the NX-104 bar of 25 ms on this container; the reference-host run decides it. But this worst case (every entity querying every tick) leaves little of the SC-10 budget for the other systems, and the grid pass alone is above the ~10 ms point where Q-SIM-4 would move hot fields to NumPy. Callers (FOG-OF-WAR sensing, combat) should query at their own cadence and only what they need, as NX-345 did; the reference run feeds that Q-SIM-4 check.
