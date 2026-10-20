# ADR-0010: Platform and provider neutrality (no lock-in)

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17
- Related: ADR-0001, ADR-0007, ADR-0008, CHAT-GATEWAY, LLM-ADVISORS, AUDIO-TTS, IDENTITY

## Context
The owner's goal: Twitch **and** YouTube are both first-class targets, and the chat and Discord bots must be generic and modular. We must never be locked into one streaming platform, one LLM or TTS provider, or one AI coding agent.

## Decision
Use **ports and adapters** everywhere the system touches an outside vendor. Core code depends only on our own interfaces (ports) and our own contracts. Vendor code lives only inside adapters.

| Port (our interface) | Adapters planned | Lives in |
|---|---|---|
| `ChatSource`: receive messages and moderation events | Twitch (EventSub), YouTube (streamList), Kick (optional), **Discord** (optional command channel), `LocalSim` (dev chat simulator) | `nexus.gateway.adapters.*` |
| `ChatSink`: send batched replies or digests | the same platforms, each honoring its own limits | same |
| `CommunityBot`: Discord-style community features (roles, announcements, OAuth link help) | Discord first; the interface allows others | `nexus.community.adapters.*` (P5) |
| `IdentityProvider`: OAuth proof of account ownership | Twitch, Google/YouTube, Kick, Discord | link portal (P3) |
| `LlmClient`: structured completion with schema, deadline and budget | provider SDKs (Anthropic, Google, OpenAI), local llama.cpp/Ollama, `FakeLLM` for tests | `nexus.advisors.providers.*` |
| `TtsEngine`: text → audio | Piper, Kokoro, a cloud TTS later, `SilentTts` for tests | `nexus.audio.engines.*` |
| `ClipPublisher`: clip review → publish | manual export first, then the YouTube/TikTok APIs after their audits | `nexus.clips.publishers.*` |
| `AlertSink`: ops alerts | ntfy, Discord webhook, email | `nexus.ops.alerts.*` |
| `ModerationProvider`: text moderation verdicts (callsigns, templates) | local blocklist with leetspeak/homoglyph folding, a free or local classifier, a cheap hosted check for custom callsigns when needed (Q-MOD-2) | `nexus.moderation.providers.*` |
| `BackupTarget`: encrypted off-site backup storage | Google Drive first (owner already has it), other free or cheap S3-compatible providers; `age`-encrypted before upload (Q-OPS-6; provider limits [UNVERIFIED], NX-285) | `nexus.ops.backup.targets.*` |
| `SupportSource`: support and engagement events | Twitch (channel points, Bits, subs), YouTube (Super Chat, memberships), one third-party tip service later (Q-SUP-3) | `nexus.support.adapters.*` (SUPPORT-REDEMPTIONS §3) |
| `AdminChannel`: admin requests into the Command Center | web console, Discord slash commands (ADMIN-RBAC §7.1) | `nexus.ops.admin.channels.*` |
| `MusicSource`: licensed music for the Music bus | Epidemic Sound (owner subscription; streaming/clip coverage and API [UNVERIFIED], NX-273), local licensed stems | `nexus.audio.music.*` |

### Rules
1. **N-1. No vendor imports outside adapters.** Enforced by import-linter: only `*.adapters.*`, `*.providers.*`, `*.engines.*` and `*.publishers.*` may import vendor SDKs.
2. **N-2. Everything is normalized at the boundary.** Every inbound message becomes a `ChatEnvelope`, and every identity is a `(platform, platform_user_id)` pair (CONTRACTS). Game logic never branches on platform.
3. **N-3. Adapters declare capabilities instead of the core guessing.** Each adapter publishes a `Capabilities` record:
   - `max_reply_rate` and `reply_cost` (YouTube replies cost quota)
   - `supports_moderation_events`
   - `supports_whisper`
   - `message_max_len`
   - `quota_model`
   - `latency_class`

   The core adapts to these values. A missing capability means the feature is off, not faked (DATA-INTEGRITY).
4. **N-4. Conformance test suite.** One shared pytest suite (`tests/conformance/`) runs against every adapter of a port, using recorded fixtures. It covers:
   - normalization
   - dedupe
   - reconnect and backoff
   - rate-limit compliance
   - capability honesty
   - error mapping

   A new platform or provider counts as **done** only when it passes this suite. That keeps "add YouTube/Kick/another LLM" a bounded task.
5. **N-5. Configuration selects adapters.** Enabled platforms and providers are listed in app config. Several chat sources can run at the same time (simulcast); the core merges their messages into one command stream. Adapters can be enabled, disabled or restarted independently, and one platform failing never takes down another.
6. **N-6. Contracts are vendor-free.** No vendor field names or ids leak into `/contracts`. Raw platform payloads are kept only in adapter debug logs, which have a short retention.
7. **N-7. Agent neutrality (development).** `AGENTS.md` is the tool-agnostic source of truth. Tool-specific files (`CLAUDE.md`, `.claude/`, Cursor or Copilot rules if added) only point to it, and add tool mechanics, never different rules. Role cards, prompts, skills and specs are plain Markdown any agent can read. CI quality gates are what enforce the rules, not one agent's plugins, so swapping the coding agent changes nothing about what passes review.

### Launch order
Both Twitch and YouTube are first-class targets. The *launch order* is Twitch alpha → YouTube beta (ADR-0008), **confirmed by the owner on 2026-10-17 (Q-PROD-6)**, for one reason: YouTube's quota needs an application and monitoring first. The architecture doesn't care which goes first, and simulcasting both is supported by design (N-5).

## Consequences
- Adding a platform or provider means writing one adapter and passing the conformance suite. No core changes.
- A little more upfront structure (the interfaces plus the suite), kept small: interfaces are defined only for vendors we actually plan to use.
- Simulcast chat means one game with viewers from several platforms. Cross-platform identity linking (IDENTITY §4) is what makes that fair.

## Amendment (2026-10-19): when the rules are enforced (Q-MB-2, Q-MB-3)
- **N-1** is enforced by an import-linter contract added in the PR that brings in the first vendor SDK (likely the Twitch adapter, NX-191); every later SDK joins its list in the PR that adds it.
- **Ports, `Capabilities` and conformance suites (N-3, N-4)** land with each port's first adapter (chat in NX-190, LLM with the first P4 advisor, TTS with the first engine), not ahead of them. The former NX-050 is dissolved into those items.
- **Status:** accepted by the owner, 2026-10-19.
