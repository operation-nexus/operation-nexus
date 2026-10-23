# AGENTS.md — Operation Nexus

This is the entry point for every AI coding agent (Claude Code, Codex, Gemini, Antigravity, Cursor, etc.) working in this repository. Humans should read it too.

> **Status: P1 (headless sim kernel).** P0 is closed; `services/sim`, `content/`, `balance/` and `tools/` exist. Code changes go through the `build-loop` skill against specs marked `Status: Approved`. A spec still in Draft needs owner sign-off before code. Open questions are in [`docs/planning/OPEN-QUESTIONS.md`](docs/planning/OPEN-QUESTIONS.md).

## 1. What this project is

Operation Nexus is a 24/7, crowd-controlled, co-op PvE wargame played by live-stream chat (Twitch first, then YouTube; TikTok is deferred). A deterministic, server-authoritative simulation runs the war. A browser overlay renders a C2 "war room" map, and OBS streams it. Viewers type commands to spawn and direct units against an adaptive AI Threat Director.

- Vision and scope: [`docs/planning/VISION.md`](docs/planning/VISION.md)
- System design: [`docs/architecture/SYSTEM-DESIGN.md`](docs/architecture/SYSTEM-DESIGN.md)
- Specs: [`docs/specs/`](docs/specs/)
- Decisions (ADRs): [`docs/architecture/adr/`](docs/architecture/adr/)
- Roadmap: [`docs/planning/ROADMAP.md`](docs/planning/ROADMAP.md)
- Work tracker: [`docs/planning/TRACKER.md`](docs/planning/TRACKER.md)
- Critique of the original plans: [`docs/review/PLAN-CRITIQUE.md`](docs/review/PLAN-CRITIQUE.md)
- Original source material (read-only): [`Raw-plans.md`](Raw-plans.md), [`Raw-conversation.md`](Raw-conversation.md)

The raw files are brainstorms from an AI chat. **They are not specs.** Where they conflict with `docs/`, `docs/` wins. Do not copy the sample code from the raw files; the critique lists its defects.

## 2. Ground rules for agents

0. **NO FABRICATED OR HALLUCINATED DATA. EVER.** This is mandatory and has no exceptions. Don't invent values, names, ids, stats, API fields, file paths, library versions, flags, or facts. When data doesn't exist, say so or leave it empty. Defaults and fallbacks are allowed only when they're required, honest, visible, and listed in the registry. Unverified external facts must be marked **[UNVERIFIED]**. Report only what you actually ran and observed. Full policy: [`docs/quality/DATA-INTEGRITY.md`](docs/quality/DATA-INTEGRITY.md).
1. **Spec first.** Every change traces to a tracker ID (`NX-###`) and a spec section. If no spec covers it, stop and propose a spec change. Don't invent behavior.
2. **Never guess on design decisions.** If a spec is ambiguous, add a question to `OPEN-QUESTIONS.md` and ask the owner. Exception for autonomy (Q-DEV-1): when a question has a recommended option, the lead takes it, records it as a Q-row with status `Decided by lead, owner may veto`, keeps going, and presents the list at the end of the work stretch (Q-DEV-21); real alternatives without a recommendation, and costs, legal or security questions, still go to the owner (`.claude/skills/build-loop` §3).
3. **The simulation is deterministic.** Inside `sim-core`, don't use wall-clock time, unseeded randomness, `uuid4`, set/dict iteration over unordered data, floating-point reductions in nondeterministic order, threads, or network I/O. See [`docs/specs/SIM-CORE.md`](docs/specs/SIM-CORE.md).
4. **Chat input is hostile.** Every string from a platform, a URL, or an LLM is untrusted. It is validated, length-capped, normalized, and moderated before it reaches the sim, the screen, TTS, logs or a prompt. See [`docs/security/THREAT-MODEL.md`](docs/security/THREAT-MODEL.md).
5. **LLMs advise; code decides.** LLM output is always parsed into a typed schema, range-checked, and treated as a *suggestion* that deterministic code can reject. An LLM is never on the hot path of a tick.
6. **Contracts are generated, not hand-copied.** Wire types (WebSocket frames, commands, events) come from a single schema source. CI fails if generated types drift.
6a. **No command exists in only one place.** A chat command is its `contracts/commands/` schema, its parser entry and its sim handler, added or removed in the same PR. An LLM prompt (LLM-ADVISORS) lists only commands and enum values the code handles; drop one from the prompt in the commit that deletes its handler, never before or after. A name the parser doesn't know does nothing.
7. **Small PRs.** One tracker item per PR where possible, under ~400 changed lines of non-test, non-generated source. Tests, regenerated goldens and `make contracts` output don't count; state the split in the PR body. Each PR includes tests and updates the docs it affects.
8. **No new dependencies without justification.** Each one goes in the PR description (why, license, maintenance status, alternatives). Licenses must be compatible with the project license (see OPEN-QUESTIONS Q-LEGAL-1).
9. **No secrets in the repo.** Ever. Use `.env` (gitignored) locally and GitHub Environments / a secret manager in CI/CD.
10. **Push, open PRs and merge only inside the owner-granted workflow** (Q-PROC-1, Q-PROC-2, ADR-0009). When the owner has asked you in the current session to work on something, you may push a fresh feature branch and open a PR into `develop` after bringing in the latest `develop`. That PR merges through GitHub auto-merge once `ci-gate` is green: no approval is needed, and direct pushes to `develop` are blocked. If the owner limits the ask (for example "push, but no PRs"), the limit wins. Without such an ask, don't push or open PRs. Never push to or merge into `main`, never deploy, and never bypass, disable or weaken a required check to get a PR merged. Promotion, hotfix and release merges to `main` are owner-only. Because PRs auto-merge, open anything that must not land (experiments, seeded-failure tests) as a **draft** PR.
10a. **No vendor lock-in.** Vendor SDKs (chat platforms, LLM, TTS, Discord) are imported only inside adapter packages, behind our own interfaces. Adapters must pass the shared conformance suite. See ADR-0010.
11. **Branches:** branch from and target `develop`. Target `main` only with a promotion or hotfix PR the owner asked for; only the owner merges it (rule 10). See ADR-0009. Delete the feature branch (local and remote) once its PR is merged into `develop`; don't reuse a merged branch.
11b. **One writer per file.** Work in parallel (separate sessions, worktrees or subagents) only when no two pieces can touch the same file; when in doubt, work sequentially. Before a parallel piece starts, check which files it will change and which files other open branches or sessions are changing; any overlap means one of them waits. Files that many tasks update (trackers, indexes, decision logs, checklists, changelogs, shared config, CI workflows, this file) are changed by one session at a time: a parallel session leaves them alone and lists the edits it needs in its PR description, and the coordinating session applies them in one follow-up PR. Merge the latest `develop` into your branch right before opening the PR.
11a. **Devlog checkpoints.** When you finish a tracker item labeled `devlog-moment`, end your report with a **DEVLOG CHECKPOINT** block: what to capture, 3–5 talking-point suggestions, and a title idea (docs/planning/MARKETING.md).
12. **Commit messages:** Conventional Commits (`feat(sim): ...`, `fix(gateway): ...`, `docs: ...`). Don't add AI co-author trailers or self-references in commits or docs.

## 3. Repository layout (target)

The layout below is the target. Directories are created when their first tracker item starts, not before.

```
.
├── AGENTS.md                 # you are here
├── CLAUDE.md                 # pointer to AGENTS.md for Claude Code
├── .agents/                  # agent roles, reusable prompts, context drops
├── .github/                  # workflows, templates, CODEOWNERS, dependabot
├── docs/
│   ├── planning/             # vision, roadmap, tracker, open questions, glossary
│   ├── architecture/         # system design + ADRs
│   ├── specs/                # one spec per subsystem
│   ├── security/             # threat model, security requirements
│   ├── cicd/                 # pipeline architecture, release, environments
│   ├── quality/              # testing strategy, definition of done, review checklist
│   └── review/               # critiques and review reports
├── contracts/                # JSON Schema / protobuf source of truth for wire types
├── services/
│   ├── sim/                  # Python: deterministic sim core + API/WS (modular monolith)
│   └── gateway/              # Python: platform chat adapters -> normalized commands
├── apps/
│   ├── overlay/              # TypeScript: broadcast overlay (Canvas2D first, ADR-0005)
│   ├── site/                 # Public site: replays, leaderboards, stats (no admin features)
│   └── command-center/       # Private admin console (Q-ARCH-7; tailnet + Discord only)
├── tools/                    # chat simulator, replay CLI, balance harness, load bots
├── scripts/                  # repo hygiene checks (commit message, tracked files) + their tests
├── deploy/                   # docker compose, host provisioning, runbooks
└── tests/                    # cross-service e2e / soak tests
```

## 4. Toolchain (proposed; see ADR-0004)

| Area | Tool |
|---|---|
| Python | 3.12+, `uv` (deps + lockfile), `ruff` (lint + format), `mypy --strict`, `pytest`, `hypothesis` |
| TypeScript | Node LTS, `pnpm`, Vite, TypeScript `strict`, ESLint + Prettier (or Biome), Vitest, Playwright |
| Contracts | JSON Schema → generated Pydantic + TS types |
| Containers | Docker, Compose v2 |
| CI | GitHub Actions (see [`docs/cicd/CICD-ARCHITECTURE.md`](docs/cicd/CICD-ARCHITECTURE.md)) |

## 5. Commands

```
make bootstrap      # (fresh clone: `make bootstrap check`; cloud sessions bootstrap via SessionStart hook)
                    # uv sync + pnpm install (frozen lockfiles) + pre-commit hooks if installed
make contracts      # regenerate Python + TS types from contracts/ (CI fails on drift; NX-021)
make check          # Python: ruff + ruff format --check (services/sim and tools/), mypy --strict (src, tests,
                    #   maintained tools: TOOLS_TYPED in the Makefile), import-linter, pytest,
                    #   repo-check script tests (scripts/tests)
                    # Overlay: tsc --noEmit, eslint + prettier --check, vitest
# make sim          # (NX-031/NX-193) not yet implemented
# make dev          # (NX-255) not yet implemented
```

Requires: `uv`, Node 22 (`.node-version`; `make` checks it) with `pnpm`, `make`. Python 3.12 comes from `services/sim/.python-version` via uv.

CI (`.github/workflows/ci.yml`) runs the same commands, plus `pnpm run build`. `ci-gate` is the single required check.

## 6. Definition of Done

See [`docs/quality/DEFINITION-OF-DONE.md`](docs/quality/DEFINITION-OF-DONE.md). In short: spec referenced, tests written (including a determinism test for sim changes), CI green, docs updated, no new high or critical security findings, tracker updated.

## 7. Agent roles

Role cards live in [`.agents/roles/`](.agents/roles/). Pick the one that matches your task and follow it. Owner-provided context files go in [`.agents/context/`](.agents/context/).

Every agent also follows [`.agents/rules/code-quality.md`](.agents/rules/code-quality.md) in new or touched files and adds to its "Lessons learned here" section when this repo teaches something new. Skills live in [`.claude/skills/`](.claude/skills/) ([index](.claude/skills/VENDORED.md)); agents other than Claude read them by path. `build-loop` for any code change (coder → QA → lead review → PR or owner), `coding-safeguards` before multi-file edits, `frontend-design` before any new visual surface, `grill-with-docs` to stress-test a plan or spec with the owner before implementation (it records answers in OPEN-QUESTIONS, the glossary, specs and ADRs).
