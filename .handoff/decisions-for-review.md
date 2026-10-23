# Lead decisions awaiting the owner's review (Q-DEV-21)

Each row is in docs/planning/OPEN-QUESTIONS.md with status "Decided by lead, owner may veto".
Approve, veto or change any of them; the list grows as work continues.

- Q-SIM-37 Kinematics shape (NX-121)
- Q-SIM-40 JOIN interim shape (NX-122)
- Q-SIM-41 Reserve queue shape (NX-122)
- Q-SIM-43 Aircraft model shape (NX-368)
- Q-SIM-44 SYS_SET_CALLSIGN shape (NX-370)
- Q-SIM-45, 46, 47 Fog of war shapes (NX-150) (initial values owner-approved)
- Q-SIM-52, 55 Logistics shapes (NX-123)
- Q-SIM-58 Capture shape (NX-125)
- Q-SIM-62, 63 Campaign scope and shape (NX-126)
- Q-SIM-67, 70, 72 Combat shapes (NX-124)
- Q-SIM-75 Tasking Board part 1 shape (NX-374)
- Q-SIM-80 Director part 1 shape (NX-151, NX-155)
- Q-SIM-82 scout-job cap (lead part), Q-SIM-83 Director part 2 shape (NX-156)
- Q-SIM-84 Director part 2 QA fixes: reuse idle Director units and retire after 600 s, STAGE completion rule, PoL operations outside the ALPHA one-op cap, strike-failure left to balance (NX-156)
- Q-SIM-85 Director part 3 shape: garrison upkeep, patrols, PoL convoys, night progress slot and flip cap (NX-157)
- Q-SIM-85 build notes: patrols only between held nodes; garrison units only defend their own base; Static board posts no offensive jobs at Pattern of Life; PoL live-unit cap 24 -> 40 (NX-157)
SHIPPED (#235) WATCHLIST ROWS (docs/quality, needs owner PR):
- Routine recon burn: 101 UAVs / 6 game h at 0 viewers = 505 stock (~84/h, 68% of SPAWN spend), mostly shot down by coalition SAMs; Static start stock ~4000 (NX-157 coder run, seed 12345)
- Q-SIM-86 NX-157 QA fixes: convoys refill below-floor bases, fighters only at airbases, garrison returns home, held bars stay held when a viewer arrives, patrolling units never capture (patrols go toward the front), Static starts at garrison quota
- Q-SIM-87 lead details on owner's recon direction: cost 5 -> 2, loiter 600 s within 5 km at stale points outside known air-defense rings (NX-379)
- Q-SIM-86 (8): garrison units never capture anywhere; failed patrols head to the nearest friendly base or stand (from CodeRabbit review on #233)
- Q-SIM-88 recon details: 10 km grid, fuel-feasible stalest cell, ring clearance = loiter radius, outbound only, square loiter, per-cell visit memory (NX-379)
- NX-379 new keys: director.recon.memory_s 3600 (visit memory), grid_m 10000; staleness = fresher of look and track
SHIPPED (#235) WATCHLIST ROW (NX-379): | Static recon | RECON costs 2; a scout loiters 600 game s within 5 km of the stalest point of a sector (tracks and sensor looks, forgotten after 3,600 game s) that no known, not-Disabled air-defense ring covers, then goes home; a sector fully covered is skipped (all PROPOSED, Q-SIM-87, NX-379) | The Static sees nothing new for hours, scouts still die to sites it never found, or viewers never notice the scouting | Q-SIM-87, NX-379 |

## Owner reviewed 2026-10-22
Approved: Q-SIM-84, 85, 86 (incl. build notes and (8)), 87, 88 (1 h memory to playtest). Scout kills too cheap -> Q-SIM-89 (recon weights 0/2). Quiet nights intended.
Still pending: Q-SIM-37, 40, 41, 43, 44, 45-47, 52, 55, 58, 62, 63, 67, 70, 72, 75, 80, 82 (lead part), 83; Q-SIM-89 values.
- Q-SIM-90 !rebase shape: friendly base valid for domain, explicit order releases jobs, holds at destination until next order, no Director op (NX-158) [APPROVED 2026-10-22]
- Q-SIM-91 balance harness shape: 3 parts (runner+profiles+report now; adversarial with gateway; nightly CI later), personas use JOIN/REBASE only, seeded schedule, parallel seeds (NX-031)
- Q-SIM-92 idle armed viewers: STRIKE slots +1 per idle armed viewer up to 3, up to 2 extra strike jobs on known defended nodes (owner direction, lead values); A4 suspended (owner) (NX-380)
- Q-SIM-92 lead addition: idle-target strike posting only at Director tier >= ALPHA (tasking.strike_idle_targets_min_tier), so a lone newbie's auto-tasked jet never provokes the Director at Pattern of Life (NX-380)
- Q-SIM-94 lead build: coalition PATROL jobs along friendly front-line nodes, below STRIKE/DEFEND priority, never enter non-coalition nodes, provoke only via existing rules (NX-382)
- Q-SIM-96 lead details: intercept reaction 60 s (ALPHA+) / 600 s (PoL), radius 30 km, priority 45, leash 80 km, lost 120 s, garrison fighter exception (NX-382)
- Q-PROG-10 lead details: discovery XP 5/3/1, merit 1/1/0, stale 30 min, cooldown 60 min, per-sortie cap (NX-384)
- Q-SIM-94 lead details: patrol max 3 nodes, slots 2, orbit 5 km, dwell 600 s

## Overnight 2026-10-22/23
- NX-031 harness overrides (lead): `balance.py --set key=value` (existing numeric keys only, schema-validated) and a `set:` key in harness-run issues (max 4, strict regex), so tuning sweeps run on the PC queue
- OWNER APPROVED 2026-10-23: harness `--theater <file>` flag + density metrics (open job slots per live viewer unit, jobs per node) now; a larger hand-made benchmark theater (24-30 nodes) after P1 (needs tracker rows)
- Q-SIM-94 NX-382 build (lead): front line = coalition node with a neutral/foe/unknown road neighbour, ordered by exact squared distance to nearest foe node; no Director tier gate on posting (QA measured: patrols add no provocation; a lone UAV held on patrol actually provoked less); parameterless JOIN never takes a patrol (board assigns at next pass); aircraft fly a square orbit; ring check adds the orbit distance as clearance; patrol releases its unit when a higher-priority job it can take opens; ownership checked every tick for patrol units so they never enter a lost node; dwell 600 -> 300 s so a jet can finish one on a tank; after DONE units stay and the patrol may repost
- NX-031 density (lead): open job = claims < slots; Disabled units excluded from slots-per-unit
- OWNER QUESTION: queue `theater:` key? (security: issue text would name a file on the PC) - left out
- OWNER PR NEEDED (Makefile is CODEOWNERS): `make check` lints only services/sim, so tools/balance, tools/replay, tools/sim-determinism are never ruff/mypy-checked (a ruff format miss and an unused import slipped through tonight; tools/replay/replay.py:180 is 101 chars)
- NX-382 preemption (lead): an aircraft drops a patrol for better work any time; a ground unit only once it stands on a node (shortcut; upgrade = route from its next node)
- Q-GP-48/NX-386 lead details on owner's rule-preset direction: preset = validated overlay on default config, per campaign at start, in config hash; admins/owner apply, GMs draft; >1 unit per viewer needs its own spec; NX-376 ladder sets unit ceiling
- OWNER QUESTION (balance, from the new A2): a bare `!join logi` hauler waits ~30 min median (board posts RESUPPLY only below a node's starve floor or for damaged facilities; rare in a healthy campaign); bare `!join recon` scouts often find nothing new in 15 min. Options: (a) haulers get a standing "forward stock" job (move surplus from rear to forward bases up to a target level) - design change; (b) raise starve floors / add a "low stock" threshold above the floor - tuning; (c) bare join logi takes any capture run or escort follow - design. Scouts: intercepts + stale-sector scout jobs may help; check after #267.
- NX-031 A2 harness (lead): hauler departure = first tick its truck has cargo and a road path; tail excludes unresolved newbies like the median
- LESSON (for docs review): a fix pushed to an auto-merge PR can miss the merge (#268 merged seconds before 2784a9b; re-sent as #269). Rule: before pushing review fixes, disable auto-merge (or check the PR is still open right before push) and re-enable after.
- Q-SIM-96 NX-382 part 2 build (lead): reaction clock stored as world state (World.intercept_seen, snapshot 23), sampled each 50-tick board pass; wait uses the tier at posting; interceptors chase the Static's track, never truth; DONE on scout destroyed or Disabled; EXPIRED on lost_s untracked (claimed) or leaving every held node's radius; an unclaimed job ends as soon as the track goes; slots 1 may overfill to 2 by the usual rule; garrison leash enforced for the whole chase (released and recalled past 80 km); no re-post for a dead/Disabled scout
- HARNESS RESULTS: strike_idle_targets_max sweep 2/4/8 (#259-261): no gain (4 and 8 identical; few defended foe nodes on strait-1) -> keep 2 (lead). Patrols (#267, sha b14e564, old 5-min A2 rule): raid-300 A2 median 1376 -> 294 s (pass), evening-150 330 -> 192 s (pass); idle armed 75->73% / 59->56%; slots per unit 0.02 (raid) / 0.04 (evening) / 3.69 (quiet-5): crowds have almost no open slots -> map/job capacity is the limit (NX-385 benchmark theater, hauler work). Haulers/scouts still rarely impact.
- NX-371 (lead): ReserveQueueLeft reasons SLOT_FREED/REPLACED/REJECTED/TIMEOUT; a replacing JOIN = Left(REPLACED)+Joined (keeps the counter exact); new SYS_QUEUE_TIMEOUT command, applies while paused (added to SC-11); idleness counts only unpaused time; idle = chat silence per spec (gateway feeds activity); milestones and ban/forget removal deferred (nothing consumes / commands not built); runtime wiring waits for the host loop (follow-up row)
- From now: no 'Generated with Claude Code' footer in PR bodies (merge commits copy it; user rule + AGENTS 12). Morning item: merge commits authored by canthony224 vs Q-LEGAL-8.
- Docs review (lead): DoD 'CHANGELOG fragment' replaced by 'entries come from Conventional Commits once release-please lands (NX-015)'; rule 7 budget = non-test non-generated source; AGENTS banner -> P1 status; new .claude/rules/tools.md
- Docs C (lead): NX-301 -> P4 (beside NX-290 CSAR); NX-387 -> P2; duplicate PCG Q-SIM-29 renamed Q-SIM-99; OV-17/18/19 duplicates -> OV-23/24/25
- OWNER 2026-10-23: avoid hard-coded parameters as much as possible; customizable options are worth it even if they 'break rules' (default rule set stays; options via keys/presets). Audit running.
- OWNER 2026-10-23: B rule options - small ones now as keys (default = today's rule); 4 big ones (units per viewer, queue order, chat side, tier ladder) to NX-386 spec. Hot-reload yes for night_progress_cap, capture.quiet_floor/quiet_ref, objective_period_min, crew_marker_min.
- Lead proposal (veto window): config registry = schema metadata x-category/x-audience/x-edit-role/x-tune/x-source/x-status; generated CONFIG-REFERENCE.md with CI drift check; add-config-key skill; sweep tooling; GUI from metadata later.

## 2026-10-23 (after the morning report)
- **NX-376 closed on the reference-host step-only result** (#278: p99 @1,000 16.4 ms convoy, 12.0 ms mixed). The frame build share moves to NX-170; long-run single-tick spikes move to the NX-033 soak. Reversible: reopen if the frame bench breaks 25 ms.

## 2026-10-23 (after owner answers)
- Q-TEST-10 reduced P1 exit run = 10 seeds x 6 standard profiles at 72 h (60 runs).
- NX-389 forward stock design: reuse RESUPPLY job; stocking below `logistics.stock_target_frac` 0.8, urgency 0.5, front-line bonus 0.25; both sides.
- NX-364 part 1: port + no-op + log adapter now; DSN set without Sentry adapter -> log adapter with a visible warning.
- Order of kernel work: NX-388 kind keys -> NX-389 forward stock -> NX-388 B options -> NX-373 bridges -> NX-390 registry.

## Owner answers on Sentry (2026-10-23, ~10:00 UTC) - to record in OPEN-QUESTIONS Q-DEV-24 with the options-research PR
- Account: owner creates it only after research deems the service worth it; will apply for the OSS sponsorship.
- Data region: US only. Project is US-based; English first, other languages later.
- Read-only token for the routine: yes if useful after further research (asked for lead opinion).
- Spike protection check: after deciding it's worth it.
- Owner asked: alternatives, AI-enabled skills/MCP/connectors, direct integrations, build-own vs Sentry payoff -> research agent writing docs/review/ERROR-TRACKING-OPTIONS-2026-10-23.md.
- Q-SIM-102 (lead, owner may veto): NX-389 stocking runs load only from stock above a base's own target (ceil(stock_target_frac x max)), else from the rear source; starving/damaged runs keep Q-GP-24's floor rule. Reason: with the floor rule, stocking jobs would shuttle stock between forward bases (coder found; every base starts at 50%).
- NX-389 lead details (owner may veto, add to Q-SIM-102 row): stocking-only jobs sized to the target (not max); urgency milli guard sum <= 999; no snapshot FORMAT_VERSION bump (RESUPPLY urgency may be < 1000); stocking rule re-derived at load time.
- NX-392 (lead, owner may veto; Q-row to add): error tags use a typed per-key allowlist (tick digits, campaign_id id-shaped; others dropped and counted) instead of a shape-only check; sync assumptions: store set -> always also logs; hourly throttle gates reopen+comment; failed item doesn't stop the run; 1000-fingerprint store cap; 0.25 s busy timeout; redirects refused; a human-closed issue reopens (at most hourly) while the error recurs (EP-5).
