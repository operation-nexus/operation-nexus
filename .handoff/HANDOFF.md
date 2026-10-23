# Session handoff (2026-10-23)

This is a work branch only, not for merge. It carries the scratch files a fresh session needs. Delete the branch once its contents are used.

## Why the restart
Every GitHub MCP call (reads too, both repos) returned "invalid session" after the app install on the ops repo. Git over HTTPS still worked.

## State of the repos
- **operation-nexus** `develop` at 1878a2a. PRs #281–#293 merged. No open PRs from this session.
- **operation-nexus-ops**: branch `docs/error-issues` (3f113fc) is pushed, but the **PR was never opened** because the MCP failed. Open the PR into `main`, request SaltySeraphCodes as reviewer, and let the owner merge. Body: the README now says the repo holds the runtime `error` issues written by `python -m nexus.errors.sync` (ERROR-PIPELINE EP-9, Q-DEV-29); docs only.
- **operation-nexus-vault**: branch `docs/allow-ai-attribution` is pushed, and its **PR is not opened**. AGENTS rule 9 now allows AI attribution (owner, 2026-10-23). Open the PR into `main` and request SaltySeraphCodes. It touches a root file, so the owner merges it by hand. Until it merges, the vault's main still bans trailers.

## Pending work, in order
1. Open the two PRs above.
2. **NX-389 follow-up (hauler impact, A2):** see `nx389b-report.md` and `nx389b.patch` on this branch, if present. Background:
   - Forward stock (#289) roughly doubled deliveries, but new haulers rarely get an impact.
   - Raid-300 seeds 4–10: `resupply_slots_max=6` lifts haulers from 3/43 to 24/34, but drops auto players from 207/281 to 96/215 and makes A2 worse overall (tail 43% → 66%). Defaults are unchanged.
   - Options being tested: `tasking.stock_slots_max`, or keeping stocking jobs for an explicit `!join logi`.
   - Owner decides once the data is in. Then run the build loop (coder → QA → PR).
3. Next kernel and config work, one at a time:
   - NX-373 bridges (the lead proposes repair values next to FOB HP 300);
   - NX-390 settings registry;
   - NX-395 reload apply path (P2).
4. **Lessons PR** (CODEOWNERS path, so the owner approves): add the line in `lessons-pending.md` to `.agents/rules/code-quality.md` §9.
5. **Owner questions still open:**
   - Should a higher `director.tier.start` hold until provocation drops?
   - The hauler fix choice (item 2).
6. **PC queue** (owner runs these; wait until the hauler behaviour is stable):
   - the reduced P1 acceptance run, 10 seeds × 6 standard profiles × 72 h, gate A1–A4;
   - the NX-378 entertainment-review runs, 12–24 h;
   - NX-033 part 2, the weekly PC soak via `harness_queue.py` (needs security-review).
7. **P2 grilling** (`/grill-with-docs`): use `p2-grill-agenda.md`. Block A items 1–2 were already answered on 2026-10-23 (all lead rows approved; the reduced run was chosen). Refresh the agenda against `develop` before starting.
8. **P1 devlog: hold.** The owner said to wait (2026-10-23).

## Files on this branch
- `harness_wrap.py`: the stock-flow counters wrapper for `tools/balance` (NX-389 analysis only). Run it from `services/sim` with `uv run --frozen python <wrap> ../../tools/balance <balance args>`.
- `analyse.py`: summarises the wrapper output.
- `p2-grill-agenda.md`, `decisions-for-review.md`, `morning-report-2026-10-23.md`: context.
- `lessons-pending.md`: the code-quality §9 entry.
