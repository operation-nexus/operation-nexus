# W7 design review: what the stock number does, where its roles couple, and the raid stall

Read-only design review (W7, NX-415), 2026-11-02, against develop at fcf5505. The lead checked the upkeep, resupply-posting and repair-job claims against the code.
Citations are `file:line` from that tree. Paths: `core/` = `services/sim/src/nexus/core/`.
Anything the code or harness data does not show is marked **[HYPOTHESIS]** or **[UNVERIFIED]**.

## 0. Facts that frame everything below

- There are three stock numbers, not one:
  1. **Per-node stock**: `World.stock[node]`, finite bases only (`core/world.py:736-738`).
  2. **Per-side source pool**: `World.pool[side]`, the sanctuary of a limited side (`core/world.py:739-742`; `core/economy.py:52-59`).
  3. **Storage cap**: `World.storage[side]`, derived from the nodes a side owns, not from stock (`core/economy.py:39-43`).
- **Upkeep is 0 for every kind in the shipped config** (`balance/default.yaml:396-405`, "rollout placeholder 0"). G2 and J0 ran shipped rules (`docs/review/HARNESS-J0-2026-11-02.md:7`, `HARNESS-H0-H3-G2-2026-11-01.md:50`), and the raid-300 profile sets no economy override (`tools/balance/profiles.yaml:28`). So in the stalled runs, grounding (EC-6), the upkeep reserve (EC-7) and shortfall sitreps did nothing. Any stall story built on upkeep is ruled out for G2/J0.
- **Unload is counted twice by design.** One delivered unit both adds 1 stock and rebuilds `defense_repair_hp_per_stock` = 2 hp (`core/logistics.py:412-421`; GAMEPLAY §8 items 7-8).
- **Rearm and repair at a sanctuary are free.** They do not touch the pool; only finite nodes are debited (`core/rearm.py:11-12, 130-132`). The pool pays truck loads, spawns and upkeep only.
- **GAMEPLAY already lists the five uses of the starvation floor** (`docs/specs/GAMEPLAY.md:541-554`), and NX-500 already split off one of them, the Director's surplus (ECONOMY EC-7 items 78-85, `docs/specs/ECONOMY.md:156-170`). At the shipped `surplus_ref_frac` 0.25 the split is inert: the reference equals the floor (`balance/default.yaml:288`).

## 1. Roles table

| # | Role | Reads | Reader (file:line) | Spec rule | Config keys |
|---|---|---|---|---|---|
| R1 | Director budget, base term | stock above `surplus_ref` at the side's bases | `core/director.py:94-101, 139-146` | ECONOMY EC-7 items 69-70; TD §4 step 2 | `director.spend_frac.*`, `surplus_ref_frac` |
| R2 | Director budget, rear term | pool × `source_spend_frac` | `core/director.py:104-106`; `core/launch.py:141-145` | EC-7 item 71 | `director.source_spend_frac` (0.01) |
| R3 | Cadence floor and capture-slot cap, convoy gate, convoy/capture purse | surplus (R1) + rear account | `core/director.py:119-127`; `core/launch.py:343-347, 492, 564, 582-589` | EC-7 items 73-75, 82 | `director.cadence_windows` |
| R4 | Operation payment (EC-13): a base pays only above its floor, else the pool | stock − floor; pool | `core/launch.py:864-877, 905-917`; `core/logistics.py:339-348` | EC-13 items 183-186; TD §7a items 126-129 | `logistics.starve_threshold` / `starve_floor_*` |
| R5 | Launch base and garrison convoy shortfall (`Own.margin`) | stock − floor | `core/launch.py:225-229`; `core/operations.py:640-656` | GAMEPLAY §5 item 43; TD §5a item 178 | as R4, `director.pol.convoy_*` |
| R6 | Forward deploy / spawn location (both sides, JOIN included) | stock − floor ≥ max(min surplus, loadout) | `core/logistics.py:284-300, 311-337` | GP-7; GAMEPLAY §5 item 43 | `forward_deploy_min_surplus` (50), `loadout_cost.*` |
| R7 | Starved state: a fuel cap and guns-only rearm | stock < floor | `core/rearm.py:103-106, 155-200` | GAMEPLAY §5 item 40 | `starved_loadout.fuel_frac` |
| R8 | Starvation drain of defense hp, and through it the capture gate and the EC-9b pause | stock < floor | `core/defense.py:133-147`; `core/capture.py:255`; `core/campaign.py:266-267` | GAMEPLAY §8 items 2, 9; EC-9b 2) (Q-TD-134 (1), (2)) | `starve_hp_drain_per_min` (5), `capture.requires_defenses_down` |
| R9 | Rearm/repair payment (fuel, ammo, unit and facility hp) | stock, down to 0 (not to the floor) | `core/rearm.py:122-153, 206-245` | GAMEPLAY §5 items 74-75, §5b item 11 | `rearm_rate`, `repair_rate.*`, `loadout_cost.*`, `facility_repair_hp_per_stock` |
| R10 | Hauling demand: resupply job, urgency, slots | (floor − stock)/floor; stock < target | `core/tasking_gen.py:371-392, 417-427` | GAMEPLAY §1b, §5 LC-3, items 78-79 | `stock_target_*`, `tasking.stock_urgency`, `resupply_slots_max*` |
| R11 | Keep: what a source never ships below | floor or target | `core/logistics.py:234-244, 199-214`; `core/tasking.py:1416-1435` | GAMEPLAY §5 item 42 (Q-SIM-102) | as R10 |
| R12 | Logistics cadence triggers (LC-1 AI trucks; LC-2 Static demand convoys) | source stock − floor; any base < floor | `core/ai_trucks.py:118-121`; `core/launch.py:441, 452-459` | GAMEPLAY §5 LC-1, LC-2 | `ai_trucks.period_s`, `director.pol.convoy_demand_s` |
| R13 | Refuel routing (hops, capped tank) | stock > 0; starved | `core/tasking.py:1461-1514` | GAMEPLAY §5 (Q-TD-88) | as R7 |
| R14 | FS-3 staging lift of the stock target | target raised by staged op costs | `core/logistics.py:247-268`; `core/launch.py:553-554` | TD §4a items 53-54 | `director.staging.*` |
| R15 | Pool as payer: truck loads, source spawns, upkeep at the source, JOIN `NO_STOCK` | pool | `core/logistics.py:354-360`; `core/upkeep.py:221-234`; `core/handlers.py:354-362` | EC-1, EC-4, EC-13 | `economy.unlimited.*`, `free_viewer_spawn` |
| R16 | Storage cap and clip; income | nodes owned; a capture bar zeroes a node's income | `core/economy.py:39-50, 87-104` | EC-1, EC-2 | `economy.income.*`, `economy.storage.*` |
| R17 | Defense rebuild | each unit unloaded | `core/logistics.py:403-427`; `core/defense.py:108-111` | GAMEPLAY §8 items 7-8 (Q-SIM-71) | `defense_repair_hp_per_stock` (2) |
| R18 | Capture transfers stock: it stays with the node | stock | `core/capture.py` (no stock write; GAMEPLAY §8 item 78) | GAMEPLAY §8 item 78 | — |
| R19 | Momentum supply fill | coalition stock / max | `core/campaign.py:121-131`, read only by `tools/balance/metrics.py:505` | Q-SIM-60 | `campaign.momentum.supply_weight` |
| R20 | Upkeep, grounding, reserve | stock / pool at home | `core/upkeep.py:181-234`; `core/director.py:142` | EC-4..6, EC-7 item 69 | `economy.upkeep.*` (**all 0 shipped**) |

R19 has no feedback into the sim (HUD and metrics only). R20 is dormant at the shipped values.

## 2. Coupling map and feedback loops

Shared inputs: **R1, R3** read stock above the reference. **R4-R8, R10-R12** read the floor. **R9** reads raw stock down to 0. **R17** writes hp from the same unload that writes stock. **R2** reads the pool, whose size is set by **R16** (ownership), not by stock flows.

| Loop | Mechanism | Intended? |
|---|---|---|
| L1 Raid starves the Director | The coalition kills convoys or takes a base: base stock falls or moves to the captor (R18), so R1 and R3 fall | **Intended**: TD §4 step 2 ("Raiding its convoys, stock or factories still starves the director"); EC-7 item 72; GAMEPLAY:79 |
| L2 A fight at a Static base cuts the Director's budget | Its units rearm and repair from that base's stock (R9), so surplus R1 falls while provocation raises the tier and `spend_frac` (×2.67 from ALPHA to BRAVO, `balance/default.yaml:283-286`) | **Emergent.** No rule ties rearm draws to the budget. It follows from R1 and R9 sharing the number |
| L3 Starvation becomes a victory signal | A hold node is drawn below the floor by R9 (busy combat), then R8 drains its hp to 0. It enters `defense_down`: (a) the Static may start a capture bar; (b) EC-9b pauses the hold; (c) the Offensive's weakness multiplier peaks (`core/operations.py:492-498`) | (b) **intended**: EC-9b 2) "A starvation drain to 0 also … counts" (Q-TD-134, lead reading, owner may veto); GAMEPLAY §11 item 95. The chain from (a) to (c) is **emergent** |
| L4 Defense repair rides on the stock signal | DEFENSES_DOWN ends only at full hp (`docs/specs/GAMEPLAY.md:1290`). Hp comes only from unloads (R17). A non-sanctuary node gets a resupply job only for a stock deficit or damaged facilities (`core/tasking_gen.py:378-384`; `facility_damage` counts facilities, not node defense, `core/logistics.py:221-231`). A down node at stock ≥ target posts no job, so no truck is sent to rebuild it. Restoring an AIRBASE from 0 takes 500 hp / 2 = 250 units, 2.5 truck loads (`balance/default.yaml:104, 45, 71`) | **Emergent.** Only the sanctuary has a defense-repair job (NX-497, `core/tasking_gen.py:403-414`) |
| L5 Captured stock funds the captor and its repairs | R18 moves base stock between the Director's R1 and the coalition's R9/R10. NX-471 seized facilities repair from that stock ("no stock, no progress", `HARNESS-I0-I1-2026-11-01.md:15`). I1 starved node-minutes +22% are "consistent with seized sites drawing repair stock" (`:52`) | Stock moving with the node is **intended** (GAMEPLAY §8 item 78). The coupling to the Director's budget is **emergent** |
| L6 An un-raidable floor under the Director | The pool refills at `income.floor` 30 plus the income of held nodes each window (`balance/default.yaml:381-387`). The rear is never struck (Q-SIM-64). R2 scales with the storage cap, which is ownership (R16). Convoys move pool into HQ stock (R15, then R1), outside the rear-share cap. With the Static's start nodes, cap = 2000 + 2×1000 + 2×2000 = 8000 (`content/theaters/strait-1.yaml:32-35`, `default.yaml:389-394`), so R2 = 80 a window, above OFFENSIVE's cost of 60 (`content/operations.yaml:12`) | **Intended**: EC-7 item 72 "a Static holding only its rear can still act"; EC-9 item 93 hold response "from the rear if needed". The size of the floor is a placeholder (`default.yaml:381` "NX-412 sweep") |
| L7 Contested nodes earn nothing | A capture bar zeroes a node's income (R16) | **Intended**: EC-1 |
| L8 Hauling demand rises with storage | R10's slots scale with max − stock | **Intended**, and measured: H0→H1 stocking job-min ×1.9 (`HARNESS-H0-H3-G2-2026-11-01.md:34`) |

The two loops that matter for raids both run through the **floor**, not through the Director's budget:
- **L3**: combat consumption, then starvation, then pause or capture.
- **L4**: defense hp has no demand signal of its own.

L6 means the Static never runs dry while it holds its HQ.

## 3. Link to the stall evidence

**What the data shows:**
- Stall rate is 2 of 12 in G2 (s1, s10) and in J0 (s8, s9) (`HARNESS-H0-H3-G2-2026-11-01.md:55`; `HARNESS-J0-2026-11-02.md:11`).
- The stalled seeds are the busiest:
  - J0 s8/s9 hold 141 of 200 Offensives and 554 of 852 A2 newbies, with idle at 5-6% (`HARNESS-J0:32`).
  - G2 s1/s10 have idle at 3-7% (`HARNESS-H0-H3-G2:58-61`).
- Pauses are pooled over the 12 G2 seeds: holds paused by CAPTURE_BAR 10, CAPTURE_OP 10, DEFENSES_DOWN 18 (`:56`). DEFENSES_DOWN is the most common reason. No per-seed split is quoted.
- G0 vs G1: with the pause on, starved node-minutes were 529 against 296 (`HARNESS-G0-G1-2026-10-30.md:29`), and there were 97 Offensives against 25 (`:22`).
- NX-471 changed which seeds stall, not how often (`HARNESS-J0:11`; LESSONS L-46).
- With upkeep 0, the economy reaches the stall only through stock, the floor and the pool.

**Not shown by any review:**
- Per-seed Static budget, rear/base split or no-launch reasons.
- Pause reasons per stalled seed.
- Whether hold nodes were starved when they went down.

The metrics already record the budget per hour (`tools/balance/metrics.py:183-184, 395-396`) and the no-launch reasons (`core/launch.py:359-411`; `tools/balance/report.py:464`). The report pools them (`report.py:492-549`).

**Hypotheses**, in order of how well the code supports them:
- **H1 [HYPOTHESIS]: L4 keeps DEFENSES_DOWN pauses long.**
  - In a busy fight the Static strikes hold nodes to 0 often (97 Offensives with the pause on, G0).
  - Each down node pauses the hold until it is rebuilt to full.
  - Rebuild happens only as a side effect of a stock job. That job may not exist (stock ≥ target), or may sit at stocking urgency below 1.0 behind other jobs (`core/tasking_gen.py:15-21`).
  - Harness bots give no orders (`HARNESS-J0:38`; `profiles.yaml:33`, JOIN and REBASE only), so no human sends a truck to a down node.
  - Test: per-seed DEFENSES_DOWN paused minutes in s8/s9 against the won seeds.
- **H2 [HYPOTHESIS]: L3 turns busy combat into downs without a hit.**
  - More combat means more R9 draws at forward nodes, so more starvation (529 vs 296), then drain, then DEFENSES_DOWN.
  - Test: split `NodeDefensesDown` on hold nodes by cause (drain tick vs hit). The data does not record the cause today; `defense_down` keeps none (EC-9b 2)).
- **H3 [HYPOTHESIS]: L6 means the Static never runs out of capture operations during a hold.**
  - The stall then depends on the coalition's repair rate, not the Static's money.
  - Weak support: 67-74 Offensives in 24 h is about 3 an hour, far below what the rear share alone could fund at cap 6000+. Budget is probably not the binding limit, but this is [UNVERIFIED] until the per-seed budget and no-launch reasons are read.
- **H4: the lead's own hypothesis** (`HARNESS-J0:38`): personas without orders are what keep busy fights open. H1 is one concrete path for it.

## 4. Options

**O0. Do nothing in code until the harness personas give orders (W7), but read the data first.**
- **What changes:** nothing in the sim. Pull per-seed budget, no-launch reasons, pause reasons and paused minutes for J0 s8/s9 vs the won seeds from the existing per-run metrics. Then re-run raid-300 at 12+ seeds once personas give orders.
- **Separates:** nothing; it tells H1-H4 apart.
- **Size:** 0 spec. A small report or script change if the per-seed split is not printed (est. <50 lines in `tools/balance/report.py`) [estimate].
- **Determinism and goldens:** none.
- **Harness test:** J0 data re-read, then a raid-300 rerun with 12 seeds with ordering personas.
- **Risk:** the stall stays at 2 in 12 meanwhile. The owner accepted that under Q-TD-136 (a) (`docs/planning/OPEN-QUESTIONS.md:195`).

**O1. Give node defense hp its own hauling demand (splits R10 from R17).**
- **What changes:** the board posts a resupply job for an owned node below full defense hp, at least while it is in `defense_down` or is a hold node, whatever its stock. Urgency comes from the missing-hp share, like the sanctuary job (`core/tasking_gen.py:403-414`), and the job is done at full hp. Behind a switch (Q-CFG-16 style).
- **Separates:** "this node needs defenses" from "this node needs stock" (L4).
- **Size:** GAMEPLAY §1b/§8 plus one balance key (add-config-key skill). About 40-80 lines in `tasking_gen.py`, `ai_trucks.py` and tests [estimate].
- **Determinism and goldens:** deterministic (sorted nodes, integer shares). New `JobCreated` events, so every golden with a down node regenerates.
- **Harness test:** an A/B at one sha with the switch on and off: raid-300 at 12 seeds (stall rate, per-seed DEFENSES_DOWN minutes) plus prime-50 (stocking job-min, deliveries/h, starved).
- **Risks:**
  - More trucks at the front, which runs against the owner's hauling-demand concern (H0/H1).
  - It may end stalls by making holds harder to contest, which partly undoes NX-466's gain (G0 vs G1).
  - Parity: the Static's board gets the same job (EC-3).

**O2. Record why defenses went down; let EC-9b count only hit-caused downs (splits R8 from the victory signal).**
- **What changes:** `defense_down` records a cause (HIT or STARVED) when it is entered. `campaign.pressure` ignores STARVED (or a switch chooses). The capture gate (R8a) and the drain stay as they are.
- **Separates:** the starvation floor from the hold clock (L3 (b)).
- **Size:** reverses the lead reading Q-TD-134 (1)/(2) in EC-9b 2) and GAMEPLAY §11 item 95. About 30-60 lines plus a snapshot field and a schema version bump (`core/world.py` versions list, `:71-106`) [estimate].
- **Determinism and goldens:** deterministic. A snapshot change means goldens regenerate. Event streams change only where a drain downed a hold node.
- **Harness test:** first the H2 cause split, as instrumentation only. Ship the rule change only if starvation downs are a material share of DEFENSES_DOWN pause minutes in stalled seeds.
- **Risk:** a starving hold node no longer pauses the hold, so the coalition's logistics matter less to winning. That is a design trade the owner should make.

**O3. Base the Director's budget on flow, not stock level (splits R1/R3 from R9 and R18).**
- **What changes:** the base term of EC-7 is computed from what reached Static bases (convoy deliveries per window, smoothed), not from stock above the reference. Stock stays only the payment constraint (R4).
- **Separates:** a fight at a base no longer cuts the budget through rearm draws (L2), and a capture no longer swings it by the captured stock (L5). Raids still starve it, because killed convoys deliver nothing.
- **Size:** large. An ECONOMY EC-7 rewrite, TD §4 step 2 and §7a items 5-16, `director.py` budget, `launch.py` purses, a re-tune of `spend_frac`, and a sweep. Est. 150-300 lines plus spec [estimate].
- **Determinism and goldens:** deterministic if integer. Every golden and every Director event stream changes.
- **Harness test:** the NX-412 sweep set (operations per hour, gaps, Offensives) plus raid-300 at 12 seeds.
- **Risks:**
  - The largest change.
  - The H3 evidence suggests the budget is not what binds in stalls, so it may not touch the stall at all.
  - It loses the legible "stock is the budget" (Q-TD-12).

**O4. Outcome-level fallback, not a decoupling: Q-TD-136 (b) or (c), a cap on pause time.**
- **What changes:** a hold runs regardless after N paused minutes (total or single pause).
- **Separates:** nothing; it caps the symptom.
- **Size:** EC-9b plus 1-2 keys, about 30 lines [estimate].
- **Determinism and goldens:** deterministic; raid goldens with long pauses change.
- **Harness test:** raid-300 at 12 seeds.
- **Risk:** the owner already chose (a). A cap leaves L3 and L4 in place and only bounds them.

## 5. Recommendation and owner questions

**Recommendation:**
1. Do **O0 now**. Read J0 s8/s9 against the won seeds for:
   - DEFENSES_DOWN paused minutes;
   - pause reasons;
   - the Static budget and no-launch reasons per seed.

   Add the down-cause instrumentation from O2 to the harness metrics (no rule change) so the next run can tell H1 from H2.
2. If DEFENSES_DOWN minutes dominate the stalled seeds, take **O1** behind a switch and A/B it at 12 seeds (L-46: rates need 12+ seeds).
3. Take **O2** only if drain-caused downs are a material share.
4. Park **O3** unless budget turns out to be binding.
5. Keep **O4** as the backstop the owner already holds.

Upkeep-related couplings (R20) need a separate review once upkeep values ship. Today they are 0.

**Owner questions** (one line each):
1. **O0 first:** may the lead read J0's per-seed data and add down-cause instrumentation (no rule change) before choosing a fix? (yes/no)
2. **O1:** should a down node's defenses get their own truck job even when its stock is fine, behind a switch, default off until an A/B? (yes/no)
3. **O2 / Q-TD-134 veto:** should a hold keep pausing when a node's defenses drained to 0 from starvation rather than enemy fire? (keep / hits only)
4. **O3:** should the Director's money stay "the stock in its bases" (Q-TD-12), or is a delivery-rate budget open for study? (keep / study)
5. **L6:** is it intended that the Static can always fund capture operations from its un-raidable rear while it holds its HQ, so only an HQ capture or the coalition's repair rate can end a contested raid? (yes / cap it)
