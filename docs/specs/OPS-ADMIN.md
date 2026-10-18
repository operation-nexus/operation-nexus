# SPEC: Operations & Admin

Status: Draft · Tracker: NX-250…NX-269

## 1. Watchdog & recovery

The three-layer design (on-box, LAN watchdog, off-site heartbeat) is in [`docs/ops/MONITORING-WATCHDOG.md`](../ops/MONITORING-WATCHDOG.md).

- **Topology (ADR-0012):** the broadcast host is the owner's **Windows** gaming PC. The app stack runs in Docker Desktop on **WSL2**, OBS runs natively on Windows (controlled via obs-websocket), and the deploy script runs inside WSL2 (Q-ARCH-15). The **Linux server** (Ubuntu 24.04 LTS after the rebuild, Q-ARCH-8) runs the watchdog, observability (Prometheus + Grafana + Loki, Q-ARCH-11), backups and staging (Q-OPS-2).
- **Supervision:** Compose restart policies supervise the containers on both machines. On the Linux server, systemd supervises `docker compose` and `nexus-watchdog`. On the Windows host, how OBS, WSL2 and Docker Desktop are supervised and auto-started is **open** (Q-OPS-7); systemd does not apply there.
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
- **Dashboards:** one "stream health" board, on self-hosted Prometheus + Grafana + Loki on the Linux server (Q-ARCH-11). The external dead-man's switch stays (MONITORING-WATCHDOG L3).
- **Alerts** (Q-OPS-4: ntfy push + a private Discord channel, text-based first):
  - stream offline
  - frozen frames
  - tick p99 over budget for 5 min
  - adapter disconnected for 5 min
  - crash loop
  - disk over 80%
  - LLM + cloud TTS spend at 80% of the $20/month hard cap (Q-AI-5); the breaker cuts off at 100%
  - backup failed

## 3. Command Center (admin console; P2 minimal, phone-friendly)
Per Q-ARCH-7 there are two apps in one codebase: the private **Command Center** described here and in [ADMIN-RBAC](ADMIN-RBAC.md), and the **public site** (replays, leaderboards, stats, Field Manual; no admin features, separate API and deployment).
- Auth: passkey (WebAuthn) for the owner and admins, Discord OAuth with a verified role mapping for moderators later (Q-ARCH-12). Authorization follows the RBAC matrix (ADMIN-RBAC §4); in P2 there is a single OWNER operator. Access only through the tailnet and the Discord admin channel (Q-RB-4).
- Controls:
  - **Kill switch** (SEC-MOD-3): hide user text, mute TTS, freeze spawns
  - pause (reason required; moderators may pause) or resume (GM/admin/owner) the campaign, with the owner alert and one-tap resume (ADMIN-RBAC pause flow, Q-RB-1)
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
