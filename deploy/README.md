# deploy/

Compose files, host provisioning, deploy and rollback scripts, and runbooks (docs/cicd/CICD-ARCHITECTURE.md §6, ADR-0006). Contents arrive with NX-014 and NX-255.

- `server/`: scripts and systemd units that run on the Linux server `hiveplex-linux` (Discord alert helper and the 5-minute health check). Copy them to `/usr/local/bin` and `/etc/systemd/system`; see `docs/ops/SERVER-SETUP.md`. No secrets are stored here.
- `server/monitoring/`, `server/prometheus.yml`, `server/hiveplex-kasa-exporter*`: the Prometheus + Grafana + Kasa plug monitoring on the Linux server (docs/ops/SERVER-SETUP.md, "Monitoring").
- `pc/`: the heartbeat the harness PC (WSL) sends to the server every 2 minutes over a restricted SSH key. Install under `~/.local/bin` and `~/.config/systemd/user`; see `docs/ops/SERVER-SETUP.md`.
