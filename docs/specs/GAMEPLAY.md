# SPEC: Gameplay Rules

> **All numeric values in this spec are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). They become real only after the balance harness validates them.
Status: Approved (owner, 2026-10-20) · Tracker: NX-120…NX-149 · Inputs: Raw plans P206–225, P983–1009, P1139–1168; conversation C1–C48

Rules only. Narration, history, decision trails, examples and derived numbers: [GAMEPLAY-NOTES.md](GAMEPLAY-NOTES.md) (not normative). One section: `python3 scripts/spec_section.py docs/specs/GAMEPLAY.md <number or title>`.

1. All numbers below are **initial balance values** in `balance/default.yaml`.
2. They're tuned with the balance harness, not hard-coded.

3. **Timers (Q-CFG-8, Q-ALN-1, Q-ALN-4, Q-ALN-6, Q-ALN-23):** every duration in this spec runs on one of three clocks and is labeled with it:

4. **World time** (in the sim): ticks scaled by `sim.time_scale`.
5. It drives movement, logistics and combat (§5, §6), capture progress and decay (§8), bridge repair (§5), and the fog-of-war refresh and track fade (FOG-OF-WAR).

6. **Game time** (in the sim): unscaled ticks, so 1 game minute = 1 real minute while the sim runs.
7. It drives player-facing durations: Tasking Board claim lease and priority aging (TB-1, TB-3), idle handoff/retire (§4b), respawn delay (§4, Q-ALN-5), ability and command cooldowns, package fill wait (§7), objective period and victory/defeat hold (§9), campaign length, and the director's window, dwell, decay and Pattern of Life timers (THREAT-DIRECTOR TD-1).

8. **Real time** (outside the sim): a monotonic clock for chat rate limits and digest batching (CHAT-GATEWAY), and the taunt, GM auto-release, redemption and supply-drop limits (Q-ALN-4, THREAT-DIRECTOR, SUPPORT-REDEMPTIONS).
9. These are enforced before anything enters the sim.

10. World and game time are both deterministic and both freeze while the sim is paused; real time does not.
11. Config keys use friendly units (s/min) and are converted to ticks at load, rounding **up** so a timer is never shorter than configured (Q-ALN-6).

12. **Pause (Q-ALN-2):** a pause freezes the whole world: movement, combat and every sim timer on both clocks.
13. Commands that don't change the world still work while paused: `!me`/`!status`, `!quiet`, and joining the reserve queue (a `!join` while paused always queues, even when a slot is free, Q-ALN-26).
14. Every other command gets a "war paused" reply in the digest (FB-UX-5) and has no effect (STATE-MACHINES §4.4).
15. Staff safety actions always work while paused (ban, forget, kill switch, pause/resume/end); a config reload waits until resume, and director overrides are rejected (Q-ALN-24).
16. Unban, unit purges and approved callsign changes also apply; advisor choices and GM commands other than a GM release are rejected, and channel-points redemptions are refused and refunded (Q-ALN-36, Q-ALN-37).

17. **First-build scope (Q-PROD-8):** the first build ships the core loop, damage states (COMBAT), base defense HP (§8), limited munitions (§5), fog of war, director tiers with Pattern of Life, and the Tasking Board (§1b).
18. Stances (`!stance` and deploy-time stance), CSAR and crew rescue (`!rescue`), packages, carry-over, world events, base upgrades and weather come later behind feature flags; their rules are in [GAMEPLAY-LATER](GAMEPLAY-LATER.md) (Q-GP-1).
19. With stances off, every unit behaves as `standard`.

## 1. Core loop (what a viewer does in 30 s)

1. Type `!join strike|recon|logi`.
2. Within 500 ms (server side) a radar ping and their callsign appear at a base.

3. With no parameters, the unit takes the best open job from the **Tasking Board** (§1b) at once; with a node it goes there; with `hold` it waits at base (Q-GP-23).
4. Assisting the current objective is one of those jobs, not an automatic route.

5. Optionally type `!target <node>`, `!rebase <node>` or `!rtb`.

6. The unit completes or fails its mission, and the viewer sees a contribution line in the ticker.

## 0. Parity rule (owner, 2026-10-17)

1. **Both sides play by the same rules.**
2. The Static has the same mechanics as the Quorum: scouting, fog of war (FOW-4), supply and starvation, rebasing, damage states, ammo, and rescue/recovery where it applies.
3. Any new mechanic must say how it applies to both sides, or explicitly justify an asymmetry (e.g. the sanctuary base) in its spec.

4. **Asymmetry, idle floor (Q-GP-44, Q-TH-7):** only the coalition's `forward_airbase` and its sanctuary's last point of defense HP (and the last base, below) are protected while no humans play; the Static has no such floor because players are always present when it is attacked.
5. Default; Q-CFG-16 option: `campaign.idle_floor.enabled` and `sanctuary_min_hp`.
6. **Last base (Q-TD-93, NX-474; Q-TD-103, NX-481):** the only strategic node (`campaign.strategic_node_kinds`) the coalition still holds, whichever it is (the `forward_airbase` or a FOB), is also protected, at any viewer count (under the same `enabled` switch): no Static bar starts or fills there, a running one decays or is drained as usual, so there is always one base to fight from.
7. The never-captured sanctuary is not a strategic node and does not count.
8. The protection lifts once the coalition holds a second strategic node.
9. On the `forward_airbase` with no humans the idle floor above applies instead (its bar does not decay either).

10. **Asymmetry, AI escorts (Q-GP-45):** the Static's director escorts its convoys through threat memory, while the coalition AI garrison never escorts: escorting coalition convoys is the players' decision, so unescorted convoys are a real risk the Static can punish.

11. **Asymmetry, emission control (Q-FOW-13):** only the Static's director can turn its sites dark in the first build (a deception tool); coalition parity arrives with SEAD (FOG-OF-WAR FOW-11).

12. **Asymmetry, spawn cost (Q-TD-12, Q-TD-26):** one spawn rule for both sides: every spawn draws its cost from the stock of the node it spawns at, the source included, so a unit paid from the source has to travel ([ECONOMY](ECONOMY.md) EC-13).
13. The one exception is the switch `economy.free_viewer_spawn` (default on for live streams): a viewer's own spawn at the coalition's sanctuary draws no stock, so joining never hurts a person.
14. The AI garrison and the director always pay, and agent-vs-agent harness profiles turn the switch off.

15. **Asymmetry, capture jobs (Q-TD-14):** `CAPTURE` jobs exist only on the Static's board in the first build; coalition captures stay player-driven (`!join logi <node>`, free orders, the objective), and the coalition AI garrison never initiates offense.
16. **Sole exception, the retake job (owner, 2026-10-28, Q-TD-94 (b), Q-TD-99; NX-475, in code):** the coalition board posts one `retake:<node>` CAPTURE job on a start node it lost (§1b), so a quiet stream that lost every base has assigned work to win ground back.
17. Every other coalition capture stays player-driven.

18. **Asymmetry, quiet-stream capture (Q-SIM-26):** the `quiet_mult` easing in §8 applies to the coalition only.
19. Applying it to the Static would make a quiet stream easier for the enemy as well, which defeats its purpose.
20. It is a pacing aid for small crowds, not a rule of the fiction.
21. Default; Q-CFG-16 option: `capture.quiet_sides`.

22. **Economy, both sides (Q-GD-30, Q-TD-16..18; [ECONOMY](ECONOMY.md) EC-1..4):** each side's source holds a finite pool that gains income per window (a floor plus a share per strategic node held), capped by storage that also follows held nodes.
23. Every live unit pays upkeep from its home base.
24. The Static's budget is real stock, shipped by convoy from its rear source (factories are parked, Q-GP-41), which the coalition can raid and starve; its rear source sits behind its capturable HQ (the coalition's sanctuary can never be captured, §9).
25. Same rules and same keys for both sides.
26. **Unlimited mode (Q-TD-28, EC-15):** like unlimited ammo, a campaign or test option `economy.unlimited.<side>` (default off, owner/Admin at setup only) makes that side's pool endless and its units free of upkeep.

27. **Static tasking (Q-GD-34):** the Static uses the same Tasking Board (§1b).
28. The director is the strategic layer that creates jobs on the Static's board (stage, escort, strike, defend, reposition), with the same job types and mechanics as the Quorum.
29. It may compose richer job combinations but gets no unique powers.
   - **Sector scouting (Q-SIM-134, NX-512):** both boards post a point scout job on the stalest-point rule of THREAT-DIRECTOR Part 4, with the same keys (§1b item 203).

30. **Lieutenants (Q-GD-38, P4, NX-317):** later, sectors may be run by Static lieutenants, each a Threat Director profile on the same mechanics.
31. Not in scope before P4.

## 1a. "Did my command work?" feedback (owner requirement, Q-MOD-1)

1. Viewers see a generated callsign, not their username, so the game must connect "me" to "my unit" unmistakably.
2. Otherwise they assume nothing happened and leave.

3. **FB-UX-1 Chat confirmation:** the bot's batched digest names the platform user and their callsign, e.g. "@SaltyUser → VIPER-27 deployed (strike) from WEST BASE".
4. It's sent within platform rate limits (Twitch as a moderator: 100 messages / 30 s, per PLATFORM-REALITY-CHECK), with up to N mentions per digest message (N PROPOSED).

5. **FB-UX-2 On-screen recruit strip:** for 10 s after each spawn, a "NEW RECRUITS" strip shows the callsign, platform icon and role, with a ping on the map at the spawn point.

6. **FB-UX-3 `!me`:** highlights your unit for 5 s, and the next chat digest repeats your callsign and status.
7. Also works while you're in the reserve queue (shows your position).
8. `!status` is a pure alias with identical behavior (Q-UX-12).

9. **FB-UX-4 First-time hint:** a commander's first successful command adds a one-time "New? You're VIPER-27.
10. Type !me anytime." line to the digest.

11. **FB-UX-5 Rejections are visible too.**
12. Reasons like "unit in sortie" or "respawn in 12 s" are batched into the digest with the callsign, never silently dropped.

13. **FB-UX-6 Measure it:** track the share of first-time commanders who issue a second command (NX-036).
14. A low value means the feedback isn't working.

## 1b. Tasking Board (owner decision 2026-10-17, Q-GD-26)

1. A shared queue of **jobs** the system generates from the live situation, so every unit, human or AI, always has something useful to do:

2. **Job types (first build, Q-GP-5; rescue a downed crew joins with CSAR, GAMEPLAY-LATER §6a):** resupply a starving base or stock a forward base below its target (Q-SIM-100), scout a sector or blob, escort a convoy, defend a threatened node, strike a target, repair a bridge, assist the current objective.
3. Damaged facilities raise the urgency of a resupply job to their base, since facilities repair from base stock (Q-GP-47).

4. **Each job has:** a priority (Q-GP-20: `tasking.priority.<job_kind>` × an urgency multiplier of 1.0–2.0 from the triggering condition (a stocking job's is below 1.0, Q-SIM-100), such as the node's supply level, the threat or danger near it, or the objective flag, plus linear aging, TB-3; refined in playtests), the role(s) that fit, a **slot count** (how many units it needs), and an expiry.

5. **Assignment:** a unit with no explicit order takes the highest-priority open job matching its role.
6. Slots prevent pile-ups: a job is skipped once its slots are full, unless no job with a free slot is one the unit can fly or drive (**Q-TD-89, NX-465; in code**, both sides, no key): a free job counts only if it is feasible for that unit (its route crosses no known ring, it reaches it, and a ground unit has a road), so one free job behind a ring no longer keeps every unit off the reachable full ones.
7. A free job the unit could fly after a rearm step still counts as free: it takes the rearm step (below), as before.

8. **AI garrison** units are ordinary units: they can be destroyed and repaired like any unit, and upgraded only through player actions, never by other AI (Q-TD-11; upgrades are GAMEPLAY-LATER §5a).
9. The garrison pulls from the same board, but only takes jobs no human has claimed, and releases them when an operator wants one (default; Q-CFG-16 option `tasking.human_displaces_ai`).
10. **The AI garrison never initiates offense**: it takes defend, resupply (which also repairs facilities, Q-GP-47), scout and repair bridge jobs (rescue jobs join with CSAR, GAMEPLAY-LATER §6a; default; Q-CFG-16 option `tasking.ai_jobs`, in code DEFEND, RESUPPLY, SCOUT and REPAIR_BRIDGE), never escort or patrol jobs (Q-GP-45: escorting is the players' call; default; Q-CFG-16 option `tasking.ai_excluded_jobs`), and joins strike jobs only when a player started them (objective; later also a rally call or player-led flight).
11. **Sole exception (Q-GD-31):** it may counterattack a node the coalition just lost, within a configurable window (PROPOSED ~15 min), using only units still able to fight (not Disabled or Destroyed).

12. **Feasibility:** a unit only takes a job it can reach and complete with its current fuel and munitions.
13. Otherwise it first takes a rearm/refuel step (nearest base with stock, Q-GD-17).
14. **A starved base does not trap it (Q-TD-88, NX-464; in code):** a unit landed at a base below its starvation floor, whose capped tank (`logistics.starved_loadout.fuel_frac` of a full one, or what it holds if more) cannot serve the job, flies to the nearest landing base not below its floor that it can reach on the fuel it has and from which a full tank flies the job (ties by node id; NX-467), its sanctuary included (unlimited stock), and refuels there; with none it stays and fills to the cap first.
15. A unit landed at a base with no stock (it sells nothing) leaves whatever it is short of, for the nearest base with stock in reach whose tank serves the job (a starved one whose capped tank does, or one not starved whose full tank does); with none it waits there for a truck.
16. A unit the capped tank serves, short only of rounds or of fuel the base can still sell, stays, as at a base that is not starved.
17. An airborne unit on its refuel step does the same before it lands (NX-467): when the nearest landing base with stock is starved and the capped tank there (or what it would land with, if more) cannot serve the job, it flies to that hop instead, and lands at the starved base only when there is none.
18. RTB (COMBAT §5.6, bingo) still picks the nearest base, starved or not.
19. Both sides (§0); no new key.

20. **Logistics routing (Q-GP-24):** a supply job sets the *destination*; the route is planned automatically along roads/sea lanes.
21. `!join logi` with no parameters takes the best resupply job, or the retake job when that ranks first (Q-TD-100, below).
22. `!join logi <friendly node>` makes that node the delivery destination.
23. `!join logi <neutral or enemy node>` is a capture run with no cargo. **Its truck starts at the nearest friendly forward base (Q-TEST-14, Q-SIM-135; NX-513; lead details PROPOSED, owner may veto):** the §4 GP-7 forward-deploy rule for a ground unit (`logistics.plan_deploy`): a theater `spawns` node for GROUND that the side owns, with finite stock at least `logistics.forward_deploy_min_surplus` above its starvation floor, nearest the target by road (ties by node id), with a road route to it; otherwise the sanctuary, as before.
   - The truck loads nothing and pays nothing (`logistics.loadout_cost.LOGI_TRUCK` is 0), so no stock moves: the surplus test only keeps a starved base from being a start. The bare `!join logi` that takes the retake job (item 222) plans the same run; a column truck following a capture-run leader starts at the same base.
   - Switch `logistics.capture_run_forward_start` (true; false starts every capture run at the sanctuary, the A/B control).
   - **Parity:** the Static's capture columns already start at `plan_deploy`'s base (THREAT-DIRECTOR §4 item 7); this makes the coalition's the same rule.
24. **Source:** the nearest reachable friendly base whose stock is above its own starvation threshold, with the sanctuary as last resort, so a truck never strips a base into starvation; cargo = min(capacity, that base's surplus).
25. **Supply runs avoid enemy-held ground (Q-SIM-122, NX-407; in code):** every road a resupply or stocking run plans (the source pick, the pickup leg, the run, a reroute after a cut) enters no node the other side holds (`bridges.enemy_held`); NEUTRAL nodes stay passable, unlike the patrol's rule (`bridges.not_held`), so a node past a still-neutral crossing can be supplied.
26. The run's own start and destination are allowed.
27. Both sides follow it (§0).
28. A capture run, a unit going home or escaping a captured base, a truck diverting from a lost node, a REBASE, a follower, a forward-deploy and garrison recall keep the old road search (down bridges only), so a unit fleeing still drives through enemy ground when that is its only road.
29. A loaded supply truck stopped on ground the other side does not hold, with no such road to a friendly base, holds there with its cargo and leaves once one opens (Q-SIM-126).
30. A supply run or a repair crew (Q-SIM-125) whose remaining road enters a node that has just turned enemy turns back and replans around it in the tick of the flip (`bridges.reroute` with `taken`, called by the capture flip), the same turn-back as after a cut; a supply run's destination is exempt (it arrives, then diverts), a crew's bank is not (it takes the other bank when that has a road), and neither is an empty truck's pickup source (the leg stops, `Entity.pickup` is cleared and the claim's lease frees the truck for a new reload plan); with no road it stops at the last node before that node (NX-413).
31. **Stocking runs (Q-SIM-102, NX-389):** a run to a base that is not starving, has no damaged facility and is below its forward stock target (§5) counts a source's stock above that source's own target instead of its floor, so forward stock comes from the rear and never moves back and forth between bases below target; a parameterless `!join logi` that takes such a job follows the same rule.
32. En route, `!target <friendly node>` changes the destination with the cargo aboard, and `!rtb` unloads at the nearest friendly base, so nothing is lost.
33. Choosing the source (`!join logi <from> <to>`) is parked.

34. **Follow, escort and lead (Q-GP-31):** a friendly unit's callsign is accepted wherever a node is (`!join strike VIPER-27`, `!target VIPER-27`).
35. Your unit follows and escorts that unit: it keeps station, engages what threatens it, and re-tasks when the followed unit dies or despawns (when it lands, followers land with it and keep following).
36. **Station by domain (Q-GP-32):** a ground combat unit following a truck or convoy moves ahead on the same road (`tasking.follow_station_m.<domain>`); an aircraft following a ground unit flies overwatch and engages air threats and detected air-defense sites on the route; a truck following a truck falls in behind as a convoy column that keeps station on its leader, and an escort job for the lead truck covers the column; an aircraft following an aircraft flies as wingman.
37. If the followed unit stops, followers hold station; if it reaches a base, they land or park there.
38. **Followers still do their own role's work:** a truck in a column loads at a source by the §1b source rule and unloads at the column's destination, a striker still engages, and a recon unit still scans.
39. Following sets station and route, never replaces the role.
40. **Chains (Q-GP-33):** a follower may itself be followed; each unit keeps station on its direct leader, so repeated follows build a column.
41. Following yourself, or a follow that would close a loop, is rejected with `FOLLOW_TARGET_INVALID`.
42. When a leader in the middle of a chain leaves, its followers re-attach to that leader's own leader, or re-task if there is none.
43. Column length has no cap.
44. Leading needs no command: anyone can follow you, and the overlay shows "VIPER-27 + 2 following".
45. Only same-side units can be followed (AUTO units included).
46. **Follower credit (Q-GP-42):** credit follows outcomes, not jobs: whatever the leader achieves, on a job or a free order (a delivery, a capture, a kill, a facility disabled), followers within station range share a capped portion of that outcome's merit (`progression.follower_share`, `progression.follower_share_cap`, PROPOSED).
47. Coordinated free play counts; a follower far out of station gets nothing.
48. Packages (shared target, XP share, NPC fill, a lead rank) stay in GAMEPLAY-LATER §7.
49. **Escorts answer attacks (owner, Q-SIM-76):** an armed follower of a convoy or column (ground or air) does not ignore an attack from any side.
50. A *group threat* is a tracked enemy that fired at any member of its group (leader, column trucks, other escorts) within `tasking.escort_threat_memory_s` (60 world seconds), or whose kind's catalog weapons reach a member now (never its live ammo: hidden state); an untracked attacker is not one (fog).
51. Escorts shoot group threats before other targets (units first, CB-1 order among them), break station toward the nearest one they can hit until it is in weapon range (a landed aircraft escort takes off for an air threat even in range, since it cannot fire at aircraft from the ground, COMBAT CB-7, Q-MV-19), never farther than `tasking.escort_leash_m` from the convoy (measured from the leader and unarmed followers, so escorts cannot leapfrog away; a threat that far is not chased), and return to station when none remains.
52. A ground escort answers along the road passing nearest the threat, one leg at a time, and keeps station when no leg leads closer.
53. Follow arrives through `!join <role> <callsign>` only (`!target` has no handler yet); the JOIN carries the leader's entity id, resolved from the callsign before the command is built (NX-374 part 2).
54. Rejected with `FOLLOW_TARGET_INVALID`: an unknown, other-side, Disabled or STATIC leader, a ground unit after an aircraft (no station to keep), a self-follow or a loop.
55. Station distances are `tasking.follow_station_m` (PROPOSED, Q-SIM-76): a ground combat unit `escort` 500 m ahead of a truck on the leader's road (road distance to the leader's destination; a unit mid-road may turn back), a truck, or any ground follower of a non-truck, `column` 200 m behind, an aircraft `overwatch` within 3,000 m of a ground leader (it flies there and orbits), `wingman` 1,000 m off the right of an aircraft lead.
56. A follower catches up at its own top speed, then matches the leader's speed and never overshoots; a leader stopped at a base (any node but a BRIDGE) draws ground followers all the way in (they park, trucks unload) and aircraft land if it is a landing base, taking off again when it leaves; stopped elsewhere, ground followers within twice the station hold.
57. A column truck spawned by `!join logi <callsign>` loads at the source for the leader's destination and unloads there.
58. A leader that dies or despawns hands its followers to its own leader, else they return to the board; a Disabled leader likewise.
59. A unit sent home stops following.

60. **Escort jobs (Q-GP-29, Q-GP-47):** when a truck's route passes within a detected threat (a discovered air-defense ring whose last confirmed state is not Disabled, or a currently tracked enemy; last-known tracks and unseen emitters do not count), the board posts an `escort convoy` job for players' strike and recon units.
61. Taking it is just a follow order on that truck (station by domain, below), and it expires when the truck arrives.
62. The coalition AI garrison never takes it (Q-GP-45).
63. The job is `ESCORT_CONVOY`, key `escort:<truck id>`, 2 slots, priority 40 (`tasking.priority.escort_convoy`, `tasking.slots.escort_convoy`), urgency 1.0, posted for each carrier with a road path that follows no one (a column is covered by its lead truck) whose route, from its position through its path nodes, passes within a discovered ring or within `tasking.defend_radius_m` of a tracked enemy (the radius is an interpretation: the spec names none) (NX-374 part 2).
64. Armed and recon aircraft of either side fit it (the Static's AI takes it by the same rule); an aircraft's ring check does not apply to it.
65. It ends DONE when the truck has no path left (`JobDone` lists the active followers as participants; no merit is awarded yet, that is PROGRESSION, Q-GP-42), EXPIRED if unclaimed by then or once the threat is gone, FAILED when the truck is lost or Disabled while claimed (the claim is kept until that verdict); a claim is released when its follow order ends.
66. **Repair crews (Q-SIM-118, NX-373 part 2; lead decision, owner may veto):** while a coalition carrier holds a REPAIR_BRIDGE claim, on the way or parked at the bridge's stop, the board posts the same job for it (`escort:<truck id>`, same slots and priority) with no threat test, naming the bridge as its node (option `tasking.escort_repair_crews`, default on).
67. It ends DONE when the bridge is repaired (no participant: EXPIRED), FAILED when the truck is lost or Disabled while claimed, EXPIRED when the truck drops the repair job or nobody claimed it by then; a crew parked at the stop with no path left does not end it.
68. The coalition AI garrison never takes it (Q-GP-45).
69. A ground follower of a truck at a bridge's stop drives out along the bridge's road and holds within twice its station of the stop (`follow._drive`); a parameterless JOIN never takes an escort job.

**Player patrols (Q-SIM-94, NX-382; in code).**
70. So a player has real work at quiet times, the coalition's board posts `patrol:<node>` jobs on **front-line nodes**: coalition-held nodes (not a sanctuary or bridge) with a road neighbour the coalition does not hold, at most `tasking.patrol_max_nodes` (PROPOSED 3) at once, those nearest a node the other side holds first (ties by node id).
71. It posts them only while the side has an idle armed or recon viewer unit (the staffing rule below).
72. Priority `tasking.priority.patrol` sits below STRIKE and DEFEND (the existing key, 15), so a patrol never takes a unit a strike or defense needs; slots `tasking.slots.patrol` (PROPOSED 2).
73. Armed and recon units of either domain fit it (not carriers); the coalition AI garrison never takes it.
74. A ground unit drives to the node by roads through coalition-held nodes only and holds there; an aircraft orbits the node at `tasking.patrol_orbit_m` (PROPOSED 5,000 m) and skips the job if that orbit crosses a discovered ring last seen not Disabled (TB-2).
75. The job is done after `tasking.patrol_dwell_s` (PROPOSED 300 game s, so an aircraft can finish one on a tank, lead decision) on station, then the unit returns to the board.
76. **A patrol never enters a node the coalition does not hold.**
77. It does what any unit does on station: its sensors reveal enemies (which feeds scouting and discovery credit, PROGRESSION §2) and it engages by the ordinary rules, so it provokes the Director only through the existing provocation rules (firing, THREAT-DIRECTOR §5a), never by patrolling.
78. Patrols are the counterpart of the Static's PATROL job (THREAT-DIRECTOR §5a), with the same job kind.
79. Key `patrol:<node>`, urgency 1.0, `tasking_gen._patrol` (NX-382).
80. Interpretations: the order is the exact squared straight-line distance from the node to the nearest node the side's view shows the other side holding (as the idle strike targets are ordered by straight-line distance); a road neighbour "not held" includes neutral and unknown ones; "viewer unit" is a COMMANDER-owned unit that is idle (no job, no order, no path, not Disabled, not RTB) and armed or recon, the NX-380 rule without its ammo test; no tier gate.
81. A new unit's parameterless JOIN never takes a patrol (its route plan does not check ownership); the board gives it one at the next pass.
82. A ground unit's route is the shortest road route through nodes the side holds only (none: it takes no patrol).
83. An aircraft flies to the node and then to the next corner of a square of half-side `tasking.patrol_orbit_m` around it (the scout loiter's corners); the ring check treats `patrol_orbit_m` as clearance, along the whole route.
84. The dwell clock starts when the first claimant is on station (restarts with no claimant) and the job is DONE `tasking.patrol_dwell_s` later, crediting its active claimants; the units stay where they are and are idle again, so the same patrol may be posted again and they can re-patrol.
85. The job FAILS, and its units go home or stop, when its node, or a node on a claimant's route, is no longer the side's; a ground unit mid-edge whose route home is clean continues to the node ahead and then home, otherwise it goes to the end of its edge the side still holds (the node it left first, else the one ahead), and with neither held it stops (Q-SIM-109); the same applies to a Static patrol, using the unit's side; this is checked every tick, before movement, for claimed patrols only, so no claimed patrol enters a node it lost (after a patrol fails the unit is an ordinary unit again).
86. At each board pass a patrol claimant is released, and then assigned normally, when an open job of higher priority with a free slot exists that the unit fits and would pass the board's own assignment checks for (route, ring, fuel), so a patrol never holds a unit a strike or defense needs and a unit never drops a patrol only to be refused.
87. Preemption applies to an aircraft at any time and to a ground unit once it stands on a node (the board routes a ground unit only from a node), so a ground patrol on the road is preempted when its transit ends.
88. The Director's patrol keeps its ground-only garrison crew.

89. **Logistics conduct (Q-GP-24, Q-GP-47):** merit counts only delivered cargo and completed captures (PROGRESSION).
90. Until the conduct system (NX-291) defines detectors, staff see plain per-commander logistics stats in the Command Center (runs started, delivered, abandoned; cargo returned) and judge patterns themselves; nothing is punished automatically.

91. **Visible:** the overlay shows the top few open jobs ("NEEDED: supply to WEST FOB") so lurkers learn what matters, in the rotating HUD panel at double frequency (Q-UX-11, OVERLAY).

92. **Free movement and auto-tasking (Q-GP-19, Q-GP-23):** a player can always send their unit wherever they choose.
93. Auto-tasking happens only when the command has no parameters: `!join <role>` takes the best matching job at once, with no hold at base.
94. `!join <role> <node>` goes straight to that node and does not auto-task until that order completes.
95. `!join <role> hold` waits at base until given an order.
96. A player can redirect the unit en route with `!target`, `!rebase` or `!rtb`, within the command rate limit (CHAT-GATEWAY); `!target <bridge>` strikes the bridge rather than holding it (Q-SIM-124).
97. Any explicit order suspends auto-tasking until it completes.
98. There is no decision window.
99. **Direct orders hold (owner, Q-SIM-110; in code, NX-398):** orders off the board are encouraged and must never break or stick.
100. An armed unit (a round left in any weapon) that reaches the node of its `!join <role> <node>` order holds station there: an aircraft orbits the node as any idle aircraft does, a ground unit stands on it, and both engage by the ordinary CB-1 targeting.
101. **An order to a friendly or neutral site defends it (owner, Q-SIM-124; in code, NX-408):** the unit goes there and patrols or defends it, and never fires on it.
102. Every bridge is a NEUTRAL node, so a plain order never drops a bridge, whichever side holds its banks; dropping one takes an explicit strike (a STRIKE job; later `!target`).
103. The Static strikes bridges with its STRIKE_BRIDGE operation (NX-401, THREAT-DIRECTOR §7a Part 5): two strike jets on an intact bridge on the coalition's supply route to a node it holds, one bridge at a time, from ALPHA, chosen from roads and owners only, never from units on the span.
104. The order ends, and the board may task the unit at that pass, at the first of: bingo fuel or RTB (the unit has a path home), ammo out (every weapon empty), landing (a GOTO to its own landing base), Disabled, a new order (`!rebase`), or `tasking.order_dwell_s` (PROPOSED 600 game s, a strike jet's whole tank, so a jet bingos first) after the hold began.
105. A hold on a bridge outlasts the bridge's fall: the unit keeps guarding the repair crews (Q-SIM-127, lead decision, owner may veto; it no longer ends at the next pass as Q-SIM-115 had it).
106. A unit that stopped short of the node (a ground unit cut off by a down bridge) does not hold.
107. An unarmed unit (a truck, a recon UAV) hands back as before: at the first pass after it arrived, its unloading stop ended and any capture run is done.
108. **Orders to the Static's rear (owner, Q-SIM-111; in code, NX-399):** `!join strike static-rear` is accepted as a deep raid: the rear stays untouchable (CB-10, no win effect), the raider holds there as above and engages Static convoys and aircraft that pass, and the raid adds no provocation weight.
109. `!join logi <node>` to a node that can never be captured (its kind is in `capture.uncapturable_node_kinds`, which covers the Static's rear and bridges) and that the coalition does not own is rejected with `NODE_INVALID_FOR_UNIT`; the coalition's own sanctuary is still a valid delivery.
110. The kernel's acceptance is the unit's `UnitSpawned`; a reply that says "deep raid" belongs to the chat and overlay layer (FB-UX-1), which does not exist yet.

**Robustness (Q-GD-37).**
111. These apply to both sides' boards:

112. **TB-1 Lifecycle:** a job moves OPEN → CLAIMED → ACTIVE → DONE | FAILED | EXPIRED.
113. A claim is a **lease** (`tasking.claim_lease_s`, game time, Q-ALN-23): if the claiming unit makes no progress within the lease, the claim is released and the job returns to OPEN.
114. A job ends DONE only with a participant, else EXPIRED (unless another job waits for it): a claimant still making progress, or, for a STRIKE job, a unit that fired at the job's target (the node's defenses or bridge, or a facility of that node) while holding the claim, even if it has since gone home (RTB with its bombs spent) and lost the claim (Q-TD-87, NX-463).
115. `JobDone` lists every participant.

116. **TB-2 Feasibility pre-check:** before claiming, a unit checks fuel, munitions, a route, and known threats on that route.

117. **TB-3 Priority aging:** an open job's priority rises the longer it waits (per game-time minute, Q-ALN-23), so low-priority jobs are never starved.
118. An unclaimed coalition resupply job, which no longer expires unclaimed (Q-SIM-131, below), ages for at most `tasking.expire_min` minutes, about the most it could wait unclaimed before NX-492 (then at most `expire_min` less one board pass, about 14.9 points), so it ranks about as before; a claimed one ages without a cap, as before (Q-SIM-132 (a), lead decision, owner may veto; in code: `tasking.priority`).
119. The retake job does not age at all (Q-TD-107).

120. **TB-4 Slots and dedupe:** every job carries a slot count and a dedupe key.
121. Generating a job whose key matches an open job updates that job instead of adding a second one.

122. **TB-5 Deterministic assignment:** units are assigned in a stable sort order with a seeded tie-break drawn from the dedicated `tasking` RNG sub-stream, which no other system shares (Q-ALN-7), so a replay reproduces every assignment (SIM-CORE).

123. **TB-6 Cadence:** the board is re-evaluated every N ticks (configurable, PROPOSED), not every tick.

124. **TB-7 Preemption:** a human order always wins over a board job.
125. Emergency preemption of AI-run units is deferred (Q-GP-5).

126. **TB-8 Dependencies:** a job may depend on another (e.g. repair bridge, then convoy) and can't be claimed until that job is DONE.

127. **TB-9 Per-side fog of war:** each side builds its board only from its own fog-of-war view (FOW-4).

128. **TB-10 Logged outcomes:** every job's lifecycle and outcome is emitted as sim events and **stored durably** (Q-ALN-16), for recap stats (e.g. "most supply delivered"; "most rescues" joins with CSAR), AAR stats and balance analysis.
129. A job completed by a commander's AUTO unit is recorded as an **AUTO assist** for recaps only; it never counts toward XP, merit or leaderboards (Q-ALN-30, PROGRESSION).
130. The same holds for every other action by an AUTO unit, such as a kill, a supply delivery or capture participation (Q-ALN-34, PROGRESSION PROG-12).

131. **TB-11 Command Center:** both boards are visible in the Command Center.
132. A GM can inject jobs into the **Static's board only** (Q-ALN-11, GM scope §9c); a GM never injects jobs into the Quorum's board.

**Generated jobs (NX-374 part 1, Q-SIM-73; SIM-CORE §4 Tasking Boards).**
133. Both sides' boards run every `tasking.reeval_every_ticks` running ticks.
134. Jobs, by the key they dedupe on:

135. `resupply:<node>`: a node the side owns with finite stock below its starvation floor, or with damaged facilities (Q-GP-47).
136. Urgency: 1.0 plus the larger of the stock deficit share and the facilities' missing-hp share.
137. **Forward stock (Q-SIM-100, NX-389; in code):** a node below its stock target (`logistics.stock_target_frac`, 0.8 of its maximum) gets the same job (stocking), urgency `tasking.stock_urgency` (0.5) plus `tasking.stock_front_bonus` (0.25) on the front line (the patrol rule below), below 1.0 so a starving or damaged base ranks first; when both apply the higher urgency wins.
138. Both sides' boards post it (the Static's only while it has a live carrier); an unclaimed coalition one does not expire by `tasking.expire_min` while it is posted, so LC-1's age counts from its first posting (Q-SIM-131, NX-492; TB-1 line below).
139. A sanctuary has no stock limit and never gets one.
140. Slots: one per `tasking.resupply_stock_per_slot` of missing stock (to the node's maximum; for a stocking-only job, not starving and with no damaged facility, to its stock target, so stocking fills up to the target), 1 to 3 (NX-473, in code: the cap rises with a starving or damaged base's shortfall, §5 LC-3, and coalition AI trucks fill slots viewers leave open, §5 LC-1; both off at the shipped no-op values, Q-TD-113).
141. Done when a claimant stands at the node with its cargo gone (the delivery stop ended); a truck still unloading at a friendly base that takes stock gets no job elsewhere until its cargo is gone or the base is full, but may take this job for the base it stands on (it stays and keeps unloading, and is credited when the job ends), and any claim of a job elsewhere first reports an open unloading stop at its node (§5 LC-1, Q-SIM-130, NX-486); a truck takes only resupply jobs and the retake job (below, Q-TD-100) from a parameterless `!join logi` (Q-GP-24).

**Sanctuary repair job (NX-497; Q-TD-124, owner 2026-10-29: (c) then (a); Q-TD-129 (1)-(5), lead, owner may veto); step 1 (the rate) and the defeat rule (Q-TD-129 (6)) stay open.**
142. A truck repairs a sanctuary by standing on it (§9 last stand, `defense._repair_sanctuaries`); this job sends one there.

143. **Step 1 (Q-TD-124 (c)), open: the rate is unchanged (1.0) until a harness run sets it; its tuning range is widened for that sweep (CONFIG-AND-CONTENT §6.5).**
144. Lower `capture.sanctuary_repair_hp_per_s` to a value set by a harness run (sweep and acceptance in CONFIG-AND-CONTENT §6.5), so that one parked truck repairs less than a siege takes.

145. **Posting:** the board posts the job at the side's own sanctuary (`Supply.rear`) while its defense hp is below `capture.defense_hp.SANCTUARY`, whether or not an enemy is tracked in range.
146. The job is RESUPPLY with the key `resupply:<sanctuary>`, so there is no new JobKind and no contract change.
147. An unclaimed job is withdrawn at full hp, as every coalition resupply job is (`tasking.unexpiring`).
148. It has no TB-8 dependency.

149. **Urgency:** `tasking.urgency_max` while the sanctuary is besieged (the `defend:<sanctuary>` condition, `tasking_gen.besieged`) or at 0 hp (the defeat run is counting).
150. Otherwise it is 1.0 plus the missing-hp share (missing ÷ maximum, `tasking_gen._urgency`), the share a damaged base's facilities give.

151. **Slots:** the LC-3 cap, with the missing-hp share as its need: `resupply_slots_max` + ⌊share × (`resupply_slots_max_starving` − `resupply_slots_max`)⌋ (`tasking_gen.slot_cap`), which is 3 to 6 at the shipped values.
152. There is no stock-per-slot term, because a sanctuary has no stock.
153. Overfill works as for any job (`tasking.overfill_factor`).

154. **Claimants: viewer trucks only.**
155. A COMMANDER-owned carrier takes it through the board or a bare `!join logi`, which spawns the truck at the sanctuary (the job's `plan_run` is a run from the rear to itself, cargo 0).
156. AI trucks and other AI_GARRISON carriers never take it, whatever `tasking.ai_jobs` lists.
157. `tasking._may_take` refuses it as it refuses the retake.
158. LC-1 (`ai_trucks._spawn_for_jobs`) skips it, so no AI truck spawns for it and no idle AI truck is counted against its slots.
159. `tasking.human_displaces_ai` never applies, since no AI truck holds a claim.
160. An AI truck that happens to stand on the sanctuary still repairs it under §9, because the rule is about parking, not the job.

161. **Executor:** no cargo and no reload.
162. An empty truck can take the job if it has a road route to the sanctuary (`supply_route`, around enemy-held nodes).
163. A truck with cargo is refused it, so it delivers its cargo elsewhere first (the sanctuary takes no cargo, `logistics.accepts`); the harness's idle reason for a refusal is `no_route`, never `no_reload`.
164. The claim sets the path.
165. On arrival the truck stands there (no path, `last_node` the sanctuary), which counts as lease progress (TB-1), and repairs under §9.

166. **DONE** when a live claimant stands at the sanctuary and its defense hp is full.
167. A participant is needed, else the job is EXPIRED.
168. A claimed job does not expire (no claimed non-CAPTURE job does), so claimants stay parked until DONE.
169. They leave earlier only through a human order (TB-7), loss or Disabled.
170. The job never FAILS through node loss, because a sanctuary is never captured (unless `capture.uncapturable_node_kinds` drops SANCTUARY: then it FAILS on capture, as any resupply job does).
171. When the war ends the board freezes (C-2).

172. **Sides (EC-3):** the rule is written for the side's own sanctuary.
173. Both strait-1 sides have one (`haven` and `static-rear`, `content/theaters/strait-1.yaml:21, :36`).
174. The Static has no viewer trucks, and its rear is never struck (Q-SIM-64), so only the coalition's board posts the job: coalition only in effect, like the retake.
175. Parked Static convoys still repair their rear by parity (§9).

176. **Events:** none new.
177. The job emits `JobCreated`, `JobClaimed` and `JobDone` like any job.
178. The `SANCTUARY_AT_RISK` sitrep (contracts 0.53), on the drop from full, is the call to action, and `NodeDefensesRestored` marks a rebuild to full from 0.
179. The overlay shows the sitrep as its top card (OVERLAY OV-26, NX-496); no overlay surface shows jobs yet.

180. **Defeat (§9) is unchanged here.**
181. A repair to the defeat reset threshold resets the defeat run and a repair below it only pauses the run (§9, NX-499).
182. The siege has to kill or disable the trucks: at 0 hp the node is pinned and the Static's shots go to units (`combat._fire`).

183. `defend:<node>`: a node the side owns (not a sanctuary or bridge) with the other side's capture bar on it, or a *tracked* enemy ground unit within `tasking.defend_radius_m` (10 km, Q-SIM-74) of it.
184. Urgency: 1.0 plus the larger of the bar's share and `1 - d / radius` for the nearest tracked enemy at distance `d`, capped at `tasking.urgency_max`.
185. Done when a claimant stands there, no bar runs and the side tracks no enemy ground unit within the radius; fails if the side loses the node.
186. **Sanctuary last stand (Q-TD-122 (a), lead decision, owner may veto; NX-493, in code):** the side's own sanctuary is the exception to "not a sanctuary": while its defense hp is below its maximum (`capture.defense_hp.SANCTUARY`) **and** the side tracks an enemy aircraft or ground unit within `tasking.defend_radius_m` (at the default (10 km) it covers every STRUCTURE weapon's reach, so a unit firing on it is in range; a last-known track does not count; lead refinement of Q-TD-122, so the job never outlives the threat while no repair exists), the board posts `defend:<sanctuary>` at the top urgency (`tasking.urgency_max`, 2.0, whatever the damage), with `tasking.slots.defend` (2) slots; any armed aircraft or ground unit fits it, as any defend job (the AI garrison takes it freely, `tasking.ai_jobs`; a garrison unit homed elsewhere does not, its board gives it only its own base's defense).
187. Done when a claimant stands there and either the hp is full again or no tracked enemy aircraft or ground unit is within the radius (and the usual threat test passes); an unclaimed one is withdrawn as soon as either holds, and the next strike package the side tracks posts a new one.
188. A defeat stays possible (§9): at 0 hp nothing ends it, and when the war ends the board freezes with the world (C-2), as every job does.
189. The same rule names each side's own rear (EC-3), but the Static's rear is never struck (Q-SIM-64), so only the coalition's board posts it in play.
190. The hit that takes the coalition sanctuary below full emits the sitrep `ThreatAdaptation{SANCTUARY_AT_RISK}` ("NULL strikes <node>, the sanctuary is at risk"), once per drop from full, as HOLD_AT_RISK is once per launch (§9, CONTRACTS).
191. The truck repair job of Q-TD-122 (a) is NX-497 (Q-TD-124, Q-TD-129; in code): see `resupply:` above.

192. `strike:<node>`: an enemy-held node with defense hp above 0 that is the active objective (coalition only, urgency at the cap), or an enemy-held node at any defense hp that holds a discovered facility marker not last seen Disabled (urgency 1.0 plus `tasking.strike_urgency_per_threat` (0.01) x the facility kind's `threat`).
193. Done when the side owns the node, or the node's defense hp is 0 and the side knows no live site there (no facility marker at the node last seen not Disabled).
194. **SEAD (Q-TD-81, NX-461; both boards, EC-3):** a node whose defenses are down keeps its job while its site is live, so the crowd suppresses a SAM instead of idling behind its ring; the job ends once the side's marker shows the site Disabled (its jets see it hit).
195. SEAD covers only the board's own `strike:<node>` jobs: a Director operation's STRIKE (an `op:` job) is still done when the node's defense hp is 0, so the CAPTURE waiting on it opens (THREAT-DIRECTOR §7a), and so is the objective strike (it has no expiry); the next pass posts a plain `strike:<node>` SEAD job if a live site remains.
196. Q-SIM-92: every strike job gets one extra slot per idle armed viewer unit (a viewer-owned aircraft with ammo, no job, not on HOLD), at most `tasking.strike_max_scaled_slots` (3) extra; while idle ones remain and no objective or marked target is open, and the Static's Director tier is at least `tasking.strike_idle_targets_min_tier` (ALPHA; at Pattern of Life a lone new viewer provokes nothing, Q-SIM-86), the board also posts `strike:<node>` (urgency 1.0) on the `tasking.strike_idle_targets_max` (2) known defended foe-held nodes nearest a coalition-held node (ties by node id).
197. Reach, fuel and ammo are checked at claim as for any strike.
198. The Static's rear source is never a strike target, by any path (combat never fires at it, Q-SIM-64; NX-396).
199. Mobile targets are not struck yet.

200. `assist:<node>` (coalition only): the active objective's node, urgency at the cap, ends with the objective (done if it completed and a claimant had made progress).

201. `scout:<cell>`: each SIGINT blob in the side's view, deduped by cell index, posted only once a blob has stayed in the cell for `tasking.scout_blob_runs` (2) consecutive SIGINT refreshes (urgency `tasking.scout_urgency`: small 1.0, medium 1.5, large 2.0).
202. Done when a claimant orbits at the blob's cell centre; the cell is then not posted again for `tasking.scout_cooldown_min` (5 min, Q-SIM-75).
203. **Sector scout (Q-TEST-14, Q-SIM-134; NX-512; lead details PROPOSED, owner may veto):** both boards post a point scout job for the stalest point of a sector, by the one rule of THREAT-DIRECTOR Part 4 (Q-SIM-87, §0 parity). The Static's is its RECON operation (`op:RECON:<sector>:0`); the coalition's is this board job.
   - **The pick:** per theater sector (ids ascending), `operations.recon_point` on the side's own `SideView` (FOW-4, FOW-8) and its own `DirectorState.looked`, with the same keys (`director.recon.grid_m`, `loiter_radius_m`, `loiter_s`, `memory_s`) and the same tests: stalest cell first, ties by (x, y); the first whose straight route from its launch base crosses no discovered ring last seen not Disabled (widened by the loiter radius); a sortie that fits (flight, loiter and return with the bingo reserve). The launch base is the coalition's `launch_base` for an aircraft (GP-7 pool, else the sanctuary).
   - **Looked memory for both sides:** at each board pass the side marks the cells its sensors cover (`launch.look`, the Static's rule: units in id order, cells ascending), kept in `World.director[COALITION].looked`; no new state.
   - **Nothing stale, no job:** a point is posted only when no sensor of the side covered its cell for `tasking.scout_sector_stale_min` (PROPOSED 30 game min, at most `director.recon.memory_s`) and no track within the loiter radius is fresher.
   - **Count and keys:** up to `tasking.scout_sector_points` (PROPOSED 1; 0 turns the job off) per sector, the k-th stalest passing cell at least twice the loiter radius from those already chosen this pass; key `scout:pt:<sector>:<k>`.
   - **The job:** SCOUT, `Job.pos` the point, node and blob empty; slots `tasking.slots.scout`, priority `tasking.priority.scout`, urgency `tasking.scout_sector_urgency` (PROPOSED 0.5, below a small blob's 1.0). It counts toward `tasking.scout_open_max` and `scout_post_interval_min` like any generated scout job and never overfills (a point job).
   - **The point is fixed while the job is open:** an unclaimed job whose point stops being stale or comes under a ring is withdrawn (item 229); a claimed one is not moved. After DONE, EXPIRED or FAILED the sector may post a new point at the next pass; `tasking.scout_cooldown_min` applies by sector id.
   - **Taking it:** recon units fit it; a unit claims it only if it can fly there, loiter and land with the bingo reserve left from where it stands (TB-2) and its route crosses no discovered ring (item 234). The executor is the Static's loiter (`tasking._loiter`): DONE after `director.recon.loiter_s` on station, or when a ring discovered since covers the point.
   - **No new reward:** a refresh pays no XP or merit (owner, Q-TEST-14; PROG-13 unchanged). The job's value is the picture and A2's impact (TESTING-STRATEGY A2).
   - **Parity (§0 item 3):** same function, keys, tests and loiter. Differences: the Static raises a unit from its budget at a decision window, the coalition's claimant is a viewer's free unit; the coalition's job expires unclaimed like any job; cadence is the board pass, not the decision window.

204. `repair_bridge:<node>` (coalition only, NX-373 part 2): each down bridge that some live, not Disabled coalition carrier can reach a bank of by road (the claimant's own route), urgency 1.0, `tasking.priority.repair_bridge` 45 and `tasking.slots.repair_bridge` 2 (PROPOSED).
205. Carriers fit it; the Static's board never posts it.
206. The truck drives to the quicker bank (route time, then metres, then bank id: `bridges.quickest`, NX-429, Q-SIM-129) and out along the road to the bridge's repair stop and repairs there (STATE-MACHINES §4.3); DONE once the bridge is up again, then its trucks drive back to their bank.
207. The crew's road to the bank (`logistics.approach`, the generator's reach test and the claimant's route alike, and a crew's reroute after a cut) enters no node the other side holds, the bank included (`bridges.enemy_held`; neutral nodes are passable), so with no such road from any carrier the job is not posted (NX-410, Q-SIM-125).
208. A parameterless `!join logi` never takes it (the bridge is not a valid truck destination, Q-SIM-111); the board gives it to an idle truck.
209. **TB-8 in code:** a coalition RESUPPLY job whose node no friendly source reaches by road while bridges are down depends on the REPAIR_BRIDGE job of the first down bridge on the intact road route from the sanctuary (posted in the same pass; an open job that gains the dependency is posted again); it opens when that job is DONE and fails with it otherwise.
210. Neither route enters a Static-held node, as the run does (Q-SIM-122; neutral nodes are passable): a node whose only road crosses enemy ground depends on no repair, is still posted, no truck can take it, and it stays posted unclaimed while the rule posts it (the coalition resupply exemption from `expire_min`, below; Q-SIM-131).

211. `retake:<node>` (coalition only, a `CAPTURE` job; owner 2026-10-28, Q-TD-94 (b), Q-TD-99, Q-TD-100 (a), Q-TD-101 (a); NX-475, `tasking_gen._retake`): **eligible** is a strategic node (`campaign.strategic_node_kinds`) the coalition held at campaign start (the theater's `start_owner`, so no new state) and does not hold now (enemy or neutral), with no time window (not the 15-min `World.lost` memory).
212. It is posted only once the node's defenses are down (defense hp 0), so it follows the coalition's strike job on that node (a SEAD strike on a live site there may still run beside it).
213. **One job id per lost node (Q-TD-121 (a), revised; lead decision, owner may veto; NX-484):** an unclaimed retake job never expires by `tasking.expire_min` (TB-1 does not apply to it, as TB-3 aging does not, Q-TD-107); it ends only when withdrawn as below, by DONE, or once claimed by the CAPTURE rules, whose clock starts at the claim.
214. **Keep:** an unclaimed retake job stays posted for `tasking.retake_keep_min` (PROPOSED 30 game min) after its node's defenses return above 0, then is withdrawn as before; if they fall to 0 again within that time the same job goes on (no new posting, the same job id) and the next return starts a fresh keep.
215. The keep is counted from the first board pass that sees the defenses up (`Job.lost`, the intercept job's clock field, reused).
216. Every other rule still withdraws it at once: the coalition holds the node again, no capture run reaches it, or no truck role can JOIN.
217. `retake_keep_min` 0 means no keep (withdrawn at the first pass that sees the defenses up); with the expiry exemption it is no longer the rule before NX-484.
218. A kept job is still the one retake job, and a claimed one behaves as before.
219. A kept job stays claimable: a truck that takes it drives to the node and waits there until a strike drops the defenses (capture cannot start above 0 hp, §8) or its own CAPTURE rules end it.
220. **One at a time:** the live retake job stays while its node is still eligible (no churn when another node becomes nearer); while a claimed one is live no other is posted, even when its node stops qualifying (it ends by the CAPTURE rules below); otherwise the board posts the eligible node nearest a node the coalition holds, a base or the haven (exact squared straight-line distance, ties by node id, the patrol's order).
221. A node no capture run reaches by road (`plan_run`, the bare JOIN's own plan: from the forward start of item 23, else the rear; down bridges blocking) is skipped.
222. **Taking it (Q-TD-100 (a)):** any viewer truck, through the board or a bare `!join logi` (which plans it as `!join logi <node>`: an empty capture run from its start base, item 23); the truck drives there and stands, and the capture is the ordinary §8 presence rule.
223. The AI garrison never takes it (it never initiates offense).
224. **Ranking:** priority `tasking.priority.capture` (45, the existing key) x urgency 1.0, with no priority aging (TB-3 does not apply to it; lead decision, NX-475 review, so Q-TD-100 (a) holds however long it waits): a starving base's resupply (`priority.resupply` 50 x 1.0 and up) always ranks above it, and a stocking one (50 x 0.5 or 0.75) below it until that job's own aging lifts it past 45 (TB-3, so stocking is never starved).
225. One slot (one truck's capture run; more trucks join only by overfill, `tasking.overfill_factor`).
226. It ends as the Director's CAPTURE does: DONE when the node is the coalition's (a participant needed, else EXPIRED), EXPIRED at its expiry even when claimed (counted from the claim, Q-TD-121), with a fresh clock while a claimant still drives (`tasking.capture_max_restarts`), and not at all while a claimant is within `capture.radius_m` of the node and the side's bar there is live (NX-483; THREAT-DIRECTOR §7a, STAGE and CAPTURE); the next pass then posts the next eligible node.
227. Interpretations (lead, inside the owner rows): "starving" is the existing urgency split, so a resupply to a damaged base that is not starving (urgency 1.0 and up) also outranks the retake; "base or haven" is any node the coalition holds; the one-slot count adds no key.

228. A board generates a kind of job only while its side can staff it: a live unit of the side fits it, or (coalition) a viewer can JOIN as a role that fits.
229. A job with no claim expires `tasking.expire_min` after it was posted; an unclaimed generated job whose condition ended expires at once (the retake job's keep aside, above; an unclaimed retake job does not expire by `expire_min` at all, Q-TD-121).
230. **Coalition resupply (Q-SIM-131 (a), lead decision, owner may veto; NX-492, in code):** an unclaimed coalition `resupply:<node>` job does not expire by `expire_min` either; it keeps its job id and posting time while the generator still posts it, and is withdrawn at once when the generator no longer does (the base no longer needs it, or is lost).
231. Only the expiry: it still ages (TB-3), while unclaimed for at most `expire_min` minutes' worth and once claimed without a cap, as before (Q-SIM-132 (a)), and a claim starts no new clock, since a claimed resupply job does not expire (`tasking.unexpiring`).
232. The Static's resupply jobs and every other job still expire as before.
233. The AI garrison takes defend, resupply, scout and repair-bridge jobs freely, never escort or patrol jobs, and any other job only once a COMMANDER-owned unit holds a claim on it, and a human takes an AI unit's slot; for `tasking.counterattack_window_min` (15 min, Q-GD-31, Q-SIM-74) after its side loses a node (`World.lost`), units still able to fight may also take strike and assist-objective jobs against it.
234. An aircraft skips a job whose straight route crosses the ring of a discovered enemy site last seen not Disabled, unless the job targets that site's base (TB-2; direct orders are unaffected).
235. An empty truck that takes a resupply job first drives to a source (the `!join logi` source rule), loads `min(truck_cargo, surplus)` as a spawn does, then delivers.
236. When no fitting job with a free slot is feasible for a unit (every one full, or every free one refused, Q-TD-89), it overfills a job only up to `tasking.overfill_factor` (2) times its slots and otherwise waits for the next pass (Q-SIM-75).
237. A carrier (truck, convoy) takes resupply and repair-bridge jobs, and the coalition's retake job (Q-TD-100), only: any other capture run stays a direct order, so no assist-objective job exists until a non-carrier ground unit (an AI garrison unit) can staff it.
238. A parameterless `!join` claims the best job at spawn (ties by job id; an aircraft skips a job whose route crosses a discovered ring, like the board); a unit with no explicit order takes jobs from the board, and a node-target `!join` order ends on arrival (a capture run when its bar is gone).

Notes: GAMEPLAY-NOTES.md §1b

## 2. Roles (MVP, resolves critique #7 and #8)

| Role | Command | Domain | Does | Can't |
|---|---|---|---|---|
| Strike | `!join strike` | AIR | Attacks ground/air targets; suppresses SAMs poorly without SEAD | Capture nodes |
| Recon | `!join recon` | AIR | Large sensor radius; converts SIGINT blobs to tracks; paints targets | Deal damage |
| Logistics | `!join logi` | GROUND | Carries supply along roads to nodes; captures uncontested nodes slowly | Fight |
| Naval | `!join navy` | SEA | **P3** (Q-GD-8: sea domain moved earlier because maps are water-heavy) | — |

1. Specialist chassis (SEAD, jammer, engineer, AWACS, artillery) unlock with rank (PROGRESSION) and arrive in P4 (NX-212, COMMAND-CATALOG §3).
2. **Specialist doctrines** are chosen once per campaign and lock (Q-GD-3).

3. **Display names (Q-NAME-2, working names; final list in the brand guide NX-274):** roles and unit kinds keep plain ids in code and contracts (TS-4), but the stream shows friendly class names: Striker (multirole jet, `STRIKE`), Scout (recon drone, `RECON`), Hauler (supply truck, `LOGI`), Tank, Gunboat, Tanker (refueler), Lifter (rescue helo), Sentinel (anti-air site), Spire (radar).
4. No real-world platform names (Q-PROD-5).

## 3. Commands (Q-GP-2, Q-CMD-1)

1. Rank ids `O-1`…`O-6` are **internal ids** used in config and contracts.
2. On stream and in replies they show as themed display names (Q-NAME-1, PROGRESSION §3).

3. The commands, their syntax, ranks and phases are listed in [COMMAND-CATALOG](COMMAND-CATALOG.md) §2 (Q-CMD-1).
4. Behavior notes that are only here: `!join` spawns your one unit, or switches role if your unit is at base, and `hold` opts out of auto-tasking (§1b); `!target` sets your unit's objective or follows a friendly unit (Q-GP-31); `!rtb` returns your unit to the nearest friendly base; `!rebase` moves your unit to another friendly base and stays there to refuel, rearm or stage (e.g. move a plane forward before an attack), using that base's stock, and the Static does the same (THREAT-DIRECTOR §5a).
5. An aircraft can only rebase to a landing base it can reach with its bingo reserve, a ground unit to any friendly non-bridge base it has a road to; the order releases a board job and ends a follow, the unit takes no board job on the way or at the base until its commander gives a new order (it holds: default; Q-CFG-16 option `slots.rebase_order`, HOLD its only value so far), and cargo stays aboard (a truck still unloads at the base by the ordinary stop rules); `!me` highlights your unit for 5 s and the next digest repeats its status (FB-UX-3, Q-MOD-5); a `!callsign` is moderated, never equal to a node name or alias (Q-GP-31), one change per 30 days (NX-158, Q-SIM-90).

6. Commands the gateway handles alone (`!help`, `!guide`, `!rules`, `!link`, `!quiet`, `!forget`) are in CHAT-GATEWAY §9.
7. Later-phase commands (`!stance`, `!rally`, `!rescue`, `!vector`, specialist spawns, `!package`, `!wingman`, `!doctrine`, `!order`) are listed in COMMAND-CATALOG §3, with design notes in GAMEPLAY-LATER §3.
8. Unknown commands and ordinary chat are ignored.
9. Command aliases are configurable.

## 4. Unit slots

1. **GP-1** Each commander has at most **one live personal unit**, and an AI-run (AUTO) unit still counts as it (GP-6, Q-ALN-9).
2. `!join` while your unit is alive retargets or switches it only if it's at a base.
3. Otherwise you get the reply "unit in sortie".

4. **GP-2** After death, respawn is allowed after `slots.respawn_delay_s` (PROPOSED 20 s, game time, Q-ALN-5) to stop suicide spam.
5. The delay grows with repeated losses in a short window, and a rescued crew removes part of it (Q-CBT-9).
6. Losing a unit never costs XP; deliberate disruption is handled by the conduct system (ADMIN-RBAC §6.8).

7. **GP-7 Spawning never hurts (Q-GP-41):** joining is always free.
8. A unit with a node target spawns at a base from the theater's `spawns` list for its domain that its side owns and whose stock exceeds its starvation threshold by `logistics.forward_deploy_min_surplus` (and by at least its loadout cost), nearest the target by straight line for aircraft and by road for ground units, and pays its loadout from that surplus (**forward deploy**, Q-SIM-54).
9. A JOIN with no target or `hold`, or one no base qualifies for, spawns at the sanctuary, whose stock is infinite, and travels forward.
10. The spawn always has a full loadout.
11. A logistics unit spawns at its source base (§1b). A capture run's truck carries nothing, so it has no source: it forward-deploys by item 8 (§1b item 23, NX-513).
12. The Static spawns by the same rule (Q-TD-8, parity).
13. Spawning never takes a base below its starvation threshold: the debit stays above the floor.
14. When a delivery lets a base forward-deploy again, the ticker credits it ("HAULER-12's delivery: WEST FOB can forward-deploy again"); a starving base shows "units spawn at sanctuary".

15. **GP-3** Above `slots.max_viewer_units` (Q-GD-6) new joiners go to a visible reserve queue.
16. The queue is served FIFO as slots free up.

## 4a. Reserve-queue mitigations (Q-GD-6 decided with mitigations)

1. **RQ-1:** show the queue length on the HUD.
2. Each queued viewer gets their position (Q-SIM-12): a reply on `JOIN` ("queued, position N of M"), an update only when the position crosses a milestone (top 10, top 3, next; PROPOSED milestones), and "you're in" when served.
3. `!me`/`!status` can ask at any time.
4. The Field Manual, `!help` and the `JOIN` reply must tell viewers this is how the queue works.
5. A queued viewer leaves the queue after `slots.queue_idle_min` (15, real time, Q-SIM-12) without any chat message, so a departed viewer does not hold a slot.
6. The runtime logs a `SYS_QUEUE_TIMEOUT` for an entry whose commander has been silent that long (paused time does not count, so an offline auto-pause, Q-OPS-8, does not empty the queue; until the gateway feeds chat times, NX-190, JOIN times stand in), and every queue exit emits `ReserveQueueLeft` (STATE-MACHINES §4.1); the position milestones are not built yet (NX-371).

**RQ-2: Dynamic cap.**
7. `slots.max_viewer_units` is a ceiling.
8. The runtime may lower the effective cap while tick time is over budget, and raises it back when there's headroom (logged, visible on the ops dashboard).

9. **RQ-3 (P4):** flights and wingmen moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §4a.
10. The alpha uses the plain reserve queue.

11. **RQ-4, RQ-5 (moved, Q-GP-9):** queued `!scout` pings, participation merit, the first-timer boost and the max-wait guarantee are in [GAMEPLAY-LATER](GAMEPLAY-LATER.md) under "Moved from the first-build review".
12. The queue is plain FIFO; a silent commander's unit frees its slot only when it retires (GP-5), and a handed-off AUTO unit (GP-4) still occupies it (Q-ALN-8, Q-ALN-9).
13. There is no other idle despawn.

## 4b. Silent viewers (Q-GD-35, Q-ALN-8)

1. Chat gives no presence signal, so silence is measured as time since the commander's last command that reached the sim (game time, Q-CFG-8, Q-ALN-1).
2. Info commands, `!quiet` and `!callsign` are handled outside the sim and do not reset the timers (Q-ALN-26).
3. These two timers are the only idle rule; the earlier fixed idle despawn is removed (Q-ALN-8).

4. **GP-4 Idle handoff:** after `presence.idle_handoff_min` (PROPOSED default 10, game time) with no command from its commander, the unit finishes its current order and joins the Tasking Board as an AI-run unit.
5. The overlay tags it **AUTO** from the handoff tick, and the current order is kept (Q-ALN-26).
6. The AUTO unit keeps occupying its commander's slot (GP-1, GP-3) until it retires (Q-ALN-9).
7. A unit that joined with `hold` gets the same handoff and keeps holding until it claims a job (Q-ALN-25).

8. **GP-5 Idle retire:** after `presence.idle_retire_min` (PROPOSED default 30, game time) with no command, the unit RTBs and despawns.
9. Cargo it carries is unloaded at the base it RTBs to.
10. Only then is the slot freed.
11. A **Disabled** unit can't RTB; it is a wreck removed after `combat.disabled_timeout_s` whoever owns it, and its cargo is lost (COMBAT CB-7, Q-CBT-14).

12. **GP-6 Reclaim:** any command from the commander while the unit is alive restores their control of **that** unit and clears the AUTO tag; a `!join` reclaims the AUTO unit instead of spawning a second one (Q-ALN-9).

13. Both timers are admin-configurable in the Command Center.

## 5. Logistics (resolves critique #13)

1. Nodes hold `stock` (0..max).
2. Spawning or rearming at a node consumes stock according to the unit's loadout cost.

3. **Sources (Q-GP-41):** in the first build stock comes only from each side's source, shipped in by truck: the coalition's SANCTUARY (infinite, far away) and the Static's rear source behind its HQ.
4. Factories are parked in GAMEPLAY-LATER until playtests show single-source convoys are too slow.
5. Since NX-412 ([ECONOMY](ECONOMY.md), approved) neither source is infinite: each is a finite pool with income (EC-1) and storage (EC-2).

6. Each side not in unlimited mode keeps its source's pool in `World.pool` (snapshot format 28) (NX-412 part 1).
7. It starts full, at storage.
8. Every `economy.window_s` (60 game s) it gains `economy.income.floor` plus `economy.income.per_node.<kind>` for each node the side owns with no capture bar on it, up to storage, as `SupplyProduced{side, amount}`.
9. Then it is clipped to storage, `economy.storage.floor` plus `economy.storage.per_node.<kind>` per owned node, with the excess reported as `SupplyConsumed{STORAGE_LOST}`.
10. A truck loading at the source takes at most the pool, and an empty pool loads nothing; a viewer's sanctuary spawn is free only while `economy.free_viewer_spawn` is on (EC-13, item 29 below).
11. `economy.unlimited.<side>` shipped true for both sides until NX-412 part 5b (Q-TD-29) and ships false since then, so both sources are finite.

12. **Upkeep and grounding (Q-TD-18, Q-TD-23, Q-TD-43, Q-TD-49; ECONOMY EC-4..6):** every live unit pays `economy.upkeep.<unit_kind>` from its home base once every `economy.upkeep_period.<unit_kind>` windows (Q-TD-41), so a unit can cost less than 1 stock per window.
13. A unit whose home cannot pay is grounded, never deleted: it returns to its home, takes no new job or order, still returns fire, and flies or drives again when its home pays.
14. Its one way out is `!rebase` to a friendly base that can pay it (Q-TD-51 U3): there it lands or parks, that base becomes its home, and it ungrounds at the next window.
15. Viewer units are paid before AI units, so AI garrison units ground first.
16. Within each, busy units (holding a claimed job or following an explicit order) are paid before idle ones, so a busy viewer unit grounds only when the viewer units ahead of it have used what its home holds.

17. Every unit has a home base (`Entity.home_base`, snapshot format 29): the node it spawned at, then the friendly base it last landed or parked at; when that node is captured, the nearest friendly node that can host it by straight line from the unit (a landing base for aircraft, any base but a bridge for ground units), ties by node id (NX-412 part 2).
18. Every economy window, after income and the clip and before the Threat Director, each live unit of a side not in unlimited mode pays `economy.upkeep.<kind>` from its home's stock, or from the side's pool when the home is its source, in the order viewer units first, then within each class units holding a claimed job or an explicit order under way (`Entity.job_id`, `Entity.order`; a HOLD only while the unit travels, `upkeep._busy`) before the rest, then the most recent spawn or order (`Entity.ordered`; JOIN and REBASE are the orders), then entity id.
19. A home pays only the full amount; each home's total is one `SupplyConsumed{UPKEEP}`.
20. A unit that is not paid is grounded (`UnitGrounded{entity_id, node_id}`): it drops its job claim, order and leader, flies home and lands or drives home and parks, the board and the Director give it no job, and it still fights.
21. REBASE (NX-435, Q-TD-51 U3) accepts it only to a base that holds its full upkeep now (`upkeep.pays_at`: the base's stock, or the pool at the source; units due there first are not deducted), else refuses with `UNIT_GROUNDED`; the unit flies or drives there still grounded with the REBASE hold, the landing or parking makes that base its home, and the next window (a grounded unit is charged every window) charges it there and ungrounds it.
22. It ungrounds (`UnitUngrounded`) at the first window its home pays.
23. Period (NX-426): a unit is charged only in the window whose index plus its entity id is a multiple of its kind's `economy.upkeep_period`, so payments spread across windows; a grounded unit is charged every window until paid, then returns to that stagger.
24. The shipped upkeep is 0 for every kind, kept in NX-412 part 5b (Q-TD-85), so nothing pays or grounds yet, although both sides ship limited since part 5b (Q-TD-29).
25. Shortfall sitreps (NX-436, ECONOMY EC-6a): one `SupplyShortfall{STARTED}` per base when it starts grounding units ("<BASE> OUT OF SUPPLY: n flights grounded.
26. Haul to <BASE>"), one `ENDED` crediting the trucks that hauled to it when it pays again, a Static base only while the coalition sees it, and a chronic base kept quiet by `economy.shortfall_quiet_windows`.
27. Not built: the spawn reply's "haul to <base>" warning (the sim has no spawn-reply path; the gateway's replies come with NX-190) and the overlay's grounded icon.

28. **One spawn rule and the guard (ECONOMY EC-13, EC-8; NX-412 part 3):** every spawn draws its cost at the node it spawns at.
29. A JOIN at a base pays its `logistics.loadout_cost` there as before (GP-7); a JOIN at the sanctuary is free while `economy.free_viewer_spawn` is on (default), and otherwise draws the same cost from the coalition's pool, or is refused with `NO_STOCK` when the pool cannot pay (an unlimited pool always pays, for nothing).
30. The Director pays each operation once at the node where its units spawn (THREAT-DIRECTOR §7a).
31. `sim.max_live_units_per_side` caps each side's live AIR and GROUND units as a tick-rate guard: a JOIN at the guard waits in the reserve queue exactly as at `slots.max_viewer_units` (GP-3, RQ-2; `ReserveQueueJoined`).
32. The theater's opening garrison is placed at setup and draws nothing.

33. **Starvation (Q-SIM-53):** a spawn always gets a full loadout.
34. Starvation bites on **rearm** only: a unit refuelling or rearming at a base below `logistics.starve_threshold` (PROPOSED 25%) is filled only up to the starved loadout (`logistics.starved_loadout.fuel_frac`, 50% of its fuel; guns only, NX-124 part 2, with the gun rounds also drawn from stock).
35. At 0, the node can't rearm.
36. A unit whose job its capped tank cannot serve leaves for an unstarved base instead of waiting there, and on its airborne refuel step passes such a base by (§1b, Q-TD-88, NX-467).
37. A refuel is paid by what is missing: `logistics.loadout_cost` x the share of the tank bought, at `logistics.rearm_rate` (Q-SIM-51); the sanctuary refuels for free.

**What the floor does today.**
38. Each finite-stock node has one floor, `Supply.starve_floor` = ⌈`logistics.starve_threshold` × `node_max_stock`⌉.
39. Its readers use it in five ways:

40. **Starved, a state (stock < floor):** the rearm cap, the starvation hp drain, the refuel hops and the capped-tank check, LC-2's demand test and the harness Starved count (coalition-held nodes only).

41. **Need share, (floor − stock) ÷ floor:** the board's resupply urgency and LC-3 slots, and the Static convoy's LC-3 cap.

42. **Keep, what a source never ships below:** every run that is not a stocking run, both when the run is planned and when it loads at the source, and LC-1's spawn check.

43. **Spendable margin, stock − floor (a debit never takes a base below it):** forward deploy (GP-7), the Director's margin for the operation launch base and the garrison convoy shortfall, the operation payment checks and the FS-3 staging lift.

44. **The Director's surplus, the Static's wealth:** `director.surplus`, read by the EC-7 budget, the cadence floor's cap, the capture slot's selection, the convoy gate and the purse of convoy and capture-slot spends.
45. Since NX-500 (ECONOMY EC-7 "Surplus reference", in code) this use, and only this use, reads its own reference `Supply.surplus_ref`, max(⌈`director.surplus_ref_frac` × maximum⌉, the floor), which equals the floor at the shipped 0.25.

**Absolute floor (NX-495; Q-TD-123 owner direction 2026-10-29; the details are Q-TD-132, lead, owner may veto); ships at `fraction` until the probe picks.**

**Switch.**
46. `logistics.starve_floor_mode`, `fraction` (default) or `loadouts`.
47. `fraction` is exactly today's floor.
48. `loadouts` sets every finite-stock node's floor to min(N × C, `node_max_stock`), where N is `logistics.starve_floor_loadouts` (PROPOSED 5) and C is the largest `logistics.loadout_cost` entry (20 at the shipped values: STRIKE_FIGHTER, ENEMY_FIGHTER and ENEMY_STRIKE_FIGHTER, `balance/default.yaml:50, :52, :56`).
49. The floor is fixed at load, the same at every base and for whichever side holds it, and it does not grow with storage.
50. The min caps it at the node's maximum, so a BRIDGE (maximum 0) keeps floor 0 and no node is starved while full.

51. **Every reader above follows the floor**, in either mode, except the Director's surplus (NX-500).
52. So the switch changes logistics only: starved, need, keep and margin.

**Parity (Q-TD-119, EC-3).**
53. One C for the whole catalog, not one per side: the floor of a node never changes when it is captured, and a cost probe moves both sides' floors only when it moves C: raising any kind above 20, or cutting every kind at 20.
54. A synced cut of the strike pair alone leaves C at 20, because ENEMY_FIGHTER (unpaired, EC-3) also costs 20.
55. Either way both sides get the same floors, which is the owner's "minimum supply needed" measured in units.

**What it does not change.**
56. The forward stock target (`logistics.stock_target_frac`, 0.8 × maximum, `tasking_gen.py:380-388`) still grows with storage and still posts stocking jobs up to it, so steady hauling is set mostly by the target, not the floor (inference from the code, [UNVERIFIED] in play; it fits Y1, where a lower floor did not cut hauling).
57. The target gets its own switch, next bullet (NX-501).

**Harness.**
58. "Starved" counts nodes below the live floor (H1), so a `loadouts` run is not comparable with a `fraction` control on it.
59. The report adds a second count against the fraction floor, ⌈`starve_threshold` × maximum⌉ whatever the mode, computed by the harness from the loaded balance (in code, NX-495: `metrics.Collector` takes `starve_threshold`; `starvation.fraction_floor_node_minutes` in `report.json`, the "Starved (fraction floor)" column in `report.md`).

**Stock target cap (NX-501; Q-TD-133 (a), lead recommendation 2026-10-30, the owner may veto); ships at `fraction` until the probe picks.**
60. The rule:

**Switch.**
61. `logistics.stock_target_mode`, `fraction` (default) or `loadouts`.
62. `fraction` is exactly today's target, ⌈`stock_target_frac` × maximum⌉ (`rules._supply`).
63. `loadouts` sets every finite-stock node's target to min(max(M × C, floor), maximum), where M is `logistics.stock_target_loadouts` (PROPOSED 15, a starting value to probe, not measured), C is the same dearest `loadout_cost` as NX-495 (20 at the shipped values) and floor is the node's live `Supply.starve_floor`.
64. Fixed at load, the same at every base and for either side (Q-TD-119), and it does not grow with storage.

**Readers follow.**
65. Every reader of `Supply.stock_target` follows it unchanged: the stocking job and its urgency (`tasking_gen._resupply`), the load limit of a stocking run (`logistics.py:239-244`), the FS-3 staging raise, which lifts a staging base to at least floor plus the staged cost (`logistics.stock_targets`, unchanged), and the LC-1/convoy ordering (`launch.py:553`).
66. The Director's surplus (NX-500) does not read the target.

**Harness.**
67. Probe at one sha, both sides at parity: a control (both `fraction`) against floor `loadouts` N 5 with target `loadouts` M 10, 15 and 20, reading hauling, Starved on both counts (NX-495) and the A2 and Offensive lines.
68. The report did not print hauling (checked 2026-10-30), so NX-501 adds a line (in code: `metrics.Collector.jobs_posted` and `.stops`, `report._hauling`; the "Hauling" section of `report.md` and `profiles.<p>.hauling` in `report.json`): per side, `resupply:<node>` jobs posted (`JobCreated` with kind RESUPPLY, not the sanctuary's own repair job at the side's rear; new postings only: a job re-posted after it ended, or ended unclaimed and posted fresh behind a bridge repair, counts again, so this is posting churn, not distinct needs) and truck deliveries (`SupplyDelivered`, one per unloading stop, by the truck's side), each per run-hour, pooled over the seeds.
69. It does not split stocking from starving: neither event says which a job is, so a split would be invented.

70. **Munitions per sortie (Q-CBT-7):** every unit leaves with a limited load drawn from base stock.
71. **Guns are limited too** (high round count); rounds used are charged to base stock on resupply.
72. Out of missiles/bombs → auto-RTB unless stance `press` or `guns` (COMBAT §5.6; the first build runs every unit as `standard`, and `!stance` is in GAMEPLAY-LATER §3).
73. **Unlimited ammo** is a campaign/test option (testing, special events) set at campaign setup by the owner or an Admin only, never by a GM and never live mid-war (Q-ALN-10).

74. **Repairs (Q-GD-27):** repair happens at a friendly base with stock, for **all domains** (aircraft at airbases, ground vehicles at bases/depots, ships at ports).
75. It costs time and stock and is faster at bigger or upgraded bases.
76. There is no field repair of Disabled units in the first build; they are wrecks (COMBAT CB-7, Q-CBT-14) until the engineer specialist brings quicker, dedicated repair.
77. Same rules for the Static (parity).

78. **Forward stock (Q-SIM-100, Q-SIM-102, NX-389; in code):** stock flows forward all the time, not only when a base starves, because the stock at a forward base pays for its repairs and later its upgrades (GAMEPLAY-LATER §5a).
79. Every base below `logistics.stock_target_frac` (PROPOSED 0.8) of its maximum gets a standing resupply job (§1b), and a run to it loads only stock a source holds above its own target, so the stock comes from the rear source or from a base already above its own target, never from another base below it; a source never ships below its own floor (Q-GP-24).
80. With the target at the starvation threshold the rule is off.
81. Both sides play by it.

82. **Supply moves only on trucks (Q-GP-16):** stock moves between nodes only as `cargo` on logistics trucks, which load at a source node, drive the road graph and unload at the destination.
83. There is no passive trickle along connected roads.
84. **One exception (Q-GP-40):** a supply drop (redemption or GM world event) is an air delivery that can be intercepted and lands as stock at its target base.
85. The AI garrison takes `resupply` jobs (§1b), so a 0-viewer war runs a slow convoy cadence instead of starving.
86. The coalition spawns `AI_GARRISON` trucks on that cadence (LC-1 below), off at the shipped `logistics.ai_trucks.max_live` 0 until the harness sweep switches it on (Q-TD-113) (NX-473).

**Logistics cadence (NX-473, Q-TD-92; lead decision, owner may veto; in code; landed at the no-op values of Q-TD-113 and switched on after the harness (Q-TD-128, `docs/review/ENTERTAINMENT-C0-V2-2026-10-29.md`): `logistics.ai_trucks.max_live` 3, `tasking.resupply_slots_max_starving` 6, `director.pol.convoy_demand_s` 900).**
87. Restocks are a steady, visible part of the war on both sides, not only when a viewer hauls.

**LC-1 Coalition AI trucks.**
88. Once per `logistics.ai_trucks.period_s` (game time; it fires in the economy windows whose index is a multiple of the period in windows, like the EC-4 stagger, so it adds no snapshot state), after upkeep and before the Director window (ECONOMY EC-10 order), the coalition spawns `LOGI_TRUCK` units owned by `AI_GARRISON` (the catalog's `playable_by` already allows it) for its resupply demand.
89. Idle AI trucks go first: the board pass already gives them jobs (`tasking.ai_jobs` has RESUPPLY).
90. Then, for each open `resupply:<node>` job in rank order (ties by job id) that was posted at least one period ago (`Job.created`, counted from its first posting: an unclaimed coalition resupply job does not expire by `tasking.expire_min`, §1b, so it reaches the age even when `period_s` ≥ `expire_min`; Q-SIM-131, NX-492) and still has slots no claim holds, one new truck per such slot, while live AI trucks number fewer than `logistics.ai_trucks.max_live` and within `sim.max_live_units_per_side` (EC-8).
91. A job whose run finds no source that can load stock gets no truck.
92. A new truck spawns where a viewer's `!join logi <node>` would (GP-7: the §1b source of its run, the sanctuary last), claims the job at spawn and loads by the source rule.
93. **Scaling:** a job's slots already grow with the missing stock (one per `tasking.resupply_stock_per_slot`, up to the LC-3 cap), so a base far below its target draws more trucks per period than one just below.
94. LC-1 runs at every viewer count, 0 included: that is the slow 0-viewer cadence.

**Who pays.**
95. The spawn costs `logistics.loadout_cost.LOGI_TRUCK` (0) at its spawn node (EC-13).
96. The truck pays `economy.upkeep.LOGI_TRUCK` (0; EC-4: "the trucks are expected to be free") from its home, after every viewer unit (EC-6, Q-TD-23, Q-TD-49), so with a non-zero truck upkeep the AI trucks ground first.
97. The cargo is real stock from the source's surplus or pool (§1b, §5 Sources).
98. If truck upkeep ever goes above 0, the EC-11 coalition floor check must count `max_live` AI trucks (open question L1).

**Viewer trucks keep priority (the value of `!join logi`).**
99. (a) LC-1 waits one full period on a new job, so viewers get the first pick.
100. (b) A viewer truck takes a full job's slot from an AI claimant (`tasking.human_displaces_ai`, Q-TD-11): the highest-id one with no cargo, else the highest id, so a loaded run finishes (Q-TD-110, `tasking.claim`); a displaced truck with cargo keeps its route and unloads at its target, an empty one stops at its next road node (PR #514), and a bare `!join logi` ignores AI claims when it counts free slots (`tasking._full`).
101. **A truck finishes unloading first (Q-SIM-130, NX-486; in code):** a truck with cargo standing on a friendly base that still takes stock or defense hp (`logistics.accepts`, the rule `_unload` applies) is unloading, and until its cargo is gone or the base is full the board gives it only a job at that base, such as its `resupply:<node>` (`tasking._unloading`, any owner): that claim sends it nowhere (no new path), its stop stays open and is reported there as usual, and it is a participant when the job ends DONE.
102. A truck holding cargo at a full base, or where it cannot unload, stays in the idle pool (Q-SIM-126), so it is never stranded.
103. Any claim of a job at another node first ends an open unloading stop (`tasking.claim`), and a stop at a base that is already full when the truck's turn comes ends there (`logistics._unload`), so each `SupplyDelivered` names the node where its units were unloaded.
104. (c) AI trucks never take the retake (Q-TD-100), the sanctuary repair job (NX-497; LC-1 skips it too), escort or patrol jobs (`tasking._may_take`).
105. (d) An AI delivery earns no merit, XP or AUTO assist (PROGRESSION).
106. An escort job for a threatened AI truck (§1b) is new work for players.

**What an AI truck is not.**
107. It is not a viewer unit (`World.viewer_units` counts COMMANDER units), so the idle floor, the night cap and its fade (NX-474, Q-TD-93), the last-base freeze (Q-TD-103) and the defeat-run hold (Q-TD-95) do not change; it adds 0 provocation (Q-TD-11).
108. It never counts as a capturer, as the Static's garrison and patrol units do not (Q-SIM-86), so a run past a neutral node never starts a bar (Q-TD-14, Q-GD-26: the AI never initiates offense).
109. As an unarmed ground unit at a friendly base it applies `capture.garrison_mult`, as any truck does (open question L4).

**Base lost mid-run, and retirement.**
110. Every truck follows the existing rules: the flip reroutes the run (§1b, NX-413), and a truck whose destination is no longer friendly drives to the nearest friendly base with room and unloads there (NX-123), so no cargo is lost on the road.
111. An AI truck with no cargo and no job for `director.idle_retire_s` (600 game s) is retired, the Static's rule (Q-SIM-84): it returns home first (111a), then is removed with `UnitDespawned{RETIRED}`.
111a. It returns before it retires, by the Static's rule (THREAT-DIRECTOR §7a 143a–143d, Q-TD-141): it drives to the nearest friendly base and is removed only on arrival; one that can reach no friendly base stays and is tried again each window.
112. A loaded one is kept, so stock + cargo + consumed stays exact.

113. **LC-2 Static demand convoys:** THREAT-DIRECTOR §5a, Convoys.

**LC-3 Per-job truck cap scaled by shortfall (both sides).**
114. A board resupply job's slots stay min(cap, max(1, ⌈missing ÷ `tasking.resupply_stock_per_slot`⌉)) as today, and a Static convoy job's become min(cap, max(`director.pol.convoy_slots`, ⌈shortfall ÷ `logistics.truck_cargo`⌉)), where shortfall is the `convoy_bases` value; a raised convoy count then shrinks to what `director.max_spawns_per_window` and the live room (EC-8) still allow, never below `director.pol.convoy_slots`, below which the base is skipped as before (CodeRabbit, PR #514).
115. In both, cap = base + ⌊need × (`tasking.resupply_slots_max_starving` − `tasking.resupply_slots_max`)⌋, and `base` is `tasking.resupply_slots_max` on the board and `director.pol.convoy_slots` for a convoy.
116. `need` is the share §1b's urgency already uses: the larger of (floor − stock) ÷ floor and the facilities' missing-hp share, from 0 to 1, and 0 for a stocking-only job.
117. The arithmetic is exact (fractions, floored).
118. Bounds: base ≤ cap ≤ base + (`resupply_slots_max_starving` − `resupply_slots_max`), and the loader refuses `resupply_slots_max_starving` < `resupply_slots_max`.
119. Overfill stays `overfill_factor` × slots.
120. A stocking job keeps today's cap, because Q-SIM-104 measured a flat 6 slots hurting the jets (autos with impact 25/39 → 3/39 on seed 4; cause [UNVERIFIED]).
121. So the raise applies only to starving or damaged bases, and the harness tunes it up from the no-op value (max_starving = slots_max).

**LC-4 With NX-474 and NX-475.**
122. AI trucks change no viewer count (above), so neither the night cap nor the quiet brake moves.
123. A Static convoy is no capture operation: the cap does not gate it.
124. A restocked Static base can pay garrison and operations sooner, but only inside the existing budget and caps.
125. The retake job stays viewer-only, with its ranking unchanged (Q-TD-100, Q-TD-106).
126. AI trucks on resupply leave viewer trucks free for it.
127. LC-3 adds slots only to a starving resupply job, which already outranks the retake.

**LC-5 Determinism.**
128. No new RNG.
129. Jobs are visited by rank then job id and bases by shortfall then node id.
130. Spawns take entity ids in that order.
131. A claim at spawn uses no draw; later board assignment uses the existing TB-5 `tasking` sub-stream.
132. The cap arithmetic is integer or `Fraction`.
133. Timers count running ticks, so they freeze with a pause and do not depend on `sim.time_scale`.
134. LC-1 keeps no state, and LC-2 reuses `DirectorState.last_convoy`.
135. AI trucks are ordinary entities (`owner_kind` is already in the snapshot); the AI-truck retirement clock reuses the coalition's `DirectorState.idle`, an existing snapshot field the coalition never used, so the snapshot format is unchanged (NX-473).

**Details (NX-473).**
136. LC-1 is `nexus.core.ai_trucks`, run in the `director` slot after upkeep and before the Threat Director (SIM-CORE SC-13, ECONOMY §5.1).
137. Interpretations: the loader rounds `period_s` up to whole economy windows (`Supply.ai_truck_period_ticks`), and the spawn step runs at the economy windows whose running tick is a multiple of it; retirement is checked at every economy window.
138. "Idle AI trucks go first": each idle AI truck (`tasking_gen.is_idle`) holds back one new spawn, in the jobs' rank order, and the board pass of the same tick tasks it.
139. `max_live` counts every coalition AI truck on the map, a wreck included.
140. A spawn at a base also keeps that base's starvation floor when it pays a non-zero `loadout_cost` (GP-7).
141. An AI truck never counts as a capturer through the shared rule (`capture._patrolling`: a coalition `AI_GARRISON` carrier has no capture weight, other AI garrison units still capture, Q-GD-31; it still garrisons, Q-TD-112).

**Keys (added with add-config-key by NX-473; CONFIG-AND-CONTENT §6.3, §6.6, §6.7).**
142. Reused: `tasking.resupply_slots_max`, `tasking.resupply_stock_per_slot`, `tasking.overfill_factor`, `tasking.human_displaces_ai`, `tasking.ai_jobs`, `logistics.loadout_cost.LOGI_TRUCK`, `economy.upkeep.LOGI_TRUCK`, `director.idle_retire_s`, `sim.max_live_units_per_side`, and `director.pol.convoy_period_s`, `convoys_per_period` and `convoy_slots`.
143. New, all PROPOSED, audience TUNER, edit role ADMIN:

| Key | Type | Unit | Start value | Bounds | Why |
|---|---|---|---|---|---|
| `logistics.ai_trucks.period_s` | number | s (game) | 900, a starting value to tune: one haven–west-airbase round trip (950 s, derived in GAMEPLAY-NOTES.md §5), rounded down to whole 60 s windows | > 0, rounded up to whole economy windows; tune 300–3600 | LC-1 spawn cadence and the viewer-first wait |
| `logistics.ai_trucks.max_live` | integer | trucks | 3 (Q-TD-128, harness C0): one full job (`resupply_slots_max`); 0 is off | ≥ 0 (0 = off); tune 0–48 (48 covers the raid break-even in GAMEPLAY-NOTES.md §5) | Caps live coalition AI trucks |
| `tasking.resupply_slots_max_starving` | integer | units | 6 (Q-TD-128, harness C0); = `resupply_slots_max` is the no-op | ≥ `resupply_slots_max` (loader); tune 3–9 | LC-3 raise for starving or damaged bases |
| `director.pol.convoy_demand_s` | number | s (game) | 900 (Q-TD-128, harness V2, chosen over 300 and off); = `convoy_period_s` is off (THREAT-DIRECTOR §5a) | > 0 and ≤ `convoy_period_s` (equal = off); tune 60–3600 | LC-2 demand spacing |

**Harness acceptance (NX-473 tracker row: "west-airbase stock above its floor at raid").**
144. Runs: one sha (L-37), 24 h, 6 seeds, overnight-0, quiet-5, prime-50 and raid-300, the current sweep's base overrides; a control at the no-op values, and candidates that raise `max_live`, `resupply_slots_max_starving` and `convoy_demand_s` in turn.
145. Pass: (1) at raid-300, west-airbase stock sampled every 15 game min while the coalition holds it has its median above its floor (500 = 0.25 × 2000) on every seed (the reading of "above its floor" is open question L7); report the share of samples above the floor and the `refuel` idle share.
146. (2) No regression against control on the Q-SIM-104 metrics (A2 median and tail share, autos and haulers with impact).
147. (3) At every profile, overnight-0 included, coalition AI deliveries and Static convoy deliveries each run every game hour that the side holds a base below its target.
148. (4) quiet-5 and overnight-0: Static captures and coalition-held nodes are not worse than control (the AI trucks' `garrison_mult` effect).
149. The sweep reports how far each candidate gets rather than raising values blindly.

150. **Movement speeds (owner, 2026-10-21, Q-SIM-38):** a unit's catalog `speed_mps` is its top speed, not a fixed speed.
151. It moves slower on slow roads (`speed_mult`), when damaged (`combat.damage_state.damaged_speed_mult`, COMBAT CB-6) and in an escorted group, which moves at its slowest member's speed so a convoy never outruns its armor escort (NX-369; Q-SIM-76 decided it lands with follow).
152. Airborne aircraft never fly below their stall speed `min_speed_mps`.
153. An aircraft may land only at an AIRBASE or the SANCTUARY its side owns, never at an FOB, HQ, port or bridge (speed 0 while landed); an idle aircraft still in the air orbits its last point (a CAP or scouting station) until it gets an order, and returns to base and lands on its own only at bingo fuel (STATE-MACHINES §4.1), so operators can hold CAPs and scout outlying areas for as long as fuel lasts (owner, 2026-10-21; NX-368).
154. All speeds are PROPOSED and tuned by playtests and the balance harness (NX-031).
155. A leader and the ground followers within `tasking.escort_leash_m` of it (not engaging) form a group; each member is held to the slowest member's `speed_mps` x its damage multiplier (before the road's `speed_mult`) every tick, and a follower still catching up to its station runs at its own top speed instead, so a faster escort can get ahead and a straggler beyond the leash neither slows the group nor is slowed (NX-369).
156. Aircraft are not capped by it: they orbit and never fly below `min_speed_mps`.

157. Logi trucks carry `cargo`, drive the road graph (A* over ROAD edges, cost = length / speed_mult), and unload over time at the destination.

158. A truck never drives into a node that turned enemy on its way: the capture flip replans every supply run and repair crew whose road enters it (§1b, Q-SIM-122, Q-SIM-125) (NX-413).

159. The starting numbers are in CONFIG-AND-CONTENT §6.3 (a truck loads 100, unloads 1.0 stock per world s, a base is starved below 25% of its maximum) (NX-123 part 1, Q-SIM-48 to Q-SIM-50).
160. The Static's rear source is a SANCTUARY node behind its HQ, like the coalition's.
161. A truck unloads up to the base's maximum; one sent by its operator's command stays parked at a full base with the rest of its cargo, and a truck at a destination that is no longer friendly drives to the nearest friendly base with room (else the nearest friendly base).

162. Forward deploy and refuel at bases (NX-123 part 2, Q-SIM-49, Q-SIM-51, Q-SIM-53, Q-SIM-54).
163. A strike jet or UAV (a full loadout costs 20 or 5 stock) that joins with a node target spawns at `west-airbase` while it holds at least 50 stock above its floor (and at least the loadout); a landed aircraft buys fuel at 0.5 stock per world s, so a full refill from empty costs 20 stock and takes about 67 ticks (40 world s, about 6.7 s of real time at `sim.time_scale` 6); a starved base fills it to half a tank only; an empty base stalls it (`RearmStalled`).
164. Ground units have no fuel or ammo modeled yet.

165. An aircraft's `loadout_cost` is half for a full tank and half for a full load of rounds (a unit with ammo and no fuel pays all of it for rounds); units pay `loadout_cost` x the hp share repaired at `logistics.repair_rate` (AIRBASE 1.0, HQ 1.0, PORT 1.0, FOB 0.5 hp per world s, SANCTUARY 2.0 and free); a starved base still repairs but sells only gun rounds and half a tank; the trucks (`loadout_cost` 0) repair free at a base (NX-124 part 2, Q-SIM-68).
166. The ammo share is the average over weapons of each weapon's missing share (so a missile round costs far more than a gun round).
167. A facility refills its ammo from its base at the normal rearm rate for `logistics.facility_rearm_cost` 10 per full reload (Q-SIM-69), while the base is friendly and uncontested and the facility is not Disabled.
168. Repair spend is reported as `SupplyConsumed{REPAIR}`, apart from `REARM`.

169. **Bridges** are nodes with HP.
170. A destroyed bridge removes its edge until it is repaired (Q-GD-11): **logistics trucks** can slowly repair a bridge, never a unit (Q-CBT-19; `logistics.bridge_repair_time_s` × `logistics.truck_bridge_repair_mult`), and **engineers** repair fast (building new crossings moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) under "Moved from the first-build review", Q-GP-9).
171. Every bridge has `logistics.bridge_hp` (PROPOSED 300) hp; only units on a STRIKE job at the bridge shoot it, never a unit holding a direct order on it (Q-SIM-124, NX-408); at 0 it emits `BridgeDestroyed` and every new road path avoids its edge (NX-373 part 1a, Q-SIM-105 to Q-SIM-107).
172. The fall destroys every ground unit of either side on the bridge's road within `logistics.bridge_collapse_radius_m` (PROPOSED 1000 m) of the bridge, cargo and all, the shooter credited with each kill; aircraft are not affected (NX-400, Q-SIM-112, owner).
173. Ground units already on the way reroute at once: one short of the bridge turns back and takes another road (or stops at its bank's node when there is none), one past the bridge and beyond the collapse radius carries on, and aircraft are not affected (NX-373 part 1b, Q-SIM-108).
174. Truck repair is in code (NX-373 part 2, STATE-MACHINES §4.3); engineer repair is not (below).
175. A truck (either side) parked at the bridge, on the road from a bank, repairs it at `logistics.bridge_hp / (bridge_repair_time_s × truck_bridge_repair_mult)` hp per world second (PROPOSED 600 s × 5: one truck repairs 300 hp in 3,000 world s, two in half), with no cargo cost; at full hp a down bridge's road returns and `BridgeRepaired` names the truck (NX-373 part 2).
176. The coalition board posts a repair-bridge job for each down bridge a truck can reach (§1b), and a down bridge is never fired at again while it is repaired.
177. Engineers come later (P4).

178. Units heal and rearm **only while landed or parked at a friendly node**, by spending stock.
179. They never heal passively (fixes the immortality bug).

180. **Empty bases stay bases** (Q-GD-17): at 0 stock, units can still land, garrison and wait there for a resupply convoy.
181. They get no fuel or ammo, but keep what they have and can take off again with reduced endurance.

Notes: GAMEPLAY-NOTES.md §5

## 5a. Base upgrades (P4)

1. Moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §5a.

## 5b. Facilities (Q-GP-21, Q-GP-25)

1. **Bases** (AIRBASE, FOB, PORT, HQ, SANCTUARY) are where you spawn, rearm and repair; every base except the sanctuary can be captured.
2. **Facilities** are attached to a base: radar sites and air-defense sites in the first build (factories are parked, Q-GP-41), pre-placed by the theater file.

3. A facility is an ordinary STATIC unit with HP and damage states.
4. It can be struck, disabled and repaired like any unit, its side follows its base, and it is never captured on its own.
5. This gives air roles targets of their own ("knock out the radar at EAST FOB before the convoy goes in").

6. **Modular:** a new facility kind (for example a missile-interception site later) is a new catalog entry through the content pipeline (CONFIG-AND-CONTENT §7a), not new kernel rules.
7. Building and upgrading facilities with surplus supply is GAMEPLAY-LATER §5a.

8. **Neutral bases (Q-GP-36):** a neutral base just exists until captured and has no facilities; the theater validator rejects facilities at a base whose start owner is NEUTRAL, so a facility's side is always COALITION or ENEMY.

9. Facilities have no crew (crew count 0), so disabling one never produces a downed-crew marker.

10. **Never destroyed (Q-GP-37):** infrastructure is always repairable: a facility's hp floors at Disabled and it is never Destroyed (default; Q-CFG-16 option `combat.facility_indestructible`); bridges already repair (§5).

11. **Repair (Q-GP-26; in code, NX-124 part 2: 1 stock per `logistics.facility_repair_hp_per_stock` = 10 hp, base without a capture bar = not contested):** a damaged or disabled facility repairs over time at `logistics.repair_rate.<node_kind>` by spending its base's stock while the base is friendly and not contested, like units at a base.
12. A disabled facility does nothing (no sensing, no fire) until repaired back up to the restore line, `combat.facility_restore_frac` (shipped: the Mission-kill line; COMBAT CB-9, Q-TD-86, NX-472: from its 14-hp floor, about 39 world s at an airbase, 78 at a FOB, for a 150-hp site).
13. Deliveries become stock and stock repairs facilities, so resupply is how logistics fixes a base (Q-GP-47 replaces the Q-GP-30 truck multiplier); engineers (P4) repair faster, also away from a base.
14. **A facility seized with its base** (§8, NX-471, Q-TD-78) arrives Disabled at its floor and repairs `capture.seized_repair_slowdown` times slower (PROPOSED 92) until it reaches the restore line: 10.0 game minutes at an airbase and 19.9 at a FOB with steady supply, against 6.5 game s for a struck site.

15. **Visibility (Q-GP-27, revised by Q-FOW-15):** bases are known to both sides, but a base's facilities are unknown to the other side until discovered by ISR (an air, ground or radar sensor, passive detection of an emitting site, or capturing the base).
16. A discovered facility stays marked for the campaign; its details refresh only when observed again, so unsensed strikes and repairs stay hidden (FOG-OF-WAR FOW-13).

17. Parity: the Static's facilities follow the same rules.

## 6. Combat

1. Moved to [COMBAT](COMBAT.md) (NX-312, 2026-10-20): targeting, shots, hit probability, damage, wrecks, stance, munitions and the who-can-shoot-whom table.
2. Kills and assists generate events; a recon "paint" grants assist credit (PROGRESSION).

## 6a. Crew, CSAR and consequences

1. **Crew survival** and downed-crew markers: COMBAT CB-8.
2. *Working name "crew"; a playful mascot name is possible under the brand guide.*

3. **CSAR** (P4+): [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §6a.

4. **Consequences without punishment** (Q-CBT-9): losses cost the *team* (base stock spent, a longer respawn for that unit type) rather than taking XP from the player.

## 7. Packages (P4)

1. Moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §7.

## 8. Capture

1. **Base defenses first (Q-GD-18):** each node has defense HP (configurable, upgradable via §5a).
2. Capture can't begin until HP is 0 (default; Q-CFG-16 option `capture.requires_defenses_down`).
3. Air strikes, artillery and ground fire reduce HP; supply deliveries repair it; starvation slowly drains it (`logistics.starve_hp_drain_per_min`, PROPOSED).
4. Max HP by kind `capture.defense_hp.<node_kind>` (PROPOSED: AIRBASE 500, FOB 300, HQ 800, PORT 300, SANCTUARY 1000; a BRIDGE has none until NX-373) (NX-124 part 3, Q-SIM-71).
5. An owned node starts full, a NEUTRAL node at 0 (so it can be captured at once), and a node that changes hands is 0 for its new owner.
6. Weapons with the STRUCTURE target fire on the HP of an enemy-owned node in range only when no unit is in range (COMBAT CB-10), unless the shooter holds a STRIKE claim on that node and `combat.strike_structure_first` is on (Q-TD-55; shipped on since NX-412 part 5b, Q-TD-79).
7. A truck at a node with full stock still unloads while its defenses are below the maximum, each unit going straight into them.
8. Every whole stock unit unloaded into a node rebuilds `logistics.defense_repair_hp_per_stock` (PROPOSED 2) HP in that tick, up to the maximum.
9. A node with finite stock below its starvation floor loses `logistics.starve_hp_drain_per_min` (PROPOSED 5, whole HP) per game minute, counted in running ticks with an exact carry; the drain pauses while the node is not starved.
10. The gate is on starting a bar: a bar already running is not stopped by a later repair (it fills or decays by the rules below), and the flip sets the HP to 0.
11. Down and back: `NodeDefensesDown` when HP reaches 0 and `NodeDefensesRestored` only when it has been rebuilt to full, so a node flapping around 0 gives one pair per cycle.
12. A truck rebuilds a SANCTUARY only by parking there, not by unloading (§9 last stand).

13. Capture requires a ground or logistics unit (a logistics unit counts as half a capturer, `capture.logi_weight`, Q-SM-7) within `capture.radius_m`, with no enemy ground unit contesting it.
14. Progress takes `capture.time_s` (PROPOSED 120 s, world time, Q-ALN-23), scaled by the number of units with diminishing returns.
15. Air units can't capture (default; Q-CFG-16 option `capture.air_counts`: airborne aircraft then count as capturers weighing `capture.air_weight`, never contesting).
16. **Formula (Q-SIM-22, Q-SIM-26):** `time = max(capture.min_time_s, capture.time_s × quiet_mult(v) ÷ n^capture.multi_unit_exponent)`, where `n` is the number of capturing units in radius and `v` the number of live viewer units in kernel state (deterministic, no new input).
17. `quiet_mult` rises linearly from `capture.quiet_floor` at `v` = 0 to 1.0 at `v` = `capture.quiet_ref` and stays 1.0 above.
18. `min_time_s` is the only cap on how fast a crowd can flip a base (Q-GP-4).
19. A contested bar decays at `capture.decay_per_s`, the same rate as an abandoned one (owner, 2026-10-21, Q-SIM-23); at 0 the bar is removed and the start rule applies again, so a raid that leaves does not leave a half-captured base and an unarmed capturer cannot block a node for ever.
20. `min_time_s` applies after the garrison and empty-base modifiers.
21. "at the base" and "in radius" are both `capture.radius_m`; only GROUND units and aircraft LANDED at the base count there; two sides at a neutral node follow STATE-MACHINES §4.2 (NX-125).
22. The quiet-stream factor applies to the coalition only (below; `capture.quiet_sides`).
23. Easing other loops (repair, resupply, rearm) waits for harness results (Q-SIM-27).

**An HQ is very hard to capture, hardest alone (in code, NX-490; Q-TD-105 owner 2026-10-29, Q-TD-127 lead, owner may veto).**
24. An HQ capture still wins at once (§9, `campaign.victory.hq_capture`), and the defenses-down start gate above is unchanged.
25. Two per-node-kind keys enter the formula: `time = max(capture.min_time_s, capture.time_s × capture.time_mult.<kind> × quiet_mult(v) ÷ n^(capture.multi_unit_exponent + capture.extra_exponent.<kind>) × modifier)`.
26. Every kind but HQ keeps 1.0 and 0, so its capture is unchanged.
27. HQ gets PROPOSED 20 and 0.5: a capture takes 20 times longer, and each extra capturer helps in proportion (n^1.0, not n^0.5), so a lone capturer is slowest relative to a crowd.
28. The keys are by node kind and apply to whichever side captures (EC-3 parity; strait-1 has only the Static HQ, the coalition's sanctuary cannot be captured, Q-TH-7).
29. `min_time_s` still caps a crowd.

30. **Facilities never contest (Q-GP-38):** facilities do not freeze or slow capture and do not count for the garrison or empty-base modifiers below; base defense HP models fixed defenses.

31. **Garrison modifier (Q-GD-32, Q-ALN-33):** a combat-capable defending unit at the base freezes capture (contested).
32. Defending units that cannot contest (parked air, Disabled units) heavily slow it; an empty base is captured faster.
33. Both are configurable multipliers (PROPOSED).
34. Applies to both sides.

35. **Facilities at a captured base (Q-GP-25, amended by Q-TD-78 / NX-471; Q-TD-135 lead, owner may veto; in code, NX-471):** facilities are not mobile units: when a base flips, its facilities switch side with it.
36. With `capture.facilities_disabled` on (the default) they arrive **Disabled**, and the new owner repairs them slowly.
37. So a captured air-defense site or radar does nothing for a while, and the old owner can retake the base before it is back (the owner's "retake before the SAM is back" beat, Q-TD-78 (a): "repairs should take a while").
38. With the switch off they switch side and keep their damage, which is Q-GP-25's original rule and the code before NX-471 (`_switch_facilities`, `capture.py`).

**The flip.**
39. The facilities change in the flip tick, after `NodeCaptured` and the Static's provocation, and before the loser's units are resolved; this is today's order (`capture.py:349-372`).
40. For each facility whose `base_id` is the node, in id order, the sim:

41. changes its side;

42. sets its hp to min(hp, its floor), whatever its hp was.
43. The floor is the highest hp still Disabled (`UnitRules.floor`, `rules.py:452-454`), 14 for the shipped 150-hp sites (`content/units/air-defense-site.yaml:9`, `radar-site.yaml:9`; `combat.damage_state.disabled_below` 0.10);

44. sets its damage state to DISABLED, emitting `UnitDamageStateChanged{from, to: DISABLED}` when it was not already Disabled (no event when it was);

45. sets both repair carries, `Entity.repair_milli` and `repair_debt` (`world.py:325-326`), to 0;

46. marks it *seized* (`Entity.seized_carry` = 0, State below);

47. hands it over in the fog (`fog.hand_over`, `fog.py:288-305`).
48. Because the disable comes first, the loser's new marker records the site as DISABLED.

49. There is no separate "low-hp" state.
50. A Disabled facility above the restore line fails the restore check (`combat.py:676-679`, `UnitRules.state_after`, `rules.py:441-448`), and the floor is the state a strike already leaves a site in (COMBAT CB-9).
51. The facility's ammo is unchanged; a Disabled facility buys none until it is back on line (`rearm.py:137`).

**What Disabled does: unchanged (COMBAT CB-9).**

52. A Disabled facility does not fire (`combat.py:147-148`).

53. It is not a valid target, and a shot already in flight at it fizzles (`combat.py:244-256, 505-510`).

54. It senses, emits and listens for no one (`fog.is_off_facility`, `fog.py:204-207`, read at `fog.py:152, 241, 251, 285, 326` and `launch.py:250`).
55. So a seized radar adds nothing to its new owner's FoW coverage or SIGINT, and a seized air-defense site has no ring.

**Rings.**
56. TB-2 (`tasking.crosses_ring`, `tasking.py:1360-1365`) and the Director's TD-2 read a side's discovered markers, not live sites, and they skip a marker whose last-seen state is DISABLED (`ring_crossed`, `tasking.py:1393-1405`).
57. At the hand-over the new owner drops its marker of the site, and the loser gets a new one with the site's state at the flip, which is DISABLED.
58. So the loser's board and Director are not locked out by a ring they have just lost; that lockout was the S1 finding behind Q-TD-78.
59. The loser's marker stays DISABLED until the loser observes the site again (FOG-OF-WAR FOW-13).
60. Once the site is back on line, a loser that has not looked at it again can route through a live ring it believes is off.
61. That is the existing "last seen" fog rule, not a new one.

**Repair under the new owner.**
62. The facility uses the existing base repair (§5b, `rearm.py:206-233`).
63. It repairs while its base is friendly and has no capture bar (`rearm.station`, `rearm.py:84-93`; `rearm.py:213` reads the rate).
64. It pays from the base's stock, 1 stock per `logistics.facility_repair_hp_per_stock` (10) hp, and repairs free at a sanctuary.
65. It stays Disabled until the restore line, `ceil(combat.facility_restore_frac × hp)`, which is 53 of 150 (Q-TD-86).

**Slower while seized.**
66. A seized facility's rate is its base kind's `logistics.repair_rate` divided by `capture.seized_repair_slowdown` S (PROPOSED 92, Q-TD-135).
67. Each tick:

68. the base rate in thousandths of an hp a tick (`Supply.repair_milli`, `rules.py:911`) is added to `seized_carry`;

69. `seized_carry // S` of those thousandths go into the normal repair step, paid and carried as today;

70. the remainder stays in `seized_carry`.

71. So the average rate is exactly rate ÷ S, with integer state.

**No stock, no progress.**
72. On a tick when its base can pay for nothing (finite stock with no room, `rearm.py:221-223`), neither carry moves; the stop stalls with `RearmStalled` as today.
73. A starved base that still has stock repairs (§5).
74. The existing repair-debt rule lets a repair accrue up to 9 thousandths of an hp before any whole stock unit is owed, so a site at a 0-stock base moves that far before it stalls; and when stock room limits the draw (0 < m < the slowed whole thousandths), the unpaid thousandths are dropped, not carried.
75. Both are under 1 hp.

**Back on line.**
76. At the restore line the facility leaves DISABLED (`UnitDamageStateChanged`) and `seized_carry` is cleared to null.
77. The rest of the repair, up to full hp, runs at the base's normal rate (`UnitRepaired` at full).

78. A captured base keeps its stock ("Stock stays with the node", `capture.py:40`), so a captor finds stock there and starts repairing at once.
79. Only S sets the time; more deliveries do not shorten it.

**Resupply side effects (existing code, unchanged).**

**Resupply job.**
80. A seized facility's missing hp counts in its base's `facility_damage` (`logistics.py:221-232`).
81. So the new owner's board posts `resupply:<base>` for as long as the facility is below full hp, even at full stock (`tasking_gen.py:370-392`; urgency from the missing-hp share, `starving_need`, `tasking_gen.py:417-421`).

**REINFORCE_IADS.**
82. A Static air-defense site taken back by the Static meets that operation's precondition (`content/operations.yaml:58-64`; `director.reinforce_damage_above` 0, `balance/default.yaml:314`).

83. Both now last for a seized repair (about 10 to 20 min) instead of seconds, and neither speeds it up.
84. The NX-471 harness line (§11) watches the hauling this causes.

**Retaken mid-repair.**
85. The flip back applies the same rule.
86. The facility changes side, its hp drops back to its floor (progress is lost), it stays DISABLED (no event), and it is seized afresh (carry 0) for the side that retook it.
87. A capture bar on the base already pauses the repair (no station while a bar exists), so a counterattack stops the clock before it completes.

**Parity (ECONOMY EC-3).**
88. One rule applies for whichever side flips the base, with no side check and no side-specific value.
89. A coalition capture of a Static base and a Static capture of the mirrored coalition base give mirrored outcomes.
90. No provocation is added: the flip's own `base_captured` covers it (`provocation.captured`, called at `capture.py:367`), and `suffered_hit` runs only on hits (`provocation.py:110-129`).

**Switch.**
91. `capture.facilities_disabled` (bool, default true, `RULE_DEFAULT`: the owner decided the rule, Q-TD-78 (a)).
92. Set to false, the flip changes no hp, state or carry, `seized_carry` stays null, and the run is exactly as before NX-471.
93. S is then not read.
94. Neither key is hot-reloadable, because they are capture rules, like `capture.requires_defenses_down` (CONFIG-AND-CONTENT §6.5).

**State (in the hash).**
95. NX-471 is snapshot format 39 (`FORMAT_VERSION = 39`, `world.py`; 38 was NX-466).
96. It adds `Entity.seized_carry: int | None`.
97. The field is null for every entity that is not seized.
98. For a seized facility it holds the thousandths of an hp carried toward the next slowed thousandth, with 0 ≤ carry < S.
99. Restore refuses it on a non-facility, on a facility that is not DISABLED, at S or above, below 0, or when `capture.facilities_disabled` is off.
100. An older format is refused.

**Events.**
101. No new event.
102. The flip emits `UnitDamageStateChanged{to: DISABLED}` after `NodeCaptured`, for each facility that was not already Disabled.
103. The repair emits `UnitDamageStateChanged` out of DISABLED at the restore line and `UnitRepaired` at full hp, as any facility repair does (`rearm.py:236-252`).
104. An overlay "site off line" cue can read these; a "back on line" sitrep is a follow-up.

105. **Units at a captured base (Q-GD-32):** when a base flips, each mobile unit there escapes to the nearest reachable friendly base: a ground unit when a road route exists, an aircraft when its fuel reaches one of its landing bases (Q-SM-10).
106. Every other mobile or parked unit there is destroyed, with a crew-survival roll (§6a).
107. Facilities (units with a `base_id`) are exempt: they switch side (§5b), Disabled under NX-471 (above).
108. Applies to both sides.

109. Progress decays when the node is uncontested and unoccupied.
110. A capture can't flip twice in one tick (property test).

Notes: GAMEPLAY-NOTES.md §8

## 9. Campaign, objectives, win/loss (resolves critique #12)

1. **Modes:** Total Domination (MVP).
2. Hold the Line and Siege moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9.

3. **Theater objective (Q-GD-19):** calm, not railroading.
4. The objective mode is set per campaign:

5. `timed` (default): every `campaign.objective_period_min` (PROPOSED 15 min, game time) the system picks one frontline node uniformly (`campaign.objective_pick: uniform`, its only value so far; Q-CFG-16) (a node next to one owned by the other side or by no one; never the sanctuary or the Static's HQ; own `objective` RNG stream, Q-SM-1, Q-SM-11) and announces it with a timer: capture it if the enemy holds it, hold it for the period if you do.
6. Completing it gives a merit bonus.
7. A node the coalition does not own is to be captured; one it owns is to be held, and counts only if held when the timer ends, however often it changed hands (Q-SIM-61); the next objective appears the moment one resolves (NX-126).

8. `off`: sandbox/creative, no system objectives.

9. The owner and Admins can also set objectives; a GM cannot (Q-ALN-10).
10. Whenever an objective exists it is visible on screen.

11. **Strategic nodes (Q-GP-17, Q-GP-21):** AIRBASE, FOB and PORT bases count toward the hold fractions below.
12. BRIDGE nodes and the SANCTUARY do not, and facilities (radars, air defense) never count on their own; the enemy HQ is its own win route.

13. **Victory (Domination):** hold ≥ `campaign.victory_node_frac` (PROPOSED 0.75, Q-TD-142) of strategic nodes for `campaign.victory_hold_min` (PROPOSED 30 min, game time) continuously, **or** capture the enemy HQ (default; Q-CFG-16 option `campaign.victory.hq_capture`).
14. Only the coalition can win this way: the Static holding the nodes is not a defeat (Q-SIM-62, NX-126).
15. The rubber-band zone is tuned to 55–75% so that victory sits beyond it.
16. **Contested hold (Q-TD-19, ECONOMY EC-9):** while the hold runs, the sim emits `VictoryHoldStarted` and then `VictoryHoldBroken` or the victory.
17. The hold is public (overlay and sitrep), and the Static may target a node in it, with a sitrep.
18. `VictoryHoldStarted{node_ids, ends_at_tick}` on the first running tick of the hold (the held strategic nodes; `ends_at_tick` on the campaign clock) and `VictoryHoldBroken{node_id}` (the hold node lost, lowest id first) when it breaks, none when the campaign ends during it (both now carry `progress_ticks`, and a break decays instead of resetting: ECONOMY EC-9a, NX-489); the hold's nodes are in the Static's view, its capture operations on them score x `director.score.victory_hold_mult`, and launching one emits `ThreatAdaptation{HOLD_AT_RISK, node_id}` for the sitrep (THREAT-DIRECTOR §7a) (NX-412 part 4).

**Broken hold decays (NX-489; Q-TD-102 owner 2026-10-29, Q-TD-126 lead, owner may veto; rule in ECONOMY EC-9a).**
19. A broken hold keeps its progress instead of restarting from 0.
20. The kept progress drains slowly for `campaign.victory.decay_slow_min`, at `decay_slow_rate`, then faster, at `decay_fast_rate`.
21. It resets to 0 when it drains out, or when the other side has repaired a lost hold node to full defense HP (`campaign.victory.reset_on_repair`).
22. If the coalition gets back above `victory_node_frac` before then, the hold resumes from what is left.
23. "Continuously" above then means "with no reset".
24. With `campaign.victory.hold_break: reset`, today's rule applies.

**Hold pauses under pressure (NX-466; Q-TD-84 (b), owner 2026-10-28; readings Q-TD-134, lead, owner may veto; rule in ECONOMY EC-9b; in code, NX-466).**
25. A running hold gains nothing on a tick where one of its nodes is under the other side's pressure, and it does not reset.
26. Pressure means any of: a capture bar, defenses down (from `NodeDefensesDown` until `NodeDefensesRestored`), or a claimant of a capture operation's CAPTURE step within `tasking.defend_radius_m` of the node.
27. The hold resumes when no node is pressured.
28. It is never won while paused, and it neither gains nor decays while paused.
29. A break during a pause decays from the paused progress (EC-9a).
30. `VictoryHoldPaused{node_id, reason, progress_ticks}` and `VictoryHoldResumed{ends_at_tick, progress_ticks}` carry it on the wire.
31. The tick a hold starts always gains 1.
32. The switch `campaign.victory.pause_on_pressure` (default true) turns the rule off.
33. With the rule on, "continuously" above means "with no reset, not counting paused ticks".

34. **Defeat (Q-TH-7, replaces the Q-GD-7 rule):** the sanctuary can be besieged but never captured.
35. It has defense HP like any base (§8), the Static can strike it, and trucks parked on it repair it (the last stand below; it takes no cargo, `logistics.accepts`).
36. The coalition loses when the sanctuary's defense HP stays at 0 for `campaign.defeat.hold_min` (PROPOSED 30) minutes of game time: a visible last stand in which players can repair or resupply it.
37. Losing other ground squeezes the front and lengthens travel but is not itself a loss.
38. **Idle floor (Q-GP-28, Q-GP-44, Q-TH-7):** with 0 humans present (no live viewer unit under player control; AUTO units don't count), capture progress on the theater's `forward_airbase` freezes and the sanctuary's defense HP cannot drop below 1 (`campaign.idle_floor.sanctuary_min_hp`; the whole floor is the default, Q-CFG-16 option `campaign.idle_floor.enabled`), so the Static can never take that airbase and a war is never lost while nobody plays; the slow idle drift is a deliberate "come back and retake it" hook.
39. The sanctuary base can never be captured.
40. The hold is `campaign.defeat.hold_min` (PROPOSED 30) of running ticks with the coalition sanctuary's HP at 0; a repair to the reset threshold resets it and a repair below it pauses it (NX-499, sub-bullet below); `CampaignEnded{result: DEFEAT, winner: ENEMY}` with the usual scores (NX-124 part 3).
41. Within a tick the order is the objective, then victory (HQ capture, node hold), then defeat, then the time limit, so a victory beats a defeat and a defeat beats the limit.
42. Idle floor: "no humans" is "no live COMMANDER-owned unit" until the AUTO state exists (then AUTO units will not count); while it holds, a hit cannot take the sanctuary below 1, the defeat run is held, and once nobody has played for `campaign.defeat.hold_min` it restarts from 0, so a short gap (a death and respawn) does not save the siege and a viewer who joins after a long empty stretch starts a full `hold_min` (Q-TD-95: nobody loses the war by joining an empty map), and a bar on the `forward_airbase` (while the coalition owns it) neither starts, fills nor decays.
43. **Last stand (Q-SIM-71):** each friendly logistics unit (LOGI_TRUCK; ENEMY_CONVOY by parity) parked at its side's sanctuary (no path, `last_node` the sanctuary, not Disabled) rebuilds its defense HP at `capture.sanctuary_repair_hp_per_s` (PROPOSED 1.0 per world second per unit; two units repair twice as fast), from the sanctuary's infinite supply with no stock debit, up to the maximum; a repair that lifts the HP to the reset threshold resets the defeat hold, and below it pauses the hold (NX-499).
44. Not while paused.
45. **Call to arms (Q-TD-122 (a), NX-493, in code):** while the sanctuary's HP is below full and the coalition tracks an enemy aircraft or ground unit within `tasking.defend_radius_m` of it, the coalition board posts `defend:<sanctuary>` at the top urgency, and the drop from full emits the `SANCTUARY_AT_RISK` sitrep (§1b `defend:`); a defeat stays possible.
46. **Repair job (NX-497; Q-TD-124 owner: (c) then (a); Q-TD-129; in code):** the board posts `resupply:<sanctuary>` for viewer trucks only while the HP is below full, and it is DONE at full HP with a claimant parked (§1b `resupply:`).
47. Open: lowering `capture.sanctuary_repair_hp_per_s` to a harness-set rate (step 1; the value is still 1.0).
48. The owner chose a reset threshold (Q-TD-129 (6) (b)); it is the sub-bullet below, in code (NX-499): below the threshold a repair only pauses the hold.
49. The Static's rear source is never a STRUCTURE target (it cannot be captured and the Static has no defeat, Q-SIM-64); the coalition sanctuary is.

**Defeat reset threshold (NX-499; Q-TD-129 (6), owner 2026-10-29: "B (your rec)"; the details are Q-TD-131, lead, owner may veto).**
50. The rule uses a threshold T = max(1, ⌈`campaign.defeat.reset_hp_frac` × `capture.defense_hp.SANCTUARY`⌉) hp.
51. T is fixed at load from the exact decimal: PROPOSED 0.5, so T = 500 of 1000.
52. The rule reads the sanctuary's hp once per running tick in the `objectives` slot, as today (after combat and the repair):

53. **hp 0:** unchanged.
54. The run counts.
55. With the idle floor on and no viewer unit, the run is held while the empty stretch counts, and it resets once the stretch reaches `hold_min` (Q-TD-95).

56. **0 < hp < T, the repair pause:** the run neither counts nor resets.
57. A run that is 0 has nothing to pause: the run and the empty stretch stay 0, as today, so a sanctuary scratched from full never starts a run.
58. A run in progress keeps its empty stretch as at hp 0.
59. A live viewer unit clears the stretch.
60. With the idle floor on and nobody playing, the stretch counts, and at `hold_min` the run resets to 0.
61. So a paused run cannot wait out an empty night and then end the war minutes after a viewer joins (Q-TD-95 again).
62. If the hp falls back to 0, the run resumes from the paused value.

63. **hp ≥ T:** the run and the empty stretch reset to 0, as today's rule does at 1 hp.
64. After that, a fall below T or to 0 starts from 0: reaching T saves the base, and falling back does not restore the old run.

65. **`reset_hp_frac` 0:** T is 1, the pause band is empty, and the rule is exactly the pre-NX-499 one (a §11 test).
66. 1.0 resets only at full hp (Q-TD-129 (6) (c)).

67. **Clock:** this pause belongs to the defeat run only; it is not a sim pause.
68. The campaign clock (`running_ticks`), the time limit and the objective timers keep running through it.
69. A sim pause freezes the run, the repair and the clock, as today.
70. The run still counts only running ticks.

71. **Signal:** no contract change.
72. No wire field carries the defeat run today.
73. The only defeat-related wire signals are `CampaignEnded{DEFEAT}`, the sanctuary's `NodeDefensesDown`/`NodeDefensesRestored` and the `SANCTUARY_AT_RISK` sitrep.
74. A public defeat countdown with a "holding" state would be a later overlay item, not part of NX-499.

75. **Campaign clock:** 72 h, the shipped `campaign.time_limit_h` (game time, Q-ALN-1; admin-adjustable, schedulable per campaign, Q-GD-5). The owner set 72 h on 2026-11-04 (Q-DEV-44), replacing Q-GD-5's 48 h target, so the clock, the time limit and acceptance target A1 agree.
76. It **never pauses for lack of humans** (Q-GD-4 amended): at 0 humans the Static drops to Pattern of Life (THREAT-DIRECTOR §5a).
77. Only a sim pause with a reason stops the clock: a staff pause (ADMIN-RBAC pause flow), the auto-pause when the broadcast has been offline longer than `ops.offline_pause_after_min` (reason TECHNICAL, Q-OPS-8), the weekly maintenance window, or the owner's Ceasefire mode (Q-OPS-9); pause reasons are STAFF, TECHNICAL, MAINTENANCE and CEASEFIRE (Q-ALN-3), and a STAFF pause may carry a sub-reason (RAID, ABUSE, CONTENT, OTHER; Q-ALN-31).
78. Timers on both sim clocks freeze with it (Q-CFG-8, Q-ALN-2).

79. **Time limit (Q-GD-29, Q-TEST-6, Q-TEST-7):** `campaign.time_limit_h` (PROPOSED 72).
80. The owner or an Admin may extend a running campaign; each extension is logged and the total is capped by `campaign.max_extension_h`.
81. Unlimited campaigns are parked (GAMEPLAY-LATER).
82. Hitting the time limit decides by score (Q-SIM-64) = `campaign.score.average_weight` (PROPOSED 50) × a side's average share of strategic nodes over the campaign + `campaign.score.final_weight` (PROPOSED 50) × its share at the final tick + `campaign.score.objective_points` (PROPOSED 5) per completed objective (coalition only); sustained play counts and the last hour can still swing it.
83. Higher score wins; a Static win is `TIME_LIMIT` with `winner: ENEMY`, shown as a defeat ("SIGNAL LOST"); there is no mid-war Static domination win, so a war never ends while chat is asleep. an exact tie is a draw with no special screen (Q-GP-10).
84. The draw band, Stalemate screen, special event and banter are in [GAMEPLAY-LATER](GAMEPLAY-LATER.md) under "Moved from the first-build review".

85. **End of campaign (Q-UX-8, Q-UX-4):** a victory or "SIGNAL LOST" moment (optional configurable zoom on the final action), a ~5-minute after-action review (top operators per role, best rescue, the "what you didn't see" reveal with the seed, Q-CT-2), then a looping War Briefing card during the intermission.
86. Advancement is configurable: `auto_advance` (next war after N min) or `await_owner` (one-tap owner approval).
87. The next theater rotates archetypes with no back-to-back repeat, reusing the first theater with a new seed until more exist (Q-SM-4).

88. **Units reset each war** (Q-GD-23); rank, callsign, cosmetics and stats persist.
89. Survivor reward: [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9.

Notes: GAMEPLAY-NOTES.md §9

## 9a. Theater style and orientation (owner, 2026-10-17)

1. **Theater variety** is a design goal; the archetype rotation moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9a.

2. **Theater #1 (Q-GD-33, Q-GP-22):** small, about 8 bases (3 coalition, 3 Static, 2 contested; a sketch for the NX-008 sign-off).
3. Later theaters in the rotation are larger (12–20 bases).
4. A map that grows inside one campaign is parked in GAMEPLAY-LATER.
5. It is a land-leaning map with a bridged strait, so the water theme works before naval units arrive (P3).

6. **Orientation:** the coalition (chat) is always on the **left (west)**, the enemy on the **right (east)**, and the main axis of advance runs left → right.
7. Theater files must declare `orientation: west_to_east`, and the theater validator rejects maps whose sanctuary isn't in the left third.
8. For the vertical 9:16 layout, see Q-GD-13.

9. **Urban terrain** rules (NX-129) moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9a.

## 9b. Campaign carry-over

1. Moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9b.

## 9c. Theme vs strategy rule (owner, 2026-10-17)

1. The signal and Static theme is a **presentation layer over the strategy game, never a replacement for it**:

2. **TS-1:** Chat volume and viewer count never directly buff, nerf or decide anything.
3. Outcomes come only from units, logistics, fog of war and the director rules.
4. (The director already scales on coalition *units and supply*, not on chat activity.) Supply-drop redemptions therefore have a fixed global hourly cap (`support.supply_drop.max_per_hour`, PROPOSED/TBD by harness) plus a shared cooldown, independent of audience size (Q-SUP-7, SUPPORT-REDEMPTIONS).

5. **GM scope (Q-AI-8, Q-ALN-10, Q-ALN-11):** during play a human GM drives the Static and triggers world events only, and injects jobs only into the Static's Tasking Board (TB-11).
6. A world event may help the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction.
7. A GM never grants units, ammo or XP to specific players.
8. Campaign setup (objectives, unlimited ammo and other campaign options) is owner/Admin only, never GM.
9. Every GM action is logged and flagged in replays.

10. **TS-2:** "Momentum" stays a strategic measure (nodes, stock, recent events).
11. Any "signal strength" visuals are cosmetic flavor on top of it: map color brightness, static overlay intensity, sound.

12. **TS-3:** The game must play well at **0 viewers** (AI garrison + Pattern of Life, Q-GD-4 amended) and scale smoothly upward.
13. No mechanic may require a minimum crowd.

14. **TS-4:** Lore names (The Static, Relays, etc.) relabel things on screen and in sitreps only.
15. Mechanics and their docs keep plain names (node, unit, supply).

## 10. Readability rules (stream-facing)

1. Moved to OVERLAY (Q-GP-9); the always-visible items and the 5-second "who is winning" criterion are the overlay's acceptance tests.

## 11. Test plan

1. Every rule above gets a unit test plus the property tests from TESTING-STRATEGY §3.1.
2. Balance scenarios are defined in the harness.
3. Tasking Board assignment (TB-5) gets a replay determinism test, and pause tests check that game-time and world-time timers freeze (Q-CFG-8).
4. Specific checks for the Q-ALN decisions:

5. Q-ALN-1: with `sim.time_scale` ≠ 1, a game-time timer (e.g. `presence.idle_handoff_min`) fires after the same number of ticks as with `sim.time_scale` = 1, while world-time movement scales.

6. Q-ALN-6: a configured duration that is not a whole number of ticks converts to the next tick up, never down.

7. Q-ALN-2: while paused, `!me`, `!status`, `!quiet` and a reserve-queue join are accepted; every other command gets "war paused" and changes no sim state.

8. Q-ALN-9: an AUTO unit occupies its commander's slot; a `!join` from that commander reclaims it and the live-unit count for that commander stays 1.

9. Q-ALN-10/11: a GM cannot set objectives or campaign options, and a GM job injection into the Quorum's board is rejected.

10. Q-ALN-12: `!quiet` twice returns the opt-out to its original state, and each use gets a confirmation naming the new state.

11. Q-ALN-23: with `sim.time_scale` ≠ 1, capture progress scales with it, while the claim lease and the package fill wait take the same number of ticks as at `sim.time_scale` = 1.

12. Q-ALN-24: while paused, a ban despawns the banned commander's unit and a director override is rejected.

13. Q-ALN-25: a Disabled unit reaching idle retire despawns where it is and no cargo returns to the reserve; a `hold` unit handed off to AUTO stays at base until it claims a job.

14. Q-ALN-26: a `!join` while paused queues even with a free slot; `!quiet` and `!help` do not reset the idle timers.

15. Q-ALN-30: a job completed by an AUTO unit adds an AUTO assist and no XP or merit.

16. Q-ALN-34: a kill, a supply delivery or capture participation by an AUTO unit adds an AUTO assist and no XP or merit.

17. Q-GP-25 (amended by Q-TD-78 / NX-471): when a base flips, its facilities switch side; with `capture.facilities_disabled` off they keep their hp, and with it on they arrive Disabled at their floor (NX-471 list below); no facility rolls crew survival.

18. Q-GP-31/33: a follow loop or self-follow is rejected with `FOLLOW_TARGET_INVALID`; when a middle leader despawns, its followers take that leader's own leader.

19. Q-GP-24: the source rule never takes a base below its starvation threshold.

20. Q-TD-99..101 (NX-475, `tests/core/test_retake.py`): a retake job only once the node's defenses are down; only on a start strategic node not held now, with no time window; one at a time, the nearest first; below a starving base's resupply and above a stocking one; a board truck and a bare `!join logi` take it, the AI garrison does not; the Static's board and CAPTURE jobs are unchanged; the run is deterministic across save and load.

21. Q-TD-121 (NX-484, `tests/core/test_retake.py`): an unclaimed retake job at 0 defense hp is the same job after twice `tasking.expire_min` (no `JobExpired`, no new `JobCreated`), while other generated jobs still expire; a claim starts its CAPTURE clock and a claimed one still expires by it; an unclaimed retake job outlives its node's restored defenses for `tasking.retake_keep_min` (past `expire_min` when longer) and is withdrawn at the first pass at or after it; defenses down again inside the keep continue the same job (no `JobCreated`) with a fresh clock; a keep of 0 withdraws at once and stamps no clock; recapture, a lost road or no truck role withdraw it at once inside the keep; a snapshot mid-keep restores the clock and refuses one in the future or on another coalition job; the run is deterministic across save and load.

22. NX-473 (in code, `tests/core/test_logistics_cadence.py`; §5 LC-1..LC-5; THREAT-DIRECTOR §7 for LC-2).
23. LC-1: no AI truck spawns for a job younger than one period, for a slot any claim holds, past `ai_trucks.max_live` or the EC-8 guard, or with no loadable source.
24. An idle AI truck takes a job before a new one spawns, and a spawn goes to the run's source and claims at spawn.
25. More missing stock gives more trucks in a period.
26. AI trucks spawn at 0 viewers too.
27. `max_live` 0 spawns none.
28. LC-1 viewer priority: a viewer truck displaces an AI claimant from a full job; a bare `!join logi` sees a job full of AI trucks as free; AI trucks never take retake, escort or patrol.
29. AI trucks are invisible to `viewer_units`, add no provocation and are never capturers, so a run through a neutral node starts no bar.
30. Payment: viewers pay before AI trucks (with a test upkeep > 0 the AI truck grounds first), and the spawn draws `loadout_cost` at its node.
31. Lost destination: the truck unloads at the nearest friendly base with room.
32. Retirement: an empty idle AI truck due after `director.idle_retire_s` drives to the nearest friendly base and retires there (at once when it is already at one), a loaded one does not; one with no friendly base to reach stays and is tried again each window (111a).
33. LC-3: at the default the slots are unchanged on both boards; a starving base's cap is base + ⌊need × spread⌋ (the 205-stock example gives 4); a stocking job never rises; the loader refuses max_starving < slots_max.
34. LC-5: two runs and a save/restore mid-run give the same events and hash; stock + cargo + consumed stays exact; the timers freeze with a pause.
35. NX-486 (Q-SIM-130, same file): a truck unloading at a base with room gets no job elsewhere until its cargo is gone and reports the whole stop there (AI truck, and a viewer truck at `max_live` 0); an unloading truck takes the resupply job of the base it stands on, stays put, reports its stop once there and is the DONE job's participant; a loaded truck on a neutral or enemy node with stock room still takes a job elsewhere; the harness's idle reason (`tasking.idle_diagnosis`) follows the same pool; a loaded truck at a full base still takes a job and delivers it; a base another truck fills ends the stop there; a new job reports an open stop at its node first and what each node got matches its report, with stock + cargo + consumed exact; two runs and a restore mid-unload give the same events and hash.
36. NX-492 (Q-SIM-131 (a), same file): at the shipped `expire_min` and `period_s` an unclaimed job gets its AI trucks at the first spawn window after it is one period old (no viewer, `max_live` 3); the unclaimed job keeps its id past 2 × `expire_min` and is withdrawn once its base no longer needs it; its TB-3 aging is capped at `expire_min` while unclaimed (Q-SIM-132), so after an hour a front-line stocking job ranks as it did near 15 min before NX-492: above the retake, below a fresh starving base's job and a DEFEND; a no-viewer shipped campaign run to 28,000 ticks spawns AI trucks that deliver; a claimed coalition resupply job and an old Static resupply job age without a cap, and the board pass (`_assign`) gives a viewer truck the starving job, not the capped one; the Static's resupply job still expires; a cut-off base's job (only through enemy ground) stays posted with one id and gets no AI truck; two runs and a restore past the old expiry give the same events and hash.

37. NX-497 (Q-TD-124, Q-TD-129; in code, `tests/core/test_sanctuary_repair.py`, beside `test_sanctuary_defend.py`; the harness line is open with step 1):

38. **Posting:** a sanctuary below full posts `resupply:<sanctuary>` with or without a contact in range.
39. Urgency is `urgency_max` when besieged or at 0 hp, else 1.0 + the missing share.
40. Slots run 3 to 6 by the share.
41. The job is withdrawn unclaimed at full.

42. **Executor:** an empty viewer truck takes it through the board and through a bare `!join logi` (spawned at the sanctuary).
43. It drives with no reload and parks there.
44. The job is DONE only at full hp, not on arrival.
45. A loaded truck is refused.

46. **AI exclusion:** an AI truck never claims it, in the board pass (a coalition AI truck at haven, and a Static AI convoy at its own rear) or LC-1 (no spawn for it, and no idle AI truck counted against its slots).
47. An AI truck parked there still repairs.
48. A captured sanctuary (`capture.uncapturable_node_kinds` without SANCTUARY) gets no repair job, and a claimed one FAILS once it is captured.

49. **Sides and defeat:** the Static's board never posts it for the coalition sanctuary; the generator posts it for a struck Static rear by parity (EC-3).
50. The defeat run resets only at the NX-499 threshold and pauses below it (in code, NX-499, below).

51. **Determinism:** a repair run (a viewer truck drives to the haven, parks and repairs it to full) gives the same state hash and events twice, and a snapshot taken mid-drive or mid-repair round-trips to the same run.

52. **Harness (open, with step 1):** the step-1 rate sweep (CONFIG-AND-CONTENT §6.5 `capture.sanctuary_repair_hp_per_s`) will report, per rate and seed, haven's lowest hp, the defeats and the trucks destroyed at haven.

53. NX-499 (Q-TD-129 (6), Q-TD-131; in code, NX-499; `tests/core/test_defense.py`, beside the two defeat-run tests, which now pin the share to 0; the loader line in `tests/runtime/test_config.py` and `test_campaign_config.py`):

54. **0 is the old rule:** at `campaign.defeat.reset_hp_frac` 0, `test_a_repair_that_lifts_the_sanctuary_above_zero_resets_the_defeat_hold` and `test_a_repair_during_an_empty_stretch_clears_the_run_and_the_stretch` pass unchanged.
55. A sieged campaign run gives the same events and state hash as the same run before NX-499 (in code as worked old-rule values at share 0 and a property test over hp sequences; no golden case damages haven, so the goldens do not exercise it).

**Pause and resume (0.5, T 500):**

56. A repair to between 1 and 499 hp leaves `defeat_ticks` unchanged and ends nothing.

57. A fall back to 0 resumes the run from the paused value.
58. The defeat comes once the zero ticks add up to `hold_min`.

59. **Reset:** reaching 500 sets the run and the empty stretch to 0, and a later fall below 500 or to 0 starts from 0.
60. A sanctuary damaged from full with no run stays at (0, 0).

61. **Empty stretch:** in the pause band with nobody playing, the stretch counts and resets the run at `hold_min`.
62. A live viewer unit clears it.

63. **Clock:** `running_ticks` counts through a repair pause, and a sim pause freezes the run.

64. **Loader:** it refuses −0.01 and 1.01, and it computes T exactly (0.5 → 500, 0.0001 → 1, 1.0 → 1000, 0 → 1; 0.07 of 800 → 56, the exact decimal).

65. **Determinism:** a run with a pause, a resume and a reset gives the same events and hash twice.
66. A snapshot taken mid-pause round-trips.

67. **Harness (with NX-497 step 1):** a joint sweep of rate × threshold reports, per seed, the defeats, haven's lowest hp and the ticks spent in the pause band.

68. NX-495 (Q-TD-123, Q-TD-132; in code, after NX-500; loader lines in `tests/runtime/test_config.py`, the floor in a new `tests/core/test_starve_floor.py`):

69. **`fraction` is today's rule:** at `logistics.starve_floor_mode` `fraction`, `Supply.starve_floor` equals ⌈`starve_threshold` × maximum⌉ for every node, and every golden case keeps its `event_count` and `events_hash` (only `config_hash` and the checkpoints are re-pinned, as NX-494).

70. **`loadouts`:** N 5 and C 20 give 100 at every strait-1 AIRBASE, HQ and FOB and 0 at both bridges.
71. A node whose maximum is below N × C gets its maximum.
72. Doubling `node_max_stock` leaves the floor unchanged.
73. Raising one coalition kind's `loadout_cost` above C (with `economy.cost_parity` false) raises every node's floor, whoever holds it; lowering one kind that is not the dearest changes nothing.

74. **Readers follow:** in `loadouts` mode a base at 150 stock is not starved (full rearm, no hp drain, no LC-2 demand), a source ships down to 100 on a starving run, and a jet deploys at west-airbase from 150 stock; the Director's surplus at the same stock is the NX-500 figure, unchanged by the mode.

75. **Loader:** refuses an unknown mode and N below 1; N is read only in `loadouts` mode.

76. **Determinism:** a `loadouts` run gives the same events and hash twice, and a snapshot round-trips (the floor is derived from config, so the snapshot format does not change).

77. **Harness:** the report shows Starved against the live floor and against the fraction floor; probe at one sha, a `fraction` control against `loadouts` N 3, 4 and 5, both sides at parity (Q-TD-119), with NX-500 merged.

78. NX-501 (Q-TD-133 (a); in code, after NX-495; loader lines in `tests/runtime/test_config.py`, the target in a new `tests/core/test_stock_target.py`):

79. **`fraction` is today's rule:** at `logistics.stock_target_mode` `fraction`, `Supply.stock_target` equals ⌈`stock_target_frac` × maximum⌉ for every node, M is not read, and every golden case keeps its `event_count` and `events_hash` (only `config_hash` and the checkpoints are re-pinned).

80. **`loadouts`:** with floor `loadouts` N 5 and M 15, C 20, the target is 300 at every strait-1 AIRBASE, HQ and FOB and 0 at both bridges; doubling `node_max_stock` leaves it unchanged; a node whose maximum is below M × C gets its maximum; with floor `fraction` the target is max(300, floor), so 500 at an airbase and 300 at a FOB; raising the dearest kind's cost raises every target (with `economy.cost_parity` false).

81. **Readers follow:** in `loadouts` mode a FOB at 290 posts a stocking `resupply:<node>` job and one at 300 does not (with no starvation or damage); a stocking run to it loads only up to 300; a staging base still gets the FS-3 raise above its target.

82. **Loader:** refuses an unknown mode and M below 1; M is read only in `loadouts` mode.

83. **Determinism:** a `loadouts` run gives the same events and hash twice, and a snapshot round-trips (the target is derived from config, so the snapshot format does not change).

84. **Harness:** the report prints the hauling line (resupply jobs and truck deliveries per run-hour, per side; no stocking/starving split) on a scripted run with a known count (`tests/tools/test_balance_harness.py`).

85. NX-466 (Q-TD-84 (b), Q-TD-134; ECONOMY EC-9b; in code).
86. The rule goes in a new `tests/core/test_hold_pause.py`, beside `test_victory_hold.py` and `test_hold_decay.py`.
87. The loader line goes in `tests/runtime/test_config.py`, and the switch joins `tests/core/test_rule_options.py`.
88. Worlds are strait-1 through the shipped config, with the coalition set to own 7 of the 8 strategic nodes so that a hold runs, and the key flipped through the config, not a hand-built `Rules` (add-config-key §2.6):

**Pause and resume, one test per condition:**

89. `CAPTURE_BAR`: an ENEMY bar on a hold node pauses the hold on the next running tick.
90. `hold_ticks` stays flat while the bar lives, and the hold resumes on the first tick after the bar drains to 0, with `ends_at_tick` later by exactly the paused running ticks.
91. A night-held bar (`DirectorState.held`) and a bar frozen by the idle floor on `forward_airbase` with 0 viewer units also pause it.

92. `DEFENSES_DOWN`: a hit that takes a hold node to 0 hp pauses the hold.
93. A rebuild to 1 hp does not resume it; a rebuild to full (`NodeDefensesRestored`) does.
94. A node the coalition has just captured (0 hp, never down) does not pause the hold.
95. A starvation drain to 0 does pause it.

96. `CAPTURE_OP`: an ENEMY unit claiming an `op:OFFENSIVE:<n>:2` CAPTURE job pauses the hold at `defend_radius_m` and not 1 m outside it.
97. It counts while its STRIKE step is still open (TB-8).
98. The pause ends when the claimant leaves the radius, is Disabled (claim released), or is lost.
99. A claimant of the same operation's STRIKE job inside the radius does not pause the hold, and neither does a staged operation.
100. Parity: the hold is coalition-only in code (`campaign.py` uses `_COALITION`), so parity is tested on the pressure check itself.
101. It takes the holder as an argument and gives the mirrored answer for an ENEMY-held node: a COALITION bar on it, the node down, or a coalition `retake:<n>` claimant in the radius.
102. (Its name and signature are the coder's choice.)

103. **Events:** one `VictoryHoldPaused` per pause, naming the lowest-id pressured node and the first condition in the order CAPTURE_BAR, DEFENSES_DOWN, CAPTURE_OP.
104. Two conditions on two nodes give one event, and a change of node or reason mid-pause gives none.
105. Each pause gets one `VictoryHoldResumed`, with `ends_at_tick` = running ticks + `victory_hold_ticks` − `progress_ticks`.
106. `hold_paused_ticks` is 1 on the pause tick and 0 again on the resume tick.

107. **Start tick:** a hold that starts or resumes from decay under pressure gains 1 on its `VictoryHoldStarted` tick, unchanged from today, and pauses from the next tick on.

108. **No victory while paused:** with `hold_ticks` at `victory_hold_ticks` − 1 and a node pressured, no `CampaignEnded` comes for any number of paused ticks.
109. The first unpressured tick emits `VictoryHoldResumed` and then `CampaignEnded{VICTORY}` on the same tick.
110. An HQ capture during a pause still wins at once.

111. **With EC-9a:** a paused hold neither gains nor decays (`hold_broken_ticks` stays 0).
112. A bar that flips a node during the pause breaks the hold: `VictoryHoldBroken.progress_ticks` is the paused P, no `VictoryHoldResumed` is emitted, `hold_paused_ticks` is 0, and the decay starts from the slow stage.
113. With `hold_break: reset` the break gives P 0.
114. A hold re-held after that starts unpaused.

115. **Director view:** a paused hold's nodes stay in `SideView.hold`, so a capture operation launched on one during the pause still emits `HOLD_AT_RISK`, gets `victory_hold_mult` and skips staging (FS-10).

116. **Clock:** a sim pause during a hold pause emits nothing and leaves `hold_paused_ticks` unchanged.
117. The resume comes on the first running tick with no pressure.
118. `running_ticks`, the time limit and the objective timers run through a hold pause.

119. **Switch off is today:** with `campaign.victory.pause_on_pressure` false, a scripted run with all three conditions on hold nodes gives the same events, tick for tick, as the same run before NX-466 (`hold_ticks` grows by 1 per running tick, and no pause event).
120. `hold_paused_ticks` stays 0.

121. **Loader:** the key is required, a bool, and refused if missing.
122. The schema carries all eight annotations (`make contracts`).

123. **Determinism:** a run with a pause, a resume, a break during a pause and a re-hold gives the same events and state hash twice.
124. A snapshot taken mid-pause round-trips to the same run.
125. A snapshot with `hold_paused_ticks` > 0 and no running hold is refused (`_bad_hold`).
126. An older snapshot format is refused.
127. The switch joins the default, non-default and every-option-flipped runs in `test_rule_options.py`.

128. **Harness:** `tools/balance/metrics.py` adds per profile:

129. holds paused: holds with at least one `VictoryHoldPaused`;

130. pauses, by reason;

131. paused minutes: running ticks with `Campaign.hold_paused_ticks` > 0, counted in `observe`, because a pause ended by a break has no `VictoryHoldResumed`;

132. paused minutes per hold in the `holds` list.

133. The report (`report.md` and `report.json`) prints them next to holds broken.
134. A scripted run with a known pause count checks the line in `tests/tools/test_balance_harness.py`.
135. The first raid-300 and prime-50 run after merge reports them against the E0 baseline (`docs/review/HARNESS-E0-E2-2026-10-30.md`: raid-300 14 holds, 8 broken; prime-50 0 holds).

136. NX-471 (Q-TD-78 (a), Q-TD-135; §8 "Facilities at a captured base"; in code).
137. The rule is in a new `tests/core/test_seized_facilities.py`, beside `test_capture.py`.
138. The loader lines go in `tests/runtime/test_config.py`, and the switch joins `tests/core/test_rule_options.py`.
139. Worlds are strait-1 through the shipped config, with the keys flipped through the config, not a hand-built `Rules` (add-config-key §2.6).
140. A capture is forced as the existing capture tests force one (a bar at one step short of full, defenses at 0).

**The flip disables:**

141. A coalition capture of `fob-n-e` with `ad-fob-n-e` HEALTHY at 150 hp leaves the site COALITION, at 14 hp, DISABLED, with `seized_carry` 0 and both repair carries 0, in the flip tick.
142. The events come in this order: `NodeCaptured`, then `UnitDamageStateChanged{HEALTHY → DISABLED}`.

143. A site already DISABLED at 30 hp (struck, not yet back) drops to 14 with no state event.

144. With `combat.facility_indestructible` false, a site at 10 hp (below the floor) keeps 10.

145. At `east-airbase`, `radar-east` and `ad-east` are both seized, with their events in id order.

146. A NEUTRAL base flip (`cross-n`, no facilities, Q-GP-36) emits nothing more than today.

147. Property: the flip never raises a facility's hp, and a seized facility's hp stays below its restore line while seized.

**Disabled does nothing:**

148. Through the whole slow repair, the seized SAM site fires at no enemy jet inside its range.
149. The same site fires on the first tick after it is back on line.

150. A seized radar adds no FoW coverage and no SIGINT blob for its new owner.
151. It does both again once back on line.

152. A shot in flight at the site at the flip fizzles with no `combat` draw (the stream position is unchanged).

153. The loser's marker of the site has state DISABLED.
154. The loser's `crosses_ring` through its ring is false and `ring_blocker` is null, both for the coalition board and for the Director's TD-2 check (`ring_crossed`).

155. With the switch off, the same capture gives the loser a live marker and the ring refuses its jobs, which is today's lockout (Q-TD-78).

**Repair with supply (S 92, shipped repair rates):**

156. At an airbase with stock, the site reaches 53 hp and leaves DISABLED after exactly 5,980 ticks, and `seized_carry` is null from that tick.
157. It reaches 150 hp with `UnitRepaired` 162 ticks later.

158. At a FOB the same takes 11,960 and then 324 ticks.

159. At S 1 the times equal the switch-off times (65 ticks to the restore line at an airbase).

160. The stock debited is 3.9 units to the line and 13.6 to full.
161. Stock + consumed stays exact, and `SupplyConsumed{REPAIR}` matches the units drawn.

**No supply, no repair:**

162. At a seized FOB with 0 stock, hp, `repair_milli` and `seized_carry` stay unchanged for 1,000 ticks, with one `RearmStalled`.

163. A delivery restarts the repair from where it stood, with no carry lost.

164. A capture bar on the base pauses the repair (no carry moves) until the bar drains.

**Retaken mid-repair:**

165. With the site at 40 hp under its captor, the loser retakes the base.
166. The site is back on its old side at 14 hp, still DISABLED, with no state event and `seized_carry` 0, and it repairs again at the slow rate.

167. A third flip does the same.

168. **Parity:** in a mirrored setup, a coalition capture of a Static FOB and a Static capture of a coalition FOB give the same hp, state, carries, tick counts and events (side fields swapped).
169. No provocation is noted at the flip beyond `base_captured`.

**Switch off is today:**

170. With `capture.facilities_disabled` false, a capture of `fob-n-e` keeps the site's hp and state.
171. A HEALTHY SAM site fires for its new owner on the next tick, and `seized_carry` stays null.

172. A scripted capture-and-retake run gives the same events, tick for tick, as the same run before NX-471.

173. **Loader:** both keys are required.
174. The switch must be a bool.
175. S must be an integer ≥ 1; the loader refuses 0, −1 and 1.5.
176. The schema carries all eight annotations (`make contracts`).

**Determinism:**

177. A seize, repair, retake and back-on-line run gives the same events and state hash twice.

178. A snapshot taken mid-slow-repair round-trips to the same run.

179. Restore refuses `seized_carry` on a non-facility, on a facility that is not DISABLED, at S or above, below 0, or with the switch off.

180. An older snapshot format is refused.

181. The switch joins the default, non-default and every-option-flipped runs in `test_rule_options.py`.

182. **Harness:** `tools/balance/metrics.py` adds per profile and per side:

183. captured facilities disabled: facilities seized at a flip, counted at `NodeCaptured` from world state (`seized_carry` not null);

184. minutes until back on line: game minutes from the seizure to the facility's `UnitDamageStateChanged` out of DISABLED, as median and max.
185. A site retaken before it is back counts as not repaired, and its new seizure starts a new clock;

186. still off at run end.

187. The report (`report.md` and `report.json`) prints them next to `ring_by_site` (NX-462), so a probe shows whether the captured-SAM lockout is gone.
188. A scripted run with a known count checks the line in `tests/tools/test_balance_harness.py`.
189. The first raid-300 run after merge reports them, with the hauling line (NX-501), against the last baseline, because seized facilities keep their base's resupply job open (§8 "Resupply side effects").

190. Q-GP-23: `!join strike` with no parameters claims a job on the spawn tick; `!join strike <node>` does not auto-task until that order completes.

191. Q-ALN-33: an enemy combat-capable unit at a node being captured freezes progress; a parked air unit or a Disabled unit there only slows it.

192. NX-490 (Q-TD-127; `tests/core/test_hq_capture.py`, harness line `tests/tools/test_balance_harness.py`): at the shipped values (no defender, quiet 1.0) a lone capturer flips an HQ in 2000 ticks and a FOB in 100; 4, 10 and 20 capturers flip the HQ in 500, 200 and 100 ticks; with every kind at `time_mult` 1.0 and `extra_exponent` 0 every capture time and the replay goldens are unchanged; the HQ keys apply alike to a coalition and an ENEMY capturer (a strait-1 world whose `Rules.node_kind` makes a coalition FOB an HQ: the theater loader allows one HQ, the Static's); `min_time_s` still caps a crowd at an HQ; a logistics capturer (weight 0.5) alone takes 2 × the lone time; the loader refuses a missing kind, a `time_mult` of 0 or less and an `extra_exponent` below 0; the run is deterministic across save and load.
193. Harness: a raid campaign batch reports every HQ capture with its participant count (`NodeCaptured.participant_commander_ids`), and capture weight (in code, NX-490); the check that a 1-commander HQ capture is rarer than in T0/T1 (2 of 2 there) waits on the HQ value sweep (open in the NX-490 tracker row).

Notes: GAMEPLAY-NOTES.md §11

## 12. Open questions
1. Every Q-row this section listed is decided and folded in; the list is in GAMEPLAY-NOTES.md §12.

Notes: GAMEPLAY-NOTES.md §12
