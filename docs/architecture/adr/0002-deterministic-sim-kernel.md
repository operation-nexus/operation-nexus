# ADR-0002: Deterministic, fixed-step simulation kernel at 10 Hz

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17

## Context
The plans call the sim deterministic, but the sample code uses `random`, `uuid4`, wall-clock time and a drifting `asyncio.sleep`. The plans also want an LLM-driven director, event-sourced replays and auto-clips. Without real determinism, we can't reproduce bugs from a stream, golden tests are impossible, and replays have to store full frames.

## Decision
- `core.step(state, commands, rng) -> (state, events)` is a pure function. Time is an integer `tick` at 10 Hz (dt = 0.1 s of sim time).
- Randomness comes from one `SimRng` (PCG64), seeded per campaign. Sub-streams are derived per subsystem, so adding a random draw in one subsystem doesn't shift the draws in the others.
- Entity ids are sequential integers allocated by the kernel. Iteration always happens in id order.
- Positions use float64. A canonical state hash quantizes values (to 1 mm and 1e-6) before hashing. Cross-machine float determinism is **not** guaranteed, so replays are verified on the same platform and Python version.
- Commands are applied in canonical order: `(target_tick, arrival_seq)`.
- All non-deterministic inputs (chat commands, LLM advisor choices, staff actions) enter only as logged `Command`s.
- The runtime uses a fixed-step accumulator on `time.monotonic()`, outside the kernel.

## Consequences
- Replays need only the seed, config hash, command log and periodic snapshots.
- Golden replay tests and cross-process hash checks become CI gates.
- A Semgrep rule bans wall-clock and random APIs in `nexus/core`.
- Revisit if floats cause cross-platform replay divergence that matters (for example, a public replay viewer running the sim in the browser). The option then is fixed-point math.
