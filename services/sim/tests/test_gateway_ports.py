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


def test_fake_ids_follow_the_key_not_the_resolution_order() -> None:
    first, second = InMemoryIdentityResolver(), InMemoryIdentityResolver()
    a1, b1 = first.resolve("TWITCH", "a", None), first.resolve("TWITCH", "b", None)
    b2, a2 = second.resolve("TWITCH", "b", None), second.resolve("TWITCH", "a", None)
    assert (a1, b1) == (a2, b2) and a1 != b1
    assert COMMANDER.match(a1) and COMMANDER.match(b1)


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


def _absolute(package: str, level: int, module: str | None, names: list[str]) -> list[str]:
    """Absolute names an `import`/`from ... import` statement reaches, from a file in `package`."""
    if level == 0:
        return [module] if module else []
    base = ".".join(package.split(".")[: len(package.split(".")) - (level - 1)])
    if module:
        return [f"{base}.{module}"]
    return [f"{base}.{n}" for n in names]


def test_relative_imports_resolve_against_the_package() -> None:
    assert _absolute("nexus.gateway", 2, "runtime", ["inbox"]) == ["nexus.runtime"]
    assert _absolute("nexus.gateway", 1, "ports", ["Health"]) == ["nexus.gateway.ports"]
    assert _absolute("nexus.gateway", 2, None, ["core"]) == ["nexus.core"]
    assert _absolute("nexus.gateway", 0, "os.path", ["join"]) == ["os.path"]


def _allowed(name: str) -> bool:
    return name.split(".")[0] in sys.stdlib_module_names or any(
        name == a or name.startswith(a + ".") for a in ALLOWED_NEXUS | {"nexus.gateway"}
    )


def test_gateway_imports_no_core_and_no_vendor_sdk() -> None:
    """Belt and braces for import-linter: every import is stdlib or an allowed nexus sibling."""
    assert not _allowed("nexus.runtime") and not _allowed("nexus.core")
    offenders = []
    for path in sorted(GATEWAY.rglob("*.py")):
        parts = path.relative_to(GATEWAY).with_suffix("").parts
        package = ".".join(("nexus", "gateway", *parts[:-1]))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                aliases = [a.name for a in node.names]
                names = _absolute(package, node.level, node.module, aliases)
            else:
                continue
            offenders += [f"{path.name}: {n}" for n in names if not _allowed(n)]
    assert not offenders, offenders
    assert ports.__doc__
