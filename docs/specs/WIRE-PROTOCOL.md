# SPEC: Wire Protocol (server → overlay)

Status: Approved (owner, 2026-11-04, in chat, with the lead defaults below) · Tracker: NX-170, NX-171 (clients: NX-175, NX-178) · ADRs: 0004, 0005 · Related: CONTRACTS §7 (field shapes), SIM-CORE §5 and SC-10, FOG-OF-WAR, THREAT-MODEL (SEC-API-2/3 at :76-77, SEC-OV-2 at :81), OVERLAY

Values marked PROPOSED are lead defaults, tunable in config without a spec change. Everything else is normative.

## 1. Purpose and scope
1. The one-way state feed from the sim to the browser overlay that OBS renders. The overlay never sends commands; chat is the only command path.
2. Field shapes live in [CONTRACTS §7](CONTRACTS.md) and `contracts/wire/`; this spec does not repeat them. Where the two disagree, CONTRACTS wins on shape and this spec wins on behavior.
3. Not in P2, each deferred to a later item: `Audio` (needs TTS; NX-225, AUDIO-TTS), the `BANNER` and `KILL_SWITCH` `Control` actions (kill-switch banners; NX-253), and the PiP and vertical clients (NX-179, NX-180b). Their schemas may exist; the P2 server never sends them.

## 2. Transport
1. WebSocket served by FastAPI/Starlette on uvicorn (ADR-0004; the dependency write-up goes in the NX-170 PR). Binary frames carry msgpack of the generated types.
2. JSON text frames are a debug mode: off by default and honored only when the server is bound to loopback.
3. The overlay is Canvas2D with DOM panels and renders at server tick minus 100 ms (ADR-0005), so Deltas are never batched or delayed server-side.

## 3. Messages
| Type | Dir | Sent when | Shape |
|---|---|---|---|
| `Hello` | C→S | First client frame | `contracts/wire/hello.json`; `client_kind` is `OVERLAY\|PIP\|VERTICAL` (upper case), P2 serves `OVERLAY` only |
| `Welcome` | S→C | Every (re)connect, after a valid Hello | CONTRACTS §7; static nodes, edges, `bounds_m` and the terrain ref are in `Welcome.theater` |
| `Snapshot` | S→C | After Welcome, on resync, on a detected gap | CONTRACTS §7; includes the `Hud` state |
| `Delta` | S→C | Every tick | CONTRACTS §7 |
| `Hud` | S→C | At most 1 Hz, its own message | CONTRACTS §7 |
| `Control` | S→C | Version mismatch or gap | P2 actions: `RELOAD`, `RESYNC` only |
| `Ack` | C→S | After applying a Delta | CONTRACTS §7 (`applied_tick`) |
| `Audio` | S→C | Not in P2 (§1.3) | CONTRACTS §7 |

## 4. Rules
- **WP-1 Version.** Every message carries `type` and `v` (`"major.minor"`, `contracts/VERSION`). On a major mismatch in `Hello` the server sends `Control{RELOAD}` and closes (4003); the overlay shows "UPDATE REQUIRED" and reloads. A minor mismatch is ignored.
- **WP-2 Tolerance.** Unknown fields are ignored. An unknown message type is logged and ignored. Neither crashes either side.
- **WP-3 Gap and resync.** A `Delta` carries `base_tick`. If the client lacks that base, or its `Ack` lags past a gap limit (PROPOSED 10 ticks), the server sends `Control{RESYNC}` then a `Snapshot`. A client that detects a gap asks for the same by sending an `Ack` with its last applied tick.
- **WP-4 Size.** p95 `Delta` ≤ 16 KB at 1,000 entities. Positions are quantized to 1 m and unchanged values are omitted. Measured by NX-171.
- **WP-5 Client reconnect.** Jittered exponential backoff, 0.5 s to 10 s max, and a "COMMS RESYNC" banner after 2 s without data (NX-175).
- **WP-6 Text.** Text fields are `SafeText` or `ModeratedText` (CONTRACTS, text rules). The client renders them with `textContent`, never as HTML (SEC-OV-1).
- **WP-7 Handshake.** `Hello` → `Welcome` → `Snapshot`, then `Delta`s. The first frame MUST be a valid `Hello` within PROPOSED 5 s, else close with 4001. `Hello.last_tick` is a hint only; P2 always sends a full `Snapshot` and never replays missed Deltas.
- **WP-8 Frame build.** Once per tick, right after `step`, on the sim thread, the server builds one shared `Delta` as immutable bytes (SIM-CORE §5.3-5.4, Q-SIM-8/9); its time counts inside SC-10. A `Snapshot` is built on demand, at most once per tick, and shared by every client that needs one that tick. Socket encoding of per-client extras and all sending happen off the sim thread.
- **WP-9 Redaction.** Redaction happens server-side, before serialization, from the coalition `SideView` (`core/fog.py`; FOW-1). The client never receives a hidden entity, seed or raw display name, and is never trusted to hide one.
- **WP-10 Cadence.** `Delta` every tick, empty ones included (liveness). `Hud` at most 1 Hz as its own message (and inside every `Snapshot`). `Snapshot` only on connect, on resync or on a detected gap. No periodic keyframes in P2.
- **WP-11 Backpressure (SEC-API-3).** Each client has a bounded send queue of PROPOSED 3 frames. A full queue drops that client (close 4004). The tick never waits on a client; the impact of all clients on the tick is ≤ 5 ms. A dropped client reconnects and gets a `Snapshot` (WP-7).
- **WP-12 Caps.** Connections are capped at PROPOSED 8, configurable; the next one is closed with 4006. Inbound messages are capped at PROPOSED 4 KB (close 1009). The server pings every PROPOSED 15 s and closes a client silent for PROPOSED 45 s (4005). `Ack`s are limited to PROPOSED 20 per second per client; the excess is ignored, not queued.
- **WP-13 Client frames.** Every inbound frame is validated against its schema before use. A malformed or schema-violating frame (the first one is WP-7) is logged as `contract_violation` with the schema id (CONTRACTS §9) and dropped; the connection stays open. The only outbound frames a client can trigger are the resync responses of WP-3.
- **WP-14 Auth (SEC-API-2).** As in §7.

## 5. Close codes
A closed set. 1001 and 1009 are standard WebSocket codes; the rest are application codes.
| Code | Name | When |
|---|---|---|
| 1001 | `SERVER_RESTART` | Shutdown or restart |
| 1009 | `MESSAGE_TOO_BIG` | Inbound frame over the WP-12 cap |
| 4001 | `INVALID_HELLO` | First frame missing, late or malformed, or a `client_kind` not served in P2 |
| 4002 | `AUTH_FAILED` | Bad `capability_token` |
| 4003 | `VERSION_MISMATCH` | Major mismatch, after `Control{RELOAD}` |
| 4004 | `SLOW_CLIENT` | Send queue full |
| 4005 | `IDLE_TIMEOUT` | No pong or traffic in time |
| 4006 | `AT_CAPACITY` | Connection cap reached |

A disallowed Origin never upgrades: the server answers the HTTP request with 403 (§7.2).

## 6. Failure modes
| Failure | Behavior |
|---|---|
| Client drop (network, OBS refresh) | The server frees its queue. The client reconnects (WP-5) and gets Welcome and a full Snapshot (WP-7). |
| Slow client | Dropped with 4004 (WP-11); other clients and the tick are unaffected. |
| Server restart | Clients see 1001 or a socket error and reconnect with backoff. After sim recovery (SIM-CORE §5.11) they get Welcome and a Snapshot at the recovered tick; after a Welcome the overlay MUST accept a tick lower than the last it saw. |
| Gap (missing base, lagging Ack) | `Control{RESYNC}` then `Snapshot` (WP-3). |
| Major version mismatch | `Control{RELOAD}`, close 4003, "UPDATE REQUIRED" (WP-1). A minor mismatch is ignored. |
| Bad token | Close 4002 with no frame sent first. Logged without the token. |
| Frame build exception | The frame is dropped and logged; the next tick sends `Control{RESYNC}` and a `Snapshot`. A build that overruns the budget records `tick_overrun` (SIM-CORE §5.6); the bench (§8) guards it. |
| Producer emits a schema-invalid frame | `contract_violation` logged, frame dropped, metric (CONTRACTS §9). |

## 7. Security
1. **Auth, SEC-API-2 (owner, 2026-11-04, chat).** `capability_token` is a static secret read from the environment (`.env`, never in the repo or a log). The OBS browser-source URL carries it in the fragment (`#token=…`), which browsers never send to the server, so it stays out of server and proxy logs. The page's JS reads it and sends it in `Hello.capability_token` (the schema field; ≤ 128 characters).
2. The server compares the token in constant time, never logs or echoes it, binds `127.0.0.1` or the private network (SYSTEM-DESIGN), and checks `Origin` against an explicit allowlist, with no wildcard, on upgrade.
3. Rotation: change `.env` and the OBS URL, then restart. P2 has no token store and no expiry.
4. **CSP, SEC-OV-2.** The overlay page ships a strict CSP: no inline script, `connect-src` limited to the WS origin. OBS page permissions are "No access".
5. **Hostile input.** `Hello` and `Ack` are validated, length-capped, and never echoed or logged raw; a failing token is not logged even in part. Text fields follow WP-6.
6. **Backpressure and caps** are WP-11 and WP-12 (SEC-API-3). **Redaction** is WP-9.

## 8. Test plan
| Requirement | Test |
|---|---|
| Messages match schemas | Generated-type round trip and schema validation for every message, Python and TS (NX-021 drift check) |
| No hidden entity, seed or display name on the wire (WP-9) | Property test over random sim runs, on every Snapshot and Delta payload (CONTRACTS §10, FOW-1) |
| Handshake and close codes (WP-7, §5) | Integration tests: valid flow; no Hello in time (4001); bad token (4002); major mismatch (`RELOAD`, 4003); unsupported `client_kind` (4001); cap (4006); oversize (1009); idle (4005); disallowed Origin (403) |
| Hostile input (WP-13) | Fuzz `Hello` and `Ack`: a bad `Ack` is dropped and logged and the connection survives; a bad first frame closes; the token never appears in logs |
| Slow client (WP-11) | A client that never reads is dropped with 4004; tick duration with it connected stays within 5 ms of the baseline |
| Gap (WP-3) | An `Ack` lagging past the limit gets `RESYNC` and a `Snapshot` |
| Delta size (WP-4) | p95 ≤ 16 KB at 1,000 entities (NX-171) |
| Tick budget (SC-10) | Bench of `step` plus frame build at 1,000 entities and 500 viewer units on the reference host, p99 < 25 ms (NX-170 part c) |
| Frame build is read-only | The state hash is unchanged with and without the broadcaster attached |

## 9. NX-170 split
Three PRs, each within the size rule (AGENTS.md rule 7):
1. **(a) Schemas and frames.** `Welcome`, `Snapshot`, `Delta`, `Hud`, `Control` and `Ack` in `contracts/wire/`, the `make contracts` output (Python and TS), and the `nexus.broadcast` frame builders with redaction (WP-8, WP-9). NX-171 adds the Delta encoder and size test on top.
2. **(b) Server.** The FastAPI WS endpoint, per-client queues, auth, caps, close codes, and the hook into `runtime/loop.py` after `step`. Carries the dependency write-up.
3. **(c) Bench.** `step` plus frame build at 1,000 entities against SC-10 (NX-376 measured `step` only).

## 10. Open questions
None open. Deferred items are listed in §1.3.
