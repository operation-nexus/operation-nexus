# ADR-0007: LLMs advise and narrate; deterministic rules decide

- Status: Accepted (owner, 2026-10-17)
- Date: 2026-10-17

## Context
The owner wants a dynamic, unpredictable enemy that respects fog of war. The plans put an LLM (a local Gemma 27B) in charge of the director. LLMs are slow (seconds), cost money or VRAM, can't be replayed, are hard to test, can be manipulated through user text in their context, and "unpredictable" is not the same as "fun".

## Decision
- The Threat Director is rule-based and deterministic, and sees only its own fog-of-war view. Variety comes from seeded randomness, threat memory and a library of doctrine options.
- An optional **LLM advisor** (Phase P4) gets a structured, redacted battlespace summary (ids, no user strings) plus the list of currently *valid* operations. It returns a choice plus a short rationale, validated against a schema. If it's late, invalid or over budget, the rules pick instead. The choice is logged as a command, so replays stay deterministic.
- **LLM narration** (sitreps, operation names) uses templates with LLM embellishment, and passes output moderation before TTS.
- **Natural-language `!order`** (P4) only targets the requester's own unit, and its output is bounded by the schema.
- No large local LLM runs on the broadcast host. **Amended 2026-10-17 (Q-ARCH-4):** a *small* local model on the gaming-PC GPU (GTX 1070 8 GB) is approved as a **free experiment**, narration first, gated by the quality benchmark (NX-292) and auto-disabled if stream quality suffers. Nothing depends on it, and the rules above apply to it unchanged (it is just another `LlmClient` provider, running in the isolated LLM container, Q-AI-3).
- All LLM + cloud TTS spend is under a **$20/month hard cap** with an automatic cutoff and an alert at 80% (Q-AI-5).

## Consequences
Testable, cheap, and replayable. The LLM adds flavor and *apparent* intelligence without being on the critical path. If it turns out the LLM adds nothing measurable, we can remove it without changing gameplay.
