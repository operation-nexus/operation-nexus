"""NX-519 A2 probe: where a newbie's time to first impact goes (tools/balance/probe_a2.py)."""

import dataclasses
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import probe_a2 as pa  # type: ignore[import-not-found,unused-ignore]
import profiles  # type: ignore[import-not-found,unused-ignore]


def _n(
    ttfi: float | None, watched: float, phases: dict[str, float], *, losses: int = 0
) -> dict[str, Any]:
    return {
        "ttfi_s": ttfi, "watched_s": watched, "phases": phases, "states": {}, "timeline": [],
        "losses": [
            {"unit": "U", "killer": "K", "cause": "C", "last_state": "transit:STRIKE"}
        ] * losses,
        "gave_up_after_s": None,
    }  # fmt: skip


def test_the_tail_rule_is_the_reports_rule() -> None:
    assert pa.is_tail(_n(901, 901, {})) and not pa.is_tail(_n(900, 900, {}))  # 900 is not later
    assert pa.is_tail(_n(None, 901, {})) and pa.judged(_n(None, 901, {}))
    assert not pa.judged(_n(None, 900, {}))  # watched 900 s or less with none: unresolved


def test_phase_of_is_the_state_prefix() -> None:
    assert pa.phase_of("idle:full") == "idle"
    assert pa.phase_of("on_task:STRIKE:at_target:fired") == "on_task"
    assert pa.phase_of("gave_up:left") == "gave_up"


def test_phase_table_shares_cover_the_tails_time() -> None:
    quick = _n(100, 100, {"transit": 100.0})
    slow = _n(1000, 1000, {"idle": 600.0, "transit": 400.0})
    gone = _n(None, 2000, {"transit": 200.0, "gave_up": 1800.0})
    t = pa.phase_table([quick, slow, gone])
    assert (t["newbies"], t["tail"]) == (3, 2)
    shares = {p: v["tail_time_share"] for p, v in t["phases"].items()}
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["gave_up"] == pytest.approx(1800 / 3000)
    assert t["phases"]["idle"]["tail_dominant"] == 1
    assert t["phases"]["gave_up"]["tail_dominant"] == 1
    assert t["phases"]["transit"]["median_s"] == 200.0  # over all three newbies, zeros included


def test_the_first_window_cuts_the_timeline_at_900_s_or_the_time_watched() -> None:
    line = [[0.0, "idle:full"], [300.0, "transit:order_GOTO"], [1200.0, "gave_up:left"]]
    n = {"watched_s": 5000.0, "timeline": line}
    assert pa.first_window(n) == {"idle": 300.0, "transit": 600.0}
    assert pa.first_window({**n, "watched_s": 400.0}) == {"idle": 300.0, "transit": 100.0}


def test_a_table_with_no_tail_has_no_shares() -> None:
    t = pa.phase_table([_n(10, 10, {"transit": 10.0})])
    assert t["tail"] == 0 and t["phases"]["idle"]["tail_time_share"] is None


def test_loss_table_counts_units_lost_before_the_impact() -> None:
    assert pa.loss_table([_n(5, 5, {}, losses=2), _n(5, 5, {})]) == {
        "U by K on ? (C) in transit": 2
    }


def test_a_run_books_every_second_of_a_newbies_wait_into_a_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The phases sum to the newbie's time to first impact (or its time watched), the impact times
    are the collector's, and the report's A2 reads them the same."""
    full = profiles.load()
    crowd = dataclasses.replace(full.profiles["prime-50"], viewers=40, ramp_min=1)
    every = dataclasses.replace(full.targets, a2_min_tier="PATTERN_OF_LIFE")  # count them all
    data = dataclasses.replace(full, profiles={**full.profiles, "prime-50": crowd}, targets=every)
    monkeypatch.setattr(profiles, "load", lambda *a, **k: data)
    run = pa.run_one("prime-50", 1, 0.2, sample_s=5.0)
    assert not run["crash"] and run["newbies"]
    for n in run["newbies"]:
        total = sum(n["phases"].values())
        assert total == pytest.approx(n["ttfi_s"] if n["ttfi_s"] is not None else n["watched_s"])
        assert set(n["phases"]) <= set(pa.PHASES)
    impacted = sorted(n["ttfi_s"] for n in run["newbies"] if n["ttfi_s"] is not None)
    assert impacted == run["metrics"]["newbie"]["ttfi_s"]
