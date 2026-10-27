# Movement, attitude and terrain height: grill for the owner (2026-10-27)

Asked by the owner on 2026-10-27: "I just want the movement, roll pitch yaw, xyz, and movement of all vehicles to be realistic without having to implement a physics engine, though I may want to? … no need to change altitude via command (yet) but I saw you say that the kernel is 2D only. But then that conflicts with our ability to navigate terrain height differences."

Written by the lead (architect role) at `develop` `b443f5a`. Docs only: no code, tracker, spec or question row was changed. Every repo claim cites `file:line`. External facts are marked **[UNVERIFIED]**. Numbers I computed say "computed" and show the formula.

## Short answer

- **There is no conflict in the code today, because nothing navigates terrain height.** Ground units drive a road graph whose 13 edges all have `speed_mult: 1.0`, and there is no heightmap. Aircraft have a fixed altitude band, not a height. "2D kernel" means positions and velocities are `Vec2`, with no z.
- **No physics engine in the sim.** It would break determinism and buy no gameplay. A cosmetic one in a later 3D view is fine.
- **Roll, pitch and yaw stay display-only**, derived by the renderer from the sim's position and heading.
- **One change to the lead's starting position:** most of the realism can come without putting height or a heightmap in the kernel at all. Slope can be baked into each road's `speed_mult` offline. Masking from the heightmap is already decided as an offline bake (Q-VIZ-1). Display height can come from the band. The kernel needs a heightmap only for live line of sight or off-road driving, and neither is planned.
- **Where the kernel does need work: aircraft turns.** Aircraft change heading instantly at a waypoint. A renderer can't hide that without drawing the jet up to about 1.5 km away from its sim position (computed below). The fix is a per-kind turn-rate limit for aircraft in the kernel. It's 2D, cheap and deterministic, but it moves goldens and travel times.
- **Most of the attitude realism shows only in a 3D view.** The main view is a top-down Canvas2D map (ADR-0005), and 3D is picture-in-picture later (Q-VIZ-6, ROADMAP P5). Top-down, viewers see yaw, the turn arcs and, at most, a shadow offset for height.

## 1. What exists today

### 1.1 The kernel's movement state

| Fact | Where |
|---|---|
| Position and velocity are `Vec2` (x, y). There is no z, heading, vertical speed, attitude or airspeed field | `services/sim/src/nexus/core/world.py:263-264`; `Vec2` at `world.py:215` |
| `vel` is "the end-of-tick heading at the current speed". Heading is not stored; it is `atan2` of `vel` | `docs/planning/OPEN-QUESTIONS.md:684` (Q-SIM-37); `step.py:312-319` |
| `path` is the remaining waypoints: node ids, or `Vec2` points for aircraft. A ground unit is on the edge from `last_node` to `path[0]` | `world.py:266-269` |
| Floats are float64. Only `state_hash` quantizes: positions to integer mm, velocities to integer mm/s, other floats to 1e-6 | `world.py:7-10`, `world.py:102-105`, `world.py:1045-1046` |
| Cross-machine float determinism is not guaranteed; replays verify on the same platform. Fixed-point is the stated fallback | `docs/architecture/adr/0002-deterministic-sim-kernel.md:13`, `:22` |
| The kernel steps at 10 Hz. `TICK_DT` 0.1 s × `sim.time_scale` 6.0 gives `world_dt` 0.6 world seconds per tick | `docs/specs/SIM-CORE.md:14`; `step.py:33`; `rules.py:496`, `rules.py:808-810`; `balance/default.yaml:6-7` |
| Combat range is 2D distance | `combat.py:118-119` |

So "2D kernel" means exactly this: every position, velocity, distance and waypoint is an (x, y) pair. The one vertical concept is the aircraft's altitude band.

### 1.2 How units move

| Behaviour | Where |
|---|---|
| Each unit spends `world_dt` along its path in id order; time left after a waypoint carries on to the next | `step.py:111-114`; `SIM-CORE.md:51` |
| Aircraft fly straight lines between waypoints at top speed | `step.py:113`, `step.py:153-154` |
| Ground units follow road edges at `speed_mps × speed_mult`. A ground waypoint that is not a node id raises an error, so there is no off-road movement | `step.py:265-271` |
| Heading changes in one tick at a waypoint: `_move` snaps to the node (`_arrive`), and `_velocity` points straight at the next waypoint | `step.py:278-299`, `step.py:302-319` |
| Speed changes in one tick: no acceleration. Takeoff goes from 0 to top speed. Orbit entry drops to `min_speed_mps`. A road change or arrival changes speed at once | `step.py:160-187`, `step.py:234-245` |
| An idle airborne aircraft orbits at `min_speed_mps`, one lap per `air.orbit_period_s` (120 world s) | `step.py:228-254`; `balance/default.yaml:19` |
| Damage slows a unit (`damaged_speed_mult` 0.75); an escorted group moves at its slowest member's speed | `step.py:119-121`; `balance/default.yaml:110`; `docs/specs/GAMEPLAY.md:134` |
| The movement system costs about 0.79 ms p99 in the 1,000-entity worst case on the reference host (sensing 4.63 ms, combat 2.65 ms). The budget is p99 `step` < 25 ms | `docs/review/NX-345-BENCH.md:47`; `SIM-CORE.md:24` |

Speeds per kind (all PROPOSED in content):

| Kind | Domain | `speed_mps` | `min_speed_mps` | Bands (default) | Where |
|---|---|---|---|---|---|
| STRIKE_FIGHTER, ENEMY_STRIKE_FIGHTER, ENEMY_FIGHTER | AIR | 250 | 100 | LOW, MED, HIGH (MED) | `content/units/strike-fighter.yaml:8-12`, `enemy-strike-fighter.yaml:8-12`, `enemy-fighter.yaml:7-11` |
| RECON_UAV, ENEMY_RECON_UAV | AIR | 60 | 20 | LOW, MED (MED) | `content/units/recon-uav.yaml:8-12`, `enemy-recon-uav.yaml:8-12` |
| LOGI_TRUCK, ENEMY_CONVOY | GROUND | 25 | — | — | `logi-truck.yaml:8`, `enemy-convoy.yaml:7` |
| ENEMY_ARMOR | GROUND | 20 | — | — | `enemy-armor.yaml:7` |
| GARRISON_INFANTRY | GROUND | 5 | — | — | `garrison-infantry.yaml:8` |
| RADAR_SITE, AIR_DEFENSE_SITE | STATIC | 0 | — | — | `radar-site.yaml:8`, `air-defense-site.yaml:8` |

There are no helicopters and no ships. Neither is a `UnitKind` (`docs/review/VISUALIZER-KERNEL-AUDIT-2026-10-26.md:28`). The sea domain is planned for P3 (`docs/planning/OPEN-QUESTIONS.md:29`; `docs/planning/ROADMAP.md:10`).

Per tick, a jet moves 150 m and a truck 15 m (computed: speed × 0.6 s).

### 1.3 Where height already exists

- **Altitude bands.** `AltBand` is `NOE`, `LOW`, `MED` and `HIGH` (`contracts/common/enums.json:17`). An aircraft gets its kind's default band at spawn (`world.py:766`), and no command changes it (`docs/specs/COMBAT.md:93`; Q-CBT-11, `OPEN-QUESTIONS.md:606`). **A band has no number.** There are no metre thresholds (audit, `VISUALIZER-KERNEL-AUDIT-2026-10-26.md:8`). Every air kind in content flies MED, and no kind lists NOE.
- **What a band does:** a weapon hits an AIR target only if its `bands:` list includes the target's band (`combat.py:414`). A band in `fow.masked_alt_bands` (default NOE and LOW, `docs/specs/CONFIG-AND-CONTENT.md:145`) is masked like a ground unit (`fog.py:14-16`, `fog.py:210-217`).
- **Masking regions.** Masking is a per-area flag, not line of sight (Q-FOW-3, `OPEN-QUESTIONS.md:476`). The theater's polygons are rasterized to 1 km cells (`CONFIG-AND-CONTENT.md:144`, `rules.py:519-522`). strait-1 has two: `northern-hills` and `southern-valley` (`content/theaters/strait-1.yaml:12-14`). A masked target is tracked only by a sensor in the same region, and takes Pk × 0.5 (`COMBAT.md:85`, `combat.py:417-419`).

### 1.4 Where height doesn't exist

- **No heightmap.** strait-1 says "No heightmap in the first build (Q-TH-4); one is planned later" (`content/theaters/strait-1.yaml:10-11`). The schema accepts `masking_regions` only. "Nothing in the first build reads height", and the height fields join with the item that reads height (`CONFIG-AND-CONTENT.md:612`). The heightmap format is decided as a 16-bit PNG (Q-CFG-3, `OPEN-QUESTIONS.md:132`). Owner: a heightmap "will still be needed later" (Q-TH-4, `OPEN-QUESTIONS.md:575`).
- **Road `speed_mult` doesn't approximate terrain yet.** All 13 strait-1 edges have `speed_mult: 1.0` (`content/theaters/strait-1.yaml:47-60`). The lead's brief said terrain is approximated by `speed_mult`. The mechanism exists (`roads.py:111-117`, `step.py:269`), but no edge uses it.
- **Roads are straight lines between nodes.** Edge length is the straight line (`roads.py:5`). Curved roads are decided but deferred (Q-VIZ-2, `OPEN-QUESTIONS.md:814`).
- **Already decided (owner, #383, 2026-10-26):** "No height, vertical speed or attitude enters the kernel." The renderer maps the catalog's `default_alt_band` to a display height (Q-VIZ-3, `OPEN-QUESTIONS.md:815`). Masking cells are derived offline from the PNG heightmap, not by live line of sight (Q-VIZ-1, `OPEN-QUESTIONS.md:813`). **Putting height in the kernel would reopen Q-VIZ-3.**

### 1.5 What reaches the overlay

- **No wire to the overlay exists yet.** The only wire schema is `Hello` (`contracts/wire/hello.json`). The WS server (Snapshot, Delta) is NX-170, not started (`docs/planning/TRACKER.md:174`). The overlay runs from a mock feed (`apps/overlay/src/app.ts:3`).
- **The specified `EntityView`** carries `pos:{x_m:int, y_m:int}`, `heading_deg:int` and `speed_mps:int`. It has no velocity vector, height, band, path or attitude (`docs/specs/CONTRACTS.md:266-267`). `LastKnownView` has a position and heading (`CONTRACTS.md:274`).
- **Interpolation:** render at server time minus 100 ms, linear, extrapolating at most 200 ms (OV-7, `docs/specs/OVERLAY.md:58`; `docs/architecture/adr/0005-overlay-renderer.md:11`).
- **Overlay types:** `VisualUnit` has `x`, `y`, an optional `z` described as "altitude in meters (0 for ground, 30..60 for air)", `vx`, `vy`, `headingDeg` and `speedMps` (`apps/overlay/src/types/unit.ts:24-30`). The mock feed sets jets at `z: 45` (`apps/overlay/src/simulation/mock-feed.ts:166`).
- **The 3D prototype engine** ignores `z`: air units are drawn at a fixed height of 40 scene units, ground units at terrain base + 1.2. Only yaw is applied (`apps/overlay/src/renderers/holo3d/holo-engine.ts:422-434`).
- **The "elevation budget"** is a set of display constants to avoid Z-fighting: water −3.5, terrain 2.0, northern hills 32.0, road offset 0.22, bridge deck 2 to 14, vehicle ride height 0.35, air cruise 45.0 (`apps/overlay/src/theater/elevation.ts:7-16`). The visual-engineer role repeats part of it (`.agents/roles/visual-engineer.md:15`). These are scene heights, not world metres (see §6).

## 2. The gap, per vehicle class

| Class | Exists today | The owner's goal needs | Gap |
|---|---|---|---|
| Jets (3 kinds) | Straight legs at 250 m/s; instant heading change at waypoints; instant speed change; orbit at 100 m/s, radius about 1.9 km; band MED, no height | Smooth turns with bank, climb out after takeoff, descent to land, a believable height | Turns: **kernel** (instant turn). Bank, pitch, climb and descent: renderer, derived. Height: renderer, from band |
| UAVs (2 kinds) | As jets at 60 m/s; orbit at 20 m/s, radius about 380 m | As jets, gentler | As jets. At 60 m/s an instant turn is small on the map (see §3 A) |
| Helicopters | None | — | Not a `UnitKind`. Out of scope until one is added to content |
| Trucks, convoys, armor on roads | Straight edges at 20 to 25 m/s; snap at nodes; flat `speed_mult` 1.0 | Ride the ground's height; pitch on slopes; roll on side slopes; slower uphill | Height, pitch, roll: renderer, from a heightmap. Corners: renderer (sub-pixel radius). Slope speed: offline bake into `speed_mult`. **No heightmap file exists** |
| Off-road ground | Not possible (`step.py:265-266`) | — | Not in any spec. Off-road movement is what would truly need terrain in the kernel |
| Infantry | 5 m/s on roads | As trucks | As trucks |
| Ships | None (sea domain P3) | Heading, wake, gentle roll | Out of scope now. When added: flat sea, so yaw from heading and cosmetic roll only |
| Facilities | Static | Sit on the ground | Renderer: sample the heightmap at the site |

Orbit figures computed: radius = `min_speed_mps × orbit_period_s / 2π` (`step.py:228-231`). Jet: 100 × 120 / 2π ≈ 1,910 m. UAV: 20 × 120 / 2π ≈ 382 m.

## 3. Options

Each option lists size (S/M/L), determinism risk, CPU risk, replay impact and what viewers see.

### A. Render-only attitude from today's 2D motion, heightmap sampled only in the renderer

The renderer derives everything:
- **Yaw** = heading (`heading_deg`).
- **Turn rate ω** from the interpolated path. Don't use differences of `heading_deg`, which is a whole degree and would make ω noisy.
- **Bank (roll)** for aircraft from a coordinated turn: `tan φ = v·ω / g`.
- **Pitch** for aircraft from the display climb rate (takeoff ramp, landing ramp, band change); for ground units from the road slope sampled from the heightmap.
- **Height** from the band (Q-VIZ-3) for aircraft, and from the heightmap plus ride height for ground units.

Check against the existing orbit (computed, world time): ω = 2π / 120 s ≈ 0.052 rad/s. Jet: tan φ = 100 × 0.052 / 9.81 ≈ 0.53, so φ ≈ 28°. UAV: tan φ ≈ 0.107, so φ ≈ 6°. Both look plausible.

**The problem is waypoint turns.** The sim turns in one tick, so ω is a spike. The renderer has two choices:
1. Show the snap: a jet's heading flips in 0.1 s of real time, and the bank would clamp to its limit for one frame.
2. Draw a smooth arc: the arc leaves the sim position. Example (computed): a jet at 250 m/s with 60° bank turns on a radius of v² / (g·tan φ) = 62,500 / (9.81 × 1.73) ≈ 3.7 km. In a 90° turn, the arc stays up to r(√2 − 1) ≈ 1.5 km from the corner. On a full-screen 400 km map at 1920 px (about 208 m per pixel), that's about 7 px. Worse, `EntityView` carries no path, so the renderer can't see the turn coming. It would start turning late and swing wide on the outside.

The audit already ruled that the renderer "must never draw a unit away from its sim position" (V-10, `VISUALIZER-KERNEL-AUDIT-2026-10-26.md:21`; OV-7, DI-1). So option 2 conflicts with a ruling the owner accepted.

**For ground units this is fine.** At 25 m/s a realistic corner radius is tens of metres **[UNVERIFIED: typical road-vehicle turning figures]**, which is under one pixel at map scale. Only a close 3D camera would notice.

| | |
|---|---|
| Size | M (NX-177 already plans an interpolator; adds the attitude rules) plus the heightmap file (Q-MV-7) |
| Determinism risk | None: the kernel doesn't change |
| CPU risk | Renderer only. A few trig calls per unit per frame. The 3D view has a 60 FPS budget (`.agents/roles/visual-engineer.md:17`) |
| Replay | None. A replay from recorded frames shows the same attitude, because it's a pure function of the frames |
| Viewers see | Top-down: units rotate to heading, trucks follow roads. Jets snap at turns, or swing up to ~1.5 km off their true position. 3D: banked orbits, climb-outs, trucks pitching over hills |

### B. Kinematic motion in the kernel

Split it, because the parts have very different costs and value.

**B1. Turn-rate (and optional acceleration) limits for aircraft, still 2D.**
- Store heading as state, or keep deriving it from `vel`.
- Each tick an aircraft turns toward its next waypoint by at most `max_turn_rate × world_dt`.
- A waypoint counts as reached within a capture radius. Today's arrival is an exact snap (`step.py:302-309`).
- Optional: speed ramps up and down at `accel_mps2` instead of jumping.
- Ground units stay on the graph, unchanged (positions on edges is an NX-121 property, `TRACKER.md:96`).

| | |
|---|---|
| Size | M |
| Determinism risk | Low. It uses the same float `atan2`, `sin`, `cos` that `_orbit` already uses (`step.py:248-254`). Heading needs a quantization rule in `state_hash` (like 1e-6 rad). Needs a determinism test (rule 3) |
| CPU risk | Low. Movement is 0.79 ms p99 at 1,000 entities (`NX-345-BENCH.md:47`), and this adds a few trig calls per aircraft per tick |
| Replay | Goldens re-pin. Travel times change, so balance moves. Bingo uses straight-line distance (`step.py:217-225`) and needs a margin for the turn. Orbit entry joins up with the turn |
| Viewers see | Jets fly real arcs on the 2D map, in the right place. The renderer's bank is honest because ω is real |

**B2. Height as kernel state, with a terrain heightmap in the sim.**
- Add `z` (float m) per unit and a terrain table in `Rules`, loaded from the PNG into an integer table and included in the config hash.
- Ground z = terrain at position. Aircraft z follows the band nominal height (MSL, or AGL over terrain).
- Slope sampled along each edge changes ground speed.

| | |
|---|---|
| Size | L (loader, `Rules`, `Entity`, world encoding version, hash, snapshots, contracts if on the wire, content heights per band) |
| Determinism risk | Medium. Sample with integer arithmetic (nearest cell or integer bilinear). Bilinear in floats is deterministic on one platform (ADR-0002), but it's another surface |
| CPU risk | Low for z (one lookup per unit per tick); unmeasured for anything that samples along a line |
| Replay | Goldens re-pin. The heightmap enters the config hash (TH-8, `CONFIG-AND-CONTENT.md:636`) |
| Viewers see | Same as A plus B1. **B2 adds nothing visible over A** unless gameplay reads the height |

B2 only pays off when gameplay reads height:
- **Slope speed:** can be baked offline into `speed_mult` with no kernel change (audit V-5, `VISUALIZER-KERNEL-AUDIT-2026-10-26.md:18`).
- **Masking:** already decided as an offline bake (Q-VIZ-1).
- **Live line of sight:** sized L, cost unmeasured, would reopen Q-FOW-3 (Q-VIZ-1, `OPEN-QUESTIONS.md:813`).
- **Off-road driving:** not in any spec.

**B3. Line of sight from a real heightmap.** This needs B2's height per unit, a height per sensor (mast) and band, and DEM samples along each sensor–target pair on every sensing pass (every 5 ticks). Sensing is already the largest system (4.63 ms p99, `NX-345-BENCH.md:47`). Size L. A bench decides it, not a guess.

### C. A physics engine in the renderer only (cosmetic)

For things like debris, a wreck tumbling, a bridge span falling, or smoke. It runs in the browser on render state and never feeds back into the sim. Candidate browser physics libraries exist (for example Rapier or cannon-es) **[UNVERIFIED: current names, licenses and maintenance; check per AGENTS.md rule 8 before adding]**.

| | |
|---|---|
| Size | M per effect family, plus a new dependency review |
| Determinism risk | None for the sim. The effect may differ between clients, which is fine for cosmetics |
| CPU risk | Browser GPU and CPU on the broadcast PC, inside the 60 FPS budget. It can hurt the OBS encode |
| Replay | A replay from recorded frames may show different debris. That's acceptable if it's labelled cosmetic |
| Viewers see | Nicer explosions and wrecks in 3D views only. Nothing on the top-down Canvas2D map |

Timing: with the Three.js picture-in-picture or replay viewer (Q-VIZ-6; ROADMAP P5, `docs/planning/ROADMAP.md:12`).

### D. A physics engine in the sim (not recommended)

- **Determinism.** SC-1 requires `step` to be pure and deterministic (`SIM-CORE.md:13`). General physics engines are often not bit-reproducible across builds or thread counts **[UNVERIFIED for any specific engine]**. The kernel bans threads and nondeterministic float reductions (AGENTS.md rule 3).
- **CPU.** Rigid-body integration needs small fixed sub-steps. The kernel runs at 10 Hz with 0.6 world seconds per tick, a very large physics step. Getting stability at that step means sub-stepping for 1,000 entities in Python inside a 25 ms budget.
- **No gameplay value.** Chat commands work at node and order level (GOTO, FOLLOW, HOLD; `world.py:241-245`). Nobody steers a stick. Rigid-body detail would change no decision a viewer makes.
- **Cost.** A new native dependency (rule 8), new failure modes, harder balance tuning, and goldens that depend on the engine's version.
- **What it would take to reconsider:** direct control of a vehicle by a viewer, or collisions as a game mechanic. Neither is in VISION or the specs.

| | |
|---|---|
| Size | L+ |
| Determinism risk | High |
| CPU risk | High |
| Replay | Tied to the engine's build. Re-simulation across versions already doesn't work (audit V-16) |
| Viewers see | Little beyond A plus B1 at map scale |

### Recommendation

**A for attitude, plus B1 for aircraft turns. No B2 until gameplay reads height. C later, D never.**

Phased path:

| Phase | Work | Kernel change |
|---|---|---|
| P2 (with NX-170 and NX-177) | A: yaw from heading; coordinated-turn bank from the smoothed path; aircraft height from the band (Q-VIZ-3); cosmetic takeoff and landing ramps (z only, x and y stay true); ground ride height from a renderer-side heightmap when one exists (NX-176) | None |
| P2, if the owner wants arcs on the main map | B1: per-kind `max_turn_rate` (and optional `accel_mps2`) for AIR in the unit catalog | M; goldens re-pin; harness re-run |
| P2 or P3, once a heightmap exists | Author the strait-1 heightmap PNG (Q-CFG-3). Bake masking cells (Q-VIZ-1) and per-edge slope into `speed_mult` offline. The renderer uses the same file for ground height | None (content and tools only) |
| P3 with the sea domain | Ships: yaw from heading, cosmetic roll | None beyond the sea domain itself |
| P4 or later, only if wanted | B2 plus B3: height in the kernel and live line of sight, after a sensing bench at 1,000 entities | L; reopens Q-VIZ-3 and Q-FOW-3 |
| P5 | C: cosmetic physics in the 3D picture-in-picture or replay viewer | None |

## 4. Questions for the owner

| ID | Question | Options | Recommendation |
|---|---|---|---|
| Q-MV-1 | Are roll, pitch and yaw display-only? | (a) Derived in the renderer, never sim state or wire fields. (b) Kernel state | **(a).** Consistent with Q-VIZ-3 and the audit's V-10. Yaw is already on the wire as `heading_deg` |
| Q-MV-2 | Should aircraft turn with a turn-rate limit in the kernel? | (a) Keep instant turns; the renderer shows the snap. (b) Keep instant turns; the renderer draws arcs that leave the true position by up to ~1.5 km. (c) Kernel per-kind `max_turn_rate` for AIR (B1) | **(c)**, for AIR only. (b) breaks the V-10 ruling, and (a) looks wrong for jets. Cost M; goldens and travel times move |
| Q-MV-3 | Should aircraft accelerate instead of jumping between 0, top speed and stall speed? | (a) No: instant speed. (b) A kernel `accel_mps2` per kind. (c) Renderer-only ramp | **(a) for now, (b) with Q-MV-2 if it's cheap in the same item.** A renderer ramp (c) would draw the jet behind its true position |
| Q-MV-4 | Do ground units stay on the road graph, with corners smoothed in the renderer? | (a) Yes. (b) Kernel turn limits for ground units too. (c) Off-road movement | **(a).** At 25 m/s the corner radius is under a pixel at map scale. (b) would take units off their edges, and (c) is new design work that needs terrain in the kernel |
| Q-MV-5 | Does terrain slope change ground speed? | (a) No. (b) Baked offline into each edge's `speed_mult` from the heightmap. (c) The kernel samples slope live | **(b)**, once a heightmap exists. No kernel change, and it's in the config hash already (the theater file). With curved roads (Q-VIZ-2), bake per segment |
| Q-MV-6 | Should altitude become continuous metres in the kernel, or stay bands? | (a) Bands, with a nominal display height per band. (b) Continuous metres in the kernel | **(a).** (b) reopens Q-VIZ-3, and nothing in gameplay reads metres. Sub-question: put the per-band heights in content (one table, all renderers agree) rather than in renderer constants. Values would be PROPOSED |
| Q-MV-7 | What is a band's height measured from? | (a) All above sea level. (b) All above ground. (c) NOE and LOW above ground (terrain-following look); MED and HIGH above sea level with a floor of terrain plus a margin | **(c).** It looks right over hills and never draws a MED jet inside a mountain |
| Q-MV-8 | Heightmap source and resolution? (Q-CFG-3 fixed the format: 16-bit PNG) | Source: hand-authored, generated by a seeded tool, or real elevation data **[UNVERIFIED: licensing of any real dataset]**. Resolution for 400 × 240 km: 100 m cells (4000 × 2400, ~19 MB raw), 250 m (1600 × 960, ~3.1 MB raw), 500 m (800 × 480, ~0.8 MB raw) | **Fictional, from a seeded tool, committed as the PNG, 250 m cells.** Sizes computed as cells × 2 bytes, before PNG compression. A formula at runtime is out (audit, `VISUALIZER-KERNEL-AUDIT-2026-10-26.md:17`) |
| Q-MV-9 | Do aircraft follow terrain at NOE? | (a) No unit flies NOE now; the renderer terrain-follows NOE and LOW visually if one ever does. (b) A band-change command and NOE gameplay | **(a).** No kind lists NOE, and no command changes band (Q-CBT-11, Q-VIZ-4). (b) stays in GAMEPLAY-LATER |
| Q-MV-10 | Is line of sight over terrain wanted, and when? | (a) Keep Q-VIZ-1: masking cells baked offline from the heightmap. (b) Live line of sight in the kernel | **(a) through P3.** Revisit (b) in P4 or later, only after a sensing bench at 1,000 entities. It needs height in the kernel (B2) and reopens Q-FOW-3 |
| Q-MV-11 | If height enters the kernel later: fixed-point or float? | (a) float64 z, quantized to mm in `state_hash`, as positions are now. (b) Fixed-point | **(a)**, consistent with ADR-0002. The heightmap stays an integer table, sampled with integer arithmetic |
| Q-MV-12 | Wire changes for heading, height and velocity? | (a) None for P2: `pos`, `heading_deg`, `speed_mps`, and the band from the catalog. (b) Add `alt_m` and a velocity vector | **(a).** Add `alt_m` only if height becomes kernel state (Q-MV-6 b). A 1° heading step is invisible for yaw. The renderer gets turn rate from positions, not from heading differences |
| Q-MV-13 | A physics engine at all? | (a) Never in the sim; cosmetic in the renderer's 3D views later. (b) Renderer never. (c) In the sim | **(a).** See §3 D. Revisit only if viewers get direct control of a vehicle |
| Q-MV-14 | Should a landed aircraft count as a MED-band target? Today it keeps its kind's band on the ground (`world.py:766`), and targeting checks only the band (`combat.py:405-416`). COMBAT CB-7 expects landed aircraft to be hit (`COMBAT.md:22`). In 3D, a SAM that reaches only MED would be shown hitting a jet parked at 0 m | (a) Keep: a parked jet is hit like an airborne one. (b) Landed aircraft count as ground targets (any weapon that targets GROUND) | **Lead: no recommendation; it's a combat-balance question.** It's raised here because it decides what a 3D view can honestly show |
| Q-MV-15 | Should turn rates and bank use world time or screen time? At 6× a 120 s world orbit takes 20 real seconds | (a) World time: physically consistent bank, but the map turns six times faster than a real aircraft would. (b) Screen time | **(a).** Bank depends on world speed and world turn rate, which is what the sim simulates. The fast map is the time scale's job, not a bug |

## 5. Proposed tracker rows (not added)

Numbers are left out so they don't collide with parallel sessions. The coordinating session assigns them.

| Proposed row | Size | Depends on | Acceptance |
|---|---|---|---|
| Overlay attitude derivation (renderer): yaw from heading, coordinated-turn bank from the interpolated path, pitch from the display climb or road slope, height from the band table; replaces the drifted DECOUPLED-RENDERER §2.3 maths | M | NX-177, Q-MV-1, Q-MV-6, Q-MV-7 | Unit tests: orbit bank matches `atan(v·ω/g)`; a unit is never drawn away from its interpolated sim x, y |
| AIR turn-rate limit in the kernel (B1): per-kind `max_turn_rate` in the unit catalog, capture radius at waypoints, bingo margin; optional `accel_mps2` | M | Q-MV-2, Q-MV-3 | Determinism test; property: heading change per tick ≤ limit; goldens re-pinned; harness re-run shows no A1–A4 regression |
| strait-1 heightmap: a seeded generator in `tools/terrain`, committed 16-bit PNG, schema fields `heightmap`, `height_scale_m`, `sea_level_m`, TH-8 check | M | Q-MV-8, Q-CFG-3 | Loader validates dimensions against `bounds_m`; content hash covers the file; no kernel code reads it |
| Offline bakes from the heightmap: masking cells (Q-VIZ-1) and per-edge slope into `speed_mult` (Q-MV-5) | M | heightmap row | The bake is reproducible from the PNG; goldens re-pin when values change |
| Per-band nominal heights in content (Q-MV-6, Q-MV-7) | S | Q-MV-6 | One table, read by every renderer; values marked PROPOSED |
| Reconcile the visualizer elevation numbers (§6) into one documented display scale | S | heightmap row | `elevation.ts`, the visual-engineer role, TERRAIN-AND-BIOMES and ROAD-AND-BRIDGE-TAXONOMY agree, or each says which scale it uses |
| Later, if wanted (P4+): kernel height and line-of-sight spike with a sensing bench | L | Q-MV-10 | Bench at 1,000 entities on the reference host before any spec change |

**Specs that would change:**
- SIM-CORE §4 Movement (`SIM-CORE.md:51`): B1 only.
- CONFIG-AND-CONTENT §7.3 unit catalog: turn rate, accel, band heights. Also the `terrain` row (`CONFIG-AND-CONTENT.md:612`) and TH-8 (`:636`).
- OVERLAY: a new requirement next to OV-7 for derived attitude and the "never off the sim position" rule.
- COMBAT §5.3 (`COMBAT.md:92-93`): band nominal heights, if they live in content, and Q-MV-14's outcome.
- CONTRACTS §7 `EntityView`: no change under the recommendation.
- FOG-OF-WAR: no change unless Q-MV-10 (b).
- DECOUPLED-RENDERER §2.3, ROAD-AND-BRIDGE-TAXONOMY and TERRAIN-AND-BIOMES: corrections from §6.

## 6. Visualizer docs that promise 3D behaviour the sim can't back

These docs are Draft or Proposed and not law. Each already carries the audit's "Kernel facts check" note.

| Doc | Promise | Why the sim can't back it |
|---|---|---|
| DECOUPLED-RENDERER §2.3 (`docs/architecture/DECOUPLED-RENDERER-ARCHITECTURE.md:83-118`) | Pitch from vertical climb rate ż; helicopter cyclic attitude; canyon-wall weaving that pushes the visual path toward the valley | There is no ż, no helicopter kind and no NOE unit. Weaving moves the drawn unit off its sim position (V-10). The coordinated-turn bank formula is usable, but needs ω from a smoothed path (§3 A) |
| Same doc, `rollDeg` and `pitchDeg` frame fields (`:178-179`) | Attitude as part of the frame state | Fine as renderer-internal values; not wire or sim fields (Q-MV-1) |
| DETERMINISTIC-REPLAY-AND-MULTI-CAMERA-CINEMATICS (`docs/specs/DETERMINISTIC-REPLAY-AND-MULTI-CAMERA-CINEMATICS.md:7`, Draft) | Bit-for-bit re-simulation years later (`:21-22`); helicopter and ship POV passes (`:65-66`); canyon-run chase and cockpit with "NOE CANYON MASKED" (`:73-74`); 6-DOF banking and AoA pitch over a DTED mesh (`:248`) | Re-simulation works only on the same commit and image (audit V-16). No helicopter or ship kinds. No unit flies NOE, and masking is per-area, not canyon line of sight |
| SIMULATION-TERRAIN-AND-ROAD-INTEGRATION-RFC (`docs/architecture/SIMULATION-TERRAIN-AND-ROAD-INTEGRATION-RFC.md:121-128`) | A "2.5D" kernel with metre-threshold bands and line-of-sight raycasts against a DTED `.bin` | Bands have no metres; masking is per-area (Q-FOW-3); the `.bin` is out (Q-VIZ-1, Q-CFG-3) |
| UNIT-POV-AND-COCKPIT-CONTRACTS-RFC (`docs/architecture/UNIT-POV-AND-COCKPIT-CONTRACTS-RFC.md:78`, `:130`, `:239`) | A "NOE CANYON MASKED" badge from DEM ridges; barometric altitude and G-meter tapes; a miss when the scout loses line of sight | No line of sight, no altitude, no G. A miss comes from the hit roll and track state (CB-3, audit V-14) |
| Skill reference `.agents/skills/hiveplex-visualization/references/six-dof-kinematics-and-canyon-runs.md:32`, `:68` | The kernel supplies `v_z` | There is no `v_z` (`world.py:264`) |
| TERRAIN-AND-BIOMES (`docs/specs/TERRAIN-AND-BIOMES.md:59-66`) | Biomes with speed multipliers, NOE masking and "impassable for trucks" | No kernel code reads biomes; ground units move only on the road graph (audit, `VISUALIZER-KERNEL-AUDIT-2026-10-26.md:62`) |
| ROAD-AND-BRIDGE-TAXONOMY (`docs/specs/ROAD-AND-BRIDGE-TAXONOMY.md:31-32`, `:38-45`) | Roads draped over a continuous DEM; a north viaduct at about +450 m and a south bridge at about +25 m | No DEM exists in the repo. These heights don't match the overlay's display constants |

**The elevation numbers don't agree with each other:**
- Northern hills are 32.0 in `apps/overlay/src/theater/elevation.ts:11`.
- TERRAIN-AND-BIOMES gives a 2500 m height scale (`:17`) and highlands at +450 to +2500 m (`:65`).
- The bridge deck is 2 to 14 in `elevation.ts:13-14`, +2.0 in the role card (`.agents/roles/visual-engineer.md:15`) and in TERRAIN-AND-BIOMES (`:141`, `:147`), and about +450 m for the north viaduct in ROAD-AND-BRIDGE-TAXONOMY (`:39`).
- Air cruise is 45.0 (`elevation.ts:16`), and the overlay type says "30..60 for air" (`apps/overlay/src/types/unit.ts:26`).

The "elevation budget" is a compressed scene scale for Z-fighting, not world metres. Whatever band heights the owner picks under Q-MV-6 need one stated display scale. Otherwise a MED jet at its nominal height and a hill drawn at 32 scene units can't share a 3D view.
