# Why Static strikes never reach a base's defenses (NX-458, 2026-10-27)

**What this is:** a code reading at develop `a9787e0`, not a harness run. Per-cause shares are reasoning, not measurements. Asked by the owner on #412 (Q-TD-72): base air defense should start weak, grow when supplied or reinforced, and never kill every strike; are strike packages stacking or flying one line and getting shot down?

**Context:** sweep M (`ENTERTAINMENT-sweep-M0-M4-2026-10-27.md`) found about 94–95% of Static Offensives never fire on their target's defenses, overnight-0 included (no viewer jets there).

**Short answer:** the main cause is targeting, not air-defense lethality. Both strike jets spend every bomb on the base's air-defense site, with all bombs in flight before the first lands, then fly home empty without firing at the node's defenses. Formation stacking is real but secondary. At FOBs, air defense cannot touch strike jets at all.

## 1. How a strike package travels

- Both jets spawn at one node's exact position (`launch.py:937`); the operation has 2 strike slots (`content/operations.yaml:16`).
- They claim the strike job at spawn (`launch.py:719-720`, `tasking.py:327-333`), and every claimant launches in the same pass when staging ends (`tasking.py:727-729`).
- An aircraft's path is a single waypoint, the target node (`tasking.py:1060-1061`, `_waypoint` at `tasking.py:971-978`). It flies straight at full speed (`step.py:114-115`), 250 m/s (`enemy-strike-fighter.yaml:8`), and orbits a point next to the node on arrival (`step.py:187`, `step.py:234`).
- No spacing exists. The only formation code is the viewer wingman offset for FOLLOW (`follow.py:485`).
- The board refuses a straight route through a known enemy air-defense ring except when the target is that site's own base (`tasking.py:1113-1125`), so a strike flies straight into its target's ring.

## 2. How air defense engages

- Each ready weapon picks one target per tick: highest threat, then nearest, ties by id (`combat.py:140-157`, `_pick` at `combat.py:200`). No tracking or engagement limit; only reload and ammo (`combat.py:290-291`).
- Weapons (`content/weapons.yaml`, all PROPOSED, Q-SIM-65):

| Weapon | Range | Bands | Base Pk | Damage | Reload | Ammo |
|---|---|---|---|---|---|---|
| SAM | 35 km | LOW, MED, HIGH | 0.7 | 70 | 15 s | 8 |
| AAA_GUN | 4 km | NOE, LOW | 0.3 | 15 | 2 s | 400 |
| AG_LIGHT (strike jet main) | 10 km | ground, static, structure | 0.7 | 50 | 10 s | 4 |

- Only the two airbase sites carry the SAM; FOB sites are the short-range variant with the gun only (`rules.py:59-63`, `strait-1.yaml:39-44`). Strike jets fly MED (`enemy-strike-fighter.yaml:12`), so **FOB air defense cannot hit them**.
- Pk = min(0.95, base × track × range factor × evasion) (`combat.py:419-425`); the range factor falls from 1.0 at half range to 0.5 at max (`combat.py:430-435`). Against evasion 0.7 a SAM shot hits 0.245–0.49.
- One SAM hit (100 → 30 hp) is below the 35% mission-kill line and sends the jet home (`combat.py:473`).

## 3. Why "strike fired" almost never happens

- The harness counts a Static shot whose target is a node's defenses (`tools/balance/metrics.py:526-530`).
- A jet fires at a node's defenses only when no valid unit is in range; units come first (`combat.py:14-20`, `151-153`). `combat.strike_structure_first` (`combat.py:143`) would reverse this; it ships false.
- The air-defense site is a STATIC unit with threat 90 (`air-defense-site.yaml:13`), and AG_LIGHT targets STATIC, so it is picked first.
- A bomb at 10 km flies ceil(10000 / (300 × 0.6)) = 56 ticks (`combat.py:292`); reload is 10 s. So each jet fires all 4 bombs before the first lands. COMBAT CB-1: "there is no overkill check" (`docs/specs/COMBAT.md:38`).
- About 4 hits (35 damage after the site's 0.3 armor, hp 150) disable the site; later bombs fizzle on a disabled facility. Facilities are indestructible (`balance/default.yaml:124`, `combat.py:451`) and repair at their base (`rearm.py:26-29`).
- Out of bombs, each jet goes home (`combat.py:337`) without firing at the node's defenses.

So at FOBs the failure is essentially all bomb absorption; at airbases SAM mission-kills come first, then absorption by the site and the radar (threat 50). Expiry is minor (sweep M3).

**Counter gaps:** no per-cause counters; `strike_downed` (`report.py:446`) counts viewer kills only (`combat.py:496-499`); the 47 overnight air-defense kills are not broken down by kind [UNVERIFIED whether any were strike jets].

## 4. Does air defense scale with supply today?

No. `World.defense_hp` only gates capture; stock rebuilds it at 2 hp per unit (`logistics.py:411-414`, `defense.py:79-82`), and it never fires. Site firepower is fixed by the catalog; stock affects it only through ammo restock and repair (`rearm.py:17-29`). No upgrade path exists.

## 5. Options, ranked

| # | Option | Kernel cost | Determinism risk | Spec |
|---|---|---|---|---|
| 1 | Turn on `combat.strike_structure_first` (run S1, #430): bomb the node's defenses before units. Applies to both sides | S, no code | none | COMBAT CB-10, Q-TD-55 |
| 2 | Overkill check: a weapon skips a target whose in-flight shots already cover its remaining hp | M | low (sum over `world.shots`, ordered) | amends COMBAT CB-1, owner (Q-TD-73) |
| 3 | Air defense that grows: site Pk scaled by base stock (and later an upgrade tier), starting low and capped below perfect; plus a per-site cap on missiles guided at once (saturation) | M | low (integers, id order) | COMBAT §5, ECONOMY, new keys; Q-TD-74 |
| 4 | Formation spread and staggered departure: slot k gets a lateral offset (reuse `follow.py:485` maths) and leaves k × a few seconds later | S–M | low (slot index, no RNG) | GAMEPLAY TB-2, THREAT-DIRECTOR §4 |
| 5 | Escort or SEAD for strike packages: an escort or decoy draws SAM fire; mostly content | M | low | THREAT-DIRECTOR §4 catalog |

Routing around coverage is last: the target is the defended base itself.

**Lead plan:** read S1 first. If strike-first opens the funnel, the overkill check is optional; air defense that grows with stock (option 3) is the owner's stated direction either way, sized after S1 and a harness sweep. Formation spread (4) is cheap polish for the airbase SAM duel.
