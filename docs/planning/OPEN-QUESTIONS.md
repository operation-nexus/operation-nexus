# Open Questions & Decision Log

Every question has a **recommendation**. Recommendations are **never applied automatically**. Work that a question blocks waits for the owner's decision (DATA-INTEGRITY policy: no silent defaults). Answer inline by editing the **Decision** column, or reply in the PR or chat. Once decided, the answer moves into the relevant spec or ADR and the row is marked ✅.

Legend: **Blocks** is the earliest roadmap phase that needs the answer (P0 = Foundations, P1 = Sim kernel, P2 = Closed alpha, P3 = Public beta, P4 = Depth, P5 = Scale).

## Product & scope

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROD-1 | What is the #1 goal for year one: fun hobby/devlog content, audience growth, or revenue? It drives how much ops rigor and cost is justified. | Audience growth + devlog content. Revenue is a bonus. | P0 | |
| Q-PROD-2 | Which platform launches first? | **Twitch only** through closed alpha. YouTube in beta. Kick optional. TikTok deferred. | P0 | |
| Q-PROD-3 | Will you be present on stream sometimes, or is it fully unattended? (This affects TikTok/YouTube policy risk and moderation.) | Unattended by default, plus scheduled "commander's briefing" sessions with you live weekly. | P2 | |
| Q-PROD-4 | What is the success metric for closed alpha? | ≥5 cold testers can say who's winning within 5 s and spawn within 30 s. 7 days unattended with ≤1 manual fix. | P2 | |
| Q-PROD-5 | Public name and branding? "Operation Nexus" is fine. Avoid "NORAD" and real-org insignia. | Fictional factions, "Operation Nexus" | P2 | |

## Game design

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-GD-1 | Which campaign modes ship first? | **Total Domination** first. Defense mode second. | P1 | |
| Q-GD-2 | "Hold the Line": do **players** defend against AI waves (plans), or must the **AI** hold out for X hours while players attack (your conversation)? | Ship *players defend* as "Hold the Line". Add your *AI holds out* idea as a separate mode, "Siege", in the backlog. | P4 | ✅ 2026-10-17: Players defend first; Siege later |
| Q-GD-3 | Doctrine/specialization: base roles open to all, with specialist perks locked per campaign? | Yes. Anyone can `!join` any base role. A **specialist doctrine** (perks + one signature ability) is picked once per campaign and locked until the next campaign. | P4 | |
| Q-GD-4 | What happens with 0 human players? | "Slow war": the AI garrison holds. Enemy progress is capped (≤1 node / 6 h). The campaign clock pauses below 1 active human. | P1 | |
| Q-GD-5 | Campaign length? | 48 h target. Ends early on decisive victory or defeat. Rotating 15-minute theater objective. | P1 | |
| Q-GD-6 | Hard cap on live viewer units? What happens above it? | Cap 300 (configurable). Above the cap, viewers join a **reserve queue** with an on-screen counter, or get auto-merged into flights. | P2 | |
| Q-GD-7 | Defeat condition? | Coalition loses its forward airbase + ≥75% of nodes for 30 min. The sanctuary base can never be captured. | P1 | |
| Q-GD-8 | Domains in the MVP: Air + Ground logistics only, or also Sea? | **Air + Ground** in the MVP. Sea in phase P4. A strait map works without naval units at first. | P1 | |
| Q-GD-9 | Map: hand-authored theater or procedural? | Hand-authored first theater (≈15 nodes) for tunability. Procedural later. | P1 | |
| Q-GD-10 | Do NPC "rival commanders" or NPC aces exist in the MVP? | One NPC wingman type fills empty package slots. Named NPC personalities come later. | P4 | |

## Progression & identity

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROG-1 | Are ranks lifetime and Campaign Merit per-war (both tracks)? | Yes, both tracks. | P3 | |
| Q-PROG-2 | XP sources? | Mission completion, supply delivered, captures, recon assists ≥ kills. Hourly diminishing returns. | P3 | |
| Q-PROG-3 | Minimum account age or activity before persistent XP? | Persistent XP starts after the first completed mission. Accounts under 24 h old count at 0.5× toward director power. | P3 | |
| Q-PROG-4 | Account merge rule? | **Never sum XP.** Keep the max of each stat. One merge per 30 days. OAuth-proven only. | P3 | |
| Q-PROG-5 | Is cross-platform linking needed at launch? | No. Launch on Twitch only. Linking arrives with YouTube in beta. | P3 | |

## Moderation & safety

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-MOD-1 | Do raw platform display names appear on stream? | **No.** Everyone gets a generated callsign (`VIPER-27`). Custom callsigns unlock at O-2 and pass moderation. | P2 | |
| Q-MOD-2 | Which moderation list or classifier? | An open denylist with leetspeak/homoglyph folding, plus a small hosted moderation API for custom callsigns only. | P2 | |
| Q-MOD-3 | Who moderates? Just you? Trusted viewer mods? | You + Twitch mods. Bans issued via Twitch carry over to the game automatically. | P2 | |
| Q-MOD-4 | Will user-created voices ever exist? | Not without a consent policy and an ADR. Preset voices only. | P4 | |

## AI / LLM / TTS

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-AI-1 | Does an LLM *decide* enemy moves? | **No.** A rule-based director decides. An optional LLM *advisor* picks among valid rule options and writes flavor text. All LLM outputs are recorded. | P1 | |
| Q-AI-2 | When does the natural-language `!order` ship? | Phase P4, own unit only, 1 per minute per user, with a budget cap. | P4 | |
| Q-AI-3 | Which LLM provider? Use LiteLLM? | Call one provider's SDK directly behind our own small interface. Avoid LiteLLM given the March 2026 compromise, unless it's hash-pinned and isolated. | P4 | |
| Q-AI-4 | TTS engine for the MVP? | **Piper** (piper1-gpl, run as a separate process. GPL is fine for server-side use) **or Kokoro** (Apache-2.0, pending verification). Pick after a 1-day listening test. | P2 | |
| Q-AI-5 | Monthly LLM + TTS budget? | $20/month hard cap with a circuit breaker. | P4 | |

## Architecture

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-ARCH-1 | Modular monolith vs microservices? | **Modular monolith** (ADR-0001). | P0 | |
| Q-ARCH-2 | Database? | SQLite (WAL) in P1–P2. Move to Postgres when a second writer process appears (ADR-0003). | P1 | |
| Q-ARCH-3 | Languages: Python sim + TypeScript overlay? | Yes. (Revisit if the sim tick exceeds its budget at target scale. NumPy first, then Rust via PyO3 for hot loops.) | P0 | |
| Q-ARCH-4 | Local LLM on the broadcast machine? | **No.** Use a hosted flash-tier model or a separate machine. | P4 | |
| Q-ARCH-5 | Renderer: Canvas2D or Pixi.js? | Canvas2D with layered canvases first. Pixi if profiling shows >8 ms/frame (ADR-0005). | P2 | |

## Operations & hosting

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-OPS-1 | Where does the 24/7 stream run? Your PC, a dedicated home box, or a cloud GPU? What hardware do you have? (GPU model, RAM, upload bandwidth) | See [`docs/ops/HARDWARE.md`](../ops/HARDWARE.md) | P2 | Partial 2026-10-17: owner PC has a GTX 1080, 32 GB RAM, and ~15–25 Mbps upload (owner estimate; to be measured). Upgrade possible. Dedicated vs shared box still open. |
| Q-OPS-2 | Staging: same host, separate compose project, or a cheap VPS? | Same host, separate project, streaming to an unlisted test channel. | P2 | |
| Q-OPS-3 | Monthly cost ceiling (power + APIs + hosting)? | $75/month. | P2 | |
| Q-OPS-4 | Alerts go where? (Discord webhook, phone push, email) | Discord webhook + phone push via ntfy. | P2 | |
| Q-OPS-5 | Uptime target? | 99% monthly. Automatic recovery in under 2 min. | P2 | |

## CI/CD & repo

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-CI-1 | Is the repo public or private? (This affects runner security, CodeQL cost, and secret exposure.) | **Stay public.** On a free account, the following are free on public repos only: CodeQL, secret scanning and push protection, the dependency-review action, private vulnerability reporting, unlimited Actions minutes, and (critically) **rulesets/branch protection and environment required reviewers**. Private repos on the Free plan don't get rulesets or required reviewers at all. Sources: docs.github.com rulesets and environments pages; github.blog 2025-03-04 changelog. | P0 | ✅ 2026-10-17: Owner has no preference. Staying **public** per recommendation. |
| Q-CI-2 | Code license? | Keep the existing MIT for code. Assets (art, audio, voices) are licensed separately. | P0 | |
| Q-CI-3 | As a solo dev, who approves PRs? | You approve. An AI reviewer (code-review + security-review) posts a required review comment. Allow self-merge after the checks pass. | P0 | |
| Q-CI-5 | Add SonarQube? | Not yet. SonarQube Cloud is free for public repos [2024 terms; current terms UNVERIFIED]. Its security rules overlap CodeQL + Semgrep, and its extra value (code smells, duplication, coverage gates) matters once there's real code. Revisit at P2 (NX-047). | P2 | |
| Q-CI-4 | Dependabot or Renovate? | Dependabot (built-in), grouped weekly. | P0 | |

## Legal & business

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-LEGAL-1 | Allowed dependency licenses? | MIT, BSD, Apache-2.0, ISC, MPL-2.0. GPL only for separate server-side processes (e.g., Piper). | P0 | |
| Q-LEGAL-2 | Music source? | Royalty-free or commissioned stems with written licenses. No "sound-alike" tracks. | P2 | |
| Q-LEGAL-3 | Data retention and privacy notice? | As in THREAT-MODEL SEC-DATA-4. Privacy notice published before beta. | P3 | |
| Q-BIZ-1 | Monetization? | Cosmetic-only (halos, trails, voice presets) via channel points or bits. **Never** gameplay power. | P4 | |

## Questions from your conversation that need your words

1. You said the Threat Director "learns" when players attack its stockpiles. How visible should that learning be? (Default: a sitrep line, e.g. "Enemy has reinforced convoy escorts on Route 4.")
2. Should a viewer ever be able to see *why* the AI did something? (Default: yes, through a short "INTEL ASSESSMENT" panel. It builds trust that the AI isn't cheating.)
3. The global map / multi-campaign theater is in the backlog. Do campaigns carry consequences into the next one? (Default: no in v1. Cosmetic history only.)
4. Discord: is it part of the MVP or later? (Default: later. Use the Twitch-only alpha first.)
5. Vertical 9:16 output: is it part of the MVP? (Default: no. It doubles encode load. Add it in beta.)
