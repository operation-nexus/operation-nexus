"""nexus.errors: the `ErrorReporter` port (ERROR-PIPELINE EP-1, NX-364).

Leaf module: imports nothing else from `nexus` (SYSTEM-DESIGN §4). The kernel never calls it
(EP-4); the runtime around it does. Adapters live in `nexus.errors.adapters`; vendor SDKs are
imported only there (ADR-0010).
"""

import logging
from collections.abc import Mapping
from typing import Protocol

_log = logging.getLogger(__name__)


class ErrorReporter(Protocol):
    """Where unexpected exceptions go. `tags` carry ids only, never chat text or names (EP-2)."""

    def capture(self, exc: BaseException, *, component: str, tags: dict[str, str]) -> None: ...

    def flush(self, timeout_s: float) -> None: ...


def report_safely(
    reporter: ErrorReporter, exc: BaseException, *, component: str, tags: Mapping[str, str]
) -> None:
    """EP-3: a reporter that raises never reaches the caller. The failure is logged by type only
    (its message may echo the report), once per failure."""
    try:
        reporter.capture(exc, component=component, tags=dict(tags))
    except Exception as failure:  # noqa: BLE001 - EP-3: a broken reporter must not stop the sim
        _log.error("error reporter failed: %s", type(failure).__name__)
