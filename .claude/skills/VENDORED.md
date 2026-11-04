# Skills in this folder

Claude Code loads every `<name>/SKILL.md` here as a project skill (desktop and cloud sessions). Other agents read them
by path from `AGENTS.md` §7.

## Ours

| Skill | Use |
|---|---|
| `build-loop` | Any code change: coder → QA → lead review → PR or owner (Q-DEV-1) |
| `coding-safeguards` | Before refactoring, renaming or moving code across files |
| `frontend-design` | Before any new visual surface (overlay layer, site page, Command Center screen) |
| `add-config-key` | Adding, renaming or retiring a balance key with its registry metadata (NX-390) |
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


## Vendored from vercel-labs (web-design-guidelines)

Sources, both pinned:
- Skill wrapper: https://github.com/vercel-labs/agent-skills, `skills/web-design-guidelines`, at commit `1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62` (2026-10-27).
- Rules: https://github.com/vercel-labs/web-interface-guidelines, `command.md`, at commit `434b7f91364665f2f733b310ec54809bf8f37937` (2026-10-05).

License: MIT, copyright Vercel Labs (`LICENSE-web-interface-guidelines`, copied from the rules repo). `vercel-labs/agent-skills` has no LICENSE file; its README says only "MIT" (no copyright holder). So the wrapper `SKILL.md` was rewritten by us (same name, description and purpose, about 25 lines) rather than copied; the rules text is copied from the repo that has a LICENSE file. Copied, not installed as a plugin, so cloud sessions get it. Reviewed line by line; Markdown only. Left out: the rest of `agent-skills` (other skills, zips, scripts) and the rules repo's `README.md`, `AGENTS.md` (a different MUST/SHOULD rewrite of the same guidelines), `install.sh`.

| Skill | Invoked by | Local changes |
|---|---|---|
| `web-design-guidelines` | model or user (`/web-design-guidelines <file-or-pattern>`) | `SKILL.md` no longer tells the agent to fetch the rules from `raw.githubusercontent.com` at review time (no WebFetch): it reads the pinned `guidelines.md` (byte-identical to upstream `command.md`, renamed). Added a section saying OVERLAY and the role card win and which rules to skip for a Canvas2D/no-framework overlay |

## Vendored from emilkowalski/skills

Source: https://github.com/emilkowalski/skills at commit `c8a79627b59d72d764d6ab6f2c87c09a48169833` (2026-11-04), `skills/emil-design-eng`.
License: MIT, copyright Emil Kowalski (`LICENSE-emilkowalski-skills`). The repo README is signed by Emil Kowalski and the LICENSE names him. Copied, not installed as a plugin, so cloud sessions get it. Reviewed line by line; one Markdown file, no scripts or network calls. Left out: the repo's other 17 skills (`animate`, `review-animations`, `break-ui`, `prototype` and so on; `prototype` is on the not-vendored list in `docs/agentic/TOOLING.md` §2 because it shadows a Claude Code built-in), cheatsheets and README.

| Skill | Invoked by | Local changes |
|---|---|---|
| `emil-design-eng` | model or user (`/emil-design-eng`) | Added an Operation Nexus note (OVERLAY and OBS/1080p win; React/Motion snippets are illustrations, no new dependencies). The "reply only with this line when first invoked" rule now applies only when the user types the command with no task. The pointer to the easing.dev and easings.co sites was replaced by a plain sentence |

## Vendored from Nutlope/hallmark

Source: https://github.com/Nutlope/hallmark at commit `de4999e0cd7a7a41df0b4e6903fa02fe9f1492a8` (2026-11-04), `skills/hallmark`, v2.0.0 (package.json). Not `batureren/hallmark`.
License: MIT, copyright "Hallmark contributors" (`LICENSE-hallmark`; the same file ships inside the skill upstream). Copied, not installed as a plugin, so cloud sessions get it. Markdown and the theme `index.json` only (99 files, 832 KB: `SKILL.md`, `references/` including 21 macrostructures, 4 genres and the theme files).

Left out, and why:
- `scripts/` (sloplint, theme dealer/scaffold/photo picker, capture, imagegen, installers, hook): JavaScript, not copied by policy. The skill is built around them (Steps 3, 6 and 7 call them), so this copy runs in a degraded manual mode; a `SKILL.md` block says what to do by hand. `scripts/photos.json` (the 755-photo library, 453 KB) and the theme `.jpg` pictures (about 5 MB) too.
- `agents/openai.yaml` (Codex manifest), the repo's `site/`, `eval/`, `docs/`, `package.json`.
- `references/comp.md` (calls the Together AI image API with `TOGETHER_API_KEY`) and `references/brand-truth.md` (tells the agent to fetch a brand's homepage and CSS).
- `references/themes/README.md` (how to author a theme with the validator script).

Memory log: upstream writes `.hallmark/log.json` (plus `brand-spec.md`, `preflight.json`, `before/`, `compare.html`) relative to the project root, a hidden folder not covered by our hygiene. All paths were rewritten to `docs/design/hallmark/`; only `log.json` and `brand-spec.md` are meant to be committed, the rest goes to the session scratchpad. Nothing is written to `$HOME` or `$TMPDIR` by the Markdown (the upstream installers wrote to `~/.claude`, `~/.codex` and `~/.config/opencode`; they are not copied).

| Skill | Invoked by | Local changes |
|---|---|---|
| `hallmark` | model or user (`/hallmark <prompt>`, `redesign <path>`, `audit <path>`) | Adaptation block at the top of `SKILL.md` (repo rules and OVERLAY win; no scripts, outside calls or installs; log location; bundled fonts only despite the Google Fonts links in theme files). `flow.md`: removed the signal 8 (Inspo MCP), edit-time hook, comp-before-build and harness-table sections and the "start the product and install its lockfile" step. `imagery.md`: §2 (photo library), §4 capture command and §6 (generated stills) replaced with repo-safe text. `redesign.md`: banner. `.hallmark/` paths rewritten as above |

