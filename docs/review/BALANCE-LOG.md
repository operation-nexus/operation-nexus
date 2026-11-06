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
