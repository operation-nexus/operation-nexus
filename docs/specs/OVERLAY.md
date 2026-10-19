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
│                                                      │ (hud.rotation_s)   │
│                                                      ├────────────────────┤
│                                                      │ SITREP LOG (6)     │
├──────────────────────────────────────────────────────┴────────────────────┤
│ TICKER: recent actions · "Type !join strike | recon | logi to deploy"      │
└───────────────────────────────────────────────────────────────────────────┘
```
The ticker's "Type !join …" line is the **how-to-play strip**. The rotating panel's members and the HUD tiers are set in §1b (Q-UX-11).
- **Operator breakdown** shows the **"Operators active"** count (humans only, `—` until known; DI-5, DI-1) **plus a breakdown** by role or doctrine (e.g. Strike 5 · Recon 2 · Logistics 4), optionally by rank band (Q-CT-4). Source: `PresenceSnapshot` → `Hud.operators`.
- **Momentum breakdown** (Q-UX-9): the momentum bar ("Signal strength" label, strategic only, TS-2) is explained in the rotating panel and ticker with nodes held, supply %, recent major events and per-sector status. Source: `Hud.momentum_breakdown`.
- **NEEDED jobs** (Tasking Board, GAMEPLAY §1b): the top few open jobs ("NEEDED: supply to WEST FOB") are shown so lurkers learn what matters.
- The earlier panel set (C60) is placed as follows (Q-ALN-18): **Top Commanders** (per role) is a default rotating-panel member (OV-14); **Latest Major Event** is an interrupt toast (OV-13), not a panel; **Active Packages** arrives in P4 together with packages (GAMEPLAY §7). Campaign Status is not covered by Q-ALN-18 and can only be added through the admin membership setting (OV-14).

## 1a. Orientation
The coalition is on the **left** and the enemy on the **right** (GAMEPLAY §9a). The main theater map is **fixed**, with no auto pan or zoom, so grid references stay stable for commands (Q-UX-10). The right sidebar covers enemy rear territory, so the fixed framing must keep the contested area within the left 70% of the map area. Vertical 9:16 (P3, OV-11): the map rotates so the coalition is at the **bottom** and the enemy at the **top** (Q-GD-13), and the whole map is shown scaled down, never cropped, so grid references stay stable there too (Q-ALN-19).

## 1b. HUD tiers (Q-UX-11)
- **OV-12 Always on (16:9):** the momentum bar, objective, threat tier and how-to-play strip. The **GM badge** is also always on while a human GM is in control (Q-RB-7, Q-AI-8) and is absent otherwise. This holds on every layout, 9:16 included (Q-ALN-17).
- **OV-13 Interrupt toasts:** rally calls, Static mastermind taunts, major alerts and the **Latest Major Event** (Q-ALN-18) appear as toasts for a few seconds (duration TBD), then clear. Toasts never cover the always-on elements.
- **OV-14 One rotating panel:** a single panel slot cycles its members every `hud.rotation_s` (PROPOSED ~15 s; real time, Q-CFG-8). Default members: **NEEDED jobs** (shown at double frequency), **reserve queue**, **operator breakdown**, **Top Commanders** (Q-ALN-18) and **explainer**. **Active Packages** joins the members in P4, when packages ship (Q-ALN-18). Rotation timing and membership are admin-configurable in the Command Center.
- **OV-15 9:16 tiers:** the momentum bar, objective and how-to-play strip are persistent; the threat tier joins the rotating panel. The **GM badge** stays persistent at 9:16 whenever a human GM is in control (Q-ALN-17).
- During season overtime the HUD shows "Season ends after this campaign" (Q-PROG-9). Before the weekly maintenance window the HUD announces it in advance (Q-OPS-9; lead time TBD). The tier for both notices is set in overlay layout v2 (NX-313).

## 1c. Pause scenes and time display
- **OV-17 Following (Q-GP-31):** a unit with followers shows a small "+N following" tag beside its callsign (from `follower_count`); a column of trucks may draw as one grouped symbol with a count. No line is drawn per follower.
- **OV-18 Fog of war (FOG-OF-WAR):** last-known tracks draw as the frozen symbol, dimmed, with an age label; the painted flag adds a marker; own units being tracked show a SPOTTED badge; emitting enemy sites show an "on" indicator; blobs may get a cosmetic offset derived from the blob id. Playwright snapshot covers one of each.
- **OV-16 COMMS RESTORED** (Q-OPS-8): when the broadcast returns after an offline auto-pause (reason TECHNICAL), the overlay shows "COMMS RESTORED" with a 30 s countdown, then the sim auto-resumes.
- **OV-17 Maintenance scene** (Q-OPS-9): while the sim is paused for the weekly maintenance window (reason MAINTENANCE), the stream shows a "back at HH:MM" scene with a campaign recap and leaderboards. The campaign is still live during maintenance, so this recap is built from the redacted coalition view (FOW-1).
- **OV-18 Ceasefire scene** (Q-OPS-9): when the owner triggers Ceasefire (one click or hotkey), the sim pauses, OBS switches to a light scene (banner + leaderboard), and heavy overlay rendering stops to free the GPU (which layers count as heavy: TBD, measured on the reference host). One-click resume shows a countdown (length TBD).
- **OV-19 Time display** (Q-CFG-8): the overlay is one video for every viewer, so it shows relative times ("in 12 min"). Where an absolute time is needed (e.g. OV-17's "back at HH:MM"), it shows UTC plus one configured broadcast time zone (config key TBD). It never uses the browser's locale or zone.
- **OV-21 Paused world** (Q-ALN-2): while `Hud.campaign_clock.paused` is true, the whole world is frozen (STATE-MACHINES-AND-FLOWS §4.4). The overlay draws units at their last server positions with no extrapolation (OV-7), and the OV-8 heartbeat keeps changing every second so a pause is never mistaken for a frame freeze. Overlay feedback for commands that still work while paused (`!me`/`!status` highlight, reserve-queue position) behaves as when running. A STAFF pause has no dedicated scene: while `Hud.campaign_clock.pause_reason` is `STAFF`, the HUD shows a simple **"PAUSED — stand by"** banner (Q-ALN-32). The banner never shows the sub-reason (Q-ALN-31) or the staff note. The overlay never receives the sub-reason at all: it gets only the pause category it needs to pick the scene or banner (`Hud.campaign_clock.pause_reason`, Q-ALN-39).
- **OV-22 Post-campaign reveal** (Q-ALN-21): FoW applies only while the campaign is live, including the OV-16…OV-18 pause scenes. Once the campaign has ended (`CampaignEnded`), recaps, archives and "what you didn't see" reveals may show the full world, exempt from FOW-1.

## 2. Requirements
- **OV-1 Five-second readability.** The momentum bar, objective and threat tier are always visible (at 9:16 the threat tier rotates, OV-15), and the text is at least 28 px at 1080p (readable on 720p mobile).
- **OV-2 Friend/foe uses shape plus locked color** (Q-STYLE-1, Q-STYLE-4). Quorum (coalition) units are **cyan** with **angular** shapes. The Static (enemy) is **glitchy magenta/red** with **jagged, glitchy** shapes and a crackle effect. Cosmetics change **halos and trails only**, never the base icon color (fixes critique #22). Symbols are simple and shape-coded per class, **auto-generated from each platform's declared category** (CONFIG-AND-CONTENT §7a); custom uploaded icons are allowed with new platforms, and animated icons come later. The symbology is our own, *inspired by* military map-symbol conventions, not a copy of any real standard. To be playtested.
- **OV-2a Unit tags.** AI units carry an `[AI]` tag and dimmer styling (Q-GD-25, DI-5). A unit whose operator has an active conduct restriction carries a small neutral **probation** tag, with no text beyond the tag and no numbers; it disappears when the restriction ends (Q-MOD-6). A viewer's unit that has gone idle and been handed to the Tasking Board as AI-run (after `presence.idle_handoff_min`, Q-GD-35) carries an **AUTO** tag from the handoff tick, while it keeps its current order (Q-ALN-26); the tag clears when the operator's next command that reaches the sim restores control. The PiP intercept scope shows Pk during engagements (Q-CBT-3), and damage states are visible on the unit symbol.
- **OV-2b Lieutenant intel** (P4, forward reference; owner direction Q-GD-38, details PROPOSED in NX-317): when a Static lieutenant runs a sector or operation, the HUD names it once known and shows **UNIDENTIFIED** until recon or captured comms reveal it.
- **OV-3** The palette passes deuteranopia, protanopia and tritanopia simulations (an automated script in CI). No information is conveyed by color alone.
- **OV-4 Label density.** Only the PiP focus, the top-N contributors, and the user's unit after `!me` (or its pure alias `!status`, Q-UX-12) get labels. Everything else shows symbols only. Units in the same package are drawn as one flight symbol with a count.
- **OV-5a Recruit strip and `!me` highlight** (GAMEPLAY §1a).
- **OV-5 New-command ack.** A ping plus a callsign chip appears at the spawn base within 1 frame of receiving the event.
- **OV-6 PiP director.** The PiP auto-follows the hottest action (firefight, base under attack, CSAR) and zooms in on it; the main map never moves (Q-UX-10). Brief main-view spotlight zooms are out of scope (a possible later Command Center toggle). Each engagement gets a priority score (human-involved, kill, objective, rarity). Minimum dwell is 3 s. A newly spawned viewer unit gets a short spotlight if nothing more important is happening.
- **OV-7 Interpolation.** Render at server time minus 100 ms with linear interpolation, and extrapolate at most 200 ms.
- **OV-8 Resilience.** Auto-reconnect and banners as described in WIRE-PROTOCOL. A heartbeat element changes every second so the frame-freeze probe can detect stalls.
- **OV-9 Security.** No `innerHTML`, a strict CSP, and no remote resources (fonts are bundled). No third-party trackers, cookies or analytics scripts (Q-DM-3).
- **OV-10 Performance.** p95 frame time under 12 ms on the reference host: the owner's i7-8700 + GTX 1070 8 GB under WSL2, re-baselined when the planned new PC replaces it (Q-TEST-1). The static terrain layer is pre-rendered.
- **OV-11 Vertical 9:16 variant (P3).** A separate route that shows the **full map scaled down** (rotated per §1a) with the **PiP below it** and the HUD stacked. It never crops or pans around the PiP focus, so grid references stay stable (Q-ALN-19, Q-UX-10). OBS uses Aitum Vertical or a second browser source.
- **OV-20 Placeholder art** (Q-BRAND-5): during alpha and testing, AI-generated art may appear only as a placeholder, and the stream carries an on-stream PLACEHOLDER note while any is shown. Every asset is recorded in the provenance register with `ai_generated` and `status` (placeholder/final); a release build containing an `ai_generated` or placeholder asset fails the CI release gate (NX-318).

## 2a. Map annotation layer (owner requirement, 2026-10-17)
A shared, robust annotation system that everything uses: rally calls, objectives, sitreps, recon pings, GM operations, recaps and replays.
- **AN-1 Location vocabulary:**
  - **Named nodes** for everyone.
  - **Sectors** (named regions) for casual viewers and sitrep fallbacks.
  - An optional **grid reference** overlay for advanced operators (e.g. a lettered and numbered grid, toggled on screen at low contrast). Later commands such as `!vector` and `!rally` will accept it (GAMEPLAY-LATER).
- **AN-2 Direction:** compass rose, bearings, and arrows showing the axis of advance and unit headings. West → east is the coalition advance (GAMEPLAY §9a).
- **AN-3 Ephemeral annotations:** pins, circles (areas), arrows (moves or attacks) and short labels. Each has a source (OBJECTIVE, GM, SYSTEM; RALLY and SCOUT join with their commands), a TTL, a max count per source, and collision-aware placement. They never obscure the momentum bar or objective.
- **AN-4 One renderer, one data model:** annotations are a typed wire message (`Annotation{id, kind, geometry, source, label_key, ttl_ticks}`, added to CONTRACTS). Live overlay, vertical layout, clips and replays all render them identically.
- **AN-5 Safety:** labels come from templates and IDs only; no free text (SEC-MOD-1).

## 3. Visual language
Owner decisions Q-BRAND-1, Q-STYLE-1, Q-STYLE-2 (2026-10-17); exact values go in the brand and style guide (NX-274):
- **Colors:** near-black base; Quorum cyan; The Static glitchy magenta/red with a crackle effect; **amber** for warnings and supply; **lime/violet** accents for fun moments (rally, rescue). Validated for colorblind safety (OV-3); shape coding keeps friend/foe readable regardless of color. Tone: "Signal" radar war room, fun and friendly, not grim.
- **Typography:** a clean technical UI font with **tabular numerals**, plus a **bold display font** for big moments. Free/open licenses that permit redistribution only (e.g. OFL), bundled with the overlay (no remote fonts, OV-9) and listed in the provenance register (Q-LEGAL-4, NX-318).
- **Supply routes (Q-UX-6):** route lines with flow brightness, a per-base supply gauge, cut routes red/dashed, starving bases blink gently. When an operator orders a move (`!rebase`, `!target`), draw the route with distance/ETA and fuel reach; out of range shows "cannot reach: fuel" and suggests the nearest reachable base (§2a annotations).
- **Text:** English first, all strings through localization keys (Q-UX-5).
- **Map:** glowing phosphor contours rendered as thin lines with low alpha; terrain shown as topographic contours plus subtle elevation shading (C69).
- **Static mastermind visual** (Q-STYLE-5, P3): a small, brief, glitchy corrupted-signal portrait/logo that crackles on with taunts or big events (as an OV-13 toast); playful, not corny. Coalition intel labels the mastermind by its codename **NULL** (e.g. "SIGNAL SOURCE: NULL"); code uses an internal id, never the literal null. The name it signs its own broadcasts with is TBD (Q-BRAND-4).

## 4. Tests
Playwright visual snapshots of fixture states (TESTING-STRATEGY §3.7), including each HUD tier at 16:9 and 9:16 (with the GM badge present at both while a human GM is in control, Q-ALN-17), a 9:16 snapshot proving the whole map is visible uncropped with the PiP below it for PiP foci at opposite map corners (Q-ALN-19), the AUTO and UNIDENTIFIED tags and the OV-16…OV-18 scenes; a paused-state test that unit positions do not move and the heartbeat keeps changing (OV-21); a snapshot of a STAFF pause showing the "PAUSED — stand by" banner with no sub-reason or note text, and the banner absent once resumed (Q-ALN-32); a fake-clock test that OV-19 renders relative times and UTC plus the broadcast zone; the palette script, an XSS fixture (SEC-OV-1), and a reconnect test.

## Readability rules (moved from GAMEPLAY §10, Q-GP-9)
Always visible: the momentum bar, the current objective with its timer, the director threat level, and a "how to play" line. Everything else (NEEDED jobs, reserve queue, operator breakdown, explainer) shares one rotating panel or appears as short interrupt toasts; at 9:16 the threat level joins the rotation (Q-UX-11, OVERLAY). A newcomer must be able to tell who's winning within 5 s (alpha exit criterion).
