# Owner To-Do (desktop setup and account actions)

Things only the owner can do. Check items off here or in the linked issues.

## 1. Desktop agent setup (issue #28, NX-044)
Mac done 2026-10-17 where checked; the Windows PC still needs every item (details: docs/agentic/TOOLING.md §5).

- [x] Install `jq` (the guard hook prefers it; python3 also works)
- [x] Put the `claude` CLI on PATH (`claude install stable`)
- [x] Clone the repo, open it in Claude Code, trust the folder, and accept the **Ponytail** plugin and **Context7** MCP prompts (Mac: approve Context7 once in the terminal `claude` too)
- [x] Install **Serena**, then run `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` and check it with `/mcp`
- [ ] Enable **finecomb** and **claude-code-review-council** (claude.ai plugin directory)
- [ ] Optional: `claude remote-control` on the desktop so you can drive it from your phone (docs/agentic/REMOTE-WORK.md)

## 2. GitHub settings (issue #20, NX-022; NX-049)
Applied and verified through the GitHub API on 2026-10-18 where checked.

- [x] Secret scanning + push protection ON
- [x] Dependabot alerts + security updates ON (version-update config `.github/dependabot.yml` is NX-018)
- [x] Private vulnerability reporting ON
- [x] Actions: allow only selected actions, require SHA pinning, default `GITHUB_TOKEN` read-only. Allowed: GitHub-owned actions plus `astral-sh/setup-uv` and `pnpm/action-setup`; a workflow that adds another third-party action needs it added under Settings → Actions
- [x] Environments `staging` (deploys from `develop` only) and `production` (your approval; `main` and `v*` tags only)
- [x] Rulesets per ADR-0009: `develop` = require a PR (0 approvals), require status check `ci-gate`, block force-push and deletion, allow auto-merge (Settings → General → "Allow auto-merge" and "Automatically delete head branches"); `main` = all checks, owner-only merge
- [ ] Optional: set the default branch to `develop`
- [x] Settings → General → **Automatically delete head branches** ON (AGENTS.md rule 11: merged feature branches are deleted)
- [x] Review PR #37 (repo skeleton) and merge it into `develop` if happy

## 3. Hardware (issue #6, NX-007)
- [ ] Linux server: `free -h`, `sudo dmidecode -t memory`, `lscpu`, `lsb_release -a` (record the results in docs/ops/HARDWARE.md)
- [ ] Back up the server, then move it to Ubuntu 24.04 LTS (Q-ARCH-8; a fresh install needs USB or console access)
- [ ] Measure upload speed (3 tests, different times of day)
- [ ] Optional: plug-in power meter for real wattage numbers

## 4. Accounts and brand (NX-297)
- [ ] Check handle availability and create **new** Twitch / YouTube / TikTok / Instagram accounts for Operation Nexus
- [ ] Epidemic Sound: ask support (a) whether a 24/7 monetized game stream is covered, (b) what happens to published content after cancelling; then choose upgrade vs a separate subscription
- [ ] Create the private `operation-nexus-ops` repo (secrets, NX-299)

## 5. Decisions still open
See docs/planning/OPEN-QUESTIONS.md. Rows ending in an empty Decision column still need your answer.
