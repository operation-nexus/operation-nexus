"""Run tools/balance/balance.py with extra per-run stock-flow counters (NX-389 analysis only).

Usage (from services/sim): uv run --frozen python <this> <balance.py args>
Adds `metrics.nx389` to each run JSON: per side, stock loaded at the rear source (cargo rising on a
carrier standing at its side's sanctuary), stock loaded at finite bases (lateral), stock delivered
(SupplyDelivered, by the node's owner), stock consumed (SupplyConsumed, by the node's owner),
carriers spawned, and the side's finite stock at start and end of the run.
"""
import sys
from collections import Counter
from pathlib import Path

BAL = Path(__file__).resolve().parents[0]
sys.path.insert(0, sys.argv.pop(1))  # tools/balance
import metrics  # noqa: E402

C = metrics.Collector
_init, _feed, _observe, _result = C.__init__, C.feed, C.observe, C.result


def _stock(world, side):
    return sum(s for n, s in world.stock.items() if world.owner.get(n) == side)


def init(self, world, *a, **k):
    _init(self, world, *a, **k)
    self._xw = world
    self._x = {k: Counter() for k in ("rear_loaded", "lateral_loaded", "delivered", "consumed", "carriers_spawned")}
    self._xstart = {s: _stock(world, s) for s in ("COALITION", "ENEMY")}
    self._xcargo = {}


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


def result(self, ran):
    r = _result(self, ran)
    w = self._xw
    r["nx389"] = {k: dict(v) for k, v in self._x.items()}
    r["nx389"]["stock_start"] = self._xstart
    r["nx389"]["stock_end"] = {s: _stock(w, s) for s in ("COALITION", "ENEMY")}
    return r


C.__init__, C.feed, C.observe, C.result = init, feed, observe, result
sys.argv[0] = "balance.py"
import balance  # noqa: E402

sys.exit(balance.main())
