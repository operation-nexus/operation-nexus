"""nexus.obs: structured JSON logging with secret redaction (NX-026).

Specs: CICD-ARCHITECTURE §8 ("secrets must never be logged"), DATA-MODEL §6.3 (crash bundles carry
recent secret-redacted logs), THREAT-MODEL (chat text is hostile). Leaf module: imports nothing
else from `nexus` (SYSTEM-DESIGN §4). Stdlib `logging` only.

Use: call `configure_logging()` once at process start, then log through stdlib loggers.
Structured fields go in `extra={"fields": {...}}`::

    logging.getLogger(__name__).info("joined %s", channel, extra={"fields": {"tick": 5}})

Each record is one line of JSON: `ts` (UTC ISO-8601, `Z`), `level`, `logger`, `msg`, then
`fields` (object) and `exc` (formatted exception text) when present. `stack_info` is dropped.

Redaction runs on the logger name, the formatted message (so %-args too; a mapping arg has its
secret-keyed values redacted before formatting), every structured field (recursively through
dicts, lists and tuples) and the exception text. It never raises: on any internal error the
record becomes `msg="[REDACTION_FAILED]"` with no fields or exception, and `redaction_failures()`
goes up. Running it twice on a record is safe, so the formatter always runs it again.

By key: a name that contains (case-insensitive, `_` or `-` or nothing between words) one of
`SECRET_KEYS` is a secret key, unless the whole name is in `ALLOWED_KEYS` (token counts). Keys of
4 chars or fewer (`pwd`, `hmac`, `dsn`, `otp`) must be a whole word of the name, split on `_`, `-`,
`.` and camelCase (`user_otp`, `otpCode` match; `hotpath_ms` does not). A field with a secret key
has its whole value replaced with `[REDACTED]`, whatever its type.

By value, anywhere in a string. These are shapes, not guarantees of vendor formats: the vendor
prefixes and lengths are [UNVERIFIED] against current vendor docs and over-redaction is preferred.

| Name            | Matches                                                       | Kept           |
|-----------------|---------------------------------------------------------------|----------------|
| authorization   | `Authorization:` or `=` then the rest of the line             | the label      |
| bearer          | `Bearer <token68>`                                            | `Bearer `      |
| url_userinfo    | password in `scheme://user:password@`                    | `scheme://user:` |
| discord_webhook | `discord.com/api/webhooks/...` or `discordapp.com/...` to a space | nothing    |
| twitch_oauth    | `oauth:` + letters/digits                                     | nothing        |
| anthropic_key   | `sk-ant-` + `[A-Za-z0-9_-]+`, not inside a longer word        | nothing        |
| openai_key      | `sk-` + 20 or more `[A-Za-z0-9_-]`, not inside a longer word  | nothing        |
| github_token    | `ghp_` `gho_` `ghu_` `ghs_` `ghr_` `github_pat_` + `\\w+`     | nothing        |
| slack_token     | `xoxa-` `xoxb-` `xoxp-` `xoxr-` `xoxs-` + 10 or more `[A-Za-z0-9-]` | nothing  |
| aws_key_id      | `AKIA` + 16 `[0-9A-Z]`                                        | nothing        |
| jwt             | `eyJ...` `.` `eyJ...` `.` signature                           | nothing        |
| discord_token   | 23+ `.` 6+ `.` 27+ chars of `[A-Za-z0-9_-]`                   | nothing        |
| key_value       | `name=v`, `name: v`, `"name": "v"`, `?name=v&`; the name holds | `name=` etc. |
|                 | a secret key; the value ends at whitespace, `&`, `,`, `;`, quote |            |

Hostile text (AGENTS.md rule 4): every string is capped at `MAX_FIELD_CHARS`, marker included.
Messages and fields keep the head (marker `...[TRUNCATED]` at the end); the exception text keeps
the tail, where the exception line is (marker `[TRUNCATED]...` at the front). A cut first drops
the partial word (head) or partial first line (tail), so half a secret is not left for the
patterns to miss; with no such boundary it is a hard cut. Ints too long for the cap become capped
strings. JSON encoding with `ensure_ascii` escapes newlines, control and non-ASCII characters, so
a record is always exactly one line (no log injection).

Limits: redaction is pattern-based. A secret with neither a known key nor a known shape in the
rendered text ("the password is X", a `bytes` repr, a hard cut through a secret) gets through.
Only the handler `configure_logging` installs is covered: a handler added elsewhere, or on a
logger that does not propagate to the root, gets unredacted records.
"""

import json
import logging
import math
import re
import threading
import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TextIO

REDACTED = "[REDACTED]"
REDACTION_FAILED = "[REDACTION_FAILED]"
TRUNCATED = "...[TRUNCATED]"
TRUNCATED_HEAD = "[TRUNCATED]..."
# Every string is capped to this before any pattern runs. The cap also bounds the
# url_userinfo and jwt patterns, which are quadratic on long hostile input: keep the cap
# ahead of them if this changes.
MAX_FIELD_CHARS = 2_000
HANDLER_NAME = "nexus.obs"
_INT_CAP = 10 ** (MAX_FIELD_CHARS - 1)  # the smallest int whose str is over the cap

SECRET_KEYS = (
    "token", "secret", "password", "passwd", "passphrase", "pwd", "authorization", "api_key",
    "apikey", "cookie", "credential", "private_key", "client_secret", "refresh_token",
    "access_token", "session", "hmac", "dsn", "signature", "webhook", "otp",
)  # fmt: skip
# Whole names (lowercase, `-` as `_`) that hold a count, not a credential (LLM usage fields).
ALLOWED_KEYS = frozenset({
    "input_tokens", "output_tokens", "max_tokens", "total_tokens", "token_count", "tokens_used",
    "prompt_tokens", "completion_tokens",
})  # fmt: skip
# Keys of 4 chars or fewer match only as a whole word of the name, so `hotpath` is not `otp`.
_SHORT_KEYS = frozenset(k for k in SECRET_KEYS if len(k) <= 4)
_LONG_KEYS = (k.replace("_", "[_-]?") for k in SECRET_KEYS if k not in _SHORT_KEYS)
_SECRET_KEY_RE = re.compile("|".join(_LONG_KEYS), re.IGNORECASE)
_NAME_WORD_RE = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")  # snake, kebab, dotted, camelCase
_B64URL = "[A-Za-z0-9_-]"

# Group 1, when present, is kept; the rest of the match becomes REDACTED. Patterns run in order;
# a later one can only redact more, never bring back text an earlier one removed. Lookbehinds
# start a match only where a run starts, which keeps the scans linear.
_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(authorization[\"']?\s*[:=]\s*)[^\r\n]*",
        r"(bearer\s+)[A-Za-z0-9._~+/-]+=*",
        r"(?<![a-z0-9+.-])([a-z][a-z0-9+.-]*://[^/\s:@]*:)[^\s@]+(?=@)",
        r"discord(?:app)?\.com/api/webhooks/\S+",
        r"oauth:[a-z0-9]+",
        rf"(?<!{_B64URL})sk-ant-{_B64URL}+",
        rf"(?<!{_B64URL})sk-{_B64URL}{{20,}}",
        r"(?:gh[pousr]_|github_pat_)\w+",
        r"xox[abprs]-[A-Za-z0-9-]{10,}",
        r"AKIA[0-9A-Z]{16}",
        rf"eyJ{_B64URL}+\.eyJ{_B64URL}+\.{_B64URL}*",
        rf"(?<!{_B64URL}){_B64URL}{{23,}}\.{_B64URL}{{6,}}\.{_B64URL}{{27,}}",
    )
)
# Free text `name=value`, `name: value`, `"name": "value"`, query params: see `_redact_key_values`.
_KEY_LABEL = re.compile(r"(?<![\w.-])([\w.-]+)[\"']?\s*[:=]\s*[\"']?")
_KEY_VALUE = re.compile(r"[^\s&,;\"']+")

_failures = 0
_failures_lock = threading.Lock()


def redaction_failures() -> int:
    """How many redaction attempts failed (and emitted REDACTION_FAILED) since process start."""
    return _failures


def _count_failure() -> None:
    global _failures  # process-wide counter, guarded by the lock
    with _failures_lock:
        _failures += 1


def _is_secret_key(name: str) -> bool:
    if name.lower().replace("-", "_") in ALLOWED_KEYS:
        return False
    if _SECRET_KEY_RE.search(name):
        return True
    return any(word.lower() in _SHORT_KEYS for word in _NAME_WORD_RE.findall(name))


def _keep_prefix(match: re.Match[str]) -> str:
    return (match.group(1) or "") + REDACTED if match.re.groups else REDACTED


def _redact_key_values(text: str) -> str:
    """Replace the value after each secret-key label. A label that is not a secret consumes only
    itself, so `https://h/p?access_token=v` still finds `access_token=`."""
    out: list[str] = []
    pos = 0
    for label in _KEY_LABEL.finditer(text):
        if label.start() < pos or not _is_secret_key(label.group(1)):
            continue
        value = _KEY_VALUE.match(text, label.end())
        if value is not None:
            out += [text[pos : label.end()], REDACTED]
            pos = value.end()
    out.append(text[pos:])
    return "".join(out)


def _cut(text: str, limit: int, keep_tail: bool) -> str:
    """Cut to `limit` chars without leaving part of a secret the patterns would then miss.

    Head: drop the partial last word (a key comes before its value, so the value goes too).
    Tail: drop the whole partial first line, since a cut word could be the key of the next one.
    With no such boundary (nothing would be left), it is a hard cut.
    """
    if keep_tail:
        start = len(text) - limit
        if text[start - 1] != "\n":
            newline = text.find("\n", start)
            if newline >= 0 and text[newline + 1 :].strip():
                start = newline + 1
        return text[start:]
    end = limit
    while end and not text[end - 1].isspace():
        end -= 1
    return text[:end] if text[:end].strip() else text[:limit]


def _clean_text(text: str, *, keep_tail: bool = False) -> str:
    """Redact secret shapes, then cap the length: keep the head, or the tail for tracebacks."""
    marker = TRUNCATED_HEAD if keep_tail else TRUNCATED
    limit = MAX_FIELD_CHARS - len(marker)
    cut = len(text) > MAX_FIELD_CHARS
    if cut:
        text = _cut(text, limit, keep_tail)
    for pattern in _PATTERNS:
        text = pattern.sub(_keep_prefix, text)
    text = _redact_key_values(text)
    if cut or len(text) > MAX_FIELD_CHARS:
        text = marker + text[-limit:] if keep_tail else text[:limit] + marker
    return text


def _int_text(value: int) -> str:
    try:
        return str(value)
    except ValueError:  # over sys.get_int_max_str_digits(); hex has no such limit
        return hex(value)


def _clean_value(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if abs(value) < _INT_CAP else _clean_text(_int_text(value))
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)  # NaN is not valid JSON
    if isinstance(value, Mapping):
        return {
            _clean_text(str(k)): REDACTED if _is_secret_key(str(k)) else _clean_value(v)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_clean_value(v) for v in value]
    return _clean_text(value if isinstance(value, str) else str(value))


def _message(record: logging.LogRecord) -> str:
    if isinstance(record.args, Mapping):  # "%(token)s" style: the key says what the value is
        record.args = {k: REDACTED if _is_secret_key(str(k)) else v for k, v in record.args.items()}
    return _clean_text(record.getMessage())


class RedactingFilter(logging.Filter):
    """Redact a record in place, so every formatter after it sees only cleaned text. Never drops.

    Safe to run again on a record it already cleaned (the output is still clean and capped).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            name = _clean_text(record.name)
            msg = _message(record)
            raw = getattr(record, "fields", None)
            fields = {} if raw is None else _clean_value(raw)
            exc = None
            if record.exc_info and record.exc_info[1] is not None:
                text = "".join(traceback.format_exception(record.exc_info[1]))
                exc = _clean_text(text, keep_tail=True)
            elif record.exc_text:
                exc = _clean_text(record.exc_text, keep_tail=True)
        except Exception:  # noqa: BLE001 - fail closed: emit no data rather than raise or leak
            _count_failure()
            name, msg, fields, exc = HANDLER_NAME, REDACTION_FAILED, {}, None
        record.name, record.msg, record.args = name, msg, None
        setattr(record, "fields", fields)  # noqa: B010 - LogRecord declares no `fields` attribute
        record.exc_info, record.exc_text, record.stack_info = None, exc, None
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Always runs the redaction itself (again, if a filter ran)."""

    def format(self, record: logging.LogRecord) -> str:
        RedactingFilter().filter(record)
        try:
            out: dict[str, object] = {
                "ts": datetime.fromtimestamp(record.created, UTC)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.msg,
            }
            fields = getattr(record, "fields", None)
            if fields:
                out["fields"] = fields
            if record.exc_text:
                out["exc"] = record.exc_text
            return json.dumps(out, ensure_ascii=True, separators=(",", ":"))
        except Exception:  # noqa: BLE001 - fail closed: a formatter that raises would print the record
            _count_failure()
            return json.dumps({"level": "ERROR", "logger": HANDLER_NAME, "msg": REDACTION_FAILED})


def configure_logging(*, level: str = "INFO", stream: TextIO | None = None) -> None:
    """Install the JSON + redaction handler on the root logger (stderr by default).

    Idempotent: a second call replaces the handler instead of adding one. `level` is a stdlib
    level name such as "INFO"; an unknown name raises ValueError. Callers must not add other
    handlers: only this one redacts (see Limits in the module docstring).
    """
    root = logging.getLogger()
    for old in [h for h in root.handlers if h.name == HANDLER_NAME]:
        root.removeHandler(old)
    handler = logging.StreamHandler(stream)
    handler.name = HANDLER_NAME
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
