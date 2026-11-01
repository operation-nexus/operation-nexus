# Decided questions: Q-MB

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Foundations grilling (2026-10-19): NX-021, NX-040, NX-019/NX-050

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-MB-1 | What NX-019 enforces | SYSTEM-DESIGN §4 as import-linter `forbidden` contracts (gateway, commands, progression, persistence, advisors must not import core; contracts imports nothing else from nexus; core stays pure); read-only rules by tests and review; a test proves a bad import fails. | P0 | ✅ 2026-10-19 |
| Q-MB-2 | When the vendor rule arrives | With the first vendor SDK (likely NX-191); each SDK joins the list in the PR that adds it. | P0 | ✅ 2026-10-19 |
| Q-MB-3 | NX-050 | Dissolved: each port, `Capabilities` and conformance suite lands with its first adapter (chat in NX-190). | P0 | ✅ 2026-10-19 |
| Q-MB-4 | SYSTEM-DESIGN status | §4 module table Approved; the rest stays Draft pending owner review. | P0 | ✅ 2026-10-19 |
