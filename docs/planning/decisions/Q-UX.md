# Decided questions: Q-UX

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-UX-6 | Supply route visualization | Route lines with flow brightness, per-base supply gauge, cut routes red/dashed, starving bases blink gently | P2 | ✅ 2026-10-17: A, supply must read as **vital** and look good. **Plus reachability:** when an operator orders a move (`!rebase`, `!target`), draw the route with distance/ETA and fuel reach. If out of range, show it clearly ("cannot reach: fuel") and suggest the nearest reachable base (OVERLAY §2a annotations) |
| Q-UX-7 | Rally call visuals | Pulsing pin on the target + arrow from the caller's unit + short banner ("VIPER-27: ATTACK STRAIT BRIDGE"); ~2 min TTL; max active count; fades out (OVERLAY §2a annotations) | P4 | ✅ 2026-10-17: A |
| Q-UX-8 | War end sequence | Victory/defeat moment → AAR → looping War Briefing while the next theater loads; ~10–15 min intermission | P2 | ✅ 2026-10-17: A. Victory/"SIGNAL LOST" screen; **optional** zoom-in on the final action (configurable); AAR summary + leaderboards. **Intermission and advancement fully configurable:** `auto_advance` (start the next war after N min) or `await_owner` (notify the owner, who approves the next war with one tap, as in the pause flow). Timings configurable. |
| Q-UX-9 | Momentum bar formula | Smoothed blend of nodes held, supply health and recent major events; themed label "Signal strength"; strategic only (TS-2) | P1 | ✅ 2026-10-17: A, with the **detailed breakdown** (nodes, supply %, recent events, per-sector status) in the rotating panels and ticker |

## Batch: naming, onboarding, seasons, UX (added 2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-UX-1 | First-time viewer onboarding | A persistent "How to play" strip + a 30-second looping explainer card every ~10 min + `!help` digest. No long tutorials. | ✅ 2026-10-17: A (on-screen How-to-play strip + looping explainer card + !help). Plus a **Field Manual** on the public site: a simple quick-start guide up front, and an **advanced operations guide** (stances, grid refs, CSAR, logistics tricks, hidden mechanics) as page, video, or PDF. Linked from stream descriptions, channel panels and !guide |
| Q-UX-2 | Season structure | Seasons of ~4–8 weeks (several campaigns). Season leaderboards reset; lifetime ranks don't. A season-end recap and cosmetic badges. Ties into the global campaign later. | ✅ 2026-10-17: A, seasons of ~4–8 weeks; season boards reset, lifetime ranks don't; season recap + cosmetic badges; later tied to the global campaign |
| Q-UX-3 | Leaderboard reset cadence | Per-campaign boards reset each war; season boards each season; lifetime boards never | ✅ 2026-10-17: A, three boards: war (reset each war), season (reset each season), lifetime (never). **Banned or confirmed-cheating operators are removed from every board** (mod/admin action, audited; their entries are hidden and recomputed, not deleted from the ledger) |
| Q-UX-4 | After-action review (AAR) screen contents | 5 minutes: winner, map timeline, top operators per role (not just kills), best rescue, the "what you didn't see" reveal, next-war teaser | ✅ 2026-10-17: A, full ~5 min AAR. Plus a **short War Briefing card** (what happened, where we stand, where we go next, the plan) that loops on stream between wars and is published to the site and Discord. Same content source, three outputs |
| Q-UX-5 | Overlay language(s) | English first; all text through localization keys so more languages can be added later | ✅ 2026-10-17: A, English first; all text through localization keys |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-UX-10 | Main map camera: fixed, or auto pan/zoom? | fixed; the PiP shows detail | ✅ 2026-10-18: Main theater map is fixed (stable grid references for commands). A PiP detail window auto-follows the hottest action (firefight, base under attack, CSAR) and zooms in. Brief main-view spotlight zooms for huge moments are a possible later Command Center toggle, not in scope now. |
| Q-UX-11 | HUD priority with about 12 new elements (NEEDED jobs, queue, operator breakdown, rally, GM badge, explainer, mastermind) at 16:9 and 9:16 | only momentum/objective/threat/how-to-play stay on screen; the rest rotate | ✅ 2026-10-18: Three tiers. Always on: momentum, objective, threat, how-to-play strip. Interrupt toasts (few seconds): rally calls, mastermind taunts, major alerts. One rotating panel (hud.rotation_s, proposed ~15 s): NEEDED jobs (double frequency), reserve queue, operator breakdown, explainer. GM badge is persistent whenever a human GM is in control. 9:16: only momentum, objective, how-to-play persistent; threat joins rotation. Rotation timing and membership admin-configurable. |
| Q-UX-12 | Merge the overlapping `!me` and `!status`? | `!status` becomes an alias | ✅ 2026-10-18: !me is canonical (FB-UX-3 behavior: 5 s highlight + digest line, works in reserve queue). !status is a pure alias with identical behavior. |
