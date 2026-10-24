# Visual Design Language & Asset Brainstorming Catalog

> **Operation Nexus / Hiveplex Creative Visual Direction**
> *Codename: "Signal"*
> *Tone: Tactical Radar War Room · High Energy · Playful & Non-Grim*
> *Storage: External Brain Artifact (Decoupled from Git Repository)*

---

## 1. Core Visual DNA & Aesthetic Tenets

### 1.1 The "Signal" Identity
The visual soul of Hiveplex is **"The Living Glass"** — an ambient military radar console operating in the dead of night, where every pixel feels like raw tactical telemetry, radio signals, and electrical current flowing through wire and air.

```
       [ DARK CRT VOID ]  ────────►  Near-black slate (#070b10)
              │
              ├──► [ QUORUM CYAN ]      Sharp, crisp, coherent vector arrays
              │
              ├──► [ THE STATIC ]       Glitchy, jagged magenta/red with crackle & VHS noise
              │
              └──► [ TACTICAL TELEMETRY] Phosphor green radar sweeps & warm amber supply lines
```

### 1.2 The Three Fundamental Readability Rules
1. **The 5-Second Glance Test (OV-1):** A viewer stumbling into the livestream while scrolling Twitch or YouTube Shorts must immediately know:
   - Who is winning (Strategic Momentum Gauge / Signal Strength).
   - What the current 15-minute goal is (Objective banner with countdown).
   - How to immediately spawn their own unit (`!join strike` in the bottom ticker).
2. **Colorblind-Safe Dual Encoding (OV-2 / OV-3):** Information is never conveyed through color alone:
   - **Coalition (Quorum):** Smooth angular geometry (chevrons, sharp triangles, diamonds, clean circles) + Cyan (`#00E5FF`).
   - **The Static (Enemy):** Jagged sawtooth silhouettes, erratic polygon vertices, flickering offset duplicates + Glitch Magenta (`#FF0055`).
3. **No Visual Clutter (OV-4):** At 1080p, only the user's unit (when typing `!me`), top commanders, and the active PiP combat target have visible text callsigns. All other 500+ units are crisp shape-coded glyphs with dynamic speed vectors.

---

## 2. Color Palette & Token System

All colors are designed for deep OLED / dark CRT displays with high contrast:

| Token Name | Hex Code | Purpose | Visual Feel |
|---|---|---|---|
| `--color-void-dark` | `#070b10` | Base background slate | Deep vacuum black with slight naval blue tint |
| `--color-grid-lines` | `#111d28` | Topo contours & theater grid | Subtle phosphor wireframe, non-distracting |
| `--color-quorum-primary` | `#00e5ff` | Coalition units, friendly bases | Electric Cyan / Coherent laser pulse |
| `--color-quorum-glow` | `rgba(0, 229, 255, 0.4)` | Friendly halos, shields, radar pings | Radiant phosphor bloom |
| `--color-static-primary` | `#ff0055` | Static enemy swarm, hostile missiles | Glitch Crimson-Magenta / Hostile frequency |
| `--color-static-glitch` | `#ff00aa` | Static mastermind taunt, scanline tears | Chromatic aberration fringing |
| `--color-supply-amber` | `#ffaa00` | Supply trucks, fuel conduits, logistics | Industrial amber glow, warm and steady |
| `--color-radar-green` | `#00ff66` | Radar sweep cones, active sensor arcs | CRT oscilloscope green |
| `--color-contested-neutral`| `#e0e6ed` | Neutral crossings, unaligned nodes | Crisp chalk white / high-visibility beacon |
| `--color-alert-red` | `#ff3333` | Starving bases, destroyed bridges, SAM lock | Urgent flashing strobe |

---

## 3. Shape Symbology & Glyph Matrix

Units use custom simplified vector glyphs optimized for instant recognition at small pixel scales ($14\text{px} \dots 24\text{px}$ on screen):

### 3.1 Air Units
- **Strike Fighter (Coalition):** Swept-wing delta chevron pointing in direction of travel:
  $$\Delta \quad \text{with double rear afterburner tick}$$
- **Recon UAV (Coalition):** High-aspect glider diamond with a central scanning circle:
  $$\diamondsuit \quad \text{with emitting concentric pulse rings}$$
- **Enemy Fighter (The Static):** Jagged inverted arrowhead with broken flickering wingtips.
- **Enemy Recon Swarm:** Asymmetric cluster of triangular shards that pulse erratically.

### 3.2 Ground Units & Logistics
- **Logistics Truck (Coalition):** Hexagonal supply capsule with directional chevron trail:
  $$\hexagon \quad \text{pulsing amber with small supply crate count chip}$$
- **Follower Convoys:** When units follow a leader (OV-17), followers compress into a stacked column glyph with a neat badge: `[TRUCK] +3`.
- **Garrison Infantry / Base Security:** Shield glyph with internal anchor dot:
  $$\Box \quad \text{with internal crosshair}$$
- **Static Ground Spearhead:** Spiked trapezoid moving along road axes.

### 3.3 Infrastructure & Facilities
- **Airbase:** Large dual-ring icon with runway vector line.
- **Forward Operating Base (FOB):** Sturdy octagonal fortress node with supply level dial.
- **Radar Station:** Concentric emitting arcs (rotates actively; goes dark when destroyed or jammed).
- **SAM / Air Defense Battery:** Triangle encased in a dotted interception perimeter ring.
- **Bridge / Chokepoint:** Dual parallel anchor brackets spanning river/strait. Breaks into red dashed markers when severed.

---

## 4. Visual Styles: 4 Creative Approaches

```carousel
### Style 1: "Signal Vector" — The Pure Radar War Room (2D Phosphor)
Inspired by NORAD tactical consoles, DEFCON, and HighFleet.
- **Background:** CRT scanlines with subtle curvature and edge vignette.
- **Terrain:** Glowing topographic contour rings with elevation gradients.
- **Effects:** Sweeping radar lines with phosphor trail persistence, SAM engagement circles with transparency falloff, glowing supply highways.
- **Best For:** Ultra-low CPU/GPU overhead in OBS (<8ms frame time), maximum tactical readability.
<!-- slide -->
### Style 2: "Holographic Tabletop" — 2.5D C2 War Room (Isometric WebGL)
Inspired by Star Wars briefing tables, Ender's Game, and Homeworld C2.
- **Background:** High-tech command deck with subtle ambient reflection and hexagonal grid depth.
- **Terrain:** 2.5D extruded wireframe topography with relief shading and deep shadows.
- **Effects:** Air units cast directional light cones and shadows onto the terrain below; missiles fly on 3D ballistic parabolic arcs.
- **Best For:** High streamer production value, jaw-dropping visual appeal for devlogs and YouTube shorts.
<!-- slide -->
### Style 3: "FLIR Thermal & Tactical Recon" — Modern Glass Cockpit
Inspired by Boeing Link-16, AC-130 gunship HUDs, and modern military multi-function displays (MFDs).
- **Background:** Monochromatic FLIR satellite terrain view with simulated sensor grain.
- **Overlay:** High-density telemetry readouts, compass heading ladders, coordinate grid tickers.
- **Effects:** Targets flash with box tracking brackets, laser designation dots, and predictive vector leads.
- **Best For:** Mil-sim hardcore fans, intense tactical combat focus, and the PiP Intercept Scope.
<!-- slide -->
### Style 4: "Vector Arcade Swarm" — Playful Neon Defense
Inspired by Geometry Wars, Polybius, and modern neon roguelites.
- **Background:** Star-field vacuum with pulsing neon shockwaves.
- **Effects:** Particle trails behind every fighter, screen-space chromatic aberration on Static explosions, energetic electric arcs along supply lines.
- **Tone:** Leans heavily into the "playful, fun, non-grim co-op" mandate, making chat commands feel like an arcade spectacle.
```

---

## 5. The PiP (Picture-in-Picture) Intercept Scope

Located in the top-right corner of the broadcast, the PiP is the **"Drama Magnifier"** (OV-6, ADR-0005). While the main theater map remains fixed and stable, the PiP automatically locks onto the hottest combat event:

```
┌────────────────────────────────────────────────────────┐
│ [LIVE INTERCEPT] 04:12:89 ZULU         CAM: RECON-02   │
│ TARGET: ENEMY_FIGHTER_08 (BANDIT)      Pk: 78% [LOCK]  │
├────────────────────────────────────────────────────────┤
│                                                        │
│                    \     /                             │
│                  -- [ + ] --                           │
│                    /     \                             │
│                                                        │
│       >>> [VIPER-04]                     ▲             │
│            TRACER ====>          BANDIT [AI]           │
│                                                        │
│ SPEED: Mach 1.4       ALT: 18,000 FT     RNG: 4.2 KM   │
└────────────────────────────────────────────────────────┘
```

- **Visual Modes for PiP:**
  - **Thermal White-Hot:** Inverted monochrome sensor view showing heat signatures of afterburners and explosions.
  - **Tactical Intercept Scope (MVP):** Close-up 2D vector wireframe with lead-angle crosshairs, missile trajectory arcs, and weapon lock indicators.
  - **3D Dogfight Wireframe (P3):** Rotating 3D vector wireframe models of engaging aircraft and SAM intercept trajectories.

---

## 6. The Static Mastermind "NULL" Glitch Presentation

When the AI Threat Director escalates or taunts chat:
- **Corrupted Signal Toast (OV-13, Q-STYLE-5):** A CRT transmission interrupt glitch sweeps horizontally across the top-right panel.
- **Visual Icon:** A shifting, distorted holographic skull/signal wave glyph flickering between magenta and cyan chromatic fringes.
- **Text Stamp:** `[SIGNAL SOURCE: NULL]` rendered in monospaced glitch font with random binary characters decaying into the actual taunt message.
- **Ambient static:** Faint analog TV fuzz and horizontal sync tears appear briefly along the border of the stream before clearing.

---

## 7. Stream Layout Wireframes (16:9 vs 9:16)

### 7.1 Standard 16:9 Broadcast Overlay (1920 × 1080)

```
0px                                                                           1920px
┌──────────────────────────────────────────────────────────────────────────────────┐ 0px
│ [STRATEGIC MOMENTUM: ██████████░░░░ 68%]  │ OBJ: HOLD STRAIT 08:45 │ THREAT: BRAVO│ 72px
├───────────────────────────────────────────────────────┬──────────────────────────┤
│                                                       │ [PiP INTERCEPT SCOPE]    │
│                                                       │ Live Tactical Kill-Cam   │ 360px
│              MAIN THEATER C2 MAP (Canvas)             ├──────────────────────────┤
│                                                       │ [ROTATING PANEL]         │
│  - Topographic contour lines                          │ • NEEDED: Supply to West │
│  - Contested frontline & strait                       │ • Active Reserve Queue   │
│  - Friendly Bases (West) -> Enemy Bases (East)        │ • Top Fleet Commanders   │ 720px
│  - Active units, SAM envelopes, supply arteries       ├──────────────────────────┤
│                                                       │ [SITREP TACTICAL LOG]    │
│                                                       │ 10:14 FOB Alpha Supplied │
│                                                       │ 10:13 Bandit Down (SEAD) │ 980px
├───────────────────────────────────────────────────────┴──────────────────────────┤
│ TICKER: [HOW TO PLAY: Type !join strike | recon | logi]  •  VIPER-04 spawned...  │ 1080px
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Vertical 9:16 Broadcast Overlay (1080 × 1920 - YouTube Shorts / TikTok)

```
0px                                                              1080px
┌─────────────────────────────────────────────────────────────────────┐ 0px
│ [STRATEGIC MOMENTUM: ████████░░░ 62%]  OBJ: BRIDGE 08:45            │ 120px
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                     FULL THEATER C2 MAP                             │
│                  (Rotated 90°: Coalition at                         │
│                    Bottom, Static at Top)                           │
│                                                                     │ 1080px
├─────────────────────────────────────────────────────────────────────┤
│ [PiP INTERCEPT SCOPE / KILL-CAM]                                    │
│ High-intensity zoomed dogfights and missile strikes                 │ 1500px
├─────────────────────────────────────────────────────────────────────┤
│ [ROTATING STATS & SITREPS]                                          │
│ NEEDED Jobs • Active Commanders • Threat Tier                       │ 1780px
├─────────────────────────────────────────────────────────────────────┤
│ [HOW TO PLAY] Type !join strike in chat to spawn your jet now!       │ 1920px
└─────────────────────────────────────────────────────────────────────┘
```
