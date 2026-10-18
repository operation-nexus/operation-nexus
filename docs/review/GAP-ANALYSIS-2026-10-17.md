> Generated 2026-10-17 by a read-only reviewer agent over branch planning/round5-decisions. Questions in section 1 are mirrored into docs/planning/OPEN-QUESTIONS.md (gap batch).

# Operation Nexus gap analysis (branch `planning/round5-decisions`; I read the docs and changed nothing)

## 1. Unanswered design questions
Format: **ID** question → recommended default *(phase it blocks)*. None of these IDs collide with existing ones.

**Gameplay/sim**
- **Q-PROD-8** Where is the MVP cut line? Today's decisions put damage states, munitions, repair, base HP, track fade, Tasking Board and Pattern of Life into P1/P2 → P1 gets core loop + damage states + base HP + munitions; everything else goes behind flags *(P1)*
- **Q-GD-29** How is the "time limit → decided by score" score computed (GAMEPLAY §9)? Can a war end in a draw? → node-share over time + objectives; a ±5% draw band *(P1)*
- **Q-GD-30** Parity: is the director's budget backed by real enemy stock and factories? Does the Static have an off-map source? → budget = enemy stock; infinite rear source behind a capturable HQ *(P1)*
- **Q-GD-31** Can the AI garrison retake lost or neutral nodes, given it "never initiates offense"? → only its own nodes, within N min *(P1)*
- **Q-GD-32** What happens to units parked at a base when it's captured? → scramble to the nearest reachable base, else destroyed with a crew roll *(P1)*
- **Q-GD-33** What archetype is theater #1, given that navy arrives in P3? → land-leaning map with a bridged strait *(P1)*
- **Q-GD-34** Does the Static use the same Tasking Board, with the director as the strategic layer only? → yes *(P1)*
- **Q-GD-35** What happens when a viewer goes silent with a live unit? Chat gives no presence signal → the unit finishes its job, then RTBs and despawns after 30 min *(P2)*
- **Q-GD-36** RQ-3 (merge joiners into flights) depends on packages, which are P4. Is it in the alpha? → no; alpha uses the queue only *(P2)*

**Director/AI**
- **Q-AI-7** Can mastermind taunts name individual operators? Template-only before P4? → template-only; never name a person *(P3)*
- **Q-AI-8** Can a GM help the coalition, or only drive the Static? → Static + world events only (TS-1) *(P4)*
- **Q-AI-9** Which redemptions add to `provocation`? → only those with a gameplay effect *(P4)*

**Overlay/UX**
- **Q-UX-10** Main map camera: fixed, or auto pan/zoom? → fixed; the PiP shows detail *(P2)*
- **Q-UX-11** HUD priority with about 12 new elements (NEEDED jobs, queue, operator breakdown, rally, GM badge, explainer, mastermind) at 16:9 and 9:16 → only momentum/objective/threat/how-to-play stay on screen; the rest rotate *(P2)*
- **Q-UX-12** Merge the overlapping `!me` and `!status`? → `!status` becomes an alias *(P2)*

**Identity/progression**
- **Q-PROG-6** PROG-2 ("no XP with <2 humans") contradicts the VISION "night-owl hero" and TS-3 → drop it and rely on the cap, the first-mission gate and NX-277 *(P3)*
- **Q-PROG-7** Is Merit only a score, or can it be spent? (The O-6 "asset from merit" conflicts with ADR-0011's no-currency rule) → score only; abilities run on cooldowns *(P3)*
- **Q-PROG-8** What metric ranks each board, per role? → role contribution; overall = merit *(P3)*
- **Q-PROG-9** What happens when a season ends mid-campaign? → the season ends at the next campaign end *(P3)*

**Chat/platforms**
- **Q-GW-2** Accept commands from Twitch Shared Chat or raid-origin viewers? (API specifics [UNVERIFIED]) → own channel only *(P2)*

**Admin/ops**
- **Q-OPS-7** How are OBS, WSL2 and Docker supervised and auto-started on Windows? OPS-ADMIN §1 assumes systemd → a Windows-native supervisor + Update active hours [tooling unverified] *(P2)*
- **Q-OPS-8** Should the sim pause while the stream is offline? → auto-pause after 10 min (reason TECHNICAL) *(P2)*
- **Q-OPS-9** Weekly maintenance window, and what the stream shows while the owner games on the broadcast PC (Q-OPS-1 is still partial) → fixed window; gaming = banner + pause *(P2)*

**Data/infra**
- **Q-ARCH-16** Public site hosting and data path; does it force Postgres? → static export at campaign end; stay on SQLite *(P3)*
- **Q-DM-3** Where do D7 and session analytics come from (NX-036)? → sim events only; no trackers *(P3)*

**Content/brand, Legal**
- **Q-BRAND-4** Mastermind name (still "TBD") → owner picks from a shortlist *(P3)*
- **Q-BRAND-5** Are AI-generated logos, portraits or icons allowed under "no AI slop"? → only with owner editing + disclosure *(P2)*
- **Q-LEGAL-4** Licence for art, audio and fonts in a public MIT repo (Q-CI-2 says only "separately") → brand assets all-rights-reserved; licensed music never committed *(P2)*
- **Q-LEGAL-5** Trademark and handle clearance for Operation Nexus, Clearwave and The Static before NX-297 → basic search first *(P2)*
- **Q-LEGAL-6** Legal entity and contact for the privacy notice and donations → individual + a privacy email *(P3)*
- **Q-LEGAL-7** Can the viewer simulator (Q-PROD-4) run on the public channel, given fake-engagement policies? → LocalSim on staging/unlisted only *(P2)*
- **Q-SUP-7** Channel-point supply drops grow with audience size, which violates TS-1 → a fixed global hourly cap, or drop the category *(P4)*

**Testing/Process**
- **Q-TEST-1** Which host is the "reference host" (SC-10, OV-10)? Which platform and Python/NumPy pins apply to golden replays? → i7-8700 under WSL2 for perf; the CI image for goldens *(P1)*
- **Q-TEST-2** What does "harness-validated" mean, so a value can drop its PROPOSED label (DI-7)? → written targets (campaign 24–72 h in ≥80% of seeds, newbie impact <5 min) *(P1)*
- **Q-TEST-3** How are cold alpha testers recruited while the old-Discord announcement is held back? → 5–10 private invites *(P2)*
- **Q-PROC-1** Who folds decisions into specs, and in what order are specs approved? → one agent PR per spec; P1 specs first *(P0)*

## 2. Decision → spec propagation gaps
1. **Q-GD-4 amended (no clock pause):** the pause still appears in GAMEPLAY §9, CONTRACTS §6 PresenceSnapshot, NX-126, STATE-MACHINES §8, THREAT-DIRECTOR §5 ("stays in ALPHA") and CONFIG §6.6.
2. **Q-GD-11 (bridge repair):** still "open" in GAMEPLAY §5, STATE-MACHINES §4.3 and CONFIG `logistics.bridge_repair_time_s`.
3. **Already decided but still "TBD/pending/undecided":** Q-GD-7 (CONFIG `campaign.defeat`), Q-SM-1 (STATE-MACHINES §4.5), Q-OPS-6 (DATA-MODEL §7/§11).
4. **Q-GD-8 (sea moves to P3):** GAMEPLAY §2, CONTRACTS enums, CONFIG §7 and STATE-MACHINES §4.1 still say P4.
5. **Q-CFG-6 (night mode 00–08 America/New_York):** CONFIG `audio.night_mode.hours` is still TBD; AU-2 has no hours; ADMIN-RBAC §6.4 says times are "stored UTC".
6. **Q-NAME-1/2 (rank and class names):** PROGRESSION §3, GAMEPLAY §3 and GLOSSARY still use O-1…O-6. GLOSSARY and the Q-MOD-1 row still say custom callsigns unlock at O-2, which Q-PROG-3 superseded.
7. **Q-SUP-1 (money buys cosmetics only):** SUPPORT-REDEMPTIONS §4/§7 still say "⚠️ owner choice", and ADR-0011 still allows paid QoL.
8. **Q-RB-1…7:** ADMIN-RBAC §13 still lists them as open. Its §2 non-goal contradicts Q-ARCH-7.
9. **Q-ARCH-7/12 (public site + Command Center):** missing from SYSTEM-DESIGN §1/§6. OPS-ADMIN §3 and CONTRACTS §8 still describe an owner-only console.
10. **Q-AI-3 (isolated LLM container):** SYSTEM-DESIGN §4 runs advisors in-process, and ADR-0001 isolates only TTS.
11. **Q-ARCH-4 (local GTX 1070 experiment; the GPU was recorded as a GTX 1080 when this review was written, corrected 2026-10-17):** ADR-0007 and HARDWARE both still say "no local LLM".
12. **Q-ARCH-11/15, Q-OPS-2 (Windows/WSL2 host + Linux server):** ADR-0006, SYSTEM-DESIGN §6 and OPS-ADMIN §1 assume a single systemd host. CICD §6 still offers staging on the same host or a VPS.
13. **Q-STYLE-1/2/4 (colors, type, symbols):** OVERLAY OV-2 (red/orange diamonds) and §3 (#050811, monospace) don't match.
14. **Q-CT-4, Q-UX-9 (operator and momentum breakdowns):** missing from the CONTRACTS `Hud`/`Panels` schema and OVERLAY §1.
15. **Q-MOD-5/6 (conduct system, probation tag):** no spec mentions them at all.
16. **Q-GD-26 (Tasking Board, blocks P2):** GAMEPLAY §1 and STATE-MACHINES §4.1 still auto-route units to the objective. NX-309 is filed under P4.
17. **Q-GD-19 (`off`/`relaxed` objective modes):** these violate STATE-MACHINES invariant O-1. NX-304 is under P4 although the question blocks P1. Likewise track fade (Q-GD-16, P1) is NX-301 under P4.
18. **Q-CBT-1/2/6/7, Q-GD-27 (combat):** SIM-CORE §4 Entity has no damage state, stance or crew. STATE-MACHINES §4.1 has no Damaged/Mission-kill/Disabled states. GAMEPLAY §5 "guns only" assumes unlimited guns. GAMEPLAY §6 Pk uses only 2 factors.
19. **Command catalog:** CONTRACTS §5.2 lacks `!stance/!rebase/!rally/!rescue/!me/!scout/!help/!guide/!rules/!link`. GAMEPLAY §3 `!stance` omits `guns`.
20. **Q-GW-1, Q-CT-1 (rate limits, over-length chat):** CONFIG §6.9 still uses a single rate bucket. CHAT-GATEWAY §4 "cap at 300" doesn't say over-length messages are rejected.
21. **Q-AI-5/6 ($20 cap, AI-voice disclosure):** the $20 cap is absent from LLM-ADVISORS LLM-3, and the disclosure from AUDIO-TTS.
22. **Q-PROD-4 (flexible alpha success criteria):** VISION and NX-035 still say "7 days"; NX-034 still says "5 people". ROADMAP P4 lists 9:16, but OV-11 and NX-180b put it in P3.
23. **Stale ADR text:** ADR-0003 still says the amendment needs owner acknowledgment (Q-ARCH-6). ADR-0010 still says "Q-PROD-6 asks", and its port table lacks ModerationProvider, BackupTarget, SupportSource, AdminChannel and MusicSource.

## 3. Missing documents/specs
- **P1:**
  - Theater #1 design (NX-008): nodes, sectors, ownership, routes, names.
  - COMBAT spec: Pk factors, damage states, munitions, repair, crew/CSAR, stance.
  - Command/intent catalog: one source for the parser, `!help`, the Field Manual and `!order` (Q-AI-2).
  - Balance-acceptance criteria.
- **P2:**
  - Tasking Board spec.
  - Brand & style guide (NX-274 is filed in P4, but the overlay needs it in P2).
  - Minimal lore bible (NX-275) covering mastermind and taunt/sitrep voice.
  - Overlay layout v2 + 9:16 wireframes.
  - Sitrep/text template catalog + tone guide.
  - Viewer-simulator spec (NX-193).
  - Deployment-topology ADR amending ADR-0006.
  - Alpha playtest plan.
  - AAR / War Briefing / "what you didn't see" spec.
- **P3:**
  - Conduct-system spec (NX-291) + published community rules.
  - Public site spec (Q-ARCH-7).
  - Seasons & leaderboards spec.
  - Privacy notice.
  - Analytics metric definitions.
- **P4:**
  - Global map + carry-over spec (NX-294).
  - World events catalog (NX-310).

## 4. Top 10 risks
1. **Scope explosion** for one part-time developer → decide Q-PROD-8; put new mechanics behind flags.
2. **Agents build superseded behavior** from stale specs → run the §2 fold pass, plus a lint that flags "open" references to decided Q-IDs.
3. **A Windows gaming PC as the 24/7 host** (updates, gaming, WSL2 stability) → answer Q-OPS-7/9; plan a dedicated box early.
4. **The old Linux server** (Ubuntu 16/18.04, 8–16 GB RAM) can't carry staging + observability + backups → NX-007 measurement and the 24.04 rebuild first; VPS fallback.
5. **Channel-standing incident** (custom callsigns, taunts, AI voices, simulator bots) → template-only text, manual approval in alpha, kill-switch drills.
6. **Python tick budget** (SC-10) with crew, jobs, PoL and track fade added → benchmark the full mechanic set early; run the Tasking Board at a slower cadence.
7. **5-second readability erodes** as HUD elements pile up → Q-UX-11 + cold-tester studies on fixtures.
8. **Empty-stream boredom:** PoL may look static to early viewers → make PoL visibly animated, run scheduled live sessions, measure FB-UX-6 early.
9. **[UNVERIFIED] platform rules** (Twitch 48 h limit, AI disclosure, fake engagement, YouTube quota audit) → verify before the P2/P3 gates (NX-288 pattern).
10. **The owner is the single approver** for callsigns, clips, pauses and posts while travelling → phone-first batch queues, auto-moderation thresholds, a second ADMIN or moderator.
