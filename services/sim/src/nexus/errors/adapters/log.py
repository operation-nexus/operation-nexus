"""Log adapter: one structured log line per capture, allowlisted fields only (EP-2 spirit).

The line may be shipped off the box later, so it holds the exception type, frames (file, line,
function), component and tags, and nothing else: no exception message, locals or chained causes.
Tag keys and values must match `_TAG_KEY` / `_TAG_VALUE`; the rest are dropped and counted in
`tags_dropped`. The value pattern is a shape check, not a defence: a viewer name such as
`SomeViewer_99` matches it, so the id-only rule rests on callers (EP-2). These patterns are this
adapter's own allowlist, not the NX-026 redaction rules: `nexus.obs` is a separate leaf and EP-1
forbids importing it. File paths are cut to start at the `nexus` package (a basename outside it),
so a home directory or OS user name never reaches the line. The Sentry adapter owns the full EP-2
scrub.
"""

import logging
import re
import traceback
from pathlib import PureWindowsPath

_log = logging.getLogger("nexus.errors")
_TAG_KEY = re.compile(r"[a-z][a-z0-9_]{0,31}")
_TAG_VALUE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
MAX_FRAMES = 50  # the innermost frames; bounds a line from a runaway recursion


def short_path(filename: str) -> str:
    """`/home/u/.../nexus/runtime/loop.py` -> `nexus/runtime/loop.py`; elsewhere the basename."""
    parts = PureWindowsPath(filename).parts  # splits on both / and \\
    if "nexus" in parts:
        start = len(parts) - 1 - parts[::-1].index("nexus")
        return "/".join(parts[start:])
    return parts[-1] if parts else ""


class LogReporter:
    def __init__(self, environment: str | None = None) -> None:
        ok = environment is not None and _TAG_VALUE.fullmatch(environment)
        self.environment = environment if ok else None

    def capture(self, exc: BaseException, *, component: str, tags: dict[str, str]) -> None:
        frames = traceback.extract_tb(exc.__traceback__)[-MAX_FRAMES:]
        kept = {k: v for k, v in tags.items() if _TAG_KEY.fullmatch(k) and _TAG_VALUE.fullmatch(v)}
        fields: dict[str, object] = {
            "exc_type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "frames": [
                {"file": short_path(f.filename), "line": f.lineno, "function": f.name}
                for f in frames
            ],
            "component": component if _TAG_VALUE.fullmatch(component) else "invalid",
            "tags": kept,
        }
        if len(kept) < len(tags):
            fields["tags_dropped"] = len(tags) - len(kept)  # visible, never the dropped text
        if self.environment is not None:
            fields["environment"] = self.environment
        _log.error("error captured", extra={"fields": fields})

    def flush(self, timeout_s: float) -> None:
        return None
