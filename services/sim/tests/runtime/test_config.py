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

from .test_operations import GOLDEN_OPERATIONS_HASH as OPERATIONS_HASH
from .test_theater import GOLDEN_THEATER_HASH as THEATER_HASH
from .test_units import GOLDEN_UNITS_HASH as UNITS_HASH

DEFAULT = Path(__file__).resolve().parents[4] / "balance" / "default.yaml"
VALID = """\
schema_version: 1
sim:
  tick_hz: 10
  time_scale: 6.0
  snapshot_every_ticks: 300
air:
  bingo_reserve_frac: 0.15
  orbit_period_s: 120.0
  landing_node_kinds: [AIRBASE, SANCTUARY]
fow:
  track_every_ticks: 5
  track_fade_s: 180.0
  sigint_range_mult: 1.5
  sigint_refresh_s: 54.0
  sigint_cell_m: 10000
  sigint_size_m_min: 3
  sigint_size_l_min: 7
  paint_range_m: 20000.0
  mask_cell_m: 1000
  masked_alt_bands: [NOE, LOW]
slots:
  max_live_per_commander: 1
  respawn_delay_s: 20
  max_viewer_units: 500
  reserve_queue_max: 1000
  queue_idle_min: 15
logistics:
  node_max_stock:
    AIRBASE: 2000
    BRIDGE: 0
    FOB: 1000
    HQ: 2000
    PORT: 1000
  starve_threshold: 0.25
  stock_target_frac: 0.8
  truck_cargo: 100
  unload_rate: 1.0
  rearm_rate: 0.5
  forward_deploy_min_surplus: 50
  starved_loadout:
    fuel_frac: 0.5
  loadout_cost:
    ENEMY_ARMOR: 15
    ENEMY_CONVOY: 0
    ENEMY_FIGHTER: 20
    ENEMY_RECON_UAV: 5
    ENEMY_STRIKE_FIGHTER: 20
    GARRISON_INFANTRY: 5
    LOGI_TRUCK: 0
    RECON_UAV: 5
    STRIKE_FIGHTER: 20
  repair_rate:
    AIRBASE: 1.0
    FOB: 0.5
    HQ: 1.0
    PORT: 1.0
    SANCTUARY: 2.0
  facility_repair_hp_per_stock: 10
  facility_rearm_cost: 10
  ammo_loadout_share: 0.5
  starve_hp_drain_per_min: 5
  defense_repair_hp_per_stock: 2
capture:
  radius_m: 2000.0
  time_s: 120.0
  multi_unit_exponent: 0.5
  quiet_floor: 0.6
  quiet_ref: 50
  min_time_s: 30.0
  logi_weight: 0.5
  garrison_mult: 3.0
  empty_base_mult: 0.5
  decay_per_s: 0.008333333333333333
  min_progress_per_tick: 1
  defense_hp:
    AIRBASE: 500
    FOB: 300
    HQ: 800
    PORT: 300
    SANCTUARY: 1000
  sanctuary_repair_hp_per_s: 1.0
  uncapturable_node_kinds: [SANCTUARY, BRIDGE]
  requires_defenses_down: true
  air_counts: false
  air_weight: 1.0
  quiet_sides: [COALITION]
combat:
  pk_cap: 0.95
  track_quality:
    track: 1.0
    painted: 1.25
  range:
    full_pk_frac: 0.5
    min_mult: 0.5
  pk_mult:
    terrain_masked: 0.5
  damage_state:
    damaged_below: 0.70
    mission_kill_below: 0.35
    disabled_below: 0.10
    damaged_speed_mult: 0.75
    damaged_sensor_mult: 0.8
  disabled_timeout_s: 600
  assist_window_s: 120
  min_damage: 1
  crew_survival:
    ENEMY_ARMOR: 0.60
    ENEMY_CONVOY: 0.70
    ENEMY_FIGHTER: 0.75
    ENEMY_STRIKE_FIGHTER: 0.75
    GARRISON_INFANTRY: 0.50
    LOGI_TRUCK: 0.70
    STRIKE_FIGHTER: 0.75
  crew_marker_min: 10
  facility_indestructible: true
campaign:
  time_limit_h: 72
  victory_node_frac: 0.80
  strategic_node_kinds: [AIRBASE, FOB, PORT]
  victory_hold_min: 30
  defeat:
    hold_min: 30
  objective_period_min: 15
  objective_mode: timed
  objective_pick: uniform
  victory:
    hq_capture: true
  idle_floor:
    enabled: true
    sanctuary_min_hp: 1
  score:
    average_weight: 50
    final_weight: 50
    objective_points: 5
  momentum:
    nodes_weight: 70
    supply_weight: 30
  night_progress_cap_nodes_per_h: 0.16666666666666666
tasking:
  reeval_every_ticks: 50
  claim_lease_s: 120
  expire_min: 15
  priority:
    defend: 60
    resupply: 50
    assist_objective: 45
    strike: 40
    scout: 30
    escort_convoy: 40
    stage: 20
    capture: 45
    patrol: 15
    intercept: 45
  static_offense_min_tier: ALPHA
  urgency_max: 2.0
  priority_aging_per_min: 1
  slots:
    defend: 2
    strike: 2
    assist_objective: 4
    scout: 1
    escort_convoy: 2
    patrol: 2
    intercept: 1
  resupply_stock_per_slot: 100
  resupply_slots_max: 3
  defend_radius_m: 10000
  counterattack_window_min: 15
  scout_cooldown_min: 5
  scout_post_interval_min: 2
  scout_open_max: 3
  capture_max_restarts: 3
  follow_station_m:
    escort: 500
    column: 200
    overwatch: 3000
    wingman: 1000
  escort_threat_memory_s: 60
  escort_leash_m: 10000
  follow_hold_slack: 2
  overfill_factor: 2
  overfill_point_jobs: false
  join_excluded_jobs: [PATROL]
  scout_blob_runs: 2
  scout_urgency: {small: 1.0, medium: 1.5, large: 2.0}
  strike_urgency_per_threat: 0.01
  strike_max_scaled_slots: 3
  strike_idle_targets_max: 2
  strike_idle_targets_min_tier: ALPHA
  patrol_max_nodes: 3
  patrol_orbit_m: 5000
  patrol_dwell_s: 300
  stock_urgency: 0.5
  stock_front_bonus: 0.25
director:
  window_s: 60
  cp:
    unit_value:
      STRIKE_FIGHTER: 10
      RECON_UAV: 3
      LOGI_TRUCK: 2
      GARRISON_INFANTRY: 2
    ema_window_s: 300
  tier:
    alpha_enter_cp: 0
    bravo_enter_cp: 60
    exit_ratio: 0.8
    min_dwell_s: 600
  provocation:
    half_life_s: 900
    escalate_threshold: 10
    bravo_threshold: 40
    scout_in_rear_max_per_window: 1
    weights:
      unit_destroyed: 5
      unit_damaged: 1
      recon_destroyed: 2
      recon_damaged: 0
      convoy_hit: 3
      facility_damaged: 3
      facility_disabled: 8
      base_captured: 15
      scout_in_rear: 2
      redemption:
        support: 1
        cosmetic: 0
  budget:
    pattern_of_life: 10
    alpha: 30
    bravo: 80
  max_spawns_per_window: 6
  max_live_units:
    pattern_of_life: 24
    alpha: 40
    bravo: 70
  op_priority: {RETAKE: 1.2, OFFENSIVE: 1.0, RECON: 0.5}
  score:
    target_value: {AIRBASE: 1.5, FOB: 1.0, PORT: 1.0, SANCTUARY: 2.0}
    weakness_max: 2.0
    own_node_value: 1.0
    weakness_min: 1.0
    stale_factor: 1.0
    provocation_proximity: 1.5
    proximity_tiers: [ALPHA]
  memory:
    half_life_s: 1800
    factor: 1.0
    weights: {convoy_hit: 1, radar_hit: 1, scout_lost: 1, node_lost: 1}
  decoy_blink: {dark_s: 120, cooldown_s: 600, max_per_window: 1}
  recon: {loiter_s: 600, loiter_radius_m: 5000, grid_m: 10000, memory_s: 3600}
  intercept: {radius_m: 30000, reaction_s: 60, pol_linger_s: 600, leash_m: 80000, lost_s: 120}
  max_ops:
    alpha: 1
    bravo: null
  idle_retire_s: 600
  adaptation_up_above: 0
  reinforce_damage_above: 0
  escort_min_convoys: 1
  frontline_hops: 1
  job_urgency: 1.0
  adaptation_down_below: 1
  noise_scale: 0.1
  retake_window_min: 30
  garrison:
    replace_per_window: 1
    kinds:
      FOB: [ENEMY_ARMOR]
      AIRBASE: [ENEMY_FIGHTER, ENEMY_ARMOR]
      HQ: [ENEMY_ARMOR]
  pol:
    patrol_period_s: 1800
    convoy_period_s: 3600
    offensive_period_s: 21600
    patrol_slots: 1
    patrols_per_base: 1
    convoys_per_period: 1
    offensives_per_period: 1
    convoy_cost: 0
    convoy_slots: 1
    convoy_kind: ENEMY_CONVOY
"""
# Pinned from this implementation's first run (NX-367: balance, units, theater; re-pinned NX-121
# for speed_mps, NX-122 for slots and again for the GP-3 cap and queue, NX-368 for air fuel and
# orbit, NX-150 for sensors, stealth and fow, passive ranges, and SIGINT and paint keys, NX-123
# for logistics and the rear source, NX-123 part 2 for loadouts, rearm and forward deploy, NX-125
# for capture, NX-126 for campaign, NX-124 for combat and its assist window, and NX-124 part 2 for
# repair, crew and the damage multipliers, NX-124 part 3 for defense hp and the defeat hold, and
# NX-374 for the tasking keys and again for follow and escort, NX-155 for the director, and NX-157
# for the Pattern of Life keys and the garrison operation, NX-389 for the forward stock keys,
# NX-388 part 2 for the Q-CFG-16 rule options); a
# change means every config_hash moved.
GOLDEN_CONFIG_HASH = "0a81a80113e039490f339ec3bc371c60ec4dbf0dfc98fcb982a7c8d30f204a89"
AIR = {
    "bingo_reserve_frac": 0.15,
    "orbit_period_s": 120.0,
    "landing_node_kinds": ["AIRBASE", "SANCTUARY"],
}
SLOTS = {
    "max_live_per_commander": 1,
    "respawn_delay_s": 20,
    "max_viewer_units": 500,
    "reserve_queue_max": 1000,
    "queue_idle_min": 15,
}
FOW = {
    "track_every_ticks": 5,
    "track_fade_s": 180.0,
    "sigint_range_mult": 1.5,
    "sigint_refresh_s": 54.0,
    "sigint_cell_m": 10000,
    "sigint_size_m_min": 3,
    "sigint_size_l_min": 7,
    "paint_range_m": 20000.0,
    "mask_cell_m": 1000,
    "masked_alt_bands": ["NOE", "LOW"],
}
LOGISTICS = {
    "node_max_stock": {"AIRBASE": 2000, "BRIDGE": 0, "FOB": 1000, "HQ": 2000, "PORT": 1000},
    "starve_threshold": 0.25,
    "stock_target_frac": 0.8,
    "truck_cargo": 100,
    "unload_rate": 1.0,
    "rearm_rate": 0.5,
    "forward_deploy_min_surplus": 50,
    "starved_loadout": {"fuel_frac": 0.5},
    "loadout_cost": {
        "ENEMY_ARMOR": 15,
        "ENEMY_CONVOY": 0,
        "ENEMY_FIGHTER": 20,
        "ENEMY_RECON_UAV": 5,
        "ENEMY_STRIKE_FIGHTER": 20,
        "GARRISON_INFANTRY": 5,
        "LOGI_TRUCK": 0,
        "RECON_UAV": 5,
        "STRIKE_FIGHTER": 20,
    },
    "repair_rate": {"AIRBASE": 1.0, "FOB": 0.5, "HQ": 1.0, "PORT": 1.0, "SANCTUARY": 2.0},
    "facility_repair_hp_per_stock": 10,
    "facility_rearm_cost": 10,
    "ammo_loadout_share": 0.5,
    "starve_hp_drain_per_min": 5,
    "defense_repair_hp_per_stock": 2,
}
CAPTURE = {
    "radius_m": 2000.0,
    "time_s": 120.0,
    "multi_unit_exponent": 0.5,
    "quiet_floor": 0.6,
    "quiet_ref": 50,
    "min_time_s": 30.0,
    "logi_weight": 0.5,
    "garrison_mult": 3.0,
    "empty_base_mult": 0.5,
    "decay_per_s": 0.008333333333333333,
    "min_progress_per_tick": 1,
    "defense_hp": {"AIRBASE": 500, "FOB": 300, "HQ": 800, "PORT": 300, "SANCTUARY": 1000},
    "sanctuary_repair_hp_per_s": 1.0,
    "uncapturable_node_kinds": ["SANCTUARY", "BRIDGE"],
    "requires_defenses_down": True,
    "air_counts": False,
    "air_weight": 1.0,
    "quiet_sides": ["COALITION"],
}
COMBAT = {
    "pk_cap": 0.95,
    "track_quality": {"track": 1.0, "painted": 1.25},
    "range": {"full_pk_frac": 0.5, "min_mult": 0.5},
    "pk_mult": {"terrain_masked": 0.5},
    "damage_state": {
        "damaged_below": 0.70,
        "mission_kill_below": 0.35,
        "disabled_below": 0.10,
        "damaged_speed_mult": 0.75,
        "damaged_sensor_mult": 0.8,
    },
    "disabled_timeout_s": 600,
    "assist_window_s": 120,
    "min_damage": 1,
    "crew_survival": {
        "ENEMY_ARMOR": 0.60,
        "ENEMY_CONVOY": 0.70,
        "ENEMY_FIGHTER": 0.75,
        "ENEMY_STRIKE_FIGHTER": 0.75,
        "GARRISON_INFANTRY": 0.50,
        "LOGI_TRUCK": 0.70,
        "STRIKE_FIGHTER": 0.75,
    },
    "crew_marker_min": 10,
    "facility_indestructible": True,
}
CAMPAIGN = {
    "time_limit_h": 72,
    "victory_node_frac": 0.80,
    "strategic_node_kinds": ["AIRBASE", "FOB", "PORT"],
    "victory_hold_min": 30,
    "defeat": {"hold_min": 30},
    "objective_period_min": 15,
    "objective_mode": "timed",
    "objective_pick": "uniform",
    "victory": {"hq_capture": True},
    "idle_floor": {"enabled": True, "sanctuary_min_hp": 1},
    "score": {"average_weight": 50, "final_weight": 50, "objective_points": 5},
    "momentum": {"nodes_weight": 70, "supply_weight": 30},
    "night_progress_cap_nodes_per_h": 0.16666666666666666,
}
TASKING = {
    "reeval_every_ticks": 50,
    "claim_lease_s": 120,
    "expire_min": 15,
    "priority": {
        "defend": 60,
        "resupply": 50,
        "assist_objective": 45,
        "strike": 40,
        "scout": 30,
        "escort_convoy": 40,
        "stage": 20,
        "capture": 45,
        "patrol": 15,
        "intercept": 45,
    },
    "static_offense_min_tier": "ALPHA",
    "urgency_max": 2.0,
    "priority_aging_per_min": 1,
    "slots": {
        "defend": 2,
        "strike": 2,
        "assist_objective": 4,
        "scout": 1,
        "escort_convoy": 2,
        "patrol": 2,
        "intercept": 1,
    },
    "resupply_stock_per_slot": 100,
    "resupply_slots_max": 3,
    "defend_radius_m": 10000,
    "counterattack_window_min": 15,
    "scout_cooldown_min": 5,
    "scout_post_interval_min": 2,
    "capture_max_restarts": 3,
    "scout_open_max": 3,
    "follow_station_m": {"escort": 500, "column": 200, "overwatch": 3000, "wingman": 1000},
    "escort_threat_memory_s": 60,
    "escort_leash_m": 10000,
    "follow_hold_slack": 2,
    "overfill_factor": 2,
    "overfill_point_jobs": False,
    "join_excluded_jobs": ["PATROL"],
    "scout_blob_runs": 2,
    "scout_urgency": {"small": 1.0, "medium": 1.5, "large": 2.0},
    "strike_urgency_per_threat": 0.01,
    "strike_max_scaled_slots": 3,
    "strike_idle_targets_max": 2,
    "strike_idle_targets_min_tier": "ALPHA",
    "patrol_max_nodes": 3,
    "patrol_orbit_m": 5000,
    "patrol_dwell_s": 300,
    "stock_urgency": 0.5,
    "stock_front_bonus": 0.25,
}
DIRECTOR = {
    "window_s": 60,
    "cp": {
        "unit_value": {
            "STRIKE_FIGHTER": 10,
            "RECON_UAV": 3,
            "LOGI_TRUCK": 2,
            "GARRISON_INFANTRY": 2,
        },
        "ema_window_s": 300,
    },
    "tier": {"alpha_enter_cp": 0, "bravo_enter_cp": 60, "exit_ratio": 0.8, "min_dwell_s": 600},
    "provocation": {
        "half_life_s": 900,
        "escalate_threshold": 10,
        "bravo_threshold": 40,
        "scout_in_rear_max_per_window": 1,
        "weights": {
            "unit_destroyed": 5,
            "unit_damaged": 1,
            "recon_destroyed": 2,
            "recon_damaged": 0,
            "convoy_hit": 3,
            "facility_damaged": 3,
            "facility_disabled": 8,
            "base_captured": 15,
            "scout_in_rear": 2,
            "redemption": {"support": 1, "cosmetic": 0},
        },
    },
    "budget": {"pattern_of_life": 10, "alpha": 30, "bravo": 80},
    "max_spawns_per_window": 6,
    "max_live_units": {"pattern_of_life": 40, "alpha": 40, "bravo": 70},
    "op_priority": {
        "RETAKE": 1.2,
        "OFFENSIVE": 1.0,
        "ESCORT_CONVOYS": 0.8,
        "REINFORCE_IADS": 0.7,
        "PROBE": 0.6,
        "RECON": 0.5,
        "DECOY_BLINK": 0.3,
        "GARRISON_UPKEEP": 0.9,
    },
    "score": {
        "target_value": {"AIRBASE": 1.5, "FOB": 1.0, "PORT": 1.0, "SANCTUARY": 2.0},
        "weakness_max": 2.0,
        "own_node_value": 1.0,
        "weakness_min": 1.0,
        "stale_factor": 1.0,
        "provocation_proximity": 1.5,
        "proximity_tiers": ["ALPHA"],
    },
    "memory": {
        "half_life_s": 1800,
        "factor": 1.0,
        "weights": {"convoy_hit": 1, "radar_hit": 1, "scout_lost": 1, "node_lost": 1},
    },
    "decoy_blink": {"dark_s": 120, "cooldown_s": 600, "max_per_window": 1},
    "recon": {"loiter_s": 600, "loiter_radius_m": 5000, "grid_m": 10000, "memory_s": 3600},
    "intercept": {
        "radius_m": 30000,
        "reaction_s": 60,
        "pol_linger_s": 600,
        "leash_m": 80000,
        "lost_s": 120,
    },
    "max_ops": {"alpha": 1, "bravo": None},
    "idle_retire_s": 600,
    "adaptation_up_above": 0,
    "reinforce_damage_above": 0,
    "escort_min_convoys": 1,
    "frontline_hops": 1,
    "job_urgency": 1.0,
    "adaptation_down_below": 1,
    "noise_scale": 0.1,
    "retake_window_min": 30,
    "garrison": {
        "replace_per_window": 1,
        "kinds": {
            "FOB": ["ENEMY_ARMOR"],
            "AIRBASE": ["ENEMY_FIGHTER", "ENEMY_ARMOR"],
            "HQ": ["ENEMY_ARMOR"],
        },
    },
    "pol": {
        "patrol_period_s": 1800,
        "convoy_period_s": 3600,
        "offensive_period_s": 21600,
        "convoy_kind": "ENEMY_CONVOY",
        "patrol_slots": 1,
        "patrols_per_base": 1,
        "convoys_per_period": 1,
        "offensives_per_period": 1,
        "convoy_cost": 0,
        "convoy_slots": 1,
    },
}
CFG = BalanceConfig.model_validate(
    {
        "schema_version": 1,
        "sim": {"tick_hz": 10, "time_scale": 6.0, "snapshot_every_ticks": 300},
        "slots": SLOTS,
        "air": AIR,
        "fow": FOW,
        "logistics": LOGISTICS,
        "capture": CAPTURE,
        "combat": COMBAT,
        "campaign": CAMPAIGN,
        "tasking": TASKING,
        "director": DIRECTOR,
    }
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
    assert (
        config_hash(balance_hash(DEFAULT), UNITS_HASH, OPERATIONS_HASH, THEATER_HASH)
        == GOLDEN_CONFIG_HASH
    )
    # Order is part of the hash (§4.4): swapping the parts gives another hash.
    assert (
        config_hash(THEATER_HASH, UNITS_HASH, OPERATIONS_HASH, balance_hash(DEFAULT))
        != GOLDEN_CONFIG_HASH
    )


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("schema_version: 1\n", "schema_version"),
        ("  tick_hz: 10\n", "sim.tick_hz"),
        ("  time_scale: 6.0\n", "sim.time_scale"),
        ("  snapshot_every_ticks: 300\n", "sim.snapshot_every_ticks"),
        ("  max_live_per_commander: 1\n", "slots.max_live_per_commander"),
        ("  respawn_delay_s: 20\n", "slots.respawn_delay_s"),
        ("  max_viewer_units: 500\n", "slots.max_viewer_units"),
        ("  reserve_queue_max: 1000\n", "slots.reserve_queue_max"),
        ("  queue_idle_min: 15\n", "slots.queue_idle_min"),
        ("  bingo_reserve_frac: 0.15\n", "air.bingo_reserve_frac"),
        ("  orbit_period_s: 120.0\n", "air.orbit_period_s"),
        ("  track_every_ticks: 5\n", "fow.track_every_ticks"),
        ("  track_fade_s: 180.0\n", "fow.track_fade_s"),
        ("  sigint_range_mult: 1.5\n", "fow.sigint_range_mult"),
        ("  sigint_refresh_s: 54.0\n", "fow.sigint_refresh_s"),
        ("  sigint_cell_m: 10000\n", "fow.sigint_cell_m"),
        ("  paint_range_m: 20000.0\n", "fow.paint_range_m"),
        ("  mask_cell_m: 1000\n", "fow.mask_cell_m"),
        ("  sigint_size_m_min: 3\n", "fow.sigint_size_m_min"),
        ("  sigint_size_l_min: 7\n", "fow.sigint_size_l_min"),
        ("  starve_threshold: 0.25\n", "logistics.starve_threshold"),
        ("  stock_target_frac: 0.8\n", "logistics.stock_target_frac"),
        ("  stock_urgency: 0.5\n", "tasking.stock_urgency"),
        ("  stock_front_bonus: 0.25\n", "tasking.stock_front_bonus"),
        ("  truck_cargo: 100\n", "logistics.truck_cargo"),
        ("  unload_rate: 1.0\n", "logistics.unload_rate"),
        ("    HQ: 2000\n", "logistics.node_max_stock.HQ"),
        ("  rearm_rate: 0.5\n", "logistics.rearm_rate"),
        ("  forward_deploy_min_surplus: 50\n", "logistics.forward_deploy_min_surplus"),
        ("  starved_loadout:\n    fuel_frac: 0.5\n", "logistics.starved_loadout"),
        ("    STRIKE_FIGHTER: 20\n", "logistics.loadout_cost.STRIKE_FIGHTER"),
        ("  pk_cap: 0.95\n", "combat.pk_cap"),
        ("    painted: 1.25\n", "combat.track_quality.painted"),
        ("    min_mult: 0.5\n", "combat.range.min_mult"),
        ("    disabled_below: 0.10\n", "combat.damage_state.disabled_below"),
        ("    damaged_speed_mult: 0.75\n", "combat.damage_state.damaged_speed_mult"),
        ("    damaged_sensor_mult: 0.8\n", "combat.damage_state.damaged_sensor_mult"),
        ("    GARRISON_INFANTRY: 0.50\n", "combat.crew_survival.GARRISON_INFANTRY"),
        ("  crew_marker_min: 10\n", "combat.crew_marker_min"),
        ("    SANCTUARY: 2.0\n", "logistics.repair_rate.SANCTUARY"),
        ("  facility_repair_hp_per_stock: 10\n", "logistics.facility_repair_hp_per_stock"),
        ("  facility_rearm_cost: 10\n", "logistics.facility_rearm_cost"),
        ("  ammo_loadout_share: 0.5\n", "logistics.ammo_loadout_share"),
        ("  starve_hp_drain_per_min: 5\n", "logistics.starve_hp_drain_per_min"),
        ("  defense_repair_hp_per_stock: 2\n", "logistics.defense_repair_hp_per_stock"),
        ("    SANCTUARY: 1000\n", "capture.defense_hp.SANCTUARY"),
        ("  sanctuary_repair_hp_per_s: 1.0\n", "capture.sanctuary_repair_hp_per_s"),
        ("  defeat:\n    hold_min: 30\n", "campaign.defeat"),
        ("  disabled_timeout_s: 600\n", "combat.disabled_timeout_s"),
        ("  assist_window_s: 120\n", "combat.assist_window_s"),
        ("  min_damage: 1\n", "combat.min_damage"),
        ("  min_progress_per_tick: 1\n", "capture.min_progress_per_tick"),
        ("  objective_period_min: 15\n", "campaign.objective_period_min"),
        ("  objective_mode: timed\n", "campaign.objective_mode"),
        ("  objective_pick: uniform\n", "campaign.objective_pick"),
        ("  victory:\n    hq_capture: true\n", "campaign.victory"),
        ("    sanctuary_min_hp: 1\n", "campaign.idle_floor.sanctuary_min_hp"),
        ("  requires_defenses_down: true\n", "capture.requires_defenses_down"),
        ("  air_counts: false\n", "capture.air_counts"),
        ("  air_weight: 1.0\n", "capture.air_weight"),
        ("  quiet_sides: [COALITION]\n", "capture.quiet_sides"),
        ("  facility_indestructible: true\n", "combat.facility_indestructible"),
        ("    objective_points: 5\n", "campaign.score.objective_points"),
        ("    final_weight: 50\n", "campaign.score.final_weight"),
        ("    supply_weight: 30\n", "campaign.momentum.supply_weight"),
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
        ("bingo_reserve_frac: 0.15", "bingo_reserve_frac: 1.5", "air.bingo_reserve_frac"),
        ("bingo_reserve_frac: 0.15", "bingo_reserve_frac: -0.1", "air.bingo_reserve_frac"),
        ("orbit_period_s: 120.0", "orbit_period_s: 0", "air.orbit_period_s"),
        ("track_every_ticks: 5", "track_every_ticks: 0", "fow.track_every_ticks"),
        ("track_fade_s: 180.0", "track_fade_s: 0", "fow.track_fade_s"),
        ("sigint_range_mult: 1.5", "sigint_range_mult: 0", "fow.sigint_range_mult"),
        ("sigint_refresh_s: 54.0", "sigint_refresh_s: 0", "fow.sigint_refresh_s"),
        ("sigint_cell_m: 10000", "sigint_cell_m: 0", "fow.sigint_cell_m"),
        ("sigint_cell_m: 10000", "sigint_cell_m: 10000.5", "fow.sigint_cell_m"),
        ("paint_range_m: 20000.0", "paint_range_m: 0", "fow.paint_range_m"),
        ("mask_cell_m: 1000", "mask_cell_m: 10", "fow.mask_cell_m"),  # a cell count in the millions
        ("mask_cell_m: 1000", "mask_cell_m: 100000", "fow.mask_cell_m"),
        ("min_damage: 1", "min_damage: 0", "combat.min_damage"),
        ("min_progress_per_tick: 1", "min_progress_per_tick: 0", "capture.min_progress_per_tick"),
        ("sigint_size_m_min: 3", "sigint_size_m_min: 1", "fow.sigint_size_m_min"),
        ("sigint_size_l_min: 7", "sigint_size_l_min: 3", "fow.sigint_size_l_min"),  # == M
        ("sigint_size_l_min: 7", "sigint_size_l_min: 7.0", "fow.sigint_size_l_min"),
        # NX-155: the Director's thresholds are ordered (Q-TD-1), and a CP value cannot be left out
        ("bravo_threshold: 40", "bravo_threshold: 10", "director.provocation.bravo_threshold"),
        ("bravo_threshold: 40", "bravo_threshold: 5", "director.provocation.bravo_threshold"),
        ("      LOGI_TRUCK: 2\n", "", "director.cp.unit_value.LOGI_TRUCK"),
        ("exit_ratio: 0.8", "exit_ratio: 1.5", "director.tier.exit_ratio"),
        ("window_s: 60", "window_s: 0", "director.window_s"),
        # NX-389: the forward stock target is a fraction; stocking urgencies stay below 1.0
        ("stock_target_frac: 0.8", "stock_target_frac: 1.2", "logistics.stock_target_frac"),
        ("stock_urgency: 0.5", "stock_urgency: 0", "tasking.stock_urgency"),
        ("stock_urgency: 0.5", "stock_urgency: 1.0", "tasking.stock_urgency"),
        ("stock_front_bonus: 0.25", "stock_front_bonus: -0.1", "tasking.stock_front_bonus"),
        ("stock_front_bonus: 0.25", "stock_front_bonus: 1.0", "tasking.stock_front_bonus"),
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
        VALID.replace(
            "  reserve_queue_max: 1000\n", "  reserve_queue_max: 1000\n  respawn_delay_s: 20\n"
        ),  # nested, same value
        VALID.replace("sim:\n", "sim:\n  time_scale: 7.0\n"),  # nested, earlier and different
    ],
)
def test_duplicate_keys_are_rejected(tmp_path: Path, text: str) -> None:
    path = write(tmp_path, text)
    with pytest.raises(
        ConfigError,
        match=rf"(?s)^{path}: .*duplicate key '(schema_version|respawn_delay_s|time_scale)'",
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
        "slots: {respawn_delay_s: 20, max_live_per_commander: 1, reserve_queue_max: 1000,\n"
        "  max_viewer_units: 500, queue_idle_min: 15}\n"
        "air: {orbit_period_s: 120.0, bingo_reserve_frac: 0.15,\n"
        "  landing_node_kinds: [AIRBASE, SANCTUARY]}\n"
        "fow: {track_fade_s: 180.0, track_every_ticks: 5, paint_range_m: 20000.0,\n"
        "  mask_cell_m: 1000, masked_alt_bands: [NOE, LOW],\n"
        "  sigint_cell_m: 10000, sigint_refresh_s: 54.0, sigint_range_mult: 1.5,\n"
        "  sigint_size_l_min: 7, sigint_size_m_min: 3}\n"
        "logistics: {unload_rate: 1.0, truck_cargo: 100, starve_threshold: 0.25,\n"
        "  stock_target_frac: 0.8,\n"
        "  rearm_rate: 0.5, forward_deploy_min_surplus: 50, starved_loadout: {fuel_frac: 0.5},\n"
        "  loadout_cost: {STRIKE_FIGHTER: 20, RECON_UAV: 5, LOGI_TRUCK: 0, GARRISON_INFANTRY: 5,\n"
        "    ENEMY_FIGHTER: 20, ENEMY_STRIKE_FIGHTER: 20, ENEMY_RECON_UAV: 5, ENEMY_ARMOR: 15,\n"
        "    ENEMY_CONVOY: 0},\n"
        "  repair_rate: {SANCTUARY: 2.0, PORT: 1.0, HQ: 1.0, FOB: 0.5, AIRBASE: 1.0},\n"
        "  facility_repair_hp_per_stock: 10, facility_rearm_cost: 10, ammo_loadout_share: 0.5,\n"
        "  starve_hp_drain_per_min: 5, defense_repair_hp_per_stock: 2,\n"
        "  node_max_stock: {PORT: 1000, HQ: 2000, FOB: 1000, BRIDGE: 0, AIRBASE: 2000}}\n"
        "capture: {radius_m: 2000.0, time_s: 120.0, multi_unit_exponent: 0.5, quiet_floor: 0.6,\n"
        "  quiet_ref: 50, min_time_s: 30.0, logi_weight: 0.5, garrison_mult: 3.0,\n"
        "  empty_base_mult: 0.5, decay_per_s: 0.008333333333333333,\n"
        "  min_progress_per_tick: 1,\n"
        "  defense_hp: {AIRBASE: 500, FOB: 300, HQ: 800, PORT: 300, SANCTUARY: 1000},\n"
        "  sanctuary_repair_hp_per_s: 1.0, uncapturable_node_kinds: [SANCTUARY, BRIDGE],\n"
        "  quiet_sides: [COALITION], air_weight: 1.0, air_counts: false,\n"
        "  requires_defenses_down: true}\n"
        "combat: {pk_cap: 0.95, track_quality: {painted: 1.25, track: 1.0},\n"
        "  range: {min_mult: 0.5, full_pk_frac: 0.5}, pk_mult: {terrain_masked: 0.5},\n"
        "  damage_state: {disabled_below: 0.10, damaged_below: 0.70, mission_kill_below: 0.35,\n"
        "    damaged_speed_mult: 0.75, damaged_sensor_mult: 0.8},\n"
        "  crew_survival: {STRIKE_FIGHTER: 0.75, LOGI_TRUCK: 0.70, GARRISON_INFANTRY: 0.50,\n"
        "    ENEMY_STRIKE_FIGHTER: 0.75, ENEMY_FIGHTER: 0.75, ENEMY_CONVOY: 0.70,\n"
        "    ENEMY_ARMOR: 0.60},\n"
        "  crew_marker_min: 10, disabled_timeout_s: 600, assist_window_s: 120,\n"
        "  min_damage: 1, facility_indestructible: true}\n"
        "campaign: {momentum: {supply_weight: 30, nodes_weight: 70}, objective_mode: timed,\n"
        "  score: {objective_points: 5, final_weight: 50, average_weight: 50},\n"
        "  objective_period_min: 15,\n"
        "  victory_hold_min: 30, defeat: {hold_min: 30}, victory_node_frac: 0.80,\n"
        "  strategic_node_kinds: [AIRBASE, FOB, PORT],\n"
        "  idle_floor: {sanctuary_min_hp: 1, enabled: true}, victory: {hq_capture: true},\n"
        "  objective_pick: uniform,\n"
        "  time_limit_h: 72, night_progress_cap_nodes_per_h: 0.16666666666666666}\n"
        "tasking: {reeval_every_ticks: 50, claim_lease_s: 120, expire_min: 15,\n"
        "  priority: {scout: 30, strike: 40, assist_objective: 45, resupply: 50, defend: 60,\n"
        "    escort_convoy: 40, stage: 20, capture: 45, patrol: 15,\n"
        "    intercept: 45},\n"
        "  static_offense_min_tier: ALPHA,\n"
        "  urgency_max: 2.0, priority_aging_per_min: 1,\n"
        "  slots: {scout: 1, assist_objective: 4, strike: 2, defend: 2, escort_convoy: 2,\n"
        "    patrol: 2, intercept: 1},\n"
        "  resupply_stock_per_slot: 100, resupply_slots_max: 3, defend_radius_m: 10000,\n"
        "  counterattack_window_min: 15, scout_cooldown_min: 5, scout_open_max: 3,\n"
        "  scout_post_interval_min: 2, capture_max_restarts: 3,\n"
        "  follow_station_m: {escort: 500, column: 200, overwatch: 3000, wingman: 1000},\n"
        "  escort_threat_memory_s: 60, escort_leash_m: 10000,\n"
        "  follow_hold_slack: 2, overfill_factor: 2, scout_blob_runs: 2,\n"
        "  overfill_point_jobs: false, join_excluded_jobs: [PATROL],\n"
        "  scout_urgency: {small: 1.0, medium: 1.5, large: 2.0}, strike_urgency_per_threat: 0.01,\n"
        "  strike_max_scaled_slots: 3, strike_idle_targets_max: 2,\n"
        "  strike_idle_targets_min_tier: ALPHA,\n"
        "  patrol_max_nodes: 3, patrol_orbit_m: 5000, patrol_dwell_s: 300,\n"
        "  stock_urgency: 0.5, stock_front_bonus: 0.25}\n"
        "director: {window_s: 60, max_spawns_per_window: 6,\n"
        "  cp: {ema_window_s: 300, unit_value: {STRIKE_FIGHTER: 10, RECON_UAV: 3, LOGI_TRUCK: 2,\n"
        "    GARRISON_INFANTRY: 2}},\n"
        "  tier: {alpha_enter_cp: 0, bravo_enter_cp: 60, exit_ratio: 0.8, min_dwell_s: 600},\n"
        "  provocation: {half_life_s: 900, escalate_threshold: 10, bravo_threshold: 40,\n"
        "    scout_in_rear_max_per_window: 1,\n"
        "    weights: {unit_destroyed: 5, unit_damaged: 1, recon_destroyed: 2, recon_damaged: 0,\n"
        "      convoy_hit: 3, facility_damaged: 3,\n"
        "      facility_disabled: 8, base_captured: 15, scout_in_rear: 2,\n"
        "      redemption: {support: 1, cosmetic: 0}}},\n"
        "  budget: {pattern_of_life: 10, alpha: 30, bravo: 80},\n"
        "  max_live_units: {pattern_of_life: 40, alpha: 40, bravo: 70},\n"
        "  op_priority: {RETAKE: 1.2, OFFENSIVE: 1.0, ESCORT_CONVOYS: 0.8, REINFORCE_IADS: 0.7,\n"
        "    PROBE: 0.6, RECON: 0.5, DECOY_BLINK: 0.3, GARRISON_UPKEEP: 0.9},\n"
        "  score: {target_value: {AIRBASE: 1.5, FOB: 1.0, PORT: 1.0, SANCTUARY: 2.0},\n"
        "    weakness_max: 2.0, own_node_value: 1.0, weakness_min: 1.0, stale_factor: 1.0,\n"
        "    provocation_proximity: 1.5, proximity_tiers: [ALPHA]},\n"
        "  memory: {half_life_s: 1800, factor: 1.0,\n"
        "    weights: {convoy_hit: 1, radar_hit: 1, scout_lost: 1, node_lost: 1}},\n"
        "  decoy_blink: {dark_s: 120, cooldown_s: 600, max_per_window: 1},\n"
        "  recon: {loiter_s: 600, loiter_radius_m: 5000, grid_m: 10000, memory_s: 3600},\n"
        "  intercept: {radius_m: 30000, reaction_s: 60, pol_linger_s: 600, leash_m: 80000,\n"
        "    lost_s: 120},\n"
        "  max_ops: {alpha: 1, bravo: null}, job_urgency: 1.0,\n"
        "  idle_retire_s: 600, adaptation_up_above: 0, reinforce_damage_above: 0,\n"
        "  escort_min_convoys: 1, frontline_hops: 1,\n"
        "  adaptation_down_below: 1, noise_scale: 0.1, retake_window_min: 30,\n"
        "  garrison: {replace_per_window: 1, kinds: {FOB: [ENEMY_ARMOR],\n"
        "    AIRBASE: [ENEMY_FIGHTER, ENEMY_ARMOR],\n"
        "    HQ: [ENEMY_ARMOR]}},\n"
        "  pol: {patrol_period_s: 1800, convoy_period_s: 3600, offensive_period_s: 21600,\n"
        "    convoy_kind: ENEMY_CONVOY, patrol_slots: 1, patrols_per_base: 1,\n"
        "    convoys_per_period: 1, offensives_per_period: 1, convoy_cost: 0, convoy_slots: 1}}\n"
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
    assert (
        config_hash(balance_hash(changed), UNITS_HASH, OPERATIONS_HASH, THEATER_HASH)
        != GOLDEN_CONFIG_HASH
    )


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
            "slots": SLOTS,
            "air": AIR,
            "fow": FOW,
            "logistics": LOGISTICS,
            "capture": CAPTURE,
            "combat": COMBAT,
            "campaign": CAMPAIGN,
            "tasking": TASKING,
            "director": DIRECTOR,
        }
    )
    n = world_ticks(seconds, cfg)
    with localcontext() as ctx:
        ctx.prec = 100  # exact for these magnitudes: only products of short decimals
        s, ts = Decimal(repr(seconds)), Decimal(repr(time_scale))
        assert n * ts >= s * 10  # n ticks cover the configured world seconds (Q-ALN-6)
        assert (n - 1) * ts < s * 10  # and one tick fewer would not


def test_momentum_weights_must_add_up_to_100(tmp_path: Path) -> None:
    path = write(tmp_path, VALID.replace("supply_weight: 30", "supply_weight: 31"))
    with pytest.raises(
        ConfigError, match=r"campaign\.momentum: the two weights must add up to 100"
    ):
        load_balance(path)
    # exact decimals: 33.3 + 66.7 is 100, whatever the binary floats say
    ok = VALID.replace("nodes_weight: 70", "nodes_weight: 33.3").replace(
        "supply_weight: 30", "supply_weight: 66.7"
    )
    assert load_balance(write(tmp_path, ok)).campaign.momentum.supply_weight == 66.7


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("disabled_below: 0.10", "disabled_below: 0.35"),  # equal to mission_kill_below
        ("damaged_below: 0.70", "damaged_below: 0.30"),  # under mission_kill_below
    ],
)
def test_damage_state_thresholds_must_descend(tmp_path: Path, old: str, new: str) -> None:
    path = write(tmp_path, VALID.replace(old, new))
    with pytest.raises(ConfigError, match=r"combat\.damage_state: need disabled_below"):
        load_balance(path)


def test_game_ticks_in_minutes_and_hours() -> None:
    assert game_ticks(30, CFG, unit_s=60) == 18_000  # victory_hold_min
    assert game_ticks(72, CFG, unit_s=3600) == 2_592_000  # time_limit_h
    assert (
        game_ticks(0.1, CFG, unit_s=3600) == 3600
    )  # exact decimal: 0.1 h is 360 s, not 360.0000..1
