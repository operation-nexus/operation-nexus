# SPEC: Identity & Account Linking

Status: Draft · Tracker: NX-200…NX-209 · Security: THREAT-MODEL SEC-ID-*

## 1. Model
```
commanders(commander_id UUIDv7 PK, callsign UNIQUE, callsign_kind GENERATED|CUSTOM|TOMBSTONE,
           created_at, banned bool, deletion_requested_at null, deleted_at null)
platform_identities(platform enum, platform_user_id text, commander_id FK, display_name text,
                    first_seen, last_seen, PRIMARY KEY(platform, platform_user_id))
identity_events(append-only audit: created, linked, unlinked, merged, banned, forgotten)
```
- The platform enum is defined once in `/contracts`. That removes the YT vs YOUTUBE duplication.
- Full DDL, including XP (derived from append-only ledgers, not stored on the commander row), is in [DATA-MODEL](DATA-MODEL.md) §4.
- `platform_identities.first_seen` is the "first-seen age" anti-farming layer (PROGRESSION PROG-4, Q-PROG-6, NX-277). Platform account age is a further layer only where the platform API exposes it [UNVERIFIED: Twitch Get Users `created_at`; YouTube channel `publishedAt` costs quota]. The current DDL has no column for it.

## 2. Lazy creation (P2)
The first valid command from an unknown `(platform, platform_user_id)` creates a commander with a **generated callsign** of the form `WORD-NN` (for example `VIPER-27`), drawn from a curated word list. Uniqueness is enforced and collisions are retried. The display name is never used to build the callsign.

Raid-origin viewers are normal viewers in our chat and get commanders the same way (Q-GW-2). Twitch Shared Chat messages that originate in another channel are ignored by default, so they create no commander; `gateway.shared_chat.accept_foreign` (default false) enables them only after the source-channel API fields are verified [UNVERIFIED] (CHAT-GATEWAY).

## 3. Custom callsigns (P3)
Unlocks after the commander's first completed mission (Q-PROG-3). The format is `^[A-Z][A-Z0-9-]{2,11}$`, then moderation (SEC-MOD-1). Generated-callsign patterns (`WORD-NN`) and the tombstone prefix `X-` are reserved, and callsigns are unique across all platforms. Changes are limited to one per 30 days.

## 4. Cross-platform linking (P3) — OAuth only (replaces the token-in-chat design)
Not needed at launch: the game launches on Twitch only, and linking ships with YouTube in the public beta (Q-PROG-5).

1. A viewer types `!link`. The bot (in its periodic digest) or the overlay ticker shows the **static portal URL**. No token is posted in chat.
2. On the portal, the viewer signs in with platform A (OAuth). That proves ownership of A's `platform_user_id`, and the portal resolves A's commander.
3. The viewer clicks "Add Twitch / YouTube / Kick" and signs in with platform B (OAuth), which proves ownership of B.
4. If B has no commander yet, it is attached to A's commander. If B already has a commander, the portal shows a **merge preview** (which callsign is kept, the per-stat max) and asks for confirmation.
5. The merge runs as a single transaction: **XP is not summed** (SEC-ID-6, Q-PROG-4), and the event is written to the audit log. Merges are limited to one per 30 days.

The portal is a separate small web app (P3), exposed through a tunnel. It uses the minimum OAuth scopes needed for identity (no chat or upload scopes), sets CSRF, SameSite and secure cookies, and is DAST-scanned in staging.

## 5. Deletion (SEC-DATA-3)
`!forget` or the portal sets `deletion_requested_at`. Within 30 days the job deletes identities, replaces the callsign with a unique tombstone value (`callsign_kind = TOMBSTONE`, DATA-MODEL §4.2), sets `deleted_at`, and shreds the id→name mapping. Viewers see `[REDACTED]` wherever a tombstoned callsign would appear. Replays already contain only ids.

## 6. Preferences
- **ID-PREF-1 Taunt opt-out** (Q-AI-7): `!quiet` records a per-commander opt-out. While it is set, Static mastermind taunts never name that commander (no `{target}` fill with their callsign). Stored per commander, so it applies on every linked platform.
- Open: how a commander opts back in, and where the flag lives in DATA-MODEL §4 (no column yet). `!quiet` must also be added to the command catalog, parser and handler in one PR (AGENTS.md rule 6a).
