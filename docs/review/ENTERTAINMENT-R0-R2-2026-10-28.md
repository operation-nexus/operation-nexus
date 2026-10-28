# Entertainment review: R0 #480, R1 #481, R2 #482 (sha b0bc4e3), 2026-10-28

## Bottom line

1. **A 2 h raid win does not meet Q-TD-91's "at least some resistance".**
   - NX-464 and NX-465 worked: coalition jets now fly. Raid `refuel` idle fell from about 43k samples (Q1) to 0.5–1.5k, and ring idle went to about 0.
   - The Static now offers nothing: 0 captures in all 18 raid seeds, 0 broken holds, and hold pressure all 0 in R1.
   - Cause, probed on raid s4: **the Static dies rich.** Its pool sits at the storage cap (8000) for the first hour. The window budget can draw only about 40 a window from it. Its one Offensive is staged for about half of all decision windows. With strike-first on, every Static air defense is down within 4–6 minutes.
2. **The raid A2 tail is real.**
   - About 90% of raid newbies join during the 5-minute ramp, at Pattern of Life. A2 excludes them.
   - The counted late joiners find one strike job at 10 of 5 claims and nothing left to shoot.
3. **Q-TD-79 holds.** Strike-first goes on in NX-412 part 5b together with NX-474.
   - Raid's failure is on the Static side under both settings (0 captures in R0 and in R1).
   - At prime, strike-first is clearly better: 67 captures against 13, and a median longest dry stretch of 361 min against 721.5.
4. **Q-TD-90: take `director.staging.max_wait_windows` 30 for 5b.** R2 beats R1 on every prime story metric and is neutral at raid.
5. **The fix for raid steamroll is Static spending, not campaign length.** `campaign.victory_node_frac`, `campaign.victory_hold_min` and the NX-466 hold pause add no resistance on their own. The hold pause triggers only on Static pressure, and raid holds have none.

## 1. What was reviewed

**Numbers:** the lead's R-series extract of #480–#482.
- All three: 24 h, 6 seeds, prime-50 + raid-300, base overrides B (`economy.legacy_rules=false`, both `economy.unlimited.*=false`, `director.adaptation_up_above=2`), upkeep 0.
- R1 = B + `combat.strike_structure_first=true`. R2 = R1 + `director.staging.max_wait_windows=30`.
- Same-config controls before NX-464/465: Q0 #470 and Q1 #471.
- "Derived" marks the reviewer's own arithmetic.

**Probe (measured, read-only, one seed):** raid-300 s4 at b0bc4e3, `--hours 24`, stopped at the campaign end (L-39), with the R1 and R0 configs.
- Both reproduced the queue's end times: 1.70 h and 3.06 h.
- Every 15 game minutes it sampled tier, pools, owners, Static units, idle reasons, strike-job claims, and newbie joins and first impacts.
- One seed proves a mechanism, not a frequency.
- The scripts stayed in the session scratchpad.

**Code read at b0bc4e3:**
- `services/sim/src/nexus/core/economy.py:72-90`: income is clipped at storage.
- `director.py:120-140`: the budget formula.
- `tools/balance/metrics.py:229-234, 549-556, 700-720, 836-851` and `report.py:97-160`: how A2 is collected and judged.
- `tools/balance/profiles.yaml:28, 45`.

## 2. Findings

### Raid: what the Static does (probe s4)

- **Air defenses go first.**
  - R1: east-airbase, fob-n-e and fob-s-e defenses are down at 3.8–5.9 min (derived).
  - R0: down at 0.685–0.948 h.
  - Both reach BRAVO, the top tier, at 0.333 h. CHARLIE is parked (Q-TD-3), so there is no higher tier to escalate to.
- **It dies rich.**
  - The Static pool reads 8000 at 0.25, 0.5 and 0.75 h. That is its storage cap: 2000 floor + 2000 airbase + 2000 HQ + 2 × 1000 FOB (derived).
  - Income is `min(income, cap - pool)` (`economy.py:79`). So the reported "income 252/h" mostly measures income clipped by a full pool, not poverty.
  - Its money is later lost to STORAGE_LOST as nodes fall. It is never spent.
- **The budget can't reach the pool.** The formula is `floor(base surplus × spend_frac[tier]) + floor(pool × source_spend_frac)`. At 8000 × 0.005 that is 40 a window (derived). The base-surplus term at struck bases is [UNVERIFIED].
- **The one Offensive spends the war staged.** Decision windows by first reason:

| Config | Windows | Launched | Staged | Budget | Floor not due | Tier |
|---|---|---|---|---|---|---|
| R1 | 102 | 1 | 53 (52%) | 17 | 18 | 9 |
| R0 | 183 | 1 | 90 (49%) | 74 | 7 | 9 |

- **The army thins out.** Static live units drop from 26 to 8–12 (R1) and from 25 to 0–5 after 1.25 h (R0).
- **Some strikes still land.** 31 Static `STRIKE|op` jobs ended DONE in R1 s4, but none were Offensive strikes. Which operations they belonged to is [UNVERIFIED].

| Raid | Static captures | Hold pressure | Holds broken | Steamroll | Median win |
|---|---|---|---|---|---|
| Q1 (before NX-464/465) | 12 | [2,2,1,0,0,0,3] | 1 | 1/6 | 5.1 h |
| R0 | 0 | [0,1,0,0,1,0] | 0 | 4/6 | 3.0 h |
| R1 | 0 | all 0 | 0 | 6/6 | 1.9 h |
| R2 | 0 | [0,2,0,0,0,0] | 0 | 5/6 | 2.0 h |

### Raid A2

- **Ramp newbies are excluded.** In probe s4, 113 of 125 newbies (R1) and 113 of 139 (R0) joined between 0.001 and 0.137 h, at Pattern of Life. A2 excludes them (`a2_min_tier: ALPHA`). They did fine: median 267 s and 615 s, mostly hits.
- **Counted late joiners do badly.** In R0 s4, 17 of 26 had no impact by the campaign end. The probe's tail is 87%, which reproduces the queue's 85.9%.
- **Why:** after 0.75 h, 29–96 of about 130 armed jets idle as `full`. The board holds one strike job at its overfill cap (10 of 5), and the Static has 0–12 units left.
- **The run-end "unresolved" rule hides the worst cases rather than adding them** (`report.py:101-113`). The short war also shrinks the judged sample, so R1-against-R2 A2 differences are noise-sized.

### Prime

| | R0 (off) | R1 (on) | R2 (on, wait 30) |
|---|---|---|---|
| Outcomes | 6 not ended | 6 not ended | 5 not ended, 1 victory at 16.09 h (not a steamroll) |
| Static captures | 13 | 67 | 63 |
| RETAKE launches | 1 | 7 | 13 |
| Longest dry stretch, median (min) | 721.5 | 361 | 286.5 |
| Holds (broken), pressure | 1 (1), [2] | 0 | 2 (1), [5, 2] |
| Momentum | 52.7% | 38.7% | 45.2% |
| A2 tail | 32.3% | 28.2% | 26.8% |
| STAGING_DISPERSED | 33 | 45 | 99 |

R2 against R1 at raid is neutral: seeds 1, 3, 4 and 6 end at the same lengths, and steamrolls are 5/6 against 6/6.

### Levers for raid steamroll

Every key below passed `override_balance` at b0bc4e3. None has been probed, so each effect is [UNVERIFIED].

| Lever | Kind | Expected effect (estimate) | Risk |
|---|---|---|---|
| `director.source_spend_frac` 0.005 → 0.02 | Tuning | About 160 a window at a pool of 8000; targets "dies rich" directly | Global: the quiet-5 Static pool sat at its 14000 cap in L1, so it speeds the quiet collapse unless NX-474 is in |
| `director.spend_frac.bravo` | Tuning | More spend from base surplus | Weak where bases are struck; global |
| `campaign.victory_node_frac` 0.9, `campaign.victory_hold_min` | Tuning | Length only | Adds time, not resistance |
| NX-466 hold pause | Design (owner-agreed) | Inert at raid while hold pressure is 0 | None; build it for prime |
| Crowd-scaled Static spend above `capture.quiet_ref` | Design | Matches the owner's "if 300 becomes common, raise difficulty slightly" | M |
| Spend the pool before it is lost (an emergency draw when a storage node is under capture) | Design | A visible last stand | M |

## 3. Audience scores (estimates, 1–5)

| Audience | Prime R0 | Prime R1 | Prime R2 | Raid R0 | Raid R1 | Raid R2 |
|---|---|---|---|---|---|---|
| Watcher | 2.5 | 3.5 | 3.5 | 2.5 | 2 | 2 |
| Player | 3 | 3 | 3 | 2 | 2 | 2 |
| Site watcher | 2.5 | 3.5 | 3.5 | 2 | 1.5 | 1.5 |
| VOD and clip | 2 | 3 | 3.5 | 2.5 | 2 | 2 |

- **Raid R1** on stream: every SAM down in 6 minutes, then a 1.5 h one-way push into a hold with no fight. 30–96 jets idle as `full`. The Static's full war chest is invisible and never spent.
- **Prime R1/R2:** Static captures, retakes and broken holds. R2 has the most retake beats and the shortest dry stretches.

## 4. Recommendations, watch items, decisions

### Ranked recommendations

1. Strike-first on in 5b, with NX-474 (Q-TD-79).
2. `director.staging.max_wait_windows` 30 in 5b (Q-TD-90).
3. Static spend at high crowds (Q-TD-97).
   - First a tuning probe, S1: `director.source_spend_frac=0.02` at the NX-474 sha against the S0 control.
   - If quiet-5 or prime regress, move to crowd-scaled spend (design).
4. Coalition board capacity at raid (Q-TD-98; design after item 3): more strike capacity, or a non-strike job, for a large crowd's late joiners.
5. Build NX-466 as agreed, but don't count on it for raid until the Static can pressure a hold.
6. Harness tooling (NX-478):
   - Static income lost to the storage clip;
   - A2 for below-ALPHA newbies (information only);
   - idle `full` next to the board's open strike slots.
7. Keep `campaign.victory_node_frac` 0.80 and `campaign.victory_hold_min` 30.

### Next runs (after NX-474 merges; a new sha carries its own control, L-37)

- **S0:** B + strike-first + `director.staging.max_wait_windows=30`, on overnight-0, quiet-5, prime-50 and raid-300. This is the 5b candidate control.
- **S1:** S0 + `director.source_spend_frac=0.02`.

### Watch items for PLAYTEST-WATCHLIST

- The Static pool at its storage cap for more than 30 min while at BRAVO.
- A raid win with 0 Static captures and 0 hold pressure.
- All Static air defenses down within 10 min of a raid ramp.
- More than 25% of live armed viewer units idle as `full`.
- STAGING_DISPERSED more often than once per hour at prime.
- Prime momentum under 40% averaged over a seed-day.

### Decisions (lead, owner may veto)

- **Q-TD-91 follow-up:** R1 raid (0 Static captures and 0 hold pressure on 6/6 seeds) fails "at least some resistance". The fix is Static spend (Q-TD-97), not length keys.
- **Q-TD-97:** Static spend at high crowds. Tuning probe first; the design option only if the global key hurts quiet or prime.
- **Q-TD-90:** confirmed. `director.staging.max_wait_windows` 30 ships in 5b.
- **Q-TD-79:** unchanged. Strike-first is on in 5b, together with NX-474.
- **Q-TD-98:** coalition board capacity grows with the live crowd. Design item, after Q-TD-97, judged by A2 for late joiners.
