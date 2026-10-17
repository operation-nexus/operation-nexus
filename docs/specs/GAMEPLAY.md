# SPEC: Gameplay Rules

Status: Draft · Tracker: NX-120…NX-149 · Inputs: Raw plans P206–225, P983–1009, P1139–1168; conversation C1–C48

All numbers below are **initial balance values** in `balance/default.yaml`. They're tuned with the balance harness, not hard-coded.

## 1. Core loop (what a viewer does in 30 s)
1. Type `!join strike|recon|logi`. Within 500 ms (server side) a radar ping and their callsign appear at a base.
2. The unit auto-routes to the **current theater objective**, which is always on screen.
3. Optionally type `!target <node>` or `!rtb`.
4. The unit completes or fails its mission, and the viewer sees a contribution line in the ticker.

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
| `!status` | — | O-1 | Overlay highlights your unit for 5 s; no chat reply |
| `!callsign <NAME>` | `^[A-Z][A-Z0-9-]{2,11}$`, moderated | O-2 | Reserve a global callsign |
| `!vector <bearing> <km>` | ints | O-2 | Manual waypoint from your unit |
| `!sead`, `!himars`, `!engineer`, `!jammer`… | — | per PROGRESSION | Specialist spawns |
| `!package <NAME>` / `!wingman` | — | O-5 / O-1 | Form or join a formation (§7) |
| `!doctrine <name>` | — | O-3 | Once per campaign |
| `!order <text>` | free text ≤ 200 chars | O-3 | **P4**, LLM-parsed, own unit only |
| `!forget` | — | any | Data deletion request (SEC-DATA-3) |

Unknown commands and ordinary chat are ignored. Command aliases are configurable.

## 4. Unit slots
- **GP-1** Each commander has at most **one live personal unit**. `!join` while your unit is alive retargets or switches it only if it's at a base. Otherwise you get the reply "unit in sortie".
- **GP-2** After death, respawn is allowed after `respawn_delay_s` (default 20 s) to stop suicide spam.
- **GP-3** Above `max_viewer_units` (Q-GD-6) new joiners go to a visible reserve queue. The queue is served FIFO as slots free up.

## 5. Logistics (resolves critique #13)
- Nodes hold `stock` (0..max). Spawning or rearming at a node consumes stock according to the unit's loadout cost.
- **Sources:** the SANCTUARY base has infinite stock but is far away. A FACTORY generates `factory_rate` per minute, but only while it's connected by owned roads to the sanctuary.
- **Starvation:** below `starve_threshold` (default 25%) units spawn with reduced loadouts (50% fuel, guns only). At 0, the node can't rearm.
- Logi trucks carry `cargo`, drive the road graph (A* over ROAD edges, cost = length / speed_mult), and unload over time at the destination.
- **Bridges** are nodes with HP. A destroyed bridge removes its edge until an engineer repairs it.
- **Supply-line stretch** (snowball breaker): coalition truck transit time scales with road distance from the sanctuary. Enemy reinforcement time shrinks as the front nears its HQ.
- Units heal and rearm **only while landed or parked at a friendly node**, by spending stock. They never heal passively (fixes the immortality bug).

## 6. Combat
- Each tick, a unit with a ready weapon chooses the **highest-priority valid target** in range: by domain compatibility, then threat, then distance, with a stable tie-break by id.
- Hit probability = `base_pk × track_quality_mult × evasion_mult`, rolled on the `combat` RNG. Track quality depends on FoW tier: blob 0.2, track 1.0, painted 1.25.
- SAMs have engagement rings. Jammers reduce enemy pk within their corridor. SEAD missiles home on emitting radars, and radars may go dark ("blink") to avoid them.
- Kills and assists generate events. A recon "paint" grants assist credit (PROGRESSION).

## 7. Packages (formations)
A package is a group of up to 4 existing units, with a lead (O-5+) or an auto-lead. It shares the lead's target and gives a small jamming/escort benefit plus an XP share bonus. **There is no lobby wait.** Units join as they spawn. If fewer than 2 humans are in the package after 30 s, an NPC wingman may fill a slot (Q-GD-10).

## 8. Capture
- Capture requires a ground or logistics unit within `capture_radius`, with no enemy ground unit contesting it. Progress takes `capture_time_s` (default 120 s), scaled by the number of units with diminishing returns. Air units can't capture.
- Progress decays when the node is uncontested and unoccupied. A capture can't flip twice in one tick (property test).

## 9. Campaign, objectives, win/loss (resolves critique #12)
- **Modes:** Total Domination (MVP), Hold the Line (P4), Siege / AI-holds-out (backlog, Q-GD-2).
- **Theater objective:** every 15 min the system picks one node, weighted by its frontline position, and announces it with a timer. Completing it gives a merit bonus. It's always visible.
- **Victory (Domination):** hold ≥ `victory_node_pct` (default 80%) of strategic nodes for 30 min continuously, **or** capture the enemy HQ. The rubber-band zone is tuned to 55–75% so that victory sits beyond it.
- **Defeat:** Q-GD-7.
- **Campaign clock:** 48 h target. It pauses when active humans are below 1 (Q-GD-4). Hitting the time limit decides by score.
- **End of campaign:** a 5-minute after-action review (top contributors per role, campaign stats), then a new seed or theater.

## 10. Readability rules (stream-facing)
Always visible: the momentum bar, the current objective with its timer, the director threat level, and a "how to play" line. A newcomer must be able to tell who's winning within 5 s (alpha exit criterion).

## 11. Test plan
Every rule above gets a unit test plus the property tests from TESTING-STRATEGY §3.1. Balance scenarios are defined in the harness.
