# Entertainment review: S0 #493 and S1 #494 (sha 8f9a5ff), 2026-10-28

## Bottom line

1. **NX-474 mostly meets its criterion on quiet-5, for day 1.**
   - **Most of the day:** in the two hardest seeds the coalition held 2 or more strategic nodes for 89.6% (s1) and 56.3% (s2) of the day (probe). The other four seeds had only 3 Static captures between them (derived: 11 minus the 8 in the probe seeds).
   - **The gain is from the night cap, nothing else.** The cap now applies from 1 to 49 viewer units, and at 5 units it keeps about 90–100% of its 0-viewer spacing. `night_cap` was the first no-capture reason in 77% of quiet-5 windows. Every probe flip came about 6 h after the one before.
   - **The fade does almost nothing at 5 viewer units,** as Q-TD-93's note predicted.
   - **The last-base freeze never took effect in either probe seed.** It guards only `west-airbase`, and `west-airbase` fell before the last FOB both times.
   - **Day 2 is unprotected [estimate, not run past 24 h].**
2. **The quiet-5 A2 fail is noise.** It is 2 newbies out of 10, both auto-tasked, in seeds 3–6. With n ≈ 10, one newbie moves the tail by 10 points. Don't gate 5b on it.
3. **Q-TD-97: S1 overshoots.**
   - S1 raid is a far better stream than S0. The longest dry stretch is a median 54 min against 110, and the Static has 50.65 ops/h against 15.13.
   - But it is a stalemate the crowd can't close with a hold. All 33 victory holds were broken, 5 of 6 seeds hadn't ended at 24 h, and in probe s1 the Static pushed about 120 live viewer units back to 1 of 8 nodes at 10.75 h.
   - The one win (s2, 12.23 h) was a one-commander capture of the Static HQ, not a hold.
   - That is more than the owner's "at least some resistance" or "raise difficulty slightly".
   - **Pick: `director.source_spend_frac` 0.01 for 5b (tuning)**, with 0.02 as the same-sha bracket. Leave crowd-scaled spend aside for now.
4. **Global-key safety: 0.02 did not hurt quiet-5 or prime-50,** so a single global key is acceptable for 5b. One caveat: quiet-5 is only safe because the night cap is binding. Recheck when NX-475 (retake) lands.
5. **New flag: NX-474's cap also takes effect at prime-50** (first reason in 32.5% of S0 windows and 45.8% of S1 windows, 2811 and 3960 of 8640). Prime Static captures fell from 63 (R2, b0bc4e3) to 47 (S0). That compares two shas, so the cause is [UNVERIFIED] (L-37).
6. **5b candidate:** B + strike-first + `director.staging.max_wait_windows=30` + `director.source_spend_frac=0.01`. Confirm it at the newest develop sha (it must include NX-467, NX-480, NX-468 and NX-475) against a 0.02 bracket. Configs are in section 3.

The review is by the Opus entertainment-reviewer subagent, with probes capped at 2 seeds and one causal probe per question (L-40). The lead filed it unchanged except for adding NX-475 to item 6 and run T, since NX-475 is now in build.

## 1. What was reviewed

**Queue numbers** come from a Sonnet extract, copied verbatim from report comments #493/6470684541 and #494/6472806544.
- Both runs: sha 8f9a5ff4, 24 h, 6 seeds, overnight-0, quiet-5, prime-50 and raid-300, 0 crashes, 0 harness errors.
- Config hashes: S0 `84542b09…`, S1 `543e8874…`.
- "Derived" marks the reviewer's own arithmetic on those numbers.

**Configs:**
- **S0:** B (`economy.legacy_rules=false`, `economy.unlimited.*=false`, `director.adaptation_up_above=2`) + `combat.strike_structure_first=true` + `director.staging.max_wait_windows=30`.
- **S1:** S0 + `director.source_spend_frac=0.02` (shipped 0.005).

**Prior context:**
- `docs/review/ENTERTAINMENT-R0-R2-2026-10-28.md`: R2 #482 at b0bc4e3 is the S0 config without NX-474/476/472.
- `docs/review/LEAD-NOTE-L1p-L4-2026-10-28.md`.
- `docs/review/ENTERTAINMENT-L0-L1-2026-10-28.md`.
- The rows for Q-TD-79, Q-TD-84, Q-TD-90, Q-TD-91, Q-TD-93, Q-TD-94, Q-TD-97 and Q-TD-98 in `docs/planning/OPEN-QUESTIONS.md`.

**Probes (measured, read-only, 2 questions, 2 seeds each):**
- **Source tree:** `git archive 8f9a5ff`. Each probe samples every 15 game min (owners, Static pool and budget, tier, live viewer units, `no_capture_reason`) and logs captures, hold start/break and newbie join/impact events. Scripts stayed in the session scratchpad.
- **Q1 probe:** quiet-5, S0 config, seeds 1 and 2, `--hours 24`, run to the end. The final hashes reproduce the queue: `a3338153798e827e…` and `88bd31a98d0c72cd…`, config hash `84542b09…`.
- **Q2 probe:** raid-300, S1 config.
  - s2: `--hours 24`, ended by the campaign at 12.23 h (440411 ticks). The final hash `6632342d985b0736…` reproduces the queue.
  - s1: `--hours 24`, stopped early at 12 h (L-39), so it has no comparable final hash.
- No probes for Q3 or Q4.

**Code read at 8f9a5ff:**
- **`services/sim/src/nexus/core/director.py`:**
  - `:75-78`: `night_spacing` is `night_cap_ticks × (quiet_ref − min(v, quiet_ref)) // quiet_ref`. At 5 units that is 0.9 × 360 min = 324 min.
  - `:81-86`: `night_capped`.
  - `:102-104`: `rear_share` is `floor(pool × source_spend_frac)`.
- **`capture.py`:**
  - `:113-118`: the last-base freeze applies only to `idle_node = forward_airbase`, which is `west-airbase` (`content/theaters/strait-1.yaml:76`).
  - `:239-256`: `_night_hold`. Any Static flip stamps `last_flip`, neutral nodes included. A held bar waits the full 0-viewer cap.
- **`launch.py:286, :393`:** the cap bars capture operations.
- **`campaign.py:181-182`:** an HQ capture wins at once.
- **`campaign.py:198`:** the hold resets to 0 when it breaks.
- **`balance/default.yaml`:**
  - `:77`: `quiet_ref` 50.
  - `:146`: night cap 1/6 node per hour.
  - `:264`: `source_spend_frac` 0.005.
- **`content/operations.yaml:12`:** OFFENSIVE costs 60.

**What doesn't exist yet:** the overlay, the site and clips. Every audience view below is reconstructed from events, and every score is an estimate. Coalition captures and time held per node count are not in the harness report; for those, only the 4 probe seeds exist.

## 2. Findings

### Q1. NX-474 on quiet-5

| quiet-5 | L1p (b0bc4e3, before NX-474) | S0 (8f9a5ff) | S1 |
|---|---|---|---|
| Momentum % | 8.7 | 33.9 | 32.3 |
| Static captures (Offensive + Retake) | 20 + 1 | 11 + 0 | 11 + 0 |
| `no_target` windows | 2690 | 0 | 0 |
| `night_cap` windows (of 8640) | not in note | 6673 (77.2%, derived) | 6859 (79.4%) |
| Longest dry stretch, median / max (min) | 1045 / 1357 | 406.5 / 455 | 389 / 417 |

**Probe timeline (S0):**

| Seed | Static flips (h) | Coalition holds 3 / 2 / 1 strategic nodes (share of 96 samples) |
|---|---|---|
| s1 | cross-s (neutral) 1.74; cross-n (neutral) 7.66; fob-n-w 15.76; west-airbase 21.57 | 65.6% / 24.0% / 10.4% |
| s2 | cross-s (neutral) 0.98; fob-s-w 7.21; west-airbase 13.55; cross-n (neutral) 19.58 | 29.2% / 27.1% / 43.8% |

- **The flips follow the cap clock.** The steps between flips are 5.92, 8.10, 5.81, 6.23, 6.34 and 6.03 h (derived), against a 324–360 min spacing.
- **`night_cap` was the probe's first no-capture reason** in 79 of 96 samples (s1) and 88 of 96 (s2).

**Verdict:**
- The criterion "keeps a front line for most of the day" is met on day 1.
  - In the worst probe seed (s2) the coalition sits on one FOB from 13.5 h.
- **What does the work:** the cap barring capture operations at 1–49 viewer units. At quiet-5 the spacing barely fades (90% at 5 units, 96% at 2), so the effect is close to the 0-viewer cap applied to a small crowd.
- **What does not work yet:**
  - **The freeze guards `west-airbase` only.** In both seeds the Static took a FOB and then `west-airbase`, leaving an unguarded FOB as the last base. The freeze never took effect.
  - **Neutral flips spend the cap** (4 of the 8 probe flips). That slows the opening, but once both crossings are Static, every 6 h costs the coalition a node.
  - **Day 2 [estimate]:** the next flip in s2 was due at about 25.6 h, against the unguarded last FOB. Quiet-5 could reach zero nodes again on day 2, the Q-TD-94 state. NX-475 is the fix already planned.
- **Pacing on stream:** the Static moves once every 6 h by construction. Between moves, the probe shows 0.38 STAGING sitreps and 0.17 STRIKE_DOWNED sitreps per run-hour. That's calm (pillar 5), not dead, but there are few clip moments.

**A2 fail on quiet-5:**
- **Numbers:** median 86 s (passes), tail 20.0% = 2 of 10, both auto-tasked (extract: auto 8, tail 25%).
- **Probe seeds:** 2 newbies at ALPHA or above in s1, at 799 s (scout) and 144 s (hit). All 3 s2 newbies arrived at Pattern of Life and are excluded. So the two late newbies are in s3–s6; why they were late is [UNVERIFIED].
- **The sample is too small to judge.** A 95% interval for 2 of 10 runs from about 3% to 56% (derived, Clopper–Pearson). L4 passed at 1 of 11, and S1 fails at 1 of 6.
- **Verdict:** not a 5b signal. Judge quiet-5 A2 over pooled runs or with a minimum n.

### Q2. Q-TD-97 at raid: resistance or stalemate?

| raid-300 | S0 (0.005) | S1 (0.02) |
|---|---|---|
| Outcomes | 6 victories, median 2.0 h, 5 of 6 steamrolls | 1 victory (12.23 h), 5 not ended |
| Static captures (Offensive + Retake) | 0 + 0 | 237 + 11 |
| Holds (broken) | 6 (0) | 33 (33) |
| Longest dry stretch, median (min) | 110.4 | 54.0 |
| Static budget per window / income per hour | 46.5 / 395.8 | 164.5 / 3035.1 |
| BRAVO dwell (h) | 1.67 | 21.68 |
| STRIKE_DOWNED per hour / HOLD_AT_RISK per hour | 2.87 / – | 10.76 / 1.28 |
| A2 tail | 57.4% (n 119) | 32.5% (n 1488) |

**Mechanism (probe s1 and s2, 12 h each):**
- **The Static now spends.** Its budget runs 77–266 a window (hourly means 87–258) against a pool of 3.3k–12k.
  - Income rose 7.7× (3035.1/h against 395.8/h), mainly because spending keeps the pool off its storage cap, so income is no longer clipped. That is the R0–R2 "dies rich" diagnosis, confirmed.
  - In s1 the pool reached its cap again (12000) at 10.75–11.25 h, while the Static held 7 of 8 nodes.
- **EC-9 plus money breaks every hold.**
  - During a hold the Static launches capture operations outside `max_ops`, but the budget still applies (`docs/specs/ECONOMY.md:35`).
  - At 0.005 the budget (about 46) can't buy a 60-cost Offensive; at 0.02 it buys about 2 a window (derived).
  - Probe hold-break times: 15.2, 18.9, 10.1, 0.3 and 5.8 min (s2); 22.2, 18.5 and 4.0 min (s1). The median is 12.7 min (derived). Every one is under the 30-min hold.
  - The broken holds are on fob-s-e, fob-n-e, cross-n and cross-s. All four are within the Static's 11.8–25.7 min travel time; the western nodes are out of its reach.
  - A broken hold resets to 0 (`campaign.py:198`).
- **It's a tug-of-war around the crossings.**
  - s2: 66 captures in 12.2 h, 34 coalition and 32 Static. cross-s flipped 22 times and cross-n 21; cross-s flipped 8 times between 8.13 and 9.08 h.
  - s1: 73 captures, 36 coalition and 37 Static.
  - Coalition captures in s1 had 1.14 commander participants on average. The crowd doesn't mass on a node.
- **There are big swings both ways.**
  - In s1 the coalition went from 8 of 8 nodes at 2.25 h to 1 of 8 (`west-airbase` only) at 10.75 h with 122 live viewer units, then back to 3 at 11.75 h.
  - Live viewer units fell from about 200 to about 120–175 over 12 h in both seeds (profile churn).
- **The only win is a decapitation.** The s2 victory was `static-hq` captured at 12.234 h by 1 commander while the coalition held 4 of 8 nodes (`campaign.py:181`). Whether the HQ was undefended is [UNVERIFIED].

**How it looks on stream:**
- **Better than S0 by a lot:** a constant fight, a HOLD_AT_RISK sitrep every 47 min, and real comebacks. That is the VISION line "the frontline changes over days".
- **But the crossing ping-pong is a treadmill.** A node flipping every 5–10 min reads as noise, not a story.
- **Every hold ends the same way:** "hold at risk, hold broken" 33 times out of 33. Viewers will learn the hold can't be won. There is tension, but no payoff.

**Verdict:** S1 is past "at least some resistance" (Q-TD-91) and is a stalemate for a 300 crowd: 0 of 33 holds held, and 1 win in 6 by a side door.

**Recommendation:** 0.01 is the in-between value [estimate]. With the base-surplus term roughly as in S0, it gives about 46 + 40 ≈ 86 a window at a pool of 8000. That buys about one Offensive a window: enough to contest a hold, not to flood it.

**Crowd-scaled spend above `quiet_ref` (Q-TD-97 b): not now.**
- Its purpose was to spare quiet and prime, and 0.02 already doesn't hurt them (Q3).
- At raid, spend that rises with the crowd would deepen the stalemate the data shows.

**Separate design question:** if 0.01 still breaks almost every hold, change the hold so that a break doesn't cost all progress (see recommendation 3).

### Q3. Global-key safety (S0 → S1)

| Profile | Momentum % | Static captures | Other numbers |
|---|---|---|---|
| overnight-0 | same | same | A3 passes in both; spend debits the same |
| quiet-5 | 33.9 → 32.3 | 11 → 11 | Offensives 51 → 47; STRIKE_DOWNED 24 → 33; coalition income 343 → 281/h (cause [UNVERIFIED]) |
| prime-50 | 45.0 → 44.8 | 46+1 → 47+1 | Longest dry stretch median 367 → 225.5 min (better); BRAVO dwell 3.05 → 4.54 h; A2 tail 28.3% → 29.1%; STAGING_DISPERSED 0.26 → 0.36/h |

- **At prime, 0.02 makes more fights, not more losses.** Defenses down rose from 50 to 74 and capture starts from 63 to 92, while captures stayed at 46 against 47.
- **Verdict:** no harm. A single global key is acceptable for 5b.
- **Caveat:** quiet-5 is safe because `night_cap` binds in about 77% of its windows, so the spend key has little room to act there. Recheck quiet-5 with any change to the cap or the retake path.

### Q4. The 5b set, and the prime side effect of NX-474

- **The data supports:**
  - B + `combat.strike_structure_first=true` + `director.staging.max_wait_windows=30`, with NX-474 (Q-TD-79, Q-TD-90 unchanged);
  - a spend value between 0.005 (raid steamroll) and 0.02 (raid stalemate).
- **Prime-50 lost Static activity from R2 to S0**, which have the same config at two shas:

| prime-50 | R2 (b0bc4e3) | S0 (8f9a5ff) |
|---|---|---|
| Static captures | 63 | 47 |
| RETAKE launches | 13 | 2 |
| Longest dry stretch, median (min) | 286.5 | 367 |

- **The likely cause is the night cap at prime.**
  - Prime-50 means about 50 viewers, not 50 live viewer units: peak armed units were 14–29 per seed. Below 50 units the cap still applies, and a held bar waits the full 6 h (`capture.py:250`).
  - This is a cross-sha comparison, so the cause is [UNVERIFIED] (L-37).
- **0.02 partly offsets it** (225.5 min).
- **The confirming run must be at the newest sha.** NX-480 holds staged capture operations under the cap, so expect fewer pointless quiet Offensives [estimate]. NX-468 changes SAM fire against jets, which bears directly on raid STRIKE_DOWNED.

### Audience scores (estimates, 1–5; S0 / S1)

| Audience | quiet-5 | prime-50 | raid-300 |
|---|---|---|---|
| Watcher | 2.5 / 2.5 | 3.5 / 3.5 | 2 / 3.5 |
| Player | 3 / 3 | 3 / 3 | 2 / 3 |
| Site watcher | 3 / 3 | 3.5 / 3.5 | 1.5 / 3 |
| VOD and clip | 2 / 2 | 3 / 3.5 | 2 / 3 |

**Three biggest problems:**
- **Watcher:**
  - raid S1 holds always break (no payoff);
  - crossing ping-pong at raid;
  - quiet moves only every 6 h.
- **Player:**
  - At prime and raid, A2 fails because of the role kinds: capturer tail 89–99%, hauler 50–96%, scout 71–88%. Auto-tasked joiners pass at 9.4–9.7%, and strikers at raid S1 pass at 1.9%. About 82% of the raid S1 tail are capturers, haulers and scouts (derived).
  - Coalition captures are made by about 1 commander.
  - The quiet A2 sample is too small to judge.
- **Site watcher:**
  - quiet day 2 is unprotected;
  - raid S1 has no ending;
  - the prime Static is quieter than at R2.
- **VOD and clip:**
  - Quiet is clip-poor.
  - The s2 one-commander HQ grab is the best clip in the batch, and also possibly a cheap way to win.
  - A broken hold makes a good clip only while viewers believe a hold can succeed.

## 3. Recommendations (ranked)

| # | Suggestion | Kind | Audience | Expected effect (estimate) | Cost | Touches |
|---|---|---|---|---|---|---|
| 1 | `director.source_spend_frac` 0.01 as the 5b candidate | **Tuning** | Watcher, Player at raid | About 1 Offensive a window at raid: holds contested, some survive; prime between S0 and S1 | Two runs | `balance/default.yaml:264`, Q-TD-97 |
| 2 | Confirming runs at the newest develop sha (with NX-467, NX-480, NX-468, NX-475), see the configs below | Harness | All | Sets the 5b value on the shipping code (L-37) | About 2 × 1.5 h queue | NX-412 5b |
| 3 | A broken hold keeps part of its progress, or pauses instead of resetting while a node is lost and retaken within N min | **Design** | Watcher, VOD | A crowd that keeps winning ground finishes the war; a broken hold is a setback with a payoff later | S–M | ECONOMY EC-9, GAMEPLAY §9, `campaign.py:198`, Q-TD-84 |
| 4 | Hold NX-466 (pause under pressure) until run T is read: with 0.02 every hold already breaks, and a pause makes raid harder | Sequencing | Watcher | Avoids deepening the stalemate | 0 | NX-466, Q-TD-84 |
| 5 | Last-base freeze applies to whatever strategic node the coalition holds last, not only `west-airbase` | **Design** | Site watcher, quiet Player | Quiet day 2 keeps one base to fight from | S | `capture.py:113-127`, Q-TD-93 |
| 6 | Cap fade against live viewer units at prime: a release tick stored at hold time (Q-TD-93 note) or a separate fade reference below 50 | Design (new key = add-config-key) | prime Watcher | Restores R2-level prime Static activity | S–M | `director.py:75-78`, `capture.py:250`, Q-TD-93 |
| 7 | Harness (NX-478 add-ons): time held at N strategic nodes per side, coalition captures, Static spend split (`shared` + `unattributed` are 52% of S1 raid debits, derived), A2 per kind with a minimum n | Tooling | Lead | Answers NX-474-type criteria without probes | S | `tools/balance/metrics.py`, `report.py` |
| 8 | Q-TD-98 (NX-479): late joiners get a hold-defence job | Design | Player | Fixes the role-kind A2 tail and gives the crowd a reason to mass on hold nodes | M | GAMEPLAY §1b, Q-TD-98 |

**Run T0:**
- `sha: <newest develop, with NX-475>`
- `profiles: overnight-0, quiet-5, prime-50, raid-300`
- `seeds: 6`, `hours: 24`
- `set: economy.legacy_rules=false, economy.unlimited.ENEMY=false, economy.unlimited.COALITION=false, director.adaptation_up_above=2, combat.strike_structure_first=true, director.staging.max_wait_windows=30, director.source_spend_frac=0.01`

**Run T1** (same-sha bracket and control): T0 with `director.source_spend_frac=0.02`.

**Later:** once a value wins, run raid-300 at `hours: 72` for A1 (85% of seeds ended by 72 h).

## 4. Watch items, questions and decisions

**PLAYTEST-WATCHLIST additions** (for the coordinating session; this PR does not edit `docs/quality/`):
- Every victory hold broken in a profile, or every hold broken in under 30 min.
- One node flipping more than 4 times in a game hour.
- A raid war ended by an HQ capture with 3 or fewer participants.
- The coalition on its last strategic node for more than 6 h while that node is not the protected airbase.
- `night_cap` as the first reason in more than 20% of prime-50 windows.
- The Static pool at its storage cap for more than 30 min at BRAVO, which came back at raid S1 s1 while the Static was winning.

**OPEN-QUESTIONS rows filed with this review:** Q-TD-102 (broken hold keeps progress), Q-TD-103 (last-base freeze on any last node), Q-TD-104 (cap fade at prime), Q-TD-105 (low-participation HQ capture).

**Decisions (lead, owner may veto):**
- **NX-474 acceptance:** met for day 1, with two follow-ups. The day-2 freeze gap is Q-TD-103, and prime is rechecked in run T (Q-TD-104).
- **Q-TD-97:** S1 (0.02) overshoots. Take 0.01 as the 5b candidate, confirmed by T0 against T1. Defer crowd-scaled spend.
- **Q-TD-91 follow-up:** at 0.02, raid has resistance but no winnable hold. Judge run T by holds survived and steamroll share, not only by length.
- **Quiet-5 A2:** not a gate for 5b until a minimum n exists.
- **NX-466:** stays queued but not started until T is read.
- **Q-TD-79, Q-TD-90:** unchanged (strike-first and wait 30 ship in 5b).
