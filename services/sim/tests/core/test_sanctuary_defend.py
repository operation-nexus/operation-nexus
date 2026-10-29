"""NX-493 (Q-TD-122 (a), GAMEPLAY §1b `defend:` and §9 last stand): a struck sanctuary posts
`defend:<sanctuary>` at the top urgency while its defense hp is below full and the coalition
tracks an enemy aircraft or ground unit within `tasking.defend_radius_m` of it (the lead's
refinement, so the job never outlives the threat), and the hit that takes it below full emits the
`SANCTUARY_AT_RISK` sitrep. Built on the Tasking Board fixtures
(`test_tasking`: strait-1, haven is the coalition sanctuary; the Static has its own rear)."""

import dataclasses

from test_tasking import AI, EVERY, RULES, TR, board_pass, jobs, kinds, new_world, post, put

from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.contracts.gen.events.campaign_ended import CampaignEnded
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.threat_adaptation import ThreatAdaptation
from nexus.core.defense import damage, heal
from nexus.core.fog import side_view
from nexus.core.step import step
from nexus.core.tasking_gen import generate
from nexus.core.world import Contact, Entity, Job, Vec2, World, state_hash
from nexus.runtime.campaign_config import load_campaign_config

HAVEN = "haven"
_D = RULES.defense
assert _D is not None
FULL = _D.max_hp[HAVEN]
STATIC_REAR = RULES.supply.rear["ENEMY"]
STATIC_FULL = _D.max_hp[STATIC_REAR]


def defends(w: World, side: Side = "COALITION") -> list[tuple[str | None, int, int]]:
    return [(j.node, j.slots, j.urgency) for j in w.boards[side].values() if j.kind == "DEFEND"]


def at_risk(events: list[Event]) -> list[str | None]:
    return [
        e.node_id
        for e in events
        if isinstance(e, ThreatAdaptation) and e.category == "SANCTUARY_AT_RISK"
    ]


def threat(
    w: World, *, node: str = HAVEN, side: Side = "COALITION", kind: UnitKind = "ENEMY_FIGHTER",
    dist: float = 5000.0,
) -> Entity:  # fmt: skip
    """An enemy unit `dist` m east of `node` that `side` tracks now (FOG-OF-WAR Tier 2)."""
    x, y = RULES.roads.pos[node]
    owner: OwnerKind = "ENEMY_DIRECTOR" if side == "COALITION" else "COMMANDER"
    e = w.spawn(kind, "ENEMY" if side == "COALITION" else "COALITION", owner, Vec2(x + dist, y))
    w.contacts[side][e.id] = Contact(kind, e.pos, Vec2(0, 0))
    return e


def lose_track(w: World, e: Entity) -> None:
    del w.contacts["COALITION"][e.id]


def test_a_struck_sanctuary_posts_its_defend_job_at_the_top_urgency() -> None:
    w = new_world()
    put(w, "STRIKE_FIGHTER", "west-airbase")
    jet = threat(w)
    board_pass(w)
    assert defends(w) == []  # full hp: nothing to defend, though a striker is tracked
    w.defense_hp[HAVEN] = FULL - 1
    board_pass(w)
    # tasking.slots.defend (2) slots, tasking.urgency_max (2.0) whatever the damage
    assert defends(w) == [(HAVEN, 2, 2000)]
    assert TR.urgency_max_milli == 2000
    w.defense_hp[HAVEN] = 0
    board_pass(w)
    assert defends(w) == [(HAVEN, 2, 2000)] and len(jobs(w)) == 1  # the same job, no repost
    assert jet.id in w.contacts["COALITION"]


def test_damage_alone_or_a_threat_out_of_range_or_untracked_posts_nothing() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    board_pass(w)
    assert defends(w) == []  # below full, but nobody tracked near it (the siege is over)
    far = threat(w, dist=TR.defend_radius_m + 1)  # just beyond tasking.defend_radius_m
    board_pass(w)
    assert defends(w) == []
    lose_track(w, far)
    site = threat(w, kind="AIR_DEFENSE_SITE", dist=1000)  # a facility is no aircraft or ground unit
    board_pass(w)
    assert defends(w) == []
    lose_track(w, site)
    near = threat(w, dist=TR.defend_radius_m)  # at the radius: in range
    w.contacts["COALITION"][near.id].age = 5  # a last-known track does not count
    board_pass(w)
    assert defends(w) == []
    w.contacts["COALITION"][near.id].age = None
    board_pass(w)
    assert defends(w) == [(HAVEN, 2, 2000)]


BASE = "west-airbase"
BASE_FULL = _D.max_hp[BASE]


def _damaged_base_with_a_fighter() -> tuple[World, Entity]:
    w = new_world()
    w.defense_hp[BASE] = BASE_FULL - 100
    return w, threat(w, node=BASE, dist=2000)


def test_a_tracked_aircraft_posts_no_defend_job_at_a_damaged_base_other_than_the_sanctuary() -> (
    None
):
    """A base other than the sanctuary keeps the old rule: only a tracked ground unit or a capture
    bar posts its defend job, never a tracked aircraft (Q-TD-122 is the sanctuary's alone)."""
    w, _ = _damaged_base_with_a_fighter()
    put(w, "STRIKE_FIGHTER", BASE)
    board_pass(w)
    assert defends(w) == []


def test_a_tracked_aircraft_does_not_hold_open_a_claimed_defend_job_at_another_base() -> None:
    w, fighter = _damaged_base_with_a_fighter()
    job = post(w, "COALITION", "DEFEND", BASE, "d", urgency=5000)  # above any generated job
    jet = put(w, "STRIKE_FIGHTER", BASE)
    board_pass(w)
    assert jet.job_id == job.id
    jet.path, jet.last_node = [], BASE  # it is there; the fighter is still tracked
    assert fighter.id in w.contacts["COALITION"]
    events = board_pass(w)
    assert "JobDone" in kinds(events) and job.id not in w.boards["COALITION"]


def test_a_tracked_ground_unit_counts_too() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 1
    threat(w, kind="ENEMY_ARMOR", dist=9000)
    board_pass(w)
    assert defends(w) == [(HAVEN, 2, 2000)]


def test_an_armed_viewer_unit_and_an_ai_unit_take_it() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    threat(w)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    ai_jet = put(w, "STRIKE_FIGHTER", "west-airbase", AI)
    truck = put(w, "LOGI_TRUCK", "west-airbase")
    board_pass(w)
    (job,) = [j for j in jobs(w) if j.kind == "DEFEND"]
    assert jet.job_id == job.id and ai_jet.job_id == job.id
    assert truck.job_id != job.id  # a carrier only hauls (`fits`)
    assert jet.path == [HAVEN]


def _held() -> tuple[World, Job, Entity]:
    """A claimed defend job with its claimant at haven, the striker still tracked."""
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 100
    striker = threat(w)
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    (job,) = jobs(w)
    jet.path, jet.last_node = [], HAVEN  # it is there
    assert "JobDone" not in kinds(board_pass(w))  # still below full and menaced: it holds
    assert jobs(w) == [job]
    return w, job, striker


def test_the_job_ends_done_when_the_hp_is_full() -> None:
    w, _, _ = _held()
    w.defense_hp[HAVEN] = FULL
    events = board_pass(w)
    assert "JobDone" in kinds(events) and defends(w) == []


def test_the_job_ends_done_when_no_tracked_enemy_is_in_range_though_the_hp_is_still_low() -> None:
    w, _, striker = _held()
    lose_track(w, striker)
    events = board_pass(w)
    assert "JobDone" in kinds(events) and defends(w) == []
    assert w.defense_hp[HAVEN] == FULL - 100  # no repair exists yet (Q-TD-124)


def test_a_striker_that_is_only_a_last_known_track_ends_the_job_too() -> None:
    w, _, striker = _held()
    w.contacts["COALITION"][striker.id].age = 1  # lost this pass: no longer tracked
    events = board_pass(w)
    assert "JobDone" in kinds(events) and defends(w) == []


def test_an_unclaimed_job_is_withdrawn_when_the_threat_leaves_and_reposted_on_a_new_strike() -> (
    None
):
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 1
    first = threat(w)
    board_pass(w)  # a viewer can JOIN as STRIKE: the kind is staffable with no unit on the map
    (old,) = jobs(w)
    lose_track(w, first)
    assert kinds(board_pass(w)) == ["JobExpired"] and jobs(w) == []
    threat(w, dist=3000)  # the next strike package
    board_pass(w)
    (new,) = jobs(w)
    assert (new.key, new.urgency) == (old.key, 2000) and new.id != old.id


def test_an_unclaimed_job_is_withdrawn_once_the_hp_is_full() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 1
    threat(w)
    board_pass(w)
    assert defends(w) == [(HAVEN, 2, 2000)]
    w.defense_hp[HAVEN] = FULL
    assert kinds(board_pass(w)) == ["JobExpired"] and jobs(w) == []


def test_the_static_board_posts_nothing_for_a_struck_coalition_sanctuary() -> None:
    w = new_world()
    put(w, "ENEMY_FIGHTER", "east-airbase")
    threat(w)
    w.defense_hp[HAVEN] = 0
    board_pass(w)
    assert defends(w, "ENEMY") == []


def test_the_rule_is_the_same_for_the_static_rear_ec3() -> None:
    """EC-3: the rule names each side's own rear. The Static's is never struck in play (Q-SIM-64),
    so this only proves the generator treats it alike: below full, with a coalition unit tracked
    near it, the Static's board defends it."""
    w = new_world()
    put(w, "ENEMY_FIGHTER", "east-airbase")
    threat(w, node=STATIC_REAR, side="ENEMY", kind="STRIKE_FIGHTER")

    def static_defends() -> list[tuple[str | None, int]]:
        view = side_view(w, "ENEMY")
        specs = generate(w, RULES, TR, "ENEMY", view)
        return [(s.node, s.urgency) for s in specs if s.kind == "DEFEND"]

    assert static_defends() == []
    w.defense_hp[STATIC_REAR] = STATIC_FULL - 1
    assert static_defends() == [(STATIC_REAR, 2000)]


def test_a_hit_from_full_emits_one_sitrep_per_drop() -> None:
    w = new_world()
    put(w, "STRIKE_FIGHTER", "west-airbase")  # a viewer plays: no idle floor
    out: list[Event] = []
    damage(w, RULES, HAVEN, 10, out)
    (sitrep,) = [e for e in out if isinstance(e, ThreatAdaptation)]
    assert (sitrep.side, sitrep.direction, sitrep.node_id, sitrep.credit_ids) == (
        "ENEMY", "UP", HAVEN, []
    )  # fmt: skip
    assert sitrep.sector_id is not None
    ThreatAdaptation.model_validate(sitrep.model_dump())  # a valid wire event
    damage(w, RULES, HAVEN, 10, out)
    assert len(at_risk(out)) == 1  # already below full: no repeat
    heal(w, RULES, HAVEN, FULL, out)
    damage(w, RULES, HAVEN, 10, out)
    assert at_risk(out) == [HAVEN, HAVEN]  # a repair to full, then a new drop
    other: list[Event] = []
    damage(w, RULES, "west-airbase", 10, other)
    assert at_risk(other) == []  # only the sanctuary


def test_a_hit_that_leaves_the_hp_full_says_nothing() -> None:
    w = new_world()
    out: list[Event] = []
    damage(w, RULES, HAVEN, 0, out)  # a hit for no damage: still full
    assert at_risk(out) == [] and w.defense_hp[HAVEN] == FULL
    damage(w, RULES, HAVEN, 10, out)  # nobody plays: the idle floor (1 hp) still lets it drop
    assert at_risk(out) == [HAVEN]


def _siege(seed: int) -> tuple[World, list[Event]]:
    rc = load_campaign_config().rules.campaign
    assert rc is not None
    rules = dataclasses.replace(
        RULES, campaign=dataclasses.replace(rc, defeat_hold_ticks=3 * EVERY),
        track_every_ticks=10**9,
    )  # fmt: skip
    w = new_world(seed, rules)
    put(w, "STRIKE_FIGHTER", "west-airbase")
    threat(w, kind="ENEMY_ARMOR")  # tracked where it was seen: no tracking pass runs here
    w.defense_hp[HAVEN] = 0
    events: list[Event] = []
    while not w.campaign.ended:
        events += step(w, [])
    return w, events


def test_the_defend_job_stays_open_to_the_defeat_and_the_board_freezes_with_the_war() -> None:
    w, events = _siege(1)
    (ended,) = [e for e in events if isinstance(e, CampaignEnded)]
    assert (ended.result, ended.winner) == ("DEFEAT", "ENEMY")  # a defeat stays possible
    assert defends(w) == [(HAVEN, 2, 2000)]  # posted, never DONE at 0 hp
    assert step(w, []) == [] and defends(w) == [(HAVEN, 2, 2000)]  # frozen with the war (C-2)


def test_the_siege_is_deterministic() -> None:
    (a, ea), (b, eb) = _siege(7), _siege(7)
    assert state_hash(a) == state_hash(b) and ea == eb
