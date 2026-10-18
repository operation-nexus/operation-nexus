# ADR-0006: Single-node deployment with Compose, signed images, and a Tailscale-based deploy

- Status: Accepted (owner, 2026-10-17); amended by [ADR-0012](0012-deployment-topology.md)
- Date: 2026-10-17

## Context
"Helm from day one" and K3s are premature. The broadcast needs a GPU host running OBS, which is a single physical machine.

## Decision
- Docker Compose on the broadcast host. OBS and the watchdog run under systemd on the host.
- CI builds the images, signs them (cosign keyless), and pushes them to GHCR. A deploy job in a protected GitHub Environment connects over Tailscale (ephemeral, tagged node) and runs `deploy/bin/deploy`. That script verifies signatures, pulls, does a health-gated restart, and rolls back automatically on failure.
- No inbound ports on the host. No self-hosted runner executes PR code.

## Consequences
Simple and cheap, and rollback takes one command. A single point of failure is accepted, given the uptime target of 99%. Revisit when multiple theaters run at once or the host can't keep up.

## Amendment note (2026-10-17)
The decision text above assumed one Linux host with OBS and the watchdog under systemd. The owner's actual setup is a **Windows** gaming PC (app stack in Docker Desktop on WSL2, OBS native) plus a separate **Linux server** for watchdog, observability, backups and staging. [ADR-0012](0012-deployment-topology.md) records that topology. The rest of this ADR (Compose, signed images, Tailscale deploy, no inbound ports, no self-hosted runner for PR code) still applies. This text is kept as written for history.
