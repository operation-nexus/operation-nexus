# Decided questions: Q-PH

Owner-decided (✅) rows moved verbatim from `../OPEN-QUESTIONS.md` on 2026-11-01 (W3, Q-DEV-37), grouped by their original section. Open and lead-decided rows stay in OPEN-QUESTIONS.

## P0 phase gate (2026-10-20)

| ID | Question | Decision | Priority | Status |
|---|---|---|---|---|
| Q-PH0-1 | Carry-over of open P0 items | Proposed in PHASE-P0 §6: tooling and lint items to P1, deploy and release items to P2, owner tasks anytime. | P0 | ✅ 2026-10-20: GO to P1, carry-over as proposed |
| Q-PH0-2 | Auto-merge for agent PRs | Let agent PRs into `develop` merge by auto-merge once `ci-gate` is green (AGENTS.md rule 10, ADR-0009); today the owner merges by hand. | P0 | ✅ 2026-10-20: yes, except PRs touching CODEOWNERS files, which the owner merges (Q-DEV-12) |
| Q-PH0-3 | Security review M1 and L6 | M1: `ci-gate` can be satisfied by a PR's own workflow edit, with no review required. Recommended: block auto-merge on PRs touching `.github/workflows/**` if Q-PH0-2 is yes, otherwise accept while the owner merges by hand. L6: pin the `ponytail` plugin to a commit. | P0 | ✅ 2026-10-20: M1 fixed by code-owner review on gate files (Q-DEV-12); L6 pinned to a tag (Q-DEV-13) |
