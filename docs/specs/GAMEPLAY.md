# SPEC: Gameplay Rules


> **All numeric values in this spec are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). They become real only after the balance harness validates them.
Status: Draft · Tracker: NX-120…NX-149 · Inputs: Raw plans P206–225, P983–1009, P1139–1168; conversation C1–C48

All numbers below are **initial balance values** in `balance/default.yaml`. They're tuned with the balance harness, not hard-coded.

## 1. Core loop (what a viewer does in 30 s)
1. Type `!join strike|recon|logi`. Within 500 ms (server side) a radar ping and their callsign appear at a base.
2. The unit auto-routes to the **current theater objective**, which is always on screen.
3. Optionally type `!target <node>` or `!rtb`.
4. The unit completes or fails its mission, and the viewer sees a contribution line in the ticker.

## 0. Parity rule (owner, 2026-10-17)
**Both sides play by the same rules.** The Static has the same mechanics as Clearwave: scouting, fog of war (FOW-4), supply and starvation, rebasing, damage states, ammo, and rescue/recovery where it applies. Any new mechanic must say how it applies to both sides, or explicitly justify an asymmetry (e.g. the sanctuary base) in its spec.

## 1a. "Did my command work?" feedback (owner requirement, Q-MOD-1)
Viewers see a generated callsign, not their username, so the game must connect "me" to "my unit" unmistakably. Otherwise they assume nothing happened and leave.
- **FB-UX-1 Chat confirmation:** the bot's batched digest names the platform user and their callsign, e.g. "@SaltyUser → VIPER-27 deployed (strike) from WEST BASE". It's sent within platform rate limits (Twitch as a moderator: 100 messages / 30 s, per PLATFORM-REALITY-CHECK), with up to N mentions per digest message (N PROPOSED).
- **FB-UX-2 On-screen recruit strip:** for 10 s after each spawn, a "NEW RECRUITS" strip shows the callsign, platform icon and role, with a ping on the map at the spawn point.
- **FB-UX-3 `!me`:** highlights your unit for 5 s, and the next chat digest repeats your callsign and status. Also works while you're in the reserve queue (shows your position).
- **FB-UX-4 First-time hint:** a commander's first successful command adds a one-time "New? You're VIPER-27. Type !me anytime." line to the digest.
- **FB-UX-5 Rejections are visible too.** Reasons like "unit in sortie" or "respawn in 12 s" are batched into the digest with the callsign, never silently dropped.
- **FB-UX-6 Measure it:** track the share of first-time commanders who issue a second command (NX-036). A low value means the feedback isn't working.

## 2. Roles (MVP, resolves critique #7 and #8)
| Role | Command | Domain | Does | Can't |
|---|---|---|---|---|
| Strike | `!join strike` | AIR | Attacks ground/air targets; suppresses SAMs poorly without SEAD | Capture nodes |
| Recon | `!join recon` | AIR | Large sensor radius; converts SIGINT blobs to tracks; paints targets | Deal damage |
| Logistics | `!join logi` | GROUND | Carries supply along roads to nodes; captures uncontested nodes slowly | Fight |
| Naval | `!join navy` | SEA | P4 (Q-GD-8) | — |

Specialist chassis (SEAD, jammer, engineer, AWACS, artillery) unlock with rank (PROGRESSION). **Specialist doctrines** are chosen once per campaign and lock (Q-GD-3).

## 3. Commands (single source of truth)
| Command | Args | Min rank | Notes |
|---|---|---|---|
| `!join <role>` | role | O-1 | Spawns your one unit, or switches role if your unit is at base |
| `!target <node>` | node name/alias (fuzzy match against a fixed list) | O-1 | Sets your unit's objective |
| `!rtb` | — | O-1 | Return to the nearest friendly base |
| `!stance <press\|standard\|cautious>` | stance | O-1 | Standing intent for your unit: `press` = keep fighting even when badly damaged; `standard` = auto-RTB at mission-kill (default); `cautious` = RTB as soon as Damaged; `guns` = keep fighting with guns after missiles/bombs run out (default is auto-RTB when out of munitions). Can also be given at deploy: `!join strike press` (Q-CBT-6). |
| `!rebase <node>` | friendly node | O-1 | Move your unit to another friendly base and stay there to refuel/rearm/stage (e.g. move a plane forward before an attack). Uses that base's stock. The Static does the same (THREAT-DIRECTOR §5a). |
| `!status` | — | O-1 | Overlay highlights your unit for 5 s; no chat reply |
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
- **GP-2** After death, respawn is allowed after `slots.respawn_delay_s` (PROPOSED 20 s) to stop suicide spam.
- **GP-3** Above `slots.max_viewer_units` (Q-GD-6) new joiners go to a visible reserve queue. The queue is served FIFO as slots free up.

## 4a. Reserve-queue mitigations (Q-GD-6 decided with mitigations)
- **RQ-1:** show the queue length on the HUD. Each queued viewer gets their position via the digest or `!me`.
- **RQ-2: Dynamic cap.** `slots.max_viewer_units` is a ceiling. The runtime may lower the effective cap while tick time is over budget, and raises it back when there's headroom (logged, visible on the ops dashboard).
- **RQ-3: Units merge into flights before anyone queues.** Joiners attach to existing human flights as wingmen (sharing one map symbol) before the queue is used. Only when every flight is full does the queue start.
- **RQ-4: Queued viewers still contribute.** While waiting they can `!scout <sector>`, a cheap intel ping that reveals SIGINT detail briefly, and they earn a small participation merit (PROPOSED values, diminishing).
- **RQ-5: Priority and fairness.** Q-GD-14: FIFO, with a boost for first-time commanders and a max-wait guarantee. Idle units auto-despawn (`slots.idle_despawn_s`) to free slots.

## 5. Logistics (resolves critique #13)
- Nodes hold `stock` (0..max). Spawning or rearming at a node consumes stock according to the unit's loadout cost.
- **Sources:** the SANCTUARY base has infinite stock but is far away. A FACTORY generates `logistics.factory_rate` per minute, but only while it's connected by owned roads to the sanctuary.
- **Starvation:** below `logistics.starve_threshold` (PROPOSED 25%) units spawn with reduced loadouts (50% fuel, guns only). At 0, the node can't rearm.
- Logi trucks carry `cargo`, drive the road graph (A* over ROAD edges, cost = length / speed_mult), and unload over time at the destination.
- **Bridges** are nodes with HP. A destroyed bridge removes its edge until it is repaired. Who can repair it, and how fast, is open question Q-GD-11.
- **Supply-line stretch** (snowball breaker): coalition truck transit time scales with road distance from the sanctuary. Enemy reinforcement time shrinks as the front nears its HQ.
- Units heal and rearm **only while landed or parked at a friendly node**, by spending stock. They never heal passively (fixes the immortality bug).
- **Empty bases stay bases** (Q-GD-17): at 0 stock, units can still land, garrison and wait there for a resupply convoy. They get no fuel or ammo, but keep what they have and can take off again with reduced endurance.

## 5a. Base upgrades (P4; extension point reserved now)
Owner idea: sending **surplus supply** to a base gradually upgrades it: a radar site gains range, an air-defense site gains faster interceptors, an airbase rearms quicker. Upgrades decay or are lost if the base is starved or captured.
- **Reserved now so it doesn't need a rewrite later:** nodes carry `tier: int` and `upgrades: [UpgradeId]` in the world model, and all node stats are read through a modifier layer (base stats × tier/upgrade modifiers from config). The MVP ships with tier 0 and no upgrades.

## 6. Combat
- Each tick, a unit with a ready weapon chooses the **highest-priority valid target** in range: by domain compatibility, then threat, then distance, with a stable tie-break by id.
- Hit probability = `base_pk × track_quality_mult × evasion_mult`, rolled on the `combat` RNG. Track quality depends on FoW tier: blob 0.2, track 1.0, painted 1.25.
- SAMs have engagement rings. Jammers reduce enemy pk within their corridor. SEAD missiles home on emitting radars, and radars may go dark ("blink") to avoid them.
- Kills and assists generate events. A recon "paint" grants assist credit (PROGRESSION).

## 6a. Platform attributes, disabled units, crew and CSAR (owner, 2026-10-17)
- **Per-platform attributes** (unit catalog, CONFIG §7/§7a; all PROPOSED): armor level per facing or generic, maneuverability/evasion, speed per terrain type (road, off-road, sand, mountain, urban, water), sensor and weapon profiles, countermeasures, crew count. Hot-loaded platforms define these too, inside the stat envelope.
- **Damage states:** Healthy → Damaged → Mission-kill → **Disabled** (can't move, not destroyed) → Destroyed (Q-CBT-1). Armor shifts the chances between these outcomes.
- **Crew survival:** when a unit is disabled or shot down, a seeded crew-survival roll (modified by platform and location) decides whether the crew is alive. The crew is shown on the map as a downed-crew marker. *Working name "crew"; a playful mascot name is possible under the brand guide.*
- **CSAR (combat search and rescue):** operators can mount a rescue (`!rescue <marker>`) with suitable units: helicopters or ground vehicles once those exist, recon for spotting. Successful rescues give a **large XP and merit bonus** to the rescuers and recover the crew. The Static may try to capture downed crews, which sets up a race. Disabled vehicles can also be recovered or repaired in place by engineers or logistics.
- **Consequences without punishment** (Q-CBT-9): losses cost the *team* (base stock spent, a longer respawn for that unit type) rather than taking XP from the player.

## 7. Packages (formations)
A package is a group of up to 4 existing units, with a lead (O-5+) or an auto-lead. It shares the lead's target and gives a small jamming/escort benefit plus an XP share bonus. **There is no lobby wait.** Units join as they spawn. If fewer than 2 humans are in the package after 30 s, an NPC wingman may fill a slot (Q-GD-10).

## 8. Capture
- **Base defenses first (Q-GD-18):** each node has defense HP (configurable, upgradable via §5a). Capture can't begin until HP is 0. Air strikes, artillery and ground fire reduce HP; supply deliveries repair it; starvation slowly drains it (`logistics.starve_hp_drain_per_min`, PROPOSED).
- Capture requires a ground or logistics unit within `capture.radius_m`, with no enemy ground unit contesting it. Progress takes `capture.time_s` (PROPOSED 120 s), scaled by the number of units with diminishing returns. Air units can't capture.
- Progress decays when the node is uncontested and unoccupied. A capture can't flip twice in one tick (property test).

## 9. Campaign, objectives, win/loss (resolves critique #12)
- **Modes:** Total Domination (MVP), Hold the Line (P4), Siege / AI-holds-out (backlog, Q-GD-2).
- **Theater objective:** every 15 min the system picks one node, weighted by its frontline position, and announces it with a timer. Completing it gives a merit bonus. It's always visible.
- **Victory (Domination):** hold ≥ `campaign.victory_node_frac` (PROPOSED 0.80) of strategic nodes for `campaign.victory_hold_min` (PROPOSED 30 min) continuously, **or** capture the enemy HQ. The rubber-band zone is tuned to 55–75% so that victory sits beyond it.
- **Defeat:** Q-GD-7.
- **Campaign clock:** 48 h target. It pauses when active humans are below 1 (Q-GD-4). Hitting the time limit decides by score.
- **End of campaign:** a 5-minute after-action review (top contributors per role, campaign stats), then a new seed or theater.

## 9a. Theater style and orientation (owner, 2026-10-17)
- **Theater variety is a design goal (owner, 2026-10-17).** Water-heavy theaters (straits, archipelagos, large islands) are common, but land theaters are just as welcome: desert ops, mountain passes, urban districts, plains. Rotating between them forces chat to adapt. A crowd used to seaports must rethink tactics in a desert with no naval option. Theater archetypes change which domains, nodes and supply routes matter. Rotation avoids repeating the same archetype twice in a row (proposed rule; PROPOSED, admin-configurable).
- **Orientation:** the coalition (chat) is always on the **left (west)**, the enemy on the **right (east)**, and the main axis of advance runs left → right. Theater files must declare `orientation: west_to_east`, and the theater validator rejects maps whose sanctuary isn't in the left third. For the vertical 9:16 layout, see Q-GD-13.
- **Urban terrain** needs extra rules (line-of-sight blocking, slower ground movement, capture by district). This is new design work, NX-129.

## 9b. Campaign carry-over (owner chose: results carry over)
The outcome of campaign N affects campaign N+1, within bounded and visible rules (Q-GD-12). Carry-over state is stored in the DB (DATA-MODEL addition: `campaign_carryover`) and applied at campaign setup. It's never applied mid-campaign.

## 9c. Theme vs strategy rule (owner, 2026-10-17)
The signal and Static theme is a **presentation layer over the strategy game, never a replacement for it**:
- **TS-1:** Chat volume and viewer count never directly buff, nerf or decide anything. Outcomes come only from units, logistics, fog of war and the director rules. (The director already scales on coalition *units and supply*, not on chat activity.)
- **TS-2:** "Momentum" stays a strategic measure (nodes, stock, recent events). Any "signal strength" visuals are cosmetic flavor on top of it: map color brightness, static overlay intensity, sound.
- **TS-3:** The game must play well at **0 viewers** (AI garrison + slow war, Q-GD-4) and scale smoothly upward. No mechanic may require a minimum crowd.
- **TS-4:** Lore names (The Static, Relays, etc.) relabel things on screen and in sitreps only. Mechanics and their docs keep plain names (node, unit, supply).

## 10. Readability rules (stream-facing)
Always visible: the momentum bar, the current objective with its timer, the director threat level, and a "how to play" line. A newcomer must be able to tell who's winning within 5 s (alpha exit criterion).

## 11. Test plan
Every rule above gets a unit test plus the property tests from TESTING-STRATEGY §3.1. Balance scenarios are defined in the harness.
