# Decided questions: Q-ARCH

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Architecture

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-ARCH-1 | Modular monolith vs microservices? | **Modular monolith** (ADR-0001). | ✅ 2026-10-17: Modular monolith (A, ADR-0001 accepted) |
| Q-ARCH-2 | Database? | SQLite (WAL) in P1–P2. Move to Postgres when a second writer process appears (ADR-0003). | ✅ 2026-10-17: Accepted via ADR-0003: SQLite (WAL) now; Postgres when a second writer appears |
| Q-ARCH-3 | Languages: Python sim + TypeScript overlay? | Yes. (Revisit if the sim tick exceeds its budget at target scale. NumPy first, then Rust via PyO3 for hot loops.) | ✅ 2026-10-17: Python sim + TypeScript overlay (A) |
| Q-ARCH-4 | Local LLM on the broadcast machine? (See [LOCAL-VS-API-COST](../ops/LOCAL-VS-API-COST.md) R2: free narration-only experiment on the gaming-PC GPU, a GTX 1070.) | **No.** Use a hosted flash-tier model or a separate machine. | ✅ 2026-10-17: A, free experiment on the gaming-PC GPU (narration first, auto-disabled if stream quality suffers). Extend to other AI experiments, all gated by a **quality benchmark** (NX-292) |
| Q-ARCH-5 | Renderer: Canvas2D or Pixi.js? | Canvas2D with layered canvases first. Pixi if profiling shows >8 ms/frame (ADR-0005). | ✅ 2026-10-17: Accepted via ADR-0005: Canvas2D first, Pixi only if profiling needs it |

## From the detailed system specs (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-ARCH-6 | Accept the ADR-0003 amendment: XP and merit become append-only, idempotent ledgers (source of truth) with `commander_stats` derived in the same transaction, replacing `UPDATE … SET xp = xp + ?`? | Accept. Prevents double-counting after crash replay and gives an audit trail. | ✅ 2026-10-17: Accepted: XP/merit are append-only ledgers (ADR-0003 amendment) |

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-ARCH-7 | One website or several for replays/stats vs admin/moderation/missions/content? | **Two apps, one codebase.** (1) **Public site**: replays, leaderboards, stats, later player login and account linking; public, read-mostly, contains **no** admin features. (2) **Command Center** (admin console): moderation, users, AI/GM, campaign/mission planning, rules, content creation; **private** (tailnet + Discord, Q-RB-4), separate login, separate deployment. They share a design system and contracts but use separate APIs, so a public-site bug can't reach admin powers. | ✅ 2026-10-17: A, two apps (public site + private Command Center), one codebase |
| Q-ARCH-8 | Linux server OS is Ubuntu 16.04/18.04 (out of standard support) | **Fresh install of Ubuntu 24.04 LTS** before using it for watchdog, staging or backups. Old OS = unpatched security holes and old Docker. Back up anything on it first. | ✅ 2026-10-17: A, move to Ubuntu 24.04 LTS. Note: a fresh install usually needs physical access (USB). Upgrading in place over SSH means chained release upgrades (one LTS at a time), which is riskier: back up first and keep console access available **Amended by owner 2026-10-26: Ubuntu 26.04.1 LTS is accepted and preferred**; the server was rebuilt on it 2026-10-25 (docs/ops/HARDWARE.md) |
| Q-ARCH-9 | Kubernetes/K3s now? | **No** (ADR-0006): Docker Compose on each box. Revisit only at the SYSTEM-DESIGN §7 triggers. | P0 | ✅ 2026-10-17: Owner open to K3s if needed; stays No until a trigger is hit |
| Q-ARCH-10 | Secrets storage | sops + age (per-machine keys), file in a separate private ops repo | P0 | ✅ 2026-10-17: A. Secrets encrypted with sops+age to each machine's public key (gaming PC, Linux server, owner laptop, deploy CI). The encrypted file lives in a **private ops repo** (`operation-nexus-ops`), not the public code repo. Rotate on machine loss; GitHub Environment secrets only hold what CI needs. |
| Q-ARCH-11 | Observability stack | Self-hosted Prometheus + Grafana + Loki on the Linux server; external dead-man's switch stays (MONITORING-WATCHDOG L3) | P2 | ✅ 2026-10-17: A |
| Q-ARCH-12 | Command Center login | Passkeys (WebAuthn) for owner/admins; Discord OAuth for moderators later (verified role mapping); reachable only via Tailscale | P2 | ✅ 2026-10-17: A |
| Q-ARCH-13 | Sim language and performance path | Python + measure; Rust only if desperately needed | P1 | ✅ 2026-10-17: A. Python (NumPy where profiling shows it helps). Escalation order: optimize → scale hardware → Rust hot spots only if truly necessary. The overlay's interpolation/dead reckoning (ADR-0005) smooths lower server rates. |
| Q-ARCH-14 | Build order after the skeleton | 1) CI + security (NX-011, NX-012, NX-020, NX-046) 2) contracts pipeline (NX-021) 3) ports + conformance suite (NX-050), then sim kernel (P1) | P0 | ✅ 2026-10-17: A |
| Q-ARCH-15 | Update delivery | Signed images; staging auto-deploys to the Linux server; production on owner tap-approve with auto-rollback; Tailscale, no open ports (ADR-0006) | P2 | ✅ 2026-10-17: A. Windows host note: the deploy script runs inside WSL2 (Docker Desktop), and OBS stays native on Windows (controlled via obs-websocket) |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-ARCH-16 | Public site hosting and data path; does it force Postgres? | static export at campaign end; stay on SQLite | ✅ 2026-10-18: Now: static public site fed by one-way exports from the broadcast host (leaderboards/stats JSON every ~15 min, configurable; full campaign archive at campaign end) pushed to a free static host (free-tier limits [UNVERIFIED]); no inbound path to the home network; stay on SQLite. Later (owner intent): move to a live interactive site with its own API + database, which triggers the ADR-0003 Postgres revisit and a separate security review. |
