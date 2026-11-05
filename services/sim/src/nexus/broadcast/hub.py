"""Frame fan-out to overlay clients (WIRE-PROTOCOL WP-3, WP-8, WP-10, WP-11; NX-170 part b).

Threads: `Hub.on_tick` runs on the sim thread right after `step` (SIM-CORE 5.3-5.4). It builds the
tick's shared bytes (Delta, Hud once per second, a Snapshot when a client wants one) and hands
them to the event-loop thread with `call_soon_threadsafe`, which never blocks. Everything else
(per-client queues, sends, closes) runs on the loop thread. The hook only reads the world, so it
changes no `state_hash`.

A client starts `awaiting` a Snapshot and gets no Delta until it has one, so it never applies a
Delta without its base. A frame-build exception drops the tick's frames, logs it, and the next
good tick sends every client RESYNC then a Snapshot (section 6). A client whose bounded queue is
full is closed with 4004; the tick never waits on it.
"""

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import suppress

import msgpack
from starlette.websockets import WebSocket

from nexus.broadcast.config import WsConfig
from nexus.broadcast.frames import FrameBuilder, control, encode
from nexus.contracts.gen.events.event import Event
from nexus.core.step import TICK_DT
from nexus.core.world import World

log = logging.getLogger(__name__)
_HUD_EVERY = round(1 / TICK_DT)  # WP-10: at most 1 Hz, counted in ticks so it is deterministic


async def send_frame(ws: WebSocket, data: bytes, debug_json: bool) -> None:
    if debug_json:
        await ws.send_text(json.dumps(msgpack.unpackb(data)))
    else:
        await ws.send_bytes(data)


class Client:
    def __init__(self, ws: WebSocket, queue_frames: int) -> None:
        self.ws = ws
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(queue_frames)
        self.ready = False  # past the handshake: fan-out may queue to it
        self.awaiting = True  # needs a Snapshot before any Delta
        self.snap_tick = -1
        self.sender: asyncio.Task[None] | None = None
        self.dead = False
        self.ack_sec, self.ack_n = 0, 0


class Hub:
    def __init__(
        self,
        builder: FrameBuilder,
        world: World,
        cfg: WsConfig,
        *,
        protocol_version: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg, self.version, self._b, self._clock = cfg, protocol_version, builder, clock
        self.welcome = encode(builder.welcome(world))  # static for the campaign
        self.reload = encode(control(protocol_version, "RELOAD"))
        self._resync = encode(control(protocol_version, "RESYNC"))
        self.clients: set[Client] = set()
        self.tick = -1  # latest tick fanned out; loop thread only
        self._loop: asyncio.AbstractEventLoop | None = None
        self._want = threading.Event()  # a client awaits a Snapshot (loop sets, sim clears)
        self._failed = False  # sim thread only
        self._closers: set[asyncio.Task[None]] = set()

    def on_tick(self, world: World, events: Sequence[Event]) -> None:
        """Sim thread, after `step` (WP-8). Never raises and never waits on a client."""
        tick = world.campaign.tick
        try:
            delta = encode(self._b.delta(world, events))
            hud = encode(self._b.hud(world)) if tick % _HUD_EVERY == 0 else None
            resync, snap = self._failed, None
            if resync or self._want.is_set():
                self._want.clear()
                snap = encode(self._b.snapshot(world))  # at most once per tick, shared
            self._failed = False
        except Exception as e:  # noqa: BLE001 - section 6: drop the frame, log, resync next tick
            self._failed = True
            log.error(
                "frame build failed", extra={"fields": {"tick": tick, "error": type(e).__name__}}
            )
            return
        loop = self._loop
        if loop is not None and self.clients:
            with suppress(RuntimeError):  # the loop closed: shutting down
                loop.call_soon_threadsafe(self._fanout, tick, delta, hud, snap, resync)

    def _fanout(
        self, tick: int, delta: bytes, hud: bytes | None, snap: bytes | None, resync: bool
    ) -> None:
        self.tick = tick
        for c in list(self.clients):
            if not c.ready or c.dead:
                continue
            frames: list[bytes] = []
            if resync and not c.awaiting:  # one awaiting its first Snapshot needs no RESYNC
                self._start_resync(c)
            if c.awaiting:
                if snap is None:
                    continue  # asked after this tick's decision; the next tick builds it
                frames.append(snap)
                c.awaiting, c.snap_tick = False, tick
            else:
                frames += [delta] if hud is None else [delta, hud]
            for f in frames:
                self.offer(c, f)

    def _start_resync(self, c: Client) -> None:
        """Discard the client's queued frames (stale: it drops them after RESYNC), then queue
        RESYNC, so the resync burst of RESYNC plus a Snapshot never overflows the bound itself."""
        while not c.queue.empty():
            c.queue.get_nowait()
        c.awaiting = True
        self.offer(c, self._resync)

    def offer(self, c: Client, frame: bytes) -> None:
        try:
            c.queue.put_nowait(frame)
        except asyncio.QueueFull:
            self.kill(c, 4004)  # WP-11 SLOW_CLIENT

    def add(self, ws: WebSocket) -> Client | None:
        """Counts a connection from accept on, so unauthenticated ones are capped too (WP-12)."""
        self._loop = asyncio.get_running_loop()
        if len(self.clients) >= self.cfg.max_clients:
            return None
        c = Client(ws, self.cfg.queue_frames)
        self.clients.add(c)
        return c

    def activate(self, c: Client) -> None:
        """After a valid Hello: Welcome first, then the Snapshot the next tick builds (WP-7)."""
        c.queue.put_nowait(self.welcome)
        c.ready = True
        c.sender = asyncio.create_task(self._pump(c))
        self._want.set()

    def remove(self, c: Client) -> None:
        self.clients.discard(c)
        if c.sender:
            c.sender.cancel()

    async def _pump(self, c: Client) -> None:
        with suppress(Exception):  # the socket is gone; the handler sees the disconnect
            while True:
                await send_frame(c.ws, await c.queue.get(), self.cfg.debug_json)

    def on_ack(self, c: Client, applied_tick: int) -> None:
        """WP-3 and WP-12: a lagging Ack gets RESYNC then a Snapshot; the excess is ignored."""
        sec = int(self._clock())
        if sec != c.ack_sec:
            c.ack_sec, c.ack_n = sec, 0
        c.ack_n += 1
        if c.ack_n > self.cfg.ack_per_s or c.awaiting or applied_tick < c.snap_tick:
            return  # over the rate, a resync is pending, or stale from before the Snapshot
        if self.tick - applied_tick > self.cfg.gap_ticks:
            self._start_resync(c)
            self._want.set()

    def kill(self, c: Client, code: int) -> None:
        if not c.dead:
            c.dead = True
            task = asyncio.create_task(self._close(c, code))
            self._closers.add(task)
            task.add_done_callback(self._closers.discard)

    async def _close(self, c: Client, code: int) -> None:
        if c.sender:
            c.sender.cancel()
        with suppress(Exception):  # a client that never reads may not take the close either
            await asyncio.wait_for(c.ws.close(code), self.cfg.close_timeout_s)

    async def close_all(self, code: int) -> None:
        for c in list(self.clients):
            self.kill(c, code)
        await asyncio.gather(*self._closers)
