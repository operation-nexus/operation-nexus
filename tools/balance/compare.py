"""Same-sha A/B compare of two harness reports (NX-511; GAMEPLAY §1b item 253).

  python tools/balance/compare.py A/report.json B/report.json

Arm A is the default run (`tasking.wingmen_max` 2, the wingmen on), arm B the same sha and
seeds with `--set tasking.wingmen_max=0` (off). Prints the item 253 verdicts `report.json` can
answer, and says plainly which part it cannot. Refuses (exit 2) reports from different shas, an
unknown or dirty sha, different profile sets, profiles.yaml digests, seeds, hours, economy or
theater, or overrides that differ in more than `tasking.wingmen_max` (B must set it to 0; A may
set it to 2). Exit 1 when a verdict fails, 3 when none was judged, else 0. Every threshold is the
spec's; PROPOSED ones are marked so in the output."""

import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PASS, FAIL, PARTIAL, NOT_MEASURED = "pass", "FAIL", "partial", "not measured"
SOLO_MIN_RATIO = 2.0  # item 253 solo: Static NodeDefensesDown/h at least doubles (PROPOSED)
LENGTH_SHIFT_MAX = 0.10  # item 253 raid/surge: median campaign length moves under 10 % (PROPOSED)
WINGMEN_KEY = "tasking.wingmen_max="
WINGMEN_ON, WINGMEN_OFF = WINGMEN_KEY + "2", WINGMEN_KEY + "0"  # shipped default 2; B turns it off
JUDGED = ("pass", "fail")  # report.py's judged target statuses (anything else is not a verdict)
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
    for key in ("economy", "theater"):
        if a["config"].get(key) != b["config"].get(key):
            raise ValueError(f"the arms differ in config.{key}")
    ov_a, ov_b = (list(x["config"]["overrides"]) for x in (a, b))
    if (
        ov_b.count(WINGMEN_OFF) != 1
        or ov_a.count(WINGMEN_OFF)
        or any(
            o.startswith(WINGMEN_KEY) and o not in (WINGMEN_ON, WINGMEN_OFF) for o in (*ov_a, *ov_b)
        )
    ):
        raise ValueError(f"arm B must set {WINGMEN_OFF} and arm A must not set it to anything else")
    rest_a = sorted(o for o in ov_a if o != WINGMEN_ON)
    if rest_a != sorted(o for o in ov_b if o != WINGMEN_OFF):
        raise ValueError(f"the arms differ in more than {WINGMEN_KEY}: {ov_a} and {ov_b}")


def _quiet5(a: dict[str, Any]) -> Verdict:
    name = "quiet-5 holds start"
    p = a["profiles"].get("quiet-5")
    if p is None:
        return Verdict(name, NOT_MEASURED, "no quiet-5 in the reports")
    a1 = p["A1"]
    if not a1["seeds"]:
        return Verdict(name, NOT_MEASURED, "A1 has no seeds")
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


def _rates(x: dict[str, Any]) -> list[float] | None:
    """Static NodeDefensesDown per hour for each solo-1 seed over the hours that seed ran
    (`ticks_run` / `tick_hz`, which the harness records per run); None when a seed lacks a part."""
    ran = {
        r["seed"]: (r["ticks_run"], r.get("tick_hz")) for r in x["runs"] if r["profile"] == "solo-1"
    }
    out = []
    for p in x["profiles"]["solo-1"]["per_seed"]:
        ticks, hz = ran.get(p["seed"], (None, None))
        if p.get("static_defenses_down") is None or not ticks or not hz:
            return None
        out.append(p["static_defenses_down"] / (ticks / hz / 3600))
    return out or None


def _solo(a: dict[str, Any], b: dict[str, Any]) -> Verdict:
    name = f"solo-1 Static NodeDefensesDown/h, median seed, >= {SOLO_MIN_RATIO:g}x (A on / B off)"
    if "solo-1" not in b["profiles"]:
        return Verdict(name, NOT_MEASURED, "no solo-1 in the reports", True)
    on, off = _rates(a), _rates(b)
    if on is None or off is None:
        return Verdict(name, NOT_MEASURED, "a seed has no defenses-down count or hours run", True)
    ra, rb = statistics.median(on), statistics.median(off)
    ok = ra > 0 and ra >= SOLO_MIN_RATIO * rb
    ratio = "inf" if rb == 0 and ra > 0 else "n/a" if rb == 0 else f"{ra / rb:.2f}x"
    return Verdict(
        name, PASS if ok else FAIL, f"A on {ra:.2f}/h, B off {rb:.2f}/h, ratio {ratio}", True
    )


def _overnight(a: dict[str, Any], b: dict[str, Any]) -> Verdict:
    """The config-free final hash (`runner.state_hash_sans_config`): the raw `state_hash` holds
    the config hash, which differs between the arms by construction."""
    name = "overnight-0 byte-identical"
    if "overnight-0" not in b["profiles"]:
        return Verdict(name, NOT_MEASURED, "no overnight-0 in the reports")
    rows = [
        {
            r["seed"]: (r.get("final_state_hash_sans_config"), r["ticks_run"])
            for r in x["runs"]
            if r["profile"] == "overnight-0"
        }
        for x in (a, b)
    ]
    if any(sorted(r) != sorted(a["seeds"]) for r in rows):
        return Verdict(
            name, NOT_MEASURED, "overnight-0 runs missing for some of the report's seeds"
        )
    if any(h is None for r in rows for h, _ in r.values()):
        return Verdict(
            name, NOT_MEASURED, "a run has no config-free state hash (crash, old report)"
        )
    diff = sorted(s for s in rows[0] if rows[0][s] != rows[1][s])
    if diff:
        return Verdict(name, FAIL, f"config-free final state hash or ticks differ in seeds {diff}")
    return Verdict(
        name,
        PASS,
        f"config-free final state hash and ticks equal in {len(rows[0])} seeds; event count and "
        "event hash are not in report.json, so they are not judged",
    )


def _crowd(a: dict[str, Any], b: dict[str, Any], profile: str) -> Verdict:
    name = f"{profile} unchanged verdicts, median length shift < {LENGTH_SHIFT_MAX:.0%}"
    if profile not in b["profiles"]:
        return Verdict(name, NOT_MEASURED, f"no {profile} in the reports", True)
    pa, pb = a["profiles"][profile], b["profiles"][profile]
    sa = {t: pa[t]["status"] for t in TARGETS}
    sb = {t: pb[t]["status"] for t in TARGETS}
    judged = [t for t in TARGETS if sa[t] in JUDGED and sb[t] in JUDGED]
    moved = [t for t in judged if sa[t] != sb[t]]
    skewed = [t for t in TARGETS if t not in judged and sa[t] != sb[t]]
    la, lb = pa["A1"]["median_length_h"], pb["A1"]["median_length_h"]
    if moved:
        return Verdict(name, FAIL, f"verdict changed: {moved}", True)
    if "A1" not in judged:
        why = f"A1 not judged in both arms ({sa['A1']}, {sb['A1']})"
        return Verdict(name, NOT_MEASURED, why, True)
    if skewed:
        why = f"statuses differ and are not both pass/fail: {skewed}"
        return Verdict(name, NOT_MEASURED, why, True)
    if not lb or la is None:
        return Verdict(name, NOT_MEASURED, f"verdicts equal; median length A {la}, B {lb}", True)
    shift = abs(la - lb) / lb
    status = PASS if shift < LENGTH_SHIFT_MAX else FAIL
    return Verdict(
        name,
        status,
        f"verdicts equal on {judged}; length A {la:.2f} h, B {lb:.2f} h ({shift:.1%})",
        True,
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
    count = Counter(v.status for v in vs)
    judged = count[PASS] + count[FAIL]
    print(
        f"{judged} judged ({count[PASS]} pass, {count[FAIL]} FAIL), "
        f"{count[PARTIAL]} partial, {count[NOT_MEASURED]} not measured"
    )
    return 1 if count[FAIL] else 3 if not judged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
