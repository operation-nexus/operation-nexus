# Decided questions: Q-ALN

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Spec-alignment batch (2026-10-18)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-ALN-1 | Does sim.time_scale (6x) scale player-facing durations? | Two clocks. World time (scaled by sim.time_scale) drives movement, logistics and combat. Game time (unscaled ticks; 1 game minute = 1 real minute while running) drives player-facing durations: idle handoff/retire, cooldowns, decision windows, respawn, campaign/objective length. Both are deterministic and freeze on pause. | P1 | ✅ 2026-10-18 |
| Q-ALN-2 | What does a pause freeze? | The whole world: movement, combat and all sim timers. Commands that do not change the world (!me/!status, !quiet, joining the reserve queue) still work; others get a 'war paused' reply. STATE-MACHINES §4.4 updated accordingly. | P1 | ✅ 2026-10-18 |
| Q-ALN-3 | Pause reasons for maintenance and Ceasefire | PauseReasonCategory = OPERATOR, TECHNICAL, MAINTENANCE, CEASEFIRE. CampaignClockPaused no longer says 'no automatic pause'. | P1 | ✅ 2026-10-18 |
| Q-ALN-4 | Clock for taunt cooldowns, GM idle auto-release, redemption cooldowns, supply-drop cap | Real time (monotonic). All are enforced outside the sim before anything enters it; matches platform reward cooldowns. | P1 | ✅ 2026-10-18 |
| Q-ALN-5 | Clock for respawn delay | Game time (sim ticks). | P1 | ✅ 2026-10-18 |
| Q-ALN-6 | Rounding seconds to ticks | Round up (ceil) so a timer is never shorter than configured. | P1 | ✅ 2026-10-18 |
| Q-ALN-7 | RNG stream for Tasking Board tie-breaks | New dedicated sub-stream `tasking`, never shared. | P1 | ✅ 2026-10-18 |
| Q-ALN-8 | Old ~5 min idle despawn (slots.idle_despawn_s) vs Q-GD-35 | Removed everywhere; replaced entirely by presence.idle_handoff_min / presence.idle_retire_min. | P1 | ✅ 2026-10-18 |
| Q-ALN-9 | Does an AUTO (AI-run) unit occupy its viewer's slot? | Yes, until it retires. If the viewer commands again they reclaim that unit instead of spawning a second one. | P1 | ✅ 2026-10-18 |
| Q-ALN-10 | GM scope vs objectives and campaign options | Split roles. Campaign setup (objectives, unlimited ammo, friendly fire and other campaign options) is Admin/owner only. A GM runs only the Static and world events during play (Q-AI-8). | P1 | ✅ 2026-10-18 |
| Q-ALN-11 | Which Tasking Board can a GM inject jobs into? | The Static's board only. | P1 | ✅ 2026-10-18 |
| Q-ALN-12 | !quiet mechanics | Toggle: `!quiet` switches taunt-naming opt-out on/off and the bot confirms the new state. Any rank. Stored per commander (DATA-MODEL column) and applies across linked platforms. Added to the command catalog with parser + handler in one PR (AGENTS.md rule 6a). | P1 | ✅ 2026-10-18 |
| Q-ALN-13 | Offensive redemption class vs the no-damage rule | Keep the no-damage rule; no offensive redemption class for now. Respawn skip, queue jump and extra scout ping are support (small provocation weight); cosmetic = 0. | P1 | ✅ 2026-10-18 |
| Q-ALN-14 | Rank threshold changes via presets | Earned ranks are never revoked; new thresholds apply going forward. | P1 | ✅ 2026-10-18 |
| Q-ALN-15 | 'Held the Line' condition | Only active Operator for >= 30 continuous game-time minutes (PROPOSED) while the Static is escalated above Pattern of Life. | P1 | ✅ 2026-10-18 |
| Q-ALN-16 | Leaderboard/season data and Tasking Board outcomes | Season and per-role leaderboard source tables are specified in the seasons/leaderboards spec (NX-314). Tasking Board job outcomes are stored durably (needed for recap stats such as 'most rescues' and for balance analysis). | P1 | ✅ 2026-10-18 |
| Q-ALN-17 | GM badge on 9:16 | Always visible while a human GM is in control, on every layout. | P1 | ✅ 2026-10-18 |
| Q-ALN-18 | Older panels (Top Commanders, Active Packages, Latest Major Event) | Top Commanders joins the default rotation; Latest Major Event becomes an interrupt toast; Active Packages arrives in P4 with packages. | P1 | ✅ 2026-10-18 |
| Q-ALN-19 | 9:16 cropping around the moving PiP focus (OV-11) | No cropping: 9:16 shows the full map scaled down with the PiP below it, keeping grid references stable. | P1 | ✅ 2026-10-18 |
| Q-ALN-20 | Track fade (FOW-6) phase (partly reversed by Q-FOW-1) | Later, behind a feature flag (Q-PROD-8); NX-301 no longer blocks P1. | P1 | ✅ 2026-10-18 |
| Q-ALN-21 | Archive and 'what you didn't see' after a campaign ends | Exempt from FOW-1 once the campaign has ended: full reveal is allowed in archives and recaps. FoW applies only during the live campaign. | P1 | ✅ 2026-10-18 |
| Q-ALN-22 | GM vs Admin for rank/XP presets (Q-PROG-7 vs Q-ALN-10) | Admins/owner apply presets. GMs may draft/propose a preset; an Admin approves and applies it. | P1 | ✅ 2026-10-18 |
| Q-ALN-23 | Clock for remaining timers | World time: capture progress and decay, bridge repair, FoW sensor refresh, track fade. Game time: director decision window, tier dwell, CP EMA, memory and provocation half-lives, Pattern of Life periods, night-progress cap, Tasking Board claim lease and priority aging, package fill wait. | P1 | ✅ 2026-10-18 |
| Q-ALN-24 | Operator/system actions while paused | Safety actions always work: ban, forget, kill switch, pause/resume/end. Config reload is deferred until resume. Director overrides are rejected while paused. | P1 | ✅ 2026-10-18 |
| Q-ALN-25 | Idle retire for a Disabled unit; idle handoff for `hold` units | A Disabled unit that reaches idle retire despawns in place and its cargo is lost. `hold` units get the normal handoff and keep holding until they claim a job. | P1 | ✅ 2026-10-18. The Disabled idle-despawn part is superseded by Q-CBT-14 (wreck timeout). |
| Q-ALN-26 | Pause and idle readings | Confirmed: JOIN during a pause always queues (even with a free slot); the AUTO tag shows from the handoff tick and the current order is kept; only commands that reach the sim reset idle timers (info commands, !quiet, !callsign do not). | P1 | ✅ 2026-10-18 |
| Q-ALN-27 | 'Active' Operator for Held the Line | Has a non-AUTO unit and sent a sim-reaching command within presence.idle_handoff_min. | P1 | ✅ 2026-10-18 |
| Q-ALN-28 | !quiet on account merge | Opt-out wins: if either merged commander had taunt_opt_out set, the survivor keeps it set. | P1 | ✅ 2026-10-18 |
| Q-ALN-29 | Suffix after REDACTED- | A random 4-character tag assigned and stored at deletion time (e.g. REDACTED-7KQ2); not derived from any identifier, so it cannot be reversed; distinct actors stay distinct in replays. | P1 | ✅ 2026-10-18 |
| Q-ALN-30 | Jobs completed by a viewer's AUTO unit | Recorded as separate 'AUTO assists' for recaps only; they never count toward XP, Merit or leaderboards. | P1 | ✅ 2026-10-18 |
| Q-ALN-31 | Q-RB-1 operator pause categories vs Q-ALN-3 | Two fields: category (OPERATOR/TECHNICAL/MAINTENANCE/CEASEFIRE) plus an optional sub-reason (RAID/ABUSE/CONTENT/OTHER) used only when category = OPERATOR. | P1 | ✅ 2026-10-18 |
| Q-ALN-32 | HUD label for an operator pause | A simple 'PAUSED — stand by' banner. | P1 | ✅ 2026-10-18 |
| Q-ALN-33 | Capture with defenders present (Q-GD-32 reading) | Combat-capable defenders freeze capture (Contested); defenders that cannot contest (parked air, Disabled units) slow it via the garrison multiplier. | P1 | ✅ 2026-10-18 |
| Q-ALN-34 | XP for AUTO units outside jobs | None. No action by an AUTO unit (kills, deliveries, captures, jobs) earns XP or Merit or counts toward leaderboards; all are recorded as AUTO assists for recaps. | P1 | ✅ 2026-10-18 |
| Q-ALN-35 | Clock for the CHARLIE warning lead time | Game time. | P1 | ✅ 2026-10-18 |
| Q-ALN-36 | Remaining actions while paused | Allowed: unban, purge units, set callsign (none move the world). Rejected with CAMPAIGN_PAUSED: advisor choices and GM commands, except a GM releasing control. | P1 | ✅ 2026-10-18 |
| Q-ALN-37 | Redemptions while paused | Refused and the channel points refunded automatically. | P1 | ✅ 2026-10-18 |
| Q-ALN-38 | FoW Tier 1 refresh on world time | Re-express the value as world time so the real cadence stays about 8-10 s (48-60 s of world time at 6x); PROPOSED until harness-validated. | P1 | ✅ 2026-10-18 |
| Q-ALN-39 | Pause sub-reason on stream | The public stream shows only 'PAUSED — stand by'; the sub-reason stays internal. The overlay receives only the pause category needed to choose the scene. | P1 | ✅ 2026-10-18 |
| Q-ALN-40 | 'Operator' has three meanings (player, Command Center staff, O-2 rank) | Operator means a player only. Command Center people (owner, admins, mods, GMs) are 'staff': staff_id, STAFF_* admin commands, STAFF pause category. O-2 is renamed (Q-ALN-41). | P1 | ✅ 2026-10-18 |
| Q-ALN-41 | Rank ladder theme | Hive ladder (working names): O-1 Recruit, O-2 Drone, O-3 Specialist, O-4 Swarm Lead, O-5 Hive Commander, O-6 Quorum Marshal. Voice profile 'Quorum Control' confirmed. | P1 | ✅ 2026-10-18 |
| Q-ALN-42 | Balance-harness crowd profiles | 0, 5, 50, 150, 300 and 500 simulated viewers (supersedes the 0/10/100/300 in Q-TEST-2 and the 0/5/50/500 in ROADMAP/TESTING-STRATEGY), plus the adversarial profiles. Amended 2026-10-18 (Q-SIM-6): the 500 profile exercises the raised `slots.max_viewer_units` cap. | P1 | ✅ 2026-10-18 |
