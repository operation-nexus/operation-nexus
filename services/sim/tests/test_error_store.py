"""NX-392 (NX-364 part 2): fingerprint, local store, store reporter, issue sync (EP-8, EP-9)."""

import http.client
import io
import json
import logging
import sqlite3
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nexus.errors import sync as sync_module
from nexus.errors.adapters.log import LogReporter
from nexus.errors.adapters.stored import StoreReporter
from nexus.errors.factory import make_reporter
from nexus.errors.fingerprint import fingerprint
from nexus.errors.store import MAX_FINGERPRINTS, Store
from nexus.errors.sync import GitHubClient, SyncError, _NoRedirect, main, run_sync

TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"  # noqa: S105 - a fake token for leak tests
CHAT_LINE = "!spawn strike fighter at the east base please"
USERNAME = "SomeViewer_99"
T0 = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
REPO = "example-org/example-ops"


def frame(file: str, function: str, line: int = 1) -> dict[str, object]:
    return {"file": file, "line": line, "function": function}


def raise_from(filename: str, function: str, message: str, exc: type[Exception]) -> Exception:
    """Raise `exc` from a function whose code claims to live in `filename`."""
    namespace: dict[str, object] = {}
    exec(compile(f"def {function}():\n    raise EXC(MSG)\n", filename, "exec"), namespace)  # noqa: S102
    namespace.update(EXC=exc, MSG=message)
    try:
        namespace[function]()  # type: ignore[operator]  # defined by the exec above
    except Exception as e:  # noqa: BLE001 - the test wants the instance
        return e
    raise AssertionError("unreachable")


def nexus_error(
    message: str = "boom", exc: type[Exception] = ValueError, function: str = "step"
) -> Exception:
    return raise_from("/home/u/src/nexus/runtime/loop.py", function, message, exc)


# --- fingerprint ---------------------------------------------------------------------------


def test_fingerprint_ignores_line_numbers_but_not_function_type_or_component() -> None:
    base = fingerprint("sim.step", "builtins.ValueError", [frame("nexus/a.py", "f", 10)])
    assert len(base) == 16 and int(base, 16) >= 0
    assert fingerprint("sim.step", "builtins.ValueError", [frame("nexus/a.py", "f", 99)]) == base
    assert fingerprint("sim.step", "builtins.KeyError", [frame("nexus/a.py", "f")]) != base
    assert fingerprint("sim.other", "builtins.ValueError", [frame("nexus/a.py", "f")]) != base
    assert fingerprint("sim.step", "builtins.ValueError", [frame("nexus/a.py", "g")]) != base
    assert fingerprint("sim.step", "builtins.ValueError", [frame("nexus/b.py", "f")]) != base


def test_fingerprint_uses_only_the_innermost_five_in_package_frames() -> None:
    inner = [frame(f"nexus/m{i}.py", f"f{i}") for i in range(5)]
    outside = frame("test_x.py", "t")
    outer = frame("nexus/outer.py", "o")
    plain = fingerprint("c", "t", inner)
    assert fingerprint("c", "t", [outer, *inner]) == plain  # a 6th frame out is ignored
    assert fingerprint("c", "t", [outside, *inner, outside]) == plain  # non-package ignored
    assert fingerprint("c", "t", [*inner[1:], frame("nexus/m9.py", "f9")]) != plain
    # worked values from `printf ... | sha256sum`, outside the implementation
    assert fingerprint("c", "t", [outside]) == "67694584ab41057a"
    assert fingerprint("c", "t", [frame("nexus/a.py", "f")]) == "3012513081de2a85"


# --- store ---------------------------------------------------------------------------------


def test_store_round_trip_counts_and_keeps_the_last_sample(tmp_path: Path) -> None:
    store = Store(tmp_path / "sub" / "errors.db")
    kw = {"exc_type": "builtins.ValueError", "component": "sim.step", "release": None}
    store.record("fp1", sample={"n": 1}, now=T0, **kw)  # type: ignore[arg-type]
    store.record("fp1", sample={"n": 2}, now=T0 + timedelta(minutes=5), **kw)  # type: ignore[arg-type]
    (entry,) = store.pending()
    assert entry.seen_count == 2 and entry.sample == {"n": 2}
    assert entry.first_seen == T0 and entry.last_seen == T0 + timedelta(minutes=5)
    assert entry.first_seen.tzinfo is not None and entry.release is None
    assert entry.issue_number is None and entry.synced_count == 0
    store.mark_synced("fp1", 7, 2, T0)
    assert store.pending() == []
    store.record("fp1", sample={"n": 3}, now=T0, **kw)  # type: ignore[arg-type]
    (again,) = store.pending()
    assert again.issue_number == 7 and again.synced_count == 2 and again.seen_count == 3


def test_store_write_failure_logs_the_type_and_does_not_raise(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    store = Store(blocker / "errors.db")  # parent is a file: unwritable
    with caplog.at_level(logging.WARNING, logger="nexus.errors"):
        store.record("fp", exc_type="t", component="c", sample={}, release=None, now=T0)
    assert any("capture lost" in r.getMessage() for r in caplog.records)
    assert str(blocker) not in caplog.text


def test_store_is_bounded(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    store = Store(tmp_path / "e.db")
    for i in range(MAX_FINGERPRINTS):
        store.record(f"fp{i}", exc_type="t", component="c", sample={}, release=None, now=T0)
    with caplog.at_level(logging.WARNING, logger="nexus.errors"):
        store.record("one-more", exc_type="t", component="c", sample={}, release=None, now=T0)
        store.record("fp0", exc_type="t", component="c", sample={}, release=None, now=T0)
    assert len(store.pending()) == MAX_FINGERPRINTS
    assert [e.seen_count for e in store.pending() if e.fp == "fp0"] == [2]  # known ones still count
    assert sum("store full" in r.getMessage() for r in caplog.records) == 1


# --- reporter ------------------------------------------------------------------------------


def test_reporter_records_and_logs_with_allowlisted_sample_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = Store(tmp_path / "e.db")
    reporter = StoreReporter(store, LogReporter("production"), "v1.2", lambda: T0)
    tags = {"tick": "42", "chat": CHAT_LINE}
    exc = nexus_error(f"{TOKEN} {CHAT_LINE} {USERNAME}")
    with caplog.at_level(logging.ERROR, logger="nexus.errors"):
        reporter.capture(exc, component="sim.step", tags=tags)
        reporter.capture(nexus_error("other text"), component="sim.step", tags={})
    assert len(caplog.records) == 2  # the delegate still logs
    (entry,) = store.pending()  # same fingerprint twice: the message is not part of it
    assert entry.seen_count == 2 and entry.release == "v1.2"
    assert entry.exc_type == "builtins.ValueError" and entry.component == "sim.step"
    assert set(entry.sample) == {"exc_type", "frames", "component", "tags"}
    frames = entry.sample["frames"]
    assert frames[-1] == {"file": "nexus/runtime/loop.py", "line": 2, "function": "step"}  # type: ignore[index]
    stored = json.dumps(entry.sample)
    for secret in (TOKEN, CHAT_LINE, USERNAME):
        assert secret not in stored


def test_factory_wires_the_store_only_when_the_env_names_one(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="nexus.errors"):
        off = make_reporter({})
    assert "error store is off: NEXUS_ERRORS_DB is not set" in caplog.text
    assert not isinstance(off, StoreReporter)
    db = tmp_path / "e.db"
    on = make_reporter({"NEXUS_ERRORS_DB": str(db), "NEXUS_RELEASE": "r1", "SENTRY_DSN": "x"})
    assert isinstance(on, StoreReporter)
    on.capture(nexus_error(), component="sim.step", tags={})
    assert [e.release for e in Store(db).pending()] == ["r1"]
    unreleased = make_reporter({"NEXUS_ERRORS_DB": str(db), "NEXUS_RELEASE": CHAT_LINE})
    unreleased.capture(nexus_error(function="other"), component="sim.step", tags={})
    assert {e.release for e in Store(db).pending()} == {"r1", None}


# --- sync ----------------------------------------------------------------------------------


class FakeClient:
    """Records calls; models each issue's open/closed state."""

    def __init__(self) -> None:
        self.issues: dict[int, dict[str, str]] = {}
        self.comments: list[tuple[int, str]] = []
        self.calls: list[str] = []
        self.fail_on: str | None = None

    def _maybe_fail(self, call: str) -> None:
        self.calls.append(call)
        if self.fail_on == call:
            raise SyncError(f"GitHub {call} returned HTTP 500")

    def create_issue(self, title: str, body: str) -> int:
        self._maybe_fail("create")
        number = len(self.issues) + 1
        self.issues[number] = {"title": title, "body": body, "state": "open"}
        return number

    def comment(self, number: int, body: str) -> None:
        self._maybe_fail("comment")
        self.comments.append((number, body))

    def reopen(self, number: int) -> None:
        self._maybe_fail("reopen")
        self.issues[number]["state"] = "open"

    def update_body(self, number: int, body: str) -> None:
        self._maybe_fail("update_body")
        self.issues[number]["body"] = body


def capture_n(store: Store, n: int, function: str = "step", now: datetime = T0) -> None:
    reporter = StoreReporter(store, LogReporter(), None, lambda: now)
    for _ in range(n):
        reporter.capture(nexus_error(function=function), component="sim.step", tags={"tick": "1"})


def test_two_captures_one_fingerprint_make_one_issue(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    capture_n(store, 2)
    assert run_sync(store, client, T0, 10) == 0
    (issue,) = client.issues.values()
    assert issue["title"] == "error: `builtins.ValueError` in sim.step"
    first, _, rest = issue["body"].partition("\n")
    assert first.startswith("Fingerprint: local:") and len(first) == len("Fingerprint: local:") + 16
    assert "Count: 2" in rest and "Release: none recorded" in rest
    assert "First seen: 2026-10-23T12:00:00+00:00" in rest and '"function": "step"' in rest
    assert run_sync(store, client, T0 + timedelta(hours=5), 10) == 0  # nothing new: nothing sent
    assert len(client.issues) == 1 and client.comments == []


def test_recurrence_after_close_reopens_and_comments_once_an_hour(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    capture_n(store, 1)
    run_sync(store, client, T0, 10)
    client.issues[1]["state"] = "closed"
    later = T0 + timedelta(hours=2)
    capture_n(store, 1, now=later)
    run_sync(store, client, later, 10)
    assert client.issues[1]["state"] == "open" and len(client.issues) == 1
    assert len(client.comments) == 1
    assert (
        "Count: 2" in client.comments[0][1] and "2026-10-23T14:00:00+00:00" in client.comments[0][1]
    )
    # a third capture 30 minutes later: throttled, no second comment, still pending
    capture_n(store, 1, now=later + timedelta(minutes=30))
    run_sync(store, client, later + timedelta(minutes=30), 10)
    assert len(client.comments) == 1 and len(store.pending()) == 1
    run_sync(store, client, later + timedelta(minutes=61), 10)
    assert len(client.comments) == 2 and "Count: 3" in client.comments[1][1]
    assert store.pending() == []


def test_flood_cap_makes_ten_issues_and_one_flood_issue(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    for i in range(12):
        capture_n(store, 1 + (i == 11), f"fn{i:02d}", T0 + timedelta(seconds=i))
    run_sync(store, client, T0, 10)
    titles = [i["title"] for i in client.issues.values()]
    assert titles.count("error: `builtins.ValueError` in sim.step") == 10
    assert titles.count("error: flood") == 1 and len(titles) == 11
    flood = next(i for i in client.issues.values() if i["title"] == "error: flood")
    lines = flood["body"].splitlines()
    assert lines[0] == "Fingerprint: local:flood"
    entries = [line for line in lines if line.startswith("- local:")]
    assert len(entries) == 2 and sorted(e.rsplit(": ", 1)[1] for e in entries) == ["1", "2"]
    assert len(store.pending()) == 2  # the overflow stays pending
    # next run, within the hour: the flood issue is not rewritten, but new issues drain the overflow
    run_sync(store, client, T0 + timedelta(minutes=1), 10)
    assert len(client.issues) == 13 - 0 and store.pending() == []
    assert sum(i["title"] == "error: flood" for i in client.issues.values()) == 1


def test_flood_issue_is_updated_and_reopened_after_an_hour(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    for i in range(3):
        capture_n(store, 1, function=f"fn{i}")
    run_sync(store, client, T0, 1)
    flood_no = next(n for n, i in client.issues.items() if i["title"] == "error: flood")
    client.issues[flood_no]["state"] = "closed"
    run_sync(store, client, T0 + timedelta(minutes=10), 0)  # throttled
    assert client.issues[flood_no]["state"] == "closed"
    run_sync(store, client, T0 + timedelta(hours=1, minutes=1), 0)
    assert client.issues[flood_no]["state"] == "open"
    assert client.issues[flood_no]["body"].count("- local:") == 2


def test_failed_call_leaves_store_unchanged_and_next_run_retries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    capture_n(store, 1)
    client.fail_on = "create"
    assert run_sync(store, client, T0, 10) == 1
    (entry,) = store.pending()
    assert entry.issue_number is None and entry.synced_count == 0
    assert "HTTP 500" in capsys.readouterr().err
    client.fail_on = None
    assert run_sync(store, client, T0, 10) == 0 and len(client.issues) == 1


def test_failed_update_is_not_marked_synced(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    capture_n(store, 1)
    run_sync(store, client, T0, 10)
    capture_n(store, 1, now=T0 + timedelta(hours=2))
    client.fail_on = "comment"
    assert run_sync(store, client, T0 + timedelta(hours=2), 10) == 1
    (entry,) = store.pending()
    assert entry.synced_count == 1 and entry.synced_at == T0


def test_no_token_chat_line_or_username_reaches_any_issue_or_comment(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    secrets = (TOKEN, CHAT_LINE, USERNAME)
    reporter = StoreReporter(store, LogReporter(), None, lambda: T0)
    message = " ".join(secrets)
    bad_tags = {"tick": "1", "chat": CHAT_LINE, "user": USERNAME + " says hi", TOKEN: "x"}
    for _ in range(2):
        reporter.capture(nexus_error(message), component="sim.step", tags=bad_tags)
    reporter.capture(nexus_error(message, function="two"), component=CHAT_LINE, tags=bad_tags)
    run_sync(store, client, T0, 10)
    reporter.capture(nexus_error(message), component="sim.step", tags=bad_tags)
    run_sync(store, client, T0 + timedelta(hours=2), 10)
    text = json.dumps([client.issues, client.comments])
    assert len(client.issues) == 2 and len(client.comments) == 1
    for secret in (*secrets, "oauth", "spawn"):
        assert secret not in text
    assert "tick" in text  # the id-shaped tag did get through


# --- CLI and GitHub client -----------------------------------------------------------------


def seeded_db(tmp_path: Path) -> Path:
    store = Store(tmp_path / "e.db")
    capture_n(store, 2)
    return store.path


def test_dry_run_prints_the_plan_needs_no_token_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = seeded_db(tmp_path)
    env = {"NEXUS_ERRORS_DB": str(db), "NEXUS_ERRORS_REPO": REPO}
    assert main(["--dry-run"], env=env, clock=lambda: T0) == 0
    assert (
        capsys.readouterr().out == "would create issue: error: `builtins.ValueError` in sim.step\n"
    )
    assert len(Store(db).pending()) == 1  # still pending: nothing marked


def test_main_requires_config_and_token_and_never_prints_the_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = seeded_db(tmp_path)
    assert main([], env={}) == 2
    assert main([], env={"NEXUS_ERRORS_DB": str(db)}) == 2  # no code default for the repo
    assert main([], env={"NEXUS_ERRORS_DB": str(db), "NEXUS_ERRORS_REPO": "a b/c"}) == 2
    assert main([], env={"NEXUS_ERRORS_DB": str(db), "NEXUS_ERRORS_REPO": REPO}) == 2
    assert "NEXUS_ERRORS_GH_TOKEN is required" in capsys.readouterr().err
    missing = {"NEXUS_ERRORS_DB": str(tmp_path / "none.db"), "NEXUS_ERRORS_REPO": REPO}
    assert main([], env=missing) == 0  # no store yet: nothing to do


def test_main_runs_with_an_injected_client_and_reports_failure_as_exit_1(tmp_path: Path) -> None:
    db = seeded_db(tmp_path)
    env = {"NEXUS_ERRORS_DB": str(db), "NEXUS_ERRORS_REPO": REPO}
    client = FakeClient()
    client.fail_on = "create"
    assert main([], env=env, client=client, clock=lambda: T0) == 1
    client.fail_on = None
    assert main(["--max-new", "0"], env=env, client=client, clock=lambda: T0) == 0
    assert [i["title"] for i in client.issues.values()] == ["error: flood"]
    with pytest.raises(SystemExit):
        main(["--max-new", "-1"], env=env, client=client)


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def patch_urlopen(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[urllib.request.Request], object]
) -> list[urllib.request.Request]:
    seen: list[urllib.request.Request] = []

    def fake(request: urllib.request.Request, timeout: float) -> object:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(sync_module._OPENER, "open", fake)
    return seen


def test_github_client_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = patch_urlopen(monkeypatch, lambda r: FakeResponse(b'{"number": 12}'))
    client = GitHubClient(REPO, TOKEN)
    assert client.create_issue("t", "b") == 12
    client.comment(12, "c")
    client.reopen(12)
    client.update_body(12, "nb")
    create, comment, reopen, update = seen
    base = f"https://api.github.com/repos/{REPO}/issues"
    assert (create.get_method(), create.full_url) == ("POST", base)
    assert json.loads(create.data) == {"title": "t", "body": "b", "labels": ["error"]}  # type: ignore[arg-type]
    assert (comment.get_method(), comment.full_url) == ("POST", f"{base}/12/comments")
    assert (reopen.get_method(), reopen.full_url) == ("PATCH", f"{base}/12")
    assert json.loads(reopen.data) == {"state": "open"}  # type: ignore[arg-type]
    assert json.loads(update.data) == {"body": "nb"}  # type: ignore[arg-type]
    for request in seen:
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        assert TOKEN not in request.full_url


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError("https://x", 401, f"bad {TOKEN}", None, None),  # type: ignore[arg-type]
        urllib.error.URLError(f"unreachable {TOKEN}"),
        TimeoutError(TOKEN),
    ],
)
def test_token_never_leaks_through_an_api_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    failure: Exception,
) -> None:
    def boom(request: urllib.request.Request) -> object:
        raise failure

    patch_urlopen(monkeypatch, boom)
    with pytest.raises(SyncError) as caught:
        GitHubClient(REPO, TOKEN).create_issue("t", "b")
    assert TOKEN not in str(caught.value) and caught.value.__cause__ is None
    assert caught.value.__suppress_context__
    env = {
        "NEXUS_ERRORS_DB": str(seeded_db(tmp_path)),
        "NEXUS_ERRORS_REPO": REPO,
        "NEXUS_ERRORS_GH_TOKEN": TOKEN,
    }
    assert main([], env=env, clock=lambda: T0) == 1
    out, err = capsys.readouterr()
    assert TOKEN not in out + err + caplog.text
    assert len(Store(Path(env["NEXUS_ERRORS_DB"])).pending()) == 1


def test_bad_json_reply_is_a_sync_error(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_urlopen(monkeypatch, lambda r: FakeResponse(b"not json"))
    with pytest.raises(SyncError):
        GitHubClient(REPO, TOKEN).create_issue("t", "b")
    patch_urlopen(monkeypatch, lambda r: FakeResponse(b'{"number": "x"}'))
    with pytest.raises(SyncError):
        GitHubClient(REPO, TOKEN).create_issue("t", "b")


# --- fix round 1 ---------------------------------------------------------------------------

CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"


def test_corrupt_store_exits_1_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "e.db"
    db.write_bytes(b"this is not a sqlite file" * 100)
    env = {"NEXUS_ERRORS_DB": str(db), "NEXUS_ERRORS_REPO": REPO, "NEXUS_ERRORS_GH_TOKEN": TOKEN}
    assert main([], env=env, client=FakeClient(), clock=lambda: T0) == 1
    err = capsys.readouterr().err
    assert "DatabaseError" in err and "Traceback" not in err and TOKEN not in err


def test_mark_synced_failure_after_create_is_reported_with_fingerprint_and_issue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    capture_n(store, 1)
    (entry,) = store.pending()

    def broken(*args: object) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "mark_synced", broken)
    assert run_sync(store, client, T0, 10) == 1
    err = capsys.readouterr().err
    assert f"issue #1 for local:{entry.fp} was written but the store update failed" in err
    assert "OperationalError" in err and "may post it again" in err
    assert len(client.issues) == 1


class IncompleteReadClient(FakeClient):
    def create_issue(self, title: str, body: str) -> int:
        raise http.client.IncompleteRead(b"partial")


def test_incomplete_read_counts_as_one_failed_item_and_the_rest_continue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = Store(tmp_path / "e.db")
    capture_n(store, 1, "a", T0)
    assert run_sync(store, IncompleteReadClient(), T0, 10) == 1
    assert "IncompleteRead" in capsys.readouterr().err and len(store.pending()) == 1


def test_github_client_turns_a_half_read_reply_into_a_sync_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(request: urllib.request.Request) -> object:
        raise http.client.BadStatusLine("x")

    patch_urlopen(monkeypatch, boom)
    with pytest.raises(SyncError, match="BadStatusLine"):
        GitHubClient(REPO, TOKEN).comment(1, "c")


def test_redirects_are_refused_and_the_token_is_not_resent(monkeypatch: pytest.MonkeyPatch) -> None:
    hits: list[str] = []

    class FakeHTTPS(urllib.request.HTTPSHandler):
        def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
            hits.append(req.full_url)
            resp = urllib.response.addinfourl(
                io.BytesIO(b""), http.client.HTTPMessage(), req.full_url, 302
            )
            resp.headers["Location"] = "https://elsewhere.invalid/x"
            resp.msg = "Found"  # type: ignore[attr-defined]  # urllib reads .msg
            return resp  # type: ignore[return-value]  # a stand-in with the same read API

    monkeypatch.setattr(sync_module, "_OPENER", urllib.request.build_opener(_NoRedirect, FakeHTTPS))
    with pytest.raises(SyncError, match="HTTP 302") as caught:
        GitHubClient(REPO, TOKEN).create_issue("t", "b")
    assert len(hits) == 1 and "elsewhere" not in hits[0] and TOKEN not in str(caught.value)


@pytest.mark.parametrize("repo", ["../..", "a/..", "./x", "../x", "a/.", "a", "a/b/c", "a b/c", ""])
def test_repo_must_be_owner_slash_name_without_dot_segments(
    tmp_path: Path, repo: str, capsys: pytest.CaptureFixture[str]
) -> None:
    env = {"NEXUS_ERRORS_DB": str(seeded_db(tmp_path)), "NEXUS_ERRORS_REPO": repo}
    assert main(["--dry-run"], env=env) == 2
    ok = {**env, "NEXUS_ERRORS_REPO": "a.b/c-d_e.f"}
    assert main(["--dry-run"], env=ok, clock=lambda: T0) == 0


def test_tags_are_typed_per_key_and_unknown_or_malformed_values_are_dropped() -> None:
    from nexus.errors.adapters.log import allowlisted_fields

    tags = {
        "tick": "42",
        "campaign_id": CAMPAIGN,
        "viewer": "SomeViewer_99",  # unknown key, name-shaped value
        "node": "ghp_abcdefghijklmnopqrstuvwxyz0123456789",  # unknown key, token-shaped
        "entity": "a" * 40,  # unknown key, 40 hex
    }
    fields = allowlisted_fields(nexus_error(), component="sim.step", tags=tags)
    assert fields["tags"] == {"tick": "42", "campaign_id": CAMPAIGN}
    assert fields["tags_dropped"] == 3
    for bad in (
        {"tick": "4x"},
        {"tick": "SomeViewer_99"},
        {"tick": "1" * 13},
        {"tick": ""},
        {"campaign_id": "SomeViewer_99"},
        {"campaign_id": CAMPAIGN.upper()},
        {"campaign_id": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"},
    ):
        got = allowlisted_fields(nexus_error(), component="sim.step", tags=bad)
        assert got["tags"] == {} and got["tags_dropped"] == 1, bad


def test_unset_or_bad_release_warns_once_without_the_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    env = {"NEXUS_ERRORS_DB": str(tmp_path / "e.db"), "NEXUS_RELEASE": CHAT_LINE}
    with caplog.at_level(logging.WARNING, logger="nexus.errors.factory"):
        make_reporter(env)
        make_reporter({**env, "NEXUS_RELEASE": "v1"})
    assert sum("NEXUS_RELEASE" in r.getMessage() for r in caplog.records) == 1
    assert CHAT_LINE not in caplog.text


def test_exception_type_is_backticked_in_title_and_body(tmp_path: Path) -> None:
    store, client = Store(tmp_path / "e.db"), FakeClient()
    capture_n(store, 1)
    run_sync(store, client, T0, 10)
    (issue,) = client.issues.values()
    assert "`builtins.ValueError`" in issue["title"]
    assert "Exception: `builtins.ValueError`" in issue["body"]
