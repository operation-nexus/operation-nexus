# Prompt: Visual Iteration, Rendering & Headless Review

```
You are working on visual rendering, 3D terrain, camera sequencing, or broadcast overlay in Operation Nexus.
Read AGENTS.md, docs/specs/OVERLAY.md, docs/specs/TERRAIN-AND-BIOMES.md, and activate the skill `hiveplex-visualization`.

Follow this visual engineering workflow:

1. ARCHITECTURAL DECOUPLING (DI-1):
   - Confirm rendering consumes only `RenderFrameState`.
   - Never put simulation logic or fabricated unit movement in the presentation layer.

2. ELEVATION & GEOMETRY AUDIT:
   - Check the physical elevation budget: water at -3.5m, terrain at 0.0m, roads at +0.22m (with polygonOffset: true), elevated bridges at +2.0m.
   - Separate channel landmasses to eliminate overlapping coplanar triangles (zero Z-fighting).
   - If heightmaps or 3D meshes are needed, run `python3 tools/terrain/generate_terrain_model.py`.

3. DESIGN PASS & MULTI-PARADIGM CHECK:
   - Run a design pass producing 2-3 distinct concepts (Option A 2D Signal, Option B 3D Holo-Table, Option C FLIR MFD).
   - Adhere to the Signal / Static brand colors (docs/design/VISUAL-STYLE-CATALOG.md).
   - Avoid generic AI UI or default unstyled component libraries.

4. HEADLESS VISUAL VERIFICATION:
   - Before committing any visual code or HTML sandbox, run:
     `./.agents/skills/hiveplex-visualization/scripts/capture_review_screenshot.sh <html-path> <output.png> 1600,1050 2500`
   - Inspect the rendered screenshot for pixel density, non-blank WebGL buffers, and proper camera framing.
   - Test both 16:9 desktop (1600x1050) and 9:16 mobile vertical (600x1050).

5. COMMIT & PR:
   - Run `make check-overlay` (if overlay is touched) and `make check-python` (if tools/terrain is touched).
   - Include visual screenshots in the PR body comparing before and after.
   - Commit with Conventional Commits on a feature branch off develop.
```
