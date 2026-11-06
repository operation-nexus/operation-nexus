"""Real-kernel scaling bench smoke tests (NX-376; tools/sim-bench/kernel_bench.py)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "sim-bench"))
import kernel_bench  # type: ignore[import-not-found,unused-ignore]


@pytest.mark.parametrize("scene", ["convoy", "mixed"])
@pytest.mark.parametrize("n", [50, 150, 333])
def test_the_scene_has_exactly_the_requested_entities(scene: str, n: int) -> None:
    assert len(kernel_bench.build_scene(scene, n, 1)) == n


def test_the_same_seed_builds_the_same_scene() -> None:
    def layout(seed: int) -> list[tuple[str, float, float]]:
        w = kernel_bench.build_scene("mixed", 100, seed)
        return [(e.kind, e.pos.x, e.pos.y) for e in w.entities()]

    assert layout(5) == layout(5)
    assert layout(5) != layout(6)


def test_the_bench_reports_the_ladder_and_its_exponent(tmp_path: Path) -> None:
    out = tmp_path / "k.json"
    res: Any = kernel_bench.main(
        ["--ladder", "100,50", "--ticks", "100", "--scene", "mixed", "--out", str(out)]
    )
    assert json.loads(out.read_text())["scene"] == "mixed"
    assert [r["entities"] for r in res["rungs"]] == [50, 100]
    assert res["frame_build_counted"] is False
    assert {"platform", "cpu", "cpus", "python"} <= res["host"].keys()
    for r in res["rungs"]:
        assert r["ticks"] == r["board_pass_ticks"] + r["plain_ticks"] == 100
        assert r["ticks_per_s"] > 0 and r["viewer_units"] > 0
        assert 0 < r["step_ms"]["p50"] <= r["step_ms"]["p99"] <= r["step_ms"]["max"]
        assert r["largest_tick"]["ms"] == r["step_ms"]["max"]
    assert isinstance(res["scaling_exponent"], float)


def test_the_exponent_of_a_known_power_law() -> None:
    rungs = [{"entities": n, "step_ms": {"mean": n**1.5}} for n in (100, 200, 400, 1000)]
    assert kernel_bench.exponent(rungs) == pytest.approx(1.5, abs=1e-9)
    assert kernel_bench.exponent(rungs[:1]) is None


def test_the_percentile_helper_on_a_small_list() -> None:
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert kernel_bench.pct(xs, 50) == 3.0
    assert kernel_bench.pct(xs, 99) == pytest.approx(4.96)
    assert kernel_bench.pct([7.0], 99) == 7.0


def test_board_ticks_are_every_reeval_period() -> None:
    assert [t for t in range(120) if kernel_bench.is_board_tick(t, 50)] == [49, 99]
    assert not kernel_bench.is_board_tick(0, 50)


def test_the_convoy_scene_steps_and_reports_the_first_board_pass() -> None:
    res = kernel_bench.run_rung("convoy", 150, 20, 1, settle=60)
    assert res["entities"] == 150 and res["ticks"] == 20
    assert res["first_board_pass_ms"] > 0  # the settle ran past tick 50
    assert kernel_bench.run_rung("convoy", 150, 5, 1, settle=10)["first_board_pass_ms"] is None


def test_a_ladder_below_the_scene_base_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        kernel_bench.main(["--ladder", "1", "--ticks", "5", "--scene", "mixed"])
    assert e.value.code == 2
    assert "--ladder" in capsys.readouterr().err


def test_the_frames_flag_times_the_frame_build_and_a_snapshot_every_tick(tmp_path: Path) -> None:
    """NX-170c smoke: no timing assertion (the 25 ms budget is judged on the reference host)."""
    out = tmp_path / "f.json"
    res: Any = kernel_bench.main(
        [
            *("--ladder", "100", "--ticks", "30", "--scene", "mixed", "--viewers", "40"),
            *("--frames", "--settle", "5", "--out", str(out)),
        ]
    )
    assert res["frame_build_counted"] is True and res["snapshot_every"] == 1
    (r,) = res["rungs"]
    assert r["entities"] == 100 and r["viewer_units"] == 40
    f = r["frames"]
    assert f["budget_ms"] == 25.0 and isinstance(f["pass"], bool)
    assert f["delta"] and f["snapshot"] and f["frame"] and f["all"]  # every tick built both
    assert f["all"]["max"] >= r["step_ms"]["max"]  # combined adds the frame build to step
    assert json.loads(out.read_text())["rungs"][0]["frames"]["pass"] == f["pass"]


def test_snapshot_every_zero_builds_no_snapshot_and_viewers_needs_mixed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    res: Any = kernel_bench.main(
        ["--ladder", "60", "--ticks", "12", "--scene", "mixed", "--frames", "--snapshot-every", "0"]
    )
    assert res["rungs"][0]["frames"]["snapshot"] == {}
    assert res["rungs"][0]["frames"]["hud"]  # tick 10 is a Hud tick
    capsys.readouterr()
    for argv, msg in (
        (["--ladder", "60", "--viewers", "5"], "--viewers needs --scene mixed"),  # convoy scene
        (
            ["--ladder", "60", "--scene", "mixed", "--viewers", "-1"],
            "--viewers must not be negative",
        ),
        (
            ["--ladder", "60", "--scene", "mixed", "--viewers", "100000"],
            "--viewers 100000 does not fit",
        ),
    ):
        with pytest.raises(SystemExit) as e:
            kernel_bench.main(argv)
        assert e.value.code == 2
        assert msg in capsys.readouterr().err


def test_the_table_labels_the_largest_tick_as_combined_only_with_frames(
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = ["--ladder", "60", "--ticks", "5", "--scene", "mixed", "--settle", "1"]
    kernel_bench.main(base)
    assert "  largest (tick)" in capsys.readouterr().out
    kernel_bench.main([*base, "--frames"])
    out = capsys.readouterr().out
    assert "  largest combined (tick)" in out and "  largest (tick)" not in out

