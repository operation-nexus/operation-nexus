# tools/balance: balance harness runner (NX-031 part 1)

Headless runs of the real sim with scripted viewers, for the six crowd profiles, with a report per run and per profile.
Spec: Q-SIM-91 (OPEN-QUESTIONS), TESTING-STRATEGY §3.5 and §3.5a (A1 to A6), Q-TEST-2 and Q-TEST-4 to Q-TEST-8, Q-ALN-42.
This is part 1. Part 2 (adversarial profiles, A5 and A6, NX-321) and part 3 (the nightly 20-seed diff job and trend chart, a CI change) are not here.

```
cd services/sim && uv run --frozen python ../../tools/balance/balance.py \
    --profile prime-50 --seeds 5 --hours 72 --workers 4 --out /path/to/new-report-dir
```

| Flag | Meaning |
|---|---|
| `--profile` | one of `overnight-0`, `quiet-5`, `prime-50`, `evening-150`, `raid-300`, `surge-500`, or the check profile `freelance-50` (below); a comma list; or `all` (default: the six standard profiles, never `freelance-50`) |
| `--seeds` | a count N (seeds 1..N) or a comma list; the sim seed is the seed itself |
| `--hours` | game hours per run, default `campaign.time_limit_h` of the config in use (72 shipped, the acceptance length; follows `--set campaign.time_limit_h=...`). A run stops early when the campaign ends. Short runs work; targets that need a longer window say `not evaluable` |
| `--workers` | parallel processes, one run each (default 1), started biggest crowd first to cut wall time. The report does not depend on it |
| `--set` | `key=value`, repeatable: override one numeric or boolean key of the shipped balance config (dotted path, e.g. `tasking.strike_idle_targets_max=0`, `economy.legacy_rules=false`, `economy.unlimited.ENEMY=false`). A boolean key takes `true` or `false` only (lower case); a numeric key a number only, never a boolean (NX-412 part 5a). An unknown key, a section, a value of the wrong type, a float for an integer key, a key given twice or a value the schema rejects exits 2 before any run. The overridden copy is saved as `<out>/balance.yaml`, every worker loads it, and the report header lists the overrides next to the (changed) config hash, plus the economy mode (below) |
| `--theater` | a theater file to run on instead of `content/theaters/strait-1.yaml`. Loaded with the sim's own loader (and cross-checked with the balance config) before any run: a missing, malformed or inconsistent file exits 2 with one stderr line, before `--out` exists. The loader wants the slug to equal the file name, so the copy is saved as `<out>/theater/<file name>` (not a fixed `theater.yaml`; a subdirectory so a file named `balance.yaml` cannot clobber the `--set` copy), every worker loads that copy, and the report header shows its slug, name, node count, landing-base count and the config hash (the theater is part of `config_hash`). The queue has no theater key on purpose: a hostile issue naming files on the owner's PC is a security surface, so adding one is a separate owner decision |
| `--out` | report directory; must not exist |

Output: `report.md` and `report.json` (config hash, profiles.yaml digest, seeds, hours, wall times, the target table, per-profile aggregates, one headline row per run), `runs/<profile>-s<seed>.json` (the full per-run report: metrics, momentum curve at one sample per game minute, command and response counts, final `state_hash`, timing) and `logs/<profile>-s<seed>/` (the run's command log). Wall time and ticks per second are the only values that differ between two runs of the same seed; they sit under `timing` (and `wall_s` and `ticks_per_s` in the run rows).

## How a run works

`runner.run` builds the campaign with `start_campaign` from the shipped config (the path the goldens use), then each tick: the viewers whose wake-up is due send commands, the commands are appended to a command log (the NX-103 format `tools/replay` reads, written before the tick that applies them), and `step(world, commands, HANDLERS)` runs with the production handler registry. Events feed the metrics and the viewers (a spawn, a queue place, a rejection, a loss). `runner.replay_log` rebuilds a run from its log alone and reaches the same final `state_hash` (tested). `tools/replay/replay.py` needs a snapshot directory, which the harness does not write yet.

The harness has its own seeded `random.Random` streams (the arrival schedule per profile and seed, and one per viewer), never the sim's. Commander ids are synthetic, deterministic UUIDv7-shaped ids; `SYS_SET_CALLSIGN` is not used because JOIN does not need a callsign.

## Profiles and personas: `profiles.yaml`

Only the six profile names and sizes are decided (Q-ALN-42, Q-TEST-5). **Every other value in `profiles.yaml` is PROPOSED**: the ramp length, the arrival rate after the ramp, each profile's persona mix, and each persona's behaviour (join, rejoin and rebase chances and delays). No spec gives them. They are harness inputs, not game balance, and are re-tuned once the first runs show what a believable crowd looks like. The report carries the file's digest so runs compare only on the same crowd.

**A profile name is the number of distinct viewers who arrive in the ramp, not the concurrent count.** Viewers who lose their unit and do not come back leave, and later arrivals join, so the peak with a live unit at once differs; every run reports `viewers.peak_concurrent` (most viewers holding a unit at once) beside `viewers.distinct`.

A profile has `viewers` distinct viewers arriving at uniform seeded times in the first `ramp_min` minutes, then new distinct viewers at `arrivals_per_hour` (Poisson, seeded) for the rest of the run. A viewer leaves only by losing its unit and not re-joining (there is no leave command yet, Q-SIM-91).

| Persona | Behaviour (commands that exist: JOIN with a role and no target or `hold`, and REBASE) |
|---|---|
| lurker | rarely joins (a role of any kind); rarely comes back |
| newbie | a bare join as STRIKE (a role is required by the contract; no target, so the board auto-tasks it); usually comes back |
| veteran | joins STRIKE; nearly always comes back. Its one REBASE to the most forward friendly airbase is built but **off** (`rebase_prob` 0): an accepted REBASE sets HOLD and nothing clears it until the parser's unit orders exist (NX-192), so rebased units would park for good. Turn it back on (0.5) then |
| logistics-lover | joins LOGI; nearly always comes back |
| afk-farmer | joins STRIKE with `hold`, then does nothing and never comes back |

## Metrics and targets

| Metric | From | Target (TESTING-STRATEGY §3.5a) |
|---|---|---|
| Campaign outcome and length | `CampaignEnded` | A1: at least 85% of seeds end by victory or defeat by `campaign.time_limit_h` (72); a time-limit ending is a miss. No 24 h floor (Q-TEST-6, owner 2026-10-24): a fast win is fine. Needs a run at least as long as the limit |
| Steamroll signals S1 to S4 | event log of each won run (`steamroll.py`; inputs from `Collector`), see "A1 steamroll check" below | A1's no-steamroll check (Q-TEST-11): the share of won seeds flagged as a steamroll, and a per-seed table. Information only: no pass threshold for the share is decided |
| Momentum curve | `momentum(world)` once per game minute | none (reported: mean, final median) |
| Newbie time to first impact | from a newbie's first JOIN to its first impact (see "A2 and impact" below) | A2 (Q-SIM-97, TESTING-STRATEGY §3.5a): for newbies who arrived at the Static's tier ALPHA or above, the median is at most 480 s (8 min, the top of a sortie) and at most 10% have a first impact later than 900 s (15 min). Tail rule below |
| Coalition kill share by unit kind | `UnitDestroyed` of an enemy unit, by the killer's kind (assists are not counted) | A4: no kind over 40% of all the coalition's kills (AI garrison and facilities included), pooled over seeds (PROPOSED, Q-TEST-8). A4 is suspended (`a4_suspended` in profiles.yaml, Q-SIM-92) until a second armed viewer unit kind exists: the report shows `suspended (Q-SIM-92): needs a second armed viewer unit kind`, never a fail, and still prints the measured top kind and share. Fewer than `a4_min_kills` (30, PROPOSED) pooled kills is `no data`. The report also gives the player-only share (commander-owned killers), which the target does not use |
| Idle armed viewer-unit share | `Collector.sample_idle(world)` every `idle_sample_min` game minutes (profiles.yaml, 5, PROPOSED): commander-owned units of an armed kind, not Disabled, with no job, order or route, over all such units | none (reported: mean and max per profile). For each idle unit, `tasking.idle_reason` (the board's own pool, `_open` and `_feasible`, read-only) says why it holds no job: `no_job`, `full`, `ring`, `ammo`, `refuel` (a rearm step would fix it), `reach_fuel` (a full tank would not reach) or `other`; the report sums the reasons over samples (Q-SIM-92, NX-380) |
| Slots per unit | `Collector.sample_density(world)` on the same cadence: unfilled slots (`slots - claims`) of the coalition board's open jobs (a job with an unfilled slot) over all live (not Disabled) commander-owned units; mean over samples, a sample with no such unit is skipped | none (reported) |
| Jobs per node | the same sample: coalition open jobs over the theater's node count; mean over samples | none (reported) |
| Strategic nodes lost, sanctuary defense HP | `NodeCaptured` from COALITION; `defense_hp` every tick | A3, `overnight-0` only: at most one strategic node lost and the sanctuary's HP above 0 in the first 12 h, every seed (PROPOSED, Q-TEST-8). A sim crash inside the window is a fail; a seed that stopped short of 12 h (or hit a harness error) makes A3 `not evaluable`. With no viewer units the sim's idle floor keeps the sanctuary at 1 or more, so the HP half of A3 cannot fail at 0 viewers; the nodes half is the real test |
| Director tier dwell | `ThreatTierChanged` (the Static's Director) | none |
| Supply-starvation minutes | coalition-held finite-stock nodes below their starvation floor, sampled once per game minute: node-minutes and minutes with at least one | none |

### Economy (NX-412 part 5a; ECONOMY §4 "Harness report", econ checkpoint review §4)

Information only, no targets. The report header labels the economy mode of the config in use (ECONOMY EC-15): `legacy_rules ON` or `off` and which sides are unlimited; anything but legacy off with no unlimited side is marked "not a normal balance result". `report.json` has the raw series per run (`metrics.economy`) and the pooled values per profile (`profiles.<name>.economy`); `report.md` has a table and one line per profile.

| Metric | From |
|---|---|
| Income, upkeep, groundings per side per hour | `SupplyProduced`, `SupplyConsumed{UPKEEP}` (the side of the paying node: its source or its owner), `UnitGrounded`; per game hour, the report gives the mean per run-hour |
| Pool and grounded units per side | read at the end of each game hour (first sample of the next): the source pool (`-`/null for an unlimited side, which has none) and live grounded units |
| Grounded share by previous state | at each idle sample, every armed viewer unit's state ("job", "busy" for an order, route or RTB, else its idle reason such as `full`); a unit grounded by the next sample counts for that state. Share = grounded / units seen again in that state. This is the review's "full-idle versus with a job" split |
| Static budget per window, base and source spend | the Static's `DirectorState.budget` at each decision window (planned); its `SupplyConsumed{SPAWN}` split by node: the rear source (the rear account) or a base. The planned split into the two EC-7 accounts is not in any event and the pool is read after the window spends, so the report gives the actual debits per account instead. Under legacy rules everything is a base debit; an unlimited Static's source spawns are never debited |
| Static operations per hour, by operation | the Static's `JobCreated` whose job key (read from its board the same tick) is the first job of an operation, `op:<operation>:<target>:0`, one per (operation, target) a tick. Per hour counts catalog operations; `POL_PATROL` and `POL_CONVOY` (routine Pattern of Life work) are only in the by-operation counts |
| Offensives, gap, on coalition-held nodes | `OFFENSIVE` launches: the minutes between consecutive ones in a run (median, max), and how many targeted a node the coalition held then |
| Live-cap refusals | `SpawnRefused` (ECONOMY EC-8): operations the budget and anti-spam allowed but the live cap stopped, by reason (`GUARD`, `TIER_CAP`). A JOIN at the cap is in `responses.queued` instead |
| Victory holds | `VictoryHoldStarted` / `VictoryHoldBroken`: holds, holds broken, Static catalog operations launched during each |
| Peak army against viewers | the most live armed coalition units in one sample (AI garrison included) against the run's peak concurrent viewers, per seed (the TS-1 check) |
| S4 against start stock | already in the steamroll table (`stock_of_start`) |
| Static travel time to the victory nodes | `metrics.travel_table`, from the config alone (no run): for each strategic node and each unit kind a Static CAPTURE job buys, the shortest road path from the Static's rear source with every bridge up, at the kind's Healthy top speed and each road's `speed_mult`, in game minutes, against `campaign.victory_hold_min`. Staging, spawning and combat are left out, so a real arrival is later (review §4.1: the Static must be able to reach a victory node within a hold) |

Not built yet (ECONOMY §4 asks, beyond this part): grounded unit-minutes by viewer vs AI and join-order quartile, grounded churn, the share of floor income cut by raids.

Sweep recipe, the economy on and legacy rules off (one issue per value, `set` takes up to `max_overrides`, 8: the 3 economy switches leave 5 for tuning):

````
```harness
sha: <a develop commit with NX-412 part 5a>
profiles: prime-50, raid-300, surge-500
seeds: 5
hours: 72
set: economy.legacy_rules=false, economy.unlimited.ENEMY=false, economy.unlimited.COALITION=false, director.source_spend_frac=0.01
```
````

Locally the same with `--set economy.legacy_rules=false --set economy.unlimited.ENEMY=false ...`.

### A1 steamroll check (NX-411, Q-TEST-11)

Only a campaign that ended in VICTORY is judged; a lost, time-limit or unfinished one shows "not judged". All thresholds are `targets.steamroll_*` in `profiles.yaml` and **PROPOSED** (Q-TEST-11), recalibrated once a hard-fought run exists. A signal that cannot be measured has no value, does not fire and says why (`note` in `report.json`; `n/m` in the table).

| Signal | Value, from | Fires when |
|---|---|---|
| S1 Static pressure on held ground | pressure events per 4 campaign hours (events x 4 / `length_h`). A pressure event is a `CaptureStarted` by the Static on a node the coalition holds, a `NodeDefensesDown` with owner COALITION, or a `NodeCaptured` that takes a node from the coalition (any node kind, not only strategic). Ownership starts from the setup and follows `NodeCaptured` | under `steamroll_pressure_per_4h` (2) |
| S2 contested final hold | pressure events at or after the start of the last victory-hold run, and the holds broken before it. The run comes from the sim's `VictoryHoldStarted` / `VictoryHoldBroken` (ECONOMY EC-9, NX-412 part 5a; before, the harness derived the same rule from `NodeCaptured`): the coalition owning at least `campaign.victory_node_frac` of the strategic nodes; a dip closes a run (a broken hold) and the campaign ends in VICTORY when the run lasts `victory_hold_min`. A win by HQ capture while below the fraction has no hold: S2 is "not measurable" and does not fire | both are 0 |
| S3 momentum swing | the existing momentum samples (one per game minute). The coalition leads above `steamroll_lead_line` (50), the Static below it. Largest drop from the running peak after the first coalition lead; lead changes count each flip of the leader after the first leader is set (a start below 50 then a first lead is 1 change). Never led: not measurable | drop under `steamroll_swing_pts` (10) and at most `steamroll_max_lead_changes` (1) changes |
| S4 late Static force | per-minute samples (`Collector.sample`): the Static's live armed units that are not Disabled, and the stock of the finite-stock bases it owns. In the last third of the campaign (by `end_tick`): the mean of each against the run's own peak units and the stock at tick 0 | units under `steamroll_late_units_frac` (25%) of peak, or stock under `steamroll_late_stock_frac` (10%) of start |

- An HQ-capture win while at or above the victory fraction judges S2 on the short, incomplete last hold.
- S3 counts lead changes over the whole campaign but measures the drop only after the first coalition lead.
- S4's late stock counts only the bases the Static owns at that time, so losing bases lowers it (intended: a beaten Static).
- S4 uses the mean over the late third, not the last sample.
- The A1 steamroll share is information only until a threshold is decided (Q-TEST-12).

Steamroll = S1 and S2 both fire, or at least `steamroll_min_signals` (3) of S1 to S4 fire. The report has a per-seed table (each value, `*` when it fired) and the share of won seeds flagged per profile (also `A1.steamroll` in `report.json`).

### A2 and impact (NX-383, Q-SIM-93)

**Which newbies.** A2 judges only newbies whose first JOIN finds the Static Director's tier (`world.director["ENEMY"].tier`, as `tasking_gen._idle_targets_open` reads it) at `targets.a2_min_tier` (ALPHA) or above. At Pattern of Life the board posts no strike work by design (Q-SIM-85, Q-SIM-92). Those arrivals are counted (`joined_below_tier`, their times in `below_tier_ttfi_s`) and shown as "information only"; the report names both counts and never judges the second.

**What is an impact.** Any real contribution; the first of these by the newbie's unit sets its time:

| Kind | Source |
|---|---|
| `hit` | `WeaponImpact` with `hit` true, shooter owned by the newbie |
| `kill` | `UnitDestroyed` of an enemy, the newbie's unit the killer |
| `delivery` | `SupplyDelivered` with the newbie's commander id |
| `capture` | `NodeCaptured` naming the newbie a participant; or, derived from world state every `impact_check_s`, a GROUND unit of the newbie inside `capture.radius_m` of a node whose capture bar the coalition fills (no `CaptureProgress` event is emitted, and `CaptureStarted` names no commander) |
| `departure` | derived from world state every tick (`Collector.observe`, so the tick is exact): the first tick a newbie's own truck (a `supply.carriers` kind) holds cargo and a path, i.e. it loaded at its source and set off for a delivery. No event names the load. A truck that spawns or sets off empty (a capture run, a bare JOIN waiting for work) does not count; its later `delivery` does. Applies to every persona kind |
| `scout` | derived from world state every `impact_check_s`: a coalition track not seen before, within the newbie's recon unit's sensor reach (radius x the target's stealth). No event says who tracked what, and masking is not applied, so this is an approximation |

When two kinds land in the same tick the earlier row of `metrics.IMPACT_KINDS` (kill, capture, delivery, departure, scout, hit) is recorded. `scout` is the first coalition track never seen before that falls inside the sensor reach of a recon (painter) unit of the newbie's own.

**A2 rule (Q-SIM-97).** Pass needs both. (1) The median time to first impact is at most `targets.a2_max_s` (480 s). A newbie with no impact after being watched `a2_max_s` or longer counts as a miss (infinite); one watched for less when the run ended is unresolved and left out. (2) The tail share is at most `targets.a2_tail_share` (10%): of the newbies whose fate is known past `targets.a2_tail_s` (900 s), those whose first impact came later than 900 s or who had none after being watched more than 900 s. A newbie with no impact who was watched 900 s or less is unresolved for the tail and left out of its denominator. Exactly 10% passes; an impact at exactly 900 s is not in the tail. The detail line reads like "12.0% over 900 s (3/25), needs <= 10%" (one decimal, so 10.4% never shows as the 10% limit); the JSON has `A2.tail` (`limit_s`, `over`, `judged`, `share`), per persona kind too. The report shows the first-impact kind breakdown, overall and per persona kind.

### Persona kinds (Q-SIM-95)

Each viewer also draws a kind from its profile's `kinds` shares (a harness RNG per viewer, apart from the sim's streams and the viewer's own). The shares are `profiles.yaml` keys (PROPOSED) and must sum to 1 (checked on load).

| Kind | JOIN it sends |
|---|---|
| auto | today's bare `!join <role>` with the persona's role; the board auto-tasks it |
| striker | STRIKE with a node target: a seeded pick (the viewer's RNG) among foe-held nodes with defense HP in the coalition's view. It may strike a base alone. With none known it sends the bare JOIN and counts it in `viewers.striker_fallbacks` |
| hauler | bare `JOIN LOGI` |
| scout | bare `JOIN RECON` |
| capturer | `JOIN LOGI` with a node target: a seeded pick (the viewer's RNG) among foe-held, capturable nodes (not an `uncapturable_node_kinds` kind: the rear SANCTUARY, BRIDGE) whose defense HP is 0 in the coalition's view. A capture run with no cargo (Q-GP-24); the progress of its bar is a capture impact. With none known it sends the bare `JOIN LOGI` and counts it in `viewers.capturer_fallbacks`. PROPOSED share 0.1 (Q-SIM-104) |
| freelancer | the persona's own role (as auto) with a node target: a seeded pick (the viewer's RNG) among **all** theater nodes, the Static rear, bridges and the coalition sanctuary included (NX-398, Q-SIM-110). Only the check profile `freelance-50` has it (prime-50's crowd, kinds `auto: 0.5, freelancer: 0.5`), so the standard profiles' results stay comparable |

**Direct-order checks (NX-398, `orders.py`).** Every run's JSON has `orders`: `stuck_goto` (units whose GOTO order had an empty path at two board passes in a row without a hold, or held `tasking.order_dwell_s` or more; a unit `tasking.order_working` says is still working, a truck with cargo or a ground unit on its side's filling capture bar, is not counted, and a cargo stop has no bound here), `stale_claims` (board claims, both sides, with no progress for `tasking.claim_lease_s` or more after a pass), and for freelancers `direct_orders_ended`, `no_effect` (orders that ended, by the order going or the unit going, with no shot fired, no delivery and no capture by that unit) and `no_effect_share`. Crashes are the run's `crash` and `harness_error`. Run it with `--profile freelance-50`. `report.json` and `report.md` aggregate `orders` per profile (summed over seeds) as the `orders` row of the targets table: `fail` when any run has a stuck GOTO or a stale claim, `no data` when no run has the checks (a harness error); the no-effect share is information only. Like every target, it never changes the exit code. `services/sim/tests/tools/test_balance_harness.py` runs it for 12 game minutes with a fast 40-viewer crowd and asserts no crash, no stuck order and no stale claim.

Every command still goes through the ordinary path and the command log. The report breaks A2 down per kind (`A2.by_persona_kind`).

Other new keys: `momentum_sample_s` (60, game seconds between momentum and starvation samples; > 0) and `kind_roles` (`striker: STRIKE, hauler: LOGI, scout: RECON, capturer: LOGI`: the JOIN role each persona kind but auto and freelancer sends; values must be playable roles and every kind a profile uses needs one), checked on load; `targets.a2_min_tier` (ALPHA), `targets.a2_tail_s` and `a2_tail_share` (Q-SIM-97; positive, share in (0, 1]) and `impact_check_s` (1 game second between the two state checks), both PROPOSED.

A target with nothing to judge says so: `not evaluable` (the run was shorter than the window), `no data` (for example no kills), `not measurable yet`. **Not measurable yet:** the kill-share Gini by rank (no ranks until PROGRESSION), A5 and A6 (part 2). The CLI exit code is 0 whatever the targets say.

## Cost (measured 2026-10-22, 4 cores, one process unless noted)

A 72 h campaign is 2.59 M ticks, so the acceptance run's time is measured, not promised. One game hour: no viewers about 3,300 ticks per second; `prime-50` 26 s (1,384 ticks/s); `surge-500` 215 s (167 ticks/s). Two-hour runs with 4 workers in parallel (seconds per game hour): `overnight-0` 13, `quiet-5` 16, `prime-50` 31, `evening-150` 65, `raid-300` 150, `surge-500` 225. Linear extrapolation to 72 h and 50 seeds is about 500 CPU-hours for the six standard profiles (surge-500 about 225, raid-300 about 150), before the adversarial profiles and counting campaigns that never end early; the cost per tick grows with the unit count, so treat it as a floor to check against a real 72 h run.

A harness exception outside the sim (a bug here) is recorded as `harness_error` on that run, which is a stand-in with empty metrics, and the batch goes on. A sim exception (for example `the Director's budget exceeded the stock by 14`, seen at `prime-50` seed 1, tick 52,200) is recorded as `crash` in that run's report and counts as a miss; the other runs go on.

## Tests

`services/sim/tests/tools/test_balance_harness.py`, picked up by `make check` (the test puts `tools/balance` on `sys.path` itself; mypy sees the harness modules as `Any` from there). Same seed gives the same report and command log, the log replays to the same `state_hash`, every persona emits only valid commands, each metric and target rule is checked on a hand-built event stream, and the report is the same for 1 and 2 workers. `make check` also lints `tools/balance` and type-checks it with `mypy --strict` (it is in the Makefile's `TOOLS_TYPED`), so the harness modules are checked directly, not only as `Any` through the tests.

## Local run queue (NX-381)

Spec: Q-OPS-14. Long runs go to the owner's PC (WSL2 Ubuntu). A cloud session opens a GitHub issue labelled `harness-run`; an hourly timer runs `tools/balance/harness_queue.py run-once`, which runs each eligible issue with `balance.py` at the requested commit and comments `report.md` back, swapping the label to `harness-done` (or `harness-failed`, with the exit code and the last 40 log lines). The file is `harness_queue.py`, not `queue.py`, because a `queue.py` beside `balance.py` would shadow the standard library's `queue`. Config: `queue.yaml` (every key is commented). Tests: `services/sim/tests/tools/test_balance_queue.py`.

An issue is eligible when it is open, carries the `harness-run` label and was opened by a login in `trusted_authors`. Anyone else's issue is ignored without a comment. So when an issue sits unpicked past the next tick, check its opener against `trusted_authors` before suspecting the PC or the network (docs/agentic/LESSONS.md L-2). **Token check and late posting (NX-409, L-12).** Before a long run starts the queue proves the `gh` token can write to the issue with `gh issue edit <n> --add-label harness-run -R <repo>`: it adds the label the issue already has, so no label changes and no comment is left, yet it is a real write that needs Issues read and write (a read-only or unapproved token fails it; that the repeat add is a no-op is **[UNVERIFIED]** against live `gh`). If it fails, the queue logs one fixed line (never the token or issue text), leaves the labels as they were and does not start the run; once the token is fixed (organization approval under Settings → Personal access tokens → Pending requests, and Issues read and write on this repository) the next tick picks the issue up. When a run finishes, the queue writes a `finished` marker holding the size of `report.md` in `results_dir/<issue>-<sha8>/`, then posts the report and swaps the label to `harness-done`. If the post or the swap fails, the report stays on disk, the issue stays `harness-running` and the run is not failed. At the start of the next tick, a `harness-running` issue whose directory has a `finished` marker matching the report size gets the report posted (once; a `posted` marker prevents a second comment) and is marked `harness-done`; a stale issue without one, including a partial `report.md`, is marked `harness-failed`. Recovery takes the sha from `results_dir/<issue>.running`, written when the run starts and removed when the issue is posted or failed, not from the issue body, so an edited issue cannot redirect it (a missing or non-40-hex file means failed). Two crash windows are accepted: a crash before the `finished` marker is written is reported as a failure, and a crash between the comment and the `posted` marker can post the report twice. One run per issue and SHA: a request for a SHA the issue already ran is refused with a comment (its results directory exists), so recovery can never take an earlier attempt's report for a new one; open a new issue to run it again. The labels need triage rights, so they are the first gate. The request is parsed from the first ```` ```harness ```` block with strict `key: value` lines; an unknown key, a duplicate or a bad value is refused with a comment that names keys only, never the value. Issue text never reaches a shell. The SHA must be reachable from `origin/develop` (`git merge-base --is-ancestor` after a fetch). The run happens in a throwaway `git worktree` (`uv sync --frozen`, then `balance.py`), removed afterwards. A lock file stops two ticks overlapping; a second instance logs and exits 0.

**Trust.** The `harness-run` label gate is only as strong as the list of people with triage rights. A collaborator could edit a trusted author's issue; the damage is still bounded to SHAs on `develop`, profiles that exist in `profiles.yaml` and capped numbers (`max_*`, `job_timeout_hours` in `queue.yaml`). GitHub login reuse (a deleted account's name re-registered) is a residual risk, so keep `trusted_authors` current. A job past `job_timeout_hours` is killed with its child processes and marked `harness-failed`; an issue left `harness-running` by a crash or reboot is marked failed at the start of the next tick.

### Expected wall time

The Cost section above was measured on a 4-core cloud box. The owner's PC runs about 200 to 380 ticks per second per run. A game hour is 36,000 ticks (10 Hz), so one run takes about:

| Run length | Wall time per run, per worker |
|---|---|
| 6 game hours | about 10 to 20 minutes |
| 72 game hours | about 2 to 3.6 hours |

Add up to 60 minutes until the next hourly tick, and the time of any job ahead in the queue. One tick drains every eligible issue serially under one lock (`run_once` loops over `eligible()` and calls `process` for each). A tick that fires during a long run finds the lock held, logs it and exits 0, so a later issue starts on the first tick after the earlier run ends. Schedule check-ins on these times, not on the hourly timer. The throughput comes from the per-run Ticks/s column of the queue's own reports on the owner's PC (issues #253, #259, #260, #261 and #267, 2026-10-22 and 23: raid-300 about 180-230, evening-150 about 280-390, quiet-5 about 1,150-1,480 ticks/s, 6-8 workers).

### Setup on the PC

1. Prerequisites: `git`, `uv` and `gh`. Log `gh` in as **project-hiveplex** (the machine account, Q-OPS-15: a trusted author that is not the owner's notification account, so its comments reach the owner only when it assigns or @mentions `SaltySeraphCodes`, `docs/planning/ISSUE-WORKFLOW.md` rule 5) with a **fine-grained personal access token**: resource owner `operation-nexus`, only the `operation-nexus` repository, Repository permissions → Issues: Read and write (Metadata read comes with it); 90-day expiry. The queue only lists issues, relabels and comments, and `git fetch` needs no token on a public repo, so an Issues-only token keeps a leaked PC from pushing code or touching settings. WSL has no browser for `gh auth login`'s web flow, so use `gh auth login --with-token`, paste the token, press Ctrl-D, then check `gh auth status`. Renew the token before it expires (owner, 2026-10-22). Set the harness clone's git identity to the machine account too (`git config user.name project-hiveplex`, `git config user.email 344438984+project-hiveplex@users.noreply.github.com`). The organization must approve a new fine-grained token (as an org owner: organization Settings → Personal access tokens → Pending requests); until it does, reads of the public repo work but every write fails, and the tick logs `skipped after QueueError: ...` and leaves the issue untouched for the next tick. `journalctl --user -u nexus-harness` shows the full error text.
2. A dedicated clone, never your working clone (the tick runs `git reset --hard origin/develop` in it):
   ```
   mkdir -p ~/nexus-harness && git clone https://github.com/operation-nexus/operation-nexus ~/nexus-harness/operation-nexus
   chmod +x ~/nexus-harness/operation-nexus/tools/balance/queue-tick.sh
   touch ~/nexus-harness/operation-nexus/.nexus-harness-clone
   ```
   The marker file `.nexus-harness-clone` is required: `queue-tick.sh` refuses to run in a directory without it (or one that is not a git top level), so it can never `reset --hard` a working clone. It is untracked, so the reset keeps it.
3. Test without side effects (reads issues and fetches `develop`, comments, relabels and runs nothing):
   ```
   cd ~/nexus-harness/operation-nexus/services/sim
   uv run --frozen python ../../tools/balance/harness_queue.py run-once --dry-run
   ```
4. Timer, systemd user units. `~/.config/systemd/user/nexus-harness.service`:
   ```
   [Unit]
   Description=Nexus balance harness queue (NX-381)

   [Service]
   Type=oneshot
   # Lower CPU priority so long runs never slow the desktop.
   Nice=15
   Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
   ExecStart=%h/nexus-harness/operation-nexus/tools/balance/queue-tick.sh %h/nexus-harness/operation-nexus
   ```
   `~/.config/systemd/user/nexus-harness.timer`:
   ```
   [Unit]
   Description=Hourly Nexus balance harness queue

   [Timer]
   OnCalendar=hourly
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```
   Then `systemctl --user daemon-reload && systemctl --user enable --now nexus-harness.timer` and `loginctl enable-linger "$USER"` (user timers keep running without a login session). WSL needs systemd on: `[boot]` / `systemd=true` in `/etc/wsl.conf`, then `wsl --shutdown` from Windows. A timer fires only while the WSL distro is running; whether WSL stays up with no open terminal after `enable-linger` depends on the Windows and WSL versions and the `vmIdleTimeout` setting **[UNVERIFIED]**: check that a tick fires with every terminal closed, and keep a WSL session open if it does not. The user manager's `PATH` (`systemctl --user show-environment`) does not include `~/.local/bin`, where the `uv` installer puts `uv`, hence the `Environment=PATH=` line in the unit (needed on the owner's PC, 2026-10-22); add any other directory `gh` lives in. Ways to keep WSL running for the timer (none verified here): leave a WSL terminal open, set `vmIdleTimeout` under `[wsl2]` in `%UserProfile%\.wslconfig` (then `wsl --shutdown`), or a Windows Task Scheduler task at logon running `wsl.exe -d <distro> -- sleep infinity`. The dry run creates an untracked `services/sim/.venv` in the clone; that is expected.
5. Cron alternative (no systemd): `crontab -e`, add `0 * * * * $HOME/nexus-harness/operation-nexus/tools/balance/queue-tick.sh $HOME/nexus-harness/operation-nexus >> $HOME/.local/share/nexus-harness/tick.log 2>&1` (create that directory first; cron needs the WSL cron service running **[UNVERIFIED]**, and a minimal `PATH` that includes `uv` and `gh`).

Where things are: the journal (`journalctl --user -u nexus-harness`) holds the queue's log (it logs to stdout); results are in `~/.local/share/nexus-harness/results/<issue>-<sha8>/` with the run's output in `<issue>-<sha8>.log` beside it; worktrees and the lock live in `~/.local/share/nexus-harness/work/`. Change the paths and limits in `queue.yaml`.

### Requesting a run

Open an issue with the `harness-run` label (you need triage rights, and be a trusted author). Body:

````
```harness
sha: 0123456789abcdef0123456789abcdef01234567
profiles: prime-50, evening-150
seeds: 5
hours: 72
workers: 4
set: tasking.strike_idle_targets_max=0
```
````

`sha` is 40 lowercase hex characters on `develop`; `profiles` are names from `profiles.yaml`; `seeds` is 1 to `max_seeds`; `hours` is above 0 and at most `max_hours`; `workers` is optional (1 to `max_workers`, default from `queue.yaml`; `max_workers` is 12 and the default `workers` stays 2: ask for 12 (the owner barely uses the PC by day or night, 2026-10-26), about 20% less wall time per job with each run about 25% slower (issue #278); 12 matches the i7-8700's 12 threads; workers beyond `profiles × seeds` sit idle, so give a 12-worker job at least 12 runs, e.g. 6 seeds per profile for two profiles; measured on #385: 6 runs kept 6 of 12 workers busy, about 44% CPU); `set` is optional: up to `max_overrides` comma-separated `key=value` balance overrides (see `--set`; the key must exist at that `sha`, which must also have `--set`, and a `true`/`false` value needs NX-412 part 5a there), echoed in the result comment. The queue accepts only a dotted key (first segment lower case, later ones may be an upper-case side or unit kind, e.g. `economy.upkeep.STRIKE_FIGHTER`) and a bounded number or `true`/`false`; anything else refuses the whole request naming the key `set` only; balance.py then checks the value against the key's type. For a sweep, open one issue per value (0, 1, 2, 4). Wait for the next hourly tick.
