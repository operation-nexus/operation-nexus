# ADR-0005: Overlay renderer is Canvas2D first, Pixi.js if profiling demands it

- Status: Proposed (Q-ARCH-5)
- Date: 2026-10-17

## Context
The plans mention Pixi.js, plain Canvas and Three.js interchangeably. The look is vector lines, glows, text and rings, so there are few textures. React adds nothing to a full-screen canvas except a DOM layer for panels.

## Decision
- Layered canvases: a static terrain layer (rendered once, cached), a dynamic units/rings layer, and an FX layer. HUD panels and the ticker are DOM, rendered with `textContent` only, with no framework (or Preact if the panels get complex).
- Client interpolation: render at server tick minus 100 ms, linearly interpolating between snapshots. Extrapolate only when a frame is late, up to 200 ms.
- Move to Pixi.js (WebGL) if p95 frame time exceeds 8 ms on the reference host.
- The Three.js PiP is deferred to the backlog. The MVP PiP is a 2D intercept scope.

## Consequences
Small bundle and fast startup in the OBS browser source. Glow effects use `shadowBlur` sparingly, or pre-rendered sprites.
