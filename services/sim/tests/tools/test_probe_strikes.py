"""NX-514 strike probe: why a launch's strike never fired (tools/balance/probe_strikes.py)."""

import sys
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import probe_strikes as ps  # type: ignore[import-not-found,unused-ignore]


def _unit(*weapons: str) -> dict[str, Any]:
    return {"hits": [(5, w, 2) for w in weapons], "damage": []}


def _launch(
    units: dict[str, Any] | None = None, *, tick: int = 100, shots: int = 0, other: int = 0,
    end: str | None = None, strike: bool = True,
) -> dict[str, Any]:  # fmt: skip
    jobs: list[dict[str, Any]] = [{"kind": "CAPTURE", "end": None, "units": {}}]
    if strike:
        jobs.append({"kind": "STRIKE", "end": (end, 50) if end else None, "units": units or {}})
    return {
        "tick": tick,
        "shots": [(1, 1, "AG_LIGHT")] * shots,
        "other_shots": [(1, 3, "AG_LIGHT")] * other,
        "jobs": jobs,
    }


def test_a_fired_launch_says_how_its_claimants_fared_and_its_strike_ended() -> None:
    both = {"1": _unit("SAM"), "2": _unit("SAM")}
    assert ps.classify(_launch(both, shots=2, end="expired"), 1000) == (
        "fired; all claimants SAM-hit; STRIKE expired"
    )
    assert ps.classify(_launch({"1": _unit()}, shots=1, end="done"), 1000) == (
        "fired; claimants unhit; STRIKE done"
    )


def test_a_shot_by_another_static_unit_still_counts_as_fired() -> None:
    assert ps.classify(_launch({"1": _unit()}, other=1), 1000) == (
        "fired; claimants unhit; STRIKE still open"
    )


def test_one_sam_hit_of_two_claimants_is_not_all() -> None:
    mixed = {"1": _unit("SAM"), "2": _unit()}
    assert ps.classify(_launch(mixed, end="expired"), 1000) == (
        "not fired; claimants hit, not all by a SAM; STRIKE expired"
    )
    gun = {"1": _unit("GUN"), "2": _unit("SAM")}
    assert "not all by a SAM" in ps.classify(_launch(gun, end="expired"), 1000)


def test_no_claimant_record_is_not_all_hit() -> None:
    assert ps.classify(_launch({}, end="expired"), 1000) == (
        "not fired; claimants unhit; STRIKE expired"
    )


def test_a_launch_without_a_strike_job_says_so() -> None:
    assert "no STRIKE job" in ps.classify(_launch(strike=False), 1000)


def test_only_a_launch_on_the_last_tick_had_no_time() -> None:
    assert "last tick" in ps.classify(_launch(tick=1000), 1000)
    assert "last tick" not in ps.classify(_launch({"1": _unit()}, tick=999), 1000)


def test_no_end_is_reported_as_open() -> None:
    assert ps.classify(_launch({"1": _unit()}), 1000) == (
        "not fired; claimants unhit; STRIKE still open at the run's end"
    )


def _ev(kind: str, **kw: Any) -> NS:
    return NS(kind=kind, **kw)


def test_the_tap_follows_a_launch_from_its_events() -> None:
    tap = ps.Tap()
    board = {
        10: NS(key="op:OFFENSIVE:west-airbase:0"),
        11: NS(key="op:OFFENSIVE:west-airbase:1"),
        12: NS(key="op:RECON:centre:0"),  # not a strike operation: ignored
    }

    def job(job_id: int, kind: str, side: str = "ENEMY", dep: int | None = None) -> NS:
        return _ev(
            "JobCreated", side=side, job_id=job_id, job_kind=kind, slots=2, tick=5,
            depends_on_job_id=dep,
        )  # fmt: skip

    created = [
        job(10, "STRIKE"), job(11, "CAPTURE", dep=10), job(12, "SCOUT"),
        job(13, "STRIKE", side="COALITION"),
    ]  # fmt: skip
    tap.feed([_ev("UnitSpawned", entity_id=1, side="ENEMY"), *created])
    tap.feed(
        [
            _ev("JobClaimed", job_id=10, entity_id=1, tick=5),
            _ev("WeaponImpact", target_id=1, hit=True, weapon="SAM", shooter_id=2, tick=6),
            _ev("WeaponImpact", target_id=1, hit=False, weapon="SAM", shooter_id=2, tick=7),
            _ev(
                "WeaponFired",
                shooter_id=1,
                target_node_id="west-airbase",
                weapon="AG_LIGHT",
                tick=8,
            ),
            _ev("WeaponFired", shooter_id=1, target_node_id=None, weapon="SAM", tick=8),
            _ev("UnitDestroyed", entity_id=1, tick=9),
            _ev("JobExpired", job_id=10, tick=10),
            _ev("NodeCaptured", tick=11, from_="NEUTRAL", to="ENEMY"),
        ]
    )
    tap.process(board)
    assert [launch["target"] for launch in tap.launches] == ["west-airbase"]
    launch = tap.launches[0]
    strike, capture = launch["jobs"]
    assert (strike["kind"], capture["kind"]) == ("STRIKE", "CAPTURE")
    assert strike["claims"] == [(5, 1)] and strike["end"] == ("expired", 10)
    assert strike["units"]["1"]["hits"] == [(6, "SAM", 2)]  # the miss is not a hit
    assert strike["units"]["1"]["lost"] == ("destroyed", 9)
    assert launch["shots"] == [(8, 1, "AG_LIGHT")] and launch["other_shots"] == []
    assert tap.flips == [(11, "NEUTRAL", "ENEMY")]
    assert ps.classify(launch, 1000) == "fired; all claimants SAM-hit; STRIKE expired"
