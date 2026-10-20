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

**Planning phase.** `content/`, `balance/`, the operations loader and the balance harness (NX-031) don't exist yet.
Until their tracker items start, the operation lands as an addition to the first-build lists in THREAT-DIRECTOR §4
step 3 and CONFIG-AND-CONTENT §8a, and the YAML draft goes in the PR description. Don't create `content/` early
(AGENTS.md §3). Once the tools exist, run them and paste the commands and output (DOC-4). Never say a check passed
that you didn't run.

## 1. Can the job kinds do it?

An operation composes existing pieces only: `JobKind` values (CONTRACTS §3.3: `RESUPPLY`, `SCOUT`, `ESCORT_CONVOY`,
`DEFEND`, `STRIKE`, `REPAIR_BRIDGE`, `CAPTURE`, `ASSIST_OBJECTIVE`), existing `UnitKind`s on the ENEMY side,
preconditions from the schema's closed list, selectors, slots and job dependencies (TB-8). Map every step of the
request to a job. If a step doesn't map (a new job kind, a unit acting outside the board, a new precondition, a
selector the schema lacks, a new threat-memory counter), that part is a **new capability**: it needs a spec change
approved by the owner and a code PR (AGENTS.md rules 1–2). Say so, split it out, and author only what the job kinds
express. Don't stretch a job kind to fake a behaviour.

Also stop if the request needs the director to:
- move units directly. Only `DecoyBlink` acts outside the board (FOW-11); everything else is jobs (§4 step 8).
- read anything outside `EnemyView` (step 5).
- get a power Quorum units don't have (step 4). The director may compose jobs into richer combinations, nothing more.

A new job kind is a contract change: CONTRACTS `JobKind` (spec table, and `contracts/common/enums.json` once the
enum exists there, following the contracts/README.md checklist), its `tasking.priority.<job_kind>` key and its board
handler land in one PR (rule 6a), before any operation uses it.

## 2. Fill every field

Use the §8a schema field for field:

| Field | Rule |
|---|---|
| `id` | UPPER_SNAKE, unique. It is also the `<op>` in `director.op_priority.<op>` and the name `STAFF_DIRECTOR_OVERRIDE.trigger_operation` and `STAFF_GM_OPERATION.operation` accept |
| `target` | What the operation is aimed at. §8a shows `NODE`; §4 step 3 also uses sector, route, edge and radar. The full target enum isn't written down yet (step 7) |
| `preconditions` | Names from the schema's closed enum only. §8a shows `target_owner_is_coalition` and `target_in_enemy_view`. A new one is a code change (step 1). Every operation that targets a coalition thing needs `target_in_enemy_view` |
| `cost` | Budget points, `TBD` + `# PROPOSED – unvalidated`. It is the only place an operation's cost lives; its units cost nothing extra (Q-TD-8, Q-TD-12). It must sit inside the loader's cost envelope (Q-TD-7 test); the envelope keys aren't in §6 yet |
| `enabled_tiers` | Some of `PATTERN_OF_LIFE`, `ALPHA`, `BRAVO`. Pattern of Life is routine only (§3, §5a): Recon, EscortConvoys, DecoyBlink, repositioning; no offensives beyond the night cap. CHARLIE is parked (Q-TD-3) |
| `jobs` | Ordered; each later job depends on the one before it (TB-8). Each job has `kind`, `at` (a selector), `unit_kinds` (ENEMY kinds in CONTRACTS §3.3 `UnitKind`) and `slots` (`TBD`, PROPOSED) |

Rules:
- **No invented numbers.** `cost`, `slots`, the priority and any multiplier are `TBD` and carry
  `# PROPOSED – unvalidated` (DI-7, DOC-2) until the harness validates them. Relative intent ("cheaper than OFFENSIVE")
  is fine as a comment; a number is not.
- **Priority is not in the catalog.** It comes from `director.op_priority.<id>` (step 6).
- **Spawns follow parity (Q-TD-8).** Don't put a spawn location in the template. Units come from the nearest Static
  base with surplus, else the rear source (GP-7), within `director.max_spawns_per_window` and
  `director.max_live_units.<tier>`.
- **Threat memory.** Scoring multiplies by `1 + counter` for the operation's matching counter (§4 step 4). The
  counters are `convoy_attacks`, `radar_strikes`, `node_losses_by_sector`, `recon_losses_by_sector` (§2). Say which one
  matches, or that none does (multiplier 1). A new counter is a spec change.
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

- `director.op_priority.<id>`: float, base priority, `TBD by harness`, HR Yes (CONFIG §6.7, Q-TD-6). §6.7 holds one
  generic `director.op_priority.<op>` row today: name the new key in the PR, and add its own row only if §6.7 lists
  operations one by one by then. The key lands in the balance profile with the operation once `balance/` exists.
- Any other key the operation reads (e.g. `director.decoy_blink.dark_s`): list it with its HR status (§5). A new key
  goes in the §6 table and the schema together (§11.2 drift check).
- Hot-reload: director budgets and tier thresholds reload at the next window (§5). Whether `content/operations.yaml`
  itself is hot-reloadable isn't stated in §5 (step 7); don't assume it is.

## 7. Gaps to raise, not fill

These are open in the specs today. Hit one → add a question to OPEN-QUESTIONS (or list it in the PR) and leave the
field `<OPEN: Q-…>`:

- The closed list of preconditions: §8a shows two names, the full enum isn't written.
- The selector list: §8a names `target_defenses` and `nearest_own_base` (and `target` in its example), no more.
- The `target` enum: §8a shows `NODE`; sector, route, edge and radar appear in §4 step 3 as prose only. An entity
  target (a unit or convoy) isn't defined, and `STAFF_GM_OPERATION.target` is `NodeId|SectorId|null` only.
- The cost envelope keys (step 2).
- Whether the operation catalog is hot-reloadable (step 6).

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

The two list additions, the YAML draft (or the `content/operations.yaml` entry once it exists), the
`director.op_priority.<id>` key, the parity statement, the enemy-view check, the key list with HR status, the
watch-list row, the golden idea, gaps raised, every number `TBD`/PROPOSED, and any validator or harness output you
actually ran. The PR targets `develop`; values stay PROPOSED until the harness runs (CONFIG-AND-CONTENT §11.4). Owner or
admin approval gates the content: never publish it yourself.

## Worked example: convoy ambush

Request: "the Static should ambush our supply convoys when it spots them on a road".

**Step 1.** The parts map to job kinds: find the convoy (`SCOUT`), hit it (`STRIKE`). Nothing new is needed for the
jobs themselves. **Step 7 gaps hit:** the target is a moving coalition convoy, and no entity target type exists
(neither in §8a nor in `STAFF_GM_OPERATION`); the preconditions it wants (`target_tracked`) and the selector for "the
convoy" aren't in the schema. Options to raise with the owner: target the route edge or sector instead (closer to
`StrikeBridge(edge)` and `Recon(sector)`), or add an entity target type. The draft shows the fields only.

```yaml
- id: CONVOY_AMBUSH                   # working name only
  target: <OPEN: entity target type, or EDGE/SECTOR of the convoy's route>
  preconditions: [target_owner_is_coalition, target_in_enemy_view, <OPEN: "currently tracked, not last-known">]
  cost: TBD                           # PROPOSED – unvalidated
  enabled_tiers: [ALPHA, BRAVO]       # an attack, so not Pattern of Life (§3, §5a)
  # priority from director.op_priority.CONVOY_AMBUSH (TBD by harness)
  jobs:
    - { kind: SCOUT, at: <OPEN: convoy's sector selector>, unit_kinds: [ENEMY_RECON_UAV], slots: TBD }   # PROPOSED – unvalidated
    - { kind: STRIKE, at: <OPEN: target selector>, unit_kinds: [ENEMY_STRIKE_FIGHTER], slots: TBD }     # PROPOSED – unvalidated
```

- **Same PR:** THREAT-DIRECTOR §4 step 3 and CONFIG §8a list entries; `director.op_priority.CONVOY_AMBUSH`
  (float, TBD by harness, HR Yes).
- **Threat memory:** none of the four counters matches (they count what the coalition does to the Static), so the
  multiplier is 1. Making ambushes answer coalition convoy traffic would need a new counter: a spec change.
- **Parity:** the Quorum already does this: players strike Static convoys with free orders and board strike jobs. No new
  asymmetry. The Quorum's answer is its existing escort jobs (Q-GP-29), which players choose to take (Q-GP-45).
- **Enemy view:** the convoy is a target only while an ENEMY sensor tracks it. A last-known track isn't enough to
  strike (Q-FOW-4), which is why `SCOUT` comes first; if the scout dies, the `STRIKE` has nothing to resolve and the
  operation drops (TD-2). It never reads coalition stock or route plans.
- **Watch list:** Watch "Convoy ambush", Decision "SCOUT then STRIKE on a tracked coalition convoy, ALPHA and BRAVO,
  values PROPOSED", Revisit if "players stop running supply because every convoy dies, or ambushes are never seen",
  Source "NX-284 (proposed operation)".
- **Golden idea:** seeded ALPHA with a coalition convoy on a road inside Static sensor range → CONVOY_AMBUSH jobs on
  the Static's board within N windows; the same convoy outside every Static sensor → no ambush posted.
- **Rollout:** hot-reload status of the catalog is open (step 7); until answered, assume a new campaign.
