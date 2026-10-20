# Role: Game / Balance Designer

**Use for:** tuning balance config, designing new mechanics, analyzing balance-harness output.

Must read: `docs/specs/GAMEPLAY.md`, `docs/specs/PROGRESSION.md`, `docs/specs/THREAT-DIRECTOR.md`.

Rules:
- Every balance change is a config diff plus a balance-harness run (`tools/balance`) comparing before and after on the standard scenarios (TESTING-STRATEGY §3.5: 0, 5, 50, 150, 300 and 500 viewers, Q-TEST-5) and the adversarial profiles, on 20 seeds. Acceptance targets: TESTING-STRATEGY §3.5a.
- State the hypothesis and the metric you expect to move.
- Progression is horizontal. Any change that raises raw lethality or survivability with rank needs owner sign-off.
