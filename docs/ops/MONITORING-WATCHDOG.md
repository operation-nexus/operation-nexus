# Monitoring & Watchdog Design (3 layers)

Status: Draft · Tracker: NX-251, NX-252 · Related: OPS-ADMIN spec, HARDWARE.md

## The problem the owner raised
If the home internet goes down, both the stream PC and the Linux server lose internet together. A watchdog on the same LAN **can't tell you** about that outage, and can't send phone alerts through the dead connection. It *can* still see everything on the LAN.

So monitoring is split into three layers. Each one covers failures the others can't see.

```
 Layer 1: on-box (stream PC)        Layer 2: LAN watchdog (Linux server)     Layer 3: off-site dead-man's switch
 ─────────────────────────────      ───────────────────────────────────      ───────────────────────────────────
 supervisor restarts crashed        Probes the stream PC over the LAN        A free external heartbeat service
 processes (app, OBS)               (no internet needed):                    expects a ping every N minutes from
                                    - app /health                            BOTH boxes. If pings stop, it alerts
 frame-freeze probe reloads the     - OBS via obs-websocket                  your phone.
 browser source                     - frame-freeze hash                      → catches internet outages,
                                    - is the stream PC even up?              power cuts, and both boxes dying
                                    Can act locally: restart services
                                    over SSH, Wake-on-LAN, or power-cycle
                                    via a smart plug (optional)
                                    Queues alerts; sends them when the
                                    internet returns
```

Topology per [ADR-0012](../architecture/adr/0012-deployment-topology.md): the stream PC is Windows (app stack in Docker Desktop on WSL2, OBS native), so L1 uses Compose restart policies plus a Windows-side supervisor whose tooling is **open (Q-OPS-7)**; systemd applies only on the Linux server (L2).

## What each layer catches
| Failure | L1 on-box | L2 LAN watchdog | L3 external | Who tells you |
|---|---|---|---|---|
| App or OBS crash | ✅ auto-restart | ✅ verifies recovery | — | L2 (if L1 failed) |
| Overlay frozen | ✅ reload | ✅ detects if L1 missed it | — | L2 |
| Stream PC hung or rebooted | ❌ | ✅ detects; can WoL or power-cycle | ✅ (heartbeat stops) | L2 / L3 |
| Stream offline at the platform (RTMP dropped) | partial | ✅ via platform API (needs internet) | — | L2 |
| **Home internet down** | ❌ | sees it, can't send alerts | ✅ | **L3** |
| Power cut (both boxes) | ❌ | ❌ | ✅ | **L3** |
| Linux server itself dies | — | ❌ | ✅ (its heartbeat stops) | L3 |

## Notes and options
- **LAN without internet:** the two boxes already talk over your router or switch, and that keeps working when the ISP is down (as long as the router has power). No extra hardware needed. A direct Ethernet cable between the boxes is optional; it would only help if the router itself fails.
- **Layer 3 options:** a hosted "cron/heartbeat monitoring" service (dead-man's switch style) that pushes to your phone. Pick one in NX-252. **Free-tier limits and pricing [UNVERIFIED]; check before choosing.** Self-hosting this layer on a cheap VPS is also possible, but costs money.
- **Internet redundancy (optional, later):** a cellular backup (LTE router or phone hotspot) could keep the stream alive through ISP outages. The cost is [UNVERIFIED], and it needs ~6+ Mbps upload for 1080p60 (HARDWARE.md). Not needed for the alpha.
- **Power:** a small UPS on the stream PC, the router and the Linux server rides through brief blips. If the power is out long enough, layer 3 still alerts you.
- **Raspberry Pi:** could replace the Linux server for layer 2 if that server ever goes away. It isn't needed now.
- **What viewers see during an outage:** nothing. If the internet is down, the stream is down. When it comes back, the app resumes from its snapshot (SYSTEM-DESIGN §8), and OBS auto-reconnects (verify that OBS's reconnect setting is enabled).

## Implemented so far (2026-10-25)
On the Linux server (`hiveplex-linux`), `deploy/server/` holds the scripts that run there:
- `hiveplex-notify` posts a message to a Discord webhook. The URL lives only in `/etc/hiveplex-alerts.env` (mode 600, root); it is never in the repo.
- `hiveplex-health-check`, run every 5 minutes by `hiveplex-health.timer`, posts only when a check changes state (OK to FAIL, and FAIL to OK with the downtime), plus one notice after each boot. Checks: root disk at 85% or more, less than 10% of RAM available, both `1.1.1.1` and `8.8.8.8` unreachable (the alert can only be delivered once the internet is back), Tailscale not `Running`, the Docker service not active, and a pending reboot. A Kasa smart plug that has been unreadable for 60 minutes also alerts (`plug_server`, `plug_pc`); shorter Wi-Fi gaps are ignored, since a 3-4 minute gap happened twice on 2026-10-25/26 and the Kasa app was fine.
- Tested on 2026-10-25: a test message, the boot notice and a simulated recovery all arrived in Discord. During a real outage that evening (the server's network and the PC were both down for about 5 minutes) the "FAILED" messages could not be sent and were lost; only the two "recovered" messages arrived. **Fix (same day):** an alert that cannot be delivered is kept in `/var/lib/hiveplex-health/outbox` (newest 50) and sent at the next run once Discord is reachable, marked "(sent N min late, the network was down)", before that run's own alerts. Tested by creating `/var/lib/hiveplex-health/simulate-notify-failure`, which makes `hiveplex-notify` fail until the file is removed.

**PC watchdog (layer 2, 2026-10-25):** the server also watches the harness PC (`192.168.1.102`):
- `pc_lan`: a ping reply from the PC. Alerts when it stops answering (off, asleep or off the network).
- `pc_heartbeat`: the PC sends a status line every 2 minutes (`deploy/pc/hiveplex-heartbeat-send`, a WSL systemd user timer) over a dedicated SSH key that can run only one forced command on the server (`restrict`, `from=` the PC's two addresses, `command=` the receiver `hiveplex-heartbeat-recv`). Alerts when the PC answers ping but the heartbeat is older than 10 minutes: Windows is up and WSL, or its timer, is not. This is the failure that a plain ping cannot see.
- `pc_harness`: alerts when the heartbeat says the `nexus-harness.timer` on the PC is not active.
- If the PC is down, only `pc_lan` speaks, so one outage is one message.
- Planned maintenance (a reboot, a hardware install): `sudo hiveplex-maintenance 60` on the server pauses the PC alerts for 60 minutes; `sudo hiveplex-maintenance off` resumes them.
- Tested 2026-10-25: a stale heartbeat produced the failure state and a fresh one cleared it. A real PC outage then happened (a planned shutdown with maintenance mode left off): the ping check failed at 22:40:07 and Discord reported "pc_lan recovered (down 5 min)" at 22:45; the "failed" message was lost because the network was down too (fixed by the outbox above).

**Dashboard (2026-10-25):** Prometheus, a blackbox exporter, a node exporter and a Kasa plug exporter feed a Grafana dashboard on the server, reachable on the tailnet only (SERVER-SETUP.md, "Monitoring"). It shows internet and PC reachability, ping latency, server load, and the server plug's power, energy and cost.

**Not done yet:** the L3 external heartbeat (NX-252), the PC's CPU/GPU load (Windows exporter; its power is read by its Kasa plug since #373), and Loki logs.

## Implementation items
- NX-251: L1 + L2 probes and actions (Windows-side supervision on the stream PC per Q-OPS-7, a systemd watchdog service on the Linux server, SSH key with restricted commands)
- NX-252: alert routing (ntfy, Discord webhook) + L3 heartbeat service selection
- New NX-257: optional smart-plug power-cycle for a hung stream PC (decide later)
