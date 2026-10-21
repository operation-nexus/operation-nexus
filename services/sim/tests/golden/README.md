# Golden replays (NX-105)

SIM-CORE SC-3, §5 and §7; TESTING-STRATEGY §3.2. Each directory here is one case:

| File | What |
|---|---|
| `case.json` | `campaign_id`, `seed`, `config_hash`, `ticks`, `checkpoints_every` (100, SIM-CORE §5), `handlers` (the name of a handler registry), `description` |
| `log/` | The command log in the NX-103 format (DATA-MODEL §6.2), read with `CommandLogReader` |
| `expected.json` | `state_hash` at every checkpoint tick, plus the count and blake2b-256 hash of the event stream (one canonical JSON line per event) |

`nexus.runtime.golden.run_golden` builds the world from the seed, steps every tick from 1 to `ticks`
and drops the commands of a tombstoned tick (SC-8). `test_golden.py` compares the result with
`expected.json` by exact string equality. `tools/sim-determinism/check.py` runs every case again in
four interpreters with different `PYTHONHASHSEED` values (CI job `sim-determinism`).

Until the kernel has handlers (`nexus.core.step.HANDLERS` is empty), the cases use the stub
registries in `test_golden.py`: `stub` spawns a unit with hp drawn from the `spawn` stream, `poison`
does the same but raises on the command with correlation id `poison`. These are test stand-ins, not
gameplay.

| Case | Ticks | What it pins |
|---|---|---|
| `empty-1h` | 36,000 | One game hour, no commands: tick, RNG and state stay stable (Q-SIM-19 "empty theater 1 h", without a theater yet) |
| `stub-commands` | 300 | JOIN-shaped commands through the `stub` handler |
| `poison-crash` | 200 | A tombstoned tick whose three commands are dropped (Q-SIM-19 "poison-command crash") |

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
