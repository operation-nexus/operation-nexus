"""Chat ports (CHAT-GATEWAY GW-1, GW-3, GW-5, GW-6; ADR-0010 N-2, N-3).

Vendor-free: no platform SDK is imported here, and `nexus.core` is off limits (import-linter).
`ModerationEvent` joins `ChatSource` with its contract schema (GW-2, a later PR).
"""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Protocol

from nexus.contracts.gen.common.enums import Platform
from nexus.contracts.gen.common.envelope import ChatEnvelope
from nexus.contracts.gen.common.ids import CommanderId, EntityId, NodeId


@dataclass(frozen=True)
class Capabilities:
    """What an adapter can do; `None`/`False` means the feature is off, never faked (GW-3)."""

    max_reply_rate: float | None = None  # replies per second the platform allows
    reply_cost: int | None = None  # quota units one reply costs (YouTube)
    message_max_len: int | None = None  # characters per outgoing message
    supports_moderation_events: bool = False
    supports_whisper: bool = False
    quota_model: str | None = None
    latency_class: str | None = None


@dataclass(frozen=True)
class Health:
    """`connected`, `lag_ms` and `quota_used` (GW-3); `None` is not measured."""

    connected: bool
    lag_ms: int | None = None
    quota_used: int | None = None


class ChatSource(Protocol):
    """Inbound side of an adapter. Envelopes are already the platform-neutral shape (N-2)."""

    @property
    def capabilities(self) -> Capabilities: ...

    def messages(self) -> AsyncIterator[ChatEnvelope]: ...

    def health(self) -> Health: ...


class ChatSink(Protocol):
    """Outbound side. `send_batch` honors `capabilities` (rate, length); it never exceeds them."""

    @property
    def capabilities(self) -> Capabilities: ...

    async def send_batch(self, lines: list[str]) -> None: ...


class IdentityResolver(Protocol):
    """Platform identity to commander (IDENTITY §2). The gateway never touches the database."""

    def resolve(
        self, platform: Platform, platform_user_id: str, account_created_at: datetime | None
    ) -> CommanderId:
        """Return the commander for this identity, creating one on first sight."""
        ...

    def is_banned(self, commander_id: CommanderId) -> bool: ...


@dataclass(frozen=True)
class NameDirectory:
    """Read-only snapshot for fuzzy resolution (GW-6): friendly callsign to entity, node name or
    alias to node. The runtime builds a new one per tick and swaps the reference; this PR ships
    only the type. The mappings are copied read-only, so a caller cannot mutate a snapshot.
    """

    callsigns: Mapping[str, EntityId] = field(default_factory=dict)
    nodes: Mapping[str, NodeId] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "callsigns", MappingProxyType(dict(self.callsigns)))
        object.__setattr__(self, "nodes", MappingProxyType(dict(self.nodes)))
