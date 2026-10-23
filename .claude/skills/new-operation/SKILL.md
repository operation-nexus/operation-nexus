---
name: new-operation
description: Add or change a Threat Director operation (a Static enemy behaviour such as an ambush, a raid or a new kind of offensive) as an entry in the operation catalog content/operations.yaml, with no kernel code. Use when someone asks for a new enemy behaviour, job combination or director operation, or a change to an existing one.
---

# Author an operation

A director operation is **content, not code** (Q-TD-7, CONFIG-AND-CONTENT §8a, THREAT-DIRECTOR §4). It is a job
template: preconditions, a cost, enabled tiers and an ordered list of Tasking Board jobs that the director posts on
the Static's board. This skill takes a plain description to a proposed catalog entry that matches the specs exactly.
Read first: THREAT-DIRECTOR §2, §3, §4 (steps 3–8, TD-2, TD-5), §5a, §7; CONFIG-AND-CONTENT §5, §6.7, §8a;
CONTRACTS §3.3 (`JobKind`, `UnitKind`) and the `STAFF_DIRECTOR_OVERRIDE` row; ADMIN-RBAC `STAFF_GM_OPERATION`;
GAMEPLAY §0, §1b; FOG-OF-WAR FOW-4, FOW-8, FOW-10, FOW-11, FOW-13; AGENTS.md rules 0, 2, 6a;
`docs/quality/DATA-INTEGRITY.md`.

**Where things are.** The catalog is `content/operations.yaml`; its schema is `contracts/config/operations.json`; the
loader is `nexus.runtime.operations` (NX-156). Read the schema for every closed list: do not copy lists from this skill.
Costs are owner-approved starting values marked PROPOSED (Q-SIM-78), tuned by the balance harness. Never say a check
passed that you didn't run.

## 1. Can the job kinds do it?

An operation composes existing pieces only: `JobKind` values, existing `UnitKind`s on the ENEMY side, preconditions,
targets, selectors (`at`), slots and job dependencies (TB-8). Read their enums in `contracts/config/operations.json`
and `contracts/common/enums.json`. Map every step of the request to a job. If a step doesn't map (a new job kind, a
unit acting outside the board, a new precondition, target or selector, a new threat-memory counter), that part is a
**new capability**: it needs a spec change approved by the owner and a code PR (AGENTS.md rules 1-2). Say so, split it
out, and author only what the job kinds express. Don't stretch a job kind to fake a behaviour.

Also stop if the request needs the director to:
- move units directly. Only `DecoyBlink` acts outside the board (FOW-11); everything else is jobs (§4 step 8).
- read anything outside `EnemyView` (step 5).
- get a power Quorum units don't have (step 4). The director may compose jobs into richer combinations, nothing more.

A new job kind is a contract change: the `JobKind` enum in `contracts/common/enums.json` (and CONTRACTS §3.3), its
`tasking.priority.<job_kind>` key and its board handler land in one PR (rule 6a), before any operation uses it.

## 2. Fill every field

Use `contracts/config/operations.json` field for field; the loader also checks the cross-file rules listed in its
description. Current fields:

| Field | Rule |
|---|---|
| `id` | UPPER_SNAKE, unique. It is also the `<op>` in `director.op_priority.<op>` and the name `STAFF_DIRECTOR_OVERRIDE.trigger_operation` and `STAFF_GM_OPERATION.operation` accept |
| `target` | One of the schema's `target` enum. It decides which preconditions and selectors fit (the loader checks) |
| `preconditions` | Names from the schema's closed enum only; no duplicates. A new one is a code change. Every operation that targets a coalition thing needs `target_in_enemy_view` |
| `cost` | Whole budget points, the operation's only price (Q-TD-8, Q-TD-12); its units cost nothing extra. At least 1 with jobs, 0 for an effect-only operation; not above the largest tier budget. Existing values are PROPOSED (Q-SIM-78); a new one is your proposal, marked `# PROPOSED – unvalidated` |
| `enabled_tiers` | Some of `ThreatTier` (`contracts/common/enums.json`). Pattern of Life is routine only (§3, §5a): Recon, EscortConvoys, DecoyBlink, GarrisonUpkeep; no offensives beyond the night cap. CHARLIE is parked (Q-TD-3) |
| `jobs` | Ordered; each later job depends on the one before it (TB-8). Each job has `kind`, `at` (a selector from the schema), `unit_kinds` (ENEMY kinds; omitted only for a GARRISON operation) and `slots` (units bought, at least 1) |
| `effect` | For an operation with no jobs; exactly one of `effect` and `jobs`. Read the schema's enum |
| `memory` | Optional `{counter, effect}`: the threat-memory counter that RAISEs or LOWERs the score. Omitted: multiplier 1 |
| `track_age` | Optional, SECTOR targets only: the score also rises with how stale the Static's picture of the sector is (TD-5) |

Rules:
- **No invented numbers.** `cost`, `slots`, the priority and any multiplier are PROPOSED
  (`# PROPOSED – unvalidated`, DI-7, DOC-2) until the harness validates them. Give a reason for each new one (relative
  intent such as "cheaper than OFFENSIVE" is fine as a comment); the shipped values are the reference.
- **Priority is not in the catalog.** It comes from `director.op_priority.<id>` (step 6).
- **Spawns follow parity (Q-TD-8).** Don't put a spawn location in the template. Units come from the nearest Static
  base with surplus, else the rear source (GP-7), within `director.max_spawns_per_window` and
  `director.max_live_units.<tier>`.
- **Threat memory.** Scoring uses the operation's matching counter (§4 step 4; RAISE multiplies by `1 + counter`, LOWER divides by it). The
  counters are the schema's `memory.counter` enum (§2). Say which one matches, or that none does (multiplier 1). A new counter is a spec change.
- **Changing an existing operation** is the same procedure: show the old and new entry and say what moves in play.
  Removing one also removes its `director.op_priority` key, and is checked against anything that names it (GM
  presets, overrides, tests), in the same PR (rule 6a's spirit: nothing left that names a missing operation).

## 3. Edits that land in the same PR

1. THREAT-DIRECTOR §4 step 3: add the operation to the candidate list, with its target type.
2. CONFIG-AND-CONTENT §8a: add it to the first-build list (and the example only if it teaches something new).
3. `director.op_priority.<id>` (step 6).
4. Any spec rule the operation touches (a new parity asymmetry goes in GAMEPLAY §0; a new adaptation in THREAT-DIRECTOR
   §4 step 5).
5. A `docs/quality/PLAYTEST-WATCHLIST.md` row for a new behaviour (step 8).
6. A golden-scenario test idea in THREAT-DIRECTOR §7 (step 9).

`TRACKER.md` and `OPEN-QUESTIONS.md` are shared files: if you are a parallel session, list the edits you need in the
PR description instead (AGENTS.md rule 11b).

## 4. Parity (GAMEPLAY §0)

State in one or two sentences how the same thing is done by the Quorum: which coalition job, free order or player
action matches it. The Static gets the same job kinds and mechanics (claim leases, feasibility, aging, slots, dedupe,
TB-1..TB-9); the director only composes them. If the operation relies on something only the Static has today (e.g.
`CAPTURE` jobs, Q-TD-14; emission control, Q-FOW-13; AI escorts, Q-GP-45), name the existing asymmetry. A **new**
asymmetry needs a justification in GAMEPLAY §0 approved by the owner; write it as a proposal, not a decision.

## 5. Enemy view only (TD-2, FOW-4, FOW-8, FOW-13)

Every selector and precondition resolves against `EnemyView`. Check each one and write down what it sees:
- Coalition units: only current enemy detections or last-known tracks (FOW-10). A `STRIKE` needs a track at impact
  (Q-FOW-4, Q-FOW-16), so a target that is only a last-known track needs a `SCOUT` first.
- Coalition facilities: only through discovered markers (FOW-13), with their last confirmed state and its age.
- Nodes: positions and owners are always known (FOW-10).
- Never coalition stock, supply readiness or anything the Static didn't sense (Q-TD-2).

A selector that resolves to nothing drops the operation (TD-2). The Static's board must never hold a job that names
an entity outside its view; the TD-2 property test checks this. If the behaviour needs knowledge the view can't give,
the answer is a `SCOUT` job (TD-5) or no operation.

## 6. Config keys and rollout

- `director.op_priority.<id>`: float, base priority, PROPOSED, HR Yes (CONFIG §6.7, Q-TD-6). §6.7 holds one
  generic `director.op_priority.<op>` row: name the new key in the PR, and add its own row only if §6.7 lists
  operations one by one. The key lands in `balance/default.yaml` with the operation (the loader rejects a missing one).
- Any other key the operation reads (e.g. `director.decoy_blink.dark_s`): list it with its HR status (§5). A new key
  goes in the §6 table and the schema together (§11.2 drift check).
- Hot-reload: director budgets and tier thresholds reload at the next window (§5). Whether `content/operations.yaml`
  itself is hot-reloadable isn't stated in §5 (step 7); don't assume it is.

## 7. Gaps to raise, not fill

Hit one → add a question to OPEN-QUESTIONS (or list it in the PR) and leave the field `<OPEN: Q-…>`:

- An entity target (a single unit or convoy) isn't in the `target` enum, and `STAFF_GM_OPERATION.target` is
  `NodeId|SectorId|null` only.
- Whether the operation catalog is hot-reloadable (step 6).
- Any precondition, selector, target or counter the schema lacks: a spec change plus a code PR (§1).

## 8. Playtest watch-list row

A new behaviour gets a row in `docs/quality/PLAYTEST-WATCHLIST.md`: Watch (the behaviour), Decision (what it does,
values PROPOSED), Revisit if (what viewers would notice if it's wrong: too frequent, too punishing, invisible,
predictable), Source (the Q-id or tracker id). A change to an existing operation updates its row rather than adding a
duplicate.

## 9. Golden-scenario test idea

Write one line in THREAT-DIRECTOR §7 in the form of the existing goldens ("convoy raids → escorts appear within N
windows"): a seeded setup, the coalition action that provokes it, and what must appear on the Static's board within N
windows (N TBD). Add the negative too when it matters: the operation is not posted when its target isn't in
`EnemyView`, when the budget can't pay for it, or at a tier it isn't enabled for. Goldens become
`tests/golden/*.jsonl` when tests exist (TESTING-STRATEGY).

## 10. Done means

The two list additions, the `content/operations.yaml` entry, the `director.op_priority.<id>` key in
`balance/default.yaml`, the parity statement, the enemy-view check, the key list with HR status, the watch-list row,
the golden idea, gaps raised, every number PROPOSED, and the output of what you ran:

- `cd services/sim && uv run --frozen pytest tests/runtime/test_operations.py tests/runtime/test_config.py`. Update
  `GOLDEN_OPERATIONS_HASH` and the shipped-catalog test in `test_operations.py` with the entry, and add a rejecting case
  for any new rule.
- A short harness run, e.g. `cd services/sim && uv run --frozen python ../../tools/balance/balance.py --profile prime-50 --seeds 3 --hours 6 --out <new dir>`
  (`tools/balance/README.md`). Longer runs go to the queue (`harness-run` issue).

The PR targets `develop`; values stay PROPOSED until the harness validates them (CONFIG-AND-CONTENT §11.4). Owner or
admin approval gates the content: never publish it yourself.

## Worked example: cheap harassment

Request: "the Static should sometimes poke at the defenses of a base on the front with a single jet".

**Step 1.** One `STRIKE` job on the target's defenses maps directly. A minimal valid entry (checked by loading it with
a matching `director.op_priority.HARASS`; the shipped `PROBE` already does nearly this, so a real request would change
`PROBE` instead):

```yaml
- id: HARASS
  target: NODE
  preconditions: [target_owner_is_coalition, target_in_enemy_view, target_is_frontline]
  cost: 12                            # PROPOSED – unvalidated: between PROBE (15) and RECON (2)
  enabled_tiers: [ALPHA, BRAVO]       # an attack, so not Pattern of Life (§3, §5a)
  jobs:
    - { kind: STRIKE, at: target_defenses, unit_kinds: [ENEMY_STRIKE_FIGHTER], slots: 1 }
```

- **Same PR:** THREAT-DIRECTOR §4 step 3 and CONFIG §8a list entries; `director.op_priority.HARASS` in
  `balance/default.yaml`.
- **Threat memory:** `memory` omitted, multiplier 1.
- **Parity:** the Quorum strikes Static defenses with the same `STRIKE` job. No new asymmetry.
- **Enemy view:** `target_in_enemy_view` keeps the job to nodes the Static can see.
- **Watch list:** a row if it ships (step 8).
- **Golden idea:** seeded ALPHA with a frontline coalition base in view → a HARASS STRIKE job on the Static's board
  within N windows; with the base out of view → none.
- **Rollout:** hot-reload status of the catalog is open (step 7); until answered, assume a new campaign.
