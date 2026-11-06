"""NX-514 probe: why does a planned Static strike never fire? (Q-TD-143; no kernel change.)

Runs one (profile, seed) through `runner.run` with its `on_tick` hook and a tap on the collector's
event feed, and follows every Static operation launch that carries a STRIKE job (OFFENSIVE, RETAKE,
PROBE, STRIKE_BRIDGE): its jobs (`op:<op>:<target>:<index>` keys), their claims, releases and ends,
the shots its units fired at the target, the hits they took, and how each unit was lost. A launch
is "fired" the way the harness funnel counts it (`Collector._fired`): a Static unit fired at the
target node while the launch was the newest on it. Each launch is classified from those records
only, by whether its STRIKE claimants were all, some or none of them hit by a SAM and how the job
ended; a cause the records do not show is not named (the reason is then just how the job ended).

Limits: "fired" counts only Static shots that carry a `target_node_id`; `unit_job` keeps the last
STRIKE/STAGE/CAPTURE job a unit claimed, so a hit or loss after it moved on is booked on that job;
a job that is off the board by the end of its creation tick is not seen (no record, so such a
launch can show no STRIKE job); the sampled unit states are 10 s apart.

    cd services/sim && uv run --frozen python ../../tools/balance/probe_strikes.py \
        --profile overnight-0 --seeds 1,2,3 --hours 72 --workers 3 --json out.json

Prints launches by operation and one table, reason -> launches; `--json` keeps the records.
"""

import argparse
import json
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any
from unittest import mock

import balance
import metrics
import runner

from nexus.contracts.gen.common.enums import Side
from nexus.core.world import World
from nexus.runtime.campaign_config import ConfigPaths, load_campaign_config

ENEMY: Side = "ENEMY"
STRIKE, HITS, JOBS = "STRIKE", "hits", "jobs"
STRIKE_OPS = ("OFFENSIVE", "RETAKE", "PROBE", "STRIKE_BRIDGE")
SAMPLE_TICKS = 100  # 10 s at the 10 Hz tick
TAPPED = frozenset({
    "UnitSpawned", "JobCreated", "JobClaimed", "JobReleased", "JobDone", "JobExpired", "JobFailed",
    "WeaponFired", "WeaponImpact", "UnitDamageStateChanged", "UnitDestroyed", "UnitDespawned",
    "SpawnRefused", "ThreatTierChanged", "NodeCaptured",
})  # fmt: skip


class Tap:
    """The events and samples of one run, grouped by Static operation launch."""

    def __init__(self) -> None:
        self.buf: list[Any] = []
        self.launches: list[dict[str, Any]] = []
        self.newest: dict[tuple[str, str], dict[str, Any]] = {}  # (op, target) -> its newest launch
        self.job_of: dict[
            int, tuple[dict[str, Any], dict[str, Any]]
        ] = {}  # job id -> (launch, job)
        self.unit_job: dict[int, dict[str, Any]] = {}  # unit -> the launch job it claimed last
        self.side: dict[int, str] = {}
        self.tier = "PATTERN_OF_LIFE"
        self.tiers: list[tuple[int, str]] = []
        self.flips: list[tuple[int, str, str]] = []
        self.refused: list[int] = []

    def feed(self, events: list[Any]) -> None:
        self.buf += [e for e in events if e.kind in TAPPED]

    def process(self, board: dict[int, Any]) -> None:
        """After the step, JobCreated first (the key is on the board only), then the rest."""
        buf, self.buf = self.buf, []
        for e in buf:
            if e.kind == "UnitSpawned":
                self.side[e.entity_id] = e.side
            elif e.kind == "JobCreated" and e.side == ENEMY:
                self._created(e, board)
        for e in buf:
            if e.kind == "JobCreated" or e.kind == "UnitSpawned":
                continue
            getattr(self, "_" + e.kind)(e)

    def _created(self, e: Any, board: dict[int, Any]) -> None:
        job = board.get(e.job_id)
        p = job.key.split(":") if job is not None else []
        if len(p) < 4 or p[0] != "op" or p[1] not in STRIKE_OPS:
            return
        if p[3] == "0":
            launch = {
                "op": p[1],
                "target": p[2],
                "tick": e.tick,
                "tier": self.tier,
                JOBS: [],
                "shots": [],
                "other_shots": [],
            }
            self.launches.append(launch)
            self.newest[(p[1], p[2])] = launch
        newest = self.newest.get((p[1], p[2]))
        if newest is None:
            return
        rec: dict[str, Any] = {
            "id": e.job_id, "kind": e.job_kind, "slots": e.slots, "created": e.tick,
            "claims": [], "releases": [], "end": None, "states": [], "units": {},
        }  # fmt: skip
        newest[JOBS].append(rec)
        self.job_of[e.job_id] = (newest, rec)

    def _unit(self, rec: dict[str, Any], eid: int) -> dict[str, Any]:
        unit: dict[str, Any] = rec["units"].setdefault(str(eid), {HITS: [], "damage": []})
        return unit

    def _JobClaimed(self, e: Any) -> None:
        if e.job_id in self.job_of:
            _, rec = self.job_of[e.job_id]
            rec["claims"].append((e.tick, e.entity_id))
            self._unit(rec, e.entity_id)
            self.unit_job[e.entity_id] = rec

    def _JobReleased(self, e: Any) -> None:
        if e.job_id in self.job_of:
            self.job_of[e.job_id][1]["releases"].append((e.tick, e.entity_id))

    def _end(self, e: Any, why: str) -> None:
        if e.job_id in self.job_of:
            self.job_of[e.job_id][1]["end"] = (why, e.tick)

    def _JobDone(self, e: Any) -> None:
        self._end(e, "done")

    def _JobExpired(self, e: Any) -> None:
        self._end(e, "expired")

    def _JobFailed(self, e: Any) -> None:
        self._end(e, "failed")

    def _WeaponFired(self, e: Any) -> None:
        if e.target_node_id is None or self.side.get(e.shooter_id) != ENEMY:
            return
        for (_, target), launch in self.newest.items():
            if target != e.target_node_id:
                continue
            rec = self.unit_job.get(e.shooter_id)
            own = rec is not None and self.job_of[rec["id"]][0] is launch
            launch["shots" if own else "other_shots"].append((e.tick, e.shooter_id, e.weapon))

    def _WeaponImpact(self, e: Any) -> None:
        rec = self.unit_job.get(e.target_id) if e.target_id is not None else None
        if rec is not None and e.hit:
            self._unit(rec, e.target_id)[HITS].append((e.tick, e.weapon, e.shooter_id))

    def _UnitDamageStateChanged(self, e: Any) -> None:
        if (rec := self.unit_job.get(e.entity_id)) is not None:
            self._unit(rec, e.entity_id)["damage"].append((e.tick, e.to))

    def _UnitDestroyed(self, e: Any) -> None:
        if (rec := self.unit_job.get(e.entity_id)) is not None:
            self._unit(rec, e.entity_id)["lost"] = ("destroyed", e.tick)

    def _UnitDespawned(self, e: Any) -> None:
        if (rec := self.unit_job.get(e.entity_id)) is not None:
            self._unit(rec, e.entity_id)["lost"] = (str(e.reason).lower(), e.tick)

    def _SpawnRefused(self, e: Any) -> None:
        if e.side == ENEMY:
            self.refused.append(e.tick)

    def _ThreatTierChanged(self, e: Any) -> None:
        if e.side == ENEMY:
            self.tier = e.to
            self.tiers.append((e.tick, e.to))

    def _NodeCaptured(self, e: Any) -> None:
        self.flips.append((e.tick, e.from_, e.to))

    def sample(self, world: World, tick: int) -> None:
        """Each followed job still on the board: its state (BLOCKED while the job it depends on is
        on the board), and its claimants' last state."""
        board = world.boards[ENEMY]
        for jid, (_, rec) in self.job_of.items():
            job = board.get(jid)
            if job is None:
                continue
            blocked = job.depends_on is not None and job.depends_on in board
            state = "BLOCKED" if blocked else job.state
            if not rec["states"] or rec["states"][-1][1] != state:
                rec["states"].append((tick, state))
            for eid in job.claims:
                if (ent := world.find(eid)) is not None:
                    self._unit(rec, eid)["last"] = {
                        "tick": tick, "kind": ent.kind, "state": ent.state,
                        "damage": ent.damage_state, "hp": ent.hp, "ammo": list(ent.ammo),
                        "fuel": round(ent.fuel or 0),
                    }  # fmt: skip


def run_one(profile: str, seed: int, hours: float, sets: tuple[str, ...] = ()) -> dict[str, Any]:
    tap = Tap()
    config = None
    if sets:  # the harness's own `--set` path: override, validate, load a copy
        with tempfile.TemporaryDirectory() as tmp:
            (bal := Path(tmp) / "balance.yaml").write_text(balance.override_balance(list(sets)))
            config = load_campaign_config(ConfigPaths(balance=bal))
    orig = metrics.Collector.feed

    def feed(self: Any, events: list[Any]) -> Any:
        tap.feed(events)
        return orig(self, events)

    def on_tick(tick: int, _step_s: float, world: World) -> bool:
        tap.process(world.boards[ENEMY])
        if tick % SAMPLE_TICKS == 0:
            tap.sample(world, tick)
        return False

    with (
        mock.patch.object(metrics.Collector, "feed", feed),
        tempfile.TemporaryDirectory() as tmp,
    ):
        res = runner.run(profile, seed, hours, Path(tmp) / "log", config=config, on_tick=on_tick)
    return {
        "seed": seed,
        "ticks_run": res["ticks_run"],
        "tick_hz": res["tick_hz"],
        "tiers": tap.tiers,
        "flips": tap.flips,
        "refused": tap.refused,
        "crash": res["crash"],
        "launches": tap.launches,
    }


def _job(launch: dict[str, Any], kind: str) -> dict[str, Any] | None:
    return next((j for j in launch[JOBS] if j["kind"] == kind), None)


def _sam_hit(unit: dict[str, Any]) -> bool:
    return any(w == "SAM" for _, w, _ in unit[HITS])


def _claimants(units: list[dict[str, Any]]) -> str:
    if units and all(_sam_hit(u) for u in units):
        return "all claimants SAM-hit"
    if any(u[HITS] for u in units):
        return "claimants hit, not all by a SAM"
    return "claimants unhit"


def classify(launch: dict[str, Any], ticks_run: int) -> str:
    """The launch's reason: fired (the funnel's rule: any Static shot at the target) or not, how
    its STRIKE claimants fared (`_claimants`) and how the STRIKE job ended, from its own records."""
    strike = _job(launch, STRIKE)
    units = list(strike["units"].values()) if strike else []
    if launch["shots"] or launch["other_shots"]:
        end = strike["end"][0] if strike and strike["end"] else "still open"
        return f"fired; {_claimants(units)}; STRIKE {end}"
    if strike is None:
        return "no STRIKE job posted with the launch"
    if launch["tick"] >= ticks_run:
        return "launched on the run's last tick (no time to fire)"
    end = strike["end"][0] if strike["end"] else "still open at the run's end"
    return f"not fired; {_claimants(units)}; STRIKE {end}"


def _capture_end(launch: dict[str, Any]) -> str:
    job = _job(launch, "CAPTURE")
    return "no CAPTURE job" if job is None else (job["end"][0] if job["end"] else "still open")


def summarize(runs: list[dict[str, Any]]) -> None:
    table: Counter[str] = Counter()
    by_op: Counter[str] = Counter()
    captures: Counter[str] = Counter()
    for r in runs:
        for launch in r["launches"]:
            by_op[launch["op"]] += 1
            table[classify(launch, r["ticks_run"])] += 1
            captures[_capture_end(launch)] += 1
    print(f"launches by op: {dict(by_op)}")
    for reason, n in sorted(table.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"{n:5d}  {reason}")
    print(f"{sum(table.values()):5d}  total")
    print(f"CAPTURE jobs ended: {dict(captures)}")
    hours = sum(r["ticks_run"] / r["tick_hz"] for r in runs) / 3600
    coalition_flips = sum(f[1] == "COALITION" for r in runs for f in r["flips"])
    other = sum(f[1] != "COALITION" for r in runs for f in r["flips"])
    print(f"Static flips in {hours:.0f} seed-hours: {coalition_flips} of a coalition node, {other} of others")
    print(f"tier changes: {sum(len(r['tiers']) for r in runs)}")
    targets: Counter[str] = Counter()
    sam: Counter[int] = Counter()
    losses: Counter[str] = Counter()
    shots: Counter[int] = Counter()
    for r in runs:
        for launch in r["launches"]:
            targets[launch["target"]] += 1
            strike = _job(launch, STRIKE)
            units = list(strike["units"].values()) if strike else []
            for u in units:
                sam.update(sh for _, w, sh in u[HITS] if w == "SAM")
            lost = sorted(u["lost"][0] for u in units if "lost" in u)
            losses[f"{len(units)} claimants, lost {lost}"] += 1
            if launch["shots"] or launch["other_shots"]:
                shots[len(launch["shots"]) + len(launch["other_shots"])] += 1
    print(f"launch targets: {dict(targets)}")
    print(
        f"SAM hits on STRIKE claimants, by shooter entity: {dict(sam)} (total {sum(sam.values())})"
    )
    print(f"STRIKE claimants per launch and how they were lost: {dict(losses)}")
    print(f"shots at the target per fired launch (shots: launches): {dict(sorted(shots.items()))}")
    for r in runs:
        print(f"seed {r['seed']} flips (tick, from, to): {[tuple(f) for f in r['flips']]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", default="overnight-0")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--hours", type=float, default=12.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--set", action="append", default=[], help="key=value, as balance.py --set")
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--from-json", type=Path, default=None, help="summarize a saved --json, no run")
    a = ap.parse_args()
    if a.from_json:
        summarize(json.loads(a.from_json.read_text()))
        return
    seeds = [int(s) for s in a.seeds.split(",")]
    with ProcessPoolExecutor(a.workers) as ex:
        runs = list(
            ex.map(
                run_one,
                [a.profile] * len(seeds),
                seeds,
                [a.hours] * len(seeds),
                [tuple(a.set)] * len(seeds),
            )
        )
    if a.json:
        a.json.write_text(json.dumps(runs, indent=1, default=list))
    summarize(runs)


if __name__ == "__main__":
    main()
