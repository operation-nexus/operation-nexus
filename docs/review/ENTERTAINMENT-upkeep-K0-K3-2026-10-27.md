# Entertainment review: upkeep series K0–K3 (2026-10-27)

**Bottom line:** no tested upkeep value meets the rare-shortfall targets at raid-300. Prime-50 passes at K1 (period 20). The cause at raid is how many jets one forward airbase has to feed, not enemy action. My pick for NX-412 part 5b is to keep upkeep at 0.

## 1. What was reviewed

- **Runs:** K0 #421 (control, upkeep 0), K1 #422 (upkeep 1, period 20, recon 30), K2 #423 (period 10) and K3 #424 (period 5).
  - Charged kinds: STRIKE_FIGHTER, RECON_UAV, ENEMY_STRIKE_FIGHTER, ENEMY_FIGHTER, ENEMY_ARMOR and ENEMY_RECON_UAV. GARRISON_INFANTRY stayed at 0.
  - Each job ran at sha `86af552`, prime-50 and raid-300, seeds 1–6, 24 h, 12 workers. Economy on, both sides limited, `director.adaptation_up_above=2`.
- **Source:** every measured number comes from the queue report comments on #421–#424, which the lead copied into one extract for the `entertainment-reviewer` agent (Opus), since it cannot read GitHub. Figures marked "derived" are the reviewer's arithmetic on those numbers. Owner questions from §6 are Q-TD-75 to Q-TD-77.
- **Code read at the working tree (not run):** `upkeep.py`, `economy.py`, `logistics.py`, `director.py`, `tasking_gen.py`, `tools/balance/metrics.py`, `balance/default.yaml`, `content/operations.yaml`, `content/theaters/strait-1.yaml`.
- **What doesn't exist yet:** the overlay, the site and clips. So every audience view is rebuilt from the reports. Scores are estimates.
- **Built before the floor fixes:** this sha predates NX-439/441/434 (per the sweep M review), so the prime droughts here overstate what develop does now.

## 2. Q1: rare-shortfall targets (all PROPOSED)

Raid run-hours are derived from the VICTORY times in the extract: K0 132.4, K1 101.8, K2 100.2, K3 70.2. Prime is 144 run-hours at every K. R3 is judged per home, as the target says; the worst home is west-airbase, and its rate is the report's per-run-hour figure times west's share.

| Target | K1 prime | K2 prime | K3 prime | K1 raid | K2 raid | K3 raid |
|---|---|---|---|---|---|---|
| R1 ≤ 1% | 0.0 ✔ | 0.0 ✔ | 0.4 ✔ | 6.9 ✘ | 13.6 ✘ | 15.9 ✘ |
| R2 ≤ 5% | 0.0 ✔ | 0.0 ✔ | 0.5 ✔ | 17.0 ✘ | 27.5 ✘ | 39.8 ✘ |
| R3 per home (prime ≤ 0.25/h, raid ≤ 0.5/h), median ≤ 10 windows | 0 ✔ | 0 ✔ | 0.03, med 6 ✔ | west 0.40, med 7 ✔ | west 0.75 ✘ | west 1.54 ✘ |
| R4 ≤ 10% | 0.0 ✔ | 0.0 ✔ | 5.5 ✔ | 41.9 ✘ | 50.8 ✘ | 56.5 ✘ |
| R7 budget per window ≥ 85% of K0 | 88.7% ✔ | 83.8% ✘ (marginal) | 67.4% ✘ | 76.0% ✘ | 66.4% ✘ | 44.0% ✘ |
| R7 Offensives ≥ 85% of K0 (raid per run-hour, derived) | 93.6% ✔ | 109% ✔ | 62.2% ✘ | 64% ✘ | 47% ✘ | 13% ✘ |
| R10 never | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ (2 stretches, 447 min) |
| R11 ≥ 50% | n/a (0 episodes) | n/a | 0/4 ✘ | 1.7% ✘ | 6.3% ✘ | 0.7% ✘ |

**Verdict:**
- **Prime:** K1 passes every target that applies.
- **Raid:** fails at every K, the mildest included.
- **The predicted knee wasn't there.** The 2026-10-26 review expected raid shortfall to stay rare at a period of about 15 or more. K1, at period 20, already grounds 6.9% of viewer unit-time.
- **Why the prototype misled:** P4 measured 0.15% at raid, but that was 1 seed × 2 h, before NX-428. West-airbase starts with 1000 stock, which lasts the first hours, so short runs under-predict. That is a lesson for future upkeep probes.

## 3. Q2: why raid shortfall happens

**What the code does:**
1. A viewer jet spawns at haven. When it runs out of bombs, standard RTB sends it to the **nearest** landing base (`logistics.py:84`). Landing makes that base its home (`logistics.py:383`, EC-5).
2. At the start the coalition's landing bases are haven (x = 20 km) and west-airbase (x = 90 km) (`strait-1.yaml:21-22`). From the front, west-airbase is nearer, so almost every jet that comes back re-homes forward.
3. A home pays upkeep from its own stock (`upkeep.py:220-227`); only the source pays from the pool.
4. **Income goes only to the pool at haven.** `economy.py:80` adds every node's `income.per_node`, west-airbase's 10 per window included, to the source pool. West-airbase gets stock only by truck.
5. That truck-fed stock also pays every rearm and repair (`rearm.py`; STRIKE_FIGHTER `loadout_cost` 20). The base holds at most 2000 (`balance/default.yaml:34`).

**What the data shows:**
- The coalition pool stays healthy at K1 and K2 raid (last pool 7906 and 7400).
- West-airbase holds 41 of 58, 77 of 95 and 111 of 151 episodes at K1, K2 and K3.
- R11 is near zero, so the shortage is self-inflicted. It is the "6000 in the pool, yet my jet is grounded" case the last review warned about, now measured.
- Grounding reaches job holders: 3.5% at K1 rising to 15.0% at K3, from the "grounded by previous state" mix. The EC-6 payment order can only choose who grounds when the home holds some stock. Job holders grounding means the home is fully dry, not trimmed at the margin.
- **The base was short before upkeep.** K0 raid already had 1423.7 starved node-minutes against 227.3 at prime. Upkeep is a second drain on a base that rearm demand had already emptied. That these minutes are mostly west-airbase is [UNVERIFIED]: the report doesn't split them by node.

**So, to the brief's question:** yes, in effect. The raid crowd cycles hundreds of jets through one forward airbase that earns nothing locally and is fed only by trucks. The max grounded at once was 218, 244 and 175. Hauling throughput, not the upkeep value, is what binds.

**Estimate of the hauling gap:** a 100-stock truck on a round trip of 70 km or more each way delivers about 60–65 stock per hour. K3's 1910 per hour of coalition upkeep, if mostly at west, would need about 30 trucks cycling for upkeep alone. The per-home split of upkeep is [UNVERIFIED].

**R11 is slightly understated:** it doesn't count depot raids (`tools/balance/README.md:88`). The concentration at west-airbase doesn't depend on that.

**Side effect on the idle metric:** idle armed share at raid "improves" from 62% to 45%. But `is_idle` excludes grounded units (`tasking_gen.py:217`), so idle jets were relabelled as grounded, not put to work.

## 4. Q3: why raid Offensives collapse and steamrolls rise

**How the reserve works:**
- EC-7 subtracts `floor(upkeep_reserve_windows × owed)` (`director.py:133-136`).
- `owed` is the ceiling of Σ upkeep ÷ period over every charged Static unit (`upkeep.py:190`), passed in at `step.py:92`. The shipped key is 2.
- I estimated the reserve from the Static upkeep it actually paid per hour. This is an estimate: groundings were rare on that side, so paid ≈ owed.

| | Static upkeep per window | Reserve (est.) | Budget drop vs K0 |
|---|---|---|---|
| prime K1 / K2 / K3 | 1.39 / 3.47 / 4.58 | 4 / 8 / 10 | 7.3 / 10.5 / 21.1 |
| raid K1 / K2 / K3 | 1.23 / 2.44 / 3.28 | 4 / 6 / 8 | 18.1 / 25.3 / 42.2 |

**Reading it:**
- The reserve explains about half of the prime drop but only about 15–30% of the raid drop.
- **The reserve counts upkeep twice.** Upkeep is already paid from Static stock, and that lowers next window's surplus. The reserve then holds back two more windows of it, even though `spend_frac` (0.02–0.053) already caps one window's spend far below the stock (design reading).
- **A small budget loss has a big effect.** OFFENSIVE costs 60 (`content/operations.yaml:12`). Budget per window falls 75 → 57 → 50 → 33, from above that line to below it. Cheap operations go on (Static ops per hour 42.4 → 36.6), but Offensives stop.
- **The rest of the raid drop is a feedback loop [UNVERIFIED]:** fewer Offensives, so uncontested coalition captures, so the Static loses nodes. That shrinks its storage and surplus; Static last pool fell from 8100 to about 5900. That lowers the rear share, so even fewer Offensives.
  - Raid steamrolls went from 1/1 at K0 to 4/4, 2/3 and 5/5.
  - Victory holds went from 1 to 5–6, with 0–2 broken.
  - The per-window no-capture reason (NX-452) would settle the loop; it isn't in these reports.
- **K3 prime droughts are probably not upkeep's fault alone.** Seeds 1 and 5 had one early Offensive, then a 1414- and a 1430-min tail. That matches the pre-fix floor pattern; re-test at tip.

## 5. Q4: audiences (scores are estimates; M0 gave 2 everywhere)

| Audience | K1 prime | Raid (K1→K3) | Evidence and biggest problems |
|---|---|---|---|
| Watcher | 2 | 1.5 | Prime looks like K0, since grounding never happens there. At raid, STAGING sitreps fall 2.41 → 0.26 per run-hour: no enemy build-up to watch. The "out of supply" beat is chronic and muted (EC-6a quiet gap), not a story. |
| Player | 2 | 1–1.5 | 42–57% of raid viewers are grounded at some point (R4), job holders included. Newbie A2 median 330 → 692 s, tail 37 → 46%. The fix for the player is hauling, which harness personas don't do at scale. |
| Site | 2 | 1.5 | Raid campaigns end as steamrolls in 5–17 h. No comeback arc; 0–2 holds broken. |
| VOD | 2 | 1.5 | No cut → dry → resupply → relaunch payoff, because R11 is near 0. Fewer flips per seed; K3 raid funnel 21 > 1 > 0 > 0 > 0. |
| Low population | not tested | — | EC-11, quiet-5 and overnight-0 were not in K. |

## 6. Q5: recommendations

**Ranked options:**

| # | Option | Type | Effect (estimate) | Owner? |
|---|---|---|---|---|
| 1 | **Keep upkeep 0 for every kind in 5b** (shipped). The NX-426 period machinery stays dormant. | Tuning (no change) | R1–R11 pass trivially; loses the grounding beat, which at raid was never a beat anyway | Yes, as confirmation (Q1 below) |
| 2 | `director.upkeep_reserve_windows` 0 (or 1) | Pure tuning | Gives back about 4–10 budget per window; recovers prime R7 at K2/K3; doesn't fix raid grounding | No (Q-DEV-21) |
| 3 | Charge upkeep to the side's pool rather than the forward base it last landed at (an EC-5 amendment for upkeep only) | Design, S–M | Raid grounding then tracks the pool (R10), which only drops when income is lost (a side-level enemy cause). Loses the per-base alarm. | Yes (Q2) |
| 4 | Viewer units free up to a per-base count | Design, M | Too weak: west held up to 244 grounded at once, so any allowance small enough to matter at prime still drowns at raid | Yes |
| 5 | Scale airbase stock or income with crowd size | Design | Conflicts with TS-1 (income doesn't grow with the crowd). A bigger `node_max_stock` alone doesn't fix truck throughput. | Yes |
| 6 | Upkeep for the Static only | Design; breaks EC-3 parity | Removes viewer grounding but keeps the reserve and Static-budget hit, the steamroll lever K shows. Worst for raid arcs. | Yes |

**For NX-412 part 5b:** take option 1, and add option 2 as a dormant tuning (it matters only once upkeep is non-zero).

**Before any upkeep return, run these:**
- **K4:** K1 values plus `director.upkeep_reserve_windows=0`, at the develop tip (floor fixes in), prime-50 and raid-300.
- **Raid-only K5 at period 40:** tells whether any period passes. Extrapolating R1 suggests about 3%, still a fail (rough estimate).
- **Report change:** split starved node-minutes and upkeep paid per node.

**Owner questions (#412), each with a recommendation:**
1. **Ship 5b with all upkeep at 0,** since no tested value keeps raid grounding rare (Q-TD-50)? *Recommend yes.*
2. **Should upkeep be paid by the side's pool instead of the forward base a jet last landed at (EC-5)?** *Recommend: try it as K6 before deciding.* It is the only option that addresses the measured cause.
3. **Does "rare" (Q-TD-50) hold at raid-300 and surge-500 too, or may big crowds hit forward shortage as an army cap (Q-TD-16(1))?** *Recommend rare at every profile, with EC-8 as the only cap.*

## 7. Q6: cross-host determinism note

**What matches:** K0 equals M0 #415 on both funnels (172>11>10>17>17 and 315>15>12>17>17), on Offensive counts, on A2 (147 s / 27.1% and 330 s / 37.3%) and on prime starved minutes (227).

**What that proves:** it is strong evidence that sha `86af552` plays the same game as `1b5fd60`. That fits the sweep M finding that the diff touches only tools, tests and docs.

**What it doesn't prove:**
- **Tick-level equality.** Matching aggregates aren't matching states.
- **That the runs were on different hosts.** The extract doesn't name hosts.
- **The new R-metrics.** They have no M0 counterpart.

**What settles it:** compare K0's final hashes (prime s1 `c456e8aac280e996`, raid s3 `d2bb5168b8eeb55c`) with M0's. That comparison hasn't been done.

## 8. Watch items for PLAYTEST-WATCHLIST

- **Forward-airbase concentration:** jets re-home to the nearest base. Revisit if any single base holds more than 50% of shortfall episodes.
- **Idle share falls when grounded rises:** read idle and R1 together.
- **Upkeep probes under 24 h under-predict raid shortfall:** P4 measured 0.15%, K3 measured 15.9%.
- **R11 ignores depot raids.**