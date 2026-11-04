# SPEC: Chat Gateway

Status: Approved (owner, 2026-11-04) for the P2 scope: ports, `Capabilities`, normalization, rate limits, dedupe, replies and the Twitch adapter (§§1, 2, 4–12). YouTube (§3) stays Draft (P3). · Tracker: NX-190 (ports, conformance skeleton, normalization, rate limits), NX-191 (Twitch adapter; approved in principle, its credentials are owner-gated, §2.3), NX-192 (parser), NX-193 (viewer simulator), NX-041 (moderation pipeline) · ADR-0001, ADR-0008, ADR-0010 · Facts: PLATFORM-REALITY-CHECK, PLATFORM-POLICY-VERIFICATION-2026-10-18

Rule numbers are stable and cited from other docs; sections keep their numbers (§9 stays the gateway-only command list). Tunable numbers are PROPOSED unless an owner row says otherwise.

## 1. Ports and architecture (ADR-0010: platform-neutral)

The core never branches on platform. Every adapter implements the ports below, declares its `Capabilities`, and must pass the shared conformance suite. Multiple sources can run at once (simulcast, ADR-0010 N-5).

- **CG-1 Viewer simulator never on the public channel** (Q-LEGAL-7). The viewer simulator (NX-193) feeds commands only through the `LocalSim` source into the internal command queue, never through real chat accounts or platform chat. It runs only locally, on staging, or against an unlisted/private test stream, and it refuses to start when the config targets the production channel. Platform policy wording is [UNVERIFIED].

**Owner decisions, 2026-11-04 (in chat):** (a) the gateway is **in-process**, package `nexus.gateway` inside the single app process (ADR-0001, SYSTEM-DESIGN §4); the adapter runs an asyncio loop in its own thread and hands commands to the runtime through the thread-safe, non-blocking `Inbox.submit` (`services/sim/src/nexus/runtime/inbox.py`), which returns `False` when full. A later process split stays possible behind the ports (SYSTEM-DESIGN's split triggers, SEC-API-1). (b) This spec is approved with the lead defaults below. (c) Raw chat retention is 24 h (GW-16). (d) Bot replies may @-mention the viewer's platform login (GW-15).

### 1.1 Normative rules

- **GW-1 Ports.** `ChatSource` yields `ChatEnvelope`s and `ModerationEvent`s; `ChatSink` has `send_batch(lines: list[str])`, which honors the adapter's `Capabilities`. One adapter class may implement both. Vendor SDKs are imported only under `nexus.gateway.adapters.*` (ADR-0010 N-1; the import-linter contract arrives with the first SDK, in NX-191).
- **GW-2 `ModerationEvent`** is a vendor-free shape owned by `contracts/` (ADR-0010 N-6), added with its first producer (AGENTS.md rule 6a: schema, adapter mapping and consumer land in one PR). Its fields are decided in the PR that adds it, from the platform fields the Twitch adapter actually receives; no field is invented here. It carries at least the event type (ban, unban, timeout, message deleted), `(platform, platform_user_id)`, and a gateway receipt time.
- **GW-3 `Capabilities`** is the union of the former CHAT-GATEWAY list and ADR-0010 N-3: `max_reply_rate`, `reply_cost`, `message_max_len`, `supports_moderation_events`, `supports_whisper`, `quota_model`, `latency_class`. A missing capability means the feature is off, not faked (DATA-INTEGRITY). The adapter also exposes `health()` (connected, lag_ms, quota_used).
- **GW-4 Conformance path.** The single path is `tests/conformance/chat/`, a chat-specific subdirectory of ADR-0010 N-4's `tests/conformance/`. The suite is parametrized over adapters and covers normalization, dedupe, reconnect and backoff, rate-limit compliance, capability honesty and error mapping. NX-190 ships the skeleton against `LocalSim` (§11); Twitch recorded fixtures join in NX-191.
- **GW-5 `IdentityResolver` port.** `resolve(platform, platform_user_id, account_created_at) -> commander_id` (lazy creation, IDENTITY §2) plus `is_banned(commander_id)`. NX-190 and NX-192 build against an in-memory fake; the real implementation (SQLite) comes with NX-200. The gateway never touches the database directly.
- **GW-6 Name directory (fuzzy resolution, Q-SIM-77).** Callsign and node-name matching reads a read-only, immutable `NameDirectory` snapshot (friendly callsign → `entity_id`, node names and aliases) that the runtime publishes once per tick and swaps atomically (a reference swap, no lock held across a tick). The gateway and `nexus.commands` never import `nexus.core` (import-linter, SYSTEM-DESIGN §4). The resolved id, not the typed text, is what goes into the `Command` and the command log, so replay is exact. Match order follows Q-SIM-77 / Q-GP-39.

### 1.2 Module layout and import contract

`nexus.gateway` (adapters, limiter, dedupe, digest) → `nexus.commands` (parser) → `nexus.moderation` (normalization, denylist). `nexus.gateway` may import `nexus.contracts`, `nexus.commands`, `nexus.moderation` and `nexus.obs`; it must not import `nexus.core`. SYSTEM-DESIGN §4's table row for `nexus.gateway` ("may import: contracts") is updated in the NX-190 PR-a to match; the existing import-linter contracts in `services/sim/pyproject.toml` already forbid `gateway`, `commands` and `moderation`-side kernel imports for the first two.

## 2. Twitch (P2)

### 2.1 Behavior
- EventSub `channel.chat.message` consumed by the adapter; the transport (WebSocket or a conduit) is an NX-191 decision (§2.2).
- Moderation events (`channel.ban`, `channel.moderate`, per the previous draft) are consumed so that a Twitch ban also bans the commander in game (`ModerationEvent` → `IdentityResolver`, bans take effect at the first pipeline step, GW-8). The exact EventSub type names and payload fields are [UNVERIFIED] until NX-191 checks them against Twitch docs.
- Token refresh runs automatically; refresh tokens are stored encrypted (§2.3). Credentials arrive only through `secret_ref` config entries (never values in config, never in the repo, AGENTS.md rule 9).
- Send limits: 20 messages per 30 s for a normal account and 100 per 30 s for a moderator or VIP; exceeding them makes Twitch ignore the bot's messages for 1 hour (PLATFORM-REALITY-CHECK §Twitch; the 1 h figure is as corrected in PLATFORM-POLICY-VERIFICATION-2026-10-18 T13). The 100/30 s figure applies only if the bot account is a moderator (or VIP); the adapter's `Capabilities.max_reply_rate` is set from the real status, defaulting to the 20/30 s figure when the status is unknown (NX-191 reads it; it is never assumed).

### 2.2 NX-191 decision: conduit vs WebSocket
Open for NX-191 and listed in §12 (to be filed as Q-GW-7 with NX-191). The only facts available in this repo are those in PLATFORM-REALITY-CHECK and PLATFORM-POLICY-VERIFICATION-2026-10-18 (T17: `max_total_cost` conflict inside Twitch's own docs; our subscriptions are for users who authorized the app, so cost 0). Anything else about connection counts, session lifetime or conduit shard behavior is [UNVERIFIED] and must be checked against Twitch docs in the NX-191 PR before choosing.

### 2.3 Owner actions before NX-191 (checklist; the lead and agents do not pick these)
- [ ] Register the Twitch application (client id; client secret into the secret manager, referenced by `secret_ref`).
- [ ] Create or nominate the bot account; decide whether it is made a channel moderator (affects the 20 vs 100 per 30 s send limit) or VIP.
- [ ] Decide the scopes: `user:read:chat` and `user:write:chat` (both in PLATFORM-REALITY-CHECK), and the open question whether `user:bot` and/or `channel:bot` are also required (PLATFORM-REALITY-CHECK says an app token needs `user:bot` plus `channel:bot` or moderator status; whether our token type needs it is [UNVERIFIED]).
- [ ] Choose where the encrypted refresh token lives (file path/secret store, encryption key custody) and who rotates it.
- [ ] Authorize the bot and the broadcaster grants (OAuth consent) on the real channel or a private test channel.
- [ ] Confirm the test channel is unlisted/private for the first adapter runs (CG-1).

## 3. YouTube (P3, Draft)
- Find the active broadcast's `liveChatId`, then use `liveChatMessages.streamList` (gRPC server streaming). Reconnect with resume from `nextPageToken`, and alert if the quota rate exceeds the budget.
- **Replies:** a single summary message every ≥ 5 min at most (each one costs 20 units). Acknowledgement is visual only.
- A quota dashboard shows units used per hour and projected time to run out.
- Discord as a `ChatSource` (ADR-0010's optional command channel) is **post-launch**: ADR-0008's launch order is Twitch (P2), YouTube (P3), then Kick (optional); Discord command input is not scheduled in any phase and needs its own tracker item before it is built.

## 4. Normalization and pipeline (SEC-GW-1)

- **GW-7 One pure normalizer.** `nexus.moderation.normalize(text) -> str` (pure, no I/O, no clock): NFKC; line breaks and tabs (`\n`, `\r`, `\t`, `\v`, `\f`, U+0085, U+2028, U+2029) become one space each (runs are not collapsed), so a stripped break cannot glue two words into a different command; strip the other control, bidi and zero-width characters; then the 300-character cap measured **after** normalization. It also exposes a confusable-folded `match_key` (≤ 300) and the command token is lowercased by the parser. Over-length is **rejected, never truncated** (Q-CT-1): a command over 300 characters after normalization is dropped and the sender gets a "too long" line in the next digest. Truncation could turn a long message into a different valid command. NFKC can expand text (e.g. ligatures, compatibility forms) so a message under 300 before normalization may be over after; the cap is checked on the result only. Display names are stored but **never rendered** unless approved (Q-MOD-1).
- **GW-8 Pipeline order (fixed).** For every inbound message: (1) ban check on `(platform, platform_user_id)`; (2) normalize (GW-7); (3) dedupe by platform message id (LRU of 10k, FIFO eviction, in memory); (4) rate limit (§5); (5) parse (`nexus.commands`); (6) moderate any user-derived text in the parsed command (callsign requests etc.; the denylist, SEC-MOD-1); (7) `Inbox.submit`. Each stage that drops a message produces a counted metric and, where the sender is a known commander and the drop is not blatant spam (GW-13), a digest line. A step failing never skips a later step to "fail open": an exception in a stage drops the message and reports through `nexus.errors`.
- **GW-9 Ids.** `correlation_id` (CONTRACTS ≤ 64 chars) is derived deterministically from the platform message id: `sha256("{platform}:{platform_message_id}")` hex-truncated to 32 chars. Same input gives the same id; it never contains raw user text. `received_at` is gateway wall clock and never reaches the sim (envelope contract).
- **GW-10 Logs.** Logs never hold raw user text beyond the raw store (GW-14). Gateway logging goes through `nexus.obs` redaction; the unit test for each stage asserts no raw message text appears in log output.

- **CG-2 `!me` and `!status`** (Q-UX-12): `!me` is canonical (FB-UX-3: 5 s highlight plus a digest line; works in the reserve queue). `!status` is a pure alias: the parser maps it to `!me`, with identical behavior.
- **CG-4 `!quiet` toggle** (Q-ALN-12, Q-AI-7): `!quiet` takes no arguments and is open to any rank. Each use flips the commander's taunt-naming opt-out (IDENTITY ID-PREF-1): off → on, on → off. The bot confirms the **new** state to that commander in the next batched digest (§6). The flag is stored per commander, so it applies on every linked platform. Its schema, parser entry and handler land in one PR (AGENTS.md rule 6a).
- **CG-5 Commands while paused** (Q-ALN-2, Q-ALN-26): a pause freezes the whole world (STATE-MACHINES-AND-FLOWS §4.4). Commands that do not change the world still work while paused: the Info class (`!me`/`!status`, `!help`, `!guide`, `!rules`, `!link`), `!quiet`, `!callsign`, and joining the reserve queue. A `!join` from a commander with no live unit always joins the reserve queue while paused, even when a slot is free, and spawns in queue order after resume (Q-ALN-26). Every other command is refused, and the sender gets a "war paused" line in the next batched digest (§6), never a silent drop (FB-UX-5). A channel-points redemption that arrives while paused is refused and its points are refunded automatically (SUPPORT-REDEMPTIONS SR-5, Q-ALN-37).
- **CG-6 Idle timers** (Q-ALN-26, Q-GD-35): only commands that reach the sim reset a commander's idle handoff/retire timers (`presence.idle_handoff_min`, `presence.idle_retire_min`). The Info class (`!me`/`!status`, `!help`, `!guide`, `!rules`, `!link`), `!quiet` and `!callsign` never reset them, whether accepted, rate-limited or refused.

## 5. Rate limiting (SEC-GW-2)

**Owner decision (2026-10-17, Q-GW-1): stricter, per command class, and adjustable live.** All values are PROPOSED, tuned in playtests, and edited in the Command Center rules editor (hot-reloadable; config keys `ratelimit.class.*` and `ratelimit.slow_mode.multiplier`, CONFIG-AND-CONTENT §6.9). Rule editing is owner/admin only (ADMIN-RBAC §4.3, Q-ALN-10).

- **GW-11 Limiter.** A token bucket per `(commander_id or platform identity, command class)` on an **injected monotonic clock** (never wall clock, never sim time, Q-CFG-8; tests drive a fake clock). Rate limits, digest batching and reconnect backoff all use that clock. Buckets are created lazily and evicted after idle (bounded memory). The config keys in the table already exist in CONFIG-AND-CONTENT §6.9; the NX-190 PR adds the missing ones (global cap, blatant-spam threshold, digest interval) through the `add-config-key` skill, with loader field, registry metadata, regenerated reference and goldens.

| Command class | Examples | Proposed limit per operator |
|---|---|---|
| Deploy | `!join`; later the specialist spawns (reserved, COMMAND-CATALOG §3) | 1 per 10 s (plus respawn timer) |
| Unit correction | `!target`, `!rebase`, `!rtb`; later `!vector`, `!stance`, `!rescue` (GAMEPLAY-LATER §3) | 1 per 5 s, burst 2 |
| Info | `!me`, `!status`, `!help`, `!guide`, `!rules`, `!link`, `!quiet` (Q-ALN-12; class PROPOSED) | 1 per 15 s |
| Callsign | `!callsign` (also has the 30-day change limit and the moderation queue; Q-CMD-3) | 1 per 60 s |
| Forget | `!forget` (Q-CMD-3) | 1 per 60 s |
| Social / redeem | redemptions (`!rally` and `!scout` come later, GAMEPLAY-LATER) | Own cooldowns (e.g. rally ~2 min; PROPOSED). Gameplay cooldowns of later social commands run in game time inside the sim (Q-ALN-1); redemption cooldowns and caps run in real time in the gateway (Q-ALN-4) |
| Global | all | Admission cap per tick (raid protection) |

- **GW-12 Global admission cap.** At most `ratelimit.global.per_tick_cap` commands are admitted per tick; PROPOSED default **50** (a guess sized against the ~100 messages/s ceiling in ADR-0001 at the 10 Hz tick; to be tuned by NX-193 load runs). Above the cap, `!join` requests go to the reserve queue path and other commands are dropped, each with a metric and a digest line unless blatant (GW-13). The cap also bounds work done before `Inbox.submit`; `Inbox` capacity (NX-106) is a second, independent limit.
- **Slow mode.** An admin toggle that multiplies all limits (`ratelimit.slow_mode.multiplier`, PROPOSED 3). **P2 ships only the multiplier**; switching on the platform's own chat slow mode through the official API is **deferred** (it needs an extra scope and platform support [UNVERIFIED]) and gets its own tracker item if wanted.

**Feedback without spam:**
1. A **cooldown ring** around the operator's own unit icon on the map. It's cheap and visible to everyone.
2. **Batched bot replies**, e.g. "@a @b @c: hold up, ready in a few seconds". These are grouped per digest, within platform send limits (§6).
3. `!me` shows remaining cooldowns.

Throttled commands are never silently lost without one of these signals (GAMEPLAY FB-UX-5), except blatant spam and floods (GW-13).

Redemption cooldowns and the supply-drop cap (SUPPORT-REDEMPTIONS SR-1/SR-2) are enforced the same way: before anything enters the sim, matching platform reward cooldowns, and they keep running while the sim is paused (Q-ALN-4).

- During a raid (a spike in new users), `!join` requests are coalesced.
- **CG-3 Raids and Shared Chat** (Q-GW-2): raid-origin viewers are normal viewers in our chat; their commands are accepted under the normal rate limits. A raid may trigger a small "reinforcements arriving" world event. Twitch Shared Chat messages that originate from another channel are dropped by default; `gateway.shared_chat.accept_foreign` (default `false`) enables them, and may be switched on only after the source-channel API fields are verified [UNVERIFIED].

## 6. Replies and the always-answer rule (Q-SIM-77, FB-UX-5)

- **GW-13 Always answer.** Every command, accepted or rejected, gets feedback (accepted: the unit highlight plus a digest line; rejected: the reason in the next digest) unless the sender is **blatant spam or a flood**, who get the cooldown ring alone. "Blatant" is a per-user count of limiter rejections in a window: `gateway.spam.blatant_threshold` PROPOSED **10 rejections within 60 s** (a guess; tuned by NX-193), a config key added in NX-190 PR-b.
- **GW-14 Digest.** `ChatSink.send_batch(lines)` carries output; a `DigestBuilder` in `nexus.gateway` takes `CommandRejected` and accepted-command events from the in-process event bus and gateway-side rejects (too long, rate limited, parse errors, inbox overflow; banned users get no reply), **coalesces per user**, and caps each batch to the adapter's `Capabilities` (message length, reply rate). Twitch caps are the PLATFORM-REALITY-CHECK numbers (20 or 100 messages per 30 s depending on moderator status); cadence is at most one digest every 30 s on Twitch, less often on YouTube. Example: "12 new commanders deployed: VIPER-27, …"; errors like "unit in sortie" go out in the digest, not one per user. Reject reasons are the `RejectReason` enum (CONTRACTS §5.2); digest text is static templates keyed by reason, never an echo of user text. An `Inbox.submit` returning `False` (overflow) produces a digest reject ("busy, try again") for that sender.
- **GW-15 Platform login in replies (owner, 2026-11-04).** A bot reply may @-mention the viewer's platform login in that platform's chat ("@user → VIPER-27"). The login is never rendered on our overlay, TTS or logs, which stay callsign-only (Q-MOD-1). The login is held only in the digest builder's in-memory batch and not written to logs (GW-10).
- **GW-16 Raw chat retention (owner, 2026-11-04).** Raw chat envelopes are kept **at most 24 h**, the stricter Twitch limit (Developer Services Agreement, PLATFORM-POLICY-VERIFICATION-2026-10-18 T19: cache "for only a twenty-four hour time period"). Only the resolved command log is kept longer (campaign duration + 30 days per Q-LEGAL-3, unaffected). This supersedes the 7-day raw-chat figure in THREAT-MODEL SEC-DATA-4 and Q-LEGAL-3; the lead updates those separately. A purge job enforces the limit; adapter debug payloads (ADR-0010 N-6) follow the same or a shorter limit.

## 7. Failure modes

| Failure | Behavior |
|---|---|
| Disconnect | Backoff and reconnect (backoff on the injected monotonic clock). The overlay shows "UPLINK LOST" if it's down for more than 30 s. Alert after 5 min. |
| Duplicate delivery | Dedupe by message id (LRU of 10k, GW-8). A duplicate older than the LRU window can pass; accepted, the limiter and sim idempotency bound the effect. |
| Quota exhausted (YouTube) | Adapter pauses. Overlay shows "YouTube commands paused" with the resume time as a relative time, or as UTC plus the broadcast time zone (OVERLAY OV-25, Q-CFG-8). Alert. |
| One platform's chat down while the broadcast is live | The sim keeps running. The offline auto-pause is triggered by stream-offline detection only, never by a single chat platform dropping (Q-OPS-8). |
| `Inbox` full | `submit` returns `False`; counted; sender gets a digest reject (GW-14). The adapter loop never blocks on the inbox. |
| Gateway thread crash | Caught at the thread boundary, reported via `nexus.errors` with token scrubbing (GW-19, EP-2); the sim keeps ticking; the adapter restarts with backoff. |
| Limiter or dedupe state lost on restart | Starts empty (fail-open for rate limits only on a cold start; the global cap and inbox capacity still bound input). |
| Bot send-limit exceeded | `ChatSink` never exceeds `Capabilities.max_reply_rate`; digest lines are dropped oldest-first with a metric rather than risk the platform's 1 h mute. |
| Name directory stale/unavailable | Fuzzy resolution rejects with a "try again" digest line; never guesses. |
| Denylist/moderation service error | The user-derived string is treated as unapproved (neutral generated callsign); no fail-open. |

## 8. Security (SEC-GW, SEC-MOD, SEC-LLM)

- **GW-17 Chat never becomes system/staff.** Gateway output maps only to chat `CommandKind`s; it never produces `SYS_*` or `STAFF_*` kinds (COMMAND-CATALOG §4). A test enumerates the `CommandKind` enum and asserts the parser's reachable set excludes them.
- **GW-18 Callsigns.** The callsign regex `^[A-Z][A-Z0-9-]{2,11}$` and the reserved words (generated patterns, the `X-` tombstone prefix, command keywords, role and stance names, node names/aliases) come from IDENTITY §3 and are enforced in `nexus.moderation`, shared with the parser, not duplicated. Homoglyph/confusable folding applies before the reserved-word comparison.
- **GW-19 Tokens.** No platform token reaches an error report, log or exception text (ERROR-PIPELINE EP-2 allowlist scrub; `nexus.obs` redaction). The `nexus-llm` container and `nexus.advisors` never receive platform tokens (SYSTEM-DESIGN §4). Credentials are `secret_ref` config only.
- **GW-20 EventSub integrity.** Signature verification and message-id dedupe per SEC-GW-4 where a webhook transport is used; for a WebSocket transport the equivalent integrity guarantees are an NX-191 finding [UNVERIFIED].
- **GW-21 Review.** The `security-review` skill is required on every gateway PR (chat ingestion), plus the Claude review action label (CLAUDE.md, Q-CI-7).
- Only official APIs (SEC-GW-3). Chat text is hostile (AGENTS.md rule 4); LLM output never sits on the ingest path (rule 5).

## 9. Gateway-only commands (moved from GAMEPLAY §3, Q-GP-2)
These never enter the sim; the gateway answers them with a digest line or a static URL (CONTRACTS §5). `!status` is an alias of `!me` set in config (Q-UX-12).

| Command | Args | Min rank | Notes |
|---|---|---|---|
| `!status` | — | O-1 | Alias of `!me`, identical behavior (Q-UX-12) |
| `!help` | — | any | Short command digest (Q-UX-1) |
| `!guide` | — | any | Link to the Field Manual on the public site (Q-UX-1) |
| `!rules` | — | any | Link to the published community/conduct rules (Q-MOD-5) |
| `!quiet` | — | any | **Toggle** (Q-ALN-12): switches your opt-out from being named in mastermind taunts (Q-AI-7, THREAT-DIRECTOR TD-3) on or off, and the bot confirms the new state in the digest. Stored per commander (DATA-MODEL) and applies across linked platforms. Works while paused (Q-ALN-2). Ships with taunts that name operators; schema, parser entry and handler land in one PR (AGENTS.md rule 6a) |
| `!link` | — | any | Shows the static account-linking portal URL (IDENTITY §4; ships with YouTube in beta, Q-PROG-5) |
| `!forget` | — | any | Data deletion request (SEC-DATA-3) |

### 9.1 Parser scope (NX-192)
- **GW-22 First parser PR: `!join` and `!rebase` only.** Today only `JOIN` and `REBASE` have schemas and handlers among chat commands (`contracts/commands/command.json`). Each further command (`!target`, `!rtb`, `!me`, `!quiet`, `!callsign`, `!forget`, …) is its own small PR with schema, parser entry and handler together (AGENTS.md rule 6a, COMMAND-CATALOG CC-2). NX-192's tracker line (parser + grammar + fuzz + fuzzy callsigns + always-answer + HOLD-clearing orders) is therefore larger than one M; the lead splits it when the item starts: (a) JOIN + REBASE parser and grammar with fuzz, (b) fuzzy callsign/node resolution via `NameDirectory` (GW-6), (c) the always-answer wiring (GW-13/14), (d) one PR per further command. Unknown names are ignored (CC-4).

## 10. Test plan

| Req | Test |
|---|---|
| GW-7 | `hypothesis` fuzz of `normalize`: zero-width and bidi characters inserted at random positions are stripped; control characters stripped; 10 KB strings are rejected in bounded time and never truncated; NFKC expansion cases (a 150-char string that expands over 300 is rejected, a 300-char string that contracts is accepted); idempotence (`normalize(normalize(x)) == normalize(x)`); homoglyph callsigns (Cyrillic/fullwidth lookalikes of `VIPER-27`, reserved words) fold to the reserved key and are rejected |
| GW-8 | Pipeline order test: a banned user is dropped before normalization; the stage-order is asserted with a recording harness; an exception in a stage drops (no fail-open) |
| Dedupe | The same message id twice yields one command; LRU of 10k evicts oldest first; ids across platforms with equal text do not collide |
| GW-11, GW-12 | Limiter with a fake monotonic clock: refill, burst, per-class independence, slow-mode multiplier, global per-tick cap, bucket eviction, no wall-clock access (the test patches `time.time` to raise) |
| GW-13, GW-14 | Digest coalescing per user, platform caps, blatant-spam threshold gives ring-only, inbox overflow gives a digest reject, templates never echo user text |
| GW-9 | `correlation_id` is deterministic, ≤ 64 chars, contains no user text |
| GW-10, GW-19 | Log capture and error-report capture contain no raw text or token-shaped strings |
| GW-17 | Reachable `CommandKind` set from chat excludes every `SYS_*`/`STAFF_*` kind |
| GW-4 | Conformance skeleton on `LocalSim` (normalization, dedupe, rate-limit compliance, capability honesty, error mapping, reconnect/backoff via a fault-injecting fake); Twitch fixtures in NX-191 |
| GW-16 | Purge job removes raw envelopes older than 24 h on a fake clock; the command log is untouched |
| Import | import-linter: `nexus.gateway` does not import `nexus.core` (existing contract) |

## 11. NX-190 split (each PR under ~400 non-test lines, AGENTS.md rule 7)
- **PR-a: ports + `Capabilities` + normalization.** `ChatSource`, `ChatSink`, `Capabilities`, `ModerationEvent` contract (or its stub row, GW-2), `IdentityResolver` port + in-memory fake, `NameDirectory` type, `nexus.moderation.normalize` with the fuzz tests, the SYSTEM-DESIGN §4 table update.
- **PR-b: limiter + dedupe + conformance skeleton + `LocalSim`.** Token bucket on the injected clock, global cap, LRU dedupe, `DigestBuilder` skeleton, config keys via `add-config-key`, `tests/conformance/chat/` with the `LocalSim` source (Platform `LOCAL_SIM` already exists).
- NX-192 (GW-22) and NX-041 (moderation pipeline) build on PR-a. NX-041's tracker dependency is NX-190 only, but its callsign checks (GW-18) also need the IDENTITY callsign rules (spec text exists) and a resolver to test uniqueness; it builds against the in-memory `IdentityResolver` fake from PR-a, and the real resolver arrives with NX-200 (add NX-200 as a soft dependency on NX-041's callsign part).

## 12. Open questions
- Decided and folded in (2026-10-18): Q-GW-2 (CG-3), Q-UX-12 (CG-2), Q-LEGAL-7 (CG-1), Q-ALN-12 (CG-4), Q-ALN-2 (CG-5), Q-ALN-4 (§5 real-time redemption cooldowns), Q-ALN-10 (rule editing is owner/admin only, §5), Q-ALN-26 (`!join` queues while paused, CG-5; idle timers, CG-6), Q-ALN-37 (redemptions refused and refunded while paused, CG-5).
- Decided 2026-11-04 (owner in chat; to be recorded as Q-GW-3 to Q-GW-6): in-process gateway, approval with lead defaults, 24 h raw retention, @-mention of platform login in bot replies.
- Open for NX-191: conduit vs WebSocket (§2.2); Twitch owner checklist (§2.3). Tunable numbers (global cap, blatant-spam threshold, digest cadence) are PROPOSED and tuned with NX-193.
