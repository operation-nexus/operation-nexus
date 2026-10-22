# Golden replays (NX-105)

SIM-CORE SC-3, §5 and §7; TESTING-STRATEGY §3.2. Each directory here is one case:

| File | What |
|---|---|
| `case.json` | `campaign_id`, `seed`, `config_hash`, `ticks`, `checkpoints_every` (100, SIM-CORE §5), `handlers` (the name of a handler registry), `description`, and optionally `rules: "shipped"` |
| `log/` | The command log in the NX-103 format (DATA-MODEL §6.2), read with `CommandLogReader` |
| `expected.json` | `state_hash` at every checkpoint tick, plus the count and blake2b-256 hash of the event stream (one canonical JSON line per event) |

`nexus.runtime.golden.run_golden` builds the world from the seed, steps every tick from 1 to `ticks`
and drops the commands of a tombstoned tick (SC-8). `test_golden.py` compares the result with
`expected.json` by exact string equality. `tools/sim-determinism/check.py` runs every case again in
four interpreters with different `PYTHONHASHSEED` values (CI job `sim-determinism`).

The `kernel` registry is the real `nexus.core.handlers.HANDLERS`. The older cases use the stub
registries in `test_golden.py`: `stub` spawns a unit with hp drawn from the `spawn` stream, `poison`
does the same but raises on the command with correlation id `poison`. These are test stand-ins, not
gameplay.

A case with `"rules": "shipped"` starts from `start_campaign` with the shipped config
(`load_campaign_config`: balance, unit catalog, strait-1), so its world holds strait-1's nine
facilities (ids 1-9) from tick 0, and its `config_hash` must equal that config's, so any config change fails
the case with a clear error until `make_cases.py` and `expected.json` are regenerated (a golden
update, below). Cases without it start from an empty world with no rules.

| Case | Ticks | What it pins |
|---|---|---|
| `empty-1h` | 36,000 | One game hour, no commands: tick, RNG and state stay stable (Q-SIM-19 "empty theater 1 h", without a theater yet) |
| `stub-commands` | 300 | JOIN-shaped commands through the `stub` handler |
| `poison-crash` | 200 | A tombstoned tick whose three commands are dropped (Q-SIM-19 "poison-command crash") |
| `joins-strait-1` | 6,000 | Real JOINs on strait-1 with the shipped config: strike, recon and logistics units spawn at the sanctuary, ground units drive road routes and aircraft fly straight; rejects for a unit in sortie, an unknown node, a node no road reaches and an unplayable role (NX-122). Aircraft with no target stay landed at the sanctuary; the strike jet (forward-deployed at west-airbase, NX-123 part 2) flies toward east-airbase and is shot down there by the enemy SAM site on tick 1386, before the tick-1467 arrival (NX-124 part 1, see the format 14 note; before combat it orbited east-airbase, hit bingo on tick 3644 and refuelled at west-airbase by tick 5157, NX-368) |
| `capture-strait-1` | 17,000 | One LOGI JOIN to the neutral `cross-n`: a capture run from the sanctuary of about 16,000 ticks, then `CaptureStarted` (tick 16008) and `NodeCaptured` NEUTRAL to COALITION with the JOINing commander (tick 16179): the truck alone fills the bar at 581,502 millionths of a percent a tick (weight 0.5, quiet 0.608, about 103.2 s; NX-125) |

The reserve queue (GP-3) has no case yet: the shipped cap is 500 units, nothing frees a slot until despawn and combat (NX-324, NX-124), so
`tests/core/test_reserve_queue.py` covers it with a test-only cap. Snapshot format 4 (NX-122:
the reserve queue in world state) re-pinned every case's `state_hash` checkpoints; no event
stream changed. Snapshot format 5 (NX-368: aircraft `state`, `fuel` and `orbit`, new catalog and
balance keys so a new `config_hash`) re-pinned every case's checkpoints again and the
`joins-strait-1` `config_hash`; no event stream changed, as takeoff, orbit, bingo and landing
emit no events (STATE-MACHINES §4.1 lists none) and no golden aircraft runs out of fuel (the
only new event, `UnitDestroyed`). The `stub` and `poison` registries now spawn their fighters
`LANDED` with fuel, since an AIR entity must have a state; they never take off.

Snapshot format 6 (NX-370: the per-commander `callsigns` map) re-pinned every case's checkpoints again; no event stream changed and no case sends `SYS_SET_CALLSIGN` yet.

Snapshot format 7 (NX-150: each side's FoW `contacts`) re-pinned every case's checkpoints again, and the new catalog (`sensor`, `stealth`) and balance (`fow`) keys gave `joins-strait-1` a new `config_hash`; no event stream changed (sensing emits no events). No case has enemy units yet, so every case's contacts stay empty: `tests/core/test_fog.py` covers sensing, including a cross-process hash check at 1,000 entities.

Snapshot format 8 (NX-150 part 2: facility `base_id`, `variant` and `emitting`, each side's
discovered facility `markers`) re-pinned every case's checkpoints again. The new catalog key
(`sensor.passive_range_m`) gave `joins-strait-1` a new `config_hash`, and its world now starts with
strait-1's facilities, so its JOINed units get ids from 10 instead of 1: the `UnitSpawned` events
carry the new ids, which changed its `events_hash` (still 10 events). In that run the enemy's
east-airbase radar tracks the strike jet from tick 1135, the jet's own radar tracks east-airbase's
radar and SAM site from tick 1670 and the coalition keeps their markers (last confirmed on tick
3895, as the jet flies home after bingo), and the enemy tracks the recon UAV from tick 5310. Masking and
passive discovery have no golden case yet: `tests/core/test_fog.py` covers them.

Snapshot format 9 (NX-150 part 2b: each contact's `painted` flag, each side's SIGINT `blobs` and
`sigint_age`) re-pinned every case's checkpoints again, and the new balance keys (`fow.sigint_*`,
including the size thresholds, and `fow.paint_range_m`) gave `joins-strait-1` a new `config_hash`; no event stream changed (sensing
emits no events). In that run the enemy holds one or two S blobs on most SIGINT refreshes (every
90 ticks) from tick 810 to tick 5220: moving coalition units within 180 km of its radar but outside
its sensors. The coalition has none, as no enemy unit moves, and nothing is painted, as no recon
UAV comes within paint range of an enemy. `tests/core/test_fog_sigint.py` covers blobs and
painting, including a cross-process hash check at 1,000 entities.

Snapshot format 10 (NX-123 part 1: node `stock`, a carrier's `cargo`, `unload_milli` and `delivered`) re-pinned every
case's checkpoints again. The new `logistics` balance keys and strait-1's `static-rear` node, road, spawn and
`enemy_rear_source` gave `joins-strait-1` a new `config_hash`. In that case the truck to `fob-n-w` now spawns at
`west-airbase` (its source) and loads 100 (stock 1000 to 900), so that `UnitSpawned` carries a new `node_id` and
`events_hash` changed; the same truck also finishes unloading there, so the stream gains one
`SupplyDelivered` (11 events); the truck to the enemy `static-hq` is a capture run from `haven` with no
cargo. `empty-1h`, `stub-commands` and `poison-crash` hold no stock (no `rules`), so only the format changed
their checkpoints.

Snapshot format 11 (NX-123 part 2: an aircraft's `rearm_milli`, `rearm_spent` and `stalled`) re-pinned every
case's checkpoints again. The new `logistics` balance keys (`loadout_cost`, `rearm_rate`,
`forward_deploy_min_surplus`, `starved_loadout`) gave `joins-strait-1` a new `config_hash`. In that case the
two JOINs that name a node and pass the surplus test forward-deploy: the strike jet to `east-airbase` and the
recon UAV to `fob-s-e` spawn at `west-airbase` instead of `haven` and each pay their `loadout_cost` (20 on tick
1, 5 on tick 10, two `SupplyConsumed{SPAWN}`); the jet therefore reaches east-airbase on tick 1467, not 1934,
and hits bingo on tick 3644, not 3634. When it lands at west-airbase on tick 5101 it refuels to full, which
ends on tick 5157 with one `SupplyConsumed{REARM}` of 17 units: 14 events in all, up from 11. The
`hold` and no-target JOINs still spawn at `haven`, free. `empty-1h`, `stub-commands` and `poison-crash` hold
no stock, so only the format changed their checkpoints.

Snapshot format 12 (NX-125: each node's live `owner` and its `capture` bar) re-pinned every case's checkpoints
again. The new `capture` balance block gave `joins-strait-1` a new `config_hash`; its event stream did not change
(14 events, same `events_hash`), as no unit of that run reaches a node it can capture. `empty-1h`,
`stub-commands` and `poison-crash` hold no nodes, so only the format changed their checkpoints. The new
`capture-strait-1` case pins the first capture. Events are now hashed with their contract keys
(`model_dump(by_alias=True)`, so `NodeCaptured.from`); no earlier event has an alias, so no earlier hash moved.

The orbit uses libm `atan2`, `cos` and `sin`. They are deterministic on one platform but may
differ across platforms or libm versions, so every checkpoint here is pinned to the CI platform
(ADR-0002, SC-3): a mismatch on another machine is not by itself a determinism bug.

Snapshot format 13 (NX-126: the campaign clock `running_ticks`, `pause_reason`, `ended`, the hold run, the held-node sums, the objective counts and the active objective) re-pinned every case's checkpoints again, and the new `campaign` balance block gave `joins-strait-1` and `capture-strait-1` a new `config_hash` (the score keys `average_weight` and `final_weight`, Q-SIM-64, are part of it). The two `rules: "shipped"` cases now have the campaign layer on: `joins-strait-1` gains one event (15), `ObjectiveAnnounced` on tick 1 (a hold on `fob-s-w`, deadline 9001); `capture-strait-1` gains three (6): that announcement, then on tick 9001 `ObjectiveResolved` (the hold on `fob-s-w` COMPLETED: nobody takes it from the coalition and no unit is needed to hold it, Q-SIM-61, so no participants) and `ObjectiveAnnounced` for `east-airbase` (a capture, deadline 18001; the truck's `cross-n` capture on tick 16179 is not that node). Every later event's `event_seq` moved up with them. `empty-1h`, `stub-commands` and `poison-crash` have no rules, so only the format changed their checkpoints. No case sends a staff command yet (the `kernel` cases are built from JOINs only): `tests/core/test_campaign.py` covers pause, resume, end and the time limit.

Snapshot format 14 (NX-124 part 1: every entity's real `hp`, `damage_state`, `alt_band`, per-weapon `ammo` and `reload`, `wreck_left`, and the pending `shots` with their id counter) re-pinned every case's checkpoints again, and the new `combat` balance block plus the combat stats in the unit catalog and weapon numbers gave `joins-strait-1` and `capture-strait-1` a new `config_hash`. `empty-1h`, `stub-commands` and `poison-crash` have no rules, so only the format changed their checkpoints. `capture-strait-1` has one unarmed truck, so its event stream is unchanged (6 events). `joins-strait-1` is now also the combat case, and its event stream grew from 15 to 30 events: the strike jet that flew to east-airbase is fired on by the enemy SAM site there (`WeaponFired` from tick 1234, a missile in flight about 60 ticks), takes a first hit on tick 1349 (HEALTHY to MISSION_KILL, `UnitDamageStateChanged`) and is shot down on tick 1386 (`UnitDestroyed{killer_id}`, the site is entity 6), so the orbit at east-airbase, the bingo landing and the refuel described above no longer happen in this case; `tests/core/test_air.py` and `test_forward_deploy_refuel.py` cover them. The per-target recent-hit list (assists, Q-SIM-66) joined the entity encoding in the same format 14, so its checkpoints were re-pinned once more and the new `combat.assist_window_s` key gave both `rules: "shipped"` cases another new `config_hash`; no event changed (the kill has one shooter, so no assists). Unlike the older cases, the fight depends on the catalog's combat numbers, so a balance change re-pins this case.

Snapshot format 15 (NX-124 part 2: the rearm-stop carries `ammo_credit`, `repair_milli`, `repair_debt` and the downed-crew markers) re-pinned every case's checkpoints again, and the new balance keys (repair rates, crew survival, marker time, damaged multipliers) gave both `rules: "shipped"` cases a new `config_hash`. `capture-strait-1` has one unarmed truck, so its events are unchanged. `joins-strait-1` goes from 30 to 37 events: once the strike jet is hit to Mission-kill (tick 1349) it turns back (auto-RTB) at 0.75 speed, so it lives until tick 1420 instead of 1386 and the SAM site fires more missiles; the site now refills from east-airbase after each missile (facility restock, Q-SIM-69), so five `SupplyConsumed{REARM}` of 1 unit join the stream and no `MunitionsDepleted` is needed; the jet's crew roll (one `combat` draw) is LOST, so no `CrewDowned`. The new `logistics.facility_rearm_cost` key is part of the `config_hash`. `empty-1h`, `stub-commands` and `poison-crash` changed only by the format.

Snapshot format 16 (NX-124 part 3: node defense hp, its drain carry and down flags, the defeat run, shots at nodes, `Entity.defended` and the facility markers' `ring_m` and `state`, all in the hash) re-pinned every case's checkpoints again. The new balance keys (`capture.defense_hp`, `capture.sanctuary_repair_hp_per_s`, `logistics.starve_hp_drain_per_min`, `logistics.defense_repair_hp_per_stock`, `campaign.defeat`) moved `config_hash`, so `capture-strait-1` and `joins-strait-1` got new `case.json` hashes. Only `joins-strait-1`'s `events_hash` moved, because `WeaponFired` and `WeaponImpact` now carry `target_node_id`; no event count changed.

Snapshot format 17 (NX-374: both Tasking Boards, their job counter, the lost-node and scout-cooldown maps, the blob runs, `Entity.order`, `Entity.job_id` and `Entity.pickup`) re-pinned every case's checkpoints again. The new required `tasking` balance block moved `config_hash`, so `capture-strait-1` and `joins-strait-1` got new `case.json` hashes. `empty-1h`, `stub-commands` and `poison-crash` have no rules (no board), so only the format changed them. The two `rules: "shipped"` cases gain job events, because the board runs every 50 running ticks, and every later `event_seq` moved: `capture-strait-1` goes from 6 to 9 events and `joins-strait-1` from 37 to 54. The Static's board posts nothing (it has no recon or truck to staff a scout or resupply job, and a scout needs a blob to stay in its cell for two SIGINT refreshes), and neither board posts an assist-objective job, because only a non-carrier ground unit fits it and no golden unit is one (trucks only haul). `capture-strait-1`: the second objective (`east-airbase`) posts a strike job on tick 9050 that nobody can fly; the truck's capture run keeps its order until `cross-n` flips (tick 16179); the newly owned base is starved at stock 0, so a resupply job is posted for it on tick 16200 and the empty truck claims it (it reloads at a source first). `joins-strait-1`: the strike jet that JOINed with no target on tick 10 had no job and waited at the sanctuary, and claims the strike job posted on tick 1250 once an enemy facility is discovered (a marker, urgency 1.9), flies to `east-airbase` (the site's own base, so the route-danger rule exempts it) and is shot down, which releases its claim on tick 3045, the tick it is removed; another strike job (`fob-s-e`) is posted on tick 4350 and nobody can take it. Flights, shots and deliveries that existed before did not change.

Snapshot format 18 (NX-374 part 2: `Entity.follow_id` and `fired_by`, `Job.entity`) re-pinned every case's checkpoints again. The new `tasking` keys (`follow_station_m`, `escort_threat_memory_s`, `escort_leash_m`, the `escort_convoy` priority and slots) moved `config_hash`, so `capture-strait-1` and `joins-strait-1` got new `case.json` hashes. `JobCreated` gained `entity_id`, so `capture-strait-1`'s event hash changed with the same count. `joins-strait-1` gains two events: at tick 1250 the board posts an `ESCORT_CONVOY` job for the logistics truck driving toward the Static's discovered site, and at tick 6000 the recon unit claims it (54 to 56 events); no other outcome changed.

Q-SIM-19 cases still to come, each with the item that makes it runnable: the empty *theater* hour
(theater loader NX-120), the 50-viewer scripted raid (real `JOIN` and orders, NX-122; viewer
simulator NX-193), pause and resume mid-combat (combat NX-124) and campaign end (needs staff
commands in `make_cases.py`, which builds JOINs only).

## Adding or changing a case

The inputs are written by `make_cases.py`, never by hand (the log is zstd):

```
cd services/sim/tests && uv run --frozen python -m golden.make_cases
cd services/sim && NEXUS_UPDATE_GOLDEN=1 uv run --frozen pytest tests/golden
```

The second command rewrites every `expected.json` with what the code produces now.

## Update policy

A changed `expected.json` means the simulation's outcomes changed. It is allowed only for an
intentional rule change, in the same PR as that change, with the `golden-update` label and a PR
note saying why the outcomes changed (TESTING-STRATEGY §3.2). A refactor that needs a golden update
is a bug.

The hashes are pinned to the CI image and its exact Python (3.12, `services/sim/.python-version`)
and dependency pins (`uv.lock`); a different platform may differ (SC-3). They hold only for this
commit's code: re-simulating an old log on new code is not promised (SC-16).
