"""`LocalSim`: the in-process ChatSource + ChatSink with fault injection (CHAT-GATEWAY CG-1, GW-4).

Test-side for now; NX-193's viewer simulator feeds the same shape. It declares Twitch-shaped
`Capabilities` (§2.1: 20 messages per 30 s, 500 characters is the platform's own limit [UNVERIFIED],
so the fake declares a smaller, round 100: a test value, not a Twitch fact) and honors them on send.
"""

from collections import deque
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

from nexus.contracts.gen.common.envelope import ChatEnvelope
from nexus.gateway.ports import Capabilities, Health

SEND_WINDOW_S = 30.0  # the window the declared max_reply_rate is measured over


def envelope(text: str, message_id: str, user: str = "u1") -> ChatEnvelope:
    return ChatEnvelope(
        platform="LOCAL_SIM",
        platform_user_id=user,
        platform_message_id=message_id,
        display_name="",
        text=text,
        match_key=text.lower(),
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
        platform_badges=set(),
        account_created_at=None,
    )


class LocalSim:
    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._queue: deque[ChatEnvelope] = deque()
        self._connected = True
        self.sent: list[tuple[float, str]] = []  # (clock time, message)
        self.refused = 0  # lines the sink declined to send to stay inside its capabilities

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(max_reply_rate=20 / 30, message_max_len=100)

    def inject(self, env: ChatEnvelope) -> None:
        self._queue.append(env)

    async def messages(self) -> AsyncIterator[ChatEnvelope]:
        if not self._connected:
            raise ConnectionError("local sim connection dropped")
        while self._queue:
            yield self._queue.popleft()

    def health(self) -> Health:
        return Health(connected=self._connected)

    async def send_batch(self, lines: list[str]) -> None:
        caps = self.capabilities
        assert caps.max_reply_rate is not None and caps.message_max_len is not None
        now = self._clock()
        for line in lines:
            recent = sum(1 for t, _ in self.sent if now - t < SEND_WINDOW_S)
            if len(line) > caps.message_max_len or recent >= int(
                caps.max_reply_rate * SEND_WINDOW_S
            ):
                self.refused += 1
            else:
                self.sent.append((now, line))

    # fault injection
    def drop(self) -> None:
        self._connected = False

    def restore(self) -> None:
        self._connected = True
