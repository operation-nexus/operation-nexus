# SPEC: Brand Ops (social presence monitoring and review)

Status: Draft · Owner: — · Tracker: NX-328 · Related ADRs: 0008, 0010 (a new isolation ADR is proposed in §9) · Related: [ADMIN-RBAC](ADMIN-RBAC.md), [OPS-ADMIN](OPS-ADMIN.md), [CHAT-GATEWAY](CHAT-GATEWAY.md), [CLIPS-REPLAY](CLIPS-REPLAY.md), [LLM-ADVISORS](LLM-ADVISORS.md), [DATA-MODEL](DATA-MODEL.md), [CONFIG-AND-CONTENT](CONFIG-AND-CONTENT.md), [THREAT-MODEL](../security/THREAT-MODEL.md), [SOCIAL-CHANNEL-AUTOMATION-RESEARCH](../review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md), [MARKETING-AND-PRODUCTION-RESEARCH](../review/MARKETING-AND-PRODUCTION-RESEARCH.md), [MARKETING](../planning/MARKETING.md)

> **Evidence rule (AGENTS.md rule 0).** Every platform capability, quota, scope name, policy or price in this spec is carried from the research doc, whose author read **no primary page** (research §0, §7). Source ids `[S..]` and the tags `[EXCERPT-OFFICIAL]`, `[3P]`, `[CONFLICT]` and `[UNVERIFIED]` are kept from there. Nothing here is re-verified. Every interface name, table, column, permission, route, config key and number below is **PROPOSED** unless it cites an owner decision. Re-read the live platform page before building on any claim (§5.12, BO-39).

## 1. Purpose

The project will have public presences on Twitch, YouTube, Instagram and TikTok. Somebody has to notice when a token expires, a quota runs out, a policy notice arrives, a post goes out private by mistake, or a hostile comment lands, and somebody has to approve what the project says in public. The owner is a solo developer who travels often (Q-MKT-4), so this must be cheap to run and must fail safe.

**Brand Ops** is a separate, mostly read-only service that:
1. watches the project's public presences and reports to the owner (signals, alerts, a daily and weekly digest);
2. holds a **review queue** where staff review and clear items; and
3. publishes **only what a human approved**, exactly as approved, through narrow adapters.

It is the answer to research §5 and to Q-MKT-4's "scheduled post queue so content keeps flowing while away". It does not run the game, read viewer chat, or set up accounts.

## 2. Goals / Non-goals

### 2.1 Owner decisions treated as requirements

These were given by the owner for this spec. They are binding here and are not re-argued; where a number or detail is missing it stays open in §8.

| # | Decision |
|---|---|
| D1 | **Twitch and YouTube at launch.** Instagram waits until P3. **TikTok stays manual through P4.** |
| D2 | **Native platform tools only until P3.** A scheduler is an optional P3 stopgap, only behind our own `PublisherPort`-style adapter. |
| D3 | **Stage 0: nothing public is posted without owner approval.** |
| D4 | **AI label on every post that contains text-to-speech, plus a "Synthetic voices" caption** (Q-AI-6). |
| D5 | **Passkeys everywhere the platform supports them.** One project mailbox. The Google OAuth app is put **In production** and verified (no 7-day Testing tokens). |
| D6 | **The review queue lives in the Command Center** (tailnet and Discord only, Q-ARCH-7, Q-RB-4) **and in Discord** (signed approve and reject buttons, owner-ID allowlist). Phone push (ntfy, Q-OPS-4) and an email digest are **only notifications** into it. |
| D7 | **Credentials via sops+age** in the private ops repo (Q-ARCH-10), with **separate read and publish credential sets**. |
| D8 | **Audit rows store the hash of the approved artifact.** |
| D9 | **Isolation.** Brand Ops is a separate process and container with its own Discord application and its own Twitch client id. It shares only adapter-interface patterns, a one-way sanitized event feed (sim and gateway to Brand Ops), the observability stack and the Discord library. It holds **no** stream keys, chat-bot tokens, sim DB access, admin write tokens or game LLM keys, and receives **no raw viewer chat**. |
| D10 | A public-facing **AI disclosure policy** (Q-AI-6). |
| D11 | **Brand-account setup is manual** (platforms bar automated account creation, research §1.1) and has a setup runbook. |

### 2.2 Goals
- One place to see, triage and clear everything that needs a human about the project's public presences.
- Nothing public happens that a human did not approve, and what is published is byte-for-byte what was approved.
- Early, loud warning for expiring tokens, exhausted quotas, silent private locks, policy notices and outages, without alert fatigue.
- A compromise of Brand Ops cannot touch the game, and a compromise of the game cannot publish (D9).
- Low owner effort: one-tap approval from a phone, a short daily digest.

### 2.3 Non-goals
- **Account creation or login automation.** Never (D11, research §1.1). Agents and Brand Ops use OAuth-granted API access only, never UI automation of a consumer account.
- Engagement automation: auto-follow, auto-like, DM blasts or auto-replies, view-botting, scrapers, mass-templated AI Shorts, reverse-engineered APIs (research §3, SEC-GW-3). None of these is ever a Stage.
- Reading or relaying viewer chat (CHAT-GATEWAY owns it) and chat replies or stream announcements (`ChatSink`).
- Stream metadata (title, category, schedule), stream keys, going live, restart watchdogs: OPS-ADMIN owns them.
- Rendering clips (CLIPS-REPLAY owns it) and deciding that a clip is good enough to exist (`mod.clip_review`).
- Unattended TikTok LIVE; YouTube community posts (no public API, research §2.2 `[3P]`, manual only).
- Any sim command. Brand Ops issues no `STAFF_*` or `SYS_*` command and cannot affect sim state, so ADMIN-RBAC RB-4 does not apply to it (its actions are still audited, BO-34).
- Paid advertising, third-party analytics or trackers (Q-MKT-3, Q-DM-3).
- A public site feature. The Command Center page is private.

### 2.4 Actors and roles

Staff means Command Center people (owner, admins, moderators). **Operator** means a player only and never appears here for staff (Q-ALN-40). The coalition is the Quorum and the enemy is the Static (GLOSSARY); social copy uses those names, and this spec's plain terms are for mechanics.

| Actor | What it is | Maps to (ADMIN-RBAC §4.1) |
|---|---|---|
| Owner | The one person who approves public output at Stage 0 | `OWNER` |
| Admin | Trusted co-runner | `ADMIN` |
| Moderator | May triage third-party text and pause Brand Ops | `MODERATOR` |
| Game Master, Content Editor, Viewer | No Brand Ops access at launch | `GAME_MASTER`, `CONTENT_EDITOR`, `VIEWER` |
| Brand Ops service | The container itself. A service principal, never an approver | `SVC_BRAND_OPS` (**PROPOSED**, zero Command Center permissions, same class as `SVC_ADVISOR`) |
| Agents (Claude Code, others) | Develop Brand Ops. Hold no Brand Ops credentials | `SVC_AGENT`, read-only drafts as today |
| Platforms | Twitch, YouTube, Instagram (from P3), TikTok (manual) | External, untrusted |
| Third parties | Commenters, mentioners, anyone who writes text we can read | External, **hostile** (BO-SEC-2..6) |

**Proposed permissions** (the full list and matrix additions are in §9, since this spec may not edit ADMIN-RBAC). Naming follows ADMIN-RBAC §4.2 (dotted lowercase `snake_case`):

| Permission | Effect | OWNER | ADMIN | MOD | Others |
|---|---|---|---|---|---|
| `brand.view` | Read queue, signals, status, digests, audit | yes | yes | yes | no |
| `brand.review` | Triage: mark seen, snooze, clear, flag; log a manual intake item. No public effect | yes | yes | non-publish kinds only | no |
| `brand.publish` | Approve, reject, revoke or cancel a publication, and approve a Stage 2 public write | yes | **no** at Stage 0 (owner decision D3) | no | no |
| `brand.pause` | Pause Brand Ops writes or all activity (BO-33) | yes | yes | yes | no |
| `brand.admin` | Connect and disconnect platform accounts, re-consent, resume from pause, alert and digest settings | yes | yes | no | no |
| `brand.stage_set` | Change the Brand Ops stage; enable Stage 2 rules (BO-16) | yes (two-person rule eligible) | no | no | no |

## 3. Requirements

Use of MUST, SHOULD and MAY follows RFC 2119. Each id is tested in §7.

### 3.1 Isolation and trust boundaries (D9)
| ID | Requirement |
|---|---|
| BO-1 | Brand Ops MUST run as its own process and container with its own datastore and volume, its own Discord application and bot token, and its own Twitch client id (so rate buckets and EventSub subscription limits are independent of the gateway's, research §5.3). It SHOULD use its own Google Cloud project so its OAuth consent, verification and YouTube quota are independent of the gateway's (quota is per project `[UNVERIFIED]` that a separate project is required; see Q-BO-4). |
| BO-2 | The Brand Ops container's environment, mounts and network MUST NOT contain: stream keys, chat-bot tokens or Twitch send scopes held by the gateway, any path to the sim database or snapshot volumes, any admin write token, any game LLM provider key, or platform account passwords, passkeys or 2FA seeds. |
| BO-3 | Brand Ops MUST learn about the game only through a **one-way, sanitized event feed** (§4.3) from sim and gateway to Brand Ops. The feed schema is a closed list; any unlisted event kind or unlisted field is dropped and counted. The feed MUST NOT carry raw chat, platform user ids, display names or free text from viewers. Brand Ops MUST NOT be able to publish anything into the feed or send a game command. |
| BO-4 | Media reaches Brand Ops only as an **approved clip bundle** (media file plus provenance manifest, §4.3) exported by the sim side to a **read-only mount**. Brand Ops cannot write to it and re-hashes the media on read. |
| BO-5 | Brand Ops MUST NOT expose an inbound listener to the internet. Discord and Twitch EventSub use outbound connections (gateway WebSocket, EventSub WebSocket). Its only inbound surface is the private API for the Command Center (BO-SEC-13). A webhook receiver (for example for Instagram mentions) is a separate minimal component that needs its own review (BO-SEC-8, Q-BO-5). Outbound traffic MUST be limited to an allowlist of the platform API hosts, Discord, ntfy and the mail relay (host list TBD, verified when each adapter is built). |
| BO-6 | Brand Ops MUST NOT import sim or gateway packages (import-linter contract). It reuses only the adapter-interface pattern and conformance-suite approach (ADR-0010 N-1, N-4), the observability client libraries and the Discord library. Vendor SDKs are imported only inside adapter packages (AGENTS.md rule 10a). |

### 3.2 Review queue
| ID | Requirement |
|---|---|
| BO-7 | The Brand Ops store is the **only** system of record for review items (D6). The Command Center page, Discord messages, ntfy pushes and the email digest are views and notifications; none holds independent state, and a decision made in any view is applied to the store and then re-rendered everywhere. |
| BO-8 | A review item MUST follow the lifecycle in §5.2 and carry `kind`, `platform`, `severity`, `state`, `created_at`, `evidence_hash` and, for publications, the artifact reference. Transitions not in §5.2 MUST be rejected. |
| BO-9 | Items MUST be deduplicated by `evidence_hash`. Alert volume MUST be bounded: batched milestone alerts, a per-hour cap with a digest fallback, and quiet hours (BO-28). |
| BO-10 | "Clear" MUST remove an item from the open list but never delete its row or its audit rows. |

### 3.3 Approval and stages
| ID | Requirement |
|---|---|
| BO-11 | **Stage 0 (default).** No public write (post, reply, hide, delete, pin, visibility flip by API) MAY be executed without a recorded approval by a staff member holding `brand.publish`. Brand Ops MAY read, summarize, draft, package and notify without approval. |
| BO-12 | An approval MUST bind to the **artifact hash** (§5.4): SHA-256 over the canonical manifest of media hash, final text, platform, target account, visibility, labels, tags and scheduled time. The publisher MUST recompute the hash from the exact payload it is about to send and abort on any mismatch (D8). |
| BO-13 | An approval MUST expire (`brand_ops.approval_ttl_h`, real time), be single-use, and carry an idempotency key (artifact hash, platform, account) so a retry or replayed button cannot publish twice. An edit of any approved field creates a new artifact and voids the earlier approval. |
| BO-14 | Only a human staff identity with `brand.publish` can approve. Service principals MUST NOT approve (ADMIN-RBAC RB-7, `SVC_BRAND_OPS` holds no approval right). A Discord approval is valid only from a user id on the owner allowlist (BO-SEC-7). Approval of a public publication SHOULD require step-up authentication in the Command Center (ADMIN-RBAC §5) and MUST record whether it happened. |
| BO-15 | Approval is two layers. (a) **Clip content approval** (`mod.clip_review`, SEC-CLIP-1, CLIPS-REPLAY §4) stays where it is; Brand Ops creates publication items only for clips already `APPROVED` there. (b) Each **platform variant** is a separate artifact with its own approval and hash. One UI action MAY approve all variants of one clip together, and each still writes its own approval row. |
| BO-16 | The stage (§5.3) MUST change only by `brand.stage_set`, only upward one stage at a time after the entry criteria are checked and shown, and every change MUST be audited. Moving down is always allowed to `brand.pause` holders for writes and to `brand.stage_set` for the stage itself. |
| BO-17 | **Stage 1.** A scheduled publication MUST use an artifact approved under BO-12, publishes at the approved time, and MUST give staff a cancel window before the time (`brand_ops.stage1.cancel_window_min`). |
| BO-18 | **Stage 2** auto-actions MUST be explicit per-rule allowlist entries enabled by `brand.stage_set`, each with a rate cap, a log entry, an undo path and the kill switch (BO-33). They MUST NOT include DMs, replies to criticism, anything about moderation disputes, politics or money, or free-form generated text. A rule that cannot be undone MUST NOT be offered. |

### 3.4 Packaging and disclosure
| ID | Requirement |
|---|---|
| BO-19 | Every publication artifact MUST carry **provenance** from the clip manifest: `sim_rendered`, `tts_used`, `owner_voice_used`, `simulated_actors`. Unknown or missing provenance MUST block approval (DATA-INTEGRITY: unknown is not false). If `tts_used`, the artifact MUST have the platform's AI or synthetic-content toggle **on** where the platform has one, **and** the caption line "Synthetic voices" (D4, Q-AI-6). |
| BO-20 | If `simulated_actors`, the artifact MUST be labelled as a simulated test in the caption and the clip itself MUST show it on screen for the whole clip (MARKETING: "SIMULATED TEST: scripted bot operators, no real players"; Q-MKT-3). Simulated footage is never implied to be real viewers. The viewer simulator never touches the public channel (Q-LEGAL-7). |
| BO-21 | Variants MUST be platform-specific, not byte-identical cross-posts: platform formatting, a title and first comment drafted from the same event but not copied, and no media carrying another platform's watermark (research §3, §4.1). Mass-templated output is blocked by a per-account and per-day volume cap (`brand_ops.publish.max_per_day.<platform>`). |
| BO-22 | `PublisherPort.capabilities()` MUST state `label_fields`, `can_draft`, `can_schedule`, `needs_audit` and `daily_cap` honestly (ADR-0010 N-3). If an adapter cannot set a required label by API, that artifact MUST NOT be auto-published as public; it falls back to a private upload or an export bundle with a checklist item for the owner. A missing capability means the feature is off, not faked. |
| BO-23 | Links in captions MAY carry a first-party source tag only (§5.4). No third-party trackers, pixels, cookies, shorteners or analytics scripts anywhere in the flow (Q-DM-3). |

### 3.5 Signals, alerts and digests
| ID | Requirement |
|---|---|
| BO-24 | Signal collectors MUST be read-only and record the source of each signal (`API`, `FEED`, `MANUAL`). Signals that no API provides (§5.1) MUST be taken in by **manual intake** by staff at launch; Brand Ops MUST NOT hold read access to the project mailbox. |
| BO-25 | After every publish attempt Brand Ops MUST **read back** the observed visibility and platform reference and compare with the intended. A mismatch (for example a silently private upload from an unverified YouTube project) MUST produce a `post_result` item "published private - audit required" and MUST NOT be reported as success. |
| BO-26 | Notifications go to ntfy, the staff Discord channel and email according to severity (§5.5). Push and email MUST NOT contain raw third-party text or secrets (BO-SEC-10); they carry counts, our own summaries and a deep link. |
| BO-27 | Brand Ops MUST produce a daily and a weekly digest (§5.5) at configured wall-clock times in an IANA zone (Q-CFG-6) and MUST state data lag where a source has one (Instagram insights up to 48 h, research §2.4 `[EXCERPT-OFFICIAL]` S57). |
| BO-28 | Quiet hours MUST suppress pushes except `severity >= critical` kinds (strike or claim notice, write attempt outside an approval, publisher credential revoked). |

### 3.6 Credentials, tokens and quotas (D5, D7)
| ID | Requirement |
|---|---|
| BO-29 | Credentials are two sets per platform: **READ** (read scopes only) and **PUBLISH** (write scopes). Two workers: the reader never holds a PUBLISH credential; the publisher executes only approved queue items and does not read the comment stream. A platform whose API cannot separate the scopes MUST be listed in the adapter's capabilities with the reason. |
| BO-30 | Brand Ops MUST track for each credential `issued_at`, `expires_at` (when the platform says), `last_ok_at` and granted scopes, probe health, and raise `token_expiring` items ahead of expiry (`brand_ops.token.expiry_warn_days`). The Google OAuth app MUST be **In production** with verification complete before any YouTube credential is relied on (D5); an adapter MUST refuse to start in a Google app state of Testing outside development, because refresh tokens then expire after 7 days (research §2.2, S45). |
| BO-31 | Brand Ops MUST keep local counters of quota-bearing calls per platform and bucket, compare with limits the platform reports where it reports them, alert at `brand_ops.quota.alert_pct` (PROPOSED 80, matching the OPS-ADMIN 80% pattern) and hold the queue when exhausted. Limits are read from config or a live probe, never hard-coded from this spec (§5.6 lists the research values and their conflicts). |
| BO-32 | Secrets MUST live in the private ops repo encrypted with sops+age to the Brand Ops host's own key (Q-ARCH-10). Runtime refresh tokens MUST be encrypted at rest. Revoking a platform token MUST never require changing a platform password (research §1.6). A revocation runbook MUST exist (§5.9). |

### 3.7 Control, audit and operations
| ID | Requirement |
|---|---|
| BO-33 | **Kill switch.** `brand.pause` holders can pause Brand Ops from the Command Center and from Discord (`/brandops pause`) in at most two taps or one command. Pause stops every write adapter immediately (tokens retained, scopes unused); `PAUSE_ALL` also stops collectors. The state is persistent, survives restarts, and is **fail-closed**: if the pause state cannot be read, nothing is written. Resume needs `brand.admin`. Activation of the game's kill switch (SEC-MOD-3), seen on the feed, MUST pause writes automatically. |
| BO-34 | Every staff decision, state change, publish attempt, stage change, credential event and pause MUST write one append-only `brand_audit` row: who, what, when, item id, before and after state, platform response id, and the artifact hash where one applies (D8). Audit rows cannot be edited or deleted by anyone (DM-3). Each staff decision MUST also be mirrored into the Command Center `admin_audit` (RB-3). |
| BO-35 | Platform accounts are created by the owner by hand (D11). Brand Ops refuses to connect an account until the owner has completed the connect flow in the Command Center (`brand.admin`) and the setup log entry exists (§5.9). |
| BO-36 | Staff access to Brand Ops goes through Command Center authentication (passkey for owner and admins, ADMIN-RBAC §5, D5) or Discord with the allowlist (BO-SEC-7). Platform logins (passwords, passkeys, 2FA seeds) live only in the owner's password manager and device keychains and never reach Brand Ops, an agent, `.env` or the repo (research §1.6). |
| BO-37 | Every timer in Brand Ops is **real time** (monotonic or wall-clock with an IANA zone, Q-CFG-6, CFG-9). Brand Ops does not interpret sim-time. Feed events carry a real `occurred_at` and optionally a display-only `campaign_time_label` marked as game time. A sim pause does not pause Brand Ops. |
| BO-38 | A third-party scheduler or clipper (Buffer or Metricool class, research §2.5 `[3P]`) MAY be used only as an adapter behind `PublisherPort` that passes the conformance suite, only from P3 (D2), only with the owner's explicit acceptance that a third party holds publish tokens (Q-BO-8), and never as an AI mass-clipper (research §3). |
| BO-39 | Platform AI-disclosure rules, policies, quotas and thresholds MUST be re-checked against the live primary pages at every phase gate, alongside NX-288, and any change recorded as a `policy_recheck` item. Adapters are behind feature flags so a changed policy can switch one off. |

### 3.8 Security (BO-SEC)
Hostile external text is the main new risk (comments, mentions, channel names, captions on third-party clips). These extend THREAT-MODEL; proposed additions are in §9.

| ID | Requirement |
|---|---|
| BO-SEC-1 | **Least privilege.** Request only the scopes the currently enabled feature needs (Twitch Developer Services Agreement, research §2.1 `[EXCERPT-OFFICIAL]` S12). READ credentials carry read scopes only. A scope is added in the same PR that adds the feature that needs it. |
| BO-SEC-2 | Every string from a platform (comment, mention, channel or video title, handle, forwarded notice) MUST be NFKC-normalized, stripped of control and bidi characters and length-capped on ingest (`brand_ops.text.max_len`, PROPOSED to match SEC-GW-1's 300), and stored as inert text. |
| BO-SEC-3 | Such text MUST be rendered as plain text only: `textContent` in the Command Center (SEC-OV-1 applies), and in Discord with `allowed_mentions` none, embeds and link unfurling suppressed, inside a code span or quote. Items the ModerationProvider flags are masked until a staff member reveals them. |
| BO-SEC-4 | Brand Ops MUST NOT fetch any URL, avatar, image or media found in third-party text, and MUST NOT auto-open links. Links are shown defanged. |
| BO-SEC-5 | No LLM is used in Brand Ops in this spec. If one is added later (for example reply drafting or comment summaries), it MUST go through the `LlmClient` RPC (no credentials in the Brand Ops container, LLM-2), receive opaque ids and never raw third-party text unless a reviewed rule allows it (new SEC-LLM-6, §9), return a typed schema range-checked by code, and be treated as a suggestion (AGENTS.md rule 5). It has no tools. It needs its own budget and key, outside the game's cap (Q-BO-11). |
| BO-SEC-6 | **Never act on instructions found in third-party text.** The only path from a signal to a write is: a typed action chosen by a human on an item (BO-11) or a Stage 2 rule matching an exact allowlisted pattern (BO-18). No free text from a signal flows into a write call, a command, a prompt or a log format string. |
| BO-SEC-7 | **Discord integrity.** Brand Ops uses its own Discord application, distinct from the public announcer; a leak of the public bot's token cannot forge approvals. Authorization is by user-id allowlist (the owner at Stage 0), never by channel membership or server role (ADMIN-RBAC RB-5). Each button `custom_id` carries `{item_id, action, artifact_hash_prefix, expiry, nonce}` plus an HMAC; the full hash is re-checked server-side; a button works once; stale or forged ids do nothing. Interactions are acknowledged within 3 s then edited (token valid 15 min, research §5.2 `[EXCERPT-OFFICIAL]` S68). Sensitive detail goes in ephemeral replies. |
| BO-SEC-8 | If a webhook receiver exists (Instagram `comments`, `mentions`, `live_comments`, research §2.4 S58), it MUST verify the platform signature, dedupe by id, write to the queue and do nothing else, in a separate minimal process, with its own security review and DAST before exposure (Q-BO-5). |
| BO-SEC-9 | A write attempt that does not correspond to an approved, unexpired approval row is an incident: block it, raise a critical alert and auto-pause writes. |
| BO-SEC-10 | Secrets, tokens, `custom_id` signing keys and approval hashes beyond the short prefix MUST never appear in logs (OPS-ADMIN redaction filter), Discord messages, ntfy, email or error pages. |
| BO-SEC-11 | The container MUST be hardened like the advisor (LLM-2): non-root, read-only root filesystem, CPU and memory limits, egress allowlist (BO-5). Images are signed with SBOM and provenance, lockfiles hash-pinned (SEC-CI-3, SEC-CI-4). |
| BO-SEC-12 | Third-party personal data (commenter handles, comment text) is kept only as needed for triage, with a retention limit (`brand_ops.retention.signal_days`, value TBD, Q-BO-12) and included in the privacy notice (NX-204, NX-314). Staff-visible handles are shown only with `brand.view`. |
| BO-SEC-13 | The Command Center calls Brand Ops over a private API with a service credential. Every decision request carries `{staff_id, permission, item_id, action, artifact_hash, request_id, step_up_ref, exp}` signed by the Command Center. Brand Ops verifies the signature, expiry and permission claim, and rejects replays by `request_id`. Brand Ops never trusts a bare network position. |

## 4. Interfaces

### 4.1 Architecture and trust boundaries

```
 Staff (owner mostly)                         Public platforms (untrusted)
  phone / laptop                       Twitch   YouTube   Instagram(P3+)   TikTok: manual
   |  tailnet only                       ^ READ creds   ^ PUBLISH creds (approved items only)
   v                                     |              |
+-----------------+  signed decisions  +----------------------------------------------+
| COMMAND CENTER  | -----------------> |  BRAND OPS  (own container, own DB, own app)  |
| RBAC, passkeys, | <---- items/status | +-------------+ +--------------+ +-----------+ |
| admin_audit     |   (CC pulls)       | | reader      | | publisher    | | queue,    | |
+-----------------+                    | | READ creds  | | PUBLISH cred | | alerts,   | |
                                       | | hostile text| | approved only| | digests,  | |
 Discord: Brand Ops' OWN app+token <-->| +-------------+ +--------------+ | audit     | |
  (buttons: owner-ID allowlist)        +----------^------------^----------+-----------+-+
 ntfy push, email digest <-------------notify only|            |read-only    one-way |
                                                   |            |clip bundle  feed    |
                     +-----------------------------+            |                     |
                     |  sanitized event feed (relay, pull)      |                     |
   sim / gateway ----+------------------------------------------+                     |
   (never receives anything from Brand Ops)                                           |
                                                                                      v
 NOT reachable from Brand Ops: sim DB, stream keys, chat-bot tokens, admin write      observability
 tokens, game LLM keys, raw viewer chat, platform passwords/passkeys                  (shared stack)
```

| Boundary | From to | Crosses | Controls |
|---|---|---|---|
| TB-1 | sim and gateway to Brand Ops | Sanitized facts, clip bundles | Closed schema, read-only mount, no return path (BO-3, BO-4) |
| TB-2 | Platforms to Brand Ops | Hostile text, metrics, notices | Sanitize on ingest, inert render, no fetch (BO-SEC-2..6) |
| TB-3 | Brand Ops to platforms | Approved publications only | Artifact hash, approval row, read-back (BO-11..13, BO-25) |
| TB-4 | Command Center to Brand Ops | Signed staff decisions | BO-SEC-13, RBAC on the Command Center side (RB-1) |
| TB-5 | Discord to Brand Ops | Button and slash interactions | Own app, allowlist, signed `custom_id` (BO-SEC-7) |
| TB-6 | Brand Ops to notification channels | Our own summaries | No raw third-party text, no secrets (BO-26, BO-SEC-10) |

The Command Center is more trusted than Brand Ops: it holds RBAC and the audit log; Brand Ops holds public-facing publish tokens. A compromise of the game, the gateway, the broadcast host or the Command Center's game powers does not hand over publish tokens, and a compromise of Brand Ops does not hand over the game (research §5.3).

### 4.2 Ports (all names PROPOSED, ADR-0010 patterns)

```python
class BrandPlatformAdapter(Protocol):          # read side, one per platform
    platform: BrandPlatform                     # TWITCH | YOUTUBE | INSTAGRAM | TIKTOK
    def capabilities(self) -> BrandCapabilities: ...   # signals it can read, scopes, quota model
    async def health(self) -> AdapterHealth: ...
    async def poll(self, since: Cursor) -> list[RawSignal]: ...   # READ credential only

class PublisherPort(Protocol):                  # write side; research §4.3 sketch
    def capabilities(self) -> PublisherCapabilities: ...
        # {max_len_s, aspect, label_fields, daily_cap, needs_audit, can_draft, can_schedule}
    async def submit(self, artifact: ApprovedArtifact, when: datetime | None) -> SubmissionHandle: ...
    async def status(self, handle: SubmissionHandle) -> PublishStatus: ...
        # queued | processing | private | published | rejected, plus platform_url
    async def readback(self, handle: SubmissionHandle) -> ObservedState: ...   # BO-25

class BrandNotifier(Protocol):                  # ntfy, Discord, email; reuses the AlertSink idea
    async def notify(self, n: Notification) -> None: ...
```

Adapters: `export-folder` (works today: writes the bundle and notifies the owner; no credentials), `youtube`, `instagram`, `tiktok-draft` (P5), `scheduler-<vendor>` (optional, P3). All pass a shared conformance suite (`tests/conformance/brand/`: capability honesty, idempotency, read-back, error mapping, quota accounting, no write without an approved artifact). `PublisherPort` replaces the `ClipPublisher` row of ADR-0010 and moves out of `nexus.clips.publishers.*` into Brand Ops (§9). Brand Ops lives in `services/brand-ops/`, Python package `nexus.brand_ops` (PROPOSED).

### 4.3 One-way feed and clip handoff (TB-1)

Transport is PROPOSED: Brand Ops pulls from a read-only feed relay that sim and gateway write to; it holds a read token and no write path (Q-BO-10). Events are validated against schemas generated from `contracts/` (AGENTS.md rule 6) and are vendor-free (ADR-0010 N-6).

| Feed event (PROPOSED, `PascalCase`) | Fields | Use |
|---|---|---|
| `StreamOnline`, `StreamOffline` | `occurred_at`, `platform` | Digest context; compare with public-side state |
| `CampaignMilestone` | `occurred_at`, `campaign_id`, `kind`, `campaign_time_label` (game time, display only) | Milestone items, post prompts |
| `ClipBundleReady` | `clip_id`, `bundle_ref`, `media_sha256`, `manifest_sha256`, `excitement_reason`, `approved_at` | Creates `clip_approval` items (BO-15) |
| `AdapterHealth` | `adapter`, `state`, `since` | Digest context |
| `KillSwitchChanged` | `active`, `occurred_at` | Auto-pause writes (BO-33) |
| `QuotaUsed` | `provider`, `bucket`, `used`, `limit` | Shared-project awareness only |

No callsigns, commander ids or chat text are in the baseline feed (Q-BO-9). The clip manifest holds the provenance fields of BO-19 plus the FoW-redaction state (RP-1: while a campaign runs only the redacted view is exportable).

### 4.4 Command Center and Discord surfaces

Routes follow ADMIN-RBAC §8 (kebab-case; each maps to exactly one permission). All are PROPOSED.

| Route | Effect | Permission |
|---|---|---|
| `GET /admin/brand/status` | Stage, pause state, adapter health, token and quota status | `brand.view` |
| `GET /admin/brand/items`, `GET /admin/brand/items/{id}` | Queue and detail | `brand.view` |
| `POST /admin/brand/items/{id}/triage` | seen, snooze, clear, flag | `brand.review` |
| `POST /admin/brand/items/manual` | Log a manual-intake item (policy notice, TikTok comment) | `brand.review` |
| `POST /admin/brand/artifacts/{id}/decide` | approve, reject, revoke, cancel scheduled | `brand.publish` |
| `POST /admin/brand/pause` | Pause writes or all | `brand.pause` |
| `POST /admin/brand/resume` | Resume | `brand.admin` |
| `POST /admin/brand/accounts/{platform}/connect`, `.../disconnect` | OAuth connect flow, revoke | `brand.admin` |
| `POST /admin/brand/stage` | Change stage | `brand.stage_set` |
| `GET /admin/brand/audit` | Read `brand_audit` | `brand.view` (export through `audit.export`) |

Discord (Brand Ops' own application; the web Command Center is canonical, ADMIN-RBAC §7.2 parity applies in spirit): `/brandops queue`, `/brandops pause`, `/brandops digest`, and message buttons Approve, Reject, Snooze, Open in Command Center. `/brandops resume`, stage changes, account connection and rule editing are web only.

### 4.5 Data model (PROPOSED, DATA-MODEL naming style)

Brand Ops has its **own** datastore (SQLite per ADR-0003 while one process writes), never the sim durable store. Ids are UUIDv7 `TEXT`, times are RFC 3339 UTC `TEXT`, enums are `UPPER_SNAKE` with `CHECK` lists generated from contracts, tables are plural `snake_case`, `STRICT`. A `NULL` means unknown or not applicable (DI-1). No secret values are stored, only references.

```sql
CREATE TABLE brand_accounts (                 -- the public presences
  account_id    TEXT PRIMARY KEY,
  platform      TEXT NOT NULL CHECK (platform IN ('TWITCH','YOUTUBE','INSTAGRAM','TIKTOK')),
  handle        TEXT NOT NULL,                -- as written in the setup log
  mode          TEXT NOT NULL CHECK (mode IN ('MANUAL','READ_ONLY','READ_PUBLISH')),
  enabled_from_phase TEXT,                    -- e.g. 'P3'; NULL if not scheduled
  setup_logged_at TEXT,                       -- owner confirmed the setup-log entry (BO-35)
  created_at    TEXT NOT NULL
) STRICT;

CREATE TABLE brand_credentials (              -- metadata only; secret_ref names a sops entry
  credential_id TEXT PRIMARY KEY,
  account_id    TEXT NOT NULL REFERENCES brand_accounts(account_id),
  set_kind      TEXT NOT NULL CHECK (set_kind IN ('READ','PUBLISH')),
  secret_ref    TEXT NOT NULL,
  scopes_json   TEXT NOT NULL,                -- granted scopes as the platform reported them
  oauth_app_state TEXT CHECK (oauth_app_state IN ('TESTING','PRODUCTION')),  -- Google only
  issued_at     TEXT, expires_at TEXT, last_ok_at TEXT, revoked_at TEXT
) STRICT;

CREATE TABLE brand_signals (                  -- everything read from outside
  signal_id     TEXT PRIMARY KEY,
  account_id    TEXT REFERENCES brand_accounts(account_id),
  kind          TEXT NOT NULL,                -- BrandSignalKind (generated CHECK)
  source        TEXT NOT NULL CHECK (source IN ('API','FEED','MANUAL')),
  external_id   TEXT,
  dedupe_hash   TEXT NOT NULL,
  observed_at   TEXT NOT NULL,
  text_sanitized TEXT,                        -- BO-SEC-2; NULL when the signal has no text
  metrics_json  TEXT,                         -- counts, never user content
  flagged       INTEGER NOT NULL DEFAULT 0 CHECK (flagged IN (0,1))
) STRICT;
CREATE UNIQUE INDEX idx_brand_signals_dedupe ON brand_signals(account_id, dedupe_hash);

CREATE TABLE brand_artifacts (                -- one platform variant of one thing to publish
  artifact_id   TEXT PRIMARY KEY,
  clip_id       TEXT NOT NULL,                -- opaque id from the feed, not a sim FK
  account_id    TEXT NOT NULL REFERENCES brand_accounts(account_id),
  variant_json  TEXT NOT NULL,                -- title, caption, tags, first comment, visibility, scheduled_for + tz
  labels_json   TEXT NOT NULL,                -- ai_toggle, synthetic_voices_caption, simulated_test
  provenance_json TEXT NOT NULL,              -- BO-19
  media_sha256  TEXT NOT NULL,
  artifact_hash TEXT NOT NULL,                -- BO-12
  state         TEXT NOT NULL CHECK (state IN ('DRAFT','PENDING_REVIEW','APPROVED','SCHEDULED','PUBLISHING',
                  'PUBLISHED_PRIVATE','PUBLISHED_PUBLIC','FAILED','CANCELLED','EXPIRED','SUPERSEDED')),
  supersedes_artifact_id TEXT REFERENCES brand_artifacts(artifact_id),
  created_at    TEXT NOT NULL
) STRICT;

CREATE TABLE brand_review_items (             -- the queue (BO-7)
  item_id       TEXT PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('CLIP_APPROVAL','POST_RESULT','COMMENT_FLAG','MENTION','MILESTONE',
                  'ANOMALY','TOKEN_EXPIRING','QUOTA_LOW','POLICY_NOTICE','PLATFORM_OUTAGE','POLICY_RECHECK')),
  platform      TEXT CHECK (platform IN ('TWITCH','YOUTUBE','INSTAGRAM','TIKTOK')),
  severity      TEXT NOT NULL CHECK (severity IN ('INFO','NORMAL','HIGH','CRITICAL')),
  state         TEXT NOT NULL CHECK (state IN ('NEW','SEEN','APPROVED','REJECTED','SNOOZED','CLEARED')),
  summary       TEXT NOT NULL,                -- our own generated text, never third-party text
  signal_id     TEXT REFERENCES brand_signals(signal_id),
  artifact_id   TEXT REFERENCES brand_artifacts(artifact_id),
  evidence_hash TEXT NOT NULL,                -- BO-9
  created_at    TEXT NOT NULL, due_at TEXT, snoozed_until TEXT, decided_at TEXT
) STRICT;
CREATE INDEX idx_brand_items_open ON brand_review_items(state, severity, created_at);

CREATE TABLE brand_approvals (
  approval_id   TEXT PRIMARY KEY,
  item_id       TEXT NOT NULL REFERENCES brand_review_items(item_id),
  artifact_id   TEXT NOT NULL REFERENCES brand_artifacts(artifact_id),
  artifact_hash TEXT NOT NULL,
  decision      TEXT NOT NULL CHECK (decision IN ('APPROVED','REJECTED','REVOKED')),
  staff_id      TEXT NOT NULL,                -- Command Center staff id (no FK: other store)
  channel       TEXT NOT NULL CHECK (channel IN ('WEB_CONSOLE','DISCORD')),
  discord_user_id TEXT,                       -- set iff channel = DISCORD
  step_up       INTEGER NOT NULL CHECK (step_up IN (0,1)),
  stage         TEXT NOT NULL CHECK (stage IN ('STAGE_0','STAGE_1','STAGE_2')),
  decided_at    TEXT NOT NULL, expires_at TEXT NOT NULL, consumed_at TEXT
) STRICT;

CREATE TABLE brand_publish_attempts (
  attempt_id    TEXT PRIMARY KEY,
  approval_id   TEXT NOT NULL REFERENCES brand_approvals(approval_id),
  artifact_id   TEXT NOT NULL REFERENCES brand_artifacts(artifact_id),
  idempotency_key TEXT NOT NULL UNIQUE,       -- BO-13
  adapter       TEXT NOT NULL,
  intended_visibility TEXT NOT NULL, observed_visibility TEXT,   -- BO-25
  platform_ref  TEXT, error_class TEXT, quota_cost_units INTEGER,
  attempted_at  TEXT NOT NULL, completed_at TEXT
) STRICT;

CREATE TABLE brand_alerts (
  alert_id      TEXT PRIMARY KEY,
  item_id       TEXT REFERENCES brand_review_items(item_id),
  channel       TEXT NOT NULL CHECK (channel IN ('NTFY','DISCORD','EMAIL','COMMAND_CENTER')),
  priority      INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
  dedupe_key    TEXT NOT NULL, sent_at TEXT NOT NULL, acked_at TEXT
) STRICT;

CREATE TABLE brand_quota_counters (
  platform TEXT NOT NULL, bucket TEXT NOT NULL, window_start TEXT NOT NULL,
  used INTEGER NOT NULL, limit_observed INTEGER,   -- NULL = platform did not report one
  source TEXT NOT NULL CHECK (source IN ('LOCAL','PLATFORM_REPORTED')),
  PRIMARY KEY (platform, bucket, window_start)
) STRICT;

CREATE TABLE brand_state (                    -- singleton: stage and pause (BO-16, BO-33)
  id INTEGER PRIMARY KEY CHECK (id = 1),
  stage TEXT NOT NULL CHECK (stage IN ('STAGE_0','STAGE_1','STAGE_2')),
  pause_mode TEXT NOT NULL CHECK (pause_mode IN ('NONE','PAUSE_WRITES','PAUSE_ALL')),
  pause_reason TEXT, changed_by TEXT, changed_at TEXT NOT NULL
) STRICT;

CREATE TABLE brand_rules (                    -- Stage 2 allowlist (BO-18); empty until enabled
  rule_id TEXT PRIMARY KEY, kind TEXT NOT NULL, params_json TEXT NOT NULL,
  rate_cap_per_hour INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
  undo_supported INTEGER NOT NULL CHECK (undo_supported = 1),
  enabled_by TEXT, enabled_at TEXT
) STRICT;

CREATE TABLE brand_audit (                    -- append-only (DM-3): triggers block UPDATE and DELETE
  audit_id      TEXT PRIMARY KEY,
  actor         TEXT NOT NULL,                -- staff_id, or 'BRAND_OPS' for automatic rows
  action        TEXT NOT NULL,                -- BrandAuditAction (generated)
  item_id       TEXT, artifact_id TEXT,
  artifact_hash TEXT,                         -- D8
  before_state  TEXT, after_state TEXT,
  platform_ref  TEXT, detail_json TEXT,
  occurred_at   TEXT NOT NULL
) STRICT;
```

Signal kinds (`BrandSignalKind`): `STREAM_STATE`, `FOLLOWER_DELTA`, `MILESTONE`, `VIDEO_METRICS`, `COMMENT`, `MENTION`, `DM_NOTIFY`, `POLICY_NOTICE`, `ANOMALY`, `HELD_MODERATION`, `ADAPTER_HEALTH`.

### 4.6 Config keys (all PROPOSED, TBD unless stated)

A separate runtime file for the Brand Ops service (for example `deploy/<env>/brand-ops.yaml`) plus env overrides, never in a balance profile or its hash (CONFIG-AND-CONTENT §4.1). Keys use the prefix `brand_ops.` so they do not collide with the `brand.*` permissions (NAMING-CONVENTIONS §3 item 13). Every time key names its clock (CFG-9); all are real time or wall-clock-with-zone.

| Key | Type | Unit and clock | Value |
|---|---|---|---|
| `brand_ops.enabled` | bool | | `false` until P2 |
| `brand_ops.stage` | enum `stage_0`/`stage_1`/`stage_2` | | `stage_0` (D3); changed only through `brand.stage_set` |
| `brand_ops.platforms.<platform>.enabled` | bool | | twitch, youtube per D1; instagram `false` before P3; tiktok `false` through P4 |
| `brand_ops.platforms.<platform>.mode` | enum `manual`/`read_only`/`read_publish` | | TBD per phase (§5.11) |
| `brand_ops.poll.<platform>.every_s` | float | s (real) | TBD, derived from quota in §5.6 |
| `brand_ops.approval_ttl_h` | float | h (real) | TBD (owner) |
| `brand_ops.stage1.cancel_window_min` | float | min (real) | TBD (owner) |
| `brand_ops.publish.max_per_day.<platform>` | int | per day (wall-clock in `brand_ops.digest.tz`) | TBD; must sit under the platform's reported cap |
| `brand_ops.token.expiry_warn_days` | float | days (real) | TBD |
| `brand_ops.quota.alert_pct` | float | % | 80 (matches OPS-ADMIN LLM/TTS pattern) |
| `brand_ops.alerts.max_per_hour` | int | per h (real) | TBD |
| `brand_ops.alerts.quiet_hours` | `{start: time, end: time, tz: IANA zone}` | wall-clock in `tz` | TBD (owner travels, Q-MKT-4) |
| `brand_ops.digest.daily` / `brand_ops.digest.weekly` | `{weekday?, time, tz}` | wall-clock in `tz` | TBD |
| `brand_ops.text.max_len` | int | chars | 300 (matches SEC-GW-1) |
| `brand_ops.feed.stale_after_s` | float | s (real) | TBD; feed older than this is shown as stale, not as "all quiet" |
| `brand_ops.retention.signal_days` | float | days (real) | TBD (Q-BO-12) |
| `brand_ops.discord.owner_user_ids` | `secret_ref` | | allowlist kept in the ops repo, not in the public repo |
| `brand_ops.scheduler.adapter` | enum `none`/`<vendor>` | | `none` (D2) |

Not configurable: the AI label rule for TTS (BO-19), the Stage 0 default (BO-11) and fail-closed pause (BO-33). Config can only make them stricter.

## 5. Behavior

### 5.1 Signals, by platform, and how they are read

Legend: API = readable by an official API with the read credential; EMAIL = reaches us only by notice email or Studio, so manual intake at launch (BO-24); FEED = from the sanitized feed; N/A = no source. All rows carry the research tags.

| Signal | Twitch | YouTube | Instagram (P3+) | TikTok (manual) |
|---|---|---|---|---|
| Stream online and health | API: EventSub `stream.online`/`offline` plus Get Streams (S39) | API: Live Streaming API broadcast status; stream-health field names `[UNVERIFIED]` | N/A | N/A |
| Follower, sub and milestone counts | API: `channel.follow` v2 (`moderator:read:followers`), `channel.subscribe` (`channel:read:subscriptions`) (S39) | API: channel statistics, subscriber counts may be rounded `[UNVERIFIED]` | API: profile and user insights | Display API profile stats `[UNVERIFIED]`; otherwise manual |
| Clip, video and post performance | API: Get Clips, Get Videos | API: Analytics API and Reporting API; scope names conflict between pages `[CONFLICT]` (S48) | API: media insights `views`, `reach`, up to 48 h lag (S57) | Display API video list `[UNVERIFIED]`; otherwise manual in TikTok Studio |
| Comments and mentions | N/A (chat belongs to the gateway; Brand Ops does not read it) | API: `commentThreads.list`, 1 unit (S40) | API: webhooks for `comments`, `mentions`, `live_comments` (S58). Polling for mentions `[UNVERIFIED]`, so a receiver may be needed (Q-BO-5) | **Not by API.** Manual in TikTok Studio |
| DMs | N/A | N/A | API: Messaging API, 24 h window. **Notify only, never auto-reply** (S58) | N/A |
| Held moderation queue | API: held AutoMod messages `[UNVERIFIED]` | API: comments held for review (`setModerationStatus`, 50 units) | API: comment hide and delete details `[UNVERIFIED]` | Manual |
| **Policy strikes and copyright claims** | **EMAIL and dashboard only** `[UNVERIFIED]` as an API | **EMAIL and Studio only**; Content ID API is partner-only (S49) | **EMAIL and in-app Account Status**; API `[UNVERIFIED]` | In-app and email notices `[UNVERIFIED]` |
| Own-pipeline health | FEED and observability stack | same | same | same |
| Anomalies | Derived by Brand Ops from the above (baseline and threshold TBD) | derived | derived | manual |

Gaps that stay manual (policy and strike notices, TikTok comments and analytics, YouTube community posts, appeals) reach the owner by the project mailbox. At launch the owner enters them through manual intake (`POST /admin/brand/items/manual`), which creates a `POLICY_NOTICE` item typed by staff. An automated forward is not specified here: giving Brand Ops mailbox scope is excluded (BO-24), and a forward filter into a Discord or ntfy bridge still needs a decision on the receiving path and its attack surface (Q-BO-3).

### 5.2 Review item lifecycle

States: `NEW`, `SEEN`, `APPROVED`, `REJECTED`, `SNOOZED`, `CLEARED` (research §5.2).

| From | To | Who | Notes |
|---|---|---|---|
| (created) | `NEW` | Brand Ops | Deduped by `evidence_hash` (BO-9) |
| `NEW` | `SEEN` | `brand.view` opening it | |
| `NEW`, `SEEN` | `SNOOZED` | `brand.review` | Returns to `NEW` at `snoozed_until` |
| `NEW`, `SEEN`, `SNOOZED` | `CLEARED` | `brand.review` | Informational kinds (`MILESTONE`, `ANOMALY`, `QUOTA_LOW`, `POST_RESULT` that succeeded). Row and audit kept (BO-10) |
| `NEW`, `SEEN` | `APPROVED` / `REJECTED` | `brand.publish`, kinds with an artifact only | Creates a `brand_approvals` row (BO-12) |
| `APPROVED` | `CLEARED` | Brand Ops | After the publish attempt is read back (BO-25) |

An item that needs action never auto-clears. A `CRITICAL` item is re-alerted until acknowledged (interval TBD).

The artifact has its own lifecycle: `DRAFT` (packaged, provenance checked) → `PENDING_REVIEW` → `APPROVED` → (`SCHEDULED` at Stage 1) → `PUBLISHING` → `PUBLISHED_PRIVATE` or `PUBLISHED_PUBLIC`, with `FAILED`, `CANCELLED`, `EXPIRED` (approval TTL passed) and `SUPERSEDED` (edited, BO-13) as terminal states. `PUBLISHED_PRIVATE` when public was intended is a failure to report, not a success (BO-25).

### 5.3 Approval workflow and stages

**Stage 0 (default through the whole pre-P4 period, D3).**
1. A `ClipBundleReady` feed event arrives for a clip already approved under `mod.clip_review` (BO-15a).
2. Brand Ops re-hashes the bundle, checks provenance (BO-19), and builds one `DRAFT` artifact per enabled platform (§5.4).
3. It creates a `CLIP_APPROVAL` item and notifies (§5.5). The staff view shows preview, excitement reason, final text, labels pre-filled from provenance, visibility, and the artifact hash prefix.
4. The owner approves or rejects each variant. Approval is recorded with the channel and step-up status (BO-14).
5. The publisher recomputes the hash, checks pause state and quota, submits through the platform's `PublisherPort` adapter, then reads back the result (BO-25).
6. Result is an item and a digest line. Anything other than the intended visibility is reported as failed.

Before P3 the only adapter is `export-folder` (D2): it writes the approved bundle and a checklist for the owner to post by hand with the native tool, and notifies. Pre-P3 Brand Ops therefore never holds a PUBLISH credential.

**Stage 1: scheduled after approval.** Same approval, plus a time. The owner approves once; the publisher fires at the approved time (a human decision, only the clock is automated). A cancel window before the time lets any `brand.publish` holder cancel. Entry criteria (all must be shown green before `brand.stage_set` is accepted; numbers are for the owner, Q-BO-7):
- Stage 0 has run for at least N approved publications on each enabled platform with zero hash mismatches, zero duplicate posts and zero unreported silent-private results (N TBD);
- the kill switch drill and the credential-revocation drill have been run once on purpose (§5.9);
- the read-back verifier has caught a seeded wrong-visibility case in a test;
- the daily digest has run for a period with no missed days (TBD);
- policy and quota facts for each enabled platform were re-read against the live pages in the last phase gate (BO-39).

**Stage 2: low-risk auto-actions, opt-in per rule.** Examples proposed by the research and still for the owner to approve one by one (Q-BO-7): hide a comment that exactly matches a spam rule; send a thank-you from a fixed template set to a milestone event; pin the weekly schedule. Each rule: allowlisted and enabled by `brand.stage_set`; exact-match conditions only; a per-hour rate cap; a log row with undo; stops under pause. Never: DMs, replies to criticism, moderation disputes, politics or money, free-form generated text, anything on TikTok (TikTok's terms bar generative-AI features via automated systems unless authorized, research §3, S15). Entry criteria: Stage 1 stable for a period (TBD), the rule list reviewed by the owner, the undo path demonstrated, and the kill switch tested again.

Moving back down is always allowed (BO-16). The pause is separate from the stage (BO-33).

### 5.4 Content packaging

Per artifact (BO-12 hash covers all of it):

| Element | Rule |
|---|---|
| Media | Our own sim-rendered footage at 9:16 1080x1920, FoW-redacted while a campaign runs (CLIPS-REPLAY §3, RP-1). Source and provenance from the manifest. Burned-in captions per MARKETING (owner voice or captions only) |
| Per-platform formatting | Values are format guidance and `[UNVERIFIED]` against current specs except where cited: YouTube Shorts vertical or square up to 3 min since 2025-12-08 (S46); Instagram Reels and TikTok limits not confirmed (research §4.1). The adapter's `capabilities()` supplies the limits at run time; Brand Ops does not hard-code them |
| Text | Title, caption, hashtags and first comment drafted per platform from the event, not copy-pasted. At launch drafts come from templates and the clip's own facts, not an LLM (BO-SEC-5) |
| AI disclosure (D4, D10) | `tts_used` → platform AI or synthetic-content toggle on where it exists (YouTube "altered or synthetic content" setting in Studio, TikTok "AI-generated content" toggle, Instagram disclosure tool; research §4.2, S64..S66 `[EXCERPT-OFFICIAL]`) **and** the caption line "Synthetic voices". Twitch has no post toggle; its disclosure is the channel panel note (Q-AI-6). Whether each API can set the toggle is `[UNVERIFIED]`: if not, BO-22 applies |
| Simulated actors | Caption and on-screen "SIMULATED TEST" (BO-20) |
| Music | Credits per the provenance register and platform requirement (MARKETING research §4.8) |
| Link tagging (BO-23) | A first-party source tag (for example `?src=<short opaque code>`) MAY be added to links to our own site or link portal. It is read only by our own first-party code at link time, never persisted in a cookie, and the destination loads no third-party scripts (Q-DM-3). No shortener or redirect service. Whether to use `utm_*` names or our own is open (Q-BO-6) |
| Volume | Capped per account and day (BO-21); no mass-templated series (research §3, S63) |

Artifact hash: SHA-256 over the canonical JSON of `{media_sha256, platform, account_id, visibility, scheduled_for with tz, title, caption, tags, first_comment, labels, link}`. The publisher recomputes it from the payload bytes and the resolved fields immediately before the call.

### 5.5 Alerting, digests and notification routing

One source of truth, three notification channels and the Command Center page (BO-7).

| Severity | Examples | ntfy priority (PROPOSED) | Discord staff channel | Email |
|---|---|---|---|---|
| `CRITICAL` | Strike or claim notice entered, write outside approval (BO-SEC-9), PUBLISH credential revoked | 5 | message with buttons | digest and immediate |
| `HIGH` | Approval waiting, `token_expiring`, quota over `alert_pct`, silent private lock, platform outage | 3 to 4 | message with buttons | digest |
| `NORMAL` | Result of a post, comment flag | 2 to 3 | quiet message | digest |
| `INFO` | Milestone, follower deltas | 1 | none or batched | digest only |

Stream-offline paging stays with OPS-ADMIN (OA-5, OA-6); Brand Ops only reports it in context to avoid two pagers for one fault. ntfy supports priority 1 to 5 and up to three action buttons (research §5.2, S69). Noise control: dedupe by `evidence_hash`, batched milestones, `brand_ops.alerts.max_per_hour` with a digest fallback, quiet hours (BO-28).

**Daily digest** (email, and a Discord summary): open items by kind and age; yesterday's publications with intended versus observed visibility; scheduled publications for the next day; token days remaining and quota use per platform; adapter and feed health; anomalies. **Weekly digest** adds: per-platform analytics (YouTube Analytics, Instagram insights with the lag stated, Twitch counts), clip approval rate, policy re-check status, and the open-items backlog. Digests and pushes carry counts, our own summaries and deep links only (BO-26).

### 5.6 Quota and token management

Values are the research's best reported figures of 2026-10-18, not facts. Counters and live probes drive behavior (BO-31); the table is for planning.

| Platform | Reported limits and lifetimes | Handling |
|---|---|---|
| YouTube | Default 10,000 units/day for most endpoints, plus separate buckets of 100 `videos.insert` and 100 `search.list` calls/day (revision entry 2026-06-01); a Dec 2025 entry cut upload cost from about 1,600 to about 100 units `[EXCERPT-OFFICIAL]` S40, S41, conflicting with older guides and with PLATFORM-REALITY-CHECK §5 `[CONFLICT]`. Costs: `commentThreads.list` 1, `setModerationStatus` 50, `comments.insert` 50, `thumbnails.set` 50 (S40). Invalid requests cost at least 1. **Uploads from unverified API projects created after 2020-07-28 are silently locked private** until a compliance audit passes (S42, S43); audit and quota extension go through the YouTube API Services Audit and Quota Extension Form, no processing time published (S44) | Local counters per bucket; poll comments at a rate that fits the budget (a few hundred per day fits, research §2.2); BO-25 read-back detects the private lock; start the audit process early in P3 (research §6.1) |
| YouTube OAuth | An app in **Testing** gets refresh tokens that **expire in 7 days** and caps test users at 100; **In production** removes this and sensitive or restricted scopes need Google verification (S45). Whether `youtube.upload` is sensitive or restricted is `[UNVERIFIED]` | D5: production plus verification before relying on it; BO-30 refuses a Testing app outside development. Verification and audits need public privacy and terms pages (Q-LEGAL-6) (Q-BO-13) |
| Twitch | Token bucket per client id per user per minute, point cost per endpoint, 429 when empty; read the `Ratelimit-*` headers (S35). EventSub WebSocket needs a user token; up to 3 connections and 300 subscriptions each; `max_total_cost` docs inconsistent `[CONFLICT]` (S39). User tokens refresh and can be revoked in connections settings `[UNVERIFIED path]` | Adapter honors headers; own client id (BO-1); refresh handled by the adapter |
| Instagram | Publishing cap reported as 100 posts per rolling 24 h by Meta's guide, with a third party citing 50 `[CONFLICT]`; check live with the `content_publishing_limit` endpoint (S56). Business Use Case call budget is 4,800 x account impressions in 24 h, so a tiny new account has a tiny budget (S57). Long-lived token refresh details `[UNVERIFIED]` | Query the limit endpoint, do not assume; budget polls accordingly |
| TikTok | Manual through P4 (D1). From P5: Direct Post private-only for unaudited clients, up to 5 users per 24 h; inbox drafts capped at 5 pending shares per 24 h; about 15 posts per day per creator shared across clients (S50..S52). Token lifetimes `[UNVERIFIED]` | Not built before P5 (ADR-0008) |

Token lifecycle: tracked in `brand_credentials`; health probe per credential; `token_expiring` item ahead of expiry; on 401 the adapter stops, raises a `HIGH` item with a one-tap re-consent link (an owner-performed flow), and the other platforms continue. A revoked or expired PUBLISH credential never silently falls back to the READ credential.

### 5.7 Kill switch and pause

| Mode | Stops | Keeps |
|---|---|---|
| `PAUSE_WRITES` | Every write adapter: publish, reply, hide, pin, scheduled fires. Approvals still recordable but do not execute until resume | Collectors, queue, alerts, digests |
| `PAUSE_ALL` | Writes and collectors | Queue and audit; alerts about the pause itself |

Entry: Command Center (`brand.pause`), `/brandops pause`, automatic on a game `KillSwitchChanged(active)` (BO-33), automatic on BO-SEC-9. Pause persists across restarts and is fail-closed. Pause raises a `HIGH` alert to the owner naming who and why. Resume needs `brand.admin`; resuming does not execute anything that expired meanwhile (approvals past their TTL become `EXPIRED`). Pause is independent of the campaign pause (OPS-ADMIN §1): a campaign pause does not stop Brand Ops, and Brand Ops pause does not touch the sim.

### 5.8 Audit logging

`brand_audit` rows (BO-34) are written in the same transaction as the state change they describe. The published-artifact row stores the **hash of the approved artifact** and the platform's response id, so a swapped file cannot be mistaken for the approved one (D8, research §5.6). A daily job verifies that every `PUBLISHED_*` artifact has exactly one approval, one attempt and one audit row with matching hashes, and raises `CRITICAL` if not. Retention follows the DATA-MODEL retention approach (period TBD). Export through `audit.export`.

### 5.9 Brand-account setup runbook (manual, D11)

Accounts are created by the owner in a normal browser or app session (research §1.1, §1.5). The runbook is written into `deploy/runbooks/` as a template with **no identifiers**; the real run, setup log and recovery locations live in the private ops repo. Required content:
1. Project mailbox with the strongest MFA; recovery codes offline; a shared public contact alias; no personal address on any account (Q-LEGAL-6).
2. One password-manager entry per platform; **passkeys** where supported (Google yes; Instagram reported only through a linked Facebook login `[3P]`; Twitch and TikTok per research `[UNVERIFIED]`), TOTP fallback, a second device or hardware key to avoid lockout, recovery tested once.
3. Google first: the YouTube channel as a **Brand Account** channel, phone verification started early (about 24 h wait before first live stream, `[3P]` S34), Google Cloud project, OAuth consent screen moved to **In production** and verified (D5).
4. Twitch: 2FA on (needed for the developer app, S26); channel panel with the "Synthetic voices" note (Q-AI-6).
5. Instagram (P3): switch to a Professional account; prefer **Instagram Login** (no Facebook Page) unless Meta Business Suite scheduling is wanted (S25; Q-BO-2).
6. TikTok: account with the project mailbox, manual through P4 (D1); no developer app until P5.
7. Developer registrations when a feature needs them, not all at once.
8. Setup log: platform, handle, date, mailbox, 2FA methods, recovery location (location only), developer app dates.
9. Sealed offline recovery envelope mirroring the Command Center break-glass model (ADMIN-RBAC §5).
10. **Revocation and rotation page**: revoke per platform, delete the sops entry, re-consent, confirm the health check is green (Q-ARCH-10). Handle strategy follows the brand-name decision (Q-BRAND-6, Q-MKT-3, Q-BO-1).

### 5.10 Worked example

A clip passes `mod.clip_review`. The feed delivers `ClipBundleReady` (TTS used, no simulated actors). Brand Ops builds a YouTube Shorts artifact and, at P3, an Instagram Reels artifact; each shows "Synthetic voices", the AI toggle set, a per-platform title, and a `?src=` tag. A Discord message with Approve and Reject appears in the staff channel and an ntfy push (priority 3) reaches the owner's phone. The owner taps Approve on the YouTube artifact: the allowlist check passes, the signed `custom_id` verifies, an approval row is written with the full hash and `step_up = 0`, and the item moves to `APPROVED`. The publisher recomputes the hash, finds quota available, uploads through the `youtube` adapter, and reads back `private` because the Google project is not yet audited. Brand Ops raises "published private - audit required" and the next digest lists it; the owner flips it public in Studio, a step outside Brand Ops that the read-back later confirms. A hostile comment arrives on the video: it is sanitized, stored inert, flagged, and shown masked in the queue; no code path from it reaches a write.

### 5.11 Phasing against the ROADMAP

| Phase | Brand Ops scope |
|---|---|
| **P0 to P1** | This spec, the isolation ADR and the conformance-suite skeleton. Accounts created by hand (NX-297) once the brand name settles; setup log in the ops repo. **No automation.** First public post is by hand, labelled "simulated test" where applicable (Q-MKT-3) |
| **P2** (Twitch alpha) | Stage 0, **read-only**: Twitch EventSub milestones and counts, feed context, Discord and ntfy alerts, the Command Center page, `export-folder` adapter, manual intake. Own Discord app and Twitch client id. No PUBLISH credential exists |
| **P3** (public beta, YouTube, clip review queue) | YouTube READ adapter; Google OAuth In production and verification; start the YouTube API audit and quota extension early; private-upload `PublisherPort` adapter with read-back; **Instagram on Standard Access, own account** (D1) with comment and mention intake; email digest; optional scheduler adapter (D2, BO-38) |
| **P4** (depth) | Stage 1 scheduled publish after approval; weekly analytics digest; first Stage 2 rules (exact-match spam hide) behind the kill switch; **TikTok still manual** (D1) |
| **P5** (scale) | TikTok app review and inbox-draft adapter, Direct Post only if the audit passes and the UX contract allows (research §2.3); other platforms per ADR-0008; re-check disclosure rules |

### 5.12 Policy re-check
Each phase gate adds a "social policy and quota re-check" step beside NX-288 (BO-39). Facts that change behavior (quota buckets, AI-disclosure toggles, scope names, thresholds such as Twitch Affiliate criteria, which the research reports changed in May 2026 `[EXCERPT-OFFICIAL]` S31) are re-read from the live primary pages by a human or an agent that can reach them, and the research doc's `[UNVERIFIED]` and `[CONFLICT]` tags are cleared or confirmed in the PR that depends on them.

## 6. Failure modes

| Failure | Detect | Behavior | Recovery |
|---|---|---|---|
| Token expired or revoked (including Google Testing 7-day expiry) | 401 on the health probe; `token_expiring` item; BO-30 refusal | Stop that adapter, `HIGH` alert, one-tap re-consent link; other platforms continue; never fall back to another credential | Owner re-consents; check turns green |
| Quota exhausted (YouTube units or 100 uploads/day, Instagram cap, TikTok pending shares) | Local counters, 403 or 429 | Hold the queue; alert at `alert_pct`; resume at reset; artifacts whose approval expires become `EXPIRED` | Re-approve if needed |
| Platform outage or 5xx | Probe, retries with backoff | No duplicate posts (idempotency key = artifact hash + platform + account); digest note; status pages `[UNVERIFIED URLs]` | Retry resumes safely |
| Silent private lock (unaudited YouTube project; unaudited TikTok later) | Read-back shows `private` where `public` intended (BO-25) | `post_result` "published private - audit required"; never reported as success | Audit, or owner flips visibility manually |
| Policy or API change | Phase-gate re-check; optional weekly diff alert on tracked doc URLs `[UNVERIFIED]` | `POLICY_RECHECK` item; adapter feature flag off if needed | Update spec and adapter |
| **Wrong post approved** (wrong clip, typo, wrong label) | Staff notice after approval; or approval not yet consumed | Before publish: revoke or cancel (item to `REJECTED`; approval `REVOKED`), edit makes a new artifact (BO-13). After publish: delete or unpublish is itself a public write and needs `brand.publish` approval, or the owner uses the native tool; an audit row records both | Post-incident note in the audit; Stage reconsidered |
| **Wrong post published** (hash mismatch, swapped media) | Publisher hash recompute (BO-12); daily reconciliation (§5.8) | Abort on mismatch before the call; if discovered after, `CRITICAL`, auto-pause, kill switch | Review audit; rotate credentials if tampering suspected |
| **Compromised credentials, platform token leaked** | Platform security notice (EMAIL), unexpected publish, BO-SEC-9 | Pause, revoke at the platform, delete sops entry, rotate | Revocation runbook (§5.9); re-consent |
| **Compromised Brand Ops container** | Write outside approval, egress anomaly | It holds only its own tokens (BO-2): game, stream and chat unaffected; pause, revoke its tokens, rotate its Discord token and `custom_id` key | Rebuild image, re-consent |
| Compromised Discord token (Brand Ops app) | Unexpected bot activity | Forged buttons fail on HMAC and allowlist; rotate token | Rotate; the public announcer's token is a different app |
| Compromised Command Center session | Anomalous decision | Decision still needs BO-SEC-13 signature and, preferably, step-up; owner pauses | Revoke session (RB-11) |
| Hostile comment content | Sanitizer, ModerationProvider flag | Inert, masked, no fetch, no action (BO-SEC-2..6) | Staff clear or report on the platform |
| Feed outage | `brand_ops.feed.stale_after_s` | Shown as stale, never as "all quiet"; no new `CLIP_APPROVAL` items; collectors continue | Restore relay |
| Command Center unreachable | CC probe | Discord buttons still work; both down means nothing publishes (fail closed) | Restore access |
| Discord outage | Gateway disconnect | Command Center and ntfy still work | Reconnect |
| Brand Ops store lost or corrupt | Integrity check, backup (Q-OPS-6) | Fail closed: a missing approval means no publish; restore from backup, re-approve in-flight items | Restore; in-flight approvals re-collected |
| Clock or time-zone error on a scheduled post | Compare resolved UTC with intent; DST test | Show resolved UTC at approval; cancel window protects | Cancel and re-approve |
| Mailbox lost or locked | Owner report | Policy notices cannot reach manual intake | Recovery envelope (§5.9) |
| Webhook replay or forgery (if a receiver exists) | Signature, dedupe | Drop and count (BO-SEC-8) | |

## 7. Test plan

| Req | Tests |
|---|---|
| BO-1, BO-2 | Container-spec test: the image's env, mounts and network config contain none of the forbidden items (BO-2 list); a Brand Ops run with the sim DB path and stream-key names absent from its secrets and from the compose network; separate Discord app id, Twitch client id and Google project id asserted distinct from the gateway's in config checks |
| BO-3 | Schema test: an unlisted feed event kind or field is dropped and counted; a feed fixture containing chat text or a platform id is rejected; Brand Ops code has no feed publish function (static check) |
| BO-4 | Read-only mount: a write to the bundle path fails; a media file whose hash differs from `media_sha256` is rejected |
| BO-5 | Network test: no listening socket on a public interface; outbound to a host off the allowlist fails; the webhook receiver (if built) is a separate process |
| BO-6 | import-linter contract: `nexus.brand_ops` imports none of sim or gateway packages; vendor SDK imports only under adapter packages |
| BO-7, BO-8, BO-10 | Property test over the §5.2 transition table: every disallowed transition rejects; a decision made via Discord is visible in the Command Center and the reverse; clearing keeps item and audit rows |
| BO-9 | Duplicate signals produce one item; an alert burst above `max_per_hour` falls back to the digest |
| BO-11 | At Stage 0 every write adapter call is wrapped by a guard test: calling submit without an approval row raises; a matrix of (stage, action, approval) asserts only approved publish executes |
| BO-12, BO-13 | Mutate any approved field after approval: the publisher aborts on hash mismatch; replay of an approval or a double-clicked button publishes once; an expired approval is refused; an edit voids the earlier approval |
| BO-14, BO-SEC-7 | Service principal and ADMIN (at Stage 0) approval attempts denied; Discord approval from a non-allowlisted user, from a user with only a server role, with a forged, reused or stale `custom_id` all do nothing; step-up flag recorded |
| BO-15 | A clip not `APPROVED` in CLIPS-REPLAY creates no publication item; variants have independent approval rows when approved together |
| BO-16 | Stage change by a non-`brand.stage_set` identity denied; skipping a stage denied; unmet entry criteria shown and block the change; every change audited |
| BO-17 | A Stage 1 artifact publishes only at its approved time from an approved hash; cancel inside the window prevents the call |
| BO-18 | A rule without undo cannot be saved (`CHECK`); a rule outside the allowlist or beyond its rate cap does nothing; a DM, a reply or a generated-text action is unrepresentable in the rule schema; pause stops rules |
| BO-19, BO-20 | Missing provenance blocks approval; `tts_used` forces the AI toggle on where the capability exists and appends "Synthetic voices"; `simulated_actors` forces the simulated label and the on-screen flag; the simulator configured against the production channel is refused (Q-LEGAL-7) |
| BO-21 | Two variants of one clip are not byte-identical in text; a media file with a foreign watermark flag is blocked; the per-day cap holds |
| BO-22 | Conformance suite: an adapter that cannot set a label cannot publish public; capability fields match behavior (capability honesty) |
| BO-23 | Link builder emits only the first-party tag; a test fails on any third-party host, pixel or shortener in a generated link; destination page loads no third-party script |
| BO-24 | Collectors hold only READ credentials; a POLICY_NOTICE exists only from manual intake; no mailbox scope is requested by any adapter |
| BO-25 | Fake platform returns `private` for an intended `public`: the item is "published private" and not success; read-back mismatch always reported |
| BO-26, BO-SEC-10 | Fixtures with hostile comment text and token-shaped strings: none appears in ntfy, email, logs or Discord push bodies |
| BO-27 | Digest golden test with a fake clock in a DST-crossing IANA zone; data lag line present for insights |
| BO-28 | Quiet-hours test: a non-critical push is suppressed; a critical one passes |
| BO-29 | The publisher worker cannot call a read endpoint for comments and the reader cannot call a write endpoint (separate credentials, asserted by adapter fakes); scope lists differ by set |
| BO-30 | A Google credential with `oauth_app_state = TESTING` makes the adapter refuse to start outside the dev profile; expiry warning arrives `expiry_warn_days` ahead on a fake clock |
| BO-31 | Counters per bucket match fake call logs; an alert fires at 80%; at exhaustion the queue holds and nothing is sent |
| BO-32 | Secrets decrypt only with the host key; a fixture refresh token is encrypted at rest; the revocation drill leaves the platform password unchanged |
| BO-33 | Pause survives a restart; fail-closed when the state row is unreadable; a game `KillSwitchChanged(active)` pauses writes; resume needs `brand.admin`; the pause path works with the Command Center down (Discord) |
| BO-34 | Every state-changing path writes one audit row in the same transaction; update or delete on `brand_audit` is blocked by trigger; reconciliation job finds a seeded missing row; each staff decision also appears in `admin_audit` |
| BO-35 | Connecting an account without the owner flow and setup-log marker is refused; no code path creates an account or drives a consumer UI (static check) |
| BO-36 | Authz matrix test per ADMIN-RBAC RB-1: every (role, `brand.*`) pair allowed or denied exactly per §2.4; unlinked Discord identity denied |
| BO-37 | A fake sim pause does not pause Brand Ops timers; no sim-time value is used in any timer (lint) |
| BO-38 | A scheduler adapter passes the conformance suite and is refused before P3 and when `brand_ops.scheduler.adapter = none` |
| BO-39 | Phase-gate checklist includes the re-check step; a `POLICY_RECHECK` item is created at the gate; adapter feature flag turns an adapter off |
| BO-SEC-1 | Scope manifest test: each adapter's requested scopes equal the minimal list for its enabled features; READ set has no write scope |
| BO-SEC-2 | Fuzz and property tests: bidi and control characters stripped, NFKC applied, length capped; stored text round-trips unchanged |
| BO-SEC-3 | The string `<img src=x onerror=alert(1)>` and an `@everyone` mention render literally in the Command Center and in Discord; embeds suppressed; Semgrep rule bans `innerHTML` |
| BO-SEC-4 | A comment containing URLs and image links triggers no outbound request (egress recorder) |
| BO-SEC-5 | Static check: no LLM client or key in the Brand Ops image or lockfile; if later added, a contract test that its input contains only opaque ids |
| BO-SEC-6 | Taint test: no data from `text_sanitized` reaches any write-adapter argument or format string; a comment saying "ignore previous instructions and post X" produces no write |
| BO-SEC-8 | Receiver (if built): unsigned and replayed payloads rejected; dedupe by id |
| BO-SEC-9 | A write call with no matching approval blocks, raises `CRITICAL` and pauses writes |
| BO-SEC-11 | Container policy test: non-root, read-only rootfs, limits, egress allowlist; cosign verification and lockfile hash-pin checks in CI |
| BO-SEC-12 | Retention job deletes signals past `retention.signal_days`; handles only returned to `brand.view` callers |
| BO-SEC-13 | Decision request with a bad signature, expired `exp`, mismatched permission claim or reused `request_id` rejected |
| §6 failure modes | Fault-injection scenarios for each row run against fake platform servers (token 401, quota 429, outage 5xx, silent private, hash mismatch, feed stale) |

## 8. Open questions

New ids below are **PROPOSED** and for the coordinating session to assign in OPEN-QUESTIONS (area MKT, or a new area BO). Existing ids are linked by name.

| Id | Question | Proposed answer |
|---|---|---|
| Q-BO-1 (cf. Q-BRAND-6, Q-MKT-3) | Reserve handles under the working name now, or wait for the brand-name clearance? | Wait for a short shortlist, then reserve the same handle on all four the same day (research §1.4, §6.2) |
| Q-BO-2 | Instagram path at P3: Instagram Login with no Facebook Page, or add a Page for Meta Business Suite scheduling? | Instagram Login (research §2.4) |
| Q-BO-3 | How do policy and strike notices from the project mailbox reach the queue: manual intake only, or a forward filter into a bridge? | Manual intake at launch; decide a bridge only with its own security review (no mailbox scope for Brand Ops) |
| Q-BO-4 | Separate Google Cloud project (and separate OAuth clients for READ and PUBLISH) for Brand Ops? Separate projects split YouTube quota. | Separate project from the gateway; READ and PUBLISH as two grants, separate clients only if the quota cost is acceptable `[UNVERIFIED]` |
| Q-BO-5 | Does Instagram mention intake require a webhook receiver, and may a minimal public receiver exist at all (ADR and DAST)? | Poll where possible; no public receiver before an ADR |
| Q-BO-6 | Link tagging: `utm_*` names or own `src` tag, and does it fit the Q-DM-3 privacy text (NX-204, NX-314, NX-316)? | Own opaque `src` tag, read by first-party code only |
| Q-BO-7 | Numbers and examples for the Stage 1 and Stage 2 entry criteria (N approvals, observation periods, which auto-actions if any) | Owner sets them; hide exact-match spam only (research §6.2) |
| Q-BO-8 | Scheduler purchase at P3, and does the owner accept a third party holding publish tokens? | Native tools only until P3; optional afterwards |
| Q-BO-9 | May feed events or posts name approved callsigns of Operators, given deletion and pseudonymity rules (SEC-DATA-2, SEC-DATA-3)? | Not in the baseline feed |
| Q-BO-10 | Feed transport (relay, bus, polling) and where Brand Ops runs (the Linux server per ADR-0012 is assumed) | Pull from a read-only relay on the Linux server; decide in the ADR |
| Q-BO-11 | LLM-assisted drafting or comment summaries in Brand Ops later: separate key and budget outside the Q-AI-5 cap? | None until a spec change |
| Q-BO-12 | Retention period and privacy-notice wording for third-party commenter data (Q-LEGAL-3 area) | TBD with the retention schedule |
| Q-BO-13 | Public privacy and terms pages (Q-LEGAL-6) before Google verification and any audit: are they in the P3 critical path? | Yes; they block YouTube production use |
| Q-BO-14 | Who may approve besides the owner, and may moderators see comment text? | Owner only at Stage 0; moderators see non-publish kinds |
| Q-BO-15 | Does the owner have a hardware key, and which devices hold passkeys? (research §6.2) | Owner to answer; recovery tested once |
| Q-BO-16 | Twitch clip and marker creation (`clips:edit`, `channel:manage:broadcast`): in Brand Ops' PUBLISH set, or in the gateway? Not decided here | Out of the baseline; sim-rendered clips are the primary source |
| Q-BO-17 | Add the "social policy and quota re-check" step to every phase gate (BO-39)? | Yes |
| Q-BO-18 | Should the Discord allowlist be derived from verified staff links (ADMIN-RBAC RB-5) instead of config? | Config at Stage 0, derived later |

## 9. Integration notes

This spec changes no other file (AGENTS.md rule 11b). A coordinating session applies the following in follow-up PRs, one file at a time. Every item is PROPOSED.

| File | Change needed |
|---|---|
| **CONTRACTS** | New `BrandPlatform` enum (`TWITCH`, `YOUTUBE`, `INSTAGRAM`, `TIKTOK`; separate from the chat `Platform` enum, which has `KICK`, `DISCORD`, `LOCAL_SIM`). New enums: `BrandItemKind`, `BrandItemState`, `BrandStage`, `BrandArtifactState`, `BrandSignalKind`, `BrandPauseMode`, `BrandAuditAction`. New schema family `contracts/brand-feed/` (§4.3 events, vendor-free) and the signed `BrandDecisionRequest` (BO-SEC-13). Admin API additions `/admin/brand/*` (§4.4). **No** new `STAFF_*` or `SYS_*` command and no `CommandKind` change |
| **ADMIN-RBAC** | Role `SVC_BRAND_OPS` (zero permissions, listed so RB-7 tests cover it). Permissions `brand.view`, `brand.review`, `brand.publish`, `brand.pause`, `brand.admin`, `brand.stage_set` in §4.2, the matrix in §4.3 (OWNER all, `brand.stage_set` two-person eligible; ADMIN all but `brand.publish` and `brand.stage_set` at Stage 0; MODERATOR `brand.view`, `brand.review` for non-publish kinds, `brand.pause`; others none), §6 feature area "Brand", §7.2 parity note for `/brandops` (Brand Ops' own Discord app, distinct from `/nexus`), §8 admin API list and enums, §10 phasing (P2 view and review, P3 publish). `admin_audit` mirror of staff decisions. Note RB-5: the Brand Ops Discord allowlist is a config list until derived from verified staff links (Q-BO-18) |
| **DATA-MODEL** | A pointer section: Brand Ops tables (§4.5) live in Brand Ops' own store, not the sim durable store, and are specified here; retention schedule row for `brand_signals` (SEC-DATA-4, Q-BO-12). Add provenance fields to `clips` (§4.14: `tts_used`, `owner_voice_used`, `simulated_actors`, `sim_rendered`) and an export record (`exported_at`, `export_sha256`) for BO-4, BO-19. Existing mismatch to resolve: `clips.reviewed_by` allows only `'OWNER'` while ADMIN-RBAC grants `mod.clip_review` to MODERATOR and ADMIN |
| **CONFIG-AND-CONTENT** | §4.2: note that Brand Ops has its own runtime config file and add the `brand_ops.*` keys of §4.6 with clock labels (CFG-9). Keep them out of the balance hash. Secret references only (`secret_ref`) |
| **OPS-ADMIN** | §2 metrics: adapter up, token days remaining, quota used per bucket, queue depth and oldest open item age, publish attempts by outcome, feed lag. Alerts: Brand Ops down, token expiring, quota over 80%. §3 Command Center "Brand" page and the clip review queue pointer. §4 runbooks: brand-account setup (template, no identifiers), rotate Brand Ops secrets, social policy change, compromised social credentials, Brand Ops pause and resume. A new `OA-n` requirement that stream-offline paging stays with OA-5/OA-6 |
| **THREAT-MODEL** | Assets: social publish tokens. Component row "Brand Ops" with its entry points (platform text, Discord, Command Center API). New `SEC-BO-*` summary pointing at BO-SEC-1..13. New **SEC-LLM-6**: text from social platforms reaches no LLM except through a reviewed, tool-less, credential-less path (BO-SEC-5). Extend SEC-CLIP-1 (its "until Phase 7" has no counterpart in ROADMAP, which ends at P5) to say clips are published only through Brand Ops stages. Note the Brand Ops container as another SEC-LLM-5-style credential-isolated component |
| **ADR** | New ADR (next free number): Brand Ops isolation boundary and the read/publish credential split (hard to reverse, surprising, a real trade-off). Amend ADR-0010: replace the `ClipPublisher` row with `PublisherPort` and add `BrandPlatformAdapter` and `BrandNotifier`, living in `nexus.brand_ops.*`. ADR-0008: add Instagram at P3 and keep TikTok manual through P4 |
| **TRACKER** | NX-328 to status Draft spec. New items (ids to be assigned): Brand Ops service skeleton, store and audit; one-way feed and clip bundle export; Command Center Brand page and signed decision API; Discord approval bot (own app, signed buttons); `PublisherPort`, conformance suite and `export-folder` adapter; Twitch READ adapter (P2); YouTube READ and private-upload adapters, Google OAuth production and verification, API audit process (P3); Instagram adapter (P3); email digest; Stage 1 (P4); Stage 2 rules (P4); brand-account setup runbook (relates to NX-297); phase-gate policy re-check step (relates to NX-288); the isolation ADR; ADMIN-RBAC, CONTRACTS, DATA-MODEL, CONFIG, OPS-ADMIN and THREAT-MODEL follow-ups above |
| **OPEN-QUESTIONS** | Add the Q-BO rows of §8 (the area name and numbering are the coordinating session's call). Record the owner decisions D1 to D11 against Q-MKT-4 and Q-AI-6 |
| **CLIPS-REPLAY** | §4: replace "uploads it manually or via the API" with the Brand Ops hand-off (approved clip bundle, then Brand Ops stages) |
| **GLOSSARY** | Brand Ops, review item, approved artifact, Brand Ops stage (0, 1, 2), publisher credential set, "Synthetic voices" label. Definitions only, no implementation detail |
| **PLATFORM-REALITY-CHECK** | §5 correction on the YouTube `videos.insert` quota bucket after a live check (research §6.3) |
| **AGENTS.md / SYSTEM-DESIGN** | Repository layout adds `services/brand-ops/`; SYSTEM-DESIGN gets Brand Ops as a deployable outside the modular monolith (ADR-0001 notes the exception) and the one-way feed as a boundary |
| **MARKETING** | Link to this spec for the approval flow and cadence; the per-platform AI-label rule from BO-19 |

## 10. Evidence and sources

All platform facts come from [SOCIAL-CHANNEL-AUTOMATION-RESEARCH](../review/SOCIAL-CHANNEL-AUTOMATION-RESEARCH.md) (source list §7.2, ids S10..S69) and [MARKETING-AND-PRODUCTION-RESEARCH](../review/MARKETING-AND-PRODUCTION-RESEARCH.md) §4.8, as web-search excerpts read on 2026-10-18 with no primary page read. Repo facts come from AGENTS.md, ADMIN-RBAC (RB-1..RB-13, §4, §5, §7, §8), OPS-ADMIN (§1..§4), CHAT-GATEWAY, CLIPS-REPLAY, LLM-ADVISORS (LLM-2), DATA-MODEL (§4.14, §4.15), CONFIG-AND-CONTENT (§4.1, §4.2, CFG-9), THREAT-MODEL (SEC-GW, SEC-OV, SEC-MOD, SEC-LLM, SEC-CLIP, SEC-CI), ADR-0008, ADR-0010, MARKETING, and the OPEN-QUESTIONS rows Q-MKT-1..4, Q-LEGAL-6/7/8, Q-ARCH-7, Q-ARCH-10, Q-DM-3, Q-OPS-4, Q-AI-6.
