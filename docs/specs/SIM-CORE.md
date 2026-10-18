# SPEC: Simulation Core

Status: Draft · Tracker: NX-100…NX-119 · ADRs: 0002, 0003

## 1. Purpose
This is the authoritative, deterministic world simulation. Everything else is input to it or a view of it.

## 2. Goals / Non-goals
- Goals: determinism, testability, a predictable tick budget, recovery from snapshots.
- Non-goals: rendering, networking, persistence I/O, and LLM calls (those live outside the kernel).

## 3. Requirements
- **SC-1** `step(state, commands, rng) -> (state, events)` MUST be pure: no I/O, no wall clock, no global mutable state.
- **SC-2** **Two clocks (Q-ALN-1).** The kernel steps at 10 Hz while running. Both clocks below are derived from the tick count, so both are deterministic, and both freeze while paused (SC-11).
  - **Game time** is the unscaled tick count: `TICK_DT = 0.1` game seconds per tick, so 1 game minute = 1 real minute while running. It drives player-facing durations: idle handoff and retire, ability cooldowns, the Tasking Board decision window, the respawn delay (Q-ALN-5), and campaign and objective length. Per Q-ALN-23 it also drives the director decision window and tier dwell, the CP EMA window, the threat-memory and provocation half-lives, the Pattern of Life periods, the night-progress cap, the Tasking Board claim lease and priority aging, and the package fill wait.
  - **World time** is game time scaled by `sim.time_scale` (CONFIG-AND-CONTENT): `WORLD_DT = TICK_DT × sim.time_scale` world seconds per tick. It drives movement, logistics and combat, and per Q-ALN-23 also capture progress and decay, bridge repair, the FoW sensor (Tier 1 SIGINT) refresh and track fade. Rates for those in config are per world second and are multiplied by `WORLD_DT`.
- **SC-3** Given the same seed, config hash and command log, every replay MUST produce identical `state_hash` checkpoints on the same platform. Golden replays are pinned to the CI container image with exact Python and NumPy pins, and MUST match byte-for-byte there (Q-TEST-1).
- **SC-4** Entities have sequential integer ids. Every iteration over entities happens in id order.
- **SC-5** All randomness MUST come from `SimRng` sub-streams named per subsystem (`combat`, `director`, `spawn`, `fow`, `objective`, `tasking`; never shared between subsystems, Q-SM-1). `tasking` is used only for the Tasking Board's seeded tie-break (Q-GD-37 item 5, Q-ALN-7).
- **SC-6** Commands MUST be applied in `(target_tick, arrival_seq)` order. Commands for past ticks MUST be applied at the current tick and flagged `late`.
- **SC-7** Invalid commands MUST produce a `CommandRejected{reason}` event, never an exception.
- **SC-8** An exception inside `step` MUST NOT corrupt state. The runtime keeps the previous state, logs a crash bundle, and fails over to restore-from-snapshot.
- **SC-9** Snapshots MUST round-trip losslessly: `hash(load(save(s))) == hash(s)`.
- **SC-10** Budgets: p99 `step` time < 25 ms at 1,000 entities and 300 viewer units on the reference host: the owner's broadcast host, an i7-8700 with a GTX 1070 8 GB under WSL2 (Q-TEST-1). Re-baseline when the planned new PC replaces it. Spatial queries use a uniform grid (cell = max sensor radius / 2) instead of O(n²) scans.
- **SC-11** **A pause freezes the whole world (Q-CFG-8, Q-OPS-8, Q-OPS-9, Q-ALN-2):** every timer that changes sim state counts ticks, not wall-clock time: idle handoff/retire, despawn, respawn delay, ability cooldowns, the Tasking Board decision window, logistics, capture, director windows and FoW timers. While `clock_paused` is set, for any reason (`PauseReasonCategory`, Q-ALN-3), neither game time nor world time advances: no unit moves, no combat resolves, no logistics or capture progresses, and no timer advances. Chat commands that do not change the world (`ME`, which `!status` aliases; `!quiet`; a `JOIN` from a commander with no live unit, which always joins the reserve queue while paused, even when a slot is free, Q-ALN-26) still work; every other chat command that reaches the kernel is rejected with `CAMPAIGN_PAUSED` (CONTRACTS §5.2, STATE-MACHINES §4.4). **Operator and system commands while paused (Q-ALN-24):** the safety actions always apply: `OP_BAN`, `FORGET` (including the despawn of the orphaned unit), `OP_KILL_SWITCH`, `OP_CAMPAIGN_PAUSE`, `OP_CAMPAIGN_RESUME` and `OP_CAMPAIGN_END`. `OP_CONFIG_RELOAD` is held and applied when the campaign resumes. `OP_DIRECTOR_OVERRIDE` is rejected with `CAMPAIGN_PAUSED`. A pause and a resume enter only as logged commands (ADR-0002), so replays reproduce them.
- **SC-12** **Units and conversion (Q-CFG-8, Q-ALN-1, Q-ALN-6):** config durations use friendly units (s, min) and are converted to whole ticks once at config load, rounding **up** so a timer is never shorter than configured (Q-ALN-6): a game-time duration `d` seconds becomes `ceil(d / TICK_DT)` ticks; a world-time duration `d` world seconds becomes `ceil(d / WORLD_DT)` ticks. Each duration key's spec labels it game-time, world-time or real-time. Real-time timers (chat rate limits, digest batching, LLM/TTS budgets, reconnect backoff, the offline-pause trigger, and, per Q-ALN-4, taunt cooldowns, GM idle auto-release, redemption cooldowns and the supply-drop cap) live outside the kernel on a monotonic clock, are enforced before anything enters the sim, and reach the sim only as logged commands.

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
           start_tick, clock_paused, pause_reason:PauseReasonCategory?,
           pause_sub_reason:OperatorPauseSubReason?, objective:Objective?, score }
```
- `pause_sub_reason` is set only when `pause_reason = OPERATOR` and is optional there (RAID, ABUSE, CONTENT, OTHER; Q-ALN-31, CONTRACTS §3.3).
- **Combat state (owner decisions 2026-10-17):**
  - `damage_state` follows Q-CBT-1 (Healthy → Damaged → Mission-kill → Disabled; Destroyed is the terminal lifecycle state, STATE-MACHINES §4.1). Rolls use the `combat` stream.
  - `munitions` holds the per-sortie load per weapon, drawn from base stock at spawn/rearm. **Guns are limited** (`gun_rounds`, high count) and rounds used are charged to base stock on resupply (Q-CBT-7). `unlimited_ammo` is a campaign option only, set at campaign setup by an Admin or the owner; a GM cannot change campaign options (Q-ALN-10).
  - `stance` drives auto-RTB: `STANDARD` at mission-kill, `CAUTIOUS` at Damaged, `PRESS` never, `GUNS` keeps fighting with guns after missiles/bombs run out (Q-CBT-6, Q-CBT-7).
  - `crew` is set from the platform's crew count; a seeded crew-survival roll on disable or shoot-down decides `DOWNED` vs `LOST`, and CSAR resolves `RESCUED` or `CAPTURED` (GAMEPLAY §6a).
  - Hit probability uses the full Q-CBT-2 factor list (GAMEPLAY §6); every factor is a config multiplier.
  - The Static's units carry the same fields and rules (parity, GAMEPLAY §0).
- **World scale (resolves critique #24):** the theater is about 400 × 240 km. Ground convoy speed is about 25 m/s (a 90 km road takes ~1 h of world time, about 10 real minutes at 6×), and strike aircraft fly about 250 m/s. The world-time multiplier `sim.time_scale` (default 6×, SC-2) shortens travel so a sortie lasts 3–8 real minutes. It scales only world time (movement, logistics, combat), never player-facing game-time durations (Q-ALN-1). Tune it with the balance harness.

## 5. Runtime (outside the kernel)
- A fixed-step accumulator on `time.monotonic()`. Catch up at most 3 steps, then record `tick_overrun` (SYSTEM-DESIGN §5.2).
- The inbox is a bounded queue with an admission cap. Overflow is rejected with a metric and reply aggregation.
- The command log is append-only JSONL plus zstd, flushed every 1 s, and rotated per campaign.
- A snapshot is written every 300 ticks and kept for the last 20, plus one per hour.
- `state_hash` is computed every 100 ticks: blake2b over canonical msgpack of sorted, quantized state.
- **Automatic pauses (outside the kernel):** when the broadcast has been offline longer than `ops.offline_pause_after_min` (real time, default 10, configurable), the runtime issues a pause with reason `TECHNICAL`; shorter blips and a single chat platform dropping do not pause (Q-OPS-8). On recovery the overlay shows "COMMS RESTORED" and a 30 s countdown, then the runtime issues the resume. The weekly maintenance window pauses with reason `MAINTENANCE` and the owner's Ceasefire mode with reason `CEASEFIRE` (Q-OPS-9, Q-ALN-3). Admins can override from the Command Center.
- Timestamps the runtime writes (command log, snapshots, crash bundles) are UTC ISO-8601 (Q-CFG-8). None enters `state`.

## 6. Failure modes
| Failure | Behavior |
|---|---|
| Exception in step | Crash bundle `(seed, config, last snapshot, log tail, exception)` → restore → continue; 3 crashes/10 min → pause campaign + alert |
| Tick overrun sustained | Shed load: lower viewer unit cap, coarser FoW update, alert |
| Snapshot write fails | Retry; alert; keep running |

## 7. Test plan
SC-1/SC-5: Semgrep rule + unit tests with a fake RNG. SC-3: golden replays + cross-process check. SC-4/SC-6: property tests (shuffled arrival yields the same result). SC-9: property round-trip. SC-10: benchmark in CI (smoke) and nightly (full); the pass/fail number is measured on the Q-TEST-1 reference host. SC-2: a unit's distance moved per tick equals speed × `WORLD_DT`, and a game-time timer of `d` seconds expires after `ceil(d / TICK_DT)` ticks whatever `sim.time_scale` is. SC-11: property: for every game-time and world-time timer, its remaining ticks at resume equal those at pause, and no entity position, hp, stock or capture progress changes between pause and resume except through the commands SC-11 allows. Q-ALN-24: while paused, `OP_BAN` and `FORGET` despawn the target's unit, `OP_DIRECTOR_OVERRIDE` is rejected with `CAMPAIGN_PAUSED`, and an `OP_CONFIG_RELOAD` changes no balance value until the resume tick, where it is applied. Q-ALN-23: with `sim.time_scale` ≠ 1, capture progress and the Tier 1 refresh scale with it while the director window and Tasking Board claim lease take the same number of ticks. SC-12: a duration that is not a whole number of ticks rounds up (e.g. 0.25 s game time becomes 3 ticks), and two loads give the same tick values.

## 8. Open questions
Decided and folded in: Q-ALN-1 (SC-2 two clocks, §4), Q-ALN-2 (SC-11), Q-ALN-3 (§4 `pause_reason`, §5), Q-ALN-23 (SC-2 clock for the remaining timers), Q-ALN-24 (SC-11 operator and system commands while paused), Q-ALN-26 (SC-11 `JOIN` while paused), Q-ALN-31 (§4 `pause_sub_reason`), Q-ALN-4 (SC-12 real-time list), Q-ALN-5 (SC-2), Q-ALN-6 (SC-12 rounding), Q-ALN-7 (SC-5 `tasking`), Q-ALN-10 (§4 campaign options), Q-GD-8 (air + ground at launch, sea in P3), Q-GD-9 (hand-authored first theater; procedural later), Q-ARCH-3/Q-ARCH-13 (Python; NumPy where profiling helps; Rust hot spots only if truly necessary), Q-SM-1 (`objective` RNG stream), Q-CBT-1/2/6/7/8 (combat state above), Q-TEST-1 (SC-3, SC-10), Q-CFG-8 (SC-11, SC-12), Q-OPS-8/9 (§5). Still open: whether `OP_UNBAN`, `OP_PURGE_UNITS`, `SYS_SET_CALLSIGN` and the GM commands (ADMIN-RBAC) apply while paused; Q-ALN-24 names only the safety actions, config reload and director overrides.
