"""Log adapter: one structured log line per capture, allowlisted fields only (EP-2 spirit).

The line may be shipped off the box later, so it holds the exception type, frames (file, line,
function), component and tags, and nothing else: no exception message, locals or chained causes.
Tags go through the typed per-key allowlist `TAG_PATTERNS`; the rest are dropped and counted in
`tags_dropped`, so a viewer name or token under any key never passes. This is the adapter's own
allowlist, not the NX-026 redaction rules: `nexus.obs` is a separate leaf and EP-1 forbids
importing it. Component and environment are code-supplied and checked for shape only. File
paths are cut to start at the `nexus` package (a basename outside it), so a home directory or OS
user name never reaches the line. The Sentry adapter owns the full EP-2 scrub.
"""

import logging
import re
import traceback
from pathlib import PureWindowsPath

_log = logging.getLogger("nexus.errors")
_TAG_VALUE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")  # component, environment, release: shape only
# EP-2: tags are ids only, typed per key. A new tag key is added HERE with a typed pattern; any
# other key, and any value that does not match its key's pattern, is dropped and counted.
TAG_PATTERNS: dict[str, re.Pattern[str]] = {
    "tick": re.compile(r"[0-9]{1,12}"),
    # contracts/common/ids.json CampaignId: UUIDv7, canonical lowercase
    "campaign_id": re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    ),
}
MAX_FRAMES = 50  # the innermost frames; bounds a line from a runaway recursion


def short_path(filename: str) -> str:
    """`/home/u/.../nexus/runtime/loop.py` -> `nexus/runtime/loop.py`; elsewhere the basename."""
    parts = PureWindowsPath(filename).parts  # splits on both / and \\
    if "nexus" in parts:
        start = len(parts) - 1 - parts[::-1].index("nexus")
        return "/".join(parts[start:])
    return parts[-1] if parts else ""


def allowlisted_fields(
    exc: BaseException, *, component: str, tags: dict[str, str]
) -> dict[str, object]:
    """The EP-2 sample: exception type, frames, component, id-shaped tags. Never the message.
    Shared by the log adapter and the store reporter (EP-8), so both hold the same fields."""
    frames = traceback.extract_tb(exc.__traceback__)[-MAX_FRAMES:]
    kept = {k: v for k, v in tags.items() if k in TAG_PATTERNS and TAG_PATTERNS[k].fullmatch(v)}
    fields: dict[str, object] = {
        "exc_type": f"{type(exc).__module__}.{type(exc).__qualname__}",
        "frames": [
            {"file": short_path(f.filename), "line": f.lineno, "function": f.name} for f in frames
        ],
        "component": component if _TAG_VALUE.fullmatch(component) else "invalid",
        "tags": kept,
    }
    if len(kept) < len(tags):
        fields["tags_dropped"] = len(tags) - len(kept)  # visible, never the dropped text
    return fields


def is_id_shaped(value: str) -> bool:
    return _TAG_VALUE.fullmatch(value) is not None


class LogReporter:
    def __init__(self, environment: str | None = None) -> None:
        ok = environment is not None and _TAG_VALUE.fullmatch(environment)
        self.environment = environment if ok else None

    def capture(self, exc: BaseException, *, component: str, tags: dict[str, str]) -> None:
        fields = allowlisted_fields(exc, component=component, tags=tags)
        if self.environment is not None:
            fields["environment"] = self.environment
        _log.error("error captured", extra={"fields": fields})

    def flush(self, timeout_s: float) -> None:
        return None
