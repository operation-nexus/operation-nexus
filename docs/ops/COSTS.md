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
| Power, hosting | Running the stream and servers | Server about $6.8 to $8.5; server plus PC about $19 to $25 at idle-ish draw (derived, see Notes) | P2 | Q-OPS-3, [HARDWARE](HARDWARE.md); Kasa plug readings on the Grafana dashboard |

## Notes
- **Electricity (the owner's AES Ohio bills, entered by the owner 2026-10-25):**

  | Period | Days | kWh | Cost | $/kWh (cost / kWh) |
  |---|---|---|---|---|
  | 2026-04-28 to 05-20 | 23 | 168.89 | $39.02 | 0.2310 |
  | 2026-05-21 to 06-22 | 33 | 396.26 | $88.61 | 0.2236 |
  | 2026-06-23 to 07-23 | 31 | 429.92 | $96.54 | 0.2246 |
  | 2026-07-24 to 08-21 | 29 | 210.82 | $53.92 | 0.2558 |
  | 2026-08-22 to 09-22 | 32 | 213.08 | $54.36 | 0.2551 |

  These are whole-home bills, not the project's share. **Derived figures** (arithmetic on the lines above, not billed rates): a straight-line fit of cost against kWh over the five periods is about $8.23 + $0.2053 per kWh (R² 0.99). The latest bill splits into a $9.75 customer charge, $21.48 "other delivery charges" and $23.13 supply, so excluding the fixed charge the variable cost was about $0.2094 per kWh (assuming "other delivery charges" scale with kWh [UNVERIFIED]). The all-in average over the five periods is $0.2343 per kWh. The dashboard uses $0.2094 (marginal) or $0.2551 (latest all-in).
- **Measured draw:** the Linux server's plug read about 46 W on 2026-10-25 (45.9 to 48.5 W), which is about 33 kWh a month, or roughly $6.8 to $8.5 a month at the derived rates above. The harness PC's plug (installed 2026-10-25) read 80.8 W and then 89.2 W within the first few minutes after a reboot with the harness idle. Server plus PC was about 130 to 138 W, which is roughly 93 to 99 kWh over 30 days, or about $19 to $25 a month at the derived rates ($0.2094 and $0.2551 per kWh). **That is a short idle reading:** the PC's draw rises with harness load and gaming, so the project's real total is not known yet; the dashboard accumulates it from now on.
- **Two reviewers are wanted when the budget allows:** CodeRabbit plus the Claude review action, each run only some of the time (Q-CI-7).
- **The Claude review action** (`.github/workflows/claude-review.yml`) authenticates with `CLAUDE_CODE_OAUTH_TOKEN`. Anthropic's docs say runs with that token "use your Claude subscription instead of API billing", so it adds no separate charge. Whether its runs count against the plan's usage limits is not stated for the action [UNVERIFIED]; it runs only on sensitive-path PRs and on the `ai-review` label to keep usage low. It also uses GitHub Actions minutes.
- **Anthropic's separate security-review action** (`anthropics/claude-code-security-review`) accepts only an API key, so it would bill to the API. It is not used.
- Prices checked 2026-10-22: CodeRabbit at coderabbit.ai/pricing; the action at code.claude.com/docs/en/github-actions.
