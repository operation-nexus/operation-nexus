"""Snapshot file tests (NX-103, DATA-MODEL §6.1, SIM-CORE SC-9)."""

import hashlib
import struct
from pathlib import Path
from typing import Any

import msgpack
import pytest
import zstandard

from nexus.core.world import Campaign, Vec2, World, save, state_hash, to_canonical
from nexus.runtime import snapshot_file
from nexus.runtime.snapshot_file import (
    SnapshotError,
    read_snapshot,
    snapshots_to_delete,
    write_snapshot,
)

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
CREATED_AT = "2026-10-21T12:00:00Z"


def make_world() -> World:
    w = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test", tick=4321))
    w.spawn(
        "STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(1000.25, 2000.5), vel=Vec2(0.1, 0), hp=100
    )
    w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(150e3, 80e3), hp=200)
    w.rng.stream("combat").next_u64()  # RNG state is snapshot state too
    return w


def write(directory: Path, world: World | None = None) -> Path:
    return write_snapshot(
        directory,
        world or make_world(),
        last_arrival_seq=77,
        sim_build="test-build",
        protocol_version="0.2",
        created_at=CREATED_AT,
    )


def test_round_trip_is_lossless_and_atomic(tmp_path: Path) -> None:
    world = make_world()
    path = write(tmp_path, world)
    assert path.name == "000000004321.nxs"
    assert [p.name for p in tmp_path.iterdir()] == ["000000004321.nxs"]  # no .tmp left
    assert path.read_bytes().startswith(b"NXSNAP\x00\x01")
    header, restored = read_snapshot(path)
    assert state_hash(restored) == state_hash(world) == header.state_hash
    assert to_canonical(restored, quantize=False) == to_canonical(world, quantize=False)
    assert (header.tick, header.last_arrival_seq, header.protocol_version) == (4321, 77, "0.2")
    assert (header.campaign_id, header.created_at) == (CAMPAIGN_ID, CREATED_AT)


def test_rewrite_of_same_tick_replaces_file(tmp_path: Path) -> None:
    write(tmp_path)
    write(tmp_path)
    assert len(list(tmp_path.iterdir())) == 1


def corrupt(path: Path, offset: int) -> None:
    data = bytearray(path.read_bytes())
    data[offset] ^= 0x01
    path.write_bytes(bytes(data))


@pytest.mark.parametrize("where", ["magic", "header_len", "header", "body", "trailer"])
def test_flipped_byte_is_rejected(tmp_path: Path, where: str) -> None:
    path = write(tmp_path)
    size = path.stat().st_size
    offset = {"magic": 3, "header_len": 8, "header": 20, "body": size - 40, "trailer": size - 1}
    corrupt(path, offset[where])
    with pytest.raises(SnapshotError):
        read_snapshot(path)


@pytest.mark.parametrize("keep", [0, 7, 12, 100, -1])
def test_truncated_file_is_rejected(tmp_path: Path, keep: int) -> None:
    path = write(tmp_path)
    path.write_bytes(path.read_bytes()[:keep])
    with pytest.raises(SnapshotError):
        read_snapshot(path)


def rewrite_header(path: Path, body: bytes | None = None, **changes: Any) -> None:
    """Re-encode the header with `changes` (and `body`) and a valid trailer, as a buggy writer
    would."""
    data = path.read_bytes()
    (n,) = struct.unpack_from("<I", data, 8)
    header = {**msgpack.unpackb(data[12 : 12 + n]), **changes}
    packed = msgpack.packb(header)
    payload = struct.pack("<I", len(packed)) + packed + (body or data[12 + n : -32])
    path.write_bytes(data[:8] + payload + hashlib.blake2b(payload, digest_size=32).digest())


@pytest.mark.parametrize(
    "changes",
    [
        {"state_hash": "00" * 32},
        {"tick": 4320},
        {"campaign_id": "0192f3a4-5b6c-7d8e-9f01-000000000000"},
        {"seed": 1},
        {"config_hash": "cfg-other"},
        {"format_version": 2},
        {"schema_version": 2},
        {"last_arrival_seq": True},  # wrong type
        {"extra": 1},
    ],
)
def test_header_mismatch_is_rejected(tmp_path: Path, changes: dict[str, Any]) -> None:
    path = write(tmp_path)
    rewrite_header(path)
    read_snapshot(path)  # the helper itself keeps a valid file valid
    rewrite_header(path, **changes)
    with pytest.raises(SnapshotError):
        read_snapshot(path)


def test_body_without_content_size_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path)
    body = zstandard.ZstdCompressor(write_content_size=False).compress(save(make_world()))
    rewrite_header(path, body=body)
    with pytest.raises(SnapshotError, match="content size"):
        read_snapshot(path)


def test_body_declaring_more_than_the_cap_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write(tmp_path)
    read_snapshot(path)
    monkeypatch.setattr(snapshot_file, "_MAX_BODY", 100)  # the real world body is larger
    with pytest.raises(SnapshotError, match="content size"):
        read_snapshot(path)


def test_failed_write_leaves_no_tmp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.fsync", fail)
    with pytest.raises(OSError):
        write(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_retention_keeps_newest_twenty_and_each_hours_first() -> None:
    # Every 300 ticks for 60,000 ticks; a game hour is 36,000 ticks.
    paths = [Path(f"{t:012d}.nxs") for t in range(0, 60_001, 300)]
    kept = {0, 36_000, *range(54_300, 60_001, 300)}
    assert snapshots_to_delete(list(reversed(paths))) == [
        p for p in paths if int(p.stem) not in kept
    ]
    assert snapshots_to_delete(paths[:20]) == []
    assert snapshots_to_delete([]) == []
