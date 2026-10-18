# Review Checklist

Used by human reviewers and by `.agents/roles/reviewer.md`. Skip lines that don't apply. Never skip the security block for the listed paths.

## Correctness
- Does the change do what the spec section says, and only that?
- Edge cases: empty collections, zero viewers, 1,000 viewers, a unit destroyed mid-command, node captured mid-delivery, campaign ending mid-sortie.
- Sim: any wall-clock time, unseeded randomness, unordered iteration, or float accumulation order dependence?
- Concurrency: shared mutable state across async tasks? Await inside a critical section?
- Errors: are failures handled at the boundary with a user-visible outcome, not swallowed (`except Exception: pass`)?

## Data integrity (mandatory, see DATA-INTEGRITY.md)
- Is any value invented, guessed, padded, or a placeholder? Is missing data shown as missing?
- Does any `except`, `.get(k, default)`, `getenv(k, default)`, or `?? default` hide a failure? If so, is it in the FB registry, logged, and visible?
- Do fixtures or mock data stay inside `tests/`? Are NPCs labeled as AI?
- Are numbers in docs sourced, or labeled proposed/estimate?

## Security (mandatory for gateway, identity, llm, tts, api, deploy, .github)
- All external strings validated, normalized (NFKC), length-capped, moderated before display/TTS/prompt/log.
- No string-built SQL, shell, or HTML. Parameterized queries only.
- AuthZ: does this endpoint or command check *who* is acting and whether they're allowed to?
- Secrets: none in code, logs, error messages, or URLs.
- LLM: output validated against schema and ranges, and treated as a suggestion. Prompt contains no secrets. Cost/timeout cap present.
- CI: actions SHA-pinned, minimal `permissions`, no untrusted input in `run:` via `${{ }}` interpolation.

## Design and maintainability
- Respects module boundaries in SYSTEM-DESIGN §4 (e.g., overlay has no game logic; sim-core has no I/O).
- Is there a simpler way? Is any new abstraction justified by a second use?
- New dependency justified (license, maintenance, size).
- Names match the glossary (`docs/planning/GLOSSARY.md`) and the case style in `docs/planning/NAMING-CONVENTIONS.md`.

## Tests
- Would these tests fail if the feature were broken? (Mentally delete the implementation.)
- No sleeps or timing-dependent assertions. Fake clocks are used.
- Property and golden tests present for sim changes.

## Ops
- Metrics/logs for the new path. Alert if it can take the stream down.
- Config has a safe default. Feature flag if risky.
