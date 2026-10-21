"""Measure replay storage for one game hour (NX-032; CLIPS-REPLAY "Measured storage").

Runs the real `SimRuntime` with the stub handler from tests/runtime/test_recovery.py, submitting
STAND-IN chat commands at a fixed rate, into a temp dir, then runs `replay.py size` on it. Entity
counts are tiny (the stub spawns one unit per command), so the snapshot size is a floor.

  cd services/sim && uv run --frozen python ../../tools/replay/measure.py
    [--ticks 36000] [--per-min 120]

--per-min must divide 600 (10 ticks per second, a whole number of ticks between commands).
Type check: cd services/sim && MYPYPATH=tests uv run --frozen mypy --strict ../../tools/replay
"""

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "services" / "sim" / "tests"))

# shortcut: imports the test helpers (Rig, make_join, stub handler), so this tool is coupled to
# test internals. Upgrade: move them to a shared tests/support module when a second tool needs them.
from runtime.conftest import CAMPAIGN_ID, PROTOCOL  # noqa: E402
from runtime.test_recovery import Rig, make_join  # noqa: E402

from nexus.runtime.command_log import CommandLogWriter  # noqa: E402


class RatedRig(Rig):
    """One JOIN every `period` ticks, a fixed rate (10 ticks per second)."""

    period = 5

    def submit(self, tick: int, poison_at: tuple[int, ...]) -> None:
        if tick % self.period == 0:
            if not self.inbox.submit(make_join(f"t{tick}")):
                raise RuntimeError("inbox full")

    def run(self, last: int) -> None:
        """`run_to` without its per-tick state_hash, which dominates a long run."""
        while self.rt.world.campaign.tick < last:
            self.submit(self.inbox.next_tick, ())
            self.steps += 1
            self.events += self.rt.run_due()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    ap.add_argument("--ticks", type=int, default=36_000)
    ap.add_argument("--per-min", type=int, default=120, help="STAND-IN commands per minute")
    args = ap.parse_args()
    if args.ticks < 1 or not 1 <= args.per_min <= 600 or 600 % args.per_min:
        ap.error("--ticks must be >= 1 and --per-min a divisor of 600")
    RatedRig.period = 600 // args.per_min
    opened: list[CommandLogWriter] = []

    def make_log(directory: Path, *, segment: int, next_arrival_seq: int) -> CommandLogWriter:
        w = CommandLogWriter(
            directory,
            campaign_id=CAMPAIGN_ID,
            protocol_version=PROTOCOL,
            segment=segment,
            next_arrival_seq=next_arrival_seq,
        )
        opened.append(w)
        return w

    factory: Callable[..., CommandLogWriter] = make_log
    with tempfile.TemporaryDirectory() as tmp:
        rig = RatedRig(factory, Path(tmp))
        rig.run(args.ticks)
        for w in opened:
            w.close()
        print(f"{args.ticks} ticks, {args.per_min} commands/min, snapshot_every 300")
        return subprocess.run(  # noqa: S603
            [
                sys.executable,
                str(HERE / "replay.py"),
                "size",
                str(rig.snaps),
                str(rig.logs),
            ]
        ).returncode


if __name__ == "__main__":
    sys.exit(main())
