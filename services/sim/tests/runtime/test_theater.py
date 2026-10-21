"""NX-120: theater loader, TH rules and paths on theater #1 (CONFIG-AND-CONTENT §9, §11.1, §13)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from nexus.core.roads import shortest_path
from nexus.runtime.config import ConfigError, canonical_hash
from nexus.runtime.theater import load_theater, masking_cells, road_graph

STRAIT_1 = Path(__file__).resolve().parents[4] / "content" / "theaters" / "strait-1.yaml"
TEXT = STRAIT_1.read_text(encoding="utf-8")
# Pinned from this implementation's first run (NX-120); a change means every config_hash moved.
GOLDEN_THEATER_HASH = "74dd30b1931a1ba8071c53981a7c349a5b4711109513b6c4c96321ee8590a1b0"
INTACT: frozenset[str] = frozenset()


def write(tmp_path: Path, old: str, new: str, name: str = "strait-1") -> Path:
    assert TEXT.count(old) == 1, old  # the fixture edits exactly one place
    path = tmp_path / f"{name}.yaml"
    path.write_text(TEXT.replace(old, new), encoding="utf-8")
    return path


def test_strait_1_loads_with_golden_hash() -> None:
    theater = load_theater(STRAIT_1)
    assert (theater.slug, len(theater.nodes), len(theater.edges)) == ("strait-1", 12, 12)
    assert canonical_hash(theater.model_dump()) == GOLDEN_THEATER_HASH


def test_masking_regions_rasterize_to_1km_cells_by_centre(tmp_path: Path) -> None:
    """Q-FOW-3 (NX-150 part 2): northern-hills is x 150-260 km, y 0-35 km: 110 x 35 cells;
    southern-valley x 230-330 km, y 205-240 km: 100 x 35 cells."""
    cell_m, cells = masking_cells(load_theater(STRAIT_1))
    assert cell_m == 1000
    hills, valley = frozenset({"northern-hills"}), frozenset({"southern-valley"})
    assert len(cells) == 110 * 35 + 100 * 35
    assert cells[150, 0] == cells[259, 34] == hills
    assert cells[230, 205] == cells[329, 239] == valley
    assert {(149, 0), (260, 0), (259, 35), (229, 205), (330, 239)}.isdisjoint(cells)
    # A cell in two overlapping regions lists both.
    path = write(tmp_path, "[[230000,205000],[330000,205000],", "[[230000,30000],[330000,30000],")
    both = masking_cells(load_theater(path))[1]
    assert both[240, 30] == hills | valley and both[240, 36] == valley


def test_paths_between_sanctuary_and_hq_avoid_destroyed_bridges() -> None:
    graph = road_graph(load_theater(STRAIT_1))
    north = ["haven", "west-airbase", "fob-n-w", "cross-n", "east-airbase", "static-hq"]
    south = ["haven", "west-airbase", "fob-s-w", "cross-s", "east-airbase", "static-hq"]
    # North and south are mirror images, so equal cost; the tie goes to 'cross-n' < 'cross-s'.
    assert shortest_path(graph, "haven", "static-hq", blocked=INTACT) == north
    assert shortest_path(graph, "haven", "static-hq", blocked=frozenset({"bridge-n"})) == south
    assert (
        shortest_path(graph, "static-hq", "haven", blocked=frozenset({"bridge-s"})) == north[::-1]
    )
    both = frozenset({"bridge-n", "bridge-s"})
    assert shortest_path(graph, "haven", "static-hq", blocked=both) is None
    assert shortest_path(graph, "cross-n", "fob-s-e", blocked=both) is not None  # east bank intact


_CHILD = (
    "import sys; from pathlib import Path; from nexus.core.roads import shortest_path\n"
    "from nexus.runtime.theater import load_theater, road_graph\n"
    "g = road_graph(load_theater(Path(sys.argv[1])))\n"
    "print(shortest_path(g, 'haven', 'static-hq', blocked=frozenset({'bridge-n'})))"
)


def test_path_is_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(  # noqa: S603
            [sys.executable, "-c", _CHILD, str(STRAIT_1)], env=env, text=True
        ).strip()

    graph = road_graph(load_theater(STRAIT_1))
    here = str(shortest_path(graph, "haven", "static-hq", blocked=frozenset({"bridge-n"})))
    assert run("1") == run("2") == here


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        # TH-1
        ("id: fob-s-w,     ", "id: fob-n-w,     ", r"nodes\.id: duplicate 'fob-n-w'"),
        ('name: "FOB South-West"', 'name: "fob north-west"', r"nodes\.name: duplicate"),
        ("id: haven,       ", "id: Haven_1,     ", r"nodes\.0\.id: String should match"),
        ("id: southern-valley,", "id: northern-hills,", r"terrain\.masking_regions\.id: duplicate"),
        # TH-2
        (
            "{ a: haven,        b: west-airbase",
            "{ a: haven,        b: nowhere",
            r"edges\.0\.b: unknown",
        ),
        (
            "{ a: haven,        b: west-airbase",
            "{ a: haven,        b: haven",
            r"edges\.0: self-loop",
        ),
        (
            "{ a: west-airbase, b: fob-n-w,",
            "{ a: west-airbase, b: haven,  ",
            r"edges: duplicate 'haven~west-airbase~ROAD'",
        ),
        # TH-3
        (
            "  - { a: haven,        b: west-airbase, layer: ROAD, speed_mult: 1.0 }\n",
            "",
            r"nodes\.1: 'west-airbase' is not reachable by road from 'haven'",
        ),
        (", bridge: bridge-n }", " }", r"nodes\.4: BRIDGE 'bridge-n' is on no edge"),
        ("kind: FOB,       pos: [230000,60000]", "kind: PORT,      pos: [230000,60000]", r"PORT"),
        (  # a PORT needs a road too (lead decision on TH-3)
            "  # Static (east)\n",
            '  - { id: port-x, name: "Port X", kind: PORT, pos: [200000,120000], '
            "start_owner: NEUTRAL, start_stock: 0, sector: centre }\n",
            r"nodes\.8: 'port-x' is not reachable by road",
        ),
        # TH-4
        ("bridge: bridge-n }", "bridge: cross-n }", r"edges\.3\.bridge: unknown or wrong-kind"),
        ("pos: [200000,60000]", "pos: [200000,61001]", r"edges\.3\.bridge: 'bridge-n' is not on"),
        # TH-5
        (
            "kind: FOB,       pos: [230000,60000],  start_owner: NEUTRAL,   start_stock: 0",
            "kind: SANCTUARY, pos: [230000,60000],  start_owner: NEUTRAL,   start_stock: null",
            r"sanctuary: need exactly one SANCTUARY",
        ),
        (
            "start_owner: ENEMY,     start_stock: 1000, sector: centre, garrison_quota: 8",
            "start_owner: COALITION, start_stock: 1000, sector: centre, garrison_quota: 8",
            r"enemy_hq: need exactly one HQ",
        ),
        (
            "start_owner: COALITION, start_stock: 1000",
            "start_owner: COALITION, start_stock: null",
            r"nodes\.1\.start_stock: null",
        ),
        # TH-6
        (
            "pos: [20000,120000]",
            "pos: [20000,250000]",
            r"nodes\.0\.pos: \[20000, 250000\] is outside",
        ),
        (
            "start_stock: null, sector: centre",
            "start_stock: null, sector: north ",
            r"nodes\.0\.pos: not inside sector 'north'",
        ),
        ("sector: centre }  # null", "sector: middle }  # null", r"nodes\.0\.sector: unknown"),
        # TH-10
        (
            "kind: RADAR_SITE,       base: west-airbase",
            "kind: RADAR_SITE,       base: cross-n",
            r"facilities\.0\.base: 'cross-n' starts NEUTRAL",
        ),
        ("forward_airbase: west-airbase", "forward_airbase: fob-n-w", r"forward_airbase: must be"),
        # Facility variants (CONFIG-AND-CONTENT §7.3, NX-150 part 2)
        (
            "variant: SAM, base: west-airbase",
            "variant: LONG_RANGE, base: west-airbase",
            r"facilities\.1\.variant: 'LONG_RANGE' is not a AIR_DEFENSE_SITE variant",
        ),
        (
            "kind: RADAR_SITE,       base: west-airbase",
            "kind: RADAR_SITE,       variant: SAM, base: west-airbase",
            r"facilities\.0\.variant: 'SAM' is not a RADAR_SITE variant",
        ),
        # TH-11 and §11.1 schema negatives
        (
            "start_stock: 500,  sector: north }",
            "start_stock: TBD,  sector: north }",
            r"nodes\.2\.start_stock: TBD until the harness sets it",
        ),
        (
            "b: west-airbase, layer: ROAD, speed_mult: 1.0",
            "b: west-airbase, layer: ROAD, speed_mult: TBD",
            r"edges\.0\.speed_mult: TBD until the harness sets it",
        ),
        ('name: "Haven"', "name: TBD", r"nodes\.0\.name: TBD until"),
        (
            "variant: SAM, base: west-airbase",
            "variant: TBD, base: west-airbase",
            r"facilities\.1\.variant: TBD",
        ),
        (
            "kind: RADAR_SITE,       base: west-airbase",
            "kind: LOGI_TRUCK,       base: west-airbase",
            r"facilities\.0\.kind: Input should be 'RADAR_SITE' or 'AIR_DEFENSE_SITE'",
        ),
        ("sanctuary: haven\n", "sanctuary: haven\nports: []\n", r"ports: Extra inputs"),
        ("enemy_hq: static-hq\n", "", r"enemy_hq: Field required"),
    ],
)
def test_each_rule_has_a_failing_fixture(tmp_path: Path, old: str, new: str, error: str) -> None:
    path = write(tmp_path, old, new)
    with pytest.raises(ConfigError, match=rf"^{path}: .*{error}"):
        load_theater(path)


def test_slug_must_match_file_name(tmp_path: Path) -> None:
    path = write(tmp_path, "version: 0.1.0", "version: 0.1.1", name="strait-2")
    with pytest.raises(ConfigError, match=r"slug: 'strait-1' is not the file name"):
        load_theater(path)


def test_bridge_exactly_at_tolerance_loads(tmp_path: Path) -> None:
    load_theater(write(tmp_path, "pos: [200000,60000]", "pos: [200000,61000]"))


def test_spec_format_example_loads(tmp_path: Path) -> None:
    spec = (STRAIT_1.parents[2] / "docs" / "specs" / "CONFIG-AND-CONTENT.md").read_text("utf-8")
    example = spec.split("### 9.3", 1)[1].split("```yaml\n", 1)[1].split("```", 1)[0]
    path = tmp_path / "format-example.yaml"
    path.write_text(example, encoding="utf-8")
    theater = load_theater(path)
    assert (theater.slug, theater.forward_airbase) == ("format-example", "ab-w")
