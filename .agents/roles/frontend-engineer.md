# Role: Overlay / Frontend Engineer

**Use for:** `apps/overlay` (broadcast renderer) and, later, the companion site.

Must read: `docs/specs/OVERLAY.md`, `docs/specs/WIRE-PROTOCOL.md`.

Hard rules:
- Never use `innerHTML` with data. Render text through Pixi `Text`/`BitmapText` or `textContent`.
- The overlay is a pure function of (snapshot + deltas + local interpolation time). It has no game logic.
- Frame budget: 16.6 ms at 1080p on the reference broadcast machine. Add a perf test for new layers.
- Every color pairing must pass the colorblind-safe palette check in OVERLAY §Accessibility.
- Use only generated types from `contracts/`. Don't hand-write wire types.

Design originality (owner requirement, 2026-10-17):
- The look must be **distinctive, not generic AI UI.** Before building any new visual surface (overlay layer, site page, Command Center screen), run a design pass using every available design skill and tool: e.g. the `frontend-design` skill, `artifact-design`/`dataviz` guidance for charts, design MCP servers if configured. Produce 2–3 distinct concepts and compare them against the brand guide (NX-274) **before** coding.
- Avoid template defaults: no stock gradients, generic card grids, or default component-library looks. Every visual choice should trace back to the Signal/Static brand.
- Record the chosen concept and the reasoning in the PR (screenshots of the alternatives).
