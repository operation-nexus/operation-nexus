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
from nexus.contracts.gen.commands.join import JoinCommand
from nexus.runtime.campaign_config import load_campaign_config
from nexus.runtime.command_log import CommandLogWriter
from nexus.runtime.golden import CASE_FILE, LOG_DIR

HERE = Path(__file__).parent

# Case name -> (ticks, handler registry, description, {tick: commands}, tombstoned ticks, whether
# it runs with the shipped config's rules). Each command's target_tick and arrival_seq are stamped
# by `write_case`, in list order.
type Plan = tuple[int, str, str, dict[int, list[JoinCommand]], tuple[int, ...], bool]


def joins(ticks: dict[int, list[str]]) -> dict[int, list[JoinCommand]]:
    return {t: [make_join(cid) for cid in ids] for t, ids in ticks.items()}


def join(n: int, role: str, node: str | None = None, *, hold: bool = False) -> JoinCommand:
    """A JOIN from commander number `n` to `node` (None: no target)."""
    return JoinCommand.model_validate(
        {
            "kind": "JOIN",
            "source": "CHAT",
            "issuer": {"commander_id": f"0192f0c1-7a2b-7c3d-8e4f-{n:012d}"},
            "target_tick": 1,
            "arrival_seq": 1,
            "correlation_id": f"c{n}-{role.lower()}",
            "role": role,
            "target": None if node is None else {"node_id": node},
            "hold": hold,
        }
    )


STUB_TICKS = joins({t: [f"t{t}-{i}" for i in range(t % 4)] for t in range(5, 301, 5)})
POISON_IDS = {t: [f"t{t}-a", f"t{t}-b"] for t in range(10, 201, 10)}
POISON_IDS[120].insert(1, POISON_ID)
# strait-1: haven (sanctuary) - west-airbase - fob-n-w - (bridge-n) - cross-n - ... - static-hq.
STRAIT_JOINS = {
    1: [
        join(1, "STRIKE", "east-airbase"),  # AIR, straight there
        join(2, "LOGI", "fob-n-w"),  # GROUND, haven -> west-airbase -> fob-n-w
        join(3, "RECON", hold=True),  # Holding, no path
        join(1, "LOGI", "fob-s-w"),  # UNIT_IN_SORTIE: commander 1 has a unit
    ],
    5: [
        join(4, "LOGI", "bridge-n"),  # NODE_INVALID_FOR_UNIT: no road reaches a bridge node
        join(5, "STRIKE", "nowhere"),  # NODE_UNKNOWN
        join(6, "NAVY"),  # ROLE_UNKNOWN until P3
    ],
    10: [
        join(4, "LOGI", "static-hq"),  # GROUND across the north bridge
        join(5, "RECON", "fob-s-e"),  # AIR
        join(6, "STRIKE"),  # no target: Holding until auto-tasking (NX-155)
    ],
}

CASES: dict[str, Plan] = {
    "empty-1h": (
        36_000,
        "kernel",
        "One game hour, no commands: tick, RNG and state stay stable.",
        {},
        (),
        False,
    ),
    "stub-commands": (
        300,
        "stub",
        "JOIN-shaped commands every 5th tick (0-3 per tick) through a stub spawn handler that "
        "draws hp from the spawn stream.",
        STUB_TICKS,
        (),
        False,
    ),
    "poison-crash": (
        200,
        "poison",
        "Tick 120 holds a command that raises and is tombstoned: all three of its commands are "
        "dropped as CommandRejected{INTERNAL_ERROR}; the other ticks spawn as usual (SC-8).",
        joins(POISON_IDS),
        (120,),
        False,
    ),
    "joins-strait-1": (
        6_000,
        "kernel",
        "Real JOINs on strait-1 with the shipped config: units with a node target forward-deploy "
        "at west-airbase (paying their loadout) and move along their routes for 10 game minutes; "
        "trucks and units with no target spawn at the sanctuary; rejects for a unit in sortie, "
        "an unknown node, a node no road reaches and an unplayable role (NX-122). Aircraft "
        "without a target stay landed; the strike jet orbits east-airbase, then RTBs at bingo "
        "fuel, lands at west-airbase and refuels (NX-368, NX-123).",
        STRAIT_JOINS,
        (),
        True,
    ),
    "capture-strait-1": (
        17_000,
        "kernel",
        "One LOGI JOIN to the neutral cross-n on strait-1 with the shipped config: a capture run "
        "from the sanctuary, a road trip of about 16,000 ticks, then the truck alone fills the "
        "capture bar and flips the node: CaptureStarted, then NodeCaptured with its commander "
        "(NX-125).",
        {1: [join(1, "LOGI", "cross-n")]},
        (),
        True,
    ),
}


def write_case(case_dir: Path, plan: Plan) -> None:
    ticks, handlers, description, commands, tombstoned, shipped = plan
    shutil.rmtree(case_dir / LOG_DIR, ignore_errors=True)
    (case_dir / LOG_DIR).mkdir(parents=True)
    case = {
        "campaign_id": CAMPAIGN_ID,
        "seed": 12345,
        "config_hash": load_campaign_config().config_hash if shipped else "cfg-golden",
        "ticks": ticks,
        "checkpoints_every": 100,
        "handlers": handlers,
        "description": description,
        **({"rules": "shipped"} if shipped else {}),
    }
    (case_dir / CASE_FILE).write_text(json.dumps(case, indent=2) + "\n")
    log = CommandLogWriter(
        case_dir / LOG_DIR, campaign_id=CAMPAIGN_ID, protocol_version=PROTOCOL, next_arrival_seq=1
    )
    for tick, cmds in sorted(commands.items()):
        batch: list[Command] = []
        for cmd in cmds:
            seq = log.next_arrival_seq + len(batch)
            batch.append(cmd.model_copy(update={"target_tick": tick, "arrival_seq": seq}))
        log.append(batch)
        if tick in tombstoned:
            log.append_tombstone(tick)  # as the runtime writes it: after the tick's commands
        log.flush()
    log.close()


if __name__ == "__main__":
    for name, plan in CASES.items():
        write_case(HERE / name, plan)
