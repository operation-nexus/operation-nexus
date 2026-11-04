"""GW-1, GW-3, GW-5, GW-6: the vendor-free gateway ports and their in-memory fake."""

import ast
import re
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from nexus.contracts.gen.common.ids import CommanderId
from nexus.gateway import fakes, ports
from nexus.gateway.fakes import InMemoryIdentityResolver
from nexus.gateway.ports import Capabilities, IdentityResolver, NameDirectory

GATEWAY = Path(fakes.__file__).parent
COMMANDER = re.compile("^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
# nexus.gateway may import these siblings (CHAT-GATEWAY §1.2) and the standard library, no more.
ALLOWED_NEXUS = {"nexus.contracts", "nexus.commands", "nexus.moderation", "nexus.obs"}


def test_fake_satisfies_the_resolver_port() -> None:
    resolver: IdentityResolver = InMemoryIdentityResolver()
    a = resolver.resolve("TWITCH", "u1", None)
    assert COMMANDER.match(a)
    assert resolver.resolve("TWITCH", "u1", None) == a  # lazy, then stable
    assert resolver.resolve("YOUTUBE", "u1", None) != a  # identity is (platform, user id)
    assert resolver.resolve("TWITCH", "u2", None) != a


def test_ban_is_per_commander() -> None:
    resolver = InMemoryIdentityResolver()
    a: CommanderId = resolver.resolve("TWITCH", "u1", None)
    b: CommanderId = resolver.resolve("TWITCH", "u2", None)
    assert not resolver.is_banned(a)
    resolver.ban(a)
    assert resolver.is_banned(a) and not resolver.is_banned(b)


def test_fake_ids_are_deterministic_across_instances() -> None:
    first, second = InMemoryIdentityResolver(), InMemoryIdentityResolver()
    assert first.resolve("TWITCH", "x", None) == second.resolve("TWITCH", "x", None)


def test_capabilities_default_to_off_and_are_frozen() -> None:
    caps = Capabilities()
    assert caps.max_reply_rate is None and not caps.supports_whisper
    with pytest.raises(FrozenInstanceError):
        caps.supports_whisper = True  # type: ignore[misc]


def test_name_directory_is_an_immutable_snapshot() -> None:
    source = {"VIPER-27": 7}
    directory = NameDirectory(callsigns=source, nodes={"alpha": "node-a"})
    source["VIPER-27"] = 8  # the publisher mutating its own dict does not leak in
    assert directory.callsigns["VIPER-27"] == 7
    with pytest.raises(TypeError):
        directory.callsigns["X"] = 1  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        directory.nodes = {}  # type: ignore[misc]


def test_gateway_imports_no_core_and_no_vendor_sdk() -> None:
    """Belt and braces for import-linter: every import is stdlib or an allowed nexus sibling."""
    stdlib = set(sys.stdlib_module_names)
    offenders = []
    for path in sorted(GATEWAY.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                ok = name.split(".")[0] in stdlib or any(
                    name == a or name.startswith(a + ".") for a in ALLOWED_NEXUS
                )
                if not ok:
                    offenders.append(f"{path.name}: {name}")
    assert not offenders, offenders
    assert ports.__doc__
