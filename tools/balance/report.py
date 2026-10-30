"""Aggregate runs into per-profile results and the target table (NX-031 part 1; TESTING-STRATEGY
§3.5a), and render the Markdown summary. A target that cannot be judged says so, never a default:
`not evaluable` (the run was too short for its window), `no data`, or `not measurable yet`."""

import itertools
import math
import statistics
from collections import Counter
from typing import Any

import steamroll
from metrics import CAPTURE_OPS, FUNNEL_STEPS, OFFENSIVE, ROUTINE_JOBS
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
ORDER_COUNTS = ("stuck_goto", "stale_claims", "direct_orders_ended", "no_effect")


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
        and o["length_h"] <= limit
    )
    frac = good / len(runs)
    sr = _steamroll(runs, t)
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
        "steamroll": sr,
        "detail": f"{outcomes['CRASHED']} sim crashes, {outcomes['HARNESS_ERROR']} harness errors; "
        f"{good}/{len(runs)} seeds ended by victory or defeat by {limit or 0:g} h "
        f"(need {t.a1_pass_frac:.0%}); steamroll (Q-TEST-11, information only): "
        f"{sr['flagged']}/{sr['judged']} won seeds flagged",
    }


def _steamroll(runs: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    """A1's no-steamroll check (Q-TEST-11): per seed, the signals S1 to S4 of each won campaign;
    the share of judged (won) seeds flagged. A seed that was not won is not judged."""
    seeds = [
        {"seed": r["seed"], "outcome": r["metrics"]["outcome"].get("result"), **v}
        for r in runs
        if not r["harness_error"] and not r["crash"]
        for v in [steamroll.judge(r["metrics"], t)]
    ]
    judged = [s for s in seeds if s["judged"]]
    flagged = sum(bool(s["steamroll"]) for s in judged)
    return {
        "seeds": seeds,
        "judged": len(judged),
        "flagged": flagged,
        "share": flagged / len(judged) if judged else None,
    }


def _a2_group(groups: list[dict[str, Any]], t: Targets) -> dict[str, Any]:
    """A2 over groups of counted newbies (their `ttfi_s`, `no_impact_observed_s`, impact kinds).

    Median (Q-SIM-97): a newbie watched `a2_max_s` or longer with no impact counts as a miss
    (infinity); one watched less is unresolved and left out. Tail: of the newbies whose fate is
    known past `a2_tail_s` (an impact at any time, or no impact after being watched longer than
    that), the share whose first impact came later than it or never. A newbie with no impact and
    watched `a2_tail_s` or less is unresolved for the tail and left out of its denominator."""
    ttfi = [v for g in groups for v in g["ttfi_s"]]
    watched = [s for g in groups for s in g["no_impact_observed_s"]]
    never = sum(s >= t.a2_max_s for s in watched)  # watched long enough for the median
    unresolved = len(watched) - never  # run ended first
    values = sorted(ttfi + [float("inf")] * never)
    median = _med(values)
    over = sum(v > t.a2_tail_s for v in ttfi) + sum(s > t.a2_tail_s for s in watched)
    judged = len(ttfi) + sum(s > t.a2_tail_s for s in watched)
    share = over / judged if judged else None
    kinds: Counter[str] = Counter()
    for g in groups:
        kinds.update(g["first_impact_kinds"])
    if median is None:
        status = NO_DATA
    else:
        status = PASS if median <= t.a2_max_s and (share or 0) <= t.a2_tail_share else FAIL
    return {
        "status": status,
        "newbies": len(ttfi) + never + unresolved,
        "with_impact": len(ttfi),
        "no_impact_within_window": never,
        "unresolved_run_ended": unresolved,
        "median_s": None if median in (None, float("inf")) else median,
        "tail": {"limit_s": t.a2_tail_s, "over": over, "judged": judged, "share": share},
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
    tail = out["tail"]
    tail_txt = (
        "no tail data"
        if tail["share"] is None
        else f"{tail['share']:.1%} over {t.a2_tail_s:g} s ({tail['over']}/{tail['judged']})"
    )
    out["detail"] = (
        f"{med} time to first impact over {out['newbies']} newbies who arrived at {t.a2_min_tier} "
        f"or above (needs <= {t.a2_max_s:g} s); {tail_txt}, needs <= {t.a2_tail_share:.0%}; "
        f"{out['unresolved_run_ended']} unresolved when the "
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
    """The idle armed viewer-unit share (Q-SIM-92), pooled over the samples of every seed, why
    those units held no job (summed over samples), and the `ring` ones by blocking marker and job
    (NX-462; a run from before it has no `ring_by_site` and adds none)."""
    ms = [r["metrics"]["idle"] for r in runs if "idle" in r["metrics"]]
    n = sum(m["samples"] for m in ms)
    reasons: Counter[str] = Counter()
    ring: Counter[str] = Counter()
    for m in ms:
        reasons.update(m["reasons"])
        ring.update(m.get("ring_by_site", {}))
    maxes = [m["share_max"] for m in ms if m["share_max"] is not None]
    return {
        "samples": n,
        "share_mean": sum(m["share_sum"] for m in ms) / n if n else None,
        "share_max": max(maxes, default=None),
        "reasons": dict(sorted(reasons.items())),
        "ring_by_site": dict(sorted(ring.items())),
    }


def _ring_lines(ring: dict[str, int], top: int = 5) -> list[str]:
    """The `ring` idle samples by blocking marker and job (NX-462), most first, ties by key."""
    if not ring:
        return []
    ranked = sorted(ring.items(), key=lambda kv: (-kv[1], kv[0]))
    more = len(ranked) - top
    rest = f"; {more} more in report.json" if more > 0 else ""
    shown = ", ".join(f"{k}: {v}" for k, v in ranked[:top])
    return [f"  - ring by blocking site -> job: {shown}{rest}"]


def _density(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Board density (open job slots per live viewer unit; open jobs per node), pooled over the
    samples of every seed."""
    ms = [r["metrics"]["density"] for r in runs if "density" in r["metrics"]]
    out: dict[str, Any] = {}
    for key in ("slots_per_unit", "jobs_per_node"):
        n = sum(m[f"{key}_samples"] for m in ms)
        out[key] = sum(m[f"{key}_sum"] for m in ms) / n if n else None
    return out


def _orders(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Direct-order health (NX-398, `orders.py`), summed over the runs that have it: any stuck GOTO
    or stale claim fails; the freelancers' no-effect share is information only."""
    ms = [r["orders"] for r in runs if r.get("orders")]
    total = {k: sum(m[k] for m in ms) for k in ORDER_COUNTS}
    ended, bad = total["direct_orders_ended"], total["stuck_goto"] + total["stale_claims"]
    share = total["no_effect"] / ended if ended else None
    return {
        **total,
        "no_effect_share": share,
        "status": NO_DATA if not ms else FAIL if bad else PASS,
        "detail": f"stuck GOTO orders {total['stuck_goto']}, stale claims "
        f"{total['stale_claims']} over {len(ms)} runs (any is a fail); freelancer orders ended "
        f"{ended}, with no shot, delivery or capture {total['no_effect']} ({_fmt(share, '.0%')})",
    }


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _per_hour(series: list[list[int]], hours: int) -> float | None:
    """Mean per run-hour of per-hour counts (a run's list may stop before its last hour)."""
    return sum(map(sum, series)) / hours if hours else None


def _funnel(es: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """D5: per capture operation (OFFENSIVE, RETAKE), launches and how many saw each later step."""
    out = {op: {"launched": 0, **dict.fromkeys(FUNNEL_STEPS, 0)} for op in CAPTURE_OPS}
    for e in es:
        for f in e["funnel"]:
            out[f["op"]]["launched"] += 1
            for k in FUNNEL_STEPS:
                out[f["op"]][k] += f[k]
    return out


def _funnel_own(es: list[dict[str, Any]]) -> dict[str, dict[str, int]] | None:
    """NX-453: the funnel through each launch's own units, per capture operation; `units` and
    `capturers` are the units that claimed any of its jobs and its CAPTURE job, summed. None when
    any launch row lacks it (an older run): never a zero standing for no data."""
    rows = [f for e in es for f in e["funnel"]]
    if any("own" not in f for f in rows):
        return None
    keys = ("units", "capturers")
    out = {op: {"launched": 0, **dict.fromkeys((*keys, *FUNNEL_STEPS), 0)} for op in CAPTURE_OPS}
    for f in rows:
        o = out[f["op"]]
        o["launched"] += 1
        o["units"] += f["own_units"]
        o["capturers"] += f["own_capturers"]
        for k in FUNNEL_STEPS:
            o[k] += f["own"][k]
    return out


def _dispersed_split(es: list[dict[str, Any]]) -> dict[str, int] | None:
    """NX-453: `STAGING_DISPERSED` sitreps by whether a capture operation launched on the same
    tick; None when any seed lacks the split (an older run)."""
    if any("dispersed_split" not in e for e in es):
        return None
    return {k: sum(e["dispersed_split"][k] for e in es) for k in ("with_launch", "no_launch")}


def _tier_at(tiers: dict[str, Any], tick: int) -> str:
    tier = tiers["start"]
    for t, to in tiers["changes"]:
        if t <= tick:
            tier = to
    return str(tier)


def _gaps(rs: list[dict[str, Any]], es: list[dict[str, Any]]) -> dict[str, Any]:
    """D5: Offensive gaps per seed, with the lead-in (tick 0 to the first one, or the whole run
    when there is none) and the tail (the last one to the last tick run), and the gaps between
    Offensives by the Static's tier at the earlier one."""
    per_seed: list[dict[str, Any]] = []
    by_tier: dict[str, list[float]] = {}
    for r, e in zip(rs, es, strict=True):
        hz = r["tick_hz"]
        ticks = [o[0] for o in e["ops"] if o[1] == OFFENSIVE]
        end = r["ticks_run"]
        gaps = [(b - a) / hz / 60 for a, b in itertools.pairwise(ticks)]
        lead_in = (ticks[0] if ticks else end) / hz / 60
        tail = (end - ticks[-1]) / hz / 60 if ticks else None
        per_seed.append(
            {
                "seed": r["seed"],
                "offensives": len(ticks),
                "lead_in_min": lead_in,
                "gaps_min": gaps,
                "tail_min": tail,
                # NX-451: the longest stretch without an Offensive, lead-in and tail included
                "longest_dry_min": max([lead_in, *gaps, *([] if tail is None else [tail])]),
            }
        )
        for a, b in itertools.pairwise(ticks):
            by_tier.setdefault(_tier_at(e["tiers"], a), []).append((b - a) / hz / 60)
    return {
        "per_seed": per_seed,
        "by_tier": {
            t: {"n": len(g), "median": _med(g), "max": max(g)} for t, g in sorted(by_tier.items())
        },
    }


def _share(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _shortfall(es: list[dict[str, Any]], hours: int) -> dict[str, Any]:
    """Rare-shortfall metrics (NX-437; ENTERTAINMENT-upkeep Q2 R1-R4, R8, R10, R11) pooled over the
    seeds that carry them. Shares are sums over sums; no number here names a player."""
    ss = [e["shortfall"] for e in es if e.get("shortfall")]
    eps = [x for s in ss for x in s["episodes"]]
    uw = {
        side: [sum(s["unit_windows"][side][k] for s in ss) for k in ("grounded", "units")]
        for side in ("COALITION", "ENEMY")
    }
    windows = sum(s["windows"] for s in ss)
    by_home = Counter(x["home"] for x in eps)
    sitreps: Counter[str] = Counter()
    for s in ss:
        sitreps.update(s.get("sitreps", {}))
    return {
        "windows": windows,
        "r1_viewer_grounded_share": _share(*uw["COALITION"]),
        "r8_static_grounded_share": _share(*uw["ENEMY"]),
        "r2_windows_with_viewer_grounded_share": _share(
            sum(s["windows_viewer_grounded"] for s in ss), windows
        ),
        "r3_episodes": len(eps),
        "r3_episodes_per_hour": len(eps) / hours if hours else None,
        "r3_episodes_by_home": dict(sorted(by_home.items())),
        "r3_median_episode_windows": _med([x["windows"] for x in eps]),
        "r4_viewers_grounded": sum(s["viewers_grounded"] for s in ss),
        "r4_viewers": sum(s["viewers"] for s in ss),
        "r4_viewers_grounded_share": _share(
            sum(s["viewers_grounded"] for s in ss), sum(s["viewers"] for s in ss)
        ),
        "r10_pool_low_stretches": sum(s["pool_low"]["stretches"] for s in ss),
        "r10_pool_low_minutes": sum(s["pool_low"]["minutes"] for s in ss),
        "r11_episodes_after_enemy_action": sum(x["after_action"] for x in eps),
        "r11_share": _share(sum(x["after_action"] for x in eps), len(eps)),
        "sitreps": dict(sorted(sitreps.items())),  # SupplyShortfall by side and status (NX-436)
    }


def _no_capture(es: list[dict[str, Any]]) -> dict[str, int] | None:
    """NX-452: decision windows summed over the seeds that carry them, `launched` or by why no
    capture operation launched; None when no seed does (an older run)."""
    have = [e["no_capture"] for e in es if "no_capture" in e]
    if not have:
        return None
    total: Counter[str] = Counter()
    for n in have:
        total.update(n)
    return {k: total[k] for k in have[0]}


def _hq_captures(es: list[dict[str, Any]]) -> dict[str, Any] | None:
    """NX-490: HQ captures summed over the seeds that carry them, by participant count and by the
    capturing side's capture weight; None when no seed does (an older run)."""
    have = [e["hq_captures"] for e in es if "hq_captures" in e]
    if not have:
        return None
    caps = [c for h in have for c in h]
    people = Counter(c["participants"] for c in caps)
    weight = Counter(c["weight"] for c in caps)
    return {
        "total": len(caps),
        "by_participants": {str(k): people[k] for k in sorted(people)},
        "by_weight": {f"{k:g}": weight[k] for k in sorted(weight)},
    }


def _economy(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """ECONOMY §4 "Harness report" (NX-412 part 5a), pooled over the seeds with the data; per-hour
    values are means per run-hour (game hours actually run)."""
    rs = [r for r in runs if r["metrics"].get("economy")]
    es = [r["metrics"]["economy"] for r in rs]
    hours = sum(math.ceil(r["ticks_run"] / (3600 * r["tick_hz"])) for r in rs if r.get("tick_hz"))
    sides: dict[str, Any] = {}
    for side in sorted({s for e in es for s in e["sides"]}):
        snaps = [h[side] for e in es for h in e["hourly"] if side in h]
        last = [e["hourly"][-1][side]["pool"] for e in es if e["hourly"]]
        sides[side] = {
            **{
                f"{k}_per_hour": _per_hour([e["sides"][side][k] for e in es], hours)
                for k in ("income", "upkeep", "groundings")
            },
            "grounded_mean": _mean([h["grounded"] for h in snaps]),
            "grounded_max": max((h["grounded"] for h in snaps), default=None),
            "pool_last_mean": None if None in last else _mean(last),  # None: unlimited or no data
        }
    exposure: Counter[str] = Counter()
    grounded: Counter[str] = Counter()
    refused: Counter[str] = Counter()
    adapted: Counter[str] = Counter()
    for e in es:
        exposure.update(e["exposure"])
        grounded.update(e["grounded_from"])
        refused.update({k: sum(v) for k, v in e["refused"]["operations_per_hour"].items()})
        adapted.update({k: sum(v) for k, v in e["adapted"].items()})
    ops = [o for e in es for o in e["ops"]]
    catalog = [o for o in ops if o[1] not in ROUTINE_JOBS]
    by_id = Counter(o[1] for o in ops)
    gaps = [
        (b[0] - a[0]) / hz / 60
        for r, e in zip(rs, es, strict=True)
        for hz in [r["tick_hz"]]
        for a, b in itertools.pairwise([o for o in e["ops"] if o[1] == OFFENSIVE])
    ]
    offensives = [o for o in catalog if o[1] == OFFENSIVE]
    funnel = _funnel(es)
    spawn_by_op: Counter[str] = Counter()
    for e in es:
        spawn_by_op.update(e["spawn_by_op"]["ops"])
    windows = sum(sum(e["budget"]["windows"]) for e in es)
    holds = [h for e in es for h in e["holds"]]
    hold_pauses: Counter[str] = Counter()
    for e in es:
        hold_pauses.update(e["hold_pauses"])
    return {
        "sides": sides,
        "shortfall": _shortfall(es, hours),
        "grounded_share_by_state": {
            k: {"grounded": grounded[k], "seen": n, "share": grounded[k] / n}
            for k, n in sorted(exposure.items())
        },
        "refused_operations": dict(sorted(refused.items())),
        "adaptations": dict(sorted(adapted.items())),  # STAGING counts forward staging (NX-416)
        "budget_per_window": sum(sum(e["budget"]["sum"]) for e in es) / windows
        if windows
        else None,
        "spent": {k: sum(sum(e["budget"]["spent"][k]) for e in es) for k in ("base", "source")},
        "ops_per_hour": len(catalog) / hours if hours else None,
        "ops_by_id": dict(sorted(by_id.items())),
        "offensives": len(offensives),
        "offensives_on_coalition": sum(o[3] for o in offensives),
        "offensive_gap_min": {"median": _med(gaps), "max": max(gaps, default=None)},
        "adaptations_per_hour": {
            k: v / hours if hours else None for k, v in sorted(adapted.items())
        },
        "funnel": funnel,
        "funnel_own": _funnel_own(es),
        "staging": {
            "sitreps": adapted["STAGING"],
            "capture_launches": sum(f["launched"] for f in funnel.values()),
            # NX-431 (Q-TD-47): each massing closes once, by a launch from its staging base or
            # a disperse; `open` is the massings no payoff closed before the run ended
            "launched": adapted["STAGING_LAUNCHED"],
            "dispersed": adapted["STAGING_DISPERSED"],
            "open": adapted["STAGING"] - adapted["STAGING_LAUNCHED"] - adapted["STAGING_DISPERSED"],
            "strike_downed": adapted["STRIKE_DOWNED"],  # Q-TD-56
            # NX-453: the sitreps cannot name a cause; a launch on the same tick is the one clue
            "dispersed_split": _dispersed_split(es),
        },
        "gaps": _gaps(rs, es),
        "no_capture": _no_capture(es),
        "hq_captures": _hq_captures(es),
        "spawn_by_op": {
            "ops": dict(sorted(spawn_by_op.items())),
            "shared": sum(e["spawn_by_op"]["shared"] for e in es),
            "unattributed": sum(e["spawn_by_op"]["unattributed"] for e in es),
        },
        "pressure_per_hold": [h["pressure"] for h in holds],
        "holds": len(holds),
        "holds_broken": sum(h["broken"] for h in holds),
        "holds_paused": sum(e["holds_paused"] for e in es),  # EC-9b (NX-466)
        "hold_pauses": dict(sorted(hold_pauses.items())),
        "hold_paused_min": sum(e["hold_paused_min"] for e in es),
        "paused_min_per_hold": [h["paused_min"] for h in holds],
        "ops_per_hold": [h["ops"] for h in holds],
        "army_vs_viewers": [
            [e["army_peak"], r["viewers"]["peak_concurrent"]] for r, e in zip(rs, es, strict=True)
        ],
    }


def _hauling(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """NX-501: per side, `resupply:<node>` jobs posted and truck unloading stops per run-hour,
    pooled over the seeds (total count over total run-hours)."""
    hours = sum(r["metrics"]["hauling"]["run_hours"] for r in runs)

    def rate(key: str, side: str) -> float | None:
        return sum(r["metrics"]["hauling"][key][side] for r in runs) / hours if hours else None

    return {
        side: {
            "resupply_jobs_per_h": rate("resupply_jobs", side),
            "deliveries_per_h": rate("deliveries", side),
        }
        for side in ("COALITION", "ENEMY")
    }


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
        "orders": _orders(runs),
        "economy": _economy(runs),
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
        "starvation_fraction_floor_node_minutes": {  # NX-495: against the fraction floor
            "mean": _mean(
                [r["metrics"]["starvation"]["fraction_floor_node_minutes"] for r in runs]
            ),
            "max": max(r["metrics"]["starvation"]["fraction_floor_node_minutes"] for r in runs),
        },
        "hauling": _hauling(runs),
        "viewers_distinct_mean": _mean([r["viewers"]["distinct"] for r in runs]),
        "viewers_peak_mean": _mean([r["viewers"]["peak_concurrent"] for r in runs]),
    }


def target_table(profiles: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """One row per (target, profile) that applies, then the targets nothing can measure yet."""
    rows = [
        {"target": key, "profile": name, "status": agg[key]["status"], "detail": agg[key]["detail"]}
        for name, agg in profiles.items()
        for key in ("A1", "A2", "A3", "A4", "orders")
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
        _fmt(a["starvation_fraction_floor_node_minutes"]["mean"]),
    ]


_STEAMROLL_HEADER = [
    "Profile",
    "Seed",
    "S1 /4 h",
    "S2 pressure, broken",
    "S3 drop, changes",
    "S4 units, stock",
    "Fired",
    "Steamroll",
]


def _sig(s: dict[str, Any], text: str) -> str:
    return "n/m" if s["value"] is None else text + ("*" if s["fired"] else "")


def _steamroll_row(profile: str, s: dict[str, Any]) -> list[str]:
    head = [profile, str(s["seed"])]
    if not s["judged"]:
        return [*head, "-", "-", "-", "-", "-", f"not judged ({s['outcome'] or 'not ended'})"]
    g = s["signals"]
    v1, v2, v3, v4 = (g[k]["value"] for k in ("S1", "S2", "S3", "S4"))
    return [
        *head,
        _sig(g["S1"], _fmt(v1, ".2f")),
        _sig(g["S2"], f"{v2['pressure']}, {v2['broken']}" if v2 else ""),
        _sig(g["S3"], f"{v3['max_drop']}, {v3['lead_changes']}" if v3 else ""),
        _sig(
            g["S4"], f"{v4['units_of_peak']:.0%}, {_fmt(v4['stock_of_start'], '.0%')}" if v4 else ""
        ),
        str(s["fired"]),
        "YES" if s["steamroll"] else "no",
    ]


def _economy_mode(mode: dict[str, Any] | None) -> list[str]:
    """EC-15: an unlimited run is labelled in the header, apart from balance runs."""
    if not mode:
        return []
    unlimited = [s for s, on in sorted(mode["unlimited"].items()) if on]
    return [
        f"- **economy: unlimited {', '.join(unlimited) or 'none'}**"
        + (" (ECONOMY EC-15: not a normal balance result)" if unlimited else "")
    ]


def _d5_lines(name: str, e: dict[str, Any]) -> list[str]:
    """The D5 additions (review ENTERTAINMENT-runs-F-G-H §8) of one profile, sub-bullets."""
    funnel = {
        op: " > ".join(f"{k} {f[k]}" for k in ("launched", *FUNNEL_STEPS))
        for op, f in e["funnel"].items()
    }
    own = e.get("funnel_own")  # an older report.json has none
    funnel_own = (
        "-"
        if own is None
        else {
            op: " > ".join(f"{k} {f[k]}" for k in ("launched", "units", "capturers", *FUNNEL_STEPS))
            for op, f in own.items()
        }
    )
    split = e["staging"].get("dispersed_split")
    cause = (
        "-"
        if split is None
        else f"{split['with_launch']} with a capture launch the same tick, "
        f"{split['no_launch']} without"
    )
    seeds = [
        f"s{g['seed']}: lead-in {_fmt(g['lead_in_min'])}, "
        f"gaps [{', '.join(_fmt(x) for x in g['gaps_min'])}], tail {_fmt(g['tail_min'])}"
        for g in e["gaps"]["per_seed"]
    ]
    tiers = {
        t: f"n {v['n']}, median {_fmt(v['median'])}, max {_fmt(v['max'])}"
        for t, v in e["gaps"]["by_tier"].items()
    }
    dry = {g["seed"]: g.get("longest_dry_min") for g in e["gaps"]["per_seed"]}  # old report: none
    dry_vals = [v for v in dry.values() if v is not None]
    sp = e["spawn_by_op"]
    nc = e.get("no_capture")  # an older report.json has none
    why = "-" if nc is None else ", ".join(f"{k} {v}" for k, v in nc.items())
    per_h = {k: _fmt(v, ".2f") for k, v in e["adaptations_per_hour"].items()}
    hq = e.get("hq_captures")  # an older report.json has none
    hq_text = (
        "-"
        if hq is None
        else f"{hq['total']}; by participant count {hq['by_participants'] or 'none'}; by capture "
        f"weight {hq['by_weight'] or 'none'}"
    )
    return [
        f"  - {name} capture funnel (launch, then the target saw): {funnel}",
        f"  - {name} capture funnel through the launch's own units (claimed its jobs; the capture "
        f"steps need one that claimed its CAPTURE job, no event names the capturer): "
        f"{funnel_own}",
        f"  - {name} STAGING sitreps {e['staging']['sitreps']} for "
        f"{e['staging']['capture_launches']} capture launches; closed by a launch "
        f"{e['staging']['launched']}, dispersed {e['staging']['dispersed']}, open at the end "
        f"{e['staging']['open']}; strike packages downed {e['staging']['strike_downed']}; "
        f"dispersed, by whether a capture launched the same tick (not the cause: a "
        f"fallback launch or an unrelated one; drop, timeout and re-stage are not told "
        f"apart): {cause}",
        f"  - {name} Offensive minutes per seed: {'; '.join(seeds) or 'none'}; gaps by tier at "
        f"the earlier one: {tiers or 'none'}",
        f"  - {name} longest stretch without an Offensive (min, lead-in and tail included) per "
        f"seed: {', '.join(f's{k} {_fmt(v)}' for k, v in dry.items()) or 'none'}; max "
        f"{_fmt(max(dry_vals, default=None))}, median {_fmt(_med(dry_vals))}",
        f"  - {name} decision windows by why no capture operation launched (first reason): {why}",
        f"  - {name} HQ captures (either side): {hq_text}",
        f"  - {name} pressure events per victory hold {e['pressure_per_hold']}",
        f"  - {name} spawn debits by operation {sp['ops'] or 'none'}, shared {sp['shared']}, "
        f"unattributed {sp['unattributed']}",
        f"  - {name} sitreps per run-hour {per_h or 'none'}",
    ]


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def _shortfall_lines(name: str, f: dict[str, Any]) -> list[str]:
    """The rare-shortfall metrics of one profile (ENTERTAINMENT-upkeep Q2), sub-bullets."""
    return [
        f"  - {name} shortfall (rare is the goal): R1 viewer unit-time grounded "
        f"{_pct(f['r1_viewer_grounded_share'])}; R8 Static AI "
        f"{_pct(f['r8_static_grounded_share'])} (info); R2 windows with a viewer grounded "
        f"{_pct(f['r2_windows_with_viewer_grounded_share'])} of {f['windows']}; R4 viewers ever "
        f"grounded {_pct(f['r4_viewers_grounded_share'])} ({f['r4_viewers_grounded']} of "
        f"{f['r4_viewers']})",
        f"  - {name} shortfall episodes: R3 {f['r3_episodes']} "
        f"({_fmt(f['r3_episodes_per_hour'], '.2f')} per run-hour, median "
        f"{_fmt(f['r3_median_episode_windows'])} windows, by home "
        f"{f['r3_episodes_by_home'] or 'none'}); R11 after enemy action within 30 min "
        f"{_pct(f['r11_share'])} ({f['r11_episodes_after_enemy_action']} of {f['r3_episodes']}); "
        f"R10 coalition pool under 10% of cap for over 30 min: {f['r10_pool_low_stretches']} "
        f"stretches, {_fmt(f['r10_pool_low_minutes'])} min; sitreps (NX-436) "
        f"{', '.join(f'{k} {n}' for k, n in sorted(f.get('sitreps', {}).items())) or 'none'}",
    ]


def _economy_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Economy (ECONOMY §4, NX-412; per run-hour means, pooled over seeds)", ""]
    rows = [
        [
            n,
            side,
            _fmt(v["income_per_hour"]),
            _fmt(v["upkeep_per_hour"]),
            _fmt(v["groundings_per_hour"]),
            f"{_fmt(v['grounded_mean'])} / {_fmt(v['grounded_max'], 'd')}",
            _fmt(v["pool_last_mean"], ".0f"),
        ]
        for n, a in report["profiles"].items()
        for side, v in a["economy"]["sides"].items()
    ]
    lines += _table(
        ["Profile", "Side", "Income / h", "Upkeep / h", "Groundings / h", "Grounded mean / max",
         "Last pool"],
        rows,
    )  # fmt: skip
    lines += [
        "Grounded: live grounded units at the end of each game hour. Last pool: the source pool at "
        "the last hour end, `-` for unlimited (no pool).",
        "",
    ]
    for n, a in report["profiles"].items():
        e = a["economy"]
        share = {
            k: f"{v['share']:.1%} of {v['seen']}" for k, v in e["grounded_share_by_state"].items()
        }
        gap = e["offensive_gap_min"]
        lines += [
            f"- {n}: Static operations / h {_fmt(e['ops_per_hour'], '.2f')} {e['ops_by_id']}; "
            f"Offensives {e['offensives']} ({e['offensives_on_coalition']} on coalition-held "
            f"nodes), gap median {_fmt(gap['median'])} min, max {_fmt(gap['max'])} min; budget / "
            f"window {_fmt(e['budget_per_window'])}, spawn debits base {e['spent']['base']}, "
            f"source {e['spent']['source']}; live-cap refusals "
            f"{e['refused_operations'] or 'none'}; Static sitreps {e['adaptations'] or 'none'}; "
            f"victory holds {e['holds']} (broken {e['holds_broken']}, paused "
            f"{e['holds_paused']} by {e['hold_pauses'] or 'none'}, paused min "
            f"{_fmt(e['hold_paused_min'])}, per hold "
            f"{[round(m, 1) for m in e['paused_min_per_hold']]}), "
            f"Static operations per hold {e['ops_per_hold']}; peak coalition armed units vs peak "
            f"viewers per seed "
            f"{e['army_vs_viewers']}; grounded by previous state {share or 'none'}",
        ]
        lines += _d5_lines(n, e)
        lines += _shortfall_lines(n, e["shortfall"])
    lines += [""]
    travel = report.get("travel") or []
    if travel:
        lines += ["## Static travel time to the victory nodes (rear source, road, top speed)", ""]
        lines += _table(
            ["Node", "Kind", "Road km", "Game min", "Hold min", "Within hold"],
            [
                [t["node"], t["kind"], _fmt(t["road_km"]), _fmt(t["minutes"]), _fmt(t["hold_min"]),
                 "-" if t["within_hold"] is None else "yes" if t["within_hold"] else "NO"]
                for t in travel
            ],
        )  # fmt: skip
        lines += [
            "Shortest road path from the Static's rear source with every bridge up, the capture "
            "kind's Healthy top speed; staging, spawning and combat are left out, so a real "
            "arrival is later (econ checkpoint §4.1).",
            "",
        ]
    return lines


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
        *_economy_mode(cfg.get("economy")),
        f"- profiles.yaml digest: `{cfg['profiles_digest']}` (every value in it is PROPOSED)",
        f"- seeds: {report['seeds']}; game hours per run: {report['hours']:g}",
        f"- workers: {report['workers']}; wall time {timing['elapsed_s']:.1f} s elapsed, "
        f"{timing['run_wall_s']:.1f} s summed over the runs",
        f"- slot wait: {timing.get('slot_wait_s', 0.0):.1f} s summed over the runs",
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
            "Starved (fraction floor)",
        ],
        [_profile_row(n, a) for n, a in report["profiles"].items()],
    )
    lines += [
        "Viewers: mean per run, distinct arrivals / peak with a live unit at once. "
        "Starved: mean supply-starved node-minutes against the live floor; "
        "Starved (fraction floor): the same against ceil(`starve_threshold` x maximum) "
        "whatever `starve_floor_mode` is "
        "(NX-495). Idle armed: share of commander-owned armed "
        "units with no job, order or route, sampled every `idle_sample_min`. "
        "Slots / unit: open job slots on the coalition board per live (not Disabled) "
        "commander-owned unit (mean over samples with a unit). Jobs / node: open coalition jobs "
        "per theater node (mean). "
        "A job is open while it has an unfilled slot.",
        "",
    ]
    lines += ["## Hauling (per run-hour, pooled over the seeds)", ""]
    lines += _table(
        ["Profile", "Coalition jobs", "Coalition deliveries", "Static jobs", "Static deliveries"],
        [
            [
                n,
                *(
                    _fmt(a["hauling"][side][k], ".2f")
                    for side in ("COALITION", "ENEMY")
                    for k in ("resupply_jobs_per_h", "deliveries_per_h")
                ),
            ]
            for n, a in report["profiles"].items()
        ],
    )
    lines += [
        "Jobs: new `resupply:<node>` postings (`JobCreated`, not the sanctuary's own repair job); "
        "a job re-posted after it ended counts again, so this is posting churn, not distinct "
        "needs. "
        "Deliveries: truck unloading stops at a node (`SupplyDelivered`, by the truck's side). "
        "Stocking jobs are not told apart from starving ones: neither event carries it (NX-501).",
        "",
    ]
    lines += ["## Steamroll signals (Q-TEST-11, thresholds PROPOSED; won seeds only)", ""]
    lines += _table(
        _STEAMROLL_HEADER,
        [
            _steamroll_row(n, s)
            for n, a in report["profiles"].items()
            for s in a["A1"]["steamroll"]["seeds"]
        ],
    )
    lines += [
        "A signal is shown as value, then `*` when it fired; `n/m` is not measurable (the note "
        "is in report.json). S1: Static pressure on held ground per 4 campaign hours. S2: "
        "pressure during the last victory hold, holds broken. S3: largest momentum drop after the "
        "coalition first led, lead changes. S4: late-third Static armed units / its peak, stock / "
        "its start. Steamroll = S1 and S2, or at least `steamroll_min_signals` of S1 to S4. "
        "Share of won seeds flagged: "
        + "; ".join(
            f"{n} {_fmt(a['A1']['steamroll']['share'], '.0%')} "
            f"({a['A1']['steamroll']['flagged']}/{a['A1']['steamroll']['judged']})"
            for n, a in report["profiles"].items()
        ),
        "",
    ]
    lines += _economy_lines(report)
    lines += ["## A2 first impact (newbies arriving at the A2 tier or above)", ""]
    for n, a in report["profiles"].items():
        a2 = a["A2"]
        lines += [
            f"- {n}: counted {a2['newbies']} newbies ({a2['with_impact']} with impact), "
            f"tail over {a2['tail']['limit_s']:g} s: {_fmt(a2['tail']['share'], '.1%')}, "
            f"below-tier (information only) {a2['below_tier']['newbies']}; "
            f"first impact kinds {a2['first_impact_kinds']}",
            *(
                f"  - {k}: {g['newbies']} newbies, median {_fmt(g['median_s'])} s, "
                f"tail {_fmt(g['tail']['share'], '.1%')}, {g['first_impact_kinds']}"
                for k, g in a2["by_persona_kind"].items()
            ),
        ]
    lines += [""]
    lines += ["## Why idle armed units hold no job (summed over samples)", ""]
    for n, a in report["profiles"].items():
        lines += [f"- {n}: {a['idle']['reasons']}", *_ring_lines(a["idle"]["ring_by_site"])]
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
