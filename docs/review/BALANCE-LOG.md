# Balance log

One appended entry per balance-harness run, newest at the bottom (Q-DEV-42, owner 2026-11-04). It replaces the separate `HARNESS-<id>-<date>.md` review file per run. A run gets its own review file only when it needs more than an entry: a new method, or an owner question with several options.

Each balance question gets one same-sha A/B, then a PROPOSED value and a Q-row. There's no second cycle on the same question until real viewers have played (Q-DEV-42).

## Entry format

```
### <run id> #<issue>, <date>, sha <short sha>
- Question: one line.
- Run: profiles, seeds, hours, overrides.
- Replay check: matches <earlier run> / new hashes because <change>.
- Result: 2–4 lines with the numbers that answer the question.
- Decision: what changes (or nothing), with Q-row / NX id.
```

## Entries

### O0 #620, 2026-11-04, sha aa56803
- Question: which two strategic nodes form the 6-of-8 raid plateau (N0)?
- Run: raid-300 vs raid-300-agency, seeds 1–12, 24 h, shipped rules.
- Replay check: all 24 runs match N0, final state hashes included.
- Result: all 8 stalled seed-arms miss exactly fob-n-e and fob-s-e, the FOBs one road link from the Static HQ. At `victory_node_frac` 0.80 of 8 (7), 9 of 16 wins hold 7 with one east FOB still Static. Full review: [`HARNESS-O0-2026-11-04.md`](HARNESS-O0-2026-11-04.md).
- Decision: Q-TD-142 asked (threshold, ease the east FOBs, or keep).

### P0 #622, 2026-11-04, sha aa56803
- Question: Q-TD-142 (a): what happens at 6 of 8 (`campaign.victory_node_frac=0.75`)?
- Run: O0 with that one override.
- Replay check: new hashes in every seed, as expected (the threshold changes when holds start).
- Result: 23 of 24 seed-arms win (O0: 16), 0 steamroll flags, median win 0.4–0.8 h sooner, shortest 1.75 h. One new stall (raid-300 s10); raid-300-agency s8 wins only at 22.23 h. Full review: [`HARNESS-P0-2026-11-04.md`](HARNESS-P0-2026-11-04.md).
- Decision: owner chose Q-TD-142 (b), 0.75 (NX-506). Raid-stall thread closed (Q-DEV-40); next is the 72 h reduced acceptance run.

### Q0b #648, 2026-11-05, sha 8f814e6
- Question: does the P1-exit reduced acceptance run (Q-TEST-10) pass A1–A4 on the north-up map (NX-507)? It re-runs #631, which failed at 27 of 60 runs when the runner restarted.
- Run: overnight-0, quiet-5, prime-50, evening-150, raid-300, surge-500; seeds 1–10; 72 h; shipped rules (`victory_node_frac` 0.75, Q-TD-142 (b)); economy on, no unlimited side; 401.5 min wall.
- Replay check: new hashes. First run at this config hash (`1920af11…`, NX-507 mirrored strait-1); #631 never posted a report at a8e6e59.
- Result:
  - **A1 fails at 0, 5 and 50 viewers:** overnight-0, quiet-5 and prime-50 end 10/10 by TIME_LIMIT. No defeat run starts, the coalition never loses every strategic node, and momentum ends at 51 %, 51 % and 36 %.
  - **A1 passes at 150, 300 and 500 viewers:** evening-150 9/10 VICTORY (median 15.2 h), raid-300 10/10 (2.8 h), surge-500 10/10 (1.6 h). 0 of 29 won seeds are flagged as a steamroll.
  - **A2 fails at every profile with newbies:** the median is under 480 s except at surge-500 (3248 s), but 28–61 % of newbies wait over 900 s (needs ≤ 10 %).
  - **A3 and orders pass. A4** stays suspended (Q-SIM-92).
  - At 0 viewers the Static's 119 Offensives produce 37 strikes, 1 defences-down and 0 captures; the idle floor holds the coalition's nodes by design.
- Decision: P1 exit is not met. Owner question on #412: whether A1 applies to the low-crowd profiles at all, or the low-crowd stalemate needs balance work. The high-crowd picture matches P0 at 0.75 (every raid and surge seed won, 0 steamroll), so NX-507 holds.

### Q0c acceptance (#667, 2901d4c), 2026-11-06
- Question: does the reduced acceptance run pass A1–A4 under the NX-510 low-crowd rule (below 150 viewers A1 judges every seed by the collapse fields, whatever its ending)? It is also the baseline for the queued A/Bs #668 (T1 `capture.quiet_ref=100`), #669 (T2 `director.provocation.half_life_s=1800`) and #670 (T4 `logistics.ai_trucks.max_live=6`).
- Run: sha 2901d4c4, config hash `1e4fefaf…`; overnight-0, quiet-5, prime-50, evening-150, raid-300, surge-500; seeds 1–10; 72 h; 12 workers; shipped config, economy on, no unlimited side; 465.9 min wall. Source: the harness comment on #667 (the posted copy is truncated; the full `report.md` is on the harness PC).
- Replay check: not compared. The config hash differs from Q0b (`1920af11…`) and the sha is new, so new hashes are expected.
- Result: **acceptance not met: A1 fails at quiet-5 and evening-150, A2 fails at every profile with newbies.** Every number below is read from the report unless marked (inferred).

| Profile | A1 | A2 (median s, tail > 900 s) | A3 | A4 | Orders | Outcomes | Median campaign h |
|---|---|---|---|---|---|---|---|
| overnight-0 | pass (10/10 no collapse) | no data (0 newbies) | pass (max 1 strategic node lost in 12 h) | suspended (Q-SIM-92) | pass | TIME_LIMIT 10 | 72.0 |
| quiet-5 | **fail (9/10 no collapse)** | fail (105 s; 16.0 %, 12/75) | no row | suspended | pass | TIME_LIMIT 10 | 72.0 |
| prime-50 | pass (10/10 no collapse) | fail (283 s; 40.5 %, 658/1626) | no row | suspended | pass | TIME_LIMIT 10 | 72.0 |
| evening-150 | **fail (8/10 ended, need 85 %)** | fail (193 s; 32.1 %, 799/2487) | no row | suspended | pass | VICTORY 8, TIME_LIMIT 2 | 22.9 |
| raid-300 | pass (10/10) | fail (776 s; 46.4 %, 129/278) | no row | suspended | pass | VICTORY 10 | 2.3 |
| surge-500 | pass (10/10) | fail (963 s; 50.4 %, 127/252) | no row | suspended | pass | VICTORY 10 | 1.9 |

  A3 appears only for overnight-0 in the posted report. 0 sim crashes and 0 harness errors in every profile; steamroll flags 0/8, 0/10, 0/10 at evening-150, raid-300, surge-500 (evening-150 s6 fired 2 signals, below the threshold). A5, A6 and the Gini target are not measurable yet.
- Low-crowd numbers:
  - **overnight-0 (NX-514):** the Static launched 119 Offensives (all on coalition-held nodes, gap median 360 min, night_cap blocked 360 decision windows). They produced 37 strikes, 1 defences-down, 0 capture starts, 0 captures; 0 coalition captures, 0 min with no strategic node. The funnel is the same as Q0b's (119 / 37 / 1 / 0).
  - **quiet-5:** 9/10 seeds never collapsed, 1 did. The posted report doesn't say which collapse field fired. The coalition spent 0.0 min with no strategic node, so the sanctuary-HP field is the likelier one (inferred, not read). Defeat runs: 4 started, 4 reset, 0 defeats, longest 15.5 min, 6.0 min paused; SANCTUARY_AT_RISK 0.03 per h. The Static launched 287 Offensives (78 captured by the target's count); the coalition made 100 captures. Mean starved node-minutes 781.8.
  - **prime-50 (T4):** mean starved node-minutes 1066.5 (evening-150 is higher at 1149.2). Coalition starving job-min 9166 vs stocking 7591 (raid-300 also has starving above stocking, 188 vs 182). 36 coalition trucks lost near the sanctuary (0.05 per h; quiet-5 3, every other profile 0). Coalition deliveries 51.73 per run-hour. Static income lost to the storage clip 1,975,218 of 3,306,040 due; coalition 1,068,100 of 1,858,605. Coalition ended 35.4 % momentum, the lowest of the six.
  - NX-504, NX-505 and NX-512 metrics are not in the posted (truncated) comment; check the full `report.md` before citing them.
- Changed since Q0b (only metrics both carry; Q0b gave fewer numbers, so many rows can't be compared):
  - Outcomes: low-crowd profiles unchanged (TIME_LIMIT 10/10 each). evening-150 went 9/10 VICTORY to 8/10, median 15.2 h to 22.9 h (seeds 4 and 8 reached the limit). raid-300 10/10, 2.8 h to 2.3 h. surge-500 10/10, 1.6 h to 1.9 h.
  - A1: overnight-0 and prime-50 now pass and quiet-5 fails (all three failed in Q0b), because the rule changed to the collapse fields (NX-510), not because the ending changed. evening-150 went from pass to fail.
  - Momentum: overnight-0 51 to 51.1 %, quiet-5 51 to 48.2 %, prime-50 36 to 35.4 %.
  - A2: Q0b's tail was 28–61 % over 900 s; now 16.0–50.4 %. surge-500 median 3248 s to 963 s. Q0b's median was under 480 s everywhere else, so raid-300 (776 s) now fails the median test too (inferred from Q0b's "under 480 s"; the exact Q0b values aren't in its entry).
  - overnight-0 Offensive funnel: identical to Q0b (see above).
- Compare #668–#670 against: this run, same sha and config hash `1e4fefaf…`, seeds 1–10, 72 h, per profile. T1: quiet-5 A1 collapse seed, coalition captures (100), Static Offensives (287) and captures, newbie median/tail. T2: the pressure and provocation-driven numbers at quiet-5 and prime-50 (Offensives 287 and 1253, sitreps per h) and evening-150 outcomes (8/10, 22.9 h). T4: prime-50 starved node-minutes (1066.5), starving job-min (9166), trucks lost (36), coalition deliveries (51.73 per h) and the evening-150 starved figure (1149.2).
- Surprises and regressions:
  - evening-150 A1 now 8/10 (Q0b 9/10) with 2 time-limit seeds; this shows against a changed sha and config, and the report doesn't attribute it.
  - quiet-5 has one collapse seed under a rule that needs every seed.
  - Supply starvation is highest at evening-150 (1149.2), above prime-50 (1066.5).
  - A2 fails everywhere; raid-300 and surge-500 medians (776 s, 963 s) are above the 480 s target.
- Decision: none from this entry. P1 exit isn't met on these numbers (A1 at quiet-5 and evening-150, A2 everywhere). The queued A/Bs (#668–#670) are the next step; no tuning proposed here (Q-DEV-42).

### T1: capture.quiet_ref 50→100 vs Q0c (#668 vs #667, 2901d4c), 2026-11-06
- Question: does raising `capture.quiet_ref` from its shipped 50 (`balance/default.yaml:97`) to 100, the top of its tuning range (`contracts/config/balance.json`, `x-tune` max 100), soften the Static's low-population brake at 50 viewers and move the quiet-5 / prime-50 stalemate? From the NX-378 low-crowd review (§4); the A/B arm for Q0c (#667).
- Run: sha 2901d4c4, config hash `1c41b0af…` (Q0c: `1e4fefaf…`); overnight-0, quiet-5, prime-50; seeds 1–10; 72 h; 12 workers; `set: capture.quiet_ref=100`; economy on, no unlimited side; 289.7 min wall. Source: the harness comment on #668 (the posted copy is truncated; the full `report.md` is on the harness PC). Arm A is the Q0c entry above, same sha and seeds; its posted copy is truncated before the per-seed tables, so per-seed comparisons exist only for T1.
- Replay check: not compared (different config hash). overnight-0 matches Q0c in every figure compared (funnel 119 / 37 / 1 / 0, momentum 51.1 %, income, coalition 0 captures).
- Side effect to keep in mind: `quiet_ref` also sets where the quiet-stream capture-time multiplier reaches 1.0 (`capture.quiet_floor`, `balance.json:458`) and the fade of AI wingmen on a landed STRIKE claim (`tasking.wingmen_max`, `balance.json:1983`), so this arm moves three things, not only the night-cap spacing.
- Result: **T1 cut the Static's offensive pressure at 50 viewers but moved no acceptance target, and it raised sanctuary and defence-down pressure at prime-50.** A = Q0c, B = T1. Numbers are pooled over 10 seeds unless marked.

| Metric | overnight-0 A / B | quiet-5 A / B | prime-50 A / B |
|---|---|---|---|
| A1 | pass / pass (10/10 no collapse) | fail / fail (9/10; collapse field not named in either posted report) | pass / pass (10/10) |
| Outcomes | TIME_LIMIT 10 / 10 | TIME_LIMIT 10 / 10 | TIME_LIMIT 10 / 9, VICTORY 0 / 1 (seed 7, peak 46 viewers) |
| Median campaign h | 72.0 / 72.0 | 72.0 / 72.0 | 72.0 / 72.0 |
| Momentum % | 51.1 / 51.1 | 48.2 / 49.2 | 35.4 / 44.8 |
| Static Offensives launched | 119 / 119 | 287 / 253 | 1253 / 811 |
| Offensive funnel, captured (RETAKE) | 0 / 0 | 78 (0) / 71 (0) | 191 (9) / 174 (3) |
| Static strategic-node captures of coalition nodes | no data (A) / 0 | no data (A) / 85 (5–11 per seed) | no data (A) / 272 (1–37 per seed) |
| Coalition captures | 0 / 0 | 100 / 89 | 317 / 261 |
| Decision windows blocked by night_cap | 360 / 360 | 34584 / 33315 | 9437 / 22144 |
| STAGING per h; Static sitreps SANCTUARY_AT_RISK per h | 0.17; 0 / 0.17; 0 | 0.41; 0.03 / 0.36; 0.02 | 2.11; 1.05 / 1.43; 1.27 |
| Coalition defences-down fires (minutes) | 2 (2125.1) / 2 (2125.1) | 572 (33730.4) / 559 (39627.2) | 594 (20257.7) / 893 (26592.4) |
| Coalition 0-strategic-node minutes | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| Defeat runs started, longest (min) | 0 / 0 | 4, 15.5 / 1, 5.7 | 0 / 0 |
| A2 (median s; tail over 900 s) | no data (0 newbies) | 105; 16.0 % (12/75) / 132; 20.3 % (13/64), fail / fail | 283; 40.5 % (658/1626) / 282; 38.8 % (556/1434), fail / fail |
| Starved node-min (mean) | 0.0 / 0.0 | 781.8 / 831.1 | 1066.5 / 770.3 |
| Coalition trucks lost near sanctuary | 0 / 0 | 3 / 4 | 36 / 18 |

  - **Moved as intended:** at prime-50, Offensives fell 1253 to 811 (-35 %), captured Offensive and RETAKE targets 200 to 177 (-12 %), coalition captures 317 to 261, and night_cap blocked 22144 windows (9437 in A). At quiet-5 Offensives fell 287 to 253 (-12 %) and night_cap blocks barely changed (34584 to 33315). prime-50 momentum 35.4 to 44.8 %, one VICTORY in 10 (0 in A).
  - **Did not move:** every A1 verdict is the same (quiet-5 still 9/10); every seed but one still ends at TIME_LIMIT; median campaign time is 72.0 h in both arms; A2 still fails at both profiles (quiet-5 tail worse, 16.0 to 20.3 %, prime-50 tail 40.5 to 38.8 %, medians within 27 s).
  - **Harm signals at prime-50:** coalition defences-down fires 594 to 893 (+50 %) and 20257.7 to 26592.4 min; SANCTUARY_AT_RISK 1.05 to 1.27 per h. Coalition deliveries 51.73 to 44.15 per h (quiet-5 8.94 to 9.06). Offsetting: starved node-min 1066.5 to 770.3, trucks lost 36 to 18, coalition starving job-min 9166 to 5587.
  - **Noise:** the only outcome change is prime-50 seed 7 (peak 46 viewers, 36 newbies, against 108–154 peak in most other seeds); one seed in ten does not support a claim. Quiet-5's A2 sample is 64 newbies against 75, with per-seed counts of 1–13, so its 4.3-point tail change is inconclusive. The momentum jump at prime-50 (+9.4 points) has no per-seed split in the posted report and rests on that one victory seed plus the pressure drop (inferred, not read). The quiet-5 collapse seed isn't named in either arm.
  - Not comparable: Q0c's per-seed tables (strategic nodes held, early hours, Static strategic captures per seed) are cut from the posted copy.
- Decision: **reject `quiet_ref=100` as a fix for the A1 stalemate; keep 50.** It lowers Static Offensives at 50 viewers (-35 %) but changes no A1 verdict, no median time and no A2 verdict, and raises prime-50 defence-down fires by 50 %. Per Q-DEV-42 the question gets no second cycle until real viewers have played. Compare with T2 (#669) and T4 (#670) on the same Q0c baseline. No Q-row or NX id opens from this entry.

### T2: director.provocation.half_life_s 900→1800 vs Q0c (#669 vs #667, 2901d4c), 2026-11-06
- Question: with the shipped 900 s half-life (`balance/default.yaml:272`) a solo player gets about an hour of Offensives and then 4–5 h of Pattern of Life. Does 1800 s keep the Static engaged at low crowds without breaking the other targets? From the NX-378 low-crowd review (§4, T2), which suggested about 2,700; 1800 is the top of the key's tuning range (`contracts/config/balance.json`, `x-tune` max 1800.0). The A/B arm for Q0c (#667).
- Run: sha 2901d4c4, config hash `8fd2c153…` (Q0c: `1e4fefaf…`); overnight-0, quiet-5, prime-50; seeds 1–10; 72 h; 12 workers; `set: director.provocation.half_life_s=1800`; economy on, no unlimited side; 300.1 min wall. Source: the harness comment on #669 (the posted copy is truncated; the full `report.md` is on the harness PC). Arm A is the Q0c entry above, same sha and seeds. Its posted copy is cut before the per-seed tables, so per-seed comparisons exist only for T2.
- Replay check: not compared (different config hash). overnight-0 matches Q0c in every figure compared (funnel 119 / 37 / 1 / 0, momentum 51.1 %, STAGING 0.17 per h, coalition 0 captures, income).
- Result: **T2 moved no acceptance target. It raised Static Offensives at quiet-5 (287 to 379) but not at prime-50, and it did not shorten the longest quiet stretch. It also shows supply and sanctuary-pressure harm.** A = Q0c, B = T2. Numbers are pooled over 10 seeds unless marked.

| Metric | overnight-0 A / B | quiet-5 A / B | prime-50 A / B |
|---|---|---|---|
| A1 | pass / pass (10/10 no collapse) | fail / fail (9/10; collapse field not named in either posted report) | pass / pass (10/10) |
| Outcomes | TIME_LIMIT 10 / 10 | TIME_LIMIT 10 / 10 | TIME_LIMIT 10 / 10 |
| Median campaign h | 72.0 / 72.0 | 72.0 / 72.0 | 72.0 / 72.0 |
| Momentum % | 51.1 / 51.1 | 48.2 / 37.2 | 35.4 / 31.2 |
| Static Offensives launched | 119 / 119 | 287 / 379 | 1253 / 1249 |
| Offensive funnel, captured (RETAKE) | 0 / 0 | 78 (0) / 65 (0) | 191 (9) / 151 (11) |
| Static strategic-node captures of coalition nodes | no data (A) / 0 | no data (A) / 82 (2–11 per seed) | no data (A) / 246 (14–40 per seed) |
| Coalition captures | 0 / 0 | 100 / 75 | 317 / 227 |
| Longest stretch without an Offensive, median (max), min | 360.0 (376.0) / 360.0 (376.0) | 382.0 (659.0) / 382.0 (713.0) | 227.5 (328.0) / 224.5 (266.0) |
| Gap by tier, Pattern of Life (n, median min) | 109, 360.0 / 109, 360.0 | 66, 153.5 / 51, 214.0 | 54, 44.0 / 18, 58.0 |
| Decision windows blocked by night_cap | 360 / 360 | 34584 / 32495 | 9437 / 9915 |
| STAGING per h; SANCTUARY_AT_RISK per h | 0.17; 0 / 0.17; 0 | 0.41; 0.03 / 0.54; 0.19 | 2.11; 1.05 / 1.97; 9.83 |
| Coalition defences-down fires (minutes) | 2 (2125.1) / 2 (2125.1) | 572 (33730.4) / 493 (36678.6) | 594 (20257.7) / 551 (24528.6) |
| Coalition 0-strategic-node minutes | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| Defeat runs started, longest (min), paused (min) | 0 / 0 | 4, 15.5, 6.0 / 4, 19.1, 1.4 | 0 / 0 |
| Victory holds | 0 / 0 | 0 / 0 | 0 / 3 (all broken, all in seed 7) |
| A2 (median s; tail over 900 s) | no data (0 newbies) | 105; 16.0 % (12/75) / 132; 30.9 % (29/94), fail / fail | 283; 40.5 % (658/1626) / 187; 37.8 % (685/1812), fail / fail |
| Starved node-min (mean) | 0.0 / 0.0 | 781.8 / 2357.2 | 1066.5 / 1710.9 |
| Coalition deliveries per h | 0.20 / 0.20 | 8.94 / 8.27 | 51.73 / 38.98 |
| Coalition trucks lost near sanctuary | 0 / 0 | 3 / 5 | 36 / 39 |

  - **Moved:** at quiet-5 Offensives rose 287 to 379 (+92, +32 %), STAGING 0.41 to 0.54 per h, momentum fell 48.2 to 37.2 %, coalition captures fell 100 to 75. Static strategic-node captures at quiet-5 and prime-50 can't be compared (Q0c's per-seed table is cut); T2's figures are the per-seed "Strategic node losses" summed: quiet-5 9+2+10+5+7+11+8+10+10+10 = 82, prime-50 31+40+17+20+19+14+17+20+31+37 = 246.
  - **Did not move:** every A1 verdict is the same (quiet-5 still 9/10); every seed in every profile still ends at TIME_LIMIT at 72.0 h; A2 still fails at both profiles. The median longest stretch without an Offensive at quiet-5 is 382.0 min in both arms, and night_cap still blocks 32495 windows (A: 34584). At prime-50 Offensives are 1249 against 1253. Hour 4 of the early-hours table shows 6 of 10 quiet-5 seeds back in PATTERN_OF_LIFE (s1, s2, s4, s5, s8, s9); the Q0c table is cut, so there is no A figure to compare.
  - **Harm signals:** quiet-5 starved node-min 781.8 to 2357.2, coalition starving job-min 6512.0 to 21224.0 (stocking 26161.0 to 27915.0). prime-50 starved node-min 1066.5 to 1710.9, coalition deliveries 51.73 to 38.98 per h, SANCTUARY_AT_RISK 1.05 to 9.83 per h, defences-down minutes 20257.7 to 24528.6, starving job-min 9166.0 to 15186.0. quiet-5 A2 tail 16.0 to 30.9 %.
  - **Not clearly harm:** prime-50 momentum fell 35.4 to 31.2 %, prime-50 coalition captures 317 to 227, and 3 victory holds (A: 0) in seed 7 (209.3 min at 6+ nodes), all broken. Fewer coalition captures and lower momentum are more Static pressure, which is the aim. They moved no target.
  - **Noise:** quiet-5 A2 samples are 75 against 94 newbies, with per-seed counts of 2–16, so the tail change is inconclusive. The quiet-5 collapse seed isn't named in either arm. The report doesn't attribute any change to the half-life; the prime-50 SANCTUARY_AT_RISK jump (about 9x) is read as measured, not explained. 12200.2 s of slot wait is recorded for T2 (Q0c: 0.0 s) and doesn't change results.
- Decision: **PROPOSED reject `half_life_s=1800`; keep 900.** It changes no pass/fail (A1 quiet-5 fail/fail, prime-50 and overnight-0 pass/pass, A2 fail/fail), no outcome and no median time. The one gain is +32 % Offensives at quiet-5, and the longest-stretch median doesn't move (382.0 min) while night_cap blocks most windows, so the hours-long lulls remain. It also triples quiet-5 starved node-min. This is a judgement call for the owner: a reader who counts more Static pressure at 5 viewers (and lower coalition momentum) as the goal could call it a partial success. By target pass/fail it is a no-op. Per Q-DEV-42 the question gets no second cycle until real viewers have played. The numbers point at night_cap spacing, not the provocation decay, as the binder at quiet-5 (T3 and T1 touch it). Compare with T1 (#668) and T4 (#670) on the same Q0c baseline. No Q-row or NX id opens from this entry; the lead records the PROPOSED verdict.
