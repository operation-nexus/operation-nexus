# Docs Index

Every folder and file under `docs/`, with one line each. Start with [planning/VISION.md](planning/VISION.md), then [architecture/SYSTEM-DESIGN.md](architecture/SYSTEM-DESIGN.md). Root-level entry points: [README](../README.md), [AGENTS.md](../AGENTS.md), [CHANGELOG](../CHANGELOG.md), [SECURITY.md](../SECURITY.md).

When you add, rename or remove a doc, update this index in the same PR.

## planning/ — what we build and in what order

| Doc | Description |
|---|---|
| [VISION.md](planning/VISION.md) | One-sentence pitch, pillars, audience, v1 scope and success targets. |
| [ROADMAP.md](planning/ROADMAP.md) | Phases P0–P5 with goals and exit criteria, plus milestone gates. |
| [TRACKER.md](planning/TRACKER.md) | Phase plan and `NX-###` ID index; links to GitHub Issues for live status. |
| [OPEN-QUESTIONS.md](planning/OPEN-QUESTIONS.md) | Owner questions with recommendations, and the log of decisions made. |
| [OWNER-TODO.md](planning/OWNER-TODO.md) | Actions only the owner can take: desktop setup, GitHub settings, hardware, accounts. |
| [GLOSSARY.md](planning/GLOSSARY.md) | Project terms (Clearwave, The Static, Operator, and more). |
| [ISSUE-WORKFLOW.md](planning/ISSUE-WORKFLOW.md) | How GitHub Issues, labels and the tracker fit together. |
| [MARKETING.md](planning/MARKETING.md) | Living marketing plan, devlog checkpoints and posting principles. |

## architecture/ — how the system is shaped

| Doc | Description |
|---|---|
| [SYSTEM-DESIGN.md](architecture/SYSTEM-DESIGN.md) | Context, principles, non-functional requirements, modules, key flows, deployment, scaling path, failure modes. |
| [adr/README.md](architecture/adr/README.md) | ADR index with status. |
| [adr/0000-template.md](architecture/adr/0000-template.md) | Template for new ADRs. |
| [adr/0001-modular-monolith.md](architecture/adr/0001-modular-monolith.md) | Start as a modular monolith. |
| [adr/0002-deterministic-sim-kernel.md](architecture/adr/0002-deterministic-sim-kernel.md) | Deterministic, fixed-step simulation kernel at 10 Hz. |
| [adr/0003-persistence.md](architecture/adr/0003-persistence.md) | In-memory live state, snapshot + command log, SQLite for durable data. |
| [adr/0004-toolchain.md](architecture/adr/0004-toolchain.md) | Languages and toolchain. |
| [adr/0005-overlay-renderer.md](architecture/adr/0005-overlay-renderer.md) | Canvas2D overlay first, Pixi.js only if profiling demands it. |
| [adr/0006-deployment-single-node.md](architecture/adr/0006-deployment-single-node.md) | Single-node Compose deploy, signed images, Tailscale-based deploy. |
| [adr/0007-llm-role.md](architecture/adr/0007-llm-role.md) | LLMs advise and narrate; deterministic rules decide. |
| [adr/0008-platforms.md](architecture/adr/0008-platforms.md) | Platform order: Twitch, then YouTube, then Kick; TikTok deferred. |
| [adr/0009-branching-strategy.md](architecture/adr/0009-branching-strategy.md) | `develop` for integration, `main` for verified releases. |
| [adr/0010-platform-and-provider-neutrality.md](architecture/adr/0010-platform-and-provider-neutrality.md) | Ports and adapters with a conformance suite; no vendor lock-in. |
| [adr/0011-support-redemptions-no-currency.md](architecture/adr/0011-support-redemptions-no-currency.md) | Support events trigger capped redemptions; no in-game currency for now. |

## specs/ — subsystem behavior (all Draft)

| Doc | Description |
|---|---|
| [README.md](specs/README.md) | Spec index with scope and phase. |
| [_TEMPLATE.md](specs/_TEMPLATE.md) | Template for new specs. |
| [SIM-CORE.md](specs/SIM-CORE.md) | Tick loop, world model, determinism rules, performance budgets. |
| [GAMEPLAY.md](specs/GAMEPLAY.md) | Roles, commands, combat, logistics, capture, win/loss, campaigns. |
| [FOG-OF-WAR.md](specs/FOG-OF-WAR.md) | Sensor tiers, redaction, director fairness. |
| [THREAT-DIRECTOR.md](specs/THREAT-DIRECTOR.md) | Enemy AI tiers, budget, threat memory, advisor hook. |
| [WIRE-PROTOCOL.md](specs/WIRE-PROTOCOL.md) | Server-to-overlay WebSocket protocol and versioning. |
| [OVERLAY.md](specs/OVERLAY.md) | Broadcast layout, readability, accessibility, picture-in-picture. |
| [CHAT-GATEWAY.md](specs/CHAT-GATEWAY.md) | Platform adapters, normalization, rate limits, replies. |
| [IDENTITY.md](specs/IDENTITY.md) | Commanders, generated callsigns, OAuth account linking. |
| [PROGRESSION.md](specs/PROGRESSION.md) | XP, ranks, merit, doctrines, cosmetics, anti-farming. |
| [AUDIO-TTS.md](specs/AUDIO-TTS.md) | Audio buses, sitreps, TTS, night mode. |
| [CLIPS-REPLAY.md](specs/CLIPS-REPLAY.md) | Replays, excitement scoring, clip review queue. |
| [LLM-ADVISORS.md](specs/LLM-ADVISORS.md) | LLM advisor, narrator, `!order` parser and budgets. |
| [CONTRACTS.md](specs/CONTRACTS.md) | Enums, commands, events, wire messages, internal and admin API. |
| [DATA-MODEL.md](specs/DATA-MODEL.md) | SQLite schema, ledgers, snapshot and log formats, retention, backups. |
| [CONFIG-AND-CONTENT.md](specs/CONFIG-AND-CONTENT.md) | Config layers, balance keys, unit catalog, theater format. |
| [STATE-MACHINES-AND-FLOWS.md](specs/STATE-MACHINES-AND-FLOWS.md) | Lifecycles, transition tables, end-to-end sequences. |
| [ADMIN-RBAC.md](specs/ADMIN-RBAC.md) | Admin roles and permissions, moderation, GM takeover, rules editor. |
| [SUPPORT-REDEMPTIONS.md](specs/SUPPORT-REDEMPTIONS.md) | Bits, channel points, Super Chats and tips mapped to capped redemptions. |
| [OPS-ADMIN.md](specs/OPS-ADMIN.md) | Watchdog, observability, alerting, admin console, kill switch, runbooks. |

## security/

| Doc | Description |
|---|---|
| [THREAT-MODEL.md](security/THREAT-MODEL.md) | Protected assets, actors, trust boundaries, STRIDE summary and the testable `SEC-*` requirements. |

## cicd/

| Doc | Description |
|---|---|
| [CICD-ARCHITECTURE.md](cicd/CICD-ARCHITECTURE.md) | Pipeline design: branching, required checks, security tooling, environments, zero-downtime deploys, secrets. |

## quality/

| Doc | Description |
|---|---|
| [DATA-INTEGRITY.md](quality/DATA-INTEGRITY.md) | **Mandatory** no-fabricated-data policy and the registry of approved fallbacks. |
| [DEFINITION-OF-DONE.md](quality/DEFINITION-OF-DONE.md) | What must be true before a tracker item is Done. |
| [REVIEW-CHECKLIST.md](quality/REVIEW-CHECKLIST.md) | Checklist for human and agent reviewers. |
| [TESTING-STRATEGY.md](quality/TESTING-STRATEGY.md) | Risk-to-test mapping, test pyramid and budgets, coverage policy, flaky-test handling. |

## ops/ — hardware, cost and monitoring

| Doc | Description |
|---|---|
| [HARDWARE.md](ops/HARDWARE.md) | Owner's machines, bandwidth budget, fit for the project and proposed role split. |
| [LOCAL-VS-API-COST.md](ops/LOCAL-VS-API-COST.md) | Cost-benefit of a local LLM vs paid APIs (estimates, sourced prices). |
| [MONITORING-WATCHDOG.md](ops/MONITORING-WATCHDOG.md) | Three-layer monitoring and watchdog design. |
| [data/llm-cost-estimates.csv](ops/data/llm-cost-estimates.csv) | Data behind the cost analysis charts. |
| [img/llm-monthly-cost.svg](ops/img/llm-monthly-cost.svg) | Chart: estimated monthly LLM cost by option and scenario. |
| [img/llm-cumulative-24mo.svg](ops/img/llm-cumulative-24mo.svg) | Chart: cumulative cost over 24 months, medium scenario. |

## agentic/ — working with AI agents

| Doc | Description |
|---|---|
| [TOOLING.md](agentic/TOOLING.md) | Committed agent config, plugins and skills, MCP servers, token-efficiency practices. |
| [REMOTE-WORK.md](agentic/REMOTE-WORK.md) | Planning, reviewing and approving from a phone while the desktop runs. |

## review/ — critiques and research (point-in-time reports)

| Doc | Description |
|---|---|
| [PLAN-CRITIQUE.md](review/PLAN-CRITIQUE.md) | Critique of the original raw plans. |
| [SECURITY-REVIEW-RAW-PLANS.md](review/SECURITY-REVIEW-RAW-PLANS.md) | Security review of the raw plans' sample code (do not reuse it). |
| [PLATFORM-REALITY-CHECK.md](review/PLATFORM-REALITY-CHECK.md) | Platform and dependency risks, from web research. |
| [SUPPORT-AND-SCRAPING-RESEARCH.md](review/SUPPORT-AND-SCRAPING-RESEARCH.md) | YouTube chat scraping and support/donation event research. |
| [EPIDEMIC-SOUND-RESEARCH.md](review/EPIDEMIC-SOUND-RESEARCH.md) | Epidemic Sound licensing for a 24/7 stream (unverified). |
| [GEMINI-TTS-VOICE-DESIGN-RESEARCH.md](review/GEMINI-TTS-VOICE-DESIGN-RESEARCH.md) | Gemini TTS voice design capabilities (unverified). |
| [GAP-ANALYSIS-2026-10-17.md](review/GAP-ANALYSIS-2026-10-17.md) | Gap analysis of the planning set: unanswered questions and missing docs. |
