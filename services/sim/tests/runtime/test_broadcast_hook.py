"""The runtime's broadcaster hook (WIRE-PROTOCOL WP-8): it reads the world and changes nothing,
so the state hash is the same with the hook attached and detached (determinism test, NX-170b)."""

from collections.abc import Callable, Sequence
from pathlib import Path

from nexus.broadcast.config import WsConfig
from nexus.broadcast.frames import FrameBuilder
from nexus.broadcast.hub import Hub
from nexus.contracts.gen.events.event import Event
from nexus.core.world import World, state_hash
from nexus.runtime.campaign_config import load_campaign_config, start_campaign
from nexus.runtime.clock import FixedStepClock
from nexus.runtime.command_log import CommandLogWriter
from nexus.runtime.inbox import Inbox
from nexus.runtime.loop import SimRuntime

CFG = load_campaign_config()
CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
TICKS = 40  # past the first Hud (tick 10) and several Deltas


def run(
    directory: Path,
    log_writer: Callable[..., CommandLogWriter],
    on_tick: Callable[[World, Sequence[Event]], None] | None,
) -> tuple[str, int]:
    now = [0.0]
    world = start_campaign(CAMPAIGN, 7, CFG)
    runtime = SimRuntime(
        world,
        Inbox(capacity=10, next_tick=1),
        FixedStepClock(lambda: now[0]),
        log_writer(directory),
        directory,
        protocol_version="0.65",
        sim_build="test",
        created_at=lambda: "2026-11-04T12:00:00Z",
        on_tick=on_tick,
    )
    for _ in range(TICKS):
        now[0] += 0.1  # TICK_DT
        runtime.run_due()
    return state_hash(runtime.world), runtime.world.campaign.tick


def test_state_hash_is_the_same_with_the_broadcaster_attached_and_detached(
    tmp_path: Path, log_writer: Callable[..., CommandLogWriter]
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    detached = run(tmp_path / "a", log_writer, None)
    world = start_campaign(CAMPAIGN, 7, CFG)
    builder = FrameBuilder(CFG.theater, protocol_version="0.65", server_build="test")
    cfg = WsConfig(token="t", origins=frozenset({"http://localhost"}), bind="127.0.0.1:1")  # noqa: S106
    hub = Hub(builder, world, cfg, protocol_version="0.65")
    hub._want.set()  # also build a Snapshot on the first tick, the heaviest path
    ticks: list[int] = []

    def hook(w: World, events: Sequence[Event]) -> None:
        ticks.append(w.campaign.tick)
        hub.on_tick(w, events)

    attached = run(tmp_path / "b", log_writer, hook)
    assert detached == attached and detached[1] == TICKS
    assert ticks == list(range(1, TICKS + 1))  # once per tick, after step
