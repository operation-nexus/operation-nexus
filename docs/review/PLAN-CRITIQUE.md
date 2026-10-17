# Critique of the Original Plans

Date: 2026-10-17 · Inputs: `Raw-plans.md` (P), `Raw-conversation.md` (C) at commit `f0c7624`
Companion reports: [Security review](SECURITY-REVIEW-RAW-PLANS.md) · [Platform reality check](PLATFORM-REALITY-CHECK.md)

## TL;DR

The core idea is strong and worth building. Co-op chat logistics against an adaptive AI, on a readable 2D war-room map, is distinctive. Unlike most "AI slop" streams, it is anchored in deterministic rules and persistent state.

The plans themselves, though, show the usual signs of AI generation:
- **Copy-paste residue from other projects:** "apex species", "racing league" and "ecosystem extinction" (P25–31), and "SimConnect" (C108), which is a Microsoft Flight Simulator API.
- **Duplicated paragraphs:** P34≡P39 and C69≡C72.
- **Confident numbers with no derivation:** "50–80% of revenue" (P8), "35 MB per war" (P243), "+35% survival" (P44).
- **Sample code that doesn't do what its comments claim:** "deterministic" code that uses `random`, "8x zoom" set to `0.85`, "dead reckoning" that doesn't interpolate.
- **Over-engineering for a solo developer:** five containers, Helm "from day one", K3s, a local 27B LLM, Three.js, a Discord bot, and auto-upload, all before one viewer has typed `!join`.

The plans also miss three things that will decide whether the project succeeds:
1. **Platform reality.** TikTok has no chat API, YouTube quota makes polling impossible, and auto-uploads stay private until an audit passes.
2. **Content safety.** Every username is broadcast, spoken and clipped.
3. **24/7 operations.** There is no watchdog, alerting, kill switch, or deploy-without-dropping-the-stream plan.

The rest of this document lists every hole found. Each one maps to a decision in [OPEN-QUESTIONS](../planning/OPEN-QUESTIONS.md) or a requirement in the specs.

## 1. Contradictions that must be resolved

| # | Conflict | Where | Proposed resolution |
|---|---|---|---|
| 1 | The tick rate is given as 20 Hz, "10 or 20 Hz", and 10 Hz | P120, P144, P290 | **10 Hz** fixed step (ADR-0002) |
| 2 | The sim is called "deterministic", but the code uses `random`, `uuid4`, wall-clock time and a drifting `sleep`. The director is LLM-driven, and replays are a 1 Hz snapshot log rather than a re-simulation. | P6, P240, P382, P525, C22 | Make determinism real: a seeded RNG and integer ticks. Record LLM outputs as input events (ADR-0002). |
| 3 | The director is described as "PID-controlled every 60 s", as fixed tiers whose ranges overlap at 40 and exclude 0, and as code that runs every 6 s and just counts entities | P63, P69–71, P422 | Tiers with hysteresis on smoothed **coalition power** rather than headcount (THREAT-DIRECTOR) |
| 4 | SQLite vs Postgres is never decided. Link tokens live in Redis in one place and in a SQLite table in another. | P51, P748, P847 | ADR-0003 |
| 5 | Pixi.js vs plain Canvas vs "zero-dependency" | C76, P92, P268 | ADR-0005 (Canvas2D first; Pixi if profiling demands it) |
| 6 | Three.js PiP in the architecture vs a 2D intercept box in Phase 1. The "8x zoom" is `0.85`. | C67, P252, P693 | 2D scope in the MVP. Three.js goes to the backlog. |
| 7 | Doctrine is "locked per campaign for hero moments" (C8–10), but `!spec` lets players switch between campaigns, and *everyone* can already `!join logi` | P779, P760, P1166 | Base roles are open to all. **Specialist perks are locked per campaign.** (Q-GD-3) |
| 8 | Newbie Tier-1 commands include `!sead` and `!package`, which the rank table gates at O-3 and O-5 | P43, P47, P762, P764 | A single command table in GAMEPLAY §Commands |
| 9 | "0-second wait, 1 slot" conflicts with a 60 s 4-ship lobby. The "or after a 90 s cooldown" rule is ambiguous and could allow two live units. | P47, P209 | 1 live unit per viewer. Packages form *around* units that already exist. |
| 10 | Quorum voting and "3–4 AI factions, join a faction" appear in one place; everything else describes single-coalition co-op | P2, P25 | Co-op single coalition. Voting is dropped from the MVP. |
| 11 | In "Hold the Line" the owner wanted the **AI** to defend for X hours. The plans make the **players** defend. | C29, C44 | Both are valid modes. Ask the owner which ships first (Q-GD-2). |
| 12 | Campaign length is 24–72 h in one place and 48–72 h in another. Victory at 75% of nodes sits inside the 70–85% rubber-band zone, and no defeat condition exists. | P211, P218, P220, P968 | GAMEPLAY §Win/Loss |
| 13 | Supply rate is +10/min, +10/5 min, and 90/min in code. Starvation is <25% in one place and 0% in another. | P998, P1005, P1046 | Balance config, tuned by the harness |
| 14 | Rank 2 is "~2 sorties" in one place and "~15 min" in another. There is no XP table. | P752, P761 | PROGRESSION §XP table |
| 15 | Fire-control buff is +25% vs +15%. Recon XP is a 50/50 split vs a +50% assist. There is no accuracy model. | P237, P786 | GAMEPLAY §Combat |
| 16 | "<1.5 s feedback" vs 2–20 s platform stream delay and YouTube's API-dictated polling | P27, P43 | Redefine as **≤500 ms from ingest to on-screen ack** (server side). Measure real end-to-end latency per platform. |
| 17 | A local Gemma 27B (~16–18 GB VRAM at 4-bit) is planned on the same GPU as OBS dual-encode, Chromium WebGL and the clip renderer | P34, P141 | No local large LLM on the broadcast box (Q-ARCH-4) |
| 18 | "Helm from day one" and five containers, for one developer | C89, P113 | Modular monolith (ADR-0001), Compose on a single node (ADR-0006) |
| 19 | Unclear authoritative store: "all state via Redis" and "reload from Redis in 50 ms" with no persistence configured | C136, P147 | In-memory sim plus snapshot plus command log (ADR-0003) |
| 20 | The 35 MB/48 h replay estimate implies about 1 byte per unit per second. Clips read "30 s from Redis", but frames are written at 1 Hz. | P243, P249 | Measure in Phase 0. Clips come from the command log and replay at full tick rate. |
| 21 | The text promises delta frames; the code sends full state every tick | P145, P507 | WIRE-PROTOCOL |
| 22 | The cosmetic Crimson `#F43F5E` is the exact ENEMY color, and Gold is the exact LOGI color | P770, P376, P371 | Cosmetics only affect halos and trails. Friend/foe uses **shape + locked color**. |
| 23 | Platform is stored as "YT" in one place and "YOUTUBE" in another, which would create duplicate identities | P736, P1094 | An enum in contracts |
| 24 | The map is in "km" and strike speed is 140 units/s, i.e. 140 km/s, so a unit crosses the map in about 14 s. "3 minutes to the front" contradicts this. | P210, P288 | Define units and time scale in SIM-CORE §World scale |
| 25 | "Ambient music to fall asleep to" vs camera-shutter sound effects and "splash two bandits" TTS | P95, P99 | AUDIO §Night mode |

## 2. Sample code defects (don't reuse this code)

**Stream-killing**
- The sim task can die silently from a `clients.remove` race or any exception. The task reference isn't kept.
- One slow WebSocket client stalls the tick.
- The overlay never reconnects, so it freezes on air.
- The tick drifts because it uses `sleep(dt)` after doing work, and there's no fixed-step accumulator.

**Correctness**
- **Combat:**
  - The O(n²) loop shoots the first enemy in range rather than the best target.
  - Trucks and drones deal damage.
  - `valid_target_domains` is ignored.
- **Captures and win check:**
  - Any unit instantly flips a node on arrival, including a drone flipping the enemy capital.
  - There is no win check, so the campaign never ends.
- **Spawning:** the enemy falls back to spawning *inside the player's main base*.
- **Kills:** dead units linger a tick with negative HP, and kills award nothing.
- **PiP:** focus thrashes every tick.
- **Rendering:** there's no client interpolation, so the "60 fps dead reckoning" doesn't exist.
- **Supply tick:**
  - It heals HP (not ammo or fuel) at 20 HP/s with no distance limit, so units near a friendly node are effectively immortal.
  - It drains supply per tick per unit.
  - It never uses graph edges, so there's no pathfinding.
- **Fog of war leaks:**
  - The real entity id is inside the SIGINT blob id, and the jitter is deterministic, so exact positions can be recovered.
  - There's one blob per unit, so the count leaks.
  - Tracers reveal hidden shooters.
  - **The enemy director is omniscient**, which violates the owner's fairness rule (C22).
- **Callsigns:**
  - The default callsign `TW-ABCDEFG-42` is 13 characters and fails the project's own `{3,12}` regex.
  - Collisions crash the viewer's first command forever.
  - Non-Latin names collapse to "UNIT".
- **Blocking I/O:** synchronous SQLite calls run inside async handlers and block the event loop.

**Security** (detail in the [security review](SECURITY-REVIEW-RAW-PLANS.md))
- Account takeover via linking.
- Tokens posted in public chat, and those tokens are guessable.
- Stored XSS into OBS.
- An unauthenticated command API with CORS set to `*`.
- The LLM can command other users' units.
- Every unmatched chat message goes to the LLM (cost DoS).

## 3. Game design holes and questions

1. **What happens with no players.** If the war keeps moving overnight, a viewer can wake up to find the campaign lost while nobody was watching. If it pauses, the stream looks dead. *Recommendation:* when no humans are active, run "slow war": the AI vs AI garrison is capped at 1 node per 6 h and the campaign clock pauses. (Q-GD-4)
2. **Scaling difficulty by headcount punishes growth and is easy to game.** One person with 40 alt accounts could trigger CHARLIE. *Recommendation:* scale on smoothed demonstrated **coalition power** (active units weighted by supply state), ignore accounts younger than a threshold, and cap the scaling. (THREAT-DIRECTOR)
3. **XP farming and bots.** Idle macros spamming `!join`/`!logi` will farm XP. *Recommendation:* award XP for *mission completion* rather than spawns, apply hourly diminishing returns, require a minimum account age, and give no persistent XP when fewer than 2 distinct humans are present. (PROGRESSION)
4. **Griefing in co-op:**
   - spawn-spamming at an FOB to drain its supply
   - suicide runs that feed the director
   - parking trucks on bridges
   - `!order`-ing other people's units

   *Recommendation:* spawns at a starved FOB are free but under-equipped, units don't collide, and orders apply only to your own unit.
5. **Leaderboards pull against teamwork.** If kills give the most XP, everyone plays strike. *Recommendation:* weight the leaderboard by objective contribution (supply delivered, nodes captured, recon assists) at least equal to kills, and run separate boards per role.
6. **1,000 viewers means 1,000 units.** Labels become unreadable, the tick budget breaks, and quota runs out. *Recommendation:* auto-group units into flights, label only the PiP focus and the top N, and degrade gracefully with a "reserve queue" above an entity cap (Q-GD-6).
7. **Session length vs campaign length.** Viewers stay 10–40 minutes and wars run 48 h. *Recommendation:* a rotating **15-minute theater objective** that is always on screen (P20 had the idea, but it never reached the design).
8. **The LLM director is unpredictable, which isn't the same as fun.** It is also untestable, costs latency and VRAM, and breaks replays. "Learns that convoys get attacked" (C37) is a decaying threat counter and doesn't need an LLM. *Recommendation:* rules decide what happens. An LLM *advisor* may pick among rule-valid options and write flavor (operation names, sitreps). Every LLM output is recorded as an event. (Q-AI-1)
9. **Variety over months.** Procedural seeds change the layout but not behavior. We need a content cadence: new enemy doctrines, events, seasonal theaters.
10. **Running costs at 3 a.m.** A GPU box draws 300–500 W around the clock, plus API calls. We need an idle mode and a monthly cost ceiling (Q-OPS-3).
11. **Platform rules:**
    - A Twitch broadcast reportedly ends after 48 h, so the stream needs auto-restart.
    - TikTok penalizes LIVEs that are "unattended" or have no presenter.
    - YouTube's "inauthentic content" policy targets templated, auto-narrated Shorts.
12. **Readable in five seconds.** The momentum bar and the "current 15-minute objective" are the most important UI elements, and neither appears in the code or the overlay spec. They are now P0 in OVERLAY.

## 4. Missing requirements (now added to specs)

- **Non-functional requirements:**
  - Latency budgets.
  - Uptime target and mean time to recover (MTTR).
  - Cost ceiling.
  - Reference hardware.

  → SYSTEM-DESIGN §NFRs
- **Observability and external "stream is down or frozen" alerting** → OPS spec
- **Watchdog, fallback "technical difficulties" scene, kill switch, admin console** → OPS + ADMIN
- **Moderation pipeline and generated callsigns by default** → THREAT-MODEL SEC-MOD
- **Balance workflow:**
  - Versioned YAML config.
  - A harness with bot populations.
  - The config hash stored with replays.

  → GAMEPLAY + TESTING-STRATEGY
- **Determinism, property, soak and balance tests** → TESTING-STRATEGY
- **Data:**
  - Migrations and backups.
  - Retention.
  - GDPR deletion.
  - Pseudonymous replays.
- **Accessibility:** friend/foe shown by shape plus color, colorblind-safe palette, and a minimum text size at 720p/mobile.
- **Legal:**
  - Music licensing (no "Vangelis-like" without a licence).
  - Avoid "NORAD" in branding.
  - Privacy notice.
  - Platform ToS.
  - Piper's GPL.
- **Monetization:** not mentioned at all. A non-pay-to-win policy is needed (Q-BIZ-1).
- **Success metrics per phase,** so we know whether it's working (ROADMAP).

## 5. What the plans got right (keep these)

- Co-op PvE first, not chat-vs-chat PvP (P12–13).
- **Fast path vs slow path:** deterministic commands skip the LLM (P139, P1125).
- **One guaranteed command slot per viewer** and supply-backed effectiveness instead of spawn gating (P206–210).
- **Horizontal progression** (sidegrades and force multipliers, no raw power creep) (P754–765).
- **SIGINT-style fog of war** that never blacks out the map (P228–238).
- **Supply-line stretch** as a snowball breaker (P211).
- Lazy account creation, keyed on `(platform, platform_user_id)` (P731–745).
- Event-sourced replays and a companion site for depth, keeping the broadcast clean (C54–56).
- Shipping the 2D intercept scope before Three.js (P252).
- The night-friendly audio philosophy (P99–107).

## 6. Recommendations (summary)

1. **Build a modular monolith** around a **pure, deterministic sim kernel.** Split into services only when there's a measured reason (ADR-0001).
2. **Launch on Twitch first**, add YouTube (via `streamList`) second, and consider Kick third. **TikTok is deferred** until an official API exists or the owner accepts the ToS risk in an ADR.
3. **Rules decide; the LLM advises and narrates.** No LLM on the broadcast GPU.
4. **Make content safety a first-class system:** generated callsigns by default, a moderation pipeline, an operator kill switch, and human approval for clips.
5. **Link accounts via OAuth** on a small portal. No tokens in chat.
6. **Treat operations as a feature:** a watchdog, frozen-frame detection, alerting, and deploys that don't drop the stream.
7. **Make the balance harness exist before the stream does.** Prove 0, 5, 50 and 500 viewers in simulation before going live.
8. **Give each phase measurable exit criteria** (ROADMAP).
