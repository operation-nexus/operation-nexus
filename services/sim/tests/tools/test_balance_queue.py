"""Local harness run queue tests (NX-381, Q-OPS-14; tools/balance/harness_queue.py).

`gh` and `git` are faked at the one subprocess boundary (`run_cmd`). The fake `gh issue list`
output uses only fields `gh issue list --json` has: number, title, body, author{login},
labels[{name}] and createdAt.
"""

import fcntl
import importlib.util
import json
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
import yaml

TOOL = Path(__file__).resolve().parents[4] / "tools" / "balance"
sys.path.insert(0, str(TOOL))
_spec = importlib.util.spec_from_file_location("harness_queue", TOOL / "harness_queue.py")
assert _spec and _spec.loader
hq: Any = importlib.util.module_from_spec(_spec)
sys.modules["harness_queue"] = hq
_spec.loader.exec_module(hq)

SHA = "a" * 40
NAMES = ["overnight-0", "quiet-5", "prime-50"]


@pytest.fixture
def cfg(tmp_path: Path) -> dict[str, Any]:
    c = hq.load_config(TOOL / "queue.yaml")
    c["work_dir"], c["results_dir"] = tmp_path / "work", tmp_path / "results"
    return dict(c)


def block(**kv: str) -> str:
    base = {"sha": SHA, "profiles": "quiet-5", "seeds": "2", "hours": "1.5"}
    base.update(kv)
    return "text\n```harness\n" + "\n".join(f"{k}: {v}" for k, v in base.items()) + "\n```\n"


def issue(n: int, author: str = "project-hiveplex", body: str | None = None, at: str = "t1") -> Any:
    return {
        "number": n,
        "title": "run",
        "body": block() if body is None else body,
        "author": {"login": author},
        "labels": [{"name": "harness-run"}],
        "createdAt": at,
    }


def test_parse_valid(cfg: dict[str, Any]) -> None:
    req = hq.parse_block(block(profiles="quiet-5, prime-50", workers="3"), cfg, NAMES)
    assert req == {
        "sha": SHA,
        "profiles": ["quiet-5", "prime-50"],
        "seeds": 2,
        "hours": 1.5,
        "workers": 3,
        "set": [],
    }
    assert hq.parse_block(block(), cfg, NAMES)["workers"] == cfg["workers"]


def test_parse_uses_first_block_only(cfg: dict[str, Any]) -> None:
    body = block() + block(seeds="3")
    assert hq.parse_block(body, cfg, NAMES)["seeds"] == 2


@pytest.mark.parametrize(
    ("body", "text"),
    [
        ("no block here", "no harness block"),
        (block(sha="A" * 40), "key: sha"),
        (block(sha="abc"), "key: sha"),
        (block(profiles="x; rm -rf ~"), "key: profiles"),
        (block(profiles="quiet-5,nope"), "key: profiles"),
        (block(seeds="0"), "key: seeds"),
        (block(seeds="51"), "key: seeds"),
        (block(seeds="2; id"), "key: seeds"),
        (block(hours="0"), "key: hours"),
        (block(hours="73"), "key: hours"),
        (block(hours="$(id)"), "key: hours"),
        (block(workers="13"), "key: workers"),
        (block(extra="1"), "unknown or malformed"),
        (block(**{"Bad Key": "1"}), "unknown"),
        ("```harness\nsha: " + SHA + "\n```", "missing keys: profiles, seeds, hours"),
        (block().replace("seeds: 2", "seeds: 2\nseeds: 3"), "duplicate key: seeds"),
    ],
)
def test_parse_refusals(cfg: dict[str, Any], body: str, text: str) -> None:
    with pytest.raises(hq.Refusal, match=text) as e:
        hq.parse_block(body, cfg, NAMES)
    assert "rm -rf" not in str(e.value)  # refusals never echo a raw value
    assert "$(id)" not in str(e.value)


class Fake:
    """Records every command; answers gh issue list from `issues` and git from `ancestor`."""

    def __init__(self, issues: list[Any], ancestor: bool = True) -> None:
        self.issues, self.ancestor = issues, ancestor
        self.calls: list[list[str]] = []
        self.stdin: list[str] = []
        self.kw: list[dict[str, Any]] = []

    def __call__(self, cmd: list[str], cwd: Any = None, stdin: str | None = None, **kw: Any) -> Any:
        self.calls.append(cmd)
        self.kw.append(kw)
        out = ""
        if cmd[:3] == ["gh", "issue", "list"]:
            want = cmd[cmd.index("--label") + 1]  # as gh does: only issues carrying the label
            out = json.dumps([i for i in self.issues if want in self.names(i)])
        if cmd[:3] == ["gh", "issue", "edit"]:  # apply label edits, as GitHub does
            i = next(i for i in self.issues if str(i["number"]) == cmd[3])
            names = self.names(i)
            if "--add-label" in cmd and cmd[cmd.index("--add-label") + 1] not in names:
                names.append(cmd[cmd.index("--add-label") + 1])
            if "--remove-label" in cmd:
                names = [n for n in names if n != cmd[cmd.index("--remove-label") + 1]]
            i["labels"] = [{"name": n} for n in names]
        if cmd[:3] == ["gh", "issue", "view"]:
            body = next(i["body"] for i in self.issues if str(i["number"]) == cmd[3])
            out = json.dumps({"body": body})
        if cmd[:2] == ["gh", "issue"] and stdin:
            self.stdin.append(stdin)
        rc = 1 if cmd[:3] == ["git", "merge-base", "--is-ancestor"] and not self.ancestor else 0
        return type("R", (), {"returncode": rc, "stdout": out, "stderr": ""})()

    @staticmethod
    def names(i: Any) -> list[str]:
        return [x["name"] for x in i["labels"]]

    def edits(self) -> list[tuple[str, str, str]]:
        return [
            (c[3], c[c.index("--add-label") + 1], c[c.index("--remove-label") + 1])
            for c in self.calls
            if c[:3] == ["gh", "issue", "edit"] and "--remove-label" in c  # not the write check
        ]


def test_author_filter_and_order(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(3, at="t3"), issue(2, "stranger"), issue(1, "SaltySeraphCodes", at="t0")])
    monkeypatch.setattr(hq, "run_cmd", fake)
    assert [i["number"] for i in hq.eligible(cfg)] == [1, 3]
    assert all(c[0] == "gh" and "-R" in c for c in fake.calls)


def test_untrusted_is_silent(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(2, "stranger", body="junk")])
    monkeypatch.setattr(hq, "run_cmd", fake)
    assert hq.run_once(cfg, False) == 0
    assert not fake.edits() and not fake.stdin


def test_malformed_refused_with_comment(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(4, body=block(profiles="x; rm -rf ~"))])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, False)
    assert fake.edits() == [("4", "harness-failed", "harness-run")]
    assert "key: profiles" in fake.stdin[0] and "rm -rf" not in fake.stdin[0]
    assert fake.stdin[0].rstrip().endswith(hq.FOOTER)
    assert not any(c[0] == "uv" for c in fake.calls)


def test_non_ancestor_sha_refused(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(5)], ancestor=False)
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, False)
    assert fake.edits() == [("5", "harness-failed", "harness-run")]
    assert "origin/develop" in fake.stdin[0]
    assert ["git", "fetch", "origin", "develop"] in fake.calls
    assert not any(c[:3] == ["git", "worktree", "add"] for c in fake.calls)


def test_same_sha_rerun_refused(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    old = cfg["results_dir"] / f"8-{SHA[:8]}"  # an earlier, finished and posted attempt
    old.mkdir(parents=True)
    (old / "report.md").write_text("# OLD")
    (old / hq.FINISHED).write_text("5")
    (old / hq.POSTED).touch()
    fake = Fake([issue(8)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    ran: list[int] = []
    monkeypatch.setattr(hq, "execute", lambda *a: ran.append(1))
    hq.run_once(cfg, False)
    assert not ran and not hq.running_file(cfg, 8).exists()
    assert fake.edits() == [("8", "harness-failed", "harness-run")]
    assert "already ran this sha" in fake.stdin[0]


def test_dry_run_changes_nothing(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(6), issue(7, body="junk")])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, True)
    assert not fake.edits() and not fake.stdin
    assert not any(c[:2] == ["git", "worktree"] for c in fake.calls)


def fake_exec(rc: int, report: str | None, logtext: str = "") -> Any:
    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        out = c["results_dir"] / f"{n}-{req['sha'][:8]}"
        out.mkdir(parents=True)
        log = c["results_dir"] / f"{n}.log"
        log.write_text(logtext)
        if report is not None:
            (out / "report.md").write_text(report)
        return rc, out, log

    return _exec


def test_success_labels_and_comment(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(8)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    assert fake.edits() == [
        ("8", "harness-running", "harness-run"),
        ("8", "harness-done", "harness-running"),
    ]
    assert "# REPORT" in fake.stdin[0] and " min" in fake.stdin[0]
    assert fake.stdin[0].rstrip().endswith(hq.FOOTER)
    assert f"Sha that ran (recorded at start): `{SHA}`" in fake.stdin[0]
    assert "edited after queueing" not in fake.stdin[0]  # body unchanged: no flag
    report = cfg["results_dir"] / f"8-{SHA[:8]}" / "report.md"
    assert report.read_text().startswith(f"Sha that ran (recorded by the queue at start): `{SHA}`")


def test_edited_body_sha_is_flagged(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(9)])
    monkeypatch.setattr(hq, "run_cmd", fake)

    def edit_then_run(c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False) -> Any:
        fake.issues[0]["body"] = block(sha="b" * 40)  # the lead edits the issue mid-run
        return fake_exec(0, "# REPORT")(c, n, req, resume)

    monkeypatch.setattr(hq, "execute", edit_then_run)
    hq.run_once(cfg, False)
    assert (
        f"Body sha `{'b' * 40}` was edited after queueing; this run used `{SHA}`" in fake.stdin[0]
    )


def test_edited_body_sha_is_flagged_on_recovery(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = Fake([issue(27)])
    monkeypatch.setattr(hq, "run_cmd", failing(first, ["gh", "issue", "comment"]))
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    edited = stale_issue(27)
    edited["body"] = block(sha="c" * 40)
    second = Fake([edited])
    monkeypatch.setattr(hq, "run_cmd", second)
    hq.run_once(cfg, False)
    assert (
        f"Body sha `{'c' * 40}` was edited after queueing; this run used `{SHA}`" in second.stdin[0]
    )


def test_hostile_body_sha_is_not_echoed(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(10)])
    monkeypatch.setattr(hq, "run_cmd", fake)

    def edit_then_run(c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False) -> Any:
        fake.issues[0]["body"] = block(sha="@someone [x](http://e)")
        return fake_exec(0, "# REPORT")(c, n, req, resume)

    monkeypatch.setattr(hq, "execute", edit_then_run)
    hq.run_once(cfg, False)
    assert "Body sha (none valid or unreadable) was edited" in fake.stdin[0]
    assert "@someone" not in fake.stdin[0] and "http://e" not in fake.stdin[0]


def test_duplicated_body_sha_is_flagged(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(10)])
    monkeypatch.setattr(hq, "run_cmd", fake)

    def edit_then_run(c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False) -> Any:
        # the run sha stays, a second sha line is added: ambiguous, as parse_block would refuse it
        fake.issues[0]["body"] = block().replace("\n```\n", "\nsha: " + "b" * 40 + "\n```\n")
        return fake_exec(0, "# REPORT")(c, n, req, resume)

    monkeypatch.setattr(hq, "execute", edit_then_run)
    hq.run_once(cfg, False)
    assert "Body sha (none valid or unreadable) was edited" in fake.stdin[0]


def test_unreadable_body_still_posts_with_a_note(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(11)])
    monkeypatch.setattr(hq, "run_cmd", failing(fake, ["gh", "issue", "view"]))
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    assert "Body sha (none valid or unreadable) was edited" in fake.stdin[0]
    assert "# REPORT" in fake.stdin[0]
    assert fake.edits()[-1] == ("11", "harness-done", "harness-running")  # posted, not failed


def test_failure_comment_has_exit_code_and_last_40_lines(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(9)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    monkeypatch.setattr(
        hq, "execute", fake_exec(3, None, "\n".join(f"line{i}" for i in range(100)))
    )
    hq.run_once(cfg, False)
    assert fake.edits()[-1] == ("9", "harness-failed", "harness-running")
    body = fake.stdin[0]
    assert "exit code 3" in body and "line99" in body and "line59" not in body
    assert "line60" in body


def test_truncation(tmp_path: Path) -> None:
    assert hq.truncate("short", tmp_path) == "short"
    cut = hq.truncate("x" * 100000, tmp_path)
    assert len(cut) <= hq.COMMENT_MAX and hq.shown(tmp_path) in cut and "Truncated" in cut


def test_lock_held_exits_zero(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake([issue(10)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    cfg["work_dir"].mkdir(parents=True)
    with (cfg["work_dir"] / "queue.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert hq.run_once(cfg, False) == 0
    assert "holds the lock" in capsys.readouterr().out
    assert fake.calls == []


def test_missing_gh_is_one_line_error(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(hq, "load_config", lambda _: cfg)
    assert hq.main(["run-once", "--dry-run"]) == 2
    assert "gh not found" in capsys.readouterr().err


def test_profiles_deduped_and_capped(cfg: dict[str, Any]) -> None:
    req = hq.parse_block(block(profiles="quiet-5,quiet-5,prime-50"), cfg, NAMES)
    assert req["profiles"] == ["quiet-5", "prime-50"]
    cfg["max_profiles"] = 2
    with pytest.raises(hq.Refusal):
        hq.parse_block(block(profiles="quiet-5,prime-50,overnight-0"), cfg, NAMES)


def test_execute_commands(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([])
    monkeypatch.setattr(hq, "run_cmd", fake)
    req = hq.parse_block(block(profiles="quiet-5,prime-50", workers="3"), cfg, NAMES)
    rc, out, _ = hq.execute(cfg, 11, req)
    wt = cfg["work_dir"] / f"wt-11-{SHA[:8]}"
    assert rc == 0 and out == cfg["results_dir"] / f"11-{SHA[:8]}"
    assert fake.calls[0] == ["git", "worktree", "add", "--detach", str(wt), SHA]
    assert fake.calls[1] == ["uv", "sync", "--frozen"]
    assert fake.calls[2] == [
        "uv", "run", "--frozen", "python", "../../tools/balance/balance.py",
        "--profile", "quiet-5,prime-50", "--seeds", "2", "--hours", "1.5",
        "--workers", "3", "--out", str(out),
    ]  # fmt: skip
    assert fake.kw[1]["timeout"] == fake.kw[2]["timeout"] == cfg["job_timeout_hours"] * 3600
    assert fake.calls[-2][:3] == ["git", "worktree", "remove"]


def test_timeout_fails_and_cleans_up(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(12)])

    def run(cmd: list[str], **kw: Any) -> Any:
        if cmd[0] == "uv" and "timeout" in kw:
            raise hq.JobTimeout
        return fake(cmd, **kw)

    monkeypatch.setattr(hq, "run_cmd", run)
    hq.run_once(cfg, False)
    assert fake.edits()[-1] == ("12", "harness-failed", "harness-running")
    assert "timed out after 96 h" in fake.stdin[0]
    assert any(c[:3] == ["git", "worktree", "remove"] for c in fake.calls)


def test_real_timeout_kills_process_group(tmp_path: Path) -> None:
    marker = tmp_path / "survived"
    cmd = ["sh", "-c", f"(sleep 2; touch {marker}) & sleep 30"]
    with pytest.raises(hq.JobTimeout):
        hq.run_cmd(cmd, timeout=0.5)
    import time

    time.sleep(2.5)
    assert not marker.exists()


def test_unexpected_error_marks_failed_with_type_only(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake([issue(13), issue(14)])
    monkeypatch.setattr(hq, "run_cmd", fake)

    def boom(*a: Any) -> Any:
        raise ValueError("secret detail")

    monkeypatch.setattr(hq, "execute", boom)
    hq.run_once(cfg, False)
    for n in ("13", "14"):  # the two jobs overlap (NX-442): order within each issue only
        assert [e[1] for e in fake.edits() if e[0] == n] == ["harness-running", "harness-failed"]
    assert "ValueError" in fake.stdin[0] and "secret detail" not in fake.stdin[0]
    assert "ValueError: secret detail" in capsys.readouterr().out  # the local log keeps the text


def test_stale_running_recovered(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    stale = issue(15)
    stale["labels"] = [{"name": "harness-running"}]
    fake = Fake([stale])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, False)
    assert fake.edits() == [("15", "harness-failed", "harness-running")]
    assert "restarted mid-job" in fake.stdin[0]


def test_tail_caps_and_shown(tmp_path: Path) -> None:
    log = tmp_path / "x.log"
    log.write_text(("y" * 5000 + "\n") * 100)
    assert len(hq.tail(log)) < hq.COMMENT_MAX
    home = Path.home()
    assert hq.shown(home / ".local" / "a") == "~/.local/a"
    assert str(home) not in hq.shown(home / "a") or str(home) == "/"


def test_tail_hides_the_home_path_and_closing_fences(tmp_path: Path) -> None:
    log = tmp_path / "x.log"
    log.write_text(f'File "{Path.home()}/proj/run.py", line 3\n```\ndone\n')
    out = hq.tail(log)
    assert str(Path.home()) not in out
    assert "~/proj/run.py" in out
    assert "```" not in out


def test_set_parsed_into_argv_pairs(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    req = hq.parse_block(block(set="tasking.strike_idle_targets_max=0, a.b_1=-2.5"), cfg, NAMES)
    assert req["set"] == ["tasking.strike_idle_targets_max=0", "a.b_1=-2.5"]
    assert hq.parse_block(block(), cfg, NAMES)["set"] == []
    fake = Fake([])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.execute(cfg, 11, req)
    assert fake.calls[2][-4:] == [
        "--set", "tasking.strike_idle_targets_max=0", "--set", "a.b_1=-2.5",
    ]  # fmt: skip


def test_set_takes_bool_literals_and_enum_segments(cfg: dict[str, Any]) -> None:
    # NX-412 part 5a: a switch and a per-side key; balance.py checks the value against the key
    value = (
        "economy.legacy_rules=false, economy.unlimited.ENEMY=true, economy.upkeep.STRIKE_FIGHTER=3"
    )
    assert hq.parse_block(block(set=value), cfg, NAMES)["set"] == [
        "economy.legacy_rules=false", "economy.unlimited.ENEMY=true",
        "economy.upkeep.STRIKE_FIGHTER=3",
    ]  # fmt: skip


def test_set_takes_max_overrides(cfg: dict[str, Any]) -> None:
    # 16 (queue.yaml): the 3 economy switches plus all 9 economy.upkeep kinds fit (Q-TD-41, J5)
    value = ",".join(f"k{i}=1" for i in range(16))
    assert len(hq.parse_block(block(set=value), cfg, NAMES)["set"]) == 16


@pytest.mark.parametrize(
    "value",
    [
        ",".join(f"k{i}=1" for i in range(17)),  # over max_overrides (16)
        "A.b=1", "a..b=1", "a=1;rm", "a=1e9", "a=$(x)", "a=", "a=1234567890",
        # bools: lower-case literals only, nothing around them
        "a=True", "a=FALSE", "a=yes", "a=on", "a=true1", "a=truefalse", "a=-true", "a=tru",
        "a.ENEMY=fals", "a.ENEMY-1=true", "a.b=true;rm", "a.b=`true`", "a.b= true x",
    ],
)  # fmt: skip
def test_set_refusals(cfg: dict[str, Any], value: str) -> None:
    with pytest.raises(hq.Refusal, match="bad value for key: set"):
        hq.parse_block(block(set=value), cfg, NAMES)


def failing(fake: Fake, *prefixes: list[str], rc: int = 1) -> Any:
    """Wrap a Fake so a gh call starting with one of `prefixes` fails with a token-ish error."""

    def run(cmd: list[str], **kw: Any) -> Any:
        if any(cmd[: len(p)] == p for p in prefixes):
            fake.calls.append(cmd)
            return type("R", (), {"returncode": rc, "stdout": "", "stderr": "SECRET-TOKEN-TEXT"})()
        return fake(cmd, **kw)

    return run


def test_timed_out_post_keeps_report_for_recovery(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(22)])

    def run(cmd: list[str], **kw: Any) -> Any:
        if cmd[:3] == ["gh", "issue", "comment"]:
            raise hq.JobTimeout
        return fake(cmd, **kw)

    monkeypatch.setattr(hq, "run_cmd", run)
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    assert fake.edits() == [("22", "harness-running", "harness-run")]  # not failed
    assert hq.running_file(cfg, 22).exists()  # recovery can still find the report
    fake.issues[0]["labels"] = [{"name": "harness-running"}]  # the Fake doesn't apply edits
    hq.recover_stale(cfg, hq.Jobs(cfg))  # a second timeout in recovery must not escape the tick
    assert hq.running_file(cfg, 22).exists()


def test_failed_write_check_skips_run_and_keeps_labels(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake([issue(20)])
    monkeypatch.setattr(hq, "run_cmd", failing(fake, ["gh", "issue", "edit"]))
    ran: list[int] = []
    monkeypatch.setattr(hq, "execute", lambda *a: ran.append(1))
    hq.run_once(cfg, False)
    assert not ran and not fake.stdin
    (check,) = [c for c in fake.calls if c[:3] == ["gh", "issue", "edit"]]
    assert check[3:] == ["20", "--add-label", "harness-run", "-R", cfg["repo"]]  # no removal
    out = capsys.readouterr().out
    assert "cannot write" in out and "SECRET-TOKEN-TEXT" not in out


def test_failed_post_keeps_report_and_run_not_failed(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(21)])
    monkeypatch.setattr(hq, "run_cmd", failing(fake, ["gh", "issue", "comment"]))
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    assert fake.edits() == [("21", "harness-running", "harness-run")]  # not failed, not done
    kept = (cfg["results_dir"] / f"21-{SHA[:8]}" / "report.md").read_text()
    assert kept.endswith("\n\n# REPORT")
    assert not fake.stdin


def stale_issue(n: int) -> Any:
    stale = issue(n)
    stale["labels"] = [{"name": "harness-running"}]
    return stale


def test_next_tick_posts_finished_report_and_marks_done(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = Fake([issue(22)])
    monkeypatch.setattr(hq, "run_cmd", failing(first, ["gh", "issue", "comment"]))
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    second = Fake([stale_issue(22)])
    monkeypatch.setattr(hq, "run_cmd", second)
    hq.run_once(cfg, False)
    assert second.edits() == [("22", "harness-done", "harness-running")]
    assert "# REPORT" in second.stdin[0] and second.stdin[0].rstrip().endswith(hq.FOOTER)


def test_recovery_does_not_double_post(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = Fake([issue(23)])
    monkeypatch.setattr(
        hq, "run_cmd", failing(first, ["gh", "issue", "edit", "23", "--add-label", "harness-done"])
    )
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    assert len(first.stdin) == 1  # posted, relabel failed
    second = Fake([stale_issue(23)])
    monkeypatch.setattr(hq, "run_cmd", second)
    hq.run_once(cfg, False)
    assert not second.stdin and second.edits() == [("23", "harness-done", "harness-running")]


def test_stale_without_finished_report_still_fails(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([stale_issue(24)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, False)
    assert fake.edits() == [("24", "harness-failed", "harness-running")]
    assert "restarted mid-job" in fake.stdin[0]


def test_partial_report_is_not_finished(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out = cfg["results_dir"] / f"25-{SHA[:8]}"
    out.mkdir(parents=True)
    (cfg["results_dir"] / "25.running").write_text(SHA)
    (out / "report.md").write_text("# half a rep")  # balance.py died mid-write: no marker
    fake = Fake([stale_issue(25)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, False)
    assert fake.edits() == [("25", "harness-failed", "harness-running")]
    (out / hq.FINISHED).write_text("999")  # a marker that disagrees with the file is not finished
    assert not hq.finished(out)


def test_recovery_uses_recorded_sha_not_edited_body(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = Fake([issue(26)])
    monkeypatch.setattr(hq, "run_cmd", failing(first, ["gh", "issue", "comment"]))
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    hq.run_once(cfg, False)
    older = cfg["results_dir"] / f"26-{'b' * 8}"
    older.mkdir()
    (older / "report.md").write_text("# OLDER")
    (older / hq.FINISHED).write_text(str(len("# OLDER")))
    edited = stale_issue(26)
    edited["body"] = block(sha="b" * 40)
    second = Fake([edited])
    monkeypatch.setattr(hq, "run_cmd", second)
    hq.run_once(cfg, False)
    assert "# REPORT" in second.stdin[0] and "OLDER" not in second.stdin[0]
    assert not (cfg["results_dir"] / "26.running").exists()


def test_invalid_recorded_sha_fails(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    cfg["results_dir"].mkdir(parents=True)
    (cfg["results_dir"] / "27.running").write_text("../../etc")
    fake = Fake([stale_issue(27)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, False)
    assert fake.edits() == [("27", "harness-failed", "harness-running")]
    assert not (cfg["results_dir"] / "27.running").exists()


def test_posted_marker_oserror_leaves_running(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(28)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    monkeypatch.setattr(hq, "execute", fake_exec(0, "# REPORT"))
    real = Path.touch

    def touch(self: Path, *a: Any, **k: Any) -> None:
        if self.name == hq.POSTED:
            raise OSError("disk full")
        real(self, *a, **k)

    monkeypatch.setattr(Path, "touch", touch)
    hq.run_once(cfg, False)
    assert fake.edits() == [("28", "harness-running", "harness-run")]  # not failed, not done
    assert len(fake.stdin) == 1


# --- resume after a kill (NX-433) ------------------------------------------------------------
class Killed(BaseException):
    """Stands in for the process being killed: nothing in the queue catches it."""


def killable_exec(kill_after: int | None, ran: list[str], seen: list[bool]) -> Any:
    """A fake balance job over seeds 1..N: writes one run file per seed unless the file is
    already there and `resume` is set (what `--resume` does), and `report.md` last."""

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        seen.append(resume)
        out = c["results_dir"] / f"{n}-{req['sha'][:8]}"
        (out / "runs").mkdir(parents=True, exist_ok=True)
        log = c["results_dir"] / f"{n}.log"
        log.write_text("")
        for seed in range(1, req["seeds"] + 1):
            f = out / "runs" / f"s{seed}.json"
            if resume and f.exists():
                continue
            if kill_after is not None and len(ran) >= kill_after:
                raise Killed
            f.write_text("{}")
            ran.append(f"s{seed}")
        (out / "report.md").write_text("# ONE REPORT")
        return 0, out, log

    return _exec


def test_kill_mid_job_then_next_tick_reruns_only_the_missing_runs(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[str] = []
    seen: list[bool] = []
    first = Fake([issue(40, body=block(seeds="3"))])
    monkeypatch.setattr(hq, "run_cmd", first)
    monkeypatch.setattr(hq, "execute", killable_exec(1, ran, seen))
    with pytest.raises(Killed):
        hq.run_once(cfg, False)
    assert ran == ["s1"] and hq.running_file(cfg, 40).exists()
    second = Fake([stale_issue(40)])
    second.issues[0]["body"] = block(seeds="9", sha="b" * 40, profiles="prime-50")  # edited
    monkeypatch.setattr(hq, "run_cmd", second)
    monkeypatch.setattr(hq, "execute", killable_exec(None, ran, seen))
    hq.run_once(cfg, False)
    assert ran == ["s1", "s2", "s3"] and seen == [False, True]  # s1 not run again, 3 seeds not 9
    assert second.edits() == [("40", "harness-done", "harness-running")]
    assert len(second.stdin) == 1 and "# ONE REPORT" in second.stdin[0]  # one report
    assert f"Sha that ran (recorded at start): `{SHA}`" in second.stdin[0]  # not the edited body's
    assert "(resumed)" in second.stdin[0]
    assert second.names(second.issues[0]) == ["harness-done"]  # no `harness-run` left behind
    assert len(second.stdin) == 1  # and no Refused comment
    for f in (hq.running_file, hq.resumes_file, hq.request_file):
        assert not f(cfg, 40).exists()


def test_resume_argument_reaches_balance(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    req = hq.parse_block(block(), cfg, NAMES)
    wt = str(cfg["work_dir"] / f"wt-41-{SHA[:8]}")
    remove = ["git", "worktree", "remove", "--force", wt]
    seen = []
    for resume in (False, True):
        fake = Fake([])
        monkeypatch.setattr(hq, "run_cmd", fake)
        hq.execute(cfg, 41, req, resume)
        balances = [c for c in fake.calls if "../../tools/balance/balance.py" in c]
        assert ("--resume" in balances[0]) is resume
        # a killed attempt's worktree is removed (and pruned) before the new one is added
        add = next(i for i, c in enumerate(fake.calls) if c[:3] == ["git", "worktree", "add"])
        seen.append((remove in fake.calls[:add], ["git", "worktree", "prune"] in fake.calls[:add]))
    assert seen == [(False, False), (True, True)]


def test_failed_resume_leaves_only_harness_failed_and_one_comment(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hq, "run_cmd", Fake([issue(46, body=block(seeds="2"))]))
    monkeypatch.setattr(hq, "execute", killable_exec(1, [], []))
    with pytest.raises(Killed):
        hq.run_once(cfg, False)

    def exec_fails(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        log = c["results_dir"] / f"{n}.log"
        log.write_text("boom")
        return 3, c["results_dir"] / f"{n}-{req['sha'][:8]}", log

    second = Fake([stale_issue(46)])
    monkeypatch.setattr(hq, "run_cmd", second)
    monkeypatch.setattr(hq, "execute", exec_fails)
    hq.run_once(cfg, False)
    assert second.names(second.issues[0]) == ["harness-failed"]
    assert len(second.stdin) == 1 and "Run failed" in second.stdin[0]
    assert "Refused" not in second.stdin[0]


def test_recorded_request_naming_another_sha_is_failed_not_resumed(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[Any] = []
    monkeypatch.setattr(hq, "execute", lambda *a: ran.append(a))
    cfg["results_dir"].mkdir(parents=True)
    (cfg["results_dir"] / "47.running").write_text(SHA)
    (cfg["results_dir"] / f"47-{SHA[:8]}").mkdir()
    other = hq.parse_block(block(sha="b" * 40), cfg, NAMES)
    hq.request_file(cfg, 47).write_text(json.dumps(other))
    fake = Fake([stale_issue(47)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.recover_stale(cfg, hq.Jobs(cfg))
    assert not ran
    assert fake.names(fake.issues[0]) == ["harness-failed"]


def test_resumes_are_bounded(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """A job that keeps getting killed is resumed MAX_RESUMES times, then failed."""
    ran: list[str] = []
    seen: list[bool] = []
    monkeypatch.setattr(hq, "run_cmd", Fake([issue(42, body=block(seeds="2"))]))
    monkeypatch.setattr(hq, "execute", killable_exec(0, ran, seen))
    with pytest.raises(Killed):
        hq.run_once(cfg, False)
    for attempt in range(hq.MAX_RESUMES):
        monkeypatch.setattr(hq, "run_cmd", Fake([stale_issue(42)]))
        with pytest.raises(Killed):
            hq.run_once(cfg, False)
        assert hq.resumes_file(cfg, 42).read_text() == str(attempt + 1)
    last = Fake([stale_issue(42)])
    monkeypatch.setattr(hq, "run_cmd", last)
    hq.run_once(cfg, False)
    assert seen == [False] + [True] * hq.MAX_RESUMES  # no further execute
    assert last.edits() == [("42", "harness-failed", "harness-running")]
    assert "restarted mid-job" in last.stdin[0]
    assert not hq.resumes_file(cfg, 42).exists() and not hq.request_file(cfg, 42).exists()


def test_stale_job_without_results_dir_or_request_fails_not_resumes(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[Any] = []
    monkeypatch.setattr(hq, "execute", lambda *a: ran.append(a))
    cfg["results_dir"].mkdir(parents=True)
    (cfg["results_dir"] / "43.running").write_text(SHA)
    (cfg["results_dir"] / f"43-{SHA[:8]}").mkdir()  # dir but no recorded request
    (cfg["results_dir"] / "44.running").write_text(SHA)
    hq.request_file(cfg, 44).write_text(json.dumps(hq.parse_block(block(), cfg, NAMES)))
    fake = Fake([stale_issue(43), stale_issue(44)])  # 44: a request but no results dir
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.recover_stale(cfg, hq.Jobs(cfg))
    assert not ran
    assert [e[1] for e in fake.edits()] == ["harness-failed", "harness-failed"]


def test_new_request_for_an_attempted_sha_is_still_refused(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    (cfg["results_dir"] / f"45-{SHA[:8]}").mkdir(parents=True)  # `harness-run` again, not stale
    fake = Fake([issue(45)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    ran: list[Any] = []
    monkeypatch.setattr(hq, "execute", lambda *a: ran.append(a))
    hq.run_once(cfg, False)
    assert not ran and "already ran this sha" in fake.stdin[0]


# --- overlapping jobs on one worker budget (NX-442, Q-DEV-33) ----------------------------------
TWO = "quiet-5, prime-50"  # x 6 seeds = 12 runs


def out_of(cfg: dict[str, Any], n: int) -> Path:
    return Path(cfg["results_dir"]) / f"{n}-{SHA[:8]}"


def write_runs(out: Path, k: int) -> None:
    """Result files for the first k runs, named as balance.py names them (<profile>-s<seed>)."""
    (out / "runs").mkdir(parents=True, exist_ok=True)
    for seed in range(1, k + 1):
        (out / "runs" / f"p-s{seed}.json").write_text("{}")
    (out / "runs" / "p-s99.json.tmp").write_text("")  # a half-written run is not a result


def finish(c: dict[str, Any], n: int, out: Path) -> tuple[int, Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(f"# REPORT {n}")
    log = Path(c["results_dir"]) / f"{n}.log"
    log.write_text("")
    return 0, out, log


def own_reports(fake: Fake, numbers: list[int]) -> None:
    """Each issue ends `harness-done` with exactly one comment, carrying its own report only."""
    for n in numbers:
        i = next(i for i in fake.issues if i["number"] == n)
        assert fake.names(i) == ["harness-done"], n
        mine = [s for s in fake.stdin if f"# REPORT {n}" in s]
        assert len(mine) == 1 and all(f"# REPORT {m}" not in mine[0] for m in numbers if m != n)
    assert len(fake.stdin) == len(numbers)


class Polls:
    """Counts the tick's waits (`Jobs.wait`), so a test can let the tick look N more times
    instead of sleeping. The 10 s is only a hang guard; no assertion depends on time."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.n, self.cv, real = 0, threading.Condition(), hq.Jobs.wait

        def wait(jobs: Any) -> bool:
            timed_out = bool(real(jobs))
            with self.cv:
                self.n += 1
                self.cv.notify_all()
            return timed_out

        monkeypatch.setattr(hq, "POLL_S", 0.01)
        monkeypatch.setattr(hq.Jobs, "wait", wait)

    def after(self, k: int) -> None:
        """Block until the tick has waited k more times (so it re-checked at least k - 1)."""
        with self.cv:
            target = self.n + k
            assert self.cv.wait_for(lambda: self.n >= target, timeout=10)


def lock_is_held(c: dict[str, Any]) -> bool:
    with (Path(c["work_dir"]) / "queue.lock").open("w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
        return False


@pytest.mark.parametrize("value", [None, 0, -1, "six", 13, True])
def test_min_overlap_workers_is_validated(tmp_path: Path, value: Any) -> None:
    raw = yaml.safe_load((TOOL / "queue.yaml").read_text())
    if value is None:
        del raw["min_overlap_workers"]
    else:
        raw["min_overlap_workers"] = value
    (path := tmp_path / "queue.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(hq.QueueError, match="min_overlap_workers"):
        hq.load_config(path)
    raw["min_overlap_workers"] = 12  # = max_workers: accepted
    path.write_text(yaml.safe_dump(raw))
    assert hq.load_config(path)["min_overlap_workers"] == 12


def test_next_job_starts_on_freed_workers_within_the_budget(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Budget 12, min_overlap_workers 6 (queue.yaml). A (12 runs, 12 workers) holds min(12, runs
    left); B starts once A has 6 left, on 6 workers; C waits until A ends and B still holds 6."""
    assert (cfg["max_workers"], cfg["min_overlap_workers"]) == (12, 6)
    polls = Polls(monkeypatch)
    body = block(profiles=TWO, seeds="6", workers="12")
    fake = Fake([issue(50, body=body, at="t1"), issue(51, body=body, at="t2"),
                 issue(52, body=body, at="t3")])  # fmt: skip
    monkeypatch.setattr(hq, "run_cmd", fake)
    starts: list[tuple[int, int, int, int]] = []  # issue, workers, A's and B's runs left
    b_started, c_started = threading.Event(), threading.Event()
    early: list[bool] = []
    second_tick: list[int] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        left = [hq.runs_left(out_of(c, m), 12) for m in (50, 51)]
        starts.append((n, req["workers"], *left))
        out = out_of(c, n)
        if n == 50:
            write_runs(out, 5)  # 7 left: 5 free, under 6
            polls.after(5)  # the tick looked at least 4 more times
            early.append(b_started.is_set())  # B must not have started,
            early.append(fake.names(fake.issues[1]) != ["harness-run"])  # nor been relabelled
            second_tick.append(hq.run_once(c, False))  # a second tick while this one runs
            write_runs(out, 6)  # 6 left: 6 free
            b_started.wait(10)
            write_runs(out, 12)
        elif n == 51:
            b_started.set()
            c_started.wait(10)  # B holds its 6 workers until C has started
            write_runs(out, 12)
        else:
            c_started.set()
            write_runs(out, 12)
        return finish(c, n, out)

    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert early == [False, False] and second_tick == [0]  # the lock: the second tick did nothing
    assert starts == [
        (50, 12, 12, 12),  # nothing running: A gets all it asked for
        (51, 6, 6, 12),  # A at 6 runs left holds 6; B gets the 6 freed, not the 12 it asked
        (52, 6, 0, 12),  # A done; B holds min(6, 12) = 6; C gets the other 6
    ]
    for n in ("50", "51", "52"):
        assert [e[1] for e in fake.edits() if e[0] == n] == ["harness-running", "harness-done"]
    own_reports(fake, [50, 51, 52])


def test_crash_with_two_jobs_running_resumes_each(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hq, "POLL_S", 0.01)
    body = block(profiles=TWO, seeds="6", workers="12")
    monkeypatch.setattr(hq, "run_cmd", Fake([issue(60, body=body, at="t1"),
                                             issue(61, body=body, at="t2")]))  # fmt: skip
    both = threading.Barrier(2, timeout=5)

    def crash(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        write_runs(out_of(c, n), 6 if n == 60 else 2)  # 60 at 6 left lets 61 start
        both.wait()  # both jobs are running
        raise Killed

    monkeypatch.setattr(hq, "execute", crash)
    with pytest.raises(Killed):
        hq.run_once(cfg, False)
    resumed: list[tuple[int, bool, int]] = []

    def resume_exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        total = len(req["profiles"]) * req["seeds"]
        resumed.append((n, resume, hq.runs_left(out_of(c, n), total)))
        write_runs(out_of(c, n), 12)
        return finish(c, n, out_of(c, n))

    second = Fake([stale_issue(60), stale_issue(61)])  # bodies say quiet-5 x 2: never read
    monkeypatch.setattr(hq, "run_cmd", second)
    monkeypatch.setattr(hq, "execute", resume_exec)
    hq.run_once(cfg, False)
    assert sorted(resumed) == [(60, True, 6), (61, True, 10)]  # each from its own result files
    own_reports(second, [60, 61])
    assert all("(resumed)" in s for s in second.stdin)
    for n in (60, 61):
        assert not hq.running_file(cfg, n).exists() and not hq.request_file(cfg, n).exists()


def test_failed_relist_keeps_the_running_job(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hq, "POLL_S", 0.01)
    fake = Fake([issue(70)])  # 2 workers: 10 free, so the tick relists while it runs
    lists: list[int] = []
    failed = threading.Event()

    def run(cmd: list[str], **kw: Any) -> Any:
        if cmd[:3] == ["gh", "issue", "list"] and "harness-run" in cmd:
            lists.append(1)
            if len(lists) > 1:
                failed.set()
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": "down"})()
        return fake(cmd, **kw)

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        failed.wait(5)
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "run_cmd", run)
    monkeypatch.setattr(hq, "execute", _exec)
    assert hq.run_once(cfg, False) == 0
    assert failed.is_set()
    own_reports(fake, [70])


def test_job_killed_beside_another_keeps_the_lock_until_both_end(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    polls = Polls(monkeypatch)
    fake = Fake([issue(90, body=block(profiles=TWO, seeds="6", workers="12"), at="t1"),
                 issue(91, body=block(seeds="6", workers="6"), at="t2"),
                 issue(99, body=block(workers="2"), at="t3")])  # fmt: skip
    monkeypatch.setattr(hq, "run_cmd", fake)
    b_started, a_dying = threading.Event(), threading.Event()
    held: list[bool] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        if n == 90:
            write_runs(out_of(c, n), 6)  # 6 free: B fits
            b_started.wait(10)
            a_dying.set()
            raise Killed
        if n == 91:
            b_started.set()
            a_dying.wait(10)
            polls.after(3)  # the tick has reaped A's error and gone on
            held.append(lock_is_held(c))
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "execute", _exec)
    with pytest.raises(Killed):  # re-raised only after B ended
        hq.run_once(cfg, False)
    assert held == [True]
    assert fake.names(fake.issues[0]) == ["harness-running"]  # A is left for recovery
    assert hq.running_file(cfg, 90).exists()
    own_reports(fake, [91, 99])  # B, and #99 on A's freed workers, run to the end
    assert not lock_is_held(cfg)


def test_an_error_leaving_the_tick_waits_for_its_jobs(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """recover_stale resumes #95, then the list of new issues fails: the tick still holds the
    lock until the resume has ended, and only then raises."""
    out = out_of(cfg, 95)
    out.mkdir(parents=True)
    hq.running_file(cfg, 95).write_text(SHA)
    hq.request_file(cfg, 95).write_text(json.dumps(hq.parse_block(block(), cfg, NAMES)))
    fake = Fake([stale_issue(95)])
    monkeypatch.setattr(hq, "run_cmd", failing(fake, ["gh", "issue", "list", "--state", "open",
                                                      "--label", "harness-run"]))  # fmt: skip
    joining = threading.Event()
    real_join = hq.Jobs.join

    def join(jobs: Any) -> None:
        joining.set()
        real_join(jobs)

    monkeypatch.setattr(hq.Jobs, "join", join)
    held: list[bool] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        joining.wait(10)  # the tick is on its way out
        held.append(lock_is_held(c))
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "execute", _exec)
    with pytest.raises(hq.QueueError):
        hq.run_once(cfg, False)
    assert held == [True]
    own_reports(fake, [95])


def test_requests_start_oldest_first(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """A at 10 runs left frees 2: B (12 workers) needs 6 and waits, and C (2 workers), younger,
    does not overtake it."""
    polls = Polls(monkeypatch)
    big = block(profiles=TWO, seeds="6", workers="12")
    fake = Fake([issue(86, body=big, at="t1"), issue(87, body=big, at="t2"),
                 issue(88, body=block(workers="2"), at="t3")])  # fmt: skip
    monkeypatch.setattr(hq, "run_cmd", fake)
    starts: list[int] = []
    overtaken: list[bool] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        starts.append(n)
        if n == 86:
            write_runs(out_of(c, n), 2)
            polls.after(5)
            overtaken.append(len(starts) > 1)
            write_runs(out_of(c, n), 12)
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert overtaken == [False] and starts == [86, 87, 88]
    own_reports(fake, [86, 87, 88])


def test_a_timed_out_failure_comment_still_drops_the_records(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(89)])

    def run(cmd: list[str], **kw: Any) -> Any:
        if cmd[:3] == ["gh", "issue", "comment"]:
            raise hq.JobTimeout
        return fake(cmd, **kw)

    monkeypatch.setattr(hq, "run_cmd", run)
    monkeypatch.setattr(hq, "execute", fake_exec(3, None))
    assert hq.run_once(cfg, False) == 0
    assert fake.names(fake.issues[0]) == ["harness-failed"]
    assert not hq.running_file(cfg, 89).exists()


def test_a_slip_in_launch_still_fails_the_issue_once(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(92)])
    monkeypatch.setattr(hq, "run_cmd", fake)

    def boom(*a: Any) -> None:
        raise ValueError("detail")

    monkeypatch.setattr(hq, "launch", boom)
    assert hq.run_once(cfg, False) == 0
    assert fake.edits() == [("92", "harness-running", "harness-run"),
                            ("92", "harness-failed", "harness-running")]  # fmt: skip
    assert len(fake.stdin) == 1 and "internal error (ValueError)" in fake.stdin[0]
    assert "detail" not in fake.stdin[0]


def test_fail_survives_a_disk_error_dropping_records(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([issue(93)])
    monkeypatch.setattr(hq, "run_cmd", fake)
    monkeypatch.setattr(hq, "execute", fake_exec(3, None))

    def broken(*a: Any) -> None:
        raise OSError("disk")

    monkeypatch.setattr(hq, "forget", broken)
    assert hq.run_once(cfg, False) == 0
    assert fake.names(fake.issues[0]) == ["harness-failed"]
    assert len(fake.stdin) == 1  # one failure comment, not a second from a last-resort handler


def test_an_issue_is_tried_once_while_a_job_runs(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """No POLL_S passes (the job's end wakes the tick), so a failed write check is not retried."""
    fake = Fake([issue(80, at="t1"), issue(81, at="t2")])
    checked = threading.Event()
    checks: list[int] = []
    wrapped = failing(fake, ["gh", "issue", "edit", "81", "--add-label", "harness-run"])

    def run(cmd: list[str], **kw: Any) -> Any:
        if cmd[:4] == ["gh", "issue", "edit", "81"]:
            checks.append(1)
            checked.set()
        return wrapped(cmd, **kw)

    started: list[int] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        started.append(n)
        checked.wait(10)
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "run_cmd", run)
    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert started == [80] and len(checks) == 1
    assert fake.names(fake.issues[1]) == ["harness-run"]  # untouched for the next tick


def test_a_skipped_issue_is_retried_after_poll_s(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    Polls(monkeypatch)
    fake = Fake([issue(82, at="t1"), issue(83, at="t2")])
    checks: list[int] = []
    second = threading.Event()

    def run(cmd: list[str], **kw: Any) -> Any:
        if cmd == ["gh", "issue", "edit", "83", "--add-label", "harness-run", "-R", cfg["repo"]]:
            checks.append(1)
            if len(checks) == 1:  # a transient failure
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": "x"})()
        return fake(cmd, **kw)

    started: list[int] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        started.append(n)
        if n == 82:
            second.wait(10)  # 82 runs until 83 has started
        else:
            second.set()
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "run_cmd", run)
    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert started == [82, 83] and len(checks) == 2
    own_reports(fake, [82, 83])


def test_a_small_request_starts_as_soon_as_it_fits(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A (12 runs, 12 workers) at 10 runs left frees 2: a 2-worker request needs only 2."""
    Polls(monkeypatch)
    fake = Fake([issue(84, body=block(profiles=TWO, seeds="6", workers="12"), at="t1"),
                 issue(85, body=block(workers="2"), at="t2")])  # fmt: skip
    monkeypatch.setattr(hq, "run_cmd", fake)
    b_started = threading.Event()
    starts: list[tuple[int, int, int]] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        starts.append((n, req["workers"], hq.runs_left(out_of(c, 84), 12)))
        if n == 84:
            write_runs(out_of(c, n), 2)
            b_started.wait(10)
            write_runs(out_of(c, n), 12)
        else:
            b_started.set()
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert starts == [(84, 12, 12), (85, 2, 10)]
    own_reports(fake, [84, 85])


def stale_job(cfg: dict[str, Any], n: int, req: dict[str, Any] | None, at: str) -> Any:
    """A `harness-running` issue cut off by a crash: its records, results dir and no runs yet."""
    out_of(cfg, n).mkdir(parents=True)
    hq.running_file(cfg, n).write_text(SHA)
    if req is not None:
        hq.request_file(cfg, n).write_text(json.dumps(req))
    s = stale_issue(n)
    s["createdAt"] = at
    return s


def test_recovery_posts_and_fails_first_then_resumes_within_the_budget(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two 12-worker resumes with 0 runs: the second waits in Jobs.start until the first has 6
    runs left, gets 6 workers, and both then run at once. A late report (#102) and a failure
    (#103), listed after them, are done before any resume starts (two passes)."""
    polls = Polls(monkeypatch)
    big = hq.parse_block(block(profiles=TWO, seeds="6", workers="12"), cfg, NAMES)
    late = out_of(cfg, 102)
    issues = [stale_job(cfg, 100, big, "t1"), stale_job(cfg, 101, big, "t2"),
              stale_job(cfg, 102, None, "t3"), stale_job(cfg, 103, None, "t4")]  # fmt: skip
    (late / "report.md").write_text("# LATE 102")
    (late / hq.FINISHED).write_text(str(len("# LATE 102")))
    fake = Fake(issues)
    monkeypatch.setattr(hq, "run_cmd", fake)
    b_started = threading.Event()
    seen: list[Any] = []

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        out = out_of(c, n)
        if n == 100:
            seen.append(("pass 1 done", any("# LATE 102" in s for s in fake.stdin),
                         fake.names(fake.issues[3])))  # fmt: skip
            write_runs(out, 5)  # 7 left: 5 free, under 6
            polls.after(5)
            seen.append(("early", b_started.is_set()))
            write_runs(out, 6)  # 6 left: 6 free
            seen.append(("both running", b_started.wait(10)))
            write_runs(out, 12)
        else:
            seen.append((n, resume, req["workers"], hq.runs_left(out_of(c, 100), 12)))
            b_started.set()  # after the record, so the order of `seen` is fixed
            write_runs(out, 12)
        return finish(c, n, out)

    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert seen == [
        ("pass 1 done", True, ["harness-failed"]),
        ("early", False),
        (101, True, 6, 6),  # waited for 6 free, got 6 of the 12 it asked for
        ("both running", True),
    ]
    for n in (100, 101, 102):
        i = next(i for i in fake.issues if i["number"] == n)
        assert fake.names(i) == ["harness-done"]
    assert sum("# REPORT 100" in s for s in fake.stdin) == 1
    assert sum("# REPORT 101" in s for s in fake.stdin) == 1


def test_a_resumed_issue_relabelled_harness_run_is_not_picked_again(
    cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    polls = Polls(monkeypatch)
    fake = Fake([stale_job(cfg, 104, hq.parse_block(block(), cfg, NAMES), "t1")])
    monkeypatch.setattr(hq, "run_cmd", fake)

    def _exec(
        c: dict[str, Any], n: int, req: dict[str, Any], resume: bool = False
    ) -> tuple[int, Path, Path]:
        fake.issues[0]["labels"].append({"name": "harness-run"})  # someone adds it mid-run
        polls.after(3)  # the tick relists meanwhile
        return finish(c, n, out_of(c, n))

    monkeypatch.setattr(hq, "execute", _exec)
    hq.run_once(cfg, False)
    assert not any("Refused" in s for s in fake.stdin)
    assert fake.edits() == [("104", "harness-done", "harness-running")]
    assert sum("# REPORT 104" in s for s in fake.stdin) == 1
