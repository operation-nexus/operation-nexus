# discord-setup

Owner-run setup for the community Discord server. Spec: [DISCORD-SERVER-SETUP](../../docs/specs/DISCORD-SERVER-SETUP.md) (Approved). Tracker: NX-354.

It creates or updates the roles, categories, channels and permission overwrites in [blueprint.json](blueprint.json). It **never** deletes anything, kicks or bans anyone, sends a message or touches existing members. Python standard library only. The bot token stays on your computer, in one environment variable, and is never printed or stored. **Do not paste a token into a chat, an issue, a pull request or a file.**

Discord's developer pages could not be read when this was written, so the API version, permission values and portal labels are from memory and marked UNVERIFIED in the code. The dry run prints every permission as a name and a hex value so you can check them against Discord's own table.

## Steps

1. **Preview offline** (no token, no network): `python3 tools/discord-setup/setup.py --show-blueprint`
2. **Make a throwaway application** in the Discord Developer Portal (not the `hiveplex` one, not Brand Ops'). Add a bot and copy its token into your shell only: `export DISCORD_BOT_TOKEN=...`
3. **Invite the bot** to `hiveplex-community` with Manage Roles, Manage Channels and View Channels. If the run is refused ("Missing Permissions") when setting permissions the bot does not itself hold, give the throwaway bot Administrator for the run only [UNVERIFIED Discord rule]; it is removed in step 6.
4. **Dry run against the real server** (turn on Developer Mode, right-click the server, Copy Server ID): `python3 tools/discord-setup/setup.py --guild <server id>`. Read the list. Nothing is written.
5. **Apply**: `python3 tools/discord-setup/setup.py --guild <server id> --apply --confirm-guild-name hiveplex-community`. Run it a second time: it should report `0 change(s)`.
6. **Clean up**: kick the bot from the server, delete the application (or reset its token), and `unset DISCORD_BOT_TOKEN`.
7. **Test with a second account** before you share the invite widely: a new member must see only START HERE, must not see STAFF, and must end up with the `Operator` role after the first-screen step.

## Set by hand (the script does not touch these)

Community features, rules screening, onboarding (the click-through step that gives the `Operator` role), default notifications (suggested: mentions only), the temporary-membership invite, 2FA for staff, and the welcome and rules text. The approved copy is in the private vault (`marketing/drafts/`, MKT-0009 and MKT-0010). You can change the text in Discord at any time; tell the assistant, or update the vault copy, so the two stay in step.

## Tests

`python3 tools/discord-setup/tests/test_setup.py` (also run by `make check-python` and CI). They use a fake of Discord's HTTP layer: a dry run writes nothing, a second apply changes nothing, no delete, kick, ban or message call exists, the token never appears in output, and the blueprint keeps STAFF private.
