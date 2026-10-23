"""Store reporter: records each capture in the local fingerprint store (EP-8), then delegates to
another reporter (the log adapter). Composition: the delegate is unchanged."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from nexus.errors import ErrorReporter
from nexus.errors.adapters.log import allowlisted_fields
from nexus.errors.fingerprint import fingerprint
from nexus.errors.store import Store


class StoreReporter:
    def __init__(
        self,
        store: Store,
        delegate: ErrorReporter,
        release: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._delegate = delegate
        self._release = release
        self._clock = clock

    def capture(self, exc: BaseException, *, component: str, tags: dict[str, str]) -> None:
        fields = allowlisted_fields(exc, component=component, tags=tags)
        sample = {k: fields[k] for k in ("exc_type", "frames", "component", "tags")}
        exc_type, comp = str(fields["exc_type"]), str(fields["component"])
        frames = cast("list[dict[str, object]]", fields["frames"])
        self._store.record(
            fingerprint(comp, exc_type, frames),
            exc_type=exc_type,
            component=comp,
            sample=sample,
            release=self._release,
            now=self._clock(),
        )
        self._delegate.capture(exc, component=component, tags=tags)

    def flush(self, timeout_s: float) -> None:
        self._delegate.flush(timeout_s)
