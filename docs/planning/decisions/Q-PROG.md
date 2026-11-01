# Decided questions: Q-PROG

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Progression & identity

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROG-1 | Are ranks lifetime and Campaign Merit per-war (both tracks)? | Yes, both tracks. | ✅ 2026-10-17: Lifetime rank + per-war merit (A) |
| Q-PROG-2 | XP sources? | Mission completion, supply delivered, captures, recon assists ≥ kills. Hourly diminishing returns. | ✅ 2026-10-17: Objective/supply/capture/recon ≥ kills; hourly diminishing returns (A) |
| Q-PROG-3 | Minimum account age or activity before persistent XP? | Persistent XP starts after the first completed mission. Accounts under 24 h old count at 0.5× toward director power. | ✅ 2026-10-17: A. Persistent rank counts after the first completed mission; new accounts count 0.5× toward director power for 24 h. **Custom callsign unlocks after the first completed mission** (moderated, 1 change per 30 days), not at O-2. No captcha (owner prefers no verification step). Anti-farming is layered instead (NX-277). |
| Q-PROG-4 | Account merge rule? | **Never sum XP.** Keep the max of each stat. One merge per 30 days. OAuth-proven only. | ✅ 2026-10-17: Never sum XP; per-stat max; OAuth-proven (A) |
| Q-PROG-5 | Is cross-platform linking needed at launch? | No. Launch on Twitch only. Linking arrives with YouTube in beta. | ✅ 2026-10-17: A, linking ships with YouTube in public beta |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROG-6 | PROG-2 ("no XP with <2 humans") contradicts the VISION "night-owl hero" and TS-3 | drop it and rely on the cap, the first-mission gate and NX-277 | ✅ 2026-10-18: Drop PROG-2's <2-humans rule (conflicts with VISION night-owl hero and TS-3). Anti-farming relies on NX-277 layers: first-completed-mission gate, hourly diminishing XP, platform account age where the API exposes it, first-seen age, lockstep anomaly flags, mod XP void. Add a cosmetic 'Held the Line' badge for defending as the only active human (no bonus XP, so it can't be farmed). |
| Q-PROG-7 | Is Merit only a score, or can it be spent? (The O-6 "asset from merit" conflicts with ADR-0011's no-currency rule) | score only; abilities run on cooldowns | ✅ 2026-10-18: Merit is a score only, never spent (ADR-0011). Ranks unlock abilities that run on cooldowns (O-6 = may call 1 theater asset per cooldown, default 1 h). The rank table (thresholds, unlocked abilities, cooldowns) and XP source values are data in config, editable by admin/GM from the Command Center as named presets with validation and an audit log; changes are versioned with the campaign config hash. Naming/glossary unification tracked as NX-315. |
| Q-PROG-8 | What metric ranks each board, per role? | role contribution; overall = merit | ✅ 2026-10-18: Per-role boards rank by role contribution (logistics: supplies delivered; recon: spotted enemies later engaged by friendlies; CSAR: rescues completed; combat: threat-weighted kills + objective damage); overall board ranks by Merit. Assists count. Two views per board: season total (primary) and per-hour-played. Metric per board defined in config. |
| Q-PROG-9 | What happens when a season ends mid-campaign? | the season ends at the next campaign end | ✅ 2026-10-18: Season ends at the end of the campaign running on the planned end date. Safety cap season.overtime_cap_days (proposed default 14): past it the season closes and the running campaign carries into the new season, with points from then on counting there. HUD/site show 'Season ends after this campaign' during overtime. |
| Q-PROG-10 | Should scouting new information earn XP (NX-384)? | Yes, small and once per entity per cooldown coalition-wide, diminishing per sortie; paint → assist stays the main reward | P2 | ✅ 2026-10-23 (owner): discovery credit for a facility marker first discovered, a base change first seen in a while, and a unit first tracked by the side, smallest for units; each entity pays once per cooldown for the whole coalition; per-sortie diminishing returns and cap; AUTO earns none. Values PROPOSED. Spec: PROGRESSION §2, PROG-13. |
