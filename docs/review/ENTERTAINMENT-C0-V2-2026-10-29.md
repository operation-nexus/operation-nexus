# Entertainment review: C0 #532, V1 #533, V2 #534 (sha 70d7d5c), 2026-10-29

The `entertainment-reviewer` (Opus) wrote this review and the lead wrote it up.

**Runs.** All 24 h, 6 seeds, all four profiles.
- At 70d7d5c (X0's code plus #529 NX-486 and #530 NX-492):
  - C0: the NX-473 W1 keys (control).
  - V1: C0 with LC-2 off (`director.pol.convoy_demand_s` 3600).
  - V2: C0 with LC-2 at 900 s.
- Compared with X0 #525 and X2 #527 at 60d6cd4.
- C0 and X0 have the same config hash.

**Sources.**
- A Sonnet agent copied the queue numbers verbatim. The reviewer checked every number used here against the report comments 6500018362 (C0), 6501177229 (V1), 6502189742 (V2), 6494525512 (X0) and 6495787151 (X2).
- One causal probe on `git archive` trees (raid-300 s1, C0's keys):
  - 71127f0 (60d6cd4 plus #529 only) and 70d7d5c both reach VICTORY at tick 72994, with the identical state hash `40b1dcdbdc47f552…`.
  - This is exactly C0's queue run.
- Every audience score is an estimate, because the overlay, site and clips don't exist yet.
- Develop has since gained NX-489 (hold decay, #536) and NX-490 (HQ capture). No run here includes them.

## Verdicts
**Q1. C0 confirms X2's LC-1 behaviour: ship `logistics.ai_trucks.max_live` 3 and `tasking.resupply_slots_max_starving` 6.**
- overnight-0 is the same as X2 in everything the report prints: momentum 51.3 (X2 51.4, X0 41.0), coalition income 58.3/h (X2 58.3, X0 0.0). V1 and V2 are the same.
- Nothing gets worse at the busier profiles, and several numbers are better than X0 at the same keys:
  - prime A2 tail 33.6% (X0 39.2%);
  - prime auto tail 19.3% (21.9%);
  - prime starved 191.0 (215.0);
  - quiet-5 starved 206.8 (470.3).
- Which of #529 and #530 moves these is [UNVERIFIED].
- **New:** a prime R10 pool stretch: 1 stretch of 33 min in C0, and 1 of 44 min in V2. Cause [UNVERIFIED].
- **Still not measured:** the night after a busy day.

**Q2. Ship `director.pol.convoy_demand_s` 900 (V2).**

| Metric | C0 (300) | V2 (900) | V1 (off) |
|---|---|---|---|
| prime A2 tail | 33.6% | 33.6% | 33.5% |
| prime auto tail | 19.3% | 17.3% | 16.6% |
| prime starved | 191.0 | 197.7 | 319.0 |
| prime BRAVO dwell (h) | 1.49 | 1.85 | 2.47 |
| prime strike packages downed | 100 | 135 | 138 |
| raid median h (per-seed range) | 2.2 (1.79–5.02) | 2.5 (2.08–2.91) | 4.0 (1.79–7.45) |
| raid holds (broken) | 11 (5) | 14 (8) | 24 (18) |
| raid starved | 300.3 | 313.3 | 463.8 |

- The X0-Y1 prime A2 regression does not reproduce at 70d7d5c: the overall tail is flat across all three settings.
- 900 keeps nearly all of LC-2's prime starvation gain and keeps the auto tail below the 20% watch line. It restores most of the visible escalation and gives the tightest raid length.
- LC-2 off gives the most raid comebacks, at +67% prime starvation.
- Quiet-5 starvation and A2 (n ≤ 12) behave as seed noise. C0 and X0 at identical keys differ by 207 against 470, so quiet-5 does not decide this.

**Q3. The raid-300 drop from X2 to C0 is mostly a seed-mix artifact.**
- Offensives by seed (X2 → C0):
  - s1: 67 → 3;
  - seeds 2–6 together: 22 → 24.
- The pooled raid numbers were dominated by X2's 24 h, not-ended s1: budget per window, idle armed, slots per unit and A2 counted newbies.
- s1 went from 24 h not ended to VICTORY at 2.03 h. The probe ties this to **NX-486 (#529)**, not the LC-1 fix. The mechanism inside NX-486 is [UNVERIFIED].
- **Is a 2.2 h median raid victory too quick?** It is within the owner's Q-TD-91 ruling ("at least some resistance"). C0 shows:
  - 7 Offensive captures and 1 RETAKE capture;
  - 5 of 11 holds broken;
  - 0 of 6 seeds flagged as a steamroll.
- It is still close to the edge:
  - S2 (an uncontested last hold) fired on s2 and s3;
  - s3 and s4 won in under 1.9 h.
- Re-judge at current develop (NX-489, NX-490).

## Risks, ranked
1. Develop has moved past every run: NX-489 and NX-490 change victory and HQ capture.
2. Raid pooled metrics are seed-mix artifacts (H3, X0-Y1 review).
3. Quiet-5 is too noisy to judge starvation or A2.
4. Nothing measures the night after a busy day.
5. Prime R10 pool stretches appear in C0 (33 min) and V2 (44 min).
6. The raid A2 tail stays at 45–48% in all variants (target 10%).
7. Quiet-5 stretches without an Offensive exceed 600 min: C0 s6 at 660 min, V1 s3 at 643 min.

## Audience scores (estimates, 1–5; C0 / V1 / V2)
| Audience | overnight-0 | quiet-5 | prime-50 | raid-300 |
|---|---|---|---|---|
| Watcher | 2.5 / 2.5 / 2.5 | 3 / 3 / 3 | 3 / 3.5 / 3.5 | 3 / 3.5 / 3 |
| Player | – | 3 / 3 / 2.5 | 3 / 3 / 3 | 2.5 / 3 / 2.5 |
| Site watcher | 2.5 / 2.5 / 2.5 | 3 / 3 / 3 | 3.5 / 3.5 / 3.5 | 2.5 / 3 / 2.5 |
| VOD and clip | 1.5 / 1.5 / 1.5 | 2 / 2 / 2 | 3 / 3.5 / 3.5 | 3.5 / 3.5 / 3.5 |

## Decisions and follow-ups (lead)
- **Ship as tuning (Q-DEV-21, lead decision, owner may veto; Q-TD-128):**
  - `logistics.ai_trucks.max_live` 3;
  - `tasking.resupply_slots_max_starving` 6;
  - `director.pol.convoy_demand_s` 900.
  - Don't ship `ai_trucks.period_s` 420.
- **Next runs:** C0′ (control) and V2′ (the shipped keys) at current develop, prime-50 and raid-300, same sha (L-37).
- **Harness changes:**
  - per-seed idle armed, A2 and starvation in `report.py` (fixes H3);
  - a day-into-night profile;
  - a burst raid profile (Q-TD-91 (a), NX-321).
- **Look into:** the quiet-5 C0 s6 660-min stretch without an Offensive, starting at ALPHA.
- **Watchlist:**
  - a prime R10 pool stretch over 30 min while LC-1 is on;
  - raid S2 (uncontested last hold) on 2 or more of 6 seeds;
  - a raid victory under 2 h with no broken hold;
  - prime auto A2 tail above 20% while `convoy_demand_s` < 3600;
  - a quiet-5 stretch without an Offensive above 600 min.

Probe scripts and outputs are in the lead session's scratchpad; they are not committed.
