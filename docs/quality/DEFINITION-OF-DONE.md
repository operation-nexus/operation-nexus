# Definition of Done

A tracker item is **Done** only when all of these are true.

## Every item
- [ ] Linked to a tracker ID and spec section. The spec is updated if behavior was clarified.
- [ ] Acceptance criteria from the tracker are each proven by a named test.
- [ ] `make check` passes locally; CI `ci-gate` is green. On `develop`, `ci-gate` blocks on build, lint, format, typecheck and import contracts; tests are advisory there, and a red advisory test gets a tracker issue within 24 h (ADR-0009, Q-CI-6).
- [ ] No new high or critical findings from CodeQL, Semgrep, SCA, trivy, or gitleaks.
- [ ] Self-review done with `.agents/roles/reviewer.md`. A human or reviewer-agent pass is recorded in the PR.
- [ ] No fabricated, placeholder, or unregistered fallback data (DATA-INTEGRITY.md)
- [ ] No TODOs without a tracker ID (`# TODO(NX-123): ...`).
- [ ] If a contract changed: the `contracts/README.md` checklist is done (schema, union and enum, `VERSION` bump, `make contracts` output committed, validation test, CONTRACTS row).
- [ ] Docs updated (README/runbook/spec/ADR as relevant). CHANGELOG fragment added.
- [ ] Tracker status updated.

## Additionally, for sim-core changes
- [ ] Property test for every new invariant.
- [ ] Golden replays pass, or are regenerated with a justification.
- [ ] Tick-time benchmark is within budget.
- [ ] Balance values live in config, not literals.

## Additionally, for anything user-visible (overlay, TTS, chat replies)
- [ ] User-provided text passes moderation and is length-capped.
- [ ] Readable at 720p and 9:16 crop. Colorblind check passed.

## Additionally, for integrations and infra
- [ ] Failure mode documented: what the stream shows when this dependency is down.
- [ ] Metrics and logs added for the new path. Alert added if it can break the stream.
- [ ] Rollback steps in the runbook.
