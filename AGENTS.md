# AGENTS.md — Operation Nexus

This is the entry point for every AI coding agent (Claude Code, Codex, Gemini, Antigravity, Cursor, etc.) working in this repository. Humans should read it too.

> **Status: PLANNING PHASE.** No production code exists yet. Do not write application code until the owner has answered the blocking questions in [`docs/planning/OPEN-QUESTIONS.md`](docs/planning/OPEN-QUESTIONS.md) and the relevant spec is marked `Status: Approved`.

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
2. **Never guess on design decisions.** If a spec is ambiguous, add a question to `OPEN-QUESTIONS.md` and ask the owner.
3. **The simulation is deterministic.** Inside `sim-core`, don't use wall-clock time, unseeded randomness, `uuid4`, set/dict iteration over unordered data, floating-point reductions in nondeterministic order, threads, or network I/O. See [`docs/specs/SIM-CORE.md`](docs/specs/SIM-CORE.md).
4. **Chat input is hostile.** Every string from a platform, a URL, or an LLM is untrusted. It is validated, length-capped, normalized, and moderated before it reaches the sim, the screen, TTS, logs or a prompt. See [`docs/security/THREAT-MODEL.md`](docs/security/THREAT-MODEL.md).
5. **LLMs advise; code decides.** LLM output is always parsed into a typed schema, range-checked, and treated as a *suggestion* that deterministic code can reject. An LLM is never on the hot path of a tick.
6. **Contracts are generated, not hand-copied.** Wire types (WebSocket frames, commands, events) come from a single schema source. CI fails if generated types drift.
7. **Small PRs.** One tracker item per PR where possible, under ~400 changed lines excluding generated files. Each PR includes tests and updates the docs it affects.
8. **No new dependencies without justification.** Each one goes in the PR description (why, license, maintenance status, alternatives). Licenses must be compatible with the project license (see OPEN-QUESTIONS Q-LEGAL-1).
9. **No secrets in the repo.** Ever. Use `.env` (gitignored) locally and GitHub Environments / a secret manager in CI/CD.
10. **Don't push, merge, deploy, or open PRs** unless the owner explicitly asks in the current session.
10a. **No vendor lock-in.** Vendor SDKs (chat platforms, LLM, TTS, Discord) are imported only inside adapter packages, behind our own interfaces. Adapters must pass the shared conformance suite. See ADR-0010.
11. **Branches:** branch from and target `develop` (once it exists, NX-049). Never target `main` except for release and hotfix PRs. See ADR-0009.
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

## 5. Commands (fill in as they are created)

```
# make bootstrap      # install toolchains & pre-commit hooks
# make check          # lint + typecheck + unit tests for everything
# make sim            # run sim headless with the scripted chat simulator
# make dev            # docker compose up for the full local stack
```

## 6. Definition of Done

See [`docs/quality/DEFINITION-OF-DONE.md`](docs/quality/DEFINITION-OF-DONE.md). In short: spec referenced, tests written (including a determinism test for sim changes), CI green, docs updated, no new high or critical security findings, tracker updated.

## 7. Agent roles

Role cards live in [`.agents/roles/`](.agents/roles/). Pick the one that matches your task and follow it. Owner-provided context files go in [`.agents/context/`](.agents/context/).
