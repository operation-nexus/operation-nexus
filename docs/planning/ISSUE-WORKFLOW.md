# Issue & Task Workflow (GitHub Issues)

GitHub Issues is the **live** tracker for tasks, bugs and decisions. `docs/planning/TRACKER.md` remains the phase plan and ID index. When an item gets an issue, its row links to that issue (`#12`), and status lives in the issue from then on.

## Structure
| Concept | GitHub feature |
|---|---|
| Tracker item `NX-###` | Issue titled `NX-###: …` (template: *Work item*) |
| Owner decision `Q-…` | Issue titled `Q-…: …` (template: *Decision needed*) |
| Bug | Issue from the *Bug* template |
| Phase P0…P4 | Milestone `P0 Foundations`, `P1 Sim kernel`, … |
| Area | Label `area:sim`, `area:overlay`, `area:gateway`, `area:identity`, `area:director`, `area:ops`, `area:ci`, `area:docs`, `area:security` |
| Type | Label `type:task`, `type:bug`, `type:decision`, `type:spike` |
| Priority | Label `prio:p0` (blocks the phase), `prio:p1`, `prio:p2` |
| Status | Open/closed, plus labels `status:blocked` and `status:needs-owner`; optional GitHub Project board (Todo / In progress / Review / Done) |
| Agent-friendly | Label `agent-ready` = spec approved, acceptance criteria are testable, and no open decisions remain |

Label definitions live in `.github/labels.yml`. They're applied by hand, or by a label-sync action once CI exists (NX-018).

## Rules
1. **One issue per PR** where possible. The PR body says `Closes #N`.
2. Agents only pick up `agent-ready` issues. They comment with their plan before starting, and report only work they actually completed (DATA-INTEGRITY DOC-4).
3. A bug report needs repro steps, expected vs actual behavior, and evidence such as logs, a replay seed, or a screenshot. Never write "probably".
4. Decisions are closed with the answer written in the issue, and the answer is copied into OPEN-QUESTIONS and the relevant spec or ADR.
