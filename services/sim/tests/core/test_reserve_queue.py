"""NX-122 part 3: the viewer-unit cap and the reserve queue (GAMEPLAY GP-3, §4a; STATE-MACHINES
§4.1 Reserve rows, §4.4 Paused JOIN, Q-ALN-26; SIM-CORE SC-6, SC-9, SC-11, SC-13, SC-14).

Runs on the shipped strait-1 config with a low cap (`max_viewer_units` 2) so a few JOINs reach it.
"""

import dataclasses
import os
import subprocess
import sys

from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter
from test_join import CAMPAIGN_ID, RULES, at_tick, cid, join, reasons

from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.reserve_queue_joined import ReserveQueueJoined
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.world import Campaign, Vec2, World, load, save, state_hash

CAP2 = dataclasses.replace(RULES, max_viewer_units=2)


def capped(rules: Rules = CAP2) -> World:
    return World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"), rules)


def queued(events: list[Event]) -> list[tuple[str, int]]:
    return [(e.commander_id, e.position) for e in events if isinstance(e, ReserveQueueJoined)]


def spawned(events: list[Event]) -> list[str | None]:
    return [e.commander_id for e in events if isinstance(e, UnitSpawned)]


def queue_of(w: World) -> list[str]:
    return [c.issuer.commander_id for c in w.reserve_queue]


def full_world() -> World:
    """Commanders 1 and 2 hold both slots; 3, 4 and 5 are queued in that order."""
    w = capped()
    step(w, [join(n, arrival_seq=n) for n in range(1, 6)])
    return w


def test_cap_reached_queues_in_arrival_order() -> None:
    w = capped()
    events = step(w, [join(n, arrival_seq=n) for n in range(1, 6)])
    assert [TypeAdapter(Event).validate_python(e.model_dump()) for e in events] == events
    assert spawned(events) == [cid(1), cid(2)]
    assert events[2] == ReserveQueueJoined(
        kind="ReserveQueueJoined",
        tick=1,
        event_seq=3,
        campaign_id=CAMPAIGN_ID,
        commander_id=cid(3),
        position=1,
    )
    assert queued(events) == [(cid(3), 1), (cid(4), 2), (cid(5), 3)]
    assert (len(w), queue_of(w)) == (2, [cid(3), cid(4), cid(5)])
    assert queued(step(w, [])) == [] and len(w) == 2  # no slot frees: nobody is served


def test_a_freed_slot_serves_the_head_in_lifecycle() -> None:
    w = full_world()
    w.remove(1)  # e.g. idle retire (NX-324): the slot frees with no respawn delay
    events = at_tick(w, 2)
    assert spawned(events) == [cid(3)]
    assert (events[0].tick, queue_of(w)) == (2, [cid(4), cid(5)])
    (unit,) = [e for e in w.entities() if e.commander_id == cid(3)]
    assert (unit.kind, unit.last_node) == ("STRIKE_FIGHTER", "haven")  # spawned as a direct JOIN


def test_a_loss_frees_the_slot_for_the_queue_not_the_loser() -> None:
    w = full_world()
    w.remove(1)
    w.record_loss(cid(1))  # destroyed (NX-124): commander 1 waits out the delay
    assert spawned(at_tick(w, 2)) == [cid(3)]
    assert reasons(at_tick(w, 3, join(1))) == ["RESPAWN_COOLDOWN"]


def test_a_join_with_a_free_slot_still_queues_behind_the_queue() -> None:
    # Strict FIFO (U-4): commands apply before lifecycle serves, so a newcomer must not jump it.
    w = full_world()
    w.remove(1)
    events = at_tick(w, 2, join(6))
    assert queued(events) == [(cid(6), 4)]
    assert spawned(events) == [cid(3)]
    assert queue_of(w) == [cid(4), cid(5), cid(6)]


def test_paused_join_queues_even_with_a_free_slot_and_spawns_fifo_after_resume() -> None:
    w = capped(RULES)  # cap 500: every slot is free
    w.campaign.clock_paused = True
    events = step(w, [join(2, arrival_seq=1), join(1, "LOGI", "fob-n-w", arrival_seq=2)])
    assert queued(events) == [(cid(2), 1), (cid(1), 2)]
    assert len(w) == 0
    assert spawned(at_tick(w, 30)) == []  # nothing spawns while paused (U-8)
    w.campaign.clock_paused = False
    events = at_tick(w, 31)
    assert spawned(events) == [cid(2), cid(1)]
    assert [e.tick for e in events] == [31, 31]
    assert queue_of(w) == []


def test_paused_join_with_a_live_unit_is_rejected() -> None:
    w = capped()
    step(w, [join(1)])
    w.campaign.clock_paused = True
    assert reasons(at_tick(w, 2, join(1, "LOGI"))) == ["CAMPAIGN_PAUSED"]
    assert queue_of(w) == []


def test_paused_join_in_cooldown_is_rejected_not_queued() -> None:
    # The delay is frozen while paused (SC-11), so it cannot run out in the queue.
    w = capped()
    w.record_loss(cid(1))
    w.campaign.clock_paused = True
    assert reasons(step(w, [join(1)])) == ["RESPAWN_COOLDOWN"]
    assert queue_of(w) == []


def test_only_commander_units_take_viewer_slots() -> None:
    w = capped()
    for _ in range(3):  # AI units, more than the cap
        w.spawn("GARRISON_INFANTRY", "COALITION", "AI_GARRISON", Vec2(0, 0))
    events = step(w, [join(n, arrival_seq=n) for n in range(1, 4)])
    assert spawned(events) == [cid(1), cid(2)]
    assert queued(events) == [(cid(3), 1)]


def test_a_second_join_while_queued_replaces_the_entry_and_keeps_its_place() -> None:
    w = full_world()
    events = at_tick(w, 2, join(3, "RECON", "fob-s-e", correlation_id="again"))
    assert queued(events) == [(cid(3), 1)]
    assert queue_of(w) == [cid(3), cid(4), cid(5)]
    w.remove(1)
    assert spawned(at_tick(w, 3)) == [cid(3)]
    (unit,) = [e for e in w.entities() if e.commander_id == cid(3)]
    assert (unit.kind, unit.path) == ("RECON_UAV", ["fob-s-e"])  # the newer request


def test_an_invalid_second_join_keeps_the_old_entry() -> None:
    w = full_world()
    assert reasons(at_tick(w, 2, join(3, "STRIKE", "nowhere"))) == ["NODE_UNKNOWN"]
    assert w.reserve_queue[0].role == "STRIKE" and w.reserve_queue[0].target is None


def test_a_full_queue_rejects_newcomers_but_not_replacements() -> None:
    w = capped(dataclasses.replace(CAP2, reserve_queue_max=2))
    events = step(w, [join(n, arrival_seq=n) for n in range(1, 6)])
    assert queued(events) == [(cid(3), 1), (cid(4), 2)]
    assert reasons(events) == ["RESERVE_QUEUE_FULL"]
    rejected = [e for e in events if isinstance(e, CommandRejected)]
    assert (rejected[0].commander_id, rejected[0].arrival_seq) == (cid(5), 5)
    assert queued(at_tick(w, 2, join(4, "LOGI"))) == [(cid(4), 2)]


def test_an_entry_invalid_at_serve_time_is_rejected_and_the_next_is_served() -> None:
    # Commander 3 queued a truck to fob-n-w. Before it is served the trucks lose that route (a
    # stand-in for a destroyed bridge, NX-124): it is rejected with the reason a direct JOIN gets.
    w = capped()
    step(w, [join(1), join(2), join(3, "LOGI", "fob-n-w"), join(4)])
    truck = CAP2.role_kind["LOGI"]
    w.rules = dataclasses.replace(CAP2, domain={**CAP2.domain, truck: "STATIC"})
    w.remove(1)
    events = at_tick(w, 2)
    rejected = events[0]
    assert isinstance(rejected, CommandRejected) and isinstance(events[1], UnitSpawned)
    assert (rejected.reason, rejected.commander_id, rejected.arrival_seq) == (
        "NODE_INVALID_FOR_UNIT",
        cid(3),
        3,
    )
    assert spawned(events) == [cid(4)]
    assert queue_of(w) == []


MIXED = [
    join(1, "STRIKE", "east-airbase"),
    join(2, "LOGI", "fob-s-w"),
    join(3, "RECON"),
    join(1, "RECON"),  # in sortie
    join(4, "NAVY"),  # unknown role
    join(5, "LOGI", "fob-n-w"),
    join(3, "STRIKE", "nowhere"),
    join(6, "RECON", hold=True),
    join(5, "STRIKE"),
]


@given(st.permutations(range(len(MIXED))))
def test_sc6_list_order_does_not_matter_at_the_cap(order: list[int]) -> None:
    stamped = [c.model_copy(update={"arrival_seq": i}) for i, c in enumerate(MIXED, 1)]
    a, b = capped(), capped()
    assert step(a, stamped) == step(b, [stamped[i] for i in order])
    assert state_hash(a) == state_hash(b)
    assert queue_of(a) == queue_of(b) == [cid(3), cid(5), cid(6)]


def queue_world() -> World:
    w = capped()
    step(w, [c.model_copy(update={"arrival_seq": i}) for i, c in enumerate(MIXED, 1)])
    return w


def test_snapshot_round_trip_keeps_the_queue() -> None:
    w = queue_world()
    loaded = load(save(w))
    assert state_hash(loaded) == state_hash(w)
    assert loaded.reserve_queue == w.reserve_queue
    loaded.rules = CAP2  # not in snapshots (SIM-CORE §4); the runtime re-attaches it
    w.remove(1)
    loaded.remove(1)
    assert at_tick(loaded, 2) == at_tick(w, 2)
    assert state_hash(loaded) == state_hash(w)
    # The queue is world state: serving it changed the hash.
    assert state_hash(w) != state_hash(load(save(queue_world())))


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_reserve_queue import queue_world\n"
    "from nexus.core.world import state_hash; print(state_hash(queue_world()))"
)


def test_queue_state_hash_is_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert run("1") == run("2") == state_hash(queue_world())


def test_a_tombstoned_tick_drops_the_entries_it_would_serve() -> None:
    # SC-8: one entry per free slot (two here), in queue order; the rest stay queued.
    w = full_world()
    w.remove(1)
    w.remove(2)
    events = step(w, [], dropped=[])
    dropped = [
        (e.reason, e.commander_id, e.arrival_seq) for e in events if isinstance(e, CommandRejected)
    ]
    assert dropped == [("INTERNAL_ERROR", cid(3), 3), ("INTERNAL_ERROR", cid(4), 4)]
    assert (len(events), len(w), queue_of(w)) == (2, 0, [cid(5)])


def test_a_tombstoned_tick_drops_at_least_the_head_and_nothing_while_paused() -> None:
    # No free slot: the slot the crashed tick freed may have come from a dropped command.
    w = full_world()
    assert reasons(step(w, [], dropped=[])) == ["INTERNAL_ERROR"]
    assert queue_of(w) == [cid(4), cid(5)]
    w.campaign.clock_paused = True  # nothing is served while paused, so nothing can crash
    assert step(w, [], dropped=[]) == []
    assert queue_of(w) == [cid(4), cid(5)]
