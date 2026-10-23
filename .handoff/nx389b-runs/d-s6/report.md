# Balance run

- config hash: `71cb6811b4fff29342ed2b9c2420341c280f94593033368bb91edeea5ae46e82`
- **balance overrides: `tasking.resupply_slots_max=6`**
- profiles.yaml digest: `08fbf4f71a41cbabc67dea69148f4395` (every value in it is PROPOSED)
- seeds: [4, 5, 7]; game hours per run: 6
- workers: 4; wall time 488.9 s elapsed, 1386.7 s summed over the runs

## Targets

| Target | Profile | Result | Detail |
|---|---|---|---|
| A1 | raid-300 | not evaluable: ran 6 h, needs 72 h | 0 sim crashes, 0 harness errors; 0/3 seeds ended by victory or defeat in 24-72 h (need 85%) |
| A2 | raid-300 | fail | no median time to first impact over 113 newbies who arrived at ALPHA or above (needs <= 480 s); 86.7% over 900 s (98/113), needs <= 10%; 0 unresolved when the run ended; 396 more arrived below ALPHA (information only) |
| A4 | raid-300 | suspended (Q-SIM-92): needs a second armed viewer unit kind | no unit kind over 40% of all the coalition's kills (AI garrison included), pooled over seeds; needs 30 kills, saw 208 |
| Gini of kill share by rank | all | not measurable yet | needs ranks (PROGRESSION), not built yet |
| A5 adversarial bound | all | not measurable yet | part 2 (NX-321): needs the adversarial profiles |
| A6 conduct | all | not measurable yet | part 2 (NX-321): needs the chat gateway and the conduct system (NX-291) |

## Profiles (across seeds)

| Profile | Viewers (distinct / peak) | Outcomes | Median h | Momentum % | Newbie s | Idle armed mean / max | Slots / unit | Jobs / node | Top kind | Starved |
|---|---|---|---|---|---|---|---|---|---|---|
| raid-300 | 479 / 343 | {'NOT_ENDED': 3} | - | 46.7 | - | 70% / 81% | 0.00 | 0.01 | STRIKE_FIGHTER 100% | 78.3 |

Viewers: mean per run, distinct arrivals / peak with a live unit at once. Starved: mean supply-starved node-minutes. Idle armed: share of commander-owned armed units with no job, order or route, sampled every `idle_sample_min`. Slots / unit: open job slots on the coalition board per live (not Disabled) commander-owned unit (mean over samples with a unit). Jobs / node: open coalition jobs per theater node (mean). A job is open while it has an unfilled slot.

## A2 first impact (newbies arriving at the A2 tier or above)

- raid-300: counted 113 newbies (28 with impact), tail over 900 s: 86.7%, below-tier (information only) 396; first impact kinds {'departure': 5, 'hit': 22, 'kill': 1}
  - auto: 80 newbies, median - s, tail 96.2%, {'hit': 14}
  - hauler: 12 newbies, median - s, tail 75.0%, {'departure': 5}
  - scout: 6 newbies, median - s, tail 100.0%, {}
  - striker: 15 newbies, median 239.3 s, tail 40.0%, {'hit': 8, 'kill': 1}

## Why idle armed units hold no job (summed over samples)

- raid-300: {'full': 28834, 'refuel': 476}

## Director tier dwell (mean hours per run)

- raid-300: {'ALPHA': 2.2888888888888888, 'BRAVO': 1.2333333333333334, 'PATTERN_OF_LIFE': 2.477777777777778}

## Runs

| Profile | Seed | Ticks | Outcome | Wall s | Ticks/s | Final state hash |
|---|---|---|---|---|---|---|
| raid-300 | 4 | 216000 | not ended | 440.9 | 490 | `918b214524f0acd3` |
| raid-300 | 5 | 216000 | not ended | 457.1 | 473 | `fb939450639a2dfc` |
| raid-300 | 7 | 216000 | not ended | 488.8 | 442 | `374ff9b3b3f3c2ea` |
