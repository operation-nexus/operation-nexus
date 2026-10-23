"""Picks the ErrorReporter from the environment (EP-7, EP-8): `SENTRY_DSN`, `NEXUS_ENV`,
`NEXUS_ERRORS_DB`, `NEXUS_RELEASE`."""

import logging
import os
from collections.abc import Mapping
from pathlib import Path

from nexus.errors import ErrorReporter
from nexus.errors.adapters.log import LogReporter, is_id_shaped
from nexus.errors.adapters.noop import NoOpReporter
from nexus.errors.adapters.stored import StoreReporter
from nexus.errors.store import Store

_log = logging.getLogger(__name__)
_DSN_WARNING = "SENTRY_DSN is set but the Sentry adapter is not built yet; using the log adapter"


def make_reporter(env: Mapping[str, str] | None = None) -> ErrorReporter:
    """`NEXUS_ERRORS_DB` set: the log adapter plus the local store (no default path; unset means
    no store, logged). No `SENTRY_DSN` and no store: no-op, logged. DSN set: the Sentry adapter is
    not built yet (NX-364 part 2), so say so and use the log adapter instead of pretending to
    report (FB-7). The DSN is a secret and is never logged."""
    env = os.environ if env is None else env
    db = env.get("NEXUS_ERRORS_DB")
    dsn = env.get("SENTRY_DSN")
    if dsn:
        _log.warning(_DSN_WARNING)
    elif not db:
        _log.info("error reporting is off: SENTRY_DSN is not set")
    if not db:
        _log.info("error store is off: NEXUS_ERRORS_DB is not set")
        return LogReporter(env.get("NEXUS_ENV")) if dsn else NoOpReporter()
    release = env.get("NEXUS_RELEASE")
    if release and not is_id_shaped(release):
        _log.warning("NEXUS_RELEASE is not id-shaped; releases are recorded as none")  # no value
        release = None
    return StoreReporter(Store(Path(db)), LogReporter(env.get("NEXUS_ENV")), release or None)
