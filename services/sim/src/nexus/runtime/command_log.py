"""Write-ahead command log: JSONL in independent zstd frames, one per flush (DATA-MODEL §6.2).

A record is the command exactly as its contract (`model_dump(mode="json")`), so it holds a
commander_id and never a name. The first record of each segment is a header; a tombstone marks
a tick whose commands are dropped on replay (SC-8). Reading is a trust boundary: every record is
validated against the generated `Command` union. The directory must be on a POSIX filesystem
(see `fsutil`).
"""

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import zstandard
from pydantic import TypeAdapter, ValidationError

from nexus.contracts.gen.commands.command import Command
from nexus.runtime.fsutil import fsync_dir

LOG_FORMAT_VERSION = 1
STEP_EXCEPTION = "STEP_EXCEPTION"
_HEADER = "header"
_TOMBSTONE = "tombstone"
_SUFFIX = ".nxl.zst"
# Rotation is at 64 MiB uncompressed (DATA-MODEL §6.2, PROPOSED); twice that per segment leaves
# headroom and still stops a zip bomb of many small frames from exhausting memory or CPU.
_MAX_SEGMENT_DECOMPRESSED = 128 * 1024 * 1024
_MAX_SEGMENT_FILE = 256 * 1024 * 1024  # compressed bytes read into memory per segment
_FRAME_HEADER_MAX = 18  # ZSTD_FRAMEHEADERSIZE_MAX
_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_CHUNK = 64 * 1024  # compressed bytes fed to the decoder per call
_FIRST_FRAME_READ = 64 * 1024  # bytes read to find a segment's header (see _first_seq)
_COMMAND: TypeAdapter[Command] = TypeAdapter(Command)


class CommandLogError(ValueError):
    """A command log that breaks the format, ordering or contract (DATA-MODEL §6.2)."""


@dataclass(frozen=True, slots=True)
class Tombstone:
    tick: int


type LogEntry = Command | Tombstone


def _line(record: dict[str, Any]) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def segment_path(directory: Path, segment: int) -> Path:
    return directory / f"{segment:06d}{_SUFFIX}"


class CommandLogWriter:
    """Appends to `segment`. The caller appends a tick's commands before `step` runs.

    Opening an existing segment walks it: a torn final frame (a crash mid-write) is copied to
    `<segment>.torn-<offset>` as evidence, cut off, and counted in `recovered_torn_bytes` so the
    runtime can alert. The segment must then continue at `next_arrival_seq`.
    """

    def __init__(
        self,
        directory: Path,
        *,
        campaign_id: str,
        protocol_version: str,
        segment: int = 1,
        next_arrival_seq: int,
    ) -> None:
        self._directory = directory
        self._campaign_id = campaign_id
        self._protocol_version = protocol_version
        self._next_seq = next_arrival_seq
        self._compressor = zstandard.ZstdCompressor(write_checksum=True)
        self._buffer: list[bytes] = []
        self.recovered_torn_bytes = 0
        self._open(segment)

    def _open(self, segment: int) -> None:
        self.segment = segment
        path = segment_path(self._directory, segment)
        lines = self._recover(path) if path.exists() else []
        self._file = path.open("ab")
        try:
            if lines:
                self._check_resume(lines, path.name)
            else:
                fsync_dir(self._directory)  # the file may be new
                header = {
                    "format_version": LOG_FORMAT_VERSION,
                    "campaign_id": self._campaign_id,
                    "first_arrival_seq": self._next_seq,
                    "protocol_version": self._protocol_version,
                }
                self._buffer.append(_line({_HEADER: header}))
        except BaseException:
            self._file.close()
            raise

    def _recover(self, path: Path) -> list[bytes]:
        """The lines of every complete frame; a torn tail is saved aside and cut off."""
        data = _read_segment(path)
        lines: list[bytes] = []
        for start, content in _frames(data, path.name):
            if content is None:
                self._cut_torn_tail(path, data, start)
                break
            lines += content.splitlines()
        return lines

    def _cut_torn_tail(self, path: Path, data: bytes, start: int) -> None:
        torn = base = path.with_name(f"{path.name}.torn-{start}")
        n = 0
        while torn.exists():  # never overwrite earlier evidence
            n += 1
            torn = base.with_name(f"{base.name}.{n}")
        with torn.open("xb") as f:
            f.write(data[start:])
            f.flush()
            os.fsync(f.fileno())
        with path.open("r+b") as f:
            f.truncate(start)
            os.fsync(f.fileno())
        fsync_dir(self._directory)
        self.recovered_torn_bytes += len(data) - start

    def _check_resume(self, lines: list[bytes], name: str) -> None:
        header = _segment_header(lines[0], name)
        ours = (self._campaign_id, self._protocol_version)
        if (header["campaign_id"], header["protocol_version"]) != ours:
            raise CommandLogError(f"{name}: header {header!r} does not match {ours}")
        last = header["first_arrival_seq"] - 1
        for raw in lines[1:]:
            entry = _entry(raw, name)
            if not isinstance(entry, Tombstone):
                last = entry.arrival_seq
        if self._next_seq != last + 1:
            raise CommandLogError(f"{name}: next_arrival_seq {self._next_seq} != {last + 1}")

    @property
    def directory(self) -> Path:
        return self._directory

    @property
    def next_arrival_seq(self) -> int:
        return self._next_seq

    def append(self, commands: Iterable[Command]) -> None:
        """Buffer a batch; nothing is buffered unless every arrival_seq is the next in order."""
        batch = list(commands)
        for i, command in enumerate(batch):
            if command.arrival_seq != self._next_seq + i:
                raise ValueError(f"arrival_seq {command.arrival_seq} != {self._next_seq + i}")
        self._buffer += [_line(c.model_dump(mode="json")) for c in batch]
        self._next_seq += len(batch)

    def append_tombstone(self, tick: int) -> None:
        self._buffer.append(_line({_TOMBSTONE: tick, "reason": STEP_EXCEPTION}))

    def flush(self) -> None:
        """Write the buffer as one independent zstd frame and fsync; no-op when empty.

        A failure is fatal: the buffer is dropped and the file closed, because retrying could
        append after a partial frame. The runtime stops and recovers from snapshot plus log.
        """
        if not self._buffer:
            return
        frame = self._compressor.compress(b"".join(self._buffer))
        try:
            self._file.write(frame)
            self._file.flush()
            os.fsync(self._file.fileno())
        except BaseException:
            self._file.close()
            raise
        finally:
            self._buffer = []

    def rotate(self) -> None:
        self.close()
        self._open(self.segment + 1)

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self._file.close()


class CommandLogReader:
    """Streams every entry in segment order. After a full pass, `truncated_tail` says whether the
    last segment ended inside a frame and that frame was dropped (commands may be lost; the
    runtime alerts). Damage anywhere else raises `CommandLogError`.

    With `from_arrival_seq`, leading segments whose successor starts below it are skipped
    unread: every command and tombstone in them was written before that arrival_seq was taken.
    The first segment read must start at or before `from_arrival_seq`, else the log does not
    cover it and reading raises. The segments read are checked in full.
    """

    def __init__(self, directory: Path, from_arrival_seq: int = 1) -> None:
        self._paths = sorted(directory.glob(f"*{_SUFFIX}"))
        self._from = from_arrival_seq
        self.truncated_tail = False

    def _first_needed(self) -> list[Path]:
        # Strictly below: a successor starting exactly at `from` may follow tombstones for ticks
        # after the snapshot that had no commands, in the segment before it.
        start = 0
        while start + 1 < len(self._paths):
            successor = _first_seq(self._paths[start + 1])
            if successor is None or successor >= self._from:
                break
            start += 1
        return self._paths[start:]

    def __iter__(self) -> Iterator[LogEntry]:
        self.truncated_tail = False
        first: dict[str, Any] | None = None
        next_seq = 0
        paths = self._first_needed()
        for i, path in enumerate(paths):
            last = i == len(paths) - 1
            lines = self._lines(path, last=last)
            raw_header = next(lines, None)
            if raw_header is None and last:
                return  # a segment created at rotation whose first flush never landed
            header = _segment_header(raw_header or b"", path.name)
            if first is None and header["first_arrival_seq"] > self._from:
                raise CommandLogError(f"{path.name}: log does not cover arrival_seq {self._from}")
            first = first or header
            next_seq = next_seq or header["first_arrival_seq"]
            if (header["campaign_id"], header["first_arrival_seq"]) != (
                first["campaign_id"],
                next_seq,
            ):
                raise CommandLogError(f"{path.name}: header does not continue the log: {header!r}")
            for raw in lines:
                entry = _entry(raw, path.name)
                if not isinstance(entry, Tombstone):
                    if entry.arrival_seq != next_seq:
                        raise CommandLogError(
                            f"{path.name}: arrival_seq {entry.arrival_seq} != expected {next_seq}"
                        )
                    next_seq += 1
                yield entry

    def _lines(self, path: Path, *, last: bool) -> Iterator[bytes]:
        for _, content in _frames(_read_segment(path), path.name):
            if content is None:
                if not last:
                    raise CommandLogError(f"{path.name}: truncated frame in a non-final segment")
                self.truncated_tail = True
                return
            yield from content.splitlines()


def _read_segment(path: Path) -> bytes:
    if path.stat().st_size > _MAX_SEGMENT_FILE:
        raise CommandLogError(f"{path.name}: segment file over {_MAX_SEGMENT_FILE} bytes")
    return path.read_bytes()


def _first_seq(path: Path) -> int | None:
    """The segment header's first_arrival_seq; None when no complete frame has landed."""
    with path.open("rb") as f:
        head = f.read(_FIRST_FRAME_READ)
    first = next(_frames(head, path.name), None)
    # The first frame (header plus one flush) almost always fits; if not, read the whole file.
    if first is not None and first[1] is None and len(head) == _FIRST_FRAME_READ:
        first = next(_frames(_read_segment(path), path.name), None)
    if first is None or first[1] is None:
        return None
    header = _segment_header(first[1].split(b"\n", 1)[0], path.name)
    return int(header["first_arrival_seq"])


def _frames(data: bytes, name: str) -> Iterator[tuple[int, bytes | None]]:
    """Yield (start offset, content) per frame. The last item is (start, None) when the file
    ends inside that frame (torn); a decode error in a complete frame raises."""
    view = memoryview(data)
    offset = total = 0
    while offset < len(data):
        size = _declared_size(view[offset : offset + _FRAME_HEADER_MAX], name)
        if size is None:
            yield offset, None
            return
        total += size
        if total > _MAX_SEGMENT_DECOMPRESSED:
            raise CommandLogError(f"{name}: over {_MAX_SEGMENT_DECOMPRESSED} decompressed bytes")
        end, content = _decode(view, offset, size, name)
        yield offset, content
        if content is None:
            return
        offset = end


def _declared_size(head: memoryview, name: str) -> int | None:
    """The frame's recorded content size, or None for a header cut off by the end of the file."""
    try:
        size = zstandard.frame_content_size(head)
    except zstandard.ZstdError as e:
        if len(head) < _FRAME_HEADER_MAX and _ZSTD_MAGIC.startswith(bytes(head[:4])):
            return None
        raise CommandLogError(f"{name}: bad zstd frame header") from e
    if size < 0:  # -1 = size not recorded; the writer always records it
        raise CommandLogError(f"{name}: frame without a content size")
    return size


def _decode(view: memoryview, offset: int, size: int, name: str) -> tuple[int, bytes | None]:
    """Decode one frame: (end offset, content), or (end of data, None) if the data runs out."""
    decoder = zstandard.ZstdDecompressor().decompressobj()
    out: list[bytes] = []
    produced, pos = 0, offset
    while not decoder.eof:
        if pos >= len(view):
            return pos, None
        chunk = view[pos : pos + _CHUNK]
        try:
            out.append(decoder.decompress(chunk))
        except zstandard.ZstdError as e:
            raise CommandLogError(f"{name}: corrupt zstd frame at {offset}: {e}") from e
        produced += len(out[-1])
        if produced > size:
            raise CommandLogError(f"{name}: frame at {offset} exceeds its content size")
        pos += len(chunk)
    if produced != size:
        raise CommandLogError(f"{name}: frame at {offset} is shorter than its content size")
    return pos - len(decoder.unused_data), b"".join(out)


def _json(raw: bytes, name: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError as e:
        raise CommandLogError(f"{name}: record is not JSON") from e


def _segment_header(raw: bytes, name: str) -> dict[str, Any]:
    record = _json(raw, name) if raw else None
    header = record.get(_HEADER) if isinstance(record, dict) and len(record) == 1 else None
    keys = {"format_version", "campaign_id", "first_arrival_seq", "protocol_version"}
    if not isinstance(header, dict) or set(header) != keys:
        raise CommandLogError(f"{name}: first record must be a segment header")
    version, seq = header["format_version"], header["first_arrival_seq"]
    if type(version) is not int or version != LOG_FORMAT_VERSION:
        raise CommandLogError(f"{name}: unsupported format_version {version!r}")
    strings = isinstance(header["campaign_id"], str) and isinstance(header["protocol_version"], str)
    if not strings or type(seq) is not int or seq < 1:
        raise CommandLogError(f"{name}: bad segment header {header!r}")
    return header


def _entry(raw: bytes, name: str) -> LogEntry:
    record = _json(raw, name)
    if isinstance(record, dict) and _TOMBSTONE in record:
        tick = record[_TOMBSTONE]
        if record != {_TOMBSTONE: tick, "reason": STEP_EXCEPTION} or type(tick) is not int:
            raise CommandLogError(f"{name}: bad tombstone {record!r}")
        return Tombstone(tick)
    try:  # strict: no "5" -> 5 coercion of hostile input
        return _COMMAND.validate_json(raw, strict=True)
    except ValidationError as e:
        raise CommandLogError(f"{name}: record is not a valid command: {e}") from e
