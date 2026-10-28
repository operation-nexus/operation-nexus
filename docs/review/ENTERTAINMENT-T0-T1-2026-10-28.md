# Entertainment review: T0 #502 and T1 #503 (sha e69f16a), 2026-10-28

The review is by the Opus entertainment-reviewer subagent, with probes capped at 2 seeds and one causal probe per question (L-40). The lead filed it with one change to section 4's run sha: U0 is #510 and U1 is #511 (#507–#509 were closed without running because their sha was invalid; see L-41).

## Bottom line

1. **Q-TD-97: ship 0.01 in 5b (tuning). Don't pick a value between 0.01 and 0.02.**
   - **Mechanism (found by the probe):** during a victory hold, the Static's budget is about floor(rear pool × `source_spend_frac`), and its pool is pinned at its storage cap.
   - In a hold of 7 of 8 nodes, that cap is only 4000–5000, because the Static holds just its HQ, or its HQ and one FOB (`economy.py:38-41, :78-81`; `balance/default.yaml:364-371`).
   - **At 0.01:** the hold-phase budget is 40–50. That is below the Offensive cost of 60 (`content/operations.yaml:12`), so `budget` was the first no-capture reason in every hold sample.
   - **At 0.0125:** 50–62, so a Retake (cost 50, `operations.yaml:21`) almost always, and an Offensive only at the 5000 cap.
   - **At 0.015:** 60–75, so one Offensive fits in every hold (derived).
   - These are cliffs, not smooth tuning. In T0, holds the Static could answer mostly broke, and holds it couldn't answer were won.
   - A value between 0.01 and 0.02 would most likely move seeds from "uncontested win" to "broken hold", not to "contested and won" [estimate].
2. **Q-TD-91: T0 meets "at least some resistance", but only at the minimum.**
   - For: 6 of 6 wars ended, 0 of 6 were flagged as steamrolls, and 7 of 13 holds broke.
   - Against: 4 of 6 seeds (1.85–1.96 h) look like S0 in substance. In probe s3 the Static's pool sat at its cap for the first hour, its one Offensive stayed staged from 0.5 to 1.25 h, and the final hold went unanswered. Only s1 (4.31 h) and s2 (8.77 h) were real wars.
3. **Q-TD-102: not needed for 5b, but needed before any spend increase.**
   - At 0.01 the breaks are not Offensives. In probe s2, Static units already on the map flipped back eastern FOBs the coalition had taken with 1 commander. That took 13–23 min, and none of the 5 Static flips was the target of a capture operation.
   - Any spend that funds a reply to every hold lands in T1's regime (43 of 43 broken) while the reset stays as it is.
4. **Q-TD-104: prime is fine now. Keep the cap as it is (b).**
   - `night_cap` was the first no-capture reason in 47.5% of T0 prime windows (4103 of 8640).
   - Even so, T0 prime has the best pacing of any run so far: longest dry stretch median 185 min (S0 367, R2 286.5), momentum 49.7, and 53 + 1 Static captures.
5. **Q-TD-105: the one probed HQ win was a 1-commander grab.**
   - T0 raid s2 ended at 8.77 h with `static-hq` captured by 1 commander, 3.9 min into a hold of 7 of 8 nodes.
   - With S1 s2, that makes 2 of 2 observed HQ wins by 1 commander.
   - The T0 one was a good finale, not a side door. Keep (a) and watch it.
6. **Quiet-5: the retake job works.**
   - In both probe seeds the coalition kept 2 or more strategic nodes for 97.9% of the day (S0 probe: 89.6% and 56.3%).
   - It retook 3 lost nodes: 2 within 25 min of losing them, 1 after 8 h. Each retake came 0.1–0.4 h after a retake job was posted.
   - Readability problem: one retake job was re-posted 14 times in 7.5 h without success.
7. **The raid A2 tail has two causes.**
   - Role kinds, as before: about 60% of the tail (derived).
   - New at T0: auto-tasked joiners have no targets. Their tail is 33.1% at T0 against 8.8% at T1, at the same sha with only spend different. The Static fields 5–35 units against about 200 viewer units, and probe joiners in the first hour waited 46–99 min for a first hit.
   - Q-TD-98's "board capacity" is a symptom of that. A hold-defence job for late joiners would address both the tail and the hold breaks.
8. **Run one confirming run at develop 3aa67f3 before 5b ships.** NX-483 changes both sides' capture-job expiry, which moves the raid flips and prime capture completion. The config is in section 4.

## 1. What was reviewed

**Queue numbers.**
- Source: a Sonnet verbatim extract of #502 comment 6477758250 and #503 comment 6479590726.
- Both runs: sha e69f16a, 24 h, 6 seeds, overnight-0, quiet-5, prime-50 and raid-300, 0 crashes, 0 harness errors.
- Config hashes: T0 `2757b80f…`, T1 `2e15373a…`.
- S-series comparisons come from the S0/S1 extract (sha 8f9a5ff).
- "Derived" marks the reviewer's own arithmetic on those numbers.

**Configs.**
- T0: B + `combat.strike_structure_first=true` + `director.staging.max_wait_windows=30` + `director.source_spend_frac=0.01`.
- T1: the same with 0.02.

**Code at e69f16a.**
- Included: NX-474, NX-467, NX-480, NX-468 (overkill check) and NX-475 (coalition retake job).
- Not included: NX-481 and NX-483.

**Prior context.** `docs/review/ENTERTAINMENT-S0-S1-2026-10-28.md`, and Q-TD-84, 91, 93, 97, 98, 102, 103, 104 and 105 in `docs/planning/OPEN-QUESTIONS.md`.

**Probes.**
- Measured and read-only, on a `git archive e69f16a` tree with the T0 config.
- Each samples every 15 game minutes: owners, pool, budget, tier, live units and `no_capture_reason`. Each logs captures with participant counts, hold start and break, the end cause, each Static operation launch, and newbie join and first impact.
- **Q1/Q4 probe:** raid-300, seeds 2 and 3, `--hours 24`, run to campaign end (L-39).
  - s3 ended at 66736 ticks, final hash `43876cb6b81df9d9…`.
  - s2 ended at 315713 ticks, final hash `e07f947c4ac86dae…`.
  - The config hash `2757b80f…` and both final hashes match the queue.
- **Q5 probe:** quiet-5, seeds 1 and 2, `--hours 24`.
  - Final hashes `8970097d8ab93fab…` and `f994ad0bfd8394a8…`, matching the queue.
  - This probe also recorded each `retake:` job posted on the coalition board.
- No probes for Q3, Q6 or Q7. Q6 uses the Q1 probe's newbie data and the report's per-kind A2.
- The scripts stayed in the session scratchpad.

**Code read at e69f16a.**
- `campaign.py:181-182`: an HQ capture wins at once.
- `campaign.py:198`: the hold resets to 0 when it breaks.
- `director.py:75-78`: night spacing.
- `director.py:102-104`: `rear_share` is floor(pool × frac).
- `economy.py:38-41`: storage cap = floor + held nodes.
- `economy.py:78-81`: the pool is clipped to the cap.
- `launch.py:139-143`: the purse's rear account.
- `launch.py:284`: the cap check.
- `content/operations.yaml:12`: OFFENSIVE costs 60. `:21`: RETAKE costs 50.
- `balance/default.yaml:265`: `source_spend_frac` 0.005.
- `balance/default.yaml:364-371`: storage floor 2000; per node AIRBASE 2000, FOB 1000, HQ 2000.
- `balance/default.yaml:139`: `hq_capture` true.
- `tasking_gen.py:66-75`: the retake job rule.
- `tasking.py:1059`: `refuel_stuck`.
- `tools/balance/report.py:98-110`: A2 tail rules.
- `tools/balance/profiles.yaml:72-79`: steamroll signals.

**What doesn't exist yet.** The overlay, the site and clips. Every audience view is rebuilt from events, and every score is an estimate. The harness report has no coalition-capture line and no HQ line.

## 2. Findings

### Q1. Q-TD-97: the spend value

| raid-300 | S0 0.005 | T0 0.01 | T1 0.02 |
|---|---|---|---|
| Outcomes | 6 V, median 2.0 h | 6 V: 4.31, 8.77, 1.85, 1.85, 1.96, 1.92 h | 1 V (18.44 h), 5 not ended |
| Holds broken / total | 0/6 | 7/13 | 43/43 |
| Offensives (captured) | 7 (0) | 48 (3) + RETAKE 3 (1) | 664 (217) + 46 (14) |
| Budget per window / ENEMY income per hour | 46.5 / 395.8 | 65.0 / 1180.9 | 161.3 / 2981.7 |
| `budget` as first no-capture reason | – | 361 windows | 0 |
| HOLD_AT_RISK / STRIKE_DOWNED | – / 43 | 8 / 136 | 200 / 1511 |

**Probe s3 (1.85 h; the 4 fast seeds look like this).**
- The Static's pool sat at 8000 (its cap) until about 1 h, with a budget of 80–106.
- It launched 3 Offensives in the whole war. The first-reason sample was `staged` from 0.5 to 1.25 h.
- The coalition took east-airbase and two FOBs. The cap fell to 4000 and the pool was clipped to 3970.
- The hold started at 1.354 h. Its budget samples were 40, with first reason `budget`, and the hold ran its full 30 min.
- There was 1 Static flip: fob-s-e, which the coalition recaptured 2 min later.

**Probe s2 (8.77 h).**
- The coalition took 6 of 8 nodes by 2.9 h.
- From 3.26 h to 7.90 h, no node changed hands for 4.64 h (278 min, derived). The Static held fob-n-e, fob-s-e and its HQ, a cap of exactly 6000. Its budget was exactly 60 (floor(6000 × 0.01)) in nearly every window.
- It launched an Offensive every 15–45 min. All 29 captured nothing, and most sat `staged`.
- The coalition pool also hit its 10000 cap, so both sides were rich and stuck.
- Hold breaks:
  - start 2.886 h, broken after 22.4 min (fob-s-e);
  - start 7.897 h, broken after 20.9 min (fob-n-e);
  - start 8.352 h, broken after 13.5 min (fob-s-e).
- The breaking flips were not capture operations: no Static operation in the run targeted fob-s-e or fob-n-e.
- Which Static units flip them, and why they are there, is [UNVERIFIED]. T0 raid has many more ESCORT, GARRISON_UPKEEP and REINFORCE_IADS operations than S0 (107/68/74 against 26/36/23). Whether that explains the flips is an [estimate].
- The harness's "Static captures" counts only operation captures. Probe s2 had 5 Static flips, while the report shows 4 operation captures across all 6 seeds.

**The hold-phase cliffs (derived).** During a hold the Static's budget is about floor(storage cap × frac). The cap is 4000 when the Static holds only its HQ, and 5000 when it also holds a FOB. In every probed hold the coalition held east-airbase.

| frac | Hold-phase budget | What it buys |
|---|---|---|
| 0.01 | 40–50 | nothing at 40; a Retake at 50 |
| 0.0125 | 50–62 | a Retake almost always; an Offensive only at the 5000 cap |
| 0.015 | 60–75 | one Offensive per window in every hold |
| 0.02 | 80–100 | Offensives in every hold, plus the opening-economy feedback seen in T1 (income 2.5×) |

**Verdict.**
- 0.01 is the only tested value that ends wars (A1 6/6 ended). It is also better than 0.02 at prime:
  - longest dry stretch median 185 vs 242 min;
  - A2 tail 29.9% vs 34.9%;
  - momentum 49.7 vs 46.8.
- Quiet-5 and overnight-0 are identical between T0 and T1, so the spend key has no effect there (the night cap and the tier bind).
- A value between 0.01 and 0.02 crosses the 50/60 cost cliffs during holds. More broken holds, not more contested wins, is the likely result [estimate].
- 0.01 is the safer 5b default. "Resistance" should grow through the hold rule (Q-TD-102) and coalition hold defence (Q-TD-98), and spend should rise only after that.

### Q2. Q-TD-102 (a broken hold keeps progress)

- **What T0 shows.**
  - The winning holds had 0–3 pressure events (steamroll signal S2 per seed: s3 1, s4 3, s5 0, s6 3). So holds can be contested and still won, but only when the Static can't afford a reply.
  - The breaks (s1 4, s2 3) are fast flips back of thinly held eastern FOBs, 18.8 min from the Static.
- **Verdict.**
  - The reset is acceptable at 0.01, so keep it (b) for 5b.
  - Spend and the reset interact. Any future increase ("raise difficulty slightly", Q-TD-91) needs Q-TD-102 (a) first, or raid goes back to T1's 43/43.
  - Keep the row open for the owner, recommending (a) before any spend increase.
  - NX-466 (the hold pauses under pressure, Q-TD-84) can go ahead after 5b. At 0.01 it only lengthens the contested winning holds [estimate].

### Q3. Q-TD-104 (night cap at prime)

- **Cap share.** `night_cap` was the first-reason window 47.5% of the time at T0 (4103 of 8640, derived). T1 was 4412 (51.1%) and S0 was 2811 (32.5%).
- **Prime over time:**

  | | R2 (b0bc4e3) | S0 (8f9a5ff) | T0 (e69f16a) |
  |---|---|---|---|
  | Static captures | 63 | 46 + 1 | 53 + 1 |
  | Longest dry stretch median (min) | 286.5 | 367 | 185 |

- **Caveats.**
  - The rise in cap share from S0 to T0 may be a counting shift after NX-480, which holds staged operations under the cap. That is [UNVERIFIED], and the runs are at different shas (L-37).
  - How many cap windows would have launched without the cap is [UNVERIFIED]. `max_ops` (1354) and `staged` (1925) would also bind often.
- **Verdict.** Prime has its best pacing and balance yet, so a separate fade reference is not warranted for 5b. Take (b) and add a watch item.

### Q4. Q-TD-105 (HQ grabs)

- **Probe seeds.**
  - s2: `static-hq` was captured at 8.770 h by 1 commander, with 193 live viewer units, during a hold of 7 of 8 nodes that had run 2328 ticks (3.9 min).
  - s3: won by a full hold; the HQ was still Static at the end.
  - s1 and s4–s6: [UNVERIFIED]. The end times of s4–s6 (1.85–1.96 h) fit a hold starting at about 1.35–1.45 h plus 30 min, so they are probably hold wins [estimate].
- **Verdict.**
  - The T0 HQ grab is the best clip in the batch: a stalemate of over 4 hours ends in 50 minutes, with two broken holds and a lone commander taking the HQ.
  - It ended a war that was about to be won anyway. S1's grab, at 4 of 8 nodes held, was the side-door case.
  - Keep (a). Revisit (b) only if an HQ win at under 50% of nodes held happens again.

### Q5. Quiet-5 with the retake job (NX-475)

| Quiet-5 probe | S0 probe (8f9a5ff) | T0 probe (e69f16a) |
|---|---|---|
| s1: share of time at 3 / 2 / 1 strategic nodes | 65.6 / 24.0 / 10.4% | 58.3 / 39.6 / 2.1% |
| s2: share of time at 3 / 2 / 1 strategic nodes | 29.2 / 27.1 / 43.8% | 66.7 / 31.2 / 2.1% |
| Coalition retakes | none | s1: west-airbase at 20.29 h (lost 19.86). s2: fob-n-w at 21.14 h (lost 20.74), fob-s-w at 22.47 h (lost 14.46). Each by 1 commander. |

- **Queue, all 6 seeds, S0 → T0:**
  - momentum 33.9 → 39.2;
  - Static captures 11 → 9;
  - starved node-minutes 1825.8 → 1222.5;
  - longest dry stretch median 406.5 → 383.5 min.
- **Static flips still follow the 6 h cap clock.** s1: 1.65, 7.85, 14.06 and 19.86 h. s2: 0.98, 7.79, 14.46 and 20.74 h.
- **Verdict: yes, it helped.**
  - Each retake followed a retake job posted 0.1–0.4 h earlier. That a truck claimed that job is [UNVERIFIED]; the probe did not log claimants.
  - The S0 → T0 comparison crosses shas (NX-467, NX-480 and NX-468 also changed), so how much of the gain is NX-475 is [UNVERIFIED].
  - The front now swings at a calm pace: the Static takes a node about every 6 h, and the coalition takes some back.
- **Readability problem.**
  - In s1, `retake:fob-s-w` was posted 14 times between 14.07 and 21.5 h and never succeeded.
  - The job only qualifies while the node's defense hp is 0 (`tasking_gen.py:66-75`), so on stream it would blink in and out of the NEEDED list.
- NX-481 (freeze on any last node) would have mattered in only 2.1% of samples here.

### Q6. The raid A2 tail (45.8% at T0)

- **Per-kind tail at T0:**

  | Kind | Newbies | Tail |
  |---|---|---|
  | Capturer | 31 | 100% |
  | Hauler | 24 | 82.6% |
  | Scout | 12 | 100% |
  | Auto-tasked | 126 | 33.1% |
  | Striker | 28 | 0% |

  - Weighted, that is about 60% role kinds and 40% auto-tasked (derived; the denominators differ slightly).
  - At T1, same sha, the auto-tasked tail is 8.8%.
- **Probe.**
  - Newbies at ALPHA or above who ended in the tail: 15 of 23 in s3, and 41 of 94 in s2 (the reviewer's count, using the report's rule).
  - s2 newbies who joined between 0.37 and 1.02 h waited 2783–5915 s for their first hit.
  - Static units on the map were 5–35, against about 190–245 viewer units.
  - Raid idle reasons: `full` 4497, `refuel_stuck` 6389.
- **Verdict.**
  - It is Q-TD-98, but the cause is too few targets: the Static fields too little. Board capacity is how that shows on the board.
  - The role-kind part is unchanged from S0/S1.
  - `refuel_stuck` (NX-467, `tasking.py:1059`) is large at raid in both runs (6389 / 10474). Whether it hits newbies is [UNVERIFIED].

### Q7. The final 5b set

- **Candidate:** B + strike-first + `director.staging.max_wait_windows=30` + `director.source_spend_frac=0.01`, with Q-TD-79 and Q-TD-90 unchanged.
- **A confirming run is needed before 5b ships (L-37).**
  - NX-483 keeps capture jobs alive mid-bar on both sides. That touches the raid flips that break holds, prime capture completion (78 started, 53 captured at T0) and the retake job's flapping.
  - NX-481 changes quiet day 2.

## 3. Audience scores (estimates, 1–5; T0, with S0 → T0 at raid)

| Audience | overnight-0 | quiet-5 | prime-50 | raid-300 (S0 → T0) |
|---|---|---|---|---|
| Watcher | 2 | 2.5 | 3.5 | 2 → 3 |
| Player | – | 3 | 3 | 2 → 2.5 |
| Site watcher | 2.5 | 3.5 | 3.5 | 1.5 → 2.5 |
| VOD and clip | 1.5 | 2 | 3.5 | 2 → 3 |

Three biggest problems per audience:
- **Watcher:**
  - 4 of 6 raid wars end in under 2 h with a quiet final hold;
  - raid s2 had a 4.6 h stretch with no node changing hands;
  - quiet moves only every 6 h.
- **Player:**
  - raid joiners wait up to 1–1.6 h for a first hit (too few targets);
  - capturer, hauler and scout joiners almost never get an impact;
  - coalition captures are made by 1 commander, so FOBs are lost again within minutes.
- **Site watcher:**
  - raid maps freeze for hours when both sides are rich;
  - the harness can't show coalition or HQ captures yet;
  - quiet retake jobs flap.
- **VOD and clip:**
  - the s2 finale (two broken holds, then a 1-commander HQ grab) is the best clip, but it comes once in 6 seeds;
  - fast seeds have no climax;
  - quiet is clip-poor.

## 4. Recommendations (ranked)

| # | Suggestion | Kind | Audience | Expected effect (estimate) | Cost | Touches |
|---|---|---|---|---|---|---|
| 1 | Ship `director.source_spend_frac` 0.01 in 5b; no value between 0.01 and 0.02 | **Tuning** | All | Raid wars end with some contest; prime best; quiet unaffected | 0 | `balance/default.yaml:265`, Q-TD-97 |
| 2 | Run U0 to confirm (below) | Harness | All | Checks 5b on the shipping code (NX-481, NX-483) | About 1 h of queue | NX-412 5b |
| 3 | Hold-defence job: during a running hold, idle coalition units get a defend or garrison job on the hold nodes the Static can reach | **Design** | Player, Watcher | Late joiners have something to do (A2); 1-commander FOB captures stop being flipped back for free; a crowd massing on hold nodes reads well | M | GAMEPLAY §1b, Q-TD-98, Q-TD-118 |
| 4 | Q-TD-102 (a) is a precondition for any spend above 0.01 | **Design**, sequencing | Watcher, VOD | Stops a later "raise difficulty" step from bringing back T1's stalemate | S–M | `campaign.py:198`, ECONOMY EC-9 |
| 5 | NX-466 may go ahead after 5b, with a raid-300 recheck | Sequencing | Watcher | Contested winning holds last longer and feel more tense | 0 | Q-TD-84 |
| 6 | Harness add-ons: all `NodeCaptured` by side (not only operation funnels); HQ capture with participant count; longest stretch with no node changing hands; per-kind A2 denominators | Tooling | Lead | Answers Q-TD-105 and "Static captures" without probes | S | `tools/balance/metrics.py`, `report.py`, NX-478 |
| 7 | Retake job hysteresis: keep a retake job posted for N min after the node's defenses return, or show it as "strike needed" | **Design** | Player, Site | NEEDED list stops blinking (14 postings in 7.5 h) | S | `tasking_gen.py:66-75`, Q-TD-99..101, NX-484 |
| 8 | Steamroll S1 needs a minimum absolute count: under 2 h, 4 pressure events read as 8.6 per 4 h (s3), which passes the PROPOSED 2-per-4h line | Tooling | Lead | The flag catches fast-seed near-steamrolls | S | `tools/balance/profiles.yaml:73`, Q-TEST-11, NX-478 |
| 9 | Look at `refuel_stuck` at raid (6389 / 10474 samples) | Investigation | Player | Possibly part of the A2 tail [UNVERIFIED] | S | NX-467, `tasking.py:1059` |

**Run U0 (#510), which gates 5b.**
- sha 3aa67f38271a02fe58e6372ab0cea3d9ac501680 (develop, with NX-481 and NX-483); all four profiles; 6 seeds; 24 h.
- Config: B + strike-first + `director.staging.max_wait_windows=30` + `director.source_spend_frac=0.01`.
- Pass reading:
  - raid: at least 5 of 6 ended, at least 1 hold broken, 0 steamroll flags;
  - prime: longest dry stretch median at most 250 min;
  - quiet: momentum at least 35;
  - overnight: A3 pass.

**Run U1 (#511), optional and not gating.** U0 at raid-300 only, with `director.source_spend_frac=0.015`. It tests the cliff prediction: if holds broken climbs toward all of them, that is evidence for Q-TD-102 (a).

**Later:** raid-300 at `hours: 72` for A1, once 5b ships.

## 5. Watch items, questions and decisions

**PLAYTEST-WATCHLIST additions** (for the coordinating session; this PR does not edit `docs/quality/`):
- A raid stretch of more than 2 h with no node changing hands while both pools are at their caps (probe s2: 4.64 h).
- A hold-phase Static budget below the cheapest capture operation (`budget` as first reason during a hold) in most holds.
- A coalition retake job posted more than 5 times on one node without a capture.
- A raid auto-tasked A2 tail above 20% while Static units on the map are under 10% of viewer units.
- Keep from S0/S1: a raid war ended by an HQ capture with 3 or fewer participants (now 2 of 2 observed).
- `night_cap` as first reason in more than 50% of prime windows together with a longest dry stretch median above 300 min.

**OPEN-QUESTIONS:**
- Q-TD-97, Q-TD-102, Q-TD-104 and Q-TD-105 get notes.
- New: Q-TD-118, the hold-defence job (recommendation 3), for the owner.

**Decisions (lead, owner may veto):**
- **Q-TD-97:** 0.01 is the 5b value, with no value between 0.01 and 0.02 because of the hold-phase cost cliffs. Crowd-scaled spend stays deferred.
- **Q-TD-91:** T0 meets "at least some resistance" at the minimum (6/6 ended, 0 steamroll flags, 7 of 13 holds broken). More resistance comes through Q-TD-102 and Q-TD-98, not spend.
- **Q-TD-102:** keep the reset for 5b. The row stays open for the owner, recommending (a) as a precondition for any spend increase.
- **Q-TD-104:** (b), keep the cap. Close it with a watch item, and reopen it if the watch condition fires.
- **Q-TD-105:** (a) for now. The T0 grab was a finisher at 7 of 8 nodes.
- **NX-466:** unblocked after 5b, with a raid recheck.
- **5b gating:** U0 at 3aa67f3 runs before 5b ships; U1 is optional.
- **Quiet-5 A2** (n = 8, 1 in the tail): still not a gate.
