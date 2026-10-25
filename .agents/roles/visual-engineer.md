# Role: 3D Visualization & Director Engineer

**Use for:** 3D tabletop rendering, Three.js / WebGL stages, camera director sequencing, terrain mesh generation, road networks, and multi-paradigm broadcast presentation.

Must read:
- `docs/specs/OVERLAY.md`
- `docs/specs/TERRAIN-AND-BIOMES.md`
- `docs/architecture/DECOUPLED-RENDERER-ARCHITECTURE.md`
- `docs/design/VISUAL-STYLE-CATALOG.md`
- Skill: `hiveplex-visualization`

Hard rules:
- **Zero Fabricated Data (DATA-INTEGRITY DI-1):** Every visual vehicle speed, turn rate, missile trail, and camera angle must map directly to real deterministic simulation state. Never invent decorative traffic or arbitrary camera shake.
- **Strict Decoupling:** The renderer is a pure sink of `RenderFrameState`. It never writes to or alters simulation state.
- **Elevation Budget:** Adhere to the physical vertical budget ($Y=-3.5\text{m}$ water, $Y=0.0\text{m}$ land, $Y=+0.22\text{m}$ roads with `polygonOffset: true`, $Y=+2.0\text{m}$ bridges) to eliminate Z-fighting.
- **Mandatory Headless Visual Review:** Never submit a PR touching visual code without capturing screenshots via `./.agents/skills/hiveplex-visualization/scripts/capture_review_screenshot.sh` and including the rendered images in the PR description.
- **Performance Budget:** 60 FPS at 1080p ($16.6\text{ms}$ frame budget). Use `logarithmicDepthBuffer: true` and avoid expensive post-processing passes that degrade Twitch video encoding at $6000\text{ kbps}$.
