"""NX-382 part 2: the Static's scout intercepts (Q-SIM-96; THREAT-DIRECTOR §5a; FOG-OF-WAR FOW-4).

Runs on the shipped strait-1 config with the campaign layer off (see `test_tasking`). Shipped
numbers: radius 30,000 m, reaction 60 game s (600 ticks, 12 board passes of 50), Pattern of Life
linger 600 game s (6,000 ticks), leash 80,000 m, lost after 120 game s (1,200 ticks). The Static
holds east-airbase (310 km, 120 km), fob-n-e (290, 40), fob-s-e (290, 200), static-hq (380, 120).
`board_pass` runs a board pass without moving anything, so the scene is set by hand.
"""

from typing import Any

import msgpack
import pytest
from test_tasking import EVERY, RULES, board_pass, jobs, new_world, of, put

from nexus.contracts.gen.common.enums import OwnerKind, ThreatTier, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.job_created import JobCreated
from nexus.contracts.gen.events.job_done import JobDone
from nexus.contracts.gen.events.job_expired import JobExpired
from nexus.contracts.gen.events.job_released import JobReleased
from nexus.core.launch import _recall
from nexus.core.provocation import suffered_hit
from nexus.core.rules import DirectorRules
from nexus.core.tasking import post_job
from nexus.core.tasking_gen import JobSpec, can_hit, fits
from nexus.core.world import Contact, Entity, Vec2, World, load, save, state_hash

DIRECTOR: OwnerKind = "ENEMY_DIRECTOR"  # the Static's units are the Director's (garrison included)
DR: DirectorRules = RULES.director  # type: ignore[assignment]
REACTION, LINGER, LOST = (
    DR.intercept_reaction_ticks,
    DR.intercept_pol_linger_ticks,
    DR.intercept_lost_ticks,
)
NEAR = (290_000.0, 120_000.0)  # 20 km from east-airbase
AWAY = (100_000.0, 120_000.0)  # nowhere near a Static node


def scene(tier: ThreatTier = "ALPHA", where: tuple[float, float] = NEAR) -> tuple[World, Entity]:
    """A coalition RECON_UAV tracked by the Static, and a Static fighter at east-airbase that has
    no rounds (so it can staff nothing, yet makes the board able to post an intercept)."""
    w = new_world()
    w.director["ENEMY"].tier = tier
    scout = w.spawn("RECON_UAV", "COALITION", "COMMANDER", Vec2(*where), commander_id="c-1")
    scout.state, scout.alt_band, scout.fuel = "ON_STATION", "MED", RULES.fuel_s["RECON_UAV"]
    track(w, scout)
    dud = put(w, "ENEMY_FIGHTER", "east-airbase", DIRECTOR)
    dud.ammo = [0]
    return w, scout


def track(
    w: World, scout: Entity, *, at: tuple[float, float] | None = None, age: int | None = None
) -> None:
    pos = scout.pos if at is None else Vec2(*at)
    w.contacts["ENEMY"][scout.id] = Contact(scout.kind, pos, Vec2(0, 0), age)


def kill(w: World, scout: Entity) -> None:
    """The scout is destroyed and the Static's track of it goes with it."""
    w.remove(scout.id)
    del w.contacts["ENEMY"][scout.id]


def posted(w: World) -> list[Any]:
    return [j for j in jobs(w, "ENEMY") if j.kind == "INTERCEPT"]


def passes(w: World, n: int) -> None:
    for _ in range(n):
        board_pass(w)


def ripe(w: World, scout: Entity) -> None:
    """The scout has been watched long enough: the next pass posts the intercept."""
    w.campaign.running_ticks = 5999
    w.intercept_seen[scout.id] = 1


def hunted() -> tuple[World, Entity, Entity]:
    """A ripe scene with a fighter that can hit the scout, which claims the job."""
    w, scout = scene()
    ripe(w, scout)
    fighter = put(w, "ENEMY_FIGHTER", "east-airbase", DIRECTOR)
    board_pass(w)
    return w, scout, fighter


# --- the reaction clock ---------------------------------------------------------------------------


def test_shipped_intercept_numbers() -> None:
    assert (DR.intercept_radius_m, DR.intercept_leash_m) == (30_000, 80_000)
    assert (REACTION, LINGER, LOST) == (600, 6_000, 1_200)
    assert RULES.tasking.priority["INTERCEPT"] == 45 and RULES.tasking.slots["INTERCEPT"] == 1  # type: ignore[union-attr]


def test_the_intercept_is_posted_after_exactly_the_reaction_at_alpha() -> None:
    w, scout = scene()
    passes(w, REACTION // EVERY)  # the first pass starts the clock, the next 11 age it to 550
    assert posted(w) == []
    board_pass(w)  # 600 ticks after the first pass
    (job,) = posted(w)
    assert (job.key, job.entity, job.slots, job.urgency) == (
        f"intercept:{scout.id}",
        scout.id,
        1,
        1000,
    )
    assert job.node is None and job.blob is None and job.pos == scout.pos


def test_pattern_of_life_waits_for_the_longer_linger() -> None:
    w, _ = scene("PATTERN_OF_LIFE")
    passes(w, LINGER // EVERY)
    assert posted(w) == []  # the ALPHA reaction passed long ago
    board_pass(w)
    assert len(posted(w)) == 1


@pytest.mark.parametrize("breaks", ["leaves the radius", "is only a last-known track"])
def test_the_clock_restarts_when_the_scout_leaves_or_stops_being_tracked(breaks: str) -> None:
    w, scout = scene()
    passes(w, 6)
    if breaks == "leaves the radius":
        track(w, scout, at=AWAY)
    else:
        track(w, scout, age=1)
    board_pass(w)
    assert scout.id not in w.intercept_seen
    track(w, scout)  # back; the clock starts over
    passes(w, REACTION // EVERY)
    assert posted(w) == []
    board_pass(w)
    assert len(posted(w)) == 1


def test_a_last_known_track_never_counts() -> None:
    w, scout = scene()
    track(w, scout, age=3)
    passes(w, 2 * REACTION // EVERY)
    assert w.intercept_seen == {} and posted(w) == []


def test_a_coalition_aircraft_that_is_not_a_painter_does_not_start_the_clock() -> None:
    w, _ = scene()
    jet = w.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(*NEAR), commander_id="c-2")
    w.contacts["ENEMY"].clear()
    w.contacts["ENEMY"][jet.id] = Contact(jet.kind, jet.pos, Vec2(0, 0))
    passes(w, 2 * REACTION // EVERY)
    assert w.intercept_seen == {} and posted(w) == []


def test_the_clock_is_world_state_and_survives_a_snapshot() -> None:
    w, scout = scene()
    passes(w, 3)
    seen = dict(w.intercept_seen)
    assert seen == {scout.id: EVERY}  # the first pass, at running tick 50
    w.campaign.tick = w.campaign.running_ticks
    back = load(save(w))
    assert back.intercept_seen == seen and state_hash(back) == state_hash(w)
    w.intercept_seen[scout.id] += 1
    assert state_hash(back) != state_hash(w)  # the clock is in the hash


# --- who takes it ---------------------------------------------------------------------------------


def test_fits_is_armed_aircraft_only() -> None:
    assert fits(RULES, "ENEMY_FIGHTER", "INTERCEPT") and fits(
        RULES, "ENEMY_STRIKE_FIGHTER", "INTERCEPT"
    )
    for kind in ("ENEMY_RECON_UAV", "ENEMY_ARMOR", "ENEMY_CONVOY"):
        assert not fits(RULES, kind, "INTERCEPT")


@pytest.mark.parametrize(
    ("kind", "ammo", "takes"),
    [
        ("ENEMY_FIGHTER", [4], True),
        ("ENEMY_FIGHTER", [0], False),  # no round left
        ("ENEMY_STRIKE_FIGHTER", [4, 0], False),  # only its air-to-ground rounds are left
        ("ENEMY_STRIKE_FIGHTER", [0, 400], True),  # its light air-to-air gun reaches a MED scout
        ("ENEMY_RECON_UAV", [], False),  # unarmed
        ("ENEMY_ARMOR", None, False),  # a ground unit
    ],
)
def test_only_armed_aircraft_that_can_hit_the_scout_take_it(
    kind: UnitKind, ammo: list[int] | None, takes: bool
) -> None:
    w, scout = scene()
    ripe(w, scout)
    unit = put(w, kind, "east-airbase", DIRECTOR)
    if ammo is not None:
        unit.ammo = ammo
    board_pass(w)
    (job,) = posted(w)
    assert (unit.job_id == job.id) is takes
    if takes:
        assert unit.path == [scout.pos]  # it flies at once, from its base


def test_can_hit_reads_the_loaded_weapons_and_the_scouts_band() -> None:
    w, _ = scene()
    jet = put(w, "ENEMY_STRIKE_FIGHTER", "east-airbase", DIRECTOR)
    assert can_hit(RULES, jet, "RECON_UAV")  # AA_LIGHT covers LOW and MED, the recon's band is MED
    jet.ammo = [4, 0]
    assert not can_hit(RULES, jet, "RECON_UAV")


def test_can_hit_needs_the_scouts_band_in_the_weapons_reach() -> None:
    w, _ = scene()
    flak = w.spawn("AIR_DEFENSE_SITE", "ENEMY", DIRECTOR, Vec2(*NEAR), variant="SHORT_RANGE")
    assert not can_hit(RULES, flak, "RECON_UAV")  # its gun reaches NOE and LOW, the recon flies MED


def test_it_ranks_between_defend_and_strike() -> None:
    from nexus.core.tasking import priority
    from nexus.core.world import Job

    tr = RULES.tasking
    assert tr is not None
    job = Job(1, "INTERCEPT", "intercept:1", 1, 1000, 0)
    assert priority(tr, Job(2, "STRIKE", "s", 1, 1000, 0), 0) < priority(tr, job, 0)
    assert priority(tr, job, 0) < priority(tr, Job(3, "DEFEND", "d", 1, 1000, 0), 0)


# --- garrison fighters ----------------------------------------------------------------------------


def garrison(w: World, home: str) -> Entity:
    unit = put(w, "ENEMY_FIGHTER", home, DIRECTOR)
    unit.home = home
    return unit


@pytest.mark.parametrize(
    ("home", "takes"),
    [("east-airbase", True), ("static-hq", False), (None, True)],  # 65 km, 112 km, no leash
)
def test_a_garrison_fighter_takes_an_intercept_within_its_leash_only(
    home: str | None, takes: bool
) -> None:
    w, scout = scene(where=(285_000.0, 60_000.0))  # 20 km from fob-n-e
    ripe(w, scout)
    unit = put(w, "ENEMY_FIGHTER", home or "static-hq", DIRECTOR)
    unit.home = home
    board_pass(w)
    (job,) = posted(w)
    assert (unit.job_id == job.id) is takes


def test_the_leash_holds_for_the_whole_chase() -> None:
    w, scout = scene()
    ripe(w, scout)
    home = garrison(w, "east-airbase")  # the scout is 20 km off: in the leash
    free = put(w, "ENEMY_FIGHTER", "east-airbase", DIRECTOR)  # no home
    board_pass(w)
    job = posted(w)[0]
    assert home.job_id == job.id and free.job_id == job.id  # overfill: both chase
    track(w, scout, at=(310_000.0 + DR.intercept_leash_m + 1, 120_000.0))  # near static-hq
    out = board_pass(w)
    assert home.job_id is None and home.path == []
    assert [e.entity_id for e in of(out, JobReleased)] == [home.id]
    assert free.job_id == job.id and free.path == [job.pos]  # no leash: it keeps chasing
    out = board_pass(w)
    assert home.job_id is None  # and the board does not give it the job again
    home.state, home.last_node = "ON_STATION", None  # it is away from its base
    _recall(w, RULES, "ENEMY")
    assert home.path == ["east-airbase"]


def test_a_garrison_fighter_still_takes_nothing_else_away_from_home() -> None:
    w, _ = scene()
    unit = garrison(w, "east-airbase")
    post_job(w, "ENEMY", JobSpec("STRIKE", "strike:haven", 1, 1000, node="haven"), [])
    board_pass(w)
    assert unit.job_id is None


def test_the_garrison_fighter_goes_home_after_the_intercept() -> None:
    w, scout = scene()
    ripe(w, scout)
    unit = garrison(w, "east-airbase")
    board_pass(w)
    assert unit.job_id is not None
    unit.state, unit.last_node, unit.path = "ON_STATION", None, []  # it chased the scout out
    unit.orbit = scout.pos
    kill(w, scout)
    board_pass(w)
    assert unit.job_id is None  # the job is done, the unit is idle again
    assert unit.path == []  # it stops chasing a dead scout
    _recall(w, RULES, "ENEMY")
    assert unit.path == ["east-airbase"]


# --- how it ends ----------------------------------------------------------------------------------


def test_the_job_is_done_when_the_scout_is_destroyed() -> None:
    w, scout, fighter = hunted()
    board_pass(w)  # the claimant has made progress (a path): it is a participant
    kill(w, scout)
    out = board_pass(w)
    assert posted(w) == [] and len(of(out, JobDone)) == 1
    assert [p.entity_id for p in of(out, JobDone)[0].participants] == [fighter.id]
    assert fighter.job_id is None


def test_a_scout_knocked_to_disabled_also_ends_the_job() -> None:
    w, scout, _ = hunted()
    board_pass(w)
    scout.damage_state = "DISABLED"  # the Static's contact of the wreck stays tracked
    assert len(of(board_pass(w), JobDone)) == 1
    assert posted(w) == []
    assert JobCreated not in {type(e) for _ in range(4) for e in board_pass(w)}
    assert posted(w) == [] and w.intercept_seen == {}


def test_a_wreck_or_a_removed_scout_with_a_lingering_track_is_not_hunted_again() -> None:
    for how in ("removed", "disabled"):
        w, scout, _ = hunted()
        board_pass(w)
        if how == "removed":
            w.remove(scout.id)  # the contact lingers until sensing drops it
        else:
            scout.damage_state = "DISABLED"
        events = [e for _ in range(5) for e in board_pass(w)]
        assert len(of(events, JobDone)) == 1 and of(events, JobCreated) == []
        assert posted(w) == [] and w.intercept_seen == {}, how


def test_a_kill_with_nobody_active_on_the_job_expires_it() -> None:
    w, scout, fighter = hunted()
    fighter.path = []  # it never got going: no progress, so it is no participant
    kill(w, scout)  # killed by something else
    out = board_pass(w)
    assert posted(w) == [] and of(out, JobDone) == [] and len(of(out, JobExpired)) == 1


def test_the_job_ends_when_the_scout_was_untracked_for_lost_s() -> None:
    w, scout, fighter = hunted()
    board_pass(w)
    del w.contacts["ENEMY"][scout.id]  # the track faded
    passes(w, LOST // EVERY)  # the first finds it untracked, the last is 1,150 ticks on
    assert len(posted(w)) == 1
    out = board_pass(w)
    assert posted(w) == [] and len(of(out, JobExpired)) == 1 and fighter.job_id is None


def test_a_track_that_is_already_old_counts_its_age() -> None:
    w, scout, _ = hunted()
    board_pass(w)
    track(w, scout, age=LOST - EVERY)  # untracked for 1,150 ticks already
    out = board_pass(w)  # 1,150 at this pass, so 1,200 at the next
    assert len(posted(w)) == 1 and of(out, JobExpired) == []
    assert len(of(board_pass(w), JobExpired)) == 1


def test_a_track_found_again_resets_the_lost_clock() -> None:
    w, scout, _ = hunted()
    board_pass(w)
    track(w, scout, age=EVERY)
    passes(w, 10)
    track(w, scout)  # tracked again
    passes(w, 10)
    assert len(posted(w)) == 1 and posted(w)[0].lost is None


def test_the_job_ends_when_the_scout_is_no_longer_in_range_of_a_held_node() -> None:
    w, scout, fighter = hunted()
    board_pass(w)
    track(w, scout, at=AWAY)  # still tracked, but far from every Static node
    out = board_pass(w)
    assert posted(w) == [] and len(of(out, JobExpired)) == 1 and fighter.job_id is None
    assert fighter.path == []  # it stops chasing, not flies on to the last track


def test_an_unclaimed_job_goes_when_the_scout_does() -> None:
    w, scout = scene()
    ripe(w, scout)
    board_pass(w)
    assert len(posted(w)) == 1  # the only fighter has no rounds: nobody claims it
    track(w, scout, age=1)
    out = board_pass(w)
    assert posted(w) == [] and len(of(out, JobExpired)) == 1


def test_the_interceptor_chases_the_track_not_the_truth() -> None:
    w, scout, fighter = hunted()
    track(w, scout, at=(300_000.0, 130_000.0))  # the Static's track is off from where it is
    board_pass(w)
    assert posted(w)[0].pos == Vec2(300_000.0, 130_000.0)
    assert fighter.path == [Vec2(300_000.0, 130_000.0)]
    assert scout.pos == Vec2(*NEAR)


# --- no provocation -------------------------------------------------------------------------------


def lifecycle(with_fighter: bool) -> tuple[Any, ThreatTier]:
    """A viewer's scout flies in, is tracked, hunted and shot down (or not hunted at all)."""
    w, scout = scene()
    fighter = put(w, "ENEMY_FIGHTER", "east-airbase", DIRECTOR) if with_fighter else None
    ripe(w, scout)
    passes(w, 3)
    if fighter is not None:
        suffered_hit(w, fighter, scout, "HEALTHY")  # the interceptor's shot lands
    kill(w, scout)
    passes(w, 2)
    d = w.director["ENEMY"]
    return (d.pending, d.provocation, d.last_provocation_tick), d.tier


def test_an_intercept_adds_no_provocation_and_leaves_the_tier_alone() -> None:
    assert lifecycle(with_fighter=True) == lifecycle(with_fighter=False)
    (pending, provocation, tick), tier = lifecycle(with_fighter=True)
    assert (pending, provocation, tick, tier) == (0, 0, 0, "ALPHA")


# --- snapshot rules -------------------------------------------------------------------------------


def raw_of(w: World) -> dict[str, Any]:
    w.campaign.tick = w.campaign.running_ticks
    raw = msgpack.unpackb(save(w), raw=False)
    assert isinstance(raw, dict)
    return raw


def reload(raw: dict[str, Any]) -> World:
    return load(msgpack.packb(raw, use_bin_type=True))


def test_a_world_with_an_intercept_round_trips_and_continues_the_same() -> None:
    w, scout, _ = hunted()
    passes(w, 2)
    track(w, scout, age=EVERY)
    board_pass(w)
    assert posted(w)[0].lost is not None
    again = reload(raw_of(w))
    again.rules = w.rules
    assert state_hash(again) == state_hash(w) and posted(again)[0].lost == posted(w)[0].lost
    for world in (w, again):
        world.contacts["ENEMY"] = {scout.id: Contact("RECON_UAV", scout.pos, Vec2(0, 0), 4)}
    passes(w, 3)
    passes(again, 3)
    assert state_hash(again) == state_hash(w)


def test_the_loader_refuses_a_bad_clock_or_intercept_job() -> None:
    w, scout, _ = hunted()
    post_job(w, "ENEMY", JobSpec("STAGE", "op:x", 1, 1000, node="east-airbase"), [])
    w.campaign.running_ticks += 1
    good = raw_of(w)
    assert good["v"] == 27

    def job(r: dict[str, Any]) -> dict[str, Any]:
        return next(j for j in r["boards"]["ENEMY"] if j["kind"] == "INTERCEPT")

    def bad(edit: Any, why: str) -> None:
        raw = raw_of(w)
        edit(raw)
        with pytest.raises(ValueError, match=why):
            reload(raw)

    bad(lambda r: r["intercept_seen"].update({"999": 1}), "intercept_seen")
    bad(lambda r: r["intercept_seen"].update({"0": 1}), "scout id")
    bad(lambda r: r["intercept_seen"].update({"-3": 1}), "scout id")
    bad(lambda r: r["intercept_seen"].update({str(scout.id): 10**9}), "intercept_seen")
    bad(lambda r: r.update(intercept_seen=[]), "intercept_seen must be a map")
    bad(lambda r: r["intercept_seen"].update({"x": 1}), "invalid literal")
    bad(lambda r: job(r).update(lost=10**9), "loses its scout")
    bad(lambda r: job(r).update(entity=None), "names an entity")
    bad(lambda r: job(r).update(pos=None), "at a position only")
    bad(lambda r: job(r).update(node="east-airbase"), "at a position only")
    bad(lambda r: job(r).update(key="intercept:9"), "does not name its kind and target")
    bad(
        lambda r: r["boards"]["COALITION"].append(
            dict(job(r), id=99, key="intercept:" + str(scout.id))
        ),
        "ENEMY|Static|ids",
    )
    bad(
        lambda r: next(j for j in r["boards"]["ENEMY"] if j["kind"] != "INTERCEPT").update(lost=1),
        "loses its scout",
    )
    raw = raw_of(w)
    raw["v"] = 22
    with pytest.raises(ValueError, match="unsupported snapshot format version 22"):
        reload(raw)
    raw = raw_of(w)
    del raw["intercept_seen"]
    with pytest.raises(ValueError):
        reload(raw)


# --- determinism ----------------------------------------------------------------------------------


def test_the_same_scene_replays_identically_and_a_restored_world_agrees() -> None:
    def hashes(restore_at: int | None = None) -> list[str]:
        w, _ = scene()
        put(w, "ENEMY_FIGHTER", "east-airbase", DIRECTOR)
        out = []
        for k in range(REACTION // EVERY + 6):
            w.campaign.tick = w.campaign.running_ticks  # what `raw_of` does, in every variant
            if k == restore_at:
                rules, w = w.rules, reload(raw_of(w))
                w.rules = rules
            board_pass(w)
            out.append(state_hash(w))
        assert len(posted(w)) == 1
        return out

    assert hashes() == hashes() == hashes(restore_at=8)


def test_events_of_the_scenario_are_the_same_every_time() -> None:
    def kinds_of() -> list[str]:
        w, _ = scene()
        put(w, "ENEMY_FIGHTER", "east-airbase", DIRECTOR)
        events: list[Event] = []
        for _ in range(REACTION // EVERY + 4):
            events += board_pass(w)
        return [e.kind for e in events]

    assert kinds_of() == kinds_of()
    assert "JobClaimed" in kinds_of()
