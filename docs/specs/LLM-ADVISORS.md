# SPEC: LLM Advisors (P4)

Status: Draft · Tracker: NX-240…NX-249 · ADR-0007 · Security: SEC-LLM-*

## 1. Uses
| Use | Input | Output schema | Deadline | Fallback |
|---|---|---|---|---|
| Director advisor | Structured enemy-view summary + top-K ops | `{choice_index, op_name, rationale}` | 2 decision windows | Rule pick |
| Narrator | Event + template slots (ids resolved to approved names after generation) | `{line ≤ 140 chars}` | 10 s | Template line |
| `!order` parser | Requester's own unit state + order text (≤ 200 chars) + node enum. The parser maps onto the **intent and command catalog** ([COMMAND-CATALOG](COMMAND-CATALOG.md) CC-3) only (Q-AI-2); players get `!order help` and on-screen examples | `TacticalOrder{mission, target_node: enum, waypoint: bounded, profile}` | 5 s | "Brevity error" digest |

## 2. Requirements
- **LLM-1** The provider is behind our own `LlmClient` interface (ADR-0010). Hosted and local (llama.cpp/Ollama) providers are interchangeable via config, and each one passes the LLM conformance suite (schema adherence, deadline, budget accounting, error mapping). Official provider SDKs are called directly, and the lockfile is hash-pinned. **No LiteLLM** (Q-AI-3, decided 2026-10-17). Standards-based options (e.g. OpenAI-compatible endpoints) may be revisited only behind our own port.
- **LLM-1a Local experiment (Q-ARCH-4):** a local llama.cpp/Ollama provider on the gaming-PC GPU (GTX 1070 8 GB) is an approved free experiment, narration first. It is enabled only after passing the quality benchmark (NX-292) and is auto-disabled if stream quality suffers (frame time, encoder lag). Nothing depends on it; the hosted provider or templates remain the fallback.
- **LLM-2** The advisor runs in its **own isolated container** (owner decision Q-AI-3): no platform or stream credentials (SEC-LLM-5), egress allowlist limited to the configured provider endpoints, read-only root filesystem, non-root user, CPU and memory limits. It talks to the app only through the internal `LlmClient` RPC.
- **LLM-3** Budgets: per-user `!order` 1/min and 5 per 10 min, a global $/day cap, and a circuit breaker on errors or latency. **Monthly hard cap: $20 for LLM + cloud TTS combined** (Q-AI-5, decided 2026-10-17), enforced by an automatic cutoff (circuit breaker). Over the cap, the director uses rules (FB-2) and narration uses template lines (FB-3). An ops alert fires at **80%** of the monthly cap (OPS-ADMIN §2).
- **LLM-4** All prompts are versioned files. Outputs are logged with prompt version, model, latency and cost.
- **LLM-5** Offline evaluation suite (TESTING-STRATEGY §3.8). CI uses only FakeLLM.
- **LLM-6 Taunt lines (P4, THREAT-DIRECTOR TD-3/TD-4, Q-AI-7):** the LLM may write the text of a Static taunt but never sees a name, callsign or chat text (SEC-LLM-4). Code fills the `{target}` placeholder after generation, with an approved callsign only, and never with a commander whose `taunt_opt_out` is set by `!quiet` (Q-ALN-12, DATA-MODEL §4.2). The naming cooldowns (`taunt.name_cooldown_min`, `taunt.name_cooldown_spotlight_min`) are real time and are checked in code before the fill, not by the LLM (Q-ALN-4). A taunt prompt lists no command the parser doesn't handle, so `!quiet` appears in a prompt only once its parser entry and handler exist (AGENTS.md rule 6a).
