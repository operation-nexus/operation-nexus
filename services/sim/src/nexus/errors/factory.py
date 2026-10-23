"""Picks the ErrorReporter from the environment (EP-7): `SENTRY_DSN`, `NEXUS_ENV`."""

import logging
import os
from collections.abc import Mapping

from nexus.errors import ErrorReporter
from nexus.errors.adapters.log import LogReporter
from nexus.errors.adapters.noop import NoOpReporter

_log = logging.getLogger(__name__)


def make_reporter(env: Mapping[str, str] | None = None) -> ErrorReporter:
    """No DSN: no-op, logged here. DSN set: the Sentry adapter is not built yet (NX-364 part 2),
    so say so and use the log adapter instead of pretending to report. The DSN is a secret and
    is never logged."""
    env = os.environ if env is None else env
    if not env.get("SENTRY_DSN"):
        _log.info("error reporting is off: SENTRY_DSN is not set")
        return NoOpReporter()
    _log.warning("SENTRY_DSN is set but the Sentry adapter is not built yet; using the log adapter")
    return LogReporter(env.get("NEXUS_ENV"))
