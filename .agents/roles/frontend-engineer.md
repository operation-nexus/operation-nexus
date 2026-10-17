# Role: Overlay / Frontend Engineer

**Use for:** `apps/overlay` (broadcast renderer) and, later, the companion site.

Must read: `docs/specs/OVERLAY.md`, `docs/specs/WIRE-PROTOCOL.md`.

Hard rules:
- Never use `innerHTML` with data. Render text through Pixi `Text`/`BitmapText` or `textContent`.
- The overlay is a pure function of (snapshot + deltas + local interpolation time). It has no game logic.
- Frame budget: 16.6 ms at 1080p on the reference broadcast machine. Add a perf test for new layers.
- Every color pairing must pass the colorblind-safe palette check in OVERLAY §Accessibility.
- Use only generated types from `contracts/`. Don't hand-write wire types.
