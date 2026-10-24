"""The Q-TEST-11 steamroll signals S1 to S4 for one won campaign (NX-411; TESTING-STRATEGY §3.5a A1;
docs/review/ENTERTAINMENT-steamroll-2026-10-24.md §3). Pure functions on one run's metrics dict
(`Collector.result`); the thresholds are `profiles.Targets.steamroll_*` (all PROPOSED, Q-TEST-11).

A signal with nothing to measure has `value` None and does not fire; `note` says why. Only a won
campaign (result VICTORY) is judged."""

import statistics
from typing import Any

from profiles import Targets

HOURS_PER_UNIT = 4  # S1 is normalised per 4 campaign hours (Q-TEST-11): a unit, not a tunable


def _signal(value: Any, fired: bool, note: str | None = None) -> dict[str, Any]:
    return {"value": value, "fired": fired, "note": note}


def _s1(raw: dict[str, Any], length_h: float, t: Targets) -> dict[str, Any]:
    if length_h <= 0:
        return _signal(None, False, "not measurable: zero-length campaign")
    rate = len(raw["pressure_ticks"]) * HOURS_PER_UNIT / length_h
    return _signal(rate, rate < t.steamroll_pressure_per_4h)


def _s2(raw: dict[str, Any]) -> dict[str, Any]:
    start = raw["hold_start"]
    if start is None:
        # the campaign ended with the coalition under victory_node_frac: an HQ capture, no hold
        return _signal(None, False, "not measurable: won with no victory hold running (HQ capture)")
    pressure = sum(tick >= start for tick in raw["pressure_ticks"])
    value = {"pressure": pressure, "broken": raw["holds_broken"]}
    return _signal(value, pressure == 0 and raw["holds_broken"] == 0)


def _s3(momentum: list[int], t: Targets) -> dict[str, Any]:
    leader: str | None = None
    changes, first, peak, drop = 0, None, 0, 0
    for i, m in enumerate(momentum):
        side = "C" if m > t.steamroll_lead_line else "E" if m < t.steamroll_lead_line else leader
        if side != leader and side is not None:
            changes += leader is not None  # the first leader is the start, not a change
            leader = side
        if first is None and leader == "C":
            first = i
        if first is not None:
            peak = max(peak, m)
            drop = max(drop, peak - m)
    if first is None:
        return _signal(None, False, "not measurable: the coalition never led")
    fired = drop < t.steamroll_swing_pts and changes <= t.steamroll_max_lead_changes
    return _signal({"max_drop": drop, "lead_changes": changes}, fired)


def _s4(raw: dict[str, Any], end_tick: int, t: Targets) -> dict[str, Any]:
    units, stock = raw["static"]["units"], raw["static"]["stock"]
    late = [i for i in range(len(units)) if (i + 1) * raw["sample_ticks"] * 3 > end_tick * 2]
    if not late or not max(units, default=0):
        return _signal(None, False, "not measurable: no late-third sample or no Static unit seen")
    units_frac = statistics.fmean(units[i] for i in late) / max(units)
    start = raw["static"]["start_stock"]
    stock_frac = statistics.fmean(stock[i] for i in late) / start if start else None
    fired = units_frac < t.steamroll_late_units_frac or (
        stock_frac is not None and stock_frac < t.steamroll_late_stock_frac
    )
    return _signal({"units_of_peak": units_frac, "stock_of_start": stock_frac}, fired)


def judge(metrics: dict[str, Any], t: Targets) -> dict[str, Any]:
    """The four signals and the verdict for one run's `metrics`. A run that was not won is not
    judged (`judged` False, `steamroll` None)."""
    out = metrics["outcome"]
    raw = metrics.get("steamroll")
    if out.get("result") != "VICTORY" or raw is None:
        return {"judged": False, "steamroll": None, "fired": 0, "signals": {}}
    mo = metrics["momentum"]
    signals = {
        "S1": _s1(raw, out["length_h"], t),
        "S2": _s2(raw),
        "S3": _s3(mo["samples"], t),
        "S4": _s4(raw, out["end_tick"], t),
    }
    fired = sum(s["fired"] for s in signals.values())
    both = signals["S1"]["fired"] and signals["S2"]["fired"]
    return {
        "judged": True,
        "steamroll": both or fired >= t.steamroll_min_signals,
        "fired": fired,
        "signals": signals,
    }
