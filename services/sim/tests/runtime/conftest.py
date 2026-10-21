"""Runtime test fixtures. `__init__.py` here keeps this conftest apart from `tests/conftest.py`
for mypy."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from nexus.runtime.command_log import CommandLogWriter

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
PROTOCOL = "0.2"


@pytest.fixture
def log_writer() -> Iterator[Callable[..., CommandLogWriter]]:
    """Opens command log writers for the test's campaign and closes them afterwards."""
    opened: list[CommandLogWriter] = []

    def make(directory: Path, *, segment: int = 1, next_arrival_seq: int = 1) -> CommandLogWriter:
        writer = CommandLogWriter(
            directory,
            campaign_id=CAMPAIGN_ID,
            protocol_version=PROTOCOL,
            segment=segment,
            next_arrival_seq=next_arrival_seq,
        )
        opened.append(writer)
        return writer

    yield make
    for writer in opened:
        writer.close()  # every tick was flushed, so this only releases the file
