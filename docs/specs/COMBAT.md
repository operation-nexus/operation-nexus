# SPEC: Combat

Status: Approved (owner, 2026-10-21, Q-CBT-23) · Owner: — · Tracker: NX-312 (spec), NX-124 (build) · Related ADRs: ADR-0002

> Grilled with the owner on 2026-10-20 (Q-CBT-10 … Q-CBT-22). **Every number here is PROPOSED and unvalidated** (DATA-INTEGRITY DI-7) until the balance harness (NX-031) runs. Per-kind stats (hp, damage, armor, evasion, threat) are content values in `content/units/*.yaml` and `content/weapons.yaml` (CONFIG-AND-CONTENT §7); this spec defines the fields and the rules, never the numbers.

## 1. Purpose
How units find targets, fire, hit, take damage and leave the fight. Combat is deterministic given the seed (SIM-CORE), the same for both sides (GAMEPLAY §0, parity), and driven by simulation factors, never by an LLM. GAMEPLAY §6 and §6a point here.

## 2. Goals / Non-goals
- **Goals:** outcomes that are probabilistic and different every war but replayable from the seed; factors a viewer can read (Pk is shown in the PiP scope, Q-CBT-3); every tunable is content or config, not kernel code.
- **Non-goals (first build):** shots as flying entities, critical hits (Q-CBT-8), friendly fire (Q-CBT-4), jamming, countermeasures, radar lock, weather and night, field repair, CSAR. Each has a return path (§8).

## 3. Requirements
- **CB-1 Targeting.** Each tick, a unit with a ready weapon picks the highest-priority valid target in range. Valid means: it is not a Disabled facility, its side currently tracks the target (never a last-known track or a SIGINT blob, Q-FOW-4), the weapon's `targets:` list includes the target's domain (§5.1), and for an AIR target, the weapon's `bands:` list includes the target's altitude band (§5.3; `bands:` is ignored for other targets). Priority: `threat` (content, descending), then distance (ascending), then entity id (ascending).
- **CB-2 Shots.** A shot is not an entity. Firing spends the round and stores `Shot{id, shooter, target, weapon_id, impact_tick}`; impact lands `ceil(range / projectile_speed / WORLD_DT)` ticks later, guns on the fire tick. Pending shots land in `(impact_tick, id)` order (SIM-CORE §4, Q-GP-7, Q-GP-12).
- **CB-3 Fizzle.** At impact, if the shooter's side no longer tracks the target, or the target is out of the weapon's range or bands, destroyed or despawned, the shot is a miss with no RNG draw (Q-FOW-16).
- **CB-4 Hit roll.** At impact, `Pk = min(combat.pk_cap, base_pk × track × range × evasion × masking)` (§5.2), rolled once on the `combat` stream. Pk is shown in the PiP scope (Q-CBT-3).
- **CB-5 Damage.** A hit removes `damage × (1 − armor)` hp (rounded down, minimum 1; Q-CBT-22). Damage is fixed: the only randomness is the hit roll and the crew-survival roll (Q-GP-8).
- **CB-5a Assists (Q-SIM-66).** `UnitDestroyed.assist_ids` lists every other distinct shooter that landed a hit on the unit within `combat.assist_window_s` (120 s of game time, PROPOSED) before the kill, sorted by id, excluding the killer (the shooter of the killing hit); at most 32. The recent hits are world state.
- **CB-6 Damage state.** `damage_state` derives from the hp fraction: Damaged below `combat.damage_state.damaged_below`, Mission-kill below `mission_kill_below`, Disabled below `disabled_below`, Destroyed at 0 (Q-CBT-1, Q-GP-8). A state only gets worse through combat and better only by repair at a friendly base (GAMEPLAY §5).
- **CB-7 Wrecks.** An aircraft that is airborne (any state but LANDED) when it reaches Disabled is destroyed at once, with the shooter as killer (Q-SIM-66; the crew roll is CB-8). Any other Disabled unit (not a facility, CB-9; including a LANDED aircraft) can't move and is a wreck: it can still be targeted until Destroyed, and it is removed after `combat.disabled_timeout_s` (game time) whoever owns it, emitting `UnitDespawned{reason: WRECKED}`. There is no field repair in the first build (Q-CBT-14). Its commander can `!join` again once it is gone, after the GP-2 respawn delay.
- **CB-8 Crew.** Once per unit, at the first of Disabled or Destroyed (Q-CBT-22), a seeded crew-survival roll (`combat.crew_survival.*`) decides DOWNED or LOST for units with `crew > 0`; a surviving crew gets a downed-crew marker (GAMEPLAY §6a). Facilities have `crew: 0`.
- **CB-9 Facilities.** A facility's hp floors at the Disabled threshold; it is never Destroyed (Q-GP-37) and repairs from its base's stock (GAMEPLAY §5b). A Disabled facility does nothing until repaired: it does not fire, is not a valid target (CB-1), and senses, emits and listens for no one (FOG-OF-WAR FOW-11).
- **CB-10 Node defenses.** A weapon whose `targets:` includes `STRUCTURE` can fire on a node's defense HP and on bridges, with the same hit and damage rules (structures have armor 0 and evasion 1.0; Q-CBT-22). Node defense HP gates capture (GAMEPLAY §8).
- **CB-11 Munitions and stance.** Loads are per sortie from base stock, guns included (Q-CBT-7). Stance drives auto-RTB (§5.6). Unlimited ammo and friendly fire are campaign options set at setup by the owner or an Admin only, never a GM (Q-ALN-10).
- **CB-12 Parity.** Both sides use these rules and the same content fields.

**In code now (NX-124 part 1, `nexus.core.combat`; SIM-CORE §4 Combat):** CB-1 to CB-7 and CB-9, with these readings where the text leaves room.
- **Clock.** Pending shots, reloads and wreck timers are on the campaign clock (running ticks), so a pause freezes them (SC-11). `WeaponFired.impact_tick` is therefore a campaign-clock tick, not a `Tick`, like `ObjectiveAnnounced.deadline_tick`.
- **CB-1.** Targets come from the shooter's side's tracked contacts only; range, domain and band use the real positions. A Disabled entity does not fire. Each ready weapon, in the unit's catalog order, picks independently; there is no overkill check. A Disabled facility is never picked, and a shot in flight at one fizzles.
- **CB-2.** The flight time is `ceil(distance at the fire tick / (projectile_speed x WORLD_DT))` ticks, not the weapon's maximum range; a gun lands on the fire tick (after the new shots, SC-13). A reload is `ceil(reload_s / WORLD_DT)` ticks.
- **CB-1 search.** Targeting is a grid search (per side and threat level, then by domain and band; growing radii), exactly equal to a scan-and-sort of every tracked contact: a differential test checks targets, events and RNG draws, including ranges hit to the float. The combat slot costs about 3 ms a tick at 1,000 units spread over 200 km (before: 35 ms).
- **CB-3.** A shot also fizzles when its shooter is gone (destroyed or removed) before it lands: with no shooter there is no envelope to test and no distance for the range factor. A shot already in flight still lands after its shooter becomes Disabled; only a gone shooter fizzles it.
- **CB-4.** One draw `rng.random() < Pk` on the `combat` stream per non-fizzled impact. Masking applies to NOE and LOW aircraft and to ground units in any theater masking region.
- **CB-5, CB-6.** `armor` is an exact decimal, so `floor(damage x (1 - armor))` has no float error; thresholds are whole hp, `hp < ceil(fraction x max hp)`. One `UnitDamageStateChanged` per hit that changes the state, none for the hit that destroys.
- **CB-7.** A Disabled non-facility unit stops (path cleared) and is removed `combat.disabled_timeout_s` later; an airborne aircraft that reaches Disabled is destroyed at once (that hit emits `UnitDestroyed` alone, no `UnitDamageStateChanged`), a LANDED one is a ground wreck (Q-SIM-66). Disabled units do not contest a capture and count for the garrison multiplier (Q-ALN-33); a wreck cannot escape a flipped base; a Disabled truck keeps its cargo, unloads nothing and loses it with the wreck.
- **CB-9.** The floor is the highest hp still Disabled (`ceil(disabled_below x hp) - 1`, at least 1).
- **CB-5a.** `Entity.hits` holds `[shooter, running tick]` per hit, pruned to the window on each new hit; a hit exactly `assist_window_ticks` before the kill still counts. Facilities keep none.
- **Restore.** `restore` checks a snapshot's combat state against the campaign rules (`nexus.core.combat.validate`): hp within the kind's maximum, `damage_state` and `alt_band` consistent, ammo and reload lists fitting the loadout (variant included), wreck timers only on Disabled non-facilities, and pending shots naming known weapons their shooter carries; `load` stays rules-free.
- **Not yet:** the crew roll and ammo restock (part 2), STRUCTURE targets and node defense HP (part 3).

## 4. Interfaces
- **Events:** `WeaponFired`, `WeaponImpact{hit}` (CONTRACTS §4); `UnitDamageStateChanged`, `MunitionsDepleted`, `CrewDowned`, `UnitRepaired` (CONTRACTS pending additions); `UnitDestroyed{killer?, assists[]}`; `UnitDespawned{reason: WRECKED}` (new reason, CB-7).
- **RNG:** the `combat` stream only (SIM-CORE).
- **Content (CONFIG-AND-CONTENT §7.1, §7.2):** unit `alt_bands`, `default_alt_band`, `hp`, `armor`, `evasion`, `crew`, `threat`; weapon `targets`, `bands`, `range_m`, `projectile_speed_mps`, `base_pk`, `damage`, `reload_s`, `ammo`.
- **Config (CONFIG-AND-CONTENT §6.4):** `combat.pk_cap`, `combat.track_quality.*`, `combat.range.full_pk_frac`, `combat.range.min_mult`, `combat.pk_mult.terrain_masked`, `combat.damage_state.*`, `combat.disabled_timeout_s`, `combat.assist_window_s`, `combat.crew_survival.*`.

## 5. Behavior

### 5.1 Who can shoot whom
A weapon's `targets:` list names domains (`AIR`, `GROUND`, `SEA`, `STATIC`) plus `STRUCTURE` (node defenses and bridges, CB-10). The content is the source of truth; the table below is derived from CONFIG-AND-CONTENT §7.3 for the MVP kinds and is checked against the content (`content/units/*.yaml`, `content/weapons.yaml`) by `tests/runtime/test_units.py` (Q-CBT-15). A disagreement fails the test; fix the content or this table, never both silently.

| Kind | AIR | GROUND | STATIC | STRUCTURE | Source |
|---|---|---|---|---|---|
| STRIKE_FIGHTER, ENEMY_STRIKE_FIGHTER | light | yes | yes | yes | §7.3 "AG + AA light"; STRUCTURE: GAMEPLAY §8 (air strikes reduce defense HP) |
| ENEMY_FIGHTER | yes | — | — | — | §7.3 "AA" |
| ENEMY_ARMOR | — | yes | yes | yes | §7.3 "AG"; STRUCTURE: GAMEPLAY §8 (ground fire reduces defense HP) |
| GARRISON_INFANTRY | — | yes | — | — | §7.3 "light"; GROUND only, a pure defender (owner, Q-CBT-25; the unit loader enforces it, NX-367). Anti-air and anti-facility infantry variants come later as new catalog entries, for garrisons and for operators (GAMEPLAY-LATER) |
| AIR_DEFENSE_SITE (AAA, SAM variants) | yes | — | — | — | §7.3 engagement ring |
| RECON_UAV, ENEMY_RECON_UAV, LOGI_TRUCK, ENEMY_CONVOY, RADAR_SITE | unarmed | | | | §7.3 |

"light" means a weapon with that target is carried but is not the kind's main role. SEA arrives with naval units (P3).

### 5.2 Hit probability (first build)
`Pk = min(combat.pk_cap, base_pk × track × range × evasion × masking)`

| Factor | Value | Key / field |
|---|---|---|
| Track quality | tracked 1.0; painted by recon 1.25 | `combat.track_quality.track`, `.painted` |
| Range | 1.0 up to `full_pk_frac` (0.5) of `range_m`, then linear down to `min_mult` (0.5) at `range_m`; no fire beyond `range_m` | `combat.range.full_pk_frac`, `combat.range.min_mult` |
| Evasion | per target kind, 0.6–1.0 (fighters about 0.7; UAVs, trucks, infantry 1.0; facilities always 1.0) | unit `evasion` |
| Terrain masking | 0.5 when the target is NOE, LOW or a ground unit inside a theater `masking_regions` area (Q-FOW-3); otherwise 1.0 | `combat.pk_mult.terrain_masked` |
| Cap | 0.95: every shot can miss | `combat.pk_cap` |

Factors not built yet are a multiplier of 1.0, registered as fallback FB-6 (DATA-INTEGRITY): radar lock, jamming, countermeasures, weather and night. Each returns with the unit or phase that produces it (§8).

In code now (NX-124): every factor but the unbuilt ones (FB-6); `track` is `combat.track_quality.painted` when the shooter's contact is painted. Worked example (numbers illustrative only): a weapon with `base_pk` 0.8 and `range_m` 20 km fires at a tracked, unpainted fighter (`evasion` 0.7) at 15 km over open ground. Range factor: 15 km is 75% of range, halfway between 50% and 100%, so 0.75. `Pk = 0.8 × 1.0 × 0.75 × 0.7 × 1.0 = 0.42`.

### 5.3 Altitude bands
Four bands: `NOE`, `LOW`, `MED`, `HIGH` (CONTRACTS `AltBand`; in code since NX-124: `Entity.alt_band`, the kind's default, set on spawn; aircraft sensor masking by band is not built). Each air kind lists the bands it may fly in (`alt_bands`) and its default (`default_alt_band`); for example an AWACS flies HIGH, a recon UAV LOW or MED. A unit flies at its default band; no first-build command changes band. A weapon's `bands:` list is its altitude reach (a gun AAA reaches NOE and LOW; a long-range SAM reaches all four). Ground units can be masked (§5.2); STATIC targets are never masked (Q-FOW-3 names only NOE/LOW aircraft and ground units). Adding a band is a contract and content change, not kernel code.

### 5.3a Air defense, SEAD and jamming
An air-defense site is an ordinary unit whose weapon envelope (`range_m`, `bands:`) is its ring (Q-CBT-18). Anti-radiation (SEAD) missiles that home on emitting radars, radars going dark ("blinking") to avoid them, and jammers that lower enemy Pk in a corridor all arrive with the specialist chassis in P4 (NX-212). Until then `homes_on_emitters` in content has no effect and jamming is the FB-6 1.0.

### 5.4 Damage and armor
`armor` is a fraction from 0 to 0.9 per kind (one value, no facings). A hit's damage is `damage × (1 − armor)`, so a light weapon is weak against armor without being useless. Thresholds are hp fractions, so armor and hp together set how many hits each state takes.

### 5.5 Wreck timeline
Disabled → wreck → removed after `combat.disabled_timeout_s` (600 s game time, PROPOSED) → slot frees → respawn delay (GP-2) → `!join`. A wreck at a base that flips is destroyed with a crew roll (STATE-MACHINES §4.1). In code now (NX-124 part 1): the removal, the `WRECKED` event and the respawn delay; the flip-time destruction is `UnitDestroyed{killer: null}` without the crew roll (part 2).

### 5.6 Stance and auto-RTB
`standard` RTBs at Mission-kill if still mobile; `cautious` at Damaged; `press` never; `guns` keeps fighting with guns after missiles and bombs run out. Out of missiles and bombs → RTB unless `press` or `guns` (Q-CBT-6, Q-CBT-7). The first build runs every unit as `standard`; `!stance` is in GAMEPLAY-LATER §3.

### 5.7 Changing a weapon or a combat factor
- **New or changed weapon or unit:** use the `new-unit` skill. It covers the combat fields, the §5.1 table and the balance-diff report.
- **New Pk factor or a built-but-1.0 factor:** a spec change here (§5.2 row), its config key in CONFIG-AND-CONTENT §6.4, removal of its FB-6 entry, a determinism test, and a PLAYTEST-WATCHLIST row.
- **New band or target class:** a contract change (`AltBand`, weapon `targets`), the §5.1 or §5.3 text, and content updates in one PR.
- Any balance change attaches the balance-diff report (CONFIG-AND-CONTENT §11.4).

## 6. Failure modes
- **Pk outside [0, cap]:** validator rejects content with `base_pk` outside 0..1, `armor` outside 0..0.9 or `evasion` outside 0.6..1.0; the kernel clamps to the cap.
- **Content and §5.1 disagree:** the matrix test fails CI.
- **A wreck blocks its commander for the timeout:** intended; the timeout is on the watch list.

## 7. Test plan
| Req | Test |
|---|---|
| CB-1 | Property: a chosen target is always tracked, domain- and band-compatible; ties break by id |
| CB-2, CB-3 | Unit: impact tick math; fizzle draws no RNG (stream position unchanged) |
| CB-4 | Property: 0 ≤ Pk ≤ cap; range factor is 1.0 at ≤ 50% and `min_mult` at 100%; golden worked example (§5.2) |
| CB-5, CB-6 | Unit: damage formula, minimum 1; state thresholds |
| CB-7 | Unit: wreck removed at the timeout with `WRECKED`; no field repair transition exists |
| CB-9 | Property: facility hp never below the Disabled floor |
| CB-10 | Unit: only `STRUCTURE` weapons damage node defense HP |
| CB-12 | Same scenario mirrored across sides gives mirrored outcomes |
| all | Determinism: same seed and commands → same events and hash (SIM-CORE) |

## 8. Open questions and deferred items
- **Q-CBT-17 (parked until the P1 balance runs):** dynamic threat modifiers (engaging a friendly, emitting, painted).
- Deferred items and their return paths are in GAMEPLAY-LATER "Deferred from the first build".
- Dynamic track quality in flight: GAMEPLAY-LATER "Future candidates".
