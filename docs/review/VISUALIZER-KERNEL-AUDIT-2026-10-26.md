# Visualizer suggestions vs the sim kernel (2026-10-26)

The visualizer session (NX-176; PRs #328, #341, #342, #357, #359) wrote RFCs, a skill, a prototype and overlay types that assume things about the simulation kernel. The owner asked that every kernel-affecting suggestion be checked against the real code and specs, and that none of it be taken as authoritative. This file records the check. A read-only Opus agent made the first pass. The lead re-checked the load-bearing facts against the files: `sim.time_scale` 6.0, the `painted` multiplier 1.25, the band set NOE/LOW/MED/HIGH with the strike fighter fixed at MED, `WeaponImpact`'s fields, and the drifted overlay types.

**Kernel facts the visualizer docs get wrong**
- The kernel is 2D: `Vec2` position and velocity (`world.py`), with no height, vertical speed, attitude or airspeed.
- Masking is a per-area flag, not line of sight (Q-FOW-3; `fog.py`).
- The air bands are `NOE`, `LOW`, `MED` and `HIGH`, fixed per unit kind (Q-CBT-11). There are no metre thresholds, and the strike fighter's allowed bands are LOW, MED and HIGH, flying at MED.
- One 10 Hz tick is 0.6 s of game time (`sim.time_scale` 6.0). Every 60 Hz formula and every "realistic speed" claim in those docs assumes 1x.

## Verdicts

| ID | Suggestion | Verdict |
|---|---|---|
| V-1 | Altitude bands with metre thresholds | Bands exist, but the names and thresholds in the RFC are invented |
| V-2 | Aircraft drop to NOE for canyon runs | Conflicts with Q-CBT-11: no command changes the band, and a strike fighter can't fly NOE (see Q-VIZ-4) |
| V-3, V-4 | Terrain-grid line-of-sight masking from a `.bin` DEM loaded by the kernel | Conflicts with Q-FOW-3 and Q-CFG-3. The heightmap is a PNG, and nothing in the first build reads height. A compatible version is Q-VIZ-1 |
| V-5 | Gradient and biome speed penalties | Already possible: each edge has an authored `speed_mult`, so gradient can be baked into it offline. Biomes do nothing in the kernel, because ground units move only on the road graph |
| V-6 | Junction or abutment nodes for curved roads | A real gap, but the wrong mechanism (nodes are capturable). See Q-VIZ-2 |
| V-7, V-8, V-9 | Bridge span cut, A* routing, a 10 Hz kernel | Already built (`bridges.py`, `roads.py`, ADR-0002) |
| V-10 | 6-DOF attitude, G-load, weaving | Renderer only. The renderer must smooth the one-tick turns at waypoints, and must never draw a unit away from its sim position (OV-7, DI-1) |
| V-11 | Altitude, `vz`, roll, pitch, G and `isTerrainMasked` as sim output | Invented. `EntityView` has x, y, heading and speed only. See Q-VIZ-3 |
| V-12 | A "masked" or "exposed" HUD flag | Exists honestly as FOW-12 `spotted` for own units. A masked flag would leak where enemy sensors are |
| V-13 | Fuel % in HUDs | `Entity.fuel` exists in world seconds and isn't on the wire. See Q-VIZ-3 |
| V-14 | `TargetPainted`, Pk ×1.6, a `TRACK_LOST` impact cause | The painted flag exists. The multiplier is **1.25** (COMBAT). `TargetPainted` is specified in CONTRACTS §6 but not built, and `WeaponImpact` has no `cause`. A miss follows from the shooter side having no track at impact (CB-3) |
| V-15 | Missile entities with seeker POV | Renderer only. A `Shot` has no position. Draw the flight from `WeaponFired` and `impact_tick` |
| V-16 | Re-simulate any campaign years later, bit for bit | Conflicts with Q-SIM-13, Q-SIM-18 and SC-16. Re-simulation works only on the same commit and image, and public replays come from recorded frame streams |
| V-17 | Helicopters, ships, infantry squads, burst speed | Out of scope. None are a `UnitKind`, and the speeds quoted don't match content (the truck does 25 m/s) |
| V-18 | A view of the AI's decision branches and probabilities | The director is rule-based, so no probabilities exist. See Q-VIZ-5 |

## Docs and code that misstate kernel facts

Each visualizer doc below now carries a "Kernel facts check" note pointing here. Those docs are Proposed or Draft and are grilled in the visualization phase. The corrections:
- **SIMULATION-TERRAIN-AND-ROAD-INTEGRATION-RFC:**
  - it calls the kernel 2.5D with line of sight;
  - it invents band names and thresholds;
  - it gives an edge a `length_m` field, which the schema forbids;
  - it cites the wrong tracker items (NX-180 is the palette script, NX-177 is overlay units);
  - it names a `fow` module, which is really `nexus.core.fog`;
  - it quotes 1.3 MB/h, which is a stub floor;
  - it relies on a gitignored terrain bake that is not a registered config input (not in the config hash), plus an unregistered formula fallback.
- **UNIT-POV-AND-COCKPIT-CONTRACTS-RFC:**
  - it says ×1.6; the real value is ×1.25;
  - it uses a `WeaponImpact.cause` field, which doesn't exist;
  - it ties a miss to the scout losing line of sight;
  - it calls `TargetPainted` live;
  - it gives kernel positions an "(x, y, z)" form.
- **`.agents/skills/hiveplex-visualization/references/six-dof-kinematics-and-canyon-runs.md`:** it credits the kernel with terrain sampling, `v_z` and energy.
- **DECOUPLED-RENDERER-ARCHITECTURE:**
  - it names events that don't exist (`MISSILE_INTERCEPT`, `SupplyStarved`, `MastermindTaunt`);
  - its damage states leave out `MISSION_KILL`.
- **DETERMINISTIC-REPLAY-AND-MULTI-CAMERA-CINEMATICS (Draft):**
  - it claims bit-for-bit replay;
  - it quotes the wrong speeds;
  - it says ×1.6.
- **`apps/overlay/src/types/unit.ts` and `telemetry.ts`:** these are hand-copied types that drift from the contracts (AGENTS.md rule 6). Examples: `ENEMY_STRIKE`, `AIR_DEFENSE_SAM` and `CIVILIAN` are not `UnitKind`s; `CRITICAL` stands where `MISSION_KILL` should be; `ThreatLevel` NOMINAL/ELEVATED/CRITICAL is not a contract enum (the contract has `ThreatTier`); `CONDITION_ALPHA` and `CONDITION_BRAVO` stand where `ALPHA` and `BRAVO` should be. Fixed by NX-423 (2026-10-26): the types alias the generated `event.ts` fields.
- **`tools/prototype/unified-visualizer.html`:**
  - its "Real Deterministic Simulation Replay Dataset" is partly invented (the CrewDowned at tick 1540, `JCT-W-PASS` and `RESCUE-01`);
  - movement is scripted, not taken from keyframes;
  - it treats `t` as tick/10 real seconds, but game time is tick × 0.6.
- **`tools/replay/render_cinematic_pass.py`:** it reads no sim data; it only drives the prototype page.
- **TERRAIN-AND-BIOMES:61-65:** it gives biomes gameplay effects, though its own line 27 says that gameplay feedback is missing, and no kernel code reads biomes.

**Side findings:**
- COMBAT.md said band-based aircraft masking was not built, but `fog.py` does it. Fixed in COMBAT.
- The visualizer treats a 3D view as the main stream view, which ADR-0005 doesn't allow (Canvas2D first, Three.js picture-in-picture deferred). See Q-VIZ-6.

## Owner questions
Q-VIZ-1 to Q-VIZ-6 in OPEN-QUESTIONS, each with the lead's recommendation.
