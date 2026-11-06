"""NX-511 (GAMEPLAY §1b item 253): the same-sha A/B compare of two harness reports."""

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import compare  # type: ignore[import-not-found,unused-ignore]

SHA = "a" * 40
SUM = {"flights": 0, "spawned": 0}


def _profile(name: str, downs: int | None = 0, length: float | None = 10.0) -> dict[str, Any]:
    return {
        **{t: {"status": "pass"} for t in compare.TARGETS},
        "A1": {
            "status": "pass",
            "median_length_h": length,
            "low_crowd": name in ("quiet-5", "solo-1"),
            "seeds": [{"seed": s, "good": True} for s in (1, 2, 3)],
        },
        "per_seed": [{"seed": s, "static_defenses_down": downs} for s in (1, 2, 3)],
        "wingmen": {"sum": SUM, "not_measured": 0},
    }


NAMES = ("overnight-0", "quiet-5", "solo-1", "raid-300", "surge-500")


def _report(overrides: list[str]) -> dict[str, Any]:
    return {
        "config": {
            "sha": SHA,
            "profiles_digest": "d",
            "overrides": overrides,
        },
        "seeds": [1, 2, 3],
        "hours": 6.0,
        "profiles": {n: _profile(n, 12 if overrides else 6) for n in NAMES},
        "runs": [
            {"profile": "overnight-0", "seed": s, "final_state_hash": f"h{s}", "ticks_run": 9}
            for s in (1, 2, 3)
        ],
    }


def _pair() -> tuple[dict[str, Any], dict[str, Any]]:
    return _report([]), _report(["tasking.wingmen_max=2"])


def _by_name(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {v.name.split()[0]: v for v in compare.verdicts(a, b)}


def _solo(a_downs: int, b_downs: int) -> str:
    a, b = _pair()
    a["profiles"]["solo-1"] = _profile("solo-1", a_downs)
    b["profiles"]["solo-1"] = _profile("solo-1", b_downs)
    return str(_by_name(a, b)["solo-1"].status)


def test_solo_needs_at_least_double_in_the_median_seed() -> None:
    assert _solo(6, 12) == compare.PASS  # exactly 2x passes: "at least doubles"
    assert _solo(6, 11) == compare.FAIL
    assert _solo(0, 1) == compare.PASS  # from nothing to something
    assert _solo(0, 0) == compare.FAIL


def test_solo_uses_the_median_seed_and_per_hour_over_the_run_hours() -> None:
    a, b = _pair()
    for r, counts in ((a, (1, 2, 3)), (b, (1, 4, 100))):
        r["profiles"]["solo-1"]["per_seed"] = [
            {"seed": i, "static_defenses_down": n} for i, n in enumerate(counts, 1)
        ]
    v = _by_name(a, b)["solo-1"]
    assert v.status == compare.PASS and v.proposed
    assert "A 0.33/h, B 0.67/h" in v.detail  # medians 2 and 4 over 6 h


def test_solo_is_not_measured_without_the_count_or_the_profile() -> None:
    a, b = _pair()
    b["profiles"]["solo-1"]["per_seed"][0].pop("static_defenses_down")
    assert _by_name(a, b)["solo-1"].status == compare.NOT_MEASURED
    a, b = _pair()
    del a["profiles"]["solo-1"], b["profiles"]["solo-1"]
    assert _by_name(a, b)["solo-1"].status == compare.NOT_MEASURED


def test_quiet5_holds_is_partial_at_best_and_fails_on_a_collapse() -> None:
    a, b = _pair()
    assert _by_name(a, b)["quiet-5"].status == compare.PARTIAL
    b["profiles"]["quiet-5"]["A1"]["seeds"][1]["good"] = False
    v = _by_name(a, b)["quiet-5"]
    assert v.status == compare.FAIL and "[2]" in v.detail


def test_overnight_state_hashes_must_match_per_seed() -> None:
    a, b = _pair()
    assert _by_name(a, b)["overnight-0"].status == compare.PASS
    b["runs"][2]["final_state_hash"] = "other"
    v = _by_name(a, b)["overnight-0"]
    assert v.status == compare.FAIL and "[3]" in v.detail
    a, b = _pair()
    a["runs"][0]["final_state_hash"] = b["runs"][0]["final_state_hash"] = None  # crashed run
    assert _by_name(a, b)["overnight-0"].status == compare.FAIL


@pytest.mark.parametrize("profile", compare.CROWDS)
def test_crowd_verdicts_must_not_change(profile: str) -> None:
    a, b = _pair()
    assert _by_name(a, b)[profile].status == compare.PASS
    b["profiles"][profile]["A3"]["status"] = "fail"
    v = _by_name(a, b)[profile]
    assert v.status == compare.FAIL and "A3" in v.detail and v.proposed


def _shift(length_b: float) -> str:
    a, b = _pair()
    b["profiles"]["raid-300"]["A1"]["median_length_h"] = length_b
    return str(_by_name(a, b)["raid-300"].status)


def test_median_length_must_move_under_ten_percent() -> None:
    assert _shift(10.9) == compare.PASS
    assert _shift(10.0) == compare.PASS
    assert _shift(11.0) == compare.FAIL  # exactly 10 %: "under 10 %" fails
    assert _shift(9.0) == compare.FAIL
    assert _shift(9.1) == compare.PASS


def test_length_is_not_measured_without_a_length() -> None:
    a, b = _pair()
    a["profiles"]["raid-300"]["A1"]["median_length_h"] = None
    assert _by_name(a, b)["raid-300"].status == compare.NOT_MEASURED


def test_thresholds_are_the_specs() -> None:
    assert (compare.SOLO_MIN_RATIO, compare.LENGTH_SHIFT_MAX) == (2.0, 0.10)


def _refused(mutate: Any) -> str:
    a, b = _pair()
    mutate(a, b)
    with pytest.raises(ValueError) as e:
        compare.verdicts(a, b)
    return str(e.value)


def test_it_refuses_reports_that_are_not_one_pair() -> None:
    assert "different shas" in _refused(lambda a, b: b["config"].update(sha="b" * 40))
    assert "no sha" in _refused(lambda a, b: a["config"].update(sha=None))
    assert "dirty" in _refused(lambda a, b: a["config"].update(sha=SHA + "-dirty"))
    assert "profile sets" in _refused(lambda a, b: b["profiles"].pop("solo-1"))
    assert "digests" in _refused(lambda a, b: b["config"].update(profiles_digest="x"))
    assert "seeds or hours" in _refused(lambda a, b: b.update(seeds=[1, 2]))
    assert "seeds or hours" in _refused(lambda a, b: b.update(hours=7.0))
    assert "same overrides" in _refused(lambda a, b: b["config"].update(overrides=[]))


def test_main_exit_codes_and_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a, b = _pair()
    paths = []
    for name, r in (("a", a), ("b", b)):
        paths.append(str(tmp_path / f"{name}.json"))
        Path(paths[-1]).write_text(json.dumps(r))
    assert compare.main(paths) == 0
    out = capsys.readouterr().out
    assert "PROPOSED threshold" in out and "AI wingmen counters" in out and SHA in out
    bad = copy.deepcopy(b)
    bad["profiles"]["surge-500"]["A2"]["status"] = "fail"
    Path(paths[1]).write_text(json.dumps(bad))
    assert compare.main(paths) == 1
    assert compare.main(paths[:1]) == 2
    Path(paths[1]).write_text("{}")
    assert compare.main(paths) == 2
