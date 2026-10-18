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
- [ ] Ponytail: leave `webhookUrl` empty (docs/agentic/TOOLING.md §2)
- [ ] **Git identity** on the Mac, on Windows, and inside WSL2 (it has its own `~/.gitconfig`), so every commit uses the SaltySeraphCodes noreply address (Q-LEGAL-8):
  `git config --global user.name "SaltySeraphCodes"` and `git config --global user.email "76628858+SaltySeraphCodes@users.noreply.github.com"`. Check with `git config --global --get user.email`. Agent sessions set the same identity per repo.

## 2. GitHub settings (issue #20, NX-022; NX-049)
Applied and verified through the GitHub API on 2026-10-18 where checked.

- [x] Secret scanning + push protection ON
- [x] Dependabot alerts + security updates ON (version-update config `.github/dependabot.yml` is NX-018)
- [x] Private vulnerability reporting ON
- [x] Actions: allow only selected actions, require SHA pinning, default `GITHUB_TOKEN` read-only. Allowed: GitHub-owned actions plus `astral-sh/setup-uv` and `pnpm/action-setup`; a workflow that adds another third-party action needs it added under Settings → Actions
- [x] Environments `staging` (deploys from `develop` only) and `production` (your approval; `main` and `v*` tags only)
- [x] Rulesets per ADR-0009: `develop` = require a PR (0 approvals), require status check `ci-gate`, block force-push and deletion, allow auto-merge (Settings → General → "Allow auto-merge" and "Automatically delete head branches"); `main` = all checks, owner-only merge
- [x] Rulesets: **Require code scanning results** (CodeQL) added 2026-10-18, tiered (ADR-0009 amendment): `main` blocks security alerts medium or higher and error-level alerts; `develop` blocks critical security alerts only
- [x] Set the default branch to `develop` (2026-10-18)
- [x] Settings → General → **Automatically delete head branches** ON (AGENTS.md rule 11: merged feature branches are deleted)
- [x] Review PR #37 (repo skeleton) and merge it into `develop` if happy
- [ ] **Delete merged branches.** Auto-delete only covers PRs merged on GitHub; a branch merged locally (`Merge branch '…' into develop`) stays until deleted by hand: `git push origin --delete <branch>`. Checked 2026-10-18: the remote had only `develop` and `main`. On each machine, drop stale local refs and branches: `git fetch --prune`, then `git branch --merged develop` and `git branch -d <branch>` for each listed feature branch (AGENTS.md rule 11).
- [ ] Close the issues for work that has landed, if you agree: #8 (NX-010, repo skeleton merged; `make check` green), and #20 (NX-022) and #32 (NX-049) once the settings above are confirmed
- [ ] **GitHub organization (Q-LEGAL-8, NX-320):** create an organization owned by the saltyseraphcodes account (name: your choice after the handle checks in §4a), then transfer this repo into it (repo Settings → General → Danger Zone → Transfer). Issues, PRs and links move and old URLs redirect. Afterwards re-check rulesets, environments, the Actions allowlist and security settings in the new home, since which settings carry over is [UNVERIFIED]; then update CODEOWNERS, tracker issue links and badges (NX-320)

## 3. Hardware (issue #6, NX-007)
- [ ] Linux server: `free -h`, `sudo dmidecode -t memory`, `lscpu`, `lsb_release -a` (record the results in docs/ops/HARDWARE.md)
- [ ] Back up the server, then move it to Ubuntu 24.04 LTS (Q-ARCH-8; a fresh install needs USB or console access)
- [ ] Measure upload speed (3 tests, different times of day)
- [ ] Optional: plug-in power meter for real wattage numbers

## 4. Accounts and brand (NX-297)
- [ ] Reserve the **Hiveplex** handle on Twitch, YouTube, TikTok and Instagram the same day (Q-BRAND-6, accepted risk), and the studio byline handle as a defensive hold; follow the setup runbook when it exists (NX-336). Accounts are created by hand: platforms bar automated creation
- [ ] Epidemic Sound: ask support (a) whether a 24/7 monetized game stream is covered, (b) what happens to published content after cancelling; then choose upgrade vs a separate subscription
- [ ] Create the private `operation-nexus-ops` repo (secrets, NX-299)

## 4a. Name clearance (Q-LEGAL-5, Q-BRAND-6; before NX-297 creates any account)
The research could not reach any official register (docs/review/NAME-CLEARANCE.md, Method). Only you can confirm. Full lists: NAME-CLEARANCE "Manual steps" (rounds 1–3).

- [ ] Trademark registers (USPTO with TSDR, EUIPO/TMview, WIPO Global Brand Database, UKIPO): search `HIVEPLEX`, `HIVE PLEX`, the runner-up, then `PLEX` alone, in classes 9, 41, 42 (28 for any board/card spin-off); confirm the class scope against the Nice text. Re-check PLEX reg. 4521387 and Plex, Inc.'s class 41 filings
- [ ] Look up HIVEPLEX LTD (13440983) on Companies House; check hiveplex.com and the `.gg`/`.tv`/`.live` versions at a registrar
- [ ] Handles for the chosen name: Twitch, YouTube, TikTok, X, Bluesky, Instagram, a Discord vanity URL, a subreddit and a GitHub org (the org also serves Q-LEGAL-8)
- [ ] Stores: Steam, itch.io, Epic, Xbox, PlayStation, Nintendo eShop, App Store, Google Play, Roblox
- [ ] In-world names: the Quorum (in-world label only, never the brand, Q-BRAND-7), the Static and NULL; re-check the records NAME-CLEARANCE cites for them
- [ ] TTS and chat test: play the name in the chosen voice and have a few viewers type it from audio only
- [ ] Attorney consult on "Hiveplex" versus PLEX/HIVE: deferred until traction or monetization (Q-LEGAL-9); do it before spending on marks or merch

## 4b. Follow-ups from the research session (2026-10-18)
- [ ] Decide where web-dependent verification runs (Q-PROC-3): raise the cloud environment's Network access or add hosts under Allowed domains, or run those passes in a local desktop session
- [ ] Read the primary platform policy pages from the prepared checklist (NX-333); record what you find
- [ ] Send Epidemic Sound the written questions (NX-332) before relying on it for 24/7 audio
- [ ] Ask Twitch support whether an intermission/replay loop on a 24/7 channel needs the Rerun label, before the closed alpha; check the Twitch setting that lets content train generative AI
- [ ] Put the Google OAuth app in production with verification when the YouTube integration starts (otherwise refresh tokens last 7 days)
- [ ] Turn on passkeys everywhere they exist; add a hardware key if you own one; keep one project mailbox
- [ ] Confirm the channel naming proposal (Q-MKT-7): channels named Hiveplex, studio handle as a byline hold
- [ ] Pick the first 2-3 moderators from your trusted team before the public beta (Q-MOD-7)

## 5. Decisions still open
See docs/planning/OPEN-QUESTIONS.md. Rows ending in an empty Decision column still need your answer.
