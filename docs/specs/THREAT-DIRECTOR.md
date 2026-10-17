# SPEC: Threat Director (Enemy AI)

Status: Draft · Tracker: NX-155…NX-169 · ADR-0007 · Inputs: P63–71, C14–39

## 1. Purpose
Keep every population level (0, 5, 50, 500 viewers) interesting and fair, with an enemy that seems to adapt but stays deterministic and testable.

## 2. Inputs (enemy view only, FOW-4)
- **Coalition power** `CP` = Σ over visible coalition units of the unit's value × its supply-readiness multiplier, smoothed with an EMA over `director.cp.ema_window_s` (PROPOSED 300 s). Commanders whose accounts are younger than `director.cp.new_account_age_h` count at `director.cp.new_account_weight` (PROPOSED 0.5×), which limits alt-account abuse.
- Frontline state, node ownership, and enemy stockpiles.
- **Threat memory:** decaying counters per category: `convoy_attacks`, `radar_strikes`, `node_losses_by_sector`, `sead_activity`. The half-life is configurable (default 30 min).

## 3. Tiers (with hysteresis; replaces overlapping headcount bands)
| Tier | Enter when CP ≥ | Exit when CP < | Character |
|---|---|---|---|
| ALPHA | 0 | — | Patrols, probes, supply maintenance, at most 1 operation at a time |
| BRAVO | `director.tier.bravo_enter_cp` | `bravo_enter_cp × director.tier.exit_ratio` (PROPOSED 0.8) | Concentrated offensives on weak sectors, IADS with overlapping SAMs, counter-battery |
| CHARLIE | `director.tier.charlie_enter_cp` | `charlie_enter_cp × director.tier.exit_ratio` | Named theater offensive (e.g., "Operation Red Tempest") that needs combined arms |

**CHARLIE offensives are telegraphed** (Q-GD-22): visible massing and staging (to scouts/radar), then an INTEL warning naming the sector (lead time PROPOSED ~10 min; timing, lead time and severity all configurable), and only after real provocation (§5a), never against an empty stream.

There's a minimum dwell of 10 min per tier. Tier changes are announced on the overlay and in a sitrep.

## 4. Decision loop (every 60 s of sim time)
1. Compute CP and the tier, and decay threat memory.
2. Budget for this window = `director.budget.<tier>` − upkeep.
3. Generate candidate **operations** from the doctrine library: Probe(sector), Offensive(node), Retake(node), EscortConvoys(route), ReinforceIADS(sector), StrikeBridge(edge), DecoyBlink(radar), TheaterOffensive(plan). Each candidate has a cost and preconditions.
4. Score each candidate = utility(target value, weakness from the enemy view, threat memory) + a `director` RNG noise term. The noise is what makes it unpredictable but replayable.
5. **Adaptive defense (C37):** each threat-memory counter raises the utility of the matching defensive operation. Convoys are sent with no escort at first, then escorts appear as `convoy_attacks` grows, and drop away again as it decays. Each adaptation is announced with an INTEL line.
6. Select within budget. Optionally, the LLM advisor picks among the top-K (§6).

## 5. Low-population behavior
At 0 humans, the coalition AI garrison holds the line and the Static drops to **Pattern of Life** (§5a); the campaign clock keeps running (Q-GD-4 amended, no automatic pause). Enemy progress is capped at `campaign.night_progress_cap_nodes_per_h` (PROPOSED 1 node per 6 h). With 1–3 humans, the director prefers targets near where those humans are acting, so a single viewer can be a hero without the whole map moving.

## 5a. Pattern of Life (owner requirement, 2026-10-17)
When nobody is playing, **and when viewers first arrive**, the Static does not attack. It runs a believable **Pattern of Life (PoL)** that scouts can observe and learn from:
- Garrison rotations, patrol routes, supply convoys between its bases, radar on/off cycles.
- **Repositioning between bases:** staging aircraft and ground units toward forward bases, refuel/rearm stops. Staging is how attacks are prepared, so a sharp scout can see an offensive coming (only within coalition sensor coverage or as SIGINT blobs, FOG-OF-WAR).

**Escalation is triggered by provocation, not headcount** (GAMEPLAY TS-1):
- A decaying `provocation` score rises with coalition actions: strikes on Static units or convoys, captures, recon of its rear, and redemptions with an effect.
- PoL → ALPHA → BRAVO → CHARLIE transitions need provocation **and** coalition power above thresholds, with hysteresis and minimum dwell (§3).
- Going from 0 viewers to 1 changes **nothing** until that operator acts. They get time to observe and plan.
- With no provocation, the enemy decays back to PoL. Night-progress caps still apply (§5).

Config keys (CONFIG §6.7, all PROPOSED / TBD by harness): `director.pol.patrol_period_s`, `director.pol.convoy_period_s`, `director.provocation.weights.*`, `director.provocation.half_life_s`, `director.provocation.escalate_threshold`.

## 6. LLM advisor (P4, optional)
- **Input:** a structured summary built from ids, sectors, counts and threat memory, plus the top-K candidate operations. It includes **no user strings** (SEC-LLM-4).
- **Output:** `{choice_index:int, op_name:str ≤ 40 chars, rationale:str ≤ 140 chars}`. The schema is validated, and the text is moderated.
- **Isolation and budget:** the advisor runs in its own isolated container and counts against the $20/month AI cap (LLM-ADVISORS LLM-2, LLM-3).
- **Deadline:** the answer must arrive within 2 decision windows. If it's late, invalid or over budget, the rules choose. The accepted choice enters as a logged command (ADR-0002).

## 6a. Game Master takeover (owner requirement)
The owner, or an admin with the `GAME_MASTER` permission, can take over the director (ADMIN-RBAC spec):
- **Modes:**
  - **ASSIST:** the GM injects or vetoes operations while the rules keep running.
  - **FULL:** the rules pause, and the GM issues operations from the same operation library.
- **Constraints:** GM operations are still validated against the tier budget and preconditions. A GM *may* exceed the budget only with an explicit `override_budget` flag, which is audited.
- **Logging:** every GM action is a logged `OP_*` command, so replays stay deterministic (ADR-0002).
- **On stream:** a "COMMAND: GAME MASTER" badge is shown while a GM is active (DATA-INTEGRITY DI-5: never disguise human control as AI or vice versa).
- **Threat memory keeps learning** during a FULL takeover, so control returns to an up-to-date director (Q-RB-6).
- **Voice:** GM lines use the distinct Game Master voice profile (AUDIO-TTS §2a, Q-RB-7).
- **Auto-release:** if the GM goes idle beyond a configured timeout, control returns to the rules, with a logged `GM_RELEASED{reason}`.

## 7. Tests
- Tier hysteresis property: no flapping under oscillating CP.
- Budget never exceeded.
- Threat memory decays.
- Golden scenarios: "convoy raids → escorts appear within N windows".
- Balance harness: tier dwell distribution per scenario.
