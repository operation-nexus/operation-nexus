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
