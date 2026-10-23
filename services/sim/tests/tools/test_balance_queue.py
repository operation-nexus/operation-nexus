"""Local harness run queue tests (NX-381, Q-OPS-14; tools/balance/harness_queue.py).

`gh` and `git` are faked at the one subprocess boundary (`run_cmd`). The fake `gh issue list`
output uses only fields `gh issue list --json` has: number, title, body, author{login},
labels[{name}] and createdAt.
"""

import fcntl
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

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


def issue(n: int, author: str = "canthony224", body: str | None = None, at: str = "t1") -> Any:
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
            out = json.dumps(self.issues)
        if cmd[:2] == ["gh", "issue"] and stdin:
            self.stdin.append(stdin)
        rc = 1 if cmd[:3] == ["git", "merge-base", "--is-ancestor"] and not self.ancestor else 0
        return type("R", (), {"returncode": rc, "stdout": out, "stderr": ""})()

    def edits(self) -> list[tuple[str, str, str]]:
        return [
            (c[3], c[c.index("--add-label") + 1], c[c.index("--remove-label") + 1])
            for c in self.calls
            if c[:3] == ["gh", "issue", "edit"]
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


def test_dry_run_changes_nothing(cfg: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake([issue(6), issue(7, body="junk")])
    monkeypatch.setattr(hq, "run_cmd", fake)
    hq.run_once(cfg, True)
    assert not fake.edits() and not fake.stdin
    assert not any(c[:2] == ["git", "worktree"] for c in fake.calls)


def fake_exec(rc: int, report: str | None, logtext: str = "") -> Any:
    def _exec(c: dict[str, Any], n: int, req: dict[str, Any]) -> tuple[int, Path, Path]:
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
    assert [e[1] for e in fake.edits()] == ["harness-running", "harness-failed"] * 2
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


@pytest.mark.parametrize(
    "value",
    ["a=1,b=2,c=3,d=4,e=5", "A.b=1", "a..b=1", "a=1;rm", "a=1e9", "a=$(x)", "a=", "a=1234567890"],
)
def test_set_refusals(cfg: dict[str, Any], value: str) -> None:
    with pytest.raises(hq.Refusal, match="bad value for key: set"):
        hq.parse_block(block(set=value), cfg, NAMES)
