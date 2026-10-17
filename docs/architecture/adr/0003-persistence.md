# ADR-0003: Persistence: in-memory live state, snapshot + command log, SQLite for durable data

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17

## Context
The plans can't decide between "SQLite/PostgreSQL" and "Redis as the state bus", and never say what is authoritative. The sample code opens a new SQLite connection per call, has no WAL, does read-modify-write XP updates (lost updates), and blocks the event loop.

## Decision
- **Live game state** is held in memory by the sim and is authoritative. It's recovered from snapshots (every 30 s) plus an append-only command log (fsync every 1 s).
- **Durable data** (commanders, identities, XP, campaign history) lives in SQLite: WAL mode, `busy_timeout`, `foreign_keys=ON`, one writer connection owned by the persistence module, and atomic `UPDATE … SET xp = xp + ?`. All access happens through a repository interface, and migrations are versioned SQL files applied at startup.
- **No Redis** until there are multiple processes that need a bus.
- Switch to **Postgres** when a second process needs to write: the P3 link portal or the companion site. The repository interface and portable SQL keep that switch mechanical.

## Consequences
- Fewer moving parts. Backups are a file copy (`sqlite3 .backup`) plus snapshots.
- DB writes are off the tick path: events are batched to the writer task.
- The P3 portal may force the Postgres move early. Decide then: the alternative is having the portal call the app's internal API instead of the DB.

## Amendment (2026-10-17): XP and merit are append-only ledgers
- **Change:** the Decision's "atomic `UPDATE … SET xp = xp + ?`" is replaced. XP and merit are recorded as **append-only ledger rows** (`xp_ledger`, `merit_ledger`), inserted idempotently (`INSERT … ON CONFLICT(idempotency_key) DO NOTHING`). The derived `commander_stats` row is updated **in the same transaction**.
- **Source of truth:** the ledger. `commander_stats` can always be rebuilt from the ledgers (DATA-MODEL §5.4), and a weekly check compares them.
- **Why:** a crash and command-log replay can re-emit the same events. With a counter, that double-counts; with idempotent ledger inserts, it can't. The ledger also gives an audit trail for every XP change, and keeps merges (Q-PROG-4) reproducible.
- **Status:** written by the architect during spec reconciliation. Needs owner acknowledgment (Q-ARCH-6).
