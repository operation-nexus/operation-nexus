"""Balance harness runner (NX-031 part 1, Q-SIM-91; TESTING-STRATEGY §3.5, §3.5a).

Drives the real sim headless through the ordinary command path with scripted viewer personas, for
the crowd profiles of Q-TEST-5, and writes a report per run and per profile (JSON and Markdown).

  cd services/sim && uv run --frozen python ../../tools/balance/balance.py \\
      --profile prime-50 --seeds 5 --hours 72 --workers 4 --out /path/to/report-dir

`--profile` is one name, a comma list, or `all`; `--seeds` a count N (seeds 1..N) or a comma list;
`--hours` the game hours per run (72 for acceptance; a run stops early when the campaign ends);
`--workers` the number of parallel processes (seeds are independent, so the report does not depend
on it). `--set key=number` (repeatable) overrides one numeric balance key of the shipped config
(e.g. `--set tasking.strike_idle_targets_max=0`); the config is then validated as usual, the
overridden copy is saved as `<out>/balance.yaml` (every worker loads that file), and the report
lists the overrides beside the resulting config hash; a key given twice is an error. `--out` must
not exist: it gets `report.json`, `report.md`, `runs/<profile>-s<seed>.json` and
`logs/<profile>-s<seed>/` (the command logs).

Exit 0 on success, 2 on a usage or config error (one line on stderr). Targets that fail do not
change the exit code: the report says it.
"""

import argparse
import json
import math
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import profiles
import report
import runner
import yaml

from nexus.runtime.campaign_config import CampaignConfig, ConfigPaths, load_campaign_config
from nexus.runtime.config import ConfigError, load_balance


def override_balance(pairs: list[str]) -> str:
    """The shipped balance config as YAML text with `key=number` overrides applied and validated
    by the sim's own loader. Raises ValueError (bad pair) or ConfigError (schema)."""
    tree = yaml.safe_load(ConfigPaths().balance.read_text())
    keys = [p.partition("=")[0] for p in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("--set: a key is given twice")
    for pair in pairs:
        key, _, text = pair.partition("=")
        node = tree
        *path, leaf = key.split(".")
        for part in path:
            node = node.get(part) if isinstance(node, dict) else None
        old = node.get(leaf) if isinstance(node, dict) else None
        if isinstance(old, bool) or not isinstance(old, int | float):
            raise ValueError(f"--set {key}: not an existing numeric balance key")
        try:
            value = int(text) if isinstance(old, int) else float(text)
        except ValueError:
            raise ValueError(f"--set {key}: {text!r} is not a valid {type(old).__name__}") from None
        if not math.isfinite(value):
            raise ValueError(f"--set {key}: {text!r} is not finite")
        node[leaf] = value
    dumped = yaml.safe_dump(tree, sort_keys=False)
    with tempfile.TemporaryDirectory() as d:
        (check := Path(d) / "balance.yaml").write_text(dumped)
        load_balance(check)  # raises ConfigError naming the key and the problem
    return dumped


def _one(job: tuple[str, int, float, Path, Path | None]) -> dict[str, Any]:
    """A worker: one (profile, seed) run, its JSON written next to the others."""
    profile, seed, hours, out, balance_file = job
    name = f"{profile}-s{seed}"
    try:
        config: CampaignConfig | None = None
        if balance_file:
            config = load_campaign_config(ConfigPaths(balance=balance_file))
        run = runner.run(profile, seed, hours, out / "logs" / name, config=config)
    except Exception as e:  # noqa: BLE001  # one run's failure must not kill the batch
        run = runner.failed_run(profile, seed, hours, f"{type(e).__name__}: {e}")
    (out / "runs" / f"{name}.json").write_text(json.dumps(run, indent=1, sort_keys=True) + "\n")
    return run


def _headline(run: dict[str, Any]) -> dict[str, Any]:
    o = run["metrics"]["outcome"]
    outcome = f"{o['result']} at {o['length_h']:.2f} h" if o["ended"] else "not ended"
    if run["harness_error"]:
        outcome = f"HARNESS ERROR: {run['harness_error']}"
    elif run["crash"]:
        outcome = f"CRASHED at tick {run['crash']['tick']}: {run['crash']['error']}"
    return {
        "profile": run["profile"],
        "seed": run["seed"],
        "ticks_run": run["ticks_run"],
        "outcome": outcome,
        "wall_s": run["timing"]["wall_s"],
        "ticks_per_s": run["timing"]["ticks_per_s"],
        "final_state_hash": run["final_state_hash"],  # None for a crashed run
    }


def build_report(
    runs: list[dict[str, Any]],
    data: profiles.Data,
    workers: int,
    elapsed: float,
    overrides: list[str] | None = None,
) -> dict[str, Any]:
    by_profile: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        by_profile.setdefault(r["profile"], []).append(r)
    aggregated = {n: report.aggregate(n, rs, data.targets) for n, rs in by_profile.items()}
    first = runs[0]  # every run has the same hours
    return {
        "config": {
            "config_hash": next((r["config_hash"] for r in runs if r["config_hash"]), None),
            "profiles_digest": data.digest,
            "overrides": overrides or [],
        },
        "seeds": sorted({r["seed"] for r in runs}),
        "hours": first["hours"],
        "workers": workers,
        "timing": {
            "elapsed_s": elapsed,
            "run_wall_s": sum(r["timing"]["wall_s"] for r in runs),
        },
        "profiles": aggregated,
        "targets": report.target_table(aggregated),
        "runs": [_headline(r) for r in runs],
    }


def _seeds(text: str) -> list[int]:
    try:
        values = [int(x) for x in text.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer or a comma list: {text!r}") from None
    seeds = values if len(values) > 1 else list(range(1, values[0] + 1))
    if not seeds or min(seeds) < 1 or len(set(seeds)) != len(seeds):
        raise argparse.ArgumentTypeError("seeds must be positive and distinct")
    return seeds


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    p.add_argument("--profile", default="all", help="a profile name, a comma list, or 'all'")
    p.add_argument("--seeds", type=_seeds, default=_seeds("1"), help="a count N or a comma list")
    p.add_argument("--hours", type=float, default=72.0, help="game hours per run (default 72)")
    p.add_argument("--workers", type=int, default=1, help="parallel processes (default 1)")
    p.add_argument(
        "--set", dest="overrides", action="append", default=[], metavar="KEY=NUMBER",
        help="override a numeric balance key, e.g. tasking.strike_idle_targets_max=0 (repeatable)",
    )  # fmt: skip
    p.add_argument("--out", type=Path, required=True, help="report directory (must not exist)")
    return p


def main() -> int:
    args = parser().parse_args()
    data = profiles.load()
    names = list(data.profiles) if args.profile == "all" else args.profile.split(",")
    try:
        if unknown := [n for n in names if n not in data.profiles]:
            raise ValueError(f"unknown profiles {unknown}; known: {list(data.profiles)}")
        if args.hours <= 0 or args.workers < 1:
            raise ValueError("--hours must be > 0 and --workers >= 1")
        balance_text = override_balance(args.overrides) if args.overrides else None
        args.out.mkdir(parents=True)
        (args.out / "runs").mkdir()
        balance_file = None
        if balance_text:
            balance_file = args.out / "balance.yaml"
            balance_file.write_text(balance_text)
        jobs = [(n, s, args.hours, args.out, balance_file) for n in names for s in args.seeds]
        started = time.perf_counter()
        if args.workers == 1:
            runs = [_one(j) for j in jobs]
        else:
            # Longest first (the biggest crowd costs the most) so the last run to start is a short
            # one; the results go back to job order, so the report does not depend on it.
            by_cost = sorted(jobs, key=lambda j: -data.profiles[j[0]].viewers)
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                done = dict(
                    zip(((j[0], j[1]) for j in by_cost), pool.map(_one, by_cost), strict=True)
                )
            runs = [done[(j[0], j[1])] for j in jobs]
        elapsed = time.perf_counter() - started
        result = build_report(runs, data, args.workers, elapsed, args.overrides)
    except (ValueError, OSError, ConfigError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    (args.out / "report.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (args.out / "report.md").write_text(report.markdown(result))
    print(report.markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
