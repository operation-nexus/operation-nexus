# Unified Terrain, Biomes & Z-Fighting Architectural Specification

> **Operation Nexus / Hiveplex — Theater & Environment Engineering**
> *Status: Proposed Spec Upgrade for `contracts/config/theater.json` and `CONFIG-AND-CONTENT.md` §9*
> *Storage: External Brain Artifact (Decoupled from Git Repository)*

---

## 1. Current State vs. Gaps in Existing Specs

### 1.1 What the Current Specs Contain (`CONFIG-AND-CONTENT.md` §9.1)
Currently, a theater is defined primarily as a **graph network with an optional heightmap**:
```yaml
bounds_m: { w: 400000, h: 240000 }
terrain:
  heightmap: "theaters/strait-1/heightmap.png" # 16-bit PNG (Optional in first build)
  height_scale_m: 2500
  sea_level_m: 0
  masking_regions: [...]                      # Polygons for LoS sensor blockage
nodes: [...]                                  # Airbases, FOBs, Bridges
edges: [...]                                  # ROAD / SEA_LANE connections
```

### 1.2 The Missing Architectural Elements
1. **No Landcover / Biome Standard:** The spec has no vocabulary for differentiating between **ocean, lake, river, beach, grassland, forest, desert, and urban zones**.
2. **No Vertical Elevation Budget (Z-Fighting Root Cause):** There is no defined rule for where roads, water surfaces, bridges, and shorelines sit in 3D space, leading to coplanar polygon collision.
3. **No Simulation Gameplay Feedback:** Forests do not yet provide sensor clutter or convoy speed penalties; cities do not reflect radar clutter; rivers do not impede ground units unless a bridge exists.

---

## 2. Eliminating Z-Fighting: The 3 Core Graphics Rules

Z-fighting occurs when two polygons occupy the exact same depth coordinates ($Y=0$) or when floating-point precision collapses across vast tactical distances ($0.5\text{ m} \dots 400\text{ km}$).

```
[ Elevated Bridge Span ]  ──────►  Y = +14.0m
[ Road / Infrastructure]  ──────►  Y = +3.0m   (polygonOffset: -1, -2)
[ Ground / Lowland Plain] ──────►  Y = +2.0m   (polygonOffset: 1, 1)
[ Beach / Shoreline Bevel] ─────►  Y = 0.0m
[ Water Surface (River/Strait)] ►  Y = -2.5m
[ Channel Bed / Lake/Sea Trench]►  Y = -8.0m
```

### 2.1 The Three Enforced Mitigations:
1. **Physical Elevation Budget (Layer Budget):** Never allow two distinct surface types to share the same $Y$ coordinate. Water is strictly recessed ($Y = -2.5\text{m} \dots -4\text{m}$), beaches sit at $Y = 0\text{m}$, terrain plains at $Y = +2\text{m}$, and bridges rise cleanly at $Y = +12\text{m} \dots +18\text{m}$.
2. **Topological Carving (Non-Overlapping Meshes):** The land mesh must **never** render geometry beneath water surfaces. Water channels are physically cut out from the terrain mesh (either via Boolean CSG or two distinct landmass meshes), guaranteeing that no two triangles overlap in $(X, Z)$.
3. **Engine-Level Precision:**
   - Enable `logarithmicDepthBuffer: true` in `THREE.WebGLRenderer` to distribute 24-bit/32-bit depth precision evenly across logarithmic distance.
   - Apply `polygonOffset: true` (`factor: -1`, `units: -2`) on wireframes, runways, and road decals to keep them cleanly above the terrain surface.

---

## 3. Proposed Biome & Landcover Taxonomy

We propose adding a standard `landcover` classification to `contracts/config/theater.json`:

| Biome Code | Name | Physical Elevation | Gameplay Sim Effect (SIM-CORE) | Visual Shading Style |
|---|---|---|---|---|
| `0x00` | `OCEAN_DEEP` | $-20\text{ m} \dots -100\text{ m}$ | Impassable for ground; naval domain (P3) | Deep navy abyss with bathymetric wireframe |
| `0x01` | `WATER_INLAND` (River/Strait/Lake) | $-2.5\text{ m} \dots -5.0\text{ m}$ | Blocks ground convoys unless bridge exists | Translucent teal/cyan flow with shore bevels |
| `0x02` | `BEACH_SHORE` | $-0.5\text{ m} \dots +1.0\text{ m}$ | Amphibious transit zone; convoy speed $0.6\times$ | Pale cyan/amber contour transition line |
| `0x03` | `PLAINS_LOWLAND` | $+2.0\text{ m} \dots +80\text{ m}$ | Baseline terrain; convoy speed $1.0\times$ | Standard dark slate with subtle grid |
| `0x04` | `FOREST_WOODLAND` | $+50\text{ m} \dots +200\text{ m}$ | Radar clutter; NOE air masked; convoy speed $0.7\times$ | Emerald/cyan cluster glyphs or procedural trees |
| `0x05` | `DESERT_ARID` | $+10\text{ m} \dots +150\text{ m}$ | High dust signature (thermal bloom); speed $0.85\times$ | Warm amber contour lines with sparse dune ridges |
| `0x06` | `HIGHLANDS_ROCK` | $+450\text{ m} \dots +2500\text{ m}$ | Full radar LoS masking (`masking_regions`); impassable for trucks | Steep wireframe peaks with topographic density |
| `0x07` | `URBAN_METRO` | $+10\text{ m} \dots +60\text{ m}$ | High radar clutter; repair rate $+25\%$; cover | Dense rectilinear block grid with neon node anchors |

---

## 4. Multi-Layer Theater Authoring Pipeline

```mermaid
flowchart TD
    subgraph Authoring["1. Master Content Source (content/theaters/strait-1/)"]
        Topo["elevation.png (16-bit Grayscale Heightmap)"]
        Biome["landcover.png (8-bit Categorical Biome Index)"]
        Network["theater.yaml (Nodes, Edges, Bridges, Sectors)"]
    end

    subgraph Compiler["2. Tooling: Terrain Preprocessor (tools/terrain_compiler.py)"]
        Topo & Biome & Network --> CompilerPass["Precompute Masking & Mesh Buffers"]
        CompilerPass --> SimCache["sim_masking_grid.bin (1km cells for FOW-3)"]
        CompilerPass --> WebMesh["terrain_mesh.glb / WebGL Buffer (Zero Z-Fighting)"]
    end

    subgraph Runtime["3. Dual Runtime Consumers"]
        SimCache --> SimKernel["nexus.core (Deterministic Sim, 10 Hz)"]
        WebMesh --> WebGLRenderer["Overlay / 3D Director Engine (60 FPS)"]
    end
```

### 4.1 Theater File Schema Upgrade (`contracts/config/theater.json`)

```yaml
schema_version: 2
slug: strait-1
name: "Strait One — Contested Lifeline"
bounds_m: { w: 400000, h: 240000 }

terrain:
  elevation_map: "theaters/strait-1/elevation.png"
  height_scale_m: 2500
  sea_level_m: 0
  landcover_map: "theaters/strait-1/landcover.png"
  
  elevation_budget_m:
    water_surface: -2.5
    beach: 0.0
    plains: 2.0
    roads: 3.0
    bridges: 14.0

biomes:
  - id: FOREST_NORTH
    kind: FOREST_WOODLAND
    speed_mult: 0.70
    radar_clutter: true
    polygon: [[-120000, 40000], [-80000, 60000], ...]

bridges:
  - id: bridge_north
    node_id: north_bridge
    spans_nodes: [fob_nw, north_crossing]
    clearance_m: 14.0
    deck_width_m: 18.0
    structural_hp: 500
```

---

## 5. Implementation Roadmap

1. **Step 1 (Immediate - Verified in Prototype):**
   - Implemented dual-landmass separation with recessed $-3.5\text{m}$ water channel and elevated $+2\text{m}$ bridge spans in `hiveplex-advanced-visualizer.html`.
   - Enabled `logarithmicDepthBuffer: true` and `polygonOffset` on wireframe contours.
2. **Step 2 (Tooling / Compiler):**
   - Create `tools/terrain_compiler.py` in `operation-nexus` to bake 16-bit heightmaps and landcover index maps into precomputed spatial masking grids for `nexus.core`.
3. **Step 3 (Contracts & Schema):**
   - Update `contracts/config/theater.json` to include the `elevation_budget_m` and `biomes` list definitions.
