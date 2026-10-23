"""Direct-order health (NX-398, Q-SIM-110): orders off the board must never break or stick.

`Orders.feed(events)` and `observe(world)` after every tick, like `metrics.Collector`. It counts:
- `stuck_goto`: units whose GOTO order has an empty path at two board passes in a row without a
  hold (`Entity.held_since`), or whose hold has lasted `tasking.order_dwell_s` or more. A unit the
  kernel says is still working (`tasking.order_working`: a truck with cargo unloading, a ground
  unit on its side's filling capture bar) is not counted; a cargo stop has no bound here.
- `stale_claims`: board claims with no progress for `tasking.claim_lease_s` or more after a pass
  (the pass releases those, TB-1), each (job, unit) once.
- for the freelancer persona's direct orders: how many ended (the order is gone or the unit is),
  and how many of those ended with no shot fired, no delivery and no capture by that unit.
It only reads the world.
"""

from collections.abc import Iterable
from typing import Any

from nexus.core.tasking import order_working
from nexus.core.world import World


class Orders:
    def __init__(self, world: World, freelancers: frozenset[str]) -> None:
        rules = world.rules
        if rules is None or rules.tasking is None:
            raise ValueError("the order checks need the tasking rules")
        self._tr = rules.tasking
        self.freelancers = freelancers
        self.active: dict[int, bool] = {}  # freelancer unit -> it had an effect on this order
        self.unit_of: dict[str, int] = {}  # freelancer commander -> its unit on an order
        self.ended = self.no_effect = 0
        self.stuck: set[int] = set()
        self.stale: set[tuple[int, int]] = set()
        self._idle_goto: set[int] = set()  # GOTO, no path, no hold, at the last pass

    def feed(self, events: Iterable[Any]) -> None:
        for e in events:
            if e.kind == "UnitSpawned" and e.commander_id in self.freelancers:
                self.active[e.entity_id] = False
                self.unit_of[e.commander_id] = e.entity_id
            elif e.kind == "WeaponFired":
                self._effect(e.shooter_id)
            elif e.kind == "SupplyDelivered":
                self._effect(self.unit_of.get(e.commander_id))
            elif e.kind == "NodeCaptured":
                for c in e.participant_commander_ids:
                    self._effect(self.unit_of.get(c))

    def _effect(self, entity: int | None) -> None:
        if entity in self.active:
            self.active[entity] = True

    def observe(self, world: World) -> None:
        for eid, effect in sorted(self.active.items()):
            e = world.find(eid)
            if e is None or e.order != "GOTO":
                del self.active[eid]
                self.ended += 1
                self.no_effect += not effect
        now = world.campaign.running_ticks
        if now % self._tr.reeval_every_ticks or world.frozen:
            return
        idle: set[int] = set()
        for e in world.entities():
            if e.order != "GOTO" or e.path or order_working(world, e):
                continue
            if e.held_since is None:
                idle.add(e.id)
                if e.id in self._idle_goto:
                    self.stuck.add(e.id)
            elif now - e.held_since >= self._tr.order_dwell_ticks:
                self.stuck.add(e.id)
        self._idle_goto = idle
        for board in world.boards.values():
            for job in board.values():
                for i, c in job.claims.items():
                    if job.depends_on is None and now - c.at >= self._tr.claim_lease_ticks:
                        self.stale.add((job.id, i))

    def result(self) -> dict[str, Any]:
        return {
            "direct_orders_ended": self.ended,
            "no_effect": self.no_effect,
            "no_effect_share": self.no_effect / self.ended if self.ended else None,
            "stuck_goto": len(self.stuck),
            "stale_claims": len(self.stale),
        }
