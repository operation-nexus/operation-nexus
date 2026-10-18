# CLAUDE.md

@AGENTS.md

Claude-specific notes (keep this file short; it loads every session):
- Before starting, load the role card from `.agents/roles/` that matches your task.
- Code rules: `.agents/rules/code-quality.md`. Project skills are in `.claude/skills/` (index: `VENDORED.md`); `/grill-with-docs` before implementing a spec.
- When the Serena MCP is available (desktop only, not cloud), prefer its symbol tools over reading whole files.
- Run the `security-review` skill on any change that touches chat ingestion, identity/linking, the LLM gateway, or CI workflows.
- Run `code-review` before declaring a PR ready. Optional deeper passes: `finecomb`, `review-council`, `/ponytail-review`.
- Agent tooling (MCP servers, plugins, hooks): see `docs/agentic/TOOLING.md`.
