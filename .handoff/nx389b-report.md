# NX-389 follow-up: hauler A2 diagnosis (partial, 2026-10-23)

No code was written. The runs are at develop 1878a2a: raid-300, seeds 4, 5 and 7, 6 game hours.
Data is in `nx389b-runs/` (d-base is the default `tasking.resupply_slots_max` 3; d-s6 is `--set tasking.resupply_slots_max=6`).
The wrapper is `diag_wrap.py`; the summary scripts are `summ.py` and `diag.py`.

"Newbies judged / below tier" means newbies who arrived at ALPHA or above (judged by A2) versus those who arrived at Pattern of Life. The dwell column is seconds the Static spent at Pattern of Life (PoL), ALPHA and BRAVO.

| seed | config | newbies judged / below tier | auto with impact | striker | hauler | Static dwell s, PoL/ALPHA/BRAVO | STRIKE jobs | SCOUT jobs | ESCORT jobs | starvation node-min |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | default | 51/106 | 25/37 | 4/5 | 0/4 | 1980/9180/10440 | 24 | 12 | 18 | 335 |
| 4 | slots 6 | 30/127 | 6/22 | 2/4 | 2/2 | 8760/7680/5160 | 13 | 0 | 0 | 93 |
| 5 | default | 65/115 | 43/47 | 8/8 | 0/10 | 600/4860/16140 | 40 | 11 | 18 | 363 |
| 5 | slots 6 | 36/144 | 8/26 | 2/5 | 1/5 | 9540/8880/3180 | 7 | 1 | 18 | 70 |
| 7 | default | 62/110 | 26/41 | 7/7 | 0/7 | 1680/8700/11220 | 20 | 25 | 23 | 352 |
| 7 | slots 6 | 47/125 | 0/32 | 5/6 | 2/5 | 8460/8160/4980 | 6 | 0 | 0 | 72 |

Triples below are seeds 4/5/7.

**Coalition stock flow**

| | default | slots 6 |
|---|---|---|
| Loaded at the rear | 15900/14900/14900 | 16400/15700/16000 |
| Loaded between bases (lateral) | 11855/12813/12579 | 6816/3919/3406 |
| Stock at 6 h | 2440/1243/1730 | 3225/3272/3048 |
| Trucks spawned | 67/76/63 | 67/76/63 |

**Static**

| | default | slots 6 |
|---|---|---|
| Stock loaded at its rear | 1800/2300/1600 | 900/600/900 |
| Stock consumed | 3990/4593/3720 | 3197/2897/3000 |

**Player strike fighters:**
- Idle 0.70/0.69/0.72 of the time with the default, 0.71/0.70/0.73 with 6 slots.
- Player hits, almost all from STRIKE jobs: 1397/1591/1235 with the default, 1249/1086/1196 with 6 slots.

**Ruled out:**
- Escort jobs: seeds 4 and 7 have none with 6 slots and still lose the auto impact.
- Auto units taking resupply claims: every truck sampled was player-owned.

**Diagnosis so far:** the auto-player loss comes with the Static staying at Pattern of Life much longer (PoL dwell 600–1980 s with the default, 8460–9540 s with 6 slots).
- At PoL the board posts no idle-viewer strike targets (`tasking.strike_idle_targets_min_tier` is ALPHA, Q-SIM-86).
- So STRIKE jobs fall from 20–40 to 6–13 per run, and fewer newbies arrive at ALPHA or above to be judged.
- The Static also gets quieter: SCOUT jobs collapse, it loads and spends about half as much stock, and coalition starvation drops to 70–93 node-minutes.

**Not established:** why the tier falls. Player hits drop only 3–32%. The likely cause is what gets hit (kills or facility hits), or a self-reinforcing loop: PoL → no idle strike jobs → fewer provoking hits → stays at PoL.
- The provocation samples (`metrics.diag.prov`) are saved but not analysed.
- The TB-5 tie-break divergence has not been checked.

**Not run:**
- fix (a), a new `tasking.stock_slots_max` key;
- fix (b), stocking jobs only for an explicit `!join logi`;
- evening-150;
- the acceptance before/after runs;
- unit-cap pressure.

**Recommendation (coder):**
- Keep the default of 3.
- Next run: one instrumented pair (raid-300, seeds 4 and 7, 6 h) logging provocation by action kind and the tick of the first drop to PoL.
- If the drop comes from bases no longer starving (a calmer Static), it's a Director / A2-judging interaction: an owner design choice (the Q-SIM-86 tier gate, or which newbies A2 judges), not a slot-cap change.
- If it comes from strike capacity or job ranking, try fix (a) with `stock_slots_max` 4–6.
- Idea: make the diagnosis wrapper a `--diag` option in `tools/balance`.
