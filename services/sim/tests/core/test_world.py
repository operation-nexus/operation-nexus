"""World model, canonical state_hash and snapshot tests (NX-101, SIM-CORE SC-4 / SC-9, ADR-0002)."""

import os
import subprocess
import sys
from typing import Any

import msgpack
import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.core import world as world_mod
from nexus.core.rng import RngStream
from nexus.core.world import Campaign, Vec2, World, load, save, state_hash, to_canonical

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"


QUEUED = JoinCommand.model_validate(
    {
        "kind": "JOIN",
        "source": "CHAT",
        "issuer": {"commander_id": "0192f3a4-5b6c-7d8e-9f01-000000000003"},
        "target_tick": 9,
        "arrival_seq": 41,
        "correlation_id": "m41",
        "role": "LOGI",
        "target": {"node_id": "fob-n-w"},
        "hold": False,
    }
)


def golden_world() -> World:
    w = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"))
    fighter = w.spawn(
        "STRIKE_FIGHTER",
        "COALITION",
        "COMMANDER",
        Vec2(1000.25, 2000.5),
        commander_id="0192f3a4-5b6c-7d8e-9f01-000000000001",
        callsign="VIPER-01",
        vel=Vec2(250.0, 0.0),
        hp=100,
    )
    w.spawn("GARRISON_INFANTRY", "COALITION", "AI_GARRISON", Vec2(-5.0, 7.125), hp=40)
    # int -25 on purpose: ints must encode as floats like any other coordinate.
    armor = w.spawn(
        "ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(150e3, 80e3), vel=Vec2(-25, 3.5), hp=200
    )
    fighter.path = [Vec2(5000.0004, 2000.5), "west-airbase"]  # NX-121: Vec2 and node waypoints
    fighter.state, fighter.fuel, fighter.orbit = "ON_STATION", 1234.25, Vec2(900.5, 2000.5)
    armor.path, armor.last_node = ["east-airbase"], "cross-n"
    w.respawn_left["0192f3a4-5b6c-7d8e-9f01-000000000002"] = 7  # NX-122: per-commander state
    w.reserve_queue.append(QUEUED)  # NX-122 part 3: the reserve queue
    return w


def test_golden_state_hash_seed_12345() -> None:
    # Pinned by running this implementation once (NX-101; re-pinned NX-121: path, last_node, v2;
    # NX-122: respawn_left, v3; NX-122 part 3: reserve_queue, v4; NX-368: state, fuel, orbit, v5;
    # NX-370: callsigns, v6).
    # A change here breaks every recorded replay hash: needs a `golden-update` reason.
    assert (
        state_hash(golden_world())
        == "31311eb9c0f15f7b0663577096296791d64fc80c6dfab479e4d8032f968e7dfc"
    )
    e = to_canonical(golden_world(), quantize=True)["entities"][0]
    assert e["pos"] == [1000250, 2000500]  # mm
    assert e["vel"] == [250000, 0]  # mm/s
    assert e["path"] == [[5000000, 2000500], "west-airbase"]  # waypoints in mm too
    assert (e["state"], e["fuel"], e["orbit"]) == ("ON_STATION", 1234250000, [900500, 2000500])
    assert to_canonical(golden_world(), quantize=True)["entities"][1]["fuel"] is None
    assert list(e) == sorted(e)


@given(
    ops=st.lists(st.one_of(st.just("spawn"), st.integers(min_value=0, max_value=30)), max_size=60)
)
def test_ids_sequential_never_reused_and_iterated_in_order(ops: list[Any]) -> None:
    w = World.new(Campaign(CAMPAIGN_ID, 1, "c"))
    live: list[int] = []
    issued = 0
    for op in ops:
        if op == "spawn":
            issued += 1
            assert w.spawn("RECON_UAV", "COALITION", "COMMANDER", Vec2(0, 0), hp=1).id == issued
            live.append(issued)
        elif live:
            victim = live.pop(op % len(live))
            w.remove(victim)
            with pytest.raises(KeyError):
                w.get(victim)
    assert [e.id for e in w.entities()] == sorted(live)
    assert len(w) == len(live)
    assert [w.next_event_seq() for _ in range(3)] == [1, 2, 3]  # SC-14: starts at 1


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf"), 1e30, 10**400, True, "1"]
)
def test_vec2_rejects_non_finite_huge_and_non_numbers(bad: Any) -> None:
    with pytest.raises(ValueError):
        Vec2(bad, 0.0)
    with pytest.raises(ValueError):
        Vec2(0.0, bad)


finite = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False)
vecs = st.builds(Vec2, finite, finite)
_KINDS: list[tuple[UnitKind, Side, OwnerKind]] = [
    ("LOGI_TRUCK", "COALITION", "COMMANDER"),
    ("RADAR_SITE", "ENEMY", "AI_GARRISON"),
]
kinds = st.sampled_from(_KINDS)
fuels = st.floats(min_value=0.0, max_value=1e6, allow_nan=False)
entity_args = st.tuples(kinds, vecs, vecs, st.integers(0, 1000), st.sampled_from([None, "HAWK-07"]))


@st.composite
def worlds(draw: st.DrawFn) -> World:
    seed, tick = draw(st.integers(0, 2**64 - 1)), draw(st.integers(0, 10**9))
    w = World.new(Campaign(CAMPAIGN_ID, seed, "c", tick, draw(st.booleans())))
    for (kind, side, owner), pos, vel, hp, callsign in draw(st.lists(entity_args, max_size=8)):
        e = w.spawn(kind, side, owner, pos, vel=vel, hp=hp, callsign=callsign)
        if draw(st.booleans()):  # an aircraft's state (NX-368)
            e.state, e.fuel = draw(st.sampled_from(world_mod._UNIT_STATES)), draw(fuels)
            e.orbit = draw(vecs) if e.state == "ON_STATION" else None
    for _ in range(draw(st.integers(min_value=0, max_value=5))):
        w.rng.stream(draw(st.sampled_from(list(RngStream)))).next_u64()
    if len(w) and draw(st.booleans()):
        w.remove(next(w.entities()).id)
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        w.next_event_seq()
    for n in draw(st.lists(st.integers(10, 99), unique=True, max_size=3)):  # one entry each (U-4)
        issuer = {"commander_id": f"0192f3a4-5b6c-7d8e-9f01-0000000000{n}"}
        w.reserve_queue.append(QUEUED.model_validate({**QUEUED.model_dump(), "issuer": issuer}))
    return w


@given(w=worlds())
def test_snapshot_round_trip_is_lossless(w: World) -> None:
    restored = load(save(w))
    assert state_hash(restored) == state_hash(w)
    assert to_canonical(restored, quantize=False) == to_canonical(w, quantize=False)
    assert restored.rng.stream("combat").next_u64() == w.rng.stream("combat").next_u64()


def _changes_hash(mutate: Any) -> bool:
    w = golden_world()
    before = state_hash(w)
    mutate(w)
    return state_hash(w) != before


def test_hash_tracks_state_at_mm_resolution() -> None:
    assert _changes_hash(lambda w: setattr(w.get(2), "hp", 39))
    assert _changes_hash(lambda w: setattr(w.get(2), "pos", Vec2(-5.0, 7.126)))
    assert _changes_hash(lambda w: setattr(w.campaign, "tick", 1))
    assert _changes_hash(lambda w: w.rng.stream("spawn").next_u64())
    assert _changes_hash(lambda w: w.remove(3))
    # Quantization: sub-millimetre moves do not change the hash.
    assert not _changes_hash(lambda w: setattr(w.get(2), "pos", Vec2(-5.0003, 7.1253)))
    assert not _changes_hash(lambda w: setattr(w.get(3), "vel", Vec2(-25.0002, 3.5)))
    # fuel at ADR-0002's 1e-6 step (NX-368)
    assert _changes_hash(lambda w: setattr(w.get(1), "fuel", 1234.250002))
    assert not _changes_hash(lambda w: setattr(w.get(1), "fuel", 1234.2500004))
    assert _changes_hash(lambda w: setattr(w.get(1), "state", "RTB"))


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_world import golden_world\n"
    "from nexus.core.world import state_hash; print(state_hash(golden_world()))"
)


def test_cross_process_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert run("1") == run("2") == state_hash(golden_world())


def _resave(mutate: Any) -> bytes:
    data = msgpack.unpackb(save(golden_world()))
    mutate(data)
    return msgpack.packb(data, use_bin_type=True)  # type: ignore[no-any-return]  # untyped lib


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        save(golden_world()) + b"\x00",
        msgpack.packb([1, 2]),
        _resave(lambda d: d.update(v=1)),
        _resave(lambda d: d.update(extra=1)),
        _resave(lambda d: d["entities"][0].update(kind="FACTORY")),
        _resave(lambda d: d["entities"][0].update(hp="100")),
        _resave(lambda d: d["entities"][0].update(hp=True)),
        _resave(lambda d: d["entities"][0].update(pos=[1e30, 0.0])),
        _resave(lambda d: d["entities"][0].update(pos=[float("nan"), 0.0])),
        _resave(lambda d: d["entities"][0].pop("callsign")),
        _resave(lambda d: d["entities"][0].update(path="west-airbase")),
        _resave(lambda d: d["entities"][0].update(path=[7])),
        _resave(lambda d: d["entities"][0].update(last_node=7)),
        _resave(lambda d: d["entities"][0].update(state="HOLDING")),  # not in code yet
        _resave(lambda d: d["entities"][0].update(fuel=-1.0)),
        _resave(lambda d: d["entities"][0].update(fuel=float("nan"))),
        _resave(lambda d: d["entities"][0].update(fuel=12)),  # always a float
        _resave(lambda d: d["entities"][0].update(orbit=[1.0])),
        _resave(lambda d: d["entities"][0].update(fuel=None)),  # a state needs fuel
        _resave(lambda d: d["entities"][1].update(fuel=1.0)),  # fuel needs a state
        _resave(lambda d: d["entities"][0].update(state="RTB")),  # orbit only ON_STATION
        _resave(lambda d: d["entities"].reverse()),
        _resave(lambda d: d.update(next_entity_id=3)),
        _resave(lambda d: d["campaign"].update(clock_paused=0)),
        _resave(lambda d: d["campaign"].update(tick=-1)),
        _resave(lambda d: d.update(respawn_left=[])),
        _resave(lambda d: d.update(respawn_left={"c": 0})),  # 0 is deleted, never stored
        _resave(lambda d: d.update(respawn_left={"c": True})),
        _resave(lambda d: d.update(respawn_left={7: 1})),
        _resave(lambda d: d.update(reserve_queue={})),
        _resave(lambda d: d["reserve_queue"][0].update(role="PILOT")),
        _resave(lambda d: d["reserve_queue"][0].update(extra=1)),
        _resave(lambda d: d["reserve_queue"][0].update(target_tick="9")),  # strict: no coercion
        _resave(lambda d: d["reserve_queue"].append(d["reserve_queue"][0])),  # U-4: once each
    ],
)
def test_load_rejects_malformed_input(bad: bytes) -> None:
    with pytest.raises(ValueError):
        load(bad)


def test_load_checks_cover_every_field() -> None:
    assert set(world_mod._ENTITY_CHECKS) == set(world_mod._ENTITY_KEYS)
    assert set(world_mod._CAMPAIGN_CHECKS) == set(world_mod._CAMPAIGN_KEYS)


def test_older_format_gets_the_version_error() -> None:
    def v3(d: dict[str, Any]) -> None:
        d.pop("reserve_queue")
        d.update(v=3)

    with pytest.raises(ValueError, match="unsupported snapshot format version 3"):
        load(_resave(v3))
