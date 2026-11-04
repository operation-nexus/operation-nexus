"""LocalSim's own send window (the shared suite only checks the invariant)."""

import asyncio

from conformance.chat.local_sim import SEND_WINDOW_S, LocalSim
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
