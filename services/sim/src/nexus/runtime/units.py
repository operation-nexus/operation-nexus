"""Unit catalog loader: strict YAML, schema, then the cross-file rules (NX-367).

Files (CONFIG-AND-CONTENT §7, §7a): `content/units/<kind-in-kebab-case>.yaml` (one unit each),
`content/weapons.yaml`, `content/roles.yaml`. Checked here: the kind set equals `UnitKind` with no
duplicates, file names match kinds, weapon ids resolve and none is unused, `min_rank` iff VIEWER,
`min_speed_mps` and `fuel_s` iff AIR with `min_speed_mps <= speed_mps` (NX-368),
each MVP role maps to a kind a VIEWER can play, and COMBAT §5.1 target limits (Q-CBT-25).
TBD values (DI-7) are `load_model`'s. Stats join item by item (Q-CFG-10).
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from nexus.contracts.gen.common.enums import UnitKind
from nexus.contracts.gen.config.roles import RolesConfig
from nexus.contracts.gen.config.unit import UnitConfig
from nexus.contracts.gen.config.weapons import Weapon, WeaponsConfig
from nexus.runtime.config import ConfigError, canonical_hash, load_model

_VIEWER = "VIEWER"
# Q-CBT-25: a kind whose weapons may target only these domains (COMBAT §5.1). The spec states no
# general rule, so the one decided row is listed here.
_ONLY_TARGETS = {"GARRISON_INFANTRY": frozenset({"GROUND"})}


@dataclass(frozen=True)
class UnitCatalog:
    """The validated catalog: units ordered by kind, weapons by id, never by file order."""

    units: tuple[UnitConfig, ...]
    weapons: tuple[Weapon, ...]
    roles: RolesConfig


def load_catalog(units_dir: Path, weapons_path: Path, roles_path: Path) -> UnitCatalog:
    """Load and validate the catalog; every problem names the file and its key path."""
    if not units_dir.is_dir():
        raise ConfigError(f"{units_dir}: not a directory")
    # Sorted filename order (§7a); the result is re-ordered by kind below.
    files = sorted(units_dir.glob("*.yaml"), key=lambda p: p.name)
    loaded = [(f, load_model(f, UnitConfig)) for f in files]
    weapons = load_model(weapons_path, WeaponsConfig)
    roles = load_model(roles_path, RolesConfig)
    catalog = UnitCatalog(
        units=tuple(sorted((u for _, u in loaded), key=lambda u: u.kind)),
        weapons=tuple(sorted(weapons.weapons, key=lambda w: w.id)),
        roles=roles,
    )
    problems = _files(loaded) + _units(loaded, catalog, weapons_path, roles_path)
    problems += _weapons(weapons_path, weapons, catalog)
    if problems:
        raise ConfigError("; ".join(problems))
    return catalog


def catalog_hash(catalog: UnitCatalog) -> str:
    """Hex blake2b-256 of the canonical JSON of the validated tree, the `units` part of config_hash.

    The tree is `{"units": [...by kind], "weapons": [...by id], "roles": {...}}`, so file order,
    comments and formatting do not matter; every validated value does, and list order inside a unit
    (`playable_by`, `weapons`) counts as written.
    """
    return canonical_hash(
        {
            "units": [u.model_dump() for u in catalog.units],
            "weapons": [w.model_dump() for w in catalog.weapons],
            "roles": catalog.roles.roles.model_dump(),
        }
    )


def _duplicates(values: Iterable[str], where: str) -> list[str]:
    counts = Counter(values)
    return [f"{where}: duplicate {v!r}" for v in sorted(counts) if counts[v] > 1]


def _files(loaded: list[tuple[Path, UnitConfig]]) -> list[str]:
    problems = _duplicates((u.kind for _, u in loaded), "units dir: kind")
    for f, u in loaded:
        if f.stem != u.kind.lower().replace("_", "-"):
            problems.append(f"{f}: kind: {u.kind!r} does not match the file name")
    expected = set(get_args(get_args(UnitKind.__value__)[0]))  # Annotated[Literal[...], ...]
    found = {u.kind for _, u in loaded}  # an unknown kind already failed the schema
    return problems + [f"units dir: missing kind {k!r}" for k in sorted(expected - found)]


def _units(
    loaded: list[tuple[Path, UnitConfig]],
    catalog: UnitCatalog,
    weapons_path: Path,
    roles_path: Path,
) -> list[str]:
    targets = {w.id: frozenset(w.targets) for w in catalog.weapons}
    problems: list[str] = []
    for f, u in loaded:
        problems += _duplicates(u.playable_by, f"{f}: playable_by")
        problems += _duplicates(u.weapons, f"{f}: weapons")
        if (_VIEWER in u.playable_by) != (u.min_rank is not None):
            problems.append(f"{f}: min_rank: present if and only if {_VIEWER} is in playable_by")
        problems += _air(f, u)
        problems += [
            f"{f}: weapons.{i}: unknown weapon {w!r} (not in {weapons_path})"
            for i, w in enumerate(u.weapons)
            if w not in targets
        ]
        if only := _ONLY_TARGETS.get(u.kind):
            for w in u.weapons:
                if not targets.get(w, only) <= only:
                    problems.append(f"{f}: weapons: {w!r} may target outside {sorted(only)}")
    by_kind = {u.kind: u for _, u in loaded}
    for role, kind in catalog.roles.roles:
        unit = by_kind.get(kind)
        if unit is not None and _VIEWER not in unit.playable_by:
            problems.append(f"{roles_path}: roles.{role}: {kind!r} is not playable by {_VIEWER}")
    return problems


def _air(f: Path, u: UnitConfig) -> list[str]:
    """`min_speed_mps` and `fuel_s` iff AIR (NX-368); a stall speed above top speed cannot fly."""
    air = u.domain == "AIR"
    problems = [
        f"{f}: {key}: present if and only if domain is AIR"
        for key, value in (("min_speed_mps", u.min_speed_mps), ("fuel_s", u.fuel_s))
        if air != (value is not None)
    ]
    if u.min_speed_mps is not None and u.min_speed_mps > u.speed_mps:
        problems.append(f"{f}: min_speed_mps: above speed_mps")
    return problems


def _weapons(path: Path, weapons: WeaponsConfig, catalog: UnitCatalog) -> list[str]:
    problems = _duplicates((w.id for w in weapons.weapons), f"{path}: weapons.id")
    for i, w in enumerate(weapons.weapons):
        problems += _duplicates(w.targets, f"{path}: weapons.{i}.targets")
    used = {w for u in catalog.units for w in u.weapons}
    return problems + [
        f"{path}: weapons: {w.id!r} is used by no unit" for w in catalog.weapons if w.id not in used
    ]
