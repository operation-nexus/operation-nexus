# Entertainment review: NX-412 economy sweep runs B–E (2026-10-26)

Written by the entertainment-reviewer agent (Opus); filed by the lead. "#354 L55" means line 55 of that issue's harness report comment. Follow-ups: runs G (#385) and H (#386, a control run); owner questions in #383.

Sources: the harness report comments on issues #346, #352, #353 and #354 (line numbers such as "#354 L55" count lines in each comment body; 364 had only queue notes). Also used: balance/default.yaml, content/theaters/strait-1.yaml, tools/balance/profiles.yaml:72-79 (steamroll thresholds), docs/specs/ECONOMY.md, THREAT-DIRECTOR.md:42-49 (§4a) and the two earlier reviews. No harness or replay was run for this review. "Derived" means arithmetic on reported numbers; "est." means an estimate.

## 1. What was reviewed
- **Common setup.** Profiles prime-50 and raid-300, seeds 1-3, 24 game hours each, all with `economy.legacy_rules=false` and both sides limited.
  - B, #346: `upkeep.STRIKE_FIGHTER=2`. It ran at sha 0b1969c4 (#346 L1).
  - C, #352: `capture.garrison_mult=2.0`, `capture.time_s=90`, `income.per_node.FOB=10`, `victory_hold_mult=2.0`.
  - D, #353: `source_spend_frac=0.002`, `cadence_windows=20`, `spend_frac.bravo=0.04`.
  - E, #354: `income.floor=15`, `storage.floor=500`, `storage.per_node.AIRBASE=1000`, `HQ=1000`.
  - C, D and E ran at sha be5ec255 (L1 of each).
- **Caveats.**
  1. B is at a different sha from C-E.
  2. There is no control run (legacy off, no overrides) at be5ec255. Each run is compared only with run A as the earlier review summarised it; run A's sha is not in these files [UNVERIFIED].
  3. **E is not a binding economy in the spec's sense.** `economy.upkeep.*` is 0 for every kind (default.yaml:369-378), so in C, D and E no unit paid upkeep: upkeep/h is 0.0 on both sides (#354 L54-57). E only binds through storage. B is the only run with upkeep, and only the coalition paid it, because no Static kind is STRIKE_FIGHTER (#346 L55, L57: ENEMY upkeep 0.0).
  4. All four runs predate forward staging (§4a).
  5. Not available: overlay, event streams or replays (so no clip counts or dead-air timing beyond the Offensive gaps), low-population and overnight profiles, and Offensive arrival counts.

## 2. Scores by audience (all estimates, reconstructed from report numbers)

**Watcher: 2, same as run A.**
- Evidence:
  - Endings now happen: C 1/6 (#352 L33), D 5/6 (#353 L32-33), E 4/6 (#354 L32-33), against run A's 0/6.
  - Two seeds have a real arc. C raid s2 has a 29-point drop and 17 lead changes over 20.7 h (#352 L45). E raid s2 has a 19-point drop and 5 lead changes (#354 L45).
  - But D is a steamroll factory with 0 Offensives (#353 L61-62).
- Problems:
  1. No victory hold was ever broken in any run: B-E show "broken 0" (L61-62 of each).
  2. In E prime the longest gap between Offensives is 737 min (#354 L61), about 12 h with no Static push.
  3. The Static still buys 80-95% of its spawns at the rear. Derived from spawn debits: B prime 15645 of 17187, C prime 18251 of 21161, E prime 12112 of 14464, E raid 7056 of 8867, D raid 3228 of 3383. So columns march 25-50 min (travel table, L66-75).

**Player: 2, same as run A.**
- Evidence:
  - Auto and striker newbies get impact fast: median 142-193 s (L81-92 of each).
  - A2 still fails everywhere. The raid-300 median passes in C, D and E (422 / 233 / 399 s) but fails in B (613 s). The tail over 900 s is 27-47%.
- Problems:
  1. The capturer, hauler and scout personas are broken. Their tails run 63-100% and medians 1244-49365 s; for example E raid capturer is 49365.5 s (#354 L89).
  2. Upkeep 2 in B benched the raid crowd. Mean grounded was 227.5 (max 326) against a peak of 316-342 armed units, with 315.4 groundings/h and a last pool of 19 (#346 L56, L62).
  3. Without upkeep the raid crowd sits idle anyway: idle armed mean is 70-75% in C, D and E (L33). Slots per unit are 0.02-0.03.

**Site watcher: 2, up from 1.**
- There are now results to post: 10 wins across C-E.
- Problems:
  1. 7 of 10 wins are flagged steamroll: D 5/5 and E 2/4 (L48 of each).
  2. A wide spread in result per seed reads as random. raid-300 wins came anywhere from 4.86 h to 20.70 h (#354 L111-113).
  3. Prime-50 mostly does not end: 6 of 12 prime seeds across B-E did not end.

**VOD / clip watcher: 2, same as run A.**
- Problems:
  1. The designed signature moment, "hold broken", happened zero times. The Static ran 5-13 operations per hold but logged 0 pressure, apart from 1 event in E raid s3 (#354 L46, L61-62).
  2. Seeds that end late have no climax. The E raid s2 win came at 20.7 h with S2 fired.
  3. There is no event stream, so clip counts are not measurable.

## 3. What changed vs run A
- **Stalemate broken in C, D and E:**
  - D gets there by making the Static passive: budget per window 21.7 / 15.6 and 0 Offensives (#353 L61-62).
  - E gets there by making the Static poorer.
  - C produced the only hard-fought win.
- **B (coalition upkeep) flipped momentum to the Static:** 39.5% / 40.0% (#346 L32-33), against 46-60% in C, D and E. It is also the only run where haulers did comparatively well: prime hauler median 2319.9 s, against 5275-14830 s elsewhere (L84 of each). That fits ECONOMY §5.2, which says upkeep gives hauling real impact. The sample is small (14-16 newbies).
- **The Static pool is still clipped at its cap.** Without upkeep the pool never drains:
  - C, D and E report Static income/h below floor × 60. At floor 30 that is 1800/h, against C prime 1450.9 and D raid 552.6 (#352 L55, #353 L57). Reported income must therefore be after the clip.
  - Last Static pools in C sit at about 7.6-8.3k (#352 L55, L57). The default storage keys give 8000 for the Static's start holdings (derived from default.yaml:361-367 and strait-1.yaml:32-35).

## 4. Steamroll signals (won seeds only; thresholds from profiles.yaml:72-79)
- **B:** no seed won, so none judged (#346 L41-46).
- **C:** raid s2 shows S1 9.27, S2 fired (0, 0), S3 29 / 17, S4 28% / 44%. One signal fired, so no steamroll (#352 L45).
- **D:** all 5 won seeds flagged (#353 L42-46).
  - S1 fired on every seed: 0.00-1.35 per 4 h.
  - S2 fired on every seed.
  - S3 fired on all raid seeds (6, 1).
  - S4 stock 14% fired on prime s3.
- **E:** 2 of 4 flagged (#354 L42-46).
  - Prime s2: S1 0.26, S2, S4 units 18%.
  - Raid s1: S1 0.82, S2, S3 (1, 1), at 4.86 h.
  - Not flagged: raid s2 (S1 3.28, S3 19 / 5, S4 33% / 73%), 1 signal.
  - Not flagged: raid s3 at 5.5 h (S1 3.64, S2 pressure 1, S3 8 / 3, S4 34% / 18%), 0 signals.
- **Overall, S2 is the constant failure:** 9 of 10 won seeds had an uncontested last hold. The travel table shows why: 3 of 8 victory nodes are more than 30 min from the rear, and the rest are 11.8-25.7 min away before spawn, staging and combat (L68-75). `victory_hold_mult=2.0` (C) cannot move S2 without staging.
- **A coincidence:** C raid s2 and E raid s2 both won at 20.70 h (ticks 745323 vs 745358, #352 L112, #354 L112). If this happens again, check it for a shared scripted trigger [UNVERIFIED cause].

## 5. Does the binding economy (E) play better or worse?
- **Better than run A and D:**
  - It ends games: 4/6.
  - Raid has healthy Offensive cadence: gap median 21.5 min, max 45 min (#354 L62).
  - It has 2 non-steamroll wins, including the only seed with pressure during a hold.
- **Worse than C for prime tempo:**
  - 15 Offensives against 63 in C, with a 737-min max gap (#354 L61, #352 L61).
  - 2 of 3 prime seeds still did not end.
- **Mechanism (est.):**
  - The smaller cap shrinks the rear pool: last pools 3520 / 2731 (#354 L55, L57), against 7645 / 8262 in C.
  - EC-7's source share then shrinks the budget: 40.8 / 41.6 per window, against 65.5 / 79.0 in C, a 38-47% drop (derived).
  - So E weakens the Static's spend, not its army upkeep. It is "a poorer Static", not the economy the spec intends.
  - Whether E still clips income cannot be shown: 1322.8/h is above the 900/h floor (#354 L55). The report needs a clipped-stock column.

## 6. Top risks
1. **TS-1 benching from whole-number upkeep.**
   - With 60 s windows the smallest nonzero upkeep is 1 per window.
   - In B the coalition's undrained income was about 49-54 per window (derived from 2921.2 and 3238.1 per hour, #346 L54, L56). At upkeep 2 that pays for about 22-25 fighters (derived from 2695.0 and 3016.7 per hour of upkeep).
   - At upkeep 1 it would pay for about 50 (est.), against a raid-300 peak of 182-342 armed units (#346 / #352 / #354 L62).
   - ECONOMY.md:145 requires the owner to see this before values are set.
2. **Upkeep churn.** B prime had 82.4 groundings/h with only 6.5 grounded on average (#346 L54). That is the ECONOMY §6 oscillation failure mode.
3. **Busy units get grounded.** B grounded 6.1% of busy units in prime and 46.2% in raid, plus 64.7% of units on a job in raid (#346 L61-62). A player who loses a unit mid-job will feel griefed.
4. **Static upkeep can zero the budget through the reserve term.**
   - The strait-1 garrison is 22 units (quotas 4+4+6+8, strait-1.yaml:32-35). At Static upkeep 1 that is 22 per window.
   - With `upkeep_reserve_windows` 2 the reserve term is 44, which exceeds E's budget of 40.8, so the budget would fall to the cadence floor (derived).
5. **Loader check may block E's floor once upkeep is on.** `economy.floor_viewer_units` (EC-11) is not in balance/ or services/sim/src (my grep found no key). The loader check is probably not built yet, and floor 15 may fail it once upkeep is nonzero [UNVERIFIED].
6. **The cadence floor does not prevent Offensive droughts.** It guarantees the cheapest affordable op, not an Offensive (EC-7), which fits the 737-min gap.

## 7. Suggestions, ranked

**Pure tuning (balance keys). Proposed starting values for NX-412 part 5b, all PROPOSED and unvalidated:**

| # | Key(s) | Proposed start | Report evidence | Expected effect |
|---|---|---|---|---|
| T1 | `economy.storage.floor`; `economy.storage.per_node.AIRBASE` / `HQ`; `per_node.FOB` / `PORT` | 500; 1000 / 1000; keep 1000 / 1000 | #354 L32-33, L45-46, L55, L57: the only run with non-steamroll wins at early hours; pools fall from about 8k to 2.7-3.5k | Pools are no longer pinned at the cap; capturing bases matters. Serves site and watcher. Untested idea: FOB 500, so the airbase and HQ count for more than FOBs; there is no data either way |
| T2 | `economy.income.floor` | 15 | #354 L1, L54-57 | Lower floor; at 30, C and D pools sat at the cap (#352 L55, #353 L57) |
| T3 | `economy.income.per_node.*` | keep default (AIRBASE 10, HQ 10, FOB 5, PORT 5) | C's FOB=10 had no isolatable effect: coalition income was clipped at 1596 / 2634 (#352 L54, L56) | None measured; sweep it alone |
| T4 | `director.source_spend_frac` | 0.0075 (sweep 0.0075 / 0.010) | #354 L61-62 vs #352 L61-62: budget fell 38-47% when pools shrank. 0.005 × 7645 / 3520 ≈ 0.011 would fully restore C's budget (derived); I propose about half-way because C's full tempo left prime stalemated (#352 L32) | More Static Offensives in E-style economies; shorter prime droughts. Serves watcher and VOD |
| T5 | `director.spend_frac.*`, `director.cadence_windows` | keep 0.007 / 0.02 / 0.0534 and 10 | D's 0.04 / 20 / 0.002 gave 0 Offensives and 5/5 steamrolls (#353 L42-46, L61-62) | Reject D's values |
| T6 | `director.upkeep_reserve_windows` | 1 if Static upkeep is on (else keep 2) | Risk 4: 2 × 22 > 40.8 (#354 L61, strait-1.yaml:32-35) | Keeps a nonzero discretionary budget |
| T7 | `economy.upkeep.ENEMY_ARMOR` / `ENEMY_FIGHTER` / `ENEMY_STRIKE_FIGHTER` | 1 / 1 / 1; `ENEMY_RECON_UAV` 0; convoys and trucks 0 | No run has tested Static upkeep (#346-#354 L55 / L57: ENEMY upkeep 0.0). Garrison 22 / window against E's unclipped full-hold income of 45 / window (derived: 15 + 10 + 10 + 5 + 5) | First real binding on the Static; a test value, not a starting value |
| T8 | `economy.upkeep.STRIKE_FIGHTER` / `RECON_UAV` / `GARRISON_INFANTRY` | Set 1 (spec-clean, EC-3): 1 / 0 / 1. Set 2 (needs owner): 0 / 0 / 1 | B: 2 grounded 227.5 of about 330 raid units (#346 L56, L62); 1 would pay for about 50 (est.) | Set 1 shows the owner the TS-1 cost; Set 2 avoids it but is a side asymmetry in effect |
| T9 | `director.score.victory_hold_mult` | keep 2.0; judge only after staging | #352 L62: 9 ops in the hold, 0 pressure, 0 broken | — |
| T10 | `director.score.income_node_mult` | untested (1.0 in every run) | — | Sweep after staging |

**Design changes (need the owner):**
- D1. Rerun E plus T4 plus T7 with forward staging (§4a, NX-416). It is the only lever on S2: 9 of 10 holds were uncontested. Serves the VOD and watcher audiences. Cost: harness time only.
- D2. Fix upkeep granularity: a per-kind upkeep period (pay every N windows) or a larger stock scale, so a viewer unit can cost less than 1 per window. Touches ECONOMY EC-4, EC-10 and EC-14 and adds a new key. Cost: S-M.
- D3. Let the cadence floor guarantee a capture-class operation (an Offensive or Retake) while the Static holds its HQ, not only the cheapest op. Fixes the 737-min gap. Touches ECONOMY EC-7 and THREAT-DIRECTOR §4. Cost: S.
- D4. Grounding order: never ground a unit while it holds a claimed job, if a unit idle at home exists (#346 L62). Touches ECONOMY EC-6. Cost: S.
- D5. Harness report additions (ECONOMY §4):
  - clipped stock per hour per side
  - live Static units per hour
  - Offensive arrivals at the target
  - pressure events per hold
  - a no-override control run at the same sha in every batch
  
  Cost: S.

## 8. Watch items and questions
- **Watch: upkeep churn.** Groundings/h against mean grounded; B prime 82.4 against 6.5. Revisit if the ratio is above about 5 (est.).
- **Watch: share of busy or job units grounded.** B raid 46.2% / 64.7%.
- **Watch: longest Offensive gap.** Revisit if it exceeds 120 min (proposed); E prime was 737.
- **Watch: hold broken count.** Revisit if it is still 0 after staging.
- **Q (owner, TS-1, ECONOMY §6).** At upkeep 1 per window a raid-300 crowd tops out near 50 paid units. Accept that, or change upkeep granularity (D2), or give viewer kinds upkeep 0 (an effective EC-3 asymmetry)?
- **Q (owner, EC-7).** Should the cadence floor guarantee an Offensive (D3)?
- **Q (lead).** EC-11 (`economy.floor_viewer_units`) seems not to exist yet. It needs to be in place before a 5b run with upkeep on and floor 15.