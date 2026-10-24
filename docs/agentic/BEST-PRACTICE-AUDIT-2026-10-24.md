# Best-practice audit: shanraisshan/claude-code-best-practice, 2026-10-24 (NX-414)

Two passes over [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) (MIT, a docs repo with example `.claude/` files, not a plugin), compared with our setup. Its text was read as data. Claude Code facts were checked against code.claude.com (hooks, skills, sub-agents, settings, permission modes, cloud environments) on 2026-10-24; anything not confirmed there is marked [UNVERIFIED]. Nothing was copied from the repo.

## Done in NX-414
| Item | Where |
|---|---|
| `ruff format` after each Python write under `services/sim` and `tools/` (PostToolUse; never blocks) | `.claude/hooks/format-python.sh`, `scripts/tests` |
| One coder per item, compact at a boundary, a handoff issue at the end of a stretch | build-loop §4a |
| Gotchas from real failures | build-loop §2, add-config-key, new-operation |
| Settings-loaded check at the start of a brief; owner steps for cloud sessions | build-loop §1, OWNER-TODO §4f, TOOLING |
| Built-in Explore and Plan agents off (`CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS`) so lookups go to `searcher` | `.claude/settings.json` |
| `qa.md` no longer says subagents can't start agents (they can, up to three layers) | `.claude/agents/qa.md` |
| `/grill-with-docs` is user-only; the lead asks the owner to type it | build-loop §3 |

**The main finding:** a cloud session with more than one repository reads only `enabledPlugins` and `extraKnownMarketplaces` from `.claude/settings.json` ([settings docs](https://code.claude.com/docs/en/settings), "Settings in cloud sessions"). The 2026-10-24 session had all three repos: `CLAUDE_CODE_SUBAGENT_MODEL` and `CLAUDE_PROJECT_DIR` were empty, so hooks, read denies, the subagent model default and bootstrap were all off. Fix: OWNER-TODO §4f (L-19).

## Not done: `context: fork` for heavy skills
The field exists (skills docs), but a forked skill gets only its own text as the prompt, without the conversation, and the heavy reviews (`security-review`, `code-review`, `ponytail-review`) are built-in or plugin skills we don't edit. Running reviews through the `reviewer` or `qa` agents already keeps their reading out of the lead's context.

## Proposed follow-ups (NX-415, one PR each, by value)
1. **`make pre-pr`:** `make check` plus what only CI runs today (sim determinism, `make contracts` drift, overlay build, commit-message lint over `origin/develop..HEAD`, `check_tracked_files.py`, the non-test line count); build-loop §2.6 runs it before a push. A PreToolUse hook on `git push` could run its cheap parts. S-M.
2. **Narrow permission allow rules and force-push denies** in `.claude/settings.json`, from `/fewer-permission-prompts` run on the desktop session. Narrow rules skip the auto-mode classifier; broad ones are dropped. No `ask` rules (they stall unattended runs). Security review needed. S.
3. **`qa` without `Agent`** (or `Agent(searcher)` only), after checking `code-review` still runs inside it [UNVERIFIED]. S.
4. **A SubagentStop check** in `coder.md` and `qa.md` frontmatter hooks: block once (not when `stop_hook_active`) if background tasks are still running, a coder report has no `make check` line, or a QA report has no PASS/FIX. Turns code-quality §9 (NX-382) into a check. S.
5. **SessionStart on `compact|resume`:** print the branch, `git status -s`, commits not pushed (L-13) and the PR's auto-merge state; silent when `gh` fails. S.
6. **Agent frontmatter:** `skills:` preload for `coder` (`coding-safeguards`, `ponytail`); `maxTurns` on `searcher` and `fact-checker`. Small savings. S.
7. **Headless overlay check in cloud:** a `verify-overlay` script with `@playwright/test` (new dependency, rule 8), so overlay changes stop escalating when the Playwright MCP is missing. Whether the cloud network allows the browser download is [UNVERIFIED]. M.
8. **Earlier auto-compact** (`autoCompactWindow`): models with a 1M window compact near 967K tokens by default; a lower window costs less per turn but keeps less context. Owner call: cost against recall.

## Looked at, not worth it here
Agent `memory:` (LESSONS and the repo are the memory); agent teams, RPI, `/batch`, `/goal` and Ralph-style loops (fight one writer per file and minimal pings); broad `Bash(*)` allow and `ask` lists; `autoMode.environment` (user settings only); worktree symlink and sparse settings ([UNVERIFIED], and `.worktreeinclude` would copy `.env`); status line, output styles and other personal UX; API-only features; squash merges and cross-vendor QA (rejected earlier).
