# SPEC (draft): Harness persona agency, the tactician mode

Status: Draft (owner sign-off needed before any code) · Tracker: NX-321 (player personas, "tactician") under NX-031 (balance harness) · Related: TESTING-STRATEGY §3.5, `tools/balance/README.md` "Persona kinds (Q-SIM-95)", FOG-OF-WAR FOW-10, Q-SIM-104, Q-TD-136, Q-TD-140

**Where it lives:** this Draft sits in `docs/review/` until the owner signs it off; then it moves to a new row and paragraph in `tools/balance/README.md` §"Persona kinds (Q-SIM-95)" (README.md:164), plus the key comment in `profiles.yaml`'s header. Reason: every existing persona kind (capturer Q-SIM-104, freelancer NX-398) is specified there and in `profiles.yaml:13-22`, not in `docs/specs/`; TESTING-STRATEGY §3.5 only names the populations. 

## 1. Purpose
1. Test whether a crowd that pushes where the fight is changes the stalled raids, using only what a real viewer can send and see.
2. Evidence: in K1, the stalled raid seeds s8 and s9 see-saw over the strategic nodes Static armor reaches within the 30-minute hold (cross-n 22 losses, cross-s 21, fob-n-e 12, fob-s-e 13, east-airbase 9), and lose 73 of the run's 97 strategic-node losses (`docs/review/HARNESS-K1-2026-11-02.md`).
3. No won seed ever drops below 3 of 8 strategic nodes; s8 reaches 7+ for at most 15.1 min at a stretch, s9 never (HARNESS-K1).
4. Static armor was among the capturers in 88 of the 97 losses, and 39 losses had a jobless capturer (`docs/review/HARNESS-K2-2026-11-02.md`); the addendum traces it to expired CAPTURE jobs leaving armor parked at the target (HARNESS-K2, Q-TD-140).
5. K0 rules out hold pauses as the cause and names persona agency as "the main untested factor" (`docs/review/HARNESS-K0-2026-11-02.md`); K1 asks for this spec (HARNESS-K1).

## 2. What exists today (code read 2026-11-03)
- Chat commands with a handler: only `JOIN` and `REBASE` (`services/sim/src/nexus/core/handlers.py:550-558`; `CommandKind` in `contracts/common/enums.json:29`); `SYS_*` and `STAFF_*` are not chat (COMMAND-CATALOG §4). `!target`, `!rtb`, `!me` are catalog rows with no schema or handler yet (`docs/specs/COMMAND-CATALOG.md:18-21,28`). No chat parser is in the repo (no `services/gateway`), so the harness builds the typed models directly (`tools/balance/personas.py:79-113`).
- `JOIN` targets: a role (STRIKE, RECON, LOGI; NAVY rejected) and `target` = null, a `node_id`, or a `follow_entity_id`; `hold` only with a null target (`contracts/commands/join.json:44-58`, `handlers.py:373-379`).
- A STRIKE JOIN on a node goes there and, on arrival, orbits it and engages by CB-1 until bingo, ammo out or `tasking.order_dwell_s` 600 s (`services/sim/src/nexus/core/tasking.py:13-18`, `balance/default.yaml:242`). A LOGI JOIN on an enemy node is a capture run, on a friendly node a delivery (GAMEPLAY §1b items 22-23).
- A viewer with a live unit cannot retarget: a second JOIN is `UNIT_IN_SORTIE` (`handlers.py:378-379`), and an accepted REBASE parks the unit on HOLD (`handlers.py:114-125`; rebase_prob is 0 for that reason, `tools/balance/profiles.yaml:46-48`). So agency acts only at JOIN and re-JOIN.
- Kinds today: auto, striker, hauler, scout, capturer, freelancer (`tools/balance/profiles.py:16`); strikers pick a seeded node among defended foes, capturers among capturable foes at 0 defense HP (`tools/balance/runner.py:41-61,114-128`, `personas.py:52-55`).

## 3. Scope and non-goals
- In scope: a `tactician` mode on the existing `striker` and `capturer` kinds that picks its JOIN node by the rules in §4; one `profiles.yaml` key; report counters.
- Harness only: `tools/balance/` (personas.py, runner.py, profiles.py, profiles.yaml, report.py, README.md). No change to `services/sim/src/nexus/core/`, `balance/*.yaml` config keys, `contracts/` or content.
- Out of scope, needs a new command (rule 6a, CC-2): redirecting a live unit (`TARGET`), recalling it (`RTB`), a crowd rally point (`RALLY`, reserved, COMMAND-CATALOG:36).
- Out of scope: follow targets, new roles, changing kind shares or the auto/hauler/scout kinds, a rule on own-unit density (no own-side view exists to cite, see Q4).

## 4. Behaviour
1. A viewer is a tactician when its kind is `striker` or `capturer` and a separate seeded draw is below `agency.share`.
2. The draw uses its own RNG, `random.Random(f"balance/agency/{profile}/{seed}/{index}")`, so kinds, persona draws and every other viewer's stream stay as today.
3. A tactician decides at every JOIN it sends (arrival and re-JOIN), from the inputs in §5 only.
4. A tactician never sends a command other than the JOIN its kind already sends (striker STRIKE, capturer LOGI, `kind_roles`, `profiles.yaml:62`).
5. Capturer tactician, rule 1: among today's capturer candidates (foe-held, capturable, 0 defense HP, `runner.py:47-61`) restricted to strategic nodes, it targets the one the coalition lost most recently.
6. A node "lost" is one with a public `NodeCaptured{from: COALITION, to: ENEMY}` this run; the latest such event's tick ranks it.
7. Capturer tactician, rule 2: with no lost strategic node among the candidates, it makes today's capturer pick.
8. Striker tactician, rule 1: among coalition-owned strategic nodes with a public `CaptureStarted{side: ENEMY}` in the last `agency.threat_window_s`, it targets the most recent one (a friendly node: orbit and engage, §2).
9. Striker tactician, rule 2: else, among coalition-owned strategic nodes with defense HP 0 in the coalition's view, it makes a seeded pick.
10. Striker tactician, rule 3: else it makes today's striker pick.
11. Ties on tick are broken by `v.rng.choice` over the tied node ids, sorted.
12. Every pick a tactician falls back from is counted, so the report shows how often each rule fired.

## 5. Inputs the bot may read
- Node owners, positions and defense HP: `nexus.core.fog.side_view(world, "COALITION")`, fields `owners`, `nodes`, `defense_hp` (`services/sim/src/nexus/core/fog.py:409-441`); public node state per FOG-OF-WAR FOW-10 (`docs/specs/FOG-OF-WAR.md:21`). The overlay frame contract does not exist yet (`contracts/wire/` holds only `hello.json`), so `side_view` is the source.
- The strategic node list: `world.rules.strategic` (AIRBASE, FOB, PORT, `services/sim/src/nexus/core/rules.py:178`), map data a viewer sees.
- Public events from `step`'s output, already passed to `_Crowd.react` (`runner.py:130-140`): `NodeCaptured` (public, ENEMY participants omitted, `contracts/events/node_captured.json`) and `CaptureStarted` ("Public view: none (nodes are always visible)", `contracts/events/capture_started.json:5`).
- Not read: Static jobs, boards, director state, enemy units outside `side_view.tracks`, or any `World` field outside the above.

## 6. Profiles and numbers (all PROPOSED, harness inputs, not game balance)
- `agency.share`: 0.5 of striker and capturer viewers (raid-300 has 0.1 + 0.1 of 300, `profiles.yaml:28`, so about 30 tacticians). 0 reproduces today exactly.
- `agency.threat_window_s`: 300 game s; K2's addendum says an empty base flips in about a minute (HARNESS-K2), so a shorter window would rarely catch a bar.
- Report: `viewers.tacticians` and `viewers.agency_picks` by rule (`retake`, `capture_started`, `defenses_down`, `fallback`).

## 7. Determinism
- All decisions use the viewer's own seeded RNG and the agency RNG of §4.2; candidate lists are sorted by node id before any pick (as `runner.py:44,55-61`).
- The event memory (last loss tick and last ENEMY `CaptureStarted` tick per node) is a dict keyed by node id, read only through `sorted()`.
- No wall clock (runner reads `time.perf_counter` only for `timing` and step time, `runner.py:217,225-228,251`); commands still go through `step` and the command log, so `replay_log` rebuilds the run (`runner.py:283-292`).
- Test: with `agency.share` 0 every seed's `final_state_hash` equals the run without the change; with the PROPOSED share two runs of one seed match.

## 8. Acceptance (12-seed raid-300 A/B, 24 h, one sha, shipped rules)
- Arm A: `agency.share` 0; arm B: the PROPOSED share. Seeds 1-12, as K0-K2.
- Arm A must reproduce K2's outcomes and final state hashes if no sim, balance, contract or content file changed (e.g. s8 `243874bac559a998`, s9 `f2f7703f4fe03234`, HARNESS-K2); else it is the new baseline.
- Compare per seed on K1's columns: outcome (and victory time), minutes at 7+ of 8 strategic nodes, longest stretch at 7+, strategic node losses (HARNESS-K1); also A2 and idle share, so agency doesn't buy a hold by idling players.
- Report the per-node loss split for the K1 contested set (cross-n, cross-s, fob-n-e, fob-s-e, east-airbase).
- Read (lead, then owner): does B give s8 or s9 a 30-minute stretch at 7+, and does any won seed lose its win or turn into a steamroll (NX-411 S1-S4)? No pass/fail threshold is set; this A/B informs, it doesn't gate.

## 9. Risks
- Agency is late by design: a viewer only chooses at JOIN, and a jet from the sanctuary may arrive after a one-minute flip; rule 1 of the capturer (retake) then matters more than defence.
- Whether an orbiting coalition aircraft blocks an ENEMY capture bar is [UNVERIFIED]; it helps only by killing armor.
- Overlap with the board's own `retake:<node>` job (GAMEPLAY §0 item 16): tacticians and autos may pile on one node; the A/B shows it.
- Q-TD-140 (leftover Static armor) is open; if (b) lands, the A/B must be rerun, since it changes what the bots push against (HARNESS-K2).
- Herding: 30 viewers on one node may starve other fronts; the per-node loss split shows it.

## 10. Open questions for the owner (lead's recommendation first)
1. Mode on striker/capturer, or a new `tactician` kind with its own share? Rec: mode; share 0 is then byte-identical to today and the other kinds' shares don't move.
2. `agency.share` 0.5 for the B arm? Rec: yes, one A/B; sweep 0.25/1.0 only if B moves the stalled seeds.
3. Apply agency in all profiles or only raid-300 for now? Rec: key on every profile, 0 everywhere except the A/B run.
4. Add "fewest coalition units nearby" later? Rec: no, not until an own-side view or overlay frame exists to cite; today's rules use only public node state.
5. Restrict candidates to the travel table's "reachable within the hold" nodes (`tools/balance/metrics.py:1312`)? Rec: no; all strategic nodes keep the rule simple, and the table is derived map data a viewer can't see.
6. Run the A/B before Q-TD-140 is decided? Rec: yes, at shipped rules; rerun after any Q-TD-140 change.
