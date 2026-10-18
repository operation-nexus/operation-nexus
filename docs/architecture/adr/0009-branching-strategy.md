# ADR-0009: Branching strategy: `develop` for integration, `main` for verified releases

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17
- Related: CICD-ARCHITECTURE §2, §4, §6

## Context
The owner wants `main` to contain only verified work: CI passed, CD passed, deployed, and approved. A `develop` branch should take all development work. Some tests or CI jobs may fail on `develop`, but security checks must still run and pass. Release branches are optional.

## Decision
| Branch | Purpose | Merges in from | Protection |
|---|---|---|---|
| `main` | Production. Every commit is a verified release. | `develop` (*promotion PR*, merge commit) and `hotfix/*` only | All required checks green, staging deploy healthy, merge restricted to the owner, no force-push. Tags via release-please. |
| `develop` | Integration of all day-to-day work | `feat/*`, `fix/*`, `docs/*`, `chore/*` | PR required. **Gate: security + build + lint/format/typecheck** (see below). Tests run but are advisory. No force-push. |
| `feat/NX-###-…` etc. | One tracker item | branched from `develop` | — |
| `hotfix/…` | Urgent production fix | branched from `main`, merged to `main` **and** back to `develop` | Same as `main` |
| `release/*` | **Not used** for now. Revisit if we ever need to stabilize a release while `develop` moves on. | — | — |

### Required checks by target branch
| Check | → `develop` | → `main` |
|---|---|---|
| gitleaks (secrets) | **Required** | Required |
| CodeQL / Semgrep: no new high or critical | **Required** | Required |
| dependency-review / SCA high or critical | **Required** | Required |
| zizmor (workflow security) | **Required** | Required |
| Build (packages and images build) | **Required** | Required |
| Lint / format / typecheck | **Required** (amended 2026-10-18, Q-CI-6) | Required |
| Unit + property tests | Advisory | Required |
| sim-determinism (golden replays) | Advisory | Required |
| Integration + Playwright | Advisory | Required |
| Staging deploy from `develop` HEAD healthy ≥ 24 h, plus soak | — | Required (verified by the release checklist) |
| Owner sign-off | Optional | Required. Enforced by owner-only merge to `main` plus `production` Environment reviewers. Not by a PR approval count, which a solo author can't satisfy (CICD §2). |

"Advisory" means the check still runs and reports, but doesn't block the merge. A red advisory check on `develop` must get a tracker issue within 24 h (`status:blocked` label on the related item). It's never silently ignored.

### Environments
- **staging** deploys automatically from `develop` after every merge, once the security and build gates pass. It streams to an unlisted test channel.
- **production** deploys from `main` tags with owner approval in the GitHub Environment.

### Bootstrap
The planning PR merges straight into `main`, which the owner allowed while there's no code. After planning is complete, `develop` is created from `main` (NX-049). From then on, all work targets `develop`.

## Consequences
- `main` stays releasable, so rollback means redeploying the previous tag.
- `develop` can carry in-progress work with failing tests, but never a known secret leak or a new high-severity vulnerability.
- More PRs, since releases need a `develop → main` promotion PR (merge commit). release-please then opens its own *release PR* on `main`.
- Feature PRs merge into `develop` with a merge commit, as do promotion and hotfix PRs, so the branches share history (amendment 2026-10-18).

## Amendment (2026-10-18): lint, format and typecheck block on `develop` (Q-CI-6)
- **Change:** lint, format and typecheck move from advisory to **required** on `develop`. Tests, golden replays, integration and Playwright stay advisory on `develop` and required on `main`.
- **Why:** these checks take seconds and are almost always auto-fixable, and a clean `develop` keeps agents on every machine from inheriting errors. This matches the `ci-gate` job in `.github/workflows/ci.yml`.
- **Status:** accepted by the owner, 2026-10-18.

## Amendment (2026-10-18): PRs into `develop` auto-merge on green (Q-PROC-2)
- **Change:** every change reaches `develop` through a PR, but no human approval is needed. The ruleset requires the `ci-gate` check, and PRs use GitHub auto-merge so they land as soon as `ci-gate` is green. Direct pushes to `develop` are blocked.
- **`main`** is unchanged: owner-only merge, all checks required.
- **Branch hygiene:** the feature branch is deleted (local and remote) once its PR is merged (AGENTS.md rule 11).
- **Status:** accepted by the owner, 2026-10-18.

## Amendment (2026-10-18): feature PRs merge into `develop` with a merge commit
- **Change:** feature PRs into `develop` use a **merge commit**, not squash, matching how the 2026-10-18 spec-alignment PRs were merged. The `develop` ruleset does not restrict merge methods.
- **Consequence:** every commit on a feature branch lands in `develop`, so each one must be a Conventional Commit (`scripts/check_commit_msg.py`), not only the PR title. The merge commit's subject is the PR title, ending with `(#N)`.
- **Revisit** (squash only) if `develop` history becomes hard to read or the changelog fills with fixup commits.
- **Status:** accepted by the owner, 2026-10-18.
