"""NX-122: one-place campaign config loader, and `rules` required on restore/recover; NX-150
part 2: the theater's facilities placed at campaign start."""

import dataclasses
from pathlib import Path

import pytest

from nexus.core import operations as ops
from nexus.core.fog import side_view
from nexus.core.world import Vec2, state_hash
from nexus.runtime.campaign_config import (
    CampaignConfig,
    ConfigPaths,
    load_campaign_config,
    start_campaign,
)
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config as shipped_config_with
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
    assert rules.landing_nodes == ("east-airbase", "haven", "static-rear", "west-airbase")
    assert (rules.bounds_m, rules.bingo_reserve_frac) == ((400_000.0, 240_000.0), 0.15)
    # NX-150: fow.track_fade_s 180 world s at 0.6 world s per tick is 300 ticks.
    assert (rules.track_every_ticks, rules.track_fade_ticks) == (5, 300)
    # NX-150 part 2b: fow.sigint_refresh_s 54 world s is 90 ticks; recon UAVs paint.
    assert rules.sigint_refresh_ticks == 90
    assert rules.painters == {"RECON_UAV", "ENEMY_RECON_UAV"}
    assert rules.sensor_radius_m.keys() == rules.stealth.keys() == rules.speed_mps.keys()
    assert (
        rules.min_speed_mps.keys()
        == rules.fuel_s.keys()
        == {u.kind for u in shipped_config.catalog.units if u.domain == "AIR"}
    )


CAMPAIGN = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
# content/theaters/strait-1.yaml `facilities`, in file order, at their base's position on its
# starting side; RADAR_SITE and the SAM variant emit (FOW-11), others never do (None).
STRAIT_1_FACILITIES = [
    (1, "RADAR_SITE", "COALITION", "west-airbase", None, True, Vec2(90_000, 120_000)),
    (2, "AIR_DEFENSE_SITE", "COALITION", "west-airbase", "SAM", True, Vec2(90_000, 120_000)),
    (3, "AIR_DEFENSE_SITE", "COALITION", "fob-n-w", "SHORT_RANGE", None, Vec2(130_000, 60_000)),
    (4, "AIR_DEFENSE_SITE", "COALITION", "fob-s-w", "SHORT_RANGE", None, Vec2(130_000, 180_000)),
    (5, "RADAR_SITE", "ENEMY", "east-airbase", None, True, Vec2(310_000, 120_000)),
    (6, "AIR_DEFENSE_SITE", "ENEMY", "east-airbase", "SAM", True, Vec2(310_000, 120_000)),
    (7, "AIR_DEFENSE_SITE", "ENEMY", "fob-n-e", "SHORT_RANGE", None, Vec2(290_000, 40_000)),
    (8, "AIR_DEFENSE_SITE", "ENEMY", "fob-s-e", "SHORT_RANGE", None, Vec2(290_000, 200_000)),
    (9, "RADAR_SITE", "ENEMY", "static-hq", None, True, Vec2(380_000, 120_000)),
]


def test_start_campaign_stamps_the_config_and_attaches_rules(
    shipped_config: CampaignConfig,
) -> None:
    world = start_campaign(CAMPAIGN, 77, shipped_config)
    assert (world.campaign.id, world.campaign.seed, world.campaign.tick) == (CAMPAIGN, 77, 0)
    assert world.campaign.config_hash == GOLDEN_CONFIG_HASH
    assert world.rules is shipped_config.rules
    assert (world.reserve_queue, world.respawn_left) == ([], {})
    facilities = [e for e in world.entities() if e.home is None]
    assert [
        (e.id, e.kind, e.side, e.base_id, e.variant, e.emitting, e.pos) for e in facilities
    ] == STRAIT_1_FACILITIES
    # the Static's opening garrison (Q-SIM-86): its quotas 6 + 4 + 4 + 8, after the facilities
    assert sorted(e.id for e in world.entities() if e.home) == list(range(10, 32))
    for e in facilities:  # base-owned, parked, at full hp (NX-124)
        hp = {"RADAR_SITE": 150, "AIR_DEFENSE_SITE": 150}[e.kind]
        assert (e.owner_kind, e.commander_id, e.hp, e.path, e.vel) == (
            "AI_GARRISON", None, hp, [], Vec2(0, 0)
        )  # fmt: skip
    # Facilities spawn with a full load; the variant picks the weapons (CONTRACTS, Q-SIM-65):
    # a radar none, SHORT_RANGE the gun only, SAM the gun then the missile.
    assert [(e.id, e.ammo, e.reload) for e in world.entities() if e.id in (1, 2, 3)] == [
        (1, [], []), (2, [400, 8], [0, 0]), (3, [400], [0]),
    ]  # fmt: skip
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


# --- NX-388, Q-DEV-21: gameplay kind tables and hidden 0/1 counts are balance keys ---


def test_kind_key_defaults_are_the_old_hard_coded_values(shipped_config: CampaignConfig) -> None:
    rules = shipped_config.rules
    dr, tr = rules.director, rules.tasking
    assert dr is not None and tr is not None and rules.campaign is not None
    assert rules.uncapturable == {"SANCTUARY", "BRIDGE"}
    assert rules.masked_bands == {"NOE", "LOW"}
    strategic = {"AIRBASE", "FOB", "PORT"}
    assert rules.campaign.strategic == tuple(
        sorted(n.id for n in shipped_config.theater.nodes if n.kind in strategic)
    )
    assert tr.join_excluded_jobs == {"PATROL"} and tr.overfill_point_jobs is False
    assert dr.max_ops == {"ALPHA": 1, "BRAVO": None}
    assert dr.proximity_tiers == {"ALPHA"}
    assert (dr.alpha_enter_cp, dr.scout_in_rear_max, dr.convoy_slots) == (0, 1, 1)


def overridden(**keys: object) -> CampaignConfig:
    return shipped_config_with({k.replace("__", "."): v for k, v in keys.items()})


def test_non_default_kind_keys_reach_the_rules() -> None:
    cfg = overridden(
        air__landing_node_kinds=["AIRBASE", "SANCTUARY", "FOB"],
        campaign__strategic_node_kinds=["AIRBASE"],
        capture__uncapturable_node_kinds=["BRIDGE"],
        fow__masked_alt_bands=["NOE"],
        director__tier__alpha_enter_cp=20,
        director__score__proximity_tiers=["ALPHA", "BRAVO"],
        director__provocation__scout_in_rear_max_per_window=3,
        director__pol__convoy_slots=2,
        director__max_ops__bravo=2,
        director__max_ops__alpha=None,
        tasking__overfill_point_jobs=True,
        tasking__join_excluded_jobs=[],
    )
    rules = cfg.rules
    dr, tr = rules.director, rules.tasking
    assert dr is not None and tr is not None and rules.campaign is not None
    assert {rules.node_kind[n] for n in rules.landing_nodes} == {"AIRBASE", "SANCTUARY", "FOB"}
    assert {rules.node_kind[n] for n in rules.campaign.strategic} == {"AIRBASE"}
    assert rules.uncapturable == {"BRIDGE"} and "haven" in rules.campaign.candidates
    assert rules.masked_bands == {"NOE"}
    assert dr.alpha_enter_cp == 20_000_000 and dr.proximity_tiers == {"ALPHA", "BRAVO"}
    assert (dr.scout_in_rear_max, dr.convoy_slots) == (3, 2)
    assert dr.max_ops == {"ALPHA": None, "BRAVO": 2}
    assert tr.overfill_point_jobs is True and tr.join_excluded_jobs == frozenset()


def test_landing_and_uncapturable_kinds_change_what_the_world_and_the_director_see() -> None:
    base = start_campaign(CAMPAIGN, 1, overridden())
    assert "fob-n-w" not in base.landing_bases("COALITION")
    assert "haven" not in ops.bases(side_view(base, "COALITION"), base.rules)  # type: ignore[arg-type]
    cfg = overridden(
        air__landing_node_kinds=["AIRBASE", "SANCTUARY", "FOB"],
        capture__uncapturable_node_kinds=["BRIDGE"],
    )
    w = start_campaign(CAMPAIGN, 1, cfg)
    assert "fob-n-w" in w.landing_bases("COALITION")  # an aircraft may land at a FOB it owns
    assert "haven" in ops.bases(side_view(w, "COALITION"), cfg.rules)  # no longer "not a base"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("air.landing_node_kinds", ["AIRBASE", "FORT"]),
        ("air.landing_node_kinds", []),
        ("campaign.strategic_node_kinds", ["FORT"]),
        ("capture.uncapturable_node_kinds", ["FORT"]),
        ("capture.uncapturable_node_kinds", ["SANCTUARY"]),  # BRIDGE must stay in
        ("capture.uncapturable_node_kinds", []),
        ("fow.masked_alt_bands", ["TREETOP"]),
        ("tasking.join_excluded_jobs", ["PARADE"]),
        ("director.score.proximity_tiers", ["CHARLIE"]),
        ("director.max_ops.alpha", 0),
        ("director.tier.alpha_enter_cp", 60),
    ],
)
def test_the_loader_rejects_an_unknown_kind_or_a_bad_count(key: str, value: object) -> None:
    with pytest.raises(ConfigError):
        shipped_config_with({key: value})
