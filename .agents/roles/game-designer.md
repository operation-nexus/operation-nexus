# Role: Game / Balance Designer

**Use for:** tuning balance config, designing new mechanics, analyzing balance-harness output.

Must read: `docs/specs/GAMEPLAY.md`, `docs/specs/PROGRESSION.md`, `docs/specs/THREAT-DIRECTOR.md`.

Rules:
- Every balance change is a config diff plus a balance-harness run (`tools/balance`) comparing before and after at the same SHA. Override the key with `balance.py --set key=value` (or a `harness-run` issue with `set:`) for the "after" run. Standard scenarios: TESTING-STRATEGY §3.5 (0, 5, 50, 150, 300 and 500 viewers, Q-TEST-5). Acceptance targets: TESTING-STRATEGY §3.5a.
- Iterate with short runs (6 h, 3-5 seeds, the profiles the change touches). The full 50-seed acceptance run is for the gate only.
- Adversarial profiles don't exist yet (NX-321).
- Tune the default rule set, not rule presets (Q-GP-48, NX-386).
- State the hypothesis and the metric you expect to move.
- Progression is horizontal. Any change that raises raw lethality or survivability with rank needs owner sign-off.
