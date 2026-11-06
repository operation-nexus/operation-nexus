"""NX-514 strike probe: why a launch's strike never fired (tools/balance/probe_strikes.py)."""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "balance"))
import probe_strikes as ps  # type: ignore[import-not-found,unused-ignore]


def _launch(
    *, tick: int = 100, shots: int = 0, hits: list[str] | None = None, end: str | None = None
) -> dict[str, Any]:
    units = {"1": {"hits": [(5, w, 2) for w in hits or []], "damage": []}}
    strike = {"kind": "STRIKE", "end": (end, 50) if end else None, "units": units}
    return {
        "tick": tick,
        "shots": [(1, 1, "AG_LIGHT")] * shots,
        "other_shots": [],
        "jobs": [strike, {"kind": "CAPTURE", "end": None}],
    }


def test_a_fired_launch_says_how_its_strike_ended() -> None:
    assert ps.classify(_launch(shots=2, end="expired"), 1000) == "fired; STRIKE expired"


def test_sam_hits_on_every_claimant_are_named_not_guessed() -> None:
    assert ps.classify(_launch(hits=["SAM"]), 1000) == "every claimant hit by a SAM before firing"
    assert ps.classify(_launch(hits=["GUN"]), 1000) == "a claimant hit by other fire before firing"


def test_a_launch_on_the_last_tick_had_no_time_to_fire() -> None:
    assert "last tick" in ps.classify(_launch(tick=1000), 1000)


def test_no_evidence_is_reported_as_it_ended() -> None:
    assert ps.classify(_launch(end="expired"), 1000) == "no hit seen; STRIKE expired"
    assert "still open" in ps.classify(_launch(), 1000)
