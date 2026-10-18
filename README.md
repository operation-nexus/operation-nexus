# Operation Nexus

**Live-stream chat plays a 24/7 co-op war against an adaptive AI, on a glowing radar war-room map.**

Viewers are **Operators** of **Clearwave** (working name, Q-BRAND-2), defending the network against **The Static**, a glitchy enemy with a taunting mastermind. Type one command in chat and your unit is on screen. Hold supply lines, scout through the fog, and push the frontline over days while the Threat Director adapts to what you do.

The look is **"Signal"**: a radar war room on near-black, with radio static and callsigns (Q-BRAND-1, Q-STYLE-1). The tone is **fun, friendly and playful**, not grim or sweaty. The goal is a welcoming, non-toxic community.

Under the hood: a deterministic, server-authoritative simulation (Python), a browser overlay captured by OBS (TypeScript, Canvas2D), and platform chat adapters (Twitch first, then YouTube; TikTok deferred, ADR-0008). LLMs only advise and narrate; deterministic code decides (ADR-0007).

## Status

**Planning is largely complete; implementation is starting.**

- Done: vision, roadmap, tracker, system design, ADRs 0001–0011, subsystem specs, threat model, CI/CD design, testing strategy, data-integrity policy, agent tooling. Most owner questions are answered; the rest are in [OPEN-QUESTIONS](docs/planning/OPEN-QUESTIONS.md).
- In review: the repo skeleton (NX-010) is open as PR #37 against `develop`.
- Next (P0 Foundations): CI workflows (NX-011, NX-012), the contracts pipeline (NX-021) and port interfaces with a conformance suite (NX-050). See [TRACKER](docs/planning/TRACKER.md).

No production code is merged yet. Specs stay `Draft` until the owner approves them.

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
| `develop` | Integration branch for all day-to-day work. PRs target it. Security and build checks are required. |
| `main` | Verified releases only, promoted from `develop` (or `hotfix/*`). Owner-only merge. |
| `feat/NX-###-…`, `fix/…`, `docs/…`, `chore/…` | One tracker item each, branched from `develop`. |

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(sim): …`, `docs: …`).

## For AI agents and contributors

Start with [AGENTS.md](AGENTS.md). It sets the ground rules (spec first, no fabricated data, deterministic sim, hostile chat input, small PRs) and points to the role cards in [.agents/roles/](.agents/roles/). Claude Code also loads [CLAUDE.md](CLAUDE.md). Issue and label conventions are in [docs/planning/ISSUE-WORKFLOW.md](docs/planning/ISSUE-WORKFLOW.md).

Report vulnerabilities as described in [SECURITY.md](SECURITY.md), not in public issues.

## License

- **Code:** [MIT](LICENSE).
- **Brand assets, art, fonts and music:** not covered by the MIT license. See Q-LEGAL-4 (pending; raised in the [gap analysis](docs/review/GAP-ANALYSIS-2026-10-17.md), recommendation: brand assets all rights reserved, licensed music never committed). Licensed music stays under its own terms (Q-LEGAL-2).
- **Dependencies:** must use MIT, BSD, Apache-2.0, ISC or MPL-2.0; GPL only in separate server-side processes (Q-LEGAL-1).
