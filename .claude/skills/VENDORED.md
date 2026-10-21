# Skills in this folder

Claude Code loads every `<name>/SKILL.md` here as a project skill (desktop and cloud sessions). Other agents read them
by path from `AGENTS.md` §7.

## Ours

| Skill | Use |
|---|---|
| `build-loop` | Any code change: coder → QA → lead review → PR or owner (Q-DEV-1) |
| `coding-safeguards` | Before refactoring, renaming or moving code across files |
| `frontend-design` | Before any new visual surface (overlay layer, site page, Command Center screen) |
| `new-unit` | Adding a new unit or facility kind (catalog entry, no kernel code) |
| `new-operation` | Adding or changing a Threat Director operation (job template in `content/operations.yaml`, no kernel code) |

## Vendored from mattpocock/skills

Source: https://github.com/mattpocock/skills at commit `49dd158d1076134a641b33efb035946536778336` (2026-10-09).
License: MIT, copyright Matt Pocock (`LICENSE-mattpocock-skills`). Copied, not installed as a plugin, so the text is
pinned and reviewed and works in cloud sessions. Update by diffing a newer commit against these files.

| Skill | Invoked by | Local changes |
|---|---|---|
| `grill-me` | user (`/grill-me`) | none |
| `grill-with-docs` | user (`/grill-with-docs`) | none |
| `grilling` | model or user | none |
| `domain-modeling` | model or user | File-structure section rewritten for this repo's glossary, ADR, OPEN-QUESTIONS and spec paths; owner-decides rule added; `ADR-FORMAT.md` points at our template; `GLOSSARY-FORMAT.md` rewritten for our table |
| `wait-what` | user | glossary path |
| `handoff` | user | none (writes to `$TMPDIR`, so a desktop handoff is not visible to a cloud session) |
| `to-questionnaire` | user | writes to `docs/review/QUESTIONNAIRE-<slug>.md` instead of the working directory |

Not vendored yet, and why: see `docs/agentic/TOOLING.md` §2.

## Vendored from DietrichGebert/ponytail

Source: https://github.com/DietrichGebert/ponytail at tag `v5.3.2`, commit `16352ac229eb08a9598dcae48fe9f2b342567d86` (2026-10-20).
License: MIT, copyright DietrichGebert (`LICENSE-ponytail`). Copied so cloud sessions get it: cloud sessions don't install
plugins a repo enables in `.claude/settings.json` (Q-DEV-18). Reviewed line by line; Markdown only. Left out: the plugin's
JavaScript hooks (always-on mode, status band), `ponytail-help` and `ponytail-gain` (plugin and benchmark text). On the
desktop the plugin can stay installed; its skills are namespaced `ponytail:…`, so names don't clash. Update by diffing a
newer tag against these files.

| Skill | Invoked by | Local changes |
|---|---|---|
| `ponytail` | model or user (`/ponytail`) | none |
| `ponytail-review` | model or user (`/ponytail-review`) | none |
| `ponytail-audit` | model or user (`/ponytail-audit`) | none |
| `ponytail-debt` | model or user (`/ponytail-debt`) | none |

