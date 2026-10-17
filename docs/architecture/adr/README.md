# Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith.md) | Start as a modular monolith | Accepted |
| [0002](0002-deterministic-sim-kernel.md) | Deterministic fixed-step sim kernel (10 Hz) | Accepted |
| [0003](0003-persistence.md) | In-memory state + snapshot/log; SQLite durable store | Accepted |
| [0004](0004-toolchain.md) | Toolchain & languages | Accepted |
| [0005](0005-overlay-renderer.md) | Canvas2D overlay first | Accepted |
| [0006](0006-deployment-single-node.md) | Single-node Compose deploy over Tailscale | Accepted (amended by 0012) |
| [0007](0007-llm-role.md) | LLMs advise and narrate; rules decide | Accepted |
| [0008](0008-platforms.md) | Twitch → YouTube → Kick; TikTok deferred | Accepted |
| [0011](0011-support-redemptions-no-currency.md) | Support events → capped redemptions; no in-game currency in v1 | Accepted |
| [0010](0010-platform-and-provider-neutrality.md) | Platform and provider neutrality (ports and adapters, conformance suite) | **Accepted** |
| [0009](0009-branching-strategy.md) | `develop` for integration, `main` for verified releases | **Accepted** |
| [0012](0012-deployment-topology.md) | Deployment topology: Windows/WSL2 broadcast host + Linux ops server (amends 0006) | Proposed |

Only the owner moves an ADR from Proposed to Accepted. Use [`0000-template.md`](0000-template.md) for new ones.
