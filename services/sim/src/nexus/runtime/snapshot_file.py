"""Snapshot files: header, zstd body, blake2b trailer, atomic write (DATA-MODEL §6.1, SC-9).

Layout: magic | header_len (u32 LE) | header (msgpack map) | body (zstd of `world.save`) |
trailer (blake2b-256 of every byte after the magic: header_len, header and body). The trailer
catches corruption, not tampering. `created_at` is informational and never enters state.
The directory must be on a POSIX filesystem (see `fsutil`).
"""

import hashlib
import os
import struct
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import msgpack
import zstandard

from nexus.core.step import TICK_DT
from nexus.core.world import FORMAT_VERSION, World, load, save, state_hash
from nexus.runtime.fsutil import fsync_dir

MAGIC = b"NXSNAP\0\1"
FILE_FORMAT_VERSION = 1
_LEN = struct.Struct("<I")
_TRAILER_LEN = 32
_MAX_HEADER = 64 * 1024  # a header is ~300 bytes; anything larger is corruption
# 64 MiB caps the decompressed world. SC-10's 3,000-entity world is far below it; raise the
# limit if a measured snapshot approaches it.
_MAX_BODY = 64 * 1024 * 1024
_KEEP_LAST = 20
_TICKS_PER_HOUR = round(3600 / TICK_DT)  # game time (DATA-MODEL §6.1, CFG-9)


class SnapshotError(ValueError):
    """A snapshot file that fails any check; never load it (DATA-MODEL §6.1)."""


@dataclass(frozen=True, slots=True)
class SnapshotHeader:
    format_version: int  # file layout, FILE_FORMAT_VERSION
    schema_version: int  # world encoding, core.world.FORMAT_VERSION
    campaign_id: str
    seed: int
    config_hash: str
    sim_build: str
    tick: int
    state_hash: str
    last_arrival_seq: int
    protocol_version: str  # contracts/VERSION (CONTRACTS §3.6)
    created_at: str  # UTC ISO-8601, informational only


def write_snapshot(
    directory: Path,
    world: World,
    *,
    last_arrival_seq: int,
    sim_build: str,
    protocol_version: str,
    created_at: str,
) -> Path:
    """Write `<tick:012d>.nxs` atomically (tmp, fsync, rename, fsync dir); returns its path."""
    c = world.campaign
    header = SnapshotHeader(
        FILE_FORMAT_VERSION,
        FORMAT_VERSION,
        c.id,
        c.seed,
        c.config_hash,
        sim_build,
        c.tick,
        state_hash(world),
        last_arrival_seq,
        protocol_version,
        created_at,
    )
    packed = msgpack.packb(asdict(header), use_bin_type=True)
    payload = _LEN.pack(len(packed)) + packed + zstandard.ZstdCompressor().compress(save(world))
    path = directory / f"{c.tick:012d}.nxs"
    tmp = path.with_name(path.name + ".tmp")  # one writer (the sim thread), so a fixed name is safe
    try:
        with tmp.open("wb") as f:
            f.write(MAGIC + payload + hashlib.blake2b(payload, digest_size=_TRAILER_LEN).digest())
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)  # never leave a partial file behind
        raise
    fsync_dir(directory)
    return path


def read_snapshot(path: Path) -> tuple[SnapshotHeader, World]:
    """Verify every check in DATA-MODEL §6.1, then return the header and the restored world."""
    data = path.read_bytes()
    if len(data) < len(MAGIC) + _LEN.size + _TRAILER_LEN or not data.startswith(MAGIC):
        raise SnapshotError(f"{path.name}: bad magic or too short")
    payload, trailer = data[len(MAGIC) : -_TRAILER_LEN], data[-_TRAILER_LEN:]
    if hashlib.blake2b(payload, digest_size=_TRAILER_LEN).digest() != trailer:
        raise SnapshotError(f"{path.name}: trailer checksum mismatch")
    (header_len,) = _LEN.unpack_from(payload)
    if header_len > min(_MAX_HEADER, len(payload) - _LEN.size):
        raise SnapshotError(f"{path.name}: header length {header_len} out of bounds")
    header = _header(payload[_LEN.size : _LEN.size + header_len], path.name)
    try:
        world = load(_decompress(payload[_LEN.size + header_len :]))
    # SnapshotError is a ValueError too; KeyError/TypeError cover malformed nested state.
    except (ValueError, KeyError, TypeError, zstandard.ZstdError) as e:
        raise SnapshotError(f"{path.name}: bad body: {e}") from e
    _check_matches(header, world, path.name)
    return header, world


def _header(raw: bytes, name: str) -> SnapshotHeader:
    try:
        d: Any = msgpack.unpackb(raw, raw=False)
    except Exception as e:  # msgpack raises several unrelated types on bad bytes
        raise SnapshotError(f"{name}: header is not msgpack") from e
    types = {f.name: f.type for f in fields(SnapshotHeader)}
    if not isinstance(d, dict) or set(d) != set(types):
        raise SnapshotError(f"{name}: header must have exactly the keys {sorted(types)}")
    for key, typ in types.items():
        if type(d[key]) is not typ:  # exact type: rejects bool where int is expected
            raise SnapshotError(f"{name}: header {key} must be {typ}, got {d[key]!r}")
    header = SnapshotHeader(**d)
    if (header.format_version, header.schema_version) != (FILE_FORMAT_VERSION, FORMAT_VERSION):
        versions = (header.format_version, header.schema_version)
        raise SnapshotError(f"{name}: unsupported format/schema versions {versions}")
    return header


def _decompress(body: bytes) -> bytes:
    size = zstandard.frame_content_size(body)
    if not 0 <= size <= _MAX_BODY:  # -1 = size not recorded; we always record it
        raise SnapshotError(f"body content size {size} out of bounds")
    return zstandard.ZstdDecompressor().decompress(body, max_output_size=_MAX_BODY)


def _check_matches(header: SnapshotHeader, world: World, name: str) -> None:
    c = world.campaign
    expected = (c.id, c.seed, c.config_hash, c.tick, state_hash(world))
    got = (header.campaign_id, header.seed, header.config_hash, header.tick, header.state_hash)
    if got != expected:
        raise SnapshotError(f"{name}: header {got} does not match the restored world {expected}")


def list_snapshots(directory: Path) -> list[Path]:
    """Snapshot files in tick order; other names (`.tmp`, strays) are ignored."""
    return sorted(directory.glob("[0-9]" * 12 + ".nxs"))


def snapshots_to_delete(paths: list[Path]) -> list[Path]:
    """Retention (SIM-CORE §5): keep the newest 20 and the earliest snapshot of each game hour.

    The newest is the campaign's final snapshot once it ends, so it is always kept.
    """
    by_tick = sorted(paths, key=lambda p: int(p.stem))
    keep = set(by_tick[-_KEEP_LAST:])
    hours: set[int] = set()
    for p in by_tick:
        hour = int(p.stem) // _TICKS_PER_HOUR
        if hour not in hours:
            hours.add(hour)
            keep.add(p)
    return [p for p in by_tick if p not in keep]
