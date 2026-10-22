# Broadcast Hardware

Status: Draft · Q-OPS-1 · Facts verified 2026-10-17 (server row 2026-10-22) unless marked [UNVERIFIED]

## Owner's current PC (as reported by the owner, 2026-10-17)
| Item | Value | Source |
|---|---|---|
| GPU | NVIDIA **GTX 1070** (Pascal), 8 GB. *Corrected 2026-10-17: first recorded as a GTX 1080.* | Owner |
| RAM | 32 GB | Owner |
| CPU | Intel Core i7-8700 (6 cores / 12 threads, non-K) | Owner, confirmed 2026-10-17 |
| Upload | ~15–25 Mbps (owner estimate; **measure it**) | Owner |
| OS | **Windows** (owner, 2026-10-17). Docker installed (needs update). Plan: Docker Desktop on WSL2 for the app stack; OBS native on Windows. **No dual boot**: it would break 24/7 operation, and Windows is needed for gaming. | Owner |
| Can run 24/7 | Yes (owner, 2026-10-17). It's also the gaming PC. | Owner |

## Other owner hardware
| Machine | Specs | Role today | Source |
|---|---|---|---|
| Linux home server ("abberhub") | **AMD A10-6700 APU** (4 threads, 1.8–3.7 GHz; AVX but no AVX2). Corrected 2026-10-22: first recorded as an Intel i5. **7.0 GiB usable RAM** (likely 8 GB installed) + 2 GiB swap. **Ubuntu 18.04.6 LTS, 32-bit (i686) install** on a 64-bit-capable CPU (`lm` flag). Disk and motherboard: still needed. Runs 24/7 on the LAN | Existing home server | Owner's `free -h`, `lscpu`, `lsb_release -a` output, 2026-10-22 |
| Steam Deck | Owned; specs not recorded | None yet | Owner, 2026-10-22 |
| Raspberry Pi 3 Model B+ | Owned. USB, Ethernet, HDMI and camera ports. RAM and network speed not measured (1 GB RAM per the published spec [UNVERIFIED here]) | None yet | Owner, 2026-10-22 |

### Linux server: the 32-bit install blocks the plan
`lscpu` reports `Architecture: i686`, so the running OS is 32-bit even though the CPU is 64-bit. This matters:
- Docker Engine publishes packages for 64-bit architectures only, so the staging stack, watchdog and backups (all planned as containers, ADR-0012) can't run on this install as it stands [UNVERIFIED: re-check Docker's install page before acting].
- Ubuntu shipped no 32-bit desktop or server installer after 18.04, so `do-release-upgrade` can't lead to a 64-bit system. The move to a current LTS (Q-ARCH-8) has to be a **fresh 64-bit (amd64) install**; back up anything on the server first.
- About 7 GiB of RAM covers the watchdog, monitoring and backups. A full staging stack may want more (see the note below).

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

## Still needed from the owner
- [x] CPU: i7-8700
- [x] Gaming PC OS: Windows
- [x] Linux server: CPU (AMD A10-6700), RAM (7.0 GiB usable), distro (Ubuntu 18.04.6, 32-bit), reported 2026-10-22
- [ ] Linux server: disk (`lsblk -o NAME,SIZE,TYPE,ROTA,MODEL` and `df -h`), motherboard and max RAM (`sudo dmidecode -t baseboard`, `sudo dmidecode -t memory`)

Note: 8 GB is enough for the watchdog, monitoring and backups. Staging the full stack is likely to want 16 GB [ESTIMATE; confirm once the app exists].
- [ ] Measured upload (e.g., three speed tests at different times)
- [x] Monthly cost ceiling (Q-OPS-3: $75–100/month total, decided 2026-10-17)
