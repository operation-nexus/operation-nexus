# Entertainment review: harness runs F, G and H, forward staging (2026-10-26)

Written by the entertainment-reviewer agent (Opus); filed by the lead. "#385 L61" means line 61 of that issue's harness report comment. Follow-ups: the next sweep (J0-J4), harness report additions (D5), owner questions in #383 section I.

Checkpoint review following ENTERTAINMENT-REVIEW.md. I ran no harness and no replay. I did run one check: the proposed `set:` lists go through `override_balance` at HEAD 0f564f1, and all sweep sets below pass. One alternative fails: `director.adaptation_down_below=0.5` is rejected because the YAML value is an int.

**Citation format.** "#385 L61" means line 61 of `the #385 report comment`, which is the report comment body.

**Code and config read:**
- `tools/balance/metrics.py:108-113, 322-340, 381-435`
- `tools/balance/report.py:309-340`
- `tools/balance/steamroll.py:23-34`
- `services/sim/src/nexus/core/operations.py:551-598`
- `services/sim/src/nexus/core/launch.py:881-910`
- `services/sim/src/nexus/core/tasking.py:940-965`
- `content/operations.yaml:9-76`
- `balance/default.yaml:253-340, 353-380`
- `tools/balance/profiles.yaml:72-79`

**Labels.** "Derived" means arithmetic on reported numbers. "Est." means an estimate. "Hyp." means a hypothesis the reports cannot settle.

### 1. What was reviewed
- **F, #364** at c98f93db, 4 workers. Economy limited on both sides, default values, staging on. It predates the Q-TD-39 "jets from the rear" fix (commits 29bbb7c / 0f9b3e7 sit between the two shas).
- **G, #385** at d06bf7f4. Run E's economy (`income.floor=15`, `storage.floor=500`, AIRBASE/HQ storage 1000) plus `director.source_spend_frac=0.0075` (#385 L1).
- **H, #386** at d06bf7f4. Control: economy limited, no tuning overrides (#386 L1).
- All three: prime-50 and raid-300, seeds 1-3, 24 h.

**Key fact: H is almost the same run as F.**
- raid-300 seeds 1-3 and prime-50 seeds 2-3 have identical final hashes in F and H (#364 L109-113 vs #386 L109-113). Only prime s1 differs (`ae526088` vs `c1415151`).
- So the Q-TD-39 fix changed the outcome of 1 run in 6. Its branch (a staged op's jets falling back to the rear) changed nothing in 5 of 6 runs (derived).
- Every F-vs-H prime difference comes from seed 1. F raid and H raid are the same data, so I count them once.

**Missing from the reports:**
- per-seed Offensive gaps
- an Offensive outcome funnel (launch → strike → defenses down → capture)
- staged waits, timeouts and drops
- Offensive timing by tier
- spawn debits by operation
- event streams, so clips and dead air can't be measured
- the overlay
- low-population and overnight profiles
- A1, which needs 72 h

**The sim has changed since G and H.** It now carries NX-410/NX-413 routing fixes and the EC-11 check (`git log d06bf7f4..HEAD -- services/sim`: 9abc62f, e1514c7, 527cd47, b42a23f and others). The next sweep therefore needs a new control.

### 2. Scores by audience (estimates; B-E scores were 2/2/2/2)

**Watcher: 2, no change.**
- Evidence:
  - Staging produces a readable setup beat ("NULL forces are massing in <sector>"). STAGING sitreps: F 118 / 181, G 67 / 49, H 109 / 181 (L61-62). That is about 1.5-3 per run-hour (derived: F prime 1.64/h, raid 3.0/h).
  - Raid cadence is good: Offensive gap median 5 min, max 56 min (#386 L62).
  - But the build-up never pays off. S1 on every won seed is 0.00-1.62 pressure events per 4 h (#364/#385/#386 L42-46). Pressure is a Static capture start, a coalition NodeDefensesDown or a node lost (metrics.py:108-110).
- Problems:
  1. Massing that leads nowhere teaches watchers to ignore the sitrep.
  2. Prime droughts of 779 min (F, H) and 973 min (G) (L61).
  3. CONVOY_ESCORT sitreps flood the ticker in prime: 1409 / 654 / 1627 per 3 runs, against 1456 / 1432 / 1748 escort ops (L61). That is about 20 per run-hour in F and H (derived). Cause in section 4.

**Player: 2, no change; G raid is worse.**
- A2 fails everywhere:
  - prime median 146 / 184 / 146 s, tail 29.4 / 33.8 / 30.1%
  - raid median 235 / 478 / 235 s, tail 32.9 / 39.2 / 32.9% (L17, L21)
- Problems:
  1. Raid capturers and haulers have a 100% tail in every run (L89-90).
  2. In G raid, idle armed share is 74% against 49% in H (L33). Idle reason `ring` is 27963 in G against 8 in H (#385 L97, #386 L97). `ring` means the first job the unit may take crosses a known enemy air-defense ring (tasking.py:964).
  3. Scouts have median 5583-26128 s to first impact (L85, L91).

**Site watcher: 2, no change.**
- Problems:
  1. Every win is flagged steamroll: 4 distinct won seeds, 4 of 4 flagged (L46, #385 L42-46).
  2. Fewer endings than C-E. F and H ended 1 of 6 (prime 0 of 3); G ended 3 of 6. C-E ended 10 of 18.
  3. Every victory hold that started ended in victory. No hold ever failed, so there is no "near miss" story to follow.

**VOD and clip watcher: 2, no change.**
- The designed signature moment, "hold broken", still has 0 occurrences.
- 4 distinct holds saw 8, 16, 9 and 12 Static catalog operations launched during them, with pressure 0 and broken 0 in each (#386 L62, #385 L61-62).
- Staging adds a setup with no payoff.
- One real positive: mid-campaign swings exist.
  - G prime s2: 8-point drop, 15 lead changes.
  - G raid s1: 11-point drop, 15 lead changes (#385 L42, L44).
  - S3 did not fire on either. The arc exists; the ending doesn't land.

### 3. What forward staging actually did

**Staging fires on almost every Offensive.**
- STAGING sitreps per Offensive (derived from L61-62):

| Run | Ratio | Sitreps / Offensives |
|---|---|---|
| F prime | 1.06 | 118 / 111 |
| F / H raid | 0.95 | 181 / 190 |
| G prime | 1.06 | 67 / 63 |
| G raid | 1.09 | 49 / 45 |
| H prime | 1.04 | 109 / 105 |

- A ratio above 1 fits ops that staged but never launched (dropped or still waiting at the end). The reports don't count these.

**Base vs source spawn spend** (derived from "spawn debits base X, source Y", L61-62):

| Run | Base share |
|---|---|
| F prime | 23.5% |
| H prime | 24.6% |
| G prime | 19.8% |
| F / H raid | 17.5% |
| G raid | 12.6% |

- Before staging: E prime 16.3%, E raid 20.4%, C prime 13.8% (from the B-E review's debits).
- So staging moved prime's base share up about 4-10 points and did not move raid.
- The base vs source split mostly measures escorts, not Offensives. At catalog cost, ESCORT_CONVOYS (cost 10) is 50-58% of prime's nominal op spend and Offensives (cost 60) are 15-23% (derived: op counts × `content/operations.yaml` costs; reused idle units lower the real draw).
- An Offensive's armor portion is 40 of 60 (4 of 6 slots, if paid per unit) [assumption]. Offensives × 40 = F prime 4440 against base debits 4764; H 4200 vs 5249; G 2520 vs 3369. That is consistent with Offensive armor being paid forward in prime (est.).
- In raid, 7600 is more than the base debits of 4780. So many raid Offensives paid their armor at the rear, through the FS-4 timeout fallback or a full `max_staged` (hyp.).

**Offensive cadence** (L61-62):

| Run | Offensives prime / raid | Gap median prime / raid (min) | Gap max prime / raid (min) |
|---|---|---|---|
| F | 111 / 190 | 16 / 5 | 779 / 56 |
| G | 63 / 45 | 12.5 / 9 | 973 / 245 |
| H | 105 / 190 | 16 / 5 | 779 / 56 |

- Gaps are measured only between Offensives inside one run (report.py:312-317). Time before the first and after the last Offensive is not counted, so real droughts can be longer.

**Holds and pressure during holds:**
- F and H: prime has 0 holds; raid has 1 hold (8 ops, pressure 0).
- G: prime 1 hold (16 ops), raid 2 holds (9 and 12 ops), all with pressure 0 and broken 0.

**Why holds are still never broken (ranked by how strongly the report supports it):**
1. **Offensives almost never produce pressure, hold or no hold.**
   - Won-seed S1 values convert to: F raid s3 1.62 per 4 h over 12.38 h, about 5 events. G raid s1 about 2 in 9.91 h. G raid s3 about 2 in 13.70 h. G prime s2 0 in 13.45 h (derived).
   - Against about 3 Offensives per run-hour in raid (derived), at most about 13% of Offensives produce any pressure event, even if every event came from an Offensive (est.). PROBE strikes also count as pressure.
   - The bottleneck is between launch and effect, not cadence or distance.
   - The template is STAGE → STRIKE (2 jets on the defenses) → CAPTURE (2 armor), and CAPTURE waits on STRIKE (`content/operations.yaml:9-17`). Zero CaptureStarted together with zero DefensesDown points at the strike step.
   - This matches the existing watch row (Q-SIM-84: strikes expire because the jets are lost to air defense or engage units first). Hyp. until a funnel is reported.
2. **Staging can't act inside a hold.**
   - A staged op may wait `director.staging.max_wait_windows` 90 windows (90 game min, default.yaml:328), three times the 30-min hold (`campaign.victory_hold_min`, default.yaml:129).
   - Late in a won campaign the Static has lost its near bases: S4 late units are 24-38% of peak (L46, #385 L42-46). FS-2 may then give no base, leaving the rear, which is 39.6-49.6 min from 3 of 8 victory nodes (L72-75).
3. **Hold scoring is off.** `director.score.victory_hold_mult` is 1.0 in all three runs (default.yaml:287, not overridden).
4. **The crowd is overwhelming at hold time.** Raid peak coalition armed units are 171-306 (L62).

### 4. G vs H (same sha; H is the control)
G's overrides:
- **Starved the Director's budget below one Offensive.**
  - Budget per window: 58.5 vs 75.8 (prime), 50.8 vs 80.1 (raid) (L61-62). An Offensive costs 60 (`operations.yaml:12`). G prime's mean budget is below one Offensive.
  - The cause: the Static pool is lower (last pool 5117 / 4292 vs 10000 / 6267, L55, L57), and 0.0075 × the smaller pool is less than 0.005 × the capped pool.
  - Result: Offensives fell 40% in prime and 76% in raid. STAGING fell 39% / 73%. Max gap rose 779 → 973 (prime) and 56 → 245 (raid).
- **Ended more games, all as steamrolls.** Wins: prime 1 vs 0, raid 2 vs 1. All 3 G wins flagged (S1 and S2 on all three, S4 stock as well on raid s3). Coalition mean momentum in raid fell to 45.1 vs 51.9 (L33), but the coalition still won 2 of 3.
- **Hurt raid players.**
  - A2 median 478 vs 235 s; auto median 306 vs 187 s.
  - Idle armed 74% vs 49%.
  - `ring` idle samples 27963 vs 8.
  - IADS_REINFORCED sitreps 143 vs 53 (raid) and 154 vs 20 (prime), while REINFORCE_IADS op counts were similar (181 vs 198, 158 vs 108).
  - Hyp.: more coalition hits on radars plus intact Static rings keep coalition jets parked. These numbers are pooled over seeds, so one long seed (G raid s2 ran the full 24 h) may dominate.
- **Coalition economy.** G's coalition is poorer in raid (last pool 2070 vs 7662). It shows higher prime income (1534.8 vs 1177.3) because H's pool sat at its cap (6000), and income is apparently counted after the clip (hyp., as in the B-E review).

**Verdict:** G's direction ("a poorer Static") cuts the Director's tempo and doesn't fix holds. H's defaults keep raid cadence healthy.

**The escort-sitrep flood is in the code, not in G or H.**
- `_announce_up` fires when the counter is above `adaptation_up_above` (0) and the category is not yet adapted. `_announce_down` fires when the counter is below `adaptation_down_below` (1) (launch.py:889, 908).
- The two bands overlap. Any decayed counter in (0, 1) flips UP, then DOWN, then UP again on each escort launch.
- Prime: 1409-1627 sitreps against 1456-1748 escort ops. Raid: 102 against 1134. In raid the counter presumably stays at or above 1.

### 5. Steamroll readings (won seeds only)

| Seed | S1 (per 4 h) | S2 | S3 drop / changes | S4 units / stock | Signals fired | Steamroll |
|---|---|---|---|---|---|---|
| F/H raid s3 (12.38 h) | 1.62* | 0 / 0* | 20 / 9 | 37% / 41% | 2 | yes |
| G prime s2 (13.45 h) | 0.00* | fired | 8 / 15 | 30% / 25% | 2 | yes |
| G raid s1 (9.91 h) | 0.81* | fired | 11 / 15 | 38% / 19% | 2 | yes |
| G raid s3 (13.70 h) | 0.58* | fired | 6 / 3 | 24% / 16%* | 3 | yes |

- "*" means the signal fired. Sources: #364 L46, #385 L42-46.
- S1 and S2 fire together on every won seed. Across B-H, S2 fired on 13 of 14 won seeds (B-E 9 of 10 plus these 4).

### 6. The prime-50 Offensive drought (F 779, G 973 min)
What the report contains that explains it:
1. **ALPHA dwell plus the one-op cap at ALPHA.**
   - Prime spends 11.1 h (F), 6.15 h (G) and 13.2 h (H) at ALPHA per 24 h (L101). Raid spends 1.3-2.3 h (L102).
   - `director.max_ops.alpha` is 1 (default.yaml:294-296). It counts every non-routine op. Routine ops are those enabled at Pattern of Life (`operations.routine_ops`), so OFFENSIVE, PROBE, STRIKE_BRIDGE and REINFORCE_IADS compete for one slot (`operations.py:571`). Prime runs 132-192 PROBE, 108-158 REINFORCE_IADS and 18-43 STRIKE_BRIDGE (L61).
   - A staged Offensive also holds that slot for up to 90 windows (FS-4).
   - Raid lives at BRAVO (`max_ops.bravo` null) and its max gap is 56 min in F and H.
2. **Budget.**
   - Offensive cost 60 against G prime's mean 58.5 per window.
   - ALPHA's surplus share is 0.02, against 0.0534 at BRAVO (default.yaml:258-261), so ALPHA windows are poorer than the mean (est.).
   - The cadence floor only guarantees the cheapest affordable op (EC-7), not an Offensive.
3. **Pattern of Life.** It allows one capture op per `pol.offensive_period_s` 21600 s, and prime spends 1.7-2.0 h there (L101).
4. **The drought is a seed property.** F and H both show exactly 779 min, and seeds 2-3 are identical across them. It is very likely deterministic in seed 2 or 3 (which seed is not reported).

Which of 1 and 2 dominates can't be told without gaps by tier. Hyp.: (1) in F and H, (1) plus (2) in G.

### 7. Top risks
1. **Cry-wolf staging.** About 1-3 "massing" sitreps per run-hour with near-zero follow-through.
2. **S2 never clears.** Staging did not create contested holds: 0 pressure in 4 of 4 holds.
3. **Intel ticker spam in prime.** About 20 CONVOY_ESCORT sitreps per run-hour from the inverted hysteresis.
4. **A poorer Static is the wrong lever.** G cuts Offensives 40-76% and hurts raid A2.
5. **Prime droughts of 13-16 h.** A prime watcher sees no Static push for a whole evening.
6. **Spend stays 75-87% at the rear,** driven mostly by escorts (est.).
7. **Capturer and hauler personas are broken** in raid (100% tail), unchanged since B-E.

### 8. Suggestions, ranked

**Pure tuning (balance keys; all values PROPOSED):**

| # | Key = value | Rests on | Expected effect |
|---|---|---|---|
| T1 | `director.max_ops.alpha=2` (from 1) | ALPHA dwell 6-13 h prime (L101); max gap 779 / 973 (#364/#385/#386 L61); raid at BRAVO max gap 56 (#386 L62) | Prime max gap falls; one PROBE, REINFORCE_IADS or staged op no longer blocks Offensives. Risk: a stronger prime Static. Serves watcher and VOD |
| T2 | `director.staging.max_wait_windows=30` (from 90; x-tune 15-180) | Hold is 30 min (default.yaml:129); 0 pressure in 4 holds (L61-62) | A staged op resolves within one hold length. More rear fallbacks, so watch base share |
| T3 | `director.score.victory_hold_mult=3.0` (x-tune max; with T2) | 8-16 ops per hold, 0 pressure; C's 2.0 before staging also gave 0 | Hold-node Offensives win the selection. Tells us whether selection or effectiveness is the block |
| T4 | `director.adaptation_up_above=2` (from 0; keep `down_below` 1) | launch.py:889 / 908; prime CONVOY_ESCORT sitreps about equal to escort ops (L61) | Real hysteresis; escort sitreps drop sharply (est.). Readability only. Note: x-tune is null for this key, but `set:` accepts it (checked) |
| T5 | Reject G's direction. If E's storage stays, `director.source_spend_frac=0.01` (x-tune max), not 0.0075 | G budget 58.5 / 50.8 against Offensive cost 60. A full restore needs about 0.011 (prime) to 0.014 (raid) (derived: (75.8-58.5)/5117 and (80.1-50.8)/4292 added to 0.0075, using last pools as a stand-in for the mean). Both are above the x-tune range | Budget stays at or above one Offensive. Going beyond 0.01 needs a registry range change |
| T6 | `director.op_priority.ESCORT_CONVOYS=0.5` (from 0.8), lower confidence | Escorts are 50-58% of prime's nominal op spend (derived) | Frees budget for capture ops in prime. Risk: more convoy raids |
| — | Keep `staging.direct_s` 1500 and `max_staged` 2 | No report evidence that either binds | — |

**Design changes (need the owner):**
- **D1. Offensive effectiveness.**
  - First, add a harness funnel: staged → launched → strike arrived → DefensesDown → CaptureStarted → captured, per Offensive.
  - Then decide the levers: more strike slots, a capture that can start after an expired strike, or SEAD before the strike.
  - Touches `content/operations.yaml` OFFENSIVE, the TB-8 dependency and Q-SIM-84 ("no code tilt toward success"). Cost: S for the harness, then M.
- **D2. A hold response.** While a victory hold runs, staging is skipped and capture ops can launch at once, from the rear if needed, outside the `max_ops` cap. Or tie `campaign.victory_hold_min` to Static reach.
  - Touches EC-9, THREAT-DIRECTOR §4a FS-1 / FS-4. Cost: S-M.
  - `campaign.victory_hold_min` is a key, but changing it changes the win rule, so it goes to the owner.
- **D3. The cadence floor guarantees a capture-class op** while the Static holds its HQ. Carried over from B-E; now with 779 / 973 min of evidence. Touches EC-7. Cost: S.
- **D4. A staging payoff.** Add a "NULL assault launching from <sector>" sitrep on launch, and a "massing disperses" sitrep on drop or timeout. Touches FS-5 / FOW-13. Cost: S.
- **D5. Harness report additions:**
  - the D1 funnel
  - staged wait, timeout and drop counts
  - Offensive gaps per seed and by tier, including the leading and trailing stretches
  - pressure per hold
  - spawn debits by operation
  - sitreps per run-hour by category
  
  Cost: S.

### 9. Next sweep
- **Setup:** at HEAD (the sim changed after d06bf7f4). Each job runs seeds 1-6 × prime-50 and raid-300 for 24 h, so 12 runs per job and 12 workers busy.
- **Overrides:** every job carries the 3 base overrides: `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`. All sets were checked with `override_balance` at HEAD.
- **Run time** is an estimate: about 100-130 min per job (H's 6 runs took 80.5 min with 6 busy workers; the 20-30% gain from hyperthreads is an unmeasured rule of thumb, #385 comment), so 5 jobs take about 9-11 h.

| Job | Extra overrides | Count | Question |
|---|---|---|---|
| J0 control | none | 3 | Baseline at 6 seeds on the new sha (needed: NX-410 / NX-413 / EC-11 landed) |
| J1 | `director.max_ops.alpha=2` | 4 | Is the ALPHA one-op cap the prime drought? Watch prime max gap, Offensives, S1, ALPHA dwell |
| J2 | `director.staging.max_wait_windows=30`, `director.score.victory_hold_mult=3.0` | 5 | Can selection plus a shorter wait put pressure into holds? Watch S2 pressure, broken, ops per hold, base share. If still 0 pressure, D1 is confirmed as the block |
| J3 | `economy.income.floor=15`, `economy.storage.floor=500`, `economy.storage.per_node.AIRBASE=1000`, `economy.storage.per_node.HQ=1000`, `director.source_spend_frac=0.01` | 8 | Does a budget of at least 60 rescue E's economy? Watch budget per window, Offensives, A2 raid, `ring` idle, steamroll share against J0 and G |
| J4 | `director.adaptation_up_above=2` | 4 | Does hysteresis remove escort-sitrep spam without changing outcomes? Watch CONVOY_ESCORT / IADS_REINFORCED counts; outcomes should match J0 closely |
| J5 (optional) | `director.op_priority.ESCORT_CONVOYS=0.5` | 4 | Does cheaper escort behaviour free budget for capture ops in prime? Watch escort ops, Offensives, starved minutes, convoy losses (not reported) |

A1 stays not evaluable at 24 h. Run the best set at 72 h afterwards.

### 10. Watch items and questions
- **Watch: STAGING sitreps per Offensive that produced pressure.** Revisit if it stays under 0.2 (proposed).
- **Watch: CONVOY_ESCORT sitreps per run-hour.** Revisit if over 4 (proposed).
- **Watch: share of runs where the Q-TD-39 rear-jet branch changes the outcome** (1 of 6 so far).
- **Watch: longest Offensive gap.** Still over 120 min in prime (now 779-973).
- **Q (owner):** Should a victory hold trigger a dedicated Static response that skips staging and the `max_ops` cap (D2)?
- **Q (owner):** Offensive template: may the capture step start after an expired strike, or should strike slots rise (D1, Q-SIM-84)?
- **Q (owner):** Should the cadence floor guarantee a capture op (D3, repeated)?
- **Q (lead):** `adaptation_up_above` has `x-tune: null` and `adaptation_down_below` is an int in the YAML, so 0.5 can't be set. Make both proper floats with sweep ranges (add-config-key).
- **Q (lead):** Widen the `source_spend_frac` x-tune range above 0.01 if J3 shows a partial restore.
- **Resolved since B-E:** risk 5 (EC-11 missing) is closed by 9abc62f (`economy.floor_viewer_units` and the load check).
