# Work Tracker

Phase plan and ID index. **Live status for items that have an issue lives in GitHub Issues** (see ISSUE-WORKFLOW.md). IDs are stable; never reuse one.

**Status:** ⬜ Todo · 🟨 In progress · 👀 In review · ✅ Done · ⛔ Blocked · ❓ Needs owner decision
**Size:** S (≤½ day) · M (1–2 days) · L (3–5 days) — split anything bigger.

## Phase summary

| Phase | Items | Done | Status |
|---|---|---|---|
| P0 Foundations | 42 | 19 | 🟨 |
| P1 Sim kernel | 39 | 31 | 🟨 |
| P2 Closed alpha | 34 | 0 | ⬜ |
| P3 Public beta | 22 | 0 | ⬜ |
| P4 Depth | 67 | 1 | ⬜ |

Not counted above: the 10 items NX-328..NX-337 in "Brand, marketing, community and legal" (added 2026-10-18; phase noted per item once triaged).

---

## P0 — Foundations

### Planning & decisions
| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-001 | Initial planning docs, critique, specs, ADRs, tracker, AGENTS.md | L | ✅ | — | This PR |
| NX-002 [#1](https://github.com/operation-nexus/operation-nexus/issues/1) | Owner answers P0-blocking questions (Q-PROD-1/2, Q-ARCH-1/3, Q-CI-1..4, Q-LEGAL-1) | S | ✅ | NX-001 | Decision column filled |
| NX-003 [#2](https://github.com/operation-nexus/operation-nexus/issues/2) | Owner reviews ADR-0001…0008 → Accepted/Amended | S | ✅ | NX-002 | ADR statuses updated |
| NX-004 [#3](https://github.com/operation-nexus/operation-nexus/issues/3) | Owner drops reference files into `.agents/context/` + updates INDEX | S | ⬜ | — | INDEX lists files |
| NX-005 [#4](https://github.com/operation-nexus/operation-nexus/issues/4) | Move `Raw-*.md` to `docs/source/` with a "not a spec" banner | S | ❓ | NX-002 | Links updated |
| NX-006 [#5](https://github.com/operation-nexus/operation-nexus/issues/5) | Specs SIM-CORE, GAMEPLAY, FOG-OF-WAR, THREAT-DIRECTOR → Review → Approved | M | ✅ | NX-002 | Owner sign-off. All four Approved: FOG-OF-WAR and THREAT-DIRECTOR 2026-10-19, SIM-CORE and GAMEPLAY 2026-10-20 after NX-345 |
| NX-007 [#6](https://github.com/operation-nexus/operation-nexus/issues/6) | Reference hardware spec documented (Q-OPS-1) | S | ❓ | — | `docs/ops/HARDWARE.md` |
| NX-008 [#7](https://github.com/operation-nexus/operation-nexus/issues/7) | Hand-authored first theater map sketch (12 nodes, 8 strategic bases, roads, bridges; Q-TH-1..7) | M | ✅ | Q-GD-9 | YAML in `content/theaters/strait-1.yaml` + SVG sketch in `docs/design/theater-1.svg` (PR #127) |
| NX-009 | Decide: mirror tracker to GitHub Issues + Project board? | S | ✅ | — | Decision recorded |

### Repo & CI/CD (see `docs/cicd/CICD-ARCHITECTURE.md`)
| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-010 [#8](https://github.com/operation-nexus/operation-nexus/issues/8) | Repo skeleton: `services/sim`, `apps/overlay`, `contracts/`, `tools/`, `deploy/`, Makefile, `.editorconfig`, pre-commit | M | ✅ | NX-003 | `make check` runs green on empty skeleton |
| NX-011 [#9](https://github.com/operation-nexus/operation-nexus/issues/9) | `ci.yml`: path filters, python + typescript jobs, `ci-gate` | M | ✅ | NX-010 | Required check on `main` |
| NX-012 [#10](https://github.com/operation-nexus/operation-nexus/issues/10) | `security.yml`: CodeQL, gitleaks, dependency-review, osv-scanner, zizmor, trivy config, hadolint | M | ✅ | NX-010 | Fails on seeded test vuln/secret in a throwaway PR |
| NX-013 [#11](https://github.com/operation-nexus/operation-nexus/issues/11) | `build.yml`: buildx, pinned digests, SBOM, trivy image, cosign, provenance → GHCR | M | ⬜ | NX-011 | `cosign verify` passes on pushed image |
| NX-014 [#12](https://github.com/operation-nexus/operation-nexus/issues/12) | `deploy.yml` + `deploy/bin/deploy|rollback` + Tailscale (staging auto, prod approval) | L | ⬜ | NX-013, Q-OPS-1 | Deploy + auto-rollback demonstrated on staging |
| NX-015 [#13](https://github.com/operation-nexus/operation-nexus/issues/13) | `release.yml` release-please (manifest mode) | S | ⬜ | NX-011 | Release PR generated |
| NX-016 [#14](https://github.com/operation-nexus/operation-nexus/issues/14) | `nightly.yml` skeleton (soak, balance, rescan, scorecard) | M | ✅ | NX-011 | Runs on schedule, uploads artifacts. Skeleton runs determinism, grid bench and the dependency rescan; soak (NX-033), balance (NX-031), base-image rescan (NX-013) and Scorecard (needs an approved pin) join with their items |
| NX-017 [#15](https://github.com/operation-nexus/operation-nexus/issues/15) | `pr-hygiene.yml`: conventional title, tracker-ID check, size label | S | ✅ | NX-010 | PR without NX-ID fails |
| NX-018 [#16](https://github.com/operation-nexus/operation-nexus/issues/16) | `dependabot.yml` grouped weekly (uv, npm, actions; docker arrives with the first Dockerfile, NX-013) + label sync | S | ✅ | NX-010 | First grouped PR appears |
| NX-019 [#17](https://github.com/operation-nexus/operation-nexus/issues/17) | import-linter contracts for module boundaries (SYSTEM-DESIGN §4; Q-MB-1) | S | ✅ | NX-010 | Violating import fails CI (a test proves it) |
| NX-020 [#18](https://github.com/operation-nexus/operation-nexus/issues/18) | Custom Semgrep rules (`.semgrep/`) per CICD §5 with tests | M | ⬜ | NX-012 | Each rule has positive/negative fixture |
| NX-021 [#19](https://github.com/operation-nexus/operation-nexus/issues/19) | Contracts pipeline: JSON Schema → Pydantic + TS, drift check, compat check; seed schemas only (Q-CT-6..10) | M | ✅ | NX-010 | Changing schema without regen fails CI |
| NX-022 [#20](https://github.com/operation-nexus/operation-nexus/issues/20) | Repo settings applied (CICD §9 checklist) | S | ✅ | Q-CI-1 | Checklist ticked |
| NX-023 | CODEOWNERS, PR template, issue templates, SECURITY.md | S | ✅ | — | Files present |
| NX-024 [#21](https://github.com/operation-nexus/operation-nexus/issues/21) | markdownlint + lychee docs job | S | ⬜ | NX-011 | Broken link fails |
| NX-025 [#22](https://github.com/operation-nexus/operation-nexus/issues/22) | Dev container / `make bootstrap` for desktop + cloud agents (SessionStart hook) | M | ✅ | NX-010 | Fresh clone → `make check` in one command |
| NX-026 [#23](https://github.com/operation-nexus/operation-nexus/issues/23) | Structured logging lib with secret-redaction + test | S | ✅ | NX-010 | Test proves token redacted |
| NX-027 [#24](https://github.com/operation-nexus/operation-nexus/issues/24) | Runbook: rotate secrets | S | ⬜ | NX-014 | Doc reviewed |
| NX-028 | `.gitignore` additions (`*.db`, `node_modules/`, snapshots, logs, `.env*`) | S | ✅ | — | Present |
| NX-029 [#25](https://github.com/operation-nexus/operation-nexus/issues/25) | Agent review gate: code-review + security-review run on every PR (Q-CI-3) | M | ✅ | NX-011 | Review comment posted on PRs |
| NX-327 | Pin the toolchain: Node 22 in `.node-version` (CI reads it; `engines.node`), Python 3.12 in `services/sim/.python-version`; `make bootstrap` and `make check` fail clearly on a wrong Node major; fix the `prettier-overlay` pre-commit hook path | S | ✅ | NX-010 | Wrong Node major stops `make bootstrap` with a message |

### Quality & security baselines
| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-030 [#26](https://github.com/operation-nexus/operation-nexus/issues/26) | Test harness skeleton: pytest profiles (ci/nightly), hypothesis settings, vitest, Playwright | M | 🟨 | NX-010 | Example tests run in CI. Hypothesis `ci`/`nightly` profiles and an example test done (`services/sim/tests/conftest.py`); Playwright waits for the first overlay visual test (owner, 2026-10-19) |
| NX-363 | Agent build loop: `coder` and `qa` subagents, `build-loop` skill, autonomy rule (Q-DEV-1 … Q-DEV-6) | S | ✅ | — | Agents and skill committed; AGENTS.md rule 2 exception |
| NX-365 | Agent GitHub identity: a machine account or GitHub App for agents and the daily routine that is neither a code owner nor a ruleset bypass actor; move the routine and agent `gh` auth to it; then drop the interim deny rules (Q-DEV-16) | S | ✅ | — | An agent PR shows the new identity as author; `gh pr merge --admin` from it is refused by GitHub |
| NX-044 [#28](https://github.com/operation-nexus/operation-nexus/issues/28) | Owner desktop agent setup (docs/agentic/TOOLING.md §5): jq, Serena, plugins | S | ✅ | — | `/mcp` shows serena + context7 connected |
| NX-045 [#29](https://github.com/operation-nexus/operation-nexus/issues/29) | Spike: code knowledge-graph MCP (CodeGraphContext vs codebase-memory-mcp), measured vs baseline; also Serena in cloud sessions (project `.mcp.json` plus setup-script install, Q-DEV-19) | M | ⬜ | P1 code exists | Report with token and accuracy numbers; adopt/reject decision |
| NX-046 [#30](https://github.com/operation-nexus/operation-nexus/issues/30) | Data-integrity Semgrep rules + FB registry tests (DATA-INTEGRITY §6) | M | ⬜ | NX-012 | Each rule has positive/negative fixtures |
| NX-047 [#31](https://github.com/operation-nexus/operation-nexus/issues/31) | Optional: SonarQube Cloud quality gate (Q-CI-5) | S | ❓ | P2 | Decision recorded |
| NX-048 | Open GitHub issues for P0 items (labels auto-created; phases tracked as `phase:Pn` labels because the available tooling can't create milestones) | S | ✅ | owner OK | Issues #1–#32 exist and are linked here |
| NX-049 [#32](https://github.com/operation-nexus/operation-nexus/issues/32) | Create `develop` from `main` after planning sign-off; apply branch rulesets per ADR-0009; set default branch to `develop` | S | ✅ | planning done | Rulesets visible; PR to main without gates is blocked |
| NX-050 | ~~Port interfaces + `Capabilities` + conformance suite skeleton~~ Dissolved (Q-MB-3): each port, its `Capabilities` and its conformance suite land with that port's first adapter (chat in NX-190, LLM with the first P4 advisor, TTS with the first engine); the vendor rule lands with the first vendor SDK (Q-MB-2) | M | ✅ | — | Merged into those items |
| NX-311 | **Decision→spec propagation pass:** fold every ✅ decision in OPEN-QUESTIONS into the spec bodies (23 gaps listed in GAP-ANALYSIS §2), one PR per spec, P1 specs first. The docs lint that flags decided Q-IDs still described as open moved to NX-322. **Must finish before specs are marked Approved.** Done 2026-10-18 through the spec-alignment PRs #40–#52, #54–#57 and #61–#63. | L | ✅ | — | GAP-ANALYSIS §2 items all resolved |
| NX-322 | Docs lint: flag decided Q-IDs (✅ in OPEN-QUESTIONS) that a spec or planning doc still describes as open or pending (split out of NX-311) | — | ⬜ | — | A doc line that calls a decided Q-ID open fails the lint |
| NX-312 | Missing P1 docs: COMBAT spec, command and intent catalog, balance acceptance criteria (theater #1 = NX-008) | M | ✅ | NX-311 | Docs exist, reviewed |
| NX-040 [#27](https://github.com/operation-nexus/operation-nexus/issues/27) | Threat model review with owner; accept residual risks | S | ✅ | NX-001 | THREAT-MODEL §6 signed off |

---

## P1 — Sim kernel (headless)

| ID | Item | Size | Status | Depends | Acceptance |
|---|---|---|---|---|---|
| NX-345 | SIM-CORE benchmark spike (gates NX-006 approval of SIM-CORE; Q-SIM-4, Q-SIM-17, Q-SIM-18) | S | ✅ | NX-010 | On the Q-TEST-1 reference host: (1) `step` plus frame build p99 < 25 ms at 1,000 entities and 500 viewer units, with movement, sensor and combat passes; (2) the idle case (0 viewers, about 150 AI-only entities); (3) entity-storage verdict (objects, or NumPy arrays if the pass exceeds about 10 ms); (4) bytes per game hour of the redacted and the full-truth frame streams. Harness `tools/sim-bench/bench.py`; indicative Mac results in `docs/review/NX-345-BENCH.md`; reference-host run 2026-10-20, verdict objects (Q-SIM-4) |
| NX-364 | Error pipeline per ERROR-PIPELINE: `ErrorReporter` port, Sentry adapter with scrubber, `error` tickets, daily-routine triage (Q-DEV-7 … Q-DEV-10) | M | ⬜ | NX-026 | EP-2 scrub test passes; a seeded error becomes one `error` issue |
| NX-100 [#157](https://github.com/operation-nexus/operation-nexus/issues/157) | `SimRng` (PCG64, named sub-streams) | S | ✅ | NX-010 | Unit + property tests; same seed → same draws |
| NX-101 [#158](https://github.com/operation-nexus/operation-nexus/issues/158) | World model types + canonical `state_hash` | M | ✅ | NX-021 | SC-9 round-trip property |
| NX-102 [#159](https://github.com/operation-nexus/operation-nexus/issues/159) | Fixed-step runtime + inbox + canonical command ordering | M | ✅ | NX-101 | SC-6 shuffled-arrival property |
| NX-103 [#160](https://github.com/operation-nexus/operation-nexus/issues/160) | Snapshot + command log + restore | M | ✅ | NX-102 | Kill/restore integration test equal hash |
| NX-104 [#161](https://github.com/operation-nexus/operation-nexus/issues/161) | Spatial grid + benchmarks | M | ✅ | NX-101 | 1k entities p99 < 25 ms (bench) |
| NX-105 [#162](https://github.com/operation-nexus/operation-nexus/issues/162) | Golden replay framework + cross-process check in CI | M | ✅ | NX-103 | Job `sim-determinism` in `ci-gate`: required on main, advisory on develop (ADR-0009) |
| NX-106 [#169](https://github.com/operation-nexus/operation-nexus/issues/169) | Balance config loader (YAML, schema-validated, hashed) | S | ✅ | NX-101 | Invalid config rejected; hash in campaign |
| NX-120 [#175](https://github.com/operation-nexus/operation-nexus/issues/175) | Theater loader + road graph + A* | M | ✅ | NX-008, NX-106 | Paths avoid destroyed bridges |
| NX-367 [#178](https://github.com/operation-nexus/operation-nexus/issues/178) | Unit catalog loader + MVP catalog entries (`content/units/`, PROPOSED values; Q-CBT-24) | M | ✅ | NX-106 | Catalog kinds equal `UnitKind`; joins `config_hash`; GARRISON_INFANTRY GROUND only |
| NX-121 [#185](https://github.com/operation-nexus/operation-nexus/issues/185) | Kinematics (air direct, ground on graph), time scale | M | ✅ | NX-120, NX-367 | Property: positions in bounds, on edges |
| NX-122 [#187](https://github.com/operation-nexus/operation-nexus/issues/187) | Unit slots, spawn, respawn delay, reserve queue | M | ✅ | NX-121, NX-367 | GP-1..3 tests; also builds `Rules` at campaign start and in the replay CLI, makes `rules=` required in restore/recover, adds a golden case with moving units (Q-SIM-37) |
| NX-368 [#188](https://github.com/operation-nexus/operation-nexus/issues/188) | Aircraft minimum (stall) speed and idle orbit (Q-SIM-38) | S | ✅ | NX-121 | Airborne AIR never below `min_speed_mps`; land only at own-side AIRBASE/SANCTUARY (speed 0); out of fuel in the air = lost (Q-SIM-42); first `UnitDestroyed` producer; idle airborne aircraft orbit (CAP/scouting) and auto-RTB and land only at bingo fuel; positions in bounds |
| NX-370 [#192](https://github.com/operation-nexus/operation-nexus/issues/192) | `SYS_SET_CALLSIGN`: commander callsigns reach the sim; JOIN copies them (Q-SIM-39) | S | ✅ | NX-122 | Contract + handler; callsign in snapshot; UnitSpawned carries it |
| NX-371 [#194](https://github.com/operation-nexus/operation-nexus/issues/194) | Reserve queue follow-ups: `ReserveQueueLeft` events, `slots.queue_idle_min` timeout, RQ-1 milestones, ban/forget removal | S | ⬜ | NX-122 | Queue counter derivable from events; idle entries removed by a logged command |
| NX-123 | Logistics: stock, convoys, unload, starvation (factories parked, Q-GP-41) | L | ✅ | NX-121 | Conservation property; starvation loadouts. Part 1 (stock, rear source, trucks, `SupplyDelivered`) done; part 2 (forward deploy, refuel, starvation cap; Q-SIM-51, 53 to 55) in review; munitions on rearm join with NX-124 |
| NX-124 | Combat per COMBAT spec: targeting, pk model, damage, wrecks, SAM rings | L | ✅ | NX-121, NX-150, NX-367 | Damaged units slow down by `combat.damage_state.damaged_speed_mult` (Q-SIM-38); COMBAT §7 test plan passes, incl. Pk cap, range factor and the §5.1 matrix check against content; adds the min-speed clamp for damaged aircraft and the wreck and crew roll on `UnitDestroyed` (Q-SIM-43); adds aircraft altitude bands so terrain masking and the Q-FOW-3 aircraft test apply, plus `ring_m` and damage `state` on facility markers (Q-SIM-46). Part 1 (core) done; part 2 (rearm, repair, auto-RTB, crew, damaged slowdown; Q-SIM-68 to Q-SIM-70) done; part 3 (node defense HP, defeat, idle floor, fog follow-ups; Q-SIM-71, Q-SIM-72) done |
| NX-125 | Capture with contest/decay | M | ✅ | NX-121 | No double flip property; replaces the static `Rules.landing_bases` with live node ownership (Q-SIM-43); adds node owners to `SideView` and moves a facility's contacts when its base flips (Q-SIM-45); drops a side's markers of facilities it captures and discovers captured bases' facilities (FOW-13) |
| NX-126 | Campaign: objectives, momentum, win/loss, pause with a reason category (Q-ALN-3); the clock never pauses for lack of humans (Q-GD-4 amended). The automatic pauses are NX-325 | M | ✅ | NX-125 | Scenario tests per condition. In code: clock, staff pause/resume/end, coalition victory, time-limit score (Q-SIM-64), timed objectives, momentum; defeat with NX-124, idle floor with AUTO, `CampaignStarted` and extensions with their commands (Q-SIM-62, Q-SIM-63) |
| NX-150 [#198](https://github.com/operation-nexus/operation-nexus/issues/198) | FoW tiers + server-side redaction + blob clustering, last-known tracks (FOW-6a), emitters (FOW-11), spotted flag (FOW-12), masking regions | L | ✅ | NX-104 | FOW-1..3, FOW-6a, FOW-11, FOW-12 properties |
| NX-372 [#203](https://github.com/operation-nexus/operation-nexus/issues/203) | Sensing performance: one grid per sensor-range class (Q-SIM-4) | S | ✅ | NX-150 | Same results as the brute-force oracle; owner re-runs the i7 sensing bench; NumPy reopened only if a sensing tick stays above ~10 ms |
| NX-373 | Bridges: bridge HP from STRUCTURE fire, a destroyed bridge cuts its road (paths reroute), truck repair (STATE-MACHINES §4.3, Q-GD-11, Q-SIM-71) | M | ⬜ | NX-124 | B-1, B-2; convoys reroute around a cut bridge; repair numbers approved by the owner first |
| NX-374 [#220](https://github.com/operation-nexus/operation-nexus/issues/220) | Tasking Board core, pulled into P1 from NX-309 (owner, Q-SIM-73): part 1 jobs, lifecycle, leases, priorities and aging, slots and dedupe, dependencies, deterministic assignment, per-side fog, events; resupply, defend, strike, assist-objective and scout jobs; AI garrison takes jobs; parameterless `!join`; part 2 follow and escort (Q-GP-31 to Q-GP-33). Part 1 done (Q-SIM-74, Q-SIM-75); part 2 with NX-369 done (Q-SIM-76) | L | ✅ | NX-126 | TB-1 to TB-10 tests per GAMEPLAY §1b; same seed same assignments; the AI garrison never initiates offense |
| NX-376 | Worst-case tick budget: QA's 1,000-unit convoy scene (every unit tracked, ~700 followers) runs a p99 of about 31 ms with escort generation off, over the SC-10 25 ms line; profile the board pass, sensing and movement together and bring p99 under budget. Also explain the rare single-tick spikes seen in long PoL runs (one 127.8 ms tick in 6 h, NX-379 QA, not reproduced; 35 ms in NX-157 QA's 48 h run) | M | ⬜ | NX-374 | p99 < 25 ms on QA's worst-case scene in the container and an i7 re-run |
| NX-377 | Tunability sweep (Q-DEV-21): move every outcome-affecting constant in `nexus.core` into balance or content keys (e.g. the follow hold slack, the decay ratio bound, the scout cap if left in code), documented in CONFIG-AND-CONTENT, with a test that fails on new outcome-affecting literals in kernel modules | S | ✅ | NX-156 | No gameplay number lives only in code; config docs list every key |
| NX-378 | Entertainment review at P1 exit (Q-DEV-22): read long seeded balance-harness runs as each audience would see them (watcher, player, site watcher, VOD and clip watcher); report in docs/review per docs/quality/ENTERTAINMENT-REVIEW.md | S | ⬜ | NX-031, NX-032 | A report with a score, evidence and suggestions per audience; the owner has decided on each suggestion |
| NX-379 | Static recon that explores instead of feeding the air defenses (Q-SIM-87): cheaper Recon, stale-area loiter points outside known air-defense rings, route-danger check, loiter then home | S | ✅ | NX-157 | Overnight 0-viewer run: recon losses and stock burn well below NX-157's (about 14 UAVs and 70 stock per game hour) while the Static's last-known picture stays fresh |
| NX-380 | Idle armed viewers get strike work (Q-SIM-92): STRIKE slots scale with idle armed viewer units up to a cap, plus capped strike jobs on known defended foe nodes when no marked target is open; harness A4 suspended | M | ✅ | NX-031 | A2 newbie wait and idle-jet share improve on `prime-50` / 300-viewer runs; determinism + goldens |
| NX-382 | Player front-line patrol jobs (Q-SIM-94): spec in GAMEPLAY §1b, then PATROL on the coalition board | M | ⬜ | NX-380 | Idle armed or recon viewers at quiet times patrol the front; patrols never enter non-coalition nodes; no Director escalation without fire |
| NX-383 | Harness: A2 at ALPHA+ only with impact = any contribution (Q-SIM-93), mixed personas (Q-SIM-95) | M | ⬜ | NX-380 | A2 reported per the new definition; persona mix per profile in the report |
| NX-151 | Enemy-side view for director (FOW-4) | M | ✅ | NX-150 | Director API accepts only `EnemyView` |
| NX-155 | Director: CP, tiers w/ hysteresis, budget | M | ✅ | NX-151, NX-374 | Hysteresis property |
| NX-156 | Director: operations library + scoring + threat memory | L | ✅ | NX-155 | "Convoy raids → escorts" golden scenario |
| NX-369 [#189](https://github.com/operation-nexus/operation-nexus/issues/189) | Formation speed: an escorted group moves at its slowest member's speed (Q-SIM-38) | S | ✅ | NX-121, NX-156 | Property: an escorted convoy never outruns its escort; both sides; adds the min-speed clamp for aircraft in a formation (Q-SIM-43) |
| NX-157 | AI garrison + Pattern of Life + provocation-gated escalation (THREAT-DIRECTOR §5a) | M | ✅ | NX-155, NX-374 | overnight-0: no escalation, at most one node lost per 6 game hours (Q-SIM-85); 0→1 viewer: no escalation until provocation; staging visible to scouts |
| NX-158 | `!rebase` and base-to-base repositioning for both sides | S | ✅ | NX-121 | Units stage forward and refuel at the destination base |
| NX-031 | Balance harness (`tools/balance`) + bot personas + report; part 1 done (`tools/balance` runner, crowd profiles, report; Q-SIM-91), part 2 adversarial (with NX-321), part 3 nightly CI | L | 🟨 | NX-126 | Standard scenarios (crowd profiles of 0, 5, 50, 150, 300 and 500 simulated viewers plus the adversarial profiles, Q-ALN-42): 20-seed balance-diff report; the 50-seed acceptance run of TESTING-STRATEGY §3.5a (Q-TEST-4); unit speeds (`speed_mps`, `min_speed_mps`) are tuned from playtests too (Q-SIM-38) |
| NX-381 | Local harness run queue (Q-OPS-14): `tools/balance/harness_queue.py` + wrapper, hourly timer on the owner's WSL box, `harness-run` issues in, report comments out | S | 👀 | NX-031 | A labelled issue from a trusted author is run at its SHA and answered with the report; untrusted, malformed or off-`develop` requests are refused with a comment |
| NX-032 [#176](https://github.com/operation-nexus/operation-nexus/issues/176) | Replay CLI + measured storage size | S | ✅ | NX-103 | Size documented in CLIPS-REPLAY |
| NX-033 | Headless soak (6h) in nightly | M | ⬜ | NX-016 | No memory growth; hashes replay |
| NX-301 | Track fade (FOW-6 only; FOW-6a is in NX-150), later phase behind a feature flag (Q-PROD-8, Q-ALN-20) | — | ⬜ | NX-150 | Tracks age back into SIGINT blobs over time after the scout dies or leaves (FOG-OF-WAR) |
| NX-304 | Objective modes: timed / off per campaign (Q-GD-19 blocks P1; moved from P4 in NX-311) | — | ✅ | NX-126 | O-1 invariant per mode (STATE-MACHINES §4.5). Done in NX-126 (`campaign.objective_mode` timed/off, O-1 tested per mode) |

## P2 — Closed alpha (Twitch, unlisted)

| ID | Item | Size | Status | Depends |
|---|---|---|---|---|
| NX-170 | WS server: Hello/Welcome/Snapshot/Delta/Hud, bounded queues | L | ⬜ | NX-150 |
| NX-171 | Delta encoder + size budget test | M | ⬜ | NX-170 |
| NX-175 | Overlay scaffold, layered canvases, reconnect, banners | M | ⬜ | NX-170 |
| NX-176 | Terrain contour pre-render + nodes/roads/bridges | M | ⬜ | NX-175 |
| NX-177 | Units (shape-coded), rings, blobs, tracers, interpolation | L | ⬜ | NX-176 |
| NX-178 | HUD: momentum, objective, threat, ticker, rotating panels | M | ⬜ | NX-175 |
| NX-182 | Map annotation layer (OVERLAY §2a): sectors, optional grid reference, direction cues, ephemeral pins, circles and arrows with TTL and collision handling | M | ⬜ | NX-177 |
| NX-179 | PiP 2D intercept scope + PiP director scoring | M | ⬜ | NX-177 |
| NX-180 | Palette/colorblind script + visual snapshot tests | M | ⬜ | NX-177 |
| NX-190 | Gateway: `ChatSource`/`ChatSink` ports + `Capabilities` + conformance suite skeleton (from NX-050, ADR-0010 N-3/N-4) + normalization + rate limits | M | ⬜ | NX-021 |
| NX-191 | Twitch EventSub adapter + moderation event sync + batched replies | L | ⬜ | NX-190 |
| NX-192 | Command parser + grammar + fuzz tests, with fuzzy callsign matching and the always-answer feedback rule (Q-SIM-77); the parser's unit orders (`!target`, `!rtb`, a `!join` role switch) clear a unit's `HOLD` order, the only way out of a hold after `!rebase` today (NX-158 QA) | M | ⬜ | NX-190 |
| NX-193 | Viewer simulator (`tools/chatsim`): scripted bot operators (personas from the balance harness) sending real chat-shaped commands through the LocalSim adapter; runnable against staging for long tests during viewer droughts. Bots are always labeled as simulated and never counted as humans (DI-5). Never on the public channel: commands go straight into the internal command queue, and the simulator refuses to start when config targets the production channel (Q-LEGAL-7). | M | ⬜ | NX-190 |
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
| NX-255 | Production compose + host supervision (Windows/WSL2 per ADR-0012, Q-OPS-7; systemd on the Linux server) + host provisioning doc | M | ⬜ | NX-014 |
| NX-256 | Runbooks (deploy/rollback, restore, moderation incident, outage) | M | ⬜ | NX-255 |
| NX-325 | Automatic pauses: offline auto-pause with the "COMMS RESTORED" resume, weekly maintenance window and its scene, owner Ceasefire mode (one click or hotkey), staff pause sub-reasons and the "PAUSED — stand by" banner (OPS-ADMIN OA-5…OA-10b; Q-OPS-8, Q-OPS-9, Q-ALN-3, Q-ALN-31, Q-ALN-32) | — | ⬜ | NX-126, NX-253 |
| NX-042 | Phase-2 security review + pentest of command path | M | ⬜ | all P2 |
| NX-034 | Cold-tester readability study (a few cold testers, not strictly 5; Q-PROD-4). Also test: hidden-shooter tracers on/off (Q-CT-3), recruit strip + `!me` clarity (FB-UX), orientation | S | ⬜ | NX-178 |
| NX-035 | Multi-day unattended burn-in on unlisted stream (not strictly 7 days; minimal manual fixes; zero unmoderated text; monitoring + viewer simulator NX-193 in use; Q-PROD-4) | M | ⬜ | all P2 |
| NX-309 | Tasking Board: job generation from state, priorities, role matching, slot de-dup, AI garrison integration, overlay "NEEDED" list, auto-tasking on a parameterless `!join` (Q-GP-23), `hold` opt-out (Q-GD-26 blocks P2; moved from P4 in NX-311) | — | ⬜ | NX-126, NX-178. The kernel core moved to NX-374 (P1, Q-SIM-73); this item keeps the overlay NEEDED list and the chat-facing parts |
| NX-324 | Silent viewers: idle handoff to an AUTO unit, idle retire, reclaim; an AUTO unit keeps its commander's slot; AUTO tag on the overlay (GAMEPLAY §4b GP-4…GP-6; Q-GD-35, Q-ALN-8, Q-ALN-9, Q-ALN-25, Q-ALN-26) | — | ⬜ | NX-122, NX-309 |
| NX-274 | Brand and style guide: name usage, fictional factions and insignia, unit class naming (generic: Tank, Striker, Bomber…), color, type, sound identity, tone of voice; **no real names** rule added to the content validator. Includes rank display names (Q-NAME-1), unit class names (Q-NAME-2), colors (Q-STYLE-1), typography (Q-STYLE-2), symbology (Q-STYLE-4). (Overlay needs it in P2; moved from P4 in NX-311.) | — | ⬜ | — |
| NX-366 [#174](https://github.com/operation-nexus/operation-nexus/issues/174) | Architecture and service-layout document: module boundaries, queues/APIs between them, which modules can split into their own process or container; checked against the import contracts (owner request, #119) | S | ⬜ | NX-014 |

## P3 — Public beta

| ID | Item | Status |
|---|---|---|
| NX-375 | Configurable sides (owner, 2026-10-22): a campaign setting for which side chat plays, an AI Director per side (agent vs agent), symmetric or per-campaign win rules, objectives, idle protection and quiet multiplier, and a mirrored theater layout; agent vs agent is also a balance-harness and soak-test mode (NX-031, NX-033). Chat vs chat (team assignment and balancing) is a later step | ⬜ |
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
| NX-326 | Mastermind taunts: template-only lines before P4, code-filled `{target}` callsign naming with real-time cooldowns, `!quiet` toggle (opt-out wins on merge), the Hum before every Static transmission (THREAT-DIRECTOR §6b, AUDIO-TTS AU-6/AU-7, CHAT-GATEWAY CG-4; Q-AI-7, Q-ALN-12, Q-ALN-28, Q-BRAND-4). Phase not set by any decision: owner to confirm | ❓ |

## P4 — Depth

| ID | Item | Status |
|---|---|---|
| NX-212 | Ranks O-4..O-6, specialist chassis (SEAD, jammer, engineer, AWACS, artillery); acceptance: the reserved `SPAWN_SPECIALIST` command gets its schema, parser and handler (Q-CMD-2), the jamming Pk factor replaces its FB-6 1.0 | ⬜ |
| NX-362 | Countermeasures (chaff/flares, one-shot per load) and radar lock as Pk factors; acceptance: both replace their FB-6 1.0 fallback (COMBAT §5.2, Q-CBT-20) | ⬜ |
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
| NX-263 | Game Master takeover: ASSIST first, FULL in the next release (Q-TD-9; owner wants FULL soon) + on-stream badge | ⬜ |
| NX-264 | Theater library: upload, validate, preview, publish | ⬜ |
| NX-265 | Procedural theater generation (water-heavy archetypes, west→east) | ⬜ |
| NX-266 | Two-person rule and approvals | ⬜ |
| NX-267 | SupportSource port + conformance suite | ⬜ |
| NX-268 | Twitch channel points redemptions (create rewards, fulfill/refund) | ⬜ |
| NX-269 | Twitch Bits + subs (gift de-dup) + Hype Train v2 | ⬜ |
| NX-270 | YouTube Super Chat/Sticker/membership ingest | ⬜ |
| NX-271 | Redemption rules engine + forbidden-effect validator | ⬜ |
| NX-275 | Lore bible + campaign narrative: why we fight, who the enemy is, the season and global campaign arc, mission briefings; feeds sitrep templates and the global map (future) | ⬜ |
| NX-276 | Community health design: positive-only feedback (no kill-shaming), cooperative and role-based leaderboards (no single "top killer"), friendly tone in all bot text, code of conduct, mod tools (ADMIN-RBAC), no PvP between viewers | ⬜ |
| NX-277 | Layered anti-farming without captchas: (1) platform account age, if the platform API exposes it [VERIFY: Twitch Get Users `created_at`; YouTube channel `publishedAt` costs quota]; (2) our own first-seen age; (3) first-completed-mission gate; (4) hourly diminishing XP; (5) admin-console anomaly flags (many new accounts acting in lockstep); (6) mod tools to void XP | ⬜ |
| NX-278 | Voice cast listening session: pick an engine voice, filter and pacing per profile; set the sitrep cadence | ⬜ |
| NX-279 | Post-war reveal: "what you didn't see" recap (summary + optional narrative) with a decision-source label per enemy action (RULES / ADVISOR / GAME_MASTER), plus the seed published; shown in the AAR and on the replay site | ⬜ |
| NX-280 | Balance experiment: fuel for all domains (big ground and sea tanks, slower burn, "crawl when dry") vs air-only, run as a harness A/B plus a playtest | ⬜ |
| NX-281 | Rescue and refuel missions (future, tied to NX-280): a stranded ground or logistics unit can end its sortie or wait for rescue, and operators can mount a rescue or refuel run. Air-to-air refueling (tanker unit) for combat air patrols in safe airspace. Aircraft that run dry crash. | ⬜ |
| NX-283 | Hot-loadable unit content pipeline: per-unit YAML, validators (incl. no-real-names and stat envelope), `STAFF_CONTENT_LOAD`, admin form | ⬜ |
| NX-284 | `new-unit` agent skill + tool-agnostic prompt: plain-language description → validated draft → approval | ⬜ |
| NX-285 | Backups: `BackupTarget` port with local (Linux server) + Google Drive (owner has access) adapters, age encryption, tiered retention (DB/snapshots nightly; replay/telemetry archives separately), quarterly restore test; verify provider limits first | ⬜ |
| NX-286 | Pause flow: reason form, owner alert with state summary, optional AI assessment, one-tap resume (alert link / Discord / console), re-alert | ⬜ |
| NX-287 | Research: Gemini TTS synthetic voice design/generation (capabilities, pricing, rate limits, terms, commercial use on streams) for voice-cast profiles via the `TtsEngine` port; cost vs the $20/mo cap | ⬜ |
| NX-288 | Platform AI-content compliance: verify Twitch and YouTube synthetic-media and AI disclosure rules now and at every phase gate; apply labels, channel panel note | ⬜ |
| NX-289 | Human voice lines pipeline: owner or community voice actors record lines from the sitrep template list, with a consent and license agreement per contributor; recorded lines plug into the voice cast as a `TtsEngine`-compatible source | ⬜ |
| NX-290 | Disabled state, crew survival roll, downed-crew markers, CSAR missions (`!rescue`), recovery of disabled vehicles, **field repair of Disabled units by the engineer specialist** (Q-CBT-14), rescue XP bonus | ⬜ |
| NX-291 | Conduct system: disruptive-pattern detectors, decaying conduct score, escalation ladder (warn → restrict → timeout → XP penalty → mod review), appeals, mod dashboard; never auto-ban | ⬜ |
| NX-292 | AI evaluation harness: golden question/answer sheets per AI use (narration, advisor, `!order` intent parsing, moderation), schema and command-format validation, intent accuracy scoring, latency/cost per call; runs any provider (hosted or local) through the same port so models can be compared before adoption | ⬜ |
| NX-293 | Field Manual: quick-start guide + advanced operations guide (site pages, optional PDF/video), linked from stream descriptions, panels and `!guide`; generated from the command catalog so it never drifts | ⬜ |
| NX-294 | Global campaign map spec: fictional world graph of theaters, progression and branching rules, narrative hooks per theater, carry-over integration, season arcs, admin tools to add theaters. **Live-service world (owner, 2026-10-17; inspired by liberation-map style games):** the world map changes between and during campaigns. The Static launches counter-offensives (AI- or GM-induced, labeled as such), a lost campaign leads to defense narratives (Hold the Line on our territory), and community progress is tracked on a public world map | ⬜ |
| NX-295 | Leaderboard moderation: remove banned or cheating operators from all boards (hide + recompute, audited) | ⬜ |
| NX-296 | AAR + War Briefing: full AAR screen; short briefing card looping between wars; auto-published to site and Discord (via `ChatSink`/`CommunityBot` ports); data-only content (no invented text) | ⬜ |
| NX-297 | Brand accounts setup: new Twitch/YouTube/TikTok/Instagram profiles + handles (check availability), Epidemic Sound plan decision (upgrade vs separate subscription; ask support about coverage after cancellation), Discord re-brand | ⬜ |
| NX-298 | Scheduled post queue: approved clips/devlog posts scheduled per platform from the Command Center (phone-friendly). Uploads stay manual or private until platform audits pass (ADR-0008). | ⬜ |
| NX-299 | Create the private `operation-nexus-ops` repo; set up sops+age, enroll machine keys, document rotation (ties to NX-027) | ⬜ |
| NX-300 | Observability on the Linux server: Prometheus + Grafana + Loki via compose; stream-health dashboard; alert rules → ntfy/Discord | ⬜ |
| NX-302 | Target handoff for long-range strikes (FOW-7) | ⬜ |
| NX-303 | Base upgrades via surplus supply (GAMEPLAY §5a). The node tier/modifier layer is in the MVP world model. | ⬜ |
| NX-305 | Assault Helicopter class ("Lifter" variants): troop landing, airfield/island capture, short range | ⬜ |
| NX-306 | Isolated-base logistics: air drops, sea ferries, engineer bridging, helicopter airlift (Q-GD-21) | ⬜ |
| NX-307 | Icon system: category-based auto-generated symbols, custom SVG upload with sanitization, playtest symbol readability; animated icons later | ⬜ |
| NX-308 | Survivor reward: eligibility check (alive + ≥1 completed mission), ribbon, merit bonus, next-war forward-base first deploy | ⬜ |
| NX-310 | World events system: event catalog (data-defined like units), rotation, timing, strength, rewards/consequences, manual start/stop, scheduling, on-stream labeling | ⬜ |
| NX-313 | Missing P2 docs: Tasking Board spec, brand/style guide (NX-274, now in P2), minimal lore bible, overlay layout v2 + 9:16 wireframes, sitrep template catalog, viewer-simulator spec, deployment-topology ADR (Windows/WSL2 + Linux server; drafted as ADR-0012 in NX-311, awaiting owner acceptance), alpha playtest plan, AAR/briefing/reveal spec | ⬜ |
| NX-314 | Missing P3/P4 docs: conduct spec + community rules, public site spec, seasons/leaderboards spec, privacy notice, analytics definitions, global map + carry-over spec, world events catalog | ⬜ |
| NX-315 | Unified naming conventions + glossary pass: one canonical term per concept across specs, config keys, contracts, commands and UI (e.g. Operator/commander, Merit/XP, sortie/mission, Static/enemy); update GLOSSARY.md and add a naming-convention section (case style per layer: config keys, enums, events, commands). Owner runs a grill-me pass to settle disputed terms. Done 2026-10-18: GLOSSARY.md and NAMING-CONVENTIONS.md; the grill pass is NX-323 | ✅ |
| NX-323 | Owner grill pass on the naming conflicts in NAMING-CONVENTIONS §3 (Operator overload, commander vs Operator, lore names in mechanics docs, two decision windows, Held/Hold the Line, rank names, sortie vs mission, event and enum case), then one rename pass across specs, config keys and contracts (split out of NX-315). Best done before NX-021 generates contract types. Settled 2026-10-18: Operator overload (Q-ALN-40), rank names (Q-ALN-41) | ⬜ |
| NX-316 | Legal pages for site/portal: privacy notice, terms of service, cookie banner (only if any non-essential cookie exists). Must list: first-party-only analytics and no third-party trackers (Q-DM-3), data retention (SEC-DATA-4), `!forget` deletion (SEC-DATA-3), what is stored per commander, platform data received via official APIs. Links into NX-204 and NX-314 | ⬜ |
| NX-317 | Static lieutenants: director personality profiles (data-defined presets), per-sector assignment, intel identification flow (UNIDENTIFIED → revealed via recon/captured comms), briefing integration, per-lieutenant taunt voice; parity rule applies (Q-GD-38) | ⬜ |
| NX-318 | Asset provenance register + CI release gate: manifest per asset (path, source, author, license, ai_generated, status placeholder/final); validator in CI; release builds fail on ai_generated or placeholder assets; on-stream PLACEHOLDER disclosure during alpha (Q-BRAND-5) | ⬜ |
| NX-319 | Art plan: 'artists wanted' notes (README, site, Discord), commission brief + budget question for owner, owner art toolkit guide (free tools, templates, style-guide checklist), replacement schedule for placeholder art before release (Q-BRAND-5) | ⬜ |
| NX-320 | Public identity migration to saltyseraphcodes (Q-LEGAL-6, Q-LEGAL-8): repo home decided by Q-LEGAL-8 (a GitHub organization owned by saltyseraphcodes now; a fresh-start repo with one clean import commit before public launch), update CODEOWNERS, tracker issue links and badges, set commit identity to the new account's noreply address on all machines and agent sessions, decide on history of earlier commits; dedicated project email | ⬜ |
| NX-321 | Playtest + harness reporting (Q-TEST-2/3): player personas (newcomer, casual, tactician, logistics main, lurker, mobile viewer) and adversarial bot profiles (troll-swarm, spammer, alt farmer, griefer, raid wave) in the balance harness; per-run report (config hash, target pass/fail, charts); written analysis summary for the owner after each playtest/harness batch; watchable replay of any run in the overlay at selectable speed | ⬜ |
| NX-273 | Research + spike: Epidemic Sound license coverage for 24/7 streams/clips; API/MCP availability; `MusicSource` port so an agent can search and queue licensed tracks by mood (tension-driven, AUDIO-TTS §1) | ⬜ |
| NX-272 | Third-party tips adapter (Ko-fi or Streamlabs/StreamElements; Q-SUP-3) | ❓ |

### Brand, marketing, community and legal (research session, 2026-10-18)

| ID | Item | Size | Status | Depends |
|---|---|---|---|---|
| NX-328 | Brand Ops spec: monitoring and review service for the public presences; draft in `docs/specs/BRAND-OPS.md`, then owner review (Q-MKT-5) | S | ⬜ | NX-297 |
| NX-329 | Auto-moderator: review `docs/review/AUTOMOD-AND-PRIVACY-ANALYTICS-RESEARCH.md`, choose build/compose, write the spec (reject/delete/timeout/ban ladder, reversible, logged, never auto-ban from the conduct score; Q-MOD-8) | M | ⬜ | NX-291 |
| NX-330 | Privacy-preserving analytics (owner chose 2026-10-22: no web-stats tool, keep Q-DM-4; attribution by the Discord onboarding question, weekly check-in skill in the vault): pick the cookieless web-stats tool for the public site, define dashboards and minimum cohort sizes, privacy-notice wording (Q-DM-3, Q-DM-4; ties NX-036, NX-316) | S | ⬜ | NX-329 |
| NX-331 | Marketing and lore agent teams: private lore-vault repo, owner-written bible and tone guide, pilot (P3), scheduled loop (P4); design in `docs/planning/AGENT-TEAMS.md` (Q-MKT-8, Q-AI-10) | L | ⬜ | NX-294, NX-317 |
| NX-332 | Epidemic Sound: send the written 24/7 questions; decide between it, CC0/free-license music and commissioned music for the alpha (extends NX-273, NX-297; Q-LEGAL-10). Owner reported 2026-10-22 that 24/7 use is fine; the answer's source and the VOD-archive and lapse answers are not yet recorded | S | 🟨 | — |
| NX-333 | Platform policy verification pass: read the primary Twitch, YouTube, TikTok, Instagram and Discord policy pages from the prepared checklist, record findings (needs a local session or a network allowlist, Q-PROC-3) Agent pass done 2026-10-18 (`docs/review/PLATFORM-POLICY-VERIFICATION-2026-10-18.md`): 44 of 75 claims verified, 16 still need a browser (its section 5). | S | 🟨 | — |
| NX-334 | Moderator program: recruit 2-3 mods from the owner's trusted team, mod guide, volunteer/assigned chat-watch slots, conflict-of-interest rules for mods who play, pay question for an accountant (Q-MOD-7). Owner is adding the first moderators to the Discord (2026-10-22) | M | 🟨 | NX-291 |
| NX-335 | Legal housekeeping: LICENSE holder, `assets/LICENSE`, `TRADEMARKS.md`, DCO, license allowlist update (PSF-2.0, BlueOak-1.0.0), CI license scan (Q-LEGAL-10; LICENSE holder before the Q-LEGAL-8 fresh-start import) | S | ⬜ | NX-320 |
| NX-336 | Brand setup runbook: manual account creation and verification per platform, passkey and mailbox hygiene, setup log template for the private ops repo, handle reservation (Hiveplex plus the studio byline handle; Q-MKT-5, Q-MKT-7); extends NX-297 | S | ⬜ | NX-299 |
| NX-337 | Marketing backlog triage: accept or drop MKT-1..MKT-19 from `docs/review/MARKETING-AND-PRODUCTION-RESEARCH.md` §7 into this tracker | S | ⬜ | — |
| NX-338 | Vault scaffold (private repo `operation-nexus-vault`): structure, `AGENTS.md`, `CLAUDE.md`, house skill standard, Vale config, front-matter checker; owner sets the vault ruleset and `maintainers`-only access (Q-MKT-14, Q-MKT-15) | M | ✅ | NX-337 |
| NX-339 | First marketing skills with test cases (3 minimum, 5 preferred) run on their claimed model tier: `devlog-outline`, `social-post-draft`, `clip-package`, `style-check` (Q-MKT-15) | M | ✅ | NX-338 |
| NX-340 | Voice interview and voice brief: about 15 questions, 3 drafts the owner rewrites, ban list and examples file; repeat monthly for a quarter (Q-MKT-15) | S | 🟨 | NX-338 |
| NX-341 | Local production scripts in the vault (ffmpeg clipping, whisper transcripts, caption files) the owner runs on a desktop; text outputs committed for cloud agents (Q-MKT-14) | M | ⬜ | NX-338 |
| NX-342 | Scheduled weekly drafting run (max 5 drafts, one vault PR, no platform credentials) and the weekly metrics note (Q-MKT-14, Q-AI-10) | S | ⬜ | NX-339 |
| NX-343 | Service context pack: export of voice summary, `RELEASED` lore and campaign facts from the vault for read-only use by services; shared libraries and event feed (Q-OPS-11, BRAND-OPS §4.3) | M | ⬜ | NX-328, NX-338 |
| NX-344 | Primary-source read of Reddit and Discord self-promotion and bot rules; record findings in `docs/review/` (Q-MKT-15). Partly done 2026-10-19 (`docs/review/PLATFORM-RULES-REDDIT-DISCORD-2026-10-19.md`): Reddit Content Policy and Data API Terms and Discord Community Guidelines read; Discord Developer Policy and Terms and Reddit's help articles still unread (HTTP 403: owner reads in a browser, or allowlist the hosts, Q-PROC-3) | S | 🟨 | — |
| NX-361 | Meme desk: design with the owner (grill), then pilot as a content-time agent in the vault that proposes current meme and programmer-humor angles for owner-approved posts (Q-MKT-16) | M | ⬜ | NX-339 |
| NX-346 | NULL meme-flavored template lines: mechanism decided (Q-MKT-17); implement with NX-326 and the no-real-world-references rule (Q-MKT-17) | S | ⬜ | NX-326 |
| NX-347 | Contributor license template (draft v0 written 2026-10-19 in `docs/legal/CONTRIBUTOR-AGREEMENT-TEMPLATE.md`; owner decisions D1 to D12 and the attorney review remain) (flat fee, contributor keeps copyright, project license, no voice training or cloning, credit) and one narrow attorney review before the first paid use (Q-LEGAL-13; ties NX-289) | S | 🟨 | — |
| NX-348 | Credits page on the site and in the stream's about section; alias and removal-on-request rules (Q-LEGAL-13) | S | ⬜ | — |
| NX-349 | Draft account profile copy (bios, link-page text) for each brand account, in the vault; the owner approved all eight on 2026-10-18 and pasted seven into the profiles by hand on 2026-10-19; the link-page draft is posted at hiveplex.live; site-link bio updates are drafts MKT-0011 to MKT-0014 in the vault (Q-MKT-14) | S | ✅ | NX-340 |
| NX-351 | Link page for hiveplex.live: spec `docs/specs/PUBLIC-SITE.md` (Approved 2026-10-19), built under `apps/site/` (concept B, `scripts/check_site.py`, `.github/workflows/pages.yml`); live at https://hiveplex.live/ since 2026-10-19 (GitHub Pages, custom domain, HTTPS enforced by the owner); copy is the approved vault draft MKT-0008 with the Discord invite; follow-ups are NX-357 (#116) (Q-MKT-18) | S | ✅ | NX-352 |
| NX-352 | Placeholder logo and avatar: concept C3 (signal break) chosen by the owner on 2026-10-19; master SVG, avatar, icon and banner and the provenance record are in the vault; the owner sets the avatars and banners by hand (AI-assisted placeholder, status `placeholder` per NX-318), then a human-made replacement when the budget allows (Q-MKT-18, Q-LEGAL-13) | S | 🟨 | — |
| NX-353 | Discord server setup: spec `docs/specs/DISCORD-SERVER-SETUP.md` (Approved 2026-10-19) and the blueprint in `tools/discord-setup/`; no bot token in any session or repo (Q-OPS-12) | S | ✅ | NX-352 |
| NX-354 | Discord setup tool `tools/discord-setup/` (spec Approved 2026-10-19): stdlib only, dry run by default, idempotent, owner-run with a throwaway token, sends no messages, tests in `make check` and CI (Q-OPS-12). Run by the owner | M | ✅ | NX-353 |
| NX-355 | Make docs easy to find: a "Find it fast" task table in the root README and in the vault README, and bring `docs/README.md` back to listing every file under `docs/` (owner request 2026-10-19) | S | ✅ | — |
| NX-356 | Review marketing drafts by PR comment in the vault: the owner comments `/approve` or `/reject <id> <reason>`; a workflow records status and date, runs the checks and merges (Q-MKT-19). Live on 2026-10-22: `/approve` approved drafts on a real PR. Follow-up `/merge` for content-only PRs is vault PR #28 (Q-MKT-19) | S | ✅ | NX-342 |
| NX-357 | Link page follow-ups: `www` certificate, link previews on Discord and Bluesky, Instagram and Reddit links opened by hand (#116) | S | ⬜ | NX-351 |
| NX-358 | Daily owner check: a scheduled session (about 8 AM US Eastern) reads new owner comments and assignments in the public repo and the vault, acts on small asks through a PR, and reports on issue #119; it never merges, approves or posts to a platform. First run 2026-10-20 still to be checked (#119) | S | 🟨 | NX-356 |
| NX-359 | Discord community stage in `tools/discord-setup/`: open layout (+ #off-topic), `--community` (Community feature, rules and updates channels, notifications, welcome screen, onboarding with an Operator option) and `--post-text` for the welcome and rules text; spec DS-11 to DS-14, tests with the fake HTTP layer, security review (Q-OPS-13). Server set up by the owner; welcome and rules reposted by hand on 2026-10-22 after the setup bot was deleted | M | ✅ | NX-354 |
| NX-360 | Discord rank roles from global merit, XP and rank (linked roles preferred, or a role-sync bot); proposal only until account linking and real ranks exist (PROGRESSION section 8, Q-OPS-13) | S | ⬜ | NX-359 |
| NX-350 | `meme-brief` skill (on demand): owner's weekly examples to source-dated format ideas and drafts, tests on its tier (Q-MKT-16) | S | 🟨 | NX-339 |

## Backlog (unscheduled — from owner's conversation & plans)
- **Global campaign map (owner vision, 2026-10-17):** a fictional world (not Earth) made of connected theaters forming a progression. Each campaign is one theater; winning pushes the front to the next connected theater (cross the mountains → urban assault; win the ocean battle → land on the mainland, which is more land than water; reach the Static's "secret base"). The map is finite but large, and new theaters can be added indefinitely (hand-made or generated). It ties together seasons, carry-over (Q-GD-12), lore (NX-275) and theater rotation (Q-SM-4). Needs its own spec (NX-294).
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
