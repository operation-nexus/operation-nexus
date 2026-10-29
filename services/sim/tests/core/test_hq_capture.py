"""NX-490: an HQ is very hard to capture, hardest alone (GAMEPLAY §8 and the §11 NX-490 row;
Q-TD-105 owner, Q-TD-127 lead, owner may veto; CONFIG-AND-CONTENT §6.5).

`capture.time_mult.<kind>` multiplies `capture.time_s` and `capture.extra_exponent.<kind>` is
added to `capture.multi_unit_exponent`, by the node's kind, for whichever side captures. Shipped:
HQ 20 and 0.5, every other kind 1.0 and 0. Expected ticks are worked by hand from the shipped
numbers (0.6 world s a tick; an empty base x0.5; quiet 1.0): a lone capturer at an empty HQ takes
120 x 20 x 0.5 / 1^1.0 = 1200 s, so it gains 100,000,000 x 0.6 / 1200 = 50,000 a tick and flips
on tick 2000; at a FOB 120 x 0.5 = 60 s, 100 ticks.

These worlds turn the quiet-stream multiplier off (`quiet_sides` empty, quiet 1.0 as the spec's
worked numbers assume) and the Threat Director off (no Static unit walks onto the node mid-test);
the HQ keys themselves come through the loader (`shipped_config`). strait-1 has only the Static's
HQ; the parity test gives the coalition one in `Rules.node_kind` (the theater loader allows one).
"""

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_capture import ARMOR, CAMPAIGN_ID, INFANTRY, TRUCK, of, progress, put, run

from nexus.contracts.gen.common.enums import Side, UnitKind
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.core.rules import CAPTURE_FULL
from nexus.core.world import World, load, save, state_hash
from nexus.runtime.campaign_config import CampaignConfig, start_campaign
from nexus.runtime.config import ConfigError
from nexus.runtime.golden import shipped_config

ENEMY_HQ, ENEMY_FOB, ENEMY_AIRBASE = "static-hq", "fob-n-e", "east-airbase"
WEST_FOB = "fob-n-w"  # a coalition FOB; the parity theater makes it the coalition's HQ
KINDS = ("AIRBASE", "FOB", "HQ", "PORT", "SANCTUARY")
SHIPPED = shipped_config({})
NEUTRAL_KEYS = {
    "capture.time_mult": dict.fromkeys(KINDS, 1.0),
    "capture.extra_exponent": dict.fromkeys(KINDS, 0.0),
}


def world(cfg: CampaignConfig) -> World:
    """A campaign on `cfg` with every defense down, no board, garrison or Director, quiet 1.0."""
    rules = cfg.rules
    assert rules.capture is not None
    rules = dataclasses.replace(
        rules,
        tasking=None,
        garrison_quota={},
        director=None,
        capture=dataclasses.replace(rules.capture, quiet_sides=frozenset()),
    )
    w = start_campaign(CAMPAIGN_ID, 12345, dataclasses.replace(cfg, rules=rules))
    w.defense_hp = dict.fromkeys(w.defense_hp, 0)
    return w


def crowd(w: World, node: str, side: Side, n: int, kind: UnitKind | None = None) -> None:
    unit = kind or (INFANTRY if side == "COALITION" else ARMOR)
    for i in range(n):
        put(w, unit, side, node, n=i + 1 if unit == TRUCK else None)  # an AI truck never captures


def flip_tick(w: World, node: str, limit: int = 4100) -> int:
    """The tick `node` flips on, counted from the first tick of the run."""
    for _ in range(limit):
        if of(run(w), NodeCaptured):
            assert w.owner[node] != "NEUTRAL"
            return w.campaign.tick
    raise AssertionError(f"{node} did not flip in {limit} ticks")


def two_hq_world() -> World:
    """strait-1 with the coalition's FOB North-West an HQ, so each side has one. The theater
    loader refuses a second HQ (`enemy_hq`: exactly one HQ, owned by ENEMY), so the node's kind is
    changed in `Rules.node_kind`, the one table the capture reads a kind from."""
    w = world(SHIPPED)
    assert w.rules is not None
    w.rules = dataclasses.replace(w.rules, node_kind={**w.rules.node_kind, WEST_FOB: "HQ"})
    return w


# --- the shipped values -------------------------------------------------------------------------


def test_the_shipped_keys_reach_the_rules() -> None:
    cap = SHIPPED.rules.capture
    assert cap is not None
    assert dict(cap.time_mult) == {**dict.fromkeys(KINDS, 1.0), "HQ": 20.0}
    assert dict(cap.extra) == {**dict.fromkeys(KINDS, 0.0), "HQ": 0.5}


def test_a_lone_capturer_takes_2000_ticks_at_an_hq_and_100_at_a_fob() -> None:
    w = world(SHIPPED)
    crowd(w, ENEMY_HQ, "COALITION", 1)
    run(w)
    assert progress(w, ENEMY_HQ) == 50_000  # 1e8 x 0.6 / 1200
    assert flip_tick(w, ENEMY_HQ) == 2000
    w2 = world(SHIPPED)
    crowd(w2, ENEMY_FOB, "COALITION", 1)
    assert flip_tick(w2, ENEMY_FOB) == 100


@pytest.mark.parametrize(("n", "ticks"), [(4, 500), (10, 200), (20, 100)])
def test_more_capturers_speed_an_hq_capture_in_proportion(n: int, ticks: int) -> None:
    w = world(SHIPPED)
    crowd(w, ENEMY_HQ, "COALITION", n)
    assert flip_tick(w, ENEMY_HQ) == ticks  # 1200 s / n (exponent 0.5 + 0.5)


def test_min_time_s_still_caps_a_crowd_at_an_hq() -> None:
    w = world(SHIPPED)
    crowd(w, ENEMY_HQ, "COALITION", 50)  # 1200 / 50 = 24 s, under min_time_s 30: 50 ticks, not 40
    assert flip_tick(w, ENEMY_HQ) == 50


def test_a_lone_logistics_capturer_takes_twice_the_lone_time() -> None:
    w = world(SHIPPED)
    crowd(w, ENEMY_HQ, "COALITION", 1, TRUCK)  # weight 0.5: 1200 / 0.5^1.0 = 2400 s
    run(w)
    assert progress(w, ENEMY_HQ) == 25_000
    assert flip_tick(w, ENEMY_HQ) == 4000


@settings(max_examples=30, deadline=None)
@given(st.integers(1, 60))
def test_an_hq_never_fills_faster_than_a_fob_and_a_crowd_never_slows_it(n: int) -> None:
    w = world(SHIPPED)
    crowd(w, ENEMY_HQ, "COALITION", n)
    crowd(w, ENEMY_FOB, "COALITION", n)
    w2 = world(SHIPPED)
    crowd(w2, ENEMY_HQ, "COALITION", n + 1)
    run(w)
    run(w2)
    assert progress(w, ENEMY_HQ) <= progress(w, ENEMY_FOB)
    assert progress(w, ENEMY_HQ) <= progress(w2, ENEMY_HQ)


# --- the neutral values: every capture as before NX-490 -------------------------------------------


def test_at_1_and_0_an_hq_is_captured_like_any_base() -> None:
    cfg = shipped_config(NEUTRAL_KEYS)
    for node, n, ticks in ((ENEMY_HQ, 1, 100), (ENEMY_HQ, 4, 50), (ENEMY_FOB, 1, 100)):
        w = world(cfg)
        crowd(w, node, "COALITION", n)
        assert flip_tick(w, node) == ticks  # 60 s / n^0.5, floored at 30 s


@pytest.mark.parametrize(
    ("key", "node", "ticks"),
    [
        ("capture.time_mult.FOB", ENEMY_FOB, 200),  # 60 s x 2
        ("capture.time_mult.AIRBASE", ENEMY_AIRBASE, 200),
        ("capture.time_mult.HQ", ENEMY_FOB, 100),  # another kind's key leaves the FOB alone
    ],
)
def test_each_kind_reads_its_own_time_mult(key: str, node: str, ticks: int) -> None:
    w = world(shipped_config({key: 2.0}))
    crowd(w, node, "COALITION", 1)
    assert flip_tick(w, node) == ticks


def test_each_kind_reads_its_own_extra_exponent() -> None:
    w = world(shipped_config({"capture.extra_exponent.FOB": 0.5}))
    crowd(w, ENEMY_FOB, "COALITION", 2)  # 60 / 2^1.0 = 30 s: 50 ticks (n^0.5 alone: 71)
    assert flip_tick(w, ENEMY_FOB) == 50


# --- parity (ECONOMY EC-3) ------------------------------------------------------------------------


@pytest.mark.parametrize(("n", "ticks"), [(1, 2000), (4, 500)])
def test_the_hq_keys_apply_alike_to_either_side(n: int, ticks: int) -> None:
    w = two_hq_world()
    assert w.owner[WEST_FOB] == "COALITION"
    crowd(w, WEST_FOB, "ENEMY", n)
    assert flip_tick(w, WEST_FOB) == ticks
    assert w.owner[WEST_FOB] == "ENEMY"
    w2 = two_hq_world()
    crowd(w2, ENEMY_HQ, "COALITION", n)
    assert flip_tick(w2, ENEMY_HQ) == ticks
    assert w2.owner[ENEMY_HQ] == "COALITION"


# --- the loader ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("capture.time_mult.HQ", 0),
        ("capture.time_mult.FOB", -1.0),
        ("capture.extra_exponent.HQ", -0.1),
        ("capture.time_mult", {k: 1.0 for k in KINDS if k != "PORT"}),  # a missing kind
        ("capture.extra_exponent", {k: 0.0 for k in KINDS if k != "HQ"}),
        ("capture.time_mult", {**dict.fromkeys(KINDS, 1.0), "BRIDGE": 1.0}),  # an unknown kind
        ("capture.extra_exponent", {**dict.fromkeys(KINDS, 0.0), "DEPOT": 0.0}),
    ],
)
def test_the_loader_refuses_a_bad_value(key: str, value: object) -> None:
    with pytest.raises(ConfigError):
        shipped_config({key: value})


def test_non_default_values_reach_the_rules() -> None:
    cap = shipped_config({"capture.time_mult.HQ": 7.5, "capture.extra_exponent.PORT": 0.25})
    assert cap.rules.capture is not None
    assert (cap.rules.capture.time_mult["HQ"], cap.rules.capture.extra["PORT"]) == (7.5, 0.25)


# --- save, load and determinism -----------------------------------------------------------------


def mid_hq_capture() -> World:
    w = world(SHIPPED)
    crowd(w, ENEMY_HQ, "COALITION", 1)
    run(w, 1000)
    return w


def test_a_snapshot_mid_hq_capture_continues_identically() -> None:
    w = mid_hq_capture()
    assert progress(w, ENEMY_HQ) == CAPTURE_FULL // 2
    restored = load(save(w))
    assert state_hash(restored) == state_hash(w)
    restored.rules = w.rules
    assert flip_tick(restored, ENEMY_HQ) == flip_tick(w, ENEMY_HQ) == 2000
    assert state_hash(restored) == state_hash(w)


def test_two_hq_capture_runs_hash_equal() -> None:
    def scenario() -> tuple[str, int]:
        w = mid_hq_capture()
        return state_hash(w), flip_tick(w, ENEMY_HQ)

    assert scenario() == scenario()
