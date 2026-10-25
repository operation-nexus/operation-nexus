# Entertainment review: run A (#345) and west-bank reach, 2026-10-25

Checkpoint and proposal review by the `entertainment-reviewer` (docs/quality/ENTERTAINMENT-REVIEW.md). Sources: harness #345 (run A: economy on, placeholder values) against baseline #337 (economy off), the previous checkpoint, ECONOMY.md, GAMEPLAY §0/§9, `balance/default.yaml`, `content/units/*.yaml`, `content/theaters/strait-1.yaml`. Nothing new was run; no overlay exists, so audiences are reconstructed from events. Estimates are marked.

## 1. Run A against baseline #337
- **Watcher / VOD:** from steamroll (6/6 wins) to stalemate: no campaign ended, no victory hold started. Offensives every 17-23 min keep action alive but there is no arc. Score 2 (est.).
- **Player:** A2 better for auto and striker (prime-50 143-145 s; baseline striker 326 s). Capturers never get a job (tail 72% / 98.6%); haulers and scouts wait 48-133 min. Score 2 (est.).
- **Site:** nothing ends, so no results to post. Score 1 (est.).
- **Cause (est.):** the economy is not binding. Income per hour (COAL 1281, ENEMY 1495) is below the floor alone (30 × 60 = 1800/h), so both pools sit at their storage caps and income is clipped (last pools 6.3-9.5k match what the storage keys allow for the held nodes). The Static spent about 17k of roughly 36k income, 85% of it rear-pool spend, so its units start at the rear and march 40-50 min to the west bank, the only coalition ground it can attack. The stalemate comes from the broken coalition capture loop plus a Static never short of stock; the income placeholders are too generous for the storage caps to matter.
- **Tick rate:** raid-300 ~150/s (baseline ~275), likely more enemy movers in transit with the live cap at 1000 (est.); the report needs a units-per-tick figure.

## 2. West-bank reach
**Premise correction.** There are 8 strategic nodes; 0.8 means 7, so every victory hold includes at least 2 of the 3 east-bank nodes (11.8-18.8 min from the Static's rear) and both crossings (25.7 min). Retaking any one breaks the hold, and capture takes about 2-6 min (est.). Holds are already contestable. The real problem is Offensives on the west bank: a 40-50 min march with a new Offensive every ~20 min means overlapping columns and few arrivals.

| Option | What viewers get | Risk | Cost |
|---|---|---|---|
| (a) Fast capture car | Quicker raids | Under rule 6a the coalition version needs schema, parser and handler; strike fighters likely kill it (85-100% of kills); speeds up coalition steamrolls | M |
| (b1) Hold timer scales with travel / (b2) count only contestable nodes | Nothing visible | Breaks the simple "hold 30 min"; invisible, feels game-y | S, rule change |
| (b3) Forward staging (EC-13): the director convoys stock forward and spawns at its nearest held base | Visible convoys and a building threat; raid targets for haulers and scouts | Director logic only; parity already holds; raids can starve it | S-M |
| (c) Road `speed_mult` | Shorter marches | Both sides faster (parity holds); content tuning, sweepable | XS |
| (d) Helicopters | Great clips | `capture.air_counts` false, needs a landing state; big build | L, later |

**Pick:** (b3) plus (c) as a sweep knob. Do not change the victory rules. Revisit (a) only if a sweep with staging still shows no arrivals. Defer (d).

## 3. Next sweep (pure tuning; prime-50 + raid-300, seeds 1-3, 24 h)
1. Get captures moving: `capture.garrison_mult=2.0`, `capture.time_s=90`, `economy.income.per_node.FOB=10`, `director.score.victory_hold_mult=2.0`.
2. Lower the Static's tempo: `director.source_spend_frac=0.002`, `director.cadence_windows=20`, `director.spend_frac.bravo=0.04`.
3. Make the economy binding: `economy.income.floor=15`, `economy.storage.floor=500`, `economy.storage.per_node.AIRBASE=1000`, `economy.storage.per_node.HQ=1000`.

Report holds started and broken; compare with run B (#346).

## 4. Watch items and questions
- Watch: income at the storage cap (clipped share per hour); Offensives with no arrival; Static ground units in transit vs tick rate.
- Q (design): should the director stage Static ground forces at forward bases (EC-13) before launching west-bank Offensives?
- Q (design): why does the capturer persona never get a job with the economy on? Check forward-spawn stock at coalition FOBs.
