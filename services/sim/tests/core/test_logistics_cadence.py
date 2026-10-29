"""NX-473: the logistics cadence (GAMEPLAY §5 LC-1..LC-5, THREAT-DIRECTOR §5a demand convoys;
Q-TD-92, Q-TD-109..117).

LC-1 coalition AI trucks (`nexus.core.ai_trucks`), LC-2 demand convoys and LC-3 the per-job truck
cap (`nexus.core.launch`, `nexus.core.tasking_gen`), each switched on here by hand; the shipped
config keeps them at the no-op values (Q-TD-113), which the goldens pin. Board scenes reuse
`test_tasking` (strait-1, campaign layer off, stocking off, board passes by hand), convoy scenes
`test_pol`. strait-1: west-airbase (max 2000, floor 500, start 1000), fob-n-w and fob-s-w (max
1000, floor 250, start 500) and the haven (the rear, infinite under the unlimited mode that
`test_tasking.CONFIG` keeps from `fixture_pre_5b`).
"""

import dataclasses

from test_join import join
from test_launch import DR, skip
from test_pol import GARRISON_ONLY, window
from test_pol import new_world as pol_world
from test_retake import RET_RULES, lose
from test_tasking import AI, CONFIG, HUMAN, RULES, TR, board_pass, jobs, new_world, post, put

from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_despawned import UnitDespawned
from nexus.core.ai_trucks import ai_trucks
from nexus.core.capture import capture
from nexus.core.economy import MOVERS, guard_room
from nexus.core.handlers import join as handle_join
from nexus.core.launch import _night_capped
from nexus.core.logistics import plan_run
from nexus.core.rules import DirectorRules, EconomyRules, Rules
from nexus.core.step import step
from nexus.core.tasking import claim, joinable_jobs
from nexus.core.world import Entity, Job, Vec2, World, load, save, state_hash
from nexus.runtime.golden import shipped_config

_eco = CONFIG.rules.economy
assert _eco is not None
ECO: EconomyRules = _eco
WINDOW = ECO.window_ticks  # 600: one economy window (60 game s)
PERIOD = 2 * WINDOW


def cadence(max_live: int = 3, period: int = PERIOD, rules: Rules = RULES) -> Rules:
    sup = dataclasses.replace(
        rules.supply, ai_truck_period_ticks=period, ai_truck_max_live=max_live
    )
    return dataclasses.replace(rules, supply=sup)


ON = cadence()


def at(w: World, now: int) -> list[Event]:
    """LC-1 alone at running tick `now` (an economy window when `now` is a multiple of 600)."""
    w.campaign.running_ticks = now - 1
    out: list[Event] = []
    ai_trucks(w, out)
    w.campaign.running_ticks = now
    return out


def ai_trucks_of(w: World) -> list[Entity]:
    return [
        e for e in w.entities()
        if e.side == "COALITION" and e.owner_kind == "AI_GARRISON" and e.kind == "LOGI_TRUCK"
    ]  # fmt: skip


def starving_west(rules: Rules = ON) -> tuple[World, Job]:
    """west-airbase empty: its resupply job (3 slots) is posted at running tick 50."""
    w = new_world(rules=rules)
    w.stock["west-airbase"] = 0
    board_pass(w)
    (job,) = [j for j in jobs(w) if j.key == "resupply:west-airbase"]
    assert (job.slots, job.created) == (3, 50)
    return w, job


def total(w: World) -> int:
    return sum(w.stock.values()) + sum(e.cargo or 0 for e in w.entities())


# --- LC-1: the cadence ----------------------------------------------------------------------------


def test_no_truck_for_a_job_younger_than_one_period_then_one_per_free_slot() -> None:
    w, job = starving_west()
    assert at(w, PERIOD) == []  # posted 1,150 ticks ago: viewers still have the first pick
    first = plan_run(w, ON, "COALITION", "west-airbase")
    assert first is not None and first.source == "fob-n-w"  # the §1b source, not the haven
    before = total(w)
    out = at(w, 2 * PERIOD)
    trucks = ai_trucks_of(w)
    assert [e.kind for e in out if e.kind == "UnitSpawned"] == ["UnitSpawned"] * 3
    assert {(e.owner_kind, e.commander_id, e.callsign) for e in out if e.kind == "UnitSpawned"} == {
        ("AI_GARRISON", None, None)
    }
    assert len(trucks) == 3 and sorted(job.claims) == [e.id for e in trucks]
    assert trucks[0].last_node == first.source and trucks[0].cargo == first.cargo
    assert trucks[0].home_base == first.source  # its spawn node pays its upkeep (EC-5)
    assert all(e.cargo and e.path and e.path[-1] == "west-airbase" for e in trucks)
    assert total(w) == before  # the cargo left the sources' stock
    assert w.viewer_units() == 0


def test_only_at_the_period_windows() -> None:
    w, _ = starving_west()
    assert at(w, 2 * PERIOD + WINDOW) == []  # an economy window, not a period one
    assert at(w, 2 * PERIOD + 1) == []  # no window at all
    assert len([e for e in at(w, 3 * PERIOD) if e.kind == "UnitSpawned"]) == 3


def test_max_live_caps_the_live_ai_trucks_and_zero_spawns_none() -> None:
    for live, made in ((0, 0), (2, 2), (5, 3)):
        w, _ = starving_west(cadence(live))
        at(w, 2 * PERIOD)
        assert len(ai_trucks_of(w)) == made
    w, _ = starving_west(cadence(4))
    at(w, 2 * PERIOD)
    at(w, 3 * PERIOD)  # the job is full: nothing more however many periods pass
    assert len(ai_trucks_of(w)) == 3


def test_busy_ai_trucks_count_against_max_live() -> None:
    w, _ = starving_west(cadence(2))
    other = post(w, "COALITION", "RESUPPLY", "fob-s-w", "busy", slots=2)
    for _ in range(2):  # two AI trucks already working another job: not idle, not spare
        claim(w, put(w, "LOGI_TRUCK", "haven", AI), other, [])
    assert at(w, 2 * PERIOD) == [] and len(ai_trucks_of(w)) == 2


def test_the_ec8_guard_binds_below_max_live() -> None:
    w, _ = starving_west(cadence(3))
    assert w.rules is not None
    live = sum(e.side == "COALITION" and ON.domain[e.kind] in MOVERS for e in w.entities())
    eco = dataclasses.replace(ECO, legacy=False, max_live_per_side=live + 2)
    w.rules = dataclasses.replace(w.rules, economy=eco)
    assert guard_room(w, "COALITION") == 2
    out = at(w, 2 * PERIOD)
    assert len([e for e in out if e.kind == "UnitSpawned"]) == 2 and guard_room(w, "COALITION") == 0


def test_a_base_source_that_cannot_pay_the_spawn_cost_on_top_of_its_cargo_spawns_none() -> None:
    sup = dataclasses.replace(ON.supply, loadout_cost={**ON.supply.loadout_cost, "LOGI_TRUCK": 7})
    rules = dataclasses.replace(ON, supply=sup)
    floor, cargo = sup.starve_floor["fob-n-w"], sup.truck_cargo
    for spare, made in ((7 - 1, 0), (7, 1)):  # cost - 1 short, then exactly enough
        w, job = starving_west(rules)
        job.slots = 1
        w.stock["fob-n-w"] = floor + cargo + spare
        run = plan_run(w, rules, "COALITION", "west-airbase")
        assert run is not None and (run.source, run.cargo) == ("fob-n-w", cargo)
        at(w, 2 * PERIOD)
        assert len(ai_trucks_of(w)) == made
        assert w.stock["fob-n-w"] == (floor + cargo + spare if not made else floor)


def test_a_slot_any_claim_holds_gets_no_truck() -> None:
    w, job = starving_west()
    viewer = put(w, "LOGI_TRUCK", "haven", HUMAN, cargo=100)
    claim(w, viewer, job, [])
    at(w, 2 * PERIOD)
    assert len(ai_trucks_of(w)) == 2


def test_an_idle_ai_truck_goes_first() -> None:
    w, job = starving_west(cadence(5))  # room for 4 more: only the idle truck holds one back
    idle = put(w, "LOGI_TRUCK", "haven", AI)
    at(w, 2 * PERIOD)
    assert len(ai_trucks_of(w)) == 3  # the idle one plus two new, for the 3 free slots
    board_pass(w)  # the board gives the idle one the free slot
    assert idle.job_id == job.id and len(job.claims) == 3


def test_a_job_whose_run_loads_nothing_gets_no_truck() -> None:
    limited = dataclasses.replace(ECO, limited=("COALITION",))
    rules = cadence(rules=dataclasses.replace(RULES, economy=limited))
    w, _ = starving_west(rules)
    w.pool["COALITION"] = 0  # an empty source pool ...
    for n in ("fob-n-w", "fob-s-w"):
        w.stock[n] = rules.supply.starve_floor[n]  # ... and no base above its floor
    run = plan_run(w, rules, "COALITION", "west-airbase")
    assert run is not None and run.cargo == 0
    assert at(w, 2 * PERIOD) == [] and ai_trucks_of(w) == []


def test_more_missing_stock_draws_more_trucks_in_a_period() -> None:
    rules = cadence(9, rules=dataclasses.replace(RULES, supply=CONFIG.rules.supply))  # stocking on
    target = rules.supply.stock_target["fob-n-w"]  # 800
    w = new_world(rules=rules)
    w.stock["fob-n-w"] = target - 50  # a stocking job, 1 slot
    w.stock["west-airbase"] = 0  # a starving job, 3 slots
    board_pass(w)
    at(w, 2 * PERIOD)
    by_job = {j.node: len(j.claims) for j in jobs(w) if j.kind == "RESUPPLY"}
    assert by_job["west-airbase"] == 3 and by_job["fob-n-w"] == 1


def test_the_spawn_pays_its_loadout_cost_at_its_node() -> None:
    sup = dataclasses.replace(ON.supply, loadout_cost={**ON.supply.loadout_cost, "LOGI_TRUCK": 7})
    rules = dataclasses.replace(ON, supply=sup)
    w, _ = starving_west(rules)
    before = total(w)
    out = at(w, 2 * PERIOD)
    paid = [(e.node_id, e.amount) for e in out if e.kind == "SupplyConsumed" and e.cause == "SPAWN"]
    sources = [e.last_node for e in ai_trucks_of(w)]
    assert paid == [(n, 7) for n in sources if n in w.stock]  # the haven is infinite here
    assert total(w) == before - sum(a for _, a in paid)


def test_a_paused_clock_runs_nothing() -> None:
    w, _ = starving_west()
    w.campaign.clock_paused = True
    assert at(w, 2 * PERIOD) == [] and ai_trucks_of(w) == []


def test_the_shipped_key_switches_it_on() -> None:
    """Through the loader: `logistics.ai_trucks.max_live` 3 and a period of 930 s, rounded up to
    whole 60 s economy windows (960 s = 9,600 ticks)."""
    cfg = shipped_config({"logistics.ai_trucks.max_live": 3, "logistics.ai_trucks.period_s": 930})
    assert (cfg.rules.supply.ai_truck_max_live, cfg.rules.supply.ai_truck_period_ticks) == (
        3, 9_600,
    )  # fmt: skip
    shipped = CONFIG.rules
    assert (shipped.supply.ai_truck_max_live, shipped.supply.ai_truck_period_ticks) == (0, 9_000)


# --- LC-1: retirement -----------------------------------------------------------------------------


def test_an_empty_idle_ai_truck_retires_a_loaded_one_does_not() -> None:
    dr = RULES.director
    assert dr is not None
    w = new_world(rules=ON)
    empty, loaded = put(w, "LOGI_TRUCK", "haven", AI), put(w, "LOGI_TRUCK", "haven", AI, cargo=40)
    at(w, WINDOW)
    assert w.director["COALITION"].idle == {str(empty.id): WINDOW}
    assert at(w, WINDOW + dr.idle_retire_ticks - WINDOW) == []
    out = at(w, WINDOW + dr.idle_retire_ticks)
    assert [(e.entity_id, e.reason) for e in out if isinstance(e, UnitDespawned)] == [
        (empty.id, "RETIRED")
    ]
    assert len(out) == 1
    assert w.find(empty.id) is None and w.find(loaded.id) is loaded
    assert w.director["COALITION"].idle == {}


# --- LC-1: viewer trucks keep priority ------------------------------------------------------------


def full_of_ai(*cargo: int) -> tuple[World, Job, list[Entity]]:
    w, job = starving_west()
    job.slots = len(cargo)
    trucks = [put(w, "LOGI_TRUCK", "haven", AI, cargo=c) for c in cargo]
    for t in trucks:
        claim(w, t, job, [])
    return w, job, trucks


def test_a_viewer_displaces_the_highest_id_ai_claimant_with_no_cargo_first() -> None:
    w, job, (empty, loaded) = full_of_ai(0, 60)  # the loaded one has the higher id
    claim(w, put(w, "LOGI_TRUCK", "haven", HUMAN), job, [])
    assert empty.id not in job.claims and loaded.id in job.claims  # Q-TD-110: the run finishes
    w, job, (a, b) = full_of_ai(30, 60)  # all loaded: the highest id
    claim(w, put(w, "LOGI_TRUCK", "haven", HUMAN), job, [])
    assert a.id in job.claims and b.id not in job.claims


def test_a_displaced_loaded_ai_truck_keeps_its_route_and_an_empty_one_stops() -> None:
    route: list[str | Vec2] = ["fob-n-w", "west-airbase"]
    w, job, (a, b) = full_of_ai(30, 60)  # all loaded: b goes, and drives on to unload (Q-TD-110)
    a.path, b.path = list(route), list(route)
    claim(w, put(w, "LOGI_TRUCK", "haven", HUMAN), job, [])
    assert b.id not in job.claims and b.path == route  # CodeRabbit, PR #514
    w, job, (empty, _loaded) = full_of_ai(0, 60)
    empty.path = list(route)
    claim(w, put(w, "LOGI_TRUCK", "haven", HUMAN), job, [])
    assert empty.id not in job.claims and empty.path == route[:1]  # it finishes its road leg


def test_a_bare_join_logi_ignores_ai_claims() -> None:
    w, job, trucks = full_of_ai(0, 0, 0)
    assert job in joinable_jobs(w, "LOGI_TRUCK")
    out: list[Event] = []
    handle_join(w, join(1, "LOGI"), out)
    (viewer,) = [e for e in w.entities() if e.owner_kind == HUMAN]
    assert viewer.job_id == job.id and trucks[-1].id not in job.claims


def test_ai_trucks_never_take_a_retake_job() -> None:
    w = new_world(rules=cadence(rules=RET_RULES))
    lose(w, "fob-n-w")
    truck = put(w, "LOGI_TRUCK", "haven", AI)
    board_pass(w)
    (retake,) = [j for j in jobs(w) if j.key.startswith("retake:")]
    assert truck.job_id is None and retake.claims == {}


# --- LC-1: an AI truck is no viewer unit ----------------------------------------------------------


def test_ai_trucks_are_no_viewer_units_and_never_capture() -> None:
    dr = RULES.director
    assert dr is not None
    w, _ = starving_west()
    s = w.director["ENEMY"]
    s.last_flip = 1  # the Static flipped a node: the night cap at 0 viewers is spent
    capped = _night_capped(w, ON, s, dr, 2)
    at(w, 2 * PERIOD)
    assert w.viewer_units() == 0 and _night_capped(w, ON, s, dr, 2) == capped is True
    truck = ai_trucks_of(w)[0]
    truck.pos, truck.last_node, truck.path = put(w, "LOGI_TRUCK", "cross-n", AI).pos, "cross-n", []
    capture(w, [])
    assert "cross-n" not in w.capture  # a neutral node: no bar from AI trucks (Q-TD-14)
    w.remove(truck.id)
    put(w, "LOGI_TRUCK", "cross-n", HUMAN)
    capture(w, [])
    assert w.capture["cross-n"].side == "COALITION"  # a viewer's truck there does start one


# --- LC-1: a base lost mid-run, save and load -----------------------------------------------------


def stepped_west() -> World:
    """west-airbase empty on a world run by real `step`s (the board posts its job at tick 50)."""
    w = new_world(rules=ON)
    w.stock["west-airbase"] = 0
    return w


def test_a_destination_lost_mid_run_fails_the_job_and_the_cargo_lands_elsewhere() -> None:
    w = stepped_west()
    for _ in range(2 * PERIOD):
        step(w, [])
    (job,) = [j for j in jobs(w) if j.key == "resupply:west-airbase"]
    trucks = ai_trucks_of(w)
    assert len(trucks) == 3
    before = total(w)
    w.owner["west-airbase"] = "ENEMY"  # lost before any truck arrives
    events: list[Event] = []
    for _ in range(12_000):
        events += step(w, [])
        if all(not e.cargo for e in trucks if w.find(e.id)):
            break
    assert any(e.kind == "JobFailed" and e.job_id == job.id for e in events)
    assert all(w.find(e.id) is not None and not e.cargo for e in trucks)
    landed = {e.node_id for e in events if e.kind == "SupplyDelivered"}
    assert landed and all(w.owner[n] == "COALITION" for n in landed)
    spent = sum(e.amount for e in events if e.kind == "SupplyConsumed")
    assert total(w) + spent == before  # no cargo lost on the road


def test_two_runs_and_a_restore_with_ai_trucks_live_give_the_same_events_and_hash() -> None:
    def run(w: World, ticks: int) -> list[Event]:
        out: list[Event] = []
        for _ in range(ticks):
            out += step(w, [])
        return out

    a, b = stepped_west(), stepped_west()
    first = run(a, 2 * PERIOD + 200)
    assert first == run(b, 2 * PERIOD + 200) and len(ai_trucks_of(a)) == 3
    again = load(save(a))
    again.rules = ON
    assert state_hash(again) == state_hash(a)
    assert run(a, 3_000) == run(again, 3_000)
    assert state_hash(again) == state_hash(a)


# --- LC-3: the per-job truck cap ------------------------------------------------------------------


def raised(spread: int, rules: Rules = RULES) -> Rules:
    tasking = dataclasses.replace(TR, resupply_slots_max_starving=TR.resupply_slots_max + spread)
    return dataclasses.replace(rules, tasking=tasking)


def west_slots(rules: Rules, stock: int) -> int:
    w = new_world(rules=rules)
    w.stock["west-airbase"] = stock
    board_pass(w)
    (job,) = [j for j in jobs(w) if j.key == "resupply:west-airbase"]
    return job.slots


def test_the_default_cap_is_unchanged_and_a_raise_follows_the_need() -> None:
    assert TR.resupply_slots_max_starving == TR.resupply_slots_max == 3
    assert west_slots(RULES, 205) == 3
    assert west_slots(raised(3), 205) == 4  # need 295/500 = 0.59: 3 + floor(0.59 x 3)
    assert west_slots(raised(3), 0) == 6  # need 1
    assert west_slots(raised(3), 499) == 3  # need 1/500


def test_a_stocking_job_never_rises() -> None:
    rules = raised(6, dataclasses.replace(RULES, supply=CONFIG.rules.supply))
    assert west_slots(rules, 600) == 3  # above the floor, below the 1,600 target: 10 short slots


def test_damaged_facilities_raise_the_cap() -> None:
    rules = raised(3)
    w = new_world(rules=rules)
    for e in w.entities():
        if e.base_id == "west-airbase" and e.side == "COALITION":
            e.hp = 0  # every facility down: need 1 (stock 1,000 is above the floor)
    board_pass(w)
    (job,) = [j for j in jobs(w) if j.key == "resupply:west-airbase"]
    assert job.slots == 6


# --- LC-2: demand convoys, and the convoy's LC-3 cap ----------------------------------------------

DEMAND = 5 * DR.window_ticks
POL_FLOOR = RULES.supply.starve_floor["fob-n-e"]
_garrison_dr = GARRISON_ONLY.director
assert _garrison_dr is not None
CONVOY_DR: DirectorRules = _garrison_dr
CONVOYS = dataclasses.replace(
    GARRISON_ONLY,
    director=dataclasses.replace(
        CONVOY_DR,
        convoy_demand_ticks=DEMAND,
        max_spawns_per_window=30,
        max_live_units={t: 90 for t in DR.max_live_units},
    ),
)


def convoy_jobs(w: World) -> list[Job]:
    return [j for j in w.boards["ENEMY"].values() if j.kind == "RESUPPLY"]


def at_window(w: World, now: int, rules: Rules = CONVOYS) -> None:
    skip(w, now - 1 - w.campaign.running_ticks)
    window(w, "PATTERN_OF_LIFE", 0, rules)


def test_the_shipped_demand_is_the_period_so_nothing_changes() -> None:
    assert DR.convoy_demand_ticks == DR.convoy_ticks
    w = pol_world(1, GARRISON_ONLY, opening=True)
    w.stock["east-airbase"] = 0
    at_window(w, DEMAND, GARRISON_ONLY)
    assert convoy_jobs(w) == []  # a starving base still waits the full period
    at_window(w, DR.convoy_ticks, GARRISON_ONLY)
    assert [j.node for j in convoy_jobs(w)] == ["east-airbase"]


def test_a_starving_base_gets_a_convoy_after_the_demand_spacing_not_the_period() -> None:
    w = pol_world(1, CONVOYS, opening=True)
    w.stock["east-airbase"] = 0
    at_window(w, DEMAND - 1)
    assert convoy_jobs(w) == []
    at_window(w, DEMAND)
    (job,) = convoy_jobs(w)
    assert job.node == "east-airbase" and w.director["ENEMY"].last_convoy == DEMAND
    at_window(w, 2 * DEMAND)  # due again, but the base's convoy is still live: no second one
    assert convoy_jobs(w) == [job] and w.director["ENEMY"].last_convoy == 2 * DEMAND


def test_a_base_short_only_of_garrison_waits_the_period() -> None:
    w = pol_world(1, CONVOYS)  # no opening garrison: every base is short of units
    w.stock["fob-n-e"] = POL_FLOOR  # at its floor, not below: no margin covers the missing units
    at_window(w, DEMAND)
    assert convoy_jobs(w) == []
    at_window(w, DR.convoy_ticks)
    assert len(convoy_jobs(w)) == 1


def test_the_night_cap_does_not_hold_a_demand_convoy() -> None:
    w = pol_world(1, CONVOYS, opening=True)
    w.stock["east-airbase"] = 0
    s = w.director["ENEMY"]
    s.last_flip = DEMAND - 10
    assert _night_capped(w, CONVOYS, s, CONVOYS.director, DEMAND)  # type: ignore[arg-type]
    at_window(w, DEMAND)
    assert len(convoy_jobs(w)) == 1


def test_a_paused_clock_freezes_the_demand_timer() -> None:
    w = pol_world(1, CONVOYS, opening=True)
    w.stock["east-airbase"] = 0
    w.campaign.clock_paused = True
    for _ in range(DEMAND + DR.window_ticks):
        step(w, [])
    assert w.campaign.running_ticks == 0 and convoy_jobs(w) == []


def test_the_convoy_takes_trucks_by_its_shortfall_up_to_the_raised_cap() -> None:
    def slots(stock: int, spread: int) -> int:
        rules = raised(spread, CONVOYS)
        w = pol_world(1, rules, opening=True)
        w.stock["east-airbase"] = stock
        at_window(w, DEMAND, rules)
        (job,) = convoy_jobs(w)
        return job.slots

    assert slots(0, 0) == DR.convoy_slots == 1  # the default: unchanged
    assert slots(0, 3) == 4  # need 1: cap 1 + 3; shortfall 500 wants 5 trucks
    assert slots(250, 3) == 2  # need 0.5: cap 1 + 1; shortfall 250 wants 3
    assert slots(400, 3) == 1  # need 0.2: cap 1 + 0


def test_a_raised_convoy_cap_shrinks_to_the_spawn_room_instead_of_skipping_the_base() -> None:
    def slots(spawns: int) -> int | None:
        base = raised(3, CONVOYS)
        assert base.director is not None
        rules = dataclasses.replace(
            base, director=dataclasses.replace(base.director, max_spawns_per_window=spawns)
        )
        w = pol_world(1, rules, opening=True)
        w.stock["east-airbase"] = 0  # need 1: the raised cap is 4
        at_window(w, DEMAND, rules)
        found = convoy_jobs(w)
        return found[0].slots if found else None

    assert slots(30) == 4  # room enough: the raised cap
    assert slots(2) == 2  # less room than the cap: a smaller convoy, not none (CodeRabbit, #514)
    assert slots(0) is None  # no room for even `convoy_slots`: skipped, as before


def test_damaged_facilities_raise_the_convoys_cap() -> None:
    sup = dataclasses.replace(RULES.supply, truck_cargo=1)  # the shortfall wants many trucks
    rules = dataclasses.replace(raised(3, CONVOYS), supply=sup)

    def slots(damaged: bool) -> int:
        w = pol_world(1, rules, opening=True)
        w.stock["east-airbase"] = RULES.supply.starve_floor["east-airbase"] - 10  # need 0.02
        if damaged:
            for e in w.entities():
                if e.base_id == "east-airbase" and e.side == "ENEMY":
                    e.hp = 0  # every facility down: need 1
        at_window(w, DEMAND, rules)
        (job,) = convoy_jobs(w)
        return job.slots

    assert (slots(False), slots(True)) == (1, 4)  # cap 1 + floor(0.02 x 3); 1 + 3


def test_a_restored_world_runs_the_same_demand_convoys() -> None:
    def make() -> World:
        w = pol_world(1, CONVOYS, opening=True)
        w.rules = CONVOYS
        w.stock["east-airbase"] = 0
        return w

    a, b = make(), make()
    ev_a = [e for _ in range(DEMAND + 10) for e in step(a, [])]
    ev_b = [e for _ in range(DEMAND + 10) for e in step(b, [])]
    assert ev_a == ev_b and any(e.kind == "JobCreated" and e.side == "ENEMY" for e in ev_a)
    again = load(save(a))
    again.rules = CONVOYS
    assert [e for _ in range(500) for e in step(a, [])] == [
        e for _ in range(500) for e in step(again, [])
    ]
    assert state_hash(again) == state_hash(a)


def test_the_lc2_and_lc3_keys_load_through_the_shipped_profile() -> None:
    """The cross-key refusals are in tests/runtime/test_config.py."""
    cfg = shipped_config(
        {"tasking.resupply_slots_max_starving": 6, "director.pol.convoy_demand_s": 300}
    )
    assert cfg.rules.tasking is not None and cfg.rules.director is not None
    assert cfg.rules.tasking.resupply_slots_max_starving == 6
    assert cfg.rules.director.convoy_demand_ticks == 3_000
