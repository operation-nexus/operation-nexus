# Agentic Coding Setup

Goal: agents that stay **grounded** (no hallucinated APIs or data), **cheap** (load only the context they need), and **safe** (no access to secrets, guarded edits).
Facts here were verified on 2026-10-17 against the cited sources. Anything marked [UNVERIFIED] wasn't.

## 1. What's committed in this repo (applies to everyone)

| File | Purpose |
|---|---|
| `AGENTS.md` | Tool-agnostic instructions (Codex, Gemini, Cursor, Claude). Kept under ~200 lines. |
| `CLAUDE.md` | Imports AGENTS.md with `@AGENTS.md`. Claude Code reads AGENTS.md on its own only when no CLAUDE.md exists ([docs](https://code.claude.com/docs/en/memory)). |
| `.claude/settings.json` | Deny reads of `.env*` (any directory) and `*.pem`/`*.key`. PreToolUse guard hook. Ponytail marketplace and plugin. |
| `.claude/hooks/protect-files.sh` | Blocks agent writes (Edit/Write/MultiEdit/NotebookEdit) to `.env*` anywhere and to the raw source files. Uses `jq`, or `python3` if jq is absent. Fails closed: if neither exists, edits are blocked. It can't see shell redirection (`echo > .env`), so the deny rules and review remain the backstop. |
| `.claude/agents/` | Subagents: `reviewer` and `fact-checker` (enforces DATA-INTEGRITY). |
| `.mcp.json` | Context7 (remote, no key), for up-to-date library docs so agents don't guess APIs. |
| `.agents/` | Role cards, rules (`rules/code-quality.md`), skills (`skills/`), reusable prompts, and the owner's context drop zone. |
| `.serena/project.yml` | Serena project config (languages: python, typescript, bash). `cache/` and `project.local.yml` are ignored by `.serena/.gitignore`. |
| `scripts/` | `check_commit_msg.py` (Conventional Commits, no AI trailer) and `check_tracked_files.py` (no ignored, recorded or oversized files), with tests in `scripts/tests/`. Wiring them into pre-commit and CI belongs with NX-011. |

Notes:
- Project `allow` rules and `extraKnownMarketplaces` take effect only after you trust the folder. `deny` rules apply immediately ([settings docs](https://code.claude.com/docs/en/settings)).
- **Cloud and non-interactive sessions load `.mcp.json` servers without asking** ([MCP docs](https://code.claude.com/docs/en/mcp)). Only add servers here that are safe and work everywhere.
- Enabling an external plugin in project settings doesn't install it for each person automatically. Each person accepts it once.

## 2. Plugins and skills

| Tool | Use it for | Where it comes from |
|---|---|---|
| `code-review` (built-in) | Correctness review of diffs | Claude Code |
| `security-review` (built-in) | Security review of pending changes | Claude Code |
| `simplify` (built-in) | Cleanup and simplification pass | Claude Code |
| **Ponytail** (`/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`) | Smallest complete change; YAGNI; reviews for over-engineering | `DietrichGebert/ponytail` (MIT), declared in `.claude/settings.json` |
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

**Review stack, in order:**
1. `code-review`
2. `security-review` (paths in CLAUDE.md)
3. `/ponytail-review` (over-engineering)
4. `fact-checker` subagent (docs and external facts)
5. Optionally `finecomb` or `review-council` for phase-gate reviews

## 3. MCP servers ("memory graph" and context)

### Recommended now
| Server | Why | Scope | Setup |
|---|---|---|---|
| **Context7** | Current library docs, so agents don't hallucinate APIs | Project (`.mcp.json`) | Committed. Works without a key at low rate limits. Optionally set your own key later via a user-scope entry. In cloud sessions the environment's network policy currently blocks it (proxy 403, seen 2026-10-17), so it only works on desktop unless the cloud environment's allowed hosts are changed. Privacy: Context7 stores the search queries the agent sends, not your code ([privacy](https://context7.com/docs/security/data-privacy)). Docs are community-sourced, so treat them as a pointer, not truth. |
| **Serena** | LSP-backed symbol search, references and edits. Answers come from a real language server, which is the most grounded and token-efficient way to navigate code. | **User scope on your desktop**, not committed (it needs a local install, and cloud sessions would fail to start it) | `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` ([Serena client docs](https://github.com/oraios/serena/blob/main/docs/02-usage/030_clients.md)). Install Serena per its README first. The README warns against installing it via a plugin marketplace. License is GPL-3.0 for the app, which is fine for local use. Mac (2026-10-17): installed as a `uv` tool (`serena-agent` 2.0.0), `serena init` run, registered with the command above, `claude mcp list` shows it connected. On first use in a repo Serena writes `.serena/` there; `project.yml` is committed. Its web dashboard opens a browser tab on every start (`web_dashboard_open_on_launch` in `~/.serena/serena_config.yml`; set `false` to stop it). |

### Evaluate at P1, once real code exists (NX-045 spike)
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
3. Path-scoped rules (`.claude/rules/` with `paths:` frontmatter) are added when code directories exist (NX-025), so sim rules load only when touching `services/sim/**`.
4. Use subagents (Explore, reviewer, fact-checker) for broad searches so their file dumps stay out of the main context.
5. One tracker item per session or PR, then a fresh context.
6. Serena symbol lookups beat reading whole files.

## 5. Owner setup checklist (desktop)
Done on the Mac on 2026-10-17 where checked. Repeat every item on the Windows PC.

- [x] Install `jq` (the guard hook needs it)
- [x] Put the `claude` CLI on PATH (the desktop app does not): run `claude install stable` from the app's bundled binary, or the native installer from the Claude Code docs. It installs to `~/.local/bin/claude` and updates itself.
- [ ] Open the repo in Claude Code and trust the folder. Accept the Ponytail plugin. Approve the Context7 MCP (the desktop app has it; the `claude` CLI still shows it pending until approved there once).
- [x] Install Serena and run the user-scope `claude mcp add` command above. Check it with `/mcp` or `claude mcp list`.
- [ ] Enable finecomb and review-council from the plugin card in chat
- [ ] Ponytail: leave `webhookUrl` empty
