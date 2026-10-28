"""NX-463 (Q-TD-87): a STRIKE claimant that fired at its job's target while holding the claim is
a participant even after RTB released the claim, so a strike whose jets spent their bombs and
turned home ends DONE crediting them, not EXPIRED (`Job.struck_by`, `combat._record_strike`,
`tasking._participants`). Both boards alike (ECONOMY EC-3).

Shipped strait-1 via `test_tasking` (campaign off, no opening garrison). Shots go through the
real `combat._shoot`; the RTB turn is the state `go_home` sets (as in `test_strike_downed`); the
board pass is `tasking._settle`, the one that releases RTB claims and then decides the outcome.
"""

from typing import Any

import msgpack
import pytest
from test_tasking import HUMAN, RULES, TR, new_world, post, put

from nexus.contracts.gen.common.enums import JobKind, OwnerKind, Side, UnitKind
from nexus.contracts.gen.events.event import Event
from nexus.core import tasking
from nexus.core.combat import _shoot
from nexus.core.world import Entity, Job, Vec2, World, load, release_claim, save, state_hash

# A foe node per board with its own air-defense site (`base_id`), and a second foe node.
TARGET: dict[Side, str] = {"COALITION": "fob-n-e", "ENEMY": "fob-n-w"}
OTHER: dict[Side, str] = {"COALITION": "east-airbase", "ENEMY": "west-airbase"}
HOME: dict[Side, str] = {"COALITION": "west-airbase", "ENEMY": "static-hq"}
assert RULES.combat is not None
AG = 0  # loadout index of AG_LIGHT on STRIKE_FIGHTER and ENEMY_STRIKE_FIGHTER (STRUCTURE weapon)


def strike(side: Side, jets: int = 1) -> tuple[World, Job, list[Entity]]:
    """`side`'s STRIKE job on its foe node, taken by `jets` jets that are flying (ACTIVE)."""
    w = new_world()
    kind, owner = ("STRIKE_FIGHTER", HUMAN) if side == "COALITION" else (
        "ENEMY_STRIKE_FIGHTER", "ENEMY_DIRECTOR",
    )  # fmt: skip
    job = post(w, side, "STRIKE", TARGET[side], f"strike-{side}", slots=4)
    units = [put(w, kind, HOME[side], owner) for _ in range(jets)]  # type: ignore[arg-type]
    for jet in units:
        tasking.take(w, jet, job, [])
    settle(w, side)  # flying: every claim ACTIVE
    assert all(c.active for c in job.claims.values()) and len(job.claims) == jets
    return w, job, units


def site(w: World, node: str) -> Entity:
    (s,) = [e for e in w.entities() if e.base_id == node and e.kind == "AIR_DEFENSE_SITE"]
    return s


def fire(w: World, jet: Entity, target: Entity | str) -> None:
    assert RULES.combat is not None
    weapon = RULES.combat.loadout(jet.kind, jet.variant)[AG]
    _shoot(w, RULES, jet, AG, weapon, (target, 1.0), w.campaign.running_ticks, [])


def settle(w: World, side: Side) -> list[Event]:
    out: list[Event] = []
    now = w.campaign.running_ticks
    tasking._settle(w, RULES, TR, side, now, tasking.Routes(), out)
    return out


def rtb_then_met(w: World, side: Side, jets: list[Entity]) -> list[Event]:
    """The jets turn home (their claims go at the next pass), the node is at 0 hp (the verdict
    is DONE), and the pass runs."""
    for jet in jets:
        jet.state = "RTB"
    w.defense_hp[TARGET[side]] = 0
    return settle(w, side)


def ended(out: list[Event], job: Job) -> list[tuple[str, list[int]]]:
    return [
        (e.kind, [p.entity_id for p in getattr(e, "participants", [])])
        for e in out
        if e.kind in ("JobDone", "JobExpired", "JobFailed") and e.job_id == job.id
    ]


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])  # EC-3: both boards
@pytest.mark.parametrize("at", ["node", "site"])  # the node's defenses, or its facility
def test_a_claimant_that_fired_at_the_target_and_went_rtb_is_credited(side: Side, at: str) -> None:
    w, job, (jet,) = strike(side)
    fire(w, jet, TARGET[side] if at == "node" else site(w, TARGET[side]))
    assert job.struck_by == [jet.id]
    out = rtb_then_met(w, side, [jet])
    assert ended(out, job) == [("JobDone", [jet.id])]
    (done,) = [e for e in out if e.kind == "JobDone"]
    assert done.participants[0].commander_id == jet.commander_id  # same fields as before
    assert done.participants[0].auto is False


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])
def test_a_claimant_that_went_rtb_without_firing_is_not_credited(side: Side) -> None:
    w, job, (jet,) = strike(side)
    out = rtb_then_met(w, side, [jet])
    assert ended(out, job) == [("JobExpired", [])]  # nobody to credit, as before


def test_only_the_jets_that_fired_are_credited_beside_the_active_claimants() -> None:
    w, job, (a, b, c) = strike("COALITION", jets=3)
    fire(w, c, TARGET["COALITION"])
    a.state = c.state = "RTB"  # a never fired; b is still on the job (ACTIVE)
    w.defense_hp[TARGET["COALITION"]] = 0
    out = settle(w, "COALITION")
    assert ended(out, job) == [("JobDone", [b.id, c.id])]  # ascending ids


@pytest.mark.parametrize("side", ["COALITION", "ENEMY"])
@pytest.mark.parametrize("at", ["node", "site"])
def test_a_released_claimant_that_fired_at_another_target_is_not_credited(
    side: Side, at: str
) -> None:
    w, job, (jet,) = strike(side)
    fire(w, jet, OTHER[side] if at == "node" else site(w, OTHER[side]))
    assert job.struck_by == []
    out = rtb_then_met(w, side, [jet])
    assert ended(out, job) == [("JobExpired", [])]


@pytest.mark.parametrize(
    ("side", "kind", "unit"),
    [
        ("ENEMY", "CAPTURE", "ENEMY_ARMOR"),  # a Static capture run: AG_CANNON at the node's site
        ("COALITION", "SCOUT", "STRIKE_FIGHTER"),
    ],
)
def test_a_claimant_of_another_job_kind_firing_at_its_nodes_site_is_not_recorded(
    side: Side, kind: JobKind, unit: UnitKind
) -> None:
    w = new_world()
    job = post(w, side, kind, TARGET[side], f"{kind}-{side}")
    owner: OwnerKind = HUMAN if side == "COALITION" else "ENEMY_DIRECTOR"
    e = w.spawn(unit, side, owner, Vec2(*RULES.roads.pos[TARGET[side]]))
    tasking.claim(w, e, job, [])
    assert RULES.combat is not None
    loadout = RULES.combat.loadout(e.kind, e.variant)
    i = next(n for n, wpn in enumerate(loadout) if "STATIC" in wpn.targets)
    _shoot(w, RULES, e, i, loadout[i], (site(w, TARGET[side]), 1.0), w.campaign.running_ticks, [])
    assert e.job_id == job.id and e.id in job.claims and job.struck_by == []


def test_a_shot_without_the_claim_is_not_recorded() -> None:
    w, job, (jet,) = strike("COALITION")
    release_claim(w, job, jet.id, [])  # still pointed at the job, but no claim held
    jet.job_id = job.id
    fire(w, jet, TARGET["COALITION"])
    assert job.struck_by == []


def test_struck_by_survives_save_and_load_and_the_run_is_deterministic() -> None:
    def once() -> tuple[str, list[dict[str, Any]]]:
        w, job, (a, b) = strike("ENEMY", jets=2)
        fire(w, b, site(w, TARGET["ENEMY"]))
        fire(w, a, TARGET["ENEMY"])
        fire(w, b, TARGET["ENEMY"])  # once each
        assert job.struck_by == [a.id, b.id]
        w.campaign.tick += 1  # the job was posted for the next tick
        w.campaign.running_ticks += 1
        copy = load(save(w))
        copy.rules = w.rules
        assert state_hash(copy) == state_hash(w)
        assert copy.boards["ENEMY"][job.id].struck_by == [a.id, b.id]
        out = rtb_then_met(copy, "ENEMY", [copy.find(a.id), copy.find(b.id)])  # type: ignore[list-item]
        assert ended(out, job) == [("JobDone", [a.id, b.id])]
        return state_hash(copy), [e.model_dump() for e in out]

    first = once()
    assert first == once()


@pytest.mark.parametrize(
    "change",
    [
        {"struck_by": [12, 11]},
        {"struck_by": [11, 11]},
        {"struck_by": [10**6]},
        {"struck_by": [0]},  # entity ids start at 1
        {"struck_by": [11], "kind": "CAPTURE"},  # only on a STRIKE job
    ],
)
def test_a_corrupt_struck_by_is_refused(change: dict[str, Any]) -> None:
    w, job, _ = strike("ENEMY", jets=2)
    raw = msgpack.unpackb(save(w), raw=False, strict_map_key=False)
    found = next(j for j in raw["boards"]["ENEMY"] if j["id"] == job.id)
    found.update(change)
    with pytest.raises(ValueError, match="struck_by"):
        load(msgpack.packb(raw, use_bin_type=True))
