# SPEC: Identity & Account Linking

Status: Draft · Tracker: NX-200…NX-209 · Security: THREAT-MODEL SEC-ID-*

## 1. Model
```
commanders(commander_id UUIDv7 PK, callsign UNIQUE, callsign_kind GENERATED|CUSTOM|TOMBSTONE,
           created_at, banned bool, deletion_requested_at null, deleted_at null, taunt_opt_out bool)
platform_identities(platform enum, platform_user_id text, commander_id FK, display_name text,
                    platform_account_created_at null, first_seen, last_seen,
                    PRIMARY KEY(platform, platform_user_id))
identity_events(append-only audit: created, linked, unlinked, merged, banned, forgotten)
```
- The platform enum is defined once in `/contracts`. That removes the YT vs YOUTUBE duplication.
- Full DDL, including XP (derived from append-only ledgers, not stored on the commander row), is in [DATA-MODEL](DATA-MODEL.md) §4.
- `platform_identities.first_seen` is the "first-seen age" anti-farming layer (PROGRESSION PROG-4, Q-PROG-6, NX-277). Platform account age is a further layer only where the platform API exposes it [UNVERIFIED: Twitch Get Users `created_at`; YouTube channel `publishedAt` costs quota]. It is stored in `platform_identities.platform_account_created_at` and stays null when the platform doesn't provide it (DATA-MODEL §4.3).

## 2. Lazy creation (P2)
The first valid command from an unknown `(platform, platform_user_id)` creates a commander with a **generated callsign** of the form `WORD-NN` (for example `VIPER-27`), drawn from a curated word list. Uniqueness is enforced and collisions are retried. The display name is never used to build the callsign.

Raid-origin viewers are normal viewers in our chat and get commanders the same way (Q-GW-2). Twitch Shared Chat messages that originate in another channel are ignored by default, so they create no commander; `gateway.shared_chat.accept_foreign` (default false) enables them only after the source-channel API fields are verified [UNVERIFIED] (CHAT-GATEWAY).

## 3. Custom callsigns (P3)
Unlocks after the commander's first completed mission (Q-PROG-3). The format is `^[A-Z][A-Z0-9-]{2,11}$`, then moderation (SEC-MOD-1). Generated-callsign patterns (`WORD-NN`), the tombstone prefix `X-`, and command keywords (`HOLD`, every role name and every stance word) are reserved (Q-GP-39). A callsign may not equal a node name or alias; the theater validator also rejects node names or aliases equal to a reserved word or an existing callsign. and callsigns are unique across all platforms. Changes are limited to one per 30 days.

## 4. Cross-platform linking (P3) — OAuth only (replaces the token-in-chat design)
Not needed at launch: the game launches on Twitch only, and linking ships with YouTube in the public beta (Q-PROG-5).

1. A viewer types `!link`. The bot (in its periodic digest) or the overlay ticker shows the **static portal URL**. No token is posted in chat.
2. On the portal, the viewer signs in with platform A (OAuth). That proves ownership of A's `platform_user_id`, and the portal resolves A's commander.
3. The viewer clicks "Add Twitch / YouTube" (plus Kick only if the optional Kick adapter ships, Q-PROD-2) and signs in with platform B (OAuth), which proves ownership of B.
4. If B has no commander yet, it is attached to A's commander. If B already has a commander, the portal shows a **merge preview** (which callsign is kept, the per-stat max, and whether the taunt opt-out ends up set) and asks for confirmation.
5. The merge runs as a single transaction: **XP is not summed** (SEC-ID-6, Q-PROG-4), the taunt opt-out follows "opt-out wins" (ID-PREF-1, Q-ALN-28), and the event is written to the audit log. Merges are limited to one per 30 days.

The portal is a separate small web app (P3), exposed through a tunnel. It uses the minimum OAuth scopes needed for identity (no chat or upload scopes), sets CSRF, SameSite and secure cookies, and is DAST-scanned in staging.

## 5. Deletion (SEC-DATA-3)
`!forget` or the portal sets `deletion_requested_at`. Within 30 days the job deletes identities, replaces the callsign with a unique tombstone value `X-<tag>` (`callsign_kind = TOMBSTONE`, DATA-MODEL §4.2), sets `deleted_at`, and shreds the id→name mapping. The tag is a random 4-character value drawn and stored at deletion time, not derived from any identifier, so it can't be reversed (Q-ALN-29). Viewers see `REDACTED-<tag>` (e.g. `REDACTED-7KQ2`) wherever a tombstoned callsign would appear (Q-DM-2), never the `X-` value itself, and two deleted commanders stay distinct in replays. Replays already contain only ids.

A deletion request is a safety action: `!forget` is accepted while the campaign is paused (Q-ALN-24).

## 6. Preferences
- **ID-PREF-1 Taunt opt-out** (Q-AI-7, Q-ALN-12): `!quiet` is a toggle. Each use flips a per-commander opt-out flag; sending `!quiet` again while opted out opts the commander back in. The bot confirms the new state (CHAT-GATEWAY CG-4). While the flag is set, Static mastermind taunts never name that commander (no `{target}` fill with their callsign). The flag is a column on the commander in DATA-MODEL §4 (Q-ALN-12), so it applies on every linked platform. **On a merge, opt-out wins** (Q-ALN-28): the merged commander is opted out if either commander was (§4 step 5). `!quiet` does not reset idle timers (CHAT-GATEWAY CG-6, Q-ALN-26). `!quiet` lands in the command catalog, parser and handler in one PR (AGENTS.md rule 6a).

## 7. Open questions
- Decided and folded in (2026-10-18): Q-ALN-12 (ID-PREF-1), Q-ALN-24 (`!forget` while paused, §5), Q-ALN-26 (§6), Q-ALN-28 (opt-out wins on merge, §4, §6), Q-ALN-29 (`REDACTED-<tag>`, §5), Q-DM-2, Q-PROD-2 (Kick optional, §4).
- None open.
