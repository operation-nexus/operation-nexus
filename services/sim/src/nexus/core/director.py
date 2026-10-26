"""The Threat Director's decisions, part 1 (THREAT-DIRECTOR §2-§4, TD-1, TD-2; NX-151, NX-155).

**Own view only (TD-2, FOW-4).** `decide` takes a side's `SideView` (its `EnemyView` when the side
is ENEMY), the side's own `DirectorState` and its own stock; it never sees the `World`. What the
Static suffers or senses reaches it as the `pending` provocation that `nexus.core.provocation` wrote
while the hits and flips happened. `tests/core/test_director.py` checks that this module names
neither `World` nor an entity accessor, and that coalition units the Static does not track change
nothing.

One decision window is `director.window_s` of game time, i.e. every `window_ticks` running ticks
(`due`; never while frozen, SC-11, so a pause or a different `sim.time_scale` changes no count). In
it, in order:

1. Provocation decays by one window's multiplier (an exact integer ratio of the half-life), then
   what was noted since the last window is added; so does every threat-memory counter, by its own
   half-life (§2).
2. Coalition power (CP, §2, Q-TD-2): the sum of `director.cp.unit_value.<kind>` over the units the
   side tracks now (never last-known tracks, Q-FOW-14; a kind not listed counts 0), moved a
   `window / ema_window` step toward it from the old smoothed value. It starts at 0.
3. Levels with hysteresis (Q-TD-1): the provocation level (0 PATTERN_OF_LIFE, 1 ALPHA from
   `escalate_threshold`, 2 BRAVO from `bravo_threshold`) and the CP ceiling (ALPHA from
   `tier.alpha_enter_cp`, 0 by default so always; PATTERN_OF_LIFE below it; BRAVO from
   `bravo_enter_cp`); a level drops only below its enter value x `exit_ratio`.
4. The tier moves at most `tier.max_step` steps (1 by default, Q-TD-1) toward min(level, ceiling),
   and only once it has been in the current tier for `min_dwell_s` (`dwell` is running ticks, added
   a window at a time and held at `min_dwell_ticks`; a new campaign starts in `tier.start`,
   PATTERN_OF_LIFE by default, with dwell 0: `nexus.runtime.campaign_config.start_campaign`).
5. The window's budget (§4 step 2, `budget`). Under `economy.legacy_rules` (Q-TD-5, Q-TD-12):
   min(`director.budget.<tier>`, the summed surplus of the side's bases above their starvation
   floors); a node without finite stock, i.e. the rear source, has no entry in `starve_floor` and
   so adds nothing. Otherwise ECONOMY EC-7 (NX-412 part 3): floor(surplus x `spend_frac.<tier>`)
   + floor(rear pool x `source_spend_frac`) - floor(`upkeep_reserve_windows` x the upkeep the
   side's units owe per window), at least the cadence floor (0 when it does not apply), at most
   surplus + rear pool.
   The rear pool is 0 for a side in unlimited mode (no pool). Cadence floor: while the side holds
   an HQ, has no operation staged and has launched no capture operation for `cadence_windows`
   windows (`last_operation`, also stamped when a staged one is dropped; Q-TD-54), the
   cheapest operation of its tier that surplus + pool can pay; `nexus.core.launch` lifts it to
   the cheapest capture operation with a target that window (Q-TD-42). The pool share is spent
   only on operations that spawn at the source (`rear_share`, `nexus.core.launch`).

All state is integer (millionths of a point, ticks), the arithmetic is floor division, nothing is
random and nothing reads a clock. NX-375 will run one Director per side with this same code.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from nexus.contracts.gen.common.enums import ThreatTier
from nexus.core.fog import SideView
from nexus.core.rules import DirectorRules, Rules, legacy_rules
from nexus.core.world import DirectorState

TIERS: tuple[ThreatTier, ...] = ("PATTERN_OF_LIFE", "ALPHA", "BRAVO")


@dataclass(frozen=True, slots=True)
class TierChange:
    """A tier move in the window just decided; `cp` is the smoothed coalition power then."""

    before: ThreatTier
    after: ThreatTier
    cp: int  # millionths of a CP point


def due(dr: DirectorRules, running_tick: int) -> bool:
    """`running_tick` is the running tick being computed (`running_ticks + 1`)."""
    return running_tick % dr.window_ticks == 0


def night_capped(state: DirectorState, dr: DirectorRules, running_tick: int) -> bool:
    """The night-progress cap is spent (Q-SIM-85): the Static flipped a node while no viewer unit
    was live less than `night_cap_ticks` ago. The caller adds the "no viewer unit" test."""
    return state.last_flip != 0 and running_tick - state.last_flip < dr.night_cap_ticks


def raw_cp(view: SideView, dr: DirectorRules) -> int:
    """Millionths of a CP point of the units `view` tracks now."""
    return sum(dr.cp_value.get(c.kind, 0) for c in view.tracks.values())


def surplus(view: SideView, rules: Rules, stock: Mapping[str, int]) -> int:
    """Stock above the starvation floor, summed over the bases `view.side` owns now."""
    return sum(
        max(0, stock.get(node, 0) - floor)
        for node, floor in rules.supply.starve_floor.items()
        if view.owners.get(node) == view.side
    )


def rear_share(dr: DirectorRules, pool: int) -> int:
    """EC-7: what the rear pool adds to a window's budget, floor(pool x `source_spend_frac`)."""
    return math.floor(pool * dr.source_spend_frac)


def cadence_due(state: DirectorState, view: SideView, rules: Rules) -> bool:
    """EC-7: the side holds an HQ, has no operation staged and has launched no capture operation
    for `cadence_windows` windows (a staged one dropped stamps `last_operation`, Q-TD-42); other
    operations do not reset it (Q-TD-54), for the capture floor and the cheapest-operation one."""
    dr = rules.director
    if dr is None or state.staged or state.windows - state.last_operation < dr.cadence_windows:
        return False
    return any(view.owners.get(n) == view.side for n, k in rules.node_kind.items() if k == "HQ")


def cadence_floor(state: DirectorState, view: SideView, rules: Rules, cap: int) -> int:
    """EC-7: the cheapest operation of the tier that `cap` pays, once `cadence_due`; else 0.
    `nexus.core.launch` lifts it to a capture operation when one has a target (Q-TD-42)."""
    dr = rules.director
    if dr is None or not cadence_due(state, view, rules):
        return 0
    costs = [o.cost for o in dr.operations if o.jobs and state.tier in o.tiers]
    return min((c for c in costs if c <= cap), default=0)


def budget(
    state: DirectorState, view: SideView, rules: Rules, stock: Mapping[str, int], pool: int,
    upkeep: int,
) -> int:  # fmt: skip
    """Step 5 (module docstring): `pool` is the side's rear pool (0 when unlimited), `upkeep`
    what its live units owe per window."""
    dr = rules.director
    if dr is None:
        raise ValueError("budget needs the Director rules")
    base = surplus(view, rules, stock)
    if legacy_rules(rules):
        return min(dr.budget[state.tier], base)
    planned = (
        math.floor(base * dr.spend_frac[state.tier]) + rear_share(dr, pool)
        - math.floor(dr.reserve_windows * upkeep)
    )  # fmt: skip
    # never above surplus + pool: the fractions are at most 1 (schema) and the floor is capped
    return max(cadence_floor(state, view, rules, base + pool), planned)


def level(value: int, held: int, enters: tuple[int, ...], exit_ratio: Fraction) -> int:
    """The level for `value` given the `held` one: `enters[i]` raises it to i + 1, and a level is
    kept until `value` is below its enter value x `exit_ratio` (Q-TD-1)."""
    while held > 0 and value < enters[held - 1] * exit_ratio:
        held -= 1
    while held < len(enters) and value >= enters[held]:
        held += 1
    return held


def decide(
    state: DirectorState, view: SideView, rules: Rules, stock: Mapping[str, int], *,
    pool: int = 0, upkeep: int = 0,
) -> TierChange | None:  # fmt: skip
    """One decision window (module docstring); changes `state`, returns the tier move if any.
    `pool` and `upkeep` feed the EC-7 budget (`budget`)."""
    dr = rules.director
    if dr is None:
        raise ValueError("decide needs the Director rules")
    state.windows += 1
    num, den = dr.decay
    state.provocation = state.provocation * num // den + state.pending
    state.pending = 0
    mn, md = dr.memory_decay
    state.convoy_attacks = state.convoy_attacks * mn // md
    state.radar_strikes = state.radar_strikes * mn // md
    for counts in (state.node_losses, state.recon_losses):
        for sector, v in sorted(counts.items()):
            if v := v * mn // md:
                counts[sector] = v
            else:
                del counts[sector]
    n, d = dr.ema
    state.cp += (raw_cp(view, dr) - state.cp) * n // d
    state.prov_level = level(
        state.provocation, state.prov_level, (dr.escalate, dr.bravo), dr.exit_ratio
    )
    state.ceiling = level(
        state.cp, state.ceiling, (dr.alpha_enter_cp, dr.bravo_enter_cp), dr.exit_ratio
    )
    state.dwell = min(state.dwell + dr.window_ticks, dr.min_dwell_ticks)
    change = None
    at, target = TIERS.index(state.tier), min(state.prov_level, state.ceiling)
    if target != at and state.dwell >= dr.min_dwell_ticks:
        before = state.tier
        step = min(dr.max_step, abs(target - at))
        state.tier = TIERS[at + (step if target > at else -step)]
        state.dwell = 0
        change = TierChange(before, state.tier, state.cp)
    state.budget = budget(state, view, rules, stock, pool, upkeep)
    return change
