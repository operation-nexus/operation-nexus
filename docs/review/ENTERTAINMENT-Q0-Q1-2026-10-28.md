# Entertainment review: harness runs Q0 #470 and Q1 #471 (SEAD sha 7d0b50e), 2026-10-28

## Bottom line

1. **SEAD's job rule is not what makes raid end fast; Q-TD-86 is.** Q-TD-86 is the NX-461 rule that a Disabled facility stays Disabled until it is repaired to the Mission-kill line (`services/sim/src/nexus/core/rules.py:411-419`).
   - The probe ran raid-300 seed 2 at 7d0b50e under B, with Q-TD-86 patched out in the probe process only. That run followed the pre-SEAD control almost tick for tick:
     - 0 coalition captures in 8 h;
     - every coalition STRIKE job EXPIRED;
     - defenses went down at the same time (2.855 h).
   - Unpatched, the same seed won at 4.93 h, which matches the queue report.
2. **On strait-1, a raid crowd needs only two FOBs to win.** A hold needs 7 of 8 strategic nodes (`campaign.victory_node_frac` 0.80; `campaign.py:176`).
   - The coalition starts with 3 of them, and the two crossings are NEUTRAL and cost nothing to take. So fob-n-e plus fob-s-e is enough.
   - The owner's A1 sets no floor on how fast a campaign may end ("a large, coordinated crowd may win in 4 h or less", `docs/quality/TESTING-STRATEGY.md` §3.5a). So a 5 h raid win is within the rules. **The problem is the steamroll share, and strike-first fixes that.**
3. **Q-TD-79: turn strike-first on in NX-412 part 5b**, with NX-465 (the overfill fix, Q-TD-89) as its companion.
   - Q1's raid ring idle is the overfill block, not a lockout: SEAD keeps `strike:east-airbase` on the board at 0 HP in every ring sample.
4. **The raid `refuel` idle is the Q-TD-88 trap again,** about 74% of raid idle samples in both runs. NX-464 is the fix.

## 1. What was reviewed

- **Numbers.** The lead's extract of the #470 and #471 queue reports.
  - Both runs: sha 7d0b50e, 24 h, 6 seeds, prime-50 + raid-300.
  - Base overrides B: `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`, `director.adaptation_up_above=2`. Upkeep 0.
  - Q1 adds `combat.strike_structure_first=true`.
  - Controls: N0 #451 and the P series (ee1d570).
  - "Derived" marks the reviewer's own arithmetic.
- **Probes (measured, read-only).**
  - Tree: a `git archive` of 7d0b50e, plus the ee1d570 archive for the pre-SEAD control.
  - Method: every probe is `--hours 24` stopped early (L-39). It calls the harness's own `runner.run` and `override_balance`, reads events, and samples every 15 game minutes.
  - "Q-TD-86 off" patches `UnitRules.state_after` to plain `state(hp)` in the probe process only.
  - The probe scripts and outputs lived in the session scratchpad and are not in the repo.
- **Code read** at 7d0b50e and develop:
  - `tasking.py`: `_SEAD_KEY` (159-161), the SEAD verdict (641-650), `_open` (307-313), `_feasible` (1103-1117), `_refuel` (1271-1276);
  - `tasking_gen.py` (`live_site`, 188-191);
  - `rules.py:411-419`;
  - `combat.py:140-170`;
  - `rearm.py` (between ee1d570 and 7d0b50e only `state_after` was added; the starved cap is unchanged);
  - `campaign.py:176` and `balance/default.yaml`.
- **Caveats.**
  - The causal probes use one seed (s2). They prove a mechanism, not a 6-seed frequency.
  - NX-463 (#474) merged during the review and changes the world schema, so develop runs are a new sha (L-37).
  - overnight-0 and quiet-5 were not in Q0/Q1.
  - The overlay, site and clips don't exist yet, so every score is an estimate.

## 2. Answers

### Q1. Why SEAD ends raid fast, and whether it is a balance problem

**Capture sequence, raid s2 (measured):**

| Run | Coalition captures (h) | Static captures | Coalition STRIKE jobs | Static node at 0 defense HP (15-min samples) | Result |
|---|---|---|---|---|---|
| Pre-SEAD ee1d570 | cross-n 4.02/4.61 (flipped twice), cross-s 6.69 | cross-n 3.35, 4.29 | 0 DONE, 64 EXPIRED | 1 of 108 | not ended at 7 h |
| Q0 7d0b50e | fob-s-e 3.10, cross-s 3.42, fob-n-e 3.68, cross-n 4.43 → hold 4.43 | 0 | 8 DONE, 31 EXPIRED | fob-n-e 4/14, fob-s-e 2/12 | VICTORY 4.93 |
| Q0, Q-TD-86 off | none | none | 0 DONE, 72 EXPIRED | 1 of 93 | not ended at 8 h |
| Q1 7d0b50e (strike-first) | east-airbase 1.64, fob-n-e 3.30, plus crossing flips | cross-s 1.17, cross-n 1.84, cross-s 2.09 | 67 DONE, 16 EXPIRED | fob-s-e 14/15, east 6/6 | VICTORY 3.80 |

**Disabled time of the Static air-defense sites (measured, sim seconds):**

| Run | fob-s-e | fob-n-e | east-airbase |
|---|---|---|---|
| Pre-SEAD | 137 events, 18 s | 156 events, 21 s | 122 events, 2 s |
| Q0 | 35 events, **8547 s** | 42 events, 536 s | 61 events, 387 s |
| Q-TD-86 off | 192 events, 25 s | 145 events, 17 s | 177 events, 3 s |

**Mechanism (from the code).** Units are always picked before structures, and a Disabled facility is not a valid target (`combat.py:16-18`, `_target_levels` docstring at `combat.py:168-170`).
- **Before Q-TD-86:** each SAM was knocked to Disabled more than 100 times and was back up within a tick each time. Jets kept spending rounds on a site that can't be destroyed.
- **With Q-TD-86:** each Disabled spell is 6 sim seconds at an airbase and 13 at a FOB (39 and 78 world seconds at `sim.time_scale` 6). A site whose base has no stock stays Disabled until stock returns: fob-s-e, 8547 s in total, with stock 0 in the 2.25 h and 2.5 h samples. In those windows the bombs fall on node defense HP. So Q-TD-86 turns strike-first-off into a partial strike-first.
- How the gain splits between rounds moving to defenses and the SAM going quiet is [UNVERIFIED].

**The SEAD job rule still matters.** It remains the real fix for sweep N's lockout: in Q1 s1 and s4, `strike:east-airbase` stays on the board in every sample, including those where east's defense HP is 0. On its own it barely moves the raid trajectory.

**Is it a balance problem?**
- **Length is not a target.** A1 sets no floor.
- **raid-300 is a constant crowd,** a fixed 300 viewers for the whole run (`tools/balance/profiles.yaml:28`). So "raid wins in 5 h" means "300 viewers held for 5 h win", which is fair.
- **The real problem is a war with no middle.** In Q0 raid the Static captures nothing (funnel 18>0>0>0>0) and 4 of 6 wins are flagged as steamrolls. Q1 has the same win rate but a contested middle: 12 Static captures, crossings changing hands, 1 of 6 flagged.

**Levers** (each key was checked against `override_balance`):

| Lever | Kind | What the probes show |
|---|---|---|
| `combat.strike_structure_first` | Tuning | The steamroll fix: 4/6 → 1/6 flagged |
| `campaign.victory_node_frac` | Tuning | 0.9 makes all 8 nodes necessary. With strike-first on (s2), victory moved from 3.80 to 4.64 h. With it off, east-airbase sat at about 500 HP from 4.25 to 10 h, a stalemate. Not a clean length lever. |
| `campaign.victory_hold_min` | Tuning | Sweep P1: only delays. |
| `logistics.repair_rate.AIRBASE` / `.FOB`, `logistics.facility_repair_hp_per_stock` | Tuning | Set the Q-TD-86 off window. They do nothing for a site whose base has no stock. Untested [UNVERIFIED]. |
| A facility-restore key (the "later key" that Q-TD-86 allows) | Design | A separate off window instead of the Mission-kill line |

### Q2. Q-TD-79: should strike-first go on in 5b?

**Yes**, with NX-465 (Q-TD-89) as its companion and a same-sha low-population pair before 5b ships (L0 #475 / L1 #476).

| | Prime off (Q0) | Prime on (Q1) | Raid off | Raid on |
|---|---|---|---|---|
| Wins / steamroll flags | 2 / 1 | 3 / **0** | 6 / 4 | 6 / **1** |
| Static Offensive funnel | 189>13>11>13>13 | 162>68>53>64>63 | 18>0>0>0>0 | 45>22>9>12>12 |
| Static captures per seed-day (derived) | 2.2 | **10.5** | 0 | 2.0 |
| Holds (broken) | 2 (0) | 5 (**2**) | 6 (0) | 7 (1) |
| Longest stretch without an Offensive, median (min) | 532.3 | **370.8** | 297.1 | 227.9 |
| A2 tail | 29.4% | 27.1% | 33.9% | 31.9% |
| Ring idle share of idle samples (derived) | — | — | 3.0% | 20.3% |

- On makes prime the best stream in the series: holds get broken, there are 5 RETAKEs, and dry stretches shrink.
- At raid it costs nothing in outcome. Its cost is ring idle, which is the overfill block NX-465 removes.
- Q-TD-78 (captured sites change hands Disabled) stays parked. Q1 s2 shows east-airbase changing hands with its SAM up, and the Static then holding it Disabled for 3413 s. That reads as a retake beat, not a lockout.

### Q3. Is raid `refuel` idle the Q-TD-88 trap?

Yes.
- **Share (derived):** 42926 / 57650 = 74.5% of idle samples in Q0 raid and 44534 / 60974 = 73.0% in Q1, against 84.9% in sweep P1. The lower share comes from more `full` (Q0) and more `ring` (Q1), not less trap.
- **Probe (Q0 s2, 0.5–1.5 h):** every `refuel` jet was LANDED at starved west-airbase, at about 0.5 tank, holding a STRIKE job. That was 101–128 jets per sample.
  - West-airbase stock was 358–491, under its floor of 500.
  - 74 jets stayed in `refuel` for 5 or more consecutive samples (75 min or longer).

### Q4. Q1 raid ring idle (12407): overfill block or lockout?

**The overfill block (Q-TD-89).**
- Every ring sample in seeds 1, 2 and 4 has the blocker `AIR_DEFENSE_SITE@east-airbase -> STRIKE:static-hq`. The one exception is 7 samples blocked at fob-n-w, which the Static held in s4.
- `strike:east-airbase` was on the board at every one of those samples.
- In s2 at 1.25 h, the claims were east 5/5, fob-n-e 5/5, fob-s-e 5/5 and static-hq 0/5: the sweep P signature.

### Q5. What to queue

- **Now, at develop 08831d0** (includes NX-463): L0 #475 (overnight-0 + quiet-5, B) and L1 #476 (the same + strike-first).
- **After NX-464 and NX-465:**
  - R1: prime-50 + raid-300, B + strike-first. This is the 5b base control.
  - R2: R1 + `director.staging.max_wait_windows=30` (the Q-TD-90 re-run).
  - R3, optional: R1 + `campaign.victory_node_frac=0.9`, only if R1 raid has more than 1 of 6 steamrolls.

## 3. Audience scores (estimates, 1–5)

| Audience | Q0 prime | Q0 raid | Q1 prime | Q1 raid |
|---|---|---|---|---|
| Watcher | 2.5 | 2.5 | 3.5 | 3 |
| Player | 3 | 2 | 3 | 2 |
| Site watcher | 2.5 | 2.5 | 3.5 | 3 |
| VOD and clip | 2 | 2.5 | 3 | 3 |

- **Watcher.**
  - Q1 prime: 63 Static captures and broken holds.
  - Q1 raid: crossings change hands within the first 2 h.
  - Q0 raid is a one-way push.
  - Top problems: 100–160 jets parked at west-airbase; Q0's uncontested raid win; a SAM-off window viewers can't see.
- **Player.**
  - Raid idle armed is 65–68%, about three quarters of it the refuel trap; Q1 adds the overfill block.
  - A2 fails everywhere (tails 27–34%).
- **Site watcher.**
  - Broken holds (Q1 prime, 2) are the first real async story.
  - The Static's income at raid is a third of the coalition's (866 against 2585), so the story is "the Static can't come back".
- **VOD and clip.**
  - A broken hold, east-airbase falling at 1.6 h, and a crossing changing hands three times in an hour all fit 15–60 s clips.
  - Q0 raid's climax is a 30-minute hold with no fight.

## 4. Recommendations, watch items, questions

### Ranked recommendations

1. **Strike-first on for 5b** (tuning; Q-TD-79). It ships with NX-465. Expected effect: raid steamroll flags 4/6 → about 1/6 and prime Static captures about 5× (Q1, measured).
2. **NX-465 overfill** (design, S; Q-TD-89): removes about 20% of Q1 raid idle.
3. **NX-464 starved-base refuel** (design, S; Q-TD-88): about 74% of raid idle.
4. **Queue L0/L1 now; R1/R2 after NX-464 and NX-465.**
5. **Record Q-TD-86 as the raid-speed cause.** If R1 raid still steamrolls, try `logistics.repair_rate.*` or `logistics.facility_repair_hp_per_stock` before a new facility-restore key. Keep "the site stays off while its base has no stock".
6. **Don't lengthen raid on purpose** (A1). Keep `campaign.victory_node_frac` at 0.80.
7. **Harness tooling:** an idle label for "ring, others full" (part of NX-465) and a job-claim column in the ring report.

### Watch items for PLAYTEST-WATCHLIST

- A Static site Disabled for more than 1 h in total per seed-day (its base is starved).
- Raid wins where the Static captures 0 nodes.
- Ring idle where the blocked job's alternatives are full.
- An east-airbase capture that hands its SAM over live, and the retake that follows.

### Owner questions (recorded as lead decisions, owner may veto)

1. Turn `combat.strike_structure_first` on in 5b (Q-TD-79)? **Recommend yes**, with NX-465, if the same-sha L0/L1 pair shows no A3 failure at overnight-0.
2. Should a facility stay Disabled indefinitely while its base has 0 stock (Q-TD-86 as built)? **Recommend yes**: supply decides the war. Revisit with the repair-rate keys only if R1 raid steamrolls again.
3. Is a 4–6 h win by a constant 300-viewer crowd acceptable, given A1's "no floor"? **Recommend yes** (Q-TD-91). Judge raid by its steamroll share, not its length, and add a burst-style raid profile under NX-321.
4. Wait for NX-464 and NX-465 before the prime and raid runs? **Recommend yes.** Run the low-population pair now.
