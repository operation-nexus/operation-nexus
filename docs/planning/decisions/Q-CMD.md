# Decided questions: Q-CMD

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## NX-312 grilling (2026-10-20): COMBAT, command catalog, balance acceptance

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-CMD-1 | Where commands are listed | New `docs/specs/COMMAND-CATALOG.md` is the one list of every command and intent (syntax, rank, phase, handler); each command maps 1:1 to an intent; `!order` (P4) uses only catalog intents. CONTRACTS §5.2 keeps the wire shapes. | P1 | ✅ 2026-10-20 |
| Q-CMD-2 | `SPAWN_SPECIALIST` | Moves from the live command table to the reserved list. Owner: must not be dropped; NX-212's acceptance names it. | P1 | ✅ 2026-10-20 |
| Q-CMD-3 | Rate-limit class for `!callsign` and `!forget` | CHAT-GATEWAY §5 lists neither. Recommended: `!callsign` gets its own class at 1 per 60 s (it already has a 30-day change limit and a moderation queue); `!forget` 1 per 60 s, since repeats add nothing. | P1 | ✅ 2026-10-20: as recommended |
