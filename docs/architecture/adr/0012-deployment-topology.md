# ADR-0012: Deployment topology: Windows/WSL2 broadcast host plus a Linux ops server

- Status: Proposed (records owner decisions Q-ARCH-8, Q-ARCH-10, Q-ARCH-11, Q-ARCH-15, Q-OPS-2 of 2026-10-17; only the owner moves it to Accepted)
- Date: 2026-10-17
- Deciders: owner
- Amends: [ADR-0006](0006-deployment-single-node.md) (ADR-0006 is kept as written; this ADR records where its single-host assumption no longer holds)
- Related: SYSTEM-DESIGN §6, OPS-ADMIN §1, CICD-ARCHITECTURE §6, MONITORING-WATCHDOG, HARDWARE, NX-007, Q-OPS-7, Q-OPS-9

## Context
ADR-0006 assumed one Linux broadcast host where Docker Compose runs the app and systemd supervises OBS and the watchdog. The owner's real hardware (HARDWARE.md) is different:
- **Gaming PC:** Windows, i7-8700, 32 GB RAM, GTX 1070 8 GB. It runs 24/7 and is also used for gaming. The owner rules out dual boot.
- **Linux home server:** older Intel i5, 8 or 16 GB RAM (unconfirmed), currently Ubuntu 16.04 or 18.04, which are past standard support.

The owner then decided:
- **Q-ARCH-15:** signed images; staging auto-deploys to the Linux server; production on owner tap-approve with auto-rollback; Tailscale, no open ports. On the Windows host the deploy script runs inside WSL2 (Docker Desktop), and OBS stays native on Windows, controlled via obs-websocket.
- **Q-OPS-2:** staging runs on the Linux server, streaming to an unlisted test channel. If the server is too old or weak (checked in NX-007), a cheap cloud server is the fallback.
- **Q-ARCH-11:** self-hosted Prometheus + Grafana + Loki on the Linux server; the external dead-man's switch stays (MONITORING-WATCHDOG L3).
- **Q-ARCH-8:** the Linux server moves to Ubuntu 24.04 LTS before it hosts the watchdog, staging or backups.
- **Q-ARCH-10:** secrets are encrypted with sops + age to each machine's key, in the private `operation-nexus-ops` repo.

## Options considered
1. **Keep ADR-0006 as is** (one Linux host). Doesn't match the hardware; it would need a new machine or a dual boot, which the owner ruled out.
2. **Two machines with split roles** (this ADR): production stream on the Windows PC, operations and staging on the Linux server.
3. **Everything on the Windows PC.** The watchdog can't detect that its own box died, and staging would compete with the live stream.

## Decision
Option 2.

| Machine | Runs | Supervision |
|---|---|---|
| **Windows gaming PC** (production broadcast host) | Docker Desktop on WSL2: `nexus-app`, `nexus-tts`, `nexus-llm` (isolated LLM container, Q-AI-3), `nginx` overlay. OBS **native on Windows**, controlled via obs-websocket. The deploy script runs inside WSL2. | Compose restart policies for containers. How OBS, WSL2 and Docker Desktop are auto-started and supervised on Windows (and how Windows Update is kept from rebooting mid-stream) is **open: Q-OPS-7**. systemd does not apply on this host. |
| **Linux server** (Ubuntu 24.04 LTS after rebuild) | Watchdog L2 (LAN probes of the PC), Prometheus + Grafana + Loki, local backup copy + encrypted off-site upload (`BackupTarget`, Q-OPS-6), the **staging** stack streaming to an unlisted test channel | systemd + Compose |
| **External** | Dead-man's switch / heartbeat (L3) | Provider-managed |

Unchanged from ADR-0006: images are built and signed in CI (cosign keyless) and pulled from GHCR; deploys go over Tailscale from a protected GitHub Environment; no inbound ports on either machine; no self-hosted runner executes PR code; health-gated restart with automatic rollback.

## Consequences
- The watchdog lives on a different box from the stream, so a dead PC is detected (MONITORING-WATCHDOG).
- Staging no longer competes with the live stream for CPU/GPU, but its feasibility depends on the server's real specs (NX-007; RAM 8 vs 16 GB is unconfirmed). The cloud fallback (Q-OPS-2) covers a weak server.
- WSL2 adds a virtualization layer between Docker and the host. Its effect on the sim tick budget (SC-10) and on the reference host for performance tests is **not measured** yet (Q-TEST-1 is open).
- Gaming, updates and reboots on the broadcast PC remain the main availability risk (HARDWARE "Fit for this project"); the maintenance window and what the stream shows while the owner games are open (Q-OPS-9).
- Runbooks (OPS-ADMIN §4) need Windows-specific steps for OBS and WSL2 restarts.
- **Revisit when:** a dedicated broadcast box replaces the gaming PC, the Linux server can't carry staging plus observability, or multiple theaters run at once (SYSTEM-DESIGN §7).
