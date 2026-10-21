"""NX-021: the generated contract types validate the seed messages (CONTRACTS §3-7)."""

import pytest
from pydantic import TypeAdapter, ValidationError

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.common.envelope import ChatEnvelope
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.contracts.gen.wire.hello import Hello

COMMANDER = "0192f0c1-7a2b-7c3d-8e4f-0123456789ab"
COMMANDS: TypeAdapter[Command] = TypeAdapter(Command)
EVENTS: TypeAdapter[Event] = TypeAdapter(Event)

JOIN = {
    "kind": "JOIN",
    "source": "CHAT",
    "issuer": {"commander_id": COMMANDER},
    "target_tick": 11,
    "arrival_seq": 1,
    "correlation_id": "msg-1",
    "role": "STRIKE",
    "target": {"node_id": "west-airbase"},
    "hold": False,
}


def test_command_union_parses_join() -> None:
    cmd = COMMANDS.validate_python(JOIN)
    assert cmd.kind == "JOIN"
    assert cmd.role == "STRIKE"


def test_produced_objects_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python({**JOIN, "stance": "PRESS"})


def test_event_union_parses_unit_spawned() -> None:
    event = EVENTS.validate_python(
        {
            "kind": "UnitSpawned",
            "tick": 12,
            "event_seq": 1,
            "campaign_id": COMMANDER,
            "entity_id": 1,
            "unit_kind": "STRIKE_FIGHTER",
            "side": "COALITION",
            "owner_kind": "COMMANDER",
            "commander_id": COMMANDER,
            "callsign": "VIPER-27",
            "node_id": "west-airbase",
            "loadout": "FULL",
        }
    )
    assert isinstance(event, UnitSpawned)
    assert event.entity_id == 1


def test_envelope_rejects_over_length_text() -> None:
    with pytest.raises(ValidationError):
        ChatEnvelope.model_validate(
            {
                "platform": "TWITCH",
                "platform_user_id": "u1",
                "platform_message_id": "m1",
                "display_name": "viewer",
                "text": "x" * 301,
                "match_key": "x",
                "received_at": "2026-10-20T00:00:00Z",
                "platform_badges": [],
                "account_created_at": None,
            }
        )


def test_hello_requires_protocol_version_shape() -> None:
    with pytest.raises(ValidationError):
        Hello.model_validate(
            {
                "type": "Hello",
                "v": "one",
                "client_kind": "OVERLAY",
                "capability_token": "t",
                "last_tick": None,
            }
        )


COMMAND_REJECTED = {
    "kind": "CommandRejected",
    "tick": 12,
    "event_seq": 3,
    "campaign_id": COMMANDER,
    "arrival_seq": 5,
    "command_kind": "JOIN",
    "reason": "INTERNAL_ERROR",
    "commander_id": None,
}


def test_event_union_parses_command_rejected() -> None:
    event = EVENTS.validate_python(COMMAND_REJECTED)
    assert event.kind == "CommandRejected"
    assert event.reason == "INTERNAL_ERROR"


@pytest.mark.parametrize(
    "bad",
    [
        {"reason": "BANNED"},  # not emitted by any code yet, so not in RejectReason
        {"command_kind": "MOVE"},
        {"arrival_seq": 0},
        {"text": "free text"},  # SC-14: ids only
    ],
)
def test_command_rejected_rejects_bad_fields(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EVENTS.validate_python({**COMMAND_REJECTED, **bad})


QUEUE_JOINED = {
    "kind": "ReserveQueueJoined",
    "tick": 12,
    "event_seq": 4,
    "campaign_id": "0192f3a4-5b6c-7d8e-9f01-23456789abcd",
    "commander_id": COMMANDER,
    "position": 1,
}


def test_event_union_parses_reserve_queue_joined() -> None:
    event = EVENTS.validate_python(QUEUE_JOINED)
    assert event.kind == "ReserveQueueJoined"
    assert (event.commander_id, event.position) == (COMMANDER, 1)


@pytest.mark.parametrize(
    "bad",
    [
        {"position": 0},  # 1-based
        {"commander_id": None},  # only commanders queue
        {"commander_id": "viewer-1"},  # not a CommanderId
        {"reason": "LEFT"},  # ReserveQueueLeft's field, not this event's
    ],
)
def test_reserve_queue_joined_rejects_bad_fields(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EVENTS.validate_python({**QUEUE_JOINED, **bad})
