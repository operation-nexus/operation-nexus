# SPEC: Broadcast Overlay

Status: Draft · Tracker: NX-175…NX-189 · ADR-0005 · Inputs: P72–98, C51–72

## 1. Layout (1920×1080; 16:9)
```
┌───────────────────────────────────────────────────────────────────────────┐
│ MOMENTUM ███████░░░ 64%  │ OBJECTIVE: SEIZE STRAIT BRIDGE 11:42 │ THREAT: BRAVO │
├──────────────────────────────────────────────────────┬────────────────────┤
│                                                      │ PiP INTERCEPT SCOPE│
│                 MAIN C2 MAP (canvas)                 │ (2D, 3 s min dwell)│
│  terrain contours (static) · roads/bridges · nodes   ├────────────────────┤
│  units (shape-coded) · rings · blobs · tracers       │ ROTATING PANEL     │
│                                                      │ (4 panels, 20 s)   │
│                                                      ├────────────────────┤
│                                                      │ SITREP LOG (6)     │
├──────────────────────────────────────────────────────┴────────────────────┤
│ TICKER: recent actions · "Type !join strike | recon | logi to deploy"      │
└───────────────────────────────────────────────────────────────────────────┘
```
The rotating panels (from the conversation, C60) are: Campaign Status, Top Commanders (per role), Active Packages, and Latest Major Event.
- **Campaign Status** includes the **"Operators active"** count (humans only, `—` until known; DI-5, DI-1) **plus a breakdown** by role or doctrine (e.g. Strike 5 · Recon 2 · Logistics 4), optionally by rank band (Q-CT-4). Source: `PresenceSnapshot` → `Hud.operators`.
- **Momentum breakdown** (Q-UX-9): the momentum bar ("Signal strength" label, strategic only, TS-2) is explained in the rotating panels and ticker with nodes held, supply %, recent major events and per-sector status. Source: `Hud.momentum_breakdown`.
- **Tasking Board** (GAMEPLAY §1b): the top few open jobs ("NEEDED: supply to WEST FOB") are shown so lurkers learn what matters.
- Which elements stay permanently on screen vs rotate as more HUD elements arrive is **open** (Q-UX-11, gap analysis 2026-10-17).

## 1a. Orientation
The coalition is on the **left** and the enemy on the **right** (GAMEPLAY §9a). The right sidebar covers enemy rear territory, so the camera framing keeps the frontline within the left 70% of the map area. Vertical 9:16 (P3, OV-11): the map rotates so the coalition is at the **bottom** and the enemy at the **top** (Q-GD-13).

## 2. Requirements
- **OV-1 Five-second readability.** The momentum bar, objective and threat tier are always visible, and the text is at least 28 px at 1080p (readable on 720p mobile).
- **OV-2 Friend/foe uses shape plus locked color** (Q-STYLE-1, Q-STYLE-4). Clearwave (coalition) units are **cyan** with **angular** shapes. The Static (enemy) is **glitchy magenta/red** with **jagged, glitchy** shapes and a crackle effect. Cosmetics change **halos and trails only**, never the base icon color (fixes critique #22). Symbols are simple and shape-coded per class, **auto-generated from each platform's declared category** (CONFIG-AND-CONTENT §7a); custom uploaded icons are allowed with new platforms, and animated icons come later. The symbology is our own, *inspired by* military map-symbol conventions, not a copy of any real standard. To be playtested.
- **OV-2a Unit tags.** AI units carry an `[AI]` tag and dimmer styling (Q-GD-25, DI-5). A unit whose operator has an active conduct restriction carries a small neutral **probation** tag, with no text beyond the tag and no numbers; it disappears when the restriction ends (Q-MOD-6). The PiP intercept scope shows Pk during engagements (Q-CBT-3), and damage states are visible on the unit symbol.
- **OV-3** The palette passes deuteranopia, protanopia and tritanopia simulations (an automated script in CI). No information is conveyed by color alone.
- **OV-4 Label density.** Only the PiP focus, the top-N contributors, and the user's unit after `!me` / `!status` get labels. Everything else shows symbols only. Units in the same package are drawn as one flight symbol with a count.
- **OV-5a Recruit strip and `!me` highlight** (GAMEPLAY §1a).
- **OV-5 New-command ack.** A ping plus a callsign chip appears at the spawn base within 1 frame of receiving the event.
- **OV-6 PiP director.** Each engagement gets a priority score (human-involved, kill, objective, rarity). Minimum dwell is 3 s. A newly spawned viewer unit gets a short spotlight if nothing more important is happening.
- **OV-7 Interpolation.** Render at server time minus 100 ms with linear interpolation, and extrapolate at most 200 ms.
- **OV-8 Resilience.** Auto-reconnect and banners as described in WIRE-PROTOCOL. A heartbeat element changes every second so the frame-freeze probe can detect stalls.
- **OV-9 Security.** No `innerHTML`, a strict CSP, and no remote resources (fonts are bundled).
- **OV-10 Performance.** p95 frame time under 12 ms on the reference host. The static terrain layer is pre-rendered.
- **OV-11 Vertical 9:16 variant (P3).** A separate route that crops around the PiP focus and stacks the HUD. OBS uses Aitum Vertical or a second browser source.

## 2a. Map annotation layer (owner requirement, 2026-10-17)
A shared, robust annotation system that everything uses: rally calls, objectives, sitreps, recon pings, GM operations, recaps and replays.
- **AN-1 Location vocabulary:**
  - **Named nodes** for everyone.
  - **Sectors** (named regions) for casual viewers and sitrep fallbacks.
  - An optional **grid reference** overlay for advanced operators (e.g. a lettered and numbered grid, toggled on screen at low contrast). It's also accepted by `!vector` and `!rally`.
- **AN-2 Direction:** compass rose, bearings, and arrows showing the axis of advance and unit headings. West → east is the coalition advance (GAMEPLAY §9a).
- **AN-3 Ephemeral annotations:** pins, circles (areas), arrows (moves or attacks) and short labels. Each has a source (RALLY, OBJECTIVE, SCOUT, GM, SYSTEM), a TTL, a max count per source, and collision-aware placement. They never obscure the momentum bar or objective.
- **AN-4 One renderer, one data model:** annotations are a typed wire message (`Annotation{id, kind, geometry, source, label_key, ttl_ticks}`, added to CONTRACTS). Live overlay, vertical layout, clips and replays all render them identically.
- **AN-5 Safety:** labels come from templates and IDs only; no free text (SEC-MOD-1).

## 3. Visual language
Owner decisions Q-BRAND-1, Q-STYLE-1, Q-STYLE-2 (2026-10-17); exact values go in the brand and style guide (NX-274):
- **Colors:** near-black base; Clearwave cyan; The Static glitchy magenta/red with a crackle effect; **amber** for warnings and supply; **lime/violet** accents for fun moments (rally, rescue). Validated for colorblind safety (OV-3); shape coding keeps friend/foe readable regardless of color. Tone: "Signal" radar war room, fun and friendly, not grim.
- **Typography:** a clean technical UI font with **tabular numerals**, plus a **bold display font** for big moments. Free/open licenses only, bundled with the overlay (no remote fonts, OV-9).
- **Supply routes (Q-UX-6):** route lines with flow brightness, a per-base supply gauge, cut routes red/dashed, starving bases blink gently. When an operator orders a move (`!rebase`, `!target`), draw the route with distance/ETA and fuel reach; out of range shows "cannot reach: fuel" and suggests the nearest reachable base (§2a annotations).
- **Text:** English first, all strings through localization keys (Q-UX-5).
- **Map:** glowing phosphor contours rendered as thin lines with low alpha; terrain shown as topographic contours plus subtle elevation shading (C69).
- **Static mastermind visual** (Q-STYLE-5, P3): a small, brief, glitchy corrupted-signal portrait/logo that crackles on with taunts or big events; playful, not corny.

## 4. Tests
Playwright visual snapshots of fixture states (TESTING-STRATEGY §3.7), the palette script, an XSS fixture (SEC-OV-1), and a reconnect test.
