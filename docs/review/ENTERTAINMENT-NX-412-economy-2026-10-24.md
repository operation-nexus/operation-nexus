# Entertainment proposal review: NX-412 force economy (ECONOMY.md draft), 2026-10-24

Proposal-mode review by the `entertainment-reviewer` agent (docs/quality/ENTERTAINMENT-REVIEW.md) of the first draft of docs/specs/ECONOMY.md, against Q-TEST-11 and docs/review/ENTERTAINMENT-steamroll-2026-10-24.md. No harness run; every effect is an **estimate**. The lead applied changes 1-5 to the draft (see "Applied" at the end).

## 1. Effect on the Q-TEST-11 signals
| Signal | Moved by | Estimate |
|---|---|---|
| 1 Static pressure on held ground | EC-1 floor, EC-7 waves | Mostly untouched: more Static units, but nothing points them at coalition nodes (probes: 0 capture starts on held nodes in 4 of 4 runs) |
| 2 Contested final hold | EC-9 | Likely moves, if the Static can still afford an operation at the end (risk B) |
| 3 Momentum swing | indirect | Only if signal 1 moves |
| 4 Late Static force | EC-1, EC-7 | Moves; caveat: waves lower the hour-1 peak, so "under 25% of peak" can pass from a smaller peak alone |

## 2. Risks by audience
- **A. Newcomers grounded first (player, watcher):** paying in ascending unit id grounds the newest units, usually the newest viewers'.
- **B. Static death spiral at the climax (all):** floor income lands at the rear source, which EC-7's surplus excludes (Q-TD-5); a Static holding only its rear has budget 0 exactly when EC-9 needs it. The reserve term also zeroes the budget when the army is large.
- **C. Big crowd capped in practice (TS-1):** income does not grow with viewers and hauling moves stock without adding it, so the coalition army tops out near income ÷ upkeep; the marginal viewer is benched. Not a rubber band, but felt.
- **D. Coalition spiral, finite sanctuary (Q-TD-21):** EC-11 sizes the floor for the 0-viewer garrison only; losing nodes grounds units, which loses more nodes. Worst picture: the whole crowd parked and grey.
- **E. Grounded units on screen (watcher, VOD):** parked Static reads as a frozen map; a grounded unit driving home reads as a bug without an icon and reason. Upside: a mass RTB after a convoy raid is a clean clip.
- **F. Site:** per-side economy charts are good content; grounded time per player would shame individuals, so per side only.

## 3. Lead decisions
- Q-TD-20 (income at the source): change: the Static budget must count the source pool or a share (B).
- Q-TD-21 (coalition sanctuary finite): agree with a guard: floor covers the garrison plus a minimum viewer force.
- Q-TD-22 (upkeep by kind, per window): agree.
- Q-TD-23 (home and grounding): change the order: AI garrison first, then viewer units idle longest, newest viewer units last; deterministic sort by (class, last order tick, id).
- Q-TD-24 (spend fraction and reserve): agree with a cap so a minimum operation cadence survives (B).
- Q-TD-25 (hold public, in EnemyView): agree; best clip moment in the design.

## 4. Ranked spec changes
1. Static budget sees its source (a scaled share of the rear pool, or staging from the source).
2. `director.score.income_node_mult` on Offensive/Retake against coalition-held income nodes: the only lever on signal 1.
3. Grounding order as above; the spawn reply warns when the home can't pay its next upkeep and names the fix; a grounded icon and reason on the overlay.
4. Coalition anti-spiral: EC-11 covers a minimum viewer force; watch item "coalition units over 50% grounded for 30 min" (PROPOSED).
5. Operation cadence floor: at least one operation affordable every N windows while the Static holds its HQ (N swept); report signal 4 against start stock too.

**Harness metrics for NX-411:** Static operations per hour, gap between Offensives and how many hit coalition-held nodes; Static budget per window split source pool vs base surplus; grounded unit-minutes per side (viewer vs AI) and grounded share by join-order quartile; grounded churn per hour; peak coalition army vs viewer count across prime-50, raid-300, surge-500; Static operations during each victory hold, holds broken; share of floor income cut by convoy raids.

Watch items carried forward: Static economy death spiral, uncontested final hold, BRAVO with under 10 live units, STRIKE_BRIDGE never firing.

## Applied (lead, 2026-10-24)
Changes 1-5 are in the draft as EC-7 (source share, Q-TD-26, amends Q-TD-5), EC-12 (income-node multiplier), EC-6 (grounding order, spawn warning, overlay icon), EC-11 (minimum viewer force) and EC-7's cadence floor. The metrics are listed in ECONOMY §4 for NX-411.
