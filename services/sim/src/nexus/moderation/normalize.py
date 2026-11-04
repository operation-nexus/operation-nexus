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
# Line breaks and tabs separate words, so they become one space each (no run collapsing) instead
# of being stripped, which would glue "!join\nfoo" into "!joinfoo".
_SPACED = frozenset("\t\n\v\f\r\x85\u2028\u2029")


@dataclass(frozen=True)
class TooLong:
    """The text is over `MAX_TEXT_LEN` after normalization. Carries the length, never the text."""

    length: int


def _strip(text: str) -> str:
    return "".join(
        " " if c in _SPACED else c
        for c in text
        if c in _SPACED or unicodedata.category(c) not in _STRIPPED
    )


def normalize(text: str) -> str | TooLong:
    """Return the normalized text, or `TooLong` when it is over the cap after normalizing.

    Stripping runs before NFKC (so a zero-width character cannot block a composition) and again
    after it, which makes the function idempotent. With the Unicode tables in use today NFKC never
    produces a stripped or line-break character, so the second pass is a guard against a future
    Unicode version rather than a path any current input takes.
    """
    out = _strip(unicodedata.normalize("NFKC", _strip(text)))
    return TooLong(len(out)) if len(out) > MAX_TEXT_LEN else out
