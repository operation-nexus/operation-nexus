# Entertainment review: two owner proposals (rear-source strikes, bridge-collapse kills), 2026-10-23

Checkpoint review (ENTERTAINMENT-REVIEW.md, "the owner asks"). It covers two proposals, not a phase. It makes suggestions only, and the owner decides (AGENTS rule 2).

## 1. What was reviewed

- Code at local HEAD `62021d5`, which is `develop` 99b843d plus the NX-397 patrol fix. All probes ran on that HEAD, and the patrol fix should not affect these findings. Files read: `combat.py`, `tasking_gen.py`, `tasking.py`, `bridges.py`, `handlers.py`, `logistics.py`, `provocation.py`, `step.py` (air movement), `content/theaters/strait-1.yaml`, `content/weapons.yaml`, unit files and `balance/default.yaml`.
- Specs and rows read: GAMEPLAY §0, §1, §1b, §5, §8 and §9; THREAT-DIRECTOR §5a; COMBAT CB-10; STATE-MACHINES §4.3; PLAYTEST-WATCHLIST; and Q-SIM-64, Q-SIM-92, Q-SIM-103, Q-SIM-105..108, Q-TD-14 and Q-GP-24.
- Probes I ran (scripts are in the scratchpad `br/` folder, nothing in the repo was changed):
  - **Direct-order probe:** a fresh campaign (seed 1) and one JOIN on tick 1, then the unit's events and state followed. Cases: `STRIKE static-rear`, `LOGI static-rear`, `STRIKE bridge-n` and `LOGI bridge-n`.
  - **Bridge-occupancy probe:** the real balance harness (`tools/balance/runner.run` with an `on_tick` hook). Once per game second it counts the ground units within 500 m, 1 km and 2 km of each bridge point. Runs: overnight-0 s1 6 h, quiet-5 s1 6 h and 4 h, prime-50 s1 4 h, prime-50 s2 4 h, raid-300 s7 2 h. These are short runs on few seeds, so the frequencies below are indicative only.
- **Surfaces that don't exist yet:** the overlay does not draw bridges (`apps/overlay/src` has bridges only in generated contract types), there is no chat parser, `!target` has no handler, and nothing exists for the site or clips. Audiences who need those surfaces are reviewed from what the sim emits.

## 2. Facts first

### Proposal 1: striking the Static rear source by direct order

**P1-F1. `!join strike static-rear` is accepted today.**
- `handlers._route` (handlers.py:366-392) has no rear check. An AIR unit forward-deploys through `plan_deploy` (logistics.py:219-221) with path `[static-rear]`.
- Observed: `UnitSpawned` at west-airbase on tick 1 with order `GOTO`.
- `!join logi static-rear` is accepted too, as a cargo-free capture run that spawns at haven (`plan_run`, logistics.py:112-139). The rear is a SANCTUARY, which can never be captured (`capture.uncapturable_node_kinds`), so the truck drives about 375 km of road for no possible capture.

**P1-F2. There is no `!target` command yet.**
- `contracts/commands/` holds only join, rebase, the staff commands and the system commands.
- GAMEPLAY:55 says "`!target` has no handler yet".
- So the only orders a player can give off the board today are JOIN with a node, a follow, or `hold`, plus REBASE.

**P1-F3. Nothing at the rear can be "struck" as a structure.**
- `_pick_node` skips `rules.supply.rear["ENEMY"]` (combat.py:225-230).
- No facility sits at static-rear (strait-1.yaml:38-47). The nearest is `radar-hq` at the HQ, and the HQ has no air defense.
- The rear has defense HP (SANCTUARY 1000, balance:85), but nothing can damage it.
- Its stock is infinite (strait-1.yaml:36; `Rules.supply.rear` is "infinite source", rules.py:71).
- Static operations are paid from base surplus with the rear excluded (GAMEPLAY §0, Q-TD-12).
- So hitting the rear itself could drain nothing and win nothing (Q-SIM-64).
- What a raider can do there is shoot Static units passing through under CB-1: convoys loading at the rear and driving the single 15 km road to the HQ (strait-1.yaml:60), and aircraft spawning there (strait-1.yaml:72). Those hits already provoke and are remembered: `convoy_hit` 3 points and `convoy_attacks` memory (provocation.py:76-78, balance:233).

**P1-F4. A direct order cannot get stuck the way NX-396 did, but it doesn't linger either.**
- A GOTO order ends at the first board pass after the path empties (tasking.py:339-340). An idle aircraft orbits until bingo (step.py air movement). After that the board takes the unit.
- Observed with `STRIKE bridge-n`: the jet arrived around tick 835 (125 km at 250 m/s), and on tick 850, about 1.5 game s later, it claimed a board job elsewhere.
- So a player who orders their jet to a spot is overridden almost on arrival. The order means "fly there", not "hunt there". This is the opposite of what the owner asked for ("operator decisions... are encouraged").

**P1-F5. A solo rear raid today is a suicide line.**
- AIR paths are a straight line from the deploy base (`[target]`). TB-2's ring check skips direct orders (GAMEPLAY:81), so a west-airbase → static-rear flight on y = 120 km passes straight over `ad-east` (SAM, 35 km range) at east-airbase.
- Observed (seed 1): the SAM engaged at tick 1234 and the jet was mission-killed at tick 1293, around x ≈ 260-280 km, then turned for home. It never reached the rear.
- In a second probe I removed the Static SAM and fighters. Fighters launched by the Director destroyed the jet at tick 1365.
- The GOTO order stayed set through the turn home and cleared only after landing.

**P1-F6. Nothing tells the player.**
- No rejection reason exists for "the rear can't be struck", and an arrival that achieves nothing has no feedback line. This cuts against GAMEPLAY §1a FB-UX-1 ("did my command work?").

### Proposal 2: units on a bridge die when it falls

**P2-F1. Today nothing in live play can drop a bridge.**
- Only a unit holding a STRIKE *job claim* on the bridge fires at it (bridges.py:46-55, Q-SIM-105).
- The coalition board never posts a bridge STRIKE job: `_strike` needs a node the foe owns with defense HP (tasking_gen.py:351-390), and bridges are NEUTRAL with none.
- The Static's STRIKE_BRIDGE operation isn't built (operations.yaml:6).
- Observed: `!join strike bridge-n` is accepted, the jet arrives, it fires **no** shot at the bridge, and the board takes it 1.5 s later (P1-F4).
- So the "strategically timed strike" has no trigger yet, for either side.

**P2-F2. Today a falling bridge harms nobody on it.**
- A ground unit at or past the cut point carries on unharmed. A unit short of it turns back. Aircraft are untouched (bridges.py:105-127, Q-SIM-108).
- The cut point is the bridge node's position projected onto its edge (bridges.py:89-99).

**P2-F3. Kill maths (stats are PROPOSED values).**
- `logistics.bridge_hp` is 300.
- AG_LIGHT does 50 damage, carries 4 rounds and has base Pk 0.7, so one strike jet deals at most 200. Dropping a bridge needs at least 2 jets, about 2.2 jets' worth of rounds on average [estimate from base Pk].
- ENEMY_ARMOR (AG_CANNON: 40 damage, 40 rounds) could drop one alone in 8 hits.
- A jet's 4 rounds take 30 world s, which is 5 real s at `time_scale` 6.
- So the fall itself comes fast. Most of the visible build-up is the jets flying in: west-airbase to bridge-n is about 125 km, about 500 world s, about 83 real s [computed].

**P2-F4. Geometry.**
- The bridge edges are fob-n-w → cross-n and fob-s-w → cross-s. Each is 100 km long, with the bridge point at x = 200 km, 70 km from the west end. The strait is drawn as scenery from x ≈ 190 to 210 km (strait-1.yaml:25).
- A truck moves 25 m/s world. 1 km of road therefore takes 40 world s, about 6.7 real s.
- A coalition truck from haven reaches bridge-n after about 212 km, about 8,500 world s, **about 24 real minutes** [computed from node positions; assumes straight edges, speed_mult 1.0 and no stops].

**P2-F5. How often ground units are near a bridge** (share of game seconds with at least one ground unit within the radius):

| Run | bridge-n ≤500 m | ≤1 km | ≤2 km | ≥2 units ≤1 km | bridge-s ≤1 km | Distinct units within 1 km |
|---|---|---|---|---|---|---|
| overnight-0 s1, 6 h | 0 | 0 | 0 | 0 | 0 | none |
| quiet-5 s1, 6 h | 0 | 0 | 0 | 0 | 0 | none |
| prime-50 s1, 4 h | 0.37% | 0.74% | 1.48% | 0.47% (max 3) | 0.09% | 10 + 1 coalition viewer trucks |
| prime-50 s2, 4 h | 0 | 0 | 0 | 0 | 0 | none |
| raid-300 s7, 2 h | 0.74% | 1.49% | 2.92% | 0.75% (max 4) | 0.18% | 15 + 1 coalition viewer trucks |

- **Every unit seen near a bridge was a coalition `LOGI_TRUCK` owned by a COMMANDER** (a viewer's truck).
- Static armor and convoys did enter the x 150-250 km band, but they stayed on the east bank around the crossings and never came within 2 km of a bridge. In these runs the Static never crossed west.
- On strait-1 as tuned today, then, the people a collapse rule would kill are viewers' trucks, not Static convoys. Whether a Static Offensive column ever crosses west wasn't measured and would need longer runs.

**P2-F6. Readability infrastructure.**
- The overlay doesn't draw bridges yet.
- The clip excitement score (CLIPS-REPLAY §2) counts missiles, kills, captures, human involvement and objectives. It has no bridge term.
- `respawn_delay_s` is 20 game s (balance:11), so most of a victim's loss is the trip, not the timer.

## 3. Scores

Scores are reviewer estimates from the facts above, not measurements. "Today" is the code as it stands. "Shaped" means with the recommended shape from §4.

### Proposal 1: rear raids by direct order, and "off-board orders never break and are encouraged"

| Audience | Today | Shaped | Evidence and biggest problems |
|---|---|---|---|
| Watcher | 2 | 3 | A jet heading for the Static rear and dying at the SAM belt reads as a moment. A jet that arrives and then turns away for an unrelated job (P1-F4) reads as a bug. The rear itself is off-map visually (x 395 of 400 km). |
| Player | 1 | 4 | The order is accepted, then the board overrides it within seconds of arrival (P1-F4). There is no route choice, so it dies on the straight SAM line (P1-F5). No feedback says why (P1-F6). Shaped: the raider hunts convoys on the rear-HQ road, which already provokes and already starves the Static. That is real agency and a clear "I did that". |
| Site watcher | 2 | 3 | Deep raids could become a story beat ("convoys hit at the source"), but only if `UnitDestroyed` of convoys near the rear is attributed and summarised. |
| VOD and clip | 2 | 4 | "Lone jet slips past the HQ and catches a convoy leaving the rear" is a clean setup and payoff (about 90 s of flight, then a few seconds of fire). Today the payoff never happens. |

### Proposal 2: collapse kills on a falling bridge

| Audience | As proposed, no telegraph | Shaped (radius, telegraph, events, symmetric) | Evidence and biggest problems |
|---|---|---|---|
| Watcher | 3 | 4 | A span dropping with trucks on it is the most legible kind of event, but only once the overlay draws bridges, their HP and the loss burst (P2-F6). |
| Player (striker) | 1 today (can't fire, P2-F1), 5 once possible | 5 | A big, earned payoff that needs 2 jets coordinating (P2-F3): good teamwork bait. |
| Player (victim) | 2 | 3 | About 24 real minutes of driving lost in one moment (P2-F4), and on strait-1 the victims are viewers' trucks (P2-F5). It is fair only if both sides can see it coming and only if the Director doesn't time collapses against occupancy. |
| Site watcher | 3 | 4 | "North Bridge dropped, 3 trucks lost, front starved" is a strong asynchronous headline. |
| VOD and clip | 4 | 5 | Setup (jets inbound and a column approaching, about 80 real s) and payoff (about 5 s) fit under a minute. The catch is frequency: about 0.7-1.5% of seconds at prime and raid crowd sizes on bridge-n and about 0 at 0 or 5 viewers (P2-F5). Untimed falls almost never catch anyone, so these moments come only from deliberate timing. |

## 4. Suggestions (ranked)

Each one lists the audience, the effect, a rough cost, what it touches, and whether it is tuning or a design change.

1. **A direct order to a node is a standing order that holds until it means something.**
   - Shape: an armed unit ordered to a node holds station there and engages under CB-1 until bingo, ammo out, a new order, or `tasking.order_dwell_s`, a PROPOSED new key. Only then does the board take it.
   - Audience: Player, Watcher.
   - Effect: fixes P1-F4 for every node, not only the rear. It is the core of "off-board orders are encouraged".
   - Cost: S-M.
   - Touches: GAMEPLAY §1b "Free movement", the `tasking.py` order-completion rule, STATE-MACHINES §4.1.
   - Design change.

2. **A direct strike order on a bridge fires at the bridge.**
   - Shape: `bridges.target` also accepts a unit whose GOTO or standing order node is that bridge, not only a STRIKE job claimant.
   - Audience: Player (striker), Clip.
   - Effect: Proposal 2 can't happen without it (P2-F1), and it is exactly the owner's "operators can choose".
   - Cost: S.
   - Touches: amends Q-SIM-105, COMBAT CB-10, `bridges.py`.
   - Design change.

3. **A rear order is accepted as a "deep raid", with honest feedback.**
   - Shape: keep accepting `!join strike static-rear`. The rear node takes no damage (keep Q-SIM-64 and combat's exclusion). With item 1, the raider hunts convoys and aircraft at the rear and on the rear-HQ road. Those hits already provoke and starve the Static (P1-F3).
   - Feedback: on arrival the digest says, for example, "VIPER-27 on station over STATIC REAR: hunting convoys" (FB-UX-1).
   - For `!join logi static-rear`, reject with `NODE_INVALID_FOR_UNIT`: an uncapturable node can't be a capture run's goal (P1-F1).
   - Audience: Player, Clip.
   - Cost: S.
   - Touches: GAMEPLAY §1b and §1a, handlers `_route` for the logi case, COMMAND-CATALOG reasons.
   - Design change (small).

4. **A collapse destroys the ground units on the span.**
   - Shape: the hit that drops a bridge destroys every GROUND unit, either side, on the cut edge within `logistics.bridge_collapse_radius_m` (PROPOSED 1,000 m) of the cut point, measured along the edge. That is ±6.7 real s of truck travel, so it rewards precise timing.
   - Destroyed, not Disabled: no wreck on a span that no longer exists. Cargo is lost. The usual crew roll applies (CB-8, so a downed crew is a CSAR hook later). The killer is the shooter. Aircraft are unaffected.
   - Runs inside `bridges.damage` before `reroute`, in entity-id order (deterministic).
   - Audience: all four.
   - Cost: S in the sim, plus a contract change if a cause is added (item 5).
   - Touches: amends Q-SIM-108, GAMEPLAY §5, STATE-MACHINES §4.3, CONFIG-AND-CONTENT §6.3.
   - Design change. The radius value itself is tuning.

5. **Make the collapse a single readable event.**
   - Shape: each victim gets a `UnitDestroyed` with the shooter as killer. `BridgeDestroyed` gains `lost_ids`, or a `cause: BRIDGE_COLLAPSE` field is added (contracts, `make contracts`). Add a `bridge_destroyed` term to the clip excitement score.
   - Audience: Watcher, Clip, Site.
   - Cost: S (contract) plus M on the overlay (bridge rendering and an HP bar in P2).
   - Touches: CONTRACTS, CLIPS-REPLAY §2, OVERLAY.
   - Design change.

6. **A telegraph so the collapse reads as earned.**
   - Shape: from the first hit, the overlay shows the bridge's HP falling and an "UNDER ATTACK" state. `NodeView hp_pct` already exists for bridges (Q-SIM-106). No new sim mechanic is needed. The near-bank turn-back in Q-SIM-108 already lets units short of the cut point escape.
   - Audience: Watcher, Player (victim).
   - Cost: M (overlay, P2).
   - Touches: OVERLAY.
   - Design change (presentation only).

7. **Keep the Director honest on STRIKE_BRIDGE.**
   - Shape: when it is built, the operation must not choose its timing or target by bridge occupancy (no "wait for trucks"), and it stays ALPHA or above like the other offensive operations. The collapse rule applies to it symmetrically (GAMEPLAY §0).
   - Audience: Player (victim), low population (TS-3).
   - Cost: S.
   - Touches: THREAT-DIRECTOR §5a, operations.yaml, NX-373 part 3.
   - Design change.

8. **Provocation: no new weights.**
   - Static units killed by a commander-caused collapse count as `unit_destroyed` (5 each) through the existing path, and carriers feed `convoy_attacks`.
   - Rear raids provoke through the existing `convoy_hit` weight.
   - Revisit only if the harness shows collapses escalating the war too cheaply.
   - Tuning.

9. **Add a "freelancer" harness persona.**
   - Shape: it sends JOINs with random node targets, including static-rear, bridges and its own sanctuary.
   - Assert no crash, no unit holding a GOTO with no path for more than one pass, and no claim stuck. Report the share of direct orders that ended with no effect. Also add a "ground units within R of a bridge" sampler like the scratchpad probe.
   - Audience: all (guards the owner's "never break things").
   - Cost: S.
   - Touches: tools/balance and profiles.yaml.
   - Harness inputs, not game balance.

10. **Later: a route choice for deep raids.**
    - Shape: a `via` waypoint on `!target`, so a raider can skirt the east-airbase SAM ring (P1-F5).
    - Audience: Player, Clip.
    - Cost: M.
    - Touches: COMMAND-CATALOG and CONTRACTS `TARGET`.
    - Design change. Park until `!target` exists.

## 5. Watch items for PLAYTEST-WATCHLIST

| Watch | Decision | Revisit if | Source |
|---|---|---|---|
| Bridge-collapse losses by side | Collapse destroys ground units within `bridge_collapse_radius_m` (if taken) | Losses are mostly viewer trucks on strait-1 (as the probe suggests), or players complain of being griefed by the Director's bridge strikes | Q-SIM-108 amendment |
| Direct orders with no effect | Direct orders hold station (if taken) | More than a small share of direct orders end with no shot, delivery or capture, or viewers stop giving direct orders | Suggestion 1, harness freelancer |
| Deep-raid survival | Rear orders are accepted as raids | Rear raids are always shot down before arrival (today: mission-killed at x ≈ 260-280 km), or always unopposed | P1-F5 |
| Trip lost to a collapse | No refund | Viewers who lose a 24-minute haul quit, as seen in churn after a `cause: BRIDGE_COLLAPSE` loss | P2-F4 |

## 6. Questions for the owner (each with a recommended option)

1. **What should a direct order to a node do after arrival?**
   - (a) As today: the board takes the unit at the next pass.
   - (b) **Recommended:** the unit holds and engages there until bingo, ammo out, a new order, or `tasking.order_dwell_s` (PROPOSED).
   - (c) It holds forever, like `hold`.
   - Reason: (b) is the only option where "operator decisions are encouraged" is true, and its exit conditions keep it from re-creating NX-396.

2. **What does `!join strike static-rear` mean?**
   - (a) Reject it with a reason.
   - (b) **Recommended:** accept it as a deep raid. The rear node stays untouchable (Q-SIM-64), and the raider engages Static units there, with digest feedback.
   - (c) Give rear hits a bounded effect, such as slowing convoy dispatch for N minutes.
   - Reason: (b) already has real stakes, because convoys there feed the Static. (c) adds a new mechanic that GAMEPLAY §0 would also need to mirror for the coalition sanctuary.

3. **`!join logi static-rear` (a capture run to a node that can never be captured).**
   - **Recommended:** reject it with `NODE_INVALID_FOR_UNIT`.
   - The alternative is to accept it and drive about 375 km for nothing.

4. **Can a direct strike order drop a bridge?**
   - **Recommended:** yes. Amend Q-SIM-105 so the ordered node counts like a claimed job (suggestion 2).
   - The alternative is a board bridge-strike job raised by a player marker, which is a bigger change.

5. **Collapse victims: Destroyed or Disabled?**
   - **Recommended:** Destroyed. Cargo is lost, the usual crew roll applies, and the shooter gets the kill.
   - Disabled would leave a wreck on a span that no longer exists.

6. **What counts as "on the bridge"?**
   - **Recommended:** ground units on the cut edge within `logistics.bridge_collapse_radius_m`, PROPOSED 1,000 m along the edge either side of the cut point.
   - The alternative is the whole drawn strait span (±10 km), a window of about 133 real s per truck, which would make collapses frequent rather than earned.

7. **Telegraph.**
   - **Recommended:** presentation only: bridge HP and an "under attack" state on the overlay. No sim warning.
   - The alternative is a sim-side hold order for units approaching a bridge under fire.

8. **The Director and collapse kills.**
   - **Recommended:** the rule applies to both sides (GAMEPLAY §0). STRIKE_BRIDGE may not time or choose targets by occupancy and stays ALPHA or above.
   - The alternative is that collapse kills apply only to coalition-caused falls, an asymmetry that would need its own justification under §0.

9. **Provocation for collapse kills.**
   - **Recommended:** no new weight. The existing `unit_destroyed` (5) and `convoy_attacks` memory cover it.
   - The alternative is a dedicated `bridge_collapse` weight.

All numbers above are PROPOSED or computed estimates unless marked "observed". The harness counts come from 6 short runs on few seeds, not from the acceptance length.
