# SPEC: Threat Director (Enemy AI)

Status: Draft · Tracker: NX-155…NX-169, NX-309, NX-317 · ADR-0007 · Inputs: P63–71, C14–39

## 1. Purpose
Keep every population level (the harness crowd profiles of 0, 5, 50, 150 and 300 viewers, Q-ALN-42) interesting and fair, with an enemy that seems to adapt but stays deterministic and testable.

## 2. Inputs (enemy view only, FOW-4)
- **Coalition power** `CP` = Σ over visible coalition units of the unit's value × its supply-readiness multiplier, smoothed with an EMA over `director.cp.ema_window_s` (PROPOSED 300 s, game time, Q-ALN-23). Commanders whose accounts are younger than `director.cp.new_account_age_h` count at `director.cp.new_account_weight` (PROPOSED 0.5×), which limits alt-account abuse.
- Frontline state, node ownership, and enemy stockpiles.
- **Threat memory:** decaying counters per category: `convoy_attacks`, `radar_strikes`, `node_losses_by_sector`, `sead_activity`. The half-life is configurable (`director.memory.half_life_s`, default 30 min of game time, Q-ALN-23).

## 3. Tiers (with hysteresis; replaces overlapping headcount bands)
| Tier | Enter when CP ≥ | Exit when CP < | Character |
|---|---|---|---|
| ALPHA | 0 | — | Patrols, probes, supply maintenance, at most 1 operation at a time |
| BRAVO | `director.tier.bravo_enter_cp` | `bravo_enter_cp × director.tier.exit_ratio` (PROPOSED 0.8) | Concentrated offensives on weak sectors, IADS with overlapping SAMs, counter-battery |
| CHARLIE | `director.tier.charlie_enter_cp` | `charlie_enter_cp × director.tier.exit_ratio` | Named theater offensive (e.g., "Operation Red Tempest") that needs combined arms |

**CHARLIE offensives are telegraphed** (Q-GD-22): visible massing and staging (to scouts/radar), then an INTEL warning naming the sector (lead time PROPOSED ~10 min; timing, lead time and severity all configurable), and only after real provocation (§5a), never against an empty stream.

There's a minimum dwell of 10 min of game time per tier (`director.tier.min_dwell_s`, Q-ALN-23). Tier changes are announced on the overlay and in a sitrep.

## 4. Decision loop (every 60 s of game time, `director.window_s`, Q-ALN-23)
1. Compute CP and the tier, and decay threat memory.
2. Budget for this window = `director.budget.<tier>` − upkeep, and never more than the Static's real stock and factory output can pay for (Q-GD-30). Raiding its convoys, stock or factories starves the director. The only off-map source is an infinite rear source behind the Static's capturable HQ.
3. Generate candidate **operations** from the doctrine library: Probe(sector), Offensive(node), Retake(node), EscortConvoys(route), ReinforceIADS(sector), StrikeBridge(edge), DecoyBlink(radar), TheaterOffensive(plan). Each candidate has a cost and preconditions.
4. Score each candidate = utility(target value, weakness from the enemy view, threat memory) + a `director` RNG noise term. The noise is what makes it unpredictable but replayable.
5. **Adaptive defense (C37):** each threat-memory counter raises the utility of the matching defensive operation. Convoys are sent with no escort at first, then escorts appear as `convoy_attacks` grows, and drop away again as it decays. Each adaptation is announced with an INTEL line.
6. Select within budget. Optionally, the LLM advisor picks among the top-K (§6).
7. **Turn operations into jobs** (Q-GD-34, Q-GD-37): the director is the strategic layer only. It never moves units directly; each selected operation becomes one or more jobs (stage, escort, strike, defend, reposition) on the Static's own Tasking Board (GAMEPLAY §1b), and Static units take them with the same mechanics as Quorum units: claim leases, feasibility check, priority aging, slots and dedupe keys, deterministic assignment order, job dependencies (Q-GD-37). Parity: the Static gets the same job types and mechanics, with no unique powers; only the director may compose them into richer combinations.

**TD-1 (time and pauses, Q-CFG-8, Q-OPS-8, Q-OPS-9, Q-ALN-2, Q-ALN-3, Q-ALN-23, Q-ALN-24):** every director timer runs inside the sim. These are **game time** (Q-ALN-23): the decision window (`director.window_s`), tier dwell (`director.tier.min_dwell_s`), the CP EMA window, the threat-memory and provocation half-lives, the PoL periods (`director.pol.*_period_s`) and the night-progress cap (`campaign.night_progress_cap_nodes_per_h`, per game hour). The advisor deadline is counted in decision windows, so it is game time too. The CHARLIE warning lead time is not assigned to a clock yet (§8). Static units carrying out the director's jobs move in world time, like every unit. While the campaign is paused for any reason (`STAFF`, broadcast offline `TECHNICAL`, weekly `MAINTENANCE`, owner `CEASEFIRE`), none of them advances and the director makes no decision (SIM-CORE SC-11). A `STAFF_DIRECTOR_OVERRIDE` sent while paused is rejected with `CAMPAIGN_PAUSED` (Q-ALN-24). Taunt naming cooldowns (TD-4) and the GM idle auto-release (§6a) are **not** sim timers: they run on a monotonic real clock outside the sim (Q-ALN-4).

**TD-2 (own view only, FOW-4, Q-GD-37 item 9):** CP, candidate generation, scoring and the jobs the director posts are computed only from `EnemyView`. The Static's board never holds a job that targets or references an entity outside that view.

## 5. Low-population behavior
At 0 humans, the coalition AI garrison holds the line and the Static drops to **Pattern of Life** (§5a); the campaign clock keeps running: it never pauses for lack of humans (Q-GD-4 amended); only a pause with a reason stops it (TD-1, Q-ALN-3). Enemy progress is capped at `campaign.night_progress_cap_nodes_per_h` (PROPOSED 1 node per 6 h of game time, Q-ALN-23). With 1–3 humans, the director prefers targets near where those humans are acting, so a single viewer can be a hero without the whole map moving.

## 5a. Pattern of Life (owner requirement, 2026-10-17)
When nobody is playing, **and when viewers first arrive**, the Static does not attack. It runs a believable **Pattern of Life (PoL)** that scouts can observe and learn from:
- Garrison rotations, patrol routes, supply convoys between its bases, radar on/off cycles.
- **Repositioning between bases:** staging aircraft and ground units toward forward bases, refuel/rearm stops. Staging is how attacks are prepared, so a sharp scout can see an offensive coming (only within coalition sensor coverage or as SIGINT blobs, FOG-OF-WAR).

**Escalation is triggered by provocation, not headcount** (GAMEPLAY TS-1):
- A decaying `provocation` score rises with coalition actions: strikes on Static units or convoys, captures, recon of its rear, and channel-point redemptions.
- **Redemption weights (Q-AI-9, Q-ALN-13):** every redemption type has its own weight, `director.provocation.weights.redemption.<type>` (admin-tunable). There is **no offensive redemption class**: no redemption may deal damage (SUPPORT-REDEMPTIONS §4). Classes: support (supply drop, respawn skip, reserve-queue jump, extra `!scout` ping) = small weight; cosmetic (color, ping, shoutout, spectacle) = 0. Weight values are PROPOSED / TBD by harness.
- PoL → ALPHA → BRAVO → CHARLIE transitions need provocation **and** coalition power above thresholds, with hysteresis and minimum dwell (§3).
- Going from 0 viewers to 1 changes **nothing** until that operator acts. They get time to observe and plan.
- With no provocation, the enemy decays back to PoL. Night-progress caps still apply (§5).

Config keys (CONFIG §6.7, all PROPOSED / TBD by harness): `director.pol.patrol_period_s`, `director.pol.convoy_period_s`, `director.provocation.weights.*` (including `.redemption.<type>`), `director.provocation.half_life_s`, `director.provocation.escalate_threshold`.

## 6. LLM advisor (P4, optional)
- **Input:** a structured summary built from ids, sectors, counts and threat memory, plus the top-K candidate operations. It includes **no user strings** (SEC-LLM-4).
- **Output:** `{choice_index:int, op_name:str ≤ 40 chars, rationale:str ≤ 140 chars}`. The schema is validated, and the text is moderated.
- **Isolation and budget:** the advisor runs in its own isolated container and counts against the $20/month AI cap (LLM-ADVISORS LLM-2, LLM-3).
- **Deadline:** the answer must arrive within 2 decision windows. If it's late, invalid or over budget, the rules choose. The accepted choice enters as a logged command (ADR-0002).

## 6a. Game Master takeover (owner requirement)
The owner, or an admin with the `GAME_MASTER` permission, can take over the director (ADMIN-RBAC spec):
- **Scope (Q-AI-8, Q-ALN-10):** a GM drives the Static and triggers world events (TS-1), nothing else. World events may benefit the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction. A GM never grants units, ammo or XP to specific players. Campaign setup (objectives, unlimited ammo, friendly fire and other campaign options) is owner/Admin only, never GM (GAMEPLAY §9c).
- **Job injection (Q-GD-37 item 11, Q-ALN-11):** a GM injects jobs into the **Static's board only**. An injection that targets the Quorum's board is rejected.
- **Modes:**
  - **ASSIST:** the GM injects or vetoes operations while the rules keep running.
  - **FULL:** the rules pause, and the GM issues operations from the same operation library.
- **Constraints:** GM operations are still validated against the tier budget and preconditions. A GM *may* exceed the budget only with an explicit `override_budget` flag, which is audited.
- **Logging:** every GM action is a logged `STAFF_*` command, so replays stay deterministic (ADR-0002), and is flagged as a GM action in replays (Q-AI-8).
- **On stream:** a "COMMAND: GAME MASTER" badge is always visible while a human GM is in control, on every layout including 9:16 (Q-ALN-17; DATA-INTEGRITY DI-5: never disguise human control as AI or vice versa).
- **Threat memory keeps learning** during a FULL takeover, so control returns to an up-to-date director (Q-RB-6).
- **Voice:** GM lines use the distinct Game Master voice profile (AUDIO-TTS §2a, Q-RB-7).
- **Auto-release:** if the GM goes idle beyond a configured timeout (monotonic real time, measured outside the sim, Q-ALN-4), control returns to the rules, with a logged `GM_RELEASED{reason}`.

## 6b. Mastermind and taunts (Q-AI-7, Q-BRAND-4)
- **Name:** the Quorum's intelligence codename for the Static's mastermind is NULL (shown e.g. "SIGNAL SOURCE: NULL"). Code, config, contracts and logs refer to it by an internal id, never the literal string or value `null`. The display name is content, not code.
- **TD-3 Naming operators:** a taunt may name one operator only through a `{target}` placeholder that code fills with that operator's approved callsign. The text around it is a template before P4; from P4 the LLM may write the line but never sees names or chat text (SEC-LLM-4). Operators whose `!quiet` opt-out is currently on are never named; `!quiet` is a toggle stored per commander and applies across linked platforms (GAMEPLAY §3, Q-ALN-12).
- **TD-4 Naming cooldown:** the same operator is named at most once per `taunt.name_cooldown_min` (PROPOSED 10); spotlight operators (recent hero events or high recent action) use `taunt.name_cooldown_spotlight_min` (PROPOSED 5). Both are admin-configurable and run on a monotonic real clock, enforced outside the sim (Q-ALN-4).
- **Tone:** playful rivalry; never an insult about the person.

## 6c. Lieutenants (P4, Q-GD-38, NX-317)
Owner direction, details PROPOSED: NULL commands through lieutenants, each a **director profile** (a config preset of priorities, aggression, preferred operations and taunt voice) using the same mechanics (parity). Each sector or operation is run by one lieutenant. Briefings name the lieutenant when known; otherwise the HUD shows UNIDENTIFIED until recon or captured comms reveal it. Specced in NX-317; nothing here changes the P1 director.

## 7. Tests
- Tier hysteresis property: no flapping under oscillating CP.
- Budget never exceeded, and never above what the Static's real stock can pay for (Q-GD-30): a starved Static posts no operation it cannot fund.
- TD-1: golden scenario with a pause mid-window: every director field (tier, dwell, threat memory, provocation, window progress) is unchanged from the pause tick to the resume tick, no operation is posted in between, and a `STAFF_DIRECTOR_OVERRIDE` sent during the pause is rejected (Q-ALN-24). With `sim.time_scale` ≠ 1, the decision window and tier dwell take the same number of ticks as at 1 (Q-ALN-23).
- TD-2: property: every job on the Static's board references only entities in `EnemyView`.
- Q-AI-9, Q-ALN-13: a cosmetic redemption leaves `provocation` unchanged; a respawn skip, queue jump or extra scout ping adds its (small) support weight.
- Q-ALN-11: a GM job injection into the Quorum's board is rejected; one into the Static's board is accepted and logged as a GM action.
- TD-3/TD-4: a taunt never names an operator whose `!quiet` opt-out is on (and may again after they toggle it off), never names the same operator twice inside the cooldown, and an LLM taunt prompt contains no callsign or chat text.
- Threat memory decays.
- Golden scenarios: "convoy raids → escorts appear within N windows".
- Balance harness: tier dwell distribution per scenario.

## 8. Open questions
Decided and folded in: Q-GD-4 (amended), Q-GD-22, Q-GD-30, Q-GD-34, Q-GD-37, Q-AI-7, Q-AI-8, Q-AI-9, Q-RB-6, Q-RB-7, Q-OPS-8, Q-OPS-9, Q-CFG-8, Q-BRAND-4, Q-ALN-2, Q-ALN-3, Q-ALN-4, Q-ALN-10, Q-ALN-11, Q-ALN-12, Q-ALN-13, Q-ALN-17. Forward reference: Q-GD-38 (lieutenants, NX-317). Decided and folded in (2026-10-18, second batch): Q-ALN-23 (game time for the director's timers, TD-1), Q-ALN-24 (director overrides rejected while paused, TD-1). Still open: the clock (world or game time) for the CHARLIE warning lead time (§3), which Q-ALN-23 does not list.
