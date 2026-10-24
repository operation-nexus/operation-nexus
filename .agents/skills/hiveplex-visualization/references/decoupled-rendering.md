# Decoupled Rendering Architecture in Hiveplex

## 1. Core Rule: Kernel / Renderer Boundary

1. **Simulation Kernel (`nexus.core`) is Pure:**
   - Evaluates at fixed 10 Hz ticks.
   - Emits raw positions (meters from center `(0, 0)`), headings, velocities, and semantic events.
   - Knows **nothing** about pixels, textures, shaders, camera angles, or WebGL.

2. **Decoupled Bridge (`IRenderEngine`):**
   - Consumes `RenderFrameState`.
   - Any rendering engine (2D Canvas, Three.js 3D, PixiJS, WebGPU) implements the `IRenderEngine` interface.
   - Can be swapped hot at runtime (`setParadigm('option_a' | 'option_b' | 'option_c')`).

## 2. Zero Fabricated Data Rule (DATA-INTEGRITY DI-1)

- Every vehicle speed, turn rate, missile trail, and camera angle must map directly to the deterministic simulation frame.
- 3D chase cameras must anchor to the simulated kinematics vector:
  $$\vec{P}_{\text{cam}} = \vec{P}_{\text{unit}} - \vec{V}_{\text{norm}} \cdot d_{\text{follow}} + \vec{U} \cdot h_{\text{offset}}$$
  where $\vec{V}_{\text{norm}}$ is the unit velocity unit vector, $d_{\text{follow}} = 36\text{m}$, and $h_{\text{offset}} = 14\text{m}$.
