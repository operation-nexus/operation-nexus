# NX-345 SIM-CORE benchmark spike: results

Status: **Done. Reference-host run 2026-10-20; verdict: objects behind the `World` API (owner, Q-SIM-4).** · Tracker: NX-345 · Spec: SIM-CORE SC-10, Q-SIM-4, Q-SIM-17, Q-SIM-18, Q-SIM-24

The verdict comes from the Q-TEST-1 reference host: the owner's i7-8700 under WSL2 (results below). The Mac run further down was indicative only.

## How to run it (reference host)

From the repo root under WSL2, with `uv` installed:

```bash
uv run --locked tools/sim-bench/bench.py --out nx-345-ref.json
```

A run takes about 15 minutes on the Mac: four 36,000-tick runs. Close other heavy programs first. Paste the JSON into a new section below; it records the platform, CPU model and library versions. `--ticks 600` gives a quick smoke run. The script pins Python 3.12 and its own dependencies (`tools/sim-bench/bench.py.lock`), so nothing is added to `services/sim`.

## What it measures

- **World.** Synthetic, on the SIM-CORE §4 theater: 400 × 240 km, `WORLD_DT` = 0.1 s × 6. Speeds come from §4: jets 250 m/s, ground 25 m/s. Sensor and weapon ranges, Pk, damage, cooldowns and the unit mix are **stand-ins**, listed in `KINDS` and `SCENARIOS` at the top of the script.
- **Worst case:** 1,000 entities. 500 are viewer units (coalition jets and armor). The other 500 are AI: 350 enemy mobile units plus 150 radar and SAM sites split between the sides.
- **Idle:** 0 viewers and 150 AI entities (Q-SIM-17).
- **Each tick, in SC-13 order:**
  - Movement: waypoints, plus a new order on arrival.
  - Sensing, every 5 ticks (FOW-5 PROPOSED): each side's tracks.
  - Combat: tracked targets only, nearest first. A `Shot` lands on `(impact_tick, id)`. A shot whose target is gone or untracked fizzles without a draw. Guns land on the fire tick.
  - Lifecycle: a destroyed entity is replaced, with a new id.
  - Frame build: a Delta with changed fields only and 1 m quantization, msgpack-encoded. It is built for both streams. A Snapshot keyframe goes out every 300 ticks.
- **Objects arm:** one `__slots__` object per entity, kept in id order (SC-4), with a uniform grid per side whose cell is max sensor radius / 2 (SC-10). A query walks only the opposing side's grid.
- **NumPy arm:** hot fields in arrays, with brute-force per-side distance matrices instead of the grid.
- **Keyframes:** on a keyframe tick the Snapshot replaces that tick's Delta.
- **Timed:** `step` plus building and encoding both frames (SC-10, Q-SIM-8). Compression is off the sim thread (§5), so it is not timed. zlib level 6 stands in for zstd (owner, 2026-10-19). The first 100 ticks are warm-up. The garbage collector stays on.
- **"Pass"** means movement + sensing + combat: the Q-SIM-4 ~10 ms threshold.
- **Redacted stream:** coalition units plus enemy units the coalition tracks (Tier 2). It has **no SIGINT blobs** and no last-known tracks. An event is kept only when every entity it names is visible this tick or was visible last tick, so the coalition still sees the kill of a unit it tracked.
- **Built-in check:** each run ends with assertions. The entity count holds, ids stay in order, no entity leaves the map, the redacted stream holds only coalition entities and coalition tracks, and shots land in `(impact_tick, id)` order.

## Reference run: Intel i7-8700 @ 3.20 GHz (12 threads), WSL2 (Linux 6.18.40.1-microsoft-standard), Python 3.12.15, NumPy 2.5.4, msgpack 1.2.3, 2026-10-20

Run by the owner: `uv run --locked tools/sim-bench/bench.py --out nx-345-ref.json`, 36,000 ticks per run, seed 345. Times in ms.

| Scenario | Arm | step+frames p50 | p99 | max | pass p99 | pass p99, sensing ticks | frames p99 | shots/tick |
|---|---|---|---|---|---|---|---|---|
| worst (1,000) | objects | 4.12 | 9.18 | 22.91 | 7.60 | 8.19 | 1.89 | 7.8 |
| worst (1,000) | numpy | 3.41 | 7.94 | 12.81 | 6.00 | 6.48 | 2.15 | 7.9 |
| idle (150) | objects | 0.50 | 1.00 | 1.90 | 0.81 | 0.96 | 0.24 | 0.2 |
| idle (150) | numpy | 0.34 | 0.48 | 1.25 | 0.27 | 0.32 | 0.25 | 0.2 |

p99 per system in the worst case (objects / numpy): movement 0.79 / 0.14, sensing 4.63 / 3.72, combat 2.65 / 3.04, frames 1.89 / 2.15.

Bytes per game hour, in MB (10⁶ bytes):

| Scenario | Arm | truth raw | truth zlib | redacted raw | redacted zlib |
|---|---|---|---|---|---|
| worst | objects | 595.4 | 251.9 | 570.3 | 238.1 |
| worst | numpy | 596.0 | 252.5 | 569.4 | 237.6 |
| idle | objects | 69.1 | 23.6 | 53.3 | 18.2 |
| idle | numpy | 68.4 | 23.4 | 54.9 | 18.9 |

### Verdict (owner, 2026-10-20)
1. **SC-10 budget: pass.** step + frames p99 is 9.2 ms (objects) and 7.9 ms (NumPy), against 25 ms. The single worst tick (22.9 ms objects, 12.8 ms NumPy) stays under the budget and counts against the catch-up rule (SIM-CORE §5), not p99.
2. **Idle: pass.** About 1 ms per tick with objects.
3. **Storage (Q-SIM-4): objects behind the `World` API.** The objects pass p99 is 7.6 ms (8.2 ms on sensing ticks), under the ~10 ms threshold with about 2 ms to spare. Sensing dominates and uses stand-in radar ranges, so the real kernel's benchmark (NX-104) re-checks it; the `World` API keeps a NumPy switch contained.
4. **Recording size:** about 252 MB (truth) and 238 MB (redacted) per game hour at the worst case with zlib, about 12 GB a day for both streams if a whole day ran at the worst case; idle about 42 MB per hour. Feeds Q-SIM-29.
5. **Cross-platform check:** the byte counts equal the Mac run's exactly, so the same seed produced the same frames on a different CPU and OS. Evidence for determinism across machines for this synthetic world only, not the real kernel.

## Indicative run: Apple M2 Pro, macOS 26.3, Python 3.12.15, NumPy 2.5.4, msgpack 1.2.3, 2026-10-19

36,000 ticks (one game hour) per run, seed 345. Times are in ms.

| Scenario | Arm | step+frames p50 | p99 | max | pass p99 | pass p99, sensing ticks | frames p99 | shots/tick |
|---|---|---|---|---|---|---|---|---|
| worst (1,000) | objects | 3.90 | 8.94 | 32.98 | 7.30 | 8.31 | 2.33 | 7.8 |
| worst (1,000) | numpy | 2.72 | 5.06 | 22.00 | 3.27 | 4.08 | 2.35 | 7.9 |
| idle (150) | objects | 0.44 | 1.01 | 9.21 | 0.79 | 0.96 | 0.24 | 0.2 |
| idle (150) | numpy | 0.24 | 0.58 | 10.36 | 0.25 | 0.38 | 0.33 | 0.2 |

p99 per system in the worst case (objects / numpy): movement 0.93 / 0.08, sensing 4.42 / 1.61, combat 2.85 / 2.18, frames 2.33 / 2.35.

Bytes per game hour, in MB (10⁶ bytes):

| Scenario | Arm | truth raw | truth zlib | redacted raw | redacted zlib |
|---|---|---|---|---|---|
| worst | objects | 595.4 | 251.9 | 570.3 | 238.1 |
| worst | numpy | 596.0 | 252.5 | 569.4 | 237.6 |
| idle | objects | 69.1 | 23.6 | 53.3 | 18.2 |
| idle | numpy | 68.4 | 23.4 | 54.9 | 18.9 |

## What the Mac run suggested (superseded by the reference run above)

1. **SC-10 budget:** step + frames p99 is under 25 ms for both arms on this Mac.
2. **Storage verdict (Q-SIM-4):** the objects pass p99 is **7.3 ms (8.3 ms on sensing ticks)**, under the ~10 ms threshold on the Mac but without much room. NumPy is 3.3 ms. The verdict depends on how the i7-8700 under WSL2 compares per core with this Mac, which is not measured here [UNVERIFIED]. A first version with one grid for both sides measured 11.3 ms: the threshold is sensitive to how the objects code is written, not only to the storage.
3. **Sensing dominates the objects arm.** The SC-10 cell rule (max sensor radius / 2) with a 120 km stand-in radar gives 60 km cells. That is a 7 × 4 grid, so most queries scan most of the map. The real radar ranges in the unit catalog decide how much the grid helps.
4. **The max column is jitter.** The single worst tick (9–33 ms) appears in every run, including the 0.2-shot idle NumPy run, so it is likely the GC or the OS, not the systems. It counts against the catch-up rule (SIM-CORE §5), not p99. The reference run should show whether it repeats.
5. **Frame size is at the WP-4 limit.** The average truth frame is about 16.5 KB raw (595 MB / 36,000 ticks, keyframes included), because every moving unit changes x and y every tick. WP-4 wants a p95 Delta under 16 KB at 1,000 entities. Lower precision for positions, or sending positions less often, would be a WIRE-PROTOCOL decision, not a spike one.
6. **The redacted stream is about as large as the full-truth stream** with the stand-in sensors: 25 coalition radars at 120 km see most of the map. With catalog ranges it will shrink.
7. **Recording storage:** about 250 MB per stream per game hour at the worst case with zlib, so about 12 GB a day for the two streams together if a whole day ran at the worst case. The idle case is about 40 MB/hour for both.

## Not covered

- SIGINT blobs, last-known tracks and terrain masking.
- Logistics, capture, objectives and the director.
- Snapshots every 300 ticks and `state_hash` every 100.
- The SC-4 tie-break by id in the NumPy arm: argmin picks the lowest slot.
- Chat-ingest and WebSocket jitter from the sim thread sharing the GIL (§5 Q-SIM-9).

The real kernel measures these when it exists: NX-104 has a benchmark acceptance.
