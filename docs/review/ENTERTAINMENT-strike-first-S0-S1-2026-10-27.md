# Entertainment review: strike-first, runs S0 and S1 (2026-10-27)

**Bottom line:** strike-first does fix the Static's strike funnel. Strikes fire on about 45% of Offensives, against 2–8% before. But at raid it also locks the coalition's own aircraft out of the map. My reading is that the Static now takes bases with their air-defense sites still working, and the job board then refuses every route that crosses those rings. **Verdict: keep the key off for NX-412 part 5b. Turn it on only together with a companion change** (§3).

## 1. What was reviewed

- **Runs:** S0 #429 (control) and S1 #430 (`combat.strike_structure_first=true`).
  - Both at sha `04e15f8`: NX-439 cadence floor, NX-438 and the NX-440 key.
  - Both prime-50 and raid-300, seeds 1–6, 24 h, 12 workers.
  - Shared overrides: `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`, `economy.unlimited.COALITION=false`, `director.adaptation_up_above=2`. Upkeep 0 everywhere.
- **Older control:** M0 #415 at `1b5fd60`. S0 against M0 mixes NX-439 with NX-438/440 code (the key itself off); S0 against S1 is a clean single-key comparison.
- **Source of measured numbers:** the queue reports on #429 and #430, as transcribed by the lead for the `entertainment-reviewer` agent (Opus). "Derived" figures are the reviewer's arithmetic on those numbers. Owner questions are Q-TD-78 to Q-TD-80; runs N0 (#451) and N2 (#452) are queued.
- **Code read (not run):** `combat.py:128-161, 252-282`, `tasking.py:60-80, 941-978, 1114-1145`, `capture.py:298-310`, `fog.py:269-305`, `director.py:100-139`, `tools/balance/runner.py:217-320`, `content/theaters/strait-1.yaml`.
- **What doesn't exist yet:** the overlay, the site and clips. Every audience view is rebuilt from the reports, and every score is an estimate.
- **Missing seed:** S1 prime seed 1 was lost to a harness error. S1 prime figures are 5 seeds (§6).

## 2. Findings

### Q1: S0 against M0 (the floor alone)

| | M0 prime | S0 prime | M0 raid | S0 raid |
|---|---|---|---|---|
| Offensives | 172 | 135 | 315 | 109 |
| Offensives per run-hour (derived) | 1.19 | 0.94 | 2.19–2.63 | 1.58 (69.0 run-h) |
| Funnel | 172>11>10>17>17 | 135>11>11>14>14 | 315>15>12>17>17 | 109>2>2>3>3 |
| Raid lead-in (min) | – | – | 444–824 | 10 in every seed |
| Outcomes | 6 not ended | 6 not ended | 1 victory | 4 victories, all steamrolls (3.5–10.2 h) |
| A2 median / tail | 147 s / 27.1% | 187 s / 27.4% | 330 s / 37.3% | 663 s / 46.0% |

- **The 10-minute lead-in is the floor working as written.** `cadence_due` fires after `cadence_windows` (10) windows with no capture operation (`director.py:100-108`). Ten one-minute windows is exactly the 10 minutes seen. That meets Q-TD-69's PROPOSED target of a first capture operation within 60 minutes. Some of the drop in raid Offensives comes from shorter runs, but not all of it: per run-hour it still falls about 28–40%.
- **Yes, the floor delivers early capture operations that viewers then steamroll.** Without strike-first those operations have no teeth. Raid captures fell 17 → 3, and only 2 of 109 raid launches fired a strike. The Static sends units into a crowd of 300 within 10 minutes, loses them, and the coalition rolls east in about 3.5 h. That the early losses drain the Static's garrison is [UNVERIFIED]: the reports give no per-operation losses.
- **Long droughts are not gone.** S0 still has a 1340-min tail (prime s3) and a 1246-min tail (raid s1). The cadence floor can't fire while an operation is staged (`state.staged`, `director.py:105`), so an operation stuck in staging would block it. That this explains the tails is [UNVERIFIED].
- **Is the floor good for the show?** For pacing, yes. For the arc at raid without strike-first, no.

### Q2: S1 against S0, and the likely mechanism

| | S0 prime | S1 prime (5 seeds) | S0 raid | S1 raid |
|---|---|---|---|---|
| Strike % of launches (derived) | 8.1 | 44.6 | 1.8 | 47.1 |
| Offensives captured per seed-day (derived) | 2.3 | 8.2 | 1.0 | 9.8 |
| Victory holds | 2 (2 broken) | 0 | 4 | 0 |
| Idle "ring" share of idle samples (derived) | 3.2% | 89.6% | 15.0% | 98.3% |
| A2 median / tail | 187 s / 27.4% | 1601 s / 61.3% | 663 s / 46.0% | 29,048 s / 86.6% |
| Raid tier dwell, BRAVO | – | – | 10.13 h | 20.74 h |

**What the code does:**
1. **Facilities keep their damage when a base changes hands.** `_switch_facilities` (`capture.py:305-310`) hands each site over as it is. `hand_over` (`fog.py:288-305`) then gives the losing side a marker of that site straight away, with its live ring (`ring_m`, the longest air weapon range: 35 km for the SAM).
2. **The board refuses any straight route that crosses a known ring that wasn't last seen Disabled,** unless the target is that site's own base (`tasking.py:1114-1145`). That refusal is what `idle_reason` reports as "ring" (`tasking.py:965-966`).
3. **With strike-first, both sides bomb the node's defense HP and leave the site alone** (`combat.py:149-150`, `_strike_node`). Under S0 the bombs went into the air-defense site (STRIKE-FUNNEL §3), so most sites were Disabled by the time their base fell.

**Inferred chain [UNVERIFIED]:**
- The Static captures more ground, and the bases it takes now come with a working SAM.
- If west-airbase falls with its SAM up, any board job flown from haven (20 km, 120 km) to a target east of it crosses the 35 km ring. For example, the haven → fob-n-w line passes about 33.5 km from the SAM (derived from `strait-1.yaml`).
- Only jobs at west-airbase itself stay legal. The coalition's strike jets there also obey strike-first and don't bomb the SAM. So the marker never turns DISABLED, and the lockout lasts until a ground retake.
- **What fits:** the striker persona, whose JOIN names a node, still reaches first impact in 188 s. Auto-tasked viewers wait a median of 28,132 s. That matches line 73, which applies the ring check to a parameterless JOIN.
- **What's missing:** the reports don't show which node was held when, so "west-airbase is the lock" is untested.

So yes, this is a parity side effect (EC-3). Coalition jets aren't shot down; they are grounded by the ring rule.

### Q3: Verdict on the key

| Option | What it does to the ring lockout | Cost | Pick |
|---|---|---|---|
| Strike-first on alone | Causes it at raid | none | No |
| Keep it off | Funnel stays dead (2–8% strikes); raid steamrolls | none | **5b default** |
| On + **a captured facility changes hands Disabled** (repairs under its new owner) | Opens a retake window before the ring comes back; the lockout ends by itself | Design, S (`capture.py`, Q-GP-25 amendment) | **Preferred companion** |
| On + ring rule exempts a ring the side itself just lost, or the board posts a SEAD strike on a site blocking many jobs | Opens the routes directly | Design, S–M (TB-2) | Second |
| Overkill check (Q-TD-73) instead | Sites still get Disabled (so no lockout); spare bombs go to defenses. Whether 3 spare bombs zero a 300-HP FOB is doubtful (estimate) | Design, M | Test as an alternative |
| Static air defense that grows with stock (Q-TD-74) | Doesn't touch the ring rule | M | Orthogonal, still wanted |

**Is the S1 Static too strong?** One capture every 2.4–2.9 h per seed (derived) is not "every hour". It is a good pace for prime. But at raid the Static wins by benching the crowd, not by out-fighting it: BRAVO for 20.7 of 24 h, 0 holds, 76% of 335–367 armed viewer units idle. That is not a comeback arc, because the coalition never comes back.

## 3. Audience scores (estimates; M0 gave 2 everywhere)

| Audience | S0 prime / raid | S1 prime / raid | Biggest problems |
|---|---|---|---|
| Watcher | 2 / 1.5 | 3 / 2 | S0: Static never lands a punch. S1 raid: hundreds of jets parked at haven while the map turns red |
| Player | 2.5 / 1.5 | 2 / 1 | S1 raid A2 tail 86.6%; auto newbies wait about 8 h; agency only for viewers who name a target |
| Site | 2 / 1.5 | 2.5 / 1.5 | S0 raid ends as a steamroll by 3.5 h; S1 raid never ends and has no holds |
| VOD | 2 / 1.5 | 3 / 2 | S1 prime has real strike → capture payoffs (41); raid captures happen against a frozen defender |
| Low population | not tested | not tested | N3 covers it |

## 4. Suggestions

**Pure tuning (Q-DEV-21):**
- Keep `combat.strike_structure_first=false` for 5b.
- Probe `capture.defense_hp.AIRBASE=1000` together with strike-first. It is symmetric under EC-3. If raid "ring" idle collapses, west-airbase is confirmed as the lock.

**Design changes (owner):**
- Captured facilities change hands Disabled.
- Or a ring exemption / SEAD strike job (TB-2).
- The overkill check (Q-TD-73) as the alternative to strike-first.

**Harness (S each):**
- Hours each node is held, per side.
- "Ring" idle split by the blocking site.
- Per-operation Static losses.
- Fix the stale-job crash (§6).

### Owner questions (#412)

1. **Should a captured base's facilities change hands Disabled and repair under the new owner** (amends Q-GP-25)? *Recommend yes:* it is thematic, parity-safe, and creates a "retake before the SAM is back" beat.
2. **Strike-first or the overkill check as the funnel fix** (Q-TD-55 / Q-TD-73)? *Recommend: decide after the N runs below. Strike-first stays in 5b only with question 1's companion.*
3. **May coalition board jobs fly through a ring the coalition itself just lost?** *Recommend no for now.* Try question 1 first; it is smaller and helps both sides.

### Runs to queue (sweep N, revised)

Base overrides `B` = `economy.legacy_rules=false,economy.unlimited.ENEMY=false,economy.unlimited.COALITION=false,director.adaptation_up_above=2` (4 overrides). Every job stays under the queue's limit of 16.

| Job | Profiles, h, seeds | `set` | Question |
|---|---|---|---|
| N0 | prime-50, raid-300, 24 h, 6 | B | Tip control |
| N1p | raid-300, 6 h, 4 | B + `combat.strike_structure_first=true,capture.defense_hp.AIRBASE=1000` (6) | Does ring idle collapse? (cheap lock test) |
| N2 | prime-50, raid-300, 24 h, 6 | B + `director.score.victory_hold_mult=3.0` (5), **strike-first off**, since only S0 produced holds | Do holds get contested? |
| N3 | overnight-0, quiet-5, 24 h, 6 | B + `combat.strike_structure_first=true` (5) | Overnight drift (Q-TD-71); whether the ring lock bites at 5 viewers |
| N1 (full) | prime-50, raid-300, 24 h, 6 | B + `combat.strike_structure_first=true` (5) | Re-run only after question 1 is built and the node-hold metric exists |

Drop the planned N4 (upkeep). The K review keeps upkeep at 0 and has its own K4.

### Watch items for PLAYTEST-WATCHLIST

- "Ring" share of idle samples above 50%.
- A Static-held base with a live SAM between haven and the front.
- Auto-tasked newbies' A2 against strikers' (they diverged 150×).
- Droughts while an operation sits in staging.

## 6. The missing S1 prime seed

- **Where the error comes from:** `ValueError: job 6257 has no target` is raised in `tasking._waypoint` (`tasking.py:972-978`).
- **Why the whole run is gone:** the runner records an exception outside `step` as a harness error and keeps none of that run's ticks (`runner.py:217-230`, `failed_run` at 294-320). So the seed is missing entirely, not cut short.
- **Path (confirmed and fixed in NX-459):** the harness's `idle_reason` diagnostic (`metrics.py:423`) calls `_feasible` → `_reaches` → `_waypoint` between tasking passes. It could hit an ESCORT_CONVOY job whose truck died this tick and that has no node or position. The sim itself never reaches it: the next board pass ends such an escort first.
- **Bias:**
  - S1 prime totals (186 Offensives, 41 captures, 11,071 ring samples) cover 5 seeds against S0's 6. Per seed, S1 is even further ahead (37.2 against 22.5 Offensives).
  - The medians and tails lose one seed, direction unknown.
  - If seed 1 was a convoy-heavy seed, the 5 left may understate interdiction [UNVERIFIED].
- **Next step:** re-run the seed after a guard fix (a bug row: the diagnostic should skip a job with no target).

**Files:** `/home/user/operation-nexus/services/sim/src/nexus/core/capture.py`, `/home/user/operation-nexus/services/sim/src/nexus/core/fog.py`, `/home/user/operation-nexus/services/sim/src/nexus/core/tasking.py`, `/home/user/operation-nexus/services/sim/src/nexus/core/combat.py`, `/home/user/operation-nexus/services/sim/src/nexus/core/director.py`, `/home/user/operation-nexus/tools/balance/runner.py`, `/home/user/operation-nexus/content/theaters/strait-1.yaml`