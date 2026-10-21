"""Runs the kernel for the steps the clock says are due (SIM-CORE §5, SYSTEM-DESIGN §5.2).

The command log and snapshots land with NX-103, the `state_hash` cadence with NX-105, metric
export with NX-250. Starting the sim thread (SIM-CORE §5 threading) has no tracker item yet.
"""

from nexus.contracts.gen.events.event import Event
from nexus.core.step import step
from nexus.core.world import World
from nexus.runtime.clock import FixedStepClock
from nexus.runtime.inbox import Inbox


class SimRuntime:
    def __init__(self, world: World, inbox: Inbox, clock: FixedStepClock) -> None:
        if inbox.next_tick != world.campaign.tick + 1:
            raise ValueError(f"inbox.next_tick {inbox.next_tick} != world tick + 1")
        self.world = world
        self.inbox = inbox
        self.clock = clock

    def run_due(self) -> list[Event]:
        """Drain and step once per due step; returns the events in order."""
        events: list[Event] = []
        for _ in range(self.clock.due_steps()):
            events += step(self.world, self.inbox.drain())
        return events
