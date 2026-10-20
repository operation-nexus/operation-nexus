# SPEC: Chat Gateway

Status: Draft · Tracker: NX-190…NX-199 · ADR-0008 · Facts: PLATFORM-REALITY-CHECK

## 1. Adapter interface (ADR-0010: platform-neutral)

The core never branches on platform. Every adapter implements the same ports, declares its `Capabilities`, and must pass the shared conformance suite (`tests/conformance/chat/`). Multiple sources can run at once (simulcast). Discord can also be a `ChatSource` (command channel) if enabled.

- **CG-1 Viewer simulator never on the public channel** (Q-LEGAL-7). The viewer simulator (NX-193) feeds commands only through the `LocalSim` source into the internal command queue, never through real chat accounts or platform chat. It runs only locally, on staging, or against an unlisted/private test stream, and it refuses to start when the config targets the production channel. Platform policy wording is [UNVERIFIED].

```python
class PlatformAdapter(Protocol):
    platform: Platform            # enum: TWITCH | YOUTUBE | KICK (Kick optional, Q-PROD-2)
    async def run(self, sink: Callable[[ChatEnvelope], Awaitable[None]]) -> None: ...
    async def send_batch(self, lines: list[str]) -> None: ...   # respects platform limits
    def health(self) -> AdapterHealth: ...                      # connected, lag_ms, quota_used
    def capabilities(self) -> Capabilities: ...                 # max_reply_rate, reply_cost, message_max_len,
                                                                # supports_moderation_events, quota_model, latency_class
```

## 2. Twitch (P2)
- EventSub `channel.chat.message` over WebSocket transport, or a conduit. The bot account uses the `user:read:chat` and `user:write:chat` scopes, and the bot is a channel moderator so it gets the 100 messages per 30 s limit.
- Moderation events (`channel.ban`, `channel.moderate`) are consumed so that a Twitch ban also bans the commander in-game.
- Token refresh runs automatically, and refresh tokens are stored encrypted.

## 3. YouTube (P3)
- Find the active broadcast's `liveChatId`, then use `liveChatMessages.streamList` (gRPC server streaming). Reconnect with resume from `nextPageToken`, and alert if the quota rate exceeds the budget.
- **Replies:** a single summary message every ≥ 5 min at most (each one costs 20 units). Acknowledgement is visual only.
- A quota dashboard shows units used per hour and projected time to run out.

## 4. Normalization (SEC-GW-1)
NFKC; strip control, bidi and zero-width characters; enforce the 300-character cap; build a confusable-folded key for matching; lowercase the command token.

**Over-length messages are rejected, never truncated** (Q-CT-1): a command over 300 characters after normalization is dropped and the sender gets a "too long" note in the next batched digest. Truncation could turn a long message into a different valid command. Display names are stored but **never rendered** unless approved (Q-MOD-1).

- **CG-2 `!me` and `!status`** (Q-UX-12): `!me` is canonical (FB-UX-3: 5 s highlight plus a digest line; works in the reserve queue). `!status` is a pure alias: the parser maps it to `!me`, with identical behavior.
- **CG-4 `!quiet` toggle** (Q-ALN-12, Q-AI-7): `!quiet` takes no arguments and is open to any rank. Each use flips the commander's taunt-naming opt-out (IDENTITY ID-PREF-1): off → on, on → off. The bot confirms the **new** state to that commander in the next batched digest (§6). The flag is stored per commander, so it applies on every linked platform. Its schema, parser entry and handler land in one PR (AGENTS.md rule 6a).
- **CG-5 Commands while paused** (Q-ALN-2, Q-ALN-26): a pause freezes the whole world (STATE-MACHINES-AND-FLOWS §4.4). Commands that do not change the world still work while paused: the Info class (`!me`/`!status`, `!help`, `!guide`, `!rules`, `!link`), `!quiet`, `!callsign`, and joining the reserve queue. A `!join` from a commander with no live unit always joins the reserve queue while paused, even when a slot is free, and spawns in queue order after resume (Q-ALN-26). Every other command is refused, and the sender gets a "war paused" line in the next batched digest (§6), never a silent drop (FB-UX-5). A channel-points redemption that arrives while paused is refused and its points are refunded automatically (SUPPORT-REDEMPTIONS SR-5, Q-ALN-37).
- **CG-6 Idle timers** (Q-ALN-26, Q-GD-35): only commands that reach the sim reset a commander's idle handoff/retire timers (`presence.idle_handoff_min`, `presence.idle_retire_min`). The Info class (`!me`/`!status`, `!help`, `!guide`, `!rules`, `!link`), `!quiet` and `!callsign` never reset them, whether accepted, rate-limited or refused.

## 5. Rate limiting (SEC-GW-2)

**Owner decision (2026-10-17, Q-GW-1): stricter, per command class, and adjustable live.** All values are PROPOSED, tuned in playtests, and edited in the Command Center rules editor (hot-reloadable; config keys `ratelimit.class.*` and `ratelimit.slow_mode.multiplier`, CONFIG-AND-CONTENT §6.9). Rule editing is owner/admin only (ADMIN-RBAC §4.3, Q-ALN-10).

| Command class | Examples | Proposed limit per operator |
|---|---|---|
| Deploy | `!join`; later the specialist spawns (reserved, COMMAND-CATALOG §3) | 1 per 10 s (plus respawn timer) |
| Unit correction | `!target`, `!rebase`, `!rtb`; later `!vector`, `!stance`, `!rescue` (GAMEPLAY-LATER §3) | 1 per 5 s, burst 2 |
| Info | `!me`, `!status`, `!help`, `!guide`, `!rules`, `!link`, `!quiet` (Q-ALN-12; class PROPOSED) | 1 per 15 s |
| Social / redeem | redemptions (`!rally` and `!scout` come later, GAMEPLAY-LATER) | Own cooldowns (e.g. rally ~2 min; PROPOSED). Gameplay cooldowns of later social commands run in game time inside the sim (Q-ALN-1); redemption cooldowns and caps run in real time in the gateway (Q-ALN-4) |
| Global | all | Admission cap per tick (raid protection) |

**Slow mode:** an admin toggle that multiplies all limits (e.g. ×3). Optionally it can also switch on the platform's own chat slow mode through the official API, if the platform supports that [VERIFY per platform].

**Feedback without spam:**
1. A **cooldown ring** around the operator's own unit icon on the map. It's cheap and visible to everyone.
2. **Batched bot replies**, e.g. "@a @b @c: hold up, ready in a few seconds". These are grouped per digest, within platform send limits.
3. `!me` shows remaining cooldowns.

Throttled commands are never silently lost without one of these signals (GAMEPLAY FB-UX-5).

Rate limits, digest batching and reconnect backoff run on a monotonic real-time clock, not sim time (Q-CFG-8). So do redemption cooldowns and the supply-drop cap (SUPPORT-REDEMPTIONS SR-1/SR-2): they are enforced before anything enters the sim, matching platform reward cooldowns, and keep running while the sim is paused (Q-ALN-4).

- Global: an admission cap on commands per tick. Above the cap, `!join` requests go to the reserve queue and other commands are dropped, with a metric.
- During a raid (a spike in new users), `!join` requests are coalesced.
- **CG-3 Raids and Shared Chat** (Q-GW-2): raid-origin viewers are normal viewers in our chat; their commands are accepted under the normal rate limits. A raid may trigger a small "reinforcements arriving" world event. Twitch Shared Chat messages that originate from another channel are dropped by default; `gateway.shared_chat.accept_foreign` (default `false`) enables them, and may be switched on only after the source-channel API fields are verified [UNVERIFIED].

## 6. Replies
Replies are an aggregated digest, e.g. "12 new commanders deployed: VIPER-27, …", at most once every 30 s on Twitch and less often on YouTube. Errors such as "unit in sortie" go out as a periodic digest, not one per user.

## 7. Failure modes
| Failure | Behavior |
|---|---|
| Disconnect | Backoff and reconnect. The overlay shows "UPLINK LOST" if it's down for more than 30 s. Alert after 5 min. |
| Duplicate delivery | Dedupe by message id (LRU of 10k). |
| Quota exhausted (YouTube) | Adapter pauses. Overlay shows "YouTube commands paused" with the resume time as a relative time, or as UTC plus the broadcast time zone (OVERLAY OV-19, Q-CFG-8). Alert. |
| One platform's chat down while the broadcast is live | The sim keeps running. The offline auto-pause is triggered by stream-offline detection only, never by a single chat platform dropping (Q-OPS-8). |

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


## 8. Open questions
- Decided and folded in (2026-10-18): Q-GW-2 (CG-3), Q-UX-12 (CG-2), Q-LEGAL-7 (CG-1), Q-ALN-12 (CG-4), Q-ALN-2 (CG-5), Q-ALN-4 (§5 real-time redemption cooldowns), Q-ALN-10 (rule editing is owner/admin only, §5), Q-ALN-26 (`!join` queues while paused, CG-5; idle timers, CG-6), Q-ALN-37 (redemptions refused and refunded while paused, CG-5).
