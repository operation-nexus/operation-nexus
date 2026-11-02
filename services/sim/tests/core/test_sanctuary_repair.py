"""NX-497 (Q-TD-124 owner (c) then (a); Q-TD-129 (1)-(5); GAMEPLAY §1b `resupply:`, §9, §11): the
sanctuary repair job. While the side's own sanctuary is below full defense hp the board posts
`resupply:<sanctuary>` (RESUPPLY, no new kind), with or without a contact; urgency
`tasking.urgency_max` while besieged or at 0 hp, else 1.0 plus the missing-hp share; slots the
LC-3 cap with that share as the need. Viewer trucks only. An empty truck takes it with no reload
and parks; `capture.sanctuary_repair_hp_per_s` (`defense._repair_sanctuaries`) does the repair and
the job is DONE with a claimant parked at full hp. Scenes reuse `test_tasking` (strait-1, board
passes by hand; haven is the coalition sanctuary at (20 km, 120 km), west-airbase at 90 km)."""

import dataclasses

from test_join import cid, join
from test_logistics_cadence import PERIOD, ai_trucks_of, at, cadence
from test_sanctuary_defend import FULL, HAVEN, STATIC_FULL, STATIC_REAR, threat
from test_tasking import AI, RULES, TR, board_pass, jobs, kinds, new_world, of, put

from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_failed import JobFailed
from nexus.core.fog import side_view
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking import idle_reason
from nexus.core.tasking_gen import generate
from nexus.core.world import Entity, Job, Vec2, World, load, save, state_hash

KEY = f"resupply:{HAVEN}"
SHIPPED_CAP: Rules = dataclasses.replace(  # LC-3 at the shipped 3 to 6 (Q-TD-128)
    RULES, tasking=dataclasses.replace(TR, resupply_slots_max_starving=6)
)


def repair(w: World) -> Job | None:
    return next((j for j in jobs(w) if j.key == KEY), None)


def posted(w: World) -> tuple[str, int, int] | None:
    j = repair(w)
    return None if j is None else (j.kind, j.slots, j.urgency)


# --- posting ------------------------------------------------------------------------------------


def test_a_damaged_sanctuary_posts_its_repair_job_without_a_contact() -> None:
    w = new_world()
    board_pass(w)
    assert repair(w) is None  # full hp: nothing to repair
    w.defense_hp[HAVEN] = FULL // 2
    board_pass(w)
    assert posted(w) == ("RESUPPLY", 3, 1500)  # 1.0 + the missing share 0.5
    w.defense_hp[HAVEN] = FULL - 1
    board_pass(w)
    assert posted(w) == ("RESUPPLY", 3, 1001)  # the same job follows the damage


def test_urgency_is_the_cap_while_besieged_or_at_zero_hp() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 1
    threat(w)  # a tracked striker in range: besieged
    board_pass(w)
    assert posted(w) == ("RESUPPLY", 3, TR.urgency_max_milli)
    high = dataclasses.replace(TR, urgency_max_milli=3000)  # above 1.0 + a whole share
    w2 = new_world(rules=dataclasses.replace(RULES, tasking=high))
    w2.defense_hp[HAVEN] = 0  # the defeat run is counting, no contact
    board_pass(w2)
    assert posted(w2) == ("RESUPPLY", 3, 3000)
    w3 = new_world()
    w3.defense_hp[HAVEN] = FULL - 1
    threat(w3, dist=TR.defend_radius_m + 1)  # out of range: not besieged
    board_pass(w3)
    assert posted(w3) == ("RESUPPLY", 3, 1001)


def test_slots_follow_the_lc3_cap_with_the_missing_share_as_need() -> None:
    def slots(hp: int) -> int | None:
        w = new_world(rules=SHIPPED_CAP)
        w.defense_hp[HAVEN] = hp
        board_pass(w)
        j = repair(w)
        return None if j is None else j.slots

    # 3 + floor(share x (6 - 3))
    assert [slots(FULL - 1), slots(FULL * 2 // 3), slots(FULL // 3), slots(0)] == [3, 4, 5, 6]


def test_an_unclaimed_job_is_withdrawn_at_full_hp_and_never_expires_before() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 1
    board_pass(w)
    job = repair(w)
    assert job is not None
    for _ in range(TR.expire_ticks // TR.reeval_every_ticks + 2):  # past `tasking.expire_min`
        assert "JobExpired" not in kinds(board_pass(w))
    assert repair(w) is job
    w.defense_hp[HAVEN] = FULL
    assert kinds(board_pass(w)) == ["JobExpired"] and repair(w) is None


def _static_specs(w: World) -> list[tuple[str, int, int]]:
    specs = generate(w, RULES, TR, "ENEMY", side_view(w, "ENEMY"))
    return [(s.key, s.slots, s.urgency) for s in specs if s.kind == "RESUPPLY"]


def test_the_rule_is_the_same_for_the_static_rear_ec3() -> None:
    """EC-3: the Static's rear is never struck in play (Q-SIM-64); the generator treats it alike."""
    w = new_world()
    put(w, "ENEMY_CONVOY", "static-hq", AI)  # the Static can staff RESUPPLY
    w.defense_hp[HAVEN] = 0
    assert all(k != KEY for k, _, _ in _static_specs(w))  # never the coalition's haven
    assert all(not k.endswith(STATIC_REAR) for k, _, _ in _static_specs(w))  # full
    w.defense_hp[STATIC_REAR] = STATIC_FULL // 2
    assert (f"resupply:{STATIC_REAR}", 3, 1500) in _static_specs(w)


def test_a_captured_sanctuary_gets_no_repair_job() -> None:
    # `capture.uncapturable_node_kinds` may drop SANCTUARY (an OPERATOR option): a haven the
    # other side took is not the coalition's to repair
    w = new_world(rules=dataclasses.replace(RULES, uncapturable=frozenset({"BRIDGE"})))
    w.owner[HAVEN] = "ENEMY"
    w.defense_hp[HAVEN] = FULL // 2
    board_pass(w)
    assert repair(w) is None


def test_a_claimed_job_fails_once_the_sanctuary_is_captured() -> None:
    w = new_world(rules=dataclasses.replace(RULES, uncapturable=frozenset({"BRIDGE"})))
    w.defense_hp[HAVEN] = FULL // 2
    truck = put(w, "LOGI_TRUCK", HAVEN, cargo=0)
    board_pass(w)
    job = repair(w)
    assert job is not None and truck.job_id == job.id
    w.owner[HAVEN] = "ENEMY"
    out = board_pass(w)
    (failed,) = of(out, JobFailed)
    assert failed.job_id == job.id and repair(w) is None and truck.job_id is None


# --- claimants ----------------------------------------------------------------------------------


def test_a_static_ai_convoy_never_claims_the_static_rears_repair_job() -> None:
    # `_may_take` checks the job against the truck's own side's sanctuary (EC-3 parity)
    w = new_world()
    convoy = put(w, "ENEMY_CONVOY", STATIC_REAR, AI, cargo=0)
    w.defense_hp[STATIC_REAR] = STATIC_FULL // 2
    board_pass(w)
    (job,) = [j for j in jobs(w, "ENEMY") if j.key == f"resupply:{STATIC_REAR}"]
    assert job.claims == {} and convoy.job_id is None


def test_ai_trucks_never_claim_it_but_one_parked_still_repairs() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = 0
    parked = put(w, "LOGI_TRUCK", HAVEN, AI, cargo=0)
    away = put(w, "LOGI_TRUCK", "west-airbase", AI, cargo=0)
    board_pass(w)
    job = repair(w)
    assert job is not None and job.claims == {}
    assert parked.job_id is None and away.job_id is None
    viewer = put(w, "LOGI_TRUCK", "west-airbase", cargo=0)
    board_pass(w)
    assert list(job.claims) == [viewer.id]  # the viewer truck takes it; no AI truck to displace
    hp = w.defense_hp[HAVEN]
    for _ in range(10):
        step(w, [])
    assert w.defense_hp[HAVEN] > hp  # §9: the AI truck parked there repairs, job or not


def test_lc1_spawns_no_ai_truck_for_it_and_counts_no_idle_one_against_it() -> None:
    w = new_world(rules=cadence(5))  # room for 4 more AI trucks
    w.defense_hp[HAVEN] = 0  # posted first (lower id, older), urgency 2.0: ranked first
    board_pass(w)
    w.stock["west-airbase"] = 0  # a starving base: urgency 2.0, 3 slots
    board_pass(w)
    idle = put(w, "LOGI_TRUCK", "west-airbase", AI)
    at(w, 2 * PERIOD)
    job = repair(w)
    assert job is not None and job.claims == {}
    # the idle truck goes to west's first slot, two new ones to the rest; none for the haven
    assert len(ai_trucks_of(w)) == 3
    board_pass(w)
    west = next(j for j in jobs(w) if j.key == "resupply:west-airbase")
    assert idle.job_id == west.id and job.claims == {}


# --- executor -----------------------------------------------------------------------------------


def test_an_empty_viewer_truck_takes_it_with_no_reload_and_heads_for_the_haven() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    stock = dict(w.stock)
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=0)
    board_pass(w)
    job = repair(w)
    assert job is not None and list(job.claims) == [truck.id]
    assert truck.path[-1] == HAVEN and truck.pickup is None and truck.cargo == 0  # no reload
    assert w.stock == stock


def test_a_loaded_truck_is_refused() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    truck = put(w, "LOGI_TRUCK", HAVEN, cargo=100)  # the haven takes no cargo (`accepts`)
    board_pass(w)
    job = repair(w)
    assert job is not None and job.claims == {} and truck.job_id is None


def test_a_claimed_job_is_not_done_before_full_hp_and_never_expires() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    truck = put(w, "LOGI_TRUCK", HAVEN, cargo=0)
    board_pass(w)
    job = repair(w)
    assert job is not None and truck.job_id == job.id
    truck.path = []  # parked: board passes only, so nothing repairs it
    for _ in range(TR.expire_ticks // TR.reeval_every_ticks + 2):  # past `tasking.expire_min`
        seen = kinds(board_pass(w))
        assert "JobDone" not in seen and "JobExpired" not in seen and "JobReleased" not in seen
    assert repair(w) is job and list(job.claims) == [truck.id]
    w.defense_hp[HAVEN] = FULL
    out = board_pass(w)
    (done,) = of(out, JobDone)
    assert done.job_id == job.id and [p.entity_id for p in done.participants] == [truck.id]


def test_full_hp_without_a_parked_claimant_is_not_done() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=0)
    board_pass(w)
    job = repair(w)
    assert job is not None and truck.job_id == job.id and truck.path
    w.defense_hp[HAVEN] = FULL  # repaired by others while it still drives
    assert "JobDone" not in kinds(board_pass(w)) and repair(w) is job


def test_a_bare_join_logi_spawns_at_the_haven_and_takes_it() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    board_pass(w)
    job = repair(w)
    assert job is not None
    step(w, [join(1, "LOGI")])
    (truck,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert truck.job_id == job.id and truck.last_node == HAVEN and truck.cargo == 0


# --- end to end, determinism, snapshots ---------------------------------------------------------


def _scene() -> tuple[World, Entity]:
    """A viewer truck at west-airbase, 70 km from the haven (about 4,700 ticks by road), and 100
    hp to rebuild (167 ticks at the shipped 600 thousandths per tick)."""
    w = new_world()
    w.defense_hp[HAVEN] = FULL - 100
    return w, put(w, "LOGI_TRUCK", "west-airbase", cargo=0)


def test_a_viewer_truck_drives_parks_repairs_and_is_done_at_full_hp_not_before() -> None:
    w, truck = _scene()
    parked_at, job_id = None, None
    for _ in range(8000):
        out = step(w, [])
        if of(out, JobDone):
            break
        job = repair(w)
        assert job is not None or w.campaign.running_ticks < TR.reeval_every_ticks
        job_id = job_id or (job.id if job else None)
        if parked_at is None and truck.last_node == HAVEN and not truck.path:
            parked_at = w.campaign.tick
            assert w.defense_hp[HAVEN] == FULL - 100  # nothing repaired it on the way
    (done,) = of(out, JobDone)
    assert done.job_id == job_id and truck.job_id is None
    assert [p.entity_id for p in done.participants] == [truck.id]
    assert w.defense_hp[HAVEN] == FULL and repair(w) is None
    assert parked_at is not None and done.tick > parked_at + 100  # DONE at full hp, not on arrival
    assert truck.last_node == HAVEN and not truck.path and truck.cargo == 0


def _run(snapshot_at: int | None = None) -> tuple[str, list[str]]:
    w, _ = _scene()
    events: list[Event] = []
    for tick in range(8000):
        if tick == snapshot_at:
            copy = load(save(w))
            copy.rules = w.rules
            assert state_hash(copy) == state_hash(w)
            w = copy
        out = step(w, [])
        events += out
        if of(out, JobDone):
            break
    return state_hash(w), [e.model_dump_json() for e in events]


def test_the_repair_run_is_deterministic_and_survives_save_and_load() -> None:
    first = _run()
    assert any('"JobDone"' in e for e in first[1])
    assert first == _run()
    assert _run(snapshot_at=2000) == first  # mid-drive, the job claimed
    assert _run(snapshot_at=4800) == first  # parked, mid-repair


def test_idle_reason_names_the_road_not_a_reload_for_it() -> None:
    w = new_world()
    w.defense_hp[HAVEN] = FULL // 2
    board_pass(w)
    truck = put(w, "LOGI_TRUCK", "west-airbase", cargo=0)
    assert idle_reason(w, truck) == "next_pass"
    truck.pos = Vec2(truck.pos.x + 500, truck.pos.y)  # off its node: no road route from here
    assert idle_reason(w, truck) == "no_route"  # not `no_reload`: the job carries nothing
