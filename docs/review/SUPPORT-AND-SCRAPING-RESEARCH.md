# Research: YouTube chat scraping & support/donation events

Date: 2026-10-17. Official pages were often unreachable from the research environment, so items tagged *(excerpt)* come from search excerpts of the cited official URL. **[UNVERIFIED]** items must be re-checked before anything is built on them.

## 1. "Free" YouTube chat libraries (no API quota)
| Library | Latest release (PyPI) | License | Status |
|---|---|---|---|
| pytchat | 0.5.5 (2021-07-24) | MIT | Repo archived 2022-01-25. **Dead.** |
| chat-downloader | 0.2.8 (2023-09-03) | MIT | Repeated breakage reported Oct 2025–Jun 2026 (issues #270–#287), no fix visible |
| innertube | 2.1.19 (2025-07-01) | MIT | Generic private-API client, not a chat reader |

**ToS:** YouTube's Terms forbid accessing the service "using any automated means (such as robots, botnets or scrapers)" except as permitted *(excerpt; re-quote before relying on it)*. Scraping risks the channel's standing and a future quota audit.
**Verdict:** don't use scrapers in production. Keep ADR-0008's `streamList` + quota-increase path. At most, a dev-only opt-in adapter, and only through a new ADR.

**Twitch** has no unit quota on EventSub (it uses a subscription-cost model with limits). Maintained libraries: twitchio 3.3.2 (2026-08-04, MIT) and twitchAPI 4.5.0 (2025-05-23, MIT).

## 2. Support events
**Twitch EventSub** (needs the broadcaster's user token):
| Event | Scope | Notes |
|---|---|---|
| `channel.cheer` | `bits:read` | |
| `channel.bits.use` | `bits:read` | Newer event; covers cheers and Power-ups |
| `channel.channel_points_custom_reward_redemption.add` / `.update` | `channel:read:redemptions` or `channel:manage:redemptions` | Rewards that our Client-Id creates can be set FULFILLED, or CANCELED, which **refunds** the points. Affiliate or Partner only. |
| `channel.subscribe`, `.subscription.gift`, `.subscription.message` | `channel:read:subscriptions` | Gift bombs double-count if handled naively |
| Hype Train | `channel:read:hype_train` | Use v2 |

**Bits** can't be refunded via the API.

**YouTube** `liveChatMessages` types (*excerpt*):
| Type | Payload |
|---|---|
| `superChatEvent` | `amountMicros`, `currency`, `tier` |
| `superStickerEvent` | same, plus sticker metadata |
| `newSponsorEvent` | membership start |
| `memberMilestoneChatEvent` | membership milestone |

`superChatEvents.list` has a 30-day window. Its quota cost is **[UNVERIFIED]**. Super Chats are "not crowdfunding or donation tools", and they're unavailable on made-for-kids videos.

**Third-party donation services**
| Service | Connection | Payload / notes |
|---|---|---|
| Streamlabs | Socket API (OAuth `socket.token`, `donations.read`) | `amount`, `currency` |
| StreamElements | Astro WebSocket, JWT | Field names **[UNVERIFIED]** |
| Ko-fi | Webhook form POST with a `data` JSON | `amount` (string), `currency`, `verification_token` (shared secret, not a signature), `message_id` (dedupe, retries) |

**Currency:** every source gives amounts in the original currency only, with no normalized USD. Bits are counts, and channel points have no monetary value.

**Policy:** the Twitch Bits AUP bans wagering, and says Bits "do not serve as a currency" *(excerpt)*. Chargebacks happen but no reversal webhook was found **[UNVERIFIED]**. Paid random outcomes risk being classified as gambling or loot boxes depending on jurisdiction, so they need legal review.
