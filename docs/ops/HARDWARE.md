# Broadcast Hardware

Status: Draft · Q-OPS-1 · Facts verified 2026-10-17 (server row 2026-10-22) unless marked [UNVERIFIED]

## Owner's current PC (as reported by the owner, 2026-10-17)
| Item | Value | Source |
|---|---|---|
| GPU | NVIDIA **GTX 1070** (Pascal), 8 GB. *Corrected 2026-10-17: first recorded as a GTX 1080.* | Owner |
| RAM | 32 GB | Owner |
| CPU | Intel Core i7-8700 (6 cores / 12 threads, non-K) | Owner, confirmed 2026-10-17 |
| Upload | **~34–38 Mbps measured** on the 1 Gbps Ethernet link, 2026-10-23 and 24 (Cloudflare test, 4 parallel streams: 33.7 to 37.7 Mbps over 6 runs, median 36.3; 3-minute sustained uploads: mean 29.3, 34.2 and 39.1 Mbps). Before the owner's upgrade: about 16 to 20 Mbps on a 100 Mbps link (2026-10-23, before 16:37). Details under "Measured network" below. Replaces the earlier ~15–25 Mbps owner estimate | Measured, i7-8700 PC (NX-007) |
| OS | **Windows** (owner, 2026-10-17). Docker installed (needs update). Plan: Docker Desktop on WSL2 for the app stack; OBS native on Windows. **No dual boot**: it would break 24/7 operation, and Windows is needed for gaming. | Owner |
| Can run 24/7 | Yes (owner, 2026-10-17). It's also the gaming PC. | Owner |

## Other owner hardware
| Machine | Specs | Role today | Source |
|---|---|---|---|
| Linux home server (`hiveplex-linux`; was "abberhub") | **AMD A10-6700 APU** (4 threads, 1.8–3.7 GHz; AVX but no AVX2). Corrected 2026-10-22: first recorded as an Intel i5. **8 GB DDR3-1600, one module in slot A1 of 4** (6.5 GiB visible to the 64-bit OS, `MemTotal` 6,773,488 kB, 2026-10-25; it was 7.0 GiB usable on the old 32-bit install). Motherboard ASUS M11BB; firmware reports an 8 GB maximum (SMBIOS figures are often wrong; check the board's spec page before buying RAM). Disk: **1 TB Toshiba DT01ACA100 hard drive** (spinning, `ROTA=1`; the only disk), 12 GB used of 916 GB (2026-10-25). **Ubuntu 26.04.1 LTS, 64-bit (x86_64), kernel 7.0.0, a fresh install by the owner (2026-10-25)**, replacing the 32-bit Ubuntu 18.04.6 (i686). LAN address 192.168.1.247 (DHCP reservation on the router), Tailscale address 100.113.223.88. Docker Engine 29.9.2 installed (see below). Runs 24/7 on the LAN | Existing home server | Owner's `free -h`, `lscpu`, `lsb_release -a`, `lsblk`, `df -h`, `dmidecode` output, 2026-10-22; OS, disk and RAM re-read over SSH 2026-10-25 |
| Steam Deck | Owned; specs not recorded | None yet | Owner, 2026-10-22 |
| Raspberry Pi 3 Model B+ | Owned. USB, Ethernet, HDMI and camera ports. RAM and network speed not measured (1 GB RAM per the published spec [UNVERIFIED here]) | None yet | Owner, 2026-10-22 |
| OneXPlayer handheld | Owned, unused; model and specs not recorded | None yet | Owner, 2026-10-22 |
| Apple MacBook (M1) | Owned; RAM and storage not recorded. Owner offers it as a server or "portal" | None yet | Owner, 2026-10-22 |

### Linux server: 64-bit rebuild (resolved 2026-10-25)
The old install was 32-bit (`Architecture: i686`) on a 64-bit-capable CPU. That blocked the plan: Docker Engine publishes packages for 64-bit architectures only, and Ubuntu has no in-place path from a 32-bit install to a 64-bit one. The owner did a fresh 64-bit install on 2026-10-25. Measured since [MEASURED, over SSH, 2026-10-25]:
- **OS:** Ubuntu 26.04.1 LTS, `x86_64`, kernel 7.0.0-38. ADR-0012 and Q-ARCH-8 name Ubuntu 24.04 as the target; the server runs 26.04.1, which Docker's install page lists as supported. The owner should confirm 26.04 is acceptable.
- **Docker:** Docker Engine 29.9.2, Compose v5.6.1 and Buildx v0.38.1 from Docker's official apt repository; `hello-world` ran. Containers that publish a port with `-p` bypass `ufw` (general Docker behaviour [UNVERIFIED here]): bind them to `127.0.0.1` unless the port is meant for the network.
- **Disk:** still one spinning disk. A backup on it is not a "separate disk from the primary" (see the role split); the plan is an external drive, the planned NAS and an encrypted off-site copy (Google Drive).
- **RAM:** 6.5 GiB visible. Whether it carries Prometheus + Grafana + Loki and the staging stack together is **not measured**.
- **Repo checks:** `make bootstrap check` on the server: 1 failed, 2499 passed, 1 skipped, about 13.5 minutes of pytest (the reference PC: about 5 minutes). The one failure is a wall-clock bound in `test_follow_steering_stays_within_budget_at_1000_entities`, not a logic failure (issue #358).
- **Setup, access, firewall, alerts and a restore checklist:** [SERVER-SETUP.md](SERVER-SETUP.md).

## What the GTX 1070 can and can't do
The GTX 1070 is the same Pascal generation as the GTX 1080 first recorded here, so the Pascal NVENC facts below are unchanged by the correction. Only the board-power row is card-specific.

| Capability | Status | Source |
|---|---|---|
| NVENC H.264 encode incl. B-frames | Yes | NVIDIA support matrix (via search summary); forums |
| NVENC HEVC | Yes, but no HEVC B-frames on Pascal | NVIDIA forums (secondary) |
| AV1 encode | No (Twitch AV1 enhanced broadcasting needs RTX 40) | https://blog.twitch.tv/en/2024/01/08/introducing-the-enhanced-broadcasting-beta |
| Concurrent NVENC sessions (consumer) | 8 on current drivers; exact driver version [UNVERIFIED] | https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new (via search) |
| Twitch Enhanced Broadcasting | Supported on GTX 900+ with OBS ≥ 30.2 | https://www.club386.com/radeon-gpus-finally-support-twitch-enhanced-broadcasting |
| Board power | 150 W rated **[UNVERIFIED]** (TechPowerUp's GTX 1070 page could not be fetched from this environment; the 180 W figure previously listed was for the GTX 1080) | — |
| System idle draw | ~99–104 W measured by reviewers on **GTX 1080** systems (their systems, not yours; not re-sourced for the GTX 1070) | legitreviews / techpowerup forums |
| Streaming-load draw | [UNVERIFIED]. Measure with a wall meter. | — |

## Bandwidth budget
| Output | Proposed setting | Bitrate | Source |
|---|---|---|---|
| Twitch 16:9 | 1080p60 H.264 NVENC | ~6,000 kbps | Third-party guides [official page unreachable] |
| Fallback | 720p60 | ~4,500 kbps | same |
| Vertical 9:16 (P3+) | 720×1280 or 1080×1920 @ 30 fps | ~2,500–3,500 kbps | https://obs-versions.com/blog/obs-vertical-streaming-guide |
| **Total** | | **~9–10 Mbps** | Fits within 15 Mbps with headroom, if the measured upload is stable |

Rule: keep total outbound ≤ 70% of the **measured** sustained upload. Measure at the times you'll stream, including evenings.

## Measured network
All numbers were measured from the i7-8700 PC on a 1 Gbps Ethernet link (2026-10-23 16:37 onward, after the owner's network upgrade), from WSL2, with the Cloudflare speed-test endpoint and `speedtest-cli`. Upload is the number that matters for streaming.

| Test | Result |
|---|---|
| Upload, Cloudflare, 4 parallel streams, 20 MB each (6 runs: 10-23 16:40, 16:41, 20:30; 10-24 03:39, 08:30, 13:30) | 33.7, 37.2, 34.0, 37.7, 36.9, 35.7 Mbps (min 33.7, median 36.3, max 37.7) |
| Download, Cloudflare, one 25 MB request (same runs, 5 of 6) | 356 to 401 Mbps |
| Sustained upload, 3 minutes, 4 streams (10-23 16:52, 20:45; 10-24 09:00) | mean 29.3, 34.2 and 39.1 Mbps (660, 770 and 880 MB) |
| `speedtest-cli` upload, two nearby servers per run | 13.1 to 50.5 Mbps (10 runs); the server list is geolocated from the IP and changed between runs (Illinois/Iowa, Ottawa, Tennessee/Kentucky, Guelph; once Brazil), so treat it as less stable than the Cloudflare figure |
| Before the upgrade (100 Mbps Ethernet link, 2026-10-23 11:25 to 12:17) | upload 15.6 to 20.1 Mbps, plus one 32.5 Mbps Cloudflare single-stream reading; one 1.5 Mbps outlier with an unknown server |

Latency to 1.1.1.1 while uploading (idle: about 26 to 28 ms, 0% loss):

| Upload load | Average ping | Max ping | Packet loss |
|---|---|---|---|
| Paced 10 Mbps (3 runs) | 34.4 to 37.4 ms | 117 to 199 ms | 0% |
| Paced 20 Mbps (1 run) | 81.0 ms | 259 ms | 0% |
| Saturated, 3 minutes (3 runs) | 103, 191 and 284 ms | 237, 765 and 513 ms | 0%, 0.28% (20:45 run), 0% |

Reading, not a rule: latency rises sharply as upload fills the line (consistent with queueing in the router or modem, which was not checked **[UNVERIFIED]**). At the proposed ~9 to 10 Mbps total the added latency was small in these runs. The 70% rule above, applied to a sustained 29 to 39 Mbps, allows about 20 to 27 Mbps, where the 20 Mbps run already showed about 55 ms of extra average latency.

Not measured: tests over Wi-Fi, tests during an actual stream, and runs on other days of the week. Raw rows: `upload-tests.csv`, `sustained-uploads.csv`, `paced-uploads.csv`, `net-baseline.csv` on the PC under `~/nexus-bench/results/`.

## Fit for this project
- **Sufficient for P2 alpha:** one Twitch output, a Canvas2D overlay (light GPU load), the sim (CPU), and a local TTS worker (CPU).
- **Local LLM: experiment only** (Q-ARCH-4, decided 2026-10-17). 8 GB VRAM shared with OBS and Chromium only fits small (~7–8B) models, so nothing depends on it. A free narration-first experiment on the GTX 1070 is approved; it is gated by the quality benchmark (NX-292) and auto-disabled if stream quality suffers (ADR-0007, LOCAL-VS-API-COST R2).
- **Clip rendering** competes with the live encode. Run it at low priority or outside peak hours.
- **24/7 on your daily PC is the main risk.** Gaming, updates, and reboots will interrupt the stream, and it draws power constantly. Options:
  1. **Alpha on your PC**, streaming only when you choose. Recommended start.
  2. **A dedicated used box** later. Any NVENC-capable GPU (GTX 16-series/RTX for better NVENC), 16–32 GB RAM, wired Ethernet, on a UPS.
  3. Cloud GPU (cost [UNVERIFIED] for 2026; get quotes before deciding).

## Role split (owner decisions Q-OPS-2, Q-ARCH-11, Q-ARCH-15; topology in [ADR-0012](../architecture/adr/0012-deployment-topology.md))
| Role | Machine | Why |
|---|---|---|
| OBS + overlay browser + encode | Gaming PC (GTX 1070) | Needs NVENC and a GPU for Chromium |
| nexus-app (sim, gateway, SQLite) + TTS | Gaming PC at first, Linux server later | CPU-only work. Moving it off the gaming PC means a game crash or reboot doesn't kill the sim |
| Watchdog / monitoring / alerting | Linux server | Must live on a *different* box to detect that the stream box died |
| Backups target | Linux server (+ offsite) | Separate disk from the primary |
| Staging stack | Linux server | Keeps staging off the broadcast box |
| Replay archive | Linux server | 858 GB free. The NX-345 spike measured about 250 MB of frame stream per game hour at the worst case (Q-SIM-29), so a 72-hour campaign is about 18 GB and the disk holds roughly 47 such campaigns [arithmetic from that figure]. Retention policy is open (Q-SIM-29). |
| Internet and power monitoring, dashboards | Linux server | Internet probes, Kasa EP25 plug readings and CPU/power/cost dashboards (planned; see SERVER-SETUP.md) |
| Alerts | Linux server | Discord webhook from the server (running since 2026-10-25); self-hosted ntfy later |

## Still needed from the owner
- [x] CPU: i7-8700
- [x] Gaming PC OS: Windows
- [x] Linux server: CPU (AMD A10-6700), RAM (7.0 GiB usable), distro (Ubuntu 18.04.6, 32-bit), reported 2026-10-22
- [x] Linux server: disk (1 TB HDD), motherboard (ASUS M11BB), RAM layout (1 × 8 GB, 3 free slots), reported 2026-10-22
- [x] Linux server rebuilt as 64-bit Ubuntu 26.04.1 LTS with Docker, 2026-10-25

Note: 8 GB is enough for the watchdog, monitoring and backups. Staging the full stack is likely to want 16 GB [ESTIMATE; confirm once the app exists].
- [x] Measured upload: six speed-test runs at different times of day and three 3-minute sustained uploads, 2026-10-23 and 24 (see "Measured network")
- [x] Monthly cost ceiling (Q-OPS-3: $75–100/month total, decided 2026-10-17)
