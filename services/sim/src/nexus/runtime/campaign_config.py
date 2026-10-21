"""Load a campaign's static config in one place (SIM-CORE §4; CONFIG-AND-CONTENT §4.4; NX-122).

Balance (NX-106), the unit catalog (NX-367) and the theater (NX-120) come from the existing
loaders; this module only joins them: the parts, their `config_hash` and the kernel's `Rules`.
Paths default to the shipped files, found from this file, not the working directory.
"""

from dataclasses import dataclass, field
from pathlib import Path

from nexus.contracts.gen.config.balance import BalanceConfig
from nexus.contracts.gen.config.theater import TheaterConfig
from nexus.core.rules import Rules, make_rules
from nexus.runtime.config import canonical_hash, config_hash, load_balance
from nexus.runtime.theater import load_theater, road_graph
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
    rules = make_rules(balance.sim, catalog.units, road_graph(theater))
    return CampaignConfig(balance, catalog, theater, digest, rules)
