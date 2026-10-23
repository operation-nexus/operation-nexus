# Prompt: Balance study

```
Act as .agents/roles/game-designer.md. Hypothesis: <...>. Change: <config diff or --set key=value>.
Run the balance harness before and after at the same SHA (profiles: <the ones the change touches>),
then report the metrics below with the exact commands. Recommend keep, revert, or iterate.
```

Command (from `tools/balance/README.md`):

```
cd services/sim && uv run --frozen python ../../tools/balance/balance.py \
    --profile <p> --seeds N --hours H [--set k=v] [--theater f] --out <new dir>
```

- Iterate with short runs (6 h, 3-5 seeds). The full 50-seed acceptance run is for the gate only.
- Runs over about an hour go through the queue: open a `harness-run` issue (README, "Local run queue"). Estimate the wall time before you schedule a check-in.
- Adversarial profiles don't exist yet (NX-321).

Report from `report.md`, before and after:
- Targets A1 to A4 (TESTING-STRATEGY §3.5a). A2 is the median time to first impact and the share over 15 min, by role (Q-SIM-97). A4 is suspended (Q-SIM-92).
- Idle armed viewer-unit share, and the idle reasons.
- Density: slots per unit and jobs per node.
- Supply-starvation minutes.
- Director tier dwell.
- Campaign length and the momentum curve.
