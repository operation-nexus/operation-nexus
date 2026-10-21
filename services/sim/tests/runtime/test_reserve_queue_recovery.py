"""NX-122 part 3: the reserve queue across SC-8 crash recovery and kill/restore (SIM-CORE SC-8,
SC-9; STATE-MACHINES §4.1). The queue is world state, so a queued JOIN outlives a tombstone."""

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core import handlers as handlers_module
from nexus.core.handlers import Handler, join
from nexus.core.rules import Rules
from nexus.core.world import Campaign, World, state_hash
from nexus.runtime.campaign_config import CampaignConfig
from nexus.runtime.command_log import CommandLogReader, CommandLogWriter, Tombstone
from nexus.runtime.recovery import restore

from .conftest import CAMPAIGN_ID
from .test_recovery import Rig, make_join

FREE = "free"


def free_or_join(world: World, command: Command, out: list[Event]) -> None:
    """Test stand-in for a despawn (NX-324): a JOIN with correlation id `free` removes the
    commander's unit; any other JOIN is the real handler. Logged, so replays repeat it."""
    if command.correlation_id != FREE:
        join(world, command, out)
        return
    (unit,) = [e for e in world.entities() if e.commander_id == command.issuer.commander_id]
    world.remove(unit.id)


FREEING: dict[str, Handler] = {"JOIN": free_or_join}


def cmd(n: int, correlation_id: str) -> Command:
    data = make_join(correlation_id).model_dump()
    return JoinCommand.model_validate({**data, "issuer": {"commander_id": cid(n)}})


def cid(n: int) -> str:
    return f"0192f0c1-7a2b-7c3d-8e4f-{n:012d}"


@pytest.fixture
def cap1(shipped_config: CampaignConfig) -> Rules:
    return dataclasses.replace(shipped_config.rules, max_viewer_units=1)


def make(
    log_writer: Callable[..., CommandLogWriter],
    root: Path,
    world: World,
    next_seq: int = 1,
    segment: int = 1,
) -> Rig:
    return Rig(
        log_writer,
        root,
        handlers=FREEING,
        world=world,
        next_seq=next_seq,
        segment=segment,
        snapshot_every=5,
    )


def drive(rig: Rig, last: int, plan: dict[int, list[Command]]) -> dict[int, str]:
    """Step to `last`, submitting `plan[tick]` before each tick; the state_hash after each."""
    hashes: dict[int, str] = {}
    while rig.rt.world.campaign.tick < last and not rig.rt.halted:
        for c in plan.get(rig.inbox.next_tick, []):
            assert rig.inbox.submit(c)
        rig.steps += 1
        rig.events += rig.rt.run_due()
        hashes[rig.rt.world.campaign.tick] = state_hash(rig.rt.world)
    return hashes


def queue_of(world: World) -> list[str]:
    return [c.issuer.commander_id for c in world.reserve_queue]


def test_a_queued_join_that_crashes_when_served_is_dropped_on_recovery(
    tmp_path: Path,
    log_writer: Callable[..., CommandLogWriter],
    cap1: Rules,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tick 1 commands queue behind the cap (commander 1 holds the slot); commander 1's unit is
    # freed on tick 3, so lifecycle serves the poison entry and raises. The poison came from the
    # log of tick 1, which is not tombstoned: without SC-8 queue dropping every replay would
    # crash on tick 3 again.
    spawn = handlers_module._spawn

    def poisoned(world: World, command: Command, *args: object) -> None:
        if command.correlation_id == "poison":
            raise RuntimeError("poison queue entry")
        spawn(world, command, *args)  # type: ignore[arg-type]  # forwarded unchanged

    monkeypatch.setattr(handlers_module, "_spawn", poisoned)
    world = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"), cap1)
    rig = make(log_writer, tmp_path, world)
    plan = {1: [cmd(1, "a"), cmd(2, "poison"), cmd(3, "b")], 3: [cmd(1, FREE)], 6: [cmd(1, FREE)]}
    hashes = drive(rig, 8, plan)

    assert list(rig.rt.crash_ticks) == [3] and not rig.rt.halted
    assert [e for e in CommandLogReader(rig.logs) if isinstance(e, Tombstone)] == [Tombstone(3)]
    at_3 = [e for e in rig.events if e.tick == 3]
    # The tick's own command, then the poison entry: both INTERNAL_ERROR, each its arrival_seq.
    assert [(type(e), getattr(e, "arrival_seq", None)) for e in at_3] == [
        (CommandRejected, 4),
        (CommandRejected, 2),
    ]
    assert {getattr(e, "reason", None) for e in at_3} == {"INTERNAL_ERROR"}
    # The free was dropped with its tick (commander 1 kept the slot), yet the poison is gone:
    # the next free, on tick 6, serves commander 3.
    served = [(e.tick, e.commander_id) for e in rig.events if isinstance(e, UnitSpawned)]
    assert served == [(1, cid(1)), (6, cid(3))]
    assert queue_of(rig.rt.world) == []
    # Replaying the log (tombstone included) reproduces the live run.
    replayed = restore(rig.snaps, rig.logs, handlers=FREEING, rules=cap1, until_tick=8)
    assert state_hash(replayed.world) == hashes[8]


def test_kill_and_restore_with_a_queue_matches_an_uninterrupted_run(
    tmp_path: Path, log_writer: Callable[..., CommandLogWriter], cap1: Rules
) -> None:
    # The queue is non-empty at the tick-5 snapshot and at the kill (tick 6); it is served on
    # ticks 7 and 10, after the restore.
    plan = {
        1: [cmd(1, "a"), cmd(2, "b"), cmd(3, "c")],
        7: [cmd(1, FREE)],
        10: [cmd(2, FREE), cmd(4, "d")],
    }

    def new_world() -> World:
        return World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"), cap1)

    expected = drive(make(log_writer, tmp_path / "a", new_world()), 12, plan)
    killed = make(log_writer, tmp_path / "b", new_world())
    drive(killed, 6, plan)
    assert queue_of(killed.rt.world) == [cid(2), cid(3)]
    snaps, logs = killed.snaps, killed.logs
    del killed

    r = restore(snaps, logs, handlers=FREEING, rules=cap1, until_tick=6)
    assert (r.snapshot.name, r.world.campaign.tick) == ("000000000005.nxs", 6)
    assert queue_of(r.world) == [cid(2), cid(3)]
    seq = r.last_arrival_seq + 1
    resumed = make(log_writer, tmp_path / "b", r.world, next_seq=seq, segment=2)
    assert drive(resumed, 12, plan) == {t: expected[t] for t in range(7, 13)}
    served = [e.commander_id for e in resumed.events if isinstance(e, UnitSpawned)]
    assert served == [cid(2), cid(3)]
    assert queue_of(resumed.rt.world) == [cid(4)]
