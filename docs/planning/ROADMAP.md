# Roadmap

Phases end on **exit criteria**, not on dates. Time estimates assume one developer working part-time with AI agents.

| Phase | Name | Goal | Exit criteria | Est. |
|---|---|---|---|---|
| **P0** | Foundations | Repo, CI/CD, contracts, decisions | All P0-blocking questions answered. ADRs 0001–0008 accepted or amended. CI green on a hello-world sim and overlay. Branch protection and security scanning live. | 1–2 wk |
| **P1** | Sim kernel (headless) | A deterministic war that plays itself | Golden replay + cross-process determinism in CI. 1,000 entities at p99 < 25 ms. Balance harness runs the 0/5/50/150/300/500 simulated-viewer crowd profiles plus the adversarial profiles (Q-ALN-42). A campaign ends with victory or defeat in 24–72 h simulated in ≥85% of 50 seeds, and every target in TESTING-STRATEGY §3.5a passes. Measured replay size. | 3–5 wk |
| **P2** | Closed alpha (Twitch, unlisted) | Real chat, real stream, real ops | Twitch adapter + moderation + generated callsigns. Overlay meets OV-1…OV-10. Watchdog + alerts + admin kill switch. **A multi-day unattended run with minimal manual fixes.** A few cold testers read the stream in 5 s and spawn within 30 s. **Monitoring live, plus a viewer simulator (scripted bot operators driving real chat-shaped commands into the internal command queue; never on the public channel, Q-LEGAL-7) used for extended testing during viewer droughts.** Zero unmoderated text on stream. | 4–6 wk |
| **P3** | Public beta | Persistence, progression, 2nd platform | SQLite profiles + XP + ranks O-1…O-3 (shown with themed display names, Q-NAME-1). YouTube via streamList within quota (<70% used). OAuth link portal (DAST clean). TTS sitreps + night mode. Clip review queue. **Sea domain + naval graph** (pulled forward, Q-GD-8). **9:16 vertical output** (OV-11, NX-180b; after the alpha per decision 5 in OPEN-QUESTIONS). **Command Center with RBAC v1** (roles, moderation, rules editor with hot-reload). (The separate public site, Q-ARCH-7, gets its phasing in its own spec; hosting is a static export pushed from the broadcast host, Q-ARCH-16.) Metrics: median session ≥ 12 min, ≥ 20% of viewers command, ≥ X% of first-time commanders issue a 2nd command (FB-UX-6). | 6–8 wk |
| **P4** | Depth | Doctrines, packages, specialists, LLM flavor | Ranks to O-6, doctrines, packages, specialist chassis, Hold the Line mode. **Procedural theater generation (admin-triggered), campaign scheduling, campaign carry-over, Game Master takeover, Discord admin parity, support/donation redemptions (pending research).** LLM advisor + narrator + `!order` within budget, with fallbacks tested. | 8+ wk |
| **P5** | Scale & expansion | Only when metrics justify it | Triggered by SYSTEM-DESIGN §7: Postgres, service split, public-site replay viewer (Q-PROD-7) and scale-out, Discord, Kick, global map, Three.js PiP, premium voices, TikTok (only per ADR-0008). | — |

## Milestone gates
Each phase ends with:
1. A demo, recorded for the devlog.
2. A security review of the phase diff (`security-review`).
3. A retro, with updates to the specs and to OPEN-QUESTIONS.
4. A go/no-go decision recorded in `docs/planning/decisions/PHASE-Pn.md`.
5. An entertainment review for the four audiences (watcher, player, site watcher, VOD and clip watcher), per [ENTERTAINMENT-REVIEW](../quality/ENTERTAINMENT-REVIEW.md) (Q-DEV-22). Also run at major checkpoints.
