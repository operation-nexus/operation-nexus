# SPEC: Command and intent catalog

Status: Review · Owner: — · Tracker: NX-312 · Related: CONTRACTS §5.2, CHAT-GATEWAY §9, GAMEPLAY-LATER §3, LLM-ADVISORS

> The one list of every chat command (Q-CMD-1, Q-AI-2). Grilled with the owner on 2026-10-20. This file says **what exists, its syntax, gate and phase**; payloads and reject reasons are in CONTRACTS §5.2 (for reserved commands, written there with the handler), gateway behavior in CHAT-GATEWAY, later-phase design notes in GAMEPLAY-LATER §3. Ranks are internal ids (PROGRESSION §3, PROPOSED).

## 1. Rules
- **CC-1 One intent per command.** Each chat command maps 1:1 to an intent, its `CommandKind`. Aliases (`!status` → `ME`) map to the same intent and add none. Info commands (`!help`, `!guide`, `!rules`, `!link`) have no intent: they never reach the sim and only add a digest line.
- **CC-2 No command in one place (AGENTS.md rule 6a).** A command is its row here, its `contracts/commands/` schema, its parser entry and its handler, added or removed in the same PR. A reserved command has a row here and nothing else.
- **CC-3 `!order` uses only catalog intents.** The `!order` parser (LLM-ADVISORS, P4) produces `TacticalOrder`, whose `mission` is one of the own-unit intents in this catalog that have a handler when `!order` ships; the exact subset is decided with the `!order` spec. An LLM prompt lists only intents and enum values the code handles.
- **CC-4 Unknown is nothing.** A name the parser doesn't know is ignored; ordinary chat is ignored.
- **CC-5 Change process.** Adding, renaming or removing a command updates this table, CONTRACTS §5.2 (or its reserved list), the rate-limit class in CHAT-GATEWAY §5, and the `!help` digest text in the same PR. A reserved command moving to live takes its row out of the reserved list.

## 2. First build (live)
| Command | Intent (`CommandKind`) | Args | Min rank | Handled by | Phase | Rate class | Defined in |
|---|---|---|---|---|---|---|---|
| `!join <role> [<node>\|<callsign>\|hold]` | `JOIN` | role; optional node, friendly callsign or `hold` | O-1 | sim | P1 | Deploy | GAMEPLAY §1b, §4; CONTRACTS §5.2; schema `contracts/commands/join.json` |
| `!target <node\|callsign>` | `TARGET` | node (fuzzy) or friendly callsign (exact wins, Q-GP-39) | O-1 | sim | P1 | Unit correction | GAMEPLAY §1b, §3; CONTRACTS §5.2 |
| `!rtb` | `RTB` | — | O-1 | sim (nearest friendly base) | P1 | Unit correction | GAMEPLAY §3; CONTRACTS §5.2 |
| `!rebase <node>` | `REBASE` | friendly node | O-1 | sim | P1 | Unit correction | GAMEPLAY §3; CONTRACTS §5.2 |
| `!me`, alias `!status` | `ME` | — | O-1 | sim (informational, never resets idle timers) | P1 | Info | CONTRACTS §5.2; STATE-MACHINES §4.1 |
| `!callsign <NAME>` | `SET_CALLSIGN` | `^[A-Z][A-Z0-9-]{2,11}$` | first completed mission (Q-PROG-3) | identity + moderation | P1 | open (Q-CMD-3) | GAMEPLAY §3; CONTRACTS §5.2 |
| `!quiet` | `QUIET` | — (toggle) | any | identity | ships with taunts that name operators | Info | CHAT-GATEWAY §9 |
| `!forget` | `FORGET` | — | any | identity (sim only to despawn the unit) | P1 | open (Q-CMD-3) | CHAT-GATEWAY §9; SEC-DATA-3 |
| `!help`, `!guide`, `!rules` | none (info) | — | any | gateway digest | P1 | Info | CHAT-GATEWAY §9 |
| `!link` | none (info) | — | any | gateway digest | with YouTube (beta) | Info | CHAT-GATEWAY §9; IDENTITY §4 |

Only `JOIN` has a schema today (NX-021 seed); every other row gets its schema in the PR that adds its handler (CC-2).

## 3. Reserved (later phases)
No schema, parser entry or handler until their phase (CONTRACTS §5.2 reserved list). Design notes are in GAMEPLAY-LATER §3.

| Command | Intent | Min rank | Phase / returns with |
|---|---|---|---|
| `!stance <press\|standard\|cautious\|guns>`; also `!join <role> <stance>` | `STANCE` | O-1 | behind a feature flag (Q-GP-3); COMBAT §5.6 |
| `!rally <node> <attack\|defend\|supply>` | `RALLY` | O-3 | later (GAMEPLAY-LATER §3) |
| `!rescue <marker>` | `RESCUE` | O-1, needs a suitable unit | CSAR, P4+ (NX-290) |
| `!vector <bearing> <km>` | `VECTOR` | O-2 | later (GAMEPLAY-LATER §3) |
| `!sead`, `!artillery` | `SPAWN_SPECIALIST` | O-3 (PROGRESSION §3) | P4, NX-212 (Q-CMD-2: must not be dropped) |
| `!engineer`, `!jammer`, `!awacs` | `SPAWN_SPECIALIST` | O-4 (PROGRESSION §3) | P4, NX-212 |
| `!package <NAME>` | `PACKAGE_CREATE` | O-5 | P4 (NX-214) |
| `!wingman` | `PACKAGE_JOIN` | O-1 | P4 (NX-214) |
| `!doctrine <name>` | `SET_DOCTRINE` | O-3 | P4 (NX-213) |
| `!order <text ≤ 200>` | `ORDER` (parsed into `ORDER_PARSED`) | O-3 | P4, LLM-parsed, own unit only (CC-3) |
| `!scout <sector>` | `SCOUT` | any, while queued | moved out (GAMEPLAY-LATER, Q-GP-9) |

## 4. Not chat commands
Staff, system and advisor commands (`STAFF_*`, `SYS_*`, `ADVISOR_CHOICE`) come from the Command Center, the runtime or an advisor, never from chat. They are listed in CONTRACTS §5.2 only.

## 5. Test plan
| Req | Test |
|---|---|
| CC-1 | Parser table test: every live command and alias maps to exactly the intent in §2 |
| CC-2 | Repo check (when the parser exists): every §2 intent that has a handler is in `contracts/common/enums.json`; every chat `CommandKind` in the enum has a parser entry and a handler; reserved intents are absent from the enum |
| CC-4 | Fuzz: unknown `!words` and plain chat produce no command |

## 6. Open questions
- **Q-CMD-3:** rate-limit class for `!callsign` and `!forget` (CHAT-GATEWAY §5 assigns none).

Decisions: Q-CMD-1, Q-CMD-2, Q-AI-2.
