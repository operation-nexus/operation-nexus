# Big-picture review, 2026-11-04

On 2026-11-04 the owner asked for a fresh look at the project: what are we trying to solve, are there more practical ways, which specs already take a shot at it, and are we making progress on P1 and P2? Two fresh agents answered independently, read-only, from facts with no conclusions handed to them: the entertainment reviewer (the four audiences, `docs/quality/ENTERTAINMENT-REVIEW.md`) and a Fable general-purpose agent (product, engineering and process). The lead wrote this synthesis and checked the load-bearing claims. The owner's decisions are at the end.

## 1. What we were solving, and whether it was on the critical path

- P1 exits on the reduced acceptance run: 10 seeds per crowd profile at 72 h, judged on A1–A4 (`docs/planning/ROADMAP.md:9`, Q-TEST-10). The raid stall touches only A1: "≥85% of seeds end in victory or defeat by 72 h" (`docs/quality/TESTING-STRATEGY.md:70`).
- Every stall run, K0 to P0, was 24 h (e.g. `HARNESS-P0-2026-11-04.md`, "Run"), and no 72 h harness review exists (lead grep of `docs/review/HARNESS-*`). A seed that hasn't ended at 24 h hasn't failed A1. **Both reviewers: the stall work was next to the critical path, not on it.**
- The game already ends every war at `campaign.time_limit_h` (72) by score (`docs/specs/GAMEPLAY.md` §9; `balance/default.yaml:150`). A long contested war fits the vision ("the frontline changes over days", `docs/planning/VISION.md:4`). The entertainment reviewer argues the stalled seeds were better shows (a see-saw, shorter newbie waits), and that the real tension with the vision runs the other way: raids now decide a 72 h war in about 2.5 h.
- The `raid-300` profile isn't a raid: 300 viewers who never leave (`tools/balance/README.md:38`), not a burst. Fine-tuning against it has low value until real chat exists.
- Fable: the loop swung from "too easy" (steamrolls, 2026-10-24) to "too hard" while adding contest mechanics (NX-466, NX-489, NX-499, NX-503).

## 2. More practical ways

| Option | Cost | Verdict |
|---|---|---|
| Threshold 0.75 (Q-TD-142 (b)) | One small PR (NX-506) | Owner approved. 23/24 raids end, no steamroll flags (P0). |
| Accept long wars; the time limit decides by score | Nothing to build (already in the spec and kernel) | Already there. If A1 fails for a profile, the question is A1's wording, not more tuning. |
| Make the stakes visible (holding 6 of 8, hold-paused banner, time-limit countdown) | Overlay work (NX-178, NX-496) | Entertainment reviewer's main design lever. P2. |
| Ease the east FOBs (Q-TD-142 (c)) | Content PR + measurement | Deferred until real crowds stall the same way. |
| Burst raid profile (NX-321) | Harness | P1 item per ROADMAP:10; currently filed under P4. |

## 3. Specs and items that already cover it

- Time-limit scoring: GAMEPLAY §9. Campaign end → after-action → next campaign: `docs/specs/STATE-MACHINES-AND-FLOWS.md`.
- Contest mechanics shipped: hold pause (NX-466), decay (NX-489), the defeat run (NX-499), return to base (NX-503).
- Open: hold-defence jobs for late joiners (NX-485), board capacity (NX-479), overlay HUD (NX-178), hold-at-risk sitreps on screen (NX-496), Hold the Line mode and procedural theaters (P4).

## 4. Progress on P1 and P2

**P1: 93 of 136 done** (`docs/planning/TRACKER.md:13`).
- Done: golden replay and cross-process determinism (NX-105), the 1,000-entity tick budget (NX-376), replay size (NX-032).
- Missing:
  - the 72 h reduced acceptance run itself;
  - the NX-321 adversarial profiles;
  - the P1 entertainment review (NX-378);
  - the weekly soak (NX-033 part 2);
  - the nightly harness in CI (NX-031 part 3).
- 24 tracker rows are still 👀, many after their PRs merged.

**P2: 0 of 56 done** (`TRACKER.md:14`). `services/gateway` doesn't exist. The WS server (NX-170), the overlay scaffold (NX-175) and the HUD (NX-178) haven't started. Its specs (WIRE-PROTOCOL, OVERLAY, CHAT-GATEWAY) are Draft.
- Critical path: NX-170 → NX-175/178, and NX-190 → NX-191 → NX-192 (with NX-041 moderation). None of it is kernel code, so the kernel pause (Q-DEV-37) doesn't block P2.

**Where effort went, 2026-10-28 to 11-04** (commits on develop touching each path): `docs/planning` 88, `services/sim/src` 36, `docs/review` 28, `tools/balance` 22, `apps` 9, `services/gateway` 0.

## 5. Process

- **Measure-first worked.** K0 killed the W7 hypothesis in a day, O0 found the real cause, and P0 confirmed the fix, all without kernel code.
- **Each hypothesis became paperwork.** Each one spawned a queue run, a review file, a Q-row and an owner question: 15 harness review files since 2026-10-28, and 91 "Decided by lead, owner may veto" rows open in OPEN-QUESTIONS.
- **The owner had already set the bar.** On 2026-10-30 the owner said "balance as we go on this small map" (Q-TD-136).

## 6. Recommendations (both reviewers make 1–3; 4 and the first half of 5 are Fable's, and the second half of 5 is the entertainment reviewer's)

1. Ship 0.75 and close the raid-stall thread; no more 24 h stall runs.
2. Queue the 72 h reduced acceptance run now, as P1 exit evidence.
3. Start P2's critical path now (WS server, overlay HUD, gateway). It needs no kernel.
4. Put the loop on a documentation diet.
5. Fix the horizon inconsistencies (48 h clock target vs 72 h limit) and keep every balance value PROPOSED until real chat has played a campaign. Point later tuning at overnight-0 and the A2 newbie tail, the weakest audiences, rather than raids.

## 7. Owner decisions (2026-11-04, chat)

- Q-TD-142 (b): 0.75, built as NX-506.
- Q-DEV-40: close the stall thread; the next run is the 72 h reduced acceptance run.
- Q-DEV-41: start P2 now, with a readiness pass on each Draft spec first.
- Q-DEV-42: documentation diet (`BALANCE-LOG.md`, weekly owner batch, retire veto rows older than two weeks, tracker cleanup).
- Q-DEV-43: several feature branches.
- Q-DEV-44: war length 72 h.
- WIRE-PROTOCOL sign-off with lead defaults: capability secret in the OBS URL fragment, sent in Hello; FastAPI/Starlette + uvicorn. Recorded with that spec's PR.
