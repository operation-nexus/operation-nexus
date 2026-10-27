# Harness: Elastic Workers Across Overlapping Jobs

Status: Accepted, built as NX-460 (Q-DEV-35, owner 2026-10-27) · Builds on: NX-442 (Q-DEV-33, Q-DEV-34), NX-433 · Author: the local ops session on the reference host; corrections by the lead session

## Decision and corrections (NX-460)

The owner asked the lead to correct and build this proposal (Q-DEV-35). What was built differs from the proposal below in four places. The code and `tools/balance/README.md` are authoritative.

1. **Older shas.** The queue runs `balance.py` from the requested sha's own worktree, so a job at a sha from before NX-460 has no `--slot-dir`. The queue reads `git show <sha>:tools/balance/balance.py` before the job starts. A sha with the option runs elastic. A sha without it runs as under NX-442 (a fixed pool, `min_overlap_workers`), and the queue process holds that job's slot locks for it, releasing them as its runs finish, so old and new jobs share one budget.
2. **Fairness by lock, not by file.** A waiting worker holds a shared flock on `wait-<issue>`. A younger job's worker probes older wait files with a non-blocking exclusive lock: if the probe fails, an older worker is waiting and the younger one does not take a slot. A killed job's lock is dropped by the kernel, so a stale wait file never blocks anyone. `balance.py` never deletes wait files; the queue removes unlocked ones at tick start.
3. **Start rule.** Starting a job whenever one slot is free would start every queued issue at once (each spends minutes in `uv sync` before its workers take a slot). Instead the queue counts demand as under NX-442: free = `max_workers` minus, over running jobs, min(workers, runs left). An elastic job starts when free is at least 1, with its requested workers, and widens as older jobs' runs end. `min_overlap_workers` now applies to legacy shas only.
4. **Progress file.** Written from `runner.run`'s existing `on_tick` callback (no runner change), at most once per 60 s, with `total_ticks` taken from the config's tick rate. It is deleted once the run's result file is written.

The per-run slot wait is recorded as `timing.slot_wait_s` and summed in the report (`slot wait` line).

## The problem

NX-442 lets a second job start beside a running one, on one worker budget (`max_workers`, 12). But a job keeps its worker count to the end, because `balance.py` never resizes its pool. A job started beside another therefore stays small even after the other job ends.

Seen on the reference host, 2026-10-27:

- #452 (12 runs, 12 workers requested) ran from 14:40. #457 (12 runs) started at 16:56 on 6 workers, because only 6 of the 12 budget workers were free.
- #452 finished at about 17:10. At 17:12 #457 had 5 of 12 runs written, still on `--workers 6`, with 6 runs in flight and 6 waiting. The load average was about 6 on a 12-thread CPU, so half the machine sat idle until #457 ended.

The idle share is the cost of "a job keeps that count for its whole run". The tail of every overlapped job is slower than it needs to be.

## What we do not want to change

- **One sha per process tree, one worktree, one results directory, one report per issue.** Q-DEV-33 rejected merging every issue's runs into one pool, because it mixes shas in one process tree. This proposal keeps that.
- **A report is posted only when all of that job's runs are done.** Unchanged.
- **Resume after a kill (NX-433), the lock, the labels, the oldest-first rule.** Unchanged.

## Proposal: a shared slot pool instead of a fixed pool per job

The budget becomes a set of `max_workers` slot files in `work_dir/slots/` (`slot-00` … `slot-11`). Each run takes one slot while it runs.

1. **`balance.py --slot-dir DIR`** (new, optional; absent means today's behaviour). The job keeps a pool of `--workers` processes. Before a worker starts its next run it takes one slot: `flock(LOCK_EX | LOCK_NB)` on the first free slot file, retrying every 2 s. It releases the slot when the run ends. The kernel drops an flock when its process dies, so a killed job frees its slots with no cleanup code.
2. **Fairness.** Slots go to the oldest job first. A job writes `DIR/waiting.<issue>` while a worker waits, and a worker skips taking a slot while an older issue's `waiting` file exists and that issue has a worker waiting. This is the same oldest-first, no-overtaking rule as Q-DEV-34(b).
3. **Queue start rule.** With `--slot-dir`, the next eligible issue starts at once when any slot is free, with its own requested `--workers` (up to `max_workers`). `min_overlap_workers` is no longer needed for the elastic path. A job started beside another simply waits for slots at first and widens as the other job's slots free up.
4. **Report.** `workers` stays the number requested. A new line, `slot wait`, gives the total seconds the job's workers waited for slots, so a long job can be told apart from a starved one.

### Why this is the smaller change

- The worker pool, run files, resume and report code stay as they are. `run_jobs` only gains "take a slot, run, release".
- No inter-process messages: the only shared state is flock on files under one directory, the same primitive the queue lock uses.
- A job that crashes frees its slots at once, and a resume takes slots like any other run.

## Expected gain

On 2026-10-27 #457 ran its last six runs on six workers, with six threads idle. With elastic slots those six runs would have started when #452 freed its slots, about 17:10, and the whole job would have ended roughly one wave (a run lasts 30 to 60 min) earlier. The real figure has to be measured. The test below compares wall time and the CPU load on the host.

## Companion: a tick count per run

The progress comments on the issues cannot say how far a run is: the run's log size varies too much between seeds to turn into a percentage (raid-300 24-hour logs ran from 15 to 237 KB on 2026-10-27), and a result file appears only at the end. So the estimate for the last runs of a job is a guess from past wall times.

- **`balance.py` writes `runs/<name>.progress`** about once a minute from the process running that run: one line, `<tick> <total_ticks> <unix_time>`, written to a `.tmp` name and renamed, as result files are. `total_ticks` is hours × 36,000 (10 Hz).
- **Nothing else changes.** The queue counts `runs/*.json` only, so a `.progress` file is never taken for a result, and `--resume` ignores and overwrites it. The report is unchanged.
- **What it gives.** The progress comment can show each running run's real percentage and remaining time from its own current speed (ticks per second over the last minutes), which also reflects load from other jobs. With slot waits (above) it also tells a waiting run from a running one.
- **Cost.** One small file write per run per minute.
- **Test.** A short run writes at least one `.progress` file and no `.progress` file counts as a result in the queue's free-worker count.

## Risks and open points

- **Memory.** More runs in flight than today is not possible (the budget is still 12), but several worktrees and `uv sync` environments exist at once. This was true under NX-442 too. Measure peak memory on the 32 GB host with two 12-run jobs.
- **Per-run speed.** Runs slow a little as more run at once. The 2026-10-27 history shows about 262 ticks/s per run for the overlapped jobs #451 and #452 against about 269 for the single job #424, so the effect is small. Both numbers are averages over a few jobs.
- **Starvation.** The oldest-first slot rule prevents a young job from taking slots from an older one. A 12-worker old job can still hold all slots until it has fewer runs left than workers; that is today's behaviour too.
- **Timeout.** `job_timeout_hours` counts a job's wall time including the time its workers wait for slots. A job that waits long is closer to the limit (already true under NX-442).
- **Flock on WSL2.** It works on the WSL2 ext4 home directory. It must not be placed on `/mnt/c`. The directory is under `work_dir` in the Linux home.

## Test plan

1. Unit tests for the slot code with a fake runner: a slot is exclusive, a killed process frees its slot, an older waiting job gets the next free slot, no `--slot-dir` means no change.
2. Queue test: the second job starts when one slot is free, and the first job's report is posted before the second's.
   Progress file: see the companion section.
3. Live: queue two 12-run jobs with 12 workers each on the reference host. Pass if the host's busy-thread count stays near 12 until the last runs, and the second job ends earlier than under NX-442.

## What this needs from the lead session

Not edited here (rule 11b):

- `docs/planning/TRACKER.md`: a new row, "Harness elastic workers across jobs (slot pool)", depends on NX-442, with the test plan above as its done-when.
- `docs/planning/OPEN-QUESTIONS.md`: a new row, "Q-DEV-35: should a job's worker count follow free slots?" with this proposal as the recommendation and "keep the fixed per-job pool (NX-442)" as the alternative.
- `tools/balance/README.md` and `harness_queue.py` change with the work itself.

If the lead agrees, the ops session can build it on a branch from `origin/develop` and run the live test on the reference host.
