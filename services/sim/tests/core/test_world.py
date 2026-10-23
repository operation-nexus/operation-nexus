"""World model, canonical state_hash and snapshot tests (NX-101, SIM-CORE SC-4 / SC-9, ADR-0002)."""

import math
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
from nexus.core.world import (
    Blob,
    Campaign,
    CaptureBar,
    Claim,
    Contact,
    FacilityMarker,
    Job,
    Objective,
    Shot,
    Vec2,
    World,
    load,
    save,
    state_hash,
    to_canonical,
)

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
    # NX-150: the enemy tracks the fighter; the coalition keeps a last-known track of the armor.
    # NX-150 part 2b: an enemy recon unit paints the fighter.
    w.contacts["ENEMY"][1] = Contact(
        "STRIKE_FIGHTER", Vec2(1000.25, 2000.5), Vec2(250.0, 0.0), painted=True
    )
    w.contacts["COALITION"][3] = Contact("ENEMY_ARMOR", Vec2(149e3, 80e3), Vec2(-25, 3.5), 12)
    # NX-150 part 2: a facility, and the enemy's marker of it confirmed on tick 2 of 5.
    w.campaign.tick = 5
    sam = w.spawn("AIR_DEFENSE_SITE", "COALITION", "AI_GARRISON", Vec2(90e3, 120e3), hp=150)
    sam.base_id, sam.variant, sam.emitting = "west-airbase", "SAM", True
    w.markers["ENEMY"][4] = FacilityMarker(
        "AIR_DEFENSE_SITE", "SAM", Vec2(90e3, 120e3), True, 2, 35_000, "DAMAGED"
    )
    # NX-150 part 2b: the coalition's blobs from the tick-3 refresh, 2 running ticks ago.
    w.blobs["COALITION"] = (Blob("3-7", Vec2(75e3, 5e3), "S"), Blob("3-48", Vec2(85e3, 15e3), "L"))
    w.blob_runs["COALITION"] = {"7": 2, "48": 1}  # NX-374: refreshes in a row a blob kept its cell
    w.sigint_age = 2
    # NX-124: the fighter has fired one of its 4 missiles (reload 3 ticks left); the infantry is a
    # wreck with 300 running ticks to go; two shots are in flight, by (impact_tick, id).
    fighter.alt_band, fighter.ammo, fighter.reload = "MED", [3, 400], [3, 0]
    wreck = w.get(2)
    wreck.hp, wreck.damage_state, wreck.wreck_left = 7, "DISABLED", 300
    wreck.hits = [[3, 40], [1, 52]]  # recent hits on the wreck: [shooter, running tick]
    w.shots = [Shot(3, 3, 1, "AG_CANNON", 6), Shot(1, 3, 2, "AG_CANNON", 7)]
    w._next_shot_id = 4
    # NX-125: node owners, and the coalition a quarter of the way into cross-n.
    w.owner = {"cross-n": "NEUTRAL", "east-airbase": "ENEMY", "west-airbase": "COALITION"}
    w.capture["cross-n"] = CaptureBar("COALITION", 25_000_000)
    # NX-126: paused by staff for a raid since running tick 3; 3 of the 4 objectives issued are
    # done, the 4th is a hold on west-airbase due at running tick 900; the coalition has held the
    # victory share for 2 ticks and the sides' held-node sums are 8 and 4.
    c = w.campaign
    c.running_ticks, c.clock_paused, c.pause_reason, c.pause_sub_reason = 3, True, "STAFF", "RAID"
    c.hold_ticks, c.held_ticks_coalition, c.held_ticks_enemy = 2, 8, 4
    c.objectives_issued, c.objectives_done = 4, 3
    w.objective = Objective(4, "west-airbase", 900, True)
    # NX-374: the coalition board holds a defend job the fighter claimed (made progress at running
    # tick 2) and a scout of blob 3-7 waiting on it; the enemy board one resupply; the armor has a
    # GOTO order.
    fighter.job_id, armor.order = 1, "GOTO"
    defend = Job(1, "DEFEND", "defend:west-airbase", 2, 1500, 1, node="west-airbase", expires=9000)
    defend.claims[1] = Claim(2, True)
    scout = Job(
        2,
        "SCOUT",
        "scout:7",
        1,
        1000,
        2,
        blob="3-7",
        pos=Vec2(75e3, 5e3),
        expires=9000,
        depends_on=1,
    )
    w.boards["COALITION"] = {1: defend, 2: scout}
    w.boards["ENEMY"] = {
        3: Job(
            3, "RESUPPLY", "resupply:east-airbase", 3, 2000, 3, node="east-airbase", expires=9000
        )
    }
    w._next_job_id = 4
    # NX-374 follow-ups: the Static lost east-airbase on running tick 2, the coalition scouted cell
    # 7 (no scout job for it until running tick 900), and the armor has a truck-style pickup.
    w.lost, w.cooldown["COALITION"], armor.pickup = {"east-airbase": 2}, {"7": 900}, "cross-n"
    return w


def test_golden_state_hash_seed_12345() -> None:
    # Pinned by running this implementation once (NX-101; re-pinned NX-121: path, last_node, v2;
    # NX-122: respawn_left, v3; NX-122 part 3: reserve_queue, v4; NX-368: state, fuel, orbit, v5;
    # NX-370: callsigns, v6; NX-150: contacts, v7; NX-150 part 2: base_id, variant, emitting,
    # markers and a tick, v8; NX-150 part 2b: painted, blobs, sigint_age, v9;
    # NX-123: node stock, cargo, unload_milli, v10; NX-123 part 2: rearm_milli, rearm_spent,
    # stalled, v11; NX-125: node owner and capture bars, v12; NX-126: the campaign clock, pause
    # reason, end flag, score sums and the active objective, v13; NX-124: damage state, altitude
    # band, ammo, reload, wreck timer and pending shots, v14; part 2: the rearm-stop carries and
    # the downed-crew markers, v15; NX-124 part 3: defense hp, drain carry, down flags, the defeat
    # run, node shots, Entity.defended and marker ring_m and state, v16; NX-374: both Tasking Boards
    # with their job counter, Entity.order and Entity.job_id, v17; NX-374 part 2: Entity.follow_id
    # and fired_by, Job.entity, v18; NX-155: each side's Threat Director state, v19; NX-157:
    # Entity.home, Job.via and the Pattern of Life timers, v21; NX-379: Job.arrived, v22; NX-382:
    # the intercept clock and Job.lost, v23; NX-373: bridge hp and the down bridges, v24).
    # A change here breaks every recorded replay hash: needs a `golden-update` reason.
    assert (
        state_hash(golden_world())
        == "65ad921445afa845f222aca0c9bae40bc14e91aa77f0b649d00d79890c878b08"
    )
    e = to_canonical(golden_world(), quantize=True)["entities"][0]
    assert e["pos"] == [1000250, 2000500]  # mm
    assert e["vel"] == [250000, 0]  # mm/s
    assert e["path"] == [[5000000, 2000500], "west-airbase"]  # waypoints in mm too
    assert (e["state"], e["fuel"], e["orbit"]) == ("ON_STATION", 1234250000, [900500, 2000500])
    assert to_canonical(golden_world(), quantize=True)["entities"][1]["fuel"] is None
    assert list(e) == sorted(e)
    lost = to_canonical(golden_world(), quantize=True)["contacts"]["COALITION"]
    assert lost == [
        {"age": 12, "id": 3, "kind": "ENEMY_ARMOR", "painted": False, "pos": [149000000, 80000000],
         "vel": [-25000, 3500]}
    ]  # fmt: skip
    assert to_canonical(golden_world(), quantize=True)["blobs"] == {
        "COALITION": [{"id": "3-7", "pos": [75000000, 5000000], "size": "S"},
                      {"id": "3-48", "pos": [85000000, 15000000], "size": "L"}],
        "ENEMY": [],
    }  # fmt: skip
    assert to_canonical(golden_world(), quantize=True)["markers"]["ENEMY"] == [
        {"confirmed_tick": 2, "emitting": True, "id": 4, "kind": "AIR_DEFENSE_SITE",
         "pos": [90000000, 120000000], "ring_m": 35000, "state": "DAMAGED", "variant": "SAM"}
    ]  # fmt: skip


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


@pytest.mark.parametrize("ok", [0, -0.0, 7, -1e9, 1e9, 10**9, 1.5e-300])
def test_vec2_accepts_in_range_numbers_as_floats(ok: Any) -> None:
    v = Vec2(ok, ok)
    assert (v.x, v.y) == (float(ok), float(ok))
    assert type(v.x) is float and type(v.y) is float


def test_vec2_just_over_the_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        Vec2(math.nextafter(1e9, math.inf), 0.0)


finite = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False)
vecs = st.builds(Vec2, finite, finite)
_KINDS: list[tuple[UnitKind, Side, OwnerKind]] = [
    ("LOGI_TRUCK", "COALITION", "COMMANDER"),
    ("RADAR_SITE", "ENEMY", "AI_GARRISON"),
]
kinds = st.sampled_from(_KINDS)
fuels = st.floats(min_value=0.0, max_value=1e6, allow_nan=False)
entity_args = st.tuples(kinds, vecs, vecs, st.integers(1, 1000), st.sampled_from([None, "HAWK-07"]))


@st.composite
def worlds(draw: st.DrawFn) -> World:
    seed, tick = draw(st.integers(0, 2**64 - 1)), draw(st.integers(0, 10**9))
    reason: Any = draw(
        st.none() | st.sampled_from(world_mod._PAUSE_REASONS)
    )  # NX-126: paused iff set
    sub: Any = (
        draw(st.none() | st.sampled_from(world_mod._PAUSE_SUB_REASONS))
        if reason == "STAFF"
        else None
    )
    issued = draw(st.integers(0, 5))
    running, ended = draw(st.integers(0, tick)), draw(st.booleans())
    w = World.new(
        Campaign(
            CAMPAIGN_ID, seed, "c", tick, reason is not None, running, reason,
            sub, ended, draw(st.integers(0, running)),
            draw(st.integers(0, 2 * running)), draw(st.integers(0, 2 * running)), issued,
            draw(st.integers(0, issued)),
        )
    )  # fmt: skip
    w.owner = {"cross-n": "NEUTRAL", "fob-n-e": "ENEMY"}  # the held sums are bounded by nodes
    if (
        issued and not ended and draw(st.booleans())
    ):  # the active objective is the latest issued (NX-126)
        w.objective = Objective(
            issued, "fob-n-e", running + draw(st.integers(1, 10**6)), draw(st.booleans())
        )
    for (kind, side, owner), pos, vel, hp, callsign in draw(st.lists(entity_args, max_size=8)):
        e = w.spawn(kind, side, owner, pos, vel=vel, hp=hp, callsign=callsign)
        if draw(st.booleans()):  # an aircraft's state (NX-368)
            e.state, e.fuel = draw(st.sampled_from(world_mod._UNIT_STATES)), draw(fuels)
            e.orbit = draw(vecs) if e.state == "ON_STATION" else None
    for e in w.entities():  # NX-124: combat state
        e.damage_state = draw(st.sampled_from(world_mod._DAMAGE_STATES))
        e.alt_band = draw(st.none() | st.sampled_from(world_mod._ALT_BANDS))
        e.ammo = draw(st.lists(st.integers(0, 400), max_size=3))
        e.reload = [draw(st.integers(0, 100)) for _ in e.ammo]
        e.wreck_left = draw(st.integers(1, 6000)) if e.damage_state == "DISABLED" else None
        stamps = sorted(draw(st.lists(st.integers(1, 10**6), max_size=3)))
        e.hits = [[draw(st.integers(1, 50)), t] for t in stamps]
    ids = list(range(1, w._next_entity_id))  # a shot's units may be gone, never unissued
    shots = []
    if ids:
        shots = draw(
            st.lists(
                st.tuples(st.sampled_from(ids), st.sampled_from(ids), st.integers(1, 99)),
                max_size=4,
            )
        )
    w._next_shot_id = len(shots) + 1
    w.shots = sorted(
        (Shot(n, a, b, "SAM", at) for n, (a, b, at) in enumerate(shots, 1)),
        key=lambda s: (s.impact_tick, s.id),
    )
    for _ in range(draw(st.integers(min_value=0, max_value=5))):
        w.rng.stream(draw(st.sampled_from(list(RngStream)))).next_u64()
    for i in draw(st.lists(st.integers(1, w._next_entity_id - 1), unique=True)) if len(w) else []:
        e = w.get(i)
        knower: Side = "ENEMY" if e.side == "COALITION" else "COALITION"
        age = draw(st.none() | st.integers(0, 10**6))
        painted = age is None and draw(st.booleans())  # part 2b: tracked contacts only
        w.contacts[knower][i] = Contact(e.kind, draw(vecs), draw(vecs), age, painted)  # NX-150
        e.base_id, e.variant = draw(st.sampled_from([(None, None), ("fob-n-e", "SAM")]))
        e.emitting = draw(st.none() | st.booleans())
        if draw(st.booleans()):  # FOW-13
            seen = draw(st.integers(0, w.campaign.tick))
            w.markers[knower][i] = FacilityMarker(
                e.kind,
                e.variant,
                draw(vecs),
                e.emitting,
                seen,
                draw(st.none() | st.integers(1, 10**5)),
                draw(st.sampled_from(world_mod._DAMAGE_STATES)),
            )
    refresh = draw(st.integers(0, w.campaign.tick))  # NX-150 part 2b
    for side in ("COALITION", "ENEMY"):
        cells = sorted(draw(st.sets(st.integers(0, 10**4), max_size=3)))
        size = draw(st.sampled_from(world_mod._BLOB_SIZES))
        w.blobs[side] = tuple(Blob(f"{refresh}-{k}", draw(vecs), size) for k in cells)
        w.blob_runs[side] = {str(k): draw(st.integers(1, 5)) for k in cells}
    w.sigint_age = draw(st.integers(0, w.campaign.tick - refresh))  # running ticks since
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
    assert _changes_hash(lambda w: setattr(w.get(4), "emitting", False))  # NX-150 part 2
    assert _changes_hash(lambda w: setattr(w.markers["ENEMY"][4], "confirmed_tick", 3))
    assert _changes_hash(lambda w: setattr(w.contacts["ENEMY"][1], "painted", False))  # part 2b
    assert _changes_hash(lambda w: setattr(w, "sigint_age", 3))
    assert _changes_hash(lambda w: w.get(1).ammo.__setitem__(0, 2))  # NX-124
    assert _changes_hash(lambda w: w.get(1).reload.__setitem__(1, 1))
    assert _changes_hash(lambda w: setattr(w.get(2), "wreck_left", 299))
    assert _changes_hash(lambda w: w.get(2).hits.append([4, 60]))
    assert _changes_hash(lambda w: setattr(w.get(1), "alt_band", "HIGH"))
    assert _changes_hash(lambda w: w.shots.pop())
    assert _changes_hash(lambda w: setattr(w, "_next_shot_id", 5))
    assert _changes_hash(lambda w: w.blobs.update(COALITION=w.blobs["COALITION"][:1]))


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
        _resave(lambda d: d["entities"][0].update(hp=None)),  # always real since NX-124
        _resave(lambda d: d["entities"][0].update(hp=0)),  # a unit at 0 hp is destroyed
        _resave(lambda d: d["entities"][0].update(damage_state="DESTROYED")),
        _resave(lambda d: d["entities"][0].update(alt_band="SPACE")),
        _resave(lambda d: d["entities"][0].update(ammo=[-1, 0])),
        _resave(lambda d: d["entities"][0].update(reload=[1])),  # one per weapon
        _resave(lambda d: d["entities"][0].update(wreck_left=5)),  # only a Disabled unit has one
        _resave(lambda d: d["entities"][1].update(wreck_left=0)),  # removed at 0, never stored
        _resave(lambda d: d["entities"][1].update(hits=[[1, 5], [1, 4]])),  # oldest first
        _resave(lambda d: d["entities"][1].update(hits=[[0, 5]])),  # a shooter id
        _resave(lambda d: d["entities"][1].update(hits=[[1]])),
        _resave(lambda d: d["shots"].reverse()),  # (impact_tick, id) order
        _resave(lambda d: d["shots"][0].update(id=1)),  # unique ids
        _resave(lambda d: d["shots"][0].update(id=4)),  # below next_shot_id
        _resave(lambda d: d["shots"][0].update(target=9)),  # below next_entity_id
        _resave(lambda d: d["shots"][0].update(impact_tick=0)),
        _resave(lambda d: d["shots"][0].pop("weapon_id")),
        _resave(lambda d: d.update(shots={})),
        _resave(lambda d: d.update(next_shot_id=0)),
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
        _resave(lambda d: d.update(contacts={"COALITION": []})),  # NX-150: both sides
        _resave(lambda d: d["contacts"].update(ENEMY={})),
        _resave(lambda d: d["contacts"]["ENEMY"][0].update(age=-1)),
        _resave(lambda d: d["contacts"]["ENEMY"][0].update(age=True)),
        _resave(lambda d: d["contacts"]["ENEMY"][0].update(id=5)),  # >= next_entity_id
        _resave(lambda d: d["contacts"]["ENEMY"][0].update(kind="FACTORY")),
        _resave(lambda d: d["contacts"]["ENEMY"][0].pop("vel")),
        _resave(lambda d: d["contacts"]["ENEMY"].append(d["contacts"]["ENEMY"][0])),  # ascending
        _resave(lambda d: d["contacts"]["COALITION"][0].update(id=2, kind="GARRISON_INFANTRY")),
        _resave(lambda d: d["contacts"]["ENEMY"][0].update(kind="RECON_UAV")),  # not entity 1's
        _resave(lambda d: d["entities"][3].update(emitting=1)),  # NX-150 part 2
        _resave(lambda d: d["entities"][3].update(base_id=7)),
        _resave(lambda d: d["entities"][3].update(variant=7)),
        _resave(lambda d: d.update(markers={"ENEMY": []})),
        _resave(lambda d: d["markers"]["ENEMY"][0].update(emitting="yes")),
        _resave(lambda d: d["markers"]["ENEMY"][0].update(confirmed_tick=6)),  # after the tick
        _resave(lambda d: d["markers"]["ENEMY"][0].update(confirmed_tick=-1)),
        _resave(lambda d: d["markers"]["ENEMY"][0].update(kind="RADAR_SITE")),  # not entity 4's
        _resave(lambda d: d["markers"]["ENEMY"][0].update(variant=1)),
        _resave(lambda d: d["markers"]["ENEMY"][0].update(id=5)),
        _resave(lambda d: d["markers"].update(COALITION=d["markers"]["ENEMY"])),  # its own site
        _resave(lambda d: d["contacts"]["ENEMY"][0].update(painted=1)),  # NX-150 part 2b
        _resave(lambda d: d["contacts"]["COALITION"][0].update(painted=True)),  # last-known
        _resave(lambda d: d.pop("sigint_age")),
        _resave(lambda d: d.update(sigint_age=-1)),
        _resave(lambda d: d.update(blobs={"COALITION": []})),
        _resave(lambda d: d["blobs"].update(ENEMY={})),
        _resave(lambda d: d["blobs"]["COALITION"][0].update(id="blob-7")),
        _resave(lambda d: d["blobs"]["COALITION"][0].update(id="03-7")),
        _resave(lambda d: d["blobs"]["COALITION"][0].update(id=7)),
        _resave(lambda d: d["blobs"]["COALITION"][0].update(size="XL")),
        _resave(lambda d: d["blobs"]["COALITION"][0].update(pos=[1.0])),
        _resave(lambda d: d["blobs"]["COALITION"][0].pop("size")),
        _resave(lambda d: d["blobs"]["COALITION"][0].update(id="2-7")),  # two refresh ticks
        _resave(lambda d: d["blobs"]["COALITION"].reverse()),  # by cell index
        _resave(lambda d: d["blobs"]["COALITION"][1].update(id="3-7")),  # a cell twice
        _resave(lambda d: d["blobs"].update(ENEMY=[{"id": "6-1", "pos": [0.0, 0.0], "size": "S"}])),
        _resave(lambda d: d.update(sigint_age=3)),  # more than the 2 ticks since tick 3
        _resave(lambda d: d.pop("owner")),  # NX-125
        _resave(lambda d: d["owner"].update({"cross-n": "BOTH"})),
        _resave(lambda d: d["owner"].update({7: "ENEMY"})),
        _resave(lambda d: d.update(owner=[])),
        _resave(lambda d: d["capture"]["cross-n"].update(progress=0)),  # no progress: no bar
        _resave(lambda d: d["capture"]["cross-n"].update(progress=100_000_000)),  # flips at once
        _resave(lambda d: d["capture"]["cross-n"].update(progress=True)),
        _resave(lambda d: d["capture"]["cross-n"].update(side="NEUTRAL")),
        _resave(lambda d: d["capture"]["cross-n"].update(extra=1)),
        _resave(lambda d: d["capture"].update({"mid-nowhere": d["capture"]["cross-n"]})),
        _resave(lambda d: d["owner"].update({"cross-n": "COALITION"})),  # its own bar
    ],
)
def test_load_rejects_malformed_input(bad: bytes) -> None:
    with pytest.raises(ValueError):
        load(bad)


def test_contact_of_a_removed_entity_loads() -> None:
    w = golden_world()
    w.remove(3)  # the coalition's last-known armor outlives it (FOW-6a)
    assert load(save(w)).contacts == w.contacts
    w.remove(4)  # a destroyed site's marker stays (FOW-13)
    assert load(save(w)).markers == w.markers


def test_load_checks_cover_every_field() -> None:
    assert set(world_mod._ENTITY_CHECKS) == set(world_mod._ENTITY_KEYS)
    assert set(world_mod._CAMPAIGN_CHECKS) == set(world_mod._CAMPAIGN_KEYS)


def test_older_format_gets_the_version_error() -> None:
    def v3(d: dict[str, Any]) -> None:
        d.pop("reserve_queue")
        d.update(v=3)

    with pytest.raises(ValueError, match="unsupported snapshot format version 3"):
        load(_resave(v3))


def test_capture_state_is_in_the_hash_and_the_snapshot() -> None:
    assert _changes_hash(lambda w: w.owner.update({"cross-n": "ENEMY"}))
    assert _changes_hash(lambda w: w.capture["cross-n"].__setattr__("progress", 25_000_001))
    assert _changes_hash(lambda w: w.capture.pop("cross-n"))
    restored = load(save(golden_world()))
    assert restored.owner == golden_world().owner
    assert restored.capture == golden_world().capture
