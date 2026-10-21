"""Seeded simulation randomness: `SimRng` with named PCG64 sub-streams (SIM-CORE SC-5, ADR-0002).

Each subsystem draws only from its own stream, so a new draw in one subsystem never shifts another.
A stream is PCG XSL-RR 128/64 with NumPy's PCG64 multiplier, in pure Python (no new dependency).
Stream (state, increment) pairs come from blake2b over (campaign seed, stream name). Snapshot state
(SC-9) uses fixed-width hex strings because 128-bit integers do not fit msgpack's 64-bit ints.
"""

import hashlib
import re
from enum import StrEnum
from typing import Self

_MASK64 = (1 << 64) - 1
_MASK128 = (1 << 128) - 1
_MULT = 0x2360ED051FC65DA44385DF649FCCF645
_PERSON = b"nexus.simrng.v1"
_HEX_LEN = 32
_STATE = "state"
_INC = "inc"
_HEX_RE = re.compile(r"[0-9a-f]{32}")


class RngStream(StrEnum):
    """The closed set of sub-streams (SC-5). `fow` was removed by Q-FOW-5."""

    COMBAT = "combat"
    DIRECTOR = "director"
    SPAWN = "spawn"
    OBJECTIVE = "objective"
    TASKING = "tasking"


class PcgStream:
    """One PCG64 (XSL-RR 128/64) generator: advance, then output from the new state (as NumPy)."""

    __slots__ = ("_inc", "_state")

    def __init__(self, state: int, inc: int) -> None:
        if not 0 <= state <= _MASK128 or not 0 < inc <= _MASK128 or inc % 2 == 0:
            raise ValueError("PCG state must be a 128-bit int and inc an odd 128-bit int")
        self._state = state
        self._inc = inc

    def next_u64(self) -> int:
        self._state = (self._state * _MULT + self._inc) & _MASK128
        rot = self._state >> 122
        x = ((self._state >> 64) ^ self._state) & _MASK64
        return ((x >> rot) | (x << (64 - rot))) & _MASK64

    def random(self) -> float:
        """A float in [0, 1) from the top 53 bits of one draw."""
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def randbelow(self, n: int) -> int:
        """An unbiased int in [0, n) by rejection sampling; 1 <= n <= 2**64."""
        if not 1 <= n <= 1 << 64:
            raise ValueError(f"randbelow needs 1 <= n <= 2**64, got {n}")
        limit = (1 << 64) - (1 << 64) % n
        while True:
            x = self.next_u64()
            if x < limit:
                return x % n

    def randint(self, lo: int, hi: int) -> int:
        """An int in [lo, hi], both ends inclusive."""
        if hi < lo:
            raise ValueError(f"randint needs lo <= hi, got {lo} > {hi}")
        return lo + self.randbelow(hi - lo + 1)


def _derive(seed: int, name: RngStream) -> PcgStream:
    digest = hashlib.blake2b(
        seed.to_bytes(8, "big") + name.value.encode(), digest_size=32, person=_PERSON
    ).digest()
    return PcgStream(int.from_bytes(digest[:16], "big"), int.from_bytes(digest[16:], "big") | 1)


def _parse_hex(value: object) -> int:
    if not isinstance(value, str) or not _HEX_RE.fullmatch(value):
        raise ValueError(f"expected a {_HEX_LEN}-char lowercase hex string, got {value!r}")
    return int(value, 16)


class SimRng:
    """Per-campaign randomness. `stream(name)` returns the same `PcgStream` object every call."""

    __slots__ = ("_streams",)
    _streams: dict[RngStream, PcgStream]

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= _MASK64:
            raise ValueError(f"seed must be an int in [0, 2**64), got {seed!r}")
        self._streams = {name: _derive(seed, name) for name in RngStream}

    def stream(self, name: RngStream | str) -> PcgStream:
        """The stream for one subsystem. An unknown name raises ValueError; none is created."""
        return self._streams[RngStream(name)]

    def to_state(self) -> dict[str, dict[str, str]]:
        """Plain, sorted snapshot data (SC-9): stream name -> 32-char hex `state` and `inc`."""
        return {
            name.value: {_STATE: f"{s._state:032x}", _INC: f"{s._inc:032x}"}
            for name, s in sorted(self._streams.items())
        }

    @classmethod
    def from_state(cls, data: object) -> Self:
        """Rebuild from `to_state()` output (validated); the sequence continues exactly."""
        if not isinstance(data, dict) or set(data) != {n.value for n in RngStream}:
            raise ValueError("RNG state must map exactly the known stream names")
        streams: dict[RngStream, PcgStream] = {}
        for key, entry in data.items():
            if not isinstance(entry, dict) or set(entry) != {_STATE, _INC}:
                raise ValueError(f"stream {key!r} needs exactly 'state' and 'inc'")
            streams[RngStream(key)] = PcgStream(_parse_hex(entry[_STATE]), _parse_hex(entry[_INC]))
        rng = cls.__new__(cls)
        rng._streams = streams
        return rng
