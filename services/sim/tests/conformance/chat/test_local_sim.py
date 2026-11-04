"""LocalSim's own send window (the shared suite only checks the invariant)."""

import asyncio

from conformance.chat.local_sim import SEND_WINDOW_S, LocalSim, envelope
from nexus.gateway.fakes import FakeClock


def test_send_window_edge() -> None:
    clock = FakeClock(1000.0)
    sim = LocalSim(clock)
    budget = int((sim.capabilities.max_reply_rate or 0) * SEND_WINDOW_S)
    asyncio.run(sim.send_batch(["ok"] * budget))
    assert len(sim.sent) == budget
    clock.advance(SEND_WINDOW_S - 0.01)
    asyncio.run(sim.send_batch(["ok"]))
    assert len(sim.sent) == budget and sim.refused == 1  # still inside the window
    clock.advance(0.01)  # exactly SEND_WINDOW_S after the first batch: it has left the window
    asyncio.run(sim.send_batch(["ok"]))
    assert len(sim.sent) == budget + 1


def test_a_drop_mid_iteration_stops_delivery_and_keeps_the_rest() -> None:
    sim = LocalSim(FakeClock(1000.0))
    for i in range(3):
        sim.inject(envelope(f"!join x{i}", f"m{i}"))

    async def read_one_then_drop() -> list[str]:
        got = []
        async for env in sim.messages():
            got.append(env.platform_message_id)
            sim.drop()
        return got

    assert asyncio.run(read_one_then_drop()) == ["m0"]
    sim.restore()

    async def drain() -> list[str]:
        return [env.platform_message_id async for env in sim.messages()]

    assert asyncio.run(drain()) == ["m1", "m2"]
