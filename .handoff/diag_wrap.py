"""Diagnosis wrapper (NX-389 follow-up, analysis only): harness_wrap's stock-flow counters plus
- `diag.claims`: JobClaimed by "<side>|<job kind>|<unit kind>|<owner kind>"
- `diag.created`: JobCreated by "<side>|<job kind>"
- `diag.cmd_strike_state`: per idle sample, COMMANDER-owned coalition STRIKE_FIGHTER units by what they are doing
  ("job:<kind>", "order", "follow", "idle", "path")
- `diag.cmd_hits_by_job`: hits by COMMANDER-owned coalition shooters, by the shooter's job kind at the hit
- `diag.prov`: the Static's provocation (points) and tier at every idle sample
- `diag.trucks_state`: per idle sample, coalition carriers by owner kind and job kind
Usage (from services/sim): uv run --frozen python <this> <tools/balance dir> <balance.py args>
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, sys.argv.pop(1))  # tools/balance
import metrics  # noqa: E402

C = metrics.Collector
_init, _feed, _observe, _result, _si = C.__init__, C.feed, C.observe, C.result, C.sample_idle


def _stock(world, side):
    return sum(s for n, s in world.stock.items() if world.owner.get(n) == side)


def init(self, world, *a, **k):
    _init(self, world, *a, **k)
    self._xw = world
    self._x = {k: Counter() for k in ("rear_loaded", "lateral_loaded", "delivered", "consumed", "carriers_spawned")}
    self._xstart = {s: _stock(world, s) for s in ("COALITION", "ENEMY")}
    self._xcargo = {}
    self._jk = {}
    self._d = {k: Counter() for k in ("claims", "created", "cmd_strike_state", "cmd_hits_by_job", "trucks_state")}
    self._prov = []


def _jobkind(self, jid):
    return self._jk.get(jid, ("?", "?"))[1] if jid is not None else None


def feed(self, events):
    events = list(events)
    w = self._xw
    for e in events:
        if e.kind == "SupplyDelivered":
            self._x["delivered"][w.owner.get(e.node_id)] += e.amount
        elif e.kind == "SupplyConsumed":
            self._x["consumed"][w.owner.get(e.node_id)] += e.amount
        elif e.kind == "UnitSpawned" and e.unit_kind in ("LOGI_TRUCK", "ENEMY_CONVOY"):
            self._x["carriers_spawned"][e.side] += 1
        elif e.kind == "JobCreated":
            self._jk[e.job_id] = (e.side, e.job_kind)
            self._d["created"][f"{e.side}|{e.job_kind}"] += 1
        elif e.kind == "JobClaimed":
            side, jk = self._jk.get(e.job_id, ("?", "?"))
            u = w.find(e.entity_id)
            uk = u.kind if u else "?"
            ok = u.owner_kind if u else "?"
            self._d["claims"][f"{side}|{jk}|{uk}|{ok}"] += 1
        elif e.kind == "WeaponImpact" and e.hit:
            u = w.find(e.shooter_id)
            if u is not None and u.side == "COALITION" and u.owner_kind == "COMMANDER":
                jk = _jobkind(self, u.job_id)
                tag = f"job:{jk}" if jk else ("follow" if u.follow_id else ("order" if u.order else "none"))
                self._d["cmd_hits_by_job"][tag] += 1
    _feed(self, events)


def observe(self, world):
    sup = world.rules.supply
    seen = {}
    for e in world.entities():
        if e.kind not in sup.carriers:
            continue
        c = e.cargo or 0
        up = c - self._xcargo.get(e.id, 0)
        if up > 0:
            key = "rear_loaded" if e.last_node == sup.rear[e.side] else "lateral_loaded"
            self._x[key][e.side] += up
        seen[e.id] = c
    self._xcargo = seen
    _observe(self, world)


def sample_idle(self, world):
    sup = world.rules.supply
    for e in world.entities():
        if e.side != "COALITION":
            continue
        jk = None if e.job_id is None else world.boards["COALITION"].get(e.job_id)
        jk = jk.kind if jk is not None else None
        if e.kind == "STRIKE_FIGHTER" and e.owner_kind == "COMMANDER":
            tag = f"job:{jk}" if jk else ("follow" if e.follow_id else ("order" if e.order else ("path" if e.path else "idle")))
            self._d["cmd_strike_state"][tag] += 1
        elif e.kind in sup.carriers:
            self._d["trucks_state"][f"{e.owner_kind}|{jk}"] += 1
    st = world.director["ENEMY"]
    self._prov.append((world.campaign.tick, st.provocation, st.tier))
    _si(self, world)


def result(self, ran):
    r = _result(self, ran)
    w = self._xw
    r["nx389"] = {k: dict(v) for k, v in self._x.items()}
    r["nx389"]["stock_start"] = self._xstart
    r["nx389"]["stock_end"] = {s: _stock(w, s) for s in ("COALITION", "ENEMY")}
    r["diag"] = {k: dict(v) for k, v in self._d.items()}
    r["diag"]["prov"] = self._prov
    return r


C.__init__, C.feed, C.observe, C.result, C.sample_idle = init, feed, observe, result, sample_idle
sys.argv[0] = "balance.py"
import balance  # noqa: E402

sys.exit(balance.main())
