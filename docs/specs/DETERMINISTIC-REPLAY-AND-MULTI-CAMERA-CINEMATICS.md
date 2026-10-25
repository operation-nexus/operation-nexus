# SPEC: Deterministic Replay & Multi-Camera Cinematics Engine

**Specification ID**: `SPEC-DETERMINISTIC-CINEMATICS-01`  
**Context**: Operation Nexus / Hiveplex Theater Media & Replay Architecture (NX-176, NX-233)  
**Status**: APPROVED  

---

## 1. Executive Summary & Core Principle

Operation Nexus is engineered from the ground up as a **100% Deterministically Reproducible Simulation**. 

Unlike conventional game engines or broadcast streams that only capture what was on a player's screen at a single moment in time, the Operation Nexus simulation state at any tick $T$ is an exact, pure mathematical function:

$$\text{State}(T) = f(\text{Seed}, \text{ConfigHash}, \text{CommandLog}_{0 \dots T})$$

Because every event, ballistic trajectory, supply consumption, radar track, and unit maneuver is completely deterministic:
1. **Zero Video Storage Overhead**: A 4-hour theater campaign requires only a compressed **$\sim 1.3\text{MB}$ per hour** command/event log ($\sim 5.2\text{MB}$ total), compared to over $120\text{GB}$ of raw 4K video.
2. **The Omniscient Virtual Film Studio**: Any past campaign can be re-simulated headlessly or interactively an infinite number of times. Content creators, video editors, and documentary narrators can place virtual cameras anywhere in the 3D world, replay the exact same battle from unlimited angles, and toggle across all 4 visual pillars.
3. **Future-Proof Upgrades**: A historic campaign fought in 2026 can be replayed in 2028 at 8K resolution with upgraded ray tracing, updated PBR terrain shaders, or newly remodeled 3D aircraft assets with bit-for-bit trajectory parity.

---

## 2. Multi-POV Omniscient Post-Production Engine

```
                               ┌────────────────────────────────────────┐
                               │   DETERMINISTIC EVENT LOG (~1.3MB/h)   │
                               │   (Seed + Config + Input Commands)     │
                               └───────────────────┬────────────────────┘
                                                   │
                   ┌───────────────────────────────┼───────────────────────────────┐
                   ▼                               ▼                               ▼
       [ PASS 1: PILOT CHASE POV ]    [ PASS 2: STRATEGIC C2 GIS ]    [ PASS 3: VOLUMETRIC EW/SAR ]
       Pillar 2 (3D Low-Angle)         Pillar 1 (2D Tactical Grid)     Pillar 4 (RF Spectrum)
       - Close-up dogfight             - Macro frontline shift         - Radar jamming lobes
       - Canopy weapon lock            - Territory balance bar         - Satellite reconnaissance
                   │                               │                               │
                   └───────────────────────────────┼───────────────────────────────┘
                                                   │
                                                   ▼
                                 ┌──────────────────────────────────┐
                                 │   NON-LINEAR VIDEO EDITING (NLE) │
                                 │   (Premiere / DaVinci Resolve)   │
                                 │   - Narrative Documentaries      │
                                 │   - 9:16 Vertical Viral Shorts   │
                                 │   - High-Octane Trailers         │
                                 └──────────────────────────────────┘
```

When producing long-form narrative documentaries (e.g. *Perun*, *Kings and Generals*, *The Operations Room*) or viral short-form cutdowns (TikTok, YouTube Shorts, Instagram Reels), video editors are never constrained by what was broadcast live.

The deterministic replay harness enables multi-pass video generation:

### 2.1 Replay Passes & Camera Archetypes

| Pass Type | Visual Pillar | Camera Perspective | Editorial Purpose |
| :--- | :--- | :--- | :--- |
| **Pass A: Strategic Establishing** | **Pillar 1 (2D GIS)** | Top-down orthographic theater view ($400 \times 240\text{km}$) | Establishes the operational context, frontline momentum, supply lines, and grand strategy. |
| **Pass B: Tactical Chase** | **Pillar 2 (3D RTS)** | Dynamic 3/4 chase camera locked behind `VIPER-01` | Captures high-g turns, sonic canyon flybys, missile launches, and target locks. |
| **Pass C: Fighter Cockpit POV** | **Pillar 2 (3D RTS)** | Pilot canopy POV with collimated HUD & BVR target diamond | Visceral first-person dogfight perspective with weapon status and radar locks. |
| **Pass D: Truck Driver POV** | **Pillar 2 (3D RTS)** | Driver cabin windshield POV behind military steering wheel | Human-scale ground view observing road terrain and distant air/bridge strikes. |
| **Pass E: CSAR Helo Low-Level** | **Pillar 2 (3D RTS)** | Helicopter bubble canopy + chin footwell window POV | Low-level nap-of-the-earth insertion tracking PRC-112 survivor beacon for pilot rescue. |
| **Pass F: Naval Wheelhouse POV** | **Pillar 2 (3D RTS)** | Ship bridge deck view over forward gun & VLS cells | Sea domain surface action, radar PPI sweep, and naval escort operations. |
| **Pass G: Missile Seeker Terminal** | **Pillar 2 (3D RTS)** | Kinetic missile seeker head POV (Mach 3 proportional nav) | High-velocity terminal flight, contrast lock brackets, and millisecond time-to-impact (TTI). |
| **Pass H: SAM Battery Optic** | **Pillar 2 (3D RTS)** | Skyward binocular optic mounted on missile launcher rail | Ground-based air defense perspective tracking supersonic targets against mountain ridges. |
| **Pass I: Viaduct Choke-Point Cam** | **Pillar 2 (3D RTS)** | Static ground-level tripod camera mounted on the North Fjord Viaduct | Delivers cinematic perspective as supersonic strike packages scream overhead. |
| **Pass J: War Room Briefing** | **Pillar 3 (Holographic)** | Isometric vector wireframe tabletop with SAM threat domes | Perfect for tactical voiceover, intel briefings, and order-of-battle breakdowns. |
| **Pass K: Cognitive Neural Scope** | **Pillar 4 (AI Lattice)** | Causal trajectory trees, branch probabilities, and synaptic intent arcs | Explains *how* the agent decided on a high-risk strike or retreat maneuver. |
| **Pass L: Target Reconnaissance** | **PiP MFD (`RECON` / `FLIR`)** | Downward optical/IR sensor hovering over enemy headquarters | Delivers bomb damage assessment (BDA) and kinetic impact confirmation. |

### 2.2 Unit POV & Cockpit Profiles (`pov_profile`)

In accordance with [RFC-UNIT-POV-002](../architecture/UNIT-POV-AND-COCKPIT-CONTRACTS-RFC.md), every unit contract in Operation Nexus supports dedicated first-person driver/pilot/operator perspectives linked via the `pov_profile` schema:
1. **Fighter Jet Canopy (`VIPER-01`, `BANDIT-04`)**:
   - Eye position: Fuselage centerline $+1.25\text{m}$ vertical, $+1.80\text{m}$ forward.
   - Collimated heads-up display (HUD): Infinity-focused pitch ladder, velocity vector, heading compass tape, airspeed tape (KTS / Mach / G-meter), barometric altitude, and active BVR target lock diamond.
   - Canopy framing: Arching carbon-composite canopy frame with subtle glass reflection sheen.
2. **Logistics Hauler Cabin (`MULE-01`)**:
   - Eye position: Inside armored cabin $+2.2\text{m}$ above road surface, offset $-0.45\text{m}$ to driver seat.
   - Ballistic split-windshield: Heavy matte A-pillars, top sun visor, and center reinforcing vertical divider.
   - Cab instruments: Military steering wheel, analog speedometer dial, tactical route navigation MFD tablet, and center interior rearview mirror showing the road receding into the distance.
3. **CSAR Helicopter Bubble (`RESCUE-01`)**:
   - Eye position: Inside rounded bubble canopy $+1.4\text{m}$ above cabin deck.
   - Chin footwell glass: Direct downward view of terrain, tree canopies, and landing zones below the rudder pedals.
   - Instruments: ADF survival beacon needle homing onto downed pilot `PRC-112`, rescue hoist status, and torque percentage gauges.
4. **Naval Surface Vessel Bridge (Sea Domain P3)**:
   - Eye position: Ship wheelhouse $+9.5\text{m}$ above waterline looking over foredeck.
   - Instruments: Compass binnacle, engine telegraph, and circular radar Plan Position Indicator (PPI) screen with bridge clearance sonar.
5. **Kinetic Weapon Seekers & SAM Optics**:
   - Missile Seeker POV: Mach 3 proportional navigation reticle with real-time millisecond Time-to-Impact (`TTI: 01.8S`).
   - SAM Site Optic: Skyward tracking periscope with radar acquisition lock ring (`INTERCEPT PROBABILITY: 84%`).

### 2.3 Cognitive Neural Decision Lattice Visibility Matrix

The **Cognitive Neural Decision Lattice** (Pillar 4) visualizes the AI agent's branching causal trajectory predictions, counterfactual futures, and synaptic intent arcs. To ensure both competitive integrity and maximum storytelling impact, the following visibility rules are enforced:

| Mode / Context | Lattice Visibility | Rationale / Enforcement |
| :--- | :--- | :--- |
| **Live: Chat vs Agent Campaign** | **STRICTLY HIDDEN** (Fog of War) | Preserves competitive integrity and Fog of War (RP-1). Live chat commanders must NOT be able to read enemy AI strike intentions, target selection, or risk calculations in real time. |
| **Live: Agent vs Agent Match** | **TOGGLEABLE / LIVE SPECTATOR** | For AI research benchmarks and autonomous esports broadcasts, the omniscient view allows audiences to analyze dual AI decision logic in real time. |
| **Replay / AAR / Video Creation** | **UNLOCKED FULL REVEAL** | In post-campaign replays, the full-truth causal tree is completely unlocked. Video editors can toggle the lattice on key narrative moments (e.g. showing the 92% risk calculation before an agent launches a daring canyon strike). |

### 2.4 Kinetic Scale, Physical Speed Calibration & Fog of War Rules

To prevent visual-simulation drift (DATA-INTEGRITY DI-1) while delivering cinematic realism:

1. **Kinematic Velocity & Spatial Scaling**:
   - Theater bounds: Strictly calibrated to $400\text{km} \times 240\text{km}$.
   - Realistic physical velocities:
     - Ground Convoys: $50 - 60\text{km/h}$ ($14 - 17\text{m/s}$).
     - CSAR Helicopters: $120 - 150\text{kts}$ ($62 - 77\text{m/s}$).
     - Strike Fighters: $480\text{kts}$ cruise ($247\text{m/s}$), Mach 1.4 burst ($476\text{m/s}$).
     - Interceptor Missiles: Mach $2.8 - 3.5$ ($950 - 1,190\text{m/s}$).
2. **Recon Spotting & Laser Designation Multiplier**:
   - When a scout UAV tracks and paints an enemy unit (`TargetPainted`), laser-guided precision strikes receive a $P_k$ multiplier ($\times 1.6$).
   - If the scout loses line-of-sight before the weapon's `impact_tick` (`Q-FOW-16`), the missile loses terminal guidance and misses.
3. **Live Broadcast Fog-of-War Redaction**:
   - In live Chat vs Agent broadcasts, the camera and overlay strictly conform to coalition sensor knowledge (`FOW-1`, `FOW-2`).
   - Unspotted enemy entities are redacted from 2D/3D scenes, or rendered solely as low-confidence SIGINT latency blobs.
   - In omniscient post-campaign replays, Fog of War is toggleable to allow full two-sided narrative breakdown.

---

## 3. Narrative Video Creation Workflows

### 3.1 Long-Form Narrative Documentaries (15–45 minutes)
For high-production military analysis videos:
1. **Act I — Intelligence Briefing & Theater Laydown**: Rendered using **Pillar 3 (Holographic Tabletop)** and **Pillar 1 (2D GIS)**. The narrator explains troop placements, logistics choke points (North Viaduct, South Bridge), and the coalition's opening strategy.
2. **Act II — The Ingress & Electronic Attack**: Cut to **Pillar 4 (Volumetric EW)**. Viewers see the stealth jamming corridor opened by electronic attack pods blinding static SAM radars.
3. **Act III — Kinetic Dogfight & Intercept**: Cut to **Pillar 2 (3D Textured Chase)**. Multi-angle cuts of `VIPER-01` engaging `BANDIT-04` with cockpit HUD telemetry from the PiP camera.
4. **Act IV — Strike & AAR Assessment**: Close on downward optical reconnaissance over the target facility, followed by the territory momentum bar flipping to coalition victory.

### 3.2 Short-Form Viral Clips (9:16 Vertical)
1. **0:00–0:03 (The Hook)**: Supersonic 3D jet flyby banking past the mountain cliff at Mach 1.4 directly into camera (Pillar 2).
2. **0:03–0:12 (The Action)**: Camera swings to trailing chase cam; missile lock tone sounds; missile trails ignite toward enemy interceptor.
3. **0:12–0:18 (The Resolution)**: Kinetic fireball explosion over the canyon; PiP MFD flashes `TARGET DESTROYED`; lower-third displays pilot callsign and viewer command credit.

---

## 4. Live Broadcast AI Auto-Director Standards

While the deterministic replay engine handles post-production, the **Live AI Auto-Director** governs real-time 24/7 stream viewing.

To maintain viewer retention and avoid spectator fatigue, the Live Director operates under strict television broadcast pacing standards:

### 4.1 Anti-Spam & Anti-Flash Guidelines
1. **Scene Dwell Time**: Calm patrol and strategic overview sequences must hold for at least **18–25 seconds**. Rapid cuts ($< 10\text{s}$) disorient live audiences and cause stream drop-off.
2. **Combat Engagement Priority Lock**:
   - The director continuously calculates closure range between hostile air/ground units:
     $$\text{Dist} = \|\mathbf{P}_{\text{coalition}} - \mathbf{P}_{\text{hostile}}\|$$
   - When hostile units enter weapon engagement envelope ($\text{Dist} < 45\text{km}$):
     - The director **locks the shot onto the combat pair**.
     - Camera cut timers are frozen. The director holds dynamic 3/4 framing on both aircraft until the engagement terminates in a kill, evasion, or disengagement.
3. **Professional Broadcast Chyron (Zero Flashing)**:
   - On-screen telemetry is displayed as a calm, glassmorphic lower-third chyron.
   - Rapidly pulsating or strobing text is strictly prohibited.
   - Features a slow-breathing red recording dot ($2.5\text{s}$ cycle) indicating active tracking:
     `● LIVE AIR INTERCEPT // VIPER-01 vs BANDIT-04 // RANGE: 14.8KM // CLOSURE: 980 KTS`
4. **Silky Camera Interpolation**:
   - All automated camera motions use soft damping ($\alpha \approx 0.018 - 0.025$) to emulate heavy gyro-stabilized broadcast helicopter and crane lenses.

---

## 6. Audio Architecture Evolution Roadmap

High-fidelity tactical audio is vital for audience immersion. The audio architecture evolves across three distinct phases:

### 6.1 Phase 1: Procedural Synth Prototype (Current)
- Implemented via pure Web Audio API oscillators and gain nodes (zero external asset dependencies):
  - Dynamic radio squelch burst on unit selection and camera cut.
  - Proximity radar warning receiver (RWR) beeps triggered on hostile closure $<45\text{km}$.
  - Supersonic flyby Doppler white noise sweep on chase cam.
  - Low-frequency 58Hz command center ambient hum.
- **Role**: Functional verification and low-latency interaction feedback.

### 6.2 Phase 2: Authentic DSP & Military Radio Convolutions
- Replaces raw synth oscillators with convolution reverb and impulse responses (IR) recorded from genuine military headsets (e.g. David Clark H10, Gentex SPH-5):
  - **Bandpass Filtering**: 300Hz–3.4kHz military VHF/UHF tactical radio frequency response.
  - **Dynamic Range Compression & Squelch Tail**: Authentic hard-knee limiter with realistic background cockpit turbine whine and wind noise.
  - **Spatial 3D Propagation**: Acoustic travel delays ($343\text{m/s}$ speed of sound) and distance attenuation for explosions and sonic booms.

### 6.3 Phase 3: Neural Voice Synthesis & Real-Time Comms
- **On-Device Kokoro-82M TTS**:
  - Ultra-lightweight ($82\text{M}$ parameter) neural text-to-speech running locally on the streaming host.
  - Generates authentic, emotion-conditioned military radio transmissions for pilots, ground commanders, and AWACS controllers (`"MAGIC-1, VIPER-01, Fox 3 in the basket!"`).
- **Dynamic Comms Layering**:
  - Automated radio priority ducking: AWACS priority breaks over routine logistics check-ins.

---

## 7. Architectural Implementation References

- **Unit POV & Cockpit Contracts**: `docs/architecture/UNIT-POV-AND-COCKPIT-CONTRACTS-RFC.md` (RFC-UNIT-POV-002).
- **Replay Measurement & Benchmarks**: `tools/replay/measure.py` (NX-032), `docs/specs/CLIPS-REPLAY.md`.
- **Road & Bridge Elevation Spec**: `docs/specs/ROAD-AND-BRIDGE-TAXONOMY.md` (SPEC-ROAD-BRIDGE-01).
- **Simulation Terrain Integration RFC**: `docs/architecture/SIMULATION-TERRAIN-AND-ROAD-INTEGRATION-RFC.md`.
- **Interactive Multi-Pillar Sandbox**: `tools/prototype/unified-visualizer.html`.
- **Headless Replay Recording Harness**: `tools/replay/render_cinematic_pass.py`.
