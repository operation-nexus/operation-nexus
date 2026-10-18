# SPEC: Simulation Core

Status: Draft · Tracker: NX-100…NX-119 · ADRs: 0002, 0003

## 1. Purpose
This is the authoritative, deterministic world simulation. Everything else is input to it or a view of it.

## 2. Goals / Non-goals
- Goals: determinism, testability, a predictable tick budget, recovery from snapshots.
- Non-goals: rendering, networking, persistence I/O, and LLM calls (those live outside the kernel).

## 3. Requirements
- **SC-1** `step(state, commands, rng) -> (state, events)` MUST be pure: no I/O, no wall clock, no global mutable state.
- **SC-2** Tick rate is 10 Hz of sim time. `TICK_DT = 0.1`. All rates in config are per second and are multiplied by `TICK_DT`.
- **SC-3** Given the same seed, config hash and command log, every replay MUST produce identical `state_hash` checkpoints on the same platform.
- **SC-4** Entities have sequential integer ids. Every iteration over entities happens in id order.
- **SC-5** All randomness MUST come from `SimRng` sub-streams named per subsystem (`combat`, `director`, `spawn`, `fow`, `objective`; never shared between subsystems, Q-SM-1).
- **SC-6** Commands MUST be applied in `(target_tick, arrival_seq)` order. Commands for past ticks MUST be applied at the current tick and flagged `late`.
- **SC-7** Invalid commands MUST produce a `CommandRejected{reason}` event, never an exception.
- **SC-8** An exception inside `step` MUST NOT corrupt state. The runtime keeps the previous state, logs a crash bundle, and fails over to restore-from-snapshot.
- **SC-9** Snapshots MUST round-trip losslessly: `hash(load(save(s))) == hash(s)`.
- **SC-10** Budgets: p99 `step` time < 25 ms at 1,000 entities and 300 viewer units on the reference host. Spatial queries use a uniform grid (cell = max sensor radius / 2) instead of O(n²) scans.

## 4. World model (component-style, flat)
```
Entity { id:int, kind:UnitKind, side:Side(COALITION|ENEMY), domain:Domain(AIR|GROUND|SEA|STATIC),
         pos:Vec2(m), vel:Vec2(m/s), alt_band:(NOE|LOW|MED|HIGH) for AIR,
         hp:int, damage_state:DamageState(HEALTHY|DAMAGED|MISSION_KILL|DISABLED),
         fuel:fixed, munitions:{<weapon_id>:int}, gun_rounds:int, cargo:int,
         stance:Stance(PRESS|STANDARD|CAUTIOUS|GUNS),
         crew:{count:int, status:Crew(ABOARD|DOWNED|RESCUED|CAPTURED|LOST)},
         sensor:SensorProfile, weapons:[WeaponProfile], countermeasures:int, stealth:float,
         owner:OwnerRef(commander_id|AI_GARRISON|ENEMY_DIRECTOR), package_id?,
         order:Order(current), job_id?:TaskingJobId, path:[NodeId|Vec2], state:UnitState }
Node   { id:str(stable), name, kind:(AIRBASE|FOB|PORT|FACTORY|RADAR|BRIDGE|HQ|SANCTUARY),
         pos, owner:Side|NEUTRAL, capture:CaptureState, stock:int, max_stock:int, hp:int }
Edge   { a:NodeId, b:NodeId, layer:(ROAD|SEA_LANE), length_m, speed_mult, bridge?:NodeId }
Campaign { id, seed, config_hash, mode, objective_mode:(TIMED|RELAXED|OFF), options:{friendly_fire:bool, unlimited_ammo:bool},
           start_tick, clock_paused, objective:Objective?, score }
```
- **Combat state (owner decisions 2026-10-17):**
  - `damage_state` follows Q-CBT-1 (Healthy → Damaged → Mission-kill → Disabled; Destroyed is the terminal lifecycle state, STATE-MACHINES §4.1). Rolls use the `combat` stream.
  - `munitions` holds the per-sortie load per weapon, drawn from base stock at spawn/rearm. **Guns are limited** (`gun_rounds`, high count) and rounds used are charged to base stock on resupply (Q-CBT-7). `unlimited_ammo` is a campaign option only (owner/admin/GM, set at campaign setup).
  - `stance` drives auto-RTB: `STANDARD` at mission-kill, `CAUTIOUS` at Damaged, `PRESS` never, `GUNS` keeps fighting with guns after missiles/bombs run out (Q-CBT-6, Q-CBT-7).
  - `crew` is set from the platform's crew count; a seeded crew-survival roll on disable or shoot-down decides `DOWNED` vs `LOST`, and CSAR resolves `RESCUED` or `CAPTURED` (GAMEPLAY §6a).
  - Hit probability uses the full Q-CBT-2 factor list (GAMEPLAY §6); every factor is a config multiplier.
  - The Static's units carry the same fields and rules (parity, GAMEPLAY §0).
- **World scale (resolves critique #24):** the theater is about 400 × 240 km. Ground convoy speed is about 25 m/s (a 90 km road takes ~1 h of sim time), and strike aircraft fly about 250 m/s. A sim-time multiplier `TIME_SCALE` (default 6×) shortens travel so a sortie lasts 3–8 real minutes. Tune it with the balance harness.

## 5. Runtime (outside the kernel)
- A fixed-step accumulator on `time.monotonic()`. Catch up at most 3 steps, then record `tick_overrun` (SYSTEM-DESIGN §5.2).
- The inbox is a bounded queue with an admission cap. Overflow is rejected with a metric and reply aggregation.
- The command log is append-only JSONL plus zstd, flushed every 1 s, and rotated per campaign.
- A snapshot is written every 300 ticks and kept for the last 20, plus one per hour.
- `state_hash` is computed every 100 ticks: blake2b over canonical msgpack of sorted, quantized state.

## 6. Failure modes
| Failure | Behavior |
|---|---|
| Exception in step | Crash bundle `(seed, config, last snapshot, log tail, exception)` → restore → continue; 3 crashes/10 min → pause campaign + alert |
| Tick overrun sustained | Shed load: lower viewer unit cap, coarser FoW update, alert |
| Snapshot write fails | Retry; alert; keep running |

## 7. Test plan
SC-1/SC-5: Semgrep rule + unit tests with a fake RNG. SC-3: golden replays + cross-process check. SC-4/SC-6: property tests (shuffled arrival yields the same result). SC-9: property round-trip. SC-10: benchmark in CI (smoke) and nightly (full).

## 8. Open questions
Decided and folded in: Q-GD-8 (air + ground at launch, sea in P3), Q-GD-9 (hand-authored first theater; procedural later), Q-ARCH-3/Q-ARCH-13 (Python; NumPy where profiling helps; Rust hot spots only if truly necessary), Q-SM-1 (`objective` RNG stream), Q-CBT-1/2/6/7/8 (combat state above). Still open: Q-TEST-1 (which host is the SC-10 reference host; gap analysis 2026-10-17).
