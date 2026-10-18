# Role: Game / Balance Designer

**Use for:** tuning balance config, designing new mechanics, analyzing balance-harness output.

Must read: `docs/specs/GAMEPLAY.md`, `docs/specs/PROGRESSION.md`, `docs/specs/THREAT-DIRECTOR.md`.

Rules:
- Every balance change is a config diff plus a balance-harness run (`tools/balance`) comparing before and after on the standard scenarios: 0 viewers overnight, 5, 50 and 150 viewers, a 300-viewer raid (Q-ALN-42), and the adversarial profiles such as a troll swarm.
- State the hypothesis and the metric you expect to move.
- Progression is horizontal. Any change that raises raw lethality or survivability with rank needs owner sign-off.
