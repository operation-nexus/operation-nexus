"""Config file loader, canonical hash and tick conversion (CONFIG-AND-CONTENT CFG-1..3, 9).

Runtime, not core: it reads files. YAML is parsed with `yaml.safe_load` semantics through
`StrictLoader`, which drops YAML 1.1's surprises (§4.4):
- only `true`/`false` (the YAML 1.2 spellings) are booleans; an unquoted `yes`, `no`, `on`, `off`,
  `y` or `n` in any case is rejected; quote it to mean the string;
- numbers are YAML 1.2 core decimals; hex, octal, leading zeros, `_` separators and sexagesimal
  (`1:30`) stay strings, which the strict schema then rejects;
- `.inf` and `.nan` are rejected: no config value is infinite, and canonical JSON has no spelling;
- a key repeated in one mapping is rejected instead of the last one silently winning.
"""

import hashlib
import json
import math
import re
from collections.abc import Hashable
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from nexus.contracts.gen.config.balance import BalanceConfig

_TAG = "tag:yaml.org,2002:"
_YAML11_WORD_TAG = "tag:nexus,2026:yaml11-bool-word"
_DIGITS = "0123456789"
_DECIMAL = r"(?:0|[1-9][0-9]*)"
_EXPONENT = r"(?:[eE][-+]?[0-9]+)?"


class ConfigError(ValueError):
    """A config file that fails to parse or validate; startup must stop (CONFIG-AND-CONTENT §12)."""


_BOOL = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
_INT = re.compile(rf"^[-+]?{_DECIMAL}$")
_FLOAT = re.compile(
    rf"^(?:[-+]?(?:{_DECIMAL}(?:\.[0-9]*)?|\.[0-9]+){_EXPONENT}"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
)


class StrictLoader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 core booleans and numbers, and no duplicate keys."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        self._reject_duplicates(node)
        return super().construct_mapping(node, deep)

    def _reject_duplicates(self, node: yaml.MappingNode) -> None:
        seen: set[Hashable] = set()
        for key_node, value_node in node.value:
            if key_node.tag == _TAG + "merge":
                # `<<: *base` then an explicit key is an override, not a duplicate; but an inline
                # base is flattened without construct_mapping, so it is scanned here.
                bases = (
                    value_node.value if isinstance(value_node, yaml.SequenceNode) else [value_node]
                )
                for base in bases:
                    if isinstance(base, yaml.MappingNode):
                        self._reject_duplicates(base)
                continue
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, Hashable):
                continue  # the base class reports unhashable keys
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate key {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)


def _not_core(node: yaml.ScalarNode, kind: str) -> yaml.constructor.ConstructorError:
    return yaml.constructor.ConstructorError(
        None, None, f"{node.value!r} is not a YAML 1.2 decimal {kind}", node.start_mark
    )


def _reject_yaml11_word(loader: yaml.SafeLoader, node: yaml.Node) -> None:
    raise yaml.constructor.ConstructorError(
        None,
        None,
        f"unquoted {node.value!r} is a YAML 1.1 boolean; write true/false or quote the string",
        node.start_mark,
    )


# The constructors repeat the resolver patterns so an explicit `!!int 0x10` is held to them too.
def _core_bool(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> bool:
    if not _BOOL.match(node.value):
        raise yaml.constructor.ConstructorError(
            None, None, f"{node.value!r} is not a YAML 1.2 boolean (true/false)", node.start_mark
        )
    return loader.construct_yaml_bool(node)


def _core_int(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> int:
    if not _INT.match(node.value):
        raise _not_core(node, "integer")
    return loader.construct_yaml_int(node)


def _finite_float(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> float:
    if not _FLOAT.match(node.value):
        raise _not_core(node, "number")
    value = loader.construct_yaml_float(node)
    if not math.isfinite(value):
        raise yaml.constructor.ConstructorError(
            None, None, f"{node.value!r} is not a finite number", node.start_mark
        )
    return value


_REPLACED = {_TAG + "bool", _TAG + "int", _TAG + "float"}
StrictLoader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag not in _REPLACED]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
StrictLoader.add_implicit_resolver(_TAG + "bool", _BOOL, list("tTfF"))
StrictLoader.add_implicit_resolver(
    _YAML11_WORD_TAG, re.compile(r"^(?i:yes|no|on|off|y|n)$"), list("yYnNoO")
)
# int before float: the float pattern also matches a plain decimal int.
StrictLoader.add_implicit_resolver(_TAG + "int", _INT, list("-+" + _DIGITS))
StrictLoader.add_implicit_resolver(_TAG + "float", _FLOAT, list("-+." + _DIGITS))
StrictLoader.add_constructor(_YAML11_WORD_TAG, _reject_yaml11_word)
StrictLoader.add_constructor(_TAG + "bool", _core_bool)
StrictLoader.add_constructor(_TAG + "int", _core_int)
StrictLoader.add_constructor(_TAG + "float", _finite_float)


def load_model[M: BaseModel](path: Path, model: type[M]) -> M:
    """Parse a YAML file strictly and validate it; errors name the file and each key path."""
    try:
        with path.open(encoding="utf-8") as f:  # a file stream puts its name in YAML error marks
            tree = yaml.load(f, Loader=StrictLoader)  # noqa: S506 - StrictLoader is a SafeLoader subclass
    except (OSError, ValueError, yaml.YAMLError) as e:  # ValueError covers bad UTF-8 too
        raise ConfigError(f"{path}: {e}") from e
    if tbd := _tbd_keys(tree, ""):
        raise ConfigError(
            f"{path}: " + "; ".join(f"{k}: TBD until the harness sets it" for k in tbd)
        )
    try:
        return model.model_validate(tree, strict=True)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(map(str, err['loc'])) or '<root>'}: {err['msg']}" for err in e.errors()
        )
        raise ConfigError(f"{path}: {problems}") from e


def _tbd_keys(tree: object, key: str) -> list[str]:
    """Key paths of every value written TBD (DATA-INTEGRITY DI-7, CONFIG-AND-CONTENT TH-11)."""
    if tree == "TBD":
        return [key or "<root>"]
    if isinstance(tree, dict):
        items: list[tuple[object, object]] = list(tree.items())
    elif isinstance(tree, list):
        items = list(enumerate(tree))
    else:
        return []
    return [k for sub, v in items for k in _tbd_keys(v, f"{key}.{sub}" if key else str(sub))]


def load_balance(path: Path) -> BalanceConfig:
    """Parse and strictly validate a balance profile (CFG-1, CFG-2)."""
    cfg = load_model(path, BalanceConfig)
    if cfg.fow.sigint_size_l_min <= cfg.fow.sigint_size_m_min:
        raise ConfigError(f"{path}: fow.sigint_size_l_min: must be above fow.sigint_size_m_min")
    ds = cfg.combat.damage_state
    if not ds.disabled_below < ds.mission_kill_below < ds.damaged_below:
        raise ConfigError(
            f"{path}: combat.damage_state: need disabled_below < mission_kill_below < damaged_below"
        )
    weights = cfg.campaign.momentum
    if _exact(weights.nodes_weight) + _exact(weights.supply_weight) != 100:
        raise ConfigError(f"{path}: campaign.momentum: the two weights must add up to 100")
    return cfg


def canonical_hash(tree: object) -> str:
    """Hex blake2b-256 of the canonical JSON of a JSON-compatible tree (§4.4).

    Keys sorted, no insignificant whitespace, UTF-8, floats as `repr`; NaN and infinity are
    rejected. Hash a validated config as `canonical_hash(cfg.model_dump())`.
    """
    try:
        text = json.dumps(
            tree, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as e:
        raise ConfigError(f"not canonically hashable: {e}") from e
    return hashlib.blake2b(text.encode("utf-8"), digest_size=32).hexdigest()


def config_hash(balance: str, units: str, theater: str) -> str:
    """Hex blake2b-256 over the concatenated raw component digests, in §4.4 order.

    Order: balance, units, doctrines, theater, text. Balance (NX-106), the unit catalog (NX-367,
    `units.catalog_hash`) and the campaign's theater (NX-120) exist today; doctrines (NX-213) and
    text join as parameters, in their places, with their loaders. A missing part is never stood
    in for by an empty or placeholder hash.
    """
    parts = bytes.fromhex(balance) + bytes.fromhex(units) + bytes.fromhex(theater)
    return hashlib.blake2b(parts, digest_size=32).hexdigest()


def _exact(value: float) -> Fraction:
    # The decimal the file wrote, not the nearest binary float: 0.1 s is exactly 1/10.
    return Fraction(repr(value))


def _duration(seconds: float) -> Fraction:
    if not (math.isfinite(seconds) and seconds >= 0):
        raise ConfigError(f"a duration must be finite and >= 0 seconds, got {seconds!r}")
    return _exact(seconds)


def game_ticks(seconds: float, cfg: BalanceConfig, *, unit_s: int = 1) -> int:
    """Whole ticks for a game-time duration, rounded up (CFG-9, Q-ALN-6). `unit_s` is the seconds
    in the key's unit (60 for minutes, 3600 for hours), applied to the exact decimal."""
    return math.ceil(_duration(seconds) * unit_s * cfg.sim.tick_hz)


def world_ticks(seconds: float, cfg: BalanceConfig) -> int:
    """Whole ticks for a world-time duration, rounded up (CFG-9, Q-ALN-6)."""
    return math.ceil(_duration(seconds) * cfg.sim.tick_hz / _exact(cfg.sim.time_scale))
