"""Dedupe (GW-8 stage 3) and correlation ids (GW-9) (CHAT-GATEWAY §10)."""

import logging
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.gateway.dedupe import DEDUPE_CAPACITY, Dedupe, correlation_id

MESSAGE_IDS = st.text(min_size=1, max_size=128)


def test_the_same_id_twice_is_one_message() -> None:
    d = Dedupe()
    assert not d.is_duplicate("TWITCH", "m1")
    assert d.is_duplicate("TWITCH", "m1")
    assert not d.is_duplicate("TWITCH", "m2")


def test_a_duplicate_delivery_stream_yields_one_of_each() -> None:
    d = Dedupe()
    stream = ["m1", "m1", "m2", "m1", "m2", "m3"]
    assert [m for m in stream if not d.is_duplicate("LOCAL_SIM", m)] == ["m1", "m2", "m3"]


def test_equal_ids_on_different_platforms_do_not_collide() -> None:
    d = Dedupe()
    assert not d.is_duplicate("TWITCH", "m1")
    assert not d.is_duplicate("YOUTUBE", "m1")
    assert d.is_duplicate("YOUTUBE", "m1")


def test_capacity_is_10k_and_oldest_goes_first() -> None:
    assert DEDUPE_CAPACITY == 10_000
    d = Dedupe()
    for i in range(DEDUPE_CAPACITY):
        d.is_duplicate("TWITCH", str(i))
    assert len(d) == DEDUPE_CAPACITY
    assert d.is_duplicate("TWITCH", "0")  # a hit does not refresh "0" (FIFO)
    d.is_duplicate("TWITCH", "new")  # evicts "0", the oldest
    assert len(d) == DEDUPE_CAPACITY
    assert not d.is_duplicate("TWITCH", "0")  # gone: passes (§7), and evicts "1"
    assert not d.is_duplicate("TWITCH", "1")
    assert d.is_duplicate("TWITCH", "5000")  # newer ids still held


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Dedupe(0)


def test_correlation_id_known_value() -> None:
    # first 32 hex of `printf 'TWITCH:abc' | sha256sum`
    assert correlation_id("TWITCH", "abc") == "8822f2ffe9d5532b647d8e43133a6565"
    assert correlation_id("TWITCH", "abc") != correlation_id("YOUTUBE", "abc")


@given(MESSAGE_IDS)
def test_correlation_id_is_deterministic_short_hex_without_input_text(message_id: str) -> None:
    cid = correlation_id("TWITCH", message_id)
    assert cid == correlation_id("TWITCH", message_id)
    assert re.fullmatch("[0-9a-f]{32}", cid)  # 32 <= 64 (CONTRACTS cap); hex only, so no text


def test_logs_hold_nothing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        d = Dedupe()
        d.is_duplicate("TWITCH", "secret-message-XYZ")
        d.is_duplicate("TWITCH", "secret-message-XYZ")
        correlation_id("TWITCH", "secret-message-XYZ")
    assert "XYZ" not in caplog.text and caplog.records == []
