# discord-setup

Owner-run setup for the community Discord server. Spec: [DISCORD-SERVER-SETUP](../../docs/specs/DISCORD-SERVER-SETUP.md) (Approved). Tracker: NX-354.

It creates or updates the roles, categories, channels and permission overwrites in [blueprint.json](blueprint.json). It **never** deletes anything, kicks or bans anyone, sends a message or touches existing members. Python standard library only. The bot token stays on your computer, in one environment variable, and is never printed or stored. **Do not paste a token into a chat, an issue, a pull request or a file.**

The API version, permission values, channel and overwrite type numbers and the invite flow were checked against Discord's developer docs (docs.discord.com/developers) on 2026-10-19. Portal screen names that are not in those docs stay marked [UNVERIFIED]. The dry run prints every permission as a name and a hex value so you can check them against Discord's own table.

## Step by step

Total time: about 20 minutes. Keep one terminal open on your Mac (Terminal app, zsh) for the whole thing. Everything marked [UNVERIFIED] is a Discord screen or label written from memory, so a name may differ slightly: follow what you see and tell the assistant if a step does not match.

**Before you start:** open a terminal in the `operation-nexus` folder and run `git pull` so you have the latest script. You need Python 3 (`python3 --version` should print a version).

### Part 1: look at the plan (no Discord, no token)

1. Run `python3 tools/discord-setup/setup.py --show-blueprint`.
2. You should see about 16 lines starting with `WOULD:` (3 roles, 5 categories, 9 channels, each with its permissions) and the last line `Dry run only: nothing was sent anywhere.` That is the whole plan. The same layout is in [DISCORD-SERVER-SETUP §5](../../docs/specs/DISCORD-SERVER-SETUP.md). To change it, edit [blueprint.json](blueprint.json) first.

### Part 2: make a throwaway bot (Discord website, about 5 minutes)

3. Go to https://discord.com/developers/applications and sign in with the account that owns `hiveplex-community`. Click **New Application** [UNVERIFIED label], name it `hiveplex-setup-throwaway`, and accept the terms. Do **not** reuse the `hiveplex` application.
4. Open the **Bot** page in the left menu. Under **Token** click **Reset Token**, confirm, then copy it (Discord's own tutorial describes this step). This is the bot token. Treat it like a password: do not paste it into a chat, an issue, a pull request, a note or a file.
5. Put the token into your terminal without it landing in your shell history. In zsh (the Mac default) type this, press Enter, paste the token (nothing shows as you paste) and press Enter again:

   `read -rs "DISCORD_BOT_TOKEN?Paste token: "; export DISCORD_BOT_TOKEN`

   (In bash the form is `read -rsp "Paste token: " DISCORD_BOT_TOKEN; export DISCORD_BOT_TOKEN`.)
6. Invite the bot to the server. **You do not need a redirect URI** for this: that box on the OAuth2 page is only for apps that log users in. A bot invite needs just the `bot` scope. Use one of these:
   - **Install link (easiest).** Open **Installation** in the left menu. Under **Installation Contexts** make sure **Guild Install** is ticked. Under **Install Link** choose **Discord Provided Link**. In **Default Install Settings**, for **Guild Install**, add the scope **bot**, then in the **Permissions** menu tick exactly the permissions the script lists in step 2 under "The bot must hold these permissions" (Manage Channels, Manage Roles, View Channels, Send Messages, Manage Messages, Embed Links, Attach Files, Read Message History, Add Reactions, Moderate Members). Copy the **Install Link**, open it in your browser, choose **Add to server**, pick `hiveplex-community` and authorize.
   - **Or build the link yourself:** `https://discord.com/oauth2/authorize?client_id=<APPLICATION ID>&scope=bot&permissions=1099780189264` (the number is what the script prints as `= 0x1001001ec50`; the application ID is on the **General Information** page [UNVERIFIED label]).

   Why the extra permissions: Discord only lets a bot give a role, or allow or deny in a channel, permissions the bot holds itself (Discord docs: Create Guild Channel, Permission Hierarchy). If you skip one, the script stops with `Missing Permissions`. The bot then shows in the member list, offline. That is expected: the script talks to Discord's web interface and never runs a bot.
7. Find the server ID. In Discord open **User Settings**, then **Advanced**, and switch on **Developer Mode** [UNVERIFIED]. Right-click the server icon and choose **Copy Server ID**.

### Part 3: dry run against the real server (changes nothing)

8. Run `python3 tools/discord-setup/setup.py --guild <paste the server id>`.
9. Read the output. It starts with `Server: hiveplex-community` (check that is the right server), then the same `WOULD:` lines (or fewer, if parts of the layout already exist), and ends with `N change(s) planned; nothing was written (dry run).` Nothing was written. If you see `error:`, see the table below.

### Part 4: apply (this creates things)

10. Run `python3 tools/discord-setup/setup.py --guild <server id> --apply --confirm-guild-name hiveplex-community`.
11. You should see `Server: hiveplex-community`, then `DO:` lines, and finally `N change(s) made.` In Discord you now have the roles, categories and channels.
12. Run the same command again. It should end with `0 change(s)`: nothing left to do.

### Part 5: clean up (do this the same day)

13. In Discord, kick the bot from the server (right-click its name in the member list). In the developer portal, delete the throwaway application or at least click **Reset Token**. In the terminal run `unset DISCORD_BOT_TOKEN` and close the terminal window.

### Part 6: the parts you do by hand

Follow [Set by hand](#set-by-hand-the-script-does-not-touch-these) below, then do the final check in step 14.

14. **Test with a second account** (a spare account or a friend) before sharing the invite widely: a new member should see only START HERE, must not see STAFF, and should end up with the `Operator` role after the first-screen step.

## If something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| `error: need --guild and the DISCORD_BOT_TOKEN environment variable` | The token variable is empty in this terminal window, or `--guild` is missing | Repeat step 5 in the same window and check the command includes `--guild <id>` |
| `error: Discord returned 401 ...` | Wrong or reset token | Reset the token in the portal and repeat steps 4 and 5 |
| `error: Discord returned 403 ...` or the message `Missing Permissions` | The bot is not in the server, or it lacks a permission the script is trying to give or set (Discord only allows a bot to hand out permissions it has itself) | Check the bot is in the member list and that its role has every permission in step 6's list (server settings, then Roles, the bot's role). As a last resort give that role **Administrator** for this run only and remove it in step 13 |
| `error: Discord returned 404 ...` | Wrong server ID | Repeat step 7 and copy the **server** ID, not a channel or user ID |
| `error: --confirm-guild-name must be exactly the server name, '...'` | The name after `--confirm-guild-name` is not the real server name | Use the name in quotes in that error, exactly |
| Discord shows **Integration requires code grant** when you open the invite link (step 6) | The application has the bot option that requires a full OAuth2 code grant switched on (Discord's application setting `bot_require_code_grant`: the bot then only joins after a full login flow, which is why the page also asks for a redirect URI) | Open the application's **Bot** page, switch **off** the option named like **Requires OAuth2 Code Grant** [UNVERIFIED label], save, and open the invite link again. You do not need a redirect URI |
| It stopped halfway | Some things were created, the rest were not | Run the same `--apply` command again; the script reuses what exists |
| Nothing makes sense | Stop here | Do not keep retrying. Copy the output (it never contains the token), remove the token from your terminal with `unset DISCORD_BOT_TOKEN`, and show it to the assistant |

## Doing it by hand instead

The script is optional. The layout is small enough to build by hand in about 30 to 45 minutes: create the three roles, five categories and nine channels from the table in [DISCORD-SERVER-SETUP §5](../../docs/specs/DISCORD-SERVER-SETUP.md), then set each category's permissions as the dry run prints them. The part people get wrong by hand is permissions: make sure `@everyone` cannot **View Channel** on every category except START HERE, and that `Operator` cannot see STAFF. The script exists to make those permissions exact and repeatable, and the second run proves nothing drifted. By hand, repeat the test in step 14 instead.

## Set by hand (the script does not touch these)

Community features, rules screening, onboarding (the click-through step that gives the `Operator` role), default notifications (suggested: mentions only), the temporary-membership invite, 2FA for staff, and the welcome and rules text. The approved copy is in the private vault (`marketing/drafts/`, MKT-0009 and MKT-0010). You can change the text in Discord at any time; tell the assistant, or update the vault copy, so the two stay in step.

## Tests

`python3 tools/discord-setup/tests/test_setup.py` (also run by `make check-python` and CI). They use a fake of Discord's HTTP layer: a dry run writes nothing, a second apply changes nothing, no delete, kick, ban or message call exists, the token never appears in output, and the blueprint keeps STAFF private.
