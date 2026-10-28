# Entertainment review: harness sweep P (P0 #463, P1 #464, P2 #465, P3 #466), 2026-10-28

**Bottom line.** Probes for this review found two code-level causes for most of the raid idling. Neither one is a balance key.

1. **`refuel` idle is a trap at a starved base.** It is not rearm congestion, and it is not the NX-463 strike-credit bug. In every `refuel` sample the probes took (raid-300, B, ee1d570, seeds 1–2), the idle jets were LANDED at west-airbase. The base sat below its starvation floor, and each jet's tank was capped at about 50%:
   - A starved base fills a tank only to `logistics.starved_loadout.fuel_frac` (0.5; `services/sim/src/nexus/core/rearm.py:124,153`).
   - `_feasible` then answers `refuel`, because a full tank would reach the job (`services/sim/src/nexus/core/tasking.py:1117`).
   - The refuel step does nothing for a jet that is already landed at a base with stock above 0 (`tasking.py:1272-1274`). So the jet never goes to haven, which has unlimited stock. It waits for the base to climb back over its floor, and every rearm pushes the base under again.
   - The trap is still present at develop 54c43bf.
2. **The raid `ring` idle in these probes is a job-slot effect, not a new SAM lockout.** At the moment it appeared, the three reachable strike jobs were all full (5/5 claims). The only job with a free slot was `strike:static-hq`, and its line crosses `ad-east`'s ring. `_open` (`tasking.py:307-311`) counts that free but unreachable job as "a free slot exists". That turns off overfill for every jet, so 109 jets sat idle. Each of them could have flown at once, or after one rearm, to a full job that overfill would have opened to them.

The other answers:
- Strike-first helps quiet servers mainly by making the Static's capture chain work. It should not become a population-dependent rule.
- A longer victory hold only delays the result.
- `director.staging.max_wait_windows=30` (P2) is a promising 5b value, but it needs a re-run at the SEAD sha first.
- P3 falsifies Q-TD-83 option (c).

## 1. What was reviewed

- **Numbers.** The lead transcribed the queue reports on #463–#466 into a numbers extract. All four runs:
  - ran at sha ee1d570, 24 h, 6 seeds;
  - used base overrides B: `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`, `director.adaptation_up_above=2`;
  - had upkeep 0.

  The controls are N0 #451 (9d6fd30) and N3 #457 (f3e2006), described in `ENTERTAINMENT-sweep-N-2026-10-27.md`. "Derived" marks the reviewer's own arithmetic on those numbers.
- **Code read** at develop 54c43bf. The diff ee1d570..54c43bf adds three things, and **none of them existed at the P sha**, so they are absent from every P report:
  - NX-461 SEAD (`tasking.py:637-649`, `tasking_gen.py:436-440`);
  - Q-TD-86 (a Disabled facility stays Disabled until repaired to the Mission-kill line);
  - the NX-462 `ring_by_site` metric.

  Q0 #470 and Q1 #471 (7d0b50e) include SEAD but not NX-462, so their reports will not split ring idle by site either.
- **Probes (measured, read-only).**
  - **How they ran.** They call the harness's own `runner.run` with an `on_tick` hook and `override_balance`. They recompute `idle_diagnosis`'s walk with the sim's own `_open`, `_feasible`, `crosses_ring` and `ring_crossed`. Every 15 game minutes they record idle armed viewer jets by reason:
    - for `refuel`: state, node, whether the node is starved, fuel fraction and job;
    - for `ring`: the blocking marker and the job.
  - **What they ran against.** They used a `git archive` of ee1d570, plus one short run at develop. The probe scripts lived in the session scratchpad and are not in the repo.
  - **Prefix runs.** Probes named `q_*` are prefixes of 24 h runs (`--hours 24`, stopped at 2.5–3.5 h), so they follow the same crowd schedule as the queue runs.
- **Harness pitfall found while probing (measured).** A `--hours 3.5` run is *not* the first 3.5 h of a 24 h run. `profiles.schedule` (`tools/balance/profiles.py:163-177`) draws every arrival time first and only then the personas, so the persona sequence depends on the run length. The reviewer's first 3.5 h runs showed ring idle from 2.75 h that the 24 h prefixes do not show. Short runs can be compared with each other, but not seed-for-seed with long queue runs (L-39).
- **What doesn't exist yet:** the overlay, the site and clips. Every audience view below is rebuilt from the reports, and every score is an estimate. The probes cover 1–2 seeds for at most 3.5 h, so they prove mechanisms, not 24 h frequencies.

## 2. Answers

### Q1. P0 against N3: is strike-first good for quiet servers?

P0 is a valid same-sim control: the sim at ee1d570 equals f3e2006 apart from harness diagnostics.

| quiet-5, 24 h × 6 | Off (P0) | On (N3) |
|---|---|---|
| Static Offensives | 224 | 194 |
| Offensives where strikes fired | **0** (224>0>0>0>0) | 67 (194>67>21>18>18) |
| Static captures | 0 | 18 (3.0 per seed-day, derived) |
| A2 | FAIL: median 138 s, tail 23.1% of 13 newbies ≈ **3 newbies** (derived) | pass: median 144 s, tail 6.2% of 16 ≈ **1 newbie** (derived) |
| Momentum | 48.1% | 36.0% |
| Static/coalition income | 1.49× (379.3/253.9, derived) | 2.34× |
| Ring idle samples | 313 | 40 |

- **What strike-first does at 5 viewers.** It lets the Static's Offensive packages hit defenses at all. With it off, the Static's jets never fired on a defense in 224 Offensives. That is the old Q-SIM-84 watch item at its worst.
  - "On" makes the war move: about one Static capture every 8 h per seed, and something for the morning crowd to retake.
  - "Off" means 37 announced Offensives per seed-day (derived) that never land, which is a cry-wolf stream.
- **The A2 difference is too small to read.** It is about 3 newbies against 1 (derived), so it is not credited to strike-first. The cause is [UNVERIFIED]: no probe.
- **The cost of "on":** the coalition loses ground (momentum 36%) and the Static's economy lead grows. Whether that ends in a DEFEAT within 72 h is [UNVERIFIED].
- **A population-dependent rule is not recommended:**
  - It would make a combat rule (CB-10) depend on an invisible quantity, so viewers could not learn what jets do.
  - It would flip mid-session as a raid arrives or leaves.
  - It would double the harness matrix that Q-GP-48 wants kept to one default rule set.

  Keep Q-TD-79 a single global decision, made from Q0/Q1 at the SEAD sha. If Q1's raid lockout is gone (SEAD's purpose), "on" everywhere gives quiet servers this gain for free. If Q1 is still bad at raid, the honest alternative is a design question rather than a population switch. The quiet-5 gain comes entirely from the Static's operation strikes, so the question would be "Director operation strikes go structure-first", an EC-3 asymmetry the owner would have to accept.

### Q2. P1 (`campaign.victory_hold_min=90`): a lever, or only a delay?

**Only a delay, as measured.**
- Every victory came exactly +1.00 h later (60 min = 90 − 30). Outcomes, funnels and A2 did not change.
- Static operations per hold rose: prime from [7, 11] to [24, 23], raid from 18 to 82 (4.6×, derived), for three times the hold length.
- Pressure stayed near zero (prime [0, 5], raid [1]) and no hold broke.
- The hold response already bypasses staging and `max_ops` (`launch.py:595-601, 642`). What fails is the chain itself: the Static's strike step fires on 16 of 224 prime Offensives (7%, derived), so more time just means more failed packages.

What would make a hold contestable (Q-TD-84; design):
1. **Pause the hold clock (no reset) while any hold node is under pressure.** "Pressure" means a Static capture bar, defenses down, or a Static capture operation inside the node's defend radius.
   - Today the hold breaks only when a node changes owner (`campaign.py:193-218`): a full capture, which the Static's funnel almost never achieves.
   - It reads well on stream ("HOLD PAUSED: FOB North-West contested"), and it uses pressure the Static already produces. The prime hold with 5 pressure events would have paused.
   - Cost: S–M (ECONOMY EC-9, `campaign._track_hold`, new event or sitrep).
2. **Make the Static's hold-response strikes land:** strike-first for operation strikes (Q-TD-79) or the overkill check (Q-TD-73).

Keep `campaign.victory_hold_min` at 30. A longer hold is worth revisiting only after (1): 45–60 minutes of countdown with a fight in it is good watcher content.

### Q3. P2 (`director.staging.max_wait_windows=30`): the ring jump, and P2 as a 5b value

**Probed mechanism (measured; seed attribution in P2 [UNVERIFIED]).** In the run that showed ring idle (raid-300 s1, B, ee1d570, `--hours 3.5`, dump at 2.75 h):
- 109 ring-idle jets, all LANDED at west-airbase.
- Their pool held `strike:east-airbase`, `strike:fob-n-e` and `strike:fob-s-e`, each with **5/5 claims**, so none was open. Verdicts on those were `refuel` for 73 jets and `ok` for 36.
- Two patrols were also full.
- The only open job was `strike:static-hq`, with 0 claims and verdict `no`: refused by the ring of `AIR_DEFENSE_SITE@east-airbase`.
- east-airbase's defense HP was **481**, not 0. This is *not* sweep N's lockout, where the job had ended at 0 HP.
- `strike:static-hq` first appeared at 2.75 h as a marker job, when a site at the HQ was discovered.

`_open` (`tasking.py:307-311`) returns free jobs, and overfill applies only when none are free. So one free job that nobody can reach disables overfill (`overfill_factor` 2) on every reachable job. 36 of those jets could have flown at once; the other 73 were one rearm away.

**Most likely reading of P2's 24033 ring samples:** the HQ job appeared in one or more P2 raid seeds and stayed open for hours.
- At about 110–150 jets per sample, that is roughly 160–220 five-minute samples, or 13–18 game hours (estimate).
- Staging plausibly affects this only through the trajectory (what is discovered when, and which jobs exist), not through a staging mechanism [UNVERIFIED].
- The NX-462 key reads "AIR_DEFENSE_SITE @ east-airbase -> STRIKE static-hq" for both a real lockout and this saturation case, so it cannot tell the two apart.
- At develop with SEAD, a short run still logged 114 ring samples of exactly that key. The 15-minute dumps caught none of those samples, so the probe cannot separate lockout from saturation either.

**P2 as a 5b candidate:**

| | prime P2 / N0 | raid P2 / N0 |
|---|---|---|
| Outcomes | 6 NOT_ENDED / 2 victories, both steamrolls | 2 victories (1 steamroll) / 1 victory |
| Offensives | 267 / 224 | 288 / 376 (−23%, derived) |
| Captures | 19 / 13 | 9 / 13 |
| Longest stretch without an Offensive, median | 440 / 417.5 (not better) | 311.5 / 417.5; max 432 / 719 |
| A2 tail | 25.3% / 32.1% | 37.7% / 41.2% |
| Budget-refused windows | 3096 / 1912 | 2249 / 1171 |
| STAGING_DISPERSED | 76 / 27 (2.8×, derived) | 63 / 28 |

- **Promising:** prime loses its steamrolls and gains captures, and A2 improves at both crowds.
- **Concerns:**
  - Raid victories rise, but on 6 seeds that is noise-level.
  - Prime dry stretches don't shrink.
  - There are more DISPERSED sitreps. `launch.py:647-648` labels a fallback launch "from elsewhere" as DISPERSED, so viewers may read "the threat dispersed" just before an attack arrives. The viewer-facing wording is [UNVERIFIED].
- The sim has moved since ee1d570 (L-37), so this is not a 5b value yet. Re-run P2 at the Q0/Q1 sha first.

### Q4. What `refuel` means, and why raid jets sit in it

**Definition.** `idle_diagnosis` walks the open jobs in rank order and stops at the first verdict that isn't `no` (`tasking.py:1000-1006`). `refuel` means that job fails now on fuel or rounds, but a full tank and load would make it (`_feasible`, `tasking.py:1111-1117`). `_assign` then calls `_refuel` (`:961`), which heads for the nearest landing base with stock, "unless already landed at one" (`:1269-1274`).

**Measured in the 24 h-prefix probes** (raid-300, B, ee1d570, seeds 1–2):
- **Every `refuel` jet in every sample** was LANDED at west-airbase, starved, not stalled, short on fuel at about 0.5 tank, and holding a STRIKE job on fob-n-e, fob-s-e or east-airbase.
- west-airbase stock ran 205–499 across samples, always below its floor of 500 (0.25 × 2000).
- The base is not stalled: it sells fuel, but only up to the starved cap of 0.5 × `fuel_s` (`rearm.py:124, 153`). Rounds weren't the problem.
- `_refuel` counts any base with stock above 0, so a jet landed at the starved base does nothing.
- In seed 2, jets stayed in `refuel` for up to 12 consecutive 15-minute samples, about 3 h.

**What it is not:**
- Not the NX-463 credit bug. These jets are LANDED, not RTB.
- Not rearm-rate congestion. The rate is per unit (`rearm_rate` 0.5 stock/s). The crowd's total draw keeps the base pinned under its floor, and the jets can't leave.

**Size (derived):** `refuel` was 223918 / 263747 = 84.9% of P1 raid idle samples. With the idle share of armed jets at 72%, that is about 61% of armed jets. N0's old `other` + `refuel` total (222665) is close to P1's 223918, which fits the NX-454 rename. The signature is still present at develop 54c43bf.

**Tuning probes (2.5 h prefixes, seed 2, measured):**

| Config | Idle/armed over 9 samples | `refuel` | west-airbase mean stock |
|---|---|---|---|
| B | 0.776 | dominant | 415 |
| B + `logistics.starved_loadout.fuel_frac=1.0` | 0.496 | gone; all idle reads `full` | 34, at 0 in most samples |
| B + `logistics.starve_threshold=0.1` | 0.632 | trap persists | 115 |

- With `fuel_frac=1.0`, the remaining idle is the slot cap (about 19 board slots for 140 jets).
- Draining the forward base would also starve its defense HP (`starve_hp_drain_per_min` 5), a risk [UNVERIFIED over 24 h].

**The right fix is design (Q-TD-88):** the refuel step should skip a starved base whose capped tank can't serve the job, and go to the nearest unstarved base. Haven is unlimited, and the starved-loadout rule still applies to any base below its floor.
- Cost: S, and it applies to both sides (EC-3).
- It touches GAMEPLAY §1b/§5, `tasking._refuel` and `_feasible`, and Q-SIM-53.
- Expected effect: jets cycle through haven instead of parking, and west-airbase recovers above its floor because the draw falls. Viewers see sorties instead of a parked carpet of jets.

### Q5. P3: is Q-TD-83 option (c) falsified?

Yes.
- 48 Offensives: strikes fired on 15 (31%, derived), defenses down 0, captures 0.
- Coalition kills rose from 47 to 119 (2.5×, derived), so more frequent night packages only feed the coalition's air defense.
- This matches the sweep N arithmetic: one 2-jet package does at most 400 damage, against 300 HP for a FOB and 500 for an airbase.

What it means for the other options:
- **(a) is the only option that creates drift without beating defenses.** The crossings are NEUTRAL FOBs with 0 defense HP (`content/theaters/strait-1.yaml:29-30`; a neutral node starts at 0, `balance/default.yaml:84`). Today an OFFENSIVE needs `target_owner_is_coalition` (`content/operations.yaml:11`), so (a) needs a catalog or operation change. Keep Q-TD-83 (a) as decided.
- **(b)** (3–4 jets) would do at most 1200–1600 damage (derived), enough to zero a FOB. P3 suggests it would also bring more kills; weigh it against A3 only after (a).
- `director.pol.offensive_period_s` stays at 21600, the shipped value.

### Q6. Updated 5b recommendation

Every key below was checked in `balance/default.yaml`.

| Key | Value | Change from Q-TD-85 |
|---|---|---|
| `economy.upkeep.*` | 0 | none |
| `combat.strike_structure_first` | false for now; decide from Q0/Q1 | P0: off leaves quiet-5 with 0 Static strikes |
| `director.adaptation_up_above` | 2 | still untested |
| `director.score.victory_hold_mult` | 1.0 | none |
| `capture.defense_hp.AIRBASE` | 500 | none |
| `campaign.victory_hold_min` | 30 | P1: 90 only delays |
| `director.staging.max_wait_windows` | 90 now; 30 is the candidate after a same-sha re-run | new (Q-TD-90) |
| `director.pol.offensive_period_s` | 21600 | P3 |

5b should not claim anything about raid idle. That idle comes from the refuel trap and the overfill block, which are code and design issues, not keys.

## 3. Audience scores (estimates, 1–5)

| Audience | P0 quiet-5 / overnight-0 (strike-first off) | P1 prime / raid (hold 90) | P2 prime / raid (wait 30) | P3 overnight (period 3 h) |
|---|---|---|---|---|
| Watcher | 2 / 1.5 | 2.5 / 2 | 3 / 2.5 | 1.5 |
| Player | 3 / n/a | 2.5 / 1.5 | 3 / 1.5 | n/a |
| Site watcher | 2 / 1.5 | 2 / 2 | 3 / 2 | 1.5 |
| VOD and clip | 1.5 / 1 | 2 / 2 | 2.5 / 2 | 1.5 |

- **Watcher.**
  - P0 quiet: 224 announced Offensives and zero strikes is cry-wolf.
  - P2 prime has the most going on: 267 Offensives and 19 captures, with no early ending.
  - Raid: 100 or more jets parked at west-airbase while the board shows open targets (probe).
  - Top problems: warnings that never land (P0, P3); the parked raid air wing; the DISPERSED wording.
- **Player.**
  - Raid idle armed is 72–74%, about 85% of it `refuel` (P1), with jets stuck for up to 3 h (probe).
  - P2 improves A2 tails at both crowds.
  - Top problems: the starved-base trap; overfill blocked by an unreachable job; capturers, haulers and scouts with near-100% tails (N0, unchanged).
- **Site watcher.**
  - Holds still have 0 breaks, and a 90-minute hold is just a longer foregone conclusion.
  - P2 prime's 6 NOT_ENDED seeds with captures are a running story.
  - Top problems: uncontested holds; no overnight change (P0, P3); a raid steamroll in P2.
- **VOD and clip.**
  - STRIKE_DOWNED moments remain.
  - P3 adds 2.5× night kills of Static jets, a small clip source, but no payoff.
  - A hold climax with no fight still has no clip.
- **Low population.**
  - Quiet-5 with strike-first off is calm but static. With it on (N3), the war moves at the coalition's expense.
  - Overnight-0 still shows no drift (P0, P3), so Q-GP-28 as amended by Q-TD-71 is still unmet.

## 4. Recommendations, watch items, questions

### Ranked recommendations

1. **Starved-base refuel step** (design, S; Q-TD-88, NX-464). An aircraft whose job fails on fuel at a starved base, where the capped tank can't serve the job, rearms at the nearest unstarved landing base. Both sides. Expected effect: most of the raid `refuel` idle (85% of idle samples) turns into sorties.
2. **Overfill when no free job is feasible** (design, S; Q-TD-89, NX-465). A free job the unit can't fly (ring or reach) must not suppress overfill on the full ones. Also a harness label that tells "ring, others full" apart from a real lockout (tooling, S; `metrics`).
3. **Read Q0/Q1** for Q-TD-79 as one global decision; their sha has no NX-462 metric. Overnight-0 and quiet-5 were not in Q0/Q1, so a same-sha low-population pair follows if Q1 favours "on".
4. **Re-run P2 at the Q0/Q1 sha** (tuning; Q-TD-90): prime-50 + raid-300, 24 h, 6 seeds, B + `director.staging.max_wait_windows=30`, plus strike-first per Q1.
5. **Hold clock pauses under pressure** (design, S–M; Q-TD-84 (b), NX-466). Keep `campaign.victory_hold_min` at 30.
6. **Build Q-TD-83 (a)** (NX-457). Mark (c) falsified, and keep `director.pol.offensive_period_s` at 21600.
7. **Optional upper-bound probe** (tuning): raid-300 + prime-50, B + `logistics.starved_loadout.fuel_frac=1.0`, 24 h, 6 seeds. It measures what rec 1 is worth; watch west-airbase defense HP.
8. **Harness docs:** a short run is not a prefix of a long one (`profiles.py:163-177`). Probes use `--hours <long>` and stop early (L-39).
9. **Check the STAGING_DISPERSED wording** for fallback launches (narration, S).

### Watch items for PLAYTEST-WATCHLIST

- `refuel` above 50% of idle samples, with jets LANDED at a starved base.
- A free but unreachable job beside full reachable ones (ring idle while east-airbase defense HP is above 0).
- Holds with pressure events above 0 and 0 breaks.
- Static strikes fired on fewer than 10% of Offensives (P0 quiet: 0%).
- STAGING_DISPERSED above 2× STAGING_LAUNCHED.
- Seed-for-seed comparisons across different `--hours`.

### Owner questions (each with a recommendation; recorded as lead decisions, owner may veto)

1. Should an aircraft at a starved base, whose capped tank can't serve its job, rearm at the nearest unstarved base instead of waiting? **Recommend yes** (Q-TD-88).
2. Should overfill apply when every free job is infeasible for the unit? **Recommend yes** (Q-TD-89).
3. Should strike-first (Q-TD-79) depend on population or profile? **Recommend no** (Q-TD-79 note). Decide it globally from Q0/Q1; if raid still fails, put "operation strikes structure-first" to the owner as an EC-3 exception.
4. For Q-TD-84: pause the hold clock under pressure, or lengthen holds? **Recommend the pause**, and keep 30 minutes.
5. Should 5b take `director.staging.max_wait_windows=30`? **Recommend not yet** (Q-TD-90). Re-run at the SEAD sha first, and ship 90 if that run doesn't confirm it.
