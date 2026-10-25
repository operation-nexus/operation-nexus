# Unified Three-Pillar Visualization & Tactical C2 Patterns

This reference codifies repeatable UI, rendering, and interaction patterns for Hiveplex / Operation Nexus visualizers.

---

## 1. The Three Visual Pillars

| Pillar | Technology | Visual Paradigm | Primary User / Role | Key Features |
| :--- | :--- | :--- | :--- | :--- |
| **Pillar 1: Tactical GIS (C2)** | HTML5 Canvas 2D (`L.CRS.Simple`) | Military Common Operational Picture | Theater Commander / Web Replay | 10km MGRS grid, MIL-STD-2525D frames, SAM MEZ rings, interactive coordinate cursor, shaded relief |
| **Pillar 2: Textured RTS (3D)** | WebGL / Three.js PBR | Solid RTS Battlespace | Broadcast Stream / Video Clip Director | Dynamic elevation vertex splatting (sand, olive grass, rock, snow), draped road ribbons, 3D fighter jets, chase cam, thermal FLIR PiP |
| **Pillar 3: Holographic (3D)** | WebGL / Three.js Wireframe | Glowing Sensor Tabletop | Abstract Sensor Manager / Cyber Mode | High-contrast wireframe terrain, sweeping radar scan cone, volumetric SAM threat domes |

---

## 2. Shared Interface & Telemetry Standards

1. **Order of Battle (OOB) Fleet Sidebar**:
   - Right-aligned panel listing all active air and ground assets with status, altitude, airspeed, and fuel percentage.
   - Clicking any asset focuses the camera and populates the targeting card.

2. **MGRS Cursor Crosshairs**:
   - Hovering over any map coordinate translates screen pixels $\to$ simulation meters $\to$ MGRS string (`38S LD 425 218`) and samples continuous elevation (`sampleStraitElevation(x, y)`).
   - Left-clicking automatically formats a valid unit command (`!strike <grid>`).

3. **Time Scrubbing & Playback**:
   - Bottom status strip provides standard playback rate controls (`Pause`, `1x`, `2x`, `5x`).
   - UTC simulation clock (`HH:MM:SS.ssZ`) and real-time event ticker log.

4. **Multi-Camera Quick Toggles**:
   - `Orbit`: Free orbital examination ($360^\circ$ rotation, smooth damping).
   - `Chase`: Locked behind the selected unit with matching velocity vector.
   - `God View`: Top-down orthographic/nadir perspective directly above the theater center.
