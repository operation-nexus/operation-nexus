# SPEC: Progression


> **All numeric values in this spec are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). They become real only after the balance harness validates them, as defined in Q-TEST-2 (≥50 seeds across crowd profiles, written targets met, report saved with the config hash).
Status: Draft · Tracker: NX-210…NX-224 · Inputs: P725–971, C5–10

## 1. Principles
Progression is horizontal. Ranks unlock **options and force multipliers**, never raw hp or damage. Two tracks: a **Lifetime Service Record** (rank, callsign, cosmetics, ribbons) and **Campaign Merit**, which resets each war (Q-PROG-1).

**Merit is a score only** (Q-PROG-7, ADR-0011). It ranks the overall board (§6) and is never spent, converted or used as a balance. Rank-unlocked abilities run on cooldowns, not on merit.

## 2. XP sources (Q-PROG-2) — initial values
The values below are the initial PROPOSED preset. They are config data, not code (§3a).
| Action | XP | Merit |
|---|---|---|
| Sortie completed (survived, objective attempted) | 40 | 10 |
| Supply delivered (per 10 stock) | 15 | 5 |
| Node capture participation | 60 | 20 |
| Theater objective completed (participant) | 80 | 30 |
| Recon paint → assist | 15 | 5 |
| CSAR rescue completed (GAMEPLAY §6a: "large" bonus) | TBD by harness | TBD by harness |
| Kill | 10 | 3 |
| Spawning | 0 | 0 |

**PROG-1** Diminishing returns: after `progression.xp_hour_soft_cap` (PROPOSED 400 per real hour), further XP is × `progression.xp_over_cap_mult` (PROPOSED 0.25).
**PROG-2** No persistent XP until the commander's first completed mission (Q-PROG-3). There is **no minimum-humans rule**: a lone operator earns XP normally (Q-PROG-6; VISION night-owl hero, GAMEPLAY TS-3).
**PROG-3** Merges never sum XP (IDENTITY §4).
**PROG-4** Anti-farming is layered, with no captcha (Q-PROG-3, Q-PROG-6, NX-277): (1) platform account age where the platform API exposes it [UNVERIFIED per platform]; (2) our own first-seen age (IDENTITY §1); (3) the first-completed-mission gate (PROG-2); (4) hourly diminishing returns (PROG-1); (5) Command Center anomaly flags for many new accounts acting in lockstep; (6) a mod/admin action that voids XP, audited, which writes compensating ledger rows and never deletes ledger rows.
**PROG-5** Nobody grants XP or merit directly: there is no admin, mod or GM command that awards XP or merit to a player (Q-AI-8). XP and merit come only from the §2 sources. PROG-4 (6) can only remove.
**PROG-12** **AUTO assists (Q-ALN-30):** a Tasking Board job completed by a commander's unit while it is AI-run (AUTO, GAMEPLAY GP-4) is recorded as an **AUTO assist** for recaps only. It awards no XP and no merit, and it never counts toward any leaderboard metric (§6). Progression tells these apart by the `auto` flag on the job's completion event (CONTRACTS, Tasking Board events).

## 3. Ranks (one table; resolves critique #8 and #14)
`O-1`…`O-6` are **internal rank ids** (config, contracts, DB). Viewers see the **themed display name** (Q-NAME-1; working names, final list in the brand guide NX-274). No real military rank titles appear on stream (Q-PROD-5).

| Rank id | Display name (working) | XP | Unlocks |
|---|---|---|---|
| O-1 | Recruit | 0 | Striker, Scout, Hauler (strike, recon, logi); `!target`, `!rtb`, `!rebase`, `!stance`, `!wingman` |
| O-2 | Operator | 300 (~45–60 min active) | `!vector`. (Custom `!callsign` is **not** rank-gated: it unlocks after the first completed mission, Q-PROG-3.) |
| O-3 | Specialist | 1,500 | `!doctrine`; SEAD, artillery; `!rally` (Q-SUP-6); `!order` (P4) |
| O-4 | Signal Lead | 5,000 | Jammer, engineer, AWACS |
| O-5 | Wave Commander | 15,000 | `!package` lead |
| O-6 | Clearwave Marshal | 40,000 | May call 1 theater asset per cooldown (default 1 h, Q-PROG-7; game time, Q-CFG-8, Q-ALN-1; held in the rank-table preset, §3a). Costs no merit (Q-PROG-7). |
The XP thresholds are placeholders. The balance harness sets them so that O-2 takes about 1 hour and O-4 about 2–4 weeks for a regular player.

## 3a. Presets and admin editing (Q-PROG-7)
**PROG-6** The rank table (internal id, XP threshold, unlocked abilities, ability cooldowns) and the §2 XP and merit values are **config data**, not code. The tables above are the initial PROPOSED preset.
**PROG-7** The owner and Admins edit them in the Command Center as **named presets** (ADMIN-RBAC). A GM may draft or propose a preset; only an Admin or the owner approves and applies it (Q-ALN-22). The active preset is a campaign option (PROG-8), so a GM can never apply or select it (Q-ALN-10). Each save is validated by the config validator (thresholds strictly increasing from O-1 = 0; no negative XP or merit value; every unlocked command or ability exists in the command catalog, AGENTS.md rule 6a) and written to the audit log. An invalid preset is rejected whole.
**PROG-8** The active preset is part of the campaign config and its `config_hash`, so every replay and ledger row can be traced to the values that produced it.
**PROG-9** Ability cooldowns are game time (unscaled sim ticks, Q-ALN-1): deterministic, and frozen while the sim is paused (Q-CFG-8, Q-ALN-2).
**PROG-11** **Earned ranks are never revoked** (Q-ALN-14). A preset that changes XP thresholds applies going forward only: a commander keeps every rank already earned, even if their XP is below the new threshold, and later promotions use the new thresholds.

## 4. Doctrines (Q-GD-3)
Chosen once per campaign at O-3 or above, from Air Superiority, Logistics Mastery, Recon/EW, and Garrison Command. Each gives 3 small perks (from the plans: cargo +15%, sensor +20%, drop tanks, …) plus **one signature ability** that only doctrine holders have. That's where the "only logistics expert" hero moments come from (C8). Holders get a doctrine badge on their unit symbol.

## 5. Cosmetics
Halo colors, trail styles, PiP placard ribbons, kill stencils, and voice presets (P4). The base icon color never changes (OV-2). Any monetization is cosmetic only (Q-BIZ-1).

**PROG-10 'Held the Line' badge** (Q-PROG-6, Q-ALN-15): a cosmetic badge for defending while the only active human. It is awarded when a commander is the **only active human operator for ≥ 30 continuous game-time minutes** (PROPOSED) while the Static is escalated above Pattern of Life (THREAT-DIRECTOR §5a). **Active** (Q-ALN-27) means the commander has a non-AUTO unit and sent a command that reached the sim within the last `presence.idle_handoff_min`; a commander whose unit is AUTO is not active. It grants **no XP or merit**, so it can't be farmed.

## 6. Leaderboards
Separate boards per role, plus an overall board. Campaign MVPs are listed in the Hall of Fame. Display uses approved callsigns only.
- **Metrics (Q-PROG-8):** each board's ranking metric is defined in config. Initial metrics: logistics = supplies delivered; recon = spotted enemies later engaged by friendlies; CSAR = rescues completed; combat = threat-weighted kills + objective damage; **overall = Merit**. Assists count toward the metric; AUTO assists never do (PROG-12, Q-ALN-30).
- **Views (Q-PROG-8):** each board has two views: season total (primary) and per-hour-played.
- **Three horizons (Q-UX-3):** war (resets each war), season (resets each season), lifetime (never resets).
- **Seasons (Q-UX-2):** ~4–8 weeks, several campaigns. Season boards reset; lifetime ranks don't. Season-end recap plus cosmetic badges.
- **Season end (Q-PROG-9):** a season ends when the campaign running on its planned end date ends. During that overtime the HUD and site show "Season ends after this campaign". If overtime reaches `season.overtime_cap_days` (PROPOSED default 14), the season closes anyway; the running campaign carries into the new season, and points earned from then on count there.
- **Removal:** banned or confirmed-cheating operators are removed from every board by a mod/admin action (audited). Their entries are hidden and the board recomputed; ledger rows are not deleted.
- **Source data (Q-ALN-16):** the season and per-role leaderboard source tables are specified in the seasons/leaderboards spec (NX-314, not yet written). Tasking Board job outcomes are stored durably (GAMEPLAY TB-10) and feed recap stats such as "most rescues"; AUTO assists appear in recaps only (PROG-12).
- **Publishing (Q-ARCH-16):** the public site gets boards through one-way static exports from the broadcast host (about every 15 min, configurable). There is no inbound path from the site.

## 7. Test plan
- PROG-1: property test that XP past the soft cap is multiplied by `xp_over_cap_mult`, and that a lone operator (1 human) earns XP (PROG-2, Q-PROG-6).
- PROG-2: no persistent XP before the first completed mission.
- PROG-5: the command catalog has no XP- or merit-granting command; PROG-4 (6) void writes compensating rows and the ledger row count never decreases.
- PROG-7: the validator rejects a preset with non-increasing thresholds, a negative value, or an unknown unlocked command; every accepted save has an audit row. A preset drafted by a GM does not become active until an Admin or the owner approves and applies it, and a GM's apply request is refused (Q-ALN-22).
- PROG-12: a job completed by an AUTO unit writes an AUTO assist for that commander, no XP or merit ledger row, and no leaderboard change (Q-ALN-30).
- PROG-9: an ability cooldown does not advance while the sim is paused, and takes the same number of ticks at any `sim.time_scale` (Q-ALN-1).
- PROG-11: after a preset raises a threshold above a commander's XP, that commander keeps the rank; a commander below it who has not earned it is promoted only at the new threshold.
- PROG-10: the badge is awarded after 30 continuous game-time minutes as the only active human with the Static above Pattern of Life; not awarded if a second human becomes active or the Static returns to Pattern of Life before then; a second commander whose unit is AUTO, or who sent no sim-reaching command within `presence.idle_handoff_min`, does not count as active (Q-ALN-27); awarding it writes no XP or merit.
- Balance harness (Q-TEST-2 target 5): alt-account XP farmer profiles are flagged and cannot move leaderboards beyond the bound set after the first runs.
- Season end: a campaign running past the planned end closes the season at campaign end; at `overtime_cap_days` the season closes and later points count in the new season.

## 8. Open questions
Decided and folded in: Q-ALN-1, Q-ALN-10, Q-ALN-14, Q-ALN-15, Q-ALN-16, Q-ALN-22 (GM drafts presets, Admin applies, PROG-7), Q-ALN-27 (active operator for PROG-10), Q-ALN-30 (AUTO assists, PROG-12). Still open: whether an AUTO unit's individual actions outside a completed job (a kill, a supply delivery, capture participation) earn the §2 XP and merit; Q-ALN-30 covers completed jobs only.
