"""NX-374 part 2 and NX-369: follow, escort, escort jobs and formation speed (GAMEPLAY §1b Q-GP-29,
Q-GP-31..33, Q-GP-45, §5 Q-SIM-38; STATE-MACHINES U-10; Q-SIM-76).

Runs on the shipped strait-1 config with the campaign layer off (as test_tasking): 0.6 world s per
tick, a truck and a convoy at 25 m/s, armor at 20, infantry at 5, a recon UAV at 60 and a strike
fighter at 250. The Static's road east-airbase - static-hq is 70 km straight east at y = 120 km, so
`on_road` puts a unit anywhere on it. Station keeping is measured as road distance along that line.
"""

import dataclasses
import math
import statistics
import time

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import cid, join
from test_tasking import (
    AI,
    EVERY,
    RULES,
    TR,
    board_pass,
    jobs,
    new_world,
    of,
    put,
)

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.common.enums import DamageState, OwnerKind, Side, UnitKind
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core.fog import side_view
from nexus.core.follow import can_follow, steer
from nexus.core.step import step
from nexus.core.tasking_gen import _escort, _near_route, _segments, fits
from nexus.core.world import (
    Contact,
    Entity,
    FacilityMarker,
    Vec2,
    World,
    load,
    lose_unit,
    save,
    state_hash,
    to_canonical,
)

DIRECTOR: OwnerKind = "ENEMY_DIRECTOR"
ROAD_Y = 120_000
EAST = 310_000  # east-airbase; static-hq is 70 km on


def unit(w: World, kind: UnitKind, owner: OwnerKind = DIRECTOR) -> Entity:
    side: Side = "ENEMY" if kind.startswith("ENEMY_") else "COALITION"
    e = w.spawn(kind, side, owner, Vec2(EAST, ROAD_Y), commander_id=None)
    e.last_node = "east-airbase"
    return e


def on_road(
    w: World, kind: UnitKind, x: float, *, to: str = "static-hq", owner: OwnerKind = DIRECTOR
) -> Entity:
    """A ground unit `x` metres east of east-airbase, heading for `to`."""
    e = unit(w, kind, owner)
    e.pos, e.path = Vec2(EAST + x, ROAD_Y), [to]
    return e


def follow(f: Entity, leader: Entity) -> None:
    f.follow_id, f.order = leader.id, "FOLLOW"


def run(w: World, ticks: int) -> list[Event]:
    return [e for _ in range(ticks) for e in step(w, [])]


def hurt(e: Entity, hp: int, state: DamageState) -> None:
    e.hp, e.damage_state = hp, state


def speed(e: Entity) -> float:
    return math.hypot(e.vel.x, e.vel.y)


def gap(f: Entity, leader: Entity) -> float:
    """Metres `f` is ahead of `leader` on the eastbound road (negative: behind)."""
    return f.pos.x - leader.pos.x


# --- JOIN: following by id ----------------------------------------------------------------------


def follow_join(n: int, role: str, leader: int) -> JoinCommand:
    return join(n, role, target={"follow_entity_id": leader})


def reasons(events: list[Event]) -> list[str]:
    return [e.reason for e in events if isinstance(e, CommandRejected)]


def test_a_follow_join_spawns_a_follower_with_the_order() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    step(w, [follow_join(1, "STRIKE", lead.id)])
    (f,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert (f.kind, f.follow_id, f.order, f.last_node) == (
        "STRIKE_FIGHTER",
        lead.id,
        "FOLLOW",
        "haven",
    )


@pytest.mark.parametrize("case", ["unknown", "enemy", "disabled", "static", "ground_after_air"])
def test_follow_targets_that_cannot_be_followed_are_rejected(case: str) -> None:
    w = new_world()
    role = "STRIKE"
    leader = {
        "unknown": None,
        "enemy": unit(w, "ENEMY_ARMOR"),
        "disabled": put(w, "LOGI_TRUCK", "west-airbase"),
        "static": next(e for e in w.entities() if e.kind == "RADAR_SITE" and e.side == "COALITION"),
        "ground_after_air": put(w, "STRIKE_FIGHTER", "west-airbase"),
    }[case]
    if case == "disabled":
        assert leader is not None
        leader.damage_state = "DISABLED"
    if case == "ground_after_air":
        role = "LOGI"
    target = 9999 if leader is None else leader.id
    events = step(w, [follow_join(1, role, target)])
    assert reasons(events) == ["FOLLOW_TARGET_INVALID"]
    assert not any(e.commander_id == cid(1) for e in w.entities())


def test_follow_rejection_comes_after_the_cooldown_and_before_the_node_checks() -> None:
    w = new_world()
    w.respawn_left[cid(1)] = 5
    assert reasons(step(w, [follow_join(1, "STRIKE", 9999)])) == ["RESPAWN_COOLDOWN"]
    assert reasons(
        step(w, [join(2, "STRIKE", hold=True, target={"follow_entity_id": 9999}, target_tick=2)])
    ) == ["INVALID_PAYLOAD"]


def test_self_follows_and_loops_are_rejected() -> None:
    w = new_world()
    a, b, c = (put(w, "LOGI_TRUCK", "west-airbase", AI) for _ in range(3))
    follow(b, a)
    follow(c, b)
    assert not can_follow(w, RULES, "LOGI_TRUCK", a.id, a)  # itself
    assert not can_follow(w, RULES, "LOGI_TRUCK", c.id, a)  # a -> c -> b -> a
    assert can_follow(w, RULES, "LOGI_TRUCK", a.id, c)  # c already follows b -> a: no loop
    assert can_follow(w, RULES, "LOGI_TRUCK", a.id, None)  # a unit about to spawn


def test_a_follower_of_a_truck_loads_and_unloads_by_its_own_role() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "haven", cargo=100)
    lead.path, lead.order = ["west-airbase", "fob-n-w"], "HOLD"  # it stays when done
    w.stock["fob-n-w"] = 0
    w.stock["west-airbase"] = 900
    step(w, [follow_join(1, "LOGI", lead.id)])
    (col,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert col.cargo and col.cargo > 0 and col.follow_id == lead.id  # loaded at its source
    start = w.stock["fob-n-w"]
    run(w, 13_000)
    assert (lead.cargo, col.cargo) == (0, 0)  # both unloaded at the column's destination
    assert w.stock["fob-n-w"] > start and col.last_node == "fob-n-w"


# --- station keeping per domain pairing ---------------------------------------------------------


def test_an_escort_settles_500_m_ahead_and_holds_it_at_the_groups_speed() -> None:
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 0)
    armor = on_road(w, "ENEMY_ARMOR", 3_000)  # well ahead: it waits for the convoy
    follow(armor, lead)
    run(w, 400)
    assert gap(armor, lead) == pytest.approx(TR.station_m["escort"], abs=20)
    assert lead.vel.x == pytest.approx(20.0)  # the convoy slowed to its escort's speed
    assert armor.vel.x == pytest.approx(20.0)


def test_a_slow_escort_catches_up_at_top_speed_and_never_overshoots() -> None:
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 800)
    hurt(lead, 30, "DAMAGED")  # 0.75 x 25 m/s = 18.75, under the armor's 20
    armor = on_road(w, "ENEMY_ARMOR", 0)
    follow(armor, lead)
    far = gap(armor, lead)
    peak, closing = -math.inf, []
    for _ in range(2_400):
        step(w, [])
        peak = max(peak, gap(armor, lead))
        closing.append(armor.vel.x)
    assert far == -800 and closing[0] == pytest.approx(20.0)  # top speed while catching up
    assert peak <= TR.station_m["escort"] + 20  # the station, never beyond it
    assert gap(armor, lead) == pytest.approx(TR.station_m["escort"], abs=20)
    assert armor.vel.x == pytest.approx(lead.vel.x)  # then it matches the leader


def test_a_truck_falls_in_200_m_behind_its_leader() -> None:
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 3_000)
    hurt(lead, 30, "DAMAGED")  # slower than the column truck behind it
    col = on_road(w, "ENEMY_CONVOY", 0)
    follow(col, lead)
    run(w, 1_000)
    assert gap(col, lead) == pytest.approx(-TR.station_m["column"], abs=20)


def test_a_chain_keeps_station_on_the_direct_leader() -> None:
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 4_000)
    mid = on_road(w, "ENEMY_CONVOY", 2_000)
    tail = on_road(w, "ENEMY_CONVOY", 0)
    follow(mid, lead)
    follow(tail, mid)
    hurt(lead, 30, "DAMAGED")
    run(w, 1_500)
    assert gap(mid, lead) == pytest.approx(-200, abs=20)
    assert gap(tail, mid) == pytest.approx(-200, abs=20)


def test_the_column_parks_at_a_base_the_leader_reaches() -> None:
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 69_000)
    col = on_road(w, "ENEMY_CONVOY", 68_000)
    escort = on_road(w, "ENEMY_ARMOR", 60_000)
    follow(col, lead)
    follow(escort, lead)
    run(w, 1500)
    assert not lead.path and lead.last_node == "static-hq"
    assert col.last_node == escort.last_node == "static-hq" and not col.path and not escort.path


def test_followers_hold_where_a_leader_stops_off_base() -> None:
    off_base = dataclasses.replace(RULES, node_kind={**RULES.node_kind, "static-hq": "BRIDGE"})
    w = new_world(rules=off_base)
    lead = on_road(w, "ENEMY_CONVOY", 69_000)
    armor = on_road(w, "ENEMY_ARMOR", 69_500)
    follow(armor, lead)
    run(w, 400)  # the convoy reaches static-hq (a "bridge" here) and stops
    assert lead.last_node == "static-hq" and not lead.path
    held = armor.pos
    run(w, 100)
    assert armor.pos == held


def test_follow_hold_slack_decides_how_near_a_follower_holds_and_is_a_key() -> None:
    """A convoy stopped off base with an escort 600 m behind it: within 2 stations (1,000 m) the
    escort holds; with a slack of 0.5 (250 m) it closes in."""
    base = RULES.tasking
    assert base is not None

    def escort_moved(slack: float) -> bool:
        tasking = dataclasses.replace(base, follow_hold_slack=slack)
        rules = dataclasses.replace(
            RULES, tasking=tasking, node_kind={**RULES.node_kind, "static-hq": "BRIDGE"}
        )
        w = new_world(rules=rules)
        lead = on_road(w, "ENEMY_CONVOY", 69_000)
        armor = on_road(w, "ENEMY_ARMOR", 68_400)
        lead.path, lead.last_node = [], "static-hq"
        follow(armor, lead)
        start = armor.pos
        run(w, 50)
        return armor.pos != start

    assert not escort_moved(2.0) and escort_moved(0.5)


def test_an_aircraft_covers_a_ground_unit_within_3000_m() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    lead.path = ["fob-n-w"]
    uav = put(w, "RECON_UAV", "west-airbase")
    follow(uav, lead)
    run(w, 400)  # it takes off, catches up and orbits
    far = []
    for _ in range(600):
        step(w, [])
        far.append(math.hypot(uav.pos.x - lead.pos.x, uav.pos.y - lead.pos.y))
    assert max(far) <= TR.station_m["overwatch"] + 100 and uav.state in ("ON_STATION", "EN_ROUTE")


def test_a_wingman_flies_1000_m_off_its_lead() -> None:
    w = new_world()
    lead = put(w, "STRIKE_FIGHTER", "west-airbase")
    wing = put(w, "STRIKE_FIGHTER", "west-airbase")
    lead.path = [Vec2(190_000, 120_000)]
    hurt(lead, 50, "DAMAGED")  # 187.5 m/s: the wingman, at 250, can close on it
    follow(wing, lead)
    run(w, 400)
    d = math.hypot(wing.pos.x - lead.pos.x, wing.pos.y - lead.pos.y)
    assert d == pytest.approx(TR.station_m["wingman"], abs=30)


def test_aircraft_land_with_a_leader_and_take_off_after_it() -> None:
    w = new_world()
    lead = put(w, "STRIKE_FIGHTER", "west-airbase")
    wing = put(w, "STRIKE_FIGHTER", "haven")
    follow(wing, lead)
    run(w, 700)
    assert wing.state == "LANDED" and wing.last_node == "west-airbase"  # joined the landed lead
    lead.path = [Vec2(150_000, 120_000)]
    run(w, 80)
    assert lead.state == "EN_ROUTE" and wing.state in ("EN_ROUTE", "ON_STATION")
    assert wing.follow_id == lead.id  # it kept following


def test_an_aircraft_lands_where_its_ground_leader_parks_at_an_airbase() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "haven", cargo=100)
    lead.path = ["west-airbase"]
    uav = put(w, "RECON_UAV", "haven")
    follow(uav, lead)
    run(w, 6_000)
    assert lead.last_node == "west-airbase" and uav.state == "LANDED"
    assert uav.last_node == "west-airbase"


def test_followers_keep_their_role_a_recon_follower_still_scans() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    lead.path = ["fob-n-w"]
    uav = put(w, "RECON_UAV", "west-airbase")
    follow(uav, lead)
    foe = unit(w, "ENEMY_ARMOR")
    foe.pos, foe.last_node = Vec2(110_000, 100_000), None
    run(w, 300)
    assert foe.id in w.contacts["COALITION"]


# --- chains and leader loss ---------------------------------------------------------------------


def chain(w: World) -> tuple[Entity, Entity, Entity]:
    a, b, c = (put(w, "LOGI_TRUCK", "west-airbase", AI) for _ in range(3))
    follow(b, a)
    follow(c, b)
    return a, b, c


def test_a_departing_middle_leader_hands_its_followers_to_its_leader() -> None:
    w = new_world()
    a, b, c = chain(w)
    lose_unit(w, b, [])
    assert (c.follow_id, c.order) == (a.id, "FOLLOW")
    lose_unit(w, a, [])
    assert (c.follow_id, c.order) == (None, None)  # none left: back to the board


def test_a_disabled_leader_is_left_by_its_followers() -> None:
    w = new_world()
    a, b, c = chain(w)
    b.damage_state = "DISABLED"
    steer(w)
    assert (c.follow_id, b.follow_id, b.order) == (a.id, None, None)
    a.damage_state = "DISABLED"
    steer(w)
    assert (c.follow_id, c.order) == (None, None)


def test_a_follower_whose_leader_is_lost_returns_to_the_board() -> None:
    w = new_world()
    w.stock["fob-n-w"] = 0
    lead = put(w, "LOGI_TRUCK", "west-airbase", AI, cargo=100)
    esc = put(w, "STRIKE_FIGHTER", "west-airbase")
    follow(esc, lead)
    lose_unit(w, lead, [])
    assert esc.order is None
    board_pass(w)
    assert esc.job_id is None or w.boards["COALITION"][esc.job_id].kind != "ESCORT_CONVOY"
    assert esc.follow_id is None


# --- escort jobs --------------------------------------------------------------------------------


def ring(w: World, side: Side, x: float, y: float, state: DamageState = "HEALTHY") -> None:
    """`side` has discovered a SAM site's 35 km ring at (x, y): the marker of a real site of the
    other side (a marker names a live entity of its kind), moved to the point."""
    site = next(e for e in w.entities() if e.kind == "AIR_DEFENSE_SITE" and e.side != side)
    w.markers[side][site.id] = FacilityMarker(site.kind, "SAM", Vec2(x, y), True, 0, 35_000, state)


def threatened_truck(w: World) -> Entity:
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    truck.path = ["fob-n-w"]
    return truck


def test_a_truck_route_through_a_known_ring_posts_an_escort_job() -> None:
    w = new_world()
    truck = threatened_truck(w)
    put(w, "STRIKE_FIGHTER", "west-airbase", owner=AI)  # staff the kind
    assert [j.kind for j in jobs(w)] == []
    ring(w, "COALITION", 110_000, 90_000)
    events = board_pass(w)
    (job,) = [j for j in jobs(w) if j.kind == "ESCORT_CONVOY"]
    created = [e for e in events if e.kind == "JobCreated"]
    assert (job.key, job.entity, job.slots, job.node, job.blob) == (
        f"escort:{truck.id}",
        truck.id,
        TR.slots["ESCORT_CONVOY"],
        None,
        None,
    )
    assert created[0].job_kind == "ESCORT_CONVOY" and created[0].entity_id == truck.id
    assert TR.slots["ESCORT_CONVOY"] == 2 and TR.priority["ESCORT_CONVOY"] == 40


def test_a_disabled_ring_a_far_ring_or_no_ring_posts_nothing() -> None:
    w = new_world()
    threatened_truck(w)
    put(w, "STRIKE_FIGHTER", "west-airbase", owner=AI)
    ring(w, "COALITION", 110_000, 90_000, "DISABLED")
    assert not [j for j in jobs(w) if j.kind == "ESCORT_CONVOY"] and board_pass(w) == []
    ring(w, "COALITION", 110_000, 10_000)  # 110 km off the route, ring 35 km
    board_pass(w)
    assert not [j for j in jobs(w) if j.kind == "ESCORT_CONVOY"]


def test_a_tracked_enemy_posts_the_job_but_a_last_known_track_does_not() -> None:
    w = new_world()
    truck = threatened_truck(w)
    put(w, "RECON_UAV", "west-airbase", owner=AI)
    foe = unit(w, "ENEMY_ARMOR")
    foe.pos = Vec2(110_000, 80_000)
    w.contacts["COALITION"][foe.id] = Contact("ENEMY_ARMOR", foe.pos, Vec2(0, 0), age=40)
    board_pass(w)
    assert not [j for j in jobs(w) if j.kind == "ESCORT_CONVOY"]  # last-known only
    w.contacts["COALITION"][foe.id] = Contact("ENEMY_ARMOR", foe.pos, Vec2(0, 0))
    board_pass(w)
    assert [j.entity for j in jobs(w) if j.kind == "ESCORT_CONVOY"] == [truck.id]
    w.contacts["COALITION"].clear()  # an unseen emitter or enemy: the condition ended
    assert "JobExpired" in [e.kind for e in board_pass(w)]


def test_players_take_an_escort_job_as_a_follow_order_the_garrison_never_does() -> None:
    w = new_world()
    truck = threatened_truck(w)
    ring(w, "COALITION", 110_000, 90_000)
    garrison = put(w, "STRIKE_FIGHTER", "west-airbase", owner=AI)
    board_pass(w)
    assert garrison.job_id is None or w.boards["COALITION"][garrison.job_id].kind != "ESCORT_CONVOY"
    player = put(w, "RECON_UAV", "west-airbase")
    for _ in range(3):
        board_pass(w)
    job = next(j for j in jobs(w) if j.kind == "ESCORT_CONVOY")
    assert player.id in job.claims and (player.follow_id, player.order) == (truck.id, None)
    assert garrison.id not in job.claims
    # A human claim does not open it to the garrison either.
    assert not _may(w, garrison, job)


def _may(w: World, e: Entity, job: object) -> bool:
    from nexus.core.tasking import _may_take

    return _may_take(w, TR, e, job)  # type: ignore[arg-type]


def test_the_escort_job_ends_done_when_the_truck_arrives_with_a_follower() -> None:
    w = new_world()
    truck = threatened_truck(w)
    ring(w, "COALITION", 110_000, 90_000)
    player = put(w, "RECON_UAV", "west-airbase")
    board_pass(w)
    board_pass(w)
    assert player.follow_id == truck.id
    truck.path = []  # it arrived
    events = board_pass(w)
    assert [e.participants[0].entity_id for e in of(events, JobDone)] == [player.id]
    assert player.follow_id is None and player.job_id is None


def test_an_unclaimed_escort_job_expires_when_the_truck_arrives() -> None:
    w = new_world()
    truck = threatened_truck(w)
    ring(w, "COALITION", 110_000, 90_000)
    put(w, "STRIKE_FIGHTER", "west-airbase", owner=AI)
    board_pass(w)
    truck.path = []
    assert len(of(board_pass(w), JobExpired)) == 1


def test_the_escort_job_fails_when_the_truck_is_lost_and_frees_the_escort() -> None:
    w = new_world()
    truck = threatened_truck(w)
    ring(w, "COALITION", 110_000, 90_000)
    player = put(w, "RECON_UAV", "west-airbase")
    board_pass(w)
    board_pass(w)
    lose_unit(w, truck, [])
    assert player.follow_id is None
    events = board_pass(w)
    assert [e.kind for e in events if e.kind in ("JobFailed", "JobExpired")]
    assert not [j for j in jobs(w) if j.kind == "ESCORT_CONVOY"] and player.job_id is None


def test_the_static_ai_may_take_the_job_by_the_same_rule() -> None:
    w = new_world()
    truck = on_road(w, "ENEMY_CONVOY", 1_000)
    ring(w, "ENEMY", 330_000, 100_000)
    pilot = put(w, "ENEMY_STRIKE_FIGHTER", "east-airbase", DIRECTOR)
    board_pass(w)
    board_pass(w)
    assert pilot.follow_id == truck.id and any(j.kind == "ESCORT_CONVOY" for j in jobs(w, "ENEMY"))


def test_only_aircraft_that_fight_or_scan_fit_an_escort_job() -> None:
    fit = {k for k in RULES.domain if fits(RULES, k, "ESCORT_CONVOY")}
    assert fit == {
        "STRIKE_FIGHTER",
        "RECON_UAV",
        "ENEMY_STRIKE_FIGHTER",
        "ENEMY_FIGHTER",
        "ENEMY_RECON_UAV",
    }


# --- formation speed ----------------------------------------------------------------------------


KINDS = st.sampled_from(["ENEMY_CONVOY", "ENEMY_ARMOR"])


@given(
    escorts=st.lists(
        st.tuples(KINDS, st.integers(0, 2_500), st.booleans(), st.integers(0, 3)),
        min_size=1,
        max_size=4,
    ),
    lead_hurt=st.booleans(),
    ticks=st.integers(30, 120),
)
@settings(max_examples=40)
def test_a_group_never_moves_faster_than_its_slowest_member(
    escorts: list[tuple[UnitKind, int, bool, int]], lead_hurt: bool, ticks: int
) -> None:
    """Every unit that is not still catching up keeps to the slowest of its group; one that leads
    followers is kept to the slowest of its own sub-group even while it catches up."""
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 3_000)
    if lead_hurt:
        hurt(lead, 30, "DAMAGED")
    members = [lead]
    for kind, behind, hurt_it, parent in escorts:
        f = on_road(w, kind, 3_000 - behind)
        if hurt_it:
            hurt(f, 80, "DAMAGED")
        follow(f, members[parent % len(members)])  # a chain or a fan, never a loop
        members.append(f)
    top = {m.id: RULES.speed(m.kind, m.damage_state) for m in members}
    for _ in range(ticks):
        step(w, [])
        near = [m for m in members if abs(m.pos.x - lead.pos.x) <= TR.leash_m]
        slowest = min(top[m.id] for m in near)
        for m in near:
            catching = m is not lead and m.vel.x >= top[m.id] - 1e-9
            followers = [f for f in near if f.follow_id == m.id]
            below = [f for f in near if _under(f, m, members)]
            if not catching:
                assert m.vel.x <= slowest + 1e-9  # the group's slowest member
            if followers:
                assert m.vel.x <= min(top[f.id] for f in below) + 1e-9  # its sub-group's


def _under(f: Entity, root: Entity, members: list[Entity]) -> bool:
    by_id = {m.id: m for m in members}
    at = f
    while at.follow_id is not None:
        if at.follow_id == root.id:
            return True
        at = by_id[at.follow_id]
    return False


def test_a_convoy_is_held_to_its_damaged_escort_on_either_side() -> None:
    for lead_kind, escort_kind in (("ENEMY_CONVOY", "ENEMY_ARMOR"),):
        w = new_world()
        lead = on_road(w, lead_kind, 600)  # type: ignore[arg-type]
        escort = on_road(w, escort_kind, 0)  # type: ignore[arg-type]
        hurt(escort, 60, "MISSION_KILL")  # 0.75 x 20
        follow(escort, lead)
        run(w, 50)
        assert lead.vel.x == pytest.approx(15.0)
    w = new_world()
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    truck.path = ["fob-n-w"]
    inf = put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    follow(inf, truck)
    run(w, 50)
    assert speed(truck) == pytest.approx(5.0) and speed(inf) == pytest.approx(5.0)


def test_aircraft_are_outside_the_formation_speed() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    lead.path = ["fob-n-w"]
    uav = put(w, "RECON_UAV", "west-airbase")
    follow(uav, lead)
    run(w, 100)
    assert speed(lead) == pytest.approx(25.0) and uav.id not in w.speed_cap


# --- escorts answer threats from any side -------------------------------------------------------


def threat_scene(behind: float, *, tracked: bool = True) -> tuple[World, Entity, Entity, Entity]:
    """A convoy at 330 km with its armor escort 500 m ahead, and a coalition infantry attacker
    `behind` metres behind the convoy that fired at it lately. The armor senses 8 km."""
    w = new_world()
    for site in [e for e in w.entities() if e.kind in ("RADAR_SITE", "AIR_DEFENSE_SITE")]:
        w.remove(site.id)  # their radars would see the whole strip: the fog is the units' own
    lead = on_road(w, "ENEMY_CONVOY", 20_000)
    armor = on_road(w, "ENEMY_ARMOR", 20_500)
    follow(armor, lead)
    foe = unit(w, "GARRISON_INFANTRY", AI)
    foe.pos, foe.last_node, foe.path = Vec2(EAST + 20_000 - behind, ROAD_Y), None, []
    lead.fired_by = [[foe.id, w.campaign.running_ticks + 1]]
    if tracked:
        w.contacts["ENEMY"][foe.id] = Contact("GARRISON_INFANTRY", foe.pos, Vec2(0, 0))
    return w, lead, armor, foe


def test_an_attacker_behind_the_column_is_engaged_and_the_escort_then_returns() -> None:
    w, lead, armor, foe = threat_scene(
        4_100
    )  # 4.6 km from the armor: past its gun, out of its station, inside the leash
    hurt(lead, 30, "DAMAGED")  # 18.75 m/s: the armor, at 20, can close on it again
    steer(w)
    assert w.group_threat[armor.id] == (foe.id,)
    assert armor.path and armor.path[-1] == "east-airbase"  # it turns back along the road for it
    shots = 0
    for _ in range(150):
        shots += len(of(step(w, []), WeaponFired))
        w.contacts["ENEMY"][foe.id] = Contact("GARRISON_INFANTRY", foe.pos, Vec2(0, 0))
    assert (shots > 0 and w.find(foe.id) is None) or foe.hp < 80  # it was engaged
    assert gap(armor, lead) < 0  # off station, behind the column it covers
    for _ in range(3_500):  # the memory ran out: it returns to station
        step(w, [])
    assert armor.id not in w.group_threat
    assert gap(armor, lead) == pytest.approx(TR.station_m["escort"], abs=40)


def test_group_threats_are_shot_before_anything_else() -> None:
    w, _lead, armor, foe = threat_scene(3_000)
    near = unit(w, "GARRISON_INFANTRY", AI)  # nearer, in the armor's range, not a group threat
    near.pos, near.last_node = Vec2(armor.pos.x, ROAD_Y - 2_500), None
    w.contacts["ENEMY"][near.id] = Contact("GARRISON_INFANTRY", near.pos, Vec2(0, 0))
    steer(w)
    events = step(w, [])
    first = [e.target_id for e in of(events, WeaponFired) if e.shooter_id == armor.id]
    assert first and first[0] == foe.id


def test_an_attacker_beyond_the_leash_is_not_chased() -> None:
    w, _lead, armor, _foe = threat_scene(TR.leash_m + 2_000)
    steer(w)
    assert armor.id in w.group_threat  # known, tracked, but too far
    assert armor.path == ["static-hq"]  # it kept its station, not turned back along the road


def test_an_untracked_attacker_is_not_engaged() -> None:
    w, lead, armor, foe = threat_scene(9_000, tracked=False)  # beyond the armor's 8 km sensor
    steer(w)
    assert armor.id not in w.group_threat
    run(w, 50)
    assert gap(armor, lead) >= TR.station_m["escort"] - 60 and w.find(foe.id) is not None


def test_a_threat_in_weapon_range_of_any_member_counts_without_a_recorded_shot() -> None:
    w, lead, armor, foe = threat_scene(1_000)
    lead.fired_by = []
    steer(w)
    assert w.group_threat[armor.id] == (foe.id,)  # infantry range 1,500 m reaches the convoy
    w2, lead2, armor2, _foe2 = threat_scene(3_000)
    lead2.fired_by = []
    steer(w2)
    assert armor2.id not in w2.group_threat


def test_a_threat_is_forgotten_after_the_memory() -> None:
    w, _lead, armor, _foe = threat_scene(3_000)
    steer(w)
    assert armor.id in w.group_threat
    w.campaign.running_ticks += TR.threat_memory_ticks + 1
    steer(w)
    assert armor.id not in w.group_threat


def test_an_aircraft_escort_breaks_station_toward_a_threat_and_unarmed_followers_do_not() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    lead.path = ["fob-n-w"]
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    col = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    follow(jet, lead)
    follow(col, lead)
    foe = unit(w, "ENEMY_ARMOR")
    jet.pos = Vec2(90_000, 129_000)  # 12.7 km from the foe, past its 10 km gun
    foe.pos, foe.last_node, foe.path = Vec2(81_000, 120_000), None, []
    w.contacts["COALITION"][foe.id] = Contact("ENEMY_ARMOR", foe.pos, Vec2(0, 0))
    lead.fired_by = [[foe.id, 1]]
    steer(w)
    assert jet.path == [foe.pos] and w.group_threat == {jet.id: (foe.id,)}
    assert col.id not in w.group_threat


def test_an_escort_off_station_does_not_slow_the_convoy() -> None:
    w, lead, _armor, _foe = threat_scene(6_000)
    run(w, 5)
    assert lead.vel.x == pytest.approx(25.0)  # the armor (20) is engaging: outside the formation


def test_threat_memory_is_60_world_seconds() -> None:
    assert TR.threat_memory_ticks == 100  # 60 s at 0.6 world s per tick, not game time


def test_a_threats_reach_comes_from_the_catalog_not_its_live_ammo() -> None:
    w, lead, armor, foe = threat_scene(1_000)
    lead.fired_by = []
    foe.ammo = [0]  # hidden to the other side: the infantry's SMALL_ARMS still reach the convoy
    steer(w)
    assert w.group_threat[armor.id] == (foe.id,)


def at_edge(w: World, kind: UnitKind, x: float, y: float, last: str, path: list[str]) -> Entity:
    e = unit(w, kind, AI)
    e.pos, e.last_node, e.path = Vec2(x, y), last, [*path]
    return e


@pytest.mark.parametrize("eastbound", [True, False])
def test_an_ambush_beside_a_bridge_edge_is_answered_along_the_road(eastbound: bool) -> None:
    """fob-n-w - cross-n runs past the BRIDGE node bridge-n, which has no road: the nearest node
    to a threat at 203 km is unroutable, so the escort turns along the edge instead."""
    w = new_world()
    for site in [e for e in w.entities() if e.kind in ("RADAR_SITE", "AIR_DEFENSE_SITE")]:
        w.remove(site.id)
    last, path = ("fob-n-w", ["cross-n"]) if eastbound else ("cross-n", ["fob-n-w"])
    lead = at_edge(w, "ENEMY_CONVOY", 210_000, 60_000, last, path)
    armor = at_edge(w, "ENEMY_ARMOR", 210_000 + (500 if eastbound else -500), 60_000, last, path)
    follow(armor, lead)
    foe = unit(w, "GARRISON_INFANTRY", AI)
    foe.pos, foe.last_node = Vec2(203_000 if eastbound else 217_000, 60_000), None
    lead.fired_by = [[foe.id, w.campaign.running_ticks + 1]]
    w.contacts["ENEMY"][foe.id] = Contact("GARRISON_INFANTRY", foe.pos, Vec2(0, 0))
    steer(w)
    assert armor.path == [last]  # back along the edge it is on, toward the foe
    before = math.hypot(armor.pos.x - foe.pos.x, armor.pos.y - foe.pos.y)
    run(w, 30)
    assert math.hypot(armor.pos.x - foe.pos.x, armor.pos.y - foe.pos.y) < before


def test_an_escort_keeps_station_when_no_road_leads_toward_the_threat() -> None:
    w = new_world()
    for site in [e for e in w.entities() if e.kind in ("RADAR_SITE", "AIR_DEFENSE_SITE")]:
        w.remove(site.id)
    lead = at_edge(w, "ENEMY_CONVOY", 249_500, 60_000, "cross-n", ["fob-n-e"])
    armor = at_edge(w, "ENEMY_ARMOR", 250_000, 60_000, "cross-n", ["fob-n-e"])
    follow(armor, lead)
    foe = unit(w, "GARRISON_INFANTRY", AI)
    foe.pos, foe.last_node = (
        Vec2(250_000, 66_000),
        None,
    )  # abeam of the armor: both legs only lead away
    lead.fired_by = [[foe.id, w.campaign.running_ticks + 1]]
    w.contacts["ENEMY"][foe.id] = Contact("GARRISON_INFANTRY", foe.pos, Vec2(0, 0))
    steer(w)
    assert armor.path[-1] == "fob-n-e"  # no leg gets closer than it is: it stayed on station


def test_escorts_cannot_leapfrog_away_from_the_convoy() -> None:
    w = new_world()
    lead = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    lead.path = ["fob-n-w"]
    near = put(w, "STRIKE_FIGHTER", "west-airbase")
    far = put(w, "STRIKE_FIGHTER", "west-airbase")
    follow(near, lead)
    follow(far, lead)
    near.pos = Vec2(90_000, 120_000 - 11_000)  # past the leash itself, so it keeps station
    far.pos = Vec2(90_000, 120_000 - 12_000)  # 1 km from `near`, 12 km from the convoy
    foe = unit(w, "ENEMY_ARMOR")
    foe.pos, foe.last_node, foe.path = Vec2(83_000, 120_000), None, []  # 7 km from the convoy
    w.contacts["COALITION"][foe.id] = Contact("ENEMY_ARMOR", foe.pos, Vec2(0, 0))
    lead.fired_by = [[foe.id, w.campaign.running_ticks + 1]]
    steer(w)
    assert far.path == [lead.pos] and near.path == [lead.pos]  # both return, neither chases
    near.pos = Vec2(90_000, 120_000 - 8_000)  # inside the leash: it does chase (10 km gun)
    steer(w)
    assert near.path == [foe.pos]


@pytest.mark.parametrize(
    "build",
    [
        lambda w, a, j, st_: follow(a, j),  # ground after an aircraft
        lambda w, a, j, st_: follow(j, st_),  # air after a STATIC unit
        lambda w, a, j, st_: follow(st_, a),  # a STATIC unit after ground
        lambda w, a, j, st_: follow(a, st_),  # ground after a STATIC unit
    ],
)
def test_a_follow_state_no_command_can_make_is_dropped_not_crashed(build) -> None:  # type: ignore[no-untyped-def]
    w = new_world()
    a = put(w, "GARRISON_INFANTRY", "west-airbase", AI)
    j = put(w, "STRIKE_FIGHTER", "west-airbase")
    st_ = next(e for e in w.entities() if e.kind == "RADAR_SITE" and e.side == "COALITION")
    build(w, a, j, st_)
    run(w, 5)  # steer drops it; nothing raises
    assert all(e.follow_id is None for e in (a, j, st_))


def test_a_snapshot_with_a_facility_in_a_follow_link_is_refused() -> None:
    w = new_world()
    j = put(w, "STRIKE_FIGHTER", "west-airbase")
    site = next(e for e in w.entities() if e.kind == "RADAR_SITE" and e.side == "COALITION")
    follow(j, site)
    with pytest.raises(ValueError, match="facility"):
        load(save(w))


def _escort_brute(w: World, side: Side) -> set[int]:
    """The escort rule written plainly: every carrier route against every ring and track."""
    view = side_view(w, side)
    out = set()
    for e in w.entities():
        if (
            e.side != side or e.kind not in RULES.supply.carriers or not e.path
            or e.follow_id is not None or e.damage_state == "DISABLED"
        ):  # fmt: skip
            continue
        route = [(e.pos.x, e.pos.y), *(RULES.roads.pos[str(p)] for p in e.path)]
        rings = [m for m in view.markers.values() if m.ring_m is not None and m.state != "DISABLED"]
        if any(
            _near_route(_segments(route), m.pos.x, m.pos.y, m.ring_m or 0) for m in rings
        ) or any(
            _near_route(_segments(route), c.pos.x, c.pos.y, TR.defend_radius_m)
            for c in view.tracks.values()
        ):
            out.add(e.id)
    return out


NODES = sorted(RULES.roads.pos)


@given(
    carriers=st.lists(
        st.tuples(
            st.sampled_from(NODES),
            st.lists(st.sampled_from(NODES), max_size=4),
            st.sampled_from(["COALITION", "ENEMY"]),
            st.booleans(),
        ),
        max_size=12,
    ),
    rings=st.lists(
        st.tuples(
            st.integers(0, 400_000),
            st.integers(0, 240_000),
            st.integers(1_000, 60_000),
            st.booleans(),
        ),
        max_size=3,
    ),
    tracks=st.lists(
        st.tuples(st.integers(0, 400_000), st.integers(0, 240_000), st.booleans()), max_size=30
    ),
)
@settings(max_examples=60)
def test_escort_generation_matches_the_plain_scan(
    carriers: list[tuple[str, list[str], Side, bool]],
    rings: list[tuple[int, int, int, bool]],
    tracks: list[tuple[int, int, bool]],
) -> None:
    w = new_world()
    for node, path, side, follows in carriers:
        kind: UnitKind = "ENEMY_CONVOY" if side == "ENEMY" else "LOGI_TRUCK"
        e = w.spawn(kind, side, DIRECTOR if side == "ENEMY" else AI, Vec2(*RULES.roads.pos[node]))
        e.path = [*path]
        if follows and w._next_entity_id > 2:
            e.follow_id = None  # a follower is skipped; the flag only varies the mix
            e.damage_state = "DISABLED"
    for side in ("COALITION", "ENEMY"):
        sites = [e for e in w.entities() if e.kind == "AIR_DEFENSE_SITE" and e.side != side]
        for site, (x, y, ring, off) in zip(sites, rings, strict=False):
            w.markers[side][site.id] = FacilityMarker(
                site.kind, "SAM", Vec2(x, y), True, 0, ring, "DISABLED" if off else "HEALTHY"
            )
        foes = [e for e in w.entities() if e.side != side]
        for foe, (x, y, tracked) in zip(foes, tracks, strict=False):
            w.contacts[side][foe.id] = Contact(
                foe.kind, Vec2(x, y), Vec2(0, 0), None if tracked else 3
            )
        found = {
            int(sp.key.split(":")[1]) for sp in _escort(w, RULES, TR, side, side_view(w, side))
        }
        assert found == _escort_brute(w, side)


# --- pause, snapshots, determinism --------------------------------------------------------------


def test_a_pause_freezes_followers_and_their_steering() -> None:
    w = new_world()
    lead = on_road(w, "ENEMY_CONVOY", 1_000)
    armor = on_road(w, "ENEMY_ARMOR", 0)
    follow(armor, lead)
    run(w, 10)
    w.campaign.clock_paused, w.campaign.pause_reason = True, "STAFF"
    before = to_canonical(w, quantize=True)["entities"]
    run(w, 30)
    assert to_canonical(w, quantize=True)["entities"] == before
    assert w.speed_cap == {} and w.group_threat == {}


def follow_scene(seed: int = 3) -> World:
    w = new_world(seed)
    lead = on_road(w, "ENEMY_CONVOY", 1_000)
    armor = on_road(w, "ENEMY_ARMOR", 0)
    follow(armor, lead)
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=100)
    truck.path = ["fob-n-w"]
    uav = put(w, "RECON_UAV", "west-airbase")
    follow(uav, truck)
    ring(w, "COALITION", 110_000, 90_000)
    run(w, 130)
    return w


def test_a_snapshot_round_trips_followers_and_the_run_continues_identically() -> None:
    w = follow_scene()
    assert any(e.follow_id for e in w.entities())
    again = load(save(w))
    again.rules = RULES
    assert state_hash(again) == state_hash(w)
    live, restored = [], []
    for _ in range(400):
        live += step(w, [])
        restored += step(again, [])
    assert live == restored and state_hash(again) == state_hash(w)


def test_same_seed_same_follow_run() -> None:
    assert state_hash(follow_scene(7)) == state_hash(follow_scene(7))


def test_format_17_snapshots_are_refused() -> None:
    raw = msgpack.unpackb(save(follow_scene()), raw=False)
    raw["v"] = 17
    with pytest.raises(ValueError, match="unsupported snapshot format version 17"):
        load(msgpack.packb(raw, use_bin_type=True))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda e: e.update(follow_id=e["id"]), "follow loop"),
        (lambda e: e.update(follow_id=9999), "gone or of the other side"),
        (lambda e: e.update(order=None), "do not match"),
        (lambda e: e.update(order="FOLLOW", follow_id=None), "do not match"),
    ],
)
def test_a_corrupt_follower_is_refused(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    raw = msgpack.unpackb(save(follow_scene()), raw=False)
    mutate(next(e for e in raw["entities"] if e["order"] == "FOLLOW"))
    with pytest.raises(ValueError, match=message):
        load(msgpack.packb(raw, use_bin_type=True))


def test_a_follower_of_the_other_side_is_refused() -> None:
    raw = msgpack.unpackb(save(follow_scene()), raw=False)
    follower = next(e for e in raw["entities"] if e["order"] == "FOLLOW" and e["side"] == "ENEMY")
    follower["follow_id"] = next(e["id"] for e in raw["entities"] if e["side"] == "COALITION")
    with pytest.raises(ValueError, match="other side"):
        load(msgpack.packb(raw, use_bin_type=True))


def test_follow_steering_stays_within_budget_at_1000_entities() -> None:
    """SC-10: 100 convoys (a leader, three escorts, three column trucks) on the Static's road with
    300 coalition infantry among them, which the escorts really track: a full `step` at 1,000
    entities. Printed; the bound is generous, the 25 ms p99 is the reference host's."""
    w = new_world()
    for site in [e for e in w.entities() if e.kind in ("RADAR_SITE", "AIR_DEFENSE_SITE")]:
        w.remove(site.id)
    for c in range(100):
        base = 600 * c
        lead = on_road(w, "ENEMY_CONVOY", base)
        for k in range(3):
            follow(on_road(w, "ENEMY_ARMOR", base + 500 - 100 * k), lead)
        for k in range(3):
            follow(on_road(w, "ENEMY_CONVOY", base - 200 - 100 * k), lead)
    leads = [e for e in w.entities() if e.kind == "ENEMY_CONVOY" and e.follow_id is None]
    for k in range(300):  # 6 km off the road: tracked (8 km optics), out of every gun's range
        foe = unit(w, "GARRISON_INFANTRY", AI)
        foe.pos, foe.last_node = Vec2(EAST + 200 * k, ROAD_Y + 6_000), None
        if k % 3 == 0:  # a third of the convoys were fired at lately: real threats to find
            leads[k // 3].fired_by = [[foe.id, w.campaign.running_ticks + 1]]
    assert len(w) >= 1_000
    run(w, 40)  # sensing tracks the infantry, fire opens
    assert len(w.group_threat) >= 100
    for k in range(10):  # trucks bound for the infantry's strip: the board has escort work too
        truck = w.spawn("ENEMY_CONVOY", "ENEMY", DIRECTOR, Vec2(EAST, ROAD_Y + 10 * k))
        truck.last_node, truck.path = "east-airbase", ["static-hq"]
    board: list[float] = []
    plain: list[float] = []
    for _ in range(200):
        due = (w.campaign.running_ticks + 1) % EVERY == 0
        start = time.perf_counter()
        step(w, [])
        (board if due else plain).append((time.perf_counter() - start) * 1000)
    tracked = len(w.contacts["ENEMY"])
    for name, ms in (("board-pass tick", board), ("other tick", plain)):
        ms.sort()
        print(
            f"follow step at {len(w)} entities, {tracked} tracked, {name}: "
            f"mean {statistics.mean(ms):.1f} ms, p99 {ms[-1]:.1f} ms ({len(ms)} ticks)"
        )
    assert board and plain and tracked >= 100
    assert all(statistics.mean(ms) < 50 and max(ms) < 100 for ms in (board, plain))
