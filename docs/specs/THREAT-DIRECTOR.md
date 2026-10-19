# SPEC: Threat Director (Enemy AI)

Status: Approved (owner, 2026-10-19) · Tracker: NX-155…NX-169, NX-309, NX-317 · ADR-0007 · Inputs: P63–71, C14–39

## 1. Purpose
Keep every population level (the harness crowd profiles of 0, 5, 50, 150, 300 and 500 viewers, Q-ALN-42) interesting and fair, with an enemy that seems to adapt but stays deterministic and testable.

## 2. Inputs (enemy view only, FOW-4)
- **Coalition power** `CP` = Σ over currently tracked coalition units (last-known tracks feed only Recon utility, TD-5; Q-FOW-14) of the unit's value, smoothed with an EMA over `director.cp.ema_window_s` (PROPOSED 300 s, game time, Q-ALN-23). Only sensed facts count: no supply readiness and no account age (Q-TD-2); alt-account abuse is handled by moderation outside the sim.
- Frontline state, node ownership, and enemy stockpiles.
- **Threat memory:** decaying counters per category: `convoy_attacks`, `radar_strikes`, `node_losses_by_sector`, `recon_losses_by_sector` (`sead_activity` joins with SEAD in P4). The half-life is configurable (`director.memory.half_life_s`, default 30 min of game time, Q-ALN-23).

## 3. Tiers (with hysteresis; replaces overlapping headcount bands)
| Tier | Enter when CP ≥ | Exit when CP < | Character |
|---|---|---|---|
| PATTERN_OF_LIFE | — | — | Routine only: Recon, EscortConvoys, DecoyBlink and repositioning (DEFEND jobs at its own bases); Offensive only under the night progress cap (§5) |
| ALPHA | 0 | — | Patrols, probes, supply maintenance, at most 1 operation at a time |
| BRAVO | `director.tier.bravo_enter_cp` | `bravo_enter_cp × director.tier.exit_ratio` (PROPOSED 0.8) | Concentrated offensives on weak sectors, IADS with overlapping SAMs |

**Escalation rule (Q-TD-1): provocation decides when, coalition power decides how far.** Provocation (§5a) maps to a level: ≥ `director.provocation.escalate_threshold` = ALPHA, ≥ `director.provocation.bravo_threshold` = BRAVO, otherwise Pattern of Life; a level drops only when provocation falls below its threshold × `director.tier.exit_ratio` (the same hysteresis as CP). The config loader requires `bravo_threshold > escalate_threshold`. CP maps to a ceiling by the table above. Each decision window the tier moves **at most one step** toward min(provocation level, CP ceiling), and only after the minimum dwell.

**CHARLIE is parked (Q-TD-3):** the named, telegraphed theater offensive (Q-GD-22, Q-ALN-35) waits for a larger roster and theaters; its rules are in GAMEPLAY-LATER.

There's a minimum dwell of 10 min of game time per tier (`director.tier.min_dwell_s`, Q-ALN-23). Tier changes are announced on the overlay and in a sitrep.

## 4. Decision loop (every 60 s of game time, `director.window_s`, Q-ALN-23)
1. Compute CP and the tier, and decay threat memory.
2. Budget for this window = min(`director.budget.<tier>`, the summed surplus stock of Static bases above their starvation thresholds) (Q-TD-5, Q-TD-12). The rear source behind its HQ is **excluded**: it refills bases only by convoy, so starving the Static's convoys and bases really starves the director. Every operation costs budget once; GP-7 only decides where its units spawn. **Anti-spam (Q-TD-12):** at most `director.max_spawns_per_window` new units per window and at most `director.max_live_units.<tier>` live Static units. The budget is never more than the Static's real stock (shipped by convoy from its rear source; factories are parked, Q-GP-41) can pay for (Q-GD-30). Raiding its convoys, stock or factories starves the director. The only off-map source is an infinite rear source behind the Static's capturable HQ.
3. Generate candidate **operations** from the operation catalog (`content/operations.yaml`, CONFIG-AND-CONTENT §8a; Q-TD-7): Probe(sector), Recon(sector), Offensive(node), Retake(node), EscortConvoys(route), ReinforceIADS(sector) (first build: repair existing air-defense sites past Disabled; emission is DecoyBlink's; building new ones waits for GAMEPLAY-LATER §5a, Q-GP-46), StrikeBridge(edge), DecoyBlink(radar). (TheaterOffensive waits with CHARLIE, Q-TD-3.) Each candidate has a cost and preconditions.
4. Score each candidate (Q-TD-6) = `director.op_priority.<op>` × target-value multiplier (`director.score.target_value.<node_kind>`, TBD) × weakness multiplier (from the target's defense-HP fraction as last seen in the enemy view; TBD curve) × threat-memory multiplier (`1 + counter` for the operation's matching counter, 1 when none matches) × proximity multiplier (Q-TD-4, below) + a `director` RNG noise term; tuned in the harness, refined in playtests. The noise is what makes it unpredictable but replayable. **Order (determinism):** candidates are enumerated sorted by (operation id, target id), one `director` draw is made per candidate in that order, and selection is greedy by (score descending, operation id, target id) within the budget.
5. **Adaptive defense (C37):** each threat-memory counter raises the utility of the matching defensive operation. Convoys are sent with no escort at first, then escorts appear as `convoy_attacks` grows, and drop away again as it decays. Each adaptation is announced with an INTEL line, at sector level only: it never names a site or updates a facility marker, so it reveals intent, not positions or states (Q-FOW-17, FOG-OF-WAR FOW-13).
6. Select within budget. Optionally, the LLM advisor picks among the top-K (§6).
7. **Spawning (Q-TD-8):** units bought from the budget spawn by the coalition's rule (GAMEPLAY GP-7, parity) for location only; their cost is the operation's budget, never a second charge: at the Static base nearest the job whose stock exceeds its starvation threshold by the forward-deploy margin, otherwise at the rear source behind its HQ.
8. **Turn operations into jobs** (Q-GD-34, Q-GD-37): the director is the strategic layer only. It never moves units directly (exception: `DecoyBlink` sets a site's emission flag directly; it is not a job, FOW-11); each selected operation becomes the jobs its **template** lists (Q-TD-7; e.g. Offensive(node) = stage at the nearest Static base, then strike the node's defenses, then send ground units to capture; EscortConvoys = a follow order on each convoy) on the Static's own Tasking Board (GAMEPLAY §1b), and Static units take them with the same mechanics as Quorum units: claim leases, feasibility check, priority aging, slots and dedupe keys, deterministic assignment order, job dependencies (Q-GD-37). Parity: the Static gets the same job types and mechanics, with no unique powers; only the director may compose them into richer combinations.

**TD-1 (time and pauses, Q-CFG-8, Q-OPS-8, Q-OPS-9, Q-ALN-2, Q-ALN-3, Q-ALN-23, Q-ALN-24, Q-ALN-35, Q-ALN-36):** every director timer runs inside the sim. These are **game time** (Q-ALN-23): the decision window (`director.window_s`), tier dwell (`director.tier.min_dwell_s`), the CP EMA window, the threat-memory and provocation half-lives, the PoL periods (`director.pol.*_period_s`) and the night-progress cap (`campaign.night_progress_cap_nodes_per_h`, per game hour). The advisor deadline is counted in decision windows, so it is game time too. Static units carrying out the director's jobs move in world time, like every unit. While the campaign is paused for any reason (`STAFF`, broadcast offline `TECHNICAL`, weekly `MAINTENANCE`, owner `CEASEFIRE`), none of them advances and the director makes no decision (SIM-CORE SC-11). A `STAFF_DIRECTOR_OVERRIDE` sent while paused is rejected with `CAMPAIGN_PAUSED` (Q-ALN-24), as are advisor choices and GM commands other than a GM release (Q-ALN-36). Taunt naming cooldowns (TD-4) and the GM idle auto-release (§6a) are **not** sim timers: they run on a monotonic real clock outside the sim (Q-ALN-4).

**TD-2 (own view only, FOW-4, Q-GD-37 item 9):** CP, provocation, candidate generation, scoring and the jobs the director posts are computed only from `EnemyView` (plus what the Static suffers). Operation-template selectors resolve against `EnemyView`, using discovered markers for facilities (FOW-13); a selector that resolves to nothing drops the operation. The Static's board never holds a job that targets or references an entity outside that view.

**TD-5 (scouting, Q-SIM-11, FOW-10):** `Recon(sector)` is an ordinary operation. It becomes jobs for ordinary ENEMY recon units (`ENEMY_RECON_UAV`, Q-TD-13) under parity (GAMEPLAY §0), paid from the same window budget, visible to viewers and killable. It adds no information beyond what those units' sensors detect, so the director's picture of a sector improves only while a scout lives. Its utility rises with the age of the director's last-known tracks over the sector (FOG-OF-WAR FOW-6a) and falls with recent scout losses there (threat memory), plus the `director` RNG noise term like any candidate.

## 5. Low-population behavior
At 0 humans, the coalition AI garrison holds the line and the Static drops to **Pattern of Life** (§5a); the campaign clock keeps running: it never pauses for lack of humans (Q-GD-4 amended); only a pause with a reason stops it (TD-1, Q-ALN-3). With 0 humans the Static can never take the coalition's `forward_airbase` or bring the sanctuary below 1 defense HP (GAMEPLAY §9, Q-GP-28). Enemy progress is capped at `campaign.night_progress_cap_nodes_per_h` (PROPOSED 1 node per 6 h of game time, Q-ALN-23). While the CP ceiling is ALPHA, a proximity multiplier (`director.score.provocation_proximity`, TBD) favours operations in `last_provocation_sector` (director state, in the snapshot and hash; the sector of the most recent provocation the Static sensed, ties broken by sector id), so a lone viewer harassing one sector gets a local fight there while the rest of the map stays calm (Q-TD-4; never by headcount, TS-1).

## 5a. Pattern of Life (owner requirement, 2026-10-17)
When nobody is playing, **and when viewers first arrive**, the Static mounts no offensives beyond the night progress cap (Q-GP-44). It runs a believable **Pattern of Life (PoL)** that scouts can observe and learn from:
- **Routine scouting (Q-TD-2 owner note):** even with no provocation, the director keeps sending Recon operations (TD-5) on a PoL cadence, so it is always looking.
- **Maintenance only, never a swarm (Q-TD-11 owner note):** at Pattern of Life the director only replaces losses up to each base's garrison quota from the theater file (`garrison_quota` per base); it never grows its force net, however long the war is quiet. Its convoys at Pattern of Life carry only what that upkeep needs.
- Garrison rotations, patrol routes, supply convoys between its bases, radar on/off cycles (through DecoyBlink, FOW-11).
- **Repositioning between bases:** staging aircraft and ground units toward forward bases, refuel/rearm stops. Staging is how attacks are prepared, so a sharp scout can see an offensive coming (only within coalition sensor coverage or as SIGINT blobs, FOG-OF-WAR).

**Escalation is triggered by provocation, not headcount** (GAMEPLAY TS-1):
- A decaying `provocation` score rises with coalition actions the Static **senses or suffers**: losses or damage to its units, convoys and facilities, node flips, recon of its rear only when its sensors track the scout, and channel-point redemptions (TD-2, Q-FOW-15: nothing unsensed counts). **Only people provoke (Q-TD-11):** only actions by viewer units under player control count, plus redemptions; AI garrison, facility and AUTO actions add 0, so the Static never escalates against an empty stream.
- **Redemption weights (Q-AI-9, Q-ALN-13):** every redemption type has its own weight, `director.provocation.weights.redemption.<type>` (admin-tunable). There is **no offensive redemption class**: no redemption may deal damage (SUPPORT-REDEMPTIONS §4). Classes: support (supply drop, respawn skip, reserve-queue jump) = small weight; cosmetic (color, ping, shoutout, spectacle) = 0. Weight values are PROPOSED / TBD by harness.
- PoL → ALPHA → BRAVO follows the escalation rule in §3 (Q-TD-1).
- Going from 0 viewers to 1 changes **nothing** until that operator acts. They get time to observe and plan.
- With no provocation, the enemy decays back to PoL. Night-progress caps still apply (§5).

Config keys (CONFIG §6.7, all PROPOSED / TBD by harness): `director.pol.patrol_period_s`, `director.pol.convoy_period_s`, `director.provocation.weights.*` (including `.redemption.<type>`), `director.provocation.half_life_s`, `director.provocation.escalate_threshold`, `director.provocation.bravo_threshold`, `director.op_priority.<op>`, `director.score.*`. Routine Recon at Pattern of Life is scored like any operation; there is no separate cadence key.

## 6. LLM advisor (P4, optional)
- **Input:** a structured summary built from ids, sectors, counts and threat memory, plus the top-K candidate operations. It includes **no user strings** (SEC-LLM-4).
- **Output:** `{choice_index:int, op_name:str ≤ 40 chars, rationale:str ≤ 140 chars}`. The schema is validated, and the text is moderated.
- **Isolation and budget:** the advisor runs in its own isolated container and counts against the $20/month AI cap (LLM-ADVISORS LLM-2, LLM-3).
- **Deadline:** the answer must arrive within 2 decision windows. If it's late, invalid or over budget, the rules choose. The accepted choice enters as a logged command (ADR-0002).

## 6a. Game Master takeover (owner requirement)
The owner, or an admin with the `GAME_MASTER` permission, can take over the director (ADMIN-RBAC spec):
- **Scope (Q-AI-8, Q-ALN-10):** a GM drives the Static and triggers world events (TS-1), nothing else. World events may benefit the coalition (supply drop, weather clearing, friendly convoy) but must be visible and in-fiction. A GM never grants units, ammo or XP to specific players. Campaign setup (objectives, unlimited ammo and other campaign options) is owner/Admin only, never GM (GAMEPLAY §9c).
- **Job injection (Q-GD-37 item 11, Q-ALN-11):** a GM injects jobs into the **Static's board only**. An injection that targets the Quorum's board is rejected.
- **Modes (Q-TD-9):**
  - **ASSIST** (first GM release): the GM injects or vetoes operations while the rules keep running.
  - **FULL** (the next release after ASSIST; the owner wants it soon): the rules pause, and the GM issues operations from the same operation catalog.
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
- Q-AI-9, Q-ALN-13: a cosmetic redemption leaves `provocation` unchanged; a respawn skip or queue jump adds its (small) support weight.
- Q-ALN-11: a GM job injection into the Quorum's board is rejected; one into the Static's board is accepted and logged as a GM action.
- TD-3/TD-4: a taunt never names an operator whose `!quiet` opt-out is on (and may again after they toggle it off), never names the same operator twice inside the cooldown, and an LLM taunt prompt contains no callsign or chat text.
- Q-TD-1: zero provocation with high CP stays Pattern of Life; high provocation with CP below `bravo_enter_cp` caps at ALPHA; a Pattern of Life → BRAVO target steps through ALPHA with dwell; provocation oscillating inside the hysteresis band never flaps.
- Q-TD-2: CP is unchanged by an untracked coalition unit.
- Q-TD-4: after a sensed strike in sector S while the CP ceiling is ALPHA, the top candidate targets S.
- Q-TD-5/H3: a starved Static posts no operation it cannot fund (see Q-TD-12).
- Q-TD-6: same seed, same scores; a shuffled catalog load order gives the same selection.
- Q-TD-7: the operations loader rejects an unknown JobKind, an unknown precondition and an out-of-envelope cost.
- Q-TD-8: a Static spawn goes to the nearest qualifying base, else the rear source.
- Q-TD-9: an ASSIST veto drops the operation; a FULL takeover is rejected until FULL ships.
- TD-2: an unsensed coalition scout in the Static's rear adds no provocation.
- Threat memory decays.
- Golden scenarios: "convoy raids → escorts appear within N windows".
- Balance harness: tier dwell distribution per scenario.

## 8. Open questions
Decided and folded in: Q-GD-4 (amended), Q-GD-22, Q-GD-30, Q-GD-34, Q-GD-37, Q-AI-7, Q-AI-8, Q-AI-9, Q-RB-6, Q-RB-7, Q-OPS-8, Q-OPS-9, Q-CFG-8, Q-BRAND-4, Q-ALN-2, Q-ALN-3, Q-ALN-4, Q-ALN-10, Q-ALN-11, Q-ALN-12, Q-ALN-13, Q-ALN-17. Forward reference: Q-GD-38 (lieutenants, NX-317). Decided and folded in (2026-10-18, second batch): Q-ALN-23 (game time for the director's timers, TD-1), Q-ALN-24 (director overrides rejected while paused, TD-1). Decided and folded in (2026-10-18, third batch): Q-ALN-35 (CHARLIE warning lead time on game time, §3, TD-1), Q-ALN-36 (advisor choices and GM commands rejected while paused, TD-1), Q-ALN-42 (crowd profiles, §1). Nothing is open here. Decided in the 2026-10-19 grilling: Q-TD-1 to Q-TD-10 (OPEN-QUESTIONS, "THREAT-DIRECTOR grilling").
