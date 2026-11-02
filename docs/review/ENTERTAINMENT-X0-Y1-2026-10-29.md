# Entertainment review: X0 #525, X1 #526, X2 #527, Y1 #528 (sha 60d6cd4), 2026-10-29

The `entertainment-reviewer` (Opus) wrote this review and the lead wrote it up.

**Runs.** All 24 h, 6 seeds, at 60d6cd4.
- X0: NX-473 W1 keys (control).
- X1: X0 without LC-2 (`director.pol.convoy_demand_s` 3600). prime-50 and raid-300 only.
- X2: X0 + `logistics.ai_trucks.period_s=420` (stopgap so LC-1 runs).
- Y1: X0 + `logistics.starve_threshold=0.05` (owner's minimum-supply floor idea, Q-TD-123).

**Sources.**
- A Sonnet agent copied the queue numbers by hand. The reviewer checked every number used here against the report comments (6494525512, 6494503711, 6495787151, 6496732999).
- The reviewer ran 6 probes on `git archive` trees:
  - five at 60d6cd4, each reproducing its queue run's final hash exactly;
  - one at 70d7d5c (the #530 LC-1 fix plus #529 NX-486).
- Every audience score is an estimate, because the overlay, site and clips don't exist yet.

## How the harness numbers read (from the code)
- **H1.** "Starved" counts nodes below the floor itself (`tools/balance/metrics.py:401-406`). Y1 lowers the floor, so its Starved numbers can't be compared with X0's.
- **H2.** The starvation floor is also the Static's budget base: surplus = stock above `starve_floor` (`nexus/core/director.py:93-99`). It is also used by forward deploy, run loading, rearm and LC-1. So Y1 also makes the Static richer:
  - budget / window, quiet 119.7 → 140.0 and prime 147.1 → 163.8;
  - strike packages downed, prime 84 → 99.
- **H3.** Raid aggregates pool seeds of very different lengths (`report.py:225-243`). The 24 h NOT_ENDED seed dominates idle armed and A2.

## Verdicts
**Q1. LC-2 is the main cause of the prime A2 regression, and also the main source of NX-473's prime starvation gain.**
- prime-50, X0 → X1: A2 tail 39.2% → 32.1% (W0 29.1%); auto-role tail 21.9% → 13.8% (W0 10.7%); starved 215.0 → 349.0 (W0 330.3).
- Without LC-2 the Static escalates more: BRAVO 1.65 → 3.14 h, strike packages downed 84 → 160, Offensive captures 43 → 56.
- Escort operations moved only 3933 → 3393. Inference: LC-2 works mainly as a brake on escalation, which also lowers starvation. The W0-W2 F2 escort-fodder reading is weakened [UNVERIFIED].
- Raid idle armed (X1 34% against X0 13%) is a seed-mix artifact (H3). On the matched short seed s2 every variant is about 41% (probes A, B, C).
- Raid s2 A2 median: X0 1610 s, X1 571 s.
- **Decision (lead):** don't ship LC-2 yet. Re-test off (V1) and damped at 900 s (V2), with LC-1 fixed.

**Q2. LC-1 actually on (X2): it works, as a one-time top-up at 0 viewers.**
- overnight-0 momentum 41.0 → 51.4.
- On s1, 3 AI trucks and 14 deliveries (1400 stock), all in hours 0-1, none after: a fresh campaign has no further demand.
- prime and raid are within noise.
- The #530 fix at 70d7d5c gave the same on overnight s1 (probe E: 3 spawns, 14 deliveries, momentum ends at 52).
- quiet-5 starved 470.3 → 373.8. Its longest stretch without an Offensive reached 644 min (cause [UNVERIFIED]).
- The X2 raid R10 pool stretches (2, 84 min) are probably one seed's path, not drain [UNVERIFIED].
- **Decision (lead):** ship `logistics.ai_trucks.max_live` 3 and `tasking.resupply_slots_max_starving` 6 once control C0 at 70d7d5c reproduces this. Don't ship `period_s` 420.
- **Harness gap:** nothing measures LC-1 on the night after a busy day.

**Q3. Y1 (low floor): not better play as tested; NX-495 on hold.**
- **Hauling:** coalition income per hour (a proxy for stock drawn and hauled) was prime −9%, quiet flat, raid +3%. Raid s2 deliveries per hour were about the same. Coalition trucks lost on raid s2: 23 against 2.
- **Raid A2:** 239 s against 766 s pooled, not reproduced on s2 (1601 s against 1610 s).
- **Momentum:** lower everywhere.
- **Overnight ambient Static movement:** escorts 209 → 25.
- **Design flaw (H2):** a lower floor makes the Static richer, and under Q-TD-119 parity it does so for both sides. Q-TD-125 asks the owner whether the Director's surplus should get its own reference.

## Risks, ranked
1. Floor variants can't be judged on "Starved", and the floor sets the Static's budget (H1, H2).
2. LC-2 trades newcomer impact for prime starvation.
3. Raid pooled metrics are dominated by one 24 h seed (H3).
4. overnight-0 can't show "the night after a busy day".
5. Quiet-5 stretches without an Offensive reach 600 min or more (X2, Y1).
6. Raid R10 pool stretches unexplained.
7. NX-486 (#529) sits between the queue sha and develop: C0 re-runs at 70d7d5c.

## Audience scores (estimates, 1–5)
| Audience | overnight-0 (X0/X2/Y1) | quiet-5 (X0/X2/Y1) | prime-50 (X0/X1/X2/Y1) | raid-300 (X0/X1/X2/Y1) |
|---|---|---|---|---|
| Watcher | 2 / 2.5 / 1.5 | 3 / 2.5 / 3 | 3 / 3.5 / 3 / 3 | 3 / 3 / 3 / 3 |
| Player | – | 3 / 3 / 3 | 2.5 / 3 / 2.5 / 2.5 | 2.5 / 3 / 2.5 / 2.5 |
| Site watcher | 2 / 2.5 / 2 | 3 / 3 / 3 | 3.5 / 3.5 / 3.5 / 3 | 3 / 3 / 3 / 3 |
| VOD and clip | 1.5 / 1.5 / 1.5 | 2 / 2 / 2 | 3 / 3.5 / 3 / 3 | 3 / 3 / 3 / 3 |

**Biggest problems overall:**
- prime and raid A2 tails of 32–47% (target 10%);
- raid idle armed about 41% on short seeds, mostly `full`;
- overnight dead air.

## Follow-ups
- **Harness, queued at 70d7d5c:**
  - C0 #532: control.
  - V1 #533: LC-2 off.
  - V2 #534: LC-2 at 900 s.
  - V3 (floor 0.1) waits on Q-TD-125.
- **Harness changes to file:**
  - starvation against a fixed reference;
  - per-seed idle armed and A2;
  - a day-into-night profile.
- **Look into:** raid idle armed `full` (slot caps, NX-380 / Q-SIM-92) and quiet-5 Offensive gaps.
- **Watchlist:**
  - prime auto A2 tail above 20% while `convoy_demand_s` is below 3600;
  - raid idle armed above 35% per short seed;
  - quiet-5 stretch without an Offensive above 600 min.
