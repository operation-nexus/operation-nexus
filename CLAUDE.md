# CLAUDE.md

Read and follow [`AGENTS.md`](AGENTS.md). It is the single source of instructions for all agents in this repo.

Claude-specific notes:
- Load the role card from `.agents/roles/` that matches your task before starting.
- Use the `security-review` skill on any change that touches chat ingestion, identity/linking, the LLM gateway, or CI workflows.
- Use the `code-review` skill before declaring a PR ready.
