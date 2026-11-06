# SPEC: Broadcast Overlay

Status: P2 subset Approved (owner, 2026-11-04): §0, OV-1, OV-7 to OV-10, OV-12, OV-13, OV-14, OV-19, OV-26 (NX-175, NX-178); rest Draft/Deferred · Tracker: NX-175…NX-189 · ADR-0005 · Feed: WIRE-PROTOCOL · Inputs: P72–98, C51–72

## 0. P2 subset: approved scope (NX-175, NX-178)

Owner, 2026-11-04, in chat: approve a P2 subset with the lead defaults below. Values marked PROPOSED are tunable without a spec change; everything else in this section is normative. **Only this section, §1b OV-12, OV-13, OV-14 (as narrowed here), OV-19 and OV-26, and requirements OV-1 and OV-7 to OV-10 (as narrowed here) are approved.** Every other section is **Deferred, not covered by this approval** and still needs its own sign-off before code.

### 0.1 Approved / deferred map
| Item | Status |
|---|---|
| §0 (this section), OV-1, OV-8, OV-9, OV-10, OV-12, OV-13 (mechanism), OV-14 (first-slice members), OV-19, OV-26; OV-7 for the state store | **Approved** |
| §0.10 map slice (NX-176/177; OV-2, OV-4, OV-5 as narrowed there) | **Approved** (owner, 2026-11-04, Q-UX-22); tunable values PROPOSED |
| §1 layout figure | A guide for the regions NX-175/178 build; the PiP and the SITREP LOG panel are not built (§0.6, §0.8) |
| §1a Orientation, OV-2/2a/2b, OV-3, OV-4, OV-5/5a, OV-6, OV-11, OV-15, OV-17, OV-18, OV-20, OV-21 to OV-25, §1c, §2a, §3 | Deferred |

The P2 exit set is OV-1 to OV-10 (ROADMAP P2). NX-175/178 deliver OV-1, OV-7, OV-8, OV-9, OV-10. OV-2, OV-4 and OV-5 come with NX-177, OV-3 with NX-180, and OV-6 needs the PiP (NX-179); all remain P2 exit items owned by those later tracker rows.

### 0.2 NX-175 / NX-178 scope
- **NX-175 (a):** WebSocket client for the WIRE-PROTOCOL feed, the state store (Welcome, Snapshot, Delta, Hud, Control), reconnect and banners (§0.3).
- **NX-175 (b):** layered canvases (static terrain, units, FX), the DOM HUD root, the 1920×1080 stage (§0.7), the CSP and bundled fonts (§0.4), and the heartbeat element (OV-8).
- **NX-178:** the HUD top bar (momentum, nodes held N of M, objective with timer, threat tier, war countdown), the ticker, the rotating panels (§0.6) and OV-26 wired to the live `PublicEvent` stream.
- **Deferred:** NX-177 (units), NX-179 (PiP), NX-180 and NX-180b, NX-182 (annotations), and the pause scenes OV-16 to OV-25. The 9:16 variant (OV-11) is P3.
- **Renderer:** Canvas2D with DOM panels (ADR-0005). three.js is not in the production bundle; the prototype's Holo3D and FLIR engines were deleted in NX-175 (a).

### 0.3 Connection, banners and reconnect
The overlay consumes WIRE-PROTOCOL and restates none of it; this section says only what the screen shows.
- **States:** cold start (before the first `Snapshot`), live, degraded. Cold start shows the HUD frame with every field at "—" (DI-1) and no map entities; it never shows stale or invented data.
- **Banners:** "UPDATE REQUIRED" on `Control{RELOAD}` or close 4003 (WP-1); "COMMS RESYNC" after 2 s without data (WP-5). UPDATE REQUIRED has priority over COMMS RESYNC. Banner text is a fixed overlay string, never server text and never the token.
- **Last frame:** on loss of data the last rendered frame stays, dimmed, under the banner; it is never cleared to black.
- **Close codes (WP §5):** 4002 and 4003 do not retry and the banner stays (4003 reloads per WP-1, after 5 s, or after 60 s (PROPOSED) when the page has been up less than 30 s (PROPOSED), so a build that is still stale after a reload retries at most once a minute; the banner shows during the wait; 4002 shows a fixed "AUTH FAILED" line). Every other close, and any socket error, reconnects with the WP-5 backoff.
- **Tick regress:** after a `Welcome` the store accepts a tick lower than the last it saw and replaces its state from the `Snapshot` (WP §6, server restart).
- **Resync:** `Control{RESYNC}` or a detected gap follows WP-3; the store stops applying `Delta`s, keeps its last data on screen (dimmed, per the Last-frame rule) and waits for the `Snapshot`, which replaces it. While unsynced and `Delta`s keep arriving, the client re-sends the resync `Ack` at most once per second. Only a `Snapshot` or an applied `Delta` counts as data for the 2 s COMMS RESYNC timer.

### 0.4 Security of the page
- **Token (WP §7.1):** read from `location.hash` once, then cleared with `history.replaceState`. It is never logged, stored (no `localStorage`, cookie or IndexedDB), put in a query string, or shown in a banner. For a WP-1 reload it is written back to the fragment with `replaceState` just before `location.reload()`, and the new page clears it again.
- **CSP (SEC-OV-2):** no inline script; no inline styles (styles live in CSS files: no `style=` attributes or `<style>` blocks, and dynamic values go through CSSOM); `connect-src` limited to the WS origin; fonts and every asset bundled, no remote assets. OBS page permissions are "No access".
  - **Delivery (NX-175 b):** a `<meta http-equiv>` CSP, injected into `index.html` by `apps/overlay/vite.config.ts` in production builds only (the dev server injects `<style>` tags and an HMR client, so it runs without the policy). `connect-src 'self'`: CSP3 lets `'self'` match `ws:`/`wss:` on the page's own host and port, which is where `start.ts` connects. Checked in headless Chromium: the WS handshake was not blocked and no `securitypolicyviolation` fired. The supported client is the OBS browser source (Chromium) only (owner, 2026-11-04); some WebKit and older Firefox versions do not match `ws:`/`wss:` under `'self'`, and a non-Chromium client would need the deployment's exact WS origin added to `connect-src`, never a bare scheme. Dynamic values (the stage transform) use CSSOM, which `style-src 'self'` allows. Fonts: JetBrains Mono Regular and Bold (OFL), files in `src/fonts/` with the license; `assetsInlineLimit: 0` keeps them out of `data:` URLs. `font-display: block` plus a `<link rel="preload">` for both faces in `index.html` (Vite rewrites the hashed URLs): the first banner never waits on a font fetch, and a fallback face never flashes on stream.
- Feed text is rendered with `textContent` (WP-6, OV-9).

### 0.5 Always-on top bar (OV-12 in the first slice)
Every nullable `Hud` field renders "—" when null (DI-1); nothing is defaulted to a number. Field shapes are CONTRACTS §7.
- **Momentum:** `Hud.momentum_pct` (0 to 100, nullable) on the bar, labeled per OV-12 ("Signal strength", Q-UX-9).
- **Nodes held N of M:** next to the momentum bar. `Hud` has no top-level node count. The only integer counts are `Hud.panels.campaign_status.nodes_held` (`coalition`, `enemy`, `neutral`); `momentum_breakdown.nodes_held_pct` is a percent only. **NX-170a's `Hud` schema must carry `nodes_held` and `nodes_total`** as top-level integers, over the same node set as `momentum_breakdown.nodes_held_pct`, with the contract stating whether that set is strategic nodes only. Until they exist the element renders "—". It does not derive N and M from the Campaign Status panel, which is deferred and whose node set is not stated.
- **Objective and timer:** `Hud.objective.name`, gated by `Hud.objective_mode`: `OFF` hides the objective and its timer, `TIMED` shows them. The timer is `objective.deadline_tick` minus `campaign_clock.elapsed_ticks` (both on the campaign clock, not the `Tick` counter; CONTRACTS `ObjectiveAnnounced`), shown as minutes and seconds at 10 ticks per second (SIM-CORE SC-2), "—" when `deadline_tick` is null. It freezes while `campaign_clock.paused` is true.
- **Threat tier:** `Hud.threat_tier` through `hud.tier.<tier>` keys (OV-19).
- **War countdown:** `campaign_clock.limit_ticks` minus `campaign_clock.elapsed_ticks`, in game time, frozen while `paused`, "—" when `limit_ticks` is absent. Between `Hud` messages (at most 1 Hz, WP-10) both timers advance by the ticks the `Delta` stream reports while not paused and are re-based on every `Hud`.
- **How-to-play strip:** the ticker's "Type !join …" line stays (§1). No "hold paused" banner is built; the hold-at-risk sitrep cards (OV-26) cover it.

### 0.6 Rotating panel, ticker, toasts and layout
- **Members in the first slice:** NEEDED (`Hud.panels.tasking_needed`), operator breakdown (`Hud.operators`), Top Commanders (`Hud.panels.top_commanders`). A panel with no real rows is skipped, never padded (DI-4). Dwell is `hud.rotation_s` (PROPOSED 15 s, real time); NEEDED shows at double frequency (OV-14). Membership is config-only in P2 (no Command Center yet). Campaign Status, the reserve queue, the explainer and Active Packages are deferred.
- **Ticker:** `Hud.ticker` items (`ModeratedText`, WP-6).
- **Toasts (OV-13):** a toast lasts PROPOSED 6 s of real time, one at a time from a queue, and never covers the OV-12 elements. Which `PublicEvent` kinds raise a toast beyond OV-26 is not decided here; P2 builds the mechanism and no other source; NX-178 defers even the mechanism until its first source exists (§0.9).
- **Layout and z-order:** the OV-26 sitrep stack replaces the "SITREP LOG" panel of §1 and sits above the rotating panel in the right column. Back to front: map canvases, DOM panels, OV-26 stack, toasts, banners (§0.3). Nothing but a banner covers the OV-12 bar.

### 0.7 Stage, readability and performance
- **Stage:** a fixed 1920×1080 stage scaled with a CSS transform to the browser-source size, centered. Device pixel ratio is handled (canvas backing store = CSS size × DPR, DPR capped at a PROPOSED 2). A safe area of a PROPOSED 5% on each edge keeps always-on text off the edge.
- **Readability (OV-1):** the 28 px floor applies to always-on HUD text. Minimum text contrast against its background: PROPOSED 4.5:1. Palette and fonts stay PROPOSED until the brand guide (NX-274).
- **5-second test (NX-034, owner-scheduled):** pass means a cold tester names who is winning, the objective, and how to join within 5 s.
- **Performance (OV-10):** p95 frame time under 12 ms at 1,000 entities on the reference host, measured in a perf run (`NEXUS_PERF=1 pnpm test`; TESTING-STRATEGY: measured on the real machine in a perf run, not in CI). The 8 ms figure in ADR-0005 is the trigger to migrate to Pixi.js, not the pass bar. NX-491's gate (`perf-gate.ts`) runs budget assertions only under `NEXUS_PERF=1` or `GITHUB_ACTIONS=true`; any new frame-time test for these layers goes through it.

**Built in NX-175 (b):** `stage.ts` and `stage-math.ts` (stage, DPR cap, safe area, layers), `terrain.ts` (roads and sea lanes, redrawn when the theater content or the backing size changes; NX-176 replaced the node fit with the `bounds_m` projector, y flipped, and added the node layer (§0.10)). The OV-8 heartbeat is a 4-cell binary counter that steps once per second from a main-thread timer (`.nx-heartbeat`, `data-beat`). The live stage mounts only when `#token=` is present; without it the prototype mock feed runs (dev mode).

### 0.8 Not built in this slice
The PiP column of §1 stays empty until NX-179. Unit drawing arrives with NX-177; NX-175 builds the layers and the terrain canvas only.

### 0.9 Built in NX-178 (`apps/overlay/src/hud/`)
Where the spec was silent, the code does the following (all reversible, none changes §0.5 or §0.6):
- **Wiring:** `WireClient` calls `onFrame` after an applied Snapshot, Hud or Delta; `mountHud` fills the existing `panels` and `sitrep` containers. The timers re-base on every Snapshot and Hud (with the store's last tick) and advance by the Delta tick step while not paused.
- **Strings:** no localization system exists; `hud/strings.ts` is a local key to English map (`hud.tier.<tier>` and the bar labels). A tier without a key shows its id.
- **Top bar:** the objective timer is m:ss (minutes can pass 59); the war countdown is h:mm:ss from one hour. An expired timer shows 00:00. `nodes_total` of 0 (campaign layer off) shows "—", like a missing count. Before the first Hud the objective cell shows "—" (the mode is unknown); `OFF` hides it.
- **Ticker:** shows the newest `Hud.ticker` item by `tick` next to the fixed how-to-play line (the contract does not fix the array order); no scrolling.
- **Rotating panel:** every Top Commanders role with rows is its own member ("Top STRIKE"), and the operator member lists the role counts then the rank bands. NEEDED appears twice per cycle, spread apart. `ROTATION_S` (15) is a constant until the config key exists.
- **OV-26:** the live path reuses the NX-496 board; sector names are not in `Welcome` (nodes only), so sectors show as their ids until the theater carries them. The stack is CSS classes in `hud/hud.css`, replacing the inline-styled prototype panel on the live stage only.
- **Toasts deferred:** nothing raises a toast in P2 (§0.6), so the queue, its CSS and the empty `nx-toasts` container were removed from NX-175/178's code; a follow-up adds them with their first source. The z-order in §0.6 still holds (toasts above the OV-26 stack, below banners).
- **Lifetime:** the HUD and its rotation timer live for the page; nothing disposes them.
- **Clock basis:** `Hud` has no tick, so its `campaign_clock.elapsed_ticks` is paired with the store's last applied tick. The Hud is built up to 1 s before it arrives, so the countdowns can be off by up to the ticks of that delay until the next Hud re-bases them. A Snapshot without a Hud advances the clock by its tick step and does not re-base the old Hud. `advance` never moves the basis tick backwards.
- **Rotator rows:** NEEDED rows read `<JOB_KIND> <node name or sector id or —>, <n> open`; operator rows `<ROLE>: <count>` then `<band>: <count>`; Top Commanders rows `<callsign>: <value>`, titled "Top <ROLE>". With exactly one other member NEEDED alternates 1:1 with it (a 2:1 cycle would show NEEDED for 30 s on wrap). The first member after an empty panel gets a full dwell.
- **Top bar:** `momentum_pct` is rounded for display; with `objective_mode` OFF the grid drops the objective column.
- **PROPOSED:** the palette (`--hud-*` tokens), every px size and position in `hud/hud.css` (bar height, 576 px right column, 104 px stack offset, panel 72 px above the ticker) are PROPOSED until NX-274.


### 0.10 NX-176 / NX-177 map slice
Approved by the owner with the lead defaults (2026-11-04, Q-UX-22). Owner decisions: Q-UX-18 to Q-UX-21. The lead defaults are PROPOSED and reversible; shapes and colours stay PROPOSED until the brand guide (NX-274). Canvas2D only (ADR-0005, Q-UX-15): no three.js, 6-DOF, InstancedMesh or attitude (NX-443).
- **Frame:** fixed, no pan or zoom (Q-UX-10). One projector for every layer: `x = left + x_m·k`, `y = top + (h − y_m)·k`, `k = min(map_w / w, map_h / h)` from `Welcome.theater.bounds_m` (NX-508): contain, never crop, anchored top-left; the leftover strip sits under the sidebar.
- **NX-176, static canvas from `Welcome.theater` (redrawn only on theater or backing-size change):**
  - **Contours:** a layer behind `terrain_ref`, empty while it is null (Q-UX-20); no invented relief.
  - **Roads and sea lanes:** `edges[].layer` ROAD as straight solid lines, SEA_LANE dashed; no road class or `speed_mult` is on the wire, so one style each.
  - **Bridges:** a crossbar across the edge at the `edges[].bridge` node; a down state only once bridge state is on the wire (Q-UX-21, NX-508).
  - **Nodes:** glyph by `kind` (AIRBASE, FOB, PORT, HQ, SANCTUARY, BRIDGE), colour by `NodeView.owner` and never colour alone (OV-3); capture as an arc from `capture.progress_pct` in `capture.side`; name labels for strategic kinds only; `stock_pct` and `starvation` as a small bar on coalition nodes only (null otherwise, DI-1).
  - **Facility rings:** `facilities[].ring_m` as a thin dashed circle at `facilities[].pos`; null draws nothing.
- **NX-177, units and FX canvases (real time, `requestAnimationFrame`):**
  - **Units:** `EntityView` shape by `unit_kind`, rotated by `heading_deg` (0 = north, clockwise); coalition angular, enemy jagged (OV-2, no crackle or cosmetics); `damage_state` as a fill ladder; `AI_GARRISON` drawn dimmer. No labels or flight symbols in this slice (OV-4 narrowed).
  - **Fog:** blobs at `cell_center` as a fuzzy mark sized by S, M or L, no icon, heading or count; last-known at `pos` as the frozen shape, dashed, faded, with its age; the server drops it (FOW-6a, FOW-9).
  - **Tracers:** from `WeaponFired` in `Delta.events`, shooter to target, until the matching `WeaponImpact` (capped at 3 s real time), then a short hit or miss flash; a shooter or target not in the store draws nothing.
  - **Interpolation (OV-7, ADR-0005):** render at the latest server tick − 100 ms, linear between bracketing states, extrapolate at most 200 ms on `speed_mps`/`heading_deg`, none while paused; heading by the shortest arc; a resync or tick regress drops the history.
- **Built in NX-176** (`apps/overlay/src/stage-math.ts`, `terrain.ts`, `nodes.ts`; layer order terrain, nodes, units, FX). Where the spec was silent (all PROPOSED, reversible):
  - **Projector:** `mapFrame(bounds_m)` in `stage-math.ts`, used by every map layer; the map rectangle is `MAP_RECT` x 96, y 120, w 1728, h 880 (inside the safe area, under the top bar, above the ticker). Strait-1 (400 by 240 km) frames at about 3.67 px per km; the enemy rear sits under the 576 px sidebar, as §1a says.
  - **Two canvases:** `.nx-terrain` is static (contours slot, roads, sea lanes) and redraws only on a theater or backing-size change. Anything that depends on `NodeView` is a separate light layer, `.nx-nodes` (tint, bridge crossbars, facility rings, node glyphs, capture arcs, stock bars, labels), redrawn on a theater or size change or when a drawn node field changes (`NodeLayer.setNodes`, called from `onFrame`), never per frame. Facility rings are on this layer because `ring_m` and `pos` come from `NodeView.facilities`, not from `TheaterStatic`.
  - **Contours:** `drawContours` draws nothing, with or without `terrain_ref`: no geometry is on the wire (Q-UX-20).
  - **Glyphs:** the owner frame is a chamfered octagon (COALITION), a spiked star (ENEMY) or a dashed circle (NEUTRAL); the kind glyph inside is a ring and dot (SANCTUARY), runway cross (AIRBASE), square (FOB), anchor (PORT), bars (BRIDGE) or star (HQ). Frame radius 15 to 31 px by kind. Before the first Snapshot a node has no `NodeView`: it shows the kind glyph dim, with no owner frame and no tint (DI-1).
  - **Labels:** only AIRBASE, FOB and PORT, the `campaign.strategic_node_kinds` default (`balance/default.yaml:153`), drawn with `fillText` at 17 px (map labels are not always-on HUD text, OV-1's 28 px floor does not apply).
  - **Bridges:** a 60 px crossbar over the node frame, normal solid. Down (`intact === false`): two dashed amber stubs shoved apart along the road. `intact: null` or no view draws the normal bar.
  - **Capture and stock:** capture is an arc outside the frame from 12 o'clock clockwise, in the capturing side's colour; stock is a 44 px bar under COALITION nodes with a non-null `stock_pct`, amber when `starvation` is not OK, plus the word LOW or EMPTY.
  - **Territory tint:** a 176 px radial pool at 15% alpha around each COALITION or ENEMY node, derived from `NodeView.owner` only; NEUTRAL and unknown stay untinted.
  - **Retired:** the NX-175 (b) `projector` (y unflipped, PAD fit) is gone. `theater/strait1.ts` stays as a marked legacy y-south copy for the no-token prototype path only; the live stage does not import it.
- **Perf (OV-10):** p95 < 12 ms at 1,000 entities with the static layer outside the frame loop; PROPOSED split: units 6 ms, FX 3 ms, interpolation 2 ms, 1 ms slack.
- **Not built here:** PiP (OV-6), 9:16 (OV-11), sectors, grid references and compass (§2a; sectors are not on the wire), supply flow (§3), altitude, follower and AUTO tags (OV-17, OV-2a), SPOTTED and painted markers (OV-18), curved roads (Q-VIZ-2), NOE visuals (Q-VIZ-4).

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

> **Deferred, not covered by the P2 approval (§0).**
The coalition is on the **left** and the enemy on the **right** (GAMEPLAY §9a). The main theater map is **fixed**, with no auto pan or zoom, so grid references stay stable for commands (Q-UX-10). The right sidebar covers enemy rear territory, so the fixed framing must keep the contested area within the left 70% of the map area. **Coordinates and framing (Q-UX-18, Q-UX-19):** world `y_m` grows north (map convention; Canvas2D draws y down, so the overlay projector flips), and theaters are authored that way (strait-1 mirrored in NX-507). The fixed frame fits the whole theater (`bounds_m`) to the map area, the sidebar covers its rightmost (enemy rear) part, and each theater keeps its contested zone in its left 70 %. Vertical 9:16 (P3, OV-11): the map rotates so the coalition is at the **bottom** and the enemy at the **top** (Q-GD-13), and the whole map is shown scaled down, never cropped, so grid references stay stable there too (Q-ALN-19).

## 1b. HUD tiers (Q-UX-11)
- **OV-12 Always on (16:9):** the momentum bar, objective, threat tier and how-to-play strip. The **GM badge** is also always on while a human GM is in control (Q-RB-7, Q-AI-8) and is absent otherwise. This holds on every layout, 9:16 included (Q-ALN-17).
- **OV-13 Interrupt toasts:** rally calls, Static mastermind taunts, major alerts and the **Latest Major Event** (Q-ALN-18) appear as toasts for a few seconds (duration TBD), then clear. Toasts never cover the always-on elements.
- **OV-14 One rotating panel** (P2 members narrowed by §0.6; the rest of the list is deferred): a single panel slot cycles its members every `hud.rotation_s` (PROPOSED ~15 s; real time, Q-CFG-8). Default members: **NEEDED jobs** (shown at double frequency), **reserve queue**, **operator breakdown**, **Top Commanders** (Q-ALN-18) and **explainer**. **Active Packages** joins the members in P4, when packages ship (Q-ALN-18). Rotation timing and membership are admin-configurable in the Command Center.
- **OV-15 9:16 tiers:** the momentum bar, objective and how-to-play strip are persistent; the threat tier joins the rotating panel. The **GM badge** stays persistent at 9:16 whenever a human GM is in control (Q-ALN-17).
- **OV-26 Threat sitrep stack** (NX-496, Q-UX-13): every `ThreatAdaptation` event (CONTRACTS §6, all eight categories) becomes a card in a stack at the top right, under the always-on bar, at most 30% of the screen wide (lines wrap), over the enemy rear the right sidebar covers (§1a); it never covers the OV-12 elements. It is how the "visible last stand" (GAMEPLAY §9) shows on stream.
  - **Card:** a kicker line (tier word · sector name) and the sitrep line, names from the theater (an id the theater lacks shows as the id; a missing node as `—`, DI-1). Every line is at least 28 px (OV-1), text only (OV-9).
  - **Per category (tier, sitrep line, life in game time):** SANCTUARY_AT_RISK: LAST STAND, "NULL strikes <node>, the sanctuary is at risk", 60 s. HOLD_AT_RISK: ALERT, "NULL moves on <node>, the hold is at risk", 30 s. STAGING_LAUNCHED: ALERT, "NULL assault launching from <sector>", 30 s. STAGING: ALERT, "NULL forces are massing in <sector>", 30 s. STRIKE_DOWNED: WIN, "NULL strike package downed near <node>" plus "Credit: <callsign>, …" (the first 3 `credit_ids` the frame can name, then `+N` for the rest), 20 s. IADS_REINFORCED UP: INTEL, "NULL reinforces its air defense in <sector>", 15 s. CONVOY_ESCORT UP: INTEL, "NULL convoys now run with escorts in <sector>", 15 s. Any DOWN: EASING, "NULL air defense back to normal in <sector>" or "NULL convoy escorts stand down in <sector>", 15 s. STAGING_DISPERSED: EASING, "massing disperses" (the sector is in the kicker), 15 s. The quoted owner wordings are the contract's; the INTEL and EASING lines are the overlay's (PROPOSED). Lives are PROPOSED and count game ticks (10 Hz), so a paused world (OV-21) keeps its cards.
  - **Priority:** LAST STAND, then ALERT (hold, launch, massing), WIN, INTEL, EASING; within a category the newest first. At most 3 cards show; the rest wait (and expire on their own clocks) behind a "+N more" line.
  - **Dedupe:** one card per slot, sector and node. A newer event replaces the older card (a repeat refreshes its life); STAGING, STAGING_LAUNCHED and STAGING_DISPERSED share a slot, so a payoff closes its sector's massing card; a DOWN replaces its UP. An event with an `event_seq` at or below the card's (a replay after reconnect) changes nothing. An event from another `campaign_id` clears every card first (a new campaign restarts seq and tick).
  - **Readability (OV-3):** each tier has its own shape (diamond, triangle, circle, square, down-triangle) and word, and colour only repeats them: LAST STAND is the one filled card (Static magenta, dark text), ALERT amber, WIN lime, INTEL light grey, EASING grey. No motion. At 9:16 (OV-11, not built) the stack sits full width under the persistent HUD.
- During season overtime the HUD shows "Season ends after this campaign" (Q-PROG-9). Before the weekly maintenance window the HUD announces it in advance (Q-OPS-9; lead time TBD). The tier for both notices is set in overlay layout v2 (NX-313).

## 1c. Pause scenes and time display

> **Deferred, not covered by the P2 approval (§0).**
- **OV-17 Following (Q-GP-31):** a unit with followers shows a small "+N following" tag beside its callsign (from `follower_count`); a column of trucks may draw as one grouped symbol with a count. No line is drawn per follower.
- **OV-18 Fog of war (FOG-OF-WAR):** last-known tracks draw as the frozen symbol, dimmed, with an age label; the painted flag adds a marker; own units being tracked show a SPOTTED badge; emitting enemy sites show an "on" indicator; blobs may get a cosmetic offset derived from the blob id. Playwright snapshot covers one of each.
- **OV-19 Threat tier labels (Q-TD-1):** the HUD shows PATTERN_OF_LIFE, ALPHA and BRAVO through localization keys `hud.tier.<tier>`; Pattern of Life reads as a calm state, not an alert.
- **OV-16 COMMS RESTORED** (Q-OPS-8): when the broadcast returns after an offline auto-pause (reason TECHNICAL), the overlay shows "COMMS RESTORED" with a 30 s countdown, then the sim auto-resumes.
- **OV-23 Maintenance scene** (Q-OPS-9): while the sim is paused for the weekly maintenance window (reason MAINTENANCE), the stream shows a "back at HH:MM" scene with a campaign recap and leaderboards. The campaign is still live during maintenance, so this recap is built from the redacted coalition view (FOW-1).
- **OV-24 Ceasefire scene** (Q-OPS-9): when the owner triggers Ceasefire (one click or hotkey), the sim pauses, OBS switches to a light scene (banner + leaderboard), and heavy overlay rendering stops to free the GPU (which layers count as heavy: TBD, measured on the reference host). One-click resume shows a countdown (length TBD).
- **OV-25 Time display** (Q-CFG-8): the overlay is one video for every viewer, so it shows relative times ("in 12 min"). Where an absolute time is needed (e.g. OV-23's "back at HH:MM"), it shows UTC plus one configured broadcast time zone (config key TBD). It never uses the browser's locale or zone.
- **OV-21 Paused world** (Q-ALN-2): while `Hud.campaign_clock.paused` is true, the whole world is frozen (STATE-MACHINES-AND-FLOWS §4.4). The overlay draws units at their last server positions with no extrapolation (OV-7), and the OV-8 heartbeat keeps changing every second so a pause is never mistaken for a frame freeze. Overlay feedback for commands that still work while paused (`!me`/`!status` highlight, reserve-queue position) behaves as when running. A STAFF pause has no dedicated scene: while `Hud.campaign_clock.pause_reason` is `STAFF`, the HUD shows a simple **"PAUSED — stand by"** banner (Q-ALN-32). The banner never shows the sub-reason (Q-ALN-31) or the staff note. The overlay never receives the sub-reason at all: it gets only the pause category it needs to pick the scene or banner (`Hud.campaign_clock.pause_reason`, Q-ALN-39).
- **OV-22 Post-campaign reveal** (Q-ALN-21): FoW applies only while the campaign is live, including the OV-16, OV-23 and OV-24 pause scenes. Once the campaign has ended (`CampaignEnded`), recaps, archives and "what you didn't see" reveals may show the full world, exempt from FOW-1.

## 2. Requirements
Approved: OV-1, OV-7 (state store), OV-8, OV-9, OV-10, as sharpened in §0. Every other requirement below is Deferred, not covered by the P2 approval.
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
- **OV-8 Resilience.** Reconnect per WP-5 and the banners of §0.3 (WP-1, WP-5). A heartbeat element changes every second so the frame-freeze probe can detect stalls.
- **OV-9 Security.** No `innerHTML`, a strict CSP, and no remote resources (fonts are bundled). No third-party trackers, cookies or analytics scripts (Q-DM-3).
- **OV-10 Performance.** p95 frame time under 12 ms on the reference host: the owner's i7-8700 + GTX 1070 8 GB under WSL2, re-baselined when the planned new PC replaces it (Q-TEST-1). The static terrain layer is pre-rendered.
- **OV-11 Vertical 9:16 variant (P3).** A separate route that shows the **full map scaled down** (rotated per §1a) with the **PiP below it** and the HUD stacked. It never crops or pans around the PiP focus, so grid references stay stable (Q-ALN-19, Q-UX-10). OBS uses Aitum Vertical or a second browser source.
- **OV-20 Placeholder art** (Q-BRAND-5): during alpha and testing, AI-generated art may appear only as a placeholder, and the stream carries an on-stream PLACEHOLDER note while any is shown. Every asset is recorded in the provenance register with `ai_generated` and `status` (placeholder/final); a release build containing an `ai_generated` or placeholder asset fails the CI release gate (NX-318).

## 2a. Map annotation layer (owner requirement, 2026-10-17)

> **Deferred, not covered by the P2 approval (§0).**
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

> **Deferred, not covered by the P2 approval (§0).**
Owner decisions Q-BRAND-1, Q-STYLE-1, Q-STYLE-2 (2026-10-17); exact values go in the brand and style guide (NX-274):
- **Colors:** near-black base; Quorum cyan; The Static glitchy magenta/red with a crackle effect; **amber** for warnings and supply; **lime/violet** accents for fun moments (rally, rescue). Validated for colorblind safety (OV-3); shape coding keeps friend/foe readable regardless of color. Tone: "Signal" radar war room, fun and friendly, not grim.
- **Typography:** a clean technical UI font with **tabular numerals**, plus a **bold display font** for big moments. Free/open licenses that permit redistribution only (e.g. OFL), bundled with the overlay (no remote fonts, OV-9) and listed in the provenance register (Q-LEGAL-4, NX-318).
- **Supply routes (Q-UX-6):** route lines with flow brightness, a per-base supply gauge, cut routes red/dashed, starving bases blink gently. When an operator orders a move (`!rebase`, `!target`), draw the route with distance/ETA and fuel reach; out of range shows "cannot reach: fuel" and suggests the nearest reachable base (§2a annotations).
- **Text:** English first, all strings through localization keys (Q-UX-5).
- **Map:** glowing phosphor contours rendered as thin lines with low alpha; terrain shown as topographic contours plus subtle elevation shading (C69).
- **Static mastermind visual** (Q-STYLE-5, P3): a small, brief, glitchy corrupted-signal portrait/logo that crackles on with taunts or big events (as an OV-13 toast); playful, not corny. Coalition intel labels the mastermind by its codename **NULL** (e.g. "SIGNAL SOURCE: NULL"); code uses an internal id, never the literal null. The name it signs its own broadcasts with is TBD (Q-BRAND-4).

## 4. Tests
Playwright visual snapshots of fixture states (TESTING-STRATEGY §3.7), including each HUD tier at 16:9 and 9:16 (with the GM badge present at both while a human GM is in control, Q-ALN-17), a 9:16 snapshot proving the whole map is visible uncropped with the PiP below it for PiP foci at opposite map corners (Q-ALN-19), the AUTO and UNIDENTIFIED tags and the OV-16, OV-23 and OV-24 scenes; a paused-state test that unit positions do not move and the heartbeat keeps changing (OV-21); a snapshot of a STAFF pause showing the "PAUSED — stand by" banner with no sub-reason or note text, and the banner absent once resumed (Q-ALN-32); a fake-clock test that OV-25 renders relative times and UTC plus the broadcast zone; the palette script, an XSS fixture (SEC-OV-1), and a reconnect test.

OV-26 (NX-496): Vitest for the category mapping, priority, expiry, dedupe and the event-to-HUD path (`apps/overlay/src/__tests__/threat-sitrep.test.ts`). Screenshots of every category were reviewed by hand for NX-496 (manual QA evidence in the PR); no automated or committed snapshot covers OV-26 yet.

**Wall-clock budgets (NX-491).** A correctness run never asserts time. The frame-time and fps assertions in `apps/overlay/src/__tests__` go through `perf-gate.ts` and run only when `NEXUS_PERF=1` or `GITHUB_ACTIONS=true` (GitHub sets the latter on every runner, so CI's `pnpm test` enforces them). `make check-overlay` skips them; run `NEXUS_PERF=1 pnpm test` in `apps/overlay` to enforce them locally.

## Readability rules (moved from GAMEPLAY §10, Q-GP-9)
Always visible: the momentum bar, the current objective with its timer, the director threat level, and a "how to play" line. Everything else (NEEDED jobs, reserve queue, operator breakdown, explainer) shares one rotating panel or appears as short interrupt toasts; at 9:16 the threat level joins the rotation (Q-UX-11, OVERLAY). A newcomer must be able to tell who's winning within 5 s (alpha exit criterion).
