"""The one pure text normalizer for chat (CHAT-GATEWAY GW-7, SEC-GW-1).

NFKC, strip control, bidi and zero-width characters, then the length cap measured on the result.
Over the cap is rejected, never truncated (Q-CT-1): truncation could turn a long message into a
different valid command. Pure: no I/O, no clock, no state.
"""

import unicodedata
from dataclasses import dataclass

# The ChatEnvelope contract's `text` maxLength (contracts/common/envelope.json). No config key
# exists for it; the spec's number is PROPOSED (CHAT-GATEWAY §4) and the schema enforces it too.
MAX_TEXT_LEN = 300

# Cc controls, Cf format characters (zero-width, bidi marks and overrides, soft hyphen, BOM),
# Cs lone surrogates.
_STRIPPED = frozenset({"Cc", "Cf", "Cs"})
# Default_Ignorable_Code_Point members that are not Cf, checked against Unicode 15.1.0
# DerivedCoreProperties.txt (the version of Python's unicodedata here).
# They render as nothing, so "!jo<U+034F>in" would defeat exact matching. Cf members are covered
# by _STRIPPED. Not all of Mn: real combining accents must survive.
_IGNORABLE = (
    (0x034F, 0x034F),  # combining grapheme joiner
    (0x115F, 0x1160),  # Hangul choseong/jungseong fillers
    (0x17B4, 0x17B5),  # Khmer inherent vowels
    (0x180B, 0x180D),  # Mongolian free variation selectors
    (0x180F, 0x180F),  # Mongolian free variation selector four
    (0x2065, 0x2065),  # unassigned, default-ignorable
    (0x3164, 0x3164),  # Hangul filler
    (0xFE00, 0xFE0F),  # variation selectors
    (0xFFA0, 0xFFA0),  # halfwidth Hangul filler
    (0xFFF0, 0xFFF8),  # unassigned, default-ignorable
    (0xE0000, 0xE0FFF),  # tags, variation selectors supplement, unassigned
)
# Line breaks and tabs separate words, so they become one space each (no run collapsing) instead
# of being stripped, which would glue "!join\nfoo" into "!joinfoo".
_SPACED = frozenset("\t\n\v\f\r\x85\u2028\u2029")


@dataclass(frozen=True)
class TooLong:
    """The text is over `MAX_TEXT_LEN` after normalization. Carries the length, never the text."""

    length: int


def _dropped(c: str) -> bool:
    return unicodedata.category(c) in _STRIPPED or any(lo <= ord(c) <= hi for lo, hi in _IGNORABLE)


def _strip(text: str) -> str:
    return "".join(" " if c in _SPACED else c for c in text if c in _SPACED or not _dropped(c))


def normalize(text: str) -> str | TooLong:
    """Return the normalized text, or `TooLong` when it is over the cap after normalizing.

    Stripping runs before NFKC (so a zero-width character cannot block a composition) and again
    after it, which makes the function idempotent. With the Unicode tables in use today NFKC never
    produces a stripped or line-break character, so the second pass is a guard against a future
    Unicode version rather than a path any current input takes.
    """
    out = _strip(unicodedata.normalize("NFKC", _strip(text)))
    return TooLong(len(out)) if len(out) > MAX_TEXT_LEN else out
