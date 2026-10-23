# Real-time scaling: CPU, threading and profiling (local harness PC)

Written 2026-10-22 by the local (WSL) agent session on the owner's harness PC, for the lead. The report is kept as
written (§1). The lead's review and the follow-ups are in §2 and §3. Tags in §1: [MEASURED] was observed on this PC;
[REPO] comes from a repo file; [GENERAL] is general Python knowledge not tested on this sim; [UNKNOWN] was not
measured. §4 has the reference-host bench results (2026-10-23), which close NX-376.

## 1. Report (local session, verbatim)

### Question

Can one live sim keep real time with high traffic or very many entities (for example a "chaos mode": a viewer joins
with 5 to 10 units, near-unlimited budget)? Does threading or profiling matter for that?

### This PC

- [MEASURED] Intel i7-8700, 6 cores / 12 threads. GTX 1070 8 GB. 32 GB RAM (WSL sees about 15.9 GB, the default
  share). Windows 10 Education, WSL 3.0.3.0. Python 3.12.
- The harness runs at `nice 15` (systemd `Nice=15`).

### What a live game needs

- [REPO] `SIM-CORE.md` SC-2: the kernel steps at 10 Hz while running. Real time = 10 ticks/s.

### What the sim delivers today

- [MEASURED] Job #253 (sha `4438a7a`, 6 game hours, 6 workers in parallel, one process per run), ticks/s per run:
  raid-300 228, 207, 230 (seeds 1 to 3); evening-150 305, 313, 391.
- That is about 20x (raid-300) to 30x+ (evening-150) the 10 ticks/s a live game needs, per single process.
- [REPO] README: `surge-500` 167 ticks/s on a 4-core machine, about 17x real time. Different hardware; not
  like-for-like.
- So today's load would use roughly 3% to 5% of one core for the sim step alone.
- [MEASURED] Each worker uses about 43 MB. The GPU sat at 7% and 791 MiB during the job (GTX 1070); the sim does not
  use it.

### What is not known (needs measuring)

- [UNKNOWN] How ticks/s falls as the unit count grows. [REPO] README says cost per tick grows with unit count but not
  the shape. If it is linear, 10x units costs 10x and the headroom (20x to 30x) is still above 1. If any part is
  quadratic (pairwise targeting, nearest-enemy searches), 10x units could cost up to 100x and a chaos mode would miss
  real time. Only a measurement settles this.
- [UNKNOWN] The cost of everything outside the sim step in a live game: WebSocket fan-out to the overlay,
  persistence, the LLM gateway, chat ingestion. The harness measures only the sim.
- [UNKNOWN] Worst-case tick time (jitter). Real time needs each tick under 100 ms, not just the average ticks/s. A
  single slow tick (for example a path recompute) matters more than the mean.

### Threading and profiling for the live case

- Threads: not usable inside `sim-core` (AGENTS.md rule 3, determinism). More cores do not speed up one run. A faster
  single core does.
- Parallelism that is allowed: put work outside the sim step in other processes or threads (rendering, broadcast,
  persistence, LLM, chat), so the sim thread only steps. [GENERAL] This is the usual way to keep a single-threaded
  core fast.
- Profiling matters if chaos mode is a goal: it finds the per-tick hot spots and tells whether the cost is linear in
  units. [GENERAL] `cProfile` or `py-spy` on a seeded run; no code change needed.
- Compiling hot spots (mypyc, Cython, a Rust extension) or PyPy are options only after profiling. [GENERAL]
  [UNKNOWN here]: each must keep state hashes bit-identical, and native code is a new dependency (rule 8).
- Free-threaded Python 3.13+ does not help one deterministic run.

### Proposed measurements (to run when the queue is idle)

1. Ticks/s and per-tick max/p99 for one process at a ladder of entity counts (for example 150, 300, 500, 1000, 2000
   units), same seed. Output: scaling curve and the exponent.
2. `py-spy` or `cProfile` on the largest case: top 10 functions by time.
3. Workers 6, 8 and 12 on one sweep, to find the throughput gain from hyperthreads on this CPU.

Each runs on this PC without changing repo files. The 1 and 2 results decide whether chaos mode is feasible on the
current design.

### Not done / caveats

- No profiling or scaling run has been done yet, because a queue job is running (#259) and a measurement would compete
  with it for CPU.
- The ticks/s above come from 6 parallel workers, which could be slightly slower per process than a single run alone
  [UNKNOWN].
- Hardware: the owner plans to buy a new computer. Single-thread speed matters most for one live sim; core count
  matters for sweeps.

## 2. Lead review (2026-10-23)

The report is sound. Its tagging is honest, and its threading and profiling advice matches the repo's rules. Four
corrections and additions:

1. **The real-time bar is 25 ms, not 100 ms.** SIM-CORE SC-10: p99 of `step` plus the frame build must stay under
   25 ms at 1,000 entities and 500 viewer units. The frame build and snapshot serialization run on the sim thread
   (SIM-CORE §5, Q-SIM-8), so 100 ms per tick is only the hard ceiling. The budget leaves room for those readers and
   for spikes.
2. **This PC is the SC-10 reference host** (Q-TEST-1: the i7-8700 with the GTX 1070 under WSL2), so its numbers are
   the ones that count. SC-10 says to re-baseline when the new PC replaces it.
3. **Part of the scaling question is answered, and part is a known problem:**
   - Spatial queries already use uniform grids, not pairwise scans: combat targeting and sensing (SC-10, NX-372).
     Tasking routes are searched once per node pair per pass. So the design aims at near-linear cost. What is not
     known is the measured curve on the real kernel.
   - The NX-345 spike (`tools/sim-bench/bench.py`, result `docs/review/nx-104-ref.json`) measured a synthetic world on
     this PC: p99 18.9 ms at 1,000 entities, max 41 ms. It is synthetic, not the real kernel.
   - **NX-376 is the known problem:** QA's 1,000-unit convoy scene ran at about 31 ms p99 in the cloud container, over
     the 25 ms line. Single spikes were also seen: 127.8 ms once in 6 h (NX-379 QA), and 35 ms in a 48 h run.
   - The report's measurements 1 and 2 are the measurements NX-376 needs, and this PC is where they count.
4. **"Chaos mode" is a design change, not only a performance question.** One viewer, one unit, a 500-unit cap and a
   FIFO queue are decided (Q-SIM-6, GAMEPLAY §4a). Several units per viewer with an unlimited budget would change
   them. It is recorded as an open owner question (Q-GP-48); the scaling ladder gives its performance facts.

## 3. Follow-ups (recorded 2026-10-23; NX-376 done, see §4)

- **NX-376 (P1):** build a real-kernel scaling bench in the repo:
  - an entity-count ladder of 150, 300, 500, 1,000 and 2,000 units, including QA's 1,000-unit convoy scene;
  - it reports ticks/s, p50, p99 and max per tick, and the top functions from `cProfile` (stdlib; `py-spy` stays a
    tool on the PC, not a repo dependency).

  The lead builds it, and the local session runs it on the reference host when the queue is idle. Results go in
  `docs/review/` with the host details, as `nx-104-ref.json` did. This replaces running ad-hoc scripts on the PC, so
  the numbers can be reproduced.
- **Harness worker count (ops, local session):** compare 6, 8 and 12 workers on one sweep, to see what hyperthreads
  add. This is ops tuning of `queue.yaml` `workers` and needs no code change.
- **Live-stack costs** (WebSocket fan-out, persistence, gateway): measured when those exist (NX-170, NX-171 delta size
  budget, NX-201), within the same SC-10 budget.
- **Q-GP-48 chaos mode:** an owner decision, after the NX-376 ladder.
- **New PC:** re-baseline SC-10 on it (SIM-CORE SC-10). Prefer single-thread speed for the live sim, and cores for
  sweeps.

## 4. Reference-host results (NX-376, 2026-10-23)

Run by the local session on this PC and posted on issue #278. All [MEASURED]. Bench:
`tools/sim-bench/kernel_bench.py`, seed 376, **step only** (no frame build exists yet, so this is a lower bound on
SC-10).

- **Before** the perf fix (#273): sha `774e0db`, one run per rung, ladder 150 to 2,000.
- **After:** sha `9e1dded` (contains #273), three repeats per scene, ladder 500, 1,000 and 2,000. Cells are the median
  of the three; the full min / median / max table is on #278.

| scene | entities | p99 before | p99 after | max after | ticks/s before | ticks/s after |
|---|---|---|---|---|---|---|
| convoy | 500 | 13.8 ms | 7.7 ms | 18.7 ms | 121.6 | 194.3 |
| convoy | 1,000 | 29.2 ms | **16.4 ms** | 32.9 ms | 59.9 | 94.0 |
| convoy | 2,000 | 87.0 ms | 37.0 ms | 59.7 ms | 26.0 | 45.2 |
| mixed | 500 | 10.4 ms | 5.6 ms | 18.1 ms | 182.6 | 317.6 |
| mixed | 1,000 | 30.9 ms | **12.0 ms** | 31.0 ms | 69.4 | 151.1 |
| mixed | 2,000 | 100.8 ms | 27.7 ms | 60.3 ms | 25.2 | 81.1 |

"Before" has no spread (single runs), so the comparison is rough. The mixed scene loses units in combat during the
timed ticks: `entities_after` is 371, 747 and 1,496, the same in all three repeats.

**Reading (lead):**

1. **SC-10 passes for `step` at 1,000 entities**, with about 8.6 ms (convoy) and 13 ms (mixed) left for the frame
   build. The frame's own cost on the real kernel is not measured (NX-345 timed step plus frames together, 9.2 ms
   p99, on a synthetic world on this PC); NX-170 benches step plus frame build on the real kernel.
2. **2,000 entities is over budget** (p99 37 ms convoy, 27.7 ms mixed). That is the ceiling a high-count rule preset
   (Q-GP-48, NX-386) must respect until more optimisation.
3. **Cost now scales about linearly** (log-log slope 0.98 to 1.05 over 500 to 2,000; before, 1.13 to 1.21 over 150
   to 2,000, so not directly comparable). The grid query (`spatial.within`) and `Vec2` construction left the top of the
   profile. Movement (`_move`, `_fly`), combat `_fire` and convoy `steer` lead now.
4. **Single-tick max** reaches about 33 ms at 1,000 entities. That counts against the catch-up rule (SIM-CORE §5),
   not p99. The rare long-run spikes (127.8 ms once in 6 h) were not reproduced here; the soak (NX-033) watches for
   them.

**Worker counts** (same issue, before the fix): 12 harness workers finished a 12-run job 20% faster on wall time than
6, with each run about 25% slower. PR #279 (NX-031) raises the `queue.yaml` `max_workers` cap to 12; the default
stays 2.
