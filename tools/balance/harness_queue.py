"""Local balance-harness run queue (NX-381, Q-OPS-14).

  uv run --project services/sim python tools/balance/harness_queue.py run-once [--dry-run]

Open issues labelled `harness-run` by a trusted author carry a ```harness block (sha, profiles,
seeds, hours, optional workers). Each is run with balance.py at that commit in a throwaway
worktree, and the report goes back as an issue comment. Jobs overlap on one worker budget of slot
files (NX-442, NX-460): see `Jobs`. Issue text is hostile input: it is parsed
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
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

import profiles
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BLOCK = re.compile(r"^```harness[ \t]*\r?\n(.*?)^```[ \t]*\r?$", re.DOTALL | re.MULTILINE)
LINE = re.compile(r"([a-z_]+): ([^\r\n]+)")
# key=value: a lower-case first segment, later ones may be an upper-case enum value (a side, a unit
# kind); the value a bounded number, a lower-case bool literal or one short word for an enum key
# (NX-498), never free text: a word spelling a bool or null in any case (True, yes, on) is refused
# and balance.py checks the word against the key's schema
OVERRIDE = re.compile(
    r"[a-z0-9_]+(\.[A-Za-z0-9_]+)*="
    r"(-?\d{1,9}(\.\d{1,9})?|true|false|(?!(?i:true|false|yes|no|on|off|y|n|null)$)[A-Za-z][A-Za-z0-9_]{0,31})"
)
KEYS = ("sha", "profiles", "seeds", "hours", "workers", "set")
COMMENT_MAX = 60000  # GitHub's limit is 65536 characters; leave room for the framing
FINISHED = "finished"  # written by the queue once balance.py exited 0 with report.md: its size
POSTED = "posted"  # written once the report comment is on the issue (no double post on retry)
MAX_RESUMES = 2  # a stale job is continued this many times; a job that crashes again is failed
FOOTER = "_Posted by the local harness queue (NX-381)_"
MAX_BALANCE_PY = 1 << 20  # a larger balance.py at a sha is not read: that sha is legacy
SLOTS = "slots"  # work_dir/slots/: slot-00 .. slot-<max_workers-1> and the jobs' wait-* files
POLL_S = 300  # how often a tick with running jobs recounts their result files and relists issues
GIT_LOCK = threading.Lock()  # worktree add, remove, prune and merge-base: one at a time


class QueueError(Exception):
    """An environment problem (gh or git missing or failing): stop with one line."""


class JobTimeout(Exception):
    """A child ran past job_timeout_hours; its process group has been killed."""


class Refusal(Exception):
    """A request that must not run; the text is fixed wording plus key names only."""


LOG_LOCK = threading.Lock()  # job threads log too (NX-442): one whole line at a time


def log(msg: str) -> None:
    with LOG_LOCK:
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
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    """The one subprocess boundary: argument lists only, never a shell.

    The child gets its own session; on a timeout the whole process group is killed (so the
    balance workers die too and the lock frees) and JobTimeout is raised. With `logfile`, stdout
    and stderr are appended to it instead of captured. `text=False` returns stdout as bytes."""
    try:
        with logfile.open("a") if logfile else open(os.devnull) as f:
            proc = subprocess.Popen(  # noqa: S603
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE if stdin is not None else None,
                stdout=f if logfile else subprocess.PIPE,
                stderr=subprocess.STDOUT if logfile else subprocess.PIPE,
                text=text,
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
    empty = "" if text else b""
    return subprocess.CompletedProcess(cmd, proc.returncode, out or empty, err or empty)


def load_config(path: Path) -> dict[str, Any]:
    cfg = yaml.safe_load(path.read_text())
    for key in ("work_dir", "results_dir"):
        cfg[key] = Path(cfg[key]).expanduser()
    v = cfg.get("min_overlap_workers")
    if type(v) is not int or not 1 <= v <= cfg["max_workers"]:  # not a bool, not a string
        raise QueueError("queue.yaml: min_overlap_workers must be an integer from 1 to max_workers")
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
    return str(r.stdout)


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


def check_write(cfg: dict[str, Any], number: int, label: str) -> bool:
    """Prove the token can write to the issue before a long run. The cheapest real write is a
    label edit that adds a label the issue already has (`label`: the run label at pickup, the
    running label on a resume, so a resume never re-adds `harness-run`): a mutation that needs
    Issues write, changes no label and leaves no comment or event. A read-only or unapproved
    token fails it. Logs a fixed line only: no token, no gh output, no issue text."""
    try:
        gh(cfg, "issue", "edit", str(number), "--add-label", label)
    except QueueError:
        log(f"#{number}: the gh token cannot write to the issue; not started, labels unchanged")
        return False
    return True


def running_file(cfg: dict[str, Any], number: int) -> Path:
    """Local record of the sha a run started with; recovery trusts it, not the editable issue."""
    return Path(cfg["results_dir"]) / f"{number}.running"


def request_file(cfg: dict[str, Any], number: int) -> Path:
    """The validated request a run started with, so a resume never reads the editable issue."""
    return Path(cfg["results_dir"]) / f"{number}.request"


def resumes_file(cfg: dict[str, Any], number: int) -> Path:
    return Path(cfg["results_dir"]) / f"{number}.resumes"


def forget(cfg: dict[str, Any], number: int) -> None:
    """The issue is posted or failed: drop its local records."""
    for f in (running_file(cfg, number), request_file(cfg, number), resumes_file(cfg, number)):
        f.unlink(missing_ok=True)


def finished(out: Path) -> bool:
    """A run is finished only when its marker (written after the run, never a partial file)
    names the size of the report on disk."""
    try:
        return int((out / FINISHED).read_text()) == (out / "report.md").stat().st_size
    except (OSError, ValueError):
        return False


def sha_note(body: str | None, ran: str) -> str:
    """Empty when the issue body still names the sha that ran; else a plain line saying it was
    edited after queueing (L-30). Only a 40-hex value from the body is ever echoed."""
    m = BLOCK.search(body or "")
    lines = [LINE.fullmatch(x.strip()) for x in m.group(1).splitlines()] if m else []
    shas = [kv.group(2).strip() for kv in lines if kv and kv.group(1) == "sha"]
    now = shas[0] if len(shas) == 1 else ""  # missing or duplicated: as parse_block, no value
    if now == ran:
        return ""
    shown_now = f"`{now}`" if re.fullmatch(r"[0-9a-f]{40}", now) else "(none valid or unreadable)"
    return f"**Body sha {shown_now} was edited after queueing; this run used `{ran}`.**\n\n"


def publish(cfg: dict[str, Any], number: int, out: Path, head: str, ran: str, body: str) -> None:
    """Post the harness-written report, then swap running -> done (last, so a failure here
    can't leave both labels). Safe to retry: the comment is posted once. `ran` is the sha the
    queue recorded at start; `body` the issue body as read now."""
    report = out / "report.md"
    if not (out / POSTED).exists():
        text = f"{head} Sha that ran (recorded at start): `{ran}`. Results: `{shown(out)}`"
        comment(
            cfg, number, f"{text}\n\n{sha_note(body, ran)}{truncate(report.read_text(), report)}"
        )
        try:
            (out / POSTED).touch()
        except OSError:  # posted but unrecorded: leave it running; a repost is the accepted risk
            log(f"#{number}: posted but could not record it; left running")
            return
    relabel(cfg, number, cfg["labels"]["done"], cfg["labels"]["running"])
    forget(cfg, number)


def on_develop(sha: str) -> bool:
    if run_cmd(["git", "fetch", "origin", "develop"], cwd=REPO_ROOT).returncode:
        raise QueueError("git fetch origin develop failed")
    with GIT_LOCK:
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


def execute(
    cfg: dict[str, Any], number: int, req: dict[str, Any], resume: bool = False
) -> tuple[int, Path, Path]:
    """Run the request in a throwaway worktree. Returns (exit code, results dir, log file).
    With `resume`, balance.py keeps the runs already in the results dir (NX-433) and the log is
    appended to. Raises JobTimeout when a step runs past job_timeout_hours."""
    tag = f"{number}-{req['sha'][:8]}"
    out, logfile = cfg["results_dir"] / tag, cfg["results_dir"] / f"{tag}.log"
    wt = cfg["work_dir"] / f"wt-{tag}"
    cfg["results_dir"].mkdir(parents=True, exist_ok=True)
    slots = cfg["work_dir"] / SLOTS  # an elastic job's workers take slots there themselves
    balance = [
        "uv", "run", "--frozen", "python", "../../tools/balance/balance.py",
        "--profile", ",".join(req["profiles"]), "--seeds", str(req["seeds"]),
        "--hours", str(req["hours"]), "--workers", str(req["workers"]), "--out", str(out),
        *[x for o in req["set"] for x in ("--set", o)],
        *(["--slot-dir", str(slots), "--slot-key", str(number)] if req.get("elastic") else []),
        *(["--resume"] if resume else []),
    ]  # fmt: skip
    limit = cfg["job_timeout_hours"] * 3600
    try:
        with GIT_LOCK:
            if resume:  # the killed attempt's worktree may still be registered
                run_cmd(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO_ROOT)
                run_cmd(["git", "worktree", "prune"], cwd=REPO_ROOT)
            else:
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
        with GIT_LOCK:
            run_cmd(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO_ROOT)
            run_cmd(["git", "worktree", "prune"], cwd=REPO_ROOT)


def runs_left(out: Path, total: int) -> int:
    """Runs of a job with no result file yet (NX-442): balance.py writes `runs/<name>.json` whole
    (a `.tmp` renamed into place), so counting them needs no IPC. On a resume, balance.py deletes
    a file it will run again (another config, a harness-error stand-in) before any run starts
    (NX-460); a legacy sha's balance.py does not, so there such a file counts as done until
    replaced."""
    return max(total - sum(1 for _ in (out / "runs").glob("*.json")), 0)


def lockable(path: Path) -> bool:
    """Can `path` be flocked exclusively right now? (Closing the probe releases it.)"""
    with path.open("a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
    return True


def sync_slots(cfg: dict[str, Any]) -> None:
    """Called holding the queue lock: work_dir/slots holds exactly slot-00 .. slot-<max_workers-1>
    and no wait-* file nobody waits on (balance.py never unlinks them: that races with flock)."""
    d = cfg["work_dir"] / SLOTS
    d.mkdir(parents=True, exist_ok=True)
    want = {f"slot-{i:02d}" for i in range(cfg["max_workers"])}
    for name in want:
        (d / name).touch()
    for extra in [p for p in d.glob("slot-*") if p.name not in want]:
        extra.unlink()
    for stale in [p for p in d.glob("wait-*") if lockable(p)]:
        stale.unlink()


@dataclass
class Job:
    n: int
    workers: int
    total: int  # profiles x seeds
    out: Path
    elastic: bool = False  # balance.py takes slots itself; else the queue holds them for it
    held: list[IO[str]] = field(default_factory=list)  # a legacy job's slots, held by the queue
    done: bool = False  # set by the job's thread when `launch` returns or raises
    error: BaseException | None = None  # a kill stand-in (not an Exception) that ended the thread
    thread: threading.Thread = field(init=False)


class Jobs:
    """The jobs one tick runs at once (NX-442, Q-DEV-33, NX-460). Each is one thread running
    `launch` (its own worktree, results dir, report and labels; the work is its balance.py
    subprocess). They share `max_workers` slot files as one budget.

    The start rule counts demand, not locks: a running job demands min(its workers, its runs
    left) of the budget, and `free` is `max_workers` minus the sum. An elastic job (its sha's
    balance.py knows `--slot-dir`) starts when `free` >= 1, with the workers it asked for; its
    workers take slots themselves, run by run, oldest job first, so it widens as older jobs' tails
    free slots. A legacy job (an older sha) starts once min(w, `min_overlap_workers`) are free
    while another job runs (any count when none runs), with min(w, free) workers kept to the end;
    the queue holds slot locks for it, non-blocking: as many as it gets at the start (elastic
    workers may still hold some), topped up on each recount to min(workers, runs left), released
    down as runs finish."""

    def __init__(self, cfg: dict[str, Any], sync: bool = True) -> None:
        self.cfg = cfg
        self.running: list[Job] = []
        self.started: set[int] = set()  # issue numbers started this tick
        self.crash: BaseException | None = None  # the first job error; run_once re-raises it
        self.changed = threading.Event()
        self.kinds: dict[str, bool] = {}  # sha -> elastic
        if sync:  # a Jobs is made holding the queue lock, at the start of a tick; not for
            sync_slots(cfg)  # --dry-run, which creates nothing

    def elastic(self, sha: str) -> bool:
        """Does `sha`'s balance.py know `--slot-dir`? Read from git, no checkout; `sha` is the
        validated 40-hex value and the bytes are only searched, never run or echoed. Any failure
        (git, a missing file, a size over MAX_BALANCE_PY, anything raised) answers legacy for this
        call only: it is not cached, so a later call retries."""
        if sha in self.kinds:
            return self.kinds[sha]
        spec = f"{sha}:tools/balance/balance.py"
        try:
            size = run_cmd(["git", "cat-file", "-s", spec], cwd=REPO_ROOT)
            if size.returncode or not size.stdout.strip().isdigit():
                return False
            if int(size.stdout) > MAX_BALANCE_PY:
                return False
            blob = run_cmd(["git", "cat-file", "blob", spec], cwd=REPO_ROOT, text=False)
            if blob.returncode:
                return False
        except Exception as e:  # noqa: BLE001  # never crash a tick over detection
            log(f"elastic check failed ({type(e).__name__}); treating {sha[:8]} as legacy")
            return False
        self.kinds[sha] = b"--slot-dir" in blob.stdout
        return self.kinds[sha]

    def free(self) -> int:
        """Budget not demanded by running jobs (see the class doc). Also settles the slot locks
        the queue holds for legacy jobs: topped up, or released down, to their demand."""
        self.reap()
        for j in self.running:
            want = min(j.workers, runs_left(j.out, j.total))
            if not j.elastic:
                while len(j.held) > want:
                    j.held.pop().close()
                if len(j.held) < want:
                    j.held += self.take(want - len(j.held))
        demand = sum(min(j.workers, runs_left(j.out, j.total)) for j in self.running)
        return int(self.cfg["max_workers"]) - demand

    def fits(self, req: dict[str, Any]) -> bool:
        need = 1
        if self.running and not self.elastic(req["sha"]):
            need = min(req["workers"], int(self.cfg["min_overlap_workers"]))
        return self.free() >= need

    def wait(self) -> bool:
        """Until a job ends or POLL_S passes; True when POLL_S passed. A job sets `done` before
        `changed`, and `reap` reads `done` after the clear, so an end is never missed."""
        timed_out = not self.changed.wait(POLL_S)
        self.changed.clear()
        self.reap()
        return timed_out

    def take(self, workers: int) -> list[IO[str]]:
        """Up to `workers` free slots, locked by the queue itself."""
        held: list[IO[str]] = []
        for path in sorted((self.cfg["work_dir"] / SLOTS).glob("slot-*")):
            if len(held) == workers:
                break
            f = path.open("a")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held.append(f)
            except BlockingIOError:
                f.close()
        return held

    def start(self, n: int, req: dict[str, Any], resume: bool) -> None:
        elastic = self.elastic(req["sha"])
        while not self.fits(req):
            self.wait()
        workers = req["workers"] if elastic else min(req["workers"], self.free())
        req = {**req, "workers": workers, "elastic": elastic}
        held = [] if elastic else self.take(workers)
        out = self.cfg["results_dir"] / f"{n}-{req['sha'][:8]}"
        job = Job(n, workers, len(req["profiles"]) * req["seeds"], out, elastic, held)
        job.thread = threading.Thread(target=self._run, args=(job, req, resume), daemon=True)
        self.running.append(job)
        self.started.add(n)
        kind = "elastic" if elastic else "legacy"
        log(f"#{n}: started on {job.workers} of {self.cfg['max_workers']} workers ({kind})")
        job.thread.start()

    def _run(self, job: Job, req: dict[str, Any], resume: bool) -> None:
        try:
            launch(self.cfg, job.n, req, resume)
        except Exception as e:  # noqa: BLE001  # a slip in launch's own handling: never leave `running`
            log(f"#{job.n}: error {type(e).__name__}: {e}")  # local log only
            if running_file(self.cfg, job.n).exists():  # not posted or failed yet
                fail(self.cfg, job.n, f"Run failed: internal error ({type(e).__name__}).")
        except BaseException as e:  # noqa: BLE001  # a kill stand-in: left `running` for recovery
            job.error = e
        finally:
            job.done = True
            self.changed.set()

    def reap(self) -> None:
        """Drop ended jobs. A job's error is logged and kept for run_once; the others go on."""
        for job in [j for j in self.running if j.done]:
            job.thread.join()
            self.running.remove(job)
            for f in job.held:
                f.close()
            if job.error is not None:
                log(f"#{job.n}: ended by {type(job.error).__name__}; left running for recovery")
                self.crash = self.crash or job.error

    def join(self) -> None:
        """Wait for every running job: the lock is never freed while one of them runs."""
        for job in list(self.running):
            job.thread.join()
        self.reap()


def process(cfg: dict[str, Any], jobs: Jobs, issue: dict[str, Any], dry: bool) -> bool:
    """Refuse, skip or start one `harness-run` issue. False (nothing done, no label changed)
    when its request does not fit the free workers yet."""
    n, labels = issue["number"], cfg["labels"]
    try:
        req = parse_block(issue["body"], cfg, list(profiles.load().profiles))
        if not on_develop(req["sha"]):  # before fits: that reads the sha's files from git
            raise Refusal("the sha is not reachable from origin/develop")
        if not jobs.fits(req):
            return False
        if (cfg["results_dir"] / f"{n}-{req['sha'][:8]}").exists():
            # balance.py never reuses a results dir, and recovery must not take an old
            # attempt's finished report for this one: one run per issue and sha
            raise Refusal("this issue already ran this sha; open a new issue to run it again")
    except Refusal as e:
        log(f"#{n}: refused: {e}")
        if not dry:
            relabel(cfg, n, labels["failed"], labels["run"])
            comment(cfg, n, f"Refused: {e}.")
        return True
    if dry:
        log(f"#{n}: would run {req}")
        return True
    if not check_write(cfg, n, labels["run"]):
        return True
    cfg["results_dir"].mkdir(parents=True, exist_ok=True)
    running_file(cfg, n).write_text(req["sha"])
    request_file(cfg, n).write_text(json.dumps(req))
    relabel(cfg, n, labels["running"], labels["run"])
    log(f"#{n}: running {req}")
    jobs.start(n, req, False)
    return True


def launch(cfg: dict[str, Any], n: int, req: dict[str, Any], resume: bool) -> None:
    """Run a request that is already `harness-running` and publish or fail it."""
    started = time.monotonic()
    try:
        try:
            rc, out, logfile = execute(cfg, n, req, resume)
        except JobTimeout:
            fail(cfg, n, f"Run timed out after {cfg['job_timeout_hours']} h.")
            return
        wall = f"{(time.monotonic() - started) / 60:.1f} min"
        report = out / "report.md"
        if rc == 0 and report.exists():
            report.write_text(f"Sha that ran (recorded by the queue at start): `{req['sha']}`\n\n"
                              + report.read_text())  # fmt: skip
            (out / FINISHED).write_text(str(report.stat().st_size))
            sets = f" Overrides: `{' '.join(req['set'])}`." if req["set"] else ""
            try:
                head = f"Run finished in {wall}{' (resumed)' if resume else ''}.{sets}"
                publish(cfg, n, out, head, req["sha"], current_body(cfg, n))
            except (
                QueueError,
                JobTimeout,
                OSError,
            ):  # the report is safe on disk; next tick's recovery posts it
                log(f"#{n}: finished but not posted, kept at {shown(out)}")
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


def current_body(cfg: dict[str, Any], number: int) -> str:
    """The issue body as it is now (the copy `process` holds is from before the run)."""
    try:
        return str(json.loads(gh(cfg, "issue", "view", str(number), "--json", "body"))["body"])
    except (QueueError, ValueError, KeyError, TypeError):
        return ""  # unreadable: sha_note then reports it as edited, which is the safe flag


def fail(cfg: dict[str, Any], number: int, text: str) -> None:
    """Relabel running -> failed and comment; if gh or the disk fails here, log it and let the
    tick go on (it runs inside launch's last-resort handler, so it must not raise)."""
    try:
        relabel(cfg, number, cfg["labels"]["failed"], cfg["labels"]["running"])
        comment(cfg, number, text)
    except (QueueError, JobTimeout) as e:
        log(f"#{number}: could not report the failure: {type(e).__name__} {e}")
    try:
        forget(cfg, number)
    except OSError as e:
        log(f"#{number}: could not drop the local records: {e}")


def render_block(req: dict[str, Any]) -> str:
    lines = [
        f"sha: {req['sha']}",
        f"profiles: {','.join(req['profiles'])}",
        f"seeds: {req['seeds']}",
        f"hours: {req['hours']}",
        f"workers: {req['workers']}",
    ]
    if req["set"]:
        lines.append(f"set: {','.join(req['set'])}")
    return "```harness\n" + "\n".join(lines) + "\n```\n"


def resumable(
    cfg: dict[str, Any], n: int, sha: str, out: Path
) -> tuple[dict[str, Any], int] | None:
    """Can a cut-off job be continued (NX-433)? (the request, earlier resumes), or None when the
    caller should fail it. Needs the results dir, the request the queue recorded (parsed again by
    parse_block; the issue body is never read) naming the recorded sha, and fewer than
    MAX_RESUMES earlier resumes. A resume is the same run, so the one-run-per-sha refusal in
    `process` does not apply; it only guards new requests."""
    try:
        tries = int(resumes_file(cfg, n).read_text()) if resumes_file(cfg, n).exists() else 0
        req = parse_block(
            render_block(json.loads(request_file(cfg, n).read_text())),
            cfg,
            list(profiles.load().profiles),
        )
    except (OSError, ValueError, KeyError, TypeError, Refusal):
        return None
    if not out.is_dir() or req["sha"] != sha or tries >= MAX_RESUMES:
        return None
    return req, tries


def recover_stale(cfg: dict[str, Any], jobs: Jobs) -> None:
    """Called first in a tick, holding the lock, so no job of ours runs: an issue still `running`
    was cut off, or its finished report could not be posted. Pass 1 posts finished reports and
    fails what cannot resume; pass 2 starts the resumes (each its own job on `jobs`, NX-442), so
    a resume waiting for workers holds up no post or failure."""
    resumes: list[tuple[int, dict[str, Any], int]] = []
    for issue in eligible(cfg, cfg["labels"]["running"]):
        n = issue["number"]
        log(f"#{n}: stale running label")
        out = None
        try:  # the path comes from the int issue number and the recorded, re-validated sha
            sha = running_file(cfg, n).read_text().strip()
            if re.fullmatch(r"[0-9a-f]{40}", sha):
                out = cfg["results_dir"] / f"{n}-{sha[:8]}"
        except OSError:
            pass
        if out is not None and finished(out):
            try:
                late = "Run finished; the report was posted late."
                publish(cfg, n, out, late, sha, current_body(cfg, n))
                log(f"#{n}: recovered the finished report")
            except (QueueError, JobTimeout, OSError):
                log(f"#{n}: recovered report not posted, will retry")
            continue
        if out is not None and (found := resumable(cfg, n, sha, out)) is not None:
            resumes.append((n, *found))
            continue
        fail(cfg, n, "Failed: the runner restarted mid-job.")
    for n, req, tries in resumes:
        if not check_write(cfg, n, cfg["labels"]["running"]):
            continue  # leave it running; the next tick tries again, no attempt used
        resumes_file(cfg, n).write_text(str(tries + 1))
        log(f"#{n}: resuming (attempt {tries + 1} of {MAX_RESUMES})")
        jobs.start(n, req, True)


def run_once(cfg: dict[str, Any], dry: bool) -> int:
    cfg["work_dir"].mkdir(parents=True, exist_ok=True)
    with (cfg["work_dir"] / "queue.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another queue run holds the lock; exiting")
            return 0
        jobs = Jobs(cfg, sync=not dry)
        try:
            if not dry:
                recover_stale(cfg, jobs)
            supervise(cfg, jobs, dry)
        finally:
            jobs.join()  # whatever happened, every job of this tick ends before the lock frees
        if jobs.crash is not None:
            raise jobs.crash
    return 0


def supervise(cfg: dict[str, Any], jobs: Jobs, dry: bool) -> None:
    """Start eligible issues, oldest first, whenever the budget allows, until none is left and no
    job runs (NX-442). Issues are relisted while jobs run, so one queued later still overlaps.
    An issue is tried once until POLL_S passes; then one that did not start (a failed fetch or
    write check) is tried again. A job error does not stop the others (run_once re-raises it)."""
    seen: set[int] = set()
    first = True
    while True:
        if jobs.free() >= 1:
            try:
                busy = seen | jobs.started  # a resume started by recovery is not in `seen`
                issues = [i for i in eligible(cfg) if i["number"] not in busy]
            except QueueError as e:
                if first:  # as before NX-442: no list, no tick
                    raise
                log(f"listing issues failed, the running jobs go on: {e}")
                issues = []
            if issues or first:
                log(f"{len(issues)} eligible issue(s)")
            first = False
            for issue in issues:
                try:
                    handled = process(cfg, jobs, issue, dry)
                except Exception as e:  # noqa: BLE001  # one issue's failure must not stop the tick
                    log(f"#{issue['number']}: skipped after {type(e).__name__}: {e}")  # local only
                    handled = True
                if not handled:
                    break  # the oldest waiting request does not fit yet: keep the order
                seen.add(issue["number"])
        if not jobs.running:
            return
        if jobs.wait():
            seen &= jobs.started


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
