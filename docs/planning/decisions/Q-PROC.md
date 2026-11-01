# Decided questions: Q-PROC

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-PROC-1 | Who folds decisions into specs, and in what order are specs approved? | one agent PR per spec; P1 specs first | ✅ 2026-10-18: Agents fold decisions into specs with one PR per spec (small reviews), reviewer-agent pass before each PR. Approval order: P1 specs first (SIM-CORE, GAMEPLAY, FOG-OF-WAR, THREAT-DIRECTOR, CONTRACTS), then the rest by phase. Owner reviews; agents may merge into develop after pulling latest changes (owner, 2026-10-18). |
| Q-PROC-2 | Every change to `develop` via PR? Avoid per-push friction | PR required, 0 approvals, `ci-gate` required, auto-merge on green; direct pushes blocked | P0 | ✅ 2026-10-18: Adopted; ADR-0009 amended; owner turns on the ruleset (OWNER-TODO). Merged branches are deleted (AGENTS.md rule 11); new work uses a fresh branch |

## Research-session batch (2026-10-18)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-PROC-3 | Where to run web-dependent research (owner question 2026-10-18) | Cloud sessions run behind a network policy that blocked most sites (trademark registers, store pages, platform policy pages, help centers), so those checks were never done at primary-source level. Options: (a) raise Network access or add the needed hosts under Allowed domains in the cloud environment settings, or (b) run these specific verification passes in a local desktop session. Open until the owner picks; either way the policy-page checklist (Q-LEGAL-10) is the work list. | P2 | ✅ 2026-10-18: Owner raised the cloud environment's Network access to full on 2026-10-18. Verified from the session: HTTP 200 from twitch.tv, youtube.com, tiktok.com, store.steampowered.com, itch.io, tmsearch.uspto.gov, dev.twitch.tv, support.google.com, epidemicsound.com, wikipedia.org; Instagram and X rate-limit automated requests, Reddit and GitHub web return 403. Primary-source verification passes now run from the cloud session (NX-333); a local session stays available for sign-in-only checks. |
