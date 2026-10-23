# Testing Strategy

Status: Draft · Tracker: NX-030…NX-039

The raw plan's testing section ("80% coverage", "Playwright guarantees 60 FPS") isn't enough for this system. Coverage percentage doesn't prove a simulation is correct, and Playwright on a CI runner can't guarantee broadcast frame rates. This strategy is built around the risks that are specific to Operation Nexus.

## 1. Risk → test mapping

| Risk | What catches it |
|---|---|
| Sim diverges between runs (replays break, bugs can't be reproduced) | Golden replay tests + cross-process determinism check (§3.2) |
| Game rules have edge-case bugs (negative supply, capture flapping, units stuck) | Property-based tests with invariants (§3.1) |
| Balance is broken (steamrolls, 3am stalemates, veterans dominate) | Balance harness with scripted bot populations (§3.5) |
| Hostile chat input breaks things (injection, unicode, spam) | Fuzzing of the command parser + moderation corpus tests (§3.3) |
| Memory leak / slowdown after days of uptime | Nightly soak + perf budgets (§3.6) |
| Wire contract drift between Python and TS | Generated types + drift check + contract tests (§3.4) |
| Overlay visually broken or unreadable | Playwright visual snapshots on a fixed state fixture (§3.7) |
| LLM output is malformed or malicious | Schema validation tests with recorded adversarial outputs; LLM never required for CI (§3.8) |
| Platform API changes or outages | Adapter contract tests against recorded fixtures + a nightly live smoke test against a test channel (§3.4) |
| Deploy drops the stream | Snapshot/restore test in integration; staging deploy rehearsal (§3.9) |

## 2. Test pyramid and budgets

| Level | Tooling | Runs | Time budget |
|---|---|---|---|
| Unit | pytest, vitest | every PR | < 60 s per language |
| Property | hypothesis (`ci` profile: 200 examples; `nightly`: 5,000) | every PR / nightly | < 90 s on PR |
| Golden replay / determinism | pytest + replay CLI | every PR touching sim | < 2 min |
| Contract | schema drift, adapter fixtures, WS contract | every PR | < 1 min |
| Integration | docker compose + scripted bots | every PR (path-filtered) | < 5 min |
| E2E / visual | Playwright | every PR touching overlay | < 3 min |
| Soak | full stack, 6 h | nightly | — |
| Balance | harness: 20 seeds × scenarios (balance-diff report); 50 seeds for the acceptance run (§3.5a, Q-TEST-4) | nightly + on balance PRs; a reduced acceptance run before P1 exit, the full run during P2 (Q-TEST-10) | < 20 min for the diff (not met yet: see `tools/balance/README.md` Cost); acceptance not time-boxed yet |

## 3. Details

### 3.1 Property-based invariants (sim-core)
Examples that must always hold after any sequence of valid commands:
- Supply at every node is in `[0, max_supply]`. Total supply is conserved, except at sources and sinks, which are logged.
- An entity has exactly one owner, and every viewer has at most one active personal unit.
- No entity position is NaN or outside map bounds. Ground units only sit on ground-graph edges.
- Node capture progress is monotonic while uncontested, and a capture can't flip twice in the same tick.
- Fog of war: the redacted snapshot sent to clients contains no enemy entity that fails the visibility predicate. SIGINT blobs never contain exact ids or exact positions.
- The Threat Director's spawned budget never exceeds its tier budget.

### 3.2 Determinism
- `state_hash(tick)` is a canonical hash of sorted, quantized state. It's emitted every 100 ticks.
- **Golden replays:** each case in `services/sim/tests/golden/<name>/` is (seed, config hash, command log) plus the pinned checkpoint and event-stream hashes ([README](../../services/sim/tests/golden/README.md)). CI replays them and compares checkpoint hashes. An intentional rule change regenerates the goldens in the same PR (`NEXUS_UPDATE_GOLDEN=1`), with a `golden-update` label and a note explaining why.
- **Cross-process:** `tools/sim-determinism/check.py` (CI job `sim-determinism`) runs every golden case in four processes with different `PYTHONHASHSEED` values, and the hashes must match each other and the pinned ones.
- **LLM decisions are recorded as events.** Replays never call an LLM.

### 3.3 Hostile input
- Fuzz `parse_command()` with hypothesis (arbitrary unicode, zero-width characters, RTL overrides, 10 KB strings, homoglyph callsigns).
- Moderation corpus: a list of known slurs and evasions (kept in a private submodule or a hashed list, Q-MOD-2) must be blocked from callsigns, TTS, and overlay text.
- Rate-limit tests: 1 user × 100 msg/s, 500 users × 1 msg/s, and a raid burst.

### 3.4 Contracts and platform adapters
- `contracts/` JSON Schema is the source of truth. Generated Pydantic and TS types are committed, and CI regenerates them and diffs.
- WS contract test: a recorded server stream is replayed into the overlay's decoder, which must decode without error. Unknown fields are ignored and unknown message types are logged.
- Adapter tests run against recorded fixtures (EventSub payloads, YouTube liveChatMessages pages) and include malformed or edge cases.

### 3.5 Balance harness (`tools/balance`)
Scripted viewer populations (lurker, newbie, veteran, logistics-lover, troll, AFK farmer) drive the sim headless at many times real time. Standard scenarios are the crowd profiles of 0, 5, 50, 150, 300 and 500 simulated viewers (`overnight-0`, `quiet-5`, `prime-50`, `evening-150`, `raid-300`, `surge-500`; Q-TEST-5), plus the adversarial profiles (`troll-swarm`, spammer, alt farmer, griefer, raid wave; NX-321) (Q-ALN-42). Metrics: momentum curve, campaign length, newbie time-to-first-impact, kill-share Gini by rank, director tier dwell time, supply starvation minutes. Results go to a nightly artifact and trend chart.

### 3.5a Balance acceptance criteria (NX-312, Q-TEST-2, Q-TEST-4 … Q-TEST-8)
A value drops its PROPOSED label (DI-7) only when an acceptance run passes: **50 seeds** across every standard and adversarial profile, campaigns at the default `campaign.time_limit_h` (72) with no extension, and a saved report with the config hash and each target's result (NX-321). Per-PR balance-diff reports use 20 seeds and do not count as acceptance. **P1 exit** uses a reduced run, 10 seeds per standard crowd profile at 72 h, judged on A1 to A4; the full run finishes on the owner PC queue during P2 (Q-TEST-10). Thresholds marked PROPOSED are re-tuned after the first runs and tracked on the playtest watch list.

| # | Target | Pass when | Status |
|---|---|---|---|
| A1 | Campaign length | ≥85% of seeds end in **victory or defeat** within 24–72 h of game time; a time-limit ending counts as a miss (Q-TEST-6) | decided |
| A2 | New-player impact | newbies who arrive while the Static Director's tier is ALPHA or above make a real contribution of their own: the **median** time to first impact is at most 8 min (the top of a sortie, SIM-CORE world scale) and **at most 10%** wait over 15 min. Impact by role: a striker or auto-tasked unit lands a weapon hit, a kill or capture progress; a scout finds a new enemy track; a hauler departs a source loaded with cargo for a delivery (its delivery comes later and counts too). Newbies who arrive at Pattern of Life are reported, not judged (Q-SIM-93, Q-SIM-97) | decided |
| A3 | Garrison holds at 0 viewers | `overnight-0` over 12 h loses at most one strategic node and the sanctuary's defense HP never reaches 0 | PROPOSED (Q-TEST-8) |
| A4 | No dominant kind | no unit kind gets more than 40% of the coalition's kills in any profile | PROPOSED (Q-TEST-8); suspended until a second armed viewer unit kind exists, the harness reports it as suspended (owner, Q-SIM-92) |
| A5 | Adversarial bound | each adversarial profile shifts the median campaign length by under 20% vs the same crowd size without it, and moves no leaderboard | PROPOSED (Q-TEST-8) |
| A6 | Conduct | the conduct system flags the adversarial personas once it exists | decided; measured from NX-291 |
| A7 | First impression | a viewer who joins gets the command acknowledgement and sees their unit on the overlay within 5 s (the ack itself stays under §3.6's 500 ms) | decided (Q-SIM-97); measured from P2, when the gateway and overlay exist |

### 3.6 Performance budgets (initial; SYSTEM-DESIGN §3 NFRs)
- Sim tick p99 < 25 ms at 1,000 entities (10 Hz → 100 ms budget, leaving headroom).
- Fan-out: WS delta frame < 16 KB p95 at 1,000 entities.
- Command-to-screen: from ingest to the overlay showing an ack < 500 ms p95, excluding platform latency.
- Overlay: frame time p95 < 12 ms at 1080p on the reference host (Q-TEST-1; measured on the real machine in a perf run, not in CI).

### 3.7 Overlay visual tests
Fixture states (empty map, heavy combat, fog-heavy, raid with 500 units, long callsigns, RTL names) render to screenshots, which are compared against baselines with a tolerance. Accessibility checks: a palette contrast script and simulated colorblind renders.

### 3.8 LLM components
- CI never calls a real model. Use a `FakeLLM` that replays recorded responses, including malformed JSON, out-of-range coordinates, injected instructions, and timeouts.
- Offline eval suite (manual or nightly with budget cap): N labeled chat orders → expected `TacticalOrder`; track accuracy and cost per call.

### 3.9 Deploy safety
An integration test does: snapshot → kill sim → restart new build → restore → state hash equal. Staging deploy rehearsal on every merge.

## 4. Coverage policy
Coverage is a floor, not a goal: sim-core ≥ 85% line and branch; diff coverage on PRs ≥ 90%. Excluded: generated code, `__main__`, and platform glue covered by contract tests.

## 5. Flaky tests
A flaky test is a bug. Quarantine is not allowed. Fix the root cause or delete the test with owner approval and a tracker item.
