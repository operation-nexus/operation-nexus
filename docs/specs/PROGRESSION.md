# SPEC: Progression


> **All numeric values in this spec are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). They become real only after the balance harness validates them.
Status: Draft · Tracker: NX-210…NX-224 · Inputs: P725–971, C5–10

## 1. Principles
Progression is horizontal. Ranks unlock **options and force multipliers**, never raw hp or damage. Two tracks: a **Lifetime Service Record** (rank, callsign, cosmetics, ribbons) and **Campaign Merit**, which resets each war (Q-PROG-1).

## 2. XP sources (Q-PROG-2) — initial values
| Action | XP | Merit |
|---|---|---|
| Sortie completed (survived, objective attempted) | 40 | 10 |
| Supply delivered (per 10 stock) | 15 | 5 |
| Node capture participation | 60 | 20 |
| Theater objective completed (participant) | 80 | 30 |
| Recon paint → assist | 15 | 5 |
| Kill | 10 | 3 |
| Spawning | 0 | 0 |

**PROG-1** Diminishing returns: after `progression.xp_hour_soft_cap` (PROPOSED 400 per real hour), further XP is × `progression.xp_over_cap_mult` (PROPOSED 0.25).
**PROG-2** No persistent XP when fewer than 2 distinct humans are active (stops solo farming with alts), and none until the commander's first completed sortie.
**PROG-3** Merges never sum XP (IDENTITY §4).

## 3. Ranks (one table; resolves critique #8 and #14)
`O-1`…`O-6` are **internal rank ids** (config, contracts, DB). Viewers see the **themed display name** (Q-NAME-1; working names, final list in the brand guide NX-274). No real military rank titles appear on stream (Q-PROD-5).

| Rank id | Display name (working) | XP | Unlocks |
|---|---|---|---|
| O-1 | Recruit | 0 | Striker, Scout, Hauler (strike, recon, logi); `!target`, `!rtb`, `!rebase`, `!stance`, `!wingman` |
| O-2 | Operator | 300 (~45–60 min active) | `!vector`. (Custom `!callsign` is **not** rank-gated: it unlocks after the first completed mission, Q-PROG-3.) |
| O-3 | Specialist | 1,500 | `!doctrine`; SEAD, artillery; `!rally` (Q-SUP-6); `!order` (P4) |
| O-4 | Signal Lead | 5,000 | Jammer, engineer, AWACS |
| O-5 | Wave Commander | 15,000 | `!package` lead |
| O-6 | Clearwave Marshal | 40,000 | 1 theater asset/hour from personal merit (whether merit is spendable is open, Q-PROG-7) |
The XP thresholds are placeholders. The balance harness sets them so that O-2 takes about 1 hour and O-4 about 2–4 weeks for a regular player.

## 4. Doctrines (Q-GD-3)
Chosen once per campaign at O-3 or above, from Air Superiority, Logistics Mastery, Recon/EW, and Garrison Command. Each gives 3 small perks (from the plans: cargo +15%, sensor +20%, drop tanks, …) plus **one signature ability** that only doctrine holders have. That's where the "only logistics expert" hero moments come from (C8). Holders get a doctrine badge on their unit symbol.

## 5. Cosmetics
Halo colors, trail styles, PiP placard ribbons, kill stencils, and voice presets (P4). The base icon color never changes (OV-2). Any monetization is cosmetic only (Q-BIZ-1).

## 6. Leaderboards
Separate boards per role, plus an overall board weighted by objective contribution. Campaign MVPs are listed in the Hall of Fame. Display uses approved callsigns only.
- **Three horizons (Q-UX-3):** war (resets each war), season (resets each season), lifetime (never resets).
- **Seasons (Q-UX-2):** ~4–8 weeks, several campaigns. Season boards reset; lifetime ranks don't. Season-end recap plus cosmetic badges.
- **Removal:** banned or confirmed-cheating operators are removed from every board by a mod/admin action (audited). Their entries are hidden and the board recomputed; ledger rows are not deleted.
