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
| `--profile` | one of `overnight-0`, `quiet-5`, `prime-50`, `evening-150`, `raid-300`, `surge-500`; a comma list; or `all` (default) |
| `--seeds` | a count N (seeds 1..N) or a comma list; the sim seed is the seed itself |
| `--hours` | game hours per run, default 72 (the acceptance length). A run stops early when the campaign ends. Short runs work; targets that need a longer window say `not evaluable` |
| `--workers` | parallel processes, one run each (default 1), started biggest crowd first to cut wall time. The report does not depend on it |
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
| Campaign outcome and length | `CampaignEnded` | A1: at least 85% of seeds end by victory or defeat in 24 to 72 h (the limit is `campaign.time_limit_h`). Needs a run at least as long as the limit |
| Momentum curve | `momentum(world)` once per game minute | none (reported: mean, final median) |
| Newbie time to first impact | from a newbie's first JOIN to its first impact (see "A2 and impact" below) | A2: the median over newbies who arrived at the Static's tier ALPHA or above is at most 300 s (the 5 min end of "3 to 5 min"; the median rule is PROPOSED). A newbie with no impact after 300 s counts as a miss; one still inside its first 300 s when the run ends is "unresolved" and left out |
| Coalition kill share by unit kind | `UnitDestroyed` of an enemy unit, by the killer's kind (assists are not counted) | A4: no kind over 40% of all the coalition's kills (AI garrison and facilities included), pooled over seeds (PROPOSED, Q-TEST-8). A4 is suspended (`a4_suspended` in profiles.yaml, Q-SIM-92) until a second armed viewer unit kind exists: the report shows `suspended (Q-SIM-92): needs a second armed viewer unit kind`, never a fail, and still prints the measured top kind and share. Fewer than `a4_min_kills` (30, PROPOSED) pooled kills is `no data`. The report also gives the player-only share (commander-owned killers), which the target does not use |
| Idle armed viewer-unit share | `Collector.sample_idle(world)` every `idle_sample_min` game minutes (profiles.yaml, 5, PROPOSED): commander-owned units of an armed kind, not Disabled, with no job, order or route, over all such units | none (reported: mean and max per profile). For each idle unit, `tasking.idle_reason` (the board's own pool, `_open` and `_feasible`, read-only) says why it holds no job: `no_job`, `full`, `ring`, `ammo`, `refuel` (a rearm step would fix it), `reach_fuel` (a full tank would not reach) or `other`; the report sums the reasons over samples (Q-SIM-92, NX-380) |
| Strategic nodes lost, sanctuary defense HP | `NodeCaptured` from COALITION; `defense_hp` every tick | A3, `overnight-0` only: at most one strategic node lost and the sanctuary's HP above 0 in the first 12 h, every seed (PROPOSED, Q-TEST-8). A sim crash inside the window is a fail; a seed that stopped short of 12 h (or hit a harness error) makes A3 `not evaluable`. With no viewer units the sim's idle floor keeps the sanctuary at 1 or more, so the HP half of A3 cannot fail at 0 viewers; the nodes half is the real test |
| Director tier dwell | `ThreatTierChanged` (the Static's Director) | none |
| Supply-starvation minutes | coalition-held finite-stock nodes below their starvation floor, sampled once per game minute: node-minutes and minutes with at least one | none |

### A2 and impact (NX-383, Q-SIM-93)

**Which newbies.** A2 judges only newbies whose first JOIN finds the Static Director's tier (`world.director["ENEMY"].tier`, as `tasking_gen._idle_targets_open` reads it) at `targets.a2_min_tier` (ALPHA) or above. At Pattern of Life the board posts no strike work by design (Q-SIM-85, Q-SIM-92). Those arrivals are counted (`joined_below_tier`, their times in `below_tier_ttfi_s`) and shown as "information only"; the report names both counts and never judges the second.

**What is an impact.** Any real contribution; the first of these by the newbie's unit sets its time:

| Kind | Source |
|---|---|
| `hit` | `WeaponImpact` with `hit` true, shooter owned by the newbie |
| `kill` | `UnitDestroyed` of an enemy, the newbie's unit the killer |
| `delivery` | `SupplyDelivered` with the newbie's commander id |
| `capture` | `NodeCaptured` naming the newbie a participant; or, derived from world state every `impact_check_s`, a GROUND unit of the newbie inside `capture.radius_m` of a node whose capture bar the coalition fills (no `CaptureProgress` event is emitted, and `CaptureStarted` names no commander) |
| `scout` | derived from world state every `impact_check_s`: a coalition track not seen before, within the newbie's recon unit's sensor reach (radius x the target's stealth). No event says who tracked what, and masking is not applied, so this is an approximation |

When two kinds land in the same tick the earlier row of `metrics.IMPACT_KINDS` (kill, capture, delivery, scout, hit) is recorded. The report shows the first-impact kind breakdown, overall and per persona kind.

### Persona kinds (Q-SIM-95)

Each viewer also draws a kind from its profile's `kinds` shares (a harness RNG per viewer, apart from the sim's streams and the viewer's own). The shares are `profiles.yaml` keys (PROPOSED) and must sum to 1 (checked on load).

| Kind | JOIN it sends |
|---|---|
| auto | today's bare `!join <role>` with the persona's role; the board auto-tasks it |
| striker | STRIKE with a node target: a seeded pick (the viewer's RNG) among foe-held nodes with defense HP in the coalition's view. It may strike a base alone. With none known it sends the bare JOIN and counts it in `viewers.striker_fallbacks` |
| hauler | bare `JOIN LOGI` |
| scout | bare `JOIN RECON` |

Every command still goes through the ordinary path and the command log. The report breaks A2 down per kind (`A2.by_persona_kind`).

Other new keys: `targets.a2_min_tier` (ALPHA) and `impact_check_s` (1 game second between the two state checks), both PROPOSED.

A target with nothing to judge says so: `not evaluable` (the run was shorter than the window), `no data` (for example no kills), `not measurable yet`. **Not measurable yet:** the kill-share Gini by rank (no ranks until PROGRESSION), A5 and A6 (part 2). The CLI exit code is 0 whatever the targets say.

## Cost (measured 2026-10-22, 4 cores, one process unless noted)

A 72 h campaign is 2.59 M ticks, so the acceptance run's time is measured, not promised. One game hour: no viewers about 3,300 ticks per second; `prime-50` 26 s (1,384 ticks/s); `surge-500` 215 s (167 ticks/s). Two-hour runs with 4 workers in parallel (seconds per game hour): `overnight-0` 13, `quiet-5` 16, `prime-50` 31, `evening-150` 65, `raid-300` 150, `surge-500` 225. Linear extrapolation to 72 h and 50 seeds is about 500 CPU-hours for the six standard profiles (surge-500 about 225, raid-300 about 150), before the adversarial profiles and counting campaigns that never end early; the cost per tick grows with the unit count, so treat it as a floor to check against a real 72 h run.

A harness exception outside the sim (a bug here) is recorded as `harness_error` on that run, which is a stand-in with empty metrics, and the batch goes on. A sim exception (for example `the Director's budget exceeded the stock by 14`, seen at `prime-50` seed 1, tick 52,200) is recorded as `crash` in that run's report and counts as a miss; the other runs go on.

## Tests

`services/sim/tests/tools/test_balance_harness.py`, picked up by `make check` (the test puts `tools/balance` on `sys.path` itself; mypy sees the harness modules as `Any` from there). Same seed gives the same report and command log, the log replays to the same `state_hash`, every persona emits only valid commands, each metric and target rule is checked on a hand-built event stream, and the report is the same for 1 and 2 workers. `make check` does not lint or type-check `tools/balance` itself (the Makefile is owner-only); run both by hand after a change: `cd services/sim && uv run --frozen ruff check ../../tools/balance && uv run --frozen ruff format --check ../../tools/balance && uv run --frozen mypy ../../tools/balance`. The tests are linted and type-checked by `make check`; the harness modules are typed `Any` there.

## Local run queue (NX-381)

Spec: Q-OPS-14. Long runs go to the owner's PC (WSL2 Ubuntu). A cloud session opens a GitHub issue labelled `harness-run`; an hourly timer runs `tools/balance/harness_queue.py run-once`, which runs each eligible issue with `balance.py` at the requested commit and comments `report.md` back, swapping the label to `harness-done` (or `harness-failed`, with the exit code and the last 40 log lines). The file is `harness_queue.py`, not `queue.py`, because a `queue.py` beside `balance.py` would shadow the standard library's `queue`. Config: `queue.yaml` (every key is commented). Tests: `services/sim/tests/tools/test_balance_queue.py`.

An issue is eligible when it is open, carries the `harness-run` label and was opened by a login in `trusted_authors`. Anyone else's issue is ignored without a comment. The labels need triage rights, so they are the first gate. The request is parsed from the first ```` ```harness ```` block with strict `key: value` lines; an unknown key, a duplicate or a bad value is refused with a comment that names keys only, never the value. Issue text never reaches a shell. The SHA must be reachable from `origin/develop` (`git merge-base --is-ancestor` after a fetch). The run happens in a throwaway `git worktree` (`uv sync --frozen`, then `balance.py`), removed afterwards. A lock file stops two ticks overlapping; a second instance logs and exits 0.

**Trust.** The `harness-run` label gate is only as strong as the list of people with triage rights. A collaborator could edit a trusted author's issue; the damage is still bounded to SHAs on `develop`, profiles that exist in `profiles.yaml` and capped numbers (`max_*`, `job_timeout_hours` in `queue.yaml`). GitHub login reuse (a deleted account's name re-registered) is a residual risk, so keep `trusted_authors` current. A job past `job_timeout_hours` is killed with its child processes and marked `harness-failed`; an issue left `harness-running` by a crash or reboot is marked failed at the start of the next tick.

### Setup on the PC

1. Prerequisites: `git`, `uv`, and `gh auth login` as the owner (the account needs to comment and relabel on the repo).
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
   Then `systemctl --user daemon-reload && systemctl --user enable --now nexus-harness.timer` and `loginctl enable-linger "$USER"` (user timers keep running without a login session). WSL needs systemd on: `[boot]` / `systemd=true` in `/etc/wsl.conf`, then `wsl --shutdown` from Windows. A timer fires only while the WSL distro is running; whether WSL stays up with no open terminal after `enable-linger` depends on the Windows and WSL versions and the `vmIdleTimeout` setting **[UNVERIFIED]**: check that a tick fires with every terminal closed, and keep a WSL session open if it does not. `uv` and `gh` must be on the `PATH` systemd gives the service; if not, add `Environment=PATH=...` to the unit **[UNVERIFIED]** for your install paths.
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
```
````

`sha` is 40 lowercase hex characters on `develop`; `profiles` are names from `profiles.yaml`; `seeds` is 1 to `max_seeds`; `hours` is above 0 and at most `max_hours`; `workers` is optional (1 to `max_workers`, default from `queue.yaml`). Wait for the next hourly tick.
