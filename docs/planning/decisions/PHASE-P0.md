# Phase gate: P0 Foundations

Status: **GO to P1 (owner, 2026-10-20)** · Date: 2026-10-20 · ROADMAP "Milestone gates" · Scope: `main` (df56a6e) → `develop` plus the open docs PRs #140–#144

## 1. Exit criteria (ROADMAP P0)
| Criterion | State | Evidence |
|---|---|---|
| All P0-blocking questions answered | Met | 0 of 20 `P0` rows in OPEN-QUESTIONS open |
| ADRs 0001–0008 accepted or amended | Met | Each ADR's Status line: Accepted (owner, 2026-10-17); ADR-0006 amended |
| CI green on a hello-world sim and overlay | Met | `ci-gate` green on #137–#139; `make check` green in a fresh cloud session (NX-025) |
| Branch protection and security scanning live | Met | `develop` ruleset: pull request, required status checks, code scanning, no deletion, no force push; `security.yml` runs gitleaks, CodeQL, dependency-review, osv-scanner, zizmor, trivy and hadolint |
| Specs SIM-CORE, GAMEPLAY, FOG-OF-WAR, THREAT-DIRECTOR Approved (NX-006) | Met once #144 merges | NX-345 reference run 2026-10-20; verdict objects behind the `World` API |

## 2. Gate items
1. **Demo:** owner to record (§5).
2. **Security review of the phase diff:** §3.
3. **Retro:** §4.
4. **Go/no-go:** §6.

## 3. Security review
Read-only review of `main..develop` excluding docs and generated code, against THREAT-MODEL and CICD-ARCHITECTURE: CI workflows, CODEOWNERS, Dependabot, agent hooks, Makefile, repo-check scripts, the Discord setup tool, the bench script, the public site and the contract schemas. NX-025's CI change and NX-021's CI change also had their own reviews (no findings).

**Verdict: no critical or high findings.** One medium, six low. Checked and fine: no `pull_request_target` or `workflow_run`; `permissions: {}` at the top of every workflow and least privilege per job; every action pinned by SHA (enforced by the repo); downloaded scanners checked by SHA-256; `persist-credentials: false` everywhere; PR-controlled text reaches `run:` only through `env:`; `ci-gate` fails on anything but success or skip; the session hook runs only in cloud sessions with frozen lockfiles; the Discord tool reads its token from the environment, never logs it, defaults to dry-run and never deletes; the site has no scripts or off-site resources; contract schemas are closed (`additionalProperties: false`) and length-capped.

| ID | Severity | Finding | Proposed handling |
|---|---|---|---|
| M1 | Medium | `ci-gate` is required by name from any GitHub Actions job, and the `develop` ruleset requires no approvals and no code-owner review (verified with `gh api`), so a PR can edit `ci.yml`, or add a workflow with a job named `ci-gate`, and pass its own gate. CODEOWNERS' "changes require owner review" isn't enforced. The agent commits as the code-owner account, so turning on code-owner review would block its PRs to `.github/` until another account approves | Owner decision Q-PH0-3 |
| L1 | Low | License exceptions in `security.yml` aren't pinned to a version, so a later version with another license passes | P1 hardening PR: add `@version` to each purl |
| L2 | Low | The site check doesn't run as a required step on an `apps/site`-only PR (Pages re-checks before deploy, so nothing bad ships) | P1 hardening PR |
| L3 | Low | `content/**` is in no CI path filter; harmless until a loader exists | With the content loader |
| L4 | Low | `tools/discord-setup` sets `Authorization` on a `urllib` request; a redirect off discord.com would carry the token (theoretical: fixed https base, allow-listed paths) | P1 hardening PR: refuse redirects |
| L5 | Low | Integer ids have no maximum; above 2^53 the TS overlay loses precision | P1 hardening PR: `maximum: 9007199254740991` (contract change, VERSION bump) |
| L6 | Low | The project enables the third-party `ponytail` plugin from a marketplace without a pinned ref; its hooks run in every agent session (predates P0) | Owner decision Q-PH0-3 |

## 4. Retro
P0 ran 2026-10-17 → 2026-10-20: 97 PRs merged into `develop`, 165 commits since the last promotion to `main`.

**Went well**
- `/grill-with-docs` before each spec turned decisions into Q-rows and spec text in the same pass; four core specs reached Approved.
- An independent reviewer agent on each docs PR caught real contradictions every time (e.g. the wreck timeout would have deleted facilities; the band check would have stopped air-to-ground fire).
- Determinism showed up early: the NX-345 harness produced byte-identical frame streams on a Mac and on the reference host.
- A fresh cloud session reaches a green `make check` with no manual steps (NX-025).

**Went badly**
- An AI co-author trailer failed CI on PR #108 and needed a force-push. Now a saved rule for agents; CI enforces it.
- Moving the repo folder broke the virtualenv and agent tooling paths.
- A tracker ID was issued twice (NX-345), fixed by renumbering (PR #133).
- Decisions didn't reach config: Q-LEGAL-10 approved PSF-2.0 but the license allowlist was never updated, which blocked #138 later.
- The contracts generator wrote a temp path into its headers, so CI drift failed on the first run.
- A merge conflict on #139 went unnoticed until the owner saw it, because no PR was being watched.
- Merges queue on the owner: five stacked docs PRs (#140–#144) waiting at the end of P0.

**Changes (actions)**
- Every PR an agent opens gets the CI watch at once (done: saved rule).
- NX-322 docs lint (decided Q-IDs still described as open) moves into P1 to catch decision drift; a decided license or config value lands in the same PR as its decision.
- Owner decision: let agent PRs into `develop` merge by auto-merge once `ci-gate` is green, as AGENTS.md rule 10 and ADR-0009 describe, so they don't queue. The repo already allows auto-merge; today the agent's account can't turn it on for a PR, so the owner merges by hand (§6 Q-PH0-2).
- Prefer smaller, independent PRs over long stacks where files allow.

## 5. Demo (owner records)
Suggested 3–5 minute capture for the devlog:
1. A fresh clone and `make bootstrap check` going green.
2. A PR going through `ci-gate`: pr-hygiene, the contract drift check, the security scans.
3. `make contracts` regenerating Python and TypeScript types from one schema.
4. The NX-345 benchmark on the reference host and the "identical bytes on two machines" result.
5. The theater #1 sketch (`docs/design/theater-1.svg`) and the COMBAT and command-catalog specs.

## 6. Decision
**Recommendation: GO to P1.** The exit criteria are met; the open P0 rows are ops and tooling that either need a deploy target (P2) or the first kernel code (P1). Proposed carry-over, for the owner to confirm (Q-PH0-1):

| Item | Proposed phase | Why |
|---|---|---|
| NX-016 nightly skeleton, NX-020 and NX-046 Semgrep rules, NX-024 and NX-322 docs lint, NX-026 logging with redaction, NX-029 agent review gate, NX-045 graph-MCP spike | P1 | Need or protect the first kernel code; nightly hosts the balance and soak runs |
| NX-013 build, NX-014 deploy, NX-015 release, NX-027 secret rotation, NX-007 hardware doc | P2 | Need a deploy target; the alpha is the first deploy |
| NX-030 Playwright part | P2 | Waits for the first overlay visual test |
| NX-047 SonarQube (optional) | P2 | Already marked P2 |
| Security hardening L1, L2, L4, L5 (§3) | P1 | One small PR; no owner decision needed |
| NX-004 context files, NX-044 desktop setup, NX-005 raw-file move | anytime (owner) | Owner tasks, block nothing |

- **Go / no-go:** ✅ GO to P1 (owner, 2026-10-20)
- **Carry-over confirmed (Q-PH0-1):** ✅ as proposed in the table above (owner, 2026-10-20)
- **Auto-merge on `develop` (Q-PH0-2):** ✅ owner 2026-10-20: yes for agent PRs on a green `ci-gate`, except PRs touching CODEOWNERS files
- **M1 and L6 (Q-PH0-3):** ✅ owner 2026-10-20: M1 fixed with code-owner review on the gate files and the owner as bypass actor (Q-DEV-12); L6 pinned to tag v5.3.2 (Q-DEV-13). Previously proposed options: Options for M1: (a) require code-owner review on `/.github/` and `/.claude/`, with a second account approving agent PRs there; (b) block auto-merge for PRs that touch `.github/workflows/**` and keep merging those by hand; (c) accept the risk while the owner merges every PR by hand. Recommended: (b) if auto-merge is turned on (Q-PH0-2), else (c). For L6: pin `ponytail` to a commit.
