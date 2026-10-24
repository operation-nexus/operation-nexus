# Entertainment review: the Director's STRIKE_BRIDGE operation (NX-401), 2026-10-24

Proposal-mode review by the `entertainment-reviewer` agent (docs/quality/ENTERTAINMENT-REVIEW.md), before any code. Suggestions only; decisions are in OPEN-QUESTIONS. Already decided for NX-401: ALPHA or above, aircraft only (ENEMY_STRIKE_FIGHTER), never timed or targeted by bridge occupancy (Q-SIM-112).

## What was run
Probes on the balance harness (`tools/balance/runner.run` with an `on_tick` hook), strait-1, develop at 0591f11:
- **P1 route probe:** prime-50 and quiet-5, seeds 1-3, 6 game hours, sampled each game minute. A raid-300 run timed out; no raid-300 data.
- **P2 forced drop:** prime-50, seeds 1-3, bridge-n set to 0 hp by hand at the first minute the coalition held cross-n with the Static at ALPHA+, followed up to 120 game minutes. Seed 1 never met the condition; seed 2 dropped at minute 306 (54-minute window), seed 3 at minute 235.
- **P2b baseline:** same seeds and minutes, no drop.

Caveats: a scripted drop, not real jets; three seeds of 6 h; indicative only.

## Measured
| | prime-50 s1 / s2 / s3 | quiet-5 s1 / s2 / s3 |
|---|---|---|
| Game minutes at ALPHA+ (of 360) | 351 / 336 / 339 | 229 / 121 / 212 |
| Minutes the coalition holds an east-bank node | 257 / 75 / 126 | 0 / 0 / 0 |
| Minutes a coalition truck route crosses a bridge | 282 / 103 / 133 | 0 / 0 / 0 |

Forced drop (seeds 2, 3): 0 collapse victims; REPAIR_BRIDGE posted 1 minute later; bridge back up after 21 and 26 game minutes; 4 and 7 crew-escort jobs, viewer units claimed up to 2 each, the last three in seed 3 unclaimed. Coalition trucks routed through a Static-held node rose to 11 and 14 (baseline 2 and 3); trucks no longer present at the end 0 and 11 (baseline 0 and 2), cause of removal not read.

## Computed (estimates)
- 300 hp bridge ÷ 50 per AG_LIGHT hit = 6 hits. At Pk 0.7: 1 jet (4 rounds) cannot drop it, 2 jets (8) about 55%, 3 jets (12) about 96%.
- east-airbase to bridge-n 125 km, about 84 real s of flight. No coalition air defense reaches a bridge (nearest AAA 70 km away).
- With bridge-n down, a haven to cross-n run detours south through east-airbase: +200 km, about +22 real min per truck.

## Code facts
- CF-1: bridges are neutral and public in `SideView`; `target_in_enemy_view` is always true; `score.target_value` has no BRIDGE entry; coalition stock is not in the Static's view (TD-2).
- CF-2: coalition truck routes have no avoid set (`logistics._route`), so after a cut they reroute through Static bases.
- CF-3: `bridges.target` has no side check; a coalition jet sent to its own bridge fires on it (Q-SIM-112).
- CF-4: a down bridge is never fired at (Q-SIM-115); a damaged standing bridge never regenerates and nothing repairs it.
- CF-5: STRIKE_BRIDGE shares the single ALPHA operation slot; its cost must be ≤ `director.budget.alpha` (30).
- CF-6: no sitrep template mentions bridges.

## Options and picks
**Target rule.** (a) a bridge on the coalition's route to its most-starved base: readable, but "most-starved" is outside the Static's view and "current route" from tracked trucks is occupancy by another name. (b) the cut that most lengthens coalition routes: always picks the second bridge and severs the east bank. (c) any bridge, weighted: at low population it drops bridges nobody uses and sends AI trucks on 24-minute busywork. **(d), picked:** "cut the lifeline", from topology and ownership only: an intact bridge on the shortest intact road from the coalition sanctuary to a node the coalition holds, scored by that node's `target_value × weakness`. Quiet at quiet-5 (measured), never cuts the Static's own route, can't sever the map.

**Cadence (all PROPOSED).** Cost 30 (2 jets at PROBE's rate; the most that still runs at ALPHA). Priority 0.6 (PROBE's): beats an Offensive only once the cut-off base is bleeding. A per-bridge cooldown of 1800 game s from `BridgeRepaired`, so a repaired road stays open at least as long as it was shut (outages measured 21-26 min). At most one bridge down at a time. A bridge under repair is not a target (Q-SIM-115 stands).

**Preconditions.** New: `target_is_bridge`, `target_bridge_intact`, `target_feeds_coalition_node`, `no_bridge_down`, the cooldown. `target_in_enemy_view` is harmless. Tiers ALPHA, BRAVO.

**Shape.** One job, `{ kind: STRIKE, at: target, unit_kinds: [ENEMY_STRIKE_FIGHTER], slots: 2 }`; no STAGE (jets spawn at an airbase; an FOB stage point is useless to aircraft). No templated pairing: the follow-up attack on the cut-off node already emerges through weakness.

## Audiences (reviewer estimates, 1-5)
| Option | Watcher | Player | Site | Clip |
|---|---|---|---|---|
| (a) as worded | 4 | 3 | 4 | 3 |
| (b) | 2 | 2 | 3 | 3 |
| (c) | 2 | 2 | 2 | 2 |
| (d) with limits | 4 | 4 (with the reroute fix) | 4 | 3 |

The arc: jets inbound (about 84 s, seen only if tracked), bridge HP falls, "NORTH BRIDGE DOWN", repair and crew escorts within 1-7 min, `BridgeRepaired` after 21-26 min. A 25-minute site story and a sub-60 s clip, once the overlay draws bridges and a sitrep line exists.

## Design suggestions outside NX-401
1. **Coalition supply runs avoid Static-held nodes** (as patrols do, `bridges.not_held`), so a cut holds resupply behind the repair (TB-8) instead of driving trucks through the enemy airbase.
2. **Coalition INTERCEPT on tracked enemy strikers near a bridge that feeds a coalition node** (parity with Q-SIM-96): the biggest reason to join. The Static jet flies MED; coalition AA_LIGHT reaches LOW and MED.
3. **A direct order to your own route's bridge means defend, not fire** (amends Q-SIM-112; owner call).
4. **A repair path for a damaged, still-standing bridge** (CF-4).
5. **Sitrep line** on an ENEMY `BridgeDestroyed`: "SIGNAL SOURCE: NULL cut <bridge>; <node> is cut off".

## Watch items (PLAYTEST-WATCHLIST)
Strike cadence (same bridge re-dropped soon after repair; or never at prime crowds); trucks driving through Static bases after a cut; crew escorts with nothing to fight; coalition jets helping drop their own bridge; a damaged bridge that can't be repaired falling to a second strike.
