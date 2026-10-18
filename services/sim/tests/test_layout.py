import importlib

MODULES = [
    "core",
    "contracts",
    "runtime",
    "gateway",
    "commands",
    "moderation",
    "broadcast",
    "progression",
    "persistence",
    "advisors",
    "audio",
    "clips",
    "ops",
]


def test_all_modules_import() -> None:
    for name in MODULES:
        mod = importlib.import_module(f"nexus.{name}")
        assert mod.__doc__, f"nexus.{name} must name its spec in a docstring"
