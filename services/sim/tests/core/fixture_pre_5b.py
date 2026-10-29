"""Test fixture: the balance defaults shipped before NX-412 part 5b, as overrides.

Part 5b turned the economy on and shipped harness-tuned values (Q-TD-29, Q-TD-33, Q-TD-79, Q-TD-85,
Q-TD-90, Q-TD-97). A test written against the old rules (the legacy budget and caps, infinite
sources, units-first fire, the old wait and spend) sets them here explicitly, so it keeps testing
what it tested; a test's own overrides go after these and win.
"""

from collections.abc import Mapping

from nexus.runtime.campaign_config import CampaignConfig
from nexus.runtime.golden import shipped_config

PRE_5B: dict[str, object] = {
    "economy.legacy_rules": True,
    "economy.unlimited.COALITION": True,
    "economy.unlimited.ENEMY": True,
    "director.adaptation_up_above": 0,
    "combat.strike_structure_first": False,
    "director.staging.max_wait_windows": 90,
    "director.source_spend_frac": 0.005,
}


def pre_5b_config(overrides: Mapping[str, object] | None = None) -> CampaignConfig:
    """`shipped_config` with the pre-5b defaults, then `overrides` on top."""
    return shipped_config({**PRE_5B, **(overrides or {})})
