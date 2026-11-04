"""The overlay WebSocket endpoint: handshake, auth, caps and close codes (WIRE-PROTOCOL 2-7).

One route (`WsConfig.path`, default `/ws`) on FastAPI under uvicorn (ADR-0004, Q-CT-14). Hostile
input (AGENTS.md rule 4): every inbound frame is size-capped, decoded and validated against its
schema before use; nothing a client sent, the token least of all, is logged or echoed. A bad
first frame closes (4001); a bad `Ack` is logged as `contract_violation` and dropped (WP-13).

Ping (WP-12) is uvicorn's protocol-level ping at `ping_s`; the app cannot see pongs, so the idle
close (4005) counts inbound application frames. The overlay sends an `Ack` per Delta.
"""

import asyncio
import hmac
import json
import logging
from contextlib import suppress
from typing import Any

import msgpack
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, ValidationError
from starlette.responses import PlainTextResponse
from starlette.websockets import WebSocket

from nexus.broadcast.config import WsConfig
from nexus.broadcast.hub import Client, Hub, send_frame
from nexus.contracts.gen.wire.ack import Ack
from nexus.contracts.gen.wire.hello import Hello

log = logging.getLogger(__name__)
_BAD_FRAME = (ValueError, TypeError, OverflowError, RecursionError, msgpack.UnpackException)


class _Close(Exception):
    """End the session; `code` None means the peer is already gone."""

    def __init__(self, code: int | None) -> None:
        self.code = code


async def _recv(ws: WebSocket, cfg: WsConfig, timeout: float, on_timeout: int) -> object:
    """One inbound frame decoded (None if undecodable). Raises `_Close` on timeout, size, hangup."""
    try:
        msg = await asyncio.wait_for(ws.receive(), timeout)
    except TimeoutError:
        raise _Close(on_timeout) from None
    if msg["type"] == "websocket.disconnect":
        raise _Close(None)
    raw: bytes | str | None = msg.get("bytes")
    raw = msg.get("text") if raw is None else raw
    if raw is None or len(raw.encode() if isinstance(raw, str) else raw) > cfg.max_inbound_bytes:
        raise _Close(1009)
    try:
        if isinstance(raw, bytes):
            return msgpack.unpackb(raw)
        return json.loads(raw) if cfg.debug_json else None
    except _BAD_FRAME:
        return None


def _validate[M: BaseModel](model: type[M], obj: object) -> M | None:
    """WP-2: unknown fields are ignored, so only the model's own fields are kept."""
    if not isinstance(obj, dict):
        return None
    known = {k: v for k, v in obj.items() if k in model.model_fields}
    try:
        return model.model_validate(known, strict=True)
    except ValidationError:
        return None  # never log the errors: they carry the input (the token, for a Hello)


async def _handshake(hub: Hub, ws: WebSocket) -> None:
    cfg = hub.cfg
    hello = _validate(Hello, await _recv(ws, cfg, cfg.hello_timeout_s, 4001))
    if hello is None:
        log.warning("contract_violation", extra={"fields": {"schema": "wire/hello.json"}})
        raise _Close(4001)
    if not hmac.compare_digest(hello.capability_token.encode(), cfg.token.encode()):
        log.warning("auth failed")  # SEC-API-2: no token, not even a part of it
        raise _Close(4002)
    if hello.client_kind != "OVERLAY":
        raise _Close(4001)
    if hello.v.split(".")[0] != hub.version.split(".")[0]:  # WP-1: a minor mismatch is ignored
        await send_frame(ws, hub.reload, cfg.debug_json)
        raise _Close(4003)


async def _serve_client(hub: Hub, ws: WebSocket, c: Client) -> None:
    cfg = hub.cfg
    await _handshake(hub, ws)
    hub.activate(c)
    while True:
        obj: Any = await _recv(ws, cfg, cfg.idle_s, 4005)
        kind = obj.get("type") if isinstance(obj, dict) else None
        if kind == "Ack":
            ack = _validate(Ack, obj)
            if ack is not None:
                hub.on_ack(c, ack.applied_tick)
                continue
        elif kind is not None:
            log.warning("unknown message type ignored")  # WP-2
            continue
        log.warning("contract_violation", extra={"fields": {"schema": "wire/ack.json"}})  # WP-13


def create_app(hub: Hub) -> FastAPI:
    cfg = hub.cfg
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.websocket(cfg.path)
    async def overlay(ws: WebSocket) -> None:
        if ws.headers.get("origin") not in cfg.origins:  # section 7.2: before the upgrade
            log.warning("origin denied")
            await ws.send_denial_response(PlainTextResponse("forbidden", 403))
            return
        await ws.accept()
        c = hub.add(ws)
        try:
            if c is None:
                raise _Close(4006)
            await _serve_client(hub, ws, c)
        except _Close as e:
            if e.code is not None:
                with suppress(Exception):  # the peer may have gone
                    await ws.close(e.code)
        finally:
            if c is not None:
                hub.remove(c)

    return app


class _Server(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, hub: Hub) -> None:
        super().__init__(config)
        self._hub = hub

    async def shutdown(self, sockets: Any = None) -> None:
        await self._hub.close_all(1001)  # SERVER_RESTART, before uvicorn's own 1012 close
        await super().shutdown(sockets)


def serve(hub: Hub) -> uvicorn.Server:
    """A uvicorn server for `hub`; the caller runs `await server.serve()` on the event loop."""
    cfg = hub.cfg
    host, port = cfg.bind.rsplit(":", 1)
    config = uvicorn.Config(
        create_app(hub),
        host=host.strip("[]"),
        port=int(port),
        ws_ping_interval=cfg.ping_s,
        ws_ping_timeout=None,  # idle is ours (4005); a library timeout would close with 1011
        ws_max_size=cfg.max_inbound_bytes,
        ws_per_message_deflate=False,
        log_config=None,
        server_header=False,
    )
    return _Server(config, hub)
