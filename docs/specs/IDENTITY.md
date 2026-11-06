# SPEC: Identity & Account Linking

Status: Draft · Tracker: NX-200…NX-209, NX-518 (§7, Draft) · Security: THREAT-MODEL SEC-ID-*

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

Identity generates callsigns outside the sim and sends each change (generated, approved, tombstone) as the logged system command `SYS_SET_CALLSIGN` (CONTRACTS §5.2); the sim keeps a per-commander callsign for JOIN and live units (SIM-CORE §4, Q-SIM-39).

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

## 7. Name modes (NX-518, Q-MOD-10)
Status: **Draft — needs owner sign-off.** No code until the owner approves this section and the security review in §7.8 has passed. Source: Q-MOD-10 (owner, 2026-11-06; the row is in a pending PR): "I honestly want to experiment/test both modes, people may get confused or not want callsigns unless they can pick their own username/nickname as a callsign".

### 7.1 The switch
- **ID-NM-1 One key.** Runtime key `identity.name_mode`, enum `GENERATED | CHOSEN | DISPLAY`, default `GENERATED` (today's rules, §2–3). It is a runtime/app key (CONFIG-AND-CONTENT §4.2), not a balance key: the sim never reads it, because identity runs outside the sim (§2), and a balance key would move `config_hash` and the goldens with no sim effect. So the add-config-key skill does not apply.
- **ID-NM-2 Who and when.** OWNER or ADMIN sets it in the deploy config; runtime keys change on a process restart (CONFIG-AND-CONTENT §4.1). It is changed only between campaigns, so one campaign runs one mode. The effective value is logged at startup with its source (CONFIG-AND-CONTENT §4.2 item 3), which ties a campaign to its mode.
- **ID-NM-3 Existing callsigns are kept.** A mode change never renames anyone. Approved `CUSTOM` callsigns stay in every mode. Only commanders still on a `GENERATED` callsign are affected by a new mode (§7.3, §7.4).
- **ID-NM-4 A value exists only with its code.** `CHOSEN` and `DISPLAY` join the runtime schema's enum in the PR that implements each, after its security review. Until then the runtime schema refuses them and startup fails (CONFIG-AND-CONTENT §4.3 step 1).

### 7.2 GENERATED (today)
Unchanged: a generated callsign at first command (§2); `!callsign` after the first completed mission (§3, Q-PROG-3), moderated, one change per 30 days.

### 7.3 CHOSEN (recommended for the experiment)
- **ID-NM-5 Pick from the first command.** A commander may send `!callsign <NAME>` (`SET_CALLSIGN`, COMMAND-CATALOG §2) at any time, with no mission unlock. There is no new command. Rule 6a is met by the existing catalog row plus its schema, parser entry and handler, which are still to be built (today `CommandKind` has no `SET_CALLSIGN`, `contracts/common/enums.json:30`).
- **ID-NM-6 Same checks as §3.** Format `^[A-Z][A-Z0-9-]{2,11}$`, the reserved words (Q-GP-39), node names and aliases, uniqueness across platforms on the confusable-folded `normalized_key` (DATA-MODEL §4.5), and moderation (SEC-MOD-1). Rate class Callsign, 1 per 60 s (Q-CMD-3). Accepted while paused (CONTRACTS §5.2); never resets idle timers (CHAT-GATEWAY CG-6).
- **ID-NM-7 Until they pick.** Every commander still gets a generated callsign at first command (§2), so `!join` never waits for a name. The first-join digest line suggests `!callsign <NAME>`.
- **ID-NM-8 Limits (recommended).** The first change away from a generated callsign is free: no unlock and no 30-day cooldown. Later changes keep one per 30 days, to stop name-hopping and impersonation churn. A rejected request does not count against the limit.

### 7.4 DISPLAY (recommended: specify now, do not ship in the first experiment)
- **ID-NM-9 Derive, never copy.** On a commander's first command in a campaign, if their callsign is `GENERATED`, identity derives a candidate from the stored `display_name` (CONTRACTS §4, SafeText ≤ 64): uppercase; keep `A-Z` and `0-9`; map space, `_` and `.` to `-`; collapse and trim `-`. Any other character, non-ASCII included, rejects the candidate. There is no transliteration: it would be a homoglyph path and a new dependency. Then truncate to 12 and run ID-NM-6.
- **ID-NM-10 Failures fall back.** A candidate that is too short, reserved, taken, a `WORD-NN` match or unapproved leaves the generated callsign in place, and the digest suggests `!callsign`. **No uniqueness suffix** (`NAME-2`): a suffix makes lookalikes of other players and of staff.
- **ID-NM-11 Once only.** Derivation runs once per commander. A later platform rename does not change the callsign, so a rename is no way around a staff revoke. `!callsign` works as in CHOSEN.
- **ID-NM-12 Impersonation.** The broadcaster's and every staff member's names (ADMIN-RBAC roster) are reserved, folded like the rest. Only the matching commander may hold one, shown by the platform `BROADCASTER`/`MODERATOR` badge (CONTRACTS §4) plus staff confirmation. Within ASCII the fold also maps lookalikes (`0`/`O`, `1`/`I`/`L`) [fold table PROPOSED].
- **ID-NM-13 Linking and deletion.** A merge keeps one callsign, as §4 step 4 already says. `!forget` tombstones a derived callsign like any other (§5).

### 7.5 What does not change
The wire type is still `Callsign`, sent by `SYS_SET_CALLSIGN` and `CallsignChanged`. A chosen or derived callsign is `callsign_kind = CUSTOM`: no new kind and no contract change. The raw display name never reaches the sim, wire, events, logs, TTS or prompts (CONTRACTS §3.5, SEC-MOD-2, SEC-LLM-4). Tombstones (§5), `!quiet` (§6) and replays holding ids only (DATA-MODEL DM-6) are unchanged. Names fit the 16-character map chip (Q-UX-26), since a callsign is at most 12.

### 7.6 Moderation flow (SEC-MOD-1)
- **ID-NM-14 Automatic checks first.** Format, reserved, taken and denylist (with leetspeak and homoglyph folding) run at once. A failure is `AUTO_REJECTED` with its reason (DATA-MODEL §4.5) and a digest line keyed by `RejectReason`, never an echo of the name (CHAT-GATEWAY GW-14).
- **ID-NM-15 Approval (open, Q1).** Recommended for CHOSEN and DISPLAY: approve on passing the automatic pipeline (normalization, denylist, optional classifier), which is what SEC-MOD-1 requires, and review after the fact. Today's human queue (CONTRACTS §8, `mod.callsign_review`) keeps the names the classifier flags. Staff pre-approval of every name would leave names waiting overnight, since mods have no duty hours (Q-MOD-7).
- **ID-NM-16 While pending.** The generated callsign shows (SEC-MOD-1). A moderation service error means unapproved, never fail-open (CHAT-GATEWAY §7).
- **ID-NM-17 Staff revoke.** A MODERATOR or above can revoke an approved name. Identity sends `SYS_SET_CALLSIGN` with a new generated callsign, marks the request `REJECTED` with reason `OWNER`, and blocks the name for that commander. This needs an admin endpoint next to `/admin/callsigns/*` (CONTRACTS §8), added with the code. Repeated rejects are a conduct signal (Q-MOD-5). Appeal: the viewer asks a mod, who may approve the name from the queue.

### 7.7 Running the experiment
- **ID-NM-18 One mode per campaign.** Alternate `GENERATED` and `CHOSEN` campaigns in the alpha. The number of campaigns needed is unknown; at alpha audience sizes, treat the result as qualitative.
- **Measures**, aggregates only (Q-MOD-9 (5)): the share of new commanders who send a second sim command; the share who use `!callsign`, and time to first pick; `!me` per new commander in their first 10 min (a confusion proxy); auto-rejects and revokes by reason. "Who am I" messages are ordinary chat, which is ignored (COMMAND-CATALOG CC-4) and not logged (CHAT-GATEWAY GW-10), so they come only from mods' manual notes.
- **What exists today: none of it.** The balance harness (`tools/balance`) has no model of viewer confusion. There is no metrics code in `services/sim/src` (OPS-ADMIN §2 lists planned metrics, including rejects by reason), and `nexus.persistence` and `nexus.commands` are empty packages. The measures need the identity store (NX-200), the command log and the `!callsign` handler first.

### 7.8 Security review notes (before CHOSEN or DISPLAY ships)
Check: hostile names on stream and on the site (NX-516); slurs split across `-`; confusables inside ASCII; impersonation of the broadcaster, staff and other players; a mass-join raid filling names faster than review; real names in display names (doxxing) in DISPLAY, where the viewer did not ask; reuse of a tombstoned or revoked name; the moderation service down (fail closed); TTS reading names (SEC-MOD-2). The PR runs the `security-review` skill (CLAUDE.md: chat ingestion and identity).

### 7.9 Failure modes
| Failure | Behaviour |
|---|---|
| Raid of slur names in CHOSEN | Automatic checks reject most; staff revoke the rest (ID-NM-17) and extend the denylist; mode back to `GENERATED` from the next campaign |
| Moderation provider down | Every request stays unapproved; generated callsigns show |
| Two viewers want one name | First approved wins; the other gets `CALLSIGN_TAKEN` |
| Restart mid-campaign with a new mode | Not allowed (ID-NM-2); how it is refused is PROPOSED (e.g. the runtime keeps the campaign's logged mode until the campaign ends) |

### 7.10 Test plan
| Req | Test |
|---|---|
| ID-NM-1, 4 | Runtime schema test: default `GENERATED`; an unimplemented value fails startup |
| ID-NM-3 | Switching mode keeps every `CUSTOM` and `TOMBSTONE` callsign |
| ID-NM-5, 8 | CHOSEN: `!callsign` before any mission is accepted; the first pick has no cooldown, a second within 30 days gets `CALLSIGN_COOLDOWN`. GENERATED: before a mission gets `NO_COMPLETED_MISSION` |
| ID-NM-6, 12 | Table and `hypothesis` tests: reserved words, `WORD-NN`, `X-`, node names, staff names and their ASCII and Unicode lookalikes are rejected |
| ID-NM-9..11 | DISPLAY: derivation table (spaces, dots, non-ASCII, over 12, collisions with no suffix); a platform rename changes nothing |
| ID-NM-16 | Moderation error: generated callsign kept, no approval |
| §7.5 | Schema check: no `display_name` in `wire/` (CONTRACTS §10), extended to `events/` |

### 7.11 Open questions for the owner
- **Q1 Approval.** (a) Auto-approve on the automatic pipeline, review after (recommended, ID-NM-15); (b) staff pre-approve every name.
- **Q2 DISPLAY at all?** (a) Specify it, ship only CHOSEN in the first experiment (recommended: CHOSEN already lets a viewer type their own nickname, without the consent and impersonation cost); (b) ship both; (c) replace DISPLAY with `!callsign me`, which derives from the display name only when the viewer asks.
- **Q3 Cooldown in CHOSEN.** (a) First pick free, then one per 30 days (recommended, ID-NM-8); (b) no limit during the experiment; (c) today's limit.
- **Q4 Key layer.** (a) Runtime key, changed between campaigns (recommended, ID-NM-1); (b) balance key, so the mode is inside each campaign's `config_hash`.
- **Q5 Freed names.** This spec does not yet say whether a tombstoned or revoked name can be claimed again. (a) Never reusable (recommended: stops impersonation of a departed player); (b) reusable after a hold period.

## 8. Open questions
- Decided and folded in (2026-10-18): Q-ALN-12 (ID-PREF-1), Q-ALN-24 (`!forget` while paused, §5), Q-ALN-26 (§6), Q-ALN-28 (opt-out wins on merge, §4, §6), Q-ALN-29 (`REDACTED-<tag>`, §5), Q-DM-2, Q-PROD-2 (Kick optional, §4).
- §7 (name modes, Draft): open questions in §7.11.
