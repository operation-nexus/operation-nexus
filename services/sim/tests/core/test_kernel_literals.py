"""NX-377, Q-DEV-21: no gameplay number lives only in code.

Design: an AST scan of every `nexus/core/**/*.py` collects each numeric literal other than 0, 1 and
-1. Skipped as trivia: 2 as the operand of `**`, `*`, `/`, `//` or `%` (squares, halves, doubles),
and any int that indexes or slices a tuple or list, or that a `len(...)` result is compared with
when it is 2 (a pair shape check). A new literal fails the test until it is either made a balance
or content key (the answer for anything that changes an outcome) or listed with the reason it
stays in code, in one of two places:

- `NAMED`: a module-level constant, by (module, name). Every literal in its value is covered, so
  a structural constant like `FORMAT_VERSION` or a scale like `CP_SCALE` is exempt by name and
  changing its value never needs an edit here.
- `ALLOWED`: any other literal, by (module, value), not by line number, so edits do not churn it.
  One entry covers every use of that value in that module, so say what the value is.

An entry that no longer matches anything fails too, so the lists stay short and true.

Reason prefixes: PERF (speed only, never changes a result), SCALE (a fixed-point scale, unit
conversion or percent), STRUCT (an enum order, wire or schema limit, algorithm constant, a
mechanism a spec defines, or a value fixed with the RNG stream).

Known limits (not a linter): a number built from other literals (`1 + 1 + 1`, `True + True`),
parsed from a string (`int("5")`), or read from a table by index is not seen. Review catches
those; this test catches the casual new constant.
"""

import ast
from pathlib import Path

import nexus.core

CORE = Path(nexus.core.__file__).parent
_OPS = (ast.Pow, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)

type Key = tuple[str, int | float]
type Name = tuple[str, str]

NAMED: dict[Name, str] = {
    ("campaign.py", "_HALF"): "STRUCT: Fraction(1, 2), the round-half-up rule",
    ("combat.py", "_CELL_M"): "PERF: targeting grid cell, changes speed never a result",
    ("combat.py", "_MAX_ASSISTS"): "STRUCT: UnitDestroyed.assist_ids maxItems",
    ("defense.py", "_MILLI"): "SCALE: thousandths of an hp",
    ("fog.py", "_CLASS_SPAN"): "PERF: sensor range class span, measured in NX-372",
    ("follow.py", "_LONG_M"): "PERF: reach beyond which a kind stays out of the track grid",
    ("follow.py", "_CELL_M"): "PERF: track grid cell",
    (
        "operations.py",
        "NOISE_STEPS",
    ): "STRUCT: noise draw resolution, fixed with the RNG stream (a change reshuffles seeds)",
    ("provocation.py", "_TIER_INDEX"): "STRUCT: the tier ladder order",
    ("rearm.py", "_MILLI"): "SCALE: thousandths of a stock unit",
    ("rearm.py", "_EPS"): "PERF: float noise epsilon in a fuel-to-milli conversion",
    ("rng.py", "_MASK64"): "STRUCT: PCG64 DXSM word width",
    ("rng.py", "_MASK128"): "STRUCT: PCG64 DXSM state width",
    ("rng.py", "_MULT"): "STRUCT: PCG64 DXSM multiplier",
    ("rng.py", "_HEX_LEN"): "STRUCT: hex width of a 128-bit state",
    ("rules.py", "CAPTURE_FULL"): "SCALE: a full capture bar in millionths of a percent",
    ("rules.py", "CP_SCALE"): "SCALE: coalition power and provocation in millionths of a point",
    ("rules.py", "_MILLI"): "SCALE: thousandths of a stock unit",
    ("rules.py", "_Q"): "SCALE: the provocation decay multiplier's fixed-point denominator",
    (
        "rules.py",
        "DECAY_RATIO_MAX",
    ): "STRUCT: a bound on a load-time bisection's cost; rejects a config",
    ("rules.py", "_AMMO_BOUND"): "STRUCT: Entity.ammo_credit must stay inside 64 bits (SC-9)",
    ("spatial.py", "_PAD_M"): "PERF: grid query padding against float rounding",
    ("step.py", "TICK_DT"): "STRUCT: 10 Hz, fixed by ADR-0002 and SC-2",
    ("tasking.py", "_MAX_PARTICIPANTS"): "STRUCT: JobDone.participants maxItems",
    ("tasking.py", "_TIE_DRAW"): "STRUCT: width of the tie-break draw, it orders equals only",
    ("world.py", "FORMAT_VERSION"): "STRUCT: the snapshot format version",
    ("world.py", "_MM"): "SCALE: metres to millimetres",
    ("world.py", "_MICRO"): "SCALE: ADR-0002 micro step for fuel",
    ("world.py", "_MILLI_UNIT"): "SCALE: thousandths of a stock unit",
    ("world.py", "_MAX_ABS"): "STRUCT: coordinate bound, keeps mm inside int64",
}

ALLOWED: dict[Key, str] = {
    ("campaign.py", 100): "SCALE: a percent; Momentum runs 0..100 (the weights sum to 100)",
    ("fog.py", 0.5): "STRUCT: a blob sits at the centre of its cell",
    ("logistics.py", 1000): "SCALE: thousandths of a stock unit",
    ("operations.py", 4): "STRUCT: a Director job key has at least four colon-separated parts",
    ("rng.py", 8): "STRUCT: PCG64 DXSM / seed byte width",
    ("rng.py", 11): "STRUCT: PCG64 DXSM, 64 - 53 bits of a float",
    ("rng.py", 16): "STRUCT: PCG64 DXSM, byte width of a stream state",
    ("rng.py", 32): "STRUCT: PCG64 DXSM, digest width",
    ("rng.py", 53): "STRUCT: PCG64 DXSM, mantissa bits of a float",
    ("rng.py", 64): "STRUCT: PCG64 DXSM, word width",
    ("rng.py", 122): "STRUCT: PCG64 DXSM, rotation shift",
    ("roads.py", 1e-06): "PERF: relative collinearity epsilon of a float geometry test",
    ("rules.py", 2): "STRUCT: Fraction(1, 2), the default ammo_loadout_share of hand-built rules",
    ("rules.py", 10): "STRUCT: hand-built Supply defaults; the shipped values come from balance",
    ("rules.py", 60): "SCALE: seconds per minute",
    ("rules.py", 1000): "SCALE: thousandths (urgency, stock)",
    ("tasking.py", 1000): "SCALE: Job.urgency is in thousandths",
    ("tasking_gen.py", 1000): "SCALE: urgency thousandths; 1.0 is the multiplier floor (Q-GP-20)",
    ("world.py", 2): "STRUCT: highest tier index (BRAVO) in a loaded Director state",
    ("world.py", 3): "STRUCT: a saved claim is [entity id, tick, active]",
    ("world.py", 32): "STRUCT: state hash width (SIM-CORE section 5)",
    ("world.py", 1000): "SCALE: thousandths; the urgency floor on load",
}


def _trivial(node: ast.Constant, parent: ast.AST | None) -> bool:
    value = node.value
    if value in (0, 1, -1):
        return True
    if isinstance(parent, ast.Subscript | ast.Slice):
        return True  # an index or slice bound into a tuple
    if value != 2:
        return False
    if isinstance(parent, ast.Compare) and isinstance(parent.left, ast.Call):
        return getattr(parent.left.func, "id", "") == "len"  # a pair shape check
    return isinstance(parent, ast.BinOp | ast.AugAssign) and isinstance(parent.op, _OPS)


def _named(tree: ast.Module) -> dict[str, ast.expr]:
    """Module-level `NAME = value` and `NAME: T = value` -> value."""
    out: dict[str, ast.expr] = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            out[n.targets[0].id] = n.value
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value:
            out[n.target.id] = n.value
    return out


def _scan() -> tuple[dict[Key, list[int]], set[Name]]:
    """Literals not covered by a NAMED constant, and the NAMED constants that exist."""
    found: dict[Key, list[int]] = {}
    names: set[Name] = set()
    for path in sorted(CORE.rglob("*.py")):
        mod = path.relative_to(CORE).as_posix()
        tree = ast.parse(path.read_text())
        covered: set[int] = set()
        for name, value in _named(tree).items():
            if (mod, name) in NAMED:
                names.add((mod, name))
                covered |= {id(x) for x in ast.walk(value)}
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
                continue
            number = node.value
            if not isinstance(number, int | float) or id(node) in covered:
                continue
            if _trivial(node, parents.get(node)):
                continue
            found.setdefault((mod, number), []).append(node.lineno)
    return found, names


def test_a_numeric_literal_in_the_kernel_is_a_key_or_allowed_with_a_reason() -> None:
    new = {k: v for k, v in _scan()[0].items() if k not in ALLOWED}
    assert not new, (
        "new numeric literals in nexus/core (module, value, lines): "
        f"{[(*k, v) for k, v in new.items()]}. If it changes an outcome (a range, rate, duration, "
        "threshold, count, multiplier, probability or coefficient) make it a balance or content "
        "key (Q-DEV-21); else name it as a module constant in NAMED or add it to ALLOWED, with the "
        "reason."
    )


def test_every_allowed_literal_and_named_constant_still_exists() -> None:
    found, names = _scan()
    stale = sorted(k for k in ALLOWED if k not in found)
    assert not stale, f"stale ALLOWED entries: {stale}"
    assert not sorted(k for k in NAMED if k not in names), "stale NAMED entries"
    assert all(len(reason) > 12 for reason in [*ALLOWED.values(), *NAMED.values()])
