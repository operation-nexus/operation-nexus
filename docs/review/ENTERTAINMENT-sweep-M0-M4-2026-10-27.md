# Entertainment review: harness sweep M0–M4 (2026-10-27)

**What was reviewed:** #415 (M0, the control) and #416–#419 (M1–M4).
- Each ran at sha `1b5fd60` with the economy on (`legacy_rules=false`, both sides limited) and `director.adaptation_up_above=2`.
- M0–M3 ran prime-50 and raid-300; M4 ran overnight-0 and quiet-5. All used seeds 1–6, 24 h each, 12 workers.
- Upkeep was 0 for every kind, so no job measures shortfall or EC-11.
- The `entertainment-reviewer` agent (Opus) wrote this; the lead checked the facts it rests on.

**Citations:** "#41x Lnn" is line nn of that issue's queue result comment, transcribed to a file for the review.
- The reviewer checked every total against its per-seed parts (Offensives, gaps, run lengths, A2 fractions, wall times) and found no mistranscription.
- The lead re-checked the two funnel lines and the M1 raid operations line against the files.

**Scores are estimates.** No viewer surfaces exist yet (no overlay, site or clips), so every audience view is rebuilt from the reports.

**How the funnel counts.** The harness credits each step to the newest launch on that node, whatever caused the step (`tools/balance/metrics.py`). So the steps are not nested: `capture_started` can exceed `strike_fired`.

## 1. Per job

| Job | Verdict | What it rests on |
|---|---|---|
| **M0 #415** control | **Baseline. Matches J4.** | Offensives: prime 172, raid 315 (J4: 171 / 315). Raid gap median / max 6 / 315, the same as J4. A2: prime 147 s / 27.1%, raid 330 s / 37.3%. Escort sitreps 0.20 per run-hour at prime. NX-427 was inert at this sha. |
| **M1 #416** `source_spend_frac=0.0075` | **Reject.** The second rejected source-share raise, after J3 at 0.01. | **Prime droughts shrink:** the longest dry stretch per seed is 100–402 min (M0: 445–1118). **Raid collapses:** 5/6 seeds won at 5.1–13.4 h, 4 of them steamrolls. Raid Offensives fall 315 → 82. Raid A2 median 464 s, tail 40.9%. Prime starved node-minutes 227 → 589. **More launches, fewer flips:** prime launches 172 → 284, but captures 17 → 11. |
| **M2 #417** `op_priority.ESCORT_CONVOYS=0.5` | **Reject.** Escorts don't crowd out Offensives. | Escort operations barely moved (prime 3142 → 3044, raid 2605 → 2882). Prime longest dry stretch got worse (850–1315 min). Prime Offensives 172 → 155. |
| **M3 #418** `tasking.expire_min=25` | **Reject.** The 15-min job life isn't binding. | Strike rate per launch unchanged within noise (prime 6.6% vs 6.4%, raid 5.3% vs 4.8%). The key also governs the coalition board, and it hurt raid newbies: A2 median 717 s, tail 47.8%. 2/2 raid wins were steamrolls, one at 3.56 h with zero Static Offensives. |
| **M4 #419** low population | **Information only; partly inconclusive.** | A3 passes. Quiet-5 A2 passes on 13 newbies. EC-11 untested (upkeep 0). Overnight-0: one Offensive every 360 min, exactly `director.pol.offensive_period_s`; 0/24 strikes fired, 0 captures. |

## 2. The funnel at 24 h

| Profile (job) | launched > strike_fired > defenses_down > capture_started > captured | Strike % | Captures per seed-day |
|---|---|---|---|
| prime M0 (#415 L92) | 172 > 11 > 10 > 17 > 17 | 6.4 | 2.8 |
| **raid M0 (#415 L99), the first raid funnel** | 315 > 15 > 12 > 17 > 17 | 4.8 | 3.1 |
| prime / raid M1 | 284 > 19 > 11 > 11 > 11 ; 82 > 1 > 1 > 3 > 3 | 6.7 ; 1.2 | 2.1 ; 1.2 |
| prime / raid M2 | 155 > 10 > 10 > 15 > 15 ; 295 > 12 > 10 > 15 > 15 | 6.5 ; 4.1 | 2.5 ; 2.6 |
| prime / raid M3 | 122 > 8 > 7 > 13 > 13 ; 152 > 8 > 8 > 10 > 10 | 6.6 ; 5.3 | 2.3 ; 2.3 |
| overnight-0 / quiet-5 | 24 > 0 > 0 > 0 > 0 ; 49 > 0 > 0 > 0 > 0 | 0 ; 0 | 0 ; 0 |

**Offensives still die at the strike step.** About 94% of prime launches and 95% of raid launches never see a Static shot at their target's defenses. None of the 73 low-population launches did either.

**What this sweep adds to the J0–J4 trace:**
1. **Overnight-0 has no viewer jets, yet 0 of 24 strikes fired.** The coalition's only kills there are by its air-defense sites (47 in 6 seed-days). Dogfights can't explain the overnight failures; air defense or CB-10 absorption must. Overnight-0 is the cleanest test of `combat.strike_structure_first` (NX-440).
2. **A capture that starts always finishes:** 101/101 Offensive captures across M0–M3, plus 2/2 Retakes. DEFEND jobs exist but never broke one, so the "base about to fall, defenders rush in" moment never happens.
3. **Raid opens with a long silence.** The first Offensive comes 444–824 min into the run (M0), although the raid crowd ramps in within 5 min. The reports give no reason per window.
4. **Prime has an early-burst-then-drought pattern.** About 4–5 Offensives come in the first hour or so, then nothing for 7–22 h. That points to an exhausted budget, which the merged floor fixes (NX-439, NX-441, NX-434) target.
5. **M1 has a recurring 91–100 min rhythm**, and all six raid lead-ins are exactly 100 min. The reviewer's hypothesis is the staging timeout; this is [UNVERIFIED], and a trace probe would settle it.
6. **"Gap max" leaves out the lead-in.** #415 reports a max gap of 878 min, but seed 5's lead-in was 1118 min.

## 3. Low population (M4)

- **Overnight-0:** the Static runs about 10.8 non-routine operations per hour, mostly RECON and patrols. The only notable events are 4 STAGING sitreps a day, none with a payoff. Dead air between notable events is about 360 min (estimate). No idle drift: 0 flips in 6 overnight days (Q-GP-28 expects the Static to gain slowly at 0 viewers).
- **Quiet-5:** the Static sits at ALPHA for 12.4 h and at Pattern of Life for 11.5 h. One seed had no Offensive in 24 h. There were 86 STAGING sitreps for 49 launches; NX-431's re-stage silence (Q-TD-64) targets exactly this.

## 4. Scores (estimates; J0–J4 gave 2 for every audience)

| Audience | Score | Biggest problems |
|---|---|---|
| Watcher | 2 | Prime droughts (longest 445–1118 min at shipped values); massing with no payoff; captures can't be contested |
| Player | 2 (raid nearer 1.5) | A2 fails; 62% of armed viewer units idle on average at raid; raid newbies who join as capturers or haulers never get an impact within 15 min |
| Site | 2 | Prime: 0/6 seeds ended; raid: 1/6, a steamroll; no comeback arc at shipped values |
| VOD | 2 | About 3 flips per seed-day; captures are foregone conclusions; dogfight wins weren't credited at this sha (NX-431 has since merged) |
| Low population | overnight 1, quiet-5 3 | No idle drift; whole days with no Offensive at 5 viewers |

## 5. Recommendations

**Values for NX-412 part 5b:**
- Keep `director.adaptation_up_above` at 2, as the owner directed.
- Keep `director.source_spend_frac` at 0.005: both raises collapse raid.
- Keep `director.op_priority.ESCORT_CONVOYS` at 0.8.
- Keep `tasking.expire_min` at 15.
- Deferred: `combat.strike_structure_first` waits for S1; `director.score.victory_hold_mult` waits for sweep N; upkeep values wait for the K series.

**Harness follow-ups (new tracker rows, all S unless noted):**
1. **Longest dry stretch per seed,** lead-in and tail included, in the report.
2. **Why no capture operation launched, per window:** budget below the cheapest capture, no target, `max_ops` full, staged, or the floor not due. S–M. This would have made M1 and M2 decisive, and it would explain the raid lead-in.
3. **Funnel credited to the launch's own units, plus a staging outcome:** launched from stage, timed out, or dropped.
4. **Split the "other" idle reason** (109,363 samples at raid).

**Queued runs:**
- **K0 #421** has the same sim, content, balance and contracts as M0 (`git diff 1b5fd60 86af552` touches only tools, tests and docs in those paths). It differs from M0 only in the harness report, which adds the rare-shortfall metrics R1–R11. Keep it as the K-series control for those metrics. Its final hashes should equal M0's, which is a free cross-host determinism check.
- **R7 (Static budget and Offensives ≥ 85% of K0):** judge it on budget per window and the longest dry stretch, not Offensive count alone. M2 moved prime Offensives 10% with almost no Director change, and per-seed spread is about 24% (estimate).
- **K1–K3** run before the floor fixes, so upkeep's reserve may lengthen prime droughts there (estimate). Re-run the winning K at the develop tip with quiet-5 and overnight-0 added, to test EC-11.
- **S0 #429** (NX-439 in, NX-441 not) should be read against M0 on: prime longest dry stretch, the raid lead-in, ALPHA gaps, Offensives per hour, and STAGING sitreps per hour. The last is a spam risk, since the floor can now fire every 10 windows (Q-TD-64).
- **S1 #430** (strike-first on): read strike and capture rates, steamroll share and A2 against S0.

**Next sweep "N"** (at develop tip, after S0/S1): each job 6 seeds × 24 h × 12 workers, base overrides `economy.legacy_rules=false, economy.unlimited.ENEMY=false, economy.unlimited.COALITION=false, director.adaptation_up_above=2`.

| Job | Profiles | Extra overrides | Question |
|---|---|---|---|
| N0 | prime-50, raid-300 | none | Tip control: droughts, raid lead-in, sitreps per hour by kind |
| N1 | prime-50, raid-300 | `combat.strike_structure_first=true` | The funnel at tip with the hold response; steamroll share |
| N2 | prime-50, raid-300 | N1 + `director.score.victory_hold_mult=3.0` | Do holds get contested and broken? |
| N3 | overnight-0, quiet-5 | `combat.strike_structure_first=true` | A3, idle drift, low-population payoff |
| N4 | quiet-5, overnight-0 | the K winner's upkeep keys, plus strike-first if S1 says so | EC-11, shortfall at low population |

Run N1–N3 only if S1 shows the funnel opening. Otherwise take the harness follow-ups first.

## 6. Watch items and questions

**Watch items:** captures always complete (101/101); raid first Offensive 7–14 h in; 62% of armed jets idle at raid; no overnight drift; raid's sensitivity to the source share; Static sitreps per run-hour after NX-431 (PROPOSED ceiling: 2 at prime).

**Questions for the owner (#412), each with a recommendation:**
1. **Should the raid crowd see a Static capture attempt early?** Recommend a PROPOSED harness target: the first capture operation within 60 game minutes of the Static reaching ALPHA, at 50 viewers and up.
2. **Should a capture in progress be breakable by defenders?** Recommend yes as the direction. First have the lead measure capture duration against DEFEND arrival time, then propose a rule.
3. **Is zero overnight drift acceptable, given Q-GP-28 says the Static gains slowly at 0 viewers?** Recommend no: at most 1 flip per 12 h (within A3), and let N3 test strike-first before adding a key.
