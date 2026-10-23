"""NX-371: the runtime's idle test for reserve-queue entries (GAMEPLAY RQ-1)."""

from nexus.runtime.queue_idle import idle_entries

A = "0192f0c1-7a2b-7c3d-8e4f-000000000001"
B = "0192f0c1-7a2b-7c3d-8e4f-000000000002"
C = "0192f0c1-7a2b-7c3d-8e4f-000000000003"


def ids(last_active: dict[str, float], now: float, minutes: int = 15) -> list[str]:
    return [c.commander_id for c in idle_entries(last_active, now, minutes)]


def test_only_entries_silent_for_the_full_time_time_out_in_queue_order() -> None:
    last_active = {A: 0.0, B: 100.0, C: 1000.0}
    assert ids(last_active, 899.9) == []
    assert ids(last_active, 900.0) == [A]  # exactly queue_idle_min counts
    assert ids(last_active, 1000.0) == [A, B]
    assert ids({}, 1e9) == []


def test_the_command_is_a_valid_system_command() -> None:
    (cmd,) = idle_entries({A: 0.0}, 900.0, 15)
    assert (cmd.kind, cmd.source, cmd.issuer.system) == (
        "SYS_QUEUE_TIMEOUT",
        "SYSTEM",
        "queue-idle",
    )
    assert len(cmd.correlation_id) <= 64


def test_paused_time_does_not_count() -> None:
    # The caller's clock is monotonic time minus total paused time (module doc).
    def running(mono: float, paused: float) -> float:
        return mono - paused

    seen = running(100.0, 0.0)  # last chat message
    # A 10 h outage pause: nothing is idle after it.
    assert ids({A: seen}, running(100.0 + 36000.0, 36000.0)) == []
    # 15 unpaused minutes later it is (14 min 59 s is not).
    assert ids({A: seen}, running(100.0 + 36000.0 + 899.0, 36000.0)) == []
    assert ids({A: seen}, running(100.0 + 36000.0 + 900.0, 36000.0)) == [A]
