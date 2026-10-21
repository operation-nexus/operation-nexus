"""Runtime tests: inbox, fixed-step clock and loop (NX-102, SIM-CORE §5, SC-6)."""

import threading

import pytest

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.core.step import step
from nexus.core.world import Campaign, World, state_hash
from nexus.runtime.clock import FixedStepClock
from nexus.runtime.inbox import Inbox
from nexus.runtime.loop import SimRuntime

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
COMMANDER = "0192f0c1-7a2b-7c3d-8e4f-0123456789ab"


def make_join(**fields: object) -> JoinCommand:
    """A validated JOIN command; keyword arguments override payload fields."""
    payload = {
        "kind": "JOIN",
        "source": "CHAT",
        "issuer": {"commander_id": COMMANDER},
        "target_tick": 1,
        "arrival_seq": 1,
        "correlation_id": "msg-1",
        "role": "STRIKE",
        "target": None,
        "hold": False,
    }
    return JoinCommand.model_validate({**payload, **fields})


class FakeTime:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def new_world() -> World:
    return World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"))


def test_submit_stamps_next_tick_and_monotonic_seq() -> None:
    inbox = Inbox(capacity=10, next_tick=5)
    original = make_join(target_tick=99, arrival_seq=99, correlation_id="a")
    assert inbox.submit(original)
    assert inbox.submit(make_join(correlation_id="b"))
    assert original.target_tick == 99  # the caller's object is not mutated
    drained = inbox.drain()
    assert [(c.correlation_id, c.target_tick, c.arrival_seq) for c in drained] == [
        ("a", 5, 1),
        ("b", 5, 2),
    ]
    assert inbox.drain() == []  # drain empties the inbox and advances the tick
    assert inbox.submit(make_join())
    assert [(c.target_tick, c.arrival_seq) for c in inbox.drain()] == [(7, 3)]  # seq never reused


def test_overflow_is_rejected_and_counted_and_drain_frees_capacity() -> None:
    inbox = Inbox(capacity=2, next_tick=1)
    assert inbox.submit(make_join())
    assert inbox.submit(make_join())
    assert not inbox.submit(make_join())
    assert not inbox.submit(make_join())
    assert inbox.rejected_overflow == 2
    assert len(inbox.drain()) == 2
    assert inbox.submit(make_join())
    assert inbox.submit(make_join())
    assert [c.arrival_seq for c in inbox.drain()] == [3, 4]


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError, match="capacity"):
        Inbox(capacity=0, next_tick=1)


def test_concurrent_submits_drain_in_arrival_order() -> None:
    inbox = Inbox(capacity=1000, next_tick=1)
    ids = [f"m{(i * 37) % 400}" for i in range(400)]  # a fixed shuffle (37 is coprime to 400)
    chunks = [ids[i::4] for i in range(4)]

    def submit_all(chunk: list[str]) -> None:
        for cid in chunk:
            assert inbox.submit(make_join(correlation_id=cid))

    threads = [threading.Thread(target=submit_all, args=(c,)) for c in chunks]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    drained = inbox.drain()
    assert [c.arrival_seq for c in drained] == list(range(1, 401))
    assert sorted(c.correlation_id for c in drained) == sorted(ids)

    # The outcome depends only on arrival order: any list order passed to step agrees.
    a, b = new_world(), new_world()
    assert step(a, drained) == step(b, list(reversed(drained)))
    assert state_hash(a) == state_hash(b)


def test_clock_counts_due_steps() -> None:
    now = FakeTime()
    clock = FixedStepClock(now)
    assert clock.due_steps() == 0
    now.t += 0.05
    assert clock.due_steps() == 0
    now.t += 0.05
    assert clock.due_steps() == 1
    now.t += 0.3
    assert clock.due_steps() == 3
    now.t += 0.25
    assert clock.due_steps() == 2
    now.t += 0.05  # the 0.05 carried over completes a step
    assert clock.due_steps() == 1
    assert clock.tick_overruns == 0


def test_clock_long_stall_catches_up_three_and_counts_overrun() -> None:
    now = FakeTime()
    clock = FixedStepClock(now)
    now.t += 5.0
    assert clock.due_steps() == 3
    assert clock.tick_overruns == 1
    assert clock.due_steps() == 0  # the excess is dropped, not run later
    now.t += 0.1
    assert clock.due_steps() == 1
    assert clock.tick_overruns == 1


def test_run_due_drains_and_steps_each_due_tick() -> None:
    now = FakeTime()
    world = new_world()
    inbox = Inbox(capacity=10, next_tick=1)
    runtime = SimRuntime(world, inbox, FixedStepClock(now))
    inbox.submit(make_join())
    assert runtime.run_due() == []
    now.t += 0.1
    first = runtime.run_due()
    inbox.submit(make_join())
    now.t += 0.1
    events = first + runtime.run_due()
    assert world.campaign.tick == 2
    # JOIN has no handler yet: each is rejected on its own tick (SC-7).
    rejected = [e for e in events if isinstance(e, CommandRejected)]
    assert len(rejected) == len(events)
    assert [(e.tick, e.arrival_seq) for e in rejected] == [(1, 1), (2, 2)]
    assert inbox.drain() == []


def test_submit_during_catch_up_lands_on_the_next_step() -> None:
    # The old race: a caller read tick T, the runtime caught up past T + 1, then the command was
    # stamped T + 1 and never drained. Now the inbox stamps the tick it will drain next.
    now = FakeTime()
    world = new_world()
    inbox = Inbox(capacity=1, next_tick=1)
    runtime = SimRuntime(world, inbox, FixedStepClock(now))
    stale_tick = world.campaign.tick
    now.t += 0.3
    assert runtime.run_due() == []  # three catch-up steps drain ticks 1..3
    assert inbox.submit(make_join())
    now.t += 0.1
    events = runtime.run_due()
    assert world.campaign.tick == stale_tick + 4
    assert [(e.kind, e.tick) for e in events] == [("CommandRejected", 4)]
    assert inbox.submit(make_join())  # its capacity slot was freed


def test_runtime_rejects_an_inbox_out_of_step_with_the_world() -> None:
    with pytest.raises(ValueError, match="next_tick"):
        SimRuntime(new_world(), Inbox(capacity=1, next_tick=5), FixedStepClock(FakeTime()))
