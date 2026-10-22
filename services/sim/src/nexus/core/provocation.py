"""What the Static suffers and senses: the provocation ledger (THREAT-DIRECTOR §5a, TD-2, Q-TD-11,
Q-AI-9, Q-ALN-13, Q-SIM-78; NX-155).

The kernel calls these where the thing happens, because only there are the actor and the victim both
in hand: `combat` after a hit lands, `capture` at a flip, the Director slot once per window for
scouts. Each adds the action's weight to the side's `DirectorState.pending`, which the Director
folds into its decaying score at its next window (`nexus.core.director.decide`, which never sees the
world). **Only people provoke:** an action counts only when the actor is a COMMANDER-owned unit
(AI garrison and facility actions add 0; AUTO joins the exclusion with the AUTO state, Q-ALN-9). The
victim is the Static's own loss or damage, or its own tracked scout contact, so nothing unsensed
counts (Q-FOW-15). A weight of 0 (a cosmetic redemption) changes nothing, not even the sector.

`last_provocation_sector` is the sector of the most recent noted provocation (a later running tick
replaces it; within one tick the lowest sector id wins). Directors run for `DIRECTED` sides, the
ENEMY only until NX-375.

shortcut: a killer destroyed later in the same tick still counts (it is in hand when its hit
lands).
"""

from typing import Literal

from nexus.contracts.gen.common.enums import DamageState, NodeOwner, Side
from nexus.core.fog import SideView
from nexus.core.rules import DirectorRules, Rules, sector_at
from nexus.core.world import DirectorState, Entity, World

DIRECTED: tuple[Side, ...] = ("ENEMY",)
_PLAYER = "COMMANDER"
_DISABLED = "DISABLED"


def _director(world: World, side: Side) -> tuple[Rules, DirectorRules] | None:
    rules = world.rules
    if rules is None or rules.director is None or side not in DIRECTED:
        return None
    return rules, rules.director


def _note(world: World, rules: Rules, side: Side, weight: int, x: float, y: float) -> None:
    if weight <= 0:
        return
    state, now = world.director[side], world.campaign.running_ticks + 1
    state.pending += weight
    sector = sector_at(rules, x, y)
    if sector is not None and (
        state.last_provocation_tick < now or sector < (state.last_provocation_sector or sector)
    ):
        state.last_provocation_sector, state.last_provocation_tick = sector, now


def suffered_hit(world: World, shooter: Entity, target: Entity, was: DamageState) -> None:
    """A hit by `shooter` landed on `target`, whose damage state was `was` before it. A facility:
    Disabled by this hit (8) or just hit (3). Any other unit: destroyed, or knocked to Disabled (a
    wreck), counts as a kill (5), once: a hit on a wreck that was already Disabled adds nothing, so
    its destruction does not count again (Q-SIM-79); else a convoy hit (3) or a unit hit (1)."""
    found = _director(world, target.side)
    if found is None or shooter.owner_kind != _PLAYER:
        return
    rules, dr = found
    w = dr.weights
    if rules.domain[target.kind] == "STATIC":
        disabled = target.damage_state == _DISABLED and was != _DISABLED
        weight = w.facility_disabled if disabled else w.facility_damaged
    elif was == _DISABLED:
        weight = 0
    elif world.find(target.id) is None or target.damage_state == _DISABLED:
        weight = w.destroyed
    else:
        weight = w.convoy_hit if target.kind in rules.supply.carriers else w.damaged
    _note(world, rules, target.side, weight, target.pos.x, target.pos.y)


def suffered_defense_hit(world: World, shooter: Entity, node: str) -> None:
    """A hit on the defense HP of a base: counts like a facility hit when the base is the Static's
    and the shooter a commander's (Q-SIM-79)."""
    for side in DIRECTED:
        found = _director(world, side)
        if found and world.owner[node] == side and shooter.owner_kind == _PLAYER:
            x, y = found[0].roads.pos[node]
            _note(world, found[0], side, found[1].weights.facility_damaged, x, y)


def captured(world: World, node: str, before: NodeOwner, to: Side, commanders: int) -> None:
    """A base flipped from `before` to `to` with `commanders` commanders in radius: a Static base
    taken by the coalition's people."""
    for side in DIRECTED:
        found = _director(world, side)
        if found and before == side and to != side and commanders:
            x, y = found[0].roads.pos[node]
            _note(world, found[0], side, found[1].weights.captured, x, y)


def in_rear(view: SideView, rules: Rules, x: float, y: float) -> bool:
    """Q-SIM-79: the point is in `view.side`'s rear when it is strictly nearer (straight line) to a
    base the side owns than to any base the other side owns, by the live owners the view shows
    (FOW-10). Bases are the finite-stock nodes except BRIDGEs, plus both sanctuaries; a tie, or
    no base of the side, is not rear. It moves with the front as bases change hands."""
    bases = {n for n in rules.supply.max_stock if rules.node_kind.get(n) != "BRIDGE"}
    bases.update(rules.supply.rear.values())
    own = other = None
    for node in bases:
        px, py = view.nodes[node]
        d2 = (px - x) ** 2 + (py - y) ** 2
        if view.owners.get(node) == view.side:
            own = d2 if own is None else min(own, d2)
        elif view.owners.get(node) in ("COALITION", "ENEMY"):
            other = d2 if other is None else min(other, d2)
    return own is not None and (other is None or own < other)


def scan_rear(world: World, side: Side, view: SideView) -> None:
    """Once per window: a scout that `side` tracks now inside its rear, and that a commander flies,
    adds `scout_in_rear` at the track's position (not the unit's: the Static knows only the track).
    One note per window however many scouts, the lowest track id first. An AI scout adds 0. The
    rear is `nexus.core.director.in_rear` on `view` (Q-SIM-79)."""
    found = _director(world, side)
    if found is None:
        return
    rules, dr = found
    for i, track in sorted(world.contacts[side].items()):
        e = world.find(i)
        if (
            track.age is None
            and track.kind in rules.painters
            and e is not None
            and e.owner_kind == _PLAYER
            and in_rear(view, rules, track.pos.x, track.pos.y)
        ):
            _note(world, rules, side, dr.weights.scout_in_rear, track.pos.x, track.pos.y)
            return


def note_redemption(world: World, side: Side, klass: Literal["support", "cosmetic"]) -> None:
    """A channel-point redemption of class `klass` (Q-AI-9): its weight, with no sector. No
    redemption command exists yet (SUPPORT-REDEMPTIONS), so nothing calls this but its test."""
    found = _director(world, side)
    if found is not None:
        w = found[1].weights
        world.director[side].pending += (
            w.redemption_support if klass == "support" else w.redemption_cosmetic
        )


_TIER_INDEX = {"PATTERN_OF_LIFE": 0, "ALPHA": 1, "BRAVO": 2}


def validate(world: World, rules: Rules) -> None:
    """Check a restored world's Director state against the campaign rules (a snapshot carries
    none); raises ValueError naming the side. Only a directed side ever changes from its start
    state, and a state must be reachable: no more windows than the clock allows, a dwell that is
    whole windows within the minimum, a tier no higher than the windows run could have reached
    (each step needs a full dwell), a budget within the tier's, a theater sector."""
    dr = rules.director
    if dr is None:
        return
    sectors = {s for s, _ in rules.sectors}
    for side, d in world.director.items():
        windows = d.windows * dr.window_ticks
        problem = (
            "a side with no Director must keep its start state"
            if side not in DIRECTED and d != DirectorState()
            else "more windows than the running ticks allow"
            if windows > world.campaign.running_ticks
            else "dwell is not whole windows within the minimum dwell and the windows run"
            if d.dwell % dr.window_ticks or d.dwell > min(dr.min_dwell_ticks, windows)
            else "a tier the windows run could not have reached"
            if _TIER_INDEX[d.tier] * dr.min_dwell_ticks > windows
            else "a budget above the tier's"
            if d.budget > dr.budget[d.tier]
            else "a provocation sector that is not in the theater"
            if d.last_provocation_sector not in (sectors | {None})
            else None
        )
        if problem:
            raise ValueError(f"director.{side}: {problem}")
