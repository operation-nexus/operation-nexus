"""GW-7: the chat normalizer (CHAT-GATEWAY §10)."""
# ruff: noqa: RUF001  # homoglyph and fullwidth literals are the point of these tests

import time

from hypothesis import given
from hypothesis import strategies as st

from nexus.moderation import MAX_TEXT_LEN, TooLong, normalize

ZERO_WIDTH = ["​", "‌", "‍", "⁠", "﻿", "­"]
BIDI = ["‎", "‏", "‪", "‫", "‬", "‭", "‮", "⁦", "⁩"]
CONTROLS = ["\x00", "\x07", "\x1b", "\x7f"]
INVISIBLE = ZERO_WIDTH + BIDI + CONTROLS


def _interleave(base: str, junk: list[str]) -> str:
    return "".join(c + j for c, j in zip(base, junk * len(base), strict=False))


@given(
    st.text(alphabet="!abc XYZ-019", max_size=60), st.lists(st.sampled_from(INVISIBLE), min_size=1)
)
def test_invisible_characters_are_stripped(base: str, junk: list[str]) -> None:
    assert normalize(_interleave(base, junk)) == base


@given(st.text())
def test_idempotent_and_never_truncates(text: str) -> None:
    once = normalize(text)
    if isinstance(once, TooLong):
        assert once.length > MAX_TEXT_LEN
        return
    assert len(once) <= MAX_TEXT_LEN
    assert normalize(once) == once


@given(st.text(min_size=MAX_TEXT_LEN + 1, alphabet="abcXYZ019 !-"))
def test_over_cap_is_rejected_not_cut(text: str) -> None:
    result = normalize(text)
    assert result == TooLong(len(text))


def test_composition_across_a_stripped_character_is_idempotent() -> None:
    once = normalize("a​́")
    assert once == "á"
    assert normalize(once) == once


def test_ten_kilobytes_rejected_in_bounded_time() -> None:
    start = time.perf_counter()
    result = normalize("!join " * 1700)  # about 10 KB
    assert isinstance(result, TooLong)
    assert time.perf_counter() - start < 1.0


def test_ten_kilobytes_of_invisible_junk_is_accepted_not_truncated() -> None:
    assert normalize("!join" + "​" * 10_000) == "!join"


def test_nfkc_expansion_crossing_the_cap_is_rejected() -> None:
    assert len("ﬃ" * 150) == 150  # the ffi ligature expands to 3 characters
    assert normalize("ﬃ" * 150) == TooLong(450)


def test_nfkc_contraction_under_the_cap_is_accepted() -> None:
    text = "Å" * 150  # A + combining ring composes to one character
    assert len(text) == 300 and normalize(text) == "Å" * 150
    assert normalize("x" * 300) == "x" * 300
    assert normalize("x" * 301) == TooLong(301)


def test_fullwidth_folds_but_cyrillic_lookalikes_do_not() -> None:
    # NFKC folds fullwidth forms. It does not fold Cyrillic: the confusable-folded match key and
    # the reserved-word check belong to NX-041 (GW-18), so this documents the boundary.
    assert normalize("ＶＩＰＥＲ-２７") == "VIPER-27"
    assert normalize("ВІРЕЯ-27") != "VIPER-27"


def test_bidi_override_cannot_hide_a_command() -> None:
    assert normalize("‮!nioj‬") == "!nioj"
    assert normalize("!jo​in") == "!join"


def test_line_breaks_and_tabs_become_one_space_each() -> None:
    assert normalize("!join\nfoo") == "!join foo"
    assert normalize("!join\tfoo") == "!join foo"
    assert normalize("a\r\nb\u2028c\u2029d\x85e") == "a  b c d e"  # runs are not collapsed
    assert normalize(" ") == " "


@given(st.text(alphabet="ab\n\t\r\u2028 \u200b", max_size=40))
def test_whitespace_mapping_is_idempotent(text: str) -> None:
    once = normalize(text)
    assert isinstance(once, str) and normalize(once) == once


def test_cap_applies_after_the_space_mapping() -> None:
    assert normalize("a\n" * 150) == "a " * 150
    assert normalize("a\n" * 151) == TooLong(302)


def test_lone_surrogates_are_stripped() -> None:
    # A surrogate that got through would fail at UTF-8 encoding in logs or JSON.
    assert normalize("\ud800x") == "x"
    assert normalize("a\udfffb") == "ab"
