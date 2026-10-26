# Architecture Blueprint: Decoupled Simulation & Visual Rendering Pipeline

> **Kernel facts check (lead, 2026-10-26):** this document states kernel facts that are wrong (2D kernel, per-area masking, fixed bands, 0.6 s game time per tick). Corrections and verdicts: [VISUALIZER-KERNEL-AUDIT-2026-10-26](../review/VISUALIZER-KERNEL-AUDIT-2026-10-26.md); owner questions Q-VIZ-1 to Q-VIZ-6. Not authoritative for kernel behaviour.

> **Operation Nexus / Hiveplex Visual Architecture**
> *Status: Draft Brainstorm & Technical Proposal*
> *Storage: External Brain Artifact (Decoupled from Git Repository)*

---

## 1. Executive Summary & Core Objective

The primary objective is to allow Hiveplex to **swap between completely different visual aesthetics, dimensions (2D, 2.5D, 3D), and rendering engines (HTML5 Canvas2D, Pixi.js, Three.js, Babylon.js, or Godot Web)** seamlessly, without touching a single line of the Python simulation kernel or backend wire protocol.

```
┌─────────────────────────────────────────────────────────────┐
│                   Python Sim Kernel (10 Hz)                 │
│         Authoritative, Deterministic, Headless               │
└──────────────────────────────┬──────────────────────────────┘
                               │ Binary msgpack / JSON WS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Sim State Buffer & Interpolation               │
│         (Snapshot / Delta, Tick Sync, Dead-Reckoning)        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Generic Render Model (IRenderModel)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Renderer Agnostic Facade                     │
│               (Viewport, Camera, SceneGraph)                │
└───────┬──────────────────────┼───────────────────────┬──────┘
        │                      │                       │
        ▼                      ▼                       ▼
┌──────────────┐       ┌──────────────┐        ┌──────────────┐
│  Renderer A  │       │  Renderer B  │        │  Renderer C  │
│ 2D Canvas /  │       │ 2.5D / 3D    │        │ High-Fi      │
│ Vector Glow  │       │ Three.js     │        │ WebGPU /     │
│ (CRT Signal) │       │ (Holo-Table) │        │ PixiJS       │
└──────────────┘       └──────────────┘        └──────────────┘
```

---

## 2. The Decoupling Strategy: "State vs. Stage"

To achieve absolute decoupling, the system separates **State** (what is happening in the world) from **Stage** (how entities and effects are materialized on screen).

### 2.1 The Four-Layer Pipeline

```mermaid
flowchart TD
    subgraph L1["Layer 1: Network & Ingestion"]
        WS["WebSocket Client"] --> Deser["MsgPack/JSON Deserializer"]
        Deser --> Validator["Schema Contracts Guard"]
    end

    subgraph L2["Layer 2: World State Store & Interpolator"]
        Validator --> SnapshotStore["Snapshot & Delta Buffer"]
        SnapshotStore --> Interpolator["Kinematic Interpolator (-100ms)"]
        Interpolator --> SceneState["Normalized Scene State"]
    end

    subgraph L3["Layer 3: Abstract Scene Graph (Bridge)"]
        SceneState --> SceneGraphAdapter["Scene Graph Adapter"]
        SceneGraphAdapter --> EventBus["Visual FX Event Bus"]
    end

    subgraph L4["Layer 4: Swappable Render Engines"]
        SceneGraphAdapter --> IRenderer["IRenderEngine Interface"]
        IRenderer --> Canvas2D["Canvas2D: CRT Vector Phosphor"]
        IRenderer --> PixiJS["Pixi.js: High-Density 2D Sprites & Glow"]
        IRenderer --> ThreeJS["Three.js: 3D Hologram Tactical Table"]
        IRenderer --> CustomWasm["WebGPU / Wasm Engine"]
    end
```

### 2.2 Boundary Separation Rules

1. **No Graphics Primitives in State:** State messages never specify colors, textures, pixel dimensions, or drawing commands. State only transmits positions, headings, velocities, entity kinds, faction affiliations, health percentages, and abstract semantic events (e.g., `MISSILE_INTERCEPT`, `NODE_CAPTURED`, `SUPPLY_STARVED`).
2. **Normalized Coordinates ($0.0 \dots 1.0$ or Real-World Meters):** The sim transmits positions in meters relative to theater origin `(0, 0)`. The rendering engine maps these meters to screen pixels, WebGL projection matrices, or isometric tiles based on its own camera/viewport configuration.
3. **Decoupled HUD vs. Main Stage:** HUD overlays (momentum bar, sitrep ticker, rotating stats panel) live as DOM elements above the canvas/viewports. Whether the canvas is rendered in 2D or 3D, the broadcast telemetry HUD remains uniform and crisp at native 1080p / 9:16 resolutions.

### 2.3 Deterministic 60 Hz 6-DOF Kinematic Interpolator (`KinematicInterpolator`)

Layer 2 ingests discrete 10 Hz simulation ticks ($t_k, t_{k+1}$) and evaluates continuous 6-DOF attitude and kinematics at 60 Hz (or monitor v-sync). This ensures fluid flight dynamics and realistic camera tracking without burdening the simulation kernel with rigid-body aerodynamics.

#### 2.3.1 Mathematical Derivation of 6-DOF Attitude
For an interpolated unit position $\mathbf{p}(t) = [x(t), y(t), z(t)]^T$ with ground velocity vector $\mathbf{v}_{xy} = [\dot{x}, \dot{y}]^T$, speed $v = \|\mathbf{v}_{xy}\|$, heading $\psi = \operatorname{atan2}(\dot{y}, \dot{x})$, and yaw angular velocity $\omega = \dot{\psi}$:

1. **Coordinated Turn Bank Angle ($\phi$)**:
   Fixed-wing aircraft bank smoothly into lateral turns balancing centrifugal and gravitational forces:
   $$\phi = -\arctan\left(\frac{v \cdot \omega}{g \cdot k_{\text{scale}}}\right)$$
   where $g = 9.81\text{m/s}^2$ and $k_{\text{scale}} \approx 1.0 - 1.2$ controls banking aggressiveness. The bank angle is smoothly clamped to safe operational limits:
   $$\phi_{\text{clamped}} = \operatorname{clamp}(\phi, -75^\circ, +75^\circ)$$

2. **Flight Path Pitch Angle ($\theta$)**:
   Aircraft pitch reflects vertical climb/dive angle plus dynamic angle of attack ($AoA$) induced during high-$G$ maneuvers:
   $$\theta = \arctan2(\dot{z}, v_{xy}) + k_{\text{AoA}} \cdot |\omega|$$
   where $\dot{z}$ is vertical climb rate and $k_{\text{AoA}} \approx 0.08\text{deg}/(\text{deg/s})$ adds dynamic nose-up pitch during aggressive lateral turns.

3. **Helicopter Cyclic & Collective Attitude**:
   Rotorcraft orientation couples forward acceleration and lateral cyclic roll:
   - **Forward Pitch**: Pitch is proportional to forward longitudinal acceleration ($\dot{v}$):
     $$\theta_{\text{helo}} \propto -k_{\text{accel}} \cdot \dot{v}$$
     yielding realistic nose-down tilt during acceleration and a nose-up flare when decelerating into hover.
   - **Cyclic Bank**: Lateral tilt into translational turns:
     $$\phi_{\text{helo}} = -\arctan\left(\frac{v \cdot \omega}{g}\right) \cdot 0.6$$

4. **Ground Vehicle Axle Terrain Alignment**:
   For ground transports and armor (`LOGI_TRUCK`, `ENEMY_ARMOR`):
   - Sample DTED terrain elevation at front axle $\mathbf{p}_f$ and rear axle $\mathbf{p}_r$ separated by wheelbase $L_w$:
     $$\theta_{\text{ground}} = \arcsin\left(\frac{\text{DEM}(\mathbf{p}_f) - \text{DEM}(\mathbf{p}_r)}{L_w}\right)$$
   - Sample left and right track/wheel elevations to compute lateral camber roll $\phi_{\text{ground}}$.

5. **Canyon Wall Potential-Field Weaving**:
   Strike fighters flying at low altitude (`LOW_NOE`) through winding canyons evaluate local terrain height gradients $\nabla \text{DEM}(x, y) = [\frac{\partial z}{\partial x}, \frac{\partial z}{\partial y}]^T$:
   - A repulsive potential force $\mathbf{F}_{\text{rep}} = -\nabla \text{DEM}(x, y)$ pushes the visual flight path toward the canyon thalweg (valley center).
   - This smoothly banks the aircraft along canyon contours, avoiding visual clipping into vertical rock walls while strictly preserving the simulation kernel's macroscopic waypoint corridor.

---

## 3. The `IRenderEngine` Contract

Every visual style (2D vector, 3D holo-table, thermal FLIR, retro-grid) implements a uniform lifecycle:

```typescript
export interface IRenderEngine {
  /** Initialize canvas context, shaders, buffers, and textures */
  initialize(container: HTMLElement, options: RenderConfig): Promise<void>;

  /** Handle viewport resizing and DPI scaling (1080p, 4K, 9:16 mobile) */
  resize(width: number, height: number, pixelRatio: number): void;

  /** Update terrain, static contours, bridges, and infrastructure */
  updateTheaterMap(theater: TheaterData): void;

  /** Apply interpolated dynamic entities for the current render frame */
  renderFrame(frame: RenderFrameState): void;

  /** Trigger ephemeral visual effects (missile tracers, explosion bursts, radar sweeps) */
  triggerEffect(effect: VisualEffectEvent): void;

  /** Set camera focus for PiP (Picture-in-Picture) or tactical zoom */
  setCameraTarget(target: CameraTarget): void;

  /** Clean up resources when switching themes or engines */
  dispose(): void;
}
```

### 3.1 `RenderFrameState` (Engine-Agnostic Input)

```typescript
export interface RenderFrameState {
  renderTick: number;
  serverTimeMs: number;
  interpolationAlpha: number; // 0.0 to 1.0 between snapshot A and B
  
  // Entities ready for drawing
  units: Map<number, VisualUnit>;
  facilities: VisualFacility[];
  supplyNodes: VisualNode[];
  supplyRoutes: VisualEdge[];
  contestedZones: VisualContestedZone[];
  fogOfWar: FogMaskData;
  annotations: VisualAnnotation[];
}

export interface VisualUnit {
  id: number;
  callsign: string;
  side: 'COALITION' | 'ENEMY';
  kind: 'STRIKE_FIGHTER' | 'RECON_UAV' | 'LOGI_TRUCK' | 'ENEMY_ARMOR' | etc;
  x: number; // meters from theater origin
  y: number; // meters from theater origin
  altitudeMeters: number; // altitude above sea level in meters
  headingDeg: number;
  rollDeg: number; // banking attitude [-75..+75]
  pitchDeg: number; // climb/dive attitude [-85..+85]
  yawRateDegPerSec: number; // instantaneous turn rate
  gLoad: number; // instantaneous G-force (1.0 = level flight)
  isTerrainMasked: boolean; // occluded from radar LoS by DEM ridges
  damageState: 'HEALTHY' | 'DAMAGED' | 'DISABLED';
  isSelected: boolean;
  isAiControlled: boolean;
  trailHistory: Array<{ x: number; y: number; alpha: number }>;
}

export interface VisualEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  layer: 'ROAD' | 'SEA_LANE';
  roadClass: 'MSR_PRIMARY' | 'CONNECTOR_SPUR' | 'BRIDGE_CAUSEWAY';
  speedMult: number;
  bridgeId?: string;
  bridgeIntegrityPct?: number; // 0 to 100
  activeConvoyCount: number;
  isContested: boolean;
  waypointsMeters: Array<[number, number]>;
}
```

---

## 4. Visual Styles & Paradigm Exploration

| Visual Paradigm | Dimension | Technology Stack | Visual Inspiration | Strengths | Trade-offs |
|---|---|---|---|---|---|
| **A. "Signal" Phosphor CRT** | 2D Vector | Canvas2D or Pixi.js | *DEFCON*, *HighFleet*, NORAD radar consoles, 80s tactical scopes | Instant readability, extremely lightweight (<5ms frame time), low GPU footprint in OBS | Limited sense of verticality/altitude |
| **B. Holographic War Table** | 2.5D / Isometric | Three.js or Babylon.js | *Ender's Game*, *Star Wars* briefing room, *Total Annihilation* radar | High production value, visually striking devlog showcase, excellent depth for air vs ground | Slightly higher GPU memory usage; camera angles must preserve grid readability |
| **C. Modern C2 Glass Cockpit** | 2D High-Tech | Pixi.js + SVG Layering | Boeing Link-16, modern F-35 tactical glass, *Command: Modern Operations* | Ultra-sharp typography, mil-spec data density, realistic flight symbology | Can feel intimidating if visual hierarchy is not carefully tuned |
| **D. FLIR Thermal / Recon Drone** | 2D/3D Hybrid | Custom GLSL Shaders | AC-130 gunship camera, thermal predator vision (White-Hot / Black-Hot) | Perfect for the PiP Intercept Scope; instant combat drama and twitch clip appeal | Not suitable for the entire full theater map (eye strain over 24/7 hours) |
| **E. Stylized Vector Voxels / Micro-Machines** | 3D Low-Poly | Three.js + Flat Shading | *Advance Wars 3D*, *Mini Motorways*, *Bad North* | Friendly, playful tone (aligns with "fun, non-grim co-op"), high streamer appeal | Deviates from the raw "NORAD military war-room" aesthetic |

---

## 5. Architectural Recommendations for Seamless Swapping

### 5.1 Hot-Swappable Renderer Registry
Create a singleton `RenderManager` in the overlay frontend that registers available render engines:

```typescript
class RenderManager {
  private activeEngine: IRenderEngine;
  private engines = new Map<string, () => IRenderEngine>();

  register(themeId: string, factory: () => IRenderEngine) {
    this.engines.set(themeId, factory);
  }

  async switchTheme(themeId: string) {
    if (this.activeEngine) {
      this.activeEngine.dispose();
    }
    const factory = this.engines.get(themeId);
    if (!factory) throw new Error(`Unknown theme: ${themeId}`);
    
    this.activeEngine = factory();
    await this.activeEngine.initialize(this.container, this.config);
    this.activeEngine.updateTheaterMap(this.currentTheater);
  }
}
```

### 5.2 Decoupled Audio & Visual Events
Sound cues (tactical chimes, radio squelch, mastermind glitch static) and visual HUD toasts are triggered by standard sim events (`UnitSpawned`, `NodeCaptured`, `SupplyStarved`, `MastermindTaunt`) via an in-memory event bus. Swapping the 3D table for a 2D radar has zero effect on the audio or broadcast HUD layers.

### 5.3 Live-Stream Streamer Controls
In the admin Command Center (or via secret query params like `?theme=crt` or `?theme=holo3d`), the broadcaster or devlog creator can switch visual renderers on the fly without refreshing OBS or disconnecting viewers.

### 5.4 Production Module Breakdown & GPU Instancing (`OV-10`)

To replace monolithic prototypes with a modular, maintainable production architecture that strictly satisfies the sub-12ms p95 frame time budget (`OVERLAY.md` OV-10) on the reference hardware (Nvidia GTX 1070 / Apple Silicon M-series):

#### 5.4.1 Production Module Breakdown
The presentation frontend is partitioned into dedicated single-responsibility TypeScript modules:
- `core/kinematic-interpolator.ts`: Ingests 10 Hz state snapshots and evaluates deterministic 60 Hz 6-DOF attitude ($\phi, \theta, \psi$), $G$-forces, and canyon-wall repulsive potential fields.
- `renderers/pillar1-c2-canvas.ts`: High-density 2D Tactical C2 GIS canvas engine with offscreen pre-rendered topographic contours and tactical vector symbology.
- `renderers/pillar2-three-surface.ts`: Full 3D low-angle and surface visualizer using Three.js with continuous DTED terrain elevation mesh and road network ribbons.
- `renderers/pillar3-flir-mfd.ts`: Sensor operator thermal infrared (White-Hot / Black-Hot) and optical tracking MFD with GLSL post-processing shaders.
- `renderers/pillar4-cognitive-lattice.ts`: AI causal decision trees, branch probabilities, counterfactual outcomes, and synaptic intent arcs.
- `renderers/cockpit-hud-overlay.ts`: High-resolution 2D/3D collimated fighter HUD, armored vehicle cabin split-windshield, helicopter chin bubble instruments, and dynamic 6-DOF artificial horizon.

#### 5.4.2 GPU Instancing & Batched Meshing (`THREE.InstancedMesh` / `BatchedMesh`)
To support large-scale engagements (up to 1,000 active units, 5,000 ballistic tracers, and complex road infrastructure) without exceeding draw call budgets:
1. **Dynamic Units**: Instanced via `THREE.InstancedMesh` grouped by archetype (aircraft, ground armor, convoys). Unit position, 6-DOF quaternion orientation, faction color, and damage state are updated in a single instance matrix buffer per frame.
2. **Infrastructure & Viaduct Pylons**: Bridge piers, abutments, and road markers are merged via `THREE.BatchedMesh` or static indexed buffer geometry, reducing complex bridges to a single draw call.
3. **Ballistic Munitions & Tracers**: High-rate autocannon tracers and missile contrails use instanced billboard quads with GPU particle expansion, maintaining solid 60 fps (<12ms frame time) even during saturation air defense engagements.
