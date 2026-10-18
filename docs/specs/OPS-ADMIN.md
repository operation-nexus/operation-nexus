# SPEC: Operations & Admin

Status: Draft · Tracker: NX-250…NX-269

## 1. Watchdog & recovery

The three-layer design (on-box, LAN watchdog, off-site heartbeat) is in [`docs/ops/MONITORING-WATCHDOG.md`](../ops/MONITORING-WATCHDOG.md).

- **Topology (ADR-0012):** the broadcast host is the owner's **Windows** gaming PC. The app stack runs in Docker Desktop on **WSL2**, OBS runs natively on Windows (controlled via obs-websocket), and the deploy script runs inside WSL2 (Q-ARCH-15). The **Linux server** (Ubuntu 24.04 LTS after the rebuild, Q-ARCH-8) runs the watchdog, observability (Prometheus + Grafana + Loki, Q-ARCH-11), backups and staging (Q-OPS-2).
- **Supervision:** Compose restart policies supervise the containers on both machines. On the Linux server, systemd supervises `docker compose` and `nexus-watchdog`. systemd does not apply on the Windows host; its supervision is OA-1…OA-4.
- **OA-1 Windows host session (Q-OPS-7):** the broadcast PC runs the stack under a dedicated **standard (non-admin)** Windows user with auto-login. Docker Desktop starts at login, and every production container uses `restart: unless-stopped`.
- **OA-2 Windows watchdog (Q-OPS-7):** a PowerShell watchdog, started by Task Scheduler at that user's logon, launches OBS and checks OBS, Docker and the overlay about every 30 s. On a failed check it restarts the failed piece and alerts (§2).
- **OA-3 Windows Update (Q-OPS-7):** active hours are set and feature updates paused, so Windows doesn't reboot mid-stream unannounced. The external probe on the Linux server (MONITORING-WATCHDOG L2) remains the last layer.
- **OA-4 Host isolation (Q-OPS-7):** all Windows-specific supervision (watchdog script, Task Scheduler definitions, setup notes) lives under `deploy/windows/`. The container stack stays host-agnostic, so a later move to cloud hosting swaps only the supervisor/encoder layer. The deployment-topology ADR (NX-313) records this migration path.
- Every tool setting in OA-1…OA-3 (auto-login, start-at-login, Task Scheduler, active hours) is **[UNVERIFIED]** until tested on the broadcast PC.
- **Frame-freeze probe:** every 30 s, grab an OBS screenshot (via obs-websocket on localhost). If the heartbeat region's hash hasn't changed for 60 s, reload the browser source. If it's still frozen, restart OBS and alert.
- **Stream-live probe:** query the platform API for live status every 2 min. If the stream is offline, restart the OBS output and alert. A scheduled restart before the 48 h Twitch broadcast limit is **[to verify]**.
- **OA-5 Offline auto-pause (Q-OPS-8):** when the broadcast has been offline longer than `ops.offline_pause_after_min` (CONFIG §6.10; real time, Q-CFG-8), the campaign auto-pauses with reason `TECHNICAL` through the normal logged pause command (ADMIN-RBAC pause flow). Shorter blips do not pause. The trigger is stream-offline detection only; a single chat platform disconnecting MUST NOT pause the campaign.
- **OA-6 Recovery (Q-OPS-8):** when the stream is back, the overlay shows "COMMS RESTORED" with a 30 s countdown, then the campaign auto-resumes. An admin can override either step (stay paused, or resume early) from the Command Center.
- **Fallback scene:** "TECHNICAL DIFFICULTIES – CAMPAIGN PAUSED", shown with ambient music when the app is down.

### 1a. Maintenance window and Ceasefire mode (Q-OPS-9)
- **OA-7 Maintenance window:** one fixed weekly window of up to ~2 h, defined in a configured IANA time zone and converted (Q-CFG-8). The starting slot (Tuesday morning, owner-local) is PROPOSED until the owner confirms it; revisit with analytics. The window is a scheduled `MAINTENANCE` item (ADMIN-RBAC scheduled events).
- **OA-8** During the window the campaign is paused with reason `MAINTENANCE`, and the stream shows a "back at HH:MM" scene with the campaign recap and leaderboards. The window is announced in advance on the HUD and in Discord.
- **OA-9 Ceasefire mode:** for the owner gaming on the broadcast PC, one click (Command Center) or a hotkey: the campaign pauses, OBS switches to a light scene (banner + leaderboard), and heavy overlay rendering stops to free the GPU. Resume is one click and starts a countdown before the campaign continues.
- **OA-10** Sim-time timers (idle handoff/retire, despawn, cooldowns, Tasking Board decision window, logistics, capture) are frozen while paused for maintenance, Ceasefire or offline (Q-CFG-8).
- A dedicated broadcast box (owner plans a new PC) or cloud hosting (OA-4) removes the gaming conflict; HARDWARE.md tracks that.

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
  - stream offline, and the offline auto-pause and auto-resume (OA-5, OA-6)
  - Windows watchdog restart of OBS, Docker or the overlay (OA-2)
  - frozen frames
  - tick p99 over budget for 5 min
  - adapter disconnected for 5 min
  - crash loop
  - disk over 80%
  - LLM + cloud TTS spend at 80% of the $20/month hard cap (Q-AI-5); the breaker cuts off at 100%
  - backup failed

## 3. Command Center (admin console; P2 minimal, phone-friendly)
Per Q-ARCH-7 there are two apps in one codebase: the private **Command Center** described here and in [ADMIN-RBAC](ADMIN-RBAC.md), and the **public site** (replays, leaderboards, stats, Field Manual; no admin features, separate API and deployment).
- **OA-11 Public site feed (Q-ARCH-16):** for now the public site is static. The broadcast host pushes one-way exports to a free static host: leaderboards/stats JSON about every 15 min (configurable) and the full campaign archive at campaign end (DATA-MODEL §7a). There is no inbound path from the site to the home network. Static-host free-tier limits are [UNVERIFIED]. A later live interactive site with its own API and database triggers the ADR-0003 Postgres revisit and a separate security review.
- Auth: passkey (WebAuthn) for the owner and admins, Discord OAuth with a verified role mapping for moderators later (Q-ARCH-12). Authorization follows the RBAC matrix (ADMIN-RBAC §4); in P2 there is a single OWNER operator. Access only through the tailnet and the Discord admin channel (Q-RB-4).
- Controls:
  - **Kill switch** (SEC-MOD-3): hide user text, mute TTS, freeze spawns
  - pause (reason required; moderators may pause) or resume (GM/admin/owner) the campaign, with the owner alert and one-tap resume (ADMIN-RBAC pause flow, Q-RB-1)
  - ban/unban across platforms, and purge a user's units
  - rename or reject callsigns, and review the callsign approval queue
  - clip review queue
  - director override: force a tier or trigger an event
  - Ceasefire on/off, maintenance window schedule, and the offline-pause override (OA-5…OA-9)
  - balance config reload (validated, logged), including the admin-configurable keys for idle handoff/retire (Q-GD-35), taunt naming cooldowns (Q-AI-7), HUD rotation timing and membership (Q-UX-11) and the offline-pause threshold (Q-OPS-8); each is reloaded under CONFIG §5
  - **OA-12 Rank and XP presets (Q-PROG-7):** owner, admin or GM edit the rank table (thresholds, unlocked abilities, cooldowns) and XP source values as named presets. A preset is validated before it can be applied, every change is written to the audit log, and applying one is versioned with the campaign `config_hash` (CONFIG §6.8). Ranks already earned are never revoked (Q-CFG-2).
  - **OA-13 Tasking Board (Q-GD-37):** both sides' boards are visible, with job state, claims and outcomes. A GM may inject or edit jobs; each injection is a logged command.
- **OA-14 GM limits (Q-AI-8):** a GM drives the Static and triggers world events only. World events may help the coalition (supply drop, weather clearing, friendly convoy) but are visible and in-fiction; there is no direct grant of units, ammo or XP to a specific player. Every GM action is logged and flagged in replays.
- Every admin action is a logged command, so replays stay deterministic and there's an audit trail.

## 4. Runbooks (`deploy/runbooks/`)
- deploy and rollback (Windows host: OBS and WSL2/Docker Desktop restart steps, ADR-0012)
- Windows host setup and recovery: user, auto-login, watchdog task, Update settings (OA-1…OA-3, `deploy/windows/`)
- weekly maintenance window and Ceasefire mode (OA-7…OA-9)
- moving the broadcast stack to another host or the cloud (OA-4, NX-313)
- restore from backup
- rotate secrets
- platform outage
- moderation incident (slur on stream)
- disk full
- new campaign or theater
- GPU or driver update

## 5. Open questions
- The pause reason for Ceasefire mode (OA-9) is not decided. `MAINTENANCE` (OA-8) is not yet in the CONTRACTS `PauseReasonCategory` enum.
