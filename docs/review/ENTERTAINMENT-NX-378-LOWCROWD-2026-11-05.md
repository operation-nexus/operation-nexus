# Entertainment review: NX-378, P1 exit, low-crowd focus, 2026-11-05

The owner asked for this review in the Q-TEST-13 answer (#412, 2026-11-05): "low crowds are going to be more common than high crowds … do an entertainment analysis on how to ensure even a solo viewer can be engaged and have fun. This could mean that we enable limited coalition AI strikes?"

Method: [`docs/quality/ENTERTAINMENT-REVIEW.md`](../quality/ENTERTAINMENT-REVIEW.md). P1 is headless, so every audience score is an estimate. Tags: [INFERENCE] means reasoned from data; [UNVERIFIED] means not checked.

## 1. Evidence

**Q0b #648.** Sha 8f814e6, config hash `1920af11…`. 6 profiles × 10 seeds × 72 h, shipped rules. The full report is on the issue; the BALANCE-LOG entry is the Q0b entry.

**Probe 1 (cause of the A2 tail).**
- prime-50, seeds 1–2, 3 h, stand-alone, at d9298f1.
- Same config hash as Q0b: between 8f814e6 and d9298f1 nothing changed in `nexus/core`, balance, content or `tools/balance`.
- Shorter than the queue run, so it is used to explain the mechanism, never for pooled numbers (L-39).

**Probe 2 (solo viewer).**
- An ad hoc `solo-1` profile (1 veteran viewer, auto-tasked, no further arrivals) in a scratch tree only. 2 seeds × 6 h, same config hash.
- No standard profile has a single viewer.

**Not available:**
- the per-kind A2 split at 72 h, and who wins on points at TIME_LIMIT (both only in Q0b's `report.json` on the harness PC);
- any event-by-event timeline;
- anything rendered.

**Structural fact: the coalition has no mobile AI unit.**
- Coalition `AI_GARRISON` entities are only the facilities (`runtime/campaign_config.py`) and the AI trucks. THREAT-DIRECTOR-NOTES says "The coalition has no mobile AI unit yet."
- `garrison_quota` exists only on Static bases (`content/theaters/strait-1.yaml`).
- So two rules have no unit to act on: GAMEPLAY §1b "garrison joins strike jobs a player started", and the Q-GD-31 counterattack.

## 2. How the 72 h war plays, by crowd

### 0 viewers (overnight-0)
- **What happens:** steady ambient traffic, about 9.5 recon flights and 8 patrols per hour per seed. A STAGING sitrep appears every 360 min like clockwork.
- **The Static's Offensives go nowhere:** 119 Offensives → 37 strikes fired → 1 defenses-down → 0 captures. Momentum ends at 51.1 %.
- **Coalition kills are 100 % by its air-defense sites.** [INFERENCE] The night strikes die on the coalition's SAMs.
- **"The war waits" is a good promise but a flat show.** Q-TD-71 (owner) asked that overnight progress be "slow but should still occur", about one flip per 12 h. Q0b shows 0 flips in 720 seed-hours.

### 1 viewer (solo probe, 6 h)
- **The solo always has a job:** auto-tasked, 0 % idle armed time.
- **Hour 1:** the solo provokes ALPHA (53 and 40 min). The Static answers with 4 Offensives per seed, 3 capture bars and 0 captures.
- **Hours 2–6:** back to Pattern of Life, with 266–268 min stretches without an Offensive, while the solo keeps killing (10 and 5 kills).
- **Why it calms down:** [INFERENCE] provocation halves every 900 s and ALPHA needs 10 points, so one jet can't keep the Static awake.
- **The solo can never take a node:** a capture needs the defenses struck down and then a truck. One unit can't do both, and no AI jet exists to help.

### 5 viewers (quiet-5)
- **Plenty of work:** 3.16 open slots per unit, so every viewer matters.
- **Pacing:** about one capture by either side every 4 h. Coalition defenses go down about every 72 min. Bursts of Offensives are followed by dry spells (median 227 min, max 668).
- **No arc:** 0 victory holds, momentum 50.6 %, every seed ends at TIME_LIMIT. About 0.2 clip-ready signals per hour.

### 50 viewers (prime-50)
- **The busiest low profile:** a capture about every 78 min. SANCTUARY_AT_RISK 0.76 per hour, STRIKE_DOWNED 0.51 per hour.
- **The worst arc:** the Static is ahead (momentum 36.3 %) and grinds for 72 h, with no hold, no defeat run and no last stand.
- **Ending:** the result is decided on points at the limit. Which side wins on points per seed is [UNVERIFIED].

### Scores (estimates, 1–5)
| Audience | overnight-0 | solo-1 | quiet-5 | prime-50 |
|---|---|---|---|---|
| Watcher | 2.5 | 2.5 | 3 | 3.5 |
| Player | – | 2.5 | 2.5 | 3 |
| Site watcher | 1.5 | 2 | 2.5 | 2.5 |
| VOD / clip | 1 | 2 | 2 | 3 |

## 3. Why 5 and 50 stall

### 5 viewers: the Static isn't allowed to win, and five people can't
- **The low-population brake** (THREAT-DIRECTOR §5) spaces Static flips about 5.4 h apart at 5 live units. It blocked capture launches in 34,677 decision windows. [INFERENCE] That is about 80 % of all windows.
- **The coalition retakes about as many as it loses:** 10.1 per seed against 8.2. Its captures need a long truck drive after a jet drops the defenses.
- **Victory needs 6 of 8 strategic nodes held for 30 min.** The coalition starts with 3 and never reaches 6.
- **People, not money, are the limit:** both pools are full, and most coalition kills (85 %) come from SAMs.

### 50 viewers: the brake is gone, the Static is at full strength, and 50 can take ground but can't supply or hold it
- **The brake fades to nothing** at `capture.quiet_ref` 50.
- **The Static attacks constantly:** 1,128 Offensives and 196 captures. It also earns more: 1,811 income per hour against the coalition's 1,207.
- **Coalition supply breaks down:**
  - 862 starved node-minutes per run;
  - more starving resupply job-minutes (7,040) than stocking ones (6,336);
  - 668 defenses-down events.
- [INFERENCE] **prime-50 sits exactly where the brake reaches 0.**

## 4. Suggestions

**Design changes:**
- **D1. Human-led AI wingmen.** A viewer's strike pulls up to N [AI] jets, and N fades to 0 by `quiet_ref`. Chosen (Q-GP-50).
- **D2. Stalemate breaker.** An HQ strike when the war has been flat for N hours; only viewer trucks capture. Deferred.
- **D3. A goal for the solo while the Static is quiet.** A hint line ("The Static is quiet. Hit its scouts or convoys to draw it out"), without the raw provocation number. P2 overlay text.
- **D4. Scout and capture-run first impact.** See §5.

**Tuning (balance keys; one same-sha A/B each):**
- **T1.** `capture.quiet_ref` 50 → 100.
- **T2.** `director.provocation.half_life_s` 900 → about 2,700.
- **T3.** Overnight drift up to the Q-TD-71 target. A causal probe comes first, because 82 of 119 night strikes never fire. Chosen (Q-TD-143).
- **T4.** `logistics.ai_trucks.max_live` 3 → higher, for prime-50 starvation.

**Not recommended:** AI strikes scaled by crowd that still run at 0 viewers. They would move the war while nobody watches, which goes against Q-GD-4, Q-GP-44, Q-TD-14 and the "never ends while chat is asleep" promise.

## 5. A2: cause and fixes

**Probe 1 (n = 26, mechanism only):** the tail is 4 of 26, all from two persona kinds.
- Scouts: 2 of 2, with no impact at all.
- Capture runs: 2 of 3, median 1,601 s.
- Auto, striker and hauler newbies: 0 % tail.

**Why [INFERENCE]:** scouts and capturers are 20 % of newbies at every profile, so those two kinds alone put about 17 % in the tail, above the 10 % limit. This needs confirming with Q0b's `A2.by_persona_kind`.
- A capture run carries no cargo, so it has no "departure" impact like a hauler.
- A scout scores only a track no one has seen, and a busy front has none left.

**At 72 h the tails are higher (34–36 % at prime and evening).** Auto newbies probably also slow down as starvation builds [UNVERIFIED]. At raid and surge the cause is board capacity (Q-TD-98).

**Fixes chosen by the owner (Q-TEST-14):**
- a coalition sector-scout job, with refreshing a stale track counting as a scout's impact;
- capture runs that start from the nearest friendly forward base with spare stock (forward deploy, Q-GP-41);
- A2's 10 % tail rule unchanged.

## 6. Owner decisions (2026-11-05, in chat)
| Question | Decision | Row | Item |
|---|---|---|---|
| Limited coalition AI strikes | Human-led AI wingmen: up to 2 [AI] jets join a viewer's strike job, fading to 0 by `quiet_ref` (50 live viewer units); never without a human lead; AI kills don't provoke | Q-GP-50 | NX-511 |
| A2 fix | Both: coalition sector-scout job (refreshing a stale track counts) and capture runs from the nearest friendly forward base; A2's 10 % tail unchanged | Q-TEST-14 | NX-512, NX-513 |
| Overnight drift | Tune to about 1 flip per 12 h at 0 viewers (Q-TD-71), causal probe first, keeping A3 and the A1 no-collapse rule | Q-TD-143 | NX-514 |
| Low-crowd ending | Keep 72 h; add "final hours" sitreps and a countdown push so the points finish is a visible climax | Q-UX-23 | NX-515 |

Lead follow-ups (no owner decision needed):
- queue the T1, T2 and T4 A/Bs after the glide days;
- read Q0b's `report.json` for `A2.by_persona_kind` and the per-seed winner at TIME_LIMIT;
- note in GAMEPLAY §1b that the garrison-joins and counterattack rules have no coalition unit until NX-511;
- spec D3's hint line with the overlay work.
