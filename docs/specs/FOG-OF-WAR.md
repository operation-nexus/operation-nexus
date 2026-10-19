# SPEC: Fog of War

Status: Draft · Tracker: NX-150…NX-154 · Inputs: P228–238; owner rule C22 ("AI should only know what it can see")

## 1. Tiers (coalition perspective)
| Tier | Condition | Shown to viewers |
|---|---|---|
| 0 Unknown | No coverage, no SIGINT | Nothing |
| 1 SIGINT | Group of enemy units outside sensors, aggregated per **cluster** (grid cell, ≥1 unit) | Fuzzy blob: position quantized to a 10 km cell plus server-side random jitter (`fow` RNG), refreshed every ~48–60 s of world time (PROPOSED; about 8–10 s real at `sim.time_scale` 6, Q-ALN-23, Q-ALN-38), size bucketed (S/M/L), opaque id per cluster per refresh |
| 2 Track | Inside any coalition sensor (unit, radar site), respecting terrain masking for NOE/LOW | Exact symbol, type, heading, health bar |
| 3 Painted | Tracked + recon unit painting within paint range | As Track + "painted" marker; combat bonus |

## 2. Requirements
- **FOW-1** Redaction MUST happen server-side, before serialization. Hidden entities MUST NOT appear in any payload sent to the overlay, the companion site, the public-site exports pushed while a campaign is running (leaderboards/stats JSON, Q-ARCH-16), or replays meant for the public.
- **FOW-1a** **After the campaign ends (Q-ALN-21):** FoW applies only during the live campaign. Once a campaign has ended, its full archive (Q-ARCH-16), its replays and recaps, and the AAR "what you didn't see" reveal are exempt from FOW-1 and may show full, unredacted history. Anything published while the campaign is still running stays under FOW-1.
- **FOW-2** SIGINT blobs MUST NOT leak entity ids, exact counts, or exact positions. Jitter comes from the seeded `fow` RNG and is re-rolled each refresh.
- **FOW-3** Events (kill feed, tracers) involving hidden enemy units MUST be redacted ("Unknown contact destroyed VIPER-27").
- **FOW-4** **Director fairness:** the Threat Director MUST decide using the *enemy-side* FoW view, built with the same algorithm from the enemy's sensors. This includes the jobs it posts on the Static's Tasking Board (Q-GD-34, THREAT-DIRECTOR TD-2). Exception: spawning in its own territory.
- **FOW-5** FoW computation uses the spatial grid and runs every tick for Tier 2/3, and every ~48–60 s of world time for Tier 1 (the sensor refresh; PROPOSED until harness-validated, chosen so the real cadence stays about 8–10 s at `sim.time_scale` 6; Q-ALN-23, Q-ALN-38).
- **FOW-8** **Per-side Tasking Boards (Q-GD-37 item 9):** each side's board is generated only from that side's own FoW view. A coalition job MUST NOT reference an entity the coalition can't see; a job against a SIGINT blob references the blob's opaque id and quantized cell, never an entity id. The overlay's NEEDED list is therefore redacted by construction (FOW-1).
- **FOW-9** **Time and pauses (Q-CFG-8, Q-ALN-23):** every FoW timer (Tier 1 refresh, `fow.track_fade_s`) is **world time** (scaled by `sim.time_scale`, SIM-CORE SC-2) and is converted to ticks at config load, rounding up (Q-ALN-6). While the campaign is paused (SIM-CORE SC-11) none advances: a last-known track does not age and no blob re-rolls.
- **FOW-10** **Enemy knowledge of nodes (Q-SIM-10, Q-GP-27):** both sides' views always include node and facility positions and facility kinds; facility state comes only from sensors. `EnemyView` always includes node positions, the state of the enemy's own nodes and the owner of every node. It never includes coalition stock or coalition unit positions except through current enemy detections and last-known tracks. The director may scout (ordinary ENEMY units, Q-SIM-11) to refresh them.

## 2a. Track fade (owner, 2026-10-17)
- **FOW-6** (later phase, behind a feature flag, off in the first build; Q-PROD-8, Q-ALN-20; NX-301 does not block P1): When sensor coverage of a tracked contact is lost (scout destroyed, out of range, radar jammed), the contact does not vanish. It becomes a **last-known track**: its position freezes and is shown with an age timer, its uncertainty circle grows, and after `fow.track_fade_s` (PROPOSED) it decays into a SIGINT blob. Seeded, deterministic, visible.

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
- FOW-6: with the track-fade flag off, losing coverage never produces a last-known track.

## 4. Open questions
Decided and folded in: Q-GD-16 (track fade, target handoff), Q-GD-34, Q-GD-37, Q-PROD-8, Q-ARCH-16, Q-CFG-8, Q-ALN-20 (FOW-6 later behind a flag), Q-ALN-21 (post-campaign archive exempt from FOW-1), Q-ALN-23 (Tier 1 refresh and track fade on world time, FOW-5, FOW-9), Q-ALN-38 (Tier 1 refresh re-expressed as ~48–60 s world, PROPOSED, FOW-5). Nothing is open here.
