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
  pov_type: FIGHTER_CANOPY    # FIGHTER_CANOPY | HELICOPTER_BUBBLE | VEHICLE_CABIN | NAVAL_BRIDGE | INFANTRY_OPTIC | GIMBAL_TURRET | WEAPON_SEEKER | AIR_DEFENSE_OPTIC

  # Eye position in unit local coordinates [lateral_x, vertical_y, forward_z] in meters
  eye_offset_m: [0.0, 1.25, 1.80]

  # Default forward optical vector in unit local coordinates
  forward_vector: [0.0, 0.0, 1.0]

  # Field of View in horizontal degrees (Standard tactical FOV: 70°-85°, Telephoto seeker: 15°-30°)
  fov_deg: 75.0

  # Head-look rotational clamping relative to unit heading [min_deg, max_deg]
  look_clamp_deg: [-70.0, 70.0]
  pitch_clamp_deg: [-30.0, 55.0]

  # Cockpit Overlay and Symbology Configuration
  cockpit_overlay:
    overlay_type: COLLIMATED_HUD   # COLLIMATED_HUD | HELO_GLASS | ARMORED_WINDSHIELD | NAVAL_WHEELHOUSE | OPTICAL_RETICLE | GIMBAL_SENSOR | WEAPON_TRACKER | SAM_OPTIC
    symbology_color: "#00ff66"     # Tactical neon HUD green (#ef4444 for adversary static units, #38bdf8 for naval)

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
      - type: ARTIFICIAL_HORIZON_6DOF # Dynamic horizon line rotating by -phi and translating by theta
      - type: G_METER                 # Live G-force indicator (1.0G to 9.0G)
        range: [1.0, 9.0]
      - type: BANK_ANGLE_SCALE        # Graduated bank arc with pointer
      - type: RADAR_OCCLUSION_STATUS  # [NOE CANYON MASKED] badge when DEM ridges block LoS
      - type: HOMING_BEACON_ARROW  # For CSAR: points to PRC-112 emergency beacon
        transponder_freq: 243.0MHZ
      - type: TIME_TO_IMPACT       # For missile seeker POV
        countdown_unit: SECONDS

    # Dynamic Exterior Visual Elements (Chase / Wingman Cameras)
    exterior_effects:
      vapor_ribbon_contrails:
        enabled: true
        g_threshold: 4.5
        emitter_offsets_m: [[-5.2, 0.1, -1.8], [5.2, 0.1, -1.8]] # Port/starboard wingtips

    # Interior Cabin Modules (For Ground, Helo & Naval Vehicles)
    cabin_elements:
      windshield_frame: ARMORED_SPLIT_PILLAR # ARMORED_SPLIT_PILLAR | HELO_BUBBLE_FRAME | NAVAL_BRIDGE_WINDOW
      steering_wheel:
        enabled: true
        position: BOTTOM_LEFT
        label: "NEXUS LOGI"
      cyclic_collective: # For helicopters
        enabled: true
      chin_bubble_glass: # For CSAR helicopters
        enabled: true
        downward_view: TERRAIN_LZ
      instrument_cluster:
        analog_speedometer: true
        fuel_gauge: true
        torque_meter: true
      tactical_mfd:
        enabled: true
        position: CENTER_CONSOLE
        feed: TACTICAL_ROUTE_NAVIGATION
      rearview_mirror:
        enabled: true
        position: TOP_CENTER
        reflection_feed: CAM_REAR_01
      naval_helm: # For naval ships
        compass_binnacle: true
        telegraph_throttle: true
        radar_ppi_scope: true
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

#### 3.1.1 6-DOF Dynamic Attitude Coupling in Cockpit HUDs
To deliver authentic tactical cockpit immersion without coupling rigid-body flight physics to the simulation kernel:
1. **Dynamic Pitch Ladder & Horizon Coupling**:
   - The artificial horizon line and pitch ladder rotate dynamically about the boresight marker by $-\phi$ (bank/roll angle) and translate vertically proportional to $\theta$ (flight pitch angle).
   - Solid positive climb rungs and dashed negative dive rungs tilt in real time with continuous roll damping.
2. **Dynamic G-Meter & Bank Angle Arc**:
   - Live digital and tape G-meter indicating instantaneous normal acceleration from `1.0G` (level flight) up to `9.0G` (maximum coordinated turn pull).
   - Bank angle pointer and graduated scale arc along the lower HUD perimeter displaying bank angle from $-75^\circ$ to $+75^\circ$.
3. **Radar Occlusion & Terrain Masking Indicator**:
   - `[NOE CANYON MASKED]` status indicator flashes in high-contrast HUD green whenever the aircraft operates in `LOW_NOE` and local DEM canyon ridges intercept line-of-sight to hostile `RADAR_SITE` and `AIR_DEFENSE_SITE` nodes.
   - When the aircraft climbs above canyon rims into radar visibility, the indicator transitions to `[RADAR EXPOSED / ILLUMINATED]`.
4. **3D Wingtip Vapor Ribbon Contrails**:
   - When instantaneous $G$-load exceeds aerodynamic cavitation thresholds ($G > 4.5G$), dual vapor ribbons emit from port and starboard wingtip coordinates (`[-5.2m, 0.1m, -1.8m]` and `[+5.2m, 0.1m, -1.8m]`).
   - The ribbons spiral dynamically into trailing air vortices, visible in external chase views, wingman cameras, and flyby perspectives during aggressive canyon maneuvers.

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

### 3.5 Helicopter & Combat Search and Rescue (CSAR) (`HELICOPTER_BUBBLE`)
- **Applies to**: `RESCUE-01` (Utility / CSAR Transport Helicopter, `GAMEPLAY-LATER` §6a, `NX-290`).
- **Physical Mounting**: Eye mounted inside glass bubble canopy $+1.4\text{m}$ above cabin deck, $-0.4\text{m}$ lateral (pilot seat).
- **Visual Presentation**:
  - Rounded panoramic Plexiglas bubble canopy with structural tubular framing and green overhead sun tint.
  - **Chin Bubble Footwell Windows**: Clear lower glass panels showing the terrain, trees, water, and landing zone directly below the pilot's rudder pedals.
  - **CSAR Direction Finder (ADF / RDF)**: Homing needle slaved to downed pilot emergency survival beacon (`PRC-112 @ 243.0 MHz`), indicating relative bearing to the extraction zone.
  - **Rescue Hoist & Winch Telemetry**: Cable extension indicator (`HOIST: 35 FT // CABLE RETRACTING`), survivor weight locked status, and hoist operator voice readiness.
  - Collective / cyclic flight controls, dual engine torque percentage dials, and barometric / radar low-altitude altimeter tape ($0 - 500\text{ft}$).

### 3.6 Naval Surface Combatant Bridge (`NAVAL_BRIDGE`)
- **Applies to**: Missile Corvettes, Fast Patrol Craft, and Sea Ferries (Sea Domain P3, `NX-128`, `Q-GD-8`).
- **Physical Mounting**: Elevated inside ship wheelhouse $+9.5\text{m}$ above waterline, looking forward over the bow.
- **Visual Presentation**:
  - Heavy naval bridge windows with rotary clear-view rain screens and salt spray accumulation.
  - Long panoramic perspective over the ship's foredeck, showcasing the forward gun turret (76mm), Vertical Launch System (VLS) cells, and Close-In Weapon System (CIWS) mounts.
  - Center helm console: Brass compass binnacle, twin engine telegraph throttles, and rudder angle indicator.
  - Tactical Navigational Radar: Circular green Plan Position Indicator (PPI) sweep displaying coastlines, strait islands, shipping lanes, and bridge abutment spans.
  - Bathymetric sonar depth sounder reading water under keel ($+14.0\text{m}$ overhead bridge clearance check).

### 3.7 Kinetic Weapon Seeker & PGM Terminal POV (`WEAPON_SEEKER`)
- **Applies to**: Guided missiles (`AAM-3`, `SARH-6`, `AGM-88`), Cruise Missiles, and Laser-Guided Bombs (`PGM`).
- **Physical Mounting**: Extreme nose of missile airframe ($0.0\text{m}$ offset), locked to seeker optical/thermal axis.
- **Visual Presentation**:
  - High-velocity terminal flight perspective (Mach $2.5 - 3.5$ for AAMs, $500\text{kts}$ for cruise missiles).
  - Electro-optical / infrared guidance overlay: Proportional navigation crosshair, contrast gate tracking brackets, and seeker gimbal angle limit circle.
  - **Time-to-Impact (TTI) Telemetry**: Real-time millisecond countdown (`TTI: 02.14S`, `CLOSURE: 1,180 M/S`).
  - Terminal Detonation Capture: The final frame before kinetic impact freeze-frames into a high-contrast flash before switching back to spectator director cam.

### 3.8 Surface-to-Air Missile (SAM) Battery & AAA Optic (`AIR_DEFENSE_OPTIC`)
- **Applies to**: `AIR_DEFENSE_SITE` (SAM batteries, radar-guided flak sites).
- **Physical Mounting**: Operator tracking periscope / pedestal mounted adjacent to missile launcher rails.
- **Visual Presentation**:
  - High-angle skyward binocular / optical periscope framing incoming aerial targets against clouds or mountain ridges.
  - Fire control radar tracking reticle (`AN/MPQ-64 / PATRIOT FC`) with lock acquisition ring and azimuth/elevation degree ticks.
  - Battery engagement status: `FIRE CONTROL: RADAR LOCK // MISSILE 1 READY // INTERCEPT PROBABILITY: 84%`.

---

## 4. Reconnaissance Spotting & Laser Designation Link (`RECON_DESIGNATION_LINK`)

To accurately represent the tactical synergy between scout units and kinetic strike assets (as defined in `COMBAT.md` and `FOG-OF-WAR.md`):

```
┌─────────────────────────────────┐                 ┌─────────────────────────────────┐
│     SCOUT / UAV (STATIC-UAV)    │                 │   STRIKE FIGHTER (VIPER-01)     │
│  - Active EO/IR sensor track    │                 │  - Distance: 45km standoff       │
│  - Laser Painting Target        │                 │  - Fires Laser-Guided Ordnance   │
└────────────────┬────────────────┘                 └────────────────┬────────────────┘
                 │                                                   │
                 │ 1. Emits TargetPainted{recon_id, target_id}       │
                 │    Sets target.painted = true                     │
                 ▼                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             SIMULATION KERNEL (COMBAT CB-5)                         │
│  - Precision Strike receives Pk Multiplier: Pk_eff = min(0.95, Pk_base * 1.6)       │
│  - Terminal Track Check (Q-FOW-16): Target MUST maintain track at impact_tick       │
│  - If scout loses LoS or target fades: Missile loses guidance (Fizzles / Misses)     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Laser Designation Symbology**:
   - In 2D/3D views, a pulsing green/IR laser beam connects the designating scout to the target entity.
   - On the striker's HUD / Cockpit POV, the target acquisition diamond changes from generic amber to flashing tactical green: `◇ TARGET PAINTED // DESIGNATOR: STATIC-UAV // PK BOOST: +60%`.
2. **Terminal Impact Condition (`Q-FOW-16`)**:
   - If the scout is destroyed, jammed by EW, or loses line-of-sight during the missile's flight, `TargetPainted` expires.
   - The missile guidance fails and the shot event is logged as `WeaponImpact{hit: false, cause: TRACK_LOST}`.
3. **Scout Assist Recognition**:
   - When a painted target is successfully destroyed, the scout unit receives an automated **Recon Assist** event (`UnitDestroyed.assist_ids`), contributing to role leaderboard ranking (`Q-PROG-8`).

---

## 5. Replay & Automated Media Integration

### 5.1 Headless Cinematic Pass Recording
The Python headless recording harness (`tools/replay/render_cinematic_pass.py`) integrates unit cockpit POV passes:
```bash
# Capture full pilot cockpit dogfight pass
python3 tools/replay/render_cinematic_pass.py --pass cockpit-viper --out viper_cockpit.mp4

# Capture CSAR helicopter extraction pass
python3 tools/replay/render_cinematic_pass.py --pass cockpit-helo --out helo_csar.mp4

# Capture terminal missile seeker POV pass
python3 tools/replay/render_cinematic_pass.py --pass seeker-missile --out missile_hit.mp4

# Capture truck driver POV crossing the fjord viaduct (9:16 vertical short)
python3 tools/replay/render_cinematic_pass.py --pass cockpit-mule --aspect 9:16 --out truck_viaduct_short.mp4
```

### 5.2 Live Broadcast Director Logic
During 24/7 live streams, the Live AI Director switches to cockpit POV during high-intensity moments:
1. **Dogfight Ingress**: When `VIPER-01` closes within $35\text{km}$ of an adversary, cut from strategic C2 to Pilot Cockpit POV for a high-intensity $15\text{s}$ engagement lock.
2. **Kinetic Missile Terminal Run**: When a precision weapon is within $3\text{s}$ of impact on a high-value facility or aircraft, cut to `WEAPON_SEEKER` POV for a dramatic terminal strike.
3. **CSAR Extraction Race**: When a rescue helicopter approaches a downed pilot marker while enemy static armor approaches, cut to Helicopter Bubble POV showing the ground through the chin windows.
4. **Convoy Chokepoints**: When `MULE-01` approaches a strategic bridge or pass, cut to Driver Cockpit POV to show the massive scale of the surrounding mountain terrain.

### 5.3 Combat Casualty & Loss-of-Signal (LOS) Failover Contract
When a unit is disabled or neutralized while viewed from its cockpit or weapon seeker optic, camera controllers MUST follow a strictly deterministic transition sequence to maintain continuous broadcast engagement:

```
[UNIT KILLED]
      │
      ├─► Frame 0–10 (0–160ms): Heavy screen shake + CRT chromatic aberration + audio glitch / warning klaxon cutoff
      │
      ├─► Case A: Ejection Capable (Fighter Jet / CSAR Crew)
      │     └─► Frame 11+: Switch to Ejection Canister Parachute POV (`EJECTION_CHUTE`)
      │           - Drifts downward toward crash crater / wreckage smoke plume
      │           - Initializes 10-minute PRC-112 beacon ping (`NX-290`) for CSAR rescue pickup
      │
      └─► Case B: Catastrophic / Kinetic Seeker Detonation / Armored Mule Penetration
            └─► Frame 11–25: 250ms Whiteout flash / military analog TV static dissolve
            └─► Frame 26+: Instant cut to nearest engaging friendly combatant, killer unit, or Theater Strategic Orbit Cam
```
Under no circumstances may a casualty leave the renderer on an orphaned camera, pitch-black screen, or null pointer exception.

---

## 6. Architectural Invariants & Decoupling

1. **Kernel Purity (DATA-INTEGRITY DI-1)**:
   The simulation kernel in `services/sim` does not know or care about canvas rendering, windshield textures, or font sizes. It only manages position $(x, y, z)$, heading angle, velocity, and health.
2. **Deterministic Parity**:
   Unit POV coordinates are strictly computed from deterministic simulation state and constant `pov_profile` offsets, guaranteeing bit-for-bit camera reproduction on every replay.
3. **Graceful Fallback**:
   If a unit contract does not specify a `pov_profile`, presentation engines automatically fallback to a standard dynamic 3/4 trailing chase camera.
