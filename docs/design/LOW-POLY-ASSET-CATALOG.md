# Low-Poly Faction 3D Asset Geometry Catalog

This document specifies the low-poly 3D geometry catalog for **Operation Nexus / Hiveplex** (NX-176).
Assets are procedurally generated via `tools/assets/generate_lowpoly_assets.py` into `content/assets/3d/*.obj`. They are not tracked in git (owner, 2026-10-25): regenerate them with the command below; the output is byte-identical.

## 1. Design & Performance Constraints

- **Strict Triangle Budget**: < 500 triangles per asset (actual catalog models average 36–132 triangles).
- **Draw Call Efficiency**: Geometries are designed for batched instanced rendering (`InstancedMesh` in Three.js or standard instanced WebGL arrays).
- **PBR Material Slots**:
  - `Slot 0 (Base Armor)`: Matte faction camo / metal (Coalition Blue `0x2563eb`, Static Dark Charcoal `0x18181b`).
  - `Slot 1 (Secondary/Accent)`: High-visibility trim (Signal Amber `0xf59e0b` or Scarlet `0xef4444`).
  - `Slot 2 (Glass/Canopy/Emissive)`: Low roughness cockpit glass or cyan afterburner plume.

---

## 2. Catalog Assets

| Asset Slug | Object Name | Dimensions (W x H x L metres) | Vertices | Triangles | Primary Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `striker_jet.obj` | `StrikerJet` | $12.0 \times 3.5 \times 14.0$ | 37 | 54 | Air Domain Strike & Combat Patrol |
| `logistics_truck.obj` | `LogisticsTruck` | $3.2 \times 3.8 \times 11.0$ | 88 | 132 | Ground Supply Convoys & Resupply |
| `sam_launcher.obj` | `SamLauncher` | $3.6 \times 3.5 \times 9.0$ | 32 | 48 | Surface-to-Air Defense Battery |
| `radar_spire.obj` | `RadarSpire` | $8.0 \times 19.0 \times 6.0$ | 28 | 36 | Long-Range Early Warning Radar |
| `truss_bridge.obj` | `TrussBridge` | $16.0 \times 18.0 \times 40.0$ | 40 | 60 | Neutral Water Channel Crossing Span |

---

## 3. Detailed Topology & Kinematic Hardpoints

### 3.1 Striker Jet (`striker_jet.obj`)
- **Fuselage**: Hexagonal tapered nose cone with swept delta wings and canted twin vertical stabilizers.
- **Hardpoints**:
  - Wingtip Rails: $( \pm 5.8\text{m}, 1.0\text{m}, -1.0\text{m} )$ for Air-to-Air Missiles.
  - Centerline Pylon: $( 0.0\text{m}, 0.2\text{m}, 0.0\text{m} )$ for heavy ordnance.
  - Afterburner Pivot: $( 0.0\text{m}, 1.0\text{m}, -7.0\text{m} )$ for dynamic thrust plume shader.

### 3.2 Logistics Truck (`logistics_truck.obj`)
- **Chassis**: 8-wheel all-terrain suspension with reinforced armored cab and standardized $20\text{ft}$ supply container.
- **Hardpoints**:
  - Cargo Attachment: $( 0.0\text{m}, 2.0\text{m}, -1.8\text{m} )$ (allows swapping fuel tank, ammo box, or radar pod).
  - Headlight Emitters: $( \pm 1.2\text{m}, 1.6\text{m}, 5.2\text{m} )$.

### 3.3 SAM Launcher (`sam_launcher.obj`)
- **Chassis**: Heavy tracked carrier base.
- **Turret**: Dual angled missile launch tubes inclined at $35^\circ$ with $360^\circ$ azimuth rotation pivot at $( 0.0\text{m}, 1.4\text{m}, -0.5\text{m} )$.

### 3.4 Radar Spire (`radar_spire.obj`)
- **Structure**: Concrete hexagonal bunker base with tubular lattice mast.
- **Antenna**: Curved elliptical dish on motorized gimbal at $+17.0\text{m}$ elevation with continuous $30\text{ RPM}$ rotation.

### 3.5 Truss Bridge Span (`truss_bridge.obj`)
- **Deck**: Dual-lane asphalt roadway conformed to physical elevation budget ($+14.0\text{m}$ above sea level).
- **Substructure**: Deep concrete collision piers extending to $-8.0\text{m}$ into the submarine trench.

---

## 4. Pipeline Integration

Assets are baked and updated directly via CLI:
```bash
python3 tools/assets/generate_lowpoly_assets.py --output-dir content/assets/3d
```
All models are verified against the unit test suite (`--test`) enforcing strict polygon limits and vertex bounds.
