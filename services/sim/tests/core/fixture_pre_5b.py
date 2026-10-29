"""Test fixture: the balance defaults shipped before NX-412 part 5b, as overrides.

Part 5b turned the economy on and shipped harness-tuned values (Q-TD-29, Q-TD-33, Q-TD-79, Q-TD-85,
Q-TD-90, Q-TD-97); NX-473 then switched the logistics keys on (Q-TD-128). A test written against
the old values (infinite sources, units-first fire, the old wait, spend and adaptation threshold,
the logistics keys off) sets them here explicitly, so it keeps testing what it tested; a test's own
overrides go after these and win. The old tier budget and live-unit caps (`economy.legacy_rules`)
were deleted in NX-488: those tests run the ECONOMY EC-7, EC-8 and EC-13 rules.
"""

from collections.abc import Mapping

from nexus.runtime.campaign_config import CampaignConfig
from nexus.runtime.golden import shipped_config

PRE_5B: dict[str, object] = {
    "economy.unlimited.COALITION": True,
    "economy.unlimited.ENEMY": True,
    "director.adaptation_up_above": 0,
    "combat.strike_structure_first": False,
    "director.staging.max_wait_windows": 90,
    "director.source_spend_frac": 0.005,
    # NX-473 switch-on (Q-TD-128): LC-1..LC-3 off, as before
    "logistics.ai_trucks.max_live": 0,
    "tasking.resupply_slots_max_starving": 3,
    "director.pol.convoy_demand_s": 3600,
}


def pre_5b_config(overrides: Mapping[str, object] | None = None) -> CampaignConfig:
    """`shipped_config` with the pre-5b defaults, then `overrides` on top."""
    return shipped_config({**PRE_5B, **(overrides or {})})
