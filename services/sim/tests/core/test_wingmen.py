"""NX-511: human-led AI wingmen (GAMEPLAY §1b items 239-255; Q-GP-50, Q-GP-51, Q-GP-32, Q-GP-44).

Runs on strait-1 with the pre-5b fixture (unlimited economy, wingmen off) and the shipped wingmen
keys turned back on: `wingmen_max` 2, `wingmen_max_live` 6, cooldown and active window 15 game min
(9,000 ticks), `capture.quiet_ref` 50. Expected counts are the spec's worked examples (item 241).
"""

import dataclasses
from collections.abc import Callable
from typing import Any

import msgpack
import pytest
from fixture_pre_5b import pre_5b_config
from hypothesis import given
from hypothesis import strategies as st
from test_join import CAMPAIGN_ID, cid, join

from nexus.contracts.gen.commands.rebase import RebaseCommand
from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import combat, wingmen
from nexus.core.economy import guard_room
from nexus.core.follow import steer
from nexus.core.provocation import suffered_defense_hit
from nexus.core.rules import Rules, TaskingRules
from nexus.core.step import step
from nexus.core.tasking import _end, claim, post_job
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import (
    Entity,
    Job,
    Vec2,
    World,
    load,
    lose_unit,
    release_claim,
    save,
    state_hash,
)
from nexus.runtime.campaign_config import CampaignConfig, start_campaign

ON = {"tasking.wingmen_max": 2}
CONFIG = pre_5b_config(ON)
LIMITED = pre_5b_config({**ON, "economy.unlimited.COALITION": False})
JET: UnitKind = "STRIKE_FIGHTER"
TARGET = "east-airbase"


def _rules(config: CampaignConfig) -> Rules:
    return dataclasses.replace(config.rules, campaign=None, garrison_quota={})


def tr_of(w: World) -> TaskingRules:
    assert w.rules is not None and w.rules.tasking is not None
    return w.rules.tasking


def new_world(config: CampaignConfig = CONFIG, seed: int = 1) -> World:
    return start_campaign(CAMPAIGN_ID, seed, dataclasses.replace(config, rules=_rules(config)))


def viewer(w: World, n: int, kind: UnitKind = JET, node: str = "haven") -> Entity:
    """A commander's landed unit at `node`, its commander active now."""
    assert w.rules is not None
    e = w.spawn(kind, "COALITION", "COMMANDER", Vec2(*w.rules.roads.pos[node]), commander_id=cid(n))
    e.last_node, e.home_base, e.state, e.fuel = node, node, "LANDED", w.rules.fuel_s[kind]
    w.last_command[cid(n)] = w.campaign.running_ticks
    return e


def crowd(w: World, v: int) -> Entity:
    """`v` live viewer units: the lead (commander 1) and v - 1 recon drones."""
    lead = viewer(w, 1)
    for n in range(2, v + 1):
        viewer(w, n, "RECON_UAV")
    assert w.viewer_units() == v
    return lead


def strike(w: World, node: str = TARGET, kind: str = "STRIKE") -> Job:
    key = f"{kind.lower()}:{node}"
    return post_job(w, "COALITION", JobSpec(kind, key, 2, 1000, node=node), [])  # type: ignore[arg-type]


def take(w: World, e: Entity, job: Job) -> list[Event]:
    out: list[Event] = []
    claim(w, e, job, out)
    return out


def flight_units(w: World, lead: Entity) -> list[Entity]:
    return [w.get(i) for i in w.flights[lead.id].wingmen]


def size(w: World, lead: Entity) -> int:
    """The lead's flight size, 0 for none."""
    return len(w.flights[lead.id].wingmen) if lead.id in w.flights else 0


def dumps(out: list[Event], kind: str) -> list[dict[str, Any]]:
    return [e.model_dump() for e in out if e.kind == kind]


def tick(w: World) -> list[Event]:
    out: list[Event] = []
    wingmen.run(w, out)
    return out


# --- trigger (item 240) ---------------------------------------------------------------------------


def test_a_landed_strike_claim_brings_two_ai_wingmen_at_the_leads_base() -> None:
    w = new_world()
    lead = viewer(w, 1)
    job = strike(w)
    out = take(w, lead, job)
    flight = w.flights[lead.id]
    assert flight.job == job.id and flight.commander == cid(1) and not flight.impact
    assert len(flight.wingmen) == 2
    for m in flight_units(w, lead):
        assert (m.kind, m.side, m.owner_kind, m.commander_id) == (
            JET,
            "COALITION",
            "AI_GARRISON",
            None,
        )
        assert (m.state, m.last_node, m.home_base, m.pos) == ("LANDED", "haven", "haven", lead.pos)
        assert (m.order, m.follow_id, m.job_id) == ("FOLLOW", lead.id, None)
        assert m.id not in job.claims and m.ammo == lead.ammo
    spawned = dumps(out, "UnitSpawned")
    assert [e["entity_id"] for e in spawned] == flight.wingmen
    assert all(e["owner_kind"] == "AI_GARRISON" and e["commander_id"] is None for e in spawned)
    assert w.viewer_units() == 1  # wingmen never count in v


def _airborne(w: World, lead: Entity) -> None:
    lead.state = "EN_ROUTE"


def _inactive(w: World, lead: Entity) -> None:
    del w.last_command[cid(1)]


def _unarmed(w: World, lead: Entity) -> None:
    lead.ammo = [0] * len(lead.ammo)


def _ai(w: World, lead: Entity) -> None:
    lead.owner_kind, lead.commander_id = "AI_GARRISON", None


def _off(w: World, lead: Entity) -> None:
    assert w.rules is not None
    w.rules = dataclasses.replace(w.rules, tasking=dataclasses.replace(tr_of(w), wingmen_max=0))


@pytest.mark.parametrize("change", [_airborne, _inactive, _unarmed, _ai, _off])
def test_no_flight_without_a_landed_armed_active_viewer_lead(change: Any) -> None:
    w = new_world()
    lead = viewer(w, 1)
    job = strike(w)
    change(w, lead)
    before = len(w)
    out = take(w, lead, job)
    assert not w.flights and len(w) == before and [e.kind for e in out] == ["JobClaimed"]


def test_no_flight_for_another_job_kind_or_a_static_claim() -> None:
    w = new_world()
    lead = viewer(w, 1)
    assert [e.kind for e in take(w, lead, strike(w, "west-airbase", "DEFEND"))] == ["JobClaimed"]
    enemy = w.spawn("ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR", Vec2(310_000, 120_000))
    enemy.last_node, enemy.state, enemy.fuel = TARGET, "LANDED", 100.0
    job = post_job(
        w, "ENEMY", JobSpec("STRIKE", "strike:west-airbase", 2, 1000, node="west-airbase"), []
    )
    assert [e.kind for e in take(w, enemy, job)] == ["JobClaimed"]
    assert not w.flights


@pytest.mark.parametrize(("ago", "flies"), [(0, True), (8_999, True), (9_000, False)])
def test_the_active_lead_window_edges(ago: int, flies: bool) -> None:
    w = new_world()
    lead = viewer(w, 1)
    w.campaign.running_ticks = 20_000
    w.last_command[cid(1)] = 20_000 - ago
    take(w, lead, strike(w))
    assert (lead.id in w.flights) is flies


def test_a_chat_command_stamps_its_commander_accepted_or_rejected_and_the_board_prunes_it() -> None:
    w = new_world()
    w.campaign.running_ticks = 0
    step(w, [join(1, "STRIKE", hold=True)])
    assert w.last_command == {cid(1): 0}
    bad = RebaseCommand.model_validate({
        "kind": "REBASE", "source": "CHAT", "issuer": {"commander_id": cid(2)}, "target_tick": 2,
        "arrival_seq": 2, "correlation_id": "r2", "node_id": "west-airbase",
    })  # fmt: skip
    events = step(w, [bad])  # commander 2 has no unit: rejected, still stamped
    assert any(e.kind == "CommandRejected" for e in events)
    assert w.last_command == {cid(1): 0, cid(2): 1}
    w.campaign.running_ticks = tr_of(w).wingmen_lead_active_ticks + 1 - 1  # 9,000 after 1
    wingmen.prune(w)
    assert w.last_command == {cid(2): 1}


# --- count and caps (item 241) --------------------------------------------------------------------


@pytest.mark.parametrize(("v", "n"), [(1, 2), (8, 2), (24, 2), (25, 1), (49, 1), (50, 0)])
def test_the_flight_fades_with_viewer_units(v: int, n: int) -> None:
    w = new_world()
    lead = crowd(w, v)
    take(w, lead, strike(w))
    assert size(w, lead) == n


@pytest.mark.parametrize(("v", "cap"), [(1, 6), (8, 6), (24, 4), (25, 3), (49, 1), (50, 0)])
def test_the_theater_cap_fades_like_the_flight(v: int, cap: int) -> None:
    assert wingmen.fade(6, v, 50) == cap
    w = new_world(pre_5b_config({"tasking.wingmen_max": 4}))
    lead = crowd(w, v)
    for _ in range(max(0, cap - 1)):  # live wingmen one short of the cap
        w.wingmen_home.append(w.spawn(JET, "COALITION", "AI_GARRISON", Vec2(20_000, 120_000)).id)
    take(w, lead, strike(w))
    assert size(w, lead) == min(1, cap, wingmen.fade(4, v, 50))


@given(cap=st.integers(0, 50), v=st.integers(0, 200), q=st.integers(1, 100))
def test_fade_is_between_zero_and_cap_and_never_rises_with_viewers(
    cap: int, v: int, q: int
) -> None:
    got = wingmen.fade(cap, v, q)
    assert 0 <= got <= cap and wingmen.fade(cap, v + 1, q) <= got
    assert wingmen.fade(cap, 0, q) == cap and wingmen.fade(cap, q, q) == 0


def test_the_ec8_guard_cuts_the_flight() -> None:
    w = new_world()
    lead = viewer(w, 1)
    assert w.rules is not None and w.rules.economy is not None
    live = w.rules.economy.max_live_per_side - guard_room(w, "COALITION")
    economy = dataclasses.replace(w.rules.economy, max_live_per_side=live + 1)
    w.rules = dataclasses.replace(w.rules, economy=economy)
    take(w, lead, strike(w))
    assert len(w.flights[lead.id].wingmen) == 1


# --- cost (item 242) ------------------------------------------------------------------------------


@pytest.mark.parametrize(("pool", "n", "left"), [(100, 2, 60), (39, 1, 19), (19, 0, 19)])
def test_at_the_sanctuary_each_wingman_pays_a_loadout_from_the_pool(
    pool: int, n: int, left: int
) -> None:
    w = new_world(LIMITED)
    w.pool["COALITION"] = pool
    lead = viewer(w, 1)
    out = take(w, lead, strike(w))
    assert size(w, lead) == n and w.pool["COALITION"] == left
    paid = [(e["node_id"], e["amount"], e["cause"]) for e in dumps(out, "SupplyConsumed")]
    assert paid == [("haven", 20, "SPAWN")] * n


@pytest.mark.parametrize(("above", "n"), [(45, 2), (25, 1), (19, 0)])
def test_at_a_forward_airbase_its_stock_pays_never_below_the_starvation_floor(
    above: int, n: int
) -> None:
    w = new_world(LIMITED)
    assert w.rules is not None
    floor = w.rules.supply.starve_floor["west-airbase"]
    w.stock["west-airbase"] = floor + above
    lead = viewer(w, 1, node="west-airbase")
    take(w, lead, strike(w))
    assert size(w, lead) == n and w.stock["west-airbase"] == floor + above - 20 * n
    assert not n or all(m.last_node == "west-airbase" for m in flight_units(w, lead))


# --- station and fighting (items 243, 244, 247) ---------------------------------------------------


def test_the_first_wingman_flies_off_the_right_and_the_second_off_the_left() -> None:
    w = new_world()
    lead = viewer(w, 1)
    take(w, lead, strike(w))
    lead.state, lead.pos, lead.vel = "EN_ROUTE", Vec2(100_000, 120_000), Vec2(250.0, 0.0)
    lead.path = [Vec2(300_000, 120_000)]
    for m in flight_units(w, lead):
        m.state, m.pos = "EN_ROUTE", Vec2(99_000, 120_000)
    steer(w)
    first, second = flight_units(w, lead)
    # flying east (+x), the right is south (-y) on a north-up map (Q-UX-18)
    assert first.path == [Vec2(100_000, 119_000)] and second.path == [Vec2(100_000, 121_000)]


def test_a_wingman_aims_with_its_leads_strike_job_and_never_joins_struck_by() -> None:
    config = pre_5b_config({**ON, "combat.strike_structure_first": True})
    w = new_world(config)
    lead = viewer(w, 1)
    job = strike(w)
    take(w, lead, job)
    first = flight_units(w, lead)[0]
    assert combat._aim(w, first).job_id == job.id and first.job_id is None
    assert combat._aim(w, lead) is lead
    stray = w.spawn(JET, "COALITION", "AI_GARRISON", Vec2(310_000, 120_000))
    assert combat._aim(w, stray) is stray  # not in a flight: no job to borrow
    assert w.rules is not None
    first.state, first.pos, first.last_node = "ON_STATION", Vec2(*w.rules.roads.pos[TARGET]), None
    first.orbit = first.pos
    out: list[Event] = []
    combat.resolve(w, out)
    fired = [e for e in dumps(out, "WeaponFired") if e["shooter_id"] == first.id]
    assert fired and fired[0]["target_node_id"] == TARGET
    assert first.id not in job.struck_by and first.id not in job.claims


def test_a_wingmans_hit_adds_no_provocation() -> None:
    w = new_world()
    lead = viewer(w, 1)
    take(w, lead, strike(w))
    before = dataclasses.asdict(w.director["ENEMY"])
    suffered_defense_hit(w, flight_units(w, lead)[0], TARGET)
    assert dataclasses.asdict(w.director["ENEMY"]) == before
    suffered_defense_hit(w, lead, TARGET)  # the lead's own hit does provoke
    assert dataclasses.asdict(w.director["ENEMY"]) != before


def test_only_the_lead_is_credited_for_a_done_job() -> None:
    w = new_world()
    lead = viewer(w, 1)
    job = strike(w)
    take(w, lead, job)
    job.struck_by = [lead.id]
    out: list[Event] = []
    _end(w, "COALITION", job, "DONE", out)
    (done,) = dumps(out, "JobDone")
    assert [(p["entity_id"], p["commander_id"]) for p in done["participants"]] == [
        (lead.id, cid(1))
    ]
    assert w.flights[lead.id].impact  # a DONE job is impact (item 248)


# --- flight end, retirement and cooldown (items 245, 248) -----------------------------------------


def _flying(w: World) -> tuple[Entity, Job]:
    lead = viewer(w, 1)
    job = strike(w)
    take(w, lead, job)
    for e in (lead, *flight_units(w, lead)):
        e.state, e.pos, e.path = "EN_ROUTE", Vec2(150_000, 120_000), [Vec2(300_000, 120_000)]
    assert not tick(w) and w.flights[lead.id].flown
    return lead, job


def test_a_dead_leads_wingmen_fly_home_land_and_retire_with_no_cooldown() -> None:
    w = new_world()
    lead, _ = _flying(w)
    members = flight_units(w, lead)
    lose_unit(w, lead, [])
    assert not tick(w)
    assert not w.flights and w.wingmen_home == [m.id for m in members]
    for m in members:
        assert (m.state, m.path, m.order, m.follow_id) == ("RTB", ["west-airbase"], None, None)
    assert w.rules is not None
    members[0].state, members[0].path = "LANDED", []
    members[0].pos, members[0].last_node = Vec2(*w.rules.roads.pos["west-airbase"]), "west-airbase"
    out = tick(w)
    assert len(out) == 1
    assert [(e["entity_id"], e["reason"]) for e in dumps(out, "UnitDespawned")] == [
        (members[0].id, "RETIRED")
    ]
    assert w.find(members[0].id) is None and w.wingmen_home == [members[1].id]
    assert not w.wingmen_cooldown  # nothing lost


def test_losing_a_wingman_with_no_impact_starts_the_cooldown() -> None:
    w = new_world()
    lead, job = _flying(w)
    lose_unit(w, flight_units(w, lead)[0], [])
    release_claim(w, job, lead.id, [])
    w.campaign.running_ticks = 500
    tick(w)
    until = 501 + tr_of(w).wingmen_cooldown_ticks
    assert w.wingmen_cooldown == {cid(1): until}
    lead.state, lead.path, lead.job_id = "LANDED", [], None  # back on the ground for a new claim
    lead.pos, lead.last_node = Vec2(20_000, 120_000), "haven"
    w.campaign.running_ticks = until - 2
    w.last_command[cid(1)] = w.campaign.running_ticks
    take(w, lead, strike(w, "fob-n-e"))
    assert lead.id not in w.flights  # still cooling down
    release_claim(w, w.boards["COALITION"][lead.job_id or 0], lead.id, [])
    w.campaign.running_ticks = until - 1
    take(w, lead, strike(w, "fob-s-e"))
    assert lead.id in w.flights  # the tick the cooldown ends


def test_an_impactful_flight_that_loses_a_wingman_starts_no_cooldown() -> None:
    w = new_world()
    lead, job = _flying(w)
    wingmen.note_hit(w, flight_units(w, lead)[1].id)
    lose_unit(w, flight_units(w, lead)[0], [])
    release_claim(w, job, lead.id, [])
    tick(w)
    assert not w.flights and not w.wingmen_cooldown


def test_cancel_before_takeoff_counts_as_a_loss_and_the_wingmen_retire_at_once() -> None:
    w = new_world()
    lead = viewer(w, 1)
    job = strike(w)
    take(w, lead, job)
    members = flight_units(w, lead)
    release_claim(w, job, lead.id, [])
    out = tick(w)
    assert [e["entity_id"] for e in dumps(out, "UnitDespawned")] == [m.id for m in members]
    assert all(w.find(m.id) is None for m in members) and not w.wingmen_home
    assert cid(1) in w.wingmen_cooldown


def test_a_wingman_sent_home_for_its_own_reason_leaves_the_flight_for_good() -> None:
    w = new_world()
    lead, _ = _flying(w)
    first, second = flight_units(w, lead)
    first.state, first.path = "RTB", ["haven"]  # bingo
    tick(w)
    assert w.flights[lead.id].wingmen == [second.id] and w.wingmen_home == [first.id]
    assert (first.order, first.follow_id) == (None, None)


def test_one_flight_per_claim() -> None:
    w = new_world()
    lead = viewer(w, 1)
    job = strike(w)
    take(w, lead, job)
    old = list(w.flights[lead.id].wingmen)
    w.flights[lead.id].flown = True  # else the cancel before takeoff cools the commander down
    release_claim(w, job, lead.id, [])
    take(w, lead, strike(w, "fob-n-e"))  # a new claim in the same pass ends the old flight
    assert set(w.wingmen_home) == set(old) and w.flights[lead.id].wingmen != old


# --- snapshot, determinism, 0 viewers (items 249, 251) --------------------------------------------


def _busy(w: World) -> None:
    lead, _ = _flying(w)
    w.wingmen_home.append(w.spawn(JET, "COALITION", "AI_GARRISON", Vec2(50_000, 120_000)).id)
    w.wingmen_cooldown[cid(9)] = 99_999
    wingmen.note_hit(w, lead.id)
    w.campaign.running_ticks += 1  # the claims were made in the tick being computed
    w.campaign.tick += 1


def test_snapshot_round_trip_and_hash_cover_every_new_field() -> None:
    w = new_world()
    _busy(w)
    back = load(save(w))
    assert state_hash(back) == state_hash(w)
    for name in ("flights", "last_command", "wingmen_cooldown", "wingmen_home"):
        assert getattr(back, name) == getattr(w, name)
    base = state_hash(w)
    changes: list[Callable[[World], object]] = [
        lambda x: setattr(x.flights[min(x.flights)], "impact", False),
        lambda x: setattr(x.flights[min(x.flights)], "flown", False),
        lambda x: x.wingmen_cooldown.__setitem__(cid(9), 1),
        lambda x: x.last_command.__setitem__(cid(1), 1),
        lambda x: x.wingmen_home.clear(),
    ]
    for change in changes:
        changed = load(save(back))
        change(changed)
        assert state_hash(changed) != base


def _raw(w: World) -> dict[str, Any]:
    raw: dict[str, Any] = msgpack.unpackb(save(w), raw=False)
    return raw


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda r: r["last_command"].__setitem__("x", r["campaign"]["running_ticks"] + 1),
        lambda r: r["wingmen_home"].append(next(iter(r["flights"].values()))["wingmen"][0]),
        lambda r: r["wingmen_home"].insert(0, r["next_entity_id"]),
        lambda r: next(iter(r["flights"].values())).__setitem__("impact", 1),
    ],
)
def test_the_loader_refuses_bad_wingmen_state(corrupt: Any) -> None:
    w = new_world()
    _busy(w)
    raw = _raw(w)
    corrupt(raw)
    with pytest.raises(ValueError):
        load(msgpack.packb(raw, use_bin_type=True))


def _run(
    seed: int, snapshot_at: int | None = None, config: CampaignConfig = CONFIG
) -> tuple[str, list[dict[str, Any]], int]:
    w = new_world(config, seed)
    strike(w)
    rules = w.rules
    events: list[dict[str, Any]] = []
    for t in range(1, 1201):
        commands = [join(1, "STRIKE", target_tick=t)] if t == 1 else []
        events += [e.model_dump() for e in step(w, commands)]
        if t == snapshot_at:
            w = load(save(w))
            w.rules = rules
    spawned = sum(
        e["kind"] == "UnitSpawned" and e["owner_kind"] == "AI_GARRISON" and e["unit_kind"] == JET
        for e in events
    )
    return state_hash(w), events, spawned


def test_a_join_claim_flies_with_wingmen_the_same_way_every_run_and_across_a_save() -> None:
    first = _run(3)
    assert first[2] == 2  # the parameterless JOIN claimed the STRIKE job while landed
    assert _run(3) == first
    assert _run(3, snapshot_at=600) == first


def test_zero_viewers_is_byte_identical_to_wingmen_off() -> None:
    def run(config: CampaignConfig) -> tuple[str, list[dict[str, Any]]]:
        w = new_world(config, 5)
        w.campaign.config_hash = "same"
        events = [e.model_dump() for t in range(3000) for e in step(w, [])]
        assert not (w.flights or w.wingmen_home or w.wingmen_cooldown or w.last_command)
        return state_hash(w), events

    assert run(CONFIG) == run(pre_5b_config({"tasking.wingmen_max": 0}))
