# SPEC: Threat Director (Enemy AI)

Status: Draft · Tracker: NX-155…NX-169 · ADR-0007 · Inputs: P63–71, C14–39

## 1. Purpose
Keep every population level (0, 5, 50, 500 viewers) interesting and fair, with an enemy that seems to adapt but stays deterministic and testable.

## 2. Inputs (enemy view only, FOW-4)
- **Coalition power** `CP` = Σ over visible coalition units of the unit's value × its supply-readiness multiplier, smoothed with an EMA over 5 min. Commanders whose accounts are younger than `min_account_age` count at 0.5×, which limits alt-account abuse.
- Frontline state, node ownership, and enemy stockpiles.
- **Threat memory:** decaying counters per category: `convoy_attacks`, `radar_strikes`, `node_losses_by_sector`, `sead_activity`. The half-life is configurable (default 30 min).

## 3. Tiers (with hysteresis; replaces overlapping headcount bands)
| Tier | Enter when CP ≥ | Exit when CP < | Character |
|---|---|---|---|
| ALPHA | 0 | — | Patrols, probes, supply maintenance, at most 1 operation at a time |
| BRAVO | `cp_bravo` | `cp_bravo × 0.8` | Concentrated offensives on weak sectors, IADS with overlapping SAMs, counter-battery |
| CHARLIE | `cp_charlie` | `cp_charlie × 0.8` | Named theater offensive (e.g., "Operation Red Tempest") that needs combined arms |

There's a minimum dwell of 10 min per tier. Tier changes are announced on the overlay and in a sitrep.

## 4. Decision loop (every 60 s of sim time)
1. Compute CP and the tier, and decay threat memory.
2. Budget for this window = `tier_budget[tier]` − upkeep.
3. Generate candidate **operations** from the doctrine library: Probe(sector), Offensive(node), Retake(node), EscortConvoys(route), ReinforceIADS(sector), StrikeBridge(edge), DecoyBlink(radar), TheaterOffensive(plan). Each candidate has a cost and preconditions.
4. Score each candidate = utility(target value, weakness from the enemy view, threat memory) + a `director` RNG noise term. The noise is what makes it unpredictable but replayable.
5. **Adaptive defense (C37):** each threat-memory counter raises the utility of the matching defensive operation. Convoys are sent with no escort at first, then escorts appear as `convoy_attacks` grows, and drop away again as it decays. Each adaptation is announced with an INTEL line.
6. Select within budget. Optionally, the LLM advisor picks among the top-K (§6).

## 5. Low-population behavior
At 0 humans, the coalition AI garrison holds the line and the director stays in ALPHA. Progress is capped at `max_night_progress` (default 1 node per 6 h). With 1–3 humans, the director prefers targets near where those humans are acting, so a single viewer can be a hero without the whole map moving.

## 6. LLM advisor (P4, optional)
- **Input:** a structured summary built from ids, sectors, counts and threat memory, plus the top-K candidate operations. It includes **no user strings** (SEC-LLM-4).
- **Output:** `{choice_index:int, op_name:str ≤ 40 chars, rationale:str ≤ 140 chars}`. The schema is validated, and the text is moderated.
- **Deadline:** the answer must arrive within 2 decision windows. If it's late, invalid or over budget, the rules choose. The accepted choice enters as a logged command (ADR-0002).

## 7. Tests
- Tier hysteresis property: no flapping under oscillating CP.
- Budget never exceeded.
- Threat memory decays.
- Golden scenarios: "convoy raids → escorts appear within N windows".
- Balance harness: tier dwell distribution per scenario.
