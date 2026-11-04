"""Overlay WebSocket settings (WIRE-PROTOCOL WP-7, WP-11, WP-12, section 7; NX-170 part b).

Runtime/app config, not balance (CONFIG-AND-CONTENT section 4.2): it never enters the state hash.
Section 4.2 lists `server.ws_bind` only; the PROPOSED numbers below have no key there yet, so they
are defaults of this object and a deployment changes them in code until a runtime config loader
exists. Env overrides follow the section 4.2 pattern `NEXUS__SECTION__KEY`; the token is a secret
and is never in `repr`.
"""

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass, field


def _host_is(bind: str, test: str) -> bool:
    host = bind.rsplit(":", 1)[0].strip("[]")
    if host == "localhost":
        return test == "is_loopback"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # a hostname other than localhost is not known to be private
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped  # `::ffff:a.b.c.d` is judged as a.b.c.d (3.12 gets it wrong itself)
    return not ip.is_unspecified and bool(getattr(ip, test))  # 0.0.0.0 and :: are never safe


@dataclass(frozen=True)
class WsConfig:
    token: str = field(repr=False)  # SEC-API-2: the capability secret from the environment
    origins: frozenset[str]  # explicit allowlist, no wildcard (section 7.2)
    bind: str  # `host:port`, loopback or private (SEC-API-2)
    path: str = "/ws"
    debug_json: bool = False  # JSON text frames, loopback only (section 2.2)
    hello_timeout_s: float = 5.0  # WP-7
    ping_s: float = 15.0  # WP-12
    idle_s: float = 45.0  # WP-12
    max_clients: int = 8  # WP-12
    max_inbound_bytes: int = 4096  # WP-12
    queue_frames: int = 3  # WP-11
    gap_ticks: int = 10  # WP-3
    ack_per_s: int = 20  # WP-12
    close_timeout_s: float = 1.0  # how long a dropped client's close may take before we give up

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("ws token is empty: the endpoint fails closed")
        if not self.origins or "*" in self.origins:
            raise ValueError("ws origins must be an explicit, non-empty allowlist")
        if not (_host_is(self.bind, "is_loopback") or _host_is(self.bind, "is_private")):
            raise ValueError("ws bind must be loopback or a private address (SEC-API-2)")
        if self.debug_json and not _host_is(self.bind, "is_loopback"):
            raise ValueError("debug_json is honored only on loopback (WIRE-PROTOCOL 2.2)")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "WsConfig":
        """Reads `NEXUS__SERVER__WS_TOKEN`, `..._WS_BIND` and comma-separated `..._WS_ORIGINS`."""
        origins = env.get("NEXUS__SERVER__WS_ORIGINS", "")
        return cls(
            token=env.get("NEXUS__SERVER__WS_TOKEN", ""),
            origins=frozenset(o.strip() for o in origins.split(",") if o.strip()),
            bind=env.get("NEXUS__SERVER__WS_BIND", ""),
        )
