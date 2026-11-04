"""NX-170 part a, QA fix round: what enemy views and Huds may reveal, restarts and pauses (WP-9).

Each test names the behaviour it pins; the hand-built worlds start the shipped campaign and
change one thing, so a regression in `nexus.broadcast.frames` fails exactly one of them.
"""

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st
from test_frames import CAMPAIGN, CFG, builder, run

from nexus.broadcast.frames import _public, encode
from nexus.contracts.gen.events.campaign_ended import CampaignEnded, Score
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.objective_announced import ObjectiveAnnounced
from nexus.contracts.gen.wire import views as v
from nexus.contracts.gen.wire.snapshot import Snapshot
from nexus.core.fog import side_view
from nexus.core.step import step
from nexus.core.world import Contact, Entity, FacilityMarker, Vec2, World
from nexus.runtime.campaign_config import start_campaign

COMMANDER = "0192f0c1-7a2b-7c3d-8e4f-0123456789ab"
FACILITY_KINDS = {"RADAR_SITE", "AIR_DEFENSE_SITE"}


def fresh() -> World:
    return start_campaign(CAMPAIGN, 1, CFG)


def enemy_mobile(world: World) -> Entity:
    rules = world.rules
    assert rules is not None
    return next(
        e for e in world.entities() if e.side == "ENEMY" and rules.domain[e.kind] != "STATIC"
    )


def check_snapshot(world: World, snap: Snapshot) -> int:
    """No enemy field reveals hidden data (WP-9); returns how many enemies the snapshot shows."""
    view = side_view(world, "COALITION")
    shown = 0
    for ev in snap.entities:
        assert ev.unit_kind not in FACILITY_KINDS  # facilities are NodeView.facilities only
        if ev.side == "ENEMY":
            shown += 1
            track = view.tracks[ev.entity_id]
            assert (ev.pos.x_m, ev.pos.y_m) == (round(track.pos.x), round(track.pos.y))
            assert (ev.callsign, ev.spotted, ev.follow_entity_id) == (None, None, None)
    for node in snap.nodes:
        if node.owner == "ENEMY":
            assert (node.stock_pct, node.starvation) == (None, None)
        for f in node.facilities:
            assert world.get(f.entity_id).side == "COALITION" or f.entity_id in view.markers
    return shown


@settings(max_examples=3, deadline=None)
@given(seed=st.integers(0, 2**31 - 1))
def test_no_enemy_field_reveals_more_than_the_track(seed: int) -> None:
    fb, shown = builder(), 0
    for world, _ in run(seed, 1300, fb):
        if world.campaign.tick % 100 == 0:
            shown += check_snapshot(world, fb.snapshot(world))
    assert shown, "the run must show tracked enemies, or the test proves nothing"


def test_enemy_view_uses_the_track_and_nulls_own_only_fields() -> None:
    world = fresh()
    e, other = enemy_mobile(world), enemy_mobile(world)
    e.callsign, e.follow_id = "ABC-12", other.id  # must not reach the wire
    world.contacts["COALITION"][e.id] = Contact(e.kind, Vec2(e.pos.x + 37.4, e.pos.y), Vec2(3, 4))
    snap = builder().snapshot(world)
    view = next(x for x in snap.entities if x.entity_id == e.id)
    assert (view.pos.x_m, view.pos.y_m) == (round(e.pos.x + 37.4), round(e.pos.y))
    assert (view.heading_deg, view.speed_mps) == (37, 5)
    assert (view.callsign, view.spotted, view.follow_entity_id) == (None, None, None)


def test_an_untracked_enemy_is_not_in_the_snapshot() -> None:
    world = fresh()
    hidden = enemy_mobile(world)
    assert all(x.entity_id != hidden.id for x in builder().snapshot(world).entities)


def test_discovered_enemy_facility_is_a_node_facility_and_an_undiscovered_one_is_not() -> None:
    world = fresh()
    sites = [
        e for e in world.entities() if e.side == "ENEMY" and e.base_id and e.kind in FACILITY_KINDS
    ]
    found, hidden = sites[0], sites[1:]
    assert hidden
    world.markers["COALITION"][found.id] = FacilityMarker(
        found.kind, found.variant, found.pos, True, 7, 1500, "HEALTHY"
    )
    nodes = {n.node_id: n for n in builder().snapshot(world).nodes}
    shown = {f.entity_id: f for n in nodes.values() for f in n.facilities}
    assert shown[found.id].confirmed_tick == 7
    assert found.id in {f.entity_id for f in nodes[found.base_id or ""].facilities}
    assert not {h.id for h in hidden} & shown.keys()
    own = [f for f in shown.values() if world.get(f.entity_id).side == "COALITION"]
    assert own and all(f.confirmed_tick is None for f in own)


def test_starvation_edges_and_enemy_stock_is_hidden() -> None:
    world = fresh()
    rules = world.rules
    assert rules is not None
    node = next(
        n for n, f in rules.supply.starve_floor.items() if f >= 2 and world.owner[n] == "COALITION"
    )
    floor = rules.supply.starve_floor[node]

    def state() -> tuple[int | None, str | None]:
        n = next(x for x in builder().snapshot(world).nodes if x.node_id == node)
        return n.stock_pct, n.starvation

    for stock, want in [(0, "EMPTY"), (floor - 1, "LOW"), (floor, "OK"), (floor + 1, "OK")]:
        world.stock[node] = stock
        assert state()[1] == want, stock
    assert state()[0] is not None
    world.owner[node] = "ENEMY"
    assert state() == (None, None)


def test_a_captured_node_hides_the_enemy_captors_commander_ids() -> None:
    def captured(to: str) -> Event:
        return NodeCaptured.model_construct(
            kind="NodeCaptured", tick=1, event_seq=1, campaign_id=CAMPAIGN, node_id="cross-n",
            from_="NEUTRAL", to=to, participant_commander_ids=[COMMANDER],
        )  # fmt: skip

    world = fresh()
    enemy, ours = _public(world, captured("ENEMY")), _public(world, captured("COALITION"))
    assert isinstance(enemy, NodeCaptured) and enemy.participant_commander_ids == []
    assert isinstance(ours, NodeCaptured) and ours.participant_commander_ids == [COMMANDER]


def test_first_delta_is_self_contained_and_an_unchanged_one_is_empty() -> None:
    world, fb = fresh(), builder()
    step(world, [])
    step(world, [])
    first = fb.delta(world, [])
    snap = fb.snapshot(world)
    assert first.base_tick == first.tick == world.campaign.tick
    assert {p.entity_id for p in first.upserts} == {e.entity_id for e in snap.entities}
    assert all(set(p.model_fields_set) >= set(v.EntityView.model_fields) for p in first.upserts)
    assert first.blobs == [] and first.last_known == []  # lists, not "unchanged"
    world.contacts["COALITION"][enemy_mobile(world).id] = Contact(
        "ENEMY_ARMOR", Vec2(10, 10), Vec2(0, 0), age=3
    )
    changed = fb.delta(world, [])
    assert changed.base_tick == first.tick and changed.last_known is not None
    same = fb.delta(world, [])
    assert (same.upserts, same.removes, same.node_patches) == ([], [], [])
    assert (same.blobs, same.last_known) == (None, None)


def test_seen_tick_and_last_known_hold_still_while_the_clock_is_paused() -> None:
    world, fb = fresh(), builder()
    step(world, [])
    lost = enemy_mobile(world)
    world.contacts["COALITION"][lost.id] = Contact(lost.kind, Vec2(5, 5), Vec2(0, 0), age=0)
    fb.delta(world, [])
    for _ in range(2):  # running: the age and the clock advance together
        step(world, [])
        fb.delta(world, [])
    seen = fb.snapshot(world).last_known[0].seen_tick
    age = world.contacts["COALITION"][lost.id].age
    assert age is not None and seen == world.campaign.running_ticks - age
    world.campaign.clock_paused, world.campaign.pause_reason = True, "TECHNICAL"
    start = world.campaign.tick
    for _ in range(5):
        step(world, [])
        d = fb.delta(world, [])
        assert d.last_known is None and d.tick > start
        assert fb.snapshot(world).last_known[0].seen_tick == seen


def test_hud_result_and_recent_events_follow_the_events_seen() -> None:
    world, fb = fresh(), builder()

    def announced(n: int) -> Event:
        return ObjectiveAnnounced.model_construct(
            kind="ObjectiveAnnounced", tick=1, event_seq=n, campaign_id=CAMPAIGN,
            objective_id=n, node_id="cross-n", deadline_tick=9,
        )  # fmt: skip

    ended = CampaignEnded.model_construct(
        kind="CampaignEnded", tick=1, event_seq=99, campaign_id=CAMPAIGN, result="VICTORY",
        end_tick=1, score=Score(coalition=1.0, enemy=0.0), winner="COALITION", nodes_held_pct=100,
    )  # fmt: skip
    assert fb.hud(world).panels.campaign_status.result is None
    fb.delta(world, [announced(n) for n in range(1, 7)] + [ended])
    hud = fb.hud(world)
    assert hud.panels.campaign_status.result == "VICTORY"
    assert hud.momentum_breakdown is not None
    assert [e.event_seq for e in hud.momentum_breakdown.recent_events] == [3, 4, 5, 6, 99]
    # Documented limit: a builder made after a restart cannot know the result (no world record).
    assert builder().hud(world).panels.campaign_status.result is None


def test_a_kind_without_a_combat_row_reads_full_hp() -> None:
    world = fresh()
    world.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(1000, 1000), hp=5)
    assert world.rules is not None and world.rules.combat is not None
    world.rules = replace(world.rules, combat=replace(world.rules.combat, units={}))
    snap = builder().snapshot(world)
    assert snap.entities and all(e.hp_pct == 100 for e in snap.entities)


def test_two_runs_of_a_seed_encode_to_identical_bytes() -> None:
    def frames() -> list[bytes]:
        fb, out = builder(), []
        for world, delta in run(7, 400, fb):
            assert delta is not None
            out.append(encode(delta))
            if world.campaign.tick % 100 == 0:
                out.append(encode(fb.snapshot(world)))
        return out

    assert frames() == frames()
