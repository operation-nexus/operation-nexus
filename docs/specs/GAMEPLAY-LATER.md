# SPEC: Gameplay (later phases)

Status: Parked (not part of the SIM-CORE / GAMEPLAY approval) · Tracker: NX-120…NX-149 and the P3/P4 items named below · Split from [GAMEPLAY](GAMEPLAY.md) on 2026-10-18 (Q-GP-1)

> **All numeric values here are PROPOSED and unvalidated** (DATA-INTEGRITY DI-7). Nothing in this file is built before its phase. Section numbers match GAMEPLAY so existing references still resolve. GAMEPLAY §0 (parity) applies: any rule here must say how it applies to both sides.

## 3. Later-phase commands
Design notes for the reserved commands; the list itself, intents and phases are in [COMMAND-CATALOG](COMMAND-CATALOG.md) §3.

| Command | Args | Min rank | Notes |
|---|---|---|---|
| `!stance <press\|standard\|cautious\|guns>` | stance | O-1 | Standing intent for your unit: `press` = keep fighting even when badly damaged; `standard` = auto-RTB at mission-kill (default); `cautious` = RTB as soon as Damaged; `guns` = keep fighting with guns after missiles/bombs run out (default is auto-RTB when out of munitions). Can also be given at deploy: `!join strike press` (Q-CBT-6). |
| `!rally <node> <attack\|defend\|supply>` | node + intent | O-3 | Templated rally call: map pin + banner with your callsign, cooldown. Informs only, never controls other units. Support can make it more prominent, never more powerful (Q-SUP-6) |
| `!rescue <marker>` | downed-crew marker | O-1 (needs a suitable unit) | Mount a CSAR mission (§6a) |
| `!vector <bearing> <km>` | ints | O-2 | Manual waypoint from your unit |
| `!sead`, `!artillery`, `!engineer`, `!jammer`, `!awacs` | — | per PROGRESSION | Specialist spawns |
| `!package <NAME>` / `!wingman` | — | O-5 / O-1 | Form or join a formation (§7) |
| `!doctrine <name>` | — | O-3 | Once per campaign |
| `!order <text>` | free text ≤ 200 chars | O-3 | **P4**, LLM-parsed, own unit only |

## 4a. Flights and wingmen (RQ-3)
> Following a unit (`!target <callsign>`, GAMEPLAY §1b, Q-GP-31) already covers positioning in the first build; flights and packages add only a shared target, a shared map symbol and an XP share. Deploy-time stance (`!join strike press`) must fit the `!join` grammar when stances return.
- **RQ-3 (P4, ships with packages §7; Q-GD-36): Units merge into flights before anyone queues.** Joiners attach to existing human flights as wingmen (sharing one map symbol) before the queue is used. Only when every flight is full does the queue start. The alpha uses the plain reserve queue only.

## 5a. Base upgrades
> Upgrades come only from player actions, never from AI (Q-TD-11); this includes AI garrison units and facilities. (P4; extension point reserved now)
Owner idea: sending **surplus supply** to a base gradually upgrades it: a radar site gains range, an air-defense site gains faster interceptors, an airbase rearms quicker. Upgrades decay or are lost if the base is starved or captured.
- **Reserved now so it doesn't need a rewrite later:** nodes carry `tier: int` and `upgrades: [UpgradeId]` in the world model, and all node stats are read through a modifier layer (base stats × tier/upgrade modifiers from config). The MVP ships with tier 0 and no upgrades.

## 6a. CSAR (combat search and rescue)
- **CSAR (combat search and rescue):** operators can mount a rescue (`!rescue <marker>`) with suitable units: helicopters or ground vehicles once those exist, recon for spotting. Successful rescues give a **large XP and merit bonus** to the rescuers and recover the crew. The Static may try to capture downed crews, which sets up a race. Disabled vehicles can also be recovered or repaired in place by engineers or logistics.

## 7. Packages (formations)
A package is a group of up to 4 existing units, with a lead (O-5+) or an auto-lead. It shares the lead's target and gives a small jamming/escort benefit plus an XP share bonus. **There is no lobby wait.** Units join as they spawn. If fewer than 2 humans are in the package after 30 s (game time, Q-ALN-23), an NPC wingman may fill a slot (Q-GD-10).

## 9. Campaign modes and rewards
- **Modes:** Total Domination (MVP), Hold the Line (P4; ends after N escalating waves or a time limit, Q-GD-15), Siege / AI-holds-out (backlog, Q-GD-2).
- **Survivor reward:** an operator whose unit is alive at war end and who completed ≥ 1 mission that war gets a Survivor ribbon, a merit bonus and a forward-base first deploy next war (no stat boost; configurable).

## 9a. Theater variety and urban terrain
- **Theater variety is a design goal (owner, 2026-10-17).** Water-heavy theaters (straits, archipelagos, large islands) are common, but land theaters are just as welcome: desert ops, mountain passes, urban districts, plains. Rotating between them forces chat to adapt. A crowd used to seaports must rethink tactics in a desert with no naval option. Theater archetypes change which domains, nodes and supply routes matter. Rotation avoids repeating the same archetype twice in a row (proposed rule; PROPOSED, admin-configurable).
- **Urban terrain** needs extra rules (line-of-sight blocking, slower ground movement, capture by district). This is new design work, NX-129.

## 9b. Campaign carry-over (owner chose: results carry over)
The outcome of campaign N affects campaign N+1, within bounded and visible rules (Q-GD-12). Carry-over state is stored in the DB (DATA-MODEL addition: `campaign_carryover`) and applied at campaign setup. It's never applied mid-campaign.

## Moved from the first-build review (Q-GP-9, Q-GP-10, 2026-10-18)
Text as it stood in GAMEPLAY before the move. Wire-level fallout was removed from CONTRACTS and the other specs in the same PR; a feature returns with its schema.

- **`!scout <sector>` (command, moved):** sector argument, any rank, only while in the reserve queue. A cheap intel ping while waiting (RQ-4).
- **RQ-4: Queued viewers still contribute.** While waiting they can `!scout <sector>`, a cheap intel ping that reveals SIGINT detail briefly, and they earn a small participation merit (PROPOSED values, diminishing).
- **RQ-5: Priority and fairness.** Q-GD-14: FIFO, with a boost for first-time commanders and a max-wait guarantee. A silent commander's unit frees its slot only when it retires (GP-5); while handed off (AUTO, GP-4) it still occupies that slot (Q-ALN-8, Q-ALN-9). There is no other idle despawn.
- **Supply-line stretch** (snowball breaker): coalition truck transit time scales with road distance from the sanctuary. Enemy reinforcement time shrinks as the front nears its HQ.
- **Critical hits (Q-CBT-8):** a small seeded chance of an outsized effect (e.g. a radar knocked offline for a while), shown with a callout. Configurable.
- **Friendly fire (Q-CBT-4):** off in v1. It is a per-campaign option set at campaign setup (never toggled mid-war), default off, editable by the owner or an Admin only, never by a GM (Q-ALN-10).
- **Relaxed objective mode (Q-GD-19, moved):** fewer, longer, untimed suggestions.

- **Stalemate (Q-GD-29, moved):** if the two sides' scores are within a draw band (PROPOSED ~5%), the war ends in a Stalemate with its own end screen, no carry-over bonus, an optional configured special event and template banter from the Static mastermind.
- **Engineer crossings (Q-GD-21, moved):** engineers can build short new crossings.

## Deferred from the first build (Q-CBT-20, 2026-10-20)
Each item must come back with the tracker item named here, whose acceptance names it. Owner: none of these may be dropped.

| Item | Interim in the first build | Returns with |
|---|---|---|
| Radar lock (track-quality factor) | 1.0, FB-6 | NX-362 |
| Countermeasures (chaff/flares) | 1.0, FB-6 | NX-362 |
| Jamming | 1.0, FB-6 | NX-212 (jammer chassis) |
| Field repair of Disabled units | none; wrecks removed after `combat.disabled_timeout_s` (COMBAT CB-7) | NX-290, with the engineer specialist (NX-212): quicker, dedicated repair |
| Dynamic threat score | fixed per-kind `threat` | Q-CBT-17, grilled after the P1 balance runs |
| `SPAWN_SPECIALIST` command | reserved, no schema or handler (Q-CMD-2) | NX-212 |
| Unlimited campaign length | `campaign.time_limit_h` plus logged extensions (Q-TEST-7) | Revisit after harness runs show how campaigns stall |

## Future candidates (tracked, not designed)
- **Map that grows inside a campaign (Q-GP-22):** the playable area starts as a small sector and new sectors unlock as the coalition pushes. Only if feedback is overwhelming.
- **More facility kinds (Q-GP-21):** facilities attach to bases, so new kinds can be added over time, such as missile-interception defense systems. These pair with projectiles as entities (Q-GP-7 option C).
- **Factories (Q-GP-41, parked):** a FACTORY facility adds `logistics.factory_rate` per minute to its base's stock. Returns if single-source convoys prove too slow in playtests.
- **Emission control with SEAD (Q-FOW-10):** both sides' AI turns a radar or air-defense site dark when an anti-radiation missile is detected inbound and resumes after a cooldown; a rank-gated player command to blink a friendly site may come with it.
- **Dynamic track quality in flight (owner, 2026-10-19):** track quality should not be fixed when a shot is fired. A fleeing target can outrun a munition depending on the weapon's range, and jamming or other interference can raise or lower track quality while the munition flies. Not implemented in the first build; see COMBAT CB-3 for the interim rule.
- **CHARLIE tier (Q-TD-3, parked):** a named theater offensive (e.g. "Operation Red Tempest") that needs combined arms, telegraphed by visible massing and staging, then an INTEL warning naming the sector (lead time PROPOSED ~10 min of game time, Q-GD-22, Q-ALN-35), only after real provocation and never against an empty stream. Brings back the `TheaterOffensive` operation and `director.tier.charlie_enter_cp`. The `sead_activity` memory counter and counter-battery return with SEAD and artillery (P4).
