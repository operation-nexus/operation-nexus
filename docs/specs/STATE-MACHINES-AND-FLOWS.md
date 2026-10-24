# SPEC: State Machines & End-to-End Flows

Status: §4.1–4.6 (sim side) Approved (owner, 2026-10-21, Q-SM-6); §4.7–4.10 and §5 (runtime side) Draft until P2 · Owner: — · Tracker: NX-101…NX-126, NX-150…NX-157, NX-170…NX-179, NX-190…NX-204, NX-250…NX-256 · Related ADRs: 0001, 0002, 0003, 0007, 0009

> Event, command and reject-reason names come from [CONTRACTS](CONTRACTS.md); balance key names come from [CONFIG-AND-CONTENT §6](CONFIG-AND-CONTENT.md). This spec uses those names exactly.

> This spec collects the lifecycle of every stateful thing in the system, so that agents implement **one** agreed set of transitions instead of inventing their own. Numbers come from other specs and are **PROPOSED** there (DATA-INTEGRITY DI-7). This spec doesn't introduce new numbers. Transitions that depend on an open owner decision are tagged with that decision's question ID.

## 1. Purpose
- Define states, events, guards, actions and invariants for each lifecycle.
- Define the end-to-end sequences across modules, so the interfaces between modules are explicit.

## 2. Goals / Non-goals
- **Goals:**
  - Unambiguous transitions.
  - Every transition is triggered by a logged command or by a tick-driven rule, so replays stay deterministic (ADR-0002).
  - Every invariant is testable.
- **Non-goals:**
  - Balance values (GAMEPLAY / `balance/*.yaml`).
  - Wire field layouts (WIRE-PROTOCOL / `contracts/`).

## 3. Conventions
- **Sim-side machines** (unit, node, bridge, campaign, objective, director) change state only inside `core.step`. Transitions are driven by commands at a tick, or by rules evaluated on that tick, and every transition emits an event.
- **Runtime-side machines** (commander, adapter, overlay client, ops) live outside the kernel. Any transition that affects the sim does so by emitting a `Command` stamped for a future tick.
- **Table format:** `State | Event / guard | Action | Next`. "—" means no action.
- **Tags:**
  - `[Q-…]` marks a transition that depends on an open question.
  - `[FB-n]` marks a registered fallback (DATA-INTEGRITY §4).

---

## 4. Sim-side state machines

### 4.1 Unit lifecycle (viewer-owned and AI-owned)

```mermaid
stateDiagram-v2
    [*] --> Reserve: !join and live cap reached (GP-3)
    [*] --> Spawning: !join and slot free
    Reserve --> Spawning: slot frees (FIFO) and campaign Running
    Reserve --> [*]: commander leaves queue / banned / forgotten
    Spawning --> Holding: placed at base, no explicit order (loadout by node stock)
    Spawning --> EnRoute: placed at base with an explicit order
    Holding --> EnRoute: explicit order, or (not `hold`) a feasible Tasking Board job taken
    Holding --> Landed: joined with hold (no auto-tasking)
    Holding --> RTB: idle retire
    EnRoute --> OnStation: reached job / target area
    EnRoute --> RTB: !rtb / bingo fuel / munitions out (stance) / mission-kill (stance) / idle retire
    OnStation --> Engaging: valid target in range
    Engaging --> OnStation: no valid target
    OnStation --> RTB: !rtb / bingo fuel / munitions out (stance) / mission-kill (stance) / job complete / idle retire
    Engaging --> RTB: bingo fuel / munitions out (stance) / mission-kill (stance) / idle retire
    EnRoute --> Disabled: a hit drops hp below the Disabled threshold
    OnStation --> Disabled: a hit drops hp below the Disabled threshold
    Engaging --> Disabled: a hit drops hp below the Disabled threshold
    RTB --> Disabled: a hit drops hp below the Disabled threshold
    Disabled --> Destroyed: hp <= 0
    Disabled --> Despawned: wreck timeout (cargo lost)
    RTB --> Landed: arrives at friendly node
    Landed --> Rearming: node stock > 0
    Rearming --> EnRoute: rearmed and has order
    Rearming --> Landed: stock exhausted (stays parked)
    Landed --> Despawned: idle retire / role switch
    Landed --> EnRoute: joined with hold, AUTO after idle handoff, feasible job claimed
    Holding --> RTB: home node captured, mobile, fuel reaches a friendly base
    Landed --> RTB: home node captured, mobile, fuel reaches a friendly base
    Rearming --> RTB: home node captured, mobile, fuel reaches a friendly base
    Holding --> Destroyed: home node captured, cannot escape
    Landed --> Destroyed: home node captured, cannot escape
    Rearming --> Destroyed: home node captured, cannot escape
    Disabled --> Destroyed: node it sits on captured
    Rearming --> Despawned: idle retire
    EnRoute --> Destroyed: hp <= 0
    OnStation --> Destroyed: hp <= 0
    Engaging --> Destroyed: hp <= 0
    RTB --> Destroyed: hp <= 0
    EnRoute --> Orphaned: owner banned / forgotten
    OnStation --> Orphaned: owner banned / forgotten
    Engaging --> Orphaned: owner banned / forgotten
    Orphaned --> Despawned: next tick
    Destroyed --> [*]
    Despawned --> [*]
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| — | `JOIN{role, target, hold}`, campaign Running, live viewer units < `slots.max_viewer_units` (AUTO units count, Q-ALN-9), commander has no live unit, and `slots.respawn_delay_s` (game time, Q-ALN-5) has elapsed | Allocate the next sequential entity id. Map the role to its `UnitKind` (`content/roles.yaml`). Choose the spawn node (GAMEPLAY GP-7, Q-GP-41, Q-SIM-54): a node of the theater's `spawns` list for the unit's domain, owned by the side, nearest the target (straight line for aircraft, road for ground) whose stock exceeds its starvation threshold by `logistics.forward_deploy_min_surplus`; otherwise (and for a null target or `hold`) the sanctuary. The loadout is always full. Debit it from that base's surplus (`SupplyConsumed{SPAWN}`; the sanctuary is never debited). Emit `UnitSpawned`. | Spawning |
| — | `JOIN` and the cap is reached, or `JOIN` from a commander with no live unit while the campaign is Paused, even when a slot is free (Q-ALN-2, Q-ALN-26) | Append to the reserve queue (FIFO by `(target_tick, arrival_seq)`). Emit `ReserveQueueJoined{commander_id, position}`. | Reserve |
| — | `JOIN` that would queue, from a commander not yet queued, while the queue holds `slots.reserve_queue_max` entries (GP-3; reason PROPOSED by NX-122) | Emit `CommandRejected{reason: RESERVE_QUEUE_FULL}` | (no unit) |
| — | `JOIN` while `slots.respawn_delay_s` hasn't elapsed | Emit `CommandRejected{reason: RESPAWN_COOLDOWN}` | (no unit) |
| Reserve | Slot frees and the campaign is Running (a paused campaign spawns nothing, §4.4) | Pop the head of the FIFO and spawn as above. Emit `ReserveQueueLeft{SLOT_FREED}` first (`REJECTED` when the re-check fails) | Spawning |
| Reserve | `SYS_QUEUE_TIMEOUT{commander_id}` (runtime: no chat from the commander for `slots.queue_idle_min` unpaused real minutes; a command that raced a pause still applies) | Remove the entry. Emit `ReserveQueueLeft{TIMEOUT}` | (no unit) |
| Spawning | Same tick, after placement, explicit order present (a stance alone is not an order) | Path to the order target | EnRoute |
| Spawning | Same tick, after placement | `JOIN` with a node: path to it (EnRoute). With no parameters: claim the best matching job at once and path to it (EnRoute), or Holding when none is feasible (Q-GP-23). With `hold`: Holding | Holding or EnRoute |
| Holding | Explicit order (`TARGET`, `REBASE`; `VECTOR` and `RESCUE` come later) | Path to the order | EnRoute |
| Holding | Not `hold`, and a Tasking Board job matches the role, has a free slot and is **feasible with current fuel and munitions** | Claim the job slot, path to it. If no job is feasible, take a rearm/refuel step first (nearest base with stock). | EnRoute |
| Holding | `JOIN … hold` was used | Never auto-task; wait for an explicit order | Landed |
| EnRoute | Inside the job / target radius | — | OnStation |
| OnStation | Valid target in range (COMBAT CB-1 priority) | Assign target | Engaging |
| Engaging | Target dead, out of range, or not valid | Clear target | OnStation |
| any airborne/moving | `!rtb`, fuel ≤ bingo, or job complete | Path to the nearest friendly node valid for the domain | RTB |
| any airborne/moving | Missiles/bombs empty, stance not `press`/`guns` (Q-CBT-7) | As above | RTB |
| any airborne/moving | Damage state reaches Mission-kill and stance is `standard` (or Damaged and stance is `cautious`), still mobile (Q-CBT-6) | As above | RTB |
| any alive, moving | A hit drops hp below the Disabled threshold (can't move, not destroyed; COMBAT CB-6) | Emit `UnitDamageStateChanged{DISABLED}`. Seeded crew-survival roll; a surviving crew emits `CrewDowned` and a downed-crew marker (GAMEPLAY §6a). | Disabled |
| RTB | Arrives at a friendly node | — | Landed |
| Landed | Node stock > 0 | Spend stock over time and restore fuel, ammo and hp (GAMEPLAY §5). Units never heal anywhere else. | Rearming |
| Rearming | Full, and there is an order | Path to the order | EnRoute |
| Rearming | Node stock hits 0 | Stop. Emit `RearmStalled{entity_id, node_id}` once per stall. | Landed |
| any alive, `COMMANDER`-owned, control `OPERATOR` | **Idle handoff:** no chat command from the owner has reached the sim for `presence.idle_handoff_min` (game time, Q-GD-35, Q-ALN-1) | Set control to `AUTO`. Emit `UnitControlChanged{control: AUTO, cause: IDLE_HANDOFF}`; the overlay shows the AUTO tag. The current order is not cancelled; once it completes, the Tasking Board tasks the unit as an AI-run unit (U-6). The unit keeps its slot (Q-ALN-9). | (unchanged) |
| Holding / EnRoute / OnStation / Engaging, `COMMANDER`-owned | **Idle retire:** no chat command from the owner has reached the sim for `presence.idle_retire_min` (game time, Q-GD-35) | Release any claimed job slot. Path to the nearest friendly node valid for the domain. | RTB |
| Landed / Rearming | Idle retire elapsed (as above) | Unload carried cargo into this base's stock (Q-GD-35, Q-GP-16). Emit `UnitDespawned{reason: IDLE}`. The slot frees. | Despawned |
| Disabled, any owner, not a facility | `combat.disabled_timeout_s` (game time) has elapsed since it became Disabled. No field repair in the first build (Q-CBT-14). | Despawn in place. Carried cargo is **lost**. Emit `UnitDespawned{reason: WRECKED}`. The slot frees; the owner's respawn delay starts (GP-2). | Despawned |
| Landed, control `AUTO`, joined with `hold` | Idle handoff applies to `hold` units like any other, and the unit keeps holding (Q-ALN-25). A Tasking Board assignment pass (TB-6) finds a job that matches its role, has a free slot and is feasible (U-6) | Claim the job slot, path to it | EnRoute |
| any alive, control `AUTO` | **Reclaim:** any chat command from the owner reaches the sim (Q-ALN-9) | Set control to `OPERATOR`. Emit `UnitControlChanged{control: OPERATOR, cause: RECLAIM}`. Then evaluate the command against this unit; a `JOIN` never spawns a second unit. | (per command) |
| Landed | `JOIN` with a different role while at base | Emit `UnitDespawned{reason: ROLE_SWITCH}` | Despawned |
| Holding / Landed / Rearming at node N | N flips to the other side (§4.2, Q-GD-32); the unit is mobile and its fuel reaches the nearest reachable friendly node valid for its domain | Release any claimed job slot. Path to that node. | RTB |
| Holding / Landed / Rearming / Disabled at node N | N flips to the other side and the unit cannot escape (Disabled, or no friendly node within fuel reach) (Q-GD-32) | Seeded crew-survival roll on the `combat` stream; a surviving crew emits `CrewDowned` and a downed-crew marker (GAMEPLAY §6a). Emit `UnitDestroyed{killer: null}`. Start the respawn delay for the owner. | Destroyed |
| any alive | hp ≤ 0 (combat resolution this tick) | Emit `UnitDestroyed{killer?, assists[]}`. Start the respawn delay for the owner. | Destroyed |
| any alive | Owner banned (`STAFF_BAN` applied → `CommanderBanned`) or forgotten (`FORGET` applied → `CommanderForgotten`) | Emit `UnitOrphaned{cause: BANNED \| FORGOTTEN}` | Orphaned → Despawned next tick with `UnitDespawned{reason: OWNER_BANNED \| OWNER_FORGOTTEN}` |

Notes:
- **In code now (NX-122; NX-123 parts 1 and 2):** a JOIN with a node target forward-deploys (GP-7: a qualifying `spawns` base, debited its `loadout_cost`), otherwise spawns at the coalition sanctuary, always with a FULL loadout; a logistics truck sent to a friendly node instead spawns at its source base and loads cargo from that base's stock above its starvation floor (the sanctuary as last resort), then drives the road route and unloads at the destination (SIM-CORE §4 Logistics). The cap and the reserve queue are in code: a valid JOIN (every reject check passed) queues while Paused, at the cap, or while the queue is not empty, so a newcomer never passes a queued commander (U-4); the `lifecycle` system serves the head while a slot is free on running ticks, re-checking it as a fresh JOIN (an entry no longer valid gets that check's `CommandRejected` and the next is served). A second JOIN from a queued commander replaces its entry in place and repeats `ReserveQueueJoined` with the same position; a newcomer to a queue of `slots.reserve_queue_max` entries is rejected with `RESERVE_QUEUE_FULL`. A JOIN while Paused from a commander with a live unit is rejected with `CAMPAIGN_PAUSED`; one from a commander still in its respawn delay gets `RESPAWN_COOLDOWN` and is not queued (the delay is frozen while Paused, SC-11). On a tombstoned tick (SIM-CORE SC-8) the entries the queue would serve, at least its head, are dropped with `CommandRejected{INTERNAL_ERROR}`, so a queued JOIN that crashes the sim cannot crash every recovery. "You're in" is the served commander's `UnitSpawned`; Every exit from the queue emits exactly one `ReserveQueueLeft{commander_id, reason}` (NX-371): `SLOT_FREED` when served, `REPLACED` when the commander's own JOIN replaces the entry (then `ReserveQueueJoined` repeats, so Joined/Left stay 1:1 and a public counter needs no per-commander state), `REJECTED` when the serve-time re-check fails or a tombstoned tick drops it, `TIMEOUT` from the logged `SYS_QUEUE_TIMEOUT{commander_id}` the runtime submits when the commander has sent no chat message for `slots.queue_idle_min` of unpaused real time (`nexus.runtime.queue_idle.idle_entries`; the runtime host that tracks queue times and calls it is not wired yet). Milestone position updates (RQ-1), the dynamic cap (RQ-2) and ban/forget removal (`STAFF_BAN` and `FORGET` do not exist yet) come later. Details: SIM-CORE §4.
- **In code now (NX-374 part 1, `nexus.core.tasking`; SIM-CORE §4 Tasking Boards):** the Holding rows. A unit is *idle* (Holding) when it is not Disabled, has no path, is not RTB, holds no job and has no explicit order; every `tasking.reeval_every_ticks` running ticks each idle unit, in id order, takes the best job that fits it (carriers resupply and do nothing else on the board, recon scouts, armed aircraft strike or defend, armed ground units defend, other ground units assist an objective), has a free slot (any, when all are full) and is feasible (fuel to the target and on to a landing base with the bingo reserve left, a road route, cargo for a resupply, a round for a strike), then paths to it (EnRoute). A unit that fails only for fuel or rounds takes the rearm/refuel step instead: it flies to the nearest landing base with stock and is tried again next pass (an empty truck's step is a drive to a source, where it loads). `JOIN … hold` sets order HOLD (never auto-tasks); a JOIN with a node sets order GOTO, which ends when the unit has no path, no cargo and no capture bar of its side where it stands (a capture run ends with the capture); an armed unit at the order's node holds it first (Q-SIM-110, NX-398: an aircraft ON_STATION over it, a ground unit on it, engaging by CB-1) until bingo or RTB, ammo out, landing, Disabled, a REBASE or `tasking.order_dwell_s` (one stopped short of the node hands back as before), and no new state is added; a JOIN with no parameters claims the best job in the Spawning step, and with none waits in Holding. A claim becomes ACTIVE when the unit has a path or has arrived, and is released after `tasking.claim_lease_s` without either, when the unit is lost, Disabled or RTB, or when it is given an explicit order (a human order wins, TB-7). Idle retire, the AUTO handoff and `TARGET`/`RTB` are not in code. `REBASE` is (NX-158, Q-SIM-90, `nexus.core.handlers.rebase`): it is the Holding to EnRoute row for a unit with a live commander. It releases a held job and a follow, sets order HOLD and a path to the base, and the unit holds there after arrival (refuelling and rearming from the base's stock) until a later order, which no handler gives yet.
- **In code now (NX-368, aircraft only):** aircraft carry four of these states: `LANDED`, `EN_ROUTE`, `ON_STATION`, `RTB` (SIM-CORE §4). A JOINed aircraft spawns `LANDED` at the sanctuary with full fuel; with a target it takes off on its first `movement` tick (Spawning → EnRoute), and without one it stays `LANDED` (Spawning → Holding / Landed: Holding is on the ground and behaves as Landed until auto-tasking, NX-155). An airborne aircraft that reaches the end of its path is `ON_STATION` and orbits that point at `min_speed_mps` until a new path or bingo fuel. Bingo (`fuel` ≤ flight time to the nearest landing base + `air.bingo_reserve_frac` × `fuel_s`) is the only RTB trigger in code; any path that ends at one of its side's landing bases lands it there, and a JOIN to the base it stands on keeps it landed. **Fuel 0 → Destroyed** (owner, 2026-10-21): the aircraft crashes like a shoot-down, `UnitDestroyed{killer_id: null}` is emitted and the owner's respawn delay starts; the crew-survival roll and wreck come with combat (NX-124); "friendly node valid for the domain" for an aircraft is its side's AIRBASE or SANCTUARY nodes, never an FOB, HQ, port or bridge (Q-SIM-38). RTB → Landed on arrival. A `LANDED` aircraft with a path takes off. **Landed → Rearming (NX-123 part 2):** a `LANDED` aircraft with no path at a friendly base buys fuel from its stock (free at the sanctuary), up to a full tank, or half a tank at a base under its starvation floor; at 0 stock it emits `RearmStalled` once and stays `LANDED` (there is no separate Rearming state in code: the `logistics` system refuels any landed aircraft; guns wait for NX-124). One ordered off at or below bingo stays on the ground and refuels first. Ground units have no state field yet; Rearming, Engaging and the other rows come with their items.
- A unit owned by `AI_GARRISON`, `ENEMY_DIRECTOR` or an NPC wingman carries an AI owner reference and must render with the AI marker (DATA-INTEGRITY DI-5).
- Sea-domain units follow the same machine on the naval graph (**P3**, Q-GD-8).
- **Control is orthogonal to the lifecycle state** (Q-GD-35, Q-ALN-9): a `COMMANDER`-owned unit is `OPERATOR` or `AUTO`. Both idle timers count game-time ticks from the owner's last chat command that reached the sim (accepted or rejected); every such command resets them, except `ME` (`!me`/`!status`), which is informational and never resets them, so repeating it cannot keep a unit under operator control (Q-ALN-26). Gateway-only commands (`!help`, `!guide`, `!rules`, `!link`, `!quiet`, `!callsign`) never reach the sim, so they do not reset them (confirmed, Q-ALN-26). The AUTO tag shows from the handoff tick, and the current order is kept. The timers freeze while paused (SIM-CORE SC-11). These two timers are the only idle rule (Q-ALN-8).
- **In code now (NX-124 part 1, `nexus.core.combat`):** the damage-state rows. `Entity.damage_state` follows `hp` (thresholds in whole hp of the kind, CB-6) and a hit that changes it emits `UnitDamageStateChanged`; a hit that takes a non-facility to Disabled clears its path and starts `wreck_left` (`combat.disabled_timeout_s` in running ticks); at 0 the wreck is removed with `UnitDespawned{WRECKED}` and `record_loss` (a unit at 0 hp is `UnitDestroyed{killer_id}` at once); a facility's hp floors at the Disabled threshold and it never leaves the world (U-2). A Disabled unit cannot be re-pathed, so it cannot escape a flipped base and is lost with `UnitDestroyed{killer: null}`; the crew rolls, `CrewDowned`, auto-RTB and the damaged slowdown are in code in part 2 (COMBAT "In code now (part 2)"): a Landed or parked unit at a friendly base rearms, refuels and repairs in one stop (SIM-CORE §4 Rearm stop), a wreck is never repaired, auto-RTB fires once on the transition (Mission-kill, last missile) and later orders stand, and a Disabled facility repaired above its floor works again. An airborne aircraft that reaches Disabled is destroyed at once with the shooter as killer (Q-SIM-66); a LANDED one is a wreck. `UnitDestroyed.assist_ids` come from `Entity.hits` (COMBAT CB-5a).
- **Damage state is orthogonal to the lifecycle state** (Q-CBT-1): `HEALTHY → DAMAGED → MISSION_KILL → DISABLED`, with `Destroyed` as the terminal lifecycle state. It only moves toward worse states through combat, and back toward HEALTHY only in Rearming (base repair). A Disabled unit is a wreck with no way back in the first build (COMBAT CB-7). DAMAGED applies the speed and sensor penalties from config. Both sides use the same machine (parity, GAMEPLAY §0).

**Invariants**
- U-1: a commander has at most one unit in {Spawning, Holding, EnRoute, OnStation, Engaging, RTB, Landed, Rearming, Disabled} (GP-1).
- U-2: a unit's hp > 0 in every non-terminal state, and a terminal unit appears in no live index. Facilities never reach Destroyed: their hp floors at the Disabled threshold (Q-GP-37).
- U-3: hp, fuel and ammo only increase in Rearming, or, for a facility, by repair at its friendly, uncontested base (Q-GP-26).
- U-6: a unit in Holding takes a Tasking Board job only if it can reach and complete it with its current fuel and munitions (Q-GD-26); the friendly AI garrison never claims a strike job no player started.
- U-4: reserve queue order is strict FIFO, and a commander appears in it at most once.
- U-5: an orphaned unit is despawned within 1 tick and earns no XP after orphaning.
- U-7: an AUTO unit counts toward `slots.max_viewer_units` and holds its commander's U-1 slot until it is Despawned or Destroyed; a command from that commander reclaims it and never spawns a second unit (Q-ALN-9).
- U-8: while the campaign is Paused, no chat command spawns, moves, fires, captures with or despawns a unit (Q-ALN-2). The only despawns while Paused are a unit orphaned by `STAFF_BAN` or `FORGET`, which are safety actions (Q-ALN-24), and a unit removed by `STAFF_PURGE_UNITS` (Q-ALN-36) (§4.4).
- U-10 (Q-GP-31..33): a unit with `follow_id` keeps station on that unit; it holds when the leader stops, lands or parks with it at a base and keeps following, and when the leader dies or despawns it takes the leader's own `follow_id` if any, else re-tasks. A follow that would create a loop, a self-follow, or a follow of a STATIC unit or another side's unit is rejected with `FOLLOW_TARGET_INVALID`; so are a Disabled leader and a ground unit after an aircraft. An armed follower breaks station toward a threat to its group (a tracked enemy that fired at a member within `tasking.escort_threat_memory_s` or has a weapon in range of one) within `tasking.escort_leash_m` and returns when none remains (Q-SIM-76). **In code now (NX-374 part 2, `nexus.core.follow`):** `Entity.follow_id` with the order `FOLLOW` (a JOIN with a follow target) or an escort-job claim; the follow rows are all in code except `!target` (no handler yet), and a unit sent home (RTB) stops following. Details: SIM-CORE §4 Follow and formation speed.
- U-9: when a node flips owner, no unit of the losing side stays parked there: each one is RTB toward another friendly node or Destroyed in the same tick (Q-GD-32). Facilities (entities with a `base_id`) are exempt: they switch side with the base and keep their damage (Q-GP-25).

### 4.2 Node capture

```mermaid
stateDiagram-v2
    [*] --> Neutral
    [*] --> Owned
    Neutral --> Capturing: eligible ground/logi unit in radius, no enemy ground unit
    Owned --> Contested: enemy eligible unit in radius
    Contested --> Capturing: defenders gone, attackers remain
    Contested --> Owned: attackers gone
    Capturing --> Owned: progress reaches 100% (flip to capturer)
    Capturing --> Contested: opposing eligible unit enters (bar decays)
    Capturing --> Decaying: capturers leave, uncontested
    Decaying --> Capturing: capturer returns
    Decaying --> Neutral: progress reaches 0 and node was neutral
    Decaying --> Owned: progress reaches 0 and node had an owner
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| Neutral / Owned | An eligible ground or logistics unit of a non-owner side enters `capture.radius_m`, with no opposing eligible unit present, **and the node's defense HP is 0** (Q-GD-18; a NEUTRAL node has 0) | Emit `CaptureStarted{node_id, side}` | Capturing / Contested |
| Capturing | Tick, still uncontested | Progress += rate × diminishing f(unit count) × garrison modifier × `WORLD_DT`, where the unit count weighs each logistics unit (LOGI_TRUCK, ENEMY_CONVOY) as `capture.logi_weight` of a capturer (PROPOSED 0.5, Q-SM-7) (capture runs on world time, Q-ALN-23). **Garrison modifier (Q-GD-32):** the garrison multiplier `capture.garrison_mult` (capture time ×3, PROPOSED) while any unit of the owning side is at the node, or the empty-base multiplier `capture.empty_base_mult` (capture time ×0.5, PROPOSED) while none is (Q-SM-8). A combat-capable defender freezes progress (Contested); defenders that cannot contest, such as parked air units and Disabled units, slow it through the garrison multiplier instead (Q-ALN-33). A Neutral node has no owner and uses neither multiplier. | Capturing |
| Capturing | Progress ≥ 100% | Set owner = capturer. Reset progress. Emit `NodeCaptured{node_id, from, to, participant_commander_ids[]}`. In the same tick, resolve the losing side's units parked at the node: mobile units able to reach a friendly node escape (RTB): a ground unit when a road route to a friendly base exists, an aircraft when its fuel reaches one of its landing bases (Q-SM-10); every other mobile or parked unit is Destroyed with a crew-survival roll (§4.1, Q-GD-32); facilities switch side and keep their damage (Q-GP-25). Applies to both sides. | Owned |
| Capturing | Opposing eligible, combat-capable unit enters (parked air and Disabled units do not contest, Q-ALN-33) | Progress −= decay rate × `WORLD_DT` while contested, as for an abandoned bar (owner, 2026-10-21, Q-SIM-23); at 0 the bar is removed and the start rule applies again | Contested |
| Contested | One side's eligible units are all gone | — | Capturing (attacker remains) / Owned (defender remains) |
| Capturing | No capturers, no opponents | — | Decaying |
| Decaying | Tick | Progress −= decay rate × `WORLD_DT` (world time, Q-ALN-23) | Decaying, then Owned/Neutral at 0 |

**Invariants**
- N-1: at most one ownership flip per node per tick.
- N-2: progress stays in [0, 100] and is monotonic while *un*contested capture continues; a contested bar decays (owner, 2026-10-21, Q-SIM-23).
- N-3: air units never change capture state (GAMEPLAY §8). Default; Q-CFG-16 option `capture.air_counts` lets airborne aircraft add capture weight (never contest), and the property then does not hold.
- N-4: the SANCTUARY node never leaves Owned (Q-GD-7).
- N-5: all else equal, capture progress per tick at an owned node is lower with a defending unit that cannot contest (parked air, Disabled) present than with none, and decaying (Contested, not rising) with a combat-capable defender present (Q-GD-32, Q-ALN-33).

**In code now (`nexus.core.capture`, NX-125; SIM-CORE §4 Capture):** one bar per node (the side filling it, progress in integer millionths of a percent), live owners in `World.owner`. "Eligible" is a GROUND unit within `capture.radius_m`; "combat-capable" a GROUND unit whose catalog has weapons and that is not Disabled (NX-124); a unit that cannot contest is an unarmed or Disabled ground unit or an aircraft LANDED at the base. A bar fills while its side has capturers and the other side has no combat-capable unit there, and drains at `capture.decay_per_s` otherwise: abandoned (Decaying) or contested by a combat-capable unit (owner, 2026-10-21, Q-SIM-23); at 0 the bar is removed and the owner stays, and the start rule applies again, so an armed side facing only unarmed units then starts its own bar. It flips at 100%. The capture time is `max(min_time_s, base time × garrison/empty modifier)`: `min_time_s` caps a crowd even against an empty base. `CaptureStarted` fires when a bar begins at 0 (again after it decayed away). At a neutral node where both sides have capturers and neither a combat-capable unit, the side with the larger capture weight (logistics units count `capture.logi_weight`) starts the bar and an exact tie starts nothing (Q-SIM-59); a running bar is not stopped by the other side's unarmed units; a bar of one side at a neutral node drains to 0 before the other side starts. Sanctuary and BRIDGE nodes are never captured (N-4). Not in code: the defense-HP gate (Q-GD-18), `CaptureProgress`, the crew-survival roll.

**In code now (NX-124 part 3, `nexus.core.defense`; SIM-CORE §4 Defense):** a node with defense HP above 0 starts no bar (default; Q-CFG-16 option `capture.requires_defenses_down`); a bar already running is not stopped by a later repair, and a flip sets the HP to 0 for the new owner (no event; `NodeCaptured` says it). With no live viewer unit the `forward_airbase` (while the coalition owns it) is skipped: its bar neither starts, fills nor decays (idle floor, Q-GP-28).

### 4.3 Bridge

```mermaid
stateDiagram-v2
    [*] --> Intact
    Intact --> Damaged: hp below damaged threshold
    Damaged --> Destroyed: hp <= 0
    Intact --> Destroyed: hp <= 0
    Destroyed --> Repairing: truck or engineer present (Q-GD-11)
    Damaged --> Repairing: truck or engineer present (Q-GD-11)
    Repairing --> Intact: repair complete
    Repairing --> Destroyed: actor leaves before completion and hp <= 0
    Repairing --> Damaged: actor leaves and hp > 0
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| Intact / Damaged | hp ≤ 0 | Remove the ROAD edge from the graph. Emit `BridgeDestroyed{lost_ids}`. Destroy the GROUND units on the edge within `logistics.bridge_collapse_radius_m` of the cut point (Q-SIM-112), then reroute affected convoys. | Destroyed |
| Destroyed / Damaged | Repair actor in radius: a **logistics truck** (slow field repair) or an **engineer** (fast) (Q-GD-11) | Restore hp at the actor's repair rate: engineer = `logistics.bridge_repair_time_s`, truck = that time × `logistics.truck_bridge_repair_mult`. Repair runs on world time (`WORLD_DT`, Q-ALN-23). | Repairing |
| Repairing | hp = max | Restore the edge. Emit `BridgeRepaired{node_id, by_id}`. | Intact |

**Invariants**
- B-1: a Destroyed bridge's edge is absent from every path computed after that tick.
- B-2: a repair never exceeds max hp.
- B-3: only a unit holding a STRIKE claim on a bridge fires at it; a direct order to it never does (Q-SIM-124).

**In code now (NX-373 part 1a, `nexus.core.bridges`; Q-SIM-105 to Q-SIM-107, lead decisions, owner may veto):** each BRIDGE node has its own hp, `World.bridge_hp` (every bridge in id order, starting at `logistics.bridge_hp`, PROPOSED 300, next to FOB defense HP; Q-SIM-101), apart from the capture defenses (`capture.defense_hp`), and `World.bridge_down`, the bridges that reached 0 (snapshot format 24). Only a unit holding a claim on a STRIKE job whose node is the bridge fires at it (B-3), with a STRUCTURE weapon, the bridge in range and hp left, after any unit target (CB-1 ranking unchanged) and before CB-10's automatic node fallback, which never picks a bridge. A hit takes the weapon's full damage, never below 0, and adds no provocation (a bridge is nobody's); a shot that lands on a bridge at 0 fizzles. At 0 the bridge is Destroyed: it joins `bridge_down` and emits `BridgeDestroyed{node_id, by_id, lost_ids}` (the shooter, and the units the fall destroyed, sorted) once; it stays down until repaired to full (part 2), and the Damaged state has no effect yet. Every path planner (board routes and patrols, JOIN routes, truck runs and escapes, followers, garrison recall) passes the down set to the road search, so B-1 holds for every path computed after the tick. A STRIKE job on a bridge is DONE once the bridge is down. There is no regeneration and no starvation drain. Restore checks the bridge state (`bridges.validate`). **Collapse (NX-400, `bridges.collapsing`; Q-SIM-112, owner):** the hit that drops a bridge then destroys, before the reroute and in entity-id order, every GROUND unit of either side on the bridge's edge (not standing on an end node) within `logistics.bridge_collapse_radius_m` (PROPOSED 1000 m) of the cut point, measured along the edge: each is lost as a combat kill (`UnitDestroyed{killer_id: the shooter, assist_ids: [], cause: BRIDGE_COLLAPSE}`), with its cargo, the respawn delay of its commander and the CB-8 crew roll for a unit not yet Disabled; a victim of the other side counts for the Static like any kill (`provocation.suffered_hit`, no new weight). Aircraft are not affected. Same rule for both sides. **A direct order defends (NX-408; Q-SIM-124, owner, amending Q-SIM-112's "a direct order can drop a bridge"):** a unit holding a direct GOTO order to a bridge (`Entity.order_node`) holds there per Q-SIM-110 and engages threats by CB-1, but never fires on the span, whichever side holds the banks; dropping a bridge takes an explicit strike (a STRIKE job; later `!target`). No coalition job targets a bridge yet (STRIKE jobs take only enemy-held nodes with defense HP; a bridge is NEUTRAL with none), so a player cannot drop a bridge today: that waits for `!target <bridge>` (NX-192), the explicit strike per Q-SIM-124, and the Static's bridge STRIKE comes with NX-401. **In code now (NX-373 part 1b, `bridges.reroute`; Q-SIM-108, lead decision, owner may veto):** the hit that brings a bridge down reroutes, in the same combat slot, every GROUND unit with a path, in entity-id order. The *cut point* is the bridge node's position projected on its edge. A unit on the cut edge still short of the cut point (on the near bank) turns back: its path becomes the node it came from plus the road route from there to its last path node, or just that node when no route exists. A unit at or past the cut point and beyond the collapse radius carries on. A unit whose later hop uses a cut edge keeps its path up to the node before that hop and replans from there (or stops there). Replans use `roads.shortest_path` with the down set; a coalition patrol replans only through nodes its side holds (as `tasking._patrol_route`), a supply run of either side (a RESUPPLY claimant, or a loaded truck on a GOTO order to its path's last node; an empty capture-run truck takes any road) around nodes the other side holds, neutral ones passable and its destination exempt (as `logistics.supply_route`, Q-SIM-122, NX-407), and a Static patrol's `via` is dropped (it goes straight home). A unit that stops keeps its claim until the lease runs out (`tasking.claim_lease_s`), then the board assigns it again; a loaded truck that stops unloads at its bank node if that base is friendly, else `_divert` sends it to the nearest friendly base; a supply truck (a RESUPPLY claimant or a GOTO order) stopped on a node the other side does not hold diverts only by a road that enters no node the other side holds, and with none it holds there with its cargo, emitting nothing, and tries again every tick, so it leaves as soon as a road opens (the repair, a capture); a truck on a node the other side holds flees by any road (Q-SIM-126, lead decision, owner may veto). Aircraft are not rerouted. **Bank rule:** a follower or escort on a cut edge never routes from the end across the cut point (`follow._ends`). **In code now (NX-373 part 2, `bridges.repair`; Q-GD-11, Q-SIM-101; lead decisions, owner may veto):** a bridge is not a road endpoint, so the repair actor's "radius" is its *stop*: the bridge's position projected on its edge (the cut point), reached along the half of the edge from a bank, the truck's `last_node` staying that bank (so it can only leave the way it came). Each logistics carrier of either side parked there (no path, not Disabled) restores `logistics.bridge_hp / (bridge_repair_time_s × truck_bridge_repair_mult)` hp per world second (PROPOSED 600 s × 5: one truck repairs 300 hp in 3,000 world s, 5,000 ticks; two in half), kept in thousandths of an hp (`World.bridge_repair`, snapshot format 26), capped at the maximum (B-2), with no cargo cost and not while paused; it repairs a Damaged bridge too. A truck that leaves keeps the bridge where it is (no regeneration, the carry kept): the Repairing state is just "a carrier is parked there". At full hp the carry is 0 and a down bridge's latch clears, its edge returns to every planner and `BridgeRepaired{node_id, by_id}` names the lowest-id carrier parked there; a Damaged bridge that was never down emits nothing. Engineers (the fast `bridge_repair_time_s` actor) come with the engineer specialist (P4). A down bridge is never fired at, even once part repaired (Q-SIM-112's constraint). A GOTO order to a bridge outlasts its fall, whether the unit is there or still under way: since Q-SIM-124 a holder never fires on a bridge, so it keeps guarding the repair crews until another exit ends the hold (Q-SIM-127, lead decision, owner may veto; this drops Q-SIM-115's end of the order at the first pass while the bridge is down). **The job:** the coalition board posts `REPAIR_BRIDGE` (key `repair_bridge:<node>`, urgency 1.0, `tasking.priority.repair_bridge` 45, `tasking.slots.repair_bridge` 2, PROPOSED) for each down bridge some live coalition carrier can reach a bank of by road; carriers only, the AI garrison by itself (`tasking.ai_jobs`); the Static's board never posts it, so the board never undoes the Director's cuts. The claimant drives to the nearer bank and out to the stop; the job is DONE when the bridge is up again (a participant needed, else EXPIRED, unless a job waits for it), and its trucks then drive back to their bank. **Escort (Q-SIM-118):** each truck holding the claim gets an `ESCORT_CONVOY` job with no threat test (`tasking.escort_repair_crews`, default on), DONE when the bridge is repaired, FAILED when the truck is lost or Disabled while claimed, EXPIRED when the truck drops the repair (GAMEPLAY §1b). A truck parked at a stop that is sent home or rebased drives back along the road through its bank (`logistics.road_start`). **Nobody idles at a stop:** a truck whose repair claim ends or is released (done, lease, eviction, an order) drops the stop from its path, turning back to its bank if it is already on the bridge's road, and heads back to its bank if it is parked there (`world.leave_stop`); as a backstop, each board pass sends every ground unit that is not Disabled, follows no one and holds no repair claim the same way. A unit at a stop, a follower too, leaves only by its own bank (`follow._ends`), never over the cut. **TB-8:** a coalition RESUPPLY job whose node no friendly source reaches by road (`plan_run`) waits for the REPAIR_BRIDGE job of the first down bridge on the intact road route from the coalition sanctuary: it cannot be claimed until that job is DONE, and fails if it fails or expires. Neither route enters a node the other side holds (`bridges.enemy_held`, Q-SIM-122; neutral nodes are passable): a node reached only through enemy ground depends on no repair, and its job expires unclaimed. **Not yet:** engineers; the Director's bridge strike (part 3, NX-401); overlay bridge HP, an "under attack" state and `NodeView.hp_pct` for a bridge (P2; the view is not built).

### 4.4 Campaign lifecycle

```mermaid
stateDiagram-v2
    [*] --> Setup
    Setup --> Running: theater + seed + config hash loaded and validated
    Running --> Paused: STAFF_CAMPAIGN_PAUSE (STAFF / TECHNICAL / MAINTENANCE / CEASEFIRE)
    Paused --> Running: STAFF_CAMPAIGN_RESUME
    Running --> Ending: victory / defeat / time limit (score)
    Running --> Ending: STAFF_CAMPAIGN_END (ABORTED)
    Paused --> Ending: STAFF_CAMPAIGN_END (ABORTED)
    Ending --> AAR: final state frozen, results computed
    AAR --> Archived: AAR screen duration elapsed
    Archived --> Setup: next theater/seed selected
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| Setup | Theater, seed and balance config pass schema validation | Record `campaign_id`, seed and config hash. Emit `CampaignStarted`. | Running |
| Setup | Validation fails | Refuse to start. Overlay shows "CAMPAIGN SETUP FAILED" (no fallback theater). Alert. | Setup |
| Running | `STAFF_CAMPAIGN_PAUSE{reason_category, sub_reason, note}` from staff (category and note required, Q-RB-1; `sub_reason` optional and allowed only with category `STAFF`, Q-ALN-31; `CEASEFIRE` from the owner, Q-OPS-9), or from SYSTEM for an automatic pause (`TECHNICAL`: broadcast offline longer than `ops.offline_pause_after_min`, Q-OPS-8; `MAINTENANCE`: weekly window, Q-OPS-9) | Set `clock_paused`, `pause_reason` and `pause_sub_reason`. Emit `CampaignClockPaused{reason, sub_reason}` (Q-ALN-3, Q-ALN-31). Alert the owner immediately (ADMIN-RBAC pause flow). Lack of humans never pauses (Q-GD-4 amended). | Paused |
| Paused | Tick | **The whole world freezes** (Q-ALN-2): neither game time nor world time advances, so no movement, combat, logistics, capture, objective timer or other sim timer progresses (SIM-CORE SC-11). | Paused |
| Paused | Chat command that doesn't change the world: `ME` (alias `!status`), or `JOIN` from a commander with no live unit | `ME` works as when Running. The `JOIN` always joins the reserve queue, even when a slot is free (§4.1, Q-ALN-26), and spawns FIFO after resume; a commander still in its respawn delay gets `CommandRejected{reason: RESPAWN_COOLDOWN}` instead, as the delay is frozen while Paused (NX-122). (`!quiet`, `!callsign` and the info commands are handled outside the sim and work as usual.) | Paused |
| Paused | Any other chat command that reaches the sim | Emit `CommandRejected{reason: CAMPAIGN_PAUSED}`; the digest replies "war paused" (Q-ALN-2) | Paused |
| Paused | Safety action: `STAFF_BAN`, `FORGET` or `STAFF_KILL_SWITCH` (Q-ALN-24) | Apply as when Running. A unit orphaned by `STAFF_BAN` or `FORGET` despawns at once (`UnitDespawned{reason: OWNER_BANNED \| OWNER_FORGOTTEN}`) instead of waiting for resume. A banned commander leaves the reserve queue. | Paused |
| Paused | `STAFF_CONFIG_RELOAD` (Q-ALN-24) | Validate and hold; no balance value changes while Paused. Apply held reloads in arrival order in the tick `STAFF_CAMPAIGN_RESUME` is applied, and emit `BalanceReloaded` then. Held reloads are discarded if the campaign ends instead (C-3). | Paused |
| Paused | `STAFF_DIRECTOR_OVERRIDE` (Q-ALN-24) | Emit `CommandRejected{reason: CAMPAIGN_PAUSED}` | Paused |
| Paused | `STAFF_UNBAN`, `STAFF_PURGE_UNITS` or `SYS_SET_CALLSIGN` (Q-ALN-36) | Apply as when Running. Units removed by `STAFF_PURGE_UNITS` despawn at once (`UnitDespawned{reason: PURGED}`). | Paused |
| Paused | `ADVISOR_CHOICE`, or a GM command other than a release (`STAFF_GM_TAKEOVER`, `STAFF_GM_OPERATION`, `STAFF_GM_VERDICT`, `STAFF_GM_LIMITS`, `STAFF_GM_INJECT_JOB`) (Q-ALN-36) | Emit `CommandRejected{reason: CAMPAIGN_PAUSED}` | Paused |
| Paused | `STAFF_GM_RELEASE`, from the GM or from SYSTEM on auto-release (Q-ALN-36) | Apply as when Running: control returns to the director | Paused |
| Paused | `STAFF_CAMPAIGN_PAUSE` | Emit `CommandRejected{reason: ALREADY_PAUSED}` | Paused |
| Paused | `STAFF_CAMPAIGN_RESUME` from staff (GM, admin or owner only, Q-RB-1), or from SYSTEM after the "COMMS RESTORED" countdown ends an offline pause (Q-OPS-8) | Clear `clock_paused`. Emit `CampaignClockResumed{reason}`. Free slots fill from the reserve queue (FIFO). | Running |
| Running | Victory condition held (GAMEPLAY §9), or defeat (the sanctuary's defense HP held at 0 for `campaign.defeat.hold_min`, Q-TH-7) | Freeze inputs. Emit `CampaignEnded{result: VICTORY \| DEFEAT}`. | Ending |
| Running | The campaign clock reaches its time limit (game time), and the two sides' time-limit scores differ | Score per side = `campaign.score.average_weight` (PROPOSED 50) × its average share of strategic nodes over the campaign + `campaign.score.final_weight` (PROPOSED 50) × its share at the final tick + `campaign.score.objective_points` (PROPOSED 5) per completed objective, coalition only (Q-GD-29, Q-SIM-64). Freeze inputs. Emit `CampaignEnded{result: TIME_LIMIT, score, winner}`; the higher score wins the war, and a Static win (`winner: ENEMY`) is shown as a defeat ("SIGNAL LOST"). The Static has no mid-war win. | Ending |
| Running | Time limit reached and the two scores are exactly equal (Q-GD-29, Q-GP-10) | Freeze inputs. Emit `CampaignEnded{result: TIME_LIMIT, score, winner: null}`: a draw, with the normal end screen. | Ending |
| Running / Paused | `STAFF_CAMPAIGN_END{reason}` | Freeze inputs. Emit `CampaignEnded{result: ABORTED}`. | Ending |
| Ending | Results computed (top contributors per role, stats) | Write results to persistence. Emit `AARStarted{result, top_by_role}`. | AAR |
| AAR | `campaign.aar_duration_s` elapsed | Close the command log. Write the final snapshot. Mark archived. | Archived |
| Archived | Next theater/seed chosen (rotation rule: Q-SM-4) | — | Setup |

**Invariants**
- C-1: in Paused, neither game time nor world time advances: no entity position, hp, stock, capture progress, objective timer or other sim timer changes (Q-ALN-1, Q-ALN-2).
- C-2: exactly one `CampaignEnded` per campaign.
- C-3: no command is applied after Ending, except the SC-11 safety actions (`STAFF_BAN`, `FORGET`, `STAFF_KILL_SWITCH`; SIM-CORE SC-15, Q-SIM-15).
- C-4: an archived campaign's command log replays to its final state hash.
- C-5: a `TIME_LIMIT` result is emitted only when the campaign clock has reached its limit (Q-GD-29, Q-GP-10).

**In code now (`nexus.core.campaign` and the staff handlers, NX-126; SIM-CORE §4 Campaign):** the campaign clock is `running_ticks`, the ticks the world was neither paused nor ended, and the time limit, the victory hold and the objective period count it. `STAFF_CAMPAIGN_PAUSE` (rejects: `INVALID_PAYLOAD` for a sub-reason with a category other than STAFF, `REASON_REQUIRED` for a STAFF command with a blank note, `ALREADY_PAUSED`), `STAFF_CAMPAIGN_RESUME` (`NOT_PAUSED` when running) and `STAFF_CAMPAIGN_END` (Running or Paused) are handled; the pause reason and sub-reason are state, and the `Resumed` event repeats them. Victory is the coalition owning the enemy HQ, or holding at least `victory_node_frac` of the AIRBASE, FOB and PORT nodes for `victory_hold_min` running ticks in a row; the Static has no mid-war win (Q-SIM-64; the defeat rule is in code too, NX-124 part 3). At the time limit the exact scores decide, a tie being `winner: null`. After `CampaignEnded` the world is frozen (Ending) and every command is rejected with `CAMPAIGN_NOT_RUNNING` (C-3; the safety-action exemption has no command in code yet). Not in code: extensions, the Ending to AAR to Archived steps (runtime), `CampaignStarted`, `STAFF_CONFIG_RELOAD` and the other staff commands in the Paused rows.

**Defeat in code (NX-124 part 3):** the Running to Ending row for defeat fires when the coalition sanctuary's defense HP has been 0 for `campaign.defeat.hold_min` running ticks in a row (a repair resets the run; it does not advance while no viewer unit plays): `CampaignEnded{result: DEFEAT, winner: ENEMY}`, an active objective expired first. Within a tick: objective, victory, defeat, time limit.

### 4.5 Theater objective

```mermaid
stateDiagram-v2
    [*] --> Announced: rotation tick (timed mode) / admin or owner sets one
    Announced --> Active: announcement shown (same tick)
    Active --> Completed: condition met before timer
    Active --> Expired: timer elapsed
    Completed --> [*]
    Expired --> [*]
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| — | Mode `timed`: objective period boundary (`campaign.objective_period_min`, game time, Q-ALN-1), and campaign Running. Mode `off`: never. Any mode: an admin or the owner sets an objective (campaign setup is Admin/owner only; a GM cannot, Q-ALN-10). | Pick uniformly among frontline nodes (a node with a road edge to a node owned by the other side or by no one), never the SANCTUARY or the Static's HQ, using the dedicated `objective` RNG stream (SIM-CORE SC-5, Q-SM-1). An enemy-held node must be captured, an own node held for the whole period (Q-SM-11). Emit `ObjectiveAnnounced`. | Active |
| Active | Condition met (e.g., node captured or held) | Grant merit to participants. Emit `ObjectiveResolved{outcome: COMPLETED}`. Queue a sitrep. | Completed |
| Active | Timer elapsed | Emit `ObjectiveResolved{outcome: EXPIRED}` | Expired |

**Invariants**
- O-1: while the campaign is Running, at most one Active objective exists. In `timed` mode there is exactly one; in `off` mode zero unless an admin or the owner set one (Q-GD-19, Q-ALN-10).
- O-2: none while Paused. The timer is frozen (C-1).

**In code now (`nexus.core.campaign`, NX-126; SIM-CORE §4 Campaign):** only the system-picked `timed` mode (`off` has none; admin-set objectives wait for their command, Q-SIM-62). One objective is active at all times while a frontline exists (O-1): the first is announced on the first running tick and the next in the tick the previous resolves, so `campaign.objective_period_min` is an objective's lifetime and an early completion starts the next one at once. The pick is uniform over the sorted frontline candidates (a node other than a SANCTUARY, a BRIDGE or the enemy HQ, with a road neighbour, BRIDGE nodes aside, of another owner) on the `objective` stream; with none, nothing is announced and no draw is made. A node the coalition does not own is a capture objective, completed when the coalition captures it (participants: those of the `NodeCaptured`); a coalition node is a hold objective, completed only if the coalition owns it when the timer ends (Q-SIM-61; participants: the coalition commanders with a ground unit or a LANDED aircraft within `capture.radius_m`, possibly none). Otherwise it expires at the deadline. An objective still active when the campaign ends (`STAFF_CAMPAIGN_END`, or victory or the time limit that leaves one active after this tick's resolution) expires in that tick, `ObjectiveResolved{EXPIRED}` with no participants, before `CampaignEnded`, and none stays active in an ended world. `deadline_tick` is on the campaign clock. No merit is granted and no sitrep queued yet (progression, later).

### 4.6 Director tier

```mermaid
stateDiagram-v2
    [*] --> PATTERN_OF_LIFE
    PATTERN_OF_LIFE --> ALPHA: min(provocation level, CP ceiling) >= ALPHA and dwell ok
    ALPHA --> PATTERN_OF_LIFE: min(...) < ALPHA (with hysteresis) and dwell ok
    ALPHA --> BRAVO: min(provocation level, CP ceiling) >= BRAVO and dwell ok
    BRAVO --> ALPHA: min(...) < BRAVO (with hysteresis) and dwell ok
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| any | Decision window (every `director.window_s`, game time, Q-ALN-23), with CP computed from the **enemy view only** (FOW-4) | Evaluate the escalation rule (THREAT-DIRECTOR §3, Q-TD-1): tier = min(provocation level, CP ceiling from `director.tier.bravo_enter_cp`), with hysteresis (`director.tier.exit_ratio`) and `director.tier.min_dwell_s` (game time, Q-ALN-23) | same / adjacent tier |
| any | Tier changes | Emit `ThreatTierChanged{side, from, to, cp_smoothed}`. Queue a sitrep. Update the HUD. | new tier |
| any | `STAFF_DIRECTOR_OVERRIDE{force_tier}` command (OPS-ADMIN §3) while the campaign is Running; rejected with `CAMPAIGN_PAUSED` while Paused (Q-ALN-24) | Force the tier and record the override | forced tier |

**Invariants**
- D-1: tiers only move between adjacent levels, one step per decision window (never PATTERN_OF_LIFE↔BRAVO in one step), except a staff override. Default; Q-CFG-16 option `director.tier.max_step` 2 allows the two-step move, and the property then does not hold.
- D-2: no transition happens before the minimum dwell has elapsed (except a staff override).
- D-3: under CP or provocation oscillating within the hysteresis band, no flapping (property test).
- D-4: spend per window ≤ the tier budget.

### 4.7 Commander lifecycle (runtime + persistence)

```mermaid
stateDiagram-v2
    [*] --> Active: first valid command from unknown (platform, user id)
    Active --> CallsignPending: !callsign NAME (first mission completed)
    CallsignPending --> Active: approved (moderation + uniqueness)
    CallsignPending --> Active: rejected (keeps generated callsign)
    Active --> Banned: platform ban event / admin ban
    Banned --> Active: admin unban
    Active --> DeletionRequested: !forget / portal request
    Banned --> DeletionRequested: !forget / portal request
    DeletionRequested --> Deleted: deletion job runs (<= 30 days)
    Deleted --> [*]
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| — | First valid command from an unknown `(platform, platform_user_id)` | Create the commander with a generated callsign [FB-1]. Write the audit row `created`. | Active |
| Active | `!callsign NAME`, first mission completed (Q-PROG-3), and the regex passes | Normalize, moderate, check uniqueness, then queue for approval if policy requires it (Q-MOD-1/Q-MOD-2) | CallsignPending |
| CallsignPending | Approved | Set `callsign`, `callsign_kind = CUSTOM`. Audit. Issue `SYS_SET_CALLSIGN` → sim emits `CallsignChanged`. | Active |
| CallsignPending | Rejected | Keep the generated callsign. Audit with the reason. | Active |
| Active | Platform moderation ban event (e.g. Twitch `channel.ban`) or admin ban | Set `banned = true`. Issue `STAFF_BAN` (source SYSTEM for platform sync, STAFF for admin) → the sim emits `CommanderBanned`, orphans the unit and removes the commander from the reserve queue. | Banned |
| Banned | Admin unban | Set `banned = false`. Audit. | Active |
| Active / Banned | `!forget` or portal request | Set `deletion_requested_at` and create the `deletion_requests` row. Issue `FORGET` → the sim emits `CommanderForgotten` and orphans the unit. Stop accepting commands from the identity. | DeletionRequested |
| DeletionRequested | Deletion job | Delete identities. Set the callsign to the tombstone value with `callsign_kind = TOMBSTONE` and set `deleted_at` (DATA-MODEL §4.2, §6.4). Viewers see `REDACTED-` plus a random 4-character tag assigned and stored at deletion time, e.g. `REDACTED-7KQ2` (Q-DM-2, Q-ALN-29). The tag is not derived from any identifier, so it can't be reversed, and distinct deleted commanders stay distinct in replays. Shred the id→name mapping (SEC-DATA-2/3). | Deleted |

**Invariants**
- ID-1: `(platform, platform_user_id)` maps to at most one commander.
- ID-2: a Banned or DeletionRequested commander's commands are rejected before reaching the sim.
- ID-3: the raw display name is never used as a callsign.
- ID-4: a merge never sums XP (SEC-ID-6).

### 4.8 Platform adapter connection

```mermaid
stateDiagram-v2
    [*] --> Disconnected
    Disconnected --> Connecting: start / retry timer
    Connecting --> Live: session established, subscriptions confirmed
    Connecting --> Backoff: error
    Live --> Backoff: disconnect / keepalive timeout
    Backoff --> Connecting: backoff elapsed (jittered, capped)
    Live --> QuotaPaused: quota projection exhausted (YouTube)
    QuotaPaused --> Connecting: quota reset time reached
    Live --> Disconnected: staff stop
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| Connecting | Session established (Twitch: EventSub subscription confirmed) | Set health `connected`. Clear the overlay "UPLINK LOST" chip. | Live |
| Live | Disconnect or keepalive timeout | Record the reason. Start backoff. | Backoff |
| Backoff | Down longer than the overlay threshold (CHAT-GATEWAY §7) | Overlay shows "UPLINK LOST". Alert after the alert threshold. | Backoff |
| Live | YouTube quota projection says the quota is exhausted | Stop streaming. Overlay shows "YouTube commands paused until HH:MM" (computed from the platform's reset time). Alert. | QuotaPaused |

**Invariants**
- PA-1: duplicate deliveries are deduplicated by message id in every state.
- PA-2: no command is emitted from an adapter outside Live.
- PA-3: backoff is capped and jittered (no retry storm).

### 4.9 Overlay client

```mermaid
stateDiagram-v2
    [*] --> Connecting
    Connecting --> Syncing: WS open, Hello/Welcome ok
    Connecting --> UpdateRequired: major protocol mismatch
    Syncing --> Live: Snapshot applied
    Live --> Resync: delta gap / base missing
    Resync --> Live: Snapshot applied
    Live --> Connecting: WS closed
    Resync --> Connecting: WS closed
    UpdateRequired --> Connecting: reload with new bundle
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| Connecting | WS open, `Welcome` with a compatible major version | Send `Hello`. Request a snapshot. | Syncing |
| Connecting | Major version mismatch (WP-1) | Show "UPDATE REQUIRED". Trigger a reload. | UpdateRequired |
| Live | `Delta.base_tick` ≠ last applied tick | Request resync. Keep rendering the last good frame. | Resync |
| Live / Resync | No data for longer than the banner threshold (WP-5) | Show the "COMMS RESYNC" banner [FB-4] | (unchanged) |
| any | WS closed | Jittered exponential backoff (WP-5) | Connecting |

**Invariants**
- OC-1: the client never renders entities from a delta whose base it hasn't applied.
- OC-2: text is always rendered as text (WP-6, SEC-OV-1).

### 4.10 Ops / stream state

```mermaid
stateDiagram-v2
    [*] --> Live
    Live --> Degraded: a non-critical dependency down (TTS, LLM, one adapter)
    Degraded --> Live: dependency recovered
    Live --> KillSwitch: staff kill switch
    Degraded --> KillSwitch: staff kill switch
    KillSwitch --> Live: staff release
    Live --> Paused: staff pause / campaign Paused
    Paused --> Live: resume
    Live --> FallbackScene: app down / sim crash loop
    Degraded --> FallbackScene: app down
    FallbackScene --> Live: app healthy again (L1/L2 watchdog)
    Live --> Offline: encoder/RTMP down or internet down
    FallbackScene --> Offline: encoder/RTMP down
    Offline --> Live: stream re-established
```

| State | Event / guard | Action | Next |
|---|---|---|---|
| Live | TTS circuit open, LLM breaker open, or one adapter out of Live | Show a degraded chip on the overlay. Text sitreps continue. | Degraded |
| Live / Degraded | Staff kill switch (SEC-MOD-3) | Blank user text, mute TTS, freeze spawns (as logged admin commands) | KillSwitch |
| any | Sim crash loop (SIM-CORE §6: repeated crashes in the window) | OBS switches to the fallback scene "TECHNICAL DIFFICULTIES – CAMPAIGN PAUSED". Alert. | FallbackScene |
| any | Stream-live probe reports offline, or L3 heartbeat missed | Alert from the layer that can reach your phone (MONITORING-WATCHDOG) | Offline |

**Invariants**
- OPS-1: in KillSwitch, no user-derived text reaches the overlay or TTS.
- OPS-2: every transition is logged with its cause, and an admin action carries an audit row.

---

## 5. End-to-end sequence flows

### 5.1 New viewer `!join strike`
```mermaid
sequenceDiagram
    participant P as Twitch EventSub
    participant G as gateway
    participant C as commands
    participant ID as identity/persistence
    participant R as runtime inbox
    participant K as core.step
    participant B as broadcast
    participant O as overlay
    P->>G: channel.chat.message (msg id)
    G->>G: verify, dedupe, normalize -> ChatEnvelope
    G->>C: ChatEnvelope
    C->>C: ban check, rate limit, parse grammar
    C->>ID: get_or_create commander (platform, user id)
    ID-->>C: commander_id, callsign (generated if new)
    C->>R: Command{join, strike, target_tick=T+1}
    R->>K: commands for tick T+1 (canonical order)
    K-->>B: UnitSpawned event + state
    B->>O: Delta (redacted)
    O->>O: radar ping + callsign chip at base
    C-->>G: add to reply digest
    G->>P: batched digest message (rate-limited)
```
Failure branches:
- Rate-limited → dropped, and a metric is recorded.
- Cap reached → `ReserveQueueJoined`, shown in the overlay queue counter.
- Respawn delay → `CommandRejected{reason: RESPAWN_COOLDOWN}`, included in the periodic digest.

### 5.2 Kill → XP → leaderboard
```mermaid
sequenceDiagram
    participant K as core.step
    participant E as event bus
    participant PR as progression
    participant DB as SQLite writer
    participant B as broadcast
    K->>E: UnitDestroyed{killer, assists}
    E->>PR: event (async, off tick path)
    PR->>PR: apply XP table, diminishing returns, first-mission gate
    PR->>DB: batched transaction - idempotent ledger insert + commander_stats update
    DB-->>PR: ok / error
    PR->>B: leaderboard panel data (<= 1 Hz Hud)
```
The ledger is the source of truth and `commander_stats` is derived from it in the same transaction (ADR-0003 amendment, DATA-MODEL §5). If the DB write fails, XP stays queued in a bounded buffer and the failure is alerted. The leaderboard shows only persisted values, never values that weren't saved (DI-6).

### 5.3 Capture → objective complete → sitrep
```mermaid
sequenceDiagram
    participant K as core.step
    participant A as audio (sitrep queue)
    participant T as nexus-tts worker
    participant O as overlay
    K->>K: NodeCaptured, objective condition met
    K->>A: ObjectiveResolved event (COMPLETED)
    A->>A: template fill (approved callsigns, node names), moderate
    A->>T: synth request (cached by text hash)
    T-->>A: audio file path
    A->>O: Audio{sitrep_id, text, url}
    O->>O: play on Radio bus, text in sitrep log
```
If TTS is down, the circuit breaker opens and the text sitrep still shows (Degraded, 4.10).

### 5.4 Director adaptation: convoy raids → escorts
```mermaid
sequenceDiagram
    participant K as core.step (director)
    participant M as threat memory
    participant O as overlay
    loop each convoy attack visible to enemy
        K->>M: convoy_attacks += 1
    end
    K->>M: decay counters (half-life)
    K->>K: escort op utility rises above threshold
    K->>K: select EscortConvoys(route) within tier budget
    K-->>O: ThreatAdaptation event (INTEL line - Enemy has reinforced convoy escorts on Route 4)
```
Only attacks the enemy could observe (enemy view, FOW-4) increment the counter.

### 5.5 Campaign end → AAR → next campaign
```mermaid
sequenceDiagram
    participant K as core.step
    participant RT as runtime
    participant PR as progression
    participant O as overlay
    K->>RT: CampaignEnded{result}
    RT->>RT: freeze inputs, final snapshot, close command log
    RT->>PR: compute results per role
    PR-->>O: AAR data (approved callsigns only)
    RT->>RT: wait campaign.aar_duration_s
    RT->>RT: select next theater/seed, validate config
    RT->>K: start new campaign (Setup -> Running)
```

### 5.6 Crash → recovery
```mermaid
sequenceDiagram
    participant RT as runtime
    participant S as supervisor (compose restart policy; host supervisor per ADR-0012)
    participant FS as snapshots + command log
    participant O as overlay
    RT->>RT: exception in step at tick T
    RT->>FS: write crash bundle (seed, config, snapshot ref, log tail)
    RT-->>S: process exits non-zero
    O->>O: WS lost -> COMMS RESYNC banner
    S->>RT: restart
    RT->>FS: load last snapshot (tick S <= T)
    RT->>FS: replay command log S..T
    RT->>RT: verify state hash checkpoints
    RT-->>O: Welcome + Snapshot
```
After repeated crashes inside the window (SIM-CORE §6), the runtime pauses the campaign and Ops switches to FallbackScene.

### 5.7 Deploy without dropping the stream
```mermaid
sequenceDiagram
    participant D as deploy script
    participant OLD as nexus-app (old)
    participant NEW as nexus-app (new)
    participant O as overlay
    D->>D: cosign verify new digest
    D->>OLD: request snapshot at next tick boundary
    OLD-->>D: snapshot written (fsync), tick N
    D->>OLD: stop
    O->>O: COMMS RESYNC banner
    D->>NEW: start, load snapshot N
    NEW->>NEW: snapshot schema compatible? else refuse
    NEW-->>O: Welcome + Snapshot
    D->>NEW: health + smoke check
    alt unhealthy
        D->>NEW: stop
        D->>OLD: start previous digest, load snapshot N
    end
```

### 5.8 Moderation incident → kill switch → ban cascade
```mermaid
sequenceDiagram
    participant OP as owner (phone, admin console)
    participant AD as admin API
    participant RT as runtime
    participant K as core.step
    participant O as overlay
    OP->>AD: kill switch ON
    AD->>RT: logged admin command
    RT->>O: Control{kill_switch: on} (blank user text, mute TTS)
    RT->>K: freeze spawns (command)
    OP->>AD: ban commander X
    AD->>RT: STAFF_BAN (covers all linked identities)
    RT->>K: STAFF_BAN applied, CommanderBanned, X's unit orphaned
    OP->>AD: kill switch OFF
```
A Twitch `channel.ban` event drives the same ban path without the owner (CHAT-GATEWAY §2).

### 5.9 Internet outage (3-layer watchdog)
```mermaid
sequenceDiagram
    participant SP as stream PC
    participant LS as Linux server (L2)
    participant EX as external heartbeat (L3)
    participant PH as owner phone
    Note over SP,LS: ISP goes down
    SP-xEX: heartbeat ping fails
    LS-xEX: heartbeat ping fails
    LS->>SP: LAN probes still OK (app, OBS)
    LS->>LS: queue alert (cannot send)
    EX->>PH: missed heartbeats -> alert
    Note over SP,LS: ISP restored
    LS->>PH: send queued alerts + outage duration
    SP->>SP: OBS reconnects RTMP (setting must be enabled)
```

### 5.10 LLM advisor late → rule fallback [FB-2]
```mermaid
sequenceDiagram
    participant K as core.step (director)
    participant RT as runtime
    participant L as advisor (async, P4)
    K->>RT: top-K candidate ops + redacted summary (no user strings)
    RT->>L: request with deadline (2 decision windows)
    alt valid response before deadline
        L-->>RT: {choice_index, op_name, rationale}
        RT->>RT: schema + range + moderation checks
        RT->>K: AdvisorChoice command (logged)
    else late / invalid / over budget
        RT->>RT: advisor_fallback metric + log
        K->>K: rule picks highest-utility op
    end
```

---

## 6. Failure modes (cross-cutting)
| Failure | Machine affected | Required behavior |
|---|---|---|
| Command for a terminal unit | Unit | `CommandRejected{reason: NO_ACTIVE_UNIT}`. No exception (SC-7). |
| Ban arrives mid-capture | Unit, Node | The unit is orphaned. Its capture contribution stops the same tick. |
| Theater config invalid at rotation | Campaign | Stay in Setup, alert, and don't substitute a theater (DI-2). |
| Adapter flapping | Adapter | Backoff is capped. The alert fires once per incident, not once per flap. |
| Snapshot schema change without migration | Deploy | Refuse the deploy (5.7). Never load partially. |

## 7. Test plan
| Invariant(s) | Test type | Location (planned) |
|---|---|---|
| U-1…U-9 | Property (hypothesis): random command sequences, including pauses and node flips | `services/sim/tests/property/test_unit_lifecycle.py` |
| N-1…N-5 | Property + scenario | `.../test_capture.py` |
| B-1, B-2 | Property: pathfinding after destruction | `.../test_bridges.py` |
| B-3 | Scenario: a direct order to a bridge holds and never fires on it; a STRIKE claim drops it | `.../test_bridges.py`, `.../test_order_hold.py` |
| C-1…C-5 | Scenario + golden replay (including a time-limit end with a clear winner and an exact tie) | `.../test_campaign.py`, `tests/golden/` |
| O-1, O-2 | Property | `.../test_objectives.py` |
| D-1…D-4 | Property: oscillating CP and provocation | `.../test_director.py` |
| ID-1…ID-4 | Unit + integration (SQLite) | `services/sim/tests/identity/` |
| PA-1…PA-3 | Adapter fixture tests | `services/sim/tests/gateway/` |
| OC-1, OC-2 | Vitest + Playwright | `apps/overlay/tests/` |
| OPS-1, OPS-2 | Integration (kill switch) | `tests/integration/test_kill_switch.py` |
| Flows 5.6, 5.7 | Integration: kill/restore, deploy rehearsal | `tests/integration/`, staging |

Paths are planned names; they're created with their tracker items.

## 8. Decisions folded in, and open questions
These decisions (2026-10-17 and 2026-10-18) are folded into the tables above:
- **Q-GD-4 (amended):** no automatic clock pause for lack of humans; the Static drops to Pattern of Life (THREAT-DIRECTOR §5a). Only a pause with a reason category stops the clock (§4.4, Q-ALN-3).
- **Q-GD-7, Q-TH-7:** defeat = the sanctuary's defense HP held at 0 for `campaign.defeat.hold_min`; the sanctuary is uncapturable (§4.2 N-4, §4.4).
- **Q-GD-8:** sea domain in **P3** (§4.1 notes).
- **Q-GD-11:** trucks do slow field repair; engineers repair fast and build (§4.3).
- **Q-GD-19 / Q-GD-26 / Q-CBT-1/6/7 / Q-GD-27:** objective modes (§4.5), Tasking Board and auto-tasking (Q-GP-23), damage states, stance, munitions and repair (§4.1).
- **Q-MOD-1 / Q-MOD-2 / Q-SM-3:** generated callsigns; custom callsigns after the first completed mission (Q-PROG-3), automated moderation with a review queue, and manual owner approval during alpha (§4.7).
- **Q-SM-1:** objective selection uses its own `objective` RNG stream (SIM-CORE SC-5).
- **Q-SM-4:** rotate theater archetypes with no back-to-back repeats; reuse the first theater with a new seed until more exist; admins can override via scheduling.
- **Q-SM-5:** superseded; `campaign.pause_after_no_humans_s` does not exist.
- **Spec-alignment batch (2026-10-18):** Q-ALN-1 (game time vs world time, §4.1, §4.4, §4.5), Q-ALN-2 (pause freezes the world; allowed commands, §4.4, U-8), Q-ALN-3 (pause reason categories, §4.4), Q-ALN-5 (respawn delay in game time, §4.1), Q-ALN-8 and Q-GD-35 (idle handoff and retire are the only idle rule, §4.1), Q-ALN-9 (AUTO unit keeps its slot; reclaim, §4.1, U-7), Q-ALN-10 (objectives set by admin or owner only, §4.5), Q-OPS-8 and Q-OPS-9 (automatic pauses, §4.4), Q-PROG-6 (no minimum-humans XP rule, §5.2), Q-DM-2 (`REDACTED-…`, §4.7).
- **Spec-alignment batch (2026-10-18, continued):** Q-ALN-23 (capture, decay and bridge repair on world time; director window and dwell on game time, §4.2, §4.3, §4.6), Q-ALN-24 (staff and system commands while Paused, §4.4, U-8), Q-ALN-25 (idle retire of a Disabled unit; idle handoff for `hold` units, §4.1), Q-ALN-26 (`JOIN` while Paused always queues; idle-timer resets; AUTO tag, §4.1, §4.4), Q-ALN-29 (`REDACTED-` tag, §4.7), Q-ALN-31 (pause sub-reason, §4.4).
- **Q-GD-29:** time-limit score, no Stalemate result (§4.4, C-5, Q-GP-10).
- **Q-GD-32:** units parked at a captured base escape or are destroyed (§4.1, §4.2, U-9); garrison and empty-base capture multipliers (§4.2, N-5).
- **Spec-alignment batch 3 (2026-10-18):** Q-ALN-33 (combat-capable defenders freeze capture; defenders that cannot contest slow it, §4.2, N-5), Q-ALN-36 (unban, purge and set callsign apply while Paused; advisor choices and GM commands other than a release are rejected, §4.4, U-8).

- **Grill 2026-10-21 (Q-SM-6 … Q-SM-12):** §4.1–4.6 approved; logistics units count as half a capturer; garrison and empty-base capture multipliers; the time-limit score weights; how units escape a captured base; how timed objectives are picked; objective voting and a self-directed mode parked in GAMEPLAY-LATER.

Still open here: nothing for §4.1–4.6. §4.7–4.10 and §5 are grilled when P2 starts on them.
