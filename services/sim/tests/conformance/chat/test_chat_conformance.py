"""Shared chat-adapter conformance suite, skeleton (CHAT-GATEWAY GW-4, ADR-0010 N-4).

Parametrized over `ADAPTERS`; LocalSim is the only one. NX-191's Twitch adapter implements
`ChatHarness` (harness.py) over its recorded fixtures and adds a factory here, and must pass every
test unchanged. Deferred to NX-191 (no production code to test yet, CHAT-GATEWAY §10 GW-4 row):
reconnect backoff timing and error mapping. What runs now is fault injection, health honesty and no
loss across an injected drop, on a fake clock.
"""

import asyncio
import logging
from collections.abc import Callable, Iterator

import pytest

from conformance.chat.harness import ChatHarness
from conformance.chat.local_sim import SEND_WINDOW_S, LocalSim, envelope
from nexus.contracts.gen.common.envelope import ChatEnvelope
from nexus.gateway.digest import DigestBuilder, GatewayReject
from nexus.gateway.fakes import FakeClock
from nexus.gateway.ports import Capabilities, ChatSource
from nexus.moderation import normalize

ADAPTERS: dict[str, Callable[[FakeClock], ChatHarness]] = {"local_sim": LocalSim}


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(1000.0)


@pytest.fixture(params=sorted(ADAPTERS))
def adapter(request: pytest.FixtureRequest, clock: FakeClock) -> ChatHarness:
    return ADAPTERS[request.param](clock)


async def _drain(source: ChatSource) -> list[ChatEnvelope]:
    return [env async for env in source.messages()]


def test_adapter_satisfies_both_ports(adapter: ChatHarness) -> None:
    assert isinstance(adapter.capabilities, Capabilities)
    assert isinstance(adapter.health().connected, bool)


def test_normalization_pass_through(adapter: ChatHarness) -> None:
    """An adapter delivers text it was given unchanged, already normalized and within the cap."""
    adapter.inject(envelope("!join strike", "m1"))
    (env,) = asyncio.run(_drain(adapter))
    assert env.text == "!join strike" and normalize(env.text) == env.text
    assert len(env.text) <= 300 and env.match_key


def test_sink_never_exceeds_its_reply_rate(adapter: ChatHarness, clock: FakeClock) -> None:
    caps = adapter.capabilities
    assert caps.max_reply_rate and caps.message_max_len
    budget = int(caps.max_reply_rate * SEND_WINDOW_S)
    # A flood of raw lines, far over budget and over length, sent in one go and then over time.
    asyncio.run(adapter.send_batch(["x" * (caps.message_max_len + 1), *["ok"] * (3 * budget)]))
    assert len(adapter.sent) == budget and adapter.refused == 2 * budget + 1
    for _ in range(5):
        clock.advance(SEND_WINDOW_S / 5)
        asyncio.run(adapter.send_batch(["ok"] * budget))
    for start, _ in adapter.sent:  # no 30 s window holds more than the declared rate allows
        in_window = [t for t, _ in adapter.sent if start <= t < start + SEND_WINDOW_S]
        assert len(in_window) <= budget
    assert all(len(m) <= caps.message_max_len for _, m in adapter.sent)


def test_digest_output_fits_the_sink_without_refusals(
    adapter: ChatHarness, clock: FakeClock
) -> None:
    builder = DigestBuilder(adapter.capabilities, clock, SEND_WINDOW_S, lambda user: False)
    for i in range(200):
        builder.add_rejected(f"u{i}", f"viewer{i}", GatewayReject.RATE_LIMITED)
    clock.advance(SEND_WINDOW_S)
    assert builder.due()
    asyncio.run(adapter.send_batch(builder.build()))
    assert adapter.refused == 0 and 0 < len(adapter.sent) <= 20
    assert builder.dropped > 0  # the cap, not the platform, shed the overflow (§7)


def test_capabilities_are_honest(adapter: ChatHarness) -> None:
    caps = adapter.capabilities
    assert caps.max_reply_rate is not None and caps.max_reply_rate > 0
    assert caps.message_max_len is not None and caps.message_max_len > 0
    assert caps.reply_cost is None or caps.quota_model  # a cost needs a model to mean anything
    if not caps.supports_whisper:
        assert not hasattr(adapter, "whisper")  # an off capability is absent, not faked
    assert adapter.health().connected
    if not caps.supports_moderation_events:  # off means no moderation items in the stream
        adapter.inject(envelope("!join", "m1"))
        assert all(isinstance(e, ChatEnvelope) for e in asyncio.run(_drain(adapter)))


def test_reconnect_after_an_injected_drop(adapter: ChatHarness, clock: FakeClock) -> None:
    adapter.inject(envelope("!join", "m1"))
    adapter.drop()
    assert not adapter.health().connected
    with pytest.raises(ConnectionError):
        asyncio.run(_drain(adapter))
    clock.advance(5)  # the adapter's backoff waits on the injected clock, not wall time
    adapter.restore()
    assert adapter.health().connected
    assert [e.platform_message_id for e in asyncio.run(_drain(adapter))] == ["m1"]  # nothing lost


@pytest.fixture
def _logs(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


def test_no_raw_text_in_logs(adapter: ChatHarness, _logs: pytest.LogCaptureFixture) -> None:
    """Vacuous for LocalSim (it never logs); meaningful for a real adapter that does I/O."""
    adapter.inject(envelope("!join secret-text-XYZ", "m1"))
    asyncio.run(_drain(adapter))
    assert "XYZ" not in _logs.text and "secret-text" not in _logs.text  # a truncated echo too
