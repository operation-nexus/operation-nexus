"""NX-461: the SEAD strike job (Q-TD-81, amends GAMEPLAY §1b `strike:<node>`). A foe-held node with
a discovered facility marker last seen not Disabled keeps its `strike:<node>` job at any defense hp;
the job ends once the side owns the node, or the node is at 0 hp and the marker shows the site
Disabled. Both boards (ECONOMY EC-3). Scenes reuse `test_tasking` (strait-1, campaign off, board
passes by hand; the scenario test uses real `step`s).
"""

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_tasking import HUMAN, RULES, TR, board_pass, jobs, kinds, new_world, of, post, put

from nexus.contracts.gen.common.enums import DamageState, NodeOwner, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core.fog import side_view
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.tasking import _verdict, post_job, take
from nexus.core.tasking_gen import JobSpec, generate
from nexus.core.world import Entity, FacilityMarker, Vec2, World, state_hash

TARGET: dict[Side, str] = {"COALITION": "fob-n-e", "ENEMY": "fob-n-w"}  # a FOB the foe holds
MARKER = 99


def scene(side: Side = "COALITION", kind: UnitKind = "AIR_DEFENSE_SITE") -> tuple[World, str]:
    """`side`'s board can staff a strike; the foe FOB is at 0 defense hp with a live marker."""
    w = new_world()
    node = TARGET[side]
    if side == "ENEMY":
        w.director["ENEMY"].tier = TR.static_offense_min_tier  # the Static's board strikes
        put(w, "ENEMY_STRIKE_FIGHTER", "static-hq", "AI_GARRISON")
    w.defense_hp[node] = 0
    pos = Vec2(*RULES.roads.pos[node])
    w.markers[side][MARKER] = FacilityMarker(kind, None, pos, True, 1, 4_000, "HEALTHY")
    return w, node


def disable(w: World, side: Side) -> None:
    w.markers[side][MARKER] = dataclasses.replace(w.markers[side][MARKER], state="DISABLED")


def state_of(e: Entity) -> DamageState:  # read again (a loop's assert narrows the attribute)
    return e.damage_state


def strikes(w: World, side: Side) -> list[tuple[int, str]]:
    return [(j.id, j.key) for j in jobs(w, side) if j.kind == "STRIKE"]


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])  # EC-3: both boards
@pytest.mark.parametrize("kind", ["AIR_DEFENSE_SITE", "RADAR_SITE"])  # any facility marker
def test_a_zero_hp_node_with_a_live_site_keeps_its_strike_job_without_flapping(
    side: Side, kind: UnitKind
) -> None:
    w, node = scene(side, kind)
    board_pass(w)
    first = strikes(w, side)
    assert [k for _, k in first] == [f"strike:{node}"]
    for _ in range(4):  # same job, no JobCreated / JobExpired / JobDone churn
        assert [k for k in kinds(board_pass(w)) if k.startswith("Job")] == []
        assert strikes(w, side) == first


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])
def test_a_zero_hp_node_whose_site_was_last_seen_disabled_gets_no_strike_job(side: Side) -> None:
    w, _ = scene(side)
    disable(w, side)
    board_pass(w)
    assert strikes(w, side) == []


def test_a_claimed_sead_job_ends_done_once_the_marker_shows_the_site_disabled() -> None:
    w, _ = scene()
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")
    board_pass(w)
    ((job_id, _),) = strikes(w, "COALITION")
    assert jet.job_id == job_id
    for _ in range(3):  # flying (ACTIVE), 0 hp: the job holds
        assert "JobDone" not in kinds(board_pass(w))
    assert jet.job_id == job_id
    disable(w, "COALITION")
    events = board_pass(w)
    assert "JobDone" in kinds(events) and job_id not in w.boards["COALITION"]
    assert strikes(w, "COALITION") == []  # and it is not posted again


def test_the_verdict_keeps_a_sead_job_only_on_a_foe_node_with_a_live_marker() -> None:
    w, node = scene()
    board_pass(w)
    job = jobs(w)[0]
    assert _verdict(w, RULES, TR, "COALITION", job) is None  # 0 hp, live site
    w.owner[node] = "NEUTRAL"  # nobody's: nothing to suppress for the board
    assert _verdict(w, RULES, TR, "COALITION", job) == "DONE"
    w.owner[node] = "COALITION"  # the side owns it
    assert _verdict(w, RULES, TR, "COALITION", job) == "DONE"
    w.owner[node] = "ENEMY"
    disable(w, "COALITION")
    assert _verdict(w, RULES, TR, "COALITION", job) == "DONE"
    w.defense_hp[node] = 5  # defenses left: the old rule, a Disabled site does not end it
    assert _verdict(w, RULES, TR, "COALITION", job) is None
    w.defense_hp[node] = 0
    elsewhere = Vec2(*RULES.roads.pos["fob-s-e"])  # a live site at another foe node
    w.markers["COALITION"][MARKER] = FacilityMarker(
        "AIR_DEFENSE_SITE", None, elsewhere, True, 1, 4_000, "HEALTHY"
    )
    assert _verdict(w, RULES, TR, "COALITION", job) == "DONE"
    assert f"strike:{node}" not in [
        s.key for s in generate(w, RULES, TR, "COALITION", side_view(w, "COALITION"))
    ]


def test_an_objective_strike_is_still_met_at_zero_hp_with_a_live_site() -> None:
    """An objective strike has no expiry, so SEAD does not hold it (Q-TD-81, CodeRabbit on #469):
    at 0 hp it is DONE as before, and only a plain board `strike:` job is kept for the site."""
    w, _ = scene()
    board_pass(w)
    job = jobs(w)[0]
    assert _verdict(w, RULES, TR, "COALITION", job) is None  # a plain SEAD job: kept
    job.objective = 1  # the same key, posted for an objective
    assert _verdict(w, RULES, TR, "COALITION", job) == "DONE"


def _strike_first(on: bool) -> Rules:
    assert RULES.combat is not None
    return dataclasses.replace(
        RULES, combat=dataclasses.replace(RULES.combat, strike_structure_first=on)
    )


def _sead_run(on: bool, ticks: int = 15_000) -> tuple[World, Entity, Entity, list[Event]]:
    """A viewer's jet at west-airbase, fob-n-e at 0 hp with its real short-range site marked
    live; real steps until the jet's first round at the site (or `ticks`)."""
    w = new_world(rules=_strike_first(on))
    w.defense_hp["fob-n-e"] = 0
    (site,) = [e for e in w.entities() if e.base_id == "fob-n-e"]
    w.markers["COALITION"][site.id] = FacilityMarker(
        site.kind, site.variant, site.pos, site.emitting, 1, 4_000, "HEALTHY"
    )
    jet = put(w, "STRIKE_FIGHTER", "west-airbase", HUMAN)
    events: list[Event] = []
    for _ in range(ticks):
        events += step(w, [])
        if any(f.target_id == site.id for f in of(events, WeaponFired)):
            break
    return w, jet, site, events


@pytest.mark.parametrize("on", [False, True])  # combat.strike_structure_first both ways
def test_a_jet_claims_the_sead_job_and_fires_at_the_site(on: bool) -> None:
    w, jet, site, events = _sead_run(on)
    (job,) = [j for j in jobs(w) if j.key == "strike:fob-n-e"]
    assert jet.job_id == job.id
    shots = [f for f in of(events, WeaponFired) if f.shooter_id == jet.id]
    assert shots and (shots[-1].target_id, shots[-1].target_node_id) == (site.id, None)


def test_the_sead_scenario_is_deterministic() -> None:
    def once() -> tuple[str, list[str]]:
        w, _, _, events = _sead_run(True)
        return state_hash(w), [e.model_dump_json() for e in events]

    a = once()
    assert a == once() and any('"WeaponFired"' in e for e in a[1])


@pytest.mark.parametrize("on", [False, True])  # combat.strike_structure_first both ways
def test_a_sead_package_puts_the_site_out_until_it_is_repaired_to_the_mission_kill_line(
    on: bool,
) -> None:
    """Real steps (Q-TD-81, Q-TD-86): four viewer jets take the SEAD job on fob-n-e (0 hp, its
    short-range site marked live) and Disable the site; the board pass that sees it Disabled ends
    the job and posts no new one while it stays Disabled; the site stays Disabled (off) while the
    FOB repairs it past the floor (14 hp) up to the Mission-kill line (53 hp, 0.3 hp a tick), and
    only then engages again (a LOW aircraft inside its AAA_GUN's 4 km)."""
    w = new_world(rules=_strike_first(on))
    w.defense_hp["fob-n-e"] = 0
    (site,) = [e for e in w.entities() if e.base_id == "fob-n-e"]
    w.markers["COALITION"][site.id] = FacilityMarker(
        site.kind, site.variant, site.pos, site.emitting, 1, 4_000, "HEALTHY"
    )
    jets = [put(w, "STRIKE_FIGHTER", "west-airbase", HUMAN).id for _ in range(4)]
    events: list[Event] = []
    while site.damage_state != "DISABLED":
        assert w.campaign.running_ticks < 5_000
        events += step(w, [])
    ((job_id, _),) = strikes(w, "COALITION")
    while job_id in w.boards["COALITION"]:  # the next pass sees the site Disabled
        events += step(w, [])
    ended = [e for e in events if e.kind in ("JobDone", "JobExpired") and e.job_id == job_id]
    # Q-TD-87 (NX-463): the jets spent their bombs on the site and went RTB before the pass, yet
    # they fired at it holding the claim, so the job is DONE crediting every one of them
    shooters = sorted({f.shooter_id for f in of(events, WeaponFired) if f.target_id == site.id})
    done = [
        [p.entity_id for p in e.participants] for e in of(events, JobDone) if e.job_id == job_id
    ]
    assert len(ended) == 1 and done == [jets] and shooters == jets
    assert w.markers["COALITION"][site.id].state == "DISABLED"
    disabled_hp = []
    while site.hp < 53:
        disabled_hp.append(site.hp)
        assert site.damage_state == "DISABLED" and strikes(w, "COALITION") == []
        events = step(w, [])
        assert not [f for f in of(events, WeaponFired) if f.shooter_id == site.id]
    assert max(disabled_hp) == 52 and state_of(site) == "DAMAGED"  # back at the line
    x, y = site.pos.x, site.pos.y
    low = w.spawn("RECON_UAV", "COALITION", "AI_GARRISON", Vec2(x + 2_000, y))
    low.alt_band, low.order, low.fuel = "LOW", "HOLD", RULES.fuel_s["RECON_UAV"]
    low.state = "ON_STATION"  # airborne where it stands, held off the board
    for _ in range(200):
        if any(f.shooter_id == site.id for f in of(step(w, []), WeaponFired)):
            break
    else:
        raise AssertionError("the repaired site never engaged again")


def test_a_director_operation_strike_is_still_met_at_zero_hp_and_opens_its_capture() -> None:
    """Only the board's `strike:` jobs are SEAD jobs (Q-TD-81): an operation's STRIKE on a 0-hp
    node is DONE even with a live site there, so the CAPTURE waiting on it opens (THREAT-DIRECTOR
    §7a; QA's reproduction of the stall)."""
    w = new_world()
    w.director["ENEMY"].tier = TR.static_offense_min_tier
    jet = put(w, "ENEMY_STRIKE_FIGHTER", "static-hq", "ENEMY_DIRECTOR")
    node = TARGET["ENEMY"]
    strike = post(w, "ENEMY", "STRIKE", node, "OFFENSIVE:fob-n-w:1", slots=1)
    cap = post(w, "ENEMY", "CAPTURE", node, "OFFENSIVE:fob-n-w:2", depends_on=strike.id)
    take(w, jet, strike, [])  # the operation's jet claims at spawn (NX-156)
    board_pass(w)  # flying: ACTIVE
    assert jet.job_id == strike.id
    w.defense_hp[node] = 0
    pos = Vec2(*RULES.roads.pos[node])
    w.markers["ENEMY"][MARKER] = FacilityMarker(
        "AIR_DEFENSE_SITE", None, pos, True, 1, 4_000, "HEALTHY"
    )
    events = board_pass(w)
    assert [d.job_id for d in of(events, JobDone)] == [strike.id]
    assert strike.id not in w.boards["ENEMY"] and w.boards["ENEMY"][cap.id].depends_on is None


_OWNERS: dict[str, NodeOwner] = {"foe": "ENEMY", "neutral": "NEUTRAL", "own": "COALITION"}
_STATES = ["HEALTHY", "DAMAGED", "MISSION_KILL", "DISABLED", "absent", "other-node"]


@settings(max_examples=60, deadline=None)
@given(
    owner=st.sampled_from(sorted(_OWNERS)),
    hp=st.sampled_from([0, 5]),
    state=st.sampled_from(_STATES),
)
def test_the_generator_and_the_verdict_agree_so_no_strike_job_flaps(
    owner: str, hp: int, state: str
) -> None:
    """A posted `strike:` job is never ended by the verdict of the same pass; at 0 hp a job the
    verdict keeps is one the generator posts (the SEAD rule is one rule, Q-TD-81)."""
    w = new_world()
    node = TARGET["COALITION"]
    w.owner[node], w.defense_hp[node] = _OWNERS[owner], hp
    if state != "absent":
        at = "fob-s-e" if state == "other-node" else node
        mark = "HEALTHY" if state == "other-node" else state
        w.markers["COALITION"][MARKER] = FacilityMarker(
            "AIR_DEFENSE_SITE",
            None,
            Vec2(*RULES.roads.pos[at]),
            True,
            1,
            4_000,
            mark,  # type: ignore[arg-type]
        )
    keys = [s.key for s in generate(w, RULES, TR, "COALITION", side_view(w, "COALITION"))]
    job = post_job(w, "COALITION", JobSpec("STRIKE", f"strike:{node}", 2, 1000, node=node), [])
    kept = _verdict(w, RULES, TR, "COALITION", job) is None
    posted = f"strike:{node}" in keys
    assert kept or not posted
    if hp == 0:
        assert kept == posted
