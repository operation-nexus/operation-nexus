# Decided questions: Q-AI

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## AI / LLM / TTS

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-AI-1 | Does an LLM *decide* enemy moves? | **No.** A rule-based director decides. An optional LLM *advisor* picks among valid rule options and writes flavor text. All LLM outputs are recorded. | ✅ 2026-10-17: Accepted via ADR-0007: rules decide; LLM advises and narrates only |
| Q-AI-2 | When does the natural-language `!order` ship? | Phase P4, own unit only, 1 per minute per user, with a budget cap. | ✅ 2026-10-17: A, after the core game is established (P4). Build a complete **intent and command catalog** first: the parser maps natural language onto that catalog only. Own unit only, 1/min per user, budget cap. Players get guidance (`!order help`, examples on screen). |
| Q-AI-3 | Which LLM provider? Use LiteLLM? | Call one provider's SDK directly behind our own small interface. Avoid LiteLLM given the March 2026 compromise, unless it's hash-pinned and isolated. | ✅ 2026-10-17: A, official provider SDKs called directly behind our `LlmClient` port (ADR-0010); no LiteLLM. **And regardless of library, all LLM code runs in its own isolated container**: no platform or stream credentials, egress allowlisted to the provider endpoints, read-only filesystem, non-root, resource limits. Revisit standards-based options for agnosticism (e.g. OpenAI-compatible endpoints) only via our own port. |
| Q-AI-4 | TTS engine for the MVP? | **Piper** (piper1-gpl, run as a separate process. GPL is fine for server-side use) **or Kokoro** (Apache-2.0, pending verification). Pick after a 1-day listening test. | ✅ 2026-10-17: A, local Piper or Kokoro picked by a listening test; engines stay interchangeable via the `TtsEngine` port (ADR-0010) so cloud voices can be added later |
| Q-AI-5 | Monthly LLM + TTS budget? (Cost analysis: [LOCAL-VS-API-COST](../ops/LOCAL-VS-API-COST.md)) | $20/month hard cap with a circuit breaker. | ✅ 2026-10-17: A, $20/month hard cap on LLM + cloud TTS, with an automatic cutoff (circuit breaker). Over cap → rules + template lines (FB-2/FB-3). Alert at 80%. |

## Admin/RBAC and support redemptions (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-AI-6 | Disclose on stream that voices are AI-generated? | Yes. A small "Synthetic voices" note in the channel panel and the about screen. Honest, and it matches DATA-INTEGRITY DI-5. Twitch policy still to check. | ✅ 2026-10-17: A, disclose AI voices (channel panel + about screen). Follow each platform's AI-content disclosure rules and **re-check them every phase gate** (NX-288). Gemini designed voices pre-record common lines. **Human voice option:** the owner may voice-act lines and, if the community prefers, run voice-actor auditions (written consent + license per contributor; SEC-MOD-4). |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-AI-7 | Can mastermind taunts name individual operators? Template-only before P4? | template-only; never name a person | ✅ 2026-10-18: Yes, via code-filled {target} placeholder with the approved callsign only; the LLM (P4+) never sees names or chat text (SEC-LLM-4). Pre-P4 taunts are template-only. Per-operator naming cooldown taunt.name_cooldown_min (proposed default 10) is reduced for spotlight operators (recent hero events / high recent action) down to taunt.name_cooldown_spotlight_min (proposed default 5); both admin-configurable. Opt-out via !quiet. Tone: playful rivalry, never insults about the person. |
| Q-AI-8 | Can a GM help the coalition, or only drive the Static? | Static + world events only (TS-1) | ✅ 2026-10-18: GM drives the Static and triggers world events (TS-1) only. World events may benefit the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction; no direct grants of units, ammo or XP to specific players. Every GM action is logged and flagged in replays. |
| Q-AI-9 | Which redemptions add to `provocation`? | only those with a gameplay effect | ✅ 2026-10-18: Every redemption type carries its own provocation weight (director.provocation.weights.redemption.<type>, admin-tunable). Classes: offensive (airstrike, barrage) = full weight; support (supply drop, repair, reinforcements) = small weight; cosmetic (color, ping, shoutout) = 0. Weight values are PROPOSED / TBD by balance harness. |

## Research-session batch (2026-10-18)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-AI-10 | Budget and runtime separation for content-time agent teams | PROPOSED: separate monthly budget from the runtime LLM cap ($20/month, isolated gateway); the lore/marketing teams run as scheduled tasks with a per-run draft limit and never hold platform credentials. Amount TBD by the owner. | P3 | ✅ 2026-10-18: Separate content-time cap of **$20/month**, apart from the runtime gateway cap; review after the first month's real usage. Cheaper model tiers draft and format, the strongest tier does continuity, red-team and style review (Q-MKT-14). |
