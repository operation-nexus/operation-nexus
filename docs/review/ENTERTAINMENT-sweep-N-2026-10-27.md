# Entertainment review: harness sweep N (N0 #451, N2 #452, N1p #456, N3 #457), 2026-10-27

**Bottom line.** A probe run for this review shows that the S review's explanation for the raid "ring" lockout (`ENTERTAINMENT-strike-first-S0-S1-2026-10-27.md`) was wrong. Jets are not locked out by a captured coalition SAM. They are locked out by the Static's own east-airbase SAM, which nobody is ever tasked to hit:

- With strike-first on, the raid crowd brings the defense HP of east-airbase, fob-n-e and fob-s-e to 0 within 10 minutes.
- A coalition STRIKE job needs the node's defense HP above 0 (`services/sim/src/nexus/core/tasking_gen.py:431`; GAMEPLAY §1b: "Done when the node's defense hp is 0"). So all three jobs end while the healthy east SAM (`ad-east`) is still up.
- The only strike job left is on `static-hq`. Its straight line crosses `ad-east`'s 35 km ring, so the route check refuses it for every jet.

This changes what to build next:

- Q-TD-78 (captured facilities change hands Disabled) would not fix this lockout. A "suppress the SAM" (SEAD) strike job would (Q-TD-81).
- Strike-first stays off for NX-412 part 5b, but for this new reason.

Two more findings:

- `victory_hold_mult` cannot change anything on strait-1. During a hold, every node the Static could capture is a hold node, so the multiplier scales every capture candidate equally.
- Overnight there is no drift at all: one night Offensive cannot physically bring a base's defenses to 0.

## 1. What was reviewed

**Runs.**

| Run | Sha | Profiles | Overrides beyond B |
|---|---|---|---|
| N0 #451 | 9d6fd30 | prime-50 + raid-300, 6 seeds, 24 h | none |
| N2 #452 | 9d6fd30 | prime-50 + raid-300, 6 seeds, 24 h | `director.score.victory_hold_mult=3.0` |
| N1p #456 | f3e2006 | raid-300, 4 seeds, 6 h | `combat.strike_structure_first=true`, `capture.defense_hp.AIRBASE=1000` |
| N3 #457 | f3e2006 | overnight-0 + quiet-5, 6 seeds, 24 h | `combat.strike_structure_first=true` |

- B is the base override set: `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`, `director.adaptation_up_above=2`. Upkeep was 0 in every job.
- **Source of measured numbers:** the queue reports on #451, #452, #456 and #457, transcribed by the lead for the `entertainment-reviewer` agent (Opus). "Derived" figures are the reviewer's arithmetic.
- **Code read** at develop af301a7. There are no commits to `services/sim/src`, `content` or `balance` after f3e2006, so this is the same sim code as N1p and N3. Files read:
  - `operations.py:268-302, 477-525, 552-575`
  - `launch.py:380-410, 565-650`
  - `campaign.py:165-215`
  - `director.py:100-115`
  - `tasking.py:949-995, 1149-1181`
  - `tasking_gen.py:30-41, 409-447`
  - `combat.py:128-160, 252-280, 395-405`
  - `defense.py:45-51, 79-100`
  - `balance/default.yaml`, `content/operations.yaml`, `content/theaters/strait-1.yaml:21-46`
  - commit 771b5a7 (NX-441)
- **Probes run by the reviewer** (all measured; read-only scripts kept outside the repo). They call the harness's own `runner.run` and `idle_reason`, with a wrapper that records which ring marker refused each idle jet:
  - raid-300, 1.5 h, sampled every 15 game minutes: seed 1 with B; seed 1 with B + strike-first; seeds 1 and 2 with the N1p config.
  - A coalition board dump at minutes 10, 20 and 30: B and B + strike-first, seed 1, 0.5 h.
  - overnight-0, seed 1, 13 h, B + strike-first, with node owners and defense HP every hour.
  - Every `--set` key proposed below was checked with the harness's own `override_balance`.
- **What doesn't exist yet:** the overlay, the site and clips. Every audience view is rebuilt from the reports, and every score is an estimate.
- **Caveat:** the probes cover 1-2 seeds of 1.5 h each. They prove the mechanism exists, not how often it occurs across 24 h.

## 2. Answers

### Q1. N0 against S0: how sensitive are verdicts to the sha?

- **Nine sim commits sit between 04e15f8 and 9d6fd30:** NX-441, NX-431, NX-430 (the Static answers a victory hold), NX-429, NX-434, NX-435, NX-436, NX-450, plus the NX-452 tooling.
- **NX-441 moved the trajectory first, but that does not make it the cause.** The repro agent found NX-441 to be the first commit that changes the trajectory. In a chaotic system almost any commit does that.
- **What fits NX-441:** Offensives per run-hour roughly doubled (derived).
  - Prime: 224 / 118.13 = 1.90, against S0's 0.94.
  - Raid: 376 / 129.57 = 2.90, against 1.58.
- **Other likely contributors [UNVERIFIED]:**
  - NX-450 at raid. Jets parked at west-airbase can no longer fire their AA_LIGHT, and they are now bomb targets.
  - NX-430 (hold response).
- **What changes in the S review's conclusions:**
  1. "Without strike-first, raid steamrolls" no longer holds at the tip, so that argument for the key is gone.
  2. The steamroll moved to prime: 2 victories, both flagged (s4 with 3 signals, s5 with 2). S0 prime had 6 NOT_ENDED.
  3. The S0-vs-S1 key comparison still stands, because it was run at one sha. The raid lockout appears again at f3e2006 (N1p) and at develop (probe).
  4. The S review's explanation of the lockout is wrong (Q3).
- **How sensitive:** very.
  - Victory counts on 6 seeds hold only at their sha. At a true win chance of 50%, P(at most 1 win in 6) = 7/64, about 11% (derived).
  - The timing change looks structural, though. S0's raid wins came at 3.46, 3.48, 3.86 and 10.17 h; N0's only win came at 9.57 h.
  - Treat outcome verdicts as void once sim code moves, and re-run a same-sha control (game-designer card).

### Q2. Why `victory_hold_mult` 3.0 changed nothing

- **Which nodes are strategic.** Strategic kinds are AIRBASE, FOB and PORT (`balance/default.yaml:129`). That gives 8 nodes on strait-1: west-airbase, fob-n-w, fob-s-w, cross-n, cross-s, fob-n-e, fob-s-e and east-airbase.
- **What a hold covers.** A hold needs a share of at least 0.80 (`campaign.py:176`), so at least 7 of the 8 (derived). `hold_nodes` is every strategic node the coalition holds (`campaign.py:198-199`).
- **What else the Static could capture.** Every other coalition node is either uncapturable (haven is SANCTUARY, bridges are BRIDGE) or `static-hq`, whose capture ends the game.
- **So the multiplier cannot reorder anything.** During a hold, every Offensive or Retake candidate is a hold node. `_press` (`operations.py:509`) multiplies them all by the same factor, so their order cannot change.
- **It could only lift captures over other operations, and they already rank first.** OFFENSIVE (1.0 × value ≥ 1 × weakness ≥ 1) and RETAKE (1.2) already outrank GARRISON_UPKEEP 0.9, ESCORT 0.8, PROBE 0.6 and RECON 0.5, apart from the ±10% noise edge.
- **What actually limits the hold response.** NX-430 already launches a hold-node capture at once, outside `max_ops` and staging (`launch.py:595-597, 642`; `operations.py:571`). What is left is money and travel time against a 30-minute hold. Both prime holds had 0 pressure events. Whether the budget is the block is [UNVERIFIED]; the NX-452 reasons are summed per campaign, not per hold.
- **The differing hashes:** `Campaign.config_hash` is a serialized campaign field (`world.py:482, 1390`), which fits the reading that only the config differs.
- **Verdict:** keep the key at 1.0, since it would matter on a map with capturable non-strategic nodes. Stop sweeping it on strait-1. Holds need a different lever: hold length or a funded hold response (§4).

### Q3. N1p: does it confirm the captured-SAM diagnosis?

No, it contradicts it. The S review's own test was: "if raid ring idle collapses with AIRBASE HP 1000, west-airbase is the lock". Ring idle did not collapse: it was 93%.

| Probe (raid-300, sampled every 15 min to 90 min) | "ring" share of idle jets | Ring that refuses them | west-airbase owner |
|---|---|---|---|
| B, seed 1 | 0 at every sample (idle reasons only `full`, `refuel`) | none | coalition |
| B + strike-first, seed 1 | 68-112 of 127-148 armed jets; 100% of idle at every sample | `ad-east` (310,120), HEALTHY, every time | coalition |
| N1p config, seeds 1 and 2 | 64-132 of 126-158 armed jets; 100% of idle | `ad-east`, HEALTHY, every time | coalition throughout; defense HP about 940-1000 |

- **Targets.** The goal in every refused case is `static-hq` (380,120). The jets start from haven (20,120) or west-airbase (90,120).
- **The board at minute 10 with strike-first:**
  - Defense HP is 0 at east-airbase, fob-n-e and fob-s-e.
  - The only coalition STRIKE job is on `static-hq`, with 0 claims.
- **The board with B alone:** STRIKE jobs on those three nodes stay open, and east-airbase's defense HP drains slowly (500 to 230 over 90 minutes).
- **Mechanism:**
  1. With strike-first, a claimant bombs the node's defense HP before units or sites (`combat.py:149-150`).
  2. A 300-viewer crowd brings the nearest Static bases to 0 HP within minutes.
  3. The board stops posting a STRIKE on a 0-HP node even while its SAM marker is live (`tasking_gen.py:431`, `or not view.defense_hp.get(node, 0)`; also `:443`).
  4. Nobody is tasked to hit `ad-east`, and the HQ job crosses its ring and is refused for every jet (`tasking.py:1149-1159`).
  5. Jets with direct orders bypass the board. That is why the striker persona was fine (N1p tail 17.9%) while auto-tasked newbies were not (95.9%).
- **Q-TD-78:** captured-facility handover never comes into play; west-airbase was never captured in any probe sample. A captured-SAM lock later in a 24 h run cannot be ruled out [UNVERIFIED].
- **Q-TD-80:** a ring exemption would not help either, since `ad-east` was never the coalition's.
- **AIRBASE HP 1000 was the wrong lever.** The crowd zeroes east-airbase anyway (0 by minute 15 in both seeds). The change mainly slowed Static captures: 5 in 24 run-hours, about 5.0 per seed-day (derived).
- **N1p in numbers:** strikes fired on 19 of 41 Offensives = 46% (derived), against 9 of 376 = 2.4% in N0 raid. Ring share of idle = 32384 / 34902 = 92.8% (derived).

### Q4. N3: overnight-0 and quiet-5

**Overnight-0: no drift at all**, not the slow drift of Q-TD-71 / NX-457.

- Pattern of Life held all 24 h. Offensives came only from the Pattern of Life capture slot, and `director.pol.offensive_period_s` 21600 gives exactly 4 a day.
- Strikes fired on 8 of 24 Offensives (derived 33%). Defenses down 0 times, captures 0.
- The 13 h probe saw node owners and every coalition defense HP unchanged at every hourly sample.
- **Why it cannot work as built** (derived from config):
  - One package is 2 jets × 4 AG_LIGHT × 50 = 400 damage at most.
  - A FOB (300 HP) needs at least 6 of 8 hits; an airbase (500 HP) cannot be zeroed by one package.
  - The expected damage is about 230 (estimate: Pk 0.7 falls to 0.35 at the 10 km release range, `combat.py:404`).
  - Stock deliveries rebuild defense HP between packages (2 HP per stock, `default.yaml:67`) [UNVERIFIED how fast overnight].
  - OFFENSIVE needs a coalition-owned target (`content/operations.yaml:11`), so the empty neutral crossings are never taken.
- A3 passes trivially, and the PLAYTEST-WATCHLIST "idle drift" item is triggered.

**Quiet-5: strike-first works for a small crowd.**

- A2 passes (median 144 s, tail 6.2%).
- Ring idle shows up in only 40 samples, which fits the mechanism: 5 viewers cannot zero every eastern defense.
- 18 captures over 144 run-hours = 3.0 per seed-day, one every 8 h per seed (derived).
- **Risk:** the Static economy outgrows the coalition's. Static income is 617.5 / 263.7 = 2.34× (derived), the pool ratio is 12333 / 3647 = 3.38× (derived), and momentum is 36%.
- A DEFEAT over 72 h is [UNVERIFIED]. There is no same-sha control with strike-first off, so nothing here can be put down to the key yet.

### Q5. NX-412 part 5b values

| Key | Value | Evidence |
|---|---|---|
| `economy.upkeep.*` | 0 (confirm Q-TD-75) | K review; nothing in N contradicts it |
| `combat.strike_structure_first` | false (confirm Q-TD-79a) | New reason: the `ad-east` lockout via `tasking_gen.py:431`. The companion is the SEAD job (Q-TD-81), not Q-TD-78 |
| `director.adaptation_up_above` | 2 (keep) | Untested: no N job varied it |
| `director.score.victory_hold_mult` | 1.0 | Inert on strait-1 (Q2) |
| `capture.defense_hp.AIRBASE` | 500 (shipped) | 1000 fixed nothing and slowed captures |

## 3. Audience scores (estimates, 1-5)

| Audience | N0 prime / raid (tip, strike-first off) | N1p raid (strike-first + AIRBASE 1000) | overnight-0 / quiet-5 (strike-first) |
|---|---|---|---|
| Watcher | 2.5 / 2 | 1.5 | 1.5 / 3 |
| Player | 2.5 / 1.5 | 1 | n/a / 3.5 |
| Site watcher | 2 / 2 | 1.5 | 1.5 / 3 |
| VOD and clip | 2.5 / 2 | 2 | 1 / 2.5 |

- **Watcher.**
  - Sitreps are frequent (derived): raid about 10.5 an hour, prime about 7.0.
  - But warnings rarely pay off: strikes fire on only 2.4-7.1% of Offensives (derived), a cry-wolf effect.
  - Both profiles have a median longest stretch of 417.5 minutes without an Offensive.
  - 40% of Director windows are "staged" (prime 2836 / 7087, raid 3121 / 7774, derived), and the cadence floor never fires while something is staged (`director.py:105`). That this causes the long stretches is [UNVERIFIED].
  - With strike-first at raid, about 100 jets sit parked while the map turns red.
- **Player.**
  - N0 raid A2 tail is 41.2%. Capturers and haulers have a 100% tail, scouts 88.7%.
  - N1p auto-tasked newbies have a 95.9% tail.
  - Raid idle armed share is 72%. Under the old reason names, "other" was 59.4% of idle samples (derived).
- **Site watcher.**
  - Victory holds are never contested: 0 broken, and 0 pressure events in the prime holds.
  - Both prime wins (9.98 h, 12.15 h) are flagged as steamrolls.
  - The overnight map does not change in 24 h.
- **VOD and clip.**
  - STRIKE_DOWNED comes 2.6-4.4 times an hour, a good 30-second setup and payoff.
  - Only 13 Static captures per profile in 6 seed-days.
  - The hold climax is a 30-minute timer with no fight.
  - A night recap has nothing to show.
- **Low population.**
  - Overnight-0 is calm, as the Calm-by-default pillar asks, but has no morning story. That fails Q-GP-28 as amended by Q-TD-71.
  - Quiet-5 is the best result in this sweep: real agency (A2 passes) and a capture every 8 h per seed.

## 4. Recommendations, watch items, questions

### Ranked recommendations

1. **SEAD strike job (design, S; Q-TD-81).** The coalition board keeps a STRIKE job on a foe node whose discovered air-defense site is not Disabled, even after its defense HP reaches 0. This amends GAMEPLAY §1b `strike:<node>` and `tasking_gen.py:425-437`.
   - With strike-first, a claimant at a 0-HP node already falls through to units and sites (`combat.py:149-156`), so it would hit the SAM (threat 90).
   - Expected effect: the raid ring lockout dissolves, and every audience gains a "kill the SAM, open the sky" beat.
   - Symmetric under EC-3.
2. **Harness metric (S).** Split "ring" idle by the site that blocks it and the job target, so the next lockout is not misdiagnosed. The probe's method was to wrap `tasking.ring_crossed`.
3. **Re-run strike-first after item 1.** prime-50 + raid-300, 24 h, 6 seeds, B + `combat.strike_structure_first=true`.
4. **Same-sha control for N3.** overnight-0 + quiet-5, 24 h, 6 seeds, B only.
5. **Hold length probe (tuning).** prime-50 + raid-300, 24 h, 6 seeds, B + `campaign.victory_hold_min=90`. Are holds contested or broken, and do the prime steamroll flags drop?
6. **Staging drought probe (tuning).** prime-50 + raid-300, 24 h, 6 seeds, B + `director.staging.max_wait_windows=30` (shipped 90). Do the staged share and the longest dry stretch shrink?
7. **Overnight drift (design; Q-TD-83).**
   - Let the Pattern of Life capture slot target a neutral strategic node (the crossings). That gives visible drift at zero A3 cost and a retake target for the morning crowd.
   - A second step could be a night Offensive with 3-4 strike slots.
   - Cheap falsification probe first: overnight-0, 24 h, 6 seeds, B + strike-first + `director.pol.offensive_period_s=10800`. The expectation is that more packages alone still flip nothing.
8. **Remove `victory_hold_mult` from strait-1 sweeps** and keep it at 1.0.
9. **Park Q-TD-78.** Revisit only if the ring-by-site metric shows a captured-SAM lock.

### Watch items for PLAYTEST-WATCHLIST

- A STRIKE job disappears at 0 defense HP while the base's SAM is live, and "ring" is above 50% of idle samples (split by site).
- Victory holds with 0 pressure events.
- A staged share of Director windows above 30%.
- Overnight-0 with 0 flips in 24 h.
- Quiet-5 Static income above 2× the coalition's, followed over 72 h.
- Keys that cannot act on the shipped theater (`victory_hold_mult` on strait-1).

### Owner questions

These are recorded as Q-TD-81 to Q-TD-85 in `docs/planning/OPEN-QUESTIONS.md`.
