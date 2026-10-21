"""Command log tests (NX-103, DATA-MODEL §6.2, SIM-CORE SC-8)."""

import json
import os
from pathlib import Path
from typing import Any

import pytest
import zstandard

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.runtime import command_log
from nexus.runtime.command_log import (
    CommandLogError,
    CommandLogReader,
    CommandLogWriter,
    LogEntry,
    Tombstone,
    segment_path,
)

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
COMMANDER = "0192f0c1-7a2b-7c3d-8e4f-0123456789ab"


def join(seq: int, tick: int) -> JoinCommand:
    return JoinCommand.model_validate(
        {
            "kind": "JOIN",
            "source": "CHAT",
            "issuer": {"commander_id": COMMANDER},
            "target_tick": tick,
            "arrival_seq": seq,
            "correlation_id": f"msg-{seq}",
            "role": "LOGI",
            "target": {"node_id": "n1"} if seq % 2 else None,
            "hold": False,
        }
    )


def writer(directory: Path, segment: int = 1, next_seq: int = 1, **kw: Any) -> CommandLogWriter:
    kw.setdefault("campaign_id", CAMPAIGN_ID)
    return CommandLogWriter(
        directory, protocol_version="0.2", segment=segment, next_arrival_seq=next_seq, **kw
    )


def read_all(directory: Path) -> tuple[list[LogEntry], bool]:
    reader = CommandLogReader(directory)
    return list(reader), reader.truncated_tail


def write_ticks(directory: Path, ticks: int, per_tick: int = 2) -> list[JoinCommand]:
    """One flush (frame) per tick, like the 1 s flush cadence."""
    w = writer(directory)
    commands: list[JoinCommand] = []
    for tick in range(1, ticks + 1):
        batch = [join(len(commands) + i + 1, tick) for i in range(per_tick)]
        w.append(batch)
        w.flush()
        commands += batch
    w.close()
    return commands


def test_round_trip_across_rotation_with_tombstone(tmp_path: Path) -> None:
    w = writer(tmp_path)
    w.append([join(1, 1), join(2, 1)])
    w.flush()
    w.append([join(3, 2)])
    w.append_tombstone(2)
    w.rotate()
    w.append([join(4, 3), join(5, 3)])
    w.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["000001.nxl.zst", "000002.nxl.zst"]
    entries, truncated = read_all(tmp_path)
    expected = [join(1, 1), join(2, 1), join(3, 2), Tombstone(2), join(4, 3), join(5, 3)]
    assert entries == expected
    assert not truncated


def test_reopen_continues_the_segment(tmp_path: Path) -> None:
    w = writer(tmp_path)
    w.append([join(1, 1)])
    w.close()
    w = writer(tmp_path, next_seq=2)
    w.append([join(2, 2)])
    w.close()
    assert [p.name for p in tmp_path.iterdir()] == ["000001.nxl.zst"]
    assert read_all(tmp_path) == ([join(1, 1), join(2, 2)], False)


def test_writer_refuses_out_of_order_seq(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="arrival_seq"):
        writer(tmp_path).append([join(2, 1)])


def test_record_is_the_flat_contract_and_bytes_are_deterministic(tmp_path: Path) -> None:
    contents = []
    for run in ("a", "b"):
        (tmp_path / run).mkdir()
        write_ticks(tmp_path / run, ticks=3)
        contents.append(segment_path(tmp_path / run, 1).read_bytes())
    assert contents[0] == contents[1]
    lines = zstandard.ZstdDecompressor().decompressobj().decompress(contents[0])  # frame 1
    header, first = lines.splitlines()[:2]
    assert json.loads(header) == {
        "header": {
            "campaign_id": CAMPAIGN_ID,
            "first_arrival_seq": 1,
            "format_version": 1,
            "protocol_version": "0.2",
        }
    }
    assert first == (
        b'{"arrival_seq":1,"correlation_id":"msg-1","hold":false,'
        b'"issuer":{"commander_id":"0192f0c1-7a2b-7c3d-8e4f-0123456789ab"},"kind":"JOIN",'
        b'"role":"LOGI","source":"CHAT","target":{"node_id":"n1"},"target_tick":1}'
    )


def frame_ends(path: Path) -> list[int]:
    """Byte offset where each frame ends, found by decoding frame by frame."""
    data, ends = path.read_bytes(), []
    while data:
        d = zstandard.ZstdDecompressor().decompressobj()
        d.decompress(data)
        data = d.unused_data
        ends.append(path.stat().st_size - len(data))
    return ends


def test_torn_last_frame_is_dropped_and_reported(tmp_path: Path) -> None:
    commands = write_ticks(tmp_path, ticks=4)
    path = segment_path(tmp_path, 1)
    full = path.read_bytes()
    ends = frame_ends(path)
    assert len(ends) == 4
    for cut in (ends[2] + 3, (ends[2] + ends[3]) // 2, ends[3] - 1):
        path.write_bytes(full[:cut])
        assert read_all(tmp_path) == (commands[:6], True)


@pytest.mark.parametrize("where", ["first-header", "first-body", "last-start", "last-end"])
def test_reopen_after_crash_cuts_the_torn_tail_and_continues(tmp_path: Path, where: str) -> None:
    commands = write_ticks(tmp_path, ticks=4)
    path = segment_path(tmp_path, 1)
    full, ends = path.read_bytes(), frame_ends(path)
    cut = {"first-header": 2, "first-body": ends[0] - 1, "last-start": ends[2] + 3}.get(
        where, ends[3] - 1
    )
    path.write_bytes(full[:cut])
    start = max([0] + [e for e in ends if e <= cut])
    kept = commands[: 2 * ends.index(start) + 2] if start else []
    w = writer(tmp_path, next_seq=len(kept) + 1)
    assert w.recovered_torn_bytes == cut - start
    w.append([join(len(kept) + 1, 9)])
    w.close()
    assert read_all(tmp_path) == ([*kept, join(len(kept) + 1, 9)], False)
    assert (tmp_path / f"000001.nxl.zst.torn-{start}").read_bytes() == full[start:cut]


@pytest.mark.parametrize(
    "kw",
    [
        {"next_seq": 4},  # 2 commands survive, so 3 is next
        {"next_seq": 2},
        {"campaign_id": "0192f3a4-5b6c-7d8e-9f01-000000000000"},
        {"protocol_version": "0.3"},
    ],
)
def test_reopen_that_does_not_continue_the_segment_raises(tmp_path: Path, kw: Any) -> None:
    write_ticks(tmp_path, ticks=1)
    kw = {"next_seq": 3, **kw}
    with pytest.raises(CommandLogError):
        CommandLogWriter(
            tmp_path,
            campaign_id=kw.get("campaign_id", CAMPAIGN_ID),
            protocol_version=kw.get("protocol_version", "0.2"),
            next_arrival_seq=kw["next_seq"],
        )


def test_bad_batch_buffers_nothing(tmp_path: Path) -> None:
    w = writer(tmp_path)
    with pytest.raises(ValueError, match="arrival_seq"):
        w.append([join(1, 1), join(3, 1)])
    w.append([join(1, 1)])
    w.close()
    assert read_all(tmp_path) == ([join(1, 1)], False)


def test_flush_failure_drops_the_buffer_and_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = writer(tmp_path)
    w.append([join(1, 1)])

    def fail(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="disk full"):
        w.flush()
    w.close()  # nothing left to retry
    w.append([join(2, 1)])
    with pytest.raises(ValueError, match="closed"):
        w.flush()


def test_damaged_header_of_final_frame_raises(tmp_path: Path) -> None:
    """A complete final frame whose header is damaged raises; it is not taken for a torn tail."""
    write_ticks(tmp_path, ticks=3)
    path = segment_path(tmp_path, 1)
    data = bytearray(path.read_bytes())
    data[frame_ends(path)[1]] ^= 0xFF  # first magic byte of the final frame
    path.write_bytes(bytes(data))
    with pytest.raises(CommandLogError, match="frame header"):
        read_all(tmp_path)


def test_cumulative_decompressed_size_is_capped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(command_log, "_MAX_SEGMENT_DECOMPRESSED", 1 << 20)
    tombstones = _tombstone_lines(5_000)  # ~200 KB per frame, a few hundred bytes compressed
    frames = [zstandard.ZstdCompressor().compress(tombstones) for _ in range(10)]
    header = zstandard.ZstdCompressor().compress(json.dumps(HEADER).encode() + b"\n")
    segment_path(tmp_path, 1).write_bytes(header + b"".join(frames))
    assert len(segment_path(tmp_path, 1).read_bytes()) < 10_000
    with pytest.raises(CommandLogError, match="decompressed bytes"):
        read_all(tmp_path)


def _tombstone_lines(n: int) -> bytes:
    return b'{"reason":"STEP_EXCEPTION","tombstone":1}\n' * n


def test_corrupt_middle_frame_raises(tmp_path: Path) -> None:
    write_ticks(tmp_path, ticks=4)
    path = segment_path(tmp_path, 1)
    data = bytearray(path.read_bytes())
    data[(frame_ends(path)[1] + frame_ends(path)[2]) // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(CommandLogError):
        read_all(tmp_path)


def test_torn_frame_in_an_earlier_segment_raises(tmp_path: Path) -> None:
    w = writer(tmp_path)
    w.append([join(1, 1)])
    w.rotate()
    w.append([join(2, 2)])
    w.close()
    first = segment_path(tmp_path, 1)
    first.write_bytes(first.read_bytes()[:-2])
    with pytest.raises(CommandLogError, match="non-final"):
        read_all(tmp_path)


def test_empty_last_segment_after_rotation_is_skipped(tmp_path: Path) -> None:
    write_ticks(tmp_path, ticks=1)
    segment_path(tmp_path, 2).touch()
    assert read_all(tmp_path) == ([join(1, 1), join(2, 1)], False)


def segment(
    directory: Path, number: int, first_seq: int, seqs: list[int], cid: str = CAMPAIGN_ID
) -> None:
    w = writer(directory, segment=number, next_seq=first_seq, campaign_id=cid)
    for seq in seqs:
        w._next_seq = seq  # bypass the writer's own seq guard to forge a bad log
        w.append([join(seq, 1)])
    w.close()


@pytest.mark.parametrize(
    "layout",
    [
        [(1, [1, 2, 4])],  # gap inside a segment
        [(1, [1, 2, 2])],  # repeat
        [(1, [1, 2]), (4, [4])],  # gap across segments
        [(1, [1, 2]), (2, [2])],  # repeat across segments
        [(1, [1, 2]), (3, [4])],  # header first_arrival_seq disagrees with its records
    ],
)
def test_arrival_seq_gap_or_repeat_raises(tmp_path: Path, layout: list[Any]) -> None:
    for number, (first_seq, seqs) in enumerate(layout, start=1):
        segment(tmp_path, number, first_seq, seqs)
    with pytest.raises(CommandLogError):
        read_all(tmp_path)


def test_campaign_mismatch_between_segments_raises(tmp_path: Path) -> None:
    segment(tmp_path, 1, 1, [1])
    segment(tmp_path, 2, 2, [2], cid="0192f3a4-5b6c-7d8e-9f01-000000000000")
    with pytest.raises(CommandLogError, match="continue"):
        read_all(tmp_path)


def write_raw(directory: Path, *records: object) -> None:
    lines = b"".join(json.dumps(r).encode() + b"\n" for r in records)
    segment_path(directory, 1).write_bytes(zstandard.ZstdCompressor().compress(lines))


HEADER = {
    "header": {
        "format_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "first_arrival_seq": 1,
        "protocol_version": "0.2",
    }
}


def test_missing_header_raises(tmp_path: Path) -> None:
    write_raw(tmp_path, join(1, 1).model_dump(mode="json"))
    with pytest.raises(CommandLogError, match="header"):
        read_all(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"extra_field": 1},  # unknown field
        {"kind": "NUKE"},  # unknown kind
        {"arrival_seq": "1"},  # string where an int belongs: no coercion
        {"issuer": {"commander_id": COMMANDER, "display_name": "x"}},  # names never logged
    ],
)
def test_hostile_record_is_rejected(tmp_path: Path, change: dict[str, Any]) -> None:
    write_raw(tmp_path, HEADER, join(1, 1).model_dump(mode="json"))
    assert read_all(tmp_path) == ([join(1, 1)], False)  # the unmodified record is accepted
    write_raw(tmp_path, HEADER, {**join(1, 1).model_dump(mode="json"), **change})
    with pytest.raises(CommandLogError, match="valid command"):
        read_all(tmp_path)


@pytest.mark.parametrize(
    "tombstone",
    [{"tombstone": "5", "reason": "STEP_EXCEPTION"}, {"tombstone": 5, "reason": "OTHER"}],
)
def test_malformed_tombstone_is_rejected(tmp_path: Path, tombstone: dict[str, Any]) -> None:
    write_raw(tmp_path, HEADER, tombstone)
    with pytest.raises(CommandLogError, match="tombstone"):
        read_all(tmp_path)


@pytest.mark.parametrize(
    ("from_seq", "seqs"), [(1, [1, 2, 3, 4, 5]), (3, [1, 2, 3, 4, 5]), (4, [3, 4, 5]), (6, [5])]
)
def test_reader_skips_segments_wholly_before_from_seq(
    tmp_path: Path, from_seq: int, seqs: list[int]
) -> None:
    # Skipped only when the next segment starts below from_seq, so nothing it holds is needed.
    for number, (first_seq, records) in enumerate([(1, [1, 2]), (3, [3, 4]), (5, [5])], start=1):
        segment(tmp_path, number, first_seq, records)
    entries = list(CommandLogReader(tmp_path, from_arrival_seq=from_seq))
    assert [e.arrival_seq for e in entries if not isinstance(e, Tombstone)] == seqs


def test_reader_raises_when_the_log_starts_after_from_seq(tmp_path: Path) -> None:
    segment(tmp_path, 2, 3, [3, 4])
    with pytest.raises(CommandLogError, match="does not cover arrival_seq 2"):
        list(CommandLogReader(tmp_path, from_arrival_seq=2))
    assert len(list(CommandLogReader(tmp_path, from_arrival_seq=3))) == 2


def test_first_frame_larger_than_the_header_read_falls_back_to_a_full_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(command_log, "_FIRST_FRAME_READ", 16)  # smaller than any first frame
    for number, (first_seq, records) in enumerate([(1, [1, 2]), (3, [3, 4]), (5, [5])], start=1):
        segment(tmp_path, number, first_seq, records)
    entries = list(CommandLogReader(tmp_path, from_arrival_seq=4))
    assert [e.arrival_seq for e in entries if not isinstance(e, Tombstone)] == [3, 4, 5]
