# System Design — Operation Nexus

Status: Draft (pending owner review) · Tracker: NX-050…NX-059 · Decisions: [ADRs](adr/)

## 1. Context

```
   Viewers (Twitch → later YouTube, Kick)                  Owner / Mods
          │ chat                                               │ phone/web
          ▼                                                    ▼
 ┌─────────────────────────────── Broadcast Host (single node) ─────────────────────────┐
 │                                                                                      │
 │  nexus-app (Python, one process, modular monolith)                                   │
 │  ┌──────────────┐   ChatEnvelope   ┌─────────────┐  Command(tick)  ┌──────────────┐  │
 │  │ gateway/     │ ───────────────► │ commands/   │ ──────────────► │ sim kernel   │  │
 │  │ platform     │   normalize,     │ parse, auth,│   inbox queue   │ (pure, 10 Hz)│  │
 │  │ adapters     │   rate-limit,    │ moderate    │                 │ step(state,  │  │
 │  └──────────────┘   moderate       └─────────────┘                 │  cmds, rng)  │  │
 │         ▲                                 ▲                        └──────┬───────┘  │
 │         │ replies (batched)               │ advisor suggestions           │ events,  │
 │         │                         ┌───────┴──────┐                        │ state    │
 │         │                         │ advisors/    │◄── redacted view ──────┤          │
 │         │                         │ (LLM, async, │                        ▼          │
 │         │                         │  optional)   │                 ┌──────────────┐  │
 │         │                         └──────────────┘                 │ broadcast/   │  │
 │  ┌──────┴───────┐   ┌─────────────┐  ┌────────────┐                │ FoW redact,  │  │
 │  │ persistence/ │◄──│ progression/│◄─┤ event bus  │◄───────────────│ delta encode │  │
 │  │ SQLite (WAL) │   │ XP, ranks   │  │ (in-proc)  │                └──────┬───────┘  │
 │  └──────────────┘   └─────────────┘  └─────┬──────┘                       │ WS       │
 │                                            ├──► audio/ (TTS worker proc)  │          │
 │                                            ├──► clips/ (review queue)     │          │
 │                                            └──► ops/ (metrics, admin API) │          │
 │                                                                           ▼          │
 │  overlay (static TS bundle via nginx) ◄──── WS (localhost) ────── nexus-app          │
 │       │                                                                              │
 │       ▼                                                                              │
 │  OBS (browser source + audio) ──RTMP──► Twitch / YouTube                             │
 │                                                                                      │
 │  watchdog (systemd + frame-freeze probe) · alerting → phone                          │
 └──────────────────────────────────────────────────────────────────────────────────────┘
          ▲
          │ (Phase P3) link portal: small separate web app, OAuth, public internet via tunnel
```

## 2. Design principles

1. **Server-authoritative, deterministic core.** `step(state, commands, rng) → (state', events)` is pure. Determinism makes replays, golden tests, bug reproduction and balance studies possible (ADR-0002).
2. **The sim never waits.** Every slow thing (platform I/O, LLM, TTS, DB writes, clients) is async and outside the tick. Its results come back as commands stamped for a future tick.
3. **Rules decide; AI advises.** LLMs choose between rule-valid options and write flavor text. They never write state directly, and their outputs are logged as inputs (ADR-0007).
4. **Hostile input by default.** All chat, names and LLM output is untrusted until it has been normalized, validated and moderated (THREAT-MODEL).
5. **The stream must not die.** A failure in any component degrades the broadcast instead of freezing it: a banner, a fallback scene, or auto-recovery.
6. **Modular monolith first.** Module boundaries are enforced in code (import-linter). A module becomes its own process only when there's a measured reason (ADR-0001).
7. **Config over code for balance.** All tunables live in versioned YAML, and each campaign stores the hash of its config.

## 3. Non-functional requirements (initial; confirm Q-OPS-*)

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Sim tick rate | 10 Hz fixed step. Tick p99 compute < 25 ms at 1,000 entities |
| NFR-2 | Command ingest → on-screen ack (server side) | p95 < 500 ms (platform delay excluded and measured separately) |
| NFR-3 | Overlay frame time on reference host | p95 < 12 ms at 1080p60 |
| NFR-4 | Availability (stream live & updating) | ≥ 99% monthly |
| NFR-5 | Recovery from process crash | Automatic, < 2 min; sim resumes from last snapshot (≤ 30 s of state lost) |
| NFR-6 | Deploy impact on stream | ≤ 10 s "COMMS RESYNC" banner; no stream disconnect |
| NFR-7 | Data durability | Snapshot every 30 s; command log fsync'd every 1 s; nightly offsite encrypted backup |
| NFR-8 | Concurrency | Designed for 300 live viewer units, 1,000 total entities, 5,000 chat msgs/min burst |
| NFR-9 | Cost | ≤ Q-OPS-3 ceiling; LLM/TTS hard budget with circuit breaker |
| NFR-10 | Moderation | Zero unmoderated user text on stream or in TTS |
| NFR-11 | Observability | Every component exports health + key metrics; external freeze/offline alert < 2 min |

## 4. Modules (inside `services/sim` → package `nexus`)

| Module | Responsibility | May import | Must not |
|---|---|---|---|
| `nexus.core` | Pure sim kernel: entities, kinematics, combat, FoW, logistics, capture, director rules | `nexus.contracts`, stdlib, numpy | Any I/O, asyncio, time, random (except injected `SimRng`) |
| `nexus.contracts` | Generated types from `/contracts` | — | Logic |
| `nexus.runtime` | Fixed-step scheduler, command inbox, snapshotting, command log, state hashing | core | Platform code |
| `nexus.gateway` | Platform adapters (`TwitchAdapter`, later `YouTubeAdapter`, `KickAdapter`) → `ChatEnvelope` | contracts | core |
| `nexus.commands` | Parse, authorize, rate-limit, moderate → `Command` | contracts, moderation | core internals |
| `nexus.moderation` | Normalize, denylist, callsign generation, approval | — | — |
| `nexus.broadcast` | Per-tick FoW redaction, delta encoding, WS fan-out with bounded queues | core (read-only views) | Mutating state |
| `nexus.progression` | Consumes events → XP/merit/ranks; writes via persistence | persistence | core |
| `nexus.persistence` | SQLite repository + migrations | — | core |
| `nexus.advisors` | LLM advisor/narrator clients, budgets, circuit breakers (P4) | contracts | core, platform tokens |
| `nexus.audio` | Sitrep queue → TTS worker process → audio to overlay | contracts | — |
| `nexus.clips` | Excitement scoring, clip job creation, review queue | contracts | Auto-upload |
| `nexus.ops` | Health, metrics (Prometheus), admin API (kill switch, bans, pause) | all read-only + control commands | — |

Boundaries are enforced with `import-linter` contracts in CI (NX-019).

## 5. Key flows

### 5.1 Chat command (fast path)
1. The adapter receives an EventSub message, verifies it, and dedupes by message id.
2. It normalizes the message into a `ChatEnvelope{platform, platform_user_id, display_name, text, received_at}`.
3. `commands` checks for a ban, applies the token-bucket rate limit, and parses against the command grammar. Unknown input is dropped silently, and **ordinary chat never reaches an LLM**.
4. It resolves the commander: get or create by `(platform, platform_user_id)`, assigning a generated callsign.
5. It emits `Command{commander_id, kind, args, target_tick = current+1}` to the inbox.
6. At that tick, `core.step` applies the commands in canonical order (sorted by `(target_tick, seq)`).
7. Events (`UnitSpawned`, …) go to the broadcast layer, and the overlay shows an ack ping on the next frame.
8. Chat replies are **batched**: one summary message per N seconds at most, within Twitch's 20 or 100 per 30 s limit. Acks are primarily visual.

### 5.2 Tick
`runtime` runs a fixed-step accumulator on a monotonic clock. Each tick:
1. Drain the inbox for this tick.
2. `core.step`.
3. Append the commands to the command log.
4. Publish events.
5. Write a snapshot every 300 ticks, and a state hash every 100 ticks.

If the tick runs late, it catches up by up to 3 steps and then records a `tick_overrun` metric. Frames are never silently dropped.

### 5.3 Broadcast
Per tick, `broadcast` builds a **redacted coalition view**. Fog-of-war filtering happens server-side, so hidden data never leaves the process. It then diffs that view against the last view acknowledged per client, and sends `Delta{tick, upserts, removes, events}`. Clients get a full `Snapshot` on connect or resync. Each client's send queue is capped, and a client that falls behind gets dropped and must resync.

### 5.4 Threat Director
The director runs inside `core`, so it is deterministic. It sees only the **enemy-side fog-of-war view** (SEC fairness rule from C22). Every 60 s of sim time it evaluates smoothed coalition power and moves between tiers with hysteresis. It spends a tier budget on rule-defined operations. Its threat memory (convoy attacks, for example) is a set of decaying counters. Optional LLM advisor: see THREAT-DIRECTOR §Advisor.

### 5.5 Persistence & recovery
- **Live state** lives in memory, inside the sim process.
- **Recovery data:** snapshots (msgpack + zstd) plus an append-only command log. Restart means loading the last snapshot and replaying the log up to the crash tick.
- **Durable data:** profiles, XP, campaign history and identities are stored in SQLite. Only `progression` and the identity module write them.
- **Replays** are rebuilt from the command log plus the seed plus the config hash. Replays contain `commander_id`s only, never names (SEC-DATA-2).

## 6. Deployment (ADR-0006)
- **Single broadcast host**, running Docker Compose with:
  - `nexus-app`
  - `nexus-tts` (separate process; GPL isolation)
  - `nginx` (overlay static files)
  - `node-exporter` / `prometheus` / `grafana` (optional), or a hosted free tier
- **OBS and the watchdog** run on the host under systemd.
- **Images** are pulled from GHCR and must be signed.
- **Overlay WS** binds to `127.0.0.1`.
- **No public inbound ports.** The P3 link portal is exposed through a tunnel (Cloudflare Tunnel or Tailscale Funnel) to a separate container with no access to stream keys.

## 7. Scaling path (when, not now)
| Trigger (measured) | Change |
|---|---|
| Tick p99 > 50 ms at target load after NumPy vectorization | Port hot loops to Rust (PyO3), keeping the same API |
| Second writer process (link portal, companion site) | SQLite → Postgres (ADR-0003 revisit) |
| Gateway needs independent restarts / more platforms | Split gateway into its own process; use Redis Streams for commands |
| Companion site traffic | Separate read replica / static export of stats; CDN |
| Multiple simultaneous theaters | Revisit orchestration (K3s) |

## 8. Failure modes
| Failure | Viewer sees | Automatic response |
|---|---|---|
| Platform API down | "TWITCH UPLINK LOST" chip; sim continues with AI garrison | Adapter backoff + reconnect; alert after 5 min |
| Sim exception in tick | ≤ 2 min "COMMS RESYNC" | Supervisor restarts; restore snapshot + log; alert; crash bundle saved (seed, log, tick) |
| Overlay WS drop | Momentary freeze → resync | Auto-reconnect with jittered backoff; full snapshot |
| OBS/encoder crash | Stream offline | systemd restart OBS; external probe alerts |
| Frozen frames (overlay hung) | Static image | Frame-hash probe detects → reload browser source → alert |
| TTS down | No voice; text sitreps continue | Circuit breaker; alert |
| LLM down / over budget | Rule-only director, generic flavor text | Circuit breaker |
| DB locked / disk full | Progress not saved; game continues | Writes queued in memory (bounded); alert; disk usage alert at 80% |
| Moderation miss reported | — | Operator kill switch (blank names, mute TTS); ban cascades |
