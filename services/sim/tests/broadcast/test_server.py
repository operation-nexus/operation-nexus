"""NX-170 part b: the overlay WebSocket server (WIRE-PROTOCOL 2-8).

No test sleeps in real time. Timeouts are injected: `hello_timeout_s=0` and `idle_s=0` make the
server's `wait_for` expire at once, the Ack-rate window reads a fake clock, and the slow client is
a fake socket whose send never completes. Frames reach the client only when the test drives a
tick, so every receive here is ordered by the test, not by a timer.
"""

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

import msgpack
import pytest
import uvicorn
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from starlette.testclient import TestClient, WebSocketDenialResponse, WebSocketTestSession
from starlette.websockets import WebSocket, WebSocketDisconnect

from nexus.broadcast.config import WsConfig
from nexus.broadcast.frames import FrameBuilder
from nexus.broadcast.hub import Client, Hub
from nexus.broadcast.server import create_app, serve
from nexus.core.step import step
from nexus.core.world import World
from nexus.runtime.campaign_config import load_campaign_config, start_campaign

CFG = load_campaign_config()
VERSION = "0.65"
TOKEN = "tok-9f3c1d7a-do-not-log"  # noqa: S105 - a test value
ORIGIN = "http://localhost:5173"
BIND = "127.0.0.1:8765"


def ws_config(**kw: Any) -> WsConfig:
    return WsConfig(token=TOKEN, origins=frozenset({ORIGIN}), bind=BIND, **kw)


class Sim:
    """The sim side: steps a world and calls the hook, as `SimRuntime._tick` does."""

    def __init__(self, **kw: Any) -> None:
        self.world: World = start_campaign("0192f3a4-5b6c-7d8e-9f01-23456789abcd", 3, CFG)
        self.builder = FrameBuilder(CFG.theater, protocol_version=VERSION, server_build="test")
        self.hub = Hub(self.builder, self.world, ws_config(**kw), protocol_version=VERSION)

    def tick(self, n: int = 1) -> None:
        for _ in range(n):
            self.hub.on_tick(self.world, step(self.world, []))


def hello(**kw: Any) -> bytes:
    body = {
        "type": "Hello",
        "v": VERSION,
        "client_kind": "OVERLAY",
        "capability_token": TOKEN,
        "last_tick": None,
    }
    return cast(bytes, msgpack.packb({**body, **kw}))


def ack(tick: int, v: str = VERSION) -> bytes:
    return cast(bytes, msgpack.packb({"type": "Ack", "v": v, "applied_tick": tick}))


def frame(ws: WebSocketTestSession) -> dict[str, Any]:
    return cast(dict[str, Any], msgpack.unpackb(ws.receive_bytes()))


def next_non_hud(ws: WebSocketTestSession) -> dict[str, Any]:
    while (got := frame(ws))["type"] == "Hud":
        pass
    return got


def close_code(ws: WebSocketTestSession, *, frames_ok: bool = True) -> int:
    with pytest.raises(WebSocketDisconnect) as e:
        while True:  # with frames_ok, a frame queued before the close may come first
            ws.receive_bytes()
            assert frames_ok, "a frame arrived before the close"
    return e.value.code


@contextmanager
def connect(sim: Sim, origin: str = ORIGIN) -> Iterator[WebSocketTestSession]:
    with (
        TestClient(create_app(sim.hub)) as client,
        client.websocket_connect("/ws", headers={"origin": origin}) as ws,
    ):
        yield ws


@contextmanager
def session(sim: Sim) -> Iterator[WebSocketTestSession]:
    """A connection past the handshake that has read its Welcome."""
    with connect(sim) as ws:
        ws.send_bytes(hello())
        assert frame(ws)["type"] == "Welcome"
        yield ws


def test_valid_flow_welcome_snapshot_delta_and_hud_once_per_second() -> None:
    sim = Sim()
    with session(sim) as ws:
        sim.tick()
        snap = frame(ws)
        assert (snap["type"], snap["tick"]) == ("Snapshot", 1)
        types = []
        for _ in range(10):  # ticks 2..11; the tick rate is 10 Hz, so tick 10 is the Hud's second
            sim.tick()
            types.append(frame(ws)["type"])
            if sim.world.campaign.tick == 10:
                types.append(frame(ws)["type"])
        assert types == ["Delta"] * 8 + ["Delta", "Hud", "Delta"]


def test_hello_not_in_time_closes_4001() -> None:
    with connect(Sim(hello_timeout_s=0)) as ws:
        assert close_code(ws) == 4001


@pytest.mark.parametrize(
    "first",
    [
        b"\xc1",  # not msgpack
        cast(bytes, msgpack.packb({"type": "Ack", "v": VERSION, "applied_tick": 1})),
        cast(bytes, msgpack.packb([1, 2, 3])),
        cast(bytes, msgpack.packb({"type": "Hello", "v": VERSION})),
    ],
)
def test_bad_first_frame_closes_4001(first: bytes) -> None:
    with connect(Sim()) as ws:
        ws.send_bytes(first)
        assert close_code(ws) == 4001


def test_text_frame_is_not_honored_without_debug_mode() -> None:
    with connect(Sim()) as ws:
        ws.send_text('{"type": "Hello"}')
        assert close_code(ws) == 4001


def test_wrong_client_kind_closes_4001() -> None:
    with connect(Sim()) as ws:
        ws.send_bytes(hello(client_kind="PIP"))
        assert close_code(ws) == 4001


def test_bad_token_closes_4002_with_no_frame_and_no_token_in_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    with connect(Sim()) as ws:
        ws.send_bytes(hello(capability_token=TOKEN + "x"))
        assert close_code(ws, frames_ok=False) == 4002  # a frame before the close fails the test
    assert "auth failed" in caplog.text
    assert TOKEN not in caplog.text


def test_major_mismatch_sends_reload_then_closes_4003() -> None:
    with connect(Sim()) as ws:
        ws.send_bytes(hello(v="999.0"))
        reload = frame(ws)
        assert (reload["type"], reload["action"]) == ("Control", "RELOAD")
        assert close_code(ws) == 4003


def test_minor_mismatch_is_ignored() -> None:
    with connect(Sim()) as ws:
        ws.send_bytes(hello(v="0.999"))
        assert frame(ws)["type"] == "Welcome"


def test_unknown_hello_fields_are_ignored() -> None:
    with connect(Sim()) as ws:
        ws.send_bytes(hello(future_field=1))
        assert frame(ws)["type"] == "Welcome"


def test_connection_cap_closes_4006() -> None:
    sim = Sim(max_clients=1)
    with session(sim), connect(sim) as second:
        assert close_code(second) == 4006


def test_cap_slot_is_released_when_a_client_leaves() -> None:
    sim = Sim(max_clients=1)
    with session(sim):
        pass
    with session(sim):  # would close 4006 if the first still held its slot
        assert len(sim.hub.clients) == 1


def test_bad_token_wins_over_a_bad_kind_and_no_frame_precedes_the_close() -> None:
    with connect(Sim()) as ws:
        ws.send_bytes(hello(client_kind="PIP", capability_token=TOKEN + "x"))
        assert close_code(ws, frames_ok=False) == 4002  # a frame before the close fails the test


def test_inbound_cap_is_exactly_4096_bytes() -> None:
    sim = Sim()
    with session(sim) as ws:
        ws.send_bytes(b"\x00" * 4096)  # at the cap: read, found invalid, dropped, still open
        sim.tick()
        assert frame(ws)["type"] == "Snapshot"
        ws.send_bytes(b"\x00" * 4097)
        assert close_code(ws) == 1009


def test_idle_client_closes_4005() -> None:
    with connect(Sim(idle_s=0)) as ws:
        ws.send_bytes(hello())
        assert close_code(ws) == 4005


def test_disallowed_origin_gets_http_403_before_the_upgrade() -> None:
    sim = Sim()
    with pytest.raises(WebSocketDenialResponse) as e, connect(sim, origin="http://evil.example"):
        pass
    assert e.value.status_code == 403
    assert not sim.hub.clients


def test_missing_origin_is_denied_too() -> None:
    with (
        TestClient(create_app(Sim().hub)) as client,
        pytest.raises(WebSocketDenialResponse) as e,
        client.websocket_connect("/ws"),
    ):
        pass
    assert e.value.status_code == 403


def test_bad_ack_is_logged_and_dropped_and_the_connection_survives(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    sim = Sim()
    with session(sim) as ws:
        ws.send_bytes(cast(bytes, msgpack.packb({"type": "Ack", "v": VERSION, "applied_tick": -5})))
        ws.send_bytes(b"\xc1")
        ws.send_text("{}")
        ws.send_bytes(cast(bytes, msgpack.packb({"type": "Mystery"})))
        sim.tick()
        assert frame(ws)["type"] == "Snapshot"
    assert caplog.text.count("contract_violation") == 3
    assert "unknown message type ignored" in caplog.text


def test_lagging_ack_gets_resync_then_snapshot() -> None:
    sim = Sim()
    with session(sim) as ws:
        sim.tick()
        assert frame(ws)["type"] == "Snapshot"
        for _ in range(12):
            sim.tick()
            assert next_non_hud(ws)["type"] == "Delta"
        ws.send_bytes(ack(1))  # 13 - 1 = 12 ticks behind, past the limit of 10
        # The Ack is handled on the loop thread at some point; RESYNC is queued then and the
        # Snapshot comes with the next tick built after it. Drive one tick per frame read until
        # the Snapshot, so the test needs no timing: every read has a tick behind it.
        seen: list[str] = []
        for _ in range(100):
            sim.tick()
            got = next_non_hud(ws)
            seen.append(got["type"] + (got.get("action") or ""))
            if got["type"] == "Snapshot":
                break
        else:
            pytest.fail(f"no Snapshot: {seen}")
        assert got["tick"] > 13
        assert "ControlRESYNC" in seen and seen.index("ControlRESYNC") < seen.index("Snapshot")
        assert set(seen) <= {"Delta", "ControlRESYNC", "Snapshot"}


def test_ack_within_the_limit_and_over_the_rate_cause_no_resync() -> None:
    now = [100.0]
    sim = Sim()
    hub = Hub(sim.builder, sim.world, ws_config(), protocol_version=VERSION, clock=lambda: now[0])
    c = Client(cast(WebSocket, object()), 3)
    c.awaiting, hub.tick = False, 100
    for _ in range(20):
        hub.on_ack(c, 95)  # 5 behind: inside the limit
    hub.on_ack(c, 0)  # the 21st in this second: ignored although far behind
    assert not c.awaiting and c.queue.empty()
    now[0] += 1
    hub.on_ack(c, 0)
    assert c.awaiting and c.queue.qsize() == 1  # RESYNC queued


def test_gap_limit_boundary_and_no_second_resync_from_stale_acks() -> None:
    sim = Sim()
    c = Client(cast(WebSocket, object()), 3)
    c.awaiting, sim.hub.tick = False, 20
    sim.hub.on_ack(c, 10)  # exactly 10 behind: allowed
    assert not c.awaiting and c.queue.empty()
    sim.hub.on_ack(c, 9)  # 11 behind: past the limit
    assert c.awaiting and c.queue.qsize() == 1
    sim.hub.on_ack(c, 0)  # a resync is pending: no second RESYNC
    assert c.queue.qsize() == 1
    c.awaiting, c.snap_tick = False, 15  # a Snapshot was applied at 15
    sim.hub.on_ack(c, 3)  # an Ack from before it
    assert not c.awaiting and c.queue.qsize() == 1


@pytest.mark.parametrize("by_gap", [True, False])
def test_resync_discards_a_full_queue_instead_of_dropping_the_client(by_gap: bool) -> None:
    async def main() -> None:
        sim = Sim()
        hub, c = sim.hub, Client(cast(WebSocket, StuckWs()), 3)
        hub.clients.add(c)
        c.ready, c.awaiting, hub.tick = True, False, 20
        for i in range(3):
            c.queue.put_nowait(b"stale%d" % i)  # full, and nothing pumps it
        if by_gap:
            hub.on_ack(c, 0)
            hub._fanout(21, b"d", None, b"snap", False)
        else:
            hub._fanout(21, b"d", None, b"snap", True)  # after a frame-build failure
        await asyncio.sleep(0)
        assert not c.dead
        assert [c.queue.get_nowait() for _ in range(c.queue.qsize())] == [hub._resync, b"snap"]

    asyncio.run(main())


def test_server_shutdown_sends_1001_before_uvicorn_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[object] = []

    class StubHub:
        async def close_all(self, code: int) -> None:
            order.append(("close_all", code))

    async def base_shutdown(self: object, sockets: object = None) -> None:
        order.append("uvicorn")

    monkeypatch.setattr(uvicorn.Server, "shutdown", base_shutdown)
    server = serve(Sim().hub)
    server._hub = StubHub()  # type: ignore[attr-defined]
    asyncio.run(server.shutdown())
    assert order == [("close_all", 1001), "uvicorn"]


class StuckWs:
    """A client that never reads: its send never completes."""

    def __init__(self) -> None:
        self.closed: int | None = None

    async def send_bytes(self, data: bytes) -> None:
        await asyncio.Event().wait()

    async def close(self, code: int) -> None:
        self.closed = code


class DrainWs(StuckWs):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[bytes] = []

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)


def test_slow_client_is_dropped_with_4004_and_the_tick_never_waits_on_it() -> None:
    async def main() -> tuple[StuckWs, DrainWs]:
        sim = Sim()
        slow, healthy = StuckWs(), DrainWs()
        for ws in (slow, healthy):
            sim.hub.activate(cast(Client, sim.hub.add(cast(WebSocket, ws))))
        await asyncio.sleep(0)  # a zero sleep only yields to the pump tasks
        # The ticks run on their own thread, as in production; if one waited on the stuck client
        # this would never return (it has no timer to rescue it).
        for _ in range(8):
            await asyncio.to_thread(sim.tick)
            await asyncio.sleep(0)  # let the fan-out and the healthy client's pump run
            await asyncio.sleep(0)
        return slow, healthy

    slow, healthy = asyncio.run(main())
    assert slow.closed == 4004
    assert healthy.closed is None and len(healthy.sent) >= 8  # Welcome, Snapshot, Deltas


def test_frame_build_exception_drops_the_frame_then_resyncs(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.DEBUG)
    sim = Sim()
    with session(sim) as ws:
        sim.tick()
        assert frame(ws)["type"] == "Snapshot"
        real = sim.builder.delta

        def boom(*a: Any) -> Any:
            raise RuntimeError("secret-internal-detail")

        monkeypatch.setattr(sim.builder, "delta", boom)
        sim.tick()  # dropped: nothing is sent
        failed = [r for r in caplog.records if r.getMessage() == "frame build failed"]
        assert [getattr(r, "fields") for r in failed] == [{"tick": 2, "error": "RuntimeError"}]  # noqa: B009
        assert "secret-internal-detail" not in caplog.text
        monkeypatch.setattr(sim.builder, "delta", real)
        sim.tick()
        got = frame(ws)
        assert (got["type"], got["action"]) == ("Control", "RESYNC")
        snap = frame(ws)
        assert (snap["type"], snap["tick"]) == ("Snapshot", 3)


def test_shutdown_closes_clients_with_1001() -> None:
    async def main() -> int | None:
        sim = Sim()
        ws = StuckWs()
        sim.hub.add(cast(WebSocket, ws))
        await sim.hub.close_all(1001)
        return ws.closed

    assert asyncio.run(main()) == 1001


def test_snapshot_is_built_once_per_tick_for_all_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    async def main() -> list[DrainWs]:
        sim = Sim()
        calls: list[int] = []
        real = sim.builder.snapshot

        def counted(w: World) -> Any:
            calls.append(1)
            return real(w)

        monkeypatch.setattr(sim.builder, "snapshot", counted)
        wss = [DrainWs(), DrainWs(), DrainWs()]
        for ws in wss:
            sim.hub.activate(cast(Client, sim.hub.add(cast(WebSocket, ws))))
        await asyncio.to_thread(sim.tick)
        await asyncio.sleep(0)
        assert len(calls) == 1
        await asyncio.to_thread(sim.tick)  # no new demand: no second Snapshot build
        await asyncio.sleep(0)
        assert len(calls) == 1
        return wss

    wss = asyncio.run(main())
    assert len({ws.sent[1] for ws in wss}) == 1  # the same snapshot bytes for each


@pytest.mark.parametrize(
    "kw",
    [
        {"token": ""},
        {"origins": frozenset({"*"})},
        {"origins": frozenset()},
        {"bind": "0.0.0.0:80"},
        {"bind": "[::]:80"},
        {"bind": "[::ffff:0.0.0.0]:80"},
        {"bind": "[::ffff:8.8.8.8]:80"},
        {"bind": "8.8.8.8:80"},
        {"bind": "10.0.0.5:80", "debug_json": True},
    ],
)
def test_config_refuses_unsafe_settings(kw: dict[str, Any]) -> None:
    base: dict[str, Any] = {"token": TOKEN, "origins": frozenset({ORIGIN}), "bind": BIND}
    with pytest.raises(ValueError, match=r"ws |debug_json"):
        WsConfig(**{**base, **kw})


@pytest.mark.parametrize("bind", ["127.0.0.1:80", "[::1]:80", "10.1.2.3:80", "localhost:80"])
def test_config_accepts_loopback_and_private_binds(bind: str) -> None:
    assert WsConfig(token=TOKEN, origins=frozenset({ORIGIN}), bind=bind).bind == bind


def test_config_from_env_hides_the_token_and_allows_private_bind() -> None:
    cfg = WsConfig.from_env(
        {
            "NEXUS__SERVER__WS_TOKEN": TOKEN,
            "NEXUS__SERVER__WS_ORIGINS": f"{ORIGIN}, http://127.0.0.1:5173",
            "NEXUS__SERVER__WS_BIND": "10.1.2.3:9000",
        }
    )
    assert TOKEN not in repr(cfg) and len(cfg.origins) == 2


def test_serve_builds_a_uvicorn_server_from_the_config() -> None:
    server = serve(Sim().hub)
    c = server.config
    assert (c.host, c.port, c.ws_max_size, c.ws_ping_interval) == ("127.0.0.1", 8765, 4096, 15.0)
    assert c.ws_ping_timeout is None  # the idle close is ours (4005), never the library's 1011


# Hostile input (WP-13, section 7.5)
junk = st.recursive(
    st.none() | st.booleans() | st.integers(-(2**40), 2**40) | st.text(max_size=20),
    lambda kids: (
        st.lists(kids, max_size=4) | st.dictionaries(st.text(max_size=8), kids, max_size=4)
    ),
    max_leaves=12,
)
FUZZ = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def pack(obj: Any) -> bytes:
    return cast(bytes, msgpack.packb(obj))


@FUZZ
@given(
    first=st.one_of(
        st.binary(max_size=300),
        junk.map(pack),
        st.fixed_dictionaries(
            {
                "type": st.sampled_from(["Hello", "hello", "Ack", ""]),
                "v": st.text(max_size=8) | st.sampled_from([VERSION, "0.1"]),
                "client_kind": st.text(max_size=8) | st.sampled_from(["OVERLAY", "PIP"]),
                "capability_token": st.text(max_size=140) | st.just(TOKEN + "x"),
                "last_tick": junk,
            },
            optional={"echo": st.just(TOKEN)},
        ).map(pack),
    )
)
def test_fuzz_hello_never_gets_in_and_the_token_never_leaks(
    first: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with connect(Sim()) as ws:
        ws.send_bytes(first)
        with pytest.raises(WebSocketDisconnect) as e:
            while True:
                got = ws.receive_bytes()
                assert TOKEN.encode() not in got
                assert msgpack.unpackb(got)["type"] != "Welcome"  # no valid token was sent
        assert e.value.code in {4001, 4002, 4003}
    assert TOKEN not in caplog.text


@FUZZ
@given(frames=st.lists(st.binary(max_size=300) | junk.map(pack), min_size=1, max_size=5))
def test_fuzz_ack_junk_is_dropped_and_the_connection_survives(
    frames: list[bytes], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    sim = Sim()
    with session(sim) as ws:
        for f in frames:
            ws.send_bytes(f)
        sim.tick()  # still connected: the Snapshot arrives
        assert frame(ws)["type"] == "Snapshot"
    assert TOKEN not in caplog.text
