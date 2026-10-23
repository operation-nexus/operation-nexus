# Balance run

- config hash: `0190fcf32a2cbeffe4f2ce1753945d84a4f0359592953c0734c46c7953862d57`
- profiles.yaml digest: `08fbf4f71a41cbabc67dea69148f4395` (every value in it is PROPOSED)
- seeds: [4, 5, 7]; game hours per run: 6
- workers: 4; wall time 555.9 s elapsed, 1513.6 s summed over the runs

## Targets

| Target | Profile | Result | Detail |
|---|---|---|---|
| A1 | raid-300 | not evaluable: ran 6 h, needs 72 h | 0 sim crashes, 0 harness errors; 0/3 seeds ended by victory or defeat in 24-72 h (need 85%) |
| A2 | raid-300 | fail | median 416 s time to first impact over 178 newbies who arrived at ALPHA or above (needs <= 480 s); 37.9% over 900 s (67/177), needs <= 10%; 1 unresolved when the run ended; 331 more arrived below ALPHA (information only) |
| A4 | raid-300 | suspended (Q-SIM-92): needs a second armed viewer unit kind | no unit kind over 40% of all the coalition's kills (AI garrison included), pooled over seeds; needs 30 kills, saw 203 |
| Gini of kill share by rank | all | not measurable yet | needs ranks (PROGRESSION), not built yet |
| A5 adversarial bound | all | not measurable yet | part 2 (NX-321): needs the adversarial profiles |
| A6 conduct | all | not measurable yet | part 2 (NX-321): needs the chat gateway and the conduct system (NX-291) |

## Profiles (across seeds)

| Profile | Viewers (distinct / peak) | Outcomes | Median h | Momentum % | Newbie s | Idle armed mean / max | Slots / unit | Jobs / node | Top kind | Starved |
|---|---|---|---|---|---|---|---|---|---|---|
| raid-300 | 479 / 341 | {'NOT_ENDED': 3} | - | 37.8 | 416.5 | 70% / 86% | 0.01 | 0.05 | STRIKE_FIGHTER 100% | 350.0 |

Viewers: mean per run, distinct arrivals / peak with a live unit at once. Starved: mean supply-starved node-minutes. Idle armed: share of commander-owned armed units with no job, order or route, sampled every `idle_sample_min`. Slots / unit: open job slots on the coalition board per live (not Disabled) commander-owned unit (mean over samples with a unit). Jobs / node: open coalition jobs per theater node (mean). A job is open while it has an unfilled slot.

## A2 first impact (newbies arriving at the A2 tier or above)

- raid-300: counted 178 newbies (113 with impact), tail over 900 s: 37.9%, below-tier (information only) 331; first impact kinds {'hit': 111, 'kill': 2}
  - auto: 125 newbies, median 365.8 s, tail 27.2%, {'hit': 92, 'kill': 2}
  - hauler: 21 newbies, median - s, tail 100.0%, {}
  - scout: 12 newbies, median - s, tail 100.0%, {}
  - striker: 20 newbies, median 192.2 s, tail 5.0%, {'hit': 19}

## Why idle armed units hold no job (summed over samples)

- raid-300: {'full': 19282, 'other': 973, 'refuel': 8291, 'ring': 498}

## Director tier dwell (mean hours per run)

- raid-300: {'ALPHA': 2.1055555555555556, 'BRAVO': 3.5, 'PATTERN_OF_LIFE': 0.39444444444444443}

## Runs

| Profile | Seed | Ticks | Outcome | Wall s | Ticks/s | Final state hash |
|---|---|---|---|---|---|---|
| raid-300 | 4 | 216000 | not ended | 463.5 | 466 | `24817026b3c5e1b4` |
| raid-300 | 5 | 216000 | not ended | 494.4 | 437 | `3b85d3f230891daf` |
| raid-300 | 7 | 216000 | not ended | 555.7 | 389 | `20450ea3cdd906bc` |
