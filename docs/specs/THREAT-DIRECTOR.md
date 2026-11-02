# SPEC: Threat Director (Enemy AI)

Status: Approved (owner, 2026-10-19) · Tracker: NX-155…NX-169, NX-309, NX-317 · ADR-0007 · Inputs: P63–71, C14–39

Rules only. Narration, history, decision trails, examples and derived numbers: [THREAT-DIRECTOR-NOTES.md](THREAT-DIRECTOR-NOTES.md) (not normative). One section: `python3 scripts/spec_section.py docs/specs/THREAT-DIRECTOR.md <number or title>`.

## 1. Purpose

1. Keep every population level (the harness crowd profiles of 0, 5, 50, 150, 300 and 500 viewers, Q-ALN-42) interesting and fair, with an enemy that seems to adapt but stays deterministic and testable.

## 2. Inputs (enemy view only, FOW-4)

1. **Coalition power** `CP` = Σ over currently tracked coalition units (last-known tracks feed only Recon utility, TD-5; Q-FOW-14) of the unit's value, smoothed with an EMA over `director.cp.ema_window_s` (PROPOSED 300 s, game time, Q-ALN-23).
2. Only sensed facts count: no supply readiness and no account age (Q-TD-2); alt-account abuse is handled by moderation outside the sim.

3. Frontline state, node ownership, and enemy stockpiles.

4. **Threat memory:** decaying counters per category: `convoy_attacks`, `radar_strikes`, `node_losses_by_sector`, `recon_losses_by_sector` (`sead_activity` joins with SEAD in P4).
5. The half-life is configurable (`director.memory.half_life_s`, default 30 min of game time, Q-ALN-23).

## 3. Tiers (with hysteresis; replaces overlapping headcount bands)

| Tier | Enter when CP ≥ | Exit when CP < | Character |
|---|---|---|---|
| PATTERN_OF_LIFE | — | — | Routine only: Recon, EscortConvoys, DecoyBlink and repositioning (DEFEND jobs at its own bases); Offensive only under the night progress cap (§5) |
| ALPHA | `director.tier.alpha_enter_cp` (0) | `alpha_enter_cp × exit_ratio` | Patrols, probes, supply maintenance, at most `director.max_ops.alpha` (1) operations at a time (the due cadence floor's capture operation may run one past it, ECONOMY EC-7, Q-TD-57) |
| BRAVO | `director.tier.bravo_enter_cp` | `bravo_enter_cp × director.tier.exit_ratio` (PROPOSED 0.8) | Concentrated offensives on weak sectors, IADS with overlapping SAMs |

1. **Escalation rule (Q-TD-1): provocation decides when, coalition power decides how far.**
2. Provocation (§5a) maps to a level: ≥ `director.provocation.escalate_threshold` = ALPHA, ≥ `director.provocation.bravo_threshold` = BRAVO, otherwise Pattern of Life; a level drops only when provocation falls below its threshold × `director.tier.exit_ratio` (the same hysteresis as CP).
3. The config loader requires `bravo_threshold > escalate_threshold`.
4. CP maps to a ceiling by the table above.
5. Each decision window the tier moves **at most one step** (default; Q-CFG-16 option `director.tier.max_step`) toward min(provocation level, CP ceiling), and only after the minimum dwell.
6. A campaign starts in Pattern of Life (default; Q-CFG-16 option `director.tier.start`: a higher start has dwell 0 and the usual starting levels, so without provocation it settles back after one dwell; no `ThreatTierChanged` is emitted at campaign start, so a client that shows the tier reads it from the snapshot, not from the first event).

7. **CHARLIE is parked (Q-TD-3):** the named, telegraphed theater offensive (Q-GD-22, Q-ALN-35) waits for a larger roster and theaters; its rules are in GAMEPLAY-LATER.

8. There's a minimum dwell of 10 min of game time per tier (`director.tier.min_dwell_s`, Q-ALN-23).
9. Tier changes are announced on the overlay and in a sitrep.

## 4. Decision loop (every 60 s of game time, `director.window_s`, Q-ALN-23)

1) Compute CP and the tier, and decay threat memory.
2) Budget for this window (ECONOMY EC-7, Q-TD-24, Q-TD-26): from the spend fraction of the Static bases' surplus stock (`director.spend_frac.<tier>`), plus a small share of the rear pool (`director.source_spend_frac`, spent on EC-13 terms), less the upkeep reserve (`director.upkeep_reserve_windows`), with a cadence floor (`director.cadence_windows`), never more than surplus plus rear pool.
   Every operation costs budget once; GP-7 only decides where its units spawn.
   **Guards (EC-8, Q-TD-12):** `sim.max_live_units_per_side` is a tick-rate guard only, and `director.max_spawns_per_window` stays as anti-spam.
   Raiding its convoys, stock or factories still starves the director (factories are parked, Q-GP-41).
   Formula, rear pool, reserve and cadence floor: [ECONOMY](ECONOMY.md).
3) Generate candidate **operations** from the operation catalog (`content/operations.yaml`, CONFIG-AND-CONTENT §8a; Q-TD-7): Probe(sector), Recon(sector), Offensive(node), Retake(node), EscortConvoys(route), ReinforceIADS(sector) (first build: repair existing air-defense sites past Disabled; emission is DecoyBlink's; building new ones waits for GAMEPLAY-LATER §5a, Q-GP-46), StrikeBridge(node: a bridge on the coalition's lifeline, NX-401, §7a Part 5), DecoyBlink(radar).
   (TheaterOffensive waits with CHARLIE, Q-TD-3.)
   Each candidate has a cost and preconditions.
4) Score each candidate (Q-TD-6) = `director.op_priority.<op>` × target-value multiplier (`director.score.target_value.<node_kind>`, TBD) × weakness multiplier (from the target's defense-HP fraction as last seen in the enemy view; TBD curve) × threat-memory multiplier (`1 + counter` for the operation's matching counter, 1 when none matches) × proximity multiplier (Q-TD-4, below) × `director.score.victory_hold_mult` (Offensive and Retake on a node in a running victory hold, EC-9) × `director.score.income_node_mult` (Offensive and Retake on a coalition-held node that yields income, EC-12) + a `director` RNG noise term; tuned in the harness, refined in playtests.
   **Order (determinism):** candidates are enumerated sorted by (operation id, target id), one `director` draw is made per candidate in that order, and selection is greedy by (score descending, operation id, target id) within the budget.
5) **Adaptive defense (C37):** each threat-memory counter raises the utility of the matching defensive operation.
   Convoys are sent with no escort at first, then escorts appear as `convoy_attacks` grows, and drop away again as it decays.
   Each adaptation is announced with an INTEL line, at sector level only: it never names a site or updates a facility marker, so it reveals intent, not positions or states (Q-FOW-17, FOG-OF-WAR FOW-13).
6) Select within budget.
   Optionally, the LLM advisor picks among the top-K (§6).
7) **Spawning (Q-TD-8):** units bought from the budget spawn by the coalition's rule (GAMEPLAY GP-7, parity) for location only; their cost is the operation's budget, never a second charge, drawn once from the stock of the node where they spawn (ECONOMY EC-13): at the Static base nearest the job whose stock exceeds its starvation threshold by the forward-deploy margin, otherwise at the rear source behind its HQ.
8) **Turn operations into jobs** (Q-GD-34, Q-GD-37): the director is the strategic layer only.
   It never moves units directly (exception: `DecoyBlink` sets a site's emission flag directly; it is not a job, FOW-11); each selected operation becomes the jobs its **template** lists (Q-TD-7; e.g. Offensive(node) = stage at the nearest Static base, then strike the node's defenses, then send ground units to capture; EscortConvoys = a follow order on each convoy) on the Static's own Tasking Board (GAMEPLAY §1b), and Static units take them with the same mechanics as Quorum units: claim leases, feasibility check, priority aging, slots and dedupe keys, deterministic assignment order, job dependencies (Q-GD-37).
   Parity: the Static gets the same job types and mechanics, with no unique powers; only the director may compose them into richer combinations.

9. **TD-1 (time and pauses, Q-CFG-8, Q-OPS-8, Q-OPS-9, Q-ALN-2, Q-ALN-3, Q-ALN-23, Q-ALN-24, Q-ALN-35, Q-ALN-36):** every director timer runs inside the sim.
10. These are **game time** (Q-ALN-23): the decision window (`director.window_s`), tier dwell (`director.tier.min_dwell_s`), the CP EMA window, the threat-memory and provocation half-lives, the PoL periods (`director.pol.*_period_s`) and the night-progress cap (`campaign.night_progress_cap_nodes_per_h`, per game hour).
11. The advisor deadline is counted in decision windows, so it is game time too.
12. Static units carrying out the director's jobs move in world time, like every unit.
13. While the campaign is paused for any reason (`STAFF`, broadcast offline `TECHNICAL`, weekly `MAINTENANCE`, owner `CEASEFIRE`), none of them advances and the director makes no decision (SIM-CORE SC-11).
14. A `STAFF_DIRECTOR_OVERRIDE` sent while paused is rejected with `CAMPAIGN_PAUSED` (Q-ALN-24), as are advisor choices and GM commands other than a GM release (Q-ALN-36).
15. Taunt naming cooldowns (TD-4) and the GM idle auto-release (§6a) are **not** sim timers: they run on a monotonic real clock outside the sim (Q-ALN-4).

16. **TD-2 (own view only, FOW-4, Q-GD-37 item 9):** CP, provocation, candidate generation, scoring and the jobs the director posts are computed only from `EnemyView` (plus what the Static suffers).
17. Operation-template selectors resolve against `EnemyView`, using discovered markers for facilities (FOW-13); a selector that resolves to nothing drops the operation.
18. The Static's board never holds a job that targets or references an entity outside that view.

19. **TD-5 (scouting, Q-SIM-11, FOW-10):** `Recon(sector)` is an ordinary operation.
20. It becomes jobs for ordinary ENEMY recon units (`ENEMY_RECON_UAV`, Q-TD-13) under parity (GAMEPLAY §0), paid from the same window budget, visible to viewers and killable.
21. It adds no information beyond what those units' sensors detect, so the director's picture of a sector improves only while a scout lives.
22. Its utility rises with the age of the director's last-known tracks over the sector (FOG-OF-WAR FOW-6a) and falls with recent scout losses there (threat memory), plus the `director` RNG noise term like any candidate.
23. **A Recon operation targets a point, not a node (NX-379, Q-SIM-87):** the stalest cell of the sector's grid (`director.recon.grid_m`), where the Static's last-known picture is oldest or missing, that lies outside every known coalition air-defense ring whose last confirmed state is not Disabled, with a straight route from the base the scout is raised at that crosses none (the TB-2 test, GAMEPLAY §1b); no such point drops the sector that window, as an unresolved selector does.
24. The scout loiters at the point for `director.recon.loiter_s` within `director.recon.loiter_radius_m`, then goes home.
25. It reads the Static's view and discovered markers only.

Notes: THREAT-DIRECTOR-NOTES.md §4

## 4a. Forward staging (owner, 2026-10-25, NX-416; Q-TD-36, Q-TD-37, Q-TD-38)

1. The Static stages a ground attack at a forward base and projects it from there, instead of marching every capture column from its rear source.
2. Viewers see the threat build: convoys run forward, units mass, then the attack goes in.
3. The coalition can raid the staging base or its convoys to blunt it.
4. It builds on ECONOMY EC-7 and EC-13.

**FS-1 When to stage.**
5. An operation with a CAPTURE job (Offensive, Retake) on target T is staged when its capture kind's road travel time from the rear source to T exceeds `director.staging.direct_s`.
6. Otherwise it spawns as EC-13 says.

**FS-2 Staging base.**
7. The staging base is the Static-held node, not a BRIDGE and with no capture bar, that can host the capture kind (EC-5 domain hosts) and has the shortest road travel time to T.
8. Ties are broken by node id.
9. If no held node is closer to T than the rear source, the operation is not staged.

**FS-3 Stocking.**
10. While an operation is staged, the staging base's forward-stock target (GAMEPLAY §5, Q-SIM-100) is raised to the cost of the operation's units that spawn there plus the base's starvation floor.
11. The existing resupply jobs and the Director's convoys then carry stock there, and convoys prefer it.
12. Nothing is teleported: stock moves only on trucks (Q-GP-16).

**FS-4 Launch.**
13. Each unit's cost is drawn only at the node it spawns at (EC-13; owner, Q-TD-38): never at a base the unit does not spawn from.
14. The units of a kind the staging base can host spawn there and are paid there; a kind it cannot host (aircraft at an FOB) spawns as EC-13 says (`plan_deploy`'s base, else the rear source) and is paid at that node.
15. A staged operation launches whole when every node it spawns at can pay for its own units; until then it waits.
16. It waits at most `director.staging.max_wait_windows` decision windows; after that it launches by EC-13 from any node that can pay (the source included), or is dropped.
17. At most `director.staging.max_staged` operations are staged at once.
18. A staged operation counts against `director.max_ops.<tier>` and holds its budget share while it waits.
19. While the night cap (§5) bars capture operations, a staged one does not launch: it keeps waiting and its wait keeps running, so when the wait runs out under the cap, or it would fall back (FS-6, FS-10), it is dropped (NX-480).

**FS-5 Projection.**
20. When staging starts, the Director emits `ThreatAdaptation{STAGING}` for the staging base's sector, at sector level only, never naming the base (FOW-13): "NULL forces are massing in <sector>".
21. Units and convoys are seen only through fog of war, as any unit is.
22. A re-stage (FS-6) emits the sitrep again only when the coalition currently tracks a live Static unit at the new base (owner, Q-TD-38: limited announcements under fog of war) and no massing sitrep is still open for that sector (FS-9).

**FS-6 Losing the base.**
23. If the staging base is captured or contested, or its stock is raided below the cost when the wait runs out, the operation re-stages at the next base by FS-2 (the wait does not reset) or falls back by FS-4.

**FS-7 State and determinism.**
24. Staged operations (operation, target, base, start window) live in `DirectorState`, in the snapshot and hash.
25. Candidates and bases are taken in id order.
26. No new RNG draws.

**FS-9 Payoff sitreps (owner, Q-TD-47, Q-TD-56; NX-431).**
27. Every massing sitrep (FS-5) is followed, once, by a payoff in the same sector, at sector level only (FOW-13): `ThreatAdaptation{STAGING_LAUNCHED}` "NULL assault launching from <sector>" when the staged operation launches from its staging base, or `ThreatAdaptation{STAGING_DISPERSED}` "massing disperses" when the massing ends any other way (dropped, timed out, fallen back to the rear, or re-staged where the coalition sees nothing or in another sector).
28. A massing the coalition was never told about gets no payoff.
29. When a viewer unit's hit destroys, disables or mission-kills the last unit of a Static STRIKE job still in the fight, `ThreatAdaptation{STRIKE_DOWNED}` "NULL strike package downed near <node>" is emitted on that tick, once per job: it names the job's target node (nodes are public, FOW-10) and its sector and credits every viewer unit that downed one of the job's units (`credit_ids`).
30. A package with a survivor that turns home, finishes, or is still on the job when it expires gets no sitrep (lead, 2026-10-27).

**FS-10 Victory-hold response (owner, Q-TD-46; NX-430).**
31. While a coalition victory hold runs (ECONOMY EC-9), the Static skips staging and may launch capture operations at once, from the rear if needed, outside the `director.max_ops.<tier>` cap.
32. In code this applies to a capture operation (Offensive, Retake) aimed at a node of the hold (`SideView.hold`): it never waits at a staging base: when FS-1 and FS-2 give a base and that base pays its units now, it launches from there at once, with no `STAGING` or `STAGING_LAUNCHED` sitrep; otherwise it launches by EC-13 at once (the deploy base, else the rear source: the rear only if needed).
33. One already staged when its target enters the hold waits no longer (it launches from its base if that pays, else by EC-13, else it is dropped, closing its massing as FS-9 says).
34. It is outside the cap as a routine operation is: neither capped nor counted.
35. The window budget, the spawn and live rooms, one operation per (operation, target) and the no-viewer night cap (§5, Q-SIM-86) still apply.
36. Its launch announces `HOLD_AT_RISK` as any capture launch on a hold node does; no new sitrep (Q-TD-64).
37. When the hold ends, hold-response operations still running count against the cap again and can block ALPHA's slot, the floor's one over included (Q-TD-57), until they finish; this is accepted for now and the NX-412 sweep measures it.

**FS-8 Tunable (EC-14).**
38. `director.staging.direct_s`, `director.staging.max_wait_windows` and `director.staging.max_staged` are balance keys with full registry metadata and sweep ranges.

**Parity (GAMEPLAY §0).**
39. Staging composes existing mechanics: forward stock, convoys and the one spawn rule.
40. The coalition stages the same way when players haul stock forward.
41. The Director composing it is allowed by Q-GD-34; no new unit power.

## 5. Low-population behavior

1. At 0 humans, the coalition AI garrison holds the line and the Static drops to **Pattern of Life** (§5a); the campaign clock keeps running: it never pauses for lack of humans (Q-GD-4 amended); only a pause with a reason stops it (TD-1, Q-ALN-3).
2. With 0 humans the Static can never take the coalition's `forward_airbase` or bring the sanctuary below 1 defense HP (GAMEPLAY §9, Q-GP-28).
3. Enemy progress is capped at `campaign.night_progress_cap_nodes_per_h` (PROPOSED 1 node per 6 h of game time, Q-ALN-23).
4. **"No humans" means no live viewer unit, the same test as the idle floor (Q-GP-44, Q-SIM-85).**
5. Every Static flip stamps `DirectorState.last_flip` (in the snapshot and hash), with or without viewers (Q-SIM-86).
6. While there are none (fading with viewers, see the low-population brake below), a Static capture flip is allowed only if none happened in the last 1 ÷ the cap game hours; until then the capture bar holds one step short of the flip, the node is recorded in `DirectorState.held`, and the Director launches no capture operation.
7. **A held bar stays held until the cap frees, even if a viewer arrives**, so a new viewer does not see held bases fall at once (§5a: 0 to 1 viewer changes nothing until that operator acts); coalition units can still contest it as any bar, and it leaves `held` when it is gone or drained.
**Low-population brake (Q-TD-93, NX-474).**
8. The cap does not end at the first viewer unit: its spacing fades linearly from the full 1 ÷ the cap hours at 0 viewer units to none at `capture.quiet_ref` (50), `night_cap_ticks x (quiet_ref - min(v, quiet_ref)) // quiet_ref` ticks for `v` live viewer units (`director.night_spacing`, integer, floored; no new key).
9. Between 1 and `quiet_ref - 1` viewer units a flip inside that spacing is held and the Director launches no capture operation inside it; from `quiet_ref` on there is no cap, but every flip still stamps the clock.
10. A bar already held stays held until the full 0-viewer cap frees, even when viewers (a crowd of `quiet_ref` included) arrive (Q-SIM-86); a bar that reaches the flip inside the faded spacing is held, so it then waits the full cap.
11. The coalition's last strategic node, whichever it is (the forward airbase or a FOB), also holds, at any viewer count, while it is the only strategic node the coalition owns (GAMEPLAY §0, Q-GP-28, Q-TD-103): no bar starts or fills there, but a running Static bar decays or is drained as usual; the sanctuary's last HP is unchanged.
12. While the CP ceiling is ALPHA, a proximity multiplier (`director.score.provocation_proximity`, TBD) favours operations in `last_provocation_sector` (director state, in the snapshot and hash; the sector of the most recent provocation the Static sensed, ties broken by sector id), so a lone viewer harassing one sector gets a local fight there while the rest of the map stays calm (Q-TD-4; never by headcount, TS-1).

## 5a. Pattern of Life (owner requirement, 2026-10-17)

1. When nobody is playing, **and when viewers first arrive**, the Static mounts no offensives beyond the night progress cap (Q-GP-44).
2. It runs a believable **Pattern of Life (PoL)** that scouts can observe and learn from:

3. **Routine scouting (Q-TD-2 owner note):** even with no provocation, the director keeps sending Recon operations (TD-5) on a PoL cadence, so it is always looking.

4. **Maintenance only, never a swarm (Q-TD-11 owner note):** at Pattern of Life the director only replaces losses up to each base's garrison quota from the theater file (`garrison_quota` per base); it never grows its force net, however long the war is quiet.
5. Its convoys at Pattern of Life carry only what that upkeep needs.

**Garrison upkeep (Q-SIM-85).**
6. A routine catalog operation (`GARRISON_UPKEEP`, every tier, outside `director.max_ops.<tier>`): a Static base with fewer live `ENEMY_DIRECTOR` units homed there (including any away on jobs) than its `garrison_quota` gets one replacement per window, raised at the base, paid from surplus like any operation.
7. **The bases start the campaign at their quota** (free, homed, the default kinds in turn, as part of setup; Q-SIM-86), so early viewers do not find empty bases.
8. The kind comes from `director.garrison.kinds.<node kind>`, used round-robin; `director.garrison.replace_per_window` (1) units are bought per short base per window.
9. Retirement (Q-SIM-84) takes only units above their home base's quota, highest id first, so a garrison sitting at its base is never churned.
10. **A garrison unit defends its own base** (the board gives it a DEFEND of that base, e.g. against a capture bar) **and nothing else by itself**: no other board job, and an operation never reuses it.
11. Only the Director sends it away, for a patrol; an idle one away from its held home is sent back (Q-SIM-86).
12. Default kinds: AIRBASE ENEMY_FIGHTER and ENEMY_ARMOR in turn, HQ and FOB ENEMY_ARMOR; a garrison kind must be raised at its base kind and an aircraft needs a landing base (the loader refuses the rest).

**Patrols (Q-SIM-85).**
13. A `PATROL` job on the Static's board.
14. Every `director.pol.patrol_period_s`, each Static base with idle ground garrison units homed there posts patrols until `director.pol.patrols_per_base` (1) are out: out to the base's road neighbour toward the frontline (the nearest node within `director.frontline_hops` hops that the Static does not hold, neutral or not; never a node the coalition holds; with no front in reach, the nearest such neighbour), then home; DONE on return.
15. A garrison unit (one with a home base) and a unit on a PATROL job never start or advance a capture bar (Q-SIM-86): a garrison only defends, so a patrol can turn at a neutral node.
16. A patrol that fails (its home or turning node is lost) sends its unit to the nearest friendly base; with no route that avoids the coalition's nodes the unit stands, and it retires once idle.
17. A job takes `director.pol.patrol_slots` (1) units.
18. Patrols are the visible garrison rotation; no separate rotation is built.

**Convoys (Q-SIM-85).**
19. Every `director.pol.convoy_period_s`, up to `director.pol.convoys_per_period` (1) `RESUPPLY` jobs, loaded by the usual reload rule (GAMEPLAY §1b, Q-GP-24: the nearest Static base with stock above its floor, the rear source only when none has; NX-389, Q-SIM-102: on a run to a base that is not starving, has no damaged facility and is below its forward stock target, a source counts only its stock above its own target, so such a convoy usually loads at the rear source), one each to the Static bases with the largest upkeep shortfall (the cost of its missing garrison units plus the floor less its stock, so a base below its floor counts too; Q-SIM-86); none when no base falls short.
20. A truck carries at most `logistics.truck_cargo`.
21. A new carrier costs `director.pol.convoy_cost` (0) from the surplus; the stock it moves is accounted as cargo.

**Demand convoys (NX-473, Q-TD-92, GAMEPLAY §5 LC-2; lead decision, owner may veto; on at the shipped `convoy_demand_s` 900, Q-TD-128; equal to `convoy_period_s` it is off, Q-TD-113).**
22. *Rule:* the step is also due when some Static base the Director owns is below its starvation floor and `director.pol.convoy_demand_s` has passed since `DirectorState.last_convoy`.
23. It then runs as now: the `convoys_per_period` bases with the largest shortfall, a staging base first (FS-3), and it stamps `last_convoy`.
24. So while a base starves, the effective period is `convoy_demand_s`.
25. Equal to `convoy_period_s`, the rule is off.
26. *Caps (all existing):* one live POL convoy job per base, `convoys_per_period` per firing, `max_spawns_per_window`, the live room (EC-8), and `convoy_cost` from the surplus.
27. A base no truck can reach gets none (NX-413).
28. *Trucks per convoy:* the GAMEPLAY §5 LC-3 cap with base `convoy_slots`, so a starving base's convoy carries about its shortfall, rounded up to whole trucks.
29. That keeps the owner's "convoys carry only what that upkeep needs" (Q-TD-11 note): the convoy restores the floor and grows no force.
30. *Not gated by the night cap or the quiet brake* (NX-474): a convoy is no capture operation.
31. *Determinism:* no new state or RNG; bases by shortfall then node id, as today.
32. Raised above `convoy_slots`, a convoy's truck count shrinks to the spawns and live room left (never below `convoy_slots`) instead of skipping the base (PR #514).

**Night progress (Q-SIM-85).**
33. At Pattern of Life (default; Q-CFG-16 option `director.pol.capture_slot_tiers`) the Director may launch up to `director.pol.offensives_per_period` (1) capture operations (any catalog operation with a CAPTURE job: Offensive, Retake) per `director.pol.offensive_period_s`, outside the window budget but paid from the real surplus, and never while the night cap (§5) is spent.

**No offensives from the board (Q-SIM-85).**
34. The Static's board generates STRIKE jobs against discovered sites only from `tasking.static_offense_min_tier` (ALPHA) up; at Pattern of Life it still posts DEFEND, RESUPPLY (including stocking jobs while it has a live carrier, NX-389), scout and the Director's PATROL jobs, and the Director's own operations (the capture slot) post their jobs themselves.
35. The coalition's board is not gated.

**Scout intercepts (Q-SIM-96, NX-382).**
36. The Static hunts coalition scouts it can see, but not instantly.
37. When the Static's view (TD-2, FOW: tracks only, never ground truth) holds a coalition aircraft of a painter kind within `director.intercept.radius_m` (PROPOSED 30,000 m) of a Static-held node, continuously for `director.intercept.reaction_s` (PROPOSED 60 game s) at ALPHA and above, or for `director.intercept.pol_linger_s` (PROPOSED 600 game s) at Pattern of Life, its board posts `intercept:<entity>` for armed AIR units that can hit it, priority `tasking.priority.intercept` (PROPOSED 45: below DEFEND 60, above STRIKE 40), slots `tasking.slots.intercept` (PROPOSED 1).
38. Interceptors are ordinary Static units that launch from a base, so a scout that leaves in time escapes.
39. A garrison fighter (one with a home, Q-SIM-85) may take an intercept within `director.intercept.leash_m` (PROPOSED 80,000 m) of its home and returns home after; this is the one exception to garrison units taking only DEFEND jobs at home.
40. The job is done when the scout is destroyed, has not been tracked for `director.intercept.lost_s` (PROPOSED 120 game s), is no longer within the radius of any Static-held node, or has landed (EXPIRED like an escape: on the ground it is no AIR target, and a LANDED scout is not watched, COMBAT CB-7, Q-MV-14; NX-450).
41. **An intercept never adds provocation** (only people provoke, Q-TD-11): a scout flying in is not an escalation, only what its commander does (THREAT-DIRECTOR §5a).
42. The job's lifecycle events (`JobCreated`, `JobClaimed`, ...) are what the overlay can call out ("BANDITS SCRAMBLED"); the callout itself is OVERLAY work.
43. Key `intercept:<entity>` (`JobKind` `INTERCEPT`, `Job.entity` the scout, `Job.pos` the Static's track of it, `JobCreated.entity_id`), urgency 1.0, `tasking_gen._intercept` (NX-382 part 2).
44. Interpretations: the reaction clock is `World.intercept_seen` (scout id to the board pass that first saw it), updated at every Static board pass, so continuity is sampled each `tasking.reeval_every_ticks` and the clock starts at the first pass that sees the scout; an untracked pass, a last-known track or a track outside every held node's radius drops its entry and the wait starts over; the wait is read at posting, by the tier then (ALPHA's reaction up, Pattern of Life's linger below).
45. "A painter kind" is `rules.painters` aircraft (the recon).
46. Interceptors are armed aircraft of any Static owner (the Director's units, garrison included) with a round of a weapon that reaches the scout's domain and default altitude band (`tasking_gen.can_hit`); a garrison unit's leash holds for the whole chase: it is checked against the scout's current track when the unit takes the job and at every board pass after, and a garrison claimant whose scout's track passes the leash is released (`JobReleased`) and stops, and the ordinary recall takes it home.
47. A scout that is gone or Disabled is never hunted (a liveness read of the truth, like the job's DONE; its contact stays tracked until sensing drops it), so a kill is not followed by a new job.
48. A taker flies to the track position (never the scout's true position, FOW), re-aimed each board pass; it is released to the board when the job ends, with its path cleared, and an idle garrison unit away from home is then recalled by the ordinary rule (Q-SIM-86).
49. Slots follow the ordinary rule, so with every job full a second fighter may overfill (`tasking.overfill_factor`).
50. Outcome: DONE when the scout is destroyed or Disabled (it needs an active claimant, else the usual EXPIRED), EXPIRED when the track is lost for `lost_s` (this holds for a claimed job; an unclaimed one is dropped as soon as its scout is no longer tracked, as no longer generated) (`Job.lost` is the tick it was first found untracked; a track's age is counted back) or its last track leaves every held node's radius; there is no FAILED.
51. Nothing in `provocation` counts an intercept: a shot by a Static unit at a coalition scout is not a provocation hit (the victim is not the Static's) and the job's posting, claiming and ending note nothing.

52. Radar on/off cycles are DecoyBlink (FOW-11; the proximity rule is already built, NX-156).

53. **Repositioning between bases:** staging aircraft and ground units toward forward bases, refuel/rearm stops.
54. Staging is how attacks are prepared, so a sharp scout can see an offensive coming (only within coalition sensor coverage or as SIGINT blobs, FOG-OF-WAR).

55. **Escalation is triggered by provocation, not headcount** (GAMEPLAY TS-1):

56. A decaying `provocation` score rises with coalition actions the Static **senses or suffers**: losses or damage to its units, convoys and facilities, node flips, recon of its rear only when its sensors track the scout, and channel-point redemptions (TD-2, Q-FOW-15: nothing unsensed counts).
57. **Only people provoke (Q-TD-11):** only actions by viewer units under player control count, plus redemptions; AI garrison, facility and AUTO actions add 0, so the Static never escalates against an empty stream.

58. **Redemption weights (Q-AI-9, Q-ALN-13):** every redemption type has its own weight, `director.provocation.weights.redemption.<type>` (admin-tunable).
59. There is **no offensive redemption class**: no redemption may deal damage (SUPPORT-REDEMPTIONS §4).
60. Classes: support (supply drop, respawn skip, reserve-queue jump) = small weight; cosmetic (color, ping, shoutout, spectacle) = 0.
61. Weight values are PROPOSED / TBD by harness.

62. PoL → ALPHA → BRAVO follows the escalation rule in §3 (Q-TD-1).

63. Going from 0 viewers to 1 changes **nothing** until that operator acts.
64. They get time to observe and plan.

65. With no provocation, the enemy decays back to PoL.
66. Night-progress caps still apply (§5).

67. Config keys (CONFIG §6.7, all PROPOSED / TBD by harness): `director.pol.patrol_period_s`, `director.pol.convoy_period_s`, `director.pol.offensive_period_s`, `director.pol.convoy_kind`, `director.pol.patrols_per_base`, `director.pol.convoys_per_period`, `director.pol.offensives_per_period`, `director.pol.convoy_cost`, `director.pol.convoy_demand_s` (PROPOSED, NX-473), `director.garrison.kinds.<node kind>`, `director.garrison.replace_per_window`, `tasking.static_offense_min_tier`, `campaign.night_progress_cap_nodes_per_h`, `director.intercept.radius_m`, `director.intercept.reaction_s`, `director.intercept.pol_linger_s`, `director.intercept.leash_m`, `director.intercept.lost_s`, `tasking.priority.intercept`, `tasking.slots.intercept`, `director.provocation.weights.*` (including `.redemption.<type>`), `director.provocation.half_life_s`, `director.provocation.escalate_threshold`, `director.provocation.bravo_threshold`, `director.op_priority.<op>`, `director.score.*`.
68. Routine Recon at Pattern of Life is scored like any operation; there is no separate cadence key.

Notes: THREAT-DIRECTOR-NOTES.md §5a

## 5b. Active defense (owner, 2026-10-26, NX-424; Q-TD-44)

Status: Draft (needs owner sign-off before code) · Tracker: NX-424 · Inputs: Q-TD-44 (G1 to G4 and the owner's "real threats only" rule), Q-SIM-96, Q-TD-46, ECONOMY EC-3, FOG-OF-WAR FOW-4 and FOW-8

**Purpose.**
1. A side's AI answers a real attack on one of its nodes with units it already has.
2. Fighters go after attacking aircraft; armor reinforces the node against attacking ground units.
3. Nothing is spawned and nothing is bought.
4. Viewers see a base fight back, so a strike on a Static base meets its idle fighters, and a careless strike package pays for it.
5. The Static and the coalition's AI garrison use the same rule and the same keys (G4, EC-3).

6. This section composes existing mechanics: the Static's Tasking Board, the scout-intercept job and leash (§5a, Q-SIM-96), DEFEND jobs (GAMEPLAY §1b) and the garrison recall (Q-SIM-86).
7. It adds no unit power (GAMEPLAY §0).
8. Values in this section are PROPOSED.
9. Readings marked "lead reading" are open below.

**AD-1 Threat (G1, owner rule).**
10. A *threat* to a side is an enemy unit that meets all of these at a board pass:

1) It is in the side's `SideView` as a current track (`Contact.age` is None, `world.py:368-378`).
   A last-known track, a SIGINT blob or a discovered marker never counts (TD-2, FOW-4).
2) Its kind is armed: it is in `rules.armed`, the kinds whose catalog lists weapons (`rules.py:1094`).
   It is the catalog, not the unit's live ammo, which is hidden state (as escorts read it, GAMEPLAY §1b, Q-SIM-76).
3) Its domain is AIR or GROUND.
   STATIC facilities never move, so they are never threats.
4) It is not a scout the intercept rule watches: a painter aircraft (`rules.painters`) stays under §5a only.
5) It is still alive and not Disabled: a liveness read of the truth, the same exception `watched` makes, so a wreck that stays tracked is not answered.
6) It is **closing** on a node the side holds (AD-2).

11. Unarmed units (scouts, trucks, convoys) never count.
12. A unit passing by, loitering or leaving is not a threat.

**AD-2 Closing (owner pick, 2026-10-26).**
13. Closing is measured per pair (enemy unit, node the side holds), only at board passes (every `tasking.reeval_every_ticks`, 50 ticks, `balance/default.yaml:149`):

14. At each pass, for each pair where the unit meets AD-1 rules 1 to 5 and its track lies within `director.defense.radius_m` of the node, the side records a sample (pass tick, range).
15. Range is the straight-line distance from the track's position to the node's position, in metres (`math.hypot`, as `held_within` and `_defend` compute it).

16. A pair whose unit is not tracked at a pass, is tracked only as last-known, or is outside the radius at a pass, loses all its samples.
17. The clock starts over (as the intercept clock does).

18. Samples older than the window are dropped.
19. The **window start** is the newest sample whose tick is at or before `now − reaction`, where `reaction` is `director.defense.reaction_s` in ticks, rounded up.
20. Every sample after it is kept.

21. The pair is **closing** at this pass when it has a window-start sample, so it was continuously in the radius for at least `reaction`, and `range_now ≤ range_start − director.defense.closing_min_m`.

22. `closing_min_m` exists so a unit circling the node at a steady range, or drifting by a few metres, does not count.
23. It is a proposed key (open question 1).
24. With it at 0 any shrink counts.

25. This is a sliding window (lead reading, open question 2): it compares the range now with the range `reaction` ago, so a unit that loitered for ten minutes and then edges in counts only once it has closed by the margin over the last `reaction`.

26. A unit closing on several nodes is one threat.
27. Its **target node** is the one with the smallest `range_now`, ties by node id.

28. Known limit, accepted by the owner's rule: a unit flying a straight line past a node closes during the first half of its pass.
29. It can become a threat before it turns away.
30. When it then leaves, an unclaimed job is dropped at once (AD-4), and a claimed one ends by the AD-5 rules.

**AD-3 Responders (G2).**
31. A responder is a unit of the side that is all of these:

**Owned by the side's AI.**
32. For the Static: `ENEMY_DIRECTOR`.
33. For the coalition: `AI_GARRISON` (open question 9).
34. A viewer's unit is never a responder.

35. **Idle by the board's test** (`tasking_gen.is_idle`), so it is not Disabled, not RTB, not grounded (ECONOMY EC-6) and holds no job.
36. Units on an operation's job (STRIKE, CAPTURE, ESCORT_CONVOY, RESUPPLY, SCOUT, PATROL, INTERCEPT) are never pulled off it.
37. A unit holding an arrived STAGE claim is the open case (open question 4).

**Within its leash, if it has a home.**
38. A garrison unit responds only when the anchor point lies within `director.defense.leash_m` of its home.
39. For an air threat the anchor is the threat's track (checked when it takes the job and at every pass after, as `_chase` does for intercepts).
40. For a ground threat the anchor is the target node (fixed, checked when it takes the job).
41. A unit with no home has no leash, as `_in_leash` reads it today (open question 5).
42. Its own feasibility rules still bound it (fuel and bingo, road route, ring crossing).

**The right tool for the threat.**
43. For an **air threat**: an AIR unit with a round that can hit the threat's domain and altitude band (`tasking_gen.can_hit`, `tasking_gen.py:172-182`), so fighters intercept.
44. For a **ground threat**: a GROUND unit that can hit it, so armor reinforces.
45. Aircraft do not answer ground threats (G2 as written; open question 12).

**Not already the node's own defender.**
46. For a ground threat, a unit homed at the target node is not a responder: it already takes that node's `defend:<node>` job.
47. For an air threat there is no such job, so the target node's own garrison fighters do respond.
48. This is the acceptance case (NX-424): "a tracked strike group near a Static base draws its idle fighters".

**AD-4 The response job.**
49. The side's board generates one job per threat, in the generate step (`tasking_gen.generate`, `tasking_gen.py:257-273`), from the side's view only (TB-9, TD-2):

50. Key `respond:<entity>` (name PROPOSED), added to the board's `GENERATED` prefixes (`tasking_gen.py:99-109`).
51. `Job.entity` is the threat.
52. `JobCreated.entity_id` names it, which FOW-8 allows because the side tracks it.

53. **Air threat:** kind `INTERCEPT`.
54. `Job.pos` is the side's track of the threat, re-aimed at every pass, never its true position.
55. Claimants fly to the track (the `_chase` rule).
56. Priority `tasking.priority.intercept` (45: below DEFEND, above STRIKE).

57. **Ground threat:** kind `DEFEND`.
58. `Job.node` is the target node.
59. Claimants drive there by road and hold it, engaging by COMBAT's ordinary rules.
60. Priority `tasking.priority.defend` (60).

61. Urgency 1.0.
62. Slots `director.defense.max_responders`.
63. **Overfill never applies** (as for a Recon point job, `tasking._overfill`, `tasking.py:303-311`), so the cap is hard: at most `max_responders` claimants per threat at any time.

64. The board posts it only while the side has a live unit that could be a responder for it (AD-3).
65. For the coalition this is narrower than the usual staffing rule, which also counts roles a viewer could JOIN (`tasking_gen.py:242-248`).

66. **Generation stops when the threat is no longer closing.**
67. By the board's existing rule an unclaimed generated job that is not generated again expires at once (`tasking.py:414-417`).
68. A claimed job stays until its outcome (AD-5).
69. So a strike package that arrives and orbits over the base keeps its responders (lead reading, open question 3) but draws no new job.

70. With `max_responders` at 0, nothing is generated (the off switch, open question 14).

**AD-5 Release and return (leash).**

71. **DONE** when the threat is destroyed or Disabled and the job has a participant, else EXPIRED (the intercept rule).

72. **EXPIRED** when the side has not tracked the threat for `director.defense.lost_s` (`Job.lost`, as intercepts count it), or when its last track is no longer within `director.defense.radius_m` of any node the side holds.

73. **FAILED** (ground job only) when the side loses the target node (the DEFEND rule).

**Leash.**
74. A garrison claimant of an air job whose threat's track passes its leash is released (`JobReleased`) and stops, as in `_chase`.

**Afterwards.**
75. An aircraft stops where it is when the job ends, and a ground unit stays at the node.
76. Each is then an ordinary idle unit.
77. A garrison unit away from its home is recalled at the next decision window (`launch._recall`).
78. A unit with no home may be reused by a later operation or retired after `director.idle_retire_s` (Q-SIM-84).
79. A responder is not idle while it holds the job, so it is not retired during a response.

80. A responder that loses its claim (lost, Disabled, sent home at bingo) frees its slot.
81. Another responder may take the slot, still within the cap.

**AD-6 Operations, staging and the hold response.**

**Not an operation.**
82. Active defense is board work, not a Director operation.
83. It has no catalog entry, does not count against `director.max_ops.<tier>` or `director.max_spawns_per_window`, does not stamp `DirectorState.last_operation`, and is never staged (§4a).

**Operations keep their units.**
84. Responders are idle, so no operation loses a unit on a job.
85. An operation's reuse of idle units (`launch._reusable`) cannot take a unit while it responds.
86. Garrison units are never reused, as today.

**Staging (§4a).**
87. A staged operation in `DirectorState.staged` has no units yet, so it is unaffected.
88. The staging base's stock target is unaffected.
89. Units holding a STAGE claim: open question 4.

**Hold response (Q-TD-46, NX-430).**
90. Independent.
91. The hold response's capture operations put the Static's units on CAPTURE and STRIKE jobs, so they are never responders.
92. When the coalition has mobile AI garrison units, the Static's hold-response jets closing on a hold node are threats to the coalition under AD-1, by the same rule (G4).

**Scout intercept (§5a).**
93. Unchanged.
94. A scout never draws a `respond:` job (AD-1 rule 4).
95. A unit on an intercept is not idle, so it is never pulled.

**Escorts.**
96. Units following a convoy hold a job or a follow order, so they are not responders.

**AD-7 Cost and budget.**
97. A response spawns nothing and buys nothing:

98. No `UnitSpawned`, no `SupplyConsumed{SPAWN}`, no draw on the window budget (step 2), the rear account or the pool.

99. Responders spend fuel and rounds, which the ordinary refuel and rearm rules restock at a landing base from its stock (GAMEPLAY §5b).
100. That is the only cost, and it already applies to any sortie.

101. **Upkeep (EC-4 to EC-6) is unchanged.**
102. One side effect: a responder holds a claimed job, so it is *busy* for the payment order (EC-6) and is paid before idle units at its home.

103. **No provocation and no threat memory from responding.**
104. A Static responder's hits land on coalition units, which is not a provocation (the victim is not the Static's, §7a).
105. A coalition AI garrison's hits on Static units add `director.provocation.ai_shooter_mult` × the weight, 0 by default (`services/sim/src/nexus/core/provocation.py:8-10`, `provocation.py:102-103`).
106. Posting, claiming and ending a `respond:` job note nothing.

**AD-8 The coalition's AI garrison (G4, EC-3).**
107. The same rule, the same keys and the same job, generated on the coalition's board from the coalition's view.

108. Only `AI_GARRISON` units respond (AD-3).
109. This is defense of its own nodes, so it does not break "the AI garrison never initiates offense" (GAMEPLAY §1b).
110. A DEFEND is already in `tasking.ai_jobs`, and `_may_take` already lets an AI unit take an INTERCEPT by itself (`tasking.py:308-314`).

111. **Inert in code until the coalition has mobile AI units.**
112. Its AI garrison is facilities today, which cannot move.
113. The leash needs a home, and `Entity.home` is refused on a unit that is not the Director's (§7a Part 3 load checks).
114. Open question 10.

115. Viewer units neither take nor see `respond:` jobs as their own work (open question 9).
116. They keep the ordinary DEFEND and NEEDED list.

**AD-9 Fog of war (FOW-4, FOW-8, TD-2).**
117. Detection, closing, the target node and the job's position read only the side's view: current tracks and node positions and owners.
118. The one read of the truth is liveness (AD-1 rule 5), the same exception the scout intercept makes.
119. Responders chase the track, never the true position.
120. A threat the side does not track draws nothing.
121. Two worlds that differ only in an untracked enemy unit give the same board.
122. No sitrep is added (G3).
123. The job's lifecycle events (`JobCreated`, `JobClaimed`, `JobDone`, ...) are what the overlay may call out; the callout is OVERLAY work.

**AD-10 Determinism and state.**

124. Order: the boards run COALITION then ENEMY, as today (`tasking.py:383-420`).
125. For each side the samples are updated after settling and before generation, in the slot where `_watch` runs for the Static.
126. Pairs are taken in (entity id, node id) order, threats in entity id order.
127. The target node is the smallest range, ties by node id.
128. Responders are assigned by the board's existing rule: idle units in id order, jobs in rank order, equal-priority runs ordered by one `tasking` draw each (SC-5).

129. No new RNG stream and no draw in detection or generation.
130. With responders on, the board holds more jobs, so the `tasking` draws in equal-priority runs change and goldens change.
131. With `max_responders` 0 nothing is posted and no draw changes, so goldens are unchanged.

132. Ranges are floats from `math.hypot` on track positions, compared directly, as `_defend` and `held_within` already do.
133. The same inputs give the same result on one thread (SIM-CORE).

134. **State:** the closing samples, for example `World.defense_seen` (side → (entity id, node id) → ascending list of (pass tick, range)), are world state, in the snapshot and the hash, with a snapshot format bump.
135. Restore refuses: a tick past the clock, a sample list not ascending by tick, a node that is not a theater node, and an entity id that does not exist.
136. There is no upper bound tied to `reaction_s`, because a hot reload may change it (as with `blink_ready`, §7a Part 2).
137. On a hot reload the window simply uses the new value at the next pass.

**Time (TD-1).**
138. Board passes never run while frozen (SC-11), so a pause freezes the samples.
139. `reaction_s` and `lost_s` are game time, counted in running ticks, so `sim.time_scale` changes no count.

**Size.**
140. At most one sample list per (tracked enemy unit, held node in radius), each at most `reaction / reeval + 1` samples long at the shipped values (13 at 60 s and 50 ticks).
141. The pass cost must stay inside SC-10; a perf test checks it (below).

**AD-11 Proposed balance keys (PROPOSED, all; added through the add-config-key skill at build time).**

| Key | Type | Unit | PROPOSED default | x-tune (min to max, step, scale) | Hot reload | Notes |
|---|---|---|---|---|---|---|
| `director.defense.radius_m` | number > 0 | m | 30000 (PROPOSED: the intercept radius, `balance/default.yaml:314`) | 10000 to 60000, step 1000, LINEAR | Yes | An armed enemy tracked this close to a held node is sampled (AD-2). |
| `director.defense.reaction_s` | number > 0 | s (game) | 60 (PROPOSED: the intercept reaction, `balance/default.yaml:315`) | 20 to 180, step 5, LINEAR | Yes | The closing window (AD-2). |
| `director.defense.closing_min_m` | number ≥ 0 | m | 250 (PROPOSED; open question 1) | 0 to 2000, step 50, LINEAR | Yes | How much the range must shrink over the window. At the shipped catalog speeds, infantry at 5 m/s closes 300 m in 60 s (`content/units/garrison-infantry.yaml:8`); a jet at 250 m/s closes 15,000 m (`content/units/strike-fighter.yaml:8`). |
| `director.defense.max_responders` | integer ≥ 0 | units | 2 (PROPOSED: `tasking.slots.defend`, `balance/default.yaml:167`) | 0 to 4, step 1, LINEAR | Yes | Hard cap of claimants per threat; 0 turns active defense off. |
| `director.defense.leash_m` | number > 0 | m | 80000 (PROPOSED: the intercept leash, `balance/default.yaml:317`) | 20000 to 160000, step 5000, LINEAR | Yes | A garrison unit responds only within this distance of its home (AD-3; open question 6). |
| `director.defense.lost_s` | number > 0 | s (game) | 120 (PROPOSED: the intercept's, `balance/default.yaml:318`) | 60 to 240, step 10, LINEAR | Yes | A response ends once its threat was untracked this long (AD-5; open question 7). |

142. All are category DIRECTOR, audience TUNER, edit role ADMIN, status PROPOSED, source THREAT-DIRECTOR §5b, as the `director.intercept.*` keys are (`contracts/config/balance.json:2818-2828`).
143. No priority or slot key is new: the jobs use `tasking.priority.intercept` and `tasking.priority.defend` (open question 15).

**AD-12 Tests (acceptance).**

**NX-424 acceptance.**
144. A seeded world: two coalition STRIKE_FIGHTERs that the Static tracks fly straight at a Static AIRBASE whose garrison fighters are idle.
145. After `reaction_s` the Static's board posts one `respond:<id>` INTERCEPT per jet.
146. The garrison fighters claim them, at most `max_responders` per jet.
147. The run emits no `UnitSpawned` and no `SupplyConsumed{SPAWN}` from it, and the window budget and every stock are the same as in a run with `max_responders` 0, before the first shot.

**Real threats only.**
148. No job is posted for: a jet flying a constant-range circle round the base; a jet flying away; a jet that closes by less than `closing_min_m` over the window; a RECON_UAV or a LOGI_TRUCK closing (the scout still gets its intercept, §5a); a unit tracked only as last-known.

**Continuity.**
149. One pass with the unit untracked, or outside the radius, resets the clock: the job comes `reaction` after it is tracked again, not before.

**Sliding window.**
150. A jet that loiters at 25 km for 10 minutes and then holds still draws nothing.
151. When it then closes by the margin over one window, it draws a job at that pass.

**Fog (TD-2).**
152. Two worlds that differ only in a closing coalition jet the Static does not track give the same board and the same events.
153. Every `respond:` job references a tracked entity.

**Cap.**
154. Five idle fighters and one threat with `max_responders` 2: never more than 2 claimants, even when the board's overfill would otherwise apply (Q-TD-89): a respond job never overfills.

**Leash.**
155. A garrison fighter whose home is farther than `leash_m` from the track does not take the job.
156. One that took it is released when the track passes the leash, stops, and is recalled home at the next window.

**Ground.**
157. A coalition GARRISON_INFANTRY closing on a Static FOB draws a `respond:<id>` DEFEND taken by idle armor homed at a neighbouring base within the leash.
158. Armor homed at the FOB takes `defend:<fob>`, not the response.
159. The job FAILS when the FOB falls.

**Never pulled.**
160. Units on STRIKE, CAPTURE, ESCORT_CONVOY, PATROL, SCOUT, RESUPPLY or INTERCEPT jobs, grounded units and RTB units never take a `respond:` job.

**Outcomes.**
161. DONE when the threat is destroyed or Disabled with a participant.
162. EXPIRED after `lost_s` untracked, or when the track leaves every held node's radius.
163. An unclaimed job is dropped at the first pass at which the threat is no longer closing.

**No side effects.**
164. Responding adds no provocation and no threat memory, launches no operation and leaves `last_operation`, `max_ops` and staging unchanged.

**Parity (EC-3).**
165. A mirrored hand-built world where the coalition has an `AI_GARRISON` fighter with a home gives the mirrored jobs and claims.
166. A viewer's unit never takes a `respond:` job.

**Determinism.**
167. Same seed, same events.
168. A snapshot taken mid-window and restored gives the same events.
169. A pause freezes the samples.
170. With `sim.time_scale` ≠ 1 the job comes after the same number of ticks.
171. With `max_responders` 0 the goldens are byte-identical to the build before.

**Load checks.**
172. A restore refuses each AD-10 case.

**Perf.**
173. A pass with 500 enemy units tracked near held nodes stays inside SC-10 (marker `perf`).

**AD-13 Harness metrics to sweep (NX-031).**
174. Sweep `radius_m`, `reaction_s`, `closing_min_m`, `max_responders` and `leash_m` (and `lost_s` once) over the x-tune ranges, at the crowd profiles (§1), and report:

175. responses posted per game hour, and the share that got a claimant;

176. time from the threat's first sample to the first claim;

177. threats destroyed or Disabled while a response ran, and responders lost per response;

178. coalition strike success on Static bases (the STRIKE jobs that reach DONE; a strike whose jets fired at the target and went home with their bombs spent counts, Q-TD-87), with active defense on and off;

179. false alarms: responses that ended EXPIRED with no shot fired by either side;

180. base exposure: game minutes a Static base had none of its garrison at home while a response ran;

181. the stock spent on responders' refuel and rearm;

182. STAGE jobs that failed because a staged unit responded (only if open question 4 lets staged units respond);

183. tick time p99 with active defense on and off.

**AD-14 Non-goals.**

184. No spawning, no purchase, no new unit and no new unit power.

185. No new sitrep (G3).

186. Not an operation: no catalog entry and no LLM or GM involvement.
187. A GM may still inject jobs as §6a allows.

188. No reaction to unarmed units.
189. Scouts stay under §5a.

190. No prediction from ground truth: no reaction to an untracked unit, no lead on a hidden heading.

191. No change to facilities: air-defense sites already fire by COMBAT's rules.

192. No automation of viewer units.

193. No pursuit beyond the leash, and no counterattack on the attacker's base.
194. Retake stays an operation.

195. No tier change from responding: active defense is not provocation.

**AD-15 Open questions (each with a recommendation; none decided here).**

1) **Closing margin.**
   Is `director.defense.closing_min_m` needed?
   **Rec:** yes, one key in metres, PROPOSED 250 m, so a steady orbit or jitter never counts.
   Alt: 0 (any shrink counts), or a margin scaled by speed.
2) **Window form.**
   Compare the range now with the range `reaction` ago (sliding), or with the range when the unit first entered the radius?
   **Rec:** sliding (AD-2).
   It matches "shrank over that time" and ignores an old loiter.
   Lead reading, owner may veto.
3) **Latching.**
   Once a response is claimed, does it run until its threat ends even if the threat stops closing (a package orbiting over the base)?
   **Rec:** yes.
   The board already keeps claimed jobs, and an orbiting striker is still attacking.
   An unclaimed response is dropped.
4) **"Staged units" (G2).**
   Units holding a STAGE claim have a job.
   **Rec:** an arrived STAGE claimant may answer a threat to its own staging base only.
   Taking the response releases its STAGE claim, and the STAGE job follows its existing rules (it FAILS with no claimant left).
   Units freed after a STAGE ends are idle and respond normally.
   Alt: STAGE claimants never respond.
5) **Leash for units with no home.**
   **Rec:** none, as `_in_leash` reads it today.
   Fuel, road and ring rules still bound them.
   Alt: `leash_m` measured from the unit's position when it takes the job.
6) **Leash key and measure.**
   Reuse `director.intercept.leash_m`, or a new `director.defense.leash_m`?
   One leash for air and ground?
   **Rec:** a new key (the two rules tune apart), one value for both domains, straight line from home to the track (air) or to the target node (ground).
   Alt: a per-domain leash, or road distance for ground.
7) **`lost_s`.**
   Reuse `director.intercept.lost_s`?
   **Rec:** a new key with the same default, so the two rules can be swept apart.
8) **Tiers.**
   Does active defense run at Pattern of Life, and with the same reaction?
   **Rec:** every tier, the same reaction.
   Only an armed unit closing on a node counts, and defending is not escalation.
   Alt: a longer wait at Pattern of Life, like `director.intercept.pol_linger_s`.
9) **Coalition responders.**
   AI garrison only, or also viewer units on the board?
   **Rec:** AI garrison only, never a parameterless JOIN, so "nothing spawned" holds literally and viewers keep their own DEFEND and NEEDED list.
10) **Coalition leash anchor.**
    `Entity.home` is Director-only.
    **Rec:** when the coalition gets mobile AI garrison units (with NX-375 or a garrison item), they get a `home` by the same rule, and AD-8 starts working then.
    Until then it is inert, and a test uses a hand-built unit.
    Alt: anchor on `home_base`, the upkeep home (EC-4), which moves when the unit lands elsewhere.
11) **Which nodes.**
    **Rec:** air threats: every node the side holds, as the scout intercept does (`held_within`).
    Ground threats: held capturable nodes only, as DEFEND (`tasking_gen.py:387`), since a DEFEND of a sanctuary or a bridge has nothing to hold.
12) **Aircraft against ground threats.**
    Armed aircraft fit DEFEND today (`tasking_gen.py:155-156`).
    **Rec:** no; G2 pairs fighters with aircraft and armor with DEFEND.
    Revisit if the harness shows ground raids going unanswered at airbases.
13) **Job kinds.**
    Reuse `INTERCEPT` and `DEFEND` with the new key prefix, or add a JobKind?
    **Rec:** reuse.
    No contract change (AGENTS rule 6).
    The outcome rules branch on the key prefix.
14) **Ship on or off.**
    **Rec:** ship on with the PROPOSED values, goldens regenerated in the same PR, `max_responders` 0 as the off switch.
    Alt: ship 0 until the sweep.
15) **Priorities.**
    **Rec:** reuse `tasking.priority.intercept` (air) and `tasking.priority.defend` (ground).
    A separate key only if the sweep shows responses starving intercepts or the reverse.

Notes: THREAT-DIRECTOR-NOTES.md §5b

## 6. LLM advisor (P4, optional)

1. **Input:** a structured summary built from ids, sectors, counts and threat memory, plus the top-K candidate operations.
2. It includes **no user strings** (SEC-LLM-4).

3. **Output:** `{choice_index:int, op_name:str ≤ 40 chars, rationale:str ≤ 140 chars}`.
4. The schema is validated, and the text is moderated.

5. **Isolation and budget:** the advisor runs in its own isolated container and counts against the $20/month AI cap (LLM-ADVISORS LLM-2, LLM-3).

6. **Deadline:** the answer must arrive within 2 decision windows.
7. If it's late, invalid or over budget, the rules choose.
8. The accepted choice enters as a logged command (ADR-0002).

## 6a. Game Master takeover (owner requirement)

1. The owner, or an admin with the `GAME_MASTER` permission, can take over the director (ADMIN-RBAC spec):

2. **Scope (Q-AI-8, Q-ALN-10):** a GM drives the Static and triggers world events (TS-1), nothing else.
3. World events may benefit the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction.
4. A GM never grants units, ammo or XP to specific players.
5. Campaign setup (objectives, unlimited ammo and other campaign options) is owner/Admin only, never GM (GAMEPLAY §9c).

6. **Job injection (Q-GD-37 item 11, Q-ALN-11):** a GM injects jobs into the **Static's board only**.
7. An injection that targets the Quorum's board is rejected.

**Modes (Q-TD-9):**

8. **ASSIST** (first GM release): the GM injects or vetoes operations while the rules keep running.

9. **FULL** (the next release after ASSIST; the owner wants it soon): the rules pause, and the GM issues operations from the same operation catalog.

10. **Constraints:** GM operations are still validated against the window budget (ECONOMY EC-7) and preconditions.
11. A GM *may* exceed the budget only with an explicit `override_budget` flag, which is audited.

12. **Logging:** every GM action is a logged `STAFF_*` command, so replays stay deterministic (ADR-0002), and is flagged as a GM action in replays (Q-AI-8).

13. **On stream:** a "COMMAND: GAME MASTER" badge is always visible while a human GM is in control, on every layout including 9:16 (Q-ALN-17; DATA-INTEGRITY DI-5: never disguise human control as AI or vice versa).

14. **Threat memory keeps learning** during a FULL takeover, so control returns to an up-to-date director (Q-RB-6).

15. **Voice:** GM lines use the distinct Game Master voice profile (AUDIO-TTS §2a, Q-RB-7).

16. **Auto-release:** if the GM goes idle beyond a configured timeout (monotonic real time, measured outside the sim, Q-ALN-4), control returns to the rules, with a logged `GM_RELEASED{reason}`.

## 6b. Mastermind and taunts (Q-AI-7, Q-BRAND-4)

1. **Name:** the Quorum's intelligence codename for the Static's mastermind is NULL (shown e.g. "SIGNAL SOURCE: NULL").
2. Code, config, contracts and logs refer to it by an internal id, never the literal string or value `null`.
3. The display name is content, not code.

4. **TD-3 Naming operators:** a taunt may name one operator only through a `{target}` placeholder that code fills with that operator's approved callsign.
5. The text around it is a template before P4; from P4 the LLM may write the line but never sees names or chat text (SEC-LLM-4).
6. Operators whose `!quiet` opt-out is currently on are never named; `!quiet` is a toggle stored per commander and applies across linked platforms (COMMAND-CATALOG, CHAT-GATEWAY §9, Q-ALN-12).

7. **TD-4 Naming cooldown:** the same operator is named at most once per `taunt.name_cooldown_min` (PROPOSED 10); spotlight operators (recent hero events or high recent action) use `taunt.name_cooldown_spotlight_min` (PROPOSED 5).
8. Both are admin-configurable and run on a monotonic real clock, enforced outside the sim (Q-ALN-4).

9. **Tone:** playful rivalry; never an insult about the person.

## 6c. Lieutenants (P4, Q-GD-38, NX-317)

1. Owner direction, details PROPOSED: NULL commands through lieutenants, each a **director profile** (a config preset of priorities, aggression, preferred operations and taunt voice) using the same mechanics (parity).
2. Each sector or operation is run by one lieutenant.
3. Briefings name the lieutenant when known; otherwise the HUD shows UNIDENTIFIED until recon or captured comms reveal it.
4. Specced in NX-317; nothing here changes the P1 director.

## 7. Tests

1. Tier hysteresis property: no flapping under oscillating CP.

2. Budget never exceeded, and never above what the Static's real stock can pay for (Q-GD-30): a starved Static posts no operation it cannot fund.

3. TD-1: golden scenario with a pause mid-window: every director field (tier, dwell, threat memory, provocation, window progress) is unchanged from the pause tick to the resume tick, no operation is posted in between, and a `STAFF_DIRECTOR_OVERRIDE` sent during the pause is rejected (Q-ALN-24).
4. With `sim.time_scale` ≠ 1, the decision window and tier dwell take the same number of ticks as at 1 (Q-ALN-23).

5. TD-2: property: every job on the Static's board references only entities in `EnemyView`.

6. Q-AI-9, Q-ALN-13: a cosmetic redemption leaves `provocation` unchanged; a respawn skip or queue jump adds its (small) support weight.

7. Q-ALN-11: a GM job injection into the Quorum's board is rejected; one into the Static's board is accepted and logged as a GM action.

8. TD-3/TD-4: a taunt never names an operator whose `!quiet` opt-out is on (and may again after they toggle it off), never names the same operator twice inside the cooldown, and an LLM taunt prompt contains no callsign or chat text.

9. Q-TD-1: zero provocation with high CP stays Pattern of Life; high provocation with CP below `bravo_enter_cp` caps at ALPHA; a Pattern of Life → BRAVO target steps through ALPHA with dwell; provocation oscillating inside the hysteresis band never flaps.

10. Q-TD-2: CP is unchanged by an untracked coalition unit.

11. Q-TD-4: after a sensed strike in sector S while the CP ceiling is ALPHA, the top candidate targets S.

12. Q-TD-5/H3: a starved Static posts no operation it cannot fund (see Q-TD-12).

13. Q-TD-6: same seed, same scores; a shuffled catalog load order gives the same selection.

14. Q-TD-7: the operations loader rejects an unknown JobKind, an unknown precondition and an out-of-envelope cost.

15. Q-TD-8: a Static spawn goes to the nearest qualifying base, else the rear source.

16. Q-TD-9: an ASSIST veto drops the operation; a FULL takeover is rejected until FULL ships.

17. TD-2: an unsensed coalition scout in the Static's rear adds no provocation.

18. TD-2, TD-5 (NX-379): the Recon point and its route are the same for two worlds that differ only in coalition air defenses the Static has not discovered, and change when one is discovered; no Recon route crosses a known, not-Disabled ring; a sector the known rings cover is skipped; the scout loiters `director.recon.loiter_s`, the job is DONE and the scout goes home; a 0-viewer run loses far fewer scouts and burns far less stock than NX-157's.

19. Threat memory decays.

20. Golden scenarios: "convoy raids → escorts appear within N windows"; "overnight-0" (NX-157): 0 viewers for one game hour with the long periods shortened: no tier move, no provocation, the capture chain runs, and the board posts no strike of its own.
21. The 6-hour acceptance (no escalation, at most one node lost per cap) runs as a test with the periods divided by 12.

22. Q-SIM-85 (NX-157): a base below its quota gets one replacement a window, of the kinds in turn and paid from surplus; retirement takes only units above the quota, highest id first; a patrol goes out and home and is DONE on return; the convoy goes to the largest shortfall and to none when nobody is short; the PoL capture slot fires once per period and not while the cap is spent; the second Static flip with no viewer waits a full cap and with a viewer does not; a garrison unit defends its own base and takes nothing else from the board, and no operation reuses it; the Static's board posts no strike at Pattern of Life and does from ALPHA (the coalition's is never gated); 0 to 1 viewer changes nothing until a provocation; staging is in a scout's contacts only inside its sensor coverage; the timers freeze with a pause; a restored world runs the same events; stock + cargo + consumed stays exact; no unit leak over a 6-hour run.
23. Q-SIM-86: a convoy refills a base below its floor; the bases start at quota, free; an idle garrison unit away from its held home goes home (also after its patrol's turning node is lost); every Static flip starts the cap clock, a held bar stays held when a viewer arrives and frees one node per cap; a patrolling unit never captures the neutral node it turns at (a unit with no job does); the loader refuses an aircraft garrison at a node that is no landing base.

24. NX-473 (in code, `tests/core/test_logistics_cadence.py`; §5a demand convoys): a Static base below its floor gets a convoy job `convoy_demand_s` (+ at most one window) after the last convoy, not a full period; a base short only of garrison still waits the period; there is no second live convoy to one base; `convoy_demand_s` = `convoy_period_s` reproduces today's events; at the LC-3 default a convoy has `convoy_slots` trucks, and with `resupply_slots_max_starving` raised a deeper shortfall gets more trucks, at most the cap; the caps and the surplus still bind; it runs with no viewer and inside a night-capped stretch; a pause freezes it; a restored world runs the same events.
25. When the spawn room is short, a raised convoy gets fewer trucks, not none.

26. NX-401 (Q-SIM-120, Q-SIM-121): seeded ALPHA with the coalition holding cross-n across bridge-n → a STRIKE_BRIDGE STRIKE job on bridge-n within N windows and Static jets drop it; none when the bridge feeds no coalition node, at Pattern of Life, while another bridge is down or during the bridge's cooldown after `BridgeRepaired`; the same choice with coalition units on the span or without.

27. Balance harness: tier dwell distribution per scenario.

## 7a. In code now (Parts 1 to 5, NX-151, NX-155, NX-156, NX-157, NX-379, NX-401; Q-SIM-78, Q-SIM-81, Q-SIM-85, Q-SIM-87, Q-SIM-120, Q-SIM-121)

**Source pools (NX-412 part 1; ECONOMY EC-1, EC-2, EC-15).**
1. `nexus.core.economy` runs in the `director` slot before the decision window, on running ticks that divide by `economy.window_s` as ticks (600): each limited side's pool in `World.pool` gains income (`SupplyProduced`), then is clipped to storage (`SupplyConsumed{STORAGE_LOST}`).
2. The Static's rear source pays truck loads from its pool; the budget (step 2) and source spawns read it too (NX-412 part 3, items 5, 7 and 21 below).
3. `economy.unlimited.<side>` shipped true for both sides until NX-412 part 5b (Q-TD-29) and ships false since then, so both sources are finite.

**Budget, guard and the one spawn rule (NX-412 part 3; ECONOMY EC-7, EC-8, EC-13; Q-TD-33).**
4. The only rules since NX-488 deleted the temporary switch that kept the old ones (tier budget, per-tier live caps, paying from the surplus of every Static base, free sanctuary spawns):

5. **Budget (step 2, `nexus.core.director.budget`).** floor(base surplus × `director.spend_frac.<tier>`) + floor(rear pool × `director.source_spend_frac`) − floor(`director.upkeep_reserve_windows` × the upkeep the Static's live units owe per window, `upkeep.owed`), at least the cadence floor and 0.
6. The surplus is the Static bases' stock above their surplus references (NX-500, ECONOMY EC-7 "Surplus reference": `Supply.surplus_ref`, max(⌈`director.surplus_ref_frac` × `node_max_stock`⌉, the starvation floor), fixed at load; at the shipped 0.25 it is the floor, so a lower floor no longer raises the budget).
7. The rear pool is the side's `World.pool`, read after the economy window; a Static in unlimited mode has no pool, so that term is 0.
8. Cadence floor: while the Static holds an HQ, has no operation staged and `windows − DirectorState.last_operation ≥ director.cadence_windows`, the cheapest catalog operation with jobs enabled at its tier whose cost base surplus plus the rear share (floor(pool × `source_spend_frac`)) covers, what the window can actually pay, not the whole pool (NX-434: the capture floor's rule below); `launch.run` lifts the base account to its cost as the capture floor does (`launch._lift`), so a base with the surplus pays it there, else the rear account at the source.
9. That window (`launch._floor_capture`, Q-TD-42) the floor is lifted to the cheapest capture operation (`operations.has_capture`) among the window's candidates (enabled at the tier, not dropped by the night cap) whose cost the window can actually pay (base surplus plus this window's rear account, not the whole pool: Q-TD-48 (5)) and that the window's caps allow (spawn and live rooms, and `max_ops` with one slot over: the floor's operation launches while `max_ops` are running but not `max_ops + 1`, Q-TD-57, NX-441; one they would skip lifts nothing), its best-ranked target; the base account is lifted to at least its cost, and that candidate is selected and launched first, then the rest in the usual order.
10. If it still cannot pay (it pays at one node, Q-TD-48 (6)), the lift is undone and the window selects as if the floor had not fired.
11. No capture candidate leaves the floor as it was.
12. No RNG draw is added.
13. `last_operation` is the decision window of the last capture operation (`operations.has_capture`: Offensive, Retake) that posted jobs (normal window or capture slot; every other operation, DecoyBlink and Pattern of Life convoys do not count, Q-TD-54, NX-439: the Static's cheap operations every window kept the floor from ever coming due), or in which a staged operation was kept, launched or dropped (Q-TD-42: the floor is also not due while an operation is staged, so it counts from the drop), in the snapshot (format 30) and the hash.
14. The cheapest-operation floor runs on the same clock, so with no capture target it stays due each window until a capture operation launches or is staged (NX-439, lead reading).
15. With the fractions at most 1 (schema) the budget never exceeds surplus + pool.

**Two accounts a window (`launch._Purse`).**
16. The budget splits into a rear account, min(budget, floor(pool × `source_spend_frac`)), and a base account, the rest (the bases' spend share less the reserve, lifted by the cadence floor).
17. Base spawns spend only the base account, source spawns only the rear account.
18. The capture slot and the Pattern of Life convoys use the real base surplus as their base account and share what is left of the window's rear account, so the pool pays at most its share a window.
19. A Static in unlimited mode has no pool, which never runs out (EC-15): it keeps one account, the whole budget (the base term plus the cadence floor; the rear term is 0), for spawns at bases and at its source alike, and a source spawn debits no stock.

**Pay and spawn (step 7, `launch._paying_node`).**
20. An operation's cost is drawn once, at the one node where all its new units spawn: the base `plan_deploy` picks for its first aircraft kind (else its first kind), when that base is a `spawns` node for every kind's domain, its surplus covers the cost and the cost fits the base account; a garrison replacement's base and a scout's checked origin are fixed, with no fallback.
21. Otherwise the source, when the rear account and the pool cover the cost.
22. Otherwise the operation is dropped this window.
23. One `SupplyConsumed{SPAWN}` at that node (none at an unlimited source).

**Guard (EC-8).**
24. `sim.max_live_units_per_side` is the live room (live AIR and GROUND units of the side, `economy.guard_room`); `max_spawns_per_window` stays.
25. A refused operation is not selected.
26. Operations the budget and `max_spawns_per_window` allow but the live room does not are counted in one `SpawnRefused{side, reason, operations, units}` per selection (the window, the capture slot, the convoys): reason `GUARD` (NX-412 part 5a, Q-TD-34 (5); `TIER_CAP`, the deleted per-tier cap's, is no longer emitted since NX-488).
27. For JOINs see GAMEPLAY §5.

**Cost envelope.**
28. The catalog loader checks costs against floor(`spend_frac.bravo` × the largest storage, every theater node held)

**Interpretations (lead, owner may veto).**
29. The cadence floor's "afford" is against base surplus plus the window's rear account, what the window can pay (NX-434; it was surplus + pool, Q-TD-34 (1), which let a Static with no base surplus "afford" an operation it could not pay); with an unlimited Static the rear pool counts 0 in the formula, and its one account lets it spawn at the source within the budget; the Director's spawns at one node use the aircraft kind's deploy base so jets never spawn at an FOB.

**The contested victory hold (NX-412 part 4; ECONOMY EC-9, EC-12; Q-TD-19, Q-TD-25).**

**Hold events and state.**
30. `nexus.core.campaign` keeps the hold's nodes in `Campaign.hold_nodes` (the strategic nodes the coalition held on the last tick of the run, ascending; snapshot format 31, in the hash) next to `hold_ticks`, and emits `VictoryHoldStarted{node_ids, ends_at_tick}` on the run's first running tick (`ends_at_tick` = that tick + `victory_hold_ticks` − 1, the victory tick if unbroken) and `VictoryHoldBroken{node_id}` on the tick the share falls below `campaign.victory_node_frac`, naming the hold node lost (the lowest id when several fell).
31. The fraction is above 0 and not hot-reloadable, so a break always loses a node.
32. Nothing is emitted when the campaign ends during the hold (victory, defeat, time limit or abort).
33. A broken hold decays (ECONOMY EC-9a, NX-489, Q-TD-126): with `campaign.victory.hold_break: decay` it keeps its progress in `hold_ticks` and its nodes in `Campaign.hold_broken_nodes` (snapshot format 37), never in `hold_nodes`, until it resumes or `VictoryHoldReset` ends it.
34. A hold paused under pressure (ECONOMY EC-9b, NX-466) is still running: it stays in `hold_nodes` and `SideView.hold`.
35. So the hold response below (the score multiplier, FS-10 and `HOLD_AT_RISK`) reads a running hold only: a decaying hold is not in `SideView.hold`, and the Static presses it like any other ground.

**EnemyView (TD-2).**
36. `SideView.hold` is `Campaign.hold_nodes`: the hold is public (Q-TD-25).
37. The Director reads it in the `director` slot, before capture, so it is the hold as of the last `objectives` slot.

**Score (step 4).**
38. For an operation with a CAPTURE job (OFFENSIVE, RETAKE: `operations.has_capture`, the same test as the capture slot) aimed at a NODE: x `director.score.victory_hold_mult` when the target is in `SideView.hold`, x `director.score.income_node_mult` when the view shows the target held by the other side and its kind has `economy.income.per_node` above 0 (`operations._press`).
39. Both ship 1.0 (PROPOSED placeholder until the NX-412 sweep), so no score changes.
40. The enumeration order, the one `director` draw per candidate and the selection order are unchanged.

**Sitrep (§5a INTEL).**
41. When such an operation targeting a hold node launches (it posted its jobs; normal window or capture slot), `launch._launch` emits `ThreatAdaptation{category: HOLD_AT_RISK, direction: UP, sector_id: the node's sector, node_id: the node}`, once per launch; a live operation is not posted again for the same target, so not again while it runs.
42. The text "NULL moves on <node>, the hold is at risk" (owner, Q-TD-19) is the sitrep template's, filled with the theater's node name (CONFIG-AND-CONTENT §10.2); no sitrep template file exists yet.
43. No DOWN follows: `VictoryHoldBroken` or the end of the campaign closes it.

**Interpretations (lead, owner may veto).**
44. "In the hold" is the strategic nodes the coalition holds while the hold runs (the set can shrink and stay a hold).
45. The sitrep rides on `ThreatAdaptation` (the existing INTEL event) with a new category and a nullable `node_id` rather than a new event; a target outside every sector (not possible on a validated theater) gets no sitrep.
46. "Coalition-held" in EC-12 is read as "held by the other side", which is the coalition for the Static, the only Director.

**Forward staging (NX-416; §4a FS-1 to FS-7; Q-TD-36, Q-TD-37, Q-TD-38).**

**When (FS-1, `staging.far`).**
47. An operation aimed at a NODE with a CAPTURE job, when the slowest capture kind's road travel time from the rear source exceeds `director.staging.direct_s` (1500 game s, PROPOSED).
48. Travel time is `roads.travel_ticks`: `shortest_path` with the bridges down in the side's view cut and no node avoided, each road at its `speed_mult`, the kind's top speed, rounded up to ticks (the balance travel table uses the same function).
49. No route counts as never arriving.

**Base (FS-2, `staging.base_for`, `staging.hosts`).**
50. A node the side holds, not a BRIDGE, with a `node_max_stock` above 0, no capture bar on it, and a theater `spawns` node for each capture kind's domain; the shortest travel time to the target, ties by node id, and strictly shorter than the rear's, else no staging.

**Stage (FS-4, FS-5, `launch._stage`).**
51. In `_launch`, for an operation the window (or the Pattern of Life capture slot) selected: when it is far and has a base and fewer than `director.staging.max_staged` (2) are waiting, `ThreatAdaptation{STAGING, UP, sector_id: the base's sector, node_id: null}` is emitted ("NULL forces are massing in <sector>"); it launches at once when every node it spawns at can pay its own units (as below), else joins `DirectorState.staged` (operation, target, base, window).
52. Not far, no base, or the list full: EC-13 as before.

**Stock (FS-3, `logistics.stock_targets`).**
53. While operations wait at a base, its forward-stock target is the larger of `Supply.stock_target` and its starvation floor plus, for each operation staged there, the cost of its units that spawn there (its template slots whose kind's domain the base hosts, at the operation's cost per unit; `logistics._base_share`), at most its maximum.
54. The board's stocking RESUPPLY job (`tasking_gen._resupply`) and `logistics.keeps` read it, and a Pattern of Life convoy goes first to a staging base below it (`launch._convoys`).

**Hold, launch, fall back (FS-4, FS-6, `launch._review`).**
55. Each window, before the selection, in (operation, target) order: an operation that is no longer a candidate (`operations.candidate`: in the catalog, preconditions hold, selectors resolve, any tier) is dropped.
56. If its base is no longer a host (lost or contested), it re-stages at the base `base_for` gives now, with the same start window, or falls back; the re-stage emits a new `STAGING` sitrep (FS-9: unless one is still open for the new base's sector) only when the coalition currently tracks (`fog.spotted`, a track with no age) a live Static entity at the new base: one standing on the node's position, or a facility whose `base_id` is the base (`fog.seen_at`, NX-436 moved it there).
57. It launches when every node it spawns at can pay its own units (`launch._staged_shares`): a kind the base hosts spawns there, any other kind where EC-13 puts it (`plan_deploy`'s base for its job, else the rear source; `launch._staged_spot`), and when that deploy base cannot pay its units' share they spawn at the rear source and pay there instead (Interpretation 6), so it waits only while the base cannot pay its own units or the source cannot pay its units; the spawn uses the nodes this check chose.
58. Each node's share is the operation's cost per unit times its new units, counted base first, then the other bases by id, the source last, each share the cost up to and including that node less the cost before it, so the shares add up to the operation's cost; a base pays from its surplus and the window's base account, the source from the pool and the rear account, the accounts drawn down node by node.
59. Each node is debited its share (`SupplyConsumed{SPAWN}` at that node).
60. After `director.staging.max_wait_windows` (30) windows, or with no base, it launches by EC-13 (`_paying_node` as for any operation) or is dropped.
61. `launch.run` computes the night cap (`_night_capped`) before `_review` and passes it in: while it is spent `_review` launches nothing, so a staged operation is kept while it may still wait and dropped otherwise (NX-480).
62. The staged operations' costs (launched now or still waiting) come off the window's budget before the selection, and their (operation, target) pairs count as running for `director.max_ops.<tier>` and are not posted again.

**State (FS-7).**
63. `DirectorState.staged` (snapshot format 32, in the hash): a list ascending by (operation, target), each pair once, `since` at most `windows` (load checks); `provocation.validate` refuses a staged operation that is not a catalog operation with a CAPTURE job, or a target or base that is no node.
64. No RNG draw; nodes in id order.

**Interpretations (lead, owner may veto).**
65. (1) FS-2 asks only that the base host the capture kind, so OFFENSIVE and RETAKE can stage at an FOB; their jets cannot spawn there, so a staged operation's aircraft spawn by EC-13's rule (`plan_deploy`, else the rear) and are paid there (Q-TD-38).
66. (2) The first sitrep comes whenever staging starts, also when the operation can pay at once; a re-stage is announced only under the coalition-track rule above (Q-TD-38: "at the base" read as on the node's position or a facility of the base; a last-known track does not count).
67. (3) At the wait limit the fallback is EC-13 as implemented (`_paying_node`: the jets' deploy base or the source), not a search of every node.
68. (4) With `max_staged` waiting, a further far operation spawns as EC-13 says rather than being skipped.
69. (5) Two operations staged at one base raise its target by both base shares; the target is an upper bound of the launch-time base share (reused idle units lower the actual draw).
70. (6) (owner, Q-TD-39) When the node `plan_deploy` picks for a staged operation's jets cannot pay their share, the jets spawn at the rear source instead and pay their share there, as `_paying_node` does for any operation; the operation waits only while no spawn node it can use can pay (the staging base for its own units, then the deploy base or else the rear for the rest).
71. Rear spawns are limited by the rear pool, the window's rear account (EC-7), upkeep (EC-4) and `director.max_spawns_per_window`, the same rules the coalition's sanctuary runs on (EC-3).
72. FS-6's "raided below the cost when the wait runs out" is not a separate re-stage: the operation takes the FS-4 timeout fallback, which is the same outcome once the wait has run out.

**The victory-hold response (NX-430; §4a FS-10; Q-TD-46).**

**No staging.**
73. `launch._stage` stages nothing aimed at a node of `SideView.hold`, and `director.staging.max_staged` does not stop it: when the target is far and `staging.base_for` gives a base, it launches from that base at once if every spawn node pays now (`_launch(at=base)`, as a staged launch, but with no `STAGING` or `STAGING_LAUNCHED` sitrep); otherwise it launches by EC-13 at once (`_paying_node`: the jets' deploy base when it pays, else the rear source).
74. The no-viewer night cap still removes capture candidates (`launch.run`'s `capped`).
75. `launch._review` treats a staged operation whose target is in the hold as past its wait: it launches at its base when every spawn node pays, else by EC-13, else it is dropped (`STAGING_LAUNCHED` or `STAGING_DISPERSED` as FS-9 says).

**Outside `max_ops`.**
76. `operations.select(hold=...)`: a candidate or running (operation, target) pair whose operation has a CAPTURE job and whose target is in the hold is skipped by the cap like a routine one, so it neither waits for a slot nor takes one.
77. The cadence floor's one-over (`over`, Q-TD-57) is unchanged.
78. When the hold ends, a hold-response operation still on the board is counted again and can hold ALPHA's slot (and the floor's one over) until it finishes; accepted for now, measured by the sweep.

**Interpretations (lead, owner may veto).**
79. (1) Only capture operations aimed at a hold node are the response; one aimed elsewhere during the hold stages and is capped as before (EC-9's multiplier and `HOLD_AT_RISK` use the same test).
80. (2) "Outside the cap" means neither capped nor counted, as the routine operations are.
81. (3) "May launch" is not free: the window budget, `max_spawns_per_window`, the live room and the payment rule still bound it, so the number of hold-response operations at once is what those allow, one per target.
82. (4) A staged operation whose target enters the hold stops waiting (launch now, else drop) rather than keeping its slot.
83. (6) The launch from the staging base needs what staging needs (FS-1 far, an FS-2 base); a near target goes by EC-13 as without a hold.

**Payoff sitreps (NX-431; §4a FS-9; Q-TD-47, Q-TD-56).**

**Open massing (`Staged.sector`).**
84. `launch._stage` records the sector its `STAGING` sitrep named (None when the base is outside every sector, so nothing was said).
85. `launch._close` emits the payoff in that sector, always UP with `node_id` null, and clears it, so each massing closes once.

**Launch.**
86. `STAGING_LAUNCHED` when the operation launches at its staging base: at once in `_stage`, right after `STAGING`, or later in `_review` (`_launch(at=base)` posted its jobs).

**Disperse.**
87. `STAGING_DISPERSED` when `_review` drops it (no longer a candidate, or the wait ran out and nothing pays) or it launches by the EC-13 fallback (no base left, or the wait ran out), since it does not go in from the base.
88. On a re-stage (`launch._restage`), the new sector is the new base's when `fog.seen_at`, else none; when it differs from the open one, the open one closes as dispersed first and a seen new base opens a `STAGING` there; a seen re-stage in the sector already open says nothing.

**Strike package downed.**
89. `combat._credit`, from the hit that destroys, disables or mission-kills a unit whose `job_id` is a STRIKE job of the Static's board, when the shooter is COMMANDER-owned (AI garrison shooters are never credited, DI-5): the shooter joins `Job.downed_by` (ascending, once each).
90. If no other claimant of the job is still in the fight (alive, neither Disabled nor Mission-killed; a claimant turning home for fuel or rounds still counts) and the job is not yet `downed`, it is marked `downed` and `ThreatAdaptation{STRIKE_DOWNED, UP, sector_id: the job node's sector, node_id: the job's node, credit_ids: downed_by (the 32 lowest ids)}` is emitted in the `combat` slot, after that hit's own events.
91. A survivor that leaves or is released, a DONE strike and the job's expiry emit nothing; a jet put on a `downed` job later and shot down adds credit but no second sitrep.
92. Any Static STRIKE job counts (OFFENSIVE, RETAKE, PROBE, STRIKE_BRIDGE, the board's own).
93. The loader refuses `downed_by` or `downed` on any other job, `downed` with no credit, and credit ids that are not ascending entity ids below the counter.

**Interpretations (Q-TD-62 to Q-TD-64; (2) and the target node in FS-9 confirmed by the owner, who asks that sitreps never spam announcements, messages or TTS).**
94. (1) A launch by the timeout or no-base fallback is a disperse: the massing at the base did not go in.
95. (2) A seen re-stage in the sector whose massing is still open emits nothing (it would read as a second massing).
96. (3) "Broke it" means the shooter of the hit that destroyed, disabled or mission-killed a claimant, not assists, and only viewer units; the sitrep needs a viewer's hit on the last jet.
97. (4) "Still in the fight" counts every claim, active or not, so a jet still waiting on the STAGE job keeps the package alive; a survivor whose claim was released before the last kill no longer counts.
98. (5) "Near <node>" is the job's target node, not where the jets fell.

99. `nexus.core.director` (decisions), `nexus.core.provocation` (what the Static suffers) and `Rules.director`; state is `World.director[side]` (`DirectorState`, snapshot format 22, in the hash).

**Own view only (TD-2).**
100. `decide(state, view, rules, stock)` takes a side's `SideView` (`side_view(world, "ENEMY")` is the `EnemyView`), that side's `DirectorState` and the stock table, of which it reads only the bases the view says the side owns.
101. The module never names `World` or an entity accessor (a test parses its source), and an untracked coalition unit changes nothing.
102. It is side-agnostic; only the ENEMY runs (`provocation.DIRECTED`) until NX-375.

**Window (TD-1).**
103. In the `director` slot, before the Tasking Boards, when the running tick being computed divides by `director.window_s` as ticks (600 at 10 Hz).
104. Never while frozen, so a pause freezes every field and the window resumes where it stopped; game time is ticks, so `sim.time_scale` changes no count.
105. Each window: provocation decays by one exact multiplier of the half-life and takes what was noted since the last window; CP moves a `window / ema_window` step (1/5) toward the sum of the tracked units' values (it starts at 0); the provocation level (0, ALPHA from 10, BRAVO from 40) and the CP ceiling (ALPHA always, BRAVO from 60) update with their 0.8 exits; the tier steps at most once toward min(level, ceiling) once it has spent `min_dwell_s` (10 windows) in the current tier (a new campaign starts in `director.tier.start`, Pattern of Life by default, with dwell 0, so the first move is 10 windows in; a move takes up to `director.tier.max_step` steps, 1 by default); the window's budget is ECONOMY EC-7's (NX-412 part 3 above: the tier's share of the surplus of the Static's finite-stock bases over their surplus references (`Supply.surplus_ref`, NX-500), plus the rear share of the pool, less the upkeep reserve, at least the cadence floor).
106. A move emits `ThreatTierChanged`.

**Provocation sources (Q-TD-11, Q-SIM-78, Q-SIM-79).**
107. Noted where it happens, and only when the actor is a COMMANDER-owned unit (AI garrison adds 0, default; Q-CFG-16 option `director.provocation.ai_shooter_mult` counts that share of a hit by any other shooter, captures and scouts excepted; AUTO joins the exclusion with the AUTO state) and the victim is the Static's: `combat` after a hit lands (a facility brought to Disabled 8, else a facility hit 3; a unit destroyed, or knocked to Disabled as a wreck, 5, once: a hit on an already Disabled wreck adds nothing; a convoy hit 3; any other unit hit 1; one class per hit; **Q-SIM-89:** an unarmed scout kind, `painters` minus `armed`, i.e. ENEMY_RECON_UAV today, uses `recon_destroyed` 2 and `recon_damaged` 0 in place of the destroyed and unit-hit weights, so about five scout kills, not two, reach ALPHA at threshold 10; threat memory `scout_lost` is unchanged), `combat` for a hit on a Static base's defense HP (3, like a facility hit), `capture` at a flip of a Static base to the coalition with a commander in radius (15), the window start for a tracked player scout in the rear (2, at most `director.provocation.scout_in_rear_max_per_window` (1) notes per window), and `note_redemption` (support 1, cosmetic 0; no command calls it yet).
108. `last_provocation_sector` is the sector (theater polygons, an edge counts, lowest id first) of the latest noted action, ties in a tick by lowest id.

**The rear (Q-SIM-79).**
109. A point is in a side's rear when it is strictly nearer, in a straight line, to a base that side owns than to any base the other side owns, by the live owners its `SideView` shows (`director.in_rear`); bases are the finite-stock nodes except BRIDGEs plus both sanctuaries; a tie is not rear.
110. It moves with the front when bases flip.
111. Only a tracked player scout there counts, at its track's position.

**Interpretations.**
112. Hysteresis levels keep their state (`prov_level`, `ceiling`); a level may jump two steps but the tier steps one.
113. CP and provocation are integers in millionths, floor division throughout.
114. `dwell` is running ticks, added a window at a time and held at `min_dwell_s`.
115. The loader refuses a `half_life_s` / `window_s` whose reduced ratio has a part above 256 (`DECAY_RATIO_MAX`; the decay multiplier is found by an exact integer root whose cost grows with it).
116. `restore` refuses a Director state the clock could not have made (`provocation.validate`: windows, dwell, a tier that needs more windows than ran, budget, sector).

**Part 2 (NX-156): operations.**
117. `content/operations.yaml` (CONFIG-AND-CONTENT §8a) is loaded by `nexus.runtime.operations` (unknown job kind, selector or precondition, a cost above the CONFIG-AND-CONTENT §8a envelope, floor(`director.spend_frac.bravo` × the largest storage), a unit that cannot take its job: refused), threat memory is fed in `nexus.core.provocation` and decayed in `decide`, `nexus.core.operations` enumerates, scores and selects, `nexus.core.launch` pays, spawns and posts (all in the `director` slot, each window right after `decide`).

**Threat memory (§2).**
118. `convoy_attacks` (a hit on a carrier), `radar_strikes` (a hit on a RADAR_SITE), `recon_losses` by sector (a scout destroyed or knocked to Disabled) and `node_losses` by sector (a base of the side lost, which also starts its Retake window) count events in millionths, from any coalition actor, not only commanders' units (provocation stays the people's).
119. What one occurrence adds is `director.memory.weights` (1 each).
120. Each window every counter decays by one exact multiplier of `director.memory.half_life_s` (1,800 s: 30 windows halve it).

**Candidates and score (steps 3-4).**
121. Enumerated by (operation id, target id) for the operations enabled at the tier whose preconditions hold and whose selectors resolve (else the operation is dropped, TD-2): NODE targets are the view's nodes, SECTOR the theater's, RADAR the Static's non-Disabled radars (by base), CONVOYS one candidate over the Static's moving, unescorted carriers.
122. A live operation (a job with key `op:<op>:<target>:...` on the board) is not posted twice, and a tier runs at most `director.max_ops.<tier>` operations with jobs at a time (ALPHA 1, BRAVO none; null is no cap; Pattern of Life has no key, its operations are all routine), not counting the routine ones (those enabled at Pattern of Life, derived from the catalog's tiers; Q-SIM-84); the due cadence floor's capture operation may run one past the cap (`select`'s `over`, Q-TD-57); a capture operation on a node of the running victory hold is outside the cap, neither capped nor counted (`select`'s `hold`, Q-TD-46, NX-430).
123. Score = `director.op_priority` x target value (`score.target_value.<node kind>` for a node of the other side, else 1) x weakness (1 at full defense HP, linear to `score.weakness_max` 2.0 at none, from the view's defense HP over the node's maximum) x memory (RAISE: `1 + c`, c in events, undecayed counter / 1,000,000; LOWER: `1 / (1 + c)`) x `score.provocation_proximity` (a target in `last_provocation_sector` while the CP ceiling is one of `score.proximity_tiers`, default ALPHA) x, for RECON, `1 + s` (TD-5: s is 0 with a current track in the sector, `age / track_fade` of its oldest last-known track, 1 with none).
124. Noise: one `director` draw per candidate, `score x (1 + noise_scale x r / 1000)` with r in [-1000, 1000].
125. Selection is greedy by (score descending, operation id, target id) within the window budget, `max_spawns_per_window` and the live room below the EC-8 guard `sim.max_live_units_per_side`; an escort operation shrinks to the convoys that fit.

**Pay and spawn (steps 2, 7; Q-TD-8, Q-TD-12).**
126. The operation's cost is drawn once, at the node where its new units spawn (EC-13, NX-412 part 3 above; a staged operation's spawn nodes each pay their own units' share, FS-4), as `SupplyConsumed{SPAWN}`; units cost nothing more, so the budget is the stock.
127. One unit per template slot, kinds in turn, from an idle live Director unit of the kind first (lowest id; nothing spawned or paid for it: the cost is scaled by the units actually spawned, Q-SIM-84), else a new one, at that paying node, full of fuel and rounds, owner `ENEMY_DIRECTOR`, planned on the stock before the debit.

**Payment rule.**
128. The window's budget is a plan, not a reservation: operations launched earlier in the window (their carriers load on taking a job), garrison upkeep, Pattern of Life convoys and the capture slot draw on the same surplus.
129. So each operation is checked at launch against the real payable surplus (the same finite-stock bases `_pay` debits) for the units it will actually spawn, before it posts or spawns anything; if the surplus cannot pay the full cost the operation is skipped whole (no jobs, no units, no partial payment, no INTEL announcement).
130. `_pay` still raises if it is ever asked for more than exists: that is an invariant, not a path.

**Jobs (step 8).**
131. `post_job` per template job in order, each depending on the last job of the step before; the units claim at spawn.
132. A job still waiting keeps its claimants' leases; when the job before is DONE the dependant's expiry clock restarts and its claimants set off.
133. `STAGE`: go to the base and hold, DONE when every slot is claimed and every claimant is there, FAILED if the base falls.
134. `CAPTURE`: go to the node and stay, DONE when the node is the side's, EXPIRED at its expiry even with claimants (the clock restarts while a claimant is still driving).
135. A job another waits for is DONE when its goal is met even with no live participant.
136. A selector resolves as: `target` and `target_defenses` the target node, `nearest_own_base` the side's base nearest the target, `sector_point` the Recon point of the sector (Part 4), `each_convoy` one job per convoy (`ESCORT_CONVOY`, a follow order on the truck).

**DecoyBlink (Q-SIM-82).**
137. The radar at the target base goes dark for `director.decoy_blink.dark_s` (120 game s) and then emits again; the same radar cannot blink again for `director.decoy_blink.cooldown_s` (600 game s, from when it went dark); at most one radar blinks per window.
138. Directly: no job, no unit, 0 cost.
139. `DirectorState.dark` (base -> tick it resumes) and `blink_ready` (base -> tick it may blink again) are in the snapshot and hash.

**INTEL (step 5).**
140. `ThreatAdaptation{CONVOY_ESCORT | IADS_REINFORCED, sector, UP | DOWN}`: UP when an operation whose RAISE counter is `convoy_attacks` or `radar_strikes` launches with that counter above 0 (once per category); DOWN when the counter has decayed below `director.adaptation_down_below` (1 event).
141. Sector level only.
142. Operation jobs have urgency `director.job_urgency` (1.0).

**Idle units and retirement (Q-SIM-84).**
143. A Director unit with no job, order or path is idle; one idle for `director.idle_retire_s` (600 s, checked each window) is removed with no refund (a carrier still holding cargo is kept, so stock + cargo + consumed stays exact), reported as `UnitDespawned{reason: RETIRED}` (not a loss: no threat memory, stats or crew roll), so spent units never block `max_live_units`.
144. `DirectorState.idle` (entity id as text -> the tick it was first seen idle) is in the snapshot and bounded on load.

**STAGE and CAPTURE (Q-SIM-84).**
145. STAGE is DONE when every current claimant has arrived and every slot is claimed or its expiry has passed, and FAILS with no claimant left (the chain fails with it).
146. A CAPTURE whose claimants are still driving at its expiry gets a fresh expiry at most `tasking.capture_max_restarts` (3) times (`Job.restarts`, in the snapshot), then expires normally.
147. **Mid-bar hold (NX-483, both boards: the Static's `op:` CAPTURE and the coalition's `retake:`):** a CAPTURE job past its expiry does not expire while one of its claimants is within `capture.radius_m` of the node (any claimant there, even one that adds no capture weight, such as a garrison unit) and the side's bar there is live, so the flip credits its `JobDone` and the claimant is not pulled away before it.
148. It spends no restart and keeps no state: the hold ends with the bar, which flips (DONE) or drains to 0 (contested or abandoned; the job then expires at the next pass).
149. A claimant still driving inside the radius when the expiry passes gets a fresh clock first (a restart, above), so the hold applies once it stops or its restarts are spent.
150. A bar that may stand still with no end in sight holds nothing (`capture.stalled`), and its job expires as before NX-483: under `campaign.idle_floor.enabled`, the coalition-held forward airbase at no live viewer unit or the coalition's last strategic node (Q-TD-103); and a night-held Static bar (`DirectorState.held`, the §5 night cap), whose release each Static flip elsewhere moves on.

**Escorts without raids.**
151. With the cost at 10 and routine operations outside the ALPHA cap, ESCORT_CONVOYS also runs with no `convoy_attacks` (score 0.8); only the INTEL line needs a raid.

**Load checks.**
152. A snapshot is refused for a job waiting on itself or a later job, `dark` ticks past what the clock allows, a `blink_ready` at a node that does not exist (no upper bound: a hot reload may shorten `cooldown_s`, NX-401), a dark radar with no cooldown, and an idle unit that does not exist.
153. The catalog loader refuses an effect operation with a cost, a job operation with cost 0 and duplicate preconditions or tiers.
154. A hit on an already Disabled radar is not remembered.

**Tunable shapes (Q-DEV-21).**
155. The formula shapes are fixed, every coefficient is a key: memory `1 + k c` / `1 / (1 + k c)` (`director.memory.factor`), weakness linear from `score.weakness_min` to `score.weakness_max`, Recon staleness `1 + f s` (`score.stale_factor`), radars per window (`decoy_blink.max_per_window`), the UP threshold (`adaptation_up_above`), ReinforceIADS' damage share (`reinforce_damage_above`), the fewest convoys kept (`escort_min_convoys`) and the front's reach (`frontline_hops`).
156. Each default reproduces the behaviour before the key.
157. The target value of a node the Static holds is `score.own_node_value`.
158. Still in code: the noise draw's resolution (`NOISE_STEPS`, 1,000 steps: it sets the resolution of a draw and changing it reshuffles every seeded decision, so it is fixed with the RNG stream), and staleness 0 / 1 for a current / absent picture.
159. `nexus/core` holds no other outcome-affecting literal (NX-377): a test fails on a new one, and the list of what stays (scales, performance constants, structure) is in CONFIG-AND-CONTENT §6.6.

**Interpretations.**
160. The Retake window is `director.retake_window_min` (30).
161. Operations that target a coalition node need a `score.target_value` for its kind (no HQ or bridge).
162. A STRIKE job posted on a node whose defenses are already down completes at once (a goal met).
163. ESCORT_CONVOYS costs 10 (Q-SIM-82), so the Pattern of Life budget (10) can pay for it.
164. The board holds at most `tasking.scout_open_max` (3) generated scout jobs per side, so the Static's moving units cannot flood the coalition's board with scout jobs (claimed ones stay, then those posted, then highest urgency, ties by key), posts at most one new one per `tasking.scout_post_interval_min` (2), and does not repost a cell for `tasking.scout_cooldown_min` after its job ended.

**Part 3 (NX-157): Pattern of Life (Q-SIM-85).**
165. `nexus.core.launch` runs it after the window's operations; the pure parts (`patrol_via`, `convoy_base`, the garrison kind) are in `nexus.core.operations` and read only the view and `Own`.

**Garrison upkeep.**
166. `GARRISON_UPKEEP` (cost 8, priority 0.9, every tier, routine) has target `GARRISON`: the Static bases (not bridge or sanctuary) whose live `ENEMY_DIRECTOR` units with `Entity.home` = that base number fewer than the theater's `garrison_quota` (`Rules.garrison_quota`).
167. Its one `STAGE` job buys one unit of the kind `director.garrison.kinds` gives (FOB: ENEMY_ARMOR; AIRBASE: ENEMY_FIGHTER, ENEMY_ARMOR; HQ: ENEMY_ARMOR, ENEMY_FIGHTER; the kind the base has fewest of, ties by list order), never reused from an idle unit and spawned at the base itself (up to `replace_per_window` units, each of the kind it is then shortest of, at the catalog cost each) (not by `plan_deploy`: a road trip through a neutral crossing would flip it), with `home` set.
168. A live upkeep job on a base is not posted again.
169. Retirement (`_retire_idle`) skips the lowest-id units up to the quota of their home base while the Static holds it (`_within_quota`); a unit with no home, or whose base fell, retires as before.
170. `Own` carries each base's homed kinds and margin over the floor (negative below it).

**Board.**
171. `PATROL` is a job kind (`tasking.priority.patrol` 15, `fits`: any ground non-carrier).
172. The board never assigns it, and gives a unit with a `home` only a DEFEND of that base (`_board_may_give`): the Director takes other jobs for them (`tasking.take`), and an operation never reuses one (`_reusable`).
173. `Job.via` is the turning node; the claimant's path is the road to `via` then home (`_patrol_route`); DONE when a claimant is back at the base, FAILED with no claimant or when the base is lost.

**Timers.**
174. `last_patrol`, `last_convoy`, `last_offensive` (set when they fire; `last_offensive` only when an operation launched, so a failed attempt retries each window) and `last_flip`; due when `running tick - last >= period`, so they are frozen with the clock by a pause and independent of `sim.time_scale` (TD-1).
175. They start at 0, so the first patrol is one period in.

**Patrol.**
176. Per Static base, the lowest-id idle ground garrison units homed there (`patrol_slots` per job, up to `patrols_per_base` jobs) take the job at posting; the base is skipped while its patrols are out or when no unit or turning node exists.
177. `_recall` sends an idle homed unit away from its held home back (a road route for ground, straight for aircraft).

**Convoy.**
178. The `convoys_per_period` bases with the largest `missing x (GARRISON_UPKEEP cost) - (stock - floor)` (ties by id; above zero) each get a `RESUPPLY` job (key `op:POL_CONVOY:<base>:0`), taken by an idle carrier of `director.pol.convoy_kind` or a new one, within `max_spawns_per_window` and the live room (EC-8); a new carrier costs `convoy_cost`, from the surplus.
179. A base no truck can reach by the supply-run rule (`logistics.plan_run`: around nodes the coalition holds, over intact bridges) gets no convoy that period and nothing is spawned or paid; the period's slot is not passed to the next base (NX-413).

**Capture slot.**
180. At Pattern of Life, when `offensive_period_s` has passed since the last launch and the cap is not spent, candidates are the catalog operations with a CAPTURE job whatever their tier, ranked as usual (one `director` draw each), selected against the real surplus (`director.surplus`) and the live room (EC-8); the best one launches.
181. The cap check (no live viewer unit and `night_capped`) also drops capture operations from the normal window at every tier.

**Cap.**
182. `capture` stamps `last_flip` on every Static flip, and holds a later bar at `CAPTURE_FULL - 1` while `night_capped` at the faded spacing for the live viewer units (`night_spacing`, Q-TD-93), or at the full cap for a node already in `DirectorState.held`; the flip comes on the first tick after the cap ends (one node per cap: the others are held again).
183. A patrolling unit is not a capturer.

**Load checks.**
184. A snapshot is refused for a timer past the clock or one no window could have set, a `home` that is not a node or is on a unit that is not the Director's, and a `via` on a job that is not a patrol.
185. The loader refuses a garrison or convoy kind that is not an ENEMY mover that can stage or resupply, a node with a quota whose node kind has no garrison kinds, a quota with no GARRISON operation, and more than one GARRISON operation.

**Interpretations.**
186. (1) The patrol's turning node is the one toward the front, neutral or not (Q-SIM-86 replaces the held-only rule).
187. (2) The counts per window or period are keys (Q-DEV-21), default 1; the convoy costs 0.
188. (3) Probe-to-capture is not built: the slot takes the operations with a CAPTURE job (Offensive, Retake).
189. (4) Retired in NX-488 with the per-tier live caps: the live room is the EC-8 guard `sim.max_live_units_per_side`.

**Part 4 (NX-379): Recon that explores (Q-SIM-87).**
190. RECON costs 2 (was 5) and its one job is `SCOUT at: sector_point` for an `ENEMY_RECON_UAV`.
191. `nexus.core.operations.recon_point(view, rules, own, sector, kind)` resolves it, pure, from the `SideView` and `Own` (TD-2):

**The cells.**
192. The centres of a `director.recon.grid_m` grid (10,000 m, cells at `k x grid + grid / 2`) that lie in the sector.
193. A cell's staleness is the fresher (lower) of two readings (TD-5, FOW-6a): the track reading is 1 with no track of any kind within `director.recon.loiter_radius_m` of its centre, else the age share (`age / fade`, at most 1; `fow.track_fade_s`) of the freshest track within it, 0 for a current one; the look reading is 1 for a cell no Static sensor covered within `director.recon.memory_s` (3,600 game s), else the time since over that time.

**Visit memory.**
194. `DirectorState.looked` (snapshot and hash) maps a cell's centre (`x:y`, m) to the running tick of the last decision window at which a Static unit's sensor covered it (every ENEMY unit with a sensor radius, emitting and not an off facility, id order, cells ascending; `launch.look`, run each window before the operations), whether or not any track was there.
195. Marks older than `director.recon.memory_s` are dropped, so it holds only cells seen within that time (at most the theater's grid, 960 cells on strait-1); a restore refuses a key that is not the centre of a grid cell in the theater or a tick past the clock.

**The pick.**
196. Cells in order of staleness, highest first, ties by (x, y).
197. The first that passes: (1) the straight route from the base the scout is raised at (`launch_base`: the nearest Static base to the cell that spawns aircraft, is a landing base and has surplus over the forward-deploy margin, else the rear source; the same rule as `plan_deploy`) to the cell, widened by `loiter_radius_m`, crosses no marker with a ring whose last confirmed state is not Disabled (`tasking.ring_crossed`, the function `crosses_ring` applies to the board's markers, TB-2); (2) the scout can fly there, loiter and land at the nearest landing base with the bingo reserve left (`_sortie_fits`: fuel, speed and `loiter_s`; else it would turn for home mid-loiter).
198. With no cell that passes, the sector is skipped this window.
199. Only the outbound route is ring-checked: the return leg to the landing base after the loiter is not.
200. Unknown rings are not avoided, as for every unit: a scout can still be shot down by a site the Static has not discovered.

**The job.**
201. The unit is raised at `launch_base`, which uses the same `logistics.deploy_pool` and `nearest_by_air` as `plan_deploy` so the two cannot drift.
202. A point job never takes a second scout: the board's overfill (twice the slots when no free job is feasible for the unit, Q-TD-89) does not apply to it.
203. `Job.pos` is the point, `Job.node` and `Job.blob` are empty (the key stays `op:RECON:<sector>:0`); the unit is raised at `Where.origin`, the base the route was checked from, and a spare Director scout is reused only if it rests there.
204. `Job.arrived` is the running tick the scout began to loiter (snapshot format 22; 21 is refused).

205. **The loiter** (`tasking._loiter`).
206. When a claimant has arrived (orbiting at the end of its path), `arrived` is set.
207. Each board pass, a claimant with no path flies to the next corner of the square of half-diagonal `loiter_radius_m` around the point (E, S, W, N; the one after the corner nearest to it, clamped to the theater), so it stays within the radius.
208. When `director.recon.loiter_s` has passed since `arrived` the job is DONE, the claimant goes home (`logistics.go_home`: RTB to the nearest landing base) and is a spare unit again once it lands.
209. The job also ends DONE, and the scout goes home, when a ring discovered since the launch (not last seen Disabled) covers the point with the loiter radius of clearance.
210. A restore refuses a job position outside the theater.
211. A scout lost, or sent home at bingo, releases its claim; with no claimant `arrived` resets, and the job expires with its clock as any unclaimed job.
212. A lost scout counts to `recon_losses` as before.

**Part 5 (NX-401): StrikeBridge, "cut the lifeline" (Q-SIM-112, Q-SIM-120, Q-SIM-121; lead decisions, owner may veto).**
213. `STRIKE_BRIDGE` (cost 30, `director.op_priority.STRIKE_BRIDGE` 0.6, ALPHA and BRAVO, all PROPOSED) targets a NODE that is a bridge; its one job is `STRIKE at: target` for 2 `ENEMY_STRIKE_FIGHTER`s, with no STAGE (jets spawn at an airbase).
214. The claimants fire on the bridge by the STRIKE claim rule (`bridges.target`, Q-SIM-124), and the job is DONE when the bridge is down (`tasking`).

**Preconditions (closed list, `nexus.core.operations._holds`).**
215. `target_is_bridge`; `target_bridge_intact` (not in the view's `bridge_down`, so a bridge under repair is never a target, Q-SIM-115); `target_feeds_coalition_node`; `target_bridge_off_cooldown`; `no_bridge_contested` (Q-SIM-121's "one bridge at a time", lead reading, owner may veto: no bridge is down and none is the node of a live STRIKE job on the side's board, `Own.struck`; and `select` takes at most one operation with this precondition per window, greedy in rank order, so BRAVO, with no `max_ops` cap and budget 80, never strikes both bridges in one window or in back-to-back windows; a yes/no rule, so no `max_down` key).

**Feeds (`operations.fed_nodes`).**
216. The nodes the other side holds whose kind has a `score.target_value` and whose supply route from that side's sanctuary (`Supply.rear`) crosses the bridge's edge.
217. The route is `logistics.supply_path`, the rule its trucks drive by (Q-SIM-122, NX-407): intact roads (the view's `bridge_down`), entering no node the Static holds (neutral ground passable), the same helper `logistics.supply_route` calls with the world's owners, so the Director and the trucks agree on which bridge carries supply.
218. A node only reachable through a Static base is fed by no bridge.
219. Inputs are the roads, `SideView.owners` and `SideView.bridge_down` only: never tracks, units or occupancy (Q-SIM-112, Q-SIM-120), so units on or near the span change nothing.

**Score.**
220. The step-4 formula with the target-value x weakness factor taken as the largest `score.target_value.<kind>` x weakness (from that node's defense HP in the view) over the nodes the bridge feeds; nodes tied on it give the same factor, so the pick is order-free.
221. Memory 1 (no counter); proximity (the bridge's sector) and noise as for any candidate.

**Cooldown.**
222. `DirectorState.bridge_ready` maps a bridge to the running tick from which it may be a target again: at `BridgeRepaired` (`bridges.repair` calls `provocation.bridge_repaired`), each directed side stamps the repair's running tick + `director.strike_bridge.cooldown_s` (1800 game s, PROPOSED) as ticks.
223. A never-repaired bridge has no entry; entries are not pruned (at most one per bridge).
224. In the snapshot (format 27) and the hash; a restore refuses a key that is not a bridge (no upper bound on the tick: a hot reload may have shortened the cooldown since the stamp).

Notes: THREAT-DIRECTOR-NOTES.md §7a

## 8. Open questions

1. Forward reference: Q-GD-38 (lieutenants, NX-317).
2. Open: §5b active defense (Draft), AD-15, rows Q-TD-58 to Q-TD-61.

Notes: THREAT-DIRECTOR-NOTES.md §8
