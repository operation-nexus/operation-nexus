# SPEC: Configuration, Balance & Content

Status: Approved (owner, 2026-10-21) · Owner: — · Tracker: NX-106, NX-008, NX-031 · Related ADRs: 0002 (determinism), 0003 (persistence), 0004 (toolchain) · Policy: [DATA-INTEGRITY](../quality/DATA-INTEGRITY.md) DI-7

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
- **CFG-5** Every balance key MUST carry its unit in the schema (`x-unit` annotation; `x-hot-reload` carries the §6 HR column) and in this spec. All rates are per second of **world** time (CFG-9) unless the unit says otherwise (SIM-CORE SC-2).
- **CFG-6** Content cross-references (unit kinds in theaters, doctrine perks naming unit kinds, template slots) MUST be validated at load and in CI (§8).
- **CFG-7** Secrets MUST NOT appear in any config file. Config refers to secrets by name only (`secret_ref`), and the values come from the environment / secret store (THREAT-MODEL SEC-CI, CICD §8).
- **CFG-8** All user-visible authored text (node names, callsign words, sitrep templates) MUST pass the moderation denylist in CI (SEC-MOD-1).
- **CFG-9 Clocks (Q-CFG-8, Q-ALN-1, Q-ALN-4, Q-ALN-5, Q-ALN-6, Q-ALN-23, Q-ALN-35, Q-ALN-38):** every time-valued key MUST name one of three clocks in its schema `x-unit` annotation and in this spec (`s (world)`, `min (game)`, `s (real)`, ...).
  - **World time** (`world`) is sim ticks scaled by `sim.time_scale`: while the campaign runs, 1 real second = `sim.time_scale` world seconds. It drives movement, logistics and combat (speeds, fuel, logistics and repair rates, weapon reload), plus capture progress and decay, bridge repair, the FoW sensor refresh and track fade (FOG-OF-WAR FOW-9) (Q-ALN-23). The Tier 1 sensor refresh is expressed in world time so its real cadence stays about 8–10 s: PROPOSED ~48–60 s world at `sim.time_scale` 6 (Q-ALN-38). Deterministic; frozen while paused.
  - **Game time** (`game`) is unscaled sim ticks: while the campaign runs, 1 game minute = 1 real minute. It drives player-facing durations: idle handoff/retire, respawn delay (Q-ALN-5), rank and doctrine ability cooldowns, campaign length, the objective period and the victory/defeat holds. Per Q-ALN-23 it also drives the Threat Director decision window, tier dwell, CP EMA, the memory and provocation half-lives, the Pattern of Life periods, the night-progress cap, the Tasking Board claim lease and priority aging, and the package fill wait (GAMEPLAY §7). (The CHARLIE warning lead time, game time per Q-ALN-35, is parked with CHARLIE, Q-TD-3.) Deterministic; frozen while paused.
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
| Content | `content/theaters/*.yaml`, `content/units/*.yaml` with `content/weapons.yaml` and `content/roles.yaml` (§7a), `content/doctrines.yaml`, `content/text/*.yaml` | YAML | Yes (theater, units, doctrines); No (text) | Yes (all, text included, so replays are exact) | New campaign only |

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
- **Canonical form:** parse YAML, convert it to a JSON-compatible tree, sort keys, serialize as UTF-8 JSON with no insignificant whitespace, then compute blake2b-256 over it. Floats are serialized with Python `repr` round-trip precision. YAML anchors and aliases are expanded before hashing. The tree hashed is the schema-validated one (`model_dump()`), so `6` and `6.0` in a float key hash alike (NX-106).
- **Strict YAML (owner, 2026-10-21):** files are parsed safe-load only (`nexus.runtime.config.StrictLoader`), with YAML 1.2 core booleans and numbers. Rejected at load, naming the file and position or key:
  - an unquoted YAML 1.1 boolean word (`yes`, `no`, `on`, `off`, `y`, `n`, any case); only `true`/`false` are booleans, and a quoted word is a string;
  - `.inf` and `.nan`;
  - a key repeated in one mapping (a `<<` merge followed by an explicit key is an override, not a duplicate);
  - YAML 1.1 number forms (hex `0x`, octal `0o` or a leading zero, `_` separators, sexagesimal `1:30`): they stay strings, which the schema then rejects for a numeric key.
- **Bounds:** durations given to the tick conversion (CFG-9) must be finite and ≥ 0; a schema key gets a maximum only once the balance harness proposes one (NX-031).
- **`config_hash`** = blake2b-256 over the concatenation of the canonical hashes (raw 32-byte digests), in a fixed order: `balance`, `units`, `operations`, `doctrines`, `theater` (the one selected for the campaign), `text`. Each part joins with its loader; until then the hash covers only the parts that exist (today `balance`, NX-106, `units`, NX-367, `operations`, NX-156, and `theater`, NX-120). The `operations` digest is `operations.operations_hash`: the canonical hash of the validated catalog in id order, so file order does not matter, never a placeholder for a missing part. The `units` digest is `units.catalog_hash`: the canonical hash of the validated tree `{units: [by kind], weapons: [by id], roles: {...}}`, so file order and formatting do not matter.
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
| `fow.track_fade_s` | float | s (world), > 0 | 180 (PROPOSED by NX-150: 300 ticks, 30 real s at 6×). How long a last-known track lasts; converted to world ticks rounding up. In the schema now (NX-150) | FOG-OF-WAR FOW-6a, Q-FOW-1 | No |
| `fow.track_every_ticks` | int | ticks, ≥ 1 | 5 (PROPOSED). In the schema now (NX-150) | FOG-OF-WAR FOW-5, Q-FOW-6 | No |
| `fow.sigint_range_mult` | float | × a radar site's `sensor.radius_m`, > 0 | 1.5 (PROPOSED by NX-150: 180 km for a 120 km radar). A moving enemy unit outside the side's sensors forms a SIGINT blob within this multiple of a friendly non-dark radar site's radius. In the schema now (NX-150) | FOG-OF-WAR Tier 1, Q-FOW-7 | No |
| `fow.sigint_refresh_s` | float | s (world), > 0 | 54 (PROPOSED by NX-150 inside Q-ALN-38's 48–60: 90 ticks, 9 real s at 6×). Running world time between blob rebuilds, converted to world ticks rounding up. In the schema now (NX-150) | FOG-OF-WAR FOW-5, FOW-9 | No |
| `fow.sigint_cell_m` | int | m, ≥ 1 | 10000 (PROPOSED). Side of the square cell blobs aggregate into and are drawn at; must divide the theater's `bounds_m` (checked when the rules are built), so every cell centre lies on the map. In the schema now (NX-150) | FOG-OF-WAR Tier 1 | No |
| `fow.sigint_size_m_min` | int | units, ≥ 2 | 3 (PROPOSED by NX-150). A blob of at least this many units reads M; fewer reads S. In the schema now (NX-150) | FOG-OF-WAR Tier 1 | No |
| `fow.sigint_size_l_min` | int | units, > `fow.sigint_size_m_min` (checked at load) | 7 (PROPOSED by NX-150). A blob of at least this many units reads L. In the schema now (NX-150) | FOG-OF-WAR Tier 1 | No |
| `fow.paint_range_m` | float | m, > 0 | 20000 (PROPOSED by NX-150: a third of a recon UAV's 60 km sensor). A recon unit paints a target it tracks itself within this range. In the schema now (NX-150) | FOG-OF-WAR Tier 2 painted flag, Q-FOW-6 | No |
| `air.bingo_reserve_frac` | float | fraction of the kind's `fuel_s`, 0–1 | 0.15 (PROPOSED by NX-368). Bingo: an airborne aircraft RTBs once its fuel is at most the flight time to the nearest base it can land at plus this reserve. In the schema now (NX-368) | STATE-MACHINES §4.1, Q-SIM-38 | No |
| `air.orbit_period_s` | float | s (world), > 0 | 120 (PROPOSED by NX-368). One lap of an idle airborne aircraft's orbit at its `min_speed_mps`; the radius is `min_speed_mps` × this / 2π (about 1.9 km for a jet). In the schema now (NX-368) | SIM-CORE §4, GAMEPLAY §5 | No |

### 6.2 Slots, respawn, reserve
In the schema now (NX-122): `slots.max_live_per_commander`, `slots.respawn_delay_s`, `slots.max_viewer_units` and `slots.reserve_queue_max`, read by the JOIN handler and the reserve queue (SIM-CORE §4). The hot-reloadable ones are read once at load until config reload exists; a reload must rebuild the kernel's `Rules` and be logged. `slots.queue_idle_min` joins with the runtime's queue timeout.

| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `slots.max_live_per_commander` | int | units | 1 | GAMEPLAY GP-1 | No |
| `slots.respawn_delay_s` | float | s (game) | 20 | GAMEPLAY GP-2 (game time: the JOIN guard runs in the sim, Q-ALN-5) | Yes |
| `slots.max_viewer_units` | int | units | 500 | GAMEPLAY GP-3, Q-GD-6, Q-SIM-6 | Yes |
| `slots.queue_idle_min` | int | min (real time) | 15 | GAMEPLAY RQ-1, Q-SIM-12 | Yes |
| `slots.reserve_queue_max` | int | entries | 1000 (PROPOSED by NX-122, Q-CFG-11: twice the cap; bounds the queue a flood of new commanders can build in world state and snapshots). A newcomer to a full queue gets `RESERVE_QUEUE_FULL` | GAMEPLAY GP-3 | Yes |
| `presence.idle_handoff_min` | float | min (game) | 10 (Q-GD-35). With no command from its operator for this long, a live unit finishes its current order and joins the Tasking Board as an AI-run unit (AUTO tag). Any command from the operator restores control | GAMEPLAY §1b, STATE-MACHINES §4.1 | Yes |
| `presence.idle_retire_min` | float | min (game) | 30 (Q-GD-35). With no command for this long, the unit RTBs and despawns; carried supplies return to the reserve. Together with `presence.idle_handoff_min` it replaces the old idle-despawn timer entirely (Q-ALN-8) | STATE-MACHINES §4.1 | Yes |

### 6.3 Logistics
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `logistics.node_max_stock.<node_kind>` | int | stock units | AIRBASE 2000, FOB 1000, HQ 2000, PORT 1000, BRIDGE 0; SANCTUARY and the rear source infinite (Q-SIM-49). In code (NX-123): all five keys required; a theater `start_stock` above its kind's maximum fails load | GAMEPLAY §5 | No |
| `logistics.starve_threshold` | float | fraction 0–1 | 0.25. In code (NX-123): the floor is `ceil(starve_threshold x max)` whole units | GAMEPLAY §5 | No |
| `logistics.starve_hp_drain_per_min` | int | node hp per min (game) | 5 (PROPOSED, Q-SIM-71). In code (NX-124 part 3): a node with finite stock below its starvation floor loses this many whole hp per game minute (600 running ticks at 10 Hz), carried exactly across ticks; 0 turns the drain off | GAMEPLAY §8 | No |
| `logistics.defense_repair_hp_per_stock` | int | hp per stock unit | 2 (PROPOSED, Q-SIM-71; key named by NX-124 part 3): defense hp one stock unit unloaded into a node rebuilds, up to `capture.defense_hp` | GAMEPLAY §8 | No |
| `logistics.starved_loadout.fuel_frac` | float | fraction | 0.5 (Q-SIM-53). In code (NX-123 part 2): a base below its starvation floor refuels an aircraft only up to this share of `fuel_s`; a spawn is always full | GAMEPLAY §5 | No |
| `logistics.starved_loadout.secondary_ammo` | int | rounds | 0 (a code rule, not a key: a starved base restocks only guns, NX-124 part 2) | GAMEPLAY §5 | No |
| `logistics.truck_cargo` | int | stock units | 100 (Q-SIM-49). One global value for every cargo kind (NX-123); a per-kind catalog `cargo` (§7.3) would replace it | GAMEPLAY §5 | No |
| `logistics.unload_rate` | float | stock/s (world) | 1.0 (Q-SIM-49). Counted in whole thousandths per tick, so the loader rejects a rate x tick below 0.001 | GAMEPLAY §5 | No |
| `logistics.loadout_cost.<unit_kind>` | int | stock units | STRIKE_FIGHTER, ENEMY_FIGHTER and ENEMY_STRIKE_FIGHTER 20, RECON_UAV and ENEMY_RECON_UAV 5, ENEMY_ARMOR 15, GARRISON_INFANTRY 5, LOGI_TRUCK and ENEMY_CONVOY 0 (Q-SIM-49). In code (NX-123 part 2) as a balance table keyed by those nine kinds, all required (facilities are placed by the theater, not spawned, and have none); the debit at forward deploy and the price of a full refill (Q-SIM-51). The per-unit catalog `loadout_cost` in §7.3 is not used | GAMEPLAY §5 | No |
| `logistics.rearm_rate` | float | stock/s (world) | 0.5 (Q-SIM-49). Landed aircraft buy fuel at this rate. Counted in whole thousandths per tick, so the loader rejects a rate x tick below 0.001 | GAMEPLAY §5 | No |
| `logistics.offroad_speed_mult` | float | multiplier | 0.5 (from raw plans P987; unvalidated) | GAMEPLAY §5 | No |
| `logistics.bridge_repair_time_s` | float | s (world) | TBD (engineer repair time; Q-GD-11) | GAMEPLAY §5 | No |
| `logistics.truck_bridge_repair_mult` | float | multiplier on engineer time | 5 (Q-GD-11 recommendation "e.g. 5× slower") | GAMEPLAY §5 | No |
| `tasking.follow_station_m.<pairing>` | float | m (world) | PROPOSED (Q-SIM-76): `escort` 500 (a ground combat unit ahead of its truck), `column` 200 (a ground unit behind its ground leader), `overwatch` 3000 (an aircraft over a ground unit), `wingman` 1000 (an aircraft off its lead) | GAMEPLAY §1b, Q-GP-32 | Yes |
| `tasking.escort_threat_memory_s` | float | s (world) | PROPOSED 60 (Q-SIM-76): a tracked enemy that fired at a convoy or column member this recently is a group threat | GAMEPLAY §1b | Yes |
| `tasking.escort_leash_m` | float | m | PROPOSED 10000 (Q-SIM-76): the farthest an escort leaves station to engage; also the range within which followers form a speed group (NX-369) | GAMEPLAY §1b, §5 | Yes |
| `progression.follower_share` | float | fraction of the outcome's merit per follower | TBD (PROPOSED) | GAMEPLAY §1b, PROGRESSION, Q-GP-42 | No |
| `progression.follower_share_cap` | int | max followers credited per outcome | TBD (PROPOSED) | GAMEPLAY §1b, Q-GP-42 | No |
| `logistics.facility_repair_hp_per_stock` | int | hp per stock unit | 10 (PROPOSED, Q-SIM-68). In code (NX-124 part 2) | GAMEPLAY §5b | No |
| `logistics.facility_rearm_cost` | int | stock units | 10 (PROPOSED, Q-SIM-69). In code (NX-124 part 2): a facility's full reload of all its weapons, by ammo share | GAMEPLAY §5b | No |
| `logistics.forward_deploy_min_surplus` | int | stock units above the starvation floor a spawn base needs to accept a forward deploy | 50 (Q-SIM-49, Q-SIM-54). In code (NX-123 part 2); the base also needs at least the loadout cost above its floor | GAMEPLAY §4, Q-GP-41 | No |
| `logistics.repair_rate.<node_kind>` | float | hp/s (world) | AIRBASE 1.0, HQ 1.0, PORT 1.0, FOB 0.5, SANCTUARY 2.0 and free (PROPOSED, Q-SIM-68). In code (NX-124 part 2): all five required; counted in thousandths of an hp per tick | GAMEPLAY §5 | No |

### 6.4 Combat
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `combat.track_quality.track` | float | multiplier | 1.0. In code (NX-124) | COMBAT | No |
| `combat.track_quality.painted` | float | multiplier | 1.25. In code (NX-124) | COMBAT | No |
| `combat.jammer_pk_mult` | float | multiplier | not built; 1.0 fallback FB-6 until the jammer arrives (NX-212) | COMBAT | No |
| `combat.weapons.<weapon_id>` | object | see §7.2 | superseded: weapon profiles are `content/weapons.yaml` (§7), not a balance key | COMBAT | No |
| `combat.pk_cap` | float | max Pk | 0.95 (PROPOSED, Q-CBT-10). In code (NX-124) | COMBAT CB-4 | No |
| `combat.range.full_pk_frac` | float | fraction of `range_m` with full range factor | 0.5 (PROPOSED, Q-CBT-10). In code (NX-124) | COMBAT §5.2 | No |
| `combat.range.min_mult` | float | range factor at `range_m` | 0.5 (PROPOSED, Q-CBT-10). In code (NX-124) | COMBAT §5.2 | No |
| `combat.disabled_timeout_s` | float | s (game) | 600 (PROPOSED, Q-CBT-14). In code (NX-124): converted to ticks at load, rounded up | COMBAT CB-7 | No |
| `combat.assist_window_s` | float | s (game) | 120 (PROPOSED, Q-SIM-66). In code (NX-124): converted to ticks at load, rounded up | COMBAT CB-5a | No |
| `combat.pk_mult.countermeasure` | float | multiplier (one-shot per load) | not built; 1.0 fallback FB-6 until countermeasures arrive (Q-CBT-20) | COMBAT §5.2 (Q-CBT-2) | No |
| `combat.pk_mult.terrain_masked` | float | multiplier | 0.5 (PROPOSED, Q-CBT-11). In code (NX-124) | COMBAT §5.2 (Q-CBT-2) | No |
| `combat.pk_mult.weather.*` / `combat.pk_mult.night` | float | multiplier | TBD (P4, Q-CBT-5) | COMBAT | No |
| `combat.damage_state.damaged_below` | float | hp fraction | 0.70 (PROPOSED). In code (NX-124); the three thresholds must descend (loader) | COMBAT CB-6, Q-GP-8 | No |
| `combat.damage_state.mission_kill_below` | float | hp fraction | 0.35 (PROPOSED). In code (NX-124) | COMBAT CB-6, Q-GP-8 | No |
| `combat.damage_state.disabled_below` | float | hp fraction | 0.10 (PROPOSED). In code (NX-124); a facility's hp floors just under it | COMBAT CB-6, Q-GP-8 | No |
| `combat.damage_state.damaged_speed_mult`, `.damaged_sensor_mult` | float | multiplier | 0.75 and 0.8 (PROPOSED, Q-SIM-65). In code (NX-124 part 2) | COMBAT CB-6 (Q-CBT-1) | No |
| `combat.crew_survival.<kind>` | float | probability | aircraft 0.75, ENEMY_ARMOR 0.60, GARRISON_INFANTRY 0.50, LOGI_TRUCK and ENEMY_CONVOY 0.70 (PROPOSED, Q-SIM-68). In code (NX-124 part 2): one per kind with crew above 0, all required | COMBAT CB-8 | No |
| `combat.crew_marker_min` | float | min (game) | 10 (PROPOSED, Q-SIM-68). In code (NX-124 part 2) | COMBAT CB-8 | No |
| `slots.respawn_loss_window_s` / `slots.respawn_loss_step_s` | float | s (game) | TBD (respawn grows with repeated losses, Q-CBT-9; game time per Q-ALN-5) | GAMEPLAY GP-2 | Yes |

### 6.5 Capture
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `capture.radius_m` | float | m | 2000 (PROPOSED, owner-approved initial value, Q-SIM-57): a ground unit this close counts for the node; a defender's unit this close is at the base | GAMEPLAY §8 | No |
| `capture.time_s` | float | s (world, Q-ALN-23) | 120 | GAMEPLAY §8 | No |
| `capture.multi_unit_exponent` | float | exponent (diminishing returns) | 0.5 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.quiet_floor` | float | multiplier at 0 viewer units | 0.6 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.quiet_ref` | int | viewer units at which the multiplier reaches 1.0 | 50 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.min_time_s` | float | s (world, Q-ALN-23) | 30 (PROPOSED) | GAMEPLAY §8, Q-SIM-26 | No |
| `capture.logi_weight` | float | capturer weight | 0.5 (PROPOSED): a logistics unit counts as half a capturer (Q-SM-7) | STATE-MACHINES §4.2 | No |
| `capture.garrison_mult` | float | capture-time multiplier | 3.0 (PROPOSED): a defender that cannot contest is at the base (Q-GD-32, Q-SM-8) | STATE-MACHINES §4.2 | No |
| `capture.empty_base_mult` | float | capture-time multiplier | 0.5 (PROPOSED): no defender at the base (Q-GD-32, Q-SM-8) | STATE-MACHINES §4.2 | No |
| `capture.defense_hp.<node_kind>` | int | hp | AIRBASE 500, FOB 300, HQ 800, PORT 300, SANCTUARY 1000 (PROPOSED, Q-SIM-71; key named by NX-124 part 3; BRIDGE has none until NX-373). An owned node starts at the maximum, a NEUTRAL one at 0, a node that changes hands at 0 for its new owner. All five keys required | GAMEPLAY §8 | No |
| `capture.sanctuary_repair_hp_per_s` | float | hp/s (world) per unit | 1.0 (PROPOSED, Q-SIM-71; key named by NX-124 part 3): defense hp each friendly logistics unit parked at its side's SANCTUARY rebuilds there, from the sanctuary's infinite supply (no stock debit). Counted in whole thousandths of an hp per tick, so the loader rejects a rate x tick below 0.001 | GAMEPLAY §9 | No |
| `capture.decay_per_s` | float | bar fraction/s (world, Q-ALN-23) | 1/120 (0.008333…, PROPOSED, owner-approved initial value, Q-SIM-57): an abandoned bar empties in the 120 world s one unit takes to fill it. Counted in whole millionths of a percent per tick, rounded (the loader refuses less than one) | GAMEPLAY §8 | No |

In code since NX-125: all ten keys are the `capture` block of `balance/default.yaml` (`contracts/config/balance.json`), read by `nexus.core.capture`; the shipped values are the PROPOSED column.

### 6.6 Campaign
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `campaign.target_duration_h` | float | h (game) | 48 | GAMEPLAY §9, Q-GD-5 | No |
| `campaign.time_limit_h` | float | h (game) | 72 (PROPOSED, Q-TEST-6) | GAMEPLAY §9 | No (set per campaign) |
| `campaign.max_extension_h` | float | h (game), total of all extensions | 48 (PROPOSED, Q-TEST-7); extensions by the owner or an Admin only, each logged | GAMEPLAY §9 | No |
| `campaign.score.average_weight` | float | points | 50 (PROPOSED, Q-SIM-64): × a side's average share of strategic nodes over the campaign (replaces `node_share_weight` 100, Q-SM-9) | STATE-MACHINES §4.4 | No |
| `campaign.score.final_weight` | float | points | 50 (PROPOSED, Q-SIM-64): × a side's share of strategic nodes at the final tick | STATE-MACHINES §4.4 | No |
| `campaign.score.objective_points` | float | points per completed objective | 5 (PROPOSED, Q-GD-29, Q-SM-9) | STATE-MACHINES §4.4 | No |
| `campaign.objective_period_min` | float | min (game) | 15: an objective's lifetime; the next is announced when one resolves (STATE-MACHINES §4.5) | GAMEPLAY §9 | No |
| `campaign.victory_node_frac` | float | fraction | 0.80 | GAMEPLAY §9 | No |
| `campaign.victory_hold_min` | float | min (game) | 30 | GAMEPLAY §9 | No |
| `campaign.momentum.nodes_weight` | float | percentage points | 70 (PROPOSED, Q-SIM-60): × the coalition's share of strategic nodes in the momentum % | GAMEPLAY §9, Q-SIM-60 | No |
| `campaign.momentum.supply_weight` | float | percentage points | 30 (PROPOSED, Q-SIM-60): × the coalition's supply fill (its finite bases' stock ÷ their max stock); the two weights must add up to 100 | GAMEPLAY §9, Q-SIM-60 | No |
| `campaign.defeat` | object | — | `{hold_min: 30}`: the sanctuary's defense HP must stay at 0 this long (Q-TH-7, replacing Q-GD-7's forward-airbase rule; PROPOSED; game minutes, Q-ALN-1). In code (NX-124 part 3): required in the balance profile; `hold_min` is converted to running ticks at load | GAMEPLAY §9 | No |
| `campaign.objective_mode` | enum `timed`\|`off` | — | `timed` (Q-GD-19); chosen at campaign setup by owner/admin only (Q-ALN-10) | GAMEPLAY §9 | No (set per campaign) |
| `campaign.options.unlimited_ammo` | bool | — | not in the schema yet (NX-124 part 2 does not honour it); false (Q-CBT-7; test/special-event option; set at campaign setup by owner/admin only, not GM, Q-ALN-10) | GAMEPLAY §5 | No |
| `campaign.intermission.mode` | enum `auto_advance`\|`await_owner` | — | TBD (owner choice per campaign, Q-UX-8) | GAMEPLAY §9 | Yes |
| `tasking.claim_lease_s` | float | s (game, Q-ALN-23) | 120 (PROPOSED, Q-SIM-73): a claim auto-releases when its unit makes no progress for this long (Q-GD-37) | GAMEPLAY §1b | Yes |
| `tasking.priority.<job_kind>` | float | base priority | PROPOSED (Q-SIM-73), by lower-case `JobKind`: defend 60, resupply 50, assist_objective 45, strike 40, scout 30, escort_convoy 40, stage 20, capture 45 (the Director's two kinds, lead decision, NX-156; repair_bridge joins with NX-373) | GAMEPLAY §1b, Q-GP-20 | Yes |
| `tasking.urgency_max` | float | multiplier cap (1.0–2.0) | 2.0 (PROPOSED, Q-SIM-73) | GAMEPLAY §1b, Q-GP-20 | Yes |
| `tasking.priority_aging_per_min` | float | priority points/min (game, Q-ALN-23) | 1 (PROPOSED, Q-SIM-73): old jobs gain priority so they aren't starved (Q-GD-37) | GAMEPLAY §1b | Yes |
| `tasking.reeval_every_ticks` | int | ticks | 50 (PROPOSED, Q-SIM-73): boards are re-evaluated every N running ticks, not every tick (Q-GD-37) | GAMEPLAY §1b | Yes |
| `tasking.expire_min` | float | min (game, Q-ALN-23) | 15 (PROPOSED, Q-SIM-73): an unclaimed job expires this long after it was posted (objective jobs: with the objective) | GAMEPLAY §1b | Yes |
| `tasking.slots.<job_kind>` | int | units | PROPOSED (Q-SIM-73): defend 2, strike 2, assist_objective 4, scout 1, escort_convoy 2 | GAMEPLAY §1b, TB-4 | Yes |
| `tasking.resupply_stock_per_slot` | int | stock units | 100 (PROPOSED, Q-SIM-73): a resupply job gets one slot per this much missing stock (max stock minus stock, rounded up, at least 1) | GAMEPLAY §1b | Yes |
| `tasking.resupply_slots_max` | int | units | 3 (PROPOSED, Q-SIM-73) | GAMEPLAY §1b | Yes |
| `tasking.defend_radius_m` | float | m | 10000 (PROPOSED, Q-SIM-74): a base posts a defend job when its side tracks an enemy ground unit this close; urgency 1.0 at the radius rising to the cap at the base | GAMEPLAY §1b | Yes |
| `tasking.counterattack_window_min` | float | min (game, Q-ALN-23) | 15 (PROPOSED, Q-SIM-74, Q-GD-31): for this long after a node is lost the AI garrison may take strike and assist-objective jobs against it | GAMEPLAY §1b | Yes |
| `tasking.scout_post_interval_min` | float | min (game) | 2 (PROPOSED, Q-DEV-21): at most one new generated scout job per board per this long (highest urgency, ties by key) | GAMEPLAY §1b | Yes |
| `tasking.capture_max_restarts` | int | restarts | 3 (PROPOSED, Q-SIM-84): a CAPTURE job whose claimants are still driving at its expiry gets a fresh one this many times, then expires normally | GAMEPLAY §1b | Yes |
| `tasking.scout_open_max` | int | jobs | 3 (PROPOSED, Q-SIM-82, NX-156): the most generated scout jobs a board holds at once; claimed ones stay, then highest urgency, ties by key | GAMEPLAY §1b | Yes |
| `tasking.scout_cooldown_min` | float | min (game, Q-ALN-23) | 5 (PROPOSED, Q-SIM-75): a generated scout job for a cell that ended (DONE, EXPIRED or FAILED) is not posted again this long (Q-DEV-21) | GAMEPLAY §1b | Yes |
| `director.pol.patrol_period_s` | float | s (game, Q-ALN-23) | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `director.pol.convoy_period_s` | float | s (game, Q-ALN-23) | TBD by harness | THREAT-DIRECTOR §5a | Yes |
| `director.provocation.weights.<action>` | float | score per action | `unit_destroyed` 5, `unit_damaged` 1 (per hit), `convoy_hit` 3, `facility_damaged` 3, `facility_disabled` 8, `base_captured` 15, `scout_in_rear` 2 (per window) (PROPOSED, Q-SIM-78); only player-controlled units cause them | THREAT-DIRECTOR §5a | Yes |
| `director.provocation.weights.redemption.<type>` | float | score per redemption | Support (supply drop, repair, reinforcements, Q-AI-9; respawn skip, queue jump, Q-ALN-13) = small weight, 1 (PROPOSED, Q-SIM-78); cosmetic (color, ping, shoutout) = 0 (owner) (Q-AI-9). The keys are the two classes, `support` and `cosmetic`, until redemption types exist (SUPPORT-REDEMPTIONS). There is no offensive redemption class: the no-damage rule stands (Q-ALN-13) | THREAT-DIRECTOR §5a | Yes |
| `campaign.rubber_band_zone` | [float, float] | fraction of nodes | [0.55, 0.75] | GAMEPLAY §9 | No |
| `director.provocation.escalate_threshold` | float | score | 10 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §5a | Yes |
| `director.provocation.half_life_s` | float | s (game, Q-ALN-23) | 900 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §5a | Yes |
| `presence.window_s` | float | s (real) | TBD (drives the HUD operator count and breakdown only; the clock never pauses for lack of operators, Q-GD-4 amended / Q-SM-5; pauses come only from the `PauseReasonCategory` causes in CFG-9, Q-ALN-3) | CONTRACTS §6 `PresenceSnapshot` | No |
| `presence.emit_every_ticks` | int | ticks | TBD | CONTRACTS §6 `PresenceSnapshot` | No |
| `campaign.night_progress_cap_nodes_per_h` | float | nodes/h (game, Q-ALN-23) | 1/6 | THREAT-DIRECTOR §5, Q-GD-4 (amended) | No |
| `campaign.aar_duration_s` | float | s (real) | 300 | GAMEPLAY §9 | Yes |

In code since NX-126: the `campaign` block of `balance/default.yaml` (`contracts/config/balance.json`) holds `time_limit_h`, `victory_node_frac`, `victory_hold_min`, `objective_period_min`, `objective_mode` (read from the balance profile until a per-campaign setting exists), `score.average_weight`, `score.final_weight`, `score.objective_points` and `momentum.nodes_weight` and `supply_weight`; `nexus.core.campaign` reads them. The three durations are game time, converted once at load (`game_ticks`, with the key's unit: 72 h = 2,592,000 ticks, 30 min = 18,000, 15 min = 9,000 at 10 Hz). The fractions and weights are read as the exact decimals written, so a threshold or a score tie is exact. `target_duration_h`, `max_extension_h`, `defeat`, `options`, `intermission`, `rubber_band_zone` and the night cap are not read yet.

In code since NX-374: the required `tasking` block of `balance/default.yaml` (`contracts/config/balance.json`) holds the keys above (`priority` and `slots` are objects keyed by lower-case job kind). `claim_lease_s` and `expire_min` are game time and become running ticks at load (`Rules.tasking`); priorities, the aging rate and the urgency cap are kept exact.

### 6.7 Threat Director
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `director.window_s` | float | s (game, Q-ALN-23) | 60 | THREAT-DIRECTOR §4 | No |
| `director.cp.unit_value.<unit_kind>` | float | CP points | STRIKE_FIGHTER 10, RECON_UAV 3, LOGI_TRUCK 2, GARRISON_INFANTRY 2 (PROPOSED, Q-SIM-78); every coalition-side kind of the unit catalog must have one (the loader refuses a missing one), facilities and other kinds count 0 | THREAT-DIRECTOR §2 | Yes |
| `director.cp.ema_window_s` | float | s (game, Q-ALN-23) | 300 | THREAT-DIRECTOR §2 | Yes |
| `director.tier.bravo_enter_cp` | float | CP | 60 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §3 | Yes |
| `director.provocation.bravo_threshold` | float | provocation score | 40 (PROPOSED, Q-SIM-78); the loader requires it above `escalate_threshold` | THREAT-DIRECTOR §3, Q-TD-1 | Yes |
| `director.tier.exit_ratio` | float | fraction of enter | 0.8 | THREAT-DIRECTOR §3 | Yes |
| `director.tier.min_dwell_s` | float | s (game, Q-ALN-23) | 600 | THREAT-DIRECTOR §3 | Yes |
| `director.budget.<tier>` | int | budget points / window | `pattern_of_life` 10, `alpha` 30, `bravo` 80 (PROPOSED, Q-SIM-78); never above the Static's real surplus (Q-TD-5) | THREAT-DIRECTOR §4 | Yes |
| `director.max_spawns_per_window` | int | units / window | 6 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §4, Q-TD-12 | Yes |
| `director.max_live_units.<tier>` | int | units | `pattern_of_life` 24, `alpha` 40, `bravo` 70 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §4, Q-TD-12 | Yes |
| `director.op_priority.<op>` | float | base priority | RETAKE 1.2, OFFENSIVE 1.0, ESCORT_CONVOYS 0.8, REINFORCE_IADS 0.7, PROBE 0.6, RECON 0.5, DECOY_BLINK 0.3 (PROPOSED, Q-SIM-78); exactly the catalog's ids | THREAT-DIRECTOR §4, Q-TD-6 | Yes |
| `director.score.target_value.<node_kind>` | float | multiplier | AIRBASE 1.5, FOB 1.0, PORT 1.0, SANCTUARY 2.0 (PROPOSED, Q-SIM-78); a kind not listed is never a target |
| `director.score.weakness_max` | float | multiplier | 2.0 (PROPOSED, Q-SIM-78): the weakness multiplier at no defenses, 1.0 at full, linear | THREAT-DIRECTOR §4 | Yes | THREAT-DIRECTOR §4, Q-TD-6 | Yes |
| `director.score.provocation_proximity` | float | multiplier | 1.5 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §5, Q-TD-4 | Yes |
| `director.memory.half_life_s` | float | s (game, Q-ALN-23) | 1800 | THREAT-DIRECTOR §2 | Yes |
| `director.noise_scale` | float | fraction of the score | 0.1 (PROPOSED, Q-SIM-78) | THREAT-DIRECTOR §4 | Yes |
| `director.decoy_blink.dark_s` | float | s (game) | 120 (PROPOSED, Q-SIM-82, owner): how long a blinking radar stays dark | FOG-OF-WAR FOW-11 | Yes |
| `director.decoy_blink.cooldown_s` | float | s (game) | 600 (PROPOSED, Q-SIM-82, owner): before the same radar can blink again; one radar blinks per window | FOG-OF-WAR FOW-11 | Yes |
| `director.decoy_blink.max_per_window` | int | radars | 1 (PROPOSED, Q-SIM-82): radars that start a blink per decision window | FOG-OF-WAR FOW-11 | Yes |
| `director.adaptation_up_above` | float | events | 0 (PROPOSED): a ThreatAdaptation goes UP when its counter is above this as the matching operation launches | THREAT-DIRECTOR §4 step 5 | Yes |
| `director.reinforce_damage_above` | float | fraction | 0 (PROPOSED, Q-SIM-81): share of an air-defense site's HP missing above which ReinforceIADS counts it damaged (0 = any damage) | THREAT-DIRECTOR §4 | Yes |
| `director.escort_min_convoys` | int | convoys | 1 (PROPOSED): the fewest convoys an escort operation is cut to when units are short | THREAT-DIRECTOR §4 step 6 | Yes |
| `director.frontline_hops` | int | road hops | 1 (PROPOSED): a node is on the front when a node within this many hops has another owner | THREAT-DIRECTOR §4 | Yes |
| `director.memory.factor` | float | multiplier | 1 (PROPOSED): k in the memory multiplier 1 + k c (RAISE) or 1 / (1 + k c) (LOWER) | THREAT-DIRECTOR §2, §4 | Yes |
| `director.score.own_node_value` | float | multiplier | 1.0 (PROPOSED, Q-DEV-21): target value of a node the Static already holds (ReinforceIADS) | THREAT-DIRECTOR §4 | Yes |
| `director.score.weakness_min` | float | multiplier | 1.0 (PROPOSED, Q-SIM-78): the weakness multiplier at full defenses; linear up to `weakness_max` | THREAT-DIRECTOR §4 | Yes |
| `director.score.stale_factor` | float | multiplier | 1.0 (PROPOSED, TD-5): f in the Recon staleness term 1 + f s | THREAT-DIRECTOR §4, TD-5 | Yes |
| `director.idle_retire_s` | float | s (game) | 600 (PROPOSED, Q-SIM-84): a Director unit with no job and no path this long is retired (removed, no refund) | THREAT-DIRECTOR §4 | Yes |
| `director.alpha_max_ops` | int | operations | 1 (PROPOSED, THREAT-DIRECTOR §3): operations with jobs ALPHA runs at once | THREAT-DIRECTOR §3 | Yes |
| `director.job_urgency` | float | multiplier | 1.0 (PROPOSED): urgency of an operation's jobs | THREAT-DIRECTOR §4 | Yes |
| `director.adaptation_down_below` | float | events | 1 (PROPOSED): a ThreatAdaptation goes DOWN below this many events | THREAT-DIRECTOR §4 step 5 | Yes |
| `director.memory.weights.<convoy_hit,radar_hit,scout_lost,node_lost>` | float | events | 1 each (PROPOSED): what one occurrence adds to its counter | THREAT-DIRECTOR §2 | Yes |
| `director.retake_window_min` | float | min (game) | 30 (PROPOSED, Q-SIM-81): a lost Static node can be retaken this long | THREAT-DIRECTOR §4 | Yes |
| `director.advisor.top_k` | int | candidates | TBD (P4) | THREAT-DIRECTOR §6 | Yes |

In code since NX-155 (Threat Director part 1): the required `director` block of `balance/default.yaml` (`contracts/config/balance.json`) holds the keys above through `max_live_units` (`budget` and `max_live_units` are objects keyed by lower-case tier; `cp.unit_value` by unit kind; `provocation.weights` by action). The game-time keys become running ticks at load (`Rules.director`); coalition power and provocation are kept as whole millionths of a point, the half-life as an exact integer per-window multiplier, the dwell, EMA step and exit ratio exactly, so thresholds never meet a float. `provocation.half_life_s` over `window_s` must reduce to a ratio with neither part above 256 (the loader refuses more). `max_spawns_per_window` and `max_live_units` are read by spawning (NX-156). In code since NX-156 (part 2): `op_priority` (an open map by operation id; the loader requires exactly the catalog's ids), `score.target_value`, `score.weakness_max`, `score.provocation_proximity`, `memory.half_life_s` (an exact integer per-window multiplier like the provocation half-life), `noise_scale` (an exact Fraction), `retake_window_min` and the `tasking.priority` keys `stage` (20) and `capture` (45), which are lead decisions, PROPOSED, for the Director's two job kinds. `director.pol.*` and `advisor.top_k` have no code yet.

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
| `ratelimit.class.callsign.min_interval_s` | float | s (real) | 60 (Q-CMD-3) | CHAT-GATEWAY §5 | Yes |
| `ratelimit.class.forget.min_interval_s` | float | s (real) | 60 (Q-CMD-3) | CHAT-GATEWAY §5 | Yes |
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

## 7. Unit catalog (`content/units/*.yaml`, `content/weapons.yaml`, `content/roles.yaml`)

**What exists now (NX-367, Q-CFG-10).** The schemas are `contracts/config/unit.json`, `weapons.json` and `roles.json`; a field enters them with the code that reads it. Today a unit file has `kind`, `side` (`COALITION | ENEMY | BASE`), `domain`, `playable_by` (list), `min_rank` (iff `VIEWER` is in `playable_by`), `speed_mps` (m/s of world time, `>= 0`, a top speed; NX-121, every value PROPOSED: aircraft 250, UAVs 60, trucks and convoys 25, armor 20, infantry 5, facilities 0), `min_speed_mps` and `fuel_s` (AIR kinds only, NX-368, PROPOSED: jets 100 m/s and 3600 world s, about 10 real minutes at 6×; UAVs 20 m/s and 14400 world s), `sensor: {radius_m}` (every kind, m, 0 = none; NX-150, PROPOSED: RADAR_SITE 120 km, recon UAVs 60 km, fighters and AIR_DEFENSE_SITE 40 km, ENEMY_ARMOR 8 km, GARRISON_INFANTRY 5 km, trucks and convoys 3 km), `stealth` (every kind, in (0, 1]; NX-150, PROPOSED 1.0 for all), optional `sensor.passive_range_m` (m, > 0, absent = no passive sensor; NX-150 part 2, FOW-13, PROPOSED: RECON_UAV and ENEMY_RECON_UAV 100 km, RADAR_SITE 150 km, short of the 220 km between strait-1's airbase radars so neither side starts with the other's discovered) and `weapons` (ids); a weapon has `id` and `targets`; `content/roles.yaml` holds `roles:` (`STRIKE`, `RECON`, `LOGI`). One file per unit, named `<kind in kebab-case>.yaml` (§7a); `ANY` is not a side. The loader (`nexus.runtime.units`) rejects: a kind set that is not exactly `UnitKind`, a file name that is not its kind, an unknown or unused weapon id, duplicates, a role mapped to a kind no VIEWER can play, a GARRISON_INFANTRY weapon that can target anything but GROUND (COMBAT §5.1, Q-CBT-25), `min_speed_mps` or `fuel_s` missing on an AIR kind or present on any other, and `min_speed_mps` above `speed_mps` (NX-368). **Combat stats (NX-124 part 1, COMBAT; PROPOSED, the owner's starting values, Q-SIM-65):** every unit has `hp`, `armor` (0 to 0.9), `evasion` (0.6 to 1.0), `crew` and `threat` (STRIKE_FIGHTER and ENEMY_STRIKE_FIGHTER 100, 0, 0.7, 1, 70; ENEMY_FIGHTER 100, 0, 0.7, 1, 80; RECON_UAV and ENEMY_RECON_UAV 60, 0, 1.0, 0, 40; ENEMY_ARMOR 200, 0.5, 1.0, 3, 60; GARRISON_INFANTRY 80, 0, 1.0, 4, 30; LOGI_TRUCK and ENEMY_CONVOY 80, 0, 1.0, 1, 20; RADAR_SITE 150, 0.3, 1.0, 0, 50; AIR_DEFENSE_SITE 150, 0.3, 1.0, 0, 90); AIR kinds also `alt_bands` and `default_alt_band` (fighters LOW/MED/HIGH, UAVs LOW/MED, default MED) and no other kind has them. A weapon has `bands` (non-empty iff its `targets` has AIR), `range_m`, `projectile_speed_mps` (`null` = a gun), `base_pk` (0 to 1), `damage` (hp, >= 1), `reload_s` and `ammo` (>= 1): AA_MISSILE 30 km, 800 m/s, 0.70, 60, 10 s, 4; AA_LIGHT 8 km, gun, 0.50, 30, 2 s, 400; SAM 35 km, 1000 m/s, 0.70, 70, 15 s, 8; AAA_GUN 4 km, gun, 0.30, 15, 2 s, 400; AG_LIGHT 10 km, 300 m/s, 0.70, 50, 10 s, 4; AG_CANNON 4 km, gun, 0.60, 40, 6 s, 40; SMALL_ARMS 1.5 km, gun, 0.40, 8, 2 s, 300. `crew` is read by part 2 (CB-8). The facility variant split is a constant in `nexus.core.rules` until the catalog lists variants: SHORT_RANGE carries AAA_GUN only, SAM and a variant-less site carry every weapon of the file (AAA_GUN then SAM). `homes_on_emitters` joins with SEAD (§5.3a). The rest of the schema below joins with its readers: `display`, `category` and icons with the overlay; cargo and the remaining stats with NX-122. Facility variants are not catalog entries yet: the theater's `variant` is copied onto the entity, and which facilities emit (RADAR_SITE, the SAM variant of AIR_DEFENSE_SITE, FOW-11) is named in `nexus.runtime.campaign_config` until the catalog lists variants; likewise the kinds that paint targets (RECON_UAV, ENEMY_RECON_UAV; FOG-OF-WAR Q-FOW-6) are named in `nexus.core.rules` until the catalog lists capabilities. The weapon ids (`AA_LIGHT`, `AA_MISSILE`, `AAA_GUN`, `SAM`, `AG_LIGHT`, `AG_CANNON`, `SMALL_ARMS`) are PROPOSED names.

### 7.1 Schema
The block shows the full target schema in one listing; on disk `roles:` is `content/roles.yaml`, each `units:` entry is its own `content/units/<kind>.yaml`, and `weapons:` (§7.2) is `content/weapons.yaml`. List order inside a unit (`playable_by`, `weapons`) is hashed as written.
```yaml
schema_version: 1
roles:                        # Role (CONTRACTS §3.3) -> UnitKind; every Role used in the MVP must map to exactly one kind
  STRIKE: STRIKE_FIGHTER
  RECON: RECON_UAV
  LOGI: LOGI_TRUCK              # NAVY added in P3 (Q-GD-8)
units:
  - kind: STRIKE_FIGHTER      # UnitKind (CONTRACTS §3.3), UPPER_SNAKE, unique
    side: COALITION           # COALITION | ENEMY | BASE (facilities: side follows the base, Q-GP-25)
    domain: AIR               # AIR | GROUND | SEA | STATIC
    playable_by: [VIEWER, AI_GARRISON]   # VIEWER | AI_GARRISON | DIRECTOR (one or more)
    min_rank: 1               # PROGRESSION §3; required when playable_by includes VIEWER
    display: { symbol: "air_strike", label_key: "unit.strike_fighter" }   # OV-2 shape-coded symbol id
    speed_mps: <float>        # top speed, m/s of world time (CFG-9)
    min_speed_mps: <float>    # AIR only (required), absent otherwise; stall speed, <= speed_mps (NX-368)
    alt_bands: [LOW, MED]     # AIR only; NOE | LOW | MED | HIGH (COMBAT §5.3)
    default_alt_band: LOW     # AIR only; one of alt_bands
    hp: <int>
    armor: <float>            # 0..0.9; damage taken = damage × (1 − armor) (COMBAT §5.4)
    evasion: <float>          # 0.6..1.0 Pk multiplier on shots at this kind; facilities 1.0 (COMBAT §5.2)
    crew: <int>               # 0 for facilities; drives the crew-survival roll (COMBAT CB-8)
    threat: <int>             # target priority, higher first (COMBAT CB-1, Q-CBT-16)
    fuel_s: <float>           # AIR only (required), absent otherwise; endurance in world s airborne (CFG-9, NX-368)
    sensor: { radius_m: <float>, passive_range_m: <float|null> }   # passive_range_m: detects emitting sites (recon units, radar sites; AWACS later), FOG-OF-WAR FOW-13   # first build: one range for all targets; per-band ranges later. Masking is a property of the target's area (masking_regions, Q-FOW-3)
    weapons: [<weapon_id>]    # refs §7.2; [] = unarmed
    cargo: <int|null>         # stock units; null = cannot carry
    can_capture: <bool>
    stealth: <float>          # detection-radius multiplier in (0, 1] (1.0 = none; NX-150)
    loadout_cost: <int>       # stock consumed at spawn/rearm; in code as balance logistics.loadout_cost.<kind> (§6.3) until the catalog carries it
    cp_value: <float>         # director CP weight (§6.7)
```
Rules:
- **Display:** `display.symbol` must exist in the overlay symbol set (validated against `apps/overlay` symbol manifest in CI).
- **Friend/foe colors:** these come from `side` only, never from the catalog (OV-2).

### 7.2 Weapon profile
```yaml
weapons:
  - id: AGM_LIGHT
    targets: [GROUND, STATIC]   # AIR | GROUND | SEA | STATIC | STRUCTURE (node defenses, bridges); COMBAT §5.1
    bands: []                   # altitude reach against AIR targets only (COMBAT §5.3); this AG weapon has none
    range_m: <float>            # max range; full range factor up to combat.range.full_pk_frac of it
    projectile_speed_mps: <float|null>  # world m/s; null = lands on the fire tick (guns). Impact tick = fire tick + ceil(range / speed / WORLD_DT) (COMBAT CB-2, Q-GP-7)
    base_pk: <float>            # 0..1
    damage: <int>               # hp per hit before armor (COMBAT CB-5)
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
| ENEMY_STRIKE_FIGHTER | ENEMY | AIR | DIRECTOR | — | yes (AG + AA light) | — | no | Mirrors STRIKE_FIGHTER (parity, Q-TD-13); stats TBD by harness |
| ENEMY_RECON_UAV | ENEMY | AIR | DIRECTOR | — | no | — | no | Mirrors RECON_UAV: large sensor, passive range, paints (parity, Q-TD-13); stats TBD by harness |

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


## 8a. Operation catalog (`content/operations.yaml`, Q-TD-7)
The director's operations are content, not kernel code. Each entry names its preconditions (a closed list in the schema), cost, enabled tiers and a **job template**: an ordered list of Tasking Board jobs (job kinds from CONTRACTS `JobKind`, with unit kinds, slot count and an `at` selector; each job after the first depends on the one before) that the operation posts on the Static's board, or an `effect` with no jobs. Selectors resolve only against the Static's view (THREAT-DIRECTOR TD-2). Adding or changing an operation is a content change validated at load (unknown job kinds, selectors or preconditions, a cost outside the envelope are rejected); new behaviour the job kinds can't express needs a spec change first. In code since NX-156: the schema is `contracts/config/operations.json`, the loader `nexus.runtime.operations`, and the shipped file is Q-SIM-81.

```yaml
schema_version: 1
operations:
  - id: OFFENSIVE                     # also the <op> of director.op_priority.<op>
    target: NODE                      # NODE | SECTOR | RADAR | CONVOYS
    preconditions: [target_owner_is_coalition, target_in_enemy_view, target_capturable]
    cost: 60                          # whole budget points, the only home of an operation's cost (Q-SIM-78)
    enabled_tiers: [ALPHA, BRAVO]     # Pattern of Life allows Offensive only under the night cap
    memory: { counter: node_losses_by_sector, effect: RAISE }   # optional; RAISE = x (1 + c), LOWER = / (1 + c)
    track_age: true                   # optional, SECTOR targets: the score rises with a stale picture (TD-5)
    jobs:                             # one unit is bought per slot
      - { kind: STAGE,   at: nearest_own_base, unit_kinds: [ENEMY_ARMOR],          slots: 2 }
      - { kind: STRIKE,  at: target_defenses,  unit_kinds: [ENEMY_STRIKE_FIGHTER], slots: 2 }
      - { kind: CAPTURE, at: target,           unit_kinds: [ENEMY_ARMOR],          slots: 2 }
    # effect: EMISSION_BLINK          # instead of jobs (DecoyBlink)
```
- **Closed lists.** Preconditions: `target_owner_is_coalition` (the other side's node), `target_in_enemy_view`, `target_capturable` (not a sanctuary or bridge), `target_is_frontline` (a road neighbour not of the node's owner), `target_recently_lost` (within `director.retake_window_min`), `target_has_damaged_air_defense`, `target_radar_operational`, `has_unescorted_convoy`. Selectors: `target`, `target_defenses`, `nearest_own_base`, `sector_node`, `each_convoy`. Each suits one target kind (the loader checks), and an `ESCORT_CONVOY` job is the one at `each_convoy`.
- **Cost envelope (Q-TD-7).** A whole number of points from 0 to the largest `director.budget.<tier>`: an operation above it could never run. The loader also checks that a priority exists for every operation and none for another, that the units are ENEMY air or ground kinds that fit the job kind (`tasking_gen.fits`) and that the units bought fit `director.max_spawns_per_window`.
- **Shipped (Q-SIM-81, costs and priorities Q-SIM-78):** OFFENSIVE 60 (stage 2 ENEMY_ARMOR, 2 ENEMY_STRIKE_FIGHTER strike, 2 ENEMY_ARMOR capture), RETAKE 50 (1 strike jet, 3 armor capture; the node lost within 30 game minutes), PROBE 15 (1 strike jet on a frontline base's defenses), RECON 5 (1 ENEMY_RECON_UAV scouts a sector), ESCORT_CONVOYS 10 (Q-SIM-82; 20 in Q-SIM-78) (1 ENEMY_FIGHTER per unescorted convoy), REINFORCE_IADS 15 (1 ENEMY_CONVOY resupplies the base whose air-defense site is damaged), DECOY_BLINK 0 (a radar goes dark for `decoy_blink.dark_s`). Tiers: DECOY_BLINK, RECON and ESCORT_CONVOYS at every tier, the rest at ALPHA and BRAVO. STRIKE_BRIDGE waits for NX-373.

## 9. Theater file format (`content/theaters/<slug>.yaml`)

### 9.1 Schema
The schema is `contracts/config/theater.json` (NX-120); like balance keys, a field enters it with the code that reads it or checks it. Coordinates and bounds are integer metres.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | int | Known version |
| `slug` | string | `^[a-z0-9-]{3,32}$`, equals the filename |
| `name` | string | Display name; moderation-checked (CFG-8) |
| `version` | semver | §4.4 |
| `bounds_m` | `{w, h}` | Map extent in metres (SIM-CORE §4: ~400×240 km for the first theater) |
| `terrain` | object | Optional in the first build (Q-TH-4): `heightmap: <path to 16-bit PNG>`, `height_scale_m`, `sea_level_m`; **or** `contours: <path to GeoJSON-like polylines>`; nothing in the first build reads height. `masking_regions`: polygons where NOE/LOW aircraft and ground units are masked from sensors outside the region, rasterized at load to the spatial grid's cells (cell centre in polygon, integer metres; the theater file is in the config hash; FOG-OF-WAR Tier 2, Q-FOW-3). In code (NX-150 part 2) the raster has its own 1 km cells (`MASK_CELL_M`, PROPOSED), not the SC-10 sensing grid's (60 km on strait-1, coarser than the regions), and a cell may belong to several regions. The NX-120 schema accepts `masking_regions` only; the height fields join with the item that reads height |
| `sectors` | list | `{id, name, polygon}`; non-overlapping; union covers the map (overlap and coverage are checked by NX-182, the first item that reads sector polygons (map annotation layer, OVERLAY AN-1); NX-120 checks ids and node membership) |
| `nodes` | list | `{id, name, kind, pos: [x_m, y_m], start_owner, start_stock, sector, garrison_quota?}`. `garrison_quota` (Static bases): the units the director may keep there at Pattern of Life, replacing losses only (THREAT-DIRECTOR §5a, Q-TD-11) |
| `edges` | list | `{a, b, layer: ROAD\|SEA_LANE, speed_mult, bridge?: <node id of kind BRIDGE>}`. `length_m` (SIM-CORE §4) is not written: it is the straight line between the endpoints. Ground travel cost is `length_m / speed_mult` (GAMEPLAY §5) |
| `facilities` | list | `{id, kind: UnitKind (a facility kind), variant?, base: <node id>}`: pre-placed facilities; side follows the base (Q-GP-25, TH-10). `start_campaign` places them in file order at their base's position (NX-150 part 2; SIM-CORE §4) |
| `spawns` | list | `{node, domains: [...]}`: where units may appear; usable by whichever side currently owns the node (GAMEPLAY GP-7) |
| `sanctuary` | node id | Coalition SANCTUARY node: infinite stock, never capturable (Q-GD-7) |
| `enemy_rear_source` | node id | The Static's rear source: its SANCTUARY node (`start_owner: ENEMY`), infinite stock, a road to the HQ, never capturable (Q-SIM-48, N-4) |
| `enemy_hq` | node id | Enemy HQ node (Domination victory, GAMEPLAY §9) |
| `forward_airbase` | node id | The coalition AIRBASE the idle floor protects (GAMEPLAY §9, Q-TH-2) |

Node `kind` ∈ `AIRBASE | FOB | PORT | BRIDGE | HQ | SANCTUARY` (SIM-CORE §4); `start_stock` is `null` on the two SANCTUARY nodes and only there; facilities are placed as STATIC units with a `base_id` (Q-GP-25).

### 9.2 Validation rules (load + CI)
| ID | Rule |
|---|---|
| TH-1 | Node `id`s match the CONTRACTS `NodeId` slug `^[a-z0-9]+(-[a-z0-9]+)*$` (≤ 32 chars, no underscores) and are unique. Node `name`s are unique (case-insensitive, confusable-folded) and moderation-clean. NX-120 folds with NFKC + casefold; confusable folding and the moderation check join with the moderation module (CFG-8) |
| TH-2 | Every edge endpoint exists. No self-loops. No duplicate `(a,b,layer)` |
| TH-3 | Every non-SEA node is reachable from `sanctuary` over the ROAD layer when all bridges are intact. PORT nodes must touch ≥1 SEA_LANE. PORT nodes need a road too (NX-120, lead decision). A BRIDGE node sits on an edge rather than ending one, so it counts as reached when an edge carries it (NX-120) |
| TH-4 | Every `bridge` reference points to a node of kind BRIDGE, and that node sits on the edge (within tolerance: PROPOSED 1000 m from the segment, NX-120) |
| TH-5 | Exactly one SANCTUARY per side (`start_owner: COALITION` named by `sanctuary`, `start_owner: ENEMY` named by `enemy_rear_source`, Q-SIM-48) and exactly one HQ (`start_owner: ENEMY`) |
| TH-6 | All positions lie inside `bounds_m`. Every node lies in the sector it names |
| TH-7 | Each side has ≥1 spawn per domain that its MVP units use at its starting nodes |
| TH-11 | A value written `TBD` is rejected at load until the balance harness supplies it (DATA-INTEGRITY DI-7); a sketch may carry TBD in the repo. The loader rejects any string `TBD` anywhere in the file, naming each key path (NX-120; balance files too) |
| TH-8 | If a terrain file is declared, it exists, its dimensions match `bounds_m` at the declared resolution, and its hash is included in the content hash |
| TH-9 | Node count and kind mix are reported, not enforced (design guidance: theater #1 has 12 nodes, 8 strategic bases, Q-TH-1) |
| TH-10 | No facility at a base whose `start_owner` is NEUTRAL (Q-GP-36); `forward_airbase` is a coalition AIRBASE |

### 9.3 Format example (NOT the real map)
> **Illustrative format example only.** This is *not* the first theater. It loads under the current schema and rules (a test keeps it that way, NX-120). The real theater is authored in NX-008 (Q-GD-9). Coordinates and names exist only to show the syntax.
```yaml
schema_version: 1
slug: format-example
name: "Format Example"
version: 0.0.1
bounds_m: { w: 40000, h: 20000 }
terrain: { masking_regions: [] }
sectors:
  - { id: west, name: "West", polygon: [[0,0],[20000,0],[20000,20000],[0,20000]] }
  - { id: east, name: "East", polygon: [[20000,0],[40000,0],[40000,20000],[20000,20000]] }
nodes:
  - { id: base-w,  name: "Example Sanctuary", kind: SANCTUARY, pos: [2000,10000],  start_owner: COALITION, start_stock: null, sector: west }
  - { id: ab-w,    name: "Example Airbase",   kind: AIRBASE,   pos: [8000,10000],  start_owner: COALITION, start_stock: 100,  sector: west }
  - { id: br-mid,  name: "Example Bridge",    kind: BRIDGE,    pos: [20000,10000], start_owner: NEUTRAL,   start_stock: 0,    sector: east }
  - { id: hq-e,    name: "Example HQ",        kind: HQ,        pos: [38000,10000], start_owner: ENEMY,     start_stock: 0,    sector: east }
  - { id: rear-e,  name: "Example Rear",      kind: SANCTUARY, pos: [39000,10000], start_owner: ENEMY,     start_stock: null, sector: east }
facilities: []
edges:
  - { a: base-w, b: ab-w, layer: ROAD, speed_mult: 1.0 }
  - { a: ab-w,   b: hq-e, layer: ROAD, speed_mult: 1.0, bridge: br-mid }
  - { a: hq-e,   b: rear-e, layer: ROAD, speed_mult: 1.0 }
spawns:
  - { node: base-w, domains: [AIR, GROUND] }
  - { node: hq-e,   domains: [AIR, GROUND] }
sanctuary: base-w
enemy_rear_source: rear-e
enemy_hq: hq-e
forward_airbase: ab-w
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
| CFG-5 | Lint: every schema numeric field has an `x-unit` annotation |
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
  - The package fill wait (GAMEPLAY §7) now has a clock (CFG-9) but no row in §6; their keys, values and HR status are added when those features are specified.
  - Weight of Top Commanders in `hud.rotation.panels` (§6.9).
  - The exact maintenance start time and the `overlay.broadcast_tz` value (owner).
