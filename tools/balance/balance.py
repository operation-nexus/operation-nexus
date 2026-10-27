"""Balance harness runner (NX-031 part 1, Q-SIM-91; TESTING-STRATEGY §3.5, §3.5a).

Drives the real sim headless through the ordinary command path with scripted viewer personas, for
the crowd profiles of Q-TEST-5, and writes a report per run and per profile (JSON and Markdown).

  cd services/sim && uv run --frozen python ../../tools/balance/balance.py \\
      --profile prime-50 --seeds 5 --hours 72 --workers 4 --out /path/to/report-dir

`--profile` is one name, a comma list, or `all`; `--seeds` a count N (seeds 1..N) or a comma list;
`--hours` the game hours per run (default `campaign.time_limit_h`, 72 shipped;
a run stops early when the campaign ends);
`--workers` the number of parallel processes (seeds are independent, so the report does not depend
on it). `--set key=value` (repeatable) overrides one numeric or boolean balance key of the shipped
config (e.g. `--set tasking.strike_idle_targets_max=0`, `--set economy.legacy_rules=false`; a
boolean key takes `true` or `false` only, a numeric key a number only); the config is then
validated as usual, the overridden copy is saved as `<out>/balance.yaml` (every worker loads that
file), and the report lists the overrides beside the resulting config hash and the economy mode
(`economy.legacy_rules`, `economy.unlimited.<side>`: ECONOMY EC-15); a key given twice is an
error. `--out` must
not exist (unless `--resume`, below): it gets `report.json`, `report.md`,
`runs/<profile>-s<seed>.json` and
`logs/<profile>-s<seed>/` (the command logs).

`--resume` (NX-433) continues a killed job in an existing `--out`: a run whose
`runs/<profile>-s<seed>.json` exists, parses, names the same profile, seed and hours, carries the
current config hash and the keys the report reads is kept, every other run (missing, partial,
corrupt, from another config, or a harness-error stand-in) is run again, and the report is built
from all of them. Apart from wall-clock fields (`timing`, each run's `wall_s` and `ticks_per_s`,
`workers`) it equals the report of an uninterrupted job.

`--slot-dir DIR --slot-key N` (NX-460, both or neither) make the workers of this job share a pool
of slot files with the other jobs on the host: before a run a worker takes a `DIR/slot-*` (an
exclusive `flock`, freed by the kernel when the process dies) and holds it until the run ends, so
a job widens as another job's slots free up. While a worker waits it holds a shared lock on
`DIR/wait-<N>`; a worker takes no slot while a job with a smaller key has a waiting worker (the
oldest job first). The seconds a run waited are `timing.slot_wait_s` in its JSON (`wall_s` excludes
them). While a run is going, `runs/<profile>-s<seed>.progress` holds `<tick> <total_ticks> <unix
time>`, rewritten about once a minute and removed once the result is written.

Exit 0 on success, 2 on a usage or config error (one line on stderr). Targets that fail do not
change the exit code: the report says it.
"""

import argparse
import fcntl
import functools
import json
import math
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import Executor, ProcessPoolExecutor
from pathlib import Path
from typing import IO, Any

import metrics
import profiles
import report
import runner
import yaml

from nexus.runtime.campaign_config import ConfigPaths, load_campaign_config
from nexus.runtime.config import ConfigError, load_balance

BOOLS = {"true": True, "false": False}


def override_balance(pairs: list[str]) -> str:
    """The shipped balance config as YAML text with `key=value` overrides applied and validated
    by the sim's own loader: a number for a numeric key, `true` or `false` for a boolean one.
    Raises ValueError (bad pair) or ConfigError (schema)."""
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
        if isinstance(old, bool):  # a switch takes `true` or `false` only (NX-412 part 5a)
            if text not in BOOLS:
                raise ValueError(f"--set {key}: {text!r} is not true or false")
            node[leaf] = BOOLS[text]
            continue
        if not isinstance(old, int | float):
            raise ValueError(f"--set {key}: not an existing numeric or boolean balance key")
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


Job = tuple[str, int, float, Path, ConfigPaths | None]


SLOT_POLL_S = 2.0  # how often a waiting worker looks for a free slot
PROGRESS_EVERY_S = 60.0  # at most one progress write per run per this many wall seconds
PROGRESS_CHECK_TICKS = 600  # the clock is read only every this many ticks, to stay cheap
Slots = tuple[Path, int]  # (--slot-dir, --slot-key)


def _lock(path: Path, mode: int) -> IO[str] | None:
    """The open `path` holding an flock of `mode` (LOCK_NB added), or None when it is held."""
    f = path.open("a")
    try:
        fcntl.flock(f, mode | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None
    except BaseException:
        f.close()
        raise
    return f


def _older_waiting(slot_dir: Path, key: int) -> bool:
    """Does a job with a smaller key have a worker waiting? Its waiters hold a shared lock on its
    wait file, so the exclusive probe fails only while one lives: a killed job frees its lock."""
    for path in sorted(slot_dir.glob("wait-*")):
        if path.name[5:].isdigit() and int(path.name[5:]) < key:
            if (probe := _lock(path, fcntl.LOCK_EX)) is None:
                return True
            probe.close()
    return False


def acquire_slot(slot_dir: Path, key: int, poll_s: float = SLOT_POLL_S) -> IO[str]:
    """Wait for a free slot, oldest job first, and return its open file; closing it releases it.
    Wait files are never deleted here (an unlink races with flock); the queue clears stale ones."""
    waiting = (slot_dir / f"wait-{key:09d}").open("a")
    try:
        fcntl.flock(waiting, fcntl.LOCK_SH)
        while True:
            if not _older_waiting(slot_dir, key):
                for path in sorted(slot_dir.glob("slot-*")):
                    if (slot := _lock(path, fcntl.LOCK_EX)) is not None:
                        return slot
            time.sleep(poll_s)
    finally:
        waiting.close()


def _progress(path: Path, total: int) -> Callable[[int, float, Any], bool]:
    """An `on_tick` writing `<tick> <total> <unix time>` to `path` (`.tmp`, then renamed) at most
    once per PROGRESS_EVERY_S. It never stops the run, and a write error never fails it."""
    due = [0.0]

    def on_tick(tick: int, _step_s: float, _world: Any) -> bool:
        if tick % PROGRESS_CHECK_TICKS or (now := time.monotonic()) < due[0]:
            return False
        due[0] = now + PROGRESS_EVERY_S
        tmp = path.with_suffix(".progress.tmp")
        try:
            tmp.write_text(f"{tick} {total} {int(time.time())}\n")
            os.replace(tmp, path)
        except OSError:
            pass
        return False

    return on_tick


def _one(job: Job, slots: Slots | None = None) -> dict[str, Any]:
    """A worker: one (profile, seed) run, its JSON written next to the others. With `slots` it
    first takes a slot (see the module doc) and holds it until the run ends."""
    profile, seed, hours, out, paths = job
    name = f"{profile}-s{seed}"
    shutil.rmtree(out / "logs" / name, ignore_errors=True)  # the leftover of a killed attempt
    progress = out / "runs" / f"{name}.progress"
    held, waited = None, 0.0
    try:
        if slots:
            asked = time.monotonic()
            held = acquire_slot(*slots)
            waited = time.monotonic() - asked  # runner's wall_s starts after this
        config = load_campaign_config(paths)
        total = round(hours * 3600 * config.balance.sim.tick_hz)
        run = runner.run(
            profile, seed, hours, out / "logs" / name, config=config,
            on_tick=_progress(progress, total),
        )  # fmt: skip
    except Exception as e:  # noqa: BLE001  # one run's failure must not kill the batch
        run = runner.failed_run(profile, seed, hours, f"{type(e).__name__}: {e}")
    finally:
        if held:
            held.close()
    run["timing"]["slot_wait_s"] = waited
    final = out / "runs" / f"{name}.json"
    tmp = final.with_suffix(
        ".json.tmp"
    )  # written whole, then renamed: a kill leaves no partial file
    tmp.write_text(json.dumps(run, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, final)
    progress.unlink(missing_ok=True)
    return run


RUN_KEYS = ("ticks_run", "metrics", "timing", "crash", "harness_error", "final_state_hash")


def load_done(job: Job, config_hash: str) -> dict[str, Any] | None:
    """The saved result of `job` when it can be trusted for a resume (NX-433), else None: the file
    must parse, name this profile, seed and hours, carry this config's hash (a harness-error
    stand-in has none, so it is rerun) and have the keys the report reads."""
    profile, seed, hours, out, _ = job
    try:
        run = json.loads((out / "runs" / f"{profile}-s{seed}.json").read_text())
    except (OSError, ValueError):
        return None
    ok = (
        isinstance(run, dict)
        and (run.get("profile"), run.get("seed"), run.get("hours")) == (profile, seed, hours)
        and run.get("config_hash") == config_hash
        and all(k in run for k in RUN_KEYS)
    )
    return run if ok else None


def run_jobs(
    jobs: list[Job],
    cost: Callable[[Job], float],
    workers: int,
    make_pool: Callable[..., Executor] = ProcessPoolExecutor,
    fn: Callable[[Job], dict[str, Any]] = _one,
) -> list[dict[str, Any]]:
    """Run every job and return the results in `jobs` order, whatever finishes first (NX-432).

    Items are submitted most expensive first (`cost`, ties keep job order), one per submit: a
    worker that finishes takes the next waiting item at once (backfill, no fixed chunks), so the
    last item to start is a cheap one and no worker idles while work waits."""
    if workers == 1:
        return [fn(j) for j in jobs]
    order = sorted(range(len(jobs)), key=lambda i: -cost(jobs[i]))  # stable
    with make_pool(max_workers=workers) as pool:
        futures = {i: pool.submit(fn, jobs[i]) for i in order}
    return [futures[i].result() for i in range(len(jobs))]


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
    theater: dict[str, Any] | None = None,
    economy: dict[str, Any] | None = None,
    travel: list[dict[str, Any]] | None = None,
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
            "theater": theater,  # None: the shipped one
            "economy": economy,  # legacy_rules and unlimited per side (EC-15 label)
        },
        "seeds": sorted({r["seed"] for r in runs}),
        "hours": first["hours"],
        "workers": workers,
        "timing": {
            "elapsed_s": elapsed,
            "run_wall_s": sum(r["timing"]["wall_s"] for r in runs),
            "slot_wait_s": sum(r["timing"].get("slot_wait_s", 0.0) for r in runs),  # old runs: 0
        },
        "profiles": aggregated,
        "targets": report.target_table(aggregated),
        "travel": travel or [],
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
    p.add_argument(
        "--hours", type=float, default=None, help="game hours per run (default: the config's limit)"
    )
    p.add_argument("--workers", type=int, default=1, help="parallel processes (default 1)")
    p.add_argument(
        "--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE",
        help="override a numeric or boolean balance key, e.g. economy.legacy_rules=false "
        "(repeatable)",
    )  # fmt: skip
    p.add_argument(
        "--theater", type=Path, help="a theater file to run on instead of the shipped one"
    )
    p.add_argument("--slot-dir", type=Path, help="share the host's slot pool in DIR (--slot-key)")
    p.add_argument("--slot-key", type=int, help="this job's age rank in the pool: lower goes first")
    p.add_argument("--resume", action="store_true", help="keep the valid runs already in --out")
    p.add_argument(
        "--out", type=Path, required=True, help="report directory (must not exist without --resume)"
    )
    return p


def resolve(arg: str, data: profiles.Data) -> list[str]:
    """`--profile`: `all` is every standard profile (never a check profile, `profiles.CHECKS`, so
    default reports stay comparable); else a name or a comma list, each one known."""
    if arg == "all":
        return [n for n in data.profiles if n not in profiles.CHECKS]
    names = arg.split(",")
    if unknown := [n for n in names if n not in data.profiles]:
        raise ValueError(f"unknown profiles {unknown}; known: {list(data.profiles)}")
    return names


def main() -> int:
    args = parser().parse_args()
    data = profiles.load()
    try:
        names = resolve(args.profile, data)
        balance_text = override_balance(args.overrides) if args.overrides else None
        if args.hours is None:  # the (possibly overridden) config's campaign length
            tree = yaml.safe_load(balance_text or ConfigPaths().balance.read_text())
            args.hours = float(tree["campaign"]["time_limit_h"])
        if args.hours <= 0 or args.workers < 1:
            raise ValueError("--hours must be > 0 and --workers >= 1")
        if (args.slot_dir is None) != (args.slot_key is None):
            raise ValueError("--slot-dir and --slot-key go together")
        slots = None
        if args.slot_dir is not None:
            if args.slot_key < 0 or not any(args.slot_dir.glob("slot-*")):
                raise ValueError("--slot-key must be >= 0 and --slot-dir must hold slot-* files")
            slots = (args.slot_dir, args.slot_key)
        theater = None
        theater_text = args.theater.read_text() if args.theater else None
        if theater_text is not None:  # validate (and cross-check with the balance) before `out`
            with tempfile.TemporaryDirectory() as d:
                bal = ConfigPaths().balance
                if balance_text:
                    (bal := Path(d) / "balance.yaml").write_text(balance_text)
                cfg = load_campaign_config(ConfigPaths(balance=bal, theater=args.theater))
            theater = {
                "slug": cfg.theater.slug,
                "name": cfg.theater.name,
                "nodes": len(cfg.theater.nodes),
                "landing_bases": len(cfg.rules.landing_nodes),
            }
        args.out.mkdir(parents=True, exist_ok=args.resume)
        (args.out / "runs").mkdir(exist_ok=args.resume)
        paths = None
        if balance_text or theater_text is not None:
            kw: dict[str, Path] = {}
            if balance_text:
                kw["balance"] = args.out / "balance.yaml"
                kw["balance"].write_text(balance_text)
            if theater_text is not None:
                # the loader wants the slug to be the file name, so keep the original file name;
                # a subdirectory keeps it clear of balance.yaml, report.*, runs/ and logs/
                (args.out / "theater").mkdir(exist_ok=args.resume)
                kw["theater"] = args.out / "theater" / args.theater.name
                kw["theater"].write_text(theater_text)
            paths = ConfigPaths(**kw)
        cfg = load_campaign_config(paths)
        eco = cfg.balance.economy
        economy = {"legacy_rules": eco.legacy_rules, "unlimited": eco.unlimited.model_dump()}
        travel = metrics.travel_table(cfg.rules, cfg.balance.sim.tick_hz)
        jobs = [(n, s, args.hours, args.out, paths) for n in names for s in args.seeds]
        started = time.perf_counter()
        kept = {}  # job index -> the saved run a resume keeps
        for i, j in enumerate(jobs if args.resume else []):
            if (done := load_done(j, cfg.config_hash)) is not None:
                kept[i] = done
        todo = [j for i, j in enumerate(jobs) if i not in kept]
        fn = functools.partial(_one, slots=slots) if slots else _one
        fresh = iter(run_jobs(todo, lambda j: data.profiles[j[0]].viewers, args.workers, fn=fn))
        runs = [kept[i] if i in kept else next(fresh) for i in range(len(jobs))]
        if kept:
            print(f"resume: kept {len(kept)} of {len(jobs)} runs", file=sys.stderr)
        elapsed = time.perf_counter() - started
        result = build_report(
            runs, data, args.workers, elapsed, args.overrides, theater, economy, travel
        )
    except (ValueError, OSError, ConfigError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    (args.out / "report.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (args.out / "report.md").write_text(report.markdown(result))
    print(report.markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
