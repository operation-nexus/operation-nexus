import os

from hypothesis import given, settings
from hypothesis import strategies as st

EXPECTED = {"ci": 200, "nightly": 5_000}


def test_profile_loaded() -> None:
    profile = os.environ.get("HYPOTHESIS_PROFILE", "ci")
    assert settings().max_examples == EXPECTED[profile]
    assert settings().deadline is None


@given(st.lists(st.integers()))
def test_sorting_is_idempotent(xs: list[int]) -> None:
    assert sorted(sorted(xs)) == sorted(xs)
