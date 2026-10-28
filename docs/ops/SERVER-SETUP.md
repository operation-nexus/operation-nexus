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

What it checks and when it speaks: see MONITORING-WATCHDOG, "Implemented so far". Alerts that cannot be sent are queued in `/var/lib/hiveplex-health/outbox` and delivered late. The test switch is a file named `simulate-notify-failure` in `/var/lib/hiveplex-health/`; remove it afterwards or no alert will be sent. To test the channel: `sudo hiveplex-notify "test"`. To test a failure path without breaking anything: write `fail` into `/var/lib/hiveplex-health/<check>` and run `sudo systemctl start hiveplex-health.service`; a recovery message follows.

## PC heartbeat (restricted key)
`~/.ssh/authorized_keys` also holds a third key, the PC's heartbeat key, written as `restrict,from="192.168.1.102,100.101.222.98",command="/usr/local/bin/hiveplex-heartbeat-recv" ssh-ed25519 ...`. It can only deliver one line of status to `/var/lib/hiveplex-heartbeat/pc` (letters, digits and a few punctuation characters, 512 bytes at most); any command it asks for is ignored. The PC side lives in `deploy/pc/` and uses the SSH host alias `hiveserver-hb`. Recreate by generating a new key on the PC, adding its public half with those options, and enabling `hiveplex-heartbeat.timer` as a user timer.

| Piece | Where |
|---|---|
| Receiver | `/usr/local/bin/hiveplex-heartbeat-recv`; source `deploy/server/` |
| Maintenance pause | `sudo hiveplex-maintenance MINUTES` or `off`; source `deploy/server/` |
| Sender and timer (on the PC) | `~/.local/bin/hiveplex-heartbeat-send`, `~/.config/systemd/user/hiveplex-heartbeat.{service,timer}`; source `deploy/pc/` |

## Monitoring (Prometheus, Grafana, Kasa plug)
Everything listens on `127.0.0.1` except Grafana, which listens on all addresses; `ufw` allows port 3000 only on `tailscale0` and loopback, so it is reachable from the server itself and over the tailnet, not from the LAN or the internet.

| Piece | Where |
|---|---|
| Prometheus 2.53.5 (Ubuntu package) | `127.0.0.1:9090`; config `/etc/prometheus/prometheus.yml` (source `deploy/server/prometheus.yml`); 30 s scrape; keeps 180 days or 8 GB. The remote-control endpoints (`--web.enable-lifecycle`) are off because anonymous Grafana Viewers can send queries through Grafana; reload the config with `sudo systemctl reload prometheus`. |
| windows_exporter 0.31.9 on the harness PC | Installed with `winget install --id Prometheus.WindowsExporter` (service, port 9182). Windows Firewall rule "Hiveplex windows_exporter (server only)" allows inbound TCP 9182 only from `192.168.1.247` and `100.113.223.88`. Scraped as job `windows` (`192.168.1.102:9182`). To remove: `winget uninstall Prometheus.WindowsExporter` and delete the rule. |
| node exporter, blackbox exporter (Ubuntu packages) | `127.0.0.1:9100`, `127.0.0.1:9115`; arguments in `/etc/default/prometheus-*` |
| Kasa plug exporter | `hiveplex-kasa-exporter.service`, `127.0.0.1:9112`; reads `/etc/hiveplex-kasa.env` (Kasa login, root-only, mode 600, never in git); plug list in the unit (`KASA_PLUGS=server=192.168.1.66,pc=192.168.1.6`; plugs are queried in parallel with an 8 s limit each, so an unreachable plug reports `kasa_up 0` and cannot hang the scrape. The server's plug stopped answering for a while on 2026-10-25, which blanked every power panel before this limit existed; reserving both plugs' addresses on the router would also help); uses the python-kasa tool installed for user `hiveplex` |
| Grafana 13.0.2 (Docker, pinned by digest) | `http://100.113.223.88:3000` (tailnet); compose and dashboard in `/opt/hiveplex/monitoring` (source `deploy/server/monitoring/`); admin password in `/etc/hiveplex-grafana.env` (root-only); data in `/var/lib/hiveplex-grafana`. **Anonymous access is on as read-only Viewer** (for the kiosk screen): it can read dashboards and query the datasource, but not edit or use admin pages (tested: write 403, user list 403). Editing needs the admin login. |

**Prometheus's own pages:** the Ubuntu/Debian package ships without Prometheus's modern web UI, so `http://localhost:9090/targets` and `/graph` only show a notice (they still return HTTP 200, which fooled my first check). The working pages are the classic UI: `http://localhost:9090/classic/targets` (is each exporter up?) and `http://localhost:9090/classic/graph`. They are on the server's loopback, so open them on the server's screen (`hiveplex-kiosk url ...`), not from another machine.

Probes: ping to `1.1.1.1`, `8.8.8.8`, the router (`192.168.1.1`) and the harness PC (`192.168.1.102`), and HTTPS to github.com and discord.com. The detailed dashboard ("Hiveplex: server, network, power and cost") is organised in sections: **Status** (internet, PC, router, GitHub/Discord, plugs, ping), **Power and cost (both machines)** (power now, energy today, cost this month so far, projected cost per month for both machines and each one, and four charts: power stacked by machine, running cost in dollars per hour, the projected monthly cost over time, and the cumulative cost this month), **Harness PC** (CPU, memory, C: disk, uptime, power, energy, network, and CPU speed: the real clock in MHz from windows_exporter's performance counters against the 4,300 MHz all-core turbo of the i7-8700, with the slowest speed seen while busy over 24 h; a busy CPU that holds near 4,300 is not throttling, a dip is. It is not a temperature, because Windows gives no CPU temperature to windows_exporter), **Server** (CPU, load, memory, disk, network, uptime, power) and **Network quality** (ping latency and reachability), plus a notes panel with the rates. The cost rate is a dashboard list set from the owner's bills (see COSTS.md); update it when a new bill arrives. A row under the billing boxes compares the plugs' energy with the latest whole-home bill (share of the bill, idle floor, cost above idle) and charts actual cost this bill period against the projected total; update the hidden `last_bill_kwh` and `last_bill_cost` values with the rate when a new bill arrives. Stat colours: green/orange/red only where a threshold means a fault; power, energy, cost and the PC's CPU are blue. The PC plug feeds a strip with the PC, two screens, a switch, a lamp and a laptop charger. To read the Grafana password: `sudo grep GF_SECURITY_ADMIN_PASSWORD /etc/hiveplex-grafana.env`. Measured after setup (2026-10-25): all 9 Prometheus targets up, all 22 dashboard queries return data, Grafana about 140 MiB, Prometheus about 85 MB.

Both plugs report (the server's at `192.168.1.66`, the harness PC's at `192.168.1.6`, both on the owner's Kasa account; the PC's was installed 2026-10-25). To add another plug: add `name=<plug ip>` to `KASA_PLUGS` in the unit, `systemctl daemon-reload`, restart the exporter. The PC's CPU, memory, disk and network come from windows_exporter; its GPU load is not collected yet.

## Kiosk screen
**How "cost this month so far" is computed (2026-10-26):** the two big-number panels add up the recorded watts since the 1st of the month (`sum_over_time(kasa_power_watts[$__range:1m])`, with the panel's time set to `now/M`) times the chosen rate. This keeps working if a plug restarts and loses a little of its own monthly counter (the PC plug lost 0.011 kWh at its 00:17 restart on 2026-10-26), and short gaps in the recording count as zero. The plugs were installed on 25 Oct, so October is a partial month. The cumulative chart in the detailed dashboard still uses the plugs' own monthly counters, because a chart that climbs through the month needs a window that grows with each point. Prometheus keeps 180 days of data. Not done: a "since the bill date" view (needs the bill date from the owner).

**What it shows (2026-10-25):** a separate big-number dashboard, "Hiveplex at a glance (kiosk)" (`deploy/server/monitoring/dashboards/hiveplex-kiosk.json`), meant to be read from across the room on the server's 16-inch 1920x1200 panel (EDID size 34 x 22 cm), viewed from across a room. Top row (slim): INTERNET, HARNESS PC, POWER PLUGS (green ONLINE/OK or red DOWN) and how long the PC has been up. Below: CPU % of the PC and the server, power in watts of the PC and the server, total power, energy today, cost this month so far and the projected monthly cost (at the marginal rate from COSTS.md). The bottom half is four thick-line charts: CPU % and power for the last 1 hour and the last 24 hours (per-panel relative time). Each machine has one fixed color everywhere (PC blue, Server orange; the power tiles use the same colors), and the power charts draw each machine as its own line plus a white dashed **Total** line (they were stacked at first, which the owner found hard to read). The first layout was too tall for the screen at this zoom and squashed the charts; the whole dashboard now fits 20 grid units. The detailed dashboard ("Hiveplex: server, network, power and cost") is unchanged. Firefox in the kiosk profile is zoomed with `layout.css.devPixelsPerPx = 1.5` (in the profile's `user.js`); change it there and run `hiveplex-kiosk restart` to make everything larger or smaller. Grafana's dashboard provider allows edits from the UI with the admin login (`allowUiUpdates`), so the layout can be tried live; copy the dashboard before editing, because a changed file on disk takes precedence when it is re-provisioned. The DRM card number of the HDMI output changed from `card1` to `card0` after a reboot, so scripts should not hard-code it.

**Quiet window (2026-10-25):** the owner asked for the screen to be off from 01:00 to 06:00. Three user timers do it (`hiveplex-screen-off.timer` at 01:00, `hiveplex-screen-on.timer` at 06:00, and `hiveplex-screen-check.timer`, which runs 3 minutes after the user manager starts and turns the screen off if the desktop came up inside the window), all calling `~/.local/bin/hiveplex-screen-window`. Times are the server's time zone (`America/Toronto`, the same offsets as US Eastern). The kiosk keeps running; only the HDMI output sleeps, and moving the mouse may wake it until 06:00. Source: `deploy/server/kiosk/`. Tested with a fake hour (`HIVEPLEX_FAKE_HOUR=3 hiveplex-screen-window check` turns the screen off, hours outside the window change nothing); the real 01:00 and 06:00 firings have not been observed yet.

**Phone control (server side only):** `/usr/local/bin/hiveplex-kiosk-remote` (source `deploy/server/kiosk/`) is a forced command for a phone's SSH key. It accepts only `kiosk start|stop|restart|status`, `screen on|off|status` and `page glance|detail|targets|site`, and refuses everything else (tested: `rm -rf /`, `page detail; id` and `screen off && echo hacked` all exit 2). The key line to add to `~/.ssh/authorized_keys` is `restrict,from="100.64.0.0/10",command="/usr/local/bin/hiveplex-kiosk-remote" ssh-ed25519 <the phone's public key> iphone` (`from` limits it to Tailscale addresses). **No phone key is installed yet**, and the shortcut itself is not built.

The server's HDMI screen can show the dashboard full screen. It is a Firefox (snap) kiosk run as a user service, `hiveplex-kiosk.service`, with its own profile in `~/snap/firefox/common/hiveplex-kiosk`, controlled over SSH with `hiveplex-kiosk` (source `deploy/server/kiosk/`):

```
ssh hiveserver hiveplex-kiosk start     # show the dashboard on the screen
ssh hiveserver hiveplex-kiosk stop      # close it
ssh hiveserver hiveplex-kiosk status
ssh hiveserver hiveplex-kiosk url       # show the address; `url ADDRESS` switches the screen; `url default` resets
ssh hiveserver hiveplex-kiosk on-boot   # start at every login (no-boot undoes it)
ssh hiveserver hiveplex-kiosk screen off   # put the HDMI output to sleep (the monitor sleeps for no signal); `screen on` wakes it
```

It needs the desktop session (GNOME on Wayland) to be logged in. **GDM auto-login is on for `hiveplex`** (`AutomaticLoginEnable = true` and `AutomaticLogin = hiveplex` in `/etc/gdm3/custom.conf`, backup `custom.conf.bak-hiveplex`), set 2026-10-25 so the desktop comes back by itself after a power cut; it takes effect at the next boot and has not been tested by rebooting. The cost is a console that is logged in and unlocked; the lock screen is also off. GNOME's blanking, dimming, auto-suspend and screen lock were turned off for this user so the screen stays on (`org.gnome.desktop.session idle-delay 0`, `org.gnome.desktop.screensaver lock-enabled false` and `idle-activation-enabled false`, `org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'` and `idle-dim false`). Measured 2026-10-25: the kiosk loads the dashboard (about 100 Grafana requests in 35 s) and `stop` leaves no Firefox process. `screen off` sets GNOME Mutter's `PowerSaveMode` to 3; the kernel then reports the HDMI output's `dpms` as `Off`, and `screen on` returns it to `On`. Whether the monitor itself went dark was not observed.

`unattended-upgrades` is active. Ubuntu holds some updates back ("phased"); those arrive on their own, and `apt list --upgradable` may keep showing them for days. A fixed reboot window is **not set up yet**.

## Rebuilding from scratch (checklist)
1. Install Ubuntu Server 26.04 (64-bit); set a DHCP reservation for the machine on the router.
2. Create user `hiveplex`; add the authorized keys; install the hardening drop-in; enable `ufw` as above.
3. Install Docker from Docker's apt repo, Tailscale from its apt repo (join with a new one-time auth key), then `gh`, `make`, `restic`, Node 22, `uv` and `pnpm`.
4. Log in `gh` as the machine account; clone the three repos.
5. Copy `deploy/server/*` into place, recreate `/etc/hiveplex-alerts.env` with a webhook, enable `hiveplex-health.timer`.

## Known issues
- The one wall-clock test that failed here (issue #358) no longer gates `make check`: NX-421 (PR #366) moved the five wall-clock budget tests behind the `perf` marker. Run them with `make perf`; expect them to be slower than on the reference PC, since this machine is slower.
- One 1 TB disk only: no separate-disk backup yet.
- 6.5 GiB RAM: not yet measured against Prometheus + Grafana + Loki plus staging.

## Not done yet
The PC's plug and Windows exporter, Loki logs, restic backups (local, NAS, Google Drive), self-hosted ntfy, the L3 heartbeat, a reboot window, and UPS monitoring (no UPS yet).
