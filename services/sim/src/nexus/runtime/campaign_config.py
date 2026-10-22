"""Load a campaign's static config in one place (SIM-CORE §4; CONFIG-AND-CONTENT §4.4; NX-122).

Balance (NX-106), the unit catalog (NX-367) and the theater (NX-120) come from the existing
loaders; this module only joins them: the parts, their `config_hash` and the kernel's `Rules`.
`start_campaign` builds a new campaign's world from them (STATE-MACHINES §4.4 Setup), with the
theater's facilities placed (Q-GP-25).
Paths default to the shipped files, found from this file, not the working directory.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from nexus.contracts.gen.common.enums import Side
from nexus.contracts.gen.config.balance import BalanceConfig
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.core.rules import (
    Rules,
    campaign_rules,
    combat_rules,
    director_rules,
    make_rules,
    tasking_rules,
    world_dt,
)
from nexus.core.world import Campaign, Vec2, World
from nexus.runtime.config import (
    canonical_hash,
    config_hash,
    game_ticks,
    load_balance,
    world_ticks,
)
from nexus.runtime.theater import load_theater, masking_cells, road_graph
from nexus.runtime.units import UnitCatalog, catalog_hash, load_catalog

# services/sim/src/nexus/runtime -> repo root. shortcut: the default paths need a source checkout;
# give the deploy item (NX-255) an env override or explicit paths when the sim ships in an image.
REPO = Path(__file__).resolve().parents[5]


@dataclass(frozen=True, slots=True)
class ConfigPaths:
    balance: Path = REPO / "balance" / "default.yaml"
    units: Path = REPO / "content" / "units"
    weapons: Path = REPO / "content" / "weapons.yaml"
    roles: Path = REPO / "content" / "roles.yaml"
    theater: Path = REPO / "content" / "theaters" / "strait-1.yaml"


@dataclass(frozen=True, slots=True)
class CampaignConfig:
    balance: BalanceConfig
    catalog: UnitCatalog
    theater: TheaterConfig
    config_hash: str  # balance, units, theater (§4.4)
    rules: Rules = field(compare=False)


def load_campaign_config(paths: ConfigPaths | None = None) -> CampaignConfig:
    """Raises ConfigError, naming the file, when any part is missing or invalid."""
    paths = paths or ConfigPaths()
    balance = load_balance(paths.balance)
    catalog = load_catalog(paths.units, paths.weapons, paths.roles)
    theater = load_theater(paths.theater)
    digest = config_hash(
        canonical_hash(balance.model_dump()),
        catalog_hash(catalog),
        canonical_hash(theater.model_dump()),
    )
    mask_cell_m, masking = masking_cells(theater)
    roads = road_graph(theater)
    cc = balance.campaign
    rules = make_rules(
        balance.sim,
        catalog.units,
        roads,
        roles=catalog.roles.roles,
        theater=theater,
        slots=balance.slots,
        air=balance.air,
        fow=balance.fow,
        logistics=balance.logistics,
        capture=balance.capture,
        respawn_delay_ticks=game_ticks(balance.slots.respawn_delay_s, balance),
        track_fade_ticks=world_ticks(balance.fow.track_fade_s, balance),
        sigint_refresh_ticks=world_ticks(balance.fow.sigint_refresh_s, balance),
        mask_cell_m=float(mask_cell_m),
        masking=masking,
        campaign=campaign_rules(
            cc,
            theater,
            roads,
            time_limit_ticks=game_ticks(cc.time_limit_h, balance, unit_s=3600),
            victory_hold_ticks=game_ticks(cc.victory_hold_min, balance, unit_s=60),
            defeat_hold_ticks=game_ticks(cc.defeat.hold_min, balance, unit_s=60),
            objective_period_ticks=game_ticks(cc.objective_period_min, balance, unit_s=60),
        ),
        combat=combat_rules(
            balance.combat,
            catalog.units,
            catalog.weapons,
            dt=world_dt(balance.sim),
            disabled_timeout_ticks=game_ticks(balance.combat.disabled_timeout_s, balance),
            assist_window_ticks=game_ticks(balance.combat.assist_window_s, balance),
            crew_marker_ticks=game_ticks(balance.combat.crew_marker_min, balance, unit_s=60),
        ),
        tasking=tasking_rules(
            balance.tasking,
            claim_lease_ticks=game_ticks(balance.tasking.claim_lease_s, balance),
            expire_ticks=game_ticks(balance.tasking.expire_min, balance, unit_s=60),
            ticks_per_min=game_ticks(1, balance, unit_s=60),
            counterattack_window_ticks=game_ticks(
                balance.tasking.counterattack_window_min, balance, unit_s=60
            ),
            scout_cooldown_ticks=game_ticks(balance.tasking.scout_cooldown_min, balance, unit_s=60),
            threat_memory_ticks=world_ticks(balance.tasking.escort_threat_memory_s, balance),
        ),
        director=director_rules(
            balance.director,
            catalog.units,
            window_ticks=game_ticks(balance.director.window_s, balance),
            ema_ticks=game_ticks(balance.director.cp.ema_window_s, balance),
            half_life_ticks=game_ticks(balance.director.provocation.half_life_s, balance),
            min_dwell_ticks=game_ticks(balance.director.tier.min_dwell_s, balance),
        ),
    )
    return CampaignConfig(balance, catalog, theater, digest, rules)


def start_campaign(campaign_id: str, seed: int, config: CampaignConfig | None = None) -> World:
    """A new campaign's tick-0 world, stamped with the config's `config_hash`, rules attached.

    `config` defaults to the shipped files; a load failure raises (no fallback, §4.4 Setup).
    `CampaignStarted` lands with the campaign lifecycle (NX-126)."""
    config = config or load_campaign_config()
    world = World.new(Campaign(campaign_id, seed, config.config_hash), config.rules)
    world.stock = {n.id: n.start_stock for n in config.theater.nodes if n.start_stock is not None}
    _place_facilities(world, config.theater)
    return world


def _place_facilities(world: World, theater: TheaterConfig) -> None:
    """Each theater facility, in file order (so ids are deterministic), becomes a STATIC entity at
    its base's position, on the base's starting side (TH-10: never NEUTRAL), owned by that side's
    AI (`AI_GARRISON`, the catalog's `playable_by`), at full hp and ammo (NX-124). FOW-11:
    RADAR_SITE and the SAM AIR_DEFENSE_SITE emit from the start; any other has `emitting` None.
    shortcut: the emitter rule names kind and variant here; it moves to the unit catalog when
    the catalog lists variants (CONFIG-AND-CONTENT §7)."""
    nodes = {n.id: n for n in theater.nodes}
    for f in theater.facilities:
        base = nodes[f.base]
        side = cast(Side, base.start_owner)  # TH-10, checked at load
        e = world.spawn(f.kind, side, "AI_GARRISON", Vec2(*base.pos), variant=f.variant)
        e.base_id = f.base
        emits = f.kind == "RADAR_SITE" or (f.kind, f.variant) == ("AIR_DEFENSE_SITE", "SAM")
        e.emitting = True if emits else None
