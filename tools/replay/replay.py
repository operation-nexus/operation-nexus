"""Replay CLI (NX-032; CLIPS-REPLAY §1, SIM-CORE SC-16, DATA-MODEL §6).

Re-simulates a campaign from its snapshots and command log with `nexus.runtime.recovery.restore`.
A developer tool: it reproduces a run only on the same commit and image (SC-16), not an archive.
It uses the real, still empty `HANDLERS`: gameplay handlers arrive with their tracker items, so a
log holding commands for a kind without a handler does not replay yet.

  cd services/sim && uv run --frozen python ../../tools/replay/replay.py run SNAPSHOTS LOGS
  ... replay.py verify SNAPSHOTS LOGS --expect HASH [--until-tick N]
  ... replay.py size SNAPSHOTS LOGS

`run` and `verify` load the campaign's config (balance, units, theater; NX-122) for the kernel's
`Rules`, the shipped files unless `--balance`, `--units`, `--weapons`, `--roles` or `--theater`
name others, and refuse a snapshot whose campaign `config_hash` differs from that config's.

Exit 0 on success, 1 when `verify` finds a different hash, 2 on any error (one line on stderr).
"""

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

from nexus.core.step import HANDLERS
from nexus.core.world import state_hash
from nexus.runtime.campaign_config import CampaignConfig, ConfigPaths, load_campaign_config
from nexus.runtime.command_log import CommandLogError, CommandLogReader, Tombstone
from nexus.runtime.config import ConfigError
from nexus.runtime.recovery import ReplayCrash, RestoreResult, restore
from nexus.runtime.snapshot_file import SnapshotError, list_snapshots

TICKS_PER_HOUR = 36_000  # game time at 10 Hz (DATA-MODEL §6.1)


def warnings(result: RestoreResult, logs: Path) -> list[str]:
    out = [
        f"warning: snapshot {p.name} failed verification, skipped" for p in result.skipped_snapshots
    ]
    if result.truncated_tail:
        out.append("warning: the log's last frame was torn and dropped")
    kinds = {e.kind for e in CommandLogReader(logs) if not isinstance(e, Tombstone)}
    if missing := sorted(kinds - HANDLERS.keys()):
        out.append(
            f"warning: the log holds {', '.join(missing)} commands with no handler yet; "
            "replay rejects them until their handler lands"
        )
    return out


def _restore(args: argparse.Namespace, until_tick: int | None) -> RestoreResult:
    snaps = list_snapshots(args.snapshots)
    if until_tick is not None and snaps and all(int(p.stem) > until_tick for p in snaps):
        raise SnapshotError(f"no snapshot at or before tick {until_tick}")
    config: CampaignConfig = args.config
    result = restore(args.snapshots, args.logs, until_tick=until_tick, rules=config.rules)
    if (have := result.world.campaign.config_hash) != config.config_hash:
        raise ConfigError(
            f"snapshot config_hash {have} differs from the loaded config's {config.config_hash}; "
            "point --balance, --units, --weapons, --roles and --theater at the campaign's files"
        )
    return result


def cmd_run(args: argparse.Namespace) -> int:
    final = _restore(args, args.until_tick)
    for line in warnings(final, args.logs):
        print(line)
    last = final.world.campaign.tick
    start = int(list_snapshots(args.snapshots)[0].stem)  # earlier history is pruned
    ticks = range(args.every, last, args.every)
    if any(t < start for t in ticks):
        print(
            f"note: checkpoints before tick {start} skipped (no snapshot at or before them)",
            file=sys.stderr,
        )
    for tick in ticks:
        if tick >= start:
            print(f"tick {tick} {state_hash(_restore(args, tick).world)}")
    print(f"tick {last} {state_hash(final.world)} (final)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    result = _restore(args, args.until_tick)
    for line in warnings(result, args.logs):
        print(line)
    got = state_hash(result.world)
    if got != args.expect:
        print(f"MISMATCH: expected {args.expect}, got {got}", file=sys.stderr)
        return 1
    print(f"ok {got}")
    return 0


def _stats(label: str, files: list[Path], ticks: int, *, rate: bool) -> None:
    total = sum(f.stat().st_size for f in files)
    largest = max((f.stat().st_size for f in files), default=0)
    if rate:
        per_hour = f"{total / ticks * TICKS_PER_HOUR:.0f} bytes per game hour" if ticks else "n/a"
    else:
        per_hour = "retained (capped by retention; not a per-hour rate)"
    print(f"{label}: {len(files)} files, {total} bytes, {per_hour}, largest {largest} bytes")


def cmd_size(args: argparse.Namespace) -> int:
    snaps = list_snapshots(args.snapshots)
    segments = sorted(args.logs.glob("*.nxl.zst"))
    if not snaps:
        raise SnapshotError(f"{args.snapshots}: no snapshots")
    ticks = int(snaps[-1].stem)  # the log holds only ticks with commands: look at its last one
    for entry in CommandLogReader(args.logs):
        ticks = max(ticks, entry.tick if isinstance(entry, Tombstone) else entry.target_tick)
    print(f"ticks covered: {ticks} ({ticks / TICKS_PER_HOUR:.3f} game hours)")
    _stats("snapshots", snaps, ticks, rate=False)
    _stats("log segments", segments, ticks, rate=True)
    return 0


def _int(minimum: int) -> Callable[[str], int]:
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"not an integer: {text!r}") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"must be >= {minimum}, got {value}")
        return value

    return parse


def _hash(text: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise argparse.ArgumentTypeError("expected 64 lowercase hex digits")
    return text


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    sub = p.add_subparsers(dest="command", required=True)
    for name, fn, text in (
        ("run", cmd_run, "print state_hash at checkpoints and the final tick"),
        ("verify", cmd_verify, "exit 0 iff the final state_hash equals --expect"),
        ("size", cmd_size, "bytes on disk and counts; log bytes per game hour"),
    ):
        s = sub.add_parser(name, help=text, description=text)
        s.add_argument("snapshots", type=Path, help="snapshot directory")
        s.add_argument("logs", type=Path, help="command log directory")
        s.set_defaults(fn=fn)
        if name != "size":
            s.add_argument("--until-tick", type=_int(0), default=None, help="stop at this tick")
        if name != "size":
            defaults = ConfigPaths()
            for field in ("balance", "units", "weapons", "roles", "theater"):
                s.add_argument(
                    f"--{field}",
                    type=Path,
                    default=getattr(defaults, field),
                    help="config path (default: the shipped file)",
                )
        if name == "run":
            s.add_argument("--every", type=_int(1), default=100, help="checkpoint spacing in ticks")
        if name == "verify":
            s.add_argument(
                "--expect", type=_hash, required=True, help="expected final state_hash (hex)"
            )
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        for path in (args.snapshots, args.logs):
            if not path.is_dir():
                raise NotADirectoryError(f"{path}: not a directory")
        if args.command != "size":
            args.config = load_campaign_config(
                ConfigPaths(args.balance, args.units, args.weapons, args.roles, args.theater)
            )
        return int(args.fn(args))
    except (ConfigError, SnapshotError, CommandLogError, ReplayCrash, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
