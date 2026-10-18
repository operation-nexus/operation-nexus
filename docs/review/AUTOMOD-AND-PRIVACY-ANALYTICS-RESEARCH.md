# Auto-Moderation and Privacy-Preserving Analytics Research

> Verification status (2026-10-18): corrected against primary sources in [PLATFORM-POLICY-VERIFICATION-2026-10-18](PLATFORM-POLICY-VERIFICATION-2026-10-18.md) and [LICENSE-AND-MUSIC-VERIFICATION-2026-10-18](LICENSE-AND-MUSIC-VERIFICATION-2026-10-18.md). Inline [CORRECTED 2026-10-18] notes mark changed claims; [VERIFIED 2026-10-18] marks confirmed ones.

Date: 2026-10-18 · Status: research, not a spec · Tracker: NX-329 · Owner request: (1) research an auto-moderator that can reject, delete, time out or ban when Twitch or YouTube tooling misses something, (2) analytics that inform the owner while minimizing tracking and staying transparent.
Related: ADMIN-RBAC §4 and §6.8, CHAT-GATEWAY, IDENTITY, THREAT-MODEL (SEC-MOD, SEC-GW, SEC-DATA), OPS-ADMIN, Q-MOD-1…6, Q-DM-3, ADR-0010, [SOCIAL-CHANNEL-AUTOMATION-RESEARCH](SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md), [MARKETING-AND-PRODUCTION-RESEARCH](MARKETING-AND-PRODUCTION-RESEARCH.md) (§5 community and moderation operations is not repeated here).

Terminology: an **Operator** is a player only. People who work in the Command Center are **staff**. The player coalition is the **Quorum**; the enemy is the **Static**. (In the specs a player is still sometimes written "commander"; this document uses "Operator" for a person playing and `commander_id` only for the database key.)

## 0. How to read this document (evidence quality)

**Nothing here was read from a primary page.** On 2026-10-18 every direct fetch failed (section 7.1): `WebFetch` returned `getaddrinfo ENOTFOUND` for every host tried, and `curl` through the agent proxy returned no HTTP status (exit code 000) for every host tried. All external facts below come from **web-search result excerpts**, which are summaries that sometimes quote official pages. Per AGENTS.md rule 0, every external fact carries a tag:

| Tag | Meaning |
|---|---|
| `[EXCERPT-OFFICIAL]` | A search excerpt that reported text attributed to an official page of the vendor or platform (URL in section 7). Re-read the live page before building on it. |
| `[3P]` | Reported only by a third-party site (blog, library docs, review site, aggregator). A lead, not a fact. |
| `[CONFLICT]` | Sources disagree. |
| `[UNVERIFIED]` | Not found in any source this session, or recalled without a source. Do not rely on it. |
| `[DESIGN]` | Our own proposal, not an external fact. PROPOSED values are tunable and need an owner decision. |

No prices, accuracy numbers or quotas are invented. Where none were found, the cell says so. Nothing here is a spec; adopting any of it needs a spec change and a tracker ID (rule 1).

**Summary for the owner**

1. Twitch and YouTube already give you a lot for free (section 1). The **cheapest, most robust auto-moderator is not a classifier**: it is our existing normalization plus denylist pipeline (SEC-MOD-1) applied to chat, wired to the platforms' own tools through a bot that is a channel moderator. A classifier or an LLM adds a second opinion for a small slice of messages and should come later.
2. **Perspective API, the best-known free classifier, is reported to shut down at the end of 2026** (section 3.3) [VERIFIED 2026-10-18 on perspectiveapi.com: "The service will remain active until December 31, 2026" and "we will not be offering direct migration support"; LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-60]. Do not design around it.
3. Bots such as Fossabot, Nightbot, Moobot, StreamElements and Streamlabs Cloudbot cover spam, caps, links and word filters well. They cannot read our game state or ban across the game. **Compose**: use one of them (or just the platforms' native tools) for generic chat hygiene, and build only the Nexus-specific part (callsign and command-text moderation, cross-platform ban sync, game-aware rules).
4. Auto-actions should stop at **delete and short timeout**. A permanent platform ban and any game ban need a human, which matches ADMIN-RBAC §6.8 ("Bans always need a human") and the owner's reversibility rule.
5. For analytics, the first-party game ledger (Q-DM-3) answers almost every question you listed. **A conflict to resolve:** Q-DM-3 says "no ... analytics scripts on overlay or site", which would also rule out a self-hosted cookieless script. Section 5 offers script-free options and asks for an explicit owner call.
6. Mods are volunteers with **no response-time obligation**. The design uses opt-in slots, a visible coverage display for staff, and the kill switch plus auto-pause as the safety net, so nobody needs to be on call.

---

## 1. Platform-native moderation (what exists for free)

### 1.1 Twitch

**Built-in tools** (all free, no approval):

| Tool | What it does (from excerpts) | Tag |
|---|---|---|
| AutoMod | Holds messages it judges risky for a human to approve or deny. A 2026 guide describes four sensitivity levels over four categories (hate, sexual content, hostility, profanity); another guide uses a different level naming. Names and numbering are not settled. | `[3P]` `[CONFLICT]` [S1] |
| Blocked terms and permitted terms | Two customizable lists that augment AutoMod. Blocked terms are stopped without moderator action. Permitted terms let a word through unless another flagged term is in the same message. A 2017 official post says moderator actions can add terms to the lists over time. | `[EXCERPT-OFFICIAL]` [S2] |
| Shield Mode | A one-click "lockdown" bundle of safety settings (hotkey or `/shield`, released with `/shieldoff`), reported to have launched 2022-11-30. Also reported to add "no first-time chatters" and bulk ban. | `[3P]` [S1] [S3] |
| Suspicious User Detection | A machine-learning model that flags likely and possible ban evaders. Messages from "likely" accounts are hidden from public chat but visible to mods; "possible" accounts chat normally but mods are alerted. On by default and adjustable. Twitch says it does not ban automatically because false positives are possible. | `[3P]` (launch-period coverage) [S4] |
| Chat settings | Slow mode, followers-only, subscribers-only, emote-only, unique-chat. Not individually sourced this session. | `[UNVERIFIED]` |
| Moderator and VIP roles | A moderator can ban, time out, delete messages and (per excerpts) review held messages. Not individually sourced. | `[UNVERIFIED]` |

**What a bot can do through the API.** Helix (REST) and EventSub (events) are the official bot surface (CHAT-GATEWAY §2 already plans EventSub). Facts reported this session:

| Capability | Endpoint or event, scope | Tag |
|---|---|---|
| Ban or time out a user | Helix Ban User (`POST /moderation/bans`); scope `moderator:manage:banned_users`, which also covers unban; timeout 1 s to 1,209,600 s (2 weeks) | `[VERIFIED 2026-10-18]` [S5] (PLATFORM-POLICY-VERIFICATION-2026-10-18 T7) |
| Delete a chat message | Helix Delete Chat Messages (`DELETE /moderation/chat`); scope `moderator:manage:chat_messages` (also covers pinned messages) | `[VERIFIED 2026-10-18]` [S5] (PLATFORM-POLICY-VERIFICATION-2026-10-18 T8) |
| Warn a user | Helix Warn Chat User exists (open beta announcement); the user must acknowledge before chatting. Endpoint `POST /helix/moderation/warnings`, scope `moderator:manage:warnings` [CORRECTED 2026-10-18: was "Its scope was not confirmed"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T10]. EventSub `channel.warning.send` and `channel.warning.acknowledge` exist; `channel.warning.send` needs `moderator:read:warnings` or `moderator:manage:warnings`. | `[VERIFIED 2026-10-18]` [S7] |
| Held-message handling | EventSub `automod.message.hold` needs `moderator:manage:automod`; its v2 payload adds the reason, term and position. Held messages end as Approved, Denied or Expired. The Helix endpoint to approve or deny a held message is `POST /helix/moderation/automod/message`, scope `moderator:manage:automod` [CORRECTED 2026-10-18: was "not found in excerpts"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T9]. | `[VERIFIED 2026-10-18]` [S8] |
| Read and change AutoMod settings | Update AutoMod Settings: `moderator:manage:automod_settings`; read: `moderator:read:automod_settings` | `[EXCERPT-OFFICIAL]` [S9]; the manage scope and AutoMod levels 0 to 4 are `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 T11) |
| Shield Mode control | Get and Update Shield Mode Status, scope `moderator:manage:shield_mode`; announced as open beta, current status unknown | `[EXCERPT-OFFICIAL]` [S10]; the scope is `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 T11) |
| Moderation events | EventSub `channel.moderate` (replaces the legacy moderator-actions topic; needs `channel:moderate` plus several other scopes), `channel.chat.message_delete` (scope `user:read:chat`), `channel.suspicious_user.message` (scope `moderator:read:suspicious_users`) [CORRECTED 2026-10-18: was "scope not confirmed" for both; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T11] | `[EXCERPT-OFFICIAL]` [S11]; the two scopes are `[VERIFIED 2026-10-18]` |
| Unban requests | Resolve events (approved, denied, canceled) exist; the create event and endpoint scope were not confirmed | `[3P]` [S12] |

Requirements and limits worth knowing:
- **Moderator status.** The user in `moderator_id` must be an active moderator of the broadcaster's channel and must match the token's user; if mod status is removed, calls return 403. `[EXCERPT-OFFICIAL]` [S5] [S6]. This matches CHAT-GATEWAY §2 (bot is a channel moderator).
- **Rate limits.** Helix uses a points bucket; the bucket is per client ID per user per minute, a sample response header shows `Ratelimit-Limit: 800`, and an empty bucket returns 429 [CORRECTED 2026-10-18: was "an app access token is reported at 800 points per minute"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T18]. The ban endpoints were reported to return 429 earlier than the bucket would suggest, so there may be a separate limit. `[3P]` [S13]. Chat-send limits are in CHAT-GATEWAY §2 (100 messages per 30 s as a moderator, existing spec).
- **Scope count.** A moderation bot needs several `moderator:*` scopes on the bot account's user token. Store them like the other refresh tokens (CHAT-GATEWAY §2). Which ones we request should follow least privilege (SEC-API, RB-7).
- **Approvals.** No Twitch review step for these scopes was found in any excerpt. `[UNVERIFIED]` (absence of evidence).

**What this means for us:** a bot account that is a moderator can delete a message and time out or ban a user using only the scopes above, without Twitch app review, as far as the excerpts show. Held-message handling and warnings are available but their exact endpoints need a live-docs read.

### 1.2 YouTube Live

| Feature | What it does | Tag |
|---|---|---|
| Blocked words | Messages containing or closely matching blocked terms are stopped outright (not held). Set in Studio under Community settings, Automated Filters. Applies to comments, live chat and posts. | `[EXCERPT-OFFICIAL]` [S14] |
| Hold potentially inappropriate messages | Opt-in. Flagged messages are held; the creator or a moderator approves, hides or reports them. If no action is taken they stay hidden. | `[EXCERPT-OFFICIAL]` [S14] |
| Links | Messages containing URLs are reported as blocked by default in live chat. | `[EXCERPT-OFFICIAL]` [S14] |
| Approved users | Messages from approved users bypass blocked-word and inappropriate-content filters. | `[EXCERPT-OFFICIAL]` [S14] |
| Moderators | Standard and managing moderators. Managing moderators can change community defaults. | `[EXCERPT-OFFICIAL]` [S14] |
| Ban or hide a user via API | `liveChatBans.insert` with type `permanent` or `temporary` (`banDurationSeconds`, default reported as 300 s); `liveChatBans.delete` lifts it. The request must be authorized by the channel owner or a moderator of that chat. | `[EXCERPT-OFFICIAL]` [S15] |
| Delete a message via API | `liveChatMessages.delete` | `[EXCERPT-OFFICIAL]` [S16] |

**Quota** (default allocation 10,000 units per day, reset at midnight Pacific time `[EXCERPT-OFFICIAL]` [S17]). Reported costs: `liveChatMessages.delete` 20, `liveChatMessages.insert` 20, `liveChatMessages.list` 5, `streamList` 5, `liveChatBans.insert` **200**, `liveChatBans.delete` 200. These were first read from search excerpts of Google's quota page, which the tool itself said were "partly garbled" [CORRECTED 2026-10-18: all costs are verified on Google's quota calculator (ban and unban 200, delete 20, insert 20, list 5, streamList 5 per call); the GitHub claim of 50 for send and delete is wrong; whether a held-open stream is billed once or per push is `[UNVERIFIED]`; was `[EXCERPT-OFFICIAL]` `[CONFLICT]`; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y3, Y4, Y5, Y6]. [S16] [S18] [S19]

Consequences (arithmetic on the reported numbers, `[DESIGN]`):
- At 200 units per ban, 10,000 units allows at most 50 API bans per day, before spending anything on reading chat or replying. CHAT-GATEWAY §3 already budgets reading and a 20-unit reply every 5 minutes (about 288 replies per day, about 5,760 units). Check: 10,000 minus 5,760 leaves about 4,240 units. So the **YouTube budget for auto-moderation is thin** and the quota dashboard (CHAT-GATEWAY §3) must count moderation calls.
- Deleting (20 units) is 10 times cheaper than banning (200 units). On YouTube the auto-moderator should prefer **delete** and rely on YouTube's own blocked words and hold-for-review, which cost no quota, for the bulk of filtering.
- A quota increase needs a compliance audit application (SOCIAL-CHANNEL-AUTOMATION-RESEARCH already covers this path, S44 there).

**What YouTube already does for free:** blocked words, link blocking, hold-for-review, approved-user bypass. **What a bot adds:** the same checks with our confusable folding, cross-platform ban sync, and game-aware rules. **Approvals:** the quota extension audit; no separate review for moderation scopes was found. `[UNVERIFIED]`.

### 1.3 Discord (community server)

| Feature | Detail | Tag |
|---|---|---|
| AutoMod keyword rule | Custom keyword and phrase lists with wildcards (`*`). Actions: block the message (custom block message up to 150 characters), send an alert to a channel, time out the member. Timeout is only available for keyword and mention-spam rules and needs the `MODERATE_MEMBERS` permission. Verified limits: 6 KEYWORD rules per guild, `keyword_filter` max 1000, timeout max 2419200 s (4 weeks). | `[VERIFIED 2026-10-18]` [S20] [S21] (PLATFORM-POLICY-VERIFICATION-2026-10-18 D1, D2) |
| Mention spam rule | A total-mention limit (`mention_total_limit` max 50) with block and timeout actions; one MENTION_SPAM rule per guild (and 1 each of SPAM, KEYWORD_PRESET, MEMBER_PROFILE) [CORRECTED 2026-10-18: was `[3P]` for the limit range; see PLATFORM-POLICY-VERIFICATION-2026-10-18 D1, D2] | `[VERIFIED 2026-10-18]` [S22] |
| Spam rule | Message rate and repetition; official description not found | `[3P]` [S22] |
| Bot access | AutoMod rules are in the Discord developer docs as an API resource, so a bot can create rules and receive rule-trigger events. Exact permissions not read. | `[EXCERPT-OFFICIAL]` [S21] |

Discord AutoMod is free and sits behind the `CommunityBot` port (ADR-0010) only if we script it; configuring it by hand in the server settings needs no code. Server structure, appeals and roles are in MARKETING §5; not repeated.

---

## 2. Existing bots and services

All "free" and "pricing" statements are from search excerpts or vendor pages seen as excerpts; re-check before relying on them.

| Service | Moderation features reported | Hosting | Price or limit | Official API for third parties | Tag |
|---|---|---|---|---|---|
| **Nightbot** | Spam filters: caps, links (with whitelist and regex), emotes, symbols, blacklist words | Cloud, run by vendor | Listed as free; a 3P comparison says no public paid tier is shown. API scope **not confirmed** | `[UNVERIFIED]` | `[3P]` [S23] |
| **Moobot** | Message filters (caps, spam and others), different settings per viewer tier (subscribers, VIPs, regulars) | Cloud | Freemium; premium price not found | `[UNVERIFIED]` | `[3P]` / `[EXCERPT-OFFICIAL]` for filter docs [S24] |
| **Fossabot** | Spam filters, blocked-terms engine, role-based access, audit logs of changes; Twitch, YouTube and Kick | Cloud | Site says free | `[UNVERIFIED]` | `[3P]` and vendor site [S25] |
| **StreamElements chatbot** | Filters: banned words (regex), caps, emotes, links, paragraph length, symbols | Cloud | Pricing of the filters not stated in excerpts | `[UNVERIFIED]` | `[EXCERPT-OFFICIAL]` [S26] |
| **Streamlabs Cloudbot** | Filters: caps, emotes, paragraphs, links, symbols, words; Twitch, YouTube and Kick | Cloud | FAQ says all the functionality including moderation is free; only a custom bot name needs Ultra | `[UNVERIFIED]` | `[EXCERPT-OFFICIAL]` [S27] |
| **Sery_Bot** | Anti-hate-raid and anti-follow-bot: bans such accounts on arrival, can clear chat and switch to subscriber-only during a raid; uses a centralized bot list | Cloud (developer-run) | No pricing found | `[UNVERIFIED]` | `[3P]` [S28] |
| **Discord AutoMod** | See 1.3 | Built into Discord | Free | Developer API exists | `[EXCERPT-OFFICIAL]` [S20] [S21] |

Common weakness for us: none of them can see game state, cannot ban across the game ledger (Q-MOD-3), cannot apply our confusable folding as defined in SEC-GW-1, and they are closed services. Several moderate by posting as a bot that must itself be a moderator. If one of them fails or changes terms, a stream with only that line of defense loses moderation silently (a Nightbot review in the excerpts says features "may break or become unavailable without warning" when platform APIs change `[3P]`).

### Build vs buy vs compose (solo developer, ADR-0010)

| Option | Effort | Control | ADR-0010 fit | Risk |
|---|---|---|---|---|
| **Buy only** (platform tools + one hosted bot) | Lowest | Low | Fine (no code), but the bot is a vendor dependency | Cannot cover callsigns, commands, ban sync |
| **Build only** | High | Full | Fine | Reinvents spam/caps/link filters the platforms already do for free |
| **Compose (recommended)** | Medium | High where it matters | Fine | Two systems to keep in sync: keep the hosted bot optional and stateless |

Recommended composition `[DESIGN]`:
1. Turn on the platform-native tools first (AutoMod, blocked terms, Shield Mode, suspicious-user monitoring, YouTube blocked words and hold-for-review). Zero code.
2. Optionally add one hosted bot for generic spam hygiene during the alpha. It is replaceable and not in the trust path (we assume nothing from it).
3. Build the Nexus-specific moderator behind our own port, reusing code the specs already require: normalization, denylist, callsign approval, ban sync. Add a new capability, not a vendor import in core (N-3).

---

## 3. Our own moderation pipeline

### 3.1 What the specs already define (build on it)

- **Normalization (SEC-GW-1, CHAT-GATEWAY §4):** NFKC, strip control, bidi and zero-width characters, 300-character cap, confusable-folded key for matching, over-length messages rejected not truncated.
- **Moderation pipeline (SEC-MOD-1):** normalization, then denylist with leetspeak and homoglyph folding, then an optional classifier. Display names never render unless approved (Q-MOD-1); unapproved names show a neutral generated callsign. TTS speaks only approved callsigns (SEC-MOD-2).
- **Port:** `ModerationProvider` for text verdicts (ADR-0010, Q-MOD-2: free-first blocklist, free or local classifier if good, cheap hosted check for custom callsigns when needed).
- **Kill switch (SEC-MOD-3, RB-8):** blanks user text, mutes TTS, freezes spawns, bans across platforms; reachable in two taps or one Discord command; works while other admin features are degraded.
- **Conduct (ADMIN-RBAC §6.8, Q-MOD-5):** decaying conduct score, five-step ladder, **bans always need a human**, every step logged and appealable. This governs **in-game** behavior (suicide spam, command spam, repeated blocked-callsign attempts). It is not a chat-content moderator.
- **Ban sync (Q-MOD-3, CHAT-GATEWAY §2):** `channel.ban` and `channel.moderate` events are consumed so a Twitch ban bans the Operator in-game. `SVC_PLATFORM_BOT` has `mod.ban` as "relay only" (ADMIN-RBAC §4.3).

**Gap found:** ADMIN-RBAC defines no role or permission for a bot that *initiates* a platform delete or timeout. `SVC_PLATFORM_BOT` is "relay only" for bans. An auto-moderator that acts on platform chat needs either a new permission or an explicit statement that platform-side delete and timeout are outside the RBAC matrix because they are platform actions under the bot's own platform moderator role. This is an owner decision (O-1 in section 6.4). Per RB-7, service accounts must use minimum scopes and can never hold OWNER or ADMIN.

A second gap: the auto-moderator's platform-side timeout is **not** an in-game ban. A platform ban that a human issues cascades to the game (Q-MOD-3). Whether a short auto-timeout also affects the game is undecided (O-2); the safest default is that auto-delete and short timeouts do **not** cascade, and only a human ban does.

### 3.2 Action ladder `[DESIGN]`

The ladder is for chat text. It is separate from the conduct ladder (§6.8) so the two never double-punish; a flagged message may feed a conduct counter only for "repeated blocked-callsign attempts", which §6.8 already lists.

| Step | Action | Auto or human | Reversible by staff | Notes |
|---|---|---|---|---|
| 0 | **Reject for game only**: the message is not turned into a command, not rendered, not spoken, not logged beyond the hashed record (SEC-MOD-1, SEC-DATA-4). Chat on the platform is untouched. | Auto | Nothing to undo (message can be replayed from the 7-day envelope if staff allow) | The cheapest and safest step. No platform API call, no quota. |
| 1 | **Delete message** on the platform (Twitch delete, YouTube delete at 20 units) | Auto for high-confidence rules (denylist hit, known scam link pattern). Human for classifier-only or LLM-only flags. | Message cannot be restored on the platform; the audit row keeps a hashed record and the rule that fired | Delete only what we have a named rule for. |
| 2 | **Short timeout** (suggest minutes, not hours; PROPOSED, admin-tunable) | Auto only for repeated step-1 hits inside a window (PROPOSED), or for a raid burst | Staff can lift the timeout (Twitch unban endpoint, YouTube `liveChatBans.delete` at the reported 200 units) | On YouTube a timeout costs 200 units, so use sparingly. |
| 3 | **Long timeout or permanent platform ban** | **Human only** | Staff unban; cascades to the game per Q-MOD-3 | Bots may *propose*: they push a card to the staff queue. |
| 4 | **Game ban / XP penalty** | **Human only** (§6.8) | Appeal | Unchanged from the spec. |

Rules that apply to every auto-action `[DESIGN]`:
- **Reversible and logged.** Each action writes an audit row with: timestamp, platform, hashed `platform_user_id` or `commander_id`, the rule id that fired, the ladder step, the confidence source (rule, classifier, LLM-advice), and the acting service identity. Raw message text is not stored in the audit row; only a hash and the rule id (SEC-DATA-2, SEC-DATA-4).
- **Dry-run first.** Every new rule runs in "shadow mode" for a period: it records what it would have done without acting. Staff review the shadow log before enabling.
- **Rate cap on auto-actions.** A per-minute cap on bot-initiated actions per platform. On hitting it, the bot stops acting, raises an alert and recommends Shield Mode or the kill switch, instead of mass-punishing during a false-positive storm.
- **Kill switch overrides.** The kill switch (SEC-MOD-3) disables auto-actions as well as blanking text.
- **Skip trusted accounts.** Staff, the owner and (optionally) VIPs are exempt from auto-timeout; their messages can still be rejected-for-game.
- **No XP side effects.** Moderation outcomes never grant or remove XP (see section 4.4).

### 3.3 Detection layers: three options

**Option A: rule-based only (recommended for P2).** NFKC, confusable and leetspeak folding, denylist (word boundaries and substring rules, with a small "permitted terms" list to reduce the Scunthorpe problem), URL and invite-link rules, repeated-character and flood rules, and callsign rules. Deterministic, free, explainable, testable with fixed fixtures, and consistent with AGENTS.md rule 3's spirit (even though the gateway is not `sim-core`). Weakness: new slang, context, and languages we do not list.

Candidate building blocks (none verified beyond the excerpt):
- `obscenity` (npm, MIT per Yarn listing): transformer pipeline for leetspeak and confusables. Version 0.4.3 seen. `[3P]` [S29]. It is JavaScript; our gateway is Python (AGENTS.md §3), so it would be a reference design, not a dependency.
- A word list such as LDNOOBW: license not confirmed (`[UNVERIFIED]`); another package using it was seen [S29]. Our own list should be small, owner-curated and versioned; never copy a large list without checking its license (rule 8).

**Option B: add a classifier as a second signal.** A classifier produces a score for messages the rules did not decide. Candidates seen this session:

| Candidate | Type | License / terms | Cost | Notes | Tag |
|---|---|---|---|---|---|
| **Perspective API** (Jigsaw) | Hosted | n/a | Free while active | **Active until 2026-12-31; no migration help** (perspectiveapi.com: "we will not be offering direct migration support"). Do not adopt. | `[VERIFIED 2026-10-18]` [S30] (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-60) |
| **OpenAI moderation endpoint** (`omni-moderation-latest`) | Hosted | OpenAI API terms | "The moderation endpoint is free to use" (official guide) [CORRECTED 2026-10-18: the 250 requests per minute and 5,000 per day figures and the "paid from 7 August" claim appear nowhere on the official guide, so the earlier `[CONFLICT]` is dropped and the limits are `[UNVERIFIED]`; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-61] | Needs an OpenAI API account and key; it is a vendor dependency, so it goes behind `ModerationProvider` (ADR-0010). Check the current pricing page. | free: `[VERIFIED 2026-10-18]`; limits: `[UNVERIFIED]` [S31] |
| **Detoxify** (Unitary) | Local Python library | Apache-2.0 per PyPI classifier and a GitHub metadata mirror; one page says the README does not state a license, so check the LICENSE file [VERIFIED 2026-10-18: the repo LICENSE is the Apache License 2.0 text and the PyPI 0.5.4 classifier agrees; LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-62] | Free; needs CPU/RAM to run a transformer model | English-centric originals; a multilingual model covers EN, FR, ES, IT, PT, TR, RU. README warns that swearing is likely scored toxic regardless of intent and can bias against some groups. | `[3P]` [S32]; license `[VERIFIED 2026-10-18]` |
| **Llama Guard 4** (Meta) | Local LLM-based safety classifier | Llama 4 Community License (Hugging Face page "License: llama4" and the licence text); AUP applies; "Built with Llama" display duty; a separate licence is needed above 700 million monthly active users [CORRECTED 2026-10-18: was "per aggregators ... attribution reported"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-63] | Free weights; the model is large (a 12B size is listed), so GPU or paid inference | Heavy for a gaming PC that is also the broadcast host. | `[3P]` [S33]; license `[VERIFIED 2026-10-18]` |
| ShieldGemma (Google), Granite Guardian (IBM) | Local LLM-based | Not found this session | Not found | Named only as leads; no excerpt returned for them | `[UNVERIFIED]` |

No accuracy numbers are given because none were verified; none should be quoted in specs until measured on our own golden set (section 3.6).

Cost and fit `[DESIGN]`: a local model competes for the broadcast PC's CPU and GPU with OBS and the overlay (OPS-ADMIN topology). If used, run it on the Linux server (Q-ARCH-8), not on the broadcast host, behind the `ModerationProvider` port, with a timeout and a fail-open-to-rules behavior. A classifier score **never** triggers step 2 or higher by itself; it can only trigger step 0 (reject for game) or send a card to staff.

**Option C: optional LLM second opinion.** A cheap model scores only the messages the rules passed but flagged as "suspicious but undecided" (for example, a staff-defined sample, or messages containing a near-miss of a denylist term).
- **Advice-only.** AGENTS.md rule 5 and SEC-LLM-1/2/4: the output is parsed into a typed schema (`{category, severity, reason_code}`), range-checked, and treated as a suggestion that deterministic code can reject. It is never on the tick hot path (rule 5). Per SEC-LLM-1, only messages with an explicit LLM prefix reach an LLM; **moderation of arbitrary chat is therefore a new LLM use that needs a spec amendment** (O-3), because SEC-LLM-1 as written forbids sending ordinary chat to a model.
- **Prompt-injection safe.** The message is untrusted data inside a fixed template with no tools and no authority; SEC-LLM-4 says raw usernames and chat text must not appear in Threat Director or narration prompts, so the moderation prompt must be a separate, isolated prompt with its own budget.
- **Cost cap.** Counts toward the existing $20 per month AI cap (Q-AI-5) and the breaker (SEC-LLM-2), or gets its own sub-cap. At 100% the breaker cuts the call and the pipeline degrades to rules only.
- **Privacy.** Sending chat text to a third-party model discloses viewer text to that vendor; this must be listed in the privacy notice (NX-316) and the vendor's retention terms read first `[UNVERIFIED]`. A local model avoids this.
- **Recommendation:** defer Option C until Option A plus platform tools show a measurable gap in the shadow logs.

### 3.4 False positives, appeals and audit

- **Never silent.** A rejected command produces the existing batched digest line ("...not understood" style, FB-UX-5); a deleted platform message cannot notify the sender by the bot without spam, so a generic "messages containing certain terms are removed; see !rules" reminder in the periodic digest is enough.
- **Appeal path.** `#appeals` private channel or form (MARKETING §5.3, ADMIN-RBAC §6.8). Staff review the audit row (rule id, step), can lift a timeout, add a term to the permitted list, or mark the rule for revision. Appeals have no response-time promise (owner context).
- **Rule feedback loop.** Each upheld appeal creates a golden-set test (3.6) before the rule is changed.
- **Two-person rule** for turning on a new auto-timeout rule where more than one staff exist; solo-owner case follows RB-6/Q-RB-3 self-approval with a flag.
- **Audit.** Rows are append-only (ADMIN-RBAC §4.5, DM-3), visible to moderators and admins, exportable by admin/owner only.

### 3.5 Who gets alerted `[DESIGN]`

Fits the existing channels (OPS-ADMIN §2: ntfy push plus a private Discord channel, Q-OPS-4):
- **Info (no push):** each auto-action as a line in `#mod-log` (Discord, staff-only).
- **Review card:** step-3 proposals, classifier-only flags and appeals appear in the Command Center review queue and `#escalations`; staff handle them when they choose.
- **Page the owner (ntfy):** auto-action rate cap hit, a slur reaching the overlay or TTS (the SEC-MOD failure case), the kill switch used, a spike of held messages, or a classifier/LLM provider failing over to rules.
- Nothing pages a volunteer moderator. Alerts to mods are pull, not push, unless they opted into a slot (section 4).

### 3.6 Evaluation without storing abusive text in a public repo `[DESIGN]`

The repo is planned to be public, so verbatim slurs and harassment must not be committed (also relevant to the crisis plan, MARKETING §5.7, which adds incidents to a "moderation test corpus").

1. **Two corpora.** A *public* corpus of synthetic fixtures built from templates with placeholder tokens (for example `<SLUR_A>`, `<THREAT_B>`) plus *mutation operators* (leetspeak, homoglyph, zero-width insertion, spacing, case) so the tests prove the **folding** works without the repo containing real slurs. A *private* corpus of real examples stays outside the repo: an encrypted file (the project already plans `age` encryption for backups, Q-OPS-6) in the owner's private storage, mounted only on the owner's machine or the staging server.
2. **Placeholder expansion.** A local-only test hook expands placeholders from the private word file when it is present; CI without the file runs the synthetic subset and marks the private tests as skipped (visibly, not silently passing).
3. **Hash-only denylist entries in the public repo (optional).** Store keyed hashes of normalized denylist terms plus a category; matching hashes the normalized token. This hides the list from casual reading but is **not secret** against a dictionary attack; the list is a defence in depth, not a confidentiality control. Decide with the owner whether the denylist itself is public.
4. **Metrics.** Per category: precision and recall measured on the golden set, a false-positive count on a corpus of *benign* gaming text (callsigns, command syntax, chat about the game, other languages), and a latency budget. Report counts, not percentages from other people's studies.
5. **Shadow-mode measurement.** In production alpha, run the candidate rules in shadow mode and have staff label a sample of hits as correct or wrong (labels only, no raw text kept beyond the review window).
6. **Regression rule.** Every appeal upheld and every incident adds a test (synthetic form) before the rule changes.

---

## 4. Moderator program design (no obligations)

Owner context: trusted volunteers from the previous channel, possibly paid later; real life comes first; **no response-time expectations**; mods may volunteer for or be assigned chat-watch slots; mods are also allowed to play.

### 4.1 Slots and scheduling

| Mode | How it works | Tools |
|---|---|---|
| **Volunteer slots** | A mod signs up for a time window they choose. No minimum. Signing up creates a soft promise ("I will look when I can") and is cancellable without explanation. | Discord sign-up thread or Discord scheduled event; a shared calendar `[UNVERIFIED]` which calendar tool |
| **Assigned slots** | The owner or an admin proposes a slot; the mod accepts, swaps or declines. Only offered to mods who said yes to assigned slots. | Same; accept/decline reaction |
| **Coverage display** | The Command Center home shows "slots covered this week" for staff only (no names on the public stream, to avoid exposing or pressuring individuals). The public overlay shows nothing about mod coverage. | Command Center page fed by the sign-ups (a scheduled-events table, ADMIN-RBAC `campaign.schedule` is Owner/Admin so scheduling slots would need a separate permission or be managed in Discord) |

Slots are **informational**, not an SLA. When a slot is empty, nothing breaks: platform tools, the bot (section 3) and the auto-pause/kill-switch cover the gap.

### 4.2 Roles and ADMIN-RBAC mapping

| Program role | ADMIN-RBAC role | Powers (existing matrix) |
|---|---|---|
| Trial moderator | `MODERATOR` with a `CAMPAIGN` or `PLATFORM` scope and `expires_at` (§4.4) | Same permissions, narrower scope; MARKETING §5.1 lists "Trial Moderator" but the mapping is "not defined" there |
| Moderator | `MODERATOR` | `mod.kill_switch`, `mod.ban/unban`, `mod.purge_units`, `mod.callsign_review`, `mod.clip_review`, `users.view`, `users.link_audit`, pause with a required note, `ops.alerts_ack`, own audit rows |
| Chat-only mod | Platform moderator role on Twitch/YouTube/Discord only; **no** Command Center login | For volunteers who only want to help in chat |
| Admin | `ADMIN` | As in the matrix |

Staff sign in through Discord OAuth with a verified link (RB-5, Q-ARCH-12); passkeys are required for admins, not moderators. Mods never get `users.view_pii`, rules or content edit rights (§4.3). Every grant is scoped and can expire (§4.4). A mod who stops volunteering simply loses the role; no process beyond revocation.

### 4.3 Onboarding guide outline

1. Welcome and what the role is not (no obligations, no response times, no payment unless agreed in writing later).
2. The Quorum and the Static in two paragraphs; the community guidelines outline (MARKETING §5.2); `!rules`.
3. Tools: platform mod tools, Discord, the Command Center (kill switch first), where the audit log is.
4. The ladder: reject, delete, timeout (mod may do), ban (mod may do with a reason; permanent platform bans and game bans are logged and reversible).
5. Do-not rules: never argue in public, never screenshot Operators' personal data, never share raw platform ids (SEC-DATA-2), never use mod powers on friends or enemies in the game.
6. Conflict-of-interest rules (4.4), logging, appeals.
7. Safety and wellbeing (4.5): how to step away, how to report abuse aimed at you, how to get help.
8. Emergency: kill switch, pause with a note, who the owner is, and the explicit statement that nobody is on call.
9. Privacy and confidentiality: what staff may see, retention (SEC-DATA-4), the `!forget` flow.
10. Sign-off: a short acknowledgement of the code of conduct, kept as an access record.

### 4.4 Conduct rules for mods who also play

Because mods are allowed to play, the risk is moderation power converting to in-game advantage or to unfair treatment. Proposed rules `[DESIGN]`, to be agreed with the owner:
- **Recusal.** A mod does not take a moderation action (ban, timeout, purge, callsign decision, conduct review, appeal) on their own account or unit, on an Operator they are in a declared dispute with, or on someone they know personally. They flag it to another staff member.
- **No in-game moderation of the match they are playing.** While their unit is deployed, a mod does not run `mod.purge_units` or `mod.callsign_review` on units adjacent to or in contention with theirs; they ask another staff member or wait.
- **Logged and visible.** All mod actions are `STAFF_*` commands with `issuer {staff_id}` (RB-4) and audit rows (RB-3); a mod can see their own actions (`audit.view` own). An admin can see mod actions against units of other staff.
- **No XP advantage.** Mod permissions never touch the XP ledger. `users.xp_adjust` is Owner/Admin only with a two-person eligible flag; a mod account is never granted it. Mod actions never grant merit or conduct credit. Self-play on a staff account is subject to the same conduct ladder as any Operator.
- **Separate identity when acting.** Staff actions come from the staff identity in the Command Center, not from chat commands from their play account, so the audit trail separates "playing" from "moderating".
- **Pause.** A mod may pause (with a required note, Q-RB-1) but is advised not to pause for reasons that benefit their own unit; every pause already alerts the owner.
- **Disclosure.** Mod status is visible to other staff; whether it is shown to players is an owner decision (O-6).

### 4.5 Burnout and safety

- No overnight duty is expected. The kill switch (RB-8) and the offline auto-pause (OA-5) are the emergency cover, not people.
- Slots cap at what the mod chooses; suggest a maximum continuous watch length and a rest rule in the guide (a suggestion, no number invented).
- Exposure to abusive text is a real risk: the auto-moderator (section 3) should hide or blur the worst category in staff queues by default (show a category label and a "reveal" click), so mods review less verbatim abuse. This is a design feature, not a sourced claim.
- A named owner contact for harassment aimed at a mod; ability to leave without explanation.
- Mods are anonymous to the public by default (display only role badges on the platforms themselves).

### 4.6 If mods are ever paid: issues to raise with an accountant or attorney (not advice)

Everything in this list is **jurisdiction-dependent** and should be reviewed by a qualified professional in the owner's jurisdiction and, where relevant, the mod's. None of it is a conclusion.
- **Classification:** whether paid mods are employees, independent contractors or volunteers with a stipend; how local tests treat control, schedule, tools and economic dependence. Assigned slots and required hours point toward more control, which is a reason to keep slots optional if volunteering is intended.
- **Wage and hour rules** if classified as employees (minimum wage, hours, record keeping) and any rules for unpaid volunteers at a for-profit business.
- **Tax:** reporting thresholds and forms for payments, withholding, VAT or sales-tax questions, and cross-border payers or payees (mods in other countries).
- **Payment channel and records:** how to pay (and the platform's own payment tools), invoices, and records retention.
- **Platform rules:** whether Twitch, YouTube or Discord terms or policies say anything about paying moderators or about moderators' access to channel tools. Nothing authoritative was found this session (the only search results were low-quality content-farm pages that said pay comes from the streamer, not the platform `[3P]`), so this is **[UNVERIFIED]** and must be read in the platforms' terms.
- **Liability, insurance and confidentiality:** a written agreement covering conduct, data handling, IP of anything the mod creates, and what happens on termination.
- **Data protection:** staff see personal data; a data-processing arrangement or confidentiality undertaking may be needed.
- **Gifts, tips and in-kind rewards** (roles, cosmetics, shout-outs) and whether they are treated as compensation.
- **Age:** whether any mod is a minor, which affects both employment and platform terms.

---

## 5. Privacy-preserving analytics

### 5.1 Ranking for this project

| Rank | Option | Why |
|---|---|---|
| 1 | (a) First-party game-event analytics | Already decided (Q-DM-3); answers the product questions; no new data collected beyond the game ledger |
| 2 | (b) UTM-tagged links in our own posts | Zero tracking by us; the destination sees the tag only if it has a measurement tool |
| 3 | (c) Platform-native dashboards, read by a human | Free, no code, not imported (Q-DM-3) |
| 4 | (e) Self-reported "how did you find us?" | Voluntary and transparent |
| 5 | (d) Cookieless web statistics for the public site | Useful but potentially conflicts with Q-DM-3 wording (see 5.3); do last |
| n/a | (f) DNT/GPC handling | Applies if any script-based tool exists |

### 5.2 (a) First-party game-event analytics

**Questions it can answer** from sim and gateway events keyed by `commander_id`:

| Question | Event inputs | Aggregate output |
|---|---|---|
| D1 and D7 retention by cohort (first-seen day or week) | first command date, later command dates | Share of cohort active on day 1 and day 7; the cohort key is first-seen date |
| Session length and sessions per Operator | consecutive command timestamps with an idle-gap rule (reuse the idle-handoff concept, CG-6, but define a separate analytics gap) | Distribution (median, percentiles), not per person |
| Funnel: join, first command, second command, first mission | `!join`, accepted commands, mission completion | Step conversion and drop-off |
| Rank progression | XP ledger entries (DATA-MODEL §4, append-only) | Time and missions to each rank |
| Peak concurrent and concurrency over time | gateway + sim connected units | Time series |
| Per-command usage | accepted and rejected commands by class | Counts by command and by rejection reason (already a metric in OPS-ADMIN §2) |
| Churn after loss events | last-seen after a unit loss versus baseline | Return rate after a loss event vs. after a non-loss session |
| Raid effects | raid-origin flag, new commanders in a window, their retention | Raid-cohort retention vs. normal cohort |
| Moderation effects | counts of rejects/deletes/timeouts per week | Operational dashboard for staff |

**Safeguards** `[DESIGN]`, PROPOSED values tunable:
- **Aggregate-only dashboards.** No screen shows a per-person timeline outside the staff console (`users.view`), and dashboards for the owner and public display only aggregates.
- **Minimum cohort size (k-anonymity style threshold).** Cells with fewer than k Operators are suppressed or merged (PROPOSED k = 10; the value is a policy choice, not a sourced standard).
- **Retention limits.** Raw envelopes 7 days and command log campaign + 30 days (SEC-DATA-4); aggregates indefinitely (Q-LEGAL-3). D7 retention needs per-Operator first-seen and last-seen dates, which already live in `platform_identities.first_seen/last_seen` (IDENTITY §1). **Question O-8:** may the analytics job compute from those columns and from the ledger, and then keep only aggregates, rather than retain a per-Operator daily activity table?
- **No profiling beyond the game ledger.** Analytics reads only what the game already stores; it adds no device ids, IP addresses, browser data or cross-site ids. Raw platform ids stay behind `users.view_pii` (RB-12).
- **Keyed hashing.** Where an analytics export is needed outside the database, replace `commander_id` with a salted/keyed hash; rotate the key on a schedule so exports cannot be joined across periods. Note that pseudonymous ids can still count as personal data under some laws (jurisdiction-dependent, flag for NX-316).
- **Opt-out through `!forget`.** `!forget` already deletes the profile and replaces the callsign with a tombstone (IDENTITY §5), and aggregates computed earlier stay. Consider whether a lighter "exclude me from analytics" flag (without deleting the account) is wanted (O-9).
- **No analytics on children's data** beyond what the platforms already provide: no age is collected by us.

### 5.3 (d) Cookieless statistics for the public site, and the Q-DM-3 conflict

Q-DM-3 (decided 2026-10-18): "No third-party trackers, cookies or analytics scripts on overlay or site." A *self-hosted, cookieless* script is not third-party and sets no cookies, but it is still an "analytics script" under that wording. Two readings:
- **Strict:** no analytics script of any kind on the site. Then only server-log analysis (no script) and first-party game events remain.
- **Relaxed (needs an explicit owner decision, O-4):** allow one self-hosted, cookieless, script-based tool, disclosed in the privacy notice.

The site is currently planned as a static site on a free static host fed by one-way exports (OPS-ADMIN OA-11), so **server logs may not be ours to read** (host log availability `[UNVERIFIED]`).

| Tool | License | Data collected (per sources) | Cookies / consent | Hosting and cost | Tag |
|---|---|---|---|---|---|
| **GoAccess** (log analyzer) | MIT (upstream COPYING and goaccess.io) [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-70] | Reads web-server logs (Apache, Nginx, S3, CloudFront); no script, no browser beacon | No client-side tracking, so no cookies set by the tool; the logs themselves hold IP addresses (retention policy needed) | Self-run terminal or HTML report; needs access to server logs | `[3P]` [S34]; license `[VERIFIED 2026-10-18]` |
| **GoatCounter** | modified EUPL 1.2 (the "Compatible Licenses" appendix removes some licenses) [CORRECTED 2026-10-18: was "EUPL (version [UNVERIFIED])"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-71] | Page views; counts unique visits using a non-identifiable hash, no cookies, no unique identifiers per its README | README says no GDPR consent notice needed (a legal conclusion we should not rely on); hosted version: the terms say it is "offered for free for reasonable public usage. Running your personal website or small-to-medium business on it is fine" [CORRECTED 2026-10-18: neither the "non-commercial" nor the "personal projects" wording appears; was `[CONFLICT]`; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-72] | Self-host (Go binary, runs with a small footprint `[UNVERIFIED]`) or hosted | `[3P]` / README excerpt [S35] |
| **Umami** | MIT [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-73] | Page views and events; script sets no cookies and stores no personal identifiers per sources | "Generally no banner needed" is a third-party claim | Self-host (Node.js + a database) free; Cloud: Hobby $0/month with up to 100K events per month, Pro $20/month with 1 million events included; no $9 tier on umami.is/pricing [CORRECTED 2026-10-18: was "Cloud pricing sources conflict (free Hobby tier with 10K events vs. $9 for 100K)"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-74] | `[3P]` [S36]; license and pricing `[VERIFIED 2026-10-18]` |
| **Plausible** | Community Edition AGPL (README: "AGPLv3 or any later version"; the JS tracker is MIT) [VERIFIED 2026-10-18, LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-75] | Cookie-free page-view statistics | Docs describe CE as cookie-free; AGPL obligations apply to modified network services | Self-host is "your job" (install, upgrade, backup); CE is released about twice a year; Cloud trial 30 days, Cloud tiers $9, $14 and $19 per month with a 30-day free trial and no free-forever plan `[VERIFIED 2026-10-18]` (LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-75) | `[EXCERPT-OFFICIAL]` for CE description, `[3P]` prices [S37] |
| **Matomo** (self-hosted, cookies off) | GPL v3 or later (README: "released under the GPL v3 (or later) license") [CORRECTED 2026-10-18: was "GPL (not confirmed) [UNVERIFIED]"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-76] | Full analytics suite; privacy features include disabling fingerprinting, user profiles and session recording, truncating IP octets | Matomo says a correctly configured install may meet the French CNIL exemption criteria; the exemption is limited to performance and content measurement and does not apply in some stricter ePrivacy jurisdictions; the CNIL page (sheet n°16) describes an opt-out regime for strictly configured audience measurement and does not mention a retired exempt-tool list [CORRECTED 2026-10-18: was "the CNIL list of exempt tools was reportedly retired on 2026-01-01, so vendors self-assess"; see LICENSE-AND-MUSIC-VERIFICATION-2026-10-18 V-77] | Heavier install (PHP + MySQL/MariaDB) | `[EXCERPT-OFFICIAL]` for Matomo's claim, `[3P]` for scope [S38] |
| **Cloudflare Web Analytics** | Hosted, proprietary | Page views and Core Web Vitals via a beacon; Cloudflare says no cookies, no localStorage, no fingerprinting; a visit is a page view with an external referrer. A 2020 review found a unique cookie at launch and unclear IP logging; Cloudflare later announced stopping the cookie in 2021 | **Third party** (Cloudflare processes visitor requests), which conflicts with the Q-DM-3 "third-party" wording regardless of cookies | Free per excerpts; needs the site to be proxied or the beacon added | `[EXCERPT-OFFICIAL]` / `[3P]` [S39] |

Cookie and consent implications (**jurisdiction dependent; flag for the NX-316 legal pages**): whether a cookieless analytics script needs consent depends on the law of the visitor's location (ePrivacy rules on accessing terminal equipment, local regulator guidance, the GDPR) and on the tool's configuration. Search excerpts show vendors claiming no banner is needed, and a regulator-linked exemption in France with limits; none of this was verified from a regulator source. Do not rely on vendor claims; get the legal pages reviewed.

**Default recommendation `[DESIGN]`:** start with **no site analytics script**. Use (a) the game ledger, (b) UTM links and (c) platform dashboards. Add GoAccess over host logs if the host exposes logs. If the owner later wants page-view counts, choose a self-hosted cookieless tool; GoatCounter or Umami are the lightest options reported, Plausible CE and Matomo are heavier. That choice needs the Q-DM-3 amendment (O-4) and a disclosure update.

### 5.4 (b) UTM-tagged links

Add `utm_source`, `utm_medium` and `utm_campaign` query parameters to links we publish in video descriptions, posts, Discord announcements and the stream panel. We do not run a tracker; the parameters are only visible to whatever measures the destination. On a static site with no analytics script nothing reads them, so UTM is only useful together with server logs (GoAccess) or a later opted-in tool. UTM parameters should be stripped before the page is stored or shared onward, and the privacy notice should mention them. UTM is a convention, not a specification, and its handling in particular tools was not verified `[UNVERIFIED]`.

### 5.5 (c) Platform-native dashboards

Twitch, YouTube, TikTok and Instagram provide their own analytics to the channel owner. Per Q-DM-3 these are used for viewer counts and **not imported** into our systems. Read them by hand; record headline numbers in the devlog if desired. What each exposes by API is in SOCIAL-CHANNEL-AUTOMATION-RESEARCH §2 (not repeated). Using the platform's analytics does not need our privacy notice to change, but we should say we do so.

### 5.6 (e) "How did you find us?"

An optional, skippable question, asked once, in a place where Operators already interact: the Discord onboarding (Community Onboarding questions `[3P]` mentioned in MARKETING §5.1) or a one-time `!` prompt after the first mission. Answers are multiple-choice (platform, friend, raid, search, other) stored as an aggregate counter keyed by cohort, with free text disallowed (it would become untrusted chat input, rule 4). It is voluntary, discloses its purpose, and respects `!forget` (the answer is aggregated; no per-person copy beyond the optional commander field if the owner wants cohort cuts, O-9).

### 5.7 (f) Do Not Track and Global Privacy Control

- **Global Privacy Control (GPC):** a header `Sec-GPC: 1` and a JavaScript property `navigator.globalPrivacyControl`. Servers should ignore the header unless the value is exactly `1`. The W3C spec is a Working Draft (2024) and MDN marks the property as experimental. The explainer ties it to opt-out choices such as under the CCPA. Whether it is legally binding is jurisdiction dependent; a 3P source says California treats it as an opt-out, which is unverified here. `[EXCERPT-OFFICIAL]` for mechanics [S40], `[3P]` for legal effect [S41].
- **Do Not Track (DNT):** no excerpt this session covered its current status; treat as `[UNVERIFIED]` and do not build on it.
- **Policy `[DESIGN]`:** if any analytics script exists on the site, it should not load when GPC is signalled (`Sec-GPC: 1` on the document request, or `navigator.globalPrivacyControl === true`), and the privacy notice should say so. With no script, GPC has nothing to suppress, and the notice can state that we do not use tracking scripts. The overlay (in OBS) and the in-game ledger are not browser-tracking surfaces and are covered by `!forget` and the notice.

### 5.8 What to disclose in the privacy notice (NX-316 input, `[DESIGN]`; not legal advice)

1. What we collect from game events (commander id, platform id, first-seen/last-seen, commands, ledger entries) and why (play, balance, retention analysis), with the retention periods from SEC-DATA-4.
2. That analytics are first-party only, aggregate-reported, with a minimum group size, and that no third-party trackers or cookies are used on the overlay or site (Q-DM-3 wording, as amended if O-4 changes it).
3. Whether the site uses any analytics script and, if so, which, self-hosted, what it records, that it sets no cookies, and how to opt out (GPC).
4. That platform dashboards are read by the owner but not imported.
5. Moderation: that chat text is checked by automated filters; what is kept (hashes, rule ids, no raw text beyond the retention window); whether any text goes to a third-party model and which; that bans on a platform carry over to the game; how to appeal.
6. Staff access: who sees what (RB-12), that staff actions are logged.
7. The `!forget` flow, its 30-day limit, what aggregates remain after deletion, and how to contact us.
8. UTM tags in our links and the optional "how did you find us" question.
9. Legal bases, controller identity and international transfers: **jurisdiction dependent, for the attorney** (`[UNVERIFIED]`).

---

## 6. Recommendations, phasing, proposed tracker items, questions

### 6.1 Recommendations

1. Enable every free platform tool before writing code (Twitch AutoMod, blocked and permitted terms, Shield Mode, suspicious-user monitoring; YouTube blocked words, hold-for-review; Discord AutoMod). Document the settings in a runbook (OPS-ADMIN §4 "moderation incident").
2. Build the Nexus moderator as a **rules-only** engine first, reusing SEC-GW-1 normalization and the SEC-MOD-1 denylist; add a `ModerationProvider` implementation for chat text and a platform-action capability on the adapters (ADR-0010 N-3).
3. Cap auto-actions at **reject-for-game, delete, short timeout**; keep long timeouts, permanent bans and game bans human-only.
4. Do not adopt Perspective API. Evaluate a local classifier (Detoxify or similar) only after shadow logs show a gap, and an LLM second opinion last.
5. Keep analytics first-party and aggregate-only; no site analytics script until the owner resolves the Q-DM-3 wording.
6. Run the moderator program as opt-in with no response times; give staff a coverage display; use kill switch and auto-pause as cover.
7. Before any pay arrangement, consult an accountant or attorney (list in 4.6).

### 6.2 Phased rollout (against AGENTS.md launch order: P2 Twitch alpha, P3 YouTube beta and linking, P4 later seasons)

| Phase | Moderation | Analytics | Moderator program |
|---|---|---|---|
| **P2 (alpha, Twitch)** | Platform tools configured; rules-only moderator in **shadow mode** then enabled for reject-for-game and delete; EventSub moderation events feed ban sync (already planned); audit log and `#mod-log` | Event schema and a small set of aggregate queries (funnel, D1/D7, per-command usage) for the owner; k-threshold; no site script | Small trusted team; volunteer slots in Discord; onboarding doc; recusal rules |
| **P3 (beta, YouTube, linking)** | YouTube adapter: delete via API, rely on YouTube's blocked words and hold-for-review; quota dashboard counts moderation units; short timeouts only after a quota check; staff review queue in the Command Center | Cross-platform cohorts after identity linking (IDENTITY §4) with care for merges; retention dashboards; "how did you find us" question | Assigned-slot option; coverage display; Discord OAuth staff login (Q-ARCH-12); appeals flow |
| **P4 (later)** | Optional local classifier as second signal; optional LLM advice if the spec is amended; periodic rule review; transparency note | Optional self-hosted cookieless site tool if O-4 is approved; GPC handling; privacy notice final copy (NX-316) | Review of workload and burnout; paid-mod decision only after professional advice |

### 6.3 Proposed tracker items (do NOT edit TRACKER; IDs to be assigned by the coordinating session)

| Proposed item | Size | Depends on |
|---|---|---|
| Runbook: configure platform-native moderation (Twitch, YouTube, Discord) and a "moderation incident" playbook | S | none |
| Spec: chat auto-moderator (`ModerationProvider` for chat, action ladder, audit row, shadow mode, rate cap, kill-switch link) | M | owner answers O-1…O-3; CHAT-GATEWAY, ADMIN-RBAC |
| ADMIN-RBAC addition: service permission(s) for bot-initiated platform actions, and conduct-vs-chat boundary note | S | the spec above |
| Contract and port: platform moderation actions (`delete_message`, `timeout`, `ban`) with `Capabilities.supports_moderation_actions`, conformance tests | M | spec above; ADR-0010 |
| Twitch moderation adapter: scopes, Helix calls, EventSub moderation events, rate limits | M | port above; NX-190 range |
| YouTube moderation adapter: delete/ban calls, quota accounting | M | YouTube adapter; quota dashboard |
| Moderation rule engine: denylist + folding for chat, permitted terms, URL rules, flood rules | M | SEC-MOD-1 implementation |
| Golden-set tooling: synthetic fixtures, mutation operators, private corpus loader, CI skip reporting | M | rule engine |
| Staff review queue and `#mod-log` / ntfy alert wiring | M | Command Center minimal console (NX-253) |
| Local classifier evaluation (Detoxify or similar), comparison on the golden set | M | golden set |
| LLM second-opinion spike + SEC-LLM-1 amendment | M | owner approval; AI budget |
| Analytics event schema and aggregate queries (retention, funnel, rank, raid, churn) with k threshold | M | DATA-MODEL; NX-036 |
| Analytics privacy review (hashing, retention, opt-out flag) | S | the item above |
| Q-DM-3 amendment decision and site-stat tool selection spike | S | owner O-4 |
| Moderator handbook, slots process, recusal rules | S | owner decisions O-5…O-7 |
| Privacy-notice inputs for NX-316 (moderation + analytics sections) | S | NX-316 |
| Paid-moderator legal questions checklist for accountant/attorney | S | owner decision to explore pay |

### 6.4 Open questions for the owner

- **O-1.** Should bot-initiated platform delete/timeout be a new RBAC permission for a service role, or outside the matrix (platform-moderator actions only)? (`SVC_PLATFORM_BOT` is "relay only" today.)
- **O-2.** Do auto-delete and short auto-timeouts cascade to the game? Recommendation: no; only human bans cascade (Q-MOD-3).
- **O-3.** May ordinary chat text ever be sent to an LLM for moderation? SEC-LLM-1 currently restricts LLMs to `!order`-prefixed messages. If yes, which provider, and under which cost cap and privacy disclosure?
- **O-4.** Amend Q-DM-3 to allow one self-hosted cookieless site script, or keep "no analytics scripts" strictly?
- **O-5.** Are chat-only mods (no Command Center login) in scope, and may they be unknown staff in the audit log?
- **O-6.** Is mod status public, or staff-only?
- **O-7.** Appeals: who reviews, and do you want a public "no promised response time" statement?
- **O-8.** May the analytics job read `first_seen/last_seen` and the ledger, then keep only aggregates, rather than keep a per-Operator daily activity table?
- **O-9.** Do you want a separate "exclude me from analytics" flag besides `!forget`, and may the "how did you find us" answer be stored per commander or only in aggregate?
- **O-10.** Which minimum cohort size k and which retention windows for analytics exports (PROPOSED k = 10)?
- **O-11.** Is the denylist public (hash-only or full), or private?
- **O-12.** Should we recommend or require a hosted bot (Fossabot, Nightbot, etc.) at all during alpha, or rely on native tools plus the Nexus moderator?

---

## 7. Sources, access log and unreachable pages

**Read date for all sources: 2026-10-18.** Method: `WebSearch` result excerpts only.

### 7.1 Access log (what was and was not reachable)

| Attempt | Result |
|---|---|
| `WebFetch https://dev.twitch.tv/docs/api/reference/` | `getaddrinfo ENOTFOUND dev.twitch.tv` |
| `WebFetch https://developers.google.com/youtube/v3/determine_quota_cost` | `getaddrinfo ENOTFOUND developers.google.com` |
| `WebFetch https://plausible.io/data-policy` | `getaddrinfo ENOTFOUND plausible.io` |
| `curl` via the agent proxy to `https://dev.twitch.tv/docs/api/reference/`, `https://developers.google.com/youtube/v3/determine_quota_cost`, `https://plausible.io/data-policy`, `https://support.discord.com` | No HTTP status returned (curl `%{http_code}` printed `000`) for all four |
| Other hosts (Nightbot, Moobot, Fossabot, StreamElements, Streamlabs, Umami, GoatCounter, GoAccess, Matomo, Cloudflare, CNIL, W3C, MDN, OpenAI, Meta, Hugging Face, GitHub) | Not fetched directly; only seen as search excerpts |

**Not found even as excerpts (all `[UNVERIFIED]`):** Twitch's current help article on AutoMod levels and Shield Mode; the Helix endpoint pages for held messages, Check AutoMod Status and Warn Chat User scope; Twitch ban-endpoint rate limit values; Twitch app-review requirements for moderator scopes; YouTube live-chat quota table (seen only as partly garbled excerpts); YouTube moderator roles via API; Discord AutoMod limits from the official article beyond the quoted fragments; any pricing page of Nightbot, Moobot, StreamElements; any official API documentation for those bots; ShieldGemma and Granite Guardian licenses; LDNOOBW license; Matomo license; GoatCounter hosted terms; Do Not Track status; any platform rule on paid moderators; any regulator page (CNIL, EDPB, ICO) read directly; a legal test for volunteer/contractor/employee classification.

### 7.2 Sources

Official or vendor pages (seen only as excerpts):
- S2 https://blog.twitch.tv/en/2017/05/18/automod-2-0-personalization-update-445c148098f8
- S5 https://dev.twitch.tv/docs/authentication/scopes/ ; https://dev.twitch.tv/docs/api/moderation
- S7 https://discuss.dev.twitch.com/t/chat-warnings-are-now-available-via-the-api-and-eventsub-in-an-open-beta/59511
- S9 https://dev.twitch.tv/docs/api/moderation (Update AutoMod Settings)
- S10 https://discuss.dev.twitch.com/t/new-shield-mode-endpoints-and-eventsub-subscription-type-are-now-in-open-beta/42172
- S11 https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/ ; https://dev.twitch.tv/docs/PubSub
- S12 https://discuss.dev.twitch.tv/t/api-to-get-unban-requests-results/31899 ; https://twurple.js.org/reference/eventsub-base/classes/EventSubChannelUnbanRequestResolveEvent.html
- S14 https://support.google.com/youtube/answer/9483359 ; https://support.google.com/youtube/answer/111870 ; https://support.google.com/youtube/answer/16622701
- S15 https://developers.google.com/youtube/v3/live/docs/liveChatBans
- S16 https://developers.google.com/youtube/v3/live/docs/liveChatMessages/delete
- S17 https://developers.google.com/youtube/v3/getting-started
- S18 https://developers.google.com/youtube/v3/determine_quota_cost ; https://developers.google.com/youtube/data/determine_quota_cost
- S19 https://developers.google.com/youtube/data/live/reference/rest ; https://github.com/Milzstream/OBS-Multi-Chat/issues/6 (disputed 50-unit claim)
- S20 https://support.discord.com/hc/articles/4421269296535 ; https://discord.com/blog/automod-launch-automatic-community-moderation
- S21 https://docs.discord.com/developers/resources/auto-moderation
- S24 https://moo.bot/docs/twitch-chat-auto-mod-bot-message-filters
- S25 https://fossabot.com/
- S26 https://docs.streamelements.com/chatbot/filters ; https://support.streamelements.com/hc/en-us/articles/18750955133458-Chatbot-Spam-Filters
- S27 https://streamlabs.com/cloudbot ; https://streamlabs.com/chatbot
- S30 https://perspectiveapi.com/
- S31 https://developers.openai.com/api/docs/models/omni-moderation-latest
- S38 https://matomo.org/faq/how-do-i-configure-matomo-without-tracking-consent-for-french-visitors-cnil-exemption/ ; https://matomo.org/wp-content/uploads/2026/04/Configure-Matomo-Analytics-for-CNIL-exemption-User-Guide.pdf
- S39 https://blog.cloudflare.com/free-privacy-first-analytics-for-a-better-web/
- S40 https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Sec-GPC ; https://developer.mozilla.org/en-US/docs/Web/API/Navigator/globalPrivacyControl ; https://www.w3.org/TR/2024/WD-gpc-20241203/ ; https://w3c.github.io/gpc/explainer.html
- S37 https://plausible.io/docs/self-hosting
- S23 https://nightbot.tv

Third-party sources (`[3P]`):
- S1 https://blog.brandbastion.com/how-to-set-up-twitch-moderation-and-keep-chat-safe
- S3 https://esports.gg/news/streamers/twitch-shield-mode-mod-update-ban/ ; https://onmsft.com/?p=289389
- S4 https://www.mcvuk.com/business-news/twitch-launches-suspicious-user-detection-to-combat-harassment-in-chat/ ; https://techxplore.com/news/2021-12-twitch-tool-evaders.amp
- S6 https://www.rapidevelopers.com/md/api-automations/how-to-automate-twitch-chat-moderation-using-the-api
- S8 https://twurple.js.org/reference/eventsub-base/classes/EventSubAutoModMessageHoldV2Event.html ; https://twitchio.dev/en/latest/references/eventsub/eventsub_models.html
- S13 https://discuss.dev.twitch.tv/t/error-429-limitation-helix-api/25216
- S22 https://blog.communityone.io/discord-automod-guide-regex-banned-words/ ; https://tessl.io/registry/tessl/pypi-disnake/files/docs/automod.md
- S28 https://serycodes.carrd.co/ ; https://scrapbox.io/twitch/How_to_use_Sery_Bot
- S29 https://classic.yarnpkg.com/en/package/obscenity ; https://deepwiki.com/jo3-l/obscenity
- S32 https://simple-repository.app.cern.ch/project/detoxify ; https://www.sourcepulse.org/projects/1855720
- S33 https://www.llmreference.com/compare/llama-4-maverick-17b-instruct/llama-guard-4-12b ; https://canirun.ai/license/llama-4-community/
- S34 https://www.ionos.com/digitalguide/server/tools/log-file-analysis-with-open-source-tool-goaccess/ ; https://archlinux.org/packages/extra/x86_64/goaccess
- S35 https://lwn.net/Articles/822568 ; https://pkg.go.dev/zgo.at/goatcounter@v1.4.2
- S36 https://privacytools.io/app/umami ; https://toolradar.com/tools/umami
- S41 https://http.dev/sec-gpc
- Paid-moderator search results (low quality, no authority): content-farm pages; not cited as evidence.

Repo documents used: AGENTS.md, docs/specs/ADMIN-RBAC.md (§4, §6.8), CHAT-GATEWAY.md, IDENTITY.md, OPS-ADMIN.md, docs/security/THREAT-MODEL.md (SEC-GW, SEC-MOD, SEC-LLM, SEC-DATA), docs/planning/OPEN-QUESTIONS.md (Q-MOD-1…6, Q-DM-3), docs/architecture/adr/0010-platform-and-provider-neutrality.md, docs/review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md, docs/review/MARKETING-AND-PRODUCTION-RESEARCH.md.
