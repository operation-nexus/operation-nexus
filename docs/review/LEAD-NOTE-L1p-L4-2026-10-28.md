# Lead note: L1p #483, L2 #484, L3 #485, L4 #486 (quiet-5 and overnight-0, b0bc4e3), 2026-10-28

This is a short lead-written note, not a full entertainment review. The question was narrow: how far does tuning alone get against the quiet-5 collapse, before the NX-474 brake? The numbers answer it, so no Opus review or probes were spent on it (token budget, L-40).

**Source:** a Sonnet agent copied the queue report numbers verbatim from #483–#486.

**Setup:** all four runs at b0bc4e3, which has NX-464/465 but not NX-474. 24 h, 6 seeds, base overrides B plus `combat.strike_structure_first=true`.

| Run | Change from L1p |
|---|---|
| L1p | none (control) |
| L2 | `capture.quiet_floor=0.3` |
| L3 | `director.provocation.escalate_threshold=20` |
| L4 | `director.cadence_windows=30` |

## quiet-5

| | L1p | L2 | L3 | L4 |
|---|---|---|---|---|
| Momentum % | 8.7 | 9.0 | 17.2 | 29.9 |
| Static captures (Offensive + Retake) | 20 + 1 | 21 + 1 | 24 + 0 | 20 + 1 |
| Offensives | 42 | 43 | 62 | 90 |
| `no_target` decision windows | 2690 | 2439 | 1356 | 1496 |
| Longest dry stretch median / max (min) | 1045 / 1357 | 894.5 / 1357 | 994.5 / 1356 | 385 / 1281 |
| Income/h, coalition / enemy | 79.7 / 785.0 | 84.2 / 768.3 | 173.5 / 711.3 | 222.4 / 749.7 |
| A2 median / tail (n) | 46 s / 18.2% (11) | 32 s / 12.5% (8) | 45 s / 14.3% (7) | 115 s / 9.1% (11), pass |

## overnight-0

All four runs are identical: A3 pass, 24 Offensives, funnel 24>8>0>0>0, 0 captures, momentum 41.0%.

## Reading

- **Tuning alone does not stop the collapse.** In every run the Static still takes about 20 nodes in 6 seed-days.
  - **L1p:** the control reproduces L1 at the new sha. Momentum is 8.7%, and `no_target` (the coalition holds nothing the Static may take) is about 2700 windows.
  - **L2:** faster coalition captures at low population (`capture.quiet_floor` 0.3) change almost nothing. The coalition has no retake path to speed up (Q-TD-94).
  - **L3 and L4:** these help a little. L4, with a 3× slower cadence floor, is the best of the four: momentum 30%, an A2 pass, and a median dry stretch of 385 min. But it still loses most of the map.
- **No tuning value is recommended for 5b from this batch.** The brake (NX-474) and the retake path (NX-475) remain the fix.
  - `director.cadence_windows` 30 is a candidate to recheck at the NX-474 sha if quiet-5 still drifts too fast in S0 (#493).
  - It is global, so prime must be checked too.
- **Caveat (L-37):** these runs predate NX-474. S0 (#493) at 8f9a5ff is the first quiet-5 measurement with the brake.
