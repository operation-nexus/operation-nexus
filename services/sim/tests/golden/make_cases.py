"""Writes each golden case's inputs: `case.json` and its `log/` (NX-105; see README.md).

Run from services/sim/tests: `uv run --frozen python -m golden.make_cases`. It rewrites the
inputs only; `expected.json` comes from `NEXUS_UPDATE_GOLDEN=1 uv run --frozen pytest tests/golden`.
"""

import json
import shutil
from pathlib import Path

from runtime.conftest import CAMPAIGN_ID, PROTOCOL
from runtime.test_recovery import POISON_ID, make_join

from nexus.contracts.gen.commands.command import Command
from nexus.runtime.command_log import CommandLogWriter
from nexus.runtime.golden import CASE_FILE, LOG_DIR

HERE = Path(__file__).parent

# Case name -> (ticks, handler registry, description, {tick: correlation ids}, tombstoned ticks).
type Plan = tuple[int, str, str, dict[int, list[str]], tuple[int, ...]]

STUB_TICKS = {t: [f"t{t}-{i}" for i in range(t % 4)] for t in range(5, 301, 5)}
POISON_TICKS = {t: [f"t{t}-a", f"t{t}-b"] for t in range(10, 201, 10)}
POISON_TICKS[120].insert(1, POISON_ID)

CASES: dict[str, Plan] = {
    "empty-1h": (
        36_000,
        "kernel",
        "One game hour, no commands: tick, RNG and state stay stable.",
        {},
        (),
    ),
    "stub-commands": (
        300,
        "stub",
        "JOIN-shaped commands every 5th tick (0-3 per tick) through a stub spawn handler that "
        "draws hp from the spawn stream.",
        STUB_TICKS,
        (),
    ),
    "poison-crash": (
        200,
        "poison",
        "Tick 120 holds a command that raises and is tombstoned: all three of its commands are "
        "dropped as CommandRejected{INTERNAL_ERROR}; the other ticks spawn as usual (SC-8).",
        POISON_TICKS,
        (120,),
    ),
}


def write_case(case_dir: Path, plan: Plan) -> None:
    ticks, handlers, description, commands, tombstoned = plan
    shutil.rmtree(case_dir / LOG_DIR, ignore_errors=True)
    (case_dir / LOG_DIR).mkdir(parents=True)
    case = {
        "campaign_id": CAMPAIGN_ID,
        "seed": 12345,
        "config_hash": "cfg-golden",
        "ticks": ticks,
        "checkpoints_every": 100,
        "handlers": handlers,
        "description": description,
    }
    (case_dir / CASE_FILE).write_text(json.dumps(case, indent=2) + "\n")
    log = CommandLogWriter(
        case_dir / LOG_DIR, campaign_id=CAMPAIGN_ID, protocol_version=PROTOCOL, next_arrival_seq=1
    )
    for tick, ids in sorted(commands.items()):
        batch: list[Command] = []
        for cid in ids:
            seq = log.next_arrival_seq + len(batch)
            batch.append(
                make_join(cid).model_copy(update={"target_tick": tick, "arrival_seq": seq})
            )
        log.append(batch)
        if tick in tombstoned:
            log.append_tombstone(tick)  # as the runtime writes it: after the tick's commands
        log.flush()
    log.close()


if __name__ == "__main__":
    for name, plan in CASES.items():
        write_case(HERE / name, plan)
