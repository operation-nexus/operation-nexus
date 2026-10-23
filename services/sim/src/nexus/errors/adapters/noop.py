"""No-op adapter: the default when no DSN is configured (EP-1)."""


class NoOpReporter:
    def capture(self, exc: BaseException, *, component: str, tags: dict[str, str]) -> None:
        return None

    def flush(self, timeout_s: float) -> None:
        return None
