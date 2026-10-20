# contracts/

JSON Schema (draft 2020-12) is the **single source of truth** for wire types: commands, events, wire messages and admin API (docs/specs/CONTRACTS.md, ADR-0004).
Pydantic and TypeScript types are generated from here by `make contracts` (NX-021); CI fails if the committed types drift and reports breaking changes against the PR base (`scripts/check_contracts_compat.py`). Add a schema in the same PR as the code that produces or handles it (AGENTS.md rule 6a).

Layout: `common/`, `commands/`, `events/`, `wire/`, `admin/`.
