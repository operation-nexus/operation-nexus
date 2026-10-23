# SPEC: Wire Protocol (server → overlay)

Status: Draft · Tracker: NX-170…NX-174

## 1. Transport
WebSocket, bound as SEC-API-2 requires (docs/security). Messages are binary msgpack, using JSON Schema–defined types from `/contracts`. A JSON debug mode is available locally.

## 2. Messages
Field names follow `contracts/wire/` (`Hello` has a schema) and CONTRACTS §7 (`Welcome` has no schema yet).

| Type | Direction | Contents |
|---|---|---|
| `Hello` | C→S | `v`, `client_kind` (overlay/pip/vertical), `capability_token`, `last_tick` |
| `Welcome` | S→C | `v`, `server_build`, `campaign_id`, `tick_rate_hz`, `theater` |
| `Snapshot` | S→C | Full redacted view at tick T: entities, nodes, edges (on first connect), blobs, HUD state |
| `Delta` | S→C | `tick`, `base_tick`, `upserts[]` (changed fields only), `removes[]`, `events[]` |
| `Hud` | S→C | Momentum, objective + timer, threat tier, ticker items, panel data (≤1 Hz) |
| `Audio` | S→C | `sitrep_id`, text (moderated), audio URL on local nginx, bus, priority |
| `Control` | S→C | `reload`, `resync`, `banner`, `kill_switch` state |
| `Ack` | C→S | Last applied tick (used for delta base) |

## 3. Rules
- **WP-1** Every message carries `v` (the PROTOCOL_VERSION string). A major mismatch makes the client show "UPDATE REQUIRED" and reload. Minor versions are additive only.
- **WP-2** Unknown fields MUST be ignored. Unknown message types MUST be logged and ignored.
- **WP-3** If the delta base is missing or there's a gap, the client requests a resync and the server sends a `Snapshot`.
- **WP-4** p95 `Delta` size is under 16 KB at 1,000 entities. Positions are quantized (to 1 m), and values that haven't changed are omitted.
- **WP-5** Clients reconnect with jittered exponential backoff (0.5 s → 10 s max) and show a "COMMS RESYNC" banner after 2 s without data.
- **WP-6** Text fields are always plain text. The client must render them as text, never as HTML.
