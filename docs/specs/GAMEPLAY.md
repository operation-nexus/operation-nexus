# SPEC: Gameplay Rules


> **All numeric values in this spec are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). They become real only after the balance harness validates them.
Status: Draft · Tracker: NX-120…NX-149 · Inputs: Raw plans P206–225, P983–1009, P1139–1168; conversation C1–C48

All numbers below are **initial balance values** in `balance/default.yaml`. They're tuned with the balance harness, not hard-coded.

**Timers (Q-CFG-8):** every timer that changes sim state runs in **sim time** (ticks): decision window, idle handoff/retire, respawn delay, cooldowns, logistics, capture, objective period, victory/defeat hold, package fill. Config keys use friendly units (s/min) and are converted to ticks at load. Sim-time timers freeze while the sim is paused. Timers outside the sim (chat rate limits, digest batching) use a monotonic real clock and belong to CHAT-GATEWAY.

**First-build scope (Q-PROD-8):** the first build ships the core loop, damage states (§6a), base defense HP (§8), limited munitions (§5), fog of war, director tiers with Pattern of Life, and the Tasking Board (§1b). Stances (`!stance` and deploy-time stance, §3/§6), CSAR and crew rescue (§6a, `!rescue`), world events, base upgrades (§5a) and weather (§6) come later behind feature flags. With stances off, every unit behaves as `standard`.

## 1. Core loop (what a viewer does in 30 s)
1. Type `!join strike|recon|logi`. Within 500 ms (server side) a radar ping and their callsign appear at a base.
2. The unit holds at base for a short **decision window**, then takes the best open job from the **Tasking Board** (§1b) if the operator gave no order. Assisting the current objective is one of those jobs, not an automatic route.
3. Optionally type `!target <node>`, `!rebase <node>`, `!stance <…>` or `!rtb`.
4. The unit completes or fails its mission, and the viewer sees a contribution line in the ticker.

## 0. Parity rule (owner, 2026-10-17)
**Both sides play by the same rules.** The Static has the same mechanics as Clearwave: scouting, fog of war (FOW-4), supply and starvation, rebasing, damage states, ammo, and rescue/recovery where it applies. Any new mechanic must say how it applies to both sides, or explicitly justify an asymmetry (e.g. the sanctuary base) in its spec.
- **Static economy (Q-GD-30):** the director's budget is the Static's real stock and factories, which the coalition can raid and starve. Its infinite rear source sits behind its capturable HQ (the coalition's sanctuary can never be captured, §9).
- **Static tasking (Q-GD-34):** the Static uses the same Tasking Board (§1b). The director is the strategic layer that creates jobs on the Static's board (stage, escort, strike, defend, reposition), with the same job types and mechanics as Clearwave. It may compose richer job combinations but gets no unique powers.
- **Lieutenants (Q-GD-38, P4, NX-317):** later, sectors may be run by Static lieutenants, each a Threat Director profile on the same mechanics. Not in scope before P4.

## 1a. "Did my command work?" feedback (owner requirement, Q-MOD-1)
Viewers see a generated callsign, not their username, so the game must connect "me" to "my unit" unmistakably. Otherwise they assume nothing happened and leave.
- **FB-UX-1 Chat confirmation:** the bot's batched digest names the platform user and their callsign, e.g. "@SaltyUser → VIPER-27 deployed (strike) from WEST BASE". It's sent within platform rate limits (Twitch as a moderator: 100 messages / 30 s, per PLATFORM-REALITY-CHECK), with up to N mentions per digest message (N PROPOSED).
- **FB-UX-2 On-screen recruit strip:** for 10 s after each spawn, a "NEW RECRUITS" strip shows the callsign, platform icon and role, with a ping on the map at the spawn point.
- **FB-UX-3 `!me`:** highlights your unit for 5 s, and the next chat digest repeats your callsign and status. Also works while you're in the reserve queue (shows your position). `!status` is a pure alias with identical behavior (Q-UX-12).
- **FB-UX-4 First-time hint:** a commander's first successful command adds a one-time "New? You're VIPER-27. Type !me anytime." line to the digest.
- **FB-UX-5 Rejections are visible too.** Reasons like "unit in sortie" or "respawn in 12 s" are batched into the digest with the callsign, never silently dropped.
- **FB-UX-6 Measure it:** track the share of first-time commanders who issue a second command (NX-036). A low value means the feedback isn't working.

## 1b. Tasking Board (owner decision 2026-10-17, Q-GD-26; decision-window length is a playtest value)
A shared queue of **jobs** the system generates from the live situation, so every unit, human or AI, always has something useful to do:
- **Job types:** resupply a starving base, scout a sector or blob, escort a convoy, defend a threatened node, strike a target, rescue a downed crew, repair a bridge, assist the current objective.
- **Each job has:** a priority (from objective, threat and starvation level), the role(s) that fit, a **slot count** (how many units it needs), and an expiry.
- **Assignment:** a unit with no explicit order takes the highest-priority open job matching its role. Slots prevent pile-ups: a job is skipped once its slots are full, unless *every* job is full.
- **AI garrison** pulls from the same board, but only takes jobs no human has claimed, and releases them when an operator wants one. **The AI garrison never initiates offense**: it takes defend, resupply, scout and rescue jobs, and joins strike jobs only when a player started them (objective, rally call, player-led flight). **Sole exception (Q-GD-31):** it may counterattack a node the coalition just lost, within a configurable window (PROPOSED ~15 min), using only units still able to fight (not Disabled or Destroyed).
- **Feasibility:** a unit only takes a job it can reach and complete with its current fuel and munitions. Otherwise it first takes a rearm/refuel step (nearest base with stock, Q-GD-17).
- **Logistics routing:** a supply job sets the *destination*; the route is planned automatically along roads/sea lanes. Players can still override with `!target` or `!rebase`.
- **Visible:** the overlay shows the top few open jobs ("NEEDED: supply to WEST FOB") so lurkers learn what matters, in the rotating HUD panel at double frequency (Q-UX-11, OVERLAY).
- **Decision window (owner idea, playtest):** after `!join`, the unit **holds at base for a short window** (configurable, sim time; owner suggested up to ~5 min) waiting for an explicit order, then auto-takes a job. Any explicit order cancels auto-tasking. `!join <role> hold` opts out of auto-tasking entirely.

**Robustness (Q-GD-37).** These apply to both sides' boards:
- **TB-1 Lifecycle:** a job moves OPEN → CLAIMED → ACTIVE → DONE | FAILED | EXPIRED. A claim is a **lease**: if the claiming unit makes no progress within the lease, the claim is released and the job returns to OPEN.
- **TB-2 Feasibility pre-check:** before claiming, a unit checks fuel, munitions, a route, and known threats on that route.
- **TB-3 Priority aging:** an open job's priority rises the longer it waits, so low-priority jobs are never starved.
- **TB-4 Slots and dedupe:** every job carries a slot count and a dedupe key. Generating a job whose key matches an open job updates that job instead of adding a second one.
- **TB-5 Deterministic assignment:** units are assigned in a stable sort order with a seeded tie-break, so a replay reproduces every assignment (SIM-CORE).
- **TB-6 Cadence:** the board is re-evaluated every N ticks (configurable, PROPOSED), not every tick.
- **TB-7 Preemption:** a human order always wins over a board job. An emergency job may preempt **AI-run units only**.
- **TB-8 Dependencies:** a job may depend on another (e.g. repair bridge, then convoy) and can't be claimed until that job is DONE.
- **TB-9 Per-side fog of war:** each side builds its board only from its own fog-of-war view (FOW-4).
- **TB-10 Logged outcomes:** every job's lifecycle and outcome is emitted as sim events for balance tuning and AAR stats.
- **TB-11 Command Center:** both boards are visible and editable in the Command Center, and a GM can inject jobs (within GM scope, §9c).

## 2. Roles (MVP, resolves critique #7 and #8)
| Role | Command | Domain | Does | Can't |
|---|---|---|---|---|
| Strike | `!join strike` | AIR | Attacks ground/air targets; suppresses SAMs poorly without SEAD | Capture nodes |
| Recon | `!join recon` | AIR | Large sensor radius; converts SIGINT blobs to tracks; paints targets | Deal damage |
| Logistics | `!join logi` | GROUND | Carries supply along roads to nodes; captures uncontested nodes slowly | Fight |
| Naval | `!join navy` | SEA | **P3** (Q-GD-8: sea domain moved earlier because maps are water-heavy) | — |

Specialist chassis (SEAD, jammer, engineer, AWACS, artillery) unlock with rank (PROGRESSION). **Specialist doctrines** are chosen once per campaign and lock (Q-GD-3).

**Display names (Q-NAME-2, working names; final list in the brand guide NX-274):** roles and unit kinds keep plain ids in code and contracts (TS-4), but the stream shows friendly class names: Striker (multirole jet, `STRIKE`), Scout (recon drone, `RECON`), Hauler (supply truck, `LOGI`), Tank, Gunboat, Tanker (refueler), Lifter (rescue helo), Sentinel (anti-air site), Spire (radar). No real-world platform names (Q-PROD-5).

## 3. Commands (single source of truth)
Rank ids `O-1`…`O-6` are **internal ids** used in config and contracts. On stream and in replies they show as themed display names (Q-NAME-1, PROGRESSION §3).

| Command | Args | Min rank | Notes |
|---|---|---|---|
| `!join <role> [stance] [hold]` | role, optional stance, optional `hold` | O-1 | Spawns your one unit, or switches role if your unit is at base. `hold` opts out of Tasking Board auto-tasking (§1b) |
| `!target <node>` | node name/alias (fuzzy match against a fixed list) | O-1 | Sets your unit's objective |
| `!rtb` | — | O-1 | Return to the nearest friendly base |
| `!stance <press\|standard\|cautious\|guns>` | stance | O-1 | Standing intent for your unit: `press` = keep fighting even when badly damaged; `standard` = auto-RTB at mission-kill (default); `cautious` = RTB as soon as Damaged; `guns` = keep fighting with guns after missiles/bombs run out (default is auto-RTB when out of munitions). Can also be given at deploy: `!join strike press` (Q-CBT-6). |
| `!rebase <node>` | friendly node | O-1 | Move your unit to another friendly base and stay there to refuel/rearm/stage (e.g. move a plane forward before an attack). Uses that base's stock. The Static does the same (THREAT-DIRECTOR §5a). |
| `!me` | — | O-1 | Highlights your unit for 5 s; the next digest repeats your callsign, status, remaining cooldowns, queue position and your own conduct standing / active restriction (FB-UX-3, Q-MOD-5) |
| `!status` | — | O-1 | Alias of `!me`, identical behavior (Q-UX-12) |
| `!rally <node> <attack\|defend\|supply>` | node + intent | O-3 | Templated rally call: map pin + banner with your callsign, cooldown. Informs only, never controls other units. Support can make it more prominent, never more powerful (Q-SUP-6) |
| `!rescue <marker>` | downed-crew marker | O-1 (needs a suitable unit) | Mount a CSAR mission (§6a) |
| `!scout <sector>` | sector | any (reserve queue) | Cheap intel ping while waiting in the reserve queue (RQ-4) |
| `!help` | — | any | Short command digest (Q-UX-1) |
| `!guide` | — | any | Link to the Field Manual on the public site (Q-UX-1) |
| `!rules` | — | any | Link to the published community/conduct rules (Q-MOD-5) |
| `!quiet` | — | any | Opts your callsign out of being named in mastermind taunts (Q-AI-7). Ships with taunts that name operators |
| `!link` | — | any | Shows the static account-linking portal URL (IDENTITY §4; ships with YouTube in beta, Q-PROG-5) |
| `!callsign <NAME>` | `^[A-Z][A-Z0-9-]{2,11}$`, moderated, 1 change / 30 days | First completed mission (Q-PROG-3) | Reserve a global callsign |
| `!vector <bearing> <km>` | ints | O-2 | Manual waypoint from your unit |
| `!sead`, `!artillery`, `!engineer`, `!jammer`, `!awacs` | — | per PROGRESSION | Specialist spawns |
| `!package <NAME>` / `!wingman` | — | O-5 / O-1 | Form or join a formation (§7) |
| `!doctrine <name>` | — | O-3 | Once per campaign |
| `!order <text>` | free text ≤ 200 chars | O-3 | **P4**, LLM-parsed, own unit only |
| `!forget` | — | any | Data deletion request (SEC-DATA-3) |

Unknown commands and ordinary chat are ignored. Command aliases are configurable.

## 4. Unit slots
- **GP-1** Each commander has at most **one live personal unit**. `!join` while your unit is alive retargets or switches it only if it's at a base. Otherwise you get the reply "unit in sortie".
- **GP-2** After death, respawn is allowed after `slots.respawn_delay_s` (PROPOSED 20 s, sim time) to stop suicide spam. The delay grows with repeated losses in a short window, and a rescued crew removes part of it (Q-CBT-9). Losing a unit never costs XP; deliberate disruption is handled by the conduct system (ADMIN-RBAC §6.8).
- **GP-3** Above `slots.max_viewer_units` (Q-GD-6) new joiners go to a visible reserve queue. The queue is served FIFO as slots free up.

## 4a. Reserve-queue mitigations (Q-GD-6 decided with mitigations)
- **RQ-1:** show the queue length on the HUD. Each queued viewer gets their position via the digest or `!me`.
- **RQ-2: Dynamic cap.** `slots.max_viewer_units` is a ceiling. The runtime may lower the effective cap while tick time is over budget, and raises it back when there's headroom (logged, visible on the ops dashboard).
- **RQ-3 (P4, ships with packages §7; Q-GD-36): Units merge into flights before anyone queues.** Joiners attach to existing human flights as wingmen (sharing one map symbol) before the queue is used. Only when every flight is full does the queue start. The alpha uses the plain reserve queue only.
- **RQ-4: Queued viewers still contribute.** While waiting they can `!scout <sector>`, a cheap intel ping that reveals SIGINT detail briefly, and they earn a small participation merit (PROPOSED values, diminishing).
- **RQ-5: Priority and fairness.** Q-GD-14: FIFO, with a boost for first-time commanders and a max-wait guarantee. Silent commanders' units are handed off and then retired (§4b) to free slots.

## 4b. Silent viewers (Q-GD-35)
Chat gives no presence signal, so silence is measured as time since the commander's last command (sim time, Q-CFG-8).
- **GP-4 Idle handoff:** after `presence.idle_handoff_min` (PROPOSED default 10) with no command from its commander, the unit finishes its current order and joins the Tasking Board as an AI-run unit. The overlay tags it **AUTO**.
- **GP-5 Idle retire:** after `presence.idle_retire_min` (PROPOSED default 30) with no command, the unit RTBs and despawns. Supplies it carries return to the reserve.
- **GP-6 Reclaim:** any command from the commander while the unit is alive restores their control and clears the AUTO tag.
- Both timers are admin-configurable in the Command Center.

## 5. Logistics (resolves critique #13)
- Nodes hold `stock` (0..max). Spawning or rearming at a node consumes stock according to the unit's loadout cost.
- **Sources:** the SANCTUARY base has infinite stock but is far away. A FACTORY generates `logistics.factory_rate` per minute, but only while it's connected by owned roads to the sanctuary.
- **Starvation:** below `logistics.starve_threshold` (PROPOSED 25%) units spawn with reduced loadouts (50% fuel, guns only, with the gun round count also drawn from stock). At 0, the node can't rearm.
- **Munitions per sortie (Q-CBT-7):** every unit leaves with a limited load drawn from base stock. **Guns are limited too** (high round count); rounds used are charged to base stock on resupply. Out of missiles/bombs → auto-RTB unless stance `press` or `guns` (§3). **Unlimited ammo** is a campaign/test option (testing, special events) settable by owner/admin/GM only, never live mid-war.
- **Repairs (Q-GD-27):** repair happens at a friendly base with stock, for **all domains** (aircraft at airbases, ground vehicles at bases/depots, ships at ports). It costs time and stock and is faster at bigger or upgraded bases. Engineers field-repair disabled vehicles. Same rules for the Static (parity).
- Logi trucks carry `cargo`, drive the road graph (A* over ROAD edges, cost = length / speed_mult), and unload over time at the destination.
- **Bridges** are nodes with HP. A destroyed bridge removes its edge until it is repaired (Q-GD-11): **logistics trucks** can do a slow field repair (`logistics.bridge_repair_time_s` × `logistics.truck_bridge_repair_mult`), and **engineers** repair fast and can also build short new crossings (Q-GD-21).
- **Supply-line stretch** (snowball breaker): coalition truck transit time scales with road distance from the sanctuary. Enemy reinforcement time shrinks as the front nears its HQ.
- Units heal and rearm **only while landed or parked at a friendly node**, by spending stock. They never heal passively (fixes the immortality bug).
- **Empty bases stay bases** (Q-GD-17): at 0 stock, units can still land, garrison and wait there for a resupply convoy. They get no fuel or ammo, but keep what they have and can take off again with reduced endurance.

## 5a. Base upgrades (P4; extension point reserved now)
Owner idea: sending **surplus supply** to a base gradually upgrades it: a radar site gains range, an air-defense site gains faster interceptors, an airbase rearms quicker. Upgrades decay or are lost if the base is starved or captured.
- **Reserved now so it doesn't need a rewrite later:** nodes carry `tier: int` and `upgrades: [UpgradeId]` in the world model, and all node stats are read through a modifier layer (base stats × tier/upgrade modifiers from config). The MVP ships with tier 0 and no upgrades.

## 6. Combat
- Each tick, a unit with a ready weapon chooses the **highest-priority valid target** in range: by domain compatibility, then threat, then distance, with a stable tie-break by id.
- Hit probability (Q-CBT-2) = `base_pk` × the product of these multipliers from config, rolled on the `combat` RNG:
  1. **Track quality** by FoW tier: blob 0.2, track 1.0, radar lock, painted 1.25 (PROPOSED).
  2. **Range** vs the weapon envelope.
  3. **Target evasion** (per-platform maneuverability) and **altitude band**.
  4. **Jamming** on either side.
  5. **Countermeasures** (chaff/flares, one-shot per load).
  6. **Terrain masking**.
  7. **Weather and night** (P4, Q-CBT-5).

  Per-platform attributes (§6a) feed these factors. The PiP intercept scope shows the resulting Pk during engagements (Q-CBT-3).
- **Critical hits (Q-CBT-8):** a small seeded chance of an outsized effect (e.g. a radar knocked offline for a while), shown with a callout. Configurable.
- **Friendly fire (Q-CBT-4):** off in v1. It is a per-campaign option set at campaign setup (never toggled mid-war), default off, editable by owner/admin/GM only.
- **Stance (Q-CBT-6):** `standard` auto-RTBs at mission-kill if still mobile; `cautious` RTBs at Damaged; `press` never auto-RTBs; `guns` keeps fighting with guns after missiles/bombs run out. Set at deploy (`!join strike press`) or with `!stance`.
- SAMs have engagement rings. Jammers reduce enemy pk within their corridor. SEAD missiles home on emitting radars, and radars may go dark ("blink") to avoid them.
- Kills and assists generate events. A recon "paint" grants assist credit (PROGRESSION).

## 6a. Platform attributes, disabled units, crew and CSAR (owner, 2026-10-17)
- **Per-platform attributes** (unit catalog, CONFIG §7/§7a; all PROPOSED): armor level per facing or generic, maneuverability/evasion, speed per terrain type (road, off-road, sand, mountain, urban, water), sensor and weapon profiles, countermeasures, crew count. Hot-loaded platforms define these too, inside the stat envelope.
- **Damage states:** Healthy → Damaged (slower, reduced sensors) → Mission-kill (must RTB, repairable) → **Disabled** (can't move, not destroyed) → Destroyed (Q-CBT-1). Armor shifts the chances between these outcomes.
- **Crew survival:** when a unit is disabled or shot down, a seeded crew-survival roll (modified by platform and location) decides whether the crew is alive. The crew is shown on the map as a downed-crew marker. *Working name "crew"; a playful mascot name is possible under the brand guide.*
- **CSAR (combat search and rescue):** operators can mount a rescue (`!rescue <marker>`) with suitable units: helicopters or ground vehicles once those exist, recon for spotting. Successful rescues give a **large XP and merit bonus** to the rescuers and recover the crew. The Static may try to capture downed crews, which sets up a race. Disabled vehicles can also be recovered or repaired in place by engineers or logistics.
- **Consequences without punishment** (Q-CBT-9): losses cost the *team* (base stock spent, a longer respawn for that unit type) rather than taking XP from the player.

## 7. Packages (formations)
A package is a group of up to 4 existing units, with a lead (O-5+) or an auto-lead. It shares the lead's target and gives a small jamming/escort benefit plus an XP share bonus. **There is no lobby wait.** Units join as they spawn. If fewer than 2 humans are in the package after 30 s, an NPC wingman may fill a slot (Q-GD-10).

## 8. Capture
- **Base defenses first (Q-GD-18):** each node has defense HP (configurable, upgradable via §5a). Capture can't begin until HP is 0. Air strikes, artillery and ground fire reduce HP; supply deliveries repair it; starvation slowly drains it (`logistics.starve_hp_drain_per_min`, PROPOSED).
- Capture requires a ground or logistics unit within `capture.radius_m`, with no enemy ground unit contesting it. Progress takes `capture.time_s` (PROPOSED 120 s, sim time), scaled by the number of units with diminishing returns. Air units can't capture.
- **Garrison modifier (Q-GD-32):** defending units present at the base heavily slow capture; an empty base is captured faster. Both are configurable multipliers (PROPOSED). Applies to both sides.
- **Units at a captured base (Q-GD-32):** when a base flips, each mobile unit there escapes to the nearest reachable friendly base if its fuel allows. Every other unit there is destroyed, with a crew-survival roll (§6a). Applies to both sides.
- Progress decays when the node is uncontested and unoccupied. A capture can't flip twice in one tick (property test).

## 9. Campaign, objectives, win/loss (resolves critique #12)
- **Modes:** Total Domination (MVP), Hold the Line (P4; ends after N escalating waves or a time limit, Q-GD-15), Siege / AI-holds-out (backlog, Q-GD-2).
- **Theater objective (Q-GD-19):** calm, not railroading. The objective mode is set per campaign:
  - `timed` (default): every `campaign.objective_period_min` (PROPOSED 15 min) the system picks one frontline node (own `objective` RNG stream, Q-SM-1) and announces it with a timer. Completing it gives a merit bonus.
  - `relaxed`: fewer, longer, untimed suggestions.
  - `off`: sandbox/creative, no system objectives.

  Admins and GMs can also set objectives. Whenever an objective exists it is visible on screen.
- **Victory (Domination):** hold ≥ `campaign.victory_node_frac` (PROPOSED 0.80) of strategic nodes for `campaign.victory_hold_min` (PROPOSED 30 min) continuously, **or** capture the enemy HQ. The rubber-band zone is tuned to 55–75% so that victory sits beyond it.
- **Defeat (Q-GD-7):** the coalition loses its forward airbase **and** holds ≤ 25% of strategic nodes for 30 min continuously. The sanctuary base can never be captured.
- **Campaign clock:** 48 h target (admin-adjustable, schedulable per campaign, Q-GD-5). It **never pauses for lack of humans** (Q-GD-4 amended): at 0 humans the Static drops to Pattern of Life (THREAT-DIRECTOR §5a). Only a sim pause with a reason stops the clock: an operator pause (ADMIN-RBAC pause flow), the auto-pause when the broadcast has been offline longer than `ops.offline_pause_after_min` (reason TECHNICAL, Q-OPS-8), the weekly maintenance window, or the owner's Ceasefire mode (Q-OPS-9). Sim-time timers freeze with it (Q-CFG-8).
- **Time limit (Q-GD-29):** hitting the time limit decides by score = node share over time + completed objectives. If the two sides' scores are within a draw band (PROPOSED ~5%), the war ends in a **Stalemate**: its own end screen and no carry-over bonus (§9b). A stalemate may trigger a configured special event, and the Static mastermind delivers template-based banter.
- **End of campaign (Q-UX-8, Q-UX-4):** a victory or "SIGNAL LOST" moment (optional configurable zoom on the final action), a ~5-minute after-action review (top operators per role, best rescue, the "what you didn't see" reveal with the seed, Q-CT-2), then a looping War Briefing card during the intermission. Advancement is configurable: `auto_advance` (next war after N min) or `await_owner` (one-tap owner approval). The next theater rotates archetypes with no back-to-back repeat, reusing the first theater with a new seed until more exist (Q-SM-4).
- **Units reset each war** (Q-GD-23); rank, callsign, cosmetics and stats persist. **Survivor reward:** an operator whose unit is alive at war end and who completed ≥ 1 mission that war gets a Survivor ribbon, a merit bonus and a forward-base first deploy next war (no stat boost; configurable).

## 9a. Theater style and orientation (owner, 2026-10-17)
- **Theater variety is a design goal (owner, 2026-10-17).** Water-heavy theaters (straits, archipelagos, large islands) are common, but land theaters are just as welcome: desert ops, mountain passes, urban districts, plains. Rotating between them forces chat to adapt. A crowd used to seaports must rethink tactics in a desert with no naval option. Theater archetypes change which domains, nodes and supply routes matter. Rotation avoids repeating the same archetype twice in a row (proposed rule; PROPOSED, admin-configurable).
- **Theater #1 (Q-GD-33):** a land-leaning map with a bridged strait, so the water theme works before naval units arrive (P3).
- **Orientation:** the coalition (chat) is always on the **left (west)**, the enemy on the **right (east)**, and the main axis of advance runs left → right. Theater files must declare `orientation: west_to_east`, and the theater validator rejects maps whose sanctuary isn't in the left third. For the vertical 9:16 layout, see Q-GD-13.
- **Urban terrain** needs extra rules (line-of-sight blocking, slower ground movement, capture by district). This is new design work, NX-129.

## 9b. Campaign carry-over (owner chose: results carry over)
The outcome of campaign N affects campaign N+1, within bounded and visible rules (Q-GD-12). Carry-over state is stored in the DB (DATA-MODEL addition: `campaign_carryover`) and applied at campaign setup. It's never applied mid-campaign.

## 9c. Theme vs strategy rule (owner, 2026-10-17)
The signal and Static theme is a **presentation layer over the strategy game, never a replacement for it**:
- **TS-1:** Chat volume and viewer count never directly buff, nerf or decide anything. Outcomes come only from units, logistics, fog of war and the director rules. (The director already scales on coalition *units and supply*, not on chat activity.) Supply-drop redemptions therefore have a fixed global hourly cap (`support.supply_drop.max_per_hour`, PROPOSED/TBD by harness) plus a shared cooldown, independent of audience size (Q-SUP-7, SUPPORT-REDEMPTIONS).
- **GM scope (Q-AI-8):** a human GM drives the Static and triggers world events only. A world event may help the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction. A GM never grants units, ammo or XP to specific players. Every GM action is logged and flagged in replays.
- **TS-2:** "Momentum" stays a strategic measure (nodes, stock, recent events). Any "signal strength" visuals are cosmetic flavor on top of it: map color brightness, static overlay intensity, sound.
- **TS-3:** The game must play well at **0 viewers** (AI garrison + Pattern of Life, Q-GD-4 amended) and scale smoothly upward. No mechanic may require a minimum crowd.
- **TS-4:** Lore names (The Static, Relays, etc.) relabel things on screen and in sitreps only. Mechanics and their docs keep plain names (node, unit, supply).

## 10. Readability rules (stream-facing)
Always visible: the momentum bar, the current objective with its timer, the director threat level, and a "how to play" line. Everything else (NEEDED jobs, reserve queue, operator breakdown, explainer) shares one rotating panel or appears as short interrupt toasts; at 9:16 the threat level joins the rotation (Q-UX-11, OVERLAY). A newcomer must be able to tell who's winning within 5 s (alpha exit criterion).

## 11. Test plan
Every rule above gets a unit test plus the property tests from TESTING-STRATEGY §3.1. Balance scenarios are defined in the harness. Tasking Board assignment (TB-5) gets a replay determinism test, and pause tests check that sim-time timers freeze (Q-CFG-8).
