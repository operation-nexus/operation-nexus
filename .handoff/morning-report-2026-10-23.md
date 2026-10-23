# Morning report: overnight P1 run, 2026-10-22/23

## 1. What merged (into `develop`)

| PR | What |
|---|---|
| #257 | Specs: player patrols, Static scout intercepts, discovery XP (NX-382, NX-384) |
| #258 | Harness `--set` balance overrides and the queue `set:` key; A2 detail shows the median |
| #262 | Harness `--theater` and board-density metrics (open slots per unit, jobs per node); NX-385 tracker row (your approval) |
| #263 | Real-time scaling report from your WSL agent, saved with the lead's review (NX-376 notes, Q-GP-48) |
| #264 | **Coalition front-line patrols** (NX-382 part 1) |
| #265 | Rule presets on top of a default rule set (Q-GP-48, NX-386) |
| #266 | New A2 target (8 min median, at most 10% over 15 min, judged by role) and A7 first impression (Q-SIM-97, your approval) |
| #268, #269 | Harness implements the new A2 target, a hauler "departure" impact, and the tail share shown to one decimal |
| #270 | **Static scout intercepts** (NX-382 part 2) |
| #271 | Real-kernel scaling benchmark (`tools/sim-bench/kernel_bench.py`) |
| #272 | Reserve queue leave events and idle timeout command (NX-371) |
| #273 | **`step` time halved at 1,000 entities**, with no behaviour change (NX-376): container p99 25.4 → 11 ms (mixed), 19.8 → 13–15 ms (convoy) |
| #274 | Docs sync: CI, harness wall times, tooling, owner to-do list, P1 gate wording |

**Harness runs on your PC:** #253, #259–#261, #267. Run #267 ran without the 15-min tail check, which #268 added later.

| | Value |
|---|---|
| `strike_idle_targets_max` sweep (2 / 4 / 8) | No gain, so it stays at 2 |
| Newbie first impact after patrols, raid-300 | 1,376 → 294 s |
| Newbie first impact after patrols, evening-150 | 330 → 192 s |
| Open job slots per viewer unit, raid-300 / evening-150 | 0.02 / 0.04 |

Big crowds barely have any open slots: the size of the map is the limit, as you said.

## 2. Waiting on you

| PR | What | Action |
|---|---|---|
| #275 | `make check`, CI and pre-commit now lint and type-check `tools/`; security review found nothing | Approve together with #276 |
| #276 | Agent rules and skills update: AGENTS banner to P1, Q-DEV-21 wording, auto-merge race rule, first six lessons in code-quality, new-operation and new-unit skills refreshed, DoD CHANGELOG item, watchlist rows | Approve together with #275 |
| #277 | Tracker and spec tidy-up: NX-301 to P4, NX-387 to P2, PCG RNG row renamed Q-SIM-99, OV-23..25, stale notes, phase counts | Auto-merges (docs only); the moves are lead decisions you may veto |

**Run the NX-376 benchmark on your PC.** Paste the WSL prompt I gave you last night. It's the SC-10 reference-host number.

## 3. Decisions to approve or veto (lead decisions, Q-DEV-21)

Approve all, or name the ones you veto.

1. **Harness overrides** (#258): `--set key=value` on existing numeric keys only, schema-checked. The queue `set:` key is limited to 4 entries with a strict pattern.
2. **Density metrics** (#262): a job is "open" while it has fewer claims than slots. Disabled units don't count as viewer units.
3. **Patrols** (Q-SIM-94, #264):
   - The front line is a held node next to a neutral, enemy or unknown node, ordered nearest-enemy first.
   - There's no Director tier gate. QA measured that patrols add no provocation.
   - A bare `!join` never takes a patrol; the board assigns one at the next pass.
   - Aircraft fly a square orbit, kept clear of known rings.
   - A patrol gives way to better work: an aircraft any time, a ground unit once it stands on a node.
   - A unit never enters a node that was just lost. The game checks this every tick.
   - Dwell is **300 s** instead of 600, so a jet can finish a patrol on one tank.
4. **Intercepts** (Q-SIM-96, #270):
   - The reaction clock is saved world state.
   - Interceptors chase what the Static *sees*, not the scout's true position.
   - The garrison fighter's 80 km leash holds for the whole chase.
   - A dead or wrecked scout is never hunted again.
   - Slots: 1, which can overfill to 2 by the usual rule.
5. **Reserve queue** (Q-SIM-98, #272):
   - Leave reasons: SLOT_FREED, REPLACED, REJECTED, TIMEOUT.
   - A rejoin emits Left then Joined, so a viewer counter stays exact.
   - The idle timeout counts only unpaused time, so an offline auto-pause never empties the queue.
   - Idle means chat silence, per the spec.
6. **Rule-preset details** (Q-GP-48):
   - A preset is a validated overlay on the default config, chosen per campaign.
   - Admins apply presets; GMs draft them.
   - More than one unit per viewer needs its own spec.
7. **A2 harness details:** a hauler's "departure" is the first tick its truck has cargo and a route.
8. **Docs** (#276): the unused "CHANGELOG fragment" Definition-of-Done item is replaced by "entries come from Conventional Commits once release-please lands (NX-015)". Rule 7's ~400-line budget counts non-test, non-generated source.
9. **Older lead decisions still waiting on you** (about 30 rows from 10-21 to 10-23): Q-SIM-37, 40, 41, 43, 44, 45–47, 52, 55, 58, 62, 63, 67, 70, 72, 75, 80, 82 (lead part), 83, 91, Q-SIM-89 values, Q-SIM-92. Recommendation: approve all. Each was QA'd and is tunable.

## 4. Questions only you can answer

1. **Haulers and scouts have little to do.** A hauler who joins with a bare `!join logi` waits a median of about 30 minutes, because resupply jobs exist only when a base is starving. Scouts often find nothing new in 15 minutes.
   - (a) A standing "forward stock" job: haul surplus from the rear to forward bases up to a target level. This is a design change. **I recommend it.**
   - (b) Raise the starvation thresholds. This is tuning only.
   - (c) A bare `!join logi` takes any capture run or escort.
2. **Merge commits:** they are authored by canthony224, the account that enables auto-merge, while your branch commits use SaltySeraphCodes. Does that meet Q-LEGAL-8?
3. **A `theater:` key in harness-run issues?** It would let issue text name a file on your PC. I left it out as a security surface; say if you want it, with an allow-list.
4. **P1 blocked items:**
   - **NX-373 bridges:** approve proposed repair numbers. I recommend I propose values next to FOB defense HP 300, and the harness tunes them.
   - **NX-364 errors:** I recommend shipping the error port with a log and issue adapter now, and adding Sentry with the first 24/7 deploy (NX-255).
   - **NX-033 soak:** I recommend a 30–60 min nightly soak on CI, plus a weekly 6 h+ soak on your PC queue.
5. **P1 exit:**
   - **The 50-seed, 72 h acceptance run** is about 500 CPU-hours. I recommend your PC queue over several nights, and exiting P1 on a reduced run while the full run finishes during P2.
   - **Which targets gate P1?** I recommend A1–A4 only. A5 needs NX-321 (adversarial profiles, P4), A6 needs NX-291 (conduct system, P4), and A7 needs P2.
   - **Entertainment review (NX-378):** I recommend a partial review now on 12–24 h runs, then another at the first P2 overlay checkpoint.

6. **PR footer in merge commits.** The GitHub tool I use appends a "Generated by Claude Code" line to every PR description it creates, even when I leave it out. Merge commits copy the description, so the line lands in `develop`'s history, against your no-self-reference rule. Fix (your call): repo Settings → General → Pull Requests → "Allow merge commits" → default message **"Pull request title"**, so PR descriptions are never copied into commits.

## 5. Blocked

- **Waiting on your answers in §4:**
  - NX-373 bridges;
  - NX-364 Sentry;
  - NX-033 soak;
  - the P1 acceptance run;
  - NX-378 entertainment review.
- **Waiting on P2 work:** NX-387 (reserve-queue runtime wiring) needs the chat gateway (NX-190).
- **Waiting on your PC:** the NX-376 reference-host benchmark run (the prompt is ready).

## 6. Entertainment review: what changed tonight (Q-DEV-22)

This is a short checkpoint note from harness data, not the full P1-exit review (NX-378).

- **Watcher (score unchanged at about 3/5):**
  - Patrols put idle viewer units on the front line instead of parked at bases, so the map has visible motion at quiet times.
  - Intercepts add a readable set-up and payoff: scout spotted, fighters scramble, chase, escape or kill.
  - Risk: with 0.02 open slots per unit at raid-300, a big crowd still sees many units idle.
- **Player (about 3 → 3.5/5):**
  - New arrivals reach their first impact far sooner: about 4–5 min at raid-300, down from 23 min.
  - Strikers get a hit in about 3 min.
  - Haulers and scouts still wait too long; that's §4 question 1.
  - Scouting gained real tension: stay too long and you get chased.
- **Site watcher (no surface yet):** intercepts and patrols create events that a campaign story can be written from ("BANDITS SCRAMBLED", "patrol held the line at FOB North").
- **VOD and clip watcher:** intercept chases are the best clip material so far. A 15–60 s chase has a natural setup and payoff.

**Suggestions:**

| Suggestion | Kind |
|---|---|
| A "BANDITS SCRAMBLED" overlay callout off the INTERCEPT `JobCreated` event | OVERLAY, P2 |
| Hauler forward-stock jobs | Design, §4 question 1 |
| The NX-385 benchmark theater, to test bigger maps for raid crowds | Content, after P1 |

## 7. P2 grilling: prepared

The full agenda is in `/tmp/claude-0/-home-user/47f1a954-d462-5225-99d8-27ec9b10b99d/scratchpad/p2-grill-agenda.md`. It has 30 questions in six blocks:

| Block | Covers |
|---|---|
| A | P1 decisions (above) |
| B | Hosting: accept ADR-0012; reinstall the Linux server 64-bit; upload speed tests; a separate Twitch test channel for the alpha; deploy pipeline depth |
| C | Gateway: approve CHAT-GATEWAY and COMMAND-CATALOG; a separate Twitch bot account; where tokens live (pull sops+age into P2); the callsign word list |
| D | WebSocket server and overlay: one ASGI stack; placeholder styling until the brand guide |
| E | Identity and data: approve IDENTITY and DATA-MODEL; frame-stream retention |
| F | Ops and admin: monitoring stack timing; Discord admin in P3; audio scope |

**Specs to approve before P2 code:** CHAT-GATEWAY, COMMAND-CATALOG, WIRE-PROTOCOL, CONTRACTS §4–8, OVERLAY, IDENTITY, DATA-MODEL, OPS-ADMIN, ADMIN-RBAC (P2 slice), MONITORING-WATCHDOG, HARDWARE, and ADR-0012.

**Specs to write:** viewer-simulator spec, brand guide, alpha playtest plan, moderation/denylist section, and callsign word list.

When you're ready, say "grill P2" and I'll run it with `/grill-with-docs`.
