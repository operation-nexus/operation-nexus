"""Restore from the newest verified snapshot plus the command log (SIM-CORE SC-8, SC-9, §5;
DATA-MODEL §6.1, §6.2; SYSTEM-DESIGN §5.5).

Replay steps every tick after the snapshot, so it needs the tick to stop at: the log holds only
ticks that had commands or a tombstone. The runtime passes the last tick it reached; without
`until_tick` replay stops at the last tick the log names.

`recover` is the entry point for both the live crash path and a process restart: when a replayed
tick raises and has no tombstone (the process died after the write-ahead flush, before the
tombstone landed), it tombstones that tick and retries.
"""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.event import Event
from nexus.core.combat import validate as validate_combat
from nexus.core.defense import validate as validate_defense
from nexus.core.rules import Rules
from nexus.core.step import HANDLERS, Handler, step
from nexus.core.world import World
from nexus.runtime.command_log import (
    CommandLogError,
    CommandLogReader,
    CommandLogWriter,
    Tombstone,
)
from nexus.runtime.snapshot_file import (
    SnapshotError,
    SnapshotHeader,
    list_snapshots,
    read_snapshot,
)


class ReplayCrash(Exception):
    """`step` raised while replaying `tick`; the partly replayed world is discarded."""

    def __init__(self, tick: int, cause: Exception, *, tombstoned: bool) -> None:
        note = " (already tombstoned)" if tombstoned else ""
        super().__init__(f"step raised replaying tick {tick}{note}: {cause!r}")
        self.tick = tick
        self.cause = cause
        self.tombstoned = tombstoned


@dataclass(frozen=True, slots=True)
class RestoreResult:
    world: World
    snapshot: Path  # the snapshot replay started from
    skipped_snapshots: list[Path]  # newer snapshots that failed verification: alert
    last_arrival_seq: int  # the next Inbox / CommandLogWriter continues at this + 1
    truncated_tail: bool  # the log's last frame was torn and dropped: alert (DATA-MODEL §6.2)
    events: list[Event]  # every replayed tick's events, in order


def recover(
    snapshot_dir: Path,
    writer: CommandLogWriter,
    *,
    handlers: Mapping[str, Handler] = HANDLERS,
    until_tick: int | None = None,
    max_attempts: int = 3,
    rules: Rules | None,
) -> RestoreResult:
    """`restore`, tombstoning (through `writer`, flushed) each replayed tick that raises.

    A tick that raises although it is already tombstoned has no command cause: a system bug that
    crashes replay needs a code fix, so its ReplayCrash is raised at once, as is the last one.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return restore(
                snapshot_dir,
                writer.directory,
                handlers=handlers,
                until_tick=until_tick,
                rules=rules,
            )
        except ReplayCrash as crash:
            if crash.tombstoned or attempt == max_attempts:
                raise
            writer.append_tombstone(crash.tick)
            writer.flush()
    raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")


def restore(
    snapshot_dir: Path,
    log_dir: Path,
    *,
    handlers: Mapping[str, Handler] = HANDLERS,
    until_tick: int | None = None,
    rules: Rules | None,
) -> RestoreResult:
    """Load the newest snapshot that verifies (at or before `until_tick`), then replay the log.

    Every command of a tombstoned tick is dropped and emitted as `CommandRejected{INTERNAL_ERROR}`
    (SC-8). Raises SnapshotError when no snapshot verifies, CommandLogError on a damaged log or
    one that does not continue the snapshot, ReplayCrash when `step` raises. `rules` is the
    campaign's static config (not in the snapshot), attached to the restored world;
    required, `None` only for a world that never reads it.
    """
    header, world, path, skipped = _newest_valid(snapshot_dir, until_tick)
    if rules is not None and set(world.owner) != set(rules.node_kind):
        raise ValueError("the snapshot's node owners do not match the rules' theater nodes")
    if rules is not None:
        validate_combat(world, rules)  # a snapshot carries no rules; its combat state must fit them
        validate_defense(world, rules)
    world.rules = rules
    by_tick: defaultdict[int, list[Command]] = defaultdict(list)
    tombstones: set[int] = set()
    # The reader checks arrival_seq is gapless from last_arrival_seq + 1 on; this check ties each
    # command to the right side of the snapshot.
    reader = CommandLogReader(log_dir, from_arrival_seq=header.last_arrival_seq + 1)
    for entry in reader:
        if isinstance(entry, Tombstone):
            tombstones.add(entry.tick)
            continue
        if (entry.target_tick > header.tick) != (entry.arrival_seq > header.last_arrival_seq):
            raise CommandLogError(
                f"arrival_seq {entry.arrival_seq} at tick {entry.target_tick} disagrees with "
                f"{path.name} (last_arrival_seq {header.last_arrival_seq})"
            )
        if entry.target_tick > header.tick:
            by_tick[entry.target_tick].append(entry)
    end = max([header.tick, *by_tick, *tombstones]) if until_tick is None else until_tick
    last_seq = header.last_arrival_seq
    events: list[Event] = []
    for tick in range(header.tick + 1, end + 1):
        commands = by_tick.get(tick, [])
        try:
            if tick in tombstones:
                events += step(world, [], handlers, dropped=commands)
            else:
                events += step(world, commands, handlers)
        except Exception as e:
            raise ReplayCrash(tick, e, tombstoned=tick in tombstones) from e
        last_seq = commands[-1].arrival_seq if commands else last_seq
    return RestoreResult(world, path, skipped, last_seq, reader.truncated_tail, events)


def _newest_valid(
    directory: Path, until_tick: int | None
) -> tuple[SnapshotHeader, World, Path, list[Path]]:
    skipped: list[Path] = []
    for path in reversed(list_snapshots(directory)):
        if until_tick is not None and int(path.stem) > until_tick:
            continue
        try:
            header, world = read_snapshot(path)
        except SnapshotError:
            skipped.append(path)
            continue
        return header, world, path, skipped
    raise SnapshotError(f"{directory}: no snapshot verifies (skipped {[p.name for p in skipped]})")
