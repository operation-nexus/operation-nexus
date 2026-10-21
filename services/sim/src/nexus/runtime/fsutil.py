"""Durable-write helpers for recovery files (DATA-MODEL §6.1, §6.2).

Data directories must be on a POSIX filesystem (WSL ext4, not /mnt/c): fsync of a directory and
atomic rename are what make a write durable here.
"""

import os
from pathlib import Path


def fsync_dir(directory: Path) -> None:
    """Make a rename, a new file or a truncation in `directory` durable."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
