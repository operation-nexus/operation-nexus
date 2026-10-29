# Entertainment review: W0 #519, W1 #520, W2 #521 (sha 9f8d058), 2026-10-29

The `entertainment-reviewer` (Opus) wrote this review and the lead wrote it up.

**Runs.** All 24 h, 6 seeds, the four profiles:
- W0: the shipped NX-412 part 5b defaults (control).
- W1: NX-473 on, at `logistics.ai_trucks.max_live` 3, `director.pol.convoy_demand_s` 300 and `tasking.resupply_slots_max_starving` 6.
- W2: W1 plus NX-487 probe values: `logistics.node_max_stock` ×1.5, and fighter, strike-fighter and recon UAV `logistics.loadout_cost` halved, both sides.

**Sources.**
- A Sonnet agent copied the queue numbers verbatim from the report comments. The reviewer read the per-role A2 blocks and Static lines in the comments themselves.
- The reviewer also ran probes at develop 974b2b1, which is 9f8d058 plus NX-488 (equivalent behaviour). Config hashes differ from the queue's because NX-488 deleted keys, so no final state hash can match.
- Equivalence evidence: W2 quiet-5 s1 reaches DEFEAT at tick 576225, the report's exact tick.
- Every audience score is an estimate, because the overlay, site and clips don't exist yet.

## Verdicts
- **NX-473: ship with changes, not at W1's values yet.** W1's gains are real: starved node-minutes fell (quiet 1222.5 → 470.3, prime 330.3 → 187.3), raid idle armed fell from 38% to 13%, and raid captures rose from 3 to 18. But W1 measured NX-473 with LC-1 mostly not running (F1). Ship it after the LC-1 fix and the LC-2 split (below).
- **NX-487 (W2 values): don't ship.** It shows no gain over W1: prime A2 tail 38.7%, raid holds broken 11 of 16, prime max dry stretch 331 min. It also raises every base's starvation floor and stock target with the larger maximums, which means more hauling, the opposite of Q-TD-119's intent (derived). Redo it after the fix, with the floor held.

## Findings
**F1. LC-1 deadlock (NX-473 code bug, measured).**
- `ai_trucks.py:90` lets a job get an AI truck only once `now - j.created >= period`, and spawns run only when `now % period == 0`.
- An unclaimed job expires after `tasking.expire_min` (15 min = 9000 ticks) and is re-posted with a new `created`. `logistics.ai_trucks.period_s` is 900 s, also 9000 ticks.
- So an unclaimed job is never old enough, and AI trucks join only jobs a viewer already holds.
- Measured:
  - overnight-0 W1 s1, 6 h: 72 coalition resupply jobs, 0 AI truck spawns, 0 deliveries.
  - prime-50 W1 s1, 24 h: 3 AI trucks.
  - With `logistics.ai_trucks.period_s=420`: 3 AI trucks in hour 0 and 14 deliveries.
- None of the 34 NX-473 tests covers expiry. Tracked as NX-492 (Q-SIM-131).

**F2. Prime A2 regression (W0 29.1% → W1 39.9%): NX-473, through the Static's convoys, not AI trucks (1 seed; the mechanism is an inference).**
- On prime-50 s1: Static convoy spawns rose from 36 to 88, enemy fighter spawns from 401 to 962, and Static units killed by coalition air-defense sites from 425 to 897. Kills by viewer jets fell from 472 to 247, and viewer hits from 2188 to 1149.
- The Director spent 5.8 h at Pattern of Life against 1.2 h.
- The regression is in the auto role (queue: auto tail 10.7% → 26.0%; striker 17.1% → 12.0%).
- Reading: LC-2 demand convoys, plus LC-3's larger convoys, bring escort fighters that the coalition's AI sites kill, so newly auto-tasked jets lose their targets.
- AI trucks taking newcomers' jobs is refuted on this seed: 3 spawns all day.
- Not split: LC-2 against the LC-3 convoy share.

**F3. The W2 quiet-5 DEFEAT (s1, 16.01 h): F1 plus a seed where every truck died. NX-487's share is [UNVERIFIED].**
- By 9.36 h all 10 AI trucks were destroyed. Three viewer trucks died within about 0.25 h with no delivery, and no AI truck spawned again (F1).
- West-airbase was at 0 defense hp from 9.25 h, drained of stock by 11.75 h, and captured at 14.85 h.
- Static strike fighters then took haven from 1000 hp to 0 by 15.5 h, and DEFEAT followed at 16.01 h.
- The coalition had no counter-play:
  - the board never posts a defend job at a sanctuary (GAMEPLAY §1b `defend:`, "not a sanctuary or bridge");
  - no job sends trucks to repair it.
- On the same seed, W1 kept delivering every hour because viewer trucks kept breaking the deadlock.

**F4. Raid (queue numbers only).** W1 passes U0's pass reading: 5 of 6 ended, 8 holds broken, 0 of 5 flagged. Momentum fell from 56.7 to 45.1, which reads as more contest. Prime dry stretch median 178.5 (needs ≤ 250) and quiet momentum 46.7 (needs ≥ 35) also pass. The NOT_ENDED seeds (W1 s1, W2 s4) were not probed.

## Audience scores (estimates, 1–5, W1 with W2 in brackets)
| Audience | overnight-0 | quiet-5 | prime-50 | raid-300 |
|---|---|---|---|---|
| Watcher | 2 (2) | 3 (2.5) | 3.5 (3) | 3 (2.5) |
| Player | – | 3 (2.5) | 2.5 (2.5) | 3 (2.5) |
| Site watcher | 2 (2) | 3.5 (3) | 3.5 (3.5) | 3 (2.5) |
| VOD and clip | 1.5 (1.5) | 2 (2.5) | 3 (3) | 3 (2.5) |

## Risks, ranked
1. **LC-1 deadlock.** While `period_s` ≥ `expire_min`, the 0-viewer cadence is off, and a quiet stream can lose its supply chain for good.
2. **No counter-play to a sanctuary siege.** `campaign.defeat.hold_min` then runs out on screen.
3. **Prime newcomers lose their targets to escort fodder** (1 seed).
4. **W2's higher floors raise demand** while the cadence is broken.
5. **Raid NOT_ENDED seeds**, cause [UNVERIFIED].

## Decisions and follow-ups (lead)
- **NX-492 (Q-SIM-131, lead decision):** fix the LC-1 eligibility so a job's age is not reset by TB-1 re-posting. Spec first, with a test at the shipped `expire_min`.
- **NX-493 (Q-TD-122, owner):** sanctuary defence, a defend job and a truck repair job at a sanctuary under siege.
- **NX-487 / Q-TD-119:** don't ship the W2 values. Redo after NX-492, with storage alone and the starvation floor held (`logistics.starve_threshold` 0.1667 with the larger maximums), and coalition costs alone. Whose loadout costs to cut goes to the owner.
- **Harness, queued at develop 60d6cd4 (L-37 same-sha control):**
  - X0: W1's three keys (control).
  - X1: LC-2 off (prime-50, raid-300).
  - X2: W1 plus the stopgap `logistics.ai_trucks.period_s=420`, to see the cadence actually on.
- **Watchlist:**
  - a coalition resupply job expiring unclaimed for more than 1 h while AI trucks are on;
  - a sanctuary at 0 defense hp with no coalition unit within defend range;
  - air-defense sites' share of Static kills above 60% at prime, together with an auto A2 tail above 20%.

Probe scripts and outputs are in the lead session's scratchpad; they are not committed.
