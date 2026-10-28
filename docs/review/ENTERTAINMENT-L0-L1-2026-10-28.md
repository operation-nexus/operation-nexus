# Entertainment review: L0 #475 and L1 #476 (quiet-5 and overnight-0, sha 08831d0), 2026-10-28

## Bottom line

1. **With strike-first on, quiet-5 collapses rather than drifts.**
   - In the probed seeds, the coalition loses all three of its strategic nodes in 0.5–4.3 game hours, with 1–5 viewers live. It then holds only haven for the rest of the run.
   - The Static then has nothing it is allowed to target. That is the whole of the report's `no_target` 2541, and it is not a pause.
   - The war can't end early. DEFEAT needs haven's defense HP at 0 for 30 minutes, so the campaign runs on to a TIME_LIMIT loss at 72 h, with momentum near 0 for most of it.
   - In one 72 h probe, 28–30 live viewers still retook nothing.
2. **Strike-first off is no better at quiet-5.**
   - There is no collapse, but no captures by either side, A2 fails, and 184 Offensives are announced that never reach a strike.
   - So the quiet-5 problem is not strike-first. There are two causes:
     - No brake on Static captures between 0 viewers and a real crowd. The night-progress cap and the idle floor act only at exactly 0 viewer units.
     - A 5-viewer coalition has almost no way to retake. Its board posts no CAPTURE job.
3. **Q-TD-79 holds with a condition:** strike-first stays on globally in NX-412 part 5b, but only together with a low-population brake (Q-TD-93).
   - The overkill check doesn't fix this.
   - "Director strikes go structure-first" makes it worse.

## 1. What was reviewed

- **Numbers:** the lead's extract of #475 and #476. Both runs:
  - sha 08831d0, 24 h, 6 seeds, overnight-0 + quiet-5;
  - base overrides B (`economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`, `director.adaptation_up_above=2`), upkeep 0;
  - L1 adds `combat.strike_structure_first=true`.
  - Prior reviews: Q0-Q1, sweep P, sweep N.
- **Probes (measured, read-only):**
  - Run against a `git archive` of 08831d0 through `runner.run` and `override_balance`.
  - Owner changes were checked every tick. Every 15 game minutes the probe recorded strategic owners, haven defense HP, the defeat run, pools, tier, live viewer units, momentum, scores and Static jobs.
  - Runs, all quiet-5:
    - strike-first on, 24 h: seeds 2, 3 and 5;
    - strike-first off, 24 h: seed 2;
    - strike-first on, 72 h: seeds 2 and 5.
  - The 24 h probes match the queue's per-seed dry stretches.
  - **Caveat (L-39):** the 72 h runs have a different crowd, because `profiles.schedule` draws from the run length. They show what a lost map does over 72 h, not what the queue's seeds did.
  - Probe scripts and outputs stayed in the session scratchpad.
- **Code read** (08831d0 unless noted):
  - `campaign.py`: 17-21 (defeat), 177-184 (end checks), 218-226 (`_defeat_run`);
  - `launch.py:386-389` (`no_target`, `targets_busy`);
  - `operations.py`: 272-277 (preconditions), 305-307 (`_targets`);
  - `capture.py`: 43-52 and 105-113 (idle floor and night cap), 174-177 (`_quiet`);
  - `defense.py:47-52` (sanctuary floor);
  - `tasking_gen.py:18-66` (coalition job kinds; there is no CAPTURE job);
  - `tools/balance/profiles.yaml`, and `runner.py:115-127` (capturer persona).
- **Not available yet:** the overlay, the site and clips, so every score is an estimate. NX-464 and NX-465 were not in L.

## 2. Answers

### Q1. What falls, and how close is DEFEAT? (quiet-5, strike-first on, measured)

| Probe | Coalition losses (game h) | Coalition retakes | Holds nothing from | Lowest haven HP | End |
|---|---|---|---|---|---|
| s2, 24 h | fob-s-w 1.21, west-airbase 1.52, fob-n-w 1.74 | none | 1.74 h (92.8% of the run, derived) | 806 | 24 h, nodes 0% |
| s5, 24 h | fob-s-w 1.69, fob-n-w 1.81, west-airbase 2.13 / 2.30 / 3.58, fob-n-w 4.30 | west-airbase 2.22 and 3.40, fob-n-w 4.13 | 4.30 h | 810 | 24 h, nodes 0% |
| s3, 24 h | fob-s-w 4.59, fob-n-w 4.68 | none | never (west-airbase held) | 1000 | momentum 31–39 |
| s2, 24 h, **off** | none (the Static took the crossings at 5.99 and 6.18 h) | none | never | 1000 | momentum 50 |
| s2, 72 h (different crowd) | all 3 by 1.80 h | none | 1.80 h | **0** | **TIME_LIMIT, ENEMY wins, 5.4 to 99.4** |
| s5, 72 h (different crowd) | all 3 by 5.67 h | west-airbase 3.41 | 5.67 h | 806 | **TIME_LIMIT, ENEMY wins, 45.8 to 98.6**; 28–30 live viewers at 60–66 h and still 0 nodes |

- **Pools:** the coalition pool sits pinned at `economy.storage.floor` (2000). The Static pool reaches its storage cap of 14000 by about 2 h and has nothing to spend it on.
- **Defeat condition** (`campaign.py:17-21`): haven's defense HP stays at 0 for `campaign.defeat.hold_min` (30 game min) in a row.
  - A repair resets the run.
  - With no viewer unit live, the run is held, not advanced, and haven can't drop below 1 HP (`defense.py:47-52`).
- **A lone viewer can trigger the loss.** In s2 at 72 h, a PROBE took haven to 1 HP at 0 viewers. One viewer joining then started the defeat run at HP 0. It reached 23.8 of 30 minutes before that viewer's unit went. So a viewer arriving at a lost map can be the one who "loses the war" within minutes.

### Q2. Slow drift or collapse? Collapse

- **The cap.** Q-TD-71 allows at most 1 flip per 12 h at 0 viewers, via `campaign.night_progress_cap_nodes_per_h` 1/6, which applies only with no viewer unit.
- **What happened.** quiet-5 always has 1–6 units live, so no cap applies. s2 lost 3 nodes in 0.53 h, about 70× the 0-viewer cap rate (derived).
- **Resistance.** The owner's "at least some resistance" (Q-TD-91) is broken from the other side: the coalition resists for 1–4 h, then nothing happens for 20+ h.
- **The lost map is a trap.** The coalition board has no CAPTURE job kind (`tasking_gen.py:18-66`). Ground capture comes only from the capturer persona and ASSIST_OBJECTIVE, and west-airbase's SAM blocks the jets. Which of these dominates is [UNVERIFIED].

### Q3. What `no_target` 2541 is

- Offensive and Retake need `target_owner_is_coalition` and `target_capturable` (`operations.py:272-277`).
- Haven is an uncapturable sanctuary, and the neutral crossings aren't the coalition's. So once the coalition holds only haven, the Static has nothing it may take. Every `no_target` sample in the probes is one where the coalition holds 0 strategic nodes.
- The stream is dead:
  - the momentum bar sits near 0;
  - the Static drops back to Pattern of Life;
  - only PROBE strikes on haven, patrols, recon, and a growing count of ESCORT_CONVOYS jobs remain. The convoy jobs rise about 1 per hour to 18–28, possibly stale [UNVERIFIED].
- Q-TD-83 (a) doesn't help here: by then the Static already holds the crossings.

### Q4. Does Q-TD-79 still hold?

**Yes, strike-first stays on globally, but 5b ships it together with a low-population brake.**

| Option | quiet-5 | Prime and raid | Verdict |
|---|---|---|---|
| ON alone | collapse, then a dead map (measured) | best prime stream, fewer raid steamrolls (Q1) | not alone |
| **ON + low-population brake** (design) | estimate: keeps L1's A2 pass and a working capture chain, with flips spaced out | none, if the brake fades out by `capture.quiet_ref` | **pick** |
| Overkill check (NX-468) instead | estimate: doesn't change units-first targeting, so Static strikes still don't reach defenses (P0: 0 strikes) [UNVERIFIED] | unknown | a companion, not a substitute |
| "Director operation strikes go structure-first" (EC-3 asymmetry) | **worse**: keeps the collapse, may lose the A2 pass [UNVERIFIED] | keeps prime captures | reject |
| Existing keys alone | `capture.quiet_floor` and `quiet_ref` act only on coalition captures; the night cap and idle floor act at 0 viewers only; global keys would also slow prime; there is no catch-up key | — | probes only (L2–L4) |

**Brake proposal (Q-TD-93).** The night-progress cap's minimum spacing between Static flips fades from its 0-viewer value down to none at `capture.quiet_ref`. On top of that, the forward-airbase protection (Q-GP-28) extends to whenever the coalition holds no other strategic node, so there is always one base to fight from. Cost estimate: S–M.

NX-464 is unlikely to change L1's quiet-5, whose idle reasons were ring 11 with no refuel. It may help L0, which had refuel 169. Both are [UNVERIFIED].

### Q5. Next runs (queued at b0bc4e3, which includes NX-464 and NX-465)

| Run | Issue | Config |
|---|---|---|
| L1p | #483 | B + strike-first (control) |
| L2 | #484 | L1p + `capture.quiet_floor=0.3` |
| L3 | #485 | L1p + `director.provocation.escalate_threshold=20` |
| L4 | #486 | L1p + `director.cadence_windows=30` |

None of these is the brake. They measure how far tuning gets.

## 3. Audience scores (estimates, 1–5)

| Audience | L0 quiet-5 (off) | L1 quiet-5 (on) | overnight-0 (both) |
|---|---|---|---|
| Watcher | 2 | 2 (4 in the first 2–4 h, 1 after) | 2 |
| Player | 2 | 2 | n/a |
| Site watcher | 2 | 1.5 | 2 |
| VOD and clip | 1.5 | 2.5 | 1.5 |

- **Watcher.** L1 opens well: bases fall, and west-airbase changes hands four times in 1.5 h. Then the bar reads 0% for about 20 h, and the morning crowd arrives to an all-red map.
- **Player.** L1 passes A2 (median 46 s). After the collapse, jets launch from haven into a SAM ring, and a returning lone viewer can restart the defeat run.
- **Site watcher.** "We lost everything in 2 hours" is readable, but then nothing changes for days. In s3 the time-limit score was 170 to 82 for the coalition at 22 h while it held 1 of 8 nodes: objective points (`campaign.score.objective_points` 5) dominate.
- **VOD and clip.** There are good moments in the first hours. A long VOD has its climax at hour 2.

## 4. Recommendations, watch items, decisions

### Ranked recommendations

1. **Low-population brake** (design, S–M; Q-TD-93, NX-474).
2. **Strike-first on in 5b, together with item 1** (Q-TD-79).
3. **A coalition retake path** (design, M; Q-TD-94, NX-475): for example, a coalition CAPTURE/RETAKE job on a recently lost node.
4. **Restart the defeat run after an empty stretch** (design, S; Q-TD-95, NX-476).
5. **Tuning probes L2–L4** (queued).
6. **NX-468 overkill check as planned,** as the owner's "both" companion.
7. **Harness counters** (NX-477): minutes the coalition holds 0 strategic nodes, coalition captures per profile, and the ESCORT_CONVOYS job count over time.
8. **Review objective points in the time-limit score** (Q-TD-96, under Q-SIM-64).

### Watch items for PLAYTEST-WATCHLIST

- The coalition holds 0 strategic nodes for more than 2 h at any crowd above 0.
- The defeat run starts within 10 min of a lone viewer arriving.
- Static flips faster than 1 per 6 h at 1–10 viewer units.
- The time-limit score leader is not the side holding the map.
- Static ESCORT_CONVOYS jobs rising steadily for hours.

### Decisions (recorded as lead decisions, owner may veto)

- **Q-TD-93:** a low-population brake ships with strike-first in 5b.
- **Q-TD-94:** when the coalition holds no strategic node, give it a guaranteed foothold or a retake job at quiet crowds. A DEFEAT siege applies only after a long hold with real viewers. Rejected alternatives: end the war at once; or leave it as now, a TIME_LIMIT up to 70 h later.
- **Q-TD-95:** the defeat run restarts from 0 after an empty stretch, so nobody loses the war by joining.
- **Q-TD-79:** "Director operation strikes go structure-first" is dropped as an option.
- **Q-TD-96:** objective points in the time-limit score are reviewed under Q-SIM-64.
