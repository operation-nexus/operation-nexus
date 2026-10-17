# .agents/

Shared material for AI coding agents. `AGENTS.md` at the repo root is the entry point; this folder holds the detail.

| Folder | Contents |
|---|---|
| `roles/` | Role cards: scope, must-read docs, checklists, and hard "never" rules for each kind of agent task. |
| `prompts/` | Reusable task prompts (implement a tracker item, review a PR, write a spec, run a balance study). |
| `context/` | **Owner drop zone.** Reference files, screenshots, sketches, exports. Agents read these but never edit them. |

Conventions:
- Files in `context/` are named `YYYY-MM-DD-short-topic.ext`. Add a one-line entry to `context/INDEX.md` when you add one.
- A role card never overrides `AGENTS.md`, a spec, or an ADR. When they conflict, stop and ask.
