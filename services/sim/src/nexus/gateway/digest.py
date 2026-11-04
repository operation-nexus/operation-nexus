"""Digest builder skeleton (CHAT-GATEWAY GW-13, GW-14, GW-15). No event-bus wiring yet: callers
use the plain `add_*` API.

Lines are static templates keyed by reason, never an echo of user text. The one user-derived string
is the platform login for the @-mention (GW-15), which must already be envelope-validated (the
caller passes it through unchanged); it lives only in the in-memory batch, is excluded
from `repr`, and nothing here logs.
"""

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from nexus.gateway.ports import Capabilities


class GatewayReject(StrEnum):
    """Gateway-side rejects that never reach the sim, so they are not `RejectReason`s (§6)."""

    TOO_LONG = "TOO_LONG"
    RATE_LIMITED = "RATE_LIMITED"
    GLOBAL_CAP = "GLOBAL_CAP"
    PARSE_ERROR = "PARSE_ERROR"
    INBOX_FULL = "INBOX_FULL"


# Keyed by the `RejectReason` value (CONTRACTS §5.3) or a `GatewayReject`. A test fails when the
# contract enum grows a value without a template here.
TEMPLATES: dict[str, str] = {
    "ROLE_UNKNOWN": "unknown role",
    "UNIT_IN_SORTIE": "unit is in sortie",
    "RESPAWN_COOLDOWN": "respawn cooldown, wait a bit",
    "NODE_UNKNOWN": "unknown node",
    "NODE_INVALID_FOR_UNIT": "that node is not valid for your unit",
    "FOLLOW_TARGET_INVALID": "invalid follow target",
    "CAMPAIGN_PAUSED": "war paused",
    "INVALID_PAYLOAD": "could not read that command",
    "INTERNAL_ERROR": "internal error, try again",
    "RESERVE_QUEUE_FULL": "reserve queue full",
    "ALREADY_PAUSED": "already paused",
    "NOT_PAUSED": "not paused",
    "CAMPAIGN_NOT_RUNNING": "campaign not running",
    "REASON_REQUIRED": "a reason is required",
    "NO_ACTIVE_UNIT": "you have no active unit",
    "NODE_NOT_FRIENDLY": "that node is not friendly",
    "OUT_OF_REACH": "out of reach",
    "UNIT_GROUNDED": "your unit is grounded",
    "NO_STOCK": "no stock",
    GatewayReject.TOO_LONG: "message too long",
    GatewayReject.RATE_LIMITED: "hold up, ready in a few seconds",
    GatewayReject.GLOBAL_CAP: "busy, try again",
    GatewayReject.PARSE_ERROR: "could not understand that command",
    GatewayReject.INBOX_FULL: "busy, try again",
}


@dataclass(repr=False)  # the login must never reach a repr, hence a log
class _Entry:
    login: str
    accepted: int = 0
    rejected: Counter[str] = field(default_factory=Counter)  # insertion-ordered


class DigestBuilder:
    """Coalesces per user, then packs lines into messages within the adapter's `Capabilities`.

    `interval_s` is the config key `replies.twitch_digest_min_s` (CONFIG-AND-CONTENT §6.9).
    """

    def __init__(
        self,
        capabilities: Capabilities,
        clock: Callable[[], float],
        interval_s: float,
        is_blatant: Callable[[str], bool],
    ) -> None:
        rate, length = capabilities.max_reply_rate, capabilities.message_max_len
        if (
            rate is None
            or length is None
            or not (math.isfinite(rate) and rate > 0 and length > 0)
            or not (math.isfinite(interval_s) and interval_s > 0)
        ):
            raise ValueError("a digest needs finite, positive rate, message length and interval")
        self._max_len = length
        self._budget = max(1, int(rate * interval_s))
        self._clock = clock
        self._interval_s = interval_s
        self._is_blatant = is_blatant
        self._last_build = clock()
        self._users: dict[str, _Entry] = {}
        self.dropped = 0  # lines lost to the caps (§7), a metric
        self.suppressed = 0  # blatant-spam events given the cooldown ring only (GW-13)

    def due(self) -> bool:
        return self._clock() - self._last_build >= self._interval_s

    def add_accepted(self, user: str, login: str) -> None:
        if self._is_blatant(user):
            self.suppressed += 1
            return
        self._entry(user, login).accepted += 1

    def add_rejected(self, user: str, login: str, reason: str) -> None:
        """Banned users get no reply, so the caller never passes them (GW-14)."""
        if self._is_blatant(user):
            self.suppressed += 1
            return
        self._entry(user, login).rejected[TEMPLATES[reason]] += 1  # unknown reason: KeyError

    def build(self) -> list[str]:
        """Messages for `ChatSink.send_batch`, oldest lines dropped first when over the caps."""
        self._last_build = self._clock()
        live = {u: e for u, e in self._users.items() if not self._is_blatant(u)}
        self.suppressed += len(self._users) - len(live)  # went blatant after queuing: ring only
        lines = [self._line(e) for e in live.values()]
        self._users = {}
        messages: list[list[str]] = []
        for line in lines:
            if len(line) > self._max_len:
                self.dropped += 1
            elif messages and len(" | ".join([*messages[-1], line])) <= self._max_len:
                messages[-1].append(line)
            else:
                messages.append([line])
        for old in messages[: max(0, len(messages) - self._budget)]:
            self.dropped += len(old)
        return [" | ".join(m) for m in messages[-self._budget :]]

    def _entry(self, user: str, login: str) -> _Entry:
        return self._users.setdefault(user, _Entry(login))

    @staticmethod
    def _line(entry: _Entry) -> str:
        parts = [f"{n} accepted"] if (n := entry.accepted) else []
        parts += [t if c == 1 else f"{t} (x{c})" for t, c in entry.rejected.items()]
        return f"@{entry.login}: " + "; ".join(parts)
