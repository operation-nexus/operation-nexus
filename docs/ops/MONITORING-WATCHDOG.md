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

## Implementation items
- NX-251: L1 + L2 probes and actions (Windows-side supervision on the stream PC per Q-OPS-7, a systemd watchdog service on the Linux server, SSH key with restricted commands)
- NX-252: alert routing (ntfy, Discord webhook) + L3 heartbeat service selection
- New NX-257: optional smart-plug power-cycle for a hung stream PC (decide later)
