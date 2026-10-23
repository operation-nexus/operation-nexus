"""Soak tool tests (NX-033; tools/soak/soak.py). A few hundred ticks only."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "soak"))
import soak  # type: ignore[import-not-found,unused-ignore]


def test_slope_fits_a_line_after_the_warmup() -> None:
    pts = [(0.0, 900.0), (0.5, 500.0), (1.0, 100.0), (2.0, 120.0), (3.0, 140.0)]
    assert soak.slope_per_hour(pts, warmup_h=1.0) == pytest.approx(20.0)


def test_slope_is_missing_not_zero_when_it_cannot_be_fitted() -> None:
    assert soak.slope_per_hour([(1.0, 5.0), (2.0, 6.0)], warmup_h=0) is None
    assert soak.slope_per_hour([(1.0, 5.0)] * 4, warmup_h=0) is None
    assert soak.slope_per_hour([(0.0, 5.0)] * 5, warmup_h=1.0) is None


def test_worst_ticks_keep_the_slowest_n_and_build_context_lazily() -> None:
    stats = soak.StepStats(worst=3)
    built: list[int] = []

    def context(tick: int) -> dict[str, Any]:
        built.append(tick)
        return {"game_s": tick / 10}

    for tick, s in enumerate([0.001, 0.005, 0.002, 0.009, 0.003, 0.0005], start=1):
        stats.add(tick, s, lambda tick=tick: context(tick))
    assert [w["tick"] for w in stats.worst()] == [4, 2, 5]
    assert 6 not in built  # too fast to enter the list: no context built
    assert stats.max_s == 0.009 and stats.n == 6
    assert stats.percentile(0.5) == pytest.approx(0.002, rel=0.02)
    assert soak.StepStats(worst=3).percentile(0.5) is None


def run_info(**kw: Any) -> dict[str, Any]:
    return {"harness_error": None, "crash": None, "final_state_hash": "h"} | kw


def test_verdict_reasons() -> None:
    ok = {"mismatches": [], "checkpoints": 2}
    assert soak.verdict(run_info(), 1.0, 20.0, ok) == []
    assert soak.verdict(run_info(), None, 20.0, ok) == []  # a missing slope is reported, not failed
    assert "memory grows" in soak.verdict(run_info(), 30.0, 20.0, ok)[0]
    assert "mismatch" in soak.verdict(run_info(), 1.0, 20.0, {"mismatches": [600]})[0]
    assert "did not run" in soak.verdict(run_info(), 1.0, 20.0, None)[0]
    crash = run_info(crash={"tick": 5, "error": "E: x"})
    assert soak.verdict(crash, 1.0, 20.0, None) == ["sim crash at tick 5: E: x"]


def test_rss_is_a_number_or_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    value = soak.read_rss_mb()
    assert value is None or value > 0

    def gone(*_a: Any, **_k: Any) -> str:
        raise OSError

    monkeypatch.setattr(soak.Path, "read_text", gone)
    assert soak.read_rss_mb() is None


def test_end_to_end_smoke(tmp_path: Path) -> None:
    out = tmp_path / "soak"
    argv = ["--profile", "prime-50", "--hours", "0.04", "--checkpoint-ticks", "300"]
    argv += [
        "--worst",
        "5",
        "--mem-every-min",
        "0.5",
        "--warmup-h",
        "0",
        "--max-growth-mb-per-h",
        "1e9",
    ]
    argv += ["--out", str(out)]
    assert soak.main(argv) == 0
    doc = json.loads((out / "soak.json").read_text())
    assert doc["pass"] and doc["stopped_by"] == "game-time budget" and doc["ticks_run"] == 1440
    assert doc["replay"]["checkpoints"] == 5 and doc["replay"]["mismatches"] == []
    assert len(doc["worst_ticks"]) == 5
    assert "# Soak: PASS" in (out / "soak.md").read_text()
    assert soak.main(argv) == 2  # --out exists


def short_argv(out: Path, *extra: str) -> list[str]:
    return [
        *("--profile", "prime-50", "--hours", "0.02", "--checkpoint-ticks", "300"),
        *("--warmup-h", "0", "--max-growth-mb-per-h", "1e9", "--out", str(out), *extra),
    ]


def test_a_replay_that_differs_fails_and_lists_the_ticks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = soak.replay_checkpoints
    # replay another seed: the rebuilt world differs from the recorded run
    monkeypatch.setattr(soak, "replay_checkpoints", lambda log, seed, *a: real(log, seed + 1, *a))
    assert soak.main(short_argv(tmp_path / "o")) == 1
    doc = json.loads((tmp_path / "o" / "soak.json").read_text())
    assert not doc["pass"] and doc["replay"]["mismatches"]
    assert "replay hash mismatch" in doc["reasons"][0]
    assert "# Soak: FAIL" in (tmp_path / "o" / "soak.md").read_text()


def test_a_tiny_wall_budget_stops_the_run(tmp_path: Path) -> None:
    assert soak.main(short_argv(tmp_path / "o", "--minutes", "0.0001", "--hours", "5")) == 0
    doc = json.loads((tmp_path / "o" / "soak.json").read_text())
    assert doc["stopped_by"] == "wall-clock budget" and 0 < doc["ticks_run"] < 5 * 36_000


def test_a_missing_memory_slope_is_not_a_clean_pass(tmp_path: Path) -> None:
    # 720 ticks with a 5-minute RSS interval: no sample, so no slope
    assert soak.main(short_argv(tmp_path / "o")) == 0
    doc = json.loads((tmp_path / "o" / "soak.json").read_text())
    assert doc["pass"] and doc["memory"]["gate_applied"] is False
    text = (tmp_path / "o" / "soak.md").read_text()
    assert "# Soak: PASS (memory not measured)" in text
    assert "memory gate NOT applied" in text
    doc["memory"]["gate_applied"] = True
    assert "# Soak: PASS\n" in soak.markdown(doc)


def test_a_crash_is_reported_as_the_stop_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = soak.runner.step

    def flaky(world: Any, cmds: Any, handlers: Any) -> Any:
        if world.campaign.tick == 50:
            raise ValueError("boom")
        return real(world, cmds, handlers)

    monkeypatch.setattr(soak.runner, "step", flaky)
    assert soak.main(short_argv(tmp_path / "o")) == 1
    doc = json.loads((tmp_path / "o" / "soak.json").read_text())
    assert doc["stopped_by"] == "crash: ValueError" and doc["replay"] is None
