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
   `escalate_threshold`, 2 BRAVO from `bravo_threshold`) and the CP ceiling (ALPHA always, BRAVO
   from `bravo_enter_cp`); a level drops only below its enter value x `exit_ratio`.
4. The tier moves at most one step toward min(level, ceiling), and only once it has been in the
   current tier for `min_dwell_s` (`dwell` is running ticks, added a window at a time and held at
   `min_dwell_ticks`; a new campaign starts in PATTERN_OF_LIFE with dwell 0).
5. The window's budget (§4 step 2, Q-TD-5, Q-TD-12): min(`director.budget.<tier>`, the summed
   surplus of the side's bases above their starvation floors). A node without finite stock, i.e. the
   rear source, has no entry in `starve_floor` and so adds nothing.

All state is integer (millionths of a point, ticks), the arithmetic is floor division, nothing is
random and nothing reads a clock. NX-375 will run one Director per side with this same code.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from nexus.contracts.gen.common.enums import ThreatTier
from nexus.core.fog import SideView
from nexus.core.rules import DirectorRules, Rules
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


def level(value: int, held: int, enters: tuple[int, ...], exit_ratio: Fraction) -> int:
    """The level for `value` given the `held` one: `enters[i]` raises it to i + 1, and a level is
    kept until `value` is below its enter value x `exit_ratio` (Q-TD-1)."""
    while held > 0 and value < enters[held - 1] * exit_ratio:
        held -= 1
    while held < len(enters) and value >= enters[held]:
        held += 1
    return held


def decide(
    state: DirectorState, view: SideView, rules: Rules, stock: Mapping[str, int]
) -> TierChange | None:
    """One decision window (module docstring); changes `state`, returns the tier move if any."""
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
    state.ceiling = level(state.cp, state.ceiling, (0, dr.bravo_enter_cp), dr.exit_ratio)
    state.dwell = min(state.dwell + dr.window_ticks, dr.min_dwell_ticks)
    change = None
    at, target = TIERS.index(state.tier), min(state.prov_level, state.ceiling)
    if target != at and state.dwell >= dr.min_dwell_ticks:
        before = state.tier
        state.tier = TIERS[at + (1 if target > at else -1)]
        state.dwell = 0
        change = TierChange(before, state.tier, state.cp)
    state.budget = min(dr.budget[state.tier], surplus(view, rules, stock))
    return change
