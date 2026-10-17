# SPEC: LLM Advisors (P4)

Status: Draft · Tracker: NX-240…NX-249 · ADR-0007 · Security: SEC-LLM-*

## 1. Uses
| Use | Input | Output schema | Deadline | Fallback |
|---|---|---|---|---|
| Director advisor | Structured enemy-view summary + top-K ops | `{choice_index, op_name, rationale}` | 2 decision windows | Rule pick |
| Narrator | Event + template slots (ids resolved to approved names after generation) | `{line ≤ 140 chars}` | 10 s | Template line |
| `!order` parser | Requester's own unit state + order text (≤ 200 chars) + node enum | `TacticalOrder{mission, target_node: enum, waypoint: bounded, profile}` | 5 s | "Brevity error" digest |

## 2. Requirements
- **LLM-1** The provider is behind our own `LlmClient` interface. Provider SDKs are called directly, and the lockfile is hash-pinned. LiteLLM is only allowed if it's isolated and pinned (Q-AI-3).
- **LLM-2** The advisor process has no platform or stream credentials (SEC-LLM-5).
- **LLM-3** Budgets: per-user `!order` 1/min and 5 per 10 min, a global $/day cap, and a circuit breaker on errors or latency.
- **LLM-4** All prompts are versioned files. Outputs are logged with prompt version, model, latency and cost.
- **LLM-5** Offline evaluation suite (TESTING-STRATEGY §3.8). CI uses only FakeLLM.
