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
        if method == "GET" and path == f"/guilds/{GUILD}":
            return 200, {}, json.dumps({"id": GUILD, "name": NAME}).encode()
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

    def writes(self) -> list[tuple[str, str]]:
        return [c for c in self.calls if c[0] != "GET"]


def run(fake, *extra, bp_path=None):
    lines: list[str] = []
    argv = ["--guild", GUILD, *extra]
    if bp_path:
        argv += ["--blueprint", str(bp_path)]
    code = setup.main(argv, env={"DISCORD_BOT_TOKEN": TOKEN}, transport=fake, out=lines.append)
    return code, lines


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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("ok")
