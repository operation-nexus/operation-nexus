"""GW-11, GW-12, GW-13: limiter on a fake monotonic clock (CHAT-GATEWAY §10)."""

import logging
import math
import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.gateway.fakes import FakeClock
from nexus.gateway.limiter import ClassLimit, CommandClass, Limiter, LimiterConfig, Verdict

# Spec §5 PROPOSED values, written out here because the config keys have no home yet.
CLASSES = {
    CommandClass.DEPLOY: ClassLimit(10, 1),
    CommandClass.CORRECTION: ClassLimit(5, 2),
    CommandClass.INFO: ClassLimit(15, 1),
    CommandClass.CALLSIGN: ClassLimit(60, 1),
    CommandClass.FORGET: ClassLimit(60, 1),
}
CONFIG = LimiterConfig(
    CLASSES, slow_mode_multiplier=3, cmds_per_tick=50, blatant_threshold=10, blatant_window_s=60
)
D, C, I = CommandClass.DEPLOY, CommandClass.CORRECTION, CommandClass.INFO  # noqa: E741


def make(config: LimiterConfig = CONFIG) -> tuple[Limiter, FakeClock]:
    clock = FakeClock(1000.0)
    return Limiter(config, clock), clock


def test_no_wall_clock_or_monotonic_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> float:
        raise AssertionError("wall clock or monotonic read inside the limiter")

    lim, clock = make()  # built before the patch: only the injected clock may be read after it
    monkeypatch.setattr(time, "time", boom)
    monkeypatch.setattr(time, "monotonic", boom)
    lim.set_slow_mode(True)
    for _ in range(12):
        clock.advance(1)
        lim.check("a", D)
    assert lim.is_blatant("a")  # 11 rejections in 12 s under slow mode, threshold 10
    clock.advance(10_000)  # forces the sweep
    lim.check("b", I)
    lim.new_tick()
    assert not lim.is_blatant("a")


def test_refill_and_single_burst() -> None:
    lim, clock = make()
    assert lim.check("a", D) is Verdict.ADMITTED
    assert lim.check("a", D) is Verdict.RATE_LIMITED
    clock.advance(9.9)
    assert lim.check("a", D) is Verdict.RATE_LIMITED
    clock.advance(0.1)
    assert lim.check("a", D) is Verdict.ADMITTED


def test_burst_of_two_then_one_per_interval() -> None:
    lim, clock = make()
    assert [lim.check("a", C) for _ in range(3)] == [Verdict.ADMITTED] * 2 + [Verdict.RATE_LIMITED]
    clock.advance(5)
    assert lim.check("a", C) is Verdict.ADMITTED
    assert lim.check("a", C) is Verdict.RATE_LIMITED
    clock.advance(1000)  # a long idle refills to the burst, not beyond it
    assert [lim.check("a", C) for _ in range(3)] == [Verdict.ADMITTED] * 2 + [Verdict.RATE_LIMITED]


def test_classes_and_users_are_independent() -> None:
    lim, _ = make()
    assert lim.check("a", D) is Verdict.ADMITTED
    assert lim.check("a", I) is Verdict.ADMITTED  # other class, own bucket
    assert lim.check("b", D) is Verdict.ADMITTED  # other user
    assert lim.check("a", D) is Verdict.RATE_LIMITED


def test_slow_mode_multiplies_the_interval() -> None:
    lim, clock = make()
    lim.set_slow_mode(True)
    assert lim.check("a", D) is Verdict.ADMITTED
    clock.advance(29.9)
    assert lim.check("a", D) is Verdict.RATE_LIMITED
    clock.advance(0.1)
    assert lim.check("a", D) is Verdict.ADMITTED
    lim.set_slow_mode(False)
    clock.advance(10)
    assert lim.check("a", D) is Verdict.ADMITTED


def test_global_cap_is_per_tick_and_does_not_charge_the_user() -> None:
    cfg = LimiterConfig(CLASSES, 3, cmds_per_tick=2, blatant_threshold=10, blatant_window_s=60)
    lim, _ = make(cfg)
    assert [lim.check(u, D) for u in "abc"] == [Verdict.ADMITTED] * 2 + [Verdict.GLOBAL_CAP]
    assert not lim.is_blatant("c")
    lim.new_tick()
    assert lim.check("c", D) is Verdict.ADMITTED  # the capped command kept its token
    assert lim.check("d", D) is Verdict.ADMITTED
    assert lim.check("e", D) is Verdict.GLOBAL_CAP


def test_idle_buckets_are_evicted_and_a_returning_user_starts_full() -> None:
    lim, clock = make()
    for i in range(100):
        lim.new_tick()  # keep the global cap (50) out of this test
        lim.check(f"u{i}", D)
    assert lim.bucket_count == 100
    clock.advance(10_000)  # past a full refill and a sweep interval
    lim.check("late", D)
    assert lim.bucket_count == 1  # the 100 refilled buckets are gone, only "late" is live
    assert lim.check("u0", D) is Verdict.ADMITTED


def test_unrefilled_buckets_survive_the_sweep() -> None:
    lim, clock = make()  # sweep interval: 60 s refill x 3 = 180 s
    clock.advance(170)
    lim.check("a", CommandClass.CALLSIGN)
    clock.advance(10)
    lim.check("b", D)  # runs the sweep; "a" has refilled only 10 of 60 s
    assert lim.bucket_count == 2
    assert lim.check("a", CommandClass.CALLSIGN) is Verdict.RATE_LIMITED


def test_blatant_threshold_and_window() -> None:
    lim, clock = make()
    lim.check("s", D)
    for _ in range(9):
        assert lim.check("s", D) is Verdict.RATE_LIMITED
    assert not lim.is_blatant("s")  # 9 rejections
    lim.check("s", D)
    assert lim.is_blatant("s")  # 10 within 60 s
    assert not lim.is_blatant("someone else")
    clock.advance(61)
    assert not lim.is_blatant("s")  # the window moved on


def test_slow_rejections_never_become_blatant() -> None:
    lim, clock = make()
    lim.check("s", D)
    for _ in range(30):  # about 8 rejections per 60 s window, under the threshold of 10
        clock.advance(7)
        lim.check("s", CommandClass.FORGET)
    assert not lim.is_blatant("s")


def test_logs_hold_nothing(caplog: pytest.LogCaptureFixture) -> None:
    lim, _ = make()
    with caplog.at_level(logging.DEBUG):
        for _ in range(3):
            lim.check("secret-user-text-XYZ", D)
    assert "XYZ" not in caplog.text and caplog.records == []


@pytest.mark.parametrize(
    "bad",
    [
        lambda: ClassLimit(0, 1),
        lambda: ClassLimit(1, 0),
        lambda: LimiterConfig({}, 3, 50, 10, 60),
        lambda: LimiterConfig(CLASSES, 0.5, 50, 10, 60),
        lambda: LimiterConfig(CLASSES, 3, 0, 10, 60),
        lambda: LimiterConfig(CLASSES, 3, 50, 0, 60),
    ],
)
def test_bad_config_is_refused(bad: object) -> None:
    with pytest.raises(ValueError):
        bad()  # type: ignore[operator]


@given(st.lists(st.floats(min_value=0, max_value=30), max_size=60))
def test_admissions_never_exceed_the_bucket_bound(gaps: list[float]) -> None:
    """Over any span T, a (1 per 10 s) bucket admits at most 1 + T/10 commands."""
    lim, clock = make()
    start = clock.now
    admitted = 0
    for gap in gaps:
        clock.advance(gap)
        admitted += lim.check("a", D) is Verdict.ADMITTED
    assert admitted <= 1 + (clock.now - start) / 10 + 1e-6


def test_a_clock_stepping_back_does_not_refill_twice() -> None:
    lim, clock = make()
    clock.now = 100.0
    assert lim.check("a", D) is Verdict.ADMITTED
    clock.now = 95.0
    assert lim.check("a", D) is Verdict.RATE_LIMITED
    clock.now = 105.0  # only 5 s after the admit at 100
    assert lim.check("a", D) is Verdict.RATE_LIMITED


def test_refill_is_capped_at_the_burst_without_a_sweep() -> None:
    lim, clock = make()
    for _ in range(2):
        lim.check("a", C)
    clock.advance(100)  # under the 180 s sweep interval: only the refill cap holds it at 2
    assert [lim.check("a", C) for _ in range(3)] == [Verdict.ADMITTED] * 2 + [Verdict.RATE_LIMITED]


def test_global_cap_refusals_never_make_a_user_blatant() -> None:
    cfg = LimiterConfig(CLASSES, 3, cmds_per_tick=1, blatant_threshold=3, blatant_window_s=60)
    lim, _ = make(cfg)
    lim.check("x", D)
    for i in range(10):
        assert lim.check(f"u{i}", D) is Verdict.GLOBAL_CAP
    assert not any(lim.is_blatant(f"u{i}") for i in range(10))
    for _ in range(5):
        assert lim.check("u0", D) is Verdict.GLOBAL_CAP  # same user, over the threshold count
    assert not lim.is_blatant("u0")


def test_blatant_window_edge_is_inclusive() -> None:
    cfg = LimiterConfig(CLASSES, 3, 50, blatant_threshold=3, blatant_window_s=60)
    lim, clock = make(cfg)
    lim.check("s", D)  # admitted, t=1000
    for _ in range(3):  # three rejections at t=1000
        lim.check("s", D)
    clock.advance(60)
    assert lim.is_blatant("s")  # the oldest of the last 3 is exactly 60 s old
    clock.advance(0.001)
    assert not lim.is_blatant("s")


def test_sweep_evicts_stale_rejections_and_keeps_live_ones() -> None:
    lim, clock = make()  # sweep interval 180 s, window 60 s
    for who in ("stale", "live"):
        lim.check(who, D)
        for _ in range(10):
            lim.check(who, D)
    clock.advance(150)  # "stale" ages out of its window by the sweep; "live" re-rejects below
    for _ in range(10):
        lim.check("live", CommandClass.FORGET)
        lim.check("live", CommandClass.FORGET)
    clock.advance(30)  # t=180: the sweep runs on this check
    lim.check("probe", D)
    assert "stale" not in lim._rejects and "live" in lim._rejects


def test_float_accumulation_needs_the_epsilon() -> None:
    cfg = LimiterConfig(
        {**CLASSES, D: ClassLimit(0.1, 1)}, 3, 50, blatant_threshold=10, blatant_window_s=60
    )
    lim, clock = make(cfg)
    clock.now = 0.1
    lim.check("a", D)  # tokens 1 -> 0, stamp 0.1
    for _ in range(50):  # ten steps of 0.1 summed in floats: each must refill exactly one token
        clock.now += 0.1
        lim.new_tick()
        assert lim.check("a", D) is Verdict.ADMITTED, clock.now


@pytest.mark.parametrize("bad", [math.nan, math.inf, 0.0, -1.0])
def test_non_finite_or_non_positive_values_are_refused(bad: float) -> None:
    with pytest.raises(ValueError):
        ClassLimit(bad, 1)
    with pytest.raises(ValueError):
        LimiterConfig(CLASSES, bad, 50, 10, 60)
    with pytest.raises(ValueError):
        LimiterConfig(CLASSES, 3, 50, 10, bad)
