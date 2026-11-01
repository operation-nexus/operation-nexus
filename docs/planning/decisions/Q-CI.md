# Decided questions: Q-CI

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## CI/CD & repo

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-CI-1 | Is the repo public or private? (This affects runner security, CodeQL cost, and secret exposure.) | **Stay public.** On a free account, the following are free on public repos only: CodeQL, secret scanning and push protection, the dependency-review action, private vulnerability reporting, unlimited Actions minutes, and (critically) **rulesets/branch protection and environment required reviewers**. Private repos on the Free plan don't get rulesets or required reviewers at all. Sources: docs.github.com rulesets and environments pages; github.blog 2025-03-04 changelog. | P0 | ✅ 2026-10-17: Owner has no preference. Staying **public** per recommendation. |
| Q-CI-2 | Code license? | Keep the existing MIT for code. Assets (art, audio, voices) are licensed separately. | ✅ 2026-10-17: Code stays MIT; assets licensed separately (A) |
| Q-CI-3 | As a solo dev, who approves PRs? | No required PR approval count (GitHub ignores self-approval, so it would deadlock). An AI reviewer (code-review + security-review) posts a review comment. Only you can merge to `main`, and production deploys need your approval in the `production` Environment (CICD §2). | ✅ 2026-10-17: AI review comment on every PR; owner-only merge to main; production deploy needs owner approval (A) |
| Q-CI-5 | Add SonarQube? | Not yet. SonarQube Cloud is free for public repos [2024 terms; current terms UNVERIFIED]. Its security rules overlap CodeQL + Semgrep, and its extra value (code smells, duplication, coverage gates) matters once there's real code. Revisit at P2 (NX-047). | ✅ 2026-10-17: Deferred by owner; revisit at P2 (NX-047) |
| Q-CI-4 | Dependabot or Renovate? | Dependabot (built-in), grouped weekly. | ✅ 2026-10-17: Dependabot, grouped weekly (A) |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-CI-6 | On `develop`, should lint/format/typecheck failures block merges? ADR-0009 says advisory; the CI build makes them blocking (only tests advisory). | Blocking: they are fast, cheap to fix, and keep `develop` clean; tests stay advisory. Amend ADR-0009 to match. | ✅ 2026-10-18: Lint, format and typecheck are blocking on develop; tests, golden replays, integration and Playwright stay advisory on develop and required on main. ADR-0009 amended to match ci.yml. |
| Q-CI-7 | Which AI reviewer runs on PRs, and does it block? (NX-029, Q-CI-3) | Owner, 2026-10-22: the Claude Code GitHub Action reviews PRs (option B). CodeRabbit ($30 a month after its trial) is over budget for now and is not renewed by default; the owner would like both reviewers when money allows, each run only some of the time to save cost (option C). A review never blocks a merge: it is advice, and `ci-gate` stays the only required check. To save cost the action runs on PRs that touch sensitive paths (chat ingestion, identity, the LLM gateway, CI workflows) and on demand by label, not on every PR, since the lead's build loop already reviews its own PRs. Costs are tracked in docs/ops/COSTS.md. | P0 | ✅ 2026-10-22 (owner) ; amended 2026-10-26 (owner, #383 H1): CodeRabbit becomes a required check on `develop` beside `ci-gate`, so auto-merge waits for its review (lesson L-25); the owner changes branch protection (OWNER-TODO) |
