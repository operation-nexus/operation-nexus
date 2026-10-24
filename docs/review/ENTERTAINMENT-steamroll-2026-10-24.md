# Entertainment checkpoint: crowd wins vs steamroll (NX-411, Q-TD-16), 2026-10-24

Checkpoint review by the `entertainment-reviewer` agent (docs/quality/ENTERTAINMENT-REVIEW.md). Owner direction (Q-TEST-6, 2026-10-24): a coordinated crowd may win in 4 h or less; a win must not be a steamroll. Verdict: today's crowd wins are steamrolls on five of the six measured signals (the exchange ratio does not separate).

## 1. What was reviewed
- Harness reports, quoted: #301 (develop 99b843d, all profiles, 3 seeds, 24 h); #316 baseline, #317 (`director.max_live_units.bravo=140`, `budget.bravo=160`, `max_spawns_per_window=12`), #318 (`campaign.victory_hold_min=120`), prime-50 and raid-300 at 7be26f4.
- Probes, measured: `tools/balance/runner.run` with an `on_tick` hook at develop 8bab4d7, strait-1, sampled each game minute: prime-50 seeds 1-3 to their end, raid-300 seed 1 for 6 h (it did not end; it won at 4.70 h at 7be26f4, cause unknown, one seed).
- Caveats: four probe runs, one at raid-300; indicative only. No overlay, site or clips yet; every audience is reconstructed from events. No capture-progress or victory-hold events exist.

## 2. Evidence
| Signal | Measured (probes) | Reports (quoted) |
|---|---|---|
| Coalition strategic node ever lost | 0 in 4 of 4 runs | — |
| Static capture starts on coalition-held nodes | 0 (all on neutral crossings) | — |
| `NodeDefensesDown` on a coalition node | 0 | — |
| Victory hold broken | 0 | #318: every win exactly 90 min later than #316, 6 of 6 |
| Lead changes | 1 per won run | — |
| Momentum: largest drop from a running peak | 5-6 points (prime-50), 13 (raid-300, early) | mean 45-59% |
| Static stock | 2,994 at start, ~1,500 after hour 1, 137-326 by the end (prime-50) | — |
| Static live units | peak 42-45 in hour 1, 3-9 late; coalition 60-121 | — |
| Longest stretch with no capture | 128-411 min | — |

Reading (estimate): the war is decided in hour 1, when the Static spends half its stock on a BRAVO surge and loses it. Seeds 2 and 3 are uncontested landslides (several bases in 12-25 minutes, no Static attempt on held ground). Seed 1 is a 17 h slog against a Static with 3-8 units. Time at BRAVO is high in steamroll runs too, so it is not a signal. #316 and #301 gave identical outcomes: today's features (bridge repair, escorts, holds, raids) did not change these campaigns. No `BridgeDestroyed` in four runs.

Audience scores (estimates, 1-5): watcher 2, player 2, site watcher 2, VOD and clip 2. Top problems: the Static never threatens held ground; its economy collapses in hours 1-2 and never recovers; the coalition's own bottleneck (jobs full, strike-only impact) sets the pace, not resistance.

## 3. Proposed steamroll signals (thresholds PROPOSED, uncalibrated)
| Rank | Signal | Events | Steamroll if |
|---|---|---|---|
| 1 | Static pressure on held ground: capture starts on coalition-held nodes + coalition `NodeDefensesDown` + nodes lost | exist | fewer than 2 per 4 campaign hours, at least 1 in any win |
| 2 | Contested final hold: Static pressure during the last hold run; holds broken | derivable; a `VictoryHoldStarted`/`Broken` event would help the overlay too | 0 and 0 |
| 3 | Momentum swing: largest drop after the coalition first leads; lead changes | exist | under 10 points and at most 1 change |
| 4 | Static force late: live armed units and stock in the last third vs its own peak (never vs the crowd) | live counts exist; stock as a sample | under 25% of peak units, or under 10% of start stock |
| 5 | Static offensive intent late: ENEMY STRIKE/CAPTURE jobs on coalition nodes in the last third | exist | under 1 per game hour |
| 6 | Exchange after hour 1 | exist | information only |

Proposed rule: a steamroll when signals 1 and 2 both fire, or 3 of signals 1-4 fire.

### For Q-TD-16 (economy scaling)
Doubling caps did nothing at raid-300 (live Static units never reached the cap; it is stock-bound), so caps-to-upkeep is right. But territory income alone would make steamrolls faster (each capture shrinks the Static). The design should aim for: a territory-independent floor income (rear source, HQ region, cut only by raiding convoys); interior lines (a falling-back Static gets shorter supply lines); upkeep that lets a beaten Static rebuild an Offensive every N windows; coalition upkeep from base stock under parity (turns "jobs full" idleness into supply work, giving haulers impact); and a Static that spends its opening budget in waves, not one hour-1 dump.

### Suggestions
- Tuning: raise `director.op_priority.RETAKE` and `director.retake_window_min` together; don't use `victory_hold_min` as the fix; spread the Static's opening spend.
- Design: NX-411 signals 1-4 in the harness (S-M); NX-412 with a floor and interior lines (L); a Static operation that may target a node during the coalition's victory hold, with a sitrep line, as a climax (M); fix the coalition bottleneck separately (A2 "full").

## 4. Watch items and questions
Watch: uncontested victory hold; Static economy death spiral (stock under 10% or units under 25% of peak for 2 h while it holds its HQ); BRAVO with under 10 live units; STRIKE_BRIDGE never firing. Questions: Q-TEST-11, Q-TD-17, Q-TD-18, Q-TD-19 in OPEN-QUESTIONS.
