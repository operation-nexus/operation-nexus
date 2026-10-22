"""Runs the kernel for the steps the clock says are due (SIM-CORE §5, SC-8; SYSTEM-DESIGN §5.2).

Per tick: drain the inbox, append the commands to the log and flush (write-ahead), `step`, and
every `snapshot_every` ticks write a snapshot, apply retention and rotate the log segment.

Flushing every tick is not what SC-8 needs: an exception in `step` appends the tombstone and
flushes before restoring, which makes the buffered commands durable too. It only shrinks what a
process kill loses. shortcut: an fsync per tick; move to the 1 s cadence (NFR-7) if it shows in
the tick budget. shortcut: the snapshot is compressed and written on the sim thread; Q-SIM-8
moves compression and the write off-thread.

A periodic snapshot that fails to write (OSError) is counted in `snapshot_failures` and retried
at the next interval; the runtime keeps running and the caller alerts (SIM-CORE §6). Any other
failure (a log flush or rotation, or a recovery that cannot restore) sets `halted` and
`halt_reason` and re-raises. The drained commands of that tick are gone from the inbox; a restart
recovers from the snapshot plus the durable log.

The `state_hash` cadence lands with NX-105, metric export with NX-250, crash bundles with
DATA-MODEL §6.3. Starting the sim thread (SIM-CORE §5 threading) has no tracker item yet.
"""

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.events.event import Event
from nexus.core.step import HANDLERS, TICK_DT, Handler, step
from nexus.core.world import World
from nexus.runtime.clock import FixedStepClock
from nexus.runtime.command_log import CommandLogWriter
from nexus.runtime.fsutil import fsync_dir
from nexus.runtime.inbox import Inbox
from nexus.runtime.recovery import recover
from nexus.runtime.snapshot_file import list_snapshots, snapshots_to_delete, write_snapshot

# SIM-CORE §6: 3 crashes in 10 minutes halt. Counted in ticks, so a test or a replay sees the same
# window; while running, 6,000 ticks are 10 real minutes. Operations safety (SIM-CORE §6), not a
# game rule: it never changes a simulated outcome, so it is not a balance key (NX-377, Q-DEV-21).
CRASH_LIMIT = 3
CRASH_WINDOW_TICKS = round(600 / TICK_DT)


class SimRuntime:
    """Owns the world between ticks. After a crash `world` is a new, restored object.

    `crash_ticks` holds the ticks of the last 3 `step` exceptions, so the caller can alert and
    write a crash bundle. On 3 crashes within `CRASH_WINDOW_TICKS` the runtime sets `halted` and
    `halt_reason` and stops stepping: pausing is a logged command (SC-11, ADR-0002), so the
    caller alerts and issues the pause.

    A halted runtime is discarded, never resumed: its `world` may be half-updated. A restart
    builds a new one from `recover`. `crash_ticks` lives per process, so bounding a restart
    loop across processes is the supervisor's job.
    """

    def __init__(
        self,
        world: World,
        inbox: Inbox,
        clock: FixedStepClock,
        log: CommandLogWriter,
        snapshot_dir: Path,
        *,
        protocol_version: str,
        sim_build: str,
        created_at: Callable[[], str],  # UTC ISO-8601 now; never enters state
        snapshot_every: int = 300,  # ops cadence, no effect on outcomes
        handlers: Mapping[str, Handler] = HANDLERS,
    ) -> None:
        if world.rules is None:  # JOIN and movement need them (start_campaign, or restore rules=)
            raise ValueError("SimRuntime needs a world with rules")
        if inbox.next_tick != world.campaign.tick + 1:
            raise ValueError(f"inbox.next_tick {inbox.next_tick} != world tick + 1")
        self.world = world
        self.inbox = inbox
        self.clock = clock
        self.log = log
        self.snapshot_dir = snapshot_dir
        self.protocol_version = protocol_version
        self.sim_build = sim_build
        self.created_at = created_at
        self.snapshot_every = snapshot_every
        self.handlers = handlers
        self.crash_ticks: deque[int] = deque(maxlen=CRASH_LIMIT)
        self.halted = False
        self.halt_reason = ""
        self.snapshot_failures = 0
        self._write_snapshot()  # the recovery base; failing here fails the start

    def run_due(self) -> list[Event]:
        """Run each due step; returns the events in order. Does nothing once halted."""
        events: list[Event] = []
        for _ in range(self.clock.due_steps()):
            if self.halted:
                break
            try:
                events += self._tick()
            except Exception as e:
                self.halted = True
                self.halt_reason = f"runtime failure after tick {self.world.campaign.tick}: {e!r}"
                raise
        return events

    def _tick(self) -> list[Event]:
        commands = self.inbox.drain()
        self.log.append(commands)
        self.log.flush()
        events = self._step(commands)
        if not self.halted and self.world.campaign.tick % self.snapshot_every == 0:
            try:
                self._write_snapshot()
            except OSError:
                self.snapshot_failures += 1
            # DATA-MODEL §6.2: rotate at the boundary even if this snapshot failed; restore then
            # starts from an older snapshot, and segment skipping (by arrival_seq) stays correct.
            self.log.rotate()
        return events

    def _step(self, commands: Sequence[Command]) -> list[Event]:
        """SC-8: on an exception, tombstone the tick, restore, rerun it with commands dropped."""
        tick = self.world.campaign.tick + 1
        try:
            return step(self.world, commands, self.handlers)
        except Exception as e:  # noqa: BLE001 - SC-8: any step exception is recovered
            error = e
        self.log.append_tombstone(tick)
        self.log.flush()
        while True:
            self.crash_ticks.append(tick)
            # The half-updated world is discarded (SC-8); the log is durable up to this tick.
            self.world = recover(
                self.snapshot_dir,
                self.log,
                handlers=self.handlers,
                until_tick=tick - 1,
                rules=self.world.rules,
            ).world
            first = self.crash_ticks[0]
            if len(self.crash_ticks) == CRASH_LIMIT and tick - first < CRASH_WINDOW_TICKS:
                self.halted = True
                self.halt_reason = f"{CRASH_LIMIT} step crashes in ticks {first}..{tick}: {error!r}"
                return []
            try:
                return step(self.world, [], self.handlers, dropped=commands)
            except Exception as e:  # noqa: BLE001 - a system bug raises again; counted above
                error = e

    def _write_snapshot(self) -> None:
        write_snapshot(
            self.snapshot_dir,
            self.world,
            last_arrival_seq=self.log.next_arrival_seq - 1,
            sim_build=self.sim_build,
            protocol_version=self.protocol_version,
            created_at=self.created_at(),
        )
        old = snapshots_to_delete(list_snapshots(self.snapshot_dir))
        for path in old:
            path.unlink()
        if old:
            fsync_dir(self.snapshot_dir)
