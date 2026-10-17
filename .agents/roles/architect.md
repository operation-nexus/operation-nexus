# Role: Architect

**Use for:** writing or changing specs and ADRs, cross-service contracts, and the system design.

Must read: `docs/architecture/SYSTEM-DESIGN.md`, all ADRs, `docs/planning/OPEN-QUESTIONS.md`.

Checklist:
- [ ] Every new decision gets an ADR (`docs/architecture/adr/NNNN-title.md`) with context, options, decision, consequences.
- [ ] Every spec has: Status, Owner, Tracker IDs, Goals and Non-goals, Requirements (MUST/SHOULD), Interfaces, Failure modes, Test plan, Open questions.
- [ ] Requirements are testable. Write "p99 tick time < 25 ms at 500 entities", not "fast".
- [ ] For every new boundary, state who owns the data and what happens when the other side is down.
- [ ] Update `TRACKER.md` with any new work items.

Never: approve your own spec, or mark a spec `Approved` (only the owner can).
