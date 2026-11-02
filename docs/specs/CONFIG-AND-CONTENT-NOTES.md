# NOTES: Configuration, Balance & Content

Not normative; CONFIG-AND-CONTENT.md wins. This file holds the implementation narration, code pointers, history, decision trails and derived numbers moved out of CONFIG-AND-CONTENT.md (NX-415, W6), verbatim. Headings use CONFIG-AND-CONTENT.md's numbers; each entry names the source paragraph by its bold label where it has one.

## 6. Balance schema: key reference

### 6.2 Slots, respawn, reserve

- (from "In the schema now ...") The runtime host loop that calls it is not wired yet.

### 6.3 Logistics

- Economy (ECONOMY, approved 2026-10-24; keys added by NX-412 with `add-config-key`; `unlimited`, `window_s`, `income.*` and `storage.*` in the schema and read by `nexus.core.economy` since NX-412 part 1, `upkeep.*` read by `nexus.core.upkeep` since part 2, the rest not in the schema yet; superseded: every §6.3 `economy.*` row is in `contracts/config/balance.json`).

### 6.5 Capture

- In code since NX-125: all ten keys are the `capture` block of `balance/default.yaml` (`contracts/config/balance.json`), read by `nexus.core.capture`; the shipped values are the PROPOSED column. `capture.time_mult` and `capture.extra_exponent` are in code since NX-490.

### 6.6 Campaign

- In code since NX-126: the `campaign` block of `balance/default.yaml` (`contracts/config/balance.json`) holds `time_limit_h`, `victory_node_frac`, `victory_hold_min`, `objective_period_min`, `objective_mode` (read from the balance profile until a per-campaign setting exists), `score.average_weight`, `score.final_weight`, `score.objective_points` and `momentum.nodes_weight` and `supply_weight`; `nexus.core.campaign` reads them. The three durations are game time, converted once at load (`game_ticks`, with the key's unit: 72 h = 2,592,000 ticks, 30 min = 18,000, 15 min = 9,000 at 10 Hz). `target_duration_h`, `max_extension_h`, `defeat`, `options`, `intermission`, `rubber_band_zone` and the night cap are not read yet (superseded for `defeat` and the night cap: `runtime/campaign_config.py` reads both, NX-157, Q-TH-7).
- Status labels moved out of CONFIG-AND-CONTENT.md (the rules after each stay there, with the ids): In code since NX-374:

### 6.7 Threat Director

- (from "In code since NX-155 ...") `advisor.top_k` has no code yet.
- (from "Rule options, part 2b ...") `tasking.ai_jobs` replaced the kernel's last job-kind literal for the garrison (`_GARRISON_JOBS`). `tests/core/test_rule_options.py` covers each.
- Status labels moved out of CONFIG-AND-CONTENT.md (the rules after each stay there, with the ids): In code since NX-155 (Threat Director part 1):; In code since NX-156 (part 2):; In code since NX-157 (part 3):; In code since NX-382 part 2 (Q-SIM-96):

## 7. Unit catalog (`content/units/*.yaml`, `content/weapons.yaml`, `content/roles.yaml`)

- (from **What exists now (NX-367, Q-CFG-10).**) `crew` is read by part 2 (CB-8). `homes_on_emitters` joins with SEAD (§5.3a). The rest of the schema below joins with its readers: `display`, `category` and icons with the overlay; cargo and the remaining stats with NX-122.

### 7.1 Schema

- **Mirrors (PROPOSED, in code, NX-494; Q-TD-130 lead, owner may veto):** `mirrors` pairs an ENEMY kind with its COALITION counterpart for cost parity (ECONOMY EC-3, `economy.cost_parity`). The field is part of the catalog hash, so it moved `config_hash`.

## 8a. Operation catalog (`content/operations.yaml`, Q-TD-7)

- (from "The director's operations are ...") In code since NX-156: the schema is `contracts/config/operations.json`, the loader `nexus.runtime.operations`, and the shipped file is Q-SIM-81.
- (from **Cost envelope (Q-TD-7; NX-412 part 3, ECONOMY §4).**) The old envelope, the largest tier budget, was deleted with the tier budgets in NX-488.

## 14. Open questions

- Decided and folded in (2026-10-17): Q-GD-5 (48 h target), Q-GD-6 (cap + visible reserve queue), Q-GD-7 (`campaign.defeat`), Q-GD-9 (hand-authored first theater), Q-GD-11 (`logistics.truck_bridge_repair_mult`), Q-PROG-3 (account age 24 h at 0.5×), Q-CFG-1…Q-CFG-7 (see [OPEN-QUESTIONS](../planning/OPEN-QUESTIONS.md)), Q-CFG-6 (`audio.night_mode.hours`), Q-GW-1 (per-class rate limits).
- Decided and folded in (2026-10-18): Q-CFG-8 (CFG-9, CFG-10), Q-TEST-2 (header note), Q-PROG-6 (distinct-humans progression gate removed), Q-PROG-7 (§5a), Q-PROG-8, Q-PROG-9, Q-GD-35, Q-GD-37, Q-AI-7, Q-AI-9, Q-UX-11, Q-SUP-7, Q-GW-2, Q-OPS-8, Q-OPS-9, Q-ARCH-16, Q-BRAND-5 / Q-LEGAL-4 (§10.2a).
- Decided and folded in (spec-alignment batch, 2026-10-18): Q-ALN-1 (world vs game time, CFG-9; the §6.6 campaign and objective timers are game time), Q-ALN-3 (pause reasons), Q-ALN-4 (taunt cooldowns, GM idle auto-release, redemption cooldowns and the supply-drop cap are real time), Q-ALN-5 (respawn is game time), Q-ALN-6 (round up to ticks), Q-ALN-8 (old idle-despawn key removed), Q-ALN-10 (campaign options are owner/admin only), Q-ALN-13 (no offensive redemption class), Q-ALN-14 (no rank revocation).
- Decided and folded in (spec-alignment batch 2, 2026-10-18): Q-ALN-18 (Top Commanders in `hud.rotation.panels`), Q-ALN-22 (GMs draft rank/XP presets; Owner/Admin approve and apply, §5a), Q-ALN-23 (clocks for the capture, Tasking Board, night-progress and Threat Director keys in §6 and for the FoW timers, CFG-9), Q-ALN-24 (a reload requested while paused is deferred until resume, §5).
- Decided and folded in (spec-alignment batch 3, 2026-10-18): Q-ALN-35 (CHARLIE warning lead time is game time, CFG-9), Q-ALN-38 (Tier 1 FoW refresh re-expressed in world time, CFG-9), Q-ALN-42 (harness crowd profiles, header note).
