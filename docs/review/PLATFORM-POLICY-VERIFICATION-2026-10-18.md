# Platform Policy and API Limit Verification (primary sources)

Date: 2026-10-18 · Status: research, not a spec · Tracker: NX-333 · Scope: every `[UNVERIFIED]`, `[CONFLICT]`, `[3P]` and `[EXCERPT-OFFICIAL]` claim about platform rules, quotas and eligibility in [SOCIAL-CHANNEL-AUTOMATION-RESEARCH](SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md), [PLATFORM-REALITY-CHECK](PLATFORM-REALITY-CHECK.md), [LEGAL-AND-NAME-SWEEP-2026-10-18](LEGAL-AND-NAME-SWEEP-2026-10-18.md) §3, [AUTOMOD-AND-PRIVACY-ANALYTICS-RESEARCH](AUTOMOD-AND-PRIVACY-ANALYTICS-RESEARCH.md) §1 and [MARKETING-AND-PRODUCTION-RESEARCH](MARKETING-AND-PRODUCTION-RESEARCH.md) §3.

Per AGENTS.md rule 0, every value below was read from a page fetched on 2026-10-18 (the "Date read" for every row). Quotes are short and verbatim. Where a page could not be read, the row says so and the item is in section 5. This file changes no other document; section 4 lists the corrections the coordinating session should apply (rule 11b).

## 1. Method and access log

Tools: `curl -sL --compressed` with a normal browser User-Agent, saved to disk and converted to text; a search tool was used only to find the URL of a primary page, never as evidence.

| Host / page family | Result |
|---|---|
| developers.google.com (YouTube Data API: quota calculator, revision history, audit guide, videos.insert, streamList, OAuth, scopes, developer policies) | Read in full. Pages show "Last updated 2026-10-15 UTC". |
| support.google.com/youtube (inauthentic content, GenAI disclosure, live streaming, verify account, Shorts, fake engagement), support.google.com/cloud (audience, verification) | Read in full (server-rendered). |
| dev.twitch.tv (API reference, chat, EventSub, API guide) | Read in full. `dev.twitch.tv/docs/chat/verified-bots/` returned 403, but the same text is on `/docs/chat/`. |
| legal.twitch.com (Developer Services Agreement, Terms of Service, DMCA, Privacy Notice), blog.twitch.tv | Read. The Community Guidelines page is a JavaScript shell with no body text. |
| help.twitch.tv (Affiliate, rerun, Always On, music, AI training) | **Not readable.** Salesforce JavaScript shell; the body is not in the HTML. web.archive.org was unreachable. Primary evidence came from the Twitch blog instead where it existed. |
| developers.tiktok.com (content sharing guidelines, Content Posting API, app review, rate limits, changelog) | Read in full. |
| tiktok.com (Developer ToS, consumer Terms, Community Guidelines "2026H2update" via its embedded JSON, creator-networks LIVE page) | Read. support.tiktok.com help articles are JavaScript shells (no body). |
| developers.facebook.com (Instagram Platform docs, Platform Terms, Developer Policies) | A plain browser User-Agent gets HTTP 400. Using the `facebookexternalhit/1.1` User-Agent (the normal link-preview crawler identity, no login, no challenge) returned the full pages. Read. |
| help.instagram.com, facebook.com/legal/automated_data_collection_terms | HTTP 200 but the body is JavaScript-rendered; no policy text recovered. |
| docs.discord.com (gateway, auto-moderation) | Read in full. |
| support-dev.discord.com, support.discord.com (Developer Policy, verification article) | HTTP 403, Cloudflare "Just a moment" challenge. Not bypassed. |
| WebFetch | Failed with `ENOTFOUND` on every host tried; not used for evidence. |

## 2. Verdict table

Legend: VERIFIED = primary page confirms; CORRECTED = primary page gives a different value (stated); CONTRADICTED = primary page says the opposite; UNVERIFIED = no primary text obtained (see section 5). All "Date read" 2026-10-18.

### 2.1 YouTube

| ID | Claim | Source doc, section | Primary URL | Verdict | Verified value |
|---|---|---|---|---|---|
| Y1 | Default quota 10,000 units/day, plus separate 100 `videos.insert` and 100 `search.list` buckets | SOCIAL §2.2 | developers.google.com/youtube/v3/determine_quota_cost | VERIFIED | "default quota allocation of 100 search.list calls, 100 videos.insert calls, and 10,000 units per day combined for all other endpoints"; resets midnight Pacific |
| Y2 | `videos.insert` costs about 1,600 units (about 6 uploads/day) | REALITY-CHECK §5 | same, plus /revision_history | **CORRECTED** | Now 100 calls/day in its own bucket, cost 1 per call. Revision history: 2025-12-04 "approximately 1600 units to approximately 100 units"; 2026-06-01 granular buckets |
| Y3 | `liveChatMessages.list` 5, `insert` 20, `delete` 20 | REALITY-CHECK §2, AUTOMOD §1.2 | quota calculator | VERIFIED | list 5, insert 20, delete 20, transition 20. The "50 for send/delete" GitHub claim is wrong |
| Y4 | `liveChatMessages.streamList` 5 units | REALITY-CHECK §2 | quota calculator; live/docs `liveChatMessages/streamList` | VERIFIED (per call) | 5. The page says "A call to this method has a quota cost of 5 units"; it does not state per-message billing. See Y5 |
| Y5 | Whether streamList is billed per connection or per message | REALITY-CHECK §2 | streamList reference | UNVERIFIED | Page defines the cost per call and shows resume by `nextPageToken`. No statement on long-lived billing. Measure in the Cloud Console |
| Y6 | `liveChatBans.insert` 200 units, `liveChatBans.delete` 200 | AUTOMOD §1.2 | quota calculator | VERIFIED | Both 200. Also `liveChatModerators` insert/delete 200, list 50 |
| Y7 | Other costs: `thumbnails.set` 50, `commentThreads.insert` 50, `comments.insert` 50, `setModerationStatus` 50, `commentThreads.list` 1, `liveBroadcasts.bind` 1, `liveStreams.insert` 1; `liveBroadcasts.insert` "unconfirmed" | SOCIAL §2.2 | quota calculator | VERIFIED | All as stated; `liveBroadcasts.insert` is 1 (also list/update/transition/delete 1) |
| Y8 | Unverified API projects (created after 2020-07-28) have `videos.insert` uploads locked private until audit | SOCIAL §2.2, REALITY-CHECK §5 | revision_history (2020-07-28 entry) vs reference `videos/insert` | **CONTRADICTED by the current reference (conflict inside Google's docs)** | The 2020 history entry still says restricted to private. The current `videos.insert` reference says "Videos uploaded from unverified API projects are not restricted to private viewing mode." No later history entry reverses the 2020 one. Needs a real test upload (section 5) |
| Y9 | Audit and quota extension go through one form; no turnaround published | SOCIAL §2.2 | guides/quota_and_compliance_audits | VERIFIED | "A member of YouTube's API Services team will contact you as soon as possible." No time stated. Extension within 12 months of a passed audit uses the same form; separate Appeals, Periodic Audit and Change of Control forms |
| Y10 | Testing-status OAuth apps get refresh tokens that expire in 7 days; 100 test users | SOCIAL §2.2 | developers.google.com/identity/protocols/oauth2; support.google.com/cloud/answer/15549945 | VERIFIED | "refresh token expiring in 7 days" for external + Testing, unless scopes are only name/email/profile; "limited to up to 100 test users"; also 100 refresh tokens per account per client |
| Y11 | In production + unverified: user cap | SOCIAL §5.5 | support.google.com/cloud/answer/15549945 | VERIFIED (new) | "100 new users in total, after the app presents the unverified app screen"; lifetime cap, not resettable |
| Y12 | Whether `youtube.upload` is sensitive/restricted | SOCIAL §2.2 | developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification | UNVERIFIED | The page names "deleting a YouTube video" as a sensitive example but does not classify `youtube.upload` or `youtube.force-ssl`. Check the Cloud Console scope table |
| Y13 | Policy renamed "inauthentic content" 2025-07-15; mass-produced/templated AI content ineligible | SOCIAL §3, REALITY-CHECK §2, LEGAL §3.2 | support.google.com/youtube/answer/1311392 | VERIFIED | "renaming this policy from 'repetitious content' to 'inauthentic content.'"; example: "AI-generated content made with generic or unoriginal templates giving the impression of mass production". Nothing about live streams. Applies to YPP monetization |
| Y14 | Altered/synthetic disclosure rule | SOCIAL §4.2, LEGAL §3.2 | support.google.com/youtube/answer/14328491 | VERIFIED + detail | Disclose realistic content only. The no-disclosure list includes "Gameplay footage from video games" and "Cloning one's own voice to create voice overs". A generic TTS voice is on neither list. Studio field: Attributes, "AI use". Misuse can mean "manual application of a label" or YPP suspension |
| Y15 | YouTube auto-labels AI content "from May 2026" | SOCIAL §4.2 | same | VERIFIED (no date) | Auto labels apply to YouTube GenAI tools, C2PA metadata, or internal detection; those labels "can not be adjusted". The page gives no May 2026 date, so the date stays unverified |
| Y16 | Live enablement: phone verification, ~24 h wait, number verifies limited channels/year, no restrictions in 90 days | SOCIAL §1.3 | support.google.com/youtube/answer/2474026, /2907883, /171664 | VERIFIED + **CORRECTED** (limit) | "no live streaming restrictions in the past 90 days"; "may take up to 24 hours"; phone number linked to "no more than 2 channels per year" (the "limited number" is 2). Also "at least 16 years old to live stream" |
| Y17 | Mobile live needs 50 subscribers | SOCIAL §1.3 | (requirements page not found) | UNVERIFIED | The linked help answer returned "page can't be found". Not needed for an encoder stream |
| Y18 | Shorts view counting changed | MARKETING §3.3 | support.google.com/youtube/answer/10059070; revision_history 2025-03-26 | VERIFIED | "Starting 3/31/2025 ... Views will count the number of times a Short starts to play or replay, with no minimum watch time"; old metric renamed "Engaged views"; YPP uses engaged views. Shorts "up to 3 minutes long" also on the page |
| Y19 | Developer Policies: delete user data in about 30 days | LEGAL §3.2 | developers.google.com/youtube/terms/developer-policies | **CORRECTED** | Two clocks. In-app revocation: delete Authorized Data "within 7 calendar days". Revocation through Google security settings: "within 30 calendar days". Non-authorized stats not stored over 30 days; authorization re-checked every 30 days |
| Y20 | YouTube ToS bars automated means | SOCIAL §1.1 | youtube.com/t/terms | VERIFIED | "access the Service using any automated means (such as robots, botnets or scrapers)" except search engines or written permission |
| Y21 | Fake engagement / viewbotting banned | SOCIAL §3 | support.google.com/youtube/answer/3399767 | VERIFIED | Lists "knowingly uses a service to artificially inflate live traffic ('viewbotting')" |

### 2.2 Twitch

| ID | Claim | Source doc, section | Primary URL | Verdict | Verified value |
|---|---|---|---|---|---|
| T1 | Affiliate criteria lowered May 2026 to 25 followers, 4 h, 4 days, 3 viewers | SOCIAL §1.3 | blog.twitch.tv/en/2026/05/13/monetization-for-all/ | VERIFIED | Old: 8 hours, 7 days, Average 3 CCV, 50+ followers. New: 4 hours, 4 different days, "Min 3 ACCV (on 4 different days)", 25+ followers; "in early June, we updated the criteria". Qualifying streamers "should automatically receive an email and a notification" (no application). Rolling-30-day window not on the blog |
| T2 | Channel Points / custom rewards are Affiliate/Partner only (403) | SOCIAL §2.1 | blog (above) vs dev.twitch.tv API reference | **CONFLICT inside Twitch's own pages** | Blog: Channel Points and other tools opened "to all streamers", US first, global "later this year". API reference for Create Custom Rewards still lists 403 "The broadcaster is not a partner or affiliate". Handle the 403 |
| T3 | Non-recurring schedule segments are Affiliate/Partner only | SOCIAL §2.1 | API reference, Create Channel Stream Schedule Segment | VERIFIED | "Only partners and affiliates may add non-recurring broadcasts." Scope `channel:manage:schedule` |
| T4 | Modify channel info, Create Stream Marker scope | SOCIAL §2.1 | API reference | VERIFIED | Both `channel:manage:broadcast` |
| T5 | Create Clip: scope, 90 s capture, 5 to 60 s, "after 15 s assume failure" | SOCIAL §2.1 | API reference, Create Clip | **CORRECTED** | `clips:edit`; "captures up to 90 seconds"; clip 5 to 60 s (default 30); failure check is "after 60 seconds" not 15 |
| T6 | Get Clips Download "open beta; availability unverified" | SOCIAL §2.1 | API reference | **CORRECTED** | Listed as NEW, not BETA: `GET /helix/clips/downloads`, 100 requests/min, scope `editor:manage:clips` or `channel:manage:clips`; links are temporary |
| T7 | Ban/timeout | AUTOMOD §1.1 | API reference, Ban User | VERIFIED | `POST /helix/moderation/bans`, `moderator:manage:banned_users`; timeout 1 s to 1,209,600 s (2 weeks) |
| T8 | Delete chat message | AUTOMOD §1.1 | API reference | VERIFIED | `DELETE /helix/moderation/chat`, `moderator:manage:chat_messages` |
| T9 | Approve/deny held AutoMod message: endpoint "not found" | AUTOMOD §1.1 | API reference, Manage Held AutoMod Messages | **CORRECTED** (exists) | `POST /helix/moderation/automod/message`, `moderator:manage:automod` |
| T10 | Warn chat user: scope unconfirmed | AUTOMOD §1.1 | API reference | **CORRECTED** (now known) | `POST /helix/moderation/warnings`, `moderator:manage:warnings`; EventSub `channel.warning.send` needs `moderator:read:warnings` or `moderator:manage:warnings` |
| T11 | Other moderation scopes | AUTOMOD §1.1 | API reference, EventSub types | VERIFIED | Update AutoMod Settings `moderator:manage:automod_settings`; AutoMod level 0 to 4; Shield Mode `moderator:manage:shield_mode`; announcements `moderator:manage:announcements` (1 per 2 s); `automod.message.hold` needs `moderator:manage:automod`; `channel.suspicious_user.message` needs `moderator:read:suspicious_users`; `channel.chat.message_delete` needs `user:read:chat`; `channel.follow` v2 `moderator:read:followers`; `channel.subscribe` `channel:read:subscriptions` |
| T12 | Chat send limits: 20 per 30 s (100 for mod/VIP) | REALITY-CHECK §1, LEGAL §3.1 | dev.twitch.tv/docs/chat/ | VERIFIED | Non-mod 20 per 30 s; broadcaster/moderator/VIP 100 per 30 s; 1 message per second per channel for non-mod; **verified** bots 7500 per 30 s. Over the limit: messages ignored "for 1 hour" |
| T13 | Ignored "30 to 60 min" after exceeding | REALITY-CHECK §1 | same | **CORRECTED** | 1 hour |
| T14 | "Verified-bot reviews are paused" | REALITY-CHECK top risks | same | **CORRECTED / UNVERIFIED** | The page says only that verified status "is rarely granted"; apply via a form; determination by email. No pause notice found |
| T15 | Send Chat Message scopes | REALITY-CHECK §1 | API reference | VERIFIED | `user:write:chat`; with an app token also `user:bot` plus `channel:bot` from the broadcaster unless the sender is a moderator. Own rate bucket separate from the normal bucket; 500 chars max |
| T16 | Whispers: 40 unique recipients/day, 3/s | REALITY-CHECK §1 | API reference | VERIFIED | 40 unique/day, 3/s, 100/min; scope `user:manage:whispers` |
| T17 | EventSub: WebSocket needs user token; 3 connections; 300 subscriptions; `max_total_cost` inconsistent | SOCIAL §2.1 | dev.twitch.tv/docs/eventsub/manage-subscriptions/ and handling-websocket-events | VERIFIED (conflict is real) | User token required for WebSocket; 3 connections; 300 enabled subs each; text says "max_total_cost is 10 across all subscriptions" while the sample responses show 10000. Subscriptions needing the user's authorization cost 0; `stream.online`/`channel.update` cost 1 unless the user authorized the app |
| T18 | API rate limit bucket | AUTOMOD §1.1 | dev.twitch.tv/docs/api/guide/ | VERIFIED | Token bucket per client ID per user per minute; sample header `Ratelimit-Limit: 800`; 429 when empty |
| T19 | Developer Services Agreement: 24 h cache, deletion, chat logs, no false follows | SOCIAL §2.1, LEGAL §3.1 | legal.twitch.com/en/legal/developer-agreement/ (last modified 12/04/2024) | VERIFIED | Cache "for only a twenty-four hour time period"; delete data "upon ... revocation ... or upon Twitch's or the end user's request"; chat logs only "as long as necessary for the operation of Your Services or to improve Your Services" and honor opt-outs; no bots with "false follows"; Twitch Data may not be sold or licensed |
| T20 | DSA "6 months" figure | LEGAL §3.1 | same | UNVERIFIED (not present) | No 6-month data-retention figure appears in the agreement |
| T21 | DSA / ToS on AI training | LEGAL §3.1 | same | not present | No generative-AI clause in the Developer Services Agreement; ToS bars "robot, spider, scraper, crawler, or other automated means" |
| T22 | Minimum age 13 (16 in Australia) | SOCIAL §1.2 | legal.twitch.com/en/legal/terms-of-service/ | VERIFIED | "at least 13 years old (or the minimum age required where you live ...)"; 16 in Australia; under-majority needs parent/guardian supervision |
| T23 | DMCA repeat infringer | MARKETING | legal.twitch.com/en/legal/dmca-guidelines/ | VERIFIED | "repeat infringer if they accrue three copyright strikes"; strikes not permanent; Copyright School may remove one |
| T24 | Rerun label, 24/7 and Always On rules, 48-hour broadcast limit | REALITY-CHECK §1, LEGAL §3.1/3.6, MARKETING §3.2 | help.twitch.tv (not readable) | UNVERIFIED | A search snippet of the help article describes a "Rerun" checkbox and "[Rerun]" prefix; no 48-hour figure was found anywhere. Owner must read the help page |
| T25 | AI-content disclosure rule on Twitch | SOCIAL §4.2, LEGAL §3.1 | none found | UNVERIFIED | No Twitch policy page mentioning a disclosure requirement was retrievable |
| T26 | "Training for Generative AI" channel setting (Aug 2026, on by default) | LEGAL §3.1 | twitch.tv/settings/security (login) | UNVERIFIED (primary) | Many outlets report launch 2026-08-12, location Settings, Security and Privacy. The Twitch Privacy Notice and Privacy Choices pages fetched contain no mention. Owner must check the toggle |
| T27 | Music / "viewership tampering" wording | MARKETING, SOCIAL §3 | help.twitch.tv, Community Guidelines (JS) | UNVERIFIED | No body text retrievable |

### 2.3 TikTok

| ID | Claim | Source doc, section | Primary URL | Verdict | Verified value |
|---|---|---|---|---|---|
| K1 | Unaudited clients: private only, 5 users per 24 h | SOCIAL §2.3, LEGAL §3.3 | developers.tiktok.com/doc/content-sharing-guidelines (updated Aug 4, 2026) | VERIFIED | "all content uploaded via this endpoint will be restricted to private viewing mode"; "up to 5 users to post in a 24 hour window"; only `SELF_ONLY`; error `unaudited_client_can_only_post_to_private_accounts` |
| K2 | Posting cap about 15/day per creator | SOCIAL §2.3 | same | VERIFIED | "typically around 15 posts per day/ creator account", shared across all Direct Post clients; also an audit-based "24-hour active creator cap" |
| K3 | **Intended use** (not in earlier docs) | none | same | NEW, decision-relevant | Not acceptable: "A utility tool to help upload contents to the account(s) you or your team manages." Clients must also "be intended for a wide audience". A single-owner Brand Ops publisher is therefore outside the stated Direct Post intent, audit or not |
| K4 | Direct Post UX contract (no default privacy, interaction off by default, nickname shown, consent declaration) | SOCIAL §2.3 | same | VERIFIED | As written; also commercial-content disclosure toggle off by default, preview required, no watermarks |
| K5 | Upload-to-inbox draft: 5 pending shares per 24 h | SOCIAL §2.3 | developers.tiktok.com/doc/content-posting-api-reference-upload-video | VERIFIED | "at most 5 pending shares within any 24-hour period" (`spam_risk_too_many_pending_share`); scope `video.upload`; 6 requests/min per token; user must click the inbox notification to finish |
| K6 | App review needed before any API use; "days to two weeks" | SOCIAL §1.2, §2.3 | developers.tiktok.com/doc/app-review-guidelines | VERIFIED (rules) / UNVERIFIED (timing) | Needs a custom app name (no social-media brand names), demo video(s) (max 5 videos, 50 MB each) showing the end-to-end flow, sandbox for first review; mobile apps must be in the stores. No review duration on the page |
| K7 | Audit timeline "2 to 4 weeks" | SOCIAL §2.3 | none | UNVERIFIED | The audit form/process is not described on the pages fetched |
| K8 | LIVE: 18+ and about 1,000 followers | SOCIAL §1.3, LEGAL §3.3 | tiktok.com/live/creator-networks/en/blog/how-to-go-live-on-tiktok | 18+ VERIFIED; **1,000 UNVERIFIED** | "Be at least 18 years old (or meet the age of majority in the relevant country or region)." "Have the required number of followers, which may vary by region" with no number. Search results with 1,000 / 50 are creator videos, not policy |
| K9 | AI-generated content label | SOCIAL §4.2, MARKETING §3.4 | tiktok.com/safety/en/policies-and-engagement/integrity-authenticity (Community Guidelines "2026H2update", released Aug 25, effective Sept 24, 2026) | VERIFIED | "we require creators to label AI-generated or significantly edited content that shows realistic-looking scenes or people"; unlabeled content "may be removed, restricted, or labeled". API: Direct Post field `is_aigc` adds the "Creator labeled as AI-generated" tag |
| K10 | "Automation tools, scripts, or other tricks designed to bypass our systems" | SOCIAL §1.1, §3 | same | VERIFIED | Same Integrity page: "We strictly prohibit automation tools, scripts, or other tricks designed to bypass our systems" |
| K11 | Terms bar generative-AI features via bots | SOCIAL §3 | tiktok.com/legal/page/us/terms-of-service/en §3.10 | **CORRECTED (scope)** | The clause is "Use generative AI-enabled features via any automated system or software, including automated 'bots,' unless otherwise authorized". It governs using TikTok's own gen-AI features. It does not restrict posting our own AI-voiced content or LLM-drafted replies |
| K12 | Developer ToS on automated generative AI | task brief | tiktok.com/legal/page/global/tik-tok-developer-terms-of-service/en | **Not present** | Keyword search of the full text finds no generative-AI clause. It licenses "use automated means in your Application to collect information from or otherwise interact with the TikTok Developer Services" within the documentation, and bars bots that "collect information about users ... for any unauthorized purposes" |
| K13 | Unattended/static LIVE disfavored | REALITY-CHECK §3 | none | UNVERIFIED | No LIVE-policy text retrievable |

### 2.4 Instagram / Meta

| ID | Claim | Source doc, section | Primary URL | Verdict | Verified value |
|---|---|---|---|---|---|
| M1 | Publishing cap 100 vs 50 per 24 h | SOCIAL §2.4, LEGAL §3.4 | developers.facebook.com/documentation/instagram-platform/content-publishing and .../reference/ig-user/content_publishing_limit | **CONFLICT inside Meta's docs; plan for 50** | Content Publishing guide "Rate Limit": "limited to 100 API-published posts within a 24-hour moving period". The same guide's carousel Limitations: "limited to 50 published posts within a 24-hour period". The `content_publishing_limit` reference says `quota_total` is "currently `50`", and its example returns `quota_total: 50`, `quota_duration: 86400`. The reference that reports the live number says 50; read it per account |
| M2 | Containers expire 24 h; 400-container cap | SOCIAL §2.4 | .../reference/ig-user/media | VERIFIED (was 3P) | "Containers expire after 24 hours"; "can only create 400 containers within a rolling 24 hour period"; Reels container supported (`media_type=REELS`) |
| M3 | Instagram Login needs no Page; Facebook Login needs a linked Page | SOCIAL §1.2, §2.4 | .../instagram-platform/overview | VERIFIED | "If your app implements Facebook Login for Business, your app users' Instagram professional accounts must be connected to a Facebook Page." Instagram Login uses `graph.instagram.com` and permissions `instagram_business_basic`, `instagram_business_content_publish`; Facebook path uses `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`. Both path tables list Standard and Advanced access |
| M4 | Own account = Standard Access, no App Review/Business Verification | SOCIAL §1.2 | same | VERIFIED | "If your app only serves your Instagram professional account or an account you manage, Standard Access is all your app needs." Advanced Access "requires App Review and Business Verification" |
| M5 | Page Publishing Authorization | none | content-publishing guide | NEW | A connected Page that requires PPA blocks publishing until PPA is done (Facebook Login path) |
| M6 | Platform Terms: "bots at very high frequencies" | SOCIAL §3 | developers.facebook.com/devpolicy/ (updated Feb 3, 2026) | **CORRECTED (context)** | The quote is in section 5, the Messenger / Instagram Messaging policy: spam "includes behavior creating bots either manually or automatically, at very high frequencies". It is not a general posting rule. Section 6 (Instagram Platform): "Don't use the Instagram Platform to simply display User Content, import or backup content, or manage Instagram relationships, without our prior permission." Section 9 Live API: no looping or static streams on the Facebook Live API |
| M7 | Automated Data Collection Terms need written permission | SOCIAL §1.1, §3 | facebook.com/legal/automated_data_collection_terms | UNVERIFIED | Page body not retrievable (JavaScript) |
| M8 | "AI info" label rules | SOCIAL §4.2 | help.instagram.com | UNVERIFIED | Help Center body not retrievable |
| M9 | April 2026 recommendation change on reposted content | SOCIAL §3 | help.instagram.com/1800814370401535 | UNVERIFIED | A search for it found only the 2024-04-30 originality update; the 2026 item was not found on any official page |
| M10 | Insights / BUC rate formula / webhooks / DM 24 h window | SOCIAL §2.4 | not re-fetched | UNVERIFIED | Out of the priority list; left as excerpt-level |

### 2.5 Discord

| ID | Claim | Source doc, section | Primary URL | Verdict | Verified value |
|---|---|---|---|---|---|
| D1 | AutoMod rule limits | AUTOMOD §1.3 | docs.discord.com/developers/resources/auto-moderation | VERIFIED | Per guild: KEYWORD 6, SPAM 1, KEYWORD_PRESET 1, MENTION_SPAM 1, MEMBER_PROFILE 1. `keyword_filter` max 1000 (60 chars each), `regex_patterns` max 10 (260 chars), `allow_list` 100 (KEYWORD) or 1000 (preset), `mention_total_limit` max 50, `exempt_roles` 20, `exempt_channels` 50 |
| D2 | AutoMod actions | AUTOMOD §1.3 | same | VERIFIED | BLOCK_MESSAGE (custom message "maximum of 150 characters"), SEND_ALERT_MESSAGE, TIMEOUT (max 2419200 s = 4 weeks; only KEYWORD and MENTION_SPAM rules; needs `MODERATE_MEMBERS`), BLOCK_MEMBER_INTERACTION |
| D3 | Privileged intents: self-serve under 100 servers, approval above | LEGAL §3.5 | docs.discord.com/developers/events/gateway | **CORRECTED** | "For verified apps (required for apps in 100+ guilds), the intent must also be approved". Separately: "Apps with fewer than 10,000 users can access privileged intents by enabling them in the Developer Portal"; above 10,000 unique users review is required. Message Content: apps without it get empty `content` except in DMs with the app, messages that mention the app, and the app's own messages |
| D4 | Developer Policy / Developer ToS text (deletion duty, AI training) | LEGAL §3.5 | support-dev.discord.com (HTTP 403 Cloudflare) | UNVERIFIED | Not readable |

### 2.6 Counts

Counted by table row (75 rows). Rows with a verified part and an unverified part are counted under the part that gates a decision.

| Verdict | Count | Rows |
|---|---|---|
| VERIFIED | 44 | includes new findings K3, M5, Y11 |
| CORRECTED | 12 | Y2, Y16, Y19, T5, T6, T9, T10, T13, T14, K11, M6, D3 |
| CONTRADICTED / conflict in the primary sources | 3 | Y8, T2, M1 |
| STILL UNVERIFIED | 16 | Y5, Y12, Y17, T20, T24, T25, T26, T27, K7, K8, K13, M7, M8, M9, M10, D4 |

## 3. Findings by topic and the decisions they change

### 3.1 YouTube

- **Upload quota is far better than the earlier docs assumed (Y1, Y2).** A `videos.insert` costs 1 unit in a bucket of 100 calls/day that is separate from the 10,000-unit pool. PLATFORM-REALITY-CHECK §5 ("1,600 units, about 6 uploads/day") is stale. The binding limit is now 100 uploads/day, which is irrelevant at our volume. Decision: drop the upload quota from the Brand Ops failure-mode list (SOCIAL §5.7); keep the 10,000-unit pool, which still limits live chat and moderation.
- **Live chat arithmetic (Y3, Y4, Y6).** list 5, insert 20, delete 20, bans 200. At 200 units a ban, 50 API bans empty the day's pool. `streamList` is 5 units per call; whether a held-open stream is billed once or per push is not documented, so measure the first week in the Cloud Console before sizing the reply rate.
- **The "private lock" is no longer safe to assume either way (Y8).** The 2020 history entry says unverified projects are locked private. The current `videos.insert` reference says they are not. Google has not reconciled the two. Decision: keep the read-back-after-publish check (SOCIAL §5.7), and do one real test upload on a fresh Cloud project before building a "public auto-publish needs an audit" gate into a spec.
- **Weekly re-consent is real (Y10, Y11).** A Testing-status external app loses refresh tokens every 7 days. Moving to In production removes that, but the app then shows the unverified screen and is capped at 100 new users for life until verified. For one owner account that cap is not a problem, but Google verification (Y12) is a likely step if `youtube.upload` is sensitive; classification still needs a Cloud Console check.
- **Disclosure (Y14).** Gameplay footage and own-voice cloning are explicitly exempt from disclosure. Sim footage is therefore fine. A generic TTS voice is on neither list; the test is whether it is realistic. The house rule (label TTS conservatively, Q-AI-6) stays optional, not required, on YouTube. The API exposes `status.containsSyntheticMedia` on `videos.insert`, so the PublisherPort can set it.
- **Inauthentic content (Y13)** stays a YPP monetization rule about mass-produced or templated channels. It says nothing about live streams. No change to the plan not to automate Shorts.
- **Live enablement (Y16).** First enablement "may take up to 24 hours"; one phone number can verify at most 2 channels a year; streamers must be 16+. Start the wait early.
- **Developer deletion duties (Y19)** are 7 days (in-app revocation) and 30 days (revoked via Google settings). Spec the 7-day path.

### 3.2 Twitch

- **Affiliate bar is verified (T1)** and Twitch emails or notifies qualifying streamers on its own. Channel Points are being opened to everyone (T2), so do not design around Affiliate-only rewards; but the API may still answer 403 for non-Affiliates while the rollout is US-first. Handle 403 as an expected state.
- **Moderation scopes are fully known now (T7 to T11).** A bot account that is a moderator needs `moderator:manage:banned_users`, `moderator:manage:chat_messages`, `moderator:manage:automod` (held-message approve/deny exists), `moderator:manage:warnings`. Update AUTOMOD §1.1 accordingly; the endpoint "not found" gap is closed.
- **Chat limits (T12 to T14).** 20 per 30 s normal, 100 per 30 s for a moderator, 1 message per second per channel for non-moderators, ignored for 1 hour on breach. Verified bots exist (7500) but are "rarely granted"; no pause notice was found. Decision unchanged: the bot is a moderator and acknowledgements are aggregated on the overlay.
- **EventSub (T17).** The `max_total_cost` conflict is inside Twitch's own docs. Because our subscriptions are for users who authorized the app (cost 0), the cap mostly does not bite. Do not rely on 10000.
- **Data handling (T19).** 24 h cache of Twitch content unless authorized; delete on revocation or request; chat logs only as long as needed, with opt-out honored. Replay storage of viewer chat needs a retention rule that fits these words.
- **Unreadable:** reruns, the 48-hour limit, Always On, music rules, the AI-training toggle, AI disclosure (T24 to T27). All sit behind Twitch's JavaScript help portal.

### 3.3 TikTok

- **New and decision-relevant (K3).** Direct Post's Intended Use says a tool to upload to accounts "you or your team manages" is not acceptable and the client should serve a wide audience. A solo-owner publisher fails that on its face. Decision: for TikTok, plan the **inbox-draft (`video.upload`) path or manual posting** only, and do not budget an audit for Direct Post. ADR-0008's "TikTok is P5" stays. Whether inbox upload needs an audit is not stated on the pages read.
- **Unaudited limits (K1, K2, K5)** are verified as previously written; inbox drafts cap at 5 pending shares per 24 h.
- **LIVE (K8).** 18+ is official; the follower count is not published on any official page found. Do not put "1,000" in a spec.
- **AI labels (K9)** are mandatory for realistic AI scenes or people in the 2026H2 guidelines (effective 2026-09-24); the API has `is_aigc`. The "automated generative AI" clause (K11) is about TikTok's own gen-AI features, so it is not a reason to avoid LLM-drafted posts.

### 3.4 Instagram / Meta

- **The 100 vs 50 conflict (M1)** is inside Meta's documentation. Use 50 as the planning number and read `quota_total` from `content_publishing_limit` per account at runtime.
- **No Page needed with Instagram Login (M3)**; Standard Access covers an owner-only app with no App Review or Business Verification (M4). Both verified. A Facebook Page adds Page Publishing Authorization risk (M5).
- **The "very high frequency bots" quote (M6)** is a messaging-spam rule, not a posting rule. The relevant Instagram Platform rule is the narrower "do not simply display User Content, import or backup content, or manage Instagram relationships".
- **Not verified:** AI info label, the April 2026 repost change, and the Automated Data Collection Terms (M7 to M9). Keep the "never auto-follow, auto-DM or reshare others' clips" rule; it needs no confirmation to stay in force.

### 3.5 Discord

- AutoMod limits (D1, D2) are now exact; only 6 keyword rules per server, so rule design must bundle terms. A bot-created rule can time out only on KEYWORD and MENTION_SPAM rules.
- Intents (D3): verification becomes mandatory at 100 or more servers and then the Message Content intent must be approved; below that, toggle it in the portal. Slash-command and component bots need none of this.

## 4. Corrections to existing docs

| File | Section | Old text | New text |
|---|---|---|---|
| docs/review/PLATFORM-REALITY-CHECK.md | §5 YouTube | "`videos.insert` historically costs 1,600 units, about 6 uploads/day **[a newer cost is UNVERIFIED]**" | "`videos.insert` has its own bucket of 100 calls/day at 1 unit per call (quota calculator, revision history 2025-12-04 and 2026-06-01; read 2026-10-18). The 2020 'unverified projects are private' rule conflicts with the current `videos.insert` reference, which says they are not restricted; test with a real upload." |
| docs/review/PLATFORM-REALITY-CHECK.md | §1 Twitch | "Exceeding them makes Twitch ignore the bot for 30–60 min." | "Twitch ignores the bot's messages for 1 hour (dev.twitch.tv/docs/chat/)." |
| docs/review/PLATFORM-REALITY-CHECK.md | Top risks #4 | "Verified-bot reviews are paused." | "Verified bot status is 'rarely granted' (dev.twitch.tv/docs/chat/). No pause notice found." |
| docs/review/PLATFORM-REALITY-CHECK.md | §3 TikTok | "18+ and about 1,000 followers" | "18+ is official; the follower number is not published ('required number of followers, which may vary by region')." |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §2.1 Twitch Clips | "after 15 s assume failure"; "Get Clips Download ... open beta; availability UNVERIFIED" | "after 60 s assume failure"; "Get Clips Download is live (`GET /helix/clips/downloads`, 100 req/min, `editor:manage:clips` or `channel:manage:clips`)." |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §1.3 Affiliate | "reportedly lowered ... [EXCERPT-OFFICIAL]" | "Verified on blog.twitch.tv/en/2026/05/13/monetization-for-all/: 25 followers, 4 hours, 4 days, min 3 ACCV on 4 days; automatic email and Creator Dashboard notice." |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §2.1 Channel points | "Affiliate/Partner only (403 otherwise)" | "Twitch opened Channel Points to all streamers starting May 2026 (US first); the API reference still lists a 403 for non-Affiliates. Treat 403 as a handled state." |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §2.2 | "Quota model changed in 2026 ... [CONFLICT]" | "Verified (quota calculator, 2026-10-18): 10,000 units + 100 `videos.insert` + 100 `search.list` per day; `videos.insert` costs 1 unit in its bucket." |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §2.2 Unverified project lock | "locked to private ... until a compliance audit passes" | "Conflict in Google's docs: the 2020 history entry says private-locked; the current `videos.insert` reference says not restricted. Test before relying on either." |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §2.3 Content Posting | (no mention) | Add: Direct Post Intended Use says a utility to upload to accounts "you or your team manages" is not acceptable. Use inbox drafts or manual posting for our own account. |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §2.4 Instagram | "100 ... but a third-party reading cites 50 [CONFLICT]" | "Meta's own pages disagree: the publishing guide says 100 (Rate Limit) and 50 (carousel Limitations); the `content_publishing_limit` reference says `quota_total` is 'currently 50'. Plan for 50; read the live value." Containers: expire after 24 h, 400 containers per rolling 24 h (verified). |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §3 table row "Cross-posting" and §3 first row | Meta "creating bots ... at very high frequencies" as a general rule | The wording is in the Messenger/Instagram Messaging section of the Developer Policies (updated 2026-02-03). |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §3 "Auto-replying" row | TikTok terms bar generative-AI features via bots, "a further reason not to automate TikTok replies" | The clause covers using TikTok's own gen-AI features via bots (consumer Terms §3.10). It does not apply to our own LLM-drafted text. |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §4.2 YouTube row | "from May 2026 YouTube may auto-label" | Auto labels apply to YouTube GenAI tools, C2PA metadata, or detection; no May 2026 date on the page. "Gameplay footage from video games" and "Cloning one's own voice" are listed as not needing disclosure. |
| docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md | §1.3 YouTube live | "a number can verify a limited number of channels per year" | "no more than 2 channels per year; up to 24 hours for first enablement; 16+ to live stream." |
| docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md | §3.2 API Services row | "~30-day cycle ... 30 days" | "Delete within 7 calendar days of in-app revocation; within 30 calendar days of revocation via Google security settings; non-authorized stats not stored over 30 days (Developer Policies, updated 2026-10-15)." |
| docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md | §3.1 Developer agreement | "forum answers ... may be stored beyond the 24 h figure" | "The agreement (last modified 12/04/2024) allows caching Twitch content 'for only a twenty-four hour time period' unless authorized; deletion on revocation or request; chat logs only as long as necessary; no '6 months' figure exists in the text." |
| docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md | §3.5 Discord | "self-serve below 100 servers and need approval above" | "Verification is required at 100+ servers, and verified apps need intent approval; below 10,000 users intents are toggled in the portal; above 10,000 unique users review is required (docs.discord.com gateway)." |
| docs/review/LEGAL-AND-NAME-SWEEP-2026-10-18.md | §3.3 TikTok LIVE | "about 1,000 followers" | 18+ official; follower number unpublished. |
| docs/review/AUTOMOD-AND-PRIVACY-ANALYTICS-RESEARCH.md | §1.1 table | "Held-message handling ... Helix endpoint ... not found"; "Warn ... scope not confirmed" | `POST /helix/moderation/automod/message` with `moderator:manage:automod`; `POST /helix/moderation/warnings` with `moderator:manage:warnings`; `channel.warning.send` needs `moderator:read:warnings` or `moderator:manage:warnings`; `channel.suspicious_user.message` needs `moderator:read:suspicious_users`. |
| docs/review/AUTOMOD-AND-PRIVACY-ANALYTICS-RESEARCH.md | §1.2 quota | "partly garbled ... [CONFLICT]" | All costs verified on the quota calculator: ban/unban 200, delete 20, insert 20, list 5, streamList 5. |
| docs/review/AUTOMOD-AND-PRIVACY-ANALYTICS-RESEARCH.md | §1.3 Discord | "Mention spam limit range [3P]" | `mention_total_limit` max 50; 6 KEYWORD rules, 1 each of SPAM, KEYWORD_PRESET, MENTION_SPAM, MEMBER_PROFILE per server; TIMEOUT max 4 weeks. |
| docs/review/MARKETING-AND-PRODUCTION-RESEARCH.md | §3.3 | "[EXCERPT-OFFICIAL via a search summary ... threshold undisclosed]" | Verified on support.google.com/youtube/answer/10059070: a Shorts view counts when it "starts to play or replay, with no minimum watch time" from 2025-03-31; old metric is "Engaged views"; YPP uses engaged views. |

## 5. STILL UNVERIFIED, with the reason and the owner's manual step

| Item | Reason | Manual step |
|---|---|---|
| Y8: do unverified projects upload as private? | Google's own docs disagree | Create the Cloud project, upload one test video with `privacyStatus=public`, and read the result in Studio. Record the outcome in the ops repo |
| Y5: streamList billing model | Not documented | Run a one-hour stream and read the Cloud Console quota graph |
| Y12: is `youtube.upload` sensitive/restricted? | No scope table with classification found | Cloud Console, OAuth consent screen, Data Access: scopes are labelled there |
| Y17: mobile live needs 50 subscribers | Help page not found | Read the Live requirements in YouTube Studio; not needed for encoder streams |
| T24: rerun label, 24/7 and Always On rules, 48-hour broadcast limit | help.twitch.tv is a JavaScript shell | Read the Twitch Help articles on Reruns, Always On and stream length in a browser; ask support about the 48-hour figure |
| T25: Twitch AI-content disclosure rule | No page found | Read the Community Guidelines in a browser; record the date |
| T26: "Training for Generative AI" toggle | Only press coverage; privacy pages fetched do not mention it | Open twitch.tv/settings/security, find the toggle, set it, screenshot into the ops repo |
| T27: music rules, viewership tampering wording | JavaScript shells | Read Twitch Help "music" and Community Guidelines in a browser |
| K6/K7: TikTok app review and audit durations | Not on the pages read | Submit the review and note the date; ask developer support for audit time |
| K8: TikTok LIVE follower threshold | Not published on official page | TikTok Studio, LIVE section shows eligibility for the account |
| K13: unattended LIVE policy | No policy text retrievable | Read TikTok LIVE guidelines in the app Help Center |
| Whether inbox-draft upload needs an audit | Pages read cover only Direct Post restrictions | Ask TikTok developer support when the app is registered |
| M7/M8/M9: Meta Automated Data Collection Terms, "AI info" label rules, April 2026 repost recommendation change | help.instagram.com and facebook.com/legal render with JavaScript | Read them in a logged-in browser; the April 2026 item was not found by search either (only the 2024-04-30 originality update appeared) |
| M10: Insights/BUC formula, webhooks, DM window | Not re-fetched (outside the priority list) | Re-read the Instagram Platform docs before building the Insights/DM adapters |
| D4: Discord Developer Policy and Developer Terms | Cloudflare challenge (HTTP 403) | Read support-dev.discord.com Developer Policy in a browser; confirm the deletion duty and any AI-training clause |
