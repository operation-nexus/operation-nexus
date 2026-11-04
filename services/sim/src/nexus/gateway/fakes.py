"""In-memory `IdentityResolver` until the SQLite one arrives with NX-200 (GW-5)."""

from datetime import datetime

from nexus.contracts.gen.common.enums import Platform
from nexus.contracts.gen.common.ids import CommanderId


class InMemoryIdentityResolver:
    """Test and dev only, never wired at runtime (the real resolver comes with NX-200).

    Lazy creation, deterministic ids (a counter in a UUIDv7-shaped string), a ban set.
    """

    def __init__(self) -> None:
        self._ids: dict[tuple[Platform, str], CommanderId] = {}
        self._banned: set[CommanderId] = set()

    def resolve(
        self, platform: Platform, platform_user_id: str, account_created_at: datetime | None
    ) -> CommanderId:
        key = (platform, platform_user_id)
        if key not in self._ids:
            self._ids[key] = f"00000000-0000-7000-8000-{len(self._ids) + 1:012x}"
        return self._ids[key]

    def is_banned(self, commander_id: CommanderId) -> bool:
        return commander_id in self._banned

    def ban(self, commander_id: CommanderId) -> None:
        self._banned.add(commander_id)
