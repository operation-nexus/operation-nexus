"""NX-519 probe: where does a newbie's time to first impact go? (A2; no kernel change.)

Runs one (profile, seed) through `runner.run` with its `on_tick` hook and a tap on the collector's
event feed. For each counted newbie (the harness's own A2 definition: it JOINed with the Static at
`targets.a2_min_tier` or above) it books the time from the first JOIN to the first impact into
phases, by the state the newbie is in at each sample (every `--sample-s` game seconds):

  join_to_spawn   no unit yet: in the reserve queue, JOIN rejected (retried later), or sent (from
                  the events `ReserveQueueJoined`, `CommandRejected`, `UnitSpawned`; the queue is
                  read from `world.reserve_queue`)
  after_loss      had a unit, lost it (`UnitDestroyed`, `UnitDespawned`), waiting to rejoin (the
                  persona's `rejoin_delay_s`)
  gave_up         the harness viewer left for good after a loss or rejections (`rejoin_prob`,
                  `max_attempts`, read from `_Crowd._lost`): no impact can come; A2 still counts
                  the newbie, watched until the run's end
  idle            a unit with no job: `tasking.idle_diagnosis`'s reason (`no_job`, `full`, `ring`,
                  `refuel_stuck`, ...), or busy with no job (order, route, RTB, grounded)
  transit         a unit holding a job and still on a path (INFERRED from `Entity.path`)
  on_task         a unit holding a job with no path left: at the target (`tasking._arrived`) or
                  waiting (INFERRED: no event says "arrived"), `fired` once the unit has fired

The phases sum to the newbie's time to first impact (a newbie with none: the time watched). The
phase of a sample is the state at its end, so a phase is exact to `--sample-s`. The impact time and
kind are the collector's own (`Collector.impact`), so A2 here is the report's A2: `summarize`
prints it from `report._a2` over the same runs.

    cd services/sim && uv run --frozen python ../../tools/balance/probe_a2.py \
        --profile prime-50 --seeds 1,2,3 --hours 6 --workers 3 --json out.json

`--from-json` summarizes a saved run without running.
"""

import argparse
import json
import math
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any
from unittest import mock

import balance
import metrics
import personas
import profiles
import report
import runner

from nexus.core.tasking import _arrived, idle_diagnosis
from nexus.core.tasking_gen import is_idle
from nexus.core.world import World
from nexus.runtime.campaign_config import ConfigPaths, load_campaign_config

PHASES = ("join_to_spawn", "after_loss", "gave_up", "idle", "transit", "on_task")
TAPPED = frozenset({
    "UnitSpawned", "UnitDestroyed", "UnitDespawned", "CommandRejected", "ReserveQueueJoined",
    "WeaponFired", "JobClaimed",
})  # fmt: skip
TAIL_S = 900.0
HZ = 10


def phase_of(state: str) -> str:
    """The phase a state belongs to (states are `<phase>:<detail>`)."""
    return state.split(":", 1)[0]


class Tap:
    """The newbies' events and state samples of one run."""

    def __init__(self, sample_ticks: int) -> None:
        self.sample_ticks = sample_ticks
        self.col: Any = None  # the run's Collector, caught in its `feed`
        self.buf: list[Any] = []
        self.unit: dict[str, int] = {}  # newbie -> its live entity id
        self.gap: dict[str, str] = {}  # newbie with no unit -> "pre" or "rejected:<reason>"
        self.gave_up: dict[str, int] = {}  # newbie -> tick the harness viewer left for good
        self.routed: set[int] = set()  # units whose first transit route was measured
        self.fired: set[int] = set()  # entities that fired
        self.rec: dict[str, dict[str, Any]] = {}
        self.last: dict[str, int] = {}  # newbie -> tick of its last booking
        self.state: dict[str, str] = {}  # newbie -> its last sampled state
        self.closed: set[str] = set()
        self.col_world: Any = None

    def feed(self, events: list[Any]) -> None:
        self.buf += [e for e in events if e.kind in TAPPED]

    def _r(self, c: str) -> dict[str, Any]:
        return self.rec[c]

    def _counted(self, c: str) -> bool:
        col = self.col
        return c in col.newbies and c in col.join_tick and col.join_tier[c] >= col.min_tier

    def _open(self, c: str) -> None:
        """First sight of a counted newbie: its record starts at its JOIN tick."""
        col = self.col
        self.rec[c] = {
            "commander": c, "persona_kind": col.kinds[c], "join_tick": col.join_tick[c],
            "phases": Counter(), "states": Counter(), "unit_kinds": [], "lives": 0,
            "rejections": [], "queued": 0, "losses": [], "job_kinds": [], "timeline": [],
            "routes": [],
        }  # fmt: skip
        self.last[c] = col.join_tick[c]
        self.gap[c] = "pre"

    def process(self) -> None:
        buf, self.buf = self.buf, []
        for e in buf:
            if e.kind == "WeaponFired":
                self.fired.add(e.shooter_id)
            elif e.kind == "JobClaimed":
                c = self.col.commander_of.get(e.entity_id)
                if self._live(c, e.tick):
                    self._r(c)["job_kinds"].append(self._job_kind(e.job_id))
            elif e.kind in ("UnitDestroyed", "UnitDespawned"):
                self._gone(e)
            elif self._live(e.commander_id, e.tick):
                getattr(self, "_" + e.kind)(e, e.commander_id)

    def _live(self, c: str | None, tick: int = 0) -> bool:
        """A recorded newbie with no impact before `tick` (a later event is not on its way to it;
        one in the tick of the impact still is: a truck's departure is credited at its spawn)."""
        if c not in self.rec:
            return False
        hit = self.col.impact.get(c)
        return hit is None or hit[0] >= tick

    def _job_kind(self, job_id: int) -> str:
        job = self.col_world.boards["COALITION"].get(job_id)
        return job.kind if job is not None else "?"

    def _UnitSpawned(self, e: Any, c: str) -> None:
        r = self._r(c)
        self.unit[c] = e.entity_id
        self.gap.pop(c, None)
        r["unit_kinds"].append(e.unit_kind)
        r["lives"] += 1

    def _CommandRejected(self, e: Any, c: str) -> None:
        if e.command_kind == "JOIN":
            self.gap[c] = f"rejected:{e.reason}"
            self._r(c)["rejections"].append((e.tick, e.reason))

    def _ReserveQueueJoined(self, e: Any, c: str) -> None:
        self._r(c)["queued"] += 1

    def _gone(self, e: Any) -> None:
        for c, eid in list(self.unit.items()):
            if eid == e.entity_id:
                del self.unit[c]
                if self._live(c, e.tick):
                    r = self._r(c)
                    killer = self.col.entity.get(getattr(e, "killer_id", None) or 0)
                    r["losses"].append({
                        "after_s": (e.tick - r["join_tick"]) / HZ,
                        "cause": str(getattr(e, "cause", None) or getattr(e, "reason", None)),
                        "killer": killer[0] if killer else None,
                        "killer_job": self._killer_job(getattr(e, "killer_id", None)),
                        "unit": self.col.entity[e.entity_id][0],
                        "last_state": self.state.get(c, "before the first sample"),
                    })  # fmt: skip
        self.fired.discard(e.entity_id)

    def _killer_job(self, killer_id: int | None) -> str:
        """What the killing unit was doing: its job's key up to the target (`op:<op>`, `patrol`,
        ...), `no job` or `unknown` (killer not alive or not named)."""
        e = self.col_world.find(killer_id) if killer_id else None
        if e is None:
            return "unknown"
        job = self.col_world.boards[e.side].get(e.job_id) if e.job_id is not None else None
        return "no job" if job is None else ":".join(job.key.split(":")[:2])

    def sample(self, world: World, tick: int) -> None:
        """Book each open newbie's time since its last booking to the state it is in now."""
        queued = {cmd.issuer.commander_id for cmd in world.reserve_queue}
        for c in sorted(self.rec):
            if c in self.closed or c in self.col.impact:
                continue
            state = self._classify(world, c, c in queued)
            self._book(c, tick, state)
            if phase_of(state) == "transit" and self.unit[c] not in self.routed:
                self.routed.add(self.unit[c])
                self._route(world, c, state)

    def _route(self, world: World, c: str, state: str) -> None:
        """The first sampled transit of a unit: its route's length from where it stands (the road
        legs for a ground unit, the waypoints for an aircraft), with what it is bound for."""
        e, rules = world.find(self.unit[c]), world.rules
        if e is None or rules is None:
            return
        at, metres = (e.pos.x, e.pos.y), 0.0
        for p in e.path:
            to = rules.roads.pos[p] if isinstance(p, str) else (p.x, p.y)
            metres += math.dist(at, to)
            at = to
        self._r(c)["routes"].append({
            "unit": e.kind, "bound_for": state.split(":", 1)[1],
            "at_s": (world.campaign.tick - self._r(c)["join_tick"]) / HZ, "m": round(metres),
        })  # fmt: skip

    def _classify(self, world: World, c: str, queued: bool) -> str:
        rules = world.rules
        if rules is None:
            raise ValueError("the probe needs a world with rules")
        e = world.find(self.unit[c]) if c in self.unit else None
        if e is None:
            if queued:
                return "join_to_spawn:queued"
            if c in self.gave_up:
                return "gave_up:left"
            if self._r(c)["losses"] and self.gap.get(c) is None:
                return "after_loss:rejoin_wait"
            return f"join_to_spawn:{self.gap.get(c, 'pre')}"
        if e.job_id is None:
            if is_idle(rules, e, "COALITION"):
                return f"idle:{idle_diagnosis(world, e)[0]}"
            if e.order in ("GOTO", "FOLLOW") and not e.grounded and e.state != "RTB":
                # a direct order from the JOIN's target (striker, capturer, freelancer kinds)
                shot = "fired" if e.id in self.fired else "no_shot"
                return f"transit:order_{e.order}" if e.path else f"on_task:order_{e.order}:{shot}"
            why = (
                "grounded" if e.grounded else "rtb" if e.state == "RTB" else
                f"order_{e.order}" if e.order is not None else "route" if e.path else
                e.damage_state.lower()
            )  # fmt: skip
            return f"idle:busy_{why}"
        job = world.boards["COALITION"].get(e.job_id)
        if job is None:
            return "idle:busy_job_gone"
        if e.path:
            return f"transit:{job.kind}"
        shot = "fired" if e.id in self.fired else "no_shot"
        return f"on_task:{job.kind}:{'at_target' if _arrived(world, e, job) else 'waiting'}:{shot}"

    def _book(self, c: str, tick: int, state: str) -> None:
        r = self._r(c)
        dt = (tick - self.last[c]) / HZ
        self.last[c] = tick
        r["states"][state] += dt
        r["phases"][phase_of(state)] += dt
        if not r["timeline"] or r["timeline"][-1][1] != state:
            r["timeline"].append([round((tick - r["join_tick"]) / HZ, 1), state])
        self.state[c] = state

    def close(self, end_tick: int) -> None:
        """Book the last stretch of each newbie that has had its impact (to the impact tick) and, at
        the run's end, of the rest (to the end tick) in the state last seen."""
        for c in sorted(self.rec):
            if c in self.closed:
                continue
            hit = self.col.impact.get(c)
            if hit is not None or end_tick:
                stop = hit[0] if hit is not None else end_tick
                if c in self.state and stop > self.last[c]:
                    self._book(c, stop, self.state[c])
                if hit is not None:
                    self.closed.add(c)


def run_one(
    profile: str, seed: int, hours: float, sample_s: float = 5.0, sets: tuple[str, ...] = ()
) -> dict[str, Any]:
    tap = Tap(max(1, round(sample_s * HZ)))
    config = None
    if sets:  # the harness's own `--set` path
        with tempfile.TemporaryDirectory() as tmp:
            (bal := Path(tmp) / "balance.yaml").write_text(balance.override_balance(list(sets)))
            config = load_campaign_config(ConfigPaths(balance=bal))
    orig = metrics.Collector.feed

    def feed(self: Any, events: list[Any]) -> Any:
        tap.col = self
        tap.feed(events)
        return orig(self, events)

    def on_tick(tick: int, _step_s: float, world: World) -> bool:
        if tap.col is None:
            return False
        tap.col_world = world
        for c in sorted(tap.col.join_tick):  # a JOIN sent this tick, not yet seen in an event
            if c not in tap.rec and tap._counted(c):
                tap._open(c)
        tap.process()
        if tick % tap.sample_ticks == 0:
            tap.sample(world, tick)
        tap.close(0)
        return False

    orig_lost = runner._Crowd._lost

    def lost(self: Any, v: Any, tick: int, hz: int) -> None:
        orig_lost(self, v, tick, hz)
        if v.status == personas.GONE:
            tap.gave_up[v.commander_id] = tick

    with (
        mock.patch.object(metrics.Collector, "feed", feed),
        mock.patch.object(runner._Crowd, "_lost", lost),
        tempfile.TemporaryDirectory() as tmp,
    ):
        res = runner.run(profile, seed, hours, Path(tmp) / "log", config=config, on_tick=on_tick)
    tap.close(res["ticks_run"])
    newbies = []
    for c, r in sorted(tap.rec.items()):
        hit = tap.col.impact.get(c)
        end = hit[0] if hit else res["ticks_run"]
        newbies.append({
            **r,
            "phases": dict(r["phases"]), "states": dict(r["states"]),
            "ttfi_s": (hit[0] - r["join_tick"]) / HZ if hit else None,
            "impact_kind": hit[1] if hit else None,
            "gave_up_after_s": (
                (tap.gave_up[c] - r["join_tick"]) / HZ if c in tap.gave_up and not hit else None
            ),
            "watched_s": (end - r["join_tick"]) / HZ,
            "timeline": r["timeline"][:200],
        })  # fmt: skip
    return {
        "profile": profile, "seed": seed, "hours": hours, "ticks_run": res["ticks_run"],
        "metrics": {"newbie": res["metrics"]["newbie"]}, "crash": res["crash"],
        "harness_error": res["harness_error"], "newbies": newbies,
    }  # fmt: skip


def is_tail(n: dict[str, Any]) -> bool:
    """The A2 tail rule for one newbie: a first impact later than 900 s, or none after being
    watched more than 900 s (a newbie watched 900 s or less with none is unresolved: left out)."""
    if n["ttfi_s"] is not None:
        return bool(n["ttfi_s"] > TAIL_S)
    return bool(n["watched_s"] > TAIL_S)


def judged(n: dict[str, Any]) -> bool:
    return n["ttfi_s"] is not None or n["watched_s"] > TAIL_S


def _q(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(p * len(s)))]


def first_window(n: dict[str, Any], limit: float = TAIL_S) -> Counter[str]:
    """Seconds per phase in the first `limit` s after the JOIN, read from the state timeline (a
    state holds until the next entry; the timeline keeps the first 200 changes)."""
    out: Counter[str] = Counter()
    end = min(limit, n["watched_s"])
    line = n["timeline"]
    for i, (at, state) in enumerate(line):
        stop = min(end, line[i + 1][0]) if i + 1 < len(line) else end
        if stop > at:
            out[phase_of(state)] += stop - at
    return out


def phase_table(newbies: list[dict[str, Any]]) -> dict[str, Any]:
    """Per phase: median and p90 of the seconds a newbie spent in it (all counted newbies, zero
    included), and, over the tail newbies only, the share of their pooled time and how many had
    it as their largest phase, and the share of the first 900 s they spent in it."""
    tail = [n for n in newbies if judged(n) and is_tail(n)]
    out: dict[str, Any] = {}
    tail_total = sum(sum(n["phases"].values()) for n in tail)
    window: Counter[str] = Counter()
    for n in tail:
        window.update(first_window(n))
    window_total = sum(window.values())
    dominant: Counter[str] = Counter()
    for n in tail:
        if n["phases"]:
            dominant[max(PHASES, key=lambda p: (n["phases"].get(p, 0.0), p))] += 1
    for p in PHASES:
        vals = [n["phases"].get(p, 0.0) for n in newbies]
        tvals = [n["phases"].get(p, 0.0) for n in tail]
        out[p] = {
            "median_s": _q(vals, 0.5), "p90_s": _q(vals, 0.9),
            "tail_median_s": _q(tvals, 0.5), "tail_p90_s": _q(tvals, 0.9),
            "tail_time_share": sum(tvals) / tail_total if tail_total else None,
            "tail_dominant": dominant[p],
            "tail_first_900_share": window[p] / window_total if window_total else None,
        }  # fmt: skip
    return {"newbies": len(newbies), "tail": len(tail), "phases": out}


def state_shares(newbies: list[dict[str, Any]], tail_only: bool = True) -> list[tuple[str, float]]:
    """States by share of the pooled time of the tail newbies (or all of them)."""
    pool = [n for n in newbies if (judged(n) and is_tail(n)) or not tail_only]
    total: Counter[str] = Counter()
    for n in pool:
        total.update(n["states"])
    s = sum(total.values())
    return [(k, v / s) for k, v in total.most_common()] if s else []


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.0f}"


def _print_group(title: str, newbies: list[dict[str, Any]]) -> None:
    t = phase_table(newbies)
    print(f"\n{title}: {t['newbies']} newbies, {t['tail']} in the tail")
    print(
        f"{'phase':14s} {'med':>6s} {'p90':>6s} | {'tail med':>8s} {'tail p90':>8s}"
        f" {'tail share':>10s} {'1st 900 s':>9s} {'dominant':>8s}"
    )
    for p, v in t["phases"].items():
        share = "-" if v["tail_time_share"] is None else f"{v['tail_time_share']:.1%}"
        first = v["tail_first_900_share"]
        print(
            f"{p:14s} {_fmt(v['median_s']):>6s} {_fmt(v['p90_s']):>6s} | "
            f"{_fmt(v['tail_median_s']):>8s} {_fmt(v['tail_p90_s']):>8s} {share:>10s}"
            f" {'-' if first is None else format(first, '.1%'):>9s} {v['tail_dominant']:>8d}"
        )


def loss_table(newbies: list[dict[str, Any]]) -> Counter[str]:
    """Units lost before their commander's first impact, by (lost unit, killer, cause, the phase
    the newbie was in at its last sample)."""
    return Counter(
        f"{loss['unit']} by {loss['killer']} on {loss.get('killer_job', '?')} "
        f"({loss['cause']}) in {phase_of(loss['last_state'])}"
        for n in newbies
        for loss in n["losses"]
    )


def _print_losses(newbies: list[dict[str, Any]]) -> None:
    lost = [n for n in newbies if n["losses"]]
    gone = [n for n in newbies if n["gave_up_after_s"] is not None]
    firsts = sorted(n["losses"][0]["after_s"] for n in lost)
    print(
        f"\nnewbies that lost a unit before their impact: {len(lost)} of {len(newbies)} "
        f"(first loss after median {_fmt(_q(firsts, 0.5))} s); gave up for good: {len(gone)}, "
        f"of them in the tail {sum(is_tail(n) for n in gone if judged(n))}"
    )
    for k, v in loss_table(newbies).most_common(10):
        print(f"  {v:4d}  {k}")


def summarize(runs: list[dict[str, Any]], top: int = 12) -> None:
    ok = [r for r in runs if not r["crash"] and not r["harness_error"]]
    newbies = [dict(n, seed=r["seed"]) for r in ok for n in r["newbies"]]
    if not newbies:
        print("no counted newbies")
        return
    a2 = report._a2(ok, profiles.load().targets)
    print(f"A2 (report._a2 over these runs): {a2['detail']}")
    ttfi = sorted(n["ttfi_s"] for n in newbies if n["ttfi_s"] is not None)
    print(
        f"probe records: {len(newbies)} newbies, {len(ttfi)} with an impact, median "
        f"{_fmt(_q(ttfi, 0.5))} s, tail rule over my records: "
        f"{sum(is_tail(n) for n in newbies if judged(n))}/{sum(judged(n) for n in newbies)}"
    )
    _print_group("all counted newbies", newbies)
    _print_group("newbies that never gave up", [n for n in newbies if n["gave_up_after_s"] is None])
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in newbies:
        groups[f"persona kind {n['persona_kind']}"].append(n)
        groups[f"first unit {(n['unit_kinds'] or ['none'])[0]}"].append(n)
    for k in sorted(groups):
        g = groups[k]
        j = [x for x in g if judged(x)]
        share = sum(is_tail(x) for x in j) / len(j) if j else float("nan")
        med = _q(sorted(x["ttfi_s"] for x in g if x["ttfi_s"] is not None), 0.5)
        print(f"{k}: {len(g)} newbies, median {_fmt(med)} s, tail {share:.1%} of {len(j)}")
    for k in sorted(k for k in groups if k.startswith("persona kind")):
        _print_group(k, groups[k])
    print("\nstates by share of the tail's time:")
    for s, v in state_shares(newbies)[:top]:
        print(f"  {v:6.1%}  {s}")
    rej: Counter[str] = Counter(r for n in newbies for _, r in n["rejections"])
    print(
        f"\nJOIN rejections (all newbies): {dict(rej)}; newbies queued: "
        f"{sum(bool(n['queued']) for n in newbies)}; lost a unit before impact: "
        f"{sum(bool(n['losses']) for n in newbies)}"
    )
    _print_losses(newbies)
    first: Counter[str] = Counter()
    for n in newbies:
        tail = "tail" if judged(n) and is_tail(n) else "ok"
        first[f"{tail}: first job {n['job_kinds'][0] if n['job_kinds'] else 'none'}"] += 1
    print(f"first board job a newbie held: {dict(sorted(first.items()))}")
    routes: dict[str, list[float]] = defaultdict(list)
    for n in newbies:
        for r in n.get("routes", [])[:1]:  # the first unit's first route
            routes[f"{r['unit']} bound for {r['bound_for']}"].append(r["m"] / 1000)
    print("first transit route length, km (kind: n, median, p90):")
    for what, km in sorted(routes.items(), key=lambda kv: -len(kv[1]))[:10]:
        print(f"  {what}: {len(km)}, {_q(km, 0.5):.1f}, {_q(km, 0.9):.1f}")
    kinds = Counter(n["impact_kind"] or "none" for n in newbies)
    print(f"first impact kinds: {dict(kinds)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", default="prime-50")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--hours", type=float, default=6.0)
    ap.add_argument("--sample-s", type=float, default=5.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--set", action="append", default=[], help="key=value, as balance.py --set")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--from-json", type=Path, nargs="*", default=None)
    a = ap.parse_args()
    if a.from_json:
        summarize([r for p in a.from_json for r in json.loads(p.read_text())])
        return
    seeds = [int(s) for s in a.seeds.split(",")]
    with ProcessPoolExecutor(a.workers) as ex:
        runs = list(ex.map(
            run_one, [a.profile] * len(seeds), seeds, [a.hours] * len(seeds),
            [a.sample_s] * len(seeds), [tuple(a.set)] * len(seeds),
        ))  # fmt: skip
    if a.json:
        a.json.write_text(json.dumps(runs, indent=1, default=list))
    summarize(runs)


if __name__ == "__main__":
    main()
