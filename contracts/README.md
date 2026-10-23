# contracts/

JSON Schema (draft 2020-12) is the **single source of truth** for wire types: commands, events, wire messages and
admin API (docs/specs/CONTRACTS.md, ADR-0004). Never hand-write a type that crosses a module or process boundary
(AGENTS.md rule 6).

Layout: `common/` (ids, enums, envelope), `commands/`, `events/`, `wire/`, `admin/`, `config/` (config file
schemas, CONFIG-AND-CONTENT CFG-1: `x-unit` and `x-hot-reload` annotate each key, plus the registry fields `x-category`,
`x-audience`, `x-edit-role`, `x-tune`, `x-source` and `x-status` per CFG-5); `VERSION` holds
`PROTOCOL_VERSION`.

## Changing a contract (checklist)

A schema lands in the same PR as the code that produces or handles it (AGENTS.md rule 6a, Q-CT-6). For each change:

1. **Edit or add the schema.** Follow CONTRACTS §3: `additionalProperties: false`, `snake_case` fields,
   `UPPER_SNAKE` enum values, a `const` `kind` (commands, events) or `type` (wire) discriminator, a `maxLength` on
   every string, `$ref` into `common/ids.json` and `common/enums.json` instead of repeating a definition.
2. **Wire it in.** A new command joins `commands/command.json` `oneOf` and the `CommandKind` enum; a new event joins
   `events/event.json` `oneOf` and `EventKind`. An enum only gets the values the code handles; a new enum goes in
   `common/enums.json` with its first user.
3. **Bump `VERSION`.** While it is `0.x`, every change bumps MINOR (Q-CT-8). From `1.0`: MINOR for additive
   changes, MAJOR for anything breaking (CONTRACTS §3.6).
4. **Regenerate:** `make contracts`. It writes Python types to `services/sim/src/nexus/contracts/gen/` (every
   schema) and TS types to `apps/overlay/src/contracts/` (wire messages and the event union). It also runs
   `scripts/gen_config_reference.py`, which fails on a config key with missing or invalid registry fields and
   writes `docs/specs/CONFIG-REFERENCE.md`. Commit the output; never edit it by hand. CI fails on drift.
5. **Test it.** A validation test for the new type in `services/sim/tests/test_contracts.py` (accept a good
   payload, reject an unknown field or an out-of-range value), plus the handler's own tests.
6. **Update the spec.** The CONTRACTS table row is the human-readable twin of the schema; change both together.

`scripts/check_contracts_compat.py` reports breaking changes against the PR base in CI (report-only before `1.0`).
Kernel code builds events with `model_construct` (no re-validation); validate at the boundaries and in tests
(Q-CT-7).
