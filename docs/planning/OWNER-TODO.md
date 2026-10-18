# Owner To-Do (desktop setup and account actions)

Things only the owner can do. Check items off here or in the linked issues.

## 1. Desktop agent setup (issue #28, NX-044)
Mac done 2026-10-17 where checked; the Windows PC still needs every item (details: docs/agentic/TOOLING.md §5).

- [x] Install `jq` (the guard hook prefers it; python3 also works)
- [x] Put the `claude` CLI on PATH (`claude install stable`)
- [ ] Clone the repo, open it in Claude Code, trust the folder, and accept the **Ponytail** plugin and **Context7** MCP prompts (Mac: approve Context7 once in the terminal `claude` too)
- [x] Install **Serena**, then run `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` and check it with `/mcp`
- [ ] Enable **finecomb** and **claude-code-review-council** (claude.ai plugin directory)
- [ ] Optional: `claude remote-control` on the desktop so you can drive it from your phone (docs/agentic/REMOTE-WORK.md)

## 2. GitHub settings (issue #20, NX-022; NX-049)
- [ ] Secret scanning + push protection ON
- [ ] Dependabot alerts + security updates ON
- [ ] Private vulnerability reporting ON
- [ ] Actions: allow only selected actions, require SHA pinning, default `GITHUB_TOKEN` read-only
- [ ] Environments `staging` and `production`; `production` requires your approval
- [ ] Rulesets per ADR-0009: `develop` (security + build required) and `main` (all checks, owner-only merge)
- [ ] Optional: set the default branch to `develop`
- [ ] Settings → General → **Automatically delete head branches** ON (AGENTS.md rule 11: merged feature branches are deleted)
- [ ] Review PR #37 (repo skeleton) and merge it into `develop` if happy

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
