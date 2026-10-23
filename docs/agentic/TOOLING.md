# Agentic Coding Setup

Goal: agents that stay **grounded** (no hallucinated APIs or data), **cheap** (load only the context they need), and **safe** (no access to secrets, guarded edits).
Facts here were verified on 2026-10-17 against the cited sources. Anything marked [UNVERIFIED] wasn't.

## 1. What's committed in this repo (applies to everyone)

| File | Purpose |
|---|---|
| `AGENTS.md` | Tool-agnostic instructions (Codex, Gemini, Cursor, Claude). Kept under ~200 lines. |
| `CLAUDE.md` | Imports AGENTS.md with `@AGENTS.md`. Claude Code reads AGENTS.md on its own only when no CLAUDE.md exists ([docs](https://code.claude.com/docs/en/memory)). |
| `.claude/settings.json` | Deny reads of `.env*` (any directory) and `*.pem`/`*.key`. PreToolUse guard hook, SessionStart bootstrap hook. Ponytail marketplace and plugin. |
| `.claude/hooks/session-start.sh` | Cloud sessions only (`CLAUDE_CODE_REMOTE=true`): runs `make bootstrap` so `make check` works from a fresh clone, and prints the result into context. Never blocks the session. Desktop: run `make bootstrap check` once after cloning (NX-025). |
| `.claude/rules/` | Path-scoped rules (`paths:` frontmatter) that load only when an agent reads or edits matching files: kernel, contracts, apps. Each points to the role card or checklist instead of repeating it. |
| `.claude/hooks/protect-files.sh` | Blocks agent writes (Edit/Write/MultiEdit/NotebookEdit) to `.env*` anywhere and to the raw source files. Uses `jq`, or `python3` if jq is absent. Fails closed: if neither exists, edits are blocked. It can't see shell redirection (`echo > .env`), so the deny rules and review remain the backstop. |
| Agent GitHub identity | Agents (desktop `gh`/git, cloud sessions, the daily routine) act as `canthony224`: write role, not a code owner, not a ruleset bypass actor. The owner acts as `SaltySeraphCodes` (code owner, bypass) and approves agent PRs that touch CODEOWNERS paths; auto-merge then lands them (Q-DEV-16, NX-365). Desktop: `gh auth switch -u canthony224` plus repo-local `git config user.name`/`user.email`; cloud and routines: `/web-setup` or claude.ai/customize/connectors. |
| `.claude/agents/` | Subagents: `reviewer`, `fact-checker` (enforces DATA-INTEGRITY), and the build loop's `coder` and `qa` (Sonnet; `.claude/skills/build-loop`). |
| `.mcp.json` | Context7 (remote, no key), for up-to-date library docs so agents don't guess APIs. |
| `.agents/` | Role cards, rules (`rules/code-quality.md`), reusable prompts, and the owner's context drop zone. |
| `.claude/skills/` | Project skills: ours plus a pinned, MIT-licensed copy of selected `mattpocock/skills` (index and local changes: `VENDORED.md`). |
| `.serena/project.yml` | Serena project config (languages: python, typescript, bash). `cache/` and `project.local.yml` are ignored by `.serena/.gitignore`. |
| `scripts/` | `check_commit_msg.py` (Conventional Commits, no AI trailer) and `check_tracked_files.py` (no ignored, recorded or oversized files), with tests in `scripts/tests/`. `make check` and the CI `python-test` job run those tests; the CI `pr-hygiene` workflow also runs `check_commit_msg.py` on the PR title and every PR commit (NX-017). `check_tracked_files.py` is not run in CI or in pre-commit, and `.pre-commit-config.yaml` has no commit-msg hook. |

Notes:
- Project `allow` rules and `extraKnownMarketplaces` take effect only after you trust the folder. `deny` rules apply immediately ([settings docs](https://code.claude.com/docs/en/settings)).
- **Cloud and non-interactive sessions load `.mcp.json` servers without asking** ([MCP docs](https://code.claude.com/docs/en/mcp)). Only add servers here that are safe and work everywhere.
- Enabling an external plugin in project settings doesn't install it for each person automatically. Each person accepts it once.
- **Daily owner check** (a claude.ai cloud routine, 07:59 America/New_York, not in this repo): handles owner comments and Dependabot PRs, logs to issue #119. From NX-363/NX-364 it also triages `error` tickets (ERROR-PIPELINE EP-6), runs `/ponytail-debt` on Mondays and `/ponytail-audit` on the 1st of the month (and every phase gate runs `/ponytail-audit` too), and sends code changes through `build-loop` QA (Q-DEV-6, Q-DEV-11). Its prompt is edited in the claude.ai routine settings; keep this line in step.

## 2. Plugins and skills

| Tool | Use it for | Where it comes from |
|---|---|---|
| `code-review` (built-in) | Correctness review of diffs | Claude Code |
| `security-review` (built-in) | Security review of pending changes | Claude Code |
| `simplify` (built-in) | Cleanup and simplification pass | Claude Code |
| **Ponytail** (`/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`) | Smallest complete change; YAGNI; reviews for over-engineering | Skills vendored in `.claude/skills/` at v5.3.2 so cloud sessions have them (Q-DEV-18); the `DietrichGebert/ponytail` plugin (MIT) stays declared in `.claude/settings.json` for desktop extras |
| **CodeRabbit** | Automatic PR review (GitHub app, installed on the `operation-nexus` org by the owner 2026-10-20, 14-day trial to about 2026-11-03; then $30 a month (Essentials), not renewed by default, Q-CI-7, docs/ops/COSTS.md). It reviews each code PR by itself, quietly: `.coderabbit.yaml` turns off summaries, status messages and poems, skips drafts and Dependabot, and skips docs, Markdown, generated code and lockfiles, which the reviewer agent and CI cover. Add `[skip review]` to a PR title to skip it. Reply `@coderabbitai …` in a PR comment to ask it something. Its comments reach the lead through the CI watch like any review | GitHub app (no Claude plugin needed) |
| **Claude review action** | Automatic PR review on GitHub (Q-CI-7, NX-029): `.github/workflows/claude-review.yml` runs the Claude Code GitHub Action with the code-review plugin on PRs into `develop` that touch sensitive paths (CI workflows, chat gateway, deploy, scripts, identity, linking, LLM code), and on any PR when the `ai-review` label is added. Inline comments, advice only, never a required check. Runs on the owner's Claude plan via the `CLAUDE_CODE_OAUTH_TOKEN` secret; skips PRs it already commented on. Its comments reach the lead through the CI watch like any review | `anthropics/claude-code-action`, pinned by SHA |
| **playwright** (Microsoft) | Browser automation for QA of the overlay, site and Command Center | claude.ai plugin directory |
| **sentry** | Reads Sentry issues for the error pipeline (ERROR-PIPELINE) | claude.ai plugin directory, once a Sentry project exists |
| **finecomb** | Exhaustive code and security audit checklist | claude.ai plugin directory (install via the card in chat) |
| **claude-code-review-council** | Six-specialist PR review | claude.ai plugin directory |
| `qa-bug-hunter` | Read-only bug hunts with reproduction | Already available in this account |
| `session-start-hook` | Set up cloud sessions so tests and linters run (NX-025) | Already available |

**Ponytail audit (2026-10-17, commit `16352ac`):**
- License: MIT.
- Hooks run Node on SessionStart, SubagentStart and UserPromptSubmit. They inject instructions and a ≤2,000-character codebase map.
- It writes a local usage ledger to `~/.config/ponytail/band/`.
- The only network call is an **optional webhook, which is empty (off) by default**. Keep it off.
- Overlap with our rules: Ponytail's "no unrequested abstraction / no 'for later' code" reinforces AGENTS.md rule 7 and DATA-INTEGRITY. Our specs still win: Ponytail must not cut validation, tests or security (its own rule says the same).

**Vendored from `mattpocock/skills`** (2026-10-17, commit `49dd158`, MIT): `grill-me`, `grill-with-docs`, `grilling`, `domain-modeling`, `wait-what`, `handoff`, `to-questionnaire`. Reviewed line by line before copying; no scripts, hooks or network calls. Copied rather than installed as a plugin so the text is pinned and cloud sessions get it.

Not vendored yet. Each needs adapting first, or clashes with something here:

| Skill | Why it could help | Why not yet |
|---|---|---|
| `to-spec`, `to-tickets` | Turn a grill session into a spec and tracer-bullet tickets | They publish to GitHub Issues with their own templates and `ready-for-agent` labels; ours are `docs/specs/_TEMPLATE.md`, NX IDs and `.github/labels.yml`. Adapt, then run `setup-matt-pocock-skills`' config by hand (`docs/agents/`). |
| `tdd`, `diagnosing-bugs`, `codebase-design`, `prototype` | Implementation discipline (red-green slices, bug loops, deep modules, throwaway prototypes) | Code exists now; not adopted yet. `prototype` shadows a Claude Code built-in name. |
| `implement`, `implement-spec` | Drive a spec to done with subagents | They call upstream `/code-review` and `/tdd`; our `code-review` is the built-in. |
| `code-review`, `research` | Standards + spec two-axis review; cited research notes | Same names as Claude Code built-ins we already use. Would need renaming. |
| `writing-for-agents` | How to write AGENTS.md, rules and skills compactly | Useful now; model-invoked, so it would load whenever docs for agents are edited. |
| `wayfinder`, `triage`, `retro`, `pr`, `wizard` | Big-plan decision maps, issue triage, session retros, PR bodies, human-steps bash wizards | Overlap with TRACKER/OPEN-QUESTIONS and the PR template; `wizard` could fit owner setup steps later. |

**Review stack, in order:**
1. `code-review`
2. `security-review` (paths in CLAUDE.md)
3. `/ponytail-review` (over-engineering)
4. `fact-checker` subagent (docs and external facts)
5. Optionally `finecomb` or `review-council` for phase-gate reviews

On GitHub, after the PR opens: the Claude review action (sensitive paths, or the `ai-review` label) and CodeRabbit while it is subscribed (Q-CI-7).

## 3. MCP servers ("memory graph" and context)

### Recommended now
| Server | Why | Scope | Setup |
|---|---|---|---|
| **Context7** | Current library docs, so agents don't hallucinate APIs | Project (`.mcp.json`) | Committed. Works without a key at low rate limits. Optionally set your own key later via a user-scope entry. In cloud sessions the environment's network policy currently blocks it (proxy 403, seen 2026-10-17), so it only works on desktop unless the cloud environment's allowed hosts are changed. Privacy: Context7 stores the search queries the agent sends, not your code ([privacy](https://context7.com/docs/security/data-privacy)). Docs are community-sourced, so treat them as a pointer, not truth. |
| **Serena** | LSP-backed symbol search, references and edits. Answers come from a real language server, which is the most grounded and token-efficient way to navigate code. | **User scope on your desktop**, not committed (it needs a local install, and cloud sessions would fail to start it) | `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` ([Serena client docs](https://github.com/oraios/serena/blob/main/docs/02-usage/030_clients.md)). Install Serena per its README first. The README warns against installing it via a plugin marketplace. License is GPL-3.0 for the app, which is fine for local use. Mac (2026-10-17): installed as a `uv` tool (`serena-agent` 2.0.0), `serena init` run, registered with the command above, `claude mcp list` shows it connected. On first use in a repo Serena writes `.serena/` there; `project.yml` is committed. Its web dashboard opens a browser tab on every start (`web_dashboard_open_on_launch` in `~/.serena/serena_config.yml`; set `false` to stop it). |

### Evaluate once real code exists (NX-045 spike, code exists and the spike is unblocked)
A code **knowledge graph** (calls, imports, inheritance) only pays off once there is code to index. Candidates:

| Server | Storage | License | Notes |
|---|---|---|---|
| CodeGraphContext | FalkorDB Lite (default) / KuzuDB / Neo4j | MIT | Tree-sitter, 23 languages. Vendor claims ~62% fewer response tokens with its opt-in output format. Default 4 GiB buffer pool. |
| codebase-memory-mcp | SQLite in `~/.cache` | MIT | Tree-sitter + type resolution. An arXiv preprint measured 10× fewer tokens but lower answer quality (83% vs 92%) than reading files. Installed via `curl \| bash`, so review the script first. |

The spike measures tokens per task and answer accuracy on 10 real questions about our code, with vs without the graph. Adopt only if the numbers say so.

### Not recommended
- `@modelcontextprotocol/server-memory`: a hand-curated JSONL knowledge graph. LLM-written "facts" go stale or wrong (memory poisoning) and bypass review. **Our memory is the repo instead:** ADRs, specs, GLOSSARY and OPEN-QUESTIONS are reviewed in PRs and versioned. That's the anti-hallucination choice.
- GitNexus: PolyForm **Noncommercial** license, which conflicts with a possibly monetized stream.

## 4. Token-efficiency practices
1. CLAUDE.md and AGENTS.md stay short and link to specs instead of inlining them. (Imports still load at launch, so link instead of `@`-importing big docs.)
2. Role cards and specs are read on demand, per task.
3. Path-scoped rules (`.claude/rules/` with `paths:` frontmatter, NX-025) load only when an agent touches matching files, so kernel rules stay out of overlay work.
4. Use subagents (Explore, reviewer, fact-checker) for broad searches so their file dumps stay out of the main context.
5. One tracker item per session or PR, then a fresh context.
6. Serena symbol lookups beat reading whole files.

## 5. Owner setup checklist (desktop)
Mac: all done (2026-10-17; review plugins and Node 22 confirmed by the owner 2026-10-22). Windows PC: done 2026-10-22 in a WSL2 distro (Ubuntu; repo cloned inside the Linux home, Claude desktop app pointed at the distro): `claude mcp list` from the repo shows serena and context7 connected. Plugins (Ponytail, finecomb, review-council) are not available in WSL sessions per the [desktop docs](https://code.claude.com/docs/en/desktop.md), so they apply on the Mac and in Windows-native sessions only; in WSL, run `claude mcp add` in a WSL terminal and approve project MCP servers from the repo folder. The owner ticks progress in
[OWNER-TODO §1](../planning/OWNER-TODO.md); keep the two lists in step.

- [x] Install `jq` (the guard hook needs it)
- [x] Node 22 first on PATH. `.node-version` pins the major; CI reads it and `make bootstrap` / `make check` stop with an error on any other major (an older Node 20 in `/usr/local/bin` once broke vitest silently). On macOS: `brew install node@22`. It is keg-only, so add `export PATH="/opt/homebrew/opt/node@22/bin:$PATH"` to `~/.zshrc`, or use a version manager that reads `.node-version`. Then delete `apps/overlay/node_modules` and run `make bootstrap`, since native bindings are built for the Node that installed them. Python needs nothing: uv reads `services/sim/.python-version` (3.12) and fetches it if missing.
- [x] Put the `claude` CLI on PATH (the desktop app does not): run `claude install stable` from the app's bundled binary, or the native installer from the Claude Code docs. It installs to `~/.local/bin/claude` and updates itself.
- [x] Open the repo in Claude Code and trust the folder. Accept the Ponytail plugin. Approve the Context7 MCP (the desktop app has it; the `claude` CLI still shows it pending until approved there once).
- [x] Install Serena and run the user-scope `claude mcp add` command above. Check it with `/mcp` or `claude mcp list`.
- [x] Enable finecomb and review-council from the plugin card in chat
- [x] Ponytail: leave `webhookUrl` empty
