"""Kernel step tests (NX-102, SIM-CORE SC-1, SC-6, SC-7, SC-13, SC-14)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.rng import RngStream
from nexus.core.step import SYSTEMS, Handler, step
from nexus.core.world import Campaign, Vec2, World, state_hash

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


def new_world() -> World:
    return World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"))


def spawn_handler(world: World, command: Command, out: list[Event]) -> None:
    """Test stand-in for a real handler: spawns one unit whose hp draws from the spawn stream."""
    hp = world.rng.stream(RngStream.SPAWN).randint(1, 100)
    e = world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(command.arrival_seq, 0), hp=hp)
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


STUB: dict[str, Handler] = {"JOIN": spawn_handler}


def test_system_order_is_sc13() -> None:
    assert [name for name, _ in SYSTEMS] == [
        "apply_commands",
        "director",
        "movement",
        "sensing",
        "combat",
        "logistics_capture",
        "objectives",
        "lifecycle",
    ]


@given(st.permutations(range(1, 9)))
def test_shuffled_commands_give_same_result(order: list[int]) -> None:
    def run(seqs: list[int]) -> tuple[str, list[Event], list[float]]:
        w = new_world()
        events = step(w, [make_join(arrival_seq=s) for s in seqs], STUB)
        return state_hash(w), events, [e.pos.x for e in w.entities()]

    h, events, xs = run(order)
    assert run(sorted(order)) == (h, events, xs)
    assert xs == [1, 2, 3, 4, 5, 6, 7, 8]  # applied in arrival_seq order


def test_unhandled_kind_is_rejected_not_raised() -> None:
    w = new_world()
    events = step(w, [make_join(arrival_seq=7), make_join(arrival_seq=3)], {})
    assert [TypeAdapter(Event).validate_python(e.model_dump()) for e in events] == events
    rejected = [e for e in events if isinstance(e, CommandRejected)]
    assert len(rejected) == len(events)
    assert [(e.arrival_seq, e.event_seq, e.tick) for e in rejected] == [(3, 1, 1), (7, 2, 1)]
    for e in rejected:
        assert (e.command_kind, e.reason, e.commander_id) == ("JOIN", "INTERNAL_ERROR", COMMANDER)
    assert len(w) == 0
    assert step(w, [make_join(target_tick=2, arrival_seq=8)], {})[0].event_seq == 3


def test_dropped_commands_are_rejected_in_arrival_order_and_not_applied() -> None:
    # SC-8: a tombstoned tick's commands are dropped, even ones a handler would accept.
    w = new_world()
    events = step(w, [], STUB, dropped=[make_join(arrival_seq=9), make_join(arrival_seq=4)])
    rejected = [e for e in events if isinstance(e, CommandRejected)]
    assert len(rejected) == len(events)
    assert [(e.arrival_seq, e.event_seq, e.reason) for e in rejected] == [
        (4, 1, "INTERNAL_ERROR"),
        (9, 2, "INTERNAL_ERROR"),
    ]
    assert len(w) == 0
    assert w.campaign.tick == 1
    with pytest.raises(ValueError, match="do not target tick 2"):
        step(w, [], STUB, dropped=[make_join(arrival_seq=10)])


def test_tick_advances_by_one_per_step() -> None:
    w = new_world()
    for expected in (1, 2, 3):
        assert step(w, []) == []
        assert w.campaign.tick == expected


def test_wrong_target_tick_raises() -> None:
    w = new_world()
    for bad in (0, 2):
        with pytest.raises(ValueError, match="do not target tick 1"):
            step(w, [make_join(target_tick=bad)])
    assert w.campaign.tick == 0


def golden_run() -> str:
    w = new_world()
    seq = 1
    for tick in range(1, 11):
        commands = [make_join(target_tick=tick, arrival_seq=seq + i) for i in range(tick % 3)]
        seq += len(commands)
        step(w, commands, STUB)
    assert w.campaign.tick == 10
    assert len(w) == 10  # tick % 3 commands at ticks 1..10: 1+2+0+1+2+0+1+2+0+1
    return state_hash(w)


GOLDEN = "466c71ad1d625bbca2392dd970abcfc671dad5695483dc1d232b91a81b261b82"


def test_golden_ten_steps_seed_12345() -> None:
    # Pinned by running this implementation once (NX-102; re-pinned NX-121: entity encoding v2;
    # NX-122: world encoding v3 adds respawn_left; v4 adds reserve_queue; NX-368: v5 adds state,
    # fuel and orbit; NX-370: v6 adds callsigns; NX-150: v7 adds contacts; v8 adds markers and
    # facility fields; v9 adds painted, blobs and sigint_age).
    # A change here breaks every recorded replay hash: needs a `golden-update` reason.
    assert golden_run() == GOLDEN
    assert golden_run() == golden_run()
