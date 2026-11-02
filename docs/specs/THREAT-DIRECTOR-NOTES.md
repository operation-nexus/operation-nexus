# NOTES: Threat Director (Enemy AI)

Not normative; THREAT-DIRECTOR.md wins. This file holds the implementation narration, code map, history, decision trails, examples and derived numbers moved out of THREAT-DIRECTOR.md (NX-415, W6), verbatim. Headings use THREAT-DIRECTOR.md's numbers; each entry names the source paragraph by its bold label where it has one.

## 4. Decision loop (every 60 s of game time, `director.window_s`, Q-ALN-23)

- (from step 2) The per-tier budget and live-unit caps are gone (NX-412; deleted from code and schema in NX-488).
- (from step 4) The noise is what makes it unpredictable but replayable.

## 5a. Pattern of Life (owner requirement, 2026-10-17)

- **Demand convoys (NX-473, Q-TD-92, GAMEPLAY §5 LC-2; lead decision, owner may veto; in code: `launch._pattern_of_life` and `launch._convoy_slots`, on at the shipped `convoy_demand_s` 900, Q-TD-128; equal to `convoy_period_s` it is off, Q-TD-113).** *Before NX-473 (verified at e8fa215):* the convoy step runs after every window's operations at every tier (`launch.py:324`), but it fires only once per `director.pol.convoy_period_s` (3600 game s, `launch.py:448-450`), and it sends `convoys_per_period` (1) convoys of `convoy_slots` (1) trucks. Its shortfall already counts a base below its floor (`operations.py:648-659`, Q-SIM-86), not only a missing garrison, so the limiter is the period, not the trigger. *Start value (derived, to tune):* `convoy_demand_s` 300 (5 windows), the harness sweep's first candidate; it ships at 3600, equal to the period (Q-TD-113). The rear source to east-airbase is 15 + 70 = 85 km of road, 3,400 world s at 25 m/s, ≈ 9.4 game min at `sim.time_scale` 6. So a starving east-airbase gets a convoy dispatched within 300 + 60 game s and its stock about 15–16 game min after it fell below the floor (when the convoy loads at the rear), against up to 60 + 9.4 min today. Q-TD-92's probe of `convoy_period_s` 900 needs that key's tune bound (min 1800) lowered through add-config-key.
- **Scout intercepts (Q-SIM-96, NX-382; in code).**
- Status labels moved out of THREAT-DIRECTOR.md (the rules after each stay there): **In code now (NX-382 part 2):**

## 5b. Active defense (owner, 2026-10-26, NX-424; Q-TD-44)

- **Seams in code today (for the builder; read-only facts).**
- The scout intercept is the model. `tasking_gen.watched` picks the tracked contacts near held nodes and reads the truth only for liveness (`services/sim/src/nexus/core/tasking_gen.py:196-209`). `tasking._watch` keeps its clock in `World.intercept_seen` before each Static pass (`tasking.py:404-405`, `tasking.py:423-427`). `tasking_gen._intercept` posts `intercept:<entity>` once the wait has passed (`tasking_gen.py:499-512`).
- A chase follows the side's track, never the true position, and releases a garrison claimant past its leash (`tasking.py:539-569`, `_in_leash` and `_chase`). The job ends DONE on a kill, else EXPIRED when lost or out of range (`tasking.py:572-581`, `tasking.py:651-655`). At its end an aircraft stops where it is (`tasking.py:700-701`).
- DEFEND is generated for a held, capturable node with a tracked enemy GROUND unit inside `tasking.defend_radius_m` (10,000 m, `balance/default.yaml:177`), with no armed or closing test (`tasking_gen.py:382-404`). It ends DONE when a claimant stands at the node and the node is no longer menaced, FAILED when the node is lost (`tasking.py:600-626`).
- A garrison unit (`Entity.home`, `world.py:328-330`) is given only a DEFEND of its home or an intercept within its leash (`tasking.py:897-908`). An idle garrison unit away from its home is sent back at the next decision window (`launch.py:803-814`). An operation never reuses a garrison unit (`launch.py:817-822`).
- "Idle" for the board means no job, no order, no path, not Disabled, not RTB, not grounded (`tasking_gen.py:212-219`). Assignment takes idle units in id order, best job first (`tasking.py:911-937`).
- The coalition's AI garrison in code today is its facilities only: setup spawns them as `AI_GARRISON`, STATIC domain (`services/sim/src/nexus/runtime/campaign_config.py:243-254`). The Static's garrison is mobile and homed (`campaign_config.py:225-240`). The coalition has no mobile AI unit yet.
- (from **AD-1 Threat (G1, owner rule).** item 4) Today both painter kinds are unarmed (`content/units/recon-uav.yaml:20`, `content/units/enemy-recon-uav.yaml:20`), so rule 2 already excludes them. Rule 4 keeps an armed painter added later from drawing two jobs.

## 7a. In code now (Parts 1 to 5, NX-151, NX-155, NX-156, NX-157, NX-379, NX-401; Q-SIM-78, Q-SIM-81, Q-SIM-85, Q-SIM-87, Q-SIM-120, Q-SIM-121)

- ECONOMY ([ECONOMY](ECONOMY.md)) is approved and lands in parts (NX-412); what follows describes the code as it is. The old tier budget and live-unit caps, and the temporary switch that kept them, were deleted in NX-488 (Q-TD-33).
- **In code (NX-412 part 1): source pools (ECONOMY EC-1, EC-2, EC-15).**
- **In code (NX-412 part 3): budget, guard and the one spawn rule (ECONOMY EC-7, EC-8, EC-13; Q-TD-33).**
- **In code (NX-412 part 4): the contested victory hold (ECONOMY EC-9, EC-12; Q-TD-19, Q-TD-25).**
- **In code (NX-416): forward staging (§4a FS-1 to FS-7; Q-TD-36, Q-TD-37, Q-TD-38).** The pure parts are `nexus.core.staging`, the flow is in `nexus.core.launch`.
- **In code (NX-430): the victory-hold response (§4a FS-10; Q-TD-46).**
- (from **Interpretations (lead, owner may veto).**) (5) Retired in NX-488 with the old rules it concerned.
- **In code (NX-431): payoff sitreps (§4a FS-9; Q-TD-47, Q-TD-56).** Protocol 0.44 adds three `ThreatAdaptation` categories and `credit_ids`; snapshot format 33 adds `Staged.sector`, `Job.downed_by` and `Job.downed`.
- No `STAFF_DIRECTOR_OVERRIDE`, advisor or GM exists. Part 2 is the next subsection, then Part 3 and Part 4 (NX-379).
- (from **Load checks.**) On strait-1 offensives fail at the strike step (jets lost to air defense or too few rounds); left to balance.
- (from **Visit memory.**) Without it an empty cell stays 'unseen' however often a scout loiters there and the same cell is picked every window (6 distinct points in 6 game hours); with it the scouts spread over the sector.
- **Known, not changed.** A 6 h QA run saw one 127.8 ms tick (p99 0.79 ms), not reproduced; tracked under NX-376.
- **Measured** (0 viewers, shipped config, 6 game hours, same seeds): see `services/sim/tests/golden/README.md` (snapshot format 22).
- Status labels moved out of THREAT-DIRECTOR.md (the rules after each stay there): **In code (NX-413):**

## 8. Open questions

- Decided and folded in: Q-GD-4 (amended), Q-GD-22, Q-GD-30, Q-GD-34, Q-GD-37, Q-AI-7, Q-AI-8, Q-AI-9, Q-RB-6, Q-RB-7, Q-OPS-8, Q-OPS-9, Q-CFG-8, Q-BRAND-4, Q-ALN-2, Q-ALN-3, Q-ALN-4, Q-ALN-10, Q-ALN-11, Q-ALN-12, Q-ALN-13, Q-ALN-17. Decided and folded in (2026-10-18, second batch): Q-ALN-23 (game time for the director's timers, TD-1), Q-ALN-24 (director overrides rejected while paused, TD-1). Decided and folded in (2026-10-18, third batch): Q-ALN-35 (CHARLIE warning lead time on game time, §3, TD-1), Q-ALN-36 (advisor choices and GM commands rejected while paused, TD-1), Q-ALN-42 (crowd profiles, §1). Decided in the 2026-10-19 grilling: Q-TD-1 to Q-TD-10 (OPEN-QUESTIONS, "THREAT-DIRECTOR grilling").
