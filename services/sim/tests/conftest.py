"""Shared test settings (TESTING-STRATEGY §2, NX-030).

Hypothesis profiles: `ci` (200 examples, derandomized, the default) and `nightly` (5,000, random,
to explore). Pick one with HYPOTHESIS_PROFILE=nightly. No deadline in either: timing is measured
by benchmarks, and a deadline on a shared CI runner is a flaky test (TESTING-STRATEGY §5).
"""

import os

import pytest
from hypothesis import settings

from nexus.runtime.campaign_config import CampaignConfig, load_campaign_config

# Built on Hypothesis's own `ci` profile (derandomized, no example database), which it loads by
# itself on a CI runner; replacing it outright would make CI draw new examples every run.
settings.register_profile("ci", settings.get_profile("ci"), max_examples=200)
settings.register_profile(
    "nightly", settings.get_profile("ci"), max_examples=5_000, derandomize=False
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))


@pytest.fixture(scope="session")
def shipped_config() -> CampaignConfig:
    """The shipped balance, units and theater, loaded once per session (NX-122)."""
    return load_campaign_config()
