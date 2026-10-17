# SPEC: Fog of War

Status: Draft · Tracker: NX-150…NX-154 · Inputs: P228–238; owner rule C22 ("AI should only know what it can see")

## 1. Tiers (coalition perspective)
| Tier | Condition | Shown to viewers |
|---|---|---|
| 0 Unknown | No coverage, no SIGINT | Nothing |
| 1 SIGINT | Group of enemy units outside sensors, aggregated per **cluster** (grid cell, ≥1 unit) | Fuzzy blob: position quantized to a 10 km cell plus server-side random jitter (`fow` RNG), refreshed every 8–10 s, size bucketed (S/M/L), opaque id per cluster per refresh |
| 2 Track | Inside any coalition sensor (unit, radar node), respecting terrain masking for NOE/LOW | Exact symbol, type, heading, health bar |
| 3 Painted | Tracked + recon unit painting within paint range | As Track + "painted" marker; combat bonus |

## 2. Requirements
- **FOW-1** Redaction MUST happen server-side, before serialization. Hidden entities MUST NOT appear in any payload sent to the overlay, the companion site, or replays meant for the public.
- **FOW-2** SIGINT blobs MUST NOT leak entity ids, exact counts, or exact positions. Jitter comes from the seeded `fow` RNG and is re-rolled each refresh.
- **FOW-3** Events (kill feed, tracers) involving hidden enemy units MUST be redacted ("Unknown contact destroyed VIPER-27").
- **FOW-4** **Director fairness:** the Threat Director MUST decide using the *enemy-side* FoW view, built with the same algorithm from the enemy's sensors. Exception: spawning in its own territory.
- **FOW-5** FoW computation uses the spatial grid and runs every tick for Tier 2/3, and every 8–10 s for Tier 1.

## 2a. Track fade (owner, 2026-10-17)
- **FOW-6:** When sensor coverage of a tracked contact is lost (scout destroyed, out of range, radar jammed), the contact does not vanish. It becomes a **last-known track**: its position freezes and is shown with an age timer, its uncertainty circle grows, and after `fow.track_fade_s` (PROPOSED) it decays into a SIGINT blob. Seeded, deterministic, visible.

## 2b. Target handoff (P4)
- **FOW-7:** A painting scout can hand a target to a long-range shooter (strike missile, artillery, theater asset). That extends the shooter's effective range (beyond its own sensors) and raises Pk while the paint holds. If the paint drops, the shot reverts to blob accuracy.

## 3. Tests
- Property: no redacted payload contains an entity that fails the visibility predicate.
- Blob ids are unlinkable across refreshes.
- Director decision functions receive only `EnemyView` (enforced by types).
