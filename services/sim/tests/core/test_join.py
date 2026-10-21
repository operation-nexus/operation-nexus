"""NX-122: the JOIN handler (GAMEPLAY GP-1, GP-2, §1b; STATE-MACHINES §4.1; SIM-CORE SC-6/7/9/14).

Runs on the shipped strait-1 config: the sanctuary is `haven` at (20 km, 120 km), roads run
haven - west-airbase - fob-n-w, bridge nodes have no road of their own, `slots.respawn_delay_s`
is 20 s (200 ticks) and `sim.time_scale` 6 (0.6 world s per tick).
"""

import dataclasses
import os
import subprocess
import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter

from nexus.contracts.gen.commands.join import JoinCommand
from nexus.contracts.gen.events.command_rejected import CommandRejected
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.unit_spawned import UnitSpawned
from nexus.core.step import step
from nexus.core.world import Campaign, Vec2, World, load, save, state_hash
from nexus.runtime.campaign_config import load_campaign_config

CAMPAIGN_ID = "0192f3a4-5b6c-7d8e-9f01-23456789abcd"
# The campaign layer is off: these tests are about JOIN, not objectives (NX-126).
RULES = dataclasses.replace(load_campaign_config().rules, campaign=None)
HAVEN = Vec2(20_000, 120_000)


def cid(n: int) -> str:
    return f"0192f0c1-7a2b-7c3d-8e4f-{n:012d}"


def join(
    n: int = 1, role: str = "STRIKE", node: str | None = None, **fields: object
) -> JoinCommand:
    payload = {
        "kind": "JOIN",
        "source": "CHAT",
        "issuer": {"commander_id": cid(n)},
        "target_tick": 1,
        "arrival_seq": n,
        "correlation_id": f"m{n}",
        "role": role,
        "target": None if node is None else {"node_id": node},
        "hold": False,
    }
    return JoinCommand.model_validate({**payload, **fields})


def new_world() -> World:
    return World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"), RULES)


def at_tick(w: World, tick: int, *commands: JoinCommand) -> list[Event]:
    """Step `w` with no commands up to `tick - 1`, then compute `tick` with `commands`."""
    while w.campaign.tick < tick - 1:
        step(w, [])
    return step(w, [c.model_copy(update={"target_tick": tick}) for c in commands])


def reasons(events: list[Event]) -> list[str]:
    return [e.reason for e in events if isinstance(e, CommandRejected)]


def test_spawns_at_the_sanctuary_with_its_role_kind() -> None:
    w = new_world()
    events = step(w, [join(1, "RECON", hold=True)])
    assert [TypeAdapter(Event).validate_python(e.model_dump()) for e in events] == events
    assert events == [
        UnitSpawned(
            kind="UnitSpawned",
            tick=1,
            event_seq=1,
            campaign_id=CAMPAIGN_ID,
            entity_id=1,
            unit_kind="RECON_UAV",
            side="COALITION",
            owner_kind="COMMANDER",
            commander_id=cid(1),
            callsign=None,
            node_id="haven",
            loadout="FULL",
        )
    ]
    (unit,) = w.entities()
    assert (unit.kind, unit.side, unit.owner_kind, unit.commander_id) == (
        "RECON_UAV",
        "COALITION",
        "COMMANDER",
        cid(1),
    )
    assert (unit.pos, unit.vel, unit.path, unit.last_node, unit.hp) == (
        HAVEN,
        Vec2(0, 0),
        [],
        "haven",
        60,  # RECON_UAV's catalog hp (Q-SIM-65)
    )


@pytest.mark.parametrize("hold", [True, False])
def test_no_target_holds_at_the_sanctuary(hold: bool) -> None:
    # hold, or null target (auto-tasking comes with the Tasking Board, NX-155): Holding, no path.
    w = new_world()
    step(w, [join(1, "LOGI", hold=hold)])
    step(w, [])
    (unit,) = w.entities()
    assert (unit.pos, unit.path) == (HAVEN, [])


def test_ground_unit_takes_the_road_route() -> None:
    w = new_world()
    step(w, [join(1, "LOGI", "fob-n-w")])
    (unit,) = w.entities()
    # It already moved in its spawn tick (SC-13): 25 m/s x 0.6 s east, toward west-airbase.
    assert (unit.pos, unit.path) == (Vec2(20_015, 120_000), ["west-airbase", "fob-n-w"])


def test_air_unit_flies_straight_to_the_node() -> None:
    w = new_world()
    step(w, [join(1, "STRIKE", "bridge-n")])  # aircraft may fly to a node no road reaches
    (unit,) = w.entities()
    assert unit.path == ["bridge-n"]
    # 250 m/s x 0.6 s = 150 m toward bridge-n at (200 km, 60 km): direction (3, -1) / sqrt(10).
    assert (round(unit.pos.x, 6), round(unit.pos.y, 6)) == (20_142.302495, 119_952.565835)


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        (join(1, "STRIKE", "nowhere"), "NODE_UNKNOWN"),
        (join(1, "LOGI", "bridge-n"), "NODE_INVALID_FOR_UNIT"),  # no road reaches a bridge node
        (join(1, "NAVY"), "ROLE_UNKNOWN"),  # NAVY is P3
        (join(1, "STRIKE", "fob-n-w", hold=True), "INVALID_PAYLOAD"),  # hold only with no target
        # Every follow until follow lands (Q-GP-31, Q-GP-33).
        (join(1, "STRIKE", target={"follow_entity_id": 1}), "FOLLOW_TARGET_INVALID"),
    ],
)
def test_invalid_join_is_rejected_and_spawns_nothing(command: JoinCommand, reason: str) -> None:
    w = new_world()
    events = step(w, [command])
    assert events == [
        CommandRejected(
            kind="CommandRejected",
            tick=1,
            event_seq=1,
            campaign_id=CAMPAIGN_ID,
            arrival_seq=1,
            command_kind="JOIN",
            reason=reason,  # type: ignore[arg-type]  # a RejectReason literal from the table
            commander_id=cid(1),
        )
    ]
    assert len(w) == 0


def test_gp1_one_live_unit_per_commander() -> None:
    w = new_world()
    events = step(
        w, [join(1, arrival_seq=1), join(1, "LOGI", arrival_seq=2), join(2, arrival_seq=3)]
    )
    assert [e.kind for e in events] == ["UnitSpawned", "CommandRejected", "UnitSpawned"]
    assert reasons(events) == ["UNIT_IN_SORTIE"]
    assert [e.event_seq for e in events] == [1, 2, 3]
    # The unit gone without a loss (e.g. idle retire): the commander may join again at once.
    w.remove(1)
    assert [e.kind for e in at_tick(w, 2, join(1))] == ["UnitSpawned"]


def lose_on(w: World, tick: int, n: int) -> None:
    """Commander `n` loses a unit on `tick`, before `lifecycle` (as combat would, NX-124)."""
    at_tick(w, tick - 1)
    w.record_loss(cid(n))


def test_gp2_respawn_delay_boundary_tick() -> None:
    # Lost on tick 50; the delay is 20 s of game time = 200 ticks: tick 249 is early, 250 is not.
    w = new_world()
    lose_on(w, 50, 1)
    early = at_tick(w, 249, join(1, arrival_seq=1), join(2, arrival_seq=2))
    assert [e.kind for e in early] == ["CommandRejected", "UnitSpawned"]  # others unaffected
    assert reasons(early) == ["RESPAWN_COOLDOWN"]
    assert [e.kind for e in at_tick(w, 250, join(1))] == ["UnitSpawned"]
    assert w.respawn_left == {}  # the entry is gone once it reaches 0


def test_gp2_respawn_delay_freezes_while_paused() -> None:
    # SC-11: a pause stops the countdown. Lost on tick 11, then 50 paused ticks (21..70).
    w = new_world()
    lose_on(w, 11, 1)
    at_tick(w, 20)
    left = w.respawn_left[cid(1)]
    assert left == 190  # 200 less the running ticks 11..20
    w.campaign.clock_paused = True
    at_tick(w, 70)
    assert w.respawn_left == {cid(1): left}
    w.campaign.clock_paused = False
    # 200 running ticks from tick 11, plus the 50 paused ticks: 260 is early, 261 is not.
    assert reasons(at_tick(w, 260, join(1))) == ["RESPAWN_COOLDOWN"]
    assert [e.kind for e in at_tick(w, 261, join(1))] == ["UnitSpawned"]


def test_other_domains_cannot_take_a_node_target() -> None:
    # Only AIR flies to a node and only GROUND drives roads; SEA (P3) and STATIC are refused.
    rules = dataclasses.replace(
        RULES, role_kind={"STRIKE": "RADAR_SITE"}, domain={"RADAR_SITE": "STATIC"}
    )
    w = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"), rules)
    assert reasons(step(w, [join(1, "STRIKE", "fob-n-w")])) == ["NODE_INVALID_FOR_UNIT"]
    assert len(w) == 0


@pytest.mark.parametrize(
    ("setup", "command", "reason"),
    [
        # Paused with a live unit: a world-changing JOIN (SC-11); with none it may queue.
        ("paused-live", join(1, "NAVY", "nowhere", hold=True), "CAMPAIGN_PAUSED"),
        ("paused", join(1, "NAVY"), "ROLE_UNKNOWN"),
        ("", join(1, "NAVY", "nowhere", hold=True), "INVALID_PAYLOAD"),
        ("", join(1, "NAVY", "nowhere"), "ROLE_UNKNOWN"),
        ("live", join(1, "STRIKE", "nowhere"), "UNIT_IN_SORTIE"),
        ("live", join(1, "STRIKE", target={"follow_entity_id": 1}), "UNIT_IN_SORTIE"),
        ("cooldown", join(1, "STRIKE", "nowhere"), "RESPAWN_COOLDOWN"),
        ("cooldown", join(1, "STRIKE", target={"follow_entity_id": 1}), "RESPAWN_COOLDOWN"),
    ],
)
def test_check_order_first_fault_wins(setup: str, command: JoinCommand, reason: str) -> None:
    w = new_world()
    if setup.endswith("live"):
        step(w, [join(1)])
    if setup == "cooldown":
        w.record_loss(cid(1))
    w.campaign.clock_paused = setup.startswith("paused")
    assert reasons(at_tick(w, w.campaign.tick + 1, command)) == [reason]


def test_a_world_without_rules_raises() -> None:
    w = World.new(Campaign(CAMPAIGN_ID, 12345, "cfg-test"))
    with pytest.raises(ValueError, match="rules"):
        step(w, [join(1)])


MIXED = [
    join(1, "STRIKE", "east-airbase"),
    join(2, "LOGI", "fob-s-w"),
    join(1, "RECON"),
    join(3, "NAVY"),
    join(4, "RECON", hold=True),
    join(2, "STRIKE", "nowhere"),
]


def mixed_world() -> World:
    w = new_world()
    step(w, [c.model_copy(update={"arrival_seq": i}) for i, c in enumerate(MIXED, 1)])
    w.record_loss(cid(9))
    w.callsigns[cid(9)] = "ALPHA-01"  # NX-370: in the hash and the hash-seed check
    at_tick(w, 21)
    return w


@given(st.permutations(range(len(MIXED))))
def test_sc6_list_order_does_not_matter(order: list[int]) -> None:
    stamped = [c.model_copy(update={"arrival_seq": i}) for i, c in enumerate(MIXED, 1)]
    a, b = new_world(), new_world()
    assert step(a, stamped) == step(b, [stamped[i] for i in order])
    assert state_hash(a) == state_hash(b)


def test_snapshot_round_trip_keeps_the_respawn_delay() -> None:
    w = mixed_world()
    loaded = load(save(w))
    assert state_hash(loaded) == state_hash(w)
    # Recorded after tick 1, counted down by ticks 2..21: 200 - 20 left.
    assert loaded.respawn_left == {cid(9): 180}
    loaded.rules = RULES  # not in snapshots (SIM-CORE §4); the runtime re-attaches it
    assert reasons(at_tick(loaded, 201, join(9))) == ["RESPAWN_COOLDOWN"]
    assert [e.kind for e in at_tick(loaded, 202, join(9))] == ["UnitSpawned"]
    # The delay is world state: a new loss changes the hash.
    w.record_loss(cid(9))
    assert state_hash(w) != state_hash(load(save(mixed_world())))


_CHILD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from test_join import mixed_world\n"
    "from nexus.core.world import state_hash; print(state_hash(mixed_world()))"
)


def test_join_state_hash_is_hash_seed_independent() -> None:
    def run(hash_seed: str) -> str:
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        argv = [sys.executable, "-c", _CHILD, os.path.dirname(__file__)]
        # fixed argv: this interpreter + a literal script
        return subprocess.check_output(argv, env=env, text=True).strip()  # noqa: S603

    assert run("1") == run("2") == state_hash(mixed_world())
