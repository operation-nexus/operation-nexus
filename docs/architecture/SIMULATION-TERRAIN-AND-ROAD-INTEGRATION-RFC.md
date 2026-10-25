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
