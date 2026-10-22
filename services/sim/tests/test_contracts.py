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


DESTROYED = {
    "kind": "UnitDestroyed",
    "tick": 30,
    "event_seq": 9,
    "campaign_id": "0192f3a4-5b6c-7d8e-9f01-23456789abcd",
    "entity_id": 4,
    "killer_id": None,
    "assist_ids": [],
    "side": "COALITION",
}


def test_event_union_parses_unit_destroyed() -> None:
    event = EVENTS.validate_python(DESTROYED)
    assert event.kind == "UnitDestroyed"
    assert (event.entity_id, event.killer_id, event.assist_ids) == (4, None, [])
    with_killer = EVENTS.validate_python({**DESTROYED, "killer_id": 7, "assist_ids": [3, 2]})
    assert with_killer.kind == "UnitDestroyed"
    assert with_killer.assist_ids == [3, 2]  # a list: order kept as produced


@pytest.mark.parametrize(
    "bad",
    [
        {"entity_id": 0},  # ids start at 1
        {"side": "NEUTRAL"},  # a unit's side
        {"assist_ids": list(range(1, 34))},  # maxItems 32
        {"commander_id": None},  # not a field of this event
    ],
)
def test_unit_destroyed_rejects_bad_fields(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EVENTS.validate_python({**DESTROYED, **bad})


_BASE = {"tick": 30, "event_seq": 9, "campaign_id": "0192f3a4-5b6c-7d8e-9f01-23456789abcd"}
FIRED = {**_BASE, "kind": "WeaponFired", "shooter_id": 4, "target_id": 7,
         "target_node_id": None, "weapon": "SAM", "impact_tick": 52}  # fmt: skip
IMPACT = {**_BASE, "kind": "WeaponImpact", "shooter_id": 4, "target_id": 7,
          "target_node_id": None, "weapon": "SAM", "hit": True}  # fmt: skip
STATE_CHANGED = {**_BASE, "kind": "UnitDamageStateChanged", "entity_id": 7, "from": "HEALTHY",
                 "to": "DAMAGED"}  # fmt: skip
DESPAWNED = {**_BASE, "kind": "UnitDespawned", "entity_id": 7, "reason": "WRECKED"}
FIRED_AT_NODE = {**FIRED, "target_id": None, "target_node_id": "east-airbase"}
DEFENSES_DOWN = {**_BASE, "kind": "NodeDefensesDown", "node_id": "east-airbase", "owner": "ENEMY"}
DEFENSES_RESTORED = {**DEFENSES_DOWN, "kind": "NodeDefensesRestored"}


@pytest.mark.parametrize(
    "good",
    [FIRED, IMPACT, STATE_CHANGED, DESPAWNED, FIRED_AT_NODE, DEFENSES_DOWN, DEFENSES_RESTORED],
)
def test_combat_events_parse_through_the_event_union(good: dict[str, object]) -> None:
    event = EVENTS.validate_python(good)
    assert event.kind == good["kind"]
    assert event.model_dump(by_alias=True, mode="json") == good  # `from` keeps its wire name


@pytest.mark.parametrize(
    ("event", "bad"),
    [
        (FIRED, {"impact_tick": 0}),  # a campaign-clock tick, at least 1
        (FIRED, {"weapon": "sam"}),  # a WeaponId
        (FIRED, {"hit": True}),  # the outcome is not known at fire time (Q-GP-12)
        (IMPACT, {"hit": "maybe"}),
        (IMPACT, {"impact_tick": 5}),
        (STATE_CHANGED, {"to": "DESTROYED"}),  # a lifecycle event, not a damage state
        (STATE_CHANGED, {"from": "BROKEN"}),
        (DESPAWNED, {"reason": "IDLE"}),  # no producer yet (rule 6a)
        (DESPAWNED, {"entity_id": 0}),
        (FIRED, {"target_node_id": "East Airbase"}),  # a NodeId slug
        (FIRED, {"target_node_id": None, "target_id": 0}),
        (DEFENSES_DOWN, {"owner": "RED"}),
        (DEFENSES_DOWN, {"hp": 0}),  # no per-hit or hp field: the HUD reads NodeView.hp_pct
        (DEFENSES_RESTORED, {"node_id": "Bad Node"}),
    ],
)
def test_combat_events_reject_bad_fields(event: dict[str, object], bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EVENTS.validate_python({**event, **bad})


JOB_CREATED = {**_BASE, "kind": "JobCreated", "job_id": 3, "side": "COALITION",
               "job_kind": "SCOUT", "node_id": None, "blob_id": "270-493", "slots": 1,
               "depends_on_job_id": None}  # fmt: skip
JOB_CLAIMED = {**_BASE, "kind": "JobClaimed", "job_id": 3, "entity_id": 12}
JOB_RELEASED = {**JOB_CLAIMED, "kind": "JobReleased"}
_PARTICIPANT = {"entity_id": 12, "commander_id": COMMANDER, "auto": False}
JOB_DONE = {**_BASE, "kind": "JobDone", "job_id": 3, "participants": [_PARTICIPANT]}
JOB_FAILED = {**_BASE, "kind": "JobFailed", "job_id": 3}
JOB_EXPIRED = {**JOB_FAILED, "kind": "JobExpired"}


@pytest.mark.parametrize(
    "good",
    [JOB_CREATED, JOB_CLAIMED, JOB_RELEASED, JOB_DONE, JOB_FAILED, JOB_EXPIRED],
)
def test_job_events_parse_through_the_event_union(good: dict[str, object]) -> None:
    event = EVENTS.validate_python(good)
    assert event.kind == good["kind"] and event.model_dump(mode="json") == good


@pytest.mark.parametrize(
    ("event", "bad"),
    [
        (JOB_CREATED, {"job_kind": "ESCORT_CONVOY"}),  # no producer yet (rule 6a)
        (JOB_CREATED, {"blob_id": "7"}),  # <refresh_tick>-<cell_index>
        (JOB_CREATED, {"node_id": "West Airbase"}),
        (JOB_CREATED, {"slots": 0}),
        (JOB_CREATED, {"job_id": 0}),
        (JOB_CREATED, {"sector_id": None}),  # joins with the sector scout
        (JOB_CLAIMED, {"entity_id": 0}),
        (
            JOB_DONE,
            {"participants": [{"entity_id": 12, "commander_id": COMMANDER}]},
        ),  # auto missing
        (JOB_DONE, {"participants": [{"entity_id": 12, "commander_id": "x", "auto": False}]}),
        (JOB_FAILED, {"reason": "NODE_LOST"}),
    ],
)
def test_job_events_reject_bad_fields(event: dict[str, object], bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EVENTS.validate_python({**event, **bad})


SET_CALLSIGN = {
    "kind": "SYS_SET_CALLSIGN",
    "source": "SYSTEM",
    "issuer": {"system": "identity"},
    "target_tick": 11,
    "arrival_seq": 1,
    "correlation_id": "approval-1",
    "commander_id": COMMANDER,
    "callsign": "VIPER-07",
    "callsign_kind": "CUSTOM",
}


def test_command_union_parses_sys_set_callsign() -> None:
    assert COMMANDS.validate_python(SET_CALLSIGN).kind == "SYS_SET_CALLSIGN"


@pytest.mark.parametrize(
    "bad",
    [
        {"callsign": "viper"},
        {"callsign_kind": "OTHER"},
        {"source": "CHAT"},
        {"issuer": {"commander_id": COMMANDER}},
        {"extra": 1},
    ],
)
def test_sys_set_callsign_rejects_bad_fields(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python({**SET_CALLSIGN, **bad})
