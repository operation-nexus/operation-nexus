# Decided questions: Q-PROD

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Product & scope

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROD-1 | What is the #1 goal for year one: fun hobby/devlog content, audience growth, or revenue? It drives how much ops rigor and cost is justified. | Audience growth + devlog content. Revenue is a bonus. | ✅ 2026-10-17: Audience growth + devlog content; revenue is a bonus (A) |
| Q-PROD-2 | Which platform launches first? | **Twitch only** through closed alpha. YouTube in beta. Kick optional. TikTok deferred. | ✅ 2026-10-17: Twitch only for alpha, then YouTube (A) |
| Q-PROD-6 | With ADR-0010 (both platforms first-class), do you want Twitch **and** YouTube in the closed alpha (simulcast), or keep Twitch-only alpha → YouTube beta? | Twitch-only alpha, YouTube in beta. The YouTube quota application and monitoring should come first. The code is neutral either way. | ✅ 2026-10-17: Twitch-only alpha, YouTube in beta (A) |
| Q-PROD-3 | Will you be present on stream sometimes, or is it fully unattended? (This affects TikTok/YouTube policy risk and moderation.) | Unattended by default, plus scheduled "commander's briefing" sessions with you live weekly. | ✅ 2026-10-17: A (mostly unattended + weekly live briefing), and seasonally C (frequent live sessions, e.g. campaign launches or season events) |
| Q-PROD-4 | What is the success metric for closed alpha? | ≥5 cold testers can say who's winning within 5 s and spawn within 30 s. 7 days unattended with ≤1 manual fix. | ✅ 2026-10-17: A, flexible: a few cold testers (not strictly 5) read the stream in 5 s and spawn within 30 s; a multi-day unattended run (not strictly 7 days) with minimal manual fixes; zero unmoderated text. **Also required:** solid monitoring, plus a **viewer simulator** (scripted bot operators) to test extensively during the expected long stretches with no viewers. |
| Q-PROD-5 | Public name and branding? "Operation Nexus" is fine. Avoid "NORAD" and real-org insignia. | Fictional factions, "Operation Nexus" | ✅ 2026-10-17: A, mandatory. **No real names anywhere**: no real countries, militaries, weapon systems or orgs ("NORAD" etc.). Units use generic class names (Tank, Striker, Bomber, Recon, Convoy…). Real-world *types* of platforms may be evoked, but they're clearly fictional and simulated. Needs a unique, memorable brand identity (Q-BRAND-1, NX-274). |

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROD-7 | Can viewers watch past wars (replays)? | Yes, later: a companion-site replay viewer showing callsigns only. Hidden enemy info stays hidden until the campaign ends. | P5 | ✅ 2026-10-17: A |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROD-8 | Where is the MVP cut line? Today's decisions put damage states, munitions, repair, base HP, track fade, Tasking Board and Pattern of Life into P1/P2 | P1 gets core loop + damage states + base HP + munitions; everything else goes behind flags | ✅ 2026-10-17: C. First build = core loop + damage states + base defense HP + limited munitions + fog of war + director tiers with Pattern of Life **+ the Tasking Board**. Later behind flags: track fade, CSAR/crew rescue, stances, world events, base upgrades, weather |
