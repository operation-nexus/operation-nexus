"""NX-122: one-place campaign config loader, and `rules` required on restore/recover."""

import dataclasses
from pathlib import Path

import pytest

from nexus.core.world import state_hash
from nexus.runtime.campaign_config import (
    CampaignConfig,
    ConfigPaths,
    load_campaign_config,
    start_campaign,
)
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
    # strait-1: aircraft land at their side's AIRBASE and SANCTUARY nodes only, never at an FOB,
    # the HQ or a neutral node (NX-368).
    assert rules.landing_bases == {
        "COALITION": ("haven", "west-airbase"),
        "ENEMY": ("east-airbase",),
    }
    assert (rules.bounds_m, rules.bingo_reserve_frac) == ((400_000.0, 240_000.0), 0.15)
    assert (
        rules.min_speed_mps.keys()
        == rules.fuel_s.keys()
        == {u.kind for u in shipped_config.catalog.units if u.domain == "AIR"}
    )


CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"


def test_start_campaign_stamps_the_config_and_attaches_rules(
    shipped_config: CampaignConfig,
) -> None:
    world = start_campaign(CAMPAIGN, 77, shipped_config)
    assert (world.campaign.id, world.campaign.seed, world.campaign.tick) == (CAMPAIGN, 77, 0)
    assert world.campaign.config_hash == GOLDEN_CONFIG_HASH
    assert world.rules is shipped_config.rules
    assert (len(world), world.reserve_queue, world.respawn_left) == (0, [], {})
    # Without a config it loads the shipped files: the same world.
    default = start_campaign(CAMPAIGN, 77)
    assert default.campaign.config_hash == GOLDEN_CONFIG_HASH
    assert state_hash(default) == state_hash(world)
    assert state_hash(start_campaign(CAMPAIGN, 78, shipped_config)) != state_hash(world)


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
