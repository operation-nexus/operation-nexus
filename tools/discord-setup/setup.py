#!/usr/bin/env python3
"""Owner-run setup for the community Discord server (docs/specs/DISCORD-SERVER-SETUP.md).

Creates or updates the roles, categories, channels and permission overwrites in blueprint.json.
It never deletes, kicks, bans or sends messages, uses only the standard library, and defaults to a
dry run. The bot token is read from DISCORD_BOT_TOKEN and is never printed or stored.

  python3 setup.py --show-blueprint                      no network, no token
  DISCORD_BOT_TOKEN=... python3 setup.py --guild ID      dry run against the real server
  DISCORD_BOT_TOKEN=... python3 setup.py --guild ID --apply --confirm-guild-name NAME

Discord's developer pages could not be read when this was written (HTTP 403), so the API version,
endpoints, permission values and channel types below are from memory and marked UNVERIFIED. The dry
run prints every permission as a name and a hex value so the owner can check them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

API_BASE = "https://discord.com/api/v10"  # UNVERIFIED version
USER_AGENT = "DiscordBot (https://github.com/operation-nexus/operation-nexus, 0.1)"
EVERYONE = "@everyone"
CHANNEL_TEXT = 0  # UNVERIFIED
CHANNEL_CATEGORY = 4  # UNVERIFIED
OVERWRITE_ROLE = 0  # UNVERIFIED
MAX_RETRIES = 5
MAX_WAIT_SECONDS = 60.0

# Permission flag values, UNVERIFIED (from memory of Discord's permissions table).
PERMISSIONS: dict[str, int] = {
    "VIEW_CHANNEL": 1 << 10,
    "SEND_MESSAGES": 1 << 11,
    "MANAGE_MESSAGES": 1 << 13,
    "EMBED_LINKS": 1 << 14,
    "ATTACH_FILES": 1 << 15,
    "READ_MESSAGE_HISTORY": 1 << 16,
    "ADD_REACTIONS": 1 << 6,
    "MODERATE_MEMBERS": 1 << 40,
}

Json = dict[str, Any]
# transport(method, url, headers, body) -> (status, response headers, response body bytes)
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, dict[str, str], bytes]]


class SetupError(Exception):
    """A problem the owner can act on. Never contains the token."""


def perm_value(names: list[str]) -> int:
    value = 0
    for name in names:
        if name not in PERMISSIONS:
            raise SetupError(f"unknown permission name: {name}")
        value |= PERMISSIONS[name]
    return value


def perm_text(value: int) -> str:
    names = [n for n, bit in PERMISSIONS.items() if value & bit]
    return f"{'|'.join(names) or 'none'} = {value:#x}"


def validate_blueprint(bp: Json) -> None:
    """DS-10: names unique, permission names known, STAFF unreachable for everyone else."""
    roles = [r["name"] for r in bp["roles"]]
    cats = [c["name"] for c in bp["categories"]]
    chans = [ch["name"] for c in bp["categories"] for ch in c["channels"]]
    for label, names in (("role", roles), ("category", cats), ("channel", chans)):
        if len(names) != len(set(names)):
            raise SetupError(f"duplicate {label} names in the blueprint")
    known = set(roles) | {EVERYONE}
    for cat in bp["categories"]:
        if not cat.get("overwrites"):
            raise SetupError(f"category {cat['name']} has no permission overwrites")
        for ow in [cat["overwrites"], *[ch.get("overwrites", {}) for ch in cat["channels"]]]:
            for principal, perms in ow.items():
                if principal not in known:
                    raise SetupError(f"unknown role in overwrites: {principal}")
                perm_value(perms["allow"] + perms["deny"])
    for role in bp["roles"]:
        perm_value(role["permissions"])
    staff = next((c for c in bp["categories"] if c["name"] == "STAFF"), None)
    if staff is None:
        raise SetupError("the blueprint needs a STAFF category")
    for principal in (EVERYONE, "Operator"):
        if "VIEW_CHANNEL" not in staff["overwrites"].get(principal, {}).get("deny", []):
            raise SetupError(f"STAFF must deny VIEW_CHANNEL to {principal}")


def merged_overwrites(cat: Json, chan: Json) -> dict[str, tuple[int, int]]:
    """Category overwrites with the channel's own on top, as (allow, deny) per role name."""
    out: dict[str, tuple[int, int]] = {}
    for principal, perms in cat["overwrites"].items():
        out[principal] = (perm_value(perms["allow"]), perm_value(perms["deny"]))
    for principal, perms in chan.get("overwrites", {}).items():
        allow, deny = out.get(principal, (0, 0))
        extra_allow, extra_deny = perm_value(perms["allow"]), perm_value(perms["deny"])
        out[principal] = ((allow | extra_allow) & ~extra_deny, (deny | extra_deny) & ~extra_allow)
    return out


class Api:
    """Thin Discord REST client. Only GET, POST and PATCH exist here (DS-5)."""

    def __init__(
        self,
        token: str,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self._transport = transport or _urllib_transport
        self._sleep = sleep

    def call(self, method: str, path: str, body: Json | None = None) -> Any:
        if method not in ("GET", "POST", "PATCH"):
            raise SetupError(f"method not allowed: {method}")
        headers = {
            "Authorization": f"Bot {self._token}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }
        data = json.dumps(body).encode() if body is not None else None
        for _ in range(MAX_RETRIES):
            status, _hdrs, raw = self._transport(method, API_BASE + path, headers, data)
            if status == 429:
                wait = min(
                    float(json.loads(raw or b"{}").get("retry_after", 1.0)), MAX_WAIT_SECONDS
                )
                self._sleep(wait)
                continue
            if status >= 400:
                detail = ""
                try:
                    detail = str(json.loads(raw).get("message", ""))
                except ValueError:
                    pass
                raise SetupError(f"Discord returned {status} for {method} {path}: {detail}")
            return json.loads(raw) if raw else None
        raise SetupError(f"still rate limited after {MAX_RETRIES} tries: {method} {path}")


def _urllib_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  fixed https URL
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


class Setup:
    def __init__(
        self, api: Api | None, guild_id: str, apply: bool, out: Callable[[str], None]
    ) -> None:
        self.api, self.guild, self.apply, self.out = api, guild_id, apply, out
        self.changes = 0
        self.roles: dict[str, Json] = {}
        self.channels: list[Json] = []

    def _write(self, method: str, path: str, body: Json, label: str, fake_id: str) -> Json:
        self.changes += 1
        self.out(f"{'DO' if self.apply else 'WOULD'}: {label}")
        if not self.apply or self.api is None:
            return {**body, "id": fake_id}
        return dict(self.api.call(method, path, body))

    def load(self) -> None:
        if self.api is None:  # --show-blueprint: plan against an empty server
            return
        self.roles = {r["name"]: r for r in self.api.call("GET", f"/guilds/{self.guild}/roles")}
        self.channels = list(self.api.call("GET", f"/guilds/{self.guild}/channels"))

    def ensure_role(self, spec: Json) -> None:
        body = {
            "name": spec["name"],
            "color": int(spec["color"].lstrip("#"), 16),
            "hoist": spec["hoist"],
            "mentionable": spec["mentionable"],
            "permissions": str(perm_value(spec["permissions"])),
        }
        label = f"role {spec['name']} ({perm_text(perm_value(spec['permissions']))})"
        have = self.roles.get(spec["name"])
        if have is None:
            self.roles[spec["name"]] = self._write(
                "POST",
                f"/guilds/{self.guild}/roles",
                body,
                f"create {label}",
                f"new:{spec['name']}",
            )
        elif any(str(have.get(k)) != str(v) for k, v in body.items()):
            self.roles[spec["name"]] = self._write(
                "PATCH",
                f"/guilds/{self.guild}/roles/{have['id']}",
                body,
                f"update {label}",
                have["id"],
            )

    def _principal_id(self, name: str) -> str:
        return self.guild if name == EVERYONE else str(self.roles[name]["id"])

    def _overwrite_list(
        self, desired: dict[str, tuple[int, int]], existing: list[Json]
    ) -> list[Json]:
        """Desired overwrites plus any existing ones for principals we do not manage."""
        managed = {self._principal_id(n) for n in desired}
        keep = [o for o in existing if str(o["id"]) not in managed]
        mine = [
            {"id": self._principal_id(n), "type": OVERWRITE_ROLE, "allow": str(a), "deny": str(d)}
            for n, (a, d) in desired.items()
        ]
        return sorted(keep + mine, key=lambda o: str(o["id"]))

    def ensure_channel(
        self,
        name: str,
        kind: int,
        parent: str | None,
        topic: str | None,
        desired: dict[str, tuple[int, int]],
    ) -> Json:
        found = next(
            (
                c
                for c in self.channels
                if c["name"] == name
                and c["type"] == kind
                and (c.get("parent_id") or None) == parent
            ),
            None,
        )
        want = self._overwrite_list(desired, (found or {}).get("permission_overwrites", []))
        body: Json = {"name": name, "type": kind, "permission_overwrites": want}
        if parent:
            body["parent_id"] = parent
        if topic and kind == CHANNEL_TEXT:
            body["topic"] = topic
        shown = ", ".join(
            f"{n}: allow {perm_text(a)}; deny {perm_text(d)}" for n, (a, d) in desired.items()
        )
        label = f"{'category' if kind == CHANNEL_CATEGORY else 'channel'} {name} [{shown}]"
        if found is None:
            made = self._write(
                "POST", f"/guilds/{self.guild}/channels", body, f"create {label}", f"new:{name}"
            )
            self.channels.append(made)
            return made
        have_ow = sorted(
            (
                {**o, "id": str(o["id"]), "allow": str(o["allow"]), "deny": str(o["deny"])}
                for o in found.get("permission_overwrites", [])
            ),
            key=lambda o: o["id"],
        )
        want_ow = sorted(({**o, "id": str(o["id"])} for o in want), key=lambda o: o["id"])
        same_ow = [(o["id"], o["allow"], o["deny"]) for o in have_ow] == [
            (o["id"], o["allow"], o["deny"]) for o in want_ow
        ]
        same_topic = kind != CHANNEL_TEXT or not topic or found.get("topic") == topic
        if not (same_ow and same_topic):
            found.update(
                self._write(
                    "PATCH", f"/channels/{found['id']}", body, f"update {label}", found["id"]
                )
            )
        return found

    def run(self, bp: Json) -> None:
        self.load()
        for spec in bp["roles"]:
            self.ensure_role(spec)
        for cat in bp["categories"]:
            cat_desired = {
                n: (perm_value(p["allow"]), perm_value(p["deny"]))
                for n, p in cat["overwrites"].items()
            }
            made = self.ensure_channel(cat["name"], CHANNEL_CATEGORY, None, None, cat_desired)
            for chan in cat["channels"]:
                self.ensure_channel(
                    chan["name"],
                    CHANNEL_TEXT,
                    str(made["id"]),
                    chan.get("topic"),
                    merged_overwrites(cat, chan),
                )


def main(
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
    out: Callable[[str], None] = print,
) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--blueprint", default=str(Path(__file__).with_name("blueprint.json")))
    parser.add_argument("--guild", help="server (guild) id")
    parser.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    parser.add_argument(
        "--confirm-guild-name", help="must equal the real server name when --apply is used"
    )
    parser.add_argument("--show-blueprint", action="store_true", help="print the plan, no network")
    args = parser.parse_args(argv)
    environment: Mapping[str, str] = os.environ if env is None else env
    try:
        bp = json.loads(Path(args.blueprint).read_text(encoding="utf-8"))
        validate_blueprint(bp)
        if args.show_blueprint:
            Setup(None, "<guild>", False, out).run(bp)
            out("Dry run only: nothing was sent anywhere.")
            return 0
        token = environment.get("DISCORD_BOT_TOKEN", "")
        if not args.guild or not token:
            raise SetupError("need --guild and the DISCORD_BOT_TOKEN environment variable")
        api = Api(token, transport)
        real = str(api.call("GET", f"/guilds/{args.guild}")["name"])
        out(f"Server: {real}")
        if args.apply and args.confirm_guild_name != real:
            raise SetupError(f"--confirm-guild-name must be exactly the server name, {real!r}")
        setup = Setup(api, args.guild, args.apply, out)
        setup.run(bp)
        outcome = "made" if args.apply else "planned; nothing was written (dry run)"
        out(f"{setup.changes} change(s) {outcome}.")
        return 0
    except SetupError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
