# SPEC: Configuration, Balance & Content

Status: Draft · Owner: — · Tracker: NX-106, NX-008, NX-031 · Related ADRs: 0002 (determinism), 0003 (persistence), 0004 (toolchain) · Policy: [DATA-INTEGRITY](../quality/DATA-INTEGRITY.md) DI-7

> **All numeric values in this spec are PROPOSED and unvalidated** (DI-7). They are starting points for the balance harness (NX-031), not tuned values. "TBD by harness" means we have no proposal yet and the harness must produce one before P2. A value drops its PROPOSED label only once it is harness-validated as defined in Q-TEST-2 (≥50 seeds across crowd profiles of 0, 5, 50, 150, 300 and 500 simulated viewers plus the adversarial profiles, Q-ALN-42; written targets met, a report saved with the `config_hash`). "(owner)" marks a value the owner set; it stays tunable.

## 1. Purpose
Define every input the system reads that isn't code: runtime settings, balance tunables, and authored content (theaters, units, doctrines, word lists, sitrep templates). This includes how each is validated, hashed, versioned and reloaded, so that:
- every campaign is reproducible from `(seed, config_hash, command_log)` (ADR-0002), and
- no value reaches the sim through a hidden code default (DI-7).

## 2. Goals / Non-goals
- **Goals:**
  - One schema per config kind, enforced at load and in CI.
  - No implicit defaults.
  - Deterministic hashing.
  - Explicit hot-reload rules.
  - An audit trail for every runtime change.
- **Non-goals:**
  - Picking the final balance values (that's the harness, NX-031).
  - Authoring the real first theater (NX-008, Q-GD-9).
  - The admin console UI (OPS-ADMIN).

## 3. Requirements
- **CFG-1** Every config kind MUST have a schema in `contracts/config/` (JSON Schema), with generated Pydantic models (ADR-0004). Unknown keys MUST be rejected (`additionalProperties: false`).
- **CFG-2** Required keys MUST NOT have code defaults. A missing required key MUST fail startup with a message naming the key and file (DI-7). Optional keys MUST state their absent-meaning in the schema (e.g. "absent = feature off"), never a substituted value.
- **CFG-3** Balance and content files MUST be hashed canonically (§4.4). The resulting `config_hash` MUST be stored on the campaign record and in every snapshot and replay header.
- **CFG-4** Values that affect sim state MUST NOT change mid-campaign except through a logged `STAFF_CONFIG_RELOAD` command (CONTRACTS §5.2) applied at a tick boundary, and only for keys marked hot-reloadable (§5). Replays MUST reproduce the reload.
- **CFG-5** Every balance key MUST carry its unit in the schema (`unit` annotation) and in this spec. All rates are per second of **world** time (CFG-9) unless the unit says otherwise (SIM-CORE SC-2).
- **CFG-6** Content cross-references (unit kinds in theaters, doctrine perks naming unit kinds, template slots) MUST be validated at load and in CI (§8).
- **CFG-7** Secrets MUST NOT appear in any config file. Config refers to secrets by name only (`secret_ref`), and the values come from the environment / secret store (THREAT-MODEL SEC-CI, CICD §8).
- **CFG-8** All user-visible authored text (node names, callsign words, sitrep templates) MUST pass the moderation denylist in CI (SEC-MOD-1).
- **CFG-9 Clocks (Q-CFG-8, Q-ALN-1, Q-ALN-4, Q-ALN-5, Q-ALN-6, Q-ALN-23, Q-ALN-35, Q-ALN-38):** every time-valued key MUST name one of three clocks in its schema `unit` annotation and in this spec (`s (world)`, `min (game)`, `s (real)`, ...).
  - **World time** (`world`) is sim ticks scaled by `sim.time_scale`: while the campaign runs, 1 real second = `sim.time_scale` world seconds. It drives movement, logistics and combat (speeds, fuel, logistics and repair rates, weapon reload), plus capture progress and decay, bridge repair, the FoW sensor refresh and track fade (FOG-OF-WAR FOW-9) (Q-ALN-23). The Tier 1 sensor refresh is expressed in world time so its real cadence stays about 8–10 s: PROPOSED ~48–60 s world at `sim.time_scale` 6 (Q-ALN-38). Deterministic; frozen while paused.
  - **Game time** (`game`) is unscaled sim ticks: while the campaign runs, 1 game minute = 1 real minute. It drives player-facing durations: idle handoff/retire, respawn delay (Q-ALN-5), rank and doctrine ability cooldowns, campaign length, the objective period and the victory/defeat holds. Per Q-ALN-23 it also drives the Threat Director decision window, tier dwell, CP EMA, the memory and provocation half-lives, the Pattern of Life periods, the night-progress cap, the Tasking Board claim lease and priority aging, and the package fill wait (GAMEPLAY §7). The CHARLIE warning lead time is game time too (THREAT-DIRECTOR §3, Q-ALN-35). Deterministic; frozen while paused.
  - **Real time** (`real`) is a monotonic clock outside the sim: chat rate limits, reply digest batching, LLM/TTS budgets, reconnect backoff, the offline-pause trigger, overlay presentation, and the limits enforced before a command enters the sim: taunt naming cooldowns, GM idle auto-release, redemption cooldowns and the supply-drop hourly cap (Q-ALN-4). It keeps running while the campaign is paused.
  - World and game time freeze for every pause reason (`PauseReasonCategory` = `STAFF`, `TECHNICAL`, `MAINTENANCE`, `CEASEFIRE`, Q-ALN-3); the offline auto-pause (§6.10) is `TECHNICAL`.
  - Keys are written in friendly units (s, min, h) and converted to ticks once, at load, by one loader function: world keys as `ceil(seconds × sim.tick_hz / sim.time_scale)`, game keys as `ceil(seconds × sim.tick_hz)`. Rounding is always up, so a timer is never shorter than configured (Q-ALN-6). No sim code reads a seconds value directly.
- **CFG-10 Time zones (Q-CFG-8, Q-CFG-6):** owner schedules (night mode, maintenance window) are defined as local times plus an IANA zone and converted at use, so DST is handled. Stored timestamps are UTC (DATA-MODEL DM-9).

## 4. Config layers

### 4.1 Overview
| Layer | Location | Format | Affects sim state? | Hashed into `config_hash`? | Changes take effect |
|---|---|---|---|---|---|
| Runtime / app | env vars + `deploy/<env>/app.yaml` | YAML + env | No | No (logged separately as `runtime_fingerprint`) | Process restart |
| Balance | `balance/<profile>.yaml` (e.g. `balance/default.yaml`) | YAML | Yes | Yes | New campaign; hot-reloadable keys only via admin reload (§5) |
| Content | `content/theaters/*.yaml`, `content/units.yaml`, `content/doctrines.yaml`, `content/text/*.yaml` | YAML | Yes (theater, units, doctrines); No (text) | Yes (all, text included, so replays are exact) | New campaign only |

### 4.2 Runtime / app config (not balance)
Covers ports, bind addresses, file paths, feature flags, platform channel ids, and secret *references*.

| Key | Type | Required | Meaning |
|---|---|---|---|
| `server.ws_bind` | `host:port` | yes | Overlay WS bind. MUST be loopback or private (SEC-API-2) |
| `server.admin_bind` | `host:port` | yes | Admin API bind (tailnet only, OPS-ADMIN §3) |
| `paths.data_dir` | path | yes | SQLite, snapshots, command logs |
| `paths.content_dir` | path | yes | Root of `content/` |
| `balance.profile` | string | yes | Which `balance/<profile>.yaml` to load |
| `platforms.twitch.enabled` | bool | yes | Adapter on or off |
| `platforms.twitch.channel_id` | string | if enabled | Broadcaster user id (from the Twitch API, never guessed, DI-8) |
| `platforms.twitch.client_secret` | `secret_ref` | if enabled | Name of the secret, not its value |
| `platforms.youtube.enabled` | bool | yes | P3 |
| `gateway.shared_chat.accept_foreign` | bool | yes | Accept Twitch Shared Chat messages that originate in other channels. `false` (owner); enable only after the source-channel API fields are verified [UNVERIFIED] (Q-GW-2). Raid-origin viewers in our own chat are always accepted |
| `overlay.broadcast_tz` | IANA zone | yes | The one zone shown next to UTC when the overlay needs an absolute time; otherwise the overlay uses relative times ("in 12 min") (Q-CFG-8). Value TBD (owner) |
| `features.<name>` | bool | per flag | Feature flags. Every flag is listed in `contracts/config/features.json` with its owner and tracker ID |
| `log.level` | enum | yes | `debug` / `info` / `warn` / `error` |

Precedence: the env var `NEXUS__SECTION__KEY` overrides the file. **Every effective value, with its source (file or env), is logged at startup**, except secrets, which are logged as `<set>` / `<missing>`.

### 4.3 Load order (startup)
1. Read runtime config (file → env overrides) and validate it against `runtime.schema.json`. On failure, exit non-zero.
2. Resolve `secret_ref`s from the environment or secret store. A missing required secret fails startup naming the ref, never the value.
3. Load the balance profile and validate it.
4. Load content: units → doctrines → theaters → text. Validate each, then run the cross-reference checks (§8.2).
5. Compute `config_hash` (§4.4). Write a `ConfigLoaded{config_hash, balance_profile, content_versions}` audit event.
6. Start a new campaign, or resume one. **Resume requires the stored campaign's `config_hash` to equal the loaded one.** On a mismatch, refuse and alert, unless an admin explicitly starts a new campaign (SIM-CORE §6).

### 4.4 Hashing & versioning
- **Canonical form:** parse YAML, convert it to a JSON-compatible tree, sort keys, serialize as UTF-8 JSON with no insignificant whitespace, then compute blake2b-256 over it. Floats are serialized with Python `repr` round-trip precision. YAML anchors and aliases are expanded before hashing.
- **`config_hash`** = blake2b-256 over the concatenation of the canonical hashes, in a fixed order: `balance`, `units`, `doctrines`, `theater` (the one selected for the campaign), `text`.
- **Manifest:** every `config_hash` is registered with a manifest listing each contributing file (path, kind, sha256) plus the full content, so crash bundles and replays never depend on git (DATA-MODEL §4.7).
- **`schema_version`:** every file carries an integer `schema_version`. A loader accepts only versions it knows. A schema bump that changes meaning requires a migration script under `tools/config_migrate/` with tests.
- **`content_version`:** a human-facing semver per content file (e.g. a theater's `version: 1.2.0`), shown in the AAR and in replay headers. It is informational only; `config_hash` is what's authoritative.

## 5. Hot-reload rules
| Category | Hot-reloadable mid-campaign? | Why |
|---|---|---|
| Rate limits, reply cadence, sitrep cadence, PiP dwell, reserve-queue cap, HUD rotation, taunt cooldowns, idle handoff/retire timers, offline-pause threshold | **Yes** | Don't change world physics. Needed for incident response (raids) |
| Director budgets and tier thresholds | **Yes**, at the next director window | Staff may need to de-escalate. Logged as a command, so replays match |
| XP table, soft cap, rank table (admin presets, §5a) | **Yes**, effective for events after the reload tick; a new rank table applies to future promotions only (Q-CFG-2) | Progression is outside the sim kernel |
| Combat pk, weapon profiles, unit stats, logistics rates, capture timings | **No**: new campaign only | Changing physics mid-war breaks fairness and invalidates comparisons |
| Theater, unit catalog, doctrines | **No**: new campaign only | Structural |
| Time scale, tick rate | **No**: new campaign only (tick rate is fixed by ADR-0002) | Determinism |

**Reload procedure (admin):**
1. Upload or select the new profile.
2. Validate it.
3. Diff it against the active profile. If the diff touches any non-hot-reloadable key, the reload is rejected.
4. Register the new config in `config_versions` (DATA-MODEL §4.7), then enqueue `STAFF_CONFIG_RELOAD{keys, new_config_hash}` for tick T+1.
5. The sim applies it at the boundary and emits `BalanceReloaded{old_hash, new_hash, keys}` (CONTRACTS §6). Old and new values are recoverable from the two registered configs, so the event carries only hashes and keys.
6. The runtime appends `(campaign_id, effective_tick = T+1, config_hash = new_hash)` to `campaign_config_history` (DATA-MODEL §4.8).

**While paused (Q-ALN-24):** steps 1–3 and the registration in step 4 run as usual, but the reload is deferred until resume: `STAFF_CONFIG_RELOAD` is enqueued for the first tick after the campaign resumes, and `effective_tick` in step 6 is that tick. The admin console shows the reload as pending until then.

Every reload is audited (who, when, diff), and is visible in the admin console history.

## 5a. Rank and XP presets (Q-PROG-7, Q-ALN-22)
- The rank table (thresholds, unlocked abilities, ability cooldowns) and the XP source values (§6.8) are config data, kept in the Command Center as **named presets** (OPS-ADMIN OA-12).
- **Who does what (Q-ALN-22):** an Owner or Admin creates, edits and applies presets. A Game Master may draft or propose a preset; the draft has no effect until an Owner or Admin approves and applies it (ADMIN-RBAC §4.3, `rules.draft` / `rules.apply_hot`).
- A preset is validated against the §6.8 schema before it can be applied. Thresholds MUST be strictly increasing; a preset that fails is rejected with the failing key named.
- Applying a preset is a normal reload (§5): it registers a new `config_hash`, is audited with the preset name, the diff, the drafting and the applying staff member, and appears in `campaign_config_history`.
- Ranks already earned are never revoked, whatever a preset changes; new thresholds apply to future promotions only (Q-CFG-2, Q-ALN-14).
- Merit is a score only and is never spent (ADR-0011). Rank abilities run on cooldowns, never on merit.

## 6. Balance schema: key reference
Legend: **HR** = hot-reloadable (§5). "TBD" = TBD by harness. **Source** = the spec the key comes from. All values are PROPOSED (DI-7).

### 6.1 Sim time & world
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `sim.tick_hz` | int (const 10) | Hz | 10 (fixed by ADR-0002; validated, not tunable) | SIM-CORE SC-2 | No |
| `sim.time_scale` | float | × real time | 6.0 | SIM-CORE §4 | No |
| `sim.snapshot_every_ticks` | int | ticks | 300 | SIM-CORE §5 | No |
| `sim.state_hash_every_ticks` | int | ticks | 100 | SIM-CORE §5 | No |
| `sim.max_entities` | int | count | 1000 | SIM-CORE SC-10 | No |

### 6.2 Slots, respawn, reserve
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `slots.max_live_per_commander` | int | units | 1 | GAMEPLAY GP-1 | No |
| `slots.respawn_delay_s` | float | s (game) | 20 | GAMEPLAY GP-2 (game time: the JOIN guard runs in the sim, Q-ALN-5) | Yes |
| `slots.max_viewer_units` | int | units | 500 | GAMEPLAY GP-3, Q-GD-6, Q-SIM-6 | Yes |
| `slots.queue_idle_min` | int | min (real time) | 15 | GAMEPLAY RQ-1, Q-SIM-12 | Yes |
| `slots.reserve_queue_max` | int | entries | TBD | GAMEPLAY GP-3 | Yes |
| `presence.idle_handoff_min` | float | min (game) | 10 (Q-GD-35). With no command from its operator for this long, a live unit finishes its current order and joins the Tasking Board as an AI-run unit (AUTO tag). Any command from the operator restores control | GAMEPLAY §1b, STATE-MACHINES §4.1 | Yes |
| `presence.idle_retire_min` | float | min (game) | 30 (Q-GD-35). With no command for this long, the unit RTBs and despawns; carried supplies return to the reserve. Together with `presence.idle_handoff_min` it replaces the old idle-despawn timer entirely (Q-ALN-8) | STATE-MACHINES §4.1 | Yes |

### 6.3 Logistics
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `logistics.node_max_stock.<node_kind>` | int | stock units | TBD per kind | GAMEPLAY §5 | No |
| `logistics.starve_threshold` | float | fraction 0–1 | 0.25 | GAMEPLAY §5 | No |
| `logistics.starve_hp_drain_per_min` | float | node hp per min (world) | TBD (PROPOSED) | GAMEPLAY §8 | No |
| `logistics.starved_loadout.fuel_frac` | float | fraction | 0.5 | GAMEPLAY §5 | No |
| `logistics.starved_loadout.secondary_ammo` | int | rounds | 0 | GAMEPLAY §5 | No |
| `logistics.truck_cargo` | int | stock units | TBD | GAMEPLAY §5 | No |
| `logistics.unload_rate` | float | stock/s (world) | TBD | GAMEPLAY §5 | No |
| `logistics.loadout_cost.<unit_kind>` | int | stock units | TBD per kind | GAMEPLAY §5 | No |
| `logistics.rearm_rate` | float | stock/s (world) | TBD | GAMEPLAY §5 | No |
| `logistics.offroad_speed_mult` | float | multiplier | 0.5 (from raw plans P987; unvalidated) | GAMEPLAY §5 | No |
| `logistics.bridge_repair_time_s` | float | s (world) | TBD (engineer repair time; Q-GD-11) | GAMEPLAY §5 | No |
| `logistics.truck_bridge_repair_mult` | float | multiplier on engineer time | 5 (Q-GD-11 recommendation "e.g. 5× slower") | GAMEPLAY §5 | No |
| `tasking.follow_station_m.<domain>` | float | m (world) | TBD (PROPOSED) | GAMEPLAY §1b, Q-GP-32 | No |
| `progression.follower_share` | float | fraction of the outcome's merit per follower | TBD (PROPOSED) | GAMEPLAY §1b, PROGRESSION, Q-GP-42 | No |
| `progression.follower_share_cap` | int | max followers credited per outcome | TBD (PROPOSED) | GAMEPLAY §1b, Q-GP-42 | No |
| `logistics.forward_deploy_min_surplus` | float | stock above the starvation threshold a base needs to accept a forward deploy | TBD (PROPOSED) | GAMEPLAY §4, Q-GP-41 | No |
| `logistics.repair_rate.<node_kind>` | float | hp/s (world) | TBD (base repair for all domains, Q-GD-27) | GAMEPLAY §5 | No |

### 6.4 Combat
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `combat.track_quality.blob` | float | multiplier | 0.2 | GAMEPLAY §6 | No |
| `combat.track_quality.track` | float | multiplier | 1.0 | GAMEPLAY §6 | No |
| `combat.track_quality.painted` | float | multiplier | 1.25 | GAMEPLAY §6 | No |
| `combat.jammer_pk_mult` | float | multiplier | TBD | GAMEPLAY §6 | No |
| `combat.evasion_mult.<alt_band>` | float | multiplier | TBD | GAMEPLAY §6 | No |
| `combat.weapons.<weapon_id>` | object | see §7.2 | TBD | GAMEPLAY §6 | No |
| `combat.track_quality.radar_lock` | float | multiplier | TBD | GAMEPLAY §6 (Q-CBT-2) | No |
| `combat.pk_mult.range.<band>` | float | multiplier | TBD | GAMEPLAY §6 (Q-CBT-2) | No |
| `combat.pk_mult.countermeasure` | float | multiplier (one-shot per load) | TBD | GAMEPLAY §6 (Q-CBT-2) | No |
| `combat.pk_mult.terrain_masked` | float | multiplier | TBD | GAMEPLAY §6 (Q-CBT-2) | No |
| `combat.pk_mult.weather.*` / `combat.pk_mult.night` | float | multiplier | TBD (P4, Q-CBT-5) | GAMEPLAY §6 | No |
| `combat.damage_state.damaged_below` | float | hp fraction | 0.70 (PROPOSED) | GAMEPLAY §6a, Q-GP-8 | No |
| `combat.damage_state.mission_kill_below` | float | hp fraction | 0.35 (PROPOSED) | GAMEPLAY §6a, Q-GP-8 | No |
| `combat.damage_state.disabled_below` | float | hp fraction | 0.10 (PROPOSED) | GAMEPLAY §6a, Q-GP-8 | No |
| `combat.damage_state.damaged_speed_mult`, `.damaged_sensor_mult` | float | multiplier | TBD | GAMEPLAY §6a (Q-CBT-1) | No |
| `combat.crew_survival.*` | object | probability modifiers per platform/location | TBD | GAMEPLAY §6a | No |
| `slots.respawn_loss_window_s` / `slots.respawn_loss_step_s` | float | s (game) | TBD (respawn grows with repeated losses, Q-CBT-9; game time per Q-ALN-5) | GAMEPLAY GP-2 | Yes |

### 6.5 Capture
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `capture.radius_m` | float | m | TBD | GAMEPLAY §8 | No |
| `capture.time_s` | float | s (world, Q-ALN-23) | 120 | GAMEPLAY §8 | No |
| `capture.multi_unit_exponent` | float | exponent (diminishing returns) | 0.5 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.quiet_floor` | float | multiplier at 0 viewer units | 0.6 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.quiet_ref` | int | viewer units at which the multiplier reaches 1.0 | 50 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.min_time_s` | float | s (world, Q-ALN-23) | 30 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.decay_per_s` | float | progress fraction/s (world, Q-ALN-23) | TBD (no value yet; used by contested decay, Q-SIM-23) | GAMEPLAY §8 | No |

### 6.6 Campaign
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `campaign.target_duration_h` | float | h (game) | 48 | GAMEPLAY §9, Q-GD-5 | No |
| `campaign.objective_period_min` | float | min (game) | 15 | GAMEPLAY §9 | No |
| `campaign.victory_node_frac` | float | fraction | 0.80 | GAMEPLAY §9 | No |
| `campaign.victory_hold_min` | float | min (game) | 30 | GAMEPLAY §9 | No |
| `campaign.defeat` | object | — | `{lose_forward_airbase: true, max_node_frac: 0.25, hold_min: 30}` (Q-GD-7; numbers PROPOSED as everywhere; `hold_min` in game minutes, Q-ALN-1) | GAMEPLAY §9 | No |
| `campaign.objective_mode` | enum `timed`\|`off` | — | `timed` (Q-GD-19); chosen at campaign setup by owner/admin only (Q-ALN-10) | GAMEPLAY §9 | No (set per campaign) |
| `campaign.options.unlimited_ammo` | bool | — | false (Q-CBT-7; test/special-event option; set at campaign setup by owner/admin only, not GM, Q-ALN-10) | GAMEPLAY §5 | No |
| `campaign.intermission.mode` | enum `auto_advance`\|`await_owner` | — | TBD (owner choice per campaign, Q-UX-8) | GAMEPLAY §9 | Yes |
| `tasking.claim_lease_s` | float | s (game, Q-ALN-23) | TBD by harness: a claim auto-releases when its unit makes no progress for this long (Q-GD-37) | GAMEPLAY §1b | Yes |
| `tasking.priority.<job_kind>` | float | base priority | TBD by harness | GAMEPLAY §1b, Q-GP-20 | No |
| `tasking.urgency_max` | float | multiplier cap (1.0–2.0) | 2.0 (PROPOSED) | GAMEPLAY §1b, Q-GP-20 | No |
| `tasking.priority_aging_per_min` | float | priority points/min (game, Q-ALN-23) | TBD by harness: old jobs gain priority so they aren't starved (Q-GD-37) | GAMEPLAY §1b | Yes |
| `tasking.reeval_every_ticks` | int | ticks | TBD by harness: boards are re-evaluated every N ticks, not every tick (Q-GD-37) | GAMEPLAY §1b | Yes |
| `director.pol.patrol_period_s` | float | s (game, Q-ALN-23) | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `director.pol.convoy_period_s` | float | s (game, Q-ALN-23) | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `director.provocation.weights.<action>` | float | score per action | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `director.provocation.weights.redemption.<type>` | float | score per redemption | Support (supply drop, repair, reinforcements, Q-AI-9; respawn skip, queue jump, Q-ALN-13) = small weight, values TBD by harness; cosmetic (color, ping, shoutout) = 0 (owner) (Q-AI-9). There is no offensive redemption class: the no-damage rule stands (Q-ALN-13) | THREAT-DIRECTOR §5a | Yes |
| `campaign.rubber_band_zone` | [float, float] | fraction of nodes | [0.55, 0.75] | GAMEPLAY §9 | No |
| `director.provocation.escalate_threshold` | float | score | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `director.provocation.half_life_s` | float | s (game, Q-ALN-23) | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `presence.window_s` | float | s (real) | TBD (drives the HUD operator count and breakdown only; the clock never pauses for lack of operators, Q-GD-4 amended / Q-SM-5; pauses come only from the `PauseReasonCategory` causes in CFG-9, Q-ALN-3) | CONTRACTS §6 `PresenceSnapshot` | No |
| `presence.emit_every_ticks` | int | ticks | TBD | CONTRACTS §6 `PresenceSnapshot` | No |
| `campaign.night_progress_cap_nodes_per_h` | float | nodes/h (game, Q-ALN-23) | 1/6 | THREAT-DIRECTOR §5, Q-GD-4 (amended) | No |
| `campaign.aar_duration_s` | float | s (real) | 300 | GAMEPLAY §9 | Yes |

### 6.7 Threat Director
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `director.window_s` | float | s (game, Q-ALN-23) | 60 | THREAT-DIRECTOR §4 | No |
| `director.cp.unit_value.<unit_kind>` | float | CP points | TBD per kind | THREAT-DIRECTOR §2 | Yes |
| `director.cp.ema_window_s` | float | s (game, Q-ALN-23) | 300 | THREAT-DIRECTOR §2 | Yes |
| `director.cp.new_account_weight` | float | multiplier | 0.5 | THREAT-DIRECTOR §2 | Yes |
| `director.cp.new_account_age_h` | float | h (real) | 24 (= Q-PROG-3 recommendation) | THREAT-DIRECTOR §2 | Yes |
| `director.tier.bravo_enter_cp` | float | CP | TBD | THREAT-DIRECTOR §3 | Yes |
| `director.tier.charlie_enter_cp` | float | CP | TBD | THREAT-DIRECTOR §3 | Yes |
| `director.tier.exit_ratio` | float | fraction of enter | 0.8 | THREAT-DIRECTOR §3 | Yes |
| `director.tier.min_dwell_s` | float | s (game, Q-ALN-23) | 600 | THREAT-DIRECTOR §3 | Yes |
| `director.budget.<tier>` | int | budget points / window | TBD per tier | THREAT-DIRECTOR §4 | Yes |
| `director.memory.half_life_s` | float | s (game, Q-ALN-23) | 1800 | THREAT-DIRECTOR §2 | Yes |
| `director.ops.<op_kind>.cost` | int | budget points | TBD per op | THREAT-DIRECTOR §4 | Yes |
| `director.ops.<op_kind>.enabled_tiers` | [enum] | — | TBD per op | THREAT-DIRECTOR §4 | Yes |
| `director.noise_scale` | float | utility units | TBD | THREAT-DIRECTOR §4 | Yes |
| `director.advisor.top_k` | int | candidates | TBD (P4) | THREAT-DIRECTOR §6 | Yes |

### 6.8 Progression
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `progression.xp.<event>` | int | XP | sortie 40, supply_per_10 15, capture 60, objective 80, recon_assist 15, kill 10, spawn 0 | PROGRESSION §2 | Yes |
| `progression.merit.<event>` | int | merit | sortie 10, supply_per_10 5, capture 20, objective 30, recon_assist 5, kill 3, spawn 0 | PROGRESSION §2 | Yes |
| `progression.xp_hour_soft_cap` | int | XP/h (real) | 400 | PROGRESSION PROG-1 | Yes |
| `progression.xp_over_cap_mult` | float | multiplier | 0.25 | PROGRESSION PROG-1 | Yes |
| `progression.rank_thresholds` | [int] | XP | [0, 300, 1500, 5000, 15000, 40000] | PROGRESSION §3 | Yes, via a preset (§5a); future promotions only (Q-CFG-2, Q-PROG-7) |
| `progression.rank_abilities.<rank>` | list of `{ability_id, cooldown_min}` | min (game) | O-6: call 1 theater asset per cooldown, 1 h (owner, Q-PROG-7); other ranks TBD | PROGRESSION §3 | Yes, via a preset (§5a) |
| `progression.leaderboards.<board>.metric` | enum | — | Per-role boards rank by role contribution, the overall board by merit; assists count (Q-PROG-8). Enum values TBD (seasons & leaderboards spec) | PROGRESSION | Yes |
| `season.overtime_cap_days` | float | days (real) | 14 (Q-PROG-9). Past it the season closes and the running campaign carries into the new season | PROGRESSION | Yes |

### 6.9 Input, audio, presentation
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `ratelimit.class.deploy.min_interval_s` | float | s (real) | 10 (plus the respawn timer) | CHAT-GATEWAY §5 (Q-GW-1) | Yes |
| `ratelimit.class.correction.min_interval_s` | float | s (real) | 5 | CHAT-GATEWAY §5 (Q-GW-1) | Yes |
| `ratelimit.class.correction.burst` | int | cmds | 2 | CHAT-GATEWAY §5 (Q-GW-1) | Yes |
| `ratelimit.class.info.min_interval_s` | float | s (real) | 15 | CHAT-GATEWAY §5 (Q-GW-1) | Yes |
| `ratelimit.class.social.<command>.cooldown_s` | float | s (real) | `rally`: 120; others TBD | CHAT-GATEWAY §5 (Q-GW-1, Q-SUP-6) | Yes |
| `ratelimit.slow_mode.multiplier` | float | × all class limits | 3 (applies only while slow mode is on) | CHAT-GATEWAY §5 (Q-GW-1) | Yes |
| `ratelimit.global.cmds_per_tick` | int | cmds/tick | TBD | CHAT-GATEWAY §5 | Yes |
| `replies.twitch_digest_min_s` | float | s (real) | 30 | CHAT-GATEWAY §6 | Yes |
| `replies.youtube_digest_min_s` | float | s (real) | 300 | CHAT-GATEWAY §3 | Yes |
| `support.supply_drop.max_per_hour` | int | redemptions/h (real), global | TBD by harness: fixed cap, no crowd-size scaling (TS-1, Q-SUP-7); real time, enforced before the redemption enters the sim (Q-ALN-4) | SUPPORT-REDEMPTIONS | Yes |
| `support.supply_drop.shared_cooldown_s` | float | s (real) | TBD by harness: shared cooldown; the reward shows "on cooldown" when capped (Q-SUP-7; real time, Q-ALN-4) | SUPPORT-REDEMPTIONS | Yes |
| `taunt.name_cooldown_min` | float | min (real) | 10 (Q-AI-7; real time, enforced outside the sim, Q-ALN-4): per-operator cooldown before a taunt names the same operator again | THREAT-DIRECTOR | Yes |
| `taunt.name_cooldown_spotlight_min` | float | min (real) | 5 (Q-AI-7; real time, Q-ALN-4): reduced cooldown for spotlight operators (recent hero events or high recent action) | THREAT-DIRECTOR | Yes |
| `hud.rotation_s` | float | s (real) | ~15 (Q-UX-11) | OVERLAY | Yes |
| `hud.rotation.panels` | list of `{panel, weight}` | — | NEEDED jobs (weight 2), reserve queue, operator breakdown, explainer (weight 1 each) (Q-UX-11), Top Commanders (Q-ALN-18; weight TBD). At 9:16, threat joins the rotation. Active Packages joins in P4 with packages; Latest Major Event is an overlay interrupt toast, not a panel (Q-ALN-18) | OVERLAY OV-14 | Yes |
| `audio.sitrep_min_interval_s` | float | s (real) | 20 | AUDIO-TTS AU-1 | Yes |
| `audio.sitrep_max_age_s` | float | s (real) | 60 | AUDIO-TTS AU-1 | Yes |
| `audio.night_mode.hours` | `{start: time, end: time, tz: IANA zone}` | wall-clock time in `tz` | `{start: "00:00", end: "08:00", tz: "America/New_York"}` (Q-CFG-6; admin-adjustable; stored with the IANA zone, not a UTC offset, so DST is handled) | AUDIO-TTS AU-2 | Yes |
| `pip.min_dwell_s` | float | s (real) | 3 | OVERLAY OV-6 | Yes |
| `pip.spawn_spotlight_s` | float | s (real) | TBD | OVERLAY OV-6 | Yes |
| `overlay.top_n_labels` | int | labels | TBD | OVERLAY OV-4 | Yes |

### 6.10 Operations
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `ops.offline_pause_after_min` | float | min (real) | 10 (owner, Q-OPS-8): auto-pause (reason TECHNICAL) when the broadcast is offline longer than this | OPS-ADMIN OA-5 | Yes |
| `ops.maintenance_window` | `{weekday, start: time, max_duration_min, tz: IANA zone}` | wall-clock time in `tz` | Tuesday morning, owner-local (start time TBD), `max_duration_min` 120; owner to confirm (Q-OPS-9) | OPS-ADMIN OA-7 | Yes |
| `export.public_stats_every_min` | float | min (real) | 15 (Q-ARCH-16) | OPS-ADMIN OA-11 | Yes |

## 7. Unit catalog (`content/units.yaml`)

### 7.1 Schema
```yaml
schema_version: 1
roles:                        # Role (CONTRACTS §3.3) -> UnitKind; every Role used in the MVP must map to exactly one kind
  STRIKE: STRIKE_FIGHTER
  RECON: RECON_UAV
  LOGI: LOGI_TRUCK              # NAVY added in P3 (Q-GD-8)
units:
  - kind: STRIKE_FIGHTER      # UnitKind (CONTRACTS §3.3), UPPER_SNAKE, unique
    side: COALITION           # COALITION | ENEMY | ANY | BASE (facilities: side follows the base, Q-GP-25)
    domain: AIR               # AIR | GROUND | SEA | STATIC
    playable_by: VIEWER       # VIEWER | AI_GARRISON | DIRECTOR (one or more)
    min_rank: 1               # PROGRESSION §3; required when playable_by includes VIEWER
    display: { symbol: "air_strike", label_key: "unit.strike_fighter" }   # OV-2 shape-coded symbol id
    speed_mps: <float>        # m/s of world time (CFG-9)
    alt_bands: [LOW, MED]     # AIR only
    hp: <int>
    fuel_s: <float|null>      # endurance in world s (CFG-9); null = not modeled (STATIC/GROUND for MVP)
    sensor: { radius_m: <float>, masking: <bool> }
    weapons: [<weapon_id>]    # refs §7.2; [] = unarmed
    cargo: <int|null>         # stock units; null = cannot carry
    can_capture: <bool>
    stealth: <float>          # detection-radius multiplier (1.0 = none)
    loadout_cost: <int>       # stock consumed at spawn/rearm (§6.3)
    cp_value: <float>         # director CP weight (§6.7)
```
Rules:
- **Display:** `display.symbol` must exist in the overlay symbol set (validated against `apps/overlay` symbol manifest in CI).
- **Friend/foe colors:** these come from `side` only, never from the catalog (OV-2).

### 7.2 Weapon profile
```yaml
weapons:
  - id: AGM_LIGHT
    targets: [GROUND, STATIC]   # domain compatibility (GAMEPLAY §6)
    range_m: <float>
    projectile_speed_mps: <float|null>  # world m/s; null = lands on the fire tick (guns). Impact tick = fire tick + ceil(range / speed / WORLD_DT) (GAMEPLAY §6, Q-GP-7)
    base_pk: <float>            # 0..1
    reload_s: <float>           # world s (CFG-9)
    ammo: <int>
    homes_on_emitters: <bool>   # SEAD behavior
```

### 7.3 MVP unit list (PROPOSED; every stat TBD by harness)
| Kind | Side | Domain | Playable by | Min rank | Armed | Carries | Captures | Notes |
|---|---|---|---|---|---|---|---|---|
| STRIKE_FIGHTER | COALITION | AIR | VIEWER, AI_GARRISON | 1 | yes (AG + AA light) | — | no | Role `STRIKE` (GAMEPLAY §2) |
| RECON_UAV | COALITION | AIR | VIEWER, AI_GARRISON | 1 | no | — | no | Role `RECON`. Large sensor; paints targets |
| LOGI_TRUCK | COALITION | GROUND | VIEWER, AI_GARRISON | 1 | no | yes | yes (slow) | Role `LOGI`. Road graph only |
| GARRISON_INFANTRY | COALITION | GROUND | AI_GARRISON | — | yes (light) | — | yes | Holds nodes when no viewers (Q-GD-4); never starts offense on its own (Q-GD-26) |
| AIR_DEFENSE_SITE | follows base | STATIC | base owner's AI | — | yes (variants: short-range AAA, SAM) | — | no | Facility (Q-GP-25). Engagement ring; a SAM variant may blink its radar. Replaces GARRISON_AAA and ENEMY_SAM_SITE |
| RADAR_SITE | follows base | STATIC | base owner's AI | — | no | — | no | Facility (Q-GP-25). Extends its side's FoW view (FOW-4) |
| ENEMY_CONVOY | ENEMY | GROUND | DIRECTOR | — | no | yes | yes (slow) | Escorts appear via threat memory |
| ENEMY_FIGHTER | ENEMY | AIR | DIRECTOR | — | yes (AA) | — | no | CAP / intercept |
| ENEMY_ARMOR | ENEMY | GROUND | DIRECTOR | — | yes (AG) | — | yes | Offensives / retakes |

Specialist chassis (SEAD, artillery, engineer, jammer, AWACS) are P4 (PROGRESSION §3). Naval units are **P3** (Q-GD-8). Their catalog rows are added then. Display class names (Striker, Scout, Hauler, …) come from `display.label_key` and the brand guide (Q-NAME-2); kind ids stay plain (GAMEPLAY TS-4).

## 7a. Unit/platform content pipeline (owner requirement, 2026-10-17)
New platforms (unit types) are **data, not code**: one YAML file per unit in `content/units/`, using the unit-catalog schema (§7). This supersedes the single `content/units.yaml` file: the loader merges `content/units/*.yaml` in sorted filename order. Behavior is composed from existing capability blocks (mobility domain, sensors, weapons, cargo, special abilities). A new *capability* still needs code and a normal PR.

**Authoring paths:**
- **Admin console form:** schema-driven, with live validation and a preview card (ADMIN-RBAC content editor, `CONTENT_EDITOR` role).
- **Agent skill `new-unit`:** a staff member describes the platform in plain words. The skill drafts the YAML, runs the validator and a short balance-harness check, and opens a draft for approval. It never publishes directly. Skill location: `.claude/skills/new-unit/`, plus a tool-agnostic prompt in `.agents/prompts/` (ADR-0010 N-7).
- **Community submissions (later):** uploaded through the portal, then moderated and approved by the owner or an admin.

**Icons (Q-STYLE-4):** each unit file declares `category` (e.g. FAST_JET, DRONE, TRUCK, TANK, BOAT, HELO, SITE, RADAR). The renderer auto-generates the symbol from category + side styling. An optional `icon` (SVG) can be uploaded. It's **sanitized** (no scripts, external refs or event handlers), size-limited, and must stay readable at small sizes. Animated icons are a later phase.

**Validation gates (all must pass):**
- Schema check.
- Cross-references resolve.
- **No real-world names** (brand rule, Q-PROD-5).
- Text passes moderation.
- Stat envelope: values inside configured min/max bands, so a new unit can't be overpowered.
- Balance harness smoke run.
- Owner or admin approval.

**Hot-loading without downtime:**
- An approved unit is published as a new content version (hash recorded).
- It becomes available via a logged `STAFF_CONTENT_LOAD{content_hash}` command, so replays stay deterministic.
- **Additive only mid-campaign:** new units may appear. Existing units' stats change only at the next campaign, unless the key is explicitly hot-reloadable.
- Removal or disablement: a unit can't be spawned anymore, but existing instances finish their sorties.

## 8. Doctrine catalog (`content/doctrines.yaml`)
```yaml
schema_version: 1
doctrines:
  - id: LOGISTICS_MASTERY
    name_key: doctrine.logistics_mastery
    min_rank: 3
    perks:                         # small, horizontal (PROGRESSION §1)
      - { target_kind: LOGI_TRUCK, stat: cargo, op: mul, value: <float> }
    signature_ability: { id: <ability_id>, cooldown_s: <float>, effect_ref: <effect_id> }   # cooldown in game s (CFG-9, Q-ALN-1)
```
- Perks may only modify whitelisted stats. Modifying `hp` or `base_pk` requires owner sign-off (game-designer role card).
- Values are PROPOSED. The catalog lands in P4 (NX-213).

## 9. Theater file format (`content/theaters/<slug>.yaml`)

### 9.1 Schema
| Field | Type | Rules |
|---|---|---|
| `schema_version` | int | Known version |
| `slug` | string | `^[a-z0-9-]{3,32}$`, equals the filename |
| `name` | string | Display name; moderation-checked (CFG-8) |
| `version` | semver | §4.4 |
| `bounds_m` | `{w, h}` | Map extent in metres (SIM-CORE §4: ~400×240 km for the first theater) |
| `terrain` | object | `heightmap: <path to 16-bit PNG>`, `height_scale_m`, `sea_level_m`; **or** `contours: <path to GeoJSON-like polylines>`. `masking_regions`: polygons where NOE/LOW flight is masked from radar |
| `sectors` | list | `{id, name, polygon}`; non-overlapping; union covers the map |
| `nodes` | list | `{id, name, kind, pos: [x_m, y_m], start_owner, start_stock, sector}` |
| `edges` | list | `{a, b, layer: ROAD\|SEA_LANE, speed_mult, bridge?: <node id of kind BRIDGE>}` |
| `spawns` | list | `{side, node, domains: [...]}`: where each side's units may appear |
| `sanctuary` | node id | Coalition SANCTUARY node: infinite stock, never capturable (Q-GD-7) |
| `enemy_hq` | node id | Enemy HQ node (Domination victory, GAMEPLAY §9) |

Node `kind` ∈ `AIRBASE | FOB | PORT | BRIDGE | HQ | SANCTUARY` (SIM-CORE §4); facilities are placed as STATIC units with a `base_id` (Q-GP-25).

### 9.2 Validation rules (load + CI)
| ID | Rule |
|---|---|
| TH-1 | Node `id`s match the CONTRACTS `NodeId` slug `^[a-z0-9]+(-[a-z0-9]+)*$` (≤ 32 chars, no underscores) and are unique. Node `name`s are unique (case-insensitive, confusable-folded) and moderation-clean |
| TH-2 | Every edge endpoint exists. No self-loops. No duplicate `(a,b,layer)` |
| TH-3 | Every non-SEA node is reachable from `sanctuary` over the ROAD layer when all bridges are intact. PORT nodes must touch ≥1 SEA_LANE |
| TH-4 | Every `bridge` reference points to a node of kind BRIDGE, and that node sits on the edge (within tolerance) |
| TH-5 | Exactly one SANCTUARY (`start_owner: COALITION`) and exactly one HQ (`start_owner: ENEMY`) |
| TH-6 | All positions lie inside `bounds_m`. Every node lies in the sector it names |
| TH-7 | Each side has ≥1 spawn per domain that its MVP units use |
| TH-8 | The terrain file exists, its dimensions match `bounds_m` at the declared resolution, and its hash is included in the content hash |
| TH-9 | Node count and kind mix are reported, not enforced (design guidance: ~15 nodes, Q-GD-9) |

### 9.3 Format example (NOT the real map)
> **Illustrative format example only.** This is *not* the first theater. The real theater is authored in NX-008 (Q-GD-9). Coordinates and names exist only to show the syntax.
```yaml
schema_version: 1
slug: format-example
name: "Format Example"
version: 0.0.1
bounds_m: { w: 40000, h: 20000 }
terrain: { heightmap: terrain/format-example.png, height_scale_m: 500, sea_level_m: 0, masking_regions: [] }
sectors:
  - { id: west, name: "West", polygon: [[0,0],[20000,0],[20000,20000],[0,20000]] }
  - { id: east, name: "East", polygon: [[20000,0],[40000,0],[40000,20000],[20000,20000]] }
nodes:
  - { id: base-w,  name: "Example Sanctuary", kind: SANCTUARY, pos: [2000,10000],  start_owner: COALITION, start_stock: null, sector: west }
  - { id: br-mid,  name: "Example Bridge",    kind: BRIDGE,    pos: [20000,10000], start_owner: NEUTRAL,   start_stock: 0,    sector: east }
  - { id: hq-e,    name: "Example HQ",        kind: HQ,        pos: [38000,10000], start_owner: ENEMY,     start_stock: 0,    sector: east }
edges:
  - { a: base-w, b: hq-e, layer: ROAD, speed_mult: 1.0, bridge: br-mid }
spawns:
  - { side: COALITION, node: base-w, domains: [AIR, GROUND] }
  - { side: ENEMY,     node: hq-e,   domains: [AIR, GROUND] }
sanctuary: base-w
enemy_hq: hq-e
```
`start_stock: null` on the SANCTUARY means "infinite by rule", not unknown. The schema documents this explicitly (CFG-2).

## 10. Text content (`content/text/*.yaml`)

### 10.1 Callsign word list (`callsign_words.yaml`)
- **Format:** words are `^[A-Z]{3,8}$`, e.g. `VIPER`. Generated callsigns are `WORD-NN`, with `NN` in 01–99 (IDENTITY §2).
- **Size (Q-CFG-4):** start with about 200 theme-fitting words (≈ 19.8k callsigns). The long-run target is ≥ 2× the measured 90-day peak of distinct commanders, set once real audience data exists.
- **Role-themed pools (Q-CFG-4):** word pools may be themed per role (e.g. strike words like VIPER, recon words like ECHO). **Flight numbering** (e.g. "VIPER 1-2") is a display label only when operators fly together; the personal callsign stays the stable identity.
- **Content screening:** every word passes the moderation denylist, including leetspeak and homoglyph folding. No word may be a real-world unit or squadron designation, or a trademark (Q-PROD-5).
- **Reserved patterns:** generated patterns are reserved and can't be claimed as custom callsigns (IDENTITY §3).

### 10.2 Sitrep templates (`sitreps.yaml`)
```yaml
schema_version: 1
templates:
  - id: node_captured
    event: NodeCaptured                 # must match a sim event type (contracts/)
    priority: normal                    # critical | normal | low (AUDIO-TTS AU-1)
    night_mode: suppress                # allow | suppress
    text_key: sitrep.node_captured      # localization key
slots:                                  # the only allowed slot types
  node_name:   { source: theater.node.name }
  callsign:    { source: commander.approved_callsign }   # never a raw display name (SEC-MOD-2)
  side:        { source: enum.side }
  tier:        { source: enum.threat_tier }
  count:       { source: event.int_field }
```
- Slots resolve **only** from the sources listed. Any other source fails validation.
- If a slot's source value is absent (e.g. a commander with no approved callsign), the template's `fallback_text_key` is used. That fallback must itself contain no slot for the missing value, and its use is logged (DATA-INTEGRITY FB-3 pattern). Templates without a fallback and with an absent value are **skipped**, not filled with placeholder text.

### 10.2a Asset provenance register (Q-BRAND-5, Q-LEGAL-4, NX-318)
- Every art, audio and font asset in the repo or loaded by the overlay has one register entry: `source`, `author`, `license`, `ai_generated` (bool) and `status` (`placeholder` | `final`). The register lives under `assets/` (file name set in NX-318).
- Alpha and testing builds may use AI-generated art anywhere, but only as a visual placeholder: `status: placeholder`, and the stream shows a placeholder note.
- **Release gate:** CI fails a release build that contains any asset with `ai_generated: true` or `status: placeholder`, or any asset missing from the register.
- Fonts and third-party assets are committed only if their license permits redistribution (e.g. OFL). Licensed music is never committed; it is loaded on the broadcast host only (Q-LEGAL-4).
- Tool commercial terms and platform AI-disclosure rules are [UNVERIFIED].

### 10.3 Localization keys (`strings.<locale>.yaml`)
- Keys are dotted (`unit.strike_fighter`, `sitrep.node_captured`, `hud.objective`).
- `en` is the only locale in the MVP. Every key referenced by templates, the catalog or the overlay must exist in `en` (CI check).
- Interpolation uses named slots `{node_name}`, never positional ones.
- Strings are plain text. No HTML or markup is allowed (WP-6, SEC-OV-1).

## 11. Validation & CI
### 11.1 Schema tests
- Every file under `balance/` and `content/` validates against its schema. Unknown keys fail.
- A negative fixture for each schema (missing required key, wrong type, unknown key) proves the loader rejects it.

### 11.2 Cross-reference checks (`tools/config_lint`)
- Unit `weapons` → weapon ids; doctrine perks → unit kinds and whitelisted stats; `roles` → existing unit kinds, and catalog kinds == the CONTRACTS `UnitKind` enum.
- Theater `spawns` domains → units for that side and domain; `display.symbol` → overlay symbol manifest.
- Sitrep `event` → contract event types; `text_key` → `strings.en.yaml`.
- Every balance key in §6 exists in the schema, and every schema key appears in this spec (a drift check against the spec table, parsed from markdown).
- Every hot-reloadable flag in the schema matches the HR column here.

### 11.3 Content safety
Moderation denylist over all display strings (CFG-8). This runs in CI and at load time.

### 11.4 Balance-diff report (required on PRs touching `balance/` or `content/`)
CI posts a comment containing:
- the key-level diff (old → new) and the new `config_hash`;
- for each changed key, its HR status and source spec section;
- a balance-harness comparison on the standard scenarios (TESTING-STRATEGY §3.5), with median and p10/p90 per metric before and after.

A PR without a harness run fails the `balance-report` check. A change that touches a non-HR key also requires the `golden-update` label if the golden replays change (TESTING-STRATEGY §3.2).

## 12. Failure modes
| Failure | Behavior |
|---|---|
| Missing or invalid required key at startup | Exit non-zero, naming the key and file. The watchdog alerts. The stream shows the fallback scene (OPS-ADMIN §1) |
| Resume with mismatched `config_hash` | Refuse the resume and alert. The admin chooses: restore the old config or start a new campaign |
| Admin reload touches a non-HR key | Rejected before enqueue, with the diff shown |
| Content file fails moderation at load | Startup refused. CI should already have caught it |
| Secret ref unresolved | Startup refused, naming the ref, never the value |

## 13. Test plan
| Req | Tests |
|---|---|
| CFG-1 | Schema positive/negative fixtures per kind; unknown-key rejection |
| CFG-2 | Loader test: each required key removed in turn fails with the key named; grep test: no defaults in the config models (Semgrep `getenv` default rule, DATA-INTEGRITY §6) |
| CFG-3 | Hash stability: the same tree with reordered keys or different YAML formatting gives the same hash; a single-value change gives a different hash; the golden `config_hash` is stored in replay fixtures |
| CFG-4 | Replay with a mid-campaign HR reload reproduces state hashes; a reload touching a non-HR key is rejected; a reload requested while paused is registered but applied at the first tick after resume, and that tick is its `effective_tick` (Q-ALN-24) |
| CFG-5 | Lint: every schema numeric field has a `unit` annotation |
| CFG-6 | `config_lint` positive/negative fixtures per cross-reference |
| CFG-7 | Semgrep / secret scan over `balance/`, `content/`, `deploy/*/app.yaml`; schema forbids secret-shaped fields except `secret_ref` |
| CFG-8 | The moderation corpus includes evasion cases; CI fails on a seeded bad node name |
| CFG-9 | Lint: every time-valued key carries a `world`, `game` or `real` label; a pause test (one per `PauseReasonCategory`) shows world and game timers frozen and real timers running; worked conversion examples at `sim.tick_hz` 10 and `sim.time_scale` 6: a 10 min game key = 6000 ticks, a 60 s world key = 100 ticks, a 1 s world key = 2 ticks (1.67 rounded up, Q-ALN-6); `capture.time_s` 120 (world) = 200 ticks and `director.window_s` 60 (game) = 600 ticks (Q-ALN-23); a Tier 1 FoW refresh of 48–60 s (world) = 80–100 ticks, 8–10 s real (Q-ALN-38); the loader converts friendly units to ticks once |
| CFG-10 | A maintenance window converted across a DST change keeps the same local start time |
| §5a | A preset with non-increasing thresholds is rejected; applying a preset registers a new `config_hash` and an audit row; raising thresholds lowers no earned rank; a GM can save a preset draft but applying it as a GM is denied, and an Admin applying that draft succeeds (Q-ALN-22) |
| §10.2a | A release-gate fixture with one placeholder asset fails; one with an unregistered asset fails |
| TH-1…TH-8 | One failing fixture theater per rule |

## 14. Open questions
- Decided and folded in (2026-10-17): Q-GD-5 (48 h target), Q-GD-6 (cap + visible reserve queue), Q-GD-7 (`campaign.defeat`), Q-GD-9 (hand-authored first theater), Q-GD-11 (`logistics.truck_bridge_repair_mult`), Q-PROG-3 (account age 24 h at 0.5×), Q-CFG-1…Q-CFG-7 (see [OPEN-QUESTIONS](../planning/OPEN-QUESTIONS.md)), Q-CFG-6 (`audio.night_mode.hours`), Q-GW-1 (per-class rate limits).
- Decided and folded in (2026-10-18): Q-CFG-8 (CFG-9, CFG-10), Q-TEST-2 (header note), Q-PROG-6 (distinct-humans progression gate removed), Q-PROG-7 (§5a), Q-PROG-8, Q-PROG-9, Q-GD-35, Q-GD-37, Q-AI-7, Q-AI-9, Q-UX-11, Q-SUP-7, Q-GW-2, Q-OPS-8, Q-OPS-9, Q-ARCH-16, Q-BRAND-5 / Q-LEGAL-4 (§10.2a).
- Decided and folded in (spec-alignment batch, 2026-10-18): Q-ALN-1 (world vs game time, CFG-9; the §6.6 campaign and objective timers are game time), Q-ALN-3 (pause reasons), Q-ALN-4 (taunt cooldowns, GM idle auto-release, redemption cooldowns and the supply-drop cap are real time), Q-ALN-5 (respawn is game time), Q-ALN-6 (round up to ticks), Q-ALN-8 (old idle-despawn key removed), Q-ALN-10 (campaign options are owner/admin only), Q-ALN-13 (no offensive redemption class), Q-ALN-14 (no rank revocation).
- Decided and folded in (spec-alignment batch 2, 2026-10-18): Q-ALN-18 (Top Commanders in `hud.rotation.panels`), Q-ALN-22 (GMs draft rank/XP presets; Owner/Admin approve and apply, §5a), Q-ALN-23 (clocks for the capture, Tasking Board, night-progress and Threat Director keys in §6 and for the FoW timers, CFG-9), Q-ALN-24 (a reload requested while paused is deferred until resume, §5).
- Decided and folded in (spec-alignment batch 3, 2026-10-18): Q-ALN-35 (CHARLIE warning lead time is game time, CFG-9), Q-ALN-38 (Tier 1 FoW refresh re-expressed in world time, CFG-9), Q-ALN-42 (harness crowd profiles, header note).
- Still open:
  - The FoW timers (the Tier 1 sensor refresh, PROPOSED ~48–60 s world per Q-ALN-38, and `fow.track_fade_s`, FOG-OF-WAR FOW-6, FOW-9), the package fill wait (GAMEPLAY §7) and the CHARLIE warning lead time (THREAT-DIRECTOR §3, PROPOSED ~10 min game, Q-ALN-35) now have a clock (CFG-9) but no row in §6; their keys, values and HR status are added when those features are specified.
  - Weight of Top Commanders in `hud.rotation.panels` (§6.9).
  - The exact maintenance start time and the `overlay.broadcast_tz` value (owner).
