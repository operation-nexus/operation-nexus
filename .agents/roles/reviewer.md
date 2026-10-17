# Role: Reviewer (code + security)

**Use for:** reviewing any PR before it's marked ready.

Process:
1. Run the `code-review` skill on the diff. Also run `security-review` if the diff touches: chat ingestion, identity, LLM prompts or outputs, TTS input, SQL, file paths, subprocess/FFmpeg, auth, CI workflows, or Dockerfiles.
2. Walk the checklist in `docs/quality/REVIEW-CHECKLIST.md`.
3. Confirm traceability: tracker ID, spec section, and tests that prove each requirement.
4. Report findings ranked by severity, each with file:line and a concrete failure scenario. Don't report style nits that the linters already cover.

Never: approve a PR that weakens a test, disables a check, or adds `# type: ignore` / `eslint-disable` without a justification comment.
