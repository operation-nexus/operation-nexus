# RFC: Universal Unit POV, Cockpit, and Operator Camera Contracts

**Document ID**: `RFC-UNIT-POV-002`  
**Target Milestone**: NX-176 / NX-233 Replay & Visual Architecture  
**Authors**: Hiveplex Core Visualization & Simulation Architecture  
**Status**: PROPOSED  

---

## 1. Problem Statement & Motivation

Existing simulation views in Operation Nexus rely primarily on external spectator perspectives:
- **Pillar 1**: 2D Tactical C2 GIS (top-down macro theater view).
- **Pillar 2**: 3D Low-Angle RTS (orbital or trailing chase camera).
- **Pillar 3**: Holographic Tactical Tabletop (isometric wireframe).
- **Pillar 4**: Cognitive Neural Battlespace (AI causal decision trees).

While these exterior perspectives excel at operational situational awareness, they lack the visceral, human-scale perspective of theater combat:
1. **Pilot Cockpit POV**: Viewing supersonic dogfights, terrain masking in canyons, and missile locks through the canopy glass with a collimated heads-up display (HUD).
2. **Logistics Truck Driver POV**: Viewing tactical highway operations from behind the steering wheel through an armored split-windshield, observing a bridge collapse or air attack 200m ahead.
3. **Dismounted Infantry / Platoon POV**: Viewing urban or mountain firefights through weapon optics (ACOG / Red Dot reticles) with squad telemetry.
4. **Sensor Operator Gimbal POV**: Viewing target areas through gyro-stabilized electro-optical / infrared (EO/IR) reconnaissance sensor suites.

To support immersive narrative video creation, viral short-form clips, and dynamic live broadcast director cuts without coupling renderer code to the simulation kernel, this RFC establishes a standardized **`pov_profile` schema** for all unit contracts and definitions.

---

## 2. Unit POV Contract Schema (`pov_profile`)

Unit contracts defined in `content/units/*.yaml` or the simulation unit catalog may optionally declare a `pov_profile`. Units without this block fallback to default trailing chase cameras.

```yaml
pov_profile:
  # POV Category Archetype
  pov_type: FIGHTER_CANOPY    # FIGHTER_CANOPY | VEHICLE_CABIN | INFANTRY_OPTIC | GIMBAL_TURRET | SENSOR_MAST

  # Eye position in unit local coordinates [lateral_x, vertical_y, forward_z] in meters
  eye_offset_m: [0.0, 1.25, 1.80]

  # Default forward optical vector in unit local coordinates
  forward_vector: [0.0, 0.0, 1.0]

  # Field of View in horizontal degrees (Standard tactical FOV: 70°-85°)
  fov_deg: 75.0

  # Head-look rotational clamping relative to unit heading [min_deg, max_deg]
  look_clamp_deg: [-70.0, 70.0]
  pitch_clamp_deg: [-30.0, 55.0]

  # Cockpit Overlay and Symbology Configuration
  cockpit_overlay:
    overlay_type: COLLIMATED_HUD   # COLLIMATED_HUD | ARMORED_WINDSHIELD | OPTICAL_RETICLE | GIMBAL_SENSOR
    symbology_color: "#00ff66"     # Tactical neon HUD green (#ef4444 for adversary static units)

    # Heads-Up Display Telemetry Modules
    hud_modules:
      - type: BORESIGHT_CROSSHAIR
      - type: FLIGHT_PATH_MARKER   # Velocity vector circle with wings
      - type: PITCH_LADDER
        step_deg: 10
        clamp_deg: 20
      - type: COMPASS_RIBBON
        position: TOP_CENTER
      - type: AIRSPEED_TAPE
        position: LEFT
        unit: KTS
      - type: ALTITUDE_TAPE
        position: RIGHT
        unit: FT_MSL
      - type: RADAR_TARGET_DIAMOND # BVR and dogfight target lock diamond
        track_source: RADAR_TWS

    # Interior Cabin Modules (For Ground Vehicles)
    cabin_elements:
      windshield_frame: ARMORED_SPLIT_PILLAR
      steering_wheel:
        enabled: true
        position: BOTTOM_LEFT
        label: "NEXUS LOGI"
      instrument_cluster:
        analog_speedometer: true
        fuel_gauge: true
      tactical_mfd:
        enabled: true
        position: CENTER_CONSOLE
        feed: TACTICAL_ROUTE_NAVIGATION
      rearview_mirror:
        enabled: true
        position: TOP_CENTER
        reflection_feed: CAM_REAR_01
```

---

## 3. Unit Archetype Implementations

### 3.1 Tactical Fighter Jet (`FIGHTER_CANOPY`)
- **Applies to**: `VIPER-01`, `VIPER-02` (Coalition Strike Fighters), `BANDIT-04` (Static Interceptor).
- **Physical Mounting**: Eye mounted $+1.25\text{m}$ above fuselage centerline, $+1.80\text{m}$ forward of wings.
- **Visual Presentation**:
  - Arching composite canopy bow with subtle glass reflection sheen.
  - Collimated HUD focused at optical infinity: pitch ladder (+10°, 0°, -10°), waterline symbol (`-v-`), velocity vector, heading tape, airspeed tape (KTS / Mach / G-meter), barometric altitude, and radar altimeter.
  - Active weapon status: Master Arm, selected missile bay (`4x AAM-3 [ARMED]`), and gun round count.
  - Wingman awareness: In trail or echelon formations, the pilot can look sideways through the canopy to see `VIPER-02` flying off the wing.
  - Target lock diamond: Displays enemy target callsign, slant range ($\text{km}$), and closure rate ($\text{kts}$).

### 3.2 Logistics & Armored Ground Vehicles (`VEHICLE_CABIN`)
- **Applies to**: `MULE-01` (Heavy Logistics Hauler), upcoming MBTs, and Armored Personnel Carriers.
- **Physical Mounting**: Eye mounted inside armored driver cabin, elevated $+2.2\text{m}$ above road surface, offset $-0.45\text{m}$ to the left (driver seat).
- **Visual Presentation**:
  - Armored split ballistic glass windshield with reinforced A-pillars, top sun visor, and center vertical divider bar.
  - Heavy bolts and ballistic rubber seal gaskets.
  - Functional military steering wheel at bottom left with grip textures and coalition logistics insignia.
  - Center dashboard console featuring an illuminated tactical route MFD tablet:
    - Current road segment and speed governor (`55 KM/H`).
    - Waypoint destination (`WEST AIRBASE VIA NORTH FJORD`).
    - Bridge integrity status (`100% SECURE` vs `COMPROMISED`).
    - Terrain road clearance (`+0.14M CONFORMED`).
  - Top interior rearview mirror showing the road and terrain receding into the distance behind the vehicle.

### 3.3 Dismounted Infantry & Platoons (`INFANTRY_OPTIC`)
- **Applies to**: Future ground rifle squads, MANPADS anti-air teams, and forward observers.
- **Physical Mounting**: Shoulder/head level ($+1.65\text{m}$ above local terrain elevation).
- **Visual Presentation**:
  - Circular optical sight housing with anti-reflection honeycomb texture.
  - Mil-dot illuminated reticle with bullet drop compensator (BDC).
  - Top miniature compass azimuth tape with MGRS coordinates.
  - Squad status lower-third (squad strength, ammunition magazines, suppressive fire status).

### 3.4 Unmanned Aerial ISR (`GIMBAL_SENSOR`)
- **Applies to**: `STATIC-UAV`, `RECON-POD`.
- **Physical Mounting**: Gyro-stabilized under-nose gimbal turret.
- **Visual Presentation**:
  - Full-screen FLIR White-Hot, Black-Hot, or Optical 32x Zoom feed.
  - Azimuth/Elevation reticle relative to aircraft heading.
  - Slant range laser rangefinder (`LRF: 14,820M`).
  - Crosshair target designation with latitude/longitude/MGRS telemetry.

---

## 4. Replay & Automated Media Integration

### 4.1 Headless Cinematic Pass Recording
The Python headless recording harness (`tools/replay/render_cinematic_pass.py`) integrates unit cockpit POV passes:
```bash
# Capture full pilot cockpit dogfight pass
python3 tools/replay/render_cinematic_pass.py --pass cockpit-viper --out viper_cockpit.mp4

# Capture truck driver POV crossing the fjord viaduct (9:16 vertical short)
python3 tools/replay/render_cinematic_pass.py --pass cockpit-mule --aspect 9:16 --out truck_viaduct_short.mp4
```

### 4.2 Live Broadcast Director Logic
During 24/7 live streams, the Live AI Director switches to cockpit POV during high-intensity moments:
1. **Dogfight Ingress**: When `VIPER-01` closes within $35\text{km}$ of an adversary, cut from strategic C2 to Pilot Cockpit POV for a high-intensity $15\text{s}$ engagement lock.
2. **Convoy Chokepoints**: When `MULE-01` approaches a strategic bridge or pass, cut to Driver Cockpit POV to show the massive scale of the surrounding mountain terrain.

---

## 5. Architectural Invariants & Decoupling

1. **Kernel Purity (DATA-INTEGRITY DI-1)**:
   The simulation kernel in `services/sim` does not know or care about canvas rendering, windshield textures, or font sizes. It only manages position $(x, y, z)$, heading angle, velocity, and health.
2. **Deterministic Parity**:
   Unit POV coordinates are strictly computed from deterministic simulation state and constant `pov_profile` offsets, guaranteeing bit-for-bit camera reproduction on every replay.
3. **Graceful Fallback**:
   If a unit contract does not specify a `pov_profile`, presentation engines automatically fallback to a standard dynamic 3/4 trailing chase camera.
