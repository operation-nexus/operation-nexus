"""NX-170 part a: the wire frame builders (WIRE-PROTOCOL WP-4, WP-8..10; CONTRACTS sections 7, 10).

The scenario starts the shipped campaign and runs it long enough for the coalition to track enemy
units (about tick 1200 on the seeds below), so frames carry both visible and hidden enemies.
"""

import json
from collections import deque
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import msgpack
import pytest
from golden.make_cases import join
from hypothesis import given, settings
from hypothesis import strategies as st

from nexus.broadcast.frames import FrameBuilder, _motion, _public, control, encode
from nexus.contracts.gen.events.campaign_clock_paused import CampaignClockPaused
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_destroyed import UnitDestroyed
from nexus.contracts.gen.wire.ack import Ack
from nexus.contracts.gen.wire.control import Control
from nexus.contracts.gen.wire.delta import Delta
from nexus.contracts.gen.wire.hud import Hud
from nexus.contracts.gen.wire.snapshot import Snapshot
from nexus.contracts.gen.wire.welcome import Welcome
from nexus.core.fog import side_view
from nexus.core.step import step
from nexus.core.world import World, state_hash
from nexus.runtime.campaign_config import CampaignConfig, load_campaign_config, start_campaign

CFG = load_campaign_config()
CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
VERSION = "0.65"
TICKS = 1300
JOINS = [join(1, "STRIKE", "east-airbase"), join(2, "LOGI", "fob-n-w"), join(3, "RECON", "cross-n")]


def builder(cfg: CampaignConfig = CFG) -> FrameBuilder:
    return FrameBuilder(cfg.theater, protocol_version=VERSION, server_build="test")


def run(
    seed: int, ticks: int = TICKS, frames: FrameBuilder | None = None
) -> Iterator[tuple[World, Delta | None]]:
    """Yields the world after each tick with the Delta built from it (None without a builder)."""
    world = start_campaign(CAMPAIGN, seed, CFG)
    for t in range(1, ticks + 1):
        commands = [
            c.model_copy(update={"target_tick": t, "arrival_seq": i + 1})
            for i, c in enumerate(JOINS)
        ]
        events = step(world, commands if t == 1 else [])
        yield world, frames.delta(world, events) if frames else None


def decoded(frame: Any) -> dict[str, Any]:
    out = msgpack.unpackb(encode(frame))
    assert isinstance(out, dict)
    return out


def test_every_message_round_trips_through_msgpack_and_its_schema() -> None:
    fb = builder()
    world, last = deque(run(3, frames=fb), maxlen=1)[0]
    assert last is not None and last.upserts, "the last tick must carry changes"
    frames: list[Any] = [fb.welcome(world), fb.snapshot(world), last, fb.hud(world)]
    frames += [
        control(VERSION, "RELOAD"),
        control(VERSION, "RESYNC"),
        Ack(type="Ack", v=VERSION, applied_tick=7),
    ]
    for frame in frames:
        wire = decoded(frame)
        again = type(frame).model_validate(wire)  # raises on any schema violation
        assert again.model_dump(mode="json", by_alias=True, exclude_unset=True) == wire
    with pytest.raises(ValueError, match="action"):
        Control.model_validate({"type": "Control", "v": VERSION, "action": "BANNER"})


def test_delta_stream_applied_to_a_snapshot_reproduces_the_later_snapshot() -> None:
    fb, start = builder(), 1100
    entities: dict[int, dict[str, Any]] = {}
    nodes: dict[str, dict[str, Any]] = {}
    blobs: list[Any] = []
    last_known: list[Any] = []
    for world, delta in run(3, frames=fb):
        assert delta is not None
        tick = world.campaign.tick
        if tick == start:
            snap = fb.snapshot(world).model_dump(mode="json")
            entities = {e["entity_id"]: e for e in snap["entities"]}
            nodes = {n["node_id"]: n for n in snap["nodes"]}
            blobs, last_known = snap["blobs"], snap["last_known"]
        elif tick > start:
            d = json.loads(delta.model_dump_json(exclude_unset=True))
            assert d["base_tick"] == tick - 1
            for p in d["upserts"]:
                entities.setdefault(p["entity_id"], {}).update(p)
            for i in d["removes"]:
                del entities[i]
            for p in d["node_patches"]:
                nodes[p["node_id"]].update(p)
            blobs = blobs if d["blobs"] is None else d["blobs"]
            last_known = last_known if d["last_known"] is None else d["last_known"]
    end = fb.snapshot(world).model_dump(mode="json")
    assert entities == {e["entity_id"]: e for e in end["entities"]}
    assert nodes == {n["node_id"]: n for n in end["nodes"]}
    assert (blobs, last_known) == (end["blobs"], end["last_known"])
    assert any(not e["side"] == "COALITION" for e in end["entities"]), "an enemy is tracked"


def ids_in(payload: Any) -> Iterator[int]:
    """Every entity id the payload names, whatever message it is in."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"entity_id", "killer_id", "follow_entity_id", "shooter_id", "target_id"}:
                if value is not None:
                    yield value
            elif key in {"assist_ids", "removes", "lost_ids", "credit_ids"}:
                yield from value
            else:
                yield from ids_in(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from ids_in(item)


def keys_in(payload: Any) -> Iterator[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from keys_in(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from keys_in(item)


@settings(max_examples=5, deadline=None)
@given(seed=st.integers(0, 2**31 - 1))
def test_no_hidden_entity_seed_or_display_name_on_the_wire(seed: int) -> None:
    fb, hidden_seen = builder(), 0
    for world, delta in run(seed, frames=fb):
        assert delta is not None
        view = side_view(world, "COALITION")
        shown = {i for i, c in view.tracks.items()} | set(view.markers) | set(view.last_known)
        hidden = {
            e.id for e in world.entities()
            if e.side == "ENEMY" and e.id not in shown
        }  # fmt: skip
        hidden_seen += len(hidden)
        frames = [decoded(delta)]
        if world.campaign.tick % 300 == 0:
            frames += [decoded(fb.snapshot(world)), decoded(fb.welcome(world))]
        for wire in frames:
            assert not hidden & set(ids_in(wire)), (wire["type"], world.campaign.tick)
            assert not {"seed", "display_name"} & set(keys_in(wire))
    assert hidden_seen, "the run must have hidden enemies, or the test proves nothing"


def test_building_frames_leaves_the_state_hash_alone() -> None:
    plain = [state_hash(w) for w, _ in run(5, 400)]
    framed = builder()
    with_frames = []
    for world, _ in run(5, 400, framed):
        framed.snapshot(world)
        with_frames.append(state_hash(world))
    assert with_frames == plain


def test_hud_counts_strategic_nodes_held_and_the_clock_limit() -> None:
    world = start_campaign(CAMPAIGN, 1, CFG)
    fb, rc = builder(), CFG.rules.campaign
    assert rc is not None
    hud = fb.hud(world)
    assert hud.nodes_total == len(rc.strategic) == 8
    held = [n for n in rc.strategic if world.owner[n] == "COALITION"]
    assert hud.nodes_held == len(held)
    flipped = next(n for n in rc.strategic if world.owner[n] != "COALITION")
    world.owner[flipped] = "COALITION"
    hud = fb.hud(world)
    assert hud.nodes_held == len(held) + 1
    assert hud.momentum_breakdown is not None
    assert hud.momentum_breakdown.nodes_held_pct == round(
        100 * hud.nodes_held / hud.nodes_total + 1e-9
    )
    assert hud.campaign_clock.limit_ticks == rc.time_limit_ticks
    assert hud.panels.campaign_status.nodes_held.coalition == hud.nodes_held
    bare = start_campaign(CAMPAIGN, 1, CFG)
    bare.rules = replace(CFG.rules, campaign=None)
    off = fb.hud(bare)
    assert (off.nodes_held, off.nodes_total, off.campaign_clock.limit_ticks, off.momentum_pct) == (
        0,
        0,
        None,
        None,
    )


def test_public_events_drop_the_staff_sub_reason_and_hidden_ids() -> None:
    world = start_campaign(CAMPAIGN, 1, CFG)
    enemy = next(e.id for e in world.entities() if e.side == "ENEMY")
    own = next(e.id for e in world.entities() if e.side == "COALITION" and e.kind != "RADAR_SITE")
    paused = CampaignClockPaused.model_construct(
        kind="CampaignClockPaused",
        tick=1,
        event_seq=1,
        campaign_id=CAMPAIGN,
        reason="STAFF",
        sub_reason="RAID",
    )
    kept = _public(world, paused)
    assert (
        isinstance(kept, CampaignClockPaused) and kept.sub_reason is None and kept.reason == "STAFF"
    )

    def destroyed(entity_id: int, side: str, killer: int | None) -> Event:
        return UnitDestroyed.model_construct(
            kind="UnitDestroyed", tick=1, event_seq=2, campaign_id=CAMPAIGN, entity_id=entity_id,
            killer_id=killer, assist_ids=[enemy], side=side, cause=None,
        )  # fmt: skip

    ours = _public(world, destroyed(own, "COALITION", enemy))
    assert isinstance(ours, UnitDestroyed) and ours.killer_id is None and ours.assist_ids == []
    assert _public(world, destroyed(enemy, "ENEMY", None)) is None


def test_welcome_names_every_node_and_edge_without_dynamic_state() -> None:
    welcome = builder().welcome(start_campaign(CAMPAIGN, 1, CFG))
    assert isinstance(welcome, Welcome) and welcome.tick_rate_hz == 10
    assert not {"entities", "hud", "owner", "stock_pct"} & set(keys_in(decoded(welcome)))
    assert [n.node_id for n in welcome.theater.nodes] == sorted(n.id for n in CFG.theater.nodes)
    assert [(e.a, e.b, e.layer, e.bridge) for e in welcome.theater.edges] == [
        (e.a, e.b, e.layer, e.bridge)
        for e in sorted(CFG.theater.edges, key=lambda e: (e.a, e.b, e.layer))
    ]
    assert isinstance(builder().snapshot(start_campaign(CAMPAIGN, 1, CFG)), Snapshot)
    assert isinstance(builder().hud(start_campaign(CAMPAIGN, 1, CFG)), Hud)


def test_heading_zero_is_north_plus_y_and_east_plus_x_is_ninety() -> None:
    """Q-UX-18: world +y is north, so a unit moving +y has heading 0 and +x (east) has 90."""
    assert _motion(0.0, 5.0) == (0, 5) and _motion(5.0, 0.0) == (90, 5)
    assert _motion(0.0, -5.0)[0] == 180 and _motion(-5.0, 0.0)[0] == 270
