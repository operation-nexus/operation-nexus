# ADR-0007: LLMs advise and narrate; deterministic rules decide

- Status: Proposed (Q-AI-1)
- Date: 2026-10-17

## Context
The owner wants a dynamic, unpredictable enemy that respects fog of war. The plans put an LLM (a local Gemma 27B) in charge of the director. LLMs are slow (seconds), cost money or VRAM, can't be replayed, are hard to test, can be manipulated through user text in their context, and "unpredictable" is not the same as "fun".

## Decision
- The Threat Director is rule-based and deterministic, and sees only its own fog-of-war view. Variety comes from seeded randomness, threat memory and a library of doctrine options.
- An optional **LLM advisor** (Phase P4) gets a structured, redacted battlespace summary (ids, no user strings) plus the list of currently *valid* operations. It returns a choice plus a short rationale, validated against a schema. If it's late, invalid or over budget, the rules pick instead. The choice is logged as a command, so replays stay deterministic.
- **LLM narration** (sitreps, operation names) uses templates with LLM embellishment, and passes output moderation before TTS.
- **Natural-language `!order`** (P4) only targets the requester's own unit, and its output is bounded by the schema.
- No large local LLM runs on the broadcast host.

## Consequences
Testable, cheap, and replayable. The LLM adds flavor and *apparent* intelligence without being on the critical path. If it turns out the LLM adds nothing measurable, we can remove it without changing gameplay.
