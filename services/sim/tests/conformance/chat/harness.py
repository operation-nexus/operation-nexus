"""What an adapter provides to the shared suite (CHAT-GATEWAY GW-4). NX-191 implements this
Protocol over its fixtures; nothing in the suite reaches into LocalSim's internals."""

from typing import Protocol

from nexus.contracts.gen.common.envelope import ChatEnvelope
from nexus.gateway.ports import ChatSink, ChatSource


class ChatHarness(ChatSource, ChatSink, Protocol):
    sent: list[tuple[float, str]]  # (injected-clock time, message) for every message it sent
    refused: int  # lines the sink declined to send to stay inside its capabilities

    def inject(self, env: ChatEnvelope) -> None:
        """Queue an inbound envelope for `messages()`."""
        ...

    def drop(self) -> None:
        """Inject a connection fault: `messages()` raises `ConnectionError`, health says so."""
        ...

    def restore(self) -> None:
        """Clear the fault; queued envelopes are delivered, none lost."""
        ...
