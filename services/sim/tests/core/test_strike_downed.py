"""NX-431 (Q-TD-56): "NULL strike package downed near <node>", crediting the viewer units that
broke it, on the tick a viewer takes out its last jet (THREAT-DIRECTOR §4a FS-9, FOW-13).

Shipped strait-1 config, campaign layer off, no opening garrison. A STRIKE job on the Static's
board at west-airbase (pos 90,000 / 120,000: sector centre), claimed by two Director strike jets;
hits are applied with `combat._hit` (the real damage path, no hit roll). ENEMY_STRIKE_FIGHTER has
100 hp, Mission-kill below 35, Disabled below 10 (COMBAT thresholds 0.70 / 0.35 / 0.10).
"""

import dataclasses
from typing import Any

import msgpack
import pytest
from test_join import CAMPAIGN_ID, cid

from nexus.contracts.gen.common.enums import OwnerKind, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import tasking
from nexus.core.combat import _hit
from nexus.core.rules import CombatRules, Rules, WeaponRules
from nexus.core.tasking import post_job, take
from nexus.core.tasking_gen import JobSpec
from nexus.core.world import Entity, Job, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import start_campaign
from nexus.runtime.golden import shipped_config

_C = shipped_config({})
CONFIG = dataclasses.replace(
    _C, rules=dataclasses.replace(_C.rules, campaign=None, garrison_quota={})
)
RULES: Rules = CONFIG.rules
assert RULES.combat is not None and RULES.tasking is not None
COMBAT: CombatRules = RULES.combat
GUN: WeaponRules = COMBAT.weapons["SAM"]  # 70 damage: 100 -> 30 (Mission-kill), then destroyed
KILL = dataclasses.replace(GUN, damage=1000)
WRECK = dataclasses.replace(GUN, damage=95)  # 100 -> 5: Disabled
TARGET = "west-airbase"


def world() -> World:
    return start_campaign(CAMPAIGN_ID, 1, CONFIG)


def unit(w: World, kind: UnitKind, side: Side, owner: OwnerKind, cmd: int | None = None) -> Entity:
    pos = Vec2(*RULES.roads.pos[TARGET])
    return w.spawn(kind, side, owner, pos, commander_id=None if cmd is None else cid(cmd))


def package(
    w: World, side: Side = "ENEMY", kind: str = "STRIKE", jets: int = 2
) -> tuple[Job, list[Entity]]:
    """A job of `kind` at west-airbase on `side`'s board with `jets` jets holding it."""
    out: list[Event] = []
    spec = JobSpec(kind, f"op:OFFENSIVE:{TARGET}:1", 2, 1000, node=TARGET)  # type: ignore[arg-type]
    job = post_job(w, side, spec, out)
    owner, jet = ("ENEMY_DIRECTOR", "ENEMY_STRIKE_FIGHTER") if side == "ENEMY" else (
        "AI_GARRISON", "STRIKE_FIGHTER",
    )  # fmt: skip
    units = [unit(w, jet, side, owner) for _ in range(jets)]  # type: ignore[arg-type]
    for j in units:
        take(w, j, job, out)
    return job, units


def viewer(w: World, n: int) -> Entity:
    return unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", cmd=n)


def downed(out: list[Event]) -> list[tuple[str, str, str | None, list[int]]]:
    return [
        (e.sector_id, e.direction, e.node_id, e.credit_ids)
        for e in out
        if e.kind == "ThreatAdaptation" and e.category == "STRIKE_DOWNED"
    ]


def expire(w: World, job: Job) -> list[Event]:
    """The board pass at the job's expiry: claims of lost or homebound units are released and
    the unclaimed job expires (`tasking._settle`)."""
    assert job.expires is not None and RULES.tasking is not None
    w.campaign.running_ticks = job.expires
    out: list[Event] = []
    tasking._settle(w, RULES, RULES.tasking, "ENEMY", job.expires, tasking.Routes(), out)
    assert job.id not in w.boards["ENEMY"]
    return out


def test_the_hit_on_the_last_jet_announces_the_package_at_once_crediting_every_viewer() -> None:
    w = world()
    job, (a, b) = package(w)
    v1, v2 = viewer(w, 1), viewer(w, 2)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v2, a, KILL, out)  # destroyed; b still flies
    assert job.downed_by == [v2.id] and downed(out) == []
    _hit(w, RULES, COMBAT, v1, b, GUN, out)  # 100 -> 30: Mission-kill, the last one out
    assert b.damage_state == "MISSION_KILL" and w.find(a.id) is None
    # FOW-13: the sector and the struck node (public, FOW-10); no position, no unit of the Static
    assert downed(out) == [("centre", "UP", TARGET, sorted([v1.id, v2.id]))]
    assert out[-1].kind == "ThreatAdaptation" and job.downed
    assert downed(expire(w, job)) == []  # once per job: nothing more when it expires


def test_a_package_with_a_survivor_that_leaves_says_nothing() -> None:
    w = world()
    job, (a, b) = package(w)
    v = viewer(w, 1)
    _hit(w, RULES, COMBAT, v, a, KILL, [])
    b.state = "RTB"  # the survivor turns home (fuel, rounds), not shot down
    assert job.downed_by == [v.id]
    assert downed(expire(w, job)) == []


def test_a_strike_that_succeeds_says_nothing() -> None:
    w = world()
    job, (a, _) = package(w)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, viewer(w, 1), a, KILL, out)
    tasking._end(w, "ENEMY", job, "DONE", out)
    assert job.downed_by and downed(out) == []


def test_a_viewer_who_downs_both_jets_is_credited_once() -> None:
    w = world()
    job, (a, b) = package(w)
    v = viewer(w, 1)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v, a, GUN, out)  # Mission-kill
    _hit(w, RULES, COMBAT, v, a, GUN, out)  # then destroyed
    _hit(w, RULES, COMBAT, v, b, KILL, out)
    assert job.downed_by == [v.id]
    assert downed(out) == [("centre", "UP", TARGET, [v.id])]


def test_a_mission_killed_jet_still_on_the_job_is_out_of_the_fight() -> None:
    w = world()
    job, (a, b) = package(w)
    v = viewer(w, 1)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v, a, GUN, out)  # Mission-kill: alive, turning home, claim not released
    assert a.damage_state == "MISSION_KILL" and a.id in job.claims and downed(out) == []
    _hit(w, RULES, COMBAT, v, b, KILL, out)
    assert downed(out) == [("centre", "UP", TARGET, [v.id])]


def test_a_landed_jet_disabled_by_a_viewer_is_credited() -> None:
    # a non-airborne Disabled is a wreck, not a destruction: the credit comes from that hit
    w = world()
    job, (a, b) = package(w)
    a.state = "LANDED"
    v = viewer(w, 1)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v, a, WRECK, out)
    assert a.damage_state == "DISABLED" and w.find(a.id) is a
    assert job.downed_by == [v.id] and downed(out) == []  # b still flies
    _hit(w, RULES, COMBAT, v, b, KILL, out)
    assert downed(out) == [("centre", "UP", TARGET, [v.id])]


def test_ai_kills_and_light_hits_credit_nobody_and_say_nothing() -> None:
    w = world()
    job, (a, b) = package(w)
    ai = unit(w, "STRIKE_FIGHTER", "COALITION", "AI_GARRISON")  # DI-5: an AI is no viewer
    v = viewer(w, 1)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v, a, dataclasses.replace(GUN, damage=40), out)  # 60: only Damaged
    assert a.damage_state == "DAMAGED" and job.downed_by == []
    _hit(w, RULES, COMBAT, ai, a, KILL, out)
    _hit(w, RULES, COMBAT, ai, b, KILL, out)  # the last jet, but by an AI: no viewer win
    assert job.downed_by == [] and downed(out) == []


def test_a_viewer_downing_the_last_jet_after_an_ai_got_the_first_announces_it() -> None:
    w = world()
    _, (a, b) = package(w)
    ai = unit(w, "STRIKE_FIGHTER", "COALITION", "AI_GARRISON")
    v = viewer(w, 1)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, ai, a, KILL, out)
    _hit(w, RULES, COMBAT, v, b, KILL, out)
    assert downed(out) == [("centre", "UP", TARGET, [v.id])]  # the AI is not credited


def test_a_new_claimant_downed_later_does_not_announce_again() -> None:
    w = world()
    job, (a,) = package(w, jets=1)
    v1, v2 = viewer(w, 1), viewer(w, 2)
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v1, a, KILL, out)
    assert len(downed(out)) == 1
    late = unit(w, "ENEMY_STRIKE_FIGHTER", "ENEMY", "ENEMY_DIRECTOR")
    take(w, late, job, out)  # the board puts a fresh jet on the job
    _hit(w, RULES, COMBAT, v2, late, KILL, out)
    assert len(downed(out)) == 1 and job.downed_by == sorted([v1.id, v2.id])


def test_only_strike_jobs_of_the_static_count() -> None:
    w = world()
    capture, (a, _) = package(w, kind="CAPTURE")  # a capture column is no strike package
    _hit(w, RULES, COMBAT, viewer(w, 1), a, KILL, [])
    assert capture.downed_by == []
    own, (c,) = package(w, side="COALITION", jets=1)  # "NULL strike package": never the coalition
    out: list[Event] = []
    _hit(w, RULES, COMBAT, viewer(w, 2), c, KILL, out)
    assert own.downed_by == [] and downed(out) == []


def test_credit_is_capped_at_the_32_lowest_ids() -> None:
    w = world()
    job, (a,) = package(w, jets=1)
    v = viewer(w, 1)
    job.downed_by = list(range(v.id + 1, v.id + 41))
    out: list[Event] = []
    _hit(w, RULES, COMBAT, v, a, KILL, out)
    ((_, _, _, credit),) = downed(out)
    assert credit == list(range(v.id, v.id + 32))  # ThreatAdaptation.credit_ids maxItems 32


def test_the_credit_survives_save_and_load_and_the_run_is_deterministic() -> None:
    def once() -> tuple[str, list[dict[str, object]]]:
        w = world()
        job, (a, b) = package(w)
        _hit(w, RULES, COMBAT, viewer(w, 1), a, KILL, [])
        w.campaign.tick += 1  # the job was posted for the next tick
        w.campaign.running_ticks += 1
        copy = load(save(w))
        copy.rules = w.rules
        assert state_hash(copy) == state_hash(w)
        got = copy.boards["ENEMY"][job.id]
        assert (got.downed_by, got.downed) == (job.downed_by, False)
        out: list[Event] = []
        _hit(copy, RULES, COMBAT, viewer(copy, 2), copy.find(b.id), KILL, out)  # type: ignore[arg-type]
        assert got.downed
        return state_hash(copy), [e.model_dump() for e in out]

    first = once()
    assert first == once()
    assert any(e.get("category") == "STRIKE_DOWNED" for e in first[1])


def corrupt(entry: dict[str, Any], change: dict[str, Any], side: str = "ENEMY") -> None:
    w = world()
    job, _ = package(w)
    w.campaign.tick += 1
    w.campaign.running_ticks += 1
    raw = msgpack.unpackb(save(w), raw=False, strict_map_key=False)
    if side != "ENEMY":  # move the job to the coalition's board
        raw["boards"][side] = raw["boards"]["ENEMY"]
        raw["boards"]["ENEMY"] = []
    found = next(j for j in raw["boards"][side] if j["id"] == job.id)
    found.update(entry, **change)
    with pytest.raises(ValueError, match="downed"):
        load(msgpack.packb(raw, use_bin_type=True))


@pytest.mark.parametrize(
    "change",
    [
        {"downed_by": [3, 2]},
        {"downed_by": [2, 2]},
        {"downed_by": [10**6]},
        {"downed_by": [0]},  # entity ids start at 1
        {"downed_by": [2], "kind": "CAPTURE"},  # credit only on a STRIKE job
        {"downed": True},  # announced without credit
    ],
)
def test_a_corrupt_downed_by_is_refused(change: dict[str, Any]) -> None:
    corrupt({}, change)


def test_credit_on_the_coalitions_board_is_refused() -> None:
    corrupt({}, {"downed_by": [2]}, side="COALITION")
