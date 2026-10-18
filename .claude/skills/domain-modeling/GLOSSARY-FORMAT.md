# Glossary format (Operation Nexus)

`docs/planning/GLOSSARY.md` is one table. Add or edit rows; keep the table.

```md
| Term | Meaning |
|---|---|
| Sortie | One unit's life from spawn to RTB or death. _Avoid:_ run, life |
```

## Rules

- **Be opinionated.** When several words exist for one concept, pick the best and list the others after `_Avoid:_`.
- **Keep definitions tight.** One or two sentences. Define what it IS, not what it does.
- **Only project terms.** General programming concepts (timeouts, retries, error types) do not belong, even if the code uses them a lot.
- **Spec and code names follow the glossary.** A rename here is a rename in the specs in the same change (REVIEW-CHECKLIST: names match the glossary).
