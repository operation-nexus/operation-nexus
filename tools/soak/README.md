# tools/soak: headless soak (NX-033 part 1)

One seeded campaign on the real kernel, driven by a crowd profile of `tools/balance` (it calls `runner.run`, the same personas and `profiles.yaml`), for a wall-clock budget or a game-time budget, whichever ends first. Decision: Q-TEST-9 (a 30-60 min soak nightly on CI, a weekly 6 h+ soak on the owner PC queue). This is part 1: the tool and the nightly job. The weekly PC-queue job is part 2.

```
cd services/sim && uv run --frozen python ../../tools/soak/soak.py \
    --profile evening-150 --minutes 20 --out /path/to/new-dir
```

| Flag | Meaning |
|---|---|
| `--profile` | a crowd profile of `tools/balance/profiles.yaml` (default `evening-150`) |
| `--seed` | sim and crowd seed (default 1) |
| `--minutes` | wall-clock budget of the run phase (default 45). The replay that follows takes about as long again, so the whole run is about twice this |
| `--hours` | game-time budget (default `campaign.time_limit_h`; the run also stops when the campaign ends) |
| `--worst` | how many of the slowest single ticks to list (default 20) |
| `--checkpoint-ticks` | `state_hash` every N ticks (default 3600, six game minutes) |
| `--mem-every-min` | game minutes between RSS samples (default 5) |
| `--warmup-h` | game hours ignored before the memory slope fit (default 0.5, PROPOSED) |
| `--max-growth-mb-per-h` | fail above this memory slope (default 20 MB per game hour). **PROPOSED, not a validated value**: no long-run slope has been measured yet; set it from the first nightly reports |
| `--out` | report directory; must not exist. Gets `soak.json`, `soak.md` and `logs/` (the command log) |

Exit 0 pass, 1 fail (reasons in the report), 2 usage or config error.

## What it records

- **Step time per tick** (`step` only, as `kernel_bench.py` does; not the crowd or metrics code). p50 and p99 come from a 1% log histogram so the recording itself uses constant memory; max is exact. The worst N ticks are listed with tick, game seconds, step ms, whether the tick was a board-pass tick (the kernel's own rule: not frozen and `running_ticks % tasking.reeval_every_ticks == 0` after the step) and the entity count. This is the hunt for the rare spikes NX-376 left open (127.8 ms once in a 6 h run). The SC-10 p99 line (25 ms) is shown beside the p99 but is **not gated**: shared-runner timings are indicative only, the reference host decides SC-10.
- **Memory**: process RSS from `/proc/self/statm` (Linux, stdlib only), sampled every K game minutes; after the warm-up a least-squares slope in MB per game hour. Without `/proc`, or with fewer than three samples after the warm-up, the slope is `null` in the JSON and "missing" in the Markdown, and the gate is not applied (reported, never invented). The process also holds the harness's own metrics, so the slope is the whole process, not only the kernel.
- **Hashes**: `state_hash` at every checkpoint tick and at the last tick, and the command log. At the end the log is replayed from tick 1 with the production handlers and every checkpoint must match ("hashes replay").

## Fail reasons

A sim crash or harness error; a memory slope above `--max-growth-mb-per-h`; any replay mismatch (the ticks are listed); a replay that did not run.

## Report

`soak.json` carries sha (`GITHUB_SHA`, else `git rev-parse HEAD`, else `null`), config hash, profiles digest, profile, seed, what stopped the run, ticks, game hours, wall time, host block, step percentiles, worst ticks, memory samples and slope, checkpoints, replay result, command counts, pass and reasons. `soak.md` is the short summary. Wall time and timings are the only values that differ between two runs of the same seed.

The nightly job (`.github/workflows/nightly.yml`, `soak`) runs `evening-150` with `--minutes 20` and uploads `soak.json` and `soak.md` (14 days).

Tests: `services/sim/tests/tools/test_soak.py`.
