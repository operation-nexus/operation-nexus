# SPEC: Data Model & Persistence Formats

Status: Draft · Owner: — · Tracker: NX-200, NX-201, NX-103, NX-204, NX-210 · Related ADRs: 0002, 0003 · Security: THREAT-MODEL SEC-DATA-*, SEC-ID-*

> **All sizes, counts and timings in this spec are PROPOSED or ESTIMATE** (DATA-INTEGRITY DI-7, DOC-2) unless a source is cited. A `NULL` column means **unknown or not applicable**. It never stands in for a value we made up (DI-1).

## 1. Purpose
Define every piece of persisted data: the durable SQLite store, the write path that fills it, the recovery formats (snapshot, command log, crash bundle), how replays stay pseudonymous, and how data is migrated, backed up, retained and deleted.

## 2. Goals / Non-goals
- **Goals**
  - One authoritative home for each fact.
  - Append-only ledgers, so derived data can always be rebuilt.
  - Idempotent writes.
  - GDPR-style deletion without breaking replays.
  - Portable SQL, so moving to Postgres is mechanical (ADR-0003).
- **Non-goals**
  - Live game state in the DB. It lives in memory in the sim (ADR-0003).
  - Analytics warehouse. Analytics are first-party only and derived from our own events (§7a, Q-DM-3).
  - Multi-writer concurrency (deferred to Postgres).

## 3. Requirements
- **DM-1** Exactly one process (`nexus-app`) and one connection (the persistence writer task) write to the durable store. Readers use separate read-only connections.
- **DM-2** Connections MUST set `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout` (value PROPOSED: 5000 ms), and `PRAGMA synchronous=NORMAL` for the writer (WAL makes this durable at checkpoint boundaries; the command log carries the per-second durability guarantee instead, §5.2).
- **DM-3** Ledgers (`xp_ledger`, `merit_ledger`, `identity_events`, `admin_audit`) are append-only. No `UPDATE` or `DELETE`, except the deletion job (§6.4), which redacts personal fields in place and logs that it did.
- **DM-4** Every ledger insert carries an `idempotency_key`, built from the source event id. Re-processing the same event MUST NOT double-count (unique constraint).
- **DM-5** Derived tables (`commander_stats`, leaderboard views) MUST be rebuildable from ledgers alone, and a CI test proves rebuild(ledgers) equals the incrementally maintained values.
- **DM-6** Replays, the command log and snapshots contain `commander_id` (UUIDv7) only. They never contain display names, platform ids or callsign text (SEC-DATA-2).
- **DM-7** Schema changes are forward-only numbered migrations. The app refuses to start if the DB schema is newer than the code knows (no silent downgrade).
- **DM-8** SQL is parameterized only (REVIEW-CHECKLIST, Semgrep `sql-no-fstring`).
- **DM-9** All timestamps are stored as UTC ISO-8601 text (`YYYY-MM-DDTHH:MM:SS.sssZ`). Sim-time references are stored as integer `tick` plus `campaign_id`, never converted to wall time. Recurring owner schedules (maintenance window, night mode) are the one exception: they are stored as local wall-clock times plus an IANA zone and converted at use (Q-CFG-6, Q-CFG-8). Rendering in a viewer's locale or time zone happens in the site and Command Center, never in storage (Q-CFG-8).
- **DM-10** No column has a made-up default. `DEFAULT` is used only for values that are true by construction (e.g., `0` for a counter that starts at zero, `CURRENT_TIMESTAMP`-equivalent set by the writer).
- **DM-11** The overlay and the site load no third-party tracker, analytics script or analytics cookie. Product analytics are derived only from our own sim and gateway events (§7a, Q-DM-3).

## 4. Durable store (SQLite DDL)

Conventions:
- **IDs:** `TEXT` UUIDv7 for entities created by the app. Platform ids stay `TEXT` exactly as the platform sends them.
- **Enums:** `TEXT` with `CHECK (col IN (...))`. The enum values are generated from `/contracts` so they match the wire types.
- **Booleans:** `INTEGER CHECK (col IN (0,1))`.
- **Table mode:** tables use `STRICT` (SQLite ≥ 3.37) to stop silent type coercion. Postgres doesn't need it (§4.17).

### 4.1 schema_migrations
```sql
CREATE TABLE schema_migrations (
  version      INTEGER PRIMARY KEY,           -- 0001, 0002, ...
  name         TEXT    NOT NULL,
  checksum     TEXT    NOT NULL,              -- sha256 of the migration file
  applied_at   TEXT    NOT NULL
) STRICT;
```

### 4.2 commanders
```sql
CREATE TABLE commanders (
  commander_id      TEXT PRIMARY KEY,                          -- UUIDv7
  callsign          TEXT NOT NULL UNIQUE,                      -- generated (FB-1), approved custom, or tombstone
  callsign_kind     TEXT NOT NULL CHECK (callsign_kind IN ('GENERATED','CUSTOM','TOMBSTONE')),
  callsign_set_at   TEXT NOT NULL,
  created_at        TEXT NOT NULL,
  first_mission_at  TEXT,                                      -- NULL until first completed sortie (first-mission XP gate, Q-PROG-6)
  banned            INTEGER NOT NULL DEFAULT 0 CHECK (banned IN (0,1)),
  deletion_requested_at TEXT,                                  -- set when !forget / portal request is received
  deleted_at        TEXT,                                      -- set by the deletion job on completion; row kept as tombstone
  taunt_opt_out     INTEGER NOT NULL DEFAULT 0 CHECK (taunt_opt_out IN (0,1)),  -- `!quiet` toggle (Q-ALN-12); 0 = never opted out
  CHECK ((callsign_kind = 'TOMBSTONE') = (deleted_at IS NOT NULL)),
  CHECK (deleted_at IS NULL OR deletion_requested_at IS NOT NULL)
) STRICT;
CREATE INDEX idx_commanders_created ON commanders(created_at);
```
- XP and rank are **not** stored here. They're derived (§4.10), so they can't drift from the ledger.
- **Tombstone callsign:** `"X-"` followed by the first 10 characters of the RFC 4648 base32 (uppercase, no padding) encoding of `blake2b-256(commander_id)`. That is 12 characters, so it matches the CONTRACTS `Callsign` regex, and it is derived from the id, so it is unique in practice. On a collision (UNIQUE violation) the deletion transaction rolls back and alerts; the job then retries with the next 10 characters. The `X-` prefix is reserved and can't be claimed as a custom callsign (IDENTITY §3).
- Viewers never see the tombstone value: anything with `callsign_kind = 'TOMBSTONE'` renders as `REDACTED-…` (Q-DM-2). What follows the `REDACTED-` prefix is not decided (§11).
- **`taunt_opt_out` (Q-ALN-12, IDENTITY ID-PREF-1):** each `!quiet` flips the flag and the bot confirms the new state. Any rank may use it. It lives on the commander, so it applies on every linked platform. While it is 1, Static taunts never name this commander. The `0` default is true by construction (DM-10): a new commander has not opted out. How the flag combines on a merge (Q-PROG-4) is not decided (§11).

### 4.3 platform_identities
```sql
CREATE TABLE platform_identities (
  platform           TEXT NOT NULL CHECK (platform IN ('TWITCH','YOUTUBE','KICK','DISCORD','LOCAL_SIM')),
  platform_user_id   TEXT NOT NULL,
  commander_id       TEXT NOT NULL REFERENCES commanders(commander_id),
  display_name       TEXT,                     -- last seen; NULL if never received; never rendered unmoderated
  platform_account_created_at TEXT,            -- from ChatEnvelope.account_created_at; NULL when the platform doesn't provide it, never guessed
  linked_via         TEXT NOT NULL CHECK (linked_via IN ('LAZY_CREATE','OAUTH_LINK','MERGE')),
  first_seen_at      TEXT NOT NULL,
  last_seen_at       TEXT NOT NULL,
  PRIMARY KEY (platform, platform_user_id)
) STRICT;
CREATE INDEX idx_identities_commander ON platform_identities(commander_id);
```
- `platform_account_created_at` is the platform-account-age anti-farming layer (PROGRESSION PROG-4, IDENTITY §1) and feeds the account-age weighting (THREAT-DIRECTOR §2, `director.cp.new_account_age_h`). It is copied from `ChatEnvelope.account_created_at` (CONTRACTS §4) and stays `NULL` when the platform doesn't expose it [UNVERIFIED per platform]. `first_seen_at` is our own first-seen age.
- `KICK` is in the CHECK list only because the `Platform` enum carries it: Kick is an optional platform, not a committed one (Q-PROD-2).
- `LOCAL_SIM` rows exist only in dev/test databases. Production config that enables the `LOCAL_SIM` adapter is rejected at startup (CONTRACTS §3.3).
- Re-pointing an existing `(platform, platform_user_id)` to another commander is only allowed inside the OAuth merge transaction (SEC-ID-2). There is no `INSERT OR REPLACE` anywhere (Semgrep rule, NX-020).

### 4.4 identity_events (audit, append-only)
```sql
CREATE TABLE identity_events (
  event_id          TEXT PRIMARY KEY,          -- UUIDv7
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  kind              TEXT NOT NULL CHECK (kind IN
                    ('CREATED','LINKED','UNLINKED','MERGED_INTO','MERGED_FROM',
                     'CALLSIGN_CHANGED','BANNED','UNBANNED','FORGET_REQUESTED','FORGOTTEN')),
  platform          TEXT CHECK (platform IN ('TWITCH','YOUTUBE','KICK','DISCORD','LOCAL_SIM')),   -- NULL when not platform-specific
  other_commander_id TEXT,                     -- merge counterpart; NULL otherwise
  actor             TEXT NOT NULL CHECK (actor IN ('SYSTEM','OWNER','PLATFORM_MOD','USER')),
  detail_json       TEXT,                      -- structured, no free-text user strings
  occurred_at       TEXT NOT NULL
) STRICT;
CREATE INDEX idx_identity_events_commander ON identity_events(commander_id, occurred_at);
```

### 4.5 callsign_requests (moderation queue)
```sql
CREATE TABLE callsign_requests (
  request_id        TEXT PRIMARY KEY,
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  requested         TEXT NOT NULL CHECK (length(requested) BETWEEN 3 AND 12),
  normalized_key    TEXT NOT NULL,             -- NFKC + confusable-folded, for collision checks
  status            TEXT NOT NULL CHECK (status IN ('PENDING','AUTO_REJECTED','APPROVED','REJECTED','EXPIRED')),
  reject_reason     TEXT CHECK (reject_reason IN ('FORMAT','DENYLIST','CLASSIFIER','TAKEN','RESERVED','OWNER','RATE_LIMIT')),
  decided_by        TEXT CHECK (decided_by IN ('AUTO','OWNER','PLATFORM_MOD')),
  requested_at      TEXT NOT NULL,
  decided_at        TEXT,
  CHECK ((status = 'PENDING') = (decided_at IS NULL))
) STRICT;
CREATE INDEX idx_callsign_requests_status ON callsign_requests(status, requested_at);
CREATE UNIQUE INDEX uq_callsign_pending ON callsign_requests(commander_id) WHERE status = 'PENDING';
```

### 4.6 bans
```sql
CREATE TABLE bans (
  ban_id            TEXT PRIMARY KEY,
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  source            TEXT NOT NULL CHECK (source IN ('PLATFORM_SYNC','OWNER','AUTO_RATE')),
  source_platform   TEXT CHECK (source_platform IN ('TWITCH','YOUTUBE','KICK','DISCORD','LOCAL_SIM')),
  reason_code       TEXT NOT NULL CHECK (reason_code IN ('HARASSMENT','SLUR','SPAM','BOT','OTHER')),
  starts_at         TEXT NOT NULL,
  ends_at           TEXT,                      -- NULL = permanent
  lifted_at         TEXT,
  lifted_by         TEXT CHECK (lifted_by IN ('OWNER','PLATFORM_SYNC'))
) STRICT;
CREATE INDEX idx_bans_active ON bans(commander_id) WHERE lifted_at IS NULL;
```
- `commanders.banned` is a cached flag maintained in the same transaction as each ban or lift. It's rebuildable from `bans`.

### 4.7 config_versions (config hash registry)
```sql
CREATE TABLE config_versions (
  config_hash       TEXT PRIMARY KEY,          -- combined hash over balance + units + doctrines + theater + text (CONFIG-AND-CONTENT §4.4)
  schema_version    INTEGER NOT NULL,
  manifest_json     TEXT NOT NULL,             -- [{"path","kind","sha256"}] for every contributing file
  git_commit        TEXT,                      -- NULL if loaded from an uncommitted file (dev only)
  validated         INTEGER NOT NULL CHECK (validated IN (0,1)),  -- 1 = passed balance-harness gate
  content_zstd      BLOB NOT NULL,             -- all contributing files, so replays and crash bundles never depend on git
  registered_at     TEXT NOT NULL
) STRICT;
```

### 4.8 campaigns
```sql
CREATE TABLE campaigns (
  campaign_id       TEXT PRIMARY KEY,
  seed              INTEGER NOT NULL,          -- SimRng root seed (ADR-0002)
  config_hash       TEXT NOT NULL REFERENCES config_versions(config_hash),   -- config at start; later reloads in campaign_config_history
  theater_id        TEXT NOT NULL,
  mode              TEXT NOT NULL CHECK (mode IN ('TOTAL_DOMINATION','HOLD_THE_LINE','SIEGE')),
  sim_build         TEXT NOT NULL,             -- app version/digest that started it
  started_at        TEXT NOT NULL,
  start_tick        INTEGER NOT NULL CHECK (start_tick >= 0),
  ended_at          TEXT,
  end_tick          INTEGER,
  outcome           TEXT CHECK (outcome IN ('VICTORY','DEFEAT','TIME_LIMIT','ABORTED')),
  final_score_json  TEXT,                      -- structured; NULL while running
  CHECK ((ended_at IS NULL) = (outcome IS NULL))
) STRICT;
CREATE UNIQUE INDEX uq_one_running_campaign ON campaigns((1)) WHERE ended_at IS NULL;

CREATE TABLE campaign_config_history (
  campaign_id       TEXT NOT NULL REFERENCES campaigns(campaign_id),
  effective_tick    INTEGER NOT NULL CHECK (effective_tick >= 0),
  config_hash       TEXT NOT NULL REFERENCES config_versions(config_hash),
  arrival_seq       INTEGER,                   -- the OP_CONFIG_RELOAD command; NULL for the campaign's starting row
  PRIMARY KEY (campaign_id, effective_tick)
) STRICT;
```
- Every campaign gets a starting row (`effective_tick = start_tick`). Each hot reload (`OP_CONFIG_RELOAD` → `BalanceReloaded`) appends one row. Replays and crash bundles use this history to load the right config at each tick.

### 4.9 campaign_participation
```sql
CREATE TABLE campaign_participation (
  campaign_id       TEXT NOT NULL REFERENCES campaigns(campaign_id),
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  doctrine          TEXT CHECK (doctrine IN ('AIR_SUPERIORITY','LOGISTICS_MASTERY','RECON_EW','GARRISON_COMMAND')),
  doctrine_set_tick INTEGER,                   -- NULL until chosen; locked once set (Q-GD-3)
  first_seen_tick   INTEGER NOT NULL,
  last_seen_tick    INTEGER NOT NULL,
  sorties           INTEGER NOT NULL DEFAULT 0 CHECK (sorties >= 0),
  PRIMARY KEY (campaign_id, commander_id)
) STRICT;
```
- The doctrine lock is enforced in code and by a trigger: `doctrine` can go from NULL to a value only once per campaign.

### 4.10 xp_ledger (append-only)
```sql
CREATE TABLE xp_ledger (
  entry_id          TEXT PRIMARY KEY,
  idempotency_key   TEXT NOT NULL UNIQUE,      -- "<campaign_id>:<source_event_seq>:<commander_id>:<reason>"
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  campaign_id       TEXT NOT NULL REFERENCES campaigns(campaign_id),
  source_tick       INTEGER NOT NULL,
  source_event_seq  INTEGER NOT NULL,          -- sim event sequence number
  reason            TEXT NOT NULL CHECK (reason IN
                    ('SORTIE_COMPLETE','SUPPLY_DELIVERED','CAPTURE','OBJECTIVE','RECON_ASSIST','KILL','ADMIN_ADJUST')),
  base_xp           INTEGER NOT NULL CHECK (base_xp >= 0),
  multiplier_milli  INTEGER NOT NULL CHECK (multiplier_milli > 0 AND multiplier_milli <= 4000), -- 1000 = 1.0x; DR and package share applied. Upper bound PROPOSED; must cover the package XP-share bonus (GAMEPLAY §7)
  awarded_xp        INTEGER NOT NULL CHECK (awarded_xp >= 0),
  persistent        INTEGER NOT NULL CHECK (persistent IN (0,1)),  -- 0 when the first-mission gate blocks persistence (§5.3)
  config_hash       TEXT NOT NULL REFERENCES config_versions(config_hash),
  recorded_at       TEXT NOT NULL,
  CHECK (awarded_xp = (base_xp * multiplier_milli) / 1000)
) STRICT;
CREATE INDEX idx_xp_commander ON xp_ledger(commander_id, recorded_at);
CREATE INDEX idx_xp_campaign ON xp_ledger(campaign_id, commander_id);
```
- Integer milli-multipliers avoid float drift between SQLite and Postgres, and make rebuilds exact.
- `ADMIN_ADJUST` rows also require a matching `admin_audit` row (checked in a test).

### 4.11 merit_ledger (append-only, per campaign)
```sql
CREATE TABLE merit_ledger (
  entry_id          TEXT PRIMARY KEY,
  idempotency_key   TEXT NOT NULL UNIQUE,
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  campaign_id       TEXT NOT NULL REFERENCES campaigns(campaign_id),
  source_tick       INTEGER NOT NULL,
  source_event_seq  INTEGER NOT NULL,
  reason            TEXT NOT NULL CHECK (reason IN
                    ('SORTIE_COMPLETE','SUPPLY_DELIVERED','CAPTURE','OBJECTIVE','RECON_ASSIST','KILL','ADMIN_ADJUST')),
  delta             INTEGER NOT NULL CHECK (delta >= 0),   -- merit is a score only, never spent (Q-PROG-7, ADR-0011)
  recorded_at       TEXT NOT NULL
) STRICT;
CREATE INDEX idx_merit_campaign ON merit_ledger(campaign_id, commander_id);
```

### 4.12 commander_stats (derived; rebuildable)
```sql
CREATE TABLE commander_stats (
  commander_id         TEXT PRIMARY KEY REFERENCES commanders(commander_id),
  xp_total             INTEGER NOT NULL CHECK (xp_total >= 0),   -- SUM(awarded_xp) WHERE persistent=1
  rank_level           INTEGER NOT NULL CHECK (rank_level BETWEEN 1 AND 6),
  kills                INTEGER NOT NULL CHECK (kills >= 0),
  supply_delivered     INTEGER NOT NULL CHECK (supply_delivered >= 0),
  captures             INTEGER NOT NULL CHECK (captures >= 0),
  objectives           INTEGER NOT NULL CHECK (objectives >= 0),
  campaigns_played     INTEGER NOT NULL CHECK (campaigns_played >= 0),
  campaigns_won        INTEGER NOT NULL CHECK (campaigns_won >= 0),
  rebuilt_from_entry   TEXT,                   -- last ledger entry_id folded in
  updated_at           TEXT NOT NULL
) STRICT;
```
- `rank_level` is derived, never edited by hand, and **never decreases** (Q-CFG-2). It is the highest level reached when each persistent `xp_ledger` row is folded in order under the rank table of that row's `config_hash`. A new rank table (an admin preset, Q-PROG-7) therefore applies to future promotions only.
- Rank tables and XP source values are config (CONFIG-AND-CONTENT §6.8). Applying an admin/GM preset registers a new `config_versions` row and writes an `admin_audit` row (Q-PROG-7).
- **Merge (Q-PROG-4):** XP is never summed. The surviving commander keeps the max per stat. The absorbed commander's ledger rows stay attached to the absorbed id (they're history), and an identity_event `MERGED_INTO` links the two. The derived stats for the survivor take `max(survivor, absorbed)` per column at merge time; that rule is recorded as a `MERGED_FROM` event so rebuilds can reproduce it.

### 4.13 Leaderboard views
```sql
CREATE VIEW v_campaign_leaderboard AS
SELECT m.campaign_id, m.commander_id, c.callsign,
       SUM(CASE WHEN m.delta > 0 THEN m.delta ELSE 0 END) AS merit_earned
FROM merit_ledger m
JOIN commanders c ON c.commander_id = m.commander_id
WHERE c.deleted_at IS NULL AND c.banned = 0
GROUP BY m.campaign_id, m.commander_id, c.callsign;

CREATE VIEW v_role_leaderboard AS
SELECT x.campaign_id, x.commander_id, x.reason, SUM(x.awarded_xp) AS xp
FROM xp_ledger x
JOIN commanders c ON c.commander_id = x.commander_id
WHERE c.deleted_at IS NULL AND c.banned = 0
GROUP BY x.campaign_id, x.commander_id, x.reason;
```
- **Interim:** `v_role_leaderboard` groups XP by reason. Q-PROG-8 replaces that ranking: per-role boards rank by role contribution (logistics: supplies delivered; recon: spotted enemies later engaged by friendlies; CSAR: rescues completed; combat: threat-weighted kills + objective damage), the overall board ranks by merit, assists count, and each board has a season-total (primary) and a per-hour-played view. The metric per board is defined in config. **Season and per-role leaderboard source tables (the recon, CSAR and threat-weighted metrics, the season key and hours played) are specified in the seasons and leaderboards spec (NX-314), not here (Q-ALN-16).** When that spec lands, its tables are added to §4 in the same PR as their migration. CSAR rescue counts can already be derived from §4.13a.
- Only approved callsigns appear, because `commanders.callsign` is always either generated or approved. Banned and deleted commanders are excluded. No padding rows (DI-4).

### 4.13a Tasking Board job outcomes (Q-ALN-16, GAMEPLAY TB-10)
Durable, because recap stats (e.g. "most rescues") and balance analysis read them across campaigns. Insert-only: one `tasking_jobs` row when a job reaches a terminal state, plus one `tasking_job_claims` row per claim it had. Built from the Tasking Board sim events (CONTRACTS: `JobPosted`, `JobClaimed`, `JobReleased`, `JobExpired`, and the DONE/FAILED outcome events, whose names CONTRACTS does not list yet).
```sql
CREATE TABLE tasking_jobs (
  campaign_id       TEXT NOT NULL REFERENCES campaigns(campaign_id),
  job_id            TEXT NOT NULL,             -- TaskingJobId (CONTRACTS)
  side              TEXT NOT NULL CHECK (side IN ('COALITION','ENEMY')),   -- whose board (ENEMY = the Static's)
  job_kind          TEXT NOT NULL,             -- enum from contracts (GAMEPLAY §1b job types)
  gm_injected       INTEGER NOT NULL CHECK (gm_injected IN (0,1)),         -- injected by a human GM (TB-11)
  posted_tick       INTEGER NOT NULL CHECK (posted_tick >= 0),
  resolved_tick     INTEGER NOT NULL,
  outcome           TEXT NOT NULL CHECK (outcome IN ('DONE','FAILED','EXPIRED')),   -- TB-1 terminal states
  config_hash       TEXT NOT NULL REFERENCES config_versions(config_hash),
  recorded_at       TEXT NOT NULL,
  PRIMARY KEY (campaign_id, job_id),
  CHECK (resolved_tick >= posted_tick),
  CHECK (gm_injected = 0 OR side = 'ENEMY')     -- a GM injects only into the Static's board (Q-ALN-11)
) STRICT;
CREATE INDEX idx_tasking_jobs_kind ON tasking_jobs(campaign_id, job_kind, outcome);

CREATE TABLE tasking_job_claims (
  campaign_id       TEXT NOT NULL,
  job_id            TEXT NOT NULL,
  claim_seq         INTEGER NOT NULL CHECK (claim_seq >= 0),  -- order of claims on this job
  entity_id         TEXT NOT NULL,             -- the claiming unit
  commander_id      TEXT REFERENCES commanders(commander_id),  -- NULL for AI garrison and Static units
  ai_run            INTEGER NOT NULL CHECK (ai_run IN (0,1)),  -- 1 when the unit was AI-run (AUTO tag, Q-GD-35) at claim time
  claimed_tick      INTEGER NOT NULL,
  ended_tick        INTEGER NOT NULL CHECK (ended_tick >= claimed_tick),
  ended_by          TEXT NOT NULL CHECK (ended_by IN ('RESOLVED','RELEASED')),   -- job reached a terminal state, or the claim was released (lease, preemption, operator)
  PRIMARY KEY (campaign_id, job_id, claim_seq),
  FOREIGN KEY (campaign_id, job_id) REFERENCES tasking_jobs(campaign_id, job_id)
) STRICT;
CREATE INDEX idx_tasking_claims_commander ON tasking_job_claims(commander_id) WHERE commander_id IS NOT NULL;
```
- Both tables hold ids and numbers only (DM-6), so the deletion job keeps them, like the ledgers (§6.4).
- Writes are idempotent: a replayed outcome hits the primary key and is ignored (`ON CONFLICT DO NOTHING`, §5.2).
- Whether a job credited to an AI-run (`ai_run = 1`) viewer unit counts toward its commander's recap stats is not decided (§11).

### 4.14 clips (review queue)
```sql
CREATE TABLE clips (
  clip_id           TEXT PRIMARY KEY,
  campaign_id       TEXT NOT NULL REFERENCES campaigns(campaign_id),
  start_tick        INTEGER NOT NULL,
  end_tick          INTEGER NOT NULL CHECK (end_tick > start_tick),
  excitement_score  INTEGER NOT NULL,
  status            TEXT NOT NULL CHECK (status IN ('QUEUED','RENDERING','READY','APPROVED','REJECTED','FAILED','PURGED')),
  file_path         TEXT,                      -- generated name under the clips dir; NULL until rendered
  fail_reason       TEXT,
  reviewed_by       TEXT CHECK (reviewed_by IN ('OWNER')),
  created_at        TEXT NOT NULL,
  reviewed_at       TEXT
) STRICT;
CREATE INDEX idx_clips_status ON clips(status, created_at);

CREATE TABLE clip_participants (
  clip_id           TEXT NOT NULL REFERENCES clips(clip_id),
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  PRIMARY KEY (clip_id, commander_id)
) STRICT;
CREATE INDEX idx_clip_participants_commander ON clip_participants(commander_id);
```
- Participants are recorded when the clip job is created, from the events in the clip window (commanders whose units appear). The deletion job uses this table (§6.4).

### 4.15 admin_audit (append-only)
```sql
CREATE TABLE admin_audit (
  audit_id          TEXT PRIMARY KEY,
  actor             TEXT NOT NULL CHECK (actor IN ('OWNER','SYSTEM')),
  action            TEXT NOT NULL,             -- enum from contracts (KILL_SWITCH, PAUSE, BAN, CONFIG_RELOAD, ...)
  target_kind       TEXT,
  target_id         TEXT,
  arrival_seq       INTEGER,                   -- command-log arrival_seq if the action entered the sim
  detail_json       TEXT,
  occurred_at       TEXT NOT NULL
) STRICT;
CREATE INDEX idx_admin_audit_time ON admin_audit(occurred_at);
```

### 4.16 deletion_requests
```sql
CREATE TABLE deletion_requests (
  request_id        TEXT PRIMARY KEY,
  commander_id      TEXT NOT NULL REFERENCES commanders(commander_id),
  channel           TEXT NOT NULL CHECK (channel IN ('CHAT_FORGET','PORTAL','OWNER')),
  status            TEXT NOT NULL CHECK (status IN ('RECEIVED','PROCESSING','DONE','FAILED')),
  requested_at      TEXT NOT NULL,
  due_by            TEXT NOT NULL,             -- requested_at + 30 days (SEC-DATA-3)
  completed_at      TEXT,
  fail_reason       TEXT
) STRICT;
CREATE INDEX idx_deletion_due ON deletion_requests(status, due_by);
```

### 4.17 Postgres portability notes
| SQLite feature | Postgres equivalent | Action at migration |
|---|---|---|
| `STRICT` tables | native typing | Drop the keyword |
| `TEXT` timestamps | `timestamptz` | Cast in migration; repository layer already speaks ISO-8601 |
| `INTEGER` booleans | `boolean` | Cast; keep CHECKs as documentation |
| `BLOB` | `bytea` | Direct |
| Partial indexes (`WHERE`) | supported | Direct |
| `uq_one_running_campaign` on `((1))` | partial unique index on a constant expression works in Postgres too | Verify in the migration test |
| Single writer | MVCC multi-writer | Keep idempotency keys; they become the concurrency guard |
| Triggers (doctrine lock) | PL/pgSQL triggers | Rewrite trigger bodies; behavior covered by the same tests |

The repository interface (`nexus.persistence`) is the only code that sees SQL. The same repository test suite runs against both engines before the switch.

## 5. Write path

### 5.1 Single writer task
- The sim publishes events to the in-process bus. `progression`, `identity` and `ops` map events into **write intents** (`AppendXp`, `AppendMerit`, `CreateCommander`, `RecordBan`, …) and put them on a bounded queue (size PROPOSED: 10,000).
- The writer task drains the queue in batches (PROPOSED: up to 500 intents or 250 ms, whichever first) and runs **one transaction per batch**.
- If the queue is full, intents are **not dropped silently**. The writer raises `persistence_backpressure`, alerts, and the sim keeps running (SYSTEM-DESIGN §8). Intents stay in memory up to the cap. Beyond the cap, the oldest *derived* intents are dropped (they're rebuildable), while ledger intents block the publisher for at most a bounded time and then the event is written to a spill file that is replayed on recovery.

### 5.2 Idempotency
- Every ledger intent carries its `idempotency_key`. Inserts use `INSERT ... ON CONFLICT(idempotency_key) DO NOTHING` (portable to Postgres).
- On restart, the runtime replays the command log from the last snapshot. The resulting events produce the same keys, so duplicates are ignored and gaps are filled.

### 5.3 XP diminishing returns (PROG-1) and the first-mission gate
For each `AppendXp(commander, reason, base_xp, source_tick)`:
1. Look up the commander's awarded XP within the trailing **60 minutes of wall-clock time**, using `recorded_at`. `progression.xp_hour_soft_cap` is defined per real hour (CONFIG-AND-CONTENT §6.8). `recorded_at` is stamped by the runtime when it persists the event. Progression runs outside the deterministic kernel, so this doesn't affect sim determinism. Replaying the command log after a crash doesn't re-award XP, because the idempotency keys dedupe (§5.2).
2. If over `progression.xp_hour_soft_cap`, `multiplier_milli = round(progression.xp_over_cap_mult × 1000)`; otherwise 1000. A package XP-share bonus (GAMEPLAY §7) multiplies on top; the result must stay within the column CHECK.
3. `persistent = 1` only if `commanders.first_mission_at IS NOT NULL`. There is no minimum-humans gate: the PROG-2 "<2 humans" rule is dropped (Q-PROG-6), so a lone operator earns persistent XP. Anti-farming relies on this gate, the hourly diminishing returns above and the NX-277 layers.
4. Insert the ledger row. If `persistent = 1`, update `commander_stats` in the same transaction (ADR-0003 amendment: the ledger is the source of truth).

### 5.4 Rebuild derived tables
`tools/db rebuild-stats` truncates `commander_stats`, folds `xp_ledger` (persistent rows), `merit_ledger`, `campaign_participation` and the merge events in order, then compares the result with a pre-rebuild copy. CI runs it on a fixture DB (DM-5). It's also run after any config change that alters the rank table.

## 6. Recovery data formats

### 6.1 Snapshot file
- **Path:** `snapshots/<campaign_id>/<tick:012d>.nxs`. Written atomically: write to `.tmp`, fsync, rename, fsync the directory.
- **Layout:**
  ```
  magic      8 bytes   "NXSNAP\0\1"
  header_len u32 LE
  header     msgpack map:
               format_version   int
               schema_version   int      (world-model schema in /contracts)
               campaign_id      str
               seed             int
               config_hash      str
               sim_build        str
               tick             int
               state_hash       str      (blake2b, SIM-CORE §5)
               last_arrival_seq int
               created_at       str      (UTC, informational only; not used by the sim)
  body       zstd(msgpack(canonical world state))
  trailer    blake2b-256 of header+body
  ```
- **Load:** verify the trailer, then decompress, rebuild state, recompute `state_hash` and compare with the header. Any mismatch → try the previous snapshot and raise an alert. Never load a partially verified snapshot.
- **Retention:** the last 20, plus one per hour of game time (CONFIG-AND-CONTENT CFG-9), plus the final snapshot of each campaign (all PROPOSED).

### 6.2 Command log
- **Path:** `command-logs/<campaign_id>/<segment:06d>.nxl.zst`
- **Format:** newline-delimited JSON records, written through a streaming zstd frame. Each segment is a sequence of independent zstd frames, one per flush, so a crash loses at most the last unflushed frame.
- **Record:**
  ```json
  {"arrival_seq": 1234567, "target_tick": 88210, "kind": "JOIN",
   "source": "CHAT", "platform": "TWITCH",
   "commander_id": "0192…", "args": {"role": "LOGI"}, "late": false}
  ```
  - `source` is a `CommandSource` (`CHAT|OPERATOR|ADVISOR|SYSTEM`, CONTRACTS §3.3). `platform` is set only for `CHAT` commands and is `null` otherwise. No vendor field names (ADR-0010 N-6).
  - `commander_id` only; no names (DM-6).
  - Advisor choices and admin actions are commands too (ADR-0002).
- **Flush and fsync:** every 1 s (NFR-7), and on campaign end and shutdown.
- **Rotation:** a new segment when one passes 64 MiB uncompressed (PROPOSED) or at each snapshot boundary. Segment names are monotonic.
- **Integrity:** every segment's first record carries a header (`format_version`, `campaign_id`, `first_arrival_seq`). The replay CLI rejects gaps in `arrival_seq`.

### 6.3 Crash bundle
Written on a `step` exception (SC-8) to `crash-bundles/<utc>-<campaign_id>-<tick>/`:
- `manifest.json`: build, campaign, seed, config hash, tick, exception type and traceback, last state_hash
- the last verified snapshot (copied, not linked)
- the command-log tail from that snapshot's `last_arrival_seq` to the crash tick
- the config content for every `config_hash` in the campaign's `campaign_config_history` (from `config_versions.content_zstd`)
- recent structured logs (secret-redacted, NX-026)

Bundles contain `commander_id`s only, so they're safe to attach to a private GitHub issue. Never attach them to a public one without owner review.

### 6.4 Pseudonymization & deletion (SEC-DATA-2/3)
| Data | Where | Contains names? |
|---|---|---|
| Snapshots, command logs, crash bundles, replays | files | **No**: `commander_id` only |
| `commanders.callsign`, `platform_identities.display_name` | SQLite | Yes (the only place) |
| Uploaded clips | platforms | Possibly (on-screen callsigns). Can't be recalled after upload (THREAT-MODEL §6) |

**Crypto-shredding:** the public replay viewer resolves `commander_id → callsign` through a `GET` against the live DB at view time. After deletion, `callsign_kind = 'TOMBSTONE'`, so old replays render `REDACTED-…` automatically (Q-DM-2). Replay files need no rewriting.

**Deletion job** (daily, processes `deletion_requests` where `status='RECEIVED'`):
1. Mark `PROCESSING`. (`commanders.deletion_requested_at` was already set when the request was received, together with the `deletion_requests` row.)
2. In one transaction:
   - delete `platform_identities` rows
   - set `commanders.callsign` to the tombstone value (§4.2), `callsign_kind = 'TOMBSTONE'`, `deleted_at = now`
   - delete `callsign_requests` rows
   - null out `display_name` in any remaining audit detail
   - append `FORGOTTEN` to `identity_events`
3. Keep ledgers (they hold only ids and numbers). Exclude the commander from leaderboards via `deleted_at`.
4. Purge any `clips` in `READY` or `QUEUED` that show the commander (via `clip_participants`) → `PURGED`.
5. Mark `DONE`. If not done by `due_by`, alert the owner.

### 6.5 Retention schedule (from SEC-DATA-4; durations PROPOSED, Q-LEGAL-3)
| Data | Kept | Then |
|---|---|---|
| Raw `ChatEnvelope`s (in logs) | 7 days | Deleted by log rotation |
| Command logs and snapshots | Campaign duration + 30 days | Deleted, except the final snapshot plus logs needed for the public replay (ids only) |
| Crash bundles | 30 days | Deleted |
| Ledgers, campaigns, stats, Tasking Board outcomes (§4.13a) | Indefinitely (ids and numbers only) | — |
| `identity_events`, `admin_audit` | Indefinitely (no free text) | — |
| Rejected or expired `callsign_requests` | 90 days | Deleted |
| Rejected clips (files) | 7 days | File deleted, row → `PURGED` |

## 7. Migrations, backups, integrity
- **Migrations** live in `services/sim/nexus/persistence/migrations/NNNN_name.sql`. They're forward-only, and each is applied in its own transaction with its checksum recorded. Editing an applied migration fails startup (checksum mismatch).
- **CI migration test:** start from a **fixture DB built at the previous release's schema**, synthetic data only (DATA-INTEGRITY DI-3), apply new migrations, then run the repository test suite plus `rebuild-stats` equality. A sanitized copy of production is **not** used in CI (PII); the fixture generator mirrors production row counts instead.
- **Backups:**
  - Nightly `sqlite3 .backup` (online, consistent) plus a tarball of the latest snapshot and command-log segments.
  - Encrypted with `age` to the owner's public key, then copied to the Linux server (local copy) and to an off-site target through the `BackupTarget` port (ADR-0010), so providers are swappable. **Q-OPS-6 (decided 2026-10-17):** the first off-site target is the owner's **Google Drive**; other free or cheap providers may be added. Provider limits and pricing are [UNVERIFIED] and are checked before setup (NX-285).
  - **Tiering (Q-OPS-6):** the DB and snapshots back up nightly; large replay/telemetry archives are compressed and kept with their own retention.
- **Restore test:** quarterly (SEC-DATA-5), plus after any migration. Restore into a scratch dir, run `PRAGMA integrity_check`, rebuild stats, then load the latest snapshot and replay its log to the recorded `state_hash`.
- **Integrity checks:** `PRAGMA quick_check` daily, `PRAGMA integrity_check` weekly and before each backup upload, and `PRAGMA foreign_key_check` weekly. Any failure alerts the owner and blocks the backup from overwriting the last good copy.

## 7a. Public exports and first-party analytics
- **Public site exports (Q-ARCH-16):** the public site is static for now. The broadcast host pushes one-way exports to a static host: leaderboard/stats JSON about every 15 min (interval configurable; ~15 min is the owner's starting value) and the full campaign archive at campaign end. Nothing on the site can read from or write to this store; there is no inbound path to the home network (OPS-ADMIN OA-11).
- **Export content:** only data that is already public: approved callsigns or `REDACTED-…` (Q-DM-2), `commander_id`-keyed pseudonymous replays (DM-6) and aggregate stats. Banned and deleted commanders are excluded as in §4.13. The export schema lives in `contracts/` with an explicit field allowlist.
- **Database:** stay on SQLite (ADR-0003, 2026-10-18 amendment). A later live interactive site with its own API and database triggers the Postgres revisit (§4.17) and a separate security review.
- **Analytics (Q-DM-3):** D7 retention, session length and similar metrics are computed from our own sim and gateway events keyed by `commander_id` (DM-11). Platform dashboards (Twitch/YouTube) are used for viewer counts but not imported. The privacy notice, terms of service and any cookie banner state this (NX-204, NX-314, NX-316). Metric definitions are not written yet (GAP-ANALYSIS §3, P3).

## 8. Size estimates (ESTIMATE; measure in P1 with NX-032)
| Item | Assumption | Arithmetic | Estimate |
|---|---|---|---|
| Command log | 5,000 chat msgs/min burst is the NFR ceiling; assume a *sustained* 20 accepted commands/min average, ~150 bytes JSON each, ~5× zstd ratio | 20 × 60 × 24 × 150 B = 4.3 MB/day raw → ~0.9 MB/day compressed | ~1 MB/day; ~2 MB per 48 h campaign |
| Snapshot | 1,000 entities × ~200 B canonical msgpack + nodes/edges ~50 KB; ~3× zstd | (200 KB + 50 KB) / 3 | ~85 KB each |
| Snapshot retention | 20 rolling + 48 hourly + 1 final per campaign | 69 × 85 KB | ~6 MB per campaign |
| xp_ledger | 1,000 commanders × 50 entries/day × ~250 B with indexes | 12.5 MB/day | ~4.5 GB/year (**dominant**; candidate for yearly archival, Q-DM-1) |
| commanders + identities | 100,000 commanders × ~500 B | 50 MB | small |

To measure in P1/P2: real command rate per hour of day, the actual zstd ratio on the canonical state, ledger rows per active commander per day, and WAL size under raid load.

## 9. Failure modes
| Failure | Behavior |
|---|---|
| Disk full | Writer stops accepting, alert at 80% (OPS), sim continues, ledger intents spill as in §5.1 |
| `SQLITE_BUSY` beyond busy_timeout | Retry the batch with backoff; alert after 3 failures; never drop ledger intents |
| Corrupt snapshot | Fall back to previous snapshot, replay longer log tail, alert |
| Command-log gap | Replay stops at the gap; campaign marked `ABORTED` only by owner decision (admin console); alert |
| Migration failure | Transaction rolls back; app refuses to start; previous image still runs (deploy rollback) |
| Ledger/derived mismatch detected by weekly rebuild check | Alert; derived table rebuilt from ledgers (ledgers are truth) |

## 10. Test plan
| Req | Test |
|---|---|
| DM-1, DM-2 | Integration: PRAGMAs asserted at connect; a second writer connection is refused by the repository |
| DM-3 | Repository API has no update/delete for ledgers; Semgrep rule bans `UPDATE xp_ledger`/`DELETE FROM xp_ledger` outside the deletion job |
| DM-4 | Property: replaying the same event stream twice yields identical ledger row counts |
| DM-5 | CI: incremental stats == `rebuild-stats` on fixture DB |
| DM-6 | Property: no snapshot/log/crash bundle contains any string from the `commanders.callsign` or `display_name` columns of the fixture |
| DM-7 | Startup test: DB at schema N+1 with code at N → refuse to start |
| DM-8 | Semgrep `sql-no-fstring` |
| §5.3 | Unit + property: DR window uses `recorded_at` (real time); re-processing the same events doesn't change awards; XP before the first completed mission is non-persistent; a lone active human earns persistent XP (Q-PROG-6) |
| §4.2 | Two `!quiet` commands from one commander set `taunt_opt_out` to 1 then back to 0; a `!quiet` sent from a second linked platform flips the same row (Q-ALN-12) |
| §4.3 | An envelope with `account_created_at: null` stores `platform_account_created_at` as `NULL`, never a substitute date |
| §4.13a | A GM-injected job on the `COALITION` board is rejected by the CHECK (Q-ALN-11); replaying the same job outcome twice leaves one `tasking_jobs` row; a fixture campaign with three DONE rescue jobs claimed by one commander yields a rescue count of 3 for that commander |
| §4.11 | Insert of a negative merit `delta` is rejected (Q-PROG-7) |
| §4.12 | Rebuild after a rank-table change that raises thresholds leaves every `rank_level` unchanged (Q-CFG-2) |
| §7a | Export files contain no field outside the allowlist; the overlay and site bundles load no third-party script (DM-11) |
| §6.1 | Round-trip and corruption tests: flipped byte → trailer mismatch → fallback |
| §6.2 | Crash-in-the-middle test: kill -9 during write; replay recovers every fsync'd record; no seq gaps |
| §6.4 | Deletion job end-to-end: identities gone, callsign tombstoned (`X-` + 10 base32, `TOMBSTONE` kind), leaderboards exclude, replay renders `REDACTED-…` (Q-DM-2); two deletions in the same second don't collide |
| §7 | Migration test from previous-release fixture; restore drill script runs in nightly CI on a fixture backup |

## 11. Questions (tracked in [OPEN-QUESTIONS](../planning/OPEN-QUESTIONS.md))
Decided 2026-10-17:
- **Q-DM-1:** archive ledger rows older than 12 months into compressed yearly files once the ledger is large (~1 GB, measured); derived totals stay live.
- **Q-OPS-6:** local copy on the Linux server + `age`-encrypted off-site copy (Google Drive first) behind the `BackupTarget` port; tiered retention; quarterly restore test (§7).
- **Q-DM-2:** public replays need no login; player login (own stats, personal highlights) comes later.

Decided 2026-10-18:
- **Q-DM-3:** first-party analytics only, from our own events; no third-party trackers (DM-11, §7a).
- **Q-ARCH-16:** static public site fed by one-way exports; stay on SQLite; a live site triggers the Postgres revisit (§7a, ADR-0003 amendment).
- **Q-PROG-6:** the "<2 humans" persistence gate is dropped (§5.3).
- **Q-PROG-7:** merit is never spent (`SPEND` removed from `merit_ledger`); rank tables are admin presets versioned with `config_hash` (§4.12).
- **Q-CFG-8:** stored timestamps are UTC; owner schedules keep their IANA zone (DM-9).

Decided 2026-10-18 (spec-alignment batch):
- **Q-ALN-12:** `!quiet` is a toggle stored per commander (`commanders.taunt_opt_out`, §4.2).
- **Q-ALN-16:** Tasking Board job outcomes are durable (§4.13a); season and per-role leaderboard source tables belong to the seasons and leaderboards spec (NX-314, §4.13).
- **Q-ALN-11:** a GM injects jobs into the Static's board only (CHECK in §4.13a).
- **Q-ALN-14:** earned ranks are never revoked (`rank_level` never decreases, §4.12).
- **Q-DM-2:** deleted commanders display as `REDACTED-…` (§4.2, §6.4).
- PROGRESSION PROG-4 / IDENTITY §1: platform account age is stored as `platform_identities.platform_account_created_at` (§4.3).

Not modeled yet:
- Season and per-role leaderboard source rows (recon assists that led to engagements, threat-weighted kills, objective damage, hours played, the season key): NX-314 (Q-ALN-16).
- What follows the `REDACTED-` prefix in the displayed name (Q-DM-2 shows only `REDACTED-…`).
- How `taunt_opt_out` combines when two commanders merge (Q-PROG-4).
- Whether Tasking Board jobs done by an AI-run (`ai_run = 1`) viewer unit count toward that commander's recap stats.
- CONTRACTS names no event for the DONE and FAILED job outcomes yet; §4.13a needs one.

## Data model additions pending merge (2026-10-17)
- **From [ADMIN-RBAC](ADMIN-RBAC.md):**
  - Tables: `operators`, `role_grants`, `operator_credentials`, `admin_sessions`, `approval_requests`, `scheduled_items`, `content_versions`.
  - New `admin_audit` columns: `channel`, `permission`, `approval_request_id`, `flags`.
- **From [SUPPORT-REDEMPTIONS](SUPPORT-REDEMPTIONS.md) §8:** `support_events`, `redemption_rules`.
- **From GAMEPLAY §9b:** `campaign_carryover` (campaign_id, from_campaign_id, effects JSON, config_hash, applied_at).
