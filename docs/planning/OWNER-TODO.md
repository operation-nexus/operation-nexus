# Owner To-Do (desktop setup and account actions)

Things only the owner can do. Check items off here or in the linked issues.

## 1. Desktop agent setup (issue #28, NX-044)
Mac all done (owner, 2026-10-22); the Windows PC (WSL2, in progress 2026-10-22) still needs every item (details: docs/agentic/TOOLING.md §5).

- [x] Install `jq` (the guard hook prefers it; python3 also works)
- [x] Put the `claude` CLI on PATH (`claude install stable`)
- [x] Clone the repo, open it in Claude Code, trust the folder, and accept the **Ponytail** plugin and **Context7** MCP prompts (Mac: approve Context7 once in the terminal `claude` too)
- [x] Install **Serena**, then run `claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd` and check it with `/mcp`
- [x] Enable **finecomb** and **claude-code-review-council** (claude.ai plugin directory)
- [ ] Optional: `claude remote-control` on the desktop so you can drive it from your phone (docs/agentic/REMOTE-WORK.md)
- [x] Ponytail: leave `webhookUrl` empty (docs/agentic/TOOLING.md §2)
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
- [ ] Reserve the **Hiveplex** handle on YouTube, TikTok, Bluesky and Discord the same day (all looked free on 2026-10-18), and after a manual look on X, Instagram, Reddit and a GitHub organization. **Twitch `hiveplex` is already taken** by a dormant 2015 account: register `hiveplextv` and ask Twitch support about releasing the original (docs/review/HANDLE-AND-DOMAIN-CHECK-2026-10-18.md, Q-MKT-10) (Q-BRAND-6, accepted risk), and the studio byline handle as a defensive hold; follow the setup runbook when it exists (NX-336). Accounts are created by hand: platforms bar automated creation
- [x] Epidemic Sound: ask support (a) whether a 24/7 monetized game stream is covered, (b) what happens to published content after cancelling; then choose upgrade vs a separate subscription Owner reported 2026-10-22: 24/7 music is fine (the answer's source is not recorded here, and no session has seen it; the VOD-archive and lapse questions are not recorded).
- [x] Create the private `operation-nexus-ops` repo (secrets, NX-299): on GitHub choose New repository, Private, README on, under the future organization if it exists (a transfer later is fine). The cloud session's GitHub integration cannot create repos (403). Then run `age-keygen` on your own machine, keep the private key in your password manager, and send only the public key (starts with `age1`) so `.sops.yaml` can be added (Q-OPS-10) Repos `operation-nexus-ops` and `operation-nexus-vault` created in the organization; the age key is still to do (§4d).
- [ ] Later (P3, with the lore pilot): create the private `operation-nexus-vault` repo for lore, marketing drafts and licensed art/audio, separate from the secrets repo (Q-OPS-10, AGENT-TEAMS.md)

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
- [x] Web-dependent verification (Q-PROC-3): Network access raised to full on 2026-10-18; verification passes now run from the cloud session (NX-333, in progress)
- [ ] Read the primary platform policy pages from the prepared checklist (NX-333); record what you find
- [x] Send Epidemic Sound the written questions (NX-332) before relying on it for 24/7 audio Owner reported 2026-10-22: 24/7 use is fine. There is no GitHub issue for NX-332; it is a tracker row, and the three questions are in `docs/review/LICENSE-AND-MUSIC-VERIFICATION-2026-10-18.md` §3.2.
- [ ] Ask Twitch support whether an intermission/replay loop on a 24/7 channel needs the Rerun label, before the closed alpha; check the Twitch setting that lets content train generative AI
- [ ] Put the Google OAuth app in production with verification when the YouTube integration starts (otherwise refresh tokens last 7 days)
- [ ] Turn on passkeys everywhere they exist; add a hardware key if you own one; keep one project mailbox
- [x] Channel naming confirmed (Q-MKT-7): channels named Hiveplex, studio handle as a byline hold
- [x] Create the brand mailbox and register a domain for the public contact addresses (Q-MKT-11); check `.gg`, `.io`, `.co` at a registrar (no public registry data for those endings) Mailbox `projecthiveplex@gmail.com` created; domain decision is Q-MKT-12.
- [ ] Pick the first 2-3 moderators from your trusted team before the public beta (Q-MOD-7) In progress 2026-10-22: the owner is adding moderators to the Discord now; tick when done.

## 4c. Manual steps left by the verification passes (2026-10-18)
Only you can do these; each report's last section has the detail. Reports: PLATFORM-POLICY-VERIFICATION, TRADEMARK-AND-NAME-VERIFICATION, LICENSE-AND-MUSIC-VERIFICATION under `docs/review/`.
- [x] **Twitch `hiveplex`:** tell me whether this account is yours. If it is, log in now and at least yearly (Twitch reclaims accounts after 12 months of no activity, per its 2017 policy post). If it isn't, use the fallback handle (Q-MKT-10) Answered 2026-10-18: not the owner's account; handles are the project_hiveplex family (docs/planning/BRAND-ACCOUNTS.md).
- [x] **GitHub user `hiveplex`** (id 4049119) exists: check whether it is yours; it affects the organization name choice Moot: the organization is `operation-nexus`.
- [ ] **Trademark registers I could not search:** (owner reported 2026-10-22: searched and found no HIVEPLEX entries; which registers were searched is not recorded, so left open) EUIPO eSearch, TMview, WIPO Global Brand Database, UKIPO: search `HIVEPLEX` and `HIVE PLEX` in classes 9, 28, 35, 38, 41, 42, or hand it to the attorney (ten questions are listed in the trademark report). Also find HIVEPLEX LTD's trading name
- [ ] **hiveplex.com** expires 2026-11-22 and is parked on BrandBucket: read the asking price there; decide whether a clean ending is enough (Q-MKT-10)
- [ ] **YouTube:** run one real test upload on a fresh Google Cloud project to settle whether unverified projects are locked to private (Google's docs contradict each other); check in the Cloud Console whether `youtube.upload` is a sensitive or restricted scope
- [ ] **Twitch pages that need a browser:** the help articles on reruns, Always On and the 48-hour limit; the AI-disclosure, music and viewbotting wording; set the "Training for Generative AI" toggle at `twitch.tv/settings/security`
- [ ] **Other pages that need a browser:** Discord Developer Policy; Meta's Automated Data Collection Terms; Instagram AI-info label rules; TikTok app-review/audit durations and the LIVE follower threshold (ask developer support)
- [ ] **Epidemic Sound:** read its Terms, subscription terms, MCP licence and plan prices in a browser (client-rendered) and send the written 24/7 questions (NX-332)
- [ ] **TTS voices:** pick specific permissively licensed voices or Kokoro or designed synthetic voices, and record each model card (Q-LEGAL-12)

## 4d. Organization move and secrets key (2026-10-18)
Accounts, handles and repos are listed in `docs/planning/BRAND-ACCOUNTS.md`.
- [x] **Install the Claude GitHub App on the `operation-nexus` organization** (done 2026-10-18) (https://github.com/apps/claude/installations/select_target) and give it this repo plus `operation-nexus-ops` and `operation-nexus-vault`. Until then cloud sessions cannot see the organization's repos (checked 2026-10-18: access denied)
- [x] **Transfer this repo** to the organization (done 2026-10-18). Rulesets, `ci-gate`, auto-merge and branch cleanup were re-checked; CODEOWNERS names `@saltyseraphcodes` until the org teams (`developers`, `maintainers`, `testers`) are used for ownership; tracker issue links point at the organization (NX-320)
- [ ] **Git identity on your machine:** use the `saltyseraphcodes` noreply address for commits in this organization (Q-LEGAL-8), and sign the GitHub CLI or browser in as `saltyseraphcodes`, not any personal account
- [x] **Install `age` and make the secrets key** (done 2026-10-18: public key sent, `.sops.yaml` added to the ops repo) (needed once, on your own computer, never in a cloud session):
  1. Install: macOS `brew install age`; Windows `winget install FiloSottile.age` (or `scoop install age`); Debian/Ubuntu `sudo apt install age`. The package includes `age-keygen`.
  2. Run `age-keygen -o key.txt`. It prints a line `Public key: age1...`.
  3. Put the whole `key.txt` in your password manager as a secure note, make a second offline backup, then delete the plain file. Never commit it, paste it into chat or put it in an issue.
  4. Send me only the `age1...` line. That public key is safe to share; it can only encrypt.
  Losing the private key means re-encrypting every secret, so back it up before anything else. I add `.sops.yaml` to the ops repo with that key; sops itself is installed later when the first secret is stored (NX-299)

## 5. Decisions still open
See docs/planning/OPEN-QUESTIONS.md. Rows ending in an empty Decision column still need your answer.
