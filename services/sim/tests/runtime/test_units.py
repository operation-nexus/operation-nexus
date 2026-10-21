"""NX-367: unit catalog loader and its cross-file rules (CONFIG-AND-CONTENT §7, COMBAT §5.1)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

from nexus.contracts.gen.common.enums import UnitKind
from nexus.runtime.config import ConfigError
from nexus.runtime.units import catalog_hash, load_catalog

CONTENT = Path(__file__).resolve().parents[4] / "content"
# Pinned from this implementation's first run (NX-367; re-pinned NX-121: speed_mps; NX-368:
# min_speed_mps and fuel_s); a change means every config_hash moved.
GOLDEN_UNITS_HASH = "c1b7ba0ef661ca63cb0213f68efb689a5c71f7d2ae6da6c1db8b23f83fe0d59b"
RADAR = "units/radar-site.yaml"


def shipped() -> tuple[Path, Path, Path]:
    return CONTENT / "units", CONTENT / "weapons.yaml", CONTENT / "roles.yaml"


def staged(tmp_path: Path, file: str, old: str, new: str) -> tuple[Path, Path, Path]:
    """A copy of the shipped content with one edit to `file` (relative to content/)."""
    root = tmp_path / "content"
    shutil.copytree(CONTENT, root, ignore=shutil.ignore_patterns("theaters"))
    path = root / file
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old  # the fixture edits exactly one place
    path.write_text(text.replace(old, new), encoding="utf-8")
    return root / "units", root / "weapons.yaml", root / "roles.yaml"


def test_shipped_catalog_loads_with_golden_hash() -> None:
    catalog = load_catalog(*shipped())
    assert catalog_hash(catalog) == GOLDEN_UNITS_HASH
    assert [u.kind for u in catalog.units] == sorted(get_args(get_args(UnitKind.__value__)[0]))
    assert [w.id for w in catalog.weapons] == sorted(w.id for w in catalog.weapons)
    assert catalog.roles.roles.STRIKE == "STRIKE_FIGHTER"


def test_garrison_infantry_fires_on_ground_only() -> None:
    catalog = load_catalog(*shipped())
    targets = {w.id: set(w.targets) for w in catalog.weapons}
    (infantry,) = (u for u in catalog.units if u.kind == "GARRISON_INFANTRY")
    assert [targets[w] for w in infantry.weapons] == [{"GROUND"}]  # Q-CBT-25


# COMBAT §5.1: the domains each kind may fire on (a test of the table, Q-CBT-15).
_GROUND_FIRE = {"GROUND", "STATIC", "STRUCTURE"}
MATRIX = {
    "STRIKE_FIGHTER": {"AIR"} | _GROUND_FIRE,
    "ENEMY_STRIKE_FIGHTER": {"AIR"} | _GROUND_FIRE,
    "ENEMY_FIGHTER": {"AIR"},
    "ENEMY_ARMOR": _GROUND_FIRE,
    "GARRISON_INFANTRY": {"GROUND"},
    "AIR_DEFENSE_SITE": {"AIR"},
}


def test_weapon_targets_match_combat_table() -> None:
    catalog = load_catalog(*shipped())
    targets = {w.id: set(w.targets) for w in catalog.weapons}
    for u in catalog.units:
        assert set().union(*(targets[w] for w in u.weapons)) == MATRIX.get(u.kind, set()), u.kind


@pytest.mark.parametrize(
    ("file", "old", "new", "error"),
    [
        # kind set and file names
        (RADAR, "kind: RADAR_SITE", "kind: LOGI_TRUCK", r"does not match the file"),
        (RADAR, "kind: RADAR_SITE", "kind: LOGI_TRUCK", r"duplicate 'LOGI_TRUCK'"),
        (RADAR, "kind: RADAR_SITE", "kind: RADAR_SIT", r"kind: .*Input should be"),
        # playable_by, min_rank
        ("units/recon-uav.yaml", "min_rank: 1\n", "", r"min_rank: present if and only if VIEWER"),
        ("units/enemy-armor.yaml", "weapons:", "min_rank: 1\nweapons:", r"min_rank: present if"),
        ("units/recon-uav.yaml", "[VIEWER, AI_GARRISON]", "[VIEWER, VIEWER]", r"playable_by: dup"),
        ("units/recon-uav.yaml", "[VIEWER, AI_GARRISON]", "[]", r"playable_by"),
        # min_speed_mps and fuel_s iff AIR (NX-368)
        ("units/recon-uav.yaml", "min_speed_mps: 20.0", "", r"min_speed_mps: present if and only"),
        ("units/recon-uav.yaml", "fuel_s: 14400.0", "", r"fuel_s: present if and only if domain"),
        ("units/enemy-armor.yaml", "weapons:", "fuel_s: 60.0\nweapons:", r"fuel_s: present if"),
        ("units/recon-uav.yaml", "min_speed_mps: 20.0", "min_speed_mps: 60.5", r"above speed_mps"),
        ("units/recon-uav.yaml", "fuel_s: 14400.0", "fuel_s: 0", r"fuel_s: .*greater than 0"),
        # weapons
        ("units/enemy-fighter.yaml", "[AA_MISSILE]", "[NO_SUCH]", r"weapons\.0: unknown weapon"),
        ("units/enemy-fighter.yaml", "[AA_MISSILE]", "[AA_MISSILE, AA_MISSILE]", r"weapons: dup"),
        (
            "weapons.yaml",
            "  - { id: SAM,",
            "  - { id: AAA_GUN, targets: [AIR] }\n  - { id: SAM,",
            r"weapons\.id: dup",
        ),
        ("units/air-defense-site.yaml", "[AAA_GUN, SAM]", "[AAA_GUN]", r"'SAM' is used by no unit"),
        (
            "weapons.yaml",
            "id: AA_LIGHT, targets: [AIR]",
            "id: AA_LIGHT, targets: [AIR, AIR]",
            r"targets: dup",
        ),
        # Q-CBT-25
        (
            "weapons.yaml",
            "id: SMALL_ARMS, targets: [GROUND]",
            "id: SMALL_ARMS, targets: [GROUND, AIR]",
            r"'SMALL_ARMS' may target outside",
        ),
        # roles
        (
            "roles.yaml",
            "LOGI: LOGI_TRUCK",
            "LOGI: ENEMY_ARMOR",
            r"roles\.LOGI: 'ENEMY_ARMOR' is not playable by VIEWER",
        ),
        ("roles.yaml", "  LOGI: LOGI_TRUCK\n", "", r"roles\.LOGI"),
        ("roles.yaml", "LOGI: LOGI_TRUCK", "LOGI: LOGI_TRUCK\n  NAVY: LOGI_TRUCK", r"roles\.NAVY"),
        # strict YAML and TBD
        (RADAR, "domain: STATIC", "domain: STATIC\ndomain: AIR", r"duplicate key"),
        (RADAR, "domain: STATIC", "domain: TBD", r"domain: TBD until"),
    ],
)
def test_rejects(tmp_path: Path, file: str, old: str, new: str, error: str) -> None:
    with pytest.raises(ConfigError, match=error):
        load_catalog(*staged(tmp_path, file, old, new))


def test_missing_kind_file(tmp_path: Path) -> None:
    units, weapons, roles = staged(tmp_path, RADAR, "weapons: []", "weapons: []")
    (units / "radar-site.yaml").rename(units / "radar-site.yaml.bak")
    with pytest.raises(ConfigError, match=r"missing kind 'RADAR_SITE'"):
        load_catalog(units, weapons, roles)


def test_hash_ignores_file_order_and_formatting(tmp_path: Path) -> None:
    units, weapons, roles = staged(
        tmp_path, "weapons.yaml", "schema_version: 1", "schema_version: 1"
    )
    lines = weapons.read_text(encoding="utf-8").splitlines()
    head, rows = lines[:5], lines[5:]
    assert len(rows) == 7
    weapons.write_text("\n".join([*head, *reversed(rows)]) + "\n", encoding="utf-8")
    radar = units / "radar-site.yaml"
    radar.write_text("# other layout\n" + radar.read_text(encoding="utf-8").replace(": ", ":   "))
    assert catalog_hash(load_catalog(units, weapons, roles)) == GOLDEN_UNITS_HASH


def test_one_value_change_changes_hash(tmp_path: Path) -> None:
    changed = staged(tmp_path, "units/strike-fighter.yaml", "min_rank: 1", "min_rank: 2")
    assert catalog_hash(load_catalog(*changed)) != GOLDEN_UNITS_HASH


_CHILD = (
    "import sys; from pathlib import Path\n"
    "from nexus.runtime.units import catalog_hash, load_catalog\n"
    "c = Path(sys.argv[1])\n"
    "print(catalog_hash(load_catalog(c / 'units', c / 'weapons.yaml', c / 'roles.yaml')))"
)


def test_hash_is_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(  # noqa: S603
            [sys.executable, "-c", _CHILD, str(CONTENT)], env=env, text=True
        ).strip()

    assert run("1") == run("2") == GOLDEN_UNITS_HASH
