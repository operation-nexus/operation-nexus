# Social Channel Automation Research (Twitch, YouTube, TikTok, Instagram)

> Verification status (2026-10-18): corrected against primary sources in [PLATFORM-POLICY-VERIFICATION-2026-10-18](PLATFORM-POLICY-VERIFICATION-2026-10-18.md). Inline [CORRECTED 2026-10-18] notes mark changed claims; [VERIFIED 2026-10-18] marks confirmed ones.

Date: 2026-10-18 · Status: research, not a spec · Owner request: set up the four channels, automate as much as is allowed, and add a monitoring bot with a review/clear queue. Related: Q-MKT-1…4, Q-AI-6, Q-LEGAL-6/7/8, Q-ARCH-7, Q-ARCH-10, Q-OPS-4, [MARKETING](../planning/MARKETING.md), [PLATFORM-REALITY-CHECK](PLATFORM-REALITY-CHECK.md), [SUPPORT-AND-SCRAPING-RESEARCH](SUPPORT-AND-SCRAPING-RESEARCH.md), [CLIPS-REPLAY](../specs/CLIPS-REPLAY.md), [OPS-ADMIN](../specs/OPS-ADMIN.md), [CHAT-GATEWAY](../specs/CHAT-GATEWAY.md).

## 0. How to read this document (evidence quality)

**Nothing in this document was read directly from a primary page.** On 2026-10-18 every direct fetch of an official host failed (see section 7: DNS failure from the fetch tool, and HTTP 403 from the egress proxy via curl). All facts below come from **web-search result excerpts** (summaries of search hits, some of which quote official pages). That is weaker than reading the page. So:

| Tag | Meaning |
|---|---|
| `[EXCERPT-OFFICIAL]` | The search excerpt reported text from an official platform page (URL in section 7). Still re-read the live page before building on it. |
| `[3P]` | Reported only by a third-party blog, vendor, news site or review site. Treat as a lead. |
| `[CONFLICT]` | Sources disagree. Check the live page or your own account's console. |
| `[UNVERIFIED]` | Not found in any source this session. Do not rely on it. |

Per AGENTS.md rule 0: numbers (quotas, thresholds, prices) here are the best reported values on 2026-10-18, not facts. Nothing below is a spec; promoting any of it needs a spec change and a tracker ID (rule 1).

**Summary of the answer to the owner**
1. Create all four accounts by hand, once, and document it. Programmatic account creation is not something any of the four permits (section 1).
2. Official APIs let us **upload/schedule, read analytics, read and moderate comments** on YouTube and Instagram, **read and manage stream metadata and clips** on Twitch, and **post only privately until an audit passes** on TikTok. Unattended TikTok LIVE is not viable. Comment moderation by API is not available to us on TikTok (section 2).
3. Do not build engagement automation, scrapers, view-botting, or mass-templated AI Shorts (section 3).
4. The low-effort flow that is allowed: stream, then auto-clip candidates, then a review queue, then one-tap owner approval, then a scheduled post per platform with the right labels (section 4).
5. Build a **read-mostly "Brand Ops" bot** in its own container with its own credentials, notifying through Discord + ntfy + Command Center, with nothing publishing without owner approval at first (section 5).

---

## 1. Account creation and verification

### 1.1 Is programmatic account creation permitted?

Expectation confirmed in substance: **no**. No source this session showed any of the four platforms offering an API to create user accounts, and each platform's terms or integrity policy bars automation that creates accounts or evades its systems. Exact clause wording was **not** read from the live terms; the quotes below are from search excerpts.

| Platform | What the excerpts said | Tag |
|---|---|---|
| Twitch | Terms of Service prohibit access "by means of any robot, spider, scraper, crawler, or other automated means"; Twitch's transparency report says mass account creation is a driver of proactive enforcement against inauthentic accounts. No clause naming "account-creation scripts" was found. Developer Services Agreement bars bots that engage in "spam or false follows". | `[EXCERPT-OFFICIAL]` [S10, S11, S12] |
| YouTube / Google | YouTube Terms: no access "using any automated means (such as robots, botnets or scrapers)" except search engines following robots.txt or with prior written permission. | `[EXCERPT-OFFICIAL]` [S13] |
| TikTok | TikTok's Integrity and Authenticity page "strictly prohibit[s] automation tools, scripts, or other tricks designed to bypass our systems"; the Terms bar scraping via automated "bots". A specific "bots to generate fake accounts" ban appears in TikTok Shop creator materials. TikTok does allow multiple accounts in general. | `[EXCERPT-OFFICIAL]` [S14, S15] |
| Instagram / Meta | Instagram Terms of Use bar attempting to create accounts or access/collect information in unauthorized or automated ways without express permission; Meta's developer policies list creating bots "at very high frequencies" [CORRECTED 2026-10-18: this wording is in section 5, the Messenger / Instagram Messaging policy (spam), updated 2026-02-03, not a general posting rule; see PLATFORM-POLICY-VERIFICATION-2026-10-18 M6] and "facilitating inauthentic behavior". Meta's Automated Data Collection Terms require express written permission. | `[EXCERPT-OFFICIAL]` [S16, S17, S18] |

**Rule for this project:** accounts are created by the owner in a normal browser/app session. Agents never create, log into, or drive consumer accounts through UI automation (that would also be "automated means"). Agents only use OAuth-granted API access (section 2).

### 1.2 What each platform asks for

| | Twitch | YouTube (Google) | TikTok | Instagram (Meta) |
|---|---|---|---|---|
| Minimum age | 13; 13 to age of majority only under parent/guardian supervision `[VERIFIED 2026-10-18]` [S10] (also 16 in Australia; PLATFORM-POLICY-VERIFICATION-2026-10-18 T22) | Google Account age rules `[UNVERIFIED]` (not searched) | 13, some regions higher; LIVE needs 18+ `[EXCERPT-OFFICIAL]` [S19, S20] | 13 `[UNVERIFIED]` (not confirmed this session) |
| Identity | Email; phone/email verification required for some community tools, not for going live `[EXCERPT-OFFICIAL]` [S21] | A Google Account, then a channel. **Brand Account** channel can have a different name and multiple managers; Google now steers to **channel permissions** (Owner/Manager/Editor/Viewer) in Studio rather than sharing the Google Account `[EXCERPT-OFFICIAL]` [S22] | Email or phone; extra checks (SMS/email, CAPTCHA) on suspicious activity `[EXCERPT-OFFICIAL]` [S19] | Email or phone `[UNVERIFIED]`; managed in Meta Accounts Center `[UNVERIFIED]` |
| Account type | One type (channel). Dev console is separate (below). | Personal-name channel vs Brand Account channel (above) | Personal; a TikTok Business Account exists (switch process not confirmed); business accounts reportedly see only the Commercial Music Library `[3P]` [S23] | **Professional account (Business or Creator)** is required for API publishing; switching is in Settings and can be reverted; a **Facebook Page is optional** for the professional account but required for the "Facebook Login" API path `[EXCERPT-OFFICIAL]` [S24, S25] |
| 2FA / passkeys | 2FA is required to register a developer app; Affiliates must enable 2FA before monetizing `[EXCERPT-OFFICIAL]` [S26, S27]. Passkey support: not found `[UNVERIFIED]` | Passkeys supported on personal Google Accounts `[3P]` [S28] | 2-step verification (phone/email/authenticator) `[EXCERPT-OFFICIAL]` [S19]; passkeys reported `[3P]` [S28] | Passkeys on Facebook; Instagram reportedly only via a linked Facebook login that has a passkey `[3P]` [S28]. Re-check. |
| Developer access | dev.twitch.tv: register an app (needs 2FA) | Google Cloud project + OAuth consent screen + enable YouTube Data API v3 | TikTok for Developers account, then **submit an app for review** before any API access ("typically days to two weeks" is `[UNVERIFIED]`: no review duration is on TikTok's page, PLATFORM-POLICY-VERIFICATION-2026-10-18 K6 [CORRECTED 2026-10-18: was `[EXCERPT-OFFICIAL]`]; the review rules are `[VERIFIED 2026-10-18]`: custom app name, demo video(s), sandbox for the first review) [S29] | Meta developer app. Own account only = Standard Access (no App Review / Business Verification); other people's accounts = Advanced Access (App Review + Business Verification) `[VERIFIED 2026-10-18]` [S30] |

### 1.3 Eligibility thresholds reported (re-check before relying)

| Platform | Threshold | Tag |
|---|---|---|
| Twitch Affiliate | Verified on blog.twitch.tv/en/2026/05/13/monetization-for-all/: **25 followers, 4 hours streamed, 4 different days, min 3 average concurrent viewers on 4 different days** (previously 50 followers / 8 h / 7 days / 3 viewers); qualifying streamers automatically receive an email and a notification, no application [CORRECTED 2026-10-18: was "reportedly lowered ... [EXCERPT-OFFICIAL]"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T1]; 2FA and tax setup needed to monetize. Non-recurring schedule segments are Affiliate/Partner only (PLATFORM-POLICY-VERIFICATION-2026-10-18 T3); Channel Points are being opened to all streamers, see section 2.1 (PLATFORM-POLICY-VERIFICATION-2026-10-18 T2). | `[VERIFIED 2026-10-18]` [S31, S32, S33]; old figures `[3P]` |
| YouTube live streaming | Verify a phone number (YouTube Studio, Settings, Channel, Feature eligibility); then a wait of about 24 hours before the first live stream; a phone number can verify no more than 2 channels per year [CORRECTED 2026-10-18: was "a limited number of channels"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y16]; first enablement may take up to 24 hours; live streamers must be 16+; no live streaming restrictions in the past 90 days. Mobile live reportedly needs 50 subscribers `[UNVERIFIED]`: the help page could not be found (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y17), and it is not needed for an encoder stream. | `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y16), except mobile live; earlier `[3P]` [S34] |
| TikTok LIVE | 18+ is official; the follower number is not published ("required number of followers, which may vary by region") [CORRECTED 2026-10-18: was "about 1,000 followers"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K8]; gifts need 18+ (19 in South Korea). Other numbers on the web (50, 200, 16 years) conflict with TikTok's own FAQ. | 18+ `[VERIFIED 2026-10-18]`, follower threshold `[UNVERIFIED]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 K8) [S20]; others `[CONFLICT]` |
| Instagram Live / Reels | No follower threshold found. | `[UNVERIFIED]` |

### 1.4 Handle strategy

- **Brand name is unresolved** (Q-BRAND-6: "Operation Nexus" is a working title; owner favorites include "Hiveplex"). Reserving handles now (Q-MKT-3) risks four renames later. Recommendation: reserve the **same handle string on all four platforms the same day**, choose it only after the Q-BRAND-6 clearance search, and keep one short fallback (e.g. a neutral suffix) written in the setup log. Renaming costs: Twitch name change limits, YouTube handle change limits, TikTok username change limits `[UNVERIFIED: none of these limits was researched]`.
- Q-LEGAL-6/8: public-facing owner identity is "saltyseraphcodes" and the project uses a dedicated project address, never a personal email. So: **one dedicated project mailbox per brand** (placeholder `<project-ops-email>`; a shared alias such as `<contact-alias>@<project-domain>` for public contact), with **no personal address on any platform account**.
- Q-MKT-2 already decided on new, clean accounts for all four platforms. The old Scrap Mechanic channel only announces the move once.
- Keep handles identical where available. Where not, document the variant in the setup log so the Brand Ops bot (section 5) can resolve platform to handle.

### 1.5 Manual setup procedure (one-time, owner, about 2 to 3 hours plus waits)

Write the real run into `deploy/runbooks/` (private ops repo for anything with identifiers) as it happens. No real addresses, numbers or codes go in this public repo.

1. **Project mailbox + domain alias.** Create `<project-ops-email>`. Enable the mailbox provider's strongest MFA. Store recovery codes offline (paper or the password manager's secure note), not in any repo.
2. **Password manager entry per platform** (one vault, project-only). Prefer **passkeys** where the platform supports them (Google yes; TikTok reported; Meta via Facebook; Twitch unknown), with a TOTP authenticator as fallback and a hardware key as the second factor for the Google account if the owner has one `[UNVERIFIED that the owner has one]`.
3. **Google first**: create the Google Account on the project mailbox, then create the YouTube channel as a **Brand Account** channel so ownership can later be transferred or shared via channel permissions without sharing the login. Enable phone verification and start the 24 h live-streaming wait immediately (it is a calendar cost).
4. **Twitch**: create the account, enable 2FA (needed for the dev console and monetization), set the stream title/category defaults, add a channel panel with the "Synthetic voices" disclosure (Q-AI-6).
5. **TikTok**: create the account with the project mailbox; switch to a business account only if the Commercial Music Library or business API features are wanted `[UNVERIFIED process]`. Remember the 18+ LIVE gate and the unpublished follower threshold (section 1.3) [CORRECTED 2026-10-18: was "18+/1,000-follower"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K8].
6. **Instagram**: create the account, switch to a **Professional (Creator or Business)** account. Decide the API path up front: **Instagram Login** (no Facebook Page needed) is simpler for a solo owner than Facebook Login (needs a linked Page) `[EXCERPT-OFFICIAL]` [S25]. Connect a Facebook Page only if Meta Business Suite scheduling is wanted.
7. **Developer registrations** (do these when a feature needs them, not all at once): Twitch dev app (needs 2FA), Google Cloud project + OAuth client, TikTok for Developers + app review, Meta developer app. Use the project mailbox for every one.
8. **Setup log** in the private ops repo: platform, handle, date created, which mailbox, which 2FA methods, where recovery codes live (location only, never the codes), and the date each API app was registered.
9. **Two-person recovery**: the Command Center owner/break-glass model (ADMIN-RBAC) already assumes one owner plus a sealed recovery. Mirror it: a sealed offline envelope with mailbox recovery info.

### 1.6 Credential and passkey hygiene (solo owner)

- Platform **logins** (passwords, passkeys, 2FA seeds) live only in the owner's password manager and device keychains. They never go to the Brand Ops bot, an agent, `.env` or the repo.
- The bot gets only **OAuth tokens** with the narrowest scopes (section 5.5). Revoking a token must never require changing the account password.
- A passkey on a phone and a second passkey on the Mac or Windows PC (or a hardware key) avoids a lockout if one device dies. Test the recovery path once, on purpose.
- Google Workspace-style shared logins are not needed: YouTube channel permissions and Meta roles allow adding a helper later without sharing a password `[EXCERPT-OFFICIAL]` [S22, S30].
- Rotate on device loss, on collaborator removal, and after any suspected leak (Q-ARCH-10 rotation rules apply to bot tokens).

---

## 2. What official APIs allow

### 2.0 Per-platform answer card

Legend: Y = yes via official API; Y* = yes with an approval/audit gate; M = manual only; N = not available; ? = not confirmed.

| Capability | Twitch | YouTube | TikTok | Instagram |
|---|---|---|---|---|
| (a) Schedule / post | Not a posting platform. Can set title/category, post chat announcements, create schedule segments (non-recurring needs Affiliate). Y | Y* video upload and Shorts; whether unverified projects are still locked private is a conflict in Google's own docs (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y8) [CORRECTED 2026-10-18: was "unverified projects are locked private"]; scheduling a publish time `[UNVERIFIED: not read this session]` | Y* **Direct Post, private-only until the client passes an audit**; Direct Post's Intended Use also excludes a single-owner publisher, so use inbox drafts or manual posting (PLATFORM-POLICY-VERIFICATION-2026-10-18 K3) [CORRECTED 2026-10-18: Intended Use was not mentioned before] | Y Reels via container + publish, professional account, per-account daily cap |
| (b) Upload as draft for human approval | N/A (clip edit URL is a manual step) | Upload as private, owner flips to public in Studio (works even before audit since uploads are private anyway) | Y **Upload-to-inbox draft** (`video.upload`); creator finishes in the TikTok app; max 5 pending shares per 24 h `[VERIFIED 2026-10-18]` | ? Not found as an API concept. A container can be created and held unpublished until `media_publish`, which gives a similar effect `[3P]` |
| (c) Read comments / mentions | Chat via EventSub; no social feed | Y `commentThreads.list` (cost 1 unit) | **N** for us. Research API comments are for approved researchers only | Y comments + mentions + live comments via webhooks (`instagram_business_manage_comments`) |
| (d) Read analytics | Y partial: stream, videos, followers, subscriptions endpoints; no general "creator analytics" API found `[UNVERIFIED]` | Y YouTube Analytics API + Reporting API (scope wording conflicts between pages) | ? Display API lists videos/profile; analytics not confirmed | Y Insights API (`views`, `reach`; `impressions`/`plays` deprecated; up to 48 h lag) |
| (e) Moderate | Y moderation endpoints and `channel.moderate` events (scopes verified in PLATFORM-POLICY-VERIFICATION-2026-10-18 T7 to T11) [CORRECTED 2026-10-18: was "scopes not fully confirmed"] | Y `comments.setModerationStatus` (50 units); moderate live chat `[UNVERIFIED endpoints]` | **N** | Y hide/delete comments with the comments permission (details `[UNVERIFIED]`) |
| (f) Run live automatically | Y standard RTMP from the broadcast host; reruns must be labelled; no explicit rule against unattended play found `[PLATFORM-REALITY-CHECK]` | Y `liveBroadcasts`/`liveStreams` management, plus the stream key route; chat quota constraints (PLATFORM-REALITY-CHECK) | **N** no LIVE API, and LIVE guidelines discourage recorded/static/unattended streams | **N/?** no live-start API found `[UNVERIFIED]` |

### 2.1 Twitch (Helix + EventSub)

- **App registration**: dev.twitch.tv console; needs 2FA on the account `[EXCERPT-OFFICIAL]` [S26]. Developer Services Agreement applies: request only scopes the current features need, no spam/false follows, caching limited to 24 h unless agreed `[VERIFIED 2026-10-18]` [S12] (PLATFORM-POLICY-VERIFICATION-2026-10-18 T19).
- **Rate limits**: token bucket per client ID per user per minute; each endpoint has a point cost (default 1); 429 when empty; read `Ratelimit-*` headers instead of assuming a size. Send Chat Message uses its own bucket. Chat announcement: one per 2 seconds. Create Clip has no special limit found beyond the general bucket `[EXCERPT-OFFICIAL]` [S35].
- **Stream info (title/category)**: Modify Channel Information, scope `channel:manage:broadcast` `[EXCERPT-OFFICIAL]` [S35].
- **Clips**: Create Clip needs `clips:edit`; asynchronous (poll Get Clips; after 60 s assume failure [CORRECTED 2026-10-18: was 15 s; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T5]); captures up to 90 s of the stream, clip 5 to 60 s (default 30). The broadcast must be live, in practice. Get Clips Download is live (`GET /helix/clips/downloads`, 100 requests/min, scope `editor:manage:clips` or `channel:manage:clips`, links are temporary) [CORRECTED 2026-10-18: was "announced in open beta; availability UNVERIFIED"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T6] [S36]. Twitch's own Clip Editor converts to vertical and shares to **YouTube Shorts**; TikTok/Instagram are manual uploads (2023 reports, `[3P]` [S37]).
- **Stream markers**: Create Stream Marker, `channel:manage:broadcast`, only while live `[EXCERPT-OFFICIAL]` [S35]. Useful to tag "excitement" moments for CLIPS-REPLAY.
- **Announcements**: Send Chat Announcement (app token supported per changelog; moderator scope `moderator:manage:announcements`, 1 per 2 s [CORRECTED 2026-10-18: was "moderator scope name UNVERIFIED"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T11]).
- **Channel points**: Create Custom Reward, `channel:manage:redemptions`, max 50 rewards. Twitch opened Channel Points to all streamers starting May 2026 (US first, global "later this year"), while the API reference still lists a 403 for non-Affiliates; treat 403 as a handled state [CORRECTED 2026-10-18: was "Affiliate/Partner only (403 otherwise)"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T2] `[CONFLICT]` inside Twitch's own pages [S38]. Governed by the Channel Points AUP [S12].
- **Schedule**: `channel:manage:schedule`; segments need start time, timezone, duration 30 to 1,380 min; non-recurring segments are Affiliate/Partner only `[VERIFIED 2026-10-18]` [S38] (PLATFORM-POLICY-VERIFICATION-2026-10-18 T3).
- **EventSub**: WebSocket transport requires a **user** token; up to 3 connections, 300 enabled subscriptions each; `max_total_cost` docs inconsistent (10 vs 10000 in samples) `[CONFLICT]`, confirmed in Twitch's own docs on 2026-10-18: the text says 10, the sample responses show 10000 (PLATFORM-POLICY-VERIFICATION-2026-10-18 T17). Subscriptions that need the user to authorize your app have no cost; `stream.online` costs unless the user authorized your app. `channel.follow` v2 needs `moderator:read:followers`; `channel.subscribe` needs `channel:read:subscriptions` `[EXCERPT-OFFICIAL]` [S39]. Support events: see SUPPORT-AND-SCRAPING-RESEARCH.
- **Chat**: covered by CHAT-GATEWAY; Brand Ops does not need chat (section 5.6).

### 2.2 YouTube (Data API v3, Live Streaming API, Analytics/Reporting APIs)

- **Quota model changed in 2026** `[EXCERPT-OFFICIAL]` [S40, S41]: default is **10,000 units/day for most endpoints**, plus separate buckets of **100 `videos.insert` calls/day and 100 `search.list` calls/day** (revision history entry dated 2026-06-01; a Dec 2025 entry cut the upload cost from about 1,600 to about 100 units). Older guides still say 1,600 units; PLATFORM-REALITY-CHECK §5 has since been corrected. Verified on the quota calculator, 2026-10-18: 10,000 units + 100 `videos.insert` + 100 `search.list` per day; `videos.insert` costs 1 unit in its bucket [CORRECTED 2026-10-18: was `[CONFLICT]`; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y1, Y2]. The cost per call is visible in the Cloud Console quota page; confirm there.
- **Costs seen** (excerpt of the quota calculator): `thumbnails.set` 50, `commentThreads.insert` 50, `comments.insert` 50, `setModerationStatus` 50, `commentThreads.list` 1, `liveBroadcasts.bind` 1, `liveStreams.insert` 1; `liveBroadcasts.insert` 1 [CORRECTED 2026-10-18: was "unconfirmed"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y7] `[VERIFIED 2026-10-18]` [S40]. Invalid requests still cost at least 1.
- **Unverified API project lock**: Conflict in Google's own docs: the 2020-07-28 revision-history entry says `videos.insert` uploads from unverified API projects are restricted to private, but the current `videos.insert` reference says "Videos uploaded from unverified API projects are not restricted to private viewing mode", and no later history entry reverses the 2020 one. Test with a real upload before relying on either [CORRECTED 2026-10-18: was "restricted to private until a compliance audit passes; the call still succeeds, silently private"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y8] `[CONFLICT]` [S42, S43]. Quota is unrelated to this lock. The audit and quota extension both go through the **YouTube API Services Audit and Quota Extension Form**; no processing time is published ("A member of YouTube's API Services team will contact you as soon as possible") `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y9) [S44]. Appeals use a separate form.
- **OAuth consent screen**: an app in **Testing** status gets refresh tokens that **expire in 7 days** (any scope beyond basic identity), max 100 test users; moving to **In production** removes that, and sensitive/restricted scopes need Google verification `[VERIFIED 2026-10-18]` [S45] (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y10). An unverified app In production is capped at 100 new users in total, a lifetime cap (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y11). Whether `youtube.upload` is sensitive/restricted was not confirmed `[UNVERIFIED]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y12). Practical effect: for a solo owner, a weekly re-consent on a Testing app is a real failure mode (section 5.7).
- **Shorts**: vertical or square videos up to **3 minutes** uploaded on or after 2025-12-08 are classified Shorts by aspect ratio and duration in the app flow; API behavior `[UNVERIFIED]` [S46].
- **Thumbnails, playlists**: `thumbnails.set` (50 units); playlists `[UNVERIFIED]` (not searched).
- **Community posts**: **no public API** to create or read them (a Google issue-tracker thread and 2026 guides say so) `[3P]` [S47]. Manual only. Do not use scrapers or browser automation.
- **Live**: `liveBroadcasts`, `liveStreams`, `liveChatMessages`; chat reading cost and `streamList` analysis in PLATFORM-REALITY-CHECK §2.
- **Analytics**: Analytics API `reports.query` for per-channel metrics; Reporting API for bulk scheduled reports; monetary data needs the monetary scope and a YPP channel. Scope names are inconsistent across pages (`youtube.readonly` vs `yt-analytics.readonly`) `[CONFLICT]` [S48].
- **Comments / moderation**: list threads (1 unit), set moderation status (50), reply (50). A moderation queue of a few hundred comments per day fits the 10,000 budget; heavy reply automation does not.
- **Strikes, copyright claims, policy notices**: shown in Studio (Dashboard, Content tab "Notices") and sent by email from a no-reply address. The **Content ID API** is for content-owner partners, not for us `[EXCERPT-OFFICIAL]` [S49]. No API path to read strikes was found `[UNVERIFIED]`. These are **email/Studio-only** signals.
- **Official scheduling**: Studio scheduled publish; the Data API supports a scheduled publish time on upload `[UNVERIFIED: not read]`.

### 2.3 TikTok (Content Posting API, Display API, Research API)

- **Gate zero**: a TikTok for Developers account, then **app review** ("a few days to two weeks" is `[UNVERIFIED]`: no review duration is on TikTok's page, PLATFORM-POLICY-VERIFICATION-2026-10-18 K6) before you can use any API; mobile apps must be in app stores; app names cannot reference social media companies; the review needs demo video(s) of the end-to-end flow (max 5 videos, 50 MB each) and a sandbox for the first review `[VERIFIED 2026-10-18]` [S29] (PLATFORM-POLICY-VERIFICATION-2026-10-18 K6).
- **Content Posting API** `[EXCERPT-OFFICIAL]` [S50, S51, S52]:
  - **Direct Post** (`video.publish`): the app must call Query Creator Info on the post screen, show the creator's nickname, make the user choose the privacy option with **no default**, and leave interaction toggles **unchecked by default**. This UX contract is incompatible with a fully hands-off pipeline by design.
  - **Intended Use** [CORRECTED 2026-10-18: not mentioned before; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K3]: TikTok's content sharing guidelines list "A utility tool to help upload contents to the account(s) you or your team manages" as not acceptable, and clients must also "be intended for a wide audience". A single-owner Brand Ops publisher is outside the stated Direct Post intent, audit or not. Use inbox drafts or manual posting for our own account; the pages read do not say whether inbox upload needs an audit. `[VERIFIED 2026-10-18]`
  - **Upload to inbox / draft** (`video.upload`, endpoint `.../post/publish/inbox/video/init/`): content lands in the creator's TikTok inbox as a draft for editing and posting in the TikTok app. Cap of **5 pending shares per 24 h** `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 K5).
  - **Unaudited clients**: all content is **private-only**; up to **5 users** posting per 24 h; error `unaudited_client_can_only_post_to_private_accounts`. Lifting the limit needs an audit, then the account must be public and each post set to "Everyone". The audit timeline of 2 to 4 weeks is `[UNVERIFIED]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 K7); the demo-video requirement is verified for app review (PLATFORM-POLICY-VERIFICATION-2026-10-18 K6), and the domain requirement stays `[3P]` `[UNVERIFIED]`.
  - **Caps**: about 15 posts/day per creator account, shared across clients (`spam_risk_too_many_posts`) `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 K2); general rate limits in the Rate Limits page (e.g. 600/min for video query), posting-endpoint rate not confirmed.
- **Display API**: read a creator's profile and public videos (scope listed under "User Display"). Details of fields `[UNVERIFIED]`.
- **Research API**: researchers only (eligible region + non-commercial academic or not-for-profit institution); not available to a game project `[EXCERPT-OFFICIAL]` [S53].
- **Comments / analytics / moderation**: no general-developer comment or analytics API was found. Treat as **manual in TikTok Studio** `[UNVERIFIED]`.
- **LIVE**: no API to read LIVE chat (PLATFORM-REALITY-CHECK §3); LIVE guidelines discourage recorded content, still images and lack of interaction and recommend the creator stay on screen; Pause LIVE exists. TikTok Shop seller pages say still/animated content over 50% of the screen is prohibited in promoted LIVEs, **seller-specific, may not apply** `[EXCERPT-OFFICIAL]` [S54].
- **Recommendation**: TikTok API work is **P5** (ADR-0008). Until then post TikTok by hand from the review queue (copy the file to the phone and use TikTok's own scheduler or app).

### 2.4 Instagram / Meta (Graph API)

- **Two API paths** `[VERIFIED 2026-10-18]` [S25, S55] (PLATFORM-POLICY-VERIFICATION-2026-10-18 M3):
  - **Instagram API with Instagram Login**: tokens are Instagram user tokens; **no Facebook Page needed**; scopes `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, `instagram_business_manage_messages`.
  - **Instagram API with Facebook Login**: Facebook/Page tokens; **requires a linked Page**; scopes `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `instagram_manage_messages`, plus Page permissions.
  - An app implements one path; both serve Business and Creator accounts. Recommendation for us: **Instagram Login**. A connected Facebook Page that requires Page Publishing Authorization blocks publishing until PPA is done on the Facebook Login path (PLATFORM-POLICY-VERIFICATION-2026-10-18 M5, new on 2026-10-18).
- **Access levels**: own professional account only = **Standard Access** in development mode with role holders, no App Review or Business Verification; other people's accounts = Advanced Access (App Review + Business Verification) `[VERIFIED 2026-10-18]` [S30] (PLATFORM-POLICY-VERIFICATION-2026-10-18 M4). That makes Instagram the easiest platform for a solo owner's own account.
- **Content publishing (Reels)** `[EXCERPT-OFFICIAL]` [S56]: create a media container, then publish it with `media_publish`; Meta's own pages disagree: the publishing guide says 100 (Rate Limit) and 50 (carousel Limitations), and the `content_publishing_limit` reference says `quota_total` is "currently 50". Plan for 50 and read the live value per account [CORRECTED 2026-10-18: was "100 API-published posts per account per rolling 24 h ... a third-party reading cites 50 [CONFLICT]"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 M1]. Containers expire after 24 h and are capped at 400 per rolling 24 h [CORRECTED 2026-10-18: was "reportedly ... there may be a 400-container cap [3P]"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 M2]. A video upload is asynchronous: poll container status before publishing `[UNVERIFIED details]`.
- **Insights**: `views` and `reach` per media and user; `plays`/`impressions` deprecated for newer media; data up to 48 h delayed `[EXCERPT-OFFICIAL]` [S57].
- **Rate limits**: Business Use Case limit: calls in 24 h = 4,800 x impressions of the account in the last 24 h, so a tiny new account gets a tiny budget `[EXCERPT-OFFICIAL]` [S57].
- **Webhooks**: `comments`, `live_comments` and `mentions` fields (mentions not sent for private accounts) `[EXCERPT-OFFICIAL]` [S58].
- **DMs**: Messaging API requires `instagram_business_manage_messages`; a **24 h reply window** after the user's message (human-agent tag can extend to 7 days) `[EXCERPT-OFFICIAL]` [S58]. DM auto-reply is an engagement-automation risk (section 3); read-only DM *notification* is acceptable.
- **Official scheduling**: Meta Business Suite scheduling needs a linked Page `[EXCERPT-OFFICIAL]` [S24]; the details of its Reels scheduling `[UNVERIFIED]`.

### 2.5 Officially supported schedulers and clip tools

| Tool | What it does | API/first-party status | Price (all `[3P]`, `[UNVERIFIED]` until checked on the vendor site) |
|---|---|---|---|
| Native: YouTube Studio, TikTok Studio/app, Meta Business Suite, Twitch Clip Editor | Schedule, draft, vertical edit, share clip to YouTube Shorts | First-party by definition | Free |
| Buffer | One queue for YouTube (Shorts), Instagram Reels, TikTok; has a GraphQL API (June 2026 case study) | Official-partner status with each platform not confirmed | Entry around $5/month per channel with a free tier `[3P]` |
| Metricool | Scheduling + analytics | Partner status not confirmed | Free: 1 brand, 20 posts/month; Starter about $20 to $25/month `[3P]` |
| Later | Scheduler (per "social set") | Reels/TikTok/Shorts auto-publish not confirmed | Starter about $25/month, no free plan `[3P]` |
| Streamlabs | Streaming suite, Ultra multistream | Not a scheduler | Ultra about $27/month or $189/year; other figures conflict `[3P]` |
| OpusClip-class AI clippers | Cut long video to short clips | Auto-posting tier uncertain; free plan 60 credits with watermark | Starter about $15/month `[3P]` |

---

## 3. What must NOT be automated, or is risky

| Practice | Why not | Policy text seen | Tag |
|---|---|---|---|
| Auto-follow/like/comment, DM blasts, "growth" bots | Fake or inauthentic engagement; account loss | Meta developer policy lists "creating bots ... at very high frequencies" [CORRECTED 2026-10-18: this wording is in the Messenger / Instagram Messaging section of the Developer Policies (updated 2026-02-03), not a general rule; see PLATFORM-POLICY-VERIFICATION-2026-10-18 M6] and "facilitating inauthentic behavior" [S18]; TikTok bans "automation tools, scripts, or other tricks designed to bypass our systems" [S14]; YouTube's fake engagement policy covers anything that "inflates views, likes, comments" via automated systems [S59] | `[EXCERPT-OFFICIAL]` |
| View-botting, sub-for-sub, buying followers | Twitch lists "viewership tampering" and says participating, organizing or running such services leads to enforcement up to indefinite suspension [S60] (wording `[UNVERIFIED]`: Twitch's help page and Community Guidelines could not be read, PLATFORM-POLICY-VERIFICATION-2026-10-18 T27); YouTube fake engagement policy [S59] (lists viewbotting, `[VERIFIED 2026-10-18]`, PLATFORM-POLICY-VERIFICATION-2026-10-18 Y21) | | `[EXCERPT-OFFICIAL]` |
| Simulated viewers on the public channel | Same family as view-botting. Already decided (Q-LEGAL-7, CG-1): the viewer simulator never touches the public channel. The wording of each platform's policy as applied to a simulator stays `[UNVERIFIED]`. | | |
| Cross-posting the same video everywhere with no adaptation | Instagram (April 2026) stops recommending accounts that regularly repost others' work and requires material transformation `[UNVERIFIED]` [S61, S62] [CORRECTED 2026-10-18: was `[EXCERPT-OFFICIAL]`; the April 2026 change was not found on any official page, only the 2024-04-30 originality update; see PLATFORM-POLICY-VERIFICATION-2026-10-18 M9]; TikTok For You ineligibility for unoriginal/reproduced content [S14]. Our own footage is original, but unmodified reposts of **other people's** clips (viewer highlights from other channels) are risky. Watermarked cross-posts (a TikTok watermark on Reels) are a classic downgrade `[3P]`. | | |
| Mass-templated AI Shorts | YouTube renamed its policy to "inauthentic content" (July 15, 2025): mass-produced or repetitive content is not monetizable; AI content "made with generic or unoriginal templates, giving the impression of mass production" without original insight is ineligible; a series with a recurring format can still qualify if each video has its own storyline `[VERIFIED 2026-10-18]` [S63] (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y13: a YPP monetization rule; nothing about live streams). Matches MARKETING principles and CLIPS-REPLAY §4. | | |
| Unattended TikTok LIVE | TikTok discourages recorded, still-image or no-interaction LIVEs [S54] (`[UNVERIFIED]`: no LIVE-policy text was retrievable, PLATFORM-POLICY-VERIFICATION-2026-10-18 K13); no LIVE API; stream keys reportedly rotate `[UNVERIFIED]` (PLATFORM-REALITY-CHECK §3) | | |
| Reverse-engineered / scraping APIs (TikTokLive-style libraries, YouTube chat scrapers, community-post scrapers, Apify-type actors) | YouTube ToS "automated means ... robots, botnets or scrapers" [S13]; TikTok Terms bar scraping by bots [S15]; Meta Automated Data Collection Terms need written permission [S17]. Also covered in SUPPORT-AND-SCRAPING-RESEARCH. | | `[EXCERPT-OFFICIAL]` |
| Auto-replying in public with LLM text (at first) | Not forbidden by the excerpts seen, but a single bad reply is public and attributable. Start approval-gated (section 5.4). TikTok's consumer Terms (section 3.10) bar using TikTok's own generative-AI features via automated systems unless authorized `[VERIFIED 2026-10-18]` [S15]; that clause does not restrict our own LLM-drafted text, so it is not a reason to avoid LLM-drafted posts [CORRECTED 2026-10-18: was "a further reason not to automate TikTok replies"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 K11]. The TikTok Developer ToS has no generative-AI clause (PLATFORM-POLICY-VERIFICATION-2026-10-18 K12). | | |
| Hiding AI use | See section 4.2. Labeling is required for realistic synthetic media on three of the four. | | |

---

## 4. Allowed, low-effort content flow

### 4.1 The flow

```
stream / replay  ->  clip candidates (CLIPS-REPLAY excitement score; Twitch stream markers)
   ->  review queue (Command Center, mod.clip_review)  ->  owner one-tap approve / reject / "edit later"
   ->  per-platform packaging (variant job)            ->  scheduled post  ->  Brand Ops watches the result
```

- **Candidates**: sim-generated renders (CLIPS-REPLAY §2, §3) at 1080x1920, FoW-redacted while a campaign is running (RP-1). These are **our own footage**, which is the strongest answer to "originality" policies. A Twitch clip made via Create Clip is a fallback for moments the sim didn't score.
- **Review queue**: the existing `clip review queue` in OPS-ADMIN §3 and `mod.clip_review` in ADMIN-RBAC. The owner sees: preview, the excitement reason, a generated caption suggestion, the **AI-disclosure checkboxes pre-filled from provenance** (see 4.2), and per-platform toggles. One tap approves; nothing is posted before that.
- **Packaging per platform** (values are format guidance, `[UNVERIFIED]` against current specs except where cited): 9:16 1080x1920 for all three short-form feeds; YouTube Shorts up to 3 min (square/vertical, since 2025-12-08) [S46]; Reels and TikTok limits not confirmed; captions burned in (owner voice or captions only, per MARKETING); hashtags per platform; a platform-specific title and first comment drafted from the same event but not copy-pasted, so the posts differ.
- **Scheduling**: Q-MKT-4 asks for a scheduled post queue so content flows while the owner travels. Section 4.3 compares how to do it.
- **Devlogs**: long-form YouTube stays manual or semi-manual (owner voice); only the upload and description are assisted. DEVLOG CHECKPOINT blocks (MARKETING) remain the trigger.

### 4.2 Disclosure and labeling requirements

| Platform | Synthetic/AI content rule (reported) | Game footage | Tag |
|---|---|---|---|
| YouTube | Creators must disclose altered or synthetic content that is realistic (a real person saying/doing something they did not, altered footage of a real event/place, a realistic scene that did not happen, music as the main focus). Scripts, ideas, captions and clearly unrealistic content (animation, filters) don't need disclosure. Set in Studio under "AI use" in the upload flow. Labels: below the player for long-form, on the video for Shorts; YouTube **auto-labels** content made with its GenAI tools, carrying C2PA metadata, or caught by internal detection, and those labels cannot be adjusted; the page gives no May 2026 date [CORRECTED 2026-10-18: was "from May 2026 YouTube may auto-label significant photorealistic AI use"; see PLATFORM-POLICY-VERIFICATION-2026-10-18 Y15]. Repeated non-disclosure can mean manual labels, removal, YPP suspension. | Gameplay is not "realistic scene that did not happen" in the sense of the rule, but **synthetic voices** and any photoreal generated imagery should be disclosed conservatively. The sim footage is stylized, so likely no label, but this is a judgment call `[UNVERIFIED]`. YouTube's page lists "Gameplay footage from video games" and "Cloning one's own voice to create voice overs" as not needing disclosure; a generic TTS voice is on neither list (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y14). | `[VERIFIED 2026-10-18]` [S64] |
| TikTok | "AI-generated content" toggle at posting adds "Disclosed by creator as AI-generated"; required for realistic AI imagery/audio/video or significant AI edits; false disclosure *and* failure to disclose are violations; the label can't be edited after posting; labelled content isn't demoted solely for the label. TikTok's own AI effects are labelled automatically. Seller pages and Creator Academy differ on placement `[CONFLICT]`. | Same as above. For synthetic voice-over, treat as disclosable. TikTok's Community Guidelines (2026H2 update, effective 2026-09-24) require labelling AI-generated or significantly edited content that shows realistic-looking scenes or people; the Direct Post field `is_aigc` adds the tag (PLATFORM-POLICY-VERIFICATION-2026-10-18 K9). | `[VERIFIED 2026-10-18]` [S65] |
| Instagram | "AI info" label applied automatically (C2PA/industry indicators) or when people disclose; users must use the disclosure tool for photorealistic video or realistic-sounding audio that was created or altered digitally; penalties for not doing so. | Same. Realistic-sounding synthetic voice may count. | `[EXCERPT-OFFICIAL]` [S66]; `[UNVERIFIED]` against Instagram's Help Center, whose body could not be retrieved (PLATFORM-POLICY-VERIFICATION-2026-10-18 M8) |
| Twitch | No AI-content disclosure requirement found; a Twitch CEO interview (Tokyo Game Show 2026) says none is needed "for now". Kick reportedly added strict disclosure in March 2026. Twitch classification labels exist but a specific AI label was not found. Q-AI-6 already commits us to a channel-panel note regardless. | Q-AI-6: re-check each phase gate (NX-288). | `[3P]` [S67]; still `[UNVERIFIED]`: no Twitch policy page mentioning an AI disclosure requirement was retrievable (PLATFORM-POLICY-VERIFICATION-2026-10-18 T25) |

**Recommended house rule**, independent of what is strictly required: every post whose audio includes TTS voices gets the platform's AI toggle **on** and the caption line "Synthetic voices" (Q-AI-6, DI-5); simulated-bot battles are labeled "simulated test" (Q-MKT-3); real-viewer footage is never implied from simulated footage. The provenance of each clip (sim-rendered, TTS used, owner voice used, simulated actors) is stored with the clip so the label checkbox is pre-filled and auditable.

### 4.3 Build vs buy for a solo developer

| Option | Effort | Control | Risk | Verdict |
|---|---|---|---|---|
| **Native tools only** (Studio, TikTok app, Business Suite, Twitch Clip Editor) | Lowest to start; phone friendly; 3 uploads per clip by hand | Highest, zero API gates | Owner time; inconsistent queue | **Phase 1 to 2**, matches the "manual posting until audits" plan in PLATFORM-REALITY-CHECK §5 |
| **Buy a scheduler** (Buffer/Metricool/Later class) | Low; one queue; some have APIs | Medium; their approvals and outages become ours | Partner status unconfirmed; price creep; lock-in; per-network feature gaps | Good Phase 3 stopgap if the owner wants a single phone queue |
| **Build direct adapters** (YouTube, Instagram, then TikTok) | Medium to high; OAuth, audits, quotas | Highest | YouTube audit and TikTok audit waits; Meta review for anything beyond own account | Build only after audits; own-account Instagram can go first (Standard Access) |
| **Hybrid (recommended)** | Review queue + our own `PublisherPort` interface; first adapter = "export bundle to a folder + notify owner" (works today); later adapters for IG, YouTube, TikTok draft, and optionally a scheduler | Keeps ADR-0010 lock-in low | Slight duplicate work | **Recommended** |

Interface sketch (names are proposals; not a spec):

```
PublisherPort.submit(variant: ClipVariant, when: datetime | None) -> SubmissionHandle   # draft, scheduled or immediate
PublisherPort.status(handle) -> {queued|processing|private|published|rejected, platform_url?}
PublisherPort.capabilities() -> {max_len_s, aspect, label_fields, daily_cap, needs_audit, can_draft, can_schedule}
```

Adapters: `export-folder`, `youtube`, `instagram`, `tiktok-draft`, `scheduler-<vendor>`. Each passes a shared conformance suite like the chat adapters (ADR-0010, CHAT-GATEWAY §1). Vendor SDKs stay inside adapter packages (rule 10a).

---

## 5. Monitoring and review bot ("Brand Ops")

### 5.1 Signals, by platform, and how they can be read

| Signal | Twitch | YouTube | TikTok | Instagram |
|---|---|---|---|---|
| Stream health / online status | EventSub `stream.online`/`offline` + Get Streams (already OPS-ADMIN "stream-live probe") | Live Streaming API broadcast status; stream health `[UNVERIFIED field names]` | None | None |
| New followers/subs, milestones | `channel.follow` v2 (`moderator:read:followers`), `channel.subscribe` (`channel:read:subscriptions`) [S39] | Channel statistics (subscriber counts may be rounded) `[UNVERIFIED]` | Display API profile stats `[UNVERIFIED]` | User insights/profile fields |
| Clip/VOD/video performance | Get Clips/Videos (views) | Analytics API / Reporting API [S48] | Display API video list `[UNVERIFIED]`; otherwise manual | Media insights `views`, `reach` (<=48 h lag) [S57] |
| Comments and mentions | Chat (not part of Brand Ops) | `commentThreads.list` (1 unit) [S40] | **Not via API** | Webhooks `comments`, `mentions`, `live_comments` [S58] |
| DMs | Whispers (not for Brand Ops) | None | None | Messaging API with 24 h window [S58]; read-only notification only |
| Policy strikes / copyright claims | **Email and dashboard** only (not found as API) `[UNVERIFIED]` | **Studio and email only**; Content ID API is partner-only [S49] | In-app/email notices `[UNVERIFIED]` | In-app "Account Status" and email; API `[UNVERIFIED]` |
| Analytics anomalies | Derived by us from the above | Derived | Manual | Derived |
| Moderation queue | Held AutoMod messages (`POST /helix/moderation/automod/message`, scope `moderator:manage:automod`) [CORRECTED 2026-10-18: was `[UNVERIFIED API]`; see PLATFORM-POLICY-VERIFICATION-2026-10-18 T9] | Comments held for review (`setModerationStatus`) | Manual | Comments (hide/delete) |
| Uptime of our own pipeline | Prometheus/Grafana/Loki, OPS-ADMIN §2 | same | same | same |

**Gaps that stay manual** (so they must reach the owner another way): policy strike/claim notices (email to the project mailbox), TikTok comments and analytics, YouTube community posts, Instagram account-status warnings, any appeal. The bot can **watch the project mailbox** (IMAP/OAuth read-only mail rule that forwards only platform security/policy senders) `[UNVERIFIED feasibility; privacy review needed]`, or the owner forwards them. Prefer a Gmail/Workspace *filter that forwards to a Discord/ntfy bridge* over giving the bot mailbox read scope.

### 5.2 Alerting and the review/clear loop

One **source of truth**: a `brand_ops_items` queue in the Command Center (private, tailnet + Discord only, Q-ARCH-7/Q-RB-4). Discord, ntfy and email are *notifications and shortcuts* into that queue, never a second copy of state.

- **Item** = `{id, kind, platform, severity, summary, detail_ref, state, created_at, due_at, evidence_hash}`; kinds: `clip_approval`, `post_result`, `comment_flag`, `mention`, `milestone`, `anomaly`, `token_expiring`, `quota_low`, `policy_notice_forwarded`, `platform_outage`.
- **States**: `new -> seen -> approved|rejected|snoozed|cleared`. "Clear" removes it from the open list but keeps the audit row.
- **Discord (private staff channel)**: one message per actionable item with buttons (Approve / Reject / Snooze / Open in Command Center). Buttons are message components; the interaction must be acknowledged within 3 s (defer, then edit) and the token is valid 15 min; ephemeral replies for sensitive detail `[EXCERPT-OFFICIAL]` [S68]. Slash commands (`/brandops queue`, `/brandops pause`, `/brandops digest`) are application commands. **Authorize by Discord user ID allowlist = owner**, not by channel membership, and sign `custom_id` (item id + HMAC) so a stale or forged button does nothing.
- **Push**: ntfy (Q-OPS-4 already chose ntfy + a private Discord channel). ntfy messages support priority 1 to 5 and up to three action buttons (view/http/copy) `[EXCERPT-OFFICIAL]` [S69]; use priority 5 only for stream-down and strike notices, priority 3 for approvals, priority 1 for milestones.
- **Email digest**: one daily summary (open items, results of yesterday's posts, quota/token status). Low-urgency items go only here.
- **Command Center**: full detail, bulk clear, history, kill switch.
- **Noise control**: dedupe by `evidence_hash`; batch milestone alerts; quiet hours (owner travels); cap alerts/hour with a "digest" fallback.

### 5.3 Does it connect to the Discord bot and the stream/chat bots? Recommendation

**Share (reuse code and a narrow event feed):**
- The **adapter interface pattern and conformance-suite approach** from CHAT-GATEWAY / ADR-0010 (a `BrandPlatformAdapter` Protocol with `capabilities()` and `health()`), as a *library*, not a running process.
- A **one-way internal event bus feed** of already-sanitized, non-sensitive facts from the sim/gateway to Brand Ops: `stream_online/offline`, `campaign_milestone`, `clip_candidate_ready`, `adapter_health`, `quota_used`. Brand Ops subscribes; it cannot publish game commands.
- The **observability stack** (Prometheus/Loki, ntfy topic) and the **Discord library** (discord.py v2.7.1, PLATFORM-REALITY-CHECK §9).

**Isolate (separate process/container, separate credentials, separate Discord application):**
- Brand Ops runs as its own container (alongside the LLM advisor pattern, LLM-2 / SEC-LLM-5 style): **no stream keys, no chat-bot tokens, no sim DB/volumes, no admin write tokens, no LLM provider keys.** It gets only its own platform OAuth tokens (below) and a database of its own.
- **Why**: Brand Ops ingests hostile text (comments, mentions) and holds tokens that can post publicly. The chat gateway holds Twitch send scopes and talks to the sim; the broadcast host holds stream keys. A compromise of any one must not give publishing power to the others.
- **A separate Discord application and token** for the staff-approval bot, distinct from the public "War Briefing" announcer. A leak of the public bot's token must not allow forging approval buttons.
- **A separate Twitch app registration (client ID)** for Brand Ops so rate buckets and EventSub subscription limits (per client ID/user) are independent of the gateway's.
- **Hostile comment text** never flows into a process that can post or into an LLM that has tools. If an LLM drafts replies, it goes through the existing `LlmClient` RPC (no credentials, egress allowlist, LLM-2), output parsed to a typed schema and treated as a suggestion (rule 5).
- It must not receive raw chat from the gateway. Viewer chat is a different trust problem (THREAT-MODEL; CHAT-GATEWAY). Brand Ops sees only platform *social* surfaces plus the sanitized event feed.

### 5.4 Human-in-the-loop approval model

| Stage | Behavior |
|---|---|
| **Stage 0 (default, P1 to P3)** | **Nothing public is posted, replied to, hidden or deleted without a recorded owner approval.** Bot may read, summarize, draft, and notify. |
| **Stage 1** | Approved-content scheduling: owner approves a clip once; the scheduler publishes at the chosen time (still a human decision). |
| **Stage 2 (later, opt-in per rule)** | Low-risk auto-actions behind a **kill switch** and an allowlist: e.g. hide comments matching an exact spam rule, thank-you replies from a fixed template set to milestone events, pin the weekly schedule. Each rule has a rate cap, is logged, and is reversible. Never: DMs, replies to criticism, anything about moderation disputes, politics or money. |
| **Kill switch** | Command Center and Discord `/brandops pause`: stops all write adapters instantly (tokens retained, scopes unused). Consistent with SEC-MOD-3 style kill switches. |
| **Two-person rule** | Sole-owner self-approval is allowed and audit-flagged as in ADMIN-RBAC (`SELF_APPROVED_SOLE_OWNER`); service accounts never hold OWNER/ADMIN and can't approve their own requests (RB-7). The Brand Ops service account therefore has a scoped role that can *propose*, never *approve*. |

### 5.5 Credentials, tokens, least privilege

- **Storage**: Q-ARCH-10: secrets in the private `operation-nexus-ops` repo encrypted with sops+age to per-machine keys; Brand Ops runs on the Linux server, so only that machine's age key decrypts its secret file. Tokens obtained at runtime (refresh tokens) are kept encrypted at rest (same as CHAT-GATEWAY §2: refresh tokens encrypted). Never in `.env` committed, logs (redaction filter in OPS-ADMIN §2) or Discord messages.
- **Read-only first**: Phase A tokens carry read scopes only (`channel:read:*`, YouTube read/analytics, Instagram `instagram_business_basic` + insights). **Write scopes are issued to a separate "publisher" credential set** used by a second worker that only executes approved queue items. The reader cannot publish; the publisher cannot read the comment firehose.
- **Per-platform notes**: Twitch user tokens refresh and can be revoked in connections settings `[UNVERIFIED path]`; Google refresh tokens expire after 7 days for **Testing** apps [S45] `[VERIFIED 2026-10-18]` (PLATFORM-POLICY-VERIFICATION-2026-10-18 Y10) (put the app **In production** or accept weekly re-consent), and unused tokens may be revoked `[UNVERIFIED]`; Instagram long-lived tokens need refresh `[UNVERIFIED details]`; TikTok access/refresh token lifetimes `[UNVERIFIED]`.
- **Revocation runbook**: one page in `deploy/runbooks/` ("rotate secrets" already listed): revoke per platform, delete the sops entry, re-consent, confirm the health check turns green.
- **Least privilege** includes the *account roles*: Instagram and YouTube support non-owner roles for helpers `[EXCERPT-OFFICIAL]` [S22, S30]; the bot authorizes through an OAuth grant by the owner, never with the owner's password.

### 5.6 Audit logging

Append-only, same DM-3 rule as other admin actions (ADMIN-RBAC): who/what/when, item id, before/after state, platform response id, hash of the exact media and text approved. Posting records store the *approved artifact hash* so a swapped file can't publish. Retain in the Command Center DB; export via `audit.export`.

### 5.7 Failure modes

| Failure | Detect | Behavior |
|---|---|---|
| Token expired/revoked (e.g. Google Testing 7 days) | 401 on health probe; `token_expiring` item | Stop that adapter, high-priority alert, one-tap re-auth link; pipeline continues for other platforms |
| Quota exhausted (YouTube 10,000 units or 100 uploads/day; Instagram publishing cap; TikTok pending-share cap) | local counters + 403/429 | Queue holds; resume at reset; alert at 80% (matches OPS-ADMIN LLM/TTS 80% pattern) |
| Platform outage / API 5xx | health probe, status pages `[UNVERIFIED URLs]` | Retry with backoff, no duplicate posts (idempotency key = approved artifact hash), digest note |
| Silent private lock (YouTube unaudited project, whether it still applies is a conflict in Google's docs, PLATFORM-POLICY-VERIFICATION-2026-10-18 Y8; TikTok unaudited) | post-publish read-back shows `private` while intended `public` | Mark `post_result` item "published private - audit required"; never report success |
| Policy/API changes | weekly diff alert on tracked doc URLs; phase-gate re-check (Q-AI-6 note, NX-288) | Item "re-verify platform policy"; adapters feature-flagged |
| Duplicate or wrong post | idempotency + artifact hash | Cancel path in queue; platform delete requires owner approval |
| Hostile comment content | escape on display, length cap, no link auto-open | Render as plain text in Discord (suppress embeds/mentions); never act on instructions in comments |
| Bot compromise | alert on write attempts outside approved items | Kill switch; revoke tokens; rotate Discord token |

---

## 6. Feasibility, effort and cost

Effort: owner minutes per week in steady state / agent build effort (S = under 1 day, M = 1 to 3 days, L = a week or more). Cost: only what sources reported, all `[UNVERIFIED]` until the vendor page is checked.

| Capability | Manual | Semi-automated | Fully automated | Risk | Cost note |
|---|---|---|---|---|---|
| Account creation | **Yes (required)** | n/a | **Not permitted** | Ban if scripted | Free |
| Handle reservation | Yes | n/a | n/a | Brand rename (Q-BRAND-6) | Free |
| Twitch stream title/category/schedule | Possible | **Auto-set from campaign state (S)** | OK after Affiliate for non-recurring schedule | Low | Free |
| Twitch clips + markers | Clip Editor | **Create Clip/marker on excitement score (S)** | Same, review queue before share | Low | Free |
| YouTube Shorts/devlog upload | Studio | **Upload private via API, owner flips public (M)** after OAuth in production | Public auto-publish only after audit | Silent private lock; quota | Free; audit effort |
| YouTube analytics/comments read | Studio | **Read-only digest (M)** | Auto-hide spam later | Quota; scope confusion | Free |
| YouTube live broadcast mgmt | Studio | **liveBroadcasts create/bind (M)** | Auto-restart watchdog (OPS-ADMIN) | 24 h verification wait; chat quota | Free |
| YouTube community posts | Studio only | none | **Not available by API** | Scraping = ToS violation | n/a |
| TikTok draft upload | App | **Upload-to-inbox after app review (M)** | Direct post after audit (L, UX contract blocks hands-off; Intended Use also excludes a single-owner publisher, PLATFORM-POLICY-VERIFICATION-2026-10-18 K3) | Private-only until audit; review wait | Free; audit effort |
| TikTok comments/analytics | App/Studio | none | **Not available** | n/a | n/a |
| TikTok LIVE | Owner present | none | **Don't** | Eligibility loss | n/a |
| Instagram Reels publish | Phone | **Container + publish via Instagram Login, Standard Access (M)** | Same behind queue | plan for 50/day and read the live `content_publishing_limit` (Meta's own pages conflict, PLATFORM-POLICY-VERIFICATION-2026-10-18 M1) [CORRECTED 2026-10-18: was "100 or 50/day cap [CONFLICT]"]; small-account call budget | Free |
| Instagram comments/mentions | App | **Webhook to review queue (M)** | Hide spam by rule (stage 2) | Hostile text; permission naming drift | Free |
| Instagram DMs | App | notify only | **Don't auto-reply** | 24 h window; engagement-bot risk | Free |
| Scheduler (single queue) | Native tools | **Buy: Buffer/Metricool class (S)** | Via our `PublisherPort` | Vendor lock-in; partner status unknown | about $0 to $25/month `[3P]` |
| AI clipper (Opus-class) | n/a | optional for devlog highlights | **Don't use for mass shorts** | Inauthentic-content policy | about $15/month `[3P]` |
| Brand Ops reader + digest | n/a | **Build (M to L)** | n/a | Credential hygiene | Free (self-hosted ntfy/Discord) |
| Strike/claim detection | Email | forward-to-Discord rule (S) | Not via API | Missed notice | Free |

### 6.1 Phased rollout (maps to ROADMAP)

| Phase | Social/Brand work |
|---|---|
| **P0 to P1** | Manual accounts per 1.5 once Q-BRAND-6 settles; setup log in ops repo; reserve handles (identical string); channel panel + "Synthetic voices" note; devlog checkpoints and auto-captured footage already planned (MARKETING). Verify every `[UNVERIFIED]` threshold on the live pages. **No automation.** |
| **P1/P2 boundary** (first moving map) | First public post, by hand, labeled "simulated test" where applicable (Q-MKT-3). |
| **P2** (Twitch alpha) | Brand Ops **Stage 0 read-only**: Twitch EventSub milestones, stream health into Discord + ntfy; `export-folder` PublisherPort; Twitch clip/marker creation. |
| **P3** (public beta, YouTube, clip review queue) | YouTube OAuth app **In production**; private-upload adapter; start the YouTube audit/quota-extension process early because no turnaround was published; Instagram adapter on Standard Access (own account); comment/mention review queue; email digest; optionally a Buffer-class scheduler adapter. |
| **P4** | Stage 1 scheduled publish after approval; Instagram insights; weekly analytics digest; first Stage 2 rules (spam hide) behind kill switch. |
| **P5** | TikTok app review and draft adapter, direct post not planned because its Intended Use excludes a single-owner publisher (PLATFORM-POLICY-VERIFICATION-2026-10-18 K3) [CORRECTED 2026-10-18: was "direct post only if audit passes"]; Kick/others per ADR-0008; revisit AI-disclosure rules at the gate. |

### 6.2 Open questions for the owner

1. **Handle strategy vs Q-BRAND-6**: reserve handles now under the working name, or wait for clearance and risk losing them? (Recommendation: wait for a short shortlist, reserve on all four the same day.)
2. **Facebook Page**: connect one for Meta Business Suite scheduling, or stay on Instagram Login with no Page?
3. **YouTube production OAuth**: OK to put the Google Cloud app **In production** and complete Google's verification, rather than live with weekly re-consent?
4. **Audits**: willing to submit the YouTube API audit/quota form and the TikTok app review (demo video, privacy policy, domain), which need public privacy and terms pages (Q-LEGAL-6)?
5. **Scheduler purchase**: native tools only until P3, or buy a Buffer-class tool earlier (price `[UNVERIFIED]`)? Does the owner accept a third party holding publish tokens?
6. **Stage 2 rules**: which categories of auto-action, if any, are acceptable (hide exact-match spam only)?
7. **Mailbox watching**: may Brand Ops read a forwarded copy of platform policy emails, or does the owner forward them manually?
8. **AI-labeling default**: toggle AI labels **on** for any clip with TTS even when strictly not required (recommended)?
9. **Passkeys/hardware key**: does the owner have a hardware security key, and which devices hold the passkeys?
10. **TikTok scope**: keep TikTok as manual posting only through P4?
11. **Quota/price re-check cadence**: add a "social policy and quota re-check" step to each phase gate (alongside NX-288)?

### 6.3 Tracker/doc follow-ups (not done here, rule 11b)

This file is the only one changed. A coordinating session should apply: new tracker items for Brand Ops and `PublisherPort`; a new Q-MKT row set for the questions above; a correction note in PLATFORM-REALITY-CHECK §5 (YouTube `videos.insert` quota bucket) after a live check; a OPS-ADMIN §3 line for the review-queue extension.

---

## 7. Sources, access log and unreachable pages

**Date read for all sources: 2026-10-18.** Access method: **web-search result excerpts only** (WebSearch tool). I was not able to read any page's full text.

### 7.1 Pages unreachable

Direct fetches failed. WebFetch returned `getaddrinfo ENOTFOUND` for: `help.twitch.tv`, `developers.google.com`, `developers.tiktok.com`, `developers.facebook.com`. A `curl` through the agent proxy to `developers.google.com` returned HTTP 403 on CONNECT ("host not allowed for this session"). Every URL below should therefore be treated as **not read in full**.

Additionally not found even as excerpts: Twitch AI-disclosure policy text (none surfaced), Twitch passkey support, TikTok comment/analytics APIs for non-research developers, Instagram Live API, YouTube `liveBroadcasts.insert` quota cost, Instagram minimum age and Accounts Center requirements, TikTok business-account switch steps, TikTok Rate Limits page values for posting, Buffer/Later/Streamlabs official pricing and API-partner status, official Twitch Affiliate help-page text.

### 7.2 Source list

Official platform pages (seen only as search excerpts):
- S10 https://www.twitch.tv/p/en/legal/terms-of-service/
- S11 https://safety.twitch.tv/s/article/H1-2025-Transparency-Report
- S12 https://www.twitch.tv/p/en/legal/developer-agreement/ ; https://www.twitch.tv/p/en/legal/channel-points-acceptable-use-policy/
- S13 https://www.youtube.com/static?template=terms
- S14 https://www.tiktok.com/safety/en/policies-and-engagement/integrity-authenticity
- S15 https://www.tiktok.com/legal/page/us/terms-of-service/en ; https://www.tiktok.com/legal/page/global/tik-tok-developer-terms-of-service/en
- S16 https://help.instagram.com/581066165581870/
- S17 https://www.facebook.com/legal/automated_data_collection_terms
- S18 https://developers.facebook.com/devpolicy/
- S19 https://www.tiktok.com/safety/en/policies-and-engagement/accounts-features ; https://www.tiktok.com/creator-academy/article/Account-verification-101
- S20 https://www.tiktok.com/support/faq_detail?id=7543604790438451768&category=web_account
- S21 https://help.twitch.tv/s/article/streamer-benefits
- S22 https://support.google.com/youtube/answer/4642409 ; https://support.google.com/youtube/answer/9481328
- S23 (3P) https://www.soundstripe.com/blogs/tiktok-music-licensing-rules
- S24 https://help.instagram.com/138925576505882 ; https://www.facebook.com/business/help/345675946300334
- S25 https://developers.facebook.com/docs/instagram-platform/overview/ ; https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/
- S26 https://dev.twitch.tv/docs/authentication/register-app
- S27 https://affiliate.twitch.tv/ ; https://help.twitch.tv/s/article/affiliate-onboarding-guide
- S28 (3P) https://www.kaspersky.com/blog/full-guide-to-passkeys-in-2025-part-1/53688/ ; https://techcrunch.com/?p=2570601 ; https://www.digitaltrends.com/computing/this-website-publicly-shames-popular-sites-like-instagram-netflix-and-spotify-for-being-too-lazy-to-add-passkeys/
- S29 https://developers.tiktok.com/docs/en/app-review-guidelines ; https://developers.tiktok.com/docs/en/getting-started-faq
- S30 https://developers.facebook.com/docs/permissions ; https://developers.facebook.com/docs/instagram-platform/create-an-instagram-app/
- S31 https://blog.twitch.tv/en/2026/05/13/monetization-for-all/
- S32 https://help.twitch.tv/s/article/streamer-benefits
- S33 (3P, older figures) https://restream.io/blog/twitch-affiliate-program/
- S34 (3P) https://support.streamelements.com/hc/en-us/articles/23903165152914-How-to-Enable-Live-Streaming-on-YouTube ; https://support.restream.io/en/articles/8948773-enable-live-streaming-on-youtube
- S35 https://dev.twitch.tv/docs/api/clips/ ; https://dev.twitch.tv/docs/api/markers/ ; https://dev.twitch.tv/docs/api/guide ; https://dev.twitch.tv/docs/rss/change-log.xml
- S36 https://dev.twitch.tv/docs/api/clips/ (Get Clips Download via changelog)
- S37 (3P) https://techcrunch.com/2023/05/11/twitch-clip-editor-edit-vertical-video-tiktok-reels ; https://www.slashgear.com/1289125/how-to-edit-share-vertical-clips-twitch
- S38 https://dev.twitch.tv/docs/api/schedule/ ; https://dev.twitch.tv/docs/authentication/scopes/ ; https://dev.twitch.tv/docs/api/reference/
- S39 https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/ ; https://dev.twitch.tv/docs/eventsub/manage-subscriptions/ ; https://dev.twitch.tv/docs/eventsub/handling-websocket-events
- S40 https://developers.google.com/youtube/data/determine_quota_cost ; https://developers.google.com/youtube/v3/determine_quota_cost
- S41 https://developers.google.com/youtube/data/revision_history ; https://developers.google.com/youtube/v3/revision_history
- S42 https://developers.google.cn/youtube/v3/docs/videos ; https://developers.google.com/youtube/v3/docs/videos/insert
- S43 (3P, consistent) https://www.ayrshare.com/solutions/google-api-error-403-unverified-app-how-to-fix-the-audit-pipeline/
- S44 https://developers.google.com/youtube/data/guides/quota_and_compliance_audits ; https://support.google.com/youtube/contact/yt_api_form
- S45 https://developers.google.com/identity/protocols/oauth2 ; https://support.google.com/cloud/answer/15549945
- S46 https://support.google.com/youtube/answer/15424877 ; https://support.google.com/youtube/answer/12779649
- S47 (3P) https://issuetracker.google.com/issues/405004980 ; https://posteverywhere.ai/social-media-terms/youtube-community-posts
- S48 https://developers.google.com/youtube/analytics/reference/reports/query ; https://developers.google.com/youtube/reporting/v1/reference/rest
- S49 https://support.google.com/youtube/answer/2814000 ; https://developers.google.com/youtube/partner/terms ; https://support.google.com/youtube/answer/17011221
- S50 https://developers.tiktok.com/docs/en/content-posting-api-get-started
- S51 https://developers.tiktok.com/doc/content-posting-api-reference-direct-post ; https://developers.tiktok.com/docs/en/content-posting-api-reference-upload-video ; https://developers.tiktok.com/bulletin/migration-notice-share-video-api/
- S52 https://developers.tiktok.com/docs/en/content-sharing-guidelines ; https://developers.tiktok.com/docs/en/tiktok-api-v2-rate-limit
- S53 https://developers.tiktok.com/products/research-api/ ; https://developers.tiktok.com/docs/en/tiktok-api-scopes
- S54 https://www.tiktok.com/live/studio/help/article/Before-you-go-LIVE/Community-Guidelines ; https://seller-us.tiktok.com/university/essay?knowledge_id=4581457528243969
- S55 https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login ; https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/business-login
- S56 https://developers.facebook.com/docs/instagram-platform/content-publishing (3P cross-check: https://bundle.social/blog/instagram-api-rate-limits ; https://adaptlypost.com/blog/content-publishing-limit-instagram-api)
- S57 https://developers.facebook.com/docs/instagram-platform/insights/ ; https://developers.facebook.com/docs/graph-api/overview/rate-limiting/
- S58 https://developers.facebook.com/docs/instagram-api/webhooks ; https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/messaging-api
- S59 https://support.google.com/youtube/answer/3399767 ; https://support.google.com/youtube/answer/2801973
- S60 https://help.twitch.tv/s/article/how-to-handle-view-follow-bots ; https://safety.twitch.tv/s/article/Community-Guidelines
- S61 https://techcrunch.com/2026/04/30/instagram-restricts-reach-of-content-aggregators-in-new-crackdown/
- S62 (3P) https://www.digitalmusicnews.com/2026/05/01/instagram-debuts-more-original-content-protections-for-creators/
- S63 https://support.google.com/youtube/answer/1311392
- S64 https://support.google.com/youtube/answer/14328491 ; https://blog.youtube/news-and-events/disclosing-ai-generated-content/ ; https://blog.youtube/news-and-events/improving-ai-labels-viewers-creators/
- S65 https://www.tiktok.com/creator-academy/en/article/ai-generated-content-label ; https://seller-us.tiktok.com/university/essay?knowledge_id=491489038501663
- S66 https://transparency.meta.com/governance/tracking-impact/labeling-ai-content/ ; https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/
- S67 (3P) https://gamesbeat.com/twitch-ceo-dan-clancy-says-platform-doesnt-need-ai-disclosure-rules-for-now/
- S68 https://docs.discord.com/developers/interactions/receiving-and-responding ; https://discord.com/developers/docs/interactions/message-components
- S69 https://docs.ntfy.sh/publish/

Vendor/third-party sources for pricing and tools (all `[3P]`): https://buffer.com/resources/coding-kitty-case-study/ ; https://www.socialpilot.co/insights/metricool-pricing ; https://www.costbench.com/software/social-media-management/metricool/free-plan/ ; https://www.blotato.com/blog/later-pricing ; https://www.capterra.com/p/152254/Later/pricing ; https://www.castmagic.io/blog/opus-clip-pricing ; https://costbench.com/software/ai-video-editing-saas/opus-clip/ ; https://www.blotato.com/blog/youtube-api-pricing ; https://bundle.social/blog/youtube-api-quota-exceeded-limits-fixes .

Repo documents used: AGENTS.md, MARKETING.md, PLATFORM-REALITY-CHECK.md, SUPPORT-AND-SCRAPING-RESEARCH.md, CLIPS-REPLAY.md, OPS-ADMIN.md, CHAT-GATEWAY.md, ADMIN-RBAC.md, THREAT-MODEL.md (SEC-LLM-5), LLM-ADVISORS.md (LLM-2), OPEN-QUESTIONS.md (Q-MKT-1…4, Q-LEGAL-6/7/8, Q-ARCH-7, Q-ARCH-10, Q-OPS-4, Q-AI-6, Q-BRAND-6), ADR-0010.
