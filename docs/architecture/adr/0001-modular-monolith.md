# ADR-0001: Start as a modular monolith

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17

## Context
The raw plan proposes five containers (chat gateway, LLM worker, sim core, Redis+DB, frontend), plus Helm "from day one", K3s, and a Discord bot. There is one developer. Every process boundary adds serialization, deployment, versioning, failure modes and observability work. None of the stated loads (≤ a few hundred concurrent players, about 100 chat messages per second at most) need horizontal scale.

## Options considered
1. **Microservices from day one.** Mirrors the eventual shape, but most of the effort goes into plumbing, and testing is hard.
2. **Modular monolith** (one Python process, with module boundaries enforced by import-linter) plus separate processes only where isolation is required: the TTS worker (GPL and crash isolation), and the overlay as static files.
3. **Single script.** Fast to start, but it turns into a ball of mud and can't be tested.

## Decision
Option 2. The app is a single `nexus-app` process. TTS runs as a separate worker process, and the overlay is a static bundle. Redis, Helm and K3s are deferred.

## Consequences
- Local development is just `make dev`. CI integration tests are simple.
- Boundaries still exist in code, so splitting a module out later is mechanical. The triggers are listed in SYSTEM-DESIGN §7.
- A crash in any module restarts the whole app. That is mitigated by fast snapshot restore (NFR-5).

## Amendment (2026-10-17): the LLM code runs in its own container (Q-AI-3)
The owner decided that **all LLM code runs in its own isolated container**, regardless of library: no platform or stream credentials, egress allowlisted to the provider endpoints, read-only filesystem, non-root, resource limits (LLM-ADVISORS LLM-2). So there are now two required isolation exceptions to the single `nexus-app` process: the **TTS worker** (GPL and crash isolation) and the **LLM container** (`nexus-llm`, security isolation). The rest of the app stays one modular-monolith process; the advisor still feeds the sim only through logged commands (ADR-0007).
