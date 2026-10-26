---
name: hiveplex-visualization
description: >-
  Engineering, procedural generation, visual styling, and headless review for
  Hiveplex / Operation Nexus live simulation rendering across 2D, 3D holographic tabletop,
  and FLIR MFD glass cockpit paradigms. Use whenever designing, testing, modifying,
  or verifying visual frontends, 3D terrain meshes, road networks, camera sequencing,
  or automated video clipping pipelines.
---

# Hiveplex Visualization & Simulation Rendering Skill

This skill teaches agents how to design, generate, debug, and visually verify rendering engines, 3D terrain meshes, road supply networks, and live broadcast overlays for **Operation Nexus / Hiveplex**.

---

## 1. Core Engineering Workflow

When tasked with creating, modifying, or auditing a visual component or renderer:

1. **Enforce State Decoupling:**
   - Keep rendering logic strictly downstream of simulation state (`RenderFrameState`).
   - Consult [Decoupled Rendering Architecture](./references/decoupled-rendering.md).
   - Ensure zero fabricated kinematics (DATA-INTEGRITY DI-1).

2. **Check Elevation Budget & Avoid Z-Fighting:**
   - Ground terrain at $Y = 0.00\text{m}$.
   - Road ribbons at $Y = +0.22\text{m}$ with `polygonOffset: true`.
   - Elevated bridges at $Y = +2.00\text{m}$.
   - Recessed water channel at $Y = -3.50\text{m}$.
   - Consult [Elevation Budgeting & Z-Fighting Immunity](./references/elevation-budget-and-zfighting.md).

3. **Generate or Verify 3D Geometry:**
   - To bake or update procedural 3D terrain meshes (`.obj`), execute:
     `python3 ./scripts/generate_terrain_model.py --output content/theaters/strait-1-terrain.obj`
   - To convert vector GeoJSON biomes and road networks into spatial grids, use:
     `python3 tools/terrain/geojson_to_mask.py --input content/theaters/strait-1-biomes.geojson`

4. **Multi-Paradigm Support & Fictional Neutrality:**
   - **Zero Real-World Geopolitics**: All theaters and factions are strictly fictional. Never stream or reference real-world borders or active conflict zones.
   - Support swappable rendering paradigms:
     - **Option A (2D Signal / Tactical GIS)**: Flat Euclidean military cartography (`L.CRS.Simple`) with synthetic hillshades and Mil-STD-2525D icons.
     - **Option B (3D Holographic Tabletop)**: High-contrast wireframe and elevation contours.
     - **Option C (FLIR MFD Glass Cockpit)**: Thermal infrared sensor targeting.
     - **Option D (Textured Low-Poly RTS)**: PBR multi-texture terrain splatting (sand, rock, asphalt) and textured military units (camo strikers, haulers).

5. **6-DOF Kinematics & Dynamic Camera Sequencing:**
   - Model realistic aerodynamic bank angles $\phi = \arctan(v \cdot \dot{\psi} / g)$, pitch attitudes, and canyon-wall repulsive potential fields.
   - Orchestrate dynamic multi-camera Edit Decision Lists (EDLs) across 2D C2, 3D chase, cockpit HUD, and seeker cameras.
   - Consult [6-DOF Kinematics & Canyon Runs](./references/six-dof-kinematics-and-canyon-runs.md).

6. **Headless Visual Review & Deterministic Capture:**
   - Never commit visual changes without capturing and inspecting screenshots.
   - Run the automated review capture script:
     `./scripts/capture_review_screenshot.sh tools/prototype/visualizer-sandbox.html review.png 1600,1050 2500`
   - Use deterministic virtual-clock stepping (`window.renderDeterministicTick`) for zero-dropped-frame 60 FPS video recording.
   - Consult [Headless Visual Review Runbook](./references/headless-visual-review.md).

---

## 2. Directory Layout & Available Helpers

- **Scripts & Tools:**
  - [`capture_review_screenshot.sh`](./scripts/capture_review_screenshot.sh): Automates headless Chrome captures with virtual time budgets.
  - [`render_cinematic_pass.py`](../../tools/replay/render_cinematic_pass.py): Headless multi-camera cinematic pass recording harness and dynamic camera EDL executor.
  - [`mgrs_grid.py`](../../tools/terrain/mgrs_grid.py): MGRS tactical grid and coordinate conversion engine.
  - [`bake_synthetic_dted.py`](../../tools/terrain/bake_synthetic_dted.py): Synthetic DEM and Horn analytical hillshade baker.
  - [`drape_roads.py`](../../tools/terrain/drape_roads.py): Dynamic road spline draping and bridge conforming engine.
  - [`generate_lowpoly_assets.py`](../../tools/assets/generate_lowpoly_assets.py): Low-poly 3D OBJ unit mesh generator (<500 triangles).
  - [`generate_terrain_model.py`](./scripts/generate_terrain_model.py): Procedural 3D OBJ terrain mesh generator.
- **References:**
  - [`six-dof-kinematics-and-canyon-runs.md`](./references/six-dof-kinematics-and-canyon-runs.md): 6-DOF attitude formulas, coordinated turn roll, canyon potential-field weaving, and deterministic clock stepping.
  - [`unified-three-pillar-patterns.md`](./references/unified-three-pillar-patterns.md): Complete specifications for Three-Pillar sandbox, OOB fleet sidebar, and crosshairs.
  - [`mgrs-and-coordinate-systems.md`](./references/mgrs-and-coordinate-systems.md): NATO MGRS mapping, precision formulas, and CLI usage.
  - [`decoupled-rendering.md`](./references/decoupled-rendering.md): Pure kernel boundary rules and `IRenderEngine`.
  - [`elevation-budget-and-zfighting.md`](./references/elevation-budget-and-zfighting.md): Layer height budget and material offsets.
  - [`headless-visual-review.md`](./references/headless-visual-review.md): Automated verification runbook.
