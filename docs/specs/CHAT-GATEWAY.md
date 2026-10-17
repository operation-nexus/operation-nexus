# SPEC: Chat Gateway

Status: Draft · Tracker: NX-190…NX-199 · ADR-0008 · Facts: PLATFORM-REALITY-CHECK

## 1. Adapter interface
```python
class PlatformAdapter(Protocol):
    platform: Platform            # enum: TWITCH | YOUTUBE | KICK
    async def run(self, sink: Callable[[ChatEnvelope], Awaitable[None]]) -> None: ...
    async def send_batch(self, lines: list[str]) -> None: ...   # respects platform limits
    def health(self) -> AdapterHealth: ...                      # connected, lag_ms, quota_used
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
NFKC; strip control, bidi and zero-width characters; cap at 300 characters; build a confusable-folded key for matching; lowercase the command token. Display names are stored but **never rendered** unless approved (Q-MOD-1).

## 5. Rate limiting (SEC-GW-2)
- Per user: a token bucket of 1 command per 2 s, burst 3.
- Global: an admission cap on commands per tick. Above the cap, `!join` requests go to the reserve queue and other commands are dropped, with a metric.
- During a raid (a spike in new users), `!join` requests are coalesced.

## 6. Replies
Replies are an aggregated digest, e.g. "12 new commanders deployed: VIPER-27, …", at most once every 30 s on Twitch and less often on YouTube. Errors such as "unit in sortie" go out as a periodic digest, not one per user.

## 7. Failure modes
| Failure | Behavior |
|---|---|
| Disconnect | Backoff and reconnect. The overlay shows "UPLINK LOST" if it's down for more than 30 s. Alert after 5 min. |
| Duplicate delivery | Dedupe by message id (LRU of 10k). |
| Quota exhausted (YouTube) | Adapter pauses. Overlay shows "YouTube commands paused until HH:MM". Alert. |
