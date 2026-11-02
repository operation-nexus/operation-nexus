# NOTES: Force economy (force scaling by economy)

Not normative; ECONOMY.md wins. This file holds the implementation narration, code pointers, history, decision trails and derived numbers moved out of ECONOMY.md (NX-415, W6), verbatim. Headings use ECONOMY.md's numbers; each entry names the source paragraph by its bold label where it has one.

## 1. Purpose

- Today the Static is capped at a fixed number of live units, and its window budget is a fixed number per tier. Harness #301 and #316-#318 show what follows. Crowds win by outnumbering the cap. The Static spends half its stock on an hour-1 surge and never recovers. No victory hold is ever contested. In short, every crowd win is a steamroll (Q-TEST-11 review).

## 3. Requirements

- **Cost parity sync (in code, NX-494; Q-TD-119 owner 2026-10-29, Q-TD-130 lead, owner may veto).** Owner text: "It should be maximum parity on both sides so we can have PVE, PVP, EVE, etc set up with little configuration. Of course settings should be configurable but yes, we can experiment with one sided cuts and try to make the game feel good, but have the ability to sync costs and cuts." Nothing in content or code says which enemy kind matches which coalition kind; only content comments did (`content/units/enemy-strike-fighter.yaml:2`, `enemy-recon-uav.yaml:2`).
- **Default.** The shipped paired values are already equal in all three tables (`balance/default.yaml:48-56, :388-406`), so the shipped config loads with the switch true and no event stream changes. The new key and catalog field move `config_hash` (`campaign_config.py:76-81`), so, as with NX-490, the three shipped-rules golden cases get new `case.json` hashes and re-pinned checkpoints, with every `event_count` and `events_hash` unchanged.
- **Surplus reference (NX-500; Q-TD-125 owner 2026-10-29: "yes your rec", (a); the details are Q-TD-132 (A), lead, owner may veto). In code (NX-500): `rules._supply` fixes R at load in `Supply.surplus_ref`, read only by `director.surplus`; `tests/core/test_surplus_ref.py`.** Before NX-500 "the surplus" was stock above the starvation floor (`director.surplus`, `director.py:94-101` now), so harness Y1 (`logistics.starve_threshold` 0.05) also raised the Static's budget per window, prime 147.1 → 163.8 (`docs/review/ENTERTAINMENT-X0-Y1-2026-10-29.md` H2).
- **Why the max.** A base never pays below its floor (EC-13 payment checks, `launch.py:877, :910-915`), so stock under the floor is never spendable. With the max, a floor lowered below the reference changes nothing in the Director's surplus (the owner's ask), and a floor raised above it still shrinks the surplus to what the bases can pay.
- **Why not the stock target.** `logistics.stock_target_frac` 0.8 gives 1,600 and 800 (`rules.py:911`): every Static base starts below it (1,000 and 500, `content/theaters/strait-1.yaml:32-35`), so the starting surplus would be 0 and every golden and harness result would change. It is also raised at staging bases (FS-3, `logistics.stock_targets`), which would make the budget move with staging.
- (from **EC-9a Broken-hold decay (NX-489; Q-TD-102 owner 2026-10-29, Q-TD-126 lead, owner may veto).**) Owner text: "it should hold partially and decrease slowly, and then decrease faster and eventually reset if it gets repaired/re-defended by the original owners". Before NX-489 a broken hold restarted from 0 (`campaign.hold_break: reset` keeps that rule).
- (from **Events (contracts, protocol 0.54).**) The overlay and narration render no hold event today (no consumer outside `nexus.core.campaign` and `tools/balance`), so showing the hold is a separate item, as NX-496 is for sitreps.
- **EC-9b Hold pause under pressure (NX-466; Q-TD-84 (b), owner 2026-10-28; readings Q-TD-134, lead, owner may veto). In code (NX-466: `pressure`, `_pause`, `_resume` and `_track_hold` in `nexus.core.campaign`; `tests/core/test_hold_pause.py`).** Before NX-466 a running hold gained 1 per running tick whatever happened at its nodes, and only a break stopped it.
- (from **Start tick (Q-TD-134 (5)).**) The cost is one credited tick per start (0.1 world s at `sim.tick_hz` 10).
- (from **Events (contracts; protocol 0.63).**) Today no overlay or narration consumer renders any hold event (EC-9a Events; outside `nexus.core.campaign`, `VictoryHold*` is read only by `tools/balance/metrics.py`; the overlay has only the generated type in `apps/overlay/src/contracts/events/event.ts`). Showing "hold paused" on screen and in a sitrep is therefore a follow-up, as NX-496 is for `ThreatAdaptation`.
- **Expected effect ([UNVERIFIED], not measured).** At raid-300, E0 had 14 holds, 8 of them broken (`docs/review/HARNESS-E0-E2-2026-10-30.md:17`). Holds that the Static contests without breaking should now take longer to win. At prime-50 no hold forms (same report, line 28), so nothing changes there. The harness lines in GAMEPLAY §11 (NX-466) measure the real effect.
- (from **EC-11 Coalition floor.**) In code (NX-412 part 5b): checked only with the coalition not unlimited (EC-15); the floor income is `economy.income.floor` alone, the AI garrison is the quotas of the theater's coalition-start nodes filled from `director.garrison.kinds` in turn, and the viewer kinds are the roles' (CONFIG-AND-CONTENT §6).
- (from **EC-15 Unlimited modes (owner, 2026-10-24, Q-TD-28).**) (Rollout: the shipped default was on until NX-412 part 5b, Q-TD-29; it is off since then, harness-tuned by U0 #510, lead note PR #517.)

## 5. Behavior

### 5.2 Why this fixes the steamroll (the intent, to be measured)

- A beaten Static keeps its floor and its shortest lines. It rebuilds an Offensive every few windows instead of collapsing (review: "economy collapses in hours 1-2 and never recovers").
- A crowd that sits idle pays upkeep, so supply work (haulers) gains real impact. That relieves the coalition's own "jobs full" bottleneck (review, A2).
- The final hold becomes a fight (EC-9), feeding Q-TEST-11 signal 2.

### 5.3 Worked example (shape only; numbers TBD)

- The Static holds its HQ and two airbases. Its income each window is the floor plus HQ + 2 × AIRBASE. The coalition takes one airbase. The Static's income and storage fall by one AIRBASE share. Its units based there re-home to the nearest friendly airbase, which now pays their upkeep. If that base runs dry, its AI units ground first (idle ones before busy ones), then the viewer units idle longest, and busy viewer units (holding a claimed job or following an order) last (EC-6). The next windows' budgets shrink in proportion, but the floor keeps them above zero while convoys get through.

## 8. Open questions

- Owner decisions: Q-TD-16..19, and Q-TD-20..26 (approved by the owner 2026-10-24). Q-TD-26 was changed by the owner to the one spawn rule with a viewer-spawn switch (EC-13). Q-TD-27 (owner): every value stays tunable (EC-14). Q-TD-28 (owner): unlimited modes per side (EC-15). The owner approved the spec as a whole on 2026-10-24. Numbers come from harness sweeps now that NX-411 has landed.
