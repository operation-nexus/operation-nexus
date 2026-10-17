# SPEC: Configuration, Balance & Content

Status: Draft · Owner: — · Tracker: NX-106, NX-008, NX-031 · Related ADRs: 0002 (determinism), 0003 (persistence), 0004 (toolchain) · Policy: [DATA-INTEGRITY](../quality/DATA-INTEGRITY.md) DI-7

> **All numeric values in this spec are PROPOSED and unvalidated** (DI-7). They are starting points for the balance harness (NX-031), not tuned values. "TBD by harness" means we have no proposal yet and the harness must produce one before P2.

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
- **CFG-4** Values that affect sim state MUST NOT change mid-campaign except through a logged `AdminCommand(ReloadBalance)` applied at a tick boundary, and only for keys marked hot-reloadable (§5). Replays MUST reproduce the reload.
- **CFG-5** Every balance key MUST carry its unit in the schema (`unit` annotation) and in this spec. All rates are per second of **sim** time unless the unit says otherwise (SIM-CORE SC-2).
- **CFG-6** Content cross-references (unit kinds in theaters, doctrine perks naming unit kinds, template slots) MUST be validated at load and in CI (§8).
- **CFG-7** Secrets MUST NOT appear in any config file. Config refers to secrets by name only (`secret_ref`), and the values come from the environment / secret store (THREAT-MODEL SEC-CI, CICD §8).
- **CFG-8** All user-visible authored text (node names, callsign words, sitrep templates) MUST pass the moderation denylist in CI (SEC-MOD-1).

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
- **`schema_version`:** every file carries an integer `schema_version`. A loader accepts only versions it knows. A schema bump that changes meaning requires a migration script under `tools/config_migrate/` with tests.
- **`content_version`:** a human-facing semver per content file (e.g. a theater's `version: 1.2.0`), shown in the AAR and in replay headers. It is informational only; `config_hash` is what's authoritative.

## 5. Hot-reload rules
| Category | Hot-reloadable mid-campaign? | Why |
|---|---|---|
| Rate limits, reply cadence, sitrep cadence, PiP dwell, reserve-queue cap | **Yes** | Don't change world physics. Needed for incident response (raids) |
| Director budgets and tier thresholds | **Yes**, at the next director window | Operators may need to de-escalate. Logged as a command, so replays match |
| XP table, soft cap | **Yes**, effective for events after the reload tick | Progression is outside the sim kernel |
| Combat pk, weapon profiles, unit stats, logistics rates, capture timings | **No**: new campaign only | Changing physics mid-war breaks fairness and invalidates comparisons |
| Theater, unit catalog, doctrines | **No**: new campaign only | Structural |
| Time scale, tick rate | **No**: new campaign only (tick rate is fixed by ADR-0002) | Determinism |

**Reload procedure (admin):**
1. Upload or select the new profile.
2. Validate it.
3. Diff it against the active profile. If the diff touches any non-hot-reloadable key, the reload is rejected.
4. Enqueue `AdminCommand(ReloadBalance{new_partial_hash, keys})` for tick T+1.
5. The sim applies it at the boundary and emits `BalanceReloaded{keys, old_values, new_values, admin_id}`.
6. The campaign record appends the new effective `config_hash` along with tick T+1.

Every reload is audited (who, when, diff), and is visible in the admin console history.

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
| `slots.respawn_delay_s` | float | s (real) | 20 | GAMEPLAY GP-2 | Yes |
| `slots.max_viewer_units` | int | units | 300 | GAMEPLAY GP-3, Q-GD-6 | Yes |
| `slots.reserve_queue_max` | int | entries | TBD | GAMEPLAY GP-3 | Yes |

### 6.3 Logistics
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `logistics.node_max_stock.<node_kind>` | int | stock units | TBD per kind | GAMEPLAY §5 | No |
| `logistics.factory_rate` | float | stock/min (sim) | TBD | GAMEPLAY §5 | No |
| `logistics.starve_threshold` | float | fraction 0–1 | 0.25 | GAMEPLAY §5 | No |
| `logistics.starved_loadout.fuel_frac` | float | fraction | 0.5 | GAMEPLAY §5 | No |
| `logistics.starved_loadout.secondary_ammo` | int | rounds | 0 | GAMEPLAY §5 | No |
| `logistics.truck_cargo` | int | stock units | TBD | GAMEPLAY §5 | No |
| `logistics.unload_rate` | float | stock/s (sim) | TBD | GAMEPLAY §5 | No |
| `logistics.loadout_cost.<unit_kind>` | int | stock units | TBD per kind | GAMEPLAY §5 | No |
| `logistics.rearm_rate` | float | stock/s (sim) | TBD | GAMEPLAY §5 | No |
| `logistics.stretch.coeff` | float | transit-time multiplier per 100 km from sanctuary | TBD | GAMEPLAY §5 (supply-line stretch) | No |
| `logistics.offroad_speed_mult` | float | multiplier | 0.5 (from raw plans P987; unvalidated) | GAMEPLAY §5 | No |
| `logistics.bridge_repair_time_s` | float | s (sim) | TBD (who repairs it is Q-GD-11) | GAMEPLAY §5 | No |

### 6.4 Combat
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `combat.track_quality.blob` | float | multiplier | 0.2 | GAMEPLAY §6 | No |
| `combat.track_quality.track` | float | multiplier | 1.0 | GAMEPLAY §6 | No |
| `combat.track_quality.painted` | float | multiplier | 1.25 | GAMEPLAY §6 | No |
| `combat.jammer_pk_mult` | float | multiplier | TBD | GAMEPLAY §6 | No |
| `combat.evasion_mult.<alt_band>` | float | multiplier | TBD | GAMEPLAY §6 | No |
| `combat.weapons.<weapon_id>` | object | see §7.2 | TBD | GAMEPLAY §6 | No |

### 6.5 Capture
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `capture.radius_m` | float | m | TBD | GAMEPLAY §8 | No |
| `capture.time_s` | float | s (sim) | 120 | GAMEPLAY §8 | No |
| `capture.multi_unit_exponent` | float | exponent (diminishing returns) | TBD | GAMEPLAY §8 | No |
| `capture.decay_per_s` | float | progress fraction/s | TBD | GAMEPLAY §8 | No |

### 6.6 Campaign
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `campaign.target_duration_h` | float | h (real) | 48 | GAMEPLAY §9, Q-GD-5 | No |
| `campaign.objective_period_min` | float | min (real) | 15 | GAMEPLAY §9 | No |
| `campaign.victory_node_frac` | float | fraction | 0.80 | GAMEPLAY §9 | No |
| `campaign.victory_hold_min` | float | min (real) | 30 | GAMEPLAY §9 | No |
| `campaign.defeat` | object | — | TBD (Q-GD-7) | GAMEPLAY §9 | No |
| `campaign.rubber_band_zone` | [float, float] | fraction of nodes | [0.55, 0.75] | GAMEPLAY §9 | No |
| `campaign.clock_pause_below_humans` | int | humans | 1 | GAMEPLAY §9, Q-GD-4 | No |
| `campaign.night_progress_cap_nodes_per_h` | float | nodes/h (real) | 1/6 | THREAT-DIRECTOR §5, Q-GD-4 | No |
| `campaign.aar_duration_s` | float | s (real) | 300 | GAMEPLAY §9 | Yes |

### 6.7 Threat Director
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `director.window_s` | float | s (sim) | 60 | THREAT-DIRECTOR §4 | No |
| `director.cp.unit_value.<unit_kind>` | float | CP points | TBD per kind | THREAT-DIRECTOR §2 | Yes |
| `director.cp.ema_window_s` | float | s (sim) | 300 | THREAT-DIRECTOR §2 | Yes |
| `director.cp.new_account_weight` | float | multiplier | 0.5 | THREAT-DIRECTOR §2 | Yes |
| `director.cp.new_account_age_h` | float | h (real) | 24 (= Q-PROG-3 recommendation) | THREAT-DIRECTOR §2 | Yes |
| `director.tier.bravo_enter_cp` | float | CP | TBD | THREAT-DIRECTOR §3 | Yes |
| `director.tier.charlie_enter_cp` | float | CP | TBD | THREAT-DIRECTOR §3 | Yes |
| `director.tier.exit_ratio` | float | fraction of enter | 0.8 | THREAT-DIRECTOR §3 | Yes |
| `director.tier.min_dwell_s` | float | s (sim) | 600 | THREAT-DIRECTOR §3 | Yes |
| `director.budget.<tier>` | int | budget points / window | TBD per tier | THREAT-DIRECTOR §4 | Yes |
| `director.memory.half_life_s` | float | s (sim) | 1800 | THREAT-DIRECTOR §2 | Yes |
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
| `progression.min_distinct_humans` | int | humans | 2 | PROGRESSION PROG-2 | Yes |
| `progression.rank_thresholds` | [int] | XP | [0, 300, 1500, 5000, 15000, 40000] | PROGRESSION §3 | No (rank changes are permanent; changing thresholds needs a migration decision) |

### 6.9 Input, audio, presentation
| Key | Type | Unit | PROPOSED | Source | HR |
|---|---|---|---|---|---|
| `ratelimit.per_user.rate_per_s` | float | cmds/s (real) | 0.5 | CHAT-GATEWAY §5 | Yes |
| `ratelimit.per_user.burst` | int | cmds | 3 | CHAT-GATEWAY §5 | Yes |
| `ratelimit.global.cmds_per_tick` | int | cmds/tick | TBD | CHAT-GATEWAY §5 | Yes |
| `replies.twitch_digest_min_s` | float | s (real) | 30 | CHAT-GATEWAY §6 | Yes |
| `replies.youtube_digest_min_s` | float | s (real) | 300 | CHAT-GATEWAY §3 | Yes |
| `audio.sitrep_min_interval_s` | float | s (real) | 20 | AUDIO-TTS AU-1 | Yes |
| `audio.sitrep_max_age_s` | float | s (real) | 60 | AUDIO-TTS AU-1 | Yes |
| `audio.night_mode.hours` | [time, time] | local time | TBD (owner) | AUDIO-TTS AU-2 | Yes |
| `pip.min_dwell_s` | float | s (real) | 3 | OVERLAY OV-6 | Yes |
| `pip.spawn_spotlight_s` | float | s (real) | TBD | OVERLAY OV-6 | Yes |
| `overlay.top_n_labels` | int | labels | TBD | OVERLAY OV-4 | Yes |

## 7. Unit catalog (`content/units.yaml`)

### 7.1 Schema
```yaml
schema_version: 1
units:
  - kind: STRIKE              # enum key, UPPER_SNAKE, unique
    side: COALITION           # COALITION | ENEMY | ANY
    domain: AIR               # AIR | GROUND | SEA | STATIC
    playable_by: VIEWER       # VIEWER | AI_GARRISON | DIRECTOR (one or more)
    min_rank: 1               # PROGRESSION §3; required when playable_by includes VIEWER
    display: { symbol: "air_strike", label_key: "unit.strike" }   # OV-2 shape-coded symbol id
    speed_mps: <float>        # sim m/s
    alt_bands: [LOW, MED]     # AIR only
    hp: <int>
    fuel_s: <float|null>      # endurance in sim s; null = not modeled (STATIC/GROUND for MVP)
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
    base_pk: <float>            # 0..1
    reload_s: <float>
    ammo: <int>
    homes_on_emitters: <bool>   # SEAD behavior
```

### 7.3 MVP unit list (PROPOSED; every stat TBD by harness)
| Kind | Side | Domain | Playable by | Min rank | Armed | Carries | Captures | Notes |
|---|---|---|---|---|---|---|---|---|
| STRIKE | COALITION | AIR | VIEWER, AI_GARRISON | 1 | yes (AG + AA light) | — | no | GAMEPLAY §2 |
| RECON | COALITION | AIR | VIEWER, AI_GARRISON | 1 | no | — | no | Large sensor; paints targets |
| LOGI_TRUCK | COALITION | GROUND | VIEWER, AI_GARRISON | 1 | no | yes | yes (slow) | Road graph only |
| GARRISON_AAA | COALITION | STATIC | AI_GARRISON | — | yes (AA short) | — | no | Node defense; labeled `[AI]` (DI-5) |
| GARRISON_INFANTRY | COALITION | GROUND | AI_GARRISON | — | yes (light) | — | yes | Holds nodes when no viewers (Q-GD-4) |
| ENEMY_SAM_SITE | ENEMY | STATIC | DIRECTOR | — | yes (SAM) | — | no | Engagement ring; may blink radar |
| ENEMY_RADAR | ENEMY | STATIC | DIRECTOR | — | no | — | no | Extends enemy FoW view (FOW-4) |
| ENEMY_CONVOY | ENEMY | GROUND | DIRECTOR | — | no | yes | yes (slow) | Escorts appear via threat memory |
| ENEMY_FIGHTER | ENEMY | AIR | DIRECTOR | — | yes (AA) | — | no | CAP / intercept |
| ENEMY_ARMOR | ENEMY | GROUND | DIRECTOR | — | yes (AG) | — | yes | Offensives / retakes |

Specialist chassis (SEAD, artillery, engineer, jammer, AWACS) and naval units are P4 (PROGRESSION §3, Q-GD-8). Their catalog rows are added then.

## 8. Doctrine catalog (`content/doctrines.yaml`)
```yaml
schema_version: 1
doctrines:
  - id: LOGISTICS_MASTERY
    name_key: doctrine.logistics_mastery
    min_rank: 3
    perks:                         # small, horizontal (PROGRESSION §1)
      - { target_kind: LOGI_TRUCK, stat: cargo, op: mul, value: <float> }
    signature_ability: { id: <ability_id>, cooldown_s: <float>, effect_ref: <effect_id> }
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

Node `kind` ∈ `AIRBASE | FOB | PORT | FACTORY | RADAR | BRIDGE | HQ | SANCTUARY` (SIM-CORE §4).

### 9.2 Validation rules (load + CI)
| ID | Rule |
|---|---|
| TH-1 | Node `id`s match `^[a-z0-9_]{2,32}$` and are unique. Node `name`s are unique (case-insensitive, confusable-folded) and moderation-clean |
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
  - { id: base_w,  name: "Example Sanctuary", kind: SANCTUARY, pos: [2000,10000],  start_owner: COALITION, start_stock: null, sector: west }
  - { id: br_mid,  name: "Example Bridge",    kind: BRIDGE,    pos: [20000,10000], start_owner: NEUTRAL,   start_stock: 0,    sector: east }
  - { id: hq_e,    name: "Example HQ",        kind: HQ,        pos: [38000,10000], start_owner: ENEMY,     start_stock: 0,    sector: east }
edges:
  - { a: base_w, b: hq_e, layer: ROAD, speed_mult: 1.0, bridge: br_mid }
spawns:
  - { side: COALITION, node: base_w, domains: [AIR, GROUND] }
  - { side: ENEMY,     node: hq_e,   domains: [AIR, GROUND] }
sanctuary: base_w
enemy_hq: hq_e
```
`start_stock: null` on the SANCTUARY means "infinite by rule", not unknown. The schema documents this explicitly (CFG-2).

## 10. Text content (`content/text/*.yaml`)

### 10.1 Callsign word list (`callsign_words.yaml`)
- **Format:** words are `^[A-Z]{3,8}$`, e.g. `VIPER`. Generated callsigns are `WORD-NN`, with `NN` in 01–99 (IDENTITY §2).
- **Size:** the list must provide ≥ 2× the expected peak distinct commanders over 90 days of `WORD × NN` combinations. That target is TBD; it depends on real audience data.
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

### 10.3 Localization keys (`strings.<locale>.yaml`)
- Keys are dotted (`unit.strike`, `sitrep.node_captured`, `hud.objective`).
- `en` is the only locale in the MVP. Every key referenced by templates, the catalog or the overlay must exist in `en` (CI check).
- Interpolation uses named slots `{node_name}`, never positional ones.
- Strings are plain text. No HTML or markup is allowed (WP-6, SEC-OV-1).

## 11. Validation & CI
### 11.1 Schema tests
- Every file under `balance/` and `content/` validates against its schema. Unknown keys fail.
- A negative fixture for each schema (missing required key, wrong type, unknown key) proves the loader rejects it.

### 11.2 Cross-reference checks (`tools/config_lint`)
- Unit `weapons` → weapon ids; doctrine perks → unit kinds and whitelisted stats.
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
| CFG-4 | Replay with a mid-campaign HR reload reproduces state hashes; a reload touching a non-HR key is rejected |
| CFG-5 | Lint: every schema numeric field has a `unit` annotation |
| CFG-6 | `config_lint` positive/negative fixtures per cross-reference |
| CFG-7 | Semgrep / secret scan over `balance/`, `content/`, `deploy/*/app.yaml`; schema forbids secret-shaped fields except `secret_ref` |
| CFG-8 | The moderation corpus includes evasion cases; CI fails on a seeded bad node name |
| TH-1…TH-8 | One failing fixture theater per rule |

## 14. Open questions
- Q-GD-5 (campaign length), Q-GD-6 (unit cap), Q-GD-7 (defeat), Q-GD-9 (map), Q-GD-11 (bridge repair), Q-PROG-3 (account age).
- New questions proposed by this spec are listed in the tracker handoff (see PR description).
