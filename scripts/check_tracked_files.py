#!/usr/bin/env python3
"""Fail when the git index holds files that should never be tracked.

A .gitignore rule added after a file was committed does not untrack it, so recordings can slip in. Checks every
tracked file (run from anywhere; operates on the repo this script lives in):
  (a) matched by .gitignore            (git ls-files -ci --exclude-standard)
  (b) a clip, recording, capture or database by extension, or under a recordings/captures/data dir, unless allowlisted
  (c) larger than MAX_BYTES, unless allowlisted
Allowlist entries are path prefixes; add one only for a genuine asset, with a reason.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 5 * 1024 * 1024
RECORDING_EXT = (".mp4", ".mkv", ".mov", ".webm", ".flv", ".wav", ".mp3", ".ogg", ".flac", ".pcap", ".pcapng",
                 ".db", ".db-wal", ".db-shm", ".sqlite", ".raw", ".bin")
RECORDING_DIR = re.compile(r"(^|/)(recordings?|captures?|clips|snapshots|command-logs|data)/")

ALLOW_IGNORED: tuple[str, ...] = ()
ALLOW_RECORDING = (
    "docs/ops/data/",  # cost-estimate CSV behind the docs/ops charts
)
ALLOW_LARGE: tuple[str, ...] = ()


def _git(*args):
    out = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def violations(tracked, ignored, size_of):
    """Return (path, reason) pairs. `size_of(path)` returns bytes or None when the file is absent."""
    bad = []
    for p in ignored:
        if not p.startswith(ALLOW_IGNORED):
            bad.append((p, "tracked but matched by .gitignore (git rm --cached it)"))
    for p in tracked:
        if not p.startswith(ALLOW_RECORDING) and (p.lower().endswith(RECORDING_EXT) or RECORDING_DIR.search(p)):
            bad.append((p, "recording/capture/database file is not allowlisted"))
        size = size_of(p)
        if size is not None and size > MAX_BYTES and not p.startswith(ALLOW_LARGE):
            bad.append((p, f"{size / 1048576:.1f} MB exceeds {MAX_BYTES // 1048576} MB"))
    return bad


def _size(path):
    full = os.path.join(ROOT, path)
    return os.path.getsize(full) if os.path.isfile(full) and not os.path.islink(full) else None


def main():
    bad = violations(_git("ls-files", "-z"), _git("ls-files", "-ci", "--exclude-standard", "-z"), _size)
    for path, why in bad:
        print(f"{path}: {why}")
    if bad:
        print(f"{len(bad)} tracked-file violation(s). Untrack with `git rm --cached`, or allowlist a real asset in "
              f"{os.path.basename(__file__)}.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
