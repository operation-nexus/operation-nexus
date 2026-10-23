"""Idle reserve-queue entries (GAMEPLAY RQ-1, Q-SIM-12, `slots.queue_idle_min`; NX-371).

The sim has no wall clock, so the runtime decides an entry is idle and submits a logged
`SYS_QUEUE_TIMEOUT` that the sim applies (`ReserveQueueLeft{TIMEOUT}`). Idle means: no chat message
from that commander for `queue_idle_min` real minutes. The gateway will feed last-activity times
(NX-190); until it exists the caller may feed JOIN times.

Paused time does not count (lead decision, NX-371): the offline auto-pause (Q-OPS-8) must not wipe
the queue. So all times here are on the caller's "running real time" clock: seconds of real time
with the paused periods left out (a monotonic clock minus the total time spent paused).
"""

from collections.abc import Mapping

from nexus.contracts.gen.commands.sys_queue_timeout import SysQueueTimeoutCommand

SYSTEM_NAME = "queue-idle"


def idle_entries(
    last_active: Mapping[str, float], now: float, queue_idle_min: int
) -> list[SysQueueTimeoutCommand]:
    """One timeout command per commander whose last activity is `queue_idle_min` or more minutes
    before `now` (both in running-real-time seconds, see the module doc), in `last_active` order.
    Pure. `Inbox.submit` stamps `target_tick` and `arrival_seq`; the values here are placeholders."""
    limit = queue_idle_min * 60
    return [
        SysQueueTimeoutCommand.model_validate(
            {
                "kind": "SYS_QUEUE_TIMEOUT",
                "source": "SYSTEM",
                "issuer": {"system": SYSTEM_NAME},
                "target_tick": 1,
                "arrival_seq": 1,
                "correlation_id": f"queue-idle-{commander}"[:64],
                "commander_id": commander,
            }
        )
        for commander, since in last_active.items()
        if now - since >= limit
    ]
