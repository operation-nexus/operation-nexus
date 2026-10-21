"""Bounded, thread-safe command inbox (SIM-CORE §5, SC-6; SYSTEM-DESIGN §5.1).

The inbox owns the next tick, so a command is stamped and drained under one lock and can never
target a tick that was already drained. The capacity config key lands with NX-106. Overflow only
counts here; nothing replies to chat yet.
"""

import threading

from nexus.contracts.gen.commands.command import Command


class Inbox:
    def __init__(self, capacity: int, next_tick: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._pending: list[Command] = []
        self._next_seq = 1
        self.next_tick = next_tick  # the tick the sim computes next
        self.rejected_overflow = 0

    def submit(self, command: Command) -> bool:
        """Stamp `target_tick` and `arrival_seq` and admit; False (and counted) when full."""
        with self._lock:
            if len(self._pending) >= self._capacity:
                self.rejected_overflow += 1
                return False
            update = {"target_tick": self.next_tick, "arrival_seq": self._next_seq}
            self._pending.append(command.model_copy(update=update))
            self._next_seq += 1
            return True

    def drain(self) -> list[Command]:
        """Take all pending commands (all target `next_tick`) in arrival order; advance the tick."""
        with self._lock:
            due, self._pending = self._pending, []
            self.next_tick += 1
            return due
