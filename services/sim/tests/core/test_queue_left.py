"""NX-371: `ReserveQueueLeft` on every queue exit and `SYS_QUEUE_TIMEOUT` (GAMEPLAY RQ-1;
STATE-MACHINES §4.1; CONTRACTS §5.2, §6). Same low-cap world as test_reserve_queue.py."""

import dataclasses

from hypothesis import example, given
from hypothesis import strategies as st
from test_join import cid, join
from test_reserve_queue import CAP2, capped, full_world, queue_of, queued

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.sys_queue_timeout import SysQueueTimeoutCommand
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.reserve_queue_joined import ReserveQueueJoined
from nexus.contracts.gen.events.reserve_queue_left import ReserveQueueLeft
from nexus.core.step import step
from nexus.core.world import World, load, save, state_hash


def timeout(n: int, seq: int = 100) -> Command:
    return SysQueueTimeoutCommand.model_validate(
        {
            "kind": "SYS_QUEUE_TIMEOUT",
            "source": "SYSTEM",
            "issuer": {"system": "queue-idle"},
            "target_tick": 1,
            "arrival_seq": seq,
            "correlation_id": f"idle{n}",
            "commander_id": cid(n),
        }
    )


def run(w: World, *commands: Command) -> list[Event]:
    """One tick with `commands` addressed to it."""
    tick = w.campaign.tick + 1
    return step(w, [c.model_copy(update={"target_tick": tick}) for c in commands])


def lefts(events: list[Event]) -> list[tuple[str, str]]:
    return [(e.commander_id, e.reason) for e in events if isinstance(e, ReserveQueueLeft)]


def test_serving_the_head_emits_slot_freed_before_the_spawn() -> None:
    w = full_world()
    w.remove(1)
    events = step(w, [])
    assert lefts(events) == [(cid(3), "SLOT_FREED")]
    assert [e.kind for e in events][:2] == ["ReserveQueueLeft", "UnitSpawned"]


def test_a_replacing_join_emits_replaced_then_joined_with_the_same_position() -> None:
    w = full_world()
    events = run(w, join(4, "RECON", arrival_seq=9))
    assert [e.kind for e in events] == ["ReserveQueueLeft", "ReserveQueueJoined"]
    assert lefts(events) == [(cid(4), "REPLACED")]
    assert queued(events) == [(cid(4), 2)] and queue_of(w) == [cid(3), cid(4), cid(5)]


def test_idle_timeout_removes_the_entry_and_keeps_the_others_in_order() -> None:
    w = full_world()
    events = run(w, timeout(4))
    assert lefts(events) == [(cid(4), "TIMEOUT")] and len(events) == 1
    assert queue_of(w) == [cid(3), cid(5)]


def test_timeout_for_a_commander_not_queued_is_ignored() -> None:
    w = full_world()
    assert run(w, timeout(1), timeout(9)) == []  # holds a slot / unknown
    assert queue_of(w) == [cid(3), cid(4), cid(5)]


def test_timeout_works_while_paused() -> None:
    w = full_world()
    w.campaign.clock_paused = True
    assert lefts(run(w, timeout(3))) == [(cid(3), "TIMEOUT")]


def test_dropped_entries_on_a_tombstoned_tick_leave_as_rejected() -> None:
    w = full_world()
    w.remove(1)
    w.remove(2)
    assert lefts(step(w, [], dropped=[])) == [(cid(3), "REJECTED"), (cid(4), "REJECTED")]


def test_timeout_replays_to_the_same_state() -> None:
    a, b = full_world(), full_world()
    run(a, timeout(4))
    run(b, timeout(4))
    assert state_hash(a) == state_hash(b) != state_hash(full_world())
    assert queue_of(load(save(a))) == [cid(3), cid(5)]


# Ops on a cap-2 world with five commanders: JOIN n, free the oldest slot, time out n.
OPS = st.one_of(
    st.tuples(st.just("join"), st.integers(1, 5)),
    st.tuples(st.just("free"), st.just(0)),
    st.tuples(st.just("timeout"), st.integers(1, 5)),
    st.tuples(st.just("logi"), st.integers(1, 5)),  # a truck JOIN to fob-n-w
    st.tuples(st.just("break"), st.integers(0, 1)),  # 1: trucks lose their route, 0: restored
    st.tuples(st.just("reload"), st.just(0)),  # save and load
)


@example(  # a queued truck fails its serve-time re-check: REJECTED
    [("join", 1), ("join", 2), ("logi", 3), ("break", 1), ("free", 0), ("reload", 0)]
)
@given(st.lists(OPS, max_size=40))
def test_a_counter_replayed_from_events_equals_the_queue_length(ops: list[tuple[str, int]]) -> None:
    w: World = capped()
    truck = CAP2.role_kind["LOGI"]
    broken = dataclasses.replace(CAP2, domain={**CAP2.domain, truck: "STATIC"})
    counter, seq = 0, 0
    for op, n in ops:
        seq += 1
        commands: list[Command] = []
        if op == "break":  # an entry queued as a truck then fails its re-check at serve time
            w.rules = broken if n else CAP2
        elif op == "reload":
            rules = w.rules
            w = load(save(w))
            w.rules = rules
        elif op == "logi":
            commands = [join(n, "LOGI", "fob-n-w", arrival_seq=seq)]
        elif op == "free":
            if len(w):
                w.remove(sorted(e.id for e in w.entities())[0])
        elif op == "join":
            commands = [join(n, arrival_seq=seq)]
        else:
            commands = [timeout(n, seq)]
        for e in run(w, *commands):
            counter += isinstance(e, ReserveQueueJoined)
            counter -= isinstance(e, ReserveQueueLeft)
        assert counter == len(w.reserve_queue)
