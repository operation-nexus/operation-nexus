# Entertainment checkpoint: economy baseline (#337) and NX-412 plan, 2026-10-24

Short checkpoint by the `entertainment-reviewer` agent (docs/quality/ENTERTAINMENT-REVIEW.md). Sources: harness #337 (develop 136170c, no economy code active; prime-50 and raid-300, seeds 1-3, 24 h), docs/specs/ECONOMY.md, Q-TD-16..30, the two earlier reviews. Nothing new was run; no overlay exists, so every audience is reconstructed from events. Estimates are marked.

## 1. Baseline
- **Arc (watcher, VOD):** 6 of 6 runs flagged steamroll (3-4 signals), same as #301. S1 is 0.00 in 5 of 6; S2 is 0,0 everywhere; S4 fired in all 6. raid-300 wins at 4.7-5.3 h, near the owner's 4 h target, but uncontested; prime-50 seed 1 is a 17 h slog.
- **Player:** A2 by kind (prime-50): auto 240 s, striker 326 s, capturer 1,601 s, hauler 3,327 s, scout mostly never. 43-44% of all newbies wait over 15 minutes.
- **Idle:** "full" beats "refuel" (raid-300 12,489 vs 6,734; prime-50 1,251 vs 818); raid-300 averages 72% idle armed units, so the crowd's own job supply sets the pace. Refuel is about a third of idle samples.
- **Monoculture:** STRIKE_FIGHTER 98-99% of kills.
- **Scores (estimates):** watcher 2, player 2, site 2, VOD 2; unchanged.

## 2. The plan
Sound. EC-7 (source share, cadence floor), EC-9 and EC-12 are the only levers on S1 and S2. EC-13 is fair and improves readability (threats visibly travel from the source). EC-15 plus labelled reports keep balance results clean. Q-TD-29 protects goldens; the risk is that unlimited mode quietly stays on, so part 5 must turn it off.

Most likely still a steamroll after NX-412 (estimate): raid-300 via S1 and S2. The economy funds the Static but nothing makes its units win against massed strike fighters; EC-12 only re-ranks targets. Under EC-13, source-funded units spawn at the rear: if rear-to-hold-node travel exceeds `campaign.victory_hold_min`, EC-9's sitrep fires and no threat arrives. S4 can also pass for the wrong reason (wave spending lowers the peak).

## 3. Factories as capturable income
Worth it, later. Upside: stakes for capturers and clips ("factory falls, grounding wave"). Cheapest path: a FACTORY node kind with an `economy.income.per_node` key; income still lands at the source (EC-1), and EC-12 targets factories automatically. Risk: capture income compounds, which accelerates steamrolls, and it reopens Q-GP-41. When: after the part 5 sweep shows a no-steamroll run; ship as theater content with a per-node income cap and a Static retake priority.

## 4. Recommendations (ranked)
1. **Gate the sweep on S1 and S2.** Add a harness check that the Static's travel time from its rear to each victory node is under `victory_hold_min`; sweep `director.score.victory_hold_mult`, `director.score.income_node_mult`, `director.source_spend_frac`, `director.cadence_windows`; report S4 against start stock too.
2. **Before upkeep goes live, report grounding by idle reason.** With 72% idle, upkeep could ground units that never had a job. Report the grounded share among "full"-idle units versus units with a job. The real fix is more capturer and hauler jobs (A2 27 and 55 minutes).
3. **Break the strike-fighter monoculture by tuning.** Set `economy.upkeep.STRIKE_FIGHTER` above other kinds in the sweep; target a top-kind kill share under 80% (PROPOSED).

Watch items: unlimited mode still on at part 5; hold sitrep with no Static arrival; idle units grounded.
