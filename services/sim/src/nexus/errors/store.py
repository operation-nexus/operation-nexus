"""Local fingerprint store (ERROR-PIPELINE EP-8): one SQLite file, one row per fingerprint.

Written only when an error is captured. Bounded like captures (EP-3): a short busy timeout, a
sample of allowlisted fields (at most `MAX_FRAMES` frames) and at most `MAX_FINGERPRINTS` rows. A
write failure (disk full, locked, unwritable path) is logged by exception type and never raised
into the caller; the capture is lost and the log line says so. The issue sync (EP-9) reads and
marks rows here and touches nothing else.
"""

import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_log = logging.getLogger("nexus.errors")
MAX_FINGERPRINTS = 1000  # bounds the file and the flood issue body; far above real distinct bugs
BUSY_TIMEOUT_S = 0.25  # a locked file may block the crash path this long, no longer

_SCHEMA = """
CREATE TABLE IF NOT EXISTS errors (
  fp TEXT PRIMARY KEY, exc_type TEXT NOT NULL, component TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, seen_count INTEGER NOT NULL,
  release TEXT, sample TEXT NOT NULL,
  issue_number INTEGER, synced_count INTEGER NOT NULL DEFAULT 0, synced_at TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass(frozen=True)
class Entry:
    fp: str
    exc_type: str
    component: str
    first_seen: datetime
    last_seen: datetime
    seen_count: int
    release: str | None
    sample: dict[str, object]
    issue_number: int | None
    synced_count: int
    synced_at: datetime | None


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=BUSY_TIMEOUT_S)
        try:
            db.executescript(_SCHEMA)
        except BaseException:
            db.close()
            raise
        return db

    def record(
        self,
        fp: str,
        *,
        exc_type: str,
        component: str,
        sample: dict[str, object],
        release: str | None,
        now: datetime,
    ) -> None:
        """Count one capture. Never raises."""
        stamp = now.isoformat()
        try:
            with closing(self._connect()) as db, db:
                known = db.execute("SELECT 1 FROM errors WHERE fp = ?", (fp,)).fetchone()
                total = db.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
                if known is None and total >= MAX_FINGERPRINTS:
                    _log.warning("error store full, capture lost (%d fingerprints)", total)
                    return
                db.execute(
                    "INSERT INTO errors (fp, exc_type, component, first_seen, last_seen,"
                    " seen_count, release, sample) VALUES (?, ?, ?, ?, ?, 1, ?, ?)"
                    " ON CONFLICT(fp) DO UPDATE SET last_seen = excluded.last_seen,"
                    " seen_count = seen_count + 1, release = excluded.release,"
                    " sample = excluded.sample",
                    (fp, exc_type, component, stamp, stamp, release, json.dumps(sample)),
                )
        except (sqlite3.Error, OSError) as failure:
            _log.warning("error store write failed, capture lost: %s", type(failure).__name__)

    def pending(self) -> list[Entry]:
        """Fingerprints with captures since their last sync, oldest first (stable order)."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT fp, exc_type, component, first_seen, last_seen, seen_count, release,"
                " sample, issue_number, synced_count, synced_at FROM errors"
                " WHERE seen_count > synced_count ORDER BY first_seen, fp"
            ).fetchall()
        return [
            Entry(
                r[0], r[1], r[2], datetime.fromisoformat(r[3]), datetime.fromisoformat(r[4]),
                r[5], r[6], json.loads(r[7]), r[8], r[9],
                None if r[10] is None else datetime.fromisoformat(r[10]),
            )
            for r in rows
        ]  # fmt: skip

    def mark_synced(self, fp: str, issue_number: int, count: int, now: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE errors SET issue_number = ?, synced_count = ?, synced_at = ? WHERE fp = ?",
                (issue_number, count, now.isoformat(), fp),
            )

    def meta_get(self, key: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def meta_set(self, key: str, value: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
