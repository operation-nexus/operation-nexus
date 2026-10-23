# CI/CD Architecture

Status: Draft · Tracker: NX-010…NX-029 · Related: ADR-0006 (deployment target), THREAT-MODEL §Supply chain

## 1. Goals

1. **Every merge to `main` is releasable.** CI proves it, not humans.
2. **Fast feedback.** PR checks finish in under 8 minutes p50. Only the jobs for changed paths run.
3. **Security is a gate, not a report.** High or critical findings block merge.
4. **Reproducible and traceable.** Every running container maps to a commit, an SBOM, a signature, and a balance-config version.
5. **Safe deploys to a single always-on node.** One-command rollback, and the stream survives a bad deploy (see §7).

Non-goals for now: Kubernetes, Helm, multi-region, canary traffic splitting (ADR-0006).

## 2. Branching and versioning

| Item | Rule |
|---|---|
| Model | **`develop` + `main`** (ADR-0009). Short-lived `feat/*` branches → PR → merge commit into `develop`. A release PR `develop → main` happens only after the full gate passes and staging is healthy. Hotfixes branch from `main` and are merged back to `develop`. |
| Branch names | `feat/NX-123-short`, `fix/NX-…`, `docs/…`, `chore/…` |
| Commits / PR titles | Conventional Commits for every commit and the PR title: merge commits keep each branch commit, and the merge subject is the PR title. A PR-title lint (NX-017) and the commit-msg check enforce this on every PR, owner promotion and back-merge PRs included (e.g. `chore: promote develop to main`, `chore: back-merge main into develop`); a PR title may not start with `Merge `. |
| Versioning | SemVer per deployable (`sim`, `gateway`, `overlay`) via release-please manifest mode. `contracts/` is versioned too, and any breaking change bumps `PROTOCOL_VERSION`. |
| Protection on `develop` | Every change by PR; direct pushes blocked; 0 approvals; `ci-gate` required; GitHub auto-merge lands the PR once `ci-gate` is green (Q-PROC-2). Security, build, lint, format and typecheck are required; tests, golden replays, integration and Playwright are advisory (ADR-0009 table, Q-CI-6). `ci-gate` also needs the `security` job (`security.yml`, NX-012); CodeQL alerts block through the rulesets' code-scanning rule (§9). No force-push. Agents open these PRs only as AGENTS.md rule 10 allows. |
| Protection on `main` | PRs only from `develop` (promotion) or `hotfix/*`. All required status checks (§4), no force-push, conversation resolution. **Required PR approvals: 0.** GitHub doesn't count an author's own approval, and the solo owner authors every PR, so a required approval would deadlock. Owner sign-off is instead enforced by (a) only the owner being able to merge to `main` (ruleset bypass list empty, merge restricted to the owner) and (b) required reviewers on the `production` Environment. Agents never merge to `main` (AGENTS.md rule 10). |
| Merge methods | **Merge commit** everywhere: `feat/*` → `develop` (ADR-0009 amendment, 2026-10-18), `develop` → `main` and `hotfix/*` → `main`, so `main` and `develop` share history and back-merges don't conflict repeatedly. Neither branch requires linear history. |
| Naming | *Promotion PR* = `develop` → `main`. *Release PR* = the release-please PR on `main`. |
| Tags | `sim-v1.4.0` etc. are created only by release-please. |

## 3. Pipeline overview

```
 PR opened/updated
   │
   ├─ pr-hygiene ── title lint · size label · tracker-ID check · changed-paths filter
   │
   ├─ python (paths: services/**, tools/**, scripts/**, contracts/**)
   │     ruff check · ruff format --check · mypy --strict (all run in services/sim only; tools/
   │     is not linted or type-checked yet, a pending owner PR adds it; tools/ tests run through
   │     services/sim pytest, tests/tools/) · pytest (unit + property)
   │     coverage gate (diff coverage ≥ 90%, sim-core total ≥ 85%)
   │
   ├─ typescript (paths: apps/**, contracts/**)
   │     eslint · prettier --check · tsc --noEmit · vitest · build
   │
   ├─ contracts
   │     regenerate Pydantic + TS types → git diff --exit-code (drift = fail)
   │     schema compatibility check vs main (breaking change requires PROTOCOL_VERSION bump)
   │
   ├─ sim-determinism (paths: same filter as python)
   │     golden replays: seed + command log → state hash must equal committed hash
   │     cross-run check: same scenario twice in separate processes → identical hashes
   │     perf smoke: 1,000 entities, p99 tick time under budget (not yet; NX-104)
   │
   ├─ integration (docker compose, ephemeral)
   │     nexus-app (sim+gateway, SQLite) + tts worker + overlay; scripted chat bots; WS contract tests
   │     Playwright: overlay renders, visual snapshot diff, no console errors
   │
   ├─ security (always)
   │     gitleaks (secrets) · dependency-review (new vulns/licenses in diff)
   │     CodeQL (python, javascript-typescript, actions) · semgrep (custom rules, §5)
   │     osv-scanner / pip-audit / pnpm audit (SCA) · zizmor (workflow lint)
   │     trivy config (Dockerfiles, compose) · hadolint
   │
   └─ docs (paths: **/*.md)
         markdownlint · lychee link check · ADR index up to date

 Merge to develop (ADR-0009)
   ├─ all of the above (full, not path-filtered; tests advisory on develop)
   ├─ build: docker buildx (pinned base digests) → push ghcr.io/<owner>/nexus-<svc>:sha-<sha>
   ├─ syft SBOM (SPDX) attached as attestation · trivy image scan (fail on HIGH/CRITICAL fixable)
   ├─ cosign keyless sign (GitHub OIDC) + SLSA provenance (actions/attest-build-provenance)
   └─ deploy → staging (automatic; see §6). Deployed digests are recorded in the staging state file.

 Promotion PR develop → main (merge commit, not squash; see §2)
   ├─ full gate, all checks required
   ├─ release checklist: staging healthy ≥ 24 h on these exact digests, nightly soak green
   └─ on merge: release-please opens or updates the *release PR* on main

 Release PR merged (tag created)
   └─ promote the exact digests that staging verified → production
      (cosign verify; manual approval via the `production` GitHub Environment)

 Nightly (cron)
   ├─ 6h soak: full stack, synthetic chat (diurnal curve incl. 500-viewer raid + troll swarm)
   │     asserts: no memory growth > X%, tick p99 within budget, zero unhandled exceptions,
   │     WS reconnect works, state hash checkpoints replay identically
   ├─ balance harness: standard scenarios × 20 seeds → report artifact + trend
   ├─ full SCA rescan of main + base-image rescan (catches newly disclosed CVEs)
   └─ OpenSSF Scorecard
```

## 4. Required status checks (branch protection)

Per-branch requirements are in ADR-0009. The list below is the full set required for **`main`**.


`pr-hygiene`, `python`, `typescript`, `contracts`, `sim-determinism`, `integration`, `security/gitleaks`, `security/codeql`, `security/dependency-review`, `security/sca`, `security/zizmor`, `docs`.

Path-filtered jobs report success when skipped, so a required check is never left pending. Use a single `ci-gate` job that `needs:` all of them and evaluates their results. That job is the only required check, which prevents "skipped = missing" deadlocks.

## 5. Security tooling (what each actually covers)

The raw plan called `pip-audit` and `npm audit` "SAST". They aren't. They're SCA (known-vulnerable dependencies). The layers are:

| Layer | Tool | Blocks merge? |
|---|---|---|
| Secrets | gitleaks (PR + push protection enabled in repo settings) | Yes, any secret, every branch |
| SAST | CodeQL default + security-extended queries; Semgrep with custom rules | `main`: medium or higher security alerts and error alerts (code-scanning ruleset rule); `develop`: critical only |
| SCA | dependency-review-action (diff), osv-scanner (full) | `main`/`release/*`: high or critical (osv: with a fix); `develop`: critical only |
| License | dependency-review `allow-licenses` list (decided in Q-LEGAL-1) | Yes |
| IaC / containers | trivy config, hadolint, trivy image | `main`/`release/*`: high or critical (hadolint warning+); `develop`: critical (hadolint error) |
| CI itself | zizmor, actions pinned by SHA, `permissions: {}` default | `main`/`release/*`: any zizmor finding; `develop`: high |
| DAST | OWASP ZAP baseline against staging (public site / link portal; also required before any public exposure of the Command Center, Q-RB-4) | Report only until Phase 5 |

Thresholds are tiered by target branch (ADR-0009 amendment 2026-10-18); `security.yml` lists them per tool.
| Supply chain posture | OpenSSF Scorecard, Dependabot/Renovate (grouped, weekly) | Report |

Custom Semgrep rules (repo-specific, under `.semgrep/`):
- `nexus.sim.no-wallclock`: bans `time.time`, `datetime.now`, `random.`, `uuid.uuid4` under `services/sim/core/`.
- `nexus.no-innerhtml`: bans `innerHTML`, `outerHTML`, `insertAdjacentHTML`, and `dangerouslySetInnerHTML` in `apps/`.
- `nexus.sql-no-fstring`: bans f-strings or `%` formatting inside `execute(`.
- `nexus.no-shell-true`: bans `subprocess(..., shell=True)` (relevant for FFmpeg).
- `nexus.llm-output-must-validate`: LLM client results must flow through a `validate_*` function.

## 6. Environments and deployment

| Env | Where | Trigger | Data | Stream target |
|---|---|---|---|---|
| `local` | dev machine, `docker compose` | manual | seeded fixtures | none (overlay in a browser) |
| `ci` | GitHub-hosted runners, ephemeral compose | every PR | fixtures | none |
| `staging` | the **Linux server** (separate machine from prod), its own compose project; a cheap cloud server only as fallback if the server proves too weak (Q-OPS-2, NX-007; ADR-0012) | merge to `develop` | anonymized copy / synthetic | private/unlisted test stream |
| `production` | broadcast host: the Windows gaming PC, app stack in Docker Desktop on WSL2, OBS native (ADR-0012) | release tag + owner tap-approve, auto-rollback (Q-ARCH-15) | real | public channel(s) |

Deployment mechanism (ADR-0006, topology amended by ADR-0012):
1. GitHub Actions job in environment `production` (required reviewer = owner).
2. Authenticates to the host over **Tailscale** (OAuth client in GitHub secrets, ephemeral tagged node). No inbound SSH port is exposed to the internet.
3. Runs `deploy/bin/deploy <service> <digest>` (on the Windows host this runs **inside WSL2**, Q-ARCH-15), which does `cosign verify` → `docker compose pull` → health-gated restart → smoke test → records the deployed digests in `deploy/state/`.
4. On a failed health check, it automatically rolls back to the previous digest. Rollback is also one manual command: `deploy/bin/rollback <service>`.

**Self-hosted runners:** don't attach one to this repo if it is public. If the broadcast PC must build or run GPU jobs, use a pull-based deploy instead (the host polls for signed digests) so CI never gets code-execution rights on the machine that holds stream keys.

## 7. Deploying without dropping the stream

The broadcast must survive deploys of every component:
- **Overlay:** OBS points to a local nginx serving `/current → overlay-vX`. Deploy = atomic symlink swap + overlay hot-reload message over WS. If the WS drops, the overlay auto-reconnects and resyncs from a snapshot.
- **Sim:** snapshot state at tick N (fsync'd) → stop → start new version → load snapshot → resume. Viewers see at most a "COMMS RESYNC" banner for a few seconds. If the snapshot schema changed incompatibly, the deploy is refused unless a migration exists and is tested in CI.
- **Gateway:** in-process with the sim for now (ADR-0001), so it restarts together with the sim. Chat that arrives during the few seconds of restart is dropped on purpose, because stale commands replayed late are worse than lost ones. Once the gateway is split out (SYSTEM-DESIGN §7), commands buffer in Redis Streams with a per-message TTL.
- **OBS / encoder:** never touched by an automated deploy. A separate runbook covers it.

## 8. Secrets

**Decision (Q-ARCH-10):** runtime secrets are a sops+age-encrypted file in the private `operation-nexus-ops` repo, decryptable only by enrolled machines (gaming PC, Linux server, owner laptop, deploy job). The table below lists *where each secret is consumed*.


| Secret | Store | Used by |
|---|---|---|
| Twitch / YouTube client secrets, refresh tokens | GitHub Environment secrets → host `.env` (0600) or sops-encrypted file in `deploy/` | gateway |
| Stream keys | Host only, never in GitHub | OBS |
| LLM API keys | GitHub Environment secrets → host | llm-gateway (Phase 4+) |
| Link-token HMAC key; DB credentials (only once Postgres exists, ADR-0003) | Generated on the host, sops-encrypted backup | sim/api |
| Tailscale OAuth | GitHub Environment secret | deploy job |

Rotation runbook in `deploy/runbooks/rotate-secrets.md` (NX-027). Secrets must never be logged; the logging library (`nexus.obs`, NX-026) has a redaction filter with a test (`services/sim/tests/test_obs.py`).

## 9. Repository settings checklist (owner action)

The repo is **public** (Q-CI-1). Rulesets, environment required reviewers, CodeQL, secret scanning and private vulnerability reporting are all free on public repos only, for a personal Free account.


- [x] Rulesets on `main` and `develop` as in §2 and ADR-0009 (NX-049)
- [x] Secret scanning + push protection ON
- [x] Dependabot alerts + security updates ON
- [x] Private vulnerability reporting ON (`SECURITY.md`)
- [x] Actions: "Allow select actions" + require SHA pinning; default `GITHUB_TOKEN` read-only
- [x] Environments `staging`, `production` created; `production` requires owner approval
- [x] CodeQL default setup OFF (we use the advanced workflow) to avoid duplicate runs
- [x] Rulesets: "Require code scanning results", tool CodeQL (NX-012), tiered per the ADR-0009 amendment of 2026-10-18: `main` security alerts **Medium or higher** + alerts **Errors**; `develop` security alerts **Critical** only. `ci-gate` only shows that CodeQL ran; this rule is what blocks new alerts

Applied 2026-10-18 (OWNER-TODO §2). New third-party actions must be added to the Actions allowlist.

## 10. Workflow file plan

| File | Purpose | Tracker | Status |
|---|---|---|---|
| `.github/workflows/ci.yml` | PR + main checks, `ci-gate` | NX-011 | Implemented |
| `.github/workflows/security.yml` | CodeQL, gitleaks, dependency-review, osv-scanner, zizmor, trivy config, hadolint; called by `ci.yml` | NX-012 | Implemented |
| `.github/workflows/build.yml` | images, SBOM, sign, attest (on merge to `develop`; build check on PRs) | NX-013 | Planned |
| `.github/workflows/deploy.yml` | staging auto from `develop`, prod on release tag with approval | NX-014 | Planned |
| `.github/workflows/release.yml` | release-please | NX-015 | Planned |
| `.github/workflows/nightly.yml` | cron 03:37 UTC + manual; runs on the default branch (`develop`). Today: `determinism` (golden replays, report artifact), `grid-bench` (NX-104, 3,000 ticks, JSON artifact; runner timings indicative only), `rescan` (osv-scanner on `develop`, same pinned binary as `security.yml`; `main` joins once it carries the gate script). Later: soak (NX-033), balance harness (NX-031), base-image rescan (NX-013), Scorecard (needs an owner-approved `ossf/scorecard-action` pin) | NX-016 | Skeleton implemented |
| `.github/workflows/pr-hygiene.yml` | reusable workflow called by `ci.yml` on every PR: Conventional title (no `Merge ...` titles), commit-message lint of every PR commit, tracker-ID check (PRs into `develop` only; Dependabot and back-merges from `main` exempt), size label | NX-017 | Implemented |
| `.github/dependabot.yml` | grouped weekly updates for uv, npm, actions (docker added with the first Dockerfile, NX-013) | NX-018 | Implemented |
| `.github/workflows/claude-review.yml` | Claude Code GitHub Action runs the code-review plugin on PRs into `develop` that touch sensitive paths, or on the `ai-review` label; advice only, never a required check (Q-CI-3, Q-CI-7) | NX-029 | Implemented |
| `.github/workflows/label-sync.yml` | create/update labels from `.github/labels.yml` when it changes on `develop` | NX-018 | Implemented |

`ci.yml` today: `changes` (git-diff path filter on PRs; pushes run everything), `pr-hygiene` (calls `pr-hygiene.yml` on every PR; blocking; `edited` events re-run CI so a fixed title or body clears it), `python` (ruff, ruff format, mypy, import-linter), `python-test` (pytest, plus two stdlib test scripts run from the repo root: `scripts/tests/test_repo_checks.py` and `tools/discord-setup/tests/test_setup.py`), `sim-determinism` (`tools/sim-determinism/check.py`: every golden replay in four processes with different `PYTHONHASHSEED` values, against the committed hashes; NX-105), `overlay` (tsc, eslint + prettier, vite build), `overlay-test` (vitest), `contracts` (`make contracts` then `git diff --exit-code` on the generated types, plus `scripts/check_contracts_compat.py` against the base branch; NX-021), `security` (calls `security.yml`: `gitleaks`, `codeql` per language, `dependency-review` on PRs, `sca` = osv-scanner gated by `scripts/check_osv_report.py`, `zizmor`, `iac` = trivy config + hadolint once a Dockerfile exists; never path-filtered), and `ci-gate`. `ci-gate` is the only required status check. Lint, format, typecheck, import contracts, the build and security always block. Scanners outside GitHub-owned actions run as release binaries pinned by version and SHA-256, so they need no Actions allowlist entry. The three test jobs (`python-test`, `sim-determinism`, `overlay-test`) are advisory when the target is `develop` (`ci-gate` emits a warning) and required for `main`. The `integration` and `docs` jobs arrive with their own tracker items.
