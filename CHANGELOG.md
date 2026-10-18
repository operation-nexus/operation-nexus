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

Planning and repo work on 2026-10-18, on `develop` (PRs #39–#63, the branch merges that created `develop`, and the naming and consistency pass):

- **Repo skeleton (NX-010) and CI (NX-011):** `services/sim`, `apps/overlay`, `contracts/`, `tools/`, `deploy/`, a Makefile with `make check`, pre-commit config, and `.github/workflows/ci.yml` with the `ci-gate` check; repo-hygiene scripts `scripts/check_commit_msg.py` and `scripts/check_tracked_files.py` with tests.
- **Owner decisions:** 37 decisions recorded in OPEN-QUESTIONS (game design, AI and GM scope, UX, progression and seasons, gateway, ops pauses and maintenance, public site hosting, analytics, brand and faction names, art and licensing, legal identity, testing, process and CI), plus the spec-alignment batches Q-ALN-1..21 (#53) and Q-ALN-22..32 (#60). Final gap answers, name clearance round 3 and the develop PR policy arrived in #39.
- **Spec alignment (NX-311):** the specs those decisions touched, one PR per spec (#40–#52), then the Q-ALN batches (#54–#57, #61–#63).
- **ADR amendments:** ADR-0003 database roadmap (Q-ARCH-16); ADR-0009 lint, format and typecheck block on `develop` (Q-CI-6), PRs into `develop` auto-merge on green (Q-PROC-2), and feature PRs merge with a merge commit (#58).
- **Name clearance research:** `docs/review/NAME-CLEARANCE.md`, rounds 1–3 (Q-LEGAL-5, Q-BRAND-6).
- **Tracker:** items NX-315…NX-321 for the decision follow-ups (naming pass, legal pages, lieutenants, asset provenance, art plan, identity migration, playtest reporting).
- **Naming and consistency pass (NX-315, NX-311):** the player faction is now the Quorum in every living doc (Q-BRAND-7); the glossary covers the 2026-10-18 concepts; `docs/planning/NAMING-CONVENTIONS.md` records the case style per layer and the naming conflicts awaiting an owner ruling (NX-323); agent rules, process docs, the ADR index and the docs index match the 2026-10-18 decisions; new tracker items NX-322…NX-326.

### Fixed

- The tracked-files check no longer flags the `nexus.clips` source package as recordings (#59).
