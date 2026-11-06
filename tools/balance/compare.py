"""Same-sha A/B compare of two harness reports (NX-511; GAMEPLAY §1b item 253).

  python tools/balance/compare.py A/report.json B/report.json

Arm A is the default run (`tasking.wingmen_max` 2, the wingmen on), arm B the same sha and
seeds with `--set tasking.wingmen_max=0` (off). Prints the item 253 verdicts `report.json` can
answer, and says plainly which part it cannot. Refuses (exit 2) reports from different shas, an
unknown or dirty sha, different profile sets, profiles.yaml digests, seeds or hours, or identical
overrides. Exit 1 when a verdict fails, else 0. Every threshold is the spec's; PROPOSED ones are
marked so in the output."""

import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PASS, FAIL, PARTIAL, NOT_MEASURED = "pass", "FAIL", "partial", "not measured"
SOLO_MIN_RATIO = 2.0  # item 253 solo: Static NodeDefensesDown/h at least doubles (PROPOSED)
LENGTH_SHIFT_MAX = 0.10  # item 253 raid/surge: median campaign length moves under 10 % (PROPOSED)
CROWDS = ("raid-300", "surge-500")
TARGETS = ("A1", "A2", "A3", "A4")


@dataclass(frozen=True, slots=True)
class Verdict:
    name: str
    status: str
    detail: str
    proposed: bool = False


def load(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text())
    if not isinstance(doc, dict) or "config" not in doc or "profiles" not in doc:
        raise ValueError(f"{path}: not a harness report.json")
    return doc


def refuse_unless_comparable(a: dict[str, Any], b: dict[str, Any]) -> None:
    """Raise ValueError naming the first reason the two reports are not one A/B pair."""
    sha_a, sha_b = a["config"].get("sha"), b["config"].get("sha")
    if not sha_a or not sha_b:
        raise ValueError(
            "a report has no sha (made before NX-511's compare, or outside a checkout)"
        )
    if sha_a.endswith("-dirty") or sha_b.endswith("-dirty"):
        raise ValueError(f"a report was made from a dirty tree ({sha_a}, {sha_b})")
    if sha_a != sha_b:
        raise ValueError(f"different shas: {sha_a} and {sha_b}")
    if a["config"]["profiles_digest"] != b["config"]["profiles_digest"]:
        raise ValueError("different profiles.yaml digests")
    if sorted(a["profiles"]) != sorted(b["profiles"]):
        raise ValueError(
            f"different profile sets: {sorted(a['profiles'])} and {sorted(b['profiles'])}"
        )
    if a["seeds"] != b["seeds"] or a["hours"] != b["hours"]:
        raise ValueError("different seeds or hours")
    if sorted(a["config"]["overrides"]) == sorted(b["config"]["overrides"]):
        raise ValueError("the arms have the same overrides: nothing to compare")


def _quiet5(a: dict[str, Any]) -> Verdict:
    name = "quiet-5 holds start"
    p = a["profiles"].get("quiet-5")
    if p is None:
        return Verdict(name, NOT_MEASURED, "no quiet-5 in the reports")
    a1 = p["A1"]
    bad = [s["seed"] for s in a1["seeds"] if not s["good"]]
    if not a1["low_crowd"] or bad:
        return Verdict(
            name,
            FAIL,
            f"A1 low-crowd no-collapse fails in seeds {bad or 'all'} (arm A, wingmen on)",
        )
    return Verdict(
        name,
        PARTIAL,
        "A1 no-collapse passes in every seed (arm A, on); 'median seed ends holding the start "
        "nodes' is not in report.json (no end-of-run strategic count), so it is not judged",
    )


def _rate(p: dict[str, Any], hours: float) -> float | None:
    n = [s.get("static_defenses_down") for s in p["per_seed"]]
    return None if not n or any(x is None for x in n) else statistics.median(n) / hours


def _solo(a: dict[str, Any], b: dict[str, Any]) -> Verdict:
    name = f"solo-1 Static NodeDefensesDown/h, median seed, >= {SOLO_MIN_RATIO:g}x (A on / B off)"
    if "solo-1" not in b["profiles"]:
        return Verdict(name, NOT_MEASURED, "no solo-1 in the reports", True)
    ra, rb = (_rate(r["profiles"]["solo-1"], r["hours"]) for r in (a, b))
    if ra is None or rb is None:
        return Verdict(name, NOT_MEASURED, "a seed has no static_defenses_down count", True)
    ok = ra > 0 and ra >= SOLO_MIN_RATIO * rb
    ratio = "inf" if rb == 0 and ra > 0 else "n/a" if rb == 0 else f"{ra / rb:.2f}x"
    return Verdict(
        name, PASS if ok else FAIL, f"A on {ra:.2f}/h, B off {rb:.2f}/h, ratio {ratio}", True
    )


def _overnight(a: dict[str, Any], b: dict[str, Any]) -> Verdict:
    name = "overnight-0 byte-identical"
    if "overnight-0" not in b["profiles"]:
        return Verdict(name, NOT_MEASURED, "no overnight-0 in the reports")
    rows = {
        k: {(r["seed"]): (r["final_state_hash"], r["ticks_run"]) for r in x["runs"]
            if r["profile"] == "overnight-0"}
        for k, x in (("a", a), ("b", b))
    }  # fmt: skip
    diff = sorted(s for s in rows["a"] if rows["a"][s] != rows["b"].get(s))
    if diff or any(h is None for h, _ in rows["a"].values()):
        return Verdict(name, FAIL, f"final state hash or ticks differ (or missing) in seeds {diff}")
    return Verdict(
        name,
        PASS,
        f"final state hash and ticks equal in {len(rows['a'])} seeds; event count and event hash "
        "are not in report.json, so they are not judged",
    )


def _crowd(a: dict[str, Any], b: dict[str, Any], profile: str) -> Verdict:
    name = f"{profile} unchanged verdicts, median length shift < {LENGTH_SHIFT_MAX:.0%}"
    if profile not in b["profiles"]:
        return Verdict(name, NOT_MEASURED, f"no {profile} in the reports", True)
    pa, pb = a["profiles"][profile], b["profiles"][profile]
    moved = [t for t in TARGETS if pa[t]["status"] != pb[t]["status"]]
    la, lb = pa["A1"]["median_length_h"], pb["A1"]["median_length_h"]
    if moved:
        return Verdict(name, FAIL, f"verdict changed: {moved}", True)
    if not lb or la is None:
        return Verdict(name, NOT_MEASURED, f"verdicts equal; median length A {la}, B {lb}", True)
    shift = abs(la - lb) / lb
    status = PASS if shift < LENGTH_SHIFT_MAX else FAIL
    return Verdict(
        name, status, f"verdicts equal; length A {la:.2f} h, B {lb:.2f} h ({shift:.1%})", True
    )


def wingmen_lines(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """The wingmen counter sums per profile for both arms (information, no threshold)."""
    return [
        f"  {p}: A {a['profiles'][p]['wingmen']['sum']}, B {b['profiles'][p]['wingmen']['sum']}"
        for p in sorted(b["profiles"])
    ]


def verdicts(a: dict[str, Any], b: dict[str, Any]) -> list[Verdict]:
    refuse_unless_comparable(a, b)
    return [
        _quiet5(a), _solo(a, b), _overnight(a, b), *(_crowd(a, b, p) for p in CROWDS)
    ]  # fmt: skip


def render(a: dict[str, Any], b: dict[str, Any], vs: list[Verdict]) -> str:
    lines = [
        f"NX-511 item 253 A/B at {a['config']['sha']}, seeds {a['seeds']}, {a['hours']:g} h",
        f"  A overrides {a['config']['overrides'] or 'none'}; "
        f"B overrides {b['config']['overrides']}",
    ]
    lines += [
        f"{v.status:>12}  {v.name}"
        + (" (PROPOSED threshold)" if v.proposed else "")
        + f"\n{'':14}{v.detail}"
        for v in vs
    ]
    return "\n".join([*lines, "AI wingmen counters (summed over seeds):", *wingmen_lines(a, b)])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: compare.py A/report.json B/report.json", file=sys.stderr)
        return 2
    try:
        a, b = load(Path(argv[0])), load(Path(argv[1]))
        vs = verdicts(a, b)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(render(a, b, vs))
    return 1 if any(v.status == FAIL for v in vs) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
