# Decided questions: Q-DM

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## From the detailed system specs (2026-10-17)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-DM-1 | Archive old XP ledger rows yearly, keeping derived stats? | Yes, once the ledger passes about 1 GB (size is an ESTIMATE; measure it) | ✅ 2026-10-17: A, archive ledger rows older than 12 months into compressed yearly files once the ledger is large (~1 GB, measured); derived totals stay live |
| Q-DM-2 | Access control on the public replay viewer? | Not for v1. Replays are pseudonymous, and deleted users show `REDACTED-…`. | ✅ 2026-10-17: A, public replays without login. Player login (own stats, personal highlights) comes later. |

## Gap-analysis batch (2026-10-17; see docs/review/GAP-ANALYSIS-2026-10-17.md)

| ID | Question | Recommended default | Blocks | Decision |
|---|---|---|---|---|
| Q-DM-3 | Where do D7 and session analytics come from (NX-036)? | sim events only; no trackers | ✅ 2026-10-18: First-party only: D7 retention, session length etc. are derived from our own sim/gateway events keyed by commander_id. No third-party trackers, cookies or analytics scripts on overlay or site. Platform dashboards (Twitch/YouTube) are used for viewer counts but not imported. This must be stated in the privacy notice, terms of service and any cookie banner (NX-204, NX-314, NX-316). |

## Research-session batch (2026-10-18)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-DM-4 | Analytics with minimum tracking (owner 2026-10-18) | The owner wants analytics that inform decisions while keeping tracking minimal and transparent. Direction: first-party game-event analytics (Q-DM-3) as the core; UTM-tagged links in our own posts; platform-native dashboards as read-only references; cookieless first-party web stats on the public site only. Tool choice open pending the research doc (NX-329/NX-330). Aggregate-only dashboards and minimum cohort sizes; all disclosed in the privacy notice (NX-316). | P3 | ✅ 2026-10-18: Direction accepted: first-party game-event analytics (aggregate-only, minimum group size PROPOSED 10), tagged links in our own posts, platform dashboards read-only, optional 'how did you find us?' answer, and NO analytics script on overlay or site for now (GoAccess-style log analysis if the static host exposes logs). Details in Q-MOD-9; tool choice and privacy-notice wording under NX-330/NX-316. **Update 2026-10-22 (owner):** after the vault research report (`production/research/website-analytics-2026-10-22.md`), option A: keep Q-DM-4 as it stands. No script or third-party tool on the site, and no redirect or short-link domain. Attribution comes from a non-required 'How did you find us?' onboarding question (Discord allows only one permanent invite, so it is used everywhere) and a weekly note from public counts and hand-read numbers. Game analytics stays first-party (Q-DM-3). |
