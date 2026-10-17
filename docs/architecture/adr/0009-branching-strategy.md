# ADR-0009: Branching strategy: `develop` for integration, `main` for verified releases

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17
- Related: CICD-ARCHITECTURE §2, §4, §6

## Context
The owner wants `main` to contain only verified work: CI passed, CD passed, deployed, and approved. A `develop` branch should take all development work. Some tests or CI jobs may fail on `develop`, but security checks must still run and pass. Release branches are optional.

## Decision
| Branch | Purpose | Merges in from | Protection |
|---|---|---|---|
| `main` | Production. Every commit is a verified release. | `develop` (release PR) and `hotfix/*` only | All required checks green, staging deploy healthy, owner approval, linear history, no force-push. Tags via release-please. |
| `develop` | Integration of all day-to-day work | `feat/*`, `fix/*`, `docs/*`, `chore/*` | PR required. **Gate: security + build** (see below). Tests run but are advisory. No force-push. |
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
| Lint / format / typecheck | Advisory | Required |
| Unit + property tests | Advisory | Required |
| sim-determinism (golden replays) | Advisory | Required |
| Integration + Playwright | Advisory | Required |
| Staging deploy from `develop` HEAD healthy ≥ 24 h, plus soak | — | Required (verified by the release checklist) |
| Owner approval | Optional | Required |

"Advisory" means the check still runs and reports, but doesn't block the merge. A red advisory check on `develop` must get a tracker issue within 24 h (`status:blocked` label on the related item). It's never silently ignored.

### Environments
- **staging** deploys automatically from `develop` after every merge, once the security and build gates pass. It streams to an unlisted test channel.
- **production** deploys from `main` tags with owner approval in the GitHub Environment.

### Bootstrap
The planning PR merges straight into `main`, which the owner allowed while there's no code. After planning is complete, `develop` is created from `main` (NX-049). From then on, all work targets `develop`.

## Consequences
- `main` stays releasable, so rollback means redeploying the previous tag.
- `develop` can carry in-progress work with failing tests, but never a known secret leak or a new high-severity vulnerability.
- More PRs, since releases need a `develop → main` PR. release-please runs on `main`.
