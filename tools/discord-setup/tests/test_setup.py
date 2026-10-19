"""Checks for tools/discord-setup/setup.py (docs/specs/DISCORD-SERVER-SETUP.md section 7).

Run: python3 tools/discord-setup/tests/test_setup.py   (or pytest tools/discord-setup/tests)
Uses a stateful fake of the Discord HTTP layer; nothing touches the network.
"""

import copy
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(HERE.parent))

import setup  # noqa: E402

BLUEPRINT = json.loads((HERE.parent / "blueprint.json").read_text(encoding="utf-8"))
TOKEN = "TEST-TOKEN-do-not-leak-0123456789"
GUILD = "900"
NAME = "hiveplex-community"


class FakeDiscord:
    """Roles, channels and permission overwrites with ids, over the transport signature."""

    def __init__(self) -> None:
        self.roles: list[dict] = [{"id": GUILD, "name": "@everyone", "permissions": "0"}]
        self.channels: list[dict] = []
        self.calls: list[tuple[str, str]] = []
        self.next_id = 1000
        self.rate_limit_once = False
        self.fail_with: int | None = None
        self.guild: dict = {"id": GUILD, "name": NAME, "features": ["NEWS"]}
        self.welcome: dict = {"enabled": False, "description": None, "welcome_channels": []}
        self.onboarding: dict = {
            "enabled": False,
            "default_channel_ids": [],
            "prompts": [],
            "mode": 0,
        }
        self.messages: dict[str, list[dict]] = {}
        self.bodies: list[dict] = []
        self.seed_on_enable = False
        self.missing_until_set = False  # Discord answers 404 until welcome/onboarding exist

    def _new_id(self) -> str:
        self.next_id += 1
        return str(self.next_id)

    def __call__(self, method, url, headers, body):
        path = url.split("/api/v10", 1)[1]
        self.calls.append((method, path))
        assert headers["Authorization"] == f"Bot {TOKEN}"
        if self.fail_with:
            return self.fail_with, {}, json.dumps({"message": "Missing Permissions"}).encode()
        if self.rate_limit_once and method != "GET":
            self.rate_limit_once = False
            return 429, {}, json.dumps({"retry_after": 2.5}).encode()
        data = json.loads(body) if body else {}
        self.bodies.append(data)
        extra = self._community_and_messages(method, path, data)
        if extra is not None:
            return extra
        if method == "GET" and path == f"/guilds/{GUILD}":
            return 200, {}, json.dumps(self.guild).encode()
        if method == "GET" and path == f"/guilds/{GUILD}/roles":
            return 200, {}, json.dumps(self.roles).encode()
        if method == "GET" and path == f"/guilds/{GUILD}/channels":
            return 200, {}, json.dumps(self.channels).encode()
        if method == "POST" and path == f"/guilds/{GUILD}/roles":
            role = {**data, "id": self._new_id()}
            self.roles.append(role)
            return 200, {}, json.dumps(role).encode()
        if method == "POST" and path == f"/guilds/{GUILD}/channels":
            chan = {**data, "id": self._new_id()}
            self.channels.append(chan)
            return 200, {}, json.dumps(chan).encode()
        if method == "PATCH" and path.startswith("/channels/"):
            chan = next(c for c in self.channels if c["id"] == path.rsplit("/", 1)[1])
            chan.update(data)
            return 200, {}, json.dumps(chan).encode()
        if method == "PATCH" and path.startswith(f"/guilds/{GUILD}/roles/"):
            role = next(r for r in self.roles if r["id"] == path.rsplit("/", 1)[1])
            role.update(data)
            return 200, {}, json.dumps(role).encode()
        raise AssertionError(f"unexpected call {method} {path}")

    def _community_and_messages(self, method, path, data):
        def ok(value):
            return 200, {}, json.dumps(value).encode()

        community_on = "COMMUNITY" in self.guild["features"]
        if method == "PATCH" and path == f"/guilds/{GUILD}":
            if "COMMUNITY" in data.get("features", []) and not (
                data.get("rules_channel_id") and data.get("public_updates_channel_id")
            ):
                return 400, {}, json.dumps({"message": "rules channel required"}).encode()
            if self.seed_on_enable and "COMMUNITY" in data.get("features", []) and not community_on:
                self.onboarding.update(
                    {
                        "default_channel_ids": ["888"],
                        "mode": 1,
                        "enabled": False,
                        "prompts": [
                            {
                                "id": "9",
                                "type": 0,
                                "title": "Seeded",
                                "single_select": False,
                                "required": False,
                                "in_onboarding": True,
                                "options": [
                                    {"id": "10", "title": "One", "role_ids": [], "channel_ids": []}
                                ],
                            }
                        ],
                    }
                )
                self.welcome.update(
                    {
                        "welcome_channels": [
                            {
                                "channel_id": "777",
                                "description": "seeded",
                                "emoji_id": None,
                                "emoji_name": "x",
                            }
                        ]
                    }
                )
            self.guild.update(data)
            return ok(self.guild)
        if path == f"/guilds/{GUILD}/welcome-screen" and method in ("GET", "PATCH"):
            if not community_on:
                return 403, {}, json.dumps({"message": "Missing Access"}).encode()
            if method == "GET" and self.missing_until_set:
                return 404, {}, json.dumps({"message": "Unknown Guild Welcome Screen"}).encode()
            if method == "PATCH":
                self.missing_until_set = False
                self.welcome.update(data)
            return ok({k: v for k, v in self.welcome.items() if k != "enabled"})
        if path == f"/guilds/{GUILD}/onboarding" and method in ("GET", "PUT"):
            if not community_on:
                return 403, {}, json.dumps({"message": "Missing Access"}).encode()
            if method == "PUT":
                for n, prompt in enumerate(data["prompts"]):
                    if not prompt.get("id"):  # Discord: every prompt and option needs an id
                        err = {
                            "prompts": {
                                str(n): {
                                    "id": {
                                        "_errors": [
                                            {
                                                "code": "BASE_TYPE_REQUIRED",
                                                "message": "This field is required",
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                        return (
                            400,
                            {},
                            json.dumps({"message": "Invalid Form Body", "errors": err}).encode(),
                        )
                    for option in prompt["options"]:
                        assert option.get("id"), "option without an id"
                        assert "emoji" not in option, "emoji object sent back to Discord"
                self.onboarding.update(data)
            return ok(self.onboarding)
        if method == "GET" and path == "/users/@me":
            return ok({"id": "42", "username": "setup-bot"})
        match = re.match(r"^/channels/([0-9]+)/messages(\?limit=[0-9]+|/([0-9]+))?$", path)
        if match:
            msgs = self.messages.setdefault(match.group(1), [])
            if method == "GET":
                return ok(list(reversed(msgs)))
            if method == "POST":
                msg = {"id": self._new_id(), "author": {"id": "42"}, "content": data["content"]}
                msgs.append(msg)
                return ok(msg)
            if method == "PATCH":
                msg = next(m for m in msgs if m["id"] == match.group(3))
                msg["content"] = data["content"]
                return ok(msg)
        return None

    def writes(self) -> list[tuple[str, str]]:
        return [c for c in self.calls if c[0] != "GET"]


def run(fake, *extra, bp_path=None):
    lines: list[str] = []
    argv = ["--guild", GUILD, *extra]
    if bp_path:
        argv += ["--blueprint", str(bp_path)]
    code = setup.main(argv, env={"DISCORD_BOT_TOKEN": TOKEN}, transport=fake, out=lines.append)
    return code, lines


def structure(fake):
    code, _ = run(fake, "--apply", "--confirm-guild-name", NAME)
    assert code == 0
    fake.calls.clear()
    fake.bodies.clear()


def community(fake, *extra, apply=True):
    args = ["--community", *extra]
    if apply:
        args += ["--apply", "--confirm-guild-name", NAME]
    return run(fake, *args)


def test_blueprint_is_valid_and_staff_is_private():
    setup.validate_blueprint(BLUEPRINT)
    cats = {c["name"]: c for c in BLUEPRINT["categories"]}
    assert {"START HERE", "ANNOUNCEMENTS", "COMMS", "FEEDBACK", "STAFF"} <= set(cats)
    deny = setup.PERMISSIONS["VIEW_CHANNEL"]
    for who in ("@everyone", "Operator"):
        names = cats["STAFF"]["overwrites"][who]["deny"]
        assert setup.perm_value(names) & deny
    # every channel sits in a category and is read-only or writable exactly as the spec table says
    start = setup.merged_overwrites(cats["START HERE"], cats["START HERE"]["channels"][0])
    assert start["@everyone"][1] & setup.PERMISSIONS["SEND_MESSAGES"]
    clips = next(c for c in cats["COMMS"]["channels"] if c["name"] == "clips-and-memes")
    allow, deny = setup.merged_overwrites(cats["COMMS"], clips)["Operator"]
    assert (
        allow & setup.PERMISSIONS["ATTACH_FILES"] and not deny & setup.PERMISSIONS["ATTACH_FILES"]
    )
    general = next(c for c in cats["COMMS"]["channels"] if c["name"] == "general")
    assert (
        setup.merged_overwrites(cats["COMMS"], general)["Operator"][1]
        & setup.PERMISSIONS["ATTACH_FILES"]
    )


def test_blueprint_validation_rejects_mistakes():
    for case, mutate in {
        "staff visible to operators": lambda b: b["categories"][-1]["overwrites"][
            "Operator"
        ].update(deny=[]),
        "duplicate channel": lambda b: b["categories"][1]["channels"].append({"name": "welcome"}),
        "unknown permission": lambda b: b["roles"][0]["permissions"].append("NOT_A_FLAG"),
        "unknown role": lambda b: b["categories"][1]["overwrites"].update(
            {"Ghost": {"allow": [], "deny": []}}
        ),
    }.items():
        broken = copy.deepcopy(BLUEPRINT)
        mutate(broken)
        try:
            setup.validate_blueprint(broken)
        except setup.SetupError:
            continue
        raise AssertionError(f"validation accepted: {case}")


def test_show_blueprint_needs_no_token_and_no_network():
    lines: list[str] = []

    def boom(*_a):
        raise AssertionError("network used")

    assert setup.main(["--show-blueprint"], env={}, transport=boom, out=lines.append) == 0
    assert any("create role Operator" in line for line in lines)
    assert any("create channel welcome" in line for line in lines)


def test_bot_needs_every_permission_the_blueprint_uses():
    needed = setup.bot_needs(BLUEPRINT)
    for role in BLUEPRINT["roles"]:
        assert needed & setup.perm_value(role["permissions"]) == setup.perm_value(
            role["permissions"]
        )
    for cat in BLUEPRINT["categories"]:
        for perms in cat["overwrites"].values():
            used = setup.perm_value(perms["allow"] + perms["deny"])
            assert needed & used == used
    assert (
        needed & setup.PERMISSIONS["MANAGE_ROLES"] and needed & setup.PERMISSIONS["MANAGE_CHANNELS"]
    )
    lines: list[str] = []
    setup.main(["--show-blueprint"], env={}, out=lines.append)
    assert any(f"{needed:#x}" in line and "must hold" in line for line in lines)


def test_dry_run_makes_no_write_calls():
    fake = FakeDiscord()
    code, lines = run(fake)
    assert code == 0
    assert fake.writes() == []
    assert any("WOULD: create role Operator" in line for line in lines)
    assert "dry run" in lines[-1]


def test_apply_creates_everything_and_a_second_run_changes_nothing():
    fake = FakeDiscord()
    code, _ = run(fake, "--apply", "--confirm-guild-name", NAME)
    assert code == 0
    names = {c["name"] for c in fake.channels}
    assert {
        "welcome",
        "rules",
        "devlog",
        "general",
        "clips-and-memes",
        "feedback",
        "bug-reports",
        "mod-chat",
        "mod-log",
        "START HERE",
        "STAFF",
    } <= names
    assert {r["name"] for r in fake.roles} >= {"Operator", "Staff", "Bot"}
    fake.calls.clear()
    code, lines = run(fake, "--apply", "--confirm-guild-name", NAME)
    assert code == 0 and fake.writes() == [], fake.writes()
    assert lines[-1].startswith("0 change(s)")
    # the STAFF channels really are hidden from @everyone and the Operator role in the fake's state
    staff = next(c for c in fake.channels if c["name"] == "mod-chat")
    operator = next(r["id"] for r in fake.roles if r["name"] == "Operator")
    view = setup.PERMISSIONS["VIEW_CHANNEL"]
    ow = {o["id"]: int(o["deny"]) for o in staff["permission_overwrites"]}
    assert ow[GUILD] & view and ow[operator] & view


def test_drift_is_repaired_and_unmanaged_overwrites_are_kept():
    fake = FakeDiscord()
    run(fake, "--apply", "--confirm-guild-name", NAME)
    chan = next(c for c in fake.channels if c["name"] == "general")
    chan["permission_overwrites"].append(
        {"id": "555", "type": 1, "allow": "1", "deny": "0"}
    )  # a member
    chan["permission_overwrites"][0]["allow"] = str(setup.PERMISSIONS["MANAGE_MESSAGES"])  # drift
    fake.calls.clear()
    code, _ = run(fake, "--apply", "--confirm-guild-name", NAME)
    assert code == 0
    assert [w[0] for w in fake.writes()] == ["PATCH"]
    assert any(o["id"] == "555" for o in chan["permission_overwrites"])


def test_only_get_post_patch_and_nothing_about_members_bans_or_messages():
    fake = FakeDiscord()
    run(fake, "--apply", "--confirm-guild-name", NAME)
    assert {m for m, _ in fake.calls} <= {"GET", "POST", "PATCH"}
    assert not any(re.search(r"/(members|bans|messages|users)", p) for _, p in fake.calls)
    api = setup.Api(TOKEN, fake)
    for verb in ("DELETE", "PUT"):
        try:
            api.call(verb, f"/guilds/{GUILD}/members/1")
        except setup.SetupError:
            continue
        raise AssertionError(f"{verb} allowed")


def test_wrong_server_name_stops_before_any_write():
    fake = FakeDiscord()
    code, _ = run(fake, "--apply", "--confirm-guild-name", "some-other-server")
    assert code == 1 and fake.writes() == []
    code, _ = run(fake, "--apply")
    assert code == 1 and fake.writes() == []


def test_rate_limit_waits_and_retries_then_errors_stop():
    fake = FakeDiscord()
    fake.rate_limit_once = True
    waits: list[float] = []
    api = setup.Api(TOKEN, fake, sleep=waits.append)
    api.call("POST", f"/guilds/{GUILD}/roles", {"name": "X"})
    assert waits == [2.5]
    fake.fail_with = 403
    try:
        api.call("GET", f"/guilds/{GUILD}")
    except setup.SetupError as err:
        assert "403" in str(err) and "Missing Permissions" in str(err) and TOKEN not in str(err)
    else:
        raise AssertionError("an HTTP error did not stop the run")


def test_the_token_never_appears_in_output_or_in_the_repo():
    fake = FakeDiscord()
    code, lines = run(fake, "--apply", "--confirm-guild-name", NAME)
    assert code == 0 and not any(TOKEN in line for line in lines)
    fake.fail_with = 403
    code, _ = run(fake)
    assert code == 1
    pattern = re.compile(r"[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,}")
    for path in HERE.parent.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".md"}:
            assert not pattern.search(path.read_text(encoding="utf-8")), (
                f"token-like text in {path}"
            )


def test_open_layout_meets_discords_onboarding_constraints():
    readable, writable = setup.everyone_access(BLUEPRINT)
    default = BLUEPRINT["community"]["onboarding"]["default_channels"]
    assert len(default) >= 7 and set(default) <= set(readable)
    assert len(set(default) & set(writable)) >= 5
    assert not {"mod-chat", "mod-log"} & set(readable)  # STAFF stays private
    for case, mutate in {
        "too few writable": lambda b: b["categories"][2]["overwrites"]["@everyone"]["deny"].append(
            "SEND_MESSAGES"
        ),
        "staff channel as default": lambda b: b["community"]["onboarding"][
            "default_channels"
        ].append("mod-chat"),
        "unknown rules channel": lambda b: b["community"].update(rules_channel="nope"),
        "bad verification level": lambda b: b["community"].update(verification_level=9),
        "administrator in the blueprint": lambda b: b["roles"][0]["permissions"].append(
            "ADMINISTRATOR"
        ),
    }.items():
        broken = copy.deepcopy(BLUEPRINT)
        mutate(broken)
        try:
            setup.validate_blueprint(broken)
        except setup.SetupError:
            continue
        raise AssertionError(f"validation accepted: {case}")


def test_only_the_listed_requests_exist():
    api = setup.Api(TOKEN, FakeDiscord())
    for method, path in (
        ("DELETE", f"/guilds/{GUILD}/channels"),
        ("DELETE", "/channels/1"),
        ("PUT", f"/guilds/{GUILD}/members/1"),
        ("PUT", f"/guilds/{GUILD}/bans/1"),
        ("POST", f"/guilds/{GUILD}/members/1/roles/2"),
        ("PATCH", f"/guilds/{GUILD}/members/1"),
        ("POST", "/users/@me/channels"),
        ("GET", f"/guilds/{GUILD}/members"),
        ("GET", "/channels/1/messages"),
        ("GET", "/channels/x/messages?limit=5"),
    ):
        try:
            api.call(method, path)
        except setup.SetupError as err:
            assert "not allowed" in str(err)
        else:
            raise AssertionError(f"{method} {path} was allowed")


def test_community_stage_needs_the_structure_first():
    fake = FakeDiscord()
    code, _ = community(fake)
    assert code == 1 and fake.writes() == []


def test_community_dry_run_writes_nothing_then_apply_then_second_run_changes_nothing():
    fake = FakeDiscord()
    structure(fake)
    code, lines = community(fake, apply=False)
    assert code == 0 and fake.writes() == []
    assert any("Administrator" in line for line in lines)
    assert lines[-1].startswith("3 change(s) planned")
    code, lines = community(fake)
    assert code == 0 and lines[-1].startswith("3 change(s) made")
    assert [w[0] for w in fake.writes()] == ["PATCH", "PATCH", "PUT"]
    ids = {c["name"]: c["id"] for c in fake.channels}
    assert "COMMUNITY" in fake.guild["features"] and "NEWS" in fake.guild["features"]
    assert fake.guild["rules_channel_id"] == ids["rules"]
    assert fake.guild["public_updates_channel_id"] == ids["mod-log"]
    assert fake.guild["explicit_content_filter"] == 2
    assert fake.guild["default_message_notifications"] == 1
    assert fake.welcome["enabled"] and len(fake.welcome["welcome_channels"]) == 4
    operator = next(r["id"] for r in fake.roles if r["name"] == "Operator")
    assert fake.onboarding["enabled"] and len(fake.onboarding["default_channel_ids"]) == 8
    (prompt,) = fake.onboarding["prompts"]
    assert prompt["required"] and prompt["options"][0]["role_ids"] == [operator]
    fake.calls.clear()
    code, lines = community(fake)
    assert code == 0 and fake.writes() == [] and lines[-1].startswith("0 change(s)")


def test_community_keeps_existing_features_prompts_and_default_channels():
    fake = FakeDiscord()
    structure(fake)
    fake.guild["features"] = ["COMMUNITY", "NEWS"]
    fake.welcome = {"enabled": True, "description": "old", "welcome_channels": []}
    fake.onboarding = {
        "enabled": True,
        "mode": 0,
        "default_channel_ids": ["777"],
        "prompts": [
            {
                "id": "5",
                "type": 0,
                "title": "The owner's own prompt",
                "single_select": False,
                "required": False,
                "in_onboarding": True,
                "options": [
                    {
                        "id": "6",
                        "title": "A",
                        "role_ids": [],
                        "channel_ids": [],
                        "emoji": {"id": None, "name": "x", "animated": False},
                    }
                ],
            }
        ],
    }
    code, _ = community(fake)
    assert code == 0
    titles = [p["title"] for p in fake.onboarding["prompts"]]
    assert titles == ["The owner's own prompt", "Ready to join in?"]
    assert fake.onboarding["default_channel_ids"][0] == "777"
    assert len(fake.onboarding["default_channel_ids"]) == 9
    assert fake.guild["features"] == ["COMMUNITY", "NEWS"]


def test_skip_onboarding_and_flag_mistakes():
    fake = FakeDiscord()
    structure(fake)
    code, _ = community(fake, "--skip-onboarding")
    assert code == 0 and not any(m == "PUT" for m, _ in fake.writes())
    for argv in (["--post-text"], ["--skip-onboarding"], ["--community", "--post-text"]):
        fake.calls.clear()
        code, _ = run(fake, *argv, "--apply", "--confirm-guild-name", NAME)
        assert code == 1 and fake.writes() == []


def test_post_text_posts_edits_and_never_duplicates_or_prints_the_text(tmp_path=None):
    import tempfile

    fake = FakeDiscord()
    structure(fake)
    community(fake)
    welcome_text = "WELCOME-TEXT-" + "w" * 30
    rules_text = "RULES-TEXT-" + "r" * 30
    with tempfile.TemporaryDirectory() as tmp:
        wf, rf = Path(tmp) / "w.txt", Path(tmp) / "r.txt"
        wf.write_text(welcome_text, encoding="utf-8")
        rf.write_text(rules_text, encoding="utf-8")
        files = ["--post-text", "--welcome-file", str(wf), "--rules-file", str(rf)]
        fake.calls.clear()
        code, lines = community(fake, *files, apply=False)
        assert code == 0 and fake.writes() == []
        code, lines = community(fake, *files)
        assert code == 0 and [m for m, _ in fake.writes()] == ["POST", "POST"]
        assert not any(welcome_text in line or rules_text in line for line in lines)
        assert all(
            b.get("allowed_mentions") == {"parse": []} for b in fake.bodies if "content" in b
        )
        fake.calls.clear()
        code, _ = community(fake, *files)
        assert code == 0 and fake.writes() == []
        rf.write_text("changed rules", encoding="utf-8")
        code, _ = community(fake, *files)
        assert [m for m, _ in fake.writes()] == ["PATCH"]
        rules_id = next(c["id"] for c in fake.channels if c["name"] == "rules")
        assert [m["content"] for m in fake.messages[rules_id]] == ["changed rules"]
        wf.write_text("x" * 2001, encoding="utf-8")
        code, _ = community(fake, *files)
        assert code == 1
        wf.write_text("", encoding="utf-8")
        code, _ = community(fake, *files)
        assert code == 1
        code, _ = community(fake, "--post-text", "--welcome-file", str(wf))
        assert code == 1


def test_a_vault_draft_is_posted_only_when_approved_and_without_its_notes():
    import tempfile

    draft = (
        "---\nid: MKT-0009\nstatus: {status}\n---\n\nWelcome to Hiveplex.\n\nSecond paragraph.\n\n"
        "[NOTE: internal, not copy to post.]\n[HOLD: also internal]\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "d.md"
        path.write_text(draft.format(status="APPROVED"), encoding="utf-8")
        assert (
            setup.read_text_file(str(path), "welcome")
            == "Welcome to Hiveplex.\n\nSecond paragraph."
        )
        for status in ("DRAFT", "REJECTED", ""):
            path.write_text(draft.format(status=status), encoding="utf-8")
            try:
                setup.read_text_file(str(path), "welcome")
            except setup.SetupError as err:
                assert "not APPROVED" in str(err)
            else:
                raise AssertionError(f"posted a {status or 'status-less'} draft")
        path.write_text("---\nstatus: APPROVED\nno end", encoding="utf-8")
        try:
            setup.read_text_file(str(path), "welcome")
        except setup.SetupError:
            pass
        else:
            raise AssertionError("accepted front matter that never ends")
        path.write_text("plain text\n[NOTE: drop me]\n", encoding="utf-8")
        assert setup.read_text_file(str(path), "rules") == "plain text"


def test_what_discord_seeds_or_the_owner_set_survives_the_first_apply():
    fake = FakeDiscord()
    structure(fake)
    fake.seed_on_enable = True
    fake.guild["verification_level"] = 4  # stricter than the blueprint: never lowered
    fake.guild["explicit_content_filter"] = 2
    code, _ = community(fake)
    assert code == 0
    assert fake.guild["verification_level"] == 4
    assert fake.onboarding["mode"] == 1  # the existing mode is kept
    assert "888" in fake.onboarding["default_channel_ids"]
    titles = [p["title"] for p in fake.onboarding["prompts"]]
    assert titles == ["Seeded", "Ready to join in?"]
    assert [c["channel_id"] for c in fake.welcome["welcome_channels"]][-1] == "777"
    assert len(fake.welcome["welcome_channels"]) == 5  # ours (4) + the one already there
    fake.calls.clear()
    code, _ = community(fake)
    assert code == 0 and fake.writes() == []


def test_extra_options_in_our_prompt_are_kept():
    fake = FakeDiscord()
    structure(fake)
    community(fake)
    (prompt,) = fake.onboarding["prompts"]
    prompt["options"].append(
        {"id": "77", "title": "Owner added", "role_ids": [], "channel_ids": []}
    )
    prompt["options"][0]["title"] = "changed by the owner"  # drift in our own option
    fake.calls.clear()
    code, _ = community(fake)
    assert code == 0 and [m for m, _ in fake.writes()] == ["PUT"]
    titles = [o["title"] for o in fake.onboarding["prompts"][0]["options"]]
    assert titles == ["I read the rules", "Owner added"]


def test_front_matter_tricks_cannot_get_a_draft_posted():
    import tempfile

    cases = {
        "bom and draft": "\ufeff---\nid: MKT-1\nstatus: DRAFT\n---\nbody\n",
        "leading blank line, draft": "\n\n---\nid: MKT-1\nstatus: DRAFT\n---\nbody\n",
        "two status lines": "---\nstatus: APPROVED\nstatus: DRAFT\n---\nbody\n",
        "status line without the fences": "id: MKT-1\nstatus: DRAFT\n\nbody\n",
        "no status": "---\nid: MKT-1\n---\nbody\n",
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in cases.items():
            path = Path(tmp) / "d.md"
            path.write_text(text, encoding="utf-8")
            try:
                setup.read_text_file(str(path), "welcome")
            except setup.SetupError:
                continue
            raise AssertionError(f"posted: {name}")
        path.write_text("\ufeff\n---\nstatus: APPROVED\n---\nok\n", encoding="utf-8")
        assert setup.read_text_file(str(path), "welcome") == "ok"


def test_odd_input_and_network_trouble_stop_cleanly():
    api = setup.Api(TOKEN, FakeDiscord())
    for path in ("/channels/1/messages?limit=5\n", "/channels/1\n", f"/guilds/{GUILD}\n"):
        try:
            api.call("GET" if "messages" in path else "PATCH", path)
        except setup.SetupError:
            continue
        raise AssertionError(f"allowed {path!r}")
    fake = FakeDiscord()
    code, _ = run(fake)
    assert code == 0
    lines: list[str] = []

    def down(*_a):
        raise OSError("network is down")

    code = setup.main(
        ["--guild", GUILD], env={"DISCORD_BOT_TOKEN": TOKEN}, transport=down, out=lines.append
    )
    assert code == 1
    code = setup.main(
        ["--guild", "abc/../x"], env={"DISCORD_BOT_TOKEN": TOKEN}, transport=fake, out=lines.append
    )
    assert code == 1 and not any(TOKEN in line for line in lines)


def test_a_welcome_screen_that_does_not_exist_yet_is_created_not_an_error():
    fake = FakeDiscord()
    structure(fake)
    fake.missing_until_set = True  # the real server answered 404 Unknown Guild Welcome Screen
    code, lines = community(fake)
    assert code == 0, lines
    assert fake.welcome["enabled"] and len(fake.welcome["welcome_channels"]) == 4
    fake.calls.clear()
    code, _ = community(fake)
    assert code == 0 and fake.writes() == []
    # any other error on that read still stops the run
    fake2 = FakeDiscord()
    structure(fake2)
    fake2.guild["features"] = ["COMMUNITY"]
    fake2.fail_with = 403
    code, _ = community(fake2)
    assert code == 1


def test_a_400_shows_which_field_discord_refused():
    body = {
        "message": "Invalid Form Body",
        "code": 50035,
        "errors": {
            "prompts": {
                "0": {
                    "options": {"_errors": [{"code": "BASE_TYPE_MIN_LENGTH", "message": "too few"}]}
                }
            },
            "default_channel_ids": {"_errors": [{"code": "X", "message": "not enough"}]},
        },
    }
    text = setup.error_details(body["errors"])
    assert "prompts.0.options: BASE_TYPE_MIN_LENGTH too few" in text
    assert "default_channel_ids: X not enough" in text
    assert setup.error_details(None) == "" and setup.error_details({"a": 1}) == ""
    raw = json.dumps(body).encode()

    def refuse(method, url, headers, data):
        return 400, {}, raw

    try:
        setup.Api(TOKEN, refuse).call("GET", f"/guilds/{GUILD}")
    except setup.DiscordError as err:
        assert "Invalid Form Body" in str(err) and "BASE_TYPE_MIN_LENGTH" in str(err)
        assert err.status == 400 and TOKEN not in str(err)
    else:
        raise AssertionError("a 400 did not stop the run")


def test_new_onboarding_prompts_and_options_get_ids_and_the_welcome_screen_is_not_rewritten():
    a, b = setup.new_id(), setup.new_id()
    assert a != b and a.isdigit() and int(a) > 1 << 40
    fake = FakeDiscord()
    structure(fake)
    code, lines = community(fake)
    assert code == 0, lines
    (prompt,) = fake.onboarding["prompts"]
    assert prompt["id"] and prompt["options"][0]["id"]
    fake.calls.clear()
    code, lines = community(fake)  # Discord's welcome screen reply has no "enabled" field
    assert code == 0 and fake.writes() == [] and lines[-1].startswith("0 change(s)")


def test_bot_role_checks_explain_a_missing_permissions_refusal():
    roles = [
        {"id": "1", "name": "@everyone", "position": 0, "permissions": "0"},
        {"id": "2", "name": "Operator", "position": 3, "permissions": "0"},
        {
            "id": "3",
            "name": "setup-bot",
            "position": 1,
            "permissions": "8",
            "tags": {"bot_id": "42"},
        },
    ]
    text = " ".join(setup.diagnose_bot_roles(roles, "42", "Operator"))
    assert "'setup-bot' (position 1)" in text and "Administrator: yes" in text
    assert "not below the bot's role" in text and "Drag 'setup-bot' above 'Operator'" in text
    roles[2].update(position=5, permissions="0")
    text = " ".join(setup.diagnose_bot_roles(roles, "42", "Operator"))
    assert "Administrator: NO" in text and "not below" not in text
    assert "no role of its own" in " ".join(setup.diagnose_bot_roles(roles[:2], "42", "Operator"))
    # a 403 on the onboarding write carries the checks in the error text
    fake = FakeDiscord()
    structure(fake)
    fake.guild["features"] = ["COMMUNITY"]
    original = fake._community_and_messages

    def refuse_onboarding(method, path, data):
        if method == "PUT" and path.endswith("/onboarding"):
            return 403, {}, json.dumps({"message": "Missing Permissions"}).encode()
        return original(method, path, data)

    fake._community_and_messages = refuse_onboarding
    lines: list[str] = []
    errors: list[str] = []
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        code = setup.main(
            ["--guild", GUILD, "--community", "--apply", "--confirm-guild-name", NAME],
            env={"DISCORD_BOT_TOKEN": TOKEN},
            transport=fake,
            out=lines.append,
        )
    errors.append(buffer.getvalue())
    assert code == 1 and "Missing Permissions" in errors[0] and "no role of its own" in errors[0]
    assert any(line.startswith("check: ") for line in lines) and TOKEN not in errors[0]


def test_community_stops_on_a_discord_refusal_and_never_leaks_the_token():
    fake = FakeDiscord()
    structure(fake)
    fake.guild["features"] = []
    fake.channels = [c for c in fake.channels if c["name"] != "rules"]  # structure incomplete
    code, lines = community(fake)
    assert code == 1 and fake.writes() == []
    fake2 = FakeDiscord()
    structure(fake2)
    fake2.fail_with = 403
    code, lines = community(fake2)
    assert code == 1 and not any(TOKEN in line for line in lines)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ok")
