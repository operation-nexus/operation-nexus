"""Golden replays: every case under this directory replays to its pinned hashes (NX-105, SC-3).

`NEXUS_UPDATE_GOLDEN=1` rewrites each `expected.json` instead of failing; see README.md for when
that is allowed. The cross-process run is `tools/sim-determinism/check.py`.
"""

import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest
from runtime.test_recovery import POISON, STUB

from nexus.core.step import HANDLERS, Handler
from nexus.runtime.golden import CASE_FILE, EXPECTED_FILE, run_golden, write_expected

from .make_cases import CASES as CASES_PLAN
from .make_cases import write_case

HERE = Path(__file__).parent
CASES = sorted(p for p in HERE.iterdir() if (p / CASE_FILE).is_file())
REGISTRIES: Mapping[str, Mapping[str, Handler]] = {
    "kernel": HANDLERS,
    "stub": STUB,
    "poison": POISON,
}


def test_every_case_is_found() -> None:
    assert [p.name for p in CASES] == [
        "capture-strait-1",
        "empty-1h",
        "joins-strait-1",
        "overnight-0",
        "poison-crash",
        "stub-commands",
    ]


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: p.name)
def test_golden_replay_matches_expected(case_dir: Path) -> None:
    result = run_golden(case_dir, REGISTRIES)
    if os.environ.get("NEXUS_UPDATE_GOLDEN") == "1":
        # An update in CI would rewrite expected.json and pass silently; updates are local only.
        if os.environ.get("CI"):
            pytest.fail("NEXUS_UPDATE_GOLDEN is set in CI; update golden files locally")
        write_expected(case_dir, result)
    expected = json.loads((case_dir / EXPECTED_FILE).read_text())
    assert result.to_json() == expected


def test_poison_case_without_its_tombstone_raises(tmp_path: Path) -> None:
    # Proves the case exercises SC-8: without the tombstone the poison command reaches its handler.
    ticks, handlers, description, commands, _, shipped = CASES_PLAN["poison-crash"]
    write_case(tmp_path, (ticks, handlers, description, commands, (), shipped))
    with pytest.raises(RuntimeError, match="poison command"):
        run_golden(tmp_path, REGISTRIES)


def test_unknown_registry_or_missing_log_raises(tmp_path: Path) -> None:
    case = shutil.copytree(HERE / "poison-crash", tmp_path / "case")
    with pytest.raises(ValueError, match="unknown handler registry"):
        run_golden(case, {"stub": STUB})
    shutil.rmtree(case / "log")
    with pytest.raises(ValueError, match="no log/"):
        run_golden(case, REGISTRIES)


def test_log_past_the_case_end_raises(tmp_path: Path) -> None:
    case = shutil.copytree(HERE / "stub-commands", tmp_path / "case")
    data = json.loads((case / CASE_FILE).read_text())
    (case / CASE_FILE).write_text(json.dumps({**data, "ticks": 294}))
    with pytest.raises(ValueError, match=r"tick 295, outside 1\.\.294"):
        run_golden(case, REGISTRIES)


@pytest.mark.parametrize("bad", [{"ticks": "300"}, {"ticks": 0}, {"extra": 1}])
def test_malformed_case_raises(tmp_path: Path, bad: dict[str, object]) -> None:
    case = shutil.copytree(HERE / "stub-commands", tmp_path / "case")
    data = json.loads((case / CASE_FILE).read_text())
    (case / CASE_FILE).write_text(json.dumps({**data, **bad}))
    with pytest.raises(ValueError, match=r"case\.json|ticks"):
        run_golden(case, REGISTRIES)


@pytest.mark.parametrize(
    ("bad", "match"),
    [({"config_hash": "cfg-old"}, "not the shipped config's"), ({"rules": "x"}, "be 'shipped'")],
)
def test_shipped_rules_case_needs_the_shipped_config(
    tmp_path: Path, bad: dict[str, object], match: str
) -> None:
    case = shutil.copytree(HERE / "joins-strait-1", tmp_path / "case")
    data = json.loads((case / CASE_FILE).read_text())
    (case / CASE_FILE).write_text(json.dumps({**data, **bad}))
    with pytest.raises(ValueError, match=match):
        run_golden(case, REGISTRIES)
