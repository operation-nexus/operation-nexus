"""Local balance-harness run queue (NX-381, Q-OPS-14).

  uv run --project services/sim python tools/balance/harness_queue.py run-once [--dry-run]

Open issues labelled `harness-run` by a trusted author carry a ```harness block (sha, profiles,
seeds, hours, optional workers). Each is run with balance.py at that commit in a throwaway
worktree, and the report goes back as an issue comment. Issue text is hostile input: it is parsed
with strict rules, never reaches a shell, and refusals quote key names only. This file is not
called queue.py because tools/balance is sys.path[0] for balance.py, and a sibling queue.py would
shadow the standard library's `queue` (which concurrent.futures imports).
"""

import argparse
import contextlib
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import profiles
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BLOCK = re.compile(r"^```harness[ \t]*\r?\n(.*?)^```[ \t]*\r?$", re.DOTALL | re.MULTILINE)
LINE = re.compile(r"([a-z_]+): ([^\r\n]+)")
OVERRIDE = re.compile(r"[a-z0-9_]+(\.[a-z0-9_]+)*=-?\d{1,9}(\.\d{1,9})?")
KEYS = ("sha", "profiles", "seeds", "hours", "workers", "set")
COMMENT_MAX = 60000  # GitHub's limit is 65536 characters; leave room for the framing
FOOTER = "_Posted by the local harness queue (NX-381)_"


class QueueError(Exception):
    """An environment problem (gh or git missing or failing): stop with one line."""


class JobTimeout(Exception):
    """A child ran past job_timeout_hours; its process group has been killed."""


class Refusal(Exception):
    """A request that must not run; the text is fixed wording plus key names only."""


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}", flush=True)


# gh and git calls get this long; a hung one must not hold the lock for good. Long steps pass
# their own timeout from job_timeout_hours.
SHORT_TIMEOUT_S = 900


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    stdin: str | None = None,
    timeout: float | None = SHORT_TIMEOUT_S,
    logfile: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """The one subprocess boundary: argument lists only, never a shell.

    The child gets its own session; on a timeout the whole process group is killed (so the
    balance workers die too and the lock frees) and JobTimeout is raised. With `logfile`, stdout
    and stderr are appended to it instead of captured."""
    try:
        with logfile.open("a") if logfile else open(os.devnull) as f:
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE if stdin is not None else None,
                stdout=f if logfile else subprocess.PIPE,
                stderr=subprocess.STDOUT if logfile else subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                out, err = proc.communicate(stdin, timeout=timeout)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(proc.pid, signal.SIGKILL)  # it may have exited meanwhile
                proc.communicate()
                raise JobTimeout from None
    except FileNotFoundError:
        raise QueueError(f"{cmd[0]} not found on PATH") from None
    return subprocess.CompletedProcess(cmd, proc.returncode, out or "", err or "")


def load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    for key in ("work_dir", "results_dir"):
        cfg[key] = Path(cfg[key]).expanduser()
    return dict(cfg)


def parse_block(body: str, cfg: dict[str, Any], known: list[str]) -> dict[str, Any]:
    """The first ```harness block as validated values. Raises Refusal."""
    m = BLOCK.search(body or "")
    if not m:
        raise Refusal("no harness block")
    raw: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        kv = LINE.fullmatch(line.strip())
        if not kv or kv.group(1) not in KEYS:
            raise Refusal("unknown or malformed line in the harness block")
        if kv.group(1) in raw:
            raise Refusal(f"duplicate key: {kv.group(1)}")
        raw[kv.group(1)] = kv.group(2).strip()
    if missing := [k for k in ("sha", "profiles", "seeds", "hours") if k not in raw]:
        raise Refusal(f"missing keys: {', '.join(missing)}")

    def bounded_int(key: str, hi: int) -> int:
        if not re.fullmatch(r"\d{1,6}", raw[key]) or not 1 <= int(raw[key]) <= hi:
            raise Refusal(f"bad value for key: {key}")
        return int(raw[key])

    if not re.fullmatch(r"[0-9a-f]{40}", raw["sha"]):
        raise Refusal("bad value for key: sha")
    names = list(dict.fromkeys(n.strip() for n in raw["profiles"].split(",")))
    if not all(n in known for n in names) or len(names) > cfg.get("max_profiles", len(known)):
        raise Refusal("bad value for key: profiles")
    if not re.fullmatch(r"\d{1,4}(\.\d{1,4})?", raw["hours"]) or not (
        0 < float(raw["hours"]) <= cfg["max_hours"]
    ):
        raise Refusal("bad value for key: hours")
    overrides = [x.strip() for x in raw["set"].split(",")] if "set" in raw else []
    if len(overrides) > cfg["max_overrides"] or not all(OVERRIDE.fullmatch(o) for o in overrides):
        raise Refusal("bad value for key: set")
    return {
        "sha": raw["sha"],
        "profiles": names,
        "seeds": bounded_int("seeds", cfg["max_seeds"]),
        "hours": float(raw["hours"]),
        "workers": bounded_int("workers", cfg["max_workers"])
        if "workers" in raw
        else cfg["workers"],
        "set": overrides,
    }


def gh(cfg: dict[str, Any], *args: str, stdin: str | None = None) -> str:
    r = run_cmd(["gh", *args, "-R", cfg["repo"]], stdin=stdin)
    if r.returncode:
        raise QueueError(f"gh {args[0]} {args[1]} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def eligible(cfg: dict[str, Any], label: str | None = None) -> list[dict[str, Any]]:
    """Open issues with `label` (default: the run label) by a trusted author, oldest first."""
    label = label or cfg["labels"]["run"]
    fields = "number,title,body,author,labels,createdAt"
    out = gh(cfg, "issue", "list", "--state", "open", "--label", label,
             "--limit", "100", "--json", fields)  # fmt: skip
    trusted = {a.lower() for a in cfg["trusted_authors"]}
    issues = [
        i
        for i in json.loads(out)
        if (i.get("author") or {}).get("login", "").lower() in trusted
        and label in [lb["name"] for lb in i["labels"]]
    ]
    return sorted(issues, key=lambda i: (i["createdAt"], i["number"]))


def relabel(cfg: dict[str, Any], number: int, add: str, remove: str) -> None:
    gh(cfg, "issue", "edit", str(number), "--add-label", add, "--remove-label", remove)


def comment(cfg: dict[str, Any], number: int, text: str) -> None:
    gh(cfg, "issue", "comment", str(number), "--body-file", "-", stdin=f"{text}\n\n{FOOTER}\n")


def on_develop(sha: str) -> bool:
    if run_cmd(["git", "fetch", "origin", "develop"], cwd=REPO_ROOT).returncode:
        raise QueueError("git fetch origin develop failed")
    r = run_cmd(["git", "merge-base", "--is-ancestor", sha, "origin/develop"], cwd=REPO_ROOT)
    return r.returncode == 0


def shown(path: Path) -> str:
    """A path for a comment: under the home directory it starts with ~, never the absolute home."""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)


def truncate(text: str, full: Path) -> str:
    if len(text) <= COMMENT_MAX:
        return text
    note = f"\n\n_Truncated; the full text is at `{shown(full)}` on the harness PC._"
    return text[: COMMENT_MAX - len(note)] + note


def tail(path: Path, n: int = 40) -> str:
    lines = path.read_text(errors="replace").splitlines()[-n:]
    text = "\n".join(line[:300] for line in lines).replace(str(Path.home()), "~")
    return truncate(text.replace("`" * 3, "'" * 3), path)


def execute(cfg: dict[str, Any], number: int, req: dict[str, Any]) -> tuple[int, Path, Path]:
    """Run the request in a throwaway worktree. Returns (exit code, results dir, log file).
    Raises JobTimeout when a step runs past job_timeout_hours."""
    tag = f"{number}-{req['sha'][:8]}"
    out, logfile = cfg["results_dir"] / tag, cfg["results_dir"] / f"{tag}.log"
    wt = cfg["work_dir"] / f"wt-{tag}"
    cfg["results_dir"].mkdir(parents=True, exist_ok=True)
    balance = [
        "uv", "run", "--frozen", "python", "../../tools/balance/balance.py",
        "--profile", ",".join(req["profiles"]), "--seeds", str(req["seeds"]),
        "--hours", str(req["hours"]), "--workers", str(req["workers"]), "--out", str(out),
        *[x for o in req["set"] for x in ("--set", o)],
    ]  # fmt: skip
    limit = cfg["job_timeout_hours"] * 3600
    try:
        logfile.write_text("")
        rc = run_cmd(
            ["git", "worktree", "add", "--detach", str(wt), req["sha"]],
            cwd=REPO_ROOT,
            logfile=logfile,
        ).returncode
        for cmd in [["uv", "sync", "--frozen"], balance] if rc == 0 else []:
            rc = run_cmd(
                cmd, cwd=wt / "services" / "sim", timeout=limit, logfile=logfile
            ).returncode
            if rc:
                break
        return rc, out, logfile
    finally:
        run_cmd(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO_ROOT)
        run_cmd(["git", "worktree", "prune"], cwd=REPO_ROOT)


def process(cfg: dict[str, Any], issue: dict[str, Any], dry: bool) -> None:
    n, labels = issue["number"], cfg["labels"]
    try:
        req = parse_block(issue["body"], cfg, list(profiles.load().profiles))
        if not on_develop(req["sha"]):
            raise Refusal("the sha is not reachable from origin/develop")
    except Refusal as e:
        log(f"#{n}: refused: {e}")
        if not dry:
            relabel(cfg, n, labels["failed"], labels["run"])
            comment(cfg, n, f"Refused: {e}.")
        return
    if dry:
        log(f"#{n}: would run {req}")
        return
    relabel(cfg, n, labels["running"], labels["run"])
    started = time.monotonic()
    log(f"#{n}: running {req}")
    try:
        try:
            rc, out, logfile = execute(cfg, n, req)
        except JobTimeout:
            fail(cfg, n, f"Run timed out after {cfg['job_timeout_hours']} h.")
            return
        wall = f"{(time.monotonic() - started) / 60:.1f} min"
        report = out / "report.md"
        if rc == 0 and report.exists():
            body = truncate(report.read_text(), report)
            sets = f" Overrides: `{' '.join(req['set'])}`." if req["set"] else ""
            comment(cfg, n, f"Run finished in {wall}.{sets} Results: `{shown(out)}`\n\n{body}")
            relabel(
                cfg, n, labels["done"], labels["running"]
            )  # last, so a failure here can't leave both labels
        else:
            fail(
                cfg,
                n,
                f"Run failed (exit code {rc}) after {wall}. Log: `{shown(logfile)}`\n\n"
                f"```\n{tail(logfile)}\n```",
            )
        log(f"#{n}: exit code {rc} after {wall}")
    except Exception as e:  # noqa: BLE001  # never leave the issue in `running`
        log(f"#{n}: error {type(e).__name__}: {e}")  # local log only; the comment stays type-only
        fail(cfg, n, f"Run failed: internal error ({type(e).__name__}).")


def fail(cfg: dict[str, Any], number: int, text: str) -> None:
    """Relabel running -> failed and comment; if gh fails here, log it and let the tick go on."""
    try:
        relabel(cfg, number, cfg["labels"]["failed"], cfg["labels"]["running"])
        comment(cfg, number, text)
    except QueueError as e:
        log(f"#{number}: could not report the failure: {e}")


def recover_stale(cfg: dict[str, Any]) -> None:
    """We hold the lock, so no job of ours runs: an issue still `running` was cut off."""
    for issue in eligible(cfg, cfg["labels"]["running"]):
        log(f"#{issue['number']}: stale running label")
        fail(cfg, issue["number"], "Failed: the runner restarted mid-job.")


def run_once(cfg: dict[str, Any], dry: bool) -> int:
    cfg["work_dir"].mkdir(parents=True, exist_ok=True)
    with (cfg["work_dir"] / "queue.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another queue run holds the lock; exiting")
            return 0
        if not dry:
            recover_stale(cfg)
        issues = eligible(cfg)
        log(f"{len(issues)} eligible issue(s)")
        for issue in issues:
            try:
                process(cfg, issue, dry)
            except Exception as e:  # noqa: BLE001  # one issue's failure must not stop the tick
                log(f"#{issue['number']}: skipped after {type(e).__name__}: {e}")  # local log only
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Local balance-harness run queue (NX-381)")
    p.add_argument("command", choices=["run-once"])
    p.add_argument(
        "--dry-run", action="store_true", help="parse and validate; comment and run nothing"
    )
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("queue.yaml"))
    args = p.parse_args(argv)
    try:
        return run_once(load_config(args.config), args.dry_run)
    except QueueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
