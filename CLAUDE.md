# CLAUDE.md

@AGENTS.md

Claude-specific notes (keep this file short; it loads every session):
- Before starting, load the role card from `.agents/roles/` that matches your task.
- Run the `security-review` skill on any change that touches chat ingestion, identity/linking, the LLM gateway, or CI workflows.
- Run `code-review` before declaring a PR ready. Optional deeper passes: `finecomb`, `review-council`, `/ponytail-review`.
- Agent tooling (MCP servers, plugins, hooks): see `docs/agentic/TOOLING.md`.
