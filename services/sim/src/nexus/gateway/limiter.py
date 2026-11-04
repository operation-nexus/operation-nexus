"""Token-bucket limiter, slow mode, global cap, blatant-spam count (CHAT-GATEWAY GW-11..13).

Time comes only from the injected monotonic `clock` (never wall clock, never sim time). Buckets are
created lazily; a bucket that has refilled to full is the same as a fresh one, so the periodic sweep
evicts those (lossless, memory bounded by the users active within one refill window).
The social/redeem class has no config keys yet and is left out of `CommandClass` until it does.
"""

import math
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum

_EPS = 1e-9


class CommandClass(StrEnum):
    DEPLOY = "deploy"
    CORRECTION = "correction"
    INFO = "info"
    CALLSIGN = "callsign"
    FORGET = "forget"


class Verdict(StrEnum):
    ADMITTED = "ADMITTED"
    RATE_LIMITED = "RATE_LIMITED"  # the user's own bucket; counts toward blatant spam
    GLOBAL_CAP = "GLOBAL_CAP"  # raid protection; not the user's fault, so it is not counted


@dataclass(frozen=True)
class ClassLimit:
    min_interval_s: float
    burst: int

    def __post_init__(self) -> None:
        if not (math.isfinite(self.min_interval_s) and self.min_interval_s > 0 and self.burst >= 1):
            raise ValueError("a class limit needs min_interval_s > 0 and burst >= 1")


@dataclass(frozen=True)
class LimiterConfig:
    """Every field is required: a value comes from config, never from a code default (CFG-2)."""

    classes: Mapping[CommandClass, ClassLimit]
    slow_mode_multiplier: float  # ratelimit.slow_mode.multiplier
    cmds_per_tick: int  # ratelimit.global.cmds_per_tick
    blatant_threshold: int  # gateway.spam.blatant_threshold
    blatant_window_s: float  # gateway.spam.blatant_window_s

    def __post_init__(self) -> None:
        missing = set(CommandClass) - set(self.classes)
        ok = (
            math.isfinite(self.slow_mode_multiplier)
            and self.slow_mode_multiplier >= 1
            and self.cmds_per_tick >= 1
            and self.blatant_threshold >= 1
            and math.isfinite(self.blatant_window_s)
            and self.blatant_window_s > 0
        )
        if missing or not ok:
            raise ValueError(f"invalid limiter config (missing classes: {sorted(missing)})")


class Limiter:
    def __init__(self, config: LimiterConfig, clock: Callable[[], float]) -> None:
        self._cfg = config
        self._clock = clock
        self._buckets: dict[tuple[str, CommandClass], list[float]] = {}  # [tokens, stamp]
        self._rejects: dict[str, deque[float]] = {}
        self._slow = False
        self._admitted = 0
        self._swept = clock()
        refill = max(lim.min_interval_s * lim.burst for lim in config.classes.values())
        self._sweep_every = max(refill * config.slow_mode_multiplier, config.blatant_window_s)

    @property
    def bucket_count(self) -> int:
        return len(self._buckets)

    def set_slow_mode(self, on: bool) -> None:
        """Settle every bucket at the old rate first, so the switch never reprices elapsed time."""
        if on == self._slow:
            return
        now = self._clock()
        for (_, cls), bucket in self._buckets.items():
            bucket[0] = self._refilled(bucket, cls, now)
            bucket[1] = max(bucket[1], now)
        self._slow = on

    def new_tick(self) -> None:
        """The caller marks each tick boundary; the global cap counts admissions since it."""
        self._admitted = 0

    def check(self, user: str, cls: CommandClass) -> Verdict:
        """Take one token for `user` (a commander id or platform identity key) in `cls`."""
        now = self._clock()
        if now - self._swept >= self._sweep_every:
            self._sweep(now)
        limit = self._cfg.classes[cls]
        bucket = self._buckets.setdefault((user, cls), [float(limit.burst), now])
        bucket[0] = self._refilled(bucket, cls, now)
        bucket[1] = max(bucket[1], now)  # a clock stepping back must not refill twice
        if bucket[0] < 1.0 - _EPS:
            self._rejects.setdefault(user, deque(maxlen=self._cfg.blatant_threshold)).append(now)
            return Verdict.RATE_LIMITED
        if self._admitted >= self._cfg.cmds_per_tick:
            return Verdict.GLOBAL_CAP
        bucket[0] -= 1.0
        self._admitted += 1
        return Verdict.ADMITTED

    def is_blatant(self, user: str) -> bool:
        """At least `blatant_threshold` limiter rejections within `blatant_window_s` (GW-13)."""
        recent = self._rejects.get(user)
        return (
            recent is not None
            and len(recent) == recent.maxlen
            and self._clock() - recent[0] <= self._cfg.blatant_window_s
        )

    def _refilled(self, bucket: list[float], cls: CommandClass, now: float) -> float:
        limit = self._cfg.classes[cls]
        interval = limit.min_interval_s * (self._cfg.slow_mode_multiplier if self._slow else 1.0)
        return min(float(limit.burst), bucket[0] + max(0.0, now - bucket[1]) / interval)

    def _sweep(self, now: float) -> None:
        self._swept = now
        for key, bucket in list(self._buckets.items()):
            if self._refilled(bucket, key[1], now) >= self._cfg.classes[key[1]].burst:
                del self._buckets[key]
        for user, recent in list(self._rejects.items()):
            if now - recent[-1] > self._cfg.blatant_window_s:
                del self._rejects[user]
