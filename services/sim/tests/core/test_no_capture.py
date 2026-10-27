"""NX-452: why a decision window launched no capture operation (`launch.no_capture_reason`), a
harness diagnostic the sim never calls. One fixed scene per reason, each a real window
(`launch.run`) on the shipped strait-1 config as test_economy_rules runs it, then the helper on
the world after it; and the helper changes nothing.

Shipped numbers (test_economy_rules): OFFENSIVE costs 60 (6 units), RETAKE 50; the Static's bases
hold 1,500 above their floors; a limited Static's pool starts at 8,000, rear share 0.005;
`cadence_windows` 10; `max_ops.alpha` 1; `max_spawns_per_window` 6.
"""

from test_economy_rules import (
    LEGACY_LIMITED,
    NEW,
    NEW_LIMITED,
    NEW_UNLIMITED,
    at_floor,
    config,
    floor_window,
    operations,
    posted,
    world,
)
from test_staging import at_floor as staging_floor
from test_staging import fire, offensive
from test_staging import world as staging_world

from nexus.core.fog import side_view
from nexus.core.launch import NO_CAPTURE, no_capture_reason
from nexus.core.world import Vec2, World, save

CAPTURE_OPS = ("OFFENSIVE", "RETAKE")


def reason(w: World) -> str:
    """The helper as the harness calls it, at the running tick of the window `launch.run` just
    ran (these tests run no step, so that is `running_ticks + 1`)."""
    assert w.rules is not None
    view = side_view(w, "ENEMY")
    return no_capture_reason(w, "ENEMY", view, w.rules, w.campaign.running_ticks + 1)


def no_capture(w: World) -> bool:
    return not [p for p in posted(w) if p[0] in CAPTURE_OPS]


def test_the_reasons_are_listed_in_priority_order() -> None:
    assert NO_CAPTURE == (
        "staged", "night_cap", "tier", "no_target", "targets_busy", "budget", "floor_not_due",
        "max_ops", "other",
    )  # fmt: skip


def test_staged_an_operation_waits_at_its_staging_base() -> None:
    # forward staging on: the far OFFENSIVE on fob-n-w waits at fob-n-e, which cannot pay
    w = staging_world()
    staging_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    assert w.director["ENEMY"].staged and no_capture(w)
    assert reason(w) == "staged"


def test_staged_comes_before_every_later_reason() -> None:
    # the same scene at Pattern of Life (also `tier`) still reads `staged`
    w = staging_world()
    staging_floor(w)
    fire(w, offensive(w, "fob-n-w"))
    w.director["ENEMY"].tier = "PATTERN_OF_LIFE"
    assert reason(w) == "staged"


def test_night_cap_no_viewer_unit_and_the_cap_spent() -> None:
    w = world(NEW_UNLIMITED)
    w.director["ENEMY"].last_flip = 1  # a flip one tick ago, no viewer unit
    assert floor_window(w, 10) and no_capture(w)
    assert reason(w) == "night_cap"


def test_a_live_viewer_unit_lifts_the_night_cap() -> None:
    # the same scene, then one live COMMANDER unit: the cap needs nobody playing
    w = world(NEW_UNLIMITED)
    w.director["ENEMY"].last_flip = 1
    floor_window(w, 10)
    w.spawn("STRIKE_FIGHTER", "COALITION", "COMMANDER", Vec2(0, 0))
    assert reason(w) != "night_cap"


def test_tier_pattern_of_life_enables_no_capture_operation() -> None:
    w = world(NEW_UNLIMITED)
    operations(w, 100, "PATTERN_OF_LIFE")
    assert no_capture(w)
    assert reason(w) == "tier"


def test_no_target_when_the_static_holds_every_capturable_node() -> None:
    w = world(NEW_UNLIMITED)
    assert w.rules is not None
    for n, side in sorted(w.owner.items()):
        if side == "COALITION" and w.rules.node_kind.get(n) not in w.rules.uncapturable:
            w.owner[n] = "ENEMY"
    floor_window(w, 10, spend=100)
    assert no_capture(w)
    assert reason(w) == "no_target"


def test_targets_busy_a_running_offensive_covers_the_one_target() -> None:
    # the coalition holds one capturable node, west-airbase; window 10's floor sends OFFENSIVE
    # there, and window 11 finds it busy (one operation per target), not targetless
    w = world(NEW_UNLIMITED)
    assert w.rules is not None
    for n, side in sorted(w.owner.items()):
        kind = w.rules.node_kind.get(n)
        if side == "COALITION" and kind not in w.rules.uncapturable and n != "west-airbase":
            w.owner[n] = "ENEMY"
    assert floor_window(w, 10) == [("OFFENSIVE", "west-airbase")]
    floor_window(w, 11, spend=100)
    assert [p for p in posted(w) if p[0] in CAPTURE_OPS] == [("OFFENSIVE", "west-airbase")]
    assert reason(w) == "targets_busy"
    w.boards["ENEMY"].clear()  # the operation over: the target is free again
    assert reason(w) != "targets_busy"


def test_budget_below_the_cheapest_capture_with_the_floor_due() -> None:
    # the floor is due (10 windows), but surplus 0 and rear share floor(400 x 0.005) = 2 count
    # only 2 against OFFENSIVE's 60
    w = world(NEW_LIMITED)
    at_floor(w)
    w.pool["ENEMY"] = 400
    floor_window(w, 10, spend=2)
    assert no_capture(w)
    assert reason(w) == "budget"


def test_budget_under_legacy_rules_which_have_no_floor() -> None:
    # 1,500 surplus would pay OFFENSIVE, but legacy rules have no floor: the budget is all
    w = world(LEGACY_LIMITED)
    floor_window(w, 10, spend=30)
    assert no_capture(w)
    assert reason(w) == "budget"


def test_floor_not_due_the_budget_is_short_but_the_floor_would_pay() -> None:
    # 9 windows: 30 points buy PROBE and RECON; 1,500 surplus would let the floor pay 60
    w = world(NEW_UNLIMITED)
    floor_window(w, 9)
    assert no_capture(w)
    assert reason(w) == "floor_not_due"
    w = world(NEW_UNLIMITED)
    w.owner["static-hq"] = "COALITION"  # no HQ held: the floor never comes due
    floor_window(w, 10)
    assert no_capture(w)
    assert reason(w) == "floor_not_due"


def test_max_ops_a_probe_holds_alphas_one_slot_with_the_floor_not_due() -> None:
    # as test_with_the_floor_not_due_max_ops_holds_as_before: 100 points pay OFFENSIVE
    w = world(NEW_UNLIMITED)
    floor_window(w, 9)
    floor_window(w, 9, spend=100)
    assert no_capture(w)
    assert reason(w) == "max_ops"


def test_max_ops_with_the_floor_due_and_its_one_extra_slot_taken() -> None:
    # as test_the_floors_capture_operation_takes_one_slot_past_max_ops_never_two: two OFFENSIVEs
    # running (cap + 1), the floor due at window 30 launches nothing
    w = world(NEW_UNLIMITED)
    floor_window(w, 10)
    floor_window(w, 20)
    floor_window(w, 30)
    assert len([p for p in posted(w) if p[0] in CAPTURE_OPS]) == 2
    assert w.director["ENEMY"].last_operation == 20  # nothing launched at 30: the floor is due
    assert reason(w) == "max_ops"


def test_with_the_floor_due_one_running_operation_is_not_max_ops() -> None:
    # Q-TD-57: the floor's capture operation may run one past the cap. PROBE holds ALPHA's slot
    # (window 9) and the floor is due at 10: had OFFENSIVE not launched, `max_ops` did not stop
    # it (it would be a payment that failed at launch), so the reason is `other`
    w = world(NEW_UNLIMITED)
    floor_window(w, 9)
    w.director["ENEMY"].windows = 10
    assert reason(w) == "other"


def test_max_ops_when_the_floor_due_cannot_count_the_lead() -> None:
    # Q-TD-48: the floor's lead (one past the cap) must cost no more than `_floor_cap`. PROBE
    # holds ALPHA's slot, the floor is due, the budget (100) pays OFFENSIVE but the floor counts
    # 0 (unlimited, surplus 0): no extra slot, so `max_ops` keeps it out
    w = world(NEW_UNLIMITED)
    floor_window(w, 9)
    at_floor(w)
    s = w.director["ENEMY"]
    s.windows, s.budget = 10, 100
    assert reason(w) == "max_ops"


def test_a_capture_on_a_victory_hold_node_is_outside_max_ops() -> None:
    # Q-TD-46: PROBE holds ALPHA's slot and 100 points pay OFFENSIVE (`max_ops`); with every
    # node in the running victory hold the cap does not apply to it, so it is no `max_ops`
    w = world(NEW_UNLIMITED)
    floor_window(w, 9)
    floor_window(w, 9, spend=100)
    assert reason(w) == "max_ops"
    assert w.rules is not None
    w.campaign.hold_nodes = tuple(sorted(w.rules.roads.pos))
    assert reason(w) == "other"


def test_other_the_live_guard_has_no_room() -> None:
    # EC-8: the guard (3) is full, so OFFENSIVE's 6 units never fit, whatever the money or the cap
    w = world(config({**NEW, "sim.max_live_units_per_side": 3}))
    for _ in range(3):
        w.spawn("ENEMY_ARMOR", "ENEMY", "ENEMY_DIRECTOR", Vec2(0, 0))
    floor_window(w, 10, spend=100)
    assert no_capture(w)
    assert reason(w) == "other"


def test_the_helper_changes_nothing() -> None:
    # no state, no RNG draw: the saved world is byte-identical after each reason's scene
    scenes = [world(NEW_UNLIMITED), world(LEGACY_LIMITED), world(NEW_LIMITED)]
    for w in scenes:
        floor_window(w, 9, spend=100)
        before = save(w)
        reason(w)
        assert save(w) == before
