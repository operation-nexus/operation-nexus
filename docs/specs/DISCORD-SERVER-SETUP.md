# SPEC: Discord community server setup

Status: Approved (owner, 2026-10-19) · Owner: owner · Tracker: NX-353, NX-354 · Related: Q-OPS-12, Q-MKT-9, BRAND-OPS (BO-1, BO-2), Q-AI-6

## 1. Purpose
Set up the community server `hiveplex-community` (invite `https://discord.gg/2sYjKYshSc`) with a clear first screen, a member role that new people earn by clicking through, and the starter channels, without ever putting a bot token in an agent session or in a repository.

## 2. Goals / Non-goals
Goals: a repeatable, reviewable setup; a safe default (dry run); the same result if run twice; no secrets in git or sessions; a blueprint the owner can read and change by pull request.
Non-goals: running any bot (Brand Ops and the War Briefing bot are separate, each with its own application and token, BO-1); moderation automation; the lore and private-tester areas (added when needed); the game-rank role mapping (pending NAMING-CONVENTIONS).

## 3. Requirements
- **DS-1** No agent session, repository file, log, issue or pull request may contain a bot token. The token is read from the environment variable `DISCORD_BOT_TOKEN` on the owner's own computer, is never printed, and is never written to a file.
- **DS-2** The setup uses a **throwaway** Discord developer application, not the `hiveplex` application and not Brand Ops' application. The owner deletes the application or resets its token after setup.
- **DS-3** The script MUST default to a dry run that prints what it would create or change and changes nothing. A change needs an explicit `--apply`.
- **DS-4** The script MUST be idempotent: roles, categories and channels are matched by exact name and reused; permission overwrites are set to the blueprint's values; a second run changes nothing.
- **DS-5** The script MUST only create or update the roles, categories, channels and permission overwrites in the blueprint. It MUST NOT delete anything, kick or ban anyone, send direct messages, or touch existing members' roles.
- **DS-6** The script MUST use only the standard library (AGENTS rule 8: no new dependency), respect rate limits (retry after the wait Discord asks for), and stop on the first unexpected error rather than continue.
- **DS-7** The bot is invited with only the permissions the script needs and is removed from the server afterward. Discord only lets a bot give a role, or allow or deny in a channel, permissions the bot holds itself (Discord docs, checked 2026-10-19: Create Guild Channel, Permission Hierarchy), so the needed set is manage roles, manage channels and every permission the blueprint uses; the dry run prints it (`The bot must hold these permissions`). If a run is still refused, the throwaway bot may be given Administrator for that run only and is removed straight after.
- **DS-8** START HERE (see §5) MUST make a new member read the rules and click to continue, and MUST end with the member holding the `Operator` role. Members who never click are expected to be removed by the invite's temporary-membership setting [UNVERIFIED: owner-reported setting; the Discord developer and help pages could not be read from this environment].
- **DS-9** The script sends no messages. Rules and welcome text are owner-approved copy in the owner's voice, kept in the vault (MKT-0009, MKT-0010); the owner puts it into Discord's own rules, onboarding and welcome features, or a channel, by hand, and may change it at any time (owner, 2026-10-19). The welcome text states the project's honest status and the AI-help line (Q-AI-6).
- **DS-10** The blueprint file lives in the repo, is validated by a test (names unique, every channel in a category, no empty permission set), and changes by pull request.

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
| ANNOUNCEMENTS | #devlog | Operator | nobody (read-only); bots post |
| COMMS | #general | Operator | Operator |
| COMMS | #clips-and-memes | Operator | Operator (files allowed here only) |
| FEEDBACK | #feedback | Operator | Operator |
| FEEDBACK | #bug-reports | Operator | Operator |
| STAFF | #mod-chat | Staff | Staff |
| STAFF | #mod-log | Staff | Staff |

Roles: `Operator` (member; the audience word, owner decision 2026-10-19), `Staff`, `Bot`. Everyone starts with no role and sees only START HERE. The `Operator` role is granted when the member completes the first-screen step. The preferred mechanism is Discord's own onboarding, configured by the owner in the server settings (a checklist is in the runbook); if it cannot assign the role, a reaction-role bot is a later, separate Brand Ops job.

Not set by the script, set by hand: Community features, rules screening, onboarding, default notifications (PROPOSED: mentions only), the temporary-membership invite, 2FA for staff. Rationale: these settings change what the server is, and the owner already knows the screens.

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
| DS-10 | Blueprint validation test |
| DS-8, permission mistakes | Manual test with a second account before the invite is shared |

## 8. Open questions
- Which onboarding setup assigns `Operator` (Discord onboarding versus a later reaction-role bot): the owner tests the onboarding option.
- Rank-to-role mapping and the lore and tester areas: later.
- Welcome and rules wording: approved by the owner on 2026-10-19 and editable by hand at any time.
