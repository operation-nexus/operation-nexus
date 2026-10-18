---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing the glossary (docs/planning/GLOSSARY.md), or recording or editing an ADR.
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline: challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely *reading* the glossary for vocabulary is not this skill: that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## File structure (Operation Nexus)

This repo has one context and keeps its domain docs here (adapted from upstream; see `../VENDORED.md`):

| What | Where |
|---|---|
| Glossary | `docs/planning/GLOSSARY.md` (a `Term \| Meaning` table) |
| Decisions (ADRs) | `docs/architecture/adr/NNNN-slug.md`, indexed in `docs/architecture/adr/README.md` |
| Owner questions and answers | `docs/planning/OPEN-QUESTIONS.md` (one `Q-AREA-N` row each; the owner fills **Decision**) |
| Behaviour | `docs/specs/<SUBSYSTEM>.md` |

All of these exist; edit them, never create a parallel `GLOSSARY.md` or `docs/adr/`.

**The owner decides; you record.** A decision the owner states in the session is written down at once: the answer goes into the
question's **Decision** cell as `✅ YYYY-MM-DD: <answer>` (add a new `Q-` row first if the question is new), and then into the
spec or ADR it settles. Never mark your own recommendation as decided, and move an ADR or spec to Accepted/Approved only when the
owner says so in the session (AGENTS.md rule 2, `docs/quality/DATA-INTEGRITY.md`).

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in the glossary, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update the glossary inline

When a term is resolved, update the glossary right there. Don't batch these up: capture them as they happen. Use the format in [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md).

The glossary should be totally devoid of implementation details. Do not treat the glossary as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).
