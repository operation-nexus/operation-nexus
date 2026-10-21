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
| `joins-strait-1` | 6,000 | Real JOINs on strait-1 with the shipped config: strike, recon and logistics units spawn at the sanctuary, ground units drive road routes and aircraft fly straight; rejects for a unit in sortie, an unknown node, a node no road reaches and an unplayable role (NX-122). Aircraft with no target stay landed at the sanctuary; the strike jet reaches east-airbase on tick 1934 and orbits it, hits bingo fuel on tick 3634 and lands at west-airbase, the nearest coalition airbase, on tick 5101 (NX-368) |

The reserve queue (GP-3) has no case yet: the shipped cap is 500 units, a pause has no logged
command until NX-126 and nothing frees a slot until despawn and combat (NX-324, NX-124), so
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

The orbit uses libm `atan2`, `cos` and `sin`. They are deterministic on one platform but may
differ across platforms or libm versions, so every checkpoint here is pinned to the CI platform
(ADR-0002, SC-3): a mismatch on another machine is not by itself a determinism bug.

Q-SIM-19 cases still to come, each with the item that makes it runnable: the empty *theater* hour
(theater loader NX-120), the 50-viewer scripted raid (real `JOIN` and orders, NX-122; viewer
simulator NX-193), pause and resume mid-combat (combat NX-124, pause NX-126) and campaign end
(NX-126).

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
