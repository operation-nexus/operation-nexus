# Entertainment review: harness sweep J0–J4 (2026-10-26)

**What was reviewed:** the five sweep jobs, #395 (J0, the control) and #396–#399 (J1–J4). Each ran prime-50 and raid-300, seeds 1–6, for 24 h, with 12 workers. The `entertainment-reviewer` agent (Opus) wrote it, and the lead checked the facts it rests on. "#39x Lnn" means line nn of that issue's final report comment. Scores are estimates.

## 0. The sha that actually ran
J1–J4 ran at **a0befff**, not the 26af630 now written in their issue bodies:
- **The evidence:** every results directory is `39x-a0befff1` (L1). The queue names that directory from the sha it recorded when it picked the job up, not from the issue body (`tools/balance/harness_queue.py:197-198, 258`).
- **Why the bodies are wrong:** the lead edited them after queueing.
- **The cost:** none of the five reports has the per-Offensive funnel.
- **Still a clean comparison:** `git diff a0befff 26af630` touches only `tools/balance/`, tests and docs. The sim, `balance/` and `content/` are identical.

**Process fix (NX-438):** the report prints the sha that ran, and the queue flags an issue whose body sha differs from the one it recorded (lesson L-30).

**Config at a0befff** (checked per L-28), plus each job's `set`:
- `economy.upkeep` is 0 for every kind.
- `director.max_ops.alpha` 1, `staging.max_wait_windows` 90, `score.victory_hold_mult` 1.0.
- `source_spend_frac` 0.005, `adaptation_up_above` 0.
- `cadence_windows` 10, `tasking.expire_min` 15.
- `capture.requires_defenses_down` true.
- Every job set `legacy_rules`, `unlimited.ENEMY` and `unlimited.COALITION` to false.

## 1. Per job
Offensives per run-hour are derived.

| Job | Offensives prime / raid (per h) | Gap median / max, min (prime ; raid) | Holds (broken), ops per hold | Wins (steamroll) | A2 median / tail (prime ; raid) | Sitreps |
|---|---|---|---|---|---|---|
| J0 #395 | 171 (1.19) / 315 (2.38) | 16 / 878 ; 6 / 315 | raid 1 (0) | raid 1 (1/1) | 146 s / 28.4% ; 330 s / 37.3% | ESC 2368, IADS 23, STG 182 ; ESC 780, IADS 210, STG 321 |
| J1 #396 `max_ops.alpha=2` | 251 (1.74) / 247 (2.10) | 12 / **1361** ; 9 / 297 | raid 2 (0) | raid 2 (1/2) | 145 / 25.8% ; 323 / 38.5% | STG 261 ; 282 |
| J2 #397 `max_wait 30`, `hold_mult 3` | 194 / 283 | 10.5 / 878 ; 10 / 425 | **none formed** | 0 | 180 / 27.2% ; 330 / 40.2% | STG 208 ; 326 |
| J3 #398 run E economy + `source_spend_frac 0.01` | 179 / 115 (1.34) | 11 / 820 ; 9 / 285 | prime 1 (0); raid 4 (**1**) | prime 1, raid 3 (**4/4**) | 146 / 25.7% ; **546** / 44.4% | STG 206 ; 155 |
| J4 #399 `adaptation_up_above=2` | same as J0 | same | same | same | same | **ESC 37, IADS 5 ; ESC 18, IADS 16** |

**Verdicts:**
- **J1: reject.** It doesn't fix the prime drought: the max gap gets worse (878 → 1361 min), ALPHA dwell is unchanged, and it adds more massing calls.
- **J2: not answered.** No victory hold formed, so the hold multiplier never applied. Don't adopt `max_wait_windows=30`. Q-TD-46 (NX-430) covers the hold case. Keep `victory_hold_mult` at 1.0 and re-test it with NX-430.
- **J3: reject.**
  - The budget recovered (69 per window against an Offensive cost of 60).
  - But raid Offensives per hour fell 44%, the Static's pool halved, raid A2's median failed (546 s against ≤ 480), and all 4 wins were steamrolls.
  - It also has the first victory hold ever broken (raid seed 2, #398 L48). The cause is unknown: no HOLD_AT_RISK sitrep appears, so it was likely a PROBE strike or a supply effect [UNVERIFIED].
- **J4: keep.** Every outcome is identical to J0. Escort sitreps fell from 16.4 to 0.26 per run-hour at prime.
  - **For NX-412 part 5b:** `director.adaptation_up_above=2`.
  - **Watch:** IADS_REINFORCED may now be too rare.

## 2. Where Offensives die: at the strike step (prime, measured)
**Method:**
- The reviewer ran scratch probes at 26af630 and at the develop tip 1b5fd60: prime-50, seeds 1–3, 6 h.
- It replayed every Offensive's jobs and units.
- A raid probe launched no Offensives in 2 h, so there is **no raid funnel data**.

**Funnel:** `launched 8 > strike_fired 0 > defenses_down 0 > capture_started 0 > captured 0` (the same at both shas).

**What happened to the 8 launches:**
- **5 of 8:** the strike jets fought coalition viewer jets on the way in. Each package fired about 34–43 air-to-air shots and was mission-killed or destroyed, mostly by viewer jets. The STRIKE job expired, so the CAPTURE job failed.
- **1 of 8:** the jets arrived and spent their whole AG_LIGHT load (4 rounds each, `content/weapons.yaml:12`) on the coalition AIR_DEFENSE_SITE at the node.
  - Under COMBAT CB-10, units always come first. A STRUCTURE weapon hits the node's defense HP only when no valid unit is in range (`combat.py:14-20, 140-141`).
  - An indestructible SAM site therefore absorbs every strike.
- **2 of 8:** still staging when the trace ended.

**CAPTURE can't bypass the strike:** it depends on STRIKE (TB-8), and `capture.requires_defenses_down` is true.

**A second possible limit:** STRIKE jobs expire after 15 min, while a rear-spawned jet needs about 20 min to reach west-airbase. None of the traced jets reached that limit.

**Options (Q-SIM-84):**

| # | Option | Cost | Note |
|---|---|---|---|
| 1 | A unit holding a STRIKE claim on a node's defenses fires at the node structure before its units. This extends the CB-10 bridge exception (Q-SIM-105). Behind a boolean key that defaults to today's rule. | S | Symmetric (EC-3), so it also strengthens viewer strikes; sweep it. Owner decision (Q-SIM-84 (4), no code tilt). |
| 2 | Strike claimants hold fire against aircraft until the strike is done, except in self-defence | M | Takes away a real viewer moment |
| 3 | A reach term in the Offensive score | S–M | Helps only mid-campaign |
| 4 | More strike slots or air-to-ground ammo | S | Weak; inflates the viewers' jets too |

**NX-427 can't fire.**
- **Why:** the cadence floor is due only after 10 windows with no launched operation of any kind (`director.py:102`), and the Static launches 35–44 cheap operations an hour.
- **Evidence:** probe B equals probe A metric for metric. Seed 3 had no Offensive for 360 min, with a budget per window of 40–59, always below the Offensive cost of 60.
- **Fix (S):** count the floor from the last capture operation (Q-TD-54).

## 3. Priorities
- **NX-430 (hold response):** after or alongside option 1. On its own it would only launch more Offensives that die at the strike step.
- **NX-431 (staging payoff sitreps):** raise its priority. STAGING is now the most common sitrep, and 0 of 8 massings were followed through.
- **NX-431 extension:** also "NULL strike package downed near <node>", crediting the viewer unit, because those dogfights are real coalition wins that nobody sees.

## 4. Scores (unchanged from the previous review)
| Audience | Score | Why |
|---|---|---|
| Watcher | 2 | Spam is gone, but massing calls have no payoff, and prime still has 13–23 h droughts |
| Player | 2 | A2 fails; viewer jets do break Offensives, but nothing credits them |
| Site | 2 | 7 won seeds, 6 of them steamrolls; J1 raid seed 5 is the best arc so far |
| VOD | 2 | The first hold ever broken, but its cause is unknown |

## 5. Next sweep "M"
Each job runs 6 seeds × prime-50 + raid-300 × 24 h, 12 workers, at develop 1b5fd60 or later.

**Base overrides (every job):** `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`, `director.adaptation_up_above=2`.

| Job | Extra overrides | Question |
|---|---|---|
| M0 control | none | The funnel at 24 h for both profiles |
| M1 | `director.source_spend_frac=0.0075` | Does a budget ≥ 60 end the prime droughts? |
| M2 | `director.op_priority.ESCORT_CONVOYS=0.5` | Does selection pressure from escorts cause droughts? |
| M3 | `tasking.expire_min=25` | Is the 15-min STRIKE life binding? (It also governs the coalition board.) |
| M4 | none; profiles overnight-0 + quiet-5 | Low population with the economy on |

**Later:** option 1 on, then NX-430 with `victory_hold_mult=3.0`. Then the best set at 72 h for A1.

## Questions
**For the owner (#412):**
1. Option 1: may STRIKE claimants hit node defenses before units?
2. Strike-package-downed sitreps crediting the defenders?

**For the lead (decided):**
- The cadence floor counts from the last capture operation (Q-TD-54).
- The harness prints the sha that ran (NX-438).
