# tools/

Developer tools: chat simulator (NX-193), replay CLI (NX-032), balance harness (NX-031), load bots. Each tool arrives with its tracker item.

| Tool | What | Tracker |
|---|---|---|
| [discord-setup](discord-setup/README.md) | Owner-run setup of the community Discord server; never holds a token in a session or repo | NX-354 |
| [sim-determinism](sim-determinism/check.py) | Cross-process determinism check: every golden replay in four interpreters with different `PYTHONHASHSEED` values, against the committed hashes (CI job `sim-determinism`) | NX-105 |
| [sim-bench](sim-bench/bench.py) | Throwaway SIM-CORE benchmark spike: objects vs NumPy, tick p99, frame-stream bytes. Results: [NX-345-BENCH](../docs/review/NX-345-BENCH.md) | NX-345 |
| [sim-bench/grid_bench.py](sim-bench/grid_bench.py) | Benchmark of the real `nexus.core.spatial.UniformGrid`: rebuild + one radius query per entity, tick p50/p95/p99. Results: [NX-104-BENCH](../docs/review/NX-104-BENCH.md) | NX-104 |
