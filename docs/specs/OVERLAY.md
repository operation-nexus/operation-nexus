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

## 1a. Orientation
The coalition is on the **left** and the enemy on the **right** (GAMEPLAY §9a). The right sidebar covers enemy rear territory, so the camera framing keeps the frontline within the left 70% of the map area. Vertical 9:16: Q-GD-13.

## 2. Requirements
- **OV-1 Five-second readability.** The momentum bar, objective and threat tier are always visible, and the text is at least 28 px at 1080p (readable on 720p mobile).
- **OV-2 Friend/foe uses shape plus locked color.** Coalition units are cyan-family with angular shapes. Enemy units are red/orange with diamond shapes. Cosmetics change **halos and trails only**, never the base icon color (fixes critique #22).
- **OV-3** The palette passes deuteranopia, protanopia and tritanopia simulations (an automated script in CI). No information is conveyed by color alone.
- **OV-4 Label density.** Only the PiP focus, the top-N contributors, and the user's unit after `!status` get labels. Everything else shows symbols only. Units in the same package are drawn as one flight symbol with a count.
- **OV-5a Recruit strip and `!me` highlight** (GAMEPLAY §1a).
- **OV-5 New-command ack.** A ping plus a callsign chip appears at the spawn base within 1 frame of receiving the event.
- **OV-6 PiP director.** Each engagement gets a priority score (human-involved, kill, objective, rarity). Minimum dwell is 3 s. A newly spawned viewer unit gets a short spotlight if nothing more important is happening.
- **OV-7 Interpolation.** Render at server time minus 100 ms with linear interpolation, and extrapolate at most 200 ms.
- **OV-8 Resilience.** Auto-reconnect and banners as described in WIRE-PROTOCOL. A heartbeat element changes every second so the frame-freeze probe can detect stalls.
- **OV-9 Security.** No `innerHTML`, a strict CSP, and no remote resources (fonts are bundled).
- **OV-10 Performance.** p95 frame time under 12 ms on the reference host. The static terrain layer is pre-rendered.
- **OV-11 Vertical 9:16 variant (P3).** A separate route that crops around the PiP focus and stacks the HUD. OBS uses Aitum Vertical or a second browser source.

## 3. Visual language
Dark slate background (`#050811`). Glowing phosphor contours rendered as thin lines with low alpha. Terrain shown as topographic contours plus subtle elevation shading (C69). Monospace typography with tabular numerals.

## 4. Tests
Playwright visual snapshots of fixture states (TESTING-STRATEGY §3.7), the palette script, an XSS fixture (SEC-OV-1), and a reconnect test.
