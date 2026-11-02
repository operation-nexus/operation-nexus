# Role: Simulation Engineer

**Use for:** anything under `services/sim/src/nexus/core/`: tick loop, kinematics, combat, fog of war, logistics, the Threat Director's rule engine.

Must read: `docs/specs/SIM-CORE.md` (normative, whole), only the `docs/specs/GAMEPLAY.md` and `docs/specs/THREAT-DIRECTOR.md` sections the brief names (`python3 scripts/spec_section.py SPEC SECTION`), and ADR-0002 (determinism). Read `docs/specs/SIM-CORE-NOTES.md` or `docs/specs/THREAT-DIRECTOR-NOTES.md` only when you need the history or current-implementation detail.

Hard rules:
- No `time.time()`, `datetime.now()`, `random.*`, `uuid4()`, `asyncio`, or I/O inside the core. Time is `tick: int`. Randomness comes from the injected `SimRng` seeded per campaign.
- Iterate collections in a stable order (sorted by entity id).
- Commands and events are the generated types in `nexus.contracts.gen`; build events with `model_construct` on the hot path (Q-CT-7). A new command or event follows the `contracts/README.md` checklist in the same PR as its handler.
- Every outcome-changing number is a balance or content key with a schema entry and a CONFIG-AND-CONTENT row (Q-DEV-21), not a literal. `tests/core/test_kernel_literals.py` fails on a new kernel literal; a literal that stays carries a reason (PERF, SCALE or STRUCT).
- Each feature ships with: unit tests, a property test (hypothesis) for invariants, and a golden replay test (same seed + same command log yields the same state hash).
- Performance: stay within the tick budget in SIM-CORE §Budgets. Add a benchmark when you add an O(n²)-or-worse loop.
