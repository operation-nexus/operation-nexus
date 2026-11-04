"""Message-id dedupe and correlation ids (CHAT-GATEWAY GW-8 stage 3, GW-9)."""

import hashlib

from nexus.contracts.gen.common.enums import Platform

DEDUPE_CAPACITY = 10_000  # GW-8: LRU of 10k, in memory


class Dedupe:
    """First-seen-first-evicted window over `(platform, platform_message_id)`.

    A hit does not refresh the entry (GW-8 says FIFO eviction), so the window is exactly the last
    `capacity` distinct ids. A duplicate older than the window passes (CHAT-GATEWAY §7).
    """

    def __init__(self, capacity: int = DEDUPE_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._seen: dict[tuple[Platform, str], None] = {}  # insertion-ordered

    def __len__(self) -> int:
        return len(self._seen)

    def is_duplicate(self, platform: Platform, platform_message_id: str) -> bool:
        """True if seen; otherwise records the id (evicting the oldest at capacity) and False."""
        key = (platform, platform_message_id)
        if key in self._seen:
            return True
        if len(self._seen) >= self._capacity:
            del self._seen[next(iter(self._seen))]
        self._seen[key] = None
        return False


def correlation_id(platform: Platform, platform_message_id: str) -> str:
    """GW-9: 32 hex chars of sha256 over `platform:message id`; never holds raw text."""
    return hashlib.sha256(f"{platform}:{platform_message_id}".encode()).hexdigest()[:32]
