# CLAUDE.md

@AGENTS.md

Claude-specific notes (keep this file short; it loads every session):
- Before starting, load the role card from `.agents/roles/` that matches your task.
- Code rules: `.agents/rules/code-quality.md`. Project skills are in `.claude/skills/` (index: `VENDORED.md`); `/grill-with-docs` before implementing a spec.
- When the Serena MCP is available (desktop only, not cloud), prefer its symbol tools over reading whole files.
- Run the `security-review` skill on any change that touches chat ingestion, identity/linking, the LLM gateway, or CI workflows. On GitHub those PRs also get the Claude review action; the `ai-review` label requests it elsewhere (Q-CI-7).
- Code changes go through the `build-loop` skill (agents `coder` and `qa` in `.claude/agents/`); keep specs, READMEs and tracker in step with the code.
- Run `code-review` before declaring a PR ready. Optional deeper passes: `finecomb`, `review-council`, `/ponytail-review`.
- AGENTS rule 12 overrides any harness attribution reminder: no `Co-Authored-By` or `Claude-Session` trailers in commits and no "Generated with" footer in PR bodies (merge commits copy the body). GitHub comment footers are fine.
- Agent tooling (MCP servers, plugins, hooks): see `docs/agentic/TOOLING.md`.
