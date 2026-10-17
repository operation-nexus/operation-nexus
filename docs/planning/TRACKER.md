# Work Tracker

Phase plan and ID index. **Live status for items that have an issue lives in GitHub Issues** (see ISSUE-WORKFLOW.md). IDs are stable; never reuse one.

**Status:** ⬜ Todo · 🟨 In progress · 👀 In review · ✅ Done · ⛔ Blocked · ❓ Needs owner decision
**Size:** S (≤½ day) · M (1–2 days) · L (3–5 days) — split anything bigger.

## Phase summary

| Phase | Items | Done | Status |
|---|---|---|---|
| P0 Foundations | 38 | 7 | 🟨 |
| P1 Sim kernel | 22 | 0 | ⬜ |
| P2 Closed alpha | 27 | 0 | ⬜ |
| P3 Public beta | 15 | 0 | ⬜ |
| P4 Depth | 12 | 0 | ⬜ |

---

## P0 — Foundations

### Planning & decisions
| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-001 | Initial planning docs, critique, specs, ADRs, tracker, AGENTS.md | L | ✅ | — | This PR |
| NX-002 [#1](https://github.com/canthony224/operation-nexus/issues/1) | Owner answers P0-blocking questions (Q-PROD-1/2, Q-ARCH-1/3, Q-CI-1..4, Q-LEGAL-1) | S | ✅ | NX-001 | Decision column filled |
| NX-003 [#2](https://github.com/canthony224/operation-nexus/issues/2) | Owner reviews ADR-0001…0008 → Accepted/Amended | S | ✅ | NX-002 | ADR statuses updated |
| NX-004 [#3](https://github.com/canthony224/operation-nexus/issues/3) | Owner drops reference files into `.agents/context/` + updates INDEX | S | ⬜ | — | INDEX lists files |
| NX-005 [#4](https://github.com/canthony224/operation-nexus/issues/4) | Move `Raw-*.md` to `docs/source/` with a "not a spec" banner | S | ❓ | NX-002 | Links updated |
| NX-006 [#5](https://github.com/canthony224/operation-nexus/issues/5) | Specs SIM-CORE, GAMEPLAY, FOG-OF-WAR, THREAT-DIRECTOR → Review → Approved | M | ⬜ | NX-002 | Owner sign-off |
| NX-007 [#6](https://github.com/canthony224/operation-nexus/issues/6) | Reference hardware spec documented (Q-OPS-1) | S | ❓ | — | `docs/ops/HARDWARE.md` |
| NX-008 [#7](https://github.com/canthony224/operation-nexus/issues/7) | Hand-authored first theater map sketch (≈15 nodes, roads, bridges) | M | ⬜ | Q-GD-9 | YAML + PNG sketch in `balance/theaters/` |
| NX-009 | Decide: mirror tracker to GitHub Issues + Project board? | S | ✅ | — | Decision recorded |

### Repo & CI/CD (see `docs/cicd/CICD-ARCHITECTURE.md`)
| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-010 [#8](https://github.com/canthony224/operation-nexus/issues/8) | Repo skeleton: `services/sim`, `apps/overlay`, `contracts/`, `tools/`, `deploy/`, Makefile, `.editorconfig`, pre-commit | M | ⬜ | NX-003 | `make check` runs green on empty skeleton |
| NX-011 [#9](https://github.com/canthony224/operation-nexus/issues/9) | `ci.yml`: path filters, python + typescript jobs, `ci-gate` | M | ⬜ | NX-010 | Required check on `main` |
| NX-012 [#10](https://github.com/canthony224/operation-nexus/issues/10) | `security.yml`: CodeQL, gitleaks, dependency-review, osv-scanner, zizmor, trivy config, hadolint | M | ⬜ | NX-010 | Fails on seeded test vuln/secret in a throwaway PR |
| NX-013 [#11](https://github.com/canthony224/operation-nexus/issues/11) | `build.yml`: buildx, pinned digests, SBOM, trivy image, cosign, provenance → GHCR | M | ⬜ | NX-011 | `cosign verify` passes on pushed image |
| NX-014 [#12](https://github.com/canthony224/operation-nexus/issues/12) | `deploy.yml` + `deploy/bin/deploy|rollback` + Tailscale (staging auto, prod approval) | L | ⬜ | NX-013, Q-OPS-1 | Deploy + auto-rollback demonstrated on staging |
| NX-015 [#13](https://github.com/canthony224/operation-nexus/issues/13) | `release.yml` release-please (manifest mode) | S | ⬜ | NX-011 | Release PR generated |
| NX-016 [#14](https://github.com/canthony224/operation-nexus/issues/14) | `nightly.yml` skeleton (soak, balance, rescan, scorecard) | M | ⬜ | NX-011 | Runs on schedule, uploads artifacts |
| NX-017 [#15](https://github.com/canthony224/operation-nexus/issues/15) | `pr-hygiene.yml`: conventional title, tracker-ID check, size label | S | ⬜ | NX-010 | PR without NX-ID fails |
| NX-018 [#16](https://github.com/canthony224/operation-nexus/issues/16) | `dependabot.yml` grouped weekly (pip/uv, npm, actions, docker) | S | ⬜ | NX-010 | First grouped PR appears |
| NX-019 [#17](https://github.com/canthony224/operation-nexus/issues/17) | import-linter contracts for module boundaries (SYSTEM-DESIGN §4) | S | ⬜ | NX-010 | Violating import fails CI |
| NX-020 [#18](https://github.com/canthony224/operation-nexus/issues/18) | Custom Semgrep rules (`.semgrep/`) per CICD §5 with tests | M | ⬜ | NX-012 | Each rule has positive/negative fixture |
| NX-021 [#19](https://github.com/canthony224/operation-nexus/issues/19) | Contracts pipeline: JSON Schema → Pydantic + TS, drift check, compat check | M | ⬜ | NX-010 | Changing schema without regen fails CI |
| NX-022 [#20](https://github.com/canthony224/operation-nexus/issues/20) | Repo settings applied (CICD §9 checklist) | S | ❓ | Q-CI-1 | Checklist ticked |
| NX-023 | CODEOWNERS, PR template, issue templates, SECURITY.md | S | ✅ | — | Files present |
| NX-024 [#21](https://github.com/canthony224/operation-nexus/issues/21) | markdownlint + lychee docs job | S | ⬜ | NX-011 | Broken link fails |
| NX-025 [#22](https://github.com/canthony224/operation-nexus/issues/22) | Dev container / `make bootstrap` for desktop + cloud agents (SessionStart hook) | M | ⬜ | NX-010 | Fresh clone → `make check` in one command |
| NX-026 [#23](https://github.com/canthony224/operation-nexus/issues/23) | Structured logging lib with secret-redaction + test | S | ⬜ | NX-010 | Test proves token redacted |
| NX-027 [#24](https://github.com/canthony224/operation-nexus/issues/24) | Runbook: rotate secrets | S | ⬜ | NX-014 | Doc reviewed |
| NX-028 | `.gitignore` additions (`*.db`, `node_modules/`, snapshots, logs, `.env*`) | S | ✅ | — | Present |
| NX-029 [#25](https://github.com/canthony224/operation-nexus/issues/25) | Agent review gate: code-review + security-review run on every PR (Q-CI-3) | M | ❓ | NX-011 | Review comment posted on PRs |

### Quality & security baselines
| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-030 [#26](https://github.com/canthony224/operation-nexus/issues/26) | Test harness skeleton: pytest profiles (ci/nightly), hypothesis settings, vitest, Playwright | M | ⬜ | NX-010 | Example tests run in CI |
| NX-044 [#28](https://github.com/canthony224/operation-nexus/issues/28) | Owner desktop agent setup (docs/agentic/TOOLING.md §5): jq, Serena, plugins | S | ⬜ | — | `/mcp` shows serena + context7 connected |
| NX-045 [#29](https://github.com/canthony224/operation-nexus/issues/29) | Spike: code knowledge-graph MCP (CodeGraphContext vs codebase-memory-mcp), measured vs baseline | M | ⬜ | P1 code exists | Report with token and accuracy numbers; adopt/reject decision |
| NX-046 [#30](https://github.com/canthony224/operation-nexus/issues/30) | Data-integrity Semgrep rules + FB registry tests (DATA-INTEGRITY §6) | M | ⬜ | NX-012 | Each rule has positive/negative fixtures |
| NX-047 [#31](https://github.com/canthony224/operation-nexus/issues/31) | Optional: SonarQube Cloud quality gate (Q-CI-5) | S | ❓ | P2 | Decision recorded |
| NX-048 | Open GitHub issues for P0 items (labels auto-created; phases tracked as `phase:Pn` labels because the available tooling can't create milestones) | S | ✅ | owner OK | Issues #1–#32 exist and are linked here |
| NX-049 [#32](https://github.com/canthony224/operation-nexus/issues/32) | Create `develop` from `main` after planning sign-off; apply branch rulesets per ADR-0009; set default branch to `develop` | S | ⬜ | planning done | Rulesets visible; PR to main without gates is blocked |
| NX-050 | Port interfaces + `Capabilities` + conformance suite skeleton (chat, LLM, TTS) per ADR-0010; import-linter vendor rule | M | ⬜ | NX-010, NX-019 | A fake adapter passes the suite; a vendor import outside adapters fails CI |
| NX-040 [#27](https://github.com/canthony224/operation-nexus/issues/27) | Threat model review with owner; accept residual risks | S | ❓ | NX-001 | THREAT-MODEL §6 signed off |

---

## P1 — Sim kernel (headless)

| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-100 | `SimRng` (PCG64, named sub-streams) | S | ⬜ | NX-010 | Unit + property tests; same seed → same draws |
| NX-101 | World model types + canonical `state_hash` | M | ⬜ | NX-021 | SC-9 round-trip property |
| NX-102 | Fixed-step runtime + inbox + canonical command ordering | M | ⬜ | NX-101 | SC-6 shuffled-arrival property |
| NX-103 | Snapshot + command log + restore | M | ⬜ | NX-102 | Kill/restore integration test equal hash |
| NX-104 | Spatial grid + benchmarks | M | ⬜ | NX-101 | 1k entities p99 < 25 ms (bench) |
| NX-105 | Golden replay framework + cross-process check in CI | M | ⬜ | NX-103 | Job `sim-determinism` required |
| NX-106 | Balance config loader (YAML, schema-validated, hashed) | S | ⬜ | NX-101 | Invalid config rejected; hash in campaign |
| NX-120 | Theater loader + road graph + A* | M | ⬜ | NX-008, NX-106 | Paths avoid destroyed bridges |
| NX-121 | Kinematics (air direct, ground on graph), time scale | M | ⬜ | NX-120 | Property: positions in bounds, on edges |
| NX-122 | Unit slots, spawn, respawn delay, reserve queue | M | ⬜ | NX-121 | GP-1..3 tests |
| NX-123 | Logistics: stock, factories, convoys, unload, starvation | L | ⬜ | NX-121 | Conservation property; starvation loadouts |
| NX-124 | Combat: targeting, pk model, SAM rings | L | ⬜ | NX-121 | Deterministic outcomes with seeded rng; domain rules |
| NX-125 | Capture with contest/decay | M | ⬜ | NX-121 | No double flip property |
| NX-126 | Campaign: objectives, momentum, win/loss, clock pause | M | ⬜ | NX-125 | Scenario tests per condition |
| NX-150 | FoW tiers + server-side redaction + blob clustering | L | ⬜ | NX-104 | FOW-1..3 properties |
| NX-151 | Enemy-side view for director (FOW-4) | M | ⬜ | NX-150 | Director API accepts only `EnemyView` |
| NX-155 | Director: CP, tiers w/ hysteresis, budget | M | ⬜ | NX-151 | Hysteresis property |
| NX-156 | Director: operations library + scoring + threat memory | L | ⬜ | NX-155 | "Convoy raids → escorts" golden scenario |
| NX-157 | AI garrison + low-population rules | M | ⬜ | NX-155 | overnight-0 scenario: ≤1 node/6h |
| NX-031 | Balance harness (`tools/balance`) + bot personas + report | L | ⬜ | NX-126 | 5 standard scenarios × 20 seeds report |
| NX-032 | Replay CLI + measured storage size | S | ⬜ | NX-103 | Size documented in CLIPS-REPLAY |
| NX-033 | Headless soak (6h) in nightly | M | ⬜ | NX-016 | No memory growth; hashes replay |

## P2 — Closed alpha (Twitch, unlisted)

| ID | Item | Size | Status | Depends |
|---|---|---|---|---|
| NX-170 | WS server: Hello/Welcome/Snapshot/Delta/Hud, bounded queues | L | ⬜ | NX-150 |
| NX-171 | Delta encoder + size budget test | M | ⬜ | NX-170 |
| NX-175 | Overlay scaffold, layered canvases, reconnect, banners | M | ⬜ | NX-170 |
| NX-176 | Terrain contour pre-render + nodes/roads/bridges | M | ⬜ | NX-175 |
| NX-177 | Units (shape-coded), rings, blobs, tracers, interpolation | L | ⬜ | NX-176 |
| NX-178 | HUD: momentum, objective, threat, ticker, rotating panels | M | ⬜ | NX-175 |
| NX-179 | PiP 2D intercept scope + PiP director scoring | M | ⬜ | NX-177 |
| NX-180 | Palette/colorblind script + visual snapshot tests | M | ⬜ | NX-177 |
| NX-190 | Gateway: adapter interface + normalization + rate limits | M | ⬜ | NX-021 |
| NX-191 | Twitch EventSub adapter + moderation event sync + batched replies | L | ⬜ | NX-190 |
| NX-192 | Command parser + grammar + fuzz tests | M | ⬜ | NX-190 |
| NX-193 | Local chat simulator (`tools/chatsim`) for dev | M | ⬜ | NX-190 |
| NX-200 | Commanders + identities + generated callsigns (SQLite, migrations) | M | ⬜ | NX-010 |
| NX-201 | Persistence writer task + backups | M | ⬜ | NX-200 |
| NX-041 | Moderation pipeline + denylist + tests (SEC-MOD-1) | M | ⬜ | NX-190 |
| NX-225 | Audio buses + foley + licensed music stems | M | ⬜ | Q-LEGAL-2 |
| NX-226 | TTS worker + sitrep templates + queue + night mode | L | ⬜ | Q-AI-4 |
| NX-250 | Metrics + structured logs + dashboard | M | ⬜ | NX-026 |
| NX-251 | Watchdog: frame-freeze probe, live probe, fallback scene | L | ⬜ | NX-175 |
| NX-252 | Alerting (ntfy/Discord) + off-site dead-man's-switch heartbeat (MONITORING-WATCHDOG L3) | S | ⬜ | NX-250 |
| NX-257 | Optional: smart-plug power-cycle for a hung stream PC | S | ❓ | NX-251 |
| NX-253 | Admin console v1 (kill switch, pause, bans, director override) | L | ⬜ | NX-200 |
| NX-254 | OBS scene collection + obs-websocket config in `deploy/obs/` | M | ⬜ | Q-OPS-1 |
| NX-255 | Production compose + systemd units + host provisioning doc | M | ⬜ | NX-014 |
| NX-256 | Runbooks (deploy/rollback, restore, moderation incident, outage) | M | ⬜ | NX-255 |
| NX-042 | Phase-2 security review + pentest of command path | M | ⬜ | all P2 |
| NX-034 | Cold-tester readability study (5 people). Also test: hidden-shooter tracers on/off (Q-CT-3), recruit strip + `!me` clarity (FB-UX), orientation | S | ⬜ | NX-178 |
| NX-035 | 7-day unattended burn-in on unlisted stream | M | ⬜ | all P2 |

## P3 — Public beta

| ID | Item | Status |
|---|---|---|
| NX-210 | XP events → progression, diminishing returns, ranks O-1..O-3 | ⬜ |
| NX-211 | Leaderboards per role + rotating panel data | ⬜ |
| NX-202 | Custom callsigns + approval queue | ⬜ |
| NX-203 | OAuth link portal (separate app, tunnel, CSRF, DAST) | ⬜ |
| NX-204 | `!forget` deletion job + privacy notice | ⬜ |
| NX-205 | Postgres migration if portal needs DB writes (ADR-0003) | ❓ |
| NX-195 | YouTube streamList adapter + quota dashboard + quota increase application | ⬜ |
| NX-196 | Kick adapter (optional) | ❓ |
| NX-233 | Excitement scoring + clip jobs | ⬜ |
| NX-234 | Clip render worker + review queue in admin | ⬜ |
| NX-180b | 9:16 vertical overlay route | ⬜ |
| NX-043 | ZAP baseline on portal in staging | ⬜ |
| NX-036 | Analytics: sessions, command rate, D7 (privacy-preserving) | ⬜ |
| NX-037 | Public launch checklist (ToS review per platform, privacy, moderation staffing) | ⬜ |
| NX-038 | Devlog #1 recorded | ⬜ |
| NX-128 | Sea domain + naval graph (pulled forward from P4, Q-GD-8) | ⬜ |
| NX-258 | Admin RBAC v1: roles, grants, authz middleware, audit (ADMIN-RBAC) | ⬜ |
| NX-259 | Admin console: moderation + user management pages (phone-friendly) | ⬜ |
| NX-260 | Rules/balance editor: schema forms, diff, hot vs next-campaign apply, rollback | ⬜ |
| NX-261 | Discord admin channel adapter (slash-command parity, verified role mapping) | ⬜ |
| NX-034b | Measure "did my command work" (FB-UX-6) | ⬜ |

## P4 — Depth

| ID | Item | Status |
|---|---|---|
| NX-212 | Ranks O-4..O-6, specialist chassis (SEAD, jammer, engineer, AWACS, artillery) | ⬜ |
| NX-213 | Doctrines (per-campaign lock, signature abilities, badges) | ⬜ |
| NX-214 | Packages / wingman / NPC fill | ⬜ |
| NX-215 | Cosmetics (halos, trails, placards) | ⬜ |
| NX-127 | Hold the Line mode | ⬜ |
| NX-240 | LlmClient + budgets + circuit breaker + FakeLLM | ⬜ |
| NX-241 | Director advisor | ⬜ |
| NX-242 | Narrator | ⬜ |
| NX-243 | `!order` parser + eval suite | ⬜ |
| NX-244 | Premium TTS voices (Gemini) behind budget | ⬜ |
| NX-245 | Discord bot (community, verification via OAuth) | ⬜ |
| NX-129 | Urban terrain rules (LOS blocking, districts) | ⬜ |
| NX-130 | Campaign carry-over (Q-GD-12) | ⬜ |
| NX-262 | Campaign planning and scheduling (calendar, scheduled events) | ⬜ |
| NX-263 | Game Master takeover (ASSIST/FULL) + on-stream badge | ⬜ |
| NX-264 | Theater library: upload, validate, preview, publish | ⬜ |
| NX-265 | Procedural theater generation (water-heavy archetypes, west→east) | ⬜ |
| NX-266 | Two-person rule and approvals | ⬜ |
| NX-267 | SupportSource port + conformance suite | ⬜ |
| NX-268 | Twitch channel points redemptions (create rewards, fulfill/refund) | ⬜ |
| NX-269 | Twitch Bits + subs (gift de-dup) + Hype Train v2 | ⬜ |
| NX-270 | YouTube Super Chat/Sticker/membership ingest | ⬜ |
| NX-271 | Redemption rules engine + forbidden-effect validator | ⬜ |
| NX-274 | Brand and style guide: name usage, fictional factions and insignia, unit class naming (generic: Tank, Striker, Bomber…), color, type, sound identity, tone of voice; **no real names** rule added to the content validator | ⬜ |
| NX-275 | Lore bible + campaign narrative: why we fight, who the enemy is, the season and global campaign arc, mission briefings; feeds sitrep templates and the global map (future) | ⬜ |
| NX-276 | Community health design: positive-only feedback (no kill-shaming), cooperative and role-based leaderboards (no single "top killer"), friendly tone in all bot text, code of conduct, mod tools (ADMIN-RBAC), no PvP between viewers | ⬜ |
| NX-277 | Layered anti-farming without captchas: (1) platform account age, if the platform API exposes it [VERIFY: Twitch Get Users `created_at`; YouTube channel `publishedAt` costs quota]; (2) our own first-seen age; (3) first-completed-mission gate; (4) hourly diminishing XP; (5) admin-console anomaly flags (many new accounts acting in lockstep); (6) mod tools to void XP | ⬜ |
| NX-278 | Voice cast listening session: pick an engine voice, filter and pacing per profile; set the sitrep cadence | ⬜ |
| NX-279 | Post-war reveal: "what you didn't see" recap (summary + optional narrative) with a decision-source label per enemy action (RULES / ADVISOR / GAME_MASTER), plus the seed published; shown in the AAR and on the replay site | ⬜ |
| NX-280 | Balance experiment: fuel for all domains (big ground and sea tanks, slower burn, "crawl when dry") vs air-only, run as a harness A/B plus a playtest | ⬜ |
| NX-281 | Rescue and refuel missions (future, tied to NX-280): a stranded ground or logistics unit can end its sortie or wait for rescue, and operators can mount a rescue or refuel run. Air-to-air refueling (tanker unit) for combat air patrols in safe airspace. Aircraft that run dry crash. | ⬜ |
| NX-273 | Research + spike: Epidemic Sound license coverage for 24/7 streams/clips; API/MCP availability; `MusicSource` port so an agent can search and queue licensed tracks by mood (tension-driven, AUDIO-TTS §1) | ⬜ |
| NX-272 | Third-party tips adapter (Ko-fi or Streamlabs/StreamElements; Q-SUP-3) | ❓ |

## Backlog (unscheduled — from owner's conversation & plans)
- Global/theater map with multiple campaigns and offensives (C48)
- "Siege" mode — AI must hold out for X hours (C29)
- Procedural theaters (Arctic Strait, Desert Archipelago)
- Three.js thermal/FLIR PiP
- Companion site with replay scrubber & detailed stats
- Named NPC rival commanders with personalities
- Viewer-made voices (requires consent policy, SEC-MOD-4)
- TikTok (view-only simulcast, or chat if official API appears — ADR-0008)
- Kubernetes/Helm (only per SYSTEM-DESIGN §7 triggers)
- Localization of HUD/commands/TTS
- **Voice ops line (owner idea, future):** a phone call system that calls the owner on critical alerts, or that the owner calls to talk to an ops agent. The agent can report status, run admin actions through RBAC with confirmation and audit, and record the owner's voice or transcript as clip narration. Text-based alerts and management come first (ADMIN-RBAC, OPS-ADMIN). Needs its own spec, security review (caller authentication, no destructive actions without confirmation) and cost research.
