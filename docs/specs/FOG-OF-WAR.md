# SPEC: Fog of War

Status: Draft · Tracker: NX-150…NX-154 · Inputs: P228–238; owner rule C22 ("AI should only know what it can see")

## 1. Tiers (coalition perspective)
| Tier | Condition | Shown to viewers |
|---|---|---|
| 0 Unknown | No coverage, no SIGINT | Nothing |
| 1 SIGINT | Group of enemy units outside sensors, aggregated per **cluster** (grid cell, ≥1 unit) | Fuzzy blob drawn at its 10 km cell (no server jitter; the overlay may add a cosmetic offset derived from the blob id, Q-FOW-5), refreshed every ~48–60 s of world time (PROPOSED; about 8–10 s real at `sim.time_scale` 6, Q-ALN-23, Q-ALN-38), size bucketed (S/M/L), opaque id per cluster per refresh |
| 2 Track | Inside any coalition sensor (unit, radar site). **Deterministic (Q-FOW-2):** a target is tracked when it is inside the sensor's range for its domain and altitude band, times modifiers (stealth; jamming later; terrain masking); no detection roll. **Terrain masking (Q-FOW-3):** NOE/LOW aircraft and ground units inside a theater `masking_regions` polygon (rasterized to grid cells at load) are hidden from sensors outside that region; no line-of-sight rays | Exact symbol, type, heading, health bar. A tracked target may also carry the **painted** flag (recon unit painting within paint range): a marker and a combat bonus, not a separate tier (Q-FOW-6) |

## 2. Requirements
- **FOW-1** Redaction MUST happen server-side, before serialization. Hidden entities MUST NOT appear in any payload sent to the overlay, the companion site, the public-site exports pushed while a campaign is running (leaderboards/stats JSON, Q-ARCH-16), or replays meant for the public.
- **FOW-1a** **After the campaign ends (Q-ALN-21):** FoW applies only during the live campaign. Once a campaign has ended, its full archive (Q-ARCH-16), its replays and recaps, and the AAR "what you didn't see" reveal are exempt from FOW-1 and may show full, unredacted history. Anything published while the campaign is still running stays under FOW-1.
- **FOW-2** SIGINT blobs MUST NOT leak entity ids, exact counts, or exact positions. Positions are the cell only; there is no server jitter and no `fow` RNG stream (Q-FOW-5).
- **FOW-3** Events (kill feed, tracers) involving hidden enemy units MUST be redacted ("Unknown contact destroyed VIPER-27").
- **FOW-4** **Director fairness:** the Threat Director MUST decide using the *enemy-side* FoW view, built with the same algorithm from the enemy's sensors. This includes the jobs it posts on the Static's Tasking Board (Q-GD-34, THREAT-DIRECTOR TD-2). Exception: spawning in its own territory.
- **FOW-5** FoW computation uses the spatial grid and runs every `fow.track_every_ticks` (PROPOSED 5 = 0.5 s; every tick if the NX-345 spike shows it is cheap; Q-FOW-6) for Tier 2 and the painted flag; combat always uses the latest computed view; and every ~48–60 s of world time for Tier 1 (the sensor refresh; PROPOSED until harness-validated, chosen so the real cadence stays about 8–10 s at `sim.time_scale` 6; Q-ALN-23, Q-ALN-38).
- **FOW-8** **Per-side Tasking Boards (Q-GD-37 item 9):** each side's board is generated only from that side's own FoW view. A coalition job MUST NOT reference an entity the coalition can't see; a job against a SIGINT blob references the blob's opaque id and quantized cell, never an entity id. The overlay's NEEDED list is therefore redacted by construction (FOW-1).
- **FOW-9** **Time and pauses (Q-CFG-8, Q-ALN-23):** every FoW timer (Tier 1 refresh, `fow.track_fade_s`) is **world time** (scaled by `sim.time_scale`, SIM-CORE SC-2) and is converted to ticks at config load, rounding up (Q-ALN-6). While the campaign is paused (SIM-CORE SC-11) none advances: a last-known track does not age and no blob re-rolls.
- **FOW-10** **Enemy knowledge of nodes (Q-SIM-10, Q-GP-27):** both sides' views always include node and facility positions and facility kinds; facility state comes only from sensors. `EnemyView` always includes node positions, the state of the enemy's own nodes and the owner of every node. It never includes coalition stock or coalition unit positions except through current enemy detections and last-known tracks. The director may scout (ordinary ENEMY units, Q-SIM-11) to refresh them.

## 2a. Track fade (owner, 2026-10-17)
- **FOW-6a (first build, both sides; Q-FOW-1, partly reverses Q-ALN-20):** when sensor coverage of a tracked contact is lost (scout destroyed, out of range, radar jammed), the contact does not vanish. It becomes a **last-known track**: its position, kind and heading freeze and are shown with an age, and after `fow.track_fade_s` (PROPOSED, world time) it is dropped. The director's `EnemyView` uses the same last-known tracks (FOW-10, THREAT-DIRECTOR TD-5).
- **FOW-6** (later phase, behind a feature flag; Q-PROD-8, Q-ALN-20; NX-301 does not block P1): the last-known track additionally grows an uncertainty circle and decays into a SIGINT blob instead of being dropped.

## 2b. Target handoff (P4)
- **FOW-7:** A painting scout can hand a target to a long-range shooter (strike missile, artillery, theater asset). That extends the shooter's effective range (beyond its own sensors) and raises Pk while the paint holds. If the paint drops, the shot reverts to blob accuracy.

## 3. Tests
- Property: no redacted payload contains an entity that fails the visibility predicate.
- Blob ids are unlinkable across refreshes.
- Director decision functions receive only `EnemyView` (enforced by types).
- FOW-8: property: no job on either side's board references an entity that fails that side's visibility predicate.
- FOW-9: a last-known track's age and uncertainty radius are identical at the pause tick and the resume tick; with `sim.time_scale` = 6 the Tier 1 refresh fires after one sixth of the ticks it takes at `sim.time_scale` = 1 (before tick rounding).
- FOW-1: a public-site export built mid-campaign contains no entity that fails the coalition visibility predicate.
- FOW-1a: the end-of-campaign archive and "what you didn't see" view are built only after the campaign has ended; attempting to build either for a running campaign is rejected.
- FOW-6a: losing coverage produces a last-known track with the frozen position and an age; it is dropped after `fow.track_fade_s`, and the same holds in `EnemyView`. FOW-6: with the flag off, no uncertainty circle and no decay into a blob.
- Q-FOW-2: detection is a pure function of positions, ranges and modifiers (no RNG draw); Q-FOW-3: a LOW aircraft inside a masking region is not tracked by a radar outside it.
- Q-FOW-4: no unit engages a target that is not tracked.

## 4. Open questions
Decided and folded in: Q-GD-16 (track fade, target handoff), Q-GD-34, Q-GD-37, Q-PROD-8, Q-ARCH-16, Q-CFG-8, Q-ALN-20 (FOW-6 later behind a flag), Q-ALN-21 (post-campaign archive exempt from FOW-1), Q-ALN-23 (Tier 1 refresh and track fade on world time, FOW-5, FOW-9), Q-ALN-38 (Tier 1 refresh re-expressed as ~48–60 s world, PROPOSED, FOW-5). Nothing is open here.
Decided in the 2026-10-19 grilling: Q-FOW-1 (minimal last-known tracks on in the first build, FOW-6a), Q-FOW-2 (deterministic detection), Q-FOW-3 (terrain masking by `masking_regions`), Q-FOW-4 (engage tracked targets only), Q-FOW-5 (no blob jitter, no `fow` stream), Q-FOW-6 (painted is a flag; Tier 2 every 5 ticks unless cheap).
