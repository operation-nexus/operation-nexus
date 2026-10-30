"""The campaign layer: clock, end conditions, timed objectives and momentum (NX-126; GAMEPLAY §9,
STATE-MACHINES §4.4 and §4.5, Q-SIM-60, Q-SIM-61, Q-SIM-62).

The campaign clock is `Campaign.running_ticks`: it counts the ticks the world was not frozen, so a
pause adds none (C-1). Each running tick, in the `objectives` slot after capture (SC-13), this adds
the tick to the clock, adds each side's held strategic nodes (AIRBASE, FOB, PORT; never BRIDGE,
SANCTUARY, HQ or a facility) to its running sum, resolves the active objective, then checks the end:

- **Victory** (coalition only: the Static has no mid-war win, Q-SIM-64): the coalition owns the
  enemy HQ (with `campaign.victory.hq_capture`, the default; a Q-CFG-16 option),
  or its hold of at least `victory_node_frac` of the strategic nodes has credited
  `victory_hold_ticks` running ticks. The HQ is checked first. The hold is public (ECONOMY EC-9,
  NX-412 part 4): `VictoryHoldStarted{node_ids, ends_at_tick, progress_ticks}` on its first tick
  (the held strategic nodes; the running tick the victory comes on; the progress carried in),
  `VictoryHoldBroken{node_id, progress_ticks}` when it breaks, naming the lowest-id hold node
  lost; none when the campaign ends during it. `Campaign.hold_nodes` keeps the held strategic
  nodes while it runs (the director's view). A break (EC-9a, NX-489, Q-TD-126) keeps the progress
  with `hold_break` decay (0 with reset): it drains along the two-stage curve (`_progress`) until
  the hold resumes from what is left, or `VictoryHoldReset` ends it (DECAYED at 0, or REPAIRED
  when the other side owns a broken-hold node at full defense hp, with `reset_on_repair`). A
  decaying hold is not in `hold_nodes`, so the director never sees it.
- **Defeat** (Q-TH-7): the coalition sanctuary's defense HP has been 0 for `defeat_hold_ticks`
  running ticks in a row (a repair above 0 resets the run; while nobody plays it is held, so a
  war is never lost while chat is asleep, Q-GP-28, and once nobody has played for the hold it
  resets, so a viewer who joins then starts a full hold, Q-TD-95; that is the idle floor,
  `campaign.idle_floor.enabled`). `CampaignEnded{DEFEAT}` with
  winner ENEMY. Checked after victory and before the time limit, so a victory beats it on the same
  tick and it beats the limit.
- **Time limit** (Q-SIM-64): at `time_limit_ticks` running ticks. Score per side =
  `average_weight` x its average share of strategic nodes over the campaign (its summed held
  counts / (nodes x running ticks)) + `final_weight` x its share at the final tick +
  `objective_points` x completed objectives, for the coalition only (objectives are the
  coalition's). Scores are exact `Fractions`, so a tie is a tie: `winner` is None. A Static win is
  `TIME_LIMIT` with winner ENEMY.

`CampaignEnded` is emitted once (C-2) and sets `Campaign.ended`: the world is then frozen
(`World.frozen`: every time-driven system stops) and `apply_commands` rejects every command with
`CAMPAIGN_NOT_RUNNING` (C-3; the SC-11 safety actions are to be exempt, SC-15). An objective still
active at the end is expired in that tick, before `CampaignEnded`. Extensions wait for their
command.

**Timed objectives**: in `timed` mode there is always exactly one active objective while the
campaign runs (O-1): the first is announced on the first running tick, and the next on the tick the
previous resolves, so the period (`objective_period_ticks`) is an objective's lifetime and an early
completion starts the next one at once. A node is picked uniformly (`campaign.objective_pick`
uniform, its only value; the `objective` stream, sorted candidates) among the frontline
candidates: ones with a road neighbour of another owner. With none, nothing is announced and no
draw is made, and it is tried again next tick. An enemy-held or neutral node is a capture:
completed when the coalition captures it (participants: that `NodeCaptured`'s).
A coalition node is a hold: completed only if the coalition owns it when the deadline arrives
(Q-SIM-61); participants are the coalition commanders whose ground units, or aircraft LANDED, are
within `capture.radius_m` of it then. Otherwise it expires at the deadline. `deadline_tick` is on
the campaign clock. Frozen with the world (O-2). No merit: progression comes later.

Momentum (Q-SIM-60) is a pure function of the world and is not stored.
Deterministic: integer state, Fractions, nodes and entities in id order, one RNG stream.
"""

import math
from fractions import Fraction
from typing import Literal, NamedTuple

from nexus.contracts.gen.common.enums import CampaignResult, ObjectiveOutcome, Side
from nexus.contracts.gen.events.campaign_ended import CampaignEnded, Score
from nexus.contracts.gen.events.event import Event
from nexus.contracts.gen.events.node_captured import NodeCaptured
from nexus.contracts.gen.events.objective_announced import ObjectiveAnnounced
from nexus.contracts.gen.events.objective_resolved import ObjectiveResolved
from nexus.contracts.gen.events.victory_hold_broken import VictoryHoldBroken
from nexus.contracts.gen.events.victory_hold_reset import VictoryHoldReset
from nexus.contracts.gen.events.victory_hold_started import VictoryHoldStarted
from nexus.core.rng import RngStream
from nexus.core.rules import CampaignRules, Rules
from nexus.core.tasking import on_objective
from nexus.core.world import Campaign, Objective, World

_COALITION: Side = "COALITION"
_ENEMY: Side = "ENEMY"
type VictoryHoldResetReason = Literal["DECAYED", "REPAIRED"]
_HALF = Fraction(1, 2)  # round half up; the rounding rule, not a tunable


class Momentum(NamedTuple):
    """Q-SIM-60: `momentum_pct` and its two inputs, whole percents (the Hud's breakdown)."""

    momentum_pct: int
    nodes_held_pct: int
    supply_pct: int


def campaign_rules(world: World) -> tuple[Rules, CampaignRules]:
    """The world's rules and campaign rules; a setup bug (ValueError) when either is missing."""
    if world.rules is None or world.rules.campaign is None:
        raise ValueError("the campaign layer needs the world's rules with campaign rules")
    return world.rules, world.rules.campaign


def _pct(share: Fraction) -> int:
    """A share as a whole percent, rounded to nearest with halves up."""
    return math.floor(share * 100 + _HALF)  # 100: a percent is a hundredth, a scale


def _held(world: World, rc: CampaignRules, side: Side) -> int:
    return sum(world.owner.get(n) == side for n in rc.strategic)


def _share(held: int, rc: CampaignRules) -> Fraction:
    return Fraction(held, len(rc.strategic)) if rc.strategic else Fraction(0)


def momentum(world: World) -> Momentum:
    """`nodes_weight` x the coalition's share of strategic nodes + `supply_weight` x its supply
    fill (its finite bases' total stock / total max stock, 0 with none), rounded half up."""
    rules, rc = campaign_rules(world)
    nodes = _share(_held(world, rc, _COALITION), rc)
    bases = [n for n in rules.supply.max_stock if world.owner.get(n) == _COALITION]
    cap = sum(rules.supply.max_stock[n] for n in bases)
    fill = Fraction(sum(world.stock.get(n, 0) for n in bases), cap) if cap else Fraction(0)
    total = rc.nodes_weight * nodes + rc.supply_weight * fill
    # 0..100 is the Momentum scale (the two weights are validated to sum to 100)
    return Momentum(min(100, max(0, math.floor(total + _HALF))), _pct(nodes), _pct(fill))


def scores(world: World, rc: CampaignRules) -> dict[Side, Fraction]:
    """Each side's exact time-limit score so far (see the module doc)."""
    c, ticks = world.campaign, len(rc.strategic) * world.campaign.running_ticks

    def side(held_ticks: int, now: Side) -> Fraction:
        average = Fraction(held_ticks, ticks) if ticks else Fraction(0)
        return rc.average_weight * average + rc.final_weight * _share(_held(world, rc, now), rc)

    return {
        _COALITION: side(c.held_ticks_coalition, _COALITION)
        + rc.objective_points * c.objectives_done,
        _ENEMY: side(c.held_ticks_enemy, _ENEMY),
    }


def end_campaign(world: World, result: CampaignResult, out: list[Event]) -> None:
    """Emit the one `CampaignEnded` and freeze the world (C-2). Winner: the coalition on VICTORY,
    the higher score on TIME_LIMIT (None on a tie), None on ABORTED. An objective still active
    expires first (F2). A world with no campaign rules (nothing was scored) ends with zero scores
    and 0 % nodes held, as `campaign()` does nothing there."""
    if world.objective is not None:
        _resolve(world, world.objective, "EXPIRED", [], out)
    rc = world.rules.campaign if world.rules else None
    zero = Fraction(0)
    score = scores(world, rc) if rc else {_COALITION: zero, _ENEMY: zero}
    winner: Side | None = None
    if result == "VICTORY":
        winner = _COALITION
    elif result == "DEFEAT":
        winner = _ENEMY
    elif result == "TIME_LIMIT" and score[_COALITION] != score[_ENEMY]:
        winner = _COALITION if score[_COALITION] > score[_ENEMY] else _ENEMY
    world.campaign.ended = True
    out.append(
        CampaignEnded.model_construct(
            kind="CampaignEnded",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            result=result,
            end_tick=world.campaign.tick + 1,
            score=Score(coalition=float(score[_COALITION]), enemy=float(score[_ENEMY])),
            winner=winner,
            nodes_held_pct=_pct(_share(_held(world, rc, _COALITION), rc)) if rc else 0,
        )
    )


def campaign(world: World, out: list[Event]) -> None:
    """The `objectives` slot: one running tick of the clock, score, objective and end checks."""
    if world.frozen:
        return
    world.campaign.running_ticks += 1
    if world.rules is None or world.rules.campaign is None:
        return
    rc = world.rules.campaign
    c = world.campaign
    coalition = _held(world, rc, _COALITION)
    c.held_ticks_coalition += coalition
    c.held_ticks_enemy += _held(world, rc, _ENEMY)
    holding = bool(rc.strategic) and _share(coalition, rc) >= rc.victory_node_frac
    _track_hold(world, rc, holding, out)
    c.defeat_ticks, c.defeat_idle_ticks = _defeat_run(world, rc)
    _resolve_objective(world, world.rules, rc, out)
    hq = rc.hq_capture and world.owner.get(rc.enemy_hq) == _COALITION
    if hq or c.hold_ticks >= rc.victory_hold_ticks:
        end_campaign(world, "VICTORY", out)
    elif c.defeat_ticks >= rc.defeat_hold_ticks:
        end_campaign(world, "DEFEAT", out)
    elif c.running_ticks >= rc.time_limit_ticks:
        end_campaign(world, "TIME_LIMIT", out)
    elif rc.objectives_on and world.objective is None:
        _announce(world, rc, out)


def _track_hold(world: World, rc: CampaignRules, holding: bool, out: list[Event]) -> None:
    """The victory hold and its nodes (ECONOMY EC-9, EC-9a): `VictoryHoldStarted` on its first
    running tick, carrying in a decaying hold's progress; `VictoryHoldBroken` naming the
    lowest-id hold node lost when it breaks (the fraction is above 0 and not hot-reloadable, so a
    break always loses one), keeping the progress with `hold_decay`; then the decay."""
    c = world.campaign
    was = c.hold_nodes
    if holding:
        if not was and c.hold_broken_nodes and rc.reset_on_repair:
            node = _repaired(world, c.hold_broken_nodes)
            if node is not None:  # a repair on the re-hold tick still resets it first
                _reset(world, "REPAIRED", node, out)
        carried = 0 if was else _progress(c, rc)  # a fresh hold's 0 or the decayed progress
        c.hold_ticks = (c.hold_ticks if was else carried) + 1
        c.hold_broken_ticks, c.hold_broken_nodes = 0, ()
        c.hold_nodes = tuple(n for n in rc.strategic if world.owner.get(n) == _COALITION)
        if not was:
            out.append(
                VictoryHoldStarted.model_construct(
                    kind="VictoryHoldStarted", tick=c.tick + 1, event_seq=world.next_event_seq(),
                    campaign_id=c.id, node_ids=list(c.hold_nodes),
                    ends_at_tick=c.running_ticks + rc.victory_hold_ticks - c.hold_ticks,
                    progress_ticks=carried,
                )
            )  # fmt: skip
    elif was:
        c.hold_nodes = ()
        if rc.hold_decay:
            c.hold_broken_nodes = was  # the break tick is t = 0
        else:
            c.hold_ticks = 0
        out.append(
            VictoryHoldBroken.model_construct(
                kind="VictoryHoldBroken", tick=c.tick + 1, event_seq=world.next_event_seq(),
                campaign_id=c.id, node_id=next(n for n in was if world.owner.get(n) != _COALITION),
                progress_ticks=c.hold_ticks,
            )
        )  # fmt: skip
    elif c.hold_broken_nodes:
        _decay(world, rc, out)


def _progress(c: Campaign, rc: CampaignRules) -> int:
    """EC-9a's P(t): the progress kept at the break (`hold_ticks`) less
    floor(slow rate x min(t, S) + fast rate x max(0, t - S)), never below 0, with t the running
    ticks since the break and S the slow stage. Closed form over exact Fractions, so no carry;
    `hold_ticks` itself with no break (t = 0)."""
    t, slow = c.hold_broken_ticks, rc.decay_slow_ticks
    loss = rc.decay_slow_rate * min(t, slow) + rc.decay_fast_rate * max(0, t - slow)
    return max(0, c.hold_ticks - math.floor(loss))


def _decay(world: World, rc: CampaignRules, out: list[Event]) -> None:
    """One running tick of a decaying hold: `VictoryHoldReset{DECAYED}` when its progress reaches
    0, else `{REPAIRED, node}` when `reset_on_repair` finds a repaired node."""
    c = world.campaign
    c.hold_broken_ticks += 1
    node = None
    if _progress(c, rc) == 0:
        reason: VictoryHoldResetReason = "DECAYED"
    elif rc.reset_on_repair and (node := _repaired(world, c.hold_broken_nodes)) is not None:
        reason = "REPAIRED"
    else:
        return
    _reset(world, reason, node, out)


def _reset(
    world: World, reason: VictoryHoldResetReason, node: str | None, out: list[Event]
) -> None:
    """End a decaying hold at progress 0 with `VictoryHoldReset{reason, node}`."""
    c = world.campaign
    c.hold_ticks = c.hold_broken_ticks = 0
    c.hold_broken_nodes = ()
    out.append(
        VictoryHoldReset.model_construct(
            kind="VictoryHoldReset", tick=c.tick + 1, event_seq=world.next_event_seq(),
            campaign_id=c.id, reason=reason, node_id=node,
        )
    )  # fmt: skip


def _repaired(world: World, nodes: tuple[str, ...]) -> str | None:
    """The lowest-id node of `nodes` (ascending) the other side owns at its full defense hp."""
    d = world.rules.defense if world.rules else None
    if d is None:
        return None
    return next(
        (
            n
            for n in nodes
            if world.owner.get(n) == _ENEMY and n in d.max_hp and world.defense_hp[n] == d.max_hp[n]
        ),
        None,
    )


def _defeat_run(world: World, rc: CampaignRules) -> tuple[int, int]:
    """The defeat run and the empty stretch within it (Q-TH-7, Q-TD-95): the running ticks the
    coalition sanctuary's defense HP has been 0, reset by a repair to `rc.defeat_reset_hp` (T) or
    more; between 0 and T a run in progress pauses (NX-499, Q-TD-131) and a run of 0 stays 0.
    While no viewer unit plays and the idle floor is on, the run is held and the empty stretch
    counts, and once that stretch reaches the hold the run resets, so a short gap (a death, a
    respawn) resumes it and a viewer who joins after a long one starts a full hold."""
    rules = world.rules
    d = rules.defense if rules else None
    hp = world.defense_hp.get(rules.sanctuary) if rules else None
    c = world.campaign
    if d is None or hp is None or hp >= rc.defeat_reset_hp or (hp and not c.defeat_ticks):
        return 0, 0
    if not d.idle_floor or world.viewer_units():
        return c.defeat_ticks + (hp == 0), 0
    idle = c.defeat_idle_ticks + 1
    return (0 if idle >= rc.defeat_hold_ticks else c.defeat_ticks), idle


def _announce(world: World, rc: CampaignRules, out: list[Event]) -> None:
    """Pick a frontline candidate uniformly and announce it (nothing, and no draw, if none)."""
    pool = [
        n
        for n, neighbours in rc.candidates.items()
        if any(world.owner[m] != world.owner[n] for m in neighbours)
    ]
    if not pool:
        return
    node = pool[world.rng.stream(RngStream.OBJECTIVE).randbelow(len(pool))]
    c = world.campaign
    c.objectives_issued += 1
    world.objective = Objective(
        c.objectives_issued, node, c.running_ticks + rc.objective_period_ticks,
        world.owner[node] == _COALITION,
    )  # fmt: skip
    out.append(
        ObjectiveAnnounced.model_construct(
            kind="ObjectiveAnnounced",
            tick=c.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=c.id,
            objective_id=world.objective.id,
            node_id=node,
            deadline_tick=world.objective.deadline,
        )
    )


def _resolve_objective(world: World, rules: Rules, rc: CampaignRules, out: list[Event]) -> None:
    o = world.objective
    if o is None:
        return
    flips = [e for e in out if isinstance(e, NodeCaptured) and e.node_id == o.node_id]
    won = [e for e in flips if e.to == _COALITION]
    if not o.hold and won:
        _resolve(world, o, "COMPLETED", sorted(won[0].participant_commander_ids), out)
    elif world.campaign.running_ticks >= o.deadline:
        if o.hold and world.owner[o.node_id] == _COALITION:
            _resolve(world, o, "COMPLETED", _holders(world, rules, o), out)
        else:
            _resolve(world, o, "EXPIRED", [], out)


def _holders(world: World, rules: Rules, o: Objective) -> list[str]:
    """Coalition commanders with a ground unit, or an aircraft LANDED, at the node."""
    if rules.capture is None:
        return []
    x, y = rules.roads.pos[o.node_id]
    r2 = rules.capture.radius_m**2
    return sorted({
        e.commander_id for e in world.entities()
        if e.side == _COALITION and e.commander_id is not None
        and (rules.domain[e.kind] == "GROUND" or e.state == "LANDED")
        and (e.pos.x - x) ** 2 + (e.pos.y - y) ** 2 <= r2
    })  # fmt: skip


def _resolve(
    world: World, o: Objective, outcome: ObjectiveOutcome, participants: list[str], out: list[Event]
) -> None:
    world.objective = None
    world.campaign.objectives_done += outcome == "COMPLETED"
    out.append(
        ObjectiveResolved.model_construct(
            kind="ObjectiveResolved",
            tick=world.campaign.tick + 1,
            event_seq=world.next_event_seq(),
            campaign_id=world.campaign.id,
            objective_id=o.id,
            outcome=outcome,
            participant_commander_ids=participants,
        )
    )
    on_objective(world, o.id, outcome == "COMPLETED", out)  # its board jobs end with it
