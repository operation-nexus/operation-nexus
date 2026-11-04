"""nexus.moderation — see docs/specs (THREAT-MODEL SEC-MOD; CHAT-GATEWAY GW-7)."""

from nexus.moderation.normalize import MAX_TEXT_LEN, TooLong, normalize

__all__ = ["MAX_TEXT_LEN", "TooLong", "normalize"]
