# RFC: Simulation Kernel Integration with Deterministic Terrain & Road Networks

**Document ID**: `RFC-SIM-TERRAIN-001`  
**Target Milestone**: NX-176 / NX-008 Theater Specification  
**Authors**: Hiveplex Core Visualization & Simulation Architecture  
**Status**: PROPOSED

---

## 1. Problem Statement & Motivation

Currently, the Operation Nexus simulation kernel (`services/sim`) treats theater geography as a flat 2D Cartesian plane ($X \in [0, 400\text{km}], Y \in [0, 240\text{km}]$) with simple polygonal masking regions (`northern-hills`, `southern-valley`).

As decoupled 2D/3D visualizers advance into realistic topography, continuous DTED elevation, and conformed road networks, the simulation must remain **authoritative** without visual drift (DATA-INTEGRITY DI-1). Specifically:
1. **Line of Sight (LoS) & Radar Masking**: Radar sites (`RADAR_SITE`) and SAM batteries (`AIR_DEFENSE_SITE`) should evaluate LoS against real terrain elevation rather than rough bounding polygons.
2. **Kinematic Slope Modifiers**: Ground supply convoys should experience realistic speed penalties on uphill grades and mountain passes.
3. **Road Waypoints vs Facilities**: The road network must support intermediate junction waypoints (`kind: JUNCTION`, `kind: ABUTMENT`) so convoys follow curved roads rather than cutting straight lines through mountains.
4. **Bridge Destruction & Chokepoint States**: When a bridge is destroyed, only the crossing span is impassable; approach roads remain usable for flanking or air defense staging.

---

## 2. Deterministic Heightfield Architecture

### 2.1 Pure Mathematical DEM vs Binary DTED
To maintain 100% determinism across simulation platforms (macOS, Linux, CI) without floating-point drift:
1. **Formula-Based Elevation (`sample_strait1_elevation(x, y)`)**:
   - Continuous closed-form harmonic equation combining macro undulations, shoreline bevels, northern ridge peaks ($+903\text{m}$), and submarine trench ($-92\text{m}$).
   - Zero I/O overhead; evaluates in $< 20\mu\text{s}$ per query.
2. **Baked DTED Matrix (`strait-1-dem16.bin`)**:
   - $400 \times 240$ matrix of 16-bit signed integers (resolution $1\text{km} \times 1\text{km}$, $188\text{KB}$ file size).
   - Ingested on simulation startup into an in-memory 1D array (`array('h', buffer)`).
   - $O(1)$ grid elevation lookup:
     $$\text{elev\_m} = \text{dem\_array}[\text{row} \times 400 + \text{col}]$$

### 2.2 Line of Sight (Bresenham Raycast in DEM)
For radar detection between sensor $(x_0, y_0, z_0)$ and target $(x_1, y_1, z_1)$:
1. Step along the ray in $1\text{km}$ increments:
   $$z_{\text{ray}}(t) = z_0 + t \cdot (z_1 - z_0)$$
2. If at any step $z_{\text{ray}}(t) < \text{DEM}(x(t), y(t))$, the target is terrain-masked.
3. Aircraft flying low in the southern valley corridor can hide below radar horizons.

---

## 3. Road Network Graph & Waypoint Integration

### 3.1 Theater YAML Schema Update (Proposed)
Add Class B non-facility nodes to `content/theaters/strait-1.yaml`:
```yaml
nodes:
  # Class A: Strategic Facilities & POIs
  - { id: haven, name: "Haven Sanctuary", kind: SANCTUARY, pos: [20000,120000], start_owner: COALITION }
  - { id: west-airbase, name: "West Airbase", kind: AIRBASE, pos: [90000,120000], start_owner: COALITION }
  - { id: fob-n-w, name: "FOB North-West", kind: FOB, pos: [130000,60000], start_owner: COALITION }

  # Class B: Road Waypoints & Shoreline Abutments (Zero garrison quota, zero production)
  - { id: jct-w-pass, name: "Junction North Pass", kind: JUNCTION, pos: [110000,75000], start_owner: NEUTRAL }
  - { id: abut-n-w, name: "North Bridge West Abutment", kind: ABUTMENT, pos: [182000,60000], start_owner: NEUTRAL }
  - { id: abut-n-e, name: "North Bridge East Abutment", kind: ABUTMENT, pos: [218000,60000], start_owner: NEUTRAL }
  - { id: jct-e-hub, name: "Junction East Hub", kind: JUNCTION, pos: [270000,120000], start_owner: NEUTRAL }

edges:
  # West Approach Highway (Land)
  - { a: fob-n-w, b: abut-n-w, layer: ROAD, speed_mult: 1.0 }
  # Bridge Crossing Span (Water) - Destructible by kinetic strikes
  - { a: abut-n-w, b: abut-n-e, layer: ROAD, bridge: bridge-n, length_m: 36000, speed_mult: 1.0 }
  # East Departure Highway (Land)
  - { a: abut-n-e, b: cross-n, layer: ROAD, speed_mult: 1.0 }
```

### 3.2 Impact on Simulation State
- Convoys calculate routing via Dijkstra/A* on the enriched graph.
- Convoys never take unrealistic direct diagonal cuts across trackless wilderness.
- Destructible bridges only sever the `abut-n-w -> abut-n-e` edge, keeping approach highways open for ground units to maneuver and establish defensive perimeters.

---

## 4. Rollout Phasing

1. **Phase 1 (Current - NX-176)**:
   - Client-side visual prototyping in `unified-visualizer.html`.
   - Continuous DTED and road draping tools in `tools/terrain/`.
2. **Phase 2 (Simulation Kernel Sync - NX-180)**:
   - Ingest `strait-1-dem16.bin` into `services/sim` radar engine.
   - Expand `content/theaters/strait-1.yaml` with Class B waypoint nodes.
   - Add unit tests verifying zero drift between simulation LoS and 3D visual geometry.

---

## 5. Two-Tier Kinematic & Physics Boundary (10 Hz Sim vs. 60 Hz Renderer)

### 5.1 Architectural Decision: Decoupled Physics Boundary
A critical architectural boundary is maintained between simulation authority and presentation: **Do NOT implement a 60 Hz rigid-body or aerodynamic physics engine inside `services/sim`**.

Preserving `services/sim` as a pure 10 Hz discrete tactical solver provides decisive advantages:
1. **Ultra-Fast Headless Balance Sweeps**: Monte Carlo balance runs and crowd simulation sweeps (`tools/balance/`) execute at $50\times - 200\times$ real-time speed.
2. **Strict Tick Budget Adherence**: Preserves the `SC-10` sub-25ms tick budget constraint on standard server hardware without CPU thread contention.
3. **Compact Replay Snapshots**: Campaign command and event logs remain lean ($\sim 1.3\text{MB}$ per hour per `CLIPS-REPLAY.md`), enabling scalable multi-camera post-production.

```
+------------------------------------------------------------------------+
|                   TIER 1: SIMULATION KERNEL (10 Hz)                    |
|  - Altitude Bands: LOW_NOE (<150m AGL) vs HIGH_ALT                     |
|  - Discrete DEM Raycast Line-of-Sight (LoS) Radar/SAM Masking          |
|  - Road Grade Velocity Multipliers & Network Graph Routing             |
|  - Class B Intermediate Valley / Road Nodes (JUNCTION, ABUTMENT)       |
+-----------------------------------T------------------------------------+
                                    | 10 Hz State Stream (msgpack / JSON)
                                    v
+------------------------------------------------------------------------+
|              TIER 2: PRESENTATION LAYER KINEMATICS (60 Hz)             |
|  - Deterministic 60 Hz 6-DOF Attitude Derivation                       |
|  - Coordinated Turn Bank (phi), Angle of Attack Pitch (theta), Yaw     |
|  - Rotorcraft Cyclic/Collective Pitch & Ground Axle Terrain Alignment  |
|  - Canyon Wall Potential-Field Weaving (grad DEM Repulsive Vector)     |
|  - Aerodynamic Vapor Ribbon Contrails & Dynamic Cockpit HUD Reticles   |
+------------------------------------------------------------------------+
```

### 5.2 Tier 1: Sim Kernel - 2.5D Tactical Truth
`services/sim` models theater geometry in 2.5D space:
- **Altitude Bands**: Units operate in discrete altitude envelopes:
  - `LOW_NOE` (Nap-of-the-Earth, $<150\text{m}$ AGL): Aircraft utilize terrain masking inside canyon corridors, valleys, and fjord trenches.
  - `MED_PATROL` ($150\text{m} - 3,000\text{m}$ AGL): Standard transit and loiter envelope.
  - `HIGH_ALT` ($>3,000\text{m}$ AGL): High-altitude transit subject to long-range early warning radar detection.
- **DEM Line-of-Sight Raycast Masking**:
  - Radar and SAM envelopes evaluate LoS raycasts against the baked DTED elevation matrix (`strait-1-dem16.bin`).
  - Aircraft flying at `LOW_NOE` inside mountain corridors break radar line-of-sight against opposing `RADAR_SITE` and `AIR_DEFENSE_SITE` nodes when ridge terrain intercepts the ray vector.
  - Occluded targets transition from active radar tracks to stale track memory or drop entirely from the tactical picture (`FOW-6`).
- **Road Grade Speed Penalties & Corridor Routing**:
  - Road network edges compute instantaneous slope between adjacent nodes, applying grade speed multipliers ($0.6\times - 1.0\times$) for uphill mountain passes.
  - Convoys and strike packages route through Class B waypoint nodes (`JUNCTION`, `ABUTMENT`) to navigate winding canyons without cutting straight lines across impassable peaks.

### 5.3 Tier 2: Presentation Layer - Deterministic 60 Hz 6-DOF Kinematics
The decoupled frontend (WebGL/Three.js/Canvas2D) consumes 10 Hz discrete snapshots and evaluates continuous 6-DOF attitude at 60 Hz (or higher display refresh):
- **Continuous 6-DOF Orientation**: Computes roll ($\phi$), pitch ($\theta$), yaw ($\psi$), and instantaneous $G$-load deterministically from velocity vectors $\mathbf{v}$, yaw rates $\omega$, and vertical rates $\dot{z}$.
- **Canyon Wall Potential-Field Weaving**: Evaluates local elevation gradients $\nabla \text{DEM}(x, y)$ to apply subtle, deterministic repulsive lateral offsets, visually banking low-flying strike fighters along canyon thalwegs without violating tactical waypoint corridors.
- **Dynamic Aerodynamic Visuals**: Triggers wingtip vapor ribbons and vortex sheets when calculated $G$-load exceeds thresholds ($>4.5G$), rendering high-speed canyon runs with broadcast-grade fidelity.

---

## 6. Main Simulation Agent Implementation Checklist (Actionable Tasks)

The following implementation tasks are assigned to the simulation kernel engineering pipeline (`NX-176`, `NX-177`, `NX-180`):

- [ ] **Task 1: DTED Binary Ingestion into Sim Kernel (`NX-176`)**
  - Ingest `strait-1-dem16.bin` (generated via `tools/terrain/bake_synthetic_dted.py`) into `services/sim`.
  - Maintain a memory-mapped or fast 1D array (`array('h', ...)`), providing an $O(1)$ lookup `get_elevation_m(x, y)`.
  - Provide fallback to pure mathematical formula `sample_strait1_elevation(x, y)` if the binary asset is not present.

- [ ] **Task 2: Low-NOE Radar & SAM Occlusion in Combat/FoW (`NX-177`)**
  - Add altitude band classification (`LOW_NOE`, `MED_PATROL`, `HIGH_ALT`) to unit state models.
  - Integrate Bresenham 3D raycast into `nexus.core.fow` and `nexus.core.combat`.
  - When an aircraft flies at `LOW_NOE` and the raycast intersects terrain elevation before reaching the sensor, mark target as terrain-masked (`is_masked = true`).
  - SAM sites and early-warning radars must reject or drop track on masked units.

- [ ] **Task 3: Class B Waypoint Nodes in Theater Schema (`NX-176` / `NX-180`)**
  - Extend theater YAML schema validator in `content/theaters/` to accept `kind: JUNCTION` and `kind: ABUTMENT`.
  - Update `content/theaters/strait-1.yaml` with valley corridor waypoints and fjord bridge abutments.
  - Verify ground convoy pathfinding and low-altitude flight packages navigate via Class B nodes without straight-line clipping through mountain terrain.
