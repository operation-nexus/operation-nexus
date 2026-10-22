# Running costs

A ledger of what Operation Nexus costs each month: plans, subscriptions and APIs, actual or planned. Update it whenever a cost starts, stops or changes. Amounts are what the owner pays or has stated; anything not yet known is left blank, not estimated (DATA-INTEGRITY).

Budget: Q-OPS-3 set a ceiling of **$75–100 per month** for running the game (power, AI and hosting). The owner counts the Claude plan used to build the project in the budget too (2026-10-22).

## Current

| Item | Purpose | Monthly | Since | Status | Decision |
|---|---|---|---|---|---|
| Claude plan (Anthropic) | Development: Claude Code sessions, and the PR review action (NX-029) | $100 | | Active | Owner, 2026-10-22 |
| CodeRabbit (Essentials, formerly Pro) | Automatic PR review on GitHub | $30 after the trial ($24 a month if billed yearly) | Trial from 2026-10-20 (14 days) | Trial ends about 2026-11-03; not renewed by default | Q-CI-7 |

**Known total:** $100 a month, or $130 if CodeRabbit is renewed.

## Planned

| Item | Purpose | Monthly | When | Decision |
|---|---|---|---|---|
| Game runtime LLM (advisor, narration, `!order`) | Phase 4 | Hard cap $20, alert at 80% | P4 | Q-AI-5, [LOCAL-VS-API-COST](LOCAL-VS-API-COST.md) |
| Power, hosting | Running the stream and servers | | P2 | Q-OPS-3, [HARDWARE](HARDWARE.md) (owner's figures still to come, NX-007) |

## Notes
- **Two reviewers are wanted when the budget allows:** CodeRabbit plus the Claude review action, each run only some of the time (Q-CI-7).
- **The Claude review action** (`.github/workflows/claude-review.yml`) authenticates with `CLAUDE_CODE_OAUTH_TOKEN`. Anthropic's docs say runs with that token "use your Claude subscription instead of API billing", so it adds no separate charge. Whether its runs count against the plan's usage limits is not stated for the action [UNVERIFIED]; it runs only on sensitive-path PRs and on the `ai-review` label to keep usage low. It also uses GitHub Actions minutes.
- **Anthropic's separate security-review action** (`anthropics/claude-code-security-review`) accepts only an API key, so it would bill to the API. It is not used.
- Prices checked 2026-10-22: CodeRabbit at coderabbit.ai/pricing; the action at code.claude.com/docs/en/github-actions.
