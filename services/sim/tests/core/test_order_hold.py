"""NX-398 (Q-SIM-110): an armed unit sent to a node by a direct order holds it (GAMEPLAY §1b).

Runs on the shipped strait-1 config as test_tasking does: west-airbase (90 km, 120 km) is a
coalition landing base, fob-n-w (130 km, 60 km) and fob-s-w coalition FOBs. Shipped keys: a board
pass every 50 running ticks, `tasking.order_dwell_s` 600 game s = 6,000 ticks at 10 Hz. A held unit
keeps the board off; the order ends at bingo or RTB, ammo out, a new order (REBASE) or the dwell,
whichever is first, and the board may take the unit at that pass.
"""

import msgpack
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_join import cid, join
from test_rebase import send
from test_tasking import EVERY, RULES, TR, board_pass, new_world, post, put

from nexus.contracts.gen.events.weapon_fired import WeaponFired
from nexus.core.step import step
from nexus.core.world import Entity, Vec2, World, load, save, state_hash

DWELL = 6_000  # 600 game s at 10 Hz (balance/default.yaml tasking.order_dwell_s)
FOB = "fob-n-w"


def holding(kind: str = "STRIKE_FIGHTER") -> tuple[World, Entity]:
    """A viewer's unit standing at (aircraft: orbiting over) FOB with a GOTO order it reached."""
    w = new_world()
    e = put(w, kind, FOB)  # type: ignore[arg-type]
    e.order, e.order_node = "GOTO", FOB
    if RULES.domain[e.kind] == "AIR":
        e.state, e.orbit = "ON_STATION", Vec2(*RULES.roads.pos[FOB])
    return w, e


def order_of(e: Entity) -> tuple[object, ...]:
    """The order fields, read fresh (an assert before does not narrow them for later passes)."""
    return e.order, e.held_since


def test_the_dwell_key_is_600_game_seconds() -> None:
    assert TR.order_dwell_ticks == DWELL


def test_an_armed_jet_holds_its_node_past_the_next_pass_and_the_board_leaves_it() -> None:
    w, jet = holding()
    job = post(w, "COALITION", "DEFEND", "fob-s-w", "d", slots=4)  # a job it fits
    board_pass(w)
    start = w.campaign.running_ticks
    assert (jet.order, jet.held_since, jet.job_id) == ("GOTO", start, None)
    for _ in range(DWELL // EVERY - 1):  # every pass up to the last before the dwell ends
        board_pass(w)
    assert (jet.order, jet.job_id) == ("GOTO", None) and job.claims == {}
    board_pass(w)  # DWELL ticks after the hold began: the order ends, the board takes the jet
    assert w.campaign.running_ticks - start == DWELL
    assert (jet.order, jet.held_since, jet.job_id) == (None, None, job.id)


def test_a_holding_jet_engages_a_target_that_appears() -> None:
    w = new_world()
    step(w, [join(1, "STRIKE", FOB)])
    (jet,) = [e for e in w.entities() if e.commander_id == cid(1)]
    for _ in range(20_000):
        if jet.state == "ON_STATION" and jet.held_since is not None:
            break
        step(w, [])
    else:
        raise AssertionError("the jet never began holding")
    for _ in range(3 * EVERY):  # three more passes: still there (before NX-398 it was released)
        step(w, [])
    assert jet.order == "GOTO" and jet.state == "ON_STATION"
    x, y = RULES.roads.pos[FOB]
    w.spawn("ENEMY_ARMOR", "ENEMY", "AI_GARRISON", Vec2(x + 500.0, y))
    for _ in range(600):
        events = step(w, [])
        if any(isinstance(ev, WeaponFired) and ev.shooter_id == jet.id for ev in events):
            break
    else:
        raise AssertionError("the holding jet never fired")
    assert jet.order == "GOTO"  # it fired while still holding (out of AG rounds it goes home)


def test_bingo_ends_the_hold() -> None:
    w, jet = holding()
    board_pass(w)
    assert jet.held_since is not None
    jet.fuel = 1.0  # below the bingo line: the movement slot turns it for home
    step(w, [])
    assert jet.state == "RTB" and jet.path
    board_pass(w)
    assert order_of(jet) == (None, None)


def test_ammo_out_ends_the_hold() -> None:
    w, jet = holding()
    job = post(w, "COALITION", "DEFEND", "fob-s-w", "d", slots=4)
    board_pass(w)
    jet.ammo = [0] * len(jet.ammo)
    board_pass(w)
    assert (jet.order, jet.held_since, jet.job_id) == (None, None, job.id)


def test_a_new_order_ends_the_hold() -> None:
    w, jet = holding()
    board_pass(w)
    assert jet.held_since is not None
    send(w, jet, "west-airbase")
    assert (*order_of(jet), jet.order_node, jet.path) == ("HOLD", None, None, ["west-airbase"])


@pytest.mark.parametrize("kind", ["LOGI_TRUCK", "RECON_UAV"])
def test_an_unarmed_unit_hands_back_at_the_first_pass_as_before(kind: str) -> None:
    w, e = holding(kind)
    if kind == "LOGI_TRUCK":
        e.cargo = 0  # an empty truck whose stop ended
    board_pass(w)
    assert (e.order, e.held_since) == (None, None)


def test_an_armed_jet_that_landed_at_its_goto_base_hands_back() -> None:
    w = new_world()
    jet = put(w, "STRIKE_FIGHTER", "west-airbase")  # LANDED
    jet.order, jet.order_node = "GOTO", "west-airbase"
    board_pass(w)
    assert order_of(jet) == (None, None)


def test_a_disabled_unit_does_not_hold() -> None:
    w, e = holding("GARRISON_INFANTRY")
    board_pass(w)
    assert e.held_since is not None  # an armed ground unit on its node holds
    e.damage_state = "DISABLED"
    board_pass(w)
    assert order_of(e) == (None, None)


def test_an_armed_unit_stopped_short_of_its_node_hands_back() -> None:
    w, e = holding("GARRISON_INFANTRY")
    e.order_node = "fob-s-w"  # e.g. a down bridge stopped it at FOB
    board_pass(w)
    assert order_of(e) == (None, None)
    w, e = holding("GARRISON_INFANTRY")
    e.pos = Vec2(e.pos.x + 100.0, e.pos.y)  # on the road just past its node
    board_pass(w)
    assert order_of(e) == (None, None)
    w, jet = holding()
    jet.order_node = "fob-s-w"  # orbiting where it last reached, not the order's node
    board_pass(w)
    assert order_of(jet) == (None, None)


def test_a_join_records_the_order_node_and_the_order_end_clears_it() -> None:
    w = new_world()
    step(w, [join(1, "STRIKE", FOB)])
    (jet,) = [e for e in w.entities() if e.commander_id == cid(1)]
    assert (jet.order, jet.order_node) == ("GOTO", FOB)
    jet.ammo = [0] * len(jet.ammo)
    jet.path = []
    board_pass(w)
    assert (jet.order, jet.order_node) == (None, None)


def test_a_hold_survives_a_snapshot_and_the_loader_checks_it() -> None:
    w, jet = holding()
    board_pass(w)
    w.campaign.tick = w.campaign.running_ticks  # `board_pass` moves the running clock only
    again = load(save(w))
    again.rules = RULES
    assert again.get(jet.id).held_since == jet.held_since
    for _ in range(3):
        board_pass(w)
        board_pass(again)
    assert state_hash(again) == state_hash(w)
    w.campaign.tick = w.campaign.running_ticks
    for bad in (
        {"order": None},
        {"order": None, "held_since": None},  # a stale order_node alone is refused too
        {"held_since": w.campaign.running_ticks + 1},
        {"order_node": None},
    ):
        raw = msgpack.unpackb(save(w), raw=False)
        (ent,) = [d for d in raw["entities"] if d["id"] == jet.id]
        ent.update(bad)
        with pytest.raises(ValueError, match=r"needs order GOTO|needs order_node and a past tick"):
            load(msgpack.packb(raw, use_bin_type=True))


def _run(seed: int) -> str:
    w = new_world(seed)
    step(w, [join(1, "STRIKE", FOB), join(2, "LOGI", FOB)])
    for _ in range(3_000):
        step(w, [])
    return state_hash(w)


def test_same_seed_same_hash() -> None:
    assert _run(3) == _run(3)


EXITS = ("none", "ammo", "bingo", "rebase")


@settings(max_examples=25, deadline=None)
@given(st.integers(0, DWELL // EVERY + 3), st.sampled_from(EXITS))
def test_the_first_exit_ends_the_order_and_nothing_sticks(passes: int, exit_: str) -> None:
    """Whatever ends the hold, and after however many passes, the order is gone by the pass after
    it (or by the dwell with no exit) and the unit never keeps `held_since` without GOTO."""
    w, jet = holding()
    board_pass(w)
    start = w.campaign.running_ticks
    for _ in range(passes):
        board_pass(w)
        if jet.order is None:
            break
    if exit_ == "ammo":
        jet.ammo = [0] * len(jet.ammo)
    elif exit_ == "bingo":
        jet.state, jet.path = "RTB", ["west-airbase"]
    elif exit_ == "rebase":
        send(w, jet, "west-airbase")
    board_pass(w)
    over = w.campaign.running_ticks - start >= DWELL
    want = "HOLD" if exit_ == "rebase" else "GOTO" if exit_ == "none" and not over else None
    assert jet.order == want
    assert (jet.held_since is None) == (jet.order != "GOTO")


# --- Q-SIM-124 (NX-408): an order to a bridge holds and defends it, never fires on it ----------

NORTH = "bridge-n"  # NEUTRAL, on the fob-n-w (130 km) ~ cross-n (230 km) road at (200 km, 60 km)


def _bridge_raid(enemy_banks: bool) -> tuple[World, Entity, list[WeaponFired]]:
    """`!join strike bridge-n` from west-airbase; once the jet holds there, a Static convoy parks
    on the span 500 m from the bridge. Steps to the jet's first shot (at most 3,000 ticks)."""
    w = new_world()
    for bank in RULES.roads.spans[NORTH] if enemy_banks else ():
        w.owner[bank] = "ENEMY"  # an enemy-side bridge
    step(w, [join(1, "STRIKE", NORTH)])
    (jet,) = [e for e in w.entities() if e.commander_id == cid(1)]
    shots: list[WeaponFired] = []
    convoy = None
    for _ in range(3_000):
        shots += [e for e in step(w, []) if isinstance(e, WeaponFired) and e.shooter_id == jet.id]
        if convoy is None and jet.held_since is not None:
            convoy = w.spawn("ENEMY_CONVOY", "ENEMY", "AI_GARRISON", Vec2(200_500, 60_000))
            convoy.last_node = "cross-n"
        if shots:
            break
    return w, jet, shots


@pytest.mark.parametrize("enemy_banks", [False, True])  # as shipped, or both banks the Static's
def test_a_jet_ordered_to_a_bridge_holds_and_engages_but_never_fires_on_it(
    enemy_banks: bool,
) -> None:
    w, jet, shots = _bridge_raid(enemy_banks)
    assert (jet.order, jet.order_node) == ("GOTO", NORTH) and jet.held_since is not None
    assert shots and all(s.target_node_id is None and s.target_id is not None for s in shots)
    assert w.bridge_hp[NORTH] == RULES.supply.bridge_hp[NORTH] and w.bridge_down == set()


def test_a_bridge_hold_is_deterministic() -> None:
    (a, _, sa), (b, _, sb) = _bridge_raid(True), _bridge_raid(True)
    assert state_hash(a) == state_hash(b) and sa == sb
