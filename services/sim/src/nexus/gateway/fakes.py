"""In-memory `IdentityResolver` until the SQLite one arrives with NX-200 (GW-5)."""

import hashlib
from datetime import datetime

from nexus.contracts.gen.common.enums import Platform
from nexus.contracts.gen.common.ids import CommanderId


class InMemoryIdentityResolver:
    """Test and dev only, never wired at runtime (the real resolver comes with NX-200).

    Lazy creation, a ban set, and ids derived from the key (12 hex digits of sha256 in a
    UUIDv7-shaped string), so the same identity gets the same id in any instance, in any order.
    Two keys can collide (48 bits); acceptable for a fake.
    """

    def __init__(self) -> None:
        self._ids: dict[tuple[Platform, str], CommanderId] = {}
        self._banned: set[CommanderId] = set()

    def resolve(
        self, platform: Platform, platform_user_id: str, account_created_at: datetime | None
    ) -> CommanderId:
        key = (platform, platform_user_id)
        if key not in self._ids:
            digest = hashlib.sha256(f"{platform}:{platform_user_id}".encode()).hexdigest()
            self._ids[key] = f"00000000-0000-7000-8000-{digest[:12]}"
        return self._ids[key]

    def is_banned(self, commander_id: CommanderId) -> bool:
        return commander_id in self._banned

    def ban(self, commander_id: CommanderId) -> None:
        self._banned.add(commander_id)
