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
| Rank | XP | Unlocks |
|---|---|---|
| O-1 | 0 | strike, recon, logi; `!target`, `!rtb`, `!wingman` |
| O-2 | 300 (~45–60 min active) | `!vector` (custom `!callsign` now unlocks after the first completed mission, Q-PROG-3) |
| O-3 | 1,500 | `!doctrine`; SEAD, artillery; `!order` (P4) |
| O-4 | 5,000 | Jammer, engineer, AWACS |
| O-5 | 15,000 | `!package` lead |
| O-6 | 40,000 | 1 theater asset/hour from personal merit |
The XP thresholds are placeholders. The balance harness sets them so that O-2 takes about 1 hour and O-4 about 2–4 weeks for a regular player.

## 4. Doctrines (Q-GD-3)
Chosen once per campaign at O-3 or above, from Air Superiority, Logistics Mastery, Recon/EW, and Garrison Command. Each gives 3 small perks (from the plans: cargo +15%, sensor +20%, drop tanks, …) plus **one signature ability** that only doctrine holders have. That's where the "only logistics expert" hero moments come from (C8). Holders get a doctrine badge on their unit symbol.

## 5. Cosmetics
Halo colors, trail styles, PiP placard ribbons, kill stencils, and voice presets (P4). The base icon color never changes (OV-2). Any monetization is cosmetic only (Q-BIZ-1).

## 6. Leaderboards
Separate boards per role, plus an overall board weighted by objective contribution. Campaign MVPs are listed in the Hall of Fame. Display uses approved callsigns only.
