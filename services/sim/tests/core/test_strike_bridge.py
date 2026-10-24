"""NX-401: the Threat Director's STRIKE_BRIDGE operation (THREAT-DIRECTOR §4 step 3, §7a Part 5;
Q-SIM-112, Q-SIM-120, Q-SIM-121). "Cut the lifeline": an intact bridge on the shortest intact road
from the coalition sanctuary (haven) to a node the coalition holds, at ALPHA or above, while no
bridge is down and the bridge's cooldown since its `BridgeRepaired` has run out; two
ENEMY_STRIKE_FIGHTERs strike it. Chosen from roads and owners only, never from units.

strait-1: haven ~ west-airbase ~ fob-n-w ~[bridge-n]~ cross-n ~ fob-n-e; the south mirrors it over
bridge-s. At the start the coalition holds only the west bank, so no bridge feeds a held node.
"""

import dataclasses
from fractions import Fraction
from itertools import pairwise

import msgpack
import pytest
from test_combat import sure
from test_launch import (
    DR,
    RULES,
    candidates,
    clear_coalition_defenses,
    ids,
    new_world,
    scores,
    unit,
    window,
    zero_noise,
)

from nexus.contracts.gen.events.bridge_destroyed import BridgeDestroyed
from nexus.contracts.gen.events.bridge_repaired import BridgeRepaired
from nexus.contracts.gen.events.event import Event
from nexus.core import bridges, operations, provocation
from nexus.core.fog import side_view
from nexus.core.logistics import supply_route
from nexus.core.operations import Own
from nexus.core.roads import shortest_path
from nexus.core.rules import Rules
from nexus.core.step import step
from nexus.core.world import Job, Vec2, World, load, save, state_hash

OP = "STRIKE_BRIDGE"
NORTH, SOUTH = "bridge-n", "bridge-s"
COOLDOWN = DR.bridge_cooldown_ticks
_sure = sure("AG_LIGHT")
# Only STRIKE_BRIDGE in the catalog, no noise, AG_LIGHT always hits: the chain test is about the
# operation, not about which of the ALPHA candidates the noise ranks first.
ONLY = dataclasses.replace(
    zero_noise(RULES),
    combat=_sure.combat,
    director=dataclasses.replace(DR, noise=Fraction(0), operations=tuple(
        o for o in DR.operations if o.id == OP
    )),
)  # fmt: skip


def across(seed: int = 1, rules: Rules = RULES) -> World:
    """The coalition holds the north crossing, on the east bank over bridge-n."""
    w = new_world(seed, rules)
    w.owner["cross-n"] = "COALITION"
    return w


def run(w: World, ticks: int) -> list[Event]:
    out: list[Event] = []
    for _ in range(ticks):
        out += step(w, [])
    return out


def test_the_cooldown_key_is_1800_game_seconds_in_ticks() -> None:
    assert COOLDOWN == 1800 * 10  # director.strike_bridge.cooldown_s, 10 Hz game ticks


# --- candidates (Q-SIM-120, Q-SIM-121) -----------------------------------------------------------


def test_no_bridge_is_a_target_while_the_coalition_holds_nothing_across() -> None:
    w = new_world()
    assert ids(candidates(w), OP) == []
    assert operations.fed_nodes(side_view(w, "ENEMY"), RULES, NORTH) == []


@pytest.mark.parametrize("tier", ["ALPHA", "BRAVO"])
def test_a_bridge_that_feeds_a_held_node_is_a_candidate_from_alpha(tier: str) -> None:
    w = across()
    assert ids(candidates(w, tier), OP) == [NORTH]  # type: ignore[arg-type]
    assert operations.fed_nodes(side_view(w, "ENEMY"), RULES, NORTH) == ["cross-n"]
    (c,) = [c for c in candidates(w) if c.op.id == OP]
    assert [[x.node for x in where] for where in c.wheres] == [[NORTH]]


def test_none_at_pattern_of_life() -> None:
    assert ids(candidates(across(), "PATTERN_OF_LIFE"), OP) == []


def test_none_while_another_bridge_is_down() -> None:
    w = across()
    w.bridge_down.add(SOUTH)
    w.bridge_hp[SOUTH] = 0
    assert ids(candidates(w), OP) == []


def test_none_for_a_bridge_already_down() -> None:
    w = across()
    w.bridge_down.add(NORTH)
    w.bridge_hp[NORTH] = 0
    assert ids(candidates(w), OP) == []


def test_the_south_bridge_feeds_only_what_lies_beyond_it() -> None:
    w = across()
    w.owner["cross-s"] = "COALITION"
    assert ids(candidates(w), OP) == [NORTH, SOUTH]
    w.owner["cross-n"] = "NEUTRAL"
    assert ids(candidates(w), OP) == [SOUTH]


def test_a_cut_road_is_not_fed_through_a_static_base() -> None:
    """With bridge-s down, the only road to cross-s runs over bridge-n and the Static's
    east-airbase; trucks never drive it (Q-SIM-122), so bridge-n feeds cross-n only."""
    w = across()
    w.bridge_down.add(SOUTH)
    w.owner["cross-s"] = "COALITION"
    view = side_view(w, "ENEMY")
    assert operations.fed_nodes(view, RULES, NORTH) == ["cross-n"]
    assert operations.fed_nodes(view, RULES, SOUTH) == []


def test_the_lifeline_is_the_route_trucks_drive_not_the_shortest_road() -> None:
    """The coalition holds east-airbase, the Static both crossings: the shortest road crosses a
    bridge, but the supply route (no Static-held node, Q-SIM-122) has no way there, so neither
    bridge is a lifeline. The world-side `logistics.supply_route` agrees."""
    w = new_world()
    w.owner.update({"east-airbase": "COALITION", "cross-n": "ENEMY", "cross-s": "ENEMY"})
    road = shortest_path(RULES.roads, "haven", "east-airbase", blocked=frozenset())
    assert road is not None and {RULES.roads.edge(a, b).bridge for a, b in pairwise(road)} & {
        NORTH, SOUTH
    }  # fmt: skip
    assert supply_route(w, RULES, "COALITION", "haven", "east-airbase") is None
    view = side_view(w, "ENEMY")
    assert operations.fed_nodes(view, RULES, NORTH) == []
    assert operations.fed_nodes(view, RULES, SOUTH) == []
    assert ids(candidates(w), OP) == []


def test_each_bridge_precondition_on_its_own() -> None:
    """Each one alone (in the catalog `no_bridge_contested` and the feed would hide others)."""
    w = across()
    state, now = w.director["ENEMY"], w.campaign.running_ticks + 1

    def holds(pre: str, node: str, own: Own | None = None) -> bool:
        view = side_view(w, "ENEMY")
        return operations._holds(pre, node, state, view, RULES, own or Own(), now)

    assert holds("target_is_bridge", NORTH) and not holds("target_is_bridge", "cross-n")
    assert holds("target_bridge_intact", NORTH) and not holds("target_bridge_intact", "cross-n")
    assert not holds("target_feeds_coalition_node", "cross-n")  # a node, not a bridge
    assert holds("no_bridge_contested", NORTH)
    assert not holds("no_bridge_contested", NORTH, Own(struck=frozenset({SOUTH})))
    w.bridge_down.add(NORTH)
    assert not holds("target_bridge_intact", NORTH) and holds("target_bridge_intact", SOUTH)
    assert not holds("no_bridge_contested", SOUTH)


def test_none_while_a_live_strike_is_on_another_bridge() -> None:
    w = across()
    w.owner["cross-s"] = "COALITION"
    job = Job(w.next_job_id(), "STRIKE", f"strike:{SOUTH}", 2, 1000, 0, node=SOUTH)
    w.boards["ENEMY"][job.id] = job
    assert ids(candidates(w), OP) == []
    del w.boards["ENEMY"][job.id]
    assert ids(candidates(w), OP) == [NORTH, SOUTH]


def test_bravo_strikes_one_bridge_at_a_time() -> None:
    """Both bridges feed a held crossing; BRAVO has the budget (80) and no operation cap, yet one
    window posts one STRIKE_BRIDGE and the next window none while it is live."""
    w = across(1, ONLY)
    w.owner["cross-s"] = "COALITION"
    clear_coalition_defenses(w)

    def struck() -> list[str]:
        keys = {j.key.split(":")[2] for j in w.boards["ENEMY"].values()}
        return sorted(k for k in keys if k in (NORTH, SOUTH))

    window(w, "BRAVO", 80, ONLY)
    assert len(struck()) == 1
    first = struck()
    run(w, 1)
    window(w, "BRAVO", 80, ONLY)
    assert struck() == first


def test_select_takes_one_bridge_strike_per_window() -> None:
    w = across()
    w.owner["cross-s"] = "COALITION"
    w.director["ENEMY"].tier = "BRAVO"
    ranked = [c for c in candidates(w, "BRAVO") if c.op.id == OP]
    assert [c.target for c in ranked] == [NORTH, SOUTH]
    chosen = operations.select(ranked, DR, 80, 6, 70, frozenset(), None)
    assert [c.target for c in chosen] == [NORTH]


def test_the_cooldown_holds_it_back_until_it_ends() -> None:
    w = across()
    now = w.campaign.running_ticks + 1
    w.director["ENEMY"].bridge_ready[NORTH] = now + 1
    assert ids(candidates(w), OP) == []
    w.campaign.running_ticks += 1  # the tick it becomes ready
    assert ids(candidates(w), OP) == [NORTH]


def test_a_repair_starts_the_cooldown_from_its_running_tick() -> None:
    w = across()
    w.bridge_down.add(NORTH)
    w.bridge_hp[NORTH] = RULES.supply.bridge_hp[NORTH] - 1
    w.bridge_repair[NORTH] = 999
    truck = w.spawn("LOGI_TRUCK", "COALITION", "COMMANDER", Vec2(*RULES.roads.stops[NORTH]))
    truck.last_node = "fob-n-w"
    w.campaign.running_ticks = 100
    out: list[Event] = []
    bridges.repair(w, out)
    assert [e.node_id for e in out if isinstance(e, BridgeRepaired)] == [NORTH]
    assert w.director["ENEMY"].bridge_ready == {NORTH: 101 + COOLDOWN}
    assert w.director["COALITION"].bridge_ready == {}  # no Director runs there


# --- score (§7a Part 5) --------------------------------------------------------------------------


def test_a_bridge_scores_by_the_best_node_it_feeds() -> None:
    quiet = zero_noise(RULES)
    w = across()
    assert RULES.defense is not None and w.defense_hp["cross-n"] == 0  # a neutral crossing
    assert scores(w, quiet)[OP, NORTH] == Fraction(3, 5) * 2  # 0.6 x FOB 1.0 x weakness 2.0
    w.defense_hp["cross-n"] = RULES.defense.max_hp["cross-n"]  # built up: weakness 1.0
    assert scores(w, quiet)[OP, NORTH] == Fraction(3, 5)
    w.owner["fob-n-e"] = "COALITION"  # fed over bridge-n as well, at half its defense hp
    w.defense_hp["fob-n-e"] = RULES.defense.max_hp["fob-n-e"] // 2
    assert scores(w, quiet)[OP, NORTH] == Fraction(3, 5) * Fraction(3, 2)  # fob-n-e's, the best


def test_selection_never_reads_units_on_the_span_or_near_it() -> None:
    """Q-SIM-112, Q-SIM-120: the same candidates, scores and posted jobs with coalition trucks
    parked on bridge-n (and tracked by the Static) and with none."""

    def picked(occupied: bool) -> tuple[object, ...]:
        w = across(3)
        if occupied:
            for dx in (0.0, 300.0, -300.0):
                e = w.spawn("LOGI_TRUCK", "COALITION", "COMMANDER", Vec2(200_000 + dx, 60_000))
                e.last_node = "fob-n-w"
            unit(w, "STRIKE_FIGHTER", "COALITION", "COMMANDER", "cross-n")
            assert any(e.side == "COALITION" for e in w.entities())
        cands = [(c.op.id, c.target, c.wheres) for c in candidates(w)]
        ranked = scores(w)
        window(w, "ALPHA", 30)
        return cands, ranked, sorted(j.key for j in w.boards["ENEMY"].values())

    assert picked(True) == picked(False)


# --- the operation in play ------------------------------------------------------------------------


def test_the_director_posts_it_and_static_jets_drop_the_bridge() -> None:
    w = across(1, ONLY)
    clear_coalition_defenses(w)
    window(w, "ALPHA", 30, ONLY)
    (job,) = [j for j in w.boards["ENEMY"].values() if j.key.startswith(f"op:{OP}:")]
    assert (job.kind, job.node, job.slots) == ("STRIKE", NORTH, 2)
    jets = [w.get(i) for i in job.claims]
    assert [e.kind for e in jets] == ["ENEMY_STRIKE_FIGHTER"] * 2
    events = run(w, 3000)  # 125 km at strike speed, then 6 sure hits
    (down,) = [e for e in events if isinstance(e, BridgeDestroyed)]
    assert down.node_id == NORTH and down.by_id in {e.id for e in jets}
    assert w.bridge_down == {NORTH} and job.id not in w.boards["ENEMY"]  # DONE once down
    assert ids(candidates(w), OP) == []  # one bridge down: no second strike


# --- determinism and snapshot ---------------------------------------------------------------------


def _played(seed: int) -> World:
    w = across(seed, ONLY)
    clear_coalition_defenses(w)
    window(w, "ALPHA", 30, ONLY)
    run(w, 400)
    return w


def test_same_seed_same_hash() -> None:
    assert state_hash(_played(7)) == state_hash(_played(7))


def test_bridge_ready_survives_a_snapshot_and_the_run_continues_the_same() -> None:
    w = _played(7)
    w.director["ENEMY"].bridge_ready = {SOUTH: w.campaign.running_ticks + 5}
    restored = load(save(w))
    restored.rules = w.rules
    assert restored.director["ENEMY"].bridge_ready == {SOUTH: w.campaign.running_ticks + 5}
    assert state_hash(restored) == state_hash(w)
    run(w, 200)
    run(restored, 200)
    assert state_hash(restored) == state_hash(w)


def test_the_hash_reads_bridge_ready() -> None:
    w = across()
    before = state_hash(w)
    w.director["ENEMY"].bridge_ready[NORTH] = 5
    assert state_hash(w) != before


def test_restore_refuses_a_bridge_cooldown_on_a_node_that_is_no_bridge() -> None:
    w = across()
    run(w, 1)
    w.director["ENEMY"].bridge_ready = {"fob-n-w": 5}
    with pytest.raises(ValueError, match="bridge cooldown"):
        provocation.validate(load(save(w)), RULES)


def test_restore_refuses_a_bridge_cooldown_tick_of_zero() -> None:
    w = across()
    w.director["ENEMY"].bridge_ready = {NORTH: 0}
    with pytest.raises(ValueError, match="bridge_ready"):
        load(save(w))


def test_a_stamp_made_under_a_long_cooldown_restores_after_a_reload_shortened_it() -> None:
    """Stamped under 1800 s (bridge) and 600 s (blink); restored under rules where both keys
    were hot-reloaded to shorter values, the snapshot is accepted and the stamps kept."""
    w = across()
    run(w, 1)
    now = w.campaign.running_ticks
    state = w.director["ENEMY"]
    state.bridge_ready = {NORTH: now + COOLDOWN}  # what a repair at this tick stamps
    state.blink_ready = {"east-airbase": now + DR.blink_cooldown_ticks}
    short = dataclasses.replace(
        RULES,
        director=dataclasses.replace(
            DR, bridge_cooldown_ticks=600 * 10, blink_cooldown_ticks=DR.blink_cooldown_ticks // 2
        ),
    )
    assert COOLDOWN == 1800 * 10 and now + COOLDOWN > now + short.director.bridge_cooldown_ticks  # type: ignore[union-attr]
    restored = load(save(w))
    provocation.validate(restored, short)
    assert restored.director["ENEMY"].bridge_ready == {NORTH: now + COOLDOWN}
    assert restored.director["ENEMY"].blink_ready == state.blink_ready


def test_a_snapshot_without_bridge_ready_is_refused() -> None:
    raw = msgpack.unpackb(save(across()), raw=False)
    del raw["director"]["ENEMY"]["bridge_ready"]
    with pytest.raises(ValueError, match="bridge_ready"):
        load(msgpack.packb(raw, use_bin_type=True))
