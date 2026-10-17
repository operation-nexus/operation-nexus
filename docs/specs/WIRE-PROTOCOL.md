# SPEC: Wire Protocol (server → overlay)

Status: Draft · Tracker: NX-170…NX-174

## 1. Transport
WebSocket on `127.0.0.1` (SEC-API-2). Messages are binary msgpack, using JSON Schema–defined types from `/contracts`. A JSON debug mode is available locally.

## 2. Messages
| Type | Direction | Contents |
|---|---|---|
| `Hello` | C→S | `protocol_version`, `client_kind` (overlay/pip/vertical), capability token |
| `Welcome` | S→C | `protocol_version`, `server_build`, `campaign_id`, `tick_rate` |
| `Snapshot` | S→C | Full redacted view at tick T: entities, nodes, edges (on first connect), blobs, HUD state |
| `Delta` | S→C | `tick`, `base_tick`, `upserts[]` (changed fields only), `removes[]`, `events[]` |
| `Hud` | S→C | Momentum, objective + timer, threat tier, ticker items, panel data (≤1 Hz) |
| `Audio` | S→C | `sitrep_id`, text (moderated), audio URL on local nginx, bus, priority |
| `Control` | S→C | `reload`, `resync`, `banner`, `kill_switch` state |
| `Ack` | C→S | Last applied tick (used for delta base) |

## 3. Rules
- **WP-1** Every message carries `v` (`protocol_version`). A major mismatch makes the client show "UPDATE REQUIRED" and reload. Minor versions are additive only.
- **WP-2** Unknown fields MUST be ignored. Unknown message types MUST be logged and ignored.
- **WP-3** If the delta base is missing or there's a gap, the client requests a resync and the server sends a `Snapshot`.
- **WP-4** p95 `Delta` size is under 16 KB at 1,000 entities. Positions are quantized (to 1 m), and values that haven't changed are omitted.
- **WP-5** Clients reconnect with jittered exponential backoff (0.5 s → 10 s max) and show a "COMMS RESYNC" banner after 2 s without data.
- **WP-6** Text fields are always plain text. The client must render them as text, never as HTML.
