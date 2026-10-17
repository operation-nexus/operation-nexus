# SPEC: Operations & Admin

Status: Draft · Tracker: NX-250…NX-269

## 1. Watchdog & recovery
- systemd units supervise `docker compose`, OBS, and `nexus-watchdog`.
- **Frame-freeze probe:** every 30 s, grab an OBS screenshot (via obs-websocket on localhost). If the heartbeat region's hash hasn't changed for 60 s, reload the browser source. If it's still frozen, restart OBS and alert.
- **Stream-live probe:** query the platform API for live status every 2 min. If the stream is offline, restart the OBS output and alert. A scheduled restart before the 48 h Twitch broadcast limit is **[to verify]**.
- **Fallback scene:** "TECHNICAL DIFFICULTIES – CAMPAIGN PAUSED", shown with ambient music when the app is down.

## 2. Observability
- **Metrics** (Prometheus format):
  - tick duration histogram, overruns, entity count, viewer units, reserve queue length
  - WebSocket clients and bytes sent
  - commands per second by platform, rejected commands by reason
  - adapter lag, YouTube quota used
  - TTS queue length, LLM latency/cost/errors
  - DB write latency, disk usage
- **Logs:** structured JSON with a correlation id per command, and a redaction filter for secrets and tokens.
- **Dashboards:** one "stream health" board.
- **Alerts** (Q-OPS-4):
  - stream offline
  - frozen frames
  - tick p99 over budget for 5 min
  - adapter disconnected for 5 min
  - crash loop
  - disk over 80%
  - LLM/TTS budget at 80%
  - backup failed

## 3. Admin console (P2, phone-friendly)
- Auth: owner only, via passkey or OAuth plus an allowlist. Access only through the tailnet.
- Controls:
  - **Kill switch** (SEC-MOD-3): hide user text, mute TTS, freeze spawns
  - pause or resume the campaign
  - ban/unban across platforms, and purge a user's units
  - rename or reject callsigns, and review the callsign approval queue
  - clip review queue
  - director override: force a tier or trigger an event
  - balance config reload (validated, logged)
- Every admin action is a logged command, so replays stay deterministic and there's an audit trail.

## 4. Runbooks (`deploy/runbooks/`)
- deploy and rollback
- restore from backup
- rotate secrets
- platform outage
- moderation incident (slur on stream)
- disk full
- new campaign or theater
- GPU or driver update
