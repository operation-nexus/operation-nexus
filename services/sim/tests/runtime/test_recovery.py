"""Restore and SC-8 crash recovery tests (NX-103, SIM-CORE SC-3, SC-8, §5, §6; DATA-MODEL §6)."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
import zstandard

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core import step as step_module
from nexus.core.rng import RngStream
from nexus.core.roads import RoadGraph
from nexus.core.rules import Rules
from nexus.core.step import TICK_DT, Handler
from nexus.core.world import Campaign, Vec2, World, state_hash
from nexus.runtime import loop
from nexus.runtime.campaign_config import load_campaign_config
from nexus.runtime.clock import FixedStepClock
from nexus.runtime.command_log import (
    CommandLogError,
    CommandLogReader,
    CommandLogWriter,
    LogEntry,
    Tombstone,
)
from nexus.runtime.inbox import Inbox
from nexus.runtime.loop import SimRuntime
from nexus.runtime.recovery import ReplayCrash, recover, restore
from nexus.runtime.snapshot_file import SnapshotError, list_snapshots, write_snapshot

from .conftest import CAMPAIGN_ID, PROTOCOL

COMMANDER = "0192f0c1-7a2b-7c3d-8e4f-0123456789ab"
POISON_ID = "poison"


def make_join(correlation_id: str) -> JoinCommand:
    """A JOIN for the inbox, which stamps target_tick and arrival_seq."""
    return JoinCommand.model_validate(
        {
            "kind": "JOIN",
            "source": "CHAT",
            "issuer": {"commander_id": COMMANDER},
            "target_tick": 1,
            "arrival_seq": 1,
            "correlation_id": correlation_id,
            "role": "STRIKE",
            "target": None,
            "hold": False,
        }
    )


def spawn_handler(world: World, command: Command, out: list[Event]) -> None:
    """Test stand-in for a real handler: spawns one unit whose hp draws from the spawn stream."""
    hp = world.rng.stream(RngStream.SPAWN).randint(1, 100)
    e = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(command.arrival_seq, 0), hp=hp)
    e.state, e.fuel = "LANDED", 1.0  # an aircraft has a state (NX-368); it never takes off here
    out.append(
        UnitSpawned.model_construct(
            kind="UnitSpawned",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            entity_id=e.id,
            unit_kind=e.kind,
            side=e.side,
            owner_kind=e.owner_kind,
            commander_id=command.issuer.commander_id if isinstance(command, JoinCommand) else None,
            callsign=None,
            node_id="test-node",
            loadout="FULL",
        )
    )


def poison_handler(world: World, command: Command, out: list[Event]) -> None:
    """Like spawn_handler, but raises mid-tick for the poison command (after earlier spawns)."""
    if command.correlation_id == POISON_ID:
        raise RuntimeError("poison command")
    spawn_handler(world, command, out)


STUB: dict[str, Handler] = {"JOIN": spawn_handler}
# SimRuntime needs rules; the stub handlers read none of them.
# The stub's fighters are LANDED aircraft (NX-368): they never move, so no other air rule is read.
STUB_RULES = Rules(
    0.6, {}, {"STRIKE_FIGHTER": "AIR"}, RoadGraph({}, []), {}, "", 1, 0, 1, 1, {}, {}, 0.0, (),
    (1.0, 1.0), 120.0, {}, {}, 5, 1, {}, 1000.0, {}, 0.0, frozenset(), 1.0, 1, 1.0, 3, 7,
)  # fmt: skip
POISON: dict[str, Handler] = {"JOIN": poison_handler}


class Rig:
    """A runtime on files under `root`; `run_to` submits tick % 3 commands per tick."""

    def __init__(
        self,
        make_log: Callable[..., CommandLogWriter],
        root: Path,
        handlers: dict[str, Handler] = STUB,
        world: World | None = None,
        next_seq: int = 1,
        segment: int = 1,
        snapshot_every: int = 300,
    ) -> None:
        self.snaps, self.logs = root / "snapshots", root / "logs"
        self.snaps.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        if world is None:  # not `world or`: an empty World is falsy (__len__)
            world = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"), STUB_RULES)
        self.inbox = Inbox(1000, world.campaign.tick + 1, next_seq)
        self.steps = 0
        self.rt = SimRuntime(
            world,
            self.inbox,
            FixedStepClock(self.now),
            make_log(self.logs, segment=segment, next_arrival_seq=next_seq),
            self.snaps,
            protocol_version=PROTOCOL,
            sim_build="test",
            created_at=lambda: "2026-10-21T12:00:00Z",
            snapshot_every=snapshot_every,
            handlers=handlers,
        )
        self.events: list[Event] = []

    def now(self) -> float:
        return 100.0 + self.steps * TICK_DT

    def submit(self, tick: int, poison_at: tuple[int, ...]) -> None:
        for i in range(tick % 3):
            assert self.inbox.submit(make_join(f"t{tick}-{i}"))
        if tick in poison_at:
            assert self.inbox.submit(make_join(POISON_ID))

    def run_to(self, last: int, poison_at: tuple[int, ...] = ()) -> dict[int, str]:
        """Step to tick `last` (or until halted); returns the state_hash after each tick."""
        hashes: dict[int, str] = {}
        while self.rt.world.campaign.tick < last and not self.rt.halted:
            self.submit(self.inbox.next_tick, poison_at)
            self.steps += 1
            self.events += self.rt.run_due()
            hashes[self.rt.world.campaign.tick] = state_hash(self.rt.world)
        return hashes


type MakeRig = Callable[..., Rig]


@pytest.fixture
def make_rig(log_writer: Callable[..., CommandLogWriter]) -> MakeRig:
    return lambda root, **kw: Rig(log_writer, root, **kw)


def tick_events(events: list[Event], tick: int) -> list[Event]:
    return [e for e in events if e.tick == tick]


def tombstones(logs: Path) -> list[LogEntry]:
    return [e for e in CommandLogReader(logs) if isinstance(e, Tombstone)]


def segments(logs: Path) -> list[Path]:
    return sorted(logs.glob("*.nxl.zst"))


def segment_text(path: Path) -> bytes:
    with path.open("rb") as f:
        return zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True).read()


def test_kill_and_restore_matches_an_uninterrupted_run(tmp_path: Path, make_rig: MakeRig) -> None:
    # Tracker acceptance: kill at tick 640, restore, continue; hashes match the run never killed.
    expected = make_rig(tmp_path / "a").run_to(750)
    killed = make_rig(tmp_path / "b")
    killed.run_to(640)
    snaps, logs = killed.snaps, killed.logs
    assert len(segments(logs)) == 3  # rotated at the snapshots of ticks 300 and 600
    del killed  # the process dies: only the files remain

    r = restore(snaps, logs, handlers=STUB, rules=STUB_RULES)
    assert r.world.campaign.tick == 640
    assert state_hash(r.world) == expected[640]
    assert (r.snapshot.name, r.skipped_snapshots, r.truncated_tail) == (
        "000000000600.nxs",
        [],
        False,
    )

    resumed = make_rig(tmp_path / "b", world=r.world, next_seq=r.last_arrival_seq + 1, segment=3)
    assert resumed.run_to(750) == {t: expected[t] for t in range(641, 751)}
    # Tick 750 has no commands, so the log alone ends at 749; the runtime passes its last tick.
    assert restore(snaps, logs, handlers=STUB, rules=None).world.campaign.tick == 749
    assert (
        state_hash(restore(snaps, logs, handlers=STUB, rules=None, until_tick=750).world)
        == expected[750]
    )


def test_poison_command_is_tombstoned_dropped_and_replayed(
    tmp_path: Path, make_rig: MakeRig
) -> None:
    rig = make_rig(tmp_path, handlers=POISON)
    hashes = rig.run_to(350, poison_at=(320,))
    assert list(rig.rt.crash_ticks) == [320]
    assert not rig.rt.halted
    assert rig.rt.world.campaign.tick == 350  # recovery did not loop

    # Every command of tick 320 (two ordinary JOINs and the poison) is dropped, none applied.
    crashed = tick_events(rig.events, 320)
    rejected = [e for e in crashed if isinstance(e, CommandRejected)]
    assert len(rejected) == len(crashed) == 3
    assert {e.reason for e in rejected} == {"INTERNAL_ERROR"}
    seqs = [e.arrival_seq for e in rejected]
    assert seqs == sorted(seqs) and seqs[-1] == seqs[0] + 2
    assert tombstones(rig.logs) == [Tombstone(320)]
    # The tombstone went to the segment opened at the tick-300 snapshot, which is still current.
    first, second = segments(rig.logs)
    assert rig.rt.log.segment == 2
    assert b'"tombstone":320' in segment_text(second)
    assert b"tombstone" not in segment_text(first)

    # Replaying the files reproduces the tick: same events, same hash.
    at_320 = restore(rig.snaps, rig.logs, handlers=POISON, rules=None, until_tick=320)
    assert at_320.snapshot.name == "000000000300.nxs"
    assert tick_events(at_320.events, 320) == crashed
    assert state_hash(at_320.world) == hashes[320]
    assert (
        state_hash(restore(rig.snaps, rig.logs, handlers=POISON, rules=None).world) == hashes[350]
    )


def test_crash_recovery_keeps_the_campaign_rules(tmp_path: Path, make_rig: MakeRig) -> None:
    # Rules are not in snapshots (NX-121); the restored world must get them back.
    rules = STUB_RULES
    rig = make_rig(tmp_path, handlers=POISON, world=World.new(Campaign(CAMPAIGN_ID, 1, "c"), rules))
    rig.run_to(5, poison_at=(4,))
    assert list(rig.rt.crash_ticks) == [4]
    assert rig.rt.world.rules is rules
    assert restore(rig.snaps, rig.logs, handlers=POISON, rules=rules).world.rules is rules


def break_systems_from(monkeypatch: pytest.MonkeyPatch, tick: int) -> None:
    def broken(world: World, c: object, h: object, out: list[Event]) -> None:
        if world.campaign.tick + 1 >= tick:
            raise RuntimeError("system bug")

    monkeypatch.setattr(step_module, "SYSTEMS", (*step_module.SYSTEMS, ("broken", broken)))


def test_restore_refuses_rules_whose_nodes_differ_from_the_snapshots_owners(
    tmp_path: Path, make_rig: MakeRig
) -> None:
    rig = make_rig(tmp_path)
    rig.run_to(310)  # a stub world owns no nodes; the shipped theater has thirteen
    with pytest.raises(ValueError, match="node owners"):
        restore(rig.snaps, rig.logs, handlers=STUB, rules=load_campaign_config().rules)


def test_system_bug_halts_after_three_crashes(
    tmp_path: Path, make_rig: MakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    break_systems_from(monkeypatch, 5)
    rig = make_rig(tmp_path)
    rig.run_to(10)
    assert rig.rt.halted
    assert "system bug" in rig.rt.halt_reason
    assert list(rig.rt.crash_ticks) == [5, 5, 5]
    assert rig.rt.world.campaign.tick == 4  # the restored, consistent state
    rig.steps += 5
    assert rig.rt.run_due() == []
    assert rig.rt.world.campaign.tick == 4
    assert tombstones(rig.logs) == [Tombstone(5)]


@pytest.mark.parametrize(("window", "halted"), [(None, True), (20, False)])
def test_crash_window_counts_ticks(
    tmp_path: Path,
    make_rig: MakeRig,
    monkeypatch: pytest.MonkeyPatch,
    window: int | None,
    halted: bool,
) -> None:
    if window is not None:
        monkeypatch.setattr(loop, "CRASH_WINDOW_TICKS", window)
    rig = make_rig(tmp_path, handlers=POISON)
    rig.run_to(40, poison_at=(10, 20, 30))
    assert list(rig.rt.crash_ticks) == [10, 20, 30]
    assert rig.rt.halted is halted
    assert rig.rt.world.campaign.tick == (29 if halted else 40)


def test_failed_recovery_halts_and_raises(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path, handlers=POISON)
    (rig.snaps / "000000000000.nxs").write_bytes(b"garbage")
    with pytest.raises(SnapshotError):
        rig.run_to(10, poison_at=(5,))
    assert rig.rt.halted
    assert "SnapshotError" in rig.rt.halt_reason


def test_log_flush_failure_halts_and_raises(
    tmp_path: Path, make_rig: MakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = make_rig(tmp_path)
    rig.run_to(3)

    def fail() -> None:
        raise OSError("disk full")

    monkeypatch.setattr(rig.rt.log, "flush", fail)
    with pytest.raises(OSError, match="disk full"):
        rig.run_to(5)
    assert rig.rt.halted
    assert rig.rt.world.campaign.tick == 3


def test_snapshot_write_failure_is_counted_and_retried(
    tmp_path: Path, make_rig: MakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = make_rig(tmp_path, snapshot_every=5)

    def fail(*args: object, **kwargs: object) -> Path:
        raise OSError("disk full")

    with monkeypatch.context() as m:
        m.setattr(loop, "write_snapshot", fail)
        rig.run_to(12)
    assert (rig.rt.snapshot_failures, rig.rt.halted) == (2, False)
    rig.run_to(15)
    assert [p.name for p in list_snapshots(rig.snaps)] == ["000000000000.nxs", "000000000015.nxs"]


def test_corrupt_newest_snapshot_falls_back_to_the_previous(
    tmp_path: Path, make_rig: MakeRig
) -> None:
    rig = make_rig(tmp_path)
    hashes = rig.run_to(650)
    newest = rig.snaps / "000000000600.nxs"
    data = bytearray(newest.read_bytes())
    data[len(data) // 2] ^= 0xFF
    newest.write_bytes(bytes(data))
    r = restore(rig.snaps, rig.logs, handlers=STUB, rules=None)
    assert r.skipped_snapshots == [newest]
    assert r.snapshot.name == "000000000300.nxs"
    assert state_hash(r.world) == hashes[650]


def test_until_tick_before_the_newest_snapshot_uses_an_older_one(
    tmp_path: Path, make_rig: MakeRig
) -> None:
    rig = make_rig(tmp_path)
    hashes = rig.run_to(650)
    r = restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=450)
    assert (r.snapshot.name, r.world.campaign.tick) == ("000000000300.nxs", 450)
    assert state_hash(r.world) == hashes[450]


def test_no_verified_snapshot_raises(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path)
    rig.run_to(5)
    (rig.snaps / "000000000000.nxs").write_bytes(b"garbage")
    with pytest.raises(SnapshotError, match="no snapshot verifies"):
        restore(rig.snaps, rig.logs, handlers=STUB, rules=None)


def test_empty_log_restores_the_snapshot(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path)  # the start snapshot is written; the log has no frame yet
    r = restore(rig.snaps, rig.logs, handlers=STUB, rules=None)
    assert (r.world.campaign.tick, r.last_arrival_seq, r.events) == (0, 0, [])
    assert state_hash(r.world) == state_hash(rig.rt.world)


def test_log_that_contradicts_the_snapshot_raises(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path)
    rig.run_to(20)
    at_10 = restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=10)
    # A snapshot claiming tick 11's first command already landed by tick 10.
    write_snapshot(
        rig.snaps,
        at_10.world,
        last_arrival_seq=at_10.last_arrival_seq + 1,
        sim_build="test",
        protocol_version=PROTOCOL,
        created_at="2026-10-21T12:00:00Z",
    )
    with pytest.raises(CommandLogError, match="disagrees"):
        restore(rig.snaps, rig.logs, handlers=STUB, rules=None)


@pytest.mark.parametrize(
    ("missing", "until_tick", "match"),
    [(2, None, "does not continue"), (1, 250, "does not cover")],
)
def test_missing_segment_raises(
    tmp_path: Path, make_rig: MakeRig, missing: int, until_tick: int | None, match: str
) -> None:
    rig = make_rig(tmp_path)
    rig.run_to(650)
    segments(rig.logs)[missing - 1].unlink()
    with pytest.raises(CommandLogError, match=match):
        restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=until_tick)


def test_restore_skips_segments_before_the_snapshot(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path)
    hashes = rig.run_to(650)
    segments(rig.logs)[0].write_bytes(b"garbage")  # proves segment 1 is never read
    assert state_hash(restore(rig.snaps, rig.logs, handlers=STUB, rules=None).world) == hashes[650]
    with pytest.raises(CommandLogError):  # from snapshot 0, segment 1 is needed
        restore(rig.snaps, rig.logs, handlers=STUB, rules=None, until_tick=250)


def test_torn_log_tail_restores_and_is_flagged(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path)
    hashes = rig.run_to(50)
    frame = zstandard.ZstdCompressor(write_checksum=True).compress(b'{"x":1}\n' * 100)
    with segments(rig.logs)[-1].open("ab") as f:
        f.write(frame[: len(frame) // 2])
    r = restore(rig.snaps, rig.logs, handlers=STUB, rules=None)
    assert r.truncated_tail
    assert state_hash(r.world) == hashes[50]


def write_ahead_then_die(rig: Rig) -> None:
    """The next tick's commands reach the log, then the process dies inside `step`."""
    rig.submit(rig.inbox.next_tick, poison_at=(rig.inbox.next_tick,))
    rig.rt.log.append(rig.inbox.drain())
    rig.rt.log.flush()


def test_recover_tombstones_a_replay_crash_without_tombstone(
    tmp_path: Path, make_rig: MakeRig
) -> None:
    rig = make_rig(tmp_path, handlers=POISON)
    rig.run_to(21)
    write_ahead_then_die(rig)  # tick 22: one JOIN and the poison
    with pytest.raises(ReplayCrash) as crash:
        restore(rig.snaps, rig.logs, handlers=POISON, rules=None)
    assert (crash.value.tick, crash.value.tombstoned) == (22, False)

    r = recover(rig.snaps, rig.rt.log, handlers=POISON, rules=None)
    assert r.world.campaign.tick == 22
    dropped = tick_events(r.events, 22)
    assert [e.reason for e in dropped if isinstance(e, CommandRejected)] == ["INTERNAL_ERROR"] * 2
    assert len(dropped) == 2
    assert tombstones(rig.logs) == [Tombstone(22)]
    assert state_hash(
        restore(rig.snaps, rig.logs, handlers=POISON, rules=None).world
    ) == state_hash(r.world)


def test_recover_gives_up_after_max_attempts(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path, handlers=POISON)
    rig.run_to(21)
    write_ahead_then_die(rig)
    with pytest.raises(ReplayCrash):
        recover(rig.snaps, rig.rt.log, handlers=POISON, rules=None, max_attempts=1)
    assert tombstones(rig.logs) == []


def test_recover_raises_on_a_system_bug_without_looping(
    tmp_path: Path, make_rig: MakeRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = make_rig(tmp_path)
    rig.run_to(10)
    break_systems_from(monkeypatch, 5)  # replay now crashes on a tick that had no crash live
    with pytest.raises(ReplayCrash) as crash:
        recover(rig.snaps, rig.rt.log, handlers=STUB, rules=None)
    assert (crash.value.tick, crash.value.tombstoned) == (5, True)
    assert tombstones(rig.logs) == [Tombstone(5)]  # tombstoned once, then raised


def test_runtime_applies_snapshot_retention(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path, snapshot_every=1)
    (rig.snaps / "notes.nxs").write_bytes(b"")  # a stray name is ignored, not parsed
    rig.run_to(30)
    kept = [int(p.stem) for p in list_snapshots(rig.snaps)]
    assert kept == [0, *range(11, 31)]  # the hour's first, plus the newest 20
    assert (rig.snaps / "notes.nxs").exists()


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from pathlib import Path\n"
    "from runtime.test_recovery import POISON; from nexus.core.world import state_hash\n"
    "from nexus.runtime.recovery import restore\n"
    "print(state_hash(restore(Path(sys.argv[2]), Path(sys.argv[3]),\n"
    "                          handlers=POISON, rules=None).world))"
)


def test_restore_is_hash_seed_independent(tmp_path: Path, make_rig: MakeRig) -> None:
    rig = make_rig(tmp_path, handlers=POISON)
    expected = rig.run_to(320, poison_at=(310,))[320]

    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        tests_dir = str(Path(__file__).parent.parent)
        argv = [sys.executable, "-c", _CHILD, tests_dir, str(rig.snaps)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output([*argv, str(rig.logs)], env=env, text=True).strip()  # noqa: S603

    assert run("1") == run("2") == expected


def test_tombstone_in_a_command_free_interval_is_not_skipped(
    tmp_path: Path, log_writer: Callable[..., CommandLogWriter]
) -> None:
    # Segments 2 and 3 both start at seq 3; segment 2 holds only a tombstone for a tick after the
    # snapshot. Skipping a segment whose successor starts at `from_arrival_seq` would lose it.
    log = log_writer(tmp_path)
    log.append([make_join("a"), make_join("b").model_copy(update={"arrival_seq": 2})])
    log.rotate()
    log.append_tombstone(305)
    log.rotate()
    log.flush()
    assert len(segments(tmp_path)) == 3
    assert Tombstone(305) in list(CommandLogReader(tmp_path, from_arrival_seq=3))

    world = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test", tick=300))
    write_snapshot(
        tmp_path,
        world,
        last_arrival_seq=2,
        sim_build="test",
        protocol_version=PROTOCOL,
        created_at="2026-10-21T12:00:00Z",
    )
    r = restore(tmp_path, tmp_path, handlers=STUB, rules=None)
    assert r.world.campaign.tick == 305  # replay reaches the tombstoned tick, dropping nothing
