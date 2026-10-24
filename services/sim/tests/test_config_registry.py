"""NX-390: the settings registry guard and generated reference (Q-CFG-15, CFG-5)."""

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


SCHEMA: dict[str, Any] = json.loads(_read("contracts", "config", "balance.json"))
DEFAULTS: dict[str, Any] = yaml.safe_load(_read("balance", "default.yaml"))
_spec = importlib.util.spec_from_file_location(
    "gen_config_reference", ROOT / "scripts" / "gen_config_reference.py"
)
assert _spec is not None and _spec.loader is not None
GEN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GEN)


def _default(path: str) -> Any:
    value: Any = DEFAULTS
    for part in path.split("."):
        value = value[part]
    return value


def test_every_site_has_unit_and_hot_reload() -> None:
    sites = GEN.sites(SCHEMA)
    assert len(sites) > 100
    for site in sites:
        assert "x-unit" in site["node"] and "x-hot-reload" in site["node"], site["paths"]


def test_registry_guard_is_clean() -> None:
    assert GEN.problems(SCHEMA) == []
    assert not hasattr(GEN, "PENDING_BLOCKS")


def test_every_site_carries_all_eight_fields() -> None:
    for site in GEN.sites(SCHEMA):
        for field in GEN.ALWAYS_FIELDS + GEN.REGISTRY_FIELDS:
            assert field in site["node"], (site["paths"], field)


def test_missing_registry_field_fails_in_every_block() -> None:
    for site in GEN.sites(SCHEMA):
        broken = copy.deepcopy(SCHEMA)
        node = next(s for s in GEN.sites(broken) if s["name"] == site["name"])["node"]
        del node["x-source"]
        found = GEN.problems(broken)
        assert any("missing x-source" in line for line in found), site["paths"]


def test_default_lies_inside_its_tune_range() -> None:
    checked = 0
    for site in GEN.sites(SCHEMA):
        tune = site["node"].get("x-tune")
        if tune is None:
            continue
        for path in site["paths"]:
            if path.endswith(".*"):
                continue
            assert tune["min"] <= _default(path) <= tune["max"], path
            checked += 1
    assert checked >= 15


def test_committed_reference_is_the_generated_one() -> None:
    assert _read("docs", "specs", "CONFIG-REFERENCE.md") == GEN.render(SCHEMA), (
        "run `make contracts`"
    )
