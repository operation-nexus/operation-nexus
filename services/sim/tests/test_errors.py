"""NX-364 part 1: ErrorReporter port, no-op and log adapters, factory (EP-1, EP-3, EP-7)."""

import logging

import pytest

from nexus.errors import report_safely
from nexus.errors.adapters.log import LogReporter, short_path
from nexus.errors.adapters.noop import NoOpReporter
from nexus.errors.factory import make_reporter
from nexus.obs import JsonFormatter

LEAKED = "oauth:abcdefghijklmnopqrstuvwxyz0123"
CHAT_LINE = "!spawn strike fighter at the east base please"
USERNAME = "SomeViewer_99"
CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"


def explode() -> None:
    raise ValueError(f"{LEAKED} {CHAT_LINE} {USERNAME}")


def raised() -> ValueError:
    try:
        explode()
    except ValueError as e:
        return e
    raise AssertionError("unreachable")


def test_factory_without_dsn_is_noop_and_says_it_is_off(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="nexus.errors"):
        assert isinstance(make_reporter({}), NoOpReporter)
        assert isinstance(make_reporter({"SENTRY_DSN": ""}), NoOpReporter)
    assert [r.getMessage() for r in caplog.records].count(
        "error reporting is off: SENTRY_DSN is not set"
    ) == 2


def test_factory_with_dsn_falls_back_to_log_visibly_and_never_logs_the_dsn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dsn = "https://publickey@o0.example.invalid/1"
    with caplog.at_level(logging.INFO, logger="nexus.errors"):
        reporter = make_reporter({"SENTRY_DSN": dsn, "NEXUS_ENV": "staging"})
    assert isinstance(reporter, LogReporter) and reporter.environment == "staging"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "not built yet" in warnings[0].getMessage()
    assert dsn not in caplog.text and "publickey" not in caplog.text


def test_factory_reads_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", "https://k@example.invalid/1")
    assert isinstance(make_reporter(), LogReporter)
    monkeypatch.delenv("SENTRY_DSN")
    assert isinstance(make_reporter(), NoOpReporter)


def test_log_line_has_only_allowlisted_fields(caplog: pytest.LogCaptureFixture) -> None:
    tags = {
        "tick": "42",
        "campaign_id": CAMPAIGN,
        "chat": CHAT_LINE,  # value fails the id pattern
        "user": USERNAME + " says hi",  # value fails the id pattern
        LEAKED: "x",  # key fails the key pattern
    }
    with caplog.at_level(logging.ERROR, logger="nexus.errors"):
        LogReporter("production").capture(raised(), component="sim.step", tags=tags)
    (record,) = caplog.records
    fields = record.fields  # type: ignore[attr-defined]  # set by extra={"fields": ...}
    assert set(fields) == {"exc_type", "frames", "component", "tags", "tags_dropped", "environment"}
    assert fields["tags_dropped"] == 3
    assert fields["exc_type"] == "builtins.ValueError"
    assert fields["component"] == "sim.step"
    assert fields["environment"] == "production"
    assert fields["tags"] == {"tick": "42", "campaign_id": CAMPAIGN}
    assert [f["function"] for f in fields["frames"]] == ["raised", "explode"]
    assert all(set(f) == {"file", "line", "function"} for f in fields["frames"])
    rendered = JsonFormatter().format(record) + record.getMessage()
    for secret in (LEAKED, CHAT_LINE, USERNAME, "oauth", "spawn"):
        assert secret not in rendered


def test_no_drop_count_when_every_tag_is_kept(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="nexus.errors"):
        LogReporter().capture(raised(), component="sim.step", tags={"tick": "1"})
    assert "tags_dropped" not in caplog.records[0].fields  # type: ignore[attr-defined]  # extra


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("/home/alice/operation-nexus/src/nexus/runtime/loop.py", "nexus/runtime/loop.py"),
        (r"C:\Users\Alice\repo\services\sim\src\nexus\core\step.py", "nexus/core/step.py"),
        ("/home/alice/.local/lib/python3.12/json/decoder.py", "decoder.py"),
    ],
)
def test_paths_never_carry_a_home_directory(filename: str, expected: str) -> None:
    assert short_path(filename) == expected


def test_log_line_frames_use_short_paths(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="nexus.errors"):
        LogReporter().capture(raised(), component="sim.step", tags={})
    files = [f["file"] for f in caplog.records[0].fields["frames"]]  # type: ignore[attr-defined]
    assert files == ["test_errors.py", "test_errors.py"]  # outside the nexus package: basename


def test_log_line_ignores_a_chained_cause(caplog: pytest.LogCaptureFixture) -> None:
    try:
        try:
            explode()
        except ValueError as inner:
            raise RuntimeError(USERNAME) from inner
    except RuntimeError as e:
        with caplog.at_level(logging.ERROR, logger="nexus.errors"):
            LogReporter().capture(e, component="sim.step", tags={})
    rendered = JsonFormatter().format(caplog.records[0])
    assert LEAKED not in rendered and USERNAME not in rendered and "ValueError" not in rendered


def test_frames_are_capped_to_the_innermost(caplog: pytest.LogCaptureFixture) -> None:
    def recurse(depth: int) -> None:
        if depth == 0:
            explode()
        recurse(depth - 1)

    try:
        recurse(80)
    except ValueError as e:
        with caplog.at_level(logging.ERROR, logger="nexus.errors"):
            LogReporter().capture(e, component="sim.step", tags={})
    frames = caplog.records[0].fields["frames"]  # type: ignore[attr-defined]  # extra
    assert len(frames) == 50 and frames[-1]["function"] == "explode"


def test_bad_component_and_environment_are_dropped(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="nexus.errors"):
        reporter = LogReporter(CHAT_LINE)
        reporter.capture(raised(), component=CHAT_LINE, tags={})
    fields = caplog.records[0].fields  # type: ignore[attr-defined]  # extra
    assert reporter.environment is None and "environment" not in fields
    assert fields["component"] == "invalid"


class Raising:
    def capture(self, exc: BaseException, *, component: str, tags: dict[str, str]) -> None:
        raise RuntimeError(f"transport down {USERNAME}")

    def flush(self, timeout_s: float) -> None:
        return None


def test_raising_reporter_is_caught_and_logged_by_type_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="nexus.errors"):
        report_safely(Raising(), raised(), component="sim.step", tags={"tick": "1"})
    assert [r.getMessage() for r in caplog.records] == ["error reporter failed: RuntimeError"]
    assert USERNAME not in caplog.text
