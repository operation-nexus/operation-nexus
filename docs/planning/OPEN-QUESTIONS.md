# Open Questions & Decision Log

Every question has a **recommendation**. Recommendations are **never applied automatically**. Work that a question blocks waits for the owner's decision (DATA-INTEGRITY policy: no silent defaults). Answer inline by editing the **Decision** column, or reply in the PR or chat. Once decided, the answer moves into the relevant spec or ADR and the row is marked ✅.

Legend: **Blocks** is the earliest roadmap phase that needs the answer (P0 = Foundations, P1 = Sim kernel, P2 = Closed alpha, P3 = Public beta, P4 = Depth, P5 = Scale).

## Product & scope

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROD-1 | What is the #1 goal for year one: fun hobby/devlog content, audience growth, or revenue? It drives how much ops rigor and cost is justified. | Audience growth + devlog content. Revenue is a bonus. | ✅ 2026-10-17: Audience growth + devlog content; revenue is a bonus (A) |
| Q-PROD-2 | Which platform launches first? | **Twitch only** through closed alpha. YouTube in beta. Kick optional. TikTok deferred. | ✅ 2026-10-17: Twitch only for alpha, then YouTube (A) |
| Q-PROD-6 | With ADR-0010 (both platforms first-class), do you want Twitch **and** YouTube in the closed alpha (simulcast), or keep Twitch-only alpha → YouTube beta? | Twitch-only alpha, YouTube in beta. The YouTube quota application and monitoring should come first. The code is neutral either way. | ✅ 2026-10-17: Twitch-only alpha, YouTube in beta (A) |
| Q-PROD-3 | Will you be present on stream sometimes, or is it fully unattended? (This affects TikTok/YouTube policy risk and moderation.) | Unattended by default, plus scheduled "commander's briefing" sessions with you live weekly. | ✅ 2026-10-17: A (mostly unattended + weekly live briefing), and seasonally C (frequent live sessions, e.g. campaign launches or season events) |
| Q-PROD-4 | What is the success metric for closed alpha? | ≥5 cold testers can say who's winning within 5 s and spawn within 30 s. 7 days unattended with ≤1 manual fix. | P2 | |
| Q-PROD-5 | Public name and branding? "Operation Nexus" is fine. Avoid "NORAD" and real-org insignia. | Fictional factions, "Operation Nexus" | ✅ 2026-10-17: A, mandatory. **No real names anywhere**: no real countries, militaries, weapon systems or orgs ("NORAD" etc.). Units use generic class names (Tank, Striker, Bomber, Recon, Convoy…). Real-world *types* of platforms may be evoked, but they're clearly fictional and simulated. Needs a unique, memorable brand identity (Q-BRAND-1, NX-274). |

## Game design

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-GD-1 | Which campaign modes ship first? | **Total Domination** first. Defense mode second. | ✅ 2026-10-17: Total Domination first; Hold the Line second; Siege later (A) |
| Q-GD-2 | "Hold the Line": do **players** defend against AI waves (plans), or must the **AI** hold out for X hours while players attack (your conversation)? | Ship *players defend* as "Hold the Line". Add your *AI holds out* idea as a separate mode, "Siege", in the backlog. | P4 | ✅ 2026-10-17: Players defend first; Siege later |
| Q-GD-3 | Doctrine/specialization: base roles open to all, with specialist perks locked per campaign? | Yes. Anyone can `!join` any base role. A **specialist doctrine** (perks + one signature ability) is picked once per campaign and locked until the next campaign. | ✅ 2026-10-17: Base roles open; specialist doctrine locked per campaign (A) |
| Q-GD-4 | What happens with 0 human players? | "Slow war": the AI garrison holds. Enemy progress is capped (≤1 node / 6 h). The campaign clock pauses below 1 active human. | ✅ 2026-10-17, **amended**: the campaign clock does **not** pause for lack of humans, so a 48–72 h war never gets stretched. At 0 humans the enemy drops to **Pattern of Life** (THREAT-DIRECTOR §5a): garrison, supply runs, rotations and repositioning, observable by scouting. Only operator actions escalate it, not headcount. Operators can still pause manually via admin. |
| Q-GD-5 | Campaign length? | 48 h target. Ends early on decisive victory or defeat. Rotating 15-minute theater objective. | ✅ 2026-10-17: 48 h target, early end on decisive result, 15-min objectives (A). Admin-adjustable, can be scheduled per campaign. |
| Q-GD-6 | Hard cap on live viewer units? What happens above it? | Cap 300 (configurable). Above the cap, viewers join a **reserve queue** with an on-screen counter, or get auto-merged into flights. | ✅ 2026-10-17: Cap + visible reserve queue (A), **with mitigations** (GAMEPLAY §4a) |
| Q-GD-7 | Defeat condition? | Coalition loses its forward airbase + ≥75% of nodes for 30 min. The sanctuary base can never be captured. | ✅ 2026-10-17: Defeat = lose forward airbase and hold ≤25% for 30 min; sanctuary uncapturable (A) |
| Q-GD-8 | Domains in the MVP: Air + Ground logistics only, or also Sea? | **Air + Ground** in the MVP. Sea in phase P4. A strait map works without naval units at first. | ✅ 2026-10-17: Air + ground at launch (A); **sea domain sooner than later** (moved to P3 in ROADMAP) since maps are water-heavy |
| Q-GD-9 | Map: hand-authored theater or procedural? | Hand-authored first theater (≈15 nodes) for tunability. Procedural later. | ✅ 2026-10-17: Hand-authored first theater (A); **procedural generation sooner than later** (moved to P3/P4, admin-triggered) |
| Q-GD-11 | Who can repair destroyed bridges? Engineers unlock at O-4 (weeks of play), so a bridge could stay down for a long time. | Logistics trucks can do a slow field repair (e.g. 5× slower). Engineers repair fast and can also build. | ✅ 2026-10-17: Trucks do slow field repair; engineers repair fast and build (A) |
| Q-GD-12 | Campaign carry-over (owner chose: results carry over). What carries? | Proposal: the winner of campaign N gets a modest start advantage in N+1: one extra starting node or starting stock, capped. A losing streak triggers a comeback bonus so the war never becomes hopeless. Theater rotation follows the outcome (e.g., a win pushes the front into the next theater). Keep it bounded and visible on stream. | ✅ 2026-10-17: Winner gets a capped head start + comeback bonus for the loser (as recommended) |
| Q-GD-13 | Map orientation: chat (coalition) on the left, enemy on the right (owner preference). What about the 9:16 vertical layout? | Keep left→right on 16:9. On vertical, rotate so the coalition is at the bottom and the enemy at the top. The overlay's right sidebar sits over enemy rear territory, which is acceptable. | ✅ 2026-10-17: Vertical layout: coalition at the bottom, enemy at the top |
| Q-GD-14 | Reserve-queue priority: pure FIFO, or first-time viewers first? | FIFO, with a small boost for first-time commanders (so newcomers get hooked) and a max wait guarantee. Tune with the harness. | P2 | |
| Q-GD-10 | Do NPC "rival commanders" or NPC aces exist in the MVP? | One NPC wingman type fills empty package slots. Named NPC personalities come later. | ✅ 2026-10-17: One generic AI wingman type, labeled as AI (A) |

## Progression & identity

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROG-1 | Are ranks lifetime and Campaign Merit per-war (both tracks)? | Yes, both tracks. | ✅ 2026-10-17: Lifetime rank + per-war merit (A) |
| Q-PROG-2 | XP sources? | Mission completion, supply delivered, captures, recon assists ≥ kills. Hourly diminishing returns. | ✅ 2026-10-17: Objective/supply/capture/recon ≥ kills; hourly diminishing returns (A) |
| Q-PROG-3 | Minimum account age or activity before persistent XP? | Persistent XP starts after the first completed mission. Accounts under 24 h old count at 0.5× toward director power. | ✅ 2026-10-17: A. Persistent rank counts after the first completed mission; new accounts count 0.5× toward director power for 24 h. **Custom callsign unlocks after the first completed mission** (moderated, 1 change per 30 days), not at O-2. No captcha (owner prefers no verification step). Anti-farming is layered instead (NX-277). |
| Q-PROG-4 | Account merge rule? | **Never sum XP.** Keep the max of each stat. One merge per 30 days. OAuth-proven only. | ✅ 2026-10-17: Never sum XP; per-stat max; OAuth-proven (A) |
| Q-PROG-5 | Is cross-platform linking needed at launch? | No. Launch on Twitch only. Linking arrives with YouTube in beta. | P3 | |

## Moderation & safety

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-MOD-1 | Do raw platform display names appear on stream? | **No.** Everyone gets a generated callsign (`VIPER-27`). Custom callsigns unlock at O-2 and pass moderation. | ✅ 2026-10-17: Generated callsigns; custom at O-2 after moderation (A). **Viewers must clearly see their command worked** (GAMEPLAY §1a). |
| Q-MOD-2 | Which moderation list or classifier? | An open denylist with leetspeak/homoglyph folding, plus a small hosted moderation API for custom callsigns only. | ✅ 2026-10-17: A. Free-first: a blocklist with leetspeak and homoglyph folding, plus a free or local classifier if a good one exists. A cheap hosted moderation check for custom callsigns is allowed when needed (behind a `ModerationProvider` port, ADR-0010). |
| Q-MOD-3 | Who moderates? Just you? Trusted viewer mods? | You + Twitch mods. Bans issued via Twitch carry over to the game automatically. | ✅ 2026-10-17: Owner + Twitch mods; Twitch ban cascades (A). Extended by the ADMIN-RBAC spec (roles via site and Discord). |
| Q-MOD-4 | Will user-created voices ever exist? | Not without a consent policy and an ADR. Preset voices only. | P4 | |

## AI / LLM / TTS

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-AI-1 | Does an LLM *decide* enemy moves? | **No.** A rule-based director decides. An optional LLM *advisor* picks among valid rule options and writes flavor text. All LLM outputs are recorded. | ✅ 2026-10-17: Accepted via ADR-0007: rules decide; LLM advises and narrates only |
| Q-AI-2 | When does the natural-language `!order` ship? | Phase P4, own unit only, 1 per minute per user, with a budget cap. | ✅ 2026-10-17: A, after the core game is established (P4). Build a complete **intent and command catalog** first: the parser maps natural language onto that catalog only. Own unit only, 1/min per user, budget cap. Players get guidance (`!order help`, examples on screen). |
| Q-AI-3 | Which LLM provider? Use LiteLLM? | Call one provider's SDK directly behind our own small interface. Avoid LiteLLM given the March 2026 compromise, unless it's hash-pinned and isolated. | ✅ 2026-10-17: A, official provider SDKs called directly behind our `LlmClient` port (ADR-0010); no LiteLLM. **And regardless of library, all LLM code runs in its own isolated container**: no platform or stream credentials, egress allowlisted to the provider endpoints, read-only filesystem, non-root, resource limits. Revisit standards-based options for agnosticism (e.g. OpenAI-compatible endpoints) only via our own port. |
| Q-AI-4 | TTS engine for the MVP? | **Piper** (piper1-gpl, run as a separate process. GPL is fine for server-side use) **or Kokoro** (Apache-2.0, pending verification). Pick after a 1-day listening test. | ✅ 2026-10-17: A, local Piper or Kokoro picked by a listening test; engines stay interchangeable via the `TtsEngine` port (ADR-0010) so cloud voices can be added later |
| Q-AI-5 | Monthly LLM + TTS budget? (Cost analysis: [LOCAL-VS-API-COST](../ops/LOCAL-VS-API-COST.md)) | $20/month hard cap with a circuit breaker. | ✅ 2026-10-17: A, $20/month hard cap on LLM + cloud TTS, with an automatic cutoff (circuit breaker). Over cap → rules + template lines (FB-2/FB-3). Alert at 80%. |

## Architecture

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-ARCH-1 | Modular monolith vs microservices? | **Modular monolith** (ADR-0001). | ✅ 2026-10-17: Modular monolith (A, ADR-0001 accepted) |
| Q-ARCH-2 | Database? | SQLite (WAL) in P1–P2. Move to Postgres when a second writer process appears (ADR-0003). | ✅ 2026-10-17: Accepted via ADR-0003: SQLite (WAL) now; Postgres when a second writer appears |
| Q-ARCH-3 | Languages: Python sim + TypeScript overlay? | Yes. (Revisit if the sim tick exceeds its budget at target scale. NumPy first, then Rust via PyO3 for hot loops.) | ✅ 2026-10-17: Python sim + TypeScript overlay (A) |
| Q-ARCH-4 | Local LLM on the broadcast machine? (See [LOCAL-VS-API-COST](../ops/LOCAL-VS-API-COST.md) R2: free narration-only experiment on the GTX 1080.) | **No.** Use a hosted flash-tier model or a separate machine. | P4 | |
| Q-ARCH-5 | Renderer: Canvas2D or Pixi.js? | Canvas2D with layered canvases first. Pixi if profiling shows >8 ms/frame (ADR-0005). | ✅ 2026-10-17: Accepted via ADR-0005: Canvas2D first, Pixi only if profiling needs it |

## Operations & hosting

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-OPS-1 | Where does the 24/7 stream run? Your PC, a dedicated home box, or a cloud GPU? What hardware do you have? (GPU model, RAM, upload bandwidth) | See [`docs/ops/HARDWARE.md`](../ops/HARDWARE.md) | P2 | Partial 2026-10-17: owner PC has a GTX 1080, 32 GB RAM, and ~15–25 Mbps upload (owner estimate; to be measured). Upgrade possible. Dedicated vs shared box still open. |
| Q-OPS-2 | Staging: same host, separate compose project, or a cheap VPS? | Same host, separate project, streaming to an unlisted test channel. | ✅ 2026-10-17: A for now (Linux server → unlisted test channel). **Risk:** the server may be too old or weak (RAM 8–16 GB, unknown CPU). Check its feasibility first (NX-007). Fallback: a cheap cloud server, which the owner may adopt later. |
| Q-OPS-3 | Monthly cost ceiling (power + APIs + hosting)? | $75/month. | ✅ 2026-10-17: $75–100/month total (power + AI + hosting) |
| Q-OPS-4 | Alerts go where? (Discord webhook, phone push, email) | Discord webhook + phone push via ntfy. | ✅ 2026-10-17: A (ntfy push + private Discord channel), text-based first |
| Q-OPS-5 | Uptime target? | 99% monthly. Automatic recovery in under 2 min. | ✅ 2026-10-17: A, **lenient**. ~99% monthly is a goal, not a hard SLA. Planned maintenance is excluded, and longer outages are acceptable. Automatic recovery is still the aim (minutes, not hours). |

## CI/CD & repo

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-CI-1 | Is the repo public or private? (This affects runner security, CodeQL cost, and secret exposure.) | **Stay public.** On a free account, the following are free on public repos only: CodeQL, secret scanning and push protection, the dependency-review action, private vulnerability reporting, unlimited Actions minutes, and (critically) **rulesets/branch protection and environment required reviewers**. Private repos on the Free plan don't get rulesets or required reviewers at all. Sources: docs.github.com rulesets and environments pages; github.blog 2025-03-04 changelog. | P0 | ✅ 2026-10-17: Owner has no preference. Staying **public** per recommendation. |
| Q-CI-2 | Code license? | Keep the existing MIT for code. Assets (art, audio, voices) are licensed separately. | ✅ 2026-10-17: Code stays MIT; assets licensed separately (A) |
| Q-CI-3 | As a solo dev, who approves PRs? | No required PR approval count (GitHub ignores self-approval, so it would deadlock). An AI reviewer (code-review + security-review) posts a review comment. Only you can merge to `main`, and production deploys need your approval in the `production` Environment (CICD §2). | ✅ 2026-10-17: AI review comment on every PR; owner-only merge to main; production deploy needs owner approval (A) |
| Q-CI-5 | Add SonarQube? | Not yet. SonarQube Cloud is free for public repos [2024 terms; current terms UNVERIFIED]. Its security rules overlap CodeQL + Semgrep, and its extra value (code smells, duplication, coverage gates) matters once there's real code. Revisit at P2 (NX-047). | P2 | |
| Q-CI-4 | Dependabot or Renovate? | Dependabot (built-in), grouped weekly. | ✅ 2026-10-17: Dependabot, grouped weekly (A) |

## Legal & business

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-LEGAL-1 | Allowed dependency licenses? | MIT, BSD, Apache-2.0, ISC, MPL-2.0. GPL only for separate server-side processes (e.g., Piper). | ✅ 2026-10-17: MIT/BSD/Apache-2.0/ISC/MPL-2.0; GPL only in separate server-side processes (A) |
| Q-LEGAL-2 | Music source? | Royalty-free or commissioned stems with written licenses. No "sound-alike" tracks. | ✅ 2026-10-17: A, licensed music only. Owner has an **Epidemic Sound** subscription. Still to check: whether it covers 24/7 Twitch/YouTube streaming and clips, and whether an API or MCP exists for an AI music agent [UNVERIFIED, research NX-273] |
| Q-LEGAL-3 | Data retention and privacy notice? | As in THREAT-MODEL SEC-DATA-4. Privacy notice published before beta. | ✅ 2026-10-17: A. Raw chat 7 days; command log = campaign + 30 days; aggregates kept; `!forget` deletion; privacy notice published before public beta (SEC-DATA-3/4) |
| Q-BIZ-1 | Monetization? | Cosmetic-only (halos, trails, voice presets) via channel points or bits. **Never** gameplay power. | ✅ 2026-10-17: A, cosmetics and recognition only; never winning power (details: SUPPORT-REDEMPTIONS, Q-SUP-1) |

## From the detailed system specs (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-SM-1 | Give objective selection its own `objective` RNG sub-stream? | Yes. Then changing objective logic doesn't shift director randomness. | P1 | |
| Q-SM-2 | How long does an idle landed unit linger before despawning? | Balance key `slots.idle_despawn_s`, tuned by the harness | ✅ 2026-10-17: A, `slots.idle_despawn_s` starts at about 5 min (PROPOSED), tuned by the harness and adjustable in admin. Owner prefers as long as practical. |
| Q-SM-3 | Custom callsigns: manual owner approval or automated moderation? | Automated moderation + review queue. Manual approval during alpha. | P3 | |
| Q-SM-4 | After the AAR, same theater with a new seed or rotate theaters? | Same hand-authored theater with a new seed until a second theater exists | ✅ 2026-10-17: A, rotate theater archetypes with no back-to-back repeats; reuse the first theater with a new seed until more exist. Admins can override via scheduling (ADMIN-RBAC). |
| Q-SM-5 | How long with no active humans before the campaign clock pauses? | Balance key `campaign.pause_after_no_humans_s`, tuned by the harness | ✅ 2026-10-17: Superseded. There's no automatic clock pause (Q-GD-4 amended). `campaign.pause_after_no_humans_s` is removed; Pattern-of-Life keys replace it (THREAT-DIRECTOR §5a). |
| Q-CT-1 | Chat over the length cap: reject or truncate? | Reject. Truncation could turn it into a different valid command. | P2 | |
| Q-CT-2 | Is the campaign seed public? | Hidden during the campaign, published after `CampaignEnded` | ✅ 2026-10-17: A. Hidden during the campaign. After `CampaignEnded`, publish the seed and a **"what you didn't see" recap** (summary and/or narrative) that labels every enemy decision as made by the **AI rules, the LLM advisor, or a human Game Master**. |
| Q-CT-3 | Show tracers from enemy shooters we can't see? | No for MVP. Revisit after the readability study (NX-034). | ✅ 2026-10-17: A, no tracers from hidden shooters (impact shown as "unknown contact"). **Playtest note:** revisit in the readability study (NX-034). |
| Q-CT-4 | Show an "active humans" count on stream? | Yes. Humans only; shows `—` until known. | ✅ 2026-10-17: A, "Operators active" shows humans only, and `—` when unknown. **Plus a breakdown** by role or doctrine (e.g. Strike 5 · Recon 2 · Logistics 4) and optionally by rank band. It goes in the Campaign Status rotating panel, from the PresenceSnapshot event. |
| Q-CT-5 | MVP enemy/garrison unit roster (garrison AAA and infantry; enemy SAM site, radar, fighter, armor, convoy)? | Confirm once the first theater sketch exists (NX-008) | ✅ 2026-10-17: A, small MVP set (SAM, radar, armor, convoy + garrison), confirmed at the theater sketch. New platforms come through the **hot-loadable unit content pipeline** (CONFIG-AND-CONTENT §7a). |
| Q-DM-1 | Archive old XP ledger rows yearly, keeping derived stats? | Yes, once the ledger passes about 1 GB (size is an ESTIMATE; measure it) | ✅ 2026-10-17: A, archive ledger rows older than 12 months into compressed yearly files once the ledger is large (~1 GB, measured); derived totals stay live |
| Q-DM-2 | Access control on the public replay viewer? | Not for v1. Replays are pseudonymous, and deleted users show `REDACTED-…`. | ✅ 2026-10-17: A, public replays without login. Player login (own stats, personal highlights) comes later. |
| Q-ARCH-6 | Accept the ADR-0003 amendment: XP and merit become append-only, idempotent ledgers (source of truth) with `commander_stats` derived in the same transaction, replacing `UPDATE … SET xp = xp + ?`? | Accept. Prevents double-counting after crash replay and gives an audit trail. | ✅ 2026-10-17: Accepted: XP/merit are append-only ledgers (ADR-0003 amendment) |
| Q-OPS-6 | Off-site backup destination? | S3-compatible object storage, `age`-encrypted before upload. Provider and price [UNVERIFIED]. | ✅ 2026-10-17: A, **local copy on the Linux server + encrypted off-site copy**. The owner already has **Google Drive**; other free or cheap providers may be used. Use a `BackupTarget` port (ADR-0010) so providers are swappable. Backups are `age`-encrypted before upload. Tier the data: the DB and snapshots back up nightly; large replay/telemetry archives are compressed and kept with their own retention. Quarterly restore test. Provider limits and pricing are [UNVERIFIED]; check them before setup (NX-285). |
| Q-CFG-1 | Balance profiles and mid-campaign changes? | `balance/<profile>.yaml`. Only hot-reloadable keys change mid-campaign; a full profile switch needs a new campaign. | P1 | |
| Q-CFG-2 | Can rank thresholds change after launch? | Only with a migration plan. Never revoke ranks; new thresholds apply to future promotions only. | P3 | |
| Q-CFG-3 | Terrain authoring for the first theater? | 16-bit heightmap PNG → derived contours, plus masking polygons | P1 | |
| Q-CFG-4 | Callsign word-list size? | Start around 200 words (≈19.8k callsigns). Final target = 2× measured 90-day peak of distinct commanders. | ✅ 2026-10-17: A, about 200 theme-fitting words to start. **Owner idea:** word pools themed **per role** (e.g. strike words like VIPER, recon words like ECHO), and **flight numbering** when operators fly together (e.g. "VIPER 1-2" = flight VIPER, member 2). The flight designation is a display label only; the personal callsign stays the stable identity. |
| Q-CFG-5 | A sitrep slot has no value: skip or fallback template? | Fallback template if one exists (logged as FB-3); otherwise skip. Never placeholder text. | ✅ 2026-10-17: A, fallback template (sector-level wording, e.g. "Contact reported in NORTH sector"), logged as FB-3; otherwise skip. Never invented text. |
| Q-CFG-6 | Night-mode hours and time zone? | Owner decides. Proposal: 00:00–07:00 owner local time, configurable. | ✅ 2026-10-17: Night mode 00:00–08:00 **America/New_York** (owner: Eastern; adjustable in admin). Softer music, fewer voice lines, no loud sounds. Times are stored with an explicit IANA time zone, not UTC offsets, so DST is handled. |
| Q-CFG-7 | Fuel for ground units in the MVP? | No. Air only (`fuel_s: null` for ground and static units). | ✅ 2026-10-17: A for launch (air-only fuel). **Playtest variant (NX-280):** all domains use fuel; ground and sea get much larger tanks and burn slower; running dry means crawling at a very low speed (any domain) instead of being destroyed. Compare in the balance harness. |

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-RB-1 | Can moderators pause campaigns? | Yes, they can pause. Resuming needs a GM or admin. | ✅ 2026-10-17: A, moderators can pause, but only with a **required reason** (category + short note). Resume: GM/admin/owner. Every pause **immediately alerts the owner** (who, when, why). Optional AI assessment ("situation report: should we stay paused?") is attached. One-tap resume from phone/Discord, voice later (ADMIN-RBAC §pause flow, NX-286). |
| Q-RB-2 | Does a platform-scoped moderator's ban cascade across the commander's linked platforms? | Yes. Unbanning needs an admin. | ✅ 2026-10-17: A, bans cascade across all linked platforms; unban requires an admin |
| Q-RB-3 | Two-person rule with a single owner? | Allow self-approval with an audit flag, plus a delay (PROPOSED 10 min) on campaign end and rules publish | ✅ 2026-10-17: A, self-approval allowed while solo, audit-flagged, with a cancellable safety delay (~10 min, PROPOSED) on campaign end and rules publish. Second-person approval once more admins exist. |
| Q-RB-4 | Is the admin console exposed publicly? | No. Tailnet + Discord only through P3. A DAST pass is required before any public exposure. | ✅ 2026-10-17: Implied by Q-ARCH-7: the Command Center is private (tailnet + Discord); DAST before any public exposure |
| Q-RB-5 | Is a harness dry-run mandatory before publishing rules? | Mandatory for next-campaign publishes. Optional for hot keys, and a skip is flagged in the audit log. | ✅ 2026-10-17: A, harness dry-run mandatory for next-campaign publishes; optional for hot keys, and a skip is audit-flagged |
| Q-RB-6 | Does threat memory keep learning during a GM FULL takeover? | Yes | ✅ 2026-10-17: A, threat memory keeps learning during GM FULL takeover |
| Q-RB-7 | Do GM sitreps get a distinct TTS voice? | Yes, a different preset with the same radio filter | ✅ 2026-10-17: Implied by the voice cast (AUDIO-TTS §2a): Game Master has its own voice profile |
| Q-SUP-1 | Can **money** (Bits, Super Chat, tips) buy QoL perks such as a respawn skip or a queue jump, or only cosmetics and shoutouts? Channel points can buy capped QoL either way. | Money buys cosmetics, shoutouts and spectacle only. QoL is channel points only. That avoids "pay to win" perception. | ✅ 2026-10-17: Money buys cosmetics, shoutouts and spectacle only; QoL via channel points only |
| Q-SUP-2 | Show donor messages on stream? | Not in v1. Callsign-only shoutouts. Messages may come later behind moderation, and are never spoken by TTS. | ✅ 2026-10-17: No free-text donor messages in v1. **Owner idea:** templated "rally call" instead (Q-SUP-6) |
| Q-SUP-3 | Third-party tips (Ko-fi, Streamlabs, StreamElements)? | Later (P5), pick one. Start with platform-native support. | ✅ 2026-10-17: A, platform-native support first; one third-party tip service later (P5) |
| Q-SUP-4 | Confirm ADR-0011: no in-game currency in v1? | Yes. Direct capped redemptions; revisit later via a new ADR plus legal review. | ✅ 2026-10-17: No in-game currency in v1 (ADR-0011 accepted) |
| Q-SUP-6 | Owner idea: a "rally call" so the crowd can coordinate like a hive mind. Example: "VIPER-27 calls: ATTACK STRAIT BRIDGE" pinned on the map. | **Templated, not free text:** `!rally <node> <attack/defend/supply>` shows a map pin and a banner with the callsign. Unlocked free at Captain (O-3) with a cooldown. Channel points or donations make it more prominent (bigger banner, longer pin) but never more powerful. It only informs; it never controls other players' units. | ✅ 2026-10-17: A, templated rally call; free at Captain with cooldown; points or donations only make it more prominent |
| Q-BRAND-1 | Brand direction for Operation Nexus (unique and memorable, not a generic war map) | Owner to choose between directions offered in chat; result goes into a brand and style guide (NX-274) | ✅ 2026-10-17: **A + C hybrid.** A "Signal" radar war-room look (glowing green and amber on black, radio static, callsigns) with a **fun, friendly, playful tone**, not grim or sweaty. Goal: a welcoming, non-toxic community. Enemy name TBD (Q-BRAND-2). Lore and campaign narrative wanted (NX-275). |
| Q-BRAND-2 | Name of the enemy (and of our side) | Brainstorm in chat with the owner | ✅ 2026-10-17: Enemy = **The Static** (with a taunting mastermind; name TBD). Our side = **Clearwave** (working name; may later be put to a community vote via chat, commanders, or Discord). Viewers are **Operators**, who command squads, platoons or individual units. |
| Q-BRAND-3 | Community naming votes (side name, mastermind name, theater names): how and when? | Later (P4+): a time-boxed poll via chat command and Discord, with an owner-approved shortlist and moderation. Results are applied through the admin console. | P4 | |
| Q-PROD-7 | Can viewers watch past wars (replays)? | Yes, later: a companion-site replay viewer showing callsigns only. Hidden enemy info stays hidden until the campaign ends. | P5 | ✅ 2026-10-17: A |
| Q-GW-1 | Command rate limits | Stricter, per command class, admin-adjustable live, slow-mode toggle, cooldown ring + batched replies (CHAT-GATEWAY §5) | P2 | ✅ 2026-10-17: A. Per-class limits as in CHAT-GATEWAY §5, admin-adjustable live; slow-mode toggle; cooldown ring + batched replies |
| Q-ARCH-7 | One website or several for replays/stats vs admin/moderation/missions/content? | **Two apps, one codebase.** (1) **Public site**: replays, leaderboards, stats, later player login and account linking; public, read-mostly, contains **no** admin features. (2) **Command Center** (admin console): moderation, users, AI/GM, campaign/mission planning, rules, content creation; **private** (tailnet + Discord, Q-RB-4), separate login, separate deployment. They share a design system and contracts but use separate APIs, so a public-site bug can't reach admin powers. | ✅ 2026-10-17: A, two apps (public site + private Command Center), one codebase |
| Q-SUP-5 | Retention of financial support records? | Keep them as long as your tax and accounting needs require. Ask an accountant; this isn't something we can define for you. | P4 | |

## Questions from your conversation that need your words

1. ✅ 2026-10-17: Visible as radio/INTEL lines (A), **plus an owner or admin can take over the AI (Game Master mode, ADMIN-RBAC)**. Original question: You said the Threat Director "learns" when players attack its stockpiles. How visible should that learning be? (Default: a sitrep line, e.g. "Enemy has reinforced convoy escorts on Route 4.")
2. ✅ 2026-10-17: Yes, an INTEL ASSESSMENT panel (A). Original question: Should a viewer ever be able to see *why* the AI did something? (Default: yes, through a short "INTEL ASSESSMENT" panel. It builds trust that the AI isn't cheating.)
3. ✅ 2026-10-17: **Yes, results carry over into the next war (B).** Carry-over rules are Q-GD-12. Original question: The global map / multi-campaign theater is in the backlog. Do campaigns carry consequences into the next one? (Default: no in v1. Cosmetic history only.)
4. ✅ 2026-10-17: Later, after the alpha (A). Original question: Discord: is it part of the MVP or later? (Default: later. Use the Twitch-only alpha first.)
5. ✅ 2026-10-17: After the alpha (A). Original question: Vertical 9:16 output: is it part of the MVP? (Default: no. It doubles encode load. Add it in beta.)
