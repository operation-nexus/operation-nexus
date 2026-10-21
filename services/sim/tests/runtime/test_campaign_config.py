"""NX-122: one-place campaign config loader, and `rules` required on restore/recover."""

import dataclasses
from pathlib import Path

import pytest

from nexus.runtime.campaign_config import CampaignConfig, ConfigPaths, load_campaign_config
from nexus.runtime.config import ConfigError
from nexus.runtime.recovery import recover, restore

from .test_config import GOLDEN_CONFIG_HASH


def test_shipped_config_hash_and_rules(shipped_config: CampaignConfig) -> None:
    assert shipped_config.config_hash == GOLDEN_CONFIG_HASH
    rules = shipped_config.rules
    sim = shipped_config.balance.sim
    assert rules.world_dt == pytest.approx(sim.time_scale / sim.tick_hz)
    assert rules.speed_mps == {u.kind: u.speed_mps for u in shipped_config.catalog.units}
    assert rules.domain == {u.kind: u.domain for u in shipped_config.catalog.units}
    assert {n.id for n in shipped_config.theater.nodes} == set(rules.roads.pos)


def test_defaults_do_not_depend_on_the_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shipped_config: CampaignConfig
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_campaign_config().config_hash == shipped_config.config_hash


@pytest.mark.parametrize("part", ["balance", "units", "weapons", "roles", "theater"])
def test_a_missing_path_names_the_file(part: str, tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(ConfigError, match="nope"):
        load_campaign_config(dataclasses.replace(ConfigPaths(), **{part: missing}))


def test_restore_and_recover_require_rules(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="rules"):
        restore(tmp_path, tmp_path)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="rules"):
        recover(tmp_path, None)  # type: ignore[call-arg, arg-type]
