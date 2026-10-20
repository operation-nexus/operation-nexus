# Role: Simulation Engineer

**Use for:** anything under `services/sim/src/nexus/core/`: tick loop, kinematics, combat, fog of war, logistics, the Threat Director's rule engine.

Must read: `docs/specs/SIM-CORE.md`, `docs/specs/GAMEPLAY.md`, `docs/specs/THREAT-DIRECTOR.md`, ADR-0002 (determinism).

Hard rules:
- No `time.time()`, `datetime.now()`, `random.*`, `uuid4()`, `asyncio`, or I/O inside the core. Time is `tick: int`. Randomness comes from the injected `SimRng` seeded per campaign.
- Iterate collections in a stable order (sorted by entity id).
- Commands and events are the generated types in `nexus.contracts.gen`; build events with `model_construct` on the hot path (Q-CT-7). A new command or event follows the `contracts/README.md` checklist in the same PR as its handler.
- All tunables live in versioned balance config files, not literals.
- Each feature ships with: unit tests, a property test (hypothesis) for invariants, and a golden replay test (same seed + same command log yields the same state hash).
- Performance: stay within the tick budget in SIM-CORE §Budgets. Add a benchmark when you add an O(n²)-or-worse loop.
