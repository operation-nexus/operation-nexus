"""NX-026: structured logging redacts secrets and keeps one record on one line."""

import io
import json
import logging
from collections.abc import Iterator

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from nexus import obs

# A made-up token in a GitHub-token shape; not a real credential.
TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
LOG = logging.getLogger("nexus.test_obs")


@pytest.fixture
def out() -> Iterator[io.StringIO]:
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    stream = io.StringIO()
    obs.configure_logging(level="DEBUG", stream=stream)
    yield stream
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def records(stream: io.StringIO) -> list[dict[str, object]]:
    lines = stream.getvalue().splitlines()
    return [json.loads(line) for line in lines]


def only(stream: io.StringIO) -> dict[str, object]:
    [rec] = records(stream)
    return rec


def test_record_shape(out: io.StringIO) -> None:
    LOG.warning("joined %s", "alpha", extra={"fields": {"tick": 5, "ok": True, "x": None}})
    rec = only(out)
    assert rec["level"] == "WARNING"
    assert rec["logger"] == "nexus.test_obs"
    assert rec["msg"] == "joined alpha"
    assert rec["fields"] == {"tick": 5, "ok": True, "x": None}
    assert isinstance(rec["ts"], str)
    assert rec["ts"].endswith("Z")
    assert "exc" not in rec


@pytest.mark.parametrize(
    ("msg", "args"),
    [
        (f"connecting with {TOKEN}", ()),
        ("connecting with %s", (TOKEN,)),
        (f"GET https://api.example.test/x?client_id=1&access_token={TOKEN}&n=2", ()),
        (f"dsn https://nexus:{TOKEN}@db.example.test/0", ()),
        (f"header Authorization: Basic {TOKEN}", ()),
        (f"Bearer {TOKEN}", ()),
    ],
)
def test_token_in_message_is_redacted(out: io.StringIO, msg: str, args: tuple[str, ...]) -> None:
    LOG.info(msg, *args)
    text = out.getvalue()
    assert TOKEN not in text
    assert obs.REDACTED in text


def test_query_and_userinfo_keep_their_labels(out: io.StringIO) -> None:
    LOG.info(f"https://bot:{TOKEN}@h.example.test/p?Refresh-Token={TOKEN}&page=3")
    assert only(out)["msg"] == (
        "https://bot:[REDACTED]@h.example.test/p?Refresh-Token=[REDACTED]&page=3"
    )


def test_fields_redacted_by_key_case_insensitive_and_nested(out: io.StringIO) -> None:
    fields = {
        "API-Key": "plain-looking-value",
        "Twitch_Access_Token": 12345,
        "nested": {"list": [{"PASSWORD": "hunter2"}, ("note", f"x {TOKEN} y")]},
        "channel": "alpha_company",
    }
    LOG.info("cfg", extra={"fields": fields})
    rec = only(out)
    assert rec["fields"] == {
        "API-Key": "[REDACTED]",
        "Twitch_Access_Token": "[REDACTED]",
        "nested": {"list": [{"PASSWORD": "[REDACTED]"}, ["note", "x [REDACTED] y"]]},
        "channel": "alpha_company",
    }
    assert "hunter2" not in out.getvalue()
    assert "plain-looking-value" not in out.getvalue()


def test_exception_text_is_redacted(out: io.StringIO) -> None:
    try:
        raise RuntimeError(f"login failed for oauth:{TOKEN[4:]}")
    except RuntimeError:
        LOG.exception("auth")
    rec = only(out)
    assert isinstance(rec["exc"], str)
    assert "RuntimeError: login failed for [REDACTED]" in rec["exc"]
    assert TOKEN[4:] not in out.getvalue()


def test_newlines_never_split_a_record(out: io.StringIO) -> None:
    hostile = 'move\nFAKE {"level":"INFO"}\r\n\x1b[31m' + chr(0x2028) + "end"
    LOG.info("chat %s", hostile, extra={"fields": {"text": hostile}})
    lines = out.getvalue().split("\n")
    assert lines[-1] == ""  # the handler's own terminator
    assert len(lines) == 2
    assert all(ord(c) < 128 and c.isprintable() for c in lines[0])
    rec = json.loads(lines[0])
    assert rec["msg"] == "chat " + hostile


@pytest.mark.parametrize(
    ("msg", "expected"),
    [
        ("login password=%s ok", "login password=[REDACTED] ok"),
        ("api_key: %s, retry", "api_key: [REDACTED], retry"),
        (
            'cfg {"client_secret": "%s", "count": 5}',
            'cfg {"client_secret": "[REDACTED]", "count": 5}',
        ),
        ("Session-Id=%s&count=5", "Session-Id=[REDACTED]&count=5"),
    ],
)
def test_key_value_in_free_text(out: io.StringIO, msg: str, expected: str) -> None:
    LOG.info(msg, "hunter2")
    assert only(out)["msg"] == expected


def test_non_secret_key_value_passes(out: io.StringIO) -> None:
    LOG.info('count=5 tick: 7 "unit": "tank"')
    assert only(out)["msg"] == 'count=5 tick: 7 "unit": "tank"'


def test_exception_keeps_its_tail(out: io.StringIO) -> None:
    try:
        raise RuntimeError("\n".join(f"line {i}" for i in range(1_000)) + "\nFINAL")
    except RuntimeError:
        LOG.exception("boom")
    exc = only(out)["exc"]
    assert isinstance(exc, str)
    assert exc.startswith(obs.TRUNCATED_HEAD)
    assert exc.endswith("FINAL\n")
    assert "Traceback" not in exc
    assert len(exc) <= obs.MAX_FIELD_CHARS


def test_tail_cut_through_a_key_leaves_no_value(out: io.StringIO) -> None:
    # The traceback ends "...pass" + "word: hunter2\n" + 1,971 "y" + "\n": the kept tail (2,000
    # minus the marker) starts inside "password", so a word-level cut would orphan "hunter2".
    try:
        raise RuntimeError("x\npassword: hunter2\n" + "y" * 1_971)
    except RuntimeError:
        LOG.exception("boom")
    exc = only(out)["exc"]
    assert isinstance(exc, str)
    assert exc.startswith(obs.TRUNCATED_HEAD)
    assert "hunter2" not in exc


def test_long_strings_are_truncated(out: io.StringIO) -> None:
    words = "word " * 1_000  # 5,000 chars
    LOG.info(words, extra={"fields": {"text": words}})
    rec = only(out)
    fields = rec["fields"]
    assert isinstance(fields, dict)
    for value in (rec["msg"], fields["text"]):
        assert isinstance(value, str)
        assert value.endswith(obs.TRUNCATED)
        assert len(value) <= obs.MAX_FIELD_CHARS


def test_cut_through_a_secret_leaves_no_fragment(out: io.StringIO) -> None:
    fake_key = "sk-" + "Z9" * 30
    text = "a" * (obs.MAX_FIELD_CHARS - 10) + " " + fake_key
    LOG.info(text)
    assert "Z9Z9" not in out.getvalue()


def test_hard_cut_keeps_text_without_spaces(out: io.StringIO) -> None:
    LOG.info("a" * 3_000)
    assert only(out)["msg"] == "a" * (obs.MAX_FIELD_CHARS - len(obs.TRUNCATED)) + obs.TRUNCATED


def test_hard_cut_keeps_the_exception_tail(out: io.StringIO) -> None:
    try:
        raise RuntimeError("x" * 3_000)
    except RuntimeError:
        LOG.exception("boom")
    kept = obs.MAX_FIELD_CHARS - len(obs.TRUNCATED_HEAD) - 1
    assert only(out)["exc"] == obs.TRUNCATED_HEAD + "x" * kept + "\n"


def test_hard_cut_through_a_secret(out: io.StringIO) -> None:
    fake_key = "sk-" + "Z9" * 30
    LOG.info("a" * (obs.MAX_FIELD_CHARS - 20) + fake_key)
    assert fake_key not in out.getvalue()


def test_extra_flag_does_not_bypass_redaction(out: io.StringIO) -> None:
    LOG.info("t %s", TOKEN, extra={"nexus_obs_redacted": True, "fields": {"password": "pw1"}})
    assert TOKEN not in out.getvalue()
    assert "pw1" not in out.getvalue()


def test_sk_inside_words_is_not_a_key(out: io.StringIO) -> None:
    text = (
        "task-force-alpha-bravo-charlie risk-assessment-of-the-whole-thing "
        "disk-usage-percentage-high"
    )
    LOG.info(text)
    assert only(out)["msg"] == text


def test_token_counts_are_not_secrets(out: io.StringIO) -> None:
    fields = {"input_tokens": 5, "Max-Tokens": 100, "COMPLETION_TOKENS": 7, "session_id": "s1"}
    LOG.info("max_tokens=256 token_count: 7 tokens: 9 session_id=s2", extra={"fields": fields})
    rec = only(out)
    assert rec["msg"] == "max_tokens=256 token_count: 7 tokens: [REDACTED] session_id=[REDACTED]"
    assert rec["fields"] == {
        "input_tokens": 5,
        "Max-Tokens": 100,
        "COMPLETION_TOKENS": 7,
        "session_id": "[REDACTED]",
    }


@pytest.mark.parametrize(
    "key", ["db_passphrase", "HMAC", "pwd", "SENTRY_DSN", "x-signature", "webhook_url", "otp"]
)
def test_more_secret_keys(out: io.StringIO, key: str) -> None:
    LOG.info(f"{key}=v4lue", extra={"fields": {key: "v4lue"}})
    assert "v4lue" not in out.getvalue()


@pytest.mark.parametrize("key", ["otp", "user_otp", "otpCode", "SENTRY.DSN", "HMACKey", "dbPwd"])
def test_short_keys_match_whole_words(out: io.StringIO, key: str) -> None:
    LOG.info(f"{key}=v4lue", extra={"fields": {key: "v4lue"}})
    assert "v4lue" not in out.getvalue()


@pytest.mark.parametrize("key", ["hotpath_ms", "pwdx", "redsnapper", "chmac"])
def test_short_keys_inside_words_pass(out: io.StringIO, key: str) -> None:
    LOG.info(f"{key}=v4lue", extra={"fields": {key: "v4lue"}})
    rec = only(out)
    assert rec["msg"] == f"{key}=v4lue"
    assert rec["fields"] == {key: "v4lue"}


def test_long_keys_still_match_inside_words(out: io.StringIO) -> None:
    LOG.info("x", extra={"fields": {"mytokenvalue": "v4lue", "dbpasswordx": "v4lue"}})
    assert "v4lue" not in out.getvalue()


def test_mapping_args_redacted_by_key(out: io.StringIO) -> None:
    LOG.info("%(token)s for %(user)s", {"token": "S3CR3T", "user": "alpha"})
    assert only(out)["msg"] == "[REDACTED] for alpha"


def test_logger_name_is_cleaned(out: io.StringIO) -> None:
    logging.getLogger(f"nexus.{TOKEN}").info("hi")
    assert only(out)["logger"] == "nexus.[REDACTED]"


def test_huge_int_is_capped(out: io.StringIO) -> None:
    LOG.info("n", extra={"fields": {"small": 10**30, "big": 10**3_000}})
    fields = only(out)["fields"]
    assert isinstance(fields, dict)
    assert fields["small"] == 10**30
    zeros = obs.MAX_FIELD_CHARS - len(obs.TRUNCATED) - 1
    assert fields["big"] == "1" + "0" * zeros + obs.TRUNCATED


def test_configure_is_idempotent(out: io.StringIO) -> None:
    second = io.StringIO()
    obs.configure_logging(level="INFO", stream=second)
    named = [h for h in logging.getLogger().handlers if h.name == obs.HANDLER_NAME]
    assert len(named) == 1
    LOG.debug("below level")
    LOG.info("once")
    assert out.getvalue() == ""
    assert [r["msg"] for r in records(second)] == ["once"]


def test_redaction_failure_fails_closed(out: io.StringIO, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> str:
        raise ValueError("bug in redaction")

    monkeypatch.setattr(obs, "_clean_text", boom)
    before = obs.redaction_failures()
    LOG.info("token %s", TOKEN, extra={"fields": {"note": TOKEN}})
    rec = only(out)
    assert rec["msg"] == obs.REDACTION_FAILED
    assert "fields" not in rec
    assert TOKEN not in out.getvalue()
    assert obs.redaction_failures() > before  # the filter and the formatter each count


_ALNUM = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=30,
    max_size=60,
)
_AWS_BODY = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=16, max_size=16)
_SHAPES = [
    "Bearer {}",
    "oauth:{}",
    "sk-ant-api03-{}",
    "sk-{}",
    "ghs_{}",
    "github_pat_{}",
    "xoxb-{}",
    "eyJhbGciOiJIUzI1NiJ9.eyJ{}.c2ln",
    "MTIzNDU2Nzg5MDEyMzQ1Njc4.GhIjKl.{}",
    "postgres://svc:{}@db.example.test",
    "https://discord.com/api/webhooks/123/{}",
    "https://h.example.test/cb?session_id={}&x=1",
    "Authorization: Basic {}",
    "password={}",
    "api_key: {}",
    "pwd={}",
    '{{"client_secret": "{}"}}',
]
_SHAPED = st.one_of(
    st.tuples(st.sampled_from(_SHAPES), _ALNUM),
    st.tuples(st.just("AKIA{}"), _AWS_BODY),
)


@given(
    case=_SHAPED,
    before=st.text(max_size=40),
    after=st.text(max_size=40),
    in_field=st.booleans(),
)
def test_secret_shapes_never_reach_output(
    case: tuple[str, str], before: str, after: str, in_field: bool
) -> None:
    shape, body = case
    assume(body not in before + after)
    # Spaces stand for the word boundary a real secret has (`sk-` inside a word is not a key).
    text = before + " " + shape.format(body) + " " + after
    stream = io.StringIO()
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        obs.configure_logging(stream=stream)
        if in_field:
            LOG.info("x", extra={"fields": {"note": text}})
        else:
            LOG.info(text)
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
    assert body not in stream.getvalue()
    assert obs.REDACTED in stream.getvalue()
