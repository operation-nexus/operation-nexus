# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will use [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it has releases. No version has been released yet.

Once release-please is set up (NX-015), it will generate release sections in this file from Conventional Commit messages. Until then, the `Unreleased` section is maintained by hand.

## [Unreleased]

### Added

Planning set, merged to `main` on 2026-10-17 via PRs #33, #34, #35, #36 and #38:

- **Planning docs:** vision, roadmap (phases P0–P5 with exit criteria), work tracker (`NX-###` IDs), open questions and decision log, glossary, owner to-do, marketing plan, and the GitHub Issues workflow (`docs/planning/`).
- **Architecture:** system design and ADRs 0001–0011, all accepted by the owner (`docs/architecture/`):
  modular monolith, deterministic 10 Hz sim kernel, persistence, toolchain, Canvas2D overlay, single-node deployment, LLM role, platform order, branching strategy (`develop`/`main`), platform and provider neutrality, and support redemptions without in-game currency.
- **Specs** (all `Draft`): sim core, gameplay, fog of war, threat director, wire protocol, overlay, chat gateway, identity, progression, audio/TTS, clips and replays, LLM advisors, contracts, data model, config and content, state machines and flows, admin RBAC, support redemptions, and ops/admin (`docs/specs/`).
- **Security and quality:** threat model, CI/CD architecture, testing strategy, definition of done, review checklist, and the mandatory data-integrity policy (`docs/security/`, `docs/cicd/`, `docs/quality/`).
- **Ops research:** hardware notes, local LLM vs API cost analysis, monitoring and watchdog design (`docs/ops/`).
- **Reviews and research:** critique of the original plans, security review of the raw plans, platform reality check, support and scraping research, Epidemic Sound research, Gemini TTS voice research, and the 2026-10-17 gap analysis (`docs/review/`).
- **Agent tooling:** `AGENTS.md`, `CLAUDE.md`, role cards and prompts (`.agents/`), Claude Code subagents and a file-protection hook (`.claude/`), Context7 MCP config (`.mcp.json`), and the tooling and remote-work guides (`docs/agentic/`).
- **GitHub setup:** issue templates (work item, bug, decision), PR template, CODEOWNERS, and a label source file (`.github/labels.yml`).
- **Repo basics:** MIT `LICENSE`, `SECURITY.md`, `.gitignore`.
- **Repo hygiene:** rewritten `README.md`, this `CHANGELOG.md`, a docs index (`docs/README.md`), and an audited `.gitignore`.

### In progress

- Repo skeleton with `make check` (NX-010): open as PR #37 against `develop`, not yet merged.
