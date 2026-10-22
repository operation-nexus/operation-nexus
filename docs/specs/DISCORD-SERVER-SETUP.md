# SPEC: Discord community server setup

Status: Approved (owner, 2026-10-19); amended 2026-10-19 by the owner's decisions on Community, onboarding and posted text (DS-5, DS-9, DS-11 to DS-14, section 5) · Owner: owner · Tracker: NX-353, NX-354 · Related: Q-OPS-12, Q-MKT-9, BRAND-OPS (BO-1, BO-2), Q-AI-6

## 1. Purpose
Set up the community server `hiveplex-community` (invite `https://discord.gg/mSaAD3GGHh`) with a clear first screen, a member role that new people earn by clicking through, and the starter channels, without ever putting a bot token in an agent session or in a repository.

## 2. Goals / Non-goals
Goals: a repeatable, reviewable setup; a safe default (dry run); the same result if run twice; no secrets in git or sessions; a blueprint the owner can read and change by pull request.
Non-goals: running any bot (Brand Ops and the War Briefing bot are separate, each with its own application and token, BO-1); moderation automation; the lore and private-tester areas (added when needed); the game-rank role mapping (pending NAMING-CONVENTIONS).

## 3. Requirements
- **DS-1** No agent session, repository file, log, issue or pull request may contain a bot token. The token is read from the environment variable `DISCORD_BOT_TOKEN` on the owner's own computer, is never printed, and is never written to a file.
- **DS-2** The setup uses a **throwaway** Discord developer application, not the `hiveplex` application and not Brand Ops' application. The owner deletes the application or resets its token after setup.
- **DS-3** The script MUST default to a dry run that prints what it would create or change and changes nothing. A change needs an explicit `--apply`.
- **DS-4** The script MUST be idempotent: roles, categories and channels are matched by exact name and reused; permission overwrites are set to the blueprint's values; a second run changes nothing.
- **DS-5** The script MUST only create or update the roles, categories, channels and permission overwrites in the blueprint and, in the separate community stage (DS-11), the server settings, welcome screen and onboarding listed there. It MUST NOT delete anything, kick or ban anyone, send direct messages, or touch existing members' roles.
- **DS-6** The script MUST use only the standard library (AGENTS rule 8: no new dependency), respect rate limits (retry after the wait Discord asks for), and stop on the first unexpected error rather than continue.
- **DS-7** The bot is invited with only the permissions the script needs and is removed from the server afterward. Discord only lets a bot give a role, or allow or deny in a channel, permissions the bot holds itself (Discord docs, checked 2026-10-19: Create Guild Channel, Permission Hierarchy), so the needed set is manage roles, manage channels and every permission the blueprint uses; the dry run prints it (`The bot must hold these permissions`). If a run is still refused, the throwaway bot may be given Administrator for that run only and is removed straight after.
- **DS-8** START HERE (see §5) MUST make a new member read the rules and click to continue, and MUST end with the member holding the `Operator` role. Members who never click are expected to be removed by the invite's temporary-membership setting [UNVERIFIED: owner-reported setting; the Discord developer and help pages could not be read from this environment].
- **DS-9** The welcome and rules text is owner-approved copy in the owner's voice, kept in the private vault (MKT-0009, MKT-0010) and never committed to this public repo. The only messages the script may send are those two, through DS-13; it sends no other message and no direct message. The owner may change the text in Discord at any time (owner, 2026-10-19). The welcome text states the project's honest status and the AI-help line (Q-AI-6).
- **DS-10** The blueprint file lives in the repo, is validated by a test (names unique, every channel in a category, no empty permission set), and changes by pull request.
- **DS-11** (owner decision, 2026-10-19) A separate stage, `--community`, with its own dry run and its own `--apply` and `--confirm-guild-name`, turns the server into a Community server: it adds `COMMUNITY` to the server's features (keeping the existing ones), sets the rules channel to #rules and the updates and safety-alerts channels to #mod-log, sets default notifications to mentions only, and sets the explicit content filter and verification level to the blueprint's value or higher (a stricter existing setting is never lowered), and sets the server description. Existing welcome-screen channels, onboarding prompts, options, mode and default channels are kept and added to (DS-12). Discord requires the `ADMINISTRATOR` permission to add or remove `COMMUNITY` (Discord docs: Modify Guild), so for this stage only the throwaway bot is given Administrator; DS-7's removal afterward still applies. Values come from the blueprint; Discord refuses settings that do not meet its Community requirements and the script then stops with Discord's message (DS-6).
- **DS-12** The community stage also sets the welcome screen (description and the channels it links) and the onboarding: the default channels, and one required prompt whose option assigns the `Operator` role (DS-8). Discord enforces, when onboarding is enabled, at least 7 default channels of which at least 5 allow `@everyone` to send messages (Discord docs: Modify Guild Onboarding), so the layout in section 5 meets that, and the blueprint test checks it. The exact shape of a prompt that only assigns a role is UNVERIFIED; the owner tests it with a second account (section 7).
- **DS-13** `--post-text` (community stage only) posts the welcome and rules text into #welcome and #rules, reading it from local files the owner passes (`--welcome-file`, `--rules-file`); a vault draft file is accepted directly only if its status is `APPROVED` or `POSTED`, and only its body is used with its internal `[NOTE ...]` and `[HOLD ...]` lines dropped. It is idempotent: a message by the bot with identical text is left alone, and a different one is edited, never duplicated, never deleted. The text is never printed in full in logs and never written to the repo. The bot needs Send Messages and Read Message History in those channels (it holds them, DS-7).
- **DS-14** All of DS-1 to DS-4 and DS-6 apply to the community stage unchanged: dry run by default, no token in output, idempotent, standard library only, stop on the first unexpected error.

## 4. Interfaces
- Command (NX-354, `tools/discord-setup/`): `DISCORD_BOT_TOKEN=... python3 tools/discord-setup/setup.py --guild <server id> [--apply]`.
- Blueprint: `tools/discord-setup/blueprint.json`. Runbook: `tools/discord-setup/README.md`.
- Extra safety beyond DS-3: `--apply` also needs `--confirm-guild-name` to equal the real server name, so a wrong server id stops before any write; `--show-blueprint` prints the plan with no token and no network.
- Discord REST calls: create and edit roles, channels and permission overwrites. Endpoints, API v10, permission values, channel and overwrite types, the Bot authorization header, the User-Agent format and the rate-limit response were checked against docs.discord.com/developers on 2026-10-19 (the developer pages are readable from the new docs.discord.com address); the script's tests use a fake of the HTTP layer.

## 5. Behavior
Starter layout (owner approved 2026-10-19):

| Category | Channel | Who sees it | Who can write |
|---|---|---|---|
| START HERE | #welcome | everyone | nobody (read-only) |
| START HERE | #rules | everyone | nobody (read-only) |
| ANNOUNCEMENTS | #devlog | everyone | nobody (read-only); bots and staff post |
| COMMS | #general | everyone | everyone |
| COMMS | #clips-and-memes | everyone | everyone (files allowed here only) |
| COMMS | #off-topic | everyone | everyone |
| FEEDBACK | #feedback | everyone | everyone |
| FEEDBACK | #bug-reports | everyone | everyone |
| STAFF | #mod-chat | Staff | Staff |
| STAFF | #mod-log | Staff | Staff |

"Everyone" means every member who has accepted the rules: Community's rules screening is the gate before anyone can see or write anything (owner decision, 2026-10-19: the layout is open, replacing the earlier "hidden until Operator" design, because Discord's onboarding needs 7 default channels of which 5 writable by @everyone, DS-12). The default channels are the eight non-staff channels above; the five writable ones are #general, #clips-and-memes, #off-topic, #feedback and #bug-reports.

Roles: `Operator` (member; the audience word, owner decision 2026-10-19), `Staff`, `Bot`. `Operator` is the member role, granted by the onboarding option (DS-12); it is also the base for rank roles later (see PROGRESSION section 8). If onboarding cannot assign the role, a reaction-role bot is a later, separate Brand Ops job.

The community stage (DS-11 to DS-13) now sets Community, the rules and updates channels, default notifications, the welcome screen, onboarding and the two messages. Still by hand: rules screening and the Community checklist screens Discord shows only in its own wizard, the temporary-membership invite, 2FA for staff and any change to server icon or banner.

## 6. Failure modes
| Failure | Effect | Handling |
|---|---|---|
| Token leaks (pasted into chat or a repo) | Someone can act as the bot | Reset the token in the developer portal at once; DS-1 forbids it |
| Script run against the wrong server | Roles and channels appear there | Dry run first; the server id is a required argument; owner checks the dry-run list |
| Rate limit | Slow run | Wait as asked, DS-6 |
| Role never granted | New members are removed or stay stuck | Test with a second account before sharing the invite widely |
| Permission mistake (everyone can see STAFF) | Private chat exposed | Test with a second account; the blueprint test checks STAFF is denied to everyone |

## 7. Test plan
| Req | Test |
|---|---|
| DS-1 | A repo check fails on strings that look like Discord tokens; the script never prints its environment |
| DS-3, DS-5 | Unit test with a fake HTTP layer: dry run makes no write calls; no delete, kick, ban or DM call exists |
| DS-4 | Run twice against the fake: the second run makes no write calls |
| DS-6 | Fake returns a rate-limit wait: the script waits and retries; fake returns an error: the script stops |
| DS-10 | Blueprint validation test, including: STAFF stays private; at least 7 default channels and at least 5 writable by @everyone (DS-12) |
| DS-11, DS-12, DS-14 | Fake HTTP layer: the community stage dry run writes nothing; apply makes the expected guild, welcome-screen and onboarding calls once and a second run makes none; existing features are kept; a Discord refusal stops the run |
| DS-13 | Fake: an identical message is left alone, a different one is edited, none duplicated or deleted; the text never appears in the output |
| DS-8, permission mistakes | Manual test with a second account before the invite is shared |

## 8. Open questions
- Which onboarding setup assigns `Operator` (Discord onboarding versus a later reaction-role bot): the owner tests the onboarding option.
- Rank-to-role mapping (Discord linked roles or a role-sync bot, needs account linking): proposed in PROGRESSION section 8; the lore and tester areas: later.
- Whether a role-only onboarding prompt is accepted by Discord, and the best verification level: found by the owner's second-account test.
- Welcome and rules wording: approved by the owner on 2026-10-19 and editable by hand at any time.
