# Broadcast Hardware

Status: Draft · Q-OPS-1 · Facts verified 2026-10-17 unless marked [UNVERIFIED]

## Owner's current PC (as reported by the owner, 2026-10-17)
| Item | Value | Source |
|---|---|---|
| GPU | NVIDIA GTX 1080 (Pascal), 8 GB | Owner |
| RAM | 32 GB | Owner |
| CPU | — (not yet reported) | — |
| Upload | ~15–25 Mbps (owner estimate; **measure it**) | Owner |
| OS | — (not yet reported) | — |

## What the GTX 1080 can and can't do
| Capability | Status | Source |
|---|---|---|
| NVENC H.264 encode incl. B-frames | Yes | NVIDIA support matrix (via search summary); forums |
| NVENC HEVC | Yes, but no HEVC B-frames on Pascal | NVIDIA forums (secondary) |
| AV1 encode | No (Twitch AV1 enhanced broadcasting needs RTX 40) | https://blog.twitch.tv/en/2024/01/08/introducing-the-enhanced-broadcasting-beta |
| Concurrent NVENC sessions (consumer) | 8 on current drivers; exact driver version [UNVERIFIED] | https://developer.nvidia.com/video-encode-and-decode-gpu-support-matrix-new (via search) |
| Twitch Enhanced Broadcasting | Supported on GTX 900+ with OBS ≥ 30.2 | https://www.club386.com/radeon-gpus-finally-support-twitch-enhanced-broadcasting |
| Board power | 180 W rated | https://www.techpowerup.com/gpudb/2870/geforce-gtx-1080 |
| System idle draw | ~99–104 W measured by reviewers (their systems, not yours) | legitreviews / techpowerup forums |
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
- **No local LLM.** 8 GB VRAM shared with OBS and Chromium is not enough for a meaningful model, which fits ADR-0007 and Q-ARCH-4.
- **Clip rendering** competes with the live encode. Run it at low priority or outside peak hours.
- **24/7 on your daily PC is the main risk.** Gaming, updates, and reboots will interrupt the stream, and it draws power constantly. Options:
  1. **Alpha on your PC**, streaming only when you choose. Recommended start.
  2. **A dedicated used box** later. Any NVENC-capable GPU (GTX 16-series/RTX for better NVENC), 16–32 GB RAM, wired Ethernet, on a UPS.
  3. Cloud GPU (cost [UNVERIFIED] for 2026; get quotes before deciding).

## Still needed from the owner
- [ ] CPU model, OS (Windows/Linux), and whether the PC can run 24/7
- [ ] Measured upload (e.g., three speed tests at different times)
- [ ] Monthly cost ceiling (Q-OPS-3)
