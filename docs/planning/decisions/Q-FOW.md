# Decided questions: Q-FOW

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## FOG-OF-WAR grilling (2026-10-19)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-FOW-1 | Last-known tracks in the first build | Minimal version on for both sides: a lost track freezes with its age and is dropped after `fow.track_fade_s`; uncertainty circle and decay into a blob stay behind the FOW-6 flag. Partly reverses Q-ALN-20; needed by the director's view (Q-SIM-10, TD-5). | P1 | ✅ 2026-10-19 |
| Q-FOW-2 | Detection model | Deterministic: in range for the target's domain and altitude band, times modifiers; no detection roll. | P1 | ✅ 2026-10-19 |
| Q-FOW-3 | Terrain masking | Per-area flag, not line of sight: the theater's existing `masking_regions` polygons, rasterized to cells, hide NOE/LOW aircraft and ground units from sensors outside them. Combat factor 6 uses the same flag. | P1 | ✅ 2026-10-19 |
| Q-FOW-4 | Shooting at blobs | First build engages tracked targets only; blobs are scouted, not shot. Area weapons may hit blobs later. | P1 | ✅ 2026-10-19 |
| Q-FOW-5 | SIGINT jitter | No server jitter; blob at its cell; cosmetic offset client-side from the blob id; `fow` RNG stream removed. | P1 | ✅ 2026-10-19 |
| Q-FOW-6 | Painted tier and update cadence | Painted is a flag on a track. Tier 2 recomputed every 5 ticks unless the NX-345 spike shows every tick is cheap. | P1 | ✅ 2026-10-19 |
| Q-FOW-7 | Where SIGINT blobs come from | Only groups that are moving or emitting, within `fow.sigint_range_mult` × a friendly radar site's range; parked silent units leave no blob. Same rule for the director's view. | P1 | ✅ 2026-10-19 |
| Q-FOW-8 | Emitting radars (revised by Q-FOW-12/15: emission is detected only by a passive sensor) | Whether a radar or air-defense site is emitting is visible to the other side whenever it emits; dark = unknown. Owner asked who controls emission (Q-FOW-10). | P1 | ✅ 2026-10-19 |
| Q-FOW-9 | Spotted indicator | Own units show `spotted` while any enemy sensor tracks them. | P1 | ✅ 2026-10-19 |
| Q-FOW-10 | Who switches emission | Sites emit by default. The director blinks Static sites through `DecoyBlink`; coalition sites stay on in the first build. A self-protection rule and a possible player command come with SEAD (GAMEPLAY-LATER). | P1 | ✅ 2026-10-19 |
| Q-FOW-11 | FOG-OF-WAR status | Reviewer pass, then Approved (owner); it does not wait for NX-008 or NX-345, whose only effect here is the update cadence fallback. | P1 | ✅ 2026-10-19 |
| Q-FOW-12 | Does an emitting site reveal its ring? | Owner: not without a passive sensor looking for it (FOW-13), and more: a base's facilities that haven't been scouted must not appear on the map at all. Bases are known; neither side knows a base's capabilities until confirmed by air, ground or any other ISR. Reverses the facility part of Q-GP-27 and FOW-10. Discovery model open (Q-FOW-15). | P1 | ✅ 2026-10-19 |
| Q-FOW-13 | Blink asymmetry | Kept and justified: DecoyBlink is a deception tool for the AI enemy; coalition parity arrives with SEAD. Owner: an emitted signature must not be visible without something looking for it; an AWACS-type sensor can detect high-power emissions at long range and mark the threat, radar or ring permanently once, updating only if it is upgraded or destroyed (Q-FOW-15). | P1 | ✅ 2026-10-19 |
| Q-FOW-14 | What feeds coalition power | Currently tracked coalition units only; last-known tracks feed only Recon utility. | P1 | ✅ 2026-10-19 |
| Q-FOW-15 | How facilities are discovered | Bases are known; enemy facilities only once discovered: an active track, a passive sensor (recon units and radar sites; AWACS later) within `sensor.passive_range_m` of an emitting site, or capturing the base. Discovery is a permanent marker (position, kind, variant, ring); details refresh only on re-observation with a "last confirmed" age. Owner: unsensed strikes and repairs must never be exposed. Same for the director. | P1 | ✅ 2026-10-19 |
| Q-FOW-16 | Track quality in the first build | Evaluated at impact: no track or out of envelope at impact = miss. Dynamic in-flight track quality (outrunning by range, jamming changing it in flight, seekers) is parked in GAMEPLAY-LATER. | P1 | ✅ 2026-10-19 |
| Q-FOW-17 | Announcing IADS reinforcement | Keep the INTEL line at sector level only; it never names a site or updates a marker. Approves FOG-OF-WAR. | P1 | ✅ 2026-10-19 |
