# SPEC: Simulation Core

Status: Approved (owner, 2026-10-20, after the NX-345 reference run) · Tracker: NX-100…NX-119 · ADRs: 0002, 0003

Rules only. Narration, history, decision trails, examples and harness numbers: [SIM-CORE-NOTES.md](SIM-CORE-NOTES.md) (not normative). One section: `python3 scripts/spec_section.py docs/specs/SIM-CORE.md <number, id or title>`.

## 1. Purpose
1. This is the authoritative, deterministic world simulation; everything else is input to it or a view of it.

## 2. Goals / Non-goals
1. Goals: determinism, testability, a predictable tick budget, recovery from snapshots.
2. Non-goals: rendering, networking, persistence I/O and LLM calls; those live outside the kernel.

## 3. Requirements

### SC-1 Deterministic step
1. `step(state, commands, rng) -> (state, events)` MUST be deterministic and free of side effects outside `state`: no I/O, no wall clock, no global mutable state.
2. For the tick budget (SC-10) `step` MUST mutate the working state in place and return it; it MUST NOT copy state per tick (Q-SIM-3).
3. Callers MUST treat the state as owned by the kernel.
4. In code this is `nexus.core.step.step(world, commands) -> events`: the RNG is `world.rng` (Q-SIM-32) and the world is the mutated state (NX-102).

### SC-2 Two clocks (Q-ALN-1)
1. The kernel steps at 10 Hz while running.
2. Game time and world time are both derived from the tick count, so both are deterministic, and both MUST freeze while paused (SC-11).
3. Game time is the unscaled tick count: `TICK_DT = 0.1` game seconds per tick, so 1 game minute = 1 real minute while running.
4. Game time drives player-facing durations: idle handoff and retire, ability cooldowns, the respawn delay (Q-ALN-5), and campaign and objective length.
5. Game time also drives the director decision window and tier dwell, the CP EMA window, the threat-memory and provocation half-lives, the Pattern of Life periods, the night-progress cap, the Tasking Board claim lease and priority aging, and the package fill wait (Q-ALN-23).
6. World time is game time scaled by `sim.time_scale` (CONFIG-AND-CONTENT): `WORLD_DT = TICK_DT × sim.time_scale` world seconds per tick.
7. World time drives movement, logistics and combat, and also capture progress and decay, bridge repair, the FoW sensor (Tier 1 SIGINT) refresh and track fade (Q-ALN-23).
8. Config rates for world-time systems are per world second and MUST be multiplied by `WORLD_DT`.

### SC-3 Replay determinism
1. Given the same seed, config hash and command log, every replay MUST produce identical `state_hash` checkpoints on the same platform.
2. Golden replays are pinned to the CI container image with exact Python and NumPy pins, and MUST match byte-for-byte there (Q-TEST-1).

### SC-4 Entity ids
1. Entities MUST have sequential integer ids.
2. Every iteration over entities MUST happen in id order.

### SC-5 Randomness
1. All randomness MUST come from `SimRng` sub-streams named per subsystem: `combat`, `director`, `spawn`, `objective`, `tasking`.
2. A stream MUST NOT be shared between subsystems (Q-SM-1); the `fow` stream was removed (Q-FOW-5).
3. `tasking` MUST be used only for the Tasking Board's seeded tie-break (Q-GD-37 item 5, Q-ALN-7).
4. Each stream is PCG64 (NumPy's XSL-RR 128/64) whose state and increment come from blake2b, personalization `nexus.simrng.v1`, over the campaign seed and the stream name.
5. Changing that scheme changes every replay, so a change MUST use a new personalization (Q-SIM-99).

### SC-6 Command order
1. Commands MUST be applied in `(target_tick, arrival_seq)` order.
2. The runtime stamps `target_tick = current_tick + 1` on admission (CONTRACTS §3), so a command is never late and there is no `late` flag (Q-SIM-1).

### SC-7 Invalid commands
1. An invalid command MUST produce a `CommandRejected{reason}` event, never an exception.

### SC-8 Crash recovery (Q-SIM-2, Q-SIM-3)
1. An exception inside `step` MUST NOT be survived in memory: `step` mutates in place (SC-1), so the half-updated state is discarded.
2. The runtime logs a crash bundle and restores from the last snapshot plus the command log.
3. The crashed tick MUST be replayed with that tick's commands dropped.
4. The runtime appends a tombstone to the command log naming the tick, and each dropped command is emitted as `CommandRejected{INTERNAL_ERROR}`.
5. Replays MUST honour the tombstone, so they stay deterministic.
6. On a tombstoned tick that is running, the `lifecycle` system MUST also drop the reserve-queue entries it would serve, one per free viewer slot and at least the head, each as `CommandRejected{INTERNAL_ERROR}` with its own `arrival_seq`, in queue order (NX-122).
7. Nothing is dropped from the reserve queue while paused, since nothing is served then.
8. A tick's commands MUST be in the log before `step` runs (SYSTEM-DESIGN §5.2).
9. A crash with no command cause (a bug in a system) raises again on the same tick; §6 bounds it: 3 crashes in 10 minutes pause the campaign and alert.
10. Dropped commands get `event_seq` values like any other events, so replays reproduce them.

Notes: SIM-CORE-NOTES.md §3 SC-8

### SC-9 Snapshot round-trip
1. Snapshots MUST round-trip losslessly: `hash(load(save(s))) == hash(s)`.

### SC-10 Budgets (Q-SIM-4, Q-SIM-6, Q-SIM-8, Q-TEST-1)
1. p99 `step` time MUST be < 25 ms at 1,000 entities and 500 viewer units (`slots.max_viewer_units`), measured as `step` plus the frame build, on the reference host.
2. The reference host is the owner's broadcast host, an i7-8700 with a GTX 1070 8 GB under WSL2; re-baseline when the planned new PC replaces it.
3. Spatial queries MUST use uniform grids instead of O(n²) scans.
4. Sensing builds one grid per sensor range class, cell = the class's largest radius / 2 (§4 Sensing; NX-372).
5. Entities are Python objects behind a small `World` API; systems MUST NOT touch storage directly.
6. If the hot pass exceeds about 10 ms on the reference host, the hot fields move to NumPy arrays behind the same API (Q-SIM-4, Q-SIM-17).

Notes: SIM-CORE-NOTES.md §3 SC-10

### SC-11 Pause freezes the world (Q-CFG-8, Q-OPS-8, Q-OPS-9, Q-ALN-2)
1. Every timer that changes sim state MUST count ticks, not wall-clock time: idle handoff/retire, despawn, respawn delay, ability cooldowns, logistics, capture, director windows and FoW timers.
2. While `clock_paused` is set, for any reason (`PauseReasonCategory`, Q-ALN-3), neither game time nor world time advances: no unit moves, no combat resolves, no logistics or capture progresses, and no timer advances.
3. Chat commands that do not change the world still work while paused: `ME` (which `!status` aliases) and a `JOIN` from a commander with no live unit.
4. A `JOIN` while paused always joins the reserve queue, even when a slot is free (Q-ALN-26).
5. Every other chat command that reaches the kernel while paused MUST be rejected with `CAMPAIGN_PAUSED` (CONTRACTS §5.2, STATE-MACHINES §4.4).
6. The safety actions always apply while paused: `STAFF_BAN`, `FORGET` (including the despawn of the orphaned unit), `STAFF_KILL_SWITCH`, `STAFF_CAMPAIGN_PAUSE`, `STAFF_CAMPAIGN_RESUME` and `STAFF_CAMPAIGN_END` (Q-ALN-24).
7. `STAFF_CONFIG_RELOAD` is held and applied when the campaign resumes.
8. `STAFF_DIRECTOR_OVERRIDE` is rejected with `CAMPAIGN_PAUSED`.
9. `STAFF_UNBAN`, `STAFF_PURGE_UNITS` (including the despawn of the purged units), `SYS_SET_CALLSIGN` and `SYS_QUEUE_TIMEOUT` apply.
10. The runtime MUST NOT count paused time toward queue idleness (NX-371).
11. `ADVISOR_CHOICE` and the GM commands are rejected with `CAMPAIGN_PAUSED`, except `STAFF_GM_RELEASE`, which applies (Q-ALN-36).
12. A pause and a resume MUST enter only as logged commands (ADR-0002), so replays reproduce them.

Notes: SIM-CORE-NOTES.md §3 SC-11

### SC-12 Units and conversion (Q-CFG-8, Q-ALN-1, Q-ALN-6)
1. Config durations use friendly units (s, min) and MUST be converted to whole ticks once at config load, rounding up, so a timer is never shorter than configured.
2. A game-time duration `d` seconds becomes `ceil(d / TICK_DT)` ticks; a world-time duration `d` world seconds becomes `ceil(d / WORLD_DT)` ticks.
3. Each duration key's spec MUST label it game-time, world-time or real-time.
4. Real-time timers MUST live outside the kernel on a monotonic clock, be enforced before anything enters the sim, and reach the sim only as logged commands.
5. The real-time timers are chat rate limits, digest batching, LLM/TTS budgets, reconnect backoff, the offline-pause trigger, and taunt cooldowns, GM idle auto-release, redemption cooldowns and the supply-drop cap (Q-ALN-4).

### SC-13 System order inside a tick (Q-SIM-7)
1. The order MUST be one constant list in code, asserted by a test.
2. The order is: apply commands → director/AI orders (the Threat Director's window, then the Tasking Boards and follow) → movement → sensing and fog (when due, FOW-5) → combat resolution (new shots fire, then pending impacts land) → logistics and capture → objectives → lifecycle (despawn, respawn, retire) → emit events, and `state_hash` when due.
3. A write by one system is visible to later systems in the same tick, never earlier.
4. A unit destroyed by combat this tick still moved this tick.

### SC-14 Event stream (Q-SIM-14)
1. `events` MUST be the only way the rest of the system learns what happened; no consumer infers a change by diffing state, except the frame builder.
2. Every event MUST carry `tick`, a campaign-wide monotonically increasing `event_seq`, a type and ids only (no free text, no user strings).
3. XP and merit ledger rows are built from events with `<campaign_id>:<event_seq>:...` as their idempotency key (DATA-MODEL DM-4), so a recovery replay that re-emits an event cannot double-count.

### SC-15 Campaign end (Q-SIM-15)
1. When the campaign ends (victory, defeat, the time limit or an abort) the kernel MUST emit `CampaignEnded{result}` and from then on apply only the SC-11 safety actions.
2. The kernel MUST NOT reset itself or start the next war.
3. The runtime builds a new kernel state for the next campaign (new seed, new config hash, units reset), so a replay never crosses a war boundary.

### SC-16 Replay scope (Q-SIM-13)
1. The seed, config hash and command log reproduce a campaign only on the same commit and pinned image.
2. They serve golden CI replays, bug reproduction and crash recovery, not archives; re-simulating an old log on new code is not promised.
3. Public "watch the war again" replays MUST come from output recorded at broadcast time, not from re-simulation.

Notes: SIM-CORE-NOTES.md §3 SC-16

## 4. World model (component-style, flat)
```
Entity { id:int, kind:UnitKind, side:Side(COALITION|ENEMY), domain:Domain(AIR|GROUND|SEA|STATIC),
         pos:Vec2(m), vel:Vec2(m/s), alt_band:(NOE|LOW|MED|HIGH) for AIR,
         hp:int, damage_state:DamageState(HEALTHY|DAMAGED|MISSION_KILL|DISABLED),
         fuel:fixed, munitions:{<weapon_id>:int}, gun_rounds:int, cargo:int,
         stance:Stance(PRESS|STANDARD|CAUTIOUS|GUNS),
         crew:{count:int, status:Crew(ABOARD|DOWNED|RESCUED|CAPTURED|LOST)},
         sensor:SensorProfile, weapons:[WeaponProfile], countermeasures:int, stealth:float,
         owner:OwnerRef(commander_id|AI_GARRISON|ENEMY_DIRECTOR), base_id?:NodeId (facilities only), follow_id?:EntityId (Q-GP-31, Q-GP-33), package_id?,
         order:Order(current), job_id?:TaskingJobId, path:[NodeId|Vec2], state:UnitState }
Node   { id:str(stable), name, kind:(AIRBASE|FOB|PORT|BRIDGE|HQ|SANCTUARY),
         pos, owner:Side|NEUTRAL, capture:CaptureState, stock:int, max_stock:int, hp:int }
Edge   { a:NodeId, b:NodeId, layer:(ROAD|SEA_LANE), length_m, speed_mult, bridge?:NodeId }
Campaign { id, seed, config_hash, mode, objective_mode:(TIMED|OFF), options:{unlimited_ammo:bool},
           start_tick, clock_paused, pause_reason:PauseReasonCategory?,
           pause_sub_reason:StaffPauseSubReason?, objective:Objective?, score }
```
1. Fields above join the code with the system that first reads them.
2. Each subsection names its SC-13 slot and the spec owning its behaviour rules; current mechanics are in the matching NOTES subsection.
3. Every `World`, `Entity`, `Campaign` and `Job` field named in §4 is world state, in snapshots and `state_hash`, unless a rule says it is derived.
4. `load` refuses a snapshot of an older format whenever a format change adds state (history: NOTES §4).
5. `pause_sub_reason` is set only when `pause_reason = STAFF` and is optional there (RAID, ABUSE, CONTENT, OTHER; Q-ALN-31, CONTRACTS §3.3).

### Entity and world state
1. `domain` is not stored: it comes from the unit catalog by `kind`.
2. `state` holds the STATE-MACHINES §4.1 states for aircraft only (`LANDED`, `EN_ROUTE`, `ON_STATION`, `RTB`); it is `None` for other domains.
3. `fuel` is an aircraft's world seconds of flight left (a float, hashed at the 1e-6 step, ADR-0002); `orbit` is the centre an idle `ON_STATION` aircraft circles (hashed in mm); both are `None` otherwise.
4. `hp` is an integer ≥ 1 for every kind, the catalog's, full at spawn.
5. `path` holds the remaining waypoints: node ids for GROUND, node ids or `Vec2` for AIR; a leading waypoint equal to `last_node` while the unit stands on that node counts as reached.
6. `last_node` is the node a unit last reached or spawned at, so a GROUND unit is always on the road edge from `last_node` to `path[0]`.
7. `World.respawn_left` maps a commander to the running ticks left of its respawn delay (GP-2), always ≥ 1.
8. `World.record_loss(commander_id)` sets it to `Rules.respawn_delay_ticks`; every loss path MUST call it before `lifecycle` in its tick.
9. `lifecycle` counts every entry down by 1 per tick in commander-id order, not while paused, and deletes it at 0, so a loss on tick L allows a JOIN on tick L + delay plus any paused ticks.
10. `World.reserve_queue` holds the queued `JOIN` commands, head first, one per commander (GP-3, U-4), encoded as each command's JSON data with sorted keys; a snapshot that holds a commander twice MUST be refused.
11. `World.stock` maps each finite-stock node to whole stock units; a SANCTUARY is infinite by rule and absent; `start_campaign` fills it from the theater's `start_stock`.
12. A cargo carrier (LOGI_TRUCK, ENEMY_CONVOY) has `cargo` (whole units aboard, else `None`), `unload_milli` (0 to 999) and `delivered`.
13. `World.owner` maps every theater node to its live owner (`COALITION`, `ENEMY` or `NEUTRAL`), starting from the theater's `start_owner`.
14. `World.capture` maps a node to `CaptureBar{side, progress}` (whole millionths of a percent, only while above 0); `load` MUST refuse a bar with no owner entry for its node, with no progress or a full bar, or on its own side.
15. Tasking state is `Entity.order` (`HOLD`, `GOTO` or `FOLLOW`; none when the board is in charge), `Entity.job_id`, `World.boards[side]` and `World._next_job_id`; `load` MUST check every board (ids, dedupe keys, dependencies, claims against `job_id`).
16. Order hold state is `Entity.order_node` and `Entity.held_since` (Q-SIM-110); `load` MUST refuse either without order GOTO, and `held_since` without `order_node` or after the running clock.

Notes: SIM-CORE-NOTES.md §4 Entity and world state

### Rules and campaign start
1. Static per-campaign data the kernel reads is one frozen `nexus.core.rules.Rules`, held as `World.rules` and built by `make_rules` from the loaded config.
2. `Rules` is not world state: it is in neither snapshots nor `state_hash` (`config_hash` covers it).
3. `restore`/`recover` MUST require it as `rules=` (`None` only for a world that never reads it), re-attach it, and refuse rules whose theater nodes differ from the snapshot's `World.owner` keys. They MUST also take the active theater hash (the theater part of `config_hash`, `CampaignConfig.theater_hash`) and, before attaching rules, refuse a snapshot whose header `theater_hash` differs (same node names, moved positions): a theater change is never restored under new geometry. The newest valid snapshot decides; an older one is not tried instead (NX-509).
4. A config reload, when it exists, MUST rebuild `Rules` and log the change. A balance-only reload (same theater hash, other `config_hash`) is allowed; restore then attaches the new balance's rules.
5. `WORLD_DT` is computed once from `sim.tick_hz` and `sim.time_scale` in exact decimals.
6. The replay CLI MUST refuse a snapshot whose campaign `config_hash` differs from the loaded config's.
7. `start_campaign` places the theater's `facilities` in theater-file order (so ids are deterministic), each a `STATIC`, `AI_GARRISON`-owned entity at its base's position, on the base's starting side, with `base_id` and `variant`.
8. RADAR_SITE and the SAM variant of AIR_DEFENSE_SITE start `emitting: true` (FOW-11, Q-FOW-10); every other facility starts `null`.
9. `SimRuntime` MUST refuse a world without rules; a JOIN on such a world raises (SC-8 drops it).

Notes: SIM-CORE-NOTES.md §4 Entity and world state

### Movement
1. Slot `movement`; behaviour rules: GAMEPLAY §5.
2. In id order, each unit with a `path` spends `WORLD_DT` world seconds along it: AIR flies straight at `speed_mps`; GROUND drives road edges at `speed_mps × speed_mult`.
3. Time left after reaching a waypoint carries on to the next in the same tick; a reached waypoint is snapped to exactly.
4. A ground unit reaching its last waypoint stops (`vel` 0, `path` empty).
5. `vel` is the heading to the next waypoint at the current speed, zero when idle.
6. A follower's `World.speed_cap` (ground units only) lowers its speed before the road's `speed_mult`.
7. A ground unit whose path starts with the node it left drives back to it along the road it is on.

Notes: SIM-CORE-NOTES.md §4 Movement

### Aircraft
1. Slot `movement`; Q-SIM-38. `speed_mps` is a top speed; an AIR entity with no `state` is a bug and MUST raise.
2. `load` MUST refuse an entity with a `state` but no `fuel` (or the reverse), or an `orbit` while not `ON_STATION`.
3. A world with no rules moves nothing: only units with no path that are stateless or `LANDED` may be in it.
4. A `LANDED` aircraft with no path stays put (`vel` 0, no burn).
5. Unless `RTB`, the bingo check comes first: bingo when `fuel` ≤ the straight-line distance to the nearest landing base of its side ÷ `speed_mps` + `air.bingo_reserve_frac` × `fuel_s` (equality counts; ties by node id; a side with no landing base never bingos).
6. At bingo its path becomes that base and its state `RTB`.
7. A `LANDED` aircraft whose path is just the base it stands on drops the path and stays landed; any other path takes it off (`EN_ROUTE`).
8. Otherwise it burns `WORLD_DT` of fuel per tick, a whole tick even on takeoff and landing ticks.
9. Only after moving is fuel 0 a crash (owner, 2026-10-21): an aircraft that lands on the tick its fuel runs out stays landed.
10. Any other aircraft at fuel 0 is lost after the loop, in id order: removed, `record_loss` called, and `UnitDestroyed{killer_id: null, assist_ids: [], side}` emitted.
11. A path ending at a landing base node of its side lands it on arrival (`LANDED`, `vel` 0, `last_node` the base); a `Vec2` waypoint after a base does not land.
12. A path ending elsewhere puts it `ON_STATION`, orbiting clockwise through the point reached, entered along its last leg, at `min_speed_mps`, one lap per `air.orbit_period_s`, centre clamped inside the theater bounds.
13. The orbit uses libm `atan2`, `cos`, `sin` (deterministic per platform, ADR-0002); golden hashes are pinned to the CI platform.
14. A new path takes an aircraft off station (`EN_ROUTE`); `movement` keeps an `RTB` aircraft `RTB` whatever its path, so an order handler that gives an RTB aircraft a new path MUST set it `EN_ROUTE` itself.
15. No airborne aircraft flies below `min_speed_mps`.
16. A landed aircraft ordered off with fuel at or below bingo stays on the ground, its order dropped, and keeps refuelling; once above bingo a new order takes it off.
17. An `RTB` aircraft whose path ends at a node that is no longer a landing base of its side MUST re-target, in the same `movement` step, to the nearest landing base its side owns by the bingo rule; with none left it flies on.

Notes: SIM-CORE-NOTES.md §4 Aircraft

### Logistics
1. Slot `logistics_capture`; behaviour rules: GAMEPLAY §5, GP-7, Q-GP-24, Q-SIM-48 to Q-SIM-54.
2. Stock and cargo are whole integers; a unit leaves a source's stock as it becomes cargo, so stock + cargo + consumed (the `SupplyConsumed` debits) MUST be conserved exactly.
3. Only a load at an infinite source adds stock; a removed truck's cargo is lost.
4. A source never falls below its starvation floor, `ceil(logistics.starve_threshold x node_max_stock)`.
5. "Friendly" is the node's live owner (`World.owner`).
6. The Static's rear source `enemy_rear_source` (`static-rear`, Q-SIM-48) is infinite, joined to its HQ by road and never capturable (N-4).
7. Unloading runs each running tick (not while paused), in id order, in whole thousandths per tick, moving whole units capped by the cargo and the node's room and keeping the fraction.
8. A truck sent by its operator's command MUST NOT divert from a full base (Q-SIM-50, owner amendment 2026-10-21).
9. A stop emits one `SupplyDelivered{node_id, amount, carrier_id, commander_id}` (CONTRACTS §6) when it ends, `amount` the units unloaded during the stop, none if that is 0, for both sides.
10. A truck lost mid-stop reports its open stop first (Defense 3), and a Disabled truck's open stop is cut and reported by `logistics`.
11. `UnitSpawned` has no cargo field, only `loadout: FULL`.

Notes: SIM-CORE-NOTES.md §4 Logistics

### Combat
1. Slot `combat`; behaviour rules: COMBAT CB-1 to CB-7, CB-9, CB-10, Q-SIM-65.
2. Each running tick, in order: weapon `reload` and `wreck_left` timers count down one tick; new shots fire; then every shot due lands.
3. Shooters fire in entity id order, each ready weapon in catalog order, at the best tracked target (`threat` descending, distance, id), only at contacts the shooter's side tracks now.
4. Target search uses grids per side and threat level and MUST equal a full scan (SC-10).
5. The overkill check (`combat.overkill_check`, Q-TD-73) is per-tick scratch summed over `World.shots` in `(impact_tick, id)` order, never world state.
6. A landing shot that does not fizzle (Combat state 5) makes one `combat`-stream draw against `Pk = min(pk_cap, base_pk x track x range x evasion x masking)`.
7. A hit takes `max(1, floor(damage x (1 - armor)))` hp (`armor` an exact decimal) and moves the damage state by whole-hp thresholds (`ceil(fraction x max hp)`).
8. `UnitDestroyed.assist_ids` holds the other shooters inside `combat.assist_window_s`, sorted, at most 32 (Q-SIM-66).
9. `impact_tick`, reloads and wreck timers are on the campaign clock (running ticks), so a pause freezes them.
10. Events are built with `model_construct` in the order fired, impact, state change, destroyed.
11. Disabled units do not move, fuel up or unload (their cargo is lost with the wreck), do not contest a capture and cannot escape a flipped base.
12. A Disabled facility is not a valid target and senses, emits and listens for no one (FOW-11) until repaired back up to `combat.facility_restore_frac` (Q-TD-86).
13. A structure shot (`Shot.node`) fizzles with no draw if the node changed hands, is at 0 or is out of range (CB-10, Q-CBT-22).

Notes: SIM-CORE-NOTES.md §4 Combat

### Capture
1. Slot `logistics_capture`, after logistics; behaviour rules: GAMEPLAY §8, STATE-MACHINES §4.2, Q-SIM-56, Q-SIM-57.
2. It runs each running tick (not while paused) for each node but a SANCTUARY or BRIDGE (never captured, N-4), in node id order, with no RNG.
3. Progress is an integer of millionths of a percent (a full bar is 100,000,000), so thresholds and decay are exact.
4. A node has one bar and one 100% test per tick (N-1).
5. With two free sides and an exact capture-weight tie, nothing starts (Q-SIM-59).
6. `n^exponent` uses libm `pow`, pinned to the CI platform (ADR-0002).
7. At 100% the owner becomes the capturing side, the bar is removed and `NodeCaptured{node_id, from, to, participant_commander_ids}` is emitted in the same tick (participants sorted, no duplicates).
8. The base's facilities switch side keeping their damage (Q-GP-25), except as `capture.facilities_disabled` says (NX-471, GAMEPLAY §8).
9. Ownership is read per node during the id-order pass, so a flip earlier in the same tick counts.
10. After a flip, `bridges.reroute(taken=node)` replans every supply run and repair crew whose road enters the node (NX-413; GAMEPLAY §1b).

Notes: SIM-CORE-NOTES.md §4 Capture

### Defense
1. Behaviour rules: GAMEPLAY §8 and §9, COMBAT CB-10, Q-GD-18, Q-SIM-71, Q-TH-7.
2. `World.defense_hp` (every node kind but BRIDGE), `defense_drain` and `defense_down` are world state.
3. A truck lost mid-stop (destroyed, or lost at a flipped base) reports its open stop first (`SupplyDelivered`, then `SupplyConsumed{REPAIR}`, before `UnitDestroyed`), so stock + cargo + consumed stays exact.
4. `NodeDefensesDown` is emitted when hp reaches 0 unless already flagged down; `NodeDefensesRestored` only when a rebuild takes a flagged node to full; a node that was never down emits nothing as it builds up.
5. A flip sets hp, carry and flag to 0 for the new owner, with no event.
6. Nothing drains or repairs while paused.
7. With the idle floor on and `World.viewer_units() == 0`, a hit cannot take the coalition sanctuary below 1 (default; Q-CFG-16 options `campaign.idle_floor.enabled` and `sanctuary_min_hp`).
8. Restore MUST refuse an entity whose `last_node` or a path waypoint is not a theater node, and MUST check defenses with `defense.validate`.

Notes: SIM-CORE-NOTES.md §4 Defense

### Bridges
1. Slots `combat` and `logistics_capture`; behaviour rules: STATE-MACHINES §4.3, COMBAT CB-10, Q-SIM-105 to Q-SIM-107.
2. `World.bridge_hp`, `World.bridge_down` and `World.bridge_repair` are world state.
3. `BridgeDestroyed{node_id, by_id, lost_ids}` is emitted once, when a bridge reaches 0.
4. `bridges.blocked(world)` is the one `blocked` set every road search MUST pass, so a cut edge is in no path computed after the tick (B-1).
5. Repair moves whole hp from a carry in thousandths, capped at the maximum (B-2); a down bridge leaves `bridge_down` only when repaired to full, with `BridgeRepaired{node_id, by_id}`.
6. A bridge under repair is never struck again.
7. Restore MUST check bridges with `bridges.validate`: the keys are the theater's bridges, 0 <= hp <= max, 0 hp is down, a down bridge is below full, and a repair carry is below 1000 and 0 at full.

Notes: SIM-CORE-NOTES.md §4 Bridges

### Campaign
1. Slot `objectives`, after capture; behaviour rules: GAMEPLAY §9, STATE-MACHINES §4.4 and §4.5, Q-SIM-60 to Q-SIM-62.
2. The campaign clock is `Campaign.running_ticks`, the ticks the world was not frozen (paused, or ended); `Campaign.tick` counts every tick (C-1).
3. Each running tick the slot adds the tick to the clock, adds each side's held strategic nodes to its running sum, resolves the active objective, then checks the end, in this order.
4. Only the coalition can win mid-war; the Static wins only at the time limit by score (Q-SIM-64).
5. Score is an exact `Fraction`; the event carries `float(score)`; an exact tie is `winner: null` (Q-GP-10).
6. `CampaignEnded{result, end_tick, score, winner, nodes_held_pct}` is emitted once (C-2); the world is then frozen and `apply_commands` rejects every later command, in the same tick too, with `CAMPAIGN_NOT_RUNNING` (C-3).
7. Whoever adds an SC-15 safety action to the code MUST exempt it in `apply_commands`.
8. `nodes_held_pct` and the Hud's percentages are rounded to the nearest whole percent, halves up.
9. The kernel only validates staff payloads; who may send which is ADMIN-RBAC's (outside the kernel).
10. In `timed` mode there is exactly one active objective while the campaign runs and a frontline exists (O-1); the pick is one uniform `objective`-stream draw over the sorted candidates, and no draw is made when there is none.
11. Objective deadlines are on the campaign clock, so a pause freezes them (O-2); `off` mode has no objectives.
12. Momentum is the pure `momentum(world)`, not stored, in exact `Fraction` arithmetic (Q-SIM-60).

Notes: SIM-CORE-NOTES.md §4 Campaign

### Rearm stop
1. Called from `logistics` for every entity not unloading cargo (Q-SIM-68); it supersedes the fuel-only refuel in NOTES §4 Logistics.
2. All lines are integers except fuel; every stock-thousandth drawn goes through `Supply.rearm_milli`, so whole units debited = thousandths bought / 1000, and a base never sells past its stock.
3. The loader refuses a `logistics.rearm_rate` of less than 0.001 per tick.
4. A Disabled non-facility never restocks.
5. At a stop's end `SupplyConsumed{REARM}` carries the whole units spent on fuel and rounds and a separate `SupplyConsumed{REPAIR}` the units spent on hp; `RearmStalled` is emitted once when something is wanted and nothing could be bought.
6. A unit removed mid-stop (any `lose_unit`, or a wreck timing out) first reports its pending `SupplyConsumed{REARM}` and `{REPAIR}`, so stock + cargo + consumed is conserved exactly across losses.
7. Auto-RTB is edge-triggered, not checked each tick.
8. A restored world is refused (`combat.validate`) if spend counters or a stall flag sit on an entity with no node to report them at, repair progress sits at full hp, `ammo_credit` is above its bound, or `seized_carry` is set anywhere but a Disabled facility with `capture.facilities_disabled` on.
9. The loader refuses a loadout whose `2 x price x lcm` of its full loads reaches 2**62, since `ammo_credit` is a msgpack integer.

Notes: SIM-CORE-NOTES.md §4 Rearm stop

### Crew, auto-RTB and damage effects
1. `combat` removes the `World.crew_markers` whose `expires` (running ticks) has come.
2. `Rules.speed(kind, damage_state)` and `Rules.sensor_radius(kind, damage_state)` apply the Damaged multipliers; the fog range-class grids are keyed on both radii, so results equal a full scan.

Notes: SIM-CORE-NOTES.md §4 Crew, auto-RTB and damage effects

### Economy
1. Slot `director`, first; behaviour rules: ECONOMY EC-1 to EC-15.
2. In the `director` slot the order is: economy window, upkeep, shortfall sitreps, coalition AI trucks, Threat Director, Tasking Boards, `steer`.
3. The window runs every `economy.window_s` running ticks, never while frozen, in Side order.
4. Arithmetic is integers and `Fraction`s (the budget floored once), iteration is sorted, and there is no RNG.
5. A limited side's pool is never debited below 0.
6. `World.pool`, `World.storage`, `Entity.home_base`, `Entity.grounded`, `Entity.ordered`, `World.shortfall`, `World.shortfall_end` and `DirectorState.last_operation` are world state; restore refuses values the window could not produce (negative stock, unknown nodes or statuses, ticks after the clock, a grounded unit with a job, order or leader).

Notes: SIM-CORE-NOTES.md §4 Economy

### Coalition AI trucks
1. Slot `director`, after upkeep and before the Threat Director; behaviour rules: GAMEPLAY §5 LC-1.
2. It acts only at economy windows and adds no state and no RNG.

Notes: SIM-CORE-NOTES.md §4 Coalition AI trucks

### Threat Director
1. Slot `director`, before the Tasking Boards; behaviour rules: THREAT-DIRECTOR §7a.
2. `World.director[side]` (`DirectorState`) is world state; restore refuses a timer or held tick past the clock and a held node, `home` or `via` no decision window could have set.
3. Every `director.window_s` running ticks (never while frozen, SC-11) the ENEMY's Director decides from `side_view(world, "ENEMY")` alone.
4. The Director decides first, then the board and `steer` run.
5. Provocation is noted by `combat` and `capture` through `nexus.core.provocation`; a tier move emits `ThreatTierChanged`.
6. `launch` uses integers and exact `Fraction`s, sorted candidates, one `director` draw per candidate in (operation id, target id) order, and spawns units in template order.
7. Pattern of Life timers run on the campaign clock, so a pause freezes them (Q-SIM-85).
8. The patrol job is the Director's alone: the board never assigns it.

Notes: SIM-CORE-NOTES.md §4 Threat Director

### Tasking Boards
1. Slot `director`, before `movement`; behaviour rules: GAMEPLAY §1b TB-1 to TB-10, Q-SIM-73.
2. The pass at running tick `n = running_ticks + 1` runs when `tasking.reeval_every_ticks` divides `n`, never while frozen, for COALITION then ENEMY.
3. A pass ends orders, settles claims, decides each job's outcome, generates and posts the side's jobs by dedupe key, then assigns the side's idle units in id order, the best job first.
4. Rank is an exact `Fraction`; runs of equal priority are ordered by one `tasking`-stream draw each in job id order, the stream's only use (SC-5, Q-ALN-7).
5. Generation reads only the side's `SideView` and its own state.
6. `post_job` is the one entry for new jobs.
7. `World.lost`, `World.cooldown`, `World.blob_runs`, `World.intercept_seen`, `Entity.pickup` and `Job.struck_by` are world state.

Notes: SIM-CORE-NOTES.md §4 Tasking Boards

### AI wingmen
1. `nexus.core.wingmen` (NX-511); behaviour rules: GAMEPLAY §1b items 239–255.
2. `step.apply_commands` stamps a JOIN's or REBASE's commander with the running ticks before the handler runs (`World.last_command`, pruned at each board pass).
3. A flight spawns inside `tasking.claim`, so on a board pass or a parameterless JOIN; the per-tick pass runs in slot `director` after the Threat Director and before the Tasking Boards, never while frozen: it ends flights, starts cooldowns and retires wingmen that landed, before the board could task one.
4. `World.last_command`, `World.flights`, `World.wingmen_cooldown` and `World.wingmen_home` are world state (snapshot format 40); no RNG.

### Follow
1. Slot `director`, after the board; behaviour rules: GAMEPLAY §1b, §5; Q-GP-31..33, Q-SIM-76.
2. `Entity.follow_id` and `Entity.fired_by` are world state.
3. `steer` runs every running tick, never while frozen.
4. `World.speed_cap` and `World.group_threat` are derived every tick and are neither snapshot nor hash.
5. A group threat is judged from the enemy kind's catalog weapons, never its live ammo.
6. A snapshot is refused when a follower names a unit that is gone, of the other side, a facility, in a loop, or without the FOLLOW order or an escort claim.

Notes: SIM-CORE-NOTES.md §4 Follow

### Sensing
1. Slot `sensing`; behaviour rules: FOG-OF-WAR Tier 1, Tier 2, FOW-11, FOW-13.
2. A Tier 2 pass runs on ticks where `tick % fow.track_every_ticks == 0`; an enemy entity inside one of the side's sensors (`sensor.radius_m` × the target's `stealth`, inclusive) is tracked, with no RNG (Q-FOW-2).
3. The range-class grids MUST give the same result as a full scan (SC-10).
4. `World.contacts`, `World.markers`, `World.blobs` and `World.sigint_age` are world state; the hash stores positions in mm and velocities in mm/s.
5. While paused nothing ages and no pass runs (FOW-9, SC-11).
6. Readers use the last pass (Q-FOW-6); last-known tracks are not visible entities.
7. A facility never leaves a last-known track, and a marker is never removed.
8. A blob carries no entity id, count or exact position, and building blobs draws no RNG; `make_rules` refuses a `fow.sigint_cell_m` that does not divide both theater bounds.

Notes: SIM-CORE-NOTES.md §4 Sensing

### SYS_SET_CALLSIGN
1. Q-SIM-39. It stores `World.callsigns[commander_id]`, sets `callsign` on every live entity of that commander and emits `CallsignChanged{commander_id, callsign, callsign_kind}`.
2. It applies while paused (Q-ALN-36).
3. A JOIN copies the stored callsign onto the unit and `UnitSpawned.callsign` (null if none).

Notes: SIM-CORE-NOTES.md §4 SYS_SET_CALLSIGN

### REBASE
1. Q-SIM-90. The commander's live, non-Disabled unit goes to a base of the coalition.
2. It is rejected in this order (SC-7): `CAMPAIGN_PAUSED`, `NO_ACTIVE_UNIT`, `NODE_UNKNOWN`, `NODE_NOT_FRIENDLY`, `NODE_INVALID_FOR_UNIT`, `OUT_OF_REACH`, `UNIT_GROUNDED`.
3. While paused it is rejected with `CAMPAIGN_PAUSED` first and changes nothing (Q-ALN-2).
4. An accepted rebase sets the order `HOLD` (Q-CFG-16 option `slots.rebase_order`) and adds no state.

Notes: SIM-CORE-NOTES.md §4 REBASE

### JOIN
1. The kernel's handler table is `nexus.core.handlers.HANDLERS`.
2. A JOIN is checked in this order, each failure a `CommandRejected` (SC-7): `CAMPAIGN_PAUSED` (paused and the commander has a live unit), `INVALID_PAYLOAD`, `ROLE_UNKNOWN`, `UNIT_IN_SORTIE`, `RESPAWN_COOLDOWN`, `FOLLOW_TARGET_INVALID`, `NODE_UNKNOWN`, `NODE_INVALID_FOR_UNIT`.
3. A JOIN that passes every check queues while paused (even with a free slot, Q-ALN-26), when the live `COMMANDER`-owned units reach `slots.max_viewer_units`, or while the queue is not empty (strict FIFO, U-4).
4. A newcomer to a full queue (`slots.reserve_queue_max`) is rejected with `RESERVE_QUEUE_FULL`.
5. `lifecycle` serves the queue after the respawn countdown, not while paused, through the same checks; an invalid entry gets its check's `CommandRejected` with the queued command's `arrival_seq`.
6. `plan_deploy` is pure; stock is debited in `_spawn`, so a queued JOIN is planned again when it is served; the sanctuary is never debited.

Notes: SIM-CORE-NOTES.md §4 JOIN

### Combat state
1. `damage_state` follows Q-CBT-1 (Healthy → Damaged → Mission-kill → Disabled; Destroyed is the terminal lifecycle state, STATE-MACHINES §4.1) and is derived from the `hp` fraction (Q-GP-8, `combat.damage_state.*` thresholds).
2. A hit does `damage × (1 − armor)` (COMBAT CB-5; exact form: Combat 7); a Disabled unit is a wreck, removed after `combat.disabled_timeout_s` (COMBAT CB-7).
3. A shot is not an entity (Q-GP-7, Q-GP-12): firing spends the round and stores a pending impact `Shot{id:int, shooter, target, weapon_id, impact_tick}` in state.
4. Pending shots are part of the snapshot and the hash, get sequential ids, and land in `(impact_tick, id)` order.
5. Pk is rolled on the impact tick against the target's state then; a missing shooter, or a target no longer tracked by the shooter's side, out of the envelope, destroyed or despawned, makes the shot fizzle as a miss with no draw (Q-FOW-16).
6. Guns land on the fire tick.
7. `munitions` holds the per-sortie load per weapon, drawn from base stock at spawn/rearm.
8. Guns are limited (`gun_rounds`, high count) and rounds used are charged to base stock on resupply (Q-CBT-7).
9. `unlimited_ammo` is a campaign option only, set at campaign setup by an Admin or the owner; a GM cannot change campaign options (Q-ALN-10).
10. `stance` drives auto-RTB: `STANDARD` at mission-kill, `CAUTIOUS` at Damaged, `PRESS` never, `GUNS` keeps fighting with guns after missiles/bombs run out (Q-CBT-6, Q-CBT-7).
11. `crew` is set from the platform's crew count; a seeded crew-survival roll on disable or shoot-down decides `DOWNED` vs `LOST`, and CSAR resolves `RESCUED` or `CAPTURED` (GAMEPLAY §6a).
12. Hit probability uses the first-build factors in COMBAT §5.2 (Q-CBT-10), capped at `combat.pk_cap`; unbuilt factors are a registered 1.0 (FB-6).
13. The Static's units carry the same fields and rules (parity, GAMEPLAY §0).
14. Discovered facility markers (FOW-13): per side, `FacilityMarker{entity_id, kind, variant, pos, ring_m, state|null, emitting|null, confirmed_tick}`, world state.
15. `ring_m` is the site variant's longest AIR weapon range in whole metres (null without one); `state` is the damage state at the last observing pass; both refresh with the marker, and a hand-over writes them as of the flip tick.
16. Facilities (Q-GP-21, Q-GP-25): radars and air-defense sites (factories are parked) are ordinary `STATIC`-domain entities with a `base_id` whose `side` follows the base's owner, switching side with their damage when it flips (GAMEPLAY §8 for `capture.facilities_disabled`).
17. New facility kinds are new catalog entries, not kernel code (CONFIG-AND-CONTENT §7a).

Notes: SIM-CORE-NOTES.md §4 Combat state

### World scale
1. The theater is about 400 × 240 km (resolves critique #24).
2. Ground convoy speed is about 25 m/s (a 90 km road takes ~1 h of world time, about 10 real minutes at 6×), and strike aircraft fly about 250 m/s.
3. The world-time multiplier `sim.time_scale` (default 6×, SC-2) shortens travel so a sortie lasts 3–8 real minutes.
4. It scales only world time (movement, logistics, combat), never player-facing game-time durations (Q-ALN-1).
5. Tune it with the balance harness.

## 5. Runtime (outside the kernel)
1. Threading (Q-SIM-9): the sim runs on its own thread; commands come in on a thread-safe queue and frames leave on another.
2. GIL contention is accepted for now; on chat-ingest or WebSocket jitter the sim moves to its own process or container behind the same queues.
3. Readers (Q-SIM-8): because `step` mutates in place (SC-1), nothing reads the world while it runs.
4. The overlay frame and, every 300 ticks, the snapshot serialization are built synchronously on the sim thread right after `step` and leave it only as finished immutable bytes; their time counts inside the SC-10 budget.
5. Compression and disk writes happen off-thread.
6. The loop is a fixed-step accumulator on `time.monotonic()`; it catches up at most 3 steps, then records `tick_overrun` (SYSTEM-DESIGN §5.2).
7. The inbox is a bounded queue with an admission cap; overflow is rejected with a metric and reply aggregation.
8. The command log is append-only JSONL plus zstd, flushed every 1 s, in one directory per campaign whose segments rotate by size and at snapshot boundaries (DATA-MODEL §6.2).
9. Each tick's commands are appended before `step` (SC-8); on a `step` exception the runtime appends the tombstone and flushes before it restores.
10. A snapshot is written when the runtime starts (the recovery base) and every 300 ticks; retention keeps the newest 20 plus the earliest snapshot of each game hour.
11. Restore (`nexus.runtime.recovery`) loads the newest snapshot that verifies, falling back to older ones, and then replays every tick after it.
12. The caller gives the stop tick (after a `step` exception, the tick before the crash); with none, replay stops at the last tick the log names, never before the snapshot, and empty ticks after it are not replayed.
13. The log must continue the snapshot: a missing segment or a command on the wrong side of the snapshot's `last_arrival_seq` fails the restore.
14. Both the live crash path and a restart go through `recover`.
15. If a replayed tick raises and has no tombstone, `recover` tombstones that tick and retries, up to 3 attempts; a tick that raises although already tombstoned is a system bug, and restore raises at once.
16. `state_hash` is computed every 100 ticks: blake2b over canonical msgpack of sorted, quantized state.
17. Only the hash quantizes (1 mm, 1e-6; ADR-0002): snapshots store floats losslessly, so a restored run continues bit-identically.
18. The RNG state is part of world state, so both the snapshot and the hash cover it.
19. Automatic pauses (Q-OPS-8): when the broadcast has been offline longer than `ops.offline_pause_after_min` (real time, default 10, configurable), the runtime issues a pause with reason `TECHNICAL`; shorter blips and a single chat platform dropping do not pause.
20. On recovery the overlay shows "COMMS RESTORED" and a 30 s countdown, then the runtime issues the resume.
21. The weekly maintenance window pauses with reason `MAINTENANCE` and the owner's Ceasefire mode with reason `CEASEFIRE` (Q-OPS-9, Q-ALN-3); Admins can override from the Command Center.
22. Recorded output (Q-SIM-18): besides the command log, the runtime records a redacted coalition frame stream and a private full-truth frame stream per campaign; public replays and clips use them (CLIPS-REPLAY §1), and the truth stream is served only after the campaign ends.
23. Clean shutdown (Q-SIM-16): a deliberate restart or deploy pauses the campaign, forces a snapshot at the next tick boundary, flushes the command log and then stops, so a planned restart loses nothing; an unclean crash still recovers from snapshot plus log (SC-8).
24. Timestamps the runtime writes (command log, snapshots, crash bundles) are UTC ISO-8601 (Q-CFG-8); none enters `state`.

Notes: SIM-CORE-NOTES.md §5

## 6. Failure modes
| Failure | Behavior |
|---|---|
| Exception in step | Crash bundle `(seed, config, last snapshot, log tail, exception)` → tombstone the tick → restore to the tick before → rerun the tick with its commands dropped (SC-8) → continue. 3 crashes within 6,000 ticks (10 minutes of game time while running; counted in ticks, so replays and tests see the same window) → the runtime stops stepping and sets `halted`; the caller alerts and pauses the campaign with a logged pause command (SC-11, ADR-0002). If recovery itself fails, or a log flush or rotation fails, the runtime also halts and re-raises; the commands drained for that tick are lost from the inbox. A halted runtime is discarded and a restart goes through `recover`. The crash count lives per process, so bounding restart loops across processes is the supervisor's job |
| Tick overrun sustained | Shed load: lower viewer unit cap, coarser FoW update, alert |
| Snapshot write fails | Count it in `snapshot_failures` (the caller alerts), keep running, and retry at the next 300-tick interval |

## 7. Test plan
1. SC-1/SC-5: Semgrep rule + unit tests with a fake RNG.
2. SC-3: golden replays + cross-process check (`services/sim/tests/golden/`, `tools/sim-determinism/check.py`, CI job `sim-determinism`; NX-105).
3. SC-4/SC-6: property tests (shuffled arrival yields the same result).
4. Q-GP-12: a shot whose target dies before impact fizzles with no `combat` draw, and pending shots round-trip through a snapshot.
5. SC-8: a command that raises inside `step` is dropped on recovery with a tombstone and `CommandRejected{INTERNAL_ERROR}`, recovery does not loop, and replaying the log reproduces the same state hash.
6. SC-9: property round-trip.
7. SC-10: benchmark in CI (smoke) and nightly (full); the pass/fail number is measured on the Q-TEST-1 reference host.
8. SC-2: a unit's distance moved per tick equals speed × `WORLD_DT`, and a game-time timer of `d` seconds expires after `ceil(d / TICK_DT)` ticks whatever `sim.time_scale` is.
9. SC-11: property: for every game-time and world-time timer, its remaining ticks at resume equal those at pause, and no entity position, hp, stock or capture progress changes between pause and resume except through the commands SC-11 allows.
10. Q-ALN-24: while paused, `STAFF_BAN` and `FORGET` despawn the target's unit, `STAFF_DIRECTOR_OVERRIDE` is rejected with `CAMPAIGN_PAUSED`, and a `STAFF_CONFIG_RELOAD` changes no balance value until the resume tick, where it is applied.
11. Q-ALN-23: with `sim.time_scale` ≠ 1, capture progress and the Tier 1 refresh scale with it while the director window and Tasking Board claim lease take the same number of ticks.
12. SC-12: a duration that is not a whole number of ticks rounds up (e.g. 0.25 s game time becomes 3 ticks), and two loads give the same tick values.

## 8. Open questions
1. Every Q-row this spec lists is decided and folded in; the list is in SIM-CORE-NOTES.md §8.

Notes: SIM-CORE-NOTES.md §8
