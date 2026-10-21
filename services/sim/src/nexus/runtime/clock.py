"""Fixed-step accumulator on a monotonic clock (SIM-CORE §5, SYSTEM-DESIGN §5.2)."""

from collections.abc import Callable

from nexus.core.step import TICK_DT


class FixedStepClock:
    """Counts the steps due since the last call. `now` is `time.monotonic` in production."""

    def __init__(
        self, now: Callable[[], float], tick_dt: float = TICK_DT, max_catch_up: int = 3
    ) -> None:
        self._now = now
        self._tick_dt = tick_dt
        self._max_catch_up = max_catch_up
        self._start = now()
        self._counted = 0  # steps run or dropped since `_start`
        self.tick_overruns = 0

    def due_steps(self) -> int:
        """Steps to run now, at most `max_catch_up`; the excess is dropped and counted."""
        # Counted from the start, so float error never accumulates; the epsilon (a millionth of
        # a step) keeps e.g. 0.3 s from rounding down to 2 steps of 0.1 s.
        total = int((self._now() - self._start) / self._tick_dt + 1e-6)
        steps = total - self._counted
        self._counted = total
        if steps > self._max_catch_up:
            self.tick_overruns += 1
            return self._max_catch_up
        return steps
