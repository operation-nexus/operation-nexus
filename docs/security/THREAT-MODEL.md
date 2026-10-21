# Threat Model & Security Requirements

Status: Approved (owner, 2026-10-19; NX-040) · Tracker: NX-040…NX-049 · Inputs: [`SECURITY-REVIEW-RAW-PLANS.md`](../review/SECURITY-REVIEW-RAW-PLANS.md), [`PLATFORM-REALITY-CHECK.md`](../review/PLATFORM-REALITY-CHECK.md)

## 1. What we protect (ranked)
1. **Channel standing.** A ToS or community-guideline strike or a ban on Twitch/YouTube is the most damaging outcome. Most of these risks come from *content* (slurs on screen or in TTS) rather than from hacking.
2. **Credentials:** platform OAuth tokens (especially YouTube upload scope), stream keys, Discord bot token, LLM keys.
3. **The broadcast host.** It holds the stream keys and runs OBS.
4. **Commander profiles** (XP, rank, callsigns) and viewers' personal data.
5. **Availability** of the 24/7 stream and the LLM/TTS budget.

## 2. Actors
- **Trolls and raiders** (coordinated waves, slur callsigns).
- **Botnets and Sybils** (XP farming, cost DoS).
- **Prompt injectors.**
- **Account hijackers** targeting high-rank or streamer profiles.
- **Compromised dependencies.** LiteLLM was compromised in March 2026, so this has precedent.
- **Malicious PR authors** if the repo is public.
- **Over-privileged moderators and Game Masters.** A GM is limited to the Static and world events during play and can inject jobs into the Static's Tasking Board only; campaign setup is Owner/Admin only (Q-ALN-10, Q-ALN-11). The server enforces this through the RBAC matrix (ADMIN-RBAC RB-1, §4.3), not the UI.

## 3. Trust boundaries
```
[Twitch/YT/Kick chat] --B1--> [gateway] --B2--> [llm-gateway] --B3--> [sim]
                                   |                                  |
                                   +----------- normalized cmds ------+
[sim] --B4 WS (redacted state)--> [overlay in OBS] --> public broadcast
[internet] --B5--> [link portal / companion API]
[services] --B6--> [SQLite now; Postgres/Redis if split per ADR-0003]
[clip worker] --B7--> [review folder] --(human)--> platforms
[GitHub CI] --B8--> [GHCR] --> [broadcast host]
```
Newer boundaries (Q-TM-3); their rules live in the spec named, not here:

| Boundary | Crossing | Rules |
|---|---|---|
| B9 | Staff → Command Center (tailnet plus verified Discord login) | ADMIN-RBAC RB-1…RB-5 |
| B10 | Public site ← read-only exports (FOW-1 while a war runs) | PUBLIC-SITE, FOG-OF-WAR FOW-1 |
| B11 | Discord bot and its token | DISCORD-SERVER-SETUP |
| B12 | Brand and social automation tokens | BRAND-OPS BO-SEC |
| B13 | Error reports → Sentry (outbound), and Sentry, CI and issue text → the daily-routine agent (inbound) | ERROR-PIPELINE EP-2 (allowlist scrub), EP-6 (text is data; tests and CODEOWNERS files are proposal-only) |

Rule: **data crossing B1, B3 or B5 is untrusted.** That includes display names and LLM output.

Kick is an optional platform, not a committed one (Q-PROD-2); its B1 path exists only if its adapter is enabled, and it gets the same B1 rules.

## 4. STRIDE summary
| Component | Top threats | Mitigation reqs |
|---|---|---|
| Gateway | Spoofing via display names; spam/raid DoS; injected text | SEC-GW-* |
| LLM gateway | Prompt injection, cost exhaustion, unit hijack via `callsign_target` | SEC-LLM-* |
| Sim/API | Unauthenticated commands; slow-client stall; FoW leak while a campaign is running (a full reveal in archives and recaps after the campaign ends is intended, Q-ALN-21, CLIPS-REPLAY RP-2) | SEC-API-*, FOW-1, FOW-2 |
| Overlay/OBS | Stored XSS → broadcast; render crash ends stream | SEC-OV-* |
| Link portal | Account takeover; token leak/brute force; CSRF | SEC-ID-* |
| TTS / clips | Slurs spoken or uploaded; defamatory narration | SEC-MOD-*, SEC-CLIP-* |
| Data stores | Lost updates; unauthenticated Redis (once introduced); PII retention | SEC-DATA-* |
| CI/CD | Unpinned actions; token over-privilege; poisoned deps | SEC-CI-* |

## 5. Security requirements (testable MUSTs)

### Identity & linking (SEC-ID)
- **SEC-ID-1.** A platform identity MUST be bound to a commander only after successful OAuth with that platform (Twitch, Google, Discord; Kick only if that optional adapter is enabled, Q-PROD-2). Requests that supply a `platform_user_id` directly MUST be rejected. *Test:* POST with an arbitrary id returns 4xx.
- **SEC-ID-2.** An existing `(platform, platform_user_id)` mapping MUST NOT be overwritten. Re-linking requires OAuth by the current owner of that identity.
- **SEC-ID-3.** Any one-time token MUST have ≥128 bits from a CSPRNG (`secrets.token_urlsafe(32)`), MUST be stored hashed, MUST be single-use (atomic delete-on-claim), MUST expire in ≤10 min, and MUST be rate-limited (≤10 attempts/IP/min).
- **SEC-ID-4.** Tokens MUST NOT be posted in public chat or included in state-changing GET URLs. The chat bot posts only a generic portal URL. The user signs in with platform OAuth there; no token is needed in chat (see IDENTITY spec).
- **SEC-ID-5.** Portal forms MUST use CSRF protection (SameSite=strict cookie + token), POST bodies, and secure session cookies.
- **SEC-ID-6.** Merging MUST happen in a single serializable transaction. **XP MUST NOT be summed on merge.** The surviving profile keeps the max per stat, or the primary's stats, per PROGRESSION §merge (Q-PROG-4).

### Gateway (SEC-GW)
- **SEC-GW-1.** Every inbound message MUST be normalized to `ChatEnvelope`: NFKC, confusables folded for comparison, control and bidi characters stripped, length ≤ 300 chars.
- **SEC-GW-2.** Per-user, per-command-class token-bucket rate limits (values in CHAT-GATEWAY §5, admin-adjustable) and a global admission cap MUST be enforced before the sim sees a command. Redemption cooldowns and the supply-drop hourly cap are enforced the same way, on a monotonic real-time clock, before a redemption reaches the sim (Q-ALN-4, Q-SUP-7).
- **SEC-GW-3.** Only official platform APIs are permitted. A reverse-engineered adapter (TikTok) requires an approved ADR, runs in an isolated container with no other credentials, and never uses the owner's personal session.
- **SEC-GW-4.** Webhook payloads (Twitch EventSub; Kick webhooks if the optional Kick adapter is enabled, Q-PROD-2) MUST have their signatures verified and be deduplicated by message id.

### API / WS (SEC-API)
- **SEC-API-1.** The command ingest MUST be internal-only. Today it's an in-process queue; once split, it moves to authenticated Redis Streams or mTLS/HMAC. The gateway is the only producer. No public command HTTP endpoint.
- **SEC-API-2.** The overlay WS MUST bind to localhost or the private network, check Origin, and require a capability token. CORS MUST be an explicit allowlist.
- **SEC-API-3.** Each WS client MUST have a bounded send queue. A slow client is dropped and MUST NOT delay the tick by more than 5 ms. Connections MUST be capped.

### Overlay (SEC-OV)
- **SEC-OV-1.** No user-derived data may be assigned to `innerHTML` or equivalents (enforced by Semgrep). *Test:* the username `<img src=x onerror=alert(1)>` renders literally.
- **SEC-OV-2.** The overlay MUST ship a strict CSP (no inline script, `connect-src` limited to the WS origin). OBS browser source "page permissions" MUST be set to *No access*.

### Moderation (SEC-MOD)
- **SEC-MOD-1.** Every user-derived string MUST pass the moderation pipeline before render, TTS, or upload: normalization → denylist (including leetspeak and homoglyph folding) → optional classifier. Unapproved names render as a **neutral generated callsign** (e.g., `VIPER-27`), not the raw display name (Q-MOD-1).
- **SEC-MOD-2.** TTS MUST speak only approved callsigns, or a phonetic-alphabet readout of them, and never raw usernames or raw chat.
- **SEC-MOD-3.** Staff MUST have a kill switch that blanks user text, mutes TTS, freezes spawns, and bans a user across platforms, reachable from a phone (ADMIN spec).
- **SEC-MOD-4.** Custom or cloned voices MUST NOT ship without a written consent policy and an approved ADR.

### LLM (SEC-LLM)
- **SEC-LLM-1.** Only messages with an explicit LLM prefix (`!order`) reach an LLM. Everything else goes to the deterministic parser or is ignored.
- **SEC-LLM-2.** Per-user (e.g., 5/10 min) and global (e.g., $/day) budgets, an input length cap, a timeout, and a circuit breaker MUST be enforced. Over budget, the gateway MUST degrade to deterministic handling.
- **SEC-LLM-3.** Parsed orders MUST target only units owned by the requester. Coordinates are bounded, and node references must be in the known-id enum.
- **SEC-LLM-4.** Raw usernames, callsigns, and chat text MUST NOT appear in Threat Director or narration prompts. Entities are referenced by opaque ids.
- **SEC-LLM-5.** The LLM process MUST run without platform OAuth tokens or stream keys in its environment.

### Clips & uploads (SEC-CLIP)
- **SEC-CLIP-1.** No clip is uploaded automatically. Clips go to a review queue, and a human approves them (at least until Phase 7).
- **SEC-CLIP-2.** FFmpeg MUST be invoked with an argv list, never `shell=True`. Paths come from a whitelist directory, and filenames are generated.

### Data (SEC-DATA)
- **SEC-DATA-1.** If and when Redis or Postgres is introduced, it requires auth, is not published to the host network, and binds to the internal network only. Compose ports bind to `127.0.0.1`.
- **SEC-DATA-2.** Event logs and replays store `commander_id` only. The id→name mapping is a separate, deletable table (crypto-shredding). After deletion, the commander displays as `REDACTED-…` everywhere, including old replays (Q-DM-2, DATA-MODEL §6.4).
- **SEC-DATA-3.** A `!forget` command or portal action deletes a user's profile and identities within 30 days. A privacy notice is linked from the channel.
- **SEC-DATA-4.** Retention: raw chat envelopes 7 days, command log for the campaign duration + 30 days, aggregates kept indefinitely (Q-LEGAL-3).
- **SEC-DATA-5.** Nightly encrypted backups with a tested restore, run quarterly.

### CI/CD (SEC-CI)
- **SEC-CI-1.** Actions MUST be pinned by SHA, use least-privilege `permissions`, and never use `pull_request_target` with a PR checkout or interpolate `${{ github.event.* }}` into `run:`.
- **SEC-CI-2.** Merge is gated on CodeQL, Semgrep, gitleaks, dependency-review, SCA, and trivy config/image.
- **SEC-CI-3.** Released images MUST be signed (cosign keyless), carry an SBOM and provenance, and have their signature verified at deploy.
- **SEC-CI-4.** Python and Node lockfiles MUST pin hashes (`uv.lock`, `pnpm-lock.yaml`). Builds use `--frozen`.
- **SEC-CI-5.** No self-hosted runner may execute untrusted PR code.

## 6. Residual risks accepted (pending owner sign-off)
- Platform outages and policy changes are outside our control. Mitigation: multi-platform support, graceful degradation, and monitoring.
- Usernames inside clips that were already posted can't be erased.
- The moderation denylist will never be complete. Defense in depth: generated callsigns by default and a staff kill switch.
- A trusted insider (admin or GM) can abuse legitimate access within their own permissions; RBAC cannot prevent that. Mitigation: every action is audited, GM actions are flagged on stream, and FULL takeover ships later (Q-TD-9).
- The full-truth frame stream is stored on the broadcast host during a war (Q-SIM-18), so a host compromise mid-campaign leaks the fog of war. Mitigation: it is never served before the war ends (FOW-1a), and the host is the most protected asset.
- A single owner holds the vault, the age key and every platform token: losing them is a single point of failure. Mitigation: the documented backups in the ops vault.

Signed off by the owner on 2026-10-19 (NX-040, Q-TM-2, Q-TM-4).
