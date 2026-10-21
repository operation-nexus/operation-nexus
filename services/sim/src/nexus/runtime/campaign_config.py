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
from nexus.core.rules import Rules, make_rules
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
    rules = make_rules(
        balance.sim,
        catalog.units,
        road_graph(theater),
        roles=catalog.roles.roles,
        theater=theater,
        slots=balance.slots,
        air=balance.air,
        fow=balance.fow,
        respawn_delay_ticks=game_ticks(balance.slots.respawn_delay_s, balance),
        track_fade_ticks=world_ticks(balance.fow.track_fade_s, balance),
        sigint_refresh_ticks=world_ticks(balance.fow.sigint_refresh_s, balance),
        mask_cell_m=float(mask_cell_m),
        masking=masking,
    )
    return CampaignConfig(balance, catalog, theater, digest, rules)


def start_campaign(campaign_id: str, seed: int, config: CampaignConfig | None = None) -> World:
    """A new campaign's tick-0 world, stamped with the config's `config_hash`, rules attached.

    `config` defaults to the shipped files; a load failure raises (no fallback, §4.4 Setup).
    `CampaignStarted` lands with the campaign lifecycle (NX-126)."""
    config = config or load_campaign_config()
    world = World.new(Campaign(campaign_id, seed, config.config_hash), config.rules)
    _place_facilities(world, config.theater)
    return world


def _place_facilities(world: World, theater: TheaterConfig) -> None:
    """Each theater facility, in file order (so ids are deterministic), becomes a STATIC entity at
    its base's position, on the base's starting side (TH-10: never NEUTRAL), owned by that side's
    AI (`AI_GARRISON`, the catalog's `playable_by`), hp unmodelled until combat (NX-124). FOW-11:
    RADAR_SITE and the SAM AIR_DEFENSE_SITE emit from the start; any other has `emitting` None.
    shortcut: the emitter rule names kind and variant here; it moves to the unit catalog when
    the catalog lists variants (CONFIG-AND-CONTENT §7)."""
    nodes = {n.id: n for n in theater.nodes}
    for f in theater.facilities:
        base = nodes[f.base]
        side = cast(Side, base.start_owner)  # TH-10, checked at load
        e = world.spawn(f.kind, side, "AI_GARRISON", Vec2(*base.pos), hp=None)
        e.base_id, e.variant = f.base, f.variant
        emits = f.kind == "RADAR_SITE" or (f.kind, f.variant) == ("AIR_DEFENSE_SITE", "SAM")
        e.emitting = True if emits else None
