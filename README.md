# Operation Nexus

**Live-stream chat plays a 24/7 co-op war against an adaptive AI, on a glowing radar war-room map.**

Viewers are **Operators** of **the Quorum** (Q-BRAND-7), defending the network against **the Static**, a glitchy enemy with a taunting mastermind. Type one command in chat and your unit is on screen. Hold supply lines, scout through the fog, and push the frontline over days while the Threat Director adapts to what you do.

The look is **"Signal"**: a radar war room on near-black, with radio static and callsigns (Q-BRAND-1, Q-STYLE-1). The tone is **fun, friendly and playful**, not grim or sweaty. The goal is a welcoming, non-toxic community.

Under the hood: a deterministic, server-authoritative simulation (Python), a browser overlay captured by OBS (TypeScript, Canvas2D), and platform chat adapters (Twitch first, then YouTube; TikTok deferred, ADR-0008). LLMs only advise and narrate; deterministic code decides (ADR-0007).

## Status

**Planning is largely complete; implementation is starting.**

- Done: vision, roadmap, tracker, system design, ADRs 0001–0011 (accepted) and ADR-0012 (proposed), subsystem specs aligned with the 2026-10-18 decisions (NX-311), glossary and naming conventions (NX-315), threat model, CI/CD design, testing strategy, data-integrity policy, agent tooling. Most owner questions are answered; the rest are in [OPEN-QUESTIONS](docs/planning/OPEN-QUESTIONS.md).
- Merged into `develop`: the repo skeleton with `make check` (NX-010) and `ci.yml` with the `ci-gate` check (NX-011).
- Next (P0 Foundations): security workflow (NX-012), the contracts pipeline (NX-021) and port interfaces with a conformance suite (NX-050). See [TRACKER](docs/planning/TRACKER.md).

Only the repo skeleton is merged; there is no production code yet. Specs stay `Draft` until the owner approves them.

## Quick links

| Area | Document |
|---|---|
| Vision and scope | [docs/planning/VISION.md](docs/planning/VISION.md) |
| Roadmap (phases and exit criteria) | [docs/planning/ROADMAP.md](docs/planning/ROADMAP.md) |
| Work tracker (`NX-###` IDs) | [docs/planning/TRACKER.md](docs/planning/TRACKER.md) |
| Open questions and decision log | [docs/planning/OPEN-QUESTIONS.md](docs/planning/OPEN-QUESTIONS.md) |
| Owner to-do | [docs/planning/OWNER-TODO.md](docs/planning/OWNER-TODO.md) |
| Glossary | [docs/planning/GLOSSARY.md](docs/planning/GLOSSARY.md) |
| System design | [docs/architecture/SYSTEM-DESIGN.md](docs/architecture/SYSTEM-DESIGN.md) |
| ADR index | [docs/architecture/adr/README.md](docs/architecture/adr/README.md) |
| Specs index | [docs/specs/README.md](docs/specs/README.md) |
| Threat model | [docs/security/THREAT-MODEL.md](docs/security/THREAT-MODEL.md) |
| CI/CD architecture | [docs/cicd/CICD-ARCHITECTURE.md](docs/cicd/CICD-ARCHITECTURE.md) |
| Testing strategy | [docs/quality/TESTING-STRATEGY.md](docs/quality/TESTING-STRATEGY.md) |
| **Data integrity (mandatory)** | [docs/quality/DATA-INTEGRITY.md](docs/quality/DATA-INTEGRITY.md) |
| Marketing plan | [docs/planning/MARKETING.md](docs/planning/MARKETING.md) |
| Agent tooling (MCP, plugins, hooks) | [docs/agentic/TOOLING.md](docs/agentic/TOOLING.md) |
| Remote work | [docs/agentic/REMOTE-WORK.md](docs/agentic/REMOTE-WORK.md) |
| Hardware | [docs/ops/HARDWARE.md](docs/ops/HARDWARE.md) |
| Local LLM vs API cost analysis | [docs/ops/LOCAL-VS-API-COST.md](docs/ops/LOCAL-VS-API-COST.md) |
| Full docs index | [docs/README.md](docs/README.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Security policy | [SECURITY.md](SECURITY.md) |

The original brainstorms are kept as read-only source material: [Raw-plans.md](Raw-plans.md), [Raw-conversation.md](Raw-conversation.md). They are not specs; where they conflict with `docs/`, `docs/` wins.

## Branching model

See [ADR-0009](docs/architecture/adr/0009-branching-strategy.md).

| Branch | Purpose |
|---|---|
| `develop` | Integration branch for all day-to-day work. Changes arrive only by PR; a PR auto-merges once `ci-gate` is green (Q-PROC-2). Build, lint, format and typecheck are required, and security checks will be once NX-012 lands; tests are advisory (ADR-0009, Q-CI-6). |
| `main` | Verified releases only, promoted from `develop` (or `hotfix/*`). Owner-only merge. |
| `feat/NX-###-…`, `fix/…`, `docs/…`, `chore/…` | One tracker item each, branched from `develop`. |

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(sim): …`, `docs: …`).

## For AI agents and contributors

Start with [AGENTS.md](AGENTS.md). It sets the ground rules (spec first, no fabricated data, deterministic sim, hostile chat input, small PRs) and points to the role cards in [.agents/roles/](.agents/roles/). Claude Code also loads [CLAUDE.md](CLAUDE.md). Issue and label conventions are in [docs/planning/ISSUE-WORKFLOW.md](docs/planning/ISSUE-WORKFLOW.md).

Report vulnerabilities as described in [SECURITY.md](SECURITY.md), not in public issues.

## License

- **Code:** [MIT](LICENSE).
- **Brand and art** (logo, names, commissioned art, portraits): not covered by the MIT license; all rights reserved, kept under `assets/` with its own license file once assets exist (Q-LEGAL-4). Fonts and other third-party assets are committed only if their license allows redistribution. Licensed music is never committed and stays under its own terms (Q-LEGAL-2).
- **Dependencies:** must use MIT, BSD, Apache-2.0, ISC or MPL-2.0; GPL only in separate server-side processes (Q-LEGAL-1).
