# SPEC: Gameplay Rules


> **All numeric values in this spec are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). They become real only after the balance harness validates them.
Status: Draft · Tracker: NX-120…NX-149 · Inputs: Raw plans P206–225, P983–1009, P1139–1168; conversation C1–C48

All numbers below are **initial balance values** in `balance/default.yaml`. They're tuned with the balance harness, not hard-coded.

**Timers (Q-CFG-8, Q-ALN-1, Q-ALN-4, Q-ALN-6, Q-ALN-23):** every duration in this spec runs on one of three clocks and is labeled with it:
- **World time** (in the sim): ticks scaled by `sim.time_scale`. It drives movement, logistics and combat (§5, §6), capture progress and decay (§8), bridge repair (§5), and the fog-of-war refresh and track fade (FOG-OF-WAR).
- **Game time** (in the sim): unscaled ticks, so 1 game minute = 1 real minute while the sim runs. It drives player-facing durations: Tasking Board claim lease and priority aging (TB-1, TB-3), idle handoff/retire (§4b), respawn delay (§4, Q-ALN-5), ability and command cooldowns, package fill wait (§7), objective period and victory/defeat hold (§9), campaign length, and the director's window, dwell, decay and Pattern of Life timers (THREAT-DIRECTOR TD-1).
- **Real time** (outside the sim): a monotonic clock for chat rate limits and digest batching (CHAT-GATEWAY), and the taunt, GM auto-release, redemption and supply-drop limits (Q-ALN-4, THREAT-DIRECTOR, SUPPORT-REDEMPTIONS). These are enforced before anything enters the sim.

World and game time are both deterministic and both freeze while the sim is paused; real time does not. Config keys use friendly units (s/min) and are converted to ticks at load, rounding **up** so a timer is never shorter than configured (Q-ALN-6).

**Pause (Q-ALN-2):** a pause freezes the whole world: movement, combat and every sim timer on both clocks. Commands that don't change the world still work while paused: `!me`/`!status`, `!quiet`, and joining the reserve queue (a `!join` while paused always queues, even when a slot is free, Q-ALN-26). Every other command gets a "war paused" reply in the digest (FB-UX-5) and has no effect (STATE-MACHINES §4.4). Staff safety actions always work while paused (ban, forget, kill switch, pause/resume/end); a config reload waits until resume, and director overrides are rejected (Q-ALN-24). Unban, unit purges and approved callsign changes also apply; advisor choices and GM commands other than a GM release are rejected, and channel-points redemptions are refused and refunded (Q-ALN-36, Q-ALN-37).

**First-build scope (Q-PROD-8):** the first build ships the core loop, damage states (§6a), base defense HP (§8), limited munitions (§5), fog of war, director tiers with Pattern of Life, and the Tasking Board (§1b). Stances (`!stance` and deploy-time stance), CSAR and crew rescue (`!rescue`), packages, carry-over, world events, base upgrades and weather come later behind feature flags; their rules are in [GAMEPLAY-LATER](GAMEPLAY-LATER.md) (Q-GP-1). With stances off, every unit behaves as `standard`.

## 1. Core loop (what a viewer does in 30 s)
1. Type `!join strike|recon|logi`. Within 500 ms (server side) a radar ping and their callsign appear at a base.
2. With no parameters, the unit takes the best open job from the **Tasking Board** (§1b) at once; with a node it goes there; with `hold` it waits at base (Q-GP-23). Assisting the current objective is one of those jobs, not an automatic route.
3. Optionally type `!target <node>`, `!rebase <node>` or `!rtb`.
4. The unit completes or fails its mission, and the viewer sees a contribution line in the ticker.

## 0. Parity rule (owner, 2026-10-17)
**Both sides play by the same rules.** The Static has the same mechanics as the Quorum: scouting, fog of war (FOW-4), supply and starvation, rebasing, damage states, ammo, and rescue/recovery where it applies. Any new mechanic must say how it applies to both sides, or explicitly justify an asymmetry (e.g. the sanctuary base) in its spec.
- **Asymmetry, idle floor (Q-GP-44):** only the coalition's last airbase is protected while no humans play; the Static has no such floor because players are always present when it is attacked.
- **Asymmetry, AI escorts (Q-GP-45):** the Static's director escorts its convoys through threat memory, while the coalition AI garrison never escorts: escorting coalition convoys is the players' decision, so unescorted convoys are a real risk the Static can punish.
- **Asymmetry, emission control (Q-FOW-13):** only the Static's director can turn its sites dark in the first build (a deception tool); coalition parity arrives with SEAD (FOG-OF-WAR FOW-11).
- **Asymmetry, quiet-stream capture (Q-SIM-26):** the `quiet_mult` easing in §8 applies to the coalition only. Applying it to the Static would make a quiet stream easier for the enemy as well, which defeats its purpose. It is a pacing aid for small crowds, not a rule of the fiction.
- **Static economy (Q-GD-30):** the director's budget is the Static's real stock, shipped by convoy from its rear source (factories are parked, Q-GP-41), which the coalition can raid and starve. Its infinite rear source sits behind its capturable HQ (the coalition's sanctuary can never be captured, §9).
- **Static tasking (Q-GD-34):** the Static uses the same Tasking Board (§1b). The director is the strategic layer that creates jobs on the Static's board (stage, escort, strike, defend, reposition), with the same job types and mechanics as the Quorum. It may compose richer job combinations but gets no unique powers.
- **Lieutenants (Q-GD-38, P4, NX-317):** later, sectors may be run by Static lieutenants, each a Threat Director profile on the same mechanics. Not in scope before P4.

## 1a. "Did my command work?" feedback (owner requirement, Q-MOD-1)
Viewers see a generated callsign, not their username, so the game must connect "me" to "my unit" unmistakably. Otherwise they assume nothing happened and leave.
- **FB-UX-1 Chat confirmation:** the bot's batched digest names the platform user and their callsign, e.g. "@SaltyUser → VIPER-27 deployed (strike) from WEST BASE". It's sent within platform rate limits (Twitch as a moderator: 100 messages / 30 s, per PLATFORM-REALITY-CHECK), with up to N mentions per digest message (N PROPOSED).
- **FB-UX-2 On-screen recruit strip:** for 10 s after each spawn, a "NEW RECRUITS" strip shows the callsign, platform icon and role, with a ping on the map at the spawn point.
- **FB-UX-3 `!me`:** highlights your unit for 5 s, and the next chat digest repeats your callsign and status. Also works while you're in the reserve queue (shows your position). `!status` is a pure alias with identical behavior (Q-UX-12).
- **FB-UX-4 First-time hint:** a commander's first successful command adds a one-time "New? You're VIPER-27. Type !me anytime." line to the digest.
- **FB-UX-5 Rejections are visible too.** Reasons like "unit in sortie" or "respawn in 12 s" are batched into the digest with the callsign, never silently dropped.
- **FB-UX-6 Measure it:** track the share of first-time commanders who issue a second command (NX-036). A low value means the feedback isn't working.

## 1b. Tasking Board (owner decision 2026-10-17, Q-GD-26)
A shared queue of **jobs** the system generates from the live situation, so every unit, human or AI, always has something useful to do:
- **Job types (first build, Q-GP-5; rescue a downed crew joins with CSAR, GAMEPLAY-LATER §6a):** resupply a starving base, scout a sector or blob, escort a convoy, defend a threatened node, strike a target, repair a bridge, assist the current objective. Damaged facilities raise the urgency of a resupply job to their base, since facilities repair from base stock (Q-GP-47).
- **Each job has:** a priority (Q-GP-20: `tasking.priority.<job_kind>` × an urgency multiplier of 1.0–2.0 from the triggering condition, such as the node's supply level, the threat or danger near it, or the objective flag, plus linear aging, TB-3; refined in playtests), the role(s) that fit, a **slot count** (how many units it needs), and an expiry.
- **Assignment:** a unit with no explicit order takes the highest-priority open job matching its role. Slots prevent pile-ups: a job is skipped once its slots are full, unless *every* job is full.
- **AI garrison** pulls from the same board, but only takes jobs no human has claimed, and releases them when an operator wants one. **The AI garrison never initiates offense**: it takes defend, resupply (which also repairs facilities, Q-GP-47), scout and repair bridge jobs (rescue jobs join with CSAR, GAMEPLAY-LATER §6a), never escort jobs (Q-GP-45: escorting is the players' call), and joins strike jobs only when a player started them (objective; later also a rally call or player-led flight). **Sole exception (Q-GD-31):** it may counterattack a node the coalition just lost, within a configurable window (PROPOSED ~15 min), using only units still able to fight (not Disabled or Destroyed).
- **Feasibility:** a unit only takes a job it can reach and complete with its current fuel and munitions. Otherwise it first takes a rearm/refuel step (nearest base with stock, Q-GD-17).
- **Logistics routing (Q-GP-24):** a supply job sets the *destination*; the route is planned automatically along roads/sea lanes. `!join logi` with no parameters takes the best resupply job. `!join logi <friendly node>` makes that node the delivery destination. `!join logi <neutral or enemy node>` is a capture run with no cargo. **Source:** the nearest reachable friendly base whose stock is above its own starvation threshold, with the sanctuary as last resort, so a truck never strips a base into starvation; cargo = min(capacity, that base's surplus). En route, `!target <friendly node>` changes the destination with the cargo aboard, and `!rtb` unloads at the nearest friendly base, so nothing is lost. Choosing the source (`!join logi <from> <to>`) is parked.
- **Follow, escort and lead (Q-GP-31):** a friendly unit's callsign is accepted wherever a node is (`!join strike VIPER-27`, `!target VIPER-27`). Your unit follows and escorts that unit: it keeps station, engages what threatens it, and re-tasks when the followed unit dies or despawns (when it lands, followers land with it and keep following). **Station by domain (Q-GP-32):** a ground combat unit following a truck or convoy moves ahead on the same road (`tasking.follow_station_m.<domain>`); an aircraft following a ground unit flies overwatch and engages air threats and detected air-defense sites on the route; a truck following a truck falls in behind as a convoy column that keeps station on its leader, and an escort job for the lead truck covers the column; an aircraft following an aircraft flies as wingman. If the followed unit stops, followers hold station; if it reaches a base, they land or park there. **Followers still do their own role's work:** a truck in a column loads at a source by the §1b source rule and unloads at the column's destination, a striker still engages, and a recon unit still scans. Following sets station and route, never replaces the role. **Chains (Q-GP-33):** a follower may itself be followed; each unit keeps station on its direct leader, so repeated follows build a column. Following yourself, or a follow that would close a loop, is rejected with `FOLLOW_TARGET_INVALID`. When a leader in the middle of a chain leaves, its followers re-attach to that leader's own leader, or re-task if there is none. Column length has no cap. Leading needs no command: anyone can follow you, and the overlay shows "VIPER-27 + 2 following". Only same-side units can be followed (AUTO units included). **Follower credit (Q-GP-42):** credit follows outcomes, not jobs: whatever the leader achieves, on a job or a free order (a delivery, a capture, a kill, a facility disabled), followers within station range share a capped portion of that outcome's merit (`progression.follower_share`, `progression.follower_share_cap`, PROPOSED). Coordinated free play counts; a follower far out of station gets nothing. Packages (shared target, XP share, NPC fill, a lead rank) stay in GAMEPLAY-LATER §7.
- **Escort jobs (Q-GP-29, Q-GP-47):** when a truck's route passes within a detected threat (an air-defense ring seen by a sensor, or a currently tracked enemy; last-known tracks and unseen emitters do not count), the board posts an `escort convoy` job for players' strike and recon units. Taking it is just a follow order on that truck (station by domain, below), and it expires when the truck arrives. The coalition AI garrison never takes it (Q-GP-45).
- **Logistics conduct (Q-GP-24, Q-GP-47):** merit counts only delivered cargo and completed captures (PROGRESSION). Until the conduct system (NX-291) defines detectors, staff see plain per-commander logistics stats in the Command Center (runs started, delivered, abandoned; cargo returned) and judge patterns themselves; nothing is punished automatically.
- **Visible:** the overlay shows the top few open jobs ("NEEDED: supply to WEST FOB") so lurkers learn what matters, in the rotating HUD panel at double frequency (Q-UX-11, OVERLAY).
- **Free movement and auto-tasking (Q-GP-19, Q-GP-23):** a player can always send their unit wherever they choose. Auto-tasking happens only when the command has no parameters: `!join <role>` takes the best matching job at once, with no hold at base. `!join <role> <node>` goes straight to that node and does not auto-task until that order completes. `!join <role> hold` waits at base until given an order. A player can redirect the unit en route with `!target`, `!rebase` or `!rtb`, within the command rate limit (CHAT-GATEWAY). Any explicit order suspends auto-tasking until it completes. There is no decision window.

**Robustness (Q-GD-37).** These apply to both sides' boards:
- **TB-1 Lifecycle:** a job moves OPEN → CLAIMED → ACTIVE → DONE | FAILED | EXPIRED. A claim is a **lease** (`tasking.claim_lease_s`, game time, Q-ALN-23): if the claiming unit makes no progress within the lease, the claim is released and the job returns to OPEN.
- **TB-2 Feasibility pre-check:** before claiming, a unit checks fuel, munitions, a route, and known threats on that route.
- **TB-3 Priority aging:** an open job's priority rises the longer it waits (per game-time minute, Q-ALN-23), so low-priority jobs are never starved.
- **TB-4 Slots and dedupe:** every job carries a slot count and a dedupe key. Generating a job whose key matches an open job updates that job instead of adding a second one.
- **TB-5 Deterministic assignment:** units are assigned in a stable sort order with a seeded tie-break drawn from the dedicated `tasking` RNG sub-stream, which no other system shares (Q-ALN-7), so a replay reproduces every assignment (SIM-CORE).
- **TB-6 Cadence:** the board is re-evaluated every N ticks (configurable, PROPOSED), not every tick.
- **TB-7 Preemption:** a human order always wins over a board job. Emergency preemption of AI-run units is deferred (Q-GP-5).
- **TB-8 Dependencies:** a job may depend on another (e.g. repair bridge, then convoy) and can't be claimed until that job is DONE.
- **TB-9 Per-side fog of war:** each side builds its board only from its own fog-of-war view (FOW-4).
- **TB-10 Logged outcomes:** every job's lifecycle and outcome is emitted as sim events and **stored durably** (Q-ALN-16), for recap stats (e.g. "most supply delivered"; "most rescues" joins with CSAR), AAR stats and balance analysis. A job completed by a commander's AUTO unit is recorded as an **AUTO assist** for recaps only; it never counts toward XP, merit or leaderboards (Q-ALN-30, PROGRESSION). The same holds for every other action by an AUTO unit, such as a kill, a supply delivery or capture participation (Q-ALN-34, PROGRESSION PROG-12).
- **TB-11 Command Center:** both boards are visible in the Command Center. A GM can inject jobs into the **Static's board only** (Q-ALN-11, GM scope §9c); a GM never injects jobs into the Quorum's board.

## 2. Roles (MVP, resolves critique #7 and #8)
| Role | Command | Domain | Does | Can't |
|---|---|---|---|---|
| Strike | `!join strike` | AIR | Attacks ground/air targets; suppresses SAMs poorly without SEAD | Capture nodes |
| Recon | `!join recon` | AIR | Large sensor radius; converts SIGINT blobs to tracks; paints targets | Deal damage |
| Logistics | `!join logi` | GROUND | Carries supply along roads to nodes; captures uncontested nodes slowly | Fight |
| Naval | `!join navy` | SEA | **P3** (Q-GD-8: sea domain moved earlier because maps are water-heavy) | — |

Specialist chassis (SEAD, jammer, engineer, AWACS, artillery) unlock with rank (PROGRESSION). **Specialist doctrines** are chosen once per campaign and lock (Q-GD-3).

**Display names (Q-NAME-2, working names; final list in the brand guide NX-274):** roles and unit kinds keep plain ids in code and contracts (TS-4), but the stream shows friendly class names: Striker (multirole jet, `STRIKE`), Scout (recon drone, `RECON`), Hauler (supply truck, `LOGI`), Tank, Gunboat, Tanker (refueler), Lifter (rescue helo), Sentinel (anti-air site), Spire (radar). No real-world platform names (Q-PROD-5).

## 3. Commands that enter the sim (Q-GP-2)
Rank ids `O-1`…`O-6` are **internal ids** used in config and contracts. On stream and in replies they show as themed display names (Q-NAME-1, PROGRESSION §3).

| Command | Args | Min rank | Notes |
|---|---|---|---|
| `!join <role> [<node>\|<callsign>\|hold]` | role, then an optional node, a friendly unit's callsign, or `hold` | O-1 | Spawns your one unit, or switches role if your unit is at base. `hold` opts out of Tasking Board auto-tasking (§1b) |
| `!target <node\|callsign>` | node name/alias (fuzzy match against a fixed list) or a friendly unit's callsign | O-1 | Sets your unit's objective, or follows that unit (Q-GP-31) |
| `!rtb` | — | O-1 | Return to the nearest friendly base |
| `!rebase <node>` | friendly node | O-1 | Move your unit to another friendly base and stay there to refuel/rearm/stage (e.g. move a plane forward before an attack). Uses that base's stock. The Static does the same (THREAT-DIRECTOR §5a). |
| `!me` (alias `!status`, set in config) | — | O-1 | Highlights your unit for 5 s; the next digest repeats your callsign, status, remaining cooldowns, queue position and your own conduct standing / active restriction (FB-UX-3, Q-MOD-5) |
| `!callsign <NAME>` | `^[A-Z][A-Z0-9-]{2,11}$`, moderated, never equal to a node name or alias (Q-GP-31), 1 change / 30 days | First completed mission (Q-PROG-3) | Reserve a global callsign |

Commands the gateway handles alone (`!help`, `!guide`, `!rules`, `!link`, `!quiet`, `!forget`) are in CHAT-GATEWAY §9. Later-phase commands (`!stance`, `!rally`, `!rescue`, `!vector`, specialist spawns, `!package`, `!wingman`, `!doctrine`, `!order`) are in GAMEPLAY-LATER §3. Unknown commands and ordinary chat are ignored. Command aliases are configurable.

## 4. Unit slots
- **GP-1** Each commander has at most **one live personal unit**, and an AI-run (AUTO) unit still counts as it (GP-6, Q-ALN-9). `!join` while your unit is alive retargets or switches it only if it's at a base. Otherwise you get the reply "unit in sortie".
- **GP-2** After death, respawn is allowed after `slots.respawn_delay_s` (PROPOSED 20 s, game time, Q-ALN-5) to stop suicide spam. The delay grows with repeated losses in a short window, and a rescued crew removes part of it (Q-CBT-9). Losing a unit never costs XP; deliberate disruption is handled by the conduct system (ADMIN-RBAC §6.8).
- **GP-7 Spawning never hurts (Q-GP-41):** joining is always free. A unit spawns at the friendly base nearest its target or job whose stock exceeds its starvation threshold by `logistics.forward_deploy_min_surplus`, and pays its loadout from that surplus (**forward deploy**). If no base qualifies it spawns at the sanctuary, whose stock is infinite, and travels forward. A logistics unit spawns at its source base (§1b). Spawning never takes a base below its starvation threshold. When a delivery lets a base forward-deploy again, the ticker credits it ("HAULER-12's delivery: WEST FOB can forward-deploy again"); a starving base shows "units spawn at sanctuary".
- **GP-3** Above `slots.max_viewer_units` (Q-GD-6) new joiners go to a visible reserve queue. The queue is served FIFO as slots free up.

## 4a. Reserve-queue mitigations (Q-GD-6 decided with mitigations)
- **RQ-1:** show the queue length on the HUD. Each queued viewer gets their position (Q-SIM-12): a reply on `JOIN` ("queued, position N of M"), an update only when the position crosses a milestone (top 10, top 3, next; PROPOSED milestones), and "you're in" when served. `!me`/`!status` can ask at any time. The Field Manual, `!help` and the `JOIN` reply must tell viewers this is how the queue works. A queued viewer leaves the queue after `slots.queue_idle_min` (15, real time, Q-SIM-12) without any chat message, so a departed viewer does not hold a slot.
- **RQ-2: Dynamic cap.** `slots.max_viewer_units` is a ceiling. The runtime may lower the effective cap while tick time is over budget, and raises it back when there's headroom (logged, visible on the ops dashboard).
- **RQ-3 (P4):** flights and wingmen moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §4a. The alpha uses the plain reserve queue.
- **RQ-4, RQ-5 (moved, Q-GP-9):** queued `!scout` pings, participation merit, the first-timer boost and the max-wait guarantee are in [GAMEPLAY-LATER](GAMEPLAY-LATER.md) under "Moved from the first-build review". The queue is plain FIFO; a silent commander's unit frees its slot only when it retires (GP-5), and a handed-off AUTO unit (GP-4) still occupies it (Q-ALN-8, Q-ALN-9). There is no other idle despawn.

## 4b. Silent viewers (Q-GD-35, Q-ALN-8)
Chat gives no presence signal, so silence is measured as time since the commander's last command that reached the sim (game time, Q-CFG-8, Q-ALN-1). Info commands, `!quiet` and `!callsign` are handled outside the sim and do not reset the timers (Q-ALN-26). These two timers are the only idle rule; the earlier fixed idle despawn is removed (Q-ALN-8).
- **GP-4 Idle handoff:** after `presence.idle_handoff_min` (PROPOSED default 10, game time) with no command from its commander, the unit finishes its current order and joins the Tasking Board as an AI-run unit. The overlay tags it **AUTO** from the handoff tick, and the current order is kept (Q-ALN-26). The AUTO unit keeps occupying its commander's slot (GP-1, GP-3) until it retires (Q-ALN-9). A unit that joined with `hold` gets the same handoff and keeps holding until it claims a job (Q-ALN-25).
- **GP-5 Idle retire:** after `presence.idle_retire_min` (PROPOSED default 30, game time) with no command, the unit RTBs and despawns. Cargo it carries is unloaded at the base it RTBs to. Only then is the slot freed. A **Disabled** unit can't RTB: it despawns in place and its cargo is lost (Q-ALN-25).
- **GP-6 Reclaim:** any command from the commander while the unit is alive restores their control of **that** unit and clears the AUTO tag; a `!join` reclaims the AUTO unit instead of spawning a second one (Q-ALN-9).
- Both timers are admin-configurable in the Command Center.

## 5. Logistics (resolves critique #13)
- Nodes hold `stock` (0..max). Spawning or rearming at a node consumes stock according to the unit's loadout cost.
- **Sources (Q-GP-41):** in the first build stock comes only from each side's source, shipped in by truck: the coalition's SANCTUARY (infinite, far away) and the Static's rear source behind its HQ. Factories are parked in GAMEPLAY-LATER until playtests show single-source convoys are too slow.
- **Starvation:** below `logistics.starve_threshold` (PROPOSED 25%) units spawn with reduced loadouts (50% fuel, guns only, with the gun round count also drawn from stock). At 0, the node can't rearm.
- **Munitions per sortie (Q-CBT-7):** every unit leaves with a limited load drawn from base stock. **Guns are limited too** (high round count); rounds used are charged to base stock on resupply. Out of missiles/bombs → auto-RTB unless stance `press` or `guns` (§6 Stance; the first build runs every unit as `standard`, and `!stance` is in GAMEPLAY-LATER §3). **Unlimited ammo** is a campaign/test option (testing, special events) set at campaign setup by the owner or an Admin only, never by a GM and never live mid-war (Q-ALN-10).
- **Repairs (Q-GD-27):** repair happens at a friendly base with stock, for **all domains** (aircraft at airbases, ground vehicles at bases/depots, ships at ports). It costs time and stock and is faster at bigger or upgraded bases. Engineers field-repair disabled vehicles. Same rules for the Static (parity).
- **Supply moves only on trucks (Q-GP-16):** stock moves between nodes only as `cargo` on logistics trucks, which load at a source node, drive the road graph and unload at the destination. There is no passive trickle along connected roads. **One exception (Q-GP-40):** a supply drop (redemption or GM world event) is an air delivery that can be intercepted and lands as stock at its target base. The AI garrison takes `resupply` jobs (§1b), so a 0-viewer war runs a slow convoy cadence instead of starving.
- Logi trucks carry `cargo`, drive the road graph (A* over ROAD edges, cost = length / speed_mult), and unload over time at the destination.
- **Bridges** are nodes with HP. A destroyed bridge removes its edge until it is repaired (Q-GD-11): **logistics trucks** can do a slow field repair (`logistics.bridge_repair_time_s` × `logistics.truck_bridge_repair_mult`), and **engineers** repair fast (building new crossings moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) under "Moved from the first-build review", Q-GP-9).
- Units heal and rearm **only while landed or parked at a friendly node**, by spending stock. They never heal passively (fixes the immortality bug).
- **Empty bases stay bases** (Q-GD-17): at 0 stock, units can still land, garrison and wait there for a resupply convoy. They get no fuel or ammo, but keep what they have and can take off again with reduced endurance.

## 5a. Base upgrades (P4)
Moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §5a.

## 5b. Facilities (Q-GP-21, Q-GP-25)
- **Bases** (AIRBASE, FOB, PORT, HQ, SANCTUARY) are where you spawn, rearm and repair; every base except the sanctuary can be captured. **Facilities** are attached to a base: radar sites and air-defense sites in the first build (factories are parked, Q-GP-41), pre-placed by the theater file.
- A facility is an ordinary STATIC unit with HP and damage states. It can be struck, disabled and repaired like any unit, its side follows its base, and it is never captured on its own. This gives air roles targets of their own ("knock out the radar at EAST FOB before the convoy goes in").
- **Modular:** a new facility kind (for example a missile-interception site later) is a new catalog entry through the content pipeline (CONFIG-AND-CONTENT §7a), not new kernel rules. Building and upgrading facilities with surplus supply is GAMEPLAY-LATER §5a.
- **Neutral bases (Q-GP-36):** a neutral base just exists until captured and has no facilities; the theater validator rejects facilities at a base whose start owner is NEUTRAL, so a facility's side is always COALITION or ENEMY.
- Facilities have no crew (crew count 0), so disabling one never produces a downed-crew marker.
- **Never destroyed (Q-GP-37):** infrastructure is always repairable: a facility's hp floors at Disabled and it is never Destroyed; bridges already repair (§5).
- **Repair (Q-GP-26):** a damaged or disabled facility repairs over time at `logistics.repair_rate.<node_kind>` by spending its base's stock while the base is friendly and not contested, like units at a base. A disabled facility does nothing (no sensing, no fire, no production) until repaired past Disabled. Deliveries become stock and stock repairs facilities, so resupply is how logistics fixes a base (Q-GP-47 replaces the Q-GP-30 truck multiplier); engineers (P4) repair faster, also away from a base.
- **Visibility (Q-GP-27):** facility positions and kinds are known to both sides, like nodes (FOW-10); their damage state is known only through sensors, and an air-defense ring shows only once detected; whether an emitter is on is visible per FOG-OF-WAR FOW-11.
- Parity: the Static's facilities follow the same rules.

## 6. Combat
- Each tick, a unit with a ready weapon chooses the **highest-priority valid target** in range; only targets its side currently tracks are valid (never last-known tracks), so a SIGINT blob is something to scout, never to shoot (Q-FOW-4; area weapons may hit blobs later): by domain compatibility, then threat, then distance, with a stable tie-break by id.
- **Shot resolution (Q-GP-7, Q-GP-12):** a shot is not an entity. Firing spends the round and stores a pending impact with its target and weapon; the impact lands after `ceil(range / projectile speed / WORLD_DT)` ticks (guns land at once). Pk is rolled on the `combat` stream when the impact lands, using the target's state then (track quality is captured when the shot is fired and stored with the pending impact) (position, track quality, evasion, countermeasures, jamming, terrain). A target that is destroyed, despawned or out of the weapon's envelope before impact makes the shot fizzle as a miss with no roll. Projectiles as flying entities (for example intercepting SAMs) come later.
- Hit probability (Q-CBT-2) = `base_pk` × the product of these multipliers from config, rolled on the `combat` RNG:
  1. **Track quality:** track 1.0, radar lock, painted 1.25 (PROPOSED); a blob value returns with area weapons (Q-FOW-4).
  2. **Range** vs the weapon envelope.
  3. **Target evasion** (per-platform maneuverability) and **altitude band**.
  4. **Jamming** on either side.
  5. **Countermeasures** (chaff/flares, one-shot per load).
  6. **Terrain masking** (flag from the theater's `masking_regions`, Q-FOW-3).
  7. **Weather and night** (P4, Q-CBT-5).

  **First build (Q-GP-6):** factors 1, 2, 3 and 6 are implemented; jamming, countermeasures and weather/night arrive with the units or phases that produce them, and an unimplemented factor is a multiplier of 1.0, listed in the fallback registry (DATA-INTEGRITY). The full list stays the target design and is being fleshed out. Per-platform attributes (§6a) feed these factors. The PiP intercept scope shows the resulting Pk during engagements (Q-CBT-3).
- **Stance (Q-CBT-6):** `standard` auto-RTBs at mission-kill if still mobile; `cautious` RTBs at Damaged; `press` never auto-RTBs; `guns` keeps fighting with guns after missiles/bombs run out. In the first build the `stance` field exists (kernel default `standard`) and no command sets it; `!stance` and deploy-time stance come with the flag (GAMEPLAY-LATER §3, Q-GP-3).
- SAMs have engagement rings. Jammers reduce enemy pk within their corridor. SEAD missiles home on emitting radars, and radars may go dark ("blink") to avoid them.
- Kills and assists generate events. A recon "paint" grants assist credit (PROGRESSION).

## 6a. Platform attributes, disabled units, crew and CSAR (owner, 2026-10-17)
- **Per-platform attributes** (unit catalog, CONFIG §7/§7a; all PROPOSED): armor level per facing or generic, maneuverability/evasion, speed per terrain type (road, off-road, sand, mountain, urban, water), sensor and weapon profiles, countermeasures, crew count. Hot-loaded platforms define these too, inside the stat envelope.
- **Damage states:** Healthy → Damaged (slower, reduced sensors) → Mission-kill (must RTB, repairable) → **Disabled** (can't move, not destroyed) → Destroyed (Q-CBT-1). The state is derived from the unit's `hp` fraction (PROPOSED: Damaged below 70%, Mission-kill below 35%, Disabled below 10%, Destroyed at 0; `combat.damage_state.*`). A hit does fixed weapon damage reduced by armor, so armor shifts how many hits each state takes (Q-GP-8).
- **Crew survival:** when a unit is disabled or shot down, a seeded crew-survival roll (modified by platform and location) decides whether the crew is alive. The crew is shown on the map as a downed-crew marker. *Working name "crew"; a playful mascot name is possible under the brand guide.*
- **CSAR** (P4+): moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §6a. Crew survival rolls and downed-crew markers stay here.
- **Consequences without punishment** (Q-CBT-9): losses cost the *team* (base stock spent, a longer respawn for that unit type) rather than taking XP from the player.

## 7. Packages (P4)
Moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §7.

## 8. Capture
- **Base defenses first (Q-GD-18):** each node has defense HP (configurable, upgradable via §5a). Capture can't begin until HP is 0. Air strikes, artillery and ground fire reduce HP; supply deliveries repair it; starvation slowly drains it (`logistics.starve_hp_drain_per_min`, PROPOSED).
- Capture requires a ground or logistics unit within `capture.radius_m`, with no enemy ground unit contesting it. Progress takes `capture.time_s` (PROPOSED 120 s, world time, Q-ALN-23), scaled by the number of units with diminishing returns. Air units can't capture. **Formula (Q-SIM-22, Q-SIM-26):** `time = max(capture.min_time_s, capture.time_s × quiet_mult(v) ÷ n^capture.multi_unit_exponent)`, where `n` is the number of capturing units in radius and `v` the number of live viewer units in kernel state (deterministic, no new input). `quiet_mult` rises linearly from `capture.quiet_floor` at `v` = 0 to 1.0 at `v` = `capture.quiet_ref` and stays 1.0 above.  `min_time_s` is the only cap on how fast a crowd can flip a base (Q-GP-4). Contested progress decays at `capture.decay_per_s` (Q-SIM-23). The quiet-stream factor applies to the coalition only (below). Easing other loops (repair, resupply, rearm) waits for harness results (Q-SIM-27).
- **Facilities never contest (Q-GP-38):** facilities do not freeze or slow capture and do not count for the garrison or empty-base modifiers below; base defense HP models fixed defenses.
- **Garrison modifier (Q-GD-32, Q-ALN-33):** a combat-capable defending unit at the base freezes capture (contested). Defending units that cannot contest (parked air, Disabled units) heavily slow it; an empty base is captured faster. Both are configurable multipliers (PROPOSED). Applies to both sides.
- **Facilities at a captured base (Q-GP-25):** facilities are not mobile units: when a base flips, its facilities switch side and keep their current damage.
- **Units at a captured base (Q-GD-32):** when a base flips, each mobile unit there escapes to the nearest reachable friendly base if its fuel allows. Every other mobile or parked unit there is destroyed, with a crew-survival roll (§6a). Facilities (units with a `base_id`) are exempt: they switch side (§5b). Applies to both sides.
- Progress decays when the node is uncontested and unoccupied. A capture can't flip twice in one tick (property test).

## 9. Campaign, objectives, win/loss (resolves critique #12)
- **Modes:** Total Domination (MVP). Hold the Line and Siege moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9.
- **Theater objective (Q-GD-19):** calm, not railroading. The objective mode is set per campaign:
  - `timed` (default): every `campaign.objective_period_min` (PROPOSED 15 min, game time) the system picks one frontline node (own `objective` RNG stream, Q-SM-1) and announces it with a timer. Completing it gives a merit bonus.
  - `off`: sandbox/creative, no system objectives.

  The owner and Admins can also set objectives; a GM cannot (Q-ALN-10). Whenever an objective exists it is visible on screen.
- **Strategic nodes (Q-GP-17, Q-GP-21):** AIRBASE, FOB and PORT bases count toward the hold fractions below. BRIDGE nodes and the SANCTUARY do not, and facilities (radars, factories, air defense) never count on their own; the enemy HQ is its own win route.
- **Victory (Domination):** hold ≥ `campaign.victory_node_frac` (PROPOSED 0.80) of strategic nodes for `campaign.victory_hold_min` (PROPOSED 30 min, game time) continuously, **or** capture the enemy HQ. The rubber-band zone is tuned to 55–75% so that victory sits beyond it.
- **Defeat (Q-GD-7):** the coalition loses its forward airbase **and** holds ≤ 25% of strategic nodes for 30 min (game time) continuously. **Idle floor (Q-GP-28, Q-GP-44):** with 0 humans present (no live viewer unit under player control; AUTO units don't count), capture progress on the coalition's last AIRBASE freezes, so the Static can never take it and a war is never lost while nobody plays; the slow idle drift is a deliberate "come back and retake it" hook. The sanctuary base can never be captured.
- **Campaign clock:** 48 h target (game time, Q-ALN-1; admin-adjustable, schedulable per campaign, Q-GD-5). It **never pauses for lack of humans** (Q-GD-4 amended): at 0 humans the Static drops to Pattern of Life (THREAT-DIRECTOR §5a). Only a sim pause with a reason stops the clock: a staff pause (ADMIN-RBAC pause flow), the auto-pause when the broadcast has been offline longer than `ops.offline_pause_after_min` (reason TECHNICAL, Q-OPS-8), the weekly maintenance window, or the owner's Ceasefire mode (Q-OPS-9); pause reasons are STAFF, TECHNICAL, MAINTENANCE and CEASEFIRE (Q-ALN-3), and a STAFF pause may carry a sub-reason (RAID, ABUSE, CONTENT, OTHER; Q-ALN-31). Timers on both sim clocks freeze with it (Q-CFG-8, Q-ALN-2).
- **Time limit (Q-GD-29):** hitting the time limit decides by score = node share over time + completed objectives. Higher score wins; an exact tie is a draw with no special screen (Q-GP-10). The draw band, Stalemate screen, special event and banter are in [GAMEPLAY-LATER](GAMEPLAY-LATER.md) under "Moved from the first-build review".
- **End of campaign (Q-UX-8, Q-UX-4):** a victory or "SIGNAL LOST" moment (optional configurable zoom on the final action), a ~5-minute after-action review (top operators per role, best rescue, the "what you didn't see" reveal with the seed, Q-CT-2), then a looping War Briefing card during the intermission. Advancement is configurable: `auto_advance` (next war after N min) or `await_owner` (one-tap owner approval). The next theater rotates archetypes with no back-to-back repeat, reusing the first theater with a new seed until more exist (Q-SM-4).
- **Units reset each war** (Q-GD-23); rank, callsign, cosmetics and stats persist. Survivor reward: [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9.

## 9a. Theater style and orientation (owner, 2026-10-17)
- **Theater variety** is a design goal; the archetype rotation moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9a.
- **Theater #1 (Q-GD-33, Q-GP-22):** small, about 8 bases (3 coalition, 3 Static, 2 contested; a sketch for the NX-008 sign-off). Later theaters in the rotation are larger (12–20 bases). A map that grows inside one campaign is parked in GAMEPLAY-LATER. It is a land-leaning map with a bridged strait, so the water theme works before naval units arrive (P3).
- **Orientation:** the coalition (chat) is always on the **left (west)**, the enemy on the **right (east)**, and the main axis of advance runs left → right. Theater files must declare `orientation: west_to_east`, and the theater validator rejects maps whose sanctuary isn't in the left third. For the vertical 9:16 layout, see Q-GD-13.
- **Urban terrain** rules (NX-129) moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9a.

## 9b. Campaign carry-over
Moved to [GAMEPLAY-LATER](GAMEPLAY-LATER.md) §9b.

## 9c. Theme vs strategy rule (owner, 2026-10-17)
The signal and Static theme is a **presentation layer over the strategy game, never a replacement for it**:
- **TS-1:** Chat volume and viewer count never directly buff, nerf or decide anything. Outcomes come only from units, logistics, fog of war and the director rules. (The director already scales on coalition *units and supply*, not on chat activity.) Supply-drop redemptions therefore have a fixed global hourly cap (`support.supply_drop.max_per_hour`, PROPOSED/TBD by harness) plus a shared cooldown, independent of audience size (Q-SUP-7, SUPPORT-REDEMPTIONS).
- **GM scope (Q-AI-8, Q-ALN-10, Q-ALN-11):** during play a human GM drives the Static and triggers world events only, and injects jobs only into the Static's Tasking Board (TB-11). A world event may help the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction. A GM never grants units, ammo or XP to specific players. Campaign setup (objectives, unlimited ammo and other campaign options) is owner/Admin only, never GM. Every GM action is logged and flagged in replays.
- **TS-2:** "Momentum" stays a strategic measure (nodes, stock, recent events). Any "signal strength" visuals are cosmetic flavor on top of it: map color brightness, static overlay intensity, sound.
- **TS-3:** The game must play well at **0 viewers** (AI garrison + Pattern of Life, Q-GD-4 amended) and scale smoothly upward. No mechanic may require a minimum crowd.
- **TS-4:** Lore names (The Static, Relays, etc.) relabel things on screen and in sitreps only. Mechanics and their docs keep plain names (node, unit, supply).

## 10. Readability rules (stream-facing)
Moved to OVERLAY (Q-GP-9); the always-visible items and the 5-second "who is winning" criterion are the overlay's acceptance tests.

## 11. Test plan
Every rule above gets a unit test plus the property tests from TESTING-STRATEGY §3.1. Balance scenarios are defined in the harness. Tasking Board assignment (TB-5) gets a replay determinism test, and pause tests check that game-time and world-time timers freeze (Q-CFG-8). Specific checks for the Q-ALN decisions:
- Q-ALN-1: with `sim.time_scale` ≠ 1, a game-time timer (e.g. `presence.idle_handoff_min`) fires after the same number of ticks as with `sim.time_scale` = 1, while world-time movement scales.
- Q-ALN-6: a configured duration that is not a whole number of ticks converts to the next tick up, never down.
- Q-ALN-2: while paused, `!me`, `!status`, `!quiet` and a reserve-queue join are accepted; every other command gets "war paused" and changes no sim state.
- Q-ALN-9: an AUTO unit occupies its commander's slot; a `!join` from that commander reclaims it and the live-unit count for that commander stays 1.
- Q-ALN-10/11: a GM cannot set objectives or campaign options, and a GM job injection into the Quorum's board is rejected.
- Q-ALN-12: `!quiet` twice returns the opt-out to its original state, and each use gets a confirmation naming the new state.
- Q-ALN-23: with `sim.time_scale` ≠ 1, capture progress scales with it, while the claim lease and the package fill wait take the same number of ticks as at `sim.time_scale` = 1.
- Q-ALN-24: while paused, a ban despawns the banned commander's unit and a director override is rejected.
- Q-ALN-25: a Disabled unit reaching idle retire despawns where it is and no cargo returns to the reserve; a `hold` unit handed off to AUTO stays at base until it claims a job.
- Q-ALN-26: a `!join` while paused queues even with a free slot; `!quiet` and `!help` do not reset the idle timers.
- Q-ALN-30: a job completed by an AUTO unit adds an AUTO assist and no XP or merit.
- Q-ALN-34: a kill, a supply delivery or capture participation by an AUTO unit adds an AUTO assist and no XP or merit.
- Q-GP-25: when a base flips, its facilities switch side and keep their hp; no facility rolls crew survival.
- Q-GP-31/33: a follow loop or self-follow is rejected with `FOLLOW_TARGET_INVALID`; when a middle leader despawns, its followers take that leader's own leader.
- Q-GP-24: the source rule never takes a base below its starvation threshold.
- Q-GP-23: `!join strike` with no parameters claims a job on the spawn tick; `!join strike <node>` does not auto-task until that order completes.
- Q-ALN-33: an enemy combat-capable unit at a node being captured freezes progress; a parked air unit or a Disabled unit there only slows it.

## 12. Open questions
Decided and folded in (2026-10-18): Q-ALN-23 (capture on world time; claim lease, priority aging and package fill wait on game time; timer note), Q-ALN-24 (staff actions while paused), Q-ALN-25 (Disabled retire, `hold` handoff), Q-ALN-26 (paused `!join`, idle-timer resets, AUTO tag), Q-ALN-30 (AUTO assists), Q-ALN-31 (pause sub-reason), Q-ALN-33 (combat-capable defenders freeze capture; defenders that cannot contest slow it, §8), Q-ALN-34 (no XP, merit or leaderboard credit for any AUTO action, TB-10), Q-ALN-36 and Q-ALN-37 (actions and redemptions while paused).
Decided in the 2026-10-18/19 grilling: Q-GP-1 to Q-GP-34 (OPEN-QUESTIONS, "GAMEPLAY grilling"): split to GAMEPLAY-LATER, sim-only commands, stance field only, capture formula, job types, hit factors, shot resolution, damage states, review cuts, time-limit ending, single supply number, trucks-only supply, strategic nodes, `!join` targeting, job priority, facilities, logistics source and conduct, facility repair and visibility, idle floor, escort jobs, follow, station and chains.
