"""NX-370: SYS_SET_CALLSIGN (CONTRACTS §5.2, §6; IDENTITY §2; SIM-CORE SC-6, SC-11; Q-SIM-39)."""

import dataclasses

import msgpack
import pytest
from pydantic import TypeAdapter, ValidationError
from test_join import CAMPAIGN_ID, RULES, cid, join

from nexus.contracts.gen.commands.command import Command
from nexus.contracts.gen.commands.sys_set_callsign import SysSetCallsignCommand
from nexus.contracts.gen.events.callsign_changed import CallsignChanged
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.step import step
from nexus.core.world import Campaign, World, load, save, state_hash


def world(cap: int = 500) -> World:
    return World.new(
        Campaign(CAMPAIGN_ID, 1, "cfg-test"), dataclasses.replace(RULES, max_viewer_units=cap)
    )


def setcs(n: int, callsign: str, kind: str = "CUSTOM", seq: int = 1, tick: int = 1) -> Command:
    return SysSetCallsignCommand.model_validate(
        {
            "kind": "SYS_SET_CALLSIGN",
            "source": "SYSTEM",
            "issuer": {"system": "identity"},
            "target_tick": tick,
            "arrival_seq": seq,
            "correlation_id": f"cs{n}",
            "commander_id": cid(n),
            "callsign": callsign,
            "callsign_kind": kind,
        }
    )


def callsigns(events: list[Event]) -> list[str | None]:
    return [e.callsign for e in events if isinstance(e, UnitSpawned)]


def test_set_then_join_spawns_with_the_callsign_and_emits_the_event() -> None:
    w = world()
    events = step(w, [setcs(1, "VIPER-07", "GENERATED"), join(1, arrival_seq=2)])
    assert [TypeAdapter(Event).validate_python(e.model_dump()) for e in events] == events
    assert events[0] == CallsignChanged(
        kind="CallsignChanged",
        tick=1,
        event_seq=1,
        campaign_id=CAMPAIGN_ID,
        commander_id=cid(1),
        callsign="VIPER-07",
        callsign_kind="GENERATED",
    )
    assert callsigns(events) == ["VIPER-07"]
    assert w.get(1).callsign == "VIPER-07"


def test_join_before_set_in_one_tick_has_none_then_the_unit_updates() -> None:
    # SC-6: arrival_seq decides, so the same two commands give a different result.
    w = world()
    events = step(w, [join(1, arrival_seq=1), setcs(1, "VIPER-07", seq=2)])
    assert callsigns(events) == [None]
    assert w.get(1).callsign == "VIPER-07"  # the set reached the live unit


def test_a_change_reaches_a_live_unit_and_only_that_commanders() -> None:
    w = world()
    step(w, [join(1, arrival_seq=1), join(2, arrival_seq=2), setcs(1, "OLD-01", seq=3)])
    ai = w.spawn("GARRISON_INFANTRY", "COALITION", "AI_GARRISON", w.get(1).pos, hp=None)
    events = step(w, [setcs(1, "NEW-02", tick=2)])
    assert [type(e).__name__ for e in events] == ["CallsignChanged"]
    assert (w.get(1).callsign, w.get(2).callsign, ai.callsign) == ("NEW-02", None, None)
    assert w.callsigns == {cid(1): "NEW-02"}


def test_a_queued_join_served_after_a_change_uses_the_newest() -> None:
    w = world(cap=1)
    step(w, [join(1, arrival_seq=1), join(2, arrival_seq=2), setcs(2, "OLD-01", seq=3)])
    assert len(w.reserve_queue) == 1
    step(w, [setcs(2, "NEW-02", tick=2)])
    w.remove(1)
    assert callsigns(step(w, [])) == ["NEW-02"]


def test_it_applies_while_paused() -> None:
    w = world()
    w.campaign.clock_paused = True
    events = step(w, [setcs(1, "VIPER-07")])
    assert [type(e).__name__ for e in events] == ["CallsignChanged"]
    assert w.callsigns == {cid(1): "VIPER-07"}


@pytest.mark.parametrize("callsign", ["", "ab-12", "A", "WAY-TOO-LONG-1", "A_B-12", "1ABC"])
def test_the_schema_rejects_a_bad_callsign(callsign: str) -> None:
    with pytest.raises(ValidationError):
        setcs(1, callsign)


def test_a_tombstone_value_is_a_valid_callsign() -> None:
    (event,) = step(world(), [setcs(1, "X-7KQ2", "TOMBSTONE")])
    assert isinstance(event, CallsignChanged) and event.callsign_kind == "TOMBSTONE"


def test_snapshot_round_trip_and_hash_cover_the_callsigns() -> None:
    w = world()
    step(w, [setcs(2, "BRAVO-02"), setcs(1, "ALPHA-01", seq=2)])
    loaded = load(save(w))
    assert loaded.callsigns == {cid(1): "ALPHA-01", cid(2): "BRAVO-02"}
    assert state_hash(loaded) == state_hash(w) != state_hash(world())
    other = world()  # same entries, opposite insertion order: equal hash (sorted canonical form)
    step(other, [setcs(1, "ALPHA-01"), setcs(2, "BRAVO-02", seq=2)])
    assert list(other.callsigns) != list(w.callsigns)
    assert state_hash(other) == state_hash(w)


def test_load_rejects_a_bad_callsign_map() -> None:
    raw = msgpack.unpackb(save(world()), raw=False)
    bad_maps: list[object] = [{cid(1): "bad"}, {cid(1): None}, [], None]
    for bad in bad_maps:
        with pytest.raises(ValueError, match=r"callsign|commander_id"):
            load(msgpack.packb({**raw, "callsigns": bad}, use_bin_type=True))
