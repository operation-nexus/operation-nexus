"""Cross-process determinism check (NX-105; SIM-CORE SC-3, TESTING-STRATEGY §3.2).

Runs every golden case under services/sim/tests/golden in separate interpreters, one per
PYTHONHASHSEED value, and requires every run to equal the others and the committed expected.json.
Exits 1 with a per-value diff on a mismatch, 2 when a run fails.

The seeds are fixed, so a failure reproduces; "0" also turns hash randomization off. There are four
because two seeds can share a small set's iteration order and then agree on a wrong result (seeds 0
and 1729 both put "alpha" first in {"alpha", "bravo", "charlie", "delta"}). More seeds only lower
that chance: the stronger guard is the comparison with expected.json, which was written by one run
and catches any run that differs from it.

  cd services/sim && uv run --frozen python ../../tools/sim-determinism/check.py

The parent is stdlib only; the children use this interpreter (the services/sim venv).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TESTS = Path(__file__).resolve().parents[2] / "services" / "sim" / "tests"
GOLDEN = TESTS / "golden"
HASH_SEEDS = ("0", "1", "1729", "4242")
MAX_LINES_PER_CASE = 10
CHILD = (
    "import json, sys; sys.path.insert(0, sys.argv[1])\n"
    "from golden.test_golden import CASES, REGISTRIES\n"
    "from nexus.runtime.golden import run_golden\n"
    "print(json.dumps({p.name: run_golden(p, REGISTRIES, rules=None).to_json() for p in CASES}))"
)


def run(hash_seed: str) -> dict[str, Any]:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    start = time.perf_counter()
    # fixed argv: this interpreter + a literal script + a repo path
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", CHILD, str(TESTS)], env=env, capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(f"PYTHONHASHSEED={hash_seed}: run failed\n{proc.stderr}", file=sys.stderr)
        sys.exit(2)
    print(f"PYTHONHASHSEED={hash_seed}: {time.perf_counter() - start:.2f} s")
    result: dict[str, Any] = json.loads(proc.stdout)
    return result


def flatten(result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return {"case": "missing"}
    flat = {f"checkpoint {tick}": h for tick, h in result["checkpoints"].items()}
    return {**flat, "event_count": result["event_count"], "events_hash": result["events_hash"]}


def diff(case: str, runs: dict[str, dict[str, Any] | None]) -> list[str]:
    flat = {label: flatten(r) for label, r in runs.items()}
    keys = dict.fromkeys(k for f in flat.values() for k in f)
    lines = []
    for key in keys:
        values = {label: f.get(key) for label, f in flat.items()}
        if len(set(map(repr, values.values()))) > 1:
            lines.append(f"  {case} {key}: " + "  ".join(f"{k}={v}" for k, v in values.items()))
    if len(lines) > MAX_LINES_PER_CASE:
        lines[MAX_LINES_PER_CASE:] = [f"  ... {len(lines) - MAX_LINES_PER_CASE} more"]
    return lines


def main() -> int:
    expected = {
        p.name: json.loads((p / "expected.json").read_text())
        for p in sorted(GOLDEN.iterdir())
        if (p / "case.json").is_file()
    }
    if not expected:
        print(f"no golden cases under {GOLDEN}", file=sys.stderr)
        return 2
    results = {f"hashseed={seed}": run(seed) for seed in HASH_SEEDS}
    mismatches: list[str] = []
    for case in sorted(expected.keys() | {c for r in results.values() for c in r}):
        runs = {"expected": expected.get(case), **{k: r.get(case) for k, r in results.items()}}
        mismatches += diff(case, runs)
    if mismatches:
        print("determinism check FAILED:", *mismatches, sep="\n")
        return 1
    print(f"determinism check passed: {len(expected)} cases x {len(HASH_SEEDS)} processes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
