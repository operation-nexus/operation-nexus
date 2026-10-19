"""Shared test settings (TESTING-STRATEGY §2, NX-030).

Hypothesis profiles: `ci` (200 examples, derandomized, the default) and `nightly` (5,000, random,
to explore). Pick one with HYPOTHESIS_PROFILE=nightly. No deadline in either: timing is measured
by benchmarks, and a deadline on a shared CI runner is a flaky test (TESTING-STRATEGY §5).
"""

import os

from hypothesis import settings

# Built on Hypothesis's own `ci` profile (derandomized, no example database), which it loads by
# itself on a CI runner; replacing it outright would make CI draw new examples every run.
settings.register_profile("ci", settings.get_profile("ci"), max_examples=200)
settings.register_profile(
    "nightly", settings.get_profile("ci"), max_examples=5_000, derandomize=False
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))
