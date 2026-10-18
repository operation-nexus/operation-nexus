# contracts/

JSON Schema (draft 2020-12) is the **single source of truth** for wire types: commands, events, wire messages and admin API (docs/specs/CONTRACTS.md, ADR-0004).
Pydantic and TypeScript types are generated from here. Generation and the drift check land in NX-021.

Layout: `common/`, `commands/`, `events/`, `wire/`, `admin/`.
