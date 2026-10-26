# Linux server setup (`hiveplex-linux`)

Status: Draft · written 2026-10-25 · NX-007 follow-up · facts marked **[MEASURED]** were read from the machine over SSH; everything else is what was done to it. Roles and the hardware are in [HARDWARE.md](HARDWARE.md); the topology is [ADR-0012](../architecture/adr/0012-deployment-topology.md); the alert design is [MONITORING-WATCHDOG.md](MONITORING-WATCHDOG.md).

## The machine
- AMD A10-6700 APU (4 threads), 6.5 GiB RAM visible, one 1 TB spinning disk, Ubuntu 26.04.1 LTS (x86_64) **[MEASURED]**.
- User `hiveplex`, passwordless `sudo` (set by the owner for automation).
- LAN address `192.168.1.247` (a DHCP reservation on the router), Tailscale address `100.113.223.88`. The harness PC is `192.168.1.102` on the LAN (pinned by the owner), `desktop-d3k8ndu` on the tailnet.
- The system time zone is `America/Toronto` (from the installer; same offset as US Eastern).

## Access
- **SSH is key-only.** `/etc/ssh/sshd_config.d/10-hiveplex-hardening.conf` sets `PasswordAuthentication no`, `KbdInteractiveAuthentication no` and `PermitRootLogin no`. Remove that file and reload `ssh` to restore passwords.
- `~/.ssh/authorized_keys` holds two keys, each with a comment naming its device: the WSL harness PC and the owner's Mac. To revoke a device, delete its line.
- A client needs the `Host` block that points at the dedicated key. Typing the bare address does not use it:
  ```
  Host hiveserver hiveplex-linux 192.168.1.247
      HostName 192.168.1.247
      User hiveplex
      IdentityFile ~/.ssh/id_ed25519_hiveserver
      IdentitiesOnly yes
  ```
- Never add a private key to the repo or paste one into an issue.

## Firewall (ufw)
Default deny inbound, allow outbound. Allowed in: TCP 22 and TCP 3389 (a service was listening there on all interfaces; assumed to be remote desktop) from `192.168.1.0/24` only, and everything on `tailscale0`. Docker bypasses `ufw` for ports it publishes (`-p`); keep containers on `127.0.0.1` unless a port is meant for the network.

## Tailscale
Installed from Tailscale's apt repository and joined with a one-time auth key (not stored). **The node key expires on 2027-04-24**; disable key expiry for this machine in the Tailscale admin console or it drops off the tailnet. API keys are not kept on the server.

## Docker
Docker Engine 29.9.2, Compose v5.6.1, Buildx v0.38.1 from Docker's official apt repository (Ubuntu 26.04 "resolute"). The signing key fingerprint was checked after download. `hiveplex` is in the `docker` group, which is root-equivalent.

## Tools for the repo
Node 22, npm, `pnpm` 10.28.0, `uv` 0.13.4, `make`, `jq`, `gh` and `restic` are installed. `gh` and git are signed in as the machine account `project-hiveplex` with a fine-grained token; the owner chose its permissions and it is kept in `gh`'s keyring, not in a file in the repo. Repos are cloned under `~/project-hiveplex/`: `operation-nexus`, `operation-nexus-ops` and `operation-nexus-vault`. The git identity is `project-hiveplex` with its GitHub noreply address; commits from this machine are not signed (signing is undecided).

## Alerts (Discord webhook)
| Piece | Where |
|---|---|
| Webhook URL | `/etc/hiveplex-alerts.env`, mode 600, root; one line `DISCORD_WEBHOOK_URL=...`. Never in git. To rotate: delete the webhook in Discord, create a new one, edit the file. |
| `hiveplex-notify "message"` | `/usr/local/bin/`; source `deploy/server/hiveplex-notify`. Mentions are disabled. |
| `hiveplex-health-check` | `/usr/local/bin/`; source `deploy/server/`. State in `/var/lib/hiveplex-health/`. |
| `hiveplex-health.service` and `.timer` | `/etc/systemd/system/`; source `deploy/server/`. Every 5 minutes, 2 minutes after boot. |

What it checks and when it speaks: see MONITORING-WATCHDOG, "Implemented so far". To test the channel: `sudo hiveplex-notify "test"`. To test a failure path without breaking anything: write `fail` into `/var/lib/hiveplex-health/<check>` and run `sudo systemctl start hiveplex-health.service`; a recovery message follows.

## Updates
`unattended-upgrades` is active. Ubuntu holds some updates back ("phased"); those arrive on their own, and `apt list --upgradable` may keep showing them for days. A fixed reboot window is **not set up yet**.

## Rebuilding from scratch (checklist)
1. Install Ubuntu Server 26.04 (64-bit); set a DHCP reservation for the machine on the router.
2. Create user `hiveplex`; add the authorized keys; install the hardening drop-in; enable `ufw` as above.
3. Install Docker from Docker's apt repo, Tailscale from its apt repo (join with a new one-time auth key), then `gh`, `make`, `restic`, Node 22, `uv` and `pnpm`.
4. Log in `gh` as the machine account; clone the three repos.
5. Copy `deploy/server/*` into place, recreate `/etc/hiveplex-alerts.env` with a webhook, enable `hiveplex-health.timer`.

## Known issues
- `make check` fails on this machine on one wall-clock test (issue #358). The code is fine; the machine is slower than the reference PC.
- One 1 TB disk only: no separate-disk backup yet.
- 6.5 GiB RAM: not yet measured against Prometheus + Grafana + Loki plus staging.

## Not done yet
The PC watchdog probe, internet-quality history, Kasa plug power readings and cost dashboards, Prometheus/Grafana, restic backups (local, NAS, Google Drive), self-hosted ntfy, the L3 heartbeat, a reboot window, and UPS monitoring (no UPS yet).
