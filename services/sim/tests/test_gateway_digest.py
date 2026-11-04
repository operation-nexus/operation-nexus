"""GW-13, GW-14, GW-15: the digest builder skeleton (CHAT-GATEWAY §10)."""

import logging
import math
import typing

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nexus.contracts.gen.common.enums import RejectReason
from nexus.gateway.digest import TEMPLATES, DigestBuilder, GatewayReject
from nexus.gateway.fakes import FakeClock
from nexus.gateway.ports import Capabilities

CAPS = Capabilities(max_reply_rate=20 / 30, message_max_len=100)  # Twitch-shaped (§2.1)


def make(
    caps: Capabilities = CAPS, blatant: frozenset[str] = frozenset()
) -> tuple[DigestBuilder, FakeClock]:
    clock = FakeClock()
    return DigestBuilder(caps, clock, 30.0, lambda user: user in blatant), clock


def test_every_contract_reject_reason_has_a_template() -> None:
    inner = typing.get_args(RejectReason.__value__)[0]  # Annotated[Literal[...], Field]
    reasons = set(typing.get_args(inner))
    assert reasons and reasons <= set(TEMPLATES), reasons - set(TEMPLATES)
    assert {r.value for r in GatewayReject} <= set(TEMPLATES)


def test_lines_coalesce_per_user() -> None:
    b, _ = make()
    b.add_accepted("u1", "alice")
    b.add_accepted("u1", "alice")
    b.add_rejected("u1", "alice", "UNIT_IN_SORTIE")
    b.add_rejected("u1", "alice", "UNIT_IN_SORTIE")
    b.add_rejected("u2", "bob", GatewayReject.TOO_LONG)
    assert b.build() == ["@alice: 2 accepted; unit is in sortie (x2) | @bob: message too long"]
    assert b.build() == []  # the batch is consumed


def test_inbox_overflow_is_a_busy_line() -> None:
    b, _ = make()
    b.add_rejected("u1", "alice", GatewayReject.INBOX_FULL)
    assert b.build() == ["@alice: busy, try again"]


def test_unknown_reason_fails_loudly() -> None:
    b, _ = make()
    with pytest.raises(KeyError):
        b.add_rejected("u1", "alice", "MADE_UP")
    assert b.build() == []  # no half-made "@alice: " line left in the batch


def test_message_length_cap_splits_messages() -> None:
    b, _ = make(Capabilities(max_reply_rate=1.0, message_max_len=40))
    for i in range(4):
        b.add_rejected(
            f"u{i}", f"user{i}", GatewayReject.TOO_LONG
        )  # "@userN: message too long" = 24
    out = b.build()
    assert len(out) == 4 and all(len(m) <= 40 for m in out) and b.dropped == 0


def test_reply_rate_cap_drops_oldest_first_and_counts() -> None:
    b, _ = make(Capabilities(max_reply_rate=0.1, message_max_len=30))  # 3 messages per 30 s
    for i in range(5):
        b.add_rejected(f"u{i}", f"user{i}", GatewayReject.TOO_LONG)
    out = b.build()
    assert [m.split(":")[0] for m in out] == ["@user2", "@user3", "@user4"]
    assert b.dropped == 2


def test_a_line_longer_than_a_message_is_dropped_and_counted() -> None:
    b, _ = make(Capabilities(max_reply_rate=1.0, message_max_len=20))
    b.add_rejected("u1", "x" * 30, GatewayReject.TOO_LONG)
    assert b.build() == [] and b.dropped == 1


def test_blatant_users_get_the_ring_only() -> None:
    b, _ = make(blatant=frozenset({"spam"}))
    b.add_rejected("spam", "spammer", GatewayReject.RATE_LIMITED)
    b.add_rejected("ok", "fine", GatewayReject.RATE_LIMITED)
    assert b.build() == ["@fine: hold up, ready in a few seconds"]
    assert b.suppressed == 1


def test_due_follows_the_injected_clock() -> None:
    b, clock = make()
    assert not b.due()
    clock.advance(30)
    assert b.due()
    b.build()
    assert not b.due()


def test_unknown_caps_are_refused_not_guessed() -> None:
    for caps in (Capabilities(), Capabilities(max_reply_rate=1.0), Capabilities(message_max_len=9)):
        with pytest.raises(ValueError):
            make(caps)


def test_login_is_not_in_repr_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    b, _ = make()
    with caplog.at_level(logging.DEBUG):
        b.add_accepted("u1", "loginXYZ")
        b.add_rejected("u1", "loginXYZ", "NO_STOCK")
        b.build()
    assert "loginXYZ" not in caplog.text and caplog.records == []
    b.add_accepted("u2", "loginXYZ")
    assert "loginXYZ" not in repr(next(iter(b._users.values())))


def test_blatant_users_get_no_line_accepted_or_rejected() -> None:
    b, _ = make(blatant=frozenset({"spam"}))
    b.add_accepted("spam", "spammer")
    b.add_rejected("spam", "spammer", GatewayReject.RATE_LIMITED)
    b.add_accepted("ok", "fine")
    assert b.build() == ["@fine: 1 accepted"]
    assert b.suppressed == 2


def test_a_user_who_turns_blatant_after_queuing_is_dropped_at_build() -> None:
    blatant: set[str] = set()
    clock = FakeClock()
    b = DigestBuilder(CAPS, clock, 30.0, lambda user: user in blatant)
    b.add_accepted("u1", "alice")
    b.add_accepted("u2", "bob")
    blatant.add("u1")
    assert b.build() == ["@bob: 1 accepted"] and b.suppressed == 1


@pytest.mark.parametrize(
    ("rate", "interval", "budget"),
    [(0.02, 30.0, 1), (0.1, 25.0, 2), (1 / 30, 59.0, 1)],  # 0.6 -> floor 1; 2.5 -> 2; 1.97 -> 1
)
def test_budget_is_the_floored_product_with_a_minimum_of_one(
    rate: float, interval: float, budget: int
) -> None:
    clock = FakeClock()
    b = DigestBuilder(
        Capabilities(max_reply_rate=rate, message_max_len=30), clock, interval, lambda u: False
    )
    for i in range(5):
        b.add_rejected(f"u{i}", f"user{i}", GatewayReject.TOO_LONG)  # one message per line
    assert len(b.build()) == budget


def test_a_line_exactly_max_len_is_sent() -> None:
    line = "@u: message too long"
    b, _ = make(Capabilities(max_reply_rate=1.0, message_max_len=len(line)))
    b.add_rejected("u1", "u", GatewayReject.TOO_LONG)
    assert b.build() == [line] and b.dropped == 0
    b.add_rejected("u1", "uu", GatewayReject.TOO_LONG)  # one character over
    assert b.build() == [] and b.dropped == 1


@pytest.mark.parametrize("bad", [math.nan, math.inf, 0.0, -1.0])
def test_non_finite_or_non_positive_inputs_are_refused(bad: float) -> None:
    clock = FakeClock()
    with pytest.raises(ValueError):
        DigestBuilder(Capabilities(max_reply_rate=bad, message_max_len=100), clock, 30.0, bool)
    with pytest.raises(ValueError):
        DigestBuilder(Capabilities(max_reply_rate=1.0, message_max_len=100), clock, bad, bool)
    if bad <= 0:
        with pytest.raises(ValueError):
            DigestBuilder(
                Capabilities(max_reply_rate=1.0, message_max_len=int(bad)), clock, 30.0, bool
            )


@given(st.text(min_size=1, max_size=40), st.sampled_from(sorted(TEMPLATES)))
def test_a_line_is_the_login_plus_a_static_template(login: str, reason: str) -> None:
    """Whatever the login holds, the rest of the line is the closed template, never other text."""
    b, _ = make(Capabilities(max_reply_rate=1.0, message_max_len=500))
    b.add_rejected("u1", login, reason)
    assert b.build() == [f"@{login}: {TEMPLATES[reason]}"]


def test_two_lines_that_join_to_exactly_max_len_share_one_message() -> None:
    joined = "@a: busy, try again | @b: busy, try again"
    b, _ = make(Capabilities(max_reply_rate=1.0, message_max_len=len(joined)))
    b.add_rejected("ua", "a", GatewayReject.INBOX_FULL)
    b.add_rejected("ub", "b", GatewayReject.INBOX_FULL)
    assert b.build() == [joined]


def test_a_blatant_user_is_suppressed_when_added_not_held_until_build() -> None:
    b, _ = make(blatant=frozenset({"u1"}))
    b.add_accepted("u1", "alice")
    b.add_rejected("u1", "alice", GatewayReject.TOO_LONG)
    assert b.suppressed == 2  # counted at add time: nothing of theirs is held in the batch
