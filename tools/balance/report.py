"""Aggregate runs into per-profile results and the target table (NX-031 part 1; TESTING-STRATEGY
§3.5a), and render the Markdown summary. A target that cannot be judged says so, never a default:
`not evaluable` (the run was too short for its window), `no data`, or `not measurable yet`."""

import statistics
from collections import Counter
from typing import Any

from profiles import Targets

PASS, FAIL, NO_DATA = "pass", "fail", "no data"
SUSPENDED = "suspended (Q-SIM-92): needs a second armed viewer unit kind"
NOT_MEASURABLE = "not measurable yet"
NOT_BUILT = (
    ("Gini of kill share by rank", "needs ranks (PROGRESSION), not built yet"),
    ("A5 adversarial bound", "part 2 (NX-321): needs the adversarial profiles"),
    ("A6 conduct", "part 2 (NX-321): needs the chat gateway and the conduct system (NX-291)"),
)
_A3_PROFILE = "overnight-0"


def _med(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _short(hours: float, needed: float) -> str | None:
    return f"not evaluable: ran {hours:g} h, needs {needed:g} h" if hours < needed else None


def _a1(runs: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    limit = next((r["time_limit_h"] for r in runs if r["time_limit_h"] is not None), None)
    hours = runs[0]["hours"]
    outcomes = Counter(
        "HARNESS_ERROR"
        if r["harness_error"]
        else "CRASHED"
        if r["crash"]
        else o["result"]
        if o["ended"]
        else "NOT_ENDED"
        for r, o in ((r, r["metrics"]["outcome"]) for r in runs)
    )
    lengths = [
        o["length_h"] for o in (r["metrics"]["outcome"] for r in runs) if o["length_h"] is not None
    ]
    good = sum(
        1
        for r in runs
        if (o := r["metrics"]["outcome"])["result"] in ("VICTORY", "DEFEAT")
        and limit is not None
        and t.a1_min_h <= o["length_h"] <= limit
    )
    frac = good / len(runs)
    if limit is None:
        status = NO_DATA  # every run hit a harness error
    else:
        status = _short(hours, limit) or (PASS if frac >= t.a1_pass_frac else FAIL)
    return {
        "status": status,
        "outcomes": dict(sorted(outcomes.items())),
        "median_length_h": _med(lengths),
        "seeds_in_window": good,
        "frac": frac,
        "detail": f"{outcomes['CRASHED']} sim crashes, {outcomes['HARNESS_ERROR']} harness errors; "
        f"{good}/{len(runs)} seeds ended by victory or defeat in "
        f"{t.a1_min_h:g}-{limit or 0:g} h (need {t.a1_pass_frac:.0%})",
    }


def _a2_group(groups: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    """A2 over groups of counted newbies (their `ttfi_s`, `no_impact_observed_s`, impact kinds)."""
    ttfi = [v for g in groups for v in g["ttfi_s"]]
    never = sum(
        s >= t.a2_max_s for g in groups for s in g["no_impact_observed_s"]
    )  # watched long enough
    unresolved = sum(s < t.a2_max_s for g in groups for s in g["no_impact_observed_s"])  # run ended
    values = sorted(ttfi + [float("inf")] * never)
    median = _med(values)
    kinds: Counter[str] = Counter()
    for g in groups:
        kinds.update(g["first_impact_kinds"])
    return {
        "status": NO_DATA if median is None else PASS if median <= t.a2_max_s else FAIL,
        "newbies": len(ttfi) + never + unresolved,
        "with_impact": len(ttfi),
        "no_impact_within_window": never,
        "unresolved_run_ended": unresolved,
        "median_s": None if median in (None, float("inf")) else median,
        "first_impact_kinds": dict(sorted(kinds.items())),
    }


def _a2(runs: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    """A2 (Q-SIM-93): only newbies who arrived at `a2_min_tier` or above are judged; the ones who
    arrived below it are counted and reported, never judged. Impact is any real contribution."""
    news = [r["metrics"]["newbie"] for r in runs]
    out = _a2_group(news, t)
    below = [v for n in news for v in n["below_tier_ttfi_s"]]
    out["below_tier"] = {
        "newbies": sum(n["joined_below_tier"] for n in news),
        "with_impact": len(below),
        "median_s": _med(below),
    }
    kinds = sorted({k for n in news for k in n["by_kind"]})
    out["by_persona_kind"] = {
        k: _a2_group([n["by_kind"][k] for n in news if k in n["by_kind"]], t) for k in kinds
    }
    med = "no median" if out["median_s"] is None else f"median {out['median_s']:.0f} s"
    out["detail"] = (
        f"{med} time to first impact over {out['newbies']} newbies who arrived at {t.a2_min_tier} "
        f"or above (needs <= {t.a2_max_s:g} s); {out['unresolved_run_ended']} unresolved when the "
        f"run ended; {out['below_tier']['newbies']} more arrived below {t.a2_min_tier} "
        "(information only)"
    )
    return out


def _a3(runs: list[dict[str, Any]], t: Targets, profile: str) -> dict[str, Any]:
    if profile != _A3_PROFILE:
        return {"status": "n/a", "detail": "A3 is judged on overnight-0 only"}
    detail = (
        f"strategic nodes lost in {t.a3_hours:g} h (max {t.a3_max_nodes_lost}) and the "
        "sanctuary's lowest defense HP (must stay above 0), every seed"
    )
    crashed = [r for r in runs if r["crash"] and r["crash"]["tick"] <= r["a3_ticks"]]
    short = [
        r for r in runs if r["harness_error"] or (not r["crash"] and r["ticks_run"] < r["a3_ticks"])
    ]
    lost = [r["metrics"]["nodes_lost_in_a3_window"] for r in runs]
    hp = [r["metrics"]["sanctuary_hp"]["min_in_a3_window"] for r in runs]
    if crashed:  # the garrison did not hold: the sim fell over inside the window
        status = FAIL
    elif short:
        status = f"not evaluable: {len(short)} of {len(runs)} runs did not cover {t.a3_hours:g} h"
    elif all(n <= t.a3_max_nodes_lost for n in lost) and all(h > 0 for h in hp):
        status = PASS
    else:
        status = FAIL
    return {
        "status": status,
        "nodes_lost_per_seed": lost,
        "sanctuary_min_hp_per_seed": hp,
        "detail": detail,
    }


def _shares(kills: Counter[str]) -> dict[str, float]:
    total = sum(kills.values())
    return {k: v / total for k, v in sorted(kills.items())} if total else {}


def _a4(runs: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    kills: Counter[str] = Counter()
    player: Counter[str] = Counter()
    for r in runs:
        kills.update(r["metrics"]["kills"]["by_kind"])
        player.update(r["metrics"]["kills"].get("player_by_kind", {}))
    total = sum(kills.values())
    share = _shares(kills)
    top = max(share.items(), key=lambda kv: kv[1], default=None)
    if t.a4_suspended:
        status = SUSPENDED  # the measured top kind and share below are for information
    elif top is None or total < t.a4_min_kills:
        status = NO_DATA
    else:
        status = PASS if top[1] <= t.a4_max_share else FAIL
    return {
        "status": status,
        "coalition_kills": total,
        "by_kind": dict(sorted(kills.items())),
        "share": share,
        "top": None if top is None else {"kind": top[0], "share": top[1]},
        "player_kills": sum(player.values()),
        "player_share": _shares(player),  # commander-owned killers only; not the target's basis
        "detail": f"no unit kind over {t.a4_max_share:.0%} of all the coalition's kills (AI "
        f"garrison included), pooled over seeds; needs {t.a4_min_kills} kills, saw {total}",
    }


def _idle(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """The idle armed viewer-unit share (Q-SIM-92), pooled over the samples of every seed, and why
    those units held no job (summed over samples)."""
    ms = [r["metrics"]["idle"] for r in runs if "idle" in r["metrics"]]
    n = sum(m["samples"] for m in ms)
    reasons: Counter[str] = Counter()
    for m in ms:
        reasons.update(m["reasons"])
    maxes = [m["share_max"] for m in ms if m["share_max"] is not None]
    return {
        "samples": n,
        "share_mean": sum(m["share_sum"] for m in ms) / n if n else None,
        "share_max": max(maxes, default=None),
        "reasons": dict(sorted(reasons.items())),
    }


def _density(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Board density (open job slots per live viewer unit; open jobs per node), pooled over the
    samples of every seed."""
    ms = [r["metrics"]["density"] for r in runs if "density" in r["metrics"]]
    out: dict[str, Any] = {}
    for key in ("slots_per_unit", "jobs_per_node"):
        n = sum(m[f"{key}_samples"] for m in ms)
        out[key] = sum(m[f"{key}_sum"] for m in ms) / n if n else None
    return out


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def aggregate(profile: str, runs: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    """One profile's results across its seeds."""
    dwell: Counter[str] = Counter()
    for r in runs:
        dwell.update(r["metrics"]["director"]["tier_dwell_s"])
    momentum = [m for r in runs for m in r["metrics"]["momentum"]["samples"]]
    return {
        "profile": profile,
        "seeds": [r["seed"] for r in runs],
        "A1": _a1(runs, t),
        "A2": _a2(runs, t),
        "A3": _a3(runs, t, profile),
        "A4": _a4(runs, t),
        "idle": _idle(runs),
        "density": _density(runs),
        "momentum": {
            "mean_pct": _mean(momentum),
            "final_median_pct": _med(
                [
                    r["metrics"]["momentum"]["samples"][-1]
                    for r in runs
                    if r["metrics"]["momentum"]["samples"]
                ]
            ),
        },
        "tier_dwell_h_mean": {k: v / len(runs) / 3600 for k, v in sorted(dwell.items())},
        "starvation_node_minutes": {
            "mean": _mean([r["metrics"]["starvation"]["node_minutes"] for r in runs]),
            "max": max(r["metrics"]["starvation"]["node_minutes"] for r in runs),
        },
        "viewers_distinct_mean": _mean([r["viewers"]["distinct"] for r in runs]),
        "viewers_peak_mean": _mean([r["viewers"]["peak_concurrent"] for r in runs]),
    }


def target_table(profiles: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """One row per (target, profile) that applies, then the targets nothing can measure yet."""
    rows = [
        {"target": key, "profile": name, "status": agg[key]["status"], "detail": agg[key]["detail"]}
        for name, agg in profiles.items()
        for key in ("A1", "A2", "A3", "A4")
        if agg[key]["status"] != "n/a"
    ]
    rows += [
        {"target": n, "profile": "all", "status": NOT_MEASURABLE, "detail": d} for n, d in NOT_BUILT
    ]
    return rows


def _fmt(value: float | None, spec: str = ".1f") -> str:
    return "-" if value is None else format(value, spec)


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(r) + " |" for r in rows),
        "",
    ]


def _profile_row(name: str, a: dict[str, Any]) -> list[str]:
    top = a["A4"]["top"]
    return [
        name,
        f"{_fmt(a['viewers_distinct_mean'], '.0f')} / {_fmt(a['viewers_peak_mean'], '.0f')}",
        str(a["A1"]["outcomes"]),
        _fmt(a["A1"]["median_length_h"]),
        _fmt(a["momentum"]["mean_pct"]),
        _fmt(a["A2"]["median_s"]),
        "-"
        if a["idle"]["share_mean"] is None
        else f"{a['idle']['share_mean']:.0%} / {a['idle']['share_max']:.0%}",
        _fmt(a["density"]["slots_per_unit"], ".2f"),
        _fmt(a["density"]["jobs_per_node"], ".2f"),
        "-" if top is None else f"{top['kind']} {top['share']:.0%}",
        _fmt(a["starvation_node_minutes"]["mean"]),
    ]


def markdown(report: dict[str, Any]) -> str:
    """The Markdown summary of a whole report (see `balance.py`)."""
    cfg, timing = report["config"], report["timing"]
    lines = [
        "# Balance run",
        "",
        f"- config hash: `{cfg['config_hash']}`",
        *(
            [
                f"- **theater: `{t['slug']}` ({t['name']}), {t['nodes']} nodes, "
                f"{t['landing_bases']} landing bases**"
            ]
            if (t := cfg.get("theater"))
            else []
        ),
        *(
            [f"- **balance overrides: {', '.join(f'`{o}`' for o in cfg['overrides'])}**"]
            if cfg.get("overrides")
            else []
        ),
        f"- profiles.yaml digest: `{cfg['profiles_digest']}` (every value in it is PROPOSED)",
        f"- seeds: {report['seeds']}; game hours per run: {report['hours']:g}",
        f"- workers: {report['workers']}; wall time {timing['elapsed_s']:.1f} s elapsed, "
        f"{timing['run_wall_s']:.1f} s summed over the runs",
        "",
        "## Targets",
        "",
    ]
    lines += _table(
        ["Target", "Profile", "Result", "Detail"],
        [[r["target"], r["profile"], r["status"], r["detail"]] for r in report["targets"]],
    )
    lines += ["## Profiles (across seeds)", ""]
    lines += _table(
        [
            "Profile",
            "Viewers (distinct / peak)",
            "Outcomes",
            "Median h",
            "Momentum %",
            "Newbie s",
            "Idle armed mean / max",
            "Slots / unit",
            "Jobs / node",
            "Top kind",
            "Starved",
        ],
        [_profile_row(n, a) for n, a in report["profiles"].items()],
    )
    lines += [
        "Viewers: mean per run, distinct arrivals / peak with a live unit at once. "
        "Starved: mean supply-starved node-minutes. Idle armed: share of commander-owned armed "
        "units with no job, order or route, sampled every `idle_sample_min`. "
        "Slots / unit: open job slots on the coalition board per live (not Disabled) "
        "commander-owned unit (mean over samples with a unit). Jobs / node: open coalition jobs "
        "per theater node (mean). "
        "A job is open while it has an unfilled slot.",
        "",
    ]
    lines += ["## A2 first impact (newbies arriving at the A2 tier or above)", ""]
    for n, a in report["profiles"].items():
        a2 = a["A2"]
        lines += [
            f"- {n}: counted {a2['newbies']} newbies ({a2['with_impact']} with impact), "
            f"below-tier (information only) {a2['below_tier']['newbies']}; "
            f"first impact kinds {a2['first_impact_kinds']}",
            *(
                f"  - {k}: {g['newbies']} newbies, median {_fmt(g['median_s'])} s, "
                f"{g['first_impact_kinds']}"
                for k, g in a2["by_persona_kind"].items()
            ),
        ]
    lines += [""]
    lines += ["## Why idle armed units hold no job (summed over samples)", ""]
    lines += [f"- {n}: {a['idle']['reasons']}" for n, a in report["profiles"].items()]
    lines += [""]
    lines += ["## Director tier dwell (mean hours per run)", ""]
    lines += [f"- {n}: {a['tier_dwell_h_mean']}" for n, a in report["profiles"].items()]
    lines += ["", "## Runs", ""]
    lines += _table(
        ["Profile", "Seed", "Ticks", "Outcome", "Wall s", "Ticks/s", "Final state hash"],
        [
            [
                r["profile"],
                str(r["seed"]),
                str(r["ticks_run"]),
                r["outcome"],
                f"{r['wall_s']:.1f}",
                _fmt(r["ticks_per_s"], ".0f"),
                "-" if r["final_state_hash"] is None else f"`{r['final_state_hash'][:16]}`",
            ]
            for r in report["runs"]
        ],
    )
    return "\n".join(lines)
