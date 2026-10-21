"""NX-106: balance loader, canonical hash, tick conversion (CONFIG-AND-CONTENT §13 CFG-1/2/3/9)."""

from decimal import Decimal, localcontext
from pathlib import Path

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from nexus.contracts.gen.config.balance import BalanceConfig
from nexus.runtime.config import (
    ConfigError,
    StrictLoader,
    canonical_hash,
    config_hash,
    game_ticks,
    load_balance,
    world_ticks,
)

from .test_theater import GOLDEN_THEATER_HASH as THEATER_HASH
from .test_units import GOLDEN_UNITS_HASH as UNITS_HASH

DEFAULT = Path(__file__).resolve().parents[4] / "balance" / "default.yaml"
VALID = """\
schema_version: 1
sim:
  tick_hz: 10
  time_scale: 6.0
  snapshot_every_ticks: 300
"""
# Pinned from this implementation's first run (NX-367: balance, units, theater); a change means
# every config_hash moved.
GOLDEN_CONFIG_HASH = "09249e87df5c22e6d690c5f02926685a7ab9542bf988a17d364277ac7ae1f120"
CFG = BalanceConfig.model_validate(
    {"schema_version": 1, "sim": {"tick_hz": 10, "time_scale": 6.0, "snapshot_every_ticks": 300}}
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def parse(text: str) -> object:
    return yaml.load(text, Loader=StrictLoader)  # noqa: S506 - StrictLoader is a SafeLoader


def balance_hash(path: Path) -> str:
    return canonical_hash(load_balance(path).model_dump())


def test_valid_file_loads(tmp_path: Path) -> None:
    cfg = load_balance(write(tmp_path, VALID))
    assert (cfg.schema_version, cfg.sim.tick_hz, cfg.sim.time_scale) == (1, 10, 6.0)
    assert cfg.sim.snapshot_every_ticks == 300


def test_default_profile_loads_and_matches_golden_hash() -> None:
    assert load_balance(DEFAULT) == CFG
    assert config_hash(balance_hash(DEFAULT), UNITS_HASH, THEATER_HASH) == GOLDEN_CONFIG_HASH
    # Order is part of the hash (§4.4): swapping the parts gives another hash.
    assert config_hash(THEATER_HASH, UNITS_HASH, balance_hash(DEFAULT)) != GOLDEN_CONFIG_HASH


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("schema_version: 1\n", "schema_version"),
        ("  tick_hz: 10\n", "sim.tick_hz"),
        ("  time_scale: 6.0\n", "sim.time_scale"),
        ("  snapshot_every_ticks: 300\n", "sim.snapshot_every_ticks"),
    ],
)
def test_each_missing_required_key_names_key_and_file(tmp_path: Path, line: str, key: str) -> None:
    path = write(tmp_path, VALID.replace(line, ""))
    with pytest.raises(ConfigError, match=rf"^{path}: {key}: Field required"):
        load_balance(path)


def test_missing_section_and_empty_file_fail(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"sim: Field required"):
        load_balance(write(tmp_path, "schema_version: 1\n"))
    with pytest.raises(ConfigError, match=r"<root>: "):
        load_balance(write(tmp_path, ""))


@pytest.mark.parametrize("text", [VALID + "extra: 1\n", VALID + "  max_entities: 1000\n"])
def test_unknown_key_fails(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError, match=r"Extra inputs are not permitted"):
        load_balance(write(tmp_path, text))


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        ("time_scale: 6.0", 'time_scale: "6.0"', "sim.time_scale"),
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 300.0", "sim.snapshot_every_ticks"),
        ("schema_version: 1", "schema_version: true", "schema_version"),
        ("tick_hz: 10", "tick_hz: 10.0", "sim.tick_hz"),
        ("tick_hz: 10", "tick_hz: 60", "sim.tick_hz"),
        ("schema_version: 1", "schema_version: 2", "schema_version"),
        ("time_scale: 6.0", "time_scale: 0", "sim.time_scale"),
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 0", "sim.snapshot_every_ticks"),
        ("time_scale: 6.0", "time_scale: TBD", "sim.time_scale"),
    ],
)
def test_wrong_type_or_value_fails_naming_key(tmp_path: Path, old: str, new: str, key: str) -> None:
    with pytest.raises(ConfigError, match=rf": {key}: "):
        load_balance(write(tmp_path, VALID.replace(old, new)))


@pytest.mark.parametrize("word", ["yes", "No", "ON", "off", "y", "N", "yEs"])
def test_yaml11_boolean_words_are_rejected(tmp_path: Path, word: str) -> None:
    path = write(tmp_path, VALID.replace("time_scale: 6.0", f"time_scale: {word}"))
    with pytest.raises(ConfigError, match=rf"{path}: .*unquoted '{word}' is a YAML 1.1 boolean"):
        load_balance(path)


def test_strict_loader_keeps_quoted_words_and_real_booleans() -> None:
    text = "a: 'yes'\nb: true\nc: False\nd: null\ne: nope\n"
    assert parse(text) == {
        "a": "yes",
        "b": True,
        "c": False,
        "d": None,
        "e": "nope",
    }


@pytest.mark.parametrize("value", [".inf", "-.inf", ".nan", "!!float .inf"])
def test_non_finite_numbers_are_rejected(tmp_path: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"is not a finite number"):
        load_balance(write(tmp_path, VALID.replace("6.0", value)))


@pytest.mark.parametrize(
    "text",
    [
        VALID + "schema_version: 1\n",  # top level
        VALID + "  tick_hz: 10\n",  # nested, same value
        VALID.replace("sim:\n", "sim:\n  time_scale: 7.0\n"),  # nested, earlier and different
    ],
)
def test_duplicate_keys_are_rejected(tmp_path: Path, text: str) -> None:
    path = write(tmp_path, text)
    with pytest.raises(
        ConfigError, match=rf"(?s)^{path}: .*duplicate key '(schema_version|tick_hz|time_scale)'"
    ):
        load_balance(path)


@pytest.mark.parametrize(
    "base", ["{tick_hz: 10, tick_hz: 11}", "[{time_scale: 6.0}, {tick_hz: 10, tick_hz: 10}]"]
)
def test_duplicate_key_inside_inline_merge_base_is_rejected(tmp_path: Path, base: str) -> None:
    text = f"schema_version: 1\nsim:\n  <<: {base}\n  snapshot_every_ticks: 300\n"
    path = write(tmp_path, text)
    with pytest.raises(ConfigError, match=rf"(?s)^{path}: .*duplicate key 'tick_hz'"):
        load_balance(path)


def test_merge_key_override_is_not_a_duplicate() -> None:
    assert parse("base: &b {a: 1, c: 3}\nz: {<<: *b, a: 2}\n") == {
        "base": {"a": 1, "c": 3},
        "z": {"a": 2, "c": 3},
    }


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 0x12C", "sim.snapshot_every_ticks"),
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 0o454", "sim.snapshot_every_ticks"),
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 0300", "sim.snapshot_every_ticks"),
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 3_00", "sim.snapshot_every_ticks"),
        ("snapshot_every_ticks: 300", "snapshot_every_ticks: 5:00", "sim.snapshot_every_ticks"),
        ("time_scale: 6.0", "time_scale: 6_0.5", "sim.time_scale"),
        ("time_scale: 6.0", "time_scale: 1:30.0", "sim.time_scale"),
        ("time_scale: 6.0", "time_scale: 06", "sim.time_scale"),
    ],
)
def test_yaml11_number_forms_stay_strings_and_fail_naming_key(
    tmp_path: Path, old: str, new: str, key: str
) -> None:
    with pytest.raises(ConfigError, match=rf": {key}: Input should be a valid (integer|number)"):
        load_balance(write(tmp_path, VALID.replace(old, new)))


@pytest.mark.parametrize(
    ("value", "kind"), [("!!int 0x12C", "integer"), ("!!float 0x10", "number")]
)
def test_explicit_tags_are_held_to_yaml12_numbers(tmp_path: Path, value: str, kind: str) -> None:
    path = write(
        tmp_path, VALID.replace("snapshot_every_ticks: 300", f"snapshot_every_ticks: {value}")
    )
    with pytest.raises(ConfigError, match=rf"(?s)^{path}: .*is not a YAML 1.2 decimal {kind}"):
        load_balance(path)


@pytest.mark.parametrize("word", ["yes", "on"])
def test_explicit_bool_tag_rejects_yaml11_words(word: str) -> None:
    with pytest.raises(yaml.YAMLError, match=rf"'{word}' is not a YAML 1.2 boolean"):
        parse(f"a: !!bool {word}\n")


def test_explicit_tags_with_decimal_values_still_load() -> None:
    assert parse("[!!int 300, !!float 6, !!float .5, !!int -3, !!bool true, !!bool False]") == [
        300,
        6.0,
        0.5,
        -3,
        True,
        False,
    ]


def test_yaml12_numbers_still_parse() -> None:
    text = "[0, -3, +5, 300, 6.0, 6., .5, 0.25, 1e3, 1.5E-2]"
    assert parse(text) == [0, -3, 5, 300, 6.0, 6.0, 0.5, 0.25, 1000.0, 0.015]


def test_hash_ignores_key_order_and_formatting(tmp_path: Path) -> None:
    reformatted = (
        "# same profile, other layout\n"
        "sim: {snapshot_every_ticks: 300, time_scale: 6.0, tick_hz: 10}\n"
        "schema_version:   1\n"
    )
    assert balance_hash(write(tmp_path, reformatted)) == balance_hash(DEFAULT)


def test_hash_expands_anchors() -> None:
    anchored = parse("a: &w {k: 1, j: [2.5, x]}\nb: *w\n")
    expanded = parse("b: {j: [2.5, x], k: 1}\na:\n  k: 1\n  j: [2.5, x]\n")
    assert canonical_hash(anchored) == canonical_hash(expanded)


def test_single_value_change_changes_hash(tmp_path: Path) -> None:
    changed = write(tmp_path, VALID.replace("time_scale: 6.0", "time_scale: 6.5"))
    assert balance_hash(changed) != balance_hash(DEFAULT)
    assert config_hash(balance_hash(changed), UNITS_HASH, THEATER_HASH) != GOLDEN_CONFIG_HASH


def test_canonical_hash_rejects_non_json_values() -> None:
    with pytest.raises(ConfigError):
        canonical_hash({"a": float("nan")})
    with pytest.raises(ConfigError):
        canonical_hash({"a": {1, 2}})


# CONFIG-AND-CONTENT §13 CFG-9 worked examples at tick_hz 10, time_scale 6.
@pytest.mark.parametrize(
    ("seconds", "ticks"),
    [(600.0, 6000), (60.0, 600)],  # 10 min game key; director.window_s 60 (game)
)
def test_game_ticks_worked_examples(seconds: float, ticks: int) -> None:
    assert game_ticks(seconds, CFG) == ticks


@pytest.mark.parametrize(
    ("seconds", "ticks"),
    [(60.0, 100), (1.0, 2), (120.0, 200), (48.0, 80)],  # 1 s = 1.67 rounded up; capture.time_s 120
)
def test_world_ticks_worked_examples(seconds: float, ticks: int) -> None:
    assert world_ticks(seconds, CFG) == ticks


def test_game_ticks_round_up_decimal_not_binary() -> None:
    assert game_ticks(0.25, CFG) == 3  # SIM-CORE §8 SC-12 example
    assert game_ticks(0.1, CFG) == 1  # 0.1 as a binary float is a hair above 1/10


@pytest.mark.parametrize("seconds", [-1.0, -0.1, float("inf"), float("nan")])
def test_tick_helpers_reject_negative_or_non_finite(seconds: float) -> None:
    with pytest.raises(ConfigError, match=r"finite and >= 0"):
        game_ticks(seconds, CFG)
    with pytest.raises(ConfigError, match=r"finite and >= 0"):
        world_ticks(seconds, CFG)


def test_zero_duration_is_zero_ticks() -> None:
    assert (game_ticks(0.0, CFG), world_ticks(0.0, CFG)) == (0, 0)


@given(
    seconds=st.floats(min_value=0, max_value=1e6, allow_nan=False),
    time_scale=st.floats(min_value=0.001, max_value=1000, allow_nan=False),
)
def test_world_ticks_is_the_least_whole_tick_count_not_shorter(
    seconds: float, time_scale: float
) -> None:
    cfg = BalanceConfig.model_validate(
        {
            "schema_version": 1,
            "sim": {"tick_hz": 10, "time_scale": time_scale, "snapshot_every_ticks": 1},
        }
    )
    n = world_ticks(seconds, cfg)
    with localcontext() as ctx:
        ctx.prec = 100  # exact for these magnitudes: only products of short decimals
        s, ts = Decimal(repr(seconds)), Decimal(repr(time_scale))
        assert n * ts >= s * 10  # n ticks cover the configured world seconds (Q-ALN-6)
        assert (n - 1) * ts < s * 10  # and one tick fewer would not
