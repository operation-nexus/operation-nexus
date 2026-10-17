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
