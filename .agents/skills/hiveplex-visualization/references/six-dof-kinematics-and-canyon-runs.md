# 6-DOF Kinematics, Canyon Penetration & Camera Choreography

Status: Production Reference · Architecture: Two-Tier Split · Systems: Three.js, Chromium Headless, FFmpeg

This document specifies the mathematics and runtime architecture for rendering physically grounded 6-DOF vehicle attitude, terrain-masking canyon runs, collimated cockpit HUDs, and deterministic headless recording within Operation Nexus / Hiveplex.

---

## 1. The Two-Tier Split Architecture

To balance authoritative simulation integrity with broadcast-grade visual realism, Operation Nexus enforces a strict boundary between discrete simulation physics and continuous rendering attitude:

```
[ Discrete Simulation Kernel (10 Hz) ]
   ├── Tactical DEM / DTED terrain elevation sampling & masking
   ├── Radar Line-of-Sight (LOS) raycasts & horizon clearance
   ├── Waypoint navigation & high-level steering vectors
   └── Fuel, kinetic energy, & airspeed state transitions
                │
                ▼ (RenderFrameState snapshot)
[ Continuous Render Engine (60 Hz / Deterministic Virtual Step) ]
   ├── 6-DOF continuous attitude derivation (Roll φ, Pitch θ, Yaw ψ)
   ├── Dynamic canyon-wall potential-field weaving
   ├── Aerodynamic contrails, wingtip vortices, & jet wash particles
   └── Camera Edit Decision List (EDL) & collimated HUD horizon ladder
```

1. **Simulation Kernel (10 Hz):**
   - Pure state logic in `nexus.core`. Operates at 100ms discrete intervals.
   - Evaluates unit velocities $\vec{v} = (v_x, v_y, v_z)$, positions $\vec{p}$, and yaw heading $\psi$.
   - Strictly ignores visual rendering parameters (Euler angles, camera matrices, particle emitters).
2. **Render Engine (60 Hz):**
   - Consumes successive `RenderFrameState` snapshots and computes high-fidelity 6-DOF quaternions.
   - Interpolates trajectories smoothly using Hermite splines without violating discrete sim coordinates.
   - Derives realistic aerodynamic banking, climb pitch, and ground slope conformity.

---

## 2. Mathematical Kinematic Formulations

### 2.1 Coordinated Turn Roll ($\phi$) for Fixed-Wing Aircraft

Fixed-wing aircraft (e.g. VIPER-01) bank into turns to align total aerodynamic lift with the resultant of centripetal acceleration and gravity:

$$\phi_{\text{target}} = \arctan\left(\frac{v_{xy} \cdot \dot{\psi}}{g}\right)$$

Where:
- $v_{xy} = \sqrt{v_x^2 + v_y^2}$ is horizontal groundspeed ($\text{m/s}$).
- $\dot{\psi} = \frac{d\psi}{dt}$ is the instantaneous yaw rate ($\text{rad/s}$).
- $g = 9.80665\,\text{m/s}^2$ is gravitational acceleration.

To maintain structural and human limits, $\phi_{\text{target}}$ is clamped to platform maximums:
- High-performance fighters (VIPER-01): $|\phi| \le 75^\circ$ ($1.309\,\text{rad}$)
- Transport and logistics aircraft: $|\phi| \le 35^\circ$ ($0.611\,\text{rad}$)

Continuous roll smoothing follows a first-order lag filter:
$$\frac{d\phi}{dt} = k_{\text{roll}} \cdot (\phi_{\text{target}} - \phi)$$
with damping constant $k_{\text{roll}} \approx 8.5\,\text{s}^{-1}$.

### 2.2 Flight Path & Angle-of-Attack Pitch ($\theta$)

Pitch attitude $\theta$ combines geometric climb/dive angle $\gamma$ with aerodynamic angle of attack (AoA) $\alpha$:

$$\theta = \gamma + \alpha$$

$$\gamma = \arctan2\left(v_z, v_{xy}\right)$$

$$\alpha = c_{\text{lift}} \cdot \frac{m \cdot g}{0.5 \cdot \rho \cdot v^2 \cdot S}$$

During high-g turns, induced lift generates additional AoA:
$$\alpha_{\text{turn}} = \frac{\alpha_{\text{level}}}{\cos\phi}$$
This tilts the fighter's nose above the velocity vector in steep canyon banks, producing realistic high-alpha maneuvers.

### 2.3 Helicopter Cyclic Pitch & Rotor Disc Tilt

Rotary-wing units (e.g. RESCUE-01 CSAR) do not bank purely from turn rate; they tilt their tip-path rotor plane proportional to linear planar acceleration:

$$\theta_{\text{helo}} = \arctan\left(\frac{a_{\text{fwd}}}{g}\right)$$

$$\phi_{\text{helo}} = \arctan\left(\frac{a_{\text{lat}}}{g}\right)$$

Where $a_{\text{fwd}}$ and $a_{\text{lat}}$ are longitudinal and lateral vehicle-frame accelerations derived from $\frac{d\vec{v}}{dt}$. Rotor disc geometry tilts ahead of fuselage rotation with a 150ms cyclic lag.

### 2.4 Ground Axle Slope Alignment for Wheeled Vehicles

Logistics convoys (e.g. MULE-01) and mobile SAM batteries traverse rugged canyon terrain, switchbacks, and viaduct ramps. The chassis attitude conforms to bilateral axle contact normal vectors:

$$\vec{N}_{\text{terrain}} = \frac{(-\frac{\partial h}{\partial x}, -\frac{\partial h}{\partial y}, 1)}{\sqrt{(\frac{\partial h}{\partial x})^2 + (\frac{\partial h}{\partial y})^2 + 1}}$$

The vehicle forward axis $\vec{F}$ and lateral axle axis $\vec{R}$ align to terrain gradients:
$$\theta_{\text{ground}} = \arcsin\left(\vec{F} \cdot \hat{k}_{\text{up}}\right)$$
$$\phi_{\text{ground}} = \arcsin\left(\vec{R} \cdot \hat{k}_{\text{up}}\right)$$

Spring-damper suspension smoothing ($k_{\text{susp}} = 12.0\,\text{s}^{-1}$) prevents snapping over discrete terrain triangle facets.

---

## 3. Canyon-Wall Potential-Field Weaving

When operating in deep mountain defiles (such as the Northern Fjord Canyon), aircraft utilize low-altitude terrain masking to evade enemy long-range SAM radar locks. 

To navigate tight canyon corridors, steering incorporates a repulsive potential-field vector from surrounding DTED canyon walls:

$$\vec{F}_{\text{rep}} = \sum_{w \in \text{walls}} \frac{k_{\text{wall}}}{\max\left(d_w - d_{\text{safe}}, \epsilon\right)^2} \hat{n}_w$$

Where:
- $d_w$ is the normal distance from the aircraft to canyon wall segment $w$.
- $d_{\text{safe}} = 45\text{m}$ is the safety clearance margin.
- $\hat{n}_w$ is the inward surface normal of the cliff facet.
- $k_{\text{wall}} = 1800\,\text{m}^3/\text{s}^2$ is the wall repulsion coefficient.

Combined with waypoint attraction $\vec{F}_{\text{goal}} = k_{\text{goal}} (\vec{P}_{\text{target}} - \vec{P})$, this generates dynamic, organic canyon-weaving trajectories where aircraft aggressively bank away from sheer rock walls while preserving forward strike momentum.

---

## 4. Collimated Cockpit HUD Horizon Rotation

In Pass N (`cockpit-canyon`) and first-person views, the Head-Up Display (HUD) optics are focused at optical infinity. The horizon reference line and pitch ladder rotate opposite to the aircraft's body bank:

$$\phi_{\text{HUD}} = -\phi_{\text{aircraft}}$$

$$\Delta y_{\text{HUD}} = S_{\text{ladder}} \cdot \theta_{\text{aircraft}}$$

Where $S_{\text{ladder}}$ is the pixel-per-degree vertical scaling factor. When VIPER-01 executes a $65^\circ$ right bank through the canyon turn, the pilot sees the fjord walls tilt steeply while the artificial horizon remains parallel to the true world horizon.

---

## 5. Deterministic Virtual-Clock Stepping (`window.renderDeterministicTick`)

High-intensity visual passes—featuring multi-layer canyon rock shaders, dynamic water reflections, contrail smoke sprites, and 60 FPS video capture—demand guaranteed frame timing.

### 5.1 Protocol

1. The capture harness initializes Chromium with query flag `&det=1`:
   ```
   file:///path/to/unified-visualizer.html?pillar=2&view=canyon&det=1
   ```
2. When `det=1` is detected:
   - The visualizer disables internal `requestAnimationFrame` loop self-scheduling.
   - Simulation time is frozen at initial state $t_0$.
   - The global function `window.renderDeterministicTick(simTimeSec)` is mounted to the global scope.
3. The headless harness advances time in exact $\Delta t = \frac{1}{60}\text{s}$ increments:
   ```javascript
   const fps = 60;
   const frameDuration = 1.0 / fps;
   for (let i = 0; i < totalFrames; i++) {
     const t = clipStartSec + (i * frameDuration);
     await page.evaluate((simTime) => window.renderDeterministicTick(simTime), t);
     const pngBuffer = await page.screenshot({ type: 'png', omitBackground: false });
     ffmpegProcess.stdin.write(pngBuffer);
   }
   ```
4. **Guarantees:**
   - Zero dropped frames, zero tearing, and zero time dilation.
   - Identical bit-for-bit video renders across diverse CPU and GPU architectures.
